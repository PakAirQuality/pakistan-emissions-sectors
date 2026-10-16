import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from types import SimpleNamespace

from pkinv.assets import CATALOG
from pkinv.semantic import assets


class AssetCatalog(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="pakemis-assets-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "data/catalog").mkdir(parents=True)
        canonical = self.root / "data/power/canonical/fuel.csv"
        canonical.parent.mkdir(parents=True)
        canonical.write_text("Fuel,Record ID,Source row\nGas,kept-id,1\n")
        self.table = {"table_id": "activity.power.fuel", "source_path": "data/activity/power/fuel.csv",
                      "path": "data/power/canonical/fuel.csv", "row_count": 1,
                      "sha256": hashlib.sha256(canonical.read_bytes()).hexdigest(),
                      "columns": [{"field_id": "fuel", "name": "Fuel"}]}
        self.rows = [{"asset_id": self.table["table_id"], "legacy_path": self.table["source_path"],
                      "path": "data/power/activity/fuel.csv", "canonical_path": self.table["path"],
                      "owner_sector": "power", "purpose": "activity", "kind": "table",
                      "publication": "library", "license": "own-work-compilation", "title": "Fuel",
                      "description": "Shared fuel observations", "source_refs": "source-one;source-two",
                      "applies_to_sectors": "power;industry"}]

    def export(self):
        fields = list(dict.fromkeys(key for row in self.rows for key in row))
        with (self.root / CATALOG).open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(self.rows)
        with mock.patch.object(assets, "RUNTIME", {"method_registry": self.table["source_path"]}), \
             mock.patch.object(assets, "CLAIM_REGISTRIES", {}):
            return assets.build({"tables": [self.table]}, self.root)

    def test_tracked_canonical_identity_survives_source_path_move_and_absence(self):
        catalog = self.export()
        entry = catalog["assets"][0]
        self.assertEqual(entry["path"], self.table["path"])
        self.assertEqual(entry["table_id"], self.table["table_id"])
        self.assertEqual(entry["sha256"], self.table["sha256"])
        self.assertEqual(entry["sectors"], ["power", "industry"])
        self.assertEqual(entry["source_refs"], ["source-one", "source-two"])
        self.assertEqual(entry["filename"], "fuel.csv")
        self.assertEqual(entry["aliases"], ["input_activity_power_fuel.csv"])
        self.assertEqual(catalog["bindings"]["method_registry"], self.table["table_id"])

    def test_unknown_redistribution_is_metadata_only(self):
        source = self.root / "data/power/evidence/source.json"
        source.parent.mkdir(parents=True)
        source.write_text("{}")
        self.rows.append({"asset_id": "power.external", "legacy_path": "data/external.json",
                          "path": "data/power/evidence/source.json", "owner_sector": "power",
                          "purpose": "evidence", "publication": "library", "license": "not-established"})
        catalog = self.export()
        external = next(asset for asset in catalog["assets"] if asset["asset_id"] == "power.external")
        self.assertFalse(external["downloadable"])
        self.assertFalse(external["packaged"])

    def test_an_undeposited_internal_file_is_described_and_not_hashed(self):
        """rc68: a digest recorded because a file sat on the maintainer's disk made the
        contract differ in a clean rebuild; an undeposited data file carries no digest."""
        held = self.root / "data/shared/gis/cod_ab/boundaries.geojson.zip"
        held.parent.mkdir(parents=True)
        held.write_bytes(b"zip")
        self.rows.append({"asset_id": "gis.cod_ab", "legacy_path": "data/gis/cod_ab.zip",
                          "path": "data/shared/gis/cod_ab/boundaries.geojson.zip",
                          "owner_sector": "shared", "purpose": "gis", "publication": "internal",
                          "license": "not-established"})
        entry = next(a for a in self.export()["assets"] if a["asset_id"] == "gis.cod_ab")
        self.assertNotIn("sha256", entry)
        self.assertNotIn("bytes", entry)

    def test_altered_canonical_bytes_are_refused(self):
        (self.root / self.table["path"]).write_text("Fuel,Record ID,Source row\nCoal,kept-id,1\n")
        with self.assertRaisesRegex(ValueError, "differs from its catalog"):
            self.export()

    def test_method_provenance_resolves_binding_and_preserves_old_releases(self):
        from pakemis_query.functions import get_method
        from pakemis_query.models import MethodRequest

        release = SimpleNamespace(contract={}, product_digest=lambda path: "legacy-digest")
        engine = SimpleNamespace(release=release)
        rows = [{"method_id": "method-one", "category": "fuel", "equation": "a * b"}]
        with mock.patch("pakemis_query.functions.envelope", side_effect=lambda *args: args):
            old = get_method(engine, MethodRequest(), rows)
            release.contract["asset_catalog"] = self.export()
            new = get_method(engine, MethodRequest(), rows)
        self.assertEqual(old[4], new[4])
        self.assertEqual(old[6], {"tables": [{"path": "data/method_registry.csv", "sha256": "legacy-digest"}]})
        self.assertEqual(new[6], {"tables": [{"path": self.table["path"], "sha256": self.table["sha256"]}]})


if __name__ == "__main__":
    unittest.main()
