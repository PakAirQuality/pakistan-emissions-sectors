#!/bin/zsh
# The release finish: receipts -> fixpoint -> record -> package -> split, in the one
# order that survives its own guards. Proven over rc48 (as a scratchpad script) and
# promoted here; the version comes from pkinv.__version__, never typed.
#
#   usage: zsh scripts/release_finish.sh <log_dir>
#
# WHY THIS ORDER (each clause is a defect this sequence has actually caught):
# - receipts BEFORE the fixpoint, deposit LAST: release_fixpoint regenerates only the
#   manifest/cover/availability/papers, so a manifest older than the deposit describes
#   a tree that no longer exists.
# - receipts COMMITTED before the fixpoint: the manifest records tree_dirty, and a
#   manifest that admits a dirty build tree may never be committed
#   (test_release_integrity).
# - the record refuses a FAILED run; the split builder refuses a package whose own
#   reproduce/quick/full exit codes are nonzero (fail-closed, logs/exit_codes.txt).
set -e
cd "$(dirname "$0")/.."
G="$1"
[ -n "$G" ] || { echo "usage: zsh scripts/release_finish.sh <log_dir>"; exit 2; }
V=$(python3 -c "import sys; sys.path.insert(0,'src'); import pkinv; print(pkinv.__version__)")
echo "== release finish for $V"

echo "== receipts (deposit last)"
python3 -m pkinv.report.artifact_inventory > /dev/null 2>&1
python3 -m pkinv.report.product_facts > /dev/null 2>&1
python3 -m pkinv.report.data_provenance > /dev/null 2>&1
python3 -m pkinv.report.release_manifest > /dev/null 2>&1
python3 -m pkinv.report.deposit_manifest > /dev/null 2>&1
if ! git diff --quiet || ! git diff --cached --quiet; then
  git add -A
  git commit -q -m "Receipts converge before the fixpoint (deposit last)"
  echo "receipts: $(git log --oneline -1)"
fi

echo "== fixpoint"
python3 scripts/release_fixpoint.py > "$G/fixpoint_$V.log" 2>&1
git add -A
git commit -q -m "Release manifest, cover, SHA256SUMS and PDFs: regenerate against the clean $V tree"
echo "artifacts: $(git log --oneline -1)"

echo "== record"
python3 scripts/record_test_run.py > "$G/record_$V.log" 2>&1
tail -1 "$G/record_$V.log"
grep -q '"failed": 0' outputs/pakemis_test_run.json \
  || grep -q ', 0 failed' "$G/record_$V.log" \
  || { echo "RECORD NOT CLEAN"; exit 1; }
git add outputs/pakemis_test_run.json
git commit -q -m "Record the $V release run on the fixpoint tree"
echo "record: $(git log --oneline -1)"

echo "== package"
python3 scripts/build_validation_package.py > "$G/package_$V.log" 2>&1 \
  || { echo "PACKAGE FAILED"; tail -6 "$G/package_$V.log"; exit 1; }
tail -3 "$G/package_$V.log"

echo "== split"
python3 scripts/build_release_split.py

echo "== ALL DONE for $V"
