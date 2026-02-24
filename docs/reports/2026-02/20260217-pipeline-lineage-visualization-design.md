# Pipeline Lineage Visualization Design

**Date:** 2026-02-17
**Status:** Approved
**Approach:** Backend-Only Changes with Opt-in Pipeline Tracing

## Overview

Enhance the medical Q&A chatbot to show full pipeline lineage including query retrieval, data lineage, and pipeline visualization. Users will be able to see how their questions are processed through the RAG pipeline with technical detail about retrieved documents, score breakdowns, and context sent to the LLM.

## Requirements

### Functional Requirements
- Show full pipeline journey from query → embedding → retrieval → generation
- Display technical details for each stage (retrieval, scoring, context assembly, generation)
- Present retrieved documents with individual scores (semantic, keyword, source boost)
- Visualize score breakdown (60% semantic, 20% keyword, 20% source boost)
- Show exact text chunks sent to the LLM
- Include timing information for each stage

### Non-Functional Requirements
- Pipeline tracing must be opt-in (zero performance impact when disabled)
- Pipeline failures must not break normal chat functionality
- UI must be responsive (desktop, tablet, mobile)
- Frontend must gracefully handle missing or incomplete pipeline data

## Architecture

### Overall Structure

**Backend (FastAPI):**
- Add new data models for pipeline tracing in `src/main.py`
- Modify `VectorStore` in `src/vectorstore/store.py` to capture detailed metadata
- Update RAG retriever to collect and return pipeline information
- Pipeline data flows through the same `/chat` endpoint, augmented with optional tracing

**Frontend (SvelteKit):**
- New right sidebar component (`PipelinePanel.svelte`)
- Enhanced message state to include pipeline data
- New visualization components for each pipeline stage
- Minimal changes to existing chat UI

### Data Flow

```
User Query → /chat?include_pipeline=true
           ↓
    Query embedding created (timed)
           ↓
    VectorStore.similarity_search_with_trace()
           ↓
    Retrieved documents (top 5) with metadata:
    - doc_id, content, source, page
    - semantic_score, keyword_score, source_boost
    - combined_score, rank
           ↓
    Score breakdown calculated
    (60% semantic, 20% keyword, 20% boost)
           ↓
    Context assembled (chunks + sources)
           ↓
    GeminiClient.generate() (timed)
           ↓
    ChatResponseWithPipeline {
      response,
      sources,
      pipeline: PipelineTrace {
        retrieval_stage,
        context_stage,
        generation_stage,
        total_time_ms
      }
    }
```

## Components

### Backend Components

#### 1. PipelineTrace Data Model (`src/main.py`)

```python
class RetrievedDocument(BaseModel):
    id: str
    content: str
    source: str
    page: Optional[int]
    semantic_score: float
    keyword_score: float
    source_boost: float
    combined_score: float
    rank: int

class RetrievalStage(BaseModel):
    query: str
    top_k: int
    documents: List[RetrievedDocument]
    score_weights: dict  # {"semantic": 0.6, "keyword": 0.2, "source": 0.2}
    timing_ms: int

class ContextStage(BaseModel):
    total_chunks: int
    total_chars: int
    sources: List[str]
    preview: str  # First 200 chars of context sent to LLM

class GenerationStage(BaseModel):
    model: str
    timing_ms: int
    tokens_estimate: Optional[int]

class PipelineTrace(BaseModel):
    retrieval: RetrievalStage
    context: ContextStage
    generation: GenerationStage
    total_time_ms: int
```

#### 2. Enhanced VectorStore (`src/vectorstore/store.py`)

Add `similarity_search_with_trace()` method:
- Returns both existing format AND new `RetrievedDocument` objects
- Calculates and returns individual score components
- Captures timing information

#### 3. Modified Chat Endpoint (`src/main.py`)

```python
@router.post("/chat")
async def chat(
    request: ChatRequest,
    include_pipeline: bool = False,
    ...
) -> ChatResponse | ChatResponseWithPipeline:
```

### Frontend Components

#### 1. PipelinePanel.svelte (new)
- Right sidebar, collapsible
- Receives `pipeline` prop of type `PipelineTrace`
- Contains step cards for each stage
- Toggle button to show/hide

