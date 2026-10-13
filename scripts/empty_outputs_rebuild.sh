#!/bin/sh
# Rebuild the inventory from an EMPTY outputs/ directory, in a temporary copy of this tree,
# and compare every manifest product with the committed one.
#
#   sh scripts/empty_outputs_rebuild.sh [--keep] [--full]
#
# The mirror of the validation package's reproduce.sh, runnable from a checkout without
# building a package. It exists because the rc40 package's reproduction copied outputs/ into
# its working tree first, so a phase that never ran left the copied bytes in place and the
# comparison called them identical. Here outputs/ starts EMPTY except for the held products
# data/catalog/held_products.csv declares (seeded and recorded), the build runs --strict (a phase that
# cannot run stops the run and names itself), every phase's written files are recorded in a
# ledger, and a product counts as reproduced only if a phase logged OK and wrote it in THIS run.
#
# --full runs every phase (the FIRMS fetch needs FIRMS_MAP_KEY and the network); default is
# --quick. Writes nothing into this tree except logs/empty_outputs_rebuild.*.
set -u
ROOT=$(cd "$(dirname "$0")/.." && pwd)
PYTHON="${PYTHON:-python3}"
KEEP=0; MODE="--quick"
for arg in "$@"; do
  case "$arg" in
    --keep) KEEP=1 ;;
    --full) MODE="" ;;
    *) echo "usage: $0 [--keep] [--full]" >&2; exit 2 ;;
  esac
done
mkdir -p "$ROOT/logs"
LOG="$ROOT/logs/empty_outputs_rebuild.log"
REPORT="$ROOT/logs/empty_outputs_rebuild_report.csv"
: > "$LOG"
WORK=$(mktemp -d "${TMPDIR:-/tmp}/pakemis-empty-rebuild.XXXXXX")
TREE="$WORK/tree"
echo "empty-outputs rebuild of $ROOT in $TREE" | tee -a "$LOG"

mkdir -p "$TREE"
for item in src scripts data tests docs paper_national papers paper_common sources capsule \
            validation_package .github Makefile pyproject.toml run_all.py CHANGELOG.md CITATION.cff README.md \
            requirements.txt requirements.lock LICENSE LICENSE-data .zenodo.json .gitignore; do
  [ -e "$ROOT/$item" ] && cp -R "$ROOT/$item" "$TREE/$item"
done
find "$TREE" -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null
mkdir -p "$TREE/outputs" "$TREE/logs"
echo "copied the tree WITHOUT outputs/ ($(find "$TREE" -type f | wc -l | tr -d ' ') files)" | tee -a "$LOG"

$PYTHON "$ROOT/tests/validation/seed_held_products.py" "$ROOT" "$TREE" | tee -a "$LOG" || { echo "seeding failed" | tee -a "$LOG"; exit 1; }

export PYTHONDONTWRITEBYTECODE=1
unset FIRMS_MAP_KEY
start=$(date +%s)
( cd "$TREE" && PKINV_ROOT="$TREE" PYTHONPATH="$TREE/src" $PYTHON run_all.py $MODE --strict \
    --ledger logs/pakemis_run_ledger.json --seeded logs/seeded_products.json ) >> "$LOG" 2>&1
BUILD=$?
echo "build exit $BUILD after $(( $(date +%s) - start )) s" | tee -a "$LOG"
cp "$TREE/logs/pakemis_run_ledger.json" "$ROOT/logs/empty_outputs_rebuild_ledger.json" 2>/dev/null

PKINV_ROOT="$ROOT" PYTHONPATH="$ROOT/src" $PYTHON "$ROOT/tests/validation/compare_outputs.py" \
  "$ROOT" "$TREE" "$REPORT" skipped >> "$LOG" 2>&1
COMPARE=$?
tail -15 "$LOG"
[ "$KEEP" -eq 1 ] && echo "tree kept at $TREE" || rm -rf "$WORK"
[ "$BUILD" -eq 0 ] && [ "$COMPARE" -eq 0 ] && { echo "EMPTY-OUTPUTS REBUILD: every manifest product rebuilt or seeded"; exit 0; }
echo "EMPTY-OUTPUTS REBUILD: see $LOG and $REPORT"; exit 1
