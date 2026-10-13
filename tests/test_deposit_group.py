"""The deposit build group excludes exactly the phases that read the frozen sources tree.

Measured, not inferred (docs/deposit_rebuild_limits.md): with sources/ absent, two registered
phases cannot run and every sector engine can. The group is the full registry minus those two,
their products ship as inputs, and the exclusion list may not grow without a measurement.
"""
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestTheDepositGroup(unittest.TestCase):
    def test_it_is_full_minus_exactly_the_two_measured_phases(self):
        from pkinv import build, run_all
        full = [p.label for p in build.phases_for_group("full")]
        deposit = [p.label for p in build.phases_for_group("deposit")]
        self.assertEqual(sorted(set(full) - set(deposit)),
                         sorted(build.DEPOSIT_EXCLUDED))
        self.assertEqual(set(build.DEPOSIT_EXCLUDED),
                         {"Power plant workbooks", "OGRA gas-class series"})
        self.assertTrue(set(build.DEPOSIT_EXCLUDED) <= {p.label for p in run_all.PHASES})

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
