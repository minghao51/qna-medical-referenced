"""HyPE (index-time hypothetical questions) search over the vector store.

Mixin for ChromaVectorStore: searches pre-tokenized hypothetical
questions stored in chunk metadata at ingestion time.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class HypotheticalQuestionSearchMixin:
    """Search hypothetical questions stored in chunk metadata."""

    def _build_hypothetical_question_cache(
        self,
    ) -> list[tuple[float, list[tuple[frozenset[str], str]]]]:
        """Pre-tokenize hypothetical questions so per-query search is cheap.

        Rebuilt on every mirror rebuild (add/clear/cold start), which keeps
        the cache in sync with the stored questions.
        """
        cache: list[tuple[float, list[tuple[frozenset[str], str]]]] = []
        for meta in self._doc_metadatas:
            questions = meta.get("hypothetical_questions") if meta else None
            if not isinstance(questions, list) or not questions:
                continue
            quality_score = float(meta.get("quality_score", 1.0))
            entries = [
                (frozenset(self._tokenize(str(question))), str(question)) for question in questions
            ]
            cache.append((quality_score, entries))
        return cache

    def get_hypothetical_questions(self) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        self._rebuild_index_if_needed()
        for i, doc_id in enumerate(self._doc_ids):
            meta = self._doc_metadatas[i]
            if meta and "hypothetical_questions" in meta:
                result[doc_id] = meta["hypothetical_questions"]
        return result

    def search_hypothetical_questions(self, query: str, *, limit: int = 5) -> list[str]:
        query_tokens = set(self._tokenize(query))
        if not query_tokens:
            return []

        scored: list[tuple[float, str]] = []
        self._rebuild_index_if_needed()
        # Stored questions are pre-tokenized in the cache, which is rebuilt
        # whenever documents are added, cleared, or the mirrors refreshed.
        for quality_score, entries in self._hypothetical_question_cache or []:
            for question_tokens, question in entries:
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
