# Architecture

## Project Overview

This is a medical Q&A system with RAG (Retrieval-Augmented Generation) capabilities. It combines data from multiple Singapore government health sources, PDFs, and lab reference data to provide accurate medical answers.

## Project Structure

```
src/
├── main.py                    # FastAPI app entry point
├── config/
│   └── settings.py            # Configuration management
├── pipeline/
│   ├── L0_download.py         # Download HTML from health websites
│   ├── L1_html_to_md.py       # Convert HTML to Markdown
│   ├── L2_pdf_loader.py       # Load PDF documents
│   ├── L3_chunker.py          # Text chunking
│   ├── L4_reference_loader.py # Load CSV reference data
│   ├── L5_vector_store.py      # Vector embeddings & storage
│   ├── L6_rag_pipeline.py     # RAG initialization
│   └── run_pipeline.py         # Run full L0-L6 pipeline
├── services/                  # Chat orchestration
├── api/                       # API schemas
├── llm/
│   └── client.py              # Gemini LLM client
└── middleware/
    ├── auth.py                # API key validation
    ├── rate_limit.py          # Rate limiting
    └── request_id.py          # Request ID tracking
```

## Data Pipeline (L0-L6)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    RAG DATA PIPELINE (L0-L6)                        │
└─────────────────────────────────────────────────────────────────────┘

L0: Download    →  L1: Convert    →  L2: Load     →  L3: Chunk
(HTML download)   (HTML→Markdown)   (PDFs)         (800-char)

       ↓                  ↓                ↓              ↓
data/raw/*.html    data/raw/*.md    data/raw/*.pdf  in-memory

L4: Reference    →  L5: Embed      →  L6: RAG
(CSV data)          (Vectors)         (Initialize)

       ↓                  ↓              ↓
in-memory          vector store    ready for
                                   retrieval
```

### L0: Web Content Download (`L0_download.py`)
- Downloads medical content from Singapore government health websites
- Sources: ACE Clinical Guidelines, HealthHub, HPP Guidelines, MOH Singapore
- Output: HTML files in `data/raw/`
- Idempotent: skips download if file exists

### L1: HTML to Markdown (`L1_html_to_md.py`)
- Converts downloaded HTML to clean Markdown
- Uses BeautifulSoup for parsing
- Output: Markdown files in `data/raw/`

### L2: PDF Loading (`L2_pdf_loader.py`)
- Loads PDFs from `data/raw/*.pdf`
- Extracts text per page using pypdf
- Output: List of documents with page content

### L3: Chunking (`L3_chunker.py`)
- Chunks text into 800-char segments with 150-char overlap
- Priority: paragraph → line break → sentence end
- Output: List of text chunks with metadata

### L4: Reference Data (`L4_reference_loader.py`)
- Loads lab reference ranges from CSV
- Converts to document format for indexing
- Output: Reference documents

### L5: Vector Store (`L5_vector_store.py`)
- Generates embeddings via Gemini
- Builds TF-IDF keyword index
- Stores in JSON at `data/vectors/`

### L6: RAG Pipeline (`L6_rag_pipeline.py`)
- Initializes retriever
- Loads vector store for queries
- Output: Ready for query answering

## Query Pipeline

```
User Query → RAG Retriever → Hybrid Search → LLM → Response
                                    ↓
                              ┌──────┴──────┐
                              ↓             ↓
                        Semantic      TF-IDF Keyword
                        (embeddings)  (index + stemming)
```

## Components

### 1. WebDownloader (`src/pipeline/L0_download.py`)
- Downloads HTML from Singapore government health websites
- Sources:
  - **ACE Clinical Guidelines** (ace-hta.gov.sg): 11 clinical guidelines
  - **HealthHub** (healthhub.sg): 5 public health pages
  - **HPP Guidelines** (hpp.moh.gov.sg): 1 guidelines index
  - **MOH Singapore** (moh.gov.sg): 1 main portal
- Output: HTML files in `data/raw/`

### 2. HTMLConverter (`src/pipeline/L1_html_to_md.py`)
- Converts HTML to Markdown using BeautifulSoup
- Strips scripts, styles, nav, footer, header
- Output: Markdown files in `data/raw/`

### 3. PDFLoader (`src/pipeline/L2_pdf_loader.py`)
- Loads PDFs from `data/raw/*.pdf`
- Extracts text per page using pypdf
- Output: `{"id": "...", "source": "...", "pages": [{"page": 1, "content": "..."}]}`

### 4. TextChunker (`src/pipeline/L3_chunker.py`)
- Chunks text into 800-char segments with 150-char overlap
- Priority: paragraph break → line break → sentence end
- Output: `{"id": "...", "content": "...", "source": "...", "page": N}`

### 5. ReferenceDataLoader (`src/pipeline/L4_reference_loader.py`)
- Loads lab reference ranges from CSV files
- Converts to document format
- Combines with PDF/HTML chunks for indexing

### 6. VectorStore (`src/pipeline/L5_vector_store.py`)
- **Semantic search**: Gemini embeddings (3072-dim)
- **Keyword search**: TF-IDF with stemming (Snowball) and stop words
- **Hybrid scoring**: 60% semantic + 20% keyword + 20% source boost
- Persists to JSON at `data/vectors/medical_docs.json`

### 7. GeminiClient (`src/llm/client.py`)
- Wraps Gemini API with retry logic
- Generates responses with RAG context

### 8. Middleware
- **APIKeyMiddleware**: Validates `X-API-Key` header
- **RateLimitMiddleware**: 60 req/min per IP
- **RequestIDMiddleware**: Adds request ID to logs
