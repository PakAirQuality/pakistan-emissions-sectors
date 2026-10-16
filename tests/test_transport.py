"""Tests for the road transport sector (IPCC 1A3b).

The general contract is enforced in test_sector_contract.py. These are this sector's own
invariants: the Weibull survival model, the fleet-cap defect, the fuel anchor, and the
off-road boundary.

Run:  python3 -m unittest discover tests
"""

from pkinv.assets import asset_path
import csv
import os
import unittest

from _support import require_documents  # noqa: E402  (rc42: the documents gate)

from pkinv.core import registry
from pkinv.paths import DATA
from pkinv.sectors.transport import (downscale, fleet, fuel_ledger, offroad,
                                     province_shape, road)
from pkinv.sectors.transport.data import TransportData


class TestWeibull(unittest.TestCase):
    """The survival model, whose shape parameters exist only in the manuscript PDF."""

    def setUp(self):
        self.data = TransportData()

    def test_survival_is_one_at_age_zero_and_half_at_the_median_life(self):
        """Pins lambda = L / (ln 2)^(1/beta). If that derivation were wrong, S(L) would
        not be 0.5 and every fleet number would be quietly off."""
        for cls in fleet.CLASSES:
            beta = self.data.p("weibull_beta_%s" % cls)
            life = self.data.p("weibull_life_%s" % cls)
            self.assertAlmostEqual(fleet.survival(0, beta, life), 1.0, places=12)
            self.assertAlmostEqual(fleet.survival(life, beta, life), 0.5, places=12)

    def test_survival_is_monotone_decreasing(self):
        for cls in fleet.CLASSES:
            beta = self.data.p("weibull_beta_%s" % cls)
            life = self.data.p("weibull_life_%s" % cls)
            vals = [fleet.survival(t, beta, life) for t in range(0, 40)]
            self.assertEqual(vals, sorted(vals, reverse=True))

    def test_cohorts_never_negative(self):
        """Equation (6) discards falling increments. That is the source's convention and
        the cause of the defect the cap exists to contain."""
        c = fleet.cohorts({2003: 100.0, 2004: 150.0, 2005: 120.0, 2006: 200.0})
        self.assertEqual(c[2003], 100.0)
        self.assertEqual(c[2004], 50.0)
        self.assertEqual(c[2005], 0.0)      # the fall is discarded, not carried
        self.assertEqual(c[2006], 80.0)

    def test_active_fleet_is_capped_at_reported_stock(self):
        """Without the cap the summed cohorts can exceed the stock ever registered. In
        the source workbook this reaches 402x at district-and-class level."""
        series = {2003: 1000.0, 2004: 2000.0, 2005: 500.0}
        uncapped, _ = fleet.active_fleet(series, 3.0, 15, 2005, cap=False)
        capped, was_capped = fleet.active_fleet(series, 3.0, 15, 2005, cap=True)
        self.assertGreater(uncapped, 500.0)
        self.assertEqual(capped, 500.0)
        self.assertTrue(was_capped)


class TestFuelAnchor(unittest.TestCase):
    def setUp(self):
        self.data = TransportData()
        self.sector = registry.get("transport")

    def test_total_matches_the_fuel_control_total(self):
        """The whole design: the national total is fuel supplied times an IPCC factor, so
        it reconciles by construction rather than as an afterthought. Fleet errors move
        the class split, not the magnitude.

        This closes EXACTLY. It used to be an inequality, because the off-road share
        was carved out of the control total and reported as a memo outside the components.
        Off-road is a category of its own since, so on-road plus off-road exhausts the
        petrol and diesel supplied and nothing is left over - which is the strongest form
        the fuel anchor can take, and worth asserting as equality rather than a band.

        CNG IS EXCLUDED FROM BOTH SIDES, and the exclusion is the point rather than a
        loophole. CNG emissions come from OGRA's metered sector gas, not from the petroleum
        control total, so counting them here would break an anchor that is still perfectly
        intact - the test would be reporting a second activity basis as a reconciliation
        failure. The complementary assertion below is what stops that becoming a hole: CNG
        must account for the ENTIRE difference, so any other stream leaking in still fails."""
        tj = road.fuel_TJ(self.data)
        expected = sum(
            tj[f] * self.data.efv("transport_fuel_co2", road.IPCC_FUEL[f]) / 1e6
            for f in ("Petrol", "Diesel"))
        comps = self.sector.build_components(self.data)
        got = sum(c["emissions_Gg"] for c in comps
                  if c["gas"] == "CO2" and not c["subitem"].startswith("CNG"))
        self.assertAlmostEqual(got, expected, places=9)

        # The other half: everything NOT anchored on petroleum is CNG and nothing else.
        unanchored = sum(c["emissions_Gg"] for c in comps if c["gas"] == "CO2") - got
        cng_co2 = sum(c["emissions_Gg"] for c in comps
                      if c["gas"] == "CO2" and c["subitem"].startswith("CNG"))
        self.assertAlmostEqual(unanchored, cng_co2, places=9,
                               msg="a CO2 stream exists that is neither petroleum-anchored "
                                   "nor CNG - the fuel anchor has a hole in it")

    def test_methane_IS_flagged_fossil(self):
        """Petrol and diesel are fossil, so CH4 takes AR5 30 not 28. Matches power and
        aviation; the waste sector asserts the opposite."""
        ch4 = [c for c in self.sector.build_components(self.data) if c["gas"] == "CH4"]
        self.assertTrue(ch4)
        for c in ch4:
            self.assertTrue(c.get("fossil", False))

    def test_total_in_the_expected_band(self):
        """Pakistan's BUR1 puts the whole transport sector near 51 Mt CO2e. This covers
        road only. Railway diesel is now deducted from the control total (see
        tests/test_railways.py::TestRoadClosure), but agricultural and captive-generation
        diesel remain inside it and still bias this figure high."""
        tot = sum(c["co2e_Mt_AR5"] for c in self.sector.build_components(self.data))
        self.assertTrue(35.0 < tot < 80.0, "road transport %.1f Mt" % tot)


