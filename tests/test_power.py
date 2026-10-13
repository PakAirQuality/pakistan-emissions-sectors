"""Tests for the power sector (IPCC 1A1a).

The general contract is enforced in test_sector_contract.py over every registered sector.
These are this sector's own invariants: the emission-factor table choice, the absence of a
separate oxidation factor, the coal blend, and the benchmarks.

Run:  python3 -m unittest discover tests
"""

from pkinv.assets import asset_path
import unittest

from pkinv.core import registry
from pkinv.sectors.power import combustion
from pkinv.sectors.power.data import PowerData


class TestActivity(unittest.TestCase):
    def setUp(self):
        self.data = PowerData()

    PRINTED_TABLE3_TOTAL = {2013: 15466062, 2014: 15715964, 2015: 16251764,
                            2016: 17356968, 2017: 19040364,
                            2018: 15379359, 2019: 14789647, 2020: 15081164,
                            2021: 18629088, 2022: 16853314}

    def test_the_transcription_reconciles_with_the_report_total(self):
        """SIR Table 3's printed Total row against the TRANSCRIPTION, for every year.

        This used to read data.fuel_for(), and after the coal re-base it failed by 26,224 TOE
        in FY2013-14 - correctly, because fuel_for() no longer returns Table 3's coal. The
        transcription is still Table 3 and must still reconcile with its own printed total;
        that is what this guards. What the engine BOOKS is the next test, and the two being
        different files is the whole point of the booking table.
        """
        rows = {}
        for r in self.data.fuel:
            rows.setdefault(r["fiscal_year"], {})[r["fuel"]] = r["toe"]
        for year, total in self.PRINTED_TABLE3_TOTAL.items():
            self.assertAlmostEqual(sum(rows[year].values()), total, delta=1.0,
                                   msg="FY%d" % year)

    def test_the_engine_books_the_station_coal_and_table_three_everything_else(self):
        """The re-base, asserted where it happens: every fuel but coal is Table 3's own
        number, and coal is the booking table's - so the difference between the engine's
        total and Table 3's printed total is EXACTLY the coal move, with nothing else
        riding along."""
        rows = {}
        for r in self.data.fuel:
            rows.setdefault(r["fiscal_year"], {})[r["fuel"]] = r["toe"]
        for year in self.PRINTED_TABLE3_TOTAL:
            booked = self.data.fuel_for(year)
            for fuel, toe in rows[year].items():
                if fuel != "Coal":
                    self.assertEqual(booked[fuel], toe, "FY%d %s moved" % (year, fuel))
            self.assertAlmostEqual(
                sum(booked.values()) - self.PRINTED_TABLE3_TOTAL[year],
                booked["Coal"] - rows[year]["Coal"], delta=1.0, msg="FY%d" % year)

    def test_the_booking_tables_superseded_column_is_table_threes_own_number(self):
        """A booking table that carried its own copy of the figure it supersedes could drift
        from the transcription and nothing would notice - the whole re-base would then rest on
        a number with no source."""
        from pkinv.assets import asset_path
        from pkinv.core.io import read_rows
        from pkinv.paths import DATA
        rows = {}
        for r in self.data.fuel:
            if r["fuel"] == "Coal":
                rows[r["fiscal_year"]] = r["toe"]
        seen = 0
        for r in read_rows(asset_path(DATA, "activity", "power",
                                      "coal_energy_booking.csv"), comments=True):
            year = int(r["fiscal_year"])
            self.assertAlmostEqual(float(r["superseded_toe"]), rows[year], delta=0.5,
                                   msg="FY%d" % year)
            seen += 1
        self.assertEqual(seen, 11, "the booking table no longer covers every fuel year")

    def test_the_series_spans_eleven_years(self):
        years = sorted({r["fiscal_year"] for r in self.data.fuel})
        self.assertEqual(years, list(range(2013, 2024)))

    def test_coal_grew_while_gas_fell(self):
        """The build-out this sector exists to measure, re-anchored on the booked account.

        RENAMED from test_coal_overtook_gas, because on the booked account coal did NOT
        overtake gas: coal is 206,606 TJ against gas's 313,243 in the reference year. It
        overtook gas on Table 3's published energy, and a test whose NAME asserts a crossing
        that the booked account does not show is a test that reads as evidence for something
        it never checked. Coal is still the largest EMITTER of the four, at 51.6 per cent of
        the category's CO2 against gas's 43.6, because its factor is higher - which is the
        fact the sector actually rests on.

        Table 3's coal tripled between FY2018-19 and FY2022-23; the stations' own metered
        coal rises by 1.40 over the same pair, because Table 3's flat conversion was reading
        a rank change as a quantity change. The build-out is real either way - the fleet went
        from two imported-coal units to a Thar lignite fleet - but its SIZE is a property of
        which account you read, and the old threshold was a property of Table 3. The gas side
        is untouched by the re-base and still falls by a quarter.
        """
        early, late = self.data.fuel_for(2018), self.data.fuel_for(2022)
        self.assertGreater(late["Coal"] / early["Coal"], 1.3)
        self.assertLess(late["Gas"] / early["Gas"], 0.8)
        table3 = {}
        for r in self.data.fuel:
            if r["fuel"] == "Coal":
                table3[r["fiscal_year"]] = r["toe"]
        self.assertGreater(table3[2022] / table3[2018], 2.5,
                           "Table 3's own coal series no longer triples; the contrast this "
                           "test draws has gone and the comment above is now wrong")


