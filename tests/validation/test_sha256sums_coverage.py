"""SHA256SUMS covers every packaged file except itself, and the inventory agrees with it."""
import os
import unittest

from _support import ROOT
from validation._package import IN_PACKAGE, SUMS, inventory


def listed():
    out = {}
    with open(SUMS, encoding="utf-8") as handle:
        for line in handle:
            line = line.rstrip("\n")
            if line:
                digest, _, rel = line.partition("  ")
                out[rel] = digest
    return out


class TestSha256sumsCoverage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not IN_PACKAGE:
            raise unittest.SkipTest("only inside a built validation package")
        cls.sums = listed()

    def test_the_root_records_are_listed(self):
        for name in ("VALIDATION_MANIFEST.json", "FILE_INVENTORY.csv", "KNOWN_EXCEPTIONS.json",
                     "EXPECTED_RESULTS.json", "README_VALIDATION.md", "validate.sh", "reproduce.sh"):
            self.assertIn(name, self.sums)
        self.assertNotIn("SHA256SUMS", self.sums)

    def test_every_file_in_the_tree_is_listed(self):
        unlisted = []
        for folder, dirs, names in os.walk(ROOT):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for name in names:
                rel = os.path.relpath(os.path.join(folder, name), ROOT)
                if rel == "SHA256SUMS" or name.endswith((".pyc", ".DS_Store")):
                    continue
                if rel.startswith("logs/"):
                    continue          # rewritten by every run; digests describe the packager's run
                if rel not in self.sums:
                    unlisted.append(rel)
        self.assertEqual(unlisted, [], "files the package does not vouch for:\n  " + "\n  ".join(unlisted[:40]))

    def test_the_inventory_and_the_sums_name_the_same_files(self):
        inv = {r["relative_path"]: r for r in inventory()}
        listed_non_log = {p for p in self.sums if not p.startswith("logs/")}
        inv_non_log = {p for p in inv if not p.startswith("logs/") and p != "SHA256SUMS"}
        self.assertEqual(listed_non_log - inv_non_log, set(), "in SHA256SUMS but not the inventory")
        self.assertEqual(inv_non_log - listed_non_log, set(), "in the inventory but not SHA256SUMS")
        for rel, row in inv.items():
            if row["sha256"] and rel in self.sums:
                self.assertEqual(row["sha256"], self.sums[rel], rel)


if __name__ == "__main__":
    unittest.main()
