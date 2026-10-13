"""A partition printed for a reader must sum to the total printed beside it.

WHY THIS TEST EXISTS. Table 2 of the national article was captioned "Completeness across
108 category--gas combinations" and its body listed four notation keys:

    E 52    NE 43    IE 8    NO 4

which sum to 107. The missing cell is soda ash production (2.B.7, CO2), the single NA in
outputs/completeness.csv. A reader adding the column got a different answer from the caption,
and the defect survived every guard in this repository because each half was separately
correct:

  * the 108 is a registered claim and resolves against the product;
  * the four counts are GENERATED macros carrying query receipts, so the quantity sweep
    trusts them in full ("generated sections count in full: their bytes equal a fresh
    render");
  * and nothing anywhere compared the parts with the whole.

The query simply never asked for NA. `paper_artefacts.csv` registered four keys and the
renderer loops over whatever it is given, so the table was a faithful rendering of an
incomplete question. That is the shape worth guarding: not a wrong number, but a complete-
looking set that omits a member.

It was found by cross-checking an editorial rewrite's notes against the product, which is to
say by a human reading the table and adding it up. That is not a repeatable process, so this
is.

WHAT THIS HOLDS. For each registered partition, the rendered parts sum to the total the
document prints. Adding a notation key to the product without adding it to the query now
fails here instead of printing a table that does not add up.
"""
import io
import os
from pkinv.paths import PAPER_NATIONAL_MAIN_REL  # noqa: E402
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.core.io import read_rows                                      # noqa: E402

# (what it partitions, the generated file, the macro prefix, the product, its key column)
PARTITIONS = [
    ("the notation keys over the category--gas matrix",
     os.path.join(PAPER_NATIONAL_MAIN_REL, "sections", "gen_tab_completeness.tex"),
     "genCompletenessCount",
     "outputs/completeness.csv",
     "notation_key"),
]


class TestAPrintedPartitionSumsToItsTotal(unittest.TestCase):
    def test_the_rendered_parts_sum_to_the_product_total(self):
        for what, generated, prefix, product, column in PARTITIONS:
            path = os.path.join(ROOT, generated)
            if not os.path.exists(path):
                self.skipTest("%s has not been generated in this checkout" % generated)
            text = io.open(path, encoding="utf-8").read()
            parts = {m.group(1): int(m.group(2)) for m in re.finditer(
                r"renewcommand\{\\%s([A-Za-z]+)\}\{(\d+)\}" % prefix, text)}
            rows = read_rows(product)
            self.assertEqual(
                sum(parts.values()), len(rows),
                "%s: the table renders %s = %d, and %s has %d rows. A reader adding the "
                "column gets a different answer from the caption. Every member of the "
                "partition needs its own registered query in "
                "paper_national/queries/paper_artefacts.csv."
                % (what, " + ".join("%s %d" % kv for kv in sorted(parts.items())),
                   sum(parts.values()), product, len(rows)))

    def test_every_key_in_the_product_is_rendered(self):
        """The same question from the other side, which is how the omission would be found.

        Summing to the total is necessary and not sufficient: two compensating errors would
        pass it. This asserts the SET of keys matches, so a key that exists in the product
        and not in the query fails whatever its count happens to be.
        """
        for what, generated, prefix, product, column in PARTITIONS:
            path = os.path.join(ROOT, generated)
            if not os.path.exists(path):
                self.skipTest("%s has not been generated in this checkout" % generated)
            text = io.open(path, encoding="utf-8").read()
            rendered = {m.group(1) for m in re.finditer(
                r"renewcommand\{\\%s([A-Za-z]+)\}\{\d+\}" % prefix, text)}
            held = {r[column] for r in read_rows(product) if r[column]}
            self.assertEqual(
                rendered, held,
                "%s: the table renders keys %s while %s holds %s. The difference is %s."
                % (what, sorted(rendered), product, sorted(held),
                   sorted(held ^ rendered)))

    def test_the_guard_is_watching_a_real_partition(self):
        """A registry with no entries would pass both tests above forever."""
        self.assertTrue(PARTITIONS, "no partition is registered")
        for what, generated, prefix, product, column in PARTITIONS:
            path = os.path.join(ROOT, generated)
            if not os.path.exists(path):
                continue
            text = io.open(path, encoding="utf-8").read()
            found = re.findall(r"renewcommand\{\\%s([A-Za-z]+)\}\{\d+\}" % prefix, text)
            self.assertGreater(
                len(found), 1,
                "%s: only %d part(s) found with prefix %s - the macro naming has changed "
                "and this guard is reading nothing" % (generated, len(found), prefix))


if __name__ == "__main__":
    unittest.main()
