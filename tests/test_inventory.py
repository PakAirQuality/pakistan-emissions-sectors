"""Unit tests for the Pakistan Tier 1 agricultural GHG inventory engine.

Run:  python3 -m unittest discover tests
"""
import os
import sys
import unittest


from pkinv.sectors.agriculture.ef_library import InventoryData  # noqa: E402
from pkinv.sectors.agriculture import enteric, manure, rice, soils, residue_burning, liming_urea  # noqa: E402
from pkinv.core import gwp  # noqa: E402
from pkinv.core.uncertainty import product, combine_sum  # noqa: E402


class TestInventory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = InventoryData()
        cls.comp = []
        cls.comp += enteric.compute(cls.data)
        mc, cls.npools = manure.compute(cls.data)
        cls.comp += mc
        cls.comp += rice.compute(cls.data)
        cls.comp += soils.compute(cls.data, cls.npools)
        cls.comp += residue_burning.compute(cls.data)
        cls.comp += liming_urea.compute(cls.data)
        for c in cls.comp:
            c["co2e"] = gwp.to_co2e(c["gas"], c["emissions_Gg"], "AR5") / 1000.0

    # --- IPCC worked-example style hand calcs ---
    def test_buffalo_enteric(self):
        # rc39 A1: the head is the census's exact enumeration, not 47.7e6 rounded to three
        # significant figures. Still a hand calculation against the IPCC worked example --
        # the point of this test is that the arithmetic is done OUTSIDE the engine -- so the
        # exact count is written out here rather than read from the activity file.
        # 47,738,368 head * 55 kg/head/yr / 1e6 = 2625.61024 Gg CH4
        b = next(c for c in self.comp
                 if c["category"] == "Enteric fermentation" and c["subitem"] == "buffalo")
        self.assertAlmostEqual(b["emissions_Gg"], 47738368 * 55 / 1e6, places=3)
        self.assertAlmostEqual(b["co2e"], 2625.61024 * 28 / 1000.0, places=3)  # AR5

    def test_rice_hand_calc(self):
        # EFc 1.30 * SFw * SFp * SFo * area * period * 1e-6 (period from parameters)
        r = next(c for c in self.comp if c["category"] == "Rice cultivation")
        period = self.data.p("rice_cultivation_period_days")
        # The harvested area comes from the crop file, not a literal: this is a hand-check of
        # the EQUATION, and pinning the area made it fail the moment the sector moved onto a
        # different reporting year, which is a fact about the activity data rather than about
        # the arithmetic under test.
        area = self.data.crops["rice"]["area_ha"]
        self.assertAlmostEqual(r["emissions_Gg"], 1.30 * area * period * 1e-6, places=3)

    def test_nex_per_head(self):
        # Nex = nex_rate * TAM * 365 / 1000 (Eq 10.30), parameter-driven
        expect = (self.data.p("nex_rate_dairy_cattle") * self.data.p("tam_dairy_cattle")
                  * 365 / 1000.0)
        self.assertAlmostEqual(self.data.nex_per_head("dairy_cattle"), expect, places=4)

    def test_gwp_values(self):
        self.assertEqual(gwp.GWP["AR5"]["CH4"], 28.0)
        self.assertEqual(gwp.GWP["AR5"]["N2O"], 265.0)

    # --- structural / reconciliation ---
    def test_reconciliation(self):
        # category sums add to the national total (CO2e)
        total = sum(c["co2e"] for c in self.comp)
        cats = {}
        for c in self.comp:
            cats[c["category"]] = cats.get(c["category"], 0.0) + c["co2e"]
        self.assertAlmostEqual(sum(cats.values()), total, places=6)

    def test_all_categories_present(self):
        cats = {c["category"] for c in self.comp}
        self.assertEqual(cats, {"Enteric fermentation", "Manure management",
                                "Rice cultivation", "Managed soils",
                                "Field burning of residues", "Urea application"})

    def test_urea_co2(self):
        lu = [c for c in self.comp if c["category"] == "Urea application"]
        self.assertEqual({c["gas"] for c in lu}, {"CO2"})
        urea = next(c for c in lu if "Urea" in c["subitem"])
        self.assertTrue(3.0 < urea["co2e"] < 5.5, "urea CO2 %.2f" % urea["co2e"])
        # rc39 A4: there is NO liming row to assert against any more, and that is the point.
        # This used to require one and check it equalled zero - pinning the published zero
        # that contradicted the NE declaration in the completeness table. 3.G is not
        # estimated, so the category carries urea and nothing else.
        self.assertEqual([c["subitem"] for c in lu], ["Urea application CO2"])

    def test_residue_burning_small_positive(self):
        burn = [c for c in self.comp if c["category"] == "Field burning of residues"]
        self.assertEqual({c["gas"] for c in burn}, {"CH4", "N2O"})
        total = sum(c["co2e"] for c in burn)
        self.assertTrue(0.1 < total < 3.0, "burning %.2f Mt out of expected small range" % total)

    def test_both_n2o_pathways(self):
        soil_items = [c["subitem"] for c in self.comp if c["category"] == "Managed soils"]
        self.assertTrue(any("Indirect N2O - volatilisation" in s for s in soil_items))
        self.assertTrue(any("Indirect N2O - leaching" in s for s in soil_items))

    def test_indirect_n2o_is_split_by_source_stream(self):
        """Both indirect pathways must be reported per source stream, not lumped. A lumped row can
        carry only one spatial proxy, and most of this nitrogen is livestock-derived -- routing the
        whole row on fertiliser offtake misplaced the bulk of it."""
        soil_items = [c["subitem"] for c in self.comp if c["category"] == "Managed soils"]
        for pathway in ("Indirect N2O - volatilisation", "Indirect N2O - leaching/runoff"):
            streams = [s for s in soil_items if s.startswith(pathway)]
            self.assertGreater(len(streams), 1, "%s is still a single lumped row" % pathway)
            self.assertNotIn(pathway, streams, "%s lumped row still emitted" % pathway)
            self.assertTrue(any("organic manure" in s for s in streams))
            self.assertTrue(any("synthetic fertiliser" in s for s in streams))

    def test_ef_traceability(self):
        # every EF the engine asks for must exist in the loaded library (no magic numbers)
        for key in [("enteric", "buffalo"), ("manure_ch4", "buffalo_warm"),
                    ("manure_n2o_ef3", "drylot"), ("rice", "EFc"),
                    ("soils", "EF1_dry"), ("soils", "FracLEACH")]:
            self.assertIn(key, self.data.ef)
            self.assertIsNotNone(self.data.efv(*key))

    # --- sanity ---
    def test_enteric_is_largest(self):
        cats = {}
        for c in self.comp:
            cats[c["category"]] = cats.get(c["category"], 0.0) + c["co2e"]
        self.assertEqual(max(cats, key=cats.get), "Enteric fermentation")

    def test_total_in_plausible_band(self):
        total = sum(c["co2e"] for c in self.comp)
        self.assertTrue(100 < total < 350, "total %.1f Mt outside plausible band" % total)

    def test_no_negative_emissions(self):
        for c in self.comp:
            self.assertGreaterEqual(c["emissions_Gg"], 0.0, c["subitem"])

    def test_uncertainty_helpers(self):
        self.assertAlmostEqual(product(30, 40), 50.0, places=6)  # 3-4-5
        total, u = combine_sum([(100, 10), (100, 10)])
        self.assertAlmostEqual(total, 200.0)
        self.assertAlmostEqual(u, 7.0710678, places=4)  # sqrt(10^2+10^2)/200*100


