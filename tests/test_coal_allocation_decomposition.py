"""Coal account decomposition, read from the FINAL exports and recomputed independently.

The reallocation product splits central coal emissions into a supply balance (published
production + imports, minus metered station burn and HDIP household) and an allocation seam
(HDIP's power column against the stations). These tests recompute both from the final atoms
and the source tables rather than from the producer's own accumulators.
"""
import collections
import subprocess
import sys
import unittest

from pkinv.assets import asset_path
from pkinv.core.io import read_rows
from _support import ROOT

OUT = "outputs/pakemis_coal_sector_reallocation.csv"


def rows(path, comments=True):
    return read_rows(asset_path(ROOT, path), comments=comments)


class CoalDecomposition(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = {r["period_id"]: r for r in rows(OUT)}
        cls.coal = collections.defaultdict(float)
        cls.national = collections.defaultdict(float)
        for r in rows("outputs/pakemis_ghg_configuration_atoms.csv"):
            m = float(r["co2e_Mt_AR5"] or 0)
            cls.national[(r["configuration_id"], r["period_id"])] += m
            if r["configuration_id"] != "S_TAN":
                continue
            s = r["subitem"]
            if (r["sector_id"] in ("power", "residential") and s.startswith("Coal ")) or (
                    r["sector_id"] == "industry" and ("Brick-kiln coal" in s or "Cement-sector coal" in s)):
                cls.coal[(r["period_id"], r["sector_id"])] += m

    def test_central_coal_equals_final_atoms_and_closes_exactly(self):
        for period, r in self.rows.items():
            central = sum(self.coal[(period, s)] for s in ("power", "industry", "residential"))
            self.assertAlmostEqual(central, float(r["coal_central_Mt_AR5"]), places=5)
            self.assertAlmostEqual(float(r["supply_balance_coal_Mt_AR5"]) + float(r["allocation_seam_Mt_AR5"]),
                                   central, places=5)

    def test_seam_is_minus_intensity_times_unresolved_quantity(self):
        supply = {}
        for s in rows("data/activity/industry/coal_supply.csv"):
            if s["period_coverage"] == "full_year" and s["revision_status"] in ("final", "provisional"):
                supply["FY%s-%s" % tuple(s["fiscal_year"].split("-"))] = (
                    float(s["coal_imports_kt"]) + float(s["coal_production_kt_petroleum_division"]))
        for period, r in self.rows.items():
            self.assertAlmostEqual(supply[period], float(r["national_supply_kt"]), delta=0.5)
            f = self.coal[(period, "industry")] / float(r["booked_industrial_kt"])
            self.assertAlmostEqual(-f * float(r["industrial_delta_kt"]), float(r["allocation_seam_Mt_AR5"]),
                                   delta=f * 1.0)   # integer-printed unresolved kt

    def test_national_change_and_seam_share_against_independent_totals(self):
        base = "FY2015-16"
        for period, r in self.rows.items():
            for cfg in ("S_TAN", "L_TAN", "S_IPCC", "L_IPCC"):
                change = self.national[(cfg, period)] - self.national[(cfg, base)]
                self.assertAlmostEqual(change, float(r["d_national_vs_base_%s_Mt" % cfg]), places=5)
                if period != base:
                    seam = float(r["d_allocation_seam_vs_base_Mt"])
                    self.assertAlmostEqual(100 * seam / change,
                                           float(r["seam_share_of_national_change_vs_base_%s_pct" % cfg]),
                                           places=2)
        latest = self.rows["FY2024-25"]
        # the latest year's national rise is mostly the seam reversing, and the file says so
        self.assertGreater(float(latest["seam_share_of_national_change_yoy_S_TAN_pct"]), 50)

    def test_dated_fleet_is_never_an_annual_series(self):
        own = {r["period_id"] for r in rows("outputs/pakemis_brick_kiln_fleet_by_year.csv")
               if r["year_basis"].startswith("the observation's OWN period")}
        for period, r in self.rows.items():
            if period in own:
                self.assertTrue(r["brick_fleet_low_kt"])
            else:
                self.assertEqual("", r["brick_fleet_low_kt"], period)
                self.assertTrue(r["brick_position_booked"].startswith("not compared"), period)

    def test_unresolved_and_ke_coal_are_typed_not_zero(self):
        generation = {int(g["fiscal_year"]): float(g["gwh_net"])
                      for g in rows("data/activity/power/generation_by_fuel.csv")
                      if g["fuel"] == "Coal" and g["system"] == "K-Electric"}
        for period, r in self.rows.items():
            self.assertIn("no probability", r["unresolved_quantity_kind"])
            self.assertNotEqual("", r["industrial_delta_kt"])
            year = int(period[2:6])
            self.assertAlmostEqual(generation[year], float(r["ke_system_coal_generation_GWh"]), places=2)
            if generation[year] > 0:
                self.assertTrue(r["ke_system_coal_fuel_status"].startswith("not_printed"))

    def test_regeneration_matches_export(self):
        result = subprocess.run([sys.executable, "-m", "pkinv.sectors.industry.coal_reallocation", "--check"],
                                cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
