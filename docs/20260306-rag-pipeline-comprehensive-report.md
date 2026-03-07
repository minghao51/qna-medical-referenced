# RAG Pipeline Comprehensive Technical Report

**Date:** 2026-03-06
**System:** Medical Q&A RAG Pipeline
**Version:** Current Production

---

## Executive Summary

This report provides a comprehensive technical overview of the data ingestion, retrieval-augmented generation (RAG), keyword extraction, embedding generation, and quality metrics framework for the medical Q&A chat system. The system implements a sophisticated hybrid search architecture combining semantic similarity (60%), keyword matching (20%), and source prioritization (20%) with advanced diversification strategies.

### Key Technologies
- **Embedding Model:** Qwen `text-embedding-v4` (2048 dimensions)
- **LLM:** Qwen 3.5 Flash via Dashscope API
- **Search:** Reciprocal Rank Fusion (RRF) with BM25
- **Diversification:** Maximal Marginal Relevance (MMR)
- **Storage:** JSON-based vector persistence

### System Capabilities
- Multi-source document ingestion (HTML, PDF, CSV)
- Source-aware chunking strategies
- Query expansion with acronym support
- Real-time quality monitoring across 6 pipeline stages
- Comprehensive evaluation dashboard with historical trending

---

## 1. Data Ingestion Pipeline (L0-L5)

### L0: Web Content Download
**File:** `src/ingestion/steps/download_web.py`

**Process:**
- Downloads HTML content from Singapore government health websites (ACE Clinical Guidelines, HealthHub, HPP Guidelines, MOH)
- Maintains `download_manifest.json` for tracking
- Deduplicates content using SHA256 hash comparison
- Normalizes URLs and generates safe filenames
- Uses `httpx` for async HTTP requests with timeout handling

**Quality Metrics:**
- HTML file inventory completeness
- Parse success rate
- Duplicate file detection
- Small file rate (< 2KB threshold)
- Manifest record validation

### L0b: PDF Document Ingestion
**File:** `src/ingestion/steps/load_pdfs.py`

**Process:**
- Multi-pass extraction using both `pypdf` and `pdfplumber`
- Quality scoring based on extraction confidence
- Structured blocks with page-level metadata
- Automatic fallback to pdfplumber when pypdf yields poor quality
- Artifact persistence using `SourceArtifact` for metadata

**Quality Metrics:**
- Page extraction coverage
- Empty page rate (< 20% threshold)
- Extractor fallback rate
- Low confidence page rate
- OCR required rate
- Table extraction success proxy

### L1: HTML to Markdown Conversion
**File:** `src/ingestion/steps/load_markdown.py`

**Process:**
- Converts HTML to clean Markdown format
- Removes boilerplate content
- Preserves headings and structure

**Quality Metrics:**
- Markdown empty rate (< 10% threshold)
- Content retention ratio
- Boilerplate detection
- Heading preservation rate
- Table preservation rate
- Page classification distribution

### L2: PDF Structured Extraction
**File:** `src/ingestion/steps/load_pdfs.py`

**Process:**
- Classifies content types (paragraph, table, list, heading)
- Extracts metadata (page numbers, confidence scores)
- Creates structured blocks with section paths
- Tracks extractor type (pypdf vs pdfplumber)

### L3: Document Chunking
**File:** `src/ingestion/steps/chunk_text.py`

**Chunk Configuration:**

| Source Type | Chunk Size | Overlap | Strategy | Min Chunk Size |
|-------------|------------|---------|----------|----------------|
| PDF         | 650        | 80      | Recursive | 140           |
| Markdown    | 600        | 80      | Recursive | 80            |
| Default     | 650        | 80      | Recursive | 120           |

**Code Reference:** `src/ingestion/steps/chunk_text.py:11-30`

