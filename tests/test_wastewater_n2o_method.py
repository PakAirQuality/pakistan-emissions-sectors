"""Domestic wastewater nitrous oxide on the 2019 Refinement: the nitrogen account, its
sources, and the comparison with the method it replaced.

WHY. Through rc66 the estimate was the 2006 Guidelines' single equation, and the repository's
manifest called its only wastewater chapter "2019 Refinement" although it was the 2006 one.
At rc67 the Refinement's chapter was fetched and the method changed to it. A change of method
is five changes at once here (protein consumed, household products, the industrial factor on
sewers only, removal by treatment type, plant emissions) plus a different range for the
effluent factor, so these tests hold the account to the chapter's tables and to its own
arithmetic, and hold the alternative to reproducing what rc66 published.
"""
import collections
import csv
import importlib.util
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.sectors.waste import uncertainty, wastewater          # noqa: E402
from pkinv.sectors.waste.data import WasteData                   # noqa: E402

CHAPTER = os.path.join(ROOT, "data", "raw", "ipcc", "19R_V5_6_Ch06_Wastewater.pdf")
COMPARISON = os.path.join(ROOT, "outputs", "pakemis_wastewater_method_comparison.csv")
SCENARIOS = os.path.join(ROOT, "outputs", "waste_uncertainty_scenarios_2024.csv")
MANIFEST = os.path.join(ROOT, "data", "catalog", "manifests", "source_manifest.csv")


def _rows(path):
    with open(path, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(line for line in handle if not line.startswith("#")))


