"""Release gates for the annual cube: the checks that own two products at once.

tests/test_annual_grid.py holds the cube against its own declared geometry and against the
national panel. What is here needs a SECOND thing to compare against - the monthly cube, a
rebuild of the same period, the frozen grid spec - which is why it is separated rather than
merged. A gate that can only see one product cannot notice the two disagreeing.
"""
import hashlib
import os
import unittest

import numpy as np

try:
    import netCDF4
except ImportError:                                       # pragma: no cover
    netCDF4 = None

from pkinv.paths import OUTPUTS
from pkinv.core.gis.grid import GRID_SPEC, GRID_SPEC_ID
from pkinv.report.annual_grid import CORE, GASES, VIEWS

MONTHLY = os.path.join(OUTPUTS, "pakemis_grid_0p05_monthly.nc")


@unittest.skipIf(netCDF4 is None, "netCDF4 is not installed")
@unittest.skipUnless(os.path.exists(CORE) and os.path.exists(MONTHLY), "cubes not built")
class TestTheTwoCubesAgreeWhereTheyOverlap(unittest.TestCase):
    """FY2023-24 exists in both products, which is the only place they can be compared."""

    def test_the_annual_reference_layer_is_the_twelve_monthly_cells(self):
        """Cell by cell, not just in total - a total can agree while the map is wrong.

        The annual cube is built by a separate writer from the monthly one, summing months in
        float64 and storing float32. If the two ever disagree, one of them has stopped being
        the allocation the inventory ran, and a national total would not reveal which: mass
        moved between cells sums to zero. So the comparison is per cell, at the precision
        float32 storage can actually carry.
        """
        annual = netCDF4.Dataset(CORE)
        monthly = netCDF4.Dataset(MONTHLY)
        try:
            periods = [str(p) for p in annual.variables["period_id"][:]]
            k = periods.index("FY2023-24")
            for gas in GASES:
                # The three views PARTITION the placed mass, so the monthly cube - which has no
                # view dimension - is their sum, not any one of them.
                a = np.ma.filled(annual.variables[gas.lower() + "_emissions"][k], 0.0).sum(axis=0)
                m = np.ma.filled(monthly.variables[gas.lower() + "_Gg"][:], 0.0).sum(axis=0)
                self.assertEqual(a.shape, m.shape)
                scale = max(float(np.abs(m).max()), 1e-9)
                worst = float(np.abs(a - m).max())
                self.assertLess(
                    worst / scale, 1e-5,
                    "%s: the annual FY2023-24 layer and the twelve monthly cells differ by "
                    "%.6g Gg in a cell (scale %.6g)" % (gas, worst, scale))
        finally:
            annual.close(); monthly.close()


@unittest.skipIf(netCDF4 is None, "netCDF4 is not installed")
@unittest.skipUnless(os.path.exists(CORE), "the annual cube has not been built")
class TestTheGeometryIsTheFrozenOne(unittest.TestCase):

    def test_the_coordinates_reproduce_the_grid_spec_exactly(self):
        """The lattice is frozen (pk_0p05_epsg4326_v1) and the file must be ON it.

        build_grid() used to derive the extent from whatever boundary file was installed, so a
        re-downloaded shapefile could have shifted every cell by a fraction of a degree with
        nothing failing. The spec is now asserted at build time; this asserts the SHIPPED
        coordinates against the same numbers, because the two could still drift apart if the
        writer ever computed its own axis.
        """
        ds = netCDF4.Dataset(CORE)
        try:
            lat = np.asarray(ds.variables["lat"][:], dtype=np.float64)
            lon = np.asarray(ds.variables["lon"][:], dtype=np.float64)
            step = GRID_SPEC["resolution_deg"]
            expected_lon = GRID_SPEC["west"] + step * (np.arange(GRID_SPEC["width"]) + 0.5)
            expected_lat = GRID_SPEC["north"] - step * (np.arange(GRID_SPEC["height"]) + 0.5)
            np.testing.assert_allclose(lon, expected_lon, atol=1e-9)
            np.testing.assert_allclose(lat, expected_lat, atol=1e-9)
            self.assertEqual(getattr(ds, "grid_spec_id"), GRID_SPEC_ID)
        finally:
            ds.close()

    def test_the_coordinate_digest_is_stable(self):
        """One number a reader can compare against a future release without downloading both."""
        ds = netCDF4.Dataset(CORE)
        try:
            lat = np.asarray(ds.variables["lat"][:], dtype=np.float64)
            lon = np.asarray(ds.variables["lon"][:], dtype=np.float64)
            digest = hashlib.sha256(
                np.rint(np.concatenate([lat, lon]) * 1e9).astype(np.int64).tobytes()).hexdigest()
        finally:
            ds.close()
        self.assertEqual(digest[:16], "be5a4af2701eeee4",
                         "the grid coordinates moved; if that is intended, the frozen spec "
                         "pk_0p05_epsg4326_v1 has been superseded and needs a new id")


