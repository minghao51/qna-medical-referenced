"""L4 reference data quality checks."""

from __future__ import annotations

import csv
import re
from collections import Counter
from pathlib import Path
from typing import Any

from src.config import DATA_RAW_DIR
from src.ingestion.steps.load_reference_data import REQUIRED_CSV_COLUMNS


def assess_l4_reference_quality(data_raw_dir: Path | None = None) -> dict[str, Any]:
    data_dir = Path(data_raw_dir or DATA_RAW_DIR)
    csv_path = data_dir / "LabQAR" / "reference_ranges.csv"
    if not csv_path.exists():
        return {
            "aggregate": {"csv_exists": False, "row_count": 0},
            "records": [],
            "findings": [
                {"severity": "warning", "message": "Reference CSV missing", "stage": "L4"}
            ],
        }

    records: list[dict[str, Any]] = []
    duplicate_names: Counter[str] = Counter()
    complete_rows = 0
    parseable_ranges = 0
    findings = []

    with open(csv_path, "r", encoding="utf-8", errors="ignore") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        missing_cols = sorted(REQUIRED_CSV_COLUMNS - set(fieldnames))
        if missing_cols:
            findings.append(
                {"severity": "error", "message": f"Missing columns: {missing_cols}", "stage": "L4"}
            )
        for idx, row in enumerate(reader):
            test_name = (row.get("test_name") or "").strip()
            duplicate_names[test_name.lower()] += 1
            values = {k: (row.get(k) or "").strip() for k in REQUIRED_CSV_COLUMNS}
            is_complete = all(values.values())
            complete_rows += int(is_complete)
            range_value = values.get("normal_range", "")
            parseable = bool(re.search(r"\d", range_value))
            parseable_ranges += int(parseable)
            records.append(
                {
                    "row_index": idx,
                    "test_name": test_name,
                    "is_complete": is_complete,
                    "normal_range_parseable": parseable,
                    "notes_empty": not bool(values.get("notes")),
                }
            )

    row_count = len(records)
    duplicate_entries = sum(
        count - 1 for name, count in duplicate_names.items() if name and count > 1
    )
    aggregate = {
        "csv_exists": True,
        "row_count": row_count,
        "schema_valid": not any(f["severity"] == "error" for f in findings),
        "required_columns_present": not any(f["severity"] == "error" for f in findings),
        "row_completeness_rate": (complete_rows / row_count) if row_count else 0.0,
        "duplicate_test_name_rate": (duplicate_entries / row_count) if row_count else 0.0,
        "normal_range_parseable_rate": (parseable_ranges / row_count) if row_count else 0.0,
    }
    return {"aggregate": aggregate, "records": records, "findings": findings}
