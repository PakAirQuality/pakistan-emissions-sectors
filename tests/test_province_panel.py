"""Grid power is split between provinces by each year's own stations.

WHY THIS EXISTS. Through rc65 each grid fuel carried one provincial share vector, measured on
FY2023-24, and coal and gas rode it in all nine fiscal years. The manuscript said so, gave the
size of the worst province-year (11.6 Mt CO2e, Sindh, FY2020-21) and added that a per-year
split was possible from the same records. A review asked the obvious question.
pkinv.sectors.power.province_panel is the split. These tests hold it to four things.

1. IT IS A SPLIT AND NOTHING ELSE. Shares sum to one over the five provinces in every cell.
   The stations supply proportions; the national total of every fuel comes from elsewhere and
   cannot move here.
2. THE REFERENCE YEAR IS THE COMMITTED ROW. data/province_shares.csv is what the engine reads
   for FY2023-24 and for every caller with no period. The panel must reproduce those rows, so
   the committed table cannot outlive its derivation, and the reference year's products
   cannot drift.
3. A BORROWED CELL SAYS WHY. Where the station record gives out, the engine keeps the
   reference vector, and the panel's record names the reason. A fallback with no reason is the
   state this work removed.
4. THE EVIDENCE BEHIND EACH JUDGEMENT IS RE-RUN. The bagasse plants this module places against
   Table 5 are tested against the district polygons here, and the stations it places by name
   are checked to exist in the fuel record, so neither list can outlive what justified it.

WHAT IT DOES NOT TEST. That NEPRA's printed quantities are right. Sahiwal's FY2021-22 tonnage
is twice its usual intensity and is used as booked; the panel flags it and so does this file.
"""
import csv
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.assets import asset_path                                     # noqa: E402
from pkinv.core.geography import PROVINCES                              # noqa: E402
from pkinv.sectors.power import downscale, province_panel as panel     # noqa: E402

YEARS = range(panel.FIRST_YEAR, panel.LAST_YEAR + 1)


class _Period:
    def __init__(self, fiscal_start_year):
        self.fiscal_start_year = fiscal_start_year


def _committed():
    with open(asset_path(ROOT, "data", "province_shares.csv"), encoding="utf-8",
              newline="") as handle:
        return {r["proxy"]: {p: float(r[p]) for p in PROVINCES}
                for r in csv.DictReader(handle)}


class TestEveryCellIsASplit(unittest.TestCase):
    def test_shares_sum_to_one_in_every_cell(self):
        for stream in panel.STREAMS:
            for year in YEARS:
                found = panel.record(stream, year)
                if found["shares"] is None:
                    continue
                self.assertAlmostEqual(sum(found["shares"].values()), 1.0, places=9,
                                       msg="%s FY%d" % (stream, year))
                self.assertEqual(set(found["shares"]), set(PROVINCES))
                self.assertTrue(all(v >= 0 for v in found["shares"].values()))

    def test_every_cell_states_its_basis_or_its_reason(self):
        """THE COMPLETION CRITERION, as a test: a cell either has an own-year split with a
        stated basis, or keeps the reference vector for a stated reason. Never neither."""
        silent = []
        for stream in panel.STREAMS:
            for year in YEARS:
                found = panel.record(stream, year)
                own = found["shares"] is not None and not found["fallback"]
                if own and not found["basis"]:
                    silent.append("%s FY%d: a split with no basis" % (stream, year))
                if not own and not found["fallback"]:
                    silent.append("%s FY%d: borrowed with no reason" % (stream, year))
        self.assertFalse(silent, "\n  ".join(silent))

    def test_no_station_is_left_unplaced(self):
        """A station the panel cannot place is energy missing from the split. Coal's small
        unplaced residuals are flagged by the panel; a whole station must never be."""
        lost = []
        for stream in panel.STREAMS:
            for year in YEARS:
                for flag in panel.record(stream, year)["flags"]:
                    if "is not placed" in flag and "booked energy" not in flag:
                        lost.append("%s FY%d: %s" % (stream, year, flag))
        self.assertFalse(lost, "\n  ".join(lost))


