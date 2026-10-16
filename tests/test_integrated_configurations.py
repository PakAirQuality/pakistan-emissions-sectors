"""Structural configurations retain own-year activities and native component identity."""
import unittest

from pkinv.core import configurations as conf
from pkinv.report import annual_product
from pkinv.sectors.residential import engine as residential
from pkinv.sectors.waste.data import WasteData


class IntegratedConfigurations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context = annual_product.build_context()

    def test_latest_ledger_uses_latest_household_and_herd_activity(self):
        actual = annual_product.components_for("residential", 2025, self.context, conf.LEDGER)
        expected = residential.components_for_year(self.context["res_data"], 2025, dung_basis="ledger")
        self.assertEqual([(r["gas"], r["emissions_Gg"]) for r in expected],
                         [(r["gas"], r["emissions_Gg"]) for r in actual])
        old = annual_product.components_for("residential", 2024, self.context, conf.LEDGER)
        self.assertNotEqual(sum(r["emissions_Gg"] for r in old),
                            sum(r["emissions_Gg"] for r in actual))

    def test_nitrogen_and_household_switches_are_separate_axes(self):
        ag = {cfg: annual_product.components_for("agriculture", 2025, self.context, cfg)
              for cfg in conf.ALL}
        def masses(rows):
            return {r["component_id"]: r["emissions_Gg"] for r in rows}
        self.assertEqual(masses(ag[conf.REFERENCE]), masses(ag[conf.LEDGER]))
        self.assertEqual(masses(ag[conf.IPCC_REFERENCE]), masses(ag[conf.IPCC_LEDGER]))
        self.assertEqual(set(masses(ag[conf.REFERENCE])), set(masses(ag[conf.IPCC_REFERENCE])))
        self.assertNotEqual(masses(ag[conf.REFERENCE]), masses(ag[conf.IPCC_REFERENCE]))

    def test_query_aliases_match_inventory_without_runtime_dependency(self):
        from pakemis_query import configurations as query
        self.assertEqual(conf.AIR_ALL, query.AIR_ALL)
        for old, new in conf.ALIASES.items():
            self.assertEqual(new, query.canonical(old))

    def test_population_index_preserves_order_and_refreshes_for_replaced_panel(self):
        data = WasteData()
        expected = [r for r in data.population if r["year"] == data.year]
        self.assertEqual(expected, data.population_for())
        data.population = list(reversed(data.population))
        self.assertEqual(list(reversed(expected)), data.population_for())
        with self.assertRaises(KeyError):
            data.population_for(1900)


if __name__ == "__main__":
    unittest.main()
