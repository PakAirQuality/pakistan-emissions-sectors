"""The "Activity publication" phase: python3 -m pkinv.activity.publish

Turns the hand-verified ingest tree into tables a reader can use without running PakEmis, or even
studying emissions. Six collections, eight tables, one shape.

WHY A BUILDER AND FOUR REGISTRIES rather than a script per collection. The tree holds 167 files with
937 distinct column names, 705 of which appear exactly once; units are baked into column names
(`area_kha`, `gwh`, `value_t`), and status lives in more than sixty different columns. Every one of
those is a judgement about what a number means, and a judgement buried in a melt function is a
judgement nobody can review. So the judgements live in data/activity_*.csv and this module
only executes them.

WHAT IT NEVER DOES: compute a quantity. A published value is the ingest's value. Where a unit changes
or a label is repaired, `transform` says so on the row. Where the source printed a dash, the value
stays EMPTY and the row is typed `not_printed` - an absence is never a zero.

⚠ AN UNMAPPED STATUS IS A BUILD FAILURE, not a default. If a file grows a status value that
data/activity_evidence_map.csv does not carry, this raises. Falling back to `reported` is
precisely how "verified" - which is a statement about OUR transcription - would come to be published
as "observed".
"""

from pkinv.assets import asset_path
import os
import re

from pkinv.activity.store import read_rows
from pkinv.core.io import write_table
from pkinv.paths import DATA, OUTPUTS

OUT_DIR = asset_path(OUTPUTS, "activity")

FIELDS = ("collection", "variable", "category", "subcategory", "value", "unit", "geography",
          "geography_level", "period", "period_basis", "source_period", "evidence", "evidence_note",
          "source_id", "source_row", "source_column", "source_ref", "transform", "combinable", "note")

#: the published tables, one file each; the collection column of activity_files.csv routes to them
TABLES = (
    "fuel_sales_national", "fuel_sales_area", "livestock", "crops", "fertiliser",
    "power_plants", "power_monthly", "household_fuel",
    # rc56: the three collections rc55 left pending, and the sector datasets that belong beside them
    "industry_fuel", "industry_production", "gas_supply", "gas_network",
    "waste_services", "waste_flows", "railways", "aviation", "vehicles",
)


class UnmappedStatus(Exception):
    """A source status value that data/activity_evidence_map.csv does not carry."""


#: the registers live beside the repo's other hand-authored registers in data/, not in a
#: tree of their own: the provenance audit classes a root data/*.csv with no producer as
#: `hand:parameter`, which is exactly what each of these is.
def _schema(name):
    return read_rows(asset_path(DATA, name))


def _semi(value):
    return [p for p in (value or "").split(";") if p]


def _keeps(spec, row):
    """The declared row filter. A source that prints a TOTAL beside its members would otherwise
    publish a column that double-counts the moment anyone sums it."""
    for clause in _semi(spec.get("filter", "")):
        if clause.endswith(":nonempty"):
            if not (row.get(clause[:-len(":nonempty")]) or "").strip():
                return False
        elif "!=" in clause:
            col, value = clause.split("!=", 1)
            if (row.get(col) or "").strip() == value:
                return False
        elif "=" in clause:
            col, value = clause.split("=", 1)
            if (row.get(col) or "").strip() != value:
                return False
    return True


def _evidence_rules(rows):
    exact, wildcard, dropped = {}, {}, set()
    for r in rows:
        if r.get("drop") == "yes":
            dropped.add((r["path"], r["column"], r["value"]))
        if r["value"] == "*":
            wildcard.setdefault(r["path"], []).append((r["column"], r["evidence"]))
        else:
            exact[(r["path"], r["column"], r["value"])] = r["evidence"]
    return exact, wildcard, dropped


def _items(rows):
    return {(r["path"], r["item"]): r for r in rows}


def _ref(row, cols):
    parts = [(row.get(c) or "").strip() for c in cols]
    return " · ".join(p for p in parts if p)


