# Frontend Enhancement Design: Transparency & Visualization Features

**Date:** 2026-02-27
**Status:** Completed
**Approach:** Incremental - Confidence First (Approach 1)

## Overview

This design outlines incremental enhancements to the medical Q&A frontend to improve transparency, provide better pipeline visualization, and create a more impressive demo experience. The focus is on showing both technical details and user-friendly explanations for mixed audiences (technical and non-technical stakeholders).

## Goals

1. **Demo/Showcase** - Create visually impressive interface that highlights transparency and technical sophistication
2. **Technical Debugging** - Provide tools for developers to inspect pipeline details
3. **User Transparency** - Help medical professionals understand how the AI works and build trust
4. **Simplicity** - Every change impacts as little code as possible

## Implementation Phases

### Phase 1: Confidence Indicators (Quick Win, High Impact)

**Timeline:** ~1 week
**Impact:** Immediate visual polish and transparency improvement

### Phase 2: Interactive Document Inspection
**Timeline:** ~1 week
**Impact:** Deep transparency into retrieved content

### Phase 3: Visual Flow Diagrams
**Timeline:** ~2 weeks
**Impact:** Impressive animated pipeline visualization

### Phase 4: Historical Trending
**Timeline:** ~1 week
**Impact:** Track improvements over time

---

## Phase 1: Confidence Indicators

### Architecture

**New Components:**
- `ConfidenceBadge.svelte` - Shows high/medium/low confidence with color coding
- `MetricBar.svelte` - Visual progress bar for scores
- `SourceQualityIndicator.svelte` - Domain credibility badges
- `MessageBubble.svelte` - Wrapper for messages with confidence indicators

**Enhanced Components:**
- `PipelinePanel.svelte` - Add status badges and metric bars to each stage
- `+page.svelte` - Display confidence indicators in chat stream

**Data Flow:**
```
API Response → Confidence Calculator (frontend) → Visual Components
```

**Key Principle:** All confidence calculation happens client-side using existing pipeline data. No backend changes required.

### Confidence Scoring Logic

**Overall Confidence** = Weighted Average (0-100):
- **Retrieval Score (40%)** - Average document similarity scores
- **Source Quality (30%)** - .gov/.edu sources > .org > .com
- **Context Relevance (20%)** - Chunk count and coverage
- **Generation Success (10%)** - No errors, reasonable token count

**Confidence Levels:**
- **High (75-100)** - Green badge with checkmark
- **Medium (40-74)** - Yellow/orange badge with warning
- **Low (0-39)** - Red badge with alert

### Component Specifications

#### ConfidenceBadge.svelte
```typescript
interface Props {
  level: 'high' | 'medium' | 'low'
  score: number  // 0-100
  label?: string
}
```

#### MetricBar.svelte
```typescript
interface Props {
  value: number  // 0-100
  label: string
  color?: 'green' | 'yellow' | 'red'
  showValue?: boolean
}
```

#### SourceQualityIndicator.svelte
```typescript
interface Props {
  source: string  // URL or domain
}
```

**Badge Types:**
- **Official (.gov, .edu)** - Blue badge, "Official" label
- **Organization (.org)** - Green badge, "Organization" label
- **Commercial (.com)** - Gray badge, "General" label

### Data Structures

**New file:** `src/lib/confidenceCalculator.ts`

```typescript
export interface ConfidenceScore {
  overall: number
  level: 'high' | 'medium' | 'low'
  breakdown: {
    retrieval: number
    sourceQuality: number
    contextRelevance: number
    generationSuccess: number
  }
}

export function calculateConfidence(
  pipelineTrace: PipelineTrace | null | undefined
): ConfidenceScore
```

**Extensions to `src/lib/types.ts`:**

```typescript
// Enhance existing Source interface
export interface Source {
  url: string
  title: string
  snippet?: string
  domainType?: 'government' | 'education' | 'organization' | 'commercial'
  credibilityScore?: number
}

// Enhance existing PipelineTrace interface
export interface PipelineTrace {
  retrieval: RetrievalStage
  context: ContextStage
  generation: GenerationStage
  overallConfidence?: number
  stageStatus?: {
    retrieval: 'success' | 'warning' | 'error'
    context: 'success' | 'warning' | 'error'
    generation: 'success' | 'warning' | 'error'
  }
}
```

### Layout Changes

**Chat Interface (+page.svelte):**
- Add `ConfidenceBadge` inline next to assistant messages
- Add `SourceQualityIndicator` next to source links
- No major layout restructuring - inline enhancements only

**Pipeline Panel:**
- Add stage status badges (✅ success, ⚠️ warning, ❌ error)
- Display `MetricBar` for each document's relevance score
- Show timing with status indicators
- Display aggregate confidence score at top

### Error Handling

**Confidence Calculation:**
- Returns default "medium" confidence (50) if pipeline data missing
- Gracefully handles partial/malformed data
- Never crashes UI - shows degraded indicators with defaults

**Component-Level:**
- `ConfidenceBadge` shows "Confidence unavailable" if score undefined
- `MetricBar` shows "N/A" for out-of-range values
- `SourceQualityIndicator` shows "Unknown source" for invalid URLs