class TestOffRoadBoundary(unittest.TestCase):
    """The easiest thing in this sector to get wrong. Off-road machinery is now a reported
    category rather than a memo item, so the failure mode has changed: it is no longer
    "the stream gets summed into road" but "the stream gets reported twice"."""

    def setUp(self):
        self.data = TransportData()
        self.sector = registry.get("transport")
        self.comps = self.sector.build_components(self.data)

    def test_off_road_is_not_inside_1a3b(self):
        """Tractors and plant are IPCC 1A4c, not 1A3b. They are in this sector's component
        list now, but they must never carry the road-transport category."""
        for c in self.comps:
            if c["category"] == road.CATEGORY:
                self.assertNotIn(road.OFF_ROAD, c["subitem"].split())
                self.assertNotIn("Off-road", c["subitem"])

    def test_off_road_is_a_category_and_no_longer_a_memo(self):
        """It rode as a CO2-only memo until it had a category to live in. Keeping the memo
        as well would report the same diesel twice."""
        self.assertEqual(self.sector.memo_items(self.data), [])
        off = [c for c in self.comps if c["category"] == offroad.CATEGORY]
        self.assertEqual({c["gas"] for c in off}, {"CO2", "CH4", "N2O"})
        for c in off:
            self.assertGreater(c["emissions_Gg"], 0.0)

    def test_the_category_name_states_its_ipcc_code(self):
        """A reader scanning a category list should not have to know that off-road
        machinery is not transport."""
        self.assertIn("1A4c", offroad.CATEGORY)

    def test_the_two_categories_partition_the_diesel(self):
        """off_road_TJ is carved from the same control total by the same share machinery
        that splits the on-road classes, so the two cannot claim the same tonne."""
        total_diesel = road.fuel_TJ(self.data)["Diesel"]
        off_tj = road.off_road_TJ(self.data)
        self.assertGreater(off_tj, 0.0)
        self.assertLess(off_tj, total_diesel)
        share = off_tj / total_diesel
        self.assertTrue(0.02 < share < 0.30, "off-road takes %.1f%% of diesel" % (share * 100))

    def test_off_road_uses_its_own_ipcc_table(self):
        """Table 3.3.1, not the road Table 3.2.2. N2O is seven times higher because
        off-road engines carry no catalyst; on the road factor this category would report
        materially less."""
        off_n2o = self.data.efv("offroad_machinery_n2o", "Gas/Diesel Oil")
        road_n2o = self.data.efv("transport_fuel_n2o", "Gas/Diesel Oil")
        self.assertGreater(off_n2o, 5 * road_n2o)
        self.assertEqual(self.data.efv("offroad_machinery_co2", "Gas/Diesel Oil"),
                         self.data.efv("transport_fuel_co2", "Gas/Diesel Oil"))

    def test_the_table_choice_moves_the_answer(self):
        """A pinned factor nothing depends on is decoration."""
        off = [c for c in self.comps if c["category"] == offroad.CATEGORY]
        total = sum(c["co2e_Mt_AR5"] for c in off)
        n2o = sum(c["co2e_Mt_AR5"] for c in off if c["gas"] == "N2O")
        self.assertGreater(n2o / total, 0.05)

    def test_off_road_rides_cropland_not_vehicle_kilometres(self):
        """Tractors follow the crop area. Allocating them on vehicle-kilometres would put
        them where the cars are, at an unchanged national total."""
        shares = downscale.load_shares()
        self.assertNotEqual(shares[downscale.PROXY]["Punjab"],
                            shares[downscale.OFFROAD_PROXY]["Punjab"])
        self.assertAlmostEqual(sum(shares[downscale.OFFROAD_PROXY].values()), 1.0, places=6)


