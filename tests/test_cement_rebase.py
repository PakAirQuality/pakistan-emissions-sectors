"""rc50: the clinker re-base - the eight back-years ride the census-implied fraction.

The IPCC blended-cement default 0.75 the back-years rode had no Pakistani evidence behind
it; the audited 16-company census fixes FY2023-24 and, through the clinker balance, implies
~0.965 (GEM's 30-of-32 plants at 0-5 percent substitution corroborate; IPCC's all-portland
0.95 brackets it). This module holds the re-base honest: the registry value is the
DERIVATION (not a typed number), a back-year's reference balance carries the anchored status
and the derived fraction, the 0.75 balance survives as the named diagnostic, the census year
is untouched, the method break the splice manufactured is gone, and the national pins hold.
"""
import os
import subprocess
import sys
import unittest

from _support import ROOT

sys.path.insert(0, os.path.join(ROOT, "src"))
from pkinv.sectors.ippu import cement, engine, trade_evidence  # noqa: E402
from pkinv.sectors.ippu.data import IppuData  # noqa: E402


class TestTheCensusImpliedFraction(unittest.TestCase):
    def setUp(self):
        self.data = IppuData()

    def test_the_registry_value_is_the_derivation(self):
        derived = cement.census_implied_fraction(self.data)
        v = trade_evidence.require(self.data.year)
        by_hand = (self.data.census_clinker_kt(self.data.year) - v["export_kt"] + v["import_kt"]) / \
            self.data.cement_activity_kt(self.data.cement_activity_source(self.data.year), self.data.year)
        self.assertAlmostEqual(derived, by_hand, places=9)
        self.assertAlmostEqual(self.data.p("clinker_fraction_census_implied"), derived, places=4)
        self.assertGreater(derived, 0.95)
        self.assertLess(derived, 1.0)

    def test_a_back_year_rides_the_anchored_balance_and_keeps_the_diagnostic(self):
        components, memo = cement.compute(self.data, year=2022,
                                          activity_source=self.data.cement_activity_source(2022))
        anchored, legacy = memo
        self.assertEqual(anchored["configuration_status"], "reference_model_census_anchored")
        self.assertAlmostEqual(anchored["clinker_fraction"], cement.census_implied_fraction(self.data), places=9)
        self.assertEqual(legacy["configuration_status"], "diagnostic_model_ipcc_blended_default")
        self.assertAlmostEqual(legacy["clinker_fraction"], 0.75)
        ef = self.data.efv("ippu_cement", "Clinker")
        self.assertAlmostEqual(components[0]["emissions_Gg"], anchored["clinker_production_kt"] * ef, places=6)

    def test_the_census_year_is_untouched_and_the_splice_step_closes(self):
        ref_total = sum(r["co2e_Mt_AR5"] for r in engine.build_components(self.data)
                        if r["category"] == cement.CATEGORY)   # rc52: the module also carries ammonia, steel, lubricants
        self.assertAlmostEqual(ref_total, 21.81564840, places=8)
        _c, memo23 = cement.compute(self.data, year=2023,
                                    activity_source=self.data.cement_activity_source(2023))
        _c, memo24 = cement.compute(self.data, year=2024,
                                    activity_source=self.data.cement_activity_source(2024))
        k23 = memo23[0]["clinker_production_kt"]
        k24 = memo24[0]["clinker_production_kt"]
        self.assertLess(abs(k24 - k23), 400)                       # continuity, not a +9,027 kt step
        legacy23 = memo23[1]["clinker_production_kt"]
        self.assertGreater(k24 - legacy23, 8000)                   # what the 0.75 splice had manufactured

    def test_the_national_pins_hold(self):
        rc = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "check_pins.py")],
                            capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(rc.returncode, 0, rc.stdout + rc.stderr)


if __name__ == "__main__":
    unittest.main()
