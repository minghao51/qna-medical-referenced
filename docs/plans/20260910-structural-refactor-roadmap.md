# Structural Refactor Roadmap — Phases 0–3

**Status:** Approved plan (all decisions locked 2026-09-10)
**Source audit:** scout + reviewer subagent audit of `src/` (2026-09-10); see "Audit findings" below
**How to use:** Execute phases in order. Each task lists actions, files, re-point targets, and done-criteria.
**Ground rules:** AGENTS.md workflow applies (analyze first, minimal scope, high-level summaries).
Every PR must keep `ruff`, `mypy`, `pytest` green. Docs are updated **in the same PR** as the code change.

---

## ⚡ EXECUTION STATUS (updated 2026-09-10, end of Phase 2)

**Phases 0–2 are COMPLETE. Phase 3 is pending.** A fresh agent should read this
section, then §3 (target architecture), then the Phase 3 work orders.

### Branch / commit state

Stacked branches, not yet merged to `main` (merge sequentially, oldest first):

```
main
└── refactor/phase-0-docs        (1 commit)  19ee6c0  docs truth-sync + stage vocabulary
    └── refactor/phase-1-structure (7 commits) af0d2c3..4b58330  core/, nodes/, shims, services fold
        └── refactor/phase-2-structure (5 commits) 137a21d..4323bf4  ablations/, chroma split,
                                                     AssessmentPipeline, test mirroring
```

Working tree clean. 13 commits total.

### Task status

| Task | State | Commit | Notes |
|------|-------|--------|-------|
| P0.1–P0.3 docs truth-sync | ✅ done | 19ee6c0 | ARCHITECTURE/STRUCTURE/TESTING patched; `l6_contract.py` gained `STAGE_*` constants; `docs/architecture/pipeline-stages.md` created |
| P1.1 `src/core/` + source_metadata | ✅ done | af0d2c3 | 6 importers re-pointed |
| P1.2 `components/` → `nodes/` | ✅ done | 1a1061c | plain names, normal imports, public `NODE_MODULES` |
| P1.3 di.py protocol dedup | ✅ done | 55b2ec3 | rag protocol is TYPE_CHECKING-only (no runtime infra→rag edge) |
| P1.4 services/ → evals/ | ✅ done | 30679d4 | `evals/artifact_service.py`; BaseService deleted |
| P1.5 five shim deletions | ✅ done | d475de2 | ~30 files re-pointed; orchestrator resolves fn deps from module namespace at CALL TIME (monkeypatch-safe) |
| P1.6 hype → hypothetical_questions.py | ✅ done | 656e452 | symbol names + settings keys unchanged (keys → P3.6) |
| P1.7 exceptions → core | ✅ done | 4b58330 | infra→app and usecases→app violations gone |
| P2.1 experiment_config → addition_config | ✅ done | 137a21d | renamed + de-deprecated (it is NOT a duplicate of config.py — see commit) |
| P2.2 ablations → experiments/ablations/ | ✅ done | eb10b97 | retrieval_eval.py now pure metrics (470 lines, was 831); assessment/__init__ gained real lazy exports |
| P2.3 chroma_store split | ✅ done ⚠️ | 87b3f2c | store.py(802)+hype_index.py+listing.py+factory.py+re-export(24). **DEVIATION: legacy JSON snapshot path KEPT** — load-bearing for tests/l5 consumers; needs dedicated test rework before deletion |
| P2.4 AssessmentPipeline | ✅ done | 1e2fba1 | 9 staged methods, 23 ctor-injected fn fields; `run_assessment` = monkeypatch-friendly default composition |
| P2.5 convert_html split | ✅ no-op | (in 4323bf4 msg) | `main(force)` already library-quality; real fix is P3.3. Rationale in roadmap body |
| P2.6 test mirroring | ✅ done | 4323bf4 | unit+integration mirrored to package dirs; 2 `__file__`-relative fixture paths adjusted |
| P3.1 real constructor injection | ⬜ pending | | **start here** |
| P3.3 setter-channel kill (+P3.6 keys) | ⬜ pending | | after P3.1 |
| P3.2 Hamilton delegation + parity gate | ⬜ pending | | after P3.3 — mandatory baseline diff |
| P3.4 import-linter contract | ⬜ pending | | last — asserts end state |

### Verification baselines (must hold after every Phase 3 step)

