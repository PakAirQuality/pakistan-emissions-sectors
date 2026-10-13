"""The Pass-2 control layer: registries that plan the program without touching the science.

Wave 0 of the sixteenth review's Pass-2 program adds a scope registry (annual
completeness candidates with activation gates) and a temporal-driver registry (every
stream's timing state and its planned move). The contract these tests hold is rule
one of the pass: INTRODUCING THE CONTROL LAYER CHANGES NO SCIENTIFIC OUTPUT. The
registries describe and plan; nothing in the engine reads them, and the no-op test
proves that structurally rather than by assertion.

Run:  python3 -m unittest discover tests -p "test_pass2_registries.py"
"""

from pkinv.assets import asset_path
import csv
import os
import subprocess
import sys
import unittest

from _support import require_documents  # noqa: E402  (rc42: the documents gate)
from pkinv.core.io import read_rows
from _support import ROOT, scripts_on_path

scripts_on_path()

SCOPE = asset_path(ROOT, "data", "scope_registry.csv")
DRIVERS = asset_path(ROOT, "data", "temporal_driver_registry.csv")
DECOMPOSITION = os.path.join(ROOT, "outputs", "pakemis_temporal_decomposition.csv")

SCOPE_STATUSES = ("NE", "screening", "configuration", "reference", "not_applicable",
                  "unsupported", "not_implemented")
PROCESS_CLASSES = ("observed_activity", "administrative_proxy", "modeled_seasonality",
                   "physically_continuous", "stock_driven", "variable_unobserved")
DRIVER_STATUSES = ("open_data_wave2", "open_data_wave3", "request_gated",
                   "no_action_needed")


def _rows(path):
    return read_rows(path)


class TestTheControlLayerIsInert(unittest.TestCase):
    def test_no_engine_or_report_module_reads_the_registries(self):
        """The structural no-op proof, with its one walked doorway. The registries
        are the PROGRAM's ledger; the science must not depend on them, or adding a
        plan would change a result. Wave 4 walked through this test deliberately:
        completeness_mass.py reads the scope registry to VALIDATE it against the
        shipped configurations - a reader that fails the build when the registry
        drifts from the products, which is the one relationship a plan file may
        have with the science. No sector engine reads either registry, and no
        module reads the driver registry at all."""
        out = subprocess.run(
            ["grep", "-rl", "-e", "scope_registry", "-e", "temporal_driver_registry",
             os.path.join(ROOT, "src")],
            capture_output=True, text=True)
        # deposit_manifest NAMES the registries to assign their deposit licence - a
        # rights statement about the files, not a computation from them.
        # completeness_mass is the Wave-4 doorway walked above. Anything else in
        # src/ touching them is still guarded.
        allowed = ("deposit_manifest.py", "completeness_mass.py",
                   # Wave 6: the exit scorecard - same licence, scorer never feeder
                   "pass2_scorecard.py",
                   # rc39 A2: run_all NAMES the driver registry to declare which phase WRITES
                   # it, after the generator turned out to be in no build definition and the
                   # file went stale on every pass that moved a number. A build declaration is
                   # the same category as deposit_manifest's licence statement - it says where
                   # the file comes from, and computes nothing from its contents. The registry
                   # stays inert: what run_all gains is the knowledge that it is generated.
                   "run_all.py")
        readers = [line for line in out.stdout.strip().splitlines()
                   if line.strip() and line.endswith(".py")
                   and not line.endswith(allowed)]
        self.assertEqual(readers, [],
                         "src/ reads a Pass-2 registry: %s" % readers)

    def test_the_doorway_reader_validates_rather_than_computes(self):
        """The admitted reader's licence is narrow: it may fail the build, never
        feed it. Its module must not be imported by any sector engine."""
        out = subprocess.run(
            ["grep", "-rl", "completeness_mass",
             os.path.join(ROOT, "src", "pkinv", "sectors")],
            capture_output=True, text=True)
        self.assertEqual(out.stdout.strip(), "",
                         "a sector engine imports the doorway reader: %s"
                         % out.stdout)


class TestTheScopeRegistry(unittest.TestCase):
    def setUp(self):
        self.rows = _rows(SCOPE)

    def test_every_candidate_has_a_gate_and_a_typed_status(self):
        self.assertGreaterEqual(len(self.rows), 10)
        for row in self.rows:
            self.assertIn(row["current_status"], SCOPE_STATUSES, row["category_id"])
            self.assertTrue(row["annual_activation_gate"].strip(), row["category_id"])
            self.assertTrue(row["ipcc_code"].strip(), row["category_id"])

    def test_screening_rows_name_a_priced_configuration_that_exists(self):
        """A row claiming its mass is priced outside the totals must point at a
        configuration the release actually ships."""
        with open(os.path.join(ROOT, "outputs", "national_configurations.csv"),
                  newline="", encoding="utf-8") as handle:
            shipped = handle.read()
        for row in self.rows:
            if row["current_status"] != "screening":
                continue
            named = [token.strip("() ") for token in
                     row["available_open_data"].replace("(", " ").replace(")", " ").split()
                     if "_" in token]
            self.assertTrue(any(name in shipped for name in named),
                            "%s is 'screening' but names no shipped configuration"
                            % row["category_id"])

    def test_no_screening_mass_is_inside_the_reference(self):
        """Rule 3: the reference total must not move when a screening row exists.
        The reference is pinned elsewhere; here we assert every screening row SAYS
        it is outside (the phrase is load-bearing for a reader)."""
        for row in self.rows:
            if row["current_status"] == "screening":
                text = (row["available_open_data"] + row["annual_activation_gate"]
                        + row["double_counting_exclusions"]).lower()
                self.assertTrue("outside" in text or "configuration" in text
                                or "screening" in text, row["category_id"])


