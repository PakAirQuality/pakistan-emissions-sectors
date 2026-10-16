"""Gates on the structural trajectories: every axis, every year, priced or
refused - and a refusal is a row with a reason, never a silence.

Run:  python3 -m unittest discover tests
"""
import csv
import os
import unittest
from pkinv.core.reporting_window import CORE_FY_STARTS, CORE_FY_ENDS, CORE_PERIOD_IDS, REFERENCE_PERIOD
from pkinv.core.configurations import REFERENCE
from pkinv.core.io import read_rows
from _support import ROOT

OUT = os.path.join(ROOT, "outputs", "pakemis_structural_trajectories.csv")


def _rows():
    return read_rows(OUT)


class TheTrajectories(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = _rows()

    def test_every_axis_appears_in_every_panel_year(self):
        with open(os.path.join(ROOT, "outputs", "national_axis_register.csv"),
                  newline="", encoding="utf-8") as f:
            axes = {r["axis"] for r in csv.DictReader(
                line for line in f if not line.startswith("#"))}
        cells = {(r["axis"], r["fiscal_end_year"]) for r in self.rows}
        expected = {(a, str(y)) for a in axes for y in CORE_FY_ENDS}
        self.assertEqual(cells, expected)

    def test_statuses_are_closed_and_every_refusal_has_a_reason(self):
        from pkinv.report import structural_trajectories as st
        allowed = {st.PRICED, st.PRICED_REGISTER, st.REFUSED}
        for r in self.rows:
            self.assertIn(r["status"], allowed)
            if r["status"] == st.REFUSED:
                self.assertTrue(r["reason"].strip(),
                                "%s/%s refused without a reason"
                                % (r["axis"], r["fiscal_end_year"]))
            if r["status"] == st.PRICED:
                self.assertAlmostEqual(
                    float(r["delta_Mt"]),
                    float(r["alternative_Mt"]) - float(r["reference_Mt"]),
                    places=4)

    def test_reference_year_rows_are_the_register_read_back(self):
        with open(os.path.join(ROOT, "outputs", "national_axis_register.csv"),
                  newline="", encoding="utf-8") as f:
            register = {r["axis"]: r for r in csv.DictReader(
                line for line in f if not line.startswith("#"))}
        for r in self.rows:
            if r["fiscal_end_year"] != "2024":
                continue
            reg = register[r["axis"]]
            if r["status"] == "priced_reference_register":
                self.assertEqual(r["delta_Mt"], reg["national_delta_Mt"],
                                 r["axis"])

    def test_the_fugitives_axes_price_every_panel_year(self):
        """The engine takes (year, scenario), so a refusal there would be a
        regression, not an evidence statement."""
        for axis in ("fugitive practice", "fugitive activity basis"):
            priced = [r["fiscal_end_year"] for r in self.rows
                      if r["axis"] == axis and r["status"] == "priced"]
            self.assertEqual(sorted(priced), [str(y) for y in CORE_FY_ENDS if y != 2024],
                             axis)

    def test_the_feedstock_axis_prices_every_historical_year(self):
        """Through rc66 this axis refused every year but the reference, because the
        fertiliser class was read from one year's end-use partition. Since rc67 every
        edition's own fertiliser row is held (data/sectors/fugitives/activity/
        fertilizer_gas_class.csv), so the axis is priced in all nine years, and the
        feedstock-inside alternative is above the reference in each."""
        rows = [r for r in self.rows
                if r["axis"] == "post-meter feedstock scope"
                and r["fiscal_end_year"] != "2024"]
        self.assertEqual(sorted(r["fiscal_end_year"] for r in rows),
                         [str(y) for y in CORE_FY_ENDS if y != 2024])
        for r in rows:
            self.assertEqual(r["status"], "priced", r["fiscal_end_year"])
            self.assertGreater(float(r["delta_Mt"]), 0.9, r["fiscal_end_year"])

    def test_no_probability_like_column(self):
        with open(OUT, encoding="utf-8") as f:
            header = next(csv.reader(line for line in f
                                     if not line.startswith("#")))
        for col in header:
            for word in ("probability", "weight", "likelihood", "prior"):
                self.assertNotIn(word, col.lower())

    def test_the_output_regenerates_identically(self):
        from pkinv.report import structural_trajectories as st
        fresh = st.build()
        self.assertEqual(len(fresh), len(self.rows))
        for f_row, s_row in zip(fresh, self.rows):
            for col in st.FIELDS:
                self.assertEqual(str(f_row[col]), s_row[col],
                                 "%s/%s.%s" % (f_row["axis"],
                                               f_row["fiscal_end_year"], col))


if __name__ == "__main__":
    unittest.main()
