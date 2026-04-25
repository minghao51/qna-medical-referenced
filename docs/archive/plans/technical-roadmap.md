# QnA Medical Referenced - Technical Roadmap & Enhancement Proposal

**Document Version:** 1.0  
**Date:** 2026-03-23  
**Author:** Technical Analysis  
**Repository:** https://github.com/minghao51/qna-medical-referenced

---

## Executive Summary

This document provides a comprehensive analysis of the current state of the QnA Medical Referenced project and proposes a strategic roadmap for enhancement. The analysis identifies gaps in the current implementation across five key domains: Data Ingestion & Chunking, RAG Retrieval, Evaluation Pipeline, QnA Exploration, and System Operations. For each domain, we present phased recommendations with effort estimates, pros/cons analysis, and implementation options.

### Key Findings

The project has a solid foundation with:
- Well-structured FastAPI backend with clean separation of concerns
- Complete 7-stage ingestion pipeline (L0-L6)
- Hybrid retrieval with vector and keyword indexing
- Comprehensive evaluation framework with DeepEval integration
- Modern Svelte 5 frontend with transparency features

However, significant opportunities exist to enhance:
- **Chunking strategies** for medical domain specificity
- **Retrieval quality** through advanced reranking and query understanding
- **Continuous evaluation** and human feedback loops
- **User exploration** features for better QnA discovery
- **Production readiness** with monitoring and scalability

---

## Table of Contents

