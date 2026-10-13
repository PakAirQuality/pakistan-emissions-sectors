"""Guarantees for the officially constrained FY2023-24 fallback."""

from pkinv.assets import asset_path
import csv
import os
import unittest

from pkinv.paths import DATA
from pkinv.sectors.aviation import coverage, fuel_bridge, ledger
from pkinv.sectors.aviation.data import AviationData
from pkinv.sectors.aviation.reconstructed import PCAAReconstructedSource
from pkinv.core.io import read_rows

ACTIVITY = asset_path(DATA, "activity", "aviation")


def rows(name):
    return read_rows(os.path.join(ACTIVITY, name), comments=False)


class TestOfficialControls(unittest.TestCase):
    def test_airport_national_activity_controls(self):
        source = rows("airport_controls_2023_24.csv")
        self.assertEqual(sum(int(r["domestic_commercial_movements"]) for r in source), 40600)
        self.assertEqual(sum(int(r["international_commercial_movements"]) for r in source), 95267)
        self.assertEqual(sum(int(r["noncommercial_movements"]) for r in source), 21223)
        self.assertEqual(sum(int(r["domestic_passengers"]) for r in source), 5679830)

    def test_airline_control_gap_is_preserved(self):
        source = [r for r in rows("airline_controls_2023_24.csv")
                  if r["traffic_scope"] == "domestic"]
        movements = sum(int(r["movements"]) for r in source)
        self.assertEqual(movements, 39504)
        self.assertEqual(40600 - movements, 1096)

    def test_ocac_customer_classes_are_unresolved_at_ingest(self):
        source = rows("fuel_controls_2023_24.csv")
        self.assertTrue(source)
        self.assertTrue(all(r["preliminary_ipcc_assignment"] == "UNRESOLVED" for r in source))
        got = {(r["customer_category"], r["fuel_type"]): float(r["tonnes"]) for r in source}
        self.assertEqual(got[("Domestic Avi-PIA", "JP-1")], 193813)
        self.assertEqual(got[("Domestic Avi-Others", "JP-1")], 166119)
        self.assertEqual(got[("Overseas/Foreign Aviation", "JP-1")], 283147)


class TestWeightedFallback(unittest.TestCase):
    def test_reconstruction_has_no_fictional_dates_and_exposes_residual(self):
        source = PCAAReconstructedSource()
        routes, residual = source.route_ledger()
        self.assertTrue(routes)
        self.assertTrue(residual)
        self.assertTrue(all(r.source_tier == "C" and not r.first_seen and not r.date
                            for r in routes))
        self.assertTrue(all(r.source_tier == "D" and not r.origin_icao and not r.destination_icao
                            for r in residual))
        controls, _ = source.controls()
        target = sum(float(r["domestic_commercial_movements"]) for r in controls)
        allocated = sum(coverage.endpoint_movements(routes).values())
        self.assertAlmostEqual(allocated + sum(r.activity_count for r in residual), target)

    def test_aircraft_assignment_preserves_operator_residual(self):
        source = PCAAReconstructedSource()
        routes, _ = source.route_ledger()
        assigned, residual = source.aircraft_ledger(routes)
        controls = {r["airline_icao"]: float(r["departures"])
                    for r in rows("airline_controls_2023_24.csv")
                    if r["traffic_scope"] == "domestic"}
        for airline, target in controls.items():
            allocated = sum(r.activity_count for r in assigned if r.operator == airline)
            missing = sum(r.activity_count for r in residual if r.operator == airline)
            self.assertAlmostEqual(allocated + missing, target)
        self.assertAlmostEqual(sum(r.activity_count for r in assigned), 19752)

    def test_joint_assignment_never_overallocates_a_route(self):
        source = PCAAReconstructedSource()
        routes, _ = source.route_ledger()
        assigned, _ = source.aircraft_ledger(routes)
        for route in routes:
            got = sum(r.activity_count for r in assigned
                      if (r.origin_icao, r.destination_icao) ==
                      (route.origin_icao, route.destination_icao))
            self.assertLessEqual(got, route.activity_count + 1e-6)

    def test_resident_international_is_outbound_and_closes_to_residual(self):
        source = PCAAReconstructedSource()
        assigned, residual = source.international_route_ledger()
        controls = {r["airline_icao"]: float(r["departures"])
                    for r in rows("airline_controls_2023_24.csv")
                    if r["traffic_scope"] == "international" and
                    r["airline_icao"] in {"PIA", "ABQ", "FJL", "SEP", "SIF"}}
        self.assertTrue(assigned)
        self.assertTrue(all(r.origin_icao.startswith("OP") and
                            not r.destination_icao.startswith("OP") for r in assigned))
        for airline, target in controls.items():
            got = sum(r.activity_count for r in assigned if r.operator == airline)
            missing = sum(r.activity_count for r in residual if r.operator == airline)
            self.assertAlmostEqual(got + missing, target)

    def test_evidence_dates_overlap_anchor_and_current_pages_are_not_historical_class(self):
        from datetime import date
        start, end = date(2023, 7, 1), date(2024, 6, 30)
        for row in rows("route_evidence_2023_24.csv"):
            self.assertLessEqual(date.fromisoformat(row["active_from"]), end)
            self.assertGreaterEqual(date.fromisoformat(row["active_to"]), start)
            self.assertNotEqual(row["evidence_class"], "current schedule")

    def test_anchor_fuel_scenarios_close_and_model_gap_is_not_forced(self):
        data = AviationData()
        for scenario in fuel_bridge.ANCHOR_SCENARIOS:
            built = fuel_bridge.build_anchor_scenario(data, ACTIVITY, [], 2023, scenario)
            for row in built:
                self.assertAlmostEqual(sum(row[key] for key in fuel_bridge.ACCOUNTS),
                                       row["reported_t"])
        modelled = fuel_bridge.build_anchor_scenario(
            data, ACTIVITY, [], 2023, "modelled_fuel")
        local = [r for r in modelled if r["customer_category"] in fuel_bridge.LOCAL_CUSTOMERS
                 and r["fuel_type"] == "JP-1"]
        self.assertTrue(all(r["coverage_status"] == "unresolved" for r in local))
        self.assertEqual(sum(r["residual"] for r in local), 359932)

    def test_modelled_bridge_is_quantitatively_coverage_gated(self):
        data = AviationData()
        source = PCAAReconstructedSource()
        routes, _ = source.route_ledger()
        domestic, _ = source.aircraft_ledger(routes)
        international, _ = source.international_route_ledger()
        # No fuel has yet been attached, so mere route presence cannot unlock M3.
        built = fuel_bridge.build_anchor_scenario(
            data, ACTIVITY, domestic + international, 2023, "modelled_fuel")
        local = [r for r in built if r["customer_category"] in fuel_bridge.LOCAL_CUSTOMERS
                 and r["fuel_type"] == "JP-1"]
        self.assertTrue(all(r["coverage_status"] == "unresolved" for r in local))
        self.assertTrue(all(float(r["domestic_fuel_coverage"]) == 0 for r in local))


if __name__ == "__main__":
    unittest.main()