#### 2. StepCard.svelte (new)
- Reusable component for each pipeline stage
- Shows stage name, timing, status
- Expandable to show details

#### 3. DocumentList.svelte (new)
- Displays retrieved documents in table/card format
- Shows scores with visual bars
- Click to expand full content

#### 4. ScoreBreakdown.svelte (new)
- Visual representation of score composition
- Stacked bar chart: [ semantic | keyword | boost ]

### Data Models

#### TypeScript Frontend Models

```typescript
interface RetrievedDocument {
  id: string;
  content: string;
  source: string;
  page?: number;
  semantic_score: number;
  keyword_score: number;
  source_boost: number;
  combined_score: number;
  rank: number;
}

interface RetrievalStage {
  query: string;
  top_k: number;
  documents: RetrievedDocument[];
  score_weights: { semantic: number; keyword: number; source: number };
  timing_ms: number;
}

interface ContextStage {
  total_chunks: number;
  total_chars: number;
  sources: string[];
  preview: string;
}

interface GenerationStage {
  model: string;
  timing_ms: number;
  tokens_estimate?: number;
}

interface PipelineTrace {
  retrieval: RetrievalStage;
  context: ContextStage;
  generation: GenerationStage;
  total_time_ms: number;
}

interface Message {
  role: 'user' | 'assistant';
  content: string;
  sources?: string[];
  pipeline?: PipelineTrace;
}
```

## UI/UX Design

### Layout

```
┌─────────────────────────────────────────────────────────────┐
│  Header: Health Screening Interpreter                        │
├──────────────────────────────────┬──────────────────────────┤
│                                  │                          │
│  Chat Messages Area              │  Pipeline Panel          │
│  (scrollable)                    │  (collapsible)           │
│                                  │                          │
│  [User msg]                      │  ┌────────────────────┐ │
│                                  │  │ Query Processing   │ │
│  [Assistant msg]          [🔍]   │  │ 45ms               │ │
│    Sources: [pdf] [csv]          │  └────────────────────┘ │
│                                  │                          │
│  [Input box]              [Send] │  ┌────────────────────┐ │
│                                  │  │ Retrieval          │ │
│                                  │  │ ▼ 5 docs found     │ │
│                                  │  │ 1. Lipid guide...  │ │
│                                  │  │    Score: 0.89     │ │
│                                  │  │    [▶ Expand]      │ │
│                                  │  └────────────────────┘ │
│                                  │                          │
│                                  │  ┌────────────────────┐ │
│                                  │  │ Score Breakdown    │ │
│                                  │  │ ████████░░ 89%     │ │
│                                  │  └────────────────────┘ │
│                                  │                          │
│                                  │  ┌────────────────────┐ │
│                                  │  │ Context to LLM     │ │
│                                  │  │ 3 chunks, 1245     │ │
│                                  │  │ chars              │ │
│                                  │  └────────────────────┘ │
└──────────────────────────────────┴──────────────────────────┘
```

### Interactions

**Toggle Pipeline Panel:**
- Button appears next to assistant messages when pipeline data is available
- Click to expand/collapse sidebar
- State persists during session

**Expandable Sections:**
- Each stage card shows summary by default
- Click to expand and see detailed information
- Documents show: rank, source, page, combined score
- Click document to see full content chunk + individual scores

**Visual Cues:**
- Color-coded scores: green (>0.8), yellow (0.5-0.8), red (<0.5)
- Animated loading states during pipeline execution
- Timing badges on each stage

**Responsive Design:**
- Desktop: Side panel visible
- Tablet: Panel slides in as overlay
- Mobile: Full-screen panel with back button

## Implementation Details

### Backend Changes

#### Request Flow

1. User sends message with pipeline flag:
```typescript
fetch('/chat?include_pipeline=true', {
  method: 'POST',
  body: JSON.stringify({ message, session_id })
})
```

2. Backend processes request:
```python
@router.post("/chat")
async def chat(
    request: ChatRequest,
    include_pipeline: bool = False,
    ...
):
    if include_pipeline:
        docs, trace = retrieve_context_with_trace(request.message)
        response = await generate_response(docs)
        return ChatResponseWithPipeline(
            response=response.text,
            sources=extract_sources(docs),
            pipeline=trace
        )
    else:
        docs = retrieve_context(request.message)
        response = await generate_response(docs)
        return ChatResponse(
            response=response.text,
            sources=extract_sources(docs)
        )
```

