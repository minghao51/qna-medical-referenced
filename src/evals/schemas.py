"""Dataclasses shared by evaluation modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class AssessmentConfig:
    artifact_dir: Path
    name: str | None = None
    dataset_path: Path | None = None
    top_k: int = 5
    max_synthetic_questions: int = 40
    disable_llm_generation: bool = False
    disable_llm_judging: bool = False
    include_answer_eval: bool = False
    sample_docs_per_source_type: int = 10
    seed: int = 42
    fail_on_thresholds: bool = False
    thresholds: dict[str, Any] = field(default_factory=dict)
    retrieval_options: dict[str, Any] = field(default_factory=dict)
    dataset_split: str | None = None
    min_label_confidence: str = "low"
    retrieval_mode: str = "rrf_hybrid"
    disable_page_classification: bool = False
    disable_structured_chunking: bool = False
    disable_bm25: bool = False
    export_failed_generations: bool = False
    run_retrieval_ablations: bool = False
    run_diversity_sweep: bool = False
    diversity_sweep: dict[str, Any] = field(default_factory=dict)


@dataclass
class AssessmentResult:
    run_dir: Path
    status: str
    failed_thresholds: list[dict[str, Any]]
    summary: dict[str, Any]
