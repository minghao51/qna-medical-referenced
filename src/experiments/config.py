"""Versioned experiment configuration loading and normalization."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from src.config import settings
from src.ingestion.steps.chunk_text import DEFAULT_SOURCE_CHUNK_CONFIGS
from src.rag.runtime import get_runtime_retrieval_config

SUPPORTED_SCHEMA_VERSIONS = {1}


def _strip_comment(line: str) -> str:
    in_single = False
    in_double = False
    result: list[str] = []
    for ch in line:
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            break
        result.append(ch)
    return "".join(result).rstrip()


def _parse_scalar(value: str) -> Any:
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"null", "none"}:
        return None
    if value == "{}":
        return {}
    if value == "[]":
        return []
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1].encode("utf-8").decode("unicode_escape")
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(item.strip()) for item in inner.split(",") if item.strip()]
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


def _parse_yaml_block(lines: list[tuple[int, str]], index: int, indent: int) -> tuple[Any, int]:
    items: dict[str, Any] = {}
    seq: list[Any] | None = None
    while index < len(lines):
        line_indent, text = lines[index]
        if line_indent < indent:
            break
        if line_indent > indent:
            raise ValueError(f"Unexpected indentation near: {text}")
        if text.startswith("- "):
            if items:
                raise ValueError("Cannot mix mapping and sequence items at same indentation")
            if seq is None:
                seq = []
            body = text[2:].strip()
            if not body:
                child, index = _parse_yaml_block(lines, index + 1, indent + 2)
                seq.append(child)
                continue
            if ":" in body:
                key, rest = body.split(":", 1)
                key = key.strip()
                rest = rest.strip()
                node: dict[str, Any] = {}
                if rest:
                    node[key] = _parse_scalar(rest)
                    index += 1
                else:
                    child, index = _parse_yaml_block(lines, index + 1, indent + 2)
                    node[key] = child
                while index < len(lines):
                    child_indent, child_text = lines[index]
                    if child_indent < indent + 2:
                        break
                    if child_indent > indent + 2:
                        raise ValueError(f"Unexpected indentation near: {child_text}")
                    if child_text.startswith("- "):
                        break
                    child_key, child_rest = child_text.split(":", 1)
                    child_key = child_key.strip()
                    child_rest = child_rest.strip()
                    if child_rest:
                        node[child_key] = _parse_scalar(child_rest)
                        index += 1
                    else:
                        child, index = _parse_yaml_block(lines, index + 1, indent + 4)
                        node[child_key] = child
                seq.append(node)
                continue
            seq.append(_parse_scalar(body))
            index += 1
            continue
        if seq is not None:
            raise ValueError("Cannot mix sequence and mapping items at same indentation")
        if ":" not in text:
            raise ValueError(f"Expected key/value pair near: {text}")
        key, rest = text.split(":", 1)
        key = key.strip()
        rest = rest.strip()
        if rest:
            items[key] = _parse_scalar(rest)
            index += 1
        else:
            child, index = _parse_yaml_block(lines, index + 1, indent + 2)
            items[key] = child
    return (seq if seq is not None else items), index


def parse_simple_yaml(text: str) -> dict[str, Any]:
    processed: list[tuple[int, str]] = []
    for raw_line in text.splitlines():
        line = _strip_comment(raw_line)
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent % 2:
            raise ValueError("Only even indentation is supported in experiment YAML")
        processed.append((indent, line.strip()))
    if not processed:
        return {}
    parsed, index = _parse_yaml_block(processed, 0, 0)
    if index != len(processed):
        raise ValueError("Failed to parse entire experiment file")
    if not isinstance(parsed, dict):
        raise ValueError("Experiment root must be a mapping")
    return parsed


def _deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _config_hash(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _normalize_name(value: str | None, fallback: str) -> str:
    candidate = str(value or "").strip()
    return candidate or fallback


def _normalize_wandb_metrics_verbosity(value: Any) -> str:
    verbosity = str(value or "standard").strip().lower()
    if verbosity not in {"critical", "standard", "debug"}:
        return "standard"
    return verbosity


def _normalize_source_chunk_configs(value: Any) -> dict[str, Any]:
    cfg = deepcopy(DEFAULT_SOURCE_CHUNK_CONFIGS)
    if not isinstance(value, dict):
        return cfg
    for source_type, source_cfg in value.items():
        if not isinstance(source_cfg, dict):
            continue
        if source_type not in cfg:
            cfg[source_type] = {}
        cfg[source_type].update(source_cfg)
    return cfg


def _derive_collection_name(base_name: str, suffix: str | None) -> str:
    suffix_value = str(suffix or "").strip()
    return f"{base_name}_{suffix_value}" if suffix_value else base_name


def _normalize_embedding_index(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize embedding_index config, deriving collection_name exactly once.

    The base config may already have a derived collection_name from a previous
    normalization pass (e.g. when merging variant overrides). To avoid double-
    suffixing (medical_docs_comprehensive_ablation_comprehensive_ablation), we
    recover the original base name by stripping any known suffix, then re-derive.
    """
    embedding_index = dict(raw)
    suffix = embedding_index.get("collection_name_suffix")
    raw_collection = str(embedding_index.get("collection_name", settings.collection_name))

    # Recover the original base name: if the collection_name already ends with
    # "_<suffix>", strip it off so we can re-derive cleanly.
    base_name = raw_collection
    suffix_value = str(suffix or "").strip()
    if suffix_value and base_name.endswith(f"_{suffix_value}"):
        base_name = base_name[: -(len(suffix_value) + 1)]

    embedding_index["collection_name"] = _derive_collection_name(base_name, suffix)
    embedding_index["embedding_batch_size"] = int(
        embedding_index.get("embedding_batch_size", getattr(settings, "embedding_batch_size", 10))
    )
    return embedding_index


