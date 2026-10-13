"""The benchmark task suite: frozen splits, honest roles, and the per-GWP protocol.

Four surfaces. The REGISTRY (data/benchmark_tasks.csv) must have unique tasks from
closed vocabularies whose holdout definitions exist, and every split manifest must
hash to the sha256 the registry froze - the guard that makes a quietly edited
holdout fail instead of silently rescoring. The SPATIAL product must score the
model beside deterministic baselines with the model's own allocator labelled
reference (self-agreement is not evidence), and must carry the two findings the
task surfaced at registration - the within-Punjab weakness is asserted so it
cannot be silently tuned away without the registry note being revisited. The
TEMPORAL product must carry both baselines at every frozen origin with the
measurement-regime columns declared. The COMPARISON protocol columns must be
present in national_benchmark_comparison.csv with every row resolved in its own
GWP basis - the AR6 defect this round fixed.
"""

from pkinv.assets import asset_path
import csv
import hashlib
import os
import subprocess
import sys
import unittest
from pkinv.core.io import read_rows
from _support import ROOT

TASKS = asset_path(ROOT, "data", "benchmark_tasks.csv")
SPLITS = asset_path(ROOT, "data", "benchmark_splits")
SPATIAL = os.path.join(ROOT, "outputs", "benchmark_spatial_allocation.csv")
TEMPORAL = os.path.join(ROOT, "outputs", "benchmark_temporal_hindcast.csv")
COMPARISON = os.path.join(ROOT, "outputs", "national_benchmark_comparison.csv")

KINDS = ("spatial_allocation", "temporal_hindcast", "inventory_comparison",
         "reproducibility", "asset_detection")
# pending_record joined at rc13: a task whose HOLDOUT is frozen and whose model
# candidates exist, but whose truth record has not been acquired (the road
# allocation - the split predates any record so the record can never be chosen
# after seeing the model). Distinct from pending_model, where the record exists
# and the model does not.
STATUSES = ("active", "pending_model", "pending_record")


def _rows(path):
    return read_rows(path)


