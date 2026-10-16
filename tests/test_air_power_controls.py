"""Plant design evidence must not masquerade as observed control operation."""
import unittest

from pkinv.core.io import read_rows
from pkinv.report import air_power_controls as controls


class PublicPowerControls(unittest.TestCase):
    def test_final_evidence_keeps_design_and_particle_boundary(self):
        source = controls.evidence_rows()  # validates retained publisher-document hashes
        exported = read_rows(controls.EVIDENCE)
        self.assertEqual(len(exported), len(source))
        self.assertTrue(all(r["admission_status"] == "scenario_only" for r in exported))
        self.assertTrue(all(r["operation_evidence"].startswith("not_demonstrated") for r in exported))
        so2 = {r["plant"]: float(r["design_removal_fraction"]) for r in exported
               if r["pollutant_or_property"] == "SO2"}
        self.assertEqual(so2, {"Port Qasim Electric Power": .92, "China Power Hub": .93})
        self.assertFalse(any(r["pollutant_or_property"] == "PM2.5" for r in exported))

    def test_export_uses_source_consumption_and_removal_once(self):
        rows = read_rows(controls.CASES)
        final = {(r["period_id"], r["plant"]): r for r in rows}
        # Independently transcribed SoIR2025 Table21 physical coal consumption,
        # not generation or the design application's hypothetical annual output.
        for plant, tonnes, residual in (("Port Qasim Electric Power", 1204600, .08),
                                        ("China Power Hub", 313680, .07)):
            row = final["FY2024-25", plant]
            self.assertEqual(float(row["fuel_mass_t"]), tonnes)
            expected = tonnes * 19 * float(row["sulfur_proxy_pct"]) / 1e6
            self.assertAlmostEqual(float(row["uncontrolled_case_Gg"]), expected)
            self.assertAlmostEqual(float(row["design_case_Gg"]), expected * residual)
            self.assertEqual(row["coverage_scope"], "two_selected_coal_plants_only_not_in_central_panel")

    def test_duplicate_station_fuel_fails(self):
        row = dict(plant="China Power Hub", fiscal_year="2024", fuel="Coal",
                   quantity_unit="000 t", fuel_origin="imported", quantity="313.68",
                   source_table="NEPRA SoIR2025 Table21")
        with self.assertRaisesRegex(ValueError, "duplicate station coal"):
            controls.design_cases(fuel_rows=[row, row])


if __name__ == "__main__":
    unittest.main()
