"""Scientific guarantees for the complete public-data reconciliation study."""

from pkinv.assets import asset_path
import os
import importlib.util
import unittest

from pkinv.paths import DATA, OUTPUTS
from pkinv.sectors.aviation import (
    adsblol, annual, climatetrace, fuel_bridge, ledger, monthly, performance,
    official_reporting, uncertainty,
)
from pkinv.sectors.aviation.data import AviationData
from pkinv.sectors.aviation.reconstructed import PCAAReconstructedSource
from pkinv.sectors.aviation.study import (
    annual_component_comparison, calibrate_shares, carrier_share_scenarios,
    common_support_ladder, payload_capacity_audits, route_activity_scenarios,
    route_distance_bounds,
)


class TestMonthlyObservedControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = AviationData()
        cls.cumulative, cls.monthly = monthly.ocac_monthly()
        cls.oecd = monthly.oecd_monthly()
        cls.reconciled = monthly.reconciliation(
            cls.monthly, cls.oecd, cls.data.p("co2_per_t_fuel"))

    def test_four_complete_ocac_years_and_matched_oecd_months(self):
        self.assertEqual(len(self.cumulative), 240)
        self.assertEqual(len(self.monthly), 240)
        self.assertEqual(len(self.reconciled), 42)
        self.assertEqual({int(row["fiscal_year"]) for row in self.monthly},
                         {2021, 2022, 2023, 2024})
        self.assertTrue(all(float(row["monthly_t"]) >= 0 for row in self.monthly))

    def test_months_close_to_final_public_report(self):
        for year in (2021, 2022, 2023, 2024):
            for customer in monthly.CUSTOMERS:
                summed = sum(float(r["monthly_t"]) for r in self.monthly
                             if int(r["fiscal_year"]) == year and
                             r["customer_category"] == customer)
                final = next(float(r["cumulative_t"]) for r in self.cumulative
                             if int(r["fiscal_year"]) == year and
                             int(r["period_index"]) == 12 and
                             r["customer_category"] == customer)
                self.assertAlmostEqual(summed, final)

    def test_final_report_rows_are_the_annual_controls(self):
        annual = {(r["fiscal_year"], r["customer_category"]): r["tonnes"]
                  for year in (2022, 2023) for r in self.data.fuel_sales_for(year)
                  if r["fuel_type"] == "JP-1" and r["customer_category"] in monthly.CUSTOMERS}
        for row in self.cumulative:
            if int(row["period_index"]) == 12 and int(row["fiscal_year"]) in (2022, 2023):
                key = (int(row["fiscal_year"]), row["customer_category"])
                self.assertAlmostEqual(float(row["cumulative_t"]), annual[key])