class TestFactorConvention(unittest.TestCase):
    """The two traps that would silently bias the whole sector."""

    def setUp(self):
        self.data = PowerData()
        self.sector = registry.get("power")

    def test_no_separate_oxidation_factor(self):
        """The 2006 Guidelines fold complete oxidation into the emission factor - Table
        1.4's oxidation column is 1.0 for every fuel. Applying the old 1996-era 0.98 on
        top would double-discount. Asserted exactly, so a later 'fix' fails loudly.

        Note the deliberate contrast with the waste sector, which DOES carry an oxidation
        factor of 0.71, because open burning genuinely is incomplete.

        THE ONE FACTOR THAT IS NOT AN OXIDATION FACTOR: since rc19 the gas rows book
        combustion NET of the post-meter leaked whole-gas share (a mass-boundary
        decision - the leaked gas never reaches a burner and is booked in 1.B.2 -
        not a combustion-efficiency discount). It is asserted here exactly, from its
        one home, so this test still fails loudly on any OTHER factor appearing."""
        from pkinv.sectors.fugitives import post_meter
        tj = combustion.fuel_TJ(self.data)
        comps = {c["subitem"]: c for c in self.sector.build_components(self.data)}
        ef = self.data.efv("power_combustion_co2", "Natural Gas")
        self.assertAlmostEqual(comps["Gas CO2"]["emissions_Gg"],
                               tj["Gas"] * post_meter.combusted_fraction() * ef / 1e6,
                               places=9)
        # and the liquid/coal rows carry no such factor: delivered is burned
        ef_coal = combustion.coal_co2_factor(self.data)
        self.assertAlmostEqual(comps["Coal CO2"]["emissions_Gg"],
                               tj["Coal"] * ef_coal / 1e6, places=9)

    def test_uses_the_energy_industries_table(self):
        """Chapter 2 has four parallel tables and only Table 2.2 is 1A1. CO2 is identical
        across all four, but CH4 and N2O are not, so the wrong table inflates non-CO2."""
        for item in ("Natural Gas", "Residual Fuel Oil", "Other Bituminous Coal", "Lignite"):
            src = self.data.ef[("power_combustion_co2", item)]["source"]
            self.assertIn("Table 2.2", src)
            self.assertIn("Energy Industries", src)

    def test_methane_IS_flagged_fossil(self):
        """Coal, gas and oil products are all fossil, so their CH4 takes AR5 30 not 28 -
        same as aviation, the opposite of waste. Bagasse is the one deliberate exception:
        biomass CH4 is non-fossil and takes 28, and both directions are pinned so neither
        flag can drift onto the other stream."""
        ch4 = [c for c in self.sector.build_components(self.data) if c["gas"] == "CH4"]
        self.assertTrue(ch4)
        for c in ch4:
            if c["subitem"].startswith("Bagasse"):
                self.assertFalse(c.get("fossil", False))
                self.assertAlmostEqual(c["co2e_Mt_AR5"],
                                       c["emissions_Gg"] * 28.0 / 1000.0, places=9)
            else:
                self.assertTrue(c.get("fossil", False), msg=c["subitem"])
                self.assertAlmostEqual(c["co2e_Mt_AR5"],
                                       c["emissions_Gg"] * 30.0 / 1000.0, places=9)

    def test_coal_blend_sits_between_its_bounds(self):
        """SIR reports one combined Coal figure, so the Thar-lignite and imported-
        bituminous factors are blended. The blend must lie between the two bounds, and the
        spread should be small because TOE is an energy unit - on a mass basis these two
        factors differ by a factor of two."""
        tot = lambda ov: sum(c["co2e_Mt_AR5"]
                             for c in self.sector.build_components(self.data, coal_override=ov))
        blend, bit, lig = tot(None), tot("bituminous"), tot("lignite")
        self.assertLess(bit, blend)
        self.assertLess(blend, lig)
        self.assertLess((lig - bit) / blend, 0.10, "coal choice should move the total <10%")


class TestBenchmarks(unittest.TestCase):
    def setUp(self):
        self.sector = registry.get("power")
        self.data = PowerData()
        self.total = sum(c["co2e_Mt_AR5"] for c in self.sector.build_components(self.data))

    def test_total_in_the_expected_band(self):
        """Fuel-based, FY2022-23. Ember's Pakistani electricity CO2 is the closest free
        comparator once its captive/distributed generation is set aside."""
        self.assertTrue(40.0 < self.total < 70.0, "power total %.1f Mt" % self.total)

    def test_coal_is_far_below_climate_trace(self):
        """Climate TRACE's coal-labelled assets sum to ~56 Mt, implying 2,431 g CO2e/kWh
        against a physical ceiling near 1,100; this method puts coal near 32 Mt. The
        benchmark is now READ FROM THE FILE it cites rather than hardcoded, so the CSV,
        the README's table and this assertion can no longer drift apart silently. The
        per-plant resolution (benchmarks_plants) shows the anomaly is the label's one
        modelled intensity, not any plant's operation."""
        from pkinv.sectors.power import benchmarks_plants
        trace = benchmarks_plants.coal_label_total_Mt()
        self.assertAlmostEqual(trace, 56.19, delta=0.05,
                               msg="the committed TRACE file changed - re-audit the "
                                   "per-plant findings before trusting the new total")
        coal = sum(c["co2e_Mt_AR5"] for c in self.sector.build_components(self.data)
                   if c["subitem"].startswith("Coal"))
        self.assertLess(coal, 40.0)
        self.assertGreater(trace / coal, 1.4,
                           "gap against Climate TRACE has closed unexpectedly")


