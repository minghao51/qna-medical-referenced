#!/usr/bin/env python3
"""
L3: Text Chunker - Split documents into smaller chunks.
"""

import copy
import hashlib
import re
from typing import List

DEFAULT_SOURCE_CHUNK_CONFIGS = {
    "pdf": {
        "chunk_size": 650,
        "chunk_overlap": 80,
        "strategy": "recursive",
        "min_chunk_size": 140,
    },
    "markdown": {
        "chunk_size": 600,
        "chunk_overlap": 80,
        "strategy": "recursive",
        "min_chunk_size": 80,
    },
    "default": {
        "chunk_size": 650,
        "chunk_overlap": 80,
        "strategy": "recursive",
        "min_chunk_size": 120,
    },
}
STRUCTURED_CHUNKING_ENABLED = True


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
        content_type: str = "paragraph",
        section_path: list[str] | None = None,
        quality_score: float = 1.0,
        parent_block_ids: list[str] | None = None,
        extractor: str | None = None,
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
                    "content_type": content_type,
                    "section_path": list(section_path or []),
                    "chunk_index": chunk_index,
                    "start_char": trimmed_start,
                    "end_char": trimmed_end,
                    "char_count": len(chunk_text),
                    "token_count_estimate": len(chunk_text.split()),
                    "quality_score": quality_score,
                    "parent_block_ids": list(parent_block_ids or []),
                    "extractor": extractor,
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

    def _quality_score_for_block(self, block: dict) -> float:
        text = str(block.get("text", ""))
        lowered = text.lower()
        score = 1.0
        if len(text.strip()) < self.min_chunk_size:
            score -= 0.35
        boilerplate_hits = sum(lowered.count(term) for term in ("cookie", "privacy", "navigation", "subscribe"))
        if boilerplate_hits:
            score -= min(0.4, 0.08 * boilerplate_hits)
        confidence = str(block.get("metadata", {}).get("confidence", "high"))
        if confidence == "medium":
            score -= 0.15
        elif confidence == "low":
            score -= 0.35
        return max(0.0, min(1.0, score))

    def _chunk_structured_blocks(
        self,
        blocks: list[dict],
        source: str,
        doc_id: str,
        *,
        default_page: int = 1,
        start_chunk_index: int = 0,
    ) -> List[dict]:
        chunks: list[dict] = []
        chunk_index = start_chunk_index
        for block in blocks:
            block_text = str(block.get("text", "")).strip()
            if not block_text:
                continue
            block_type = str(block.get("block_type", "paragraph"))
            page = int(block.get("metadata", {}).get("page", default_page) or default_page)
            section_path = list(block.get("section_path", []))
            quality_score = self._quality_score_for_block(block)
            block_id = str(block.get("id", f"{doc_id}_block_{chunk_index}"))

            if block_type == "heading":
                continue

            if block_type == "table":
                rows = [row for row in block_text.splitlines() if row.strip()]
                group: list[str] = []
                for row in rows:
                    candidate = "\n".join(group + [row]).strip()
                    if group and len(candidate) > max(900, self.chunk_size):
                        chunks.append(
                            self._build_block_chunk(
                                "\n".join(group),
                                source,
                                doc_id,
                                page,
                                chunk_index,
                                "table",
                                section_path,
                                quality_score,
                                [block_id],
                            )
                        )
                        chunk_index += 1
                        group = [row]
                    else:
                        group.append(row)
                if group:
                    chunks.append(
                        self._build_block_chunk(
                            "\n".join(group),
                            source,
                            doc_id,
                            page,
                            chunk_index,
                            "table",
                            section_path,
                            quality_score,
                            [block_id],
                        )
                    )
                    chunk_index += 1
                continue

            if block_type == "list" and len(block_text) <= 900:
                chunks.append(
                    self._build_block_chunk(
                        block_text,
                        source,
                        doc_id,
                        page,
                        chunk_index,
                        "list",
                        section_path,
                        quality_score,
                        [block_id],
                    )
                )
                chunk_index += 1
                continue

            split_chunks = self._chunk_text_with_base_index(
                block_text,
                source,
                doc_id,
                page=page,
                start_chunk_index=chunk_index,
                content_type="list" if block_type == "list" else "paragraph",
                section_path=section_path,
                quality_score=quality_score,
                parent_block_ids=[block_id],
                extractor=str(block.get("metadata", {}).get("extractor", "")) or None,
            )
            chunks.extend(split_chunks)
            chunk_index += len(split_chunks)

        for idx, chunk in enumerate(chunks):
            chunk["previous_chunk_id"] = chunks[idx - 1]["id"] if idx > 0 else None
            chunk["next_chunk_id"] = chunks[idx + 1]["id"] if idx + 1 < len(chunks) else None
            chunk["section_sibling_rank"] = idx
            chunk["source_type"] = self._source_kind(source)
        return chunks

    def _build_block_chunk(
        self,
        text: str,
        source: str,
        doc_id: str,
        page: int,
        chunk_index: int,
        content_type: str,
        section_path: list[str],
        quality_score: float,
        parent_block_ids: list[str],
    ) -> dict:
        text = text.strip()
        return {
            "id": f"{doc_id}_p{page}_chunk_{chunk_index}",
            "source": source,
            "page": page,
            "content": text,
            "content_type": content_type,
            "section_path": list(section_path),
            "chunk_index": chunk_index,
            "start_char": 0,
            "end_char": len(text),
            "char_count": len(text),
            "token_count_estimate": len(text.split()),
            "quality_score": quality_score,
            "parent_block_ids": list(parent_block_ids),
            "previous_chunk_id": None,
            "next_chunk_id": None,
            "section_sibling_rank": 0,
            "source_type": self._source_kind(source),
        }

    def _filter_low_quality_chunks(self, chunks: list[dict]) -> list[dict]:
        filtered: list[dict] = []
        seen_hashes: set[str] = set()
        total_chunks = len(chunks)
        for chunk in chunks:
            content = str(chunk.get("content", "")).strip()
            content_hash = hashlib.sha256(content.lower().encode("utf-8")).hexdigest()[:16] if content else ""
            keep_short = (
                total_chunks <= 2
                or str(chunk.get("content_type")) in {"list", "table"}
                or float(chunk.get("quality_score", 1.0)) >= 0.8
            )
            if len(content) < self.min_chunk_size and not keep_short:
                continue
            if float(chunk.get("quality_score", 1.0)) < 0.45:
                continue
            if content_hash and content_hash in seen_hashes:
                continue
            if content_hash:
                seen_hashes.add(content_hash)
            filtered.append(chunk)
        for idx, chunk in enumerate(filtered):
            chunk["previous_chunk_id"] = filtered[idx - 1]["id"] if idx > 0 else None
            chunk["next_chunk_id"] = filtered[idx + 1]["id"] if idx + 1 < len(filtered) else None
            chunk["section_sibling_rank"] = idx
        return filtered

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
                    blocks = (page_data.get("structured_blocks") or []) if STRUCTURED_CHUNKING_ENABLED else []
                    text = page_data.get("content", "")
                    if blocks:
                        chunks = doc_chunker._chunk_structured_blocks(
                            blocks,
                            source,
                            doc_id,
                            default_page=page_num,
                            start_chunk_index=doc_chunk_index,
                        )
                    elif text:
                        chunks = doc_chunker._chunk_text_with_base_index(
                            text,
                            source,
                            doc_id,
                            page=page_num,
                            start_chunk_index=doc_chunk_index,
                            quality_score=0.8,
                            extractor=str(page_data.get("extractor", "")) or None,
                        )
                    else:
                        chunks = []
                    if chunks:
                        chunks = doc_chunker._filter_low_quality_chunks(chunks)
                        all_chunks.extend(chunks)
                        doc_chunk_index += len(chunks)
            else:
                content = doc.get("content", "")
                page = doc.get("page", 1)
                if STRUCTURED_CHUNKING_ENABLED and doc.get("structured_blocks"):
                    chunks = doc_chunker._chunk_structured_blocks(
                        list(doc.get("structured_blocks", [])),
                        source,
                        doc_id,
                        default_page=page,
                        start_chunk_index=doc_chunk_index,
                    )
                elif str(source).lower().endswith(".md") and doc_chunker.strategy != "legacy":
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
                        quality_score=0.8,
                    )
                chunks = doc_chunker._filter_low_quality_chunks(chunks)
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


def set_structured_chunking_enabled(enabled: bool) -> None:
    global STRUCTURED_CHUNKING_ENABLED
    STRUCTURED_CHUNKING_ENABLED = bool(enabled)
