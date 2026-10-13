"""CNG in road transport (1A3b) - the sector's second activity basis.

CNG was missing from this sector entirely, and the paper called it "a data-availability problem
rather than a methodological one". It was neither: OGRA's State of the Regulated Petroleum
Industry reports gas by sector, and this inventory already read that document for the
residential control total, the LPG total, the kerosene total and the captive-power series. The
CNG figure was one row of a table four other numbers came from.

The stream is now estimated from that row. These tests cover what is particular to it: that it
does not double-count against the three other OGRA rows this inventory takes, that its heating
value matches the captive category's for the same gas, and that its magnitude comes from the
metered gas rather than from the fleet model.

Run:  python3 -m unittest discover tests -p "test_cng.py"
"""

from pkinv.assets import asset_path
import csv
import os
import unittest

from pkinv.core.units import mmcfd_to_TJ
from pkinv.paths import DATA
from pkinv.sectors.power.data import PowerData
from pkinv.sectors.transport import cng, cng_gap, engine, road
from pkinv.sectors.transport.data import TransportData
from pkinv.core.io import read_rows


def _load(*parts):
    return read_rows(asset_path(DATA, *parts), comments=False)


class TestActivity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = TransportData()

    def test_the_reference_year_matches_the_source(self):
        """FY2021-22, OGRA Table 6.1. The sector's year N is fiscal year N-1 to N, as in
        railways and residential."""
        self.assertEqual(self.data.cng_mmcfd(2022), 68.0)

    def test_the_two_ogra_tables_agree_for_the_year_they_share(self):
        """The only independent check the source offers on itself: Table 3.31 splits sector gas
        by utility (SNGPL 59 + SSGCL 3) and Table 6.1 gives the CNG sector's own series. Both
        say 62 MMCFD for FY2023-24."""
        self.assertEqual(self.data.cng_mmcfd(2024), 62.0)
        row = next(r for r in _load("activity", "transport", "cng_gas.csv")
                   if r["fiscal_year"] == "2024")
        self.assertIn("3.31", row["source"])
        self.assertIn("6.1", row["source"])

    def test_a_missing_year_raises(self):
        """Indexed, not .get(): silently dropping the stream would shrink the sector without
        saying so."""
        with self.assertRaises(KeyError):
            self.data.cng_mmcfd(1999)

    def test_the_series_collapses(self):
        """325 MMCFD in FY2011-12 to 62 in FY2023-24. The steepest decline of any activity
        series in this inventory, and the reason the sector's CNG share keeps falling."""
        years = self.data.cng_years()
        self.assertEqual(self.data.cng_mmcfd(min(years)), 325.0)
        self.assertLess(self.data.cng_mmcfd(max(years)) / self.data.cng_mmcfd(min(years)), 0.25)


class TestNoDoubleCount(unittest.TestCase):
    """OGRA Table 3.31 partitions national gas. This inventory takes three of its rows into
    three different IPCC categories, and they must be three DIFFERENT rows."""

    def test_the_three_ogra_rows_are_distinct(self):
        transport = TransportData().cng_mmcfd(2024)                 # Transport (CNG) = 62
        captive = PowerData().captive_total_mmcfd()                 # Captive Power
        residential = next(float(r["quantity"]) for r in
                           _load("activity", "residential", "fuel_supply.csv")
                           if r["fuel"] == "Natural Gas")           # Residential = 821
        self.assertEqual(len({transport, captive, residential}), 3,
                         "two sectors are reading the same OGRA row: %s"
                         % [transport, captive, residential])

    def test_the_petroleum_control_total_has_no_gas_in_it(self):
        """CNG is a different fuel from a different statistic. If it ever appeared in the
        petroleum control total, the sector would count the same energy twice."""
        self.assertNotIn("CNG", road.fuel_TJ(TransportData()))


class TestSharedGasAssumption(unittest.TestCase):
    """The same gas, assumed the same way, in both sectors that burn it as a volume."""

    def test_the_heating_value_matches_the_captive_category(self):
        """Pakistani pipeline gas is one gas. An inventory that assumed 1,000 Btu/scf in
        transport and something else in captive power would be internally inconsistent in a
        way no output would reveal."""
        t, p = TransportData(), PowerData()
        self.assertEqual(t.p("cng_hhv_btu_per_scf"), p.p("captive_hhv_btu_per_scf"))
        self.assertEqual(t.pu("cng_hhv_btu_per_scf"), p.pu("captive_hhv_btu_per_scf"))

    def test_the_gross_to_net_ratio_matches_too(self):
        t, p = TransportData(), PowerData()
        self.assertEqual(t.p("cng_gross_to_net"), p.p("captive_gross_to_net"))

    def test_the_conversion_is_the_shared_one(self):
        """Both sectors go through pkinv.core.units. The Btu constant was written out
        separately three times before that module existed and one copy was wrong by a factor
        of a thousand."""
        d = TransportData()
        self.assertAlmostEqual(
            cng.gas_TJ(d),
            mmcfd_to_TJ(d.cng_mmcfd(), d.p("cng_hhv_btu_per_scf"), d.p("cng_gross_to_net")),
            places=9)
        self.assertNotIn("1055.05585262", open(cng.__file__, encoding="utf-8").read())


