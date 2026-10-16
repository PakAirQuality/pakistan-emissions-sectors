"""The Tier-1 calibrated ammonia estimate (2026-09-10): the configuration prices
product-stoichiometry activity through the Pakistan-calibrated 1.815 factor net of
urea recovery = 3.24 Mt central, 2.70-4.53 method envelope. The reference total does
NOT move (ammonia stays NE; the estimate lives in the scope configuration)."""

from pkinv.assets import asset_path
import csv
import os
import sys
import unittest
from pkinv.core.reporting_window import CORE_FY_STARTS, CORE_FY_ENDS, CORE_PERIOD_IDS, REFERENCE_PERIOD
from pkinv.core.configurations import REFERENCE

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))


def _rows(path):
    with open(asset_path(ROOT, path), encoding="utf-8") as h:
        return list(csv.DictReader(l for l in h if not l.startswith("#")))


class AmmoniaTier1(unittest.TestCase):
    def test_the_calibrated_factor_reproduces_the_official_filing(self):
        """EF* = (3.02 + 6.30139*44/60) / (3.466054*17/14) = 1.815, by construction."""
        ef_star = (3.02 + 6.30139 * 44 / 60) / (3.466054 * 17 / 14)
        self.assertAlmostEqual(ef_star, 1.815, places=3)
        params = {r["param"]: float(r["value"]) for r in _rows("data/ippu_params.csv")}
        self.assertAlmostEqual(params["ammonia_ef_calibrated"], 1.815, places=3)
        self.assertAlmostEqual(params["ammonia_ef_modern"], 1.694, places=3)
        self.assertAlmostEqual(params["ammonia_ef_total_energy"], 2.104, places=3)

    def test_the_config_prices_the_tier1_central_and_envelope(self):
        row = next(r for r in _rows("outputs/ippu_chemicals_screening_2024.csv")
                   if r["configuration"] == "ammonia_feedstock_in_scope")
        self.assertEqual(row["evidence_state"], "tier1_calibrated_central")
        self.assertAlmostEqual(float(row["adjustment_Mt_co2e"]), 3.243, places=2)
        self.assertAlmostEqual(float(row["bracket_low_Mt"]), 2.705, places=2)
        self.assertAlmostEqual(float(row["bracket_high_Mt"]), 4.529, places=2)

    def test_the_reference_national_total_carries_ammonia(self):
        """rc52: ammonia is IN the reference (one 2.B.1 atom for FY2023-24); the configuration
        lane keeps the screening's pathway rows as diagnostics."""
        rows = _rows("outputs/semantic/fact_annual.csv")
        total = sum(float(r["co2e_Mt_AR5"]) for r in rows
                    if r["period_id"] == "FY2023-24" and r["configuration_id"] == REFERENCE)
        expected = sum(float(r["co2e_Mt_AR5"]) for r in _rows("outputs/pakemis_atomic_annual.csv")
                       if r["period_id"] == REFERENCE_PERIOD and r["co2e_Mt_AR5"])
        self.assertGreater(total, 0)
        self.assertAlmostEqual(total, expected, places=5)
        ammonia_in_ref = [r for r in rows if r["configuration_id"] == REFERENCE
                          and r["ipcc_code"] == "2.B.1" and r["period_id"] == "FY2023-24"]
        self.assertEqual(len(ammonia_in_ref), 1)
        self.assertAlmostEqual(float(ammonia_in_ref[0]["co2e_Mt_AR5"]), 3.243, places=2)

    def test_the_central_sits_between_the_modern_and_conventional_ends(self):
        row = next(r for r in _rows("outputs/ippu_chemicals_screening_2024.csv")
                   if r["configuration"] == "ammonia_feedstock_in_scope")
        lo, mid, hi = (float(row[c]) for c in ("bracket_low_Mt", "adjustment_Mt_co2e", "bracket_high_Mt"))
        self.assertLess(lo, mid)
        self.assertLess(mid, hi)


if __name__ == "__main__":
    unittest.main()
