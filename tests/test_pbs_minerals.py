"""Source-to-final-export regression controls for the repaired PBS minerals panel."""
import collections
import importlib.util
import os
import subprocess
import unittest
import openpyxl
from pkinv.assets import asset_path
from pkinv.core.io import read_rows
from pkinv.core import pbs_minerals as pm
from _support import ROOT

PANEL = asset_path(ROOT, "data/activity/monthly/pbs_minerals_month_province.csv")
RAW = asset_path(ROOT, "data/raw/pbs/minerals")

def ingest():
    spec = importlib.util.spec_from_file_location("minerals_ingest", os.path.join(ROOT, "scripts/ingest_pbs_minerals.py"))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module

class SourceToExport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = read_rows(PANEL)
        cls.module = ingest()
        cls.book = openpyxl.load_workbook(asset_path(RAW, "pbs_minerals_2020_21.xlsx"), data_only=True, read_only=True)

    @classmethod
    def tearDownClass(cls):
        cls.book.close()

    def members(self, mineral, year):
        return [r for r in self.rows if r["canonical_mineral"] == mineral and int(r["fiscal_year_start"]) == year]

    def test_final_export_unique_keys_and_source_controls(self):
        self.module.validate_export(self.rows)
        keys = [(r["fiscal_year_start"], r["canonical_mineral"], r["province"], r["month"]) for r in self.rows]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(36, len({(r["fiscal_year_start"], r["canonical_mineral"]) for r in self.rows}))

    def test_printed_year_blocks_against_independent_excel_total_cells(self):
        # Excel row identities are the public source controls, not implementation totals.
        controls = {2015: {"crude_oil": 2354, "natural_gas": 2355, "coal": 2232, "limestone": 2286},
                    2020: {"crude_oil": 3226, "natural_gas": 3231, "coal": 3116, "limestone": 3164},
                    2021: {"crude_oil": 3418, "natural_gas": 3423, "coal": 3308, "limestone": 3356},
                    2022: {"crude_oil": 3607, "natural_gas": 3612, "coal": 3496, "limestone": 3545}}
        sheet = self.book["mineral production"]
        for year, minerals in controls.items():
            for mineral, number in minerals.items():
                source = next(sheet.iter_rows(min_row=number, max_row=number, values_only=True))
                self.assertEqual("Total", source[1])
                for index, month in enumerate(self.module.months_for(year)):
                    observed = sum(float(r["quantity"]) for r in self.members(mineral, year) if r["month"] == month)
                    self.assertAlmostEqual(float(source[index + 2]), observed, delta=1.0,
                                           msg="%s/%s differs from independent source cell" % (mineral, month))
                self.assertAlmostEqual(float(source[14]), sum(float(r["quantity"]) for r in self.members(mineral, year)), delta=1.0)

    def test_fy2023_pdf_preceding_provinces_survive_final_export(self):
        # Independent extraction of the printed national rows, without the parser.
        text = subprocess.check_output(["pdftotext", "-layout", asset_path(RAW, "pbs_minerals_2023_24.pdf"), "-"]).decode()
        national_rows = {"coal": 47, "limestone": 101, "crude_oil": 174, "natural_gas": 179}
        for mineral, line_number in national_rows.items():
            tokens = text.splitlines()[line_number - 1].split()
            self.assertEqual("Total", tokens[0])
            monthly = [float(v.replace(",", "")) for v in tokens[1:13]]
            members = self.members(mineral, 2023)
            self.assertEqual({"Punjab", "Sindh", "KPK", "Balochistan"}, {r["province"] for r in members})
            for month, expected in zip(self.module.months_for(2023), monthly):
                self.assertEqual(expected, sum(float(r["quantity"]) for r in members if r["month"] == month))

    def test_native_units_and_missing_not_zero(self):
        self.assertEqual({"US_barrel"}, {r["quantity_unit"] for r in self.members("crude_oil", 2020)})
        self.assertEqual({"MMCFt"}, {r["quantity_unit"] for r in self.members("natural_gas", 2020)})
        self.assertIsNone(self.module._number(None)); self.assertIsNone(self.module._number("NR"))
        self.assertIsNone(self.module._number("-")); self.assertIsNone(self.module._number("########"))
        self.assertEqual(0, self.module._number("0"))

    def test_equal_legitimate_province_observations_are_retained(self):
        values = [100.0] * 12
        group = (2020, "MINERALS PRODUCTION DATA 2020-21", "test", "Crude Oil", [
            {"province": p, "values": values, "annual": 1200, "source_row": n}
            for n, p in enumerate(("Punjab", "Sindh", "KPK", "Balochistan"), 1)],
            {"province": "Total", "values": [400.0] * 12, "annual": 4800, "source_row": 5})
        rows, bad, control = self.module._assemble("fixture.xlsx", group)
        self.assertEqual(48, len(rows)); self.assertFalse(bad); self.assertEqual("yes", control["closed"])
        self.module.validate_export(rows)

    def test_source_quality_fallback_retires_78_percent_profile(self):
        for mineral in ("natural_gas", "crude_oil"):
            members = self.members(mineral, 2021)
            self.assertEqual({"Punjab", "Sindh", "KPK", "Balochistan"}, {r["province"] for r in members})
            self.assertEqual({"no"}, {r["timing_usable"] for r in members})
            shares, methods, covered = pm.profile_or_flat(mineral, 2021, self.rows)
            self.assertFalse(covered); self.assertEqual({"T4"}, set(methods.values()))
            self.assertLess(max(shares.values()), .09)

    def test_twelve_month_subset_cannot_be_admitted_as_national(self):
        members = [dict(r) for r in self.members("natural_gas", 2023) if r["province"] == "Balochistan"]
        self.assertEqual(12, len(members)); self.assertFalse(pm.covers("natural_gas", 2023, members))
        with self.assertRaises(ValueError): self.module.validate_export(members)

    def test_export_corruption_and_duplicates_fail(self):
        members = [dict(r) for r in self.members("natural_gas", 2023)]
        members[0]["quantity"] = str(float(members[0]["quantity"]) + 100)
        with self.assertRaises(ValueError): self.module.validate_export(members)
        self.assertFalse(pm.covers("natural_gas", 2023, members))
        with self.assertRaises(ValueError): self.module.validate_export(members + [members[0]])

    def test_held_fy2015_is_recovered_and_future_year_is_fallback(self):
        for mineral in ("natural_gas", "crude_oil"):
            self.assertTrue(pm.covers(mineral, 2015, self.rows))
            shares, method, covered = pm.profile_or_flat(mineral, 2024, self.rows)
            self.assertFalse(covered); self.assertEqual({"T4"}, set(method.values()))
            self.assertAlmostEqual(1, sum(shares.values()))

    def test_regeneration_matches_export(self):
        result = subprocess.run(["python3", "scripts/ingest_pbs_minerals.py", "--check"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

if __name__ == "__main__":
    unittest.main()
