"""Guards that make the two-raw-trees redundancy safe until it is physically merged:

  * sources/ is the FROZEN legacy document tree - its git-tracked file list is
    pinned, so a new raw document cannot be dropped there by habit (it belongs in
    data/raw/<source>/);
  * no NEW cross-tree byte duplicate may appear - the 2026-09-10 OGRA sweep put
    nine reports into data/raw that sources/ already held; the current duplicate
    set (chiefly the legacy OCAC dual-tracking) is grandfathered in a baseline,
    and anything beyond it fails here.

The physical merge into one tree is a declared v1.0.0-boundary event (it re-hashes
the release manifest's document section); these guards hold the line until then.
"""

from pkinv.assets import asset_path
from pkinv.core import layers
from _support import require_layers
import collections
import csv
import os
import subprocess
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def read(path):
    with open(asset_path(ROOT, path), encoding="utf-8") as h:
        return [l for l in h if not l.startswith("#")]


def tracked_sources():
    """sources/ as git tracks it - in the repository that owns it. From rc69 that is the
    private checkout mounted beside a public clone (src/pkinv/core/layers.py), and a public
    clone's own `git ls-files sources` is empty by design, which would read as 'every
    pinned document removed'. Without the layers there is nothing to compare: skip, with
    the prefix tests/test_layers_exercised.py counts."""
    require_layers("the frozen sources/ tree")
    return set(layers.ls_files("sources"))


class SourcesTreeIsFrozen(unittest.TestCase):
    def test_no_document_was_added_to_the_legacy_tree(self):
        pinned = set(l.strip() for l in read("data/sources_freeze.txt") if l.strip())
        tracked = tracked_sources()
        added = sorted(tracked - pinned)
        self.assertFalse(added,
            "new raw documents go to data/raw/<source>/ - sources/ is the frozen legacy "
            "tree: %s" % added[:10])

    def test_no_document_was_removed_from_the_legacy_tree(self):
        """THE OTHER DIRECTION, missing until rc65. The test above compared tracked - pinned
        and nothing compared pinned - tracked, so a document deleted from sources/ failed
        no test at all, and the message above even told the reader to edit the freeze list
        "for a deliberate removal". There is no deliberate removal: a held document is never
        deleted (tests/test_document_retention.py), and frozen means frozen both ways."""
        pinned = set(l.strip() for l in read("data/sources_freeze.txt") if l.strip())
        tracked = tracked_sources()
        removed = sorted(pinned - tracked)
        self.assertFalse(removed,
            "documents pinned in data/sources_freeze.txt are no longer tracked under "
            "sources/. Restore them; nothing in that tree is ever deleted: %s" % removed[:10])


class NoNewCrossTreeDuplicates(unittest.TestCase):
    def test_only_the_grandfathered_duplicates_exist(self):
        by_sha = collections.defaultdict(list)
        for r in csv.DictReader(read("data/raw_manifest.csv")):
            if r["path"].startswith(("sources/", "data/raw/")):
                by_sha[r["sha256"]].append(r["path"])
        current = {" | ".join(sorted(p)) for p in by_sha.values()
                   if len({"sources" if x.startswith("sources/") else "raw" for x in p}) > 1}
        baseline = {r["paths"] for r in csv.DictReader(read("data/cross_tree_duplicates_baseline.csv"))}
        new = sorted(current - baseline)
        self.assertFalse(new,
            "a document is byte-identical under BOTH sources/ and data/raw/ - use the held "
            "copy, do not re-acquire (run scripts/holdings.py first): %s" % new)




class TheLookupToolExists(unittest.TestCase):
    def test_holdings_script_is_present_and_gates_on_hits(self):
        script = os.path.join(ROOT, "scripts", "holdings.py")
        self.assertTrue(os.path.exists(script))
        hit = subprocess.run(["python3", script, "ocac"], capture_output=True, text=True)
        self.assertEqual(hit.returncode, 0)
        miss = subprocess.run(["python3", script, "zznonexistentzz"], capture_output=True, text=True)
        self.assertEqual(miss.returncode, 1)

    def test_every_layer_of_the_four_layer_gate_reports(self):
        """Exit codes are not enough: a DEAD layer still leaves them right.

        The sector-layout migration emptied data/activity/, which holdings.py walked, so
        the verified-ingest layer printed "0 table(s)" for every keyword while the registry
        layers kept the exit code at 0. The gate looked healthy and had stopped answering
        the question it exists for - whether a table is already ingested. Assert each layer
        can actually find something, on a keyword the repository certainly holds.
        """
        script = os.path.join(ROOT, "scripts", "holdings.py")
        out = subprocess.run(["python3", script, "ocac"],
                             capture_output=True, text=True, check=True).stdout
        layers = {}
        for line in out.splitlines():
            if not line.startswith("== "):
                continue
            label, _, count = line[3:].rpartition(": ")
            layers[label] = int(count.split()[0]) if count.split()[0].isdigit() else 0
        self.assertGreaterEqual(len(layers), 6, "holdings.py stopped printing its layers:\n" + out)
        silent = sorted(name for name, found in layers.items() if found == 0)
        self.assertFalse(silent, "holdings layer(s) found nothing for a keyword the "
                         "repository holds, so they are not searching what they name: %s" % silent)


if __name__ == "__main__":
    unittest.main()
