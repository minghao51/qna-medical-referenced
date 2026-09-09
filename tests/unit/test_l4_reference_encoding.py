"""Unit tests for L4 reference check encoding handling."""

from __future__ import annotations

from pathlib import Path

from src.evals.checks.l4_reference import assess_l4_reference_quality

CSV_HEADER = "test_name,normal_range,unit,category,notes\n"


def _write_csv(data_dir: Path, payload: bytes) -> None:
    csv_dir = data_dir / "LabQAR"
    csv_dir.mkdir(parents=True)
    (csv_dir / "reference_ranges.csv").write_bytes(payload)


def test_valid_utf8_csv_has_no_encoding_finding(tmp_path):
    _write_csv(tmp_path, CSV_HEADER.encode() + b"LDL,< 3.0,mmol/L,lipids,fasting sample\n")
    result = assess_l4_reference_quality(data_raw_dir=tmp_path)
    assert result["aggregate"]["csv_exists"] is True
    assert result["aggregate"]["row_count"] == 1
    assert result["findings"] == []


def test_invalid_utf8_emits_warning_and_replaces_bytes(tmp_path):
    # b"\xff" is never valid UTF-8; the check must flag it instead of
    # silently mangling it (the old errors="ignore" behaviour).
    _write_csv(
        tmp_path,
        CSV_HEADER.encode("utf-8") + b"LDL\xff,< 3.0,mmol/L,lipids,note\n",
    )
    result = assess_l4_reference_quality(data_raw_dir=tmp_path)
    assert result["aggregate"]["row_count"] == 1
    assert result["findings"] == [
        {
            "severity": "warning",
            "message": "Reference CSV is not valid UTF-8; undecodable bytes were replaced with U+FFFD",
            "stage": "L4",
        }
    ]
    # The row is still parsed; the bad byte became U+FFFD.
    assert result["records"][0]["test_name"] == "LDL\ufffd"
