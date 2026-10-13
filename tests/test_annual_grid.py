"""The nine-period annual 0.05 degree cube is a product, so it is tested like one.

WHY THIS FILE EXISTS. rc44 shipped nine fiscal years of district products and deliberately no
historical raster: the objection, written into the code that declined it, was that a grid whose
within-province pattern is for two thirds of stream-years the reference year's would be read as
evidence it is not. That objection is answered by provenance, not by assertion, so what this
file guards is the part a provenance column cannot repair - that the raster is arithmetically
the inventory. If the cells stop adding to the national controls, the evidence grading is
decoration.

WHAT IS DELIBERATELY NOT HERE. Cross-product agreement (the FY2023-24 annual layer against the
sum of the twelve monthly cells, category and module groups against the core) belongs to the
release gates, which own both products at once. This file tests the cube against the national
panel and against its own declared geometry.
"""
import csv
import os
import unittest

import numpy as np

try:
    import netCDF4
except ImportError:                                       # pragma: no cover
    netCDF4 = None

from pkinv.paths import OUTPUTS
from pkinv.core.gis.grid import GRID_SPEC, GRID_SPEC_ID
from pkinv.report.annual_grid import CORE, FILL, GASES, VIEWS, period_bounds

NATIONAL = os.path.join(OUTPUTS, "pakemis_monthly_fy2015_16_fy2023_24.csv")
UNALLOC = os.path.join(OUTPUTS, "pakemis_spatial_unallocated_by_year.csv")


