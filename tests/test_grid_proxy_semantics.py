"""Every grid proxy declares what its numbers ARE, and the declaration is re-derived here.

The cube multiplies rasters and normalises, so it has never needed to know whether a cell holds
a COUNT, a FRACTION of the cell's area, or a weight with no unit. That holds right up until
something must be corrected for the fact that a 0.05-degree cell is 28.298 km2 in Sindh and
24.678 km2 in Gilgit-Baltistan: the correction is right for a fraction and wrong for a count,
and nothing in the array distinguishes them.

THE POINT OF THIS FILE IS THAT THE TAGS ARE MEASURED. The author reached the opposite
conclusion once by reading a builder's docstring - proxies.py resamples with
Resampling.average and says "density" - and the arithmetic refutes it: a 0.05-degree cell
covers a constant 6x6 block of WorldPop source pixels at every latitude, so the averaged array
is proportional to the cell TOTAL. Read as a count, population lands within two percent of
WorldPop's national figure; read as a density it is a quarter short. A docstring is not
evidence.
"""
import os
import unittest

from _support import DATA, data_rows

SEMANTICS = "grid_proxy_semantics.csv"
VOCABULARY = ("count", "fraction", "feature_weight", "constant", "derived")


class TestTheSemanticsRegistry(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.rows = {r["proxy"]: r for r in data_rows(SEMANTICS)}

    def test_every_cube_raster_is_declared(self):
        from pkinv.core.gis.cube import RASTER_NAMES
        missing = sorted(set(RASTER_NAMES) - set(self.rows))
        self.assertFalse(missing, "cube rasters with no declared semantics: %s" % missing)

    def test_the_vocabulary_is_closed(self):
        for proxy, row in sorted(self.rows.items()):
            self.assertIn(row["semantics"], VOCABULARY, proxy)

    def test_a_derived_proxy_declares_no_area_rule_of_its_own(self):
        """manure_applied is cropland x glw_livestock - a fraction times a count, which is
        neither. A tag of its own would invite area-weighting it once for the cropland in it."""
        row = self.rows["manure_applied"]
        self.assertEqual(row["semantics"], "derived")
        self.assertEqual(row["area_weight"], "from its parents")


class TestTheTagsAreRederived(unittest.TestCase):
    """Not "the registry says fraction" - "read as a fraction times cell area it closes against
    a number this repository did not produce, and read the other way it does not"."""

    @classmethod
    def setUpClass(cls):
        from pkinv.core.gis.grid import build_grid, cell_area_km2
        from pkinv.core.gis import cube as cube_core
        from pkinv.core.gis.proxies import get_proxy
        cls.grid = build_grid()
        cls.area = cell_area_km2(cls.grid)
        cls.ctx = cube_core.Context(cls.grid)
        # THE RAW RASTER, not the Context's (rc45). Context.proxies now carries the MEASURE -
        # a fraction already multiplied by cell area - so asserting "sum x area closes against
        # the control" against it would apply area twice and refute a correct build.
        cls.raw = {name: get_proxy(name, cls.grid)[0].astype(float)
                   for name in ("cropland", "builtup", "population", "glw_livestock")}
        cls.rows = {r["proxy"]: r for r in data_rows(SEMANTICS)}

    def test_the_cell_area_gradient_is_what_the_registry_says(self):
        north, south = self.area[0, 0], self.area[-1, 0]
        self.assertAlmostEqual(north, 24.678, places=2)
        self.assertAlmostEqual(south, 28.298, places=2)
        self.assertAlmostEqual(south / north, 1.1467, places=3)

    def test_every_fraction_with_a_control_closes_as_an_AREA(self):
        checked = 0
        for proxy, row in sorted(self.rows.items()):
            if row["semantics"] != "fraction" or not row["control_value"]:
                continue
            if proxy not in self.raw:
                continue          # gcd_rice is read by the crosscheck, not the cube
            measured = float((self.raw[proxy] * self.area).sum())
            control = float(row["control_value"])
            self.assertLess(abs(measured - control) / control, 0.10,
                            "%s: %.0f km2 against a control of %.0f" % (proxy, measured, control))
            checked += 1
        self.assertGreater(checked, 0)

    def test_population_is_a_COUNT_and_the_density_reading_is_refuted(self):
        """Both directions, because the refutation is the evidence: this is the tag the author
        got wrong from a docstring, and the arithmetic that settled it."""
        pop = self.raw["population"]
        control = float(self.rows["population"]["control_value"])
        as_count = float(pop.sum()) * 36.0
        as_density = float((pop * self.area).sum())
        self.assertLess(abs(as_count - control) / control, 0.03, "count reading: %.0f" % as_count)
        self.assertGreater(abs(as_density - control) / control, 0.15,
                           "the density reading is supposed to FAIL: %.0f" % as_density)

    def test_the_context_hands_out_the_MEASURE_and_the_registry_decides(self):
        """The registry stopped being a document in rc45. Context.proxies now carries the
        measure a proxy generates, not the raster: a fraction multiplied by cell area once, a
        count untouched, and manure_applied - a fraction times a count - multiplied exactly
        once because its declared parents sum to one area exponent rather than two."""
        from pkinv.core.gis.proxies import _area_exponent
        import numpy as np
        for name, raw in sorted(self.raw.items()):
            expected = raw * self.area if _area_exponent(name) else raw
            self.assertTrue(np.allclose(self.ctx.proxies[name], expected, rtol=0, atol=0),
                            "%s: Context does not carry the declared measure" % name)
        self.assertEqual(_area_exponent("manure_applied"), 1)
        self.assertEqual(_area_exponent("population"), 0)

    def test_uniform_is_the_cell_area_and_no_longer_the_cell_COUNT(self):
        """The one tag that carried a behaviour change, and it has now happened.

        When the registry landed, this test asserted the opposite: uniform was np.ones, so it
        summed to 90,780 - the cell count - and spread mass evenly per square DEGREE. That
        assertion was written to pin the defect one commit before removing it, so that the
        removal would have to come here and say so rather than passing unnoticed. Uniform is
        the geodesic cell area now, and it sums to the area of the grid."""
        uniform = self.ctx.proxies["uniform"]
        cells = float(self.grid.height * self.grid.width)
        self.assertNotAlmostEqual(float(uniform.sum()), cells, places=0)
        self.assertAlmostEqual(float(uniform.sum()), float(self.area.sum()), places=6)
        self.assertAlmostEqual(float(uniform.sum()), 2415435.0, delta=1.0)


class TestNoSurfaceSpreadsMassPerDegree(unittest.TestCase):
    """The per-square-degree spread cannot come back by someone adding an eleventh site.

    rc44 found TEN places that spread mass evenly over a set of cells, not the six the release
    plan counted - the first commit of this pass had added a residual fallback branch to each
    of the grid, captive and IPPU weights, and those three were exactly the ones a stale count
    would have missed. So this is asserted from the source rather than from a list: a weight
    built from a bare mask, or from np.ones, treats a 24.678 km2 cell in Gilgit and a 28.298
    km2 cell in Karachi as equal.
    """

    # THE WHOLE OF src/, not a list (rc45). rc44 scanned three files and its commit letter
    # claimed "after this commit no np.ones and no bare mask remains as a weight". That was
    # true of the three files and false of the tree: five sites survived in
    # spatial_brackets_adm2.py and one in residential/gis/run_gis.py. The bracket's was the
    # damaging one - it compares two allocations, and rc44 made one arm area-correct and left
    # the other per-degree, so the published spread became partly an artefact of the mismatch,
    # and that bracket feeds pakemis_joint_uncertainty.csv. A guard with a file list is a
    # guard that goes stale; this one walks the source.
    ALLOWED = {
        # A linear-programming objective vector, not a spatial weight: one unit of "prefer
        # this cell" per free variable, which is what -np.ones means to linprog.
        ("src/pkinv/sectors/aviation/reconstructed.py", "linprog"),
    }

    def _sources(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for base, _dirs, names in os.walk(os.path.join(root, "src")):
            for name in sorted(names):
                if name.endswith(".py"):
                    full = os.path.join(base, name)
                    yield os.path.relpath(full, root), full

    def test_no_weight_is_built_from_a_bare_mask_or_from_ones(self):
        import re
        offenders = []
        for relative, full in self._sources():
            with open(full, encoding="utf-8") as handle:
                for number, line in enumerate(handle, 1):
                    if any(relative == path and token in line
                           for path, token in self.ALLOWED):
                        continue
                    if re.search(r"np\.ones\(", line):
                        offenders.append("%s:%d  %s" % (relative, number, line.strip()))
                    # `mask.astype(np.float64)` as a WEIGHT. Converting a proxy array's dtype
                    # is fine and common; converting a boolean mask is the per-degree spread.
                    # \w*mask\w* and not \bmask\w*: the rc44 pattern required a word
                    # boundary before "mask", so it read mask.astype but not dmask.astype -
                    # and dmask.astype was one of the six sites it was meant to catch.
                    if re.search(r"\w*mask\w*\.astype\(np\.float64\)", line):
                        offenders.append("%s:%d  %s" % (relative, number, line.strip()))
        self.assertFalse(offenders,
                         "a uniform surface must be per square kilometre - use "
                         "ctx.cell_area or grid.cell_area_km2:\n  " + "\n  ".join(offenders))

    def test_the_context_carries_one_area_array_and_uniform_is_it(self):
        from pkinv.core.gis.grid import build_grid
        from pkinv.core.gis import cube as cube_core
        grid = build_grid()
        ctx = cube_core.Context(grid)
        self.assertIs(ctx.proxies["uniform"], ctx.cell_area)


if __name__ == "__main__":
    unittest.main()
