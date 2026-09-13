#!/usr/bin/env python3
"""
L4: Reference Data Loader - Load CSV reference ranges data.
"""

import csv
import logging
from pathlib import Path

from src.config import DATA_RAW_DIR
from src.core.source_metadata import canonical_source_label
from src.ingestion.steps.load_pdfs import read_pdf_with_pypdf

logger = logging.getLogger(__name__)

REQUIRED_CSV_COLUMNS = {"test_name", "normal_range", "unit", "category", "notes"}

# Shared row rendering for both the flat-text and per-doc CSV loaders.
REFERENCE_ROW_TEMPLATE = "{test_name}: {normal_range} {unit} ({category}) - {notes}"


class ReferenceDataLoader:
    def __init__(self, data_dir: str | Path | None = None):
        self.data_dir = Path(data_dir) if data_dir is not None else DATA_RAW_DIR

    def _validate_csv_columns(self, reader: csv.DictReader, csv_path: Path) -> bool:
        if reader.fieldnames is None:
            logger.error(f"CSV file has no headers: {csv_path}")
            return False
        missing = REQUIRED_CSV_COLUMNS - set(reader.fieldnames)
        if missing:
            logger.error(f"CSV missing required columns {missing}: {csv_path}")
            return False
        return True

    def load_reference_ranges(self) -> str:
        csv_path = self.data_dir / "LabQAR" / "reference_ranges.csv"
        if not csv_path.exists():
            logger.warning(f"Reference ranges CSV not found: {csv_path}")
            return ""

        lines = []
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            if not self._validate_csv_columns(reader, csv_path):
                return ""
            for row in reader:
                lines.append(REFERENCE_ROW_TEMPLATE.format(**row))

        return "Reference Ranges:\n" + "\n".join(lines)

    def load_reference_ranges_as_docs(self) -> list[dict]:
        csv_path = self.data_dir / "LabQAR" / "reference_ranges.csv"
        if not csv_path.exists():
            logger.warning(f"Reference ranges CSV not found: {csv_path}")
            return []

        docs = []
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            if not self._validate_csv_columns(reader, csv_path):
                return []
            for i, row in enumerate(reader):
                content = REFERENCE_ROW_TEMPLATE.format(**row)
                docs.append(
                    {
                        "id": f"ref_range_{i}",
                        "source": "reference_ranges.csv",
                        "content": content,
                        "source_type": "reference_csv",
                        "source_class": "reference_csv",
                        "metadata": {
                            "logical_name": "Lab reference ranges",
                            "canonical_label": canonical_source_label(
                                "reference_ranges.csv", "Lab reference ranges"
                            ),
                            "source_type": "reference_csv",
                            "source_class": "reference_csv",
                        },
                    }
                )
        return docs

    def load_pdfs_text(self) -> str:
        texts = []
        for pdf_file in self.data_dir.glob("*.pdf"):
            _, page_texts = read_pdf_with_pypdf(pdf_file)
            text = f"\n\n=== {pdf_file.name} ===\n\n"
            text += "".join(page_text + "\n" for page_text in page_texts)
            texts.append(text)
        return "\n".join(texts)
