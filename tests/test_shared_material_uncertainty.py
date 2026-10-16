"""Native chemical releases share realisations and preserve their material ledger."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np

from pkinv.core.shared_parameter_draws import Draws, nitrogen_realisations, fugitives_realisations
from pkinv.core import montecarlo
from pkinv.sectors.agriculture.ef_library import InventoryData
from pkinv.sectors.agriculture import manure, soils


class FixedInputs(Draws):
    def multiplier(self, entry, year):
        return np.ones(self.n)

    def fraction(self, name, mean, uncertainty):
        return np.full(self.n, mean)


class SharedMaterialUncertainty(unittest.TestCase):
    def test_physical_input_alias_and_prefix_are_identical(self):
        a, b = Draws(12), Draws(30)
        entry = {"id": "activity:livestock:cattle", "kind": "activity", "uncert_pct": 15}
        np.testing.assert_array_equal(a.multiplier(entry, 2024), b.multiplier(entry, 2024)[:12])
        np.testing.assert_array_equal(a.normal("livestock:cattle", 2024),
                                      a.normal("activity:livestock:cattle", 2024))
        c = Draws(12, "annual_activity_errors")
        self.assertFalse(np.array_equal(c.normal("livestock:cattle", 2023),
                                        c.normal("livestock:cattle", 2024)))

    def test_fixed_native_replay_matches_each_complete_formulation(self):
        data = InventoryData()
        for method in manure.NITROGEN_METHODS:
            expected, pools = manure.compute(data, method)
            expected += soils.compute(data, pools)
            actual, residual = nitrogen_realisations(2024, FixedInputs(3), method)
            for row in expected:
                if row["gas"] == "N2O":
                    key = "ghg:%s|%s|N2O" % (row["category"], row["subitem"])
                    np.testing.assert_allclose(actual[key], row["emissions_Gg"], rtol=1e-12)
            self.assertLess(residual, 2e-6)
            nox = data.efv("soils", "NOx_frac_of_applied")
            np.testing.assert_allclose(actual["soil_NOx:synthetic"],
                data.fertilizer["nitrogen_N_offtake"]["value_t"] * 1000 * nox * 46 / 14 / 1e6)
            np.testing.assert_allclose(actual["soil_NOx:crop_residues"],
                soils.residue_N(data) * nox * 46 / 14 / 1e6)

    def test_parameter_replay_conserves_and_changes_both_product_families(self):
        results, residual = nitrogen_realisations(2024, Draws(40))
        self.assertLess(residual, 5e-6)
        self.assertGreater(np.std(results["managed_NOx_N"]), 0)
        self.assertGreater(np.std(results["ghg:Manure management|Indirect N2O (volatilisation)|N2O"]), 0)
        self.assertGreater(np.std(results["synthetic_NH3:Urea"]), 0)

    def test_native_component_is_not_sampled_again(self):
        component = {"category": "N", "subitem": "native", "gas": "N2O",
                     "co2e_Mt_AR5": 2.0, "uncert_pct": 500, "_sector": "agriculture"}
        values = [1.0, 2.0, 3.0, 4.0]
        with patch("pkinv.core.parameters.decompose", return_value=[]):
            _, totals = montecarlo.run([component], ["N"], n_iter=4, stream="parameter",
                component_values={"N|native|N2O": values})
        self.assertEqual(totals, values)

    def test_ledger_dung_does_not_sample_an_aggregate_chain_after_native_herd(self):
        from pkinv.report import ghg_conditional_uncertainty as producer
        component = {"category": "Residential fuel combustion", "subitem": "Dung cake N2O",
                     "gas": "N2O", "emissions_Gg": 1., "co2e_Mt_AR5": .265,
                     "uncert_pct": 50, "component_id": "dung-test"}
        class ChainMustNotBeRead(FixedInputs):
            def normal(self, name, year):
                if name == "1a4b_dung_chain":
                    raise AssertionError("aggregate dung-chain draw duplicates native herd replay")
                return np.zeros(self.n)
        with patch.object(producer, "Draws", ChainMustNotBeRead), \
             patch.object(producer.annual_product, "build_context", return_value={}), \
             patch.object(producer.annual_product, "components_for", return_value=[component]), \
             patch.object(producer.registry, "all_sectors", return_value=[SimpleNamespace(NAME="residential")]), \
             patch.object(producer, "waste_realisations", return_value={}), \
             patch.object(producer, "fugitives_realisations", return_value={}), \
             patch.object(producer, "power_coal_realisations", return_value={}), \
             patch.object(producer, "nitrogen_realisations", return_value=({}, 0)), \
             patch.object(producer, "dung_mass_multiplier", return_value=np.ones(3)), \
             patch.object(producer.parameters, "decompose", side_effect=lambda rows:
                          [(row, {"1a4b_dung_chain": .5}, 0, False) for row in rows]):
            levels, _trends, _drivers, _parameters = producer.build(n=3, years=(2024,), configurations=("L_TAN",))
        native = [row for row in levels if row["species_or_metric"] == "N2O"]
        self.assertTrue(native)
        self.assertTrue(all(row["P50_quantity"] == 1 for row in native))

    def test_fraction_complement_draws_preserve_partition(self):
        draws = Draws(40)
        entry = {"id": "fraction:test", "kind": "factor", "mean": .3,
                 "uncert_pct": 50, "distribution": "bounded_beta"}
        a = .3 * draws.multiplier(entry, 2024)
        b = .7 * draws.multiplier(dict(entry, complement=True), 2024)
        np.testing.assert_allclose(a + b, 1, atol=1e-15)
        self.assertEqual(draws.registry["fraction:test"]["mean"], .3)

    def test_native_fugitive_species_are_not_concatenated(self):
        values = fugitives_realisations(2024, Draws(8))
        self.assertIn("Oil production|CH4", values)
        self.assertIn("Oil production|CO2", values)
        for row in values.values():
            self.assertEqual(len(row), 8)

    def test_future_phase_uses_the_same_census_bridge(self):
        from pkinv.sectors.agriculture import fiscal_activity, timeseries
        live, _, _ = timeseries._load_history()
        future = fiscal_activity.proxy_stocks_for_year(live, 2025)
        for species in timeseries.SPECIES:
            self.assertAlmostEqual(future[species] / live[2024][species],
                (live[2024][species] / live[2019][species]) ** .2)


if __name__ == "__main__":
    unittest.main()
