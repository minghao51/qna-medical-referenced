# B1 offline repair round — Luna P2/P3 findings (slice report)

Scope: offline repair round for slice "B1" in this repository. All five repairs delivered;
nothing outside the granted file ownership touched; no tests executed, no network, no REPL
project imports. Static checks only (`.venv/bin/ruff check`, `.venv/bin/mypy`,
`.venv/bin/python -m py_compile`) run on the owned files listed below — all green.

## Files changed and why

### 1. `scripts/manual/build_labqar_reference_csv.py` (Repair 1)
- New fail-closed fallback contract for Set_2 `reference_range` bounds. Added
  `_validated_bound(path, record_id, raw) -> int | float | None`: returns `None` for a
  missing (null) bound; a present bound that is a non-numeric type (str/bool/list, …)
  raises `LabQarBuildError("... has non-numeric reference_range bounds")`; a present
  bound that is a non-finite float (NaN/Infinity, via `math.isfinite`, with
  `OverflowError` treated as non-finite for oversized ints) raises
  `LabQarBuildError("... has non-finite reference_range bounds")`.
- `build_rows` now falls back to the Set_1 answer bounds ONLY when at least one bound is
  None and every present bound validated as finite; both bounds None → fallback
  (unchanged); unparseable Set_1 answer → still skipped + counted. The `lower > upper`
  check is unchanged and still runs after fallback. The old bug — a single non-numeric
  bound (e.g. `lower="abc"`, `upper=None`) silently falling back — is fixed (fail closed).
- Module docstring updated to describe the new contract. Added `import math`.

### 2. `tests/unit/manual/test_build_labqar_reference_csv.py` (Repair 1)
- Kept `test_fails_closed_without_partial_output_on_non_numeric_bounds` (lower="abc",
  upper=None → exit != 0, no partial output) — it now actually holds under the fixed script.
- Added `test_fails_closed_without_partial_output_on_non_finite_bound` — lower=NaN,
  upper=None with parseable Set_1 answer "66-83" must exit != 0 and leave no output/tmp file.
- Added `test_falls_back_when_one_bound_missing_and_other_finite` — lower=None,
  upper=83.0 with parseable Set_1 answer exits 0 and renders the "66-83" fallback row.
- Both-bounds-None fallback with parseable answer → exit 0 was already covered by the
  existing `test_writes_exact_header_and_rendered_rows` (record 3 uses null/null bounds
  and asserts the "66-83" fallback row); deliberately not duplicated.

### 3. `tests/unit/ingestion/test_download_web_groups.py` (Repair 2, Luna P2-2)
- `test_main_iterates_every_configured_group` rewritten from source-string inspection
  (which asserted a loop shape `main()` no longer has) to a behavioral test: monkeypatches
  `download_web.download_group` with an async recorder capturing `(group, timeout)`, runs
  `dw.main()` via `asyncio.run`, and asserts: recorded groups == `list(DOWNLOAD_GROUPS)`
  in order; "moh" present; `international_guidelines` got timeout=60; every other group got
  30. Kept the label/timeout map assertions (`_GROUP_LOG_LABELS` keys == DOWNLOAD_GROUPS,
  `_GROUP_TIMEOUTS["international_guidelines"] == 60`). `main()`'s
  `_invalidate_content_hash_index()` call and directory listing are safe offline (downloads
  are stubbed, no manifest writes on this path). Removed the now-unused `import inspect`;
  added `import asyncio` / `import pytest`.

