# B1 continuation 2 — collection build metadata + backfill (slice report)

Scope: offline code slice "B1 continuation 2" for the D11 materialization. All four owned
files delivered; nothing outside ownership touched; no tests executed, no network, no REPL
imports. Static checks only (ruff/mypy/py_compile) on owned files.

## Files changed and why

### 1. `src/ingestion/indexing/store.py` (modified — additions only, 0 deletions)
- Added module-level `build_collection_build_metadata(source_digest: str | None = None) -> dict[str, Any]`
  returning all 22 `_REQUIRED_BUILD_METADATA` keys from live typed configuration:
  - `embedding_model` / `embedding_batch_size` ← `settings.llm.*`.
  - `semantic_weight` / `keyword_weight` / `boost_weight` ← `get_vector_store_runtime_config()`
    (the resolved vector-store runtime config; see Contradiction 1 below — `settings.retrieval`
    has no weight fields).
  - ingestion extractor/classification/chunking flags ← `settings.ingestion.*`.
  - HyPE ← `settings.hype.{enabled,sample_rate,max_chunks,questions_per_chunk}`;
    keyword/summaries ← `settings.enrichment.*`.
  - `source_chunk_configs` ← `json.dumps(get_source_chunk_configs(), ensure_ascii=False,
    sort_keys=True)` — the resolved chunking configuration actually in effect
    (`src/ingestion/steps/chunking/config.py`: chunk_size/chunk_overlap/strategy/
    min_chunk_size/embedding_model per source type), serialized as a JSON string because
    Chroma metadata values must be scalars (validator accepts exactly that encoding).
  - `source_snapshot_sha256` ← `source_digest` verbatim when given; otherwise
    `_corpus_source_digest(DATA_RAW_DIR)` (digest helper still raises `ValueError` with
    fixed reason enums on unverifiable trees). **2026-10-24 closure correction:** after
    gate integration, the outer helper `build_collection_build_metadata()` **returns
    `None`** (store created without collection metadata, debug log) when the corpus is
    unavailable, instead of raising at every store construction — the offline gate's
    isolated workspace binds an empty `data/`, which broke real store tests. The D11
    builder fails closed on metadata-less stores, so honesty is preserved.
  - Function-local imports for `factory.get_vector_store_runtime_config` (factory imports
    store → import cycle) and `steps.chunking.config.get_source_chunk_configs` (package
    `__init__` pulls the chunker core). No digest cache: hashing runs once per store init
    (the factory singleton means stores are rarely constructed), per the brief's
    "once per store init is acceptable".
- Added `_corpus_source_digest(directory) -> str`: byte-compatible local mirror of the
  `source-tree-v1` digest in `src.evals.assessment.reporting.content_directory_provenance`
  (same prefix, sorted `os.fsencode` relative paths, 8-byte length-prefixed paths,
  per-file st_size + SHA-256, regular files only, symlink/non-regular/empty/limits fail
  closed with the same reason enums and the same 20_000/10_000/512 MiB limits). Required
  because the layered-architecture contract forbids `src.ingestion → src.evals` (see
  Contradiction 2).
- Attached `metadata=build_collection_build_metadata()` at ALL THREE
  `get_or_create_collection` sites (injected-client, `persist_directory`, and
  server/default-persist branches), lines ~292/~305/~328 post-change. chromadb 1.5.5
  **ignores metadata for existing collections**, so this is inert for already-materialized
  stores and only stamps newly created ones.

### 2. `scripts/manual/backfill_d11_collection_metadata.py` (new)
- CLI: `--chroma-dir` (default `data/chroma-d11`), `--collection` (default `medical_docs`),
  `--source-digest` (optional override; default digests the configured raw data dir).
- Offline/local-only: `chromadb.PersistentClient(path=chroma_dir)`; refuses a missing
  directory; `client.get_collection(name=..., embedding_function=None)`.
- Idempotent: computes the payload via the store helper; if every required key already
  equals the payload (after parsing `source_chunk_configs` JSON on both sides) → prints
  `already up to date`, exit 0.
- Write path: `collection.modify(metadata=payload)` then re-reads via a fresh
  `get_collection` and verifies all required keys present; prints a one-line summary with
  added key NAMES only (never values/contents). Fail closed: missing collection, chroma
  API errors, digest unavailability, or verification failure → stderr + exit 1, never a
  partial success claim.
- Conventions match `build_labqar_reference_csv.py`/`build_d11_frozen_identity.py`:
  `main(argv: Sequence[str] | None) -> int`, `raise SystemExit(main())`, PROJECT_ROOT
  sys.path insertion, lazy imports.

### 3. `tests/unit/ingestion/test_collection_build_metadata.py` (new)
Offline unit tests; the digest-mirror test pins byte compatibility against
`content_directory_provenance` on synthetic tmp trees:
- `test_payload_contains_every_required_key_with_valid_types` — required-key subset; bools
  are bool; the five identity strings non-empty; weights finite non-bool numbers; batch
  size int ≥ 1; `source_chunk_configs` is a str.
- `test_payload_values_come_from_live_typed_configuration` — every value equals the live
  `settings.*` field and the weights equal `get_vector_store_runtime_config()`.
- `test_source_chunk_configs_round_trips_and_passes_credential_guard` — JSON round-trips
  to a dict of dicts carrying chunk_size/chunk_overlap/strategy; passes the validator's
  own `_reject_credentials` (payload and parsed configs); encoding is exactly
  `json.dumps(..., sort_keys=True)` canonical form.
