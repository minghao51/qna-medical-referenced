"""Medical document structure rules for intelligent chunking.

Provides heuristics for preserving medical-specific document structures
during chunking: lab value tables, drug dosing sections, clinical note headers.
"""

from __future__ import annotations

import re
from typing import ClassVar


class MedicalStructureRules:
    """Heuristics for preserving medical document structure during chunking.

    Identifies and protects:
    - Lab value tables (reference ranges, units)
    - Drug dosing sections
    - Clinical note headers (SOAP, history sections)
    """

    CLINICAL_SECTIONS: ClassVar[frozenset[str]] = frozenset(
        {
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
    )

    GUIDELINE_SECTIONS: ClassVar[frozenset[str]] = frozenset(
        {
            "KEY MESSAGES",
            "RECOMMENDATIONS",
            "BACKGROUND",
            "INTRODUCTION",
            "METHODS",
            "RESULTS",
            "DISCUSSION",
            "CONCLUSION",
            "TREATMENT",
            "MANAGEMENT",
            "MONITORING",
            "FOLLOW-UP",
            "FOLLOW UP",
            "SCREENING",
            "PREVENTION",
            "DIAGNOSIS",
            "REFERRAL",
            "SPECIAL POPULATIONS",
            "ADVERSE EFFECTS",
            "CONTRAINDICATIONS",
            "DRUG INTERACTIONS",
            "DOSAGE",
            "ADMINISTRATION",
            "PATIENT EDUCATION",
            "LIFESTYLE",
            "PHARMACOLOGICAL",
            "NON-PHARMACOLOGICAL",
        }
    )

    SECTION_HEADER_PATTERNS: ClassVar[list[re.Pattern[str]]] = [
        re.compile(r"^#{1,4}\s+\w+", re.IGNORECASE),
        re.compile(r"^\d+\.\s+[A-Z][A-Za-z\s]{3,}$"),
        re.compile(r"^[A-Z][A-Z\s]{3,}:$"),
        re.compile(r"^Recommendation\s+\d+", re.I),
    ]

    DOSING_PATTERNS: ClassVar[list[str]] = [
        r"(?:dosage|dose|administer|administration)\s*:?\s*",
        r"(?:take|takes?|taking)\s+.+?\s+(?:daily|twice daily|bid|tid|qid|prn)",
        r"\d+\s*(?:mg|mcg|g|ml|units?)\s*(?:daily|twice daily|bid|tid|qid|prn|every \d+ hours?)",
    ]

    LAB_TABLE_PATTERNS: ClassVar[list[str]] = [
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
        """Check if line is a clinical or guideline section header."""
        stripped = line.strip()
        stripped_upper = stripped.upper()

        # Exact match on clinical or guideline sections
        if stripped_upper in self.CLINICAL_SECTIONS or stripped_upper in self.GUIDELINE_SECTIONS:
            return True

        # Match guideline section patterns
        for pattern in self.SECTION_HEADER_PATTERNS:
            if pattern.match(stripped):
                return True

        # Contains key clinical terms with colon
        if any(term in stripped_upper for term in ("HISTORY", "EXAM", "PLAN", "ASSESSMENT")):
            return ":" in stripped_upper

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
