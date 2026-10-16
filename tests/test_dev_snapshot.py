"""The development snapshot and the deposit zips are deterministic and self-describing."""
import hashlib
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from _support import release_time_check  # noqa: E402
import zipfile
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
import pkinv  # noqa: E402


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "scripts", name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class WorkingTreeEnumeration(unittest.TestCase):
    def test_unstaged_deletion_is_not_a_snapshot_input(self):
        builder = _load("build_validation_package")
        with tempfile.TemporaryDirectory(prefix="pakemis-snapshot-inputs-") as root:
            os.makedirs(os.path.join(root, "tests"))
            retained = "tests/retained.py"
            with open(os.path.join(root, retained), "w", encoding="utf-8") as handle:
                handle.write("# retained working-tree input\n")
            removed = "tests/removed_golden.json"
            with patch.object(builder, "ROOT", root), \
                 patch.object(builder, "git", return_value=retained + "\n" + removed + "\n"), \
                 patch.object(builder, "asset_catalog", return_value=[]), \
                 patch.object(builder.deposit, "DEPOSIT_PATTERNS", ()), \
                 patch.object(builder.deposit, "reviewer_guides", return_value=[]):
                paths = builder.tracked_files()
            self.assertIn(retained, paths)
            self.assertNotIn(removed, paths)