def _base_defaults() -> dict[str, Any]:
    retrieval_defaults = get_runtime_retrieval_config()
    return {
        "schema_version": 1,
        "metadata": {
            "name": "baseline",
            "description": "",
            "owner": "",
            "hypothesis": "",
            "tags": [],
        },
        "ingestion": {
            "page_classification_enabled": True,
            "index_only_classified_pages": True,
            "html_extractor_mode": "auto",
            "html_extractor_strategy": "trafilatura_bs",
            "pdf_extractor_strategy": "pypdf_pdfplumber",
            "pdf_table_extractor": "heuristic",
            "structured_chunking_enabled": True,
            "source_chunk_configs": deepcopy(DEFAULT_SOURCE_CHUNK_CONFIGS),
        },
        "embedding_index": {
            "collection_name": settings.collection_name,
            "collection_name_suffix": None,
            "embedding_model": settings.embedding_model,
            "embedding_batch_size": getattr(settings, "embedding_batch_size", 10),
            "semantic_weight": 0.6,
            "keyword_weight": 0.2,
            "boost_weight": 0.2,
            "rebuild_policy": "if_missing_or_stale",
            "materialize_html": True,
        },
        "retrieval": {
            "top_k": 5,
            "search_mode": retrieval_defaults["search_mode"],
            "enable_diversification": retrieval_defaults["enable_diversification"],
            "mmr_lambda": retrieval_defaults["mmr_lambda"],
            "overfetch_multiplier": retrieval_defaults["overfetch_multiplier"],
            "max_chunks_per_source_page": retrieval_defaults["max_chunks_per_source_page"],
            "max_chunks_per_source": retrieval_defaults["max_chunks_per_source"],
        },
        "dataset": {
            "path": None,
            "split": None,
            "min_label_confidence": "low",
            "max_synthetic_questions": 40,
            "sample_docs_per_source_type": 10,
            "seed": 42,
            "enable_llm_generation": True,
        },
        "evaluation": {
            "artifact_dir": "data/evals",
            "thresholds_file": None,
            "include_answer_eval": None,
            "disable_llm_judging": False,
            "fail_on_thresholds": False,
            "export_failed_generations": False,
            "run_retrieval_ablations": False,
            "run_diversity_sweep": False,
            "diversity_sweep": {},
        },
        "tracking": {
            "wandb": {
                "enabled": False,
                "project": None,
                "entity": None,
                "group": None,
                "job_type": "pipeline_eval",
                "tags": [],
                "notes": None,
                "mode": "online",
                "log_artifacts": True,
                "metrics_verbosity": "standard",
            }
        },
        "variants": [],
    }


