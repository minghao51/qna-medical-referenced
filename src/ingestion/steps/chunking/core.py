"""Core chunking implementation."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, List

from src.ingestion.steps.chunking import config
from src.ingestion.steps.chunking.helpers import (
    build_block_chunk,
    build_chunk_metadata,
    hash_content,
    quality_score_for_block,
    source_kind,
    split_markdown_sections,
)
from src.ingestion.steps.chunking.strategies import find_recursive_split

if TYPE_CHECKING:
    from src.ingestion.steps.chunking.chonkie_adapter import ChonkieChunkerAdapter


class TextChunker:
    """Text chunker with support for multiple chunking strategies.

    Supported strategies:
        - recursive (default): Custom recursive chunker with quality scoring
        - custom_recursive: Alias for recursive
        - chonkie_recursive: Chonkie's RecursiveChunker with overlap refinement
        - chonkie_semantic: Chonkie's SemanticChunker using Qwen embeddings
        - chonkie_late: Chonkie's LateChunker using Qwen embeddings
    """

    SUPPORTED_STRATEGIES = {
        "recursive",
        "custom_recursive",
        "chonkie_recursive",
        "chonkie_semantic",
        "chonkie_late",
    }

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 64,
        strategy: str = "recursive",
        min_chunk_size: int = 100,
        embedding_model: str | None = None,
    ):
        """Initialize TextChunker.

        Args:
            chunk_size: Target chunk size in tokens
            chunk_overlap: Overlap between chunks in tokens
            strategy: Chunking strategy to use
            min_chunk_size: Minimum chunk size (behavior varies by strategy)
            embedding_model: Embedding model for semantic/late strategies
        """
        if strategy not in self.SUPPORTED_STRATEGIES:
            raise ValueError(
                f"TextChunker does not support strategy '{strategy}'. "
                f"Supported: {sorted(self.SUPPORTED_STRATEGIES)}"
            )

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.strategy = strategy
        self.min_chunk_size = min_chunk_size
        self.embedding_model = embedding_model or "text-embedding-v4"
        self._chonkie_adapter: "ChonkieChunkerAdapter | None" = None

    @property
    def chonkie_adapter(self) -> "ChonkieChunkerAdapter | None":
        """Lazy-load chonkie adapter for chonkie strategies."""
        if self.strategy in ("recursive", "custom_recursive"):
            return None

        if self._chonkie_adapter is None:
            from src.ingestion.steps.chunking.chonkie_adapter import get_chonkie_chunker

            self._chonkie_adapter = get_chonkie_chunker(
                strategy=self.strategy,
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                min_chunk_size=self.min_chunk_size,
                embedding_model=self.embedding_model,
            )
        return self._chonkie_adapter

    def chunk_text(
        self, text: str, source: str = "unknown", doc_id: str = "doc", page: int = 1
    ) -> List[dict]:
        # For chonkie strategies, delegate to adapter
        if self.chonkie_adapter is not None:
            return self.chonkie_adapter.chunk_text(text, source, doc_id, page)

        # For recursive (custom), use existing implementation
        return self._chunk_text_with_base_index(
            text, source, doc_id, page=page, start_chunk_index=0
        )

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
        doc_metadata: dict | None = None,
    ) -> List[dict]:
        chunks: list[dict] = []
        start = 0
        text_length = len(text)

        while start < text_length:
            end = start + self.chunk_size

            if end < text_length:
                end = find_recursive_split(
                    text,
                    start,
                    end,
                    chunk_size=self.chunk_size,
                    min_chunk_size=self.min_chunk_size,
                )

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
                chunk_metadata = build_chunk_metadata(doc_metadata)
                chunks.append(
                    {
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
                        "metadata": chunk_metadata,
                    }
                )

            start = end - self.chunk_overlap if end < text_length else text_length

        return chunks

    def _chunk_markdown_document(
        self,
        text: str,
        source: str,
        doc_id: str,
        *,
        page: int = 1,
        start_chunk_index: int = 0,
        doc_metadata: dict | None = None,
    ) -> List[dict]:
        chunks: list[dict] = []
        chunk_index = start_chunk_index
        for section_offset, section_text in split_markdown_sections(text):
            section_chunks = self._chunk_text_with_base_index(
                section_text,
                source,
                doc_id,
                page=page,
                start_chunk_index=chunk_index,
                base_char_offset=section_offset,
                doc_metadata=doc_metadata,
            )
            chunks.extend(section_chunks)
            chunk_index += len(section_chunks)
        return chunks

    def _chunk_structured_blocks(
        self,
        blocks: list[dict],
        source: str,
        doc_id: str,
        *,
        default_page: int = 1,
        start_chunk_index: int = 0,
        doc_metadata: dict | None = None,
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
            quality_score = quality_score_for_block(block, self.min_chunk_size)
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
                            build_block_chunk(
                                text="\n".join(group),
                                source=source,
                                doc_id=doc_id,
                                page=page,
                                chunk_index=chunk_index,
                                content_type="table",
                                section_path=section_path,
                                quality_score=quality_score,
                                parent_block_ids=[block_id],
                                source_type=self._source_kind(source),
                                doc_metadata=doc_metadata,
                            )
                        )
                        chunk_index += 1
                        group = [row]
                    else:
                        group.append(row)
                if group:
                    chunks.append(
                        build_block_chunk(
                            text="\n".join(group),
                            source=source,
                            doc_id=doc_id,
                            page=page,
                            chunk_index=chunk_index,
                            content_type="table",
                            section_path=section_path,
                            quality_score=quality_score,
                            parent_block_ids=[block_id],
                            source_type=self._source_kind(source),
                            doc_metadata=doc_metadata,
                        )
                    )
                    chunk_index += 1
                continue

            if block_type == "list" and len(block_text) <= 900:
                chunks.append(
                    build_block_chunk(
                        text=block_text,
                        source=source,
                        doc_id=doc_id,
                        page=page,
                        chunk_index=chunk_index,
                        content_type="list",
                        section_path=section_path,
                        quality_score=quality_score,
                        parent_block_ids=[block_id],
                        source_type=self._source_kind(source),
                        doc_metadata=doc_metadata,
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
                doc_metadata=doc_metadata,
            )
            chunks.extend(split_chunks)
            chunk_index += len(split_chunks)

        for idx, chunk in enumerate(chunks):
            chunk["previous_chunk_id"] = chunks[idx - 1]["id"] if idx > 0 else None
            chunk["next_chunk_id"] = chunks[idx + 1]["id"] if idx + 1 < len(chunks) else None
            chunk["section_sibling_rank"] = idx
            chunk["source_type"] = self._source_kind(source)
        return chunks

    def _filter_low_quality_chunks(self, chunks: list[dict]) -> list[dict]:
        filtered: list[dict] = []
        seen_hashes: set[str] = set()
        total_chunks = len(chunks)
        for chunk in chunks:
            content = str(chunk.get("content", "")).strip()
            content_hash = hash_content(content)
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

    def chunk_documents(self, documents: List[dict]) -> List[dict]:
        return self.chunk_documents_with_configs(documents, source_chunk_configs=None)

    def chunk_documents_with_configs(
        self,
        documents: List[dict],
        source_chunk_configs: dict | None = None,
    ) -> List[dict]:
        all_chunks = []
        cfg_map = copy.deepcopy(config.DEFAULT_SOURCE_CHUNK_CONFIGS)
        if source_chunk_configs:
            for key, value in source_chunk_configs.items():
                if key in cfg_map and isinstance(value, dict):
                    cfg_map[key].update(value)
                else:
                    cfg_map[key] = dict(value)
        for doc in documents:
            source = doc.get("source", "unknown")
            doc_id = doc.get("id", "doc")
            doc_metadata = doc.get("metadata", {})
            doc_chunk_index = 0
            source_key = self._source_kind(source)
            active_cfg = cfg_map.get(source_key, cfg_map.get("default", {}))
            doc_chunker = (
                self
                if self._matches_self_config(active_cfg)
                else TextChunker(
                    chunk_size=int(active_cfg.get("chunk_size", self.chunk_size)),
                    chunk_overlap=int(active_cfg.get("chunk_overlap", self.chunk_overlap)),
                    strategy=str(active_cfg.get("strategy", self.strategy)),
                    min_chunk_size=int(active_cfg.get("min_chunk_size", self.min_chunk_size)),
                    embedding_model=str(active_cfg.get("embedding_model", self.embedding_model)),
                )
            )

            if "pages" in doc:
                for page_data in doc["pages"]:
                    page_num = page_data.get("page", 1)
                    blocks = (
                        (page_data.get("structured_blocks") or [])
                        if config.is_structured_chunking_enabled()
                        else []
                    )
                    text = page_data.get("content", "")
                    if blocks:
                        chunks = doc_chunker._chunk_structured_blocks(
                            blocks,
                            source,
                            doc_id,
                            default_page=page_num,
                            start_chunk_index=doc_chunk_index,
                            doc_metadata=doc_metadata,
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
                            doc_metadata=doc_metadata,
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
                if config.is_structured_chunking_enabled() and doc.get("structured_blocks"):
                    chunks = doc_chunker._chunk_structured_blocks(
                        list(doc.get("structured_blocks", [])),
                        source,
                        doc_id,
                        default_page=page,
                        start_chunk_index=doc_chunk_index,
                        doc_metadata=doc_metadata,
                    )
                elif str(source).lower().endswith(".md"):
                    chunks = doc_chunker._chunk_markdown_document(
                        content,
                        source,
                        doc_id,
                        page=page,
                        start_chunk_index=doc_chunk_index,
                        doc_metadata=doc_metadata,
                    )
                else:
                    chunks = doc_chunker._chunk_text_with_base_index(
                        content,
                        source,
                        doc_id,
                        page=page,
                        start_chunk_index=doc_chunk_index,
                        quality_score=0.8,
                        doc_metadata=doc_metadata,
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
            and str(cfg.get("embedding_model", self.embedding_model)) == self.embedding_model
        )

    @staticmethod
    def _source_kind(source: str) -> str:
        return source_kind(source)


def chunk_documents(documents: List[dict], source_chunk_configs: dict | None = None) -> List[dict]:
    chunker = TextChunker()
    effective_configs = source_chunk_configs
    if effective_configs is None and config.SOURCE_CHUNK_CONFIGS_OVERRIDE is not None:
        effective_configs = copy.deepcopy(config.SOURCE_CHUNK_CONFIGS_OVERRIDE)
    return chunker.chunk_documents_with_configs(documents, source_chunk_configs=effective_configs)
