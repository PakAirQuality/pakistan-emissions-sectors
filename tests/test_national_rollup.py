"""The cross-sector rollup, guarded.

The all-sector total previously existed only in commit messages. These tests make the
rollup a checked artefact: the TOTAL row must equal the sum of its parts exactly, every
registered sector must appear, and memo items must stay out of the sum.

Run:  python3 -m unittest tests.test_national_rollup
"""
import collections
import unittest

from pkinv.core import registry
from pkinv.report import completeness, national_rollup


class TestNationalRollup(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = national_rollup.rollup()
        cls.sectors = [r for r in cls.rows if r["sector"] != "TOTAL"]
        cls.total = cls.rows[-1]

    def test_total_equals_the_sum_of_parts(self):
        """The closure check, on unrounded values."""
        self.assertEqual(self.total["sector"], "TOTAL")
        for key in ("co2e_Mt_AR5", "co2e_Mt_AR6"):
            self.assertEqual(self.total[key], sum(r[key] for r in self.sectors))

    def test_every_registered_sector_appears(self):
        """A sector added to SECTOR_MODULES but missing here is a silent hole."""
        self.assertEqual([r["sector"] for r in self.sectors],
                         [s.NAME for s in registry.all_sectors()])

    def test_memo_items_are_not_summed(self):
        """Each row is build_components only; aviation's bunkers must stay outside."""
        aviation = registry.get("aviation")
        comps = aviation.build_components(aviation.load_data())
        row = next(r for r in self.sectors if r["sector"] == "aviation")
        self.assertEqual(row["co2e_Mt_AR5"], sum(c["co2e_Mt_AR5"] for c in comps))
        memo = aviation.memo_items(aviation.load_data())
        self.assertTrue(memo and all(m["emissions_Gg"] > 0 for m in memo))

    def test_shares_sum_to_100(self):
        self.assertAlmostEqual(sum(r["share_pct"] for r in self.sectors), 100.0, places=9)

    def test_rounding_preserves_closure(self):
        """Rounded rows must sum to the rounded total within half an increment."""
        rounded = sum(round(r["co2e_Mt_AR5"], 5) for r in self.sectors)
        self.assertAlmostEqual(rounded, round(self.total["co2e_Mt_AR5"], 5), delta=5e-6 * len(self.sectors))

    def test_the_caveat_describes_the_rows_it_rides_on(self):
        """The TOTAL row's warning is derived from the sectors, not asserted beside them.

        It was asserted, and it went stale in place: after every sector moved onto FY2023-24
        the row read "Sum across reference years, not a single-year total" and "FY2023-24" in
        adjacent columns, with year="mixed" between them. A caveat that outlives what it warns
        about is worse than none, because it teaches a reader to discount the true ones.
        """
        spans = {(r["period_start"], r["period_end"]) for r in self.rows
                 if r["sector"] != "TOTAL"}
        self.assertIn("Memo items", self.total["note"])
        if len(spans) == 1:
            self.assertIn("Every sector on one reporting period", self.total["note"])
            self.assertNotIn("Sum across reference years", self.total["note"])
            self.assertEqual(self.total["year"], self.total["period_label"])
        else:
            self.assertIn("Sum across reference years", self.total["note"])
            self.assertEqual(self.total["year"], "mixed")

    def test_every_row_says_how_to_read_its_year(self):
        """The integer year means the opening calendar year in two sectors and the closing
        year in the rest. Both are legitimate; publishing them in one column without saying
        which is not."""
        for r in self.rows:
            if r["sector"] == "TOTAL":
                continue
            self.assertIn(r["year_convention"],
                          ("fiscal-start", "fiscal-end", "calendar"),
                          "%s publishes a year with no convention" % r["sector"])


class TestTheReferencePeriodIsPublished(unittest.TestCase):
    """The harmonisation round's deliverable, asserted rather than described.

    The released table used to carry an integer year whose meaning differed between
    sectors. It now carries explicit dates, and the honest claim - nine of ten sectors on
    one period, agriculture one fiscal year ahead - is checked here so it cannot quietly
    become "all ten" or quietly slip back to three outliers.
    """

    @classmethod
    def setUpClass(cls):
        cls.rows = national_rollup.rollup()
        cls.sectors = [r for r in cls.rows if r["sector"] != "TOTAL"]

    def test_every_row_carries_explicit_dates(self):
        for r in self.rows:
            self.assertRegex(r["period_start"], r"^\d{4}-\d{2}-\d{2}$", r["sector"])
            self.assertRegex(r["period_end"], r"^\d{4}-\d{2}-\d{2}$", r["sector"])
            self.assertLess(r["period_start"], r["period_end"], r["sector"])

    def test_all_ten_sectors_share_one_period(self):
        """The harmonisation is complete: one reference period, no outlier.

        This asserted nine-of-ten for one release, with agriculture a fiscal year ahead
        because its crop and fertiliser statistics are published on that year and the
        2023-24 editions were not held. They are held now, under sources/Agriculture/, and
        the sector reads them."""
        periods = collections.Counter(r["period_label"] for r in self.sectors)
        self.assertEqual(dict(periods), {"FY2023-24": len(self.sectors)},
                         "sectors outside the reference period: %s"
                         % [(r["sector"], r["period_label"]) for r in self.sectors
                            if r["period_label"] != "FY2023-24"])

    def test_the_period_gap_is_closed_in_the_register(self):
        gaps = {g["gap_id"]: g for g in completeness.load_data_gaps()}
        row = gaps.get("agriculture-fy2023-24")
        self.assertIsNotNone(row, "the period gap must stay in the register once closed")
        self.assertEqual(row["kind"], "closed")

    def test_the_total_row_states_the_period_it_covers(self):
        """It used to have to say 'spans FY2023-24 to FY2024-25'. With every sector on one
        period it states that period, and if a sector ever drifts again it will go back to
        naming a span rather than quietly asserting a single year."""
        total = [r for r in self.rows if r["sector"] == "TOTAL"][0]
        self.assertEqual(total["period_label"], "FY2023-24")
        self.assertEqual(total["period_start"], min(r["period_start"] for r in self.sectors))
        self.assertEqual(total["period_end"], max(r["period_end"] for r in self.sectors))


class TestTheBenchmarkRegisterCannotPromiseAYearItCannotResolve(unittest.TestCase):
    """Every benchmark row's engine_period must be the reference year the resolver uses.

    WHY THIS EXISTS. benchmark_comparison() resolves the engine side from
    registry.build_all(), which is the REFERENCE YEAR and only the reference year. The
    register nevertheless carries an `engine_period` column per row, and the resolver never
    reads it. All 27 rows happen to say FY2023-24 (or "not estimated"), so the mismatch has
    never produced a wrong number - which is exactly what makes it worth a guard rather than
    a comment, because the first row that says otherwise would be compared against the wrong
    year and would look entirely normal: a source, a category, a plausible ratio.

    The row this was found reaching for is Pakistan's own First Biennial Transparency Report.
    It publishes a full IPCC-category inventory on AR5 GWPs for 2020-21, and it states its
    own convention - "the fiscal year 1993-94 (referred to as 1994)", "Pakistan's 2020-21
    inventory (referred to as 2021)" - so its year IS a Pakistani fiscal year and matches
    FY2020-21 exactly, with no calendar blend and no GWP conversion. That makes it a
    STRICTLY better comparator than any row now in the register, every one of which needs at
    least one approximation. Adding it as data alone would have compared it against
    FY2023-24 and quietly attributed three years of growth to a methodological difference.

    So the guard is deliberately a blocker on a feature, not a restriction on data: honour
    engine_period in the resolver - the nine-year series is published and can answer for a
    historical period - and this test becomes a check that the register and the resolver
    agree about which year each row speaks for. Until then it refuses to let the register
    promise a year the code cannot deliver.
    """

    def test_every_row_declares_the_period_the_resolver_actually_uses(self):
        from pkinv.assets import asset_path
        from pkinv.activity.store import read_rows
        from pkinv.paths import DATA
        rows = read_rows(asset_path(DATA, "benchmarks.csv"))
        self.assertTrue(rows, "the benchmark register is empty")
        reference = {"FY2023-24"}
        # "not estimated" is an engine side that does not exist, which the resolver already
        # handles by emitting n/a - it promises no year, so it cannot promise a wrong one.
        unresolvable = sorted({(r["source"], r["engine_category"], r["engine_period"])
                               for r in rows
                               if r["engine_period"] not in reference
                               and r["engine_period"] != "not estimated"})
        self.assertFalse(
            unresolvable,
            "these benchmark rows declare an engine_period the resolver does not honour - "
            "benchmark_comparison() reads registry.build_all(), which is %s only, so the "
            "engine value beside them would be the reference year's whatever this column "
            "says. Teach the resolver to resolve a historical period from the published "
            "nine-year series before registering them:\n  %s"
            % ("/".join(sorted(reference)), "\n  ".join(map(str, unresolvable))))


if __name__ == "__main__":
    unittest.main()
