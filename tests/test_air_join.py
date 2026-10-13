"""The air-to-GHG join (Wave A of the air spatial lane): every pollutant row of the six
national sector layers names exactly one source stream, fail-closed, so the spatial lane can
inherit each row's stream's own allocation. Also pins that the transport per-fuel breakout
(the repair of the constant '4W1 Petrol CO2' anchor) moved NO national total: the per-fuel
rows are a regrouping of the same survival-weighted vehicle-kilometres."""

from pkinv.assets import asset_path
import csv
import os
import unittest

from pkinv.report import air_join

ROOT = os.path.join(os.path.dirname(__file__), "..")
FILES = {
    "residential": "outputs/residential_air_pollutants_2024.csv",
    "transport": "outputs/transport_air_pollutants_2024.csv",
    "waste": "outputs/waste_air_pollutants_2024.csv",
    "aviation": "outputs/aviation_air_pollutants_fy2023_24.csv",
    "power": "outputs/power_air_pollutants_fy2023_24.csv",
    "railways": "outputs/railways_air_pollutants_2024.csv",
}

# the shipped EMEP Tier 1 totals (kt, all processes): the layer's pins since the air
# program's Wave 2 factor refactor - the workbook diagnostic's totals are superseded
# and preserved only in the paper's old-vs-new comparison table
TRANSPORT_TOTALS = {"NOx": 172.117, "CO": 1430.395, "NMVOC": 535.064, "PM2.5": 8.233,
                    "PM10": 4.652, "SO2": 12.212, "NH3": 2.589, "BC": 2.001,
                    "TSP": 7.057}


def rows_of(sector):
    with open(asset_path(ROOT, FILES[sector]), encoding="utf-8") as f:
        return list(csv.DictReader(f))


class TestAirJoin(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = air_join.stream_index()

    def test_every_air_row_names_exactly_one_stream(self):
        for sector in FILES:
            for r in rows_of(sector):
                sid = air_join.stream_for(sector, r, self.index)
                self.assertTrue(sid.startswith(sector + "|"), "%s row %r -> %s" % (sector, r.get("subitem"), sid))

    def test_the_join_is_fail_closed(self):
        with self.assertRaises(KeyError):
            air_join.stream_for("transport", {"ghg_subitem": "not a stream", "subitem": "x"}, self.index)
        with self.assertRaises(KeyError):
            air_join.stream_for("power", {"category": "Electricity and heat production", "fuel": "Peat"}, self.index)

    def test_shipped_ghg_subitem_columns_are_present_and_filled(self):
        for sector in ("residential", "transport", "waste", "aviation"):
            for r in rows_of(sector):
                self.assertTrue(r.get("ghg_subitem"), "%s row %r ships no ghg_subitem" % (sector, r.get("subitem")))

    def test_transport_totals_are_the_tier1_pins(self):
        totals = {}
        for r in rows_of("transport"):
            totals[r["pollutant"]] = totals.get(r["pollutant"], 0.0) + float(r["emissions_kt"])
        self.assertEqual(set(totals), set(TRANSPORT_TOTALS))
        for p, want in TRANSPORT_TOTALS.items():
            self.assertAlmostEqual(totals[p], want, delta=0.005, msg=p)

    def test_transport_classes_anchor_their_own_fleets(self):
        # per-class anchors since the Tier 1 refactor: the diesel NOx of trucks rides
        # the truck fleet's stream, never the petrol car's (the original defect)
        for r in rows_of("transport"):
            want = "CNG CO2" if r["fuel"] == "CNG" else "%s %s CO2" % (r["ei_class"], r["fuel"])
            self.assertEqual(r["ghg_subitem"], want, r["subitem"])
        classes = {r["ei_class"] for r in rows_of("transport")}
        self.assertGreater(len(classes), 5, "the per-class grain collapsed")


if __name__ == "__main__":
    unittest.main()
