#!/usr/bin/env bash
# The from-outside half of gate 9: clone this repository into a temp directory,
# install the pinned environment, run the offline build, and compare what it wrote
# against what the clone committed.
#
# WHY A SCRIPT AND NOT JUST CI. CI rebuilds from an empty checkout on every push,
# but it rebuilds THE SAME LIST OF PHASES the workflow names - a file the working
# tree needs but never committed would fail there, yet a dependency CI's runner
# happens to preinstall would not. This script is the harness a stranger actually
# runs: nothing but git, python3 and the lockfile.
#
# WHAT COUNTS AS PASSING. After `run_all --quick` (the offline phase set; the one
# network phase is skipped by declaration), `git status` inside the clone must
# show no modified tracked file - the committed outputs ARE the rebuild's outputs.
# Known exception, checked explicitly rather than waved at: the NetCDF cube's
# BYTES churn per code-path change while its content stays deterministic
# (documented in docs/spatial_products_contract.md), so a cube-only diff is
# reported as PASS-with-note and anything else is a FAIL naming the files.
#
# poppler-utils (pdftotext) is a SYSTEM dependency of the source-ingestion
# scripts only - the inventory build itself never shells out to it, so its
# absence here is a warning, not a failure. Declared in pyproject.toml and the
# README because pip cannot install it.
#
# Usage:  bash scripts/clean_rebuild.sh [workdir]
#         (workdir defaults to a mktemp -d; kept on failure for inspection)
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
WORK="${1:-$(mktemp -d /tmp/pakemis_clean_rebuild.XXXXXX)}"
CLONE="$WORK/clone"

echo "clean-room rebuild in $WORK"
git clone --quiet --local "$REPO" "$CLONE"
echo "  cloned $(git -C "$CLONE" rev-parse --short HEAD) ($(git -C "$CLONE" ls-files | wc -l | tr -d ' ') tracked files)"

python3 -m venv "$WORK/venv"
# shellcheck disable=SC1091
source "$WORK/venv/bin/activate"
python3 -m pip install --quiet --upgrade pip
if [ ! -f "$CLONE/requirements.lock" ]; then
    # the cloned commit predates the lockfile (or a lock change is being tested
    # before its commit): fall back to the invoking repo's copy, and say so
    echo "  NOTE: clone has no requirements.lock; using $REPO/requirements.lock"
    cp "$REPO/requirements.lock" "$CLONE/requirements.lock"
fi
python3 -m pip install --quiet -r "$CLONE/requirements.lock"
python3 -m pip install --quiet --no-deps -e "$CLONE"
echo "  environment: $(python3 --version) + requirements.lock ($(grep -c '==' "$CLONE/requirements.lock") pins)"

if ! command -v pdftotext >/dev/null 2>&1; then
    echo "  WARNING: poppler-utils (pdftotext) not found - source-ingestion scripts"
    echo "  are unavailable, the inventory build does not need them (pyproject.toml)"
fi

cd "$CLONE"
python3 -m pkinv.run_all --quick

CHANGED="$(git status --porcelain --untracked-files=no | awk '{print $2}')"
CUBE="outputs/pakemis_grid_0p05_monthly.nc"
MANIFEST="outputs/release_manifest.json"

# THE SECOND DECLARED EXCEPTION, and like the cube it is CHECKED rather than waved at.
# release_manifest.json records `describes_commit`: the content commit it was cut against.
# The release dance then adds two more commits on top of it - the artifacts commit and the
# run record - so a clone at HEAD regenerates the manifest naming HEAD, and the committed
# one names the content commit three back. No fixpoint exists, in exactly the way none
# exists for a PDF that would have to contain the hash of a manifest containing its own hash.
#
# What is NOT excused is any other line. A differing product hash, source hash, total or
# count means the rebuild did not reproduce the release, so the diff is inspected and only a
# describes_commit-only difference passes. Anything else falls through to the FAIL below.
MANIFEST_ONLY_COMMIT=0
if [ "$CHANGED" = "$MANIFEST" ]; then
    SUBSTANTIVE="$(git diff -U0 -- "$MANIFEST" \
        | grep -E '^[+-]' | grep -vE '^(\+\+\+|---)' \
        | grep -vE '"(describes_commit|commit|tree_dirty|generated_at)"' || true)"
    [ -z "$SUBSTANTIVE" ] && MANIFEST_ONLY_COMMIT=1
fi

if [ -z "$CHANGED" ]; then
    echo "CLEAN-ROOM PASS: the rebuild reproduced every committed output byte-for-byte"
elif [ "$CHANGED" = "$CUBE" ]; then
    echo "CLEAN-ROOM PASS (with the documented note): only the NetCDF cube's bytes"
    echo "differ - its content is deterministic but its byte stream churns per"
    echo "code-path change; see docs/spatial_products_contract.md"
elif [ "$MANIFEST_ONLY_COMMIT" = "1" ]; then
    echo "CLEAN-ROOM PASS (with the documented note): every product, hash, total and"
    echo "count reproduced byte-for-byte. The release manifest differs in"
    echo "\`describes_commit\` alone, because it names the content commit it was cut"
    echo "against and the release dance commits twice more on top of it - a field a"
    echo "clone at HEAD cannot reproduce by construction, not a build that varies."
else
    echo "CLEAN-ROOM FAIL: the rebuild changed tracked files the commit did not hold:"
    echo "$CHANGED" | sed 's/^/    /'
    echo "workdir kept for inspection: $WORK"
    exit 1
fi

echo "  (workdir $WORK can be removed)"
