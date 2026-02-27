#!/usr/bin/env python3
"""
L3: Text Chunker - Split documents into smaller chunks.
"""

import copy
import re
from typing import List

DEFAULT_SOURCE_CHUNK_CONFIGS = {
    "pdf": {
        "chunk_size": 800,
        "chunk_overlap": 150,
        "strategy": "recursive",
        "min_chunk_size": 120,
    },
    "markdown": {
        "chunk_size": 650,
        "chunk_overlap": 100,
        "strategy": "recursive",
        "min_chunk_size": 80,
    },
    "default": {
        "chunk_size": 800,
        "chunk_overlap": 150,
        "strategy": "recursive",
        "min_chunk_size": 120,
    },
}


class TextChunker:
    def __init__(
        self,
        chunk_size: int = 800,
        chunk_overlap: int = 150,
        strategy: str = "recursive",
        min_chunk_size: int = 120,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.strategy = strategy
        self.min_chunk_size = min_chunk_size

    def chunk_text(self, text: str, source: str = "unknown", doc_id: str = "doc", page: int = 1) -> List[dict]:
        return self._chunk_text_with_base_index(text, source, doc_id, page=page, start_chunk_index=0)

    def _chunk_text_with_base_index(
        self,
        text: str,
        source: str,
        doc_id: str,
        *,
        page: int = 1,
        start_chunk_index: int = 0,
        base_char_offset: int = 0,
    ) -> List[dict]:
        chunks = []
        start = 0
        text_length = len(text)

        while start < text_length:
            end = start + self.chunk_size

            if end < text_length:
                if self.strategy == "legacy":
                    end = self._find_legacy_split(text, start, end)
                else:
                    end = self._find_recursive_split(text, start, end)

            if end <= start:
                end = min(start + self.chunk_size, text_length)

            raw_chunk = text[start:end]
            left_trim = len(raw_chunk) - len(raw_chunk.lstrip())
            right_trim = len(raw_chunk) - len(raw_chunk.rstrip())
            trimmed_start = base_char_offset + start + left_trim
            trimmed_end = base_char_offset + end - right_trim
            chunk_text = raw_chunk.strip()
            if chunk_text:
                chunk_index = start_chunk_index + len(chunks)
                chunks.append({
                    "id": f"{doc_id}_p{page}_chunk_{chunk_index}",
                    "source": source,
                    "page": page,
                    "content": chunk_text,
                    "chunk_index": chunk_index,
                    "start_char": trimmed_start,
                    "end_char": trimmed_end,
                })

            start = end - self.chunk_overlap if end < text_length else text_length

        return chunks

    def _split_markdown_sections(self, text: str) -> list[tuple[int, str]]:
        """
        Split markdown into heading-led sections while preserving original offsets.
        Returns (section_start_offset, section_text).
        """
        heading_matches = list(re.finditer(r"(?m)^#{1,6}\s+.+$", text))
        if not heading_matches:
            return [(0, text)]

        sections: list[tuple[int, str]] = []
        first_heading_start = heading_matches[0].start()
        if first_heading_start > 0:
            preamble = text[:first_heading_start]
            if preamble.strip():
                sections.append((0, preamble))

        for idx, match in enumerate(heading_matches):
            start = match.start()
            end = heading_matches[idx + 1].start() if idx + 1 < len(heading_matches) else len(text)
            section = text[start:end]
            if section.strip():
                sections.append((start, section))
        return sections

    def _chunk_markdown_document(
        self,
        text: str,
        source: str,
        doc_id: str,
        *,
        page: int = 1,
        start_chunk_index: int = 0,
    ) -> List[dict]:
        chunks: list[dict] = []
        chunk_index = start_chunk_index
        for section_offset, section_text in self._split_markdown_sections(text):
            section_chunks = self._chunk_text_with_base_index(
                section_text,
                source,
                doc_id,
                page=page,
                start_chunk_index=chunk_index,
                base_char_offset=section_offset,
            )
            chunks.extend(section_chunks)
            chunk_index += len(section_chunks)
        return chunks

    def _find_legacy_split(self, text: str, start: int, end: int) -> int:
        for sep in ["\n\n", "\n", ". "]:
            last_sep = text.rfind(sep, start, end)
            if last_sep > start:
                return last_sep + len(sep)
        return end

    def _find_recursive_split(self, text: str, start: int, end: int) -> int:
        """
        Prefer stronger boundaries while keeping chunks reasonably sized.
        Falls back to whitespace or hard cut if needed.
        """
        window = text[start:end]
        if not window:
            return end

        min_preferred = max(1, min(self.min_chunk_size, max(1, int(self.chunk_size * 0.6))))
        min_allowed_end = min(end, start + max(min_preferred, self.chunk_size // 4))
        candidate = None

        # Paragraph breaks, then line breaks.
        for sep in ["\n\n", "\n"]:
            pos = text.rfind(sep, min_allowed_end, end)
            if pos > start:
                candidate = pos + len(sep)
                break

        # Sentence boundaries (., ?, !) followed by whitespace/newline.
        if candidate is None:
            sentence_matches = list(re.finditer(r"[.!?](?:\s|\n)", window))
            for match in reversed(sentence_matches):
                abs_end = start + match.end()
                if abs_end >= min_allowed_end:
                    candidate = abs_end
                    break

        # Clause/whitespace fallback.
        if candidate is None:
            for sep in ["; ", ", ", " "]:
                pos = text.rfind(sep, min_allowed_end, end)
                if pos > start:
                    candidate = pos + len(sep)
                    break

        return candidate if candidate is not None else end

    def chunk_documents(self, documents: List[dict]) -> List[dict]:
        return self.chunk_documents_with_configs(documents, source_chunk_configs=None)

    def chunk_documents_with_configs(
        self,
        documents: List[dict],
        source_chunk_configs: dict | None = None,
    ) -> List[dict]:
        all_chunks = []
        cfg_map = copy.deepcopy(DEFAULT_SOURCE_CHUNK_CONFIGS)
        if source_chunk_configs:
            for key, value in source_chunk_configs.items():
                if key in cfg_map and isinstance(value, dict):
                    cfg_map[key].update(value)
                else:
                    cfg_map[key] = dict(value)
        for doc in documents:
            source = doc.get("source", "unknown")
            doc_id = doc.get("id", "doc")
            doc_chunk_index = 0
            source_key = self._source_kind(source)
            active_cfg = cfg_map.get(source_key, cfg_map.get("default", {}))
            doc_chunker = self if self._matches_self_config(active_cfg) else TextChunker(
                chunk_size=int(active_cfg.get("chunk_size", self.chunk_size)),
                chunk_overlap=int(active_cfg.get("chunk_overlap", self.chunk_overlap)),
                strategy=str(active_cfg.get("strategy", self.strategy)),
                min_chunk_size=int(active_cfg.get("min_chunk_size", self.min_chunk_size)),
            )

            if "pages" in doc:
                for page_data in doc["pages"]:
                    page_num = page_data.get("page", 1)
                    text = page_data.get("content", "")
                    if text:
                        chunks = doc_chunker._chunk_text_with_base_index(
                            text,
                            source,
                            doc_id,
                            page=page_num,
                            start_chunk_index=doc_chunk_index,
                        )
                        all_chunks.extend(chunks)
                        doc_chunk_index += len(chunks)
            else:
                content = doc.get("content", "")
                page = doc.get("page", 1)
                if str(source).lower().endswith(".md") and doc_chunker.strategy != "legacy":
                    chunks = doc_chunker._chunk_markdown_document(
                        content,
                        source,
                        doc_id,
                        page=page,
                        start_chunk_index=doc_chunk_index,
                    )
                else:
                    chunks = doc_chunker._chunk_text_with_base_index(
                        content,
                        source,
                        doc_id,
                        page=page,
                        start_chunk_index=doc_chunk_index,
                    )
                all_chunks.extend(chunks)
                doc_chunk_index += len(chunks)

        return all_chunks

    def _matches_self_config(self, cfg: dict) -> bool:
        return (
            int(cfg.get("chunk_size", self.chunk_size)) == self.chunk_size
            and int(cfg.get("chunk_overlap", self.chunk_overlap)) == self.chunk_overlap
            and str(cfg.get("strategy", self.strategy)) == self.strategy
            and int(cfg.get("min_chunk_size", self.min_chunk_size)) == self.min_chunk_size
        )

    @staticmethod
    def _source_kind(source: str) -> str:
        lowered = str(source).lower()
        if lowered.endswith(".pdf"):
            return "pdf"
        if lowered.endswith(".md"):
            return "markdown"
        return "default"


def chunk_documents(documents: List[dict], source_chunk_configs: dict | None = None) -> List[dict]:
    chunker = TextChunker()
    return chunker.chunk_documents_with_configs(documents, source_chunk_configs=source_chunk_configs)
