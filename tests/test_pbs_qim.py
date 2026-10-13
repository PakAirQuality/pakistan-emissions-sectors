"""Gates on the PBS QIM ingest and the cement profile it replaced.

WHAT IS BEING PROTECTED. Cement's monthly shape used to be borrowed from calendar 2022 and
graded TE4 for that reason. It now comes from each year's own fiscal QIM edition and is TE2.
That is an upgrade earned by new evidence, and these tests exist so it stays earned: if the
panel ever stops covering a year, the profile must degrade back to a declared borrowing rather
than keep the better class over a worse shape.

THE PARSE'S OWN CONTROLS ARE THE ADMISSIBILITY TEST. Every row prints its own annual figure,
and a row that fails is quarantined rather than repaired. The quarantine is listed here rather
than counted, so a new failure cannot be absorbed by an old one being fixed.

Run:  python3 -m unittest discover tests
"""

from pkinv.assets import asset_path
import csv
import os
import subprocess
import sys
import unittest
from pkinv.core.io import read_rows
from _support import ROOT


PANEL = asset_path(ROOT, "data", "activity", "monthly", "pbs_qim_month_item.csv")
SUMMARY = os.path.join(ROOT, "outputs", "pbs_qim_parse_summary.csv")
QUARANTINE = os.path.join(ROOT, "outputs", "pbs_qim_quarantine.csv")

FISCAL_YEARS = tuple(range(2015, 2024))

# The item-years PBS's OWN arithmetic does not close, listed rather than counted. Both are
# rows whose twelve printed months cannot sum to the annual figure printed beside them.
EXPECTED_QUARANTINE = {(fy, "16") for fy in ("2015", "2016", "2017", "2018", "2019", "2020",
                                             "2021", "2023")} | {("2021", "80")}


def _rows(path):
    return read_rows(path)


class TheParseClosesOnItsOwnControls(unittest.TestCase):
    def setUp(self):
        self.summary = _rows(SUMMARY)[0]

    def test_all_nine_editions_were_parsed(self):
        self.assertEqual(9, int(self.summary["files_parsed"]))

    def test_the_closure_rate_is_not_quietly_degrading(self):
        """A floor, not a target. Rows that fail are PBS's arithmetic, not the parser's, and
        if that changes it is a finding about a new edition rather than a number to relax."""
        self.assertGreaterEqual(float(self.summary["closure_rate_pct"]), 99.0)

    def test_the_quarantine_is_exactly_the_declared_rows(self):
        found = {(r["fiscal_year_start"], r["item_no"]) for r in _rows(QUARANTINE)}
        self.assertEqual(EXPECTED_QUARANTINE, found)

    def test_a_quarantined_row_keeps_its_raw_text_and_both_controls(self):
        for row in _rows(QUARANTINE):
            self.assertTrue(row["raw"].strip())
            self.assertNotEqual(row["months_sum"], row["annual_printed"])
            self.assertNotEqual(row["months_mean"], row["annual_printed"])

    def test_the_rotation_control_is_live(self):
        """The positive control. If almost every series were flat, "the months parsed" would
        be true and worthless, because a flat series is indistinguishable from a mis-sliced
        one. This asserts most series carry a shape a rotation would disturb."""
        detectable = int(self.summary["rotation_detectable_series"])
        total = int(self.summary["item_years_closed"])
        self.assertGreater(detectable / total, 0.85,
                           "only %d of %d series are distinguishable from their own rotation"
                           % (detectable, total))

    def test_both_layout_families_were_read(self):
        """Seven editions print a Weight column and two do not. If this ever reads 9 or 0, one
        layout is being forced through the other's rule and the closure test is the only thing
        standing between that and a silently shifted month."""
        self.assertEqual(7, int(self.summary["editions_with_weight_column"]))


class TheIndexRowsAreNotTonnages(unittest.TestCase):
    def setUp(self):
        self.rows = _rows(PANEL)

    def test_index_rows_are_marked_and_carry_the_mean_control(self):
        index = [r for r in self.rows if r["row_kind"] == "index"]
        self.assertTrue(index, "no index rows found - Table 2 prints group index rows and "
                               "reading them as quantities is the defect this marks")
        self.assertEqual({"mean"}, {r["annual_control"] for r in index})

    def test_no_index_row_is_ever_canonical(self):
        """An index and a tonnage are different kinds of number, and once normalised into
        twelve shares nothing downstream could tell them apart."""
        for row in self.rows:
            if row["row_kind"] == "index":
                self.assertEqual("", row["canonical_item"])

    def test_the_reader_refuses_an_index_row(self):
        from pkinv.core import pbs_qim
        rows = [dict(r, canonical_item="cement", row_kind="index")
                for r in self.rows if r["item_no"] == "83"
                and r["fiscal_year_start"] == "2023"]
        with self.assertRaises(ValueError):
            pbs_qim.series("cement", 2023, rows)


