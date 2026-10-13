"""rc41: the run ledger records what each phase wrote, and --strict stops at the first phase that cannot run.

The rc40 reproduction compared 83 products and called 82 identical while 59 of 107 phases
had never executed. The ledger is the record that makes that shape visible: per phase, its
status and the files observed to change under outputs/ while it ran. These tests exercise
the three pieces on a temporary tree with fake phases - no product is built - and hold the
contract: a written file is attributed to the phase that wrote it, an unchanged file to no
phase, a non-core failure is a `skip (error)` without --strict and a `FAIL` that ends the
run with it, and the ledger is written on every exit path.
"""
import json
import os
import tempfile
import unittest

from pkinv import run_all


class TestSnapshotAndWritten(unittest.TestCase):
    def test_written_names_exactly_the_changed_files(self):
        before = {"outputs/a.csv": (1, 10), "outputs/b.csv": (2, 20)}
        after = {"outputs/a.csv": (1, 10), "outputs/b.csv": (3, 20), "outputs/c.csv": (4, 5)}
        self.assertEqual(run_all._written(before, after), ["outputs/b.csv", "outputs/c.csv"])

    def test_a_rewrite_of_identical_bytes_with_a_new_mtime_counts_as_written(self):
        """'Observed changed', not 'attempted': the ledger records that the phase touched the
        file. A phase that rewrites identical bytes is still that file's writer."""
        before = {"outputs/a.csv": (1, 10)}
        after = {"outputs/a.csv": (2, 10)}
        self.assertEqual(run_all._written(before, after), ["outputs/a.csv"])


class TestTheLedgerOnAFakeRun(unittest.TestCase):
    """Drive main() over a substituted PHASES list of tiny `python -c` targets."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pakemis-ledger-")
        self._root = run_all.ROOT
        run_all.ROOT = self.tmp
        os.makedirs(os.path.join(self.tmp, "outputs"))
        self._phases = run_all.PHASES

    def tearDown(self):
        run_all.ROOT = self._root
        run_all.PHASES = self._phases

    def _phase(self, label, code, writes, core=True, filename="x.csv"):
        # each fake phase writes its declared file then exits with `code`
        script = ("import os,sys; p=os.path.join(%r,'outputs',%r); open(p,'w').write('1'); sys.exit(%d)"
                  % (self.tmp, filename, code))
        path = os.path.join(self.tmp, "%s.py" % label.replace(" ", "_"))
        with open(path, "w") as handle:
            handle.write(script)
        return run_all.Phase(label, "%s.py" % label.replace(" ", "_"), core, writes=writes)

    def test_each_written_file_is_attributed_to_its_phase(self):
        run_all.PHASES = [self._phase("one", 0, ("outputs/one.csv",), filename="one.csv"),
                          self._phase("two", 0, ("outputs/two.csv",), filename="two.csv")]
        ledger = os.path.join(self.tmp, "logs", "ledger.json")
        code = run_all.main(["--ledger", ledger])
        self.assertEqual(code, 0)
        with open(ledger) as handle:
            record = json.load(handle)
        self.assertEqual(record["schema"], run_all.LEDGER_SCHEMA)
        by_label = {p["label"]: p for p in record["phases"]}
        self.assertEqual(by_label["one"]["written"], ["outputs/one.csv"])
        self.assertEqual(by_label["two"]["written"], ["outputs/two.csv"])
        self.assertEqual(by_label["one"]["status"], "OK")

    def test_a_non_core_failure_is_a_skip_without_strict_and_a_stop_with_it(self):
        run_all.PHASES = [self._phase("bad", 3, ("outputs/bad.csv",), core=False, filename="bad.csv"),
                          self._phase("after", 0, ("outputs/after.csv",), filename="after.csv")]
        ledger = os.path.join(self.tmp, "logs", "lenient.json")
        self.assertEqual(run_all.main(["--ledger", ledger]), 0)
        with open(ledger) as handle:
            lenient = json.load(handle)
        self.assertEqual([p["status"] for p in lenient["phases"]], ["skip (error)", "OK"])
        ledger = os.path.join(self.tmp, "logs", "strict.json")
        self.assertEqual(run_all.main(["--strict", "--ledger", ledger]), 1)
        with open(ledger) as handle:
            strict = json.load(handle)
        self.assertEqual([p["status"] for p in strict["phases"]], ["FAIL"])
        self.assertEqual(strict["exit_code"], 1)
        self.assertTrue(strict["strict"])

    def test_from_resumes_at_the_named_phase_and_records_the_skips(self):
        """--from is a development flag for iterating a strict rebuild in a kept tree: the
        phases before the label are recorded as SKIP (resume), never as OK, so a ledger
        that carries one can never pass as a reproduction ledger."""
        run_all.PHASES = [self._phase("one", 0, ("outputs/one.csv",), filename="one.csv"),
                          self._phase("two", 0, ("outputs/two.csv",), filename="two.csv")]
        ledger = os.path.join(self.tmp, "logs", "resume.json")
        self.assertEqual(run_all.main(["--strict", "--from", "two", "--ledger", ledger]), 0)
        with open(ledger) as handle:
            record = json.load(handle)
        self.assertEqual([(p["label"], p["status"]) for p in record["phases"]],
                         [("one", "SKIP (resume)"), ("two", "OK")])
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "outputs", "one.csv")))
        with self.assertRaises(SystemExit):
            run_all.main(["--from", "no such phase"])

    def test_the_ledger_carries_the_seeded_list(self):
        run_all.PHASES = [self._phase("one", 0, ("outputs/one.csv",), filename="one.csv")]
        seeded = os.path.join(self.tmp, "logs", "seeded.json")
        os.makedirs(os.path.dirname(seeded))
        with open(seeded, "w") as handle:
            json.dump([{"path": "outputs/held.csv", "sha256": "0" * 64}], handle)
        ledger = os.path.join(self.tmp, "logs", "ledger.json")
        run_all.main(["--ledger", ledger, "--seeded", seeded])
        with open(ledger) as handle:
            self.assertEqual(json.load(handle)["seeded"][0]["path"], "outputs/held.csv")


if __name__ == "__main__":
    unittest.main()
