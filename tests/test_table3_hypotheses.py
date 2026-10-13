"""Gates on the Table 3 hypothesis register.

The register is the twelfth review's demand that "a scope difference only NEPRA
can close" become an enumeration: which readings of Table 3's coal row could
produce the x2.01, which held diagnostics discriminate against them, and which
no held source can test. Its contract: statuses come from a closed vocabulary,
every row cites the diagnostic it is scored against, the file regenerates
identically from the live evidence, and it never selects - selection stays with
the declared rule on the power_grid_control family rows.

Run:  python3 -m unittest discover tests
"""
import csv
import os
import unittest
from pkinv.assets import asset_path
from pkinv.core.io import read_rows
from _support import ROOT

OUT = os.path.join(ROOT, "outputs", "power_table3_hypotheses.csv")

EXPECTED_IDS = ("imported-cv-convention",
                # rc64: the panel constraint. Every other row explains a CONSTANT
                # bias; the adjudication shows the bias changes sign, so none of
                # them alone can hold across the ledger span.
                "basis-change-fy2021-22", "gross-vs-net-toe", "ke-inclusion",
                "coal-stock-change", "non-power-coal-scope",
                "heat-input-vs-output", "table3-correct-as-published")


def _rows():
    return read_rows(OUT)


class TheRegister(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = _rows()
        cls.by_id = {r["hypothesis_id"]: r for r in cls.rows}

    def test_the_enumeration_is_exactly_the_declared_hypotheses(self):
        self.assertEqual(set(EXPECTED_IDS), set(self.by_id))

    def test_statuses_are_from_the_closed_vocabulary(self):
        from pkinv.sectors.power import table3_hypotheses as th
        for r in self.rows:
            self.assertIn(r["status"], th.STATUSES, r["hypothesis_id"])

    def test_every_row_cites_a_resolvable_evidence_source(self):
        for r in self.rows:
            fname = r["evidence_source"].split("#", 1)[0]
            base = ROOT if fname.startswith("data/") else os.path.join(ROOT,
                                                                       "outputs")
            self.assertTrue(os.path.exists(asset_path(base, fname)),
                            "%s cites %s" % (r["hypothesis_id"], fname))

    def test_an_untestable_row_names_the_closing_acquisition(self):
        for r in self.rows:
            if r["status"] == "untestable-with-held-sources":
                self.assertTrue(r["what_would_close_it"].strip(),
                                r["hypothesis_id"])

    def test_ke_inclusion_is_the_one_discriminated_reading(self):
        """K-Electric's ledger fuel is gas and furnace oil - a coal factor of
        two cannot ride its boundary. The other readings stay open, which is
        the register's honest finding."""
        discriminated = [r["hypothesis_id"] for r in self.rows
                         if r["status"] == "discriminated-against"]
        self.assertEqual(["ke-inclusion"], discriminated)

    def test_the_register_selects_nothing(self):
        """The 57.82 selection lives with the family's declared rule; a status
        of "selected" or any probability-like column here would be the register
        crossing into the decision it exists to keep open."""
        header = next(csv.reader(line for line in open(OUT, encoding="utf-8")
                                 if not line.startswith("#")))
        for col in header:
            for word in ("probability", "weight", "likelihood", "prior",
                         "selected"):
                self.assertNotIn(word, col.lower())

    def test_the_output_regenerates_identically(self):
        from pkinv.sectors.power import table3_hypotheses as th
        fresh = th.build()
        self.assertEqual(len(fresh), len(self.rows))
        for f_row, s_row in zip(fresh, self.rows):
            for col in th.FIELDS:
                self.assertEqual(str(f_row[col]), s_row[col],
                                 "%s.%s" % (f_row["hypothesis_id"], col))


if __name__ == "__main__":
    unittest.main()
