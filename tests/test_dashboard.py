"""Tests for Phase 7 dashboard generation.

Run:  python3 -m unittest discover tests
"""
import os
import sys
import unittest


from pkinv.report import dashboard  # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "..", "outputs")


class TestDashboard(unittest.TestCase):
    def test_builds_and_has_sections(self):
        dashboard.build()
        path = os.path.join(OUT, "dashboard.html")
        self.assertTrue(os.path.exists(path))
        html = open(path, encoding="utf-8").read()
        # valid-ish HTML envelope
        self.assertTrue(html.startswith("<!doctype html>"))
        self.assertIn("</html>", html)
        # core sections present
        for token in ["Pakistan Agricultural GHG", "Emissions by category",
                      "Validation", "By province", "Trend", "CRT-style"]:
            self.assertIn(token, html, token)

    def test_headline_number_present(self):
        # the national TOTAL from outputs feeds the headline; should be in the 200s Mt
        dashboard.build()
        html = open(os.path.join(OUT, "dashboard.html"), encoding="utf-8").read()
        self.assertRegex(html, r"2[0-2][0-9](\.[0-9]+)?\s*<span>Mt CO")

    def test_missing_file_guard(self):
        # _csv on a non-existent file returns None and _table renders a placeholder
        self.assertIsNone(dashboard._csv("does_not_exist.csv"))
        self.assertIn("not generated", dashboard._table(None))


if __name__ == "__main__":
    unittest.main()
