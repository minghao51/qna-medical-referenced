# Health Screening Interpreter

A FastAPI-based chatbot that helps users understand their health screening results using RAG (Retrieval-Augmented Generation) with Google Gemini.

## Quick Start

```bash
# Install dependencies
uv sync

# Set up environment variables
cp .env.example .env
# Add your GEMINI_API_KEY to .env

# Run the server
uv run python -m src.main
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Health check |
| `/health` | GET | Service status |
| `/chat` | POST | Submit a question |
| `/history/{session_id}` | GET | Get chat history |
| `/history/{session_id}` | DELETE | Clear chat history |

## Example Request

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"message": "What is a normal LDL cholesterol level?", "session_id": "user123"}'
```

## Request Format

```json
{
  "message": "Your question here",
  "session_id": "optional-session-id",
  "user_context": "optional user context"
}
```

## Response Format

```json
{
  "response": "Answer from the chatbot",
  "sources": ["source1.pdf", "source2.csv"]
}
```

## Project Structure

```
src/
├── main.py              # FastAPI app and endpoints
├── config/              # Settings and configuration
├── inge st/             # PDF and data ingestion
├── llm/                 # Google Gemini client
├── middleware/          # Auth, rate limiting, request ID
├── processors/          # Text chunking
├── rag/                 # Retrieval pipeline
├── storage/             # Chat history (JSON file)
└── vectorstore/         # Embeddings and vector storage
```

## Data Sources

- **PDFs**: Medical guidelines in `data/raw/*.pdf`
- **Reference Ranges**: Lab test norms in `data/raw/LabQAR/reference_ranges.csv`

## Tech Stack

- **FastAPI** - Web framework
- **Google Gemini** - LLM for generation
- **pypdf** - PDF parsing
- **NLTK** - Text processing
- **pytest** - Testing

## Testing

```bash
uv run pytest
```

## Linting

```bash
uv run ruff check .
```