- `pytest tests/unit` → **540 passed, 8 skipped**
- `pytest tests/integration` → **92 passed, 56 skipped** (skips = env-key/deps, pre-existing)
- `ruff check src/ tests/ scripts/` → clean
- mypy: **2 pre-existing errors** in `ingestion/indexing/store.py` (list invariance, `_extracted_keywords_from_metadata`) — present before the refactor on `main`; do not "fix" incidentally, do not add new ones
- P3.2 additionally requires the **parity gate** (§Phase 3)

### Gotchas discovered during execution (read before Phase 3)

1. **Ruff F401 eats re-exports.** Re-export modules must use alias form
   (`from x import Y as Y`) or ruff --fix deletes them mid-session (hit in P1.7).
2. **Monkeypatch contract:** tests patch *module attributes* on
   `evals/assessment/orchestrator` (and other modules). Any refactor must keep
   dependency resolution reading module attrs at call time — never bind fn
   defaults at def time (hit twice in P1.5/P2.4).
3. **Patch targets moved with the split:** chroma internals are patched at
   `src.ingestion.indexing.store` / `...indexing.factory` now, not `chroma_store`.
4. **`rg -r` is the replace-DISPLAY flag**, not recursion — it silently mangles
   output (hit in P1.5). Use plain `rg` + `grep` for verification greps.
5. **Env gaps (pre-existing):** `scipy` and `deepeval` are not installed in the
   dev venv (eval extras group). Imports of `experiments/metric_utils` and
   deepeval-dependent tests fail/skip — not regressions.
6. **`tests/integration/conftest.py` fixtures** patch `indexing.store.embed_texts` —
   keep that target valid when touching embedding wiring in P3.1.
7. **Docs-in-same-PR policy held** for Phases 0–2: `.planning/codebase/*` and
   `docs/architecture/*` are current as of 4323bf4. ARCHITECTURE.md still
   documents `di.py` as "scheduled for deletion in Phase 3" — keep that true.
8. **Hamilton driver** is constructed in `ingestion/pipeline.py::build_ingestion_pipeline`
   via `NODE_MODULES`; tests exercise it through `tests/integration/ingestion/test_dag_functional.py`.

### Phase 3 next-work checklist (pinned order)

1. **P3.1** real constructor injection: `app/factory.py` = composition root
   (construct LLMClient/ChatHistoryStore/ChromaVectorStore → `app.state` →
   FastAPI `Depends`); delete `infra/di.py` (169 lines); remove
   `llm_client or get_client()` fallbacks in `usecases/chat.py:~137,~236`;
   offline paths construct at their own edge; relocate
   `generate_hypothetical_questions` out of `rag/hyde.py` (kills last ingestion→rag edge).
2. **P3.3** full setter kill: delete `rag/runtime_config.py` cross-package setters
   + `convert_html.py` strategy/mode globals; steps take explicit params from a
   config snapshot; `app/routes/config.py` goes through a usecase facade;
   **P3.6**: `settings.hyde.*` → `settings.hype.*` via pydantic alias + warning.
3. **P3.2** Hamilton delegation: `run_ingestion(config)` library entry with cached
   driver in `ingestion/pipeline.py`; `rag/index.py::initialize_vector_store_async`
   delegates via `asyncio.to_thread`; delete `_build_index_from_sources` +
   `materialize_html` param; preserve signature-check skip + `get_runtime_status`.
   **Run the parity gate before merge** (baseline on current branch first!).
4. **P3.4** import-linter: `cli > app > usecases > {rag,evals,experiments} >
   {ingestion,infra} > core > config` + forbids (infra→app, ingestion→rag,
   usecases→cli); wire into `ci.yml`.
5. Rewrite ARCHITECTURE.md boundaries section to the final state; mark roadmap
   phases complete in this file.

---

## 1. Why this refactor exists

Three structural debts dominate onboarding cost for a fresh dev or agent:

1. **Wiring chaos** — a decorative DI container (`infra/di.py`, used by exactly one file) coexisting
   with module singletons (`chroma_store.get_vector_store`, 10 callers), four conflicting protocol
   definitions, and silent parameter fallbacks (`llm_client or get_client()`).
2. **Two parallel ingestion pipelines** — `rag/index.py:_build_index_from_sources` re-implements the
   chunk→HyPE→enrich→embed→index sequence that the Hamilton DAG already orchestrates.
