"""A booked activity column that is a share of an identity, not a measurement.

WHY THIS TEST EXISTS. The industrial module books HDIP's brick-kiln and cement coal columns
into 1.A.2, and the brick fleet's own survey evidence sits beside them carrying an explicit
note that it is not booked. That arrangement is defensible only if the booked column measures
brick coal. Three things here say it does not, and none of them was asserted anywhere before:

  the identity      HDIP's coal supply and HDIP's coal consumption close to within 1 kt in
                    twelve of the fourteen years both tables cover. Consumption is therefore
                    constructed from supply - apparent consumption, stock-blind - not
                    measured against it.
  the constraint    over FY2019-20 to FY2023-24 the total moves -438 kt while the power
                    column gains 8,299 and brick plus cement lose 8,739. The total's move is
                    5.3 per cent of power's, so in that window a column cannot move far
                    without another column moving the other way. (An earlier version read
                    "4 kt" and "8,304": both came from the superseded FY2023-24 print.)
  the bound         the booked brick column falls BELOW the brick fleet's own low coal bound
                    in FY2016-17, FY2022-23 and FY2023-24, and at the reference year implies
                    4,765 firing kiln-years against a fleet counted at 9,486 to 10,394.

WHAT IS ASSERTED. Those three, and that the redistribution claim carries its scope - the
product must emit the full span as well, where the total grew and the claim would be false.
NOT that HDIP is wrong, and NOT that the fleet estimate should be booked instead: the fleet
was counted once and has no time axis, which is why the repository declared it unbooked.
"""
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.core.io import read_rows                                      # noqa: E402

OUT = os.path.join(ROOT, "outputs", "pakemis_coal_allocation_identity.csv")

# How close "closes" is. 1 kt on a ~25,000 kt total is 0.004 per cent - far tighter than any
# independent pair of national statistics would agree, which is the evidence for an identity.
CLOSES_KT = 1.0
# The two years that do not close, and why they are allowed to.
DECLARED_NON_ZERO = {
    "FY2015-16": "-204 kt; no held note explains this one",
}
# FY2023-24 WAS DECLARED HERE AND WAS NOT A DATA FACT. Its reason read "-434 kt; exactly the
# revision the supply table's own note records, the 2024-25 edition moving production down 434
# and the consumption total '-434.8 in step'". That note says the two tables moved TOGETHER,
# which is why they still close; it was read as saying they differ by 434. The residual was
# really the builder's own defect - the consumption reader had no revision_status filter where
# the supply reader had one, so last-write-wins picked up the superseded provisional print
# (brick kilns 1,564 kt, total 25,153) that the source file deliberately retains. With the
# filter the year closes to +1 kt. A declared exception whose stated reason contradicts the
# document it cites is how the defect survived: the symptom already had a story attached.
RECENT_WINDOW = "FY2019-20..FY2023-24"