class CementTakesItsOwnMonths(unittest.TestCase):
    def test_every_fiscal_year_is_covered(self):
        from pkinv.core import pbs_qim
        for fy_start in FISCAL_YEARS:
            self.assertTrue(pbs_qim.covers(pbs_qim.CEMENT, fy_start),
                            "cement FY%d-%02d lost its own months"
                            % (fy_start, (fy_start + 1) % 100))

    def test_each_year_of_shares_sums_to_one(self):
        from pkinv.core import pbs_qim
        for fy_start in FISCAL_YEARS:
            shares = pbs_qim.profile(pbs_qim.CEMENT, fy_start)
            self.assertEqual(12, len(shares))
            self.assertAlmostEqual(1.0, sum(shares.values()), places=12)

    def test_the_years_differ_from_one_another(self):
        """The whole point of parsing nine editions. If every year returned the same twelve
        shares, the panel would be a borrowed shape with extra steps."""
        from pkinv.core import pbs_qim
        shapes = {fy: tuple(round(v, 9) for _m, v in
                            sorted(pbs_qim.profile(pbs_qim.CEMENT, fy).items()))
                  for fy in FISCAL_YEARS}
        self.assertEqual(len(FISCAL_YEARS), len(set(shapes.values())))

    def test_the_layer_reports_an_own_year_shape_at_T2(self):
        from pkinv.sectors.ippu import monthly as ippu_monthly
        _shares, method, _basis, own = ippu_monthly.shape(2023)
        self.assertTrue(own)
        self.assertEqual("T2", method)

    def test_it_degrades_to_a_declared_borrowing_when_a_year_is_absent(self):
        """The property that keeps the class honest. A year the panel cannot serve must fall
        back to the borrowed shape AND say T3 - not keep T2 over a shape from another year."""
        from pkinv.core import pbs_qim
        fallback = {"x": 1.0}
        shares, method, own = pbs_qim.profile_or_borrowed(
            pbs_qim.CEMENT, 1999, fallback, fallback_method="T3")
        self.assertFalse(own)
        self.assertEqual("T3", method)
        self.assertEqual(fallback, shares)

    def test_the_parse_reproduces_the_earlier_hand_transcription(self):
        """An independent check the parser cannot fake: the calendar-2022 window this
        replaced was transcribed by hand from the same two editions."""
        hand = {r["month"]: float(r["cement_kt"]) for r in _rows(
            asset_path(ROOT, "data", "activity", "ippu", "cement_monthly_2022.csv"))}
        parsed = {}
        for row in _rows(PANEL):
            if row["item_no"] == "83":
                parsed["%s-%s" % (row["month"][:4], row["month"][4:])] = float(row["quantity"])
        self.assertEqual(12, len(hand))
        for month, value in sorted(hand.items()):
            self.assertAlmostEqual(value, parsed[month], places=6, msg=month)


class TheProfileOnlyDecidesWhen(unittest.TestCase):
    def test_a_reshape_cannot_move_the_annual_figure(self):
        """The contract every monthly layer is held to, checked on the one that changed."""
        from pkinv.sectors.ippu import monthly as ippu_monthly
        components, month_rows = ippu_monthly.rows()
        annual = {}
        for row in components:
            key = (row["category"], row["subitem"], row["gas"])
            annual[key] = annual.get(key, 0.0) + float(row["co2e_Mt_AR5"])
        monthly = {}
        for row in month_rows:
            key = (row["category"], row["subitem"], row["gas"])
            monthly[key] = monthly.get(key, 0.0) + float(row["co2e_Mt_AR5"])
        self.assertEqual(set(annual), set(monthly))
        for key, value in annual.items():
            self.assertAlmostEqual(value, monthly[key], places=9, msg=str(key))


class ItIsReproducible(unittest.TestCase):
    @unittest.skipUnless(os.path.exists(asset_path(ROOT, "data", "raw", "pbs", "qim")),
                         "raw QIM files not held")
    def test_re_running_the_ingest_reproduces_the_committed_table(self):
        with open(PANEL, encoding="utf-8") as handle:
            before = handle.read()
        subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "ingest_pbs_qim.py")],
                       cwd=ROOT, stdout=subprocess.DEVNULL, check=True)
        with open(PANEL, encoding="utf-8") as handle:
            self.assertEqual(before, handle.read(), "the ingest is not deterministic")


if __name__ == "__main__":
    unittest.main()
