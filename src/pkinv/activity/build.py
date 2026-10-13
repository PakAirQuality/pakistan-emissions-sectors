"""Build lossless, readable canonical inputs from verified source extracts.

Unlike activity.publish, this stage never selects measures, drops blank rows, or
combines dimensions. Every staging field survives under a registered readable
heading. Both model adapters and downloads read its output. Modelled waste flows
remain a downstream result and are deliberately absent from this input catalog.

Run ``python -m pkinv.activity.build``; ``--check`` compares without writing.
Writes: data/canonical/*.csv data/canonical/catalog.json
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile

from pkinv.activity.store import CATALOG_PATH, LINEAGE_FIELDS, REGISTRY_PATH, SCHEMA_VERSION
from pkinv.core.io import MalformedRow
from pkinv.paths import ROOT
from pkinv.assets import resolve, catalog as asset_catalog

COLUMNS_PATH = "data/canonical_columns.csv"


def _sha(payload):
    return hashlib.sha256(payload).hexdigest()


def declarations(root=ROOT):
    root = Path(root)
    with Path(resolve(root / REGISTRY_PATH, root=root)).open(newline="", encoding="utf-8") as handle:
        tables = list(csv.DictReader(handle))
    with Path(resolve(root / COLUMNS_PATH, root=root)).open(newline="", encoding="utf-8") as handle:
        columns = list(csv.DictReader(handle))
    by_table = {}
    for column in columns:
        by_table.setdefault(column["table_id"], []).append(
            {"field_id": column["field_id"], "name": column["name"],
             "storage_type": column.get("storage_type") or "string",
             "unit": column.get("unit") or ""})
    seen_ids, seen_sources, seen_paths = set(), set(), set()
    for table in tables:
        for field, seen in (("table_id", seen_ids), ("source_path", seen_sources), ("path", seen_paths)):
            if table[field] in seen:
                raise ValueError("Duplicate canonical %s: %s" % (field, table[field]))
            seen.add(table[field])
        for field in ("path", "source_path"):
            relative = Path(table[field])
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("Invalid canonical %s: %s" % (field, relative))
        if not table["source_path"].startswith("data/") or table["source_path"].startswith("data/canonical/"):
            raise ValueError("Canonical inputs may only depend on source-side data")
        if not (table["path"].startswith("data/canonical/") or
                (table["path"].startswith(("data/sectors/", "data/shared/")) and "/canonical/" in table["path"])):
            raise ValueError("Canonical outputs must stay under data/canonical/")
        table["columns"] = by_table.pop(table["table_id"], [])
        fields = [column["field_id"] for column in table["columns"]]
        names = [column["name"] for column in table["columns"]]
        if not fields or len(set(fields)) != len(fields) or len(set(names + list(LINEAGE_FIELDS))) != len(names) + 2:
            raise ValueError("Invalid or ambiguous columns for %s" % table["table_id"])
        if any(column["storage_type"] != "string" for column in table["columns"]):
            raise ValueError("Canonical source values must retain string storage")
    if by_table:
        raise ValueError("Columns declare unknown canonical tables: %s" % sorted(by_table))
    for asset in asset_catalog(root):
        if asset["canonical_path"] and asset["legacy_path"] not in seen_sources:
            raise ValueError("%s has no canonical table declaration" % asset["asset_id"])
    for directory in ("data/activity", "data/nfdc", "data/extracted/unfccc"):
        for source in (root / directory).rglob("*.csv"):
            if source.relative_to(root).as_posix() not in seen_sources:
                raise ValueError("%s has no canonical table declaration" % source)
    return tables


def _render(root, table, payload):
    text = payload.decode("utf-8-sig")
    reader = csv.DictReader(line for line in io.StringIO(text, newline="") if not line.startswith("#"))
    expected = [column["field_id"] for column in table["columns"]]
    if reader.fieldnames != expected:
        raise ValueError("%s header changed; update data/canonical_columns.csv explicitly" % table["source_path"])
    output = io.StringIO(newline="")
    names = [column["name"] for column in table["columns"]]
    writer = csv.DictWriter(output, fieldnames=names + list(LINEAGE_FIELDS), lineterminator="\n")
    writer.writeheader()
    count = 0
    for count, row in enumerate(reader, 1):
        if None in row or any(value is None for value in row.values()):
            raise MalformedRow("%s row %d has a different field count from its header" % (table["source_path"], count + 1))
        readable = {column["name"]: row[column["field_id"]] for column in table["columns"]}
        # Source ordinals deliberately preserve the identity used by the legacy
        # activity projections; this is provenance, not a guessed natural key.
        readable["Record ID"] = _sha((SCHEMA_VERSION + "\x1f" + table["table_id"] + "\x1f" + str(count)).encode())[:24]
        readable["Source row"] = str(count)
        writer.writerow(readable)
    return output.getvalue().encode("utf-8"), count


def _write_or_check(path, payload, check):
    if path.exists() and path.read_bytes() == payload:
        return False
    if check:
        return True
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return True


def build(root=ROOT, check=False):
    """Return changed paths; unchanged files keep their mtimes. Check never writes."""
    root = Path(root)
    tables = declarations(root)
    builder_sha = _sha(Path(__file__).read_bytes())
    previous_path = Path(resolve(root / CATALOG_PATH, root=root))
    previous = json.loads(previous_path.read_text()) if previous_path.exists() else {}
    reusable = {table["table_id"]: table for table in previous.get("tables", [])}
    if previous.get("builder_sha256") != builder_sha:
        reusable = {}
    changed, entries = [], []
    for table in tables:
        source_payload = Path(resolve(root / table["source_path"], root=root)).read_bytes()
        source_sha = _sha(source_payload)
        prior = reusable.get(table["table_id"])
        target = root / table["path"]
        # Hash-based reuse keeps everyday no-op builds inexpensive without
        # trusting mtimes or returning a corrupted cached CSV.
        if (not check and prior and prior["source_sha256"] == source_sha
                and all(prior.get(key) == value for key, value in table.items())
                and target.exists() and _sha(target.read_bytes()) == prior["sha256"]):
            entries.append(prior)
            continue
        payload, count = _render(root, table, source_payload)
        if _write_or_check(root / table["path"], payload, check):
            changed.append(table["path"])
        entries.append(dict(table, primary_key=["Record ID"], row_count=count, sha256=_sha(payload),
                            source_sha256=source_sha))
    catalog = {"schema_version": SCHEMA_VERSION,
               "builder_sha256": builder_sha,
               "record_id_scheme": "table_id and 1-based source ordinal; source order preserved",
               "tables": entries}
    payload = (json.dumps(catalog, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    if _write_or_check(previous_path, payload, check):
        changed.append(previous_path.relative_to(root).as_posix())
    return changed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify without writing")
    parser.add_argument("--root", default=ROOT)
    args = parser.parse_args(argv)
    changed = build(args.root, args.check)
    if args.check and changed:
        print("Canonical inputs need rebuilding:\n  " + "\n  ".join(changed))
        return 1
    print("Canonical inputs: %d %s" % (len(changed), "differences" if args.check else "files updated"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
