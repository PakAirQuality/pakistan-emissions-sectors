"""The rc33 validation lane's own invariants: vocabulary, catalog, freshness."""

from pkinv.assets import asset_path
import csv
import os
import unittest
import hashlib
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from pkinv.core.io import read_rows
from _support import OUT, ROOT



def _rows(path):
    return read_rows(path)


class TestTheVerdictVocabulary(unittest.TestCase):
    def test_the_set_is_closed_and_the_legacy_map_lands_inside_it(self):
        from pkinv.validation import verdicts
        self.assertEqual(len(verdicts.ALL), 7)
        for legacy, projected in verdicts.LEGACY_MAP.items():
            if projected is not None:
                self.assertIn(projected, verdicts.ALL, legacy)


class TestTheCatalog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = _rows(asset_path(ROOT, "data", "validation_catalog.csv"))

    def test_vocabularies_are_closed(self):
        for r in self.catalog:
            self.assertIn(r["property_tested"],
                          ("magnitude", "timing", "geography"), r["validation_id"])
            self.assertIn(r["grain"],
                          ("national", "sector", "category", "province",
                           "district", "cell", "month", "month_district",
                           "facility", "point", "worksheet_cell", "sample"),
                          r["validation_id"])
            self.assertIn(r["wired"],
                          ("run_all_phase", "makefile_target", "hand_run",
                           "test_only", "declared_absence"), r["validation_id"])

    def test_benchmark_joins_resolve(self):
        """The two registries were structurally disjoint; the join column is the
        repair, and a join naming a task that does not exist is a typo shipping
        as a link."""
        tasks = {r["task_id"] for r in _rows(
            asset_path(ROOT, "data", "benchmark_tasks.csv"))}
        for r in self.catalog:
            if r["benchmark_task_id"]:
                self.assertIn(r["benchmark_task_id"], tasks, r["validation_id"])

    def test_a_wired_row_names_a_real_producer(self):
        for r in self.catalog:
            if r["wired"] in ("run_all_phase", "makefile_target") and r["producer"]:
                self.assertTrue(
                    os.path.exists(asset_path(ROOT, r["producer"])),
                    "%s: producer %s does not exist"
                    % (r["validation_id"], r["producer"]))


class TestTheScorecard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.card = _rows(os.path.join(OUT, "pakemis_validation_scorecard.csv"))

    def test_the_full_space_is_present(self):
        """Every (property x grain) cell exists as a row - covered or a
        declared_absent roadmap entry, never silence."""
        self.assertEqual(len(self.card), 3 * 12)
        keys = {(r["property_tested"], r["grain"]) for r in self.card}
        self.assertEqual(len(keys), 36)

    def test_no_cell_is_unclassified(self):
        for r in self.card:
            self.assertIn(r["status"], ("covered", "declared_absent"),
                          (r["property_tested"], r["grain"]))

    def test_the_known_coverage_is_present(self):
        """The cells the modularity map found covered must score covered - a
        scorecard that lost magnitude x category would be reading nothing."""
        by_key = {(r["property_tested"], r["grain"]): r for r in self.card}
        for key in (("magnitude", "category"), ("timing", "month"),
                    ("geography", "district"), ("geography", "province")):
            self.assertEqual(by_key[key]["status"], "covered", key)


class TestTheFreshnessGate(unittest.TestCase):
    def test_a_stale_wired_product_is_refused(self):
        """Sabotage: age a wired validation product far past the slack and the
        builder must raise - the stale-four-releases class, closed."""
        from pkinv.report import validation_catalog as vc
        target = os.path.join(OUT, "pakemis_rice_geography_crosscheck.csv")
        if not os.path.exists(target) or not os.path.exists(vc.SENTINEL):
            self.skipTest("products not built")
        stat = os.stat(target)
        try:
            old = os.path.getmtime(vc.SENTINEL) - vc.SLACK_S - 86400.0
            os.utime(target, (old, old))
            with self.assertRaises(SystemExit) as caught:
                vc.build()
            self.assertIn("STALE", str(caught.exception))
        finally:
            os.utime(target, (stat.st_atime, stat.st_mtime))


class TestTheGateRunsAfterEverythingItGrades(unittest.TestCase):
    """The hole rc53 closed in PROSE, reopened by a phase added below the gate.

    The gate compares every wired product's mtime to the build's own sentinel, so a wired
    product written by a LATER phase still carries the previous build's mtime and fails
    STALE on a file the same build is about to write. rc53 fixed that by moving the gate
    and wrote the constraint in a comment; on 2026-10-07 `FAOSTAT nitrogen flows` was added
    four phases below it and `make dev` failed on exactly that, with 46 minutes already
    spent. A comment is not a check, so this is the check.
    """

    def test_no_wired_producer_is_scheduled_after_the_gate(self):
        from pkinv import run_all
        from pkinv.paths import DATA
        wired = {r["result_output"] for r in read_rows(
                     asset_path(DATA, "validation_catalog.csv"), comments=True)
                 if r["wired"] == "run_all_phase" and r["result_output"] not in ("none", "")}
        self.assertTrue(wired, "no wired products; this guard would be vacuous")
        order = {p.label: i for i, p in enumerate(run_all.PHASES)}
        gate = order["Validation catalog + scorecard"]
        late = []
        for i, phase in enumerate(run_all.PHASES):
            if i <= gate:
                continue
            for written in phase.writes:
                if written.split("outputs/", 1)[-1] in wired:
                    late.append("%s writes %s" % (phase.label, written))
        self.assertFalse(late, "these wired validations are produced AFTER the gate that "
                               "grades their freshness, so a clean build fails STALE on a "
                               "file it is about to write:\n  " + "\n  ".join(sorted(late)))

    def test_the_gate_still_precedes_its_three_consumers(self):
        """The other half of rc53's constraint: the inventory, the deposit manifest and the
        product facts read what the gate writes, so it cannot simply be moved to the end."""
        from pkinv import run_all
        order = {p.label: i for i, p in enumerate(run_all.PHASES)}
        gate = order["Validation catalog + scorecard"]
        for consumer in ("Artifact inventory", "Product coverage", "Deposit manifest"):
            self.assertLess(gate, order[consumer], consumer)