```python
DEFAULT_SOURCE_CHUNK_CONFIGS = {
    "pdf": {
        "chunk_size": 650,
        "chunk_overlap": 80,
        "strategy": "recursive",
        "min_chunk_size": 140,
    },
    "markdown": {
        "chunk_size": 600,
        "chunk_overlap": 80,
        "strategy": "recursive",
        "min_chunk_size": 80,
    },
    "default": {
        "chunk_size": 650,
        "chunk_overlap": 80,
        "strategy": "recursive",
        "min_chunk_size": 120,
    },
}
```

**Chunking Strategies:**
1. **Recursive splitting** with boundary preference: `\n\n` → `\n` → sentence → clause
2. **Structured chunking** for PDFs (headings, paragraphs, tables, lists)
3. **Markdown section awareness** preserves document structure
4. **Quality scoring** filters low-quality chunks (boilerplate, short content)

**Metadata Preservation:**
- Character offsets and page numbers
- Content type classification (paragraph, table, list)
- Section path and sibling rank tracking
- Previous/next chunk relationships
- Quality score (0.0-1.0)

**Quality Metrics:**
- Duplicate chunk rate (< 5% threshold)
- Boundary cut rate
- Observed overlap accuracy
- Section integrity rate
- Table row split violations
- Chunk quality distribution (high/medium/low)

### L4: Reference Data Loading
**File:** `src/ingestion/steps/load_reference_data.py`

**Process:**
- Loads CSV reference ranges from `LabQAR/reference_ranges.csv`
- Validates required columns: `test_name`, `normal_range`, `unit`, `category`, `notes`
- Converts to document format for embedding

**Quality Metrics:**
- CSV schema validation
- Row completeness rate
- Duplicate test name detection
- Normal range parseability

### L5: Embedding and Vector Storage
**File:** `src/ingestion/indexing/embedding.py`, `src/ingestion/indexing/vector_store.py`

**Embedding Configuration:**
- **Model:** `text-embedding-v4`
- **Dimensions:** 2048
- **API:** Dashscope (Singapore region)
- **Base URL:** `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`
- **Batch Size:** 10 texts per API call
- **Text Sanitization:** Applied before embedding generation

**Storage Structure:**
- JSON persistence under `data/vectors/`
- Deduplication by content hash and document ID
- Metadata preservation for chunk-level information

**Quality Metrics:**
- Vector embedding dimension consistency
- Short content rate
- Source distribution tracking
- Deduplication effect estimate
- Index file size monitoring

---

## 2. Hybrid Search Architecture

### Search Components

The system implements a **three-component hybrid search** with configurable weights:

```python
# Default weights from src/ingestion/indexing/vector_store.py
semantic_weight: float = 0.6    # 60% semantic search
keyword_weight: float = 0.2     # 20% keyword search
boost_weight: float = 0.2       # 20% source boost
```

**Code Reference:** `src/ingestion/indexing/vector_store.py` (VectorStore.__init__)

### 1. Semantic Search (60% weight)

**Method:** Cosine similarity between query and document embeddings

**Calculation:**
```python
# src/ingestion/indexing/search.py:8-12
def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot_product = sum(x * y for x, y in zip(a, b))
    magnitude_a = sum(x * x for x in a) ** 0.5
    magnitude_b = sum(y * y for y in b) ** 0.5
    return dot_product / (magnitude_a * magnitude_b) if magnitude_a * magnitude_b > 0 else 0.0
```

**Characteristics:**
- Captures semantic meaning and context
- Robust to synonym variations
- Handles medical terminology well
- Enables concept-based retrieval

### 2. Keyword Search (20% weight)

**Method:** BM25 (Best Matching 25) algorithm

**Parameters:**
```python
k1 = 1.5    # Term frequency saturation parameter
b = 0.75    # Document length normalization parameter
```

**Characteristics:**
- Exact keyword matching
- Term frequency weighting
- Document length normalization
- Effective for specific medical terms, drug names

### 3. Source Prioritization (20% weight)

