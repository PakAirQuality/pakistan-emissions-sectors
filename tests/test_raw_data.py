"""The raw inputs: all held, all listed, all licensed, and nothing over the limit in plain git.

There is no cloud backup of this project. `sources/` holds government scans that are in several
cases no longer published anywhere, so "we have the raw data" is a claim the suite should be
able to falsify rather than a thing everyone assumes. These tests do four jobs:

  * the manifest covers every raw file that exists on disk - so the register cannot drift
    behind the directory, which is exactly how 3.2 GB came to sit outside version control
    behind a .gitignore comment claiming it was backed up elsewhere;
  * every raw file declares how it is held, with no third category of "nobody noticed";
  * any file over GitHub's 100 MB limit is in LFS, which is the RULE that .gitattributes only
    lists the current members of;
  * share-alike data is LABELLED wherever it lives - it is tracked now, because a licence
    governs redistribution rather than local storage, and the question becomes live at push.

The content hashes are NOT verified here. Hashing 12.87 GB takes minutes and belongs in
scripts/verify_raw_data.py, which is a deliberate operator action before trusting a mirror.
What the suite checks is that the register is honest about what exists.

Run:  python3 -m unittest discover tests -p "test_raw_data.py"
"""

from pkinv.assets import asset_path
import csv
import os
import subprocess
import unittest

from _support import require_documents, require_layers  # noqa: E402  (rc42: the documents gate)
from pkinv.core.io import read_rows
from _support import ROOT

MANIFEST = asset_path(ROOT, "data", "raw_manifest.csv")
GITHUB_FILE_LIMIT = 100 * 1024 * 1024

# Trees the manifest is responsible for, mirrored from scripts/raw_data_manifest.py.
# rc36: data/raw (the held acquisitions, the NEPRA corpus included) and data/gis (the
# rasters and boundaries) joined; both had been in neither hash manifest.
TREES = ("sources", os.path.join("data", "cache"), os.path.join("data", "raw"),
         os.path.join("data", "gis"),
         os.path.join("data", "pbs_census"), os.path.join("data", "district_records"),
         os.path.join("data", "gleam"), os.path.join("data", "gmw"), os.path.join("data", "nfdc"))
SKIP_NAMES = {".DS_Store"}
# The gitignored derived caches beside the raw gis inputs - rebuilt by a producer from
# files the manifest lists, so deliberately not rows (mirrored from the script's SKIP_PATHS).
SKIP_PATHS = {
    "data/gis/adm2_intersections_267x340.csv",
    "data/gis/adm2_intersections_267x340.csv.txt",
}


def _manifest():
    return read_rows(MANIFEST, comments=False)


def _on_disk():
    """A FRESH enumeration, through the builder's own walk() rather than a copy of it.

    This used to re-walk the legacy TREES itself, and the sector layout broke it silently:
    asset_path() does not translate an ambiguous legacy DIRECTORY, so `data/gis` passed
    through, `os.path.isdir` said no, and the whole spatial tree counted as absent - 65
    rows reported "not here" while every one of the files was on disk under
    data/sectors/*/gis and data/shared/gis. A mirrored constant that drifts is exactly
    the failure this module exists to catch, so the mirror is gone.

    This is still a real comparison, not a tautology: walk() enumerates the disk NOW,
    the manifest records what it enumerated WHEN IT WAS RUN, and a file deleted in
    between is listed and not present - which is the finding.
    """
    from _support import load_script
    return {relative for relative, _full in load_script("raw_data_manifest").walk()}