def build_rows():
    files = _schema("activity_files.csv")
    columns = _schema("activity_columns.csv")
    classes = {r["evidence"] for r in _schema("activity_evidence_classes.csv")}
    exact, wildcard, dropped = _evidence_rules(_schema("activity_evidence_map.csv"))
    items = _items(_schema("activity_item_map.csv"))

    by_path = {}
    for c in columns:
        by_path.setdefault(c["path"], []).append(c)

    out, skipped = {}, 0
    for spec in files:
        path = spec["path"]
        rows = read_rows(asset_path(os.path.dirname(DATA), path)) if not os.path.isabs(path) else read_rows(path)
        for index, row in enumerate(rows, start=1):
            row = dict(row, _source_row=index)
            if not _keeps(spec, row):
                continue
            if _is_dropped(spec, row, dropped, path):
                skipped += 1
                continue
            for col in by_path.get(path, []):
                for published in _publish(spec, col, row, exact, wildcard, items, classes):
                    out.setdefault(published.pop("_table"), []).append(published)
    if skipped:
        print("  %-28s %7d rows declared not-publishable in evidence_map.csv" % ("(withheld)", skipped))
    return out


def _is_dropped(spec, row, dropped, path):
    """A row the evidence map declares unpublishable - and says why, in the same row."""
    if not spec["evidence_col"]:
        return False
    return (path, spec["evidence_col"], (row.get(spec["evidence_col"]) or "").strip()) in dropped


def _publish(spec, col, row, exact, wildcard, items, classes):
    """One ingest row and one value column become zero or more published rows."""
    path = spec["path"]
    names = _semi(col["column"]) or [col["column"]]
    # ⚠ `category` and `unit` may be lists PARALLEL to `column`. One melt can carry several units:
    # the statistical yearbook prints crude oil and natural gas side by side in one row, in
    # thousand barrels and million cubic feet, and a single unit for both would be wrong twice.
    cats = _semi(col.get("category", ""))
    units = _semi(col["unit"]) if ";" in (col["unit"] or "") else []
    for position, name in enumerate(names):
        if name not in row:
            continue
        raw = (row.get(name) or "").strip()

        variable, category, unit, collection = col["variable"], "", col["unit"], spec["collection"]
        # a column melted out of a wide table names its own label (cattle, buffalo, sheep, ...)
        melt = cats[position] if position < len(cats) else (name if len(names) > 1 else "")
        declared = (row.get(spec["category_col"]) or "").strip() if spec["category_col"] else spec["category_const"]
        subcategory = _joined(spec["subcategory_col"], row)
        # ⚠ THE MELT LABEL NEVER OVERWRITES A DECLARED CATEGORY. It did, once: airline_controls named
        # the airline as its category and the melt's `departures;arrivals` replaced it on every row,
        # so 235 rows left the release with no airline on them. When both exist the melt label is a
        # second axis and goes beside the subcategory.
        if melt and declared:
            category, subcategory = declared, " · ".join(p for p in (subcategory, melt) if p)
        else:
            category = melt or declared

        if variable == "item:" or unit == "item:":
            # the file's single `item` column encodes crop, variable and unit at once
            key = (path, (row.get("item") or "").strip())
            if key not in items:
                raise UnmappedStatus("%s: item %r is not in item_map.csv" % (path, key[1]))
            m = items[key]
            variable, category, unit, collection = m["variable"], m["category"], m["unit"], m["collection"]
        if position < len(units):
            unit = units[position]
        if unit.startswith("col:"):
            unit = (row.get(unit[4:]) or "").strip()

        evidence, note = _classify(spec, col, row, exact, wildcard, path, raw)
        if evidence not in classes:
            raise UnmappedStatus("%s: evidence %r is not in evidence_classes.csv" % (path, evidence))

        transform = col["transform"]
        extra = _row_transform(path, row)
        transform = " · ".join(p for p in (transform, extra) if p)
        geography, level = _geography(spec, row)
        period, basis = _period(spec, col, row)

        yield {
            "_table": collection,
            "collection": collection,
            "variable": variable,
            "category": category,
            "subcategory": subcategory,
            "value": "" if evidence == "not_printed" else raw,
            "unit": unit,
            "geography": geography,
            "geography_level": level,
            "period": period,
            "period_basis": basis,
            "source_period": (row.get(spec["source_period_col"]) or "").strip() if spec["source_period_col"] else "",
            "evidence": evidence,
            "evidence_note": note,
            "source_id": path,
            # ⚠ THE ORDINAL OF THE INGEST ROW, and it is provenance before it is a key. PBS prints
            # two rows under the truncated name "Sapphire electric company U" - a cut-off "Unit" -
            # with the same month and different generation, 24 times. They cannot be told apart from
            # the name, and neither summing them (inventing a total the source never printed) nor
            # dropping them (losing real generation) is honest. Naming the row they came from is.
            "source_row": row["_source_row"],
            "source_column": name,
            "source_ref": _ref(row, _semi(spec["source_ref_cols"])),
            "transform": transform,
            "combinable": _combinable(evidence, _row_combinable(row, col["combinable"])),
            "note": (row.get("note") or "").strip(),
        }


