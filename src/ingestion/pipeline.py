"""Hamilton Driver for the medallion data ingestion pipeline.

This module builds and executes the DAG that orchestrates:
- Bronze: raw downloads (web content, PDFs)
- Silver: parsed and validated documents
- Gold: chunked, enriched, and feature-engineered data
- Platinum: embeddings ready for vector storage
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hamilton import driver
from hamilton.execution import executors

from src.ingestion.components import _modules


def build_ingestion_pipeline(
    project_root: str | Path,
    llm_provider: str = "qwen",
    enable_hype: bool = False,
    enable_keyword_extraction: bool = False,
    enable_chunk_summaries: bool = False,
    force_rebuild: bool = False,
    parallel_cores: int = 1,
) -> driver.Driver:
    """Build the ingestion pipeline Hamilton driver.

    Args:
        project_root: Root directory of the project.
        llm_provider: LLM provider for enrichment tasks ("qwen" or "litellm").
        enable_hype: Enable HyPE question generation.
        enable_keyword_extraction: Enable keyword extraction.
        enable_chunk_summaries: Enable chunk summarization.
        force_rebuild: Force rebuild of vector store.
        parallel_cores: Number of cores for parallel execution.
    """
    modules = _modules

    config = {
        "project_root": project_root if isinstance(project_root, Path) else Path(project_root),
        "llm_provider": llm_provider,
        "enable_hype": enable_hype,
        "enable_keyword_extraction": enable_keyword_extraction,
        "enable_chunk_summaries": enable_chunk_summaries,
        "force_rebuild": force_rebuild,
        "hype_config": {
            "sample_rate": 0.1,
            "max_chunks": 500,
            "questions_per_chunk": 2,
        },
        "enrichment_config": {
            "sample_rate": 1.0,
            "max_chunks": 500,
        },
        "embedding_config": {
            "model_name": "text-embedding-v4",
            "batch_size": 10,
        },
    }

    resolved_project_root = config["project_root"]

    dr = (
        driver.Builder()
        .with_modules(*modules)
        .with_config(config)
        .with_cache(path=str(resolved_project_root / ".cache" / "hamilton"))
        .build()
    )

    if parallel_cores > 1:
        dr = (
            driver.Builder()
            .with_modules(*modules)
            .with_config(config)
            .with_cache(path=str(resolved_project_root / ".cache" / "hamilton"))
            .enable_dynamic_execution(allow_experimental_mode=True)
            .with_remote_executor(
                executors.MultiProcessingExecutor(max_tasks=parallel_cores)
            )
            .build()
        )

    return dr


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
    return results


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
        bronze.node("download_pdf_files")

    with dot.subgraph(name="cluster_silver") as silver:
        silver.attr(label="Silver (Parse)", style="dashed", color="gray")
        silver.node("all_pdf_documents")
        silver.node("all_markdown_documents")
        silver.node("write_silver_documents")

    with dot.subgraph(name="cluster_gold") as gold:
        gold.attr(label="Gold (Chunk & Enrich)", style="dashed", color="gray")
        gold.node("chunk_silver_documents")
        gold.node("all_chunks")
        gold.node("write_gold_chunks")
        gold.node("generate_hype_for_chunks")
        gold.node("apply_hype_questions")
        gold.node("extract_keywords_for_chunks")
        gold.node("apply_keyword_extractions")
        gold.node("generate_summaries_for_chunks")
        gold.node("apply_summaries")
        gold.node("write_enriched_chunks")

    with dot.subgraph(name="cluster_reference") as ref:
        ref.attr(label="Reference Data", style="dashed", color="gray")
        ref.node("load_reference_data")
        ref.node("write_reference_data")

    with dot.subgraph(name="cluster_platinum") as platinum:
        platinum.attr(label="Platinum (Embed)", style="dashed", color="gray")
        platinum.node("embed_chunks")
        platinum.node("write_embedding_stats")

    edges = [
        ("download_web_content", "all_markdown_documents"),
        ("download_pdf_files", "all_pdf_documents"),
        ("all_pdf_documents", "write_silver_documents"),
        ("all_markdown_documents", "write_silver_documents"),
        ("write_silver_documents", "chunk_silver_documents"),
        ("chunk_silver_documents", "all_chunks"),
        ("all_chunks", "write_gold_chunks"),
        ("all_chunks", "generate_hype_for_chunks"),
        ("generate_hype_for_chunks", "apply_hype_questions"),
        ("apply_hype_questions", "write_enriched_chunks"),
        ("all_chunks", "extract_keywords_for_chunks"),
        ("extract_keywords_for_chunks", "apply_keyword_extractions"),
        ("apply_keyword_extractions", "write_enriched_chunks"),
        ("all_chunks", "generate_summaries_for_chunks"),
        ("generate_summaries_for_chunks", "apply_summaries"),
        ("apply_summaries", "write_enriched_chunks"),
        ("write_enriched_chunks", "embed_chunks"),
        ("load_reference_data", "write_reference_data"),
        ("write_reference_data", "embed_chunks"),
        ("write_gold_chunks", "embed_chunks"),
        ("embed_chunks", "write_embedding_stats"),
    ]

    for src, dst in edges:
        dot.edge(src, dst)

    output_path = Path(output_path)
    output_str = str(output_path.with_suffix(""))
    dot.render(output_str, format="png", cleanup=True)
    print(f"DAG visualization saved to {output_path}")
