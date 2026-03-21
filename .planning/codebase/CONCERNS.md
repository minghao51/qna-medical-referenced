# Codebase Concerns

## Technical Debt & Bugs

### Large/Complex Files (Refactoring Targets)

**Critical** (>800 lines):
- **`src/app/routes/evaluation.py` (862 lines)** - Evaluation endpoints with multiple responsibilities. Should be split into route handlers, business logic, and response formatting.
- **`src/rag/runtime.py` (816 lines)** - Complex RAG orchestration with retrieval, ranking, and configuration management. Consider extracting retrieval strategies and configuration handlers.

**High Priority** (>500 lines):
- **`src/evals/dataset_builder.py` (622 lines)** - Complex dataset construction logic. Could benefit from builder pattern refactoring.
- **`src/ingestion/steps/download_web.py` (552 lines)** - Web scraping with retry logic and error handling. Extract scraping strategies and error recovery.
- **`src/evals/assessment/orchestrator.py` (524 lines)** - Evaluation orchestration. Consider splitting by evaluation type.
- **`src/ingestion/indexing/vector_store.py` (523 lines)** - Vector store operations. Separate search, indexing, and management.
- **`src/evals/assessment/answer_eval.py` (492 lines)** - Answer evaluation logic. Extract metric calculators.

**Frontend**:
- **`frontend/src/routes/eval/+page.svelte` (2439 lines)** - Extremely large component. Needs breaking into smaller, focused components.

### Known Issues & TODOs

From codebase search (TODO/FIXME/HACK comments):

**High Priority**:
- **`docs/reports/2026-03/20260319-immediate-actions-summary.md`**:
  - "Better error messages for debugging"
  - Test assertions need updates
  - Missing retry logic implementation

**Medium Priority**:
- **`src/rag/runtime.py`**: Configuration management could be extracted
- **`src/ingestion/steps/download_web.py`**: Error handling patterns need consistency
- **`tests/test_ingestion_error_handling.py`**: Actual retry logic needs implementation

## Security Concerns

### API Key Management

**Issues**:
- Empty default string for `dashscope_api_key` in settings could lead to runtime errors
- Test fixtures use hardcoded "secret-key" (acceptable for tests but not production)

**Recommendations**:
- Validate required API keys on startup
- Add clear error messages for missing configuration
- Consider API key rotation strategy

### Authentication & Authorization

**Current State**:
- API key-based authentication implemented
- SHA256 hashing for stored keys
- Role-based access (owner, role fields defined)

**Concerns**:
- No rate limiting per API key (only global or anonymous)
- No key expiration or rotation mechanism
- Test keys might be committed to repository

### Rate Limiting

**Issues**:
- `docker-compose.yml` sets `RATE_LIMIT_PER_MINUTE=0` (disabled)
- No rate limiting in Docker configuration
- Anonymous and authenticated users share same rate limit database

**Recommendations**:
- Enable rate limiting in production
- Separate rate limits for anonymous vs authenticated users
- Consider Redis for distributed rate limiting in production

### CORS Configuration

**Current State**:
- Long list of allowed origins in settings
- Development origins included in production config

**Recommendations**:
- Use environment-specific CORS settings
- Remove development origins from production
- Consider origin whitelisting approach

## Performance Concerns

### Memory Usage

**Issues**:
- Large Svelte component (2439 lines) may impact frontend performance
- Complex ingestion pipeline with potential memory overhead
- No streaming for large document processing

**Recommendations**:
- Implement streaming for document ingestion
- Add memory profiling to ingestion pipeline
- Consider pagination for large evaluation results

### Database Performance

**Issues**:
- SQLite for rate limiting may not scale
- File-based chat history store (no concurrent access optimization)
- No connection pooling for SQLite

**Recommendations**:
- Consider PostgreSQL for production
- Implement proper connection pooling
- Add database indexes for common queries

### Caching

**Current State**:
- Limited caching implementation
- Vector store initialization is global (potential race condition)
- No LLM response caching

**Recommendations**:
- Implement response caching for common queries
- Add cache invalidation strategy
- Consider Redis for distributed caching

## Architecture Concerns

### Potential Circular Dependencies

**Risk Areas**:
- `src/rag/runtime.py` imports from multiple modules (ingestion, indexing, rag)
- Complex interdependencies between evaluation components

**Mitigation**:
- Define clear layer boundaries
- Use dependency injection
- Consider hexagonal architecture patterns

### Code Complexity

**Issues**:
- Mixed responsibilities in runtime layer
- Global state usage (`_vector_store_initialized`)
- Module-level variables could cause issues in testing

