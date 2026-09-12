"""Hamilton Driver for the medallion data ingestion pipeline.

This module builds and executes the DAG that orchestrates:
- Bronze: raw downloads (web content, PDFs)
- Silver: parsed and validated documents
- Gold: chunked, enriched, and feature-engineered data
- Platinum: embeddings ready for vector storage
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hamilton import driver
from hamilton.execution import executors

from src.ingestion.nodes import NODE_MODULES

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IngestionRunConfig:
    """Execution flags for :func:`run_ingestion` (roadmap P3.2).

    ``from_runtime_state`` derives the feature flags (HyPE / enrichment)
    from the vector-store runtime config — the same source the deleted
    rag-side builder (``_build_index_from_sources``) read — so builds
    triggered from ``rag/index.py`` pick up experiment overrides applied
    via ``apply_runtime_config``.
    """

    project_root: Path
    skip_download: bool = True
    force_rebuild: bool = False
    force_html_convert: bool = False
    enable_hype: bool = False
    enable_keyword_extraction: bool = False
    enable_chunk_summaries: bool = False
    parallel_cores: int = 1
    hype_config: dict[str, Any] | None = None
    enrichment_config: dict[str, Any] | None = None

    @classmethod
    def from_runtime_state(
        cls,
        project_root: str | Path | None = None,
        *,
        force_rebuild: bool = False,
        force_html_convert: bool = False,
    ) -> IngestionRunConfig:
        """Build a config from the current runtime-config overlay."""
        from src.config import PROJECT_ROOT, settings
        from src.ingestion.indexing.factory import get_vector_store_runtime_config

        features = dict(get_vector_store_runtime_config().get("indexing_features", {}) or {})
        return cls(
            project_root=Path(project_root) if project_root is not None else PROJECT_ROOT,
            skip_download=True,
            force_rebuild=force_rebuild,
            force_html_convert=force_html_convert,
            enable_hype=bool(features.get("enable_hype", settings.hype.enabled)),
            enable_keyword_extraction=bool(
                features.get(
                    "enable_keyword_extraction",
                    settings.enrichment.enable_keyword_extraction,
                )
            ),
            enable_chunk_summaries=bool(
                features.get("enable_chunk_summaries", settings.enrichment.enable_chunk_summaries)
            ),
            hype_config={
                "sample_rate": float(features.get("hype_sample_rate", settings.hype.sample_rate)),
                "max_chunks": int(features.get("hype_max_chunks", settings.hype.max_chunks)),
                "questions_per_chunk": int(
                    features.get("hype_questions_per_chunk", settings.hype.questions_per_chunk)
                ),
            },
            enrichment_config={
                "sample_rate": float(
                    features.get(
                        "keyword_extraction_sample_rate",
                        settings.enrichment.keyword_extraction_sample_rate,
                    )
                ),
                "max_chunks": int(
                    features.get(
                        "keyword_extraction_max_chunks",
                        settings.enrichment.keyword_extraction_max_chunks,
                    )
                ),
            },
        )


@dataclass(frozen=True)
class IngestionResult:
    """Outcome of one :func:`run_ingestion` execution.

    ``to_stats`` keeps the exact key set the deleted rag-side builder
    (``_build_index_from_sources``) returned, so downstream consumers of
    ``initialize_vector_store_async`` payloads are unchanged.
    """

    attempted: int
    inserted: int
    skipped_duplicate_content: int
    pdf_document_count: int
    markdown_document_count: int
    reference_document_count: int
    chunk_count: int
    hype_chunk_count: int
    enriched_chunk_count: int
    build_elapsed_ms: int

    def to_stats(self) -> dict[str, Any]:
        return {
            "attempted": self.attempted,
            "inserted": self.inserted,
            "skipped_duplicate_content": self.skipped_duplicate_content,
            "build_elapsed_ms": self.build_elapsed_ms,
            "pdf_document_count": self.pdf_document_count,
            "markdown_document_count": self.markdown_document_count,
            "reference_document_count": self.reference_document_count,
            "chunk_count": self.chunk_count,
            "hype_chunk_count": self.hype_chunk_count,
            "enriched_chunk_count": self.enriched_chunk_count,
        }


# Single-entry driver cache keyed by the run-config signature, mirroring the
# vector-store factory pattern (roadmap P3.2): Hamilton driver construction is
# too heavy to repeat per request-path build, and drivers are safely reusable
# across executes with the same config.
_DRIVER_CACHE: dict[str, Any] = {"signature": None, "driver": None}
_DRIVER_CACHE_LOCK = threading.Lock()


def _freeze_config_value(value: Any) -> Any:
    if isinstance(value, dict):
        return tuple(sorted((key, _freeze_config_value(item)) for key, item in value.items()))
    if isinstance(value, Path):
        return str(value)
    return value


def _config_signature(config: IngestionRunConfig) -> tuple[tuple[str, Any], ...]:
    return tuple(
        sorted(
            {
                "project_root": str(config.project_root),
                "skip_download": config.skip_download,
                "force_rebuild": config.force_rebuild,
                "force_html_convert": config.force_html_convert,
                "enable_hype": config.enable_hype,
                "enable_keyword_extraction": config.enable_keyword_extraction,
                "enable_chunk_summaries": config.enable_chunk_summaries,
                "parallel_cores": config.parallel_cores,
                "hype_config": _freeze_config_value(config.hype_config),
                "enrichment_config": _freeze_config_value(config.enrichment_config),
            }.items()
        )
    )


def _get_cached_driver(config: IngestionRunConfig) -> driver.Driver:
    signature = _config_signature(config)
    with _DRIVER_CACHE_LOCK:
        if _DRIVER_CACHE["driver"] is None or _DRIVER_CACHE["signature"] != signature:
            _DRIVER_CACHE["driver"] = build_ingestion_pipeline(
                project_root=config.project_root,
                enable_hype=config.enable_hype,
                enable_keyword_extraction=config.enable_keyword_extraction,
                enable_chunk_summaries=config.enable_chunk_summaries,
                force_rebuild=config.force_rebuild,
                force_html_convert=config.force_html_convert,
                skip_download=config.skip_download,
                parallel_cores=config.parallel_cores,
                hype_config=config.hype_config,
                enrichment_config=config.enrichment_config,
            )
            _DRIVER_CACHE["signature"] = signature
        return _DRIVER_CACHE["driver"]


def run_ingestion(config: IngestionRunConfig) -> IngestionResult:
    """Run the ingestion DAG end-to-end and index into the vector store.

    The single library entry for ingestion (roadmap P3.2): server-start and
    eval builds delegate here from ``rag/index.py``; the CLI wraps it. Also
    writes the medallion parquet artifacts (silver documents, gold/enriched
    chunks, reference data) as a side effect of the DAG.
    """
    start = time.time()
    dr = _get_cached_driver(config)
    final_vars = [
        "write_silver_documents",
        "write_gold_chunks",
        "write_reference_data",
        "write_enriched_chunks",
        "hype_questions",
        "embed_chunks",
    ]
    results = dict(dr.execute(final_vars=final_vars))

    embed_stats = (results.get("embed_chunks") or [{}])[0]
    silver = results.get("write_silver_documents", {})
    gold = results.get("write_gold_chunks", {})
    reference = results.get("write_reference_data", {})
    enriched = results.get("write_enriched_chunks", {})
    result = IngestionResult(
        attempted=int(embed_stats.get("attempted", 0)),
        inserted=int(embed_stats.get("inserted", 0)),
        skipped_duplicate_content=int(embed_stats.get("skipped_duplicate_content", 0)),
        pdf_document_count=int(silver.get("pdf_count", 0)),
        markdown_document_count=int(silver.get("markdown_count", 0)),
        reference_document_count=int(reference.get("reference_count", 0)),
        chunk_count=int(gold.get("chunk_count", 0)),
        hype_chunk_count=len(results.get("hype_questions", {})),
        enriched_chunk_count=int(enriched.get("enriched_count", 0)),
        build_elapsed_ms=int((time.time() - start) * 1000),
    )
    logger.info(
        "Ingestion complete (attempted=%d, inserted=%d, duplicate_content=%d, chunks=%d) in %dms",
        result.attempted,
        result.inserted,
        result.skipped_duplicate_content,
        result.chunk_count,
        result.build_elapsed_ms,
    )
    return result


def build_ingestion_pipeline(
    project_root: str | Path,
    enable_hype: bool = False,
    enable_keyword_extraction: bool = False,
    enable_chunk_summaries: bool = False,
    force_rebuild: bool = False,
    force_html_convert: bool = False,
    skip_download: bool = False,
    parallel_cores: int = 1,
    hype_config: dict[str, Any] | None = None,
    enrichment_config: dict[str, Any] | None = None,
) -> driver.Driver:
    """Build the ingestion pipeline Hamilton driver.

    Args:
        project_root: Root directory of the project.
        enable_hype: Enable HyPE question generation.
        enable_keyword_extraction: Enable keyword extraction.
        enable_chunk_summaries: Enable chunk summarization.
        force_rebuild: Force rebuild of vector store.
        force_html_convert: Force re-conversion of HTML to Markdown.
        skip_download: Skip download/conversion side effects (reuse raw corpus).
        parallel_cores: Number of cores for parallel execution.
        hype_config: Config for HyPE question generation.
        enrichment_config: Config for keyword/summary enrichment.
    """
    from src.config import settings

    modules = NODE_MODULES

    resolved_hype_config = hype_config or {
        "sample_rate": settings.hype.sample_rate,
        "max_chunks": settings.hype.max_chunks,
        "questions_per_chunk": settings.hype.questions_per_chunk,
    }
    resolved_enrichment_config = enrichment_config or {
        "sample_rate": settings.enrichment.keyword_extraction_sample_rate,
        "max_chunks": settings.enrichment.keyword_extraction_max_chunks,
    }

    resolved_project_root = project_root if isinstance(project_root, Path) else Path(project_root)

    config = {
        "project_root": resolved_project_root,
        "enable_hype": enable_hype,
        "enable_keyword_extraction": enable_keyword_extraction,
        "enable_chunk_summaries": enable_chunk_summaries,
        "force_rebuild": force_rebuild,
        "force_html_convert": force_html_convert,
        "skip_download": skip_download,
        "hype_config": resolved_hype_config,
        "enrichment_config": resolved_enrichment_config,
    }

    builder = driver.Builder().with_modules(*modules).with_config(config)

    if parallel_cores > 1:
        builder = builder.enable_dynamic_execution(
            allow_experimental_mode=True
        ).with_remote_executor(executors.MultiProcessingExecutor(max_tasks=parallel_cores))

    return builder.build()


def execute_pipeline(
    dr: driver.Driver,
    final_vars: list[str] | None = None,
) -> dict[str, Any]:
    """Execute the pipeline and return results.

    Args:
        dr: The Hamilton driver.
        final_vars: List of final variables to retrieve. If None, returns all.

    Returns:
        Dictionary of results keyed by variable name.
    """
    if final_vars is None:
        final_vars = [
            "write_gold_chunks",
            "write_enriched_chunks",
            "embed_chunks",
        ]

    results = dr.execute(final_vars=final_vars)
    return dict(results)


# Hand-maintained visualization edges. Kept in check by
# tests/unit/test_ingestion_dag.py::test_visualize_edges_match_real_dag,
# which asserts every edge below is a real DAG dependency.
_VISUALIZE_EDGES = [
    ("download_web_content", "convert_html_to_markdown"),
    ("convert_html_to_markdown", "all_markdown_documents"),
    ("download_pdf_files", "all_pdf_documents"),
    ("all_pdf_documents", "write_silver_documents"),
    ("all_markdown_documents", "write_silver_documents"),
    ("write_silver_documents", "pdf_chunks"),
    ("write_silver_documents", "markdown_chunks"),
    ("pdf_chunks", "all_chunks"),
    ("markdown_chunks", "all_chunks"),
    ("all_chunks", "write_gold_chunks"),
    ("all_chunks", "hype_questions"),
    ("all_chunks", "enrichment_results"),
    ("all_chunks", "enriched_chunks"),
    ("hype_questions", "enriched_chunks"),
    ("enrichment_results", "enriched_chunks"),
    ("enriched_chunks", "write_enriched_chunks"),
    ("enriched_chunks", "embed_chunks"),
    ("reference_chunks", "write_reference_data"),
    ("reference_chunks", "embed_chunks"),
    ("embed_chunks", "write_embedding_stats"),
]


def visualize_pipeline(
    dr: driver.Driver,
    output_path: str | Path = "dag.png",
    final_vars: list[str] | None = None,
) -> None:
    """Visualize the pipeline DAG.

    Args:
        dr: The Hamilton driver.
        output_path: Path to save the visualization.
        final_vars: Variables to include in visualization.
    """
    import graphviz

    dot = graphviz.Digraph(comment="RAG Ingestion Pipeline DAG")
    dot.attr(rankdir="TB")

    with dot.subgraph(name="cluster_bronze") as bronze:
        bronze.attr(label="Bronze (Download)", style="dashed", color="gray")
        bronze.node("download_web_content")
        bronze.node("convert_html_to_markdown")
        bronze.node("download_pdf_files")

    with dot.subgraph(name="cluster_silver") as silver:
        silver.attr(label="Silver (Parse)", style="dashed", color="gray")
        silver.node("all_pdf_documents")
        silver.node("all_markdown_documents")
        silver.node("write_silver_documents")

    with dot.subgraph(name="cluster_gold") as gold:
        gold.attr(label="Gold (Chunk & Enrich)", style="dashed", color="gray")
        gold.node("pdf_chunks")
        gold.node("markdown_chunks")
        gold.node("all_chunks")
        gold.node("write_gold_chunks")
        gold.node("hype_questions")
        gold.node("enrichment_results")
        gold.node("enriched_chunks")
        gold.node("write_enriched_chunks")

    with dot.subgraph(name="cluster_reference") as ref:
        ref.attr(label="Reference Data", style="dashed", color="gray")
        ref.node("reference_chunks")
        ref.node("write_reference_data")

    with dot.subgraph(name="cluster_platinum") as platinum:
        platinum.attr(label="Platinum (Embed)", style="dashed", color="gray")
        platinum.node("embed_chunks")
        platinum.node("write_embedding_stats")

    for src, dst in _VISUALIZE_EDGES:
        dot.edge(src, dst)

    output_path = Path(output_path)
    output_str = str(output_path.with_suffix(""))
    dot.render(output_str, format="png", cleanup=True)
    logger.info("DAG visualization saved to %s", output_path)
