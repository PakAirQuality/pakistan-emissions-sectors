"""Current-engine closure and scope guards for a conditional method comparison.

These tests establish arithmetic and provenance contracts, not an expected
percentage of agreement. A changed scientific result must not fail because it
contradicts the previous manuscript's preferred interpretation.
"""
import copy
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.core import gwp  # noqa: E402
from pkinv.core.io import read_rows, table_text  # noqa: E402
from pkinv.sectors.agriculture import faostat_nitrogen_flows as nf  # noqa: E402
from pkinv.sectors.agriculture import run_inventory, soils  # noqa: E402
from pkinv.sectors.agriculture.ef_library import InventoryData  # noqa: E402


class TestConditionalDirectFactors(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data, cls.npools, cls.cases = nf.engine_cases()

    def test_current_case_equals_full_inventory_engine(self):
        expected = run_inventory.soils_total(run_inventory.build_components(self.data))
        self.assertAlmostEqual(sum(self.cases["current"].values()), expected, places=12)

    def test_substitutions_match_nitrogen_inputs_without_double_counting(self):
        d, n = self.data, self.npools
        conversion = soils.N2O_N_TO_N2O * gwp.GWP["AR5"]["N2O"] / 1e9
        ef1_n = (d.fertilizer["nitrogen_N_offtake"]["value_t"] * 1000
                 * (1 - d.p("rice_N_fraction")) + n["FON_N"] + soils.residue_N(d))
        expected_ef1 = ef1_n * (d.efv("soils", "EF1_agg")
                                - d.efv("soils", "EF1_dry")) * conversion
        expected_prp = sum(n[pool] * (d.efv("soils", factor + "_agg")
                                     - d.efv("soils", factor))
                           for pool, factor in (("FPRP_cattle_N", "EF3PRP_cattle"),
                                                ("FPRP_other_N", "EF3PRP_sheepgoat"))) * conversion
        totals = {k: sum(v.values()) for k, v in self.cases.items()}
        self.assertAlmostEqual(totals["ef1"] - totals["current"], expected_ef1, places=11)
        self.assertAlmostEqual(totals["ef3prp"] - totals["current"], expected_prp, places=11)
        self.assertAlmostEqual(totals["both"] - totals["current"],
                               expected_ef1 + expected_prp, places=11)

    def test_rice_and_all_indirect_terms_are_unchanged(self):
        unaffected = [k for k in self.cases["current"] if "Indirect" in k or "rice EF1FR" in k]
        self.assertEqual(len(unaffected), 10)
        for case in ("ef1", "ef3prp", "both"):
            for name in unaffected:
                self.assertEqual(self.cases[case][name], self.cases["current"][name])
        changed_ef1 = {k for k, v in self.cases["ef1"].items() if v != self.cases["current"][k]}
        changed_prp = {k for k, v in self.cases["ef3prp"].items() if v != self.cases["current"][k]}
        self.assertFalse(changed_ef1 & changed_prp)
        self.assertEqual(len(changed_ef1), 3)
        self.assertEqual(len(changed_prp), 2)

    def test_current_and_target_factors_are_read_live_without_mutating_input(self):
        d = copy.deepcopy(self.data)
        d.ef[("soils", "EF1_dry")]["value"] = 0.007
        d.ef[("soils", "EF1_agg")]["value"] = 0.012
        d.ef[("soils", "EF3PRP_cattle")]["value"] = 0.004
        d.ef[("soils", "EF3PRP_cattle_agg")]["value"] = 0.017
        before = copy.deepcopy(d.__dict__)
        _, _, cases = nf.engine_cases(d)
        upland = "Direct N2O - synthetic fertiliser (upland)"
        pasture = "Direct N2O - pasture deposition (cattle-type)"
        self.assertAlmostEqual(cases["ef1"][upland] / cases["current"][upland], 0.012 / 0.007)
        self.assertAlmostEqual(cases["ef3prp"][pasture] / cases["current"][pasture], 0.017 / 0.004)
        self.assertEqual(d.__dict__, before)

    def test_current_activity_is_read_live(self):
        d = copy.deepcopy(self.data)
        d.fertilizer["nitrogen_N_offtake"]["value_t"] *= 1.1
        _, _, cases = nf.engine_cases(d)
        for case in cases:
            for label, value in cases[case].items():
                expected = self.cases[case][label] * (1.1 if "synthetic" in label else 1)
                self.assertAlmostEqual(value, expected, places=11)


class TestComparatorInputs(unittest.TestCase):
    def setUp(self):
        self.rows = read_rows(nf.SNAPSHOT)

    def test_snapshot_sum_and_declared_rounding(self):
        self.assertAlmostEqual(sum(nf.comparator_pools(self.rows).values()), 58.4997, places=8)
        self.assertEqual({r["source_kind"] for r in self.rows}, {"published_comparison_transcription"})
        self.assertEqual({r["source_commit"] for r in self.rows},
                         {"41b56365df9195d6a028a66630d0395b0d7c5de1"})

    def test_duplicate_and_missing_items_are_rejected(self):
        for rows in (self.rows + [self.rows[0]], self.rows[:-1]):
            with self.assertRaises(ValueError):
                nf.comparator_pools(rows)

    def test_mismatched_metric_scope_and_nonfinite_values_are_rejected(self):
        for field, value in (("area", "India"), ("year", "2024"), ("unit", "kt CO2e AR5"),
                             ("element_code", "723114"), ("value_decimal_places", "6"),
                             ("value", "nan"), ("value", "-1")):
            rows = copy.deepcopy(self.rows)
            rows[0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                nf.comparator_pools(rows)

    def test_ambiguous_or_absent_activity_year_is_rejected(self):
        for rows in ([], [{"year": "2023"}, {"year": "2023"}]):
            with self.assertRaises(ValueError):
                nf._year_row(rows, "2023", "fertiliser")

    def test_unknown_soil_component_cannot_disappear_from_comparison(self):
        with self.assertRaises(ValueError):
            nf._pool("Direct N2O - newly introduced source")


class TestPublishedComparison(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = nf.build()
        cls.by = {r["flow"]: r for r in cls.rows}

    def test_pool_and_scenario_totals_close_at_published_precision(self):
        pools = [r for r in self.rows if r["row_kind"] == "pool"]
        current = self.by[nf.CASE_FLOWS["current"]]
        self.assertAlmostEqual(sum(float(r["pakemis"]) for r in pools),
                               float(current["pakemis"]), delta=2e-6)
        self.assertAlmostEqual(sum(float(r["faostat"]) for r in pools),
                               float(current["faostat"]), delta=2e-6)
        both = float(self.by[nf.CASE_FLOWS["both"]]["pakemis"])
        residual = float(self.by["unresolved residual after direct-factor substitutions"]["pakemis"])
        self.assertAlmostEqual(both + residual, float(current["faostat"]), delta=1e-6)
        for row in self.rows:
            if row["row_kind"] == "pool":
                legs = [float(r["pakemis"]) for r in self.rows if r["row_kind"] == "pool_leg"
                        and r["flow"].startswith(row["flow"] + " (")]
                self.assertAlmostEqual(sum(legs), float(row["pakemis"]), delta=1.1e-6)

    def test_stock_comparison_is_not_labelled_nitrogen_agreement(self):
        stocks = [r for r in self.rows if r["unit"] == "head"]
        self.assertEqual(len(stocks), 6)
        self.assertEqual({r["row_kind"] for r in stocks}, {"stock_diagnostic"})
        self.assertNotIn("livestock head: all six species", self.by)
        self.assertIn("economic_survey_projection", self.by["livestock head: poultry"]["basis"])
        for row in stocks:
            self.assertIn("not the CY2023 emissions input", row["basis"])
        for row in self.rows:
            if row["row_kind"] == "nitrogen_pool":
                self.assertEqual(row["faostat"], "")

    def test_public_build_matches_shipped_bytes_without_private_archive(self):
        expected = table_text(nf.FIELDS, self.rows, banner=nf.BANNER.splitlines())
        with open(nf.OUT, encoding="utf-8", newline="") as handle:
            self.assertEqual(handle.read(), expected)


if __name__ == "__main__":
    unittest.main()
