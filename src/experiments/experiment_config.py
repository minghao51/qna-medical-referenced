"""Experiment configuration schema for feature addition experiments.

Defines YAML schema for configuring feature addition experiments
that test new features against a baseline.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

import yaml


@dataclasses.dataclass
class ExperimentVariant:
    """Configuration for a single experiment variant."""

    name: str
    chunking_strategy: str | None = None
    query_understanding: bool = False
    ingestion_overrides: dict[str, Any] | None = None
    retrieval_overrides: dict[str, Any] | None = None

    def __post_init__(self):
        """Validate variant configuration."""
        if not self.name:
            raise ValueError("Variant name cannot be empty")


@dataclasses.dataclass
class ExperimentMetrics:
    """Metric configuration for experiment evaluation."""

    primary: str = "ndcg@5"
    target_improvement: float = 0.03
    secondary: list[str] | None = None


@dataclasses.dataclass
class ExperimentConfig:
    """Configuration for a feature addition experiment."""

    name: str
    description: str | None = None
    baseline: ExperimentVariant | None = None
    variants: list[ExperimentVariant] | None = None
    metrics: ExperimentMetrics | None = None
    dataset_path: str | None = None
    dataset_split: str | None = None

    @classmethod
    def from_yaml(cls, yaml_path: str | Path) -> ExperimentConfig:
        """Load experiment config from YAML file.

        Args:
            yaml_path: Path to YAML config file

        Returns:
            ExperimentConfig instance
        """
        yaml_path = Path(yaml_path)
        with open(yaml_path) as f:
            data = yaml.safe_load(f)

        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExperimentConfig:
        """Create ExperimentConfig from dictionary.

        Args:
            data: Dictionary with experiment configuration

        Returns:
            ExperimentConfig instance
        """
        baseline_data = data.get("baseline", {})
        baseline = ExperimentVariant(
            name=baseline_data.get("name", "baseline"),
            chunking_strategy=baseline_data.get("chunking_strategy"),
            query_understanding=baseline_data.get("query_understanding", False),
            ingestion_overrides=baseline_data.get("ingestion_overrides"),
            retrieval_overrides=baseline_data.get("retrieval_overrides"),
        )

        variants_data = data.get("variants", [])
        variants = [
            ExperimentVariant(
                name=v.get("name", f"variant_{i}"),
                chunking_strategy=v.get("chunking_strategy"),
                query_understanding=v.get("query_understanding", False),
                ingestion_overrides=v.get("ingestion_overrides"),
                retrieval_overrides=v.get("retrieval_overrides"),
            )
            for i, v in enumerate(variants_data)
        ]

        metrics_data = data.get("metrics", {})
        metrics = ExperimentMetrics(
            primary=metrics_data.get("primary", "ndcg@5"),
            target_improvement=metrics_data.get("target_improvement", 0.03),
            secondary=metrics_data.get("secondary"),
        )

        return cls(
            name=data["name"],
            description=data.get("description"),
            baseline=baseline,
            variants=variants,
            metrics=metrics,
            dataset_path=data.get("dataset_path"),
            dataset_split=data.get("dataset_split"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert experiment config to dictionary.

        Returns:
            Dictionary representation of config
        """
        return {
            "name": self.name,
            "description": self.description,
            "baseline": {
                "name": self.baseline.name if self.baseline else "baseline",
                "chunking_strategy": self.baseline.chunking_strategy if self.baseline else None,
                "query_understanding": self.baseline.query_understanding if self.baseline else False,
                "ingestion_overrides": self.baseline.ingestion_overrides if self.baseline else None,
                "retrieval_overrides": self.baseline.retrieval_overrides if self.baseline else None,
            },
            "variants": [
                {
                    "name": v.name,
                    "chunking_strategy": v.chunking_strategy,
                    "query_understanding": v.query_understanding,
                    "ingestion_overrides": v.ingestion_overrides,
                    "retrieval_overrides": v.retrieval_overrides,
                }
                for v in self.variants
            ]
            if self.variants
            else [],
            "metrics": {
                "primary": self.metrics.primary if self.metrics else "ndcg@5",
                "target_improvement": self.metrics.target_improvement if self.metrics else 0.03,
                "secondary": self.metrics.secondary if self.metrics else None,
            }
            if self.metrics
            else {},
            "dataset_path": self.dataset_path,
            "dataset_split": self.dataset_split,
        }

    def save_yaml(self, yaml_path: str | Path) -> None:
        """Save experiment config to YAML file.

        Args:
            yaml_path: Path to save YAML config file
        """
        yaml_path = Path(yaml_path)
        yaml_path.parent.mkdir(parents=True, exist_ok=True)

        with open(yaml_path, "w") as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False, sort_keys=False)


def create_sample_experiment_config(output_path: str | Path = "experiments/feature_addition_sample.yaml") -> None:
    """Create a sample feature addition experiment config.

    Args:
        output_path: Path to save the sample config
    """
    config = ExperimentConfig(
        name="medical_semantic_chunking_exp",
        description="Test medical semantic chunking and query understanding features",
        baseline=ExperimentVariant(
            name="baseline",
            chunking_strategy="chonkie_semantic",
            query_understanding=False,
        ),
        variants=[
            ExperimentVariant(
                name="medical_chunking",
                chunking_strategy="medical_semantic",
                query_understanding=False,
            ),
            ExperimentVariant(
                name="query_understanding",
                chunking_strategy="chonkie_semantic",
                query_understanding=True,
            ),
            ExperimentVariant(
                name="both_features",
                chunking_strategy="medical_semantic",
                query_understanding=True,
            ),
        ],
        metrics=ExperimentMetrics(
            primary="ndcg@5",
            target_improvement=0.03,
            secondary=["mrr", "exact_chunk_hit_rate", "evidence_hit_rate"],
        ),
    )

    config.save_yaml(output_path)
    print(f"Sample experiment config saved to: {output_path}")
