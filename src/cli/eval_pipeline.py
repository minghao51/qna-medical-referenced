"""CLI entrypoint for pipeline quality assessment."""

import argparse
import json
import logging
import sys
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from src.evals import run_assessment
from src.evals.schemas import AssessmentResult
from src.evals.usage import paid_benchmark_budget_status, paid_operation_budget_status
from src.experiments import (
    build_run_assessment_kwargs,
    compute_retrieval_delta,
    resolve_experiment_runs,
)
from src.experiments.feature_addition_runner import (
    ensure_supported_selection_axes,
    run_assessment_in_subprocess,
    validate_execution_mode,
)

logger = logging.getLogger(__name__)


def _run_single_variant(kwargs: dict[str, Any]) -> dict[str, Any]:
    """Run one variant in a fresh worker process with isolated writable storage."""
    result = run_assessment_in_subprocess(kwargs)
    return {
        "run_dir": str(result.run_dir),
        "status": result.status,
        "failed_thresholds": result.failed_thresholds,
        "summary": result.summary,
    }


def _run_variants_parallel(
    specs: list[dict[str, Any]],
    cli_overrides_fn,
    max_workers: int,
) -> list[tuple[int, dict[str, Any]]]:
    """Launch one isolated subprocess per variant, optionally concurrently.

    Returns list of (index, result_dict) tuples ordered by completion.
    """
    results: list[tuple[int, dict[str, Any]]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_idx = {}
        for idx, spec in enumerate(specs):
            kwargs = cli_overrides_fn(spec, idx)
            future = executor.submit(_run_single_variant, kwargs)
            future_to_idx[future] = idx

        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                result = future.result()
                results.append((idx, result))
            except Exception as exc:
                logger.error("Variant %s failed (%s)", idx, type(exc).__name__)
                results.append(
                    (
                        idx,
                        {
                            "run_dir": None,
                            "status": "failed",
                            "failed_thresholds": [],
                            "summary": {"error": f"isolated run failed ({type(exc).__name__})"},
                        },
                    )
                )

    return results


def _load_usage_records(path: str | Path) -> list[dict[str, Any]]:
    """Read local usage records or one run summary without contacting services."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    manifest_execution_mode: str | None = None
    if isinstance(payload, dict):
        mode = payload.get("execution_mode")
        manifest_execution_mode = mode if isinstance(mode, str) else None
        if isinstance(payload.get("records"), list):
            payload = payload["records"]
        else:
            payload = payload.get("usage_summary", payload)
            payload = payload if isinstance(payload, list) else [payload]
    if not isinstance(payload, list) or any(not isinstance(item, dict) for item in payload):
        raise ValueError("Usage summary must be a JSON record or an array of records")
    records = [dict(item) for item in payload]
    if manifest_execution_mode in {"benchmark", "diagnostic"}:
        for record in records:
            if record.get("record_type") != "manual_adjustment":
                record.setdefault("execution_mode", manifest_execution_mode)
    return records


def _operation_budget_statuses(
    records: Sequence[Mapping[str, Any]], month: str, *, overage_off_confirmed: bool
) -> dict[str, dict[str, Any]]:
    """Report shared-pool admission for benchmark and recorded paid eval modes."""
    operations = {"benchmark"}
    operations.update(
        str(record["execution_mode"])
        for record in records
        if record.get("execution_mode") in {"benchmark", "diagnostic"}
    )
    return {
        operation: paid_operation_budget_status(
            records,
            utc_month=month,
            operation=operation,
            overage_off_confirmed=overage_off_confirmed,
        )
        for operation in sorted(operations)
    }


def _usage_budget_status(
    path: str | Path, month: str, *, overage_off_confirmed: bool
) -> dict[str, Any]:
    return paid_benchmark_budget_status(
        _load_usage_records(path),
        utc_month=month,
        overage_off_confirmed=overage_off_confirmed,
    )


def _parse_csv_floats(value: str | None) -> list[float] | None:
    if not value:
        return None
    return [float(x.strip()) for x in value.split(",") if x.strip()]


def _parse_csv_ints(value: str | None) -> list[int] | None:
    if not value:
        return None
    return [int(x.strip()) for x in value.split(",") if x.strip()]


def _provided_flags(argv: list[str]) -> set[str]:
    flags: set[str] = set()
    for token in argv:
        if token.startswith("--"):
            flags.add(token.split("=", 1)[0])
    return flags


def _run_assessment_worker(result_path: str) -> int:
    """Private subprocess entrypoint; read resolved config from a private stdin pipe."""
    from src.evals.artifacts import to_serializable

    try:
        kwargs = json.loads(sys.stdin.read())
        if not isinstance(kwargs, dict):
            raise ValueError("worker config must be an object")
        ensure_supported_selection_axes(kwargs)
        validate_execution_mode(
            str(kwargs.get("execution_mode", "diagnostic")),
            index_snapshot_path=kwargs.get("index_snapshot_path"),
        )
        result = run_assessment(**kwargs)
        summary = result.summary if isinstance(result.summary, dict) else {}
        summary_keys = {
            "status",
            "execution_status",
            "measurement_contract_version",
            "measurement",
            "quality_gate",
            "identity",
            "cache_policy",
            "retrieval_metrics",
            "metrics",
            "index_execution",
            "l6_retrieval_quality_metrics",
            "l6_answer_quality_metrics",
            "dedup",
            "duration_s",
            "usage_summary",
            "evaluator_overhead_ms",
        }
        payload = {
            "run_dir": str(result.run_dir),
            "status": result.status,
            "failed_threshold_count": len(result.failed_thresholds),
            "summary": to_serializable(
                {key: value for key, value in summary.items() if key in summary_keys}
            ),
        }
        Path(result_path).write_text(
            json.dumps(payload, ensure_ascii=False, allow_nan=False), encoding="utf-8"
        )
        return 0
    except Exception as exc:
        Path(result_path).write_text(
            json.dumps({"status": "worker_error", "error_type": type(exc).__name__}),
            encoding="utf-8",
        )
        return 1


def _print_assessment_result(result: Any, baseline_result: Any = None) -> None:
    print(f"Evaluation complete: {result.run_dir}")
    print(f"Status: {result.status}")
    dedup = dict(result.summary.get("dedup") or {})
    if dedup.get("reused_existing_run"):
        print(f"Reused existing run: {dedup.get('matched_run_dir') or result.run_dir}")
    elif dedup.get("force_rerun"):
        print("Dedup bypassed: force rerun")
    if result.failed_thresholds:
        print(f"Threshold failures: {len(result.failed_thresholds)}")
    if baseline_result is not None:
        baseline_metrics = baseline_result.summary.get("retrieval_metrics", {})
        delta = compute_retrieval_delta(
            baseline_metrics, result.summary.get("retrieval_metrics", {})
        )
        comparison_path = result.run_dir / "comparison_to_baseline.json"
        comparison_path.write_text(
            json.dumps(
                {
                    "baseline_run_dir": str(baseline_result.run_dir),
                    "baseline_name": None,
                    "delta": delta,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"Baseline delta: {comparison_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate ingestion + retrieval pipeline quality")
    parser.add_argument("--config", default=None, help="Versioned experiment YAML path")
    parser.add_argument(
        "--generation-implementation",
        choices=["existing"],
        default="existing",
        help="Generation implementation (only the existing RAG path is supported)",
    )
    parser.add_argument(
        "--harness",
        choices=["deterministic_rag"],
        default="deterministic_rag",
        help="Evaluation harness (only deterministic_rag is supported)",
    )
    parser.add_argument(
        "--usage-summary",
        default=None,
        help="Read local JSON usage records for offline budget diagnostics (does not run an assessment)",
    )
    parser.add_argument(
        "--usage-month", default=None, help="UTC month for usage diagnostics (YYYY-MM)"
    )
    parser.add_argument(
        "--confirm-overage-off",
        action="store_true",
        help="Acknowledge external provider overage and auto-top-up are disabled",
    )
    parser.add_argument(
        "--execution-mode",
        default="diagnostic",
        choices=["diagnostic", "benchmark", "replay"],
        help="Diagnostic legacy run, fresh benchmark, or explicit functional replay",
    )
    parser.add_argument("--_assessment-worker-result", help=argparse.SUPPRESS)
    parser.add_argument("--variant", default=None, help="Named experiment variant to run")
    parser.add_argument(
        "--all-variants",
        action="store_true",
        help="Run the base experiment and all named variants from the config file",
    )
    parser.add_argument(
        "--artifact-dir", default="data/evals", help="Base directory for saved evaluation artifacts"
    )
    parser.add_argument("--name", default=None, help="Optional run label")
    parser.add_argument("--dataset-path", default=None, help="Optional JSON dataset path")
    parser.add_argument(
        "--review-manifest-path",
        default=None,
        help="Optional out-of-band reviewed retrieval manifest (requires an explicit frozen dataset)",
    )
    parser.add_argument(
        "--index-snapshot-path",
        default=None,
        help="Read-only verified frozen index export required for benchmark mode",
    )
    parser.add_argument("--top-k", type=int, default=5, help="Retrieval top-k")
    parser.add_argument("--max-synthetic-questions", type=int, default=40)
    parser.add_argument("--disable-llm-generation", action="store_true")
    parser.add_argument("--disable-llm-judging", action="store_true")
    parser.add_argument("--include-answer-eval", action="store_true")
    parser.add_argument("--sample-docs-per-source-type", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-queries", type=int, default=None)
    parser.add_argument("--sample-seed", type=int, default=42)
    parser.add_argument(
        "--reuse-cached-dataset",
        action="store_true",
        help="Replay unavailable until identity is verified; select --dataset-path explicitly",
    )
    parser.add_argument(
        "--force-rerun",
        action="store_true",
        help="Compatibility flag: all assessments now execute fresh attempts",
    )
    parser.add_argument("--fail-on-thresholds", action="store_true")
    parser.add_argument("--thresholds-file", default=None)
    parser.add_argument("--dataset-split", default=None, choices=["dev", "test", "regression"])
    parser.add_argument("--min-label-confidence", default="low", choices=["low", "medium", "high"])
    parser.add_argument(
        "--retrieval-mode",
        default="rrf_hybrid",
        choices=["rrf_hybrid", "semantic_only", "bm25_only"],
    )
    parser.add_argument("--disable-page-classification", action="store_true")
    parser.add_argument("--disable-structured-chunking", action="store_true")
    parser.add_argument("--disable-bm25", action="store_true")
    parser.add_argument("--export-failed-generations", action="store_true")
    parser.add_argument(
        "--search-mode",
        default="rrf_hybrid",
        choices=["rrf_hybrid", "semantic_only", "bm25_only"],
    )
    parser.add_argument("--no-diversification", action="store_true")
    parser.add_argument("--enable-hyde", action="store_true", help="Enable HyDE query expansion")
    parser.add_argument(
        "--enable-reranking", action="store_true", help="Enable cross-encoder reranking"
    )
    parser.add_argument(
        "--reranking-mode",
        default="cross_encoder",
        choices=["cross_encoder", "mmr", "both"],
        help="Reranking strategy",
    )
    parser.add_argument("--mmr-lambda", type=float, default=None)
    parser.add_argument("--overfetch-multiplier", type=int, default=None)
    parser.add_argument("--max-chunks-per-source-page", type=int, default=None)
    parser.add_argument("--max-chunks-per-source", type=int, default=None)
    parser.add_argument("--run-retrieval-ablations", action="store_true")
    parser.add_argument("--run-hype-ablations", action="store_true")
    parser.add_argument("--run-keyword-ablations", action="store_true")
    parser.add_argument("--run-reranking-ablations", action="store_true")
    parser.add_argument("--run-diversity-sweep", action="store_true")
    parser.add_argument(
        "--sweep-mmr-lambdas", default=None, help="Comma-separated, e.g. 0.5,0.75,0.9"
    )
    parser.add_argument("--sweep-overfetch-multipliers", default=None, help="Comma-separated ints")
    parser.add_argument(
        "--sweep-max-chunks-per-source-page", default=None, help="Comma-separated ints"
    )
    parser.add_argument("--sweep-max-chunks-per-source", default=None, help="Comma-separated ints")
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Run variants concurrently in separate isolated subprocesses",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=None,
        help="Max parallel workers (default: number of variants)",
    )
    args = parser.parse_args()
    if args._assessment_worker_result:
        raise SystemExit(_run_assessment_worker(args._assessment_worker_result))
    if bool(args.usage_summary) != bool(args.usage_month):
        parser.error("--usage-summary and --usage-month must be supplied together")
    if args.execution_mode == "benchmark":
        if not args.usage_summary or not args.usage_month:
            parser.error("Benchmark mode requires --usage-summary and --usage-month")
        try:
            budget_status = _usage_budget_status(
                args.usage_summary,
                args.usage_month,
                overage_off_confirmed=args.confirm_overage_off,
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            parser.error(f"Could not verify benchmark usage budget ({type(exc).__name__})")
        print(json.dumps(budget_status, indent=2, sort_keys=True))
        if not budget_status["allowed"]:
            raise SystemExit(2)
    elif args.usage_summary:
        try:
            budget_status = _usage_budget_status(
                args.usage_summary,
                args.usage_month,
                overage_off_confirmed=args.confirm_overage_off,
            )
            records = _load_usage_records(args.usage_summary)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            parser.error(f"Could not read usage summary ({type(exc).__name__})")
        budget_status["operation_admission"] = _operation_budget_statuses(
            records,
            args.usage_month,
            overage_off_confirmed=args.confirm_overage_off,
        )
        print(json.dumps(budget_status, indent=2, sort_keys=True))
        raise SystemExit(0)
    try:
        if not args.config:
            validate_execution_mode(
                args.execution_mode, index_snapshot_path=args.index_snapshot_path
            )
        elif args.execution_mode not in {"diagnostic", "benchmark", "replay"}:
            validate_execution_mode(args.execution_mode)
    except ValueError as exc:
        parser.error(str(exc))
    if args.execution_mode == "diagnostic":
        print("Execution mode: diagnostic (legacy exploratory output; not benchmark evidence)")
    provided_flags = _provided_flags(sys.argv[1:])
    # Keep the legacy mode aliases coherent; an explicit disable still wins.
    if "--search-mode" in provided_flags and "--retrieval-mode" not in provided_flags:
        args.retrieval_mode = args.search_mode
    if args.disable_bm25:
        args.retrieval_mode = "semantic_only"

    diversity_sweep = {
        k: v
        for k, v in {
            "mmr_lambda_values": _parse_csv_floats(args.sweep_mmr_lambdas),
            "overfetch_multipliers": _parse_csv_ints(args.sweep_overfetch_multipliers),
            "max_chunks_per_source_page_values": _parse_csv_ints(
                args.sweep_max_chunks_per_source_page
            ),
            "max_chunks_per_source_values": _parse_csv_ints(args.sweep_max_chunks_per_source),
        }.items()
        if v is not None
    }
    retrieval_options: dict[str, Any] = {}
    if not args.config or provided_flags & {"--search-mode", "--retrieval-mode", "--disable-bm25"}:
        retrieval_options["search_mode"] = args.retrieval_mode
    if "--top-k" in provided_flags:
        retrieval_options["top_k"] = args.top_k
    if args.no_diversification:
        retrieval_options["enable_diversification"] = False
    if args.enable_hyde:
        retrieval_options["enable_hyde"] = True
    if args.mmr_lambda is not None:
        retrieval_options["mmr_lambda"] = args.mmr_lambda
    if args.overfetch_multiplier is not None:
        retrieval_options["overfetch_multiplier"] = args.overfetch_multiplier
    if args.max_chunks_per_source_page is not None:
        retrieval_options["max_chunks_per_source_page"] = args.max_chunks_per_source_page
    if args.max_chunks_per_source is not None:
        retrieval_options["max_chunks_per_source"] = args.max_chunks_per_source
    if "--enable-reranking" in provided_flags:
        retrieval_options["enable_reranking"] = True
    if "--reranking-mode" in provided_flags:
        retrieval_options["reranking_mode"] = args.reranking_mode

    def _apply_cli_overrides(
        experiment: dict[str, Any], execution_order: int | None = None
    ) -> dict[str, Any]:
        normalized = dict(experiment)
        ensure_supported_selection_axes(normalized)
        kwargs = build_run_assessment_kwargs(normalized)
        merged = dict(kwargs)
        merged["execution_mode"] = args.execution_mode
        merged["execution_order"] = execution_order
        if "--generation-implementation" in provided_flags:
            merged["generation_implementation"] = args.generation_implementation
        if "--harness" in provided_flags:
            merged["harness"] = args.harness
        scalar_overrides = {
            "--artifact-dir": ("artifact_dir", args.artifact_dir),
            "--name": ("name", args.name),
            "--dataset-path": ("dataset_path", args.dataset_path),
            "--review-manifest-path": ("review_manifest_path", args.review_manifest_path),
            "--index-snapshot-path": ("index_snapshot_path", args.index_snapshot_path),
            "--top-k": ("top_k", args.top_k),
            "--max-synthetic-questions": ("max_synthetic_questions", args.max_synthetic_questions),
            "--sample-docs-per-source-type": (
                "sample_docs_per_source_type",
                args.sample_docs_per_source_type,
            ),
            "--seed": ("seed", args.seed),
            "--max-queries": ("max_queries", args.max_queries),
            "--sample-seed": ("sample_seed", args.sample_seed),
            "--thresholds-file": ("thresholds_file", args.thresholds_file),
            "--dataset-split": ("dataset_split", args.dataset_split),
            "--min-label-confidence": ("min_label_confidence", args.min_label_confidence),
            "--retrieval-mode": ("retrieval_mode", args.retrieval_mode),
            "--generation-implementation": (
                "generation_implementation",
                args.generation_implementation,
            ),
            "--harness": ("harness", args.harness),
        }
        for flag, (key, value) in scalar_overrides.items():
            if flag in provided_flags:
                merged[key] = value
        bool_overrides = {
            "--disable-llm-generation": ("disable_llm_generation", args.disable_llm_generation),
            "--disable-llm-judging": ("disable_llm_judging", args.disable_llm_judging),
            "--include-answer-eval": ("include_answer_eval", args.include_answer_eval),
            "--reuse-cached-dataset": ("reuse_cached_dataset", args.reuse_cached_dataset),
            "--force-rerun": ("force_rerun", args.force_rerun),
            "--fail-on-thresholds": ("fail_on_thresholds", args.fail_on_thresholds),
            "--disable-page-classification": (
                "disable_page_classification",
                args.disable_page_classification,
            ),
            "--disable-structured-chunking": (
                "disable_structured_chunking",
                args.disable_structured_chunking,
            ),
            "--disable-bm25": ("disable_bm25", args.disable_bm25),
            "--export-failed-generations": (
                "export_failed_generations",
                args.export_failed_generations,
            ),
            "--run-retrieval-ablations": (
                "run_retrieval_ablations",
                args.run_retrieval_ablations,
            ),
            "--run-hype-ablations": (
                "run_hype_ablations",
                args.run_hype_ablations,
            ),
            "--run-keyword-ablations": (
                "run_keyword_ablations",
                args.run_keyword_ablations,
            ),
            "--run-reranking-ablations": (
                "run_reranking_ablations",
                args.run_reranking_ablations,
            ),
            "--run-diversity-sweep": ("run_diversity_sweep", args.run_diversity_sweep),
        }
        for flag, (key, value) in bool_overrides.items():
            if flag in provided_flags:
                merged[key] = value
        if provided_flags & {"--search-mode", "--retrieval-mode", "--disable-bm25"}:
            merged["retrieval_mode"] = args.retrieval_mode
            if "--disable-bm25" not in provided_flags:
                merged["disable_bm25"] = args.retrieval_mode == "semantic_only"
        if any(
            flag in provided_flags
            for flag in {
                "--search-mode",
                "--retrieval-mode",
                "--disable-bm25",
                "--top-k",
                "--enable-reranking",
                "--reranking-mode",
                "--no-diversification",
                "--enable-hyde",
                "--mmr-lambda",
                "--overfetch-multiplier",
                "--max-chunks-per-source-page",
                "--max-chunks-per-source",
            }
        ):
            base_retrieval_options = dict(kwargs.get("retrieval_options", {}))
            for key, value in retrieval_options.items():
                base_retrieval_options[key] = value
            merged["retrieval_options"] = base_retrieval_options
        if diversity_sweep and any(
            flag in provided_flags
            for flag in {
                "--sweep-mmr-lambdas",
                "--sweep-overfetch-multipliers",
                "--sweep-max-chunks-per-source-page",
                "--sweep-max-chunks-per-source",
            }
        ):
            merged["diversity_sweep"] = diversity_sweep
        return merged

    if args.config:
        specs = resolve_experiment_runs(
            args.config,
            variant=args.variant,
            all_variants=args.all_variants,
        )
        if args.variant and not args.all_variants:
            specs = specs[-1:]
        exit_code = 0

        if args.parallel and len(specs) > 1:
            max_workers = args.max_workers or min(len(specs), 4)
            print(f"Running {len(specs)} variants in parallel with {max_workers} workers...")

            completed = _run_variants_parallel(
                specs,
                _apply_cli_overrides,
                max_workers=max_workers,
            )

            # Sort by original order and print results
            completed.sort(key=lambda x: x[0])
            baseline_result = None
            for idx, result_dict in completed:
                spec = specs[idx]
                variant_name = spec.get("variant_name") or spec.get("metadata", {}).get(
                    "name", "base"
                )
                print(f"\n--- Variant {idx}: {variant_name} ---")
                print(f"Status: {result_dict['status']}")
                if result_dict.get("run_dir"):
                    print(f"Run dir: {result_dict['run_dir']}")
                failures = result_dict.get("failed_thresholds", [])
                if failures:
                    print(f"Threshold failures: {len(failures)}")
                strict = _apply_cli_overrides(spec).get("fail_on_thresholds", False)
                if result_dict["status"] == "failed" or (strict and result_dict["status"] != "ok"):
                    exit_code = 1
                if baseline_result is None:
                    baseline_result = result_dict
        else:
            baseline_result = None
            for idx, spec in enumerate(specs):
                kwargs = _apply_cli_overrides(spec, idx)
                result = run_assessment_in_subprocess(kwargs)
                baseline: AssessmentResult | None = baseline_result if idx > 0 else None
                _print_assessment_result(result, baseline)
                if idx == 0:
                    baseline_result = result
                if result.status == "failed" or (
                    kwargs.get("fail_on_thresholds") and result.status != "ok"
                ):
                    exit_code = 1
        raise SystemExit(exit_code)

    result = run_assessment(
        artifact_dir=args.artifact_dir,
        name=args.name,
        dataset_path=args.dataset_path,
        review_manifest_path=args.review_manifest_path,
        index_snapshot_path=args.index_snapshot_path,
        top_k=args.top_k,
        max_synthetic_questions=args.max_synthetic_questions,
        disable_llm_generation=args.disable_llm_generation,
        disable_llm_judging=args.disable_llm_judging,
        include_answer_eval=args.include_answer_eval,
        sample_docs_per_source_type=args.sample_docs_per_source_type,
        seed=args.seed,
        max_queries=args.max_queries,
        sample_seed=args.sample_seed,
        reuse_cached_dataset=args.reuse_cached_dataset,
        force_rerun=args.force_rerun,
        fail_on_thresholds=args.fail_on_thresholds,
        thresholds_file=args.thresholds_file,
        dataset_split=args.dataset_split,
        min_label_confidence=args.min_label_confidence,
        retrieval_mode=args.retrieval_mode,
        disable_page_classification=args.disable_page_classification,
        disable_structured_chunking=args.disable_structured_chunking,
        disable_bm25=args.disable_bm25,
        export_failed_generations=args.export_failed_generations,
        retrieval_options=retrieval_options,
        run_retrieval_ablations=args.run_retrieval_ablations,
        run_hype_ablations=args.run_hype_ablations,
        run_keyword_ablations=args.run_keyword_ablations,
        run_reranking_ablations=args.run_reranking_ablations,
        run_diversity_sweep=args.run_diversity_sweep,
        diversity_sweep=diversity_sweep,
        execution_mode=args.execution_mode,
        generation_implementation=args.generation_implementation,
        harness=args.harness,
    )
    _print_assessment_result(result)
    raise SystemExit(
        1 if result.status == "failed" or (args.fail_on_thresholds and result.status != "ok") else 0
    )


if __name__ == "__main__":
    main()
