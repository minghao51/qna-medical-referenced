#!/usr/bin/env python3
"""
L5: Vector Store - Embed and store document chunks with hybrid search.
"""

import logging
import time
from typing import Any, Dict, List

from src.config import settings
from src.ingestion.indexing.embedding import embed_texts, embed_texts_with_stats
from src.ingestion.indexing.keyword_index import (
    build_keyword_index,
    build_term_frequencies,
    keyword_score,
)
from src.ingestion.indexing.persistence import (
    VECTOR_DIR,
    empty_documents,
    load_documents,
    save_documents,
)
from src.ingestion.indexing.search import cosine_similarity, rank_documents, reciprocal_rank_fusion
from src.ingestion.indexing.text_utils import content_hash, sanitize_text, tokenize_text

logger = logging.getLogger(__name__)


def _source_type_for(source: str) -> str:
    lowered = source.lower()
    if lowered.endswith(".pdf"):
        return "pdf"
    if lowered.endswith(".csv"):
        return "csv"
    if lowered.endswith(".md") or lowered.endswith(".html"):
        return "html"
    return "other"


def _source_class_for(source: str, metadata: dict | None = None) -> str:
    lowered = source.lower()
    page_type = str((metadata or {}).get("page_type", ""))
    if lowered.endswith(".pdf"):
        return "guideline_pdf"
    if lowered.endswith(".csv"):
        return "reference_csv"
    if page_type in {"index/listing", "navigation-heavy"}:
        return "index_page"
    if lowered.endswith(".md") or lowered.endswith(".html"):
        return "guideline_html"
    return "unknown"


