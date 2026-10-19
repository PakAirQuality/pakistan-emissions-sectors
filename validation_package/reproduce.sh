#!/bin/sh
# PakEmis national validation package - independent reproduction.
#
#   ./reproduce.sh            rebuild every canonical output in a SEPARATE temporary copy of
#                             the tree and compare the result with the packaged outputs
#   ./reproduce.sh --keep     keep the temporary tree for inspection (path is printed)
#
# NEVER OVERWRITES THE PACKAGED OUTPUTS. The runnable tree is copied to a temporary directory,
# the build runs there with PKINV_ROOT pointing at the copy, and the comparison reads the copy
# against this package. The only writes here are logs/reproduction.log and
# logs/reproduction_report.csv.
#
# The build is `run_all.py --quick`: every phase except the one that fetches FIRMS fire
# detections over the network (its cached product ships in data/gis/manual and is compared
# like everything else). Offline is enforced with an unroutable proxy.
#
# Comparison is bytewise first; where bytes differ, CSV products are compared cell by cell
# at a relative tolerance of 1e-9 and the maximum difference is reported. Two files are
# expected to differ by construction and are reported as such: outputs/release_manifest.json
# (its git block names the commit and tree state of the environment that ran it) and the
# NetCDF cube (HDF5 writes a creation timestamp). Everything else must match.
set -u

ROOT=$(cd "$(dirname "$0")" && pwd)
PYTHON="${PYTHON:-python3}"
KEEP=0; SOURCES=""
while [ $# -gt 0 ]; do
  case "$1" in
    --keep) KEEP=1 ;;
    --sources) shift; SOURCES="${1:-}" ;;
    *) echo "usage: $0 [--keep] [--sources DIR]" >&2; exit 2 ;;
  esac
  shift
done

mkdir -p "$ROOT/logs"
LOG="$ROOT/logs/reproduction.log"
REPORT="$ROOT/logs/reproduction_report.csv"
: > "$LOG"
WORK=$(mktemp -d "${TMPDIR:-/tmp}/pakemis-reproduce.XXXXXX")
TREE="$WORK/tree"

echo "PakEmis reproduction" | tee -a "$LOG"
echo "package: $ROOT" | tee -a "$LOG"
echo "work:    $TREE" | tee -a "$LOG"
echo "python:  $($PYTHON --version 2>&1)" | tee -a "$LOG"
echo "started: $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$LOG"

export http_proxy="http://127.0.0.1:9" https_proxy="http://127.0.0.1:9"
export HTTP_PROXY="$http_proxy" HTTPS_PROXY="$https_proxy" no_proxy="" NO_PROXY=""
unset FIRMS_MAP_KEY
export PYTHONDONTWRITEBYTECODE=1

# 1. Copy the runnable tree WITHOUT outputs/ (rc41). The rc40 package copied outputs/ into
#    this tree first, so a phase that never ran left the packaged bytes in place and the
#    comparison called them identical. Now outputs/ starts EMPTY except for the held
#    products data/held_products.csv declares - seeded, verified against their release
#    digests and recorded - and the shipped sources/ (public-licence documents) come along
#    because several phases read them. FILE_INVENTORY.csv comes along so the data
#    provenance audit can tell the package's presentation copies under data/ from
#    products (rc41: without it the audit called them unregistered and the strict
#    rebuild stopped there).
mkdir -p "$TREE"
for item in src scripts data sources docs tests capsule .github \
            Makefile pyproject.toml run_all.py CHANGELOG.md CITATION.cff README.md \
            requirements.txt requirements.lock LICENSE LICENSE-data .zenodo.json .gitignore \
            FILE_INVENTORY.csv; do
  [ -e "$ROOT/$item" ] && cp -R "$ROOT/$item" "$TREE/$item"
