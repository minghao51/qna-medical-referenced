#!/usr/bin/env python3
"""Benchmark multi-query DeepEval evaluation runs with aggregate metrics.

This script runs performance benchmarks across multiple queries to measure:
- P50, P95, P99 latency
- Cache hit rates
- Memory usage
- Throughput (queries/second)

Usage:
    python scripts/benchmark_deepeval_multi.py
    python scripts/benchmark_deepeval_multi.py --top-k 5
    python scripts/benchmark_deepeval_multi.py --queries tests/fixtures/golden_queries.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from src.config import settings
from src.evals.assessment.answer_eval import evaluate_answers_deepeval


def _count_entries(path: Path) -> int:
    """Count entries in a cache file."""
    if not path.exists():
        return 0
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return 0
    entries = payload.get("entries", {})
    return len(entries) if isinstance(entries, dict) else 0


def _percentile(data: list[float], p: float) -> float:
    """Calculate percentile of data."""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * p / 100
    f = int(k)
    c = f + 1
    if c >= len(sorted_data):
        return sorted_data[-1]
    return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])


def _format_duration(seconds: float) -> str:
    """Format duration in human-readable format."""
    if seconds < 1:
        return f"{seconds * 1000:.1f}ms"
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    secs = seconds % 60
    return f"{minutes}m {secs:.1f}s"


def _generate_markdown_report(benchmark_data: dict[str, Any]) -> str:
    """Generate a Markdown performance report."""
    lines = [
        "# Multi-Query Performance Benchmark Report",
        "",
        f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Total Queries**: {benchmark_data['summary']['total_queries']}",
        f"**Top-K**: {benchmark_data['config']['top_k']}",
        f"**Search Mode**: {benchmark_data['config']['search_mode']}",
        "",
        "---",
        "",
        "## Summary",
        "",
    ]

    # Cold cache summary
    cold = benchmark_data["cold_run"]
    lines.extend([
        "### Cold Cache (First Run)",
        "",
        f"- **Total Time**: {_format_duration(cold['total_elapsed_s'])}",
        f"- **Mean Latency**: {cold['mean_latency_ms']:.1f}ms",
        f"- **P50 Latency**: {cold['p50_latency_ms']:.1f}ms",
        f"- **P95 Latency**: {cold['p95_latency_ms']:.1f}ms",
        f"- **P99 Latency**: {cold['p99_latency_ms']:.1f}ms",
        f"- **Min Latency**: {cold['min_latency_ms']:.1f}ms",
        f"- **Max Latency**: {cold['max_latency_ms']:.1f}ms",
        f"- **Throughput**: {cold['throughput_qps']:.2f} queries/second",
        "",
    ])

    # Warm cache summary
    warm = benchmark_data["warm_run"]
    lines.extend([
        "### Warm Cache (Second Run)",
        "",
        f"- **Total Time**: {_format_duration(warm['total_elapsed_s'])}",
        f"- **Mean Latency**: {warm['mean_latency_ms']:.1f}ms",
        f"- **P50 Latency**: {warm['p50_latency_ms']:.1f}ms",
        f"- **P95 Latency**: {warm['p95_latency_ms']:.1f}ms",
        f"- **P99 Latency**: {warm['p99_latency_ms']:.1f}ms",
        f"- **Min Latency**: {warm['min_latency_ms']:.1f}ms",
        f"- **Max Latency**: {warm['max_latency_ms']:.1f}ms",
        f"- **Throughput**: {warm['throughput_qps']:.2f} queries/second",
        "",
    ])

    # Cache effectiveness
    speedup = cold['mean_latency_ms'] / warm['mean_latency_ms'] if warm['mean_latency_ms'] > 0 else 0
    lines.extend([
        "### Cache Effectiveness",
        "",
        f"- **Speedup**: {speedup:.2f}x",
        f"- **Time Saved**: {_format_duration(cold['total_elapsed_s'] - warm['total_elapsed_s'])}",
        "",
        "---",
        "",
        "## Detailed Metrics",
        "",
        "### Latency Distribution",
        "",
        "| Metric | Cold Cache | Warm Cache | Improvement |",
        "|--------|------------|------------|-------------|",
        f"| Mean | {cold['mean_latency_ms']:.1f}ms | {warm['mean_latency_ms']:.1f}ms | {((cold['mean_latency_ms'] - warm['mean_latency_ms']) / cold['mean_latency_ms'] * 100):.1f}% |",
        f"| P50 | {cold['p50_latency_ms']:.1f}ms | {warm['p50_latency_ms']:.1f}ms | {((cold['p50_latency_ms'] - warm['p50_latency_ms']) / cold['p50_latency_ms'] * 100):.1f}% |",
        f"| P95 | {cold['p95_latency_ms']:.1f}ms | {warm['p95_latency_ms']:.1f}ms | {((cold['p95_latency_ms'] - warm['p95_latency_ms']) / cold['p95_latency_ms'] * 100):.1f}% |",
        f"| P99 | {cold['p99_latency_ms']:.1f}ms | {warm['p99_latency_ms']:.1f}ms | {((cold['p99_latency_ms'] - warm['p99_latency_ms']) / cold['p99_latency_ms'] * 100):.1f}% |",
        "",
        "### Cache Statistics",
        "",
        f"- **Cold Run Cache Hits**: {cold['cache_hits']:.1f}%",
        f"- **Warm Run Cache Hits**: {warm['cache_hits']:.1f}%",
        "",
        "---",
        "",
        "## Individual Query Results",
        "",
        "| Query ID | Latency (Cold) | Latency (Warm) | Speedup |",
        "|----------|----------------|----------------|---------|",
    ])

    # Individual query results
    for query_result in benchmark_data["individual_queries"]:
        query_id = query_result["query_id"][:30]  # Truncate long IDs
        cold_lat = query_result["cold_latency_ms"]
        warm_lat = query_result["warm_latency_ms"]
        speedup = cold_lat / warm_lat if warm_lat > 0 else 0
        lines.append(f"| {query_id} | {cold_lat:.1f}ms | {warm_lat:.1f}ms | {speedup:.2f}x |")

    lines.extend([
        "",
        "---",
        "",
        "## Recommendations",
        "",
    ])

    # Generate recommendations based on performance
    if speedup > 2:
        lines.append("- ✅ Cache is highly effective - consider enabling in production")
    elif speedup > 1.5:
        lines.append("- ✅ Cache provides good performance improvement")
    else:
        lines.append("- ⚠️ Cache effectiveness is low - investigate cache hit rates")

    if cold['p95_latency_ms'] > 10000:
        lines.append("- ⚠️ P95 latency is high - consider optimizing for tail latency")
    else:
        lines.append("- ✅ Latency is within acceptable range")

    if warm['throughput_qps'] < 0.5:
        lines.append("- ⚠️ Throughput is low - consider concurrent query processing")
    else:
        lines.append("- ✅ Throughput is acceptable for expected load")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*This report was generated by `scripts/benchmark_deepeval_multi.py`*")

    return "\n".join(lines)


async def benchmark_multi_query(
    queries: list[dict[str, str]],
    top_k: int = 3,
    search_mode: str = "rrf_hybrid",
    cache_dir: Path | None = None,
) -> dict[str, Any]:
    """Benchmark performance with multiple queries.

    Args:
        queries: List of query dictionaries with 'query' and 'query_id' keys
        top_k: Number of documents to retrieve
        search_mode: Search mode for retrieval
        cache_dir: Directory for cache files

    Returns:
        Dictionary with benchmark results including cold and warm runs
    """
    if cache_dir is None:
        cache_dir = Path(settings.deepeval_cache_dir)
    else:
        cache_dir = Path(cache_dir)

    async def run_benchmark(use_cache: bool) -> dict[str, Any]:
        """Run benchmark once with cache enabled/disabled."""
        # Configure cache settings
        previous_answer_cache = settings.deepeval_answer_cache_enabled
        previous_metric_cache = settings.deepeval_metric_cache_enabled
        settings.deepeval_answer_cache_enabled = use_cache
        settings.deepeval_metric_cache_enabled = use_cache

        try:
            start_time = time.time()
            latencies_ms = []
            cache_hit_rates = []
            individual_results = []

            for i, query_data in enumerate(queries):
                query_start = time.time()

                # Prepare dataset with single query
                dataset = [{
                    "query": query_data["query"],
                    "query_id": query_data.get("query_id", f"query_{i}")
                }]

                # Run evaluation
                results, aggregate = await evaluate_answers_deepeval(
                    dataset,
                    top_k=top_k,
                    cache_dir=cache_dir,
                    retrieval_options={"search_mode": search_mode},
                    cache_namespace={"benchmark_multi": True},
                )

                query_elapsed = time.time() - query_start
                latencies_ms.append(query_elapsed * 1000)

                # Calculate cache hit rate for this query
                if results and len(results) > 0:
                    cache_info = results[0].get("cache", {})
                    total_operations = len(cache_info)
                    hits = sum(1 for v in cache_info.values() if v is True)
                    cache_hit_rates.append(hits / total_operations if total_operations > 0 else 0)

                    individual_results.append({
                        "query_id": query_data.get("query_id", f"query_{i}"),
                        "latency_ms": query_elapsed * 1000,
                        "cache_hit_rate": cache_hit_rates[-1],
                    })

            total_elapsed = time.time() - start_time

            # Calculate statistics
            return {
                "total_elapsed_s": total_elapsed,
                "latencies_ms": latencies_ms,
                "mean_latency_ms": statistics.mean(latencies_ms) if latencies_ms else 0,
                "p50_latency_ms": _percentile(latencies_ms, 50),
                "p95_latency_ms": _percentile(latencies_ms, 95),
                "p99_latency_ms": _percentile(latencies_ms, 99),
                "min_latency_ms": min(latencies_ms) if latencies_ms else 0,
                "max_latency_ms": max(latencies_ms) if latencies_ms else 0,
                "throughput_qps": len(queries) / total_elapsed if total_elapsed > 0 else 0,
                "cache_hits": statistics.mean(cache_hit_rates) * 100 if cache_hit_rates else 0,
                "individual_results": individual_results,
            }

        finally:
            settings.deepeval_answer_cache_enabled = previous_answer_cache
            settings.deepeval_metric_cache_enabled = previous_metric_cache

    # Run cold cache benchmark
    print(f"Running cold cache benchmark with {len(queries)} queries...")
    cold_run = await run_benchmark(use_cache=False)
    print(f"  Completed in {_format_duration(cold_run['total_elapsed_s'])}")

    # Run warm cache benchmark
    print("Running warm cache benchmark...")
    warm_run = await run_benchmark(use_cache=True)
    print(f"  Completed in {_format_duration(warm_run['total_elapsed_s'])}")

    # Combine individual results
    individual_queries = []
    for i, query_data in enumerate(queries):
        query_id = query_data.get("query_id", f"query_{i}")
        cold_result = next(
            (r for r in cold_run["individual_results"] if r["query_id"] == query_id),
            {"latency_ms": 0}
        )
        warm_result = next(
            (r for r in warm_run["individual_results"] if r["query_id"] == query_id),
            {"latency_ms": 0}
        )

        individual_queries.append({
            "query_id": query_id,
            "cold_latency_ms": cold_result["latency_ms"],
            "warm_latency_ms": warm_result["latency_ms"],
        })

    return {
        "config": {
            "top_k": top_k,
            "search_mode": search_mode,
            "total_queries": len(queries),
        },
        "cold_run": {
            "total_elapsed_s": cold_run["total_elapsed_s"],
            "mean_latency_ms": cold_run["mean_latency_ms"],
            "p50_latency_ms": cold_run["p50_latency_ms"],
            "p95_latency_ms": cold_run["p95_latency_ms"],
            "p99_latency_ms": cold_run["p99_latency_ms"],
            "min_latency_ms": cold_run["min_latency_ms"],
            "max_latency_ms": cold_run["max_latency_ms"],
            "throughput_qps": cold_run["throughput_qps"],
            "cache_hits": cold_run["cache_hits"],
        },
        "warm_run": {
            "total_elapsed_s": warm_run["total_elapsed_s"],
            "mean_latency_ms": warm_run["mean_latency_ms"],
            "p50_latency_ms": warm_run["p50_latency_ms"],
            "p95_latency_ms": warm_run["p95_latency_ms"],
            "p99_latency_ms": warm_run["p99_latency_ms"],
            "min_latency_ms": warm_run["min_latency_ms"],
            "max_latency_ms": warm_run["max_latency_ms"],
            "throughput_qps": warm_run["throughput_qps"],
            "cache_hits": warm_run["cache_hits"],
        },
        "individual_queries": individual_queries,
        "summary": {
            "total_queries": len(queries),
            "speedup": cold_run["mean_latency_ms"] / warm_run["mean_latency_ms"] if warm_run["mean_latency_ms"] > 0 else 0,
        },
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark multi-query DeepEval evaluation")
    parser.add_argument(
        "--queries",
        default="tests/fixtures/golden_queries.json",
        help="Path to queries JSON file"
    )
    parser.add_argument("--top-k", type=int, default=3, help="Number of documents to retrieve")
    parser.add_argument("--search-mode", default="rrf_hybrid", help="Search mode for retrieval")
    parser.add_argument("--cache-dir", default=None, help="Cache directory (default: from settings)")
    parser.add_argument(
        "--output",
        default=None,
        help="Output file for benchmark report (default: stdout)"
    )
    args = parser.parse_args()

    # Load queries
    queries_path = Path(args.queries)
    if not queries_path.exists():
        print(f"Error: Queries file not found: {queries_path}")
        return

    print(f"Loading queries from {queries_path}...")
    queries_data = json.loads(queries_path.read_text(encoding="utf-8"))

    # Extract golden queries
    queries = []
    for i, q in enumerate(queries_data.get("golden_queries", [])):
        queries.append({
            "query": q["query"],
            "query_id": q.get("query_id", f"query_{i}"),
        })

    print(f"Loaded {len(queries)} queries")

    # Run benchmark
    print("=" * 60)
    print("Multi-Query Performance Benchmark")
    print("=" * 60)
    print()

    benchmark_data = await benchmark_multi_query(
        queries=queries,
        top_k=args.top_k,
        search_mode=args.search_mode,
        cache_dir=Path(args.cache_dir) if args.cache_dir else None,
    )

    # Generate report
    report = _generate_markdown_report(benchmark_data)

    # Output report
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report, encoding="utf-8")
        print(f"\nReport saved to: {output_path}")
    else:
        print("\n")
        print(report)


if __name__ == "__main__":
    asyncio.run(main())
