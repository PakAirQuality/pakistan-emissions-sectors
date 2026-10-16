"""Agriculture timing classifications are tied to the final exported coverage panel.

Unresolved timing counts only TE4 mass from a process that should vary; calendar
allocation of a continuous process is not evidence of missing seasonal activity.
"""
import csv
import os
import unittest

from _support import OUTPUTS, ROOT, read_rows

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

    def test_the_unobserved_share_matches_final_coverage_records(self):
        coverage = [r for r in read_rows(os.path.join(OUTPUTS, "pakemis_monthly_coverage.csv"))
                    if r["sector_id"] == "agriculture"]
        variable = {r["category"] for r in self.cats
                    if r["activity_should_vary_but_unobserved"] == "yes"}
        for suffix, rows in (("panel", coverage), ("reference_year", [r for r in coverage
                             if r["period_id"] == "FY2023-24"])):
            total = sum(float(r["co2e_Mt_AR5"]) for r in rows)
            unresolved = sum(float(r["co2e_Mt_AR5"]) for r in rows
                             if r["category"] in variable and r["temporal_evidence_class"] == "TE4")
            self.assertAlmostEqual(float(self.total["unobserved_pct_" + suffix]),
                                   100 * unresolved / total, places=4)
        self.assertEqual(len({r["period_id"] for r in coverage}), 10)
        self.assertTrue(all("nine_years" not in field for field in self.total))

    def test_the_continuous_processes_contribute_no_unobserved_timing(self):
        """The whole point: a flat month of a stock-driven process is not a gap. If these
        ever contributed, the physical class would have stopped doing its job."""
        for r in self.cats:
            if r["physical_timing_class"] == "continuous_by_process":
                self.assertEqual(float(r["unobserved_Mt_panel"]), 0.0, r["category"])
                self.assertEqual(r["activity_should_vary_but_unobserved"], "no", r["category"])

    def test_managed_soils_is_the_gap(self):
        soils = next(r for r in self.cats if r["category"] == "Managed soils")
        self.assertEqual(soils["activity_should_vary_but_unobserved"], "yes")
        self.assertGreater(float(soils["unobserved_Mt_panel"]), 100.0)

    def test_the_categories_sum_to_the_total_row(self):
        for column in ("co2e_Mt_panel", "unobserved_Mt_panel",
                       "co2e_Mt_reference_year", "unobserved_Mt_reference_year"):
            self.assertAlmostEqual(sum(float(r[column]) for r in self.cats),
                                   float(self.total[column]), places=4, msg=column)

    def test_the_reference_year_total_is_the_published_sector_total(self):
        """Ties this product to the inventory rather than letting it drift as a side table."""
        rows = [r for r in read_rows(os.path.join(OUTPUTS, "pakemis_monthly_coverage.csv"))
                if r["sector_id"] == "agriculture" and r["period_id"] == "FY2023-24"]
        self.assertAlmostEqual(float(self.total["co2e_Mt_reference_year"]),
                               sum(float(r["co2e_Mt_AR5"]) for r in rows), places=4)


class TestTheFireProfilesAreYearSpecific(unittest.TestCase):
    """The prose said the reference year's profile was the fire record, and that a year
    without a fetched season stays flat at T4. Neither describes the current product: the current panel records own-year FRP-weighted VIIRS profiles and labels any carried
    profile explicitly."""

    def test_each_supported_period_has_a_complete_profile(self):
        rows = [r for r in read_rows(os.path.join(OUTPUTS, "pakemis_temporal_profiles.csv"))
                if r["category"] == "Field burning of residues"]
        self.assertTrue(rows)
        by_year = {}
        for r in rows:
            by_year.setdefault(r["fiscal_year"], {})[r["month"]] = r["weight"]
        periods = read_rows(os.path.join(ROOT, "data", "shared", "lookups", "periods.csv"))
        self.assertEqual(set(by_year), {r["period_id"] for r in periods})
        for year, weights in by_year.items():
            self.assertEqual(len(weights), 12, year)
            self.assertAlmostEqual(sum(float(v) for v in weights.values()), 1., places=8)

    def test_classes_match_actual_held_fire_window_coverage(self):
        from pkinv.sectors.agriculture.monthly import FIRMS_FIRE
        held_years = set()
        for detection in read_rows(FIRMS_FIRE):
            year, month = int(detection["acq_date"][:4]), int(detection["acq_date"][5:7])
            held_years.add(year if month >= 7 else year - 1)
        rows = [r for r in read_rows(os.path.join(OUTPUTS, "pakemis_temporal_profiles.csv"))
                if r["category"] == "Field burning of residues"]
        for row in rows:
            own_year = int(row["fiscal_year"][2:6]) in held_years
            self.assertEqual(row["temporal_evidence_class"], "TE3" if own_year else "TE4")
            self.assertEqual(row["borrowed_from_year"], "")
            if not own_year:
                import calendar
                year, month = int(row["month"][:4]), int(row["month"][4:])
                fy = int(row["fiscal_year"][2:6])
                days = 366 if calendar.isleap(fy + 1) else 365
                self.assertAlmostEqual(float(row["weight"]),
                                       calendar.monthrange(year, month)[1] / days, places=10)
                self.assertIn("no monthly series", row["basis"])

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
