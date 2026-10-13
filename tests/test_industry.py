"""Industrial fuel combustion (IPCC 1A2, gas) - the sector-specific invariants.

The 19 generic contract tests in test_sector_contract.py already run over this sector. What is
here is what is particular to 1A2: that it does not take gas another sector already took, that
it excludes the fertiliser row rather than forgetting it, and that its scope claim - a floor,
not an estimate - stays true.

This sector exists because a data-availability audit pointed out that 1A2 was described as
having no sector-disaggregated fuel data when OGRA publishes gas by sector in a table this
inventory already read for four other numbers.

Run:  python3 -m unittest discover tests -p "test_industry.py"
"""

from pkinv.assets import asset_path
import csv
import os
import unittest

from pkinv.core import registry
from pkinv.paths import DATA
from pkinv.sectors.industry import combustion, downscale, engine
from pkinv.sectors.industry.data import IndustryData
from pkinv.sectors.power.data import PowerData
from pkinv.sectors.transport.data import TransportData
from pkinv.core.io import read_rows


def _load(*parts):
    return read_rows(asset_path(DATA, *parts), comments=False)


class TestScope(unittest.TestCase):
    """1A2 gas. The claim this sector must not quietly outgrow is that it is a FLOOR."""

    @classmethod
    def setUpClass(cls):
        cls.data = IndustryData()
        cls.comps = engine.build_components(cls.data)

    def test_the_stream_set_is_gas_liquids_and_the_two_activated_coals(self):
        """The scope boundary, moved for the third time and documented each time.

        It began as 'gas only', failed the day the liquid rows landed, and failed again at
        rc46 Wave 2 when brick and cement coal entered through the
        industrial_solid_fuels_1a2 gate - which is exactly what it is for: the boundary may
        only move together with the documentation. The solid set is CLOSED at the two
        activated streams: petcoke stays on its trade lane, bagasse a ceiling, captive coal
        a configuration, and a third coal subitem here means an activation this test was
        not told about."""
        liquids = tuple(combustion.LIQUID_LABELS.values())
        solids = ("Brick-kiln coal", "Cement-sector coal")
        for c in self.comps:
            self.assertTrue("gas" in c["subitem"].lower()
                            or c["subitem"].startswith(liquids)
                            or c["subitem"].startswith(solids), msg=c["subitem"])
        seen_solids = {c["subitem"].rsplit(" ", 1)[0] for c in self.comps
                       if c["subitem"].startswith(solids)}
        self.assertEqual(seen_solids, set(solids))

    def test_the_floor_claim_is_documented(self):
        doc = combustion.__doc__
        self.assertIn("FLOOR", doc.upper())
        for missing in ("coal", "bagasse", "petroleum coke"):
            self.assertIn(missing, doc.lower())

    def test_the_category_now_covers_most_of_the_gap_it_sat_in(self):
        """Inverted at rc46 Wave 2, deliberately. The old form pinned 3-20 Mt with the
        reasoning 'if this ever approached EDGAR's ~44, the solid fuels would have to be in
        it' - and now they are, through the gate, so the guard flips: the module plus the
        power-side captive must cover the MAJORITY of EDGAR's 1A2, and falling back under
        20 Mt would mean the activation was silently lost."""
        total = sum(c["co2e_Mt_AR5"] for c in self.comps)
        self.assertTrue(20.0 < total < 30.0, "1A2 here is %.2f Mt" % total)


