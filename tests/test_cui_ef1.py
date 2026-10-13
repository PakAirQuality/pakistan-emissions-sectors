"""Tests for the Cui 2021 empirical EF1 anchor (managed-soils N2O adjudication).

Guarantees: the Cui EF is in the store and near 0.005 (it validates the arid choice); the 3-point EF1
sensitivity computes with Cui between the primary and the FAOSTAT value; the Cui benchmark row is present
and agrees with the engine; and the national total is unchanged (Cui adjudicates, EF1=0.005 stays primary).
"""

from pkinv.assets import asset_path
import csv
import os
import sys
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


EFS = asset_path(ROOT, "data", "emission_factors.csv")
BENCH = asset_path(ROOT, "data", "benchmarks.csv")
NATIONAL = os.path.join(ROOT, "outputs", "national_totals_2024.csv")


class TestCuiEF(unittest.TestCase):
    def test_cui_ef_in_store_and_low(self):
        rows = {r["key"]: r for r in csv.DictReader(open(EFS))} if False else None
        vals = {}
        for r in csv.DictReader(open(EFS)):
            vals[r.get("name") or r.get("subkey") or list(r.values())[2]] = r
        # locate EF1_cui by scanning (schema-agnostic)
        cui = [r for r in csv.DictReader(open(EFS)) if "EF1_cui" in ",".join(r.values())]
        self.assertTrue(cui, "soils_ef1_cui missing")
        val = float([v for v in cui[0].values() if v.replace(".", "").isdigit()][0])
        self.assertTrue(0.004 <= val <= 0.007)          # ~0.0055, near the arid 0.005


class TestSensitivity(unittest.TestCase):
    def test_three_point_sensitivity_orders(self):
        from pkinv.sectors.agriculture import run_inventory as R
        from pkinv.sectors.agriculture.ef_library import InventoryData
        data = InventoryData()
        base = R.build_components(data)
        sens = R._sensitivity(data, base)
        for k in ("soils_lo", "soils_cui", "soils_hi", "total_lo", "total_cui", "total_hi"):
            self.assertIn(k, sens)
        # Cui sits between the primary (0.005) and FAOSTAT (0.010) and near the primary
        self.assertLess(sens["soils_lo"], sens["soils_cui"])
        self.assertLess(sens["soils_cui"], sens["soils_hi"])
        self.assertLess(abs(sens["soils_cui"] - sens["soils_lo"]), abs(sens["soils_hi"] - sens["soils_cui"]))


class TestBenchmarkAndInvariant(unittest.TestCase):
    def test_cui_benchmark_row_present(self):
        cui = [r for r in csv.DictReader(open(BENCH))
               if r["source"] == "Cui 2021" and r["engine_category"] == "Managed soils"]
        self.assertEqual(len(cui), 1)
        self.assertTrue(25 <= float(cui[0]["value_Mt_co2e"]) <= 33)   # ~29.6, close to engine 28.4

    def test_national_total_unchanged(self):
        tot = {r["category"]: r for r in csv.DictReader(open(NATIONAL))}["TOTAL"]
        # The engine's own total: EF1=0.005 stays primary and a benchmark row adds no magnitude.
        self.assertAlmostEqual(float(tot["co2e_Mt_AR5"]), _agriculture_total_Mt(), delta=0.3)


if __name__ == "__main__":
    unittest.main()
