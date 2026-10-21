"""Guards against overstating configuration agreement and incomplete counterfactuals."""
from pathlib import Path
from itertools import product
import unittest

from pkinv.core.io import table_text
from pkinv.paths import ROOT
from pkinv.report import contribution_evidence as ce


def air_rows():
    rows = []
    for cfg in ce.CONFIGS:
        for period, multiplier in (("start", 1), ("end", 2), ("reference", 1)):
            for sector, quantity in (("households", 3), ("other", 1)):
                rows.append(dict(period_id=period, configuration_id=cfg, sector_id=sector,
                                 category=sector, pollutant="PM2.5", emissions_Gg=str(quantity * multiplier),
                                 coverage_scope="covered_sources_only"))
    return rows


def gas_rows(boundary="territorial"):
    combinations = [(r, d, f) for r, d, f in product(("R1", "R2"), ("M1", "M2", "M3"), ("F1", "F2"))]
    combinations += [("none", "D4", f) for f in ("F1", "F2")]
    return [dict(role="evidence", boundary=boundary, pollutant="CO2e_AR5", displaced=d,
                 fertilizer_route=f, baseline_fertilizer="FA2", baseline_power=pa,
                 receiving=r, leak_base=lb, prill_control=pc, sign="-", coverage="complete",
                 reference_year=ce.GAS_REFERENCE_YEAR)
            for pa, lb, pc in product(("PA1", "PA2"), ("LB1", "LB2"), ("PC1", "PC2"))
            for r, d, f in combinations]


def gas_expected(boundary):
    return {tuple(r[k] for k in ce.GAS_DIMS) for r in gas_rows(boundary)
            if boundary != "territorial" or r["fertilizer_route"] == "F1"}


def classify_gas(rows, boundary):
    return ce.gas_cells(rows, boundary, "CO2e_AR5", gas_expected(boundary))


