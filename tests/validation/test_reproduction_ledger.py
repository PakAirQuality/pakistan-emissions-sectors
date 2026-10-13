"""The packaged reproduction was a strict run from an EMPTY outputs/ that wrote every product.

WHY. The rc40 package's reproduce.sh copied outputs/ in first, so a phase that never ran
still "reproduced" its products; 82 of 83 were reported identical while 59 phases had not
run. rc41 makes the ledger the evidence: run_all.py --strict --ledger records, per phase,
what it observed written, and reproduce.sh seeds only the products data/held_products.csv
declares. This module reads that ledger inside the package and asserts the three things
a reader wants to know without trusting the report's wording:

  * every phase ended OK (or the one declared network skip under --quick) and the run
    exited 0 - nothing failed, nothing was skipped for want of a document;
  * every product VALIDATION_MANIFEST.json lists was WRITTEN by an OK phase in that run
    or SEEDED from the registry - never carried over from the packaged tree;
  * the reproduction report has no product in not_rebuilt / missing_in_rebuild /
    difference - the gate's own definition of PASS.

Outside a package (no VALIDATION_MANIFEST.json beside the tree) the module skips.
"""
import csv
import json
import os
import unittest

from _support import ROOT
from validation._package import IN_PACKAGE, manifest

LEDGER = os.path.join(ROOT, "logs", "reproduction_ledger.json")
REPORT = os.path.join(ROOT, "logs", "reproduction_report.csv")
ALLOWED_STATUS = {"OK", "SKIP (quick)"}
FAILING_REPORT_STATUS = {"not_rebuilt", "missing_in_rebuild", "difference"}


class TestTheReproductionLedger(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not IN_PACKAGE:
            raise unittest.SkipTest("not inside a validation package")
        if not os.path.exists(LEDGER):
            raise unittest.SkipTest("logs/reproduction_ledger.json absent - reproduce.sh has not run here")
        with open(LEDGER, encoding="utf-8") as handle:
            cls.ledger = json.load(handle)
        cls.products = [p["relative_path"] for p in manifest()["products"]]

    def test_the_run_was_strict_and_exited_zero(self):
        self.assertEqual(self.ledger["schema"], "pkinv.run_ledger/v1")
        self.assertTrue(self.ledger["strict"], "the packaged reproduction did not run --strict")
        self.assertEqual(self.ledger["exit_code"], 0,
                         "the packaged reproduction exited %r" % self.ledger["exit_code"])

    def test_every_phase_ended_ok(self):
        bad = {p["label"]: p["status"] for p in self.ledger["phases"]
               if p["status"] not in ALLOWED_STATUS}
        self.assertEqual(bad, {}, "phases that did not end OK: %s" % bad)
        self.assertGreater(len(self.ledger["phases"]), 50, "the ledger records too few phases to be the build")

    def test_every_manifest_product_was_written_or_seeded(self):
        written = set()
        for phase in self.ledger["phases"]:
            if phase["status"] == "OK":
                written.update(phase["written"])
        seeded = {s["path"] for s in self.ledger.get("seeded", [])}
        neither = sorted(p for p in self.products if p not in written and p not in seeded)
        self.assertEqual(neither, [],
                         "manifest products neither written by an OK phase nor seeded: %s" % neither)
        # Two declared classes may be both seeded and written: the prior release manifest
        # (seeded for the prior: read, then rewritten) and the network phase's products
        # under a full run; everything else seeded must not have been touched by a phase.
        rewritable = {s["path"] for s in self.ledger.get("seeded", [])
                      if s.get("reproducible_in_package") in ("rewritten", "network")}
        both = sorted(p for p in self.products if p in written and p in seeded and p not in rewritable)
        self.assertEqual(both, [], "seeded products a phase also rewrote: %s" % both)

    def test_the_reproduction_report_has_no_failing_status(self):
        self.assertTrue(os.path.exists(REPORT), "logs/reproduction_report.csv absent")
        with open(REPORT, newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        failing = {r["path"]: r["status"] for r in rows if r["status"] in FAILING_REPORT_STATUS}
        self.assertEqual(failing, {}, "reproduction report statuses that fail the gate: %s" % failing)
        # rc42: every seeded path has a row - as `seeded`, or, for the two declared
        # rewritable classes, as `seeded_then_rewritten_identical`.
        reported = sorted(r["path"] for r in rows
                          if r["status"] in ("seeded", "seeded_then_rewritten_identical"))
        self.assertEqual(reported, sorted(s["path"] for s in self.ledger.get("seeded", [])))

    def test_every_manifest_product_has_a_report_row(self):
        """The twentieth review's fifth gate: all manifest products compared, none
        unexamined. rc41 compared the release manifest's 74 and left 27 of the validation
        manifest's 104 without a row."""
        self.assertTrue(os.path.exists(REPORT), "logs/reproduction_report.csv absent")
        with open(REPORT, newline="", encoding="utf-8") as handle:
            reported = {r["path"] for r in csv.DictReader(handle)}
        missing = sorted(p for p in self.products if p not in reported)
        self.assertEqual(missing, [], "manifest products with no reproduction report row: %s" % missing)


if __name__ == "__main__":
    unittest.main()
