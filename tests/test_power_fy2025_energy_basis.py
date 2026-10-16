"""Physical source controls distinguish gross quantities, NCV and reconstructions."""
import os
import unittest
from pkinv.core.io import read_rows
from pkinv.sectors.power import ke_leg, plant_ledger
from pkinv.sectors.power.data import PowerData
from pkinv.paths import ROOT, OUTPUTS


def source_controls():
    return read_rows(os.path.join(ROOT, "data/sectors/power/activity/plant_fuel_2024_25.csv"))


def source_energy(row):
    q, unit = float(row["quantity"]), row["quantity_unit"]
    if row["fuel"] in ("Gas", "RLNG"):
        return q * .00105505585262 * .90 * (1000 if unit == "MMCFT" else 1)
    return q * 40.4 if row["fuel"] == "RFO" else q * .84 / 1000 * 43


class SourceBasis(unittest.TestCase):
    def test_ke_uses_same_source_ncv_and_preserves_reconstructed_cells(self):
        d = PowerData()
        source = [r for r in source_controls() if r["system"] == "K-Electric"]
        total = sum(source_energy(r) * ke_leg.CO2_KG_PER_TJ[r["fuel"]] / 1e9 for r in source)
        verified = sum(source_energy(r) * ke_leg.CO2_KG_PER_TJ[r["fuel"]] / 1e9
                       for r in source if r["estimate_status"] == "verified")
        actual = next(r for r in ke_leg.coverage_series(d) if r["fiscal_year"] == 2024)
        self.assertAlmostEqual(actual["co2_Mt"], total, places=12)
        self.assertAlmostEqual(actual["co2_Mt_printed_fuel_only"], verified, places=12)
        self.assertIn("Korangi CCPP RLNG", actual["estimated_cells"])
        self.assertIn("Gul Ahmed RFO", actual["estimated_cells"])

    def test_gas_audit_uses_matching_reference_energy_basis(self):
        d = PowerData()
        source = [r for r in source_controls() if r["fuel"] in ("Gas", "RLNG")]
        central = sum(source_energy(r) for r in source if r["system"] != "K-Electric")
        ke = sum(source_energy(r) for r in source if r["system"] == "K-Electric")
        reference = d.fuel_for(2024)["Gas"] * d.p("toe_to_tj")
        actual = next(r for r in plant_ledger.ke_boundary_audit(d) if r["fiscal_year"] == 2024)
        self.assertAlmostEqual(actual["gas_without_KE_over_national"], central / reference, places=12)
        self.assertAlmostEqual(actual["gas_with_KE_over_national"], (central + ke) / reference, places=12)


class FinalExports(unittest.TestCase):
    def test_exported_ke_and_control_rows_match_physical_source(self):
        d = PowerData()
        expected = next(r for r in ke_leg.series(d) if r["fiscal_year"] == 2024)
        actual = next(r for r in read_rows(os.path.join(OUTPUTS, "power_ke_leg_fy2023_24.csv"))
                      if r["fiscal_year"] == "2024")
        self.assertAlmostEqual(float(actual["co2_Mt"]), expected["co2_Mt"], delta=.000501)
        controls = [r for r in read_rows(os.path.join(OUTPUTS, "power_toe_reconciliation.csv"))
                    if r["fiscal_year"] == "2024"]
        self.assertEqual(len(controls), 2)
        for row in controls:
            key = "Gas" if row["fuel"].startswith("gas") else "Furnace Oil"
            self.assertEqual(row["rung_national_table3_TJ"], "")
            self.assertAlmostEqual(float(row["rung_reconstructed_reference_TJ"]),
                                   d.fuel_for(2024)[key] * d.p("toe_to_tj"), delta=.501)


if __name__ == "__main__":
    unittest.main()
