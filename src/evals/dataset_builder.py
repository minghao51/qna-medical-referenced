"""Build retrieval evaluation datasets from fixtures and optional LLM synthesis."""

from __future__ import annotations

import json
import random
import re
from pathlib import Path
from typing import Any

from src.config import VECTOR_DIR, settings


def normalize_golden_queries(fixture_path: Path) -> list[dict[str, Any]]:
    data = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
    records = []
    for i, item in enumerate(data.get("golden_queries", []), start=1):
        records.append(
            {
                "query_id": f"golden_{i}",
                "query": item.get("query", "").strip(),
                "expected_keywords": list(item.get("expected_keywords", [])),
                "expected_sources": list(item.get("expected_sources", [])),
                "expected_source_types": list(item.get("expected_source_types", [])),
                "query_category": item.get("query_category"),
                "task_type": item.get("task_type"),
                "evidence_phrase": item.get("evidence_phrase"),
                "expected_chunk_id": item.get("expected_chunk_id"),
                "label_confidence": item.get("label_confidence", "medium"),
                "dataset_origin": item.get("dataset_origin", "golden_fixture"),
            }
        )
    return [r for r in records if r["query"]]


def _load_index_docs() -> list[dict[str, Any]]:
    vector_path = VECTOR_DIR / f"{settings.collection_name}.json"
    if not vector_path.exists():
        return []
    data = json.loads(vector_path.read_text(encoding="utf-8"))
    docs = []
    for idx, content in enumerate(data.get("contents", [])):
        meta = (data.get("metadatas", []) + [{}])[idx] if idx < len(data.get("metadatas", [])) else {}
        docs.append(
            {
                "id": (data.get("ids", []) + [f"doc_{idx}"])[idx] if idx < len(data.get("ids", [])) else f"doc_{idx}",
                "content": content,
                "source": (meta or {}).get("source", "unknown"),
                "page": (meta or {}).get("page"),
            }
        )
    return docs


def _source_type(source: str) -> str:
    s = source.lower()
    if s.endswith(".pdf"):
        return "pdf"
    if s.endswith(".csv"):
        return "csv"
    if s.endswith(".md") or s.endswith(".html"):
        return "html"
    return "other"


