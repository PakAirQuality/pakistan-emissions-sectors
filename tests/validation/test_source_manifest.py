"""data/SOURCE_MANIFEST.csv carries what the registers hold, and never an mtime (rc41, P-2).

The rc40 package's manifest had 0 of 5,431 rows with a publisher, URL, edition, period or
locator, and a retrieval_date that was the file's mtime for 97 % of rows - the join keyed the
raw-acquisition register on the wrong path. The packager now joins each register on the key
it is actually keyed by; these tests hold the fill at the floors measured on the rc41 tree
and refuse a numeric (mtime-like) retrieval date anywhere. Package-only.
"""

from pkinv.assets import asset_path
import os
import re
import unittest

from _support import ROOT
from validation._package import IN_PACKAGE, data_rows

MANIFEST = asset_path(ROOT, "data", "SOURCE_MANIFEST.csv")


class TestTheSourceManifestIsFilledFromTheRegisters(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not IN_PACKAGE or not os.path.exists(MANIFEST):
            raise unittest.SkipTest("only inside a built validation package")
        cls.rows = data_rows(MANIFEST)

    def _filled(self, column):
        return sum(1 for r in self.rows if r[column] and r[column] != "..")

    def test_no_retrieval_date_is_an_mtime(self):
        numeric = [r["source_document_id"] for r in self.rows if r["retrieval_date"].strip().isdigit()]
        self.assertEqual(numeric, [])

    def test_the_raw_acquisitions_carry_their_register(self):
        """Every data/raw acquisition data/manifests/source_manifest.csv registers has its
        URL, retrieval timestamp, edition and coverage on the row (150 on the rc41 tree)."""
        self.assertGreaterEqual(self._filled("source_url"), 150)
        self.assertGreaterEqual(self._filled("retrieval_date"), 150)
        self.assertGreaterEqual(self._filled("edition"), 100)
        self.assertGreaterEqual(self._filled("reference_period"), 100)

    def test_publishers_and_locators_are_named_where_a_register_names_them(self):
        self.assertGreaterEqual(self._filled("publisher"), 200)
        # the not-retained register's page coordinates and the transcription register's
        # cell locators, joined on the data file each feeds
        self.assertGreaterEqual(self._filled("page_or_cell_range"), 30)

    # rc42 (the twentieth review's R8): a digest column is a digest or nothing, and a row that
    # names a shipped file carries THAT file's digest - rc41 carried the source document's
    # (or a sentence) on 106 of 169 shipped rows.
    HEX64 = re.compile(r"^[0-9a-f]{64}$")

    def test_digest_columns_are_digests_or_blank(self):
        for r in self.rows:
            for column in ("sha256", "document_sha256"):
                self.assertTrue(r[column] == "" or self.HEX64.match(r[column]),
                                "%s: %s = %r" % (r["source_document_id"], column, r[column][:40]))

    def test_every_shipped_row_carries_its_own_files_digest(self):
        from validation._package import sha256
        shipped = [r for r in self.rows if r["relative_path_or_not_included"] != "NOT INCLUDED"]
        self.assertGreater(len(shipped), 100)
        for r in shipped:
            path = asset_path(ROOT, r["relative_path_or_not_included"])
            self.assertTrue(os.path.exists(path), r["relative_path_or_not_included"])
            self.assertEqual(r["sha256"], sha256(path), r["relative_path_or_not_included"])
            self.assertEqual(r["size_bytes"], str(os.path.getsize(path)), r["relative_path_or_not_included"])

    def test_the_publisher_column_says_where_it_came_from(self):
        for r in self.rows:
            self.assertIn(r["publisher_basis"], ("register", "url-host", "folder", ""), r["source_document_id"])
            if r["publisher"]:
                self.assertNotEqual(r["publisher_basis"], "", "%s names a publisher with no basis" % r["source_document_id"])


if __name__ == "__main__":
    unittest.main()