class DevSnapshot(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # THE SNAPSHOT IS BUILT FROM A GIT CHECKOUT, so it cannot be built inside a
        # distributed package, which carries no .git by design: build_dev_snapshot.stage()
        # enumerates `git ls-files`, and with no repository that list is empty, so every
        # folder this class asserts is absent and the failure says "paper/national" rather
        # than "there is no git here". rc43 is the first release to SHIP this test inside
        # the validation package - it arrived with the snapshot in Wave 4, after rc42 was
        # cut - and it failed there for exactly that reason. Skipping is the honest answer:
        # the property under test is a property of the repository, and the package is not
        # one.
        if not os.path.isdir(os.path.join(ROOT, ".git")):
            raise unittest.SkipTest(
                "the development snapshot is built from a git checkout; this tree has no "
                "repository (a distributed package), so there is nothing to enumerate")
        cls.mod = _load("build_dev_snapshot")
        cls.tmp = tempfile.mkdtemp(prefix="pakemis-devsnap-")
        cls.top = cls.mod.stage(cls.tmp)
        cls.zip1 = cls.mod.zip_deterministic(cls.top, os.path.join(cls.tmp, "a.zip"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_layout_has_every_requested_folder(self):
        for folder in ("paper/national", "paper/common", "paper/technical_notes", "paper/pdf", "outputs/semantic",
                       "registries", "schemas", "data/geometry", "src/pkinv", "src/pakemis_query", "tests", "release"):
            self.assertTrue(os.path.isdir(os.path.join(self.top, folder)), folder)
        for name in ("README_DEV.md", "SHA256SUMS", "data/geometry/LICENSES.md", "release/release_manifest.json",
                     "schemas/semantic_release.schema.json", "registries/periods.csv", "registries/sectors.csv"):
            self.assertTrue(os.path.exists(os.path.join(self.top, name)), name)

    def test_nothing_from_sources_raw_or_cache_and_no_surfaces_by_default(self):
        for folder, _dirs, names in os.walk(self.top):
            rel = os.path.relpath(folder, self.top)
            self.assertFalse(rel.startswith(("sources", "data/raw", "data/cache", "dist", ".git", "data/geometry/manual")), rel)
            self.assertNotIn("__pycache__", rel)

    def test_sha256sums_covers_every_file_and_verifies(self):
        listed = {}
        with open(os.path.join(self.top, "SHA256SUMS"), encoding="utf-8") as handle:
            for line in handle:
                digest, _, rel = line.rstrip("\n").partition("  ")
                listed[rel] = digest
        on_disk = set()
        for folder, _dirs, names in os.walk(self.top):
            for name in names:
                rel = os.path.relpath(os.path.join(folder, name), self.top)
                if rel != "SHA256SUMS":
                    on_disk.add(rel)
        self.assertEqual(on_disk, set(listed))
        for rel, digest in listed.items():
            self.assertEqual(_sha(os.path.join(self.top, rel)), digest, rel)

    def test_readme_says_what_it_is_not(self):
        with open(os.path.join(self.top, "README_DEV.md"), encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("not a validation package", text)
        self.assertIn(pkinv.__version__, text)
        self.assertIn("pakemis_source_register.csv", text)

    def test_the_zip_is_deterministic(self):
        zip2 = self.mod.zip_deterministic(self.top, os.path.join(self.tmp, "b.zip"))
        self.assertEqual(_sha(self.zip1), _sha(zip2))
        with zipfile.ZipFile(self.zip1) as z:
            names = z.namelist()
        tops = {n.split("/")[0] for n in names}
        self.assertEqual(tops, {self.mod.NAME})
        with zipfile.ZipFile(zip2) as z:
            self.assertEqual(names, z.namelist())


class DepositZips(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        release_time_check("the deposit archives are laid out from the release's deposit manifest")
        cls.mod = _load("build_deposit_zip")
        cls.rows = cls.mod.deposit_rows()

    # The integrated package supplies registered compiled dependencies in a
    # reproduction-support lane and separates ODbL-sensitive records. No
    # manifest product is silently omitted from both archives.
    DECLARED_UNPLACED = {}

    def test_data_layout_is_a_partition_of_the_manifests_data_rows(self):
        entries = self.mod.data_layout(self.rows)
        arcs = [a for a, _ in entries]
        self.assertEqual(len(arcs), len(set(arcs)))
        manifest_paths = {r["path"] for r in self.rows if r["kind"] in self.mod.DATA_KINDS and not r["path"].startswith("papers/")}
        placed = {rel for _, rel in entries}
        self.assertTrue(placed <= manifest_paths | {"outputs/pakemis_deposit_manifest.csv"}, placed - manifest_paths)

    def test_every_manifest_product_row_is_placed_or_declared(self):
        """THE OTHER DIRECTION. The test above is named for a partition and held one inclusion.

        It caught anything placed that is not a manifest row, and never asked whether every
        manifest row is placed - so thirteen hashed products could be skipped by the builder
        while the manifest claimed them and nothing failed. A partition needs both halves.
        """
        entries = self.mod.data_layout(self.rows) + self.mod.companion_layout(self.rows)
        placed = {rel for _, rel in entries}
        products = {r["path"] for r in self.rows if r["kind"] == "product"}
        missing = sorted(products - placed - set(self.DECLARED_UNPLACED))
        self.assertFalse(
            missing,
            "these deposit-manifest PRODUCT rows are hashed as deposited and the data archive "
            "would not contain them. The manifest is the release's claim that a reader gets "
            "the file; rule 7 excludes build-tier products; nothing reconciles the two. Either "
            "fix the file's role, remove it from the manifest, or declare it in "
            "DECLARED_UNPLACED with the reason:\n  %s" % "\n  ".join(missing))

    def test_no_declared_exclusion_is_stale(self):
        """A declaration for a row that is now placed reads as an exclusion still in force."""
        entries = self.mod.data_layout(self.rows) + self.mod.companion_layout(self.rows)
        placed = {rel for _, rel in entries}
        products = {r["path"] for r in self.rows if r["kind"] == "product"}
        gone = sorted(p for p in self.DECLARED_UNPLACED if p in placed or p not in products)
        self.assertFalse(
            gone,
            "these paths are declared unplaced and are either placed now or no longer "
            "manifest products. Remove the entry - a stale exclusion is a claim about the "
            "archive that is not true:\n  %s" % "\n  ".join(gone))

    def test_every_declared_exclusion_gives_a_reason(self):
        thin = sorted(k for k, v in self.DECLARED_UNPLACED.items() if len(v.strip()) < 25)
        self.assertFalse(thin, "declared exclusions with no substantive reason: %s" % thin)

    def test_every_entry_lands_in_a_declared_folder(self):
        """The tail of the original partition test, which my insertion had orphaned onto the
        method above - it referenced `arcs` from a scope it no longer shared and raised
        NameError rather than passing, which is the only reason it was caught."""
        arcs = [a for a, _ in self.mod.data_layout(self.rows)]
        self.assertTrue(all(a.split("/")[0] in ("pakemis-core", "pakemis-support",
                                                "pakemis-audit") or a in self.mod.ROOT_DOCS
                            for a in arcs))
        self.assertIn("pakemis-core/national_all_sectors.csv", arcs)
        self.assertIn("pakemis-core/semantic/semantic_release.json", arcs)
        self.assertIn("pakemis-core/provenance/pakemis_deposit_manifest.csv", arcs)

    def test_build_artifacts_are_only_in_the_reproduction_support_directory(self):
        """Registered compiled dependencies remain distinct from core advertised data."""
        tier = self.mod.tiers()
        kind = {r["path"]: r["kind"] for r in self.rows}
        for arc, rel in self.mod.data_layout(self.rows):
            if rel.startswith("outputs/") and kind.get(rel) == "product":
                if tier.get(rel[len("outputs/"):]) == "build":
                    self.assertTrue(arc.startswith("pakemis-support/reproduction/"), rel)

    def test_documentation_layout_is_the_pdfs_with_their_hash_sidecar(self):
        entries = dict(self.mod.documentation_layout(self.rows))
        self.assertIn("outputs/pakemis_paper_hashes.csv", entries)
        self.assertTrue(any(rel.startswith("papers/pdf/") for rel in entries), entries)

    def test_a_deposit_zip_is_deterministic(self):
        tmp = tempfile.mkdtemp(prefix="pakemis-deposit-")
        try:
            entries = self.mod.documentation_layout(self.rows)
            a = self.mod.write_zip(os.path.join(tmp, "a.zip"), entries)
            b = self.mod.write_zip(os.path.join(tmp, "b.zip"), entries)
            self.assertEqual(_sha(a), _sha(b))
            with zipfile.ZipFile(a) as z:
                self.assertIn("SHA256SUMS", z.namelist())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