class TestTheFertiliserNutrientTrap(unittest.TestCase):
    """NFDC publishes a headline that is not the number this engine wants.

    The Review's front-page figure for 2023-24 is 4,816 thousand tonnes, and it is offtake of
    ALL NUTRIENTS (N + P2O5 + K2O). Managed-soils N2O is driven by nitrogen alone, which the
    same publication's Table 3 gives as 3,775. The two differ by 27.6 percent, and taking the
    headline would add several megatonnes of N2O that does not exist - in the largest sector
    in the inventory, from a number that would look perfectly plausible in a spreadsheet.

    The trap is worth a test rather than a comment because the headline is what a compiler
    reads first, and because the same shape recurs: a publication's most prominent number is
    rarely the one an inventory equation takes.
    """

    def setUp(self):
        self.data = InventoryData()

    def test_the_nitrogen_row_is_nitrogen_not_total_nutrients(self):
        n = self.data.fertilizer["nitrogen_N_offtake"]["value_t"]
        p = self.data.fertilizer["phosphate_P2O5_offtake"]["value_t"]
        k = self.data.fertilizer["potash_K2O_offtake"]["value_t"]
        self.assertAlmostEqual(n, 3775000.0, delta=1000.0)
        self.assertAlmostEqual(n + p + k, 4816100.0, delta=2000.0,
                               msg="the three nutrient rows must reconstruct NFDC's total")
        self.assertLess(n, n + p + k)

    def test_urea_nitrogen_is_a_share_of_total_nitrogen(self):
        """A second guard on the same file: urea N is product tonnes times 46 percent, and it
        must be a fraction of the year's nitrogen rather than a rival total."""
        n = self.data.fertilizer["nitrogen_N_offtake"]["value_t"]
        urea_n = self.data.fertilizer["nitrogen_N_from_urea"]["value_t"]
        urea_product = self.data.fertilizer["urea_product_offtake"]["value_t"]
        self.assertAlmostEqual(urea_n / urea_product, 0.46, places=3)
        self.assertLess(urea_n, n)
        self.assertGreater(urea_n / n, 0.6, "urea dominates Pakistani nitrogen")


class TestTheYearArgumentIsRefusedRatherThanEaten(unittest.TestCase):
    """Agriculture's engine used to swallow a year and return 4.8 million Mt.

    `build_components` was `(data, *args, **kwargs)` forwarding into
    `run_inventory.build_components(data, ef1_override=None)`, so a positional year landed on
    the factor override: `build_components(data, 2024)` returned 4,819,139 Mt against a
    published 223.26. The sector contract prints an invariant saying no sector may return a
    plausible wrong number for a year its sources do not cover, and the guard enforcing it took
    its own baseline through the same poisoned call - so its acceptance band scaled with the
    defect and the check passed.

    This lives here rather than in test_sector_contract.py on purpose: it is a property of THIS
    sector's signature, not one checked against every registered sector, and the manuscript
    counts the contract file's tests as "invariants enforced against every registered sector".
    A sector-specific test in that file would inflate a published count into a false claim.
    """

    def test_its_own_year_changes_nothing_and_another_year_raises(self):
        from pkinv.core import registry
        sector = next(s for s in registry.all_sectors() if s.NAME == "agriculture")
        data = sector.load_data()
        reference = sum(c["co2e_Mt_AR5"] for c in sector.build_components(data))
        at_its_own_year = sum(c["co2e_Mt_AR5"]
                              for c in sector.build_components(data, sector.YEAR))
        self.assertAlmostEqual(reference, at_its_own_year, places=6,
                               msg="passing the sector its own year changed the answer, which "
                                   "means the argument is being consumed as something else")
        with self.assertRaises(ValueError):
            sector.build_components(data, sector.YEAR - 5)


if __name__ == "__main__":
    unittest.main()
