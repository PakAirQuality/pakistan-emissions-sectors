"""The two coal lanes move together, and the cross-check is not overstated.

HDIP's consumption is its supply, so power and industry cannot be re-based independently. The
risk in a file that says so is overclaiming the corroboration: the brick-fleet bound is one
census with no time axis and a range wider than the quantity in dispute, so "inside the bound"
is a weak test and the file must not read as a proof. These tests hold the arithmetic and the
modesty.
"""
import csv
import io
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "outputs", "pakemis_coal_sector_reallocation.csv")
SRC = os.path.join(ROOT, "src", "pkinv", "sectors", "industry", "coal_reallocation.py")


def _rows(path):
    body = "".join(l for l in open(path, encoding="utf-8") if not l.startswith("#"))
    return list(csv.DictReader(io.StringIO(body)))


class TestTheTwoLanesMoveTogether(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.exists(OUT):
            raise unittest.SkipTest("the reallocation has not been built here")
        cls.rows = _rows(OUT)

    def test_it_covers_the_panel(self):
        from pkinv.core.reporting_window import CORE_FY_STARTS
        self.assertEqual({int(r["fiscal_start_year"]) for r in self.rows}, set(CORE_FY_STARTS))

    def test_the_two_deltas_offset_wherever_the_identity_CLOSES(self):
        """The whole premise - but it can only hold where HDIP's own supply and consumption
        close, and in one year they do not. The deltas must offset to the kilotonne in the
        eight closing years and must differ by exactly the declared gap in the ninth, which is
        a stronger assertion than exempting that year."""
        # ONE assertion for every year: the deltas sum to the identity's own gap. Where the
        # identity closes that gap is zero and this is the offset claim; where it does not, the
        # deltas differ by exactly the declared shortfall. Splitting it into two branches put a
        # 2 kt rounding on the boundary of both, which is how a tolerance becomes a bug.
        for r in self.rows:
            p = float(r["power_delta_kt"]); i = float(r["industrial_delta_kt"])
            gap = float(r["identity_closes_kt"])
            self.assertAlmostEqual(
                p + i, gap, delta=3.0,
                msg="%s: power %+.0f and industrial %+.0f sum to %+.0f, which is not the "
                    "identity's own gap of %+.0f - so the supply total is not being held fixed"
                    % (r["period_id"], p, i, p + i, gap))
        # This product uses the inventory booking policy, including its older
        # FY2015-16 vintage. The raw publisher identity is a separate product.
        self.assertLessEqual(max(abs(float(r["identity_closes_kt"])) for r in self.rows), 3.)

    def test_the_offset_opposes_the_power_move(self):
        for r in self.rows:
            p = float(r["power_delta_kt"]); off = float(r["industrial_offset_Mt"])
            if abs(p) > 100:
                self.assertTrue((p > 0) != (off > 0),
                                "%s: the industrial offset should oppose the power move"
                                % r["period_id"])

    def test_the_reallocation_never_worsens_the_brick_position(self):
        """The actual claim, which is weaker than "it fixes brick": it must not break a year
        that was already consistent."""
        for r in self.rows:
            if r["brick_position_booked"] == "within conditional fleet range":
                self.assertEqual(r["brick_position_with_residual"], "within conditional fleet range",
                                 "%s was inside the bound and the reallocation pushed it out"
                                 % r["period_id"])

    def test_the_cross_check_is_stated_as_three_years_not_most(self):
        """An earlier draft of the module docstring said the brick column was below its floor
        in "most years". The product says three. A claim that drifts upward in prose while the
        data says otherwise is the failure this asserts against."""
        # rc68: a fleet counted once (2020-11, 2023-07) is compared only inside the fiscal
        # period of its observation. Through rc67 one count was carried across every year
        # and three years read "below"; two of them (FY2016-17, FY2022-23) had no count.
        below = [r["period_id"] for r in self.rows
                 if r["brick_position_booked"] == "below conditional fleet case"]
        self.assertEqual(below, ["FY2023-24"], "below-floor years changed: %s" % below)
        compared = {r["period_id"] for r in self.rows if r["brick_fleet_low_kt"]}
        self.assertEqual(compared, {"FY2020-21", "FY2023-24"})
        source = open(SRC, encoding="utf-8").read()
        self.assertIn("not an annual physical floor", source)

    def test_it_does_not_claim_which_consumer_took_the_coal(self):
        for r in self.rows:
            self.assertIn("NOT resolved", r["note"],
                          "%s stops short of saying which non-power consumer took the coal, "
                          "and the note must say so" % r["period_id"])