class TestTheReferenceYearIsTheCommittedRow(unittest.TestCase):
    def test_the_panel_reproduces_the_committed_table(self):
        committed = _committed()
        for stream in panel.STREAMS:
            found = panel.record(stream, panel.REFERENCE_YEAR)
            self.assertIsNotNone(found["shares"], stream)
            for province in PROVINCES:
                self.assertAlmostEqual(
                    found["shares"][province], committed[stream][province], delta=1.5e-5,
                    msg="%s %s: data/province_shares.csv no longer says what the stations "
                        "of FY2023-24 say" % (stream, province))

    def test_no_period_and_the_reference_period_give_the_committed_table(self):
        committed = _committed()
        for period in (None, _Period(panel.REFERENCE_YEAR), _Period(None)):
            shares = downscale.load_shares(period)
            for stream in panel.STREAMS:
                self.assertEqual(shares[stream], committed[stream], stream)

    def test_the_reference_year_returns_no_override(self):
        self.assertEqual(panel.province_shares(panel.REFERENCE_YEAR), {})


class TestTheSplitFollowsTheYear(unittest.TestCase):
    def test_coal_is_not_the_reference_vector_in_the_years_the_manuscript_named(self):
        """THE DEFECT, pinned from the other side. In FY2020-21 the stations put 47 percent of
        coal in Sindh and 28 percent in Balochistan (Hub's first full year); the borrowed
        vector said 89 and under 1."""
        coal = panel.record("power_coal", 2020)["shares"]
        self.assertAlmostEqual(coal["Sindh"], 0.473, delta=0.005)
        self.assertAlmostEqual(coal["Balochistan"], 0.280, delta=0.005)
        # and FY2017-18, when Sahiwal was most of the country's coal power
        self.assertGreater(panel.record("power_coal", 2017)["shares"]["Punjab"], 0.6)
        # FY2015-16: Lakhra, alone
        self.assertAlmostEqual(panel.record("power_coal", 2015)["shares"]["Sindh"], 1.0)

    def test_the_engine_applies_the_year(self):
        for year in (2015, 2017, 2020, 2022):
            shares = downscale.load_shares(_Period(year))
            for stream, vector in panel.province_shares(year).items():
                self.assertEqual(shares[stream], vector, "%s FY%d" % (stream, year))

    def test_furnace_oil_reaches_hub_and_jamshoro(self):
        """FY2020-21 to FY2022-23: the committed row booked every tonne to Punjab while the
        ledger shows furnace oil burned in Balochistan and Sindh."""
        for year in (2020, 2021, 2022):
            oil = panel.record("power_rfo", year)["shares"]
            self.assertGreater(oil["Balochistan"] + oil["Sindh"], 0.05, year)
            self.assertLess(oil["Punjab"], 0.95, year)

    def test_a_cell_under_the_coverage_floor_keeps_the_reference_vector(self):
        """THE POSITIVE CONTROL for the fallback: at least one real cell falls back, with the
        coverage that put it there, and the engine then serves the committed row for it."""
        fallen = [(s, y) for s in panel.STREAMS for y in YEARS
                  if panel.record(s, y)["fallback"] and panel.record(s, y)["shares"] is not None]
        self.assertTrue(fallen, "no cell falls back any more; replace this control")
        committed = _committed()
        for stream, year in fallen:
            found = panel.record(stream, year)
            self.assertLess(found["coverage"], panel.COVERAGE_FLOOR, (stream, year))
            self.assertNotIn(stream, panel.province_shares(year))
            self.assertEqual(downscale.load_shares(_Period(year))[stream], committed[stream])

    def test_gas_before_the_ledger_rests_on_fuel_not_generation(self):
        """The four years before FY2019-20 are read from printed fuel quantities. Generation
        stands in only for station-years the report gives no quantity for, and never for most
        of a year."""
        for year in range(panel.FIRST_YEAR, panel.LEDGER_FIRST_YEAR):
            found = panel.record("power_gas", year)
            self.assertFalse(found["fallback"], year)
            self.assertLess(found["derived_share"], 0.25, year)
            self.assertGreater(found["coverage"], 0.75, year)


