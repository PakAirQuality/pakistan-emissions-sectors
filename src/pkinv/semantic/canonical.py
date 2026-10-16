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


def canonical_csv_external(fieldnames, rows, key, table):
    """Canonical CSV with a bounded-memory disk sort for large generated facts."""
    import os
    import sqlite3
    import tempfile
    fd, path = tempfile.mkstemp(prefix="pakemis-semantic-sort-", suffix=".sqlite")
    os.close(fd)
    connection = sqlite3.connect(path)
    try:
        columns = ["k%d" % index for index in range(len(key))]
        connection.execute("PRAGMA journal_mode=OFF")
        connection.execute("PRAGMA cache_size=-8192")
        connection.execute("CREATE TABLE records (%s, payload TEXT)" %
                           ",".join(name + " TEXT" for name in columns))
        insert = "INSERT INTO records VALUES (%s)" % ",".join("?" for _ in range(len(key) + 1))
        batch, count = [], 0
        for source in rows:
            row = dict(source)
            row["result_row_id"] = row_id(table, [row[k] for k in key])
            extra = set(row) - set(fieldnames)
            if extra:
                raise ValueError("%s: undeclared columns %s" % (table, sorted(extra)))
            batch.append(tuple(str(row[k]) for k in key) + (json.dumps(row, ensure_ascii=False),))
            count += 1
            if len(batch) == 10000:
                connection.executemany(insert, batch)
                batch.clear()
        if batch:
            connection.executemany(insert, batch)
        connection.commit()
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n", extrasaction="raise")
        writer.writeheader()
        for (payload,) in connection.execute("SELECT payload FROM records ORDER BY " + ",".join(columns)):
            writer.writerow(json.loads(payload))
        return count, output.getvalue()
    finally:
        connection.close()
        os.unlink(path)


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
