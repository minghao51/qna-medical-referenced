# Maintainability review: verified findings and corrections

Status: source-verified planning evidence, not a production certification.
Baseline: `66cb168` on `main`. This review makes no application changes.
Companion: [implementation specification](maintainability-implementation-plan.md).

## Reproduction and limitations

Executed during this verification:

```sh
uv run --frozen python -m pytest --no-cov -q \
  -m 'not slow and not live_api and not live_openrouter and not e2e_real_apis and not deepeval and not network'
(cd frontend && bunx --no-install playwright test --list)
```

Results: **2,284 passed, 2 skipped, 117 deselected, 4 warnings in 51.78s**;
Playwright: **58 tests in 6 files**. Listing does not launch a browser or prove
those tests pass. Earlier local coverage evidence was 82%; coverage was not
remeasured here. Earlier static/build results are historical evidence, not a new
run. Dependency/network/provider behavior and hosted deployment were not tested.
A `RequestsDependencyWarning` was emitted; investigate installed distribution
compatibility before treating it as a vulnerability or changing constraints.

Source references below are anchored to this baseline; use symbols after moves.

## Confirmed findings

| ID | Evidence | Assessment |
|---|---|---|
| V01 | `src/evals/assessment/orchestrator.py`: 2,930 lines; `AssessmentPipeline`, `_run_attempt`, `_resolve_config`, `_run_replay`, `_finalize` | High comprehension/change cost. Size is not proof of incorrectness. Preserve existing dependency-injection/monkeypatch seams during extraction. |
| V02 | `store.py`: 1,073 lines; `retrieval_eval.py`: 993; `telemetry.py`: 985; `dataset_builder.py`: 820 | Candidate cohesion reviews, not orders to split every file to an arbitrary limit. |
| V03 | `pyproject.toml` pytest `addopts`; `.github/workflows/ci.yml:56–94` | Coverage is always enabled locally. Unit job selects only `not slow`; integration uses a longer exclusion expression. Selection and reporting are inconsistent. |
| V04 | `tests/conftest.py:103–126`, `if LIVE_QWEN_ENABLED: return` | Enabling Qwen opt-in bypasses independent real-API/OpenRouter collection skip gates. Setup prechecks do not restore those opt-in boundaries. This deserves a regression test and early repair. |
| V05 | `tests/unit/evals/test_eval_error_handling.py:22,209,224` | Module-wide live marks also hide two offline tests. Several assertions accept any list or conditionally assert only if nonempty; `test_artifact_write_failure` only constructs a model, never writes. Marking alone did not make tests meaningful. |
| V06 | `tests/unit/ingestion/test_ingestion_error_handling.py:41–57` | Permanently skipped incomplete retry test. Replace with actual boundary behavior or remove the stub with an explicit coverage rationale. |
| V07 | `pyproject.toml` has no `[project.scripts]` or explicit build system; no root Makefile/justfile/Taskfile | Long commands are a discoverability issue. A task runner can solve this without introducing package installation or a new tool requirement. |
| V08 | `frontend/package.json`, `frontend/tests/*`, `frontend/src/routes/+page.svelte:158–201` | No configured unit-test runner; 58 Playwright tests exist. SSE parser is embedded in a page, accepts only `data: ` lines, logs malformed JSON, and does not require terminal `done` before EOF. |
| V09 | `src/config/settings.py::settings_customise_sources`, YAML, Compose environment | Multiple default declarations deserve parity tests. They are not four equal runtime authorities: model fallback < YAML < dotenv < environment < init arguments. Secret example prose is not another runtime source. |
| V10 | `docs/README.md`, `.planning/codebase/*`, `docs/architecture/*` | 104 markdown docs; index contains 23 markdown links **plus 19 backtick markdown references**. Chronological handoffs and overlapping architecture guides make current truth hard to find. |
| V11 | `.planning/codebase/ARCHITECTURE.md` | Still names deleted `chroma_store.py` and describes orchestrator as ~645 lines. Structural overview needs truth-sync, not just more handoffs. |
| V12 | `Dockerfile` (no USER), `docker-compose.yml:7–9` | Backend runs as root; Compose overlays image source with host `./src` while selecting production environment. Separate dev convenience from deployment reference; bind-mount ownership must be addressed before non-root switch. |
| V13 | `src/app/routes/evaluation.py::_validate_run_dir`; `artifact_service.py:188–202,427–431,608–625` | Regex accepts `.` and `..`; service joins unconfined paths and trusts latest-pointer content. Directory/artifact symlinks are not rejected. Fix the service boundary, not only route regex. API reads fixed artifact names, not arbitrary requested filenames; remote exploitability depends on routing normalization and filesystem layout. |
| V14 | `artifact_service.py:578–592`; `evaluation.py::get_l6_records` | L6 endpoint accepts unbounded/negative limit; service parses and retains all rows before slicing. Exact `total_count` is part of current contract; simply breaking at limit would silently change it. |
| V15 | `src/app/middleware/auth.py`; `routes/config.py`, `evaluation.py`, `documents.py`, `experiments.py`; `security.py::validate_security_configuration` | No route role authorization. Production startup requires keys; development without keys lets document/experiment routes through, while config/evaluation additionally demand auth state. Do not describe all routes as unconditionally authenticated. Roles/admin remain owner-deferred. |
| V16 | `src/app/middleware/rate_limit.py:174–190`; no body-size guard in inspected app middleware | 429 payload lacks standard error envelope; reset header is relative seconds/zero. A global body limit is absent in app code; external proxy limits are deployment-dependent and unverified. |
| V17 | `store.py:353–379,466–480`; `rag/index.py:181–216` | Explicit metadata overlay can persist on construction when it differs. Default empty overlay adopts existing metadata and need not write. Cache uses runtime signature/store identity, not metadata revision. Strict read-only Chroma support is not demonstrated. |
| V18 | `scripts/manual/r2_sync.py:290–305,321–339` | Verify hashes equal-size objects, but different sizes within 100 bytes count as OK without hashing. Transfer skip rules also use tolerance and do not repair equal-size drift. This is not exact frozen-artifact integrity. |
| V19 | `.github/workflows/ci.yml:121–135` | Dependency audit runs `uvx pip-audit --strict` with no project sync/export/input. It does not explicitly audit the project lock; tool-environment results are not project-dependency evidence. |
| V20 | `pyproject.toml` import-linter config | Architecture checks exist and pass historically, with explicit allowed eval/experiment/RAG edges. Cycles/exemptions need call-site analysis; globally renaming runners/pipelines is not a remedy. |
| V21 | `docs/testing/backend-tests.md` targeted commands and test-area list | Many examples still point to pre-mirroring test paths. Its ~50-second default command still inherits coverage, so timing claim is inconsistent. |

