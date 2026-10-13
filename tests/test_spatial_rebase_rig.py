"""The re-base rig can see a movement, and refuses one that is not conserving.

WHY THIS EXISTS. rc44 moves published district numbers in seven separate commits, and each is
only interpretable if the movement is measured against the commit before it. The rig that does
the measuring (scripts/measure_spatial_rebase.py) was written for rc42, when the inventory
published one year: it reads pakemis_adm2_monthly_sector.csv, pakemis_grid_fallbacks.csv and
district_totals_2024.csv, all of which are FY2023-24 only. A re-base that moved FY2017-18 and
left the reference year alone would have produced an empty report - not a warning, an empty
report - and rc44's sequence is built almost entirely out of such re-bases.

So the rig now reads the two nine-year products as well, and these tests hold the property that
makes it worth reading: it reports a movement it should see, and it does not report one that
did not happen. `compare_units` is the whole measurement, so it is tested directly rather than
through git - a test that needed a baseline commit could not run in a package or a clean clone.
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import importlib.util  # noqa: E402


def _rig():
    path = os.path.join(ROOT, "scripts", "measure_spatial_rebase.py")
    spec = importlib.util.spec_from_file_location("measure_spatial_rebase", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestTheRigMeasuresWhatMoved(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.rig = _rig()

    def test_a_conserving_move_is_reported_with_zero_net(self):
        """The signature of a spatial re-base: mass leaves one shape and arrives at another,
        so gross is positive and net is zero. A rig that reported net movement for this would
        be measuring a mass error, not a re-base."""
        before = {("FY2015-16", "agriculture", "shapeA", "CH4"): 100.0,
                  ("FY2015-16", "agriculture", "shapeB", "CH4"): 100.0}
        after = {("FY2015-16", "agriculture", "shapeA", "CH4"): 99.5,
                 ("FY2015-16", "agriculture", "shapeB", "CH4"): 100.5}
        moved, gross, net, worst, unit = self.rig.compare_units(
            before, after, lambda k: k[1], lambda k: k[3])
        self.assertEqual(moved, 2)
        self.assertGreater(gross, 0.0)
        self.assertAlmostEqual(net, 0.0, places=12)
        self.assertIn("shape", unit)

    def test_an_unchanged_surface_reports_nothing(self):
        """The rig must be silent when nothing moved, or twelve of rc44's fourteen commits
        cannot assert zero movement."""
        same = {("FY2019-20", "power", "shapeA", "CO2"): 42.0}
        moved, gross, net, _worst, _unit = self.rig.compare_units(
            same, dict(same), lambda k: k[1], lambda k: k[3])
        self.assertEqual((moved, gross, net), (0, 0.0, 0.0))

    def test_movement_below_the_write_precision_is_not_reported(self):
        """The products carry eight decimals; a difference under that is the file's own
        rounding, not a re-base, and reporting it would bury the real rows."""
        before = {("FY2020-21", "waste", "shapeA", "CH4"): 10.0}
        after = {("FY2020-21", "waste", "shapeA", "CH4"): 10.0 + self.rig.TOL_GG / 2}
        moved, _gross, _net, _worst, _unit = self.rig.compare_units(
            before, after, lambda k: k[1], lambda k: k[3])
        self.assertEqual(moved, 0)

    def test_the_methane_origin_follows_the_module(self):
        """A gross figure in CO2e is meaningless unless CH4 is weighted by the module's own
        origin: 28 for the biogenic modules, 30 elsewhere."""
        self.assertAlmostEqual(self.rig._co2e_Mt("agriculture", "CH4", 1000.0), 28.0, places=9)
        self.assertAlmostEqual(self.rig._co2e_Mt("fugitives", "CH4", 1000.0), 30.0, places=9)


class TestTheRigCoversTheNineYearProducts(unittest.TestCase):
    """The rc42 rig read three reference-year products. These assert it now reads the two that
    carry the other eight periods, because that gap is the reason it was extended."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(ROOT, "scripts", "measure_spatial_rebase.py"),
                  encoding="utf-8") as handle:
            cls.source = handle.read()

    def test_it_reads_both_nine_year_products(self):
        for name in ("pakemis_adm2_sector_by_year.csv", "pakemis_adm1_by_year.csv"):
            self.assertIn(name, self.source)

    def test_provincial_movement_needs_an_explicit_flag(self):
        """ADM1 is an invariant for twelve of rc44's commits and the deliverable for one.
        Moving it must therefore be declared at the call, not discovered in the output."""
        self.assertIn("--adm1-may-move", self.source)
        self.assertIn("adm1_may_move", self.source)

    def test_the_national_total_is_asserted_not_reported(self):
        """One level above ADM1 nothing may move at any point in the sequence."""
        self.assertIn("national total moved", self.source)


if __name__ == "__main__":
    unittest.main()
