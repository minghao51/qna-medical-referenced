from src.evals import llm_judges


def test_extract_json_parses_fenced_json():
    parsed = llm_judges._extract_json(
        "```json\n{\"relevance_score\": 4, \"faithfulness_score\": 5, \"grounded_claim_ratio\": 1.0, "
        "\"has_medical_disclaimer\": true, \"notes\": \"ok\"}\n```"
    )
    assert parsed["relevance_score"] == 4
    assert parsed["has_medical_disclaimer"] is True


def test_judge_answer_skips_without_valid_key(monkeypatch):
    monkeypatch.setattr(llm_judges.settings, "gemini_api_key", "test-api-key")
    result = llm_judges.judge_answer(query="q", answer="a", context="c")
    assert result["status"] == "skipped"

