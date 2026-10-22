"""Run real initialization and Hamilton enrichment with synthetic I/O leaves."""

from copy import deepcopy
from itertools import product
from types import SimpleNamespace

import polars as pl
import pytest

from src.config import context, settings
from src.ingestion import pipeline
from src.ingestion.indexing import factory
from src.ingestion.nodes import download
from src.ingestion.pipeline import IngestionRunConfig
from src.rag import index
from src.usecases.runtime_config import get_runtime_config_view


@pytest.fixture
def ingestion_leaves(monkeypatch, tmp_path):
    import src.config as config

    monkeypatch.setattr(context, "_state", context.RuntimeState())
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(download, "DATA_RAW_DIR", tmp_path / "raw")
    monkeypatch.setattr(pipeline, "_DRIVER_CACHE", {"signature": None, "driver": None})
    cache = factory.ChromaVectorStoreFactory
    monkeypatch.setattr(cache, "_instance", None)
    monkeypatch.setattr(cache, "_runtime_config", {})
    monkeypatch.setattr(cache, "_runtime_signature_value", None)
    calls = SimpleNamespace(hype=[], enrichment=[], clients=0, stored=[])
    chunks = [
        {
            "id": f"synthetic-{i}",
            "content": f"Synthetic reference evidence {i}.",
            "source": "synthetic.md",
            "quality_score": 1.0,
            "metadata": {"source_type": "markdown"},
        }
        for i in range(2)
    ]

    class Store:
        def __init__(self, **kwargs):
            assert "indexing_features" not in kwargs
            self.documents = {"contents": [], "index_metadata": kwargs.get("index_metadata", {})}
            self.last_indexing_stats = {}

        def add_documents(self, documents):
            calls.stored = deepcopy(documents)
            self.documents["contents"] = [doc["content"] for doc in documents]
            self.last_indexing_stats = {
                "attempted": len(documents),
                "inserted": len(documents),
                "skipped_duplicate_content": 0,
            }
            return self.last_indexing_stats

    class Client:
        def generate(self, prompt, context=""):
            assert context == ""
            if "question(s)" in prompt:
                calls.hype.append(prompt)
                return (
                    "What does the synthetic reference say?\nHow is synthetic evidence organized?"
                )
            calls.enrichment.append(prompt)
            return '{"keywords": ["synthetic"], "summary": "Synthetic summary."}'

    def get_client():
        calls.clients += 1
        return Client()

    monkeypatch.setattr(factory, "ChromaVectorStore", Store)
    monkeypatch.setattr("src.infra.llm.qwen_client.get_client", get_client)
    monkeypatch.setattr(
        "src.ingestion.steps.load_markdown.get_markdown_documents",
        lambda: [{"id": "doc", "content": "Synthetic document", "source": "synthetic.md"}],
    )
    monkeypatch.setattr(
        "src.ingestion.steps.chunking.chunk_documents", lambda docs: deepcopy(chunks)
    )
    monkeypatch.setattr(
        "src.ingestion.steps.load_reference_data.ReferenceDataLoader.load_reference_ranges_as_docs",
        lambda self: [],
    )
    return calls


