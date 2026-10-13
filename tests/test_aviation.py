"""Tests for the civil aviation sector (IPCC 1A3a).

The general contract is enforced in test_sector_contract.py over every registered sector.
These are this sector's own invariants: the LTO-versus-movement convention, the
bunker/memo convention, the fossil-methane flag, and the two independent benchmarks.

Run:  python3 -m unittest discover tests
"""
import unittest

from pkinv.core import registry
from pkinv.core.geography import PROVINCES
from pkinv.sectors.aviation import air_pollutants, downscale, fuel_bridge, lto, uncertainty
from pkinv.sectors.aviation.data import AviationData


class TestActivity(unittest.TestCase):
    def setUp(self):
        self.data = AviationData()

    def test_load_factor_guards_the_lto_convention(self):
        """THE test that protects the factor of two.

        LTO cycles are movements / 2, because a movement is one take-off OR one landing.
        If that divisor were ever flipped, passengers per movement would imply an
        impossible load factor. At the A320 trunk airports a one-way movement gives
        roughly 140-155 passengers against ~180 seats, i.e. 78-86%; treating a movement
        as a whole cycle would halve that to an implausible 40%.
        """
        rows = {r["icao"]: r for r in self.data.movements_for()}
        for icao in ("OPKC", "OPIS", "OPLA"):        # Karachi, Islamabad, Lahore
            r = rows[icao]
            pax_per_mv = r["pax_dom"] / r["com_dom_mv"]
            self.assertTrue(100.0 < pax_per_mv < 200.0,
                            "%s: %.1f domestic pax per movement is outside the band a "
                            "one-way movement convention implies" % (icao, pax_per_mv))

    def test_lto_is_half_of_movements(self):
        cyc = lto.lto_cycles(self.data)
        mv = sum(r["com_dom_mv"] for r in self.data.movements_for())
        self.assertAlmostEqual(cyc["domestic"], mv / 2.0, places=6)

    def test_panel_is_fiscal_years_2006_to_2023(self):
        years = {r["year"] for r in self.data.movements}
        self.assertEqual(min(years), 2006)
        self.assertEqual(max(years), 2023)
        self.assertEqual(len(years), 18)

    def test_every_airport_maps_into_a_province(self):
        self.assertEqual({r["province"] for r in self.data.movements} - set(PROVINCES), set())

    def test_reingest_recovered_the_airports_the_workbook_dropped(self):
        """The source spreadsheet held 14 airports for FY2023 against 37 in the CAA PDF,
        which is what produced its apparent collapse in non-commercial movements at 2016.
        Parsing the PDFs directly is what fixes it."""
        n2023 = len({r["icao"] for r in self.data.movements_for(2023)})
        self.assertGreaterEqual(n2023, 30, "only %d airports in FY2023" % n2023)

    def test_fleet_shares_sum_to_one_in_every_year(self):
        for year in sorted({r["year"] for r in self.data.movements}):
            for segment in ("commercial", "international", "noncommercial"):
                mix = self.data.fleet_for(segment, year)   # raises if it does not sum to 1
                self.assertTrue(mix)


class TestBunkerConvention(unittest.TestCase):
    """The most important reporting rule in this sector."""

    def setUp(self):
        self.data = AviationData()
        self.sector = registry.get("aviation")

    def test_only_domestic_is_a_component(self):
        """IPCC Vol 2 Ch 3 s3.6.1: emissions from international aviation "are to be
        excluded from national totals, and reported separately as memo items". A memo
        that became a component would be summed into the total by construction."""
        comps = self.sector.build_components(self.data)
        self.assertEqual({c["category"] for c in comps}, {"Domestic aviation"})
        for c in comps:
            self.assertIn("Domestic", c["subitem"])

    def test_international_and_noncommercial_are_memo_only(self):
        memo = self.sector.memo_items(self.data)
        self.assertEqual(len(memo), 2)
        items = " ".join(m["item"] for m in memo)
        self.assertIn("International", items)
        self.assertIn("Non-commercial", items)
        comp_gg = [c["emissions_Gg"] for c in self.sector.build_components(self.data)]
        for m in memo:
            self.assertGreater(m["emissions_Gg"], 0.0)
            self.assertNotIn(m["emissions_Gg"], comp_gg)

    def test_international_exceeds_domestic_in_movements(self):
        """Recorded because it is why the memo formatting matters here more than in the
        waste sector: Pakistan flies far more international than domestic movements, so
        the excluded figure is not a footnote."""
        cyc = lto.lto_cycles(self.data)
        self.assertGreater(cyc["international"], cyc["domestic"])

    def test_methane_IS_flagged_fossil(self):
        """Jet kerosene is a fossil fuel, so aviation CH4 takes the fossil GWP (AR5 30,
        AR6 29.8). This is the deliberate inverse of the waste sector, where an
        equivalent test asserts the flag stays off."""
        ch4 = [c for c in self.sector.build_components(self.data) if c["gas"] == "CH4"]
        self.assertTrue(ch4)
        for c in ch4:
            self.assertTrue(c.get("fossil", False), "aviation CH4 must be flagged fossil")
            # AR5 fossil CH4 is 30, not 28
            self.assertAlmostEqual(c["co2e_Mt_AR5"], c["emissions_Gg"] * 30.0 / 1000.0, places=9)