#: a projection may be added to other projections and to nothing else
PROJECTION_RULE = "only with other projections; a forward estimate is not an observation"


def _combinable(evidence, declared):
    """⚠ THE EVIDENCE CLASS OVERRIDES THE COLUMN'S DEFAULT for a projection.

    The poultry row is the case that found this: its value is the Economic Survey's estimate, while
    every other row in the same column is an enumerated census count. Left to the column default it
    would have said "yes, within a period" - an invitation to add a projected flock to five counted
    herds and call the sum a livestock population.
    """
    return PROJECTION_RULE if evidence == "projection" else declared


def _joined(columns, row):
    """Several source columns are one published axis. ⚠ Not cosmetic: OCAC prints `section` AND
    `sector_row`, and a plant-month carries both `fuel` and the `fuel_source` it was attributed
    from. Dropping either collapses two distinct source rows into one and loses a real number."""
    parts = [(row.get(c) or "").strip() for c in _semi(columns)]
    return " · ".join(p for p in parts if p)


def _geography(spec, row):
    """The place and its level. ⚠ A NATIONAL ROW IN A PLACE COLUMN IS NOT A PLACE: OCAC's area pages
    carry a PAKISTAN row beside Punjab and Karachi, and HIES prints a `national` scope beside the
    provinces. `national_marker` names that value, so it is published as Pakistan at national level
    rather than as a province called PAKISTAN - which is what 7,700 rows said until this."""
    level = spec["geography_level"]
    if not spec["geography_col"]:
        return spec["geography_const"], level
    parts = [(row.get(c) or "").strip() for c in _semi(spec["geography_col"])]
    parts = [p for p in parts if p]
    lookup = spec.get("geography_lookup", "")
    if lookup and parts:
        # an id in the source becomes the place it names: `kp_bannu` -> Khyber Pakhtunkhwa · Bannu District
        parts = _lookup(lookup, parts[0]) + parts[1:]
    marker = spec.get("national_marker", "")
    if marker and parts and parts[0] == marker:
        parts[0] = "Pakistan"
        level = "national_by_locality" if len(parts) > 1 else "national"
    if spec["geography_const"]:
        # a constant AND columns: the constant is the place, the columns qualify it (Pakistan · Urban)
        parts = [spec["geography_const"]] + parts
        if level == "national" and len(parts) > 1:
            level = "national_by_locality"
    return " · ".join(parts) or spec["geography_const"], level


_LOOKUPS = {}


def _lookup(declaration, value):
    """`file:key_column:out1;out2` - one row of a registry, for the id in `value`."""
    path, key, outs = declaration.split(":")
    if path not in _LOOKUPS:
        _LOOKUPS[path] = {r[key]: r for r in read_rows(asset_path(os.path.dirname(DATA), path))}
    row = _LOOKUPS[path].get(value)
    if row is None:
        raise UnknownPlace("%s: %r is not in %s" % (declaration, value, path))
    return [(row.get(c) or "").strip() for c in outs.split(";")]


