"""
RAG Pipeline Module

L0: Download web content from health websites
L1: Convert HTML to Markdown
L2: Load PDF documents
L3: Chunk documents into smaller pieces
L4: Load reference data (CSV)
L5: Embed and store in vector store
L6: Initialize RAG and retrieve context

Usage:
    python -m src.pipeline.run_pipeline           # Run full pipeline
    python -m src.pipeline.run_pipeline --help    # See options
"""

from src.pipeline.L6_rag_pipeline import (
    get_context,
    initialize_vector_store,
    retrieve_context,
    retrieve_context_with_trace,
)

__all__ = [
    "get_context",
    "initialize_vector_store",
    "retrieve_context",
    "retrieve_context_with_trace",
]
