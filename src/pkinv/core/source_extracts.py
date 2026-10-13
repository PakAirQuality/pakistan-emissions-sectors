"""Materialized source tables: readable CSV values, with lossless Python type metadata.

Normal model calls read the verified extract. Ingestion calls ``__wrapped__`` to
read the held workbook, so extraction is explicit and never a runtime fallback.
The schema records types (including None versus empty text), not a second value copy.
"""
from __future__ import annotations

import csv
import functools
import hashlib
import inspect
import io
import json
import os
from pathlib import Path

from pkinv.paths import ROOT
from pkinv.assets import resolve, legacy_path
from pkinv.core import documents

DIRECTORY = "data/extracted/unfccc"
SCHEMA = "pkinv.source_extract/v1"


def _sha(payload):
    return hashlib.sha256(payload).hexdigest()


def producer_fingerprint(parser):
    """Include parser helpers and serialization code so changed logic needs ingestion."""
    digest = hashlib.sha256()
    for filename in (inspect.getsourcefile(parser), __file__):
        digest.update(Path(filename).read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _flatten(record, prefix=""):
    result = {}
    for field, value in record.items():
        key = prefix + field
        if isinstance(value, dict):
            result.update(_flatten(value, key + "."))
        else:
            result[key] = value
    return result


def _unflatten(row):
    result = {}
    for field, value in row.items():
        target = result
        parts = field.split(".")
        for part in parts[:-1]:
            target = target.setdefault(part, {})
        target[parts[-1]] = value
    return result


def _type(value):
    if value is None:
        return "n"
    if isinstance(value, bool):
        return "b"
    if isinstance(value, int):
        return "i"
    if isinstance(value, float):
        return "f"
    if isinstance(value, str):
        return "s"
    raise TypeError("unsupported source value type: %s" % type(value).__name__)


def serialize(name, value):
    """Return schema and CSV payloads without rounding or conflating absent values."""
    payloads = {}

    def encode(value, suffix):
        if isinstance(value, tuple):
            return {"kind": "tuple", "items": [encode(v, suffix + "_%d" % i)
                                                  for i, v in enumerate(value)]}
        if isinstance(value, list):
            kind, rows = "records", value
        elif isinstance(value, dict) and value and all(isinstance(v, dict) for v in value.values()):
            kind = "mapping"
            if any("source_key" in row for row in value.values()):
                raise ValueError("source_key is reserved for the source's category identity")
            rows = [{"source_key": key, **row} for key, row in value.items()]
        elif isinstance(value, dict):
            kind, rows = "record", [value]
        else:
            raise TypeError("extract result must contain records")
        flat = [_flatten(row) for row in rows]
        columns = list(dict.fromkeys(key for row in flat for key in row))
        types = ["".join(_type(row[c]) if c in row else "a" for c in columns) for row in flat]
        text = io.StringIO(newline="")
        writer = csv.DictWriter(text, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(flat)
        path = name + suffix + ".csv"
        payload = text.getvalue().encode("utf-8")
        payloads[path] = payload
        node = {"kind": kind, "path": path, "columns": columns,
                "types": types, "sha256": _sha(payload)}
        if kind == "mapping":
            node["key_column"] = "source_key"
        return node

    return encode(value, ""), payloads


def deserialize(node, directory):
    if node["kind"] == "tuple":
        return tuple(deserialize(child, directory) for child in node["items"])
    path = Path(resolve(Path(directory) / node["path"]))
    from pkinv.activity.store import read_rows, table_for_source
    try:
        relative = legacy_path(path, root=ROOT)
    except ValueError:
        relative = ""
    if relative.startswith(DIRECTORY + "/"):
        # The typed receipt names the same source bytes that produced the
        # canonical table; model runtime needs no staging CSV value copy.
        source_digest = table_for_source(path.resolve())["source_sha256"]
    else:
        source_digest = _sha(path.read_bytes())
    if source_digest != node["sha256"]:
        raise ValueError("source extract digest mismatch: %s" % path)
    rows = read_rows(str(path), comments=False)
    if len(rows) != len(node["types"]):
        raise ValueError("source extract row count mismatch: %s" % path)
    decoded = []
    for row, types in zip(rows, node["types"]):
        values = {}
        for key, tag in zip(node["columns"], types):
            text = row[key]
            if tag == "a":
                continue
            values[key] = (None if tag == "n" else int(text) if tag == "i"
                           else float(text) if tag == "f" else text == "True" if tag == "b"
                           else text)
        decoded.append(_unflatten(values))
    if node["kind"] == "record":
        return decoded[0]
    if node["kind"] == "mapping":
        return {row.pop(node["key_column"]): row for row in decoded}
    return decoded


def materialized(name):
    """Decorate a held-document parser; alternate explicit paths still parse directly."""
    def decorate(parser):
        signature = inspect.signature(parser)

        @functools.wraps(parser)
        def read(*args, **kwargs):
            bound = signature.bind(*args, **kwargs)
            requested = bound.arguments.get("path")
            source = parser.__globals__["CRT_SOURCE"]
            if requested and os.path.abspath(requested) != os.path.abspath(source):
                return parser(*args, **kwargs)
            manifest_path = Path(resolve(Path(ROOT) / DIRECTORY / (name + ".json")))
            if not manifest_path.exists():
                raise FileNotFoundError("missing source extract %s; run python3 "
                                        "scripts/ingest_official_reporting.py" % name)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("schema") != SCHEMA:
                raise ValueError("unsupported source extract schema: %s" % name)
            if manifest.get("producer_sha256") != producer_fingerprint(parser):
                raise ValueError("source parser changed for %s; rerun python3 "
                                 "scripts/ingest_official_reporting.py" % name)
            if documents.digest(source, quiet=True) != manifest["source_sha256"]:
                raise ValueError("stale source extract %s; rerun ingestion" % name)
            return deserialize(manifest["result"], manifest_path.parent)

        read.extract_name = name
        return read
    return decorate


def build_extract(parser, check=False, root=ROOT):
    raw = parser.__wrapped__
    source = raw.__globals__["CRT_SOURCE"]
    from pkinv.activity.store import staging_inputs
    with staging_inputs():
        result = raw()
    tree, payloads = serialize(parser.extract_name, result)
    manifest = {"schema": SCHEMA, "name": parser.extract_name,
                "source": os.path.relpath(source, root),
                "source_sha256": documents.digest(source, quiet=True),
                "producer": raw.__module__ + "." + raw.__name__,
                "producer_sha256": producer_fingerprint(raw),
                "result": tree}
    payloads[parser.extract_name + ".json"] = (json.dumps(
        manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    directory = Path(root) / DIRECTORY
    changed = []
    for name, payload in payloads.items():
        path = Path(resolve(directory / name, root=root))
        if path.exists() and path.read_bytes() == payload:
            continue
        changed.append(name)
        if not check:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(path.suffix + ".tmp")
            temporary.write_bytes(payload)
            temporary.replace(path)
    return changed
