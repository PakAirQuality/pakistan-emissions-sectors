"""Read the same lossless input tables that are offered as CSV downloads.

Scientific code uses stable field IDs; the CSV header uses readable names. The
catalog is the only translation between them. Values and source order are never
changed here. A missing canonical table is an error, not permission to go back to
the staging extract. Ingest scripts deliberately continue using core.io.
"""
from __future__ import annotations

import csv
import copy
from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import io
import json
import os
import sys
from pathlib import Path

from pkinv.paths import ROOT
from pkinv.assets import resolve, legacy_path, catalog as asset_catalog

SCHEMA_VERSION = "pkinv.canonical-inputs/v1"
CATALOG_PATH = "data/canonical/catalog.json"
REGISTRY_PATH = "data/canonical_tables.csv"
LINEAGE_FIELDS = ("Record ID", "Source row")


class CanonicalInputError(ValueError):
    """A canonical input is absent, stale, or violates its declared contract."""


def _signature(path):
    stat = path.stat()
    return stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size


class ActivityStore:
    def __init__(self, root=ROOT):
        self.root = Path(root).resolve()
        self._catalog_signature = None
        self._tables = {}
        self._sources = {}
        self._cache = {}
        self._source_checks = {}

    def _load(self):
        path = Path(resolve(self.root / CATALOG_PATH, root=self.root))
        try:
            signature = _signature(path)
        except FileNotFoundError:
            raise CanonicalInputError(
                "Canonical inputs are missing. Run python -m pkinv.activity.build "
                "before running inventory calculations.") from None
        if signature == self._catalog_signature:
            return
        catalog = json.loads(path.read_text(encoding="utf-8"))
        if catalog.get("schema_version") != SCHEMA_VERSION:
            raise CanonicalInputError("Unsupported canonical input schema in %s" % path)
        tables = catalog["tables"]
        self._tables = {table["table_id"]: table for table in tables}
        self._sources = {table["source_path"]: table for table in tables}
        if len(self._tables) != len(tables) or len(self._sources) != len(tables):
            raise CanonicalInputError("Duplicate table or source in canonical catalog")
        for table in tables:
            relative = Path(table["path"])
            if relative.is_absolute() or ".." in relative.parts:
                raise CanonicalInputError("Canonical table path escapes its root")
        self._catalog_signature = signature
        self._cache.clear()
        self._source_checks.clear()

    def _check_source(self, table):
        # A canonical-only deployment does not need the staging tree. Where a
        # staging extract is held, however, a direct sector command must not use
        # yesterday's canonical snapshot after today's source edit.
        source = Path(resolve(self.root / table["source_path"], root=self.root))
        if not source.exists():
            return
        signature = _signature(source)
        if self._source_checks.get(table["table_id"]) == signature:
            return
        if hashlib.sha256(source.read_bytes()).hexdigest() != table["source_sha256"]:
            raise CanonicalInputError(
                "%s changed since canonical inputs were built; run python -m pkinv.activity.build"
                % table["source_path"])
        self._source_checks[table["table_id"]] = signature

    @property
    def tables(self):
        self._load()
        return tuple(copy.deepcopy(table) for table in self._tables.values())

    def table_for_source(self, source_path):
        """Independent metadata for validating a source's typed extraction receipt."""
        self._load()
        path = Path(source_path)
        relative = legacy_path(path, root=self.root)
        try:
            return copy.deepcopy(self._sources[relative])
        except KeyError:
            raise CanonicalInputError("%s has no canonical input declaration" % relative) from None

    def _rows(self, table):
        sys.audit("pkinv.canonical.read", table["table_id"], table["path"])
        self._check_source(table)
        path = self.root / table["path"]
        try:
            signature = _signature(path)
        except FileNotFoundError:
            raise CanonicalInputError("%s is missing; rebuild canonical inputs" % path) from None
        cached = self._cache.get(table["table_id"])
        if cached and cached[0] == signature:
            return cached[1]
        payload = path.read_bytes()
        if hashlib.sha256(payload).hexdigest() != table["sha256"]:
            raise CanonicalInputError("%s differs from the canonical catalog; rebuild inputs" % path)
        reader = csv.DictReader(io.StringIO(payload.decode("utf-8"), newline=""))
        fields = [column["name"] for column in table["columns"]] + list(LINEAGE_FIELDS)
        if reader.fieldnames != fields:
            raise CanonicalInputError("%s has an unexpected canonical header" % path)
        rows = list(reader)
        if len(rows) != table["row_count"]:
            raise CanonicalInputError("%s has an unexpected row count" % path)
        ids = set()
        for ordinal, row in enumerate(rows, 1):
            if None in row or any(value is None for value in row.values()):
                raise CanonicalInputError("%s row %d is malformed" % (path, ordinal))
            if row["Source row"] != str(ordinal) or row["Record ID"] in ids:
                raise CanonicalInputError("%s has invalid source row identity" % path)
            ids.add(row["Record ID"])
        self._cache[table["table_id"]] = (signature, rows)
        return rows

    def rows(self, table_id):
        """Readable rows, including lineage, isolated from callers' mutations."""
        self._load()
        try:
            table = self._tables[table_id]
        except KeyError:
            raise CanonicalInputError("Unknown canonical input table %r" % table_id) from None
        return [dict(row) for row in self._rows(table)]

    def legacy_rows(self, source_path):
        """The original scientific field IDs, backed exclusively by canonical CSV."""
        self._load()
        path = Path(source_path)
        relative = legacy_path(path, root=self.root)
        try:
            table = self._sources[relative]
        except KeyError:
            raise CanonicalInputError("%s has no canonical input declaration" % relative) from None
        return [{column["field_id"]: row[column["name"]] for column in table["columns"]}
                for row in self._rows(table)]


