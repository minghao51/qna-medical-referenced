"""Search and ranking helpers for the vector store."""

from __future__ import annotations

from typing import Any


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot_product = sum(x * y for x, y in zip(a, b))
    magnitude_a = sum(x * x for x in a) ** 0.5
    magnitude_b = sum(y * y for y in b) ** 0.5
    return dot_product / (magnitude_a * magnitude_b) if magnitude_a * magnitude_b > 0 else 0.0


def source_prior_for(source_class: str) -> float:
    priors = {
        "guideline_pdf": 0.15,
        "guideline_html": 0.1,
        "reference_csv": 0.12,
        "index_page": 0.02,
    }
    return priors.get(source_class, 0.05)


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
    max_kw_score = max(keyword_scores.values()) if keyword_scores else 1.0
    ranked: list[dict[str, Any]] = []

    for i, emb in enumerate(documents["embeddings"]):
        semantic_score = cosine_similarity(query_embedding, emb) if (use_semantic and query_embedding is not None) else 0.0
        metadata = documents["metadatas"][i]
        source_class = metadata.get("source_class", "unknown")
        source_prior = source_prior_for(source_class)
        normalized_keyword = keyword_scores.get(i, 0.0) / max_kw_score if max_kw_score > 0 else 0.0

        if hybrid:
            combined = (
                semantic_weight * semantic_score
                + keyword_weight * normalized_keyword
                + boost_weight * source_prior
            )
        elif use_semantic:
            combined = semantic_score + source_prior
        else:
            combined = normalized_keyword + source_prior

        ranked.append(
            {
                "idx": i,
                "semantic_score": semantic_score,
                "keyword_score": normalized_keyword,
                "source_prior": source_prior,
                "combined_score": combined,
            }
        )

    ranked.sort(key=lambda item: item["combined_score"], reverse=True)
    return ranked


def reciprocal_rank_fusion(
    semantic_ranked: list[dict[str, Any]],
    keyword_ranked: list[dict[str, Any]],
    *,
    k: int = 60,
) -> list[dict[str, Any]]:
    by_idx: dict[int, dict[str, Any]] = {}

    for rank, row in enumerate(semantic_ranked, start=1):
        idx = int(row["idx"])
        entry = by_idx.setdefault(idx, {"idx": idx, "semantic_rank": None, "bm25_rank": None, "fused_score": 0.0})
        entry["semantic_rank"] = rank
        entry["semantic_score"] = row.get("semantic_score", 0.0)
        entry["source_prior"] = row.get("source_prior", 0.0)
        entry["keyword_score"] = row.get("keyword_score", 0.0)
        entry["fused_score"] += 1.0 / (k + rank)

    for rank, row in enumerate(keyword_ranked, start=1):
        idx = int(row["idx"])
        entry = by_idx.setdefault(idx, {"idx": idx, "semantic_rank": None, "bm25_rank": None, "fused_score": 0.0})
        entry["bm25_rank"] = rank
        entry["semantic_score"] = entry.get("semantic_score", row.get("semantic_score", 0.0))
        entry["keyword_score"] = row.get("keyword_score", 0.0)
        entry["source_prior"] = row.get("source_prior", 0.0)
        entry["fused_score"] += 1.0 / (k + rank)

    fused = list(by_idx.values())
    fused.sort(key=lambda item: (item["fused_score"], item.get("semantic_score", 0.0), item.get("keyword_score", 0.0)), reverse=True)
    for rank, row in enumerate(fused, start=1):
        row["fused_rank"] = rank
        row["combined_score"] = row["fused_score"] + row.get("source_prior", 0.0)
    return fused
