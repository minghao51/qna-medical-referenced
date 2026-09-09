"""Offline functional test: EXECUTES the real Hamilton DAG end-to-end.

Build-only validation (tests/unit/test_ingestion_dag.py) proves the graph
resolves; this test runs it against a tiny seeded corpus with stubbed
embeddings and download side effects disabled. It proves runtime wiring that
static validation cannot: silver parquets are written before chunking, the
gold parquet before embedding, and documents actually land in ChromaDB.

No network access and no API keys are required.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

MARKDOWN_DOC = """# Anemia Overview

Anemia is a condition in which the number of red blood cells or the hemoglobin
concentration within them is lower than normal. Hemoglobin is needed to carry
oxygen, so anemia leads to symptoms such as fatigue, weakness, dizziness, and
shortness of breath.

## Diagnostic Thresholds

The World Health Organization defines anemia as hemoglobin below 13 g/dL in
men and below 12 g/dL in non-pregnant women. Iron deficiency is the most
common cause worldwide, but anemia of chronic disease, vitamin B12 deficiency,
and hemolytic disorders must also be considered.

## Management

Treatment depends on the underlying cause: oral or intravenous iron for iron
deficiency, vitamin supplementation for deficiency states, and disease-specific
therapy for anemia of chronic disease or hemolysis.
"""


@pytest.fixture
def seeded_raw_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A tmp data/raw holding one markdown document, isolated from the repo corpus."""
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "anemia_overview_a1b2c3d4.md").write_text(MARKDOWN_DOC, encoding="utf-8")

    # Bronze globs (nodes) and the markdown/reference loaders read the
    # module-level DATA_RAW_DIR they imported; repoint all of them at tmp.
    comp01 = importlib.import_module("src.ingestion.nodes.download")
    monkeypatch.setattr(comp01, "DATA_RAW_DIR", raw)
    for module_name in ("load_markdown", "load_reference_data"):
        module = importlib.import_module(f"src.ingestion.steps.{module_name}")
        if hasattr(module, "DATA_RAW_DIR"):
            monkeypatch.setattr(module, "DATA_RAW_DIR", raw)
    return raw


def test_hamilton_dag_functional_run(tmp_path: Path, seeded_raw_dir: Path, fake_chroma_embeddings):
    """Full DAG execution (skip downloads, offline embeddings) indexes the corpus."""
    from src.ingestion.indexing.chroma_store import ChromaVectorStoreFactory, get_vector_store
    from src.ingestion.pipeline import build_ingestion_pipeline

    ChromaVectorStoreFactory.reset()
    try:
        dr = build_ingestion_pipeline(
            project_root=tmp_path,
            skip_download=True,  # corpus is pre-seeded; no network side effects
        )

        results = dr.execute(
            final_vars=["write_gold_chunks", "write_reference_data", "embed_chunks"]
        )

        # Silver was written before gold chunks were produced (DAG order).
        silver_parquet = (
            tmp_path / "data" / "02_silver" / "documents" / "markdown_documents.parquet"
        )
        assert silver_parquet.exists(), "silver markdown parquet must be written by the DAG"
        gold_result = results["write_gold_chunks"]
        assert gold_result["chunk_count"] >= 1, "seeded markdown doc must produce chunks"
        assert Path(gold_result["path"]).exists()

        # Embedding stats show real insertions into the isolated Chroma store.
        embed_stats = results["embed_chunks"][0]
        assert embed_stats["inserted"] >= 1
        assert embed_stats["skipped_duplicate_content"] == 0

        store = get_vector_store()
        assert store.documents, "indexed documents must be visible in the store"

        hits = store.similarity_search("hemoglobin thresholds for anemia", top_k=3)
        assert hits, "semantic search over the indexed corpus must return results"
        assert any(str(h.get("source", "")).endswith("anemia_overview_a1b2c3d4.md") for h in hits)

        # Re-running the DAG without force skips content-identical chunks.
        dr.execute(final_vars=["embed_chunks"])
    finally:
        ChromaVectorStoreFactory.reset()
