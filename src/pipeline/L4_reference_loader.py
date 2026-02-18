#!/usr/bin/env python3
"""
L4: Reference Data Loader - Load CSV reference ranges data.
"""

import csv
import logging
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

REQUIRED_CSV_COLUMNS = {"test_name", "normal_range", "unit", "category", "notes"}


class ReferenceDataLoader:
    def __init__(self, data_dir: str = "data/raw"):
        self.data_dir = Path(data_dir)

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
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            if not self._validate_csv_columns(reader, csv_path):
                return ""
            for row in reader:
                line = f"{row['test_name']}: {row['normal_range']} {row['unit']} ({row['category']}) - {row['notes']}"
                lines.append(line)

        return "Reference Ranges:\n" + "\n".join(lines)

    def load_reference_ranges_as_docs(self) -> List[dict]:
        csv_path = self.data_dir / "LabQAR" / "reference_ranges.csv"
        if not csv_path.exists():
            logger.warning(f"Reference ranges CSV not found: {csv_path}")
            return []

        docs = []
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            if not self._validate_csv_columns(reader, csv_path):
                return []
            for i, row in enumerate(reader):
                content = f"{row['test_name']}: {row['normal_range']} {row['unit']} ({row['category']}) - {row['notes']}"
                docs.append({
                    "id": f"ref_range_{i}",
                    "source": "reference_ranges.csv",
                    "content": content
                })
        return docs

    def load_pdfs_text(self) -> str:
        from pypdf import PdfReader
        texts = []
        for pdf_file in self.data_dir.glob("*.pdf"):
            reader = PdfReader(str(pdf_file))
            text = f"\n\n=== {pdf_file.name} ===\n\n"
            for page in reader.pages:
                text += page.extract_text() + "\n"
            texts.append(text)
        return "\n".join(texts)