**Pipeline Errors:**
- User-friendly error messages (not raw stack traces)
- Suggest recovery actions: "Try rephrasing your question"
- Show retry buttons for error states

### Testing

**Files to create:**
- `tests/confidence-badge.spec.ts` - Badge rendering tests
- `tests/source-quality.spec.ts` - Source badge tests
- `tests/metric-bar.spec.ts` - Metric bar tests
- `tests/pipeline-panel-enhanced.spec.ts` - Integration tests
- `src/lib/confidenceCalculator.test.ts` - Unit tests

**Coverage:**
- High/medium/low confidence scenarios
- All source types (.gov, .org, .com)
- Missing/malformed data handling
- Visual regression with Playwright screenshots
- Unit tests for calculation logic

### Success Criteria

✅ Assistant messages show confidence badges
✅ Source links have quality indicators
✅ Pipeline panel shows stage status icons
✅ Metric bars display for document scores
✅ All tests pass
✅ Mobile responsive (no overflow/wrapping issues)
✅ Error states handled gracefully

---

## Phase 2: Interactive Document Inspection

**Note:** Detailed design to be created after Phase 1 completion

### High-Level Features

- **Clickable Documents** - Click retrieved documents to expand full content
- **Chunk Highlighting** - Show which chunks were actually used in the answer
- **Document Metadata** - Display source, date, relevance score
- **"Why Retrieved?" Tooltips** - Explain semantic similarity, keyword matches

### Rough Component Ideas

- `DocumentInspector.svelte` - Modal/side panel for full document view
- `ChunkHighlighter.svelte` - Highlight relevant passages
- Enhanced `StepCard.svelte` - Add click-to-expand behavior

---

## Phase 3: Visual Flow Diagrams

**Note:** Detailed design to be created after Phase 2 completion

### High-Level Features

- **Animated Node-Link Diagram** - Show pipeline stages as connected nodes
- **Real-Time Status** - Data flowing through stages with animations
- **Stage Indicators** - Color-coded status per stage
- **Interactive Diagram** - Click stages to see details

### Rough Component Ideas

- `PipelineFlowDiagram.svelte` - SVG or canvas-based flow visualization
- `FlowNode.svelte` - Individual stage node with status
- WebSocket connection for real-time updates (backend enhancement)

---

## Phase 4: Historical Trending

**Note:** Detailed design to be created after Phase 3 completion

### High-Level Features

- **Time-Series Charts** - Show metric changes over time
- **Run Comparison** - Side-by-side comparison of multiple evaluation runs
- **Trend Indicators** - Show improving/declining metrics with arrows

### Rough Component Ideas

- `MetricChart.svelte` - Line/bar charts for metrics
- Enhanced evaluation dashboard with historical data
- New API endpoint: `GET /evaluation/history`

---

## Development Notes

### Principles

1. **Simplicity First** - Each phase impacts minimal code
2. **Incremental Value** - Each phase delivers standalone value
3. **No Breaking Changes** - All enhancements are additive
4. **Client-Side First** - Minimize backend changes initially
5. **Mobile Responsive** - Test on tablet/mobile throughout

### Dependencies

**Phase 1:**
- No new dependencies (uses existing Svelte 5, Playwright)
- May add Vitest for unit testing Svelte components

**Phase 3:**
- May need charting library (e.g., Chart.js, Recharts) for flow diagram
- Consider using existing Svelte charting libraries

**Phase 4:**
- Charting library (same as Phase 3 if applicable)
- Backend API changes for historical data

### Technology Stack

- **Framework:** Svelte 5 with SvelteKit (already in use)
- **Testing:** Playwright (E2E), Vitest (unit tests - new)
- **Charts:** TBD (Chart.js or similar)
- **Icons:** Existing icon system or Lucide icons

---

## Open Questions

1. **Chart Library** - Which library for Phase 3/4 visualizations? (Recharts, Chart.js, ECharts?)
2. **Unit Testing** - Confirm Vitest vs other Svelte testing approaches
3. **Real-Time Updates** - Phase 3 may need WebSocket - confirm backend feasibility

---

## Next Steps

1. ✅ Design document approved
2. ✅ Phase 1: Confidence Indicators - Implemented
3. ✅ Phase 2: Interactive Document Inspection - Implemented
4. ✅ Phase 3: Visual Flow Diagrams - Implemented
5. ✅ Phase 4: Historical Trending - Implemented
6. ✅ Architecture documentation updated

---

## Appendix: Current Frontend Architecture

**Technology Stack:**
- Svelte 5 with SvelteKit 2.50.2
- TypeScript
- Playwright for E2E testing
- Vite 7.3.1

**Current Routes:**
- `/` - Chat interface with pipeline toggle
- `/eval` - Evaluation dashboard with metrics

**Current Components:**
- `PipelinePanel.svelte` - Shows retrieval → context → generation stages
- `StepCard.svelte` - Collapsible card component
- `+page.svelte` - Main chat interface
- `+layout.svelte` - Root layout with navigation

**Current API:**
- `POST /chat?include_pipeline=true` - Chat with pipeline data
- `GET /history/{session_id}` - Load chat history
- `GET /evaluation/latest` - Latest evaluation metrics
