"""Every served release is a commit this repository can still produce, and the label is not the pin.

The register is data/catalog/published_release_vintages.csv, built by
scripts/build_published_vintages.py. Two different things are guarded.

First, HISTORY: each published row names a commit, and git must still hold, at that
commit, the exact bytes whose digests were published for the semantic contract and the
release manifest. Thirteen rows, thirteen checks against git - not a transcription that
agrees with itself.

Second, THE LABEL: the register's last row is the working tree, and it says how the tree
stands against the vintage already published under the tree's own version string. Today it
says `diverged-under-the-same-label`, which is the finding that produced this file: the
Explorer serves rc59 byte-identically to commit 5915e0c0 while this tree, also rc59, reads
Punjab FY2015-16 0.653744 Mt higher. The guard does not demand that the tree match - a
candidate series may rebuild under its own label - it demands that the state be one of the
three named ones and that it be CORRECT, so "matches-published" cannot be claimed by a
tree that has moved.

WHICH AXIS moved is a different question and lives in
outputs/pakemis_release_axis_fingerprints.csv with its own guards: this register is about
identity, that product is about what changed inside it. The two carried overlapping
fingerprint columns for one commit and that was a duplication waiting to drift.
"""
import csv
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTER = os.path.join(ROOT, "data", "catalog", "published_release_vintages.csv")
BUILDER = os.path.join(ROOT, "scripts", "build_published_vintages.py")
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pkinv.core import layers                                          # noqa: E402
from _support import require_layers                                    # noqa: E402
STATES = {"not-yet-published", "matches-published", "diverged-under-the-same-label"}


def rows():
    with open(REGISTER, encoding="utf-8") as handle:
        return list(csv.DictReader(line for line in handle if not line.startswith("#")))


class TestPublishedVintages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = rows()
        cls.published = [r for r in cls.rows if r["commit"] != "(working tree)"]
        cls.tree = [r for r in cls.rows if r["commit"] == "(working tree)"]

    def test_the_register_is_populated_and_has_exactly_one_working_tree_row(self):
        """The positive control: an empty or truncated register fails here first."""
        self.assertGreaterEqual(len(self.published), 13)
        self.assertEqual(len(self.tree), 1,
                         "the register must carry exactly one working-tree row; it is "
                         "what makes the label-is-not-the-pin claim checkable")

    def test_git_still_reproduces_every_published_vintage(self):
        """The falsifiable half: each row's digests are re-hashed out of git."""
        require_layers("the release history through rc68, held by the private checkout")
        import hashlib
        problems = []
        for row in self.published:
            for path, column in (("outputs/semantic/semantic_release.json",
                                  "semantic_release_sha256"),
                                 ("outputs/release_manifest.json",
                                  "release_manifest_sha256")):
                held = layers.git_show(row["commit"], path, root=ROOT)
                if held is None:
                    problems.append("%s: %s held nothing at %s"
                                    % (row["version"], row["commit"], path))
                    continue
                got = hashlib.sha256(held).hexdigest()
                if got != row[column]:
                    problems.append("%s: %s holds %s at %s, published %s"
                                    % (row["version"], row["commit"], got[:12], path,
                                       row[column][:12]))
        self.assertFalse(problems,
                         "a published release is no longer reproducible from this "
                         "repository:\n  " + "\n  ".join(problems))
        for row in self.published:
            self.assertEqual(row["git_reproduces_both_digests"], "yes", row["version"])

    def test_no_version_is_published_twice_with_different_content(self):
        """The invariant the defect would break, stated over the register itself."""
        seen = {}
        for row in self.published:
            key = row["version"]
            pair = (row["semantic_release_sha256"], row["release_manifest_sha256"])
            if key in seen and seen[key] != pair:
                self.fail("%s appears twice with different digests; a version string that "
                          "names two contents cannot be cited" % key)
            seen[key] = pair

    def test_the_working_tree_row_states_a_known_and_correct_state(self):
        """Not "the tree must match" - "the tree must not misdescribe itself"."""
        import hashlib
        row = self.tree[0]
        state = row["contract_at_commit"]
        self.assertIn(state, STATES, "unknown working-tree state %r" % state)
        # Recomputed, never compared against a stored digest: the register's working-tree
        # row carries none, because the release manifest is regenerated several times in a
        # release dance and a stored digest would restale the file on routine work.
        on_disk = {}
        for path, column in (("outputs/semantic/semantic_release.json",
                              "semantic_release_sha256"),
                             ("outputs/release_manifest.json",
                              "release_manifest_sha256")):
            with open(os.path.join(ROOT, path), "rb") as handle:
                on_disk[column] = hashlib.sha256(handle.read()).hexdigest()
            self.assertTrue(row[column].startswith("n.a."),
                            "the working-tree row carries a digest for %s; it must not - "
                            "see the builder's comment on why a stored digest restales"
                            % path)
        match = [r for r in self.published if r["version"] == row["version"]]
        if not match:
            self.assertEqual(state, "not-yet-published")
            return
        same = all(match[0][c] == on_disk[c] for c in on_disk)
        self.assertEqual(state, "matches-published" if same
                         else "diverged-under-the-same-label",
                         "the working-tree row claims %r while the digests say otherwise; "
                         "a label that does not identify its content is exactly what this "
                         "register exists to make visible" % state)

    def test_it_regenerates_identically(self):
        before = open(REGISTER, "rb").read()
        run = subprocess.run([sys.executable, BUILDER], cwd=ROOT,
                             capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr[-2000:])
        self.assertEqual(before, open(REGISTER, "rb").read(),
                         "the register does not regenerate byte-identically")


if __name__ == "__main__":
    unittest.main()