class TestFertiliserIsExcluded(unittest.TestCase):
    """The largest trap in the source table, and the reason it is a trap.

    Fertiliser takes 756 MMCFD - more than twice General Industry. The IPCC ammonia method
    allocates the plant's TOTAL gas requirement - feedstock and process fuel together - to
    2B1, so the whole row leaves 1A2, and only separately metered auxiliary combustion
    outside the process boundary would return. NFDC's monthly plant annex puts the split
    at 83.5/16.5 in FY2023-24 - the reference year, on the plants' own meters - so a
    sixth of the row IS burned; an earlier edition of these tests pinned the claim that
    almost none of it was, which was wrong and is withdrawn, and a later one borrowed the
    FY2024-25 shares to describe the reference year, which is withdrawn too. Booking the
    row here would inflate the category three and a half fold and double-count against
    the ammonia accounting.
    """

    def test_no_fertiliser_stream_is_estimated(self):
        data = IndustryData()
        for s in data.streams():
            self.assertNotIn("fertil", s.lower())

    def test_the_exclusion_is_documented_with_its_reason(self):
        doc = combustion.__doc__.lower()
        self.assertIn("feedstock", doc)
        self.assertIn("2b1", doc)
        self.assertIn("756", doc)
        # The CORRECT rationale, pinned so it cannot silently revert: the boundary is
        # the total gas requirement of the process, not the feedstock share of it.
        self.assertIn("total gas requirement", doc)
        self.assertIn("process fuel", doc)
        self.assertNotIn("almost none", doc)

    def test_the_known_split_did_not_reopen_the_boundary(self):
        """NFDC gave the feed/fuel split and a sixth of the row is fuel. If that sixth
        ever crept back into 1A2 as a stream, the total-requirement boundary would have
        been silently traded for the flame boundary."""
        rows = _load("nfdc", "afr2025_fertilizer_gas_by_plant.csv")
        total = next(r for r in rows if r["plant"] == "Total")
        self.assertEqual(float(total["feed_mmcf"]), 234001.0)
        self.assertEqual(float(total["fuel_mmcf"]), 47152.0)
        fuel_share = float(total["fuel_mmcf"]) / float(total["total_mmcf"])
        self.assertTrue(0.10 < fuel_share < 0.25, "fuel share %.3f" % fuel_share)
        for s in IndustryData().streams():
            self.assertNotIn("fertil", s.lower())

    def test_the_reference_year_split_is_its_own_not_the_next_years(self):
        """The borrowing, withdrawn and guarded. For one edition the FY2024-25 shares
        stood in for FY2023-24 because Annex-28 had not been read. The reference year now
        has its own observed split, and it must not be equal to the year it was once
        borrowed from - equality here would mean the borrowing came back wearing the
        annex's name."""
        monthly = _load("nfdc", "afr2025_fertilizer_gas_monthly.csv")

        def feed_share(year):
            rows = [r for r in monthly
                    if r["fiscal_year"] == year and r["mmcf"].strip()]
            total = sum(float(r["mmcf"]) for r in rows)
            feed = sum(float(r["mmcf"]) for r in rows if r["consumption"] == "Feed")
            return feed / total

        reference = feed_share("2023-24")
        self.assertTrue(0.83 < reference < 0.84, "FY2023-24 feed share %.4f" % reference)
        self.assertNotEqual(round(reference, 4), round(feed_share("2024-25"), 4))

    def test_including_it_would_change_the_category_materially(self):
        """A guard against the exclusion becoming decorative. If fertiliser gas were small,
        excluding it would not need explaining; it is 2.6 times this category's own gas."""
        data = IndustryData()
        own = sum(data.mmcfd(s) for s in data.streams())
        self.assertGreater(756.0 / own, 2.0)


class TestNoDoubleCount(unittest.TestCase):
    """OGRA Table 3.31 partitions national gas. Four of its rows are now read by four
    different IPCC categories, and they must be four DIFFERENT rows."""

    def test_the_four_ogra_rows_are_distinct(self):
        industry = IndustryData().mmcfd("General Industry")        # 291
        captive = PowerData().captive_total_mmcfd()                # Captive Power
        transport = TransportData().cng_mmcfd(2024)                # Transport (CNG) = 62
        residential = next(float(r["quantity"]) for r in
                           _load("activity", "residential", "fuel_supply.csv")
                           if r["fuel"] == "Natural Gas")          # 821
        vals = [industry, captive, transport, residential]
        self.assertEqual(len(set(vals)), 4, "two sectors read the same OGRA row: %s" % vals)

    def test_captive_and_industry_are_separate_categories(self):
        """Both are 1A2 and both burn pipeline gas. They are estimated apart because they are
        metered apart - one turns gas into electricity, the other raises steam."""
        cats = {c for s in registry.all_sectors() for c in s.CATEGORIES}
        self.assertIn("Industrial fuel combustion (1A2)", cats)
        self.assertIn("Captive gas self-generation (1A2)", cats)


class TestSharedGasAssumption(unittest.TestCase):
    """Three sectors now burn Pakistani pipeline gas as a metered volume. One gas, one set of
    assumptions, or the inventory is internally inconsistent in a way no output reveals."""

    def test_the_heating_value_matches_captive_and_cng(self):
        i, p, t = IndustryData(), PowerData(), TransportData()
        self.assertEqual(i.p("industry_hhv_btu_per_scf"), p.p("captive_hhv_btu_per_scf"))
        self.assertEqual(i.p("industry_hhv_btu_per_scf"), t.p("cng_hhv_btu_per_scf"))

    def test_the_gross_to_net_ratio_matches_too(self):
        i, p, t = IndustryData(), PowerData(), TransportData()
        self.assertEqual(i.p("industry_gross_to_net"), p.p("captive_gross_to_net"))
        self.assertEqual(i.p("industry_gross_to_net"), t.p("cng_gross_to_net"))

    def test_the_factors_match_the_captive_ones(self):
        """Same table, same fuel. Carried as separate rows only so the category key does not
        say 'captive' inside an industry module."""
        i, p = IndustryData(), PowerData()
        for a, b in (("industry_combustion_co2", "captive_combustion_co2"),
                     ("industry_combustion_ch4", "captive_combustion_ch4"),
                     ("industry_combustion_n2o", "captive_combustion_n2o")):
            self.assertEqual(i.efv(a, "Natural Gas"), p.efv(b, "Natural Gas"), msg=a)

    def test_the_industrial_methane_factor_is_not_the_residential_one(self):
        """Table 2.3 gives 1 kg/TJ; Table 2.5's residential value is 5. The parallel-table
        trap this inventory documents in three other sectors."""
        self.assertEqual(IndustryData().efv("industry_combustion_ch4", "Natural Gas"), 1)