## Corrections to the earlier review

1. **Not 10 frontend tests:** Playwright currently collects 58. Absence of a unit
   runner is confirmed; total absence of frontend coverage is not.
2. **Not integration without coverage:** pytest defaults include `--cov=src`.
   Parsing current CLI arguments yields integration sources `['src']`; unit
   sources include `src` **plus** the four appended coverage arguments. Thus the
   earlier claim that CI measures only four modules is incorrect. The defensible
   concerns are duplicated sources, inconsistent selection, and separate reports.
3. **Not 23 indexed documents:** 23 counted only markdown-link syntax. The index
   also has 19 backtick references, with duplicates possible. Measure unique valid
   destinations before claiming an unindexed count.
4. **Not implicit dependency upgrades:** CI uses `uv sync --frozen` and frontend
   frozen lock install. Open-ended constraints matter at a deliberate lock
   refresh, not every install. Blind upper pins can worsen maintenance.
5. **Not a mandatory rename:** root `experiments/` is configuration/artifacts;
   `src/experiments/` is Python code. Clarify the distinction before moving paths
   embedded in scripts, reports, and image builds.
6. **Not mandatory unused-marker deletion:** reserved `network`/`serial` markers
   cost little. Correct their definitions and intended use first.
7. **Not archive/delete legacy data:** no data migration or cleanup is approved.
   Document legacy `data/chroma`; never move it as a QoL task.
8. **Not a read-only guarantee:** avoiding `collection.modify` is narrower than
   booting an embedded Chroma client on a read-only filesystem.
9. **Not proven universal timeout behavior:** prior investigation reported a
   surviving child holding a pipe, but this verification did not reproduce that
   process tree. GNU timeout behavior depends on process groups/wrappers. Live
   network work was the demonstrated runtime cause; piping to tail hides progress.
   A file redirect alone does not fix process-tree termination.
10. **No defensible B+ or day estimates:** passing tests measure regressions,
    not medical safety, benchmark validity, deployed security, or total remaining
    effort. Use staged acceptance evidence instead of a grade or unsupported ETA.

## New safety boundary for implementers

Planning is not approval for provider calls, new dependencies, benchmark/model
changes, exports, data backfill/cleanup, admin pages, or role policy. Keep existing
migration decision gates. All implementation phases below require the normal
plan/approval workflow; gated phases require a specific additional decision.
