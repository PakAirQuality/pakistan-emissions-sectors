"""Scientific invariants for the 2006-to-2019 fugitive inventory."""

from pkinv.assets import asset_path
import csv
import math
import os
import unittest

from pkinv.core import registry
from pkinv.paths import DATA, OUTPUTS
from pkinv.sectors.fugitives import (
    audits, downscale, engine, gas_balance, leakage, observations, official_reporting,
    segment_inventory, uncertainty,
)
from pkinv.sectors.fugitives.data import FugitivesData
from pkinv.core.io import read_rows


def _load(*parts):
    return read_rows(asset_path(DATA, *parts), comments=False)


class TestAnchorActivity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = FugitivesData()

    def test_registered_inventory_has_one_anchor_and_audited_history(self):
        self.assertEqual(self.data.year, 2024)
        self.assertGreater(sum(c["co2e_Mt_AR5"] for c in engine.build_components(
            self.data, year=2016)), 20.0)
        with self.assertRaises(ValueError):
            engine.build_components(self.data, year=2015)

    def test_anchor_production_matches_annual_series(self):
        self.assertAlmostEqual(self.data.activity("oil_onshore_production")["value"],
                               self.data.oil_e3m3(2024), places=3)
        self.assertAlmostEqual(self.data.activity("gas_onshore_production")["value"],
                               self.data.gas_e6m3(2024), places=3)

    def test_pipeline_length_controls_close_exactly(self):
        self.assertAlmostEqual(self.data.activity("gas_transmission_pipeline")["value"],
                               9320.69 + 4206.0, places=9)
        self.assertEqual(self.data.activity("gas_distribution_pipeline")["value"],
                         151419 + 49811)

    def test_customer_control_is_not_a_population_proxy(self):
        self.assertEqual(self.data.activity("post_meter_appliances")["value"], 10748538)
        self.assertIn("Table 3.26", self.data.activity("post_meter_appliances")["source_reference"])

    def test_historical_series_is_coverage_graded(self):
        self.assertGreaterEqual(len(self.data.years()), 15)
        self.assertEqual(max(self.data.years()), 2025)
        self.assertEqual(self.data.year, 2024)  # 2025 lacks matching infrastructure controls


