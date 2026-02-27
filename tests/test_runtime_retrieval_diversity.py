from src.rag.runtime import _diversify_results


def test_diversify_results_limits_repeated_source_page():
    results = [
        {"id": "a", "source": "s1.pdf", "page": 1, "content": "x1", "combined_score": 0.9},
        {"id": "b", "source": "s1.pdf", "page": 1, "content": "x2", "combined_score": 0.8},
        {"id": "c", "source": "s1.pdf", "page": 1, "content": "x3", "combined_score": 0.7},
        {"id": "d", "source": "s1.pdf", "page": 2, "content": "x4", "combined_score": 0.6},
        {"id": "e", "source": "s2.pdf", "page": 1, "content": "x5", "combined_score": 0.5},
    ]

    diversified = _diversify_results(results, top_k=4)

    assert len(diversified) == 4
    s1p1 = [r for r in diversified if r["source"] == "s1.pdf" and r["page"] == 1]
    assert len(s1p1) <= 2


def test_diversify_results_fills_when_constraints_tight():
    results = [
        {"id": "a", "source": "same.pdf", "page": 1, "content": "x1"},
        {"id": "b", "source": "same.pdf", "page": 1, "content": "x2"},
        {"id": "c", "source": "same.pdf", "page": 1, "content": "x3"},
    ]
    diversified = _diversify_results(results, top_k=3)
    assert len(diversified) == 3


def test_diversify_results_can_be_disabled():
    results = [
        {"id": "a", "source": "s1.pdf", "page": 1, "content": "x1"},
        {"id": "b", "source": "s1.pdf", "page": 1, "content": "x2"},
        {"id": "c", "source": "s1.pdf", "page": 1, "content": "x3"},
    ]
    diversified = _diversify_results(results, top_k=2, enable_diversification=False)
    assert [r["id"] for r in diversified] == ["a", "b"]
