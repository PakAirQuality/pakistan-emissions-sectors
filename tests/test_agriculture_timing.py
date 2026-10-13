"""rc39 A8: the monthly product says which flat months are physics and which are ignorance.

87.3% of agriculture sits at TE4, which reads as a sector whose timing is almost entirely
unevidenced. It is not. Enteric fermentation and manure management are continuous processes
riding a census stock, and a flat month there is the physics rather than a gap - no
acquisition could improve it. The share whose timing this inventory SHOULD resolve and has
not is 6.67% of the nine-year panel and 7.00% of the reference year.

Both classifications had been computed for several releases and lived in two products at two
grains, so a reader had to know to join them. Quoting either alone misleads in opposite
directions: the TE count overstates the problem by more than an order of magnitude, and the
physical class alone hides that a real gap exists.
"""
import csv
import os
import unittest

from _support import OUTPUTS, read_rows

TIMING = "agriculture_timing_classes.csv"
RESIDUAL = "agriculture_nfdc_province_residual.csv"


def _timing():
    return read_rows(os.path.join(OUTPUTS, TIMING))


def _residual():
    return read_rows(os.path.join(OUTPUTS, RESIDUAL))


class TestBothClassificationsArePublished(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = _timing()
        cls.total = next(r for r in cls.rows if r["category"] == "TOTAL")
        cls.cats = [r for r in cls.rows if r["category"] != "TOTAL"]

    def test_every_category_carries_both_classes(self):
        self.assertEqual(len(self.cats), 6)
        for r in self.cats:
            self.assertTrue(r["temporal_evidence_classes"], r["category"])
            self.assertNotEqual(r["physical_timing_class"], "unclassified", r["category"])

    def test_the_unobserved_share_is_the_audited_figure(self):
        self.assertAlmostEqual(float(self.total["unobserved_pct_nine_years"]), 6.67, places=2)
        self.assertAlmostEqual(float(self.total["unobserved_pct_reference_year"]), 7.00,
                               places=2)

    def test_the_continuous_processes_contribute_no_unobserved_timing(self):
        """The whole point: a flat month of a stock-driven process is not a gap. If these
        ever contributed, the physical class would have stopped doing its job."""
        for r in self.cats:
            if r["physical_timing_class"] == "continuous_by_process":
                self.assertEqual(float(r["unobserved_Mt_nine_years"]), 0.0, r["category"])
                self.assertEqual(r["activity_should_vary_but_unobserved"], "no", r["category"])

    def test_managed_soils_is_the_gap(self):
        soils = next(r for r in self.cats if r["category"] == "Managed soils")
        self.assertEqual(soils["activity_should_vary_but_unobserved"], "yes")
        self.assertGreater(float(soils["unobserved_Mt_nine_years"]), 100.0)

    def test_the_categories_sum_to_the_total_row(self):
        for column in ("co2e_Mt_nine_years", "unobserved_Mt_nine_years",
                       "co2e_Mt_reference_year", "unobserved_Mt_reference_year"):
            self.assertAlmostEqual(sum(float(r[column]) for r in self.cats),
                                   float(self.total[column]), places=4, msg=column)

    def test_the_reference_year_total_is_the_published_sector_total(self):
        """Ties this product to the inventory rather than letting it drift as a side table."""
        self.assertAlmostEqual(float(self.total["co2e_Mt_reference_year"]), 223.454471,
                               places=4)


class TestTheFireProfilesAreYearSpecific(unittest.TestCase):
    """The prose said the reference year's profile was the fire record, and that a year
    without a fetched season stays flat at T4. Neither describes the current product: all
    nine years carry their own FRP-weighted VIIRS profile and the fallback has never fired."""

    def test_nine_distinct_profiles_none_borrowed(self):
        rows = [r for r in read_rows(os.path.join(OUTPUTS, "pakemis_temporal_profiles.csv"))
                if r["category"] == "Field burning of residues"]
        self.assertTrue(rows)
        self.assertEqual({r["borrowed_from_year"] for r in rows}, {""})
        by_year = {}
        for r in rows:
            by_year.setdefault(r["fiscal_year"], {})[r["month"]] = r["weight"]
        self.assertEqual(len(by_year), 9)
        distinct = {tuple(sorted(v.items())) for v in by_year.values()}
        self.assertEqual(len(distinct), 9, "a fire profile is shared between years")

    def test_every_year_is_te3(self):
        rows = [r for r in read_rows(os.path.join(OUTPUTS, "pakemis_temporal_profiles.csv"))
                if r["category"] == "Field burning of residues"]
        self.assertEqual({r["temporal_evidence_class"] for r in rows}, {"TE3"})

    def test_no_module_still_says_the_reference_year_carries_the_profile(self):
        import subprocess
        from pkinv.paths import ROOT
        out = subprocess.run(["grep", "-rn", "--include=*.py",
                              "reference year's profile", os.path.join(ROOT, "src")],
                             capture_output=True, text=True)
        self.assertFalse(out.stdout.strip(), out.stdout)


class TestTheNfdcResidualIsPublishedNotRenormalised(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = _residual()
        cls.total = next(r for r in cls.rows if r["month"] == "TOTAL")

    def test_the_residual_is_the_audited_figure(self):
        self.assertAlmostEqual(float(self.total["residual_tonnes"]), 15918.0, delta=1.0)
        self.assertAlmostEqual(float(self.total["residual_pct_of_national"]), 0.154917,
                               places=5)

    def test_it_is_resolved_by_month_and_product(self):
        cells = [r for r in self.rows if r["month"] != "TOTAL"]
        self.assertGreater(len(cells), 50)
        self.assertEqual(len({r["month"] for r in cells}), 12)
        self.assertGreater(len({r["product"] for r in cells}), 5)

    def test_the_cells_sum_to_the_total(self):
        cells = [r for r in self.rows if r["month"] != "TOTAL"]
        for column in ("national_tonnes", "provincial_sum_tonnes", "residual_tonnes"):
            self.assertAlmostEqual(sum(float(r[column]) for r in cells),
                                   float(self.total[column]), places=2, msg=column)

    def test_everything_is_assigned_and_nothing_renormalised(self):
        """The provinces are NOT scaled onto the national total. If they were, every
        residual would be zero and a real discrepancy would vanish into exact-looking
        shares."""
        for r in self.rows:
            self.assertEqual(r["assigned_to"], "Other/unallocated")
        self.assertNotEqual(float(self.total["residual_tonnes"]), 0.0)

    def test_urea_carries_most_of_it(self):
        urea = sum(float(r["residual_tonnes"]) for r in self.rows if r["product"] == "Urea")
        self.assertAlmostEqual(urea, 11591.0, delta=2.0)


if __name__ == "__main__":
    unittest.main()
