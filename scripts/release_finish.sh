#!/bin/zsh
# The release finish: receipts -> fixpoint -> campaign -> record -> deposit, in the one
# order that survives its own guards. Proven over rc48 (as a scratchpad script) and
# promoted here; the version comes from pkinv.__version__, never typed.
#
#   usage: zsh scripts/release_finish.sh <log_dir>
#
# WHY THIS ORDER (each clause is a defect this sequence has actually caught):
# - receipts BEFORE the fixpoint, deposit LAST: release_fixpoint regenerates only the
#   manifest and checksums, so a manifest older than the deposit describes
#   a tree that no longer exists.
# - receipts COMMITTED before the fixpoint: the manifest records tree_dirty, and a
#   manifest that admits a dirty build tree may never be committed
#   (test_release_integrity).
# - the record refuses a FAILED run. (Until rc68 the finish built a validation package and
#   split it; the deposit collection replaced both.) The split builder refused a package whose own
#   reproduce/quick/full exit codes are nonzero (fail-closed, logs/exit_codes.txt).
set -e
cd "$(dirname "$0")/.."
# rc69: this checkout's own code, never a globally installed pkinv (in the public clone the
# global editable install pointed at the private rc68 tree)
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
G="$1"
# Optional trailer appended to every commit this script makes (e.g. attribution lines).
TRAILER=()
[ -n "$RELEASE_COMMIT_TRAILER" ] && TRAILER=(-m "$RELEASE_COMMIT_TRAILER")
[ -n "$G" ] || { echo "usage: zsh scripts/release_finish.sh <log_dir>"; exit 2; }
V=$(python3 -c "import sys; sys.path.insert(0,'src'); import pkinv; print(pkinv.__version__)")
echo "== release finish for $V"

echo "== receipts (deposit last)"
# rc69: the release tail in its registry order, repeated until a pass changes nothing. One
# pass left product_facts quoting a deposit count from before the deposit manifest grew by
# ten rows.
for pass in 1 2 3 4; do
  before=$(git diff | git hash-object --stdin)
  python3 -m pkinv.report.artifact_inventory > /dev/null 2>&1
  python3 scripts/make_product_coverage.py > /dev/null 2>&1
  python3 -m pkinv.report.deposit_manifest > /dev/null 2>&1
  python3 -m pkinv.report.product_facts > /dev/null 2>&1
  python3 -m pkinv.report.data_provenance > /dev/null 2>&1
  [ "$(git diff | git hash-object --stdin)" = "$before" ] && break
  [ $pass = 4 ] && { echo "RECEIPTS DID NOT CONVERGE"; exit 1; }
done
python3 -m pkinv.report.release_manifest > /dev/null 2>&1
python3 -m pkinv.report.deposit_manifest > /dev/null 2>&1
if ! git diff --quiet || ! git diff --cached --quiet; then
  git add -A
  git commit -q -m "Receipts converge before the fixpoint (deposit last)" "${TRAILER[@]}"
  echo "receipts: $(git log --oneline -1)"
fi

echo "== fixpoint"
python3 scripts/release_fixpoint.py > "$G/fixpoint_$V.log" 2>&1
git add -A
git commit -q -m "Release manifest and SHA256SUMS: regenerate against the clean $V tree" "${TRAILER[@]}"
echo "artifacts: $(git log --oneline -1)"

# rc69: the campaign hand-off manifest takes its digests from the release manifest, so it
# follows the fixpoint. It lives in the restricted layer and is committed there.
if [ -f research_campaign/build_campaign_tables.py ]; then
  echo "== campaign hand-off (restricted layer)"
  python3 research_campaign/build_campaign_tables.py > "$G/campaign_$V.log" 2>&1
  O=$(python3 -c "from pkinv.core import layers; print(layers.overlay_root() or '')")
  if [ -n "$O" ] && [ "$O" != "$PWD" ] && ! git -C "$O" diff --quiet -- research_campaign; then
    git -C "$O" add research_campaign
    git -C "$O" commit -q -m "Campaign hand-off manifest on the $V release" "${TRAILER[@]}"
    echo "campaign: $(git -C "$O" log --oneline -1)"
  fi
fi

echo "== record"
python3 scripts/record_test_run.py > "$G/record_$V.log" 2>&1
tail -1 "$G/record_$V.log"
grep -q '"failed": 0' outputs/pakemis_test_run.json \
  || grep -q ', 0 failed' "$G/record_$V.log" \
  || { echo "RECORD NOT CLEAN"; exit 1; }
git add outputs/pakemis_test_run.json
git commit -q -m "Record the $V release run on the fixpoint tree" "${TRAILER[@]}"
echo "record: $(git log --oneline -1)"

# rc69: the deposit collection is the release path (dist/pakemis-<version>-*.zip), as at rc68;
# the validation package and its split are no longer built here.
echo "== deposit"
python3 scripts/build_deposit_zip.py > "$G/deposit_$V.log" 2>&1 \
  || { echo "DEPOSIT FAILED"; tail -6 "$G/deposit_$V.log"; exit 1; }
tail -2 "$G/deposit_$V.log"
python3 scripts/check_release_sequence.py

echo "== ALL DONE for $V"
