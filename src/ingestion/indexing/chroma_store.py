"""ChromaDB-backed vector store with hybrid search.

Replaces the JSON-backed VectorStore with ChromaDB persistent storage.
Embedding pipeline, BM25 keyword search, RRF fusion, and MMR reranking
are all unchanged — only the storage layer moves to ChromaDB.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from src.config import settings
from src.ingestion.indexing.embedding import embed_texts, embed_texts_with_stats
from src.ingestion.indexing.keyword_index import (
    build_keyword_index,
    build_term_frequencies,
    keyword_score,
)
from src.ingestion.indexing.search import cosine_similarity, rank_documents, reciprocal_rank_fusion
from src.ingestion.indexing.text_utils import content_hash, sanitize_text, tokenize_text
from src.source_metadata import (
    canonical_source_label,
    display_source_label,
    infer_domain,
    infer_domain_type,
    normalize_source_class,
    normalize_source_type,
    sanitize_external_url,
)

logger = logging.getLogger(__name__)
_VALID_SEARCH_MODES = {"rrf_hybrid", "semantic_only", "bm25_only"}


def _source_type_for(source: str) -> str:
    return normalize_source_type(source)


def _source_class_for(source: str, metadata: dict | None = None) -> str:
    return normalize_source_class(
        source,
        source_type=(metadata or {}).get("source_type"),
        explicit_class=(metadata or {}).get("source_class"),
        page_type=(metadata or {}).get("page_type"),
        logical_name=(metadata or {}).get("logical_name"),
        domain=(metadata or {}).get("domain"),
    )


class ChromaVectorStore:
    """Vector store backed by ChromaDB persistent storage.

    Preserves the full public API of the original JSON-backed VectorStore.
    Metadata filtering is available at query time via the ``filter`` parameter.

    Storage:
        - ChromaDB PersistentClient at ``chroma_persist_directory / collection_name``
        - Keyword index (BM25) maintained in-memory, built from ChromaDB documents
        - Content hashes maintained in-memory for deduplication

    Search:
        - Semantic: ChromaDB ANN query using pre-computed query embedding
        - Keyword: Custom BM25 from keyword_index.py (unchanged)
        - Fusion: RRF (unchanged)
        - Reranking: MMR in runtime.py (unchanged)
    """

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

        self._embeddings_file: Path | None = None

        persist_dir = str(settings.chroma_persist_directory)
        self._client = chromadb.PersistentClient(
            path=persist_dir,
            settings=ChromaSettings(allow_reset=True),
        )
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=None,
        )
        self._index_metadata: dict[str, Any] = dict(index_metadata or {})
        self.content_hashes: set[str] = set()
        self._id_set: set[str] = set()
        self.keyword_index: dict[str, list[int]] = {}
        self._doc_term_freqs: dict[int, dict[str, int]] = {}
        self._index_dirty = False
        self.last_indexing_stats: dict[str, Any] = {}

        self._load_content_hashes()
        self._rebuild_index_if_needed()
        if self._index_metadata and self._index_metadata != dict(self._collection.metadata or {}):
            self._apply_index_metadata()

    @property
    def embeddings_file(self) -> Path | None:
        return self._embeddings_file

    @embeddings_file.setter
    def embeddings_file(self, value: Path | None) -> None:
        self._embeddings_file = value

    def _persist_legacy_snapshot(self) -> None:
        """Keep the legacy JSON vector artifact in sync when requested."""
        if self._embeddings_file is None:
            return

        payload = self.documents
        payload["content_hashes"] = sorted(self.content_hashes)
        self._embeddings_file.parent.mkdir(parents=True, exist_ok=True)
        self._embeddings_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _remove_legacy_snapshot(self) -> None:
        if self._embeddings_file and self._embeddings_file.exists():
            self._embeddings_file.unlink()

    @property
    def documents(self) -> dict[str, Any]:
        all_data = self._collection.get(include=["documents", "metadatas", "embeddings"])
        docs = all_data.get("documents", [])
        metas = all_data.get("metadatas", [])
        embs = all_data.get("embeddings", [])
        return {
            "ids": list(all_data.get("ids", [])),
            "contents": list(docs),
            "embeddings": [e.tolist() if hasattr(e, "tolist") else e for e in embs],
            "metadatas": list(metas),
            "index_metadata": self._index_metadata,
        }

    @documents.setter
    def documents(self, payload: dict[str, Any]) -> None:
        ids = list(payload.get("ids", []))
        contents = list(payload.get("contents", []))
        metadatas = list(payload.get("metadatas", []))
        embeddings = list(payload.get("embeddings", []))

        if len(ids) != len(contents):
            raise ValueError("documents payload must include matching ids and contents lengths")
        if metadatas and len(metadatas) != len(ids):
            raise ValueError("documents payload metadata length must match ids length")
        if embeddings and len(embeddings) != len(ids):
            raise ValueError("documents payload embeddings length must match ids length")

        self.clear()

        self._index_metadata = dict(payload.get("index_metadata", {}) or {})
        if self._index_metadata:
            self._collection.modify(metadata=self._index_metadata)

        normalized_metadatas = metadatas or [{} for _ in ids]
        non_empty_embeddings = bool(embeddings) and all(bool(vector) for vector in embeddings)
        if ids:
            upsert_payload: dict[str, Any] = {
                "ids": ids,
                "documents": contents,
                "metadatas": normalized_metadatas,
            }
            if non_empty_embeddings:
                upsert_payload["embeddings"] = embeddings
            self._collection.upsert(**upsert_payload)

        self._id_set = set(ids)
        self.content_hashes = set(payload.get("content_hashes", []))
        self._index_dirty = True
        self._rebuild_index_if_needed()
        self._persist_legacy_snapshot()

    def _load_content_hashes(self) -> None:
        all_data = self._collection.get(include=["metadatas"])
        for doc_id, meta in zip(all_data.get("ids", []), all_data.get("metadatas", [])):
            self._id_set.add(doc_id)
            if meta and "content_hash" in meta:
                self.content_hashes.add(meta["content_hash"])
        if self._collection.metadata:
            self._index_metadata = dict(self._collection.metadata)

    def _apply_index_metadata(self) -> None:
        if self._index_metadata:
            self._collection.modify(metadata=self._index_metadata)

    def _tokenize(self, text: str) -> list[str]:
        return tokenize_text(text)

    def _rebuild_index_if_needed(self) -> None:
        if self._index_dirty:
            self.keyword_index = self._build_keyword_index()
            self._doc_term_freqs = self._build_term_frequencies()
            self._index_dirty = False

    def _build_term_frequencies(self) -> dict[int, dict[str, int]]:
        contents = self._get_all_documents()
        return build_term_frequencies(contents, self._tokenize)

    def _build_keyword_index(self) -> dict:
        contents = self._get_all_documents()
        return build_keyword_index(contents, self._tokenize)

    def _get_all_documents(self) -> list[str]:
        all_data = self._collection.get(include=["documents"])
        return list(all_data.get("documents", []))

    def _keyword_score(self, query: str) -> dict[int, float]:
        self._rebuild_index_if_needed()
        return keyword_score(
            query,
            contents=self._get_all_documents(),
            keyword_index=self.keyword_index,
            doc_term_freqs=self._doc_term_freqs,
            tokenize=self._tokenize,
        )

    def _embed(self, texts: list[str], batch_size: int = 10) -> list[list[float]]:
        return embed_texts(texts, batch_size=batch_size, model=self.embedding_model)

    def _embed_with_stats(
        self, texts: list[str], batch_size: int = 10
    ) -> tuple[list[list[float]], dict]:
        return embed_texts_with_stats(
            texts,
            batch_size=batch_size,
            model=self.embedding_model,
        )

    def set_index_metadata(self, metadata: dict[str, Any] | None = None) -> None:
        self._index_metadata = dict(metadata or {})
        self._collection.modify(metadata=self._index_metadata)
        self._persist_legacy_snapshot()

    def add_documents(self, documents: list[dict], batch_size: int | None = None) -> dict:
        texts = [sanitize_text(doc["content"]) for doc in documents]
        ids = [doc["id"] for doc in documents]
        effective_batch_size = int(batch_size or self.embedding_batch_size)

        metadatas = []
        for doc in documents:
            source = doc["source"]
            doc_metadata = doc.get("metadata", {})
            source_url = sanitize_external_url(doc_metadata.get("source_url"))
            source_type = (
                doc.get("source_type")
                or doc_metadata.get("source_type")
                or _source_type_for(source)
            )
            source_class = doc.get("source_class") or _source_class_for(
                source,
                {
                    **doc_metadata,
                    "source_type": source_type,
                    "source_class": doc.get("source_class") or doc_metadata.get("source_class"),
                },
            )
            canonical_label = doc_metadata.get("canonical_label") or canonical_source_label(
                source, doc_metadata.get("logical_name")
            )
            domain = doc_metadata.get("domain") or infer_domain(source_url)
            domain_type = doc_metadata.get("domain_type") or infer_domain_type(domain)
            meta: dict[str, Any] = {
                "source": source,
                "source_type": source_type,
                "source_class": source_class,
                "content_type": doc.get("content_type", "paragraph"),
                "section_path": doc.get("section_path", []),
                "quality_score": float(doc.get("quality_score", 1.0)),
                "extractor": doc.get("extractor")
                or doc.get("metadata", {}).get("selected_extractor"),
                "logical_name": doc_metadata.get("logical_name"),
                "canonical_label": canonical_label,
                "source_url": source_url,
                "page_type": doc_metadata.get("page_type"),
                "domain": domain,
                "domain_type": domain_type,
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
            if "hypothetical_questions" in doc_metadata:
                meta["hypothetical_questions"] = doc_metadata["hypothetical_questions"]
            metadatas.append(meta)

        embeddings, embedding_stats = self._embed_with_stats(texts, effective_batch_size)

        stats: dict[str, Any] = {
            "attempted": len(documents),
            "inserted": 0,
            "skipped_duplicate_id": 0,
            "skipped_duplicate_content": 0,
            "embedding_stats": embedding_stats,
        }

        to_upsert_ids: list[str] = []
        to_upsert_embeddings: list[list[float]] = []
        to_upsert_documents: list[str] = []
        to_upsert_metadatas: list[dict[str, Any]] = []

        for i, doc_id in enumerate(ids):
            content_hash_value = content_hash(texts[i])

            if content_hash_value in self.content_hashes:
                stats["skipped_duplicate_content"] += 1
                continue

            meta = dict(metadatas[i])
            meta["content_hash"] = content_hash_value
            for k, v in list(meta.items()):
                if isinstance(v, list) and len(v) == 0:
                    del meta[k]

            to_upsert_ids.append(doc_id)
            to_upsert_embeddings.append(embeddings[i])
            to_upsert_documents.append(texts[i])
            to_upsert_metadatas.append(meta)

            self._id_set.add(doc_id)
            self.content_hashes.add(content_hash_value)
            stats["inserted"] += 1

        if to_upsert_ids:
            self._collection.upsert(
                ids=to_upsert_ids,
                embeddings=to_upsert_embeddings,
                documents=to_upsert_documents,
                metadatas=to_upsert_metadatas,
            )

        self._index_dirty = True
        self.last_indexing_stats = stats
        self._persist_legacy_snapshot()
        return stats

    def similarity_search(
        self,
        query: str,
        top_k: int = 5,
        hybrid: bool = True,
        search_mode: str | None = None,
        filter: dict | None = None,
    ) -> list[dict]:
        if self._collection.count() == 0:
            return []

        self._rebuild_index_if_needed()

        mode = (search_mode or ("rrf_hybrid" if hybrid else "semantic_only")).lower()
        ranked, _, documents_for_ranking, _ = self._search_ranked(
            query, search_mode=mode, filter=filter
        )
        top_scores = ranked[:top_k]

        results = []
        for score_info in top_scores:
            idx = score_info["idx"]
            meta = documents_for_ranking["metadatas"][idx]
            results.append(
                {
                    "id": documents_for_ranking["ids"][idx],
                    "content": documents_for_ranking["contents"][idx],
                    "source": meta.get("source", "unknown"),
                    "page": meta.get("page"),
                    "score": score_info.get("combined_score", 0.0),
                    "semantic_rank": score_info.get("semantic_rank"),
                    "bm25_rank": score_info.get("bm25_rank"),
                    "fused_rank": score_info.get("fused_rank"),
                    "source_prior": score_info.get("source_prior", 0.0),
                    "quality_score": meta.get("quality_score", 1.0),
                    "logical_name": meta.get("logical_name"),
                    "canonical_label": meta.get("canonical_label"),
                    "display_label": display_source_label(
                        meta.get("source", "unknown"),
                        logical_name=meta.get("logical_name"),
                        canonical_label=meta.get("canonical_label"),
                        page=meta.get("page"),
                    ),
                    "source_url": meta.get("source_url"),
                    "source_type": meta.get("source_type"),
                    "source_class": meta.get("source_class"),
                    "domain": meta.get("domain"),
                    "domain_type": meta.get("domain_type"),
                    "metadata": {
                        "logical_name": meta.get("logical_name"),
                        "display_label": display_source_label(
                            meta.get("source", "unknown"),
                            logical_name=meta.get("logical_name"),
                            canonical_label=meta.get("canonical_label"),
                            page=meta.get("page"),
                        ),
                        "source_url": meta.get("source_url"),
                        "canonical_label": meta.get("canonical_label"),
                        "source_type": meta.get("source_type"),
                        "source_class": meta.get("source_class"),
                        "page_type": meta.get("page_type"),
                        "domain": meta.get("domain"),
                        "domain_type": meta.get("domain_type"),
                    },
                }
            )
        return results

    def _search_ranked(
        self, query: str, search_mode: str, filter: dict | None = None
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        self._rebuild_index_if_needed()
        mode = (search_mode or "rrf_hybrid").lower()
        if mode not in _VALID_SEARCH_MODES:
            mode = "rrf_hybrid"
        trace_info: dict[str, Any] = {"search_mode": mode, "embedding_model": self.embedding_model}

        use_semantic = mode != "bm25_only"
        query_embedding: list[float] | None = None
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

        if filter is not None:
            if use_semantic:
                all_data = self._collection.query(
                    query_embeddings=[query_embedding],
                    n_results=1000,
                    where=filter,
                    include=["documents", "metadatas", "embeddings", "distances"],
                )
                chroma_ids = list(all_data.get("ids", [[]])[0])
                chroma_docs = list(all_data.get("documents", [[]])[0])
                chroma_embeddings = all_data.get("embeddings", [[]])[0]
                chroma_metadatas = list(all_data.get("metadatas", [[]])[0])
                chroma_distances: list[float] = list(all_data.get("distances", [[]])[0])
            else:
                all_data = self._collection.get(
                    where=filter,
                    include=["documents", "metadatas", "embeddings"],
                )
                chroma_ids = list(all_data.get("ids", []))
                chroma_docs = list(all_data.get("documents", []))
                chroma_embeddings = all_data.get("embeddings", [])
                chroma_metadatas = list(all_data.get("metadatas", []))
                chroma_distances = []
            filtered_term_freqs = build_term_frequencies(chroma_docs, self._tokenize)
            filtered_keyword_index = build_keyword_index(chroma_docs, self._tokenize)
            keyword_scores = keyword_score(
                query,
                contents=chroma_docs,
                keyword_index=filtered_keyword_index,
                doc_term_freqs=filtered_term_freqs,
                tokenize=self._tokenize,
            )
        else:
            all_data = self._collection.get(include=["documents", "metadatas", "embeddings"])
            chroma_ids = list(all_data.get("ids", []))
            chroma_docs = list(all_data.get("documents", []))
            chroma_embeddings = all_data.get("embeddings", [])
            chroma_metadatas = list(all_data.get("metadatas", []))
            chroma_distances = []
            keyword_scores = self._keyword_score(query)

        documents_for_ranking: dict[str, list[Any]] = {
            "ids": chroma_ids,
            "contents": list(chroma_docs),
            "embeddings": [
                emb.tolist() if hasattr(emb, "tolist") else emb for emb in chroma_embeddings
            ],
            "metadatas": list(chroma_metadatas),
        }

        semantic_ranked = rank_documents(
            documents=documents_for_ranking,
            keyword_scores={},
            query_embedding=query_embedding if use_semantic else None,
            use_semantic=use_semantic,
            hybrid=False,
            semantic_weight=self.semantic_weight,
            keyword_weight=self.keyword_weight,
            boost_weight=self.boost_weight,
        )
        keyword_ranked = rank_documents(
            documents=documents_for_ranking,
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
        elif mode == "bm25_only":
            ranked = keyword_ranked
            for rank, row in enumerate(ranked, start=1):
                row["semantic_rank"] = None
                row["bm25_rank"] = rank
                row["fused_rank"] = rank
                row["fused_score"] = row["combined_score"]
        else:
            ranked = reciprocal_rank_fusion(semantic_ranked, keyword_ranked)

        trace_info["candidate_counts"] = {
            "semantic": len(semantic_ranked),
            "bm25": len(keyword_ranked),
            "final": len(ranked),
        }
        return ranked, trace_info, documents_for_ranking, chroma_distances

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        return cosine_similarity(a, b)

    def similarity_search_with_trace(
        self,
        query: str,
        top_k: int = 5,
        hybrid: bool = True,
        search_mode: str | None = None,
        filter: dict | None = None,
    ) -> tuple[list[dict], dict]:
        start_time = time.time()
        mode = (search_mode or ("rrf_hybrid" if hybrid else "semantic_only")).lower()
        trace_info: dict[str, Any] = {
            "query": query,
            "top_k": top_k,
            "search_mode": mode,
            "score_weights": {
                "semantic": self.semantic_weight,
                "keyword": self.keyword_weight,
                "source": self.boost_weight,
            },
        }

        if self._collection.count() == 0:
            trace_info["timing_ms"] = int((time.time() - start_time) * 1000)
            return [], trace_info

        keyword_start = time.time()
        _ = self._keyword_score(query)
        trace_info["keyword_timing_ms"] = int((time.time() - keyword_start) * 1000)

        semantic_start = time.time()
        ranked, search_trace, documents_for_ranking, _ = self._search_ranked(
            query, search_mode=mode, filter=filter
        )
        trace_info.update(search_trace)
        if mode == "bm25_only":
            trace_info["semantic_timing_ms"] = 0
        else:
            trace_info["semantic_timing_ms"] = int((time.time() - semantic_start) * 1000)
        top_scores = ranked[:top_k]

        results = []
        for rank, score_info in enumerate(top_scores, start=1):
            idx = score_info["idx"]
            meta = documents_for_ranking["metadatas"][idx]
            results.append(
                {
                    "id": documents_for_ranking["ids"][idx],
                    "content": documents_for_ranking["contents"][idx],
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
                    "canonical_label": meta.get("canonical_label"),
                    "display_label": display_source_label(
                        meta.get("source", "unknown"),
                        logical_name=meta.get("logical_name"),
                        canonical_label=meta.get("canonical_label"),
                        page=meta.get("page"),
                    ),
                    "source_url": meta.get("source_url"),
                    "source_type": meta.get("source_type"),
                    "source_class": meta.get("source_class"),
                    "domain": meta.get("domain"),
                    "domain_type": meta.get("domain_type"),
                    "metadata": {
                        "logical_name": meta.get("logical_name"),
                        "display_label": display_source_label(
                            meta.get("source", "unknown"),
                            logical_name=meta.get("logical_name"),
                            canonical_label=meta.get("canonical_label"),
                            page=meta.get("page"),
                        ),
                        "source_url": meta.get("source_url"),
                        "canonical_label": meta.get("canonical_label"),
                        "source_type": meta.get("source_type"),
                        "source_class": meta.get("source_class"),
                        "page_type": meta.get("page_type"),
                        "domain": meta.get("domain"),
                        "domain_type": meta.get("domain_type"),
                    },
                }
            )

        trace_info["timing_ms"] = int((time.time() - start_time) * 1000)
        return results, trace_info

    def get_hypothetical_questions(self) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        all_data = self._collection.get(ids=None, include=["metadatas"])
        for i, doc_id in enumerate(all_data["ids"]):
            meta = all_data["metadatas"][i]
            if meta and "hypothetical_questions" in meta:
                result[doc_id] = meta["hypothetical_questions"]
        return result

    def search_hypothetical_questions(self, query: str, *, limit: int = 5) -> list[str]:
        query_tokens = set(self._tokenize(query))
        if not query_tokens:
            return []

        all_data = self._collection.get(include=["metadatas"])

        scored: list[tuple[float, str]] = []
        for i, meta in enumerate(all_data.get("metadatas", [])):
            if not meta:
                continue
            quality_score = float(meta.get("quality_score", 1.0))
            for question in meta.get("hypothetical_questions", []):
                question_tokens = set(self._tokenize(question))
                overlap = len(query_tokens & question_tokens)
                if overlap <= 0:
                    continue
                coverage = overlap / len(query_tokens)
                precision = overlap / max(1, len(question_tokens))
                score = (0.7 * coverage) + (0.3 * precision) + (0.05 * quality_score)
                scored.append((score, question))

        scored.sort(key=lambda item: item[0], reverse=True)
        selected: list[str] = []
        seen: set[str] = set()
        for _, question in scored:
            normalized = " ".join(str(question).split())
            if normalized and normalized not in seen:
                seen.add(normalized)
                selected.append(normalized)
            if len(selected) >= limit:
                break
        return selected

    def clear(self) -> None:
        all_ids = self._collection.get(include=[]).get("ids", [])
        if all_ids:
            self._collection.delete(ids=all_ids)
        self.content_hashes = set()
        self._id_set = set()
        self.keyword_index = {}
        self._doc_term_freqs = {}
        self._index_metadata = {}
        self._index_dirty = False
        self.last_indexing_stats = {}
        self._remove_legacy_snapshot()


class ChromaVectorStoreFactory:
    _instance: ChromaVectorStore | None = None
    _runtime_config: dict[str, Any] = {}
    _runtime_signature_value: tuple[tuple[str, Any], ...] | None = None

    @classmethod
    def _normalize_runtime_config(cls, config: dict[str, Any] | None = None) -> dict[str, Any]:
        resolved = dict(config or cls._runtime_config or {})
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

    @classmethod
    def _compute_runtime_signature(cls, config: dict[str, Any]) -> tuple[tuple[str, Any], ...]:
        return tuple(
            sorted(
                (
                    key,
                    tuple(sorted(value.items())) if isinstance(value, dict) else value,
                )
                for key, value in config.items()
            )
        )

    @classmethod
    def set_runtime_config(cls, config: dict[str, Any] | None = None) -> None:
        normalized = cls._normalize_runtime_config(config)
        signature = cls._compute_runtime_signature(normalized)
        cls._runtime_config = normalized
        if cls._runtime_signature_value != signature:
            cls._instance = None
            cls._runtime_signature_value = signature

    @classmethod
    def get_runtime_config(cls) -> dict[str, Any]:
        return dict(cls._normalize_runtime_config(cls._runtime_config))

    @classmethod
    def get_vector_store(cls, config: dict[str, Any] | None = None) -> ChromaVectorStore:
        normalized = cls._normalize_runtime_config(config)
        signature = cls._compute_runtime_signature(normalized)
        if config is not None:
            cls.set_runtime_config(normalized)
        if cls._instance is None:
            cls._instance = ChromaVectorStore(**normalized)
            cls._runtime_signature_value = signature
        elif cls._runtime_signature_value != signature:
            cls._instance = ChromaVectorStore(**normalized)
            cls._runtime_signature_value = signature
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None
        cls._runtime_config = {}
        cls._runtime_signature_value = None


def set_vector_store_runtime_config(config: dict[str, Any] | None = None) -> None:
    ChromaVectorStoreFactory.set_runtime_config(config)


def get_vector_store_runtime_config() -> dict[str, Any]:
    return ChromaVectorStoreFactory.get_runtime_config()


def get_vector_store(config: dict[str, Any] | None = None) -> ChromaVectorStore:
    return ChromaVectorStoreFactory.get_vector_store(config)
