from src.ingestion.indexing.vector_store import VectorStore
from src.rag.runtime import _diversify_results, _extend_with_hype_questions


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


def test_search_hypothetical_questions_only_returns_query_relevant_matches():
    store = VectorStore(collection_name="test_hype_search")
    store.clear()
    store.documents = {
        "ids": ["a", "b"],
        "contents": ["chunk a", "chunk b"],
        "embeddings": [[], []],
        "metadatas": [
            {
                "quality_score": 1.0,
                "hypothetical_questions": [
                    "What is the LDL-C target for secondary prevention?",
                    "When should high-intensity statin therapy be used?",
                ],
            },
            {
                "quality_score": 1.0,
                "hypothetical_questions": [
                    "How should pre-diabetes meal planning work?",
                ],
            },
        ],
        "content_hashes": [],
        "index_metadata": {},
    }

    matches = store.search_hypothetical_questions("LDL target for diabetes", limit=5)

    assert matches
    assert "LDL-C target" in matches[0]
    assert all("pre-diabetes" not in match.lower() for match in matches)


def test_extend_with_hype_questions_only_adds_selected_matches():
    class StubVectorStore:
        def search_hypothetical_questions(self, query: str, *, limit: int = 5) -> list[str]:
            assert query == "ldl question"
            assert limit == 5
            return ["related question", "existing query"]

    expanded, selected = _extend_with_hype_questions(
        StubVectorStore(),
        "ldl question",
        ["existing query"],
        enable_hype=True,
    )

    assert selected == ["related question", "existing query"]
    assert expanded == ["existing query", "related question"]
