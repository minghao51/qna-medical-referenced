# Code Conventions

## Python Code Style

### Linting & Formatting
- **Tool**: Ruff
- **Line length**: 100 characters
- **Target version**: Python 3.13
- **Enabled rules**: E (errors), F (pyflakes), I (isort), N (naming), W (warnings)
- **Ignored**: E501 (line too long) - allows long descriptive strings and URLs

### Documentation Style
- **Format**: Google-style docstrings
- **Coverage**: All modules, classes, and functions
- **Contents**: Parameter descriptions, return types, examples
- **Type hints**: Consistent use throughout codebase

### Naming Conventions

| Category | Convention | Example |
|----------|-----------|---------|
| Classes | PascalCase | `Settings`, `RetrievalDiversityConfig` |
| Functions | snake_case | `process_chat_message`, `retrieve_context` |
| Variables | snake_case | `top_k`, `vector_store` |
| Constants | UPPER_SNAKE_CASE | `_RETRIEVAL_OVERFETCH_MULTIPLIER` |
| Private | Leading underscore | `_vector_store_initialized` |

### Error Handling Patterns

#### HTTP Exceptions
```python
from fastapi import HTTPException

raise HTTPException(
    status_code=500,
    detail="An error occurred processing your request"
)
```

#### Validation Errors
- Use Pydantic validation for input data
- Automatic error responses on validation failure

#### Retry Logic
- Implemented with exponential backoff for API calls
- Configurable retry attempts and delays

#### Graceful Degradation
- Optional dependencies handled with try/except
- Fallback behavior when services unavailable

### Logging

#### Logger Setup
```python
import logging

logger = logging.getLogger(__name__)
```

#### Log Levels
- **DEBUG**: Detailed tracing in complex operations
- **INFO**: Normal operation milestones
- **WARNING**: Recoverable issues
- **ERROR**: Error conditions with context

#### Error Messages
- Include both exception type and message
- Provide context for debugging

### Configuration Management

#### Pattern
```python
from pydantic import BaseSettings

class Settings(BaseSettings):
    model_name: str = "qwen3.5-flash"
    api_key: str

    class Config:
        env_prefix = "APP_"
```

#### Principles
- Type-safe configuration with defaults
- Environment variables override defaults
- Validation on import
- Development-friendly defaults

### Import Style

#### Order
1. Standard library imports
2. Third-party imports
3. Local imports organized by module:
   - `from src.config import ...`
   - `from src.app import ...`
   - `from src.rag import ...`
   - etc.

#### Absolute Imports
- Preferred over relative imports
- Clearer dependency tracking

### Decorators

#### Usage
- `@classmethod`: Factory methods
- `@staticmethod`: Utility functions
- `@property`: Computed attributes
- Custom decorators for validation and retry logic

### Data Classes

#### Pattern
```python
from dataclasses import dataclass

@dataclass
class RetrievalConfig:
    top_k: int = 5
    diversity: float = 0.5
```

#### Use Cases
- Configuration objects
- Immutable data structures
- Type validation

### Async Patterns

#### Usage
- Async/await for I/O operations
- Synchronous for CPU-bound operations
- Consistent patterns across modules

## API Response Patterns

### Success Responses
- Consistent Pydantic models
- Union types for conditional structures
- Optional pipeline tracing

### Error Responses
- HTTP status codes
- Detail messages
- Structured error information

## File Organization

### Module Structure
```python
"""Module docstring."""

# Imports
from typing import Optional
from src.config import settings

# Constants
CONSTANT_VALUE = "value"

# Classes
class MyClass:
    """Class docstring."""

# Functions
def my_function():
    """Function docstring."""
```

### File Size Guidelines
- **Preferred**: < 300 lines
- **Acceptable**: 300-500 lines
- **Needs refactoring**: > 500 lines
  - Current examples: `pipeline_assessment.py` (3,748 lines), `step_checks.py` (1,355 lines)

## Frontend Conventions

### TypeScript

#### Configuration
- **Strict mode**: Enabled
- **Module system**: ES modules with `type: "module"`
- **Path aliases**: Configured by SvelteKit

#### Patterns
- Type annotations required
- Interface definitions for data structures
- Async/await for asynchronous operations

### SvelteKit

#### Routing
- File-based routing
- `+page.svelte` for pages
- `+layout.svelte` for layouts
- `+server.ts` for server endpoints

#### Components
- Reusable components in `lib/components/`
- Props with TypeScript types
- Event handling with typed handlers

### Testing

#### Test Structure
- Descriptive test names
- BDD-style (given/when/then)
- Page object pattern for selectors
- Accessibility-first selectors

#### Example
```typescript
test('chat page loads correctly', async ({ page }) => {
  await page.goto(BASE_URL);
  await expect(page).toHaveTitle(/Health Screening Q&A/);
  await expect(page.locator('h1')).toContainText('Health Screening Q&A');
});
```

## Code Quality Patterns

### Type Annotations
- Required for all function parameters
- Required for return types
- Use `Optional` for nullable values
- Use `Union` for multiple types

### Validation
- Pydantic for request/response validation
- Runtime type checking
- Custom validators for complex logic

### Error Messages
- Clear and actionable
- Include context
- Suggest fixes when possible

## Security Patterns

### API Key Management
- Environment variables only
- No hardcoded secrets
- Comma-separated string for multiple keys

### Input Validation
- Pydantic schemas for all inputs
- Type checking
- Range validation

### Data Sanitization
- HTML escaping for user input
- SQL injection prevention (parameterized queries)
- XSS prevention in frontend