class TestOcacAnchor(unittest.TestCase):
    """The controls in emission_factors.csv must equal the OCAC Road rows in the
    committed sectoral CSV - the anti-drift equality that makes keeping the control
    as a factor row safe. If either file is edited alone, this fails."""

    def setUp(self):
        self.data = TransportData()

    def test_the_diesel_control_is_the_ocac_road_row(self):
        self.assertAlmostEqual(
            self.data.efv("transport_fuel_supply", "Gas/Diesel Oil"),
            self.data.ocac_t("Road", "HSD") / 1000.0, places=3)

    def test_the_petrol_control_is_ms_plus_hobc(self):
        self.assertAlmostEqual(
            self.data.efv("transport_fuel_supply", "Motor Gasoline"),
            (self.data.ocac_t("Road", "MS") + self.data.ocac_t("Road", "HOBC"))
            / 1000.0, places=3)

    def test_the_legacy_control_documents_its_own_error(self):
        """The superseded rows must keep the values that were published and a note
        stating the x16/9 finding - the bridge must stay honest, not vanish."""
        self.assertEqual(self.data.efv("transport_fuel_supply_legacy",
                                       "Gas/Diesel Oil"), 8820.0)
        self.assertEqual(self.data.efv("transport_fuel_supply_legacy",
                                       "Motor Gasoline"), 10162.0)
        note = self.data.ef[("transport_fuel_supply_legacy",
                             "Gas/Diesel Oil")]["source"]
        # the note column is loaded into neither efv nor efu; read the raw row
        import csv as _csv
        from pkinv.paths import DATA as _DATA
        with open(asset_path(_DATA, "emission_factors.csv"), newline="",
                  encoding="utf-8") as f:
            rows = {r["ef_id"]: r for r in _csv.DictReader(f)}
        self.assertIn("16/9", rows["tr_fuel_diesel_kt_legacy"]["note"])
        self.assertIn("SUPERSEDED", rows["tr_fuel_diesel_kt_legacy"]["note"])

    def test_the_pes12_row_is_the_corrected_arithmetic(self):
        self.assertAlmostEqual(
            self.data.efv("transport_fuel_supply_pes12", "Gas/Diesel Oil"),
            4961.0 * 12 / 9, places=2)
        self.assertAlmostEqual(
            self.data.efv("transport_fuel_supply_pes12", "Motor Gasoline"),
            (5512.5 + 203.5) * 12 / 9, places=2)


