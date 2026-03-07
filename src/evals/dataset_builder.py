"""Build retrieval evaluation datasets from fixtures and optional LLM synthesis."""

from __future__ import annotations

import json
import random
import re
from pathlib import Path
from typing import Any

from src.config import settings
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


def _build_seed_context(seed: dict[str, Any], chunk_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
    context_chunks = [seed]
    for related_key in ("previous_chunk_id", "next_chunk_id"):
        related = chunk_map.get(str(seed.get(related_key)))
        if related:
            context_chunks.append(related)
    context_text = "\n\n".join(str(item.get("content", ""))[:900] for item in context_chunks if item.get("content"))
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


def _validate_synthetic_record(candidate: dict[str, Any], seed: dict[str, Any], context_text: str) -> tuple[bool, str]:
    evidence_span = str(candidate.get("evidence_span") or candidate.get("evidence_phrase") or "").strip()
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
    if answer_summary and not any(token in context_text.lower() for token in re.findall(r"[a-z0-9]+", answer_summary.lower())[:3]):
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
                "expected_keywords": [str(k).strip() for k in parsed.get("expected_keywords", []) if str(k).strip()],
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
                    source in chunk_source
                    or _source_family(source) == chunk_family
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
            item["evidence_span"] = _extract_evidence_phrase(str(best.get("content", "")), expected_keywords)
        if not item.get("evidence_phrase"):
            item["evidence_phrase"] = item.get("evidence_span")
        item["label_confidence"] = "high" if best_score >= 2 else item.get("label_confidence", "medium")
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


def _dedupe_queries(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for item in records:
        key = re.sub(r"\s+", " ", item.get("query", "").strip().lower())
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _filter_records(
    records: list[dict[str, Any]],
    *,
    dataset_split: str | None,
    min_label_confidence: str,
) -> list[dict[str, Any]]:
    minimum = _CONFIDENCE_ORDER.get(min_label_confidence, _CONFIDENCE_ORDER["low"])
    filtered = [
        item for item in records
        if _CONFIDENCE_ORDER.get(str(item.get("label_confidence", "low")), 0) >= minimum
    ]
    if dataset_split:
        filtered = [item for item in filtered if str(item.get("dataset_split")) == dataset_split]
    filtered.sort(key=lambda item: (_SPLIT_ORDER.get(str(item.get("dataset_split", "dev")), 0), item.get("query_id", "")))
    return filtered


def build_retrieval_dataset(
    *,
    dataset_path: str | Path | None = None,
    enable_llm_generation: bool = True,
    max_synthetic_questions: int = 40,
    sample_docs_per_source_type: int = 10,
    seed: int = 42,
    dataset_split: str | None = None,
    min_label_confidence: str = "low",
) -> dict[str, Any]:
    fixture = Path(dataset_path) if dataset_path else Path("tests/fixtures/golden_queries.json")
    base_records = normalize_golden_queries(fixture)
    synthetic_records: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []

    if enable_llm_generation:
        synthetic_records, attempts = _try_generate_synthetic_questions(
            max_synthetic_questions=max_synthetic_questions,
            sample_docs_per_source_type=sample_docs_per_source_type,
            seed=seed,
        )
    else:
        attempts = [{"status": "skipped", "reason": "llm_generation_disabled"}]

    merged = _dedupe_queries(base_records + synthetic_records)
    merged = _bootstrap_precise_labels(merged)
    filtered = _filter_records(merged, dataset_split=dataset_split, min_label_confidence=min_label_confidence)
    return {
        "dataset": filtered,
        "generation_attempts": attempts,
        "stats": {
            "fixture_records": len(base_records),
            "synthetic_records": len(synthetic_records),
            "merged_records": len(merged),
            "filtered_records": len(filtered),
            "split": dataset_split,
            "min_label_confidence": min_label_confidence,
        },
    }
