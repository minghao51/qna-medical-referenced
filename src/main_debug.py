from fastapi import APIRouter
from pydantic import BaseModel

from src.rag import retrieve_context

router = APIRouter()


class DebugRequest(BaseModel):
    query: str


@router.post("/debug/context")
def debug_context(request: DebugRequest):
    """Debug endpoint to see what context is retrieved."""
    context, sources = retrieve_context(request.query, top_k=5)
    return {
        "query": request.query,
        "context": context,
        "sources": sources,
        "num_sources": len(sources)
    }