**Method:** Document type-based boosting

**Source Priors:**
```python
# src/ingestion/indexing/search.py:15-22
def source_prior_for(source_class: str) -> float:
    priors = {
        "guideline_pdf": 0.15,      # Highest priority
        "reference_csv": 0.12,
        "guideline_html": 0.10,
        "index_page": 0.02,         # Lowest priority
    }
    return priors.get(source_class, 0.05)  # Default 5%
```

**Rationale:**
- PDF guidelines are most authoritative
- Reference data (lab ranges) is highly reliable
- HTML guidelines are trustworthy
- Index/listing pages are less relevant

### Score Combination

**Weighted Combination (legacy_hybrid mode):**
```python
combined_score = (
    semantic_weight * semantic_score +
    keyword_weight * normalized_keyword_score +
    boost_weight * source_prior
)
```

**Code Reference:** `src/ingestion/indexing/search.py:46-51`

### Reciprocal Rank Fusion (RRF)

**Default Search Mode:** `rrf_hybrid`

RRF combines ranked results from semantic and keyword search:

```python
# src/ingestion/indexing/search.py:71-102
def reciprocal_rank_fusion(
    semantic_ranked: list[dict],
    keyword_ranked: list[dict],
    *,
    k: int = 60,
) -> list[dict]:
    # Fuse ranks using formula: 1 / (k + rank)
    # Add source prior to fused score
    # Sort by fused_score, then semantic_score, then keyword_score
```

**Advantages:**
- Normalizes different scoring scales
- Robust to score magnitude differences
- Gives equal weight to ranking position
- Reduces impact of score outliers

**RRF Formula:**
```
fused_score = 1 / (k + semantic_rank) + 1 / (k + keyword_rank) + source_prior
```

Where `k = 60` (default constant)

---

## 3. Retrieval Configuration

### Query Expansion

**File:** `src/rag/runtime.py:60-82`

The system expands queries in multiple ways:

```python
def _expand_queries(query: str) -> list[str]:
    # 1. Original query
    # 2. Tokenized version
    # 3. Acronym expansions
    # 4. Keyword-focused version (removes stop words)
```

**Example:**
- Input: "What is BP?"
- Expanded queries:
  1. "What is BP?"
  2. "What BP?"
  3. "What is BP? blood pressure"
  4. "BP blood pressure" (keyword-focused)

**Multi-Query Retrieval:**
- Each expanded query is searched independently
- Results are merged, keeping highest scores
- Final result is diversified and ranked

### Diversification Strategy

**File:** `src/rag/runtime.py:176-242`

**Configuration:**
```python
# src/rag/runtime.py:21-25
_RETRIEVAL_OVERFETCH_MULTIPLIER = 4        # Retrieve 4x candidates
_MAX_CHUNKS_PER_SOURCE_PAGE = 2           # Max 2 chunks per page
_MAX_CHUNKS_PER_SOURCE = 3                # Max 3 chunks per document
_MMR_LAMBDA = 0.75                        # 75% relevance, 25% diversity
```

**MMR (Maximal Marginal Relevance):**

```
MMR_score = λ * relevance_score - (1 - λ) * redundancy_score
```

Where:
- `λ = 0.75` (balance toward relevance)
- `redundancy` = max similarity to already-selected chunks
- Similarity calculated via token overlap

**Diversity Constraints:**
1. **Duplicate removal:** SHA256 content hash deduplication
2. **Source page limits:** Max 2 chunks per page
3. **Source document limits:** Max 3 chunks per document
4. **Content similarity:** Penalizes semantically similar chunks

**Search Modes Available:**

| Mode | Description | Use Case |
|------|-------------|----------|
| `rrf_hybrid` | Reciprocal Rank Fusion (default) | Balanced retrieval |
| `semantic_only` | Vector similarity only | Concept queries |
| `bm25_only` | Keyword search only | Exact term matching |
| `legacy_hybrid` | Weighted combination | Custom tuning |

