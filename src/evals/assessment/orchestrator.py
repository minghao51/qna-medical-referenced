"""Evaluation assessment orchestration."""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import logging
import math
import os
import platform
import re
import stat
import tempfile
import time
from collections.abc import Callable
from contextlib import ExitStack, nullcontext
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from src.config import settings
from src.config.paths import DATA_RAW_DIR
from src.config.settings import TelemetryConfig
from src.evals.artifacts import (
    ARTIFACT_CONTRACT_VERSION,
    ArtifactStore,
    build_run_identity,
    to_serializable,
    update_run_index,
)
from src.evals.checks import (
    assess_l1_html_markdown_quality,
    assess_l2_pdf_quality,
    assess_l3_chunking_quality,
    assess_l4_reference_quality,
    assess_l5_index_quality,
    audit_l0_download,
)
from src.evals.checks.l5_index import capture_index_snapshot
from src.evals.dataset_builder import build_retrieval_dataset
from src.evals.index_snapshot import (
    FrozenIndexSnapshot,
    PrivateIndexMaterialization,
    freeze_index_snapshot,
    load_snapshot_export,
)
from src.evals.schemas import AssessmentConfig, AssessmentResult, AssessmentRunParams
from src.evals.usage import build_usage_summary

# Underscore aliases: the bare names collide with the boolean kwargs of
# run_assessment() (run_retrieval_ablations=True, ...), which shadowed
# these functions inside the default-composition body and injected False
# into the AssessmentPipeline fn fields.
from src.experiments.ablations import run_diversity_sweep as _run_diversity_sweep
from src.experiments.ablations import run_hype_ablations as _run_hype_ablations
from src.experiments.ablations import (
    run_hype_ablations_with_reingest,
    run_keyword_ablations_with_reingest,
)
from src.experiments.ablations import run_keyword_ablations as _run_keyword_ablations
from src.experiments.ablations import run_reranking_ablations as _run_reranking_ablations
from src.experiments.ablations import run_retrieval_ablations as _run_retrieval_ablations
from src.experiments.wandb_tracking import log_assessment_to_wandb
from src.infra.telemetry import (
    Operation,
    Route,
    Telemetry,
    UsageCompleteness,
    current_telemetry,
    telemetry_operation,
    use_telemetry,
)
from src.infra.usage import UsageAccumulator, capture_usage
from src.ingestion.indexing.chroma_store import ChromaVectorStore, use_vector_store
from src.ingestion.indexing.embedding import EXPECTED_EMBEDDING_DIM, embed_texts
from src.ingestion.runtime_config import apply_runtime_config, build_default_runtime_config
from src.rag import configure_runtime_for_experiment, initialize_runtime_index

logger = logging.getLogger(__name__)

from .answer_eval import evaluate_answer_quality  # noqa: E402
from .l6_contract import (  # noqa: E402
    IDENTITY_CONTRACT_VERSION,
    L6_ANSWER_QUALITY_METRICS,
    L6_ANSWER_QUALITY_ROWS,
    MEASUREMENT_CONTRACT_VERSION,
    REPLAY_SNAPSHOT_CONTRACT_VERSION,
    REQUIRED_ANSWER_METRICS,
    SUMMARY_L6_ENABLED_KEY,
    SUMMARY_L6_METRICS_KEY,
    SUMMARY_L6_STATUS_KEY,
)
from .reporting import (  # noqa: E402
    content_directory_provenance,
    git_head,
    render_summary,
    sha256_file,
    source_provenance,
)
from .retrieval_eval import (  # noqa: E402
    _is_unanswerable,
    _review_context_parts,
    _reviewed_evidence_qrels,
    evaluate_retrieval,
    review_manifest_authority_status,
)
from .thresholds import (  # noqa: E402
    DEFAULT_THRESHOLDS,
    evaluate_thresholds,
    measurement_summary,
)

__all__ = ["evaluate_answer_quality", "run_assessment"]

_SUPPORTED_EXECUTION_MODES = {"diagnostic", "benchmark", "replay"}
_SUPPORTED_GENERATION_IMPLEMENTATIONS = {"existing"}
_SUPPORTED_HARNESSES = {"deterministic_rag"}
_REVIEW_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MAX_REVIEW_MANIFEST_BYTES = 64 * 1024 * 1024
_MAX_REVIEW_DATASET_BYTES = 256 * 1024 * 1024


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("JSON contains duplicate object keys")
        result[key] = value
    return result


def _review_path_has_symlink(path: Path) -> bool:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current = current / part
        try:
            if stat.S_ISLNK(current.lstat().st_mode):
                return True
        except FileNotFoundError:
            return False
    return False


def _read_review_manifest(path: str | Path) -> tuple[dict[str, Any], str]:
    """Read one bounded manifest without following links and return its byte digest."""
    target = Path(path).absolute()
    if _review_path_has_symlink(target) or not target.is_file():
        raise ValueError("Review manifest must be a regular non-symlink file")
    descriptor: int | None = None
    try:
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(target, flags)
        with os.fdopen(descriptor, "rb") as source:
            descriptor = None
            before = os.fstat(source.fileno())
            if not stat.S_ISREG(before.st_mode):
                raise ValueError("Review manifest must be a regular file")
            if before.st_size <= 0 or before.st_size > _MAX_REVIEW_MANIFEST_BYTES:
                raise ValueError("Review manifest has an unsupported size")
            raw = source.read(_MAX_REVIEW_MANIFEST_BYTES + 1)
            after = os.fstat(source.fileno())
    except OSError:
        raise ValueError("Review manifest is unavailable") from None
    finally:
        if descriptor is not None:
            os.close(descriptor)
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ) or len(raw) != after.st_size:
        raise ValueError("Review manifest changed while being read")
    try:
        payload = json.loads(raw, object_pairs_hook=_reject_duplicate_json_keys)
    except (ValueError, UnicodeDecodeError):
        raise ValueError("Review manifest JSON is invalid") from None
    if not isinstance(payload, dict):
        raise ValueError("Review manifest schema is invalid")
    return payload, hashlib.sha256(raw).hexdigest()


def _verify_review_manifest_unchanged(path: str | Path, expected_sha256: str) -> None:
    _, actual_sha256 = _read_review_manifest(path)
    if actual_sha256 != expected_sha256:
        raise ValueError("Review manifest changed during measured execution")


def _validate_review_manifest_schema(manifest: dict[str, Any]) -> None:
    required = {
        "schema_version",
        "manifest_id",
        "dataset_sha256",
        "corpus_sha256",
        "frozen_sources",
        "frozen_documents",
        "cases",
    }
    allowed = required | {"index_snapshot_fingerprint", "attestations"}
    if (
        set(manifest) - allowed
        or not required.issubset(manifest)
        or isinstance(manifest.get("schema_version"), bool)
        or manifest.get("schema_version") != 1
    ):
        raise ValueError("Review manifest schema is unsupported")
    if "attestations" in manifest and not isinstance(manifest["attestations"], dict):
        raise ValueError("Review manifest attestations are invalid")
    if not isinstance(manifest.get("manifest_id"), str) or not manifest["manifest_id"].strip():
        raise ValueError("Review manifest identity is invalid")
    for key in ("dataset_sha256", "corpus_sha256"):
        if not isinstance(manifest.get(key), str) or not _REVIEW_SHA256.fullmatch(manifest[key]):
            raise ValueError("Review manifest digest is invalid")
    fingerprint = manifest.get("index_snapshot_fingerprint")
    if fingerprint is not None and (
        not isinstance(fingerprint, str) or not _REVIEW_SHA256.fullmatch(fingerprint)
    ):
        raise ValueError("Review manifest index binding is invalid")
    if not all(
        isinstance(manifest.get(key), dict)
        for key in ("frozen_sources", "frozen_documents", "cases")
    ):
        raise ValueError("Review manifest schema is invalid")


def _canonical_sha256(value: Any) -> str | None:
    try:
        encoded = json.dumps(
            value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError):
        return None
    return hashlib.sha256(encoded).hexdigest()


def _validate_review_context_for_dataset(
    review_context: dict[str, Any], dataset: list[dict[str, Any]]
) -> None:
    parts = _review_context_parts(review_context, dataset)
    if parts is None:
        raise ValueError("Review manifest dataset or evidence binding is invalid")
    review_cases, frozen_sources, _ = parts
    for item in dataset:
        case_id = item.get("query_id") or item.get("case_id")
        review_case = review_cases.get(str(case_id)) if case_id is not None else None
        passages = item.get("evidence_passages")
        if review_case is None or _is_unanswerable(item) or not passages:
            continue
        try:
            qrels = _reviewed_evidence_qrels(item, review_case, frozen_sources)
        except (TypeError, ValueError):
            raise ValueError("Review manifest evidence binding is invalid") from None
        if not qrels:
            raise ValueError("Review manifest evidence binding is invalid")


def _read_review_dataset(
    path: str | Path, review_context: dict[str, Any], expected_sha256: str | None
) -> list[dict[str, Any]]:
    target = Path(path).absolute()
    if _review_path_has_symlink(target) or not target.is_file():
        raise ValueError("Reviewed dataset must be a regular non-symlink file")
    descriptor: int | None = None
    try:
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(target, flags)
        with os.fdopen(descriptor, "rb") as source:
            descriptor = None
            before = os.fstat(source.fileno())
            if (
                not stat.S_ISREG(before.st_mode)
                or before.st_size <= 0
                or before.st_size > _MAX_REVIEW_DATASET_BYTES
            ):
                raise ValueError("Reviewed dataset has an unsupported size or type")
            raw = source.read(_MAX_REVIEW_DATASET_BYTES + 1)
            after = os.fstat(source.fileno())
    except OSError:
        raise ValueError("Reviewed dataset is unavailable") from None
    finally:
        if descriptor is not None:
            os.close(descriptor)
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ) or len(raw) != after.st_size:
        raise ValueError("Reviewed dataset changed while being read")
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("Reviewed dataset bytes changed or do not match the run identity")
    try:
        dataset = json.loads(raw, object_pairs_hook=_reject_duplicate_json_keys)
    except (ValueError, UnicodeDecodeError):
        raise ValueError("Reviewed dataset JSON is invalid") from None
    if not isinstance(dataset, list) or any(not isinstance(item, dict) for item in dataset):
        raise ValueError("Reviewed dataset must be a frozen array of case objects")
    if _canonical_sha256(dataset) != review_context.get("dataset_sha256"):
        raise ValueError("Reviewed dataset does not match its review manifest")
    _validate_review_context_for_dataset(review_context, dataset)
    return dataset


def _validate_review_snapshot_binding(
    review_context: dict[str, Any],
    capture: dict[str, Any],
    index_identity: dict[str, Any],
) -> None:
    fingerprint = index_identity.get("fingerprint")
    if (
        capture.get("status") != "verified"
        or capture.get("freeze_guarantee") is not True
        or not isinstance(fingerprint, str)
        or review_context.get("index_snapshot_fingerprint") != fingerprint
    ):
        raise ValueError("Review manifest does not match the verified index snapshot")
    snapshot = capture.get("snapshot")
    documents = review_context.get("frozen_documents")
    if not isinstance(snapshot, dict) or not isinstance(documents, dict):
        raise ValueError("Review manifest document binding is invalid")
    ids = snapshot.get("ids")
    contents = snapshot.get("contents")
    if (
        not isinstance(ids, list)
        or not isinstance(contents, list)
        or len(ids) != len(contents)
        or any(not isinstance(item, str) for item in ids + contents)
        or len(set(ids)) != len(ids)
        or set(documents) != set(ids)
    ):
        raise ValueError("Review manifest document binding is invalid")
    for document_id, content in zip(ids, contents, strict=True):
        document = documents.get(document_id)
        if not isinstance(document, dict) or hashlib.sha256(
            content.encode("utf-8")
        ).hexdigest() != document.get("content_sha256"):
            raise ValueError("Review manifest document binding is invalid")


def _validate_review_evaluator_support(evaluator: Callable[..., Any]) -> None:
    try:
        parameters = dict(inspect.signature(evaluator).parameters)
    except (TypeError, ValueError):
        parameters = {}
    accepts_keywords = any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in parameters.values()
    )
    review_parameter = parameters.get("review_context")
    if (
        review_parameter is not None and review_parameter.kind is inspect.Parameter.POSITIONAL_ONLY
    ) or (review_parameter is None and not accepts_keywords):
        raise ValueError("Custom retrieval evaluator does not support supplied review context")