### Frontend Changes

#### State Management

```typescript
let showPipeline = $state(false);
let includePipelineForSession = $state(false);

// Toggle controls in UI
<svelte:component this={Toggle}
  bind:checked={includePipelineForSession}
  label="Show pipeline details"
/>
```

#### Rendering

```svelte
<PipelinePanel
  pipeline={currentMessage.pipeline}
  isOpen={showPipeline}
  onToggle={() => showPipeline = !showPipeline}
/>
```

## Error Handling

### Backend

**Pipeline tracing failures shouldn't break chat:**
```python
try:
    docs, trace = retrieve_context_with_trace(query)
    response = await generate_response(docs)
    return ChatResponseWithPipeline(..., pipeline=trace)
except Exception as e:
    logger.warning(f"Pipeline tracing failed: {e}")
    docs = retrieve_context(query)  # Normal path
    response = await generate_response(docs)
    return ChatResponse(...)  # Return without pipeline
```

**Partial data handling:**
- If timing fails, still return document scores
- If document details fail, still return basic retrieval info
- Always include at least retrieval_stage even if incomplete

### Frontend

**Missing or incomplete pipeline data:**
```svelte
{#if message.pipeline}
  <PipelinePanel pipeline={message.pipeline} />
{:else if message.sources && showPipeline}
  <div class="pipeline-unavailable">
    Pipeline details not available for this message
  </div>
{/if}
```

**Client-side validation:**
- Check for required fields before rendering
- Gracefully display "Data unavailable" for missing sections
- Never crash the chat UI due to pipeline rendering issues

## Testing Strategy

### Backend Tests

**Unit tests** (`tests/test_pipeline_trace.py`):
- Test `similarity_search_with_trace()` returns correct structure
- Verify score breakdown adds up to combined score
- Check timing captures are reasonable
- Test error fallback logic

**Integration tests** (`tests/test_chat_with_pipeline.py`):
- Test `/chat?include_pipeline=true` endpoint
- Verify response structure matches schema
- Test with and without pipeline flag
- Test with various queries (simple, complex, edge cases)

### Frontend Tests

**Component tests** (`frontend/tests/pipeline.spec.ts`):
- Test PipelinePanel renders with pipeline data
- Test expand/collapse functionality
- Test score breakdown visualization
- Test document list display

**E2E tests** (`frontend/tests/chat-with-pipeline.spec.ts`):
- Test full flow: send message with pipeline toggle
- Verify panel appears with correct data
- Test user interactions (expand, click documents)
- Test responsive behavior

### Manual Testing Checklist

- [ ] Chat works normally with `include_pipeline=false`
- [ ] Chat works with `include_pipeline=true`
- [ ] Pipeline panel shows all stages
- [ ] Score breakdown matches individual scores
- [ ] Document content is accurate
- [ ] Context preview matches what was sent to LLM
- [ ] Toggle on/off persists during session
- [ ] Mobile layout works correctly

## Critical Files to Modify

### Backend
- `src/main.py` - Add pipeline data models, modify chat endpoint
- `src/vectorstore/store.py` - Add `similarity_search_with_trace()` method
- `src/rag/retriever.py` - Update to collect pipeline metadata

### Frontend
- `frontend/src/routes/+page.svelte` - Add pipeline toggle state and PipelinePanel
- `frontend/src/lib/types.ts` (new) - TypeScript interfaces for pipeline data
- `frontend/src/lib/components/PipelinePanel.svelte` (new)
- `frontend/src/lib/components/StepCard.svelte` (new)
- `frontend/src/lib/components/DocumentList.svelte` (new)
- `frontend/src/lib/components/ScoreBreakdown.svelte` (new)

## Success Criteria

1. Users can toggle pipeline visualization on/off
2. Pipeline panel shows complete retrieval, scoring, and generation details
3. Score breakdown transparently shows how documents are ranked
4. Users can see exact context sent to the LLM
5. Performance is unaffected when pipeline tracing is disabled
6. UI gracefully handles missing or incomplete pipeline data
7. Visualization works across desktop, tablet, and mobile devices
