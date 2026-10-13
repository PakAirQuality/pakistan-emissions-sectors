"""The three views of the industrial air layer (rc58 W3): the Lahore district view closes to the
release's own ADM2 allocation and carries the unplaced remainder; calendar 2023 is composed
from exactly the two fiscal years and conserves each class-year's half; the EDGAR comparison
compares and does not fit (every register is byte-identical across a run of it)."""

from pkinv.assets import asset_path
import hashlib
import os
import subprocess
import sys
import unittest
from collections import defaultdict

from pkinv.core.io import read_rows
from pkinv.paths import DATA, OUTPUTS

ROOT = os.path.join(os.path.dirname(__file__), "..")
REGISTERS = (
    asset_path(DATA, "air_emission_factors.csv"),
    asset_path(DATA, "air_source_classes.csv"),
    asset_path(DATA, "activity", "industry", "fuel_sulfur_evidence.csv"),
    asset_path(DATA, "industry_params.csv"),
    asset_path(DATA, "physical_sources.csv"),
)


def _digest(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


class TestLahoreView(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = read_rows(os.path.join(OUTPUTS, "pakemis_air_lahore_by_year.csv"))
        cls.adm2 = read_rows(os.path.join(OUTPUTS, "pakemis_air_adm2_by_year.csv"))
        cls.unalloc = read_rows(os.path.join(OUTPUTS, "pakemis_air_unallocated_by_year.csv"))

    def test_district_rows_are_the_adm2_allocation_verbatim(self):
        want = {(r["period_id"], r["configuration_id"], r["sector_id"], r["pollutant"]): float(r["emissions_Gg"])
                for r in self.adm2 if r["adm2_ids"] == "punjab_lahore"}
        got = {(r["period_id"], r["configuration_id"], r["sector_id"], r["pollutant"]): float(r["emissions_Gg"])
               for r in self.rows if r["row_kind"] == "district"}
        self.assertEqual(set(want), set(got))
        for k, v in want.items():
            self.assertAlmostEqual(got[k], v, places=12, msg=k)
        self.assertIn("industry", {k[2] for k in got})

    def test_the_unplaced_remainder_is_beside_the_district_for_every_period_and_species(self):
        below = defaultdict(float)
        for r in self.unalloc:
            if r["level"] == "below_adm1":
                below[(r["period_id"], r["configuration_id"], r["pollutant"], r["sector_id"])] += float(r["emissions_Gg"])
        got = {(r["period_id"], r["configuration_id"], r["pollutant"], r["sector_id"]): float(r["emissions_Gg"])
               for r in self.rows if r["row_kind"] == "unplaced_national"}
        self.assertEqual(set(got), set(below))
        for k, v in below.items():
            self.assertAlmostEqual(got[k], v, places=9, msg=k)

    def test_every_district_row_names_its_allocation_basis(self):
        for r in self.rows:
            if r["row_kind"] == "district":
                self.assertTrue(r["allocation_basis"] and r["allocation_basis"] != "not in support ledger", r)


class TestCalendar2023(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = read_rows(os.path.join(OUTPUTS, "pakemis_air_industry_cy2023.csv"))
        cls.detail = read_rows(os.path.join(OUTPUTS, "pakemis_air_source_classes_fy2015_16_fy2023_24.csv"))

    def test_twelve_months_from_exactly_two_fiscal_years(self):
        months = sorted({r["month"] for r in self.rows})
        self.assertEqual(months, ["2023%02d" % m for m in range(1, 13)])
        for r in self.rows:
            self.assertEqual(r["fiscal_period"], "FY2022-23" if int(r["month"][4:]) <= 6 else "FY2023-24")

    def test_each_half_is_the_fiscal_share_of_its_class_year(self):
        """Jul-Dec 2023 of a class-species equals FY2023-24's annual mass times the cube's
        Jul-Dec share sum, and likewise Jan-Jun against FY2022-23 - composition, not a
        second estimate."""
        half = defaultdict(float)
        share = defaultdict(float)
        for r in self.rows:
            k = (r["fiscal_period"], r["source_class_id"], r["pollutant"])
            half[k] += float(r["emissions_kt"])
            share[k] += float(r["month_share"])
        annual = {(r["period_id"], r["source_class_id"], r["pollutant"]): float(r["emissions_kt"])
                  for r in self.detail if r["status"] == "estimate"}
        self.assertGreater(len(half), 100)
        for k, v in half.items():
            # both files print six decimals; twelve rounded months against one rounded annual
            self.assertAlmostEqual(v, annual[k] * share[k], delta=2e-5 + 1e-5 * abs(v), msg=k)
            self.assertLess(share[k], 1.0)
            self.assertGreater(share[k], 0.0)


class TestEdgarComparisonDoesNotFit(unittest.TestCase):
    def test_the_registers_are_byte_identical_across_a_run(self):
        before = {p: _digest(p) for p in REGISTERS}
        subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "build_industry_air_edgar_comparison.py")],
                       check=True, capture_output=True)
        after = {p: _digest(p) for p in REGISTERS}
        self.assertEqual(before, after)

    def test_fiscal_years_beyond_edgar_are_not_compared(self):
        rows = read_rows(os.path.join(OUTPUTS, "pakemis_industry_air_edgar_comparison.csv"))
        for r in rows:
            if int(r["fiscal_end_year"]) > 2022:
                self.assertEqual(r["ratio_engine_over_edgar_fossil"], "")
                self.assertIn("not compared", r["reading"])
            elif r["engine_industry_kt"]:
                self.assertTrue(r["ratio_engine_over_edgar_fossil"], r)
        nh3 = [r for r in rows if r["species"] == "NH3" and int(r["fiscal_end_year"]) <= 2022]
        self.assertTrue(nh3)
        for r in nh3:
            self.assertEqual(r["engine_industry_kt"], "")
            self.assertIn("typed absent", r["reading"])


if __name__ == "__main__":
    unittest.main()
