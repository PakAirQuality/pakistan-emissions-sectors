"""The fractional cell x ADM2 table's own invariants (rc32)."""

from pkinv.assets import asset_path
import csv
import os
import unittest
from pkinv.core.io import read_rows
from _support import ROOT

PATH = asset_path(ROOT, "data", "gis", "adm2_intersections_267x340.csv")


def _rows():
    return read_rows(PATH)


class TestTheFractionsPartitionEveryCell(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = _rows()

    def test_every_cell_sums_to_one(self):
        """Fractions plus the explicit OUTSIDE remainder partition each cell -
        the property the all_touched label array never had."""
        sums = {}
        for r in self.rows:
            key = (int(r["row"]), int(r["col"]))
            sums[key] = sums.get(key, 0.0) + float(r["area_fraction"])
        bad = {k: v for k, v in sums.items() if abs(v - 1.0) > 1e-5}
        self.assertFalse(bad, "cells whose fractions do not sum to 1: %s"
                         % list(bad.items())[:5])

    def test_no_negative_or_over_unit_fraction(self):
        for r in self.rows:
            f = float(r["area_fraction"])
            self.assertGreater(f, 0.0)
            self.assertLessEqual(f, 1.0 + 1e-9)

    def test_the_outside_bucket_is_explicit_and_small(self):
        """The old -1 bincount key, now a named row class: off-polygon area must
        exist (sea, borders) and stay a small share of the frame."""
        outside = sum(float(r["area_fraction"]) for r in self.rows
                      if r["shape_id"] == "OUTSIDE")
        total = sum(float(r["area_fraction"]) for r in self.rows)
        self.assertGreater(outside, 0.0)
        self.assertLess(outside / total, 0.75)   # the frame includes sea corners

    def test_boundary_cells_are_genuinely_split(self):
        """The defect this table exists to end: alphabetical-last-wins gave every
        boundary cell to one district. A fractional table with no multi-claimant
        cells would mean the intersection never ran."""
        claims = {}
        for r in self.rows:
            if r["shape_id"] == "OUTSIDE":
                continue
            key = (int(r["row"]), int(r["col"]))
            claims[key] = claims.get(key, 0) + 1
        split = sum(1 for n in claims.values() if n > 1)
        self.assertGreater(split, 1000,
                           "only %d split cells - boundary cells are not being "
                           "fractionally shared" % split)


if __name__ == "__main__":
    unittest.main()


class TestNativeToAdm2Closure(unittest.TestCase):
    def test_agriculture_districts_reaggregate_to_provinces(self):
        """The native->ADM2 leg the chain never asserted (rc32): the shipped
        district panel must re-aggregate to the shipped provincial panel through
        the canonical district->province membership, category by category."""
        import collections
        prov_of = {}
        with open(os.path.join(ROOT, "outputs", "district_totals_2024.csv"),
                  newline="", encoding="utf-8") as f:
            d_rows = list(csv.DictReader(l for l in f if not l.startswith("#")))
        with open(os.path.join(ROOT, "outputs", "provincial_totals_2024.csv"),
                  newline="", encoding="utf-8") as f:
            p_rows = list(csv.DictReader(l for l in f if not l.startswith("#")))
        # the district panel is long (district x category x value); the
        # provincial panel is wide (category columns)
        sums = collections.defaultdict(float)
        for r in d_rows:
            sums[(r["province"], r["category"])] += float(r["co2e_Mt_AR5"])
        cats = sorted({r["category"] for r in d_rows})
        checked = 0
        for r in p_rows:
            for c in cats:
                if c in r and r.get(c):
                    got = sums.get((r["province"], c))
                    if got is None:
                        continue
                    # the provincial panel prints one decimal on large cells,
                    # so the closure is held at the coarser file's own rounding
                    self.assertAlmostEqual(
                        got, float(r[c]),
                        delta=max(0.006, abs(float(r[c])) * 1e-4),
                        msg="%s/%s: districts sum %.6f vs province %.6f"
                            % (r["province"], c, got, float(r[c])))
                    checked += 1
        self.assertGreater(checked, 10, "the closure checked almost nothing - "
                                        "column names drifted between the panels")
