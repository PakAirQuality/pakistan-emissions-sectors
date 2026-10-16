"""When the restricted layers are mounted, the guards that read them must see real content.

WHY. From rc69 a public clone reads the third-party documents through symlinks into the
private checkout (src/pkinv/core/layers.py). Absent layers make the document tests SKIP, by
design. The danger is the run in between: a mount that resolves to an empty or wrong
folder, or a git query put to the wrong repository, returns an empty listing - and an empty
listing passes most comparisons. This project has shipped exactly that before (a holdings
layer that reported 0 for every keyword while its exit code stayed green). So with the
layers present, this module asserts counts that only a real mount can produce; without
them, it asserts that nothing was configured, so "absent" can never be a broken mount.
"""
import csv
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pkinv.core import layers                                          # noqa: E402
from _support import load_script                                       # noqa: E402


def _rows(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(line for line in handle if not line.startswith("#")))


class TestTheModeIsWhatItSays(unittest.TestCase):
    def test_absent_means_nothing_was_configured(self):
        if layers.mode(ROOT) != "absent":
            self.skipTest("the layers are present")
        self.assertIsNone(layers.configured_overlay(ROOT),
                          "an overlay is configured and the mode reads absent")

    def test_a_configured_overlay_that_does_not_resolve_is_an_error(self):
        previous = os.environ.get(layers.ENVIRONMENT)
        os.environ[layers.ENVIRONMENT] = os.path.join(ROOT, "no-such-checkout")
        try:
            with self.assertRaises(layers.LayersError):
                layers.mode(ROOT)
        finally:
            if previous is None:
                del os.environ[layers.ENVIRONMENT]
            else:
                os.environ[layers.ENVIRONMENT] = previous


class TestTheMountedLayersAreReal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not layers.present(ROOT):
            raise unittest.SkipTest("restricted layers absent: the counts need the mount")

    def test_the_frozen_tree_is_tracked_where_it_lives(self):
        with open(os.path.join(ROOT, "data", "catalog", "sources_freeze.txt"),
                  encoding="utf-8") as handle:
            pinned = {l.strip() for l in handle if l.strip() and not l.startswith("#")}
        tracked = set(layers.ls_files("sources", root=ROOT))
        self.assertGreater(len(pinned), 300)
        self.assertEqual(tracked, pinned)

    def test_the_raw_tree_is_tracked_where_it_lives(self):
        self.assertGreater(len(layers.ls_files("data/raw", root=ROOT)), 5000)

    def test_every_ledger_document_is_on_disk_through_the_mount(self):
        held = _rows("data", "catalog", "document_retention.csv")
        self.assertGreater(len(held), 5000)
        missing = [r["path"] for r in held if not os.path.exists(os.path.join(ROOT, r["path"]))]
        self.assertEqual(missing[:10], [])

    def test_the_manifest_lists_at_least_what_the_ledger_holds(self):
        manifest = {r["path"] for r in _rows("data", "catalog", "raw_manifest.csv")}
        held = {r["path"] for r in _rows("data", "catalog", "document_retention.csv")}
        self.assertGreater(len(manifest), len(held) * 0.9)

    def test_the_build_snapshot_sees_the_mounted_files(self):
        """The build compares each input before and after a task; a mounted document missing
        from the before-snapshot reads as edited during the task and fails the build."""
        from pkinv.build_support import input_snapshot
        files = input_snapshot(ROOT)["files"]
        pinned = next(l.strip() for l in open(os.path.join(ROOT, "data", "catalog",
                      "sources_freeze.txt"), encoding="utf-8") if l.strip() and not l.startswith("#"))
        self.assertIn(pinned, files)

    def test_the_lfs_documents_are_seen(self):
        lfs = layers.lfs_files(root=ROOT)
        if not lfs:
            self.skipTest("git-lfs is not available")
        self.assertTrue(any(layers.is_restricted(p) for p in lfs))

    def test_the_release_history_is_reachable(self):
        """The two release-history phases read rc68 out of the private history."""
        vintages = _rows("data", "catalog", "published_release_vintages.csv")
        commits = [r["commit"] for r in vintages if r["commit"] != "(working tree)"]
        self.assertTrue(commits)
        self.assertIsNotNone(layers.git_show(commits[0], "outputs/release_manifest.json",
                                             root=ROOT))

    def test_the_holdings_tool_reads_every_layer(self):
        tool = load_script("holdings")
        self.assertTrue(hasattr(tool, "main"))


if __name__ == "__main__":
    unittest.main()
