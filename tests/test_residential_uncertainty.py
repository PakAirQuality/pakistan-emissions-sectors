"""The residential uncertainty module: the decomposition, the named cases, and the
sampled PM ratio that replaces the bare 20:1.

The strongest pin here is the corroboration scenario: dung_basis_daf routes the dung
stream through an INDEPENDENT dry-ash-free NCV on the ash-free VS mass, and must land
within a few percent of the corrected air-dry pairing. If it drifts, either the
correction or the corroboration literature value broke - both worth a loud failure.

rc67 (2026-10-13). The reference dung quantity became the household survey series
(10.93 Mt of cake in FY2023-24) and burning all the diverted dung in households
(58.74 Mt) became configuration L. The mass chain the corroboration checks is
configuration L's, so both mass-basis scenarios are now compared with the scenario
dung_all_diverted_household and not with the reference; the scenario dung_activity_hies
is gone because what it priced is the reference.

Run:  python3 -m unittest discover tests -p "test_residential_uncertainty.py"
"""
import unittest

from pkinv.sectors.residential import combustion, engine
from pkinv.sectors.residential import uncertainty as unc
from pkinv.sectors.residential.data import ResidentialData


class TestApproach1(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = ResidentialData()
        cls.a1 = unc.approach1(cls.data)

    def test_the_total_is_the_engines(self):
        total = sum(c["co2e_Mt_AR5"] for c in engine.build_components(self.data))
        self.assertAlmostEqual(self.a1["co2e_Mt_AR5"], total, places=9)

    def test_grouped_is_at_least_independent(self):
        """Sharing each stream's activity across its gas rows adds covariance; the
        grouped figure must not come out below the independent one."""
        self.assertGreaterEqual(self.a1["approach1_pct_grouped"],
                                self.a1["approach1_pct_independent"] - 1e-9)

    def test_every_stream_has_an_activity_key(self):
        """The grouped decomposition silently drops a stream whose first word is not
        in the map - so the map must cover every component."""
        words = {unc._stream_word(c)
                 for c in engine.build_components(self.data)}
        self.assertEqual(words, set(unc._AD_KEY))

    def test_the_band_is_dominated_by_biomass_factors(self):
        """The sector's character: a metered-gas core inside a wide biomass band.
        The grouped figure must sit well above the gas stream's own uncertainty and
        well below the biomass rows' 150-plus."""
        self.assertGreater(self.a1["approach1_pct_grouped"], 20.0)
        self.assertLess(self.a1["approach1_pct_grouped"], 60.0)


class TestStructuralScenarios(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = ResidentialData()
        cls.scen = {r["structural_scenario"]: r
                    for r in unc.structural_scenarios(cls.data, n_iter=2000)}

    def test_the_reference_is_the_engine(self):
        ref = self.scen["reference"]
        total = sum(c["co2e_Mt_AR5"] for c in engine.build_components(self.data))
        self.assertAlmostEqual(ref["deterministic"], total, places=9)

    def test_the_daf_corroboration_lands_on_the_corrected_pairing(self):
        """The independent energy route (VS x dry-ash-free NCV) must reproduce the
        corrected estimate within five percent - the audit's own cross-check.

        Since rc67 the corrected air-dry pairing it corroborates is configuration L's
        mass chain (the survey quantity has no VS route), so the comparison is with the
        all-diverted scenario. Against the reference it would be 21.5 percent away, which
        is the size of the configuration, not a failure of the route."""
        ledger = self.scen["dung_all_diverted_household"]["deterministic"]
        daf = self.scen["dung_basis_daf"]["deterministic"]
        self.assertLess(abs(daf - ledger) / ledger, 0.05)

    def test_the_legacy_basis_sits_below(self):
        """The superseded VS pairing under-massed the stream; the scenario must show
        the correction's direction, not just its existence.

        The stream it under-massed is configuration L's (rc67), so "below" is below the
        all-diverted scenario. It is no longer below the reference: two thirds of the
        diverted supply is still 3.5 times what the survey reports households burning."""
        self.assertLess(self.scen["dung_basis_legacy_vs"]["deterministic"],
                        self.scen["dung_all_diverted_household"]["deterministic"])
        self.assertGreater(self.scen["dung_basis_legacy_vs"]["deterministic"],
                           self.scen["reference"]["deterministic"])

    def test_configuration_l_is_the_engine_on_the_ledger_basis(self):
        """The all-diverted scenario scales the reference dung rows by ledger/survey;
        it must land on the engine run with the ledger basis, to the digit, and on the
        figure every release through rc66 published as the reference (29.4667)."""
        ledger = sum(c["co2e_Mt_AR5"]
                     for c in engine.build_components(self.data, dung_basis="ledger"))
        self.assertAlmostEqual(
            self.scen["dung_all_diverted_household"]["deterministic"], ledger, places=9)
        self.assertAlmostEqual(ledger, 29.4667, places=4)
        self.assertAlmostEqual(self.scen["reference"]["deterministic"], 24.2204,
                               places=4)

    def test_the_survey_rounds_bracket_the_reference(self):
        """Through rc66 this test held dung_activity_hies (r_dung ~ 4.9 applied once) as
        the lowest dung case. At rc67 the survey became the reference and that scenario
        was removed. What is left to hold is the survey's own spread: the 2018-19 rate
        held is the lowest dung case (23.8524), the 2024-25 round as measured sits just
        above the reference (24.3339), and configuration L is the highest. None of it
        may touch the engine (asserted again for luck)."""
        before = combustion.dung_air_dry_kg(self.data)
        self.assertNotIn("dung_activity_hies", self.scen)
        ref = self.scen["reference"]["deterministic"]
        low = self.scen["dung_survey_rate_2018_19"]["deterministic"]
        high = self.scen["dung_all_diverted_household"]["deterministic"]
        as_measured = self.scen["dung_survey_round_2024_25_as_measured"]["deterministic"]
        self.assertAlmostEqual(low, 23.8524, places=4)
        self.assertAlmostEqual(as_measured, 24.3339, places=4)
        self.assertLess(low, ref)
        self.assertLess(ref, as_measured)
        for name, r in self.scen.items():
            if name.startswith("dung_"):
                self.assertLessEqual(low, r["deterministic"] + 1e-9, name)
                self.assertLessEqual(r["deterministic"], high + 1e-9, name)
        self.assertEqual(combustion.dung_air_dry_kg(self.data), before)

    def test_firewood_cases_bracket_the_anchor_change(self):
        self.assertLess(self.scen["firewood_none"]["deterministic"],
                        self.scen["firewood_faostat"]["deterministic"])
        self.assertLess(self.scen["firewood_faostat"]["deterministic"],
                        self.scen["reference"]["deterministic"])

    def test_declaration_and_sensitivity_rows_are_not_mc_sampled(self):
        """pm_condensables is a scope declaration; stove_mix_mtf and
        residue_factor_family are declared deterministic sensitivities on held
        evidence - none carries Monte Carlo percentiles."""
        for name in ("pm_condensables", "stove_mix_mtf", "residue_factor_family"):
            r = self.scen[name]
            self.assertEqual(r["P50"], "")
            self.assertNotEqual(r["note"], "")
        self.assertLess(self.scen["stove_mix_mtf"]["deterministic"],
                        self.scen["pm_condensables"]["deterministic"])
        self.assertLess(self.scen["residue_factor_family"]["deterministic"],
                        self.scen["pm_condensables"]["deterministic"])

    def test_every_row_carries_the_interpretation(self):
        for r in self.scen.values():
            self.assertEqual(r["interpretation"], unc.INTERPRETATION)

    def test_the_seed_is_private(self):
        """The national MC's published percentiles ride seed 42; this module must
        never touch that stream."""
        self.assertNotEqual(unc.SCENARIO_SEED, 42)
        self.assertEqual(unc.SCENARIO_SEED, 1404)


class TestPmRatio(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = ResidentialData()
        cls.ratio = unc.pm_ratio_distribution(cls.data, n_iter=4000)

    def test_the_deterministic_ratio_is_inside_its_own_interval(self):
        r = self.ratio
        self.assertLess(r["P2.5"], r["deterministic_ratio"])
        self.assertLess(r["deterministic_ratio"], r["P97.5"])

    def test_the_headline_survives_the_lower_bound(self):
        """The paper's claim is that household solid fuel dwarfs road transport's
        primary particulate. That claim must hold at the 2.5th percentile, or the
        sampled interval has falsified the headline rather than refined it."""
        self.assertGreater(self.ratio["P2.5"], 5.0)

    def test_it_is_reproducible(self):
        again = unc.pm_ratio_distribution(self.data, n_iter=4000)
        self.assertEqual(self.ratio["P50"], again["P50"])

    def test_the_note_states_the_matched_basis(self):
        self.assertIn("wear PM excluded", self.ratio["note"].replace(
            "non-exhaust wear PM excluded", "wear PM excluded"))


class TestInputsRegister(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = ResidentialData()
        cls.rows = unc.inputs_register(cls.data)
        cls.by_var = {r["variable"]: r for r in cls.rows}

    def test_every_row_is_classed(self):
        for r in self.rows:
            self.assertIn(r["uncertainty_class"], ("parametric", "structural"),
                          r["variable"])

    def test_structural_rows_point_at_scenarios_or_declare_absence(self):
        for r in self.rows:
            if r["uncertainty_class"] == "structural":
                self.assertTrue("scenario" in r["note"] or "not a scenario" in r["note"],
                                r["variable"])
                self.assertEqual(r["distribution"], "not sampled", r["variable"])

    def test_the_dung_chain_shares_one_correlation_group(self):
        chain = [r for r in self.rows
                 if r["correlation_group"] == "1a4b_dung_chain"]
        self.assertGreaterEqual(len(chain), 3)

    def test_the_dung_row_is_the_survey_series_and_names_the_ledger_chain(self):
        """Through rc66 the dung activity row was "Diverted dung nitrogen" at 50 percent
        and its note recorded r_dung as published, never applied. At rc67 the survey
        took control of the residential quantity, so the row is the survey series at its
        own 35 percent, and the ledger chain's 50 is named as applying to configuration
        L only. The old row must not come back beside it."""
        self.assertNotIn("Diverted dung nitrogen", self.by_var)
        row = self.by_var["Household dung cake (survey series)"]
        self.assertEqual(row["uncertainty_class"], "parametric")
        self.assertEqual(row["correlation_group"], "1a4b_dung_chain")
        self.assertEqual(row["uncert_pct_95"],
                         self.data.p("activity_uncert_dung_survey"))
        self.assertEqual(self.data.p("activity_uncert_dung_survey"), 35)
        self.assertEqual(self.data.p("activity_uncert_dung"), 50)
        self.assertAlmostEqual(row["central_value"],
                               combustion.dung_air_dry_kg(self.data) / 1e9, places=9)
        self.assertIn("the reference since rc67", row["note"])
        self.assertIn("Configuration L", row["note"])

    def test_the_activity_source_is_the_household_survey(self):
        """The structural choice flipped at rc67: the source is the household survey and
        the scenario it points at is configuration L. The survey series' construction is
        a structural row of its own, with the two rounds as its scenarios."""
        source = self.by_var["Dung activity source"]
        self.assertEqual(source["central_value"], "household survey")
        self.assertIn("dung_all_diverted_household", source["note"])
        self.assertIn("Dung mass basis (configuration L)", self.by_var)
        series = self.by_var["Dung survey series construction"]
        self.assertIn("dung_survey_rate_2018_19", series["note"])
        self.assertIn("dung_survey_round_2024_25_as_measured", series["note"])

    def test_every_named_scenario_exists(self):
        """A structural row that points at a scenario the scenarios table no longer
        carries is how dung_activity_hies would have survived its own removal."""
        import re
        names = {r["structural_scenario"]
                 for r in unc.structural_scenarios(self.data, n_iter=200)}
        for r in self.rows:
            if r["uncertainty_class"] != "structural":
                continue
            for name in re.findall(r"\b(?:dung|firewood)_[a-z0-9_]+", r["note"]):
                self.assertIn(name, names, r["variable"])


if __name__ == "__main__":
    unittest.main()