class TestBenchmarks(unittest.TestCase):
    """Two independent flight-tracking-derived sources that agree within ~12%.

    If these start failing the result has moved outside what the literature supports and
    needs re-arguing, not re-tolerancing.
    """

    def setUp(self):
        self.sector = registry.get("aviation")
        self.data = AviationData()
        comps = self.sector.build_components(self.data)
        self.kt = sum(c["co2e_Mt_AR5"] for c in comps) * 1000.0

    def test_domestic_co2_brackets_oecd_and_climate_trace(self):
        """OECD is fiscal-year matched; Climate TRACE remains calendar-year labelled."""
        values = [(r["source"], r["co2_t"] / 1000.0)
                  for r in self.data.benchmarks_for(2023)
                  if r["component"] == "domestic"]
        for name, value in values:
            ratio = self.kt / value
            self.assertTrue(0.5 < ratio < 2.0,
                            "domestic %.0f kt is %.2fx %s, outside a factor of two"
                            % (self.kt, ratio, name))

    def test_international_lto_is_a_plausible_share_of_full_bunkers(self):
        """We report only the LTO portion of international, which should land near the
        10-15% of full-flight fuel that IPCC associates with the landing and take-off
        cycle on long-haul. OECD's matched full-flight international figure is used."""
        memo = next(m for m in self.sector.memo_items(self.data) if "International" in m["item"])
        oecd = next(r["co2_t"] / 1000.0 for r in self.data.benchmarks_for(2023, "OECD")
                    if r["component"] == "international_bunker")
        share = memo["emissions_Gg"] / oecd
        self.assertTrue(0.05 < share < 0.30,
                        "international LTO is %.0f%% of full bunkers" % (share * 100))


class TestAllocation(unittest.TestCase):
    def test_domestic_and_international_proxies_differ(self):
        """They must be separate rows: Sindh is ~43% of domestic movements but ~27% of
        international, so one blended proxy would misallocate both."""
        shares = downscale.load_shares()
        dom, intl = shares[downscale.PROXY], shares[downscale.PROXY_INTL]
        self.assertGreater(abs(dom["Sindh"] - intl["Sindh"]), 0.10)
        self.assertGreater(abs(dom["Punjab"] - intl["Punjab"]), 0.10)
        for row in (dom, intl):
            self.assertAlmostEqual(sum(row.values()), 1.0, delta=1e-6)

    def test_air_rows_anchor_to_a_real_ghg_subitem(self):
        data = AviationData()
        subitems = {c["subitem"] for c in registry.get("aviation").build_components(data)}
        for r in air_pollutants.compute(data):
            self.assertIn(r["ghg_subitem"], subitems)


