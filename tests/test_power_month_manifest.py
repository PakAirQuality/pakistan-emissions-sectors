"""The power month manifest: 108 typed service months, or the lane is lying.

The fifteenth review's completeness rule for the power lane: measure against an
EXPECTED manifest of service months, never against what a search returned. These
hold the shipped manifest to that rule and pin the discovery finding that makes
the staged backfill actionable.

Run:  python3 -m unittest discover tests -p "test_power_month_manifest.py"
"""

from pkinv.assets import asset_path
import csv
import os
import unittest

from _support import require_documents  # noqa: E402  (rc42: the documents gate)
from pkinv.core.io import read_rows
from _support import ROOT

MONTHS = asset_path(ROOT, "data", "manifests", "power_month_manifest.csv")
DOCS = asset_path(ROOT, "data", "manifests", "power_sir_document_manifest.csv")

# The closed month-status vocabulary. The SIR months carry two facts at once: the listing
# sheets are INGESTED into the plant-month panel (rc21), and the per-plant daily-PDF
# archive is discovered and remains the verification/arbitration instrument.
STATUSES = ("pbs_ingested", "sir_listing_ingested+sir_discovered", "untyped_gap")


def _rows(path):
    return read_rows(path, comments=False)


class TestEveryServiceMonthIsTyped(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.months = _rows(MONTHS)
        cls.docs = _rows(DOCS)

    def test_the_grid_is_complete(self):
        self.assertEqual(len(self.months), 108)
        self.assertEqual(len({r["service_month"] for r in self.months}), 108)

    def test_the_status_vocabulary_is_closed_and_no_month_is_untyped(self):
        for r in self.months:
            self.assertIn(r["status"], STATUSES, r["service_month"])
        gaps = [r["service_month"] for r in self.months
                if r["status"] == "untyped_gap"]
        self.assertEqual(gaps, [],
                         "untyped service months reappeared; either a lane lost "
                         "coverage or the manifest regressed: %s" % gaps)

    def test_the_two_lanes_tile_the_window(self):
        """PBS carries FY2015-16..FY2020-21 and the SIR lane FY2021-22..
        FY2023-24 - the SIR lane starts exactly where the PBS panel stops.
        The predicate is the lane PREFIX rather than one status word, so a
        status that renames a SIR stage (discovered -> listing_ingested)
        cannot silently drop the lane out of this count."""
        pbs = {r["service_month"] for r in self.months
               if "pbs_ingested" in r["status"]}
        sir = {r["service_month"] for r in self.months
               if "sir_" in r["status"]}
        self.assertEqual(len(pbs), 72)
        self.assertEqual(len(sir), 36)
        self.assertEqual(max(pbs), "2021-06")
        self.assertEqual(min(sir), "2021-07")

    def test_every_discovered_document_names_its_listing_and_hash(self):
        self.assertGreater(len(self.docs), 4000)
        for r in self.docs[:50] + self.docs[-50:]:
            self.assertTrue(r["url"].startswith("https://nepra.org.pk/"))
            self.assertEqual(len(r["listing_sha256"]), 64)
            self.assertIn(r["download_status"], ("discovered", "downloaded"))
            self.assertIn(r["parse_status"], ("pending", "parsed", "rejected"))

    def test_the_genco_crosswalk_sources_are_in_the_archive(self):
        """The discovery finding: the archive's GENCO directories are Guddu
        (CPGCL), Jamshoro (JPCL) and Muzaffargarh (NPGCL) - the stations whose
        fuel PBS never labels in FY2016-17/FY2017-18. If these directories left
        the archive, the named crosswalk source is gone and the verdicts that
        cite it must be revisited."""
        groups = {r["group"] for r in self.docs}
        for genco in ("CPGCL", "JPCL", "NPGCL"):
            self.assertIn(genco, groups)

    def test_the_manifest_regenerates_identically(self):
        import importlib.util
        require_documents("data/raw/nepra/sir_detail")
        spec = importlib.util.spec_from_file_location(
            "bpmm", os.path.join(ROOT, "scripts", "build_power_month_manifest.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        docs = mod.sir_documents()
        months = mod.month_rows(docs)
        self.assertEqual(len(docs), len(self.docs))
        self.assertEqual([tuple(sorted(m.items())) for m in months],
                         [tuple(sorted({k: (int(v) if k == "sir_documents"
                                            else (int(v) if k == "fiscal_year_start"
                                                  else v))
                                        for k, v in r.items()}.items()))
                          for r in [dict(r, sir_documents=int(r["sir_documents"]),
                                         fiscal_year_start=int(r["fiscal_year_start"]))
                                    for r in self.months]])


if __name__ == "__main__":
    unittest.main()