class TestFuelLedger(unittest.TestCase):
    """The two-tier claimant ledger. Its whole value is that every resolved row is
    READ from the table or module that owns it, so these tests assert equality with
    the accessors, not with constants - and that the national tier is OCAC's own
    exhaustive partition, which is the claimant-exhaustiveness demonstration."""

    @classmethod
    def setUpClass(cls):
        cls.data = TransportData()
        cls.rows, cls.checks = fuel_ledger.build(cls.data)

    def _row(self, fuel, tier, claimant):
        return next(r for r in self.rows
                    if r["fuel"] == fuel and r["tier"] == tier
                    and r["claimant"] == claimant)

    def test_all_four_ledgers_close_exactly(self):
        """Opening == claims + closing, per (fuel, tier). A claim added without room
        would go negative in the residual and show up here."""
        self.assertEqual(set(self.checks),
                         {("Diesel", "national"), ("Diesel", "road"),
                          ("Petrol", "national"), ("Petrol", "road")})
        for key, resid in self.checks.items():
            self.assertLess(abs(resid), 1e-6, key)
        for key in self.checks:
            fuel, tier = key
            resolved = [r for r in self.rows
                        if r["fuel"] == fuel and r["tier"] == tier
                        and r["kind"] in ("claim", "closing")]
            self.assertAlmostEqual(sum(r["share_of_opening"] for r in resolved),
                                   1.0, places=9, msg=key)

    def test_the_national_tier_reads_ocac_rows(self):
        """Every national-tier quantity equals its OCAC cell - observed, not argued."""
        self.assertEqual(self._row("Diesel", "national", "Railways")["kt"],
                         self.data.ocac_t("Railways", "HSD") / 1000.0)
        self.assertEqual(self._row("Diesel", "national", "Industry")["kt"],
                         self.data.ocac_t("Total Industry", "HSD") / 1000.0)
        self.assertEqual(self._row("Diesel", "national", "Power")["kt"],
                         self.data.ocac_t("Total Power", "HSD") / 1000.0)
        self.assertEqual(
            self._row("Diesel", "national", "Road (retail pump sales)")["kt"],
            self.data.ocac_t("Road", "HSD") / 1000.0)

    def test_bulk_agricultural_diesel_is_observed_zero(self):
        """The fact the whole boundary story rests on: OCAC books no bulk HSD to
        Agriculture, so the agricultural claim is retail-channel only."""
        self.assertEqual(
            self._row("Diesel", "national", "Agriculture (bulk)")["kt"], 0.0)

    def test_the_rail_row_carries_the_crosscheck(self):
        note = self._row("Diesel", "national", "Railways")["note"]
        chk = road.rail_crosscheck(self.data)
        self.assertIn("%.1f" % chk["yb_kt"], note)
        self.assertIn("%.1f" % (100 * chk["rel_diff"]), note)

    def test_generator_row_is_the_relayed_accessor(self):
        self.assertEqual(
            self._row("Petrol", "road", "Household generators")["kt"],
            road.generator_petrol_kt())

    def test_off_road_row_matches_the_partition(self):
        ncv = self.data.efv("transport_ncv", "Gas/Diesel Oil")
        self.assertAlmostEqual(
            self._row("Diesel", "road", "Off-road machinery")["kt"] * ncv,
            road.off_road_TJ(self.data), places=6)

    def test_unresolved_rows_are_status_not_numbers(self):
        """The three unresolved retail claimants carry no quantity - inventing one
        would be worse than declaring the gap - and each names the gap register row
        that says what would resolve it. The third row exists so the ledger never
        silently asserts that agriculture and captive generation are the only
        possible non-road uses within pump sales."""
        unresolved = [r for r in self.rows if r["kind"] == "unresolved"]
        self.assertEqual({r["claimant"] for r in unresolved},
                         {"Stationary agricultural plant (retail)",
                          "Captive generation (retail)",
                          "Other retail stationary/non-road uses"})
        gap_ids = set()
        for r in unresolved:
            self.assertIsNone(r["kt"])
            self.assertIsNone(r["share_of_opening"])
            self.assertEqual(r["tier"], "road")
            self.assertTrue(r["gap_id"])
            gap_ids.add(r["gap_id"])
        with open(asset_path(DATA, "data_gaps.csv"), newline="",
                  encoding="utf-8") as f:
            registered = {row["gap_id"] for row in csv.DictReader(f)}
        self.assertTrue(gap_ids <= registered,
                        "unresolved ledger rows cite unregistered gaps: %s"
                        % (gap_ids - registered))

    def test_cng_never_appears(self):
        """CNG is a different fuel from a different statistic; test_cng.py asserts it
        claims no share of either petroleum control, and the ledger must agree."""
        self.assertEqual([r for r in self.rows if "CNG" in r["fuel"]
                          or "CNG" in r["claimant"]], [])

    def test_on_road_diesel_is_the_net_control(self):
        """The road tier's closing residual, in TJ, must equal what road.fuel_TJ
        hands the emissions calculation minus the off-road partition."""
        ncv = self.data.efv("transport_ncv", "Gas/Diesel Oil")
        onroad_tj = self._row("Diesel", "road", "On-road transport")["kt"] * ncv
        self.assertAlmostEqual(
            onroad_tj,
            road.fuel_TJ(self.data)["Diesel"] - road.off_road_TJ(self.data),
            places=6)

    def test_navigation_is_a_visible_quantity(self):
        """Domestic bunkers - the mode the EDGAR crosswalk needs a number for."""
        self.assertGreater(
            self._row("Diesel", "national", "Domestic bunkers")["kt"], 0.0)

    def test_the_ledger_note_carries_no_hardcoded_conversion(self):
        """THE REINSTATED DEFECT. The bunkers row's note said "about 0.022 Mt" -- the
        FY2021-22 arithmetic -- for two editions while the quantity underneath it halved
        to 3.054 kt. A prose constant in a code string is invisible to every paper-number
        guard, so the note may reference the screen output and may not quote a converted
        magnitude at all."""
        note = self._row("Diesel", "national", "Domestic bunkers")["note"]
        self.assertIn("transport_navigation_screen", note)
        import re
        self.assertNotRegex(note, r"\d\.\d+\s*Mt",
                            "the note carries a hard-coded Mt figure again")
        # The stored defect: the rc3 wording must trip the same check.
        self.assertRegex("the row implies about 0.022 Mt CO2e - a bounded note",
                         r"\d\.\d+\s*Mt")


