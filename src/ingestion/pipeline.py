"""Hamilton Driver for the medallion data ingestion pipeline.

This module builds and executes the DAG that orchestrates:
- Bronze: raw downloads (web content, PDFs)
- Silver: parsed and validated documents
- Gold: chunked, enriched, and feature-engineered data
- Platinum: embeddings ready for vector storage
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from hamilton import driver
from hamilton.execution import executors

from src.ingestion.components import _modules

logger = logging.getLogger(__name__)


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

    modules = _modules

    resolved_hype_config = hype_config or {
        "sample_rate": settings.hyde.hype_sample_rate,
        "max_chunks": settings.hyde.hype_max_chunks,
        "questions_per_chunk": settings.hyde.hype_questions_per_chunk,
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
