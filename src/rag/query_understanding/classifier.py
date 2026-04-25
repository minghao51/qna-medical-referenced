"""Query classification for medical Q&A.

Uses rule-based patterns with LLM fallback to classify queries
into types that inform retrieval strategy.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, ClassVar

logger = logging.getLogger(__name__)


class QueryType(Enum):
    """Query type categories for medical Q&A."""

    DEFINITION = "definition"  # "What is X?"
    COMPARISON = "comparison"  # "X vs Y", "Compare X and Y"
    REFERENCE_RANGE = "reference_range"  # "Normal BP range", "Reference values"
    SYMPTOM_QUERY = "symptom_query"  # "Symptoms of anemia"
    TREATMENT = "treatment"  # "Treatment for high cholesterol"
    RISK_FACTOR = "risk_factor"  # "Risk factors for heart disease"
    FOLLOW_UP = "follow_up"  # Context-dependent follow-up questions
    COMPLEX = "complex"  # Multi-part or ambiguous queries


@dataclass(frozen=True)
class QueryClassification:
    """Result of query classification."""

    query_type: QueryType
    confidence: float
    reasoning: str
    sub_queries: list[str] | None = None  # For complex queries


class QueryClassifier:
    """Classifies queries using rule-based patterns with LLM fallback."""

    DEFINITION_PATTERNS: ClassVar[list[str]] = [
        r"^what\s+is\s+",
        r"^define\s+",
        r"^explain\s+",
        r"^meaning\s+of\s+",
        r"\?+$",
    ]

    COMPARISON_PATTERNS: ClassVar[list[str]] = [
        r"\s+vs\s+",
        r"\s+versus\s+",
        r"\s+compared?\s+to\s+",
        r"\s+differ(?:ence|s)?\s+between\s+",
        r"^compare\s+",
    ]

    REFERENCE_RANGE_PATTERNS: ClassVar[list[str]] = [
        r"\bnormal\b.*\b(?:range|value|level|limit)s?\b",
        r"\breference\b.*\b(?:range|value|level)s?\b",
        r"\b(?:target|goal)\b.*\b(?:range|value|level)\b",
        r"\b(?:high|low|elevated|reduced)\b.*\b(?:normal|range)\b",
    ]

    SYMPTOM_PATTERNS: ClassVar[list[str]] = [
        r"\bsymptom",
        r"\bsigns?\s+of\s+",
        r"\bclinical\s+presentation\b",
        r"\bmanifestation",
        r"\bappear(?:s|ance)?\s+of\s+",
    ]

    TREATMENT_PATTERNS: ClassVar[list[str]] = [
        r"\btreat(?:ment|ing|s)?\b",
        r"\bmanage(?:ment)?\b",
        r"\btherapy\b",
        r"\bmedication",
        r"\bdrug\b.*\bfor\b",
        r"\bintervention\b",
    ]

    RISK_FACTOR_PATTERNS: ClassVar[list[str]] = [
        r"\brisk\b.*\bfactor",
        r"\bcause",
        r"\betiology\b",
        r"\bassociated\s+with\b",
        r"\bpredisposing\b",
        r"\bcontribut(?:e|ing|ors?)\b",
    ]

    FOLLOW_UP_PATTERNS: ClassVar[list[str]] = [
        r"^(?:what|how|why|when|where|who)\b",
        r"^(?:is|are|do|does|can|could|should|would)\b",
        r"^(?:tell|explain|describe)\b",
    ]

    def __init__(self, use_llm_fallback: bool = True, llm_client: Any = None):
        """Initialize query classifier.

        Args:
            use_llm_fallback: Whether to use LLM for ambiguous queries
            llm_client: Optional LLM client for classification
        """
        self.use_llm_fallback = use_llm_fallback
        self.llm_client = llm_client
        self._compiled_patterns = self._compile_patterns()

    def _compile_patterns(self) -> dict[QueryType, list[re.Pattern]]:
        """Pre-compile regex patterns for efficiency."""
        return {
            QueryType.DEFINITION: [re.compile(p, re.IGNORECASE) for p in self.DEFINITION_PATTERNS],
            QueryType.COMPARISON: [re.compile(p, re.IGNORECASE) for p in self.COMPARISON_PATTERNS],
            QueryType.REFERENCE_RANGE: [re.compile(p, re.IGNORECASE) for p in self.REFERENCE_RANGE_PATTERNS],
            QueryType.SYMPTOM_QUERY: [re.compile(p, re.IGNORECASE) for p in self.SYMPTOM_PATTERNS],
            QueryType.TREATMENT: [re.compile(p, re.IGNORECASE) for p in self.TREATMENT_PATTERNS],
            QueryType.RISK_FACTOR: [re.compile(p, re.IGNORECASE) for p in self.RISK_FACTOR_PATTERNS],
            QueryType.FOLLOW_UP: [re.compile(p, re.IGNORECASE) for p in self.FOLLOW_UP_PATTERNS],
        }

    def _classify_with_rules(self, query: str) -> QueryClassification | None:
        """Classify query using rule-based patterns.

        Returns None if no pattern matches (ambiguous).
        """
        query_lower = query.lower().strip()

        # Check each query type's patterns
        for query_type, patterns in self._compiled_patterns.items():
            for pattern in patterns:
                if pattern.search(query):
                    confidence = 0.8  # High confidence for rule-based matches
                    reasoning = f"Matched pattern: {pattern.pattern}"

                    # Check for multi-part queries
                    if query_type != QueryType.COMPARISON:
                        # Check for comparison keywords in other types
                        if any(p.search(query_lower) for p in self._compiled_patterns[QueryType.COMPARISON]):
                            return QueryClassification(
                                query_type=QueryType.COMPLEX,
                                confidence=0.7,
                                reasoning="Mixed patterns detected",
                                sub_queries=None,
                            )

                    return QueryClassification(
                        query_type=query_type,
                        confidence=confidence,
                        reasoning=reasoning,
                        sub_queries=None,
                    )

        # No pattern matched
        return None

    async def _classify_with_llm(self, query: str) -> QueryClassification:
        """Classify query using LLM fallback.

        Used when rule-based classification is ambiguous.
        """
        if not self.use_llm_fallback or self.llm_client is None:
            # Default to DEFINITION for unknown queries
            return QueryClassification(
                query_type=QueryType.DEFINITION,
                confidence=0.3,
                reasoning="No pattern matched, LLM fallback disabled",
                sub_queries=None,
            )

        try:
            prompt = f"""Classify the following medical query into one of these types:
