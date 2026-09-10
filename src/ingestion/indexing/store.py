"""ChromaDB-backed vector store core: client, CRUD, mirrors, BM25, search.

Split in Phase 2 (roadmap P2.3): HyPE question search lives in
hype_index.py, API-shaped document listing in listing.py, the singleton
factory in factory.py. chroma_store.py re-exports the public surface.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, cast

import chromadb
from chromadb.config import Settings as ChromaSettings

from src.config import settings
from src.core.source_metadata import (
    canonical_source_label,
    display_source_label,
    infer_domain,
    infer_domain_type,
    normalize_source_class,
    normalize_source_type,
    sanitize_external_url,
)
from src.ingestion.indexing.embedding import embed_texts, embed_texts_with_stats
from src.ingestion.indexing.hype_index import HypotheticalQuestionSearchMixin
from src.ingestion.indexing.keyword_index import (
    build_keyword_index,
    build_term_frequencies,
    keyword_score_with_extracted_keywords,
)
from src.ingestion.indexing.listing import DocumentListingMixin
from src.ingestion.indexing.search import rank_documents, reciprocal_rank_fusion
from src.ingestion.indexing.text_utils import content_hash, sanitize_text, tokenize_text

logger = logging.getLogger(__name__)

_VALID_SEARCH_MODES = {"rrf_hybrid", "semantic_only", "bm25_only"}

# Page size used when fetching all documents matching a metadata filter.
# ChromaDB's collection.query has no offset parameter and its n_results cap
# silently truncated large filtered candidate sets, so filtered searches
# paginate collection.get instead (final ranking is exact cosine/BM25 over
# the fetched candidates either way).
_FILTERED_PAGE_SIZE = 1000


def _source_type_for(source: str) -> str:
    return normalize_source_type(source)


def _extracted_keywords_from_metadata(
    metadatas: list[dict[str, Any] | None],
) -> list[list[str] | None]:
    """Per-document lowercased extracted keywords (None when absent)."""
    extracted: list[list[str] | None] = []
    for meta in metadatas:
        kws = meta.get("extracted_keywords") if meta else None
        if isinstance(kws, list):
            extracted.append([str(k).lower() for k in kws])
        else:
            extracted.append(None)
    return extracted


def _source_class_for(source: str, metadata: dict | None = None) -> str:
    return normalize_source_class(
        source,
        source_type=(metadata or {}).get("source_type"),
        explicit_class=(metadata or {}).get("source_class"),
        page_type=(metadata or {}).get("page_type"),
        logical_name=(metadata or {}).get("logical_name"),
        domain=(metadata or {}).get("domain"),
    )


class ChromaVectorStore(HypotheticalQuestionSearchMixin, DocumentListingMixin):
    """Vector store backed by ChromaDB persistent storage.

    Preserves the full public API of the original JSON-backed VectorStore.
    Metadata filtering is available at query time via the ``filter`` parameter.

    Storage:
        - ChromaDB PersistentClient at ``chroma_persist_directory / collection_name``
        - Keyword index (BM25) maintained in-memory, built from ChromaDB documents
        - Content hashes maintained in-memory for deduplication

    Search:
        - Semantic: exact cosine similarity computed in Python between the
          query embedding and every candidate document embedding. ChromaDB
          is used as the document/embedding store, not as an ANN index;
          filtered queries fetch all matching documents via paginated
          collection.get calls
        - Keyword: custom BM25 from keyword_index.py with the
          extracted-keywords boost, applied identically for filtered and
          unfiltered queries
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
        self.collection_name = collection_name or settings.storage.collection_name
        self.semantic_weight = semantic_weight
        self.keyword_weight = keyword_weight
        self.boost_weight = boost_weight
        self.embedding_model = embedding_model or settings.llm.embedding_model
        self.embedding_batch_size = int(embedding_batch_size or settings.llm.embedding_batch_size)

        self._embeddings_file: Path | None = None

        chroma_host = settings.storage.chroma_server_host.strip()
        if chroma_host:
            logger.info(
                "Connecting to ChromaDB server at %s:%d",
                chroma_host,
                settings.storage.chroma_server_port,
            )
            self._client = chromadb.HttpClient(
                host=chroma_host,
                port=settings.storage.chroma_server_port,
            )
        else:
            persist_dir = str(settings.storage.chroma_persist_directory)
            self._client = chromadb.PersistentClient(
                path=persist_dir,
                settings=ChromaSettings(allow_reset=True),
            )
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=None,
        )
        # When no index metadata is supplied, adopt what the collection
        # already persists so provenance survives cold restarts. The factory
        # passes ``{}`` for "unset", which is treated the same as None.
        self._index_metadata: dict[str, Any] = (
            dict(index_metadata) if index_metadata else dict(self._collection.metadata or {})
        )
        self.content_hashes: set[str] = set()
        self._id_set: set[str] = set()
        self._doc_ids: list[str] = []
        self._doc_contents: list[str] = []
        self._doc_metadatas: list[dict[str, Any]] = []
        self._doc_embeddings: list[list[float]] = []
        self._doc_id_to_index: dict[str, int] = {}
        self.keyword_index: dict[str, list[int]] = {}
        self._doc_term_freqs: dict[int, dict[str, int]] = {}
        self._extracted_keywords_list: list[list[str] | None] = []
        self._hypothetical_question_cache: (
            list[tuple[float, list[tuple[frozenset[str], str]]]] | None
        ) = None
        self._index_dirty = True
        self.last_indexing_stats: dict[str, Any] = {}

        # A single full scan of the collection seeds the id set, content
        # hashes, and the document mirrors in one pass.
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
        """Full document payload, served from the in-memory mirrors.

        The mirrors are refreshed from ChromaDB when dirty and embeddings
        are lazy-loaded once, so callers no longer re-fetch the entire
        collection (embeddings included) on every access.
        """
        self._rebuild_index_if_needed()
        self._ensure_embeddings_loaded()
        return {
            "ids": list(self._doc_ids),
            "contents": list(self._doc_contents),
            "embeddings": [list(emb) for emb in self._doc_embeddings],
            "metadatas": [dict(meta) for meta in self._doc_metadatas],
            "index_metadata": dict(self._index_metadata),
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
        self._doc_ids = []
        self._doc_contents = []
        self._doc_metadatas = []
        self._doc_embeddings = []
        self._doc_id_to_index = {}
        self.content_hashes = set(payload.get("content_hashes", []))
        self._index_dirty = True
        self._rebuild_index_if_needed()
        self._persist_legacy_snapshot()

    def _apply_index_metadata(self) -> None:
        if self._index_metadata:
            self._collection.modify(metadata=self._index_metadata)

    def _tokenize(self, text: str) -> list[str]:
        return tokenize_text(text)

    def _rebuild_index_if_needed(self) -> None:
        """Refresh mirrors from ChromaDB (single pass) when the index is dirty.

        Also seeds the id set and content-hash set from collection metadata,
        so a cold start recovers deduplication state in the same scan.
        """
        if not self._index_dirty:
            return
        all_data = cast(
            dict[str, Any], self._collection.get(include=cast(Any, ["documents", "metadatas"]))
        )
        ids: list[Any] = all_data.get("ids", []) or []
        docs: list[Any] = all_data.get("documents", []) or []
        metas: list[Any] = all_data.get("metadatas", []) or []
        self._doc_ids = list(ids)
        self._doc_contents = list(docs)
        self._doc_metadatas = [dict(meta or {}) for meta in metas]
        self._doc_embeddings = []
        self._id_set = set(self._doc_ids)
        for meta in self._doc_metadatas:
            if "content_hash" in meta:
                self.content_hashes.add(str(meta["content_hash"]))
        self._rebuild_in_memory_indexes()
        self._index_dirty = False

    def _ensure_embeddings_loaded(self) -> None:
        """Lazy-load embeddings only when needed for semantic search."""
        if not self._doc_embeddings and self._collection.count() > 0:
            logger.debug("Lazy-loading embeddings for semantic search")
            all_data = cast(dict[str, Any], self._collection.get(include=["embeddings"]))
            embeddings_raw_raw = all_data.get("embeddings")
            embeddings_raw: list[Any] = embeddings_raw_raw if embeddings_raw_raw is not None else []
            self._doc_embeddings = [
                emb.tolist() if hasattr(emb, "tolist") else emb for emb in embeddings_raw
            ]

    def _rebuild_in_memory_indexes(self) -> None:
        self._doc_id_to_index = {doc_id: idx for idx, doc_id in enumerate(self._doc_ids)}
        self.keyword_index = build_keyword_index(self._doc_contents, self._tokenize)
        self._doc_term_freqs = build_term_frequencies(self._doc_contents, self._tokenize)
        self._extracted_keywords_list = _extracted_keywords_from_metadata(self._doc_metadatas)
        self._hypothetical_question_cache = self._build_hypothetical_question_cache()

    def _get_all_documents(self) -> list[str]:
        self._rebuild_index_if_needed()
        return list(self._doc_contents)

    def _keyword_score(self, query: str) -> dict[int, float]:
        self._rebuild_index_if_needed()
        return keyword_score_with_extracted_keywords(
            query,
            contents=self._doc_contents,
            keyword_index=self.keyword_index,
            doc_term_freqs=self._doc_term_freqs,
            tokenize=self._tokenize,
            extracted_keywords_list=self._extracted_keywords_list,
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
            if "extracted_keywords" in doc_metadata:
                meta["extracted_keywords"] = doc_metadata["extracted_keywords"]
            if "chunk_summary" in doc_metadata:
                meta["chunk_summary"] = doc_metadata["chunk_summary"]
            metadatas.append(meta)

        embeddings, embedding_stats = self._embed_with_stats(texts, effective_batch_size)

        stats: dict[str, Any] = {
            "attempted": len(documents),
            "inserted": 0,
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
                embeddings=cast(Any, to_upsert_embeddings),
                documents=to_upsert_documents,
                metadatas=cast(Any, to_upsert_metadatas),
            )

            # Incrementally update the mirrors to match Chroma upsert
            # semantics: an existing doc_id is replaced in place, a new one
            # is appended. Appending unconditionally would leave stale and
            # fresh copies of the same id both ranking in unfiltered
            # searches and duplicated in documents_for_ranking.
            embeddings_loaded = len(self._doc_embeddings) == len(self._doc_ids)
            for doc_id, text, meta, embedding in zip(
                to_upsert_ids,
                to_upsert_documents,
                to_upsert_metadatas,
                to_upsert_embeddings,
                strict=True,
            ):
                existing_idx = self._doc_id_to_index.get(doc_id)
                if existing_idx is not None:
                    old_hash = self._doc_metadatas[existing_idx].get("content_hash")
                    if old_hash is not None:
                        self.content_hashes.discard(str(old_hash))
                    self._doc_contents[existing_idx] = text
                    self._doc_metadatas[existing_idx] = meta
                    if embeddings_loaded:
                        self._doc_embeddings[existing_idx] = embedding
                else:
                    self._doc_ids.append(doc_id)
                    self._doc_contents.append(text)
                    self._doc_metadatas.append(meta)
                    if embeddings_loaded:
                        self._doc_embeddings.append(embedding)
            self._rebuild_in_memory_indexes()
        else:
            self._index_dirty = True
        self.last_indexing_stats = stats
        self._persist_legacy_snapshot()
        return stats

    @staticmethod
    def _base_result_fields(
        documents_for_ranking: dict[str, list[Any]],
        idx: int,
    ) -> dict[str, Any]:
        """Fields shared by similarity_search and similarity_search_with_trace."""
        meta = documents_for_ranking["metadatas"][idx]
        source = meta.get("source", "unknown")
        logical_name = meta.get("logical_name")
        canonical_label = meta.get("canonical_label")
        page = meta.get("page")
        display_label = display_source_label(
            source,
            logical_name=logical_name,
            canonical_label=canonical_label,
            page=page,
        )
        return {
            "id": documents_for_ranking["ids"][idx],
            "content": documents_for_ranking["contents"][idx],
            "source": source,
            "page": page,
            "logical_name": logical_name,
            "canonical_label": canonical_label,
            "display_label": display_label,
            "source_url": meta.get("source_url"),
            "source_type": meta.get("source_type"),
            "source_class": meta.get("source_class"),
            "domain": meta.get("domain"),
            "domain_type": meta.get("domain_type"),
            "metadata": {
                "logical_name": logical_name,
                "display_label": display_label,
                "source_url": meta.get("source_url"),
                "canonical_label": canonical_label,
                "source_type": meta.get("source_type"),
                "source_class": meta.get("source_class"),
                "page_type": meta.get("page_type"),
                "domain": meta.get("domain"),
                "domain_type": meta.get("domain_type"),
            },
        }

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
        ranked, _, documents_for_ranking = self._search_ranked(
            query, search_mode=mode, filter=filter
        )
        top_scores = ranked[:top_k]

        results = []
        for score_info in top_scores:
            result = self._base_result_fields(documents_for_ranking, score_info["idx"])
            meta = documents_for_ranking["metadatas"][score_info["idx"]]
            result.update(
                {
                    "score": score_info.get("combined_score", 0.0),
                    "semantic_rank": score_info.get("semantic_rank"),
                    "bm25_rank": score_info.get("bm25_rank"),
                    "fused_rank": score_info.get("fused_rank"),
                    "source_prior": score_info.get("source_prior", 0.0),
                    "quality_score": meta.get("quality_score", 1.0),
                }
            )
            results.append(result)
        return results

    def _fetch_filtered_documents(
        self, filter: dict, *, include_embeddings: bool
    ) -> tuple[list[str], list[str], list[list[float]], list[dict[str, Any]]]:
        """Fetch every document matching ``filter``, paginating past the cap.

        ChromaDB's collection.query has no offset parameter and its
        n_results bound would silently truncate large filtered candidate
        sets, so candidates are fetched with paginated collection.get
        calls instead. Final ranking is exact cosine/BM25 over the fetched
        candidates either way.
        """
        include: list[str] = ["documents", "metadatas"]
        if include_embeddings:
            include.append("embeddings")
        ids: list[str] = []
        docs: list[str] = []
        embeddings: list[list[float]] = []
        metadatas: list[dict[str, Any]] = []
        offset = 0
        while True:
            page = cast(
                dict[str, Any],
                self._collection.get(
                    where=filter,
                    limit=_FILTERED_PAGE_SIZE,
                    offset=offset,
                    include=cast(Any, include),
                ),
            )
            page_ids = list(page.get("ids") or [])
            ids.extend(page_ids)
            docs.extend(page.get("documents") or [])
            metadatas.extend(page.get("metadatas") or [])
            if include_embeddings:
                raw_embs = page.get("embeddings")
                if raw_embs is not None:
                    embeddings.extend(
                        emb.tolist() if hasattr(emb, "tolist") else emb for emb in raw_embs
                    )
            if len(page_ids) < _FILTERED_PAGE_SIZE:
                break
            offset += len(page_ids)
        return ids, docs, embeddings, metadatas

    def _search_ranked(
        self, query: str, search_mode: str, filter: dict | None = None
    ) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, list[Any]]]:
        self._rebuild_index_if_needed()
        mode = (search_mode or "rrf_hybrid").lower()
        if mode not in _VALID_SEARCH_MODES:
            raise ValueError(
                f"Invalid search_mode {search_mode!r}; valid modes are {sorted(_VALID_SEARCH_MODES)}"
            )
        trace_info: dict[str, Any] = {"search_mode": mode, "embedding_model": self.embedding_model}

        use_semantic = mode != "bm25_only"
        query_embedding: list[float] | None = None
        if use_semantic:
            try:
                embedding_start = time.time()
                # Query-embedding caching is handled by embedding.py's
                # thread-safe LRU (keyed by model + text).
                query_embedding = embed_texts([query], batch_size=1, model=self.embedding_model)[0]
                trace_info["query_embedding_timing_ms"] = int(
                    (time.time() - embedding_start) * 1000
                )
            except Exception as e:
                logger.warning(f"Embedding failed, falling back to BM25-only search: {e}")
                use_semantic = False
                trace_info["query_embedding_timing_ms"] = 0
        else:
            trace_info["query_embedding_timing_ms"] = 0

        keyword_start = time.time()
        if filter is not None:
            chroma_ids, chroma_docs, chroma_embeddings, chroma_metadatas = (
                self._fetch_filtered_documents(filter, include_embeddings=use_semantic)
            )
            filtered_term_freqs = build_term_frequencies(chroma_docs, self._tokenize)
            filtered_keyword_index = build_keyword_index(chroma_docs, self._tokenize)
            # Score with the same extracted-keywords-aware BM25 as the
            # unfiltered path so a query ranks identically with and
            # without a filter.
            keyword_scores = keyword_score_with_extracted_keywords(
                query,
                contents=chroma_docs,
                keyword_index=filtered_keyword_index,
                doc_term_freqs=filtered_term_freqs,
                tokenize=self._tokenize,
                extracted_keywords_list=_extracted_keywords_from_metadata(chroma_metadatas),
            )
        else:
            # Lazy-load embeddings only when needed for semantic search
            if use_semantic:
                self._ensure_embeddings_loaded()
            chroma_ids = list(self._doc_ids)
            chroma_docs = list(self._doc_contents)
            chroma_embeddings = list(self._doc_embeddings)
            chroma_metadatas = list(self._doc_metadatas)
            keyword_scores = self._keyword_score(query)
        trace_info["keyword_timing_ms"] = int((time.time() - keyword_start) * 1000)

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
        return ranked, trace_info, documents_for_ranking

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

        semantic_start = time.time()
        ranked, search_trace, documents_for_ranking = self._search_ranked(
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
            result = self._base_result_fields(documents_for_ranking, score_info["idx"])
            meta = documents_for_ranking["metadatas"][score_info["idx"]]
            result.update(
                {
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
                }
            )
            results.append(result)

        trace_info["timing_ms"] = int((time.time() - start_time) * 1000)
        return results, trace_info

    def clear(self) -> None:
        all_ids = self._collection.get(include=[]).get("ids", [])
        if all_ids:
            self._collection.delete(ids=all_ids)
        self.content_hashes = set()
        self._id_set = set()
        self._doc_ids = []
        self._doc_contents = []
        self._doc_metadatas = []
        self._doc_embeddings = []
        self._doc_id_to_index = {}
        self.keyword_index = {}
        self._doc_term_freqs = {}
        self._extracted_keywords_list = []
        self._hypothetical_question_cache = []
        self._index_metadata = {}
        self._index_dirty = False
        self.last_indexing_stats = {}
        self._remove_legacy_snapshot()