class TestStreams(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = TransportData()
        cls.comps = [c for c in engine.build_components(cls.data)
                     if c["subitem"].startswith("CNG")]

    def test_all_three_gases_are_reported(self):
        self.assertEqual({c["gas"] for c in self.comps}, {"CO2", "CH4", "N2O"})

    def test_methane_is_flagged_fossil(self):
        """Natural gas is fossil, so CH4 takes AR5 30 rather than the biogenic 28 - and it
        matters more here than anywhere else in the inventory, because CNG's methane factor is
        92 kg/TJ against diesel's 3.9. Unburnt methane slip dominates a gas engine's exhaust."""
        ch4 = [c for c in self.comps if c["gas"] == "CH4"]
        self.assertTrue(ch4)
        for c in ch4:
            self.assertTrue(c.get("fossil", False))
            self.assertAlmostEqual(c["co2e_Mt_AR5"], c["emissions_Gg"] * 30 / 1000.0,
                                   places=12)

    def test_the_methane_factor_is_far_above_the_liquid_fuels(self):
        d = self.data
        self.assertGreater(d.efv("transport_fuel_ch4", "Natural Gas"),
                           10 * d.efv("transport_fuel_ch4", "Gas/Diesel Oil"))

    def test_the_heating_value_sensitivity_moves_the_sector_a_little(self):
        """Published rather than buried, as the captive category does. A tenth of the CNG
        stream, two parts in a thousand of the sector."""
        base = sum(c["co2e_Mt_AR5"] for c in engine.build_components(self.data))
        low = sum(c["co2e_Mt_AR5"] for c in engine.build_components(self.data,
                                                                   cng_hhv_btu=900))
        self.assertLess(low, base)
        self.assertAlmostEqual(low / base, 0.9, delta=0.11)

    def test_cng_is_road_transport_not_its_own_category(self):
        """It is 1A3b. A separate category would misreport it and break the key-category
        analysis, however convenient it would be for presentation."""
        for c in self.comps:
            self.assertEqual(c["category"], "Road transport")


class TestMagnitudeComesFromGasNotTheFleet(unittest.TestCase):
    """The sector's central argument, applied to the one fuel where it can be tested."""

    def test_the_estimate_does_not_use_vehicle_kilometres(self):
        src = open(cng.__file__, encoding="utf-8").read()
        for forbidden in ("effective_vkt", "vkt_for", "stock_series"):
            self.assertNotIn(forbidden, src,
                             "CNG emissions have started riding the fleet model")

    def test_the_crosscheck_finds_the_fleet_model_high(self):
        """The result: metered gas over modelled CNG travel gives about 0.87 MJ/km, below any
        plausible value for a fleet seven-tenths three-wheelers. The disagreement is confined
        to what rides vehicle-kilometres - geography and air pollutants - because the emissions
        come from the gas."""
        s = cng_gap.summary(TransportData())
        self.assertEqual(s["verdict"], "FLEET-MODEL-HIGH")
        self.assertLess(s["mj_per_km"], cng_gap.PLAUSIBLE_MJ_PER_KM[0])


class TestProvincialProxy(unittest.TestCase):
    def test_cng_rides_its_own_vehicle_kilometres(self):
        """Not fuel sales. OGRA's metered gas is a national quantity, and 71 percent of
        CNG travel is three-wheelers, whose geography is not the petrol fleet's, so
        falling through to the fuel-sales proxy would allocate 1.4 Mt onto the wrong
        provinces at an unchanged national total. Petrol and diesel streams dispatch to
        their own fuel-sales rows."""
        from pkinv.sectors.transport import downscale
        self.assertEqual(downscale.proxy_for({"category": "Road transport",
                                              "subitem": "CNG CO2"}),
                         downscale.CNG_PROXY)
        self.assertEqual(downscale.proxy_for({"category": "Road transport",
                                              "subitem": "2W Petrol CO2"}),
                         downscale.PETROL_PROXY)
        self.assertEqual(downscale.proxy_for({"category": "Road transport",
                                              "subitem": "HDV Diesel CO2"}),
                         downscale.DIESEL_PROXY)

    def test_the_proxy_row_exists_and_sums_to_one(self):
        from pkinv.sectors.transport import downscale
        shares = downscale.load_shares()
        for proxy in (downscale.CNG_PROXY, downscale.PETROL_PROXY,
                      downscale.DIESEL_PROXY):
            self.assertAlmostEqual(sum(shares[proxy].values()), 1.0, places=5,
                                   msg=proxy)

    def test_the_cng_geography_differs_from_the_registration_diagnostic(self):
        """If the two vehicle-km-derived proxies agreed, the extra row would be
        pointless complexity. Compared against the registration diagnostic the CNG
        row was built beside - against the new fuel-sales rows the margin is small,
        which is expected: both lean on the same urban gas geography."""
        from pkinv.sectors.transport import downscale
        shares = downscale.load_shares()
        cng_kp = shares[downscale.CNG_PROXY]["Khyber Pakhtunkhwa"]
        reg_kp = shares[downscale.REGISTRATION_PROXY]["Khyber Pakhtunkhwa"]
        self.assertGreater(abs(cng_kp - reg_kp), 0.02)


if __name__ == "__main__":
    unittest.main()