3. **Quadruple stage vocabulary** — the same DAG is named four ways (`steps/download_pdfs.py`,
   `components/01_download.py`, `checks/l0_download.py`, `l6_contract.py`), crowned by
   digit-prefixed files that are a `SyntaxError` to import normally.

Secondary: god modules (`chroma_store.py` 1,028 lines; `orchestrator.py` ~490-line function),
five compat shims, a vestigial `services/` layer, a stray `src/source_metadata.py`, config sprawl
(5 layers), layering violations (`infra → app`, `ingestion ↔ rag` soft cycle), flat `tests/unit/`
(65 files, no mirroring), and stale claims in `.planning/codebase/ARCHITECTURE.md`.

## 2. Locked decisions

| ID | Decision | Choice | Consequence |
|----|----------|--------|-------------|
| D0.1 | Doc cadence | Patch now + update per PR | Docs never lie mid-refactor |
| D0.2 | Stage vocabulary home | Code (`evals/assessment/l6_contract.py`) + `docs/architecture/pipeline-stages.md` | Code is source of truth |
| D1.1 | Shared kernel | New `src/core/` | `source_metadata.py` moves there |
| D1.2 | `components/` | Rename package → `nodes/` + plain file names | Importlib hack dies |
| D1.3 | Protocols | Per-domain homes; `di.py` imports canonical ones | Interim; `di.py` dies in P3 |
| D1.4 | `services/` | Fold into `evals/`; delete layer + `BaseService` | |
| D1.5 | Shims | Hard-delete all 5, fix callers in same PR | No deprecation period |
| D1.6 | `experiment_config` | Migrate in Phase 2 (not P1) | Keeps P1 pure |
| D1.7 | `hype.py` | File rename in P1; settings keys in P3 | |
| D2.1 | Ablation runners | `experiments/ablations/` package | |
| D2.2 | `chroma_store` split | Flat modules in `indexing/`; **delete** legacy JSON snapshot path | `migrate.py` stays |
| D2.3 | Orchestrator | **Class-based `AssessmentPipeline`** (follows from D3.2=B) | |
| D2.4 | Test mirroring | Top-level dirs mirroring `src/` packages only | |
| D2.5 | `convert_html` | Split `main()` from core in P2; setters die in P3 | |
| D3.1 | Ingestion unification | **(A) `rag/index.py` delegates to the Hamilton driver** | Parity gate mandatory |
| D3.2 | DI lane | **(B) Real constructor injection** from composition roots | `di.py` deleted; no `or get_*()` fallbacks |
| D3.3 | Setter channel | **Full kill**; explicit params everywhere | `rag/runtime_config.py` setters die |
| D3.4 | import-linter | Adopt; CI-enforced layer contract | Lands last (P3.4) |

## 3. Target architecture

### 3.1 Layering (enforced by import-linter in P3.4)

```
cli/  →  app/  →  usecases/  →  {rag, evals, experiments}  →  {ingestion, infra}  →  core/  →  config/
```

Rules:
- Dependencies point left-to-right only. No `infra → app`, no `ingestion → rag`, no `usecases → cli`.
- **Composition roots** (the only places that construct concrete dependencies):
  `app/factory.py` (server), `cli/*` (offline entrypoints), eval/experiment runner edges.
- Inside the graph: constructor/parameter injection only — no module-level `get_*()` fallbacks on
  the request path, no global mutable config setters.
- `config/` = static settings (yaml + pydantic) + `RuntimeState` runtime overlay. That's the whole
  config story after P3 (experiments YAML stays a separate, legitimate dialect).

### 3.2 Target tree (delta from today)

```
src/
├── config/          # unchanged (settings.py, paths.py, context.py)
├── core/            # NEW: source_metadata.py, exceptions.py (shared kernel; depends on nothing)
├── infra/           # llm/ + storage/ — no di.py after P3; depends only on core/, config/
├── ingestion/
│   ├── pipeline.py  # + run_ingagement() library entry (P3.2)
│   ├── nodes/       # RENAMED from components/: download.py parse.py chunk.py
│   │                #   enrich.py reference.py embedding.py (normal imports)
│   ├── steps/       # real implementations; chunk_text.py facade deleted (P1),
│   │                #   hype.py → hypothetical_questions.py; convert_html.py split (P2)
│   ├── indexing/    # store.py + hype_index.py + listing.py + factory.py (P2.3 split);
│   │                #   vector_store.py alias deleted (P1)
│   └── schemas/     # unchanged
├── rag/             # runtime/; index.py becomes thin delegate to run_ingestion() (P3.2);
│                    #   runtime_config.py cross-package setters deleted (P3.3)
├── evals/           # + artifact_service.py (from services/); assessment/ gets
│                    #   AssessmentPipeline class (P2.4); step_checks.py + pipeline_assessment.py
│                    #   shims deleted (P1); retrieval_eval.py becomes pure metrics (P2.2)
├── experiments/     # + ablations/ package (P2.2); experiment_config.py deleted (P2.1)
├── app/             # factory.py = composition root; routes/config.py stops poking steps (P3.3)
├── usecases/        # chat only (pipeline.py shim deleted P1)
└── cli/             # entrypoints only; ingest.py wraps run_ingestion() (P3.2)
```

