"""Canonical serialisation: the bytes a semantic table IS.

A table's identity is sha256 of this text, so the text must be reproducible anywhere: LF line
ends, UTF-8, header first (no '#' preamble - the prose that lived in preambles moves into
semantic_release.json as machine-readable fields), rows sorted by the declared primary key,
every value the source's own string. Nothing here formats a float."""
import csv
import hashlib
import io
import json

from pkinv.semantic import ROW_ID_SCHEME


def canonical_csv_text(fieldnames, rows, key):
    """The table as text, rows sorted by `key` (a tuple of column names)."""
    ordered = sorted(rows, key=lambda r: tuple(str(r[k]) for k in key))
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=list(fieldnames), lineterminator="\n",
                            extrasaction="raise")
    writer.writeheader()
    writer.writerows(ordered)
    return buf.getvalue()


def canonical_json_text(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def row_id(table, key_values):
    """A stable row identity: table + key values, release-independent, so a row keeps its id
    across releases while its value may change (a release diff is then a join on it)."""
    payload = ROW_ID_SCHEME + "\x1f" + table + "\x1f" + "\x1f".join(str(v) for v in key_values)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def with_row_ids(table, key, rows):
    for row in rows:
        row["result_row_id"] = row_id(table, [row[k] for k in key])
    return rows