done
# --sources DIR (rc42): the maintainer's vault stands in for the package's public sources/
# and the two registered raw trees, so the document-dependent phases run on the real bytes.
if [ -n "${SOURCES:-}" ]; then
  [ -d "$SOURCES" ] || { echo "--sources $SOURCES is not a directory" | tee -a "$LOG"; exit 2; }
  [ -d "$SOURCES/sources" ] && rm -rf "$TREE/sources" && cp -R "$SOURCES/sources" "$TREE/sources"
  [ -d "$SOURCES/data/raw" ] && mkdir -p "$TREE/data" && cp -R "$SOURCES/data/raw" "$TREE/data/raw"
  [ -d "$SOURCES/data/cache" ] && mkdir -p "$TREE/data" && cp -R "$SOURCES/data/cache" "$TREE/data/cache"
  echo "sources vault mounted from $SOURCES" | tee -a "$LOG"
fi
find "$TREE" -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null
mkdir -p "$TREE/outputs" "$TREE/logs"
echo "copied $(find "$TREE" -type f | wc -l | tr -d ' ') files; outputs/ starts empty" | tee -a "$LOG"
$PYTHON "$ROOT/tests/validation/seed_held_products.py" "$ROOT" "$TREE" >> "$LOG" 2>&1
SEED=$?
echo "   seeded held products: exit $SEED" | tee -a "$LOG"
echo "reproduce seed exit=$SEED" >> "$ROOT/logs/exit_codes.txt"

# Reconstruct the declared readable input bytes from the deposited source recipe.
# This is offline and runs before any model command, including a direct runner.
( cd "$TREE" && PKINV_ROOT="$TREE" PYTHONPATH="$TREE/src" $PYTHON -m pkinv.activity.build ) >> "$LOG" 2>&1
BOOTSTRAP=$?
echo "reproduce canonical-inputs exit=$BOOTSTRAP" >> "$ROOT/logs/exit_codes.txt"
[ "$BOOTSTRAP" -eq 0 ] || { echo "canonical input bootstrap failed; see $LOG"; exit 1; }

# 2. Rebuild in the copy, --strict: every phase must exit 0 and the run stops at the first
#    that cannot, naming it; the ledger records what each phase wrote.
echo "== run_all.py --quick --strict (in the copy)" | tee -a "$LOG"
start=$(date +%s)
( cd "$TREE" && PKINV_ROOT="$TREE" PYTHONPATH="$TREE/src" $PYTHON run_all.py --quick --strict --ledger logs/pakemis_run_ledger.json --seeded logs/seeded_products.json ) >> "$LOG" 2>&1
BUILD=$?
echo "   build exit $BUILD after $(( $(date +%s) - start )) s" | tee -a "$LOG"
echo "reproduce build exit=$BUILD" >> "$ROOT/logs/exit_codes.txt"
cp "$TREE/logs/pakemis_run_ledger.json" "$ROOT/logs/reproduction_ledger.json" 2>/dev/null && \
  echo "   ledger -> logs/reproduction_ledger.json" | tee -a "$LOG"

# 4. Compare the copy's outputs with the packaged ones.
echo "== comparing $TREE/outputs with $ROOT/outputs" | tee -a "$LOG"
PKINV_ROOT="$ROOT" PYTHONPATH="$ROOT/src" $PYTHON "$ROOT/tests/validation/compare_outputs.py" \
  "$ROOT" "$TREE" "$REPORT" >> "$LOG" 2>&1
COMPARE=$?
echo "reproduce compare exit=$COMPARE" >> "$ROOT/logs/exit_codes.txt"
tail -12 "$LOG"

if [ "$KEEP" -eq 1 ]; then
  echo "temporary tree kept at $TREE" | tee -a "$LOG"
else
  rm -rf "$WORK"
fi
echo "finished: $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$LOG"
[ "$BUILD" -eq 0 ] && [ "$COMPARE" -eq 0 ] && { echo "REPRODUCTION: outputs reproduced (see logs/reproduction_report.csv)" | tee -a "$LOG"; exit 0; }
echo "REPRODUCTION: DIFFERENCES OR BUILD FAILURES RECORDED in logs/reproduction_report.csv" | tee -a "$LOG"
exit 1
