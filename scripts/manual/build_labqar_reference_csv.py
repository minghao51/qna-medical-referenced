#!/usr/bin/env python3
"""Build the reference-ranges CSV from the downloaded LabQAR figshare JSON files.

Converts the two local LabQAR figshare exports (DOI 10.6084/m9.figshare.29391863,
CC BY 4.0) into the CSV consumed by ``src.ingestion.steps.load_reference_data``
(``REQUIRED_CSV_COLUMNS``: test_name,normal_range,unit,category,notes).

Row sourcing per Set_2 record (the structured, preferred source):

- ``reference_range.lower_bound``/``upper_bound`` are used as given (ints stay
  ints, floats stay floats; ``normal_range`` renders as f"{lower}-{upper}").
- When at least one bound is missing (``null``) and every present bound is a
  finite number, the Set_1 "Answer" bounds are used as a fallback; if the
  Set_1 answer is unparseable the row is skipped and counted in
  ``skipped_total`` (printed in the summary line).

Fail closed: missing input files, missing required keys, present-but-non-numeric
or non-finite bounds, or lower > upper exit nonzero with a stderr message and
never leave an output file (the CSV is written to a sibling temp file and
atomically renamed).

Deterministic: identical inputs yield byte-identical output (rows sorted by
test_name then ID, unix newlines, no trailing whitespace). Offline only: reads
local files, performs no network access.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_DIR = PROJECT_ROOT / "data" / "raw" / "LabQAR"
DEFAULT_OUTPUT_PATH = DEFAULT_INPUT_DIR / "reference_ranges.csv"

CSV_HEADER = ("test_name", "normal_range", "unit", "category", "notes")
CATEGORY = "laboratory_reference"
NOTES_SOURCE = "source=LabQAR figshare DOI 10.6084/m9.figshare.29391863 (CC BY 4.0)"

_TEST_NAME_PATTERN = re.compile(r"lab test '([^']+)'")
_SPECIMEN_PATTERN = re.compile(r"Specimen '([^']*)'")
_GENDER_AGE_PATTERN = re.compile(r"for '([^']*)' and '([^']*)'")
# Set_1 "Answer" bounds: "<lower>-<upper>" with a plain or en dash; both required.
_SET1_BOUNDS_PATTERN = re.compile(r"\s*(-?\d+(?:\.\d+)?)\s*[-\u2013]\s*(-?\d+(?:\.\d+)?)\s*")
_INT_TEXT_PATTERN = re.compile(r"-?\d+")


class LabQarBuildError(ValueError):
    """A fail-closed input-contract violation; the output CSV is never written."""


def _load_json_records(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise LabQarBuildError(f"input file not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise LabQarBuildError(f"cannot read LabQAR JSON {path}: {error}") from error
    if not isinstance(payload, list) or not all(isinstance(record, dict) for record in payload):
        raise LabQarBuildError(f"{path} must contain a JSON array of objects")
    return payload


def _require_keys(record: dict[str, Any], keys: tuple[str, ...], path: Path) -> None:
    missing = [key for key in keys if key not in record]
    if missing:
        raise LabQarBuildError(f"{path}: record {record.get('ID')!r} missing key(s) {missing}")


def _require_int_id(record: dict[str, Any], path: Path) -> int:
    record_id = record.get("ID")
    if isinstance(record_id, bool) or not isinstance(record_id, int):
        raise LabQarBuildError(f"{path}: record ID is not an integer: {record_id!r}")
    return record_id


def _number_from_text(text: str) -> int | float:
    return int(text) if _INT_TEXT_PATTERN.fullmatch(text) else float(text)


def _validated_bound(path: Path, record_id: int, raw: Any) -> int | float | None:
    """Return a present bound as a finite number, or None when missing.

    A bound that is present but not a finite number (a string, bool, list,
    NaN, Infinity, ...) is a contract violation: it must never silently
    trigger the Set_1 fallback.
    """
    if raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise LabQarBuildError(f"{path}: record {record_id} has non-numeric reference_range bounds")
    bound: int | float = raw
    try:
        finite = math.isfinite(bound)
    except OverflowError:  # int too large to convert to float
        finite = False
    if not finite:
        raise LabQarBuildError(f"{path}: record {record_id} has non-finite reference_range bounds")
    return bound


def _parse_set1_answer(answer: Any) -> tuple[int | float, int | float] | None:
    """Return the (lower, upper) bounds of a Set_1 "Answer", or None if unparseable."""
    match = _SET1_BOUNDS_PATTERN.fullmatch(answer) if isinstance(answer, str) else None
    if match is None:
        return None
    return _number_from_text(match.group(1)), _number_from_text(match.group(2))


def _extract_test_name(question: str, record_id: int) -> str:
    match = _TEST_NAME_PATTERN.search(question)
    if match is None:
        raise LabQarBuildError(f"Set_2 record {record_id}: Question has no quoted lab test name")
    return match.group(1)


def _extract_specimen(question: str) -> str:
    match = _SPECIMEN_PATTERN.search(question)
    return match.group(1) if match else ""


def _extract_gender_age(question: str) -> tuple[str, str]:
    match = _GENDER_AGE_PATTERN.search(question)
    return (match.group(1), match.group(2)) if match else ("", "")


def build_rows(
    set1_path: Path, set2_path: Path
) -> tuple[list[tuple[str, str, str, str, str]], int]:
    """Return (csv_rows, skipped_total) or raise LabQarBuildError on contract violations."""
    set1_records = _load_json_records(set1_path)
    set2_records = _load_json_records(set2_path)

    set1_answers_by_id: dict[int, Any] = {}
    for record in set1_records:
        _require_keys(record, ("ID", "Answer"), set1_path)
        record_id = _require_int_id(record, set1_path)
        if record_id in set1_answers_by_id:
            raise LabQarBuildError(f"{set1_path}: duplicate record ID {record_id}")
        set1_answers_by_id[record_id] = record["Answer"]

    decorated: list[tuple[str, int, tuple[str, str, str, str, str]]] = []
    skipped_total = 0
    seen_ids: set[int] = set()
    for record in set2_records:
        _require_keys(record, ("ID", "Question", "reference_range"), set2_path)
        record_id = _require_int_id(record, set2_path)
        if record_id in seen_ids:
            raise LabQarBuildError(f"{set2_path}: duplicate record ID {record_id}")
        seen_ids.add(record_id)
        if record_id not in set1_answers_by_id:
            raise LabQarBuildError(f"{set2_path}: record ID {record_id} has no Set_1 counterpart")
        question = record["Question"]
        if not isinstance(question, str):
            raise LabQarBuildError(f"Set_2 record {record_id}: Question is not a string")
        reference_range = record["reference_range"]
        if not isinstance(reference_range, dict):
            raise LabQarBuildError(
                f"{set2_path}: record {record_id} reference_range is not an object"
            )
        _require_keys(reference_range, ("lower_bound", "upper_bound", "unit"), set2_path)

        lower = _validated_bound(set2_path, record_id, reference_range["lower_bound"])
        upper = _validated_bound(set2_path, record_id, reference_range["upper_bound"])
        if lower is None or upper is None:
            # At least one bound is missing and every present bound is a
            # validated finite number: fall back to the Set_1 answer bounds.
            fallback = _parse_set1_answer(set1_answers_by_id[record_id])
            if fallback is None:
                skipped_total += 1
                continue
            lower, upper = fallback
        if lower > upper:
            raise LabQarBuildError(f"{set2_path}: record {record_id} has lower_bound > upper_bound")

        test_name = _extract_test_name(question, record_id)
        specimen = _extract_specimen(question)
        gender, age = _extract_gender_age(question)
        notes = f"specimen={specimen}; gender={gender}; age={age}; {NOTES_SOURCE}"
        row = (test_name, f"{lower}-{upper}", str(reference_range["unit"]), CATEGORY, notes)
        decorated.append((test_name, record_id, row))

    decorated.sort(key=lambda item: (item[0], item[1]))
    return [item[2] for item in decorated], skipped_total


def write_reference_csv(output_path: Path, rows: list[tuple[str, str, str, str, str]]) -> None:
    """Write the CSV atomically: temp file next to the destination, then os.replace."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_name(output_path.name + ".tmp")
    try:
        with temp_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(CSV_HEADER)
            writer.writerows(rows)
        os.replace(temp_path, output_path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build data/raw/LabQAR/reference_ranges.csv from the downloaded LabQAR "
            "figshare JSON files (offline, deterministic)."
        )
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help="Directory containing Set_1.json and Set_2.json (default: data/raw/LabQAR).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Output CSV path (default: data/raw/LabQAR/reference_ranges.csv).",
    )
    args = parser.parse_args(argv)

    try:
        rows, skipped_total = build_rows(
            args.input_dir / "Set_1.json", args.input_dir / "Set_2.json"
        )
        write_reference_csv(args.output, rows)
    except (LabQarBuildError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(f"rows_written={len(rows)} skipped_total={skipped_total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