Deleted outright: `services/`, `infra/di.py`, 5 compat shims, `experiment_config.py`,
`ingestion/components/` (renamed), legacy JSON snapshot path in `chroma_store.py`.

### 3.3 Canonical stage names (single vocabulary)

| Stage | node (P1) | step module | eval check | label |
|-------|-----------|-------------|------------|-------|
| download | `nodes/download.py` | `steps/download_web.py`, `steps/download_pdfs.py` | `checks/l0_download.py` | `L0 download` |
| parse | `nodes/parse.py` | `steps/convert_html.py`, `steps/load_pdfs.py`, `steps/load_markdown.py` | `checks/l1_html.py`, `checks/l2_pdf.py` | `L1 html` / `L2 pdf` |
| chunk | `nodes/chunk.py` | `steps/chunking/*` | `checks/l3_chunking.py` | `L3 chunking` |
| enrich | `nodes/enrich.py` | `steps/enrich_chunks.py` | (covered by L3/L4) | `L3 enrich` |
| reference | `nodes/reference.py` | `steps/load_reference_data.py` | `checks/l4_reference.py` | `L4 reference` |
| embedding | `nodes/embedding.py` | `indexing/embedding.py`, `steps/hypothetical_questions.py` | `checks/l5_index.py` | `L5 index` |

The L-numbering survives **only as output labels**; code identifiers use the plain stage names.
Source of truth: constants in `evals/checks/l6_contract.py`, mirrored in
`docs/architecture/pipeline-stages.md` (created in Phase 0).

---

## Phase 0 — Docs truth-sync (no code)

**P0.1 Patch `.planning/codebase/ARCHITECTURE.md`**
- Remove phantom `src/config/models/` entry.
- Fix the `infra/` boundary claim ("only depends on config/" is false: `file_chat_history_store.py:13`
  imports `app.exceptions` — mark as known violation, fixed in P1.7/P3).
- Fix `services/` dependency claim (actual: → `evals`, not rag/ingestion/config).
- Document the `components/` wrapper tier + importlib trick (and its P1 replacement).
- Add `src/source_metadata.py` to the module-boundaries tree (note: → `core/` in P1).
- List all 7 mounted routers; refresh line-count drift (settings.py ~224, not ~285).

**P0.2 Create the stage vocabulary**
- Add canonical stage constants to `evals/assessment/l6_contract.py` (table in §3.3).
- Create `docs/architecture/pipeline-stages.md` mirroring the table + one paragraph on HyPE vs HyDE
  (index-time hypothetical questions vs query-time hypothetical document).

**P0.3 Update `.planning/codebase/STRUCTURE.md` + `TESTING.md`**
- Reflect current reality only (Phase 0 does not pre-announce Phase 1–3 changes; each later PR
  updates docs itself).

**Done when:** every stale claim listed in the audit is fixed or explicitly marked as a known
violation with a pointer to its fix task. No code files touched.

---

## Phase 1 — Pure deletions & renames (low risk)

One branch `refactor/phase-1`, one PR per task (or task pairs). All changes are moves/renames/
re-points: behavior identical, coverage identical.

**P1.1 Create `src/core/`; move `source_metadata.py`**
- `git mv src/source_metadata.py src/core/source_metadata.py` (+ `src/core/__init__.py` with a
  curated re-export).
- Re-point importers: `ingestion/steps/{load_markdown,load_reference_data,load_pdfs}.py`,
  `ingestion/indexing/chroma_store.py`, `rag/formatting.py`,
  `tests/integration/test_source_metadata_pipeline.py`.