class TestBagasse(unittest.TestCase):
    """The sector's one biomass stream: the memo convention, the E3 reconciliation, and
    the geography that is exact by construction."""

    @classmethod
    def setUpClass(cls):
        from pkinv.sectors.power import bagasse, engine
        cls.bagasse, cls.engine = bagasse, engine
        cls.data = PowerData()

    def test_e3_reconciles_with_the_printed_total(self):
        """Table 8's own Total row for FY2023-24 is 726.85 GWh; the parser refuses to
        write a CSV that disagrees, and this pins the committed file too."""
        self.assertAlmostEqual(self.bagasse.generation_GWh(self.data), 726.85, places=2)

    def test_biogenic_co2_is_a_memo_and_never_a_component(self):
        comps = self.engine.build_components(self.data)
        self.assertFalse([c for c in comps if c["subitem"] == "Bagasse CO2"])
        memo = self.engine.memo_items(self.data)
        self.assertEqual(len(memo), 1)
        self.assertGreater(memo[0]["emissions_Gg"], 500.0)
        total = sum(c["co2e_Mt_AR5"] for c in comps)
        self.assertLess(total, 65.0, "memo CO2 (~1.1 Mt) must not have leaked into the total")

    def test_the_factor_is_the_energy_industries_one(self):
        """Table 2.2 gives 30 kg CH4/TJ; the residential table gives 300 for the same
        fuel. The parallel-table trap, pinned in both sectors."""
        self.assertEqual(self.data.efv("power_combustion_ch4",
                                       "Other Primary Solid Biomass"), 30)

    def test_bagasse_rides_its_own_geography(self):
        """The stream takes its own proxy row, the eight plants' generation by province,
        rather than the thermal fleet's.

        rc66: this asserted Punjab == 1.0, on NEPRA Table 5's printed districts. Two of those
        districts are contradicted by the plant's own coordinate and by the generation
        workbook: Almoiz is in Dera Ismail Khan (Khyber Pakhtunkhwa) and Jamal Din Wali-III
        in Ghotki (Sindh). pkinv.sectors.power.province_panel.BAGASSE_PLACEMENT carries the
        evidence and tests/test_province_panel.py repeats the polygon test."""
        from pkinv.sectors.power import downscale
        shares = downscale.load_shares()["bagasse_grid"]
        self.assertAlmostEqual(sum(shares.values()), 1.0, places=5)
        self.assertGreater(shares["Punjab"], 0.6)
        self.assertGreater(shares["Sindh"], 0.2)
        self.assertGreater(shares["Khyber Pakhtunkhwa"], 0.0)
        c = {"category": "Electricity and heat production", "subitem": "Bagasse CH4"}
        self.assertEqual(downscale.proxy_for(c), "bagasse_grid")

    def test_a_year_before_the_series_contributes_nothing(self):
        comps, memo = self.bagasse.compute(self.data, 2018)
        self.assertEqual((comps, memo), ([], []))

    def test_cofiring_is_recorded_not_split(self):
        """The Thal Industries Corporation lists furnace oil as its alternate fuel - the
        fossil-in-renewable case. It must stay visible in the data file."""
        rows = self.bagasse.rows(2023)
        thal = next(r for r in rows if "Thal" in r["plant"])
        self.assertEqual(thal["fuel_alternate"], "FO")


