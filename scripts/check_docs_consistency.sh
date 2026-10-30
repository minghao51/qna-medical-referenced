#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

targets=(
  "README.md"
  "docs/architecture/overview.md"
  "docs/architecture/rag-system.md"
  "docs/configuration.md"
  "docs/data/sources.md"
  "docs/evaluation/pipeline_quality_assessment_plan.md"
  "docs/README.md"
  "docs/quickstart.md"
  "docs/testing/backend-tests.md"
  "docs/testing/playwright.md"
  "frontend/README.md"
)

patterns=(
  "localhost:8001"
  "synthetic_gemini"
  "gemini_key_present"
  "confidenceCalculator.ts"
  "docs/architecture/README.md"
  "docs/testing/README.md"
)

# Stale flat provider env names, e.g. `GEMINI_API_KEY=...` or `export DASHSCOPE_API_KEY=...`.
# Nested names such as `APP__LLM__GEMINI_API_KEY` are the supported form and must not match.
stale_env_keys=(
  "GEMINI_API_KEY"
  "DASHSCOPE_API_KEY"
)

cd "$ROOT_DIR"

failures=0

for target in "${targets[@]}"; do
  if [[ ! -f "$target" ]]; then
    echo "Missing docs target: $target"
    failures=1
  fi
done

for pattern in "${patterns[@]}"; do
  matches="$(rg -n --fixed-strings "$pattern" "${targets[@]}" 2>/dev/null || true)"
  if [[ -n "$matches" ]]; then
    echo "Found stale reference: $pattern"
    echo "$matches"
    echo
    failures=1
  fi
done

for env_key in "${stale_env_keys[@]}"; do
  matches="$(rg -n "(^|[^A-Za-z0-9_])${env_key}=" "${targets[@]}" 2>/dev/null || true)"
  if [[ -n "$matches" ]]; then
    echo "Found stale reference: ${env_key}="
    echo "$matches"
    echo
    failures=1
  fi
done

if [[ "$failures" -ne 0 ]]; then
  echo "Docs consistency check failed."
  exit 1
fi

echo "Docs consistency check passed."
