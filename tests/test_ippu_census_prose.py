"""The IPPU manuscript's producer census count is the census file's (rc42, the twentieth
review's M-3).

Four manuscript sites and four data rows still said "fifteen producer filings" and "no exact
Fecto output" after Fecto's FY2025 annual report (FY2024 comparative: 651,048 t clinker) had
entered the census table. The count is read from the file wherever it is printed, and the
words "fifteen" / "15 producer" cannot return to the IPPU paper.
"""
import glob
import os
import re
import unittest

from _support import DATA, ROOT, data_rows
from pkinv.assets import asset_path

CENSUS = os.path.join("activity", "ippu", "company_clinker_2023_24.csv")
WORDS = {14: "fourteen", 15: "fifteen", 16: "sixteen", 17: "seventeen", 18: "eighteen"}


class TestTheCensusCount(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.rows = [r for r in data_rows(CENSUS, comments=False) if r["period_end_year"] == "2024"]
        cls.texts = {p: open(p, encoding="utf-8").read()
                     for p in glob.glob(os.path.join(ROOT, "papers", "ippu", "sections", "*.tex"))}

    def test_every_census_company_reports_exact_clinker(self):
        self.assertGreaterEqual(len(self.rows), 16)
        for r in self.rows:
            self.assertTrue(r["clinker_production_t"].strip(), r["company"])
            self.assertGreater(float(r["clinker_production_t"]), 0.0, r["company"])

    def test_the_manuscript_prints_the_files_count(self):
        n = len(self.rows)
        word = WORDS[n]
        for path, text in self.texts.items():
            for m in re.finditer(r"\b(fourteen|fifteen|sixteen|seventeen)\b", text, re.I):
                self.assertEqual(m.group(1).lower(), word,
                                 "%s prints %r producers; the census file has %d"
                                 % (os.path.basename(path), m.group(1), n))
            for m in re.finditer(r"\b(1[4-9]) producer filings", text):
                self.assertEqual(int(m.group(1)), n, os.path.basename(path))

    def test_no_site_says_fecto_lacks_an_exact_output(self):
        for path, text in self.texts.items():
            self.assertNotRegex(text, r"Fecto (lacks|remains in the census without)",
                                os.path.basename(path))
        for rel in ("activity/ippu/source_manifest.csv", "activity/ippu/master_data_gap_matrix.csv",
                    "data_gaps.csv"):
            # only the cement rows carry the census count; other rows may count other things
            lines = [line for line in open(asset_path(DATA, *rel.split("/")), encoding="utf-8")
                     if "2.A.1" in line or "clinker" in line.lower()]
            text = "".join(lines)
            self.assertNotIn("Fifteen", text, rel)
            self.assertNotIn("fifteen", text, rel)
            self.assertNotIn("Fourteen company", text, rel)
            self.assertNotIn("Resolve Fecto exact output", text, rel)


if __name__ == "__main__":
    unittest.main()