**Code Reference:** `src/rag/runtime.py:245-263` (retrieve_context function)

---

## 4. Quality Metrics Framework

### L6: Retrieval Quality Metrics

**Core Metrics:**

1. **Hit Rate @k**
   - Fraction of queries with ≥1 relevant document in top-k
   - Formula: `queries_with_hit / total_queries`
   - Threshold: ≥70% (high confidence subset)

2. **MRR (Mean Reciprocal Rank)**
   - Average of 1/rank for first relevant document
   - Formula: `mean(1 / first_relevant_rank)`
   - Threshold: ≥0.40 (high confidence subset)

3. **NDCG @k (Normalized Discounted Cumulative Gain)**
   - Position-weighted relevance score
   - Accounts for ranking quality
   - Higher positions contribute more

4. **Precision @k / Recall @k**
   - Standard information retrieval metrics
   - Precision: relevant_documents / retrieved_documents
   - Recall: relevant_documents / total_relevant_documents

5. **Source Hit Rate**
   - Expected source document appearance rate
   - Measures source coverage

6. **Exact Chunk Hit Rate**
   - Exact chunk ID retrieval rate
   - Threshold: ≥40%

7. **Evidence Hit Rate**
   - Evidence phrase found in retrieved documents
   - Threshold: ≥50%

8. **Latency Metrics**
   - p50/p95 percentiles in milliseconds
   - Tracks performance over time

**Relevance Judgment Criteria:**

A document is considered relevant if it meets ANY of:
- Expected source match
- Evidence phrase presence
- Keyword overlap (minimum 2 keywords)
- Exact chunk ID match

### Pipeline Quality Metrics (L0-L5)

**Quality Thresholds:**

| Stage | Metric | Threshold |
|-------|--------|-----------|
| L0 | Small file rate | < 2KB |
| L1 | Markdown empty rate | < 10% |
| L2 | Empty page rate | < 20% |
| L3 | Duplicate chunk rate | < 5% |
| L4 | Schema validation | 100% |
| L5 | Dimension consistency | 2048 |

### Health Score System

**Composite Score Calculation:**

```
Health Score = (
    0.40 * retrieval_score +
    0.30 * data_quality_score +
    0.20 * performance_score +
    0.10 * completeness_score
)
```

**Grade Assignment:**

| Score Range | Grade |
|-------------|-------|
| 90-100 | A |
| 80-89 | B |
| 70-79 | C |
| 60-69 | D |
| <60 | F |

**Color Coding:**
- A (90-100): Green
- B (80-89): Light Green
- C (70-79): Yellow
- D (60-69): Orange
- F (<60): Red

---

## 5. Current Settings & Weights

### LLM Configuration

**File:** `src/config/settings.py`, `src/infra/llm/qwen_client.py`

```python
# Model Settings
model_name: str = "qwen3.5-flash"
embedding_model: str = "text-embedding-v4"

# Generation Parameters
temperature: float = 0.7
max_tokens: int = 2048

# Retry Configuration
max_retries: int = 3
retry_delay: float = 1.0  # Exponential backoff: 1s, 2s, 4s

# API Configuration
dashscope_api_key: str = ""
qwen_base_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
```

### Retrieval Configuration

**File:** `src/rag/runtime.py:28-36`

```python
@dataclass
class RetrievalDiversityConfig:
    overfetch_multiplier: int = 4           # Retrieve 4x candidates
    max_chunks_per_source_page: int = 2    # Max 2 per page
    max_chunks_per_source: int = 3         # Max 3 per document
    mmr_lambda: float = 0.75               # 75% relevance
    enable_diversification: bool = True
    search_mode: str = "rrf_hybrid"        # Default mode
```

### Vector Store Configuration

**File:** `src/ingestion/indexing/vector_store.py`