def _normalize_experiment_dict(data: dict[str, Any], *, file_path: Path) -> dict[str, Any]:
    merged = _deep_merge(_base_defaults(), data)
    schema_version = int(
        merged.get("schema_version", merged.get("metadata", {}).get("schema_version", 1))
    )
    if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        raise ValueError(f"Unsupported experiment schema_version: {schema_version}")

    metadata = dict(merged.get("metadata", {}))
    metadata["name"] = _normalize_name(metadata.get("name"), file_path.stem)
    metadata["tags"] = list(metadata.get("tags", []))

    ingestion = dict(merged.get("ingestion", {}))
    ingestion["html_extractor_mode"] = str(ingestion.get("html_extractor_mode", "auto")).lower()
    ingestion["html_extractor_strategy"] = str(
        ingestion.get("html_extractor_strategy", "trafilatura_bs")
    ).lower()
    ingestion["pdf_extractor_strategy"] = str(
        ingestion.get("pdf_extractor_strategy", "pypdf_pdfplumber")
    ).lower()
    ingestion["pdf_table_extractor"] = str(
        ingestion.get("pdf_table_extractor", "heuristic")
    ).lower()
    ingestion["source_chunk_configs"] = _normalize_source_chunk_configs(
        ingestion.get("source_chunk_configs")
    )

    embedding_index = _normalize_embedding_index(merged.get("embedding_index", {}))

    retrieval = dict(merged.get("retrieval", {}))
    retrieval["top_k"] = int(retrieval.get("top_k", 5))

    dataset = dict(merged.get("dataset", {}))
    if dataset.get("path") is not None:
        dataset["path"] = str(Path(dataset["path"]))

    evaluation = dict(merged.get("evaluation", {}))
    if evaluation.get("thresholds_file") is not None:
        evaluation["thresholds_file"] = str(Path(evaluation["thresholds_file"]))

    tracking = dict(merged.get("tracking", {}))
    wandb_cfg = dict(tracking.get("wandb", {}))
    mode = str(wandb_cfg.get("mode", "online")).strip().lower()
    if mode not in {"online", "offline", "disabled"}:
        mode = "online"
    tracking["wandb"] = {
        "enabled": bool(wandb_cfg.get("enabled", False)),
        "project": str(wandb_cfg.get("project")).strip() if wandb_cfg.get("project") else None,
        "entity": str(wandb_cfg.get("entity")).strip() if wandb_cfg.get("entity") else None,
        "group": str(wandb_cfg.get("group")).strip() if wandb_cfg.get("group") else None,
        "job_type": _normalize_name(wandb_cfg.get("job_type"), "pipeline_eval"),
        "tags": list(wandb_cfg.get("tags", [])),
        "notes": str(wandb_cfg.get("notes")).strip() if wandb_cfg.get("notes") else None,
        "mode": mode,
        "log_artifacts": bool(wandb_cfg.get("log_artifacts", True)),
        "metrics_verbosity": _normalize_wandb_metrics_verbosity(wandb_cfg.get("metrics_verbosity")),
    }

    variants = list(merged.get("variants", []))
    normalized = {
        "schema_version": schema_version,
        "metadata": metadata,
        "ingestion": ingestion,
        "embedding_index": embedding_index,
        "retrieval": retrieval,
        "dataset": dataset,
        "evaluation": evaluation,
        "tracking": tracking,
        "variants": variants,
    }
    return normalized


def _index_config_subset(experiment: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": experiment["schema_version"],
        "ingestion": experiment["ingestion"],
        "embedding_index": {
            key: value
            for key, value in experiment["embedding_index"].items()
            if key
            in {
                "collection_name",
                "embedding_model",
                "embedding_batch_size",
                "semantic_weight",
                "keyword_weight",
                "boost_weight",
                "materialize_html",
            }
        },
    }


def load_experiment_file(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)
    raw_text = file_path.read_text(encoding="utf-8")
    parsed = parse_simple_yaml(raw_text)
    normalized = _normalize_experiment_dict(parsed, file_path=file_path)
    normalized["experiment_file"] = str(file_path)
    normalized["experiment_config_hash"] = _config_hash(
        {k: v for k, v in normalized.items() if k != "variants"}
    )
    normalized["index_config_hash"] = _config_hash(_index_config_subset(normalized))
    return normalized


