#!/usr/bin/env bash
# The FULL clean-room reconstruction (rc29): the seventeenth review's contract,
# executed end-to-end where scripts/clean_rebuild.sh (the quick gate, untouched)
# covers only the middle third.
#
#   fresh clone     git clone file:// - the file:// transport forces a real object
#                   walk instead of the hardlink shortcut, so the clone holds only
#                   what git holds
#   LFS             the branch has never been pushed, so no remote holds the 19
#                   LFS objects (~3 GB, 7 of them manifest-hashed source
#                   documents); they are copied from the invoking repository's
#                   object store and checked out, then a PREFLIGHT asserts no
#                   tracked file is still a pointer - a clone that hashed pointer
#                   files would "reproduce" a manifest describing 130-byte stubs
#   empty env       a fresh venv from requirements.lock, --no-deps -e .
#   offline proof   http(s)_proxy exported to an unroutable address for the build
#                   and the tests: any attempted fetch fails loudly instead of
#                   silently succeeding, which is the difference between "did not
#                   need the network" and "happened to have it"
#   full build      run_all --quick, which is EVERY phase except the one declared
#                   NETWORK phase ("Agriculture air pollutants") - the offline
#                   build IS the full product set
#   PDFs            make papers (latexmk, local TeX Live), BEFORE the tests -
#                   the PDF-freshness test is mtime-based and must see the PDFs
#                   rebuilt after the build refreshed their figure sources; PDFs
#                   are declared non-byte-stable (embedded CreationDate), so the
#                   record is build-success + hashes, never byte equality
#   full tests      python3 -m unittest discover tests, inside the clone
#   comparison      git status over tracked files with the SAME two declared
#                   exceptions the quick gate checks (NetCDF byte churn;
#                   the manifest's describes_commit block) - anything else FAILS
#
# Every step lands in $WORK/clean_room_result.json whether it passes or fails;
# scripts/make_rebuild_log.py turns that into the published rebuild log. The
# workdir is kept on failure for inspection.
#
# Usage:  bash scripts/clean_room_full.sh [workdir]
set -uo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
WORK="${1:-$(mktemp -d /tmp/pakemis_clean_room_full.XXXXXX)}"
CLONE="$WORK/clone"
RESULT="$WORK/clean_room_result.json"
STEPS="$WORK/steps.tsv"
mkdir -p "$WORK"
: > "$STEPS"

note() { echo "$1"; }
step() {  # step <name> <status> <detail>
    printf '%s\t%s\t%s\n' "$1" "$2" "$3" >> "$STEPS"
}

fail_out() {  # assemble the result JSON and exit 1 - failures are recorded, not lost
    write_result "FAIL" "$1"
    echo "CLEAN-ROOM FAIL: $1"
    echo "workdir kept for inspection: $WORK"
    exit 1
}

write_result() {  # write_result <verdict> <headline>
    VERDICT="$1" HEADLINE="$2" REPO="$REPO" WORK="$WORK" CLONE="$CLONE" \
    python3 - "$STEPS" > "$RESULT" <<'PYEOF'
import json, os, platform, subprocess, sys
steps = []
for line in open(sys.argv[1], encoding="utf-8"):
    name, status, detail = line.rstrip("\n").split("\t", 2)
    steps.append({"step": name, "status": status, "detail": detail})
def run(cmd, cwd=None):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd,
                              timeout=60).stdout.strip()
    except Exception as exc:
        return "unavailable: %s" % exc
clone = os.environ["CLONE"]
out = {
    "verdict": os.environ["VERDICT"],
    "headline": os.environ["HEADLINE"],
    "workdir": os.environ["WORK"],
    "environment": {
        "os": "%s %s (%s)" % (platform.system(), platform.release(), platform.machine()),
        "python": platform.python_version(),
        "git": run(["git", "--version"]),
        "git_lfs": run(["git", "lfs", "version"]),
        "latexmk": (run(["latexmk", "--version"]).splitlines() or ["unavailable"])[-1],
        "offline_proxy": "http(s)_proxy=http://127.0.0.1:9 exported for build and tests",
    },
    "clone": {
        "transport": "git clone file:// (full object walk)",
        "commit": run(["git", "rev-parse", "HEAD"], cwd=clone) if os.path.isdir(clone) else "",
        "tracked_files": run(["bash", "-c", "git ls-files | wc -l"], cwd=clone).strip()
                         if os.path.isdir(clone) else "",
    },
    "steps": steps,
}
print(json.dumps(out, indent=1, sort_keys=True))
PYEOF
}

