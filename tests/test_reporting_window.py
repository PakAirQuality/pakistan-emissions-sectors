"""The extension must not silently move reference products or admit partial years."""
import unittest

from pkinv.core import reporting_window as window
from pkinv.report import periods


class ReportingWindow(unittest.TestCase):
    def test_ten_complete_fiscal_years_and_separate_reference(self):
        rows = periods.rows()
        self.assertEqual(10, len(rows))
        self.assertEqual("2015-07-01", rows[0]["period_start"])
        self.assertEqual("2025-06-30", rows[-1]["period_end"])
        self.assertEqual(["FY2023-24"], [r["period_id"] for r in rows if r["is_reference"]])
        self.assertEqual(366, next(r["days"] for r in rows if r["period_id"] == "FY2023-24"))

    def test_candidate_is_not_implicitly_a_common_scope_total(self):
        self.assertTrue(window.is_common_core("FY2024-25"))
        self.assertFalse(window.is_common_core("FY2025-26"))


if __name__ == "__main__":
    unittest.main()
