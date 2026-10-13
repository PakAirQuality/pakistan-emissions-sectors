"""--only and --changed: a build that does less, and cannot quietly do less than it says.

rc40's validation package compared 83 products, called 82 of them identical, and 59 of its
107 phases had never executed - the products it compared were the copied ones. An incremental
build is that hazard with better manners, so these tests are mostly about what the mode
REFUSES to do. The speed is not the thing that needs guarding.

The fake-phase harness is the one tests/test_run_ledger.py established: main() is driven over
a substituted PHASES list of tiny scripts in a temporary tree, and no product is built.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

from pkinv import run_all


class TheModeRefusesWhatItMustRefuse(unittest.TestCase):
    def test_changed_is_refused_under_strict(self):
        """A reproduction rebuilds every phase; that is the whole of what --strict asserts.
        The two flags must not be combinable at all, not merely discouraged in prose."""
        with self.assertRaises(SystemExit) as caught:
            run_all.main(["--changed", "--strict"])
        self.assertIn("mutually exclusive", str(caught.exception))

    def test_only_refuses_a_label_no_phase_carries(self):
        """A typo in --only would otherwise build nothing and exit 0, which reads exactly like
        a build in which everything was already current."""
        with self.assertRaises(SystemExit) as caught:
            run_all.main(["--only", "No Such Phase"])
        self.assertIn("no phase labelled", str(caught.exception))

    def test_a_phase_whose_reads_are_undeclared_can_never_be_skipped(self):
        """`reads` is a tri-state and None means "inputs NOT audited" - 64 of the 149 phases.
        Those must run every time. This asserts it over the real phase list, so declaring a
        phase's reads is the only way to make it skippable."""
        cache = {"phases": {p.label: {"closure": ["src/pkinv/run_all.py"],
                                      "fingerprint": "x", "writes": {}} for p in run_all.PHASES}}
        unaudited = [p for p in run_all.PHASES if p.reads is None]
        self.assertTrue(unaudited, "the tri-state is gone; this test needs rewriting")
        for phase in unaudited:
            self.assertIsNone(run_all._fingerprint(phase, cache), phase.label)
            self.assertFalse(run_all.is_current(phase, cache), phase.label)

    def test_a_phase_with_no_recorded_closure_can_never_be_skipped(self):
        """The closure is learned by RUNNING. A phase that has never been observed running -
        or that died before its atexit hook - has no closure, and an absent closure must not
        be read as an empty one."""
        phase = run_all.Phase("p", "x.py", writes=("outputs/x.csv",), reads=())
        self.assertIsNone(run_all._fingerprint(phase, {"phases": {"p": {}}}))
        self.assertFalse(run_all.is_current(phase, {"phases": {"p": {"fingerprint": "x"}}}))