echo "full clean-room reconstruction in $WORK"

# --- 1. fresh clone --------------------------------------------------------------
if GIT_LFS_SKIP_SMUDGE=1 git clone --quiet "file://$REPO" "$CLONE"; then
    step "clone" "OK" "file:// transport, $(git -C "$CLONE" rev-parse --short HEAD), $(git -C "$CLONE" ls-files | wc -l | tr -d ' ') tracked files"
else
    step "clone" "FAIL" "git clone file://$REPO failed"
    fail_out "the fresh clone itself failed"
fi

# --- 2. LFS materialisation + pointer preflight -----------------------------------
if [ -d "$REPO/.git/lfs/objects" ]; then
    # trailing /. : the clone's own lfs init already made .git/lfs/objects, and
    # cp -R <dir> <existing-dir> would nest a second objects/ inside it - the first
    # run's preflight caught exactly that
    mkdir -p "$CLONE/.git/lfs/objects"
    cp -R "$REPO/.git/lfs/objects/." "$CLONE/.git/lfs/objects/"
    ( cd "$CLONE" && git lfs checkout >/dev/null 2>&1 )
    step "lfs_materialise" "OK" "$(find "$CLONE/.git/lfs/objects" -type f | wc -l | tr -d ' ') objects copied from the invoking repository (no remote holds them until the branch is pushed)"
else
    step "lfs_materialise" "SKIP" "invoking repository has no .git/lfs/objects"
fi
POINTERS=""
while IFS= read -r f; do
    [ -f "$CLONE/$f" ] || continue
    if head -c 40 "$CLONE/$f" | grep -q "^version https://git-lfs" ; then
        POINTERS="$POINTERS $f"
    fi
done < <(git -C "$CLONE" lfs ls-files -n 2>/dev/null || true)
if [ -n "$POINTERS" ]; then
    step "lfs_preflight" "FAIL" "unsmudged pointers:$POINTERS"
    fail_out "LFS pointer files would poison the document hashes:$POINTERS"
fi
step "lfs_preflight" "OK" "no tracked file is an unsmudged LFS pointer"

# --- 3. fresh environment ---------------------------------------------------------
python3 -m venv "$WORK/venv"
# shellcheck disable=SC1091
source "$WORK/venv/bin/activate"
python3 -m pip install --quiet --upgrade pip
python3 -m pip install --quiet -r "$CLONE/requirements.lock" \
    || { step "venv" "FAIL" "pip install -r requirements.lock failed"; fail_out "pinned install failed"; }
python3 -m pip install --quiet --no-deps -e "$CLONE" \
    || { step "venv" "FAIL" "pip install -e clone failed"; fail_out "editable install failed"; }
PYV="$(python3 -c 'import platform; print(platform.python_version())')"
case "$PYV" in
    3.11.*) step "venv" "OK" "Python $PYV + requirements.lock ($(grep -c '==' "$CLONE/requirements.lock") pins)";;
    *)      step "venv" "WARN" "Python $PYV is not the 3.11.x the release run recorded (3.11.10); proceeding, recorded";;
esac

# --- 4. offline proof -------------------------------------------------------------
export http_proxy="http://127.0.0.1:9" https_proxy="http://127.0.0.1:9"
export HTTP_PROXY="$http_proxy" HTTPS_PROXY="$https_proxy" no_proxy="" NO_PROXY=""
step "offline_proof" "OK" "unroutable proxy exported; any network attempt in build or tests fails loudly"

# --- 5. full offline build --------------------------------------------------------
cd "$CLONE"
if python3 -m pkinv.run_all --quick > "$WORK/run_all.log" 2>&1; then
    step "run_all" "OK" "every offline phase (the full product set; the one declared NETWORK phase is the only skip); log: $WORK/run_all.log"
else
    step "run_all" "FAIL" "see $WORK/run_all.log (phase table at the end)"
    fail_out "run_all failed inside the clone"
fi