- definition: "What is X?"
- comparison: "X vs Y", "Compare X and Y"
- reference_range: "Normal BP range", "Reference values"
- symptom_query: "Symptoms of anemia"
- treatment: "Treatment for high cholesterol"
- risk_factor: "Risk factors for heart disease"
- follow_up: Context-dependent follow-up questions
- complex: Multi-part or ambiguous queries

Query: "{query}"

Respond with just the type name and a brief reasoning, in format: TYPE | reasoning"""

            response = await self.llm_client.generate(prompt)

            if response:
                parts = response.split("|", 1)
                type_str = parts[0].strip().lower()
                reasoning = parts[1].strip() if len(parts) > 1 else "LLM classification"

                # Map string to QueryType
                type_map = {
                    "definition": QueryType.DEFINITION,
                    "comparison": QueryType.COMPARISON,
                    "reference_range": QueryType.REFERENCE_RANGE,
                    "symptom_query": QueryType.SYMPTOM_QUERY,
                    "treatment": QueryType.TREATMENT,
                    "risk_factor": QueryType.RISK_FACTOR,
                    "follow_up": QueryType.FOLLOW_UP,
                    "complex": QueryType.COMPLEX,
                }

                query_type = type_map.get(type_str, QueryType.DEFINITION)
                return QueryClassification(
                    query_type=query_type,
                    confidence=0.6,  # Medium confidence for LLM
                    reasoning=f"LLM: {reasoning}",
                    sub_queries=None,
                )

        except Exception as e:
            logger.warning(f"LLM classification failed for query '{query}': {e}")

        # Fallback to DEFINITION
        return QueryClassification(
            query_type=QueryType.DEFINITION,
            confidence=0.3,
            reasoning="LLM classification failed, defaulting to definition",
            sub_queries=None,
        )

    def classify(self, query: str) -> QueryClassification:
        """Classify a query using rules with LLM fallback.

        Args:
            query: The query text to classify

        Returns:
            QueryClassification with type and confidence
        """
        # Try rule-based classification first
        rule_result = self._classify_with_rules(query)
        if rule_result is not None:
            return rule_result

        # No pattern matched, return default classification
        # (LLM fallback would be async, handled separately)
        return QueryClassification(
            query_type=QueryType.DEFINITION,
            confidence=0.4,
            reasoning="No pattern matched, defaulting to definition",
            sub_queries=None,
        )

    async def classify_async(self, query: str) -> QueryClassification:
        """Async version of classify with LLM fallback.

        Args:
            query: The query text to classify

        Returns:
            QueryClassification with type and confidence
        """
        # Try rule-based classification first
        rule_result = self._classify_with_rules(query)
        if rule_result is not None and rule_result.confidence >= 0.8:
            return rule_result

        # Use LLM for ambiguous queries
        return await self._classify_with_llm(query)


def get_query_classifier(
    use_llm_fallback: bool = True,
    llm_client: Any = None,
) -> QueryClassifier:
    """Factory function for query classifier.

    Args:
        use_llm_fallback: Whether to use LLM for ambiguous queries
        llm_client: Optional LLM client for classification

    Returns:
        Configured QueryClassifier instance
    """
    return QueryClassifier(
        use_llm_fallback=use_llm_fallback,
        llm_client=llm_client,
    )


def classify_query(query: str, llm_client: Any = None) -> QueryClassification:
    """Convenience function to classify a query.

    Args:
        query: The query text to classify
        llm_client: Optional LLM client for fallback

    Returns:
        QueryClassification with type and confidence
    """
    classifier = get_query_classifier(use_llm_fallback=llm_client is not None, llm_client=llm_client)
    return classifier.classify(query)