class TestDecomposition(unittest.TestCase):
    """LMDI-I over the grid series: exact by construction, signed by the known story."""

    @classmethod
    def setUpClass(cls):
        from pkinv.sectors.power import decomposition
        cls.D = decomposition
        cls.data = PowerData()

    def test_terms_close_exactly(self):
        """A decomposition that needs a residual is hiding something. LMDI-I closes to
        machine precision, every span."""
        for r in self.D.series_rows(self.data):
            self.assertLess(abs(r["closure"]), 1e-9,
                            msg="FY%d->FY%d" % (r["y0"], r["y1"]))

    def test_the_signs_match_the_known_story(self):
        """FY2018-19 -> FY2023-24: the fuel mix shifts to coal while oil and gas retreat.

        WHAT THIS TEST USED TO SAY, AND WHY IT CHANGED. It asserted that the period was a
        RISE dominated by the mix term, with the coal mix term above 20 Mt. On the booked
        coal account the grid falls 46.84 -> 40.02 Mt over the same pair, the activity term
        (-9.87) dominates, and the coal mix term is +9.16. Both the direction of the total
        and the size of the coal term were properties of Table 3's flat conversion, which
        read a change of coal RANK as a change of coal QUANTITY - so the old thresholds
        were measuring the conversion and not the fleet.

        WHAT SURVIVES, and it is the part that was ever about the fleet: coal's mix term is
        positive and the largest positive one, furnace oil's and gas's are negative, and the
        displacement is real on any account. The magnitudes are no longer asserted as
        thresholds, because a threshold on a quantity that moves with the coal account is a
        threshold on the coal account.
        """
        r = self.D.decompose(self.data, 2018, 2023)
        mix = r["per_fuel"]
        self.assertGreater(mix["Coal"]["mix"], 0.0)
        self.assertLess(mix["Furnace Oil"]["mix"], 0.0)
        self.assertLess(mix["Gas"]["mix"], 0.0)
        self.assertEqual(max(mix, key=lambda f: mix[f]["mix"]), "Coal")
        # The sign reversal itself, pinned so it cannot flip back unnoticed: the total falls,
        # and it falls because the activity term does.
        self.assertLess(r["delta_Mt"], 0.0)
        self.assertLess(r["activity_Mt"], 0.0)
        self.assertGreater(r["mix_Mt"], 0.0)

    def test_the_factor_term_now_sees_the_coal_switch(self):
        """This test used to assert the factor term was exactly ZERO, because the engine
        applied the FY2023-24 coal blend to every year - and the module's docstring called
        that a limitation and predicted the true series would carry a small positive term.
        The per-year blend is wired now and the prediction held: the term is positive,
        small against mix, and points the right way as the fleet moved from imported
        bituminous toward Thar lignite."""
        r = self.D.decompose(self.data, 2018, 2023)
        self.assertGreater(r["factor_Mt"], 0.0)
        self.assertLess(r["factor_Mt"], r["mix_Mt"])
        # The third assertion used to be factor < activity. The activity term is NEGATIVE on
        # the booked account, so that comparison now says only that a positive number exceeds
        # a negative one, which is not a fact about the blend. What the docstring predicted is
        # that the factor term is SMALL, and smallness against the total move is the
        # assertion that still means it.
        self.assertLess(r["factor_Mt"], abs(r["delta_Mt"]))

    def test_the_fy2021_step_is_an_activity_step_on_either_account(self):
        """FY2020-21 -> FY2021-22 was a demand story, not a mix story, and it still is.

        On Table 3 the pair was +16 Mt and the activity term carried it. On the booked coal
        account the pair is -2.77 Mt and the activity term (-3.16) still carries it, with the
        mix term an order of magnitude smaller (+0.33). The sign of the step is a property of
        the coal account; the fact that ACTIVITY and not MIX explains it is not, and that is
        what this asserts - by magnitude rather than by signed comparison, because a signed
        comparison between terms of opposite sign would pass for the wrong reason.
        """
        r = self.D.decompose(self.data, 2020, 2021)
        self.assertGreater(abs(r["activity_Mt"]), 3 * abs(r["mix_Mt"]))


class TestClimateTracePlants(unittest.TestCase):
    """The benchmark, plant-resolved: the label factor, the imputation twins, and the
    gas plants that agree."""

    @classmethod
    def setUpClass(cls):
        from pkinv.sectors.power import benchmarks_plants
        cls.B = benchmarks_plants
        cls.rows = benchmarks_plants.comparison(PowerData())

    def test_one_intensity_for_the_whole_coal_label(self):
        """Every coal-labelled asset with activity carries the same g/kWh to the gram -
        the sharpest possible signature of a modelled factor rather than plant data."""
        g = {round(r["trace_g_per_kwh"]) for r in self.rows
             if r["asset_type"] == "coal" and r["trace_g_per_kwh"] != ""}
        self.assertEqual(g, {2431})

    def test_the_imputation_twins_are_flagged(self):
        flagged = {r["trace_name"] for r in self.rows if "imputation" in r["flags"]}
        for name in ("Balloki power station", "Bhikki power station",
                     "Haveli Bahadur Shah (HBS) power station",
                     "ThalNova power station", "Thar Energy Limited power station",
                     "Port Qasim Lucky power station", "Thar Block II power station"):
            self.assertIn(name, flagged)

    def test_the_metered_gas_plants_agree(self):
        """Uch and Trimmu - exact-MMBTU plants - sit within a few percent of TRACE.
        The benchmark works where the fuels are metered; the anomaly is coal-specific."""
        by_name = {r["trace_name"]: r for r in self.rows}
        self.assertAlmostEqual(by_name["Uch power station"]["trace_over_engine"],
                               1.0, delta=0.1)
        self.assertAlmostEqual(by_name["Trimmu power station"]["trace_over_engine"],
                               1.0, delta=0.1)

    def test_hubco_misassignment_is_flagged(self):
        hub = next(r for r in self.rows if r["trace_name"] == "Hubco power station")
        self.assertIn("zero fuel", hub["flags"])

    def test_every_coal_ratio_is_high(self):
        """No grid coal plant sits near 1.0 against TRACE - the gap is label-wide."""
        for r in self.rows:
            if (r["asset_type"] == "coal" and r["trace_over_engine"] != ""
                    and r["ledger_plant"] and r["ledger_plant"] != "Hub"):
                self.assertGreater(r["trace_over_engine"], 1.2, msg=r["trace_name"])


