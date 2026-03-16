#!/usr/bin/env python3
"""Benchmark a single-query DeepEval evaluation run with cache visibility."""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path

from src.config import settings
from src.evals.assessment.answer_eval import evaluate_answers_deepeval


def _count_entries(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return 0
    entries = payload.get("entries", {})
    return len(entries) if isinstance(entries, dict) else 0


async def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark one DeepEval single-query run")
    parser.add_argument("query", help="Query to evaluate")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--cache-dir", default=settings.deepeval_cache_dir)
    parser.add_argument("--search-mode", default="rrf_hybrid")
    parser.add_argument("--no-cache", action="store_true", help="Disable caches for this run")
    parser.add_argument(
        "--compare-cold-warm",
        action="store_true",
        help="Run once without cache and once with cache for comparison",
    )
    args = parser.parse_args()

    cache_dir = Path(args.cache_dir)
    async def _run_once(use_cache: bool) -> dict:
        before = {
            "retrieval_cache_entries": _count_entries(cache_dir / "retrieval_cache.json"),
            "generation_cache_entries": _count_entries(cache_dir / "generation_cache.json"),
            "metric_cache_entries": _count_entries(cache_dir / "metric_cache.json"),
        }

        previous_answer_cache = settings.deepeval_answer_cache_enabled
        previous_metric_cache = settings.deepeval_metric_cache_enabled
        settings.deepeval_answer_cache_enabled = use_cache
        settings.deepeval_metric_cache_enabled = use_cache
        try:
            start = time.time()
            results, aggregate = await evaluate_answers_deepeval(
                [{"query_id": "benchmark_1", "query": args.query}],
                top_k=args.top_k,
                cache_dir=cache_dir,
                retrieval_options={"search_mode": args.search_mode},
                cache_namespace={"benchmark": True},
            )
            elapsed = round(time.time() - start, 3)
        finally:
            settings.deepeval_answer_cache_enabled = previous_answer_cache
            settings.deepeval_metric_cache_enabled = previous_metric_cache

        after = {
            "retrieval_cache_entries": _count_entries(cache_dir / "retrieval_cache.json"),
            "generation_cache_entries": _count_entries(cache_dir / "generation_cache.json"),
            "metric_cache_entries": _count_entries(cache_dir / "metric_cache.json"),
        }
        first = results[0] if results else {}
        return {
            "cache_enabled": use_cache,
            "elapsed_s": elapsed,
            "before": before,
            "after": after,
            "cache_delta": {key: after[key] - before[key] for key in before},
            "aggregate": aggregate,
            "metric_names": list(first.get("metrics", {}).keys()),
            "metric_timings_ms": {
                name: payload.get("elapsed_ms")
                for name, payload in first.get("metrics", {}).items()
            },
            "query_timings_ms": first.get("timings", {}),
            "cache_hits": first.get("cache", {}),
        }

    payload = {
        "query": args.query,
        "top_k": args.top_k,
        "search_mode": args.search_mode,
    }
    if args.compare_cold_warm:
        payload["cold_run"] = await _run_once(use_cache=False)
        payload["warm_run"] = await _run_once(use_cache=True)
    else:
        payload["run"] = await _run_once(use_cache=not args.no_cache)

    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