def resolve_experiment_runs(
    path: str | Path,
    *,
    variant: str | None = None,
    all_variants: bool = False,
) -> list[dict[str, Any]]:
    base = load_experiment_file(path)
    runs: list[dict[str, Any]] = []
    base_run = deepcopy(base)
    base_run["variant_name"] = None
    runs.append(base_run)

    variants = list(base.get("variants", []))
    if variant and all_variants:
        raise ValueError("Choose either a single variant or --all-variants, not both")

    selected_variants = variants
    if variant:
        selected_variants = [item for item in variants if item.get("name") == variant]
        if not selected_variants:
            raise ValueError(f"Unknown experiment variant: {variant}")
    elif not all_variants:
        selected_variants = []

    for item in selected_variants:
        name = str(item.get("name", "")).strip()
        overrides = dict(item.get("overrides", {}))
        merged = _deep_merge(base, overrides)
        merged = _normalize_experiment_dict(merged, file_path=Path(path))
        merged["metadata"]["name"] = _normalize_name(name, merged["metadata"]["name"])
        merged["experiment_file"] = str(Path(path))
        merged["variant_name"] = name
        merged["variant_overrides"] = overrides
        merged["experiment_config_hash"] = _config_hash(
            {k: v for k, v in merged.items() if k not in {"variants", "variant_overrides"}}
        )
        merged["index_config_hash"] = _config_hash(_index_config_subset(merged))
        runs.append(merged)
    return runs


def build_run_assessment_kwargs(experiment: dict[str, Any]) -> dict[str, Any]:
    dataset = experiment["dataset"]
    evaluation = experiment["evaluation"]
    retrieval = experiment["retrieval"]
    return {
        "artifact_dir": evaluation["artifact_dir"],
        "name": experiment["metadata"]["name"],
        "dataset_path": dataset.get("path"),
        "top_k": retrieval["top_k"],
        "max_synthetic_questions": dataset["max_synthetic_questions"],
        "disable_llm_generation": not bool(dataset.get("enable_llm_generation", True)),
        "disable_llm_judging": bool(evaluation.get("disable_llm_judging", False)),
        "include_answer_eval": evaluation.get("include_answer_eval"),
        "sample_docs_per_source_type": dataset["sample_docs_per_source_type"],
        "seed": dataset["seed"],
        "fail_on_thresholds": bool(evaluation.get("fail_on_thresholds", False)),
        "thresholds_file": evaluation.get("thresholds_file"),
        "dataset_split": dataset.get("split"),
        "min_label_confidence": dataset["min_label_confidence"],
        "retrieval_mode": retrieval["search_mode"],
        "disable_page_classification": not bool(
            experiment["ingestion"].get("page_classification_enabled", True)
        ),
        "disable_structured_chunking": not bool(
            experiment["ingestion"].get("structured_chunking_enabled", True)
        ),
        "disable_bm25": str(retrieval["search_mode"]).lower() == "semantic_only",
        "export_failed_generations": bool(evaluation.get("export_failed_generations", False)),
        "retrieval_options": {
            "search_mode": retrieval["search_mode"],
            "enable_diversification": retrieval["enable_diversification"],
            "mmr_lambda": retrieval["mmr_lambda"],
            "overfetch_multiplier": retrieval["overfetch_multiplier"],
            "max_chunks_per_source_page": retrieval["max_chunks_per_source_page"],
            "max_chunks_per_source": retrieval["max_chunks_per_source"],
            "enable_hyde": retrieval.get("enable_hyde", False),
            "hyde_max_length": retrieval.get("hyde_max_length", 200),
            "enable_hype": retrieval.get("enable_hype", False),
            "enable_reranking": retrieval.get("enable_reranking", False),
            "reranking_mode": retrieval.get("reranking_mode", "cross_encoder"),
        },
        "run_retrieval_ablations": bool(evaluation.get("run_retrieval_ablations", False)),
        "run_hype_ablations": bool(evaluation.get("run_hype_ablations", False)),
        "run_reranking_ablations": bool(evaluation.get("run_reranking_ablations", False)),
        "run_diversity_sweep": bool(evaluation.get("run_diversity_sweep", False)),
        "diversity_sweep": dict(evaluation.get("diversity_sweep", {})),
        "experiment_config": experiment,
    }


def compute_retrieval_delta(
    baseline_metrics: dict[str, Any], comparison_metrics: dict[str, Any]
) -> dict[str, float]:
    tracked = [
        "hit_rate_at_k",
        "mrr",
        "ndcg_at_k",
        "exact_chunk_hit_rate",
        "evidence_hit_rate",
        "latency_p50_ms",
        "latency_p95_ms",
    ]
    delta: dict[str, float] = {}
    for key in tracked:
        try:
            delta[key] = float(comparison_metrics.get(key, 0.0)) - float(
                baseline_metrics.get(key, 0.0)
            )
        except (TypeError, ValueError):
            continue
    return delta
