"""Medical semantic chunking strategy.

Layers medical-aware preprocessing and boundary hints on top of
chonkie_semantic to preserve medical document structure.
"""

from __future__ import annotations

import re
from typing import Any

from src.ingestion.steps.chunking.chonkie_adapter import ChonkieChunkerAdapter
from src.ingestion.steps.chunking.medical_entity_detector import get_medical_entity_detector
from src.ingestion.steps.chunking.medical_structure_rules import get_medical_structure_rules


class MedicalSemanticChunkerAdapter(ChonkieChunkerAdapter):
    """Medical-aware semantic chunking adapter.

    Extends ChonkieChunkerAdapter with:
    - Medical entity detection for boundary hints
    - Medical structure preservation (lab tables, dosing, clinical sections)
    - Quality scoring based on medical context preservation
    """

    def __init__(
        self,
        strategy: str = "medical_semantic",
        chunk_size: int = 512,
        chunk_overlap: int = 64,
        min_chunk_size: int = 100,
        embedding_model: str | None = None,
        medical_model: str = "en_core_web_sm",
    ):
        """Initialize medical semantic chunker adapter.

        Args:
            strategy: Must be "medical_semantic"
            chunk_size: Target chunk size in tokens
            chunk_overlap: Overlap between chunks in tokens
            min_chunk_size: Minimum chunk size
            embedding_model: Embedding model for semantic chunking
            medical_model: spaCy model for medical entity detection
        """
        if strategy != "medical_semantic":
            raise ValueError(f"MedicalSemanticChunkerAdapter only supports 'medical_semantic', got '{strategy}'")

        # Initialize parent with chonkie_semantic as the base strategy
        super().__init__(
            strategy="chonkie_semantic",
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            min_chunk_size=min_chunk_size,
            embedding_model=embedding_model,
        )

        self.medical_model = medical_model
        self._entity_detector = None
        self._structure_rules = None

    @property
    def entity_detector(self):
        """Lazy-load medical entity detector."""
        if self._entity_detector is None:
            self._entity_detector = get_medical_entity_detector(model_name=self.medical_model)
        return self._entity_detector

    @property
    def structure_rules(self):
        """Lazy-load medical structure rules."""
        if self._structure_rules is None:
            self._structure_rules = get_medical_structure_rules(min_chunk_size=self.min_chunk_size)
        return self._structure_rules

    def _apply_medical_preprocessing(self, text: str) -> tuple[str, dict[str, Any]]:
        """Apply medical-aware preprocessing to text.

        Identifies medical structures and returns text with metadata
        about important boundaries.

        Args:
            text: Input text

        Returns:
            Tuple of (preprocessed_text, metadata)
        """
        metadata: dict[str, Any] = {
            "clinical_sections": [],
            "lab_tables": [],
            "dosing_sections": [],
            "entity_boundaries": [],
        }

        # Find clinical section headers
        lines = text.split("\n")
        current_pos = 0
        for line in lines:
            if self.structure_rules.is_clinical_section_header(line):
                metadata["clinical_sections"].append({
                    "text": line.strip(),
                    "position": current_pos,
                })
            current_pos += len(line) + 1

        # Find lab tables
        for i, line in enumerate(lines):
            if self.structure_rules.is_lab_table(line):
                # Get table extent (consecutive lines with pipes)
                table_lines = [line]
                j = i + 1
                while j < len(lines) and "|" in lines[j]:
                    table_lines.append(lines[j])
                    j += 1
                metadata["lab_tables"].append({
                    "content": "\n".join(table_lines),
                    "start_line": i,
                    "end_line": j,
                })

        # Find dosing sections
        for i, line in enumerate(lines):
            if self.structure_rules.contains_dosing_info(line):
                metadata["dosing_sections"].append({
                    "line": i,
                    "text": line,
                })

        # Get entity boundaries
        metadata["entity_boundaries"] = self.entity_detector.get_boundary_hints(text)

        return text, metadata

    def _should_merge_chunks(self, chunk1: dict[str, Any], chunk2: dict[str, Any], metadata: dict[str, Any]) -> bool:
        """Check if two chunks should be merged based on medical structure.

        Args:
            chunk1: First chunk
            chunk2: Second chunk (follows chunk1)
            metadata: Medical preprocessing metadata

        Returns:
            True if chunks should stay together
        """
        content1 = chunk1["content"]
        content2 = chunk2["content"]

        # Don't split mid-dosing section
        if self.entity_detector.should_keep_together(content1 + " " + content2):
            return True

        # Don't split lab tables
        if self.structure_rules.is_lab_table(content1) or self.structure_rules.is_lab_table(content2):
            return True

        # Check if chunk1 ends with incomplete dosing info
        if self.structure_rules.contains_dosing_info(content1):
            # If chunk1 has dosage but no frequency, and chunk2 might complete it
            has_dosage_1 = bool(re.search(r"\d+\s*(?:mg|mcg|g|ml|units?)", content1))
            has_frequency_1 = bool(re.search(r"(?:daily|bid|tid|qid|prn)", content1))
            if has_dosage_1 and not has_frequency_1:
                return True

        return False

    def _post_process_chunks(
        self,
        chunks: list[dict[str, Any]],
        metadata: dict[str, Any],
        original_text: str,
    ) -> list[dict[str, Any]]:
        """Post-process chunks to preserve medical structure.

        Merges chunks that shouldn't be split based on medical rules.

        Args:
            chunks: Initial chunks from chonkie
            metadata: Medical preprocessing metadata
            original_text: Original input text

        Returns:
            Post-processed chunk list
        """
        if not chunks:
            return chunks

        processed = []
        i = 0

        while i < len(chunks):
            current = chunks[i]

            # Check if we should merge with next chunk
            if i + 1 < len(chunks) and self._should_merge_chunks(current, chunks[i + 1], metadata):
                # Merge current and next
                merged = self._merge_two_chunks(current, chunks[i + 1], original_text)
                processed.append(merged)
                i += 2  # Skip the merged chunk
            else:
                processed.append(current)
                i += 1

        # Re-index chunks
        for idx, chunk in enumerate(processed):
            chunk["chunk_index"] = idx
            chunk["id"] = chunk["id"].rsplit("_", 1)[0] + f"_{idx}"

        return processed

    def _merge_two_chunks(self, chunk1: dict[str, Any], chunk2: dict[str, Any], original_text: str) -> dict[str, Any]:
        """Merge two chunks together.

        Args:
            chunk1: First chunk
            chunk2: Second chunk
            original_text: Original text for context

        Returns:
            Merged chunk dict
        """
        merged_content = chunk1["content"] + " " + chunk2["content"]
        merged = dict(chunk1)
        merged["content"] = merged_content
        merged["char_count"] = len(merged_content)
        merged["token_count_estimate"] = len(merged_content.split())

        # Add metadata about merge
        merged.setdefault("metadata", {})["merged_from"] = [
            chunk1["id"],
            chunk2["id"],
        ]

        return merged

    def chunk_text(
        self,
        text: str,
        source: str = "unknown",
        doc_id: str = "doc",
        page: int = 1,
    ) -> list[dict[str, Any]]:
        """Chunk text with medical-aware preprocessing.

        Pre-splits text at detected medical section boundaries,
        then chunks each section separately with chonkie_semantic,
        then post-merges chunks that shouldn't be split.

        Args:
            text: Text to chunk
            source: Source document name
            doc_id: Document identifier
            page: Page number

        Returns:
            List of chunk dictionaries with medical-aware boundaries
        """
        # Apply medical preprocessing
        preprocessed_text, metadata = self._apply_medical_preprocessing(text)

        # Pre-split at section boundaries
        split_positions = self.structure_rules.get_split_positions(preprocessed_text)
        if split_positions:
            all_chunks = []
            prev_pos = 0
            chunk_offset = 0
            for pos in split_positions:
                section_text = preprocessed_text[prev_pos:pos].strip()
                if section_text:
                    section_chunks = super().chunk_text(section_text, source, doc_id, page)
                    # Re-index chunks to maintain global ordering
                    for chunk in section_chunks:
                        chunk["chunk_index"] = chunk_offset
                        chunk["id"] = chunk["id"].rsplit("_", 1)[0] + f"_{chunk_offset}"
                        chunk_offset += 1
                    all_chunks.extend(section_chunks)
                prev_pos = pos
            # Handle remaining text after last split
            remaining = preprocessed_text[prev_pos:].strip()
            if remaining:
                section_chunks = super().chunk_text(remaining, source, doc_id, page)
                for chunk in section_chunks:
                    chunk["chunk_index"] = chunk_offset
                    chunk["id"] = chunk["id"].rsplit("_", 1)[0] + f"_{chunk_offset}"
                    chunk_offset += 1
                all_chunks.extend(section_chunks)
            base_chunks = all_chunks
        else:
            # No section boundaries detected — fall back to standard chunking
            base_chunks = super().chunk_text(preprocessed_text, source, doc_id, page)

        # Post-process to preserve medical structure
        chunks = self._post_process_chunks(base_chunks, metadata, text)

        # Add medical preservation scores
        for chunk in chunks:
            score = self.structure_rules.get_chunk_preservation_score(chunk["content"])
            chunk.setdefault("metadata", {})["medical_preservation_score"] = score

        return chunks


def get_medical_semantic_chunker(
    chunk_size: int = 512,
    chunk_overlap: int = 64,
    min_chunk_size: int = 100,
    embedding_model: str | None = None,
    medical_model: str = "en_core_web_sm",
) -> MedicalSemanticChunkerAdapter:
    """Factory function to get a configured medical semantic chunker.

    Args:
        chunk_size: Target chunk size in tokens
        chunk_overlap: Overlap between chunks
        min_chunk_size: Minimum chunk size
        embedding_model: Embedding model for semantic chunking
        medical_model: spaCy model for medical entity detection

    Returns:
        Configured MedicalSemanticChunkerAdapter instance
    """
    return MedicalSemanticChunkerAdapter(
        strategy="medical_semantic",
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        min_chunk_size=min_chunk_size,
        embedding_model=embedding_model,
        medical_model=medical_model,
    )