def _safe_endpoint(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlsplit(value)
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Provider endpoint cannot contain credentials or query data")
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Unsupported provider endpoint")
    port = f":{parsed.port}" if parsed.port is not None else ""
    path = parsed.path.rstrip("/")
    return f"{parsed.scheme}://{parsed.hostname.lower()}{port}{path}"


def _execution_snapshot(
    config: AssessmentConfig, input_provenance: dict[str, Any]
) -> dict[str, Any]:
    from src.infra.llm.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
    from src.ingestion.indexing.embedding import EXPECTED_EMBEDDING_DIM

    prompt_bytes = f"{SYSTEM_PROMPT}\0{USER_PROMPT_TEMPLATE}".encode()
    rubric_path = Path(__file__).parents[1] / "metrics" / "medical.py"
    snapshot = {
        "identity_contract_version": IDENTITY_CONTRACT_VERSION,
        "execution_mode": config.execution_mode,
        "generation_implementation": config.generation_implementation,
        "harness": config.harness,
        "roles": {},
        "prompt_template_sha256": hashlib.sha256(prompt_bytes).hexdigest(),
        "rubric_source_sha256": sha256_file(rubric_path),
        "dataset": {
            "file_sha256": input_provenance.get("dataset_file_sha256"),
            "split": config.dataset_split,
            "sampling_seed": config.sample_seed,
            "case_ids_sha256": None,
        },
        "embedder": {
            "provider": "dashscope_qwen",
            "model": settings.llm.embedding_model,
            "dimensions": EXPECTED_EMBEDDING_DIM,
            "batch_size": settings.llm.embedding_batch_size,
            "endpoint": _safe_endpoint(settings.llm.qwen_base_url),
        },
        "retrieval": {
            "top_k": config.top_k,
            "options": config.retrieval_options,
        },
        "source": input_provenance.get("source", {}),
        "corpus": input_provenance.get("corpus", {"status": "unverified"}),
        "runtime": {"python": platform.python_version()},
    }
    if input_provenance.get("review_manifest_sha256") is not None:
        snapshot["review_manifest_sha256"] = input_provenance["review_manifest_sha256"]
    _validate_recorded_config(snapshot)
    return snapshot


def _index_snapshot_identity(
    capture: dict[str, Any], *, corpus_sha256: str | None = None
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "unverified",
        "reason": "index_snapshot_unavailable",
        "fingerprint": None,
        "document_count": None,
        "embedding_dimensions": None,
        "embedding_model": None,
        "hype_auxiliary_captured": False,
        "retrieval_weights": None,
        "build_spec_sha256": None,
    }
    if not isinstance(capture, dict):
        return result
    if capture.get("status") != "verified" or capture.get("freeze_guarantee") is not True:
        result["reason"] = str(capture.get("reason") or "backend_snapshot_freeze_unavailable")
        return result
    snapshot = capture.get("snapshot")
    build_spec = capture.get("build_spec")
    if not isinstance(snapshot, dict) or not isinstance(build_spec, dict):
        result["reason"] = str(capture.get("reason") or "index_snapshot_unavailable")
        return result

    try:
        _validate_recorded_config(build_spec)
        ids = list(snapshot.get("ids") or [])
        contents = list(snapshot.get("contents") or [])
        metadatas = list(snapshot.get("metadatas") or [])
        embeddings = list(snapshot.get("embeddings") or [])
        if not ids or len({str(item) for item in ids}) != len(ids):
            result["reason"] = "index_snapshot_empty_or_duplicate_ids"
            return result
        if not (len(ids) == len(contents) == len(metadatas) == len(embeddings)):
            result["reason"] = "index_snapshot_arrays_incomplete"
            return result
        if any(not isinstance(item, str) for item in ids + contents):
            result["reason"] = "index_snapshot_arrays_invalid"
            return result
        if any(not isinstance(item, dict) for item in metadatas):
            result["reason"] = "index_snapshot_metadata_invalid"
            return result
        _validate_recorded_config(metadatas)
        dimensions = {len(vector) for vector in embeddings if isinstance(vector, (list, tuple))}
        if len(dimensions) != 1 or any(
            not isinstance(vector, (list, tuple)) or len(vector) != next(iter(dimensions))
            for vector in embeddings
        ):
            result["reason"] = "index_snapshot_embeddings_incomplete"
            return result
        metadata = build_spec.get("collection_metadata")
        embedder = build_spec.get("embedder")
        if not isinstance(metadata, dict) or not isinstance(embedder, dict):
            result["reason"] = "index_build_spec_incomplete"
            return result
        required_metadata = {
            "source_snapshot_sha256",
            "embedding_model",
            "embedding_batch_size",
            "semantic_weight",
            "keyword_weight",
            "boost_weight",
            "page_classification_enabled",
            "index_only_classified_pages",
            "html_extractor_mode",
            "html_extractor_strategy",
            "pdf_extractor_strategy",
            "pdf_table_extractor",
            "structured_chunking_enabled",
            "source_chunk_configs",
            "enable_hype",
            "hype_sample_rate",
            "hype_max_chunks",
            "hype_questions_per_chunk",
            "enable_keyword_extraction",
            "enable_chunk_summaries",
            "keyword_extraction_sample_rate",
            "keyword_extraction_max_chunks",
        }
        if not required_metadata.issubset(metadata):
            result["reason"] = "index_build_spec_incomplete"
            return result
        for key in (
            "html_extractor_mode",
            "html_extractor_strategy",
            "pdf_extractor_strategy",
            "pdf_table_extractor",
        ):
            if not isinstance(metadata.get(key), str) or not metadata[key]:
                result["reason"] = "index_build_spec_incomplete"
                return result
        for key in (
            "page_classification_enabled",
            "index_only_classified_pages",
            "structured_chunking_enabled",
            "enable_hype",
            "enable_keyword_extraction",
            "enable_chunk_summaries",
        ):
            if not isinstance(metadata.get(key), bool):
                result["reason"] = "index_build_spec_incomplete"
                return result
        chunk_configs = metadata.get("source_chunk_configs")
        if isinstance(chunk_configs, str):
            try:
                chunk_configs = json.loads(chunk_configs)
            except json.JSONDecodeError:
                result["reason"] = "index_build_spec_incomplete"
                return result
        if not isinstance(chunk_configs, dict):
            result["reason"] = "index_build_spec_incomplete"
            return result
        _validate_recorded_config(chunk_configs)
        weights = build_spec.get("retrieval_weights", {})
        if not {"semantic", "keyword", "boost"}.issubset(weights) or any(
            isinstance(weights.get(key), bool)
            or not isinstance(weights.get(key), (int, float))
            or not math.isfinite(float(weights[key]))
            for key in ("semantic", "keyword", "boost")
        ):
            result["reason"] = "index_build_spec_incomplete"
            return result
        if (
            not isinstance(metadata.get("embedding_model"), str)
            or metadata.get("embedding_model") != embedder.get("model")
            or not isinstance(metadata.get("embedding_batch_size"), int)
            or metadata.get("embedding_batch_size") != embedder.get("batch_size")
        ):
            result["reason"] = "index_embedder_provenance_incomplete"
            return result
        source_sha256 = metadata.get("source_snapshot_sha256")
        if not isinstance(source_sha256, str) or len(source_sha256) != 64:
            result["reason"] = "index_source_provenance_missing"
            return result
        if corpus_sha256 and source_sha256 != corpus_sha256:
            result["reason"] = "index_source_provenance_mismatch"
            return result
        if not isinstance(build_spec.get("collection_name"), str) or not isinstance(
            build_spec.get("retrieval_weights"), dict
        ):
            result["reason"] = "index_build_spec_incomplete"
            return result
        if (
            not isinstance(embedder.get("model"), str)
            or not isinstance(embedder.get("dimensions"), int)
            or embedder["dimensions"] != next(iter(dimensions))
        ):
            result["reason"] = "index_embedder_provenance_incomplete"
            return result

        ordered_records = sorted(
            zip(ids, contents, metadatas, embeddings, strict=True), key=lambda row: row[0]
        )
        fingerprint = build_run_identity(
            config={"records": ordered_records, "build_spec": build_spec}, git_head=None
        )
        result.update(
            fingerprint=fingerprint,
            document_count=len(ids),
            embedding_dimensions=next(iter(dimensions)),
            embedding_model=embedder.get("model"),
            hype_auxiliary_captured=any(
                isinstance(metadata, dict)
                and isinstance(metadata.get("hypothetical_questions"), list)
                and bool(metadata.get("hypothetical_questions"))
                for metadata in metadatas
            ),
            retrieval_weights=dict(weights),
            build_spec_sha256=build_run_identity(config=build_spec, git_head=None),
        )
        result.update(status="verified", reason=None)
    except (TypeError, ValueError, OverflowError):
        result["reason"] = "index_snapshot_unserializable"
    return result


def _validate_recorded_config(value: Any) -> None:
    """Reject recognized credential fields/URLs before hashing or persistence."""
    error = "Evaluation configuration must not contain credentials or credential-bearing URLs"
    if hasattr(value, "get_secret_value"):
        raise ValueError(error)
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).lower().replace("-", "_")
            compact = normalized.replace("_", "")
            if (
                compact in {"key", "token", "auth", "bearer"}
                or any(
                    marker in compact
                    for marker in (
                        "apikey",
                        "password",
                        "secret",
                        "credential",
                        "authorization",
                        "cookie",
                        "headers",
                    )
                )
                or compact.endswith("token")
            ):
                raise ValueError(error)
            _validate_recorded_config(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _validate_recorded_config(item)
    elif isinstance(value, str) and "://" in value:
        try:
            endpoint = urlsplit(value)
            if endpoint.username or endpoint.password or endpoint.query or endpoint.fragment:
                raise ValueError(error)
        except ValueError:
            raise ValueError(error) from None


def _finite_metric_values(value: Any) -> Any:
    """Represent invalid numbers as null AFTER gates have recorded their failure."""

    def finite(item: Any) -> Any:
        if isinstance(item, dict):
            return {key: finite(child) for key, child in item.items()}
        if isinstance(item, list):
            return [finite(child) for child in item]
        if isinstance(item, float) and not math.isfinite(item):
            return None
        return item

    # Match the artifact serializer's tuple/dataclass/model_dump conversion exactly.
    return finite(to_serializable(value))


def _usage_by_role(manifest: dict[str, Any], provider_usage: dict[str, Any]) -> dict[str, Any]:
    usage_by_role: dict[str, Any] = {}
    for task_roles in manifest.get("effective_roles", {}).values():
        if not isinstance(task_roles, dict):
            continue
        for role_name, role_config in task_roles.items():
            if (
                role_name in {"generator", "judge", "embedder", "enrichment"}
                and isinstance(role_config, dict)
                and role_config.get("status") != "not_required"
                and role_config.get("provider")
            ):
                usage_by_role[role_name] = {
                    "input_tokens": None,
                    "output_tokens": None,
                    "total_tokens": None,
                    "status": "unavailable",
                    "source": "provider_sdk_usage_not_observed",
                }
    captured = provider_usage.get("usage_by_role", {})
    if isinstance(captured, dict):
        for role_name, counts in captured.items():
            if role_name == "generation":
                usage_by_role.pop("generator", None)
            if role_name in {"judge_light", "judge_heavy"}:
                usage_by_role.pop("judge", None)
            usage_by_role[role_name] = counts
    return usage_by_role


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
        "raw_data_identity": {
            "status": "unverified",
            "reason": "metadata_only_not_content_snapshot",
        },
        "raw_data_snapshot_sha256": build_run_identity(config=snapshot, git_head=None),
    }


