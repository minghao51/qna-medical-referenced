# Review and refinement — research as a first-class product
## Verdict
Yes. The first pass was strongest at per-turn Q&A, raw trace inspection and source provenance. It underrepresented why this repository exists: **a private lab for evaluating retrieval, generation and pipeline choices**.

This refinement changes the hierarchy, not just the styling. It keeps SvelteKit, existing backend/research capabilities and the original visual language. It adds six dedicated research screens and replaces root/mobile overview and IA. No application implementation or deployment is included.

## Prioritized review
| Priority | Finding | Evidence | Design response |
|---|---|---|---|
| P0 | Public-reader framing conflicts with recorded private-lab scope | decisions.md D01/D02/D07/D09/D10 | Research-first root, private-lab headers, CLI-first execution; Q&A retained as workbench |
| P0 | A high mean can hide failed measurements | Local 57-query baseline: faithfulness .9799, count15, errors42 | Coverage beside every score; separate slots from queries |
| P0 | Current histories are explicitly non-comparable | artifact_service.py forces comparable=false; null history averages | Comparison gate; no unsupported trend/leaderboard |
| P1 | Features have no evidence-status narrative | Existing configs, optional strategies, old winner fields | Declared variant matrix + implemented/effective/evidence distinctions |
| P1 | Dataset identity and overlap are invisible | Expanded54 exact queries all present in All57 | Catalog, splits, overlap warning and provenance |
| P1 | Current case drilldown can confuse latest with historical selection | load_step_records/load_l6_records select latest | Expected vs Observed panels; explicit missing archived case records |
| P1 | Config/report names do not reliably join | medical_semantic_exp.yaml vs medical_semantic_chunking_exp_report.json | Explicit report identity/adapter rather than inferred stem match |
| P2 | Some metric formatting distorts meaning | experiments metricValue defaults0, fmtDelta ×100, deltaClass higher=better | Null-safe formatting, direction metadata, absolute vs relative deltas |
| P2 | Near-duplicates / confidence intervals / effective settings are not established | Missing provenance and per-case runs; no inferential analysis run | Mark unverified/deferred; do not fabricate extra plots |

## Additional investigation
Sol re-read evaluation routes, artifact loading, dataset normalization, review authority, feature runners and current evaluation components; inspected public/synthetic fixtures and the local JSON report without provider calls. Codex gpt-5.6-luna performed an independent read-only design/code review using the previously verified fallback model. No exact model-version availability is newly claimed.

### What changes the story
1. The local baseline report has **268 successful metric slots and 74 failed slots out of 342 expected** (six metrics × 57 questions). Faithfulness's high mean covers only 15 successes. This is the central editorial example.
2. All four archived feature variants are degraded; per-case directories are absent. Showing a report's legacy winner as a current eligible winner would mislead.
3. There are several overlapping golden query fixtures, not one benchmark. All57 and Expanded54 share 54 exact question strings in their current bytes.
4. The frozen review set has eight cases, with seven answerable and one unanswerable. Manifest human_reviewed declarations do not authenticate reviewers.
5. Newer reviewed-evidence metrics and legacy keyword/source diagnostic scores must not share an unqualified nDCG label or comparison cohort.
6. Dataset catalog and coherent report identity require new read-only adapters. No existing datasets API was discovered.

## Refined experience
- **Workspace:** central evidence question, selected archived completeness story, research pathways and separate inventory units.
- **Evaluations:** measurement coverage, failures, metric semantics, report identity and comparison eligibility.
- **Features:** declared configuration vs known implementation vs observed archive; dependencies and limitations close to conclusions.
- **Datasets:** current fixture inventory, splits, labels, overlap, review/provenance and case expectations.
- **Q&A workbench:** existing individual-turn showcases and Harness-inspired RAG-step inspection.
- **Evidence:** chunk/source inspection remains separate from benchmark datasets.

## Screens and migration
- Replaced [01 desktop workspace](01-overview-desktop.svg), [04 mobile workspace](04-overview-mobile.svg), [07 IA](07-information-architecture.svg).
- Added [13 evaluation coverage](13-evaluation-coverage-desktop.svg), [14 feature evidence](14-feature-evidence-desktop.svg), [15 dataset catalog](15-dataset-catalog-desktop.svg), [16 case inspector](16-dataset-case-inspector.svg), [17 mobile evaluation](17-evaluation-mobile.svg), [18 comparison gate](18-comparison-gate-and-states.svg).
- Kept 00/02/03/05/06/08/09/10/11/12; aligned captions/access wording and qualified the archived comparison.
- Updated rationale, findings, data map, interactions, index and handoff. Existing route aliases and evaluation capabilities must survive implementation.

## Explicit non-goals
No live run launcher, feature activation switches, model-picker rollout, public auth/deployment, patient records, automatic promotion, manufactured confidence intervals, reconstructed missing case outputs, provider-call instrumentation or duplicate hosted trace system.

## Next useful refinement after contracts are available
A genuine per-case feature comparison, category/source-family slice analysis, ingestion→index lineage view and uncertainty estimates would be valuable. They require verified case pairing, preserved measurement definitions, sufficient samples and approved execution—not more decorative charts.