**P1.2 Rename `components/` → `nodes/` with plain names**
- `01_download.py→download.py`, `02_parse.py→parse.py`, `03_chunk.py→chunk.py`,
  `04_enrich.py→enrich.py`, `05_reference.py→reference.py`, `06_embedding.py→embedding.py`.
- Replace the `importlib.import_module` loop in `nodes/__init__.py` with normal imports; export an
  explicit `NODE_MODULES` list.
- `ingestion/pipeline.py:19`: import `NODE_MODULES` (public) instead of `_modules`.
- Update tests that used importlib: `tests/integration/test_dag_functional.py`, `tests/e2e/test_hamilton_pipeline.py`.

**P1.3 Dedupe protocols in `infra/di.py`**
- Delete `LLMClientProtocol`, `ChatHistoryStoreProtocol`, `VectorStoreProtocol` from `di.py`;
  import from `infra/llm/interfaces.py`, `infra/storage/interfaces.py`, `rag/protocols.py`.
- Add module docstring: "container scheduled for deletion in Phase 3 — do not extend".

**P1.4 Fold `services/` into `evals/`; delete the layer**
- `git mv src/services/evaluation_service.py src/evals/artifact_service.py`.
- Delete `services/base_service.py` + `services/__init__.py`.
- Re-point: `app/routes/evaluation.py`, related tests (search `EvaluationService`).

**P1.5 Delete the 5 compat shims (hard delete, per D1.5)**

| Shim | Re-point to | Known callers (verify with rg at execution) |
|------|-------------|----------------------------------------------|
| `usecases/pipeline.py` | `src.cli.ingest` (or drop the `run_pipeline` export) | `ingestion/__init__.py`, `usecases/__init__.py`, tests |
| `ingestion/indexing/vector_store.py` | `ingestion.indexing.chroma_store` | `evals/dataset_builder.py`, `evals/assessment/answer_eval.py`, `app/routes/documents.py`, `evals/checks/l3_chunking.py`, `infra/di.py`, tests (`test_chroma_store.py`, `test_l5_index_chroma.py`, integration tests). Also flip `indexing/__init__.py` to re-export `ChromaVectorStore`, not the legacy `VectorStore` alias |
| `ingestion/steps/chunk_text.py` | re-exports fold into `steps/chunking/__init__.py` | `rag/index.py`, `nodes/chunk.py` (post-P1.2), `evals/checks/l3_chunking.py`, `tests/unit/test_chunker.py` & friends |
| `evals/step_checks.py` | `evals.checks` | `evals/__init__.py`, tests |
| `evals/pipeline_assessment.py` | `evals.assessment` | `experiments/config.py`, `rag/runtime_config.py`, `scripts/manual/verify_tracing_improvements.py`, tests (`test_pipeline_assessment_smoke.py`, `test_runtime_config.py`) |

**P1.6 Rename `steps/hype.py` → `steps/hypothetical_questions.py`**
- File + symbol renames (`generate_hype_questions_for_chunks` stays or becomes
  `generate_hypothetical_questions_for_chunks`); re-point `rag/index.py`, nodes, tests.
- Settings keys (`settings.hyde.*`) are NOT touched here (P3.6).
- Note: the `ingestion → rag` import of `rag.hyde.generate_hypothetical_questions` is relocated in
  P3.1 (it needs the DI rework anyway). Do not fix here.

**P1.7 Kill the `infra → app` violation**
- Move `StorageError` (the only symbol infra needs) to `src/core/exceptions.py`;
  `app/exceptions.py` re-exports it temporarily; re-point
  `infra/storage/file_chat_history_store.py` and `usecases/chat.py` to `core`.

**Done when:** `pytest` green; `rg "from src.services|src.usecases.pipeline|step_checks|pipeline_assessment|components import _modules"` returns nothing in `src/`; coverage delta ≈ 0; docs (ARCHITECTURE.md boundaries, STRUCTURE.md tree) updated in the same PRs.

---

## Phase 2 — Structure moves (medium risk)

**P2.1 Migrate + delete deprecated `experiments/experiment_config.py`** (deferred from P1 per D1.6)
- Map real importers first (grep matched ~6 src + 4 test files; several are docstring mentions —
  verify): `scripts/run_variant_clean.py`, `src/experiments/run_addition.py`,
  `src/experiments/feature_addition_runner.py`, `app/routes/experiments.py` (verify), tests.