_STORES = {}
_REGISTRIES = {}
_STAGING = ContextVar("pkinv_ingesting_staging", default=False)


@contextmanager
def staging_inputs():
    """Explicit ingest-only boundary for producers using shared scientific helpers.

    This is never selected by a missing file, environment variable, or model
    fallback. Source producers enter it deliberately before materialization.
    """
    token = _STAGING.set(True)
    try:
        yield
    finally:
        _STAGING.reset(token)


def _managed(path, root):
    """Register lookup never needs a built catalog, so absence fails closed."""
    root = Path(root).resolve()
    absolute = Path(path).resolve()
    try:
        relative = absolute.relative_to(root).as_posix()
    except ValueError:
        return False
    relative = legacy_path(absolute, root=root)
    registry = Path(resolve(root / REGISTRY_PATH, root=root))
    if not registry.exists():
        return False
    signature = _signature(registry)
    cached = _REGISTRIES.get(root)
    if not cached or cached[0] != signature:
        with registry.open(newline="", encoding="utf-8") as handle:
            sources = {row["source_path"] for row in csv.DictReader(handle)}
        _REGISTRIES[root] = signature, sources
    if relative in _REGISTRIES[root][1]:
        return True
    # Declared metadata/templates are intentionally not model tables. New CSVs
    # in managed source folders still cannot silently bypass the contract.
    from pkinv.assets import _index
    declared = _index(root)[1].get(relative)
    if declared:
        return False
    return (relative.startswith(("data/activity/", "data/nfdc/", "data/extracted/unfccc/",
                                 "data/sectors/", "data/shared/")) and relative.endswith(".csv"))


def read_rows(path, comments=True, strict=True, *, root=ROOT):
    """Runtime CSV reader: managed inputs use canonical tables, other files use core IO."""
    from pkinv.core.io import read_rows as read_staging_rows
    if _STAGING.get() or not _managed(path, root):
        return read_staging_rows(resolve(path, root=root), comments=comments, strict=strict)
    key = str(Path(root).resolve())
    store = _STORES.setdefault(key, ActivityStore(key))
    return store.legacy_rows(Path(path).resolve())


def clear_cache():
    """Release cached rows after a build or between isolated test fixtures."""
    _STORES.clear()
    _REGISTRIES.clear()


def table_for_source(path, *, root=ROOT):
    """Lookup through the same process-local store used by runtime readers."""
    key = str(Path(root).resolve())
    return _STORES.setdefault(key, ActivityStore(key)).table_for_source(path)


def input_exists(path, *, root=ROOT):
    """Availability checks honor the canonical boundary, including optional inputs.

    A declared input with a missing canonical artifact is broken, not absent
    evidence that a model may silently replace with a fallback.
    """
    if _STAGING.get() or not _managed(path, root):
        return os.path.exists(resolve(path, root=root))
    table = table_for_source(Path(path).resolve(), root=root)
    sys.audit("pkinv.canonical.read", table["table_id"], table["path"])
    if not (Path(root) / table["path"]).is_file():
        raise CanonicalInputError("%s is missing; rebuild canonical inputs" % table["path"])
    return True