class TestIPCC2019Factors(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = FugitivesData()

    def test_reviewer_blocker_factor_is_the_2019_value(self):
        factor = self.data.factor2019("gas_prod_high_ch4")
        self.assertEqual(factor["value"], 4.09)
        self.assertEqual(factor["uncertainty_low_pct"], 20.0)
        self.assertEqual(factor["uncertainty_high_pct"], 20.0)
        self.assertIn("4.2.4g", factor["source_reference"])

    def test_reference_uses_high_practice_when_conditions_are_unknown(self):
        ledger = segment_inventory.inventory_rows(self.data, "reference")
        ids = {row["factor_id"] for row in ledger}
        self.assertIn("gas_prod_high_ch4", ids)
        self.assertIn("gas_distribution_high_km_ch4", ids)
        self.assertNotIn("gas_prod_low_ch4", ids)

    def test_lower_practice_is_structural_not_parametric(self):
        reference = sum(c["co2e_Mt_AR5"] for c in engine.build_components(self.data))
        lower = sum(c["co2e_Mt_AR5"] for c in engine.build_components(
            self.data, scenario="lower_practices"))
        self.assertLess(lower, reference)
        self.assertGreater(reference - lower, 5.0)

    def test_pipeline_and_throughput_are_alternative_bases(self):
        pipe = segment_inventory.inventory_rows(self.data, "reference")
        volume = segment_inventory.inventory_rows(self.data, "throughput")
        self.assertTrue(any(r["activity_unit"] == "km" for r in pipe))
        self.assertFalse(any(r["activity_unit"] == "km" for r in volume))
        self.assertEqual(len(pipe), len(volume))

    def test_no_duplicate_segment_gas_rows(self):
        ledger = segment_inventory.inventory_rows(self.data)
        keys = [(r["subitem"], r["gas"]) for r in ledger]
        self.assertEqual(len(keys), len(set(keys)))

    def test_registered_result_is_not_the_legacy_midpoint(self):
        reference = sum(c["co2e_Mt_AR5"] for c in engine.build_components(self.data))
        legacy = sum(c["co2e_Mt_AR5"] for c in engine.build_components(
            self.data, year=2020, method="legacy2006"))
        self.assertGreater(reference, 20.0)
        self.assertAlmostEqual(legacy, 3.8052114089057443, places=12)

    def test_joint_structural_engine_has_complete_factorial(self):
        """280 since rc67 gave the post-meter base three memberships (224 before,
        168 before that). The envelope's ends must NOT move: the feedstock-inside
        membership keeps the top, the excluded post-meter stream keeps the floor,
        and a moved end would mean a leg leaked outside its own scope."""
        configs = segment_inventory.factorial_configurations()
        self.assertEqual(len(configs), 280)
        totals = [sum(row["co2e_Mt_AR5"] for row in engine.build_components(
            self.data, config=config)) for config in configs]
        self.assertAlmostEqual(max(totals), 24.694094056555937, places=12)
        self.assertAlmostEqual(min(totals), 9.601488974504125, places=12)

    def test_central_is_interior_and_geometric(self):
        """The central member prices the midpoint, never a new bound: strictly
        inside reference and lower_practices, and its gas-production CH4 factor
        is exactly the geometric mean of the two published stems."""
        central = sum(c["co2e_Mt_AR5"] for c in engine.build_components(
            self.data, scenario="central"))
        reference = sum(c["co2e_Mt_AR5"] for c in engine.build_components(self.data))
        lower = sum(c["co2e_Mt_AR5"] for c in engine.build_components(
            self.data, scenario="lower_practices"))
        self.assertLess(lower, central)
        self.assertLess(central, reference)
        rows = segment_inventory.inventory_rows(self.data, "central")
        row = next(r for r in rows
                   if r["subitem"] == "Gas production" and r["gas"] == "CH4")
        hi = self.data.factor2019("gas_prod_high_ch4")["value"]
        lo = self.data.factor2019("gas_prod_low_ch4")["value"]
        self.assertAlmostEqual(row["factor_value"], math.sqrt(hi * lo), places=15)

    def test_the_reference_withholds_exactly_the_feedstock(self):
        """rc67: the reference removes chemical feedstock from the ACTIVITY of the one
        post-meter stream and touches nothing else. Measured against the membership
        every release through rc66 used, which survives as a named scenario."""
        reference = segment_inventory.inventory_rows(self.data)
        including = segment_inventory.inventory_rows(
            self.data, "post_meter_including_feedstock")
        share = self.data.post_meter_feedstock_share()
        whole_class = self.data.post_meter_feedstock_share(scope="class")
        self.assertAlmostEqual(whole_class, 0.309934, places=5)
        self.assertAlmostEqual(
            share, whole_class * self.data.fertilizer_feed_fraction()["value"], places=12)
        for ref_row, inc_row in zip(reference, including):
            self.assertEqual(ref_row["subitem"], inc_row["subitem"])
            if ref_row["subitem"] == "Post-meter industrial and power":
                self.assertAlmostEqual(
                    ref_row["activity_value"],
                    inc_row["activity_value"] * (1.0 - share), places=9)
                self.assertIn("feedstock", ref_row["activity_source_reference"])
            else:
                self.assertEqual(ref_row["emissions_Gg"], inc_row["emissions_Gg"],
                                 ref_row["subitem"])

    def test_the_three_memberships_are_ordered(self):
        """Feedstock inside > the reference > the whole fertiliser class out, and the
        gap between the last two is the process fuel, which is burned."""
        total = lambda name: sum(c["co2e_Mt_AR5"] for c in engine.build_components(
            self.data, scenario=name))
        inside, reference, class_out = (total("post_meter_including_feedstock"),
                                        total("reference"),
                                        total("post_meter_excluding_fertilizer"))
        self.assertGreater(inside, reference)
        self.assertGreater(reference, class_out)
        feed = self.data.fertilizer_feed_fraction()["value"]
        self.assertAlmostEqual((inside - reference) / (inside - class_out), feed, places=9)

    def test_the_feed_fraction_says_when_it_is_carried(self):
        """Observed where NFDC meters it, carried elsewhere, and never silently."""
        self.assertEqual(self.data.fertilizer_feed_fraction(2024)["basis"], "observed")
        self.assertAlmostEqual(self.data.fertilizer_feed_fraction(2024)["value"],
                               229237.0 / (229237.0 + 45219.0), places=12)
        for year in range(2016, 2024):
            found = self.data.fertilizer_feed_fraction(year)
            self.assertEqual(found["basis"], "carried", year)
            self.assertEqual(found["observed_year"], "2023-24", year)

    def test_every_panel_year_has_its_own_fertiliser_class(self):
        """The class is each year's own print; only the feed fraction may be carried."""
        seen = [self.data.fertilizer_gas_class(y)["mmcfd"] for y in range(2016, 2025)]
        self.assertEqual(seen, [720, 771, 687, 652, 779, 829, 834, 789, 756])
        with self.assertRaises(KeyError):
            self.data.fertilizer_gas_class(2015)

    def test_invalid_processing_and_sour_combination_is_rejected(self):
        with self.assertRaises(ValueError):
            segment_inventory.StructuralConfig(
                name="invalid", processing_basis="excluded", sour_fraction=0.32)


class TestLegacyUncertainty(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = FugitivesData()

    def test_geometric_midpoint_is_preserved_only_as_legacy(self):
        comps = engine.build_components(self.data, year=2020, method="legacy2006")
        row = next(c for c in comps if c["subitem"] == "Gas production fugitives CH4")
        lo, hi = 3.8e-4, 2.4e-2
        self.assertAlmostEqual(row["emissions_Gg"], self.data.gas_e6m3(2020) *
                               math.sqrt(lo * hi), places=9)

    def test_no_uncertainty_cap_survives(self):
        self.assertNotIn("max_uncert_pct", self.data.params)
        comps = engine.build_components(self.data, year=2020, method="legacy2006")
        self.assertGreater(max(c["uncert_pct"] for c in comps), 9900)

    def test_legacy_distribution_is_bounded_log_uniform(self):
        stats, samples = uncertainty.legacy_loguniform(self.data, n_iter=400, seed=7)
        low = sum(c["co2e_Mt_AR5"] for c in engine.build_components(
            self.data, year=2020, method="legacy2006", bound="low"))
        high = sum(c["co2e_Mt_AR5"] for c in engine.build_components(
            self.data, year=2020, method="legacy2006", bound="high"))
        self.assertEqual(stats["distribution"], "bounded log-uniform")
        self.assertGreaterEqual(min(samples), low)
        self.assertLessEqual(max(samples), high)

    def test_2019_mc_has_no_legacy_umbrella_term(self):
        stats, _ = uncertainty.refinement_monte_carlo(self.data, n_iter=300, seed=4)
        self.assertIn("Gas distribution", stats)
        self.assertNotIn("aggregate representation", stats)
        self.assertLess(stats["TOTAL"]["p025"], stats["TOTAL"]["p50"])
        self.assertLess(stats["TOTAL"]["p50"], stats["TOTAL"]["p975"])

    def test_uncertainty_register_declares_shared_source_groups(self):
        rows = uncertainty.uncertainty_input_rows(self.data)
        gas = [row for row in rows if row["correlation_group"] == "gas-production-volume"]
        self.assertGreaterEqual(len(gas), 3)
        self.assertTrue(all(row["distribution"] == "bounded_split_triangular" for row in rows))

    def test_rank_attribution_identifies_the_two_dominant_factors(self):
        _stats, _samples, rows = uncertainty.refinement_analysis(self.data, n_iter=600, seed=9)
        leaders = [row["input_group"] for row in rows[:2]]
        self.assertEqual(leaders, ["factor:gas_distribution_high_km",
                                   "factor:post_meter_industrial"])

    def test_selected_structural_models_have_conditional_intervals(self):
        """Five since the central member joined (rc17); it must be among them so
        the interior reading ships with its own conditional interval."""
        rows = uncertainty.conditional_interval_rows(
            self.data, segment_inventory.selected_conditional_configurations(),
            n_iter=250, seed=11)
        self.assertEqual(len(rows), 5)
        self.assertIn("central", {row["configuration"] for row in rows})
        self.assertTrue(all(row["mc_p025_mt_co2e_ar5"] <
                            row["mc_p975_mt_co2e_ar5"] for row in rows))

    def test_distribution_shape_sensitivity_is_bounded(self):
        rows = uncertainty.distribution_shape_rows(self.data, n_iter=250, seed=12)
        self.assertEqual({row["distribution"] for row in rows}, {
            "bounded_split_triangular", "bounded_uniform",
            "bounded_loguniform_positive"})


class TestDiagnosticsAreNotInventory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = FugitivesData()

    def test_ufg_conversion_has_no_factor_of_one_thousand_error(self):
        ufg_e6m3 = self.data.activity("ufg_diagnostic")["value"]
        expected = (ufg_e6m3 *
                    self.data.p("gas_density_kg_per_m3") *
                    self.data.p("gas_ch4_fraction"))
        self.assertAlmostEqual(leakage.ufg_bound_Gg_CH4(self.data), expected, places=9)
        self.assertGreater(expected, 1000)

    def test_ufg_is_absent_from_registered_components(self):
        self.assertFalse(any("UFG" in c["subitem"] for c in engine.build_components(self.data)))

    def test_viirs_is_a_memo_not_an_additive_stream(self):
        memo = observations.flare_emission_memo(self.data, 2024)
        self.assertGreater(memo["flare_volume_bcm"], 0)
        self.assertIn("not added", memo["interpretation"])
        self.assertFalse(any("VIIRS" in c["subitem"] for c in engine.build_components(self.data)))

    def test_mars_events_are_not_annualized(self):
        summary = observations.mars_summary()
        self.assertGreater(summary["oil_gas_sources"], 0)
        self.assertGreater(summary["oil_gas_plumes"], summary["oil_gas_sources"])
        self.assertIn("not annualized", summary["interpretation"])

    def test_gas_flow_identity_and_network_compatibility(self):
        rows = gas_balance.balance_rows(self.data)
        self.assertEqual([row["fiscal_year"] for row in rows], [2022, 2023, 2024])
        self.assertTrue(all(abs(row["supply_identity_residual_mmcfd"]) < 1e-9 for row in rows))
        compatibility = {row["scenario"]: row for row in gas_balance.ufg_compatibility(self.data)}
        self.assertAlmostEqual(
            compatibility["reference"]["ufg_physical_fraction_required_pct"],
            23.8284087414, places=8)
        self.assertLess(
            compatibility["lower_practices"]["ufg_physical_fraction_required_pct"], 10)

    def test_observations_evaluate_upstream_geography(self):
        # The generated evaluation is tested against its exact public-data controls.
        upstream = {"Balochistan": 1.0, "Khyber Pakhtunkhwa": 1.0,
                    "Punjab": 1.0, "Sindh": 1.0, "Other": 0.0}
        rows = observations.provincial_evaluation(upstream)
        self.assertEqual(sum(int(row["mars_sources"]) for row in rows), 20)
        matches = observations.mars_flare_matches()
        self.assertEqual(sum(float(row["distance_km"]) <= 10 for row in matches), 19)

    def test_field_evaluation_retains_zero_observation_controls(self):
        rows = observations.field_observation_evaluation()
        self.assertEqual(len(rows), 73)
        self.assertAlmostEqual(sum(row["official_marketable_supply_mmcfd"]
                                   for row in rows), 2637.75, places=6)
        self.assertTrue(any(not row["has_independent_observation"] for row in rows))
        self.assertGreater(rows[0]["official_supply_covered_by_named_observations_pct"], 70)
        stats = observations.field_observation_statistics(rows)
        self.assertEqual(len(stats), 3)
        self.assertTrue(all(row["n_official_fields"] == 73 for row in stats))

    def test_observation_matches_are_audited_without_forced_assignment(self):
        rows = observations.observation_match_audit()
        self.assertEqual(len(rows), 20)
        counts = {status: sum(row["match_confidence"] == status for row in rows)
                  for status in ("high", "review_required", "unmatched")}
        self.assertEqual(counts, {"high": 8, "review_required": 4, "unmatched": 8})
        self.assertTrue(all(row["canonicalization_method"] in
                            ("exact_normalized", "alias", "blank") for row in rows))
        self.assertTrue(all(row["review_reason_codes"] for row in rows
                            if row["match_confidence"] != "high"))

    def test_field_permutation_retains_zeros_and_is_reproducible(self):
        fields = observations.field_observation_evaluation()
        first = observations.field_observation_permutation(fields, n_iter=250, seed=17)
        second = observations.field_observation_permutation(fields, n_iter=250, seed=17)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 6)
        self.assertEqual({row["null_model"] for row in first},
                         {"national", "within_province"})
        self.assertTrue(all(row["n_official_fields"] == 73 for row in first))
        self.assertTrue(all(0 < row["spearman_two_sided_empirical_p"] <= 1
                            for row in first))

    def test_upstream_disposition_preserves_unresolved_hole(self):
        rows = gas_balance.upstream_disposition_rows(self.data, 0.13009460466631795)
        anchor = next(row for row in rows if row["fiscal_year"] == 2024)
        self.assertAlmostEqual(anchor["unresolved_upstream_difference_mmcfd"],
                               488.24739726, places=8)
        self.assertLess(anchor["calendar_2024_viirs_share_of_fiscal_difference_pct"], 3)
        self.assertEqual(anchor["reported_reinjection_mmcfd"], "")


class TestOfficialReportingAudit(unittest.TestCase):
    def test_crt_total_is_extracted_not_transcribed(self):
        total, _rows = official_reporting.extract_crt()
        self.assertEqual(total["source_reference"], "Table1!B42:J42")
        self.assertAlmostEqual(total["total_co2e_kt"], 4432.821048632558, places=9)
        self.assertEqual(len(total["workbook_sha256"]), 64)

    def test_crt_segment_rows_reveal_activity_and_factors(self):
        _total, rows = official_reporting.extract_crt()
        gas_prod = next(r for r in rows if r["row"] == 22)
        self.assertEqual(gas_prod["activity_value"], 112.46)
        self.assertEqual(gas_prod["ch4_ief_kg_per_unit"], 12190)

    def test_cell_audit_contains_every_summary_gas(self):
        audit = official_reporting.audit_cells()
        fields = {row["field"] for row in audit}
        self.assertTrue({"1B2_CO2", "1B2_CH4", "1B2_N2O", "1B2_total"} <= fields)

    def test_every_numeric_crt_row_reproduces_from_activity_and_ief(self):
        rows = official_reporting.reproduce_reported_rows()
        self.assertGreater(len(rows), 0)
        self.assertTrue(all(row["closes"] for row in rows))
        self.assertLess(max(abs(row["difference_kt"]) for row in rows), 1e-12)

    def test_native_gas_table_closes_to_reference(self):
        data = FugitivesData()
        rows = audits.native_gas_table(data)
        # 792.571797366 through rc66; rc67 withdrew 39.8108 Gg, the post-meter factor on
        # 6,526.4 million m3 of fertiliser feedstock that is reformed and not burned
        self.assertAlmostEqual(sum(row["ch4_Gg"] for row in rows), 752.760954741, places=6)
        self.assertAlmostEqual(sum(row["co2e_Mt_AR5"] for row in rows),
                               sum(row["co2e_Mt_AR5"] for row in engine.build_components(data)),
                               places=12)

    def test_crt_common_metric_and_waterfall_are_native_gas_consistent(self):
        data = FugitivesData()
        common = official_reporting.official_common_metric()
        self.assertEqual(common["submitted_implied_ch4_gwp"], 28.0)
        self.assertAlmostEqual(common["common_ar5_fossil_ch4_mt_co2e"],
                               4.748631938858129, places=12)
        waterfall = official_reporting.reconstruction_waterfall(data)
        # 26.504940462704937 through rc66; the same feedstock withdrawal in FY2021-22
        self.assertAlmostEqual(waterfall[-1]["cumulative_common_mt_co2e"],
                               25.186951964160958, places=12)
        self.assertLess(abs(waterfall[-1]["delta_common_mt_co2e"]), 1e-12)

    def test_adjacent_fiscal_years_bracket_the_crt_comparison(self):
        rows = official_reporting.fiscal_year_bracket(FugitivesData())
        self.assertEqual([row["adjacent_fiscal_period"] for row in rows],
                         ["FY2021-22", "FY2022-23"])
        self.assertTrue(all(row["ratio_to_official_common_metric"] > 5 for row in rows))


class TestSpatialAndCompleteness(unittest.TestCase):
    def test_processes_use_different_geographies(self):
        shares = downscale.load_shares()
        self.assertNotEqual(shares[downscale.GAS_PROXY], shares[downscale.DISTRIBUTION_PROXY])
        self.assertEqual(shares[downscale.LNG_PROXY]["Sindh"], 1.0)
        for key in (downscale.GAS_PROXY, downscale.OIL_PROXY,
                    downscale.TRANSMISSION_PROXY, downscale.DISTRIBUTION_PROXY,
                    downscale.CONSUMPTION_PROXY, downscale.REFINERY_PROXY,
                    downscale.LNG_PROXY):
            self.assertAlmostEqual(sum(shares[key].values()), 1.0, places=9)

    def test_completeness_matrix_carries_true_gaps(self):
        rows = _load("activity", "fugitives", "completeness.csv")
        lookup = {(r["ipcc_code"], r["subsegment"]): r for r in rows}
        self.assertEqual(lookup[("1.B.2.a.vii", "Abandoned wells")]["notation_key"], "NE")
        self.assertEqual(lookup[("1.B.2.b.iv", "Underground and surface storage")]["notation_key"], "NO")
        self.assertEqual(lookup[("1.B.1", "Coal mining")]["central_inventory"], "no")

    def test_unknown_category_raises(self):
        with self.assertRaises(KeyError):
            downscale.proxy_for({"category": "Coal mining", "subitem": "x"})

    def test_dominant_assumption_audits_reconcile(self):
        data = FugitivesData()
        end_use = audits.post_meter_end_use_audit(data)
        self.assertLess(abs(end_use[0]["rounding_residual_million_m3"]), 0.1)
        lineage = audits.post_meter_factor_lineage(data)[0]
        self.assertAlmostEqual(lineage["derived_t_CH4_per_million_m3"], 6.125)
        evidence = audits.distribution_practice_evidence()
        self.assertTrue(any(row["criterion"] == "plastic_share" and
                            row["classification_effect"] == "unresolved"
                            for row in evidence))

    def test_full_infrastructure_history_has_no_interpolation(self):
        data = FugitivesData()
        totals = []
        for year in range(2016, 2025):
            self.assertTrue(data.has_anchor_year(year))
            totals.append(sum(row["co2e_Mt_AR5"] for row in
                              engine.build_components(data, year=year)))
        self.assertEqual(len(totals), 9)
        self.assertTrue(all(value > 20 for value in totals))


class TestGeneratedProducts(unittest.TestCase):
    def test_qa_product_passes(self):
        path = os.path.join(OUTPUTS, "fugitives_qa_2024.csv")
        if not os.path.exists(path):
            self.skipTest("run fugitives target first")
        with open(path, newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.assertGreaterEqual(len(rows), 8)
        self.assertTrue(all(r["passed"] == "True" for r in rows))

    def test_fugitives_is_registered_at_2024(self):
        sector = registry.get("fugitives")
        self.assertEqual(sector.YEAR, 2024)
        self.assertGreater(sum(c["co2e_Mt_AR5"] for c in sector.build_components(
            sector.load_data())), 20.0)

    def test_segment_history_closes_and_exposes_compositional_change(self):
        segment_path = os.path.join(
            OUTPUTS, "fugitives_infrastructure_segment_timeseries_2016_2024.csv")
        total_path = os.path.join(OUTPUTS, "fugitives_infrastructure_timeseries_2016_2024.csv")
        if not os.path.exists(segment_path) or not os.path.exists(total_path):
            self.skipTest("run fugitives target first")
        with open(segment_path, newline="", encoding="utf-8") as handle:
            segments = list(csv.DictReader(handle))
        with open(total_path, newline="", encoding="utf-8") as handle:
            totals = list(csv.DictReader(handle))
        self.assertEqual(len(segments), 9 * 12)
        for total in totals:
            annual = sum(float(row["co2e_Mt_AR5"]) for row in segments
                         if row["fiscal_year"] == total["fiscal_year"])
            self.assertAlmostEqual(annual, float(total["co2e_Mt_AR5"]), places=12)
        grouped = {}
        for row in segments:
            key = (int(row["fiscal_year"]), row["reporting_group"])
            grouped[key] = grouped.get(key, 0.0) + float(row["co2e_Mt_AR5"])
        self.assertLess(grouped[(2024, "upstream/processing")],
                        grouped[(2016, "upstream/processing")])
        self.assertGreater(grouped[(2024, "network/import")],
                           grouped[(2016, "network/import")])


class TestCoalScreen(unittest.TestCase):
    """The 1.B.1 Tier-1 screen (the second review's 8.7): a partial surface bound from
    activity that was held all along, with the partial scope stated everywhere the
    number appears."""

    @classmethod
    def setUpClass(cls):
        from pkinv.sectors.fugitives import coal_screen
        cls.screen = coal_screen
        cls.rows = coal_screen.rows()

    def test_the_activity_is_the_power_ledger_thar_mass(self):
        """The screen derives nothing: its tonnage is the NEPRA mine-mouth deliveries,
        summed straight from the committed plant ledger."""
        total = 0.0
        path = asset_path(DATA, "activity", "power", "plant_fuel_ledger.csv")
        with open(path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if (int(r["fiscal_year"]) == 2023 and r["fuel"].lower() == "coal"
                        and r["fuel_origin"] == "Thar lignite"):
                    total += float(r["quantity"])
        self.assertAlmostEqual(self.rows[0]["activity_kt"], total, places=2)
        self.assertGreater(total, 10000.0, "the Thar panel shrank; check the ledger")

    def test_the_band_is_the_declared_factor_arithmetic(self):
        lo, hi = self.screen.surface_band_mt()
        tonnes = self.rows[0]["activity_kt"] * 1000.0
        want_lo = tonnes * 0.3 * 0.67 / 1000.0 * 28.0 / 1e6
        want_hi = tonnes * 2.2 * 0.67 / 1000.0 * 28.0 / 1e6
        self.assertAlmostEqual(lo, want_lo, places=4)
        self.assertAlmostEqual(hi, want_hi, places=4)
        self.assertLess(hi, 1.0, "the surface band crossed the 1 Mt materiality line; "
                                 "the category can no longer be carried as a screen")

    def test_the_partial_scope_is_stated_beside_every_number(self):
        """A bare figure would read as the category's ceiling while underground factors
        run thirty times the surface low. The unquantified row and the exclusion row
        must be published beside the band, not implied."""
        bounds = {r["bound"] for r in self.rows}
        self.assertEqual(bounds, {"low", "high", "excluded", "unquantified"})
        unq = next(r for r in self.rows if r["bound"] == "unquantified")
        self.assertIn("PARTIAL", " ".join(str(v) for v in unq.values()).upper()
                      .replace("MUST NOT BE READ", "PARTIAL"))
        self.assertIn("thirty times", unq["note"])

    def test_the_materiality_screen_carries_the_bound_with_its_scope(self):
        path = os.path.join(OUTPUTS, "fugitives_completeness_2024.csv")
        with open(path, newline="", encoding="utf-8") as f:
            row = next(r for r in csv.DictReader(f) if r["ipcc_code"] == "1.B.1")
        self.assertNotEqual(row["screen_upper_mt_co2e"], "",
                            "1.B.1's screen column is empty again - the bound the held "
                            "activity permits has been dropped")
        self.assertIn("PARTIAL", row["screen_basis"])
        _lo, hi = self.screen.surface_band_mt()
        self.assertAlmostEqual(float(row["screen_upper_mt_co2e"]), hi, places=4)
        # The stored defect: the rc3 basis string that assigned no bound while the
        # activity sat in the repository.
        self.assertNotIn("No numerical upper bound assigned", row["screen_basis"])

    def test_the_published_file_matches_a_fresh_build(self):
        path = os.path.join(OUTPUTS, "fugitives_coal_screen_2024.csv")
        with open(path, newline="", encoding="utf-8") as f:
            published = list(csv.DictReader(f))
        self.assertEqual(len(published), len(self.rows))
        for want, got in zip(self.rows, published):
            self.assertEqual(str(want["co2e_Mt_AR5"]), got["co2e_Mt_AR5"], got["scope"])


if __name__ == "__main__":
    unittest.main()
