"""Service layer for business logic.

Services encapsulate business logic and orchestrate between repositories,
external APIs, and other infrastructure. They are injected into route handlers
via FastAPI's dependency injection system.

Architecture:
    Routes (HTTP) → Services (Business Logic) → Repositories (Data Access)

Services should:
- Contain business rules and orchestration logic
- Accept dependencies via constructor injection
- Return domain models, not framework-specific types
- Be testable with mocked repositories
"""

from src.services.evaluation_service import EvaluationService
from src.services.rag_service import RAGService
from src.services.vector_store_service import VectorStoreService

__all__ = [
    "RAGService",
    "EvaluationService",
    "VectorStoreService",
]