class TestUncertaintyRebuild(unittest.TestCase):
    """The evidence-class uncertainty: per-fuel widths, the shared-conversion group, the
    delta-method coal factor, and the structural cases kept unsampled."""

    @classmethod
    def setUpClass(cls):
        from pkinv.sectors.power import engine, uncertainty
        cls.U = uncertainty
        cls.data = PowerData()
        cls.comps = engine.build_components(cls.data)

    def test_per_fuel_widths(self):
        """The rebuilt component uncertainties. If a flat scalar ever returns, these
        collapse back to one value and fail."""
        want = {"Coal CO2": 10.9, "Gas CO2": 10.8, "Furnace Oil CO2": 12.4,
                "Diesel Oil CO2": 10.2}
        got = {c["subitem"]: c["uncert_pct"] for c in self.comps}
        for k, v in want.items():
            self.assertAlmostEqual(got[k], v, delta=0.1, msg=k)

    def test_the_conversion_group_covers_exactly_the_four_grid_co2_rows(self):
        grouped = {c["subitem"] for c in self.comps
                   if c.get("corr_group") == combustion.TOE_CORR_GROUP}
        self.assertEqual(grouped, {"Coal CO2", "Gas CO2", "Furnace Oil CO2",
                                   "Diesel Oil CO2"})

    def test_delta_method_by_hand(self):
        """The formula, recomputed independently of the module."""
        import math
        d = self.data
        share, lig, bit = 0.79, 101000.0, 94600.0
        blend = bit * (1 - share) + lig * share
        u = math.sqrt((share * lig / blend * 12) ** 2
                      + ((1 - share) * bit / blend * 6) ** 2
                      + (share * (lig - bit) / blend * 12) ** 2)
        self.assertAlmostEqual(combustion.coal_co2_factor_uncert(d), u, places=6)
        self.assertAlmostEqual(u, 9.70, delta=0.02)

    def test_grouped_exceeds_independent(self):
        """The group is the conservative reading of one shared conversion practice;
        both are published and the ordering is the point."""
        a1 = {r["category"]: r for r in self.U.approach1_rows(self.data)}
        g = a1["Electricity and heat production"]
        self.assertAlmostEqual(g["approach1_pct_grouped"], 10.9, delta=0.1)
        self.assertGreater(g["approach1_pct_grouped"],
                           g["approach1_pct_independent"])
        # 2026-10-07 power coal re-base: 57.82049 -> 40.04008. The rebuild must still not
        # move the central estimate; what moved it is the booked account, upstream of here.
        self.assertAlmostEqual(g["co2e_Mt_AR5"], 40.04008, places=5,
                               msg="the rebuild must not move the central estimate")

    def test_scenarios_match_the_published_sensitivities(self):
        """Each named case's deterministic value must equal the corresponding
        sensitivity row - one number, two tables, no drift."""
        import csv as _csv
        import os as _os

        from pkinv.paths import DATA
        path = _os.path.join(_os.path.dirname(DATA), "outputs", "power_totals_fy2023_24.csv")
        with open(path, newline="", encoding="utf-8") as f:
            totals = {r["category"]: r["co2e_Mt_AR5"] for r in _csv.DictReader(f)}
        sc = {r["structural_scenario"]: r
              for r in self.U.structural_scenarios(self.data, n_iter=100)}
        pairs = {
            "coal_all_bituminous": "Sensitivity: all coal bituminous",
            "coal_all_lignite": "Sensitivity: all coal lignite",
            "coal_at_implied_cv": "Sensitivity: coal at ledger mass x implied CV",
            "captive_hhv_900": "Sensitivity: captive gas at 900 Btu/scf",
            "grid_plus_ke_ledger_fuel": "Sensitivity: grid + K-Electric ledger fuel",
        }
        for scen, cat in pairs.items():
            self.assertAlmostEqual(sc[scen]["deterministic_Mt"], float(totals[cat]),
                                   places=3, msg=scen)
        for r in sc.values():
            self.assertLess(r["P2.5_Mt"], r["P50_Mt"])
            self.assertLess(r["P50_Mt"], r["P97.5_Mt"])
            self.assertEqual(r["interpretation"],
                             "conditional parametric interval; no structural probability")

    def test_structural_rows_are_unsampled(self):
        """Discrete choices carry no percentage - a confidence interval must not conceal
        a boundary or coverage choice."""
        table = self.U.full_factor_table(self.data)
        structural = [r for r in table if r["uncertainty_class"] == "structural"]
        self.assertEqual(len(structural), 3)
        for r in structural:
            self.assertEqual(r["distribution"], "not sampled", msg=r["variable"])
            self.assertEqual(r["uncert_pct_95"], "", msg=r["variable"])
        for r in table:
            if r["uncertainty_class"] == "parametric":
                self.assertNotEqual(r["uncert_pct_95"], "", msg=r["variable"])


