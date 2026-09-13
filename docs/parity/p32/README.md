# P3.2 Parity Gate Artifacts

Roadmap `docs/plans/20260910-structural-refactor-roadmap.md` — Phase 3.2
(Hamilton delegation) mandatory parity gate.

## Method (offline substitute per roadmap gotcha 15)

No embedding API key was available on this machine, so both sides ran under
the **same deterministic fake embedder** (8-dim sha256 vectors, identical to
`tests/integration/conftest.py::fake_chroma_embeddings`), against a fixed
fabricated corpus (3 html+md pairs, 1 minimal PDF, 8-row LabQAR reference
CSV) in isolated git worktrees with isolated Chroma persistence.

- Baseline: `66837eb` (pre-P3.2; runtime build via `rag/index.py:_build_index_from_sources`)
- Branch: `006c730` (post-P3.2; runtime build delegates to `run_ingestion` → Hamilton DAG)
- Runner: `python scripts/manual/parity_gate_p32.py run|compare`
- Assessment config: LLM-free (`disable_llm_generation=True`,
  `include_answer_eval=False`), fixed seeds (42/42), `force_rerun=True`,
  default runtime config (no experiment yaml).

## Gated quantities (exact-match)

- L0–L5 step-check aggregates **and records**
- Retrieval metrics (heuristic-graded nDCG@k / recall@k / hit-rate@k — full
  float precision)
- Dataset stats (21 queries, deterministic heuristic generation)

Excluded as nondeterministic by construction: timing/latency fields, file
sizes, wall clock, epoch timestamps, worktree-root path prefixes.

## Result

**PASS** — all gated quantities identical, including the stored
`source_class_distribution` (`guideline_html: 6, guideline_pdf: 1,
reference_csv: 8`), which was the critical risk: the pre-P3.2 DAG stripped
rich document metadata at the silver boundary, which would have silently
changed retrieval boost semantics after delegation. Fixed pre-gate by the
P3.2 "rich passthrough" (see roadmap gotcha 16).

Files:

- `baseline_66837eb.json` — baseline normalized metrics
- `branch_006c730.json` — branch normalized metrics
