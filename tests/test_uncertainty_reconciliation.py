"""The uncertainty reconciliation table: two medians, named families, no ambiguity.

The contract: every module appears once; the fugitives row reproduces both published
medians from their own sources and is the ONLY row with a different sector-level
family (if a second appears, the table must say why, and this test must be extended
deliberately); rows sharing the national family explain their gap; and the product
regenerates identically.
"""
import csv
import os
import unittest
from pkinv.core.io import read_rows
from _support import OUT, ROOT



def _rows(name):
    return read_rows(os.path.join(OUT, name), comments=False)


class TestUncertaintyReconciliation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = _rows("national_uncertainty_reconciliation.csv")

    def test_every_module_appears_once(self):
        modules = [r["module"] for r in self.table]
        self.assertEqual(len(modules), len(set(modules)))
        national = {r["sector"] for r in _rows("national_all_sectors.csv")
                    if r["sector"] != "TOTAL"}
        self.assertEqual(set(modules), national)

    def test_the_fugitives_row_reproduces_both_medians(self):
        row = next(r for r in self.table if r["module"] == "fugitives")
        sector = next(r for r in _rows("fugitives_uncertainty_2024.csv")
                      if r["segment"] == "TOTAL")
        self.assertAlmostEqual(float(row["sector_p50_Mt"]), float(sector["p50"]),
                               places=3)
        self.assertEqual(row["sector_distribution"], sector["distribution"])
        national = next(r for r in _rows("national_uncertainty_montecarlo.csv")
                        if r["scenario"] == "within_sector"
                        and r["aggregation_level"] == "module"
                        and r["name"] == "fugitives")
        self.assertEqual(float(row["national_p50_Mt"]), float(national["P50_Mt"]))
        self.assertEqual(row["national_distribution"], national["distribution_id"])
        # rc12 inverted this row's meaning: the national engine now consumes the
        # sector's own draw file, so the families MATCH and the gap is draw count.
        self.assertEqual(row["sector_distribution"], row["national_distribution"])
        self.assertIn("SAME DRAWS BY CONSTRUCTION", row["why"])
        self.assertLess(abs(float(row["median_gap_Mt"])), 0.1)

    def test_the_injected_modules_are_the_only_different_families(self):
        """Until rc12 this asserted fugitives was the ONE module with a different
        sector-level family. Injection retired that finding: fugitives and waste
        now carry their sector engines' families in the national rows too, and
        this asserts exactly that set - a third member means a new native engine
        appeared and should be considered for injection, deliberately."""
        different = sorted(r["module"] for r in self.table
                           if r["sector_distribution"]
                           and r["sector_distribution"] != "mean_preserving_lognormal")
        self.assertEqual(different, ["fugitives", "waste"],
                         "the set of native sector-level families moved; decide "
                         "injection for the newcomer and extend this test "
                         "deliberately")
        for r in self.table:
            if r["module"] in ("fugitives", "waste"):
                self.assertEqual(r["sector_distribution"],
                                 r["national_distribution"], r["module"])

    def test_every_row_says_why(self):
        for row in self.table:
            self.assertTrue(row["why"].strip(), row["module"])

    def test_the_product_regenerates_identically(self):
        from pkinv.report import uncertainty_reconciliation as ur
        fresh = ur.build()
        self.assertEqual(len(fresh), len(self.table))
        for f_row, s_row in zip(fresh, self.table):
            for col in ur.FIELDS:
                self.assertEqual(str(f_row[col]), s_row[col],
                                 "%s.%s" % (f_row["module"], col))


if __name__ == "__main__":
    unittest.main()