def _read(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


@unittest.skipIf(netCDF4 is None, "netCDF4 is not installed")
@unittest.skipUnless(os.path.exists(CORE), "the annual cube has not been built")
class TestTheAnnualCubeIsTheInventory(unittest.TestCase):
    """The cells, plus what is honestly unplaceable, are the national total."""

    @classmethod
    def setUpClass(cls):
        cls.ds = netCDF4.Dataset(CORE)
        cls.periods = [str(p) for p in cls.ds.variables["period_id"][:]]
        cls.views = [str(v) for v in cls.ds.variables["spatial_view"][:]]

    @classmethod
    def tearDownClass(cls):
        cls.ds.close()

    def test_the_three_views_partition_the_placed_mass(self):
        """physical, origin and accounting are disjoint attributions, not three renderings.

        Each stream is placed under exactly one view - waste at its origin, transport where it
        is accounted, everything else where it is emitted - so the three layers SUM to the
        placed total. They are not alternative complete maps of the same mass, and a reader who
        adds two of them together gets a number that means nothing. Asserting the partition here
        is what stops a future refactor from quietly making them overlap.
        """
        national = {}
        for row in _read(NATIONAL):
            key = (row["period_id"], row["gas"].lower())
            national[key] = national.get(key, 0.0) + float(row["emission_native_mass"])

        unplaced = {}
        for row in _read(UNALLOC):
            key = (row["period_id"], row["gas"].lower())
            unplaced[key] = unplaced.get(key, 0.0) + float(row["emissions_Gg"])

        worst = 0.0
        for gas in GASES:
            block = self.ds.variables[gas.lower() + "_emissions"][:]
            for index, period in enumerate(self.periods):
                cells = float(np.ma.sum(block[index]))
                control = national[(period, gas.lower())]
                residual = cells + unplaced.get((period, gas.lower()), 0.0) - control
                worst = max(worst, abs(residual) / control)
                self.assertLess(
                    abs(residual) / control, 1e-5,
                    "%s %s: cells %.3f + unallocated %.3f != national %.3f" % (
                        period, gas, cells, unplaced.get((period, gas.lower()), 0.0), control))
        self.assertLess(worst, 1e-5)

    def test_no_period_borrows_another_period_s_magnitude(self):
        """Nine distinct years, not one year written nine times.

        The brief that asked for this product asked for it explicitly: do not construct it by
        scaling the reference map. A cube built that way would still close against the national
        panel year by year, because scaling is exactly what would make it close. What it could
        not do is differ in PATTERN, so this compares normalised layers and requires that no two
        periods are the same map at different volume.
        """
        block = self.ds.variables["co2_emissions"][:]
        shapes = []
        for index in range(len(self.periods)):
            layer = np.ma.filled(block[index, 0], 0.0).astype(np.float64)
            total = layer.sum()
            self.assertGreater(total, 0.0)
            shapes.append(layer / total)
        for i in range(len(shapes)):
            for j in range(i + 1, len(shapes)):
                spread = float(np.abs(shapes[i] - shapes[j]).sum())
                self.assertGreater(
                    spread, 1e-9,
                    "%s and %s are the same normalised map: the cube was scaled, not rebuilt"
                    % (self.periods[i], self.periods[j]))


@unittest.skipIf(netCDF4 is None, "netCDF4 is not installed")
@unittest.skipUnless(os.path.exists(CORE), "the annual cube has not been built")
class TestTheCubeSaysWhatItIs(unittest.TestCase):
    """Geometry, time and encoding are declared in the file, not in a README."""

    @classmethod
    def setUpClass(cls):
        cls.ds = netCDF4.Dataset(CORE)

    @classmethod
    def tearDownClass(cls):
        cls.ds.close()

    def test_the_time_axis_is_nine_fiscal_intervals_and_says_so(self):
        """These are nine July-to-June years, and the bounds have to make that unambiguous.

        periods.csv carries INCLUSIVE end dates; CF bounds are half-open. Getting that wrong
        costs one day per period and is invisible in every plot, so the check is that each
        period's upper bound is the NEXT July, that the midpoint lies inside its own bounds, and
        that consecutive periods meet exactly with no gap and no overlap.
        """
        import datetime
        times = self.ds.variables["time"][:]
        bounds = self.ds.variables["time_bnds"][:]
        epoch = datetime.date(1970, 1, 1)
        expected = {row[0]: row for row in period_bounds()}
        pids = [str(p) for p in self.ds.variables["period_id"][:]]
        self.assertEqual(len(pids), 9)
        previous_end = None
        for index, pid in enumerate(pids):
            lower = epoch + datetime.timedelta(days=float(bounds[index][0]))
            upper = epoch + datetime.timedelta(days=float(bounds[index][1]))
            mid = epoch + datetime.timedelta(days=float(times[index]))
            self.assertEqual((lower.month, lower.day), (7, 1), "%s starts %s" % (pid, lower))
            self.assertEqual((upper.month, upper.day), (7, 1), "%s ends %s" % (pid, upper))
            self.assertEqual(upper.year, lower.year + 1)
            self.assertTrue(lower <= mid < upper)
            if previous_end is not None:
                self.assertEqual(lower, previous_end, "%s does not meet its predecessor" % pid)
            previous_end = upper
            _, want_lo, want_hi, want_mid = expected[pid]
            self.assertEqual(
                (float(bounds[index][0]), float(bounds[index][1]), float(times[index])),
                (float(want_lo), float(want_hi), float(want_mid)))

    def test_the_grid_is_the_frozen_spec(self):
        lat = self.ds.variables["lat"][:]
        lon = self.ds.variables["lon"][:]
        self.assertEqual((len(lat), len(lon)), (GRID_SPEC["height"], GRID_SPEC["width"]))
        self.assertGreater(float(lat[0]), float(lat[-1]), "row 0 must be the northern edge")
        self.assertEqual(getattr(self.ds, "grid_spec_id", None), GRID_SPEC_ID)

    def test_a_cell_total_can_be_turned_into_a_flux_without_leaving_the_file(self):
        """cell_area and pakistan_fraction ship as variables because Gg per cell is not a map.

        A 0.05 degree cell is 28.3 square kilometres in Sindh and 24.7 in the north - a 15%
        gradient that reads as a real north-south signal in any per-cell plot. The file carries
        the divisor so a reader never has to reconstruct it, and carries the land fraction so a
        coastal or border cell can be normalised per square kilometre OF PAKISTAN.
        """
        area = self.ds.variables["cell_area"][:]
        fraction = self.ds.variables["pakistan_fraction"][:]
        self.assertEqual(area.shape, (GRID_SPEC["height"], GRID_SPEC["width"]))
        self.assertTrue(np.all(area > 0))
        self.assertGreater(float(area[-1].mean()), float(area[0].mean()))
        self.assertTrue(np.all((fraction >= 0.0) & (fraction <= 1.0)))
        self.assertGreater(float(fraction.max()), 0.99)

    def test_fill_marks_outside_pakistan_and_nothing_else(self):
        """A masked cell must mean 'not Pakistan', never 'zero emissions here'.

        The two are different claims and only one of them is true of the sea. This pins the mask
        to pakistan_fraction so a cell inside the country that happens to emit nothing stays a
        real zero, which is what lets a reader tell an empty district from an absent one.
        """
        fraction = self.ds.variables["pakistan_fraction"][:]
        outside = np.asarray(fraction) <= 0.0
        for gas in GASES:
            block = self.ds.variables[gas.lower() + "_emissions"][:]
            for index in range(block.shape[0]):
                for view in range(block.shape[1]):
                    masked = np.ma.getmaskarray(block[index, view])
                    self.assertTrue(
                        np.array_equal(masked, outside),
                        "%s period %d view %d: the mask is not the country" % (gas, index, view))

    def test_the_encoding_is_the_one_that_was_chosen(self):
        """Chunking and compression are a promise about how the file reads, so they are pinned.

        (1, 1, 128, 128) means one period, one view, a spatial tile: the access pattern of
        somebody opening one year's map. Whole-array chunking would make that read the entire
        cube, which is the defect the monthly writer has and the reason this product did not
        reuse it.
        """
        for gas in GASES:
            var = self.ds.variables[gas.lower() + "_emissions"]
            self.assertEqual(var.dtype, np.float32)
            self.assertEqual(var.units, "Gg")
            filters = var.filters() or {}
            self.assertTrue(filters.get("zlib"), "%s is not compressed" % gas)
            self.assertTrue(filters.get("fletcher32"), "%s carries no checksum" % gas)
            self.assertEqual(tuple(var.chunking()), (1, 1, 128, 128))
            self.assertAlmostEqual(float(var._FillValue), FILL, places=3)
            self.assertEqual(var.dimensions, ("time", "spatial_view", "lat", "lon"))

    def test_the_shipped_file_stays_small(self):
        """Nine periods by three views by three gases, and it still has to fit in a download.

        The monthly cube has its own 8 MB budget and this is a separate file, so it gets a
        separate bound rather than sharing one. The pre-agreed fallback if this is ever hit is
        dropping the origin and accounting views to a companion file - keeping the physical view
        whole - not raising the number, because a cube nobody can download is not published.
        """
        size = os.path.getsize(CORE)
        self.assertLess(size, 16e6,
                        "the annual cube outgrew its 16 MB budget (%.1f MB); the pre-agreed "
                        "fallback is splitting the non-physical views into a companion file, "
                        "not raising this bound" % (size / 1e6))

    def test_the_period_named_alternative_is_not_manufactured_for_history(self):
        """Only FY2023-24 has the period-named alternative, and the annual cube must not
        imply nine.

        L_2023_24 names one period: the residential re-run with all the diverted dung
        burned in households, for the reference year. A nine-year series on that basis
        is a different claim with its own id (L_HERD1624, the air panel's), so this cube
        declares itself REF and carries no configuration axis, and the annual product has
        L_2023_24 rows for FY2023-24 alone.

        rc67 (2026-10-13): this guard was test_configuration_s_is_not_manufactured_for_
        history and its reason was that the survey was run in the reference year only.
        The survey series is the reference in all nine years now, built from two rounds,
        and the id that must not spread across history is the ledger's.
        """
        from pkinv.core import configurations as conf
        self.assertEqual(conf.LEDGER, "L_2023_24")
        self.assertEqual(getattr(self.ds, "configuration_id", None), conf.REFERENCE)
        self.assertNotEqual(getattr(self.ds, "configuration_id", None), conf.LEDGER)
        self.assertNotIn("spatial_configuration", self.ds.dimensions)
        self.assertEqual([str(v) for v in self.ds.variables["spatial_view"][:]], list(VIEWS))
        annual = _read(os.path.join(OUTPUTS, "pakemis_annual_fy2015_16_fy2023_24.csv"))
        periods = {r["period_label"] for r in annual if r["configuration_id"] == conf.LEDGER}
        self.assertEqual(periods, {"FY2023-24"})
        self.assertEqual(len({r["period_label"] for r in annual
                              if r["configuration_id"] == conf.REFERENCE}), 9)


if __name__ == "__main__":
    unittest.main()