class TheFingerprintIsContentNotTime(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pakemis-incremental-")
        self._root = run_all.ROOT
        run_all.ROOT = self.tmp
        os.makedirs(os.path.join(self.tmp, "outputs"))
        self.input = os.path.join(self.tmp, "outputs", "in.csv")
        with open(self.input, "w") as handle:
            handle.write("a,b\n1,2\n")
        self.phase = run_all.Phase("p", "x.py", writes=("outputs/out.csv",),
                                   reads=("outputs/in.csv",))
        with open(os.path.join(self.tmp, "outputs", "out.csv"), "w") as handle:
            handle.write("done\n")
        self.cache = {"phases": {"p": {"closure": []}}}

    def tearDown(self):
        run_all.ROOT = self._root

    def _print(self):
        self.cache["phases"]["p"]["closure"] = ["outputs/in.csv"]
        return run_all._fingerprint(self.phase, self.cache)

    def test_a_touch_does_not_move_it(self):
        """The load-bearing choice. A phase that reruns and writes byte-identical output must
        not invalidate everything downstream of it, and a file whose mtime moved without its
        bytes moving is not a reason to rebuild anything."""
        before = self._print()
        os.utime(self.input, (0, 0))
        self.assertEqual(before, self._print())

    def test_an_edit_moves_it(self):
        before = self._print()
        with open(self.input, "a") as handle:
            handle.write("3,4\n")
        self.assertNotEqual(before, self._print())

    def test_a_missing_input_moves_it_rather_than_raising(self):
        """A read that has been deleted is a rebuild, not a crash - the phase is the thing
        that gets to complain about its own missing input."""
        before = self._print()
        os.remove(self.input)
        self.assertNotEqual(before, self._print())

    def test_a_hand_edited_output_forces_a_rerun(self):
        """The declared writes are hashed too. Someone who edits a product by hand gets it
        overwritten on the next build, rather than kept because the inputs happened to match."""
        run_all.record_current(self.phase, self.cache, ["outputs/in.csv"])
        self.assertTrue(run_all.is_current(self.phase, self.cache))
        with open(os.path.join(self.tmp, "outputs", "out.csv"), "a") as handle:
            handle.write("a hand edit nobody declared\n")
        self.assertFalse(run_all.is_current(self.phase, self.cache))

    def test_a_deleted_output_forces_a_rerun(self):
        run_all.record_current(self.phase, self.cache, ["outputs/in.csv"])
        self.assertTrue(run_all.is_current(self.phase, self.cache))
        os.remove(os.path.join(self.tmp, "outputs", "out.csv"))
        self.assertFalse(run_all.is_current(self.phase, self.cache))


class TheClosureIsTheCodeThePhaseActuallyRan(unittest.TestCase):
    """The closure is learned by RUNNING, because a static import scan would miss the ten
    sector engines: src/pkinv/core/registry.py loads each of them through
    importlib.import_module() from a registry, so nothing in the source text names them.

    These assert the closure's CONTENT. Two earlier designs for capturing it failed silently
    and in the safe direction - an empty closure reads as "never observed running", so the
    phase simply never skips - and a test that only asked whether a closure existed passed
    against both of them.
    """

    def test_the_module_map_covers_the_package_and_the_scripts(self):
        owned = run_all._module_files()
        self.assertEqual(owned["pkinv.run_all"], os.path.join("src", "pkinv", "run_all.py"))
        self.assertEqual(owned["pkinv"], os.path.join("src", "pkinv", "__init__.py"),
                         "a package must map to its __init__, not vanish")
        self.assertEqual(owned["pkinv.report.grid_cube"],
                         os.path.join("src", "pkinv", "report", "grid_cube.py"))
        self.assertIn("build_adm2_package", owned)

    def test_an_importtime_report_becomes_repository_paths(self):
        owned = run_all._module_files()
        report = "\n".join([
            "import time:       104 |        104 |   pkinv.paths",
            "import time:      1832 |       1936 | pkinv.core.io",
            "import time:       210 |        210 |     json",           # stdlib: not ours
            "not an import line at all",
        ])
        closure = run_all._closure_from(report, "pkinv.report.grid_cube", owned)
        self.assertIn(os.path.join("src", "pkinv", "paths.py"), closure)
        self.assertIn(os.path.join("src", "pkinv", "core", "io.py"), closure)
        self.assertNotIn("json", str(closure))
        self.assertIn(os.path.join("src", "pkinv", "report", "grid_cube.py"), closure,
                      "the entry point is the one file no import line ever names")

    def test_a_script_phase_contributes_its_own_path(self):
        closure = run_all._closure_from("", "scripts/build_adm2_package.py", run_all._module_files())
        self.assertEqual(closure, ["scripts/build_adm2_package.py"])

    def test_the_importtime_report_is_stripped_back_out_of_stderr(self):
        """A build's stderr has to look exactly as it always did, or every reader of it - the
        ledger's stderr_tail included - has to learn about this mode."""
        noisy = "import time:  104 | 104 | pkinv.paths\nreal warning from the phase\n"
        self.assertEqual(run_all._strip_importtime(noisy), "real warning from the phase")

    def test_a_real_phase_reports_the_code_it_ran(self):
        """End to end against the real tree, on a phase that is fast and reads one file: the
        closure must contain the phase's own module AND the core modules it reached through
        the package, not merely be non-empty."""
        phase = {p.label: p for p in run_all.PHASES}["Agriculture fiscal history"]
        owned = run_all._module_files()
        code, _secs, _out, stderr, closure = run_all._run(phase.target, owned)
        self.assertEqual(code, 0, stderr)
        self.assertIn(os.path.join("src", "pkinv", "sectors", "agriculture", "fiscal_series.py"),
                      closure)
        self.assertIn(os.path.join("src", "pkinv", "core", "io.py"), closure)
        self.assertGreater(len(closure), 5, "a closure of one file is the failure mode")
        self.assertNotIn("import time:", stderr)


class TheLedgerCannotMisreportASkip(unittest.TestCase):
    """The rc40 shape, guarded: a run that skipped a phase must never read as one that ran it."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pakemis-incremental-run-")
        self._root, self._phases = run_all.ROOT, run_all.PHASES
        run_all.ROOT = self.tmp
        os.makedirs(os.path.join(self.tmp, "outputs"))

    def tearDown(self):
        run_all.ROOT, run_all.PHASES = self._root, self._phases

    def _phase(self, label, filename):
        script = ("import os; open(os.path.join(%r,'outputs',%r),'w').write('1')"
                  % (self.tmp, filename))
        with open(os.path.join(self.tmp, "%s.py" % label), "w") as handle:
            handle.write(script)
        return run_all.Phase(label, "%s.py" % label, True,
                             writes=("outputs/%s" % filename,), reads=(), audited=True)

    def _ledger(self, argv):
        path = os.path.join(self.tmp, "logs", "ledger.json")
        code = run_all.main(argv + ["--ledger", path])
        with open(path) as handle:
            return code, {p["label"]: p for p in json.load(handle)["phases"]}

    def test_a_current_phase_is_recorded_as_a_skip_and_not_as_ok(self):
        run_all.PHASES = [self._phase("one", "one.csv"), self._phase("two", "two.csv")]
        code, first = self._ledger(["--changed"])
        self.assertEqual(code, 0)
        self.assertEqual(first["one"]["status"], "OK")
        code, second = self._ledger(["--changed"])
        self.assertEqual(code, 0)
        self.assertEqual(second["one"]["status"], "CACHED")
        self.assertEqual(second["two"]["status"], "CACHED")
        self.assertEqual(second["one"].get("written", []), [],
                         "a skipped phase must claim nothing was written")

    def test_only_records_every_other_phase_as_skipped_not_as_run(self):
        run_all.PHASES = [self._phase("one", "one.csv"), self._phase("two", "two.csv")]
        code, ledger = self._ledger(["--only", "two"])
        self.assertEqual(code, 0)
        self.assertEqual(ledger["one"]["status"], "SKIP (--only)")
        self.assertEqual(ledger["two"]["status"], "OK")

    def test_a_phase_that_failed_is_not_recorded_as_current(self):
        """Otherwise the next --changed run would skip a phase that has never succeeded."""
        path = os.path.join(self.tmp, "boom.py")
        with open(path, "w") as handle:
            handle.write("import sys; sys.exit(3)")
        run_all.PHASES = [run_all.Phase("boom", "boom.py", True,
                                        writes=("outputs/boom.csv",), reads=())]
        self.assertEqual(run_all.main(["--changed"]), 1)
        cache = run_all.load_cache()
        self.assertFalse(cache["phases"].get("boom", {}).get("fingerprint"))


if __name__ == "__main__":
    unittest.main()