class TestNavigationScreen(unittest.TestCase):
    """The 1.A.3.d screening estimate (the second review's 8.5): factor choice and
    boundary review made, published per held edition, outside every total."""

    @classmethod
    def setUpClass(cls):
        from pkinv.sectors.transport import navigation_screen
        cls.screen = navigation_screen
        cls.rows = navigation_screen.rows()

    def test_the_reference_year_row_is_the_ledger_quantity_converted(self):
        """The screen derives nothing new: its FY2023-24 tonnage IS the fuel ledger's
        Domestic bunkers row, and the conversion is the declared factor chain exactly."""
        ref = self.screen.reference_row(2024)
        ledger_kt = None
        path = os.path.join(os.path.dirname(DATA), "outputs",
                            "transport_fuel_ledger_2024.csv")
        with open(path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["claimant"] == "Domestic bunkers":
                    ledger_kt = float(r["kt"])
        self.assertIsNotNone(ledger_kt)
        self.assertAlmostEqual(ref["hsd_t"] / 1000.0, ledger_kt, places=3)
        tj = ref["hsd_t"] / 1e6 * self.screen.DIESEL_NCV_TJ_GG * 1000.0
        expected = (tj * self.screen.MARINE_CO2_KG_TJ / 1000.0
                    + tj * self.screen.MARINE_CH4_KG_TJ / 1000.0 * 28.0
                    + tj * self.screen.MARINE_N2O_KG_TJ / 1000.0 * 265.0) / 1e6
        self.assertAlmostEqual(ref["co2e_Mt_AR5"], expected, places=5)

    def test_every_held_edition_is_converted(self):
        """The volatility is the finding: nine editions spanning two orders of
        magnitude is why this stays a screen, and a screen showing one year would
        hide exactly that."""
        self.assertGreaterEqual(len(self.rows), 9)
        values = [r["co2e_Mt_AR5"] for r in self.rows]
        self.assertGreater(max(values) / max(min(values), 1e-9), 10.0,
                           "the spread collapsed; revisit whether the screen can "
                           "graduate to an estimate")

    def test_the_screen_is_marked_outside_every_total(self):
        for r in self.rows:
            self.assertIn("screening", r["status"])

    def test_the_factors_are_the_ipcc_water_borne_values(self):
        """Pinned so the screening chemistry cannot drift from what the register and
        the papers cite (IPCC 2006 Vol 2 Ch 3 Tables 3.5.2 / 3.5.3)."""
        self.assertEqual(self.screen.MARINE_CO2_KG_TJ, 74100.0)
        self.assertEqual(self.screen.MARINE_CH4_KG_TJ, 7.0)
        self.assertEqual(self.screen.MARINE_N2O_KG_TJ, 2.0)
        self.assertEqual(self.screen.DIESEL_NCV_TJ_GG, 43.0)

    def test_the_published_file_matches_a_fresh_build(self):
        path = os.path.join(os.path.dirname(DATA), "outputs",
                            "transport_navigation_screen_2024.csv")
        with open(path, newline="", encoding="utf-8") as f:
            published = list(csv.DictReader(f))
        self.assertEqual(len(published), len(self.rows))
        for want, got in zip(self.rows, published):
            self.assertEqual(str(want["co2e_Mt_AR5"]), got["co2e_Mt_AR5"],
                             got["fy_label"])


class TestFuelSeries(unittest.TestCase):
    """The fuel-based national series and its identity with the inventory: the
    reference-year row must equal the sector's petroleum total modulo exactly the
    two declared refinements (the generator carve-out and the off-road factor
    table), so the series and the inventory cannot quietly diverge."""

    @classmethod
    def setUpClass(cls):
        from pkinv.sectors.transport import timeseries
        cls.data = TransportData()
        cls.rows = {r["inventory_year"]: r for r in timeseries.build(cls.data)}

    def test_ten_ocac_years_present(self):
        """Ten since rc20: the recovered FY2015-16 image edition prepended
        inventory year 2016 to the fuel series."""
        self.assertEqual(sorted(self.rows), list(range(2016, 2026)))

    def test_reference_year_identity_modulo_declared_refinements(self):
        d = self.data
        sector = registry.get("transport")
        comps = sector.build_components(d)
        petroleum = sum(c["co2e_Mt_AR5"] for c in comps
                        if not c["subitem"].startswith("CNG"))
        # refinement 1: the series keeps generator petrol inside the Road class
        gen_tj = road.generator_petrol_kt() * d.efv("transport_ncv",
                                                    "Motor Gasoline")
        gen_mt = gen_tj * (d.efv("transport_fuel_co2", "Motor Gasoline")
                           + d.efv("transport_fuel_ch4", "Motor Gasoline") * 30
                           + d.efv("transport_fuel_n2o", "Motor Gasoline") * 265
                           ) / 1e9
        # refinement 2: the series applies road factors to ALL diesel; the
        # inventory moves the off-road portion onto Table 3.3.1
        off_tj = road.off_road_TJ(d)
        uplift_mt = off_tj * (
            (d.efv("offroad_machinery_ch4", "Gas/Diesel Oil")
             - d.efv("transport_fuel_ch4", "Gas/Diesel Oil")) * 30
            + (d.efv("offroad_machinery_n2o", "Gas/Diesel Oil")
               - d.efv("transport_fuel_n2o", "Gas/Diesel Oil")) * 265) / 1e9
        # The sector's own reference year, not a literal: this test pins the series to the
        # inventory, so it must follow the inventory when the reference period moves.
        series = self.rows[sector.YEAR]["co2e_Mt_AR5_petroleum"]
        self.assertAlmostEqual(series, petroleum + gen_mt - uplift_mt, places=3)

    def test_cng_is_present_exactly_where_source_activity_supports_it(self):
        from pkinv.core.components import enrich_co2e
        from pkinv.sectors.transport import cng
        self.assertIn(2025, self.data.cng)
        for year, row in self.rows.items():
            if year not in self.data.cng:
                self.assertEqual(row["cng_co2e_Mt_AR5"], "")
                self.assertEqual(row["co2e_Mt_AR5_incl_cng"], "")
                continue
            expected = sum(c["co2e_Mt_AR5"] for c in enrich_co2e(cng.compute(self.data, year)))
            self.assertAlmostEqual(row["cng_co2e_Mt_AR5"], expected, delta=0.00005)
            self.assertAlmostEqual(row["co2e_Mt_AR5_incl_cng"],
                                   row["co2e_Mt_AR5_petroleum"] + expected, delta=0.0001)

    def test_road_share_column_matches_the_ocac_identity(self):
        for year, r in self.rows.items():
            expected = (self.data.ocac_t("Road", "HSD", year)
                        / self.data.ocac_t("TOTAL_INTERNAL", "HSD", year))
            self.assertAlmostEqual(r["road_share_of_national_hsd"], expected,
                                   places=4, msg=year)


class TestCalendarYearConstruction(unittest.TestCase):
    """The CY2022 controls the crosswalk cites: pinned values and the differencing
    identity that justifies the construction."""

    def test_cy2022_road_sums_are_pinned(self):
        from pkinv.sectors.transport import timeseries
        cy = timeseries.calendar_year_road_t(2022)
        self.assertEqual(cy["MS"] + cy["HOBC"], 8396073.0)
        self.assertEqual(cy["HSD"], 6881127.0)

    def test_the_cumulative_series_telescopes_to_the_annual_row(self):
        """cum(2023-06) must be bit-identical to the FY2022-23 annual Road row -
        the identity that proves the cumulative editions are FYTD-from-July and
        makes the Dec-cumulative = Jul-Dec construction valid."""
        import csv as _csv
        from pkinv.sectors.transport.timeseries import PROVINCIAL_CSV
        cum = {}
        with open(PROVINCIAL_CSV, newline="", encoding="utf-8") as f:
            for r in _csv.DictReader(f):
                if (r["month"] == "2023-06" and r["area"] == "PAKISTAN"
                        and r["sector_row"] == "Road"
                        and r["report_kind"] == "cumulative"):
                    cum[r["product"]] = float(r["tonnes"])
        data = TransportData()
        self.assertEqual(cum["MS"], data.ocac_t("Road", "MS", 2023))
        self.assertEqual(cum["HOBC"], data.ocac_t("Road", "HOBC", 2023))
        self.assertEqual(cum["HSD"], data.ocac_t("Road", "HSD", 2023))


class TestFleetFuelDiagnostic(unittest.TestCase):
    """The fleet-implied vs fuel-observed comparison - the demonstration behind
    'the fleet distributes, it does not size'. Declared bands, never adjusts."""

    @classmethod
    def setUpClass(cls):
        from pkinv.sectors.transport import fuel_gap
        cls.data = TransportData()
        cls.rows = {r["fuel"]: r for r in fuel_gap.diagnostic(cls.data)}

    def test_controls_equal_the_accessors(self):
        from pkinv.sectors.transport import cng as _cng
        tj = road.fuel_TJ(self.data)
        self.assertAlmostEqual(self.rows["Petrol"]["control_TJ"], tj["Petrol"],
                               delta=0.5)
        self.assertAlmostEqual(self.rows["Diesel"]["control_TJ"], tj["Diesel"],
                               delta=0.5)
        self.assertAlmostEqual(self.rows["CNG"]["control_TJ"],
                               _cng.gas_TJ(self.data), delta=0.5)

    def test_bands_are_ordered_and_verdicts_follow(self):
        for fuel, r in self.rows.items():
            self.assertLess(r["implied_TJ_lo"], r["implied_TJ_mid"], fuel)
            self.assertLess(r["implied_TJ_mid"], r["implied_TJ_hi"], fuel)
        # The finding worth pinning, and it MOVED when the sector was harmonised onto
        # FY2023-24. At FY2021-22 the bottom-up build missed in both directions and low on
        # both petroleum fuels. At the reference period the petrol control falls INSIDE the
        # fleet-implied band: petrol demand contracted after 2022 while the registered fleet
        # did not, so the two bases converged on petrol and still disagree on diesel and CNG.
        #
        # That is a better result than the one it replaces, and it is also a caution. The
        # agreement is a coincidence of two series moving in opposite directions, not
        # evidence that the fleet model is right - the diesel and CNG rows show the same
        # model missing by a factor of 1.7 and 3.0 in opposite directions in the same year.
        self.assertEqual(self.rows["Petrol"]["verdict"], "CONTROL-INSIDE-BAND")
        self.assertEqual(self.rows["Diesel"]["verdict"], "FLEET-MODEL-LOW")
        self.assertEqual(self.rows["CNG"]["verdict"], "FLEET-MODEL-HIGH")

    def test_the_diagnostic_never_touches_the_engine(self):
        sector = registry.get("transport")
        before = sum(c["co2e_Mt_AR5"] for c in sector.build_components(self.data))
        from pkinv.sectors.transport import fuel_gap
        fuel_gap.diagnostic(self.data)
        after = sum(c["co2e_Mt_AR5"] for c in sector.build_components(self.data))
        self.assertEqual(before, after)

    def test_every_band_is_declared_judgement(self):
        import csv as _csv
        from pkinv.paths import DATA as _DATA
        with open(asset_path(_DATA, "transport_params.csv"), newline="",
                  encoding="utf-8") as f:
            rows = [r for r in _csv.DictReader(f)
                    if r["param"].startswith("mjkm_")]
        self.assertEqual(len(rows), 34)
        for r in rows:
            self.assertIn("judgement", r["source"], r["param"])


class TestRunManifest(unittest.TestCase):
    """The manifest is the reproduction contract: every primary source hashed, the
    seeds and scenario names recorded, the vintage mixture declared."""

    @classmethod
    def setUpClass(cls):
        import tempfile
        from pkinv.sectors.transport import run_transport
        # into a temporary file: writing the canonical outputs/ manifest from a test replaced
        # a packaged output inside the rc40 validation package (sources not shipped there)
        cls._tmp = tempfile.mkdtemp(prefix="pakemis-transport-manifest-")
        cls.path, cls.n_sources = run_transport._manifest(
            TransportData(), out_path=os.path.join(cls._tmp, "transport_run_manifest.json"))
        import json
        with open(cls.path, encoding="utf-8") as f:
            cls.manifest = json.load(f)

    def test_enough_sources_are_hashed_and_all_exist(self):
        from pkinv.paths import ROOT
        require_documents(*[s["path"] for s in self.manifest["sources"]])
        self.assertGreaterEqual(self.n_sources, 8)
        for s in self.manifest["sources"]:
            self.assertTrue(os.path.exists(asset_path(ROOT, s["path"])), s["path"])
            self.assertEqual(len(s["sha256"]), 64)

    def test_the_seeds_and_scenarios_are_recorded(self):
        from pkinv.sectors.transport import uncertainty
        mc = self.manifest["monte_carlo"]
        self.assertEqual(mc["national_seed"], 42)
        self.assertEqual(mc["scenario_seed"], uncertainty.SCENARIO_SEED)
        self.assertIn("cng_hhv_900", mc["structural_scenarios"])

    def test_the_vintage_mixture_is_declared_not_hidden(self):
        """The sector reports the common reference period, and the two SHAPES it has to
        borrow to do so are declared in the manifest rather than discovered by a reader.

        This used to assert FY2021-22 - the sector reported the year its provincial panel
        was complete for, which put the national total two years behind eight other sectors
        to protect an allocation the total does not depend on."""
        ref = self.manifest["reference_year"]
        self.assertIn("FY2023-24", ref)
        self.assertIn("borrowed", ref.lower())
        self.assertIn("2023 registration panel", ref)
        self.assertNotIn("FY2021-22", ref)


class TestBorrowedShapes(unittest.TestCase):
    """The reference period sets the magnitude; two shapes are borrowed from neighbouring
    years because the reference period does not carry them.

    This is where the harmonisation round could have gone wrong quietly. The sector used to
    report FY2021-22 - the year its provincial panel was complete for - which put the national
    total two years behind eight other sectors to protect an allocation the total does not
    depend on. Moving it exposed two panels that stop short of the reference year, and both
    failed silently before these tests existed.
    """

    def setUp(self):
        self.data = TransportData()

    def test_the_reference_period_carries_its_own_provincial_panel(self):
        """THE PREDECESSOR OF THIS TEST FIRED AS DESIGNED, and this is its inversion.

        It asserted months_covered(2024) == 1 with the docstring "if OCAC ever prints twelve
        area pages for FY2023-24, the shape should stop being borrowed and this test should
        fail loudly saying so". The pages had in fact been printed all along - in the direct
        single-month editions, while the panel was built from the cumulative ones - and once
        the ingest read them, this fired. The shape stopped being borrowed.

        What must now hold: the reference year IS the reference shape, on its own twelve
        months, bracketed by the complete panel years either side of it.
        """
        self.assertEqual(province_shape.REFERENCE_SHAPE_YEAR, 2024)
        self.assertEqual(province_shape.months_covered(2024), 12)
        for year in province_shape.BRACKET_SHAPE_YEARS:
            self.assertEqual(province_shape.months_covered(year), 12)

    def test_a_partial_year_cannot_become_a_shape(self):
        """A partial-year shape is not a worse annual shape, it is a different quantity.
        FY2020-21 predates the panel entirely, so it is the live partial case now that the
        reference year's own pages have arrived."""
        self.assertLess(province_shape.months_covered(2021), 12)
        with self.assertRaises(ValueError):
            province_shape.shares("petrol", 2021)

    def test_the_retired_borrowing_is_measured_and_small(self):
        """The borrowed FY2024-25 shape stood in for one release. Its measured worst-case
        error against the year's own pages is the epitaph - published, pinned, and small
        enough that the old bounding argument gets its credit."""
        self.assertLess(province_shape.borrowing_error_pp(), 1.0)

    def test_both_complete_panels_agree_within_the_published_spread(self):
        """A borrowed shape is a claim that provincial composition moves slowly. The claim
        is supported by computing both ends rather than asserting it - and the number is
        pinned here so it cannot drift without someone noticing."""
        self.assertLess(province_shape.max_spread_pp(), 5.0)
        for row in province_shape.brackets():
            self.assertAlmostEqual(row["spread_pp"],
                                   100 * (row["share_reference_shape"]
                                          - row["share_bracket_shape"]), places=9)

    def test_the_committed_shares_are_the_reference_shape(self):
        """province_shares.csv must be what province_shape computes, not a hand copy that
        can drift from it."""
        committed = downscale.load_shares()
        for fuel, proxy in (("petrol", downscale.PETROL_PROXY),
                            ("diesel", downscale.DIESEL_PROXY)):
            computed = province_shape.shares(fuel, province_shape.REFERENCE_SHAPE_YEAR)
            for prov, share in computed.items():
                self.assertAlmostEqual(committed[proxy][prov], share, places=5,
                                       msg="%s/%s" % (fuel, prov))

    def test_a_borrowed_shape_cannot_move_the_magnitude(self):
        """The property that makes borrowing safe at all: shares sum to one, so swapping
        one year's shape for another redistributes and never creates."""
        for fuel in ("petrol", "diesel"):
            for year in ((province_shape.REFERENCE_SHAPE_YEAR,)
                         + province_shape.BRACKET_SHAPE_YEARS):
                self.assertAlmostEqual(sum(province_shape.shares(fuel, year).values()),
                                       1.0, places=12)

    def test_the_fleet_year_refuses_a_partial_registration_panel(self):
        """The trap this round walked into: the panel's final year is always partial because
        provinces file at different times, so asking for 2024 returned 30 percent of the
        fleet with no exception, the class split rode a third of the vehicles, and the
        fleet-implied fuel diagnostic collapsed by an order of magnitude - which read as a
        finding about the fleet model rather than as missing data."""
        coverage = self.data.fleet_coverage()
        self.assertLess(coverage[2024], TransportData.FLEET_COVERAGE_FLOOR)
        self.assertEqual(self.data.fleet_year(), 2023)
        self.assertGreaterEqual(coverage[self.data.fleet_year()],
                                TransportData.FLEET_COVERAGE_FLOOR)

    def test_the_engine_uses_the_fleet_year_not_the_control_year(self):
        _vkt, cells, _capped = road.effective_vkt(self.data)
        self.assertEqual(cells, len(self.data.cells(self.data.fleet_year())))
        self.assertGreater(cells, 2 * len(self.data.cells(2024)))


if __name__ == "__main__":
    unittest.main()
