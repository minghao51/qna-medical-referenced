import json

from src.config.context import reset_runtime_state
from src.ingestion.indexing.chroma_store import (
    get_vector_store_runtime_config,
    set_vector_store_runtime_config,
)
from src.rag.runtime_config import (
    apply_runtime_config,
    build_default_runtime_config,
    build_experiment_runtime_config,
)


def teardown_function():
    reset_runtime_state()
    set_vector_store_runtime_config(None)


def test_build_default_runtime_config_applies_expected_flags():
    runtime_config = build_default_runtime_config(
        disable_page_classification=True,
        disable_structured_chunking=True,
    )

    assert runtime_config.html.page_classification_enabled is False
    assert runtime_config.html.extractor_mode == "auto"
    assert runtime_config.chunking.index_only_classified_pages is False
    assert runtime_config.chunking.structured_chunking_enabled is False
    assert runtime_config.vector_store is None


def test_build_experiment_runtime_config_resolves_source_configs_and_vector_store_metadata():
    experiment = {
        "metadata": {"name": "test-exp"},
        "experiment_file": "experiments/test.yaml",
        "experiment_config_hash": "exp-hash",
        "index_config_hash": "idx-hash",
        "ingestion": {
            "page_classification_enabled": False,
            "index_only_classified_pages": False,
            "html_extractor_mode": "fallback_only",
            "html_extractor_strategy": "readability_bs",
            "pdf_extractor_strategy": "pymupdf_pdfplumber",
            "pdf_table_extractor": "camelot",
            "structured_chunking_enabled": True,
            "source_chunk_configs": {"pdf": {"chunk_size": 1024}},
            "auto_select_chunk_strategy": True,
            "enable_hype": True,
            "hype_sample_rate": 0.25,
        },
        "embedding_index": {
            "collection_name": "experiment_docs",
            "semantic_weight": 0.5,
            "keyword_weight": 0.3,
            "boost_weight": 0.2,
            "embedding_model": "custom-embedding",
            "embedding_batch_size": 32,
        },
    }

    runtime_config = build_experiment_runtime_config(experiment)

    assert runtime_config.html.extractor_strategy == "readability_bs"
    assert runtime_config.pdf.table_extractor == "camelot"
    assert runtime_config.chunking.auto_select_strategy is True
    assert runtime_config.vector_store is not None
    assert runtime_config.vector_store.collection_name == "experiment_docs"
    assert runtime_config.vector_store.indexing_features["enable_hype"] is True
    resolved_configs = json.loads(
        runtime_config.vector_store.index_metadata["source_chunk_configs"]
    )
    assert resolved_configs["pdf"]["chunk_size"] == 1024
    assert resolved_configs["pdf"]["strategy"] == "chonkie_semantic"


def test_apply_runtime_config_updates_runtime_state_and_vector_store_config():
    runtime_config = build_experiment_runtime_config(
        {
            "metadata": {"name": "apply-test"},
            "ingestion": {
                "page_classification_enabled": False,
                "index_only_classified_pages": False,
                "html_extractor_mode": "fallback_only",
                "html_extractor_strategy": "readability_bs",
                "pdf_extractor_strategy": "pymupdf_pdfplumber",
                "pdf_table_extractor": "camelot",
                "structured_chunking_enabled": False,
                "source_chunk_configs": {"markdown": {"chunk_size": 900}},
                "auto_select_chunk_strategy": False,
            },
            "embedding_index": {"collection_name": "apply_docs"},
        }
    )

    apply_runtime_config(runtime_config)
    vector_store_config = get_vector_store_runtime_config()

    assert vector_store_config["collection_name"] == "apply_docs"

    from src.config.context import get_runtime_state

    state = get_runtime_state()
    assert state.page_classification_enabled is False
    assert state.index_only_classified_pages is False
    assert state.html_extractor_mode == "fallback_only"
    assert state.html_extractor_strategy == "readability_bs"
    assert state.pdf_extractor_strategy == "pymupdf_pdfplumber"
    assert state.pdf_table_extractor == "camelot"
    assert state.structured_chunking_enabled is False
    assert state.source_chunk_configs_override == {"markdown": {"chunk_size": 900}}