class TestTheSplitAndThePlacementAgree(unittest.TestCase):
    def test_no_station_sits_in_a_province_the_split_gives_nothing(self):
        """THE SILENT DROP, closed. The cube places a fuel's stations province by province and
        skips a province whose share is zero (pkinv.report.grid_cube.grid_weight: `if share
        <= 0: continue`), stations and all, without an event. Under the fixed vector that
        skipped Hub and Jamshoro's furnace oil in FY2020-21 to FY2022-23: the stations were in
        the period's pool and Punjab had every tonne. With each year's split read from the same
        station records the placement uses, no pool may sit in a zero-share province, in any
        period, for any fuel. If this fails, mass is being placed in the wrong province and
        nothing else will say so."""
        from pkinv.report import grid_cube
        with open(asset_path(ROOT, "data", "periods.csv"), encoding="utf-8",
                  newline="") as handle:
            periods = [r["period_id"] for r in csv.DictReader(handle)]
        dropped = []
        for period_id in periods:
            period = grid_cube.period_keys(period_id)
            shares = downscale.load_shares(period)
            for profile, fuels in grid_cube.GRID_PROFILE_FUELS.items():
                if not fuels:
                    continue
                for province, points in grid_cube.grid_plant_points(fuels, period).items():
                    if points and shares[profile].get(province, 0.0) <= 0:
                        dropped.append("%s %s: %d station(s) in %s, which the split gives "
                                       "nothing" % (period_id, profile, len(points), province))
        self.assertFalse(dropped, "\n  ".join(dropped))


class TestTheJudgementsStillHaveTheirEvidence(unittest.TestCase):
    def test_the_bagasse_plants_are_where_their_coordinates_are(self):
        """Three plants are placed against or without NEPRA's Table 5. Each placement rests
        on the district polygon its coordinate falls in; this repeats the test."""
        try:
            import json
            from shapely.geometry import Point, shape
        except ImportError:
            self.skipTest("shapely is not installed")
        path = asset_path(ROOT, "data", "gis", "PAK_ADM2.geojson")
        if not os.path.exists(path):
            self.skipTest("the district polygons are not in this checkout")
        with open(path, encoding="utf-8") as handle:
            districts = [(f["properties"]["shapeName"], shape(f["geometry"]))
                         for f in json.load(handle)["features"]]
        for plant, (_province, (lon, lat), district) in panel.BAGASSE_PLACEMENT.items():
            inside = [name for name, polygon in districts if polygon.contains(Point(lon, lat))]
            self.assertEqual(inside, [district], plant)

    def test_every_named_station_is_in_the_record(self):
        """A retired-station rule or an alias for a name no table prints is dead weight that
        reads like evidence."""
        with open(panel.BACK_YEARS, encoding="utf-8", newline="") as handle:
            printed = {r["plant"] for r in csv.DictReader(
                line for line in handle if not line.startswith("#"))}
        from pkinv.sectors.power import fuel_reconciliation
        printed |= {r["plant"] for r in fuel_reconciliation.account_rows()}
        for name in list(panel.RETIRED) + list(panel.BACK_YEAR_ALIAS):
            self.assertIn(name, printed, "%s is in no station record" % name)

    def test_the_suspect_tonnage_is_flagged_not_fixed(self):
        flags = " ".join(panel.record("power_coal", 2021)["flags"])
        self.assertIn("Sahiwal", flags)

    def test_the_fuel_record_re_derives_from_the_held_report(self):
        """The four early years rest on scripts/ingest_nepra_plant_fuel_quantity.py. Its
        --check re-reads the held report; run here so the table cannot drift from it."""
        import shutil
        import subprocess
        from _support import require_documents
        require_documents("sources/Power Plants/NEPRA State of Industry Report 2020.pdf")
        if not shutil.which("pdftotext"):
            self.skipTest("pdftotext is not installed")
        done = subprocess.run(
            [sys.executable, os.path.join(ROOT, "scripts", "ingest_nepra_plant_fuel_quantity.py"),
             "--check"], capture_output=True, text=True, cwd=ROOT,
            env=dict(os.environ, PYTHONPATH=os.path.join(ROOT, "src")))
        self.assertEqual(done.returncode, 0, done.stdout[-600:] + done.stderr[-300:])
        self.assertIn("checked: ", done.stdout)


if __name__ == "__main__":
    unittest.main()