class VectorStore:
    def __init__(
        self,
        collection_name: str | None = None,
        semantic_weight: float = 0.6,
        keyword_weight: float = 0.2,
        boost_weight: float = 0.2,
        embedding_model: str | None = None,
        embedding_batch_size: int | None = None,
        index_metadata: dict[str, Any] | None = None,
    ):
        self.collection_name = collection_name or settings.collection_name
        self.semantic_weight = semantic_weight
        self.keyword_weight = keyword_weight
        self.boost_weight = boost_weight
        self.embedding_model = embedding_model or settings.embedding_model
        self.embedding_batch_size = int(embedding_batch_size or settings.embedding_batch_size)
        self.embeddings_file = VECTOR_DIR / f"{self.collection_name}.json"
        self.documents = self._load()
        self.documents.setdefault("index_metadata", {})
        if index_metadata:
            self.documents["index_metadata"] = dict(index_metadata)
        self.content_hashes = set(self.documents.get("content_hashes", []))
        self.keyword_index = self._build_keyword_index()
        self._index_dirty = False
        self._doc_term_freqs = self._build_term_frequencies()
        self.last_indexing_stats: dict[str, Any] = {}

    def _load(self) -> dict:
        return load_documents(self.embeddings_file)

    def _save(self):
        self.documents["content_hashes"] = list(self.content_hashes)
        save_documents(self.embeddings_file, self.documents)

    def _tokenize(self, text: str) -> List[str]:
        return tokenize_text(text)

    def _build_term_frequencies(self) -> Dict[int, Dict[str, int]]:
        return build_term_frequencies(self.documents.get("contents", []), self._tokenize)

    def _build_keyword_index(self) -> dict:
        return build_keyword_index(self.documents.get("contents", []), self._tokenize)

    def _rebuild_index_if_needed(self):
        if self._index_dirty:
            self.keyword_index = self._build_keyword_index()
            self._doc_term_freqs = self._build_term_frequencies()
            self._index_dirty = False

    def _keyword_score(self, query: str) -> dict:
        self._rebuild_index_if_needed()
        return keyword_score(
            query,
            contents=self.documents.get("contents", []),
            keyword_index=self.keyword_index,
            doc_term_freqs=self._doc_term_freqs,
            tokenize=self._tokenize,
        )

    def _embed(self, texts: List[str], batch_size: int = 10) -> List[List[float]]:
        return embed_texts(texts, batch_size=batch_size, model=self.embedding_model)

    def _embed_with_stats(
        self, texts: List[str], batch_size: int = 10
    ) -> tuple[List[List[float]], dict]:
        return embed_texts_with_stats(
            texts,
            batch_size=batch_size,
            model=self.embedding_model,
        )

    def set_index_metadata(self, metadata: dict[str, Any] | None = None) -> None:
        self.documents["index_metadata"] = dict(metadata or {})
        self._save()

    def add_documents(self, documents: List[dict], batch_size: int | None = None) -> dict:
        texts = [sanitize_text(doc["content"]) for doc in documents]
        ids = [doc["id"] for doc in documents]
        effective_batch_size = int(batch_size or self.embedding_batch_size)
        metadatas = []
        for doc in documents:
            source = doc["source"]
            doc_metadata = doc.get("metadata", {})
            meta = {
                "source": source,
                "source_type": doc.get("source_type", _source_type_for(source)),
                "source_class": doc.get("source_class")
                or _source_class_for(source, doc.get("metadata")),
                "content_type": doc.get("content_type", "paragraph"),
                "section_path": doc.get("section_path", []),
                "quality_score": float(doc.get("quality_score", 1.0)),
                "extractor": doc.get("extractor")
                or doc.get("metadata", {}).get("selected_extractor"),
                "logical_name": doc_metadata.get("logical_name"),
                "source_url": doc_metadata.get("source_url"),
            }
            if "page" in doc:
                meta["page"] = doc["page"]
            if "chunk_index" in doc:
                meta["chunk_index"] = doc["chunk_index"]
            if "start_char" in doc:
                meta["start_char"] = doc["start_char"]
            if "end_char" in doc:
                meta["end_char"] = doc["end_char"]
            if "previous_chunk_id" in doc:
                meta["previous_chunk_id"] = doc["previous_chunk_id"]
            if "next_chunk_id" in doc:
                meta["next_chunk_id"] = doc["next_chunk_id"]
            if "section_sibling_rank" in doc:
                meta["section_sibling_rank"] = doc["section_sibling_rank"]
            metadatas.append(meta)

        embeddings, embedding_stats = self._embed_with_stats(texts, effective_batch_size)
        stats: dict[str, Any] = {
            "attempted": len(documents),
            "inserted": 0,
            "skipped_duplicate_id": 0,
            "skipped_duplicate_content": 0,
            "embedding_stats": embedding_stats,
        }

        for i, doc_id in enumerate(ids):
            content_hash_value = content_hash(texts[i])
            if doc_id in self.documents["ids"]:
                stats["skipped_duplicate_id"] += 1
                continue
            if content_hash_value in self.content_hashes:
                stats["skipped_duplicate_content"] += 1
                continue
            self.documents["ids"].append(doc_id)
            self.documents["contents"].append(texts[i])
            self.documents["embeddings"].append(embeddings[i])
            self.documents["metadatas"].append(metadatas[i])
            self.content_hashes.add(content_hash_value)
            stats["inserted"] += 1

        self.documents["ids"] = list(self.documents["ids"])
        self.documents["contents"] = list(self.documents["contents"])
        self.documents["embeddings"] = list(self.documents["embeddings"])
        self.documents["metadatas"] = list(self.documents["metadatas"])
        self.documents.setdefault("index_metadata", {})

        self._save()
        self._index_dirty = True
        self.last_indexing_stats = stats
        return stats

    def similarity_search(
        self,
        query: str,
        top_k: int = 5,
        hybrid: bool = True,
        search_mode: str | None = None,
    ) -> List[dict]:
        if not self.documents["contents"]:
            return []

        self._rebuild_index_if_needed()

        mode = (search_mode or ("hybrid" if hybrid else "semantic_only")).lower()
        ranked, _ = self._search_ranked(query, search_mode=mode)
        top_scores = ranked[:top_k]

        results = []
        for score_info in top_scores:
            idx = score_info["idx"]
            meta = self.documents["metadatas"][idx]
            results.append(
                {
                    "id": self.documents["ids"][idx],
                    "content": self.documents["contents"][idx],
                    "source": meta.get("source", "unknown"),
                    "page": meta.get("page"),
                    "score": score_info.get("combined_score", 0.0),
                    "semantic_rank": score_info.get("semantic_rank"),
                    "bm25_rank": score_info.get("bm25_rank"),
                    "fused_rank": score_info.get("fused_rank"),
                    "source_prior": score_info.get("source_prior", 0.0),
                    "quality_score": meta.get("quality_score", 1.0),
                    "logical_name": meta.get("logical_name"),
                    "source_url": meta.get("source_url"),
                    "metadata": {
                        "logical_name": meta.get("logical_name"),
                        "source_url": meta.get("source_url"),
                    },
                }
            )
        return results

    def _search_ranked(self, query: str, search_mode: str) -> tuple[list[dict], dict[str, Any]]:
        self._rebuild_index_if_needed()
        mode = (search_mode or "rrf_hybrid").lower()
        trace_info: dict[str, Any] = {"search_mode": mode, "embedding_model": self.embedding_model}

        keyword_scores = self._keyword_score(query)
        query_embedding = None
        use_semantic = mode != "bm25_only"
        if use_semantic:
            try:
                embedding_start = time.time()
                query_embedding = self._embed([query], batch_size=1)[0]
                trace_info["query_embedding_timing_ms"] = int(
                    (time.time() - embedding_start) * 1000
                )
            except Exception as e:
                logger.warning(f"Embedding failed, falling back to BM25-only search: {e}")
                use_semantic = False
                trace_info["query_embedding_timing_ms"] = 0
        else:
            trace_info["query_embedding_timing_ms"] = 0

        semantic_ranked = rank_documents(
            documents=self.documents,
            keyword_scores={},
            query_embedding=query_embedding if use_semantic else None,
            use_semantic=use_semantic,
            hybrid=False,
            semantic_weight=self.semantic_weight,
            keyword_weight=self.keyword_weight,
            boost_weight=self.boost_weight,
        )
        keyword_ranked = rank_documents(
            documents=self.documents,
            keyword_scores=keyword_scores,
            query_embedding=None,
            use_semantic=False,
            hybrid=False,
            semantic_weight=self.semantic_weight,
            keyword_weight=self.keyword_weight,
            boost_weight=self.boost_weight,
        )

        if mode == "semantic_only":
            ranked = semantic_ranked
            for rank, row in enumerate(ranked, start=1):
                row["semantic_rank"] = rank
                row["bm25_rank"] = None
                row["fused_rank"] = rank
                row["fused_score"] = row["combined_score"]
        elif mode in {"bm25_only", "keyword_only"}:
            ranked = keyword_ranked
            for rank, row in enumerate(ranked, start=1):
                row["semantic_rank"] = None
                row["bm25_rank"] = rank
                row["fused_rank"] = rank
                row["fused_score"] = row["combined_score"]
        elif mode == "legacy_hybrid":
            ranked = rank_documents(
                documents=self.documents,
                keyword_scores=keyword_scores,
                query_embedding=query_embedding if use_semantic else None,
                use_semantic=use_semantic,
                hybrid=True,
                semantic_weight=self.semantic_weight,
                keyword_weight=self.keyword_weight,
                boost_weight=self.boost_weight,
            )
            for rank, row in enumerate(ranked, start=1):
                row["semantic_rank"] = next(
                    (i for i, v in enumerate(semantic_ranked, start=1) if v["idx"] == row["idx"]),
                    None,
                )
                row["bm25_rank"] = next(
                    (i for i, v in enumerate(keyword_ranked, start=1) if v["idx"] == row["idx"]),
                    None,
                )
                row["fused_rank"] = rank
                row["fused_score"] = row["combined_score"]
        else:
            ranked = reciprocal_rank_fusion(semantic_ranked, keyword_ranked)

        trace_info["candidate_counts"] = {
            "semantic": len(semantic_ranked),
            "bm25": len(keyword_ranked),
            "final": len(ranked),
        }

        if mode == "semantic_only":
            ranked = semantic_ranked
            for rank, row in enumerate(ranked, start=1):
                row["semantic_rank"] = rank
                row["bm25_rank"] = None
                row["fused_rank"] = rank
                row["fused_score"] = row["combined_score"]
        elif mode in {"bm25_only", "keyword_only"}:
            ranked = keyword_ranked
            for rank, row in enumerate(ranked, start=1):
                row["semantic_rank"] = None
                row["bm25_rank"] = rank
                row["fused_rank"] = rank
                row["fused_score"] = row["combined_score"]
        elif mode == "legacy_hybrid":
            ranked = rank_documents(
                documents=self.documents,
                keyword_scores=keyword_scores,
                query_embedding=query_embedding if use_semantic else None,
                use_semantic=use_semantic,
                hybrid=True,
                semantic_weight=self.semantic_weight,
                keyword_weight=self.keyword_weight,
                boost_weight=self.boost_weight,
            )
            for rank, row in enumerate(ranked, start=1):
                row["semantic_rank"] = next(
                    (i for i, v in enumerate(semantic_ranked, start=1) if v["idx"] == row["idx"]),
                    None,
                )
                row["bm25_rank"] = next(
                    (i for i, v in enumerate(keyword_ranked, start=1) if v["idx"] == row["idx"]),
                    None,
                )
                row["fused_rank"] = rank
                row["fused_score"] = row["combined_score"]
        else:
            ranked = reciprocal_rank_fusion(semantic_ranked, keyword_ranked)

        trace_info["candidate_counts"] = {
            "semantic": len(semantic_ranked),
            "bm25": len(keyword_ranked),
            "final": len(ranked),
        }
        return ranked, trace_info

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        return cosine_similarity(a, b)

    def similarity_search_with_trace(
        self,
        query: str,
        top_k: int = 5,
        hybrid: bool = True,
        search_mode: str | None = None,
    ) -> tuple[List[dict], dict]:
        start_time = time.time()
        mode = (search_mode or ("hybrid" if hybrid else "semantic_only")).lower()
        trace_info = {
            "query": query,
            "top_k": top_k,
            "search_mode": mode,
            "score_weights": {
                "semantic": self.semantic_weight,
                "keyword": self.keyword_weight,
                "source": self.boost_weight,
            },
        }

        if not self.documents["contents"]:
            trace_info["timing_ms"] = int((time.time() - start_time) * 1000)
            return [], trace_info

        keyword_start = time.time()
        _ = self._keyword_score(query)
        trace_info["keyword_timing_ms"] = int((time.time() - keyword_start) * 1000)

        semantic_start = time.time()
        ranked, search_trace = self._search_ranked(query, search_mode=mode)
        trace_info.update(search_trace)
        if mode in {"bm25_only", "keyword_only"}:
            trace_info["semantic_timing_ms"] = 0
        else:
            trace_info["semantic_timing_ms"] = int((time.time() - semantic_start) * 1000)
        top_scores = ranked[:top_k]

        results = []
        for rank, score_info in enumerate(top_scores, start=1):
            idx = score_info["idx"]
            meta = self.documents["metadatas"][idx]
            results.append(
                {
                    "id": self.documents["ids"][idx],
                    "content": self.documents["contents"][idx],
                    "source": meta.get("source", "unknown"),
                    "page": meta.get("page"),
                    "semantic_score": round(score_info.get("semantic_score", 0.0), 4),
                    "keyword_score": round(score_info.get("keyword_score", 0.0), 4),
                    "source_prior": round(score_info.get("source_prior", 0.0), 4),
                    "combined_score": round(score_info["combined_score"], 4),
                    "rank": rank,
                    "semantic_rank": score_info.get("semantic_rank"),
                    "bm25_rank": score_info.get("bm25_rank"),
                    "fused_rank": score_info.get("fused_rank", rank),
                    "fused_score": round(
                        score_info.get("fused_score", score_info["combined_score"]), 4
                    ),
                    "quality_score": round(float(meta.get("quality_score", 1.0)), 4),
                    "content_type": meta.get("content_type", "paragraph"),
                    "section_path": meta.get("section_path", []),
                    "logical_name": meta.get("logical_name"),
                    "source_url": meta.get("source_url"),
                    "metadata": {
                        "logical_name": meta.get("logical_name"),
                        "source_url": meta.get("source_url"),
                    },
                }
            )

        trace_info["timing_ms"] = int((time.time() - start_time) * 1000)
        return results, trace_info

    def clear(self):
        self.documents = empty_documents()
        self.content_hashes = set()
        self.keyword_index = {}
        self._doc_term_freqs = {}
        self._index_dirty = False
        self.last_indexing_stats = {}
        if self.embeddings_file.exists():
            self.embeddings_file.unlink()