class TestKELeg(unittest.TestCase):
    """The K-Electric leg: the trend that replaced a flat claim, its corroborations, and
    the sensitivity that publishes it without deciding the boundary."""

    @classmethod
    def setUpClass(cls):
        from pkinv.sectors.power import ke_leg
        cls.ke = ke_leg
        cls.data = PowerData()
        cls.series = ke_leg.series(cls.data)

    def test_the_trend_not_a_flat_number(self):
        """7.1 down to 4.0 Mt across FY2019-23. If these bands ever fail, the '5-6 Mt'
        claim this module retired must not quietly return."""
        by_year = {r["fiscal_year"]: r["co2_Mt"] for r in self.series}
        self.assertAlmostEqual(by_year[2019], 7.13, delta=0.05)
        self.assertAlmostEqual(by_year[2023], 4.01, delta=0.05)
        self.assertGreater(by_year[2019] / by_year[2023], 1.6)

    def test_the_arithmetic_matches_the_boundary_audit(self):
        """Same ledger, same conversions: ke_leg's gas and RFO energies must reproduce
        ke_boundary_audit's to the TJ, or the two K-E stories diverge."""
        from pkinv.sectors.power import plant_ledger
        audit = {a["fiscal_year"]: a for a in plant_ledger.ke_boundary_audit(self.data)}
        for r in self.series:
            a = audit[r["fiscal_year"]]
            self.assertAlmostEqual(r["gas_TJ"] + r["rlng_TJ"], a["KE_gas_TJ"], delta=1.0)
            self.assertAlmostEqual(r["rfo_TJ"], a["KE_rfo_TJ"], delta=1.0)

    def test_efficiency_rises_as_rfo_retires(self):
        """36.9 to 45.5 percent net - the corroboration that the heating-value assumption
        is not badly wrong for K-E. Monotone within rounding."""
        effs = [r["implied_net_efficiency"] for r in self.series]
        self.assertAlmostEqual(effs[0], 0.369, delta=0.005)
        self.assertAlmostEqual(effs[-1], 0.455, delta=0.005)
        self.assertGreater(effs[-1], effs[0])

    def test_no_coal_on_the_ke_side(self):
        """K-Electric burns no coal in any ledger year; a coal row appearing would mean
        the ledger or the parser changed under this module."""
        from pkinv.sectors.power import plant_ledger
        for r in plant_ledger._all_rows():
            if r["system"] == "K-Electric":
                self.assertNotEqual(r["fuel"], "Coal", msg=r["plant"])

    def test_the_case_is_a_sensitivity_not_the_estimate(self):
        import csv as _csv
        import os as _os

        from pkinv.paths import DATA
        path = _os.path.join(_os.path.dirname(DATA), "outputs", "power_totals_fy2023_24.csv")
        with open(path, newline="", encoding="utf-8") as f:
            rows = {r["category"]: r for r in _csv.DictReader(f)}
        row = rows["Sensitivity: grid + K-Electric ledger fuel"]
        grid = float(rows["Electricity and heat production"]["co2e_Mt_AR5"])
        self.assertAlmostEqual(float(row["co2e_Mt_AR5"]),
                               grid + self.ke.fy2023_case(self.data), places=3)
        self.assertIn("trend", row["note"])

    def test_the_emissions_path_never_reads_it(self):
        import inspect

        from pkinv.sectors.power import engine
        for mod in (combustion, engine):
            self.assertNotIn("ke_leg", inspect.getsource(mod))


class TestPointSources(unittest.TestCase):
    """The per-fuel provincial geography: complete join, drift-pinned shares, and the
    mine-mouth rule applied to exactly the plants whose location Table 5 leaves blank."""

    @classmethod
    def setUpClass(cls):
        import csv as _csv
        import os as _os

        from pkinv.paths import DATA
        from pkinv.sectors.power import point_sources
        cls.ps = point_sources
        cls.data = PowerData()
        cls.rows = point_sources.rows(cls.data)
        cls.shares = point_sources.fuel_province_shares(cls.data)
        with open(asset_path(DATA, "province_shares.csv"), newline="",
                  encoding="utf-8") as f:
            cls.committed = {r["proxy"]: r for r in _csv.DictReader(f)}

    def test_every_ledger_row_is_located(self):
        """Unmatched energy is a loud failure, not a silent spread: a new plant in a
        future ledger year must extend the join before it can be allocated."""
        unmatched = [r for r in self.rows if r["located_by"] == "UNMATCHED"]
        self.assertFalse(unmatched, unmatched)

    def test_shares_sum_to_one(self):
        for grp, d in self.shares.items():
            self.assertNotIn("UNMATCHED", d, grp)
            self.assertAlmostEqual(sum(d.values()), 1.0, places=9, msg=grp)

    def test_the_committed_shares_match_the_ledger(self):
        """The drift pin: data/province_shares.csv carries these rows as static data, and
        this recomputation is what stops the CSV outliving its derivation."""
        from pkinv.core.geography import PROVINCES
        # rc66: COAL LEFT THIS LOOP. This function weights coal by per-plant implied
        # calorific values; the committed coal row is now weighted the way the national coal
        # account is booked (tonnage x rank-default NCV), and is pinned against
        # pkinv.sectors.power.province_panel by tests/test_province_panel.py. Gas, furnace
        # oil and diesel have one basis and stay pinned here as well as there.
        for grp in ("power_gas", "power_rfo", "power_hsd"):
            row = self.committed[grp]
            live = self.shares[grp]
            for p in PROVINCES:
                self.assertAlmostEqual(float(row[p]), live.get(p, 0.0), places=3,
                                       msg="%s / %s" % (grp, p))

    def test_coal_is_overwhelmingly_sindh(self):
        """The correction this phase exists for: four Thar mine-mouth plants, Port Qasim
        and Lucky against Sahiwal alone. If this ever drops below 0.8, the fleet or the
        join changed and the paper's geography claims are stale."""
        self.assertGreater(self.shares["power_coal"]["Sindh"], 0.8)
        self.assertLess(self.shares["power_coal"].get("Punjab", 0.0), 0.15)

    def test_the_mine_mouth_rule_covers_exactly_the_blank_locations(self):
        by_rule = {r["plant"] for r in self.rows
                   if r["located_by"].startswith("mine-mouth")}
        self.assertEqual(by_rule, {"Thar Energy", "Thar Coal Block-I", "ThalNova"})
        for r in self.rows:
            if r["located_by"].startswith("mine-mouth"):
                self.assertEqual(r["province"], "Sindh")

    def test_k_electric_is_excluded_from_the_shares(self):
        """The shares describe the fleet behind the national fuel rows, which the
        boundary audit finds are CPPA-only. K-E rows stay in the point-source output."""
        ke = [r for r in self.rows if r["system"] == "K-Electric"]
        self.assertTrue(ke, "K-E plants must still appear in the register")
        # Gul Ahmed and Tapal burn RFO in Karachi; if they entered the share, RFO could
        # not be wholly Punjab.
        self.assertEqual(self.shares["power_rfo"].get("Sindh", 0.0), 0.0)

    def test_coal_energy_weights_ride_the_implied_cvs(self):
        classes = {r["energy_evidence"] for r in self.rows if r["fuel"] == "Coal"}
        self.assertIn("implied CV", classes)
        for r in self.rows:
            if r["fuel"] == "Coal" and r["plant"] == "China Power Hub":
                self.assertIn("fleet CV", r["energy_evidence"],
                              "CPH FY2023 is a flagged outlier and must not carry its "
                              "own 32.5 TJ/Gg into the weights")

    def test_every_fuel_stream_has_a_mapped_proxy(self):
        from pkinv.sectors.power import downscale, engine
        for c in engine.build_components(self.data):
            proxy = downscale.proxy_for(c)
            if c["category"] == "Electricity and heat production":
                self.assertNotEqual(proxy, "power_generation",
                                    "%s fell through to the aggregate fallback"
                                    % c["subitem"])


