#!/usr/bin/env python3
"""
L6: RAG Pipeline - Initialize vector store and retrieve context.
"""

import logging
import time
from typing import List, Optional, Tuple

from src.pipeline.L2_pdf_loader import get_documents
from src.pipeline.L3_chunker import chunk_documents
from src.pipeline.L4_reference_loader import ReferenceDataLoader
from src.pipeline.L5_vector_store import get_vector_store

logger = logging.getLogger(__name__)


_vector_store_initialized = False


def initialize_vector_store(rebuild: bool = True):
    global _vector_store_initialized
    
    vector_store = get_vector_store()
    
    if rebuild:
        vector_store.clear()
        _vector_store_initialized = False

    if _vector_store_initialized:
        return

    loader = ReferenceDataLoader()

    pdf_docs = get_documents()

    chunked_docs = chunk_documents(pdf_docs)

    ref_docs = loader.load_reference_ranges_as_docs()
    chunked_docs.extend(ref_docs)

    vector_store.add_documents(chunked_docs)

    _vector_store_initialized = True
    print(f"Indexed {len(chunked_docs)} document chunks")


def retrieve_context(query: str, top_k: int = 5):
    initialize_vector_store()

    vector_store = get_vector_store()
    results = vector_store.similarity_search(query, top_k=top_k)

    context_parts = []
    sources = []
    for r in results:
        page_info = f" page {r.get('page', 'N/A')}" if r.get('page') else ""
        source_name = f"{r['source']}{page_info}"
        sources.append(source_name)
        context_parts.append(f"[Source: {source_name}]\n{r['content']}")

    return "\n\n".join(context_parts), sources


def retrieve_context_with_trace(query: str, top_k: int = 5):
    """
    Retrieve context with detailed pipeline trace information.

    Returns:
        tuple: (context, sources, pipeline_trace)
            - context: Formatted context string for LLM
            - sources: List of source names
            - pipeline_trace: Dictionary with detailed pipeline metadata
    """
    from src.models import (
        RetrievedDocument, RetrievalStage, ContextStage,
        GenerationStage, PipelineTrace
    )

    total_start = time.time()

    initialize_vector_store()
    vector_store = get_vector_store()

    retrieval_start = time.time()
    results, retrieval_trace = vector_store.similarity_search_with_trace(query, top_k=top_k)

    retrieved_docs = []
    context_parts = []
    sources = []

    for r in results:
        page_info = f" page {r.get('page', 'N/A')}" if r.get('page') else ""
        source_name = f"{r['source']}{page_info}"
        sources.append(source_name)
        context_parts.append(f"[Source: {source_name}]\n{r['content']}")

        retrieved_docs.append(RetrievedDocument(
            id=r["id"],
            content=r["content"],
            source=r["source"],
            page=r.get("page"),
            semantic_score=r["semantic_score"],
            keyword_score=r["keyword_score"],
            source_boost=r["source_boost"],
            combined_score=r["combined_score"],
            rank=r["rank"]
        ))

    retrieval_timing_ms = retrieval_trace.get("timing_ms", 0)
    retrieval_stage = RetrievalStage(
        query=query,
        top_k=top_k,
        documents=retrieved_docs,
        score_weights=retrieval_trace.get("score_weights", {}),
        timing_ms=retrieval_timing_ms
    )

    context = "\n\n".join(context_parts)
    context_stage = ContextStage(
        total_chunks=len(results),
        total_chars=len(context),
        sources=sources,
        preview=context[:200] + "..." if len(context) > 200 else context
    )

    generation_stage = GenerationStage(
        model="models/gemini-2.5-flash",
        timing_ms=0,
        tokens_estimate=None
    )

    total_time_ms = int((time.time() - total_start) * 1000)
    pipeline_trace = PipelineTrace(
        retrieval=retrieval_stage,
        context=context_stage,
        generation=generation_stage,
        total_time_ms=total_time_ms
    )

    return context, sources, pipeline_trace


def get_full_context() -> str:
    loader = ReferenceDataLoader()
    ranges = loader.load_reference_ranges()
    pdf_texts = loader.load_pdfs_text()
    return f"{ranges}\n\n{pdf_texts}"


def get_context(query: str | None = None) -> Tuple[str, List[str]]:
    if query:
        return retrieve_context(query)
    return get_full_context(), []
