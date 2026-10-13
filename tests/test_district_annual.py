"""District x year annual panel: the reconciliation invariant must hold for every category and year."""
import collections
import csv
import os
import sys
import unittest


from pkinv.sectors.agriculture.gis import district_annual as da  # noqa: E402


class TestDistrictAnnual(unittest.TestCase):
    def setUp(self):
        self.rows, self.years, self.national = da.build_panel()

    def test_reconciles_per_category_year(self):
        """Sigma over districts == national control, for every (category, year)."""
        agg = collections.defaultdict(float)
        for r in self.rows:
            agg[(r["year"], r["category"])] += r["co2e_Mt_AR5"]
        for (year, cat), got in agg.items():
            self.assertAlmostEqual(got, self.national[year][cat], places=6,
                                   msg="district sum != national for %s %s" % (cat, year))

    def test_covers_full_series(self):
        self.assertEqual(min(self.years), 1990)
        self.assertEqual(max(self.years), 2024)
        self.assertEqual(len(self.years), 35)

    def test_no_negative_emissions(self):
        self.assertTrue(all(r["co2e_Mt_AR5"] >= 0 for r in self.rows))

    def test_2024_matches_static_district_panel(self):
        """The 2024 slice reproduces the audited outputs/district_totals_2024.csv to input rounding.

        The panel reconciles exactly to the 1990-2024 series (national rounded to 2 dp there); the
        static 2024 panel is rounded independently, so agreement is expected only to ~2 dp (the
        worst per-row gap is <0.001 Mt out of a 221.7 Mt inventory)."""
        base = {(r["district"], r["category"]): float(r["co2e_Mt_AR5"])
                for r in csv.DictReader(open(da.BASE_CSV, newline="", encoding="utf-8"))}
        for r in self.rows:
            if r["year"] != 2024:
                continue
            self.assertAlmostEqual(r["co2e_Mt_AR5"], base[(r["district"], r["category"])], places=2)

    @unittest.skipUnless(os.path.exists(da.OUT_CSV), "panel not built")
    def test_written_panel_reconciles(self):
        """The persisted CSV also reconciles to the national total each year (national sum)."""
        by_year = collections.defaultdict(float)
        for r in csv.DictReader(open(da.OUT_CSV, newline="", encoding="utf-8")):
            by_year[int(r["year"])] += float(r["co2e_Mt_AR5"])
        for year, got in by_year.items():
            nat = sum(self.national[year].values())
            self.assertAlmostEqual(got, nat, places=2, msg="written panel != national for %d" % year)


if __name__ == "__main__":
    unittest.main()