# --- 6. PDFs (before the tests: test_every_distributed_pdf_is_newer_than_its_sources is mtime-based, and a rebuild that regenerates figure sources then tests before rebuilding PDFs fails on ordering, not content) ----------------------------------------------------------------------
if command -v latexmk >/dev/null 2>&1; then
    if make papers > "$WORK/papers.log" 2>&1; then
        PDFHASHES="$(shasum -a 256 papers/pdf/*.pdf | shasum -a 256 | cut -d' ' -f1)"
        step "pdfs" "OK" "make papers succeeded; $(ls papers/pdf/*.pdf | wc -l | tr -d ' ') PDFs built; combined sha256 $PDFHASHES (declared non-byte-stable: embedded CreationDate)"
    else
        step "pdfs" "FAIL" "make papers failed; see $WORK/papers.log"
        fail_out "the PDF build failed inside the clone"
    fi
else
    step "pdfs" "SKIP" "latexmk not on PATH in this environment"
fi

# --- 7. full test suite -----------------------------------------------------------
if python3 -m unittest discover tests > "$WORK/tests.log" 2>&1; then
    TESTLINE="$(grep -E '^Ran [0-9]+ tests' "$WORK/tests.log" | tail -1)"
    step "tests" "OK" "$TESTLINE, all green, inside the clone, offline"
else
    TESTLINE="$(tail -3 "$WORK/tests.log" | tr '\n' ' ')"
    step "tests" "FAIL" "$TESTLINE (full log: $WORK/tests.log)"
    fail_out "the test suite failed inside the clone"
fi

# --- 8. comparison ----------------------------------------------------------------
CHANGED="$(git status --porcelain --untracked-files=no | awk '{$1=""; sub(/^ /,""); print}')"
CUBE="outputs/pakemis_grid_0p05_monthly.nc"
MANIFEST="outputs/release_manifest.json"
# the PDF build rewrites papers/pdf and its .bbl companions; those are declared
# non-byte-stable and recorded by hash above, so they are excluded from the
# byte-equality verdict the way the quick gate excludes nothing it did not build
# the exclusion classes mirror scripts/release_fixpoint.py's ARTIFACT_PATTERNS
# exactly: everything the PDF build rewrites in place, including the national
# paper OUTSIDE papers/pdf/ - run 3 failed on precisely that omission
DATA_CHANGED="$(echo "$CHANGED" | grep -vE '^papers/pdf/|\.bbl$|^outputs/pakemis_paper_hashes\.csv$|^paper_common/release_cover\.tex$|^paper_national/[^/]+\.pdf$|^papers/[^/]+/(paper|supplement)\.pdf$' || true)"

MANIFEST_ONLY_COMMIT=0
if [ "$DATA_CHANGED" = "$MANIFEST" ]; then
    SUBSTANTIVE="$(git diff -U0 -- "$MANIFEST" \
        | grep -E '^[+-]' | grep -vE '^(\+\+\+|---)' \
        | grep -vE '"(describes_commit|commit|tree_dirty|generated_at)"' || true)"
    [ -z "$SUBSTANTIVE" ] && MANIFEST_ONLY_COMMIT=1
fi

if [ -z "$DATA_CHANGED" ]; then
    step "comparison" "OK" "every committed data output reproduced byte-for-byte"
    write_result "PASS" "the rebuild reproduced every committed output byte-for-byte in an empty environment, offline"
    echo "CLEAN-ROOM PASS (full): products, tests, PDFs all green; outputs byte-identical"
elif [ "$DATA_CHANGED" = "$CUBE" ]; then
    step "comparison" "OK" "only the NetCDF cube's bytes differ (content-deterministic; docs/spatial_products_contract.md)"
    write_result "PASS_WITH_NOTE" "byte-identical except the NetCDF cube's documented byte churn"
    echo "CLEAN-ROOM PASS (with the documented cube note)"
elif [ "$MANIFEST_ONLY_COMMIT" = "1" ]; then
    step "comparison" "OK" "manifest differs in the describes_commit block alone"
    write_result "PASS_WITH_NOTE" "byte-identical except the manifest's describes_commit block, which a clone at HEAD cannot reproduce by construction"
    echo "CLEAN-ROOM PASS (with the documented manifest note)"
else
    step "comparison" "FAIL" "$(echo "$DATA_CHANGED" | tr '\n' ' ')"
    fail_out "the rebuild changed tracked files the commit did not hold: $(echo "$DATA_CHANGED" | tr '\n' ' ')"
fi

echo "result JSON: $RESULT"
echo "  (workdir $WORK can be removed after the log is published)"
