#!/usr/bin/env bash
# No bare-pytest fallback: application subprocesses also need OS network/storage isolation.
set -euo pipefail
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
command -v bwrap >/dev/null || { echo "bubblewrap is required for the offline gate" >&2; exit 1; }
run="$(mktemp -d "${TMPDIR:-/tmp}/qna-phase123-gate-XXXXXXXX")"
mkdir -p "$run/home" "$run/tmp" "$run/data"
printf 'Isolated gate workspace: %s\n' "$run"
# Retain this new workspace for diagnostics; never alter the repository data tree.
cd "$repo"
bwrap --unshare-net --ro-bind / / --bind "$run" "$run" \
  --bind "$run/data" "$repo/data" --dev /dev --proc /proc --clearenv \
  --setenv PATH "$PATH" --setenv HOME "$run/home" --setenv TMPDIR "$run/tmp" \
  --setenv PYTHONDONTWRITEBYTECODE 1 --setenv QNA_OFFLINE_ISOLATION 1 \
  --chdir "$repo" "$repo/.venv/bin/python" "$repo/scripts/verify_phase123_offline.py"
