#!/usr/bin/env python3
"""
L5: Vector Store - Embed and store document chunks with hybrid search.
"""

import logging
import time
from typing import Dict, List

import google.genai as genai

from src.config import settings
from src.ingestion.indexing.embedding import embed_texts
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
from src.ingestion.indexing.search import cosine_similarity, rank_documents
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


class VectorStore:
    def __init__(
        self,
        collection_name: str | None = None,
        semantic_weight: float = 0.6,
        keyword_weight: float = 0.2,
        boost_weight: float = 0.2
    ):
        self.collection_name = collection_name or settings.collection_name
        self.semantic_weight = semantic_weight
        self.keyword_weight = keyword_weight
        self.boost_weight = boost_weight
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.embeddings_file = VECTOR_DIR / f"{self.collection_name}.json"
        self.documents = self._load()
        self.content_hashes = set(self.documents.get("content_hashes", []))
        self.keyword_index = self._build_keyword_index()
        self._index_dirty = False
        self._doc_term_freqs = self._build_term_frequencies()

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
        return embed_texts(self.client, texts, batch_size=batch_size)

    def add_documents(self, documents: List[dict], batch_size: int = 10) -> dict:
        texts = [sanitize_text(doc["content"]) for doc in documents]
        ids = [doc["id"] for doc in documents]
        metadatas = []
        for doc in documents:
            source = doc["source"]
            meta = {"source": source, "source_type": _source_type_for(source)}
            if "page" in doc:
                meta["page"] = doc["page"]
            if "chunk_index" in doc:
                meta["chunk_index"] = doc["chunk_index"]
            if "start_char" in doc:
                meta["start_char"] = doc["start_char"]
            if "end_char" in doc:
                meta["end_char"] = doc["end_char"]
            metadatas.append(meta)

        embeddings = self._embed(texts, batch_size)
        stats = {
            "attempted": len(documents),
            "inserted": 0,
            "skipped_duplicate_id": 0,
            "skipped_duplicate_content": 0,
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

        self._save()
        self._index_dirty = True
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
        use_keyword = mode in {"hybrid", "keyword_only"}
        use_hybrid = mode == "hybrid"
        keyword_scores = self._keyword_score(query) if use_keyword else {}
        query_embedding = None

        if mode != "keyword_only":
            try:
                query_embedding = self._embed([query])[0]
                use_semantic = True
            except Exception as e:
                logger.warning(f"Embedding failed, falling back to keyword-only search: {e}")
                use_semantic = False
        else:
            use_semantic = False

        ranked = rank_documents(
            documents=self.documents,
            keyword_scores=keyword_scores,
            query_embedding=query_embedding if use_semantic else None,
            use_semantic=use_semantic,
            hybrid=use_hybrid,
            semantic_weight=self.semantic_weight,
            keyword_weight=self.keyword_weight,
            boost_weight=self.boost_weight,
        )
        score_by_idx = {item["idx"]: item["combined_score"] for item in ranked}
        top_indices = [item["idx"] for item in ranked[:top_k]]

        results = []
        for idx in top_indices:
            results.append({
                "id": self.documents["ids"][idx],
                "content": self.documents["contents"][idx],
                "source": self.documents["metadatas"][idx].get("source", "unknown"),
                "page": self.documents["metadatas"][idx].get("page"),
                "score": score_by_idx[idx]
            })
        return results

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
        use_keyword = mode in {"hybrid", "keyword_only"}
        use_hybrid = mode == "hybrid"
        trace_info = {
            "query": query,
            "top_k": top_k,
            "search_mode": mode,
            "score_weights": {
                "semantic": self.semantic_weight,
                "keyword": self.keyword_weight,
                "source": self.boost_weight
            }
        }

        if not self.documents["contents"]:
            trace_info["timing_ms"] = int((time.time() - start_time) * 1000)
            return [], trace_info

        self._rebuild_index_if_needed()

        keyword_start = time.time()
        keyword_scores = self._keyword_score(query) if use_keyword else {}
        trace_info["keyword_timing_ms"] = int((time.time() - keyword_start) * 1000)

        semantic_start = time.time()
        query_embedding = None
        if mode != "keyword_only":
            try:
                query_embedding = self._embed([query])[0]
                use_semantic = True
                trace_info["semantic_timing_ms"] = int((time.time() - semantic_start) * 1000)
            except Exception as e:
                logger.warning(f"Embedding failed, falling back to keyword-only search: {e}")
                use_semantic = False
                trace_info["semantic_timing_ms"] = 0
        else:
            use_semantic = False
            trace_info["semantic_timing_ms"] = 0

        ranked = rank_documents(
            documents=self.documents,
            keyword_scores=keyword_scores,
            query_embedding=query_embedding,
            use_semantic=use_semantic,
            hybrid=use_hybrid,
            semantic_weight=self.semantic_weight,
            keyword_weight=self.keyword_weight,
            boost_weight=self.boost_weight,
        )
        top_scores = ranked[:top_k]

        results = []
        for rank, score_info in enumerate(top_scores, start=1):
            idx = score_info["idx"]
            results.append({
                "id": self.documents["ids"][idx],
                "content": self.documents["contents"][idx],
                "source": self.documents["metadatas"][idx].get("source", "unknown"),
                "page": self.documents["metadatas"][idx].get("page"),
                "semantic_score": round(score_info["semantic_score"], 4),
                "keyword_score": round(score_info["keyword_score"], 4),
                "source_boost": round(score_info["source_boost"], 4),
                "combined_score": round(score_info["combined_score"], 4),
                "rank": rank
            })

        trace_info["timing_ms"] = int((time.time() - start_time) * 1000)
        return results, trace_info

    def clear(self):
        self.documents = empty_documents()
        self.content_hashes = set()
        self.keyword_index = {}
        self._doc_term_freqs = {}
        self._index_dirty = False
        if self.embeddings_file.exists():
            self.embeddings_file.unlink()


_vector_store = None


def get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