class DirectionAndScopeGuards(unittest.TestCase):
    def test_missing_configuration_cannot_pass_as_four_case_agreement(self):
        rows = [r for r in air_rows() if r["configuration_id"] != ce.CONFIGS[-1]]
        with self.assertRaisesRegex(ValueError, "missing or zero"):
            ce.air_statistics(rows, "PM2.5", "start", "end", "reference")

    def test_duplicate_source_cannot_inflate_a_sector(self):
        rows = air_rows()
        rows.append(rows[0].copy())
        with self.assertRaisesRegex(ValueError, "duplicate air"):
            ce.air_statistics(rows, "PM2.5", "start", "end", "reference")

    def test_dropped_endpoint_category_cannot_create_a_false_trend(self):
        rows = [r for r in air_rows() if not (r["period_id"] == "end" and r["sector_id"] == "households")]
        with self.assertRaisesRegex(ValueError, "category coverage differs"):
            ce.air_statistics(rows, "PM2.5", "start", "end", "reference")

    def test_different_configuration_categories_cannot_create_a_false_leader(self):
        rows = [r for r in air_rows() if not (r["configuration_id"] == ce.CONFIGS[-1]
                                             and r["sector_id"] == "households")]
        with self.assertRaisesRegex(ValueError, "category coverage differs"):
            ce.air_statistics(rows, "PM2.5", "start", "end", "reference")

    def test_leader_change_is_visible_even_when_all_trends_increase(self):
        rows = air_rows()
        for row in rows:
            if row["configuration_id"] == ce.CONFIGS[-1] and row["sector_id"] == "other":
                row["emissions_Gg"] = str(float(row["emissions_Gg"]) * 10)
        changes, leaders, _ = ce.air_statistics(rows, "PM2.5", "start", "end", "reference")
        self.assertEqual(ce.direction(changes.values()), "increase in every compared case")
        self.assertEqual(leaders[ce.CONFIGS[0]], ("households",))
        self.assertEqual(leaders[ce.CONFIGS[-1]], ("other",))

    def test_ties_are_not_broken_alphabetically_into_a_unique_leader(self):
        rows = air_rows()
        for row in rows:
            if row["sector_id"] == "other":
                row["emissions_Gg"] = str(float(row["emissions_Gg"]) * 3)
        _, leaders, _ = ce.air_statistics(rows, "PM2.5", "start", "end", "reference")
        self.assertTrue(all(names == ("households", "other") for names in leaders.values()))

    def test_zero_bound_does_not_count_as_strict_increase(self):
        self.assertEqual(ce.direction([0, 12]), "direction differs or includes zero")
        with self.assertRaises(ValueError):
            ce.direction([])

    def test_negative_partial_footprint_is_not_promoted_to_reduction(self):
        rows = gas_rows("combined_partial")
        rows[0]["coverage"] = "reversible"
        _, signs, reversible, _, result = classify_gas(rows, "combined_partial")
        self.assertEqual(signs["-"], 112)
        self.assertEqual(reversible, 1)
        self.assertEqual(result, "unresolved")

    def test_domestic_import_duplicates_are_removed_but_combined_routes_remain(self):
        rows = gas_rows()
        selected, *_ = classify_gas(rows, "territorial")
        self.assertEqual(len(selected), 56)
        for row in rows:
            row["boundary"] = "combined_partial"
        selected, *_ = classify_gas(rows, "combined_partial")
        self.assertEqual(len(selected), 112)

    def test_spanning_case_prevents_whole_scope_reduction(self):
        rows = gas_rows("combined_partial")
        rows[0]["sign"] = "~"
        *_, result = classify_gas(rows, "combined_partial")
        self.assertEqual(result, "unresolved")

    def test_unrecognized_coverage_is_not_silently_complete(self):
        rows = gas_rows()
        rows[0]["coverage"] = "unknown"
        with self.assertRaisesRegex(ValueError, "coverage"):
            classify_gas(rows, "territorial")

    def test_diagnostic_fertilizer_cannot_be_admitted_by_role_label(self):
        rows = gas_rows()
        rows[0]["baseline_fertilizer"] = "FA1"
        with self.assertRaisesRegex(ValueError, "admitted FA2"):
            classify_gas(rows, "territorial")

    def test_wrong_year_cannot_be_admitted_by_role_label(self):
        rows = gas_rows()
        rows[0]["reference_year"] = "FY2024-25"
        with self.assertRaisesRegex(ValueError, "reference year"):
            classify_gas(rows, "territorial")

    def test_matching_truncated_products_cannot_imply_complete_case_agreement(self):
        rows = gas_rows()
        del rows[0]
        with self.assertRaisesRegex(ValueError, "complete admitted case set"):
            classify_gas(rows, "territorial")

    def test_relabelled_diagnostic_case_cannot_silently_narrow_scope(self):
        rows = gas_rows()
        rows[0]["role"] = "diagnostic"
        with self.assertRaisesRegex(ValueError, "complete admitted case set"):
            classify_gas(rows, "territorial")

    def test_missing_dependence_case_is_not_silently_dropped(self):
        with self.assertRaisesRegex(ValueError, "exactly once"):
            ce.ghg_endpoint([], "first", "last")


class ShippedSynthesis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.claims, cls.summary = ce.build()

    def test_expected_cases_are_derived_from_the_public_registers(self):
        registers = [ce.read_rows(ce._path(ROOT, name)) for name in ce.GAS_REGISTERS]
        for boundary in ("territorial", "combined_partial"):
            self.assertEqual(ce.expected_gas_cases(*registers, boundary), gas_expected(boundary))

    def test_changed_admission_register_requires_scope_review(self):
        registers = [ce.read_rows(ce._path(ROOT, name)) for name in ce.GAS_REGISTERS]
        next(r for r in registers[0] if r["baseline_id"] == "FA1")["classification"] = "admissible"
        with self.assertRaisesRegex(ValueError, "admission register"):
            ce.expected_gas_cases(*registers, "territorial")

    def test_every_claim_carries_its_limits_and_snapshot(self):
        for row in self.claims:
            for field in ("scope", "admission_limit", "shared_assumptions", "missing_components",
                          "permitted_interpretation", "source_sha256", "required_next_evidence"):
                self.assertTrue(row[field], (row["claim_id"], field))
            self.assertNotIn("probability", row["unit"])

    def test_products_regenerate_byte_identically(self):
        for name, fields, rows in ((ce.CLAIMS_OUT, ce.FIELDS, self.claims),
                                   (ce.SUMMARY_OUT, ce.SUMMARY_FIELDS, self.summary)):
            actual = (Path(ROOT) / "outputs" / name).read_bytes()
            self.assertEqual(actual, table_text(fields, rows, banner=ce.BANNER).encode("utf-8"))


if __name__ == "__main__":
    unittest.main()