- Migrate onto `experiments/config.py` (414-line versioned loader); delete the 226-line deprecated
  module; fold/retire its dedicated tests.

**P2.2 Move ablation runners out of `evals/assessment/retrieval_eval.py` (lines ~473–831)**
- New `experiments/ablations/` package: `hype.py`, `keyword.py`, `reranking.py`, `diversity.py`
  (+ `__init__.py` re-exporting the public `run_*` families).
- `retrieval_eval.py` keeps only the metrics library (relevance grading, nDCG, `evaluate_retrieval`).
- Re-point: `cli/eval_pipeline.py`, `evals/assessment/orchestrator.py`,
  `experiments/feature_{ablation,addition}_runner.py`, `evals/assessment/__init__.py`, tests.

**P2.3 Split `ingestion/indexing/chroma_store.py` (1,028 lines)**
- `store.py` — `ChromaVectorStore` core: client management, CRUD, in-memory mirrors, BM25 upkeep.
- `hype_index.py` — hypothetical-question (HyPE) search + cache (`search_hypothetical_questions`, line ~745+).
- `listing.py` — `list_documents_paginated` + API-shaped DTOs (line ~791+).
- `factory.py` — signature-computed builder (from `ChromaVectorStoreFactory`, line ~880+).
- **Delete** the legacy JSON snapshot persistence path (`_persist_legacy_snapshot`, line ~171);
  `indexing/migrate.py` stays for old data dirs.
- Re-point the 10 `get_vector_store` callers (paths change only if desired; keep
  `chroma_store.py` as a thin re-export for one release of this phase, delete at phase end).

**P2.4 Decompose the orchestrator into `AssessmentPipeline` (class, per D3.2=B)**
- `evals/assessment/orchestrator.py`: split `_run_assessment_impl` (lines 115–608) into staged
  methods: dataset → step checks → retrieval → answer eval → thresholds → artifacts.
- Constructor takes the 7 currently-injected function deps as explicit typed parameters
  (real DI, ready for P3.1 composition).
- Keep module-level `run_assessment()` as the default-composition convenience for callers/tests.

**P2.5 Split `steps/convert_html.py`** — *executed as a no-op*
- Inspection showed `main(force)` is already a plain library function with a minimal
  `__main__` guard; the reusable core (`convert_html_to_md`) is separate. The module's
  real problems (module-level setters, mixed strategies/classification) are resolved by
  the P3.3 setter kill, which restructures this module anyway. No churn without benefit.

**P2.6 Mirror `tests/unit/` (and `tests/integration/`) to top-level package dirs**
- Pure `git mv`: `tests/unit/{app,rag,ingestion,evals,experiments,infra,config,usecases,cli}/`.
- Root `conftest.py` stays; no test-content changes.

**Done when:** `wc -l` shows no file > ~600 lines in `src/`; pytest green; coverage unchanged;
STRUCTURE.md + TESTING.md updated.

---

## Phase 3 — Architecture (higher risk; parity-gated)

**Execution order: P3.1 → P3.3 → P3.2 → P3.4.**
Rationale: DI rework first (it touches every constructor), then the config channel (explicit
params must exist before a single orchestration consumes them), then the Hamilton delegation
(rewrites `rag/index.py` against the new seams), then the import contract (asserts the end state).

**P3.1 Real constructor injection (D3.2=B)**
- `app/factory.py` becomes the composition root: construct `LLMClient`, `ChatHistoryStore`,
  `ChromaVectorStore` (via `indexing/factory.py` builder), stash on `app.state`; routes access via
  `Depends` accessors reading `app.state` (not a service locator).
- `usecases/chat.py`: remove `llm_client or get_client()` fallbacks (lines ~137, ~236); deps are
  required parameters (a small `ChatService` class is acceptable if it reduces param threading).
- Delete `infra/di.py` entirely (169 lines: container, `_ContainerProxy`, duplicated caches).
- Offline paths (CLI, evals, experiments, Hamilton nodes) construct deps at their own edge using
  the same builders — same lane, different root.
- Relocate `generate_hypothetical_questions` out of `rag/hyde.py` (to `core/` or `infra/llm/`) so
  `ingestion` stops importing `rag`; it now receives the client as a parameter.

**P3.3 Full kill of the setter channel (D3.3)**
- Delete the cross-package setters in `rag/runtime_config.py` (`apply_runtime_config` pushing into
  `ingestion/steps/*` globals); `convert_html` strategy/mode globals from P2.5 go too.
