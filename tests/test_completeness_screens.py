"""The 1.A.4.a audit and its register consequences (the second review's 8.6).

The category was the register's one silent omission: no NE row, no gap entry, no code in
the EDGAR domain map -- so the Buildings coverage line claimed "2 of 2 codes estimated"
while commercial gas sat in the repository counted only as post-meter leakage. These tests
hold the audit to the held rows it reads, and hold the register to the audit.
"""

from pkinv.assets import asset_path
import csv
import os
import sys
import unittest


from pkinv.report import commercial_audit   # noqa: E402
from pkinv.core.io import read_rows
from _support import ROOT


def _rows(path):
    return read_rows(path)


class TestCommercialAudit(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.rows = commercial_audit.rows()

    def test_the_floor_is_material_and_below_the_filed_benchmark(self):
        """The audit's headline: the two quantifiable streams alone put 1.A.4.a above
        the 1 Mt materiality line, and a two-stream floor must sit below Pakistan's own
        filed commercial figure or one of the two is wrong."""
        floor = commercial_audit.quantified_floor_mt()
        self.assertGreater(floor, 1.0)
        self.assertLess(floor, commercial_audit.BUR1_COMMERCIAL_MT)

    def test_the_gas_stream_is_the_held_ogra_row_converted(self):
        gas = next(r for r in self.rows if r["stream"] == "Commercial piped gas")
        held = next(r for r in _rows(asset_path(ROOT, "data", "activity", "fugitives", "post_meter_end_use_2023_24.csv"))
            if r["end_use"] == "Commercial")
        self.assertEqual(gas["activity"], float(held["throughput_mmcfd"]))
        expected = (float(held["throughput_mmcfd"]) * 365.0
                    * commercial_audit.GAS_TJ_PER_MMCF
                    * commercial_audit.GAS_CO2_KG_TJ / 1e9)
        self.assertAlmostEqual(gas["screening_Mt_co2e"], expected, places=3)

    def test_every_stream_carries_a_disposition_from_the_closed_set(self):
        allowed = {"leakage-counted, combustion-unestimated", "genuinely unestimated",
                   "unresolvable within held classes", "held-unassigned, bounded",
                   "benchmark"}
        self.assertEqual({r["disposition"] for r in self.rows}, allowed)

    def test_the_register_now_declares_the_category(self):
        """The reinstated defect is the ABSENCE: before this audit no 1.A.4.a row
        existed at all. The row must exist, be NE, and point at the audit."""
        reg = [r for r in _rows(os.path.join(ROOT, "outputs", "completeness.csv"))
               if r["code"] == "1.A.4.a"]
        self.assertEqual(len(reg), 1, "1.A.4.a is missing from the register again")
        self.assertEqual(reg[0]["notation_key"], "NE")
        self.assertIn("commercial_institutional_audit", reg[0]["justification"])
        self.assertEqual(reg[0]["gap_id"], "commercial-institutional")

    def test_the_edgar_buildings_domain_no_longer_overstates_its_coverage(self):
        """The stored defect: Buildings read "2 of 2 codes estimated" while a whole
        category-class fell through the map. The domain must now carry 1.A.4.a and say
        it is not estimated here."""
        domain_map = _rows(asset_path(ROOT, "data", "edgar_domain_map.csv"))
        codes = {r[list(r)[1]] for r in domain_map if r[list(r)[0]] == "Buildings"}
        self.assertIn("1.A.4.a", codes)
        coverage = _rows(os.path.join(ROOT, "outputs",
                                      "national_benchmark_scope_coverage.csv"))
        buildings = next(r for r in coverage if r["edgar_domain"] == "Buildings")
        self.assertNotIn("2 of 2", buildings["categories_estimated"],
                         "Buildings claims full code coverage again")
        self.assertIn("1.A.4.a", buildings["not_estimated_here"])

    def test_no_domain_maps_the_same_code_twice(self):
        """A duplicate row inflates the denominator of a published coverage count.

        The stored defect: rc52 activated ammonia and iron-and-steel in IPPU and added
        rows for 2.B.1 and 2.C.1 to the Processes domain, which already listed both. The
        map then held eight rows for six codes and the shipped product read "6 of 8 codes
        estimated" - a denominator two too large and a numerator double-counting two
        codes. Every other domain was clean, so nothing else showed it.
        """
        rows = _rows(asset_path(ROOT, "data", "edgar_domain_map.csv"))
        dom, code = list(rows[0])[0], list(rows[0])[1]
        seen, dupes = set(), []
        for r in rows:
            key = (r[dom], r[code])
            if key in seen:
                dupes.append("%s / %s" % key)
            seen.add(key)
        self.assertFalse(dupes,
                         "data/edgar_domain_map.csv maps the same code into the same "
                         "domain twice: %s. The coverage count divides by the row count, "
                         "so a duplicate silently inflates the denominator." % dupes)

    def test_every_mapped_code_is_accounted_for_in_the_coverage_row(self):
        """estimated + NE + not-applicable must reach the denominator, or a reader subtracts.

        The stored defect: Processes read "4 of 6 codes estimated" beside a single named
        NE, so the sixth code was invisible. It is 2.B.7, soda ash, which is NA rather
        than NE - IPCC Vol.3 s3.8.3.1 allocates the Solvay-process carbon to Energy, so it
        is an absence this inventory has RESOLVED, not one it owes. Agriculture hid two
        the same way (3.E, 3.J). An unaccounted code reads as an undeclared gap, which is
        the opposite of what a typed absence is for.
        """
        import re
        coverage = _rows(os.path.join(ROOT, "outputs",
                                      "national_benchmark_scope_coverage.csv"))
        for row in coverage:
            if row["edgar_domain"].startswith("SUMMARY"):
                continue
            text = row["categories_estimated"]
            m = re.match(r"(\d+) of (\d+) codes estimated", text)
            self.assertTrue(m, "unparseable coverage cell for %s: %r"
                            % (row["edgar_domain"], text))
            estimated, total = int(m.group(1)), int(m.group(2))
            ne = [c for c in row["not_estimated_here"].split(";") if c.strip()]
            partly = re.search(r"(\d+) only in part", text)
            na = re.search(r"(\d+) not applicable", text)
            accounted = (estimated + len(ne)
                         - (int(partly.group(1)) if partly else 0)
                         + (int(na.group(1)) if na else 0))
            self.assertEqual(
                accounted, total,
                "%s: %d estimated + %d NE - %d counted twice + %d NA = %d, but the "
                "denominator is %d. Some mapped code is in none of the three buckets and "
                "a reader cannot tell whether it is a gap." % (
                    row["edgar_domain"], estimated, len(ne),
                    int(partly.group(1)) if partly else 0,
                    int(na.group(1)) if na else 0, accounted, total))

    def test_the_published_file_matches_a_fresh_build(self):
        published = _rows(os.path.join(ROOT, "outputs",
                                       "commercial_institutional_audit_2024.csv"))
        self.assertEqual(len(published), len(self.rows))
        for want, got in zip(self.rows, published):
            self.assertEqual(str(want["screening_Mt_co2e"]),
                             got["screening_Mt_co2e"], got["stream"])


if __name__ == "__main__":
    unittest.main()