_vector_store = None
_vector_store_runtime_config: dict[str, Any] = {}
_vector_store_runtime_signature: tuple[tuple[str, Any], ...] | None = None


def _normalize_runtime_config(config: dict[str, Any] | None = None) -> dict[str, Any]:
    resolved = dict(config or _vector_store_runtime_config or {})
    return {
        "collection_name": resolved.get("collection_name", settings.collection_name),
        "semantic_weight": float(resolved.get("semantic_weight", 0.6)),
        "keyword_weight": float(resolved.get("keyword_weight", 0.2)),
        "boost_weight": float(resolved.get("boost_weight", 0.2)),
        "embedding_model": resolved.get("embedding_model", settings.embedding_model),
        "embedding_batch_size": int(
            resolved.get("embedding_batch_size", settings.embedding_batch_size)
        ),
        "index_metadata": dict(resolved.get("index_metadata", {})),
    }


def _runtime_signature(config: dict[str, Any]) -> tuple[tuple[str, Any], ...]:
    return tuple(
        sorted(
            (
                key,
                tuple(sorted(value.items())) if isinstance(value, dict) else value,
            )
            for key, value in config.items()
        )
    )


def set_vector_store_runtime_config(config: dict[str, Any] | None = None) -> None:
    global _vector_store, _vector_store_runtime_config, _vector_store_runtime_signature
    normalized = _normalize_runtime_config(config)
    signature = _runtime_signature(normalized)
    _vector_store_runtime_config = normalized
    if _vector_store_runtime_signature != signature:
        _vector_store = None
        _vector_store_runtime_signature = signature


def get_vector_store_runtime_config() -> dict[str, Any]:
    return dict(_normalize_runtime_config(_vector_store_runtime_config))


def get_vector_store(config: dict[str, Any] | None = None) -> VectorStore:
    global _vector_store, _vector_store_runtime_signature
    normalized = _normalize_runtime_config(config)
    signature = _runtime_signature(normalized)
    if config is not None:
        set_vector_store_runtime_config(normalized)
    if _vector_store is None:
        _vector_store = VectorStore(**normalized)
        _vector_store_runtime_signature = signature
    elif _vector_store_runtime_signature != signature:
        _vector_store = VectorStore(**normalized)
        _vector_store_runtime_signature = signature
    return _vector_store
