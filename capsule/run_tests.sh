#!/bin/sh
# Re-run this capsule's agriculture test suite from a clean interpreter.
#
# NO DEPENDENCIES TO INSTALL. The agriculture engine and every test below run on the Python 3
# standard library alone - requirements.txt has said so for the national and provincial phases
# for releases, and this capsule is the first thing to prove it: the suite was run in a venv
# created with `python3 -m venv` and nothing installed into it, and all thirteen modules
# passed. The geospatial stack (numpy, rasterio, geopandas) is needed by the GRIDDING phases,
# which this capsule does not contain and this suite does not exercise.
#
# So this script creates an empty virtual environment rather than installing a pinned
# requirements file. That is not a shortcut around pinning: a suite with no third-party
# imports has nothing whose version could drift, and shipping a requirements file it does not
# use would imply a dependency surface that is not there.
#
# WHAT WAS VERIFIED, AND WHERE. macOS 15.6 (darwin 24.6.0), CPython 3.11.10, on the machine
# that produced the release. NOT verified on Linux or Windows, and not verified on another
# CPython minor version. The capsule states this rather than implying a portability nobody
# tested; if it matters to you, run this script on your platform and the answer is whatever
# it prints.
#
# Usage:  sh capsule/run_tests.sh          (from the capsule root)
set -eu

ROOT=$(cd "$(dirname "$0")/.." && pwd)
VENV="${TMPDIR:-/tmp}/pakemis-capsule-venv"

echo "capsule root: $ROOT"
echo "python:       $(python3 --version 2>&1)"
echo "platform:     $(uname -sr)"
echo

echo "== creating a clean interpreter (no packages installed) =="
rm -rf "$VENV"
python3 -m venv "$VENV"
"$VENV/bin/python" -c "import sys; print('  ', sys.version.split()[0], 'at', sys.prefix)"
echo

# Materialize the readable inputs from the capsule's deposited extracts and schemas.
# This stage also uses only the standard library and never opens source documents.
PYTHONPATH="$ROOT/src" PKINV_ROOT="$ROOT" "$VENV/bin/python" -m pkinv.activity.build

# The agriculture suite. Each module is here because it asserts something this capsule is
# meant to let a reader check for themselves, not because it happened to pass.
MODULES="
test_inventory                    hand-calculated IPCC worked examples against the engine
test_livestock_rebase             the census counts, and the district residual published not absorbed
test_fertiliser_window            the Jul-Jun composition window and the FracGASF it implies
test_urea_basis                   which urea mass each year used, measured or reconstructed
test_ne_categories                a Not-Estimated category publishes no number
test_agriculture_control          the EXTERNAL control: six categories and the total, to 6 dp
test_method_registry              every atom names the IPCC equation that produced it
test_residue_ledger               every tonne of residue has a destination, and they close
test_n_ledger                     the nitrogen chain, stage by stage, on both bases
test_agriculture_fiscal           the nine fiscal years and what the basis change cost
test_joint_uncertainty_reconciles the deterministic side reconciles to the published total
test_agriculture_timing           which flat months are physics and which are ignorance
test_spatial_exceptions           every stream names its raster; the exceptions carry mass
"

FAILED=0
PASSED=0
echo "== running the agriculture suite =="
echo "$MODULES" | while read -r module _rest; do
  [ -n "$module" ] || continue
  printf '  %-34s ' "$module"
  if PYTHONPATH="$ROOT/src:$ROOT/tests" \
     "$VENV/bin/python" -m unittest discover "$ROOT/tests" -p "$module.py" > "$VENV/$module.log" 2>&1
  then
    printf 'OK   %s\n' "$(grep -o 'Ran [0-9]* test[s]*' "$VENV/$module.log" | tail -1)"
  else
    printf 'FAILED\n'
    tail -20 "$VENV/$module.log"
    echo "$module" >> "$VENV/failures"
  fi
done

echo
if [ -s "$VENV/failures" ] 2>/dev/null; then
  echo "SUITE FAILED:"
  cat "$VENV/failures"
  exit 1
fi
echo "SUITE PASSED - every module above ran on the standard library alone."
echo
echo "The four release-integrity tests in the full repository are NOT in this suite: they"
echo "compare committed release artefacts against a working tree and can only pass on the"
echo "commit the artefacts were cut from, which a capsule does not reproduce."
