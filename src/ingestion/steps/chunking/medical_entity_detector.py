"""Medical entity detection for chunking boundary hints.

Uses spaCy with optional scispaCy models for detecting medical entities
that should inform chunking boundaries (drugs, conditions, procedures).
"""

from __future__ import annotations

import re
from typing import Any


class MedicalEntityDetector:
    """Detects medical entities that should inform chunking decisions.

    Provides boundary hints to keep related medical content together:
    - Drug names + dosing information
    - Condition names + descriptions
    - Procedures + indications
    """

    # Medical entity categories we care about for chunking
    RELEVANT_ENTITY_LABELS = {
        "DRUG",
        "CHEMICAL",
        "DISEASE",
        "DISORDER",
        "SYMPTOM",
        "PROCEDURE",
        "TREATMENT",
    }

    # Fallback regex patterns for when spaCy models unavailable
    DRUG_PATTERNS = [
        r"\b(?:[A-Z][a-z]*\s+)+(?:\d+\s*(?:mg|mcg|g|ml|units?)[^.]*)(?:\s+(?:oral|IV|IM|SC|topical|inhaled)[^.]*)?",
        r"\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+\d+\s*(?:mg|mcg|g|ml|units?)",
    ]

    CONDITION_PATTERNS = [
        r"\b(?:hypertension|diabetes|hyperlipidemia|anemia|pneumonia|bronchitis|asthma|COPD|CHF|CKD|ESRD|HIV|AIDS)\b",
        r"\b(?:Type\s+[12]\s+diabetes)\b",
    ]

    def __init__(self, model_name: str = "en_core_web_sm"):
        """Initialize medical entity detector.

        Args:
            model_name: spaCy model name. Falls back to regex if unavailable.
        """
        self.model_name = model_name
        self._nlp = None
        self._use_fallback = False

    @property
    def nlp(self):
        """Lazy-load spaCy model."""
        if self._nlp is None:
            try:
                import spacy

                self._nlp = spacy.load(self.model_name, disable=["parser", "lemmatizer"])
            except OSError:
                # Model not installed, use fallback patterns
                self._use_fallback = True
        return self._nlp

    def detect_entities(self, text: str) -> list[dict[str, Any]]:
        """Detect medical entities in text.

        Args:
            text: Text to analyze

        Returns:
            List of entity dicts with keys: text, label, start, end, confidence
        """
        if self._use_fallback or self.nlp is None:
            return self._detect_with_fallback(text)

        doc = self.nlp(text)
        entities = []

        for ent in doc.ents:
            if ent.label_ in self.RELEVANT_ENTITY_LABELS:
                entities.append({
                    "text": ent.text,
                    "label": ent.label_,
                    "start": ent.start_char,
                    "end": ent.end_char,
                    "confidence": 1.0,  # spaCy doesn't provide confidence by default
                })

        return entities

    def _detect_with_fallback(self, text: str) -> list[dict[str, Any]]:
        """Fallback regex-based detection for when spaCy unavailable."""
        entities = []

        for pattern in self.DRUG_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                entities.append({
                    "text": match.group(),
                    "label": "DRUG",
                    "start": match.start(),
                    "end": match.end(),
                    "confidence": 0.7,
                })

        for pattern in self.CONDITION_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                entities.append({
                    "text": match.group(),
                    "label": "DISEASE",
                    "start": match.start(),
                    "end": match.end(),
                    "confidence": 0.8,
                })

        return entities

    def get_boundary_hints(self, text: str) -> list[tuple[int, str]]:
        """Get chunk boundary hints based on entity detection.

        Returns positions where chunks should preferentially break
        to keep medical entities intact.

        Args:
            text: Text to analyze

        Returns:
            List of (position, reason) tuples. Position is char offset.
        """
        entities = self.detect_entities(text)
        hints = []

        for ent in entities:
            # Add hint BEFORE entity (prefer not to break before entity starts)
            if ent["start"] > 0:
                hints.append((ent["start"], f"before_{ent['label'].lower()}"))

            # Add hint AFTER entity (prefer not to break until entity ends)
            if ent["end"] < len(text):
                hints.append((ent["end"], f"after_{ent['label'].lower()}"))

        # Sort by position
        hints.sort(key=lambda x: x[0])
        return hints

    def should_keep_together(self, text_segment: str) -> bool:
        """Check if text segment contains entities that should stay together.

        Args:
            text_segment: Text segment to check

        Returns:
            True if segment contains medical entity relationships to preserve
        """
        entities = self.detect_entities(text_segment)

        # Drug + dosage pattern
        for ent in entities:
            if ent["label"] == "DRUG":
                # Check for dosage info nearby
                dosage_pattern = r"\d+\s*(?:mg|mcg|g|ml|units?)"
                if re.search(dosage_pattern, text_segment, re.IGNORECASE):
                    return True

        return False


def get_medical_entity_detector(model_name: str = "en_core_web_sm") -> MedicalEntityDetector:
    """Factory function for medical entity detector.

    Args:
        model_name: spaCy model name

    Returns:
        Configured MedicalEntityDetector instance
    """
    return MedicalEntityDetector(model_name=model_name)
