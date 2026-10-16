"""Inventory disagreements and unmatched comparators cannot bound missing mass."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

from pkinv.paths import ROOT
from pkinv.core.io import read_rows
from pkinv.report import joint_uncertainty, priority_rankings


class ComparatorBoundaries(unittest.TestCase):
    def test_both_signs_are_preserved_and_native_unmatched_is_not_missing_mass(self):
        rows = [dict(source="source", engine_category=name, benchmark_Mt_co2e=str(b),
                     engine_Mt_co2e=str(e), comparison_role=role, gwp=gwp, note="source boundary")
                for name, b, e, role, gwp in (("higher", 20, 10, "coverage", "AR5"),
                                              ("lower", 10, 30, "diagnostic", "AR5"),
                                              ("native", 19.4, "n/a", "diagnostic", "native CO2"))]
        with patch.object(priority_rankings, "_rows", side_effect=lambda name:
                          [] if name == "national_structural_bridge.csv" else rows):
            result = priority_rankings.build()
        compared = {r["name"]: r for r in result if r["ranking"] == "comparison"}
        self.assertEqual(compared["higher (source)"]["metric"], 10)
        self.assertEqual(compared["lower (source)"]["metric"], -20)
        self.assertEqual(compared["lower (source)"]["rank"], 1)
        self.assertFalse(any(r["ranking"] == "coverage" for r in result))
        unmatched = [r for r in result if r["ranking"] == "unmatched_comparator"]
        self.assertEqual(len(unmatched), 1)
        self.assertIn("native CO2", unmatched[0]["unit"])
        for row in result:
            self.assertTrue("not" in row["note"] or "no inference" in row["note"])
        # Even a large legacy coverage row must not create a source-mass bound.
        with patch.object(joint_uncertainty, "_rows", return_value=[dict(
                ranking="coverage", name="1A2 (all estimated) (EDGAR)", metric="9999", rank="1", note="")]):
            self.assertEqual(joint_uncertainty.completeness_bounds(), {})
        self.assertEqual(joint_uncertainty.completeness_national()["composable_bound_Mt"], "")

    def test_industry_diagnostic_has_a_signed_field_and_empty_bound_columns(self):
        path = Path(ROOT) / "scripts" / "build_industry_boundary_ledger.py"
        spec = importlib.util.spec_from_file_location("industry_boundary_comparison_test", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        reference_co2 = sum(float(r["native_mass"]) / 1000
                            for r in read_rows(str(Path(ROOT) / "outputs/semantic/fact_annual.csv"))
                            if r["period_id"] == "FY2023-24" and r["configuration_id"] == "S_TAN"
                            and r["geography_id"] == "PK" and r["gas"] == "CO2"
                            and (r["sector_id"] == "industry" or
                                 (r["sector_id"] == "power" and r["ipcc_code"] == "1.A.2")))
        self.assertAlmostEqual(module._engine_1a2_by_period(native_co2=True)["FY2023-24"], reference_co2)
        self.assertGreater(module._engine_1a2_by_period()["FY2023-24"], reference_co2)
        for row in module.diagnostic_row() + module._edgar_series_diagnostics() + module._unsd_series_diagnostics():
            self.assertEqual(row["boundary_status"], "diagnostic")
            self.assertEqual(row["co2e_Mt"], "")
            self.assertEqual(row["bound_low_Mt"], "")
            self.assertEqual(row["bound_high_Mt"], "")
            if row["comparison_difference_Mt"] == "":
                self.assertIn("No matched fiscal comparator", row["note"])
            self.assertIn(row["comparison_basis"], ("engine_minus_comparator", "comparator_minus_engine"))
            if row["component"].startswith("UNSD"):
                self.assertEqual(row["gas"], "CO2")
                self.assertIn("native CO2", row["detail"])
        with self.assertRaisesRegex(ValueError, "direction is required"):
            module.row("1.A.2", "untyped sign", "", "diagnostic", high="-3")


if __name__ == "__main__":
    unittest.main()
