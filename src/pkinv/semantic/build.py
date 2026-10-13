"""The "Semantic release" phase: python3 -m pkinv.semantic.build [--check]

Writes outputs/semantic/<table>.csv (the identity: canonical text), <table>.parquet (an
all-string representation of that text, so a holder of the Parquet can re-serialise and verify),
and semantic_release.json. --check re-derives everything and exits 1 on any byte difference."""

from pkinv.assets import asset_path
import os
import sys
import tempfile

from pkinv.semantic import OUT_DIR
from pkinv.semantic.canonical import canonical_csv_text, canonical_json_text, sha256_text, with_row_ids
from pkinv.semantic.dimensions import DIMENSIONS
from pkinv.semantic.downloads import build as build_downloads
from pkinv.semantic.facts import FACTS
from pkinv.semantic.release_json import build as build_release, completeness_limitations
from pkinv.semantic.sources import Sources


def _table(name, kind, fieldnames, key, rows, aggregation):
    rows = [dict(r) for r in rows]
    id_column = aggregation.get("id_column")
    if id_column:
        # rc59: a table whose rows already carry a content-derived id (the seventeen readable
        # activity tables' Record ID, minted by pkinv.activity.present from the technical key)
        # declares it, and gets NO prepended result_row_id - one id per row, and it is the
        # one the reader can join on. The declared column must be the key and unique.
        if tuple(key) != (id_column,):
            raise ValueError("%s: id_column %r must be the table's primary key %r" % (name, id_column, key))
        if id_column not in fieldnames:
            raise ValueError("%s: id_column %r is not a column" % (name, id_column))
        ids = [r[id_column] for r in rows]
        if len(ids) != len(set(ids)):
            raise ValueError("%s: id_column %r is not unique" % (name, id_column))
        fields = tuple(f for f in fieldnames if f != "result_row_id")
    else:
        fields = ("result_row_id",) + tuple(f for f in fieldnames if f != "result_row_id")
        rows = with_row_ids(name, key, rows)
    text = canonical_csv_text(fields, rows, key)
    return {"kind": kind, "path": "outputs/semantic/%s.csv" % name,
            "parquet": {"path": "outputs/semantic/%s.parquet" % name,
                        "representation_of": "outputs/semantic/%s.csv" % name, "hashed": False,
                        "note": "all-string Parquet written from the CSV text; the CSV is the identity"},
            "sha256_csv": sha256_text(text), "rows": len(rows), "primary_key": list(key),
            "columns": list(fields), "aggregation": aggregation}, text


def _write_parquet(path, fieldnames, text):
    import csv
    import io
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError:              # the twin is a representation; its absence is not a failure
        return False
    reader = csv.DictReader(io.StringIO(text))
    columns = {f: [] for f in fieldnames}
    for row in reader:
        for f in fieldnames:
            columns[f].append(row[f])
    table = pa.table({f: pa.array(columns[f], type=pa.string()) for f in fieldnames})
    fd, temporary = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".parquet")
    os.close(fd)
    try:
        pq.write_table(table, temporary, compression="snappy")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return True


def _parquet_matches(path, table, text):
    """An unchanged CSV may still have a damaged or stale optional representation."""
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError:
        return None
    try:
        held = pq.read_table(path)
        if held.column_names != table["columns"] or any(
                not pa.types.is_string(field.type) for field in held.schema):
            return False
        if any(column.null_count for column in held.columns):
            return False
        return canonical_csv_text(table["columns"], held.to_pylist(),
                                  table["primary_key"]) == text
    except (pa.ArrowException, OSError, KeyError, ValueError, TypeError):
        return False


def build_all(consume=None):
    """Build each table once; a consumer can write/check it without retaining all CSV text."""
    src = Sources()
    tables, texts = {}, {}
    builders = [(name, "dimension", builder, {"rule": "lookup", "closure": "closed vocabulary"})
                for name, builder in DIMENSIONS]
    builders += [(name, "fact", builder, aggregation) for name, builder, aggregation in FACTS]
    for name, kind, builder, aggregation in builders:
        with src.track() as dependencies:
            fields, key, rows = builder(src)
            table, text = _table(name, kind, fields, key, rows, aggregation)
        table["derived_from"] = src.digests(dependencies)
        tables[name] = table
        if consume is None:
            texts[name] = text
        else:
            consume(name, table, text)
    limitations = completeness_limitations(src.rows("completeness"))
    downloads, activity_inputs = build_downloads(tables, src)
    release = build_release(tables, src.digests(), limitations,
                            download_catalog=downloads, activity_inputs=activity_inputs)
    return tables, texts, canonical_json_text(release)


def _matches(path, text):
    if not os.path.exists(path):
        return False
    with open(path, "rb") as handle:
        return handle.read() == text.encode("utf-8")


def _write_changed(path, text):
    """Keep unchanged bytes and mtimes; publish a changed file atomically."""
    if _matches(path, text):
        return False
    fd, temporary = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return True


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    check = "--check" in argv
    if not check:
        os.makedirs(OUT_DIR, exist_ok=True)
    differences = []

    def consume(name, table, text):
        path = asset_path(OUT_DIR, name + ".csv")
        parquet = asset_path(OUT_DIR, name + ".parquet")
        parquet_exists = os.path.exists(parquet)
        if check:
            if not _matches(path, text):
                differences.append(name + ".csv")
            if parquet_exists and _parquet_matches(parquet, table, text) is False:
                differences.append(name + ".parquet")
            return
        changed = _write_changed(path, text)
        if changed or not parquet_exists or _parquet_matches(parquet, table, text) is False:
            if not _write_parquet(parquet, table["columns"], text) and parquet_exists:
                # A CSV-only environment must not leave an older representation
                # behind for query engines that prefer it over the current CSV.
                os.unlink(parquet)

    tables, _, release_text = build_all(consume=consume)
    path = asset_path(OUT_DIR, "semantic_release.json")
    if check:
        if not _matches(path, release_text):
            differences.append("semantic_release.json")
        print("semantic release: %s" % ("byte-identical" if not differences
                                        else "DIFFERS: %s" % ", ".join(differences)))
        return 1 if differences else 0
    _write_changed(path, release_text)
    print("semantic release -> %s" % OUT_DIR)
    for name in sorted(tables):
        print("  %-26s %6d rows  %s" % (name, tables[name]["rows"], tables[name]["sha256_csv"][:12]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