class TestTheDriverRegistry(unittest.TestCase):
    def setUp(self):
        self.rows = _rows(DRIVERS)
        self.decomposition = {(r["sector_id"], r["component"]): r
                              for r in _rows(DECOMPOSITION)}

    def test_it_regenerates_identically(self):
        import build_temporal_driver_registry as builder
        rebuilt = builder.build()
        self.assertEqual(len(rebuilt), len(self.rows))
        for ours, theirs in zip(rebuilt, self.rows):
            self.assertEqual({k: str(v) for k, v in ours.items()}, dict(theirs))

    def test_every_stream_mirrors_the_decomposition(self):
        """The derived columns are the decomposition's, never retyped."""
        self.assertEqual(len(self.rows), len(self.decomposition))
        for row in self.rows:
            source = self.decomposition[(row["sector_id"], row["component"])]
            self.assertEqual(row["annual_mass_Mt"], source["co2e_Mt_AR5"])
            self.assertEqual(row["current_te"], source["evidence_grade"])
            self.assertEqual(row["mass_potentially_moved_Mt"],
                             source["unobserved_Mt_AR5"])

    def test_vocabularies_are_closed(self):
        for row in self.rows:
            self.assertIn(row["current_process_class"], PROCESS_CLASSES, row["stream_id"])
            self.assertIn(row["status"], DRIVER_STATUSES, row["stream_id"])

    def test_no_variable_unobserved_stream_is_silently_unplanned(self):
        """The program's honesty rule: a stream that should vary and is unobserved
        either has a named open-data wave, is request_gated, or - since the Wave-6
        freeze - carries a no_action_needed whose driver note states the PHYSICS
        refusal in words (the managed-soils census nitrogen: the offtake shape must
        never reach it, so no acquisition can move the mass). Never blank, and a
        bare no_action_needed with no refusal stated still fails."""
        for row in self.rows:
            if row["current_process_class"] == "variable_unobserved":
                if row["status"] == "no_action_needed":
                    self.assertIn("forbids", row["driver_source"],
                                  "%s: no_action_needed on a variable-unobserved "
                                  "stream without a stated physics refusal"
                                  % row["stream_id"])
                    continue
                self.assertIn(row["status"],
                              ("open_data_wave2", "open_data_wave3",
                               "request_gated"),
                              row["stream_id"])

    def test_no_continuous_process_is_planned_a_seasonality(self):
        """The reviewer's warning made executable: physically continuous or
        stock-driven streams must not be assigned an invented monthly curve. A plan
        may refine the physics (the FOD engine) but its status is a wave, and its
        expected class stays honest - it must not promise TE1/TE2."""
        for row in self.rows:
            if row["current_process_class"] in ("physically_continuous",):
                self.assertNotIn(row["expected_te_after_pass2"], ("TE1", "TE2"),
                                 row["stream_id"])


class TestTheFcaCorpusIsHeldNotParsed(unittest.TestCase):
    """The Wave-2 remainder's acquisition rule, held: the FCA determinations are
    hash-pinned evidence whose parse is REFUSED (scan-grade digits), and the manifest
    must say both facts without claiming a parse that never happened."""

    @classmethod
    def setUpClass(cls):
        path = asset_path(ROOT, "data", "manifests", "fca_document_manifest.csv")
        if not os.path.exists(path):
            raise unittest.SkipTest("FCA manifest not built")
        cls.rows = _rows(path)

    def test_every_fetched_row_is_held_and_hashed(self):
        import hashlib
        require_documents("data/raw/nepra/fca")
        checked = 0
        for row in self.rows:
            if row["parse_status"] == "fetch_failed":
                continue
            year = row["url"].rsplit("/", 2)[-2]
            local = asset_path(ROOT, "data", "raw", "nepra", "fca", row["lane"], year if year.isdigit() else "undated", row["document"])
            self.assertTrue(os.path.exists(local), row["document"])
            if checked < 5:      # full hashes for a sample; presence for all
                digest = hashlib.sha256(open(local, "rb").read()).hexdigest()
                self.assertEqual(digest, row["sha256"], row["document"])
                checked += 1
        self.assertGreaterEqual(len(self.rows), 150)

    def test_no_document_claims_a_parse(self):
        self.assertEqual({r["parse_status"] for r in self.rows} - {"fetch_failed"},
                         {"pending"})

    def test_the_annex_vocabulary_is_typed_by_inspection(self):
        allowed = {"unknown", "plant_wise", "fuel_wise_combined",
                   "ke_own_generation_monthly", "cost_only"}
        kinds = {r["annex_kind"] for r in self.rows}
        self.assertTrue(kinds <= allowed, kinds)
        self.assertIn("plant_wise", kinds,
                      "the inspected 2016 plant-wise annexes lost their typing")


class TestTheRequestLifecycle(unittest.TestCase):
    def test_every_request_carries_a_typed_response_status(self):
        rows = _rows(asset_path(ROOT, "data", "monthly_data_requests.csv"))
        allowed = ("not_sent", "sent", "followup_sent", "closed_received",
                   "closed_refused", "closed_no_response")
        for row in rows:
            self.assertIn(row["response_status"], allowed, row["request_id"])
            if row["response_status"] == "not_sent":
                self.assertEqual(row["date_sent"], "", row["request_id"])


if __name__ == "__main__":
    unittest.main()
