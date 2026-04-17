"""Medical document structure rules for intelligent chunking.

Provides heuristics for preserving medical-specific document structures
during chunking: lab value tables, drug dosing sections, clinical note headers.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


class MedicalStructureRules:
    """Heuristics for preserving medical document structure during chunking.

    Identifies and protects:
    - Lab value tables (reference ranges, units)
    - Drug dosing sections (dosage + administration)
    - Clinical note headers (SOAP, history sections)
    """

    # Clinical section headers that should start new chunks
    CLINICAL_SECTIONS = {
        "CHIEF COMPLAINT",
        "HISTORY OF PRESENT ILLNESS",
        "PAST MEDICAL HISTORY",
        "MEDICATIONS",
        "ALLERGIES",
        "SOCIAL HISTORY",
        "FAMILY HISTORY",
        "PHYSICAL EXAMINATION",
        "ASSESSMENT",
        "PLAN",
        "SUBJECTIVE",
        "OBJECTIVE",
        "VITAL SIGNS",
        "LABORATORY RESULTS",
        "RADIOLOGY",
        "DIAGNOSIS",
        "DISPOSITION",
    }

    # Drug dosing section patterns
    DOSING_PATTERNS = [
        r"(?:dosage|dose|administer|administration)\s*:?\s*",
        r"(?:take|takes?|taking)\s+.+?\s+(?:daily|twice daily|bid|tid|qid|prn)",
        r"\d+\s*(?:mg|mcg|g|ml|units?)\s*(?:daily|twice daily|bid|tid|qid|prn|every \d+ hours?)",
    ]

    # Lab table patterns
    LAB_TABLE_PATTERNS = [
        r"(?:test|lab|laboratory|value|reference|range|unit)s?\s*\|\s*",
        r"\|\s*(?:normal|abnormal|high|low|result)\s*\|",
        r"(?:hemoglobin|hematocrit|wbc|rbc|platelet|glucose|creatinine|bun|sodium|potassium)\s*\|",
    ]

    def __init__(self, min_chunk_size: int = 100):
        """Initialize medical structure rules.

        Args:
            min_chunk_size: Minimum chunk size to consider
        """
        self.min_chunk_size = min_chunk_size
        self._compiled_dosing = [re.compile(p, re.IGNORECASE) for p in self.DOSING_PATTERNS]
        self._compiled_lab = [re.compile(p, re.IGNORECASE) for p in self.LAB_TABLE_PATTERNS]

    def is_clinical_section_header(self, line: str) -> bool:
        """Check if line is a clinical section header.

        Args:
            line: Line to check

        Returns:
            True if line appears to be a clinical section header
        """
        stripped = line.strip().upper()
        # Exact match
        if stripped in self.CLINICAL_SECTIONS:
            return True
        # Contains key terms with colon
        if any(term in stripped for term in ("HISTORY", "EXAM", "PLAN", "ASSESSMENT")):
            return ":" in stripped
        return False

    def contains_dosing_info(self, text: str) -> bool:
        """Check if text contains drug dosing information.

        Args:
            text: Text to check

        Returns:
            True if text appears to contain dosing information
        """
        return any(pattern.search(text) for pattern in self._compiled_dosing)

    def is_lab_table(self, text: str) -> bool:
        """Check if text appears to be a lab value table.

        Args:
            text: Text to check

        Returns:
            True if text appears to be a lab table
        """
        # Has pipe separators (table format)
        if "|" not in text:
            return False
        # Has lab-related patterns
        return any(pattern.search(text) for pattern in self._compiled_lab)

    def get_split_positions(self, text: str) -> list[int]:
        """Get preferred split positions based on medical structure.

        Returns positions where chunks should preferentially split
        to preserve medical context.

        Args:
            text: Text to analyze

        Returns:
            Sorted list of character positions for preferred splits
        """
        positions = []
        lines = text.split("\n")
        current_pos = 0

        for line in lines:
            if self.is_clinical_section_header(line):
                positions.append(current_pos)
            current_pos += len(line) + 1  # +1 for newline

        return sorted(set(positions))

    def should_avoid_split(self, text: str, split_pos: int) -> bool:
        """Check if split at position would break medical structure.

        Args:
            text: Full text
            split_pos: Proposed split position

        Returns:
            True if split should be avoided
        """
        before = text[:split_pos]
        after = text[split_pos:]

        # Don't split in middle of dosing section
        if self.contains_dosing_info(before) and self.contains_dosing_info(after):
            # Check if split would separate dosage from administration info
            before_lines = before.split("\n")
            if before_lines and self.contains_dosing_info(before_lines[-1]):
                return True

        # Don't split lab tables
        if self.is_lab_table(before) or self.is_lab_table(after):
            # Check if we're mid-table (has table markers on both sides)
            before_lines = before.split("\n")
            if "|" in before_lines:
                after_first_line = after.split("\n")[0] if after else ""
                if "|" in after_first_line:
                    return True

        return False

    def get_chunk_preservation_score(self, chunk: str) -> float:
        """Score chunk on how well it preserves medical structure.

        Higher score = better preservation of medical context.

        Args:
            chunk: Chunk text to score

        Returns:
            Score from 0.0 to 1.0
        """
        score = 0.5  # Base score

        # Bonus for starting at clinical section
        lines = chunk.split("\n")
        if lines and self.is_clinical_section_header(lines[0]):
            score += 0.2

        # Penalty for splitting dosing info
        if self.contains_dosing_info(chunk):
            # Check if dosing info is complete (has both dosage and frequency)
            has_dosage = bool(re.search(r"\d+\s*(?:mg|mcg|g|ml|units?)", chunk))
            has_frequency = bool(re.search(r"(?:daily|bid|tid|qid|prn)", chunk))
            if has_dosage and has_frequency:
                score += 0.15
            elif has_dosage or has_frequency:
                score -= 0.1

        # Penalty for split lab tables
        if self.is_lab_table(chunk):
            # Check if table looks complete (has header and data rows)
            table_rows = [line for line in lines if "|" in line]
            if len(table_rows) >= 2:
                score += 0.15
            else:
                score -= 0.2

        return min(max(score, 0.0), 1.0)


def get_medical_structure_rules(min_chunk_size: int = 100) -> MedicalStructureRules:
    """Factory function for medical structure rules.

    Args:
        min_chunk_size: Minimum chunk size to consider

    Returns:
        Configured MedicalStructureRules instance
    """
    return MedicalStructureRules(min_chunk_size=min_chunk_size)


def create_medical_boundary_filter(
    rules: MedicalStructureRules | None = None,
) -> Callable[[str, int, int], bool]:
    """Create a boundary filter function for chunking.

    Returns a function compatible with chunking boundary decisions.

    Args:
        rules: MedicalStructureRules instance (created if None)

    Returns:
        Function that takes (text, start, end) and returns True if split allowed
    """
    if rules is None:
        rules = get_medical_structure_rules()

    def boundary_filter(text: str, start: int, end: int) -> bool:
        """Check if split from start to end is allowed."""
        # Get the proposed split position
        split_pos = end

        # Avoid splits that break medical structure
        return not rules.should_avoid_split(text, split_pos)

    return boundary_filter
