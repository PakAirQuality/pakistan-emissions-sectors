"""Monthly production consumes the published temporal contract exactly once."""
import csv
import os
import tempfile
import unittest
from unittest.mock import patch

from pkinv.report import monthly_all_years, temporal_profiles


class MaterializedProfiles(unittest.TestCase):
    def test_reads_exact_published_weights_without_running_engines(self):
        rows = [{"component_id": "power.coal", "fiscal_year": "FY2023-24",
                 "month": "202307", "weight": "0.083333333333"}]
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "profiles.csv")
            with open(path, "w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            with patch.object(temporal_profiles, "OUT", path), patch.object(
                    temporal_profiles, "build", side_effect=AssertionError("engine rerun")):
                result = monthly_all_years._profiles()
        self.assertEqual(result[("power.coal", "FY2023-24")]["202307"], rows[0])

    def test_duplicate_month_is_rejected_instead_of_overwritten(self):
        row = {"component_id": "power.coal", "fiscal_year": "FY2023-24",
               "month": "202307", "weight": "0.1"}
        with patch.object(monthly_all_years, "read_rows", return_value=[row, row]):
            with self.assertRaisesRegex(ValueError, "duplicate temporal profile"):
                monthly_all_years._profiles()

    def test_missing_registry_does_not_silently_recompute(self):
        with patch.object(temporal_profiles, "OUT", "/missing/profiles.csv"), patch.object(
                temporal_profiles, "build", side_effect=AssertionError("engine rerun")):
            with self.assertRaises(FileNotFoundError):
                monthly_all_years._profiles()
