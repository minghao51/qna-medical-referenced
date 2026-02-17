# Code Conventions

## Language and Style

- **Language**: Python 3.13+
- **Formatter/Linter**: ruff (configured in pyproject.toml)

## Code Style Patterns

### Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Classes | PascalCase | `GeminiClient`, `VectorStore` |
| Functions | snake_case | `get_client`, `chunk_documents` |
| Variables | snake_case | `pdf_docs`, `query_embedding` |
| Constants | SCREAMING_SNAKE_CASE | `EMBEDDING_MODEL`, `VECTOR_DIR` |
| Private methods | Leading underscore | `_load`, `_save`, `_embed` |

### File Organization

- **Modules**: Single-purpose files in `src/<module>/`
- **Package exports**: `src/<module>/__init__.py`
- **Imports**: Absolute from `src` (e.g., `from src.llm import get_client`)

### Type Hints

- Return types annotated on public functions
- Parameters typed in API layer
- Internal functions may be minimally typed

## Patterns

### Singleton Pattern

```python
_vector_store = None

def get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
```

### Factory Pattern

```python
def get_client() -> GeminiClient:
    return GeminiClient()
```

### Pydantic Models

```python
class ChatRequest(BaseModel):
    message: str
    user_context: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    sources: list[str]
```

### Settings Class

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", ...)
    
    gemini_api_key: str = ""
    model_name: str = "gemini-2.0-flash"
```

## Error Handling

- API endpoints: Try-catch with HTTPException(500)
- File operations: Check existence first
- Global state: Initialization checks
- LLM client: Retry with exponential backoff

## Documentation

- Minimal inline comments (as per CLAUDE.md)
- No docstrings unless explicitly requested

## Dependencies

| Package | Purpose |
|---------|---------|
| fastapi | Web framework |
| pydantic | Data validation |
| google-genai | Gemini API |
| pypdf | PDF extraction |
| python-dotenv | Environment config |
| pydantic-settings | Settings |
| nltk | NLP (stop words, stemming) |
| pytest | Testing |
| ruff | Linting |

## Configuration

- Environment variables via `.env`
- Settings class with defaults in `src/config/settings.py`
