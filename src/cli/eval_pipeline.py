"""CLI entrypoint for pipeline quality assessment."""

import argparse
import json
import sys
from typing import Any

from src.evals import run_assessment
from src.experiments import (
    build_run_assessment_kwargs,
    compute_retrieval_delta,
    resolve_experiment_runs,
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate ingestion + retrieval pipeline quality")
    parser.add_argument("--config", default=None, help="Versioned experiment YAML path")
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
    parser.add_argument("--top-k", type=int, default=5, help="Retrieval top-k")
    parser.add_argument("--max-synthetic-questions", type=int, default=40)
    parser.add_argument("--disable-llm-generation", action="store_true")
    parser.add_argument("--disable-llm-judging", action="store_true")
    parser.add_argument("--include-answer-eval", action="store_true")
    parser.add_argument("--sample-docs-per-source-type", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--fail-on-thresholds", action="store_true")
    parser.add_argument("--thresholds-file", default=None)
    parser.add_argument("--dataset-split", default=None, choices=["dev", "test", "regression"])
    parser.add_argument("--min-label-confidence", default="low", choices=["low", "medium", "high"])
    parser.add_argument(
        "--retrieval-mode",
        default="rrf_hybrid",
        choices=["rrf_hybrid", "legacy_hybrid", "semantic_only", "bm25_only"],
    )
    parser.add_argument("--disable-page-classification", action="store_true")
    parser.add_argument("--disable-structured-chunking", action="store_true")
    parser.add_argument("--disable-bm25", action="store_true")
    parser.add_argument("--export-failed-generations", action="store_true")
    parser.add_argument(
        "--search-mode",
        default="rrf_hybrid",
        choices=[
            "rrf_hybrid",
            "legacy_hybrid",
            "semantic_only",
            "bm25_only",
            "keyword_only",
            "hybrid",
        ],
    )
    parser.add_argument("--no-diversification", action="store_true")
    parser.add_argument("--mmr-lambda", type=float, default=None)
    parser.add_argument("--overfetch-multiplier", type=int, default=None)
    parser.add_argument("--max-chunks-per-source-page", type=int, default=None)
    parser.add_argument("--max-chunks-per-source", type=int, default=None)
    parser.add_argument("--run-retrieval-ablations", action="store_true")
    parser.add_argument("--run-diversity-sweep", action="store_true")
    parser.add_argument(
        "--sweep-mmr-lambdas", default=None, help="Comma-separated, e.g. 0.5,0.75,0.9"
    )
    parser.add_argument("--sweep-overfetch-multipliers", default=None, help="Comma-separated ints")
    parser.add_argument(
        "--sweep-max-chunks-per-source-page", default=None, help="Comma-separated ints"
    )
    parser.add_argument("--sweep-max-chunks-per-source", default=None, help="Comma-separated ints")
    args = parser.parse_args()
    provided_flags = _provided_flags(sys.argv[1:])

    diversity_sweep = {
        "mmr_lambda_values": _parse_csv_floats(args.sweep_mmr_lambdas),
        "overfetch_multipliers": _parse_csv_ints(args.sweep_overfetch_multipliers),
        "max_chunks_per_source_page_values": _parse_csv_ints(args.sweep_max_chunks_per_source_page),
        "max_chunks_per_source_values": _parse_csv_ints(args.sweep_max_chunks_per_source),
    }
    diversity_sweep = {k: v for k, v in diversity_sweep.items() if v is not None}
    retrieval_options: dict[str, Any] = {"search_mode": args.search_mode}
    if args.no_diversification:
        retrieval_options["enable_diversification"] = False
    if args.mmr_lambda is not None:
        retrieval_options["mmr_lambda"] = args.mmr_lambda
    if args.overfetch_multiplier is not None:
        retrieval_options["overfetch_multiplier"] = args.overfetch_multiplier
    if args.max_chunks_per_source_page is not None:
        retrieval_options["max_chunks_per_source_page"] = args.max_chunks_per_source_page
    if args.max_chunks_per_source is not None:
        retrieval_options["max_chunks_per_source"] = args.max_chunks_per_source

    def _apply_cli_overrides(kwargs: dict[str, Any]) -> dict[str, Any]:
        merged = dict(kwargs)
        scalar_overrides = {
            "--artifact-dir": ("artifact_dir", args.artifact_dir),
            "--name": ("name", args.name),
            "--dataset-path": ("dataset_path", args.dataset_path),
            "--top-k": ("top_k", args.top_k),
            "--max-synthetic-questions": ("max_synthetic_questions", args.max_synthetic_questions),
            "--sample-docs-per-source-type": (
                "sample_docs_per_source_type",
                args.sample_docs_per_source_type,
            ),
            "--seed": ("seed", args.seed),
            "--thresholds-file": ("thresholds_file", args.thresholds_file),
            "--dataset-split": ("dataset_split", args.dataset_split),
            "--min-label-confidence": ("min_label_confidence", args.min_label_confidence),
            "--retrieval-mode": ("retrieval_mode", args.retrieval_mode),
        }
        for flag, (key, value) in scalar_overrides.items():
            if flag in provided_flags:
                merged[key] = value
        bool_overrides = {
            "--disable-llm-generation": ("disable_llm_generation", args.disable_llm_generation),
            "--disable-llm-judging": ("disable_llm_judging", args.disable_llm_judging),
            "--include-answer-eval": ("include_answer_eval", args.include_answer_eval),
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
            "--run-diversity-sweep": ("run_diversity_sweep", args.run_diversity_sweep),
        }
        for flag, (key, value) in bool_overrides.items():
            if flag in provided_flags:
                merged[key] = value
        if any(
            flag in provided_flags
            for flag in {
                "--search-mode",
                "--no-diversification",
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
        baseline_result = None
        baseline_metrics = None
        exit_code = 0
        for idx, spec in enumerate(specs):
            kwargs = _apply_cli_overrides(build_run_assessment_kwargs(spec))
            result = run_assessment(**kwargs)
            print(f"Evaluation complete: {result.run_dir}")
            print(f"Status: {result.status}")
            if result.failed_thresholds:
                print(f"Threshold failures: {len(result.failed_thresholds)}")
            if idx == 0:
                baseline_result = result
                baseline_metrics = result.summary.get("retrieval_metrics", {})
            elif baseline_result and baseline_metrics:
                delta = compute_retrieval_delta(
                    baseline_metrics,
                    result.summary.get("retrieval_metrics", {}),
                )
                comparison_path = result.run_dir / "comparison_to_baseline.json"
                comparison_path.write_text(
                    json.dumps(
                        {
                            "baseline_run_dir": str(baseline_result.run_dir),
                            "baseline_name": specs[0]["metadata"]["name"],
                            "delta": delta,
                        },
                        indent=2,
                    ),
                    encoding="utf-8",
                )
                print(f"Baseline delta: {comparison_path}")
            if result.status == "failed":
                exit_code = 1
        raise SystemExit(exit_code)

    result = run_assessment(
        artifact_dir=args.artifact_dir,
        name=args.name,
        dataset_path=args.dataset_path,
        top_k=args.top_k,
        max_synthetic_questions=args.max_synthetic_questions,
        disable_llm_generation=args.disable_llm_generation,
        disable_llm_judging=args.disable_llm_judging,
        include_answer_eval=args.include_answer_eval,
        sample_docs_per_source_type=args.sample_docs_per_source_type,
        seed=args.seed,
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
        run_diversity_sweep=args.run_diversity_sweep,
        diversity_sweep=diversity_sweep,
    )
    print(f"Evaluation complete: {result.run_dir}")
    print(f"Status: {result.status}")
    if result.failed_thresholds:
        print(f"Threshold failures: {len(result.failed_thresholds)}")
    raise SystemExit(1 if result.status == "failed" else 0)


if __name__ == "__main__":
    main()
