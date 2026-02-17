# Health Screening Interpreter Chatbot - Architecture

## Overview

This FastAPI-based chatbot provides evidence-based interpretation of health screening results using Gemini API and RAG (Retrieval-Augmented Generation) with semantic embeddings.

## Project Structure

```
qna_medical_referenced/
├── src/
│   ├── main.py              # FastAPI app entry point
│   ├── run.py               # Server runner script
│   ├── ingest/
│   │   ├── __init__.py      # PDF loading
│   │   └── pdf_loader.py    # PDF text extraction
│   ├── processors/
│   │   ├── __init__.py
│   │   └── chunker.py       # Text chunking (800 tokens, 150 overlap)
│   ├── vectorstore/
│   │   ├── __init__.py
│   │   └── store.py         # Vector store with Gemini embeddings
│   ├── rag/
│   │   ├── __init__.py
│   │   └── retriever.py     # RAG retrieval with semantic search
│   ├── llm/
│   │   ├── __init__.py
│   │   └── client.py        # Gemini API client
│   └── api/
├── data/
│   ├── vectors/             # Persisted embeddings
│   └── raw/
│       ├── LabQAR/
│       │   └── reference_ranges.csv
│       ├── Lipid management...pdf
│       └── managing-pre-diabetes...pdf
├── pyproject.toml
├── .env
└── ARCHITECTURE.md
```

## Implementation Details

### Data Flow

```
User Question → FastAPI /chat endpoint
                     ↓
              retrieve_context(query)
                     ↓
              VectorStore.similarity_search()
                     ↓
              Gemini Embeddings (gemini-embedding-001)
                     ↓
              Cosine similarity scoring
                     ↓
              Top 5 relevant chunks
                     ↓
              GeminiClient.generate(context + prompt)
                     ↓
              Response + Sources
```

### Components

1. **Ingest (src/ingest/)**
   - `PDFLoader`: Extracts text from PDFs using pypdf
   
2. **Processors (src/processors/)**
   - `TextChunker`: Chunks text into 800-token segments with 150-token overlap
   - Preserves semantic boundaries (paragraphs, sentences)

3. **VectorStore (src/vectorstore/)**
   - Uses `gemini-embedding-001` for semantic embeddings
   - Batched embedding (10 at a time) for efficiency
   - Persists embeddings to JSON for fast reload
   - Cosine similarity for ranking

4. **RAG (src/rag/)**
   - `initialize_vector_store()`: Indexes all PDF chunks + reference ranges
   - `retrieve_context(query)`: Retrieves top-k relevant chunks using semantic search

5. **LLM (src/llm/)**
   - `GeminiClient`: Wraps Gemini 2.0 Flash API
   - Medical system prompt with safety instructions

## Retrieval Process

1. **Indexing** (one-time on startup): 
   - Load PDFs → extract text
   - Chunk text (800 tokens, 150 overlap)
   - Load reference ranges from CSV
   - Generate embeddings in batches
   - Persist to `data/vectors/medical_docs.json`

2. **Query**:
   - Generate query embedding
   - Compute cosine similarity with all stored embeddings
   - Return top-k results

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Root endpoint |
| `/health` | GET | Health check |
| `/chat` | POST | Chat with RAG |

## Running the Server

```bash
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000
```

## API Usage

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is a healthy LDL cholesterol level?"}'
```

## Dependencies

- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `google-genai` - Gemini API client (embeddings + generation)
- `pypdf` - PDF text extraction
- `python-dotenv` - Environment variable loading

## Future Enhancements

1. **Reference Ranges Enhancement**
   - Expand CSV with more lab tests
   - Add demographic-specific ranges (age, sex)

2. **API Enhancements**
   - Add conversation history
   - User authentication
   - Rate limiting
   - Better source attribution
