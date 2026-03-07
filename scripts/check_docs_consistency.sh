#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

targets=(
  "README.md"
  "ARCHITECTURE.md"
  "CLAUDE.md"
  "docs/architecture/overview.md"
  "docs/architecture/rag-system.md"
  "docs/configuration.md"
  "docs/eval_plan.md"
  "docs/testing/backend-tests.md"
  ".planning/codebase/ARCHITECTURE.md"
  ".planning/codebase/CONCERNS.md"
  ".planning/codebase/CONVENTIONS.md"
  ".planning/codebase/INTEGRATIONS.md"
  ".planning/codebase/STACK.md"
  ".planning/codebase/STRUCTURE.md"
)

patterns=(
  "GEMINI_API_KEY"
  "localhost:8001"
  "localhost:5174"
  "synthetic_gemini"
  "gemini_key_present"
  "confidenceCalculator.ts"
)

cd "$ROOT_DIR"

failures=0

for pattern in "${patterns[@]}"; do
  matches="$(rg -n --fixed-strings "$pattern" "${targets[@]}" || true)"
  if [[ -n "$matches" ]]; then
    echo "Found stale reference: $pattern"
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