MONTHS = {m: i for i, m in enumerate(("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1)}


class UnresolvedPeriod(Exception):
    """A period the publisher cannot state unambiguously - a bare year with no fiscal convention."""


class UnknownPlace(Exception):
    """A geography id the declared registry does not carry."""


def _period(spec, col, row):
    """One canonical spelling per period basis, and a refusal where the source's own is ambiguous.

    ⚠ A BARE FISCAL YEAR MEANS TWO DIFFERENT THINGS IN THIS TREE. A railway `2014` is FY2013-14
    (the year the fiscal year ENDS); an airport `2006` is FY2006-07 (the year it STARTS). The
    sector engines declare which, and `fiscal_convention` carries that here, so every published
    fiscal period reads FYyyyy-yy and nothing is left for a reader to guess. Months become yyyy-mm;
    a vehicle stock "as at 30 June" becomes the date it was counted.
    """
    override = (col.get("period_override") or "").strip()
    basis = spec["period_basis"]
    if override:
        return override, basis
    parts = [(row.get(c) or "").strip() for c in _semi(spec["period_col"])] if spec["period_col"] else [spec["period_const"]]
    raw = " ".join(p for p in parts if p)
    where = "%s: period %r" % (spec["path"], raw)
    if basis in ("fiscal", "snapshot_date"):
        m = re.fullmatch(r"(?:FY)?(\d{4})-(\d{2})", raw)
        if m:
            year = int(m.group(1)) + 1
        elif re.fullmatch(r"\d{4}", raw):
            conv = spec.get("fiscal_convention", "")
            if conv == "fiscal-end":
                year = int(raw)
            elif conv == "fiscal-start":
                year = int(raw) + 1
            else:
                raise UnresolvedPeriod(where + " is a bare year and the file declares no fiscal_convention")
        else:
            raise UnresolvedPeriod(where + " is not a fiscal year this publisher can spell")
        if basis == "snapshot_date":
            return "%d-06-30" % year, basis           # counted as at 30 June, the fiscal year's end
        return "FY%d-%02d" % (year - 1, year % 100), basis
    if basis == "calendar_month":
        if re.fullmatch(r"\d{6}", raw):
            return "%s-%s" % (raw[:4], raw[4:]), basis
        if re.fullmatch(r"\d{4}-\d{2}", raw):
            return raw, basis
        m = re.fullmatch(r"(\d{4}) ([A-Z][a-z]{2})", raw)
        if m and m.group(2) in MONTHS:
            return "%s-%02d" % (m.group(1), MONTHS[m.group(2)]), basis
        raise UnresolvedPeriod(where + " is not a month this publisher can spell (a month name needs its year)")
    if basis == "calendar":
        if re.fullmatch(r"\d{4}", raw):
            return raw, basis
        raise UnresolvedPeriod(where + " is not a calendar year")
    return raw, basis                                  # survey rounds keep the source's own name


def _row_combinable(row, declared):
    """⚠ THE SOURCE'S OWN ADDITIVITY FLAG, ON THE ROW. OCAC's area pages mark which rows may be
    summed (`additive`) - a cumulative edition or a subtotal is not - and the declared rule used to
    NAME that flag without publishing its value, so a reader could not act on it."""
    if "additive" in row:
        return declared if (row.get("additive") or "").strip() == "1" else \
            "no: not additive in the source - a cumulative edition or a subtotal row"
    return declared


def _classify(spec, col, row, exact, wildcard, path, raw):
    """Evidence class and the source's own word, in that order of precedence."""
    note = ""
    if spec["evidence_col"]:
        note = (row.get(spec["evidence_col"]) or "").strip()
    # a declared split wins over everything: it makes the row an allocation whatever else it says
    for column, evidence in wildcard.get(path, []):
        if (row.get(column) or "").strip():
            return evidence, (row.get(column) or "").strip()
    if raw == "":
        return "not_printed", note
    if col["evidence_override"]:
        return col["evidence_override"], ""       # the row's status word describes the row's other columns, not this one
    if spec["evidence_col"]:
        key = (path, spec["evidence_col"], note)
        if key not in exact:
            raise UnmappedStatus(
                "%s: %s=%r has no row in evidence_map.csv. Add one with a reason; there is no default."
                % (path, spec["evidence_col"], note))
        return exact[key], note
    return spec["evidence_const"], note


def _row_transform(path, row):
    """Transformations the ingest row itself records, carried verbatim rather than restated."""
    if row.get("unit_basis"):
        return row["unit_basis"]
    if row.get("split_rule"):
        return row["split_rule"]
    return ""


BANNER = (
    "# Activity data behind the PakEmis estimates, published so it can be used on its own.",
    "# Every row answers: what the quantity is, where and when it applies, what kind of evidence it",
    "# is, where it came from, what PakEmis changed, and whether it may be added to its neighbours.",
    "# An empty value with evidence=not_printed is a cell the source left blank. It is NOT a zero.",
    "# Built by pkinv.activity.publish from data/activity_*.csv; do not hand-edit.",
)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    tables = build_rows()
    for name in sorted(TABLES):
        rows = tables.get(name, [])
        out = asset_path(OUT_DIR, "activity_%s.csv" % name)
        write_table(out, FIELDS, rows, banner=BANNER, lineterminator="\n")
        print("  %-28s %7d rows" % (name, len(rows)))
    # the reader-facing form of the same rows, rendered from the registers - see present.py
    from pkinv.activity import present
    present.build_all({name: tables.get(name, []) for name in TABLES})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