@pytest.mark.parametrize(("hype", "keywords", "summaries"), list(product([False, True], repeat=3)))
@pytest.mark.asyncio
async def test_experiment_flags_reach_real_dag_and_side_effects(
    monkeypatch, tmp_path, ingestion_leaves, hype, keywords, summaries
):
    # Opposite static defaults make silent fallback detectable in both directions.
    monkeypatch.setattr(settings.hype, "enabled", not hype)
    monkeypatch.setattr(settings.enrichment, "enable_keyword_extraction", not keywords)
    monkeypatch.setattr(settings.enrichment, "enable_chunk_summaries", not summaries)
    features = {
        "enable_hype": hype,
        "enable_keyword_extraction": keywords,
        "enable_chunk_summaries": summaries,
        "hype_sample_rate": 1.0,
        "hype_max_chunks": 1,
        "hype_questions_per_chunk": 1,
        "keyword_extraction_sample_rate": 1.0,
        "keyword_extraction_max_chunks": 1,
    }
    index.configure_runtime_for_experiment({"ingestion": features})
    config = IngestionRunConfig.from_runtime_state()
    assert config.project_root == tmp_path
    assert config.enable_hype is hype
    assert config.enable_keyword_extraction is keywords
    assert config.enable_chunk_summaries is summaries
    assert config.hype_config == {"sample_rate": 1.0, "max_chunks": 1, "questions_per_chunk": 1}
    assert config.enrichment_config == {"sample_rate": 1.0, "max_chunks": 1}
    assert "indexing_features" not in factory.get_vector_store_runtime_config()

    result = await index.initialize_runtime_index_async()
    calls = ingestion_leaves
    assert result["status"] == "built"
    assert result["indexing_stats"]["inserted"] == 2
    assert result["indexing_stats"]["hype_chunk_count"] == int(hype)
    assert len(calls.hype) == int(hype)
    assert len(calls.enrichment) == int(keywords or summaries)
    assert calls.clients == int(hype) + int(keywords or summaries)
    assert all("generate 1 question(s)" in prompt for prompt in calls.hype)
    metadata = [doc["metadata"] for doc in calls.stored]
    assert sum(bool(row.get("hypothetical_questions")) for row in metadata) == int(hype)
    assert sum(bool(row.get("extracted_keywords")) for row in metadata) == int(keywords)
    assert sum(bool(row.get("chunk_summary")) for row in metadata) == int(summaries)
    assert all(len(row.get("hypothetical_questions", [])) <= 1 for row in metadata)
    parquet = tmp_path / "data/03_gold/chunks/enriched_chunks.parquet"
    assert pl.read_parquet(parquet).height == 2
    view = get_runtime_config_view()
    assert view["enrichment"]["enable_keyword_extraction"] is keywords
    assert view["enrichment"]["enable_chunk_summaries"] is summaries
    # Summaries are attached as metadata; this fake storage leaf does not format embeddings.

    # A ready index must not silently regenerate optional features.
    reused = await index.initialize_runtime_index_async()
    assert reused["reused_existing_index"] is True
    assert len(calls.hype) == int(hype)
    assert len(calls.enrichment) == int(keywords or summaries)
    assert context.get_runtime_state().vector_store_initialized is True


@pytest.mark.asyncio
async def test_zero_sampling_does_not_generate(ingestion_leaves):
    index.configure_runtime_for_experiment(
        {
            "ingestion": {
                "enable_hype": True,
                "enable_keyword_extraction": True,
                "enable_chunk_summaries": True,
                "hype_sample_rate": 0.0,
                "keyword_extraction_sample_rate": 0.0,
            }
        }
    )
    result = await index.initialize_runtime_index_async()
    assert result["indexing_stats"]["inserted"] == 2
    assert ingestion_leaves.hype == []
    assert ingestion_leaves.enrichment == []
    assert all(not doc["metadata"].get("chunk_summary") for doc in ingestion_leaves.stored)


@pytest.mark.asyncio
async def test_ready_index_does_not_generate_just_because_flags_are_selected(
    ingestion_leaves, tmp_path
):
    index.configure_runtime_for_experiment(
        {
            "ingestion": {
                "enable_hype": True,
                "enable_keyword_extraction": True,
                "enable_chunk_summaries": True,
            }
        }
    )
    store = factory.get_vector_store()
    store.documents["contents"] = ["existing synthetic evidence"]
    result = await index.initialize_runtime_index_async()
    assert result["reused_existing_index"] is True
    assert ingestion_leaves.clients == 0
    assert ingestion_leaves.hype == []
    assert ingestion_leaves.enrichment == []
    assert not (tmp_path / "data/03_gold").exists()
    view = get_runtime_config_view()
    assert view["enrichment"]["configuration_scope"] == "next_build"
    assert view["enrichment"]["enable_chunk_summaries"] is True