- Ingestion steps take explicit params sourced from a config snapshot (`RuntimeState` read at call
  time or passed down from the composition root).
- `app/routes/config.py`: stop importing `ingestion.steps.*` directly; read/write `RuntimeState`
  through a small usecase facade.
- (P3.6, include here) `settings.hyde.*` → `settings.hype.*` via pydantic alias + deprecation
  warning; update `config/settings.yaml`, `.env.example`, docs.

**P3.2 Hamilton delegation (D3.1=A)**
- `ingestion/pipeline.py`: expose `run_ingestion(config) -> IngestionResult` — a library entry
  wrapping a **cached** Hamilton driver (cache keyed by config signature, mirroring the existing
  factory pattern).
- `cli/ingest.py` becomes an argparse wrapper around `run_ingestion`.
- `rag/index.py`: `initialize_vector_store_async` delegates via
  `asyncio.to_thread(run_ingestion, cfg_from_runtime_state)`; delete
  `_build_index_from_sources`; remove the `materialize_html` param (force-reconvert becomes a
  config flag consumed inside the pipeline); preserve the signature-check skip logic and
  `get_runtime_status`.
- **Parity gate (mandatory before merge):**
  1. Baseline on `main`: run the assessment pipeline (`python -m src.cli.eval_pipeline` /
     `run_assessment`) on the fixed eval dataset; save metrics JSON.
  2. Rerun on the branch with identical config/seed.
  3. Gate: deterministic checks (L0–L5) and retrieval metrics (nDCG/recall) must match exactly;
     LLM-judged answer metrics within judge-noise tolerance.
  4. Attach both JSONs to the PR.

**P3.4 import-linter contract (D3.4)**
- Add `import-linter` to dev deps; contract:
  `cli > app > usecases > {rag, evals, experiments} > {ingestion, infra} > core > config`,
  plus explicit forbids: `infra → app`, `ingestion → rag`, `usecases → cli`.
- Wire into CI (`ci.yml`) as a required step; optionally pre-commit.

**Done when:** contract passes on `main`; parity report attached; ARCHITECTURE.md rewritten to
describe the final state (composition roots, single ingestion path, config layers).

---

## 4. Cross-phase policies

- **Branching:** `refactor/phase-N` branches, merged sequentially. Tasks within a phase are
  independent PRs (dependencies noted inline: P1.2 before P1.5's chunk_text re-point; P3 order fixed).
- **Verification ladder:** P0 docs-only review · P1/P2 lint+mypy+pytest+coverage-delta≈0 ·
  P3 adds the parity gate.
- **Rollback:** every task is a git revert; no data migrations except the (already-existing)
  legacy-snapshot → Chroma path which `migrate.py` covers.
- **Docs:** each PR updates the affected `.planning/codebase/*` doc + `docs/architecture/*` in the
  same change (D0.1).

## 5. Risk register

| Risk | Phase | Mitigation |
|------|-------|------------|
| Shim re-point misses a dynamic/lazy import | P1.5 | rg for module names (not just `from x`), run full pytest incl. e2e marker subset |
| `chroma_store` split breaks signature-cache invalidation | P2.3 | Keep factory logic byte-identical when moving; integration tests `test_chroma_store.py` |
| Hamilton driver too heavy to build in server lifespan | P3.2 | Driver cached per config signature; measure lifespan startup time before/after |
| Runtime index rebuild semantics differ (skip logic, partial features) | P3.2 | Parity gate + preserve signature-check code path verbatim |
| LLM-judge noise masks a real regression | P3.2 | Gate primarily on deterministic L0–L5 + retrieval metrics |
| Setter removal changes default behavior of HTML/PDF steps | P3.3 | Defaults snapshot test before/after (same inputs → same extractor choices) |

## 6. Explicitly out of scope / deferred

- `frontend/` (SvelteKit) structure — separate effort.
- `get_full_context` loading reference PDFs synchronously at request time (runtime.py ~455) —
  noted in audit; candidate follow-up after P3.
- Sync/async duplication in `rag/runtime.py` (~150 parallel lines) — follow-up after P3.
- Consolidating schema file *names* (`schemas.py` vs `trace_models.py` vs `*_models.py`) — cosmetic.
- Any behavioral improvements to retrieval quality — this roadmap is behavior-preserving by design.
