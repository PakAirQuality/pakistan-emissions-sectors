"""Tests for Phase 6 time series (1990-2024).

Reads the cached historical CSVs (data/activity/historical/) - run fetch_history.py first.
Run:  python3 -m unittest discover tests
"""
import csv
import os
import sys
import unittest


from pkinv.sectors.agriculture import timeseries as ts  # noqa: E402
from pkinv.sectors.agriculture.ef_library import InventoryData  # noqa: E402
from pkinv.sectors.agriculture.run_inventory import build_components  # noqa: E402

HIST = os.path.join(os.path.dirname(__file__), "..", "data", "activity", "historical")


@unittest.skipUnless(os.path.exists(os.path.join(HIST, "livestock_stocks.csv")),
                     "run fetch_history.py first")
class TestTimeseries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live, cls.crops, cls.nitro = ts._load_history()
        cls.years = [y for y in range(ts.START, ts.ANCHOR)
                     if y in cls.live and y in cls.nitro and y in cls.crops]
        data = InventoryData()
        cls.series = {}
        for y in (cls.years[0], cls.years[-1]):
            ts._apply_year(data, cls.live[y], cls.crops[y], cls.nitro[y])
            cat, gas = ts._aggregate(build_components(data))
            cls.series[y] = cat

    def test_history_spans_period(self):
        self.assertLessEqual(self.years[0], 1990)
        self.assertGreaterEqual(self.years[-1], 2022)

    def test_all_categories_each_year(self):
        for y in (self.years[0], self.years[-1]):
            self.assertEqual(set(self.series[y].keys()), set(ts.CATEGORIES))

    def test_enteric_rises_over_period(self):
        ent0 = self.series[self.years[0]]["Enteric fermentation"]
        ent1 = self.series[self.years[-1]]["Enteric fermentation"]
        self.assertGreater(ent1, ent0 * 1.5)  # Pakistan herds grew strongly since 1990

    def test_anchor_equals_standard_run(self):
        # the 2024 anchor must equal the standard census-based Tier 2 national total
        anchor = InventoryData()
        total = sum(c["co2e_Mt_AR5"] for c in build_components(anchor))
        self.assertTrue(210 < total < 225, "anchor total %.1f" % total)

    def test_category_reconciles_to_gas(self):
        # for the latest year, per-category co2e == sum of its gas-component co2e
        data = InventoryData()
        y = self.years[-1]
        ts._apply_year(data, self.live[y], self.crops[y], self.nitro[y])
        comp = build_components(data)
        cat, _ = ts._aggregate(comp)
        recompute = {}
        for c in comp:
            recompute[c["category"]] = recompute.get(c["category"], 0.0) + c["co2e_Mt_AR5"]
        for k in ts.CATEGORIES:
            self.assertAlmostEqual(cat[k], recompute[k], places=6)

    def test_faostat_enteric_validation_close(self):
        # engine enteric should track FAOSTAT within ~15% (same activity data)
        fa = {int(r["year"]): float(r["Enteric fermentation"])
              for r in csv.DictReader(open(os.path.join(HIST, "faostat_emissions.csv")))}
        y = self.years[-1]
        ratio = self.series[y]["Enteric fermentation"] / fa[y]
        self.assertTrue(0.85 <= ratio <= 1.15, "enteric ratio %.2f" % ratio)



class TestYearBasisColumn(unittest.TestCase):
    """The tenth review: the 1990-2024 series joins calendar-year FAOSTAT activity
    to a fiscal-year census anchor, and nothing on the row said so. The column is
    the fix - two closed values, the anchor fiscal, everything else calendar."""

    def test_every_row_declares_its_time_basis(self):
        import csv, os
        path = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "outputs", "timeseries_1990_2024.csv")
        with open(path, newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.assertTrue(rows)
        for r in rows:
            expected = ("fiscal_census_anchor" if r["year"] == "2024"
                        else "calendar_faostat")
            self.assertEqual(r["year_basis"], expected, r["year"])


if __name__ == "__main__":
    unittest.main()
