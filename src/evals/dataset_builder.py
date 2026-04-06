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

logger = logging.getLogger(__name__)
from src.ingestion.steps.chunk_text import chunk_documents
from src.ingestion.steps.load_markdown import get_markdown_documents
from src.ingestion.steps.load_pdfs import get_documents

_SPLIT_ORDER = {"dev": 0, "test": 1, "regression": 2}
_CONFIDENCE_ORDER = {"low": 0, "medium": 1, "high": 2}


def _source_family(value: str) -> str:
    lowered = str(value).lower()
    lowered = re.sub(r"\.(pdf|md|html)$", "", lowered)
    lowered = re.sub(r"[^a-z0-9]+", " ", lowered)
    return " ".join(lowered.split()[:3]).strip() or "unknown"


def _assign_split(source: str) -> str:
    family = _source_family(source)
    checksum = sum(ord(ch) for ch in family)
    remainder = checksum % 10
    if remainder <= 4:
        return "dev"
    if remainder <= 7:
        return "test"
    return "regression"


def normalize_golden_queries(fixture_path: Path) -> list[dict[str, Any]]:
    data = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
    records = []
    for i, item in enumerate(data.get("golden_queries", []), start=1):
        source = (item.get("expected_sources") or ["unknown"])[0]
        records.append(
            {
                "query_id": f"golden_{i}",
                "query": item.get("query", "").strip(),
                "expected_keywords": list(item.get("expected_keywords", [])),
                "expected_sources": list(item.get("expected_sources", [])),
                "expected_source_types": list(item.get("expected_source_types", [])),
                "query_category": item.get("query_category", "anchor"),
                "task_type": item.get("task_type"),
                "evidence_phrase": item.get("evidence_phrase"),
                "evidence_span": item.get("evidence_span") or item.get("evidence_phrase"),
                "expected_chunk_id": item.get("expected_chunk_id"),
                "expected_page": item.get("expected_page"),
                "label_confidence": item.get("label_confidence", "medium"),
                "dataset_origin": item.get("dataset_origin", "golden_fixture"),
                "dataset_split": item.get("dataset_split") or _assign_split(str(source)),
                "difficulty": item.get("difficulty", "medium"),
                "negative_query": item.get("negative_query"),
                "source_family": item.get("source_family") or _source_family(str(source)),
            }
        )
    return [r for r in records if r["query"]]


def normalize_golden_conversations(fixture_path: Path) -> list[dict[str, Any]]:
    """Normalize multi-turn conversation golden data from fixture file.

    Args:
        fixture_path: Path to golden_conversations.json

    Returns:
        List of normalized conversation records suitable for evaluation
    """
    data = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
    records = []
    for i, item in enumerate(data.get("golden_conversations", []), start=1):
        turns = item.get("turns", [])
        user_turns = [t for t in turns if t.get("role") == "user"]
        records.append(
            {
                "conversation_id": item.get("conversation_id", f"mt_{i:03d}"),
                "scenario": item.get("scenario", "").strip(),
                "conversation_category": item.get("conversation_category", "contextual_followup"),
                "turns": turns,
                "user_turn_count": len(user_turns),
                "expected_outcome": item.get("expected_outcome", "").strip(),
                "turn_level_expected_keywords": list(item.get("turn_level_expected_keywords", [])),
                "turn_level_expected_sources": list(item.get("turn_level_expected_sources", [])),
                "context": list(item.get("context", [])),
                "difficulty": item.get("difficulty", "medium"),
                "dataset_split": item.get("dataset_split")
                or _assign_split(item.get("source_family", "")),
                "source_family": item.get("source_family", "unknown"),
            }
        )
    return [r for r in records if r["turns"] and r["scenario"]]


def _normalize_cached_dataset(dataset_path: Path) -> list[dict[str, Any]]:
    data = json.loads(dataset_path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "golden_queries" in data:
        return normalize_golden_queries(dataset_path)
    if isinstance(data, dict) and "golden_conversations" in data:
        return normalize_golden_conversations(dataset_path)
    if isinstance(data, list):
        return [
            item for item in data if isinstance(item, dict) and str(item.get("query", "")).strip()
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
    except Exception:
        logger.debug("Path resolution failed for %s", path)
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
    }


def _sample_filtered_records(
    records: list[dict[str, Any]],
    *,
    max_queries: int | None,
    sample_seed: int,
) -> tuple[list[dict[str, Any]], bool]:
    if max_queries is None or max_queries <= 0 or len(records) <= max_queries:
        return records, False
    rng = random.Random(sample_seed)
    chosen_indices = sorted(rng.sample(range(len(records)), max_queries))
    return [records[idx] for idx in chosen_indices], True


def _load_cached_dataset_manifest(run_dir: Path) -> dict[str, Any]:
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        return {}
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        logger.debug("Failed to read manifest at %s", manifest_path)
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
        except Exception:
            logger.debug("Path resolution failed for %s", run_dir)
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
    if s.endswith(".md") or s.endswith(".html"):
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
    rng = random.Random(seed)
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
    return overlap > 0.8


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

    if not settings.dashscope_api_key or settings.dashscope_api_key == "test-api-key":
        return accepted, [{"status": "skipped", "reason": "missing_dashscope_api_key"}]

    try:
        from openai import OpenAI
    except Exception as exc:  # pragma: no cover
        return accepted, [{"status": "skipped", "reason": f"openai_import_error: {exc}"}]

    candidates = _sample_candidate_docs(sample_docs_per_source_type, seed)
    if not candidates:
        return accepted, [{"status": "skipped", "reason": "no_candidate_docs"}]

    client = OpenAI(api_key=settings.dashscope_api_key, base_url=settings.qwen_base_url)
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
                model=settings.model_name,
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
                    "label_confidence": "high" if doc.get("content_type") != "mixed" else "medium",
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
        except Exception as exc:
            attempt["error"] = str(exc)
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
        item["label_confidence"] = (
            "high" if best_score >= 2 else item.get("label_confidence", "medium")
        )
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
    enable_llm_generation: bool = True,
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
    resolved_dataset_path = Path(dataset_path) if dataset_path else None
    reused_cached_dataset = False
    reused_from_run_dir: str | None = None
    reuse_rejections: list[dict[str, Any]] = []
    default_fixture_path = Path("tests/fixtures/golden_queries.json")
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
    elif enable_llm_generation:
        synthetic_records, attempts = _try_generate_synthetic_questions(
            max_synthetic_questions=max_synthetic_questions,
            sample_docs_per_source_type=sample_docs_per_source_type,
            seed=seed,
        )
    else:
        attempts = [{"status": "skipped", "reason": "llm_generation_disabled"}]

    merged_seen: set[str] = set()
    merged_deduped: list[dict[str, Any]] = []
    for item in base_records + synthetic_records:
        key = re.sub(r"\s+", " ", item.get("query", "").strip().lower())
        if key and key not in merged_seen:
            merged_seen.add(key)
            merged_deduped.append(item)
    merged = _bootstrap_precise_labels(merged_deduped)
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
        },
    }