class TestAirLayer(unittest.TestCase):
    """The uncontrolled air bound: the size-distribution arithmetic, the combustor-type
    split, and the residual that is reported rather than assigned."""

    @classmethod
    def setUpClass(cls):
        from pkinv.sectors.power import air_pollutants, plant_ledger
        cls.air, cls.ledger = air_pollutants, plant_ledger
        cls.data = PowerData()
        cls.rows = air_pollutants.compute(cls.data)
        cls.split = plant_ledger.gas_technology_split(cls.data)

    def _kt(self, fuel, pol, detail=None):
        return sum(r["emissions_kt"] for r in self.rows
                   if r["fuel"] == fuel and r["pollutant"] == pol
                   and (detail is None or detail in r.get("fuel_detail", "")))

    def test_bituminous_pm25_is_six_percent_of_filterable(self):
        """Table 1.1-6 puts 6 percent of filterable mass at or below 2.5 microns. The factor
        is 0.6A on the same 10A mass factor, so the ratio holds whatever ash does."""
        self.assertAlmostEqual(self._kt("Coal", "PM2.5", "bituminous")
                               / self._kt("Coal", "PM", "bituminous"), 0.06, places=9)

    def test_bituminous_pm10_reproduces_the_size_table(self):
        """Table 1.1-4's 2.3A equals Table 1.1-6's 23 percent cumulative at 10 microns -
        the internal check that the size distribution was transcribed right."""
        self.assertAlmostEqual(self._kt("Coal", "PM10", "bituminous")
                               / self._kt("Coal", "PM", "bituminous"), 0.23, places=9)

    def test_lignite_size_fractions_come_from_its_own_table(self):
        """Section 1.7's distribution, not 1.1's: Table 1.7-7 puts 35 percent of
        filterable mass at or below 10 microns and 10 percent at 2.5 (0.66A and 2.3A on
        the 6.5A tangential mass), against 1.1-6's 23 and 6 for bituminous."""
        pm = self._kt("Coal", "PM", "lignite")
        self.assertAlmostEqual(self._kt("Coal", "PM10", "lignite") / pm,
                               2.3 / 6.5, places=9)
        self.assertAlmostEqual(self._kt("Coal", "PM2.5", "lignite") / pm,
                               0.66 / 6.5, places=9)

    def test_the_rank_split_partitions_the_coal_energy(self):
        """79 percent of the coal energy on Section 1.7, the rest on 1.1, and the SO2
        factors are the sections' own 30S and 38S on each rank's own NCV."""
        share = self.data.p("coal_lignite_share")
        lig = [r for r in self.rows if "lignite" in r.get("fuel_detail", "")]
        bit = [r for r in self.rows if "bituminous" in r.get("fuel_detail", "")]
        self.assertTrue(lig and bit)
        self.assertTrue(all(r["ap42_table"].startswith("1.7") for r in lig))
        self.assertTrue(all(r["ap42_table"].startswith("1.1") for r in bit))
        # per-TJ SO2: (30S/11.9) vs (38S/25.8) on the same S - the lignite factor is
        # (30/38)*(25.8/11.9) = 1.71x the bituminous one per unit energy
        k_lig, _ = self.air._coal_kg_per_TJ(30.0, "sulfur", self.data,
                                            "Lignite", "Lignite")
        k_bit, _ = self.air._coal_kg_per_TJ(38.0, "sulfur", self.data)
        self.assertAlmostEqual(k_lig / k_bit, (30.0 / 38.0) * (25.8 / 11.9), places=6)
        so2_lig = self._kt("Coal", "SO2", "lignite")
        so2_bit = self._kt("Coal", "SO2", "bituminous")
        self.assertAlmostEqual(so2_lig / so2_bit,
                               (share / (1 - share)) * (k_lig / k_bit), places=6)

    def test_lignite_carries_no_co_row(self):
        """Table 1.7-1 prints ND for tangential CO: absent, never zero-filled."""
        self.assertEqual(self._kt("Coal", "CO", "lignite"), 0.0)
        self.assertGreater(self._kt("Coal", "CO", "bituminous"), 0.0)

    def test_bagasse_has_exactly_the_two_published_factors(self):
        """Section 1.8 publishes uncontrolled PM and NOx and no SOx or CO factor -
        bagasse sulfur is negligible in the section's prose, not as a zero row."""
        bagasse = [r for r in self.rows if r["fuel"] == "Bagasse"]
        self.assertEqual(sorted(r["pollutant"] for r in bagasse), ["NOx", "PM"])
        self.assertTrue(all(r["ap42_table"] == "1.8-1" for r in bagasse))
        self.assertGreater(self._kt("Bagasse", "PM"), 0.0)

    def test_gas_particulate_is_all_fine(self):
        """AP-42's note on the gas tables: all of it is under a micron, so PM2.5 = PM."""
        for fuel in ("Gas", "Natural Gas"):
            self.assertEqual(self._kt(fuel, "PM2.5"), self._kt(fuel, "PM"), msg=fuel)

    def test_grid_gas_nox_sits_between_the_two_chapters(self):
        """The blend can only land between boiler-only and turbine-only; outside that band
        the share stopped being a share."""
        energy = combustion.fuel_TJ(self.data)["Gas"]
        k_boil, _ = self.air._gas_kg_per_TJ(self.air.GAS_LB_PER_MMSCF["NOx"][0])
        tv = self.air.GAS_TURBINE_NOX_LB_PER_MMBTU[0]
        k_turb = tv * self.air._KG_PER_LB / self.air._TJ_PER_MMBTU
        got = next(r["emissions_kt"] for r in self.rows
                   if r["fuel"] == "Gas" and r["pollutant"] == "NOx")
        self.assertGreater(got, energy * k_boil / 1e6)
        self.assertLess(got, energy * k_turb / 1e6)

    def test_the_grid_gas_nox_row_names_both_chapters(self):
        row = next(r for r in self.rows
                   if r["fuel"] == "Gas" and r["pollutant"] == "NOx")
        self.assertEqual(row["ap42_table"], "1.4-1/3.1-1")

    def test_captive_has_left_the_grid_screening(self):
        """rc58: captive self-generation is IPCC 1.A.2 and is priced once, in the industrial
        air layer, on stationary-engine and gas-turbine factors under declared fleet shares
        (air_source_classes.csv classes captive_gas_engine / captive_gas_turbine). The
        grid screening therefore carries no captive row unless asked for the transcription
        check (include_captive=True), and never in its shipped file."""
        self.assertFalse([r for r in self.rows if r["fuel"] == "Natural Gas"])
        from pkinv.sectors.power import air_pollutants as pap, captive
        with_cap = pap.compute(self.data, include_captive=True)
        self.assertTrue([r for r in with_cap if r["category"] == captive.CATEGORY])

    def test_the_split_partitions_and_reports_its_residual(self):
        s = self.split
        self.assertAlmostEqual(s["turbine_TJ"] + s["boiler_TJ"] + s["unresolved_TJ"],
                               s["total_TJ"], places=6)
        self.assertGreater(s["turbine_share"], 0.5,
                           "the grid gas fleet is combined-cycle-heavy; if this flips, "
                           "re-audit the ledger before trusting the blend")
        self.assertGreater(s["unresolved_TJ"], 0.0,
                           "the residual is reported, not absorbed; if classification ever "
                           "becomes total, celebrate in the paper, not silently here")
        self.assertLess(s["unresolved_share"], 0.15)

    def test_the_split_excludes_k_electric(self):
        """The share describes the fleet behind the national gas row, and the boundary
        audit finds that row covers the CPPA side only."""
        for bucket in ("turbine_plants", "boiler_plants", "unresolved_plants"):
            for name in self.split[bucket]:
                self.assertNotIn("Bin Qasim", name, msg=bucket)

    def test_steam_era_names_do_not_decide_the_split(self):
        """Names lie here - Guddu units 14-16 carry 'TPS' over what heat rate shows is not
        running as a combined cycle, and K-E's TPS-III is one. Heat rate decides; the only
        name evidence accepted is turbine hardware (GTPS, CCPP)."""
        self.assertTrue(any("TPS" in p for p in self.split["boiler_plants"]))
        self.assertFalse(any("TPS" in p and "GTPS" not in p
                             for p in self.split["turbine_plants"]))

    def test_the_emissions_path_never_reads_the_air_layer(self):
        import inspect

        from pkinv.sectors.power import engine
        for mod in (combustion, engine):
            self.assertNotIn("air_pollutants", inspect.getsource(mod))


if __name__ == "__main__":
    unittest.main()
