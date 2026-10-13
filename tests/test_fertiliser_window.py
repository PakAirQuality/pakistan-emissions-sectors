"""rc39 A2: the fertiliser composition is the fiscal year's own, and the window is proven.

The national FracGASF weights BOTH the ammonia layer and the synthetic indirect-N2O row. Before
this pass it was weighted by NFDC Annex-7, whose year runs April-March, so the composition came
from a period that is not the one the inventory reports. The module knew and argued the shares
were robust to the choice; these tests replace that argument with the right window.

What is pinned here is not just the number but the SELECTION: twelve months, the first Jul-2023,
the last Jun-2024, and nothing from the Kharif that precedes them. A weighting drawn from the
wrong window is not visibly wrong in its output - it is a plausible factor computed over the
wrong period - so the selection is what has to be tested.
"""

from pkinv.assets import asset_path
import csv
import os
import sys
import unittest

from _support import OUTPUTS, ROOT, read_rows

from pkinv.sectors.agriculture import fertiliser_mix as fm
from pkinv.sectors.agriculture.ef_library import InventoryData

# The audit's value, reproduced to 1e-10 by the engine.
FRACGASF = 0.1608191992
ANNEX5_N_T = 3746448.0          # the annexe's own nitrogen over the window
AUDITED_N_T = 3775000.0         # the activity datum in fertilizer_2024.csv


class TestTheWindowIsTheFiscalYear(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = InventoryData()
        cls.rows = fm.annex5_window()

    def test_exactly_twelve_months(self):
        months = {(r["calendar_year"], r["month"]) for r in self.rows}
        self.assertEqual(len(months), 12, sorted(months))

    def test_the_first_month_is_july_2023_and_the_last_is_june_2024(self):
        order = {m: i for i, m in enumerate(
            ["Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
             "Jan", "Feb", "Mar", "Apr", "May", "Jun"])}
        months = sorted({(r["calendar_year"], r["month"]) for r in self.rows},
                        key=lambda cm: (order[cm[1]] >= 6, order[cm[1]]))
        got = sorted({(r["calendar_year"], r["month"]) for r in self.rows},
                     key=lambda cm: (int(cm[0]), order[cm[1]] if int(cm[0]) == 2024
                                     else order[cm[1]]))
        self.assertEqual(got[0], ("2023", "Jul"))
        self.assertEqual(got[-1], ("2024", "Jun"))
        del months

    def test_no_row_from_the_preceding_kharif(self):
        """Apr-Jun 2023 belongs to the previous fiscal year. Annex-7's April-March year is
        exactly where those months used to enter the weighting."""
        strays = [(r["calendar_year"], r["month"]) for r in self.rows
                  if r["calendar_year"] == "2023" and r["month"] in ("Apr", "May", "Jun")]
        self.assertFalse(strays, "the preceding Kharif is inside the window: %s" % strays)

    def test_the_window_is_checked_not_trusted(self):
        """The label alone must not be enough - a relabelled row has to raise."""
        with self.assertRaises((ValueError, KeyError)):
            fm.annex5_window(label="no-such-year")


class TestTheFactorAndItsComposition(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = InventoryData()

    def test_the_weighted_factor_is_the_audited_value(self):
        weighted, _, _ = fm.weighted_fracgasf(self.data)
        self.assertAlmostEqual(weighted, FRACGASF, places=9)

    def test_the_single_accessor_returns_it(self):
        """Both layers reach the factor through fracgasf(); if this drifts from the line
        above, one of them is on a different number for the same nitrogen."""
        value, source = fm.fracgasf(self.data)
        self.assertAlmostEqual(value, FRACGASF, places=9)
        self.assertIn("Annex-5", source)

    def test_the_shares_sum_to_one(self):
        shares, _ = fm.national_shares(self.data)
        self.assertAlmostEqual(sum(shares.values()), 1.0, places=12)

    def test_urea_dominates_and_the_shares_are_the_annexes(self):
        shares, total = fm.national_shares(self.data)
        self.assertAlmostEqual(shares["Urea"], 0.807769, places=5)
        self.assertAlmostEqual(total, ANNEX5_N_T, delta=1.0)

    def test_the_annexe_is_composition_not_magnitude(self):
        """0.756% lower than the activity datum, and that gap must stay VISIBLE rather than
        being reconciled away - the annexe supplies shares, fertilizer_2024.csv supplies the
        nitrogen."""
        _, total = fm.national_shares(self.data)
        audited = self.data.fertilizer["nitrogen_N_offtake"]["value_t"]
        self.assertAlmostEqual(audited, AUDITED_N_T, delta=1.0)
        self.assertAlmostEqual(100.0 * (1.0 - total / audited), 0.756, places=2)


class TestThePublishedComposition(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = read_rows(os.path.join(
            OUTPUTS, "agriculture_fertiliser_composition_2024.csv"))

    def test_it_is_published(self):
        self.assertTrue(self.rows)
        self.assertIn("TOTAL", [r["product"] for r in self.rows])

    def test_the_total_row_carries_the_factor(self):
        total = next(r for r in self.rows if r["product"] == "TOTAL")
        self.assertAlmostEqual(float(total["contribution"]), FRACGASF, places=9)

    def test_the_total_row_states_both_nitrogen_figures(self):
        total = next(r for r in self.rows if r["product"] == "TOTAL")
        self.assertIn("COMPOSITION only", total["note"])
        self.assertAlmostEqual(float(total["nitrogen_t"]), ANNEX5_N_T, delta=1.0)

    def test_the_product_shares_reproduce_the_factor(self):
        """Sigma share x EF over the published rows == the published total."""
        acc = 0.0
        for r in self.rows:
            if r["product"] == "TOTAL" or not r["contribution"]:
                continue
            acc += float(r["contribution"])
        self.assertAlmostEqual(acc, FRACGASF, places=9)

    def test_the_zero_nitrogen_products_say_why_they_are_there(self):
        for r in self.rows:
            if r["product"] != "TOTAL" and not float(r["n_content_frac"] or 0):
                self.assertIn("no nitrogen", r["note"], r["product"])


class TestTheAgencyPanelCorroboratesTheAnnexe(unittest.TestCase):
    """Annex-5 is the printed national row; the monthly panel is the same publication
    decomposed to twelve supplying agencies. They agree to 3 t in 10.3 Mt, and the residual
    is rounding in the agency rows - which is the reason the printed row is the source."""

    def test_they_agree_to_within_rounding(self):
        import collections
        a5 = collections.defaultdict(float)
        for r in fm.annex5_window():
            a5[r["product"].upper()] += float(r["offtake_product_tonnes"] or 0)
        panel = collections.defaultdict(float)
        path = asset_path(ROOT, "data", "activity", "monthly", "nfdc_month_product_offtake.csv")
        with open(path, newline="", encoding="utf-8") as handle:
            for r in csv.DictReader(l for l in handle if not l.startswith("#")):
                if r["fiscal_year_start"] == "2023":
                    panel[r["product"].upper()] += float(r["tonnes"] or 0)
        self.assertEqual(set(a5), set(panel) - {"TSP"} | (set(a5) & {"TSP"}))
        worst = max(abs(panel.get(p, 0.0) - v) for p, v in a5.items())
        self.assertLess(worst, 5.0, "the two vintages of one publication disagree by %.1f t"
                        % worst)


if __name__ == "__main__":
    unittest.main()
