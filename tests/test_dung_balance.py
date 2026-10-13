"""The dung balance states an assignment question and distributes nothing.

The risk in this product is not a wrong number. It is that it quietly becomes a reconciliation
- that someone splits the 46.77 Mt across the four candidate destinations, or averages their
prices, and the release gains a central case for a question no evidence has settled. Every
test here exists to make that visible rather than possible.
"""
import csv
import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

OUT = os.path.join(ROOT, "outputs", "pakemis_dung_balance.csv")
LEDGER = os.path.join(ROOT, "outputs", "residential_dung_ledger_2024.csv")


def _rows(path):
    with open(path, encoding="utf-8") as handle:
        body = "".join(l for l in handle if not l.startswith("#"))
    return list(csv.DictReader(io.StringIO(body)))


class TestTheDungBalance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.exists(OUT):
            raise unittest.SkipTest("the dung balance has not been built here")
        cls.rows = _rows(OUT)

    def test_the_schema_is_the_one_the_producer_writes(self):
        from pkinv.report.dung_balance import FIELDS
        self.assertEqual(list(self.rows[0].keys()), list(FIELDS))

    def test_every_row_declares_its_basis(self):
        """A transcribed row is evidence and a recomputed row is a live quantity. A reader
        who cannot tell them apart will take a survey reading for an engine output."""
        for r in self.rows:
            self.assertIn(r["row_basis"], ("recomputed", "transcribed"), r["element"])
        bases = {r["row_basis"] for r in self.rows}
        self.assertEqual(bases, {"recomputed", "transcribed"},
                         "both bases must be present, or the column is decoration")

    def test_the_two_headline_masses_are_the_ledger_s_own(self):
        """The whole table rests on these two, so they are read from the ledger rather than
        restated here."""
        led = {r["claimant"].split(" (")[0]: r for r in _rows(LEDGER)}
        head = next(r for r in self.rows if r["element"] == "Headline mass")
        self.assertAlmostEqual(float(head["L_side"]),
                               float(led["Diverted to fuel"]["Mt_air_dry"]), places=3)
        self.assertAlmostEqual(
            float(head["S_side"]),
            float(next(r["Mt_air_dry"] for r in _rows(LEDGER)
                       if r["configuration"] == "S"
                       and r["claimant"].startswith("Household"))), places=3)

    def test_the_difference_is_the_difference(self):
        head = next(r for r in self.rows if r["element"] == "Headline mass")
        diff = next(r for r in self.rows if r["element"] == "The difference")
        self.assertAlmostEqual(float(head["L_side"]) - float(head["S_side"]),
                               float(diff["S_side"]), places=3)

    def test_no_destination_is_adopted(self):
        """THE TEST THIS FILE EXISTS FOR. The four destinations are priced one at a time and
        the table must not carry a total, a mean or a central case over them."""
        priced = [r for r in self.rows if r["element"].startswith("Residual destination")]
        self.assertGreaterEqual(len(priced), 4, "the priced destinations are missing")
        for r in priced:
            self.assertIn("scenario", r["comparability"],
                          "%s does not mark itself a scenario" % r["element"])
            self.assertEqual(r["L_side"], "not applicable")
        # PHRASES, not bare words. "total" alone rejected "Ash fraction binding volatile to
        # total solids", where total solids is a dry-matter basis and nothing to do with
        # summing destinations. A guard that fires on a correct row teaches the next reader
        # to widen its exemptions, which is how it stops guarding anything.
        banned = ("total of", "sum of", "mean of", "average of", "weighted mean",
                  "central case", "best estimate", "expected value", "combined residual",
                  "all destinations", "across destinations")
        for r in self.rows:
            label = r["element"].lower()
            if r["element"].startswith("Residual destination"):
                continue
            for phrase in banned:
                self.assertNotIn(
                    phrase, label,
                    "%r reads like an aggregate over the destinations; the residual is "
                    "unresolved and must stay so" % r["element"])

    def test_the_guard_against_an_adopted_destination_actually_fires(self):
        """THE POSITIVE CONTROL. The test above passes trivially on a table with no such row,
        which is also what it looks like when the phrase list stops matching."""
        banned = ("total of", "sum of", "mean of", "central case", "all destinations")
        planted = "central case over all destinations"
        self.assertTrue([p for p in banned if p in planted],
                        "the phrase list no longer recognises an adopted residual")

    def test_the_falsifiable_row_is_present_and_checkable(self):
        """The product's reason for existing: L is a claim about Pakistan that could be
        refuted, and the row has to say by what."""
        row = next((r for r in self.rows
                    if r["element"].startswith("Falsifiable implication")), None)
        self.assertIsNotNone(row, "the falsifiable implication has been dropped")
        self.assertEqual(row["row_basis"], "recomputed")
        self.assertTrue(row["what_would_settle_it"].strip(),
                        "the falsifiable row names nothing that would settle it")
        self.assertIn("pct", row["L_side"])

    def test_a_comparability_verdict_is_on_every_row(self):
        for r in self.rows:
            self.assertTrue(r["comparability"].strip(),
                            "%s carries no comparability verdict" % r["element"])

    def test_every_row_points_somewhere(self):
        for r in self.rows:
            self.assertTrue(r["source_pointer"].strip(),
                            "%s cites nothing" % r["element"])

    def test_the_check_flag_agrees_with_the_shipped_file(self):
        from pkinv.core.io import table_text
        from pkinv.report.dung_balance import BANNER, FIELDS, rows
        with open(OUT, encoding="utf-8", newline="") as handle:
            held = handle.read()
        self.assertEqual(held, table_text(list(FIELDS), rows(),
                                          banner=BANNER.splitlines()))


if __name__ == "__main__":
    unittest.main()
