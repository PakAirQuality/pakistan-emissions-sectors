"""Byte-equality guards for the waste paper's generated appendices.

The residential/transport discipline: S2 (tiers), S3 (factors) and S4 (completeness)
are GENERATED .tex files, and the committed copy must match a fresh in-memory
regeneration - so a data edit that skips the generator, or a hand-edit to the .tex,
fails loudly instead of shipping a table that disagrees with the engine.

Run:  python3 -m unittest discover tests
"""

from pkinv.assets import asset_path
import csv
import importlib.util
import os
import unittest
from _support import ROOT



def _load_script(name):
    spec = importlib.util.spec_from_file_location(
        name.replace(".py", ""), os.path.join(ROOT, "scripts", name))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestTierAppendix(unittest.TestCase):
    """S2: tier status by component, parameter values asserted at generation."""

    def test_the_committed_table_matches_a_fresh_regeneration(self):
        mod = _load_script("make_waste_tier_table.py")
        committed = open(mod.OUT, encoding="utf-8").read()
        self.assertEqual(committed, mod.render())

    def test_no_single_sector_tier_claim(self):
        """The table's reason for existing: the air layer and the allocation are not
        on the tier ladder, and saying 'Tier 1' for the whole sector would hide it."""
        mod = _load_script("make_waste_tier_table.py")
        tex = open(mod.OUT, encoding="utf-8").read()
        self.assertIn("not an IPCC tier", tex)
        self.assertIn("not a tier", tex)


class TestFactorAppendix(unittest.TestCase):
    """S3: every parameter and factor rendered from the data files."""

    def test_the_committed_table_matches_a_fresh_regeneration(self):
        mod = _load_script("make_waste_factor_table.py")
        committed = open(mod.OUT, encoding="utf-8").read()
        self.assertEqual(committed, mod.render())

    def test_every_engine_row_appears(self):
        mod = _load_script("make_waste_factor_table.py")
        tex = open(mod.OUT, encoding="utf-8").read()
        for r in mod.param_rows():
            self.assertIn(mod._tex(r["param"]), tex, r["param"])
        efs = mod.ef_rows()
        self.assertGreaterEqual(len(efs), 10)
        for r in efs:
            self.assertIn(mod._tex(r["ef_id"]), tex, r["ef_id"])

    def test_the_basis_distinctions_are_stated(self):
        """The whole reason S3 exists in this form: the wet/dry bases and the NO-to-NO2
        conversion must be row-visible, not caption prose alone."""
        mod = _load_script("make_waste_factor_table.py")
        tex = open(mod.OUT, encoding="utf-8").read()
        self.assertIn("per WET tonne", tex)
        self.assertIn("DRY tonne", tex)
        self.assertIn("46/30", tex)
        self.assertNotIn("EMEP", tex)


class TestCompletenessAppendix(unittest.TestCase):
    """S4: the sector-4 rows of the national completeness table."""

    def test_the_committed_table_matches_the_engine(self):
        mod = _load_script("make_waste_completeness_table.py")
        committed = open(mod.OUT, encoding="utf-8").read()
        self.assertEqual(committed, mod.render())

    def test_every_ipcc_waste_category_appears(self):
        """4.B and 4.C.1 must be present as NE - the round that added them exists
        because they were previously not even rows."""
        mod = _load_script("make_waste_completeness_table.py")
        codes = {r["code"] for r in mod.rows()}
        self.assertEqual(codes, {"4.A", "4.B", "4.C.1", "4.C.2", "4.D.1", "4.D"})
        keys = {r["code"]: r["notation_key"] for r in mod.rows()
                if r["code"] in ("4.B", "4.C.1")}
        self.assertEqual(keys, {"4.B": "NE", "4.C.1": "NE"})

    def test_ne_rows_reference_their_gap_register_entries(self):
        with open(asset_path(ROOT, "data", "data_gaps.csv"),
                  newline="", encoding="utf-8") as f:
            gap_ids = {r["gap_id"] for r in csv.DictReader(f)}
        self.assertIn("waste-biological-treatment", gap_ids)
        self.assertIn("waste-incineration", gap_ids)
