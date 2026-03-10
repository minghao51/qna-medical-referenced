# Configuration Guide

This guide explains all configuration options for the Health Screening Interpreter Chatbot, including environment variables, defaults, and security considerations.

## Overview

The application uses [Pydantic BaseSettings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) for configuration management. Configuration is loaded from:

1. Environment variables (highest priority)
2. `.env` file in the project root
3. Default values defined in `src/config/settings.py`

## Quick Start

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your Dashscope API key:
   ```
   DASHSCOPE_API_KEY=your_api_key_here
   ```

3. Start the application:
   ```bash
   docker-compose up
   ```

## Configuration Reference

### LLM Configuration

#### `DASHSCOPE_API_KEY` (required)
**Default:** (empty string)

Alibaba Dashscope API key for Qwen text generation and embeddings.

**How to get it:**
1. Visit [Dashscope Console](https://dashscope-intl.aliyuncs.com/)
2. Sign in with your Alibaba account
3. Navigate to API Keys section
4. Create a new API key
5. Copy the key and paste it into your `.env` file

**Security:**
- Never commit this key to version control
- Rotate keys periodically for production
- Use separate keys for development and production

#### `MODEL_NAME`
**Default:** `qwen3.5-flash`

Qwen model to use for text generation.

**Options:**
- `qwen3.5-flash` - Fast, cost-effective, good for real-time chat (default)
- `qwen3.5-plus` - Balanced performance and quality
- `qwen-plus` - Higher quality
- `qwen-max` - Highest quality, slower

**When to change:**
- Use `qwen-plus` or `qwen-max` for complex medical queries requiring more accuracy
- Use `qwen3.5-flash` for faster responses in production

#### `EMBEDDING_MODEL`
**Default:** `text-embedding-v4`

Qwen model for generating text embeddings (vector representations).

**Note:** This should rarely need to be changed. Different embedding models have different vector dimensions, requiring re-indexing.

### Storage Configuration

#### `COLLECTION_NAME`
**Default:** `medical_docs`

ChromaDB collection name for vector storage.

**When to change:**
- When you want to maintain separate document collections
- When A/B testing different indexing strategies
- When isolating test data from production data

**Example:**
```bash
# Development collection
COLLECTION_NAME=medical_docs_dev

# Production collection
COLLECTION_NAME=medical_docs_prod
```

#### `DATA_DIR`
**Default:** `data/raw`

Directory for raw downloaded documents (HTML, PDF files).

**When to change:**
- When storing data on a separate volume or mount
- When working with multiple data sources

**Note:** This directory is created automatically if it doesn't exist.

#### `VECTOR_DIR`
**Default:** `data/vectors`

Directory for persistent ChromaDB vector storage.

**When to change:**
- When storing vectors on faster storage (SSD)
- When using network-mounted storage for distributed deployments

**Important:** This directory contains the vector index. Losing it requires re-indexing all documents.

### Chat Configuration

#### `MAX_MESSAGE_LENGTH`
**Default:** `2000`

Maximum message length in characters.

**What it does:**
- Truncates messages exceeding this limit before sending to LLM
- Prevents token limit errors and excessive costs
- Roughly 500 tokens at default setting

**When to adjust:**
- Increase to `4000` for complex queries with more context
- Decrease to `1000` for faster responses and lower costs
- Set to `0` to disable truncation (not recommended)

### API Configuration

#### `ENVIRONMENT`
**Default:** `development`

Runtime environment name. Use `development` or `test` for local work, and `staging` or `production` for internet-exposed deployments.

Outside development/test, the backend requires API keys at startup.

#### `API_KEYS`
**Default:** (not set)

Comma-separated list of valid API keys for client authentication.

**Format:**
```bash
API_KEYS=key1,key2,key3
```

**How clients use it:**
Clients must include the key in the `X-API-Key` header:
```bash
curl -X POST http://localhost:8000/chat \\
  -H "X-API-Key: key1" \\
  -H "Content-Type: application/json" \\
  -d '{"message": "Hello"}'
```

**When to set:**
- **Always** in production deployments
- In development when testing authentication flow
- When deploying to public networks

**Security best practices:**
- Use long, random keys (32+ characters)
- Never reuse keys across applications
- Rotate keys regularly
- Use separate keys for different client types

#### `API_KEYS_JSON`
**Default:** (not set)

Optional JSON array of richer API key records. This supports stable key IDs, hashed secrets, and metadata for ownership or revocation.

**Format:**
```bash
API_KEYS_JSON=[{"id":"frontend","key":"super-secret-key","owner":"web","role":"client","status":"active"}]
```

You may provide either `key` or a SHA-256 `hash`.

#### `CORS_ALLOWED_ORIGINS`
**Default:** local development origins

Comma-separated list of allowed frontend origins. For production, set this explicitly to the deployed frontend origin.

#### `RATE_LIMIT_PER_MINUTE`
**Default:** `60`

Maximum number of requests allowed per minute per client.

**What it does:**
- Tracks requests by authenticated API key when present, otherwise by client IP
- Returns HTTP 429 (Too Many Requests) when exceeded
- Prevents API abuse and runaway costs

**When to adjust:**
- Set to `120` for interactive applications
- Set to `10` for strict rate limiting
- Set to `0` to disable rate limiting (not recommended for production)

### Retry Configuration

#### `MAX_RETRIES`
**Default:** `3`

Maximum number of retry attempts for failed LLM API calls.

**What it does:**
- Automatically retries transient failures (network errors, timeouts)
- Uses exponential backoff between retries
- Prevents temporary issues from causing user-facing errors

**Retry schedule:**
- Attempt 1: Immediate
- Attempt 2: After 1 second
- Attempt 3: After 2 seconds
- Attempt 4: After 4 seconds

**When to adjust:**
- Set to `0` to disable retries (fail fast)
- Set to `5` for more resilience in production
- Set to `1` for faster failure detection

#### `RETRY_DELAY`
**Default:** `1.0`

Initial retry delay in seconds before exponential backoff.

**Formula:**
```
delay = RETRY_DELAY * (2 ^ attempt_number)
```

**When to adjust:**
- Increase to `2.0` for slower but more resilient retries
- Decrease to `0.5` for faster retries
- Set based on observed API recovery times

## Example Configuration Files

### Development (.env.development)
```bash
ENVIRONMENT=development

# LLM
DASHSCOPE_API_KEY=dev_key_xyz
MODEL_NAME=qwen3.5-flash

# Storage
COLLECTION_NAME=medical_docs_dev
DATA_DIR=data/raw
VECTOR_DIR=data/vectors

# Chat
MAX_MESSAGE_LENGTH=2000

# API (optional in development)
# API_KEYS=
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173

# Rate limiting
RATE_LIMIT_PER_MINUTE=60

# Retry
MAX_RETRIES=3
RETRY_DELAY=1.0
```

### Production (.env.production)
```bash
ENVIRONMENT=production

# LLM
DASHSCOPE_API_KEY=prod_key_secure_random
MODEL_NAME=qwen-plus

# Storage
COLLECTION_NAME=medical_docs_prod
DATA_DIR=/mnt/data/raw
VECTOR_DIR=/mnt/data/vectors

# Chat
MAX_MESSAGE_LENGTH=4000

# API (enabled in production)
API_KEYS=key_abc123,key_xyz789
CORS_ALLOWED_ORIGINS=https://your-frontend.example.com

# Rate limiting
RATE_LIMIT_PER_MINUTE=120

# Retry
MAX_RETRIES=5
RETRY_DELAY=2.0
```

### Testing (.env.test)
```bash
ENVIRONMENT=test

# LLM
DASHSCOPE_API_KEY=test_key
MODEL_NAME=qwen3.5-flash

# Storage (use test collections)
COLLECTION_NAME=medical_docs_test
DATA_DIR=/tmp/test_data/raw
VECTOR_DIR=/tmp/test_data/vectors

# Chat
MAX_MESSAGE_LENGTH=1000

# API (disabled in tests)
# API_KEYS=

# Rate limiting (disabled in tests)
RATE_LIMIT_PER_MINUTE=0

# Retry (minimal for faster tests)
MAX_RETRIES=1
RETRY_DELAY=0.1
```

## Troubleshooting

### Backend fails to start in production

**Cause:** `ENVIRONMENT` is set to `staging` or `production` without configured API keys.

**Solution:** Set `API_KEYS` or `API_KEYS_JSON` before starting the API.

### "Empty response from Qwen API" error

**Cause:** API key is invalid or missing.

**Solution:**
1. Verify `DASHSCOPE_API_KEY` is set in `.env`
2. Check the key is valid at [Dashscope Console](https://dashscope-intl.aliyuncs.com/)
3. Ensure the key has not been rotated or revoked

### Rate limit errors during testing

**Cause:** `RATE_LIMIT_PER_MINUTE` is too low for automated tests.

**Solution:** Set `RATE_LIMIT_PER_MINUTE=0` in test environment to disable rate limiting.

### Slow responses

**Cause:** Model is too slow or retry delays are too long.

**Solutions:**
1. Use `MODEL_NAME=qwen3.5-flash` for faster responses
2. Reduce `MAX_RETRIES` to fail faster
3. Reduce `RETRY_DELAY` for quicker retries
4. Check network latency to Dashscope API

### "Collection not found" error

**Cause:** Vector index hasn't been built or `COLLECTION_NAME` is wrong.

**Solutions:**
1. Run the ingestion pipeline to build the index:
   ```bash
   uv run python -m src.cli.ingest
   ```
2. Verify `COLLECTION_NAME` matches the indexed collection
3. Check `VECTOR_DIR` exists and contains index files

### High API costs

**Cause:** `MAX_MESSAGE_LENGTH` is too high or expensive model is used.

**Solutions:**
1. Reduce `MAX_MESSAGE_LENGTH` to truncate longer prompts
2. Use `MODEL_NAME=qwen3.5-flash` instead of `qwen-plus`
3. Implement caching for common queries
4. Monitor usage and set up cost alerts

## Security Checklist

Before deploying to production, ensure:

- [ ] `DASHSCOPE_API_KEY` is set from environment variable, not in code
- [ ] `ENVIRONMENT` is set correctly for the deployment
- [ ] `API_KEYS` or `API_KEYS_JSON` is set with strong, unique keys for each client
- [ ] `CORS_ALLOWED_ORIGINS` only includes trusted frontend origins
- [ ] `.env` file is NOT committed to version control
- [ ] `.env` file has restricted permissions (chmod 600)
- [ ] `RATE_LIMIT_PER_MINUTE` is set to prevent abuse
- [ ] SSL/TLS is enabled for API endpoints
- [ ] API keys are rotated regularly
- [ ] Separate API keys for development and production

## Next Steps

- See [Architecture Documentation](/docs/architecture/README.md) for system design
- See [Testing Guide](/docs/testing/README.md) for testing configuration
- See [README.md](/README.md) for API endpoint documentation
