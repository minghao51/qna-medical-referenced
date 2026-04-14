from fastapi import APIRouter

from src.app.middleware.rate_limit import rate_limiter
from src.rag.runtime import get_runtime_status

router = APIRouter()


@router.get("/")
def root():
    return {"message": "Health Screening Interpreter API is running"}


@router.get("/health")
def health_check():
    runtime_status = get_runtime_status()
    return {
        "status": "healthy",
        "runtime": runtime_status["runtime"],
        "vector_store": runtime_status["vector_store"],
        "rate_limit": {
            "backend": rate_limiter.backend.__class__.__name__,
            "window_seconds": getattr(rate_limiter.backend, "window_seconds", None),
        },
    }
