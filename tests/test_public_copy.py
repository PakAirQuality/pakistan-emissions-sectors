"""The public copy leaves out other people's documents, and its list cannot quietly shrink.

WHY. The working repository is private because it holds 6,000 third-party documents, among
them household survey microdata that may not be redistributed. The public repository is a copy
of each release without them (scripts/make_public_copy.py). A rule that decides what is
PUBLISHED fails in one direction only: a file that should have stayed out and did not cannot
be taken back. So the rule is tested on the tracked tree itself, and on the two things a
layout change would break - a document folder that moved, and the public address the
manuscripts print.
"""
import csv
import importlib.util
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv import release                                              # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "make_public_copy", os.path.join(ROOT, "scripts", "make_public_copy.py"))
public = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(public)


class TestWhatThePublicCopyLeavesOut(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.keep, cls.drop = public.partition()

    def test_no_primary_document_ships(self):
        for prefix in ("sources/", "data/raw/", "data/cache/"):
            shipped = [p for p in self.keep if p.startswith(prefix)]
            self.assertFalse(shipped, "%s would be published: %s" % (prefix, shipped[:5]))
        self.assertGreater(sum(1 for p in self.drop if p.startswith("data/raw/")), 1000,
                           "the rule found almost no documents to leave out - it has gone "
                           "blind to the tree it is meant to guard")

    def test_no_record_level_survey_file_ships(self):
        shipped = [p for p in self.keep if p.lower().endswith(public.FORBIDDEN_SUFFIXES)]
        self.assertFalse(shipped)
        self.assertEqual(public.left_out("data/sectors/residential/x/hies_records.sav"),
                         "record-level survey file",
                         "a microdata file under a new path would ship")

    def test_every_retained_document_is_left_out(self):
        """The retention ledger lists every held document. None of them may ship, whatever
        folder a later layout gives it."""
        with open(os.path.join(ROOT, "data", "catalog", "document_retention.csv"),
                  encoding="utf-8", newline="") as handle:
            held = {r["path"] for r in csv.DictReader(handle)}
        shipped = sorted(held & set(self.keep))
        self.assertFalse(shipped, "held third-party documents would be published: %s"
                         % shipped[:8])

    def test_the_named_rasters_exist_and_are_left_out(self):
        """A raster renamed or moved would drop off a list of names and ship."""
        tracked = set(self.keep) | set(self.drop)
        for path in public.LEFT_OUT_FILES:
            self.assertIn(path, tracked, "%s is named and no longer tracked - find where it "
                          "went before the next public copy" % path)
        tiles = [p for p in tracked if p.startswith("data/shared/gis/manual/ghsl_built_1km/")
                 and p.endswith(".tif")]
        self.assertTrue(tiles)
        self.assertFalse(set(tiles) & set(self.keep))
        shipped_rasters = [p for p in self.keep if p.startswith("data/")
                           and p.endswith(".tif")]
        self.assertFalse(shipped_rasters, "a raster under data/ would ship without having "
                         "been judged: %s" % shipped_rasters[:5])

    def test_the_projects_own_work_ships(self):
        for path in ("README.md", "CHANGELOG.md", "src/pkinv/__init__.py",
                     "outputs/national_all_sectors.csv", "outputs/release_manifest.json",
                     "data/catalog/document_retention.csv", "data/catalog/raw_manifest.csv",
                     "data/shared/gis/manual/ghsl_built_1km/GHSL_SOURCES.json",
                     "paper_national/versions/v3/paper.tex"):
            self.assertIn(path, self.keep, "%s is this project's own and would not ship" % path)


class TestTheAddressesAReaderIsGiven(unittest.TestCase):
    def _text(self, *parts):
        with open(os.path.join(ROOT, *parts), encoding="utf-8") as handle:
            return handle.read()

    def test_the_repository_named_is_the_public_one(self):
        self.assertEqual(release.OWNER, "PakAirQuality")
        self.assertNotIn("RehanAhmad13/%s" % release.REPO, self._text("CITATION.cff"))

    def test_the_article_and_the_readme_name_the_explorer(self):
        article = self._text("paper_national", "versions", "v3", "paper.tex")
        self.assertIn("\\url{%s}" % release.EXPLORER_URL, article)
        self.assertIn("\\url{%s}" % release.INITIATIVE_URL, article)
        self.assertIn(release.EXPLORER_URL, self._text("README.md"))

    def test_nothing_says_which_release_the_explorer_serves(self):
        """It is deployed separately. A sentence saying it serves this release goes false
        the day either one moves."""
        article = self._text("paper_national", "versions", "v3", "paper.tex")
        sentence = article[article.index(release.EXPLORER_URL) - 200:
                           article.index(release.EXPLORER_URL) + 400]
        self.assertIn("version of record", sentence)
        self.assertNotRegex(sentence, r"serves (this|the current) release")

    def test_the_copy_explains_itself(self):
        note = public.note("0" * 40, 1, 1, 1)
        for needle in (release.EXPLORER_URL, "PBS forbids redistribution",
                       "document_retention.csv", "do not exist here"):
            self.assertIn(needle, note)


if __name__ == "__main__":
    unittest.main()
