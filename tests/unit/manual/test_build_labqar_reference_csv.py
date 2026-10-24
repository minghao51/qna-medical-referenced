"""Offline tests for the LabQAR reference-ranges CSV builder script.

Loads ``scripts/manual/build_labqar_reference_csv.py`` through importlib and
exercises it with synthetic tmp-path fixtures only; the real ``data/raw``
downloads are never read.
"""

from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[3] / "scripts" / "manual" / "build_labqar_reference_csv.py"
)
_MODULE_NAME = "build_labqar_reference_csv_under_test"
_HEADER = ["test_name", "normal_range", "unit", "category", "notes"]
_NOTES_SOURCE = "source=LabQAR figshare DOI 10.6084/m9.figshare.29391863 (CC BY 4.0)"


def _load_builder_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, _SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("LabQAR CSV builder script could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def builder() -> ModuleType:
    return _load_builder_module()


def _question(name: str, unit: str, specimen: str, gender: str, age: str) -> str:
    return (
        f"For the lab test '{name}' measuring in '{unit}' in Specimen '{specimen}' "
        f"for '{gender}' and '{age}', what is the correct lower and upper bound "
        "range values in SI reference range?"
    )


def _set1_record(record_id: int, question: str, answer: str) -> dict[str, Any]:
    return {"ID": record_id, "Question": question, "Answer": answer}


def _set2_record(
    record_id: int, question: str, lower: Any, upper: Any, unit: str = "mmol/L"
) -> dict[str, Any]:
    return {
        "ID": record_id,
        "Question": question,
        "Choices": "\nA: High\nB: Normal\nC: Low",
        "Answer": "B",
        "reference_range": {"lower_bound": lower, "upper_bound": upper, "unit": unit},
    }


def _write_labqar_inputs(
    input_dir: Path, set1_records: list[dict[str, Any]], set2_records: list[dict[str, Any]]
) -> None:
    input_dir.mkdir(parents=True, exist_ok=True)
    (input_dir / "Set_1.json").write_text(json.dumps(set1_records), encoding="utf-8")
    (input_dir / "Set_2.json").write_text(json.dumps(set2_records), encoding="utf-8")


def _sample_records(*, id3_lower: Any = None, id3_upper: Any = None, id3_answer: str = "66-83"):
    """Three-record synthetic mirror of the real LabQAR schema (IDs 1-3)."""
    set1 = [
        _set1_record(
            1,
            _question("Acetaminophen", "μmol/L", "Serum, plasma", "any gender", "any age group"),
            "70-200",
        ),
        _set1_record(2, _question("Albumin", "g/L", "Serum", "Female", "Adult"), "35-52"),
        _set1_record(
            3,
            _question("Albumin", "g/L", "Serum", "any gender", "any age group"),
            id3_answer,
        ),
    ]
    set2 = [
        _set2_record(1, set1[0]["Question"], 70, 200, unit="μmol/L"),
        _set2_record(2, set1[1]["Question"], 35.0, 52.0),
        _set2_record(3, set1[2]["Question"], id3_lower, id3_upper),
    ]
    return set1, set2


def _read_csv_rows(output: Path) -> list[list[str]]:
    with output.open(newline="", encoding="utf-8") as handle:
        return list(csv.reader(handle))


def test_writes_exact_header_and_rendered_rows(
    builder: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    input_dir = tmp_path / "LabQAR"
    set1, set2 = _sample_records()
    _write_labqar_inputs(input_dir, set1, set2)
    output = tmp_path / "out" / "reference_ranges.csv"

    exit_code = builder.main(["--input-dir", str(input_dir), "--output", str(output)])

    assert exit_code == 0
    assert capsys.readouterr().out == "rows_written=3 skipped_total=0\n"
    raw = output.read_bytes()
    assert raw.split(b"\n")[0] == b"test_name,normal_range,unit,category,notes"
    assert b"\r" not in raw
    rows = _read_csv_rows(output)
    assert rows[0] == _HEADER
    # Sorted by test_name then ID; int bounds stay ints, float bounds stay floats.
    assert [row[0] for row in rows[1:]] == ["Acetaminophen", "Albumin", "Albumin"]
    assert rows[1] == [
        "Acetaminophen",
        "70-200",
        "μmol/L",
        "laboratory_reference",
        "specimen=Serum, plasma; gender=any gender; age=any age group; " + _NOTES_SOURCE,
    ]
    assert rows[2][1] == "35.0-52.0"
    assert rows[2][4] == "specimen=Serum; gender=Female; age=Adult; " + _NOTES_SOURCE
    assert rows[3][1] == "66-83"


def test_output_is_byte_identical_across_runs(builder: ModuleType, tmp_path: Path):
    input_dir = tmp_path / "LabQAR"
    set1, set2 = _sample_records()
    _write_labqar_inputs(input_dir, set1, set2)

    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"
    assert builder.main(["--input-dir", str(input_dir), "--output", str(first)]) == 0
    assert builder.main(["--input-dir", str(input_dir), "--output", str(second)]) == 0

    assert first.read_bytes() == second.read_bytes()
    assert not list(tmp_path.glob("*.tmp"))


def test_skips_records_without_parseable_fallback(
    builder: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    input_dir = tmp_path / "LabQAR"
    set1, set2 = _sample_records(id3_answer="<0.1")
    _write_labqar_inputs(input_dir, set1, set2)
    output = tmp_path / "reference_ranges.csv"

    exit_code = builder.main(["--input-dir", str(input_dir), "--output", str(output)])

    assert exit_code == 0
    assert capsys.readouterr().out == "rows_written=2 skipped_total=1\n"
    rows = _read_csv_rows(output)
    assert rows[0] == _HEADER
    assert [row[0] for row in rows[1:]] == ["Acetaminophen", "Albumin"]


def test_fails_closed_when_set2_missing(
    builder: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    input_dir = tmp_path / "LabQAR"
    set1, _ = _sample_records()
    _write_labqar_inputs(input_dir, set1, [])
    (input_dir / "Set_2.json").unlink()
    output = tmp_path / "reference_ranges.csv"

    exit_code = builder.main(["--input-dir", str(input_dir), "--output", str(output)])

    assert exit_code == 1
    assert "input file not found" in capsys.readouterr().err
    assert not output.exists()
    assert not list(tmp_path.glob("*.tmp"))


def test_fails_closed_without_partial_output_on_non_numeric_bounds(
    builder: ModuleType, tmp_path: Path
):
    input_dir = tmp_path / "LabQAR"
    set1, set2 = _sample_records()
    set2[2]["reference_range"]["lower_bound"] = "abc"
    _write_labqar_inputs(input_dir, set1, set2)
    output = tmp_path / "reference_ranges.csv"

    exit_code = builder.main(["--input-dir", str(input_dir), "--output", str(output)])

    assert exit_code != 0
    assert not output.exists()
    assert not list(tmp_path.glob("*.tmp"))


def test_falls_back_when_one_bound_missing_and_other_finite(
    builder: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    input_dir = tmp_path / "LabQAR"
    set1, set2 = _sample_records()
    set2[2]["reference_range"] = {"lower_bound": None, "upper_bound": 83.0, "unit": "g/L"}
    _write_labqar_inputs(input_dir, set1, set2)
    output = tmp_path / "reference_ranges.csv"

    exit_code = builder.main(["--input-dir", str(input_dir), "--output", str(output)])

    assert exit_code == 0
    assert capsys.readouterr().out == "rows_written=3 skipped_total=0\n"
    assert _read_csv_rows(output)[3][1] == "66-83"  # Set_1 fallback for the missing bound


def test_fails_closed_without_partial_output_on_non_finite_bound(
    builder: ModuleType, tmp_path: Path
):
    input_dir = tmp_path / "LabQAR"
    set1, set2 = _sample_records()  # Set_1 answer "66-83" is a parseable fallback
    set2[2]["reference_range"]["lower_bound"] = float("nan")
    _write_labqar_inputs(input_dir, set1, set2)
    output = tmp_path / "reference_ranges.csv"

    exit_code = builder.main(["--input-dir", str(input_dir), "--output", str(output)])

    assert exit_code != 0
    assert not output.exists()
    assert not list(tmp_path.glob("*.tmp"))


def test_fails_closed_without_partial_output_when_lower_exceeds_upper(
    builder: ModuleType, tmp_path: Path
):
    input_dir = tmp_path / "LabQAR"
    set1, set2 = _sample_records()
    set2[2]["reference_range"] = {"lower_bound": 83.0, "upper_bound": 66.0, "unit": "g/L"}
    _write_labqar_inputs(input_dir, set1, set2)
    output = tmp_path / "reference_ranges.csv"

    exit_code = builder.main(["--input-dir", str(input_dir), "--output", str(output)])

    assert exit_code != 0
    assert not output.exists()
    assert not list(tmp_path.glob("*.tmp"))
