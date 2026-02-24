"""Search and ranking helpers for the vector store."""

from typing import Any


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot_product = sum(x * y for x, y in zip(a, b))
    magnitude_a = sum(x * x for x in a) ** 0.5
    magnitude_b = sum(y * y for y in b) ** 0.5
    return dot_product / (magnitude_a * magnitude_b) if magnitude_a * magnitude_b > 0 else 0


def source_boost_for(source: str) -> float:
    return 1.0 if ".pdf" in source else 0.5


def rank_documents(
    *,
    documents: dict[str, list[Any]],
    keyword_scores: dict[int, float],
    query_embedding: list[float] | None,
    use_semantic: bool,
    hybrid: bool,
    semantic_weight: float,
    keyword_weight: float,
    boost_weight: float,
) -> list[dict[str, Any]]:
    max_kw_score = max(keyword_scores.values()) if keyword_scores else 1
    ranked: list[dict[str, Any]] = []

    for i, emb in enumerate(documents["embeddings"]):
        semantic_score = cosine_similarity(query_embedding, emb) if (use_semantic and query_embedding is not None) else 0.0

        source = documents["metadatas"][i].get("source", "")
        boost = source_boost_for(source)
        normalized_keyword = keyword_scores.get(i, 0) / max_kw_score if max_kw_score > 0 else 0

        if hybrid and keyword_scores:
            if use_semantic:
                combined = (
                    semantic_weight * semantic_score
                    + keyword_weight * normalized_keyword
                    + boost_weight * boost
                )
            else:
                combined = (1 - boost_weight) * normalized_keyword + boost_weight * boost
        else:
            combined = semantic_score * boost

        ranked.append(
            {
                "idx": i,
                "semantic_score": semantic_score,
                "keyword_score": normalized_keyword,
                "source_boost": boost,
                "combined_score": combined,
            }
        )

    ranked.sort(key=lambda item: item["combined_score"], reverse=True)
    return ranked

