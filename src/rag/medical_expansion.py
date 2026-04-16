"""Medical query expansion provider seam."""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import Protocol

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MedicalExpansion:
    """Normalized medical expansion term plus provenance."""

    term: str
    source: str
    relation: str | None = None

    def normalized(self) -> str:
        return " ".join(str(self.term).split())

    def as_trace_payload(self) -> dict[str, str | None]:
        payload = asdict(self)
        payload["term"] = self.normalized()
        return payload


class MedicalExpansionProvider(Protocol):
    """Provider contract for optional medical ontology expansion."""

    provider_name: str

    def expand(self, query: str, *, base_queries: list[str] | None = None) -> list[MedicalExpansion]:
        """Return normalized medical expansion terms for a query."""


class NoopMedicalExpansionProvider:
    """Default provider that returns no medical expansions."""

    provider_name = "noop"

    def expand(
        self, query: str, *, base_queries: list[str] | None = None
    ) -> list[MedicalExpansion]:
        return []


def get_medical_expansion_provider(
    provider_name: str | None = None,
) -> MedicalExpansionProvider:
    """Return the configured medical expansion provider."""
    if provider_name in {None, "", "noop"}:
        return NoopMedicalExpansionProvider()
    logger.warning("Unknown medical expansion provider '%s', falling back to noop", provider_name)
    return NoopMedicalExpansionProvider()
