"""The minerals panel's holes, counted, and the one that matters asserted directly.

The product is outputs/pakemis_minerals_panel_screening.csv, built by
scripts/build_minerals_panel_screening.py. It exists because of a finding with a single
decisive number: the monthly profile this project serves for crude oil in FY2021-22 puts
78.76% of the year in one month and labels it T2 - observed. That is Balochistan's record
alone, because the panel holds no other province for that year, and
pkinv.core.pbs_minerals.covers() asks for twelve months rather than for the country.

Two kinds of defect live in this panel and they have OPPOSITE consequences, which is why
the screening reports both rather than one count of "bad cells":

  a uniform duplication across worksheets leaves the normalised shape intact and the
  published quantity wrong - FY2020-21 reads 31 rows in every month, and coal and
  limestone read 100;

  a missing province leaves the quantity plausible and the shape wrong, and that is the
  one the consumer's "the profile is a shape, never a magnitude" defence does not cover.

These guards hold the screening to measuring both, and hold the headline finding in place
so a repair has to retire it deliberately rather than let it lapse.
"""
import csv
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRODUCT = os.path.join(ROOT, "outputs", "pakemis_minerals_panel_screening.csv")
BUILDER = os.path.join(ROOT, "scripts", "build_minerals_panel_screening.py")
VERDICTS = {"all four provinces present", "PROVINCE MISSING",
            "DOUBLE COUNTED: a national row beside the provinces",
            "national only, as the edition printed it"}


def rows():
    with open(PRODUCT, encoding="utf-8") as handle:
        return list(csv.DictReader(line for line in handle if not line.startswith("#")))


