"""The exposed historical scorecard must not manufacture scientific pass verdicts."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pkinv.core.io import read_rows
from pkinv.core.reporting_window import CORE_FY_STARTS, fiscal_label
from pkinv.report import pass2_scorecard as scorer
from pkinv.report import temporal_decomposition


class TestHistoricalScorecard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = {name: scorer._rows(name) for name in (
            "pakemis_completeness_mass.csv", "pakemis_temporal_decomposition.csv",
            "pakemis_spatial_decomposition.csv", "pakemis_ensemble_summary.csv")}
        cls.reference = temporal_decomposition.variable_unobserved(scorer.REFERENCE_PERIOD_ID)
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "scorecard.csv"
            with patch.object(scorer, "OUT", str(output)), patch.object(
                    temporal_decomposition, "variable_unobserved", return_value=cls.reference):
                scorer.main()
            cls.rows = {row["outcome_id"]: row for row in read_rows(output)}

    def test_exported_annual_target_comparison_agrees_with_candidate_source_range(self):
        source = next(r for r in self.inputs["pakemis_completeness_mass.csv"]
                      if r["row_type"] == "summary")
        quantified = source["mass_low_Mt"] != ""
        low, high = (tuple(map(float, (source["mass_low_Mt"], source["mass_high_Mt"])))
                     if quantified else (None, None))
        expected = ("RETIRED_TARGET_NO_QUANTIFIED_AGGREGATE" if not quantified else
                    "HISTORICAL_TARGET_WITHIN_REMAINING_RANGE"
                    if low <= scorer.HISTORICAL_ANNUAL_TARGET_MT <= high else
                    "HISTORICAL_TARGET_OUTSIDE_REMAINING_RANGE")
        row = self.rows["1-bound-annual-gaps"]
        self.assertEqual(row["verdict"], expected)
        if quantified:
            self.assertIn("%g-%g Mt" % (low, high), row["measured"])
        else:
            self.assertIn("unquantified", row["measured"])
        self.assertIn("not a statistical confidence interval", row["note"])

    def test_target_verdict_responds_to_source_range_instead_of_fixed_pass_literal(self):
        changed = copy.deepcopy(self.inputs)
        summary = next(r for r in changed["pakemis_completeness_mass.csv"]
                       if r["row_type"] == "summary")
        target = scorer.HISTORICAL_ANNUAL_TARGET_MT
        summary.update(mass_low_Mt=str(target - 1), mass_high_Mt=str(target + 1))
        with patch.object(scorer, "_rows", side_effect=lambda name: changed[name]), patch.object(
                temporal_decomposition, "variable_unobserved", return_value=self.reference):
            row = scorer.build()[0]
        self.assertEqual(row["verdict"], "HISTORICAL_TARGET_WITHIN_REMAINING_RANGE")

    def test_exported_temporal_metric_reconciles_and_uses_current_fiscal_window(self):
        inputs = self.inputs["pakemis_temporal_decomposition.csv"]
        total = sum(float(r["co2e_Mt_AR5"]) for r in inputs)
        missing = sum(float(r["unobserved_Mt_AR5"]) for r in inputs
                      if r["activity_should_vary_but_unobserved"] == "yes")
        percent = 100 * missing / total
        row = self.rows["2-monthly-variable-unobserved"]
        self.assertIn("%.2f%% (%.1f of %.1f Mt" % (percent, missing, total), row["measured"])
        self.assertIn("%d fiscal years" % len(CORE_FY_STARTS), row["measured"])
        self.assertIn(fiscal_label(CORE_FY_STARTS[-1]), row["measured"])
        expected = ("HISTORICAL_THRESHOLD_SATISFIED" if percent <=
                    scorer.TARGET_VARIABLE_UNOBSERVED_PCT else "HISTORICAL_THRESHOLD_EXCEEDED")
        self.assertEqual(row["verdict"], expected)

    def test_spatial_metric_is_source_mass_and_does_not_assert_facility_coverage(self):
        inputs = self.inputs["pakemis_spatial_decomposition.csv"]
        unresolved = sum(float(r["unresolved_Mt_AR5"]) for r in inputs)
        total = sum(float(r["co2e_Mt_AR5"]) for r in inputs)
        row = self.rows["3-facility-resolved-spatial"]
        self.assertIn("%.2f of %.2f Mt" % (unresolved, total), row["measured"])
        self.assertEqual(row["verdict"], "DIAGNOSTIC_UNRESOLVED_MASS")
        self.assertIn("not identical to an unallocated", row["note"])

    def test_profile_count_excludes_national_total_and_does_not_claim_universal_draws(self):
        categories = [r for r in self.inputs["pakemis_ensemble_summary.csv"]
                      if r["name"] != "NATIONAL_TOTAL"]
        count = sum(r["profile_uncertainty_status"].startswith("drawn") for r in categories)
        row = self.rows["4-common-draws-everywhere"]
        self.assertIn("%d of %d category" % (count, len(categories)), row["measured"])
        self.assertEqual(row["verdict"], "RETIRED_UNIVERSAL_DRAW_GATE")
        self.assertIn("Structural cases carry no assigned probability", row["note"])

    def test_no_current_row_inherits_obsolete_grade_or_acquisition_claim(self):
        self.assertEqual(self.rows["2b-historical-temporal-grade"]["verdict"],
                         "RETIRED_INTERNAL_GRADE")
        for row in self.rows.values():
            self.assertFalse(row["verdict"].startswith("MET"), row)
            for obsolete in ("nine-year", "drafted and unsent", "One acquisition",
                             "private seeds", "20k-draw"):
                self.assertNotIn(obsolete, " ".join(row.values()))

    def test_invalid_mass_accounts_fail_instead_of_printing_a_quality_verdict(self):
        with self.assertRaises(ValueError):
            scorer._variable_unobserved([{"co2e_Mt_AR5": "1", "unobserved_Mt_AR5": "2",
                                         "activity_should_vary_but_unobserved": "yes"}])


if __name__ == "__main__":
    unittest.main()
