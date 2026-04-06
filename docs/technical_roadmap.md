# Technical Roadmap: QNA Medical Referenced Project

**Strategic Expansion & Enhancement Plan**

Repository: github.com/minghao51/qna-medical-referenced  
Document Date: April 2026

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current State Analysis](#2-current-state-analysis)
   - 2.1 [Architecture Overview](#21-architecture-overview)
   - 2.2 [Current Feature Inventory](#22-current-feature-inventory)
   - 2.3 [Identified Gaps and Technical Debt](#23-identified-gaps-and-technical-debt)
3. [Phase 1: Foundation Strengthening (Months 1-4)](#3-phase-1-foundation-strengthening-months-1-4)
   - 3.1 [Cross-Encoder Reranking Implementation](#31-cross-encoder-reranking-implementation)
   - 3.2 [HyPE Ablation Experiments](#32-hype-ablation-experiments)
   - 3.3 [Chunking Strategy Optimization](#33-chunking-strategy-optimization)
4. [Phase 2: Advanced AI Capabilities (Months 5-9)](#4-phase-2-advanced-ai-capabilities-months-5-9)
   - 4.1 [Self-Reflection and Answer Verification](#41-self-reflection-and-answer-verification)
   - 4.2 [Multi-Agent Query Decomposition](#42-multi-agent-query-decomposition)
   - 4.3 [Adaptive Retrieval Strategies](#43-adaptive-retrieval-strategies)
5. [Phase 3: Medical Domain Enhancement (Months 10-14)](#5-phase-3-medical-domain-enhancement-months-10-14)
   - 5.1 [Medical Coding Integration (ICD-10, SNOMED-CT)](#51-medical-coding-integration-icd-10-snomed-ct)
   - 5.2 [Clinical Guidelines Integration](#52-clinical-guidelines-integration)
   - 5.3 [Medical Image Understanding](#53-medical-image-understanding)
6. [Phase 4: Enterprise & Scale (Months 15-18)](#6-phase-4-enterprise--scale-months-15-18)
   - 6.1 [Healthcare Compliance Framework](#61-healthcare-compliance-framework)
   - 6.2 [Medical Knowledge Graph](#62-medical-knowledge-graph)
   - 6.3 [Federated Deployment & API Gateway](#63-federated-deployment--api-gateway)
7. [Implementation Priorities & Success Metrics](#7-implementation-priorities--success-metrics)
8. [Risk Assessment & Mitigation](#8-risk-assessment--mitigation)
9. [Resource Requirements](#9-resource-requirements)
10. [Conclusion](#10-conclusion)

---

## 1. Executive Summary

This technical roadmap outlines a comprehensive strategy for expanding and enhancing the QNA Medical Referenced project, a sophisticated medical question-answering system built on Retrieval-Augmented Generation (RAG) architecture. The system currently demonstrates strong foundational capabilities with its multi-stage ingestion pipeline, hybrid retrieval mechanisms, and quality evaluation framework. However, significant opportunities exist to elevate the platform from a capable prototype to a production-grade medical AI assistant that can serve healthcare professionals and patients with reliable, evidence-based information.

The roadmap is organized into four strategic phases spanning approximately 18 months, each targeting specific capability enhancements. Phase 1 addresses critical quality improvements and infrastructure hardening, establishing the foundation for reliable operation. Phase 2 introduces advanced AI capabilities including multi-agent reasoning and self-reflection mechanisms. Phase 3 focuses on domain-specific medical enhancements, including clinical guideline integration and medical image understanding. Phase 4 delivers enterprise-scale features including compliance frameworks, knowledge graph integration, and federated deployment capabilities.

Key strategic priorities include implementing cross-encoder reranking for improved retrieval precision, developing HyPE ablation experiments to quantify index-time query expansion benefits, integrating medical coding standards (ICD-10, SNOMED-CT), and building a comprehensive clinical decision support layer. The roadmap balances technical innovation with practical considerations around healthcare compliance, cost optimization, and system reliability.

---

## 2. Current State Analysis

### 2.1 Architecture Overview

The project employs a well-structured three-tier architecture separating concerns across ingestion, retrieval, and serving layers. The backend is built on FastAPI with Python, providing RESTful endpoints for chat interactions, session management, and evaluation workflows. The frontend utilizes SvelteKit 2.50.2 with TypeScript, offering a responsive chat interface and evaluation dashboard. The system leverages Alibaba's Qwen models for text generation and embeddings, with ChromaDB serving as the vector database for semantic search capabilities.

The ingestion pipeline follows a six-stage Directed Acyclic Graph (DAG) architecture:

| Stage | Module | Description |
|-------|--------|-------------|
| L0 | `src/ingestion/steps/download_web.py` | Downloads HTML sources |
| L1 | `src/ingestion/steps/convert_html.py` | HTML → Markdown conversion |
| L1 | `src/ingestion/steps/load_pdfs.py` | PDF text + table extraction |
| L2 | `src/ingestion/steps/load_pdfs.py` | Classifies blocks into types |
| L3 | `src/ingestion/steps/chunk_text.py` | Text chunking with quality scoring |
| L3 | `src/ingestion/steps/hype.py` | HyPE question generation |
| L4 | `src/ingestion/steps/load_reference_data.py` | Lab reference ranges |
| L5 | `src/ingestion/indexing/vector_store.py` | Hybrid vector + BM25 index |

This modular design supports configurable strategies at each stage, including multiple PDF extractors (pypdf, PyMuPDF), chunking algorithms (recursive, semantic, late), and search modes (RRF hybrid, semantic-only, BM25-only).

### 2.2 Current Feature Inventory

**Core RAG Capabilities:**

- Hybrid retrieval combining dense embeddings (Qwen text-embedding-v4) with sparse BM25 indexing
- HyDE (Hypothetical Document Embeddings) for query-time expansion with LLM-generated hypothetical answers
- HyPE (Hypothetical Prompt Embeddings) for index-time question generation with zero query-time cost
- MMR diversification with configurable lambda parameter for result variety
- Multi-turn conversation support with cookie-backed session persistence
- Medical acronym expansion (LDL → Low-Density Lipoprotein)

**Evaluation Framework:**

- Stage-specific quality checks (L0-L5) with automated metrics collection
- Ranked IR metrics: HitRate@k, Recall@k, MRR, nDCG for retrieval evaluation
- DeepEval integration for LLM-as-a-judge answer quality assessment
- Golden conversations dataset (15 conversations across 4 categories) for benchmarking
- Historical trending with versioned artifact persistence

**Frontend Features:**

- Chat interface with pipeline toggle for debugging
- Confidence indicators with color-coded badges (high/medium/low)
- Document inspector modal with metadata visualization
- Pipeline flow diagrams showing retrieval stages
- Markdown rendering with syntax highlighting (highlight.js)

### 2.3 Identified Gaps and Technical Debt

The project documentation identifies several critical gaps that this roadmap addresses. The HyPE ablation experiments remain unimplemented, preventing quantification of index-time query expansion benefits. Strategy interaction effects between PDF extractors and chunking strategies remain unexplored, potentially leading to suboptimal default configurations. The Late Chunker implementation exists but is not included in experimental configurations. Cross-encoder reranking, a technique known to improve top-k precision significantly, is not implemented.

Additionally, several operational concerns require attention: HyDE LLM cost tracking is absent, making it difficult to optimize the cost-quality tradeoff; query variation benchmarks are incomplete, leaving optimization targets unclear; and the acronym expansion system relies on predefined medical terms, potentially missing domain-specific vocabulary. These gaps represent both immediate quality improvement opportunities and longer-term architectural considerations for production deployment.

---

## 3. Phase 1: Foundation Strengthening (Months 1-4)

Phase 1 focuses on addressing critical technical debt and implementing quality improvements that directly impact retrieval precision and answer reliability. These enhancements establish the foundation for more advanced capabilities in subsequent phases while delivering immediate value to users through improved response quality.

### 3.1 Cross-Encoder Reranking Implementation

Cross-encoder reranking represents the highest-impact improvement for retrieval quality. While the current bi-encoder approach efficiently retrieves candidate documents using vector similarity, cross-encoders jointly encode the query-document pair for more precise relevance scoring. Research indicates cross-encoder reranking can improve HitRate@k by 15-30% on medical QA benchmarks. The implementation should integrate a medical-domain cross-encoder model (e.g., BioLinkBERT-based) as a post-retrieval step, reranking the top-k candidates from the hybrid retriever.

**Implementation Details:**

1. Create new module `src/rag/reranker.py` with `CrossEncoderReranker` class
2. Integrate with `retrieve_context_with_trace()` as optional post-processing step
3. Add `RERANKER_MODEL` config option (default: `BAAI/bge-reranker-base`)
4. Implement batched inference for efficiency (process 8-16 pairs per batch)
5. Add reranking metrics to evaluation pipeline (`rerank_improvement_delta`)
6. Update `RetrievalDiversityConfig` with `enable_reranking` and `rerank_top_k` options

### 3.2 HyPE Ablation Experiments

HyPE (Hypothetical Prompt Embeddings) generates potential questions at index time, enabling query expansion without LLM calls during inference. However, the impact on retrieval quality remains unquantified. A systematic ablation study will determine optimal HyPE configuration parameters including sample rate, questions per chunk, and quality thresholds. The experiment design should test configurations ranging from disabled HyPE to full coverage, measuring the tradeoff between index size, ingestion time, and retrieval improvement.

**Experiment Configurations:**

| Variant | Description | Configuration |
|---------|-------------|---------------|
| `hype_disabled` | Baseline without HyPE | `enable_hype=false` |
| `hype_10pct` | Default configuration with 10% chunk coverage | `enable_hype=true, hype_sample_rate=0.1` |
| `hype_50pct` | Expanded coverage for quality comparison | `enable_hype=true, hype_sample_rate=0.5` |
| `hype_100pct` | Maximum coverage for upper bound measurement | `enable_hype=true, hype_sample_rate=1.0` |
| `hype_hyde_combined` | Both HyPE and HyDE enabled for interaction analysis | `enable_hype=true, enable_hyde=true` |

### 3.3 Chunking Strategy Optimization

The current system supports multiple chunking strategies but lacks systematic comparison of their effectiveness for medical documents. Medical text presents unique challenges: clinical notes may have critical information in short fragments, while research papers require preservation of section context. This initiative will benchmark chunking strategies against medical-specific quality metrics and establish evidence-based defaults for different document types.

Key experiments include testing `chonkie_semantic` against `custom_recursive` on medical corpora, measuring semantic boundary preservation through manual annotation on a sample dataset, and optimizing overlap parameters for medical terminology continuity. Results will inform a document-type-aware chunking strategy that automatically selects appropriate parameters based on source classification.

---

## 4. Phase 2: Advanced AI Capabilities (Months 5-9)

Phase 2 introduces sophisticated AI capabilities that transform the system from a retrieval-based QA tool to an intelligent medical assistant capable of reasoning, self-correction, and complex query handling. These features leverage advances in agentic AI and chain-of-thought reasoning to deliver more accurate and comprehensive medical responses.

### 4.1 Self-Reflection and Answer Verification

Self-reflection mechanisms enable the system to critique its own responses before presenting them to users. In the medical domain, this capability is particularly valuable for catching potential hallucinations, verifying factual claims against retrieved evidence, and ensuring response coherence. The implementation should add a verification layer that re-examines generated answers against source documents, flags unsupported claims, and triggers regeneration when confidence falls below thresholds.

**Verification Pipeline:**

1. Extract factual claims from generated response using structured prompting
2. Cross-reference each claim with retrieved source documents
3. Assign confidence scores to each claim based on evidence strength
4. Regenerate problematic passages when claim confidence is low
5. Generate verification report with source citations for transparency

### 4.2 Multi-Agent Query Decomposition

Complex medical queries often span multiple topics or require synthesizing information from diverse sources. A multi-agent architecture can decompose complex queries into sub-queries, route each to specialized retrieval paths, and synthesize results into coherent responses. For example, a query about "diabetes treatment complications" might spawn sub-agents for medication side effects, lifestyle interventions, and long-term outcomes, each with optimized retrieval strategies.

The architecture should implement an orchestrator agent that analyzes query complexity, spawns specialized sub-agents when decomposition is beneficial, manages inter-agent communication, and synthesizes final responses. Specialized agents might include a drug-interaction agent, a clinical-guidelines agent, and a patient-education agent, each with tailored prompt templates and retrieval configurations.

### 4.3 Adaptive Retrieval Strategies

Different query types benefit from different retrieval strategies. Factoid questions ("What is normal blood pressure?") require precise single-document retrieval, while explanatory questions ("Why does diabetes cause kidney damage?") benefit from broader context gathering. An adaptive system will classify query intent and dynamically select optimal retrieval parameters including search mode (semantic vs. hybrid vs. BM25), top-k value, diversification settings, and expansion strategies.

Implementation involves training a lightweight query classifier on annotated medical queries, mapping query types to retrieval profiles, and implementing dynamic configuration adjustment in the runtime retrieval layer. The classifier should distinguish between factoid, explanatory, procedural, and comparative query types, with corresponding retrieval optimizations validated through A/B testing.

---

## 5. Phase 3: Medical Domain Enhancement (Months 10-14)

Phase 3 delivers domain-specific enhancements that establish the system as a specialized medical AI platform. These features integrate medical standards, enable clinical workflow support, and extend capabilities to multimodal medical content including images and structured health records.

### 5.1 Medical Coding Integration (ICD-10, SNOMED-CT)

Integration of standardized medical coding systems enables precise concept identification, improves retrieval through concept-based indexing, and facilitates interoperability with clinical systems. ICD-10 provides diagnosis classification for billing and epidemiology, while SNOMED-CT offers a comprehensive clinical terminology for precise concept representation. The system should automatically detect medical entities in queries and documents, map them to standard codes, and use these mappings to enhance retrieval relevance.

**Implementation Components:**

1. Integrate medical NER model (scispaCy or BioBERT-based) for entity extraction
2. Build ICD-10 and SNOMED-CT lookup indices for entity normalization
3. Augment document metadata with extracted medical codes during ingestion
4. Implement concept-based retrieval for queries containing medical entities
5. Add code visualization in frontend document inspector

### 5.2 Clinical Guidelines Integration

Clinical practice guidelines from authoritative sources (e.g., American Heart Association, American Diabetes Association) represent high-value medical knowledge that should be prioritized in retrieval and clearly attributed in responses. This initiative creates a curated guidelines collection with structured metadata, implements guideline-specific retrieval boosting, and generates responses that clearly reference guideline recommendations with evidence grades.

The implementation should establish a guidelines ingestion pipeline with metadata extraction (publishing organization, last updated date, evidence level), create a guidelines-specific collection in the vector store with boosted scoring, and develop prompt templates that enforce guideline citation when relevant. A guidelines freshness monitoring system should flag outdated references and prioritize recent updates.

### 5.3 Medical Image Understanding

Medical literature frequently contains diagnostic images, charts, and diagrams that convey critical information not captured in text extraction. Vision-language model integration enables understanding of medical images, extracting insights from figures, and incorporating visual information into responses. This capability is particularly valuable for dermatology references, radiology reports, and anatomical diagrams.

**Technical Approach:**

- Integrate vision-language model (e.g., Qwen-VL or MedCLIP) for image encoding
- Extract images during PDF ingestion with associated figure captions
- Create multimodal embeddings combining image and text representations
- Implement image-aware retrieval with cross-modal similarity scoring
- Display relevant images in frontend responses with proper attribution

---

## 6. Phase 4: Enterprise & Scale (Months 15-18)

Phase 4 delivers enterprise-grade features required for production deployment in healthcare settings. These capabilities address compliance requirements, enable large-scale deployment, and support integration with existing healthcare IT infrastructure.

### 6.1 Healthcare Compliance Framework

Healthcare applications must comply with regulatory requirements including HIPAA (US), GDPR (EU), and regional data protection laws. The compliance framework implements data encryption at rest and in transit, audit logging for all interactions, data retention policies with automatic cleanup, and user consent management. Additionally, the system should support on-premises deployment options for organizations with strict data residency requirements.

Key implementation tasks include implementing field-level encryption for sensitive data in chat history, building comprehensive audit trail with tamper-proof logging, creating data subject access request (DSAR) workflows for GDPR compliance, and developing deployment documentation for on-premises installation with Docker Compose and Kubernetes configurations.

### 6.2 Medical Knowledge Graph

A medical knowledge graph structures relationships between diseases, symptoms, medications, procedures, and anatomical structures. This structured knowledge complements the document-based retrieval system, enabling precise relationship queries (e.g., "What medications interact with this drug?"), supporting graph-based reasoning for diagnostic suggestions, and providing structured context for answer generation. The knowledge graph should integrate with existing coding systems (ICD-10, SNOMED-CT) and support continuous updates from new literature.

The implementation should select a graph database (Neo4j or Amazon Neptune) optimized for medical knowledge representation, build ETL pipelines to import structured medical ontologies, develop entity resolution algorithms to link graph entities with document concepts, and create hybrid retrieval combining vector search with graph traversal for complex medical queries.

### 6.3 Federated Deployment & API Gateway

Large healthcare organizations may require federated deployments with centralized management but distributed data processing. This capability enables organizations with multiple facilities to maintain local document repositories while sharing a common model and evaluation framework. The federated architecture includes a central coordination service, distributed ingestion workers, and synchronized evaluation metrics aggregation.

Additionally, a comprehensive API Gateway provides unified access for integration with electronic health records (EHR) systems, clinical decision support tools, and third-party applications. The gateway should implement rate limiting, authentication, request routing, and response caching while maintaining detailed usage analytics for capacity planning and cost allocation.

---

## 7. Implementation Priorities & Success Metrics

### 7.1 Priority Matrix

The following table summarizes priority rankings based on impact, effort, and dependencies:

| Initiative | Impact | Effort | Priority | Phase |
|------------|--------|--------|----------|-------|
| Cross-Encoder Reranking | High | Medium | P1 | Phase 1 |
| HyPE Ablation Experiments | High | Low | P1 | Phase 1 |
| Self-Reflection Layer | High | High | P2 | Phase 2 |
| Multi-Agent Decomposition | Medium | High | P3 | Phase 2 |
| ICD-10/SNOMED Integration | High | Medium | P2 | Phase 3 |
| Medical Image Understanding | Medium | High | P3 | Phase 3 |
| Knowledge Graph | High | Very High | P4 | Phase 4 |
| Compliance Framework | Critical | High | P4 | Phase 4 |

### 7.2 Success Metrics

**Phase 1 Metrics:**

- HitRate@5 improvement ≥ 15% from cross-encoder reranking
- HyPE ablation results documented with statistical significance
- Chunking strategy benchmark report with recommendation matrix

**Phase 2 Metrics:**

- Hallucination rate reduction ≥ 30% with self-reflection
- Complex query handling success rate ≥ 85%
- Query intent classification accuracy ≥ 90%

**Phase 3 Metrics:**

- Medical entity recognition F1 ≥ 0.92
- Guideline citation rate in relevant responses ≥ 80%
- Image retrieval relevance score ≥ 0.85

**Phase 4 Metrics:**

- Compliance audit pass rate = 100%
- Knowledge graph entity coverage ≥ 95% of SNOMED-CT core
- Federated deployment latency overhead < 50ms

---

## 8. Risk Assessment & Mitigation

| Risk Category | Severity | Mitigation Strategy |
|---------------|----------|---------------------|
| LLM API Cost Overrun | High | Implement cost monitoring, caching layers, and budget alerts |
| Medical Accuracy Issues | Critical | Domain expert review, citation requirements, disclaimer UI |
| Regulatory Non-Compliance | Critical | Early legal review, compliance-by-design architecture |
| Performance Degradation | Medium | Load testing, caching strategies, horizontal scaling |
| Model Dependency | Medium | Multi-provider strategy, model abstraction layer |

---

## 9. Resource Requirements

### 9.1 Team Composition

Successful execution requires a multidisciplinary team combining software engineering expertise with medical domain knowledge. The recommended team composition includes:

- **Technical Lead/Architect**: System design decisions and code review
- **2-3 Senior Backend Engineers**: Core RAG development and API implementation
- **1 Frontend Engineer**: UI enhancements and visualization
- **1 ML Engineer**: Model integration and evaluation pipelines
- **Medical Domain Expert**: Content validation and clinical guidance

Part-time support from DevOps/SRE and Security specialists is recommended for Phase 4 compliance and deployment features.

### 9.2 Infrastructure Requirements

**Development Environment:**

- GPU-enabled instances for embedding and reranking (NVIDIA T4 or equivalent)
- SSD storage for vector indices (minimum 100GB for development corpus)
- Container orchestration (Docker Compose for development, Kubernetes for staging)

**Production Environment:**

- Auto-scaling API servers (minimum 4 instances for high availability)
- Dedicated vector database cluster (ChromaDB or managed alternative)
- Redis cluster for caching and session management
- Load balancer with SSL termination and DDoS protection

---

## 10. Conclusion

This technical roadmap provides a structured approach to evolving the QNA Medical Referenced project from a capable RAG prototype to a production-grade medical AI assistant. The four-phase plan addresses immediate quality improvements while building toward sophisticated capabilities including multi-agent reasoning, medical coding integration, and enterprise compliance. Each phase delivers incremental value while establishing foundations for subsequent enhancements.

The prioritized implementation sequence ensures that high-impact, lower-effort initiatives (cross-encoder reranking, HyPE ablation) are completed early, generating measurable improvements that validate the investment in subsequent phases. Success metrics provide objective criteria for phase completion and readiness assessment. Risk mitigation strategies address the unique challenges of medical AI deployment, including regulatory compliance and accuracy requirements.

Execution of this roadmap will position the project as a leading open-source medical Q&A platform, capable of serving healthcare professionals and patients with reliable, evidence-based medical information. The modular architecture ensures that individual components can be adopted independently, allowing organizations to integrate specific capabilities into existing workflows while the comprehensive platform serves greenfield deployments.
