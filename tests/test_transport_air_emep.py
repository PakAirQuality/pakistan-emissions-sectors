"""The EMEP Tier 1 road-transport air layer (air program Wave 2).

The properties the refactor was asked for, each pinned: the factor basis is the
transcribed guidebook table (every cell block-scope re-checked in the transcription
register); modelled fuel EQUALS sold fuel per fuel per year (the OCAC reconciliation,
an identity by construction); SO2 is stoichiometry under the declared per-year sulfur
regime; BC exists as the f-BC fraction of exhaust PM2.5; the wear processes carry the
coarser strata and exhaust does NOT (exhaust PM is PM2.5 by the chapter's own
statement); a fleet cell without a declared bridge row RAISES; and the guidebook's own
absences (CNG-bus NH3, CNG sulfur) stay absent, never zero.

Run:  python3 -m unittest discover tests -p "test_transport_air_emep.py"
"""
import unittest

from pkinv.sectors.transport import air_pollutants as ap
from pkinv.sectors.transport import road
from pkinv.sectors.transport.data import TransportData


class TestTheTier1Layer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = TransportData()
        cls.rows = ap.compute(cls.data)

    def test_the_fuel_reconciles_to_the_ocac_control(self):
        fuel = ap.fuel_kt_by_class(self.data)
        petrol = sum(v for (c, f), v in fuel.items() if f == "Petrol")
        diesel = sum(v for (c, f), v in fuel.items() if f == "Diesel")
        want_p = road.road_control_kt(self.data, "Motor Gasoline") - road.generator_petrol_kt()
        want_d = road.road_control_kt(self.data, "Gas/Diesel Oil")
        # off-road keeps its energy share of the diesel; the on-road classes must sum
        # to the control NET of that share, never absorb it
        vkt, _c, _k = road.effective_vkt(self.data)
        off = road._shares(self.data, vkt).get((road.OFF_ROAD, "Diesel"), 0.0)
        self.assertAlmostEqual(petrol, want_p, places=6)
        self.assertAlmostEqual(diesel, want_d * (1.0 - off), places=6)

    def test_so2_is_stoichiometry_under_the_declared_regime(self):
        ppm = ap.sulfur_ppm(None)
        fuel = ap.fuel_kt_by_class(self.data)
        want = sum(2.0 * ppm[f][0] / 1e6 * kt for (c, f), kt in fuel.items()
                   if f in ppm)
        got = sum(r["emissions_kt"] for r in self.rows if r["pollutant"] == "SO2")
        self.assertAlmostEqual(got, want, places=9)

    def test_an_undeclared_sulfur_year_raises(self):
        with self.assertRaises(KeyError):
            ap.sulfur_ppm(2010)

    def test_bc_is_the_declared_fraction_of_exhaust_pm25(self):
        ef = ap.factors()
        bridge = ap.class_map()
        pm = {(r["ei_class"], r["fuel"]): r["emissions_kt"] for r in self.rows
              if r["pollutant"] == "PM2.5" and r["process"] == "exhaust"}
        bc_rows = [r for r in self.rows if r["pollutant"] == "BC"]
        self.assertTrue(bc_rows)
        for r in bc_rows:
            cat, efuel, _n = bridge[(r["ei_class"], r["fuel"])]
            frac = ef[("bc_fraction", cat, efuel, "BC")][0]
            self.assertAlmostEqual(r["emissions_kt"],
                                   pm[(r["ei_class"], r["fuel"])] * frac, places=12)

    def test_exhaust_carries_no_coarse_strata_and_wear_carries_them(self):
        for r in self.rows:
            if r["process"] == "exhaust":
                self.assertNotIn(r["pollutant"], ("PM10", "TSP"), r["subitem"])
        wear_pols = {r["pollutant"] for r in self.rows
                     if r["process"] in ("tyre_brake_wear", "road_wear")}
        self.assertEqual(wear_pols, {"TSP", "PM10", "PM2.5"})

    def test_the_guidebooks_absences_stay_absent(self):
        cng = [(r["process"], r["pollutant"]) for r in self.rows if r["fuel"] == "CNG"]
        self.assertNotIn(("exhaust", "SO2"), cng)          # desulfurised pipeline gas
        hdv_cng = [(r["process"], r["pollutant"]) for r in self.rows
                   if r["fuel"] == "CNG" and r["ei_class"] in ("BUS", "HDV")]
        self.assertNotIn(("exhaust", "NH3"), hdv_cng)      # the table's own N/A

    def test_an_unmapped_fleet_cell_raises(self):
        with self.assertRaises(KeyError):
            ap.class_map()[("TRACTOR", "Diesel")]

    def test_evaporative_rides_petrol_counts_only(self):
        evap = [r for r in self.rows if r["process"] == "evaporative"]
        self.assertTrue(evap)
        for r in evap:
            self.assertEqual(r["fuel"], "Petrol")
            self.assertEqual(r["pollutant"], "NMVOC")

    def test_the_early_window_burns_its_own_sulfur(self):
        so2_2016 = sum(r["emissions_kt"] for r in ap.compute(self.data, 2016)
                       if r["pollutant"] == "SO2")
        so2_2024 = sum(r["emissions_kt"] for r in self.rows
                       if r["pollutant"] == "SO2")
        self.assertGreater(so2_2016, 3 * so2_2024,
                           "FY2015-16 lost its 0.5 percent diesel sulfur")

    def test_every_row_names_its_own_class_stream(self):
        from pkinv.report import air_join
        index = air_join.stream_index()
        for r in self.rows:
            sid = air_join.stream_for("transport", r, index)
            self.assertTrue(sid.startswith("transport|"), r["subitem"])


if __name__ == "__main__":
    unittest.main()
