"""Evaluation assessment orchestration."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, cast

logger = logging.getLogger(__name__)

from src.config import settings
from src.config.paths import DATA_RAW_DIR
from src.evals.artifacts import (
    ArtifactStore,
    build_run_identity,
    find_reusable_run,
    update_run_index,
    write_latest_pointer,
)
from src.evals.dataset_builder import build_retrieval_dataset
from src.evals.schemas import AssessmentConfig, AssessmentResult
from src.experiments.wandb_tracking import log_assessment_to_wandb
from src.rag.runtime import configure_runtime_for_experiment, initialize_runtime_index

from .answer_eval import evaluate_answer_quality
from .l6_contract import (
    L6_ANSWER_QUALITY_METRICS,
    L6_ANSWER_QUALITY_ROWS,
    SUMMARY_L6_ENABLED_KEY,
    SUMMARY_L6_METRICS_KEY,
    SUMMARY_L6_STATUS_KEY,
)
from .reporting import git_head, render_summary, sha256_file
from .retrieval_eval import (
    evaluate_retrieval,
    run_diversity_sweep,
    run_hype_ablations,
    run_hype_ablations_with_reingest,
    run_keyword_ablations,
    run_keyword_ablations_with_reingest,
    run_reranking_ablations,
    run_retrieval_ablations,
)
from .thresholds import DEFAULT_THRESHOLDS, evaluate_thresholds

__all__ = ["evaluate_answer_quality", "run_assessment"]


def _load_json_if_exists(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.debug("Failed to load JSON from %s: %s", path, e)
        return None
    return payload


def _load_failed_thresholds_for_run(run_dir: Path) -> list[dict[str, Any]]:
    summary = _load_json_if_exists(run_dir / "summary.json")
    failed = summary.get("failed_thresholds") if isinstance(summary, dict) else None
    if isinstance(failed, list):
        return failed
    step_findings = _load_json_if_exists(run_dir / "step_findings.json")
    findings = step_findings if isinstance(step_findings, list) else []
    return [
        item
        for item in findings
        if isinstance(item, dict) and str(item.get("stage")) == "threshold"
    ]


def _directory_snapshot(dir_path: Path) -> dict[str, Any]:
    if not dir_path.exists():
        return {"exists": False, "entries": []}
    entries: list[dict[str, Any]] = []
    for path in sorted(
        (item for item in dir_path.rglob("*") if item.is_file()), key=lambda p: str(p)
    ):
        try:
            stat = path.stat()
        except OSError:
            continue
        entries.append(
            {
                "path": str(path.relative_to(dir_path)),
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
            }
        )
    return {"exists": True, "entries": entries}


def _build_input_provenance(
    *,
    dataset_path: Path | None,
    raw_data_dir: Path,
    sha256_file_fn: Callable[[str | Path | None], str | None],
) -> dict[str, Any]:
    snapshot = _directory_snapshot(raw_data_dir)
    return {
        "dataset_file_sha256": sha256_file_fn(dataset_path),
        "download_manifest_sha256": sha256_file_fn(raw_data_dir / "download_manifest.json"),
        "raw_data_snapshot": snapshot,
        "raw_data_snapshot_sha256": build_run_identity(config=snapshot, git_head=None),
    }


def run_assessment(
    *,
    artifact_dir: str | Path = "data/evals",
    name: str | None = None,
    dataset_path: str | Path | None = None,
    top_k: int = 5,
    max_synthetic_questions: int = 40,
    disable_llm_generation: bool = False,
    disable_llm_judging: bool = False,
    include_answer_eval: bool | None = None,
    sample_docs_per_source_type: int = 10,
    seed: int = 42,
    max_queries: int | None = None,
    sample_seed: int = 42,
    reuse_cached_dataset: bool = False,
    fail_on_thresholds: bool = False,
    thresholds_file: str | Path | None = None,
    dataset_split: str | None = None,
    min_label_confidence: str = "low",
    retrieval_mode: str = "rrf_hybrid",
    disable_page_classification: bool = False,
    disable_structured_chunking: bool = False,
    disable_bm25: bool = False,
    export_failed_generations: bool = False,
    force_rerun: bool = False,
    retrieval_options: dict[str, Any] | None = None,
    run_retrieval_ablations: bool = False,
    run_hype_ablations: bool = False,
    run_keyword_ablations: bool = False,
    run_reranking_ablations: bool = False,
    run_diversity_sweep: bool = False,
    diversity_sweep: dict[str, Any] | None = None,
    experiment_config: dict[str, Any] | None = None,
    audit_l0_download_fn: Callable[[], dict[str, Any]] | None = None,
    assess_l1_html_markdown_quality_fn: Callable[[], dict[str, Any]] | None = None,
    assess_l2_pdf_quality_fn: Callable[[], dict[str, Any]] | None = None,
    assess_l3_chunking_quality_fn: Callable[[], dict[str, Any]] | None = None,
    assess_l4_reference_quality_fn: Callable[[], dict[str, Any]] | None = None,
    assess_l5_index_quality_fn: Callable[..., dict[str, Any]] | None = None,
    build_retrieval_dataset_fn: Callable[..., dict[str, Any]] = build_retrieval_dataset,
    evaluate_retrieval_fn: Callable[
        ..., tuple[list[dict[str, Any]], dict[str, Any]]
    ] = evaluate_retrieval,
    evaluate_answers_fn: Callable[
        ..., tuple[list[dict[str, Any]], dict[str, Any]]
    ] = evaluate_answer_quality,
    evaluate_thresholds_fn: Callable[..., list[dict[str, Any]]] = evaluate_thresholds,
    git_head_fn: Callable[[], str | None] = git_head,
    configure_runtime_for_experiment_fn: Callable[
        [dict[str, Any] | None], dict[str, Any]
    ] = configure_runtime_for_experiment,
    initialize_runtime_index_fn: Callable[..., dict[str, Any]] = initialize_runtime_index,
    log_assessment_to_wandb_fn: Callable[..., dict[str, Any]] = log_assessment_to_wandb,
    run_retrieval_ablations_fn: Callable[..., dict[str, Any]] = run_retrieval_ablations,
    run_hype_ablations_fn: Callable[..., dict[str, Any]] = run_hype_ablations,
    run_keyword_ablations_fn: Callable[..., dict[str, Any]] = run_keyword_ablations,
    run_keyword_ablations_with_reingest_fn: Callable[
        ..., dict[str, Any]
    ] = run_keyword_ablations_with_reingest,
    run_hype_ablations_with_reingest_fn: Callable[
        ..., dict[str, Any]
    ] = run_hype_ablations_with_reingest,
    run_reranking_ablations_fn: Callable[..., dict[str, Any]] = run_reranking_ablations,
    run_diversity_sweep_fn: Callable[..., list[dict[str, Any]]] = run_diversity_sweep,
    render_summary_fn: Callable[..., str] = render_summary,
    sha256_file_fn: Callable[[str | Path | None], str | None] = sha256_file,
) -> AssessmentResult:
    start = time.time()
    from src.ingestion.indexing.vector_store import set_vector_store_runtime_config
    from src.ingestion.steps.chunk_text import (
        set_source_chunk_configs,
        set_structured_chunking_enabled,
    )
    from src.ingestion.steps.convert_html import (
        set_html_extractor_mode,
        set_page_classification_enabled,
    )
    from src.ingestion.steps.load_markdown import set_index_only_classified_pages

    thresholds = dict(DEFAULT_THRESHOLDS)
    if thresholds_file:
        thresholds.update(json.loads(Path(thresholds_file).read_text(encoding="utf-8")))

    key_available = (
        bool(settings.dashscope_api_key) and settings.dashscope_api_key != "test-api-key"
    )
    resolved_include_answer_eval = (
        bool(include_answer_eval) if include_answer_eval is not None else key_available
    )
    resolved_retrieval_options = dict(retrieval_options or {})
    if disable_bm25:
        resolved_retrieval_options["search_mode"] = "semantic_only"
    elif retrieval_mode != "rrf_hybrid":
        resolved_retrieval_options["search_mode"] = retrieval_mode
    config = AssessmentConfig(
        artifact_dir=Path(artifact_dir),
        name=name,
        dataset_path=Path(dataset_path) if dataset_path else None,
        top_k=top_k,
        max_synthetic_questions=max_synthetic_questions,
        disable_llm_generation=disable_llm_generation,
        disable_llm_judging=disable_llm_judging,
        include_answer_eval=resolved_include_answer_eval,
        sample_docs_per_source_type=sample_docs_per_source_type,
        seed=seed,
        max_queries=max_queries,
        sample_seed=sample_seed,
        reuse_cached_dataset=reuse_cached_dataset,
        fail_on_thresholds=fail_on_thresholds,
        thresholds=thresholds,
        retrieval_options=resolved_retrieval_options,
        dataset_split=dataset_split,
        min_label_confidence=min_label_confidence,
        retrieval_mode=retrieval_mode,
        disable_page_classification=disable_page_classification,
        disable_structured_chunking=disable_structured_chunking,
        disable_bm25=disable_bm25,
        export_failed_generations=export_failed_generations,
        run_retrieval_ablations=run_retrieval_ablations,
        run_hype_ablations=run_hype_ablations,
        run_keyword_ablations=run_keyword_ablations,
        run_reranking_ablations=run_reranking_ablations,
        run_diversity_sweep=run_diversity_sweep,
        diversity_sweep=dict(diversity_sweep or {}),
        experiment_config=experiment_config,
        force_rerun=force_rerun,
    )
    config_payload = asdict(config)
    git_revision = git_head_fn()
    input_provenance = _build_input_provenance(
        dataset_path=config.dataset_path,
        raw_data_dir=DATA_RAW_DIR,
        sha256_file_fn=sha256_file_fn,
    )
    run_identity = build_run_identity(
        config={"assessment": config_payload, "input_provenance": input_provenance},
        git_head=git_revision,
    )
    reusable_run_dir = (
        None if config.force_rerun else find_reusable_run(config.artifact_dir, run_identity)
    )
    if reusable_run_dir is not None:
        write_latest_pointer(config.artifact_dir, reusable_run_dir)
        reused_summary = _load_json_if_exists(reusable_run_dir / "summary.json")
        reused_summary["dedup"] = {
            "reused_existing_run": True,
            "matched_run_dir": str(reusable_run_dir),
            "run_identity": run_identity,
            "force_rerun": False,
        }
        return AssessmentResult(
            run_dir=reusable_run_dir,
            status=str(reused_summary.get("status", "ok")),
            failed_thresholds=_load_failed_thresholds_for_run(reusable_run_dir),
            summary=reused_summary,
        )

    experiment_runtime = configure_runtime_for_experiment_fn(config.experiment_config)
    index_preparation: dict[str, Any] = {"status": "not_requested"}
    if not config.experiment_config:
        set_page_classification_enabled(not disable_page_classification)
        set_index_only_classified_pages(not disable_page_classification)
        set_html_extractor_mode("auto")
        set_structured_chunking_enabled(not disable_structured_chunking)
        set_source_chunk_configs(None)
        set_vector_store_runtime_config(None)
    if config.experiment_config:
        embedding_index = config.experiment_config.get("embedding_index", {})
        vector_config = experiment_runtime.get("vector_store", {})
        vector_path = Path("data/vectors") / (
            f"{vector_config.get('collection_name', settings.collection_name)}.json"
        )
        existing_index_hash = None
        if vector_path.exists():
            try:
                payload = json.loads(vector_path.read_text(encoding="utf-8"))
                existing_index_hash = (payload.get("index_metadata", {}) or {}).get(
                    "index_config_hash"
                )
            except Exception as e:
                logger.debug("Failed to load vector index hash from %s: %s", vector_path, e)
                existing_index_hash = None
        rebuild_policy = str(embedding_index.get("rebuild_policy", "if_missing_or_stale")).lower()
        should_rebuild = rebuild_policy == "always"
        if rebuild_policy in {"if_missing_or_stale", "auto"}:
            should_rebuild = (not vector_path.exists()) or (
                existing_index_hash != config.experiment_config.get("index_config_hash")
            )
        if rebuild_policy == "never" and existing_index_hash not in {
            None,
            config.experiment_config.get("index_config_hash"),
        }:
            raise ValueError("Experiment index configuration does not match existing index")
        index_preparation = initialize_runtime_index_fn(
            rebuild=should_rebuild,
            materialize_html=bool(embedding_index.get("materialize_html", True)),
            force_html_reconvert=should_rebuild,
        )

    store = ArtifactStore(config.artifact_dir, config.name)
    manifest = {
        "config": config_payload,
        "git_head": git_revision,
        "run_identity": run_identity,
        "input_provenance": input_provenance,
        "dashscope_key_present": key_available,
        "started_at_epoch_s": start,
        "experiment": {
            "file": (config.experiment_config or {}).get("experiment_file"),
            "variant": (config.experiment_config or {}).get("variant_name"),
            "config_hash": (config.experiment_config or {}).get("experiment_config_hash"),
            "index_config_hash": (config.experiment_config or {}).get("index_config_hash"),
        },
        "index_preparation": index_preparation,
    }
    store.write_json("manifest.json", manifest)

    l5_collection_name = experiment_runtime.get("vector_store", {}).get("collection_name")
    if (
        audit_l0_download_fn is None
        or assess_l1_html_markdown_quality_fn is None
        or assess_l2_pdf_quality_fn is None
        or assess_l3_chunking_quality_fn is None
        or assess_l4_reference_quality_fn is None
        or assess_l5_index_quality_fn is None
    ):
        raise ValueError("Assessment stage functions must be provided")
    audit_l0 = cast(Callable[[], dict[str, Any]], audit_l0_download_fn)
    assess_l1 = cast(Callable[[], dict[str, Any]], assess_l1_html_markdown_quality_fn)
    assess_l2 = cast(Callable[[], dict[str, Any]], assess_l2_pdf_quality_fn)
    assess_l3 = cast(Callable[[], dict[str, Any]], assess_l3_chunking_quality_fn)
    assess_l4 = cast(Callable[[], dict[str, Any]], assess_l4_reference_quality_fn)
    assess_l5 = cast(Callable[..., dict[str, Any]], assess_l5_index_quality_fn)
    step_metrics = {
        "l0": audit_l0(),
        "l1": assess_l1(),
        "l2": assess_l2(),
        "l3": assess_l3(),
        "l4": assess_l4(),
        "l5": assess_l5(collection_name=l5_collection_name) if l5_collection_name else assess_l5(),
    }
    step_findings: list[dict[str, Any]] = []
    for stage in step_metrics.values():
        step_findings.extend(stage.get("findings", []))
    l5_agg = step_metrics.get("l5", {}).get("aggregate", {})
    vector_path = l5_agg.get("vector_path")
    vector_file_sha256 = sha256_file_fn(vector_path)

    dataset_bundle = build_retrieval_dataset_fn(
        dataset_path=config.dataset_path,
        enable_llm_generation=not config.disable_llm_generation,
        max_synthetic_questions=config.max_synthetic_questions,
        sample_docs_per_source_type=config.sample_docs_per_source_type,
        seed=config.seed,
        max_queries=config.max_queries,
        sample_seed=config.sample_seed,
        reuse_cached_dataset=config.reuse_cached_dataset,
        reuse_requirements={
            "experiment_index_config_hash": (
                (config.experiment_config or {}).get("index_config_hash")
            ),
            "vector_file_sha256": vector_file_sha256,
        },
        artifact_dir=config.artifact_dir,
        dataset_split=config.dataset_split,
        min_label_confidence=config.min_label_confidence,
    )
    dataset = dataset_bundle["dataset"]
    generation_attempts = dataset_bundle.get("generation_attempts", [])
    dataset_stats = dataset_bundle.get("stats", {})

    if config.retrieval_options:
        retrieval_rows, retrieval_metrics = evaluate_retrieval_fn(
            dataset, config.top_k, retrieval_options=config.retrieval_options
        )
    else:
        retrieval_rows, retrieval_metrics = evaluate_retrieval_fn(dataset, config.top_k)
    retrieval_ablations: dict[str, Any] = {}
    if config.run_retrieval_ablations:
        retrieval_ablations = run_retrieval_ablations_fn(
            dataset, config.top_k, base_options=config.retrieval_options
        )
    hype_ablations: dict[str, Any] = {}
    if config.run_hype_ablations:
        if config.experiment_config:

            def _rebuild_hype_index(hype_config, collection_name):
                exp = dict(config.experiment_config or {})
                ingestion = dict(exp.get("ingestion", {}))
                ingestion.update(hype_config)
                exp["ingestion"] = ingestion
                embedding_index = dict(exp.get("embedding_index", {}))
                embedding_index["collection_name"] = collection_name
                exp["embedding_index"] = embedding_index
                configure_runtime_for_experiment_fn(exp)
                initialize_runtime_index_fn(
                    rebuild=True, materialize_html=True, force_html_reconvert=True
                )

            hype_ablations = run_hype_ablations_with_reingest_fn(
                dataset,
                config.top_k,
                base_options=config.retrieval_options,
                base_collection_name=l5_collection_name,
                reconfigure_and_rebuild_fn=_rebuild_hype_index,
            )
        else:
            hype_ablations = run_hype_ablations_fn(
                dataset, config.top_k, base_options=config.retrieval_options
            )
    reranking_ablations: dict[str, Any] = {}
    if config.run_reranking_ablations:
        reranking_ablations = run_reranking_ablations_fn(
            dataset, config.top_k, base_options=config.retrieval_options
        )
    keyword_ablations: dict[str, Any] = {}
    if config.run_keyword_ablations:
        if config.experiment_config:

            def _rebuild_keyword_index(enrichment_config, collection_name):
                exp = dict(config.experiment_config or {})
                ingestion = dict(exp.get("ingestion", {}))
                ingestion.update(enrichment_config)
                exp["ingestion"] = ingestion
                embedding_index = dict(exp.get("embedding_index", {}))
                embedding_index["collection_name"] = collection_name
                exp["embedding_index"] = embedding_index
                configure_runtime_for_experiment_fn(exp)
                initialize_runtime_index_fn(
                    rebuild=True, materialize_html=True, force_html_reconvert=False
                )

            keyword_ablations = run_keyword_ablations_with_reingest_fn(
                dataset,
                config.top_k,
                base_options=config.retrieval_options,
                base_collection_name=l5_collection_name,
                reconfigure_and_rebuild_fn=_rebuild_keyword_index,
            )
        else:
            keyword_ablations = run_keyword_ablations_fn(
                dataset, config.top_k, base_options=config.retrieval_options
            )
    diversity_sweep_rows: list[dict[str, Any]] = []
    if config.run_diversity_sweep:
        diversity_sweep_rows = run_diversity_sweep_fn(
            dataset,
            config.top_k,
            base_options=config.retrieval_options,
            mmr_lambda_values=config.diversity_sweep.get("mmr_lambda_values"),
            overfetch_multipliers=config.diversity_sweep.get("overfetch_multipliers"),
            max_chunks_per_source_page_values=config.diversity_sweep.get(
                "max_chunks_per_source_page_values"
            ),
            max_chunks_per_source_values=config.diversity_sweep.get("max_chunks_per_source_values"),
        )
    l3_agg = step_metrics.get("l3", {}).get("aggregate", {})
    l6_answer_quality_rows: list[dict[str, Any]] = []
    l6_answer_quality_metrics: dict[str, Any] = {"status": "skipped", "reason": "disabled"}
    if config.include_answer_eval and not config.disable_llm_judging:
        l6_answer_quality_rows, l6_answer_quality_metrics = evaluate_answers_fn(
            dataset,
            config.top_k,
            cache_dir=Path(getattr(settings, "deepeval_cache_dir", "data/evals/cache")),
            retrieval_options=config.retrieval_options,
            cache_namespace={
                "retrieval_mode": config.retrieval_mode,
                "experiment_index_config_hash": (
                    (config.experiment_config or {}).get("index_config_hash")
                ),
                "experiment_variant": ((config.experiment_config or {}).get("variant_name")),
                "vector_file_sha256": vector_file_sha256,
            },
        )
    elif config.disable_llm_judging:
        l6_answer_quality_metrics = {"status": "skipped", "reason": "llm_judging_disabled"}

    failed_thresholds = evaluate_thresholds_fn(
        step_metrics,
        retrieval_metrics,
        l6_answer_quality_metrics,
        config.thresholds,
    )
    step_findings.extend(
        {
            "severity": "error",
            "stage": "threshold",
            "message": f"{f['metric']} below threshold",
            **f,
        }
        for f in failed_thresholds
    )

    dataset_file = dataset_stats.get("dataset_path") or (
        str(config.dataset_path) if config.dataset_path else None
    )
    manifest["runtime_retrieval"] = retrieval_metrics.get("retrieval_options", {})
    manifest["dataset"] = dataset_stats
    manifest["chunking"] = {
        "chunk_size_config": l3_agg.get("chunk_size_config"),
        "chunk_overlap_config": l3_agg.get("chunk_overlap_config"),
        "structured_chunking_enabled": not config.disable_structured_chunking,
        "source_chunk_configs": (
            (config.experiment_config or {}).get("ingestion", {}).get("source_chunk_configs")
        ),
        "page_classification_enabled": not config.disable_page_classification,
        "html_extractor_mode": (
            (config.experiment_config or {}).get("ingestion", {}).get("html_extractor_mode")
        ),
    }
    index_metadata: dict[str, Any] = {}
    if vector_path and Path(vector_path).exists():
        try:
            index_payload = json.loads(Path(vector_path).read_text(encoding="utf-8"))
            index_metadata = index_payload.get("index_metadata", {}) or {}
        except Exception as e:
            logger.debug("Failed to load index metadata from %s: %s", vector_path, e)
            index_metadata = {}
    manifest["index_provenance"] = {
        "collection_name": index_metadata.get("collection_name", settings.collection_name),
        "vector_path": vector_path,
        "vector_file_mtime_epoch_s": Path(vector_path).stat().st_mtime
        if vector_path and Path(vector_path).exists()
        else None,
        "doc_counts_by_source_type": l5_agg.get("source_distribution", {}),
        "dedupe_effect_estimate": l5_agg.get("dedupe_effect_estimate"),
        "index_config_hash": index_metadata.get("index_config_hash"),
        "embedding_model": index_metadata.get("embedding_model"),
        "embedding_batch_size": index_metadata.get("embedding_batch_size"),
        "semantic_weight": index_metadata.get("semantic_weight"),
        "keyword_weight": index_metadata.get("keyword_weight"),
        "boost_weight": index_metadata.get("boost_weight"),
        "page_classification_enabled": index_metadata.get("page_classification_enabled"),
        "index_only_classified_pages": index_metadata.get("index_only_classified_pages"),
        "html_extractor_mode": index_metadata.get("html_extractor_mode"),
        "structured_chunking_enabled": index_metadata.get("structured_chunking_enabled"),
        "source_chunk_configs": (
            (lambda v: json.loads(v) if isinstance(v, str) else v)(
                index_metadata.get("source_chunk_configs")
            )
        ),
        "observed_embedding_dim": l5_agg.get("embedding_dim"),
        "indexing_stats": index_preparation.get("indexing_stats", {}),
    }
    manifest["checksums"] = {
        "vector_file_sha256": vector_file_sha256,
        "dataset_file_sha256": sha256_file_fn(dataset_file),
    }
    store.write_json("manifest.json", manifest)

    store.write_json("step_metrics.json", step_metrics)
    store.write_json("step_findings.json", step_findings)
    store.write_jsonl("html_metrics.jsonl", step_metrics["l1"].get("records", []))
    store.write_jsonl("pdf_metrics.jsonl", step_metrics["l2"].get("records", []))
    store.write_jsonl("chunk_metrics.jsonl", step_metrics["l3"].get("records", []))
    store.write_json("reference_metrics.json", step_metrics["l4"])
    store.write_json("index_metrics.json", step_metrics["l5"])
    store.write_json("retrieval_dataset.json", dataset)
    if config.export_failed_generations:
        store.write_jsonl("retrieval_dataset_generation.jsonl", generation_attempts)
    else:
        store.write_jsonl(
            "retrieval_dataset_generation.jsonl",
            [row for row in generation_attempts if row.get("status") == "accepted"],
        )
    store.write_jsonl("retrieval_results.jsonl", retrieval_rows)
    store.write_json("retrieval_metrics.json", retrieval_metrics)
    store.write_json("retrieval_ablations.json", retrieval_ablations)
    store.write_json("hype_ablations.json", hype_ablations)
    store.write_json("keyword_ablations.json", keyword_ablations)
    store.write_json("reranking_ablations.json", reranking_ablations)
    store.write_json("retrieval_diversity_sweep.json", diversity_sweep_rows)
    store.write_jsonl(L6_ANSWER_QUALITY_ROWS, l6_answer_quality_rows)
    store.write_json(L6_ANSWER_QUALITY_METRICS, l6_answer_quality_metrics)

    summary = {
        "run_dir": str(store.run_dir),
        "duration_s": round(time.time() - start, 3),
        "retrieval_metrics": retrieval_metrics,
        "retrieval_ablations": retrieval_ablations,
        "hype_ablations": hype_ablations,
        "keyword_ablations": keyword_ablations,
        "reranking_ablations": reranking_ablations,
        "retrieval_diversity_sweep_top": diversity_sweep_rows[:5],
        SUMMARY_L6_METRICS_KEY: l6_answer_quality_metrics,
        SUMMARY_L6_ENABLED_KEY: bool(config.include_answer_eval),
        SUMMARY_L6_STATUS_KEY: l6_answer_quality_metrics.get("status", "unknown"),
        "failed_thresholds_count": len(failed_thresholds),
        "status": "failed" if (failed_thresholds and config.fail_on_thresholds) else "ok",
        "dedup": {
            "reused_existing_run": False,
            "run_identity": run_identity,
            "force_rerun": bool(config.force_rerun),
        },
    }
    store.write_text(
        "summary.md",
        render_summary_fn(
            step_metrics=step_metrics,
            retrieval_metrics=retrieval_metrics,
            l6_answer_quality_metrics=l6_answer_quality_metrics,
            dataset_stats=dataset_stats,
            failed_thresholds=failed_thresholds,
        ),
    )
    tracking_info = log_assessment_to_wandb_fn(
        experiment=config.experiment_config,
        summary=summary,
        manifest=manifest,
        step_metrics=step_metrics,
        retrieval_metrics=retrieval_metrics,
        l6_answer_quality_metrics=l6_answer_quality_metrics,
        run_dir=store.run_dir,
        failed_thresholds=failed_thresholds,
    )
    manifest["tracking"] = {"wandb": tracking_info}
    summary["tracking"] = {"wandb": tracking_info}
    store.write_json("manifest.json", manifest)
    store.write_json("summary.json", summary)
    store.write_latest_pointer()
    update_run_index(config.artifact_dir, run_identity=run_identity, run_dir=store.run_dir)

    status = "failed" if (failed_thresholds and config.fail_on_thresholds) else "ok"
    return AssessmentResult(
        run_dir=store.run_dir, status=status, failed_thresholds=failed_thresholds, summary=summary
    )