class TestTaskRegistry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tasks = _rows(TASKS)

    def test_tasks_are_unique_and_from_closed_vocabularies(self):
        ids = [t["task_id"] for t in self.tasks]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertGreaterEqual(len(ids), 8)
        for t in self.tasks:
            self.assertIn(t["kind"], KINDS, t["task_id"])
            self.assertIn(t["status"], STATUSES, t["task_id"])
            self.assertTrue(t["holdout_definition"].strip(), t["task_id"])
            self.assertTrue(t["note"].strip(), t["task_id"])

    def test_every_holdout_definition_exists(self):
        for t in self.tasks:
            self.assertTrue(
                os.path.exists(asset_path(ROOT, t["holdout_definition"])),
                "%s: %s" % (t["task_id"], t["holdout_definition"]))

    def test_split_manifests_hash_to_the_frozen_sha256(self):
        """The freeze itself: a perturbed manifest must fail here, not rescore."""
        hashed = [t for t in self.tasks
                  if t["holdout_definition"].startswith("data/benchmark_splits/")]
        self.assertGreaterEqual(len(hashed), 4)
        for t in hashed:
            path = asset_path(ROOT, t["holdout_definition"])
            digest = hashlib.sha256(
                open(path, "rb").read()).hexdigest()
            self.assertEqual(digest, t["holdout_sha256"],
                             "%s: %s no longer hashes to the registry's frozen "
                             "sha256 - the holdout changed without re-freezing"
                             % (t["task_id"], t["holdout_definition"]))

    def test_splits_rederive_byte_identically(self):
        result = subprocess.run(
            [sys.executable, os.path.join(ROOT, "scripts",
                                          "build_benchmark_splits.py"),
             "--check"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0,
                         result.stdout + result.stderr)

    def test_the_pending_model_task_says_why(self):
        kilns = next(t for t in self.tasks if t["kind"] == "asset_detection")
        self.assertEqual(kilns["status"], "pending_model")
        self.assertIn("not held in this repository", kilns["note"])


class TestSpatialAllocation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = _rows(SPATIAL)
        cls.scored = [r for r in cls.rows if r["status"] == "scored"]

    def _rho(self, task, candidate, year=None):
        for r in self.scored:
            if (r["task_id"] == task and r["candidate"] == candidate
                    and (year is None or r["record_year"] == year)):
                return float(r["spearman_rho"])
        raise AssertionError("no %s/%s row" % (task, candidate))

    def test_the_model_beats_the_baselines_where_it_claims_to(self):
        for task in ("spatial_rice_mnfsr", "spatial_wheat_mnfsr"):
            self.assertGreater(self._rho(task, "model"),
                               self._rho(task, "population"), task)
        self.assertGreaterEqual(self._rho("spatial_rice_mnfsr", "model"), 0.6)
        self.assertGreaterEqual(self._rho("spatial_wheat_mnfsr", "model"), 0.8)

    def test_uniform_carries_no_ranking(self):
        for r in self.scored:
            if r["candidate"] == "uniform":
                self.assertEqual(r["spearman_rho"], "")
                self.assertEqual(r["top10_overlap"], "")
                self.assertNotEqual(r["wape_shares"], "")

    def test_the_models_own_allocator_is_reference_never_baseline(self):
        cropland = [r for r in self.scored if r["candidate"] == "cropland"]
        self.assertTrue(cropland)
        for r in cropland:
            self.assertEqual(r["role"], "reference")
            self.assertIn("self-agreement", r["note"])

    def test_the_within_punjab_improvement_holds_against_its_own_baseline(self):
        """The rc10 finding was that within-Punjab rice ranking was no better
        than chance (rho ~ -0.1) while the national ranking held - the allocator
        separated rice provinces, not districts. The version of this test that
        pinned the weakness said the test and the registry note move TOGETHER
        when the model improves, and Wave 5 improved it: the MapSPAM surface
        landed and the model scores 0.90-0.96 against all three CRS years. Both
        halves are asserted so neither can silently regress: the model must stay
        strong, and the CROPLAND candidate - the very surface the old weakness
        rode - must stay at chance in the same table, so the improvement is
        anchored against its own baseline rather than a moved goalpost."""
        for year in ("2022-23", "2023-24", "2024-25"):
            self.assertGreater(self._rho("spatial_rice_punjabcrs", "model", year),
                               0.85, year)
            self.assertLess(self._rho("spatial_rice_punjabcrs", "cropland", year),
                            0.3, year)
        registry_note = next(t["note"] for t in _rows(TASKS)
                             if t["task_id"] == "spatial_rice_punjabcrs")
        self.assertIn("rho 1.0", registry_note)
        self.assertIn("Wave 5", registry_note)

    def test_no_record_categories_are_declared(self):
        absent = {r["category"] for r in self.rows
                  if r["status"] == "NO_RECORD"}
        self.assertEqual(absent, {"Enteric fermentation", "Manure management",
                                  "Manure on pasture"})


class TestTemporalHindcast(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = _rows(TEMPORAL)
        cls.ocac = [r for r in cls.rows
                    if r["task_id"] == "temporal_ocac_hindcast"
                    and r["status"] == "scored"]

    def test_both_baselines_at_every_origin_for_every_stream(self):
        seen = {(r["origin_id"], r["stream"], r["candidate"])
                for r in self.ocac}
        streams = {r["stream"] for r in self.ocac}
        self.assertEqual(len(streams), 6)
        for origin in ("fy2022", "fy2023", "fy2024"):
            for stream in streams:
                for candidate in ("flat", "last_year_shape"):
                    self.assertIn((origin, stream, candidate), seen)

    def test_the_regime_columns_are_declared_and_correct(self):
        for r in self.ocac:
            self.assertIn(r["train_regime"],
                          ("direct_monthly", "cumulative_differenced"))
            self.assertIn(r["test_regime"],
                          ("direct_monthly", "cumulative_differenced"))
            self.assertEqual(
                r["regime_change"],
                "yes" if r["train_regime"] != r["test_regime"] else "no")
        changes = {r["origin_id"]: r["regime_change"] for r in self.ocac}
        self.assertEqual(changes,
                         {"fy2022": "yes", "fy2023": "no", "fy2024": "yes"})

    def test_wape_is_a_share_distance(self):
        for r in self.ocac:
            self.assertGreaterEqual(float(r["wape_monthly_shares"]), 0.0)
            self.assertLessEqual(float(r["wape_monthly_shares"]), 2.0)

    def test_aviation_cross_publisher_rows_say_what_they_are(self):
        independent = [r for r in self.rows
                       if r["task_id"] == "temporal_aviation_independent"]
        scored = [r for r in independent if r["status"] == "scored"]
        self.assertTrue(scored)
        for r in scored:
            if r["candidate"] == "ocac_shape":
                self.assertIn("not a forecast", r["note"])
        publishers = {r["scored_against"] for r in independent}
        self.assertEqual(publishers, {"oecd_territory_domestic",
                                      "climatetrace_domestic"})
        # neither publisher covers FY2024 through 2025-06: declared, not dropped
        fy24 = [r for r in independent if r["origin_id"] == "fy2024"]
        self.assertTrue(fy24)
        self.assertTrue(all(r["status"] == "NO_RECORD" for r in fy24))

    def test_excluded_streams_are_declared(self):
        declared = [r for r in self.rows if r["status"] == "NO_RECORD"
                    and "single reporting year" in r["note"]]
        self.assertEqual(len(declared), 1)


class TestComparisonProtocol(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = _rows(COMPARISON)

    def test_the_protocol_columns_are_present_and_filled(self):
        for r in self.rows:
            for col in ("gwp", "engine_period", "gas_scope",
                        "bunker_treatment", "biogenic_treatment"):
                self.assertTrue((r.get(col) or "").strip(),
                                "%s/%s has no %s" % (r["source"],
                                                     r["engine_category"], col))

    def test_climate_trace_rows_compare_in_ar6(self):
        """The rc10 fix: the engine side resolves in the row's own GWP, so the
        TRACE agriculture total differs from the AR5 one the other totals use."""
        trace = {r["engine_category"]: r for r in self.rows
                 if r["source"] == "Climate TRACE"}
        self.assertEqual({r["gwp"] for r in trace.values()}, {"AR6"})
        ar6_total = float(trace["TOTAL"]["engine_Mt_co2e"])
        ar5_total = float(next(r for r in self.rows
                               if r["source"] == "FAOSTAT"
                               and r["engine_category"] == "TOTAL")
                          ["engine_Mt_co2e"])
        self.assertNotAlmostEqual(ar6_total, ar5_total, places=1)
        self.assertLess(ar6_total, ar5_total)   # CH4-heavy: AR6 < AR5

    def test_native_co2_gets_no_engine_value(self):
        crt = next(r for r in self.rows if r["gwp"] == "native CO2")
        self.assertEqual(crt["engine_Mt_co2e"], "n/a")

    def test_the_superseded_transport_row_says_so(self):
        old = next(r for r in self.rows if r["engine_category"] == "transport"
                   and r["year"] == "2022")
        self.assertEqual(old["comparison_role"], "superseded")
        self.assertIn("SUPERSEDED", old["note"])


if __name__ == "__main__":
    unittest.main()
