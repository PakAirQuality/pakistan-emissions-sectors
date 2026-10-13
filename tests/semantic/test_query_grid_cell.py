"""get_grid_cell had no test, and the release contract declares it a public function.

WHY THIS FILE EXISTS. The function is named in semantic/release_json.py's function list, so a
reader of the contract is entitled to call it, and until now nothing in the tree executed it.
That is how it came to hold a hardcoded epoch - date(2023, 7, 1) - which was right for the one
cube it had ever been pointed at and would have silently returned the wrong month for any
other. A lookup that answers confidently is the worst kind to leave unguarded, so what is
tested here is mostly the REFUSALS: outside the grid, outside the country, the period-named
second configuration outside its own year, and a historical month that does not exist.

rc67: the second configuration was S (the survey reading, "outside the year it was
surveyed") through rc66. The survey series is the reference now and the second cube is
configuration L, the ledger dung basis, which exists for FY2023-24 alone.
"""
import os
import unittest

import numpy as np

try:
    import netCDF4
except ImportError:                                       # pragma: no cover
    netCDF4 = None

from pkinv.paths import OUTPUTS
from pakemis_query import errors as E
from pakemis_query.functions import get_grid_cell
from pakemis_query.models import GridCellRequest

from semantic._golden import open_engine

ANNUAL = os.path.join(OUTPUTS, "pakemis_grid_0p05_annual_ref_fy2015_16_fy2023_24.nc")
MONTHLY = os.path.join(OUTPUTS, "pakemis_grid_0p05_monthly.nc")
LEDGER = os.path.join(OUTPUTS, "pakemis_grid_0p05_monthly_ledger.nc")
PATHS = {"REF_2023_24": MONTHLY, "L_2023_24": LEDGER, "ANNUAL": ANNUAL}


