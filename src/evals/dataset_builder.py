"""Build retrieval evaluation datasets from fixtures and optional LLM synthesis."""

from __future__ import annotations

import hashlib
import json
import logging
import random
import re
from pathlib import Path
from typing import Any

from src.config import settings
from src.ingestion.steps.chunking import chunk_documents
from src.ingestion.steps.load_markdown import get_markdown_documents
from src.ingestion.steps.load_pdfs import get_documents

logger = logging.getLogger(__name__)

_SPLIT_ORDER = {"dev": 0, "test": 1, "regression": 2}
_CONFIDENCE_ORDER = {"low": 0, "medium": 1, "high": 2}


def _source_family(value: str) -> str:
    lowered = str(value).lower()
    lowered = re.sub(r"\.(pdf|md|html)$", "", lowered)
    lowered = re.sub(r"[^a-z0-9]+", " ", lowered)
    return " ".join(lowered.split()[:3]).strip() or "unknown"


def _assign_split(source: str) -> str:
    family = _source_family(source)
    bucket = int(hashlib.sha256(family.encode("utf-8")).hexdigest(), 16) % 10
    if bucket <= 4:
        return "dev"
    if bucket <= 7:
        return "test"
    return "regression"


def _normalize_case_record(
    item: dict[str, Any],
    *,
    default_origin: str,
    dataset_version: str,
    dataset_id: str | None = None,
    default_label_origin: str | None = None,
    default_review_status: str = "unreviewed",
) -> dict[str, Any]:
    query = str(item.get("query") or item.get("question") or "").strip()
    sources = list(item.get("expected_sources") or [])
    source = str(sources[0]) if sources else "unknown"
    source_family = str(item.get("source_family") or _source_family(source))
    split = str(item.get("dataset_split") or _assign_split(source))
    origin = str(item.get("dataset_origin") or default_origin)
    explicit_id = item.get("query_id") or item.get("case_id")
    stable_key = json.dumps(
        [query.casefold(), split, source_family, origin],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    query_id = str(
        explicit_id or f"case_{hashlib.sha256(stable_key.encode('utf-8')).hexdigest()[:16]}"
    )
    label_origin = str(
        item.get("label_origin")
        or default_label_origin
        or ("synthetic" if "synthetic" in origin else "heuristic")
    )
    record = dict(item)
    record.update(
        {
            "query_id": query_id,
            "case_id": str(item.get("case_id") or query_id),
            "query": query,
            "expected_keywords": list(item.get("expected_keywords", [])),
            "expected_sources": sources,
            "expected_source_types": list(item.get("expected_source_types", [])),
            "query_category": item.get("query_category", "anchor"),
            "task_type": item.get("task_type"),
            "evidence_phrase": item.get("evidence_phrase"),
            "evidence_span": item.get("evidence_span") or item.get("evidence_phrase"),
            "evidence_passages": list(item.get("evidence_passages", [])),
            "expected_chunk_id": item.get("expected_chunk_id"),
            "expected_page": item.get("expected_page"),
            "label_confidence": item.get("label_confidence", "low"),
            "label_origin": label_origin,
            "review_status": str(item.get("review_status", default_review_status)),
            "dataset_origin": origin,
            "dataset_version": str(item.get("dataset_version") or dataset_version),
            "dataset_id": str(item.get("dataset_id") or dataset_id or "legacy-unversioned"),
            "dataset_split": split,
            "difficulty": item.get("difficulty", "medium"),
            "negative_query": item.get("negative_query"),
            "source_family": source_family,
        }
    )
    if "answerability" not in record:
        record["answerability"] = "answerable"
    return record


def normalize_golden_queries(fixture_path: Path) -> list[dict[str, Any]]:
    data = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
    version = str(data.get("schema_version", "legacy-unversioned"))
    records = [
        _normalize_case_record(
            item,
            default_origin=str(data.get("dataset_origin", "golden_fixture")),
            dataset_version=version,
            dataset_id=data.get("dataset_id"),
            default_label_origin=data.get("label_origin"),
            default_review_status=str(data.get("review_status", "unreviewed")),
        )
        for item in data.get("golden_queries", [])
    ]
    return [record for record in records if record["query"]]


def normalize_golden_conversations(fixture_path: Path) -> list[dict[str, Any]]:
    """Normalize multi-turn conversation golden data from fixture file.

    Args:
        fixture_path: Path to golden_conversations.json

    Returns:
        List of normalized conversation records suitable for evaluation
    """
    data = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
    version = str(data.get("schema_version", "legacy-unversioned"))
    records = []
    for item in data.get("golden_conversations", []):
        turns = item.get("turns", [])
        user_turns = [t for t in turns if t.get("role") == "user"]
        scenario = str(item.get("scenario", "")).strip()
        source_family = str(item.get("source_family", "unknown"))
        stable_material = json.dumps(
            [scenario, turns, source_family], sort_keys=True, ensure_ascii=False
        )
        conversation_id = str(
            item.get("conversation_id")
            or f"conversation_{hashlib.sha256(stable_material.encode('utf-8')).hexdigest()[:16]}"
        )
        origin = str(item.get("dataset_origin", data.get("dataset_origin", "golden_fixture")))
        records.append(
            {
                "conversation_id": conversation_id,
                "case_id": conversation_id,
                "dataset_origin": origin,
                "dataset_version": str(item.get("dataset_version") or version),
                "label_origin": str(
                    item.get("label_origin")
                    or data.get("label_origin")
                    or ("synthetic" if "synthetic" in origin else "heuristic")
                ),
                "review_status": str(
                    item.get("review_status", data.get("review_status", "unreviewed"))
                ),
                "scenario": scenario,
                "conversation_category": item.get("conversation_category", "contextual_followup"),
                "turns": turns,
                "user_turn_count": len(user_turns),
                "expected_outcome": item.get("expected_outcome", "").strip(),
                "turn_level_expected_keywords": list(item.get("turn_level_expected_keywords", [])),
                "turn_level_expected_sources": list(item.get("turn_level_expected_sources", [])),
                "context": list(item.get("context", [])),
                "difficulty": item.get("difficulty", "medium"),
                "dataset_split": item.get("dataset_split") or _assign_split(source_family),
                "source_family": source_family,
            }
        )
    return [r for r in records if r["turns"] and r["scenario"]]


def _normalize_cached_dataset(dataset_path: Path) -> list[dict[str, Any]]:
    data = json.loads(dataset_path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "golden_queries" in data:
        return normalize_golden_queries(dataset_path)
    if isinstance(data, dict) and "golden_conversations" in data:
        return normalize_golden_conversations(dataset_path)
    if isinstance(data, dict) and "cases" in data:
        version = str(data.get("schema_version", "unversioned"))
        origin = str(data.get("dataset_origin", "frozen_fixture"))
        cases = data.get("cases")
        if not isinstance(cases, list):
            raise ValueError("Versioned dataset 'cases' must be a list")
        return [
            record
            for item in cases
            if isinstance(item, dict)
            for record in [
                _normalize_case_record(
                    item,
                    default_origin=origin,
                    dataset_version=version,
                    dataset_id=str(data.get("dataset_id") or "versioned-dataset"),
                    default_label_origin=data.get("label_origin"),
                    default_review_status=str(data.get("review_status", "unreviewed")),
                )
            ]
            if record["query"]
        ]
    if isinstance(data, list):
        return [
            record
            for item in data
            if isinstance(item, dict)
            for record in [
                _normalize_case_record(
                    item, default_origin="explicit_dataset", dataset_version="unversioned"
                )
            ]
            if record["query"]
        ]
    raise ValueError(f"Unsupported dataset format in {dataset_path}")


def _json_checksum(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _resolve_path_for_contract(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve())
    except OSError as e:
        logger.warning("Path resolution failed for %s: %s", path, e)
        return str(path)


def _build_dataset_compatibility_contract(
    *,
    dataset_path: Path | None,
    enable_llm_generation: bool,
    max_synthetic_questions: int,
    sample_docs_per_source_type: int,
    seed: int,
    max_queries: int | None,
    sample_seed: int,
    dataset_split: str | None,
    min_label_confidence: str,
    reuse_requirements: dict[str, Any] | None,
    benchmark_mode: bool = False,
) -> dict[str, Any]:
    return {
        "dataset_path": _resolve_path_for_contract(dataset_path),
        "dataset_split": dataset_split,
        "min_label_confidence": min_label_confidence,
        "enable_llm_generation": bool(enable_llm_generation),
        "max_synthetic_questions": max_synthetic_questions if enable_llm_generation else 0,
        "sample_docs_per_source_type": sample_docs_per_source_type if enable_llm_generation else 0,
        "seed": seed if enable_llm_generation else 0,
        "max_queries": max_queries,
        "sample_seed": sample_seed,
        "reuse_requirements": dict(reuse_requirements or {}),
        **({"benchmark_mode": True} if benchmark_mode else {}),
    }


def _dataset_diagnostics(records: list[dict[str, Any]]) -> dict[str, Any]:
    query_groups: dict[str, list[str]] = {}
    family_splits: dict[str, set[str]] = {}
    for record in records:
        normalized_query = re.sub(r"\s+", " ", str(record.get("query", "")).casefold()).strip()
        if normalized_query:
            query_groups.setdefault(normalized_query, []).append(str(record.get("query_id", "")))
        family = str(record.get("source_family", "unknown")).strip().casefold()
        split = str(record.get("dataset_split", "unknown"))
        if family and family != "unknown":
            family_splits.setdefault(family, set()).add(split)
    duplicate_groups = [ids for ids in query_groups.values() if len(ids) > 1]
    overlaps = [
        {"source_family": family, "splits": sorted(splits)}
        for family, splits in sorted(family_splits.items())
        if len(splits) > 1
    ]
    return {
        "duplicate_query_detection": "normalized_exact_only",
        "near_duplicate_query_status": "not_assessed",
        "duplicate_query_group_count": len(duplicate_groups),
        "duplicate_query_case_ids": duplicate_groups,
        "source_family_overlap_count": len(overlaps),
        "source_family_overlaps": overlaps,
    }


def _sample_filtered_records(
    records: list[dict[str, Any]],
    *,
    max_queries: int | None,
    sample_seed: int,
) -> tuple[list[dict[str, Any]], bool]:
    if max_queries is None or max_queries <= 0 or len(records) <= max_queries:
        return records, False
    rng = random.Random(sample_seed)  # nosec B311
    chosen_indices = sorted(rng.sample(range(len(records)), max_queries))
    return [records[idx] for idx in chosen_indices], True


def _load_cached_dataset_manifest(run_dir: Path) -> dict[str, Any]:
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        return {}
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("Failed to read manifest at %s: %s", manifest_path, e)
        return {}
    return payload if isinstance(payload, dict) else {}


def _resolve_cached_dataset_path(
    compatibility_contract: dict[str, Any],
    *,
    artifact_dir: str | Path = "data/evals",
) -> tuple[Path | None, str | None, list[dict[str, Any]]]:
    evals_dir = Path(artifact_dir)
    latest_pointer = evals_dir / "latest_run.txt"
    candidate_run_dirs: list[Path] = []

    if latest_pointer.exists():
        latest_dir = Path(latest_pointer.read_text(encoding="utf-8").strip())
        if not latest_dir.is_absolute():
            latest_dir = Path.cwd() / latest_dir
        candidate_run_dirs.append(latest_dir)

    if evals_dir.exists():
        run_dirs = sorted(
            (path for path in evals_dir.iterdir() if path.is_dir()),
            key=lambda path: path.name,
            reverse=True,
        )
        candidate_run_dirs.extend(run_dirs)

    rejections: list[dict[str, Any]] = []
    seen: set[Path] = set()
    for run_dir in candidate_run_dirs:
        try:
            resolved = run_dir.resolve()
        except OSError as e:
            logger.warning("Path resolution failed for %s: %s", run_dir, e)
            resolved = run_dir
        if resolved in seen:
            continue
        seen.add(resolved)
        dataset_path = run_dir / "retrieval_dataset.json"
        if not dataset_path.exists():
            rejections.append({"run_dir": str(run_dir), "reason": "missing_dataset_file"})
            continue
        manifest = _load_cached_dataset_manifest(run_dir)
        previous_contract = (manifest.get("dataset") or {}).get("compatibility") or {}
        if not isinstance(previous_contract, dict) or not previous_contract:
            rejections.append({"run_dir": str(run_dir), "reason": "missing_dataset_compatibility"})
            continue
        if previous_contract != compatibility_contract:
            rejections.append(
                {
                    "run_dir": str(run_dir),
                    "reason": "incompatible_dataset_contract",
                    "expected": compatibility_contract,
                    "actual": previous_contract,
                }
            )
            continue
        return dataset_path, _resolve_path_for_contract(run_dir), rejections
    return None, None, rejections


def _source_type(source: str) -> str:
    s = source.lower()
    if s.endswith(".pdf"):
        return "pdf"
    if s.endswith(".csv"):
        return "csv"
    if s.endswith((".md", ".html")):
        return "html"
    return "other"


def _difficulty_for_chunk(chunk: dict[str, Any]) -> str:
    token_count = int(chunk.get("token_count_estimate", 0))
    if token_count >= 120:
        return "hard"
    if token_count >= 60:
        return "medium"
    return "easy"


def _load_candidate_chunks() -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    chunks.extend(chunk_documents(get_documents()))
    chunks.extend(chunk_documents(get_markdown_documents()))
    return chunks


def _sample_candidate_docs(sample_docs_per_source_type: int, seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)  # nosec B311
    docs = _load_candidate_chunks()
    buckets: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for doc in docs:
        key = (_source_type(str(doc.get("source", ""))), str(doc.get("content_type", "paragraph")))
        buckets.setdefault(key, []).append(doc)
    sampled: list[dict[str, Any]] = []
    for bucket in buckets.values():
        rng.shuffle(bucket)
        sampled.extend(bucket[:sample_docs_per_source_type])
    rng.shuffle(sampled)
    return sampled


def _build_seed_context(
    seed: dict[str, Any], chunk_map: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    context_chunks = [seed]
    for related_key in ("previous_chunk_id", "next_chunk_id"):
        related = chunk_map.get(str(seed.get(related_key)))
        if related:
            context_chunks.append(related)
    context_text = "\n\n".join(
        str(item.get("content", ""))[:900] for item in context_chunks if item.get("content")
    )
    return {
        "target_chunk": seed,
        "neighbor_chunks": [item for item in context_chunks if item.get("id") != seed.get("id")],
        "context_text": context_text[:3000],
    }


def _contains_source_leakage(question: str, source: str) -> bool:
    normalized_source = _source_family(source)
    lowered = question.lower()
    return normalized_source in lowered or ".pdf" in lowered or ".md" in lowered


def _looks_copied(question: str, evidence_span: str) -> bool:
    question_tokens = set(re.findall(r"[a-z0-9]+", question.lower()))
    evidence_tokens = set(re.findall(r"[a-z0-9]+", evidence_span.lower()))
    if not question_tokens or not evidence_tokens:
        return False
    overlap = len(question_tokens & evidence_tokens) / max(1, len(question_tokens))
    return overlap > 0.6


def _validate_synthetic_record(
    candidate: dict[str, Any], seed: dict[str, Any], context_text: str
) -> tuple[bool, str]:
    evidence_span = str(
        candidate.get("evidence_span") or candidate.get("evidence_phrase") or ""
    ).strip()
    answer_summary = str(candidate.get("answer_summary") or candidate.get("answer") or "").strip()
    query = str(candidate.get("query") or candidate.get("question") or "").strip()
    if not query:
        return False, "empty_question"
    if not evidence_span or evidence_span not in context_text:
        return False, "invalid_evidence_span"
    if _contains_source_leakage(query, str(seed.get("source", ""))):
        return False, "source_title_leakage"
    if _looks_copied(query, evidence_span):
        return False, "question_too_copied"
    if answer_summary and not any(
        token in context_text.lower()
        for token in re.findall(r"[a-z0-9]+", answer_summary.lower())[:3]
    ):
        return False, "answer_not_grounded"
    return True, "accepted"


def _extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise ValueError("No JSON object found")
    parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("Expected JSON object")
    return parsed


def _try_generate_synthetic_questions(
    *,
    max_synthetic_questions: int,
    sample_docs_per_source_type: int,
    seed: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    attempts: list[dict[str, Any]] = []
    accepted: list[dict[str, Any]] = []

    _dashscope_key = settings.llm.dashscope_api_key.get_secret_value()
    if not _dashscope_key:
        return accepted, [{"status": "skipped", "reason": "missing_dashscope_api_key"}]

    try:
        from openai import OpenAI
    except Exception as exc:  # pragma: no cover
        return accepted, [{"status": "skipped", "reason": f"openai_import_error: {exc}"}]

    candidates = _sample_candidate_docs(sample_docs_per_source_type, seed)
    if not candidates:
        return accepted, [{"status": "skipped", "reason": "no_candidate_docs"}]

    client = OpenAI(api_key=_dashscope_key, base_url=settings.llm.qwen_base_url)
    chunk_map = {str(item.get("id")): item for item in candidates}
    for idx, doc in enumerate(candidates[:max_synthetic_questions], start=1):
        seed_context = _build_seed_context(doc, chunk_map)
        prompt = (
            "Generate ONE medically relevant retrieval test item as strict JSON with keys: "
            "question, hard_paraphrase, distractor_question, evidence_span, answer_summary, expected_keywords. "
            "Use only the provided context. evidence_span must be exact.\n\n"
            f"Metadata: source={doc.get('source')} page={doc.get('page')} "
            f"section={doc.get('section_path', [])} content_type={doc.get('content_type')}\n\n"
            f"Context:\n{seed_context['context_text']}"
        )
        attempt: dict[str, Any] = {
            "attempt_id": idx,
            "doc_id": doc.get("id"),
            "source": doc.get("source"),
            "status": "error",
        }
        try:
            response = client.chat.completions.create(
                model=settings.llm.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
            )
            text = (response.choices[0].message.content or "").strip()
            attempt["raw_response"] = text
            parsed = _extract_json_object(text)
            candidate = {
                "query": str(parsed.get("question", "")).strip(),
                "negative_query": str(parsed.get("distractor_question", "")).strip() or None,
                "paraphrase_query": str(parsed.get("hard_paraphrase", "")).strip() or None,
                "evidence_span": str(parsed.get("evidence_span", "")).strip(),
                "evidence_phrase": str(parsed.get("evidence_span", "")).strip(),
                "answer_summary": str(parsed.get("answer_summary", "")).strip(),
                "expected_keywords": [
                    str(k).strip() for k in parsed.get("expected_keywords", []) if str(k).strip()
                ],
            }
            valid, reason = _validate_synthetic_record(candidate, doc, seed_context["context_text"])
            if not valid:
                attempt["error"] = reason
                attempt["status"] = "rejected"
                attempts.append(attempt)
                continue

            accepted.append(
                {
                    "query_id": f"synthetic_{idx}",
                    "query": candidate["query"],
                    "expected_keywords": candidate["expected_keywords"],
                    "expected_sources": [str(doc.get("source", ""))],
                    "expected_chunk_id": doc.get("id"),
                    "expected_page": doc.get("page"),
                    "reference_answer": candidate["answer_summary"],
                    "evidence_phrase": candidate["evidence_phrase"],
                    "evidence_span": candidate["evidence_span"],
                    "expected_source_types": [_source_type(str(doc.get("source", "")))],
                    "query_category": "synthetic",
                    "task_type": f"{_source_type(str(doc.get('source', '')))}_{doc.get('content_type', 'paragraph')}",
                    "label_confidence": "low",
                    "label_origin": "synthetic",
                    "review_status": "unreviewed",
                    "dataset_origin": "synthetic_qwen",
                    "dataset_split": _assign_split(str(doc.get("source", ""))),
                    "difficulty": _difficulty_for_chunk(doc),
                    "negative_query": candidate["negative_query"],
                    "paraphrase_query": candidate["paraphrase_query"],
                    "source_family": _source_family(str(doc.get("source", ""))),
                }
            )
            attempt["status"] = "accepted"
            attempt["parsed"] = accepted[-1]
        except Exception:
            attempt["error"] = "synthetic_generation_failed"
            logger.warning("Synthetic dataset generation failed")
        attempts.append(attempt)

    return accepted, attempts


def _bootstrap_precise_labels(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not records:
        return records
    chunks = _load_candidate_chunks()
    by_source: dict[str, list[dict[str, Any]]] = {}
    for chunk in chunks:
        by_source.setdefault(str(chunk.get("source", "")).lower(), []).append(chunk)

    for item in records:
        if item.get("expected_chunk_id"):
            continue
        target_sources = [str(s).lower() for s in item.get("expected_sources", [])]
        expected_keywords = [str(k).lower() for k in item.get("expected_keywords", [])]
        best = None
        best_score = -1
        for chunk in chunks:
            chunk_source = str(chunk.get("source", "")).lower()
            chunk_family = _source_family(chunk_source)
            if target_sources:
                if not any(
                    source in chunk_source or _source_family(source) == chunk_family
                    for source in target_sources
                ):
                    continue
            content = str(chunk.get("content", "")).lower()
            overlap = sum(1 for kw in expected_keywords if kw and kw in content)
            if overlap > best_score:
                best = chunk
                best_score = overlap
        if not best:
            continue
        item["expected_chunk_id"] = best.get("id")
        item["expected_page"] = best.get("page")
        item.setdefault("expected_source_types", [_source_type(str(best.get("source", "")))])
        if not item.get("evidence_span"):
            item["evidence_span"] = _extract_evidence_phrase(
                str(best.get("content", "")), expected_keywords
            )
        if not item.get("evidence_phrase"):
            item["evidence_phrase"] = item.get("evidence_span")
        item.setdefault("label_confidence", "low")
        item.setdefault("label_origin", "heuristic")
        item.setdefault("review_status", "unreviewed")
        item.setdefault("source_family", _source_family(str(best.get("source", ""))))
        item.setdefault("dataset_split", _assign_split(str(best.get("source", ""))))
        item.setdefault("difficulty", _difficulty_for_chunk(best))
        item.setdefault("label_bootstrapped", True)
    return records


def _extract_evidence_phrase(content: str, keywords: list[str], window: int = 120) -> str:
    lowered = content.lower()
    for kw in keywords:
        if not kw:
            continue
        idx = lowered.find(kw.lower())
        if idx >= 0:
            start = max(0, idx - window // 2)
            end = min(len(content), idx + len(kw) + window // 2)
            return content[start:end].strip()[:220]
    return ""


def _filter_records(
    records: list[dict[str, Any]],
    *,
    dataset_split: str | None,
    min_label_confidence: str,
) -> list[dict[str, Any]]:
    minimum = _CONFIDENCE_ORDER.get(min_label_confidence, _CONFIDENCE_ORDER["low"])
    filtered = [
        item
        for item in records
        if _CONFIDENCE_ORDER.get(str(item.get("label_confidence", "low")), 0) >= minimum
    ]
    if dataset_split:
        filtered = [item for item in filtered if str(item.get("dataset_split")) == dataset_split]
    filtered.sort(
        key=lambda item: (
            _SPLIT_ORDER.get(str(item.get("dataset_split", "dev")), 0),
            item.get("query_id", ""),
        )
    )
    return filtered


def build_retrieval_dataset(
    *,
    dataset_path: str | Path | None = None,
    enable_llm_generation: bool = False,
    benchmark_mode: bool = False,
    max_synthetic_questions: int = 40,
    sample_docs_per_source_type: int = 10,
    seed: int = 42,
    max_queries: int | None = None,
    sample_seed: int = 42,
    dataset_split: str | None = None,
    min_label_confidence: str = "low",
    reuse_cached_dataset: bool = False,
    reuse_requirements: dict[str, Any] | None = None,
    artifact_dir: str | Path = "data/evals",
) -> dict[str, Any]:
    """Load frozen cases; benchmark mode disables synthesis and label bootstrapping."""
    if benchmark_mode and enable_llm_generation:
        raise ValueError(
            "benchmark_mode forbids synthetic generation; use build_synthetic_retrieval_dataset"
        )
    resolved_dataset_path = Path(dataset_path) if dataset_path else None
    reused_cached_dataset = False
    reused_from_run_dir: str | None = None
    reuse_rejections: list[dict[str, Any]] = []
    default_fixture_path = (
        Path("tests/fixtures/evals/phase123/retrieval-cases.v1.json")
        if benchmark_mode
        else Path("tests/fixtures/golden_queries.json")
    )
    effective_base_dataset_path = resolved_dataset_path or default_fixture_path
    compatibility_contract = _build_dataset_compatibility_contract(
        dataset_path=effective_base_dataset_path,
        enable_llm_generation=enable_llm_generation,
        max_synthetic_questions=max_synthetic_questions,
        sample_docs_per_source_type=sample_docs_per_source_type,
        seed=seed,
        max_queries=max_queries,
        sample_seed=sample_seed,
        dataset_split=dataset_split,
        min_label_confidence=min_label_confidence,
        reuse_requirements=reuse_requirements,
        benchmark_mode=benchmark_mode,
    )
    if resolved_dataset_path is None and reuse_cached_dataset:
        resolved_dataset_path, reused_from_run_dir, reuse_rejections = _resolve_cached_dataset_path(
            compatibility_contract,
            artifact_dir=artifact_dir,
        )
        reused_cached_dataset = resolved_dataset_path is not None
        if resolved_dataset_path is None:
            raise ValueError(
                "reuse_cached_dataset requested but no compatible prior dataset was found"
            )
    if resolved_dataset_path is None:
        resolved_dataset_path = default_fixture_path

    base_records = _normalize_cached_dataset(resolved_dataset_path)
    synthetic_records: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []

    if reused_cached_dataset:
        attempts = [
            {
                "status": "skipped",
                "reason": "reused_cached_dataset",
                "dataset_path": str(resolved_dataset_path),
                "source_run_dir": reused_from_run_dir,
            }
        ]
    elif enable_llm_generation and not benchmark_mode:
        synthetic_records, attempts = _try_generate_synthetic_questions(
            max_synthetic_questions=max_synthetic_questions,
            sample_docs_per_source_type=sample_docs_per_source_type,
            seed=seed,
        )
    else:
        attempts = [
            {
                "status": "skipped",
                "reason": "frozen_benchmark_mode" if benchmark_mode else "llm_generation_disabled",
            }
        ]

    dataset_diagnostics = _dataset_diagnostics(base_records + synthetic_records)
    merged_seen: set[str] = set()
    merged_deduped: list[dict[str, Any]] = []
    for item in base_records + synthetic_records:
        key = re.sub(r"\s+", " ", item.get("query", "").strip().lower())
        if key and key not in merged_seen:
            merged_seen.add(key)
            merged_deduped.append(item)
    # Frozen cases retain their declared identities and denominator, including
    # cross-split duplicate queries. Diagnose leakage; never silently remove it.
    merged = list(base_records) if benchmark_mode else _bootstrap_precise_labels(merged_deduped)
    filtered = _filter_records(
        merged, dataset_split=dataset_split, min_label_confidence=min_label_confidence
    )
    sampled, was_sampled = _sample_filtered_records(
        filtered,
        max_queries=max_queries,
        sample_seed=sample_seed,
    )
    filtered_checksum = _json_checksum(sampled)
    return {
        "dataset": sampled,
        "generation_attempts": attempts,
        "stats": {
            "dataset_path": str(resolved_dataset_path),
            "dataset_mode": "benchmark" if benchmark_mode else "diagnostic",
            "dataset_source": (
                "cached_reuse"
                if reused_cached_dataset
                else "explicit_path"
                if dataset_path
                else "default_fixture"
            ),
            "dataset_checksum": filtered_checksum,
            "reused_from_run_dir": reused_from_run_dir,
            "reused_cached_dataset": reused_cached_dataset,
            "reuse_rejections": reuse_rejections,
            "compatibility": compatibility_contract,
            "fixture_records": len(base_records),
            "synthetic_records": len(synthetic_records),
            "merged_records": len(merged),
            "filtered_records": len(filtered),
            "sampled_records": len(sampled),
            "max_queries": max_queries,
            "sample_seed": sample_seed,
            "was_sampled": was_sampled,
            "split": dataset_split,
            "min_label_confidence": min_label_confidence,
            **dataset_diagnostics,
        },
    }


def build_synthetic_retrieval_dataset(**kwargs: Any) -> dict[str, Any]:
    """Explicit diagnostic operation for generating synthetic retrieval questions."""
    if kwargs.get("benchmark_mode"):
        raise ValueError("synthetic dataset generation is not available in benchmark mode")
    kwargs["enable_llm_generation"] = True
    return build_retrieval_dataset(**kwargs)
