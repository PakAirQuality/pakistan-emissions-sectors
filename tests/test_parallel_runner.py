"""scripts/run_tests.py runs the same suite, and its exclusive lane is minimal and real.

The parallel runner exists for speed, and a fast runner that quietly runs FEWER tests than
the canonical one is worse than a slow runner. The canonical invocation stays
`python3 -m unittest discover -s tests` from the repo root - record_test_run.py shells it and
publishes its count - so the only thing that has to be true of the accelerator is that it
dispatches exactly what discovery finds.

These tests are the proof. The runner walks the filesystem rather than calling unittest's
discovery, because discovery imports every module it finds and the runner's parent process
should not be running 233 modules' import-time side effects. The walk is therefore held to
discovery's actual answer here, once, test id by test id.
"""
import os
import unittest

from _support import ROOT, load_script

TESTS = os.path.join(ROOT, "tests")


def _ids(suite):
    out = set()
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            out |= _ids(item)
        else:
            out.add(item.id())
    return out


class TheRunnerDispatchesTheWholeSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runner = load_script("run_tests")

    def test_the_walk_finds_the_modules_discovery_finds(self):
        loader = unittest.TestLoader()
        discovered = _ids(loader.discover(TESTS, top_level_dir=TESTS))
        # a module discovery could not import arrives as unittest.loader._FailedTest; that is
        # a broken checkout, not a disagreement about the module list, and it is reported as
        # itself rather than silently subtracted
        broken = sorted(i for i in discovered if "_FailedTest" in i)
        self.assertEqual(broken, [], "discovery could not import: %s" % broken)

        walked = set()
        for module in self.runner.discover_modules():
            walked |= _ids(loader.loadTestsFromName(module))
        self.assertEqual(walked, discovered,
                         "the runner would dispatch a different set of tests than "
                         "`unittest discover -s tests`")

    def test_every_exclusive_entry_names_a_module_that_exists(self):
        """A stale exclusive entry is a module quietly promoted back into the parallel lane -
        the exact hazard the lane exists to prevent, and invisible without this."""
        modules = set(self.runner.discover_modules())
        stale = sorted(set(self.runner.EXCLUSIVE) - modules)
        self.assertEqual(stale, [], "EXCLUSIVE names modules that no longer exist: %s" % stale)

    def test_every_exclusive_entry_carries_a_reason(self):
        """The lane costs wall time, so entry has a price. The first draft of it held nine
        modules on guesses like "serialises on the object store"; six were removed once the
        reasons had to be written down and read back."""
        for module, reason in self.runner.EXCLUSIVE.items():
            self.assertTrue(reason.strip(), module)
            self.assertGreater(len(reason), 60,
                               "%s: an exclusive entry without a real reason is a module "
                               "someone quarantined on a hunch" % module)

    def test_the_modules_that_write_into_the_live_tree_are_all_declared_exclusive(self):
        """Derived from the source, not from memory: a module that opens a file for writing
        under outputs/ or data/ must be in the exclusive lane, and this finds the next one.

        AST, not text matching. A first draft grepped for the zz_ self-test prefix and flagged
        two modules that merely pass such a name to an in-memory classifier, plus this file,
        which contains the pattern in its own source. A check that cries wolf gets switched off.

        SCOPE, stated so it is not mistaken for completeness: this sees DIRECT writes. A module
        that writes by spawning a producer - test_pbs_qim re-runs an ingest which rewrites a
        committed table - is invisible to it, and is declared by hand.
        """
        import ast
        live = {"OUT", "OUTPUTS", "DATA"}
        temp = ("tempfile", "mkdtemp", "TemporaryDirectory", "NamedTemporaryFile", "tmp")
        offenders = {}
        for module in self.runner.discover_modules():
            path = os.path.join(TESTS, module.replace(".", os.sep) + ".py")
            with open(path, encoding="utf-8") as handle:
                tree = ast.parse(handle.read(), path)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or not node.args:
                    continue
                name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
                if name == "open":
                    modes = [a.value for a in node.args[1:2] if isinstance(a, ast.Constant)]
                    modes += [k.value.value for k in node.keywords
                              if k.arg == "mode" and isinstance(k.value, ast.Constant)]
                    if not any(isinstance(m, str) and ("w" in m or "a" in m) for m in modes):
                        continue
                elif name != "write_table":
                    continue
                target = ast.unparse(node.args[0])
                if any(t in target for t in temp):
                    continue
                names = {n.id for n in ast.walk(node.args[0]) if isinstance(n, ast.Name)}
                if live & names:
                    offenders.setdefault(module, target)
        undeclared = sorted(set(offenders) - set(self.runner.EXCLUSIVE))
        self.assertEqual(
            undeclared, [],
            "these modules open a file for writing under outputs/ or data/ and are not in the "
            "exclusive lane of scripts/run_tests.py: %s"
            % ["%s -> %s" % (m, offenders[m]) for m in undeclared])


