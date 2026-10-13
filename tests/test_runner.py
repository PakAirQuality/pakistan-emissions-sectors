"""The runner harness's own invariants: clone byte-equality, ledgers,
write-then-raise. Everything runs against a temp directory - no repo outputs
are touched."""
import csv
import os
import sys
import tempfile
import unittest


from pkinv.core import runner as runner_mod
from pkinv.core.runner import Runner, QA_FIELDS
from _support import ROOT


class _TempOutputs(unittest.TestCase):
    """Point the harness's OUTPUTS at a temp dir for the duration."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old = runner_mod.OUTPUTS
        runner_mod.OUTPUTS = self._tmp.name

    def tearDown(self):
        runner_mod.OUTPUTS = self._old
        self._tmp.cleanup()

    def _bytes(self, name):
        with open(os.path.join(self._tmp.name, name), "rb") as f:
            return f.read()


class TestWriteMatchesTheClones(_TempOutputs):
    HEADER = ["category", "gas", "emissions_Gg"]
    ROWS = [["Rice cultivation", "CH4", "581.2"], ["Urea", "CO2", "17.0"]]

    def test_default_terminator_matches_the_eight_clone_family(self):
        """The eight `_write(name, header, rows)` clones use bare csv.writer,
        whose default terminator is \\r\\n - the harness must ship the same
        bytes or every migrated sector output lights up the manifest."""
        run = Runner("waste")
        run.write("t.csv", self.HEADER, self.ROWS)
        with tempfile.NamedTemporaryFile("w", newline="", suffix=".csv",
                                         delete=False) as f:
            w = csv.writer(f)
            w.writerow(self.HEADER)
            w.writerows(self.ROWS)
            ref = f.name
        try:
            self.assertEqual(self._bytes("t.csv"), open(ref, "rb").read())
        finally:
            os.unlink(ref)
        self.assertIn(b"\r\n", self._bytes("t.csv"))

    def test_pinned_terminator_matches_aviations_clone(self):
        run = Runner("aviation", lineterminator="\n")
        run.write("t.csv", self.HEADER, self.ROWS)
        self.assertNotIn(b"\r\n", self._bytes("t.csv"))
        self.assertEqual(self._bytes("t.csv").count(b"\n"), 3)

    def test_write_dicts_matches_the_ippu_fugitives_clone(self):
        """First-seen field inference + extrasaction=ignore, exactly."""
        rows = [{"a": 1, "b": 2}, {"b": 4, "c": 5, "a": 3}]
        run = Runner("ippu")
        run.write_dicts("d.csv", rows)
        got = self._bytes("d.csv").decode()
        # the clone's inference walks EVERY row, first-seen order: a, b, c
        self.assertTrue(got.startswith("a,b,c\r\n"), got)
        self.assertIn("1,2,\r\n", got)   # row 1 has no c: empty cell
        self.assertIn("3,4,5", got)
        # explicit narrower fields: extra keys dropped, not raised
        run.write_dicts("e.csv", rows, fields=["a"])
        self.assertEqual(self._bytes("e.csv"), b"a\r\n1\r\n3\r\n")


class TestTheLedgers(_TempOutputs):
    def test_every_write_lands_in_both_ledgers_in_order(self):
        run = Runner("fugitives")
        run.write("one.csv", ["x"], [["1"]])
        run.write_dicts("two.csv", [{"x": "2"}])
        run.record("three.md")
        self.assertEqual(run.written, ["one.csv", "two.csv", "three.md"])
        self.assertEqual([os.path.basename(p) for p in run.paths],
                         ["one.csv", "two.csv", "three.md"])
        self.assertTrue(all(os.path.isabs(p) for p in run.paths))


class TestFinalize(_TempOutputs):
    def test_green_run_writes_the_table_with_the_standard_gate(self):
        run = Runner("waste", declared=("one.csv",))
        run.write("one.csv", ["x"], [["1"]])
        checks = run.finalize(qa_table="waste_qa_2024.csv")
        self.assertEqual(len(checks), 1)
        rows = list(csv.DictReader(
            open(os.path.join(self._tmp.name, "waste_qa_2024.csv"))))
        self.assertEqual(list(rows[0].keys()), list(QA_FIELDS))
        self.assertEqual(rows[0]["check"], "declared outputs written")
        self.assertEqual(rows[0]["passed"], "True")
        self.assertGreater(len(rows[0]["note"]), 20)

    def test_a_failing_gate_still_writes_the_table_then_raises(self):
        """Write-then-raise: the shipped table must describe THIS run even
        when the run is red - the fugitives stale-QA-on-red class, closed."""
        run = Runner("fugitives", declared=("never_written.csv",))
        run.gate("a real check", False, actual=1, expected=2,
                 note="deliberately red so the ordering is provable")
        with self.assertRaises(AssertionError) as caught:
            run.finalize(qa_table="fug_qa_2024.csv")
        self.assertIn("fugitives QA failed", str(caught.exception))
        rows = list(csv.DictReader(
            open(os.path.join(self._tmp.name, "fug_qa_2024.csv"))))
        self.assertEqual(len(rows), 2)  # the real check + the standard gate
        self.assertEqual({r["passed"] for r in rows}, {"False"})
        self.assertIn("missing: never_written.csv", rows[1]["note"])

    def test_a_tolerated_failure_is_recorded_but_does_not_raise(self):
        """Aviation's one true warning: recorded as passed=False (the guard's
        DECLARED_WARNINGS ratchet must then explain it) without aborting."""
        run = Runner("aviation", lineterminator="\n")
        run.gate("airport_coordinate_coverage", False, 0.9, 1.0,
                 "one aerodrome carries no coordinate")
        checks = run.finalize(qa_table="av_qa.csv",
                              tolerated=("airport_coordinate_coverage",))
        self.assertEqual([c["passed"] for c in checks], [False, True])
        raw = self._bytes("av_qa.csv")
        self.assertNotIn(b"\r\n", raw)   # write_dicts honours the terminator
        self.assertIn(b"airport_coordinate_coverage,False,0.9,1.0", raw)

    def test_gate_rows_carry_the_fugitives_shape_verbatim(self):
        run = Runner("fugitives")
        run.gate("registered anchor year", True, 2024, 2024,
                 "no FY2020 production is mixed into the registered estimate")
        self.assertEqual(run.checks[0],
                         {"check": "registered anchor year", "passed": True,
                          "actual": 2024, "expected": 2024,
                          "note": "no FY2020 production is mixed into the "
                                  "registered estimate"})


if __name__ == "__main__":
    unittest.main()
