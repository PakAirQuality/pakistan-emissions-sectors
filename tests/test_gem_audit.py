"""The GEM asset-census cross-check stays a comparator, and its census claims hold.

The audit exists to answer "does the ledger know every operating coal plant GEM
knows" - so the tests pin the two properties that make the answer trustworthy:
the declared correspondence actually resolves (a renamed NEPRA plant string must
fail loudly, not become a silent unmatch), and no quantity from the tracker can
leak into the engine (the file is absent from every factor and stream registry).

Run:  python3 -m unittest discover tests -p "test_gem_audit.py"
"""

from pkinv.assets import asset_path
import csv
import os
import unittest

from pkinv.report import gem_audit
from pkinv.core.io import read_rows
from _support import ROOT

OUT = os.path.join(ROOT, "outputs", "power_gem_audit.csv")


def _rows():
    return read_rows(OUT)


class TestTheAuditIsACensus(unittest.TestCase):
    def test_every_declared_correspondence_resolves(self):
        """mapping_broken means GEM_TO_LEDGER names a NEPRA string the ledger no
        longer carries - the exact silent decay the declared table exists to
        surface, so it fails the suite rather than shipping as an unmatch."""
        broken = [r["gem_plant"] for r in _rows()
                  if r["match_class"] == "mapping_broken"]
        self.assertEqual(broken, [])

    def test_every_ledger_coal_account_is_covered(self):
        """The reverse direction: the release ships with ledger_only rows only
        if a NEPRA coal plant has no mapped GEM unit. Today all are covered;
        if NEPRA adds a coal account, this fails until the mapping learns it."""
        self.assertEqual([r["ledger_plant"] for r in _rows()
                          if r["match_class"] == "ledger_only"], [])

    def test_the_jamshoro_finding_is_closed_by_the_ledger(self):
        """Through rc67 the one census finding: GEM carried Jamshoro Unit 5
        operating on coal while the per-plant ledger held Jamshoro on RFO alone.
        The FY2024-25 extension reads NEPRA's own coal account for the unit, so
        it is now a matched row and nothing is GEM-only. Any future gem_only row
        must still say it is a finding to state, never a quantity."""
        jamshoro = [r for r in _rows() if r["gem_plant"] == "Jamshoro power station"]
        self.assertEqual([r["match_class"] for r in jamshoro], ["matched_grid_ledger"])
        self.assertEqual(jamshoro[0]["ledger_plant"], "Jamshoro Coal Power Unit-1")
        for r in _rows():
            if r["match_class"] == "gem_only":
                self.assertIn("never a quantity", r["note"])

    def test_the_product_regenerates_identically(self):
        fresh = gem_audit.build()
        shipped = _rows()
        self.assertEqual(len(fresh), len(shipped))
        for f, s in zip(fresh, shipped):
            for col in gem_audit.FIELDS:
                self.assertEqual(str(f[col]), s[col],
                                 "%s.%s" % (f["gem_plant"] or f["ledger_plant"],
                                            col))

    def test_no_stream_or_factor_reads_the_tracker(self):
        """Comparator only, structurally: the GEM extracts appear in no factor
        table, no stream registry and no geometry registry - the same fence
        the road products live behind."""
        needles = ("gem_coal_pak", "gem_cement_pak", "power_gem_audit")
        for name in ("emission_factors.csv", "stream_grid_proxy.csv",
                     "stream_geometry.csv", "geometry_sets.csv",
                     "stream_spatial_alternatives.csv"):
            with open(asset_path(ROOT, "data", name), encoding="utf-8") as f:
                text = f.read()
            for needle in needles:
                self.assertNotIn(needle, text, "%s leaked into %s" % (needle, name))


if __name__ == "__main__":
    unittest.main()
