"""Flight-ledger, coverage, performance, and independent fuel-control guarantees."""
import os
import tempfile
import unittest

from pkinv.sectors.aviation import coverage, fuel_bridge, ledger, opensky, performance, products, uncertainty
from pkinv.sectors.aviation.data import AviationData


def stage(fid, origin, destination, operator="PIA", fuel=0, tier="A"):
    return ledger.FlightStage(
        flight_id=fid, fiscal_year=2023, first_seen=1688169600,
        last_seen=1688173200, origin_icao=origin, destination_icao=destination,
        boundary=ledger.boundary(origin, destination), operator=operator,
        aircraft_type="A320", great_circle_nm=500, source_tier=tier,
        source="test fixture", cruise_fuel_kg=fuel, total_fuel_kg=fuel)


class TestCanonicalLedger(unittest.TestCase):
    def test_boundary_uses_endpoints_not_operator(self):
        self.assertEqual(ledger.boundary("OPKC", "OPLA"), "domestic")
        self.assertEqual(ledger.boundary("OPKC", "OMDB"), "international")
        self.assertEqual(ledger.boundary("", "OPKC"), "unresolved")

    def test_phase_fuel_must_close(self):
        bad = stage("bad", "OPKC", "OPLA", fuel=100)
        bad.climb_fuel_kg = 1
        with self.assertRaisesRegex(ValueError, "phase fuel"):
            bad.validate()

    def test_csv_round_trip_and_duplicate_guard(self):
        records = [stage("one", "OPKC", "OPLA")]
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "ledger.csv")
            ledger.write(records, path)
            got = ledger.read(path)
        self.assertEqual(got[0].flight_id, "one")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            ledger.validate_records(records * 2)


class TestCoverageControls(unittest.TestCase):
    def test_reconstruction_uses_supported_routes_and_closes(self):
        observed = [stage("one", "OPKC", "OPLA")]
        controls = {"OPKC": 2, "OPLA": 2}
        completed, residual = coverage.reconstruct(observed, controls)
        self.assertEqual(residual, {})
        self.assertEqual(coverage.endpoint_movements(completed), controls)
        self.assertEqual(completed[-1].source_tier, "C")
        self.assertEqual(completed[-1].record_granularity, "annual_route")
        self.assertEqual(completed[-1].first_seen, 0)

    def test_unsupported_deficit_remains_visible(self):
        completed, residual = coverage.reconstruct(
            [stage("one", "OPKC", "OPLA")], {"OPKC": 1, "OPLA": 1, "OPGT": 2})
        self.assertEqual(residual, {"OPGT": 2})
        self.assertEqual(len(completed), 1)


class FakeFuelFlow:
    def takeoff(self, tas, alt=None, throttle=1):
        return 2.0

    def enroute(self, mass, tas, alt, vs=0, acc=0, dT=0, limit=True):
        return 1.0


class TestFlightPerformance(unittest.TestCase):
    def test_phase_integration_is_exact_and_closed(self):
        s = stage("perf", "OPKC", "OPLA", fuel=0)
        points = [
            ledger.TrajectoryPoint("perf", 0, 0, 0, 0, 50, 3, False, "takeoff"),
            ledger.TrajectoryPoint("perf", 10, 0, 0, 1000, 100, 5, False, "climb"),
            ledger.TrajectoryPoint("perf", 20, 0, 0, 9000, 200, 0, False, "cruise"),
        ]
        got = performance.integrate(s, points, 60000, FakeFuelFlow())
        self.assertEqual(got.takeoff_fuel_kg, 20)
        self.assertEqual(got.climb_fuel_kg, 10)
        self.assertEqual(got.total_fuel_kg, 30)
        got.validate()


class TestLedgerFuelBridge(unittest.TestCase):
    def setUp(self):
        self.data = AviationData()

    def test_split_is_ledger_derived_and_source_rows_close(self):
        stages = [stage("pd", "OPKC", "OPLA", "PIA", 3000),
                  stage("pi", "OPKC", "OMDB", "PIA", 7000),
                  stage("od", "OPKC", "OPLA", "ABQ", 6000),
                  stage("oi", "OPKC", "OMDB", "ABQ", 4000)]
        shares = fuel_bridge.ledger_customer_shares(self.data, stages)
        self.assertEqual(shares["Domestic Avi-PIA"], 0.3)
        self.assertEqual(shares["Domestic Avi-Others"], 0.6)
        rows = fuel_bridge.build_from_ledger(self.data, stages)
        self.assertTrue(all(r["scenario"] == "flight_ledger" for r in rows))
        for row in rows:
            self.assertAlmostEqual(sum(row[k] for k in fuel_bridge.ACCOUNTS),
                                   row["reported_t"])
        recon = fuel_bridge.ledger_reconciliation(self.data, stages)
        self.assertTrue(all(r["central_split_uses_oecd"] is False for r in recon))

    def test_missing_resident_group_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "Domestic Avi-Others"):
            fuel_bridge.build_from_ledger(
                self.data, [stage("pd", "OPKC", "OPLA", "PIA", 1000),
                            stage("pi", "OPKC", "OMDB", "PIA", 1000)])

    def test_products_keep_accounting_views_separate(self):
        stages = [stage("d", "OPKC", "OPLA", "PIA", 1000),
                  stage("i", "OPKC", "OMDB", "PIA", 2000)]
        views = {r["accounting_view"]: r["fuel_t"]
                 for r in products.accounting_views(stages, self.data, 500)}
        self.assertEqual(views["UNFCCC domestic aviation"], 1)
        self.assertEqual(views["International aviation bunkers"], 2)
        self.assertEqual(views["Resident-carrier worldwide departures"], 3)
        self.assertEqual(views["Physical emissions over Pakistan"], 0.5)

    def test_flight_uncertainty_is_reproducible_and_structural(self):
        stages = [stage("d", "OPKC", "OPLA", "PIA", 1000),
                  stage("r", "OPLA", "OPKC", "ABQ", 1000,
                        tier="C")]
        stages[1].record_granularity = "annual_route"
        a = uncertainty.run_flight_ledger(self.data, stages, n_iter=50, seed=7)
        b = uncertainty.run_flight_ledger(self.data, stages, n_iter=50, seed=7)
        self.assertEqual(a, b)
        self.assertEqual({r["structural_scenario"] for r in a},
                         {"completed_ledger", "observed_only"})
        self.assertGreater(a[0]["mean_Mt"], a[1]["mean_Mt"])


class TestOpenSkyContract(unittest.TestCase):
    def test_query_is_period_and_geography_explicit(self):
        sql = opensky.flight_sql()
        self.assertIn(str(int(opensky.START.timestamp())), sql)
        self.assertIn(str(int(opensky.END.timestamp())), sql)
        self.assertIn("estdepartureairport LIKE 'OP%'", sql)

    def test_extraction_fails_without_credentials(self):
        old = {k: os.environ.pop(k, None) for k in
               ("OPENSKY_TRINO_USER", "OPENSKY_TRINO_PASSWORD")}
        try:
            with self.assertRaisesRegex(RuntimeError, "OPENSKY_TRINO_USER"):
                opensky._credentials()
        finally:
            for key, value in old.items():
                if value is not None:
                    os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