class TestIncrementalFreshnessProof(unittest.TestCase):
    def setUp(self):
        from pkinv.report import validation_catalog as vc
        self.vc = vc
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.outputs = self.root / "outputs"
        self.outputs.mkdir()
        self.result = self.outputs / "result.csv"
        self.result.write_text("value\n1\n")
        self.sentinel = self.outputs / "national_totals_2024.csv"
        self.sentinel.write_text("value\n2\n")
        os.utime(self.result, (1, 1))
        self.catalog = self.root / "catalog.csv"
        self.catalog.write_text("validation_id,result_output,wired,verdict_adapter\n"
                                "fixture,result.csv,run_all_phase,\n")
        self.proof_path = self.root / "verified.json"
        self.proof = {"schema": "pkinv.verified_outputs/v1", "root": str(self.root.resolve()),
                      "outputs": {"outputs/result.csv": hashlib.sha256(self.result.read_bytes()).hexdigest()}}
        self.proof_path.write_text(json.dumps(self.proof))
        self.patches = [patch.object(vc, "OUTPUTS", str(self.outputs)),
                        patch.object(vc, "SENTINEL", str(self.sentinel)),
                        patch.object(vc, "CATALOG", str(self.catalog)),
                        patch.dict(os.environ, {"PKINV_BUILD_VERIFIED_OUTPUTS": str(self.proof_path)})]
        for patcher in self.patches:
            patcher.start()

    def tearDown(self):
        for patcher in reversed(self.patches):
            patcher.stop()
        self.temp.cleanup()

    def test_old_mtime_with_current_verified_content_is_accepted(self):
        rows, _ = self.vc.build()
        self.assertEqual(rows[0]["fresh"], "yes")
        self.assertEqual(self.result.stat().st_mtime, 1)

    def test_missing_producer_proof_keeps_strict_age_gate(self):
        self.proof["outputs"] = {}
        self.proof_path.write_text(json.dumps(self.proof))
        with self.assertRaisesRegex(SystemExit, "STALE"):
            self.vc.build()

    def test_changed_content_cannot_reuse_valid_proof(self):
        self.result.write_text("value\n9\n")
        os.utime(self.result, (1, 1))
        with self.assertRaisesRegex(SystemExit, "STALE"):
            self.vc.build()

    def test_proof_from_another_workspace_is_rejected(self):
        self.proof["root"] = str(self.root / "elsewhere")
        self.proof_path.write_text(json.dumps(self.proof))
        with self.assertRaisesRegex(SystemExit, "STALE"):
            self.vc.build()


if __name__ == "__main__":
    unittest.main()


class TestTheSectorScorecard(unittest.TestCase):
    """rc37: the (module x property) projection - 30 cells, each the best row's claim."""

    @classmethod
    def setUpClass(cls):
        from pkinv.report import validation_catalog as vc
        cls.vc = vc
        cls.card = read_rows(vc.SECTOR_SCORECARD)

    def test_the_full_sector_space_is_present(self):
        cells = {(r["module"], r["property_tested"]) for r in self.card}
        self.assertEqual(len(self.card), len(self.vc.MODULES) * len(self.vc.PROPERTIES))
        self.assertEqual(cells, {(m, p) for m in self.vc.MODULES for p in self.vc.PROPERTIES})

    def test_every_status_is_from_the_vocabulary(self):
        allowed = {"validated", "corroborated", "calibrated_only",
                   self.vc.verdicts.DECLARED_ABSENT, "unregistered_absence"}
        for r in self.card:
            self.assertIn(r["status"], allowed, "%s/%s" % (r["module"], r["property_tested"]))

    def test_the_card_rederives_from_the_catalog(self):
        rows, _notes = self.vc.build()
        fresh = self.vc.sector_scorecard(rows)
        self.assertEqual([(r["module"], r["property_tested"], r["status"], r["best_row"])
                          for r in self.card],
                         [(r["module"], r["property_tested"], r["status"], r["best_row"])
                          for r in fresh],
                         "the shipped sector scorecard does not follow from the catalog")

    def test_no_silent_cell_is_left_unnamed(self):
        """A cell with no row at all is the failure mode the projection exposes. rc37
        found three: industry geography (non-kiln) is an absence row now, and the power
        coal/gas and industry gas timing silences are stated on the hindcast rows that
        score the liquid streams - a declared absence may not stand over a scored result,
        so the statement lives on the result. The permitted silences are none."""
        silent = sorted("%s/%s" % (r["module"], r["property_tested"]) for r in self.card
                        if r["status"] == "unregistered_absence")
        self.assertEqual(silent, [], "cells with no catalog row, not even an absence")
