"""Incremental builds keep product integrity while avoiding unrelated producers."""
import contextlib
import dataclasses
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pkinv import build, run_all
from pkinv.build_support import FileDigests


class BuildCacheIntegrity(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.patch = patch.object(run_all, "ROOT", str(self.root))
        self.patch.start()
        (self.root / "outputs").mkdir()
        (self.root / "data").mkdir()
        (self.root / "input.txt").write_text("first")
        (self.root / "producer.py").write_text("pass")
        (self.root / "outputs/result.csv").write_text("value\n1\n")
        self.phase = run_all.Phase("producer", "producer.py", writes=("outputs/result.csv",),
                                    reads=("input.txt",), audited=True)
        self.cache = {"phases": {}}

    def tearDown(self):
        self.patch.stop()
        self.temp.cleanup()

    def record(self, phase=None):
        run_all.record_current(phase or self.phase, self.cache, ["producer.py"])

    def test_command_and_output_declaration_changes_invalidate(self):
        self.record()
        self.assertTrue(run_all.is_current(self.phase, self.cache))
        for phase in (dataclasses.replace(self.phase, target="producer.py --new-option"),
                      dataclasses.replace(self.phase, writes=("outputs/result.csv", "outputs/extra.csv"))):
            self.assertFalse(run_all.is_current(phase, self.cache))

    def test_environment_and_lock_changes_invalidate(self):
        self.record()
        with patch.dict(os.environ, {"PYTHONHASHSEED": "different"}):
            self.assertFalse(run_all.is_current(self.phase, self.cache))
        (self.root / "requirements.lock").write_text("new-package==1\n")
        self.assertFalse(run_all.is_current(self.phase, self.cache))

    def test_recursive_directory_membership_and_missing_output(self):
        folder = self.root / "data/nested"
        folder.mkdir()
        (folder / "a.csv").write_text("one")
        phase = dataclasses.replace(self.phase, reads=("data/",), writes=("outputs/",))
        self.record(phase)
        self.assertTrue(run_all.is_current(phase, self.cache))
        (folder / "b.csv").write_text("two")
        self.assertFalse(run_all.is_current(phase, self.cache))
        self.record(phase)
        (self.root / "outputs/result.csv").unlink()
        self.assertFalse(run_all.is_current(phase, self.cache))

    def test_same_size_edit_with_restored_mtime_does_not_fool_digest_index(self):
        index = FileDigests(str(self.root))
        path = self.root / "input.txt"
        stat = path.stat()
        first = index.digest(str(path), run_all._sha)
        path.write_text("other")
        os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        self.assertNotEqual(first, index.digest(str(path), run_all._sha))

    def test_workspace_symlink_alias_does_not_discard_receipts(self):
        alias = self.root / "alias"
        alias.symlink_to(self.root, target_is_directory=True)
        cache = {"schema": run_all.CACHE_SCHEMA, "root": str(alias),
                 "phases": {"producer": {"fingerprint": "preserved"}}}
        run_all.save_cache(cache)
        loaded = run_all.load_cache()
        self.assertEqual(loaded["phases"], cache["phases"])
        self.assertEqual(loaded["root"], str(self.root))

    def test_missing_secondary_output_is_never_current(self):
        phase = dataclasses.replace(self.phase, writes=("outputs/result.csv", "outputs/missing.csv"))
        self.record(phase)
        self.assertFalse(run_all.is_current(phase, self.cache))

    def test_catalog_metadata_is_scoped_to_consumed_tables(self):
        canonical = self.root / "data/canonical"
        canonical.mkdir()
        catalog = {"schema_version": "test", "tables": [
            {"table_id": "one", "columns": ["First"]},
            {"table_id": "two", "columns": ["Second"]}]}
        path = canonical / "catalog.json"
        path.write_text(json.dumps(catalog))
        observation = {"complete": True, "reads": ["data/canonical/catalog.json"],
                       "canonical_tables": ["one"]}
        run_all.record_current(self.phase, self.cache, ["producer.py"], observation)
        catalog["tables"][1]["columns"] = ["Unrelated"]
        path.write_text(json.dumps(catalog))
        self.assertTrue(run_all.is_current(self.phase, self.cache))
        catalog["tables"][0]["columns"] = ["Changed"]
        path.write_text(json.dumps(catalog))
        self.assertFalse(run_all.is_current(self.phase, self.cache))


class TinyBuildLifecycle(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "outputs").mkdir()
        (self.root / "data").mkdir()
        (self.root / "data/a.txt").write_text("one")
        (self.root / "data/b.txt").write_text("two")
        self.phases = []
        for letter in ("a", "b"):
            (self.root / (letter + ".py")).write_text(
                "from pathlib import Path\n"
                "value = Path('data/%s.txt').read_text()\n" % letter +
                "Path('outputs/%s.csv').write_text(value)\n" % letter)
            self.phases.append(run_all.Phase(letter, letter + ".py", True,
                                             reads=("data/" + letter + ".txt",),
                                             writes=("outputs/" + letter + ".csv",), audited=True))
        self.patcher = patch.object(run_all, "ROOT", str(self.root))
        self.patcher.start()
        self.cache = {"schema": run_all.CACHE_SCHEMA, "root": str(self.root), "phases": {}}

    def tearDown(self):
        self.patcher.stop()
        self.temp.cleanup()

    def execute(self, jobs=1):
        ledger = self.root / "logs/test-ledger.json"
        with contextlib.redirect_stdout(io.StringIO()):
            code = build.execute(self.phases, build.dependencies(self.phases, self.cache),
                                 self.cache, jobs=jobs, ledger_path=str(ledger))
        self.assertEqual(code, 0)
        return json.loads(ledger.read_text())

    def test_noop_and_single_input_rebuild_match_clean_outputs(self):
        self.assertEqual(self.execute(jobs=2)["executed"], 2)
        self.assertEqual(self.execute()["executed"], 0)
        (self.root / "data/a.txt").write_text("edited")
        ledger = self.execute()
        self.assertEqual([(p["label"], p["status"]) for p in ledger["phases"]],
                         [("a", "OK"), ("b", "CACHED")])
        self.assertEqual((self.root / "outputs/a.csv").read_text(), "edited")
        self.assertEqual((self.root / "outputs/b.csv").read_text(), "two")

    def test_observed_undeclared_side_output_is_rebuilt_when_deleted(self):
        path = self.root / "a.py"
        path.write_text(path.read_text() + "Path('outputs/side.csv').write_text('side')\n")
        self.execute()
        (self.root / "outputs/side.csv").unlink()
        self.assertEqual(self.execute()["executed"], 1)

    def test_first_warm_run_uses_the_learned_managed_input_scope(self):
        self.phases = [dataclasses.replace(self.phases[0], audited=False)]
        catalog = self.root / "data/catalog"
        catalog.mkdir()
        (catalog / "assets.csv").write_text(
            "asset_id,legacy_path,path,canonical_path,purpose\n"
            "unrelated,data/b.txt,data/b.txt,data/sectors/other/canonical/b.csv,activity\n")
        self.assertEqual(self.execute()["executed"], 1)
        self.assertEqual(self.execute()["executed"], 0)
        (self.root / "data/b.txt").write_text("changed unrelated managed table")
        self.assertEqual(self.execute()["executed"], 0)

    def test_dry_run_rechecks_unobserved_source_membership_without_writes(self):
        self.phases = [dataclasses.replace(self.phases[0], audited=False)]
        self.execute()
        before = (self.root / "logs/build_cache.json").read_bytes()
        with contextlib.redirect_stdout(io.StringIO()) as output:
            build.dry_run(self.phases, self.cache)
        self.assertIn("CACHED a", output.getvalue())
        (self.root / "data/new_native_input.csv").write_text("new")
        with contextlib.redirect_stdout(io.StringIO()) as output:
            build.dry_run(self.phases, self.cache)
        self.assertIn("RUN    a", output.getvalue())
        self.assertEqual((self.root / "logs/build_cache.json").read_bytes(), before)

    def test_group_dry_run_and_execution_share_full_registry_input_universe(self):
        phase = dataclasses.replace(self.phases[0], audited=False)
        excluded = dataclasses.replace(self.phases[1], writes=("data/generated.csv",))
        (self.root / "data/generated.csv").write_text("existing generated value")
        full = [phase, excluded]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(build.execute([phase], {phase.label: set()}, self.cache,
                                           registry_phases=full), 0)
        with patch.object(run_all, "PHASES", full), patch.object(build, "FINALIZATION", {"b"}), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(build.main(["--dry-run"]), 0)
        self.assertIn("CACHED a", output.getvalue())

    def test_optional_generated_file_appearing_invalidates_unobserved_exists_probe(self):
        self.phases = [dataclasses.replace(self.phases[0], audited=False)]
        (self.root / "a.py").write_text(
            "from pathlib import Path\n"
            "p = Path('outputs/optional.csv')\n"
            "Path('outputs/a.csv').write_text(p.read_text() if p.exists() else 'absent')\n")
        self.execute()
        self.assertEqual(self.execute()["executed"], 0)
        (self.root / "outputs/optional.csv").write_text("present")
        self.assertEqual(self.execute()["executed"], 1)
        self.assertEqual((self.root / "outputs/a.csv").read_text(), "present")
        self.assertEqual(self.execute()["executed"], 0)
        (self.root / "outputs/optional.csv").unlink()
        self.assertEqual(self.execute()["executed"], 1)
        self.assertEqual((self.root / "outputs/a.csv").read_text(), "absent")

    def test_legacy_changed_main_uses_optional_product_membership_guard(self):
        phase = dataclasses.replace(self.phases[0], audited=False)
        (self.root / "a.py").write_text(
            "from pathlib import Path\n"
            "p = Path('outputs/optional.csv')\n"
            "Path('outputs/a.csv').write_text(p.read_text() if p.exists() else 'absent')\n")
        with patch.object(run_all, "PHASES", [phase]), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(run_all.main(["--changed"]), 0)
            (self.root / "outputs/optional.csv").write_text("present")
            self.assertEqual(run_all.main(["--changed"]), 0)
        self.assertEqual((self.root / "outputs/a.csv").read_text(), "present")

    def test_late_secondary_document_write_does_not_expand_other_task_membership(self):
        self.phases = [dataclasses.replace(p, audited=False) for p in self.phases]
        for letter in ("a", "b"):
            (self.root / ("outputs/%s.csv" % letter)).write_text("seed")
        (self.root / "summary.md").write_text("existing document")
        source = self.root / "b.py"
        source.write_text(source.read_text() + "Path('summary.md').write_text('derived document')\n")
        self.assertEqual(self.execute()["executed"], 2)
        self.assertEqual(self.execute()["executed"], 0)

    def test_failed_phase_does_not_keep_success_cache(self):
        self.execute()
        (self.root / "a.py").write_text("raise SystemExit(3)\n")
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = build.execute(self.phases, build.dependencies(self.phases, self.cache), self.cache)
        self.assertEqual(code, 1)
        self.assertNotIn("a", self.cache["phases"])

    def assert_unstable(self, source, expected):
        phase = dataclasses.replace(self.phases[0], audited=False)
        (self.root / "a.py").write_text(source)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as errors:
            code = build.execute([phase], {phase.label: set()}, self.cache)
        self.assertEqual(code, 1)
        self.assertIn("changed while a was running", errors.getvalue())
        self.assertIn(expected, errors.getvalue())
        self.assertNotIn("a", self.cache["phases"])

    def test_native_source_edit_during_task_cannot_be_mistaken_for_owned_output(self):
        self.assert_unstable(
            "from pathlib import Path\nimport subprocess, sys\n"
            "Path('outputs/a.csv').write_text(Path('data/a.txt').read_text())\n"
            "subprocess.run([sys.executable, '-c', \"from pathlib import Path; "
            "Path('data/a.txt').write_text('external edit')\"], check=True)\n", "data/a.txt")

    def test_code_edit_during_task_is_not_cached(self):
        self.assert_unstable(
            "from pathlib import Path\nimport subprocess, sys\n"
            "Path('outputs/a.csv').write_text('old implementation')\n"
            "subprocess.run([sys.executable, '-c', \"from pathlib import Path; "
            "Path('a.py').write_text('# changed implementation')\"], check=True)\n", "a.py")

    def test_file_added_after_directory_discovery_is_not_cached(self):
        (self.root / "inputs").mkdir()
        (self.root / "inputs/first.csv").write_text("one")
        self.assert_unstable(
            "from pathlib import Path\nimport subprocess, sys\n"
            "names = sorted(p.name for p in Path('inputs').iterdir())\n"
            "Path('outputs/a.csv').write_text(','.join(names))\n"
            "subprocess.run([sys.executable, '-c', \"from pathlib import Path; "
            "Path('inputs/late.csv').write_text('new file')\"], check=True)\n", "inputs/ (membership)")

    def test_optional_output_added_after_exists_probe_is_not_cached(self):
        self.assert_unstable(
            "from pathlib import Path\nimport subprocess, sys\n"
            "Path('outputs/a.csv').write_text(str(Path('outputs/optional.csv').exists()))\n"
            "subprocess.run([sys.executable, '-c', \"from pathlib import Path; "
            "Path('outputs/optional.csv').write_text('new file')\"], check=True)\n",
            "generated products/ (membership)")

    def test_strict_reexecutes_idempotent_validation_without_requiring_mtime_churn(self):
        self.execute()
        source = self.root / "a.py"
        source.write_text("from pathlib import Path\n"
                          "assert Path('data/a.txt').read_text() == Path('outputs/a.csv').read_text()\n")
        product = self.root / "outputs/a.csv"
        os.utime(product, (1, 1))
        phase = dataclasses.replace(self.phases[0], idempotent=True)
        with patch.object(run_all, "PHASES", [phase]), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(run_all.main(["--strict"]), 0)
        self.assertEqual(product.stat().st_mtime, 1)

    def test_strict_subprocess_cannot_inherit_developer_freshness_proof(self):
        (self.root / "strict_probe.py").write_text(
            "import os\nassert 'PKINV_BUILD_VERIFIED_OUTPUTS' not in os.environ\n")
        with patch.dict(os.environ, {"PKINV_BUILD_VERIFIED_OUTPUTS": "/tmp/untrusted-proof.json"}):
            code, _, _, stderr, _ = run_all._run("strict_probe.py")
        self.assertEqual(code, 0, stderr)

    def test_target_includes_only_its_declared_prerequisites(self):
        third = run_all.Phase("third", "third.py", writes=("outputs/third.csv",),
                              reads=("outputs/a.csv",), audited=True)
        selected, _graph = build.select(self.phases + [third], ["outputs/third.csv"], self.cache)
        self.assertEqual([p.label for p in selected], ["a", "third"])

    def test_sector_selection_keeps_independent_producers(self):
        phases = [dataclasses.replace(self.phases[0], target="pkinv.sectors.transport.runner"),
                  dataclasses.replace(self.phases[1], target="pkinv.sectors.transport.shape")]
        selected, _ = build.select(phases, build.sector_targets(phases, ["transport"]), self.cache)
        self.assertEqual([p.label for p in selected], ["a", "b"])

    def test_directory_discovery_keeps_producers_of_new_members(self):
        consumer = run_all.Phase("consumer", "consumer.py", writes=("summary.csv",),
                                 reads=("outputs/a.csv",), audited=True)
        self.cache["phases"]["consumer"] = {"observation_complete": True,
                                            "directory_reads": ["outputs"]}
        selected, _ = build.select(self.phases + [consumer], ["consumer"], self.cache)
        self.assertEqual([p.label for p in selected], ["a", "b", "consumer"])

    def test_directory_input_contains_child_file_producer(self):
        consumer = run_all.Phase("consumer", "consumer.py", writes=("summary.csv",),
                                 reads=("outputs/",), audited=True)
        selected, _ = build.select(self.phases + [consumer], ["consumer"], self.cache)
        self.assertEqual([p.label for p in selected], ["a", "b", "consumer"])

    def test_observed_forward_dependency_is_an_error(self):
        self.cache["phases"]["a"] = {"observation_complete": True,
                                    "observed_reads": ["outputs/b.csv"]}
        with self.assertRaisesRegex(ValueError, "before producer b"):
            build.dependencies(self.phases, self.cache)

    def test_unaudited_tasks_cannot_run_in_parallel(self):
        phases = [dataclasses.replace(p, audited=False) for p in self.phases]
        self.assertEqual(build._ready_batch(phases, set(), build.dependencies(phases, self.cache),
                                           4, self.cache), [phases[0]])

    def test_overlapping_directory_ownership_cannot_run_in_parallel(self):
        phases = [self.phases[0], dataclasses.replace(self.phases[1], writes=("outputs/",))]
        self.assertTrue(build._ownership_problems(phases, self.cache))
        self.assertEqual(build._ready_batch(phases, set(), build.dependencies(phases, self.cache),
                                           4, self.cache), [phases[0]])


if __name__ == "__main__":
    unittest.main()