class TestTheManifestMatchesTheDisk(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = _manifest()
        cls.listed = {r["path"] for r in cls.rows}
        cls.present = _on_disk()

    def test_small_tracked_rows_carry_the_digest_of_the_file_on_disk(self):
        """rc41: the committed manifest carried stale digests for two files rc40 had
        changed (the district livestock transcription and the rice sidecar) - the script is
        hand-run and nothing compared its record with the disk. The 12.87 GB cannot be
        re-hashed in a test; the ~5,200 git-tracked rows under 2 MB can, in under three
        seconds, and those are the rows a release edits."""
        import hashlib
        stale = []
        for row in self.rows:
            if row["tracked"] != "git" or int(row["bytes"]) > 2_000_000:
                continue
            path = asset_path(ROOT, row["path"])
            if not os.path.exists(path):
                continue
            with open(path, "rb") as handle:
                digest = hashlib.sha256(handle.read()).hexdigest()
            if digest != row["sha256"]:
                stale.append(row["path"])
        self.assertFalse(stale, "%d manifest rows carry a digest the file on disk does not - "
                                "run scripts/raw_data_manifest.py:\n  " % len(stale)
                                + "\n  ".join(stale))

    def test_every_raw_file_on_disk_is_listed(self):
        """A file nobody registered is a file the mirror script will not copy."""
        missing = sorted(self.present - self.listed)
        self.assertFalse(missing,
                         "%d raw files are on disk and not in the manifest - run "
                         "scripts/raw_data_manifest.py:\n  %s"
                         % (len(missing), "\n  ".join(missing[:20])))

    def test_every_listed_file_is_on_disk(self):
        """The other direction, and the more alarming one: a listed file that has gone."""
        gone = sorted(self.listed - self.present)
        # rc42: inside a package the three registered-not-shipped trees are absent by design
        # (the documents gate mounts them); a missing file anywhere else is still a finding
        from _support import unshipped_registered
        unshipped = unshipped_registered()
        gone = [p for p in gone if p not in unshipped]
        self.assertFalse(gone,
                         "%d manifest rows name files that are not here. A raw input cannot "
                         "be re-derived from anything in this repository:\n  %s"
                         % (len(gone), "\n  ".join(gone[:20])))

    def test_nothing_is_unclassified(self):
        stray = [r["path"] for r in self.rows if r["package"] == "unclassified"]
        self.assertFalse(stray, "no licence rule matched: %s" % stray[:10])

    def test_every_row_declares_how_it_is_held(self):
        for row in self.rows:
            self.assertIn(row["tracked"], ("git", "lfs", "external"), row["path"])
            self.assertTrue(row["licence"].strip(), row["path"])
            self.assertTrue(int(row["bytes"]) >= 0)
            self.assertEqual(len(row["sha256"]), 64, row["path"])


class TestTheSizeRuleIsEnforcedNotRemembered(unittest.TestCase):
    """.gitattributes lists today's oversized files. This is the rule behind the list."""

    def test_no_file_over_the_github_limit_is_in_plain_git(self):
        offenders = []
        for row in _manifest():
            if int(row["bytes"]) > GITHUB_FILE_LIMIT and row["tracked"] == "git":
                offenders.append("%s (%.0f MB)"
                                 % (row["path"], int(row["bytes"]) / 1024 ** 2))
        self.assertFalse(offenders,
                         "these exceed GitHub's 100 MB per-file limit in plain git and will "
                         "be REJECTED at push. Add a pattern to .gitattributes:\n  %s"
                         % "\n  ".join(offenders))

    def test_the_lfs_rows_really_are_lfs(self):
        """Guards the failure mode that started this: a .gitattributes pattern containing a
        space silently matches nothing and the file goes to plain git looking fine."""
        # rc69: each path's LFS state is asked of the repository that owns it - the documents
        # are tracked by the private checkout mounted beside a public clone.
        from pkinv.core import layers
        require_layers("which documents git stores in LFS")
        actual = layers.lfs_files(root=ROOT)
        if not actual:
            self.skipTest("git-lfs not available")
        claimed = {r["path"] for r in _manifest() if r["tracked"] == "lfs"}
        self.assertEqual(claimed - actual, set(),
                         "the manifest calls these LFS and git does not")


class TestTheShareAlikeDataIsLabelledWhereverItLives(unittest.TestCase):
    """These payloads used to be kept out of git to avoid relicensing them by inclusion.

    They are tracked now, because that reasoning was about REDISTRIBUTION and was being
    applied to LOCAL STORAGE, where it protected no licence and risked the only copy of nine
    gigabytes. What has to survive that change is the labelling: the licence question is
    unchanged and becomes live at push or publication, so every ODbL row must still say so
    and the licence must still sit beside the bytes.
    """

    def test_every_odbl_payload_declares_its_licence(self):
        odbl = [r for r in _manifest() if r["licence"] == "ODbL-1.0"]
        self.assertTrue(odbl, "the ODbL rows have vanished from the manifest")
        adsb = [r for r in odbl if r["path"].startswith("data/cache/aviation/adsblol/")]
        self.assertTrue(adsb, "the ADS-B payloads are no longer labelled ODbL")
        for row in adsb:
            self.assertNotEqual(row["licence"], "CC-BY-4.0", row["path"])
            self.assertEqual(row["package"], "odbl-external", row["path"])

    def test_the_licence_sits_beside_the_bytes(self):
        """A carve-out recorded only in a manifest is one a copier will not see."""
        require_documents("data/cache/aviation/adsblol/LICENSE-ODbL")
        self.assertTrue(os.path.exists(asset_path(ROOT, "data", "cache", "aviation", "adsblol", "LICENSE-ODbL")),
            "the ODbL payloads carry no licence file beside them")

    def test_every_raw_file_is_hashed_however_it_is_held(self):
        """Tracked, LFS or external - none of those states means unchecked."""
        for row in _manifest():
            self.assertEqual(len(row["sha256"]), 64, row["path"])


if __name__ == "__main__":
    unittest.main()
