# Medical AI Co-Pilot Design

**Date:** 2026-04-16
**Status:** Approved
**Timeline:** 12 weeks (1-3 months)
**Purpose:** Portfolio showcase — multi-modal + agentic medical AI

---

## Overview

Medical AI Co-Pilot that accepts lab report images, extracts structured data via vision models, and uses a ReAct agent with specialized medical tools to provide grounded analysis with citations.

### Core Demo Flow

```
User uploads lab report photo
        |
        v
  +-------------+
  | Vision OCR  |  <- Qwen-VL extracts structured data
  | + Extraction|     (test names, values, units, flags)
  +------+------+
         |
         v
  +-------------+
  | Entity      |  <- Normalize to standard medical terms
  | Normalizer  |     (Hb -> Hemoglobin, CBC -> Complete Blood Count)
  +------+------+
         |
         v
  +-------------+
  | RAG + Agent |  <- Enriched query with extracted context
  | Loop        |     Calls tools: drug_interactions(), reference_ranges(),
  +------+------+             literature_search(), differential()
         |
         v
  +-------------+
  | Interactive |  <- Extracted values table, abnormal flags highlighted,
  | Response    |     follow-up suggestions, source citations
  +-------------+
```

### The "Wow" Moment

User takes a photo of lab results, gets interactive breakdown with abnormal values highlighted, potential conditions, medication interactions flagged, and can ask follow-up questions — all grounded in retrieved medical sources with citations.

---

## Architecture

### New Modules

```
src/
+-- multimodal/
|   +-- __init__.py
|   +-- upload.py           # File upload handling (image, PDF)
|   +-- vision_extractor.py # Vision model -> structured medical data
|   +-- entity_normalizer.py# Raw text -> standardized medical entities
|   +-- models.py           # Data models: LabResult, Medication, etc.
|
+-- agent/
|   +-- __init__.py
|   +-- loop.py             # ReAct agent loop (think -> act -> observe)
|   +-- tools/
|   |   +-- drug_interaction.py  # Check drug-drug interactions
|   |   +-- reference_range.py   # Look up normal ranges
|   |   +-- literature_search.py # Search medical literature
|   |   +-- differential.py      # Generate differential from symptoms/labs
|   +-- prompts.py          # System prompt, tool descriptions
|   +-- models.py           # Agent state, tool results
|
+-- services/
    +-- copilot.py          # Orchestrator: upload -> extract -> agent -> respond
```

### Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Vision model | Qwen-VL (DashScope) | Already in ecosystem, no new provider |
| Agent pattern | ReAct loop | Simple, debuggable, shows reasoning |
| Tool count | 4 specialized tools | Focused scope, each backed by existing RAG or structured data |
| Vector DB | Existing ChromaDB | No migration needed |
| Streaming | SSE for agent responses | Better UX for long agent reasoning |

### What We Reuse

- Existing embedding pipeline (Qwen embeddings)
- Cross-encoder reranker
- Medical query expansion
- Production profiles
- Evaluation framework (extended for co-pilot scenarios)
- ChromaDB vector store
- Reference data (CSV)

---

## Agent Tools

### 1. Reference Range Lookup

```python
# Input: lab test name + value + patient context
# Output: normal range, flag (normal/high/low/critical), interpretation
reference_range.lookup(test="Hemoglobin", value=10.2, unit="g/dL", age=45, sex="M")
# -> {"range": "13.5-17.5", "flag": "low", "severity": "moderate", "interpretation": "..."}
```

Backed by existing reference CSV data. No external API.

### 2. Drug Interaction Checker

```python
# Input: list of medications
# Output: interaction pairs with severity and mechanism
drug_interaction.check(medications=["Warfarin", "Aspirin", "Omeprazole"])
# -> [{"pair": ["Warfarin", "Aspirin"], "severity": "major", "mechanism": "..."}]
```

Backed by structured drug interaction database (local dataset or RAG retrieval).

### 3. Literature Search

```python
# Input: medical query
# Output: relevant literature snippets with citations
literature_search.search(query="hemoglobin low causes differential diagnosis")
# -> [{"title": "...", "snippet": "...", "source": "...", "relevance": 0.92}]
```

Uses existing RAG retrieval pipeline. Thin wrapper.

### 4. Differential Generator

```python
# Input: abnormal lab values + symptoms
# Output: ranked differential diagnoses with reasoning
differential.generate(abnormal_results=[...], symptoms=[...])
# -> [{"condition": "Iron deficiency anemia", "likelihood": "high", "reasoning": "..."}]
```

Uses LLM + RAG. Grounded in retrieved medical sources.

---

## Implementation Phases

### Phase A: Vision Pipeline (Week 1-2)

**Goal:** Upload a lab report photo, get structured JSON back.

- Image/PDF upload endpoint + temporary storage
- Qwen-VL integration for medical document OCR
- Prompt engineering for structured extraction
- Data models: `LabResult`, `Medication`, `Condition`, `VitalSign`
- Entity normalization against existing reference data
- Unit tests with sample lab reports

