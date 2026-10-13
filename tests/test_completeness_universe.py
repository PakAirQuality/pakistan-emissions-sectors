"""A category a sector marks NE must appear in the national completeness table.

WHY THIS TEST EXISTS. outputs/completeness.csv states its own purpose as listing "every
category x gas". On 2026-10-05 it listed 9 IPPU codes while outputs/ippu_completeness_2024.csv
listed 36, and the 28 in between had no row at all: 2.A.3, 2.A.4, 2.B.3-2.B.6, 2.B.8-2.B.10,
2.C.2-2.C.7, 2.D.2, 2.D.3, 2.E, 2.F.2-2.F.6, 2.G.1-2.G.4 and 2.H. All 28 were marked NE by the
sector, one at medium-high materiality.

The module had already been burned by the same shape and says so in its own docstring:
electricity generation and road transport, the second and third largest categories in the
country, were once absent from this table entirely and nothing complained. The guard added
then walks registry.all_sectors() and fails when a registered category has no ESTIMATED row.
That closes one direction. A category a sector marks NE could still be missing from the
national table, because nothing compared the two NE universes - so the table could be a
complete partition of an incomplete universe, which is what it was.

The distinction matters more than the count. The earlier repair (also 2026-10-05) made the
rendered partition sum to its own total: 52+43+8+4+1 was 107 against a 108-row product,
because the soda-ash NA cell had no registered query. That was a partition defect. This is a
UNIVERSE defect, and a correct partition of the wrong universe reads exactly like a correct
table.

WHAT THIS HOLDS. Every (code) a sector's own completeness product marks NE appears in the
national table. It is deliberately one-directional on the code: the national table carries
rows no sector product does (cross-sector transfers, the air family, LULUCF), and requiring
the reverse would be wrong.
"""
import glob
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.core.io import read_rows                                      # noqa: E402

NATIONAL = "outputs/completeness.csv"

# Sector completeness products and the column that carries their IPCC code. A sector whose
# product is added later is picked up by the glob; the column name is checked rather than
# assumed, because the national table uses `code` and the sector products use `ipcc_code`.
SECTOR_GLOB = "outputs/*_completeness_*.csv"
CODE_COLUMNS = ("ipcc_code", "code")
KEY_COLUMNS = ("notation_key_2024", "notation_key")


def _column(row, candidates):
    for name in candidates:
        if name in row:
            return name
    return None


class TestEverySectorGapIsInTheNationalTable(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = os.path.join(ROOT, NATIONAL)
        if not os.path.exists(path):
            raise unittest.SkipTest("%s has not been generated here" % NATIONAL)
        cls.national = read_rows(NATIONAL)
        cls.codes = {r["code"] for r in cls.national}

    def test_the_sweep_finds_sector_products(self):
        """A glob that matches nothing would pass the real test forever."""
        found = glob.glob(os.path.join(ROOT, SECTOR_GLOB))
        self.assertGreater(
            len(found), 0,
            "no sector completeness product matched %s; the naming has changed and this "
            "guard is comparing the national table against nothing" % SECTOR_GLOB)

    def _declared_at_or_above(self, code):
        """Is this code's gap declared by the national table, at ITS grain?

        The national table may carry a sub-code directly, or declare the gap at a PARENT
        code with its own NE row. Both are honest: fugitives marks 1.B.2.a.i, .a.vi, .a.vii,
        .b.i, .b.vi and .b.vii NE, and the national table carries three rows at code 1.B.2 -
        one estimated, plus NE rows for "refining, well..." and "gas transmission...", the
        latter called the largest omission inside 1.B.2. The gap is declared; only the key
        granularity differs, and requiring code-level identity would flag a table that is
        telling the reader the truth.

        What it does NOT excuse is absence at every grain. None of the 28 IPPU codes added on
        2026-10-05 had a row at any level: there is no bare "2.A" row, and 2.A.2 is not a
        parent of 2.A.3. That is the case this guard is for.

        The weakening is real and worth naming: a gap declared only at a parent is guarded as
        a parent, so a newly unestimated 1.B.2.x would pass here. The per-sub-code check lives
        with the sector, which is where the sub-code vocabulary lives.
        """
        if code in self.codes:
            return True
        parts = code.split(".")
        for cut in range(len(parts) - 1, 0, -1):
            parent = ".".join(parts[:cut])
            if any(r["code"] == parent and (r["notation_key"] or "").upper() in ("NE", "IE")
                   for r in self.national):
                return True
        return False

    def test_no_sector_marks_a_category_NE_that_the_national_table_omits(self):
        missing = []
        for path in sorted(glob.glob(os.path.join(ROOT, SECTOR_GLOB))):
            name = os.path.basename(path)
            rows = read_rows(path)
            if not rows:
                continue
            code_col = _column(rows[0], CODE_COLUMNS)
            key_col = _column(rows[0], KEY_COLUMNS)
            if not (code_col and key_col):
                continue
            for r in rows:
                if (r[key_col] or "").strip().upper() != "NE":
                    continue
                code = (r[code_col] or "").strip()
                if code and not self._declared_at_or_above(code):
                    missing.append("%s: %s (%s)" % (name, code,
                                                    (r.get("category") or "")[:44]))
        self.assertFalse(
            missing,
            "these categories are marked NE by a sector's own completeness product and have "
            "NO ROW in %s, whose stated purpose is that every category x gas is listed. A "
            "partition can sum correctly over an incomplete universe and read exactly like a "
            "correct table. Add the row AND its data_gaps register entry - the completeness "
            "module's bidirectional gap check requires both:\n  %s"
            % (NATIONAL, "\n  ".join(sorted(missing))))

    def test_the_national_table_still_carries_more_than_any_one_sector(self):
        """The one-directionality is deliberate, and worth asserting so nobody 'fixes' it.

        The national table holds rows no sector product does - cross-sector transfers, the
        air family, LULUCF - so a symmetric check would fail for the right reasons and get
        deleted. This records why the comparison runs one way.
        """
        self.assertGreater(
            len(self.codes), 40,
            "the national table carries %d distinct codes; it is meant to be the superset "
            "across sectors plus the cross-sector and air rows" % len(self.codes))


if __name__ == "__main__":
    unittest.main()
