"""Packaging preserves dependency licences, actual code bytes and reproduction assets."""
import hashlib
import fnmatch
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
import zipfile

from pkinv.paths import ROOT
from pkinv.report import deposit_licensing as licensing
from pkinv.report import deposit_manifest as manifest


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, Path(ROOT) / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class IntegratedDeposit(unittest.TestCase):
    def test_reproduction_fixtures_and_plotted_data_are_in_package_selection(self):
        patterns = dict(manifest.DEPOSIT_PATTERNS)
        required = {
            "code": ("tests/semantic/golden/national_total_reference_fy2023_24.json",),
            "documentation": ("campaign/v3_readiness/repair_register.csv",
                              "campaign/v3_readiness/reproduction_rc68/result.json"),
        }
        for kind, paths in required.items():
            for path in paths:
                self.assertTrue(any(fnmatch.fnmatch(path, p) for p in patterns[kind]), path)

    def test_old_derived_spatial_and_baseline_data_do_not_inherit_own_work(self):
        paths = ("data/baselines/rc67_integrated_campaign/outputs/pakemis_atomic_annual.csv",
                 "outputs/railways_grid_2024.nc", "outputs/aviation_adsblol_pilot_days.csv")
        for path in paths:
            self.assertEqual("odbl-companion", licensing.package_group(path))
            licence, reason = manifest.licence_of_deposited(path, {})
            self.assertEqual(manifest.PUBLIC_LICENCE, licence)
            self.assertIn("ODbL", reason)

    def test_primary_scopes_are_separate_from_direct_odbl_dependencies(self):
        for path in licensing.ODBL_INPUTS:
            self.assertEqual("odbl-companion", licensing.package_group(path), path)
        for path in ("outputs/pakemis_ghg_configuration_adm2_year.csv",
                     "outputs/pakemis_grid_0p05_annual_ref_fy2015_16_fy2024_25.nc"):
            self.assertEqual("primary", licensing.package_group(path))
        audit = licensing.audit_rows()
        self.assertTrue(all(row["evidence_sha256"] for row in audit if row["row_kind"] != "preserved_scope"))

    def test_current_software_bytes_and_lockfile_enter_the_verified_archive(self):
        builder = load("deposit_builder", "scripts/build_deposit_zip.py")
        verifier = load("deposit_unpacker", "scripts/unpack_deposit.py")
        rows = [{"kind": "code", "path": "src/pakemis_query/functions.py"},
                {"kind": "build", "path": "requirements.lock"}]
        with tempfile.TemporaryDirectory() as directory:
            path = builder.software_zip(os.path.join(directory, "software.zip"), rows)
            with zipfile.ZipFile(path) as archive:
                listed = verifier.verify(archive)
                prefix = "pakemis-%s/" % builder.VERSION
                self.assertIn(prefix + "requirements.lock", listed)
                self.assertEqual((Path(ROOT) / rows[0]["path"]).read_bytes(), archive.read(prefix + rows[0]["path"]))
                metadata = json.loads(archive.read(prefix + "RELEASE_SNAPSHOT.json"))
                self.assertEqual(40, len(metadata["git_head"]))
                self.assertEqual(64, len(metadata["software_content_sha256"]))
                self.assertIn("working_tree_modified", metadata)

    def test_documentation_carries_the_documentation_rows_and_the_licences(self):
        builder = load("deposit_docs", "scripts/build_deposit_zip.py")
        rows = [{"kind": "documentation", "path": "docs/reproducibility.md",
                 "package_group": "primary"},
                {"kind": "product", "path": "outputs/national_all_sectors.csv",
                 "package_group": "primary"}]
        paths = dict(builder.documentation_layout(rows))
        self.assertIn("docs/reproducibility.md", paths)
        self.assertNotIn("outputs/national_all_sectors.csv", paths)
        for name in ("LICENSE-data", "LICENSE-ODbL", "CITATION.cff"):
            self.assertIn(name, paths)

    def test_restore_layout_preserves_inputs_and_reproduction_outputs(self):
        unpacker = load("deposit_layout", "scripts/unpack_deposit.py")
        expected = {
            "pakemis-support/inputs/sectors/power/activity/coal_rank_account.csv": "data/sectors/power/activity/coal_rank_account.csv",
            "pakemis-support/reproduction/district_totals_2024.csv": "outputs/district_totals_2024.csv",
            "pakemis-core/semantic/fact_annual.csv": "outputs/semantic/fact_annual.csv",
            "pakemis-core/review-evidence/campaign/v3_readiness/repair_register.csv": "campaign/v3_readiness/repair_register.csv",
            "docs/deposit_rebuild_limits.md": "docs/deposit_rebuild_limits.md",
        }
        for archive, restored in expected.items():
            self.assertEqual(restored, str(unpacker.destination(archive, "data")))
        with self.assertRaises(ValueError):
            unpacker.destination("../../sources/private.zip", "data")

    def test_an_archive_is_verified_against_its_own_list_not_a_nested_one(self):
        """rc68: the data archive lists reproduction_rc68/SHA256SUMS before its root list, and
        the helper checked the nested list's README.md against the archive's own README.md."""
        unpacker = load("deposit_verify", "scripts/unpack_deposit.py")
        nested = b"nested readme\n"
        nested_sums = "%s  README.md\n" % hashlib.sha256(nested).hexdigest()
        files = {"pakemis-core/review-evidence/campaign/x/SHA256SUMS": nested_sums.encode(),
                 "pakemis-core/review-evidence/campaign/x/README.md": nested,
                 "README.md": b"archive readme\n"}
        root = "".join("%s  %s\n" % (hashlib.sha256(body).hexdigest(), name)
                       for name, body in sorted(files.items()))
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "data.zip")
            with zipfile.ZipFile(path, "w") as archive:
                for name, body in files.items():
                    archive.writestr(name, body)
                archive.writestr("SHA256SUMS", root)
            with zipfile.ZipFile(path) as archive:
                self.assertEqual(unpacker.verify(archive), set(files))


if __name__ == "__main__":
    unittest.main()
