"""Service helpers for evaluation artifact discovery and loading."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from src.evals.assessment.l6_contract import (
    L6_ANSWER_QUALITY_ROWS,
    SUMMARY_L6_METRICS_KEY,
)
from src.services.base_service import BaseService


@lru_cache(maxsize=256)
def _read_json_cached(path_str: str, mtime_ns: int, size: int) -> Any:
    del mtime_ns, size
    return json.loads(Path(path_str).read_text(encoding="utf-8"))


class EvaluationService(BaseService):
    """Load and shape evaluation artifacts from the filesystem."""

    def __init__(
        self,
        evals_dir: Path,
        latest_pointer: Path,
        comprehensive_ablation_dir: Path | None = None,
    ) -> None:
        super().__init__()
        self._evals_dir = evals_dir
        self._latest_pointer = latest_pointer
        self._comprehensive_ablation_dir = (
            comprehensive_ablation_dir or Path("data/evals_comprehensive_ablation")
        )

    def list_run_dirs(self) -> list[Path]:
        if not self._evals_dir.exists():
            return []
        return sorted(
            [
                path
                for path in self._evals_dir.iterdir()
                if path.is_dir() and "_" in path.name and path.name[0].isdigit()
            ],
            reverse=True,
        )

    def read_json_if_exists(self, path: Path) -> Any:
        if not path.exists():
            return {}
        try:
            stat = path.stat()
            return _read_json_cached(str(path.resolve()), stat.st_mtime_ns, stat.st_size)
        except Exception as exc:
            self.logger.warning("Failed to read JSON from %s: %s", path, exc)
            return {}

    def read_retrieval_metrics(self, run_dir: Path) -> dict[str, Any]:
        retrieval = self.read_json_if_exists(run_dir / "retrieval_metrics.json")
        return retrieval if isinstance(retrieval, dict) else {}

    def read_summary(self, run_dir: Path) -> dict[str, Any]:
        summary = self.read_json_if_exists(run_dir / "summary.json")
        return summary if isinstance(summary, dict) else {}

    def is_valid_local_run(self, run_dir: Path) -> bool:
        if not (run_dir / "summary.json").exists():
            return False
        if not (run_dir / "retrieval_metrics.json").exists():
            return False
        retrieval = self.read_retrieval_metrics(run_dir)
        query_count = retrieval.get("query_count")
        return isinstance(query_count, (int, float)) and query_count > 0

    def get_latest_run_dir(self) -> Path | None:
        if self._latest_pointer.exists():
            run_dir = Path(self._latest_pointer.read_text(encoding="utf-8").strip())
            if run_dir.exists() and self.is_valid_local_run(run_dir):
                return run_dir
        for run_dir in self.list_run_dirs():
            if self.is_valid_local_run(run_dir):
                return run_dir
        return None

    def get_latest_existing_run_dir(self) -> Path | None:
        if self._latest_pointer.exists():
            run_dir = Path(self._latest_pointer.read_text(encoding="utf-8").strip())
            if run_dir.exists():
                return run_dir
        runs = self.list_run_dirs()
        return runs[0] if runs else None

    def get_all_runs(self) -> list[dict[str, Any]]:
        result = []
        for run_dir in self.list_run_dirs():
            if not self.is_valid_local_run(run_dir):
                continue
            try:
                summary = self.read_summary(run_dir)
                result.append(
                    {
                        "run_dir": str(run_dir.name),
                        "status": summary.get("status"),
                        "duration_s": summary.get("duration_s"),
                        "failed_thresholds_count": summary.get("failed_thresholds_count"),
                        "dedup": summary.get("dedup", {}),
                        "source": "local",
                        "tracking": summary.get("tracking", {}),
                    }
                )
            except Exception as exc:
                self.logger.debug("Failed to read summary for run %s: %s", run_dir.name, exc)
                result.append({"run_dir": str(run_dir.name), "status": "error", "source": "local"})
        return result

    def read_failed_thresholds(self, run_dir: Path) -> list[dict[str, Any]]:
        summary = self.read_summary(run_dir)
        explicit = summary.get("failed_thresholds")
        if isinstance(explicit, list):
            return [item for item in explicit if isinstance(item, dict)]

        step_findings = self.read_json_if_exists(run_dir / "step_findings.json")
        findings: list[dict[str, Any]] = step_findings if isinstance(step_findings, list) else []
        threshold_findings = []
        for finding in findings:
            if not isinstance(finding, dict):
                continue
            if finding.get("stage") != "threshold":
                continue
            threshold_findings.append(
                {
                    "metric": finding.get("metric"),
                    "value": finding.get("value"),
                    "threshold_op": finding.get("threshold_op"),
                    "threshold_value": finding.get("threshold_value"),
                    "message": finding.get("message"),
                    "severity": finding.get("severity"),
                }
            )
        return threshold_findings

    @staticmethod
    def extract_experiment_config(manifest: dict[str, Any] | None) -> dict[str, Any]:
        if not manifest:
            return {}
        config = manifest.get("config")
        if not isinstance(config, dict):
            return {}
        experiment_config = config.get("experiment_config")
        return experiment_config if isinstance(experiment_config, dict) else {}

    @staticmethod
    def normalize_ablation_payload(payload: Any) -> dict[str, Any]:
        if isinstance(payload, dict) and isinstance(payload.get("ablation_runs"), list):
            return payload
        if not isinstance(payload, dict):
            return {"ablation_runs": [], "message": "No ablation results available"}

        preferred_baselines = ("rrf_hybrid",)
        baseline_strategy = next(
            (strategy for strategy in preferred_baselines if strategy in payload),
            next(iter(payload), None),
        )
        ablation_runs = []
        for strategy, metrics in payload.items():
            if not isinstance(metrics, dict):
                continue
            ablation_runs.append(
                {
                    "strategy": strategy,
                    "hit_rate_at_k": metrics.get("hit_rate_at_k", 0),
                    "mrr": metrics.get("mrr", 0),
                    "ndcg_at_k": metrics.get("ndcg_at_k", 0),
                    "latency_p50_ms": metrics.get("latency_p50_ms"),
                    "is_baseline": strategy == baseline_strategy,
                }
            )
        return {"ablation_runs": ablation_runs}

    def local_history_runs(self, limit: int) -> list[dict[str, Any]]:
        runs = [run_dir for run_dir in self.list_run_dirs() if self.is_valid_local_run(run_dir)][:limit]
        result_runs = []
        for run_dir in runs:
            summary = self.read_summary(run_dir)
            retrieval = self.read_retrieval_metrics(run_dir)
            manifest = self.read_json_if_exists(run_dir / "manifest.json")
            experiment_cfg = self.extract_experiment_config(manifest)
            l6_metrics = summary.get(SUMMARY_L6_METRICS_KEY, {})
            result_runs.append(
                {
                    "run_dir": str(run_dir.name),
                    "timestamp": run_dir.name.split("_")[0] if "_" in run_dir.name else "",
                    "status": summary.get("status"),
                    "duration_s": summary.get("duration_s", 0),
                    "failed_thresholds_count": summary.get("failed_thresholds_count", 0),
                    "retrieval_metrics": {
                        "hit_rate_at_k": retrieval.get("hit_rate_at_k", 0),
                        "mrr": retrieval.get("mrr", 0),
                        "ndcg_at_k": retrieval.get("ndcg_at_k", 0),
                        "latency_p50_ms": retrieval.get("latency_p50_ms", 0),
                        "latency_p95_ms": retrieval.get("latency_p95_ms", 0),
                        "precision_at_k": retrieval.get("precision_at_k", 0),
                        "recall_at_k": retrieval.get("recall_at_k", 0),
                        "hyde_enabled": retrieval.get("hyde_enabled", False),
                        "hyde_queries_count": retrieval.get("hyde_queries_count", 0),
                        "hyde_hit_rate": retrieval.get("hyde_hit_rate"),
                        "hyde_mrr": retrieval.get("hyde_mrr"),
                        "hyde_source_hit_rate": retrieval.get("hyde_source_hit_rate"),
                    },
                    "l6_answer_quality_metrics": l6_metrics if isinstance(l6_metrics, dict) else {},
                    "source": "local",
                    "experiment_name": (experiment_cfg.get("metadata") or {}).get("name"),
                    "variant_name": experiment_cfg.get("variant_name"),
                    "index_config_hash": (manifest.get("experiment") or {}).get("index_config_hash"),
                    "wandb_url": (((summary.get("tracking") or {}).get("wandb") or {}).get("run_url")),
                    "wandb_run_id": (((summary.get("tracking") or {}).get("wandb") or {}).get("run_id")),
                    "dedup": summary.get("dedup", {}),
                    "tracking": summary.get("tracking", {}),
                }
            )
        return result_runs

    @staticmethod
    def aggregate_history_summary(runs: list[dict[str, Any]]) -> dict[str, Any]:
        metrics_tracking: dict[str, list[float]] = {
            "hit_rate_at_k": [],
            "mrr": [],
            "ndcg_at_k": [],
            "latency_p50_ms": [],
            "latency_p95_ms": [],
            "duration_s": [],
        }
        source_breakdown: dict[str, int] = {}
        for run in runs:
            source = str(run.get("source") or "unknown")
            source_breakdown[source] = source_breakdown.get(source, 0) + 1
            retrieval = dict(run.get("retrieval_metrics") or {})
            for key in ("hit_rate_at_k", "mrr", "ndcg_at_k", "latency_p50_ms", "latency_p95_ms"):
                value = retrieval.get(key)
                if isinstance(value, (int, float)):
                    metrics_tracking[key].append(value)
            duration = run.get("duration_s")
            if isinstance(duration, (int, float)):
                metrics_tracking["duration_s"].append(duration)
        return {
            "total_runs": len(runs),
            "avg_hit_rate": sum(metrics_tracking["hit_rate_at_k"]) / len(metrics_tracking["hit_rate_at_k"])
            if metrics_tracking["hit_rate_at_k"]
            else 0,
            "avg_mrr": sum(metrics_tracking["mrr"]) / len(metrics_tracking["mrr"])
            if metrics_tracking["mrr"]
            else 0,
            "avg_latency_p50": sum(metrics_tracking["latency_p50_ms"])
            / len(metrics_tracking["latency_p50_ms"])
            if metrics_tracking["latency_p50_ms"]
            else 0,
            "avg_duration": sum(metrics_tracking["duration_s"]) / len(metrics_tracking["duration_s"])
            if metrics_tracking["duration_s"]
            else 0,
            "sources": source_breakdown,
        }

    def load_run_payload(self, run_dir: Path) -> dict[str, Any]:
        result: dict[str, Any] = {"run_dir": str(run_dir.name)}

        summary = self.read_json_if_exists(run_dir / "summary.json")
        step_metrics = self.read_json_if_exists(run_dir / "step_metrics.json")
        retrieval_metrics = self.read_json_if_exists(run_dir / "retrieval_metrics.json")
        manifest = self.read_json_if_exists(run_dir / "manifest.json")

        if isinstance(summary, dict) and summary:
            result["summary"] = summary
        if isinstance(step_metrics, dict) and step_metrics:
            result["step_metrics"] = step_metrics
        if isinstance(retrieval_metrics, dict) and retrieval_metrics:
            result["retrieval_metrics"] = retrieval_metrics
        if isinstance(manifest, dict) and manifest:
            result["manifest"] = manifest
            experiment_cfg = self.extract_experiment_config(manifest)
            if experiment_cfg:
                result["experiment_config"] = {
                    "ingestion": experiment_cfg.get("ingestion"),
                    "retrieval": experiment_cfg.get("retrieval"),
                    "metadata": experiment_cfg.get("metadata"),
                }
        result["failed_thresholds"] = self.read_failed_thresholds(run_dir)
        return result

    def load_latest_evaluation(self) -> dict[str, Any]:
        run_dir = self.get_latest_run_dir()
        if run_dir is None:
            raise FileNotFoundError("No evaluation runs found")
        return self.load_run_payload(run_dir)

    def load_evaluation_run(self, run_dir_name: str) -> dict[str, Any]:
        target_dir = self._evals_dir / run_dir_name
        if not target_dir.exists():
            raise FileNotFoundError(f"Run directory not found: {run_dir_name}")
        return self.load_run_payload(target_dir)

    def load_ablation_results(self) -> dict[str, Any]:
        run_dir = self.get_latest_existing_run_dir()
        if run_dir is None:
            raise FileNotFoundError("No evaluation runs found")

        candidate_paths = [run_dir / "ablation_results.json", run_dir / "retrieval_ablations.json"]
        ablation_path = next((path for path in candidate_paths if path.exists()), None)
        if ablation_path is None:
            return {"ablation_runs": [], "message": "No ablation results available"}

        payload = self.read_json_if_exists(ablation_path)
        if not payload and ablation_path.exists() and ablation_path.stat().st_size > 0:
            raise ValueError("Failed to load ablation results")
        return self.normalize_ablation_payload(payload)

    def load_full_ablation_results(self) -> dict[str, Any]:
        ablation_dir = self._comprehensive_ablation_dir
        if not ablation_dir.exists():
            return {"runs": [], "message": "No ablation results available"}

        min_clean_run_date = "20260404"
        runs = []
        for run_dir in sorted(ablation_dir.iterdir()):
            if not run_dir.is_dir():
                continue
            run_prefix = run_dir.name.split("T", 1)[0]
            if len(run_prefix) != 8 or not run_prefix.isdigit() or run_prefix < min_clean_run_date:
                continue

            manifest_path = run_dir / "manifest.json"
            metrics_path = run_dir / "retrieval_metrics.json"
            if not manifest_path.exists() or not metrics_path.exists():
                continue

            manifest = self.read_json_if_exists(manifest_path)
            metrics = self.read_json_if_exists(metrics_path)
            if not isinstance(manifest, dict) or not isinstance(metrics, dict):
                self.logger.warning("Failed to load run %s", run_dir.name)
                continue

            variant = manifest.get("experiment", {}).get("variant") or manifest.get("variant_name")
            if not variant:
                parts = run_dir.name.split("Z_", 1)
                variant = parts[1] if len(parts) > 1 else run_dir.name

            idx_stats = manifest.get("index_preparation", {}).get("indexing_stats", {})
            runs.append(
                {
                    "variant": variant,
                    "run_dir": run_dir.name,
                    "chunks_attempted": idx_stats.get("attempted"),
                    "chunks_inserted": idx_stats.get("inserted"),
                    "chunks_duplicate": idx_stats.get("skipped_duplicate_content"),
                    "ndcg_at_k": metrics.get("ndcg_at_k"),
                    "mrr": metrics.get("mrr"),
                    "hit_rate_at_k": metrics.get("hit_rate_at_k"),
                    "precision_at_k": metrics.get("precision_at_k"),
                    "recall_at_k": metrics.get("recall_at_k"),
                    "latency_p50_ms": metrics.get("latency_p50_ms"),
                }
            )

        runs.sort(key=lambda run: run.get("ndcg_at_k") or 0, reverse=True)

        baseline_ndcg = next(
            (run.get("ndcg_at_k") for run in runs if run.get("variant") == "baseline"),
            None,
        )
        if baseline_ndcg is not None:
            for run in runs:
                ndcg = run.get("ndcg_at_k")
                if ndcg is not None:
                    run["delta_ndcg"] = round(ndcg - baseline_ndcg, 4)

        dimensions = {
            "pdf_extraction": [
                run for run in runs if run["variant"] in ("baseline", "pdf_pymupdf", "pdf_pymupdf_camelot")
            ],
            "html_extraction": [run for run in runs if run["variant"].startswith("html_")],
            "chunking_strategy": [
                run
                for run in runs
                if run["variant"].startswith("chunk_") and not run["variant"].startswith("chunksize_")
            ],
            "chunk_size": [run for run in runs if run["variant"].startswith("chunksize_")],
            "retrieval": [run for run in runs if run["variant"].startswith("retrieval_")],
            "combined": [run for run in runs if "pymupdf_semantic_hybrid" in run["variant"]],
        }

        findings = [
            {
                "title": "Hybrid RRF retrieval is critical",
                "detail": "Single-method retrieval drops 8-9% NDCG. Hybrid RRF (semantic + BM25) is essential.",
                "impact": "high",
            },
            {
                "title": "PyMuPDF + Chonkie Semantic is the winning combo",
                "detail": "PyMuPDF adds +0.4%, Chonkie Semantic adds +0.7%. Together with hybrid RRF: NDCG=0.9976.",
                "impact": "high",
            },
            {
                "title": "HTML extraction doesn't matter",
                "detail": "All HTML strategies fall back to BeautifulSoup for this corpus. Keep trafilatura_bs (fastest).",
                "impact": "low",
            },
            {
                "title": "Chunk size 1024 hurts",
                "detail": "Too much context per chunk reduces precision by 0.7%. Sweet spot: 384-512 tokens.",
                "impact": "medium",
            },
            {
                "title": "Camelot tables add no value",
                "detail": "Identical to PyMuPDF alone — no tables in the current corpus benefit from Camelot extraction.",
                "impact": "low",
            },
            {
                "title": "MMR tuning provides no gain",
                "detail": "λ=0.9 (aggressive diversification) performs identically to baseline λ=0.75.",
                "impact": "low",
            },
        ]

        return {
            "runs": runs,
            "dimensions": dimensions,
            "findings": findings,
            "optimal_variant": runs[0]["variant"] if runs else "baseline",
            "baseline_variant": "baseline",
            "total_variants": len(runs),
        }

    def load_step_records(self, stage: str, limit: int) -> dict[str, Any]:
        run_dir = self.get_latest_run_dir()
        if run_dir is None:
            raise FileNotFoundError("No evaluation runs found")
        step_metrics = self.read_json_if_exists(run_dir / "step_metrics.json")
        if not isinstance(step_metrics, dict) or not step_metrics:
            raise FileNotFoundError("Step metrics not found")
        stage_data = step_metrics.get(stage, {})
        records = stage_data.get("records", []) if isinstance(stage_data, dict) else []
        return {"stage": stage, "records": records[:limit], "total_count": len(records)}

    def load_l6_records(self, limit: int) -> dict[str, Any]:
        run_dir = self.get_latest_run_dir()
        if run_dir is None:
            raise FileNotFoundError("No evaluation runs found")
        l6_rows_path = run_dir / "l6_answer_quality.jsonl"
        if not l6_rows_path.exists():
            raise FileNotFoundError("L6 answer quality records not found")

        records = []
        with l6_rows_path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return {"records": records[:limit], "total_count": len(records)}

    def load_step_metrics(self, stage: str) -> dict[str, Any]:
        run_dir = self.get_latest_run_dir()
        if run_dir is None:
            raise FileNotFoundError("No evaluation runs found")
        step_metrics = self.read_json_if_exists(run_dir / "step_metrics.json")
        if not isinstance(step_metrics, dict) or not step_metrics:
            raise FileNotFoundError("Step metrics not found")
        if stage not in step_metrics:
            raise FileNotFoundError("Stage not found in metrics")
        stage_metrics = step_metrics[stage]
        if not isinstance(stage_metrics, dict):
            raise ValueError("Stage metrics are malformed")
        return dict(stage_metrics)

    def load_answer_quality_details(self, run_dir_name: str) -> dict[str, Any]:
        target_dir = self._evals_dir / run_dir_name
        if not target_dir.exists():
            raise FileNotFoundError(f"Run directory not found: {run_dir_name}")

        results_path = target_dir / L6_ANSWER_QUALITY_ROWS
        if not results_path.exists():
            raise FileNotFoundError("Answer quality results not found for this run")

        results = []
        for line in results_path.read_text(encoding="utf-8").strip().split("\n"):
            if not line:
                continue
            try:
                results.append(json.loads(line))
            except Exception as exc:
                self.logger.debug("Failed to parse L6 result line: %s", exc)
        return {"run_dir": run_dir_name, "results": results}