class TheGateCountsWhatTheRunnerPrints(unittest.TestCase):
    """scripts/gate_chain.sh greps the runner's output to decide whether a commit may land.

    That makes the two markers a contract rather than formatting, and the failure mode is the
    dangerous kind: rename [FAIL] in one file and the gate's grep counts ZERO failures, which
    reads exactly like a green suite. Nothing else in the tree would notice.
    """

    @classmethod
    def setUpClass(cls):
        cls.runner = load_script("run_tests")
        with open(os.path.join(ROOT, "scripts", "gate_chain.sh"), encoding="utf-8") as handle:
            cls.gate = handle.read()

    def _summary_lines(self, **result):
        import contextlib
        import io
        base = {"module": "m", "ran": 1, "failures": [], "errors": [], "skipped": [],
                "seconds": 1.0, "expected_failures": 0, "unexpected_successes": []}
        base.update(result)
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self.runner._summary([base], 1.0)
        return buffer.getvalue().splitlines()

    def test_the_gate_runs_the_parallel_runner_for_its_suite_step(self):
        self.assertIn("scripts/run_tests.py", self.gate)

    def _gate_patterns(self):
        """The regexes gate_chain.sh actually applies to the runner's output.

        Pulled out of the shell rather than restated here. A first draft of these tests
        asserted that the runner defines a marker AND that the gate contains a grep line -
        two independent facts - and it passed a planted rename of the marker, which is the
        precise defect it existed to catch. The pattern and the output have to MEET.
        """
        import re
        found = []
        for line in self.gate.splitlines():
            stripped = line.strip()
            if "suite.log" not in stripped or stripped.startswith("#"):
                continue
            # COUNTING lines only - the ones whose result decides whether the commit lands.
            # The gate also greps both markers together to PRINT what held it, inside the
            # branch that has already decided to fail; that one matches both kinds on
            # purpose and is not a contract about counting.
            if not re.match(r"^(ERRORS|FAILS)=", stripped):
                continue
            found += re.findall(r'"(\^[^"]+)"', stripped)
        self.assertTrue(found, "the gate counts nothing out of the runner's output any more")
        return found

    def _matches(self, pattern, lines):
        import re
        return [l for l in lines if re.search(pattern, l)]

    def test_the_gates_own_grep_matches_a_real_failure_line(self):
        lines = self._summary_lines(failures=[["test_x (m.C.test_x)", "AssertionError: no"]])
        hit = [p for p in self._gate_patterns() if self._matches(p, lines)]
        self.assertTrue(hit, "the gate's patterns %s match nothing the runner prints for a "
                             "FAILURE - it would count zero failures and read as green"
                        % self._gate_patterns())

    def test_the_gates_own_grep_matches_a_real_error_line(self):
        lines = self._summary_lines(errors=[["test_y (m.C.test_y)", "ImportError: nope"]])
        hit = [p for p in self._gate_patterns() if self._matches(p, lines)]
        self.assertTrue(hit, "the gate's patterns %s match nothing the runner prints for an "
                             "ERROR - a suite that could not run would pass the gate"
                        % self._gate_patterns())

    def test_no_counting_pattern_catches_both_kinds(self):
        """Load-bearing, not cosmetic. The gate's head-baseline exclusion list may only ever
        apply to FAILURES - a test that cannot run at all is never "expected to fail before a
        content commit". If one pattern caught both, an error would become excludable and the
        gate would pass a suite that had not run."""
        fail_lines = self._summary_lines(failures=[["test_x (m.C.test_x)", "AssertionError"]])
        error_lines = self._summary_lines(errors=[["test_y (m.C.test_y)", "ImportError"]])
        for pattern in self._gate_patterns():
            both = self._matches(pattern, fail_lines) and self._matches(pattern, error_lines)
            self.assertFalse(both, "%r matches a failure AND an error" % pattern)

    def test_the_gate_can_find_the_summary_line_it_echoes(self):
        """Display only, not counting - but a gate whose one human-readable line prints a
        traceback fragment is how this was noticed in the first place: the step originally
        tailed the log, and the runner prints its summary BEFORE the failure details."""
        import re
        lines = self._summary_lines(failures=[["test_x (m.C.test_x)", "AssertionError"]])
        display = [l for l in self.gate.splitlines()
                   if "suite.log" in l and l.strip().startswith("grep")]
        self.assertTrue(display, "the gate echoes nothing about the suite result")
        pattern = re.findall(r'"([^"]+)"', display[0])[0]
        self.assertTrue([l for l in lines if re.search(pattern, l)],
                        "the gate's summary grep %r matches nothing the runner prints"
                        % pattern)

    def test_the_exclusion_list_is_applied_to_failures_and_never_to_errors(self):
        counted = [l for l in self.gate.splitlines() if "EXCLUDE" in l and "grep" in l]
        self.assertTrue(counted, "the gate no longer filters anything with EXCLUDE")
        for line in counted:
            self.assertIn("FAIL", line)
            self.assertNotIn("ERROR", line)

    def test_a_clean_module_prints_neither_marker(self):
        """The other direction: a guard that fired on a green run would be noise."""
        lines = self._summary_lines()
        for marker in (self.runner.FAIL_MARKER, self.runner.ERROR_MARKER):
            self.assertFalse([l for l in lines if l.startswith(marker)], marker)


if __name__ == "__main__":
    unittest.main()
