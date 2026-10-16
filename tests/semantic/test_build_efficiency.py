"""Build caching must preserve scientific bytes and dependency/identity checks."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pakemis_query.errors import IdentityError
from pakemis_query.release import Release, VerificationCache
from pkinv.semantic import build, sources


class BuildEfficiency(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="pakemis-semantic-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def test_source_cache_is_immutable_and_tracks_cached_reads(self):
        (self.root / "a.csv").write_text("key,value\na,1.00\n", encoding="utf-8")
        (self.root / "b.csv").write_text("key,value\nb,2.00\n", encoding="utf-8")
        original, reads = sources.read_rows, []

        def read(path, **kwargs):
            reads.append(path)
            return original(path, **kwargs)

        with mock.patch.object(sources, "ROOT", str(self.root)), \
             mock.patch.object(sources, "registry", return_value={"a": "a.csv", "b": "b.csv"}), \
             mock.patch.object(sources, "read_rows", side_effect=read):
            source = sources.Sources()
            with source.track() as first:
                rows = source.rows("a")
                source.rows("b")
            with source.track() as second:
                self.assertIs(source.rows("a"), rows)
            self.assertEqual(first, {"a", "b"})
            self.assertEqual(second, {"a"})
            self.assertEqual(len(reads), 2)
            self.assertEqual([d["name"] for d in source.digests(second)], ["a"])
            with self.assertRaises(TypeError):
                rows[0]["value"] = "9"

    def test_source_dimensions_read_and_hash_canonical_inputs_without_staging(self):
        data = self.root / "data"
        (data / "canonical").mkdir(parents=True)
        (data / "canonical_tables.csv").write_text("source_path\ndata/input.csv\n")
        payload = b"Readable value,Record ID,Source row\n1.00,example-id,1\n"
        (data / "canonical/input.csv").write_bytes(payload)
        table = {"table_id": "parameters.input", "source_path": "data/input.csv",
                 "path": "data/canonical/input.csv", "row_count": 1,
                 "columns": [{"field_id": "value", "name": "Readable value"}],
                 "sha256": hashlib.sha256(payload).hexdigest(), "source_sha256": "unused"}
        (data / "canonical/catalog.json").write_text(json.dumps(
            {"schema_version": "pkinv.canonical-inputs/v1", "tables": [table]}))
        with mock.patch.object(sources, "ROOT", str(self.root)), \
             mock.patch.object(sources, "registry", return_value={"a": "data/input.csv"}):
            source = sources.Sources()
            self.assertEqual(dict(source.rows("a")[0]), {"value": "1.00"})
            self.assertEqual(source.digests(), [{"name": "a", "path": table["path"],
                                                "sha256": table["sha256"]}])

    def test_unchanged_build_keeps_csv_and_parquet_mtimes(self):
        table, text = build._table("example", "fact", ("key", "value"), ("key",),
                                  [{"key": "a", "value": "1.00"}], {"rule": "sum"})

        def generate(consume):
            consume("example", table, text)
            return {"example": table}, {}, "{}\n"

        with mock.patch.object(build, "OUT_DIR", str(self.root)), \
             mock.patch.object(build, "build_all", side_effect=generate):
            self.assertEqual(build.main([]), 0)
            before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.root.iterdir()}
            self.assertEqual(build.main([]), 0)
            self.assertEqual(before, {p.name: (p.read_bytes(), p.stat().st_mtime_ns)
                                      for p in self.root.iterdir()})
            self.assertEqual(build.main(["--check"]), 0)
            (self.root / "example.csv").write_text("tampered\n")
            self.assertEqual(build.main(["--check"]), 1)
            self.assertEqual(build.main([]), 0)
            self.assertEqual((self.root / "example.csv").read_text(), text)

    def test_a_twin_in_another_layout_is_rewritten(self):
        """rc68: single-row-group twins from an older writer matched cell for cell and were
        kept, so the release's twin sizes differed from a clean rebuild's."""
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError:
            self.skipTest("pyarrow not installed")
        rows = [{"key": "k%05d" % i, "value": "1"} for i in range(10001)]
        table, text = build._table("example", "fact", ("key", "value"), ("key",), rows,
                                   {"rule": "sum"})
        import csv
        import io
        parquet = self.root / "example.parquet"
        schema = pa.schema([(name, pa.string()) for name in table["columns"]])
        same_cells = list(csv.DictReader(io.StringIO(text)))
        pq.write_table(pa.Table.from_pylist(same_cells, schema=schema), parquet)  # one row group
        self.assertFalse(build._parquet_matches(parquet, table, text))
        build._write_parquet(str(parquet), table["columns"], text)
        self.assertEqual(pq.ParquetFile(parquet).metadata.num_row_groups, 2)
        self.assertTrue(build._parquet_matches(parquet, table, text))

    def test_rebuild_repairs_corrupted_parquet_without_rewriting_csv(self):
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError:
            self.skipTest("pyarrow not installed")
        table, text = build._table("example", "fact", ("key", "value"), ("key",),
                                  [{"key": "a", "value": "1.00"}], {"rule": "sum"})

        def generate(consume):
            consume("example", table, text)
            return {"example": table}, {}, "{}\n"

        with mock.patch.object(build, "OUT_DIR", str(self.root)), \
             mock.patch.object(build, "build_all", side_effect=generate):
            build.main([])
            csv_time = (self.root / "example.csv").stat().st_mtime_ns
            parquet = self.root / "example.parquet"
            for corrupt in (lambda: pq.write_table(pa.table({"key": ["a"], "value": ["9"]}), parquet),
                            lambda: parquet.write_bytes(b"not parquet")):
                corrupt()
                self.assertEqual(build.main(["--check"]), 1)
                self.assertEqual(build.main([]), 0)
                self.assertTrue(build._parquet_matches(parquet, table, text))
                self.assertEqual((self.root / "example.csv").stat().st_mtime_ns, csv_time)

    def test_csv_only_rebuild_removes_stale_parquet(self):
        table, text = build._table("example", "fact", ("key", "value"), ("key",),
                                  [{"key": "a", "value": "1.00"}], {"rule": "sum"})
        (self.root / "example.csv").write_text("stale\n")
        (self.root / "example.parquet").write_bytes(b"stale optional representation")

        def generate(consume):
            consume("example", table, text)
            return {"example": table}, {}, "{}\n"

        with mock.patch.object(build, "OUT_DIR", str(self.root)), \
             mock.patch.object(build, "build_all", side_effect=generate), \
             mock.patch.object(build, "_write_parquet", return_value=False):
            self.assertEqual(build.main([]), 0)
            self.assertEqual((self.root / "example.csv").read_text(), text)
            self.assertFalse((self.root / "example.parquet").exists())

    def release_fixture(self):
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError:
            self.skipTest("pyarrow not installed")
        text = "key,value\na,1.00\n"
        (self.root / "example.csv").write_text(text)
        pq.write_table(pa.table({"key": ["a"], "value": ["1.00"]}), self.root / "example.parquet")
        table = {"path": "example.csv", "parquet": {"path": "example.parquet"},
                 "columns": ["key", "value"], "primary_key": ["key"],
                 "sha256_csv": hashlib.sha256(text.encode()).hexdigest()}
        contract = {"release": {"release_id": "test", "version": "test"}, "defaults": {},
                    "known_limitations": [], "dimensions": {}, "facts": {"example": table}}
        (self.root / "semantic_release.json").write_text(json.dumps(contract))
        return pa, pq

    def test_valid_csv_does_not_mask_corrupted_parquet(self):
        pa, pq = self.release_fixture()
        cache = VerificationCache()
        release = Release.open(str(self.root), verification_cache=cache)
        self.assertEqual(release.table_path("example")[1], "parquet")
        pq.write_table(pa.table({"key": ["a"], "value": ["9.00"]}), self.root / "example.parquet")
        with self.assertRaisesRegex(IdentityError, "parquet"):
            Release.open(str(self.root), verification_cache=cache)

    def test_csv_only_and_parquet_only_releases_agree(self):
        self.release_fixture()
        expected = Release.open(str(self.root)).verified
        held = (self.root / "example.csv").read_bytes()
        (self.root / "example.csv").unlink()
        self.assertEqual(Release.open(str(self.root)).verified, expected)
        (self.root / "example.csv").write_bytes(held)
        (self.root / "example.parquet").unlink()
        self.assertEqual(Release.open(str(self.root)).verified, expected)


if __name__ == "__main__":
    unittest.main()
