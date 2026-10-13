"""Is every raw file still here, and still the file it was? Answerable, not assumed.

WHAT THIS IS FOR. `data/raw_manifest.csv` says the project holds 12.87 GB of raw inputs. That
claim is worth exactly as much as the last time somebody checked it, and nobody ever checks by
hand. This checks: every manifest row must exist, at the recorded size, hashing to the recorded
digest. A missing file, a truncated download, a half-copied mirror or a silently corrupted
archive all fail here rather than surfacing years later when someone tries to re-derive a
number from a source that no longer reads.

IT RUNS AGAINST A MIRROR TOO. Point `--root` at an external drive and the same manifest checks
the copy - which is the only way to know a backup is a backup rather than a directory that
looks about the right size.

WHY SIZE FIRST. A size mismatch is instant and a hash is not, so the fast check runs first and
reports the file as changed without spending a minute proving it. `--quick` stops there, which
is the sensible thing to run often; the full hash pass is what you run before trusting a mirror
or after a disk scare.

Exit status is 1 on any missing or altered file, so this can gate a build.

Usage:  python3 scripts/verify_raw_data.py [--root DIR] [--quick] [--package NAME]
Reads:  data/raw_manifest.csv
"""

from pkinv.assets import asset_path
import argparse
import csv
import os
import sys

from raw_data_manifest import OUT as MANIFEST, ROOT, sha256
from pkinv.core.io import read_rows


def rows(path=None):
    return read_rows(path or MANIFEST, comments=False)


def verify(root=ROOT, quick=False, package=None, manifest=None):
    """(problems, checked, bytes_checked). A problem is a string a human can act on."""
    problems, checked, total = [], 0, 0
    for row in rows(manifest):
        if package and row["package"] != package:
            continue
        target = asset_path(root, row["path"])
        if not os.path.exists(target):
            problems.append("MISSING   %s" % row["path"])
            continue
        size = os.path.getsize(target)
        if size != int(row["bytes"]):
            problems.append("SIZE      %s: %d bytes, manifest says %s"
                            % (row["path"], size, row["bytes"]))
            continue
        checked += 1
        total += size
        if quick:
            continue
        digest = sha256(target)
        if digest != row["sha256"]:
            problems.append("CONTENT   %s: sha256 %s, manifest says %s"
                            % (row["path"], digest[:16], row["sha256"][:16]))
    return problems, checked, total


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=ROOT,
                        help="verify a copy at this root instead of the repository")
    parser.add_argument("--quick", action="store_true",
                        help="check existence and size only, not content")
    parser.add_argument("--package", help="restrict to one manifest package")
    args = parser.parse_args(argv)

    problems, checked, total = verify(args.root, args.quick, args.package)
    where = os.path.relpath(args.root, ROOT) if args.root != ROOT else "this repository"
    print("verifying raw data in %s%s" % (where, " (size only)" if args.quick else ""))
    print("  %d files checked, %.2f GB" % (checked, total / 1024 ** 3))
    if problems:
        print("\n%d PROBLEM(S):" % len(problems))
        for line in problems[:40]:
            print("  %s" % line)
        if len(problems) > 40:
            print("  ... and %d more" % (len(problems) - 40))
        print("\nA raw input that is missing or altered cannot be re-derived from anything "
              "here. If this is a mirror, re-run the copy; if it is the repository, the "
              "source is gone and the register should say so rather than implying it is held.")
        return 1
    print("  every file present and unaltered")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    sys.exit(main())
