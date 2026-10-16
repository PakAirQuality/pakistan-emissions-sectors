#!/usr/bin/env python3
"""THE ONE LOOKUP for what this repo already holds. Run it BEFORE acquiring any
document or re-extracting any table:

    python3 scripts/holdings.py <keyword> [<keyword> ...]

It searches every holdings layer in one pass - the two raw trees, the verified
ingests, and the registries that map them - and prints per-layer hits. Exit code
is 0 when anything matched and 1 when nothing did, so acquisition scripts can
gate on it. The 2026-09-10 OGRA duplication (and the OCAC one before it)
happened because a human-shaped search covered one layer out of four; this
script exists so the search is never partial again.
"""

from pkinv.assets import asset_path, catalog
from pkinv.core import layers
import csv
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TREES = ("sources", asset_path("data", "raw"))
# The verified-ingest layer is enumerated from the asset catalog, NOT by walking a
# directory. It used to walk data/activity/, and when the sector layout moved those
# tables the walk found an empty directory and reported "0 table(s)" for every keyword
# while the registry layers kept the exit code at 0 - a false negative in the one gate
# that exists to stop a re-acquisition. A catalog query cannot go stale that way.
INGEST_LABEL = "verified ingests (sector activity)"
REGISTRIES = (
    asset_path("data", "source_documents.csv"),
    asset_path("data", "raw_manifest.csv"),
    asset_path("outputs", "pakemis_source_register.csv"),
)


def ingest_tables():
    """Every verified ingest table, by its CURRENT location, from the asset catalog.

    Both halves matter: rows that used to live under data/activity/ (some of which the
    sector layout classified as lookups or evidence rather than activity), and rows that
    now live in a sector's activity folder whether or not they ever sat under the old
    tree. A table added after the migration is therefore searched too.
    """
    tables = set()
    for row in catalog():
        path, legacy = row["path"], row["legacy_path"]
        if not path.endswith(".csv"):
            continue
        if (legacy.startswith("data/activity/")
                or path.startswith("data/shared/activity/")
                or (path.startswith("data/sectors/") and "/activity/" in path)):
            tables.add(path)
    return tables


def match(needles, text):
    low = text.lower()
    return any(n in low for n in needles)


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    needles = [a.lower() for a in argv[1:]]
    total = 0

    mounted = layers.present(ROOT)
    for tree in TREES:
        if not mounted:
            # rc69: a public clone without the restricted layers holds no documents, so it
            # cannot say a document is NOT held. Saying "0 file(s)" here would be the dead
            # layer this tool has already been caught reporting.
            print("== %s: NOT MOUNTED (restricted layers absent; docs/restricted_layers.md)"
                  % tree)
            continue
        hits = []
        for dirpath, _dirnames, filenames in os.walk(asset_path(ROOT, tree)):
            for name in filenames:
                rel = os.path.relpath(asset_path(dirpath, name), ROOT)
                if match(needles, rel):
                    hits.append(rel)
        print("== %s: %d file(s)" % (tree, len(hits)))
        for h in sorted(hits)[:20]:
            print("   ", h)
        if len(hits) > 20:
            print("    ... and %d more" % (len(hits) - 20))
        total += len(hits)

    ingest_hits = []
    for rel in sorted(ingest_tables()):
        path = os.path.join(ROOT, rel)
        if match(needles, rel):
            ingest_hits.append((rel, "filename"))
            continue
        try:
            with open(path, encoding="utf-8", errors="replace") as h:
                head = h.read(65536)
        except OSError:
            continue
        if match(needles, head):
            ingest_hits.append((rel, "content"))
    print("== %s: %d table(s)" % (INGEST_LABEL, len(ingest_hits)))
    for rel, how in sorted(ingest_hits)[:20]:
        print("    %s  (%s match)" % (rel, how))
    total += len(ingest_hits)

    for reg in REGISTRIES:
        path = asset_path(ROOT, reg)
        if not os.path.exists(path):
            print("== %s: (absent)" % reg)
            continue
        rows = []
        with open(path, encoding="utf-8", errors="replace") as h:
            for line in h:
                if line.startswith("#"):
                    continue
                if match(needles, line):
                    rows.append(line.strip())
        print("== %s: %d row(s)" % (reg, len(rows)))
        for r in rows[:8]:
            print("   ", re.sub(r"\s+", " ", r)[:160])
        if len(rows) > 8:
            print("    ... and %d more" % (len(rows) - 8))
        total += len(rows)

    print("\n%s: %d hit(s) across all layers%s"
          % ("/".join(argv[1:]), total,
             "" if total else " - NOTHING HELD; an acquisition would be genuinely new"))
    if not mounted:
        print("the document trees were not searched; mount them with "
              "python3 scripts/overlay.py link PATH before deciding to acquire anything")
        return 3
    return 0 if total else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
