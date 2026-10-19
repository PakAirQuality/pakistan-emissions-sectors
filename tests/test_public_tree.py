"""This public repository tracks nothing it may not publish, and its list cannot quietly shrink.

WHY. From rc69 the work is committed here directly, and the third-party documents stay in the
private checkout as the restricted layers (src/pkinv/core/layers.py). A rule that decides what
is PUBLISHED fails in one direction only: a file that should have stayed out and did not
cannot be taken back once pushed. So the rule is tested on the tracked tree itself, on the
ignore rules that keep a mounted document from being committed by `git add -A`, and on the
ODbL notice that must list every file carrying share-alike obligations. Until rc68 this was
tests/test_public_copy.py, which tested the copier that made each public snapshot.
"""
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pkinv import release                                              # noqa: E402
from pkinv.core import layers                                          # noqa: E402
from _support import load_script                                       # noqa: E402

check = load_script("check_public_tree")


class TestWhatThisRepositoryTracks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tracked = check.tracked()

    def test_no_restricted_path_is_tracked(self):
        self.assertEqual(check.restricted_tracked(self.tracked), [])

    def test_no_tracked_file_exceeds_the_limit(self):
        self.assertEqual(check.too_large(self.tracked), [])

    def test_every_restricted_name_is_ignored(self):
        """Without a trailing slash: the mount is a symlink, which git calls a file."""
        self.assertEqual(check.not_ignored(), [])

    def test_the_odbl_notice_lists_the_tracked_odbl_files(self):
        with open(os.path.join(ROOT, check.NOTICE), encoding="utf-8") as handle:
            self.assertEqual(handle.read(), check.notice(check.odbl_paths(self.tracked)),
                             "run python3 scripts/check_public_tree.py --write")

    def test_the_projects_own_work_is_tracked(self):
        for path in ("README.md", "CHANGELOG.md", "src/pkinv/__init__.py",
                     "src/pkinv/core/layers.py", "outputs/national_all_sectors.csv",
                     "outputs/release_manifest.json", "data/catalog/document_retention.csv",
                     "data/catalog/raw_manifest.csv", "NOTICE-ODbL.md", "LICENSE-ODbL",
                     "data/shared/gis/manual/ghsl_built_1km/GHSL_SOURCES.json",
                     "docs/restricted_layers.md"):
            self.assertTrue(path in self.tracked, "%s is this project's own and is not tracked" % path)


class TestTheRestrictionRule(unittest.TestCase):
    """The rule itself, on paths a later layout could produce."""

    def test_documents_microdata_rasters_and_notes_are_restricted(self):
        for path in ("sources/OGRA/x.pdf", "data/raw/pbs/hies/x.zip", "data/cache/a/b.tar",
                     "data/sectors/residential/x/hies_records.sav", "campaign/notes.md",
                     "research_campaign/STATE.json", "CLAUDE.md", ".claude/settings.json",
                     "data/shared/gis/manual/ghsl_built_1km/tile_1.tif",
                     "data/sectors/agriculture/gis/manual/spam_rice.tif"):
            self.assertTrue(layers.is_restricted(path), path)

    def test_the_projects_own_files_beside_them_are_not(self):
        for path in ("data/shared/gis/manual/ghsl_built_1km/GHSL_SOURCES.json",
                     "data/rawish.csv", "data/sectors/agriculture/activity/x.csv",
                     "sources.md", "outputs/national_all_sectors.csv"):
            self.assertFalse(layers.is_restricted(path), path)

    def test_every_retained_document_is_restricted(self):
        """The retention ledger lists every held document; none may be publishable."""
        import csv
        with open(os.path.join(ROOT, "data", "catalog", "document_retention.csv"),
                  encoding="utf-8", newline="") as handle:
            held = [r["path"] for r in csv.DictReader(handle)]
        self.assertGreater(len(held), 5000, "the ledger has gone blind")
        self.assertEqual([p for p in held if not layers.is_restricted(p)], [])


class TestTheAddressesAReaderIsGiven(unittest.TestCase):
    def _text(self, *parts):
        with open(os.path.join(ROOT, *parts), encoding="utf-8") as handle:
            return handle.read()

    def test_the_repository_named_is_the_public_one(self):
        self.assertEqual(release.OWNER, "PakAirQuality")
        self.assertNotIn("RehanAhmad13/%s" % release.REPO, self._text("CITATION.cff"))

    def test_the_readme_names_the_explorer(self):
        readme = self._text("README.md")
        self.assertIn(release.EXPLORER_URL, readme)
        self.assertIn(release.INITIATIVE_URL, readme)

    def test_nothing_says_which_release_the_explorer_serves(self):
        """It is deployed separately. A sentence saying it serves this release goes false
        the day either one moves."""
        readme = self._text("README.md")
        sentence = readme[readme.index(release.EXPLORER_URL) - 200:
                          readme.index(release.EXPLORER_URL) + 400]
        self.assertIn("can serve an earlier release", sentence)
        self.assertNotRegex(sentence, r"serves (this|the current) release")

    def test_the_repository_explains_what_it_does_not_hold(self):
        note = self._text("docs", "restricted_layers.md")
        for needle in (release.EXPLORER_URL, "does not allow", "document_retention.csv",
                       "restricted layers absent:", "NOTICE-ODbL.md", "--group deposit"):
            self.assertIn(needle, note)
        self.assertIn("docs/restricted_layers.md", self._text("README.md"))


if __name__ == "__main__":
    unittest.main()
