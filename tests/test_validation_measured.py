"""The compact validation table is the measured evidence, read from the products, not typed.

WHY (rc69). The review asked for measured validation in one compact table. A table of
validation that was itself unvalidated would repeat the defect it reports, so its product
regenerates byte for byte, its TeX is rendered from that product only, every row names a
source that exists, and no parse or rebuild row may print an empty rejection count, which a
reader would take for zero.
"""
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.core.io import read_rows                                     # noqa: E402
from pkinv.report import validation_measured as module                  # noqa: E402


def _run(*args):
    return subprocess.run([sys.executable] + list(args), cwd=ROOT, capture_output=True,
                          text=True, env=dict(os.environ, PYTHONPATH=os.path.join(ROOT, "src")))


class TestTheMeasuredValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = read_rows(module.OUT)

    def test_the_product_regenerates_identically(self):
        run = _run("-m", module.__name__, "--check")
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_every_source_named_exists(self):
        for row in self.rows:
            for source in row["source_file"].split("; "):
                self.assertTrue(os.path.exists(os.path.join(ROOT, source)), row["check_id"])

    def test_parse_and_rebuild_rows_state_their_rejections(self):
        for row in self.rows:
            if row["group"] in ("source parsing", "reproduction"):
                self.assertNotEqual(row["failed_or_quarantined"], "", row["check_id"])

    def test_the_rebuilds_found_no_differing_file(self):
        rebuilds = [r for r in self.rows if r["check_id"].startswith("rebuild_")]
        self.assertEqual(len(rebuilds), 2)
        for row in rebuilds:
            self.assertEqual(row["failed_or_quarantined"], "0", row["check_id"])

    def test_the_closures_are_small(self):
        for row in self.rows:
            if row["group"] == "closure" and row["max_abs_residual"]:
                self.assertLess(abs(float(row["max_abs_residual"])), 1e-3, row["check_id"])


if __name__ == "__main__":
    unittest.main()