### 4. `src/evals/index_snapshot.py` — `_reject_credentials` (Repair 3, Luna P2-3)
- Hardened the string rule: leading whitespace is stripped (`lstrip()`) before the
  anchored scheme-prefix test, and the WHOLE string is scanned with
  `_URL_SPAN.finditer` (new module-level `re` patterns `_SCHEME_PREFIX` and `_URL_SPAN`,
  same anchored scheme charset plus `\S+` body) so every embedded scheme-anchored URL span
  gets the `urlsplit` userinfo/query/fragment check. This catches
  `" https://user:pass@host/path?token=x"` and prose-embedded credential URLs, while prose
  whose spans carry no query/fragment (e.g. "See https://example.com/x and is it useful?
  Yes #indeed") still passes because only scheme-anchored spans are ever urlsplit'ed.
- Scheme-prefixed strings keep the old whole-string parse (the stripped string is checked
  first) in addition to the span scan, so no prior reject regresses.

### 5. `tests/unit/evals/test_snapshot_url_guard.py` (Repair 3)
- Added parametrized `test_rejects_padded_or_embedded_url_spans` with:
  " https://user:pass@host/path?token=x" (leading whitespace),
  "See https://user:pass@host/path for details" (prose-embedded userinfo),
  "x https://host/p?q=1" (prose-embedded query) — all must raise `SnapshotError`.
- All existing accepts/rejects left untouched and still valid (prose accept verified by
  trace: its only span is "https://example.com/x", no query/fragment).

### 6. `scripts/manual/backfill_d11_collection_metadata.py` (Repair 4, Luna P2-4, P2-6, P3-7)
- Removed the `--source-digest` CLI override entirely; the payload is now always
  `build_collection_build_metadata()` with the digest computed from the configured raw
  corpus. A `None` payload (unavailable corpus digest) fails closed with the fixed stderr
  label "error: backfill failed: corpus digest unavailable" and exit 1.
- Preserve unrelated existing metadata: `collection.modify(metadata={**raw_existing,
  **payload})` — Chroma's modify() replaces the whole mapping, so the merge is explicit;
  existing keys not in the payload survive, payload wins conflicts.
- Sanitized stderr: all raw exception interpolations replaced with fixed labels —
  "backfill failed: collection unavailable", "backfill failed: metadata write failed",
  "backfill failed: corpus digest unavailable". No exception bodies are ever printed
  (the docstring claim is now true). Kept the chroma-dir-not-found message (a user-supplied
  CLI path, not exception internals) and the required-key-names verification message
  (docstring explicitly allows metadata key names).

### 7. `tests/unit/manual/test_backfill_d11_collection_metadata.py` (Repair 4)
- `_backfill_args` no longer passes `--source-digest`; new helpers `_make_corpus` +
  `_use_synthetic_corpus` monkeypatch `src.ingestion.indexing.store.DATA_RAW_DIR` onto a
  tmp corpus and return its `_corpus_source_digest` so tests never read the real `data/`.
- `test_backfill_attaches_required_metadata_and_keeps_embeddings` now asserts
  `metadata["source_snapshot_sha256"] == expected_digest` (computed from the synthetic
  corpus) instead of the old override literal.
- `test_second_run_reports_already_up_to_date` updated for the patched corpus.
- Added `test_backfill_preserves_unrelated_existing_metadata_keys` — a collection
  pre-seeded with `{"custom_note": "keep-me"}` keeps that key after backfill while all
  required keys (and the corpus digest) are attached.
- Added `test_missing_corpus_digest_fails_closed` — unavailable corpus → exit 1, fixed
  label "corpus digest unavailable", and no internal reason (e.g. "source_tree") leaks.
- `test_missing_collection_fails_closed` updated: corpus patched, asserts the fixed
  "collection unavailable" label.

### 8. `scripts/manual/build_d11_frozen_identity.py` (Repair 5, Luna P2-4 builder cross-check)
- New small pure helper `index_identity_with_provenance_cross_check(corpus_identity,
  index_identity)`: an already-unverified index identity passes through unchanged; a
  verified one whose captured build-spec `source_snapshot_sha256` differs from the
  independently computed corpus `content_sha256` (including an unavailable/None corpus
  digest, which cannot confirm provenance) is downgraded to
  `unverified_index_identity("index_source_provenance_mismatch")` — never crashes,
  embedding/corpus blocks untouched.
- `build_output_document` (where the final output document is assembled) now runs the
  index identity through this helper; byte-determinism of output is preserved (helper
  returns `dict(index_identity)` verbatim on pass-through/match; `serialize_output`
  unchanged).

### 9. `tests/unit/evals/test_d11_identity_builder.py` (Repair 5)
- `_verified_document` fixture corpus digest aligned "c"*64 → "b"*64 so it matches the
  fixture capture's `source_snapshot_sha256` and stays genuinely verified under the new
  cross-check.
- Added `test_output_document_downgrades_index_identity_on_provenance_mismatch` — corpus
  "c"*64 vs captured "b"*64 → index identity unverified with reason
  "index_source_provenance_mismatch", all identity fields None, embedding/corpus blocks
  unchanged.
- Added `test_output_document_keeps_verified_index_identity_on_matching_provenance` —
  matching digests → index identity passes through verified unchanged.
- Added `test_provenance_cross_check_downgrades_on_missing_corpus_digest_and_passes_unverified`
  — a verified index identity with `content_sha256=None` corpus is downgraded with the
  fixed reason; an already-unverified index identity passes through with its original reason.

## Deliberately not changed
- `src/ingestion/steps/download_web.py` (parent-dirty; Repair 2 is test-only).
- `src/ingestion/indexing/store.py` (`build_collection_build_metadata` signature keeps its
  optional `source_digest` for other callers, e.g. test_collection_build_metadata.py).
- Both-bounds-None fallback test (already covered; not duplicated).
- All other dirty working-tree files byte-for-byte preserved (verified via `git status`
  before/after: identical dirty set outside ownership).

## Ownership / commands confirmation
- Owned files touched: the 9 files listed above. No other file created or modified; no
  commits; no dependency or lockfile changes.
- Commands run (static only, on owned files): `.venv/bin/ruff check <owned files>` (pass),
  `.venv/bin/mypy <owned files>` (pass, incl. the three scripts explicitly),
  `.venv/bin/python -m py_compile <three scripts>` (pass). No pytest, no application
  imports, no network.

## Contradictions / residual risks
- The brief gave no explicit report path; this file follows the established slice-report
  convention in `docs/plans/migration/` (new file; parent may move or delete it).
- Repair 5 judgment call: an unavailable corpus digest (content_sha256 None) also
  downgrades the verified index identity, since the brief requires comparison against the
  "independently computed corpus content_sha256" and the script's contract is to never
  assert unconfirmable provenance. Mismatch-only semantics would leave a verified record
  unconfirmed when the corpus is unreadable.
- `test_missing_corpus_digest_fails_closed` relies on monkeypatching
  `src.ingestion.indexing.store.DATA_RAW_DIR` (a module-global import in store.py); if the
  parent later changes that import style, the test helper needs the same update.
- The existing `test_fails_closed_without_partial_output_on_non_numeric_bounds` asserted
  exit != 0 for a case the pre-repair script actually exited 0 on (lower="abc", upper=None
  fell back); it now genuinely holds. No contradiction remains.