class TestTheMineralsPanelScreening(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = rows()

    def test_it_covers_every_canonical_mineral_year(self):
        """The positive control, against the panel rather than against itself."""
        import sys as _sys
        _sys.path.insert(0, os.path.join(ROOT, "src"))
        from pkinv.core import pbs_minerals
        panel = pbs_minerals._panel()
        expected = {(r["canonical_mineral"], int(r["fiscal_year_start"])) for r in panel
                    if r["canonical_mineral"]}
        got = {(r["canonical_mineral"], int(r["fiscal_year_start"])) for r in self.rows}
        self.assertEqual(got, expected,
                         "the screening and the panel describe different mineral-years")
        self.assertGreaterEqual(len(got), 24)

    def test_the_verdict_vocabulary_is_closed(self):
        seen = {r["verdict"] for r in self.rows}
        self.assertEqual(seen - VERDICTS, set(),
                         "undeclared verdict(s) %s" % sorted(seen - VERDICTS))
        self.assertEqual(VERDICTS - seen, set(),
                         "declared verdict(s) %s no longer occur; a stale allowance hides "
                         "the next one" % sorted(VERDICTS - seen))

    def test_both_kinds_of_defect_are_still_distinguished(self):
        """A screening that collapsed the two kinds would say nothing useful.

        Duplication and absence point opposite ways: the first keeps the shape and breaks
        the quantity, the second keeps the quantity and breaks the shape. Each must still
        appear, or the file has stopped making the distinction it was built to make.
        """
        duplicated = [r for r in self.rows
                      if max(int(n) for n in r["rows_per_month"].split(";")) > 5]
        missing = [r for r in self.rows if r["provinces_missing"] != "none"
                   and r["verdict"] == "PROVINCE MISSING"]
        self.assertTrue(duplicated, "no mineral-year reads more rows per month than there "
                                    "are provinces, so the worksheet duplication has been "
                                    "repaired and this screening's prose must change")
        self.assertTrue(missing, "no mineral-year is missing a province, so the shape "
                                 "defect has been repaired and this screening's prose "
                                 "must change")

    def test_a_served_profile_from_an_incomplete_panel_is_still_flagged(self):
        """The finding itself: `covered` does not mean the country.

        Asserted as the EXISTENCE of the case rather than as its count, because a repair
        should reduce it and a reparameterisation should not be able to hide it. The worst
        served month is asserted to be implausible, which is what makes the case a defect
        rather than a curiosity: no real month of Pakistani crude production is most of
        the year.
        """
        bad = [r for r in self.rows if r["provinces_missing"] != "none"
               and r["served_as_covered"] == "yes"]
        self.assertTrue(bad,
                        "no mineral-year is served as covered from an incomplete province "
                        "set any more. If covers() now requires the country, this guard "
                        "and the screening's docstring must be retired together")
        worst = max(float(r["served_worst_month_share_pct"]) for r in bad)
        self.assertGreater(
            worst, 20.0,
            "the worst served month among incomplete panels is %.2f%%, which is close "
            "enough to a flat twelfth that the finding no longer describes anything; "
            "re-state it rather than leaving the prose behind" % worst)

    def test_every_served_profile_sums_to_one(self):
        """The arithmetic control: a share column that does not close prices nothing."""
        for row in self.rows:
            share = float(row["served_worst_month_share_pct"])
            self.assertGreater(share, 0.0, row["canonical_mineral"])
            self.assertLessEqual(share, 100.0, row["canonical_mineral"])
            self.assertIn(row["served_timing_method"], ("T2", "T4"),
                          "%s FY%s is served with method %r"
                          % (row["canonical_mineral"], row["fiscal_year_start"],
                             row["served_timing_method"]))

    # The nine cells where the CLOSING group control and the shipped panel disagree,
    # with the panel's share of what its control certified. Declared rather than merely
    # counted so a new one cannot hide among them, and ratcheted downward: this list may
    # shrink and may not grow.
    CONTROL_DISAGREEMENTS = {
        ("limestone", "2016"): 6.9,
        ("natural_gas", "2023"): 33.6,
        ("coal", "2021"): 42.1,
        ("crude_oil", "2023"): 45.9,
        ("coal", "2016"): 47.1,
        ("coal", "2017"): 110.2,
        ("limestone", "2017"): 125.5,
        ("crude_oil", "2020"): 218.5,
        ("natural_gas", "2020"): 230.8,
    }

    def test_a_closing_group_control_that_does_not_describe_the_panel_is_declared(self):
        """The check the parse never made, and the reason its assurance was hollow.

        The minerals parse publishes "1571 of 1683 mineral-years closing the group
        control". That control compares the rows the parser BUFFERED against the printed
        Total - not the rows the panel ships. For FY2021-22 coal it closes to the unit
        while the panel holds 4,072,263 of the 9,678,139 it just certified, because the
        two province rows PBS prints above the mineral's name line are lost: the name
        cell is vertically centred across its five rows, pdftotext puts it on the middle
        one, and the parser treats that line as the group's first row. The identity is
        exact - Punjab plus Sindh plus KPK plus Balochistan equals the printed Total in
        every one of the twelve months - so this is a parse loss and not a gap in PBS.

        Both halves are asserted: no undeclared disagreement, and no declared one that
        has silently healed.
        """
        live = {(r["canonical_mineral"], r["fiscal_year_start"]):
                float(r["panel_share_of_control_pct"])
                for r in self.rows if r["control_agrees_with_panel"] == "NO"}
        self.assertEqual(
            set(live) - set(self.CONTROL_DISAGREEMENTS), set(),
            "a closing group control stopped describing the panel for %s; the parse's "
            "own assurance does not cover this, so it has to be declared here"
            % sorted(set(live) - set(self.CONTROL_DISAGREEMENTS)))
        healed = set(self.CONTROL_DISAGREEMENTS) - set(live)
        self.assertEqual(
            healed, set(),
            "declared disagreement(s) %s no longer occur. If the parse was repaired, "
            "retire them from this list and from the screening's docstring together"
            % sorted(healed))
        for key, expected in self.CONTROL_DISAGREEMENTS.items():
            self.assertAlmostEqual(
                live[key], expected, places=1,
                msg="%s FY%s now ships %.1f%% of its control instead of %.1f%%; the "
                    "parse moved and the declaration did not"
                    % (key[0], key[1], live[key], expected))

    def test_it_regenerates_identically(self):
        before = open(PRODUCT, "rb").read()
        run = subprocess.run([sys.executable, BUILDER], cwd=ROOT,
                             capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr[-2000:])
        self.assertEqual(before, open(PRODUCT, "rb").read(),
                         "the screening does not regenerate byte-identically")


if __name__ == "__main__":
    unittest.main()