class TestFuelBridge(unittest.TestCase):
    def setUp(self):
        self.data = AviationData()

    def test_ocac_jp1_totals_reproduce_the_source(self):
        totals = {year: sum(r["tonnes"] for r in self.data.fuel_sales_for(year)
                            if r["fuel_type"] == "JP-1") for year in (2022, 2023)}
        # FY2022-23 is read from the final revised annual report itself (633,879),
        # not the rounded/misaligned prior-year columns in the following report.
        self.assertEqual(totals, {2022: 633879.0, 2023: 658334.0})
        self.assertEqual(fuel_bridge.commercial_jp1_total(self.data, 2022), 614195.0)
        self.assertEqual(fuel_bridge.commercial_jp1_total(self.data, 2023), 643079.0)

    def test_every_source_row_closes_without_hiding_a_residual(self):
        for year in (2022, 2023):
            for scenario in fuel_bridge.SCENARIOS:
                for row in fuel_bridge.build(self.data, year, scenario):
                    assigned = sum(row[key] for key in fuel_bridge.ACCOUNTS)
                    self.assertAlmostEqual(assigned, row["reported_t"], places=7)
                    self.assertTrue(all(row[key] >= 0 for key in fuel_bridge.ACCOUNTS))

    def test_flight_fuel_bridge_explains_the_apparent_factor_of_four(self):
        summary = fuel_bridge.benchmark_summary(self.data, 2023)
        # Gross local-airline customer fuel is not domestic fuel. Once resident carriers'
        # international departures are removed, the bridge sits close to the movement model.
        self.assertAlmostEqual(summary["fuel_bridge_domestic_co2_t"], 292012.589, places=3)
        self.assertAlmostEqual(summary["movement_domestic_co2_t"], 298858.732, places=3)
        self.assertTrue(0.95 < (summary["fuel_bridge_domestic_co2_t"] /
                                summary["movement_domestic_co2_t"]) < 1.05)

    def test_commercial_fuel_closes_against_oecd_total(self):
        summary = fuel_bridge.benchmark_summary(self.data, 2023)
        self.assertTrue(0.98 < summary["fuel_over_oecd_total"] < 1.02)
        self.assertTrue(summary["oecd_is_calibration_input"])

    def test_structural_scenarios_are_not_collapsed_into_one_interval(self):
        rows = {r["scenario"]: r for r in fuel_bridge.reconciliation(self.data, 2023)}
        self.assertGreater(rows["literal_customer"]["domestic_fuel_t"],
                           rows["movement_count"]["domestic_fuel_t"])
        self.assertGreater(rows["movement_count"]["domestic_fuel_t"],
                           rows["flight_fuel_weighted"]["domestic_fuel_t"])

    def test_benchmarks_are_period_explicit(self):
        oecd = self.data.benchmarks_for(2023, "OECD")
        self.assertTrue(oecd)
        self.assertEqual({(r["period_start"], r["period_end"]) for r in oecd},
                         {("2023-07", "2024-06")})
        climate = self.data.benchmarks_for(2023, "Climate TRACE")
        self.assertEqual(climate[0]["period_start"], "2023-01")


class TestAviationUncertaintyAndPollutants(unittest.TestCase):
    def setUp(self):
        self.data = AviationData()

    def test_uncertainty_is_reproducible_and_keeps_scenarios_separate(self):
        a = uncertainty.run(self.data, n_iter=200, seed=17)
        b = uncertainty.run(self.data, n_iter=200, seed=17)
        self.assertEqual(a, b)
        self.assertEqual({r["structural_scenario"] for r in a},
                         {"representative_stage"} | set(fuel_bridge.SCENARIOS))
        for row in a:
            self.assertLessEqual(row["P2.5_Mt"], row["P50_Mt"])
            self.assertLessEqual(row["P50_Mt"], row["P97.5_Mt"])

    def test_eedb_rows_expose_representative_engine_imputation(self):
        rows = [r for r in air_pollutants.compute(self.data)
                if r["pollutant"] in ("NOx", "CO", "HC")]
        self.assertEqual({r["pollutant"] for r in rows}, {"NOx", "CO", "HC"})
        self.assertTrue(all(r["method"] == "ICAO EEDB representative engine" for r in rows))
        self.assertTrue(all(r["imputed"] for r in rows))
        self.assertTrue(all(0 < r["engine_coverage_share"] <= 1 for r in rows))



class TestObservedUnallocatedAccount(unittest.TestCase):
    """rc14 (the ninth review): observed fuel must not look absent because the
    reference excludes it. The account restates every identified tonne outside
    the 1A3a boundary with a closed evidence vocabulary, and its quantities must
    be the SAME numbers the totals file's memo rows carry - one source, two
    presentations."""

    EVIDENCE = ("fuel_identified_activity_unattributed",
                "fuel_identified_activity_unresolved",
                "observed_unallocated_residual",
                "movement_observed_fuel_mixed")

    def setUp(self):
        import csv, os
        path = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "outputs",
            "aviation_unallocated_fuel_fy2023_24.csv")
        with open(path, newline="", encoding="utf-8") as handle:
            self.rows = {r["account"]: r for r in csv.DictReader(handle)}

    def test_the_three_configuration_streams_are_present_with_closers(self):
        for account in ("military_government_jet", "general_aviation_100ll",
                        "unresolved_government_jp1"):
            row = self.rows[account]
            self.assertIn("booked_as_configuration", row["disposition"], account)
            self.assertTrue(row["closer"].strip(), account)

    def test_evidence_classes_are_from_the_closed_vocabulary(self):
        for account, row in self.rows.items():
            self.assertIn(row["evidence_class"], self.EVIDENCE, account)

    def test_quantities_match_the_totals_memo_rows(self):
        import csv, os
        path = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "outputs", "aviation_totals_fy2023_24.csv")
        with open(path, newline="", encoding="utf-8") as handle:
            notes = " ".join(r["note"] for r in csv.DictReader(handle))
        self.assertIn("%s t jet fuel" % self.rows["military_government_jet"]["tonnes"],
                      notes)
        self.assertAlmostEqual(
            float(self.rows["military_government_jet"]["co2_Gg"]), 381.6, places=1)


if __name__ == "__main__":
    unittest.main()
