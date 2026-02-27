"""CLI entrypoint for pipeline quality assessment."""

import argparse
from typing import Any

from src.evals import run_assessment


def _parse_csv_floats(value: str | None) -> list[float] | None:
    if not value:
        return None
    return [float(x.strip()) for x in value.split(",") if x.strip()]


def _parse_csv_ints(value: str | None) -> list[int] | None:
    if not value:
        return None
    return [int(x.strip()) for x in value.split(",") if x.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate ingestion + retrieval pipeline quality")
    parser.add_argument("--artifact-dir", default="data/evals", help="Base directory for saved evaluation artifacts")
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
    parser.add_argument("--search-mode", default="hybrid", choices=["hybrid", "semantic_only", "keyword_only"])
    parser.add_argument("--no-diversification", action="store_true")
    parser.add_argument("--mmr-lambda", type=float, default=None)
    parser.add_argument("--overfetch-multiplier", type=int, default=None)
    parser.add_argument("--max-chunks-per-source-page", type=int, default=None)
    parser.add_argument("--max-chunks-per-source", type=int, default=None)
    parser.add_argument("--run-retrieval-ablations", action="store_true")
    parser.add_argument("--run-diversity-sweep", action="store_true")
    parser.add_argument("--sweep-mmr-lambdas", default=None, help="Comma-separated, e.g. 0.5,0.75,0.9")
    parser.add_argument("--sweep-overfetch-multipliers", default=None, help="Comma-separated ints")
    parser.add_argument("--sweep-max-chunks-per-source-page", default=None, help="Comma-separated ints")
    parser.add_argument("--sweep-max-chunks-per-source", default=None, help="Comma-separated ints")
    args = parser.parse_args()

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

    diversity_sweep = {
        "mmr_lambda_values": _parse_csv_floats(args.sweep_mmr_lambdas),
        "overfetch_multipliers": _parse_csv_ints(args.sweep_overfetch_multipliers),
        "max_chunks_per_source_page_values": _parse_csv_ints(args.sweep_max_chunks_per_source_page),
        "max_chunks_per_source_values": _parse_csv_ints(args.sweep_max_chunks_per_source),
    }
    diversity_sweep = {k: v for k, v in diversity_sweep.items() if v is not None}

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
        retrieval_options=retrieval_options,
        run_retrieval_ablations=args.run_retrieval_ablations,
        run_diversity_sweep=args.run_diversity_sweep,
        diversity_sweep=diversity_sweep,
    )
    print(f"Evaluation complete: {result.run_dir}")
    print(f"Status: {result.status}")
    if result.failed_thresholds:
        print(f"Threshold failures: {len(result.failed_thresholds)}")
    raise SystemExit(1 if result.status == 'failed' else 0)


if __name__ == "__main__":
    main()