- `test_payload_is_deterministic` — two calls with the same explicit digest are equal.
- `test_explicit_source_digest_is_honored_verbatim` (parametrized a/0/f ×64) — digest
  recorded verbatim.
- `test_default_source_digest_falls_back_to_corpus_digest` — None →
  `_corpus_source_digest` result (monkeypatched).
- `test_corpus_source_digest_matches_d11_provenance_byte_for_byte` — mirror digest ==
  `content_directory_provenance` digest on a nested synthetic tree.
- `test_corpus_source_digest_fails_closed_on_empty_or_unavailable_trees` — empty/missing/
  symlinked trees raise `ValueError` with the fixed reason enums.

### 4. `tests/unit/manual/test_backfill_d11_collection_metadata.py` (new)
Importlib-loaded script driven against real local tmp Chroma stores with 2 synthetic
vector embeddings (established `test_d11_identity_builder.py` convention):
- `test_backfill_attaches_required_metadata_and_keeps_embeddings` — exit 0;
  `_REQUIRED_BUILD_METADATA` subset holds; `source_snapshot_sha256` == supplied digest;
  `collection.count()` still 2; "keys added" summary printed.
- `test_second_run_reports_already_up_to_date` — second run exit 0 with
  "already up to date".
- `test_missing_collection_fails_closed` — empty local store → exit 1, stderr message,
  never "already up to date".

## Chroma API call confirmed (chromadb 1.5.5, installed package)
`chromadb.api.models.Collection.Collection.modify(self, name=None,
metadata: Optional[Dict[str, Any]] = None, configuration=None)` → exact call used:
`collection.modify(metadata=payload)`. `_validate_modify_request` → `validate_metadata`
allows str/bool/int/float (and list/SparseVector) values; our payload is str/bool/int/float
only. `get_or_create_collection` docstring: "If the collection already exists, the metadata
provided is ignored." — creation-time attach cannot repair the existing D11 collection,
which is why the backfill uses `modify`.

## Deliberately not changed
- `src/evals/index_snapshot.py`, factory, runtime_config, migrate.py, pyproject, lockfiles,
  and every other pre-existing dirty file (preserved byte-for-byte).
- `_apply_index_metadata` / `set_index_metadata` overwrite semantics (existing behavior;
  see Residual risk 3).
- No digest caching, no new abstractions/registries.

## Contradictions with the brief (resolved, flagged for parent)
1. **Weights source**: brief said `settings.retrieval.*`; `RetrievalConfig` has **no**
   weight fields (verified). The live source the runtime config actually uses is the
   vector-store runtime config; the helper reads `get_vector_store_runtime_config()`
   (factory-normalized; defaults 0.6/0.2/0.2 — the same fallbacks as `runtime_config.py`
   and `factory.py`, never invented here). Consequence: stores constructed directly with
   explicit `semantic_weight=` kwargs that differ from the factory runtime config will
   record the runtime-config values in metadata (signature is fixed to `source_digest`
   by the brief, so per-instance weights cannot flow in).
2. **Corpus digest source**: brief said to reuse `content_directory_provenance` from
   `src.evals.assessment.reporting`; the import-linter layers contract
   (`pyproject.toml [tool.importlinter]`: `src.ingestion` sits **below** `src.evals`)
   forbids that import and `lint-imports` runs in pre-commit. Implemented a
   byte-compatible local mirror (`_corpus_source_digest`) instead, pinned to the
   provenance source by a unit test. Known differences (documented in the docstring):
   no post-hash re-stat (mid-hash mutation not detected locally — the D11 builder
   re-derives its own full provenance separately), and file opens do not use
   O_NOFOLLOW. Parent may prefer relocating the provenance helper to `src.core` and
   deleting the mirror as follow-up.

## Residual risks
1. Store init now raises `ValueError` when `data/raw` is missing/symlinked/empty/oversized
   (fail-closed provenance). Environments constructing `ChromaVectorStore` without a valid
   raw tree will fail at init; `data/raw` exists in this repo (121 files, 31 MB).
2. Experiment-built stores: factory-passed `index_metadata` still overwrites collection
   metadata at init (`_apply_index_metadata`) and that dict lacks
   `source_snapshot_sha256` — pre-existing behavior, unchanged here; such indexes would
   still fail the snapshot provenance check.
3. Backfill `modify` replaces the whole metadata dict (chroma semantics). Idempotency
   compares required keys only, so a collection carrying extra keys alongside all required
   values reports "already up to date" and is not rewritten (avoids destroying extra
   metadata). If extra keys coexist with a *changed* required value, the backfill rewrites
   and the extra keys are dropped — inherent to chroma's replace semantics.
4. `source_digest` values are honored verbatim (per brief); a malformed digest passes
   through and would only fail later at `_validate_build_spec` (64-hex check).
5. Parent-owned integration tests construct `ChromaVectorStore` heavily; each fresh store
   init now hashes `data/raw` (no cache). Measured tree ≈ 31 MB; acceptable per brief but
   visible in suite duration if many distinct store instances are built.

## Commands run (static only, owned files)
- `.venv/bin/ruff check` on all four files → "All checks passed!"
- `.venv/bin/mypy src/ingestion/indexing/store.py tests/unit/ingestion/test_collection_build_metadata.py tests/unit/manual/test_backfill_d11_collection_metadata.py` → "Success: no issues found in 3 source files" (scripts/ is outside mypy's configured `files`)
- `.venv/bin/python -m py_compile` on all four files → OK
- Read-only inspection of installed chromadb 1.5.5 (`inspect.signature/source`) and `git status/diff` (no checkout/reset/stash/clean, no commits).

No tests were executed; no application imports were run; no network access.