class TestExtendedPublicEvidence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source_rows = annual.source_rows()
        cls.annual = annual.summaries(cls.source_rows)
        cls.oecd = monthly.oecd_monthly()

    def test_nine_year_ocac_ledger(self):
        self.assertEqual(len(self.source_rows), 135)
        self.assertEqual([row["fiscal_year"] for row in self.annual], list(range(2016, 2025)))
        self.assertEqual(next(row for row in self.annual if row["fiscal_year"] == 2023)
                         ["tracked_aviation_jp1_t"], 658334)

    def test_five_complete_oecd_overlap_years(self):
        rows = annual.oecd_comparison(self.annual, self.oecd)
        self.assertEqual(sum(row["period_status"] == "complete" for row in rows), 5)
        self.assertGreater(next(row for row in rows if row["fiscal_year"] == 2023)
                           ["offset_cancellation_fraction"], 0.95)

    def test_monthly_annual_revision_is_not_hidden(self):
        _cumulative, fuel = monthly.ocac_monthly()
        rows = annual.monthly_annual_closure(fuel, self.source_rows)
        revised = [row for row in rows if row["closure_status"] != "exact"]
        self.assertEqual(len(revised), 1)
        self.assertEqual(revised[0]["fiscal_year"], 2024)
        self.assertEqual(revised[0]["monthly_minus_annual_t"], -20)

    def test_official_crt_is_extracted_not_transcribed_silently(self):
        rows = official_reporting.extract_crt()
        self.assertEqual(len(rows), 2)
        domestic = next(row for row in rows if row["scope"] == "domestic territory")
        international = next(row for row in rows if row["scope"] == "international bunker")
        self.assertAlmostEqual(domestic["co2_t"], 654065.328)
        self.assertAlmostEqual(international["co2_t"], 163516.332)
        self.assertAlmostEqual(domestic["domestic_distribution_pct"], 80)
        self.assertEqual(domestic["jet_kerosene_notation"], "NE")

    def test_official_crt_cell_audit_pins_hashes_notation_and_allocation(self):
        rows = official_reporting.extract_crt_audit()
        self.assertEqual(len(rows), 21)
        cells = {row["source_reference"]: row for row in rows}
        self.assertEqual(cells["Table1.A(a)s3!C18"]["notation_key"], "NE")
        self.assertAlmostEqual(float(cells["Table1.D!L9"]["raw_value"]), 80)
        self.assertAlmostEqual(float(cells["Table1.D!M9"]["raw_value"]), 20)
        self.assertEqual(len({row["workbook_sha256"] for row in rows}), 1)
        self.assertEqual(rows[0]["workbook_sha256"],
                         "ca504f7eb0894573d790b1b4c08576d4fbe795acd56ef5e5c4120b0d3897a944")
        self.assertEqual(cells["Table1!C25"]["transformed_value"], 654065.328)

    def test_climatetrace_fiscal_and_spatial_products(self):
        national = climatetrace.national_monthly()
        self.assertEqual(len(national), 240)
        periods = climatetrace.national_periods(national)
        fy = next(row for row in periods if row["period_type"] == "fiscal" and row["year"] == 2023)
        self.assertEqual(fy["months_available"], 12)
        airports = climatetrace.airport_monthly()
        comparisons = climatetrace.airport_comparison(airports)
        self.assertTrue(all(row["spearman_rank_correlation"] > 0.8
                            for row in climatetrace.spatial_diagnostics(comparisons)))

    def test_adsblol_trace_contract_splits_legs(self):
        trace = {"timestamp": 1692100000, "trace": [
            [0, 24.91, 67.16, "ground", 0, 0, 0, 0, {"flight": "PIA301"}],
            [60, 25.00, 67.20, 2000, 180, 30, 0, 1500, None],
            [3600, 31.52, 74.40, "ground", 0, 0, 0, -500, None],
            [7200, 31.52, 74.40, "ground", 0, 0, 2, 0, {"flight": "PIA302"}],
            [10800, 24.91, 67.16, "ground", 0, 0, 0, -500, None],
        ]}
        legs = adsblol._legs(trace)
        self.assertEqual(len(legs), 2)
        self.assertEqual(sum(len(leg) for leg in legs), 5)
        self.assertEqual(adsblol._airport_visits(legs[0], adsblol._airports()),
                         ["OPKC", "OPLA"])

    def test_adsblol_synthetic_positive_control_emits_canonical_stage(self):
        stage, control = adsblol.synthetic_positive_control()
        self.assertEqual(control["status"], "PASS")
        self.assertEqual((stage.origin_icao, stage.destination_icao), ("OPKC", "OPLA"))
        self.assertEqual(stage.source_tier, "A")
        self.assertGreater(stage.trajectory_distance_nm, 0)

    def test_adsblol_distributed_positive_control_audit_passes(self):
        import csv
        with open(os.path.join(OUTPUTS, "aviation_adsblol_positive_controls.csv"),
                  newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual({row["status"] for row in rows}, {"PASS"})
        archive = next(row for row in rows if row["control"] == "OMDB_archive_positive")
        self.assertEqual(float(archive["airport_linked_legs"]), 700)

    @unittest.skipUnless(importlib.util.find_spec("openap"), "OpenAP extra not installed")
    def test_openap_profile_range_tracks_route_length(self):
        from openap import FlightGenerator
        short = performance._synthetic_frame(FlightGenerator("A320", random_seed=42),
                                             300, 10)
        long = performance._synthetic_frame(FlightGenerator("A320", random_seed=42),
                                            1100, 10)
        self.assertLess(abs(float(short.s.iloc[-1]) / 1000 - 300), 5)
        self.assertLess(abs(float(long.s.iloc[-1]) / 1000 - 1100), 33)
        self.assertGreater(float(long.t.iloc[-1]), float(short.t.iloc[-1]) * 2)


class TestComponentAndCarrierStructure(unittest.TestCase):
    def setUp(self):
        self.data = AviationData()

    def test_component_offsets_sum_to_combined_and_mostly_cancel(self):
        rows = annual_component_comparison(self.data)
        for year in (2022, 2023):
            selected = {r["component"]: r for r in rows if r["fiscal_year"] == year}
            self.assertAlmostEqual(selected["resident"]["difference_co2_t"] +
                                   selected["foreign"]["difference_co2_t"],
                                   selected["combined"]["difference_co2_t"])
            self.assertGreater(selected["combined"]["offset_cancellation_fraction"], 0.95)
            self.assertGreater(selected["resident"]["ratio"], 1.25)
            self.assertLess(selected["foreign"]["ratio"], 0.80)

    def test_logit_calibration_preserves_order_and_hits_target(self):
        raw = {"PIA": 0.45, "Others": 0.62}
        weights = {"PIA": 193813, "Others": 166119}
        values, _ = calibrate_shares(raw, weights, 0.25674029281181654)
        aggregate = sum(weights[k] * values[k] for k in values) / sum(weights.values())
        self.assertAlmostEqual(aggregate, 0.25674029281181654)
        self.assertLess(values["PIA"], values["Others"])

    def test_customer_specific_bridge_closes_every_source_row(self):
        rows = fuel_bridge.build_with_customer_shares(
            self.data, {"Domestic Avi-PIA": 0.20, "Domestic Avi-Others": 0.32},
            2023, "test")
        for row in rows:
            self.assertAlmostEqual(sum(row[key] for key in fuel_bridge.ACCOUNTS),
                                   row["reported_t"])


class TestRouteAndResolutionExperiments(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = AviationData()
        cls.source = PCAAReconstructedSource()
        cls.routes, cls.endpoint_residual = cls.source.route_ledger()
        cls.aircraft = ledger.read(os.path.join(
            OUTPUTS, "aviation_aircraft_ledger_fy2023_24.csv"))
        cls.assigned = [s for s in cls.aircraft if s.source_tier != "D"]

    def test_route_distance_feasible_envelope_contains_central(self):
        bounds = route_distance_bounds(self.source)
        self.assertEqual([r["scenario"] for r in bounds],
                         ["minimum", "central_ipf", "maximum"])
        self.assertLessEqual(bounds[0]["mean_stage_nm"], bounds[1]["mean_stage_nm"])
        self.assertLessEqual(bounds[1]["mean_stage_nm"], bounds[2]["mean_stage_nm"])

    def test_route_activity_scenarios_each_close_to_supported_stages(self):
        rows = route_activity_scenarios(self.source, self.assigned)
        totals = {scenario: sum(float(row["stage_count"]) for row in rows
                                if row["route_graph"] == scenario)
                  for scenario in ("minimum", "central_ipf", "maximum")}
        self.assertEqual(set(totals), {"minimum", "central_ipf", "maximum"})
        for total in totals.values():
            self.assertAlmostEqual(total, 20097.5, places=4)

    def test_documented_international_endpoints_have_distances(self):
        stages, _residual = self.source.international_route_ledger()
        self.assertGreater(len(stages), 0)
        self.assertTrue(all(stage.great_circle_nm and stage.great_circle_nm > 0
                            for stage in stages))

    def test_common_support_and_completion_are_not_mixed(self):
        ladder = common_support_ladder(self.data, self.routes, self.assigned,
                                       self.endpoint_residual)
        common = [r for r in ladder if r["experiment"] == "common_support"]
        self.assertEqual(len({round(r["stage_count"], 6) for r in common}), 1)
        completed = next(r for r in ladder if r["step"] == "completed_total")
        self.assertAlmostEqual(completed["stage_count"], 20300, places=5)
        components = [r for r in ladder if r["experiment"] == "coverage_completion" and
                      r["step"] != "completed_total"]
        self.assertAlmostEqual(sum(r["fuel_t"] for r in components), completed["fuel_t"])
        self.assertAlmostEqual(sum(r["stage_count"] for r in components), 20300, places=5)

    def test_complete_uncertainty_register_separates_classes(self):
        bounds = route_distance_bounds(self.source)
        rows = uncertainty.full_factor_table(self.data, bounds)
        self.assertGreaterEqual(len(rows), 12)
        self.assertEqual({r["uncertainty_class"] for r in rows},
                         {"parametric", "structural"})
        self.assertTrue(all(r["source"] for r in rows))

    def test_pcaa_payload_and_direct_departure_controls_are_used(self):
        import csv
        with open(os.path.join(OUTPUTS, "aviation_openap_lookup_fy2023_24.csv"),
                  newline="", encoding="utf-8") as handle:
            lookup_rows = list(csv.DictReader(handle))
        airline_rows, _airport_rows, departure_rows = payload_capacity_audits(
            self.assigned, lookup_rows)
        domestic = {row["airline_icao"]: row for row in airline_rows
                    if row["boundary"] == "domestic"}
        self.assertEqual(len(domestic), 5)
        self.assertAlmostEqual(domestic["PIA"]["passengers_per_departure"],
                               824870 / 7536)
        self.assertGreater(domestic["PIA"]["mail_kg_per_departure"], 0)
        self.assertTrue(all(row["capacity_status"] == "PASS" for row in domestic.values()))
        direct = {row["boundary"]: row for row in departure_rows}
        self.assertEqual(direct["domestic"]["published_airline_departures"], 19752)
        self.assertEqual(direct["international"]["published_airline_departures"], 45723)
        central_pia = next(row for row in lookup_rows
                           if row["airline_icao"] == "PIA" and
                           row["boundary"] == "domestic" and
                           row["payload_scenario"] == "central")
        self.assertEqual(central_pia["payload_source"],
                         "PCAA airline embarked passengers, loaded cargo and loaded mail per departure")
        self.assertAlmostEqual(float(central_pia["observed_passenger_load_fraction"]),
                               domestic["PIA"]["implied_passenger_load_factor"])
        self.assertGreater(float(central_pia["mail_kg_per_stage"]), 0)

    def test_completed_m2_interval_closes_and_excludes_m0_umbrella(self):
        import csv
        scenarios = route_activity_scenarios(self.source, self.assigned)
        with open(os.path.join(OUTPUTS, "aviation_openap_lookup_fy2023_24.csv"),
                  newline="", encoding="utf-8") as handle:
            lookup_rows = list(csv.DictReader(handle))
        with open(asset_path(DATA, "activity", "aviation", "aircraft_family_shares_2023_24.csv"),
                  newline="", encoding="utf-8") as handle:
            shares = list(csv.DictReader(handle))
        intervals, envelope, contributions = uncertainty.run_completed_m2(
            self.data, scenarios, 202.5, lookup_rows, shares, [-5.0, 1.0],
            n_iter=120, seed=11)
        self.assertEqual(len(intervals), 36)
        self.assertEqual(len(envelope), 4)
        self.assertTrue(contributions)
        self.assertTrue(all(abs(row["stage_count"] - 20300) < 1e-5 for row in intervals))
        self.assertTrue(all("aggregate" not in row["parametric_inputs"].lower()
                            for row in intervals))
        primary = {(row["route_graph"], row["completion_method"], row["metric"]): row
                   for row in intervals if row["interval_type"] == "primary"}
        for key, row in primary.items():
            if key[-1] == "CO2":
                self.assertLessEqual(row["P50_Mt"], primary[key[:-1] + ("CO2E",)]["P50_Mt"])


if __name__ == "__main__":
    unittest.main()
