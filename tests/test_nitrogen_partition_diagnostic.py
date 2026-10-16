"""Native-ledger and final-export checks for the chemical-attribution case."""
import collections
import contextlib
import csv
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pkinv.core import configurations as conf
from pkinv.core.reporting_window import CORE_FY_ENDS
from pkinv.report import air_sensitivities as product
from pkinv.sectors.agriculture import air_pollutants, fiscal_activity


class NitrogenAttributionDiagnostic(unittest.TestCase):
    def test_case_recomputes_surviving_n_and_keeps_distinct_nox_sources(self):
        reference = product.nitrogen_partition_replay(2024, "tan")
        case = product.nitrogen_partition_replay(2024, "tan", 1.0)
        self.assertEqual(reference["fraction"], .95)
        self.assertEqual(case["fraction"], 1.0)
        self.assertEqual(case["pools"]["managed_NOx_N"], 0)
        for key in ("pasture_cattle", "pasture_other"):
            self.assertEqual(case["pools"]["field_volat_NOx_N"][key], 0)
        self.assertGreater(case["pools"]["field_volat_NOx_N"]["organic"], 0)
        self.assertGreater(case["pools"]["FON_N"], reference["pools"]["FON_N"])
        self.assertGreater(case["ghg"]["N2O"], reference["ghg"]["N2O"])
        self.assertGreater(case["air"]["NH3"], reference["air"]["NH3"])
        self.assertLess(case["air"]["NOx"], reference["air"]["NOx"])
        self.assertLess(case["max_residual"], 1e-5)
        # Setting the share is confined to a fresh deterministic case. It does
        # not zero separately factored applied-N or combustion NOx pathways.
        data = fiscal_activity.data_for_fiscal_year(2024)
        self.assertEqual(data.efv("soils", "NH3_frac_of_volat"), .95)
        data.nitrogen_method = "tan"
        key = "soils", "NH3_frac_of_volat"
        data.ef[key] = dict(data.ef[key], value=1.0)
        sources = {r["subitem"]: r["emissions_kt"] for r in air_pollutants.compute(data)
                   if r["pollutant"] == "NOx"}
        self.assertGreater(sources["Soil NOx - synthetic fertiliser"], 0)
        self.assertGreater(sources["Soil NOx - crop residues"], 0)
        self.assertGreater(sum(v for k, v in sources.items() if k.startswith("Residue burning")), 0)

    def test_ipcc_repartition_retains_total_loss_and_native_ghg(self):
        reference = product.nitrogen_partition_replay(2024, "ipcc")
        case = product.nitrogen_partition_replay(2024, "ipcc", 1.0)
        for key in ("FON_N", "volat_managed_N"):
            self.assertAlmostEqual(case["pools"][key], reference["pools"][key])
        for gas in ("CO2", "CH4", "N2O", "CO2e_AR5", "CO2e_AR6"):
            self.assertAlmostEqual(case["ghg"][gas], reference["ghg"][gas])
        self.assertGreater(case["air"]["NH3"], reference["air"]["NH3"])
        self.assertLess(case["air"]["NOx"], reference["air"]["NOx"])

    def test_final_export_has_typed_metrics_closure_and_matched_reference(self):
        # Exercise the actual writer in a temporary destination; reference
        # checks inside the producer independently read current exported atoms.
        with tempfile.TemporaryDirectory() as folder:
            air_path, ghg_path = Path(folder) / "air.csv", Path(folder) / "ghg.csv"
            with patch.object(product, "OUT", air_path), patch.object(product, "NITROGEN_OUT", ghg_path), \
                    contextlib.redirect_stdout(io.StringIO()):
                product.main()
            with air_path.open() as stream:
                air = [r for r in csv.DictReader(stream) if r["scenario_id"] == product.NITROGEN_CASE]
            with ghg_path.open() as stream:
                reader = csv.DictReader(stream)
                self.assertEqual(tuple(reader.fieldnames), product.NITROGEN_FIELDS)
                ghg = list(reader)
        self.assertEqual(len(air), len(CORE_FY_ENDS) * len(conf.ALL) * 7)
        self.assertEqual(len(ghg), len(CORE_FY_ENDS) * len(conf.ALL) * 5)
        self.assertEqual({r["configuration_id"] for r in air}, set(conf.ALL))
        expected = product.nitrogen_partition_replay(2024, "tan", 1.0)
        actual = product.nitrogen_partition_replay(2024, "tan")
        for row in air:
            self.assertEqual(row["case_kind"], "diagnostic_structural_case_no_probability")
            self.assertIn("not a measured alternative or plausible bound", row["limitations"])
            delta = float(row["change_Gg"])
            self.assertAlmostEqual(float(row["case_sector_Gg"]) - float(row["reference_sector_Gg"]), delta)
            self.assertAlmostEqual(float(row["case_covered_Gg"]) - float(row["reference_covered_Gg"]), delta)
            if row["period_id"] == "FY2023-24" and row["configuration_id"] == conf.REFERENCE:
                pol = row["pollutant"]
                self.assertAlmostEqual(delta, expected["air"][pol] - actual["air"][pol])
        grouped = collections.defaultdict(dict)
        for row in ghg:
            metric = row["metric"]
            self.assertEqual(row["unit"], "Mt_CO2e" if metric.startswith("CO2e") else "Gg")
            self.assertNotIn("pollutant", row)
            self.assertEqual(float(row["reference_NH3_fraction"]), .95)
            self.assertEqual(float(row["case_NH3_fraction"]), 1.0)
            self.assertLess(float(row["max_nitrogen_closure_residual_kgN"]), 1e-5)
            delta = float(row["change_quantity"])
            self.assertAlmostEqual(float(row["case_covered_quantity"]) - float(row["reference_covered_quantity"]), delta)
            grouped[row["period_id"], row["configuration_id"]][metric] = delta
        for changes in grouped.values():
            self.assertEqual(changes["CO2"], 0)
            self.assertEqual(changes["CH4"], 0)
            self.assertAlmostEqual(changes["CO2e_AR5"], changes["N2O"] * 265 / 1000)
            self.assertAlmostEqual(changes["CO2e_AR6"], changes["N2O"] * 273 / 1000)


if __name__ == "__main__":
    unittest.main()
