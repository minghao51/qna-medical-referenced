"""Validate that the Hamilton ingestion DAG fully resolves without executing.

These tests build the real driver from the component modules and use
``Driver.validate_execution`` to statically prove that every node in the
pipeline has producers for all of its dependencies. They must run in CI
without API keys or network access: nothing is executed, only the graph
is validated (broken wiring raises ``ValueError``).
"""

import pytest

from src.ingestion.pipeline import _VISUALIZE_EDGES, build_ingestion_pipeline

FINAL_VARS = [
    "write_gold_chunks",
    "write_enriched_chunks",
    "embed_chunks",
    "write_reference_data",
]


@pytest.fixture(scope="module")
def dag_driver(tmp_path_factory: pytest.TempPathFactory):
    return build_ingestion_pipeline(project_root=tmp_path_factory.mktemp("dag_project"))


def test_dag_validates_all_final_vars_together(dag_driver):
    """The whole pipeline must resolve end-to-end (every input has a producer)."""
    dag_driver.validate_execution(final_vars=FINAL_VARS)


@pytest.mark.parametrize("final_var", FINAL_VARS)
def test_dag_validates_each_final_var(dag_driver, final_var):
    """Each terminal node must resolve individually."""
    dag_driver.validate_execution(final_vars=[final_var])


def test_dag_validates_bronze_download_nodes(dag_driver):
    dag_driver.validate_execution(
        final_vars=["download_web_content", "convert_html_to_markdown", "download_pdf_files"]
    )


def test_dag_validates_parallel_driver(tmp_path):
    """The parallel (multi-processing) driver variant must resolve too."""
    dr = build_ingestion_pipeline(project_root=tmp_path, parallel_cores=2)
    dr.validate_execution(final_vars=FINAL_VARS)


def test_visualize_edges_match_real_dag(dag_driver):
    """Every hand-maintained visualization edge must be a real DAG dependency.

    Guards against edge drift in ``visualize_pipeline``: if a node is renamed
    or re-wired, this fails until the visualization (and any docs built on it)
    is updated.
    """
    nodes = {v.name: v for v in dag_driver.list_available_variables()}
    for src, dst in _VISUALIZE_EDGES:
        assert src in nodes, f"visualization references unknown node {src!r}"
        assert dst in nodes, f"visualization references unknown node {dst!r}"
        assert src in nodes[dst].required_dependencies, (
            f"visualization edge {src!r} -> {dst!r} is not a real DAG dependency"
        )


def test_dag_edges_are_consistent_with_silver_handoff(dag_driver):
    """The silver→gold handoff must be a real edge, not a filesystem side effect.

    ``pdf_chunks``/``markdown_chunks`` read parquets written by
    ``write_silver_documents``; without a DAG edge between them, executing
    gold-or-later nodes would silently chunk stale (or missing) silver data.
    """
    nodes = {v.name: v for v in dag_driver.list_available_variables()}
    for chunker in ("pdf_chunks", "markdown_chunks"):
        assert "write_silver_documents" in nodes[chunker].required_dependencies
