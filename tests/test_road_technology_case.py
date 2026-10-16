"""The road technology case changes only the factor, from the guidebook's own Tier 2 tables.

WHY (rc69). Road exhaust PM2.5 and BC are far below the matched HTAP road sector, and the
review asked whether fleet technology explains it. The central inventory uses the EMEP/EEA
Tier 1 means, a 2010 European fleet. The case recomputes each class's own fuel at its Euro II
and its pre-Euro Tier 2 factor. A case that also moved the fuel would answer a different
question, so these tests hold the fuel fixed, the factors to their transcription, and the
derived g/kg to its two printed inputs.
"""
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.core.io import read_rows                                     # noqa: E402
from pkinv.report import road_technology_case as module                 # noqa: E402


class TestTheRoadCase(unittest.TestCase):
    def test_it_regenerates_identically(self):
        run = subprocess.run([sys.executable, "-m", module.__name__, "--check"], cwd=ROOT,
                             capture_output=True, text=True,
                             env=dict(os.environ, PYTHONPATH=os.path.join(ROOT, "src")))
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_the_derived_factor_is_its_two_printed_inputs(self):
        for row in read_rows(module.TIER2):
            expected = float(row["pm25_g_per_km"]) / float(row["fc_g_per_km"]) * 1000
            self.assertAlmostEqual(float(row["pm25_g_per_kg_fuel"]), expected, places=3)
            self.assertTrue(row["table_pm"].startswith("Table 3-"))
            self.assertTrue(0 < float(row["f_bc"]) < 1)

    def test_every_case_row_states_the_central_and_the_case(self):
        rows = read_rows(module.OUT)
        self.assertEqual({r["case"] for r in rows}, set(module.CASES))
        matched = [r for r in rows if r["htap_Gg"]]
        self.assertEqual({r["period_id"] for r in matched},
                         {"FY2015-16", "FY2016-17", "FY2017-18", "FY2018-19", "FY2019-20"})
        for r in rows:
            if r["case"] == "conventional_fleet":
                self.assertGreater(float(r["case_Gg"]), float(r["central_Gg"]))

    def test_technology_alone_leaves_part_of_the_gap(self):
        for r in read_rows(module.OUT):
            if r["case_over_htap"]:
                self.assertLess(float(r["case_over_htap"]), 1.0, r["period_id"])


if __name__ == "__main__":
    unittest.main()
