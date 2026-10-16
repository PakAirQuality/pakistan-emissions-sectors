"""The reporting-window guard refuses a FY2025-26 national total and names the exact period."""
import unittest

from pkinv.core import reporting_window as window


class Guard(unittest.TestCase):
    def test_partial_candidate_year_cannot_become_a_national_total(self):
        with self.assertRaises(ValueError) as caught:
            window.require_common_core("FY2025-26")
        self.assertIn("July 2015-June 2025, ten fiscal years", str(caught.exception))
        for period in window.CORE_PERIOD_IDS:
            self.assertEqual(period, window.require_common_core(period))
        self.assertEqual(10, len(window.CORE_PERIOD_IDS))
        self.assertNotIn("calendar", window.CORE_PERIOD_TEXT.lower())


if __name__ == "__main__":
    unittest.main()
