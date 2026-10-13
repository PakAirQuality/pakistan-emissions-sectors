"""Relocation retains build identities, complete native bundles and package custody."""
import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pkinv import build, run_all
from pkinv.build_support import physical_paths
from pkinv.report import deposit_manifest as deposit


class AssetFixture(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.assets = []

    def write(self, path, text):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return target

    def catalog(self, *rows):
        self.assets = list(rows)
        fields = ("asset_id", "legacy_path", "path", "canonical_path", "purpose", "kind", "title")
        target = self.write("data/catalog/assets.csv", "")
        with target.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    def asset(self, name, legacy, path, **extra):
        return dict(asset_id=name, legacy_path=legacy, path=path, **extra)


class BuildLocations(AssetFixture):
    def test_directory_and_glob_declarations_expand_scattered_members(self):
        a = self.asset("one", "data/activity/ippu/a.csv", "data/sectors/ippu/activity/a.csv")
        b = self.asset("two", "data/activity/ippu/b.json", "data/sectors/ippu/metadata/b.json")
        self.catalog(a, b)
        self.assertEqual(physical_paths("data/activity/ippu/", self.root), (a["path"], b["path"]))
        self.assertEqual(physical_paths("glob:data/activity/ippu/*.csv", self.root), (a["path"],))
        self.assertEqual(physical_paths("held:data/activity/ippu/b.json", self.root), ("held:" + b["path"],))
        self.assertEqual(physical_paths("outputs/result.csv", self.root), ("outputs/result.csv",))
        self.assertEqual(physical_paths("data/unknown.csv", self.root), ("data/unknown.csv",))

    def test_asset_metadata_is_scoped_but_full_catalog_consumers_are_not(self):
        a = self.asset("one", "data/a.csv", "data/sectors/ippu/activity/a.csv", title="A")
        b = self.asset("two", "data/b.csv", "data/sectors/ippu/requests/b.csv", title="B")
        self.catalog(a, b)
        self.write("producer.py", "pass\n")
        self.write(a["path"], "value\n1\n")
        self.write("outputs/result.csv", "1\n")
        phase = run_all.Phase("numeric", "producer.py", writes=("outputs/result.csv",),
                              reads=(a["path"],), audited=True)
        cache = {"phases": {}}
        observation = {"complete": True, "reads": ["data/catalog/assets.csv"], "assets": ["one"]}
        with patch.object(run_all, "ROOT", str(self.root)):
            run_all.record_current(phase, cache, ["producer.py"], observation)
            self.catalog(dict(a, title="Readable new title"), dict(b, path="data/sectors/ippu/requests/new.csv"))
            self.assertTrue(run_all.is_current(phase, cache))
            self.catalog(dict(a, path="data/sectors/ippu/activity/moved.csv"), b)
            self.assertFalse(run_all.is_current(phase, cache))
            self.catalog(a, b)
            observation["whole_asset_catalog"] = True
            run_all.record_current(phase, cache, ["producer.py"], observation)
            self.catalog(dict(a, title="Updated catalog text"), b)
            self.assertFalse(run_all.is_current(phase, cache))

    def test_native_gis_members_survive_relocation(self):
        raster = self.asset("raster", "data/gis/manual/rice.tif", "data/sectors/agriculture/gis/rice.tif")
        sidecar = self.asset("proof", "data/gis/manual/RICE_SOURCES.json", "data/sectors/agriculture/gis/RICE_SOURCES.json")
        self.catalog(raster, sidecar)
        self.write(raster["path"], "native raster bytes")
        self.write(sidecar["path"], "{}")
        phase = run_all.Phase("agriculture", "pkinv.sectors.agriculture.run_inventory")
        cache = {"phases": {phase.label: {"observation_complete": True}}}
        with patch.object(run_all, "ROOT", str(self.root)):
            inputs = build.conservative_inputs(phase, [phase], cache)
        self.assertIn(raster["path"], inputs)
        self.assertIn(sidecar["path"], inputs)

    def test_metadata_only_assets_are_not_global_numerical_inputs(self):
        request = self.asset("request", "data/activity/ippu/request.csv", "data/sectors/ippu/requests/request.csv",
                             purpose="requests")
        self.catalog(request)
        self.write(request["path"], "note\nfirst\n")
        phase = run_all.Phase("national", "pkinv.report.national")
        cache = {"phases": {phase.label: {"observation_complete": True}}}
        with patch.object(run_all, "ROOT", str(self.root)):
            self.assertNotIn(request["path"], build.conservative_inputs(phase, [phase], cache))

    def test_old_path_receipts_are_invalidated_once(self):
        self.write("logs/build_cache.json", json.dumps({"schema": "pkinv.build_cache/v2",
                   "root": str(self.root), "phases": {"old": {"fingerprint": "old"}}}))
        with patch.object(run_all, "ROOT", str(self.root)):
            self.assertEqual(run_all.load_cache()["phases"], {})


class PackageLocations(AssetFixture):
    def test_new_owned_modules_are_packaged_before_staging(self):
        from scripts import build_validation_package as package
        self.catalog()
        module = "src/pkinv/new_package/reader.py"
        self.write(module, "VALUE = 1\n")
        self.write("private_notes.txt", "outside the package allowlist\n")
        self.write("src/pkinv/private_notes.txt", "not a Python module\n")
        with patch.object(package, "ROOT", str(self.root)), \
                patch.object(package, "git", return_value=""), \
                patch.object(deposit, "reviewer_guides", return_value=set()):
            files = package.tracked_files()
        self.assertIn(module, files)
        self.assertNotIn("private_notes.txt", files)
        self.assertNotIn("src/pkinv/private_notes.txt", files)

    def test_missing_declared_gis_companion_cannot_be_silently_omitted(self):
        from scripts import build_validation_package as package
        from types import SimpleNamespace
        sidecar = self.asset("proof", "data/gis/rail/RAIL_SOURCES.json", "data/sectors/railways/gis/RAIL_SOURCES.json")
        self.catalog(sidecar)
        custody = SimpleNamespace(register={}, public_documents={}, deposit={})
        with patch.object(package, "ROOT", str(self.root)), \
                patch.object(deposit, "canonical_recipe_inputs", return_value=set()):
            with self.assertRaisesRegex(RuntimeError, "declared package inputs are missing"):
                package.copy_runnable_tree(str(self.root / "package"), custody)

    def test_moved_unstaged_asset_is_enumerated_and_original_bundle_scope_is_retained(self):
        from scripts import build_validation_package as package
        sidecar = self.asset("sidecar", "data/gis/roads/ROAD_SOURCES.json", "data/shared/gis/ROAD_SOURCES.json")
        road = self.asset("road", "data/gis/roads/road.npy", "data/shared/gis/road.npy")
        unrelated = self.asset("other", "data/gis/landfills/other.csv", "data/shared/gis/other.csv")
        self.catalog(sidecar, road, unrelated)
        self.write(sidecar["path"], json.dumps({"licence": "cc-by-4.0"}))
        self.write(road["path"], "road bytes")
        self.write(unrelated["path"], "unrelated bytes")
        with patch.object(package, "ROOT", str(self.root)), patch.object(deposit, "ROOT", str(self.root)), \
                patch.object(package, "git", return_value=""), \
                patch.object(deposit, "reviewer_guides", return_value=set()):
            self.assertIn(road["path"], package.tracked_files())
            sidecars = package.Custody.__new__(package.Custody)._sidecars()
        self.assertEqual(sidecars[road["path"]], "cc-by-4.0")
        self.assertNotIn(unrelated["path"], sidecars)


if __name__ == "__main__":
    unittest.main()
