#!/bin/zsh
# The v1.0.0 release sequence, as one detached-friendly script (route A: the three DOIs
# are reserved on Zenodo BEFORE this runs and are its arguments).
#
#   nohup zsh scripts/release_1_0_0.sh <doi-data> <doi-software> <doi-docs> > /dev/null 2>&1 &
#
# Writes $PKINV_GATE_DIR/release_1_0_0.{log,status} and touches release_1_0_0.done at the end
# (success or failure - read the status). Wait on it with a Monitor, never a Bash waiter
# (a stopped waiter killed the rc42 chain). Steps, each a commit or a gate of its own:
#   1 clean tree     2 mint (versions + DOIs)     3 identity + registry checks
#   4 strict full build   5 content gate (--after-mint)   6 release fixpoint -> artifacts commit
#   7 test-run record -> record commit   8 integrity + identity on the fixpoint tree
#   9 validation package (--docker)   10 development snapshot + the three deposits
# Nothing here pushes, tags or uploads.
set -u
ROOT=$(cd "$(dirname "$0")/.." && pwd); cd "$ROOT" || exit 1
G=${PKINV_GATE_DIR:-/tmp/pakemis-gate}; mkdir -p "$G"
LOG=$G/release_1_0_0.log; ST=$G/release_1_0_0.status; DONE=$G/release_1_0_0.done
rm -f "$DONE"; : > "$ST"
DOI_DATA=${1:?doi-data}; DOI_SOFTWARE=${2:?doi-software}; DOI_DOCS=${3:?doi-docs}
PY=${PYTHON:-python3}

step() { echo "== $1 $(date +%H:%M:%S)" | tee -a "$ST" >> "$LOG"; }
fail() { echo "FAILED at $1 $(date +%H:%M:%S)" | tee -a "$ST" >> "$LOG"; touch "$DONE"; exit 1; }
suite() { $PY -m unittest discover -s tests -p "$1" >> "$LOG" 2>&1; }

step "1 clean tree"
# this script itself may be untracked: it rides the mint commit (git add -A in the gate)
[ -z "$(git status --porcelain | grep -v 'scripts/release_1_0_0.sh')" ] || fail "1: the tree is not clean; commit or stash first"
grep -q '__version__ = "1.0.0rc' src/pkinv/__init__.py || fail "1: not on a release-candidate version"

step "2 mint"
$PY scripts/mint_1_0_0.py --doi-data "$DOI_DATA" --doi-software "$DOI_SOFTWARE" --doi-docs "$DOI_DOCS" >> "$LOG" 2>&1 || fail "2 mint"

step "3 identity + registry checks"
suite test_release_identity.py || fail "3 identity"
suite test_claims_registry.py || fail "3 claims registry"
suite test_technical_notes.py || fail "3 technical notes"

step "4 strict full build"
$PY -m pkinv.run_all --strict >> "$LOG" 2>&1 || fail "4 build"
grep -q '\[FAIL\]' "$LOG" && fail "4 build: a [FAIL] line in the run log"

step "5 content gate (--after-mint)"
cat > "$G/msg_mint" <<MSG
Mint PakEmis 1.0.0: the rc42 tree frozen with the semantic truth layer, three reserved DOIs

Version 1.0.0rc42 -> 1.0.0 at every site that carries it; the three Zenodo identifiers
reserved before the mint (data $DOI_DATA, software $DOI_SOFTWARE, documentation $DOI_DOCS)
written into the release manifest, CITATION.cff, .zenodo.json, the bibliography notes, the
manuscripts' release lines, the claims registry and the CHANGELOG. No science changed: the
pins hold at L 452.34662 / S 447.21383. The strict full build regenerated every product under
the final version; this commit carries the content, the release fixpoint commit that follows
carries the manifest, cover and PDFs, and the record commit the test-run record.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GGTmKsyngnm5TwQoS12nNY
MSG
zsh scripts/gate_chain.sh "$G/msg_mint" --after-mint >> "$LOG" 2>&1 || fail "5 gate"
[ -z "$(git status --porcelain)" ] || fail "5 gate left the tree dirty"

step "6 release fixpoint"
$PY scripts/release_fixpoint.py >> "$LOG" 2>&1 || fail "6 fixpoint"
git add -A && git commit -q -F - <<MSG || fail "6 artifacts commit"
Release manifest, cover, SHA256SUMS and PDFs: regenerate against the clean 1.0.0 tree

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GGTmKsyngnm5TwQoS12nNY
MSG

step "7 test-run record"
$PY scripts/record_test_run.py >> "$LOG" 2>&1 || fail "7 record"
SUMMARY=$($PY - <<'PYS'
import json; r = json.load(open("outputs/pakemis_test_run.json"))
ex = r.get("executed", r.get("ran")); fa = r.get("failed", 0)
print("%s tests, %s failed" % (ex, fa))
PYS
)
git add -A && git commit -q -m "Record the 1.0.0 release run: $SUMMARY, on the fixpoint tree

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GGTmKsyngnm5TwQoS12nNY" || fail "7 record commit"
echo "$SUMMARY" | grep -q ' 0 failed' || fail "7 the record reports failures: $SUMMARY"

step "8 integrity + identity on the fixpoint tree"
suite test_release_integrity.py || fail "8 integrity"
suite test_release_identity.py || fail "8 identity"
suite test_grid_cube.py || fail "8 cube guards"

step "9 validation package (--docker)"
$PY scripts/build_validation_package.py --docker >> "$LOG" 2>&1 || fail "9 package"

step "10 development snapshot + deposits"
$PY scripts/build_dev_snapshot.py >> "$LOG" 2>&1 || fail "10 dev snapshot"
$PY scripts/build_deposit_zip.py >> "$LOG" 2>&1 || fail "10 deposits"

step "DONE $(git rev-parse --short HEAD)"
touch "$DONE"
