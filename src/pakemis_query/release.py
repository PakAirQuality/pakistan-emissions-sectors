"""Release: open a semantic release directory, verify every table's identity, expose the
contract. Nothing is served from a table whose bytes do not match the contract's digest."""
import csv
import hashlib
import io
import json
import os

from pakemis_query.errors import IdentityError


def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _canonical_text(columns, rows, key):
    ordered = sorted(rows, key=lambda r: tuple(str(r[k]) for k in key))
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=list(columns), lineterminator="\n")
    writer.writeheader()
    writer.writerows(ordered)
    return buf.getvalue()


class VerificationCache:
    """Share work within one startup audit; changed files never reuse a cached digest."""

    def __init__(self):
        self._digests = {}

    def _get(self, path, representation, calculate):
        stat = os.stat(path)
        key = (os.path.realpath(path), stat.st_dev, stat.st_ino, stat.st_size,
               stat.st_mtime_ns, stat.st_ctime_ns, representation)
        if key not in self._digests:
            self._digests[key] = calculate()
        return self._digests[key]

    def sha256_file(self, path):
        return self._get(path, "bytes", lambda: _sha256_file(path))

    def parquet_digest(self, path, table):
        shape = (tuple(table["columns"]), tuple(table["primary_key"]))
        return self._get(path, shape, lambda: Release._parquet_digest(path, table))


class Release:
    """`Release.open(directory)`: `directory` holds semantic_release.json and the tables;
    `manifest_path` (optional) is the release manifest, used only to report the commit."""

    def __init__(self, directory, contract, verified):
        self.directory = directory
        self.contract = contract
        self.verified = verified
        self.tables = dict(contract["dimensions"], **contract["facts"])
        self.defaults = contract["defaults"]
        self.release_id = contract["release"]["release_id"]
        self.version = contract["release"]["version"]
        self.limitations = {l["id"]: l for l in contract["known_limitations"]}
        self._dims = {}

    @classmethod
    def open(cls, directory, verify=True, manifest_path=None, verification_cache=None):
        with open(os.path.join(directory, "semantic_release.json"), encoding="utf-8") as handle:
            contract = json.load(handle)
        verified = {}
        cache = verification_cache or VerificationCache()
        if verify:
            for name, table in dict(contract["dimensions"], **contract["facts"]).items():
                csv_path = os.path.join(directory, os.path.basename(table["path"]))
                pq_path = os.path.join(directory, os.path.basename(table["parquet"]["path"]))
                present = []
                if os.path.exists(csv_path):
                    present.append((csv_path, cache.sha256_file(csv_path)))
                if os.path.exists(pq_path):
                    present.append((pq_path, cache.parquet_digest(pq_path, table)))
                if not present:
                    raise IdentityError("%s: neither the CSV nor the Parquet is present" % name)
                for path, digest in present:
                    if digest != table["sha256_csv"]:
                        raise IdentityError("%s: bytes do not match the contract (%s != %s)"
                                            % (path, digest[:12], table["sha256_csv"][:12]), table=name)
                verified[name] = table["sha256_csv"]
        release = cls(directory, contract, verified)
        release.commit = None
        if manifest_path and os.path.exists(manifest_path):
            with open(manifest_path, encoding="utf-8") as handle:
                release.commit = (json.load(handle).get("git") or {}).get("describes_commit")
        return release

    @staticmethod
    def _parquet_digest(path, table):
        import pyarrow as pa
        import pyarrow.parquet as pq
        source = pq.ParquetFile(path)
        if source.schema_arrow.names != table["columns"] or any(
                not pa.types.is_string(field.type) for field in source.schema_arrow):
            raise IdentityError("%s: Parquet columns or string types differ from the contract" % path)

        def digest(batches, check_order):
            result = hashlib.sha256()
            buffer = io.StringIO(newline="")
            writer = csv.DictWriter(buffer, fieldnames=table["columns"], lineterminator="\n")
            writer.writeheader()
            previous = None
            for batch in batches:
                if any(column.null_count for column in batch.columns):
                    raise IdentityError("%s: Parquet nulls cannot represent empty CSV strings" % path)
                for row in batch.to_pylist():
                    key = tuple(row[name] for name in table["primary_key"])
                    if check_order and previous is not None and key < previous:
                        return None
                    previous = key
                    writer.writerow(row)
                result.update(buffer.getvalue().encode("utf-8"))
                buffer.seek(0)
                buffer.truncate(0)
            result.update(buffer.getvalue().encode("utf-8"))
            return result.hexdigest()

        ordered = digest(source.iter_batches(batch_size=10000), True)
        if ordered is not None:
            return ordered
        # A valid representation may reorder records. Canonicalise it with a disk-capable
        # sort instead of materialising all monthly district dictionaries in Python.
        import duckdb
        connection = duckdb.connect(":memory:")
        try:
            connection.execute("SET memory_limit='128MB'")
            keys = ",".join('"' + name.replace('"', '""') + '"' for name in table["primary_key"])
            batches = connection.execute("SELECT * FROM read_parquet(?) ORDER BY " + keys,
                                         [str(path)]).fetch_record_batch(10000)
            return digest(batches, False)
        finally:
            connection.close()

    def table_path(self, name):
        """The Parquet when present (the engine's fast path), else the CSV."""
        table = self.tables[name]
        pq_path = os.path.join(self.directory, os.path.basename(table["parquet"]["path"]))
        if os.path.exists(pq_path):
            return pq_path, "parquet"
        return os.path.join(self.directory, os.path.basename(table["path"])), "csv"

    def dim(self, name):
        """A dimension table's rows, cached."""
        if name not in self._dims:
            path, kind = self.table_path(name)
            if kind == "parquet":
                import pyarrow.parquet as pq
                self._dims[name] = pq.read_table(path).to_pylist()
            else:
                with open(path, newline="", encoding="utf-8") as handle:
                    self._dims[name] = list(csv.DictReader(handle))
        return self._dims[name]

    def dim_values(self, name, column):
        return {r[column] for r in self.dim(name)}

    def product_digest(self, path):
        for p in self.contract["products"]:
            if p["path"] == path:
                return p["sha256"]
        return None

    def context(self, request_fields):
        """The context bar: release identity beside the request's basis, configuration, GWP,
        geography and the LULUCF status - the six things that stop 'Pakistan's emissions in
        2024' from silently mixing a calendar and a fiscal year."""
        rel = self.contract["release"]
        return {"release": self.release_id, "version": self.version, "commit": self.commit,
                "reporting_period": rel.get("reporting_period"),
                "basis": request_fields.get("basis"), "periods": request_fields.get("periods"),
                "configuration_id": request_fields.get("configuration_id"),
                "gwp_basis": request_fields.get("gwp_basis"),
                "gwp_factors": rel["gwp_bases"]["factors"].get(request_fields.get("gwp_basis"), {}),
                "geography_level": request_fields.get("geography_level"),
                "geography_ids": request_fields.get("geography_ids"),
                "spatial_view": request_fields.get("spatial_view"),
                "lulucf": rel["lulucf"]}