1. [Current Architecture Overview](#1-current-architecture-overview)
2. [Gap Analysis](#2-gap-analysis)
3. [Proposed Roadmap](#3-proposed-roadmap)
4. [Phase 1: Foundation Enhancements](#4-phase-1-foundation-enhancements)
5. [Phase 2: Advanced Retrieval](#5-phase-2-advanced-retrieval)
6. [Phase 3: Evaluation & Quality](#6-phase-3-evaluation--quality)
7. [Phase 4: User Experience & Exploration](#7-phase-4-user-experience--exploration)
8. [Phase 5: Production & Scale](#8-phase-5-production--scale)
9. [Implementation Priority Matrix](#9-implementation-priority-matrix)
10. [Resource Requirements](#10-resource-requirements)
11. [Risk Assessment](#11-risk-assessment)
12. [Appendix: Technical Specifications](#appendix-technical-specifications)

---

## 1. Current Architecture Overview

### 1.1 System Components

The current system consists of the following major components:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           QNA MEDICAL REFERENCED                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐         │
│  │    FRONTEND     │    │    BACKEND      │    │   EXTERNAL      │         │
│  │   (Svelte 5)    │◄──►│   (FastAPI)     │◄──►│   SERVICES      │         │
│  │                 │    │                 │    │                 │         │
│  │  • Chat UI      │    │  • /chat API    │    │  • Qwen LLM     │         │
│  │  • Eval Dashboard│   │  • /history API │    │  • DashScope    │         │
│  │  • Pipeline Viz │    │  • /eval API    │    │  • Embeddings   │         │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘         │
│                                    │                                        │
│                                    ▼                                        │
│                         ┌─────────────────┐                                │
│                         │  VECTOR STORE   │                                │
│                         │  (ChromaDB)     │                                │
│                         │                 │                                │
│                         │  • Hybrid Index │                                │
│                         │  • Embeddings   │                                │
│                         └─────────────────┘                                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Ingestion Pipeline Stages

| Stage | Name | Description | Output |
|-------|------|-------------|--------|
| L0 | Download | Web content & PDF downloads | Raw HTML/PDF files |
| L1 | Convert | HTML to Markdown conversion | Markdown files |
| L2 | PDF Load | PDF text extraction | Extracted text |
| L3 | Chunk | Document chunking | Text chunks |
| L4 | Reference | CSV reference data loading | Reference data |
| L5 | Index | Embedding & vector storage | Vector index |
| L6 | RAG | Runtime retrieval + generation | Answer + sources |

### 1.3 Current Evaluation Framework

The project includes a comprehensive evaluation framework:

- **Pipeline Quality Assessment**: L0-L6 stage quality checks
- **Retrieval Metrics**: HitRate@k, Recall@k, MRR, nDCG
- **Answer Quality**: DeepEval with LLM-as-judge for:
  - Factual Accuracy
  - Answer Relevancy
  - Completeness
  - Clinical Relevance
  - Faithfulness
  - Clarity

### 1.4 Already Planned Features

Based on existing documentation:

1. **Medical Intake Agent** (Approved)
   - Health parameter extraction from conversation
   - Proactive follow-up questions
   - User health profile with 30-day TTL
   - Query augmentation with patient context

2. **Frontend Enhancements** (Completed)
   - Confidence indicators
   - Interactive document inspection
   - Visual flow diagrams
   - Historical trending

---

## 2. Gap Analysis

### 2.1 Data Ingestion & Chunking

#### Current State

The current chunking implementation uses basic text splitting with fixed-size chunks. This approach has several limitations for medical content:

- **Loss of semantic boundaries**: Medical documents often contain tables, lists, and structured data that lose meaning when arbitrarily split
- **Context fragmentation**: Related information may be split across chunks
- **No domain awareness**: Medical terminology and concepts are not considered during chunking

#### Identified Gaps

| Gap | Description | Impact | Priority |
|-----|-------------|--------|----------|
| Semantic Chunking | No boundary-aware splitting | Medium-High chunks lose coherence | High |
| Multi-modal Content | No image/table extraction | Loss of visual medical data | Medium |
| Metadata Preservation | Limited chunk metadata | Reduced retrieval precision | Medium |
| Incremental Updates | Full re-indexing required | Slow iteration cycles | High |
| Duplicate Detection | No deduplication | Index bloat, redundant results | Medium |
| Content Freshness | No update monitoring | Stale medical information | Low |

#### Current Chunking Code Analysis

```python
# Current approach (simplified representation)
def chunk_text(text: str, chunk_size: int = 512, overlap: int = 50) -> list[str]:
    """Basic sliding window chunking."""
    chunks = []
    for i in range(0, len(text), chunk_size - overlap):
        chunks.append(text[i:i + chunk_size])
    return chunks
```

**Limitations:**
- Ignores paragraph boundaries
- Breaks medical tables mid-row
- No section header awareness
- Overlap creates redundancy without semantic value

### 2.2 RAG Retrieval

#### Current State

The system implements hybrid retrieval combining:
- Vector similarity search (Qwen embeddings)
- Keyword/TF-IDF matching
- MMR (Maximal Marginal Relevance) for diversity

#### Identified Gaps

| Gap | Description | Impact | Priority |
|-----|-------------|--------|----------|
| Query Understanding | No query classification/intent detection | Generic retrieval for all queries | High |
| Query Expansion | No synonym/medical term expansion | Miss relevant documents | High |
| Multi-Query Retrieval | Single query approach | Limited recall | Medium |
| Advanced Reranking | Basic MMR only | Sub-optimal ranking | High |
| Query Decomposition | No complex query handling | Poor multi-part question handling | Medium |
| Cross-Encoder Scoring | No cross-encoder reranking | Less precise relevance | Medium |
| Negative Filtering | No explicit exclusion | Irrelevant results in complex queries | Low |

#### Retrieval Flow Analysis

```
Current Flow:
Query → Embedding → Hybrid Search → MMR → Top-K → Generation

Missing Components:
Query → [Query Understanding] → [Query Expansion] → Embedding → 
       [Multi-Query Generation] → Hybrid Search → [Cross-Encoder Rerank] → 
       [Negative Filter] → Top-K → Generation
```

### 2.3 Evaluation Pipeline

#### Current State

- Offline evaluation with artifact storage
- DeepEval integration for answer quality
- Historical tracking via evaluation dashboard
- L0-L6 stage quality metrics

#### Identified Gaps

| Gap | Description | Impact | Priority |
|-----|-------------|--------|----------|
| Online Evaluation | No production monitoring | Undetected quality degradation | High |
| A/B Testing | No experiment framework | Cannot compare strategies | High |
| Human Feedback | No RLHF/correction loop | No quality improvement signal | High |
| Medical Benchmarks | No domain-specific tests | Generic evaluation only | Medium |
| Regression Testing | No automated regression | Changes may degrade quality | Medium |
| Cost Tracking | No token/cost monitoring | Uncontrolled expenses | Medium |
| Latency Monitoring | No performance tracking | Poor user experience | Medium |

### 2.4 QnA Exploration

#### Current State

- Basic chat interface with single query/response
- Source display with snippet
- Pipeline trace visualization

#### Identified Gaps

| Gap | Description | Impact | Priority |
|-----|-------------|--------|----------|
| Query Suggestions | No proactive suggestions | Users don't know what to ask | Medium |
| Related Questions | No "people also ask" | Limited exploration | Medium |
| Conversation Memory | Basic session history only | Repetitive interactions | Medium |
| Follow-up Generation | Manual follow-ups only | Poor conversation flow | Medium |
| Topic Navigation | No topic browsing | Difficult to explore domain | Low |
| Search History | No personalization | Repeated queries | Low |
| Answer Comparison | No version comparison | Cannot compare approaches | Low |

### 2.5 System Operations

#### Current State

- Local development focused
- JSON file-based chat history
- SQLite rate limiting
- Manual pipeline execution

#### Identified Gaps

| Gap | Description | Impact | Priority |
|-----|-------------|--------|----------|
| Observability | No metrics/tracing | Difficult debugging | High |
| Async Processing | Synchronous pipeline | Slow ingestion | Medium |
| Caching | No response caching | Repeated LLM calls | Medium |
| Scalability | Single-instance design | Cannot handle load | Low |
| CI/CD Pipeline | Manual deployment | Slow iteration | Medium |
| Data Versioning | No dataset versioning | Reproducibility issues | Medium |
| Configuration Management | Basic env vars | Complex deployments | Low |

---

## 3. Proposed Roadmap

### 3.1 Roadmap Overview

```
Timeline: 12-18 Months (Phased Approach)

Phase 1: Foundation Enhancements (Months 1-3)
├── 1.1 Semantic Chunking Implementation
├── 1.2 Query Understanding Module
├── 1.3 Online Evaluation Framework
└── 1.4 Observability Infrastructure

Phase 2: Advanced Retrieval (Months 3-6)
├── 2.1 Query Expansion System
├── 2.2 Cross-Encoder Reranking
├── 2.3 Multi-Query Retrieval
└── 2.4 Medical Intake Agent (Existing Plan)

Phase 3: Evaluation & Quality (Months 6-9)
├── 3.1 A/B Testing Framework
├── 3.2 Human Feedback Loop
├── 3.3 Medical Benchmark Suite
└── 3.4 Continuous Regression Testing

Phase 4: User Experience (Months 9-12)
├── 4.1 Query Suggestion Engine
├── 4.2 Related Questions System
├── 4.3 Conversation Intelligence
└── 4.4 Topic Navigation

Phase 5: Production & Scale (Months 12-18)
├── 5.1 Async Pipeline Processing
├── 5.2 Caching Layer
├── 5.3 Horizontal Scaling
└── 5.4 CI/CD & Data Versioning
```

### 3.2 Dependency Graph

```
                    ┌─────────────────────────────────────┐
                    │        PHASE 1: FOUNDATION          │
                    │  Semantic Chunking + Query          │
                    │  Understanding + Online Eval        │
                    └──────────────┬──────────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
              ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   PHASE 2A:     │  │   PHASE 2B:     │  │   PHASE 3:      │
│   Retrieval     │  │   Intake Agent  │  │   Evaluation    │
│   Enhancement   │  │   (Existing)    │  │   & Quality     │
└────────┬────────┘  └────────┬────────┘  └────────┬────────┘
         │                    │                    │
         └────────────────────┼────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │   PHASE 4:      │
                    │   User Exp      │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │   PHASE 5:      │
                    │   Production    │
                    └─────────────────┘
```

---

## 4. Phase 1: Foundation Enhancements

### 4.1 Semantic Chunking Implementation

#### Overview

Replace fixed-size chunking with semantic-aware chunking that respects document structure, medical context, and content boundaries.

#### Options Analysis

| Option | Description | Effort | Pros | Cons |
|--------|-------------|--------|------|------|
| **A: LangChain Semantic Chunker** | Use LangChain's built-in semantic splitter | Low (2-3 days) | Quick implementation, well-tested | Generic, not medical-optimized |
| **B: Custom Medical Chunker** | Build domain-specific chunker with medical NLP | Medium (1-2 weeks) | Optimal for medical content, handles tables/lists | Higher development cost |
| **C: LlamaIndex Node Parser** | Use LlamaIndex's hierarchical parser | Low (2-3 days) | Good structure awareness | Dependency on LlamaIndex ecosystem |
| **D: Hybrid Approach** | Combine semantic boundaries with size limits | Medium (1 week) | Balance of quality and efficiency | More complex logic |

#### Recommended Approach: Option D (Hybrid)

```python
class MedicalSemanticChunker:
    """
    Hybrid chunker combining:
    1. Section boundary detection
    2. Paragraph-aware splitting
    3. Table preservation
    4. Size limits with semantic overlap
    """
    
    def __init__(
        self,
        target_size: int = 512,
        max_size: int = 1024,
        min_size: int = 100,
        overlap_sentences: int = 2
    ):
        self.target_size = target_size
        self.max_size = max_size
        self.min_size = min_size
        self.overlap_sentences = overlap_sentences
    
    def chunk(self, document: Document) -> list[Chunk]:
        # 1. Parse document structure
        sections = self._detect_sections(document)
        
        # 2. Extract tables as atomic units
        tables = self._extract_tables(document)
        
        # 3. Chunk text sections with semantic boundaries
        chunks = []
        for section in sections:
            if self._is_small_section(section):
                chunks.append(self._create_chunk(section))
            else:
                chunks.extend(self._chunk_large_section(section))
        
        # 4. Add table chunks
        chunks.extend([self._table_to_chunk(t) for t in tables])
        
        return chunks
```

#### Implementation Details

**New Files:**
```
src/ingestion/chunking/
├── __init__.py
├── semantic_chunker.py      # Main chunker implementation
├── section_detector.py      # Section boundary detection
├── table_extractor.py       # Table extraction & preservation
├── medical_ner.py          # Medical entity recognition for boundaries
└── chunk_models.py         # Chunk data models
```

**Configuration:**
```python
# src/config/settings.py additions
CHUNK_TARGET_SIZE: int = 512
CHUNK_MAX_SIZE: int = 1024
CHUNK_MIN_SIZE: int = 100
CHUNK_OVERLAP_SENTENCES: int = 2
CHUNK_PRESERVE_TABLES: bool = True
CHUNK_SECTION_AWARE: bool = True
```

#### Effort Estimate

| Task | Duration | Dependencies |
|------|----------|--------------|
| Core chunker implementation | 3 days | None |
| Section detection | 2 days | spaCy/NLTK |
| Table extraction | 2 days | camelot/tabula |
| Integration & testing | 2 days | Existing pipeline |
| Documentation | 1 day | All above |
| **Total** | **10 days** | |

#### Success Metrics

- Chunk coherence score (semantic similarity within chunks) > 0.85
- Table preservation rate = 100%
- Average chunk size within target range (100-1024 tokens)
- Retrieval quality improvement (nDCG@5) > 5%

### 4.2 Query Understanding Module

#### Overview

Implement query classification and intent detection to enable query-specific retrieval strategies.

#### Options Analysis

| Option | Description | Effort | Pros | Cons |
|--------|-------------|--------|------|------|
| **A: Rule-Based Classifier** | Regex + keyword matching | Low (2 days) | Simple, fast, no LLM cost | Limited accuracy |
| **B: LLM Classification** | Use Qwen for intent detection | Medium (4 days) | High accuracy, flexible | Per-query cost |
| **C: Fine-tuned Classifier** | Train small classifier model | High (2 weeks) | No per-query cost, fast | Requires training data |
| **D: Hybrid (Rules + LLM)** | Rules for obvious cases, LLM for ambiguous | Medium (5 days) | Cost-efficient, accurate | More complex |

#### Recommended Approach: Option D (Hybrid)

```python
class QueryUnderstandingPipeline:
    """
    Multi-stage query understanding:
    1. Fast rule-based classification
    2. LLM fallback for ambiguous queries
    3. Entity extraction for medical terms
    """
    
    QUERY_TYPES = [
        "definition",      # "What is hypertension?"
        "comparison",      # "Difference between Type 1 and Type 2 diabetes"
        "reference_range", # "Normal blood pressure range"
        "symptom_query",   # "Symptoms of anemia"
        "treatment",       # "Treatment for high cholesterol"
        "risk_factor",     # "Risk factors for heart disease"
        "follow_up",       # Context-dependent follow-up
        "complex"          # Multi-part or ambiguous
    ]
    
    def __init__(self, llm_client, use_cache: bool = True):
        self.rule_classifier = RuleBasedClassifier()
        self.llm_classifier = LLMClassifier(llm_client)
        self.entity_extractor = MedicalEntityExtractor()
        self.cache = QueryCache() if use_cache else None
    
    async def understand(self, query: str, context: dict = None) -> QueryUnderstanding:
        # Check cache
        if self.cache:
            cached = self.cache.get(query)
            if cached:
                return cached
        
        # Stage 1: Rule-based classification
        rule_result = self.rule_classifier.classify(query)
        if rule_result.confidence > 0.9:
            return self._build_result(query, rule_result, context)
        
        # Stage 2: LLM classification for ambiguous queries
        llm_result = await self.llm_classifier.classify(query, context)
        
        # Stage 3: Entity extraction
        entities = self.entity_extractor.extract(query)
        
        result = self._build_result(query, llm_result, context, entities)
        
        if self.cache:
            self.cache.set(query, result)
        
        return result
```

#### Query Type Routing

Different query types should use different retrieval strategies:

| Query Type | Retrieval Strategy | Example |
|------------|-------------------|---------|
| Definition | High similarity, single source | "What is hypertension?" |
| Comparison | Multi-document, structured comparison | "Type 1 vs Type 2 diabetes" |
| Reference Range | Table-focused retrieval | "Normal BP range" |
| Symptom Query | List extraction, multiple sources | "Symptoms of anemia" |
| Treatment | Procedure-focused, authoritative sources | "Treatment for high cholesterol" |
| Risk Factor | List extraction, structured data | "Risk factors for heart disease" |
| Follow-up | Context-aware, conversation history | "What about exercise?" |
| Complex | Multi-query decomposition | "Compare treatments for diabetes considering cost and side effects" |

#### Implementation Details

**New Files:**
```
src/rag/query_understanding/
├── __init__.py
├── pipeline.py              # Main query understanding pipeline
├── rule_classifier.py       # Rule-based classification
├── llm_classifier.py        # LLM-based classification
├── entity_extractor.py      # Medical entity extraction
├── query_types.py           # Query type definitions
├── routing.py               # Query type to retrieval routing
└── cache.py                 # Query result caching
```

#### Effort Estimate

| Task | Duration | Dependencies |
|------|----------|--------------|
| Rule-based classifier | 1 day | None |
| LLM classifier | 2 days | Qwen client |
| Entity extraction | 2 days | spaCy/scispaCy |
| Routing logic | 1 day | Retrieval system |
| Integration | 1 day | All above |
| Testing | 1 day | All above |
| **Total** | **8 days** | |

#### Success Metrics

- Classification accuracy > 90% on test set
- Rule-based coverage > 60% of queries
- Average latency < 100ms for rule-based, < 500ms for LLM
- Retrieval improvement per query type > 3%

### 4.3 Online Evaluation Framework

#### Overview

Implement continuous evaluation in production to monitor quality degradation and trigger alerts.

#### Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        ONLINE EVALUATION FRAMEWORK                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │   SAMPLER   │───►│  EVALUATOR  │───►│   ALERTER   │───►│  DASHBOARD  │  │
│  │             │    │             │    │             │    │             │  │
│  │ • 1% sample │    │ • Async     │    │ • Threshold │    │ • Grafana   │  │
│  │ • Golden Qs │    │ • DeepEval  │    │ • Trend     │    │ • Alerts    │  │
│  │ • Random    │    │ • Metrics   │    │ • Anomaly   │    │ • History   │  │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘  │
│         ▲                  ▲                                                │
│         │                  │                                                │
│  ┌──────┴───────┐   ┌──────┴───────┐                                       │
│  │  PRODUCTION  │   │    METRICS   │                                       │
│  │   TRAFFIC    │   │    STORE     │                                       │
│  │              │   │              │                                       │
│  │ /chat API    │   │ • Prometheus │                                       │
│  └──────────────┘   │ • TimescaleDB│                                       │
│                     └──────────────┘                                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### Evaluation Strategies

| Strategy | Description | Frequency | Cost |
|----------|-------------|-----------|------|
| **Sampling** | Evaluate 1-5% of production queries | Continuous | Low |
| **Golden Set** | Periodic evaluation of fixed test set | Hourly/Daily | Controlled |
| **Shadow Mode** | Compare new vs current retrieval | Continuous | Medium |
| **A/B Testing** | Controlled experiment comparison | Per-experiment | Variable |

#### Implementation Details

**New Files:**
```
src/evals/online/
├── __init__.py
├── sampler.py              # Query sampling strategies
├── evaluator.py            # Async evaluation executor
├── alerter.py              # Threshold-based alerting
├── metrics_store.py        # Time-series metrics storage
├── golden_set.py           # Golden test set management
├── shadow_mode.py          # Shadow evaluation mode
└── dashboard_api.py        # Evaluation metrics API
```

**Configuration:**
```python
# src/config/settings.py additions
ONLINE_EVAL_ENABLED: bool = True
ONLINE_EVAL_SAMPLE_RATE: float = 0.01  # 1% sampling
ONLINE_EVAL_GOLDEN_SET_PATH: str = "data/evals/golden_set.json"
ONLINE_EVAL_GOLDEN_SET_INTERVAL: int = 3600  # hourly
ONLINE_EVAL_ALERT_THRESHOLDS: dict = {
    "ndcg@5": 0.7,
    "answer_relevance": 0.8,
    "factual_accuracy": 0.85,
    "latency_p95": 3000  # ms
}
```

#### Effort Estimate

| Task | Duration | Dependencies |
|------|----------|--------------|
| Sampler implementation | 2 days | None |
| Async evaluator | 3 days | DeepEval |
| Metrics storage | 2 days | Prometheus/TimescaleDB |
| Alerting system | 2 days | Threshold config |
| Dashboard integration | 2 days | Grafana/frontend |
| Testing | 2 days | All above |
| **Total** | **13 days** | |

#### Success Metrics

- 99.9% uptime for evaluation pipeline
- Alert latency < 5 minutes
- No production traffic impact
- Cost increase < 5% of LLM spend

### 4.4 Observability Infrastructure

#### Overview

Implement comprehensive observability with logging, metrics, and tracing.

#### Components

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Logging** | Structured JSON logs | Debug & audit |
| **Metrics** | Prometheus + Grafana | Performance monitoring |
| **Tracing** | OpenTelemetry | Request flow analysis |
| **Error Tracking** | Sentry | Exception monitoring |

#### Implementation Details

**New Files:**
```
src/infra/observability/
├── __init__.py
├── logging.py              # Structured logging config
├── metrics.py              # Prometheus metrics definitions
├── tracing.py              # OpenTelemetry tracing
├── error_tracking.py       # Sentry integration
└── middleware.py           # FastAPI observability middleware
```

**Key Metrics:**
```python
# Request metrics
REQUEST_COUNT = Counter('chat_requests_total', ['endpoint', 'status'])
REQUEST_LATENCY = Histogram('chat_request_latency_seconds', ['endpoint'])
ACTIVE_REQUESTS = Gauge('chat_active_requests')

# RAG metrics
RETRIEVAL_LATENCY = Histogram('rag_retrieval_latency_seconds')
RETRIEVAL_DOCUMENTS = Histogram('rag_documents_retrieved')
CONTEXT_LENGTH = Histogram('rag_context_tokens')

# LLM metrics
LLM_REQUESTS = Counter('llm_requests_total', ['model', 'status'])
LLM_TOKENS = Counter('llm_tokens_total', ['model', 'type'])  # type: input/output
LLM_LATENCY = Histogram('llm_latency_seconds', ['model'])

# Evaluation metrics
EVAL_SCORES = Gauge('eval_score', ['metric', 'query_type'])
```

#### Effort Estimate

| Task | Duration | Dependencies |
|------|----------|--------------|
| Structured logging | 1 day | None |
| Prometheus integration | 2 days | prometheus-client |
| OpenTelemetry setup | 2 days | opentelemetry-* |
| Sentry integration | 1 day | sentry-sdk |
| Grafana dashboards | 2 days | Grafana |
| **Total** | **8 days** | |

---

## 5. Phase 2: Advanced Retrieval

### 5.1 Query Expansion System

#### Overview

Expand user queries with synonyms, medical terminology, and related concepts to improve recall.

#### Options Analysis

| Option | Description | Effort | Pros | Cons |
|--------|-------------|--------|------|------|
| **A: LLM Expansion** | Use LLM to generate expansions | Low (3 days) | Context-aware, flexible | Per-query cost |
| **B: UMLS/MESH Integration** | Use medical ontologies | Medium (1 week) | Authoritative, precise | Requires UMLS license |
| **C: Embedding-based Expansion** | Find similar terms in vector space | Medium (4 days) | No external dependencies | May drift from meaning |
| **D: Hybrid** | Combine LLM + ontology | Medium-High (2 weeks) | Best coverage | Complexity |

#### Recommended Approach: Option D (Hybrid) with Fallback

```python
class QueryExpander:
    """
    Multi-source query expansion:
    1. Medical ontology (UMLS/MESH) for precise terms
    2. LLM expansion for context-aware synonyms
    3. Embedding-based for fallback
    """
    
    def __init__(self, llm_client, ontology_client=None):
        self.llm_expander = LLMExpander(llm_client)
        self.ontology_expander = OntologyExpander(ontology_client)
        self.embedding_expander = EmbeddingExpander()
        
    async def expand(self, query: str, max_expansions: int = 3) -> list[str]:
        expansions = set()
        
        # 1. Try medical ontology first (free, precise)
        ontology_terms = await self.ontology_expander.expand(query)
        expansions.update(ontology_terms[:max_expansions])
        
        # 2. Use LLM for context-aware expansion
        if len(expansions) < max_expansions:
            llm_terms = await self.llm_expander.expand(query, max_expansions - len(expansions))
            expansions.update(llm_terms)
        
        # 3. Fallback to embedding-based
        if len(expansions) < max_expansions:
            embed_terms = await self.embedding_expander.expand(query, max_expansions - len(expansions))
            expansions.update(embed_terms)
        
        return list(expansions)[:max_expansions]
```

#### Effort Estimate

| Task | Duration | Dependencies |
|------|----------|--------------|
| LLM expander | 2 days | Qwen client |
| Ontology integration | 3 days | UMLS API |
| Embedding expander | 2 days | Existing embeddings |
| Hybrid orchestration | 2 days | All above |
| Testing | 2 days | All above |
| **Total** | **11 days** | |

### 5.2 Cross-Encoder Reranking

#### Overview

Use cross-encoder models to rerank retrieved documents for higher precision.

#### Options Analysis

| Option | Description | Effort | Pros | Cons |
|--------|-------------|--------|------|------|
| **A: Local Cross-Encoder** | Run model locally | Medium (3 days) | No API cost, low latency | GPU required |
| **B: API-based Reranking** | Use Cohere/Jina rerank API | Low (2 days) | Easy integration | Per-query cost |
| **C: LLM Reranking** | Use Qwen for scoring | Medium (3 days) | Uses existing infrastructure | Higher cost |
| **D: Hybrid Reranking** | Combine multiple rerankers | High (1 week) | Best quality | Complexity |

#### Recommended Approach: Option A (Local Cross-Encoder)

```python
class CrossEncoderReranker:
    """
    Local cross-encoder reranking using sentence-transformers.
    Uses medical-domain fine-tuned model if available.
    """
    
    def __init__(self, model_name: str = "medical-cross-encoder"):
        self.model = CrossEncoder(model_name)
        
    def rerank(
        self, 
        query: str, 
        documents: list[Document], 
        top_k: int = 5
    ) -> list[ScoredDocument]:
        # Prepare query-document pairs
        pairs = [(query, doc.content) for doc in documents]
        
        # Score with cross-encoder
        scores = self.model.predict(pairs)
        
        # Sort and return top-k
        scored_docs = [
            ScoredDocument(document=doc, score=score)
            for doc, score in zip(documents, scores)
        ]
        scored_docs.sort(key=lambda x: x.score, reverse=True)
        
        return scored_docs[:top_k]
```

#### Effort Estimate

| Task | Duration | Dependencies |
|------|----------|--------------|
| Cross-encoder setup | 1 day | sentence-transformers |
| Integration with retrieval | 2 days | Existing retrieval |
| Performance optimization | 2 days | Batch processing |
| Testing | 1 day | All above |
| **Total** | **6 days** | |

### 5.3 Multi-Query Retrieval

#### Overview

Generate multiple query variations to improve recall for complex queries.

#### Implementation

```python
class MultiQueryRetriever:
    """
    Generate multiple query variations and aggregate results.
    """
    
    def __init__(self, llm_client, base_retriever):
        self.llm_client = llm_client
        self.base_retriever = base_retriever
        
    async def retrieve(
        self, 
        query: str, 
        num_variations: int = 3,
        top_k_per_query: int = 5
    ) -> list[Document]:
        # 1. Generate query variations
        variations = await self._generate_variations(query, num_variations)
        
        # 2. Retrieve for each variation
        all_results = []
        for variation in [query] + variations:
            results = await self.base_retriever.retrieve(variation, top_k_per_query)
            all_results.extend(results)
        
        # 3. Deduplicate and merge
        merged = self._merge_results(all_results)
        
        return merged
    
    async def _generate_variations(self, query: str, n: int) -> list[str]:
        prompt = f"""Generate {n} different ways to ask the following question. 
        Each variation should use different wording but seek the same information.
        
        Question: {query}
        
        Variations (one per line):"""
        
        response = await self.llm_client.generate(prompt)
        variations = [v.strip() for v in response.strip().split('\n') if v.strip()]
        return variations[:n]
```

#### Effort Estimate

| Task | Duration | Dependencies |
|------|----------|--------------|
| Query variation generation | 2 days | LLM client |
| Result aggregation | 2 days | Existing retrieval |
| Integration | 1 day | All above |
| Testing | 1 day | All above |
| **Total** | **6 days** | |

---

## 6. Phase 3: Evaluation & Quality

### 6.1 A/B Testing Framework

#### Overview

Implement a robust A/B testing framework for comparing retrieval strategies, models, and prompts.

#### Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           A/B TESTING FRAMEWORK                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │  EXPERIMENT │    │  ASSIGNMENT │    │   VARIANT   │    │   ANALYSIS  │  │
│  │   CONFIG    │───►│   SERVICE   │───►│   RUNNER    │───►│   ENGINE    │  │
│  │             │    │             │    │             │    │             │  │
│  │ • YAML/JSON │    │ • Hash-based│    │ • Parallel  │    │ • Stats     │  │
│  │ • Variants  │    │ • Sticky    │    │ • Shadow    │    │ • Signif.   │  │
│  │ • Metrics   │    │ • Consistent│    │ • Live      │    │ • Reports   │  │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### Implementation Details

**New Files:**
```
src/evals/ab_testing/
├── __init__.py
├── experiment_config.py    # Experiment configuration models
├── assignment.py           # User-to-variant assignment
├── variant_runner.py       # Variant execution
├── analysis.py             # Statistical analysis
├── reporting.py            # Report generation
└── cli.py                  # A/B test management CLI
```

**Experiment Configuration:**
```yaml
# experiments/retrieval_comparison.yaml
name: retrieval_comparison
description: Compare semantic vs hybrid retrieval
start_date: 2026-04-01
end_date: 2026-04-30
traffic_allocation: 0.1  # 10% of traffic

variants:
  - name: control
    description: Current hybrid retrieval
    weight: 0.5
    config:
      retrieval_type: hybrid
      reranker: none
      
  - name: treatment
    description: Hybrid + cross-encoder reranking
    weight: 0.5
    config:
      retrieval_type: hybrid
      reranker: cross_encoder

metrics:
  primary:
    - ndcg@5
    - answer_relevance
  secondary:
    - latency_p95
    - user_satisfaction

success_criteria:
  ndcg@5:
    min_improvement: 0.05
    confidence: 0.95
  answer_relevance:
    min_improvement: 0.03
    confidence: 0.90
```

#### Effort Estimate

| Task | Duration | Dependencies |
|------|----------|--------------|
| Experiment configuration | 2 days | None |
| Assignment service | 2 days | Hash function |
| Variant runner | 3 days | Retrieval system |
| Analysis engine | 3 days | scipy/statsmodels |
| Reporting | 2 days | All above |
| CLI | 1 day | All above |
| **Total** | **13 days** | |

### 6.2 Human Feedback Loop

#### Overview

Implement a human-in-the-loop feedback system for continuous quality improvement.

#### Components

| Component | Description |
|-----------|-------------|
| **Feedback Collection** | UI for users to rate/flag answers |
| **Annotation Interface** | Admin interface for expert review |
| **Feedback Storage** | Persistent storage of feedback data |
| **RLHF Integration** | Use feedback for model improvement |
| **Correction Pipeline** | Automated corrections for common issues |

#### Implementation Details

**New Files:**
```
src/feedback/
├── __init__.py
├── collection.py           # Feedback collection service
├── storage.py              # Feedback storage
├── annotation.py           # Annotation interface API
├── rlhf.py                 # RLHF integration
├── correction.py           # Correction pipeline
└── analysis.py             # Feedback analysis

src/app/routes/
└── feedback.py             # Feedback API endpoints

frontend/src/lib/components/
├── FeedbackButtons.svelte  # Thumb up/down buttons
├── FeedbackForm.svelte     # Detailed feedback form
└── AnnotationInterface.svelte  # Expert annotation UI
```

**API Endpoints:**
```python
# Feedback API
POST /feedback/submit       # Submit user feedback
GET  /feedback/pending      # Get pending annotations (admin)
POST /feedback/annotate     # Submit expert annotation
GET  /feedback/stats        # Feedback statistics
```

#### Effort Estimate

| Task | Duration | Dependencies |
|------|----------|--------------|
| Feedback collection UI | 2 days | Frontend |
| Feedback API | 2 days | FastAPI |
| Storage implementation | 1 day | Database |
| Annotation interface | 3 days | Frontend + API |
| Analysis & reporting | 2 days | All above |
| **Total** | **10 days** | |

### 6.3 Medical Benchmark Suite

#### Overview

Create a domain-specific evaluation benchmark for medical Q&A quality.

#### Benchmark Components

| Component | Description | Size |
|-----------|-------------|------|
| **Medical Factuality** | Verify medical claims against authoritative sources | 500 queries |
| **Reference Range Accuracy** | Test correct retrieval of lab value ranges | 200 queries |
| **Drug Interaction** | Drug-drug interaction queries | 150 queries |
| **Clinical Decision Support** | Complex clinical scenarios | 100 queries |
| **Patient Communication** | Appropriate patient-facing language | 150 queries |

#### Implementation Details

**New Files:**
```
src/evals/benchmarks/
├── __init__.py
├── medical_benchmark.py    # Main benchmark runner
├── factuality.py           # Medical factuality tests
├── reference_ranges.py     # Lab value accuracy tests
├── drug_interactions.py    # Drug interaction tests
├── clinical_scenarios.py   # Clinical decision tests
├── patient_comm.py         # Patient communication tests
└── data/
    ├── factuality.jsonl
    ├── reference_ranges.jsonl
    ├── drug_interactions.jsonl
    └── clinical_scenarios.jsonl
```

#### Effort Estimate

| Task | Duration | Dependencies |
|------|----------|--------------|
| Benchmark design | 3 days | Medical experts |
| Data curation | 5 days | Medical experts |
| Implementation | 3 days | DeepEval |
| Validation | 2 days | Medical experts |
| **Total** | **13 days** | |

---

## 7. Phase 4: User Experience & Exploration

### 7.1 Query Suggestion Engine

#### Overview

Provide proactive query suggestions to help users explore medical topics.

#### Implementation

```python
class QuerySuggestionEngine:
    """
    Generate relevant query suggestions based on:
    1. Current conversation context
    2. Popular queries in the corpus
    3. Related medical topics
    """
    
    def __init__(self, llm_client, corpus_stats):
        self.llm_client = llm_client
        self.corpus_stats = corpus_stats
        
    async def get_suggestions(
        self, 
        context: ConversationContext,
        current_query: str = None,
        max_suggestions: int = 5
    ) -> list[QuerySuggestion]:
        suggestions = []
        
        # 1. Context-based suggestions
        if context.has_medical_topic():
            context_suggestions = await self._suggest_follow_ups(context)
            suggestions.extend(context_suggestions)
        
        # 2. Popular queries in similar domain
        popular = self._get_popular_queries(context.topic, max=2)
        suggestions.extend(popular)
        
        # 3. Related topics
        related = await self._get_related_topics(context.topic)
        suggestions.extend(related)
        
        # Deduplicate and rank
        return self._rank_and_dedupe(suggestions)[:max_suggestions]
```

#### Effort Estimate

| Task | Duration | Dependencies |
|------|----------|--------------|
| Suggestion generation | 3 days | LLM client |
| Context extraction | 2 days | Chat history |
| Popular query mining | 2 days | Usage data |
| Frontend integration | 2 days | Frontend |
| Testing | 1 day | All above |
| **Total** | **10 days** | |

### 7.2 Related Questions System

#### Overview

Show "People also ask" style related questions after each answer.

#### Implementation

```python
class RelatedQuestionsGenerator:
    """
    Generate related questions based on retrieved documents.
    """
    
    async def generate(
        self, 
        query: str, 
        retrieved_docs: list[Document],
        max_questions: int = 3
    ) -> list[str]:
        # Extract key concepts from retrieved docs
        concepts = self._extract_concepts(retrieved_docs)
        
        # Generate questions about related concepts
        prompt = f"""Based on the original question and related medical concepts, 
        generate {max_questions} related follow-up questions.
        
        Original question: {query}
        Related concepts: {', '.join(concepts)}
        
        Related questions:"""
        
        response = await self.llm_client.generate(prompt)
        questions = [q.strip() for q in response.split('\n') if q.strip()]
        
        return questions[:max_questions]
```

#### Effort Estimate

| Task | Duration | Dependencies |
|------|----------|--------------|
| Question generation | 2 days | LLM client |
| Concept extraction | 1 day | spaCy |
| Frontend display | 2 days | Frontend |
| Testing | 1 day | All above |
| **Total** | **6 days** | |

### 7.3 Conversation Intelligence

#### Overview

Enhance conversation with summarization, topic tracking, and intelligent follow-ups.

#### Features

| Feature | Description |
|---------|-------------|
| **Conversation Summary** | Auto-generate summary of long conversations |
| **Topic Tracking** | Track topics discussed across conversation |
| **Follow-up Detection** | Detect when user is asking follow-up |
| **Context Window Management** | Smart context pruning for long conversations |

#### Effort Estimate

| Task | Duration | Dependencies |
|------|----------|--------------|
| Summarization | 2 days | LLM client |
| Topic tracking | 2 days | NLP |
| Follow-up detection | 2 days | LLM client |
| Context management | 2 days | All above |
| **Total** | **8 days** | |

---

## 8. Phase 5: Production & Scale

### 8.1 Async Pipeline Processing

#### Overview

Convert synchronous pipeline to async with background job processing.

#### Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        ASYNC PIPELINE ARCHITECTURE                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │   TRIGGER   │───►│    QUEUE    │───►│   WORKER    │───►│   STORAGE   │  │
│  │             │    │             │    │             │    │             │  │
│  │ • Webhook   │    │ • Redis     │    │ • Celery    │    │ • Results   │  │
│  │ • Schedule  │    │ • SQS       │    │ • AsyncIO   │    │ • Status    │  │
│  │ • Manual    │    │ • RabbitMQ  │    │ • Parallel  │    │ • Logs      │  │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### Options Analysis

| Option | Description | Effort | Pros | Cons |
|--------|-------------|--------|------|------|
| **A: Celery + Redis** | Classic task queue | Medium (1 week) | Mature, proven | Redis dependency |
| **B: AsyncIO + asyncio.Queue** | Pure Python async | Low (3 days) | No extra dependencies | No persistence |
| **C: Dramatiq + Redis** | Modern task queue | Medium (5 days) | Simpler than Celery | Less mature |
| **D: AWS SQS + Lambda** | Cloud-native | High (2 weeks) | Scalable, managed | AWS lock-in |

#### Recommended Approach: Option A (Celery + Redis)

**Effort Estimate:** 8 days

### 8.2 Caching Layer

#### Overview

Implement multi-level caching to reduce LLM costs and latency.

#### Cache Levels

| Level | Description | TTL | Storage |
|-------|-------------|-----|---------|
| **L1: Response Cache** | Exact query match | 1 hour | Redis |
| **L2: Embedding Cache** | Query embeddings | 24 hours | Redis |
| **L3: Retrieval Cache** | Retrieved documents | 6 hours | Redis |
| **L4: LLM Response Cache** | Generated responses | 1 hour | Redis |

#### Effort Estimate

| Task | Duration | Dependencies |
|------|----------|--------------|
| Redis setup | 1 day | Redis |
| Cache key design | 1 day | None |
| Cache invalidation | 2 days | None |
| Integration | 2 days | All above |
| **Total** | **6 days** | |

### 8.3 Horizontal Scaling

#### Overview

Design for horizontal scalability with load balancing and distributed processing.

#### Components

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Load Balancer** | nginx/HAProxy | Request distribution |
| **Application Servers** | Gunicorn + Uvicorn | Request handling |
| **Vector DB** | Qdrant/Milvus | Distributed vector search |
| **Cache** | Redis Cluster | Distributed caching |
| **Queue** | Redis/RabbitMQ | Job distribution |

#### Effort Estimate

| Task | Duration | Dependencies |
|------|----------|--------------|
| Container configuration | 2 days | Docker |
| Load balancer setup | 1 day | nginx |
| Vector DB migration | 3 days | Qdrant/Milvus |
| Redis cluster | 2 days | Redis |
| Documentation | 1 day | All above |
| **Total** | **9 days** | |

---

## 9. Implementation Priority Matrix

### 9.1 Priority Scoring

Each feature is scored on:
- **Impact** (1-5): User benefit and system improvement
- **Effort** (1-5): Implementation complexity
- **Risk** (1-5): Technical and operational risk
- **Dependencies** (1-5): External dependencies required

**Priority Score = Impact × 2 - Effort - Risk - Dependencies**

### 9.2 Priority Ranking

| Rank | Feature | Phase | Impact | Effort | Risk | Deps | Score |
|------|---------|-------|--------|--------|------|------|-------|
| 1 | Semantic Chunking | 1 | 5 | 3 | 2 | 2 | 3 |
| 2 | Query Understanding | 1 | 5 | 3 | 2 | 2 | 3 |
| 3 | Online Evaluation | 1 | 4 | 3 | 2 | 2 | 1 |
| 4 | Cross-Encoder Reranking | 2 | 4 | 2 | 2 | 2 | 2 |
| 5 | Human Feedback Loop | 3 | 5 | 3 | 2 | 3 | 2 |
| 6 | A/B Testing Framework | 3 | 4 | 3 | 2 | 2 | 0 |
| 7 | Query Expansion | 2 | 4 | 3 | 2 | 2 | 1 |
| 8 | Query Suggestions | 4 | 4 | 3 | 2 | 2 | 1 |
| 9 | Multi-Query Retrieval | 2 | 3 | 2 | 2 | 2 | 0 |
| 10 | Caching Layer | 5 | 3 | 2 | 2 | 2 | 0 |
| 11 | Medical Benchmark | 3 | 4 | 4 | 2 | 4 | -2 |
| 12 | Async Pipeline | 5 | 3 | 3 | 3 | 3 | -3 |
| 13 | Related Questions | 4 | 3 | 2 | 2 | 2 | 0 |
| 14 | Conversation Intelligence | 4 | 3 | 2 | 2 | 2 | 0 |
| 15 | Horizontal Scaling | 5 | 3 | 4 | 3 | 4 | -5 |

### 9.3 Recommended Implementation Order

**Quick Wins (Week 1-4):**
1. Semantic Chunking
2. Cross-Encoder Reranking
3. Query Understanding

**Medium Term (Month 2-4):**
4. Online Evaluation
5. Human Feedback Loop
6. Query Expansion
7. A/B Testing Framework

**Long Term (Month 5+):**
8. Query Suggestions
9. Multi-Query Retrieval
10. Medical Benchmark
11. Caching Layer
12. Conversation Intelligence
13. Related Questions
14. Async Pipeline
15. Horizontal Scaling

---

## 10. Resource Requirements

### 10.1 Team Requirements

| Role | Phase 1-2 | Phase 3-4 | Phase 5 |
|------|-----------|-----------|---------|
| Backend Engineer | 1-2 | 1-2 | 1-2 |
| ML/NLP Engineer | 1 | 0.5 | 0.5 |
| Frontend Engineer | 0.5 | 1 | 0.5 |
| DevOps Engineer | 0.5 | 0.5 | 1 |
| Medical SME | 0.5 | 1 | 0.5 |

### 10.2 Infrastructure Requirements

| Resource | Current | Phase 1-2 | Phase 3-4 | Phase 5 |
|----------|---------|-----------|-----------|---------|
| Compute | 1 CPU | 2-4 CPU | 4-8 CPU | 8+ CPU |
| Memory | 4 GB | 8-16 GB | 16-32 GB | 32+ GB |
| GPU | None | 1 GPU (optional) | 1 GPU | 1-2 GPU |
| Storage | 50 GB | 100 GB | 200 GB | 500+ GB |
| Vector DB | Local ChromaDB | Local ChromaDB | Managed/Clustered | Distributed |

### 10.3 External Services

| Service | Purpose | Monthly Cost Estimate |
|---------|---------|----------------------|
| DashScope/Qwen API | LLM + Embeddings | $50-500 (usage-based) |
| Redis Cloud | Caching/Queue | $0-100 |
| Prometheus/Grafana | Monitoring | $0-50 |
| Sentry | Error tracking | $0-50 |

---

## 11. Risk Assessment

### 11.1 Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| LLM API changes | Medium | High | Abstract LLM interface, multi-provider support |
| Embedding model drift | Low | Medium | Version pinning, periodic re-indexing |
| Vector DB scaling issues | Medium | High | Plan migration path to distributed DB |
| Performance degradation | Medium | Medium | Load testing, monitoring, caching |
| Data quality issues | High | High | Validation pipelines, human review |

### 11.2 Operational Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Cost overruns | Medium | Medium | Usage monitoring, budgets, caching |
| Team availability | Medium | High | Documentation, knowledge transfer |
| Medical accuracy | High | Critical | Expert review, disclaimers, evaluation |
| Regulatory compliance | Low | Critical | Legal review, HIPAA awareness |

### 11.3 Mitigation Strategies

**Medical Accuracy:**
- Implement mandatory disclaimers
- Human expert review for high-stakes queries
- Source citation for all claims
- Regular accuracy audits

**Cost Control:**
- Implement caching at all levels
- Use smaller models where possible
- Monitor and alert on usage spikes
- Optimize prompt lengths

**Scalability:**
- Design for horizontal scaling from the start
- Use managed services where cost-effective
- Implement circuit breakers and rate limiting

---

## Appendix: Technical Specifications

### A. Semantic Chunking Specifications

```python
@dataclass
class ChunkConfig:
    """Configuration for semantic chunking."""
    target_size: int = 512  # Target chunk size in tokens
    max_size: int = 1024    # Maximum chunk size
    min_size: int = 100     # Minimum chunk size
    overlap_sentences: int = 2  # Sentence overlap between chunks
    preserve_tables: bool = True  # Keep tables as atomic chunks
    section_aware: bool = True  # Respect section boundaries
    entity_aware: bool = True   # Consider medical entities
    
@dataclass
class Chunk:
    """Represents a single chunk with metadata."""
    id: str
    content: str
    source_document: str
    source_section: str | None
    chunk_index: int
    start_char: int
    end_char: int
    token_count: int
    entities: list[MedicalEntity]
    metadata: dict[str, Any]
```

### B. Query Understanding Specifications

```python
class QueryType(Enum):
    """Supported query types."""
    DEFINITION = "definition"
    COMPARISON = "comparison"
    REFERENCE_RANGE = "reference_range"
    SYMPTOM_QUERY = "symptom_query"
    TREATMENT = "treatment"
    RISK_FACTOR = "risk_factor"
    FOLLOW_UP = "follow_up"
    COMPLEX = "complex"

@dataclass
class QueryUnderstanding:
    """Result of query understanding."""
    original_query: str
    query_type: QueryType
    confidence: float
    entities: list[MedicalEntity]
    intent: str
    sub_queries: list[str] | None  # For complex queries
    suggested_retrieval_strategy: RetrievalStrategy
```

### C. Evaluation Metrics Specifications

```python
@dataclass
class EvaluationMetrics:
    """Comprehensive evaluation metrics."""
    # Retrieval metrics
    hit_rate_at_k: dict[int, float]  # k -> score
    recall_at_k: dict[int, float]
    mrr: float  # Mean Reciprocal Rank
    ndcg_at_k: dict[int, float]
    
    # Generation metrics
    answer_relevance: float
    factual_accuracy: float
    completeness: float
    clinical_relevance: float
    faithfulness: float
    clarity: float
    
    # Performance metrics
    latency_p50: float  # milliseconds
    latency_p95: float
    latency_p99: float
    tokens_input: int
    tokens_output: int
    
    # Cost metrics
    llm_cost: float
    embedding_cost: float
    total_cost: float
```

### D. API Specifications

```yaml
# OpenAPI specification additions
paths:
  /feedback/submit:
    post:
      summary: Submit user feedback
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                session_id:
                  type: string
                message_id:
                  type: string
                rating:
                  type: integer
                  minimum: 1
                  maximum: 5
                feedback_type:
                  type: string
                  enum: [helpful, not_helpful, inaccurate, needs_improvement]
                comment:
                  type: string
                  maxLength: 500
              required: [session_id, message_id, rating]
      responses:
        200:
          description: Feedback recorded

  /suggestions:
    get:
      summary: Get query suggestions
      parameters:
        - name: context
          in: query
          schema:
            type: string
        - name: limit
          in: query
          schema:
            type: integer
            default: 5
      responses:
        200:
          description: List of suggestions
          content:
            application/json:
              schema:
                type: object
                properties:
                  suggestions:
                    type: array
                    items:
                      type: object
                      properties:
                        text:
                          type: string
                        relevance_score:
                          type: number
```

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-03-23 | Technical Analysis | Initial roadmap document |

---

*This document is intended as a strategic guide and should be reviewed and updated quarterly as the project evolves and new requirements emerge.*