def _sample_candidate_docs(sample_docs_per_source_type: int, seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    docs = _load_index_docs()
    buckets: dict[str, list[dict[str, Any]]] = {"pdf": [], "csv": [], "html": [], "other": []}
    for doc in docs:
        buckets[_source_type(str(doc.get("source", "")))].append(doc)
    sampled: list[dict[str, Any]] = []
    for bucket in buckets.values():
        rng.shuffle(bucket)
        sampled.extend(bucket[:sample_docs_per_source_type])
    rng.shuffle(sampled)
    return sampled


def _try_generate_synthetic_questions(
    *,
    max_synthetic_questions: int,
    sample_docs_per_source_type: int,
    seed: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    attempts: list[dict[str, Any]] = []
    accepted: list[dict[str, Any]] = []

    if not settings.gemini_api_key or settings.gemini_api_key == "test-api-key":
        return accepted, [{"status": "skipped", "reason": "missing_gemini_api_key"}]

    try:
        import google.genai as genai
    except Exception as exc:  # pragma: no cover - dependency import edge case
        return accepted, [{"status": "skipped", "reason": f"genai_import_error: {exc}"}]

    candidates = _sample_candidate_docs(sample_docs_per_source_type, seed)
    if not candidates:
        return accepted, [{"status": "skipped", "reason": "no_candidate_docs"}]

    client = genai.Client(api_key=settings.gemini_api_key)
    for idx, doc in enumerate(candidates[:max_synthetic_questions], start=1):
        context = str(doc.get("content", ""))[:2500]
        prompt = (
            "Generate ONE medically relevant retrieval test item as strict JSON with keys: "
            "question, answer, evidence_phrase, expected_keywords (array). "
            "Use only the provided context. evidence_phrase must be an exact short substring from context.\n\n"
            f"Context:\n{context}"
        )
        attempt: dict[str, Any] = {
            "attempt_id": idx,
            "doc_id": doc.get("id"),
            "source": doc.get("source"),
            "status": "error",
        }
        try:
            response = client.models.generate_content(model=settings.model_name, contents=prompt)
            text = (response.text or "").strip()
            attempt["raw_response"] = text
            parsed = _extract_json_object(text)
            question = str(parsed.get("question", "")).strip()
            evidence = str(parsed.get("evidence_phrase", "")).strip()
            expected_keywords = parsed.get("expected_keywords", [])
            if not question:
                raise ValueError("empty question")
            if evidence and evidence not in context:
                raise ValueError("evidence phrase not present in source context")
            if not isinstance(expected_keywords, list):
                expected_keywords = []
            accepted.append(
                {
                    "query_id": f"synthetic_{idx}",
                    "query": question,
                    "expected_keywords": [str(k) for k in expected_keywords if str(k).strip()],
                    "expected_sources": [str(doc.get("source", ""))],
                    "expected_chunk_id": doc.get("id"),
                    "expected_page": doc.get("page"),
                    "reference_answer": str(parsed.get("answer", "")).strip(),
                    "evidence_phrase": evidence,
                    "expected_source_types": [_source_type(str(doc.get("source", "")))],
                    "query_category": "synthetic",
                    "task_type": {
                        "pdf": "pdf_guideline",
                        "csv": "reference_csv",
                        "html": "html_public_health",
                    }.get(_source_type(str(doc.get("source", ""))), "unknown"),
                    "label_confidence": "high",
                    "dataset_origin": "synthetic_gemini",
                }
            )
            attempt["status"] = "accepted"
            attempt["parsed"] = accepted[-1]
        except Exception as exc:
            attempt["error"] = str(exc)
        attempts.append(attempt)

    return accepted, attempts


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


def build_retrieval_dataset(
    *,
    dataset_path: str | Path | None = None,
    enable_llm_generation: bool = True,
    max_synthetic_questions: int = 40,
    sample_docs_per_source_type: int = 10,
    seed: int = 42,
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
    return {
        "dataset": merged,
        "generation_attempts": attempts,
        "stats": {
            "fixture_records": len(base_records),
            "synthetic_records": len(synthetic_records),
            "merged_records": len(merged),
        },
    }


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


def _bootstrap_precise_labels(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Enrich coarse source-level labels with chunk-level labels when the current index can
    confidently identify a matching chunk from expected source + keyword overlap.
    """
    if not records:
        return records
    try:
        from src.ingestion.indexing.vector_store import get_vector_store
        from src.rag.runtime import initialize_runtime_index
    except Exception:
        return records

    try:
        initialize_runtime_index()
        store = get_vector_store()
    except Exception:
        return records

    for item in records:
        if item.get("expected_chunk_id"):
            continue
        query = str(item.get("query", "")).strip()
        expected_sources = [str(s).lower() for s in item.get("expected_sources", [])]
        expected_keywords = [str(k).lower() for k in item.get("expected_keywords", [])]
        if not query or not expected_sources:
            continue
        try:
            results = store.similarity_search(query, top_k=10)
        except Exception:
            continue

        best = None
        best_score = -1
        for res in results:
            source = str(res.get("source", "")).lower()
            if not any(es in source for es in expected_sources):
                continue
            content = str(res.get("content", "")).lower()
            overlap = sum(1 for kw in expected_keywords if kw and kw in content)
            score = overlap
            if score > best_score:
                best = res
                best_score = score
        if not best:
            continue

        item["expected_chunk_id"] = best.get("id")
        evidence = _extract_evidence_phrase(str(best.get("content", "")), expected_keywords)
        if evidence:
            item["evidence_phrase"] = evidence
        item["label_confidence"] = "high" if best_score >= 2 else item.get("label_confidence", "medium")
        item.setdefault("label_bootstrapped", True)
    return records


def _extract_evidence_phrase(content: str, keywords: list[str], window: int = 80) -> str:
    lowered = content.lower()
    for kw in keywords:
        if not kw:
            continue
        idx = lowered.find(kw.lower())
        if idx >= 0:
            start = max(0, idx - window // 2)
            end = min(len(content), idx + len(kw) + window // 2)
            return content[start:end].strip()[:200]
    return ""