class TestTheNitrogenAccount(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = WasteData()
        cls.rows = wastewater.nitrogen_pathways(cls.data)

    def test_the_reference_is_the_2019_method(self):
        self.assertEqual(wastewater.n2o_method(self.data), "ipcc2019")
        self.assertEqual(wastewater.n2o_gg(self.data), wastewater.n2o_gg_2019(self.data))

    def test_the_alternative_reproduces_what_rc66_published(self):
        """11.447 Gg N2O, 3.034 Mt CO2e: the 2006 equation must still give the number every
        release through rc66 carried, or 'retained as the alternative' is not true."""
        gg = wastewater.n2o_gg(self.data, method="ipcc2006")
        self.assertAlmostEqual(gg, 11.447319030577404, places=9)
        self.assertAlmostEqual(gg * 265.0 / 1000.0, 3.0335, places=3)

    def test_an_unknown_method_is_refused(self):
        with self.assertRaises(ValueError):
            wastewater.n2o_gg(self.data, method="ipcc1996")

    def test_every_person_is_in_exactly_one_pathway(self):
        """The whole population stays in the estimate: no sewered-only restriction."""
        people = sum(r["people"] for r in self.rows)
        self.assertAlmostEqual(people, sum(wastewater.population(self.data).values()),
                               delta=people * 2e-3)   # JMP's one-decimal shares
        self.assertEqual({r["pathway"] for r in self.rows},
                         {p for p, *_rest in wastewater.NITROGEN_PATHWAYS})

    def test_nitrogen_is_conserved_on_every_row(self):
        for r in self.rows:
            self.assertAlmostEqual(r["removed_kg"] + r["effluent_kg"] + r["to_soil_kg"],
                                   r["nitrogen_kg"], delta=1e-6 * max(1.0, r["nitrogen_kg"]),
                                   msg="%s %s" % (r["setting"], r["pathway"]))
            self.assertGreaterEqual(r["effluent_kg"], 0.0)

    def test_the_industrial_factor_rides_the_sewered_population_only(self):
        per = collections.defaultdict(lambda: [0.0, 0.0])
        for r in self.rows:
            key = "sewer" if r["pathway"].startswith("sewer") else "other"
            per[key][0] += r["nitrogen_kg"]
            per[key][1] += r["people"]
        ratio = (per["sewer"][0] / per["sewer"][1]) / (per["other"][0] / per["other"][1])
        self.assertAlmostEqual(ratio, self.data.p("ww_f_ind_com"), places=9)

    def test_only_the_treated_sewer_share_emits_at_a_plant(self):
        plant = {r["pathway"] for r in self.rows if r["n2o_plant_Gg"] > 0}
        self.assertEqual(plant, {"sewer, treated"})
        treated = sum(r["people"] for r in self.rows if r["pathway"] == "sewer, treated")
        sewered = sum(r["people"] for r in self.rows if r["pathway"].startswith("sewer"))
        self.assertAlmostEqual(treated / sewered, self.data.p("ww_treated_share"), places=12)

    def test_the_2019_estimate_is_below_the_2006_one_and_says_why(self):
        new, old = wastewater.n2o_gg_2019(self.data), wastewater.n2o_gg_2006(self.data)
        self.assertLess(new, old)
        self.assertAlmostEqual(new, 9.7062, places=3)
        removed = sum(r["removed_kg"] for r in self.rows)
        self.assertGreater(removed, 0.0)

    def test_the_method_switch_is_a_parameter_and_scenarios_can_set_it(self):
        other = uncertainty._with_params(ww_n2o_method_2019=0)
        self.assertEqual(wastewater.n2o_method(other), "ipcc2006")
        self.assertAlmostEqual(wastewater.n2o_gg(other), wastewater.n2o_gg_2006(self.data),
                               places=9)


class TestTheFactorsAreTheChaptersOwn(unittest.TestCase):
    """Every value below was read from the held chapter. If a parameter moves, the table it
    cites must be the reason, and the source text must still name the table."""
    PRINTED = {
        "ww_ef_effluent": (0.005, (0.0005, 0.075), "Table 6.8A"),
        "ww_ef_plant_aerobic": (0.016, (0.00016, 0.045), "Table 6.8A"),
        "ww_ef_septic": (0.0, (0.0, 0.001), "Table 6.8A"),
        "ww_ef_septic_field": (0.0045, (0.0, 0.005), "Table 6.8A"),
        "ww_ef_effluent_nutrient": (0.019, (0.0041, 0.091), "Table 6.8A"),
        "ww_nrem_secondary": (0.40, (0.35, 0.55), "Table 6.10C"),
        "ww_nrem_septic": (0.15, (0.10, 0.25), "Table 6.10C"),
        "ww_nrem_septic_field": (0.68, (0.62, 0.73), "Table 6.10C"),
        "ww_nrem_latrine": (0.12, (0.07, 0.21), "Table 6.10C"),
        "ww_f_pc": (0.96, None, "Table 6.10A"),
        "ww_n_hh": (1.1, (1.07, 1.17), "Table 6.10A"),
        "ww_f_npr": (0.16, (0.15, 0.17), "Table 6.11"),
        "ww_f_non_con": (1.1, (1.0, 1.4), "Table 6.11"),
        "ww_f_ind_com": (1.25, (1.0, 1.5), "Table 6.11"),
    }

    @classmethod
    def setUpClass(cls):
        cls.data = WasteData()

    def test_values_ranges_and_citations(self):
        for name, (value, bounds, table) in self.PRINTED.items():
            self.assertAlmostEqual(self.data.p(name), value, places=12, msg=name)
            if bounds is not None:
                self.assertEqual(self.data.param_bounds[name], bounds, name)
            source = self.data.param_source[name]
            self.assertIn("2019 Refinement", source, name)
            self.assertIn(table, source, name)

    def test_the_chapter_is_held_and_its_retrieval_is_logged(self):
        self.assertTrue(os.path.exists(CHAPTER))
        log = _rows(os.path.join(os.path.dirname(CHAPTER), "RETRIEVALS.csv"))
        row = next(r for r in log if r["file"] == os.path.basename(CHAPTER))
        self.assertEqual(int(row["bytes"]), os.path.getsize(CHAPTER))
        self.assertIn("ipcc-nggip.iges.or.jp/public/2019rf", row["url"])

    def test_the_bounded_draws_are_the_refinements_ranges(self):
        for name in ("ww_ef_effluent", "ww_ef_plant_aerobic", "ww_nrem_secondary",
                     "ww_nrem_septic", "ww_nrem_latrine", "ww_n_hh"):
            self.assertIn(name, uncertainty.BOUNDED_DRAW)
            low, high = self.data.param_bounds[name]
            self.assertLess(low, self.data.p(name))
            self.assertLess(self.data.p(name), high)

    def test_the_effluent_width_is_computed_from_the_new_range(self):
        """About 267 per cent on 0.0005-0.075; it was about 401 on the 2006 range. The
        figure is computed, and this pins which range it was computed from."""
        width = uncertainty.equivalent_bounded_uncert_pct(self.data, "ww_ef_effluent")
        self.assertAlmostEqual(width, 266.8, delta=0.5)


class TestThePathwaySharesAreEachYearsOwn(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = WasteData()

    def test_each_fiscal_year_reads_its_own_jmp_year(self):
        for year in range(2016, 2025):
            self.assertEqual(wastewater.jmp_year(self.data, year), year - 1)
            for setting in wastewater.SETTINGS:
                self.assertIn((year - 1, setting), self.data.sanitation)
        self.assertEqual(wastewater.jmp_year(self.data), 2023)

    def test_methane_and_nitrous_oxide_share_one_pathway_table(self):
        """Both gases must put the same number of people on a sewer in the same year."""
        for year in (2016, 2020, 2024):
            pop = wastewater.population(self.data, year)
            sewered = sum(r["people"] for r in wastewater.nitrogen_pathways(self.data, year)
                          if r["pathway"].startswith("sewer"))
            expected = sum(pop[s] * wastewater._shares(self.data, s, year)["sewer"]
                           for s in wastewater.SETTINGS)
            self.assertAlmostEqual(sewered, expected, delta=1e-6 * expected)

    def test_the_ingest_re_derives_the_table_from_the_held_workbook(self):
        run = subprocess.run(
            [sys.executable, os.path.join(ROOT, "scripts", "ingest_jmp_sanitation.py"),
             "--check"], cwd=ROOT, capture_output=True, text=True,
            env=dict(os.environ, PYTHONPATH=os.path.join(ROOT, "src"), PKINV_ROOT=ROOT))
        self.assertEqual(run.returncode, 0, run.stdout[-600:] + run.stderr[-600:])


class TestTheDeclaredAssumptionsArePriced(unittest.TestCase):
    """Treated share, the fate of decentralised effluent, and the class of receiving water
    are declared, not measured. Each has a scenario, and each scenario moves the right way."""

    @classmethod
    def setUpClass(cls):
        cls.scen = {r["structural_scenario"]: float(r["deterministic"])
                    for r in _rows(SCENARIOS)}

    def test_the_scenarios_exist(self):
        for name in ("n2o_method_ipcc2006", "decentralised_effluent_to_soil",
                     "effluent_nutrient_impacted", "septic_with_dispersal_field",
                     "treated_share_high", "effluent_ef_low", "effluent_ef_high"):
            self.assertIn(name, self.scen)

    def test_they_bracket_the_reference_in_the_expected_direction(self):
        ref = self.scen["reference"]
        self.assertLess(self.scen["decentralised_effluent_to_soil"], ref)
        # a dispersal field removes more nitrogen before discharge (0.68 against 0.15) but
        # emits at the field (0.0045 on ALL septic nitrogen); the second term is larger,
        # so this reading is ABOVE the reference
        self.assertGreater(self.scen["septic_with_dispersal_field"], ref)
        self.assertLess(self.scen["effluent_ef_low"], ref)
        self.assertGreater(self.scen["effluent_nutrient_impacted"], ref)
        self.assertGreater(self.scen["n2o_method_ipcc2006"], ref)
        self.assertGreater(self.scen["effluent_ef_high"],
                           self.scen["effluent_nutrient_impacted"])

    def test_the_2006_scenario_is_the_2006_delta(self):
        data = WasteData()
        delta = (wastewater.n2o_gg_2006(data) - wastewater.n2o_gg_2019(data)) * 265.0 / 1000.0
        self.assertAlmostEqual(self.scen["n2o_method_ipcc2006"] - self.scen["reference"],
                               delta, places=3)


class TestTheMethodComparison(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = _rows(COMPARISON)
        cls.by = {(r["scope"], r["period_id"], r["method"]): r for r in cls.rows}

    def test_both_methods_for_all_nine_years(self):
        gas = [r for r in self.rows if r["scope"] == "wastewater_n2o"]
        self.assertEqual(len(gas), 18)
        self.assertEqual(len({r["period_id"] for r in gas}), 9)
        for r in gas:
            self.assertEqual(r["is_reference"], "yes" if r["method"] == "ipcc2019" else "no")

    def test_the_gas_rows_are_the_engines(self):
        data = WasteData()
        for year in range(2016, 2025):
            period = "FY%d-%02d" % (year - 1, year % 100)
            for method in ("ipcc2019", "ipcc2006"):
                self.assertAlmostEqual(
                    float(self.by[("wastewater_n2o", period, method)]["deterministic"]),
                    wastewater.n2o_gg(data, year, method=method), places=4)

    def test_the_national_difference_is_the_wastewater_difference(self):
        """Paired on the same draws, so the two national rows differ by exactly what the
        two wastewater rows differ by."""
        def det(scope, method):
            return float(self.by[(scope, "FY2023-24", method)]["deterministic"])
        self.assertAlmostEqual(
            det("national_total", "ipcc2006") - det("national_total", "ipcc2019"),
            det("wastewater_category", "ipcc2006") - det("wastewater_category", "ipcc2019"),
            places=4)

    def test_the_upper_tail_is_shorter_under_the_reference(self):
        ref = self.by[("national_total", "FY2023-24", "ipcc2019")]
        alt = self.by[("national_total", "FY2023-24", "ipcc2006")]
        self.assertLess(float(ref["p97_5"]), float(alt["p97_5"]))
        self.assertLess(float(ref["p2_5"]), float(ref["deterministic"]))
        self.assertGreater(float(ref["p97_5"]), float(ref["deterministic"]))
        for method in ("ipcc2019", "ipcc2006"):
            share = float(self.by[("wastewater_category", "FY2023-24", method)][
                "upper_tail_excess_share"])
            self.assertGreater(share, 0.0)
            self.assertLess(share, 1.0)

    def test_the_reference_row_states_the_reason_for_the_selection(self):
        row = self.by[("wastewater_n2o", "FY2023-24", "ipcc2019")]
        self.assertIn("does not account for the removal", row["note"])


class TestTheManifestNamesTheRightEdition(unittest.TestCase):
    """Through rc66 every file under data/raw/ipcc was stamped '2019 Refinement'."""

    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location(
            "build_raw_manifest", os.path.join(ROOT, "scripts", "build_raw_manifest.py"))
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)
        cls.rows = [r for r in _rows(MANIFEST) if r["source_id"].startswith("ipcc/")]

    def test_the_edition_is_read_from_the_file_name(self):
        edition = self.module.ipcc_edition
        self.assertEqual(edition("ipcc2006_V5_6_Ch6_Wastewater.pdf")[0],
                         "2006 IPCC Guidelines")
        self.assertIn("/2006gl/pdf/5_Volume5/", edition("ipcc2006_V5_6_Ch6_Wastewater.pdf")[1])
        self.assertEqual(edition("19R_V5_6_Ch06_Wastewater.pdf")[0], "2019 Refinement")
        self.assertEqual(edition("ipcc2019_waste_model.xlsx")[0], "2019 Refinement")
        self.assertIsNone(edition("chapter6.pdf"))

    def test_no_2006_chapter_is_called_the_refinement(self):
        self.assertGreaterEqual(len(self.rows), 12)
        for r in self.rows:
            name = r["original_filename"]
            if name.startswith("ipcc2006_"):
                self.assertEqual(r["coverage_start"], "2006 IPCC Guidelines", name)
                self.assertIn("/2006gl/", r["source_url"], name)
            else:
                self.assertEqual(r["coverage_start"], "2019 Refinement", name)
                self.assertIn("/2019rf/", r["source_url"], name)

    def test_both_wastewater_chapters_are_listed(self):
        names = {r["original_filename"] for r in self.rows}
        self.assertIn("ipcc2006_V5_6_Ch6_Wastewater.pdf", names)
        self.assertIn("19R_V5_6_Ch06_Wastewater.pdf", names)


if __name__ == "__main__":
    unittest.main()
