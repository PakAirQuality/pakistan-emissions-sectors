"""The railway uncertainty system: decomposition honest, scenarios named, question retired.

Run:  python3 -m unittest discover tests -p "test_railways_uncertainty.py"
"""
import unittest

from pkinv.sectors.railways import reconcile, uncertainty
from pkinv.sectors.railways.data import RailwaysData


class TestApproach1(unittest.TestCase):
    def test_grouped_is_the_conservative_headline(self):
        a1 = uncertainty.approach1(RailwaysData())
        self.assertGreaterEqual(a1["approach1_pct_grouped"],
                                a1["approach1_pct_independent"])
        # N2O's 150 percent factor dominates: the sector interval must sit well above the
        # diesel-CO2 5.4 and well below the N2O 150.
        self.assertTrue(10 < a1["approach1_pct_grouped"] < 30,
                        a1["approach1_pct_grouped"])


class TestInputsRegister(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = uncertainty.inputs_register(RailwaysData())

    def test_every_parametric_row_is_sourced(self):
        for r in self.rows:
            if r["uncertainty_class"] == "parametric":
                self.assertTrue(str(r["source"]).strip(), r["variable"])

    def test_structural_rows_are_never_sampled(self):
        for r in self.rows:
            if r["uncertainty_class"] == "structural":
                self.assertEqual(r["distribution"], "not sampled", r["variable"])

    def test_the_settled_question_is_recorded_as_retired(self):
        """The summary-vs-detail case must appear as RETIRED, not vanish: absence would
        read as an omission, and resurrection would reopen a question the source closed."""
        retired = [r for r in self.rows if r["central_value"] == "RETIRED"]
        self.assertEqual(len(retired), 1)
        self.assertIn("restatement", retired[0]["source"])


class TestScenarios(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = RailwaysData()
        cls.scen = {r["structural_scenario"]: r
                    for r in uncertainty.structural_scenarios(cls.data, n_iter=2000)}

    def test_reference_is_the_published_total(self):
        import csv
        import os
        path = os.path.join(os.path.dirname(__file__), "..", "outputs",
                            "railways_totals_2024.csv")
        with open(path, newline="", encoding="utf-8") as f:
            total = next(float(r["co2e_Mt_AR5"]) for r in csv.DictReader(f)
                         if r["category"] == "Module total (both categories)")
        self.assertAlmostEqual(self.scen["reference"]["deterministic"], total, places=4)

    def test_road_factor_case_matches_the_published_diagnostic(self):
        import csv
        import os
        path = os.path.join(os.path.dirname(__file__), "..", "outputs",
                            "railways_totals_2024.csv")
        with open(path, newline="", encoding="utf-8") as f:
            diag = next(float(r["co2e_Mt_AR5"]) for r in csv.DictReader(f)
                        if r["category"].startswith("Diagnostic"))
        self.assertAlmostEqual(self.scen["road_n2o_factor"]["deterministic"], diag,
                               places=4)

    def test_ie_summary_restates_the_prerc11_booking(self):
        """The rc11 flip of the sixth review's recode: the ENGINE now books the
        measured non-traction fuel at its own category (the reference), and the
        scenario row states the pre-rc11 summary booking. Deterministic equals the
        reference; moved_Mt is the measured carve-out the engine books at the
        non-traction category; national delta is exactly zero either way."""
        from pkinv.sectors.railways import engine
        moved = sum(c["co2e_Mt_AR5"] for c in engine.build_components(self.data)
                    if c["category"] == engine.traction.NON_TRACTION_CATEGORY)
        row = self.scen["ie_summary"]
        self.assertEqual(row["deterministic"],
                         self.scen["reference"]["deterministic"])
        self.assertAlmostEqual(float(row["moved_Mt"]), moved, places=5)
        self.assertEqual(float(row["national_delta_Mt"]), 0.0)
        self.assertIn("PRE-rc11", row["note"])
        self.assertIn("1.A.3.c", row["receiving_category"])

    def test_the_reference_split_is_the_detail_tables(self):
        """The re-base itself: 1.A.3.c holds the locomotive shares and the
        non-traction category holds the measured remainder, per fuel, exactly."""
        from pkinv.sectors.railways import engine, traction
        share = reconcile.non_traction_share(self.data)
        fo = reconcile.detail_for(self.data.year, "Residual Fuel Oil")
        fo_frac = fo["locomotive"] / (fo["locomotive"] + fo["other_than_locomotive"])
        comps = engine.build_components(self.data)
        diesel_all = sum(c["co2e_Mt_AR5"] for c in comps
                         if "diesel" in c["subitem"].lower())
        diesel_nt = sum(c["co2e_Mt_AR5"] for c in comps
                        if c["category"] == traction.NON_TRACTION_CATEGORY
                        and "diesel" in c["subitem"].lower())
        self.assertAlmostEqual(diesel_nt, diesel_all * share, places=9)
        fo_all = sum(c["co2e_Mt_AR5"] for c in comps
                     if "furnace" in c["subitem"].lower())
        fo_nt = sum(c["co2e_Mt_AR5"] for c in comps
                    if c["category"] == traction.NON_TRACTION_CATEGORY
                    and "furnace" in c["subitem"].lower())
        self.assertAlmostEqual(fo_nt, fo_all * (1 - fo_frac), places=9)

    def test_tier2_split_is_invariant_by_construction(self):
        self.assertEqual(self.scen["tier2_service_split"]["deterministic"],
                         self.scen["reference"]["deterministic"])
        self.assertIn("INVARIANT", self.scen["tier2_service_split"]["note"])

    def test_sulfur_cases_are_so2_scope_and_monotone(self):
        ladder = [r for name, r in self.scen.items() if name.startswith("sulfur_")]
        self.assertEqual(len(ladder), 4)
        for r in ladder:
            self.assertEqual(r["scope"], "air: SO2 kt")
            self.assertEqual(r["P50"], "")   # stoichiometric: the case IS the answer
        values = [r["deterministic"] for r in
                  sorted(ladder, key=lambda r: r["deterministic"])]
        self.assertLess(values[0], 0.01)
        self.assertGreater(values[-1], 2.0)

    def test_every_scenario_carries_the_interpretation_sentence(self):
        for r in self.scen.values():
            self.assertEqual(r["interpretation"], uncertainty.INTERPRETATION)


class TestSeedIsolation(unittest.TestCase):
    def test_the_private_seed_is_neither_national_nor_powers(self):
        self.assertNotIn(uncertainty.SCENARIO_SEED, (42, 4242))

    def test_shipped_components_carry_no_new_correlation_keys(self):
        """The grouping is computed inside this module. Stamping corr_group onto the
        shipped rows would reorder the national seed-42 gauss stream and silently move
        every published national percentile - core/montecarlo.py's own warning."""
        from pkinv.sectors.railways import engine
        for c in engine.build_components(RailwaysData()):
            self.assertNotIn("corr_group", c)


if __name__ == "__main__":
    unittest.main()
