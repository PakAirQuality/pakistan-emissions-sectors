"""The railway divergence, placed: who disagrees, in which direction, and since when.

WHY THIS TEST EXISTS. Section 10 reported the railway disagreement against ONE official
filing, BUR-1, as "a factor of ten", while the register beside it
(outputs/railways_official_comparison_2024.csv) carried five. Three facts were sitting in the
shipped product and in no manuscript, and each of them changes what the disagreement means:

  the CURRENT submission is worse. Pakistan's first Common Reporting Tables - the filing this
  paper elsewhere prefers BECAUSE a cell can be audited - are 11.6 times this inventory,
  against BUR-1's 8.7. A reader given only BUR-1 could take the divergence for an artefact of
  a superseded narrative filing.

  the OLDEST filing runs the other way. The Initial National Communication implies 0.5575 Mt
  for FY1993-94, 11.9 per cent BELOW this inventory's reconstruction of the same period. It is
  the one official comparison this inventory does not win, and Section 1 had claimed the INC
  "is not used as a comparator anywhere in this paper" while the register used it.

  so the error can be DATED. Between the only two filings that report railways separately the
  official figure rose 7.3x while this inventory's reconstruction FELL 26 per cent. The
  disagreement is not a standing feature of Pakistan's reporting; it entered the record
  between 2003 and 2022, and no more precisely than that, because the two filings in between
  report only the 1.A.3 aggregate.

And a bound that needs no traffic statistic: the operator's own fuel history, back to 1950,
peaks at 2.3049 Mt/yr in 1965-70, when Pakistan Railways burned 48,720 t of coal and
542,078 t of furnace oil a year. BUR-1's 4.06 Mt is 1.8 times that steam-era peak.

WHAT IS ASSERTED. The three directions, the dating, the peak and the ceiling - and the two
things the claims registry cannot reach: that the peak row is the one whose period the prose
names, and that the ratio the railways paper prints uses the SAME denominator as the product
beside it. That second one is the defect this file was written for: four sites said "eleven
times the metered fuel" as a spelled-out WORD, invisible to the quantity sweep, resting on
FY2021-22's metered mass alone (120.1 kt, 11.0x) where the product declares the mean of the
two fiscal years calendar 2022 straddles (104.4 kt, 12.6x). The word understated the
divergence and nothing could see it.

NOT ASSERTED: any claim about how the filing went wrong. The activity cell and the
implied-factor cells are two separate defects - the activity produces the factor of ten, the
factors move only the non-CO2 terms - and the sector paper documents them separately.
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.core.io import read_rows                                      # noqa: E402

COMPARISON = os.path.join(ROOT, "outputs", "railways_official_comparison_2024.csv")
HISTORY = os.path.join(ROOT, "outputs", "railways_fuel_history.csv")
BUR1_MT = 4.06


class TestTheRailwayDivergenceIsPlaced(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (os.path.exists(COMPARISON) and os.path.exists(HISTORY)):
            raise unittest.SkipTest("the railway benchmark products are not built here")
        cls.by = {r["benchmark_id"]: r for r in read_rows(COMPARISON, comments=True)}
        cls.history = read_rows(HISTORY, comments=True)

    def _ratio(self, key):
        return float(self.by[key]["ratio_official_over_own"])

    def test_the_current_submission_is_worse_than_the_superseded_one(self):
        crt, bur1 = self._ratio("crt2022"), self._ratio("bur1")
        self.assertGreater(
            crt, bur1,
            "the CRT (%.2f) is no longer worse than BUR-1 (%.2f). Section 10 says the "
            "divergence is live in the current filing rather than an artefact of the "
            "superseded narrative one, and that sentence would need restating." % (crt, bur1))

    def test_the_oldest_filing_runs_the_other_way(self):
        """The one official comparison this inventory does not win, and it is reported."""
        inc = self._ratio("inc1994")
        self.assertLess(
            inc, 1.0,
            "the Initial National Communication no longer sits BELOW this inventory "
            "(ratio %.3f). Section 10 reports it precisely because it is the comparison "
            "that runs against us, and Section 1's 'used once, as a labelled magnitude "
            "check' depends on it existing at all." % inc)
        self.assertEqual(
            self.by["inc1994"]["year_label"], "FY1993-94",
            "the INC row's year moved; the reconstruction it is compared against is the "
            "1990-95 quinquennial average and the pairing is what makes it a magnitude check")

    def test_the_official_figure_rose_while_this_inventory_fell(self):
        """The dating. Both sides, or the direction claim is half a claim."""
        official_rise = BUR1_MT / float(self.by["inc1994"]["official_Mt_co2e"])
        own_change = (float(self.by["bur1"]["own_Mt_co2e"])
                      / float(self.by["inc1994"]["own_Mt_co2e"]))
        self.assertGreater(official_rise, 5.0,
                           "the official figure no longer rises by the factor Section 10 "
                           "states (%.2f)" % official_rise)
        self.assertLess(
            own_change, 1.0,
            "this inventory's own reconstruction no longer FALLS between the two filings "
            "(%.3f). Section 10's point is that the two series move in opposite directions; "
            "if they now move together the dating argument is gone." % own_change)

    def test_the_dating_cannot_be_made_more_precise_than_the_paper_claims(self):
        """The stated LIMIT. If a filing gains a railway row, the paper may say more.

        Asserted so the caveat cannot outlive its reason: Section 10 says the error cannot be
        dated more closely than 2003-2022 BECAUSE the intervening filings report only the
        1.A.3 aggregate. That is a fact about the register, and it can change.
        """
        for key in ("tnc2021", "btr2024"):
            row = self.by[key]
            self.assertFalse(
                (row["official_Mt_co2e"] or "").strip(),
                "%s now carries a railway figure, so the divergence CAN be dated more "
                "closely than 'between 2003 and 2022' and Section 10 understates what the "
                "evidence supports: %s" % (key, row["match_basis"]))
            self.assertIn("not separately reported", row["match_basis"],
                          "%s no longer records WHY it carries no figure" % key)

    def test_the_official_figure_exceeds_the_steam_era_peak(self):
        peak = max(self.history, key=lambda r: float(r["co2e_Mt_AR5_indicative"]))
        value = float(peak["co2e_Mt_AR5_indicative"])
        self.assertGreater(
            BUR1_MT / value, 1.0,
            "BUR-1's %.2f Mt no longer exceeds the all-time peak of %.4f Mt/yr (%s); "
            "Section 10's ceiling argument would be false"
            % (BUR1_MT, value, peak["period"]))
        self.assertEqual(
            peak["period"], "1965-70",
            "the peak moved to %s. Section 10 names the period in PROSE and its coal and "
            "furnace-oil tonnages are read from the peak ROW, so the numbers would update "
            "and the year would not - three facts about different years in one sentence, "
            "which is the defect the matched-year table was built to fix."
            % peak["period"])


if __name__ == "__main__":
    unittest.main()
