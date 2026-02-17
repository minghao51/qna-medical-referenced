# Technology Stack

## Languages & Runtime

| Component | Technology | Version |
|-----------|------------|---------|
| Primary Language | Python | >= 3.13 |
| Package Manager | uv | Latest |

## Frameworks & Libraries

### Web Framework
- **FastAPI** (>= 0.129.0) - REST API framework
- **Uvicorn** (>= 0.40.0) - ASGI server

### LLM & AI
- **google-genai** (>= 1.63.0) - Google's Generative AI SDK (Gemini)

### Data Processing
- **pypdf** (>= 6.7.0) - PDF text extraction
- **nltk** (>= 3.9.2) - NLP (stop words, stemming)

### Configuration
- **python-dotenv** (>= 1.2.1) - Environment variable loading
- **pydantic-settings** (>= 2.6.0) - Settings management

## Dev Dependencies

- **pytest** (>= 8.0.0) - Testing framework
- **ruff** (>= 0.8.0) - Linter

## Data Storage

- **JSON file** - Vector embeddings stored at `data/vectors/medical_docs.json`
- **CSV** - Lab reference ranges at `data/raw/LabQAR/reference_ranges.csv`
- **PDF** - Medical guidelines at `data/raw/*.pdf`

## API Providers

- **Google Gemini** - LLM and embeddings
  - Model: `gemini-2.0-flash`
  - Embedding: `gemini-embedding-001` (3072-dim)