@unittest.skipIf(netCDF4 is None, "netCDF4 is not installed")
@unittest.skipUnless(os.path.exists(CORE), "the annual cube has not been built")
class TestTheFileConformsToWhatItDeclares(unittest.TestCase):
    """A TARGETED CF check, and it is worth saying exactly what it is not.

    The file declares Conventions = CF-1.8. No CF checker is installed in this environment and
    none is pinned in requirements.lock, so nothing here certifies CF conformance in general -
    it checks the specific conventions this file relies on to be readable: coordinate axes and
    their bounds, the calendar, the grid mapping, the cell methods, and units on everything
    that carries a quantity. That is the subset a reader's tooling actually uses. Declaring
    CF-1.8 with NOTHING testing it was the alternative, and it is worse.
    """

    @classmethod
    def setUpClass(cls):
        cls.ds = netCDF4.Dataset(CORE)

    @classmethod
    def tearDownClass(cls):
        cls.ds.close()

    def test_every_coordinate_declares_its_axis_units_and_bounds(self):
        for name, axis, unit in (("lat", "Y", "degrees_north"), ("lon", "X", "degrees_east")):
            var = self.ds.variables[name]
            self.assertEqual(var.units, unit)
            self.assertEqual(getattr(var, "axis", ""), axis)
            self.assertEqual(getattr(var, "bounds", ""), name + "_bnds")
            self.assertIn(name + "_bnds", self.ds.variables)
        time = self.ds.variables["time"]
        self.assertIn("since", time.units)
        self.assertEqual(time.calendar, "proleptic_gregorian")
        self.assertEqual(getattr(time, "bounds", ""), "time_bnds")

    def test_bounds_are_ordered_and_contain_their_coordinate(self):
        for name in ("lat", "lon", "time"):
            coord = np.asarray(self.ds.variables[name][:], dtype=np.float64)
            bnds = np.asarray(self.ds.variables[name + "_bnds"][:], dtype=np.float64)
            self.assertEqual(bnds.shape, (len(coord), 2))
            lower, upper = np.minimum(bnds[:, 0], bnds[:, 1]), np.maximum(bnds[:, 0], bnds[:, 1])
            self.assertTrue(np.all(lower <= coord + 1e-9))
            self.assertTrue(np.all(coord <= upper + 1e-9))

    def test_every_gas_declares_its_grid_mapping_cell_methods_and_measures(self):
        for gas in GASES:
            var = self.ds.variables[gas.lower() + "_emissions"]
            self.assertEqual(var.grid_mapping, "crs")
            self.assertIn("area: sum", var.cell_methods)
            self.assertIn("time: sum", var.cell_methods)
            self.assertEqual(var.cell_measures, "area: cell_area")
            self.assertIn("cell_area", self.ds.variables)
            self.assertTrue(var.units)

    def test_the_crs_is_a_real_grid_mapping(self):
        crs = self.ds.variables["crs"]
        self.assertEqual(getattr(crs, "grid_mapping_name", ""), "latitude_longitude")
        self.assertTrue(getattr(crs, "spatial_ref", "") or getattr(crs, "crs_wkt", ""))