class TestStreams(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = IndustryData()

    def test_methane_is_flagged_fossil(self):
        for c in engine.build_components(self.data):
            if c["gas"] == "CH4":
                self.assertTrue(c.get("fossil", False), msg=c["subitem"])
                self.assertAlmostEqual(c["co2e_Mt_AR5"], c["emissions_Gg"] * 30 / 1000.0,
                                       places=12)

    def test_the_cement_gas_row_is_effectively_nil(self):
        """Carried to close a boundary the cement paper names, not to add emissions:
        Pakistani kilns burn coal and petroleum coke."""
        cement = sum(c["co2e_Mt_AR5"] for c in engine.build_components(self.data)
                     if c["subitem"].startswith("Cement gas"))
        self.assertLess(cement, 0.01)
        # The prefix is now load-bearing: "Cement-sector coal" (rc46 Wave 2, 10.8 Mt) also
        # starts with "Cement", and the bare prefix silently swept it in here once.

    def test_a_missing_stream_raises(self):
        with self.assertRaises(KeyError):
            self.data.mmcfd("Steel")

    def test_the_heating_value_sensitivity_is_published(self):
        """A 10% cut in heating value moves the GAS streams by 10% and the liquids not at
        all, because the liquids are metered in tonnes and converted by calorific value,
        not by a gas heating value. The sector therefore moves by less than 10% - and the
        gap between the two numbers is the share of 1A2 that is no longer gas."""
        def total(comps, pred):
            return sum(c["co2e_Mt_AR5"] for c in comps if pred(c))
        liquids = tuple(combustion.LIQUID_LABELS.values())
        solids = ("Brick-kiln coal", "Cement-sector coal")
        is_gas = lambda c: not c["subitem"].startswith(liquids + solids)   # noqa: E731

        base = engine.build_components(self.data)
        low = engine.build_components(self.data, hhv_btu=900)
        self.assertAlmostEqual(total(low, is_gas) / total(base, is_gas), 0.9, delta=0.01)
        # rc46 Wave 2: the coal streams, like the liquids, do not move with a GAS heating
        # value - they are metered in tonnes on their own NCV.
        self.assertAlmostEqual(total(low, lambda c: not is_gas(c)),
                               total(base, lambda c: not is_gas(c)), places=12)
        # The whole-sector ratio at hhv 900: was 0.938 when gas was 62% of the module;
        # with the rc46 solid streams the gas share fell to ~25% and the ratio is 0.975.
        # The pinned figure IS the gas share made visible, so it moves with the boundary.
        self.assertAlmostEqual(sum(c["co2e_Mt_AR5"] for c in low)
                               / sum(c["co2e_Mt_AR5"] for c in base), 0.975, delta=0.01)


class TestDownscale(unittest.TestCase):
    def test_the_proxy_uses_the_reported_utility_split(self):
        """The 53/47 division between SNGPL and SSGCL territory is the actual reported split
        of the gas being allocated, not a stand-in for it."""
        shares = downscale.load_shares()[downscale.PROXY]
        self.assertAlmostEqual(sum(shares.values()), 1.0, places=6)
        sngpl_side = shares["Punjab"] + shares["Khyber Pakhtunkhwa"] + shares["Other"]
        self.assertAlmostEqual(sngpl_side, 155.0 / 291.0, places=3)

    def test_it_differs_from_the_captive_geography_it_is_built_from(self):
        """If the utility split changed nothing, the extra row would be pointless."""
        shares = downscale.load_shares()
        self.assertGreater(abs(shares[downscale.PROXY]["Punjab"]
                               - shares["captive_gas"]["Punjab"]), 0.05)

    def test_an_unknown_category_raises(self):
        with self.assertRaises(KeyError):
            downscale.proxy_for({"category": "Steel production", "subitem": "x"})


class TestRegistration(unittest.TestCase):
    def test_industry_is_registered(self):
        self.assertIn("industry", [s.NAME for s in registry.all_sectors()])


if __name__ == "__main__":
    unittest.main()
