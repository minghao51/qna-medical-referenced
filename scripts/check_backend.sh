#!/usr/bin/env bash
# Single backend command surface for this repository.
#
# CI and local development both call this script; the Makefile only wraps it.
# Direct use must work where `make` is unavailable.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# Marker selection is defined here once and reused by every pytest mode.
FAST_MARKERS='not slow and not live_api and not live_openrouter and not e2e_real_apis and not deepeval and not network'
OFFLINE_MARKERS='not live_api and not live_openrouter and not e2e_real_apis and not deepeval and not network'
COVERAGE_FLOOR="${QNA_COVERAGE_FLOOR:-80}"

usage() {
    cat <<'EOF'
Usage: bash scripts/check_backend.sh <mode> [pytest args...]

Modes:
  fast            Offline gate, no coverage, slow tests excluded (default; ~40s)
  offline         Offline gate including slow tests (still synthetic, no corpus rebuild)
  unit            Fast selection limited to tests/unit (parallel with xdist)
  integration     Fast selection limited to tests/integration
  coverage        Fast selection with --cov=src and a coverage floor
  lint            Ruff check/format-check, mypy, import-linter, Bandit, docs consistency.
                  Read-only: never auto-fixes.
  smoke           Smoke-marked tests only
  frontend-check  svelte-check plus production build (no Playwright)
  frontend-test   Playwright suite (requires installed browsers)
  help            This message

Notes:
  * No mode selects live/network/DeepEval tests or spends provider quota; those
    need their own opt-in environment variables and a deliberate command.
  * The coverage floor defaults to 80 (override with QNA_COVERAGE_FLOOR).
  * Tests must not write project data under data/; a session guard fails the run
    if they do.
EOF
}

die_usage() {
    echo "$1" >&2
    usage >&2
    exit 2
}

require_no_args() {
    local mode_name="$1"
    shift
    if [[ $# -gt 0 ]]; then
        die_usage "mode '$mode_name' does not accept extra arguments"
    fi
}

run_lint() {
    uv run --frozen ruff check .
    uv run --frozen ruff format --check .
    uv run --frozen mypy src
    uv run --frozen lint-imports
    uv run --frozen bandit -r src/ -ll
    bash scripts/check_docs_consistency.sh
}

mode="${1:-help}"
if [[ $# -gt 0 ]]; then
    shift
fi

case "$mode" in
    fast)
        exec uv run --frozen python -m pytest -m "$FAST_MARKERS" "$@"
        ;;
    offline)
        exec uv run --frozen python -m pytest -m "$OFFLINE_MARKERS" "$@"
        ;;
    unit)
        exec uv run --frozen python -m pytest tests/unit/ -m "$FAST_MARKERS" -n auto "$@"
        ;;
    integration)
        exec uv run --frozen python -m pytest tests/integration/ -m "$FAST_MARKERS" "$@"
        ;;
    coverage)
        exec uv run --frozen python -m pytest -m "$FAST_MARKERS" \
            --cov=src \
            --cov-report=term-missing:skip-covered \
            --cov-fail-under="$COVERAGE_FLOOR" \
            "$@"
        ;;
    lint)
        require_no_args "$mode" "$@"
        run_lint
        ;;
    smoke)
        exec uv run --frozen python -m pytest -m smoke "$@"
        ;;
    frontend-check)
        require_no_args "$mode" "$@"
        ( cd frontend && bun run check && bun run build )
        ;;
    frontend-test)
        require_no_args "$mode" "$@"
        ( cd frontend && bun run test )
        ;;
    help|-h|--help)
        usage
        ;;
    *)
        die_usage "unknown mode: $mode"
        ;;
esac
