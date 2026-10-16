"""Check the maintained integrated ESSD article and its review wrapper."""
from pathlib import Path
import re
import unittest

from pkinv.paths import PAPER_NATIONAL_MAIN, ROOT

NATIONAL = Path(PAPER_NATIONAL_MAIN)
PAPER = NATIONAL / "paper.tex"
SUBMISSION = NATIONAL / "submission.tex"
SUMMARY = NATIONAL / "short_summary.txt"
VENDORED = Path(ROOT) / "paper_common" / "copernicus"
VENDORED_FILES = ("copernicus.cls", "copernicus.cfg", "copernicus.bst",
                  "pdfscreen.sty", "pdfscreencop.sty", "template_reference.txt",
                  "README_copernicus_package_7_15.txt", "VENDORED.md")
VENDORED_ZIP_SHA256 = "f31563e860a42c6bb980de4f29c670881eccca42b31f084fc11b7f0070040767"
BANNED = ("official national inventory", "definitive", "complete inventory",
          "observed gridded emissions", "true national emissions", "live emissions system",
          "AI-derived")


def uncommented(text):
    return "\n".join(re.sub(r"(?<!\\)%.*", "", line) for line in text.splitlines())


class TestCurrentArticle(unittest.TestCase):
    def test_essd_class_and_review_wrapper(self):
        source = uncommented(PAPER.read_text())
        wrapper = uncommented(SUBMISSION.read_text())
        self.assertIn(r"\documentclass[essd]{copernicus}", source)
        self.assertIn(r"\documentclass[essd,manuscript]{copernicus}", source)
        self.assertIn(r"\input{paper.tex}", wrapper)
        self.assertIn(r"\def\reviewversion{1}", wrapper)

    def test_title_and_period_are_current(self):
        source = uncommented(PAPER.read_text())
        self.assertRegex(source, r"\\title\{PakEmis \\PakEmisRelease: greenhouse gas and air pollutant emissions in Pakistan, July 2015--June 2025\}")
        self.assertIn("ten fiscal years from July 2015 to June 2025", source)
        self.assertIn("provisional extension", source)

    def test_data_and_code_availability_are_honest(self):
        source = uncommented(PAPER.read_text())
        self.assertIn(r"\dataavailability{", source)
        self.assertIn(r"\codeavailability{", source)
        self.assertIn("persistent dataset identifier", source)
        self.assertIn("pending", source)

    def test_prose_avoids_unwarranted_claims(self):
        source = uncommented(PAPER.read_text()).lower()
        hits = [phrase for phrase in BANNED if phrase.lower() in source]
        self.assertEqual(hits, [])
        self.assertIn("spatial allocation", source)
        self.assertIn("conditional parameter uncertainty", source)

    def test_short_summary_exists_and_is_readable(self):
        summary = SUMMARY.read_text().strip()
        self.assertTrue(summary)
        self.assertLessEqual(len(summary), 500)
        self.assertIn("Pakistan", summary)
        self.assertIn("air pollutants", summary)


class TestTheClassIsVendored(unittest.TestCase):
    def test_the_vendored_files_exist(self):
        missing = [name for name in VENDORED_FILES if not (VENDORED / name).exists()]
        self.assertFalse(missing)

    def test_the_vendoring_note_records_the_archive_digest(self):
        note = (VENDORED / "VENDORED.md").read_text()
        self.assertIn(VENDORED_ZIP_SHA256, note)
        self.assertIn("7.15", note)
        self.assertIn("publications.copernicus.org", note)


if __name__ == "__main__":
    unittest.main()
