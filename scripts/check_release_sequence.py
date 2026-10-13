#!/usr/bin/env python3
"""Did the release dance happen in the right order? Checked from git, after the fact.

WHY THIS IS A SCRIPT AND NOT A TEST. The recorded test run is produced by running the suite
on the artifacts commit, so while it runs the committed record is necessarily the PREVIOUS
release's - that is the thing about to be replaced. A test asserting "the record's commit
follows the manifest's" therefore fails during every legitimate record, and the record then
captures its own failure. The first attempt did exactly that: it wrote FAILED into the
artifact it was meant to protect.

WHAT IT CATCHES. On 2026-10-05 a record taken against one artifacts commit was still in the
working tree when the next CONTENT commit ran `git add -A`, so it was committed inside that
content and described a tree two commits old - 3455 executed where the tree it shipped with
ran 3459. The record is fixpoint-written and carries no digest, so nothing else binds it to
the release it sits beside. Commit ORDER is the one thing a regeneration cannot fake.

    python3 scripts/check_release_sequence.py        # exits non-zero on a disordered release
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

RECORD = "outputs/pakemis_test_run.json"
MANIFEST = "outputs/release_manifest.json"


def _git(*args):
    return subprocess.run(("git",) + args, capture_output=True, text=True,
                          cwd=ROOT).stdout.strip()


def main():
    dirty = _git("status", "--porcelain", "--", RECORD, MANIFEST)
    if dirty:
        print("UNCOMMITTED: the record or the manifest is modified, so the release is "
              "mid-dance and its order is not yet decided:\n  %s" % dirty)
        return 0

    record = _git("log", "-1", "--format=%H", "--", RECORD)
    manifest = _git("log", "-1", "--format=%H", "--", MANIFEST)
    if not (record and manifest):
        print("no git history for the record or the manifest; nothing to check")
        return 0
    if record == manifest:
        print("REFUSING: the record and the manifest were committed together (%s). The "
              "record is produced by running the suite ON the artifacts commit, so it "
              "cannot be part of it." % manifest[:12])
        return 1

    ordered = subprocess.run(("git", "merge-base", "--is-ancestor", manifest, record),
                             cwd=ROOT).returncode == 0
    if not ordered:
        print("OUT OF ORDER: the record was last committed in %s, which does not follow the "
              "manifest's %s. The record describes a tree older than the artifacts it ships "
              "beside. Re-run scripts/record_test_run.py on the artifacts commit and commit "
              "it on its own." % (record[:12], manifest[:12]))
        return 1

    print("ordered: manifest %s -> record %s" % (manifest[:12], record[:12]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