```python
# Search Weights
semantic_weight: float = 0.6    # 60% semantic
keyword_weight: float = 0.2     # 20% keyword
boost_weight: float = 0.2       # 20% source boost

# RRF Constant
k: int = 60                     # Rank fusion constant
```

### BM25 Configuration

**File:** `src/ingestion/indexing/keyword_index.py`

```python
k1: float = 1.5     # Term frequency saturation
b: float = 0.75     # Length normalization
```

### Chunking Configuration

**File:** `src/ingestion/steps/chunk_text.py:11-30`

See Section 1.3 for full chunk configuration table.

### Quality Thresholds

**File:** Evaluation configuration

```python
# Pipeline Quality Thresholds
EMPTY_PAGE_RATE_THRESHOLD = 0.20      # 20%
MARKDOWN_EMPTY_RATE_THRESHOLD = 0.10  # 10%
DUPLICATE_CHUNK_RATE_THRESHOLD = 0.05  # 5%

# Retrieval Quality Thresholds
HIT_RATE_THRESHOLD = 0.70              # 70%
MRR_THRESHOLD = 0.40                   # 0.40
EXACT_CHUNK_HIT_THRESHOLD = 0.40       # 40%
EVIDENCE_HIT_THRESHOLD = 0.50          # 50%
```

---

## 6. Critical Files Reference

### Core Retrieval Logic

**File:** `src/rag/runtime.py`

| Function | Lines | Description |
|----------|-------|-------------|
| `retrieve_context()` | 245-263 | Main retrieval endpoint |
| `_expand_queries()` | 60-82 | Query expansion logic |
| `_diversify_results()` | 176-242 | MMR diversification |
| `_mmr_rerank()` | 149-173 | MMR scoring algorithm |
| `initialize_runtime_index()` | 122-123 | Index initialization |

### Chunking Configuration

**File:** `src/ingestion/steps/chunk_text.py`

| Section | Lines | Description |
|---------|-------|-------------|
| `DEFAULT_SOURCE_CHUNK_CONFIGS` | 11-30 | Chunk size/overlap configs |
| `_find_recursive_split()` | 344-381 | Boundary detection logic |
| `_quality_score_for_block()` | 158-172 | Quality scoring |
| `_filter_low_quality_chunks()` | 310-335 | Quality filtering |
| `chunk_documents()` | 383-473 | Main chunking entry point |

### Search and Ranking

**File:** `src/ingestion/indexing/search.py`

| Function | Lines | Description |
|----------|-------|-------------|
| `source_prior_for()` | 15-22 | Source boosting weights |
| `cosine_similarity()` | 8-12 | Semantic similarity calc |
| `rank_documents()` | 25-68 | Weighted combination |
| `reciprocal_rank_fusion()` | 71-102 | RRF algorithm |

### Vector Store

**File:** `src/ingestion/indexing/vector_store.py`

- `__init__()`: Weight initialization
- `similarity_search()`: Hybrid search execution
- `add_documents()`: Index building with deduplication

### Chat Integration

**File:** `src/usecases/chat.py`

- Main chat endpoint with RAG integration
- History management
- Pipeline tracing support
- Source attribution

---

## 7. Evaluation & Monitoring

### Evaluation Dashboard

**Route:** `/eval`

**Features:**
1. **Real-time Metrics Display**
   - Health score with grade (A-F)
   - Hit Rate, MRR, NDCG
   - Latency percentiles

2. **Historical Trending Charts**
   - Hit Rate over time
   - MRR progression
   - Latency trends (p50/p95)
   - Pipeline health evolution

3. **Pipeline Step Visualization**
   - L0-L5 status indicators
   - Color-coded health per stage
   - Drill-down capabilities

4. **Run Comparison Tools**
   - Before/after analysis
   - Ablation study results
   - Parameter sweep visualization

5. **Export Functionality**
   - CSV exports for spreadsheet analysis
   - JSON exports for programmatic access
   - Chart exports for presentations