@unittest.skipIf(netCDF4 is None, "netCDF4 is not installed")
@unittest.skipUnless(os.path.exists(ANNUAL), "the annual cube has not been built")
class TestTheGridLookupAnswersAndRefuses(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.engine = open_engine()
        ds = netCDF4.Dataset(ANNUAL)
        try:
            lats, lons = ds.variables["lat"][:], ds.variables["lon"][:]
            fraction = np.asarray(ds.variables["pakistan_fraction"][:])
            # A CELL THAT IS IN THE BOX BUT NOT IN THE COUNTRY, found rather than hardcoded:
            # the bounding box of Pakistan contains a good deal of India, Afghanistan and sea,
            # and which cell is which is a property of the mask, not of my memory of the map.
            rows, cols = np.where(fraction <= 0.0)
            cls.outside = (float(lats[rows[0]]), float(lons[cols[0]]))
            inside_rows, inside_cols = np.where(fraction > 0.99)
            cls.inside = (float(lats[inside_rows[0]]), float(lons[inside_cols[0]]))
            cls.periods = [str(p) for p in ds.variables["period_id"][:]]
        finally:
            ds.close()

    def _req(self, **kw):
        base = dict(lat=self.inside[0], lon=self.inside[1], gas="CO2")
        base.update(kw)
        return GridCellRequest(**base)

    def test_a_historical_period_reads_the_annual_cube(self):
        env = get_grid_cell(self.engine, self._req(period_id="FY2015-16"), PATHS)
        self.assertEqual(list(env["context"]["periods"]), ["FY2015-16"])
        self.assertEqual(env["values"][0]["unit"], "Gg")
        self.assertEqual(env["values"][0]["spatial_view"], "all (the three views sum)")

    def test_the_default_is_the_three_views_summed_because_they_partition(self):
        """Selecting one view must not look like the whole cell.

        physical, origin and accounting are disjoint attributions, so the default has to be
        their sum - a default of "physical" would quietly return roughly two thirds of the
        cell's mass with a receipt saying it was the cell.
        """
        total = get_grid_cell(self.engine, self._req(period_id="FY2019-20"),
                              PATHS)["values"][0]["value"]
        parts = 0.0
        for view in ("physical", "origin", "accounting"):
            parts += get_grid_cell(
                self.engine, self._req(period_id="FY2019-20", spatial_view=view),
                PATHS)["values"][0]["value"]
        self.assertAlmostEqual(total, parts, places=4)

    def test_a_historical_month_is_refused_and_says_why(self):
        with self.assertRaises(E.GrainUnavailable) as caught:
            get_grid_cell(self.engine, self._req(period_id="FY2015-16", month="201507"), PATHS)
        self.assertIn("reference year", str(caught.exception))

    def test_configuration_l_is_refused_outside_its_reference_year(self):
        with self.assertRaises(E.NotEstimated) as caught:
            get_grid_cell(self.engine, self._req(period_id="FY2015-16",
                                                 configuration_id="L_2023_24"), PATHS)
        self.assertIn("FY2023-24", str(caught.exception))
        self.assertIn("L_2023_24", str(caught.exception))
        self.assertEqual(caught.exception.limitation_id,
                         "configuration_l_reference_year_only")

    def test_a_point_outside_the_grid_is_not_snapped_to_the_nearest_edge(self):
        """argmin always succeeds, which is the whole problem.

        Without a domain check a query for a point in the Bay of Bengal returns Pakistan's
        south-eastern corner cell, with a digest and four decimal places, and nothing in the
        envelope says it is not what was asked for.
        """
        with self.assertRaises(E.UnknownDimensionValue) as caught:
            get_grid_cell(self.engine, self._req(lat=10.0, lon=100.0, period_id="FY2019-20"),
                          PATHS)
        self.assertIn("outside the Pakistan grid domain", str(caught.exception))

    def test_a_cell_inside_the_box_but_outside_the_country_is_not_called_zero(self):
        lat, lon = self.outside
        with self.assertRaises(E.NotEstimated) as caught:
            get_grid_cell(self.engine, self._req(lat=lat, lon=lon, period_id="FY2019-20"),
                          PATHS)
        self.assertIn("outside Pakistan", str(caught.exception))

    def test_an_unknown_period_is_named_against_the_nine_that_exist(self):
        with self.assertRaises(E.UnknownDimensionValue) as caught:
            get_grid_cell(self.engine, self._req(period_id="FY2009-10"), PATHS)
        self.assertIn("FY2015-16", str(caught.exception))


@unittest.skipIf(netCDF4 is None, "netCDF4 is not installed")
@unittest.skipUnless(os.path.exists(MONTHLY), "the monthly cube has not been built")
class TestTheReferenceYearStillReads(unittest.TestCase):
    """The historical path must not have cost the path that already worked."""

    @classmethod
    def setUpClass(cls):
        cls.engine = open_engine()

    def test_a_reference_month_matches_the_file_read_directly(self):
        """The epoch is READ from the cube, so this test also pins that it was not guessed.

        The old code subtracted a literal date(2023, 7, 1). It agreed with the file, which is
        why nothing caught it. Comparing against a direct read of the same cell keeps the
        agreement checked rather than assumed.
        """
        ds = netCDF4.Dataset(MONTHLY)
        try:
            lats, lons = ds.variables["lat"][:], ds.variables["lon"][:]
            var = ds.variables["co2_Gg"]
            axis = [int(x) for x in ds.variables["time"][:]]
            # A CELL WITH MASS IN IT, found rather than picked: most of the grid is masked
            # (outside the country) or an honest zero, and comparing nan to nan would pass
            # while testing nothing.
            layer = np.ma.filled(var[axis.index(0), :, :], 0.0)
            i, j = [int(x) for x in np.unravel_index(int(np.argmax(layer)), layer.shape)]
            expected = float(var[axis.index(0), i, j])
            lat, lon = float(lats[i]), float(lons[j])
        finally:
            ds.close()
        env = get_grid_cell(self.engine, GridCellRequest(
            lat=lat, lon=lon, month="202307", gas="CO2"), PATHS)
        self.assertAlmostEqual(env["values"][0]["value"], expected, places=6)
        self.assertEqual(list(env["context"]["periods"]), ["FY2023-24"])

    def test_a_month_outside_the_reference_year_is_refused(self):
        with self.assertRaises(E.UnknownDimensionValue):
            get_grid_cell(self.engine, GridCellRequest(
                lat=31.5, lon=74.3, month="202501", gas="CO2"), PATHS)


if __name__ == "__main__":
    unittest.main()