class TestTheConsumerSplitIsARedistribution(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.exists(OUT):
            raise unittest.SkipTest("the allocation identity has not been built here")
        cls.rows = read_rows(OUT, comments=True)

    def test_supply_and_consumption_close_like_an_identity(self):
        bad = {}
        for r in self.rows:
            if r["row_kind"] != "balance":
                continue
            resid = abs(float(r["supply_minus_consumption_kt"]))
            if resid > CLOSES_KT and r["period_id"] not in DECLARED_NON_ZERO:
                bad[r["period_id"]] = resid
        self.assertFalse(
            bad,
            "HDIP supply and consumption no longer close to within %g kt in %s. If they have "
            "genuinely come apart, consumption may be a measurement after all and the whole "
            "finding needs restating; if a year is newly non-zero, add it to "
            "DECLARED_NON_ZERO with the reason." % (CLOSES_KT, bad))

    def test_the_declared_exceptions_are_still_the_only_ones(self):
        live = {r["period_id"] for r in self.rows if r["row_kind"] == "balance"
                and abs(float(r["supply_minus_consumption_kt"])) > CLOSES_KT}
        self.assertEqual(
            live, set(DECLARED_NON_ZERO),
            "the set of years that do not close has changed: %s against the declared %s"
            % (sorted(live), sorted(DECLARED_NON_ZERO)))

    def test_the_recent_window_is_flat_and_the_columns_trade(self):
        rows = {r["subject"]: r for r in self.rows
                if r["row_kind"] == "redistribution" and r["period_id"] == RECENT_WINDOW}
        self.assertTrue(rows, "the recent window %s is not emitted" % RECENT_WINDOW)
        total = float(rows["total"]["value_kt"])
        power = float(rows["power"]["value_kt"])
        other = float(rows["brick_kilns"]["value_kt"]) + float(rows["cement"]["value_kt"])
        # RELATIVE TO THE SWING, not an absolute kt. The claim is "the total barely moved
        # while the columns traded", so the test is |total| against |power|, which is what
        # makes the claim true or false. The previous 50 kt threshold was calibrated to a
        # -4 kt total that came from the superseded FY2023-24 print; on the final vintage the
        # total moves -438 kt, which is 5.3 per cent of power's +8,299 and still leaves the
        # redistribution reading intact. An absolute bound here would have to be re-based
        # every time a vintage lands, and silently encoded the defect it was fitted to.
        self.assertGreater(power, 0, "the power column no longer gains over the window")
        self.assertLess(other, 0, "brick plus cement no longer lose over the window")
        self.assertLess(
            abs(total), 0.10 * abs(power),
            "the total over %s moved %+.0f kt against power's %+.0f - more than a tenth of "
            "the swing, so the fixed-total reading does not apply"
            % (RECENT_WINDOW, total, power))
        self.assertLess(
            abs(power + other), 0.10 * abs(power),
            "power's gain (%+.0f) and brick+cement's loss (%+.0f) no longer offset to within "
            "a tenth; the near-zero-sum reading needs restating" % (power, other))

    def test_the_claim_carries_its_scope(self):
        """The full span must be emitted too, because there the total GREW."""
        spans = {r["period_id"] for r in self.rows if r["row_kind"] == "redistribution"}
        self.assertGreaterEqual(
            len(spans), 2,
            "only one window is emitted (%s). The full span must be published beside the "
            "recent one: over it the total grew and a redistribution claim would be false, "
            "and a reader cannot see that from the recent window alone." % spans)

    def test_the_booked_brick_column_leaves_the_fleets_own_bound(self):
        below = sorted({r["period_id"] for r in self.rows
                        if r["row_kind"] == "brick_bound"
                        and r["verdict"].startswith("BELOW")})
        self.assertIn("FY2023-24", below,
                      "the booked brick column no longer falls below the fleet's low bound "
                      "at the reference year; the finding needs restating. Below in: %s"
                      % below)

    def test_the_implied_firing_fleet_is_published_against_the_counted_one(self):
        ref = [r for r in self.rows if r["row_kind"] == "brick_bound"
               and r["period_id"] == "FY2023-24"]
        self.assertTrue(ref, "no brick_bound row for the reference year")
        for r in ref:
            self.assertTrue(r["implied_firing_kiln_years"],
                            "%s carries no implied firing kiln-years" % r["subject"])
            ratio = float(r["implied_over_counted_fleet"])
            self.assertLess(ratio, 1.0,
                            "the booked column now implies MORE firing kilns than were "
                            "counted at the reference year (%.2f of the %s fleet)"
                            % (ratio, r["subject"]))

    def test_the_shipped_file_matches_a_fresh_build(self):
        r = subprocess.run(
            [sys.executable, "-m", "pkinv.sectors.industry.coal_allocation_identity",
             "--check"],
            capture_output=True, text=True, cwd=ROOT,
            env=dict(os.environ, PYTHONPATH=os.path.join(ROOT, "src")))
        self.assertEqual(r.returncode, 0,
                         "the allocation identity is stale; rebuild it.\n%s%s"
                         % (r.stdout, r.stderr))


if __name__ == "__main__":
    unittest.main()