**Deliverable:** `POST /copilot/upload` returns structured extraction

### Phase B: Agent Framework (Week 3-4)

**Goal:** Agent can answer multi-step medical questions using tools.

- ReAct agent loop implementation (think -> act -> observe cycle)
- Tool calling interface with structured input/output schemas
- 4 medical tools implementation
- Agent prompts (system prompt, tool descriptions, output formatting)
- Conversation memory within session
- Unit tests per tool, integration test for agent loop

**Deliverable:** `POST /copilot/chat` with agent tool use working

### Phase C: Co-Pilot Integration (Week 5-6)

**Goal:** End-to-end flow working via API.

- `copilot.py` orchestrator: upload -> extract -> agent -> respond
- Enhanced chat endpoint with multimodal context injection
- Agent streaming responses (SSE)
- Error handling for incomplete/ambiguous extractions
- Fallback when vision extraction fails (ask user to clarify)
- Integration tests for full pipeline

**Deliverable:** Full end-to-end API flow

### Phase D: Frontend + Polish (Week 7-10)

**Goal:** Demo-ready portfolio piece.

- Upload UI component (drag-and-drop, camera capture on mobile)
- Interactive results table with abnormal value highlighting
- Agent thought process visualization (tool calls shown inline)
- Follow-up suggestion chips
- Source citations with document links
- Responsive design for mobile demo
- Loading states and error handling

**Deliverable:** Polished UI demo

### Phase E: Evaluation + Demo Prep (Week 11-12)

**Goal:** Bulletproof demo with documented results.

- Co-pilot evaluation benchmark
  - Vision extraction accuracy (field-level F1)
  - Agent tool correctness (tool selection accuracy)
  - End-to-end answer quality (medical accuracy)
- Demo scenarios with 5+ sample lab reports
- Performance optimization (cache vision results, cache tool results)
- Demo script / README
- Portfolio write-up with architecture diagrams

**Deliverable:** Demo-ready project with documentation

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Qwen-VL poor extraction on handwritten reports | Medium | Medium | Start with printed/typed reports, add handwriting later |
| Agent hallucinating medical facts | High | Critical | All claims must cite retrieved sources. Tool results vetted by RAG |
| Scope creep on tool complexity | Medium | Medium | Ship 4 tools only. Each is a single API call over existing data |
| Vision model API costs for demo | Low | Low | Cache extraction results. Demo uses pre-extracted examples |
| Agent loop exceeds token budget | Medium | Medium | Cap agent turns at 5. Summarize context when approaching limit |

---

## Success Criteria

Portfolio-ready when all criteria met:

1. **Extraction:** Upload a lab report photo -> structured extraction with 90%+ field accuracy
2. **Agent grounding:** Ask "what do these results mean?" -> agent calls reference range + differential tools -> grounded response with citations
3. **Tool accuracy:** Ask "any drug interactions?" -> agent calls drug interaction tool -> accurate interaction list
4. **Performance:** Full flow completes in <30 seconds end-to-end
5. **Transparency:** UI shows agent reasoning chain (tool calls, intermediate thoughts)

---

## Portfolio Differentiators

What makes this stand out:

- **Multi-modal** (vision + text) — shows breadth
- **Agentic** (tool use, multi-step reasoning) — shows depth
- **Medical domain** — shows domain-specific engineering
- **Grounded** (RAG + citations, not just generation) — shows responsibility
- **Interactive** (not just Q&A) — shows product thinking
- **Transparent** (agent thought process visible) — shows engineering maturity

---

## Data Models

```python
@dataclass
class LabResult:
    test_name: str          # "Hemoglobin"
    value: float            # 10.2
    unit: str               # "g/dL"
    reference_range: str    # "13.5-17.5"
    flag: str               # "low" | "normal" | "high" | "critical"
    confidence: float       # extraction confidence 0-1

@dataclass
class Medication:
    name: str               # "Warfarin"
    dosage: str             # "5mg"
    frequency: str          # "daily"
    confidence: float

@dataclass
class ExtractionResult:
    document_type: str      # "lab_report" | "prescription" | "clinical_note"
    patient_info: dict      # age, sex (if available)
    lab_results: list[LabResult]
    medications: list[Medication]
    conditions: list[str]
    raw_text: str
    confidence: float

@dataclass
class AgentStep:
    thought: str
    tool_name: str | None
    tool_input: dict | None
    tool_output: dict | None
    observation: str

@dataclass
class CopilotResponse:
    answer: str
    agent_steps: list[AgentStep]
    sources: list[Source]
    follow_up_suggestions: list[str]
    extraction: ExtractionResult | None
```

---

## API Endpoints

```
POST /copilot/upload
  - Accepts: multipart/form-data (image or PDF)
  - Returns: ExtractionResult (structured data)

POST /copilot/chat
  - Accepts: { message, session_id, extraction_context? }
  - Returns: SSE stream of CopilotResponse

GET /copilot/suggestions
  - Accepts: { extraction_context }
  - Returns: list of suggested follow-up questions
```