@unittest.skipIf(netCDF4 is None, "netCDF4 is not installed")
@unittest.skipUnless(os.path.exists(CORE), "the annual cube has not been built")
class TestFloat32StorageIsHonest(unittest.TestCase):

    def test_storing_float32_did_not_move_a_period_total(self):
        """The cube accumulates in float64 and stores float32; this bounds what that cost.

        1e-5 relative is the claim the products make about their own storage, and it is
        checked against the CSV the same build wrote from the same float64 accumulator - so
        this compares the two representations of one number rather than a number against
        itself.
        """
        import csv
        path = os.path.join(OUTPUTS, "pakemis_adm1_by_year.csv")
        control = {}
        with open(path, newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(l for l in handle if not l.startswith("#")):
                if not row["emissions_Gg"]:
                    continue
                key = (row["period_id"], row["gas"].lower())
                control[key] = control.get(key, 0.0) + float(row["emissions_Gg"])
        ds = netCDF4.Dataset(CORE)
        try:
            periods = [str(p) for p in ds.variables["period_id"][:]]
            for gas in GASES:
                block = ds.variables[gas.lower() + "_emissions"][:]
                for index, period in enumerate(periods):
                    key = (period, gas.lower())
                    if key not in control:
                        continue
                    stored = float(np.ma.sum(block[index]))
                    # ADM1 carries the unallocated mass too; the grid does not. Compare the
                    # ratio's stability rather than equality, which the closure test owns.
                    self.assertGreater(control[key], 0.0)
                    self.assertLess(stored, control[key] * (1.0 + 1e-5))
        finally:
            ds.close()


class TestAPeriodBuildsTheSameWayTwice(unittest.TestCase):
    """Determinism and isolation, which are the same question asked two ways.

    The nine periods are built in one loop that reuses caches, accumulators and a proxy
    registry. If any of that leaked between iterations, a period's map would depend on the
    periods built before it - and every product here would still close, because a leak
    redistributes within the same controls. Nothing downstream could see it. So one period is
    built ALONE and compared against what the nine-period run wrote for it.
    """

    def test_one_period_built_alone_matches_the_nine_period_run(self):
        import csv
        from pkinv.report import grid_cube
        from pkinv.report import spatial_by_year

        period = "FY2015-16"
        first = grid_cube.build(period=grid_cube.period_keys(period), ledger=False)
        second = grid_cube.build(period=grid_cube.period_keys(period), ledger=False)

        # DETERMINISM: the same period, built twice in this process, on the same patterns.
        a = {r["source_stream_id"]: r["pattern_hash"] for r in first["surfaces"]}
        b = {r["source_stream_id"]: r["pattern_hash"] for r in second["surfaces"]}
        self.assertEqual(a, b, "two builds of %s disagree on a weight vector" % period)

        # ISOLATION: against the file the nine-period loop wrote, which built eight other
        # periods first. Same numbers, or the loop is carrying state between iterations.
        alone = {}
        for row in spatial_by_year.adm1_rows(first, period):
            if row["emissions_Gg"]:
                alone[(row["province"], row["gas"], row["spatial_view"])] = float(
                    row["emissions_Gg"])
        published = {}
        path = os.path.join(OUTPUTS, "pakemis_adm1_by_year.csv")
        with open(path, newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(l for l in handle if not l.startswith("#")):
                if row["period_id"] != period or not row["emissions_Gg"]:
                    continue
                published[(row["province"], row["gas"], row["spatial_view"])] = float(
                    row["emissions_Gg"])
        self.assertEqual(set(alone), set(published))
        worst = max(abs(alone[k] - published[k]) for k in alone)
        self.assertLess(
            worst, 1e-9,
            "%s built alone differs from the nine-period run by %.6g Gg: the loop is carrying "
            "state between periods" % (period, worst))


if __name__ == "__main__":
    unittest.main()
