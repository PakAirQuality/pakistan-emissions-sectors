"""Agricultural NOx is justified pathway by pathway, and the EMEP/EEA 2023 alternative is carried.

WHY (rc69). The review called the nitrogen partition a major structural assumption: the all-NH3
diagnostic moves national NOx by about 150 Gg. The central inventory books NOx from manure
management, applied manure and grazing as 5 percent of each pathway's mixed volatilisation loss,
and from fertiliser as 0.007 kg NO-N per kg N; EMEP/EEA 2023 publishes a process factor for each.
These tests hold the pathway table to the central atoms, pin the guidebook factors and their
reach, and check that the alternative case moves NOx and nothing else.
"""
import collections
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.activity.store import read_rows                              # noqa: E402
from pkinv.report import nitrogen_no_pathways as module                 # noqa: E402
from pkinv.report.air_annual import ATOMS_OUT                           # noqa: E402
from pkinv.report.air_sensitivities import OUT as STRUCTURAL            # noqa: E402


class TestThePathways(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = read_rows(module.OUT)
        cls.cases = [r for r in read_rows(STRUCTURAL) if r["scenario_id"] == module.CASE]

    def test_the_product_regenerates_identically(self):
        run = subprocess.run([sys.executable, "-m", module.__name__, "--check"], cwd=ROOT,
                             capture_output=True, text=True,
                             env=dict(os.environ, PYTHONPATH=os.path.join(ROOT, "src")))
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_the_central_pathways_are_the_central_atoms(self):
        central = collections.defaultdict(float)
        for a in read_rows(ATOMS_OUT):
            if a["sector_id"] == "agriculture" and a["pollutant"] == "NOx":
                central[(a["period_id"], a["configuration_id"], a["subitem"])] += float(a["emissions_Gg"])
        for row in self.rows:
            expected = sum(central[(row["period_id"], row["configuration_id"], s)]
                           for s in row["central_subitems"].split("; "))
            self.assertAlmostEqual(float(row["central_NOx_Gg"]), expected, places=5)

    def test_the_guidebook_factors_are_the_printed_ones(self):
        self.assertEqual(module.EMEP_APPLIED, 0.04)
        self.assertEqual(module.EMEP_STORAGE_SOLID, 0.01)
        for row in self.rows:
            if row["pathway"] in ("grazing_excreta", "synthetic_fertiliser", "applied_manure"):
                self.assertIn("Table 3-1", row["emep_reference"])
            if row["pathway"] == "manure_management":
                self.assertIn("Table 3-10", row["emep_reference"])

    def test_the_case_moves_nox_only_and_carries_every_year(self):
        periods = {r["period_id"] for r in self.cases}
        self.assertEqual(len(periods), 10)
        for row in self.cases:
            if row["pollutant"] != "NOx":
                self.assertEqual(float(row["change_Gg"]), 0.0)

    def test_the_reference_year_case(self):
        row = next(r for r in self.cases if r["period_id"] == "FY2023-24"
                   and r["configuration_id"] == "S_TAN" and r["pollutant"] == "NOx")
        self.assertAlmostEqual(float(row["change_Gg"]), 118.2, delta=0.1)


if __name__ == "__main__":
    unittest.main()
