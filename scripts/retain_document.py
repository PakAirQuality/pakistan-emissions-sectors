#!/usr/bin/env python3
"""The retention ledger: every held source document, added once and never removed.

WHY THIS EXISTS. On 2026-10-12 a reviewer quoted this project's own manuscript back at it:
"some cited primary documents have not been retained". The audit that followed found the
documents had mostly never been saved, and it also found how little stood between a held
document and its disappearance. A file deleted from data/raw/ failed one test, until someone
re-ran scripts/raw_data_manifest.py, which rebuilt the manifest from the disk and dropped the
row. A file deleted from sources/ failed nothing: the freeze test compared in one direction.
In August a cleanup commit (c3d6ee44) removed 103 Climate TRACE responses and a code archive
because "nothing referenced" them, and every test stayed green.

A manifest regenerated from the disk cannot guard the disk. So this is a second list, and it
is written differently: data/catalog/document_retention.csv only GROWS. This script appends
the documents it does not yet list and has no mode that rewrites or removes a row.
tests/test_document_retention.py holds the tree to it:

  * every listed document is on disk at its recorded size (and digest, for small files);
  * every document under sources/ and data/raw/ is listed;
  * the ledger contains every row any earlier committed version of it contained;
  * scripts/raw_data_manifest.py refuses to write a manifest that has lost a listed path.

WHAT IT COVERS. The two document trees, sources/ and data/raw/. Not the records ABOUT
documents that live beside them and are meant to change (RETRIEVALS.csv, ACQUISITION_LOG_*,
*_SOURCES.json sidecars, README.md): those are logs, and a log that could not be appended to
would be useless.

THE RULE FOR PEOPLE. Nothing under those trees is deleted: not a duplicate, not a superseded
edition, not a file "nothing reads". A wrong file is corrected by adding the right one beside
it and saying so in the register.

first_held is the release under which a row was added. The ledger was started on
2026-10-12: documents already in the committed raw manifest that day carry
"1.0.0rc64-or-earlier", because the ledger cannot say when before then each arrived.

Usage:  python3 scripts/retain_document.py            add documents the ledger does not list
        python3 scripts/retain_document.py --verify   re-hash every listed document
"""
import csv
import hashlib
import os
import sys

from pkinv.assets import asset_path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(ROOT, "data", "catalog", "document_retention.csv")
MANIFEST = asset_path(ROOT, "data", "raw_manifest.csv")
FIELDS = ("path", "sha256", "bytes", "first_held")
TREES = ("sources/", "data/raw/")


def is_record(path):
    """True for a file that records documents and is meant to change, not a document."""
    name = os.path.basename(path)
    return (name == "RETRIEVALS.csv" or name == "README.md"
            or name.startswith("ACQUISITION_LOG_") or name.endswith("_SOURCES.json"))


def covered(path):
    return path.startswith(TREES) and not is_record(path)


def read_ledger(path=LEDGER):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8", newline="") as handle:
        return [r for r in csv.DictReader(handle)]


def held_documents():
    """[(path, sha256, bytes)] for every document the raw manifest lists under the trees."""
    with open(MANIFEST, encoding="utf-8", newline="") as handle:
        return [(r["path"], r["sha256"], r["bytes"]) for r in csv.DictReader(handle)
                if covered(r["path"])]


def release():
    import re
    with open(os.path.join(ROOT, "src", "pkinv", "__init__.py"), encoding="utf-8") as handle:
        found = re.search(r'(?m)^__version__\s*=\s*["\']([^"\']+)["\']', handle.read())
    return found.group(1) if found else "unknown"


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def verify():
    """Every listed document: present, the recorded size, the recorded digest."""
    problems = []
    rows = read_ledger()
    for row in rows:
        full = os.path.join(ROOT, row["path"])
        if not os.path.exists(full):
            problems.append("MISSING  %s" % row["path"])
        elif os.path.getsize(full) != int(row["bytes"]):
            problems.append("SIZE     %s" % row["path"])
        elif sha256(full) != row["sha256"]:
            problems.append("CONTENT  %s" % row["path"])
    for line in problems:
        print(line)
    print("retention ledger: %d documents, %d problems" % (len(rows), len(problems)))
    return 1 if problems else 0


def add():
    listed = {r["path"] for r in read_ledger()}
    new = [d for d in held_documents() if d[0] not in listed]
    if not new:
        print("retention ledger: %d documents, nothing to add" % len(listed))
        return 0
    fresh = not os.path.exists(LEDGER)
    stamp = release()
    with open(LEDGER, "a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        if fresh:
            writer.writerow(FIELDS)
        for path, digest, size in sorted(new):
            writer.writerow([path, digest, size, stamp])
    print("retention ledger: %d documents (+%d first held at %s)"
          % (len(listed) + len(new), len(new), stamp))
    return 0


if __name__ == "__main__":
    sys.exit(verify() if "--verify" in sys.argv[1:] else add())