### API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /evaluation/latest` | Latest evaluation summary |
| `GET /evaluation/runs` | List all evaluation runs |
| `GET /evaluation/history` | Historical trending data |
| `GET /evaluation/steps/{stage}` | Stage-specific metrics |
| `GET /evaluation/ablation` | Retrieval strategy comparison |

### CLI Evaluation Tool

**Command:**
```bash
uv run python -m src.cli.eval_pipeline
```

**Capabilities:**
- Dataset selection and generation
- Retrieval strategy tuning
- Threshold customization
- Ablation studies
- Diversity sweeps
- Historical comparison

### Evaluation Dataset

**Golden Queries:**
- Medical domain-specific test questions
- Multiple query categories: anchor, adversarial, synthetic
- Difficulty levels: easy, medium, hard
- Label confidence tiers: low, medium, high
- Expected sources and keywords for precise evaluation
- Negative queries for adversarial testing

**Metrics Calculated:**
- Per-query retrieval performance
- Aggregate metrics across query sets
- Confidence-stratified analysis
- Source coverage tracking

---

## 8. System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     DATA SOURCES                                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                      │
│  │   HTML   │  │   PDF    │  │   CSV    │                      │
│  │ (Health  │  │ (Guides) │  │ (Lab     │                      │
│  │  Sites)  │  │          │  │  Ranges) │                      │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘                      │
└───────┼────────────┼─────────────┼─────────────────────────────┘
        │            │              │
        ▼            ▼              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  L0-L4: INGESTION                               │
│  Download → HTML→MD → PDF Extract → Reference Data Load        │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                  L3: CHUNKING                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Source-Aware Splitting (PDF: 650, MD: 600 chars)      │   │
│  │  Recursive Strategy with Overlap (80 chars)            │   │
│  │  Quality Scoring & Deduplication                       │   │
│  └─────────────────────────────────────────────────────────┘   │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                  L5: EMBEDDING & INDEXING                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Qwen Embedding Model (2048 dims)                       │   │
│  │  Vector + Keyword (BM25) + Source Prior Storage         │   │
│  └─────────────────────────────────────────────────────────┘   │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                  L6: RETRIEVAL                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Query Expansion (Original + Tokenized + Acronyms)     │   │
│  │  ↓                                                       │   │
│  │  Hybrid Search (60% Semantic + 20% BM25 + 20% Prior)   │   │
│  │  ↓                                                       │   │
│  │  Reciprocal Rank Fusion (RRF)                           │   │
│  │  ↓                                                       │   │
│  │  MMR Diversification (75% relevance, 25% diversity)    │   │
│  │  ↓                                                       │   │
│  │  Source Limits (max 2/page, 3/doc)                     │   │
│  └─────────────────────────────────────────────────────────┘   │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                  GENERATION                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Context Building (Retrieved Chunks + Sources)         │   │
│  │  ↓                                                       │   │
│  │  LLM Generation (Qwen 3.5 Flash)                        │   │
│  │  ↓                                                       │   │
│  │  Response Formatting with Source Attribution            │   │
│  └─────────────────────────────────────────────────────────┘   │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                  EVALUATION & MONITORING                        │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Quality Metrics (Hit Rate, MRR, NDCG, Latency)        │   │
│  │  Health Scoring (A-F Grade)                            │   │
│  │  Historical Trending Dashboard                         │   │
│  │  Pipeline Trace Visualization                          │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 9. Performance Characteristics

### Typical Retrieval Flow

1. **Query Processing:** ~5-10ms
   - Tokenization
   - Acronym expansion
   - Multi-query generation

2. **Vector Search:** ~50-100ms
   - Query embedding generation
   - Cosine similarity calculation
   - BM25 keyword scoring

3. **Ranking & Fusion:** ~10-20ms
   - RRF combination
   - Source prior application
   - Result merging

