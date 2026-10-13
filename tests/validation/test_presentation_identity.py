"""The reading index and the runnable tree are the same bytes.

The package root is a repo-shaped tree the engine and the suite run against; the folders the
reviewer's specification names (registries/, outputs/annual/, manuscripts/, code/ ...) are
copies of those files under the names the specification uses, or views computed from them.
A copy that could drift from its canonical twin would be two products claiming one identity.
Every copy is therefore hashed against its source here, on every run.
"""

from pkinv.assets import asset_path
import os
import unittest

from _support import ROOT
from validation._package import IN_PACKAGE, inventory, sha256


class TestEveryPresentationCopyMatchesItsCanonicalFile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not IN_PACKAGE:
            raise unittest.SkipTest("only inside a built validation package")
        cls.rows = inventory()

    def test_copies_are_byte_identical_to_their_sources(self):
        copies = [r for r in self.rows if r["generated_or_source"] == "presentation_copy"]
        self.assertGreater(len(copies), 50, "the presentation layer is expected to be substantial")
        bad = []
        for r in copies:
            copy, source = asset_path(ROOT, r["relative_path"]), asset_path(ROOT, r["source_or_product_id"])
            if not os.path.exists(source):
                bad.append("%s -> source %s missing" % (r["relative_path"], r["source_or_product_id"]))
                continue
            if sha256(copy) != sha256(source) or sha256(copy) != r["sha256"]:
                bad.append("%s differs from %s" % (r["relative_path"], r["source_or_product_id"]))
        self.assertEqual(bad, [], "\n".join(bad))

    def test_every_view_names_its_generator(self):
        views = [r for r in self.rows if r["generated_or_source"] == "view"]
        self.assertTrue(views)
        for r in views:
            self.assertTrue(r["generation_command"].strip(), "%s has no generation_command" % r["relative_path"])
            self.assertTrue(r["source_or_product_id"].strip(), "%s names no source" % r["relative_path"])

    def test_no_symlinks_anywhere(self):
        found = []
        for folder, dirs, names in os.walk(ROOT):
            for name in dirs + names:
                if os.path.islink(os.path.join(folder, name)):
                    found.append(os.path.relpath(os.path.join(folder, name), ROOT))
        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
