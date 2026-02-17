import csv
import logging
from pathlib import Path
from typing import List

from src.ingest import get_documents
from src.processors import chunk_documents
from src.vectorstore import get_vector_store

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


_vector_store_initialized = False


def initialize_vector_store(rebuild: bool = True):
    global _vector_store_initialized
    
    vector_store = get_vector_store()
    
    if rebuild:
        vector_store.clear()
        _vector_store_initialized = False

    if _vector_store_initialized:
        return

    loader = ReferenceDataLoader()

    pdf_docs = get_documents()

    chunked_docs = chunk_documents(pdf_docs)

    ref_docs = loader.load_reference_ranges_as_docs()
    chunked_docs.extend(ref_docs)

    vector_store.add_documents(chunked_docs)

    _vector_store_initialized = True
    print(f"Indexed {len(chunked_docs)} document chunks")


def retrieve_context(query: str, top_k: int = 5):
    initialize_vector_store()

    vector_store = get_vector_store()
    results = vector_store.similarity_search(query, top_k=top_k)

    context_parts = []
    sources = []
    for r in results:
        page_info = f" page {r.get('page', 'N/A')}" if r.get('page') else ""
        source_name = f"{r['source']}{page_info}"
        sources.append(source_name)
        context_parts.append(f"[Source: {source_name}]\n{r['content']}")

    return "\n\n".join(context_parts), sources


def get_full_context() -> str:
    loader = ReferenceDataLoader()
    ranges = loader.load_reference_ranges()
    pdf_texts = loader.load_pdfs_text()
    return f"{ranges}\n\n{pdf_texts}"


def get_context(query: str | None = None) -> tuple[str, list[str]]:
    if query:
        return retrieve_context(query)
    return get_full_context(), []