4. **Diversification:** ~20-50ms
   - MMR reranking
   - Source limit enforcement
   - Deduplication

5. **Total Retrieval Latency:** ~100-200ms (p95)

### Generation Performance

- **Model:** Qwen 3.5 Flash
- **Typical Response Time:** 500-1500ms
- **Max Tokens:** 2048
- **Temperature:** 0.7 (balanced creativity)

### Scaling Considerations

- **Vector Store:** JSON-based (suitable for <100K chunks)
- **Deduplication:** SHA256 hashing prevents redundant storage
- **Batch Processing:** Embeddings batched (10 texts/call)
- **Caching:** Persistent vector store avoids re-embedding

---

## 10. Recommendations & Future Improvements

### Current Strengths

1. **Robust Hybrid Search:** Combines semantic and keyword matching effectively
2. **Source-Aware Processing:** Different chunking for PDF vs HTML
3. **Advanced Diversification:** MMR prevents redundant results
4. **Comprehensive Monitoring:** 6-stage pipeline quality tracking
5. **Query Expansion:** Acronym handling improves medical queries

### Potential Enhancements

1. **Vector Database:** Consider migrating to specialized vector DB (e.g., Qdrant, Weaviate) for better scaling
2. **Cross-Encoder Reranking:** Add reranking stage for improved precision
3. **Query Classification:** Route different query types to optimized retrieval strategies
4. **Dynamic Thresholds:** Adjust MMR lambda and source limits based on query characteristics
5. **Embedding Fine-tuning:** Domain-specific embedding model for medical terminology
6. **Citations:** Include exact page/section references in responses
7. **Multi-turn Context:** Better conversation history integration

### Tuning Opportunities

1. **Chunk Size Optimization:** A/B test different chunk sizes for medical content
2. **Source Prior Adjustment:** Tune based on user feedback on source quality
3. **MMR Lambda:** Experiment with diversity vs relevance trade-offs
4. **Overfetch Multiplier:** Balance recall vs latency
5. **BM25 Parameters:** Optimize k1 and b for medical text

---

## Appendix: Configuration Quick Reference

### All Configuration Values

```python
# Embedding Model
embedding_model = "text-embedding-v4"
embedding_dimensions = 2048
embedding_batch_size = 10

# LLM
llm_model = "qwen3.5-flash"
temperature = 0.7
max_tokens = 2048
max_retries = 3
retry_delay = 1.0

# Chunking
pdf_chunk_size = 650
pdf_chunk_overlap = 80
pdf_min_chunk_size = 140
markdown_chunk_size = 600
markdown_chunk_overlap = 80
markdown_min_chunk_size = 80

# Search Weights
semantic_weight = 0.6
keyword_weight = 0.2
boost_weight = 0.2

# BM25
bm25_k1 = 1.5
bm25_b = 0.75

# RRF
rrf_k = 60

# Diversification
overfetch_multiplier = 4
max_chunks_per_source_page = 2
max_chunks_per_source = 3
mmr_lambda = 0.75

# Source Priors
guideline_pdf_prior = 0.15
reference_csv_prior = 0.12
guideline_html_prior = 0.10
index_page_prior = 0.02
default_prior = 0.05

# Quality Thresholds
hit_rate_threshold = 0.70
mrr_threshold = 0.40
exact_chunk_hit_threshold = 0.40
evidence_hit_threshold = 0.50
duplicate_chunk_rate_threshold = 0.05
empty_page_rate_threshold = 0.20
markdown_empty_rate_threshold = 0.10

# Health Score Weights
health_retrieval_weight = 0.40
health_data_quality_weight = 0.30
health_performance_weight = 0.20
health_completeness_weight = 0.10
```

---

## Document Metadata

- **Report Version:** 1.0
- **Generated:** 2026-03-06
- **Author:** System Analysis
- **System:** Medical Q&A RAG Pipeline
- **Purpose:** Comprehensive technical documentation

---

**End of Report**
