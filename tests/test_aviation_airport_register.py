"""The committed airport register keeps its resolved coordinates.

rc34 found the controls ingest (scripts/build_aviation_anchor_controls.py)
regenerates data/activity/aviation/airports.csv from OurAirports and
DISCARDS the hand-resolved OpenStreetMap centroid for Islamkot (OPZZ), leaving
the row UNRESOLVED - a whole build's spatial products then moved (the grid
cube reads this file) with no inventory number changing. The one airport with
no coordinate in any held source is Juzzak, logged negative as
aviation-juzzak-coords-01; every other commercial-service airport must carry
one, and a builder that drops a resolution fails here rather than in a
release's ADM2 view.
"""

from pkinv.assets import asset_path
import csv
import os
import unittest
from pkinv.core.io import read_rows
from _support import ROOT

REGISTER = asset_path(ROOT, "data", "activity", "aviation", "airports.csv")
DECLARED_UNRESOLVED = {"Juzzak"}


class TestTheAirportRegister(unittest.TestCase):
    def _rows(self):
        return read_rows(REGISTER, comments=False)

    def test_every_commercial_airport_but_juzzak_has_a_coordinate(self):
        missing = {r["airport"] for r in self._rows()
                   if r["commercial_service_fy2023_24"] == "yes"
                   and not r["latitude_deg"].strip()}
        self.assertEqual(missing, DECLARED_UNRESOLVED,
                         "the register lost a resolved coordinate (or gained one "
                         "without retiring the declared negative): %s" % sorted(missing))

    def test_islamkot_keeps_its_osm_resolution(self):
        row = next(r for r in self._rows() if r["airport_icao"] == "OPZZ")
        self.assertTrue(row["latitude_deg"].strip(), "Islamkot is UNRESOLVED again")
        self.assertIn("OpenStreetMap", row["coordinate_source"])

    def test_no_row_is_marked_unresolved_without_being_declared(self):
        unresolved = {r["airport"] for r in self._rows()
                      if r["coordinate_source"].strip().upper() == "UNRESOLVED"}
        self.assertLessEqual(unresolved, DECLARED_UNRESOLVED, sorted(unresolved))


if __name__ == "__main__":
    unittest.main()
