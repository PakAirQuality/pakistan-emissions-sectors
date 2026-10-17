"""The deposit build group excludes exactly the phases that read the frozen sources tree.

Measured, not inferred (docs/deposit_rebuild_limits.md): with sources/ absent, two registered
phases cannot run and every sector engine can. The group is the full registry minus those two,
their products ship as inputs, and the exclusion list may not grow without a measurement.
"""
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestTheDepositGroup(unittest.TestCase):
    def test_it_excludes_only_explicit_primary_source_phases(self):
        from pkinv import build, run_all
        full = [p.label for p in build.phases_for_group("full")]
        deposit = [p.label for p in build.phases_for_group("deposit")]
        # rc69: a public clone without the restricted layers also seeds the phases that
        # declare a restricted read (build.absent_seeded; empty where the layers are mounted)
        self.assertEqual(sorted(set(full) - set(deposit)),
                         sorted(set(build.DEPOSIT_EXCLUDED) | build.absent_seeded()))
        self.assertEqual(set(build.DEPOSIT_EXCLUDED), set(build.DEPOSIT_SOURCE_PHASES))
        self.assertTrue(all(build.DEPOSIT_SOURCE_PHASES.values()))
        self.assertTrue(set(build.DEPOSIT_EXCLUDED) <= {p.label for p in run_all.PHASES})

    def test_without_the_layers_the_release_phases_are_seeded(self):
        """rc69: the release category describes the whole release, restricted documents
        included, so a public clone reuses its committed products instead of rebuilding a
        description of a smaller tree. Forced to absent mode here, whatever this checkout is."""
        from unittest import mock
        from pkinv import build, run_all
        from pkinv.core import layers
        with mock.patch.object(layers, "mode", return_value="absent"):
            deposit = {p.label for p in build.phases_for_group("deposit")}
        release = {p.label for p in run_all.PHASES if p.category == "release"}
        self.assertIn("Release manifest", release)
        self.assertFalse(release & deposit)
        science = {p.label for p in run_all.PHASES if p.category == "science"}
        self.assertTrue(science & deposit)

    def test_a_deposit_tree_is_not_a_public_clone(self):
        """rc69: the clean rebuild and a reader's unpacked deposit have no layers either, but
        they carry every deposited file, the COD-AB boundaries included. Seeding the release
        category there left ten products unbuilt in the first rc69 clean rebuild."""
        import tempfile
        from pkinv.core import layers
        with tempfile.TemporaryDirectory() as tree:
            self.assertEqual(layers.mode(tree), "absent")
            self.assertFalse(layers.public_clone_without_layers(tree))
            os.mkdir(os.path.join(tree, ".git"))
            self.assertTrue(layers.public_clone_without_layers(tree))

    def test_the_excluded_phases_products_are_tracked_inputs_or_shipped(self):
        """Their outputs must exist in the tree the deposit is cut from."""
        from pkinv import build, run_all
        for p in run_all.PHASES:
            if p.label in build.DEPOSIT_EXCLUDED:
                for w in p.writes:
                    self.assertTrue(os.path.exists(os.path.join(ROOT, w)), "%s: %s" % (p.label, w))

    def test_the_doc_names_both(self):
        text = open(os.path.join(ROOT, "docs", "deposit_rebuild_limits.md"), encoding="utf-8").read()
        from pkinv import build
        for label in build.DEPOSIT_EXCLUDED:
            self.assertIn(label, text)


if __name__ == "__main__":
    unittest.main()
