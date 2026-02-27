# Pipeline Quality Assessment Plan (Implemented Spec)

This document captures the approved execution plan for adding comprehensive quality assessment across the ingestion and RAG pipeline.

## Scope

- L0 download audit (post-download inventory/content quality)
- L1 HTML to Markdown quality checks
- L2 PDF extraction quality checks
- L3 chunking quality checks
- L4 reference CSV quality checks
- L5 index/embedding integrity checks
- L6 retrieval quality + optional answer-generation judging
- Hybrid dataset strategy (deterministic fixture + optional Gemini synthetic questions)
- Preserve all generated evaluation artifacts under `data/evals/<timestamp>_<slug>/`

## Deliverables

- `src/cli/eval_pipeline.py`
- `src/evals/*` evaluation package
- `tests/test_eval_*.py`
- Versioned evaluation artifacts and summary report

## CLI

`uv run python -m src.cli.eval_pipeline`

Supported args:
- `--artifact-dir` (default `data/evals`)
- `--name`
- `--dataset-path`
- `--top-k` (default `5`)
- `--max-synthetic-questions` (default `40`)
- `--disable-llm-generation`
- `--disable-llm-judging`
- `--include-answer-eval`
- `--sample-docs-per-source-type` (default `10`)
- `--seed` (default `42`)
- `--fail-on-thresholds`
- `--thresholds-file`

## Acceptance Criteria

- Running the CLI produces a timestamped artifact directory and summary report.
- Offline mode works without a Gemini key.
- Retrieval metrics are persisted (`retrieval_metrics.json`) and summarized.
- Threshold failures are recorded and optionally produce a non-zero exit code.
- Existing ingestion pipeline behavior remains unchanged.
