#!/bin/bash
# Run feature-focused ablation studies for keyword/summaries, HyPE, and reranking.

set -e

echo "=== Running Feature Ablation Studies ==="
echo ""

# Check if uv is available
if ! command -v uv &> /dev/null; then
    echo "Error: uv not found. Please install uv first."
    exit 1
fi

uv run python scripts/run_feature_ablations.py "$@"