**Recommendations**:
- Extract configuration management
- Use dependency injection instead of globals
- Implement proper lifecycle management

### Error Handling

**Issues**:
- Inconsistent error handling patterns across modules
- Some endpoints lack proper error handling
- Generic error messages in some cases

**Recommendations**:
- Standardize error handling approach
- Add specific error codes for different failure modes
- Implement error aggregation for better debugging

## Testing & Reliability

### Test Coverage

**Current State**:
- Good test coverage for core functionality
- Separate test files for different components
- Integration and E2E tests present

**Gaps**:
- Limited coverage for error scenarios
- Few tests for concurrent operations
- Missing performance regression tests

**Recommendations**:
- Add property-based testing for complex logic
- Implement chaos engineering tests
- Add performance benchmarking

### Error Handling Tests

**Issues**:
- `tests/test_ingestion_error_handling.py` mentions "actual retry logic needs implementation"
- Limited tests for partial failure scenarios
- Missing tests for timeout handling

**Recommendations**:
- Implement comprehensive retry logic tests
- Add tests for timeout and cancellation
- Test partial failure scenarios

### Test Data Management

**Issues**:
- Test fixtures scattered across files
- No centralized test data management
- Some tests may depend on execution order

**Recommendations**:
- Centralize test data in `tests/fixtures/`
- Ensure test independence
- Add test data validation

## Configuration Management

### Environment Configuration

**Issues**:
- Complex configuration with many settings
- No configuration validation on startup
- Missing required field validation

**Recommendations**:
- Implement configuration validation schema
- Add startup checks for required settings
- Provide clear error messages for misconfiguration

### Feature Flags

**Issues**:
- Various enable/disable flags throughout codebase
- No centralized feature flag management
- Feature flags scattered in code

**Recommendations**:
- Implement centralized feature flag system
- Add feature flag audit logging
- Consider remote configuration service

## Documentation Concerns

### Missing Documentation

**Gaps**:
- Several documents mention "detailed design to be created after Phase 1/2/3"
- Limited operational documentation
- Missing debugging guides

**Recommendations**:
- Complete outstanding design documents
- Add operational runbooks
- Create troubleshooting guides

### Code Documentation

**Issues**:
- Inconsistent docstring coverage
- Some complex functions lack examples
- Missing architecture decision records (ADRs)

**Recommendations**:
- Enforce docstring coverage requirements
- Add usage examples for complex APIs
- Document key architectural decisions

## Deployment Concerns

### Container Configuration

**Issues**:
- Resource limits may not be optimal for production
- Health check interval may be too long (30s)
- No graceful shutdown handling

**Recommendations**:
- Tune resource limits based on actual usage
- Reduce health check interval
- Implement proper shutdown handlers

### Logging & Monitoring

**Issues**:
- Limited structured logging
- No distributed tracing
- Missing metrics collection

**Recommendations**:
- Add structured logging throughout
- Implement distributed tracing (e.g., OpenTelemetry)
- Add Prometheus metrics export

### Backup & Recovery

**Issues**:
- No backup strategy for chat history
- No disaster recovery procedures
- Missing data migration scripts

**Recommendations**:
- Implement regular backup strategy
- Create disaster recovery runbooks
- Add data migration tools

## Frontend Concerns

### Component Size

**Critical**:
- **`frontend/src/routes/eval/+page.svelte` (2439 lines)** - Needs immediate refactoring

**Recommendations**:
- Split into multiple components
- Extract business logic to separate files
- Consider lazy loading for large components

### State Management

**Issues**:
- No centralized state management
- Props drilling in some components
- Limited state persistence

**Recommendations**:
- Consider Svelte stores for global state
- Implement proper state persistence
- Add state management documentation

## Dependency Management

### Python Dependencies

**Issues**:
- Some dependencies may be outdated
- No vulnerability scanning in CI
- Limited dependency update strategy

**Recommendations**:
- Implement Dependabot or Renovate
- Add security scanning to CI
- Schedule regular dependency updates

### Frontend Dependencies

**Issues**:
- Mixed use of bun and npm
- No lock file commit strategy
- Potential dependency conflicts

**Recommendations**:
- Standardize on one package manager
- Commit lock files
- Add dependency audit to CI

## Accessibility & UX

### Frontend Accessibility

**Issues**:
- Limited ARIA labels
- Missing keyboard navigation
- No screen reader testing

**Recommendations**:
- Add comprehensive ARIA labels
- Implement keyboard navigation
- Conduct accessibility audit

### User Experience

**Issues**:
- Limited loading states
- No optimistic updates
- Missing error recovery UI

**Recommendations**:
- Add comprehensive loading states
- Implement optimistic updates
- Design error recovery flows
