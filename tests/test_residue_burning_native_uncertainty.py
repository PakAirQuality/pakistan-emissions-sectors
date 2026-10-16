"""Shared crop-flow uncertainty is a weighted sum and reaches released draws."""
import unittest
import csv
import os
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
from pkinv.core.shared_parameter_draws import Draws, SEED, residue_burning_realisations
from pkinv.sectors.agriculture.fiscal_activity import data_for_fiscal_year
from pkinv.sectors.agriculture import residue_burning
from pkinv.paths import OUTPUTS


def independent_draws(year, draws):
    data = data_for_fiscal_year(year)
    mass = np.zeros(draws.n)
    for crop, source in data.burning.items():
        production = data.crops[crop]["production_t"]
        multiplier = draws.multiplier({"id": "activity:crop:" + crop, "kind": "activity",
                                       "uncert_pct": data.crops[crop]["uncert_pct"]}, year)
        mass += production * data.residue[crop]["residue_ratio_ag"] * source["frac_burned"] * multiplier
    cf = draws.fraction("factor:burning:combustion_factor", data.efv("burning", "combustion_factor"),
                        data.efu("burning", "combustion_factor"))
    return {gas: mass * cf * data.efv("burning", "Gef_" + gas) * draws.multiplier({
        "id": "factor:burning:Gef_" + gas, "kind": "factor",
        "uncert_pct": data.efu("burning", "Gef_" + gas)}, year) / 1e6 for gas in ("CH4", "N2O")}


class SourceRecipes(unittest.TestCase):
    def test_conditional_export_pairs_native_crop_realisations_between_years(self):
        from pkinv.report import ghg_conditional_uncertainty as producer
        from pkinv.sectors.agriculture import engine
        source = {year: [r for r in engine.components_for_fiscal_year(year)
                         if r["category"] == "Field burning of residues"] for year in (2024, 2025)}
        # Isolate the admitted source to check the producer's routing and paired
        # export; every activity/factor still comes from its actual fiscal input.
        with patch.object(producer.annual_product, "build_context", return_value={}), patch.object(
                producer.registry, "all_sectors", return_value=[SimpleNamespace(NAME="agriculture")]), patch.object(
                producer.annual_product, "components_for", side_effect=lambda name, year, context, **kwargs: source[year]):
            _levels, trends, _drivers, _parameters = producer.build(n=32, years=(2024, 2025), configurations=("S_TAN",))
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "paired_trends.csv")
            with open(path, "w", newline="") as handle:
                writer = csv.DictWriter(handle, list(trends[0]));writer.writeheader();writer.writerows(trends)
            with open(path) as handle:
                exported = list(csv.DictReader(handle))
        selected = [r for r in exported if r["sector_id"] == "national_covered"
                    and r["species_or_metric"] == "CO2e_AR5"]
        self.assertEqual(len(selected), 2)
        for row in selected:
            draws = Draws(32, row["dependence_case"])
            early, late = independent_draws(2024, draws), independent_draws(2025, draws)
            delta = (late["CH4"] - early["CH4"]) * 28 / 1000 + (late["N2O"] - early["N2O"]) * 265 / 1000
            self.assertAlmostEqual(float(row["P2_5_quantity"]), float(np.quantile(delta, .025)), places=12)
            self.assertAlmostEqual(float(row["P97_5_quantity"]), float(np.quantile(delta, .975)), places=12)
    def test_fixed_inputs_reproduce_deterministic_source_equation(self):
        class Fixed(Draws):
            def multiplier(self, entry, year):
                return np.ones(self.n)
            def fraction(self, identity, mean, uncertainty):
                return np.full(self.n, mean)
        for year in (2016, 2024, 2025):
            actual = residue_burning_realisations(year, Fixed(3))
            for row in residue_burning.compute(data_for_fiscal_year(year)):
                np.testing.assert_allclose(actual[row["gas"]], row["emissions_Gg"], rtol=1e-13)

    def test_distinct_crop_draws_are_summed_not_multiplied(self):
        class Distinct(Draws):
            def multiplier(self, entry, year):
                if entry["kind"] == "activity":
                    return np.full(self.n, {"cotton": .5, "maize": 1.4, "rice": .8,
                                           "sugarcane": 1.2, "wheat": 1.7}[entry["id"].split(":")[-1]])
                return np.ones(self.n)
        actual = residue_burning_realisations(2025, Distinct(8))
        expected = independent_draws(2025, Distinct(8))
        for gas in expected:
            np.testing.assert_array_equal(actual[gas], expected[gas])
        self.assertTrue(np.all(actual["combusted_dry_t"] <= actual["burned_dry_t"]))

    def test_paired_years_use_actual_shared_activity_and_fraction_ids(self):
        for case in ("persistent_parameters", "annual_activity_errors"):
            a, b = Draws(64, case), Draws(64, case)
            for year in (2024, 2025):
                actual = residue_burning_realisations(year, a)
                expected = independent_draws(year, b)
                for gas in expected:
                    np.testing.assert_allclose(actual[gas], expected[gas], rtol=1e-14, atol=1e-13)


class FinalExport(unittest.TestCase):
    def test_actual_common_ensemble_contains_native_crop_sum_on_each_draw(self):
        import os
        import pyarrow.parquet as pq
        table = pq.read_table(os.path.join(OUTPUTS, "mc_draws", "pakemis_ensemble_annual.parquet"),
                              columns=["draw_id", "Field burning of residues"]).to_pydict()
        n = len(table["draw_id"])
        expected = independent_draws(2024, Draws(n, seed=SEED))
        order = np.argsort(table["draw_id"])
        actual = np.asarray(table["Field burning of residues"])[order]
        np.testing.assert_allclose(actual, (expected["CH4"] * 28 + expected["N2O"] * 265) / 1000,
                                   rtol=1e-12, atol=1e-13)


if __name__ == "__main__":
    unittest.main()
