#!/usr/bin/env bash
# Copy every raw input to a second physical location, then prove the copy is good.
#
# WHY THIS EXISTS SEPARATELY FROM GIT. Git now tracks all 3.2 GB under sources/, and that is
# worth having - it hashes them, versions them and makes a silent edit visible. It is not a
# backup. A tracked file and its .git object sit on the SAME disk, and this project's disk is
# 89 percent full with no cloud copy of anything. One drive failure takes both copies and the
# 9.1 GB ODbL cache that git deliberately does not hold.
#
# So: one command, driven by the manifest rather than by a directory sweep, followed by a
# verification pass against the copy. An unverified mirror is a directory that looks about the
# right size, which is not the same as a backup and fails in exactly the case you need it.
#
# Usage:  scripts/mirror_raw_data.sh /Volumes/YourDrive/pakemis-raw [--quick]
#
# Re-running is cheap: rsync copies only what changed. Run it after any acquisition.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# RESOLVED, not hardcoded. This line held the register's old top-level location as a
# literal until the sector layout moved it under data/catalog/, and then this script - the project's only
# off-machine backup, for 12.87 GB with no cloud copy - failed on its first check while the
# hint below sent the operator round in a circle. A shell script gets neither the Python
# alias shim nor tests/test_asset_path_discipline.py's *.py scan, so it asks the shim
# directly and the next relocation cannot break it either.
MANIFEST="$(PYTHONPATH="$ROOT/src" python3 -c \
    'from pkinv.assets import resolve; print(resolve("data/raw_manifest.csv"))')"

if [ $# -lt 1 ]; then
    echo "usage: $(basename "$0") TARGET_DIR [--quick]" >&2
    echo >&2
    echo "TARGET_DIR should be on a DIFFERENT physical device from $ROOT." >&2
    echo "Copying to the same disk protects against an accidental delete and against" >&2
    echo "nothing else." >&2
    exit 2
fi

TARGET="$1"
shift
QUICK=""
[ "${1:-}" = "--quick" ] && QUICK="--quick"

if [ ! -f "$MANIFEST" ]; then
    echo "no manifest at $MANIFEST" >&2
    echo "the builder writes data/catalog/raw_manifest.csv - run: python3 scripts/raw_data_manifest.py" >&2
    exit 1
fi

mkdir -p "$TARGET"

# Warn where it matters rather than refusing: a same-device copy is still better than nothing
# if it is all that is available today, but the operator should know what it does not buy.
SOURCE_DEV="$(df -P "$ROOT" | awk 'NR==2 {print $1}')"
TARGET_DEV="$(df -P "$TARGET" | awk 'NR==2 {print $1}')"
if [ "$SOURCE_DEV" = "$TARGET_DEV" ]; then
    echo "WARNING: $TARGET is on the same device as the repository ($SOURCE_DEV)."
    echo "         This protects against deletion and not against drive failure."
    echo
fi

echo "mirroring the raw inputs named in ${MANIFEST#$ROOT/}"
echo "  from: $ROOT"
echo "  to:   $TARGET"
echo

# The manifest is the list, so a file nobody registered is a file nobody copies - which is the
# behaviour that makes the register load-bearing instead of decorative.
python3 - "$MANIFEST" <<'PY' > /tmp/pakemis_raw_paths.$$
import csv, sys
with open(sys.argv[1], newline="", encoding="utf-8") as handle:
    for row in csv.DictReader(handle):
        print(row["path"])
PY

rsync -ah --info=progress2 --files-from=/tmp/pakemis_raw_paths.$$ "$ROOT/" "$TARGET/"
rm -f /tmp/pakemis_raw_paths.$$

echo
echo "verifying the copy against the manifest"
python3 "$ROOT/scripts/verify_raw_data.py" --root "$TARGET" $QUICK
