# Code Conventions

## Python Backend

### Linting & Formatting
- **Tool**: Ruff
- **Line Length**: 100 characters
- **Rules**: E (Error), F (Pyflakes), I (Import), N (Naming), W (Warning)
- **Config**: `pyproject.toml`

### Code Style
- **Naming**: `snake_case` for functions, variables, and files
- **Classes**: `PascalCase`
- **Constants**: `UPPER_SNAKE_CASE`
- **Imports**: Grouped (standard, third-party, local)

### Error Handling
- **Custom Hierarchy**: `AppError` base class with HTTP semantics
- **Pattern**: Structured exceptions with context
- **Logging**: Structured JSON logging with request IDs
- **Validation**: Pydantic models for request/response validation

### Configuration
- **Framework**: Pydantic BaseSettings
- **Environment**: Environment variable support
- **Type Safety**: Full type hints required
- **File**: `src/config/settings.py`

### Dependency Management
- **Tool**: UV package manager
- **Command**: `uv run <command>` for all Python commands
- **File**: `pyproject.toml`

## TypeScript/Svelte Frontend

### Code Style
- **Framework**: SvelteKit 2.50.2
- **TypeScript**: Strict mode enabled
- **Components**: `PascalCase` for component files
- **Utilities**: `camelCase` for utility files

### Build & Development
- **Build Tool**: Vite
- **Dev Server**: Hot module replacement
- **Type Checking**: `svelte-check`
- **Config**: `frontend/tsconfig.json`, `frontend/vite.config.ts`

### API Integration
- **Client**: Fetch API or axios
- **Types**: Centralized in `frontend/src/lib/types.ts`
- **Error Handling**: Structured error responses

## Testing

### Python Tests
- **Framework**: pytest
- **Structure**: All files in `tests/` directory
- **Naming**: `test_*.py` pattern
- **Markers**: Custom pytest markers for test categorization
- **Mocking**: `monkeypatch` for dependencies
- **Live API Tests**: Conditional execution with environment variables

### Frontend Tests
- **Framework**: Playwright (E2E)
- **Config**: `frontend/package.json`
- **Execution**: `npm run e2e`
- **Coverage**: Browser automation for critical user flows

## Common Patterns

### Async Operations
- Use `async/await` for I/O operations
- HTTPX for async HTTP calls
- Proper error handling with try/except blocks

### Logging
- Structured JSON format
- Request ID tracking for distributed tracing
- Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL

### Type Safety
- Full type hints on all Python functions
- Strict TypeScript mode
- Pydantic validation for data models
- Mypy for static type checking

## Documentation
- **Docstrings**: Google style for Python
- **Comments**: Explain "why", not "what"
- **README**: Project overview in root
- **Architecture**: This file and other `.planning/codebase/` files

## Git Conventions
- **Commits**: Concise messages, no Claude Code mentions
- **Branching**: Feature branches
- **Documentation**: Markdown with date prefix `YYYYMMDD-filename.md`
