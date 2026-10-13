"""Tests for the Climate TRACE independent benchmark (3rd validation axis).

Guarantees: Climate TRACE rows are present for the core categories + TOTAL; the regenerated
benchmark_comparison has finite ratios in a sane range; and adding a benchmark changes NO engine
magnitude (the national total is untouched -- a benchmark is a cross-check, never a control).
"""

from pkinv.assets import asset_path
import csv
import os
import unittest
from _support import ROOT


def _agriculture_total_Mt():
    """The sector total, from the engine rather than from a literal.

    This was pinned at 221.09 and 221.22 across four test files, and every one of them broke
    when the sector was harmonised onto FY2023-24 - a change in the reporting period, not in
    any of the properties these tests exist to protect. The magnitude belongs to the engine;
    what a benchmark test owns is whether the benchmark moves it."""
    from pkinv.core import registry
    from pkinv.core.components import enrich_co2e
    sector = registry.get("agriculture")
    comps = sector.build_components(sector.load_data())
    enrich_co2e(comps)
    return sum(c["co2e_Mt_AR5"] for c in comps)

BENCH = asset_path(ROOT, "data", "benchmarks.csv")
COMPARISON = os.path.join(ROOT, "outputs", "national_benchmark_comparison.csv")
NATIONAL = os.path.join(ROOT, "outputs", "national_totals_2024.csv")
CORE = {"Enteric fermentation", "Manure management", "Rice cultivation", "Managed soils", "TOTAL"}


class TestClimateTraceBenchmark(unittest.TestCase):
    def test_rows_present_for_core_categories(self):
        cats = {r["engine_category"] for r in csv.DictReader(open(BENCH)) if r["source"] == "Climate TRACE"}
        self.assertTrue(CORE <= cats, "missing Climate TRACE rows: %s" % (CORE - cats))

    def test_total_agrees_with_edgar_order(self):
        rows = {r["engine_category"]: r for r in csv.DictReader(open(BENCH)) if r["source"] == "Climate TRACE"}
        ct_total = float(rows["TOTAL"]["value_Mt_co2e"])
        self.assertTrue(240 <= ct_total <= 280)          # ~261, in the EDGAR neighbourhood

    @unittest.skipUnless(os.path.exists(COMPARISON), "national_benchmark_comparison.csv absent (run national_rollup)")
    def test_comparison_ratios_sane(self):
        ct = [r for r in csv.DictReader(open(COMPARISON)) if r["source"] == "Climate TRACE"]
        self.assertTrue(ct)
        for r in ct:
            if r["ratio_engine_over_benchmark"] not in ("n/a", "", "not comparable"):
                ratio = float(r["ratio_engine_over_benchmark"])
                self.assertTrue(0.2 <= ratio <= 3.0, "%s ratio %s" % (r["engine_category"], ratio))

    def test_engine_total_unchanged(self):
        tot = {r["category"]: r for r in csv.DictReader(open(NATIONAL))}["TOTAL"]
        self.assertAlmostEqual(float(tot["co2e_Mt_AR5"]), _agriculture_total_Mt(), delta=0.3,
                               msg="a benchmark must not move the engine")


if __name__ == "__main__":
    unittest.main()