@dataclass
class AssessmentPipeline:
    """Staged, dependency-injected end-to-end assessment pipeline.

    Decomposed from a single ~490-line function in Phase 2 (roadmap P2.4).
    Each stage is a small method with explicit inputs/outputs; ``run``
    composes them. The module-level ``run_assessment`` is the default
    composition: it resolves overrides from this module's namespace at
    call time, which keeps ``monkeypatch.setattr`` on this module working.
    """

    audit_l0_download_fn: Callable[[], dict[str, Any]] = audit_l0_download
    assess_l1_html_markdown_quality_fn: Callable[[], dict[str, Any]] = (
        assess_l1_html_markdown_quality
    )
    assess_l2_pdf_quality_fn: Callable[[], dict[str, Any]] = assess_l2_pdf_quality
    assess_l3_chunking_quality_fn: Callable[[], dict[str, Any]] = assess_l3_chunking_quality
    assess_l4_reference_quality_fn: Callable[[], dict[str, Any]] = assess_l4_reference_quality
    assess_l5_index_quality_fn: Callable[..., dict[str, Any]] = assess_l5_index_quality
    build_retrieval_dataset_fn: Callable[..., dict[str, Any]] = build_retrieval_dataset
    evaluate_retrieval_fn: Callable[..., tuple[list[dict[str, Any]], dict[str, Any]]] = (
        evaluate_retrieval
    )
    evaluate_answers_fn: Callable[..., tuple[list[dict[str, Any]], dict[str, Any]]] = (
        evaluate_answer_quality
    )
    evaluate_thresholds_fn: Callable[..., list[dict[str, Any]]] = evaluate_thresholds
    git_head_fn: Callable[[], str | None] = git_head
    source_provenance_fn: Callable[[], dict[str, Any]] = source_provenance
    corpus_provenance_fn: Callable[[Path], dict[str, Any]] = content_directory_provenance
    capture_index_snapshot_fn: Callable[[str | None], dict[str, Any]] = capture_index_snapshot
    configure_runtime_for_experiment_fn: Callable[[dict[str, Any] | None], dict[str, Any]] = (
        configure_runtime_for_experiment
    )
    initialize_runtime_index_fn: Callable[..., dict[str, Any]] = initialize_runtime_index
    log_assessment_to_wandb_fn: Callable[..., dict[str, Any]] = log_assessment_to_wandb
    run_retrieval_ablations_fn: Callable[..., dict[str, Any]] = _run_retrieval_ablations
    run_hype_ablations_fn: Callable[..., dict[str, Any]] = _run_hype_ablations
    run_keyword_ablations_fn: Callable[..., dict[str, Any]] = _run_keyword_ablations
    run_keyword_ablations_with_reingest_fn: Callable[..., dict[str, Any]] = (
        run_keyword_ablations_with_reingest
    )
    run_hype_ablations_with_reingest_fn: Callable[..., dict[str, Any]] = (
        run_hype_ablations_with_reingest
    )
    run_reranking_ablations_fn: Callable[..., dict[str, Any]] = _run_reranking_ablations
    run_diversity_sweep_fn: Callable[..., list[dict[str, Any]]] = _run_diversity_sweep
    render_summary_fn: Callable[..., str] = render_summary
    sha256_file_fn: Callable[[str | Path | None], str | None] = sha256_file

    def run(self, params: AssessmentRunParams) -> AssessmentResult:
        """Own attempt usage and opt-in local tracing; never opt a CLI run into hosted export."""
        attempt_state: dict[str, Any] = {}
        telemetry = current_telemetry()
        owned_telemetry: Telemetry | None = None
        if telemetry is None and settings.telemetry.mode == "local":
            # App/hosted settings are not permission for a new CLI export destination.
            owned_telemetry = Telemetry(
                TelemetryConfig(
                    mode="local",
                    local_span_capacity=settings.telemetry.local_span_capacity,
                    shutdown_timeout_seconds=settings.telemetry.shutdown_timeout_seconds,
                )
            )
            telemetry = owned_telemetry
        try:
            with (
                use_telemetry(telemetry),
                telemetry_operation(Operation.RUN, route=Route.CLI) as run_span,
                ExitStack() as telemetry_contexts,
                capture_usage() as provider_usage,
            ):
                attempt_state["telemetry_contexts"] = telemetry_contexts
                try:
                    return self._run_attempt(params, provider_usage, attempt_state)
                except BaseException as error:
                    try:
                        self._persist_failed_attempt(
                            attempt_state,
                            provider_usage.snapshot(),
                            cancelled=isinstance(error, asyncio.CancelledError),
                        )
                    except BaseException:
                        # Diagnostics must never replace the original failure/cancellation.
                        pass
                    raise
                finally:
                    roles = list(provider_usage.usage_by_role.values())
                    inputs = [role.get("input_tokens") for role in roles]
                    outputs = [role.get("output_tokens") for role in roles]
                    run_span.set_usage(
                        input_tokens=sum(v for v in inputs if v is not None)
                        if inputs and all(v is not None for v in inputs)
                        else None,
                        output_tokens=sum(v for v in outputs if v is not None)
                        if outputs and all(v is not None for v in outputs)
                        else None,
                        completeness=UsageCompleteness.UNKNOWN
                        if not roles
                        else (
                            UsageCompleteness.COMPLETE
                            if not provider_usage.unknowns
                            and all(v is not None for v in inputs + outputs)
                            else UsageCompleteness.PARTIAL
                        ),
                    )
        finally:
            if owned_telemetry is not None:
                try:
                    closed = owned_telemetry.close()
                    store = attempt_state.get("store")
                    if isinstance(store, ArtifactStore):
                        # Only this run's locally owned metadata sink is persisted, never
                        # a caller's potentially content-approved or hosted trace stream.
                        store.write_json(
                            "telemetry_metadata.json",
                            {
                                "schema_version": 1,
                                "mode": "local",
                                "shutdown_completed": closed,
                                "coverage": "bounded_tail_not_complete_trace",
                                "span_capacity": settings.telemetry.local_span_capacity,
                                "spans": [
                                    {
                                        "name": span.name,
                                        "attributes": dict(span.attributes or {}),
                                        "status": span.status.status_code.name,
                                        "start_time_ns": span.start_time,
                                        "end_time_ns": span.end_time,
                                        "span_id": format(span.context.span_id, "016x")
                                        if span.context
                                        else None,
                                        "trace_id": format(span.context.trace_id, "032x")
                                        if span.context
                                        else None,
                                        "parent_span_id": format(span.parent.span_id, "016x")
                                        if span.parent
                                        else None,
                                    }
                                    for span in owned_telemetry.finished_spans
                                ],
                            },
                        )
                except BaseException:
                    # Trace lifecycle/storage failures must not mask an attempt result.
                    pass

    def _persist_failed_attempt(
        self,
        attempt_state: dict[str, Any],
        provider_usage: dict[str, Any],
        *,
        cancelled: bool,
    ) -> None:
        store = attempt_state.get("store")
        if not isinstance(store, ArtifactStore):
            return
        execution_status = "cancelled" if cancelled else "failed"
        reason = "assessment_attempt_cancelled" if cancelled else "assessment_attempt_failed"
        manifest = attempt_state.get("manifest")
        if not isinstance(manifest, dict):
            manifest = {"execution_id": store.execution_id}
        usage_summary = build_usage_summary(
            store.execution_id,
            usage_by_role=_usage_by_role(manifest, provider_usage),
            unknowns=[*(provider_usage.get("unknowns", [])), reason],
        )
        usage_summary.update(
            {
                "status": "incomplete",
                "usage_status": "incomplete",
                "cash_status": "incomplete",
                "quota_status": "incomplete",
                "cash_actual_usd": None,
                "cash_estimate_usd": None,
                "quota_value_usd": None,
                "quota_applicable": None,
            }
        )
        measurement = {"status": "incomplete", "reason": reason}
        manifest.update(
            {
                "execution_id": store.execution_id,
                "execution_status": execution_status,
                "measurement": measurement,
                "quality_gate": "incomplete",
                "usage_summary": usage_summary,
            }
        )
        store.write_json("manifest.json", manifest)
        store.write_json(
            "summary.json",
            {
                "execution_id": store.execution_id,
                "execution_mode": manifest.get("execution_mode"),
                "execution_status": execution_status,
                "status": execution_status,
                "identity": manifest.get("identity"),
                "measurement": measurement,
                "quality_gate": "incomplete",
                "usage_summary": usage_summary,
                "run_dir": str(store.run_dir),
            },
        )
        update_run_index(
            store.base_dir,
            run_identity=store.execution_id,
            run_dir=store.run_dir,
            status=execution_status,
        )

    def _run_attempt(
        self,
        params: AssessmentRunParams,
        provider_usage: UsageAccumulator,
        attempt_state: dict[str, Any],
    ) -> AssessmentResult:
        """Execute a diagnostic attempt or a verified private-copy benchmark."""
        if params.execution_mode == "replay":
            return self._run_replay(params, attempt_state)
        start = time.time()
        (config, config_payload, git_revision, input_provenance, run_identity, key_available) = (
            self._resolve_config(params)
        )
        review_context = None
        review_dataset = None
        if config.review_manifest_path is not None:
            review_context, manifest_sha256 = _read_review_manifest(config.review_manifest_path)
            _validate_review_manifest_schema(review_context)
            if manifest_sha256 != input_provenance.get("review_manifest_sha256"):
                raise ValueError("Review manifest changed during run preparation")
            if config.dataset_path is None:
                raise ValueError("A review manifest requires an explicit frozen dataset_path")
            review_dataset = _read_review_dataset(
                config.dataset_path,
                review_context,
                input_provenance.get("dataset_file_sha256"),
            )
            _validate_review_evaluator_support(self.evaluate_retrieval_fn)
        frozen_snapshot = (
            load_snapshot_export(config.index_snapshot_path)
            if config.execution_mode == "benchmark" and config.index_snapshot_path is not None
            else None
        )
        index_capture = (
            frozen_snapshot.capture_payload()
            if frozen_snapshot is not None
            else {"status": "unverified", "reason": "snapshot_not_requested_in_diagnostic_mode"}
        )
        corpus_sha256 = (input_provenance.get("corpus") or {}).get("content_sha256")
        index_identity = _index_snapshot_identity(index_capture, corpus_sha256=corpus_sha256)
        if review_context is not None and config.execution_mode == "benchmark":
            _validate_review_snapshot_binding(review_context, index_capture, index_identity)
        identity = self._update_execution_identity(
            config, config_payload, input_provenance, index_identity, run_identity
        )
        self._require_benchmark_preflight(config, config_payload, input_provenance, index_identity)

        store = ArtifactStore(config.artifact_dir, config.name)
        telemetry = current_telemetry()
        telemetry_contexts = attempt_state.get("telemetry_contexts")
        if telemetry is not None and isinstance(telemetry_contexts, ExitStack):
            telemetry_contexts.enter_context(telemetry.run_id_context(store.execution_id))
        attempt_state.update(
            store=store,
            manifest={
                "execution_id": store.execution_id,
                "execution_mode": config.execution_mode,
                "run_identity": run_identity,
            },
        )
        manifest = self._seed_manifest(
            store,
            config,
            config_payload,
            git_revision,
            input_provenance,
            run_identity,
            key_available,
            {"status": "pending"},
            index_identity,
            identity,
            start,
        )
        attempt_state["manifest"] = manifest
        experiment_runtime, index_preparation = self._prepare_index(config, frozen_snapshot)
        collection_name = experiment_runtime.get("vector_store", {}).get("collection_name")
        manifest["index_preparation"] = index_preparation
        store.write_json("manifest.json", manifest)

        materialization: PrivateIndexMaterialization | None = None
        private_store: ChromaVectorStore | None = None
        copy_identity: dict[str, Any] = {}
        copy_capture = index_capture
        if config.execution_mode == "benchmark":
            if frozen_snapshot is None:
                raise ValueError("Benchmark mode requires an explicit verified index export")
            materialization, private_store = self._materialize_frozen_index(frozen_snapshot)
            copy_snapshot = freeze_index_snapshot(materialization)
            copy_capture = copy_snapshot.capture_payload()
            copy_identity = _index_snapshot_identity(copy_capture, corpus_sha256=corpus_sha256)
            if copy_identity.get("status") != "verified" or copy_identity.get(
                "fingerprint"
            ) != index_identity.get("fingerprint"):
                raise ValueError("Private index copy does not match the verified frozen export")
            if review_context is not None:
                _validate_review_snapshot_binding(review_context, copy_capture, copy_identity)
            identity = self._update_execution_identity(
                config,
                config_payload,
                input_provenance,
                index_identity,
                run_identity,
                index_execution_verified=True,
            )

        manifest["identity"] = identity
        manifest["config"] = config_payload
        attempt_state["manifest"] = manifest
        if materialization is not None and frozen_snapshot is not None:
            manifest["index_execution"].update(
                {
                    "status": "verified_private_copy",
                    "snapshot_verified": True,
                    "actual_index_path_verified": True,
                    "retrieval_routed_to_snapshot": True,
                    "reason": None,
                    "source_fingerprint": frozen_snapshot.fingerprint,
                    "copy_fingerprint_before": copy_identity["fingerprint"],
                    "execution_order": config.execution_order,
                    "private_copy_created_fresh": True,
                    "private_copy_reused": False,
                    "cache_state": {
                        "worker_process": "fresh_subprocess"
                        if os.getenv("QNA_EVAL_ATTEMPT_WORKSPACE")
                        else "current_process",
                        "private_index": "fresh_unique_copy",
                        "query_embedding_cache": "process_local_state_not_observable",
                        "filesystem_page_cache": "not_observable",
                        "query_order": "dataset_order; cold_or_warm_latency_not_inferred",
                    },
                }
            )
            store.write_json("manifest.json", manifest)

        scope = use_vector_store(private_store) if private_store is not None else nullcontext()
        with scope:
            step_metrics, step_findings, vector_path, vector_file_sha256, l5_agg = (
                self._run_step_checks(config, experiment_runtime, copy_capture)
            )
            dataset, generation_attempts, dataset_stats = self._build_dataset(
                config, vector_file_sha256, frozen_review_dataset=review_dataset
            )
            identity = self._record_dataset_identity(
                config,
                config_payload,
                input_provenance,
                index_identity,
                run_identity,
                dataset,
                index_execution_verified=private_store is not None,
                review_authority_status=(
                    review_manifest_authority_status(review_context, review_dataset)
                    if review_context is not None
                    else None
                ),
            )
            manifest["identity"] = identity
            manifest["config"] = config_payload
            store.write_json("manifest.json", manifest)
            retrieval = self._run_retrieval_stage(
                config, dataset, collection_name, review_context=review_context
            )
            l6_answer_quality_rows, l6_answer_quality_metrics = self._run_answer_eval(
                config,
                dataset,
                vector_file_sha256,
                cache_dir=store.run_dir / "cache",
                execution_snapshot=config_payload.get("execution_snapshot"),
            )

        if config.execution_mode == "benchmark":
            if frozen_snapshot is None or materialization is None:
                raise ValueError("Benchmark private index copy was unavailable")
            source_after = self._capture_index_snapshot(
                collection_name, index_snapshot_path=config.index_snapshot_path
            )
            source_after_identity = _index_snapshot_identity(
                source_after, corpus_sha256=corpus_sha256
            )
            copy_after_snapshot = freeze_index_snapshot(materialization)
            copy_after_identity = _index_snapshot_identity(
                copy_after_snapshot.capture_payload(), corpus_sha256=corpus_sha256
            )
            if (
                source_after_identity.get("status") != "verified"
                or source_after_identity.get("fingerprint") != index_identity.get("fingerprint")
                or copy_after_identity.get("status") != "verified"
                or copy_after_identity.get("fingerprint") != index_identity.get("fingerprint")
            ):
                raise ValueError(
                    "Benchmark source export or private copy changed during measured execution"
                )
            if self.sha256_file_fn(config.dataset_path) != input_provenance.get(
                "dataset_file_sha256"
            ):
                raise ValueError("Benchmark dataset changed during execution")
            try:
                source_provenance_after = self.source_provenance_fn()
                corpus_after = self.corpus_provenance_fn(DATA_RAW_DIR)
            except Exception:
                raise ValueError(
                    "Benchmark source or corpus provenance became unavailable"
                ) from None
            if (
                source_provenance_after.get("status") != "verified"
                or source_provenance_after.get("source_content_sha256")
                != (input_provenance.get("source") or {}).get("source_content_sha256")
                or source_provenance_after.get("dependency_lock_sha256")
                != (input_provenance.get("source") or {}).get("dependency_lock_sha256")
                or corpus_after.get("status") != "verified"
                or corpus_after.get("content_sha256") != corpus_sha256
            ):
                raise ValueError("Benchmark source or corpus identity changed during execution")
            manifest["index_execution"].update(
                {
                    "source_fingerprint_after": source_after_identity["fingerprint"],
                    "copy_fingerprint_after": copy_after_identity["fingerprint"],
                    "source_unchanged": True,
                    "private_copy_unchanged": True,
                }
            )
            if review_context is not None:
                _validate_review_snapshot_binding(
                    review_context,
                    copy_after_snapshot.capture_payload(),
                    copy_after_identity,
                )

        if config.review_manifest_path is not None:
            expected_review_sha256 = input_provenance.get("review_manifest_sha256")
            if not isinstance(expected_review_sha256, str):
                raise ValueError("Review manifest identity is unavailable")
            _verify_review_manifest_unchanged(config.review_manifest_path, expected_review_sha256)
            if config.dataset_path is None:
                raise ValueError("Reviewed dataset path became unavailable")
            dataset_after = _read_review_dataset(
                config.dataset_path,
                review_context or {},
                input_provenance.get("dataset_file_sha256"),
            )
            if dataset_after != dataset:
                raise ValueError("Reviewed dataset changed during measured execution")

        return self._finalize(
            config=config,
            start=start,
            run_identity=run_identity,
            store=store,
            manifest=manifest,
            step_metrics=step_metrics,
            step_findings=step_findings,
            vector_path=vector_path,
            vector_file_sha256=vector_file_sha256,
            l5_agg=l5_agg,
            dataset=dataset,
            dataset_stats=dataset_stats,
            generation_attempts=generation_attempts,
            retrieval=retrieval,
            l6_answer_quality_rows=l6_answer_quality_rows,
            l6_answer_quality_metrics=l6_answer_quality_metrics,
            identity=identity,
            index_identity=index_identity,
            provider_usage=provider_usage.snapshot(),
        )

    def _resolve_config(
        self, params: AssessmentRunParams
    ) -> tuple[AssessmentConfig, dict[str, Any], str | None, dict[str, Any], str, bool]:
        """Stage 1: validate supported axes and resolve the non-secret run snapshot."""
        if params.execution_mode not in _SUPPORTED_EXECUTION_MODES:
            raise ValueError("Unsupported execution mode; supported: diagnostic, benchmark, replay")
        if params.execution_mode == "replay":
            raise ValueError("Replay mode requires an explicit replay_snapshot")
        if params.replay_snapshot is not None:
            raise ValueError("replay_snapshot is only valid in replay mode")
        if params.index_snapshot_path is not None and params.execution_mode != "benchmark":
            raise ValueError("index_snapshot_path is only valid in benchmark mode")
        if params.execution_mode == "benchmark" and not params.index_snapshot_path:
            raise ValueError("Benchmark mode requires an explicit --index-snapshot-path export")
        if params.execution_order is not None and (
            isinstance(params.execution_order, bool)
            or not isinstance(params.execution_order, int)
            or params.execution_order < 0
        ):
            raise ValueError("execution_order must be a non-negative integer or None")
        if params.generation_implementation not in _SUPPORTED_GENERATION_IMPLEMENTATIONS:
            raise ValueError("Unsupported generation implementation; supported: existing")
        if params.harness not in _SUPPORTED_HARNESSES:
            raise ValueError("Unsupported evaluation harness; supported: deterministic_rag")
        if params.experiment_config and any(
            key in params.experiment_config for key in ("generation", "provider")
        ):
            raise ValueError("Experiment generation/provider overrides are unsupported")
        if params.execution_mode == "benchmark":
            if params.dataset_path is None or not Path(params.dataset_path).is_file():
                raise ValueError("Benchmark mode requires an explicit existing dataset_path")
        review_manifest_sha256 = None
        if params.review_manifest_path is not None:
            if params.dataset_path is None:
                raise ValueError("A review manifest requires an explicit frozen dataset_path")
            if any(
                (
                    params.run_retrieval_ablations,
                    params.run_hype_ablations,
                    params.run_keyword_ablations,
                    params.run_reranking_ablations,
                    params.run_diversity_sweep,
                )
            ):
                raise ValueError("Reviewed retrieval manifests do not support ablation variants")
            review_manifest, review_manifest_sha256 = _read_review_manifest(
                params.review_manifest_path
            )
            _validate_review_manifest_schema(review_manifest)
        if params.retrieval_mode not in {"rrf_hybrid", "semantic_only", "bm25_only"}:
            raise ValueError("Unsupported retrieval mode")
        if params.reuse_cached_dataset:
            raise ValueError(
                "Dataset cache replay requires a verified identity; use an explicit dataset_path"
            )
        thresholds = dict(DEFAULT_THRESHOLDS)
        if params.thresholds_file:
            thresholds.update(json.loads(Path(params.thresholds_file).read_text(encoding="utf-8")))

        _api_key = settings.llm.dashscope_api_key.get_secret_value()
        key_available = bool(_api_key)
        # Credential presence never authorizes a costly evaluation suite.
        resolved_include_answer_eval = params.include_answer_eval is True
        if not resolved_include_answer_eval:
            answer_keys = {
                f"l6.{key}_{suffix}"
                for key in REQUIRED_ANSWER_METRICS
                for suffix in ("mean", "error_rate")
            } | {"l6.metric_error_rate"}
            thresholds = {key: value for key, value in thresholds.items() if key not in answer_keys}
        resolved_retrieval_options = dict(params.retrieval_options or {})
        if params.disable_bm25:
            resolved_retrieval_options["search_mode"] = "semantic_only"
        elif params.retrieval_mode != "rrf_hybrid":
            resolved_retrieval_options["search_mode"] = params.retrieval_mode
        from src.rag.config import RetrievalDiversityConfig

        allowed_retrieval_options = set(RetrievalDiversityConfig.__dataclass_fields__)
        if set(resolved_retrieval_options) - allowed_retrieval_options:
            raise ValueError("Unsupported retrieval configuration override")
        if resolved_retrieval_options.get("search_mode") not in {
            None,
            "rrf_hybrid",
            "semantic_only",
            "bm25_only",
        }:
            raise ValueError("Unsupported retrieval search mode")
        if resolved_retrieval_options.get("reranking_mode") not in {
            None,
            "cross_encoder",
            "mmr",
            "both",
        }:
            raise ValueError("Unsupported retrieval reranking mode")
        if resolved_retrieval_options.get("medical_expansion_provider") not in {None, "noop"}:
            raise ValueError("Unsupported medical expansion provider")
        config = AssessmentConfig(
            artifact_dir=Path(params.artifact_dir),
            execution_mode=params.execution_mode,
            generation_implementation=params.generation_implementation,
            harness=params.harness,
            replay_snapshot=Path(params.replay_snapshot) if params.replay_snapshot else None,
            index_snapshot_path=(
                Path(params.index_snapshot_path) if params.index_snapshot_path else None
            ),
            name=params.name,
            dataset_path=Path(params.dataset_path) if params.dataset_path else None,
            review_manifest_path=(
                Path(params.review_manifest_path) if params.review_manifest_path else None
            ),
            top_k=params.top_k,
            max_synthetic_questions=(
                0 if params.execution_mode == "benchmark" else params.max_synthetic_questions
            ),
            disable_llm_generation=(
                True if params.execution_mode == "benchmark" else params.disable_llm_generation
            ),
            disable_llm_judging=params.disable_llm_judging,
            include_answer_eval=resolved_include_answer_eval,
            sample_docs_per_source_type=params.sample_docs_per_source_type,
            seed=params.seed,
            max_queries=params.max_queries,
            sample_seed=params.sample_seed,
            reuse_cached_dataset=params.reuse_cached_dataset,
            fail_on_thresholds=params.fail_on_thresholds,
            thresholds=thresholds,
            retrieval_options=resolved_retrieval_options,
            dataset_split=params.dataset_split,
            min_label_confidence=params.min_label_confidence,
            retrieval_mode=params.retrieval_mode,
            disable_page_classification=params.disable_page_classification,
            disable_structured_chunking=params.disable_structured_chunking,
            disable_bm25=params.disable_bm25,
            export_failed_generations=params.export_failed_generations,
            run_retrieval_ablations=params.run_retrieval_ablations,
            run_hype_ablations=params.run_hype_ablations,
            run_keyword_ablations=params.run_keyword_ablations,
            run_reranking_ablations=params.run_reranking_ablations,
            run_diversity_sweep=params.run_diversity_sweep,
            diversity_sweep=dict(params.diversity_sweep or {}),
            experiment_config=params.experiment_config,
            force_rerun=params.force_rerun,
            skip_ingestion=(
                True if params.execution_mode == "benchmark" else params.skip_ingestion
            ),
            execution_order=params.execution_order,
        )
        if config.execution_mode == "benchmark" and any(
            (
                config.run_retrieval_ablations,
                config.run_hype_ablations,
                config.run_keyword_ablations,
                config.run_reranking_ablations,
                config.run_diversity_sweep,
            )
        ):
            raise ValueError("Benchmark mode does not support ablation or rebuild stages")
        config_payload = asdict(config)
        config_payload["measurement_contract_version"] = MEASUREMENT_CONTRACT_VERSION
        config_payload["identity_contract_version"] = IDENTITY_CONTRACT_VERSION
        config_payload = to_serializable(config_payload)
        _validate_recorded_config(config_payload)
        git_revision = self.git_head_fn()
        input_provenance = _build_input_provenance(
            dataset_path=config.dataset_path,
            raw_data_dir=DATA_RAW_DIR,
            sha256_file_fn=self.sha256_file_fn,
        )
        if review_manifest_sha256 is not None:
            input_provenance["review_manifest_sha256"] = review_manifest_sha256
        try:
            input_provenance["source"] = self.source_provenance_fn()
        except Exception:
            input_provenance["source"] = {
                "version": 1,
                "status": "unverified",
                "reason": "source_snapshot_unavailable",
            }
        if config.execution_mode == "benchmark":
            try:
                input_provenance["corpus"] = self.corpus_provenance_fn(DATA_RAW_DIR)
            except Exception:
                input_provenance["corpus"] = {
                    "version": 1,
                    "status": "unverified",
                    "reason": "source_tree_unavailable",
                    "content_sha256": None,
                }
        else:
            input_provenance["corpus"] = {
                "version": 1,
                "status": "unverified",
                "reason": "corpus_snapshot_not_requested_in_diagnostic_mode",
                "content_sha256": None,
            }
        execution_snapshot = _execution_snapshot(config, input_provenance)
        config_payload["execution_snapshot"] = execution_snapshot
        config_payload = to_serializable(config_payload)
        _validate_recorded_config(config_payload)
        # This configuration fingerprint is diagnostic; a semantic fingerprint also
        # requires the verified index snapshot captured at the execution boundary.
        fingerprint_config = {
            key: value
            for key, value in config_payload.items()
            if key
            not in {
                "artifact_dir",
                "name",
                "force_rerun",
                "dataset_path",
                "replay_snapshot",
                "index_snapshot_path",
                "review_manifest_path",
                "execution_order",
            }
        }
        run_identity = build_run_identity(
            config={
                "artifact_contract_version": ARTIFACT_CONTRACT_VERSION,
                "identity_contract_version": IDENTITY_CONTRACT_VERSION,
                "assessment": fingerprint_config,
                "input_provenance": input_provenance,
            },
            git_head=git_revision,
        )
        return config, config_payload, git_revision, input_provenance, run_identity, key_available

    def _capture_index_snapshot(
        self,
        collection_name: str | None,
        *,
        index_snapshot_path: Path | None = None,
    ) -> dict[str, Any]:
        try:
            if index_snapshot_path is not None:
                frozen_snapshot = load_snapshot_export(index_snapshot_path)
                if (
                    collection_name is not None
                    and frozen_snapshot.collection_name != collection_name
                ):
                    return {"status": "unverified", "reason": "snapshot_collection_mismatch"}
                return frozen_snapshot.capture_payload()
            return self.capture_index_snapshot_fn(collection_name)
        except Exception:
            return {"status": "unverified", "reason": "collection_snapshot_unavailable"}

    def _require_benchmark_preflight(
        self,
        config: AssessmentConfig,
        config_payload: dict[str, Any],
        input_provenance: dict[str, Any],
        index_identity: dict[str, Any],
    ) -> None:
        if config.execution_mode != "benchmark":
            return
        source = input_provenance.get("source", {})
        corpus = input_provenance.get("corpus", {})
        if not config.skip_ingestion or not config.disable_llm_generation:
            raise ValueError(
                "Benchmark preflight requires ingestion and dataset generation disabled"
            )
        if not config.dataset_path or not input_provenance.get("dataset_file_sha256"):
            raise ValueError("Benchmark preflight requires a hashed explicit dataset")
        if (
            source.get("status") != "verified"
            or not source.get("source_content_sha256")
            or not source.get("dependency_lock_sha256")
        ):
            raise ValueError(
                "Benchmark preflight blocked: source or dependency-lock provenance is unverified"
            )
        if corpus.get("status") != "verified" or not corpus.get("content_sha256"):
            raise ValueError("Benchmark preflight blocked: corpus content provenance is unverified")
        if index_identity.get("status") != "verified" or not index_identity.get("fingerprint"):
            reason = index_identity.get("reason") or "index_snapshot_unverified"
            raise ValueError(f"Benchmark preflight blocked: {reason}")
        from src.rag.config import resolve_retrieval_config

        allowed = set(resolve_retrieval_config().__dataclass_fields__)
        unknown = set(config.retrieval_options) - allowed
        if unknown:
            raise ValueError("Benchmark contains unsupported retrieval overrides")
        effective_retrieval = resolve_retrieval_config(config.retrieval_options)
        if effective_retrieval.enable_reranking:
            raise ValueError("Benchmark preflight blocked: reranker asset readiness is unverified")
        if (
            index_identity.get("embedding_model") != settings.llm.embedding_model
            or index_identity.get("embedding_dimensions") != EXPECTED_EMBEDDING_DIM
        ):
            raise ValueError(
                "Benchmark preflight blocked: frozen index embedder does not match the active query embedder"
            )
        if effective_retrieval.enable_hype and not index_identity.get("hype_auxiliary_captured"):
            raise ValueError(
                "Benchmark preflight blocked: unsupported capability; frozen index does not "
                "contain captured HyPE auxiliary metadata"
            )
        if effective_retrieval.medical_expansion_provider != "noop":
            raise ValueError(
                "Benchmark preflight blocked: medical expansion provider is unsupported"
            )
        snapshot = config_payload.get("execution_snapshot", {})
        if not snapshot.get("prompt_template_sha256") or not snapshot.get("rubric_source_sha256"):
            raise ValueError(
                "Benchmark preflight blocked: prompt or rubric identity is unavailable"
            )
        role_tasks = snapshot.get("roles", {})
        embedder = role_tasks.get("retrieval", {}).get("embedder", {})
        if not embedder.get("key_configured"):
            raise ValueError(
                "Benchmark preflight blocked: retrieval embedder credential is unavailable"
            )
        if effective_retrieval.enable_hyde and not role_tasks.get("generation", {}).get(
            "generator", {}
        ).get("key_configured"):
            raise ValueError(
                "Benchmark preflight blocked: HyDE generator credential is unavailable"
            )
        if config.include_answer_eval and not config.disable_llm_judging:
            answer_eval = role_tasks.get("answer_eval", {})
            judge = answer_eval.get("judge", {})
            if not judge.get("key_configured") or not answer_eval.get("dependencies_available"):
                raise ValueError(
                    "Benchmark preflight blocked: answer-evaluation prerequisites are unavailable"
                )

    def _update_execution_identity(
        self,
        config: AssessmentConfig,
        config_payload: dict[str, Any],
        input_provenance: dict[str, Any],
        index_identity: dict[str, Any],
        run_identity: str,
        *,
        index_execution_verified: bool = False,
    ) -> dict[str, Any]:
        from dataclasses import asdict as dataclass_asdict

        from src.rag.config import resolve_retrieval_config

        snapshot = config_payload["execution_snapshot"]
        effective_retrieval = resolve_retrieval_config(config.retrieval_options)
        snapshot["retrieval"]["effective"] = dataclass_asdict(effective_retrieval)
        snapshot["retrieval"]["effective"]["top_k"] = config.top_k
        snapshot["retrieval"]["index_execution"] = {
            "index_snapshot_path_provided": config.index_snapshot_path is not None,
            "actual_index_path_verified": index_execution_verified,
            "retrieval_routed_to_snapshot": index_execution_verified,
        }
        from src.evals.deepeval_models import effective_roles

        task_names = ["retrieval"]
        if not config.disable_llm_generation or effective_retrieval.enable_hyde:
            task_names.append("generation")
        if config.include_answer_eval and not config.disable_llm_judging:
            task_names.append("answer_eval")
        recorded_roles: dict[str, Any] = {}
        for task_name in task_names:
            task_roles = effective_roles(
                task=task_name,
                implementation=config.generation_implementation,
                harness=config.harness,
            )
            safe_task_roles = {
                key: value
                for key, value in task_roles.items()
                if key not in {"required_credentials", "missing_dependencies"}
            }
            safe_task_roles["dependencies_available"] = not bool(
                task_roles.get("missing_dependencies")
            )
            for role_name in ("generator", "judge", "embedder", "enrichment"):
                role = safe_task_roles.get(role_name)
                if not isinstance(role, dict) or "credential" not in role:
                    continue
                credential_info = role.pop("credential")
                role["key_configured"] = bool(credential_info.get("configured"))
                role["key_required"] = bool(credential_info.get("required"))
            _validate_recorded_config(safe_task_roles)
            recorded_roles[task_name] = safe_task_roles
        snapshot["roles"] = recorded_roles
        if "embedder" in recorded_roles["retrieval"]:
            snapshot["embedder"] = recorded_roles["retrieval"]["embedder"]
        source = input_provenance.get("source", {})
        corpus = input_provenance.get("corpus", {})
        dataset_ready = bool(
            snapshot.get("dataset", {}).get("file_sha256")
            and snapshot.get("dataset", {}).get("case_ids_sha256")
        )
        identity_ready = bool(
            source.get("status") == "verified"
            and source.get("source_content_sha256")
            and source.get("dependency_lock_sha256")
            and corpus.get("status") == "verified"
            and corpus.get("content_sha256")
            and dataset_ready
            and index_identity.get("status") == "verified"
            and index_identity.get("fingerprint")
            and snapshot.get("prompt_template_sha256")
            and snapshot.get("rubric_source_sha256")
            and snapshot.get("retrieval", {})
            .get("index_execution", {})
            .get("actual_index_path_verified")
            is True
            and snapshot.get("retrieval", {})
            .get("index_execution", {})
            .get("retrieval_routed_to_snapshot")
            is True
        )
        semantic_fingerprint = (
            build_run_identity(
                config={
                    "identity_contract_version": IDENTITY_CONTRACT_VERSION,
                    "execution_snapshot": snapshot,
                    "index_fingerprint": index_identity.get("fingerprint"),
                },
                git_head=None,
            )
            if identity_ready
            else None
        )
        reasons = []
        if not source.get("source_content_sha256") or not source.get("dependency_lock_sha256"):
            reasons.append("source_or_lock_provenance_unverified")
        if not corpus.get("content_sha256"):
            reasons.append("corpus_provenance_unverified")
        if not dataset_ready:
            reasons.append("dataset_case_identity_unavailable")
        if index_identity.get("status") != "verified":
            reasons.append("index_snapshot_unverified")
        if not (
            snapshot.get("retrieval", {})
            .get("index_execution", {})
            .get("actual_index_path_verified")
            is True
            and snapshot.get("retrieval", {})
            .get("index_execution", {})
            .get("retrieval_routed_to_snapshot")
            is True
        ):
            reasons.append("frozen_snapshot_retrieval_not_wired")
        if not snapshot.get("rubric_source_sha256") or not snapshot.get("prompt_template_sha256"):
            reasons.append("prompt_or_rubric_identity_unavailable")
        configuration_fingerprint = build_run_identity(
            config={"base": run_identity, "execution_snapshot": snapshot}, git_head=None
        )
        identity = {
            "version": IDENTITY_CONTRACT_VERSION,
            "status": "verified" if semantic_fingerprint else "unverified",
            "configuration_fingerprint": configuration_fingerprint,
            "semantic_fingerprint": semantic_fingerprint,
            "index": {
                "status": index_identity.get("status", "unverified"),
                "fingerprint": index_identity.get("fingerprint"),
                "reason": index_identity.get("reason"),
            },
            "reuse_eligible": False,
            "cohort_eligible": False,
            "promotion_eligible": False,
            "reasons": reasons or ["human_review_and_integrated_promotion_gates_pending"],
        }
        config_payload["execution_snapshot"] = to_serializable(snapshot)
        config_payload["effective_roles"] = to_serializable(recorded_roles)
        selected_judge = (recorded_roles.get("answer_eval") or {}).get("judge", {})
        selected_judge_roles = (
            {
                "provider": selected_judge.get("provider"),
                "light": selected_judge.get("light_model"),
                "heavy": selected_judge.get("heavy_model"),
            }
            if isinstance(selected_judge, dict) and selected_judge.get("provider")
            else {}
        )
        config_payload["roles"] = {
            "generator": settings.llm.provider,
            "light": settings.llm.judge_model_light,
            "heavy": settings.llm.judge_model_heavy,
            "selected_judge_roles": selected_judge_roles,
        }
        _validate_recorded_config(config_payload["roles"])
        return identity

    def _record_dataset_identity(
        self,
        config: AssessmentConfig,
        config_payload: dict[str, Any],
        input_provenance: dict[str, Any],
        index_identity: dict[str, Any],
        run_identity: str,
        dataset: list[dict[str, Any]],
        *,
        index_execution_verified: bool = False,
        review_authority_status: str | None = None,
    ) -> dict[str, Any]:
        identifiers = [item.get("query_id") or item.get("case_id") for item in dataset]
        if config.execution_mode == "benchmark":
            if any(not isinstance(value, str) or not value.strip() for value in identifiers):
                raise ValueError(
                    "Benchmark dataset cases require stable query_id or case_id values"
                )
            if len(set(identifiers)) != len(identifiers):
                raise ValueError("Benchmark dataset case identifiers must be unique")
        snapshot = config_payload["execution_snapshot"]
        snapshot["dataset"]["case_ids_sha256"] = (
            build_run_identity(config=[str(value) for value in identifiers], git_head=None)
            if identifiers and all(identifiers)
            else None
        )
        reviewed = sum(
            str(item.get("review_status", "")).casefold() in {"human_reviewed", "reviewed"}
            and str(item.get("label_origin", "")).casefold() in {"human_reviewed", "human"}
            for item in dataset
        )
        snapshot["dataset"]["expected_case_count"] = len(dataset)
        snapshot["dataset"]["human_reviewed_case_count"] = reviewed
        snapshot["dataset"]["review_authority_status"] = (
            review_authority_status
            if review_authority_status is not None
            else "manifest_asserted_not_authenticated"
        )
        config_payload["execution_snapshot"] = to_serializable(snapshot)
        identity = self._update_execution_identity(
            config,
            config_payload,
            input_provenance,
            index_identity,
            run_identity,
            index_execution_verified=index_execution_verified,
        )
        identity["human_reviewed_case_count"] = reviewed
        identity["review_authority_status"] = (
            review_authority_status
            if review_authority_status is not None
            else "manifest_asserted_not_authenticated"
        )
        identity["reviewed_evidence_eligible"] = False
        identity["cohort_eligible"] = False
        identity["promotion_eligible"] = False
        identity["reasons"] = list(identity["reasons"])
        identity["reasons"].append("cohort_and_promotion_review_gates_pending")
        return identity

    def _materialize_frozen_index(
        self, frozen_snapshot: FrozenIndexSnapshot
    ) -> tuple[PrivateIndexMaterialization, ChromaVectorStore]:
        """Create a unique private Chroma copy and bind the normal RAG store API to it."""
        workspace = os.getenv("QNA_EVAL_ATTEMPT_WORKSPACE")
        if workspace:
            private_parent = Path(workspace) / "frozen-indexes"
            private_parent.mkdir(parents=True, exist_ok=True)
        else:
            private_parent = Path(tempfile.gettempdir())
        materialization = frozen_snapshot.materialize(private_parent)
        build_spec = frozen_snapshot.capture_payload()["build_spec"]
        embedder = build_spec["embedder"]
        weights = build_spec["retrieval_weights"]
        embedding_model = str(embedder["model"])
        private_store = ChromaVectorStore(
            collection_name=frozen_snapshot.collection_name,
            semantic_weight=float(weights["semantic"]),
            keyword_weight=float(weights["keyword"]),
            boost_weight=float(weights["boost"]),
            embedding_model=embedding_model,
            embedding_batch_size=int(embedder["batch_size"]),
            persist_directory=materialization.path,
            client=materialization.client,
            collection=materialization.collection,
            query_embedding_fn=lambda query: embed_texts(
                [query], batch_size=1, model=embedding_model
            )[0],
            strict_query_embedding=True,
        )
        # The Chroma API's local metadata format is scalar-only; provenance remains
        # bound to the frozen snapshot and is kept on this private store instance.
        private_store._index_metadata = dict(build_spec["collection_metadata"])
        return materialization, private_store

    def _prepare_index(
        self,
        config: AssessmentConfig,
        frozen_snapshot: FrozenIndexSnapshot | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Stage 3: configure the runtime index (or skip per config)."""
        if config.execution_mode == "benchmark":
            if frozen_snapshot is None:
                raise ValueError("Benchmark mode requires an explicit frozen index export")
            return (
                {"vector_store": {"collection_name": frozen_snapshot.collection_name}},
                {"status": "skipped", "reason": "verified_frozen_snapshot_execution"},
            )
        experiment_runtime = self.configure_runtime_for_experiment_fn(config.experiment_config)
        index_preparation: dict[str, Any] = {"status": "not_requested"}
        if config.skip_ingestion:
            logger.info("Skipping ingestion — reusing existing index")
            index_preparation = {"status": "skipped", "reason": "skip_ingestion_requested"}
        elif not config.experiment_config:
            apply_runtime_config(
                build_default_runtime_config(
                    disable_page_classification=config.disable_page_classification,
                    disable_structured_chunking=config.disable_structured_chunking,
                )
            )
        else:
            embedding_index = config.experiment_config.get("embedding_index", {})
            vector_config = experiment_runtime.get("vector_store", {})
            vector_path = Path("data/vectors") / (
                f"{vector_config.get('collection_name', settings.storage.collection_name)}.json"
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
            rebuild_policy = str(
                embedding_index.get("rebuild_policy", "if_missing_or_stale")
            ).lower()
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
            index_preparation = self.initialize_runtime_index_fn(
                rebuild=should_rebuild,
                force_html_convert=should_rebuild,
            )
        return experiment_runtime, index_preparation

    def _seed_manifest(
        self,
        store: ArtifactStore,
        config: AssessmentConfig,
        config_payload: dict[str, Any],
        git_revision: str | None,
        input_provenance: dict[str, Any],
        run_identity: str,
        key_available: bool,
        index_preparation: dict[str, Any],
        index_identity: dict[str, Any],
        identity: dict[str, Any],
        start: float,
    ) -> dict[str, Any]:
        """Stage 4: write the initial manifest into the attempt's ONE store."""
        manifest = {
            "artifact_contract_version": ARTIFACT_CONTRACT_VERSION,
            "execution_id": store.execution_id,
            "identity": identity,
            "effective_roles": config_payload.get("effective_roles", {}),
            "identity_contract_version": IDENTITY_CONTRACT_VERSION,
            "execution_mode": config.execution_mode,
            "index_snapshot": index_identity,
            "index_execution": {
                "status": "pending_private_copy"
                if config.execution_mode == "benchmark"
                else "not_applicable",
                "snapshot_verified": index_identity.get("status") == "verified",
                "index_snapshot_path_provided": config.index_snapshot_path is not None,
                "actual_index_path_verified": False,
                "retrieval_routed_to_snapshot": False,
                "execution_order": config.execution_order,
                "reason": (
                    "private_copy_not_materialized"
                    if config.execution_mode == "benchmark"
                    else "not_requested"
                ),
                "runner_contract": [
                    "Unique private Chroma copy per attempt; no served-collection reads for retrieval.",
                    "Use supplied query vectors with the baseline hybrid/ranking implementation.",
                    "Revalidate source export and private copy before and after measured work.",
                    "Retain private files until the isolated worker exits; physical Chroma close is unverified.",
                ],
            },
            "cache_policy": {
                "version": 1,
                "mode": "fresh",
                "run_reuse": False,
                "persistent_reuse": False,
                "reason": "unverified_semantic_identity",
            },
            "measurement_contract_version": MEASUREMENT_CONTRACT_VERSION,
            "required_metrics": [
                key
                for key, spec in config.thresholds.items()
                if not isinstance(spec, dict) or spec.get("required", True)
            ],
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
        return manifest

    def _run_step_checks(
        self,
        config: AssessmentConfig,
        experiment_runtime: dict[str, Any],
        index_capture: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], Any, str | None, dict[str, Any]]:
        """Stage 5: run L0-L5; feed the real L3 checker chunks from this same collection."""
        l5_collection_name = experiment_runtime.get("vector_store", {}).get("collection_name")
        l3_fn = self.assess_l3_chunking_quality_fn
        l3_parameters: dict[str, inspect.Parameter]
        try:
            l3_parameters = dict(inspect.signature(l3_fn).parameters)
        except (TypeError, ValueError):
            l3_parameters = {}
        accepts_keywords = any(
            parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in l3_parameters.values()
        )
        if "chunks" in l3_parameters or accepts_keywords:
            if not (index_capture or {}).get("snapshot"):
                index_capture = self._capture_index_snapshot(l5_collection_name)
            capture = index_capture or {}
            snapshot = capture.get("snapshot")
            chunks: list[dict[str, Any]] | None = None
            document_count: int | None = None
            chunk_size: int | None = None
            chunk_overlap: int | None = None
            if capture.get("status") == "verified" and isinstance(snapshot, dict):
                ids = snapshot.get("ids")
                contents = snapshot.get("contents")
                metadatas = snapshot.get("metadatas")
                if (
                    isinstance(ids, list)
                    and isinstance(contents, list)
                    and isinstance(metadatas, list)
                    and len(ids) == len(contents) == len(metadatas)
                    and all(isinstance(meta, dict) for meta in metadatas)
                ):
                    chunks = [
                        {
                            **metadatas[index],
                            "id": ids[index],
                            "content": contents[index],
                            "metadata": metadatas[index],
                        }
                        for index in range(len(ids))
                    ]
                    source_units = [
                        next(
                            (
                                str(metadata[key]).strip()
                                for key in (
                                    "source_id",
                                    "logical_name",
                                    "canonical_label",
                                    "source",
                                )
                                if metadata.get(key) is not None and str(metadata[key]).strip()
                            ),
                            None,
                        )
                        for metadata in metadatas
                    ]
                    if not source_units:
                        document_count = 0
                    elif all(source_units):
                        document_count = len(set(source_units))

                    index_metadata = snapshot.get("index_metadata")
                    chunk_configs = (
                        index_metadata.get("source_chunk_configs")
                        if isinstance(index_metadata, dict)
                        else None
                    )
                    if isinstance(chunk_configs, str):
                        try:
                            chunk_configs = json.loads(chunk_configs)
                        except json.JSONDecodeError:
                            chunk_configs = None
                    if isinstance(chunk_configs, dict) and chunk_configs:

                        def single_known_value(key: str) -> int | None:
                            values = [
                                value.get(key)
                                for value in chunk_configs.values()
                                if isinstance(value, dict)
                            ]
                            if len(values) != len(chunk_configs) or any(
                                isinstance(value, bool) or not isinstance(value, int)
                                for value in values
                            ):
                                return None
                            unique_values = set(values)
                            return next(iter(unique_values)) if len(unique_values) == 1 else None

                        chunk_size = single_known_value("chunk_size")
                        chunk_overlap = single_known_value("chunk_overlap")
            l3_kwargs: dict[str, Any] = {"chunks": chunks}
            if "document_count" in l3_parameters or accepts_keywords:
                l3_kwargs["document_count"] = document_count
            if "chunk_size" in l3_parameters or accepts_keywords:
                l3_kwargs["chunk_size"] = chunk_size
            if "chunk_overlap" in l3_parameters or accepts_keywords:
                l3_kwargs["chunk_overlap"] = chunk_overlap
            l3_metrics = l3_fn(**l3_kwargs)
        else:
            # Older injected test fakes and diagnostics remain callable without arguments.
            l3_metrics = l3_fn()
        step_metrics = {
            "l0": self.audit_l0_download_fn(),
            "l1": self.assess_l1_html_markdown_quality_fn(),
            "l2": self.assess_l2_pdf_quality_fn(),
            "l3": l3_metrics,
            "l4": self.assess_l4_reference_quality_fn(),
            "l5": (
                self.assess_l5_index_quality_fn(collection_name=l5_collection_name)
                if l5_collection_name
                else self.assess_l5_index_quality_fn()
            ),
        }
        step_findings: list[dict[str, Any]] = []
        for stage in step_metrics.values():
            step_findings.extend(stage.get("findings", []))
        l5_agg = step_metrics.get("l5", {}).get("aggregate", {})
        vector_path = l5_agg.get("vector_path")
        vector_file_sha256 = self.sha256_file_fn(vector_path)
        return step_metrics, step_findings, vector_path, vector_file_sha256, l5_agg

    def _build_dataset(
        self,
        config: AssessmentConfig,
        vector_file_sha256: str | None,
        *,
        frozen_review_dataset: list[dict[str, Any]] | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
        """Stage 6: build a dataset, or retain reviewed frozen rows unchanged."""
        if frozen_review_dataset is not None:
            return (
                frozen_review_dataset,
                [],
                {
                    "dataset_path": str(config.dataset_path),
                    "source": "explicit_frozen_review_dataset",
                    "fixture_records": len(frozen_review_dataset),
                    "synthetic_records": 0,
                    "merged_records": len(frozen_review_dataset),
                },
            )
        dataset_kwargs = {
            "dataset_path": config.dataset_path,
            "enable_llm_generation": not config.disable_llm_generation,
            "max_synthetic_questions": config.max_synthetic_questions,
            "sample_docs_per_source_type": config.sample_docs_per_source_type,
            "seed": config.seed,
            "max_queries": config.max_queries,
            "sample_seed": config.sample_seed,
            "reuse_cached_dataset": config.reuse_cached_dataset,
            "reuse_requirements": {
                "experiment_index_config_hash": (
                    (config.experiment_config or {}).get("index_config_hash")
                ),
                "vector_file_sha256": vector_file_sha256,
            },
            "artifact_dir": config.artifact_dir,
            "dataset_split": config.dataset_split,
            "min_label_confidence": config.min_label_confidence,
        }
        if config.execution_mode == "benchmark":
            builder_parameters = inspect.signature(self.build_retrieval_dataset_fn).parameters
            if "benchmark_mode" in builder_parameters or any(
                parameter.kind is inspect.Parameter.VAR_KEYWORD
                for parameter in builder_parameters.values()
            ):
                dataset_kwargs["benchmark_mode"] = True
            else:
                raise ValueError("Benchmark dataset builder does not support frozen mode")
        dataset_bundle = self.build_retrieval_dataset_fn(**dataset_kwargs)
        dataset = dataset_bundle["dataset"]
        generation_attempts = dataset_bundle.get("generation_attempts", [])
        dataset_stats = dataset_bundle.get("stats", {})
        return dataset, generation_attempts, dataset_stats

    def _run_retrieval_stage(
        self,
        config: AssessmentConfig,
        dataset: list[dict[str, Any]],
        l5_collection_name: str | None,
        *,
        review_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Stage 7: retrieval metrics + ablation families (with re-ingest closures)."""
        evaluator_kwargs: dict[str, Any] = {}
        if config.retrieval_options:
            evaluator_kwargs["retrieval_options"] = config.retrieval_options
        if review_context is not None:
            _validate_review_evaluator_support(self.evaluate_retrieval_fn)
            evaluator_kwargs["review_context"] = review_context
        retrieval_rows, retrieval_metrics = self.evaluate_retrieval_fn(
            dataset, config.top_k, **evaluator_kwargs
        )
        retrieval_ablations: dict[str, Any] = {}
        if config.run_retrieval_ablations:
            retrieval_ablations = self.run_retrieval_ablations_fn(
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
                    self.configure_runtime_for_experiment_fn(exp)
                    self.initialize_runtime_index_fn(rebuild=True, force_html_convert=True)

                hype_ablations = self.run_hype_ablations_with_reingest_fn(
                    dataset,
                    config.top_k,
                    base_options=config.retrieval_options,
                    base_collection_name=l5_collection_name,
                    reconfigure_and_rebuild_fn=_rebuild_hype_index,
                )
            else:
                hype_ablations = self.run_hype_ablations_fn(
                    dataset, config.top_k, base_options=config.retrieval_options
                )
        reranking_ablations: dict[str, Any] = {}
        if config.run_reranking_ablations:
            reranking_ablations = self.run_reranking_ablations_fn(
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
                    self.configure_runtime_for_experiment_fn(exp)
                    self.initialize_runtime_index_fn(rebuild=True, force_html_convert=False)

                keyword_ablations = self.run_keyword_ablations_with_reingest_fn(
                    dataset,
                    config.top_k,
                    base_options=config.retrieval_options,
                    base_collection_name=l5_collection_name,
                    reconfigure_and_rebuild_fn=_rebuild_keyword_index,
                )
            else:
                keyword_ablations = self.run_keyword_ablations_fn(
                    dataset, config.top_k, base_options=config.retrieval_options
                )
        diversity_sweep_rows: list[dict[str, Any]] = []
        if config.run_diversity_sweep:
            diversity_sweep_rows = self.run_diversity_sweep_fn(
                dataset,
                config.top_k,
                base_options=config.retrieval_options,
                mmr_lambda_values=config.diversity_sweep.get("mmr_lambda_values"),
                overfetch_multipliers=config.diversity_sweep.get("overfetch_multipliers"),
                max_chunks_per_source_page_values=config.diversity_sweep.get(
                    "max_chunks_per_source_page_values"
                ),
                max_chunks_per_source_values=config.diversity_sweep.get(
                    "max_chunks_per_source_values"
                ),
            )
        return {
            "retrieval_rows": retrieval_rows,
            "retrieval_metrics": retrieval_metrics,
            "retrieval_ablations": retrieval_ablations,
            "hype_ablations": hype_ablations,
            "reranking_ablations": reranking_ablations,
            "keyword_ablations": keyword_ablations,
            "diversity_sweep_rows": diversity_sweep_rows,
        }

    def _run_answer_eval(
        self,
        config: AssessmentConfig,
        dataset: list[dict[str, Any]],
        vector_file_sha256: str | None,
        *,
        cache_dir: Path | None = None,
        execution_snapshot: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Stage 8: L6 answer-quality evaluation (LLM-as-judge)."""
        l6_answer_quality_rows: list[dict[str, Any]] = []
        l6_answer_quality_metrics: dict[str, Any] = {
            "status": "not_applicable",
            "reason": "disabled",
        }
        if config.include_answer_eval and not config.disable_llm_judging:
            l6_answer_quality_rows, l6_answer_quality_metrics = self.evaluate_answers_fn(
                dataset,
                config.top_k,
                cache_dir=cache_dir
                if cache_dir is not None
                else Path(settings.deepeval.deepeval_cache_dir),
                retrieval_options=config.retrieval_options,
                cache_namespace={
                    "retrieval_mode": config.retrieval_mode,
                    "experiment_index_config_hash": (
                        (config.experiment_config or {}).get("index_config_hash")
                    ),
                    "experiment_variant": ((config.experiment_config or {}).get("variant_name")),
                    "vector_file_sha256": vector_file_sha256,
                    "execution_snapshot": execution_snapshot or {},
                },
            )
        elif config.include_answer_eval and config.disable_llm_judging:
            l6_answer_quality_metrics = {"status": "skipped", "reason": "llm_judging_disabled"}
        return l6_answer_quality_rows, l6_answer_quality_metrics

    def _run_replay(
        self, params: AssessmentRunParams, attempt_state: dict[str, Any]
    ) -> AssessmentResult:
        if not params.replay_snapshot:
            raise ValueError("Replay mode requires an explicit replay_snapshot path")
        if params.index_snapshot_path is not None:
            raise ValueError("index_snapshot_path is only valid in benchmark mode")
        if params.generation_implementation != "existing" or params.harness != "deterministic_rag":
            raise ValueError("Unsupported replay execution axes")
        source_path = Path(params.replay_snapshot)
        if source_path.is_symlink():
            raise ValueError("Replay snapshot path is not supported")
        manifest_path = source_path / "manifest.json" if source_path.is_dir() else source_path
        if manifest_path.name != "manifest.json" or manifest_path.is_symlink():
            raise ValueError("Replay snapshot must name a benchmark run directory or manifest.json")
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raise ValueError("Replay snapshot manifest is unavailable or invalid") from None
        if not isinstance(manifest, dict):
            raise ValueError("Replay snapshot manifest is invalid")
        identity = manifest.get("identity", {})
        index_identity = manifest.get("index_snapshot", {})
        index_execution = manifest.get("index_execution", {})
        input_provenance = manifest.get("input_provenance", {})
        config_payload = manifest.get("config", {})
        replay_snapshot = manifest.get("replay_snapshot", {})
        if not all(
            isinstance(value, dict)
            for value in (
                identity,
                index_identity,
                index_execution,
                input_provenance,
                config_payload,
                replay_snapshot,
            )
        ):
            raise ValueError("Replay snapshot manifest is invalid")
        source = input_provenance.get("source", {})
        corpus = input_provenance.get("corpus", {})
        execution_snapshot = config_payload.get("execution_snapshot", {})
        if not all(isinstance(value, dict) for value in (source, corpus, execution_snapshot)):
            raise ValueError("Replay snapshot manifest is invalid")
        identity_index = identity.get("index", {})
        snapshot_dataset = execution_snapshot.get("dataset", {})
        snapshot_source = execution_snapshot.get("source", {})
        snapshot_corpus = execution_snapshot.get("corpus", {})
        snapshot_retrieval = execution_snapshot.get("retrieval", {})
        if not all(
            isinstance(value, dict)
            for value in (
                identity_index,
                snapshot_dataset,
                snapshot_source,
                snapshot_corpus,
                snapshot_retrieval,
            )
        ):
            raise ValueError("Replay snapshot manifest is invalid")
        snapshot_index_execution = snapshot_retrieval.get("index_execution", {})
        if not isinstance(snapshot_index_execution, dict):
            raise ValueError("Replay snapshot manifest is invalid")
        if (
            manifest.get("execution_mode") != "benchmark"
            or manifest.get("identity_contract_version") != IDENTITY_CONTRACT_VERSION
            or manifest.get("execution_status") != "completed"
            or index_execution.get("actual_index_path_verified") is not True
            or index_execution.get("retrieval_routed_to_snapshot") is not True
            or snapshot_index_execution.get("actual_index_path_verified") is not True
            or snapshot_index_execution.get("retrieval_routed_to_snapshot") is not True
            or replay_snapshot.get("contract_version") != REPLAY_SNAPSHOT_CONTRACT_VERSION
            or replay_snapshot.get("eligible") is not True
            or identity.get("status") != "verified"
            or not identity.get("semantic_fingerprint")
            or index_identity.get("status") != "verified"
            or index_identity.get("fingerprint") != identity_index.get("fingerprint")
            or source.get("status") != "verified"
            or not source.get("source_content_sha256")
            or not source.get("dependency_lock_sha256")
            or corpus.get("status") != "verified"
            or not corpus.get("content_sha256")
            or not input_provenance.get("dataset_file_sha256")
            or snapshot_dataset.get("file_sha256") != input_provenance.get("dataset_file_sha256")
            or not snapshot_dataset.get("case_ids_sha256")
            or snapshot_source.get("source_content_sha256") != source.get("source_content_sha256")
            or snapshot_corpus.get("content_sha256") != corpus.get("content_sha256")
            or build_run_identity(
                config={
                    "identity_contract_version": IDENTITY_CONTRACT_VERSION,
                    "execution_snapshot": execution_snapshot,
                    "index_fingerprint": index_identity.get("fingerprint"),
                },
                git_head=None,
            )
            != identity.get("semantic_fingerprint")
        ):
            raise ValueError("Replay snapshot lacks verified benchmark provenance")

        allowed_names = {
            "retrieval_dataset.json",
            "retrieval_results.jsonl",
            "retrieval_metrics.json",
            L6_ANSWER_QUALITY_ROWS,
            L6_ANSWER_QUALITY_METRICS,
        }
        recorded_hashes = replay_snapshot.get("artifact_sha256")
        if not isinstance(recorded_hashes, dict) or set(recorded_hashes) != allowed_names:
            raise ValueError("Replay snapshot artifact inventory is incomplete")
        run_dir = manifest_path.parent
        artifacts: dict[str, Any] = {}
        actual_hashes: dict[str, str] = {}
        try:
            for name in sorted(allowed_names):
                path = run_dir / name
                if path.is_symlink() or not path.is_file():
                    raise ValueError("Replay snapshot artifact is unavailable")
                digest = self.sha256_file_fn(path)
                if not isinstance(digest, str) or digest != recorded_hashes.get(name):
                    raise ValueError("Replay snapshot artifact checksum mismatch")
                actual_hashes[name] = digest
                if name.endswith(".jsonl"):
                    artifacts[name] = [
                        json.loads(line)
                        for line in path.read_text(encoding="utf-8").splitlines()
                        if line.strip()
                    ]
                else:
                    artifacts[name] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raise ValueError("Replay snapshot artifact content is invalid") from None
        if build_run_identity(config=actual_hashes, git_head=None) != replay_snapshot.get(
            "payload_sha256"
        ):
            raise ValueError("Replay snapshot payload identity mismatch")
        if (
            not isinstance(artifacts.get("retrieval_dataset.json"), list)
            or not isinstance(artifacts.get("retrieval_results.jsonl"), list)
            or not isinstance(artifacts.get("retrieval_metrics.json"), dict)
            or not isinstance(artifacts.get(L6_ANSWER_QUALITY_ROWS), list)
            or not isinstance(artifacts.get(L6_ANSWER_QUALITY_METRICS), dict)
        ):
            raise ValueError("Replay snapshot artifact types are invalid")

        store = ArtifactStore(Path(params.artifact_dir), params.name or "replay")
        attempt_state["store"] = store
        telemetry = current_telemetry()
        telemetry_contexts = attempt_state.get("telemetry_contexts")
        if telemetry is not None and isinstance(telemetry_contexts, ExitStack):
            telemetry_contexts.enter_context(telemetry.run_id_context(store.execution_id))
        replay_identity = dict(identity)
        replay_identity["reuse_eligible"] = False
        replay_identity["cohort_eligible"] = False
        replay_identity["promotion_eligible"] = False
        replay_manifest = {
            "artifact_contract_version": ARTIFACT_CONTRACT_VERSION,
            "identity_contract_version": IDENTITY_CONTRACT_VERSION,
            "execution_id": store.execution_id,
            "execution_mode": "replay",
            "execution_status": "replayed",
            "identity": replay_identity,
            "replay_of": {
                "execution_id": manifest.get("execution_id"),
                "semantic_fingerprint": identity["semantic_fingerprint"],
            },
            "measurement": {"status": "not_applicable", "reason": "replay_is_not_a_sample"},
            "quality_gate": "not_applicable",
            "generation_sample": False,
            "latency_sample": False,
            "cache_policy": {
                "version": 1,
                "mode": "replay",
                "run_reuse": False,
                "persistent_reuse": False,
            },
        }
        attempt_state["manifest"] = replay_manifest
        store.write_json("replay_snapshot.json", {"manifest": manifest, "artifacts": artifacts})
        store.write_json("manifest.json", replay_manifest)
        summary = {
            "artifact_contract_version": ARTIFACT_CONTRACT_VERSION,
            "identity_contract_version": IDENTITY_CONTRACT_VERSION,
            "execution_id": store.execution_id,
            "execution_mode": "replay",
            "execution_status": "replayed",
            "status": "replay",
            "identity": replay_identity,
            "replay_of": replay_manifest["replay_of"],
            "measurement": replay_manifest["measurement"],
            "quality_gate": "not_applicable",
            "generation_sample": False,
            "latency_sample": False,
            "run_dir": str(store.run_dir),
        }
        store.write_json("summary.json", summary)
        update_run_index(
            Path(params.artifact_dir),
            run_identity=store.execution_id,
            run_dir=store.run_dir,
            status="replayed",
        )
        return AssessmentResult(
            run_dir=store.run_dir, status="replay", failed_thresholds=[], summary=summary
        )

    def _finalize(
        self,
        *,
        config: AssessmentConfig,
        start: float,
        run_identity: str,
        store: ArtifactStore,
        manifest: dict[str, Any],
        step_metrics: dict[str, Any],
        step_findings: list[dict[str, Any]],
        vector_path: Any,
        vector_file_sha256: str | None,
        l5_agg: dict[str, Any],
        dataset: list[dict[str, Any]],
        dataset_stats: dict[str, Any],
        generation_attempts: list[dict[str, Any]],
        retrieval: dict[str, Any],
        l6_answer_quality_rows: list[dict[str, Any]],
        l6_answer_quality_metrics: dict[str, Any],
        identity: dict[str, Any],
        index_identity: dict[str, Any],
        provider_usage: dict[str, Any] | None = None,
    ) -> AssessmentResult:
        """Stage 9: thresholds, manifest enrichment, artifacts, summary, tracking."""
        retrieval_rows = retrieval["retrieval_rows"]
        retrieval_metrics = retrieval["retrieval_metrics"]
        retrieval_ablations = retrieval["retrieval_ablations"]
        hype_ablations = retrieval["hype_ablations"]
        reranking_ablations = retrieval["reranking_ablations"]
        keyword_ablations = retrieval["keyword_ablations"]
        diversity_sweep_rows = retrieval["diversity_sweep_rows"]
        index_preparation = manifest.get("index_preparation", {})
        l3_agg = step_metrics.get("l3", {}).get("aggregate", {})
        failed_thresholds = self.evaluate_thresholds_fn(
            step_metrics,
            retrieval_metrics,
            l6_answer_quality_metrics,
            config.thresholds,
        )
        measurement = measurement_summary(
            expected=len(dataset),
            retrieval_metrics=retrieval_metrics,
            answer_metrics=l6_answer_quality_metrics,
            include_answer_eval=config.include_answer_eval,
            execution_mode=config.execution_mode,
        )
        if any(
            f.get("reason") in {"missing_required_metric", "invalid_metric"}
            for f in failed_thresholds
        ):
            measurement["status"] = "incomplete"
        index_execution = manifest.get("index_execution", {})
        if config.execution_mode == "benchmark" and (
            index_execution.get("actual_index_path_verified") is not True
            or index_execution.get("retrieval_routed_to_snapshot") is not True
        ):
            measurement["status"] = "incomplete"
            measurement["reason"] = "frozen_snapshot_retrieval_not_wired"
        quality_gate = (
            "incomplete"
            if measurement["status"] != "complete"
            else "failed"
            if failed_thresholds
            else "passed"
        )
        status = "ok" if quality_gate == "passed" else quality_gate
        usage_by_role = _usage_by_role(manifest, provider_usage or {})
        usage_summary = build_usage_summary(
            store.execution_id,
            usage_by_role=usage_by_role,
            unknowns=(provider_usage or {}).get("unknowns", []),
        )
        # Preserve fail-closed measurement semantics while producing valid JSON.
        # Invalid values never become reusable successful measurements.
        step_metrics = _finite_metric_values(step_metrics)
        retrieval_metrics = _finite_metric_values(retrieval_metrics)
        l6_answer_quality_metrics = _finite_metric_values(l6_answer_quality_metrics)
        l6_answer_quality_rows = _finite_metric_values(l6_answer_quality_rows)
        retrieval_rows = _finite_metric_values(retrieval_rows)
        retrieval_ablations = _finite_metric_values(retrieval_ablations)
        hype_ablations = _finite_metric_values(hype_ablations)
        keyword_ablations = _finite_metric_values(keyword_ablations)
        reranking_ablations = _finite_metric_values(reranking_ablations)
        diversity_sweep_rows = _finite_metric_values(diversity_sweep_rows)
        failed_thresholds = _finite_metric_values(failed_thresholds)
        manifest.update(
            {
                "execution_status": "completed",
                "execution_mode": config.execution_mode,
                "identity": identity,
                "index_snapshot": index_identity,
                "measurement": measurement,
                "quality_gate": quality_gate,
                "usage_summary": usage_summary,
            }
        )
        step_findings.extend(
            {
                "severity": "error",
                "stage": "threshold",
                "message": "Required measurement or quality threshold not satisfied",
                **f,
            }
            for f in failed_thresholds
        )

        step_findings = _finite_metric_values(step_findings)
        dataset_stats = _finite_metric_values(dataset_stats)
        generation_attempts = _finite_metric_values(generation_attempts)
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
        if vector_path and Path(vector_path).is_file():
            try:
                index_payload = json.loads(Path(vector_path).read_text(encoding="utf-8"))
                index_metadata = index_payload.get("index_metadata", {}) or {}
            except Exception as e:
                logger.debug("Failed to load index metadata from %s: %s", vector_path, e)
                index_metadata = {}
        manifest["index_provenance"] = {
            "collection_name": index_metadata.get(
                "collection_name", settings.storage.collection_name
            ),
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
            "dataset_file_sha256": self.sha256_file_fn(dataset_file),
        }
        manifest = _finite_metric_values(manifest)
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

        replay_artifact_names = (
            "retrieval_dataset.json",
            "retrieval_results.jsonl",
            "retrieval_metrics.json",
            L6_ANSWER_QUALITY_ROWS,
            L6_ANSWER_QUALITY_METRICS,
        )
        replay_artifact_hashes = {
            name: self.sha256_file_fn(store.path(name)) for name in replay_artifact_names
        }
        replay_ready = bool(
            config.execution_mode == "benchmark"
            and manifest.get("index_execution", {}).get("actual_index_path_verified") is True
            and manifest.get("index_execution", {}).get("retrieval_routed_to_snapshot") is True
            and measurement.get("status") == "complete"
            and identity.get("status") == "verified"
            and identity.get("semantic_fingerprint")
            and index_identity.get("status") == "verified"
            and all(isinstance(value, str) for value in replay_artifact_hashes.values())
        )
        manifest["replay_snapshot"] = {
            "contract_version": REPLAY_SNAPSHOT_CONTRACT_VERSION,
            "eligible": replay_ready,
            "artifact_sha256": replay_artifact_hashes,
            "payload_sha256": build_run_identity(config=replay_artifact_hashes, git_head=None)
            if replay_ready
            else None,
        }

        summary = {
            "artifact_contract_version": ARTIFACT_CONTRACT_VERSION,
            "execution_id": store.execution_id,
            "identity": manifest["identity"],
            "effective_roles": manifest.get("effective_roles", {}),
            "index_execution": manifest.get("index_execution", {}),
            "usage_summary": usage_summary,
            "cache_policy": manifest["cache_policy"],
            "measurement_contract_version": MEASUREMENT_CONTRACT_VERSION,
            "identity_contract_version": IDENTITY_CONTRACT_VERSION,
            "execution_mode": config.execution_mode,
            "execution_status": "completed",
            "replay_snapshot": manifest["replay_snapshot"],
            "measurement": measurement,
            "quality_gate": quality_gate,
            "required_metrics": manifest["required_metrics"],
            "failed_thresholds": failed_thresholds,
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
            "status": status,
            "dedup": {
                "reused_existing_run": False,
                "run_identity": run_identity,
                "force_rerun": bool(config.force_rerun),
            },
        }
        render_kwargs = {
            "step_metrics": step_metrics,
            "retrieval_metrics": retrieval_metrics,
            "l6_answer_quality_metrics": l6_answer_quality_metrics,
            "dataset_stats": dataset_stats,
            "failed_thresholds": failed_thresholds,
        }
        try:
            render_parameters = dict(inspect.signature(self.render_summary_fn).parameters)
        except (TypeError, ValueError):
            render_parameters = {}
        accepts_extra = any(
            parameter.kind is inspect.Parameter.VAR_KEYWORD
            for parameter in render_parameters.values()
        )
        if "usage_summary" in render_parameters or accepts_extra:
            render_kwargs["usage_summary"] = usage_summary
        summary_markdown = self.render_summary_fn(**render_kwargs)
        if "usage_summary" not in render_kwargs:
            summary_markdown += (
                "\n## Usage Summary\n"
                f"- Status: {usage_summary['status']}\n"
                f"- Unknowns: {', '.join(usage_summary['unknowns'])}\n"
                "- Token and cash amounts are unknown unless reported by the provider.\n"
            )
        store.write_text("summary.md", summary_markdown)
        tracking_info = self.log_assessment_to_wandb_fn(
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
        update_run_index(
            config.artifact_dir, run_identity=store.execution_id, run_dir=store.run_dir
        )

        return AssessmentResult(
            run_dir=store.run_dir,
            status=status,
            failed_thresholds=failed_thresholds,
            summary=summary,
        )


def run_assessment(
    *,
    artifact_dir: str | Path = "data/evals",
    execution_mode: str = "diagnostic",
    generation_implementation: str = "existing",
    harness: str = "deterministic_rag",
    replay_snapshot: str | Path | None = None,
    index_snapshot_path: str | Path | None = None,
    execution_order: int | None = None,
    name: str | None = None,
    dataset_path: str | Path | None = None,
    review_manifest_path: str | Path | None = None,
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
    skip_ingestion: bool = False,
    experiment_config: dict[str, Any] | None = None,
    audit_l0_download_fn: Callable[[], dict[str, Any]] | None = None,
    assess_l1_html_markdown_quality_fn: Callable[[], dict[str, Any]] | None = None,
    assess_l2_pdf_quality_fn: Callable[[], dict[str, Any]] | None = None,
    assess_l3_chunking_quality_fn: Callable[[], dict[str, Any]] | None = None,
    assess_l4_reference_quality_fn: Callable[[], dict[str, Any]] | None = None,
    assess_l5_index_quality_fn: Callable[..., dict[str, Any]] | None = None,
    build_retrieval_dataset_fn: Callable[..., dict[str, Any]] | None = None,
    evaluate_retrieval_fn: Callable[..., tuple[list[dict[str, Any]], dict[str, Any]]] | None = None,
    evaluate_answers_fn: Callable[..., tuple[list[dict[str, Any]], dict[str, Any]]] | None = None,
    evaluate_thresholds_fn: Callable[..., list[dict[str, Any]]] | None = None,
    git_head_fn: Callable[[], str | None] | None = None,
    source_provenance_fn: Callable[[], dict[str, Any]] | None = None,
    corpus_provenance_fn: Callable[[Path], dict[str, Any]] | None = None,
    capture_index_snapshot_fn: Callable[[str | None], dict[str, Any]] | None = None,
    configure_runtime_for_experiment_fn: Callable[[dict[str, Any] | None], dict[str, Any]]
    | None = None,
    initialize_runtime_index_fn: Callable[..., dict[str, Any]] | None = None,
    log_assessment_to_wandb_fn: Callable[..., dict[str, Any]] | None = None,
    run_retrieval_ablations_fn: Callable[..., dict[str, Any]] | None = None,
    run_hype_ablations_fn: Callable[..., dict[str, Any]] | None = None,
    run_keyword_ablations_fn: Callable[..., dict[str, Any]] | None = None,
    run_keyword_ablations_with_reingest_fn: Callable[..., dict[str, Any]] | None = None,
    run_hype_ablations_with_reingest_fn: Callable[..., dict[str, Any]] | None = None,
    run_reranking_ablations_fn: Callable[..., dict[str, Any]] | None = None,
    run_diversity_sweep_fn: Callable[..., list[dict[str, Any]]] | None = None,
    render_summary_fn: Callable[..., str] | None = None,
    sha256_file_fn: Callable[[str | Path | None], str | None] | None = None,
) -> AssessmentResult:
    params = AssessmentRunParams(
        artifact_dir=artifact_dir,
        execution_mode=execution_mode,
        generation_implementation=generation_implementation,
        harness=harness,
        replay_snapshot=replay_snapshot,
        index_snapshot_path=index_snapshot_path,
        execution_order=execution_order,
        name=name,
        dataset_path=dataset_path,
        review_manifest_path=review_manifest_path,
        top_k=top_k,
        max_synthetic_questions=max_synthetic_questions,
        disable_llm_generation=disable_llm_generation,
        disable_llm_judging=disable_llm_judging,
        include_answer_eval=include_answer_eval,
        sample_docs_per_source_type=sample_docs_per_source_type,
        seed=seed,
        max_queries=max_queries,
        sample_seed=sample_seed,
        reuse_cached_dataset=reuse_cached_dataset,
        fail_on_thresholds=fail_on_thresholds,
        thresholds_file=thresholds_file,
        dataset_split=dataset_split,
        min_label_confidence=min_label_confidence,
        retrieval_mode=retrieval_mode,
        disable_page_classification=disable_page_classification,
        disable_structured_chunking=disable_structured_chunking,
        disable_bm25=disable_bm25,
        export_failed_generations=export_failed_generations,
        force_rerun=force_rerun,
        retrieval_options=retrieval_options or {},
        run_retrieval_ablations=run_retrieval_ablations,
        run_hype_ablations=run_hype_ablations,
        run_keyword_ablations=run_keyword_ablations,
        run_reranking_ablations=run_reranking_ablations,
        run_diversity_sweep=run_diversity_sweep,
        diversity_sweep=diversity_sweep or {},
        skip_ingestion=skip_ingestion,
        experiment_config=experiment_config,
    )
    return AssessmentPipeline(
        audit_l0_download_fn=audit_l0_download_fn
        if audit_l0_download_fn is not None
        else audit_l0_download,
        assess_l1_html_markdown_quality_fn=assess_l1_html_markdown_quality_fn
        if assess_l1_html_markdown_quality_fn is not None
        else assess_l1_html_markdown_quality,
        assess_l2_pdf_quality_fn=assess_l2_pdf_quality_fn
        if assess_l2_pdf_quality_fn is not None
        else assess_l2_pdf_quality,
        assess_l3_chunking_quality_fn=assess_l3_chunking_quality_fn
        if assess_l3_chunking_quality_fn is not None
        else assess_l3_chunking_quality,
        assess_l4_reference_quality_fn=assess_l4_reference_quality_fn
        if assess_l4_reference_quality_fn is not None
        else assess_l4_reference_quality,
        assess_l5_index_quality_fn=assess_l5_index_quality_fn
        if assess_l5_index_quality_fn is not None
        else assess_l5_index_quality,
        build_retrieval_dataset_fn=build_retrieval_dataset_fn
        if build_retrieval_dataset_fn is not None
        else build_retrieval_dataset,
        evaluate_retrieval_fn=evaluate_retrieval_fn
        if evaluate_retrieval_fn is not None
        else evaluate_retrieval,
        evaluate_answers_fn=evaluate_answers_fn
        if evaluate_answers_fn is not None
        else evaluate_answer_quality,
        evaluate_thresholds_fn=evaluate_thresholds_fn
        if evaluate_thresholds_fn is not None
        else evaluate_thresholds,
        git_head_fn=git_head_fn if git_head_fn is not None else git_head,
        source_provenance_fn=source_provenance_fn
        if source_provenance_fn is not None
        else source_provenance,
        corpus_provenance_fn=corpus_provenance_fn
        if corpus_provenance_fn is not None
        else content_directory_provenance,
        capture_index_snapshot_fn=capture_index_snapshot_fn
        if capture_index_snapshot_fn is not None
        else capture_index_snapshot,
        configure_runtime_for_experiment_fn=configure_runtime_for_experiment_fn
        if configure_runtime_for_experiment_fn is not None
        else configure_runtime_for_experiment,
        initialize_runtime_index_fn=initialize_runtime_index_fn
        if initialize_runtime_index_fn is not None
        else initialize_runtime_index,
        log_assessment_to_wandb_fn=log_assessment_to_wandb_fn
        if log_assessment_to_wandb_fn is not None
        else log_assessment_to_wandb,
        run_retrieval_ablations_fn=run_retrieval_ablations_fn
        if run_retrieval_ablations_fn is not None
        else _run_retrieval_ablations,
        run_hype_ablations_fn=run_hype_ablations_fn
        if run_hype_ablations_fn is not None
        else _run_hype_ablations,
        run_keyword_ablations_fn=run_keyword_ablations_fn
        if run_keyword_ablations_fn is not None
        else _run_keyword_ablations,
        run_keyword_ablations_with_reingest_fn=run_keyword_ablations_with_reingest_fn
        if run_keyword_ablations_with_reingest_fn is not None
        else run_keyword_ablations_with_reingest,
        run_hype_ablations_with_reingest_fn=run_hype_ablations_with_reingest_fn
        if run_hype_ablations_with_reingest_fn is not None
        else run_hype_ablations_with_reingest,
        run_reranking_ablations_fn=run_reranking_ablations_fn
        if run_reranking_ablations_fn is not None
        else _run_reranking_ablations,
        run_diversity_sweep_fn=run_diversity_sweep_fn
        if run_diversity_sweep_fn is not None
        else _run_diversity_sweep,
        render_summary_fn=render_summary_fn if render_summary_fn is not None else render_summary,
        sha256_file_fn=sha256_file_fn if sha256_file_fn is not None else sha256_file,
    ).run(params)
