#!/bin/zsh
# The content-commit gate (tracked since the v1.0.0 program; it lived in a session scratchpad
# through rc42 and was lost with it). Every content commit on the release branch goes through
# this chain: regenerate the derived registers to a fixed point -> pins -> the full suite ->
# stage -> a quick build that must add no unstaged change -> commit.
#
#   zsh scripts/gate_chain.sh <message-file> [--after-mint]
#
# --after-mint: do NOT restore the committed release manifest before committing (the strict
# build after a mint wrote the new version's manifest and the README regenerates from it;
# restoring the old one reverts the version - the rc41/rc42 lesson). Wave gates restore it,
# because between releases the committed manifest is the release's and the tree's is noise.
#
# Logs and scratch go to $PKINV_GATE_DIR (default: /tmp/pakemis-gate). Exit 1 at the first
# gate that holds; the working tree is left as it was for inspection.
set -u
MSG=${1:?message file}
AFTER_MINT=0; [ "${2:-}" = "--after-mint" ] && AFTER_MINT=1
ROOT=$(cd "$(dirname "$0")/.." && pwd); cd "$ROOT" || exit 1
G=${PKINV_GATE_DIR:-/tmp/pakemis-gate}; mkdir -p "$G"
export PYTHONPATH=src
PY=python3

regen() {
  $PY scripts/make_readme_tables.py && $PY -m pkinv.report.data_provenance \
    && $PY -m pkinv.report.artifact_inventory \
    && $PY -m pkinv.report.deposit_manifest && $PY -m pkinv.report.product_facts \
    && $PY scripts/build_product_columns.py > /dev/null || return 1
  # steps the v1.0.0 program adds, each run only once it exists
  [ -f src/pkinv/semantic/build.py ] && { $PY -m pkinv.semantic.build > /dev/null || return 1; }
  # the deposit manifest hashes what the steps above rewrite AFTER the manifest ran: close the
  # loop so the suite never sees a manifest one step behind
  $PY -m pkinv.report.deposit_manifest > /dev/null || return 1
  return 0
}

echo "== regen 1"; regen > "$G/regen1.log" 2>&1 || { echo "REGEN 1 FAILED"; tail -20 "$G/regen1.log"; exit 1; }
echo "== regen 2"; regen > "$G/regen2.log" 2>&1 || { echo "REGEN 2 FAILED"; tail -20 "$G/regen2.log"; exit 1; }

echo "== pins"
$PY scripts/check_pins.py || { echo "PINS MOVED"; exit 1; }

echo "== full suite (parallel, one process per module)"
# scripts/run_tests.py, not `unittest discover`: the same 3,003 tests in about 172 seconds
# against 582, verified on one tree to dispatch the same test ids with the same outcomes.
# The CANONICAL serial invocation still runs once per round, in scripts/record_test_run.py,
# after the artifacts commit - that is the number the release publishes. This step is a gate,
# and a gate wants the answer, not the ceremony.
#
# The runner prints [FAIL] for a failure and [ERROR] for a test that could not run. Keeping
# them apart is load-bearing: the exclusion list below may only ever apply to FAILURES, and an
# error printed as [FAIL] would become excludable. tests/test_parallel_runner.py asserts these
# two patterns still match what the runner emits, because a rename here counts zero of
# everything and reads as green.
$PY scripts/run_tests.py > "$G/suite.log" 2>&1
# the runner's summary line, which it prints BEFORE the failure details - a tail of this log
# is the last traceback, not the result
grep -E "^[0-9]+ modules," "$G/suite.log" | tail -1
ERRORS=$(grep -c "^\[ERROR\]" "$G/suite.log" | tr -d ' ')
# THE HEAD-BASELINE FAMILY: tests that compare the working tree against the LAST COMMITTED
# release and therefore cannot pass before a content commit that legitimately moves numbers;
# they reset the moment the content lands. The first three are the release fixpoint; the three
# cube guards diff outputs/pakemis_adm2_monthly.csv against HEAD. VERIFY THEM AFTER THE COMMIT
# by re-running the suite; excluding them here is not the same as passing them.
EXCLUDE="test_the_committed_manifest_describes_the_committed_content|test_the_release_manifest_regenerates_identically|test_the_committed_release_artifacts_claim_a_clean_tree|test_a_monthly_reshape_never_moves_a_district_year|test_the_view_axis_is_a_grouping_and_not_a_reallocation|test_every_adm1_marginal_is_unchanged_by_the_change"
FAILS=$(grep "^\[FAIL\]" "$G/suite.log" | grep -E -v "$EXCLUDE" | wc -l | tr -d ' ')
echo "errors=$ERRORS non-fixpoint-fails=$FAILS"
[ "$ERRORS" = "0" ] && [ "$FAILS" = "0" ] || { echo "SUITE GATE HELD"; grep -E "^\[(FAIL|ERROR)\]" "$G/suite.log"; exit 1; }

echo "== stage, then quick build noise gate"
# Stage first, then regenerate again: data_provenance enumerates its universe with
# `git ls-files data`, so a data/ file this pass ADDS is invisible to the regen above and
# visible to the build below; staging before the second regen puts both on the same tree.
git add -A
regen > "$G/regen3.log" 2>&1 || { echo "REGEN 3 FAILED"; exit 1; }
git add -A
$PY -m pkinv.run_all --quick > "$G/build.log" 2>&1
grep -c "\[FAIL\]" "$G/build.log" | tr -d ' ' | xargs -I{} echo "build FAIL lines: {}"
grep -q "\[FAIL\]" "$G/build.log" && { echo "BUILD GATE HELD"; grep "\[FAIL\]" "$G/build.log"; exit 1; }
NOISE=$(git status --short | grep -v "^[MARD]  " | grep -v "outputs/release_manifest.json" | wc -l | tr -d ' ')
echo "unstaged changes beyond the manifest: $NOISE"
[ "$NOISE" = "0" ] || { echo "NOISE GATE HELD"; git status --short | grep -v "^[MARD]  "; exit 1; }
if [ "$AFTER_MINT" = "1" ]; then
  git add -A
else
  git checkout HEAD -- outputs/release_manifest.json
  git add -A
fi

echo "== commit"
git commit -q -F "$MSG" && git log --oneline -1
