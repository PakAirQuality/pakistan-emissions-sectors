"""The axis register: one row per structural axis, statuses closed, reasons where
unpriced. The ninth review found three products describing the axis space with no
single table to reconcile them against; this file is that table's contract.

Run:  python3 -m unittest discover tests -p "test_axis_register.py"
"""

from pkinv.assets import asset_path
import csv
import os
import unittest
from pkinv.core.io import read_rows
from _support import ROOT

OUT = os.path.join(ROOT, "outputs", "national_axis_register.csv")

STATUSES = ("priced", "unpriced")


def _rows():
    return read_rows(OUT, comments=False)


def _axes():
    path = asset_path(ROOT, "data", "scenarios.csv")
    return [r["axis"] for r in read_rows(path)]


class TestAxisRegister(unittest.TestCase):
    def test_one_row_per_registered_axis(self):
        self.assertEqual(sorted(r["axis"] for r in _rows()), sorted(_axes()))

    def test_statuses_are_from_the_closed_vocabulary(self):
        for r in _rows():
            self.assertIn(r["priced_status"], STATUSES, r["axis"])

    def test_every_grain_column_is_typed(self):
        """Configuration parity, the sixteenth review's item 9: which grains an
        alternative ships at is a ROW per axis, never a free-text note in a sector
        CSV. An availability starts 'available (' and names its artifact; an absence
        starts with its typed reason."""
        # available_independent_run (Wave 6): a real conditional MC on a private
        # per-scenario seed - an interval from an independent run, never a
        # per-draw delta; the two-tier honesty the uncertainty grain demanded.
        prefixes = ("available (", "available_independent_run (",
                    "delta_scalar_only", "reference_only")
        for r in _rows():
            for column in ("monthly_grain", "spatial_grain", "uncertainty_grain"):
                self.assertTrue(r[column].startswith(prefixes),
                                "%s %s: %r" % (r["axis"], column, r[column]))

    def test_unpriced_rows_carry_reasons_and_only_they_do(self):
        for r in _rows():
            if r["priced_status"] == "unpriced":
                self.assertTrue(r["reason_if_unpriced"].strip(), r["axis"])
                self.assertEqual(r["national_delta_Mt"], "", r["axis"])
            else:
                self.assertEqual(r["reason_if_unpriced"], "", r["axis"])
                self.assertTrue(r["national_delta_Mt"].strip(), r["axis"])

    def test_configuration_membership_agrees_with_the_configurations_file(self):
        path = os.path.join(ROOT, "outputs", "national_configurations.csv")
        with open(path, newline="", encoding="utf-8") as handle:
            config_axes = {r["axis"] for r in csv.DictReader(handle)
                           if r["axis"] and not r["axis"].startswith("JOINT")}
        for r in _rows():
            expected = "yes" if r["axis"] in config_axes else "no"
            self.assertEqual(r["in_configurations"], expected, r["axis"])

    def test_no_probability_like_column(self):
        with open(OUT, newline="", encoding="utf-8") as handle:
            header = next(csv.reader(handle))
        for col in header:
            for word in ("probability", "prob", "weight", "likelihood", "prior"):
                self.assertNotIn(word, col.lower())

    def test_the_product_regenerates_identically(self):
        from pkinv.report import national_axis_register
        fresh = national_axis_register.build()
        shipped = _rows()
        self.assertEqual(len(fresh), len(shipped))
        for f, s in zip(fresh, shipped):
            for col in national_axis_register.FIELDS:
                self.assertEqual(str(f[col]), s[col], "%s.%s" % (f["axis"], col))

    def test_family_ids_agree_with_the_shared_mapping(self):
        from pkinv.report.national_rollup import AXIS_FAMILIES
        for r in _rows():
            self.assertEqual(r["family_id"], AXIS_FAMILIES.get(r["axis"], ""),
                             r["axis"])


if __name__ == "__main__":
    unittest.main()
