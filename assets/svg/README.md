# Fieldnote — evidence-led private research lab
Design lead: Sol. Design specifications plus the now-implemented offline Fieldnote redesign.

## Current direction
**Substantially redesign within SvelteKit**, retaining FastAPI, RAG, offline ingestion and research capabilities.
The second review corrected the first pass's public-reader emphasis: owner decisions identify this as a **private research lab**, with public/synthetic data and no clinical-suitability claims. Q&A remains a workbench, not the whole product.

Read [review and refinement](review-and-refinement.md), then [repository findings](repository-findings.md), [design rationale](design-rationale.md), [data map](screen-data-map.md), [interactions](interaction-spec.md) and [implementation handoff](implementation-handoff.md).

## Implementation package — ready for the next agent
- [Full specification](implementation-specification.md): routes, DTO/API contracts, safety, data semantics and acceptance scenarios.
- [File and ownership map](implementation-map.md): exact existing/new paths, components, tests and shared integration boundaries.
- [Phased implementation plan](implementation-plan.md): P00–P10 dependencies, gates, execution briefs, tests and rollback.
- [Continuation handoff](continuation-handoff.md): P01–P10 state, verified baseline, deployment gate and new-thread kickoff.
- [Next-agent starting brief](next-agent-start.md): verification, deployment/next-work instructions.
- [Specification review](implementation-review.md): findings addressed, rejected unsupported claims and remaining gates.

**P01–P10 and the P09.1/P10.1 review follow-ups were implemented offline**; see the [P10 readiness report](../../docs/plans/20261101-p10-readiness.md), the [follow-up report](../../docs/plans/20261102-p09p10-ask-surface-and-hardening.md) and per-slice reports. Deployment and authenticated-release verification are **not** done. Continue via the continuation handoff and [deployment pickup brief](../../docs/plans/20261101-deployment-pickup.md); this is not deployment/live-spend/public-rollout approval.

## Suggested visual review
01 → 13 → 14 → 15 → 16 → 18 → 08 → 09 → 12, followed by mobile/system/source screens.

## Asset index
All SVGs have explicit viewBoxes, selectable system-font text and editable vector elements. Open directly in a browser. These specify semantic HTML/components/chart output, not an SVG-only application.

| Asset | Viewport | Purpose |
|---|---|---|
| [00 design system](00-design-system.svg) | 1440 × 1200 | Palette, type, spacing, charts, controls |
| [01 workspace](01-overview-desktop.svg) | 1440 × 1360 | Research-first overview, coverage story and Q&A workbench |
| [02 evidence explorer](02-explorer-desktop.svg) | 1440 × 1120 | Chunk browsing with real PDF examples |
| [03 source detail](03-detail-desktop.svg) | 1440 × 1120 | Excerpt, provenance and limits |
| [04 mobile workspace](04-overview-mobile.svg) | 390 × 1340 | Evaluation/features/datasets/Q&A entry |
| [05 mobile explorer](05-explorer-mobile.svg) | 390 × 1220 | Cards + separately illustrated filter sheet |
| [06 general states](06-interaction-and-states.svg) | 1440 × 1220 | Loading, incomplete, empty, unavailable, access |
| [07 IA](07-information-architecture.svg) | 1440 × 1220 | Private lab research journeys and migration |
| [08 Q&A chat](08-qna-chat-desktop.svg) | 1440 × 1180 | Individual-turn showcases and follow-up |
| [09 turn breakdown](09-turn-breakdown-desktop.svg) | 1440 × 1420 | Recorded stages, timing, ranked chunks |
| [10 mobile Q&A](10-qna-turn-mobile.svg) | 390 × 1320 | Answer + subsequent full-screen inspection |
| [11 archived reranking note](11-research-comparison.svg) | 1440 × 1170 | Separate 54-query reported quality/latency trade-off |
| [12 individual step](12-individual-step-inspector.svg) | 1440 × 1180 | Harness-inspired raw step inspector |
| [13 evaluation coverage](13-evaluation-coverage-desktop.svg) | 1440 × 1370 | Actual 57-query baseline means + successful/failed slots |
| [14 feature evidence](14-feature-evidence-desktop.svg) | 1440 × 1330 | Declared variant matrix, observed results, capability map |
| [15 dataset catalog](15-dataset-catalog-desktop.svg) | 1440 × 1440 | Actual inventory, splits, overlap, label/review provenance |
| [16 fixture case](16-dataset-case-inspector.svg) | 1440 × 1250 | Real expected labels vs unavailable archived observations |
| [17 mobile evaluation](17-evaluation-mobile.svg) | 390 × 1390 | Coverage and means remain readable together |
| [18 comparison gate](18-comparison-gate-and-states.svg) | 1440 × 1210 | Preserve comparable=false; research-specific states |

Tall viewBoxes are scrolling pages. Screens05/10 illustrate sequential states, not combined runtime layouts.

## Evidence legend
- **Verified local data:** D11 counts; real PDF excerpt; current fixture counts/splits/overlap; actual archived JSON metric counts and means.
- **Reported archive:** screen11 values come from repository documentation; original 54-query bundle is absent. Screen14's 57-query values come from local aggregate JSON, but underlying per-case directories are absent.
- **Synthetic:** all chat outputs, timings, scores, example model and trace counts in 08–10/12.
- **Proposed:** every new layout/route, dataset catalog adapter, report-identity integration, global facets, search and future storage/instrumentation. Existing support is mapped separately.
- Confidence labels, manifest assertions and high means do not establish reviewer identity, clinical validity or comparison eligibility.

## Validation
All **19 SVGs** were XML-parsed, Chromium-rendered and visually reviewed. Text-bound/overlap checks, contrast, arithmetic and relative documentation links were checked; see [validation record](validation.md).
No live provider evaluation, historical rerun, authenticated deployment or clinical validation was performed.
