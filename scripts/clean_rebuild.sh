#!/usr/bin/env bash
# Compiled-input reproduction in a fresh deposit-shaped tree and pinned environment.
# Full primary-source re-extraction is separately recorded by the source checks.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
exec python3 "$REPO/scripts/clean_rebuild.py" "$@"
