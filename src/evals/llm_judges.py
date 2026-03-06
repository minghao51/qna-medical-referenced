"""Optional LLM judges for RAG answer relevance and faithfulness."""

from __future__ import annotations

import json
import re
from typing import Any

from src.config import settings


def _extract_json(text: str) -> dict[str, Any]:
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
        raise ValueError("No JSON found in judge response")
    parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("Judge output must be JSON object")
    return parsed


def judge_answer(
    *,
    query: str,
    answer: str,
    context: str,
    max_retries: int = 2,
) -> dict[str, Any]:
    if not settings.dashscope_api_key or settings.dashscope_api_key == "test-api-key":
        return {"status": "skipped", "reason": "missing_dashscope_api_key"}

    try:
        from openai import OpenAI
    except Exception as exc:  # pragma: no cover
        return {"status": "skipped", "reason": f"openai_import_error: {exc}"}

    prompt = f"""
You are an evaluator for a medical RAG system.
Return strict JSON with keys:
- relevance_score (1-5 integer)
- faithfulness_score (1-5 integer)
- grounded_claim_ratio (0-1 float)
- has_medical_disclaimer (true/false)
- notes (string)

Question:
{query}

Retrieved Context:
{context[:8000]}

Answer:
{answer[:4000]}
""".strip()

    client = OpenAI(api_key=settings.dashscope_api_key, base_url=settings.qwen_base_url)
    last_error = None
    raw_response = ""
    for _ in range(max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=settings.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
            raw_response = (response.choices[0].message.content or "").strip()
            parsed = _extract_json(raw_response)
            return {"status": "ok", "parsed": parsed, "raw_response": raw_response}
        except Exception as exc:
            last_error = str(exc)
    return {"status": "error", "error": last_error, "raw_response": raw_response}
