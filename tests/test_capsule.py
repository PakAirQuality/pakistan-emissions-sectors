"""rc39 A12: the deposit capsule reruns, and says where it was rerun.

The rc38 witness passed all 361 of its own checksums while covering 111 of 618
release-checksum files and 40 of 68 manifest products, so its "everything needed to rerun"
claim rested on a checksum set describing the capsule rather than the release. A capsule that
has not been rerun is a claim; running it is what makes it a record.

THE SUITE NEEDS NOTHING INSTALLED. requirements.txt has said for releases that the national
and provincial phases run on the standard library alone; this capsule is the first artefact
to prove it, in a venv created with `python3 -m venv` and nothing added. That is why
capsule/run_tests.sh ships no pinned requirements file - a suite with no third-party imports
has no versions that could drift, and shipping one would imply a dependency surface that is
not there.

These tests do not build the capsule (148 MB, and the builder runs a venv and a suite inside
it). They hold the SHIPPED script and builder to what they promise, which is the part that
can rot silently between releases.
"""
import os
import re
import unittest

from _support import ROOT

SCRIPT = os.path.join(ROOT, "capsule", "run_tests.sh")
BUILDER = os.path.join(ROOT, "scripts", "build_capsule.py")


def _read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


class TestTheCapsuleScriptIsShipped(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = _read(SCRIPT)
        cls.builder = _read(BUILDER)

    def test_the_script_exists_and_is_a_shell_script(self):
        self.assertTrue(self.script.startswith("#!/bin/sh"))

    def test_it_creates_a_clean_interpreter_rather_than_using_the_host(self):
        """The point of the rerun is that it does NOT inherit this machine's site-packages.
        If it ever calls the host python directly, the demonstration stops demonstrating."""
        self.assertIn("python3 -m venv", self.script)
        self.assertIn('"$VENV/bin/python" -m unittest', self.script)
        self.assertLess(self.script.index('"$VENV/bin/python" -m pkinv.activity.build'),
                        self.script.index('"$VENV/bin/python" -m unittest'))

    def test_the_modules_it_runs_all_exist(self):
        block = self.script.split('MODULES="')[1].split('"')[0]
        modules = [line.split()[0] for line in block.strip().splitlines() if line.strip()]
        self.assertGreaterEqual(len(modules), 13)
        for module in modules:
            path = os.path.join(ROOT, "tests", "%s.py" % module)
            self.assertTrue(os.path.exists(path), "%s is listed and does not exist" % module)

    def test_the_suite_and_the_builder_name_the_same_modules(self):
        """Two lists of the same thing drift. If they ever disagree, the capsule ships one
        suite and the builder was verified against another."""
        block = self.script.split('MODULES="')[1].split('"')[0]
        in_script = {line.split()[0] for line in block.strip().splitlines() if line.strip()}
        in_builder = set(re.findall(r'"(test_[a-z_0-9]+)"', self.builder))
        self.assertEqual(in_script, in_builder)

    def test_it_states_what_was_verified_and_what_was_not(self):
        """The specific failure this replaces: a manifest implying a portability nobody
        tested. The script must name the platform AND name what it did not cover."""
        self.assertIn("NOT verified on Linux", self.script)
        self.assertRegex(self.script, r"CPython 3\.\d+")

    def test_it_does_not_claim_a_dependency_surface_it_does_not_have(self):
        for token in ("pip install", "requirements-capsule"):
            self.assertNotIn(token, self.script,
                             "the suite is stdlib-only; installing anything would imply "
                             "otherwise")

    def test_it_says_why_the_release_integrity_tests_are_absent(self):
        """A reader counting tests will notice four missing. Silence there reads as an
        omission rather than a boundary."""
        self.assertIn("release-integrity", self.script)


class TestTheBuilderIsHonestAboutWhatItShips(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.builder = _read(BUILDER)

    def test_it_excludes_the_held_source_documents_and_says_why(self):
        """3.8 GB of PDFs are not in the capsule. That is a decision, and the reason - the
        capsule reruns the engine, and the documents are listed with hashes - has to travel
        with it or the absence looks like an oversight."""
        self.assertIn("data/raw", self.builder)
        self.assertIn("held SOURCE DOCUMENTS", self.builder)

    def test_it_writes_its_own_manifest_and_checksums(self):
        self.assertIn("MANIFEST.csv", self.builder)
        self.assertIn("SHA256SUMS", self.builder)

    def test_it_runs_the_suite_inside_the_assembled_tree(self):
        """The inclusion rule is verified by execution, not by inspection: a file left out
        must fail the rerun rather than surprise whoever downloads it."""
        self.assertIn("def demonstrate", self.builder)
        self.assertIn("cwd=DIST", self.builder)

    def test_it_records_the_result_rather_than_assuming_it(self):
        self.assertIn("VERIFIED.txt", self.builder)
        self.assertIn('"PASSED" if code == 0 else "FAILED"', self.builder)

    def test_the_capsule_tree_is_not_committed(self):
        """148 MB of copies of tracked files. Committing it would double the repository to
        no purpose, so dist/ is ignored and the capsule is built on demand."""
        ignore = _read(os.path.join(ROOT, ".gitignore"))
        self.assertIn("/dist/", ignore)


if __name__ == "__main__":
    unittest.main()
