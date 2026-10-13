"""The reader-facing form of the activity tables, rendered from the technical ones.

The technical tables (outputs/activity/activity_*.csv) answer the six questions in a machine's
vocabulary - `head_count`, `kha`, `province_by_locality`, a period `2014` whose meaning depends on
the sector. A reader who wants Pakistan's livestock numbers should not have to decode any of that.
This module turns each technical table into one a person can open: `Period · Location · Measure ·
Animal type · Value · Unit · …`, with every label expanded, every unit spelt out, every fiscal year
written `FY 2013-14`, and a `Use note` on every row saying what may not be added to what.

⚠ IT RENDERS; IT DOES NOT DECIDE. Every label comes from a register in data/ - activity_measures,
activity_units, activity_labels, activity_collections, activity_use_notes, and the `label` column
of activity_evidence_classes - and a value with no register entry FAILS THE BUILD naming it. The
registers were seeded from the tables the user reshaped by hand (PakEmis_Activity_Data, 2026-09-17)
and are the source of truth from then on.

⚠ NOTHING IS LOST. The twenty technical fields of every row are written, verbatim, to
activity_source_details.csv under the same `Record ID` the readable row carries, and a test holds
every readable value to its technical value across all 101,808 rows. The readable table is a view;
the technical one is the record.
"""

from pkinv.assets import asset_path
import os
import re

from pkinv.core.io import read_rows, write_table
from pkinv.paths import DATA, OUTPUTS
from pkinv.semantic.canonical import row_id

IN_DIR = asset_path(OUTPUTS, "activity")
OUT_DIR = asset_path(IN_DIR, "public")
DETAILS = asset_path(IN_DIR, "activity_source_details.csv")
GUIDE = asset_path(IN_DIR, "activity_column_guide.csv")

#: the semantic table the technical rows become, and therefore the table their ids are minted for
DETAILS_TABLE = "fact_activity_source_details"
DETAILS_KEY = ("source_id", "source_row", "source_column", "variable", "category")

TECHNICAL = ("collection", "variable", "category", "subcategory", "value", "unit", "geography",
             "geography_level", "period", "period_basis", "source_period", "evidence", "evidence_note",
             "source_id", "source_row", "source_column", "source_ref", "transform", "combinable", "note")

PERIOD_TYPE = {"fiscal": "Fiscal year", "calendar": "Calendar year", "calendar_month": "Calendar month",
               "survey_round": "Survey round", "snapshot_date": "Snapshot date"}
REPORTING_INTERVAL = {"monthly": "Single-month report", "cumulative": "Cumulative report"}


class UnlabelledValue(Exception):
    """A technical value with no reader label in any register. There is no default label."""


def _reg(name):
    return read_rows(asset_path(DATA, name))


def mechanical(raw):
    """The default label: underscores to spaces, first letter capitalised, the rest as written.
    A SHOUTED source label (AZAD KASHMIR) is not re-cased here: acronyms shout too (SNGPL, NPKS),
    and only the labels register knows which is which."""
    text = (raw or "").replace("_", " ").strip()
    return text[:1].upper() + text[1:]


class Registers:
    def __init__(self):
        self.collections = {r["collection"]: r for r in _reg("activity_collections.csv")}
        self.measures = {(r["source_id"], r["variable"], r["unit"]): r["label"] for r in _reg("activity_measures.csv")}
        self.units = {(r["unit"], r["category"]): r["label"] for r in _reg("activity_units.csv")}
        self.labels = {(r["collection"], r["raw"]): r["label"] for r in _reg("activity_labels.csv")}
        self.evidence = {r["evidence"]: r["label"] for r in _reg("activity_evidence_classes.csv")}
        self.series = {r["path"]: r["series_label"] for r in _reg("activity_files.csv")}
        self.notes = [(r["collection"], r["condition"], r["note"]) for r in _reg("activity_use_notes.csv")]

    def measure(self, row):
        sid, var, unit = row["source_id"], row["variable"], row["unit"]
        for key in ((sid, var, unit), (sid, var, "*"), ("*", var, unit), ("*", var, "*")):
            if key in self.measures:
                return self.measures[key]
        raise UnlabelledValue("%s: variable %r (unit %r) has no row in activity_measures.csv" % (sid, var, unit))

    def unit(self, row):
        unit, cat = row["unit"], row["category"]
        for key in ((unit, cat), (unit, "*")):
            if key in self.units:
                return self.units[key]
        raise UnlabelledValue("%s: unit %r (category %r) has no row in activity_units.csv" % (row["source_id"], unit, cat))

    def label(self, collection, raw):
        """The whole value first, then each ` · `-separated part, then the mechanical default."""
        if not raw:
            return ""
        for key in ((collection, raw), ("*", raw)):
            if key in self.labels:
                return self.labels[key]
        if " · " in raw:
            parts = []
            for part in raw.split(" · "):
                if not parts or part != parts[-1]:      # OCAC prints `DOMESTIC · DOMESTIC`; once is enough
                    parts.append(part)
            return " · ".join(self.label(collection, part) for part in parts)
        return mechanical(raw)

    def use_note(self, row):
        base = self.collections[row["collection"]]["base_note"]
        extra = [note for coll, cond, note in self.notes
                 if coll in ("*", row["collection"]) and _holds(cond, row)]
        return " ".join([base] + extra)


def _holds(condition, row):
    if "~" in condition:
        col, prefix = condition.split("~", 1)
        return (row.get(col) or "").startswith(prefix)
    col, value = condition.split("=", 1)
    return (row.get(col) or "") == value


def period_display(period, basis):
    if basis == "fiscal" and re.fullmatch(r"FY\d{4}-\d{2}", period):
        return "FY " + period[2:]
    m = re.fullmatch(r"hies(\d{4})", period)
    if m:                                        # a survey round is named for the fiscal year it ran in
        end = int(m.group(1))
        return "HIES %d-%02d" % (end - 1, end % 100)
    return period


_DIGEST = re.compile(r"\b[0-9a-f]{64}\b")
#: directory components in front of a filename, wherever it sits in the prose
_DIRS = re.compile(r"(?<![\w:])(?:[\w.-][\w .-]*/)+(?=[\w.-]+\.(?:pdf|csv|xlsx|xls|html|zip|json|txt|nc)\b)")


def source_reference(row, series):
    """The citation without its machinery: digests dropped, directory paths dropped, the rest as
    the ingest wrote it - a table number, a page, a printed label."""
    text = row["source_ref"] or ""
    text = _DIGEST.sub("", text)
    text = _DIRS.sub("", text)
    parts = [p.strip() for p in text.split(" · ") if p.strip()]
    return " · ".join(parts) or series


def split_geography(mode, geography):
    """A composite place into its columns. Returns (location, second) where second is the
    locality or the province the mode names, or None when the collection has no such column."""
    parts = [p.strip() for p in geography.split(" · ")]
    if mode == "location_locality":
        return parts[0], (parts[1] if len(parts) > 1 else "")
    if mode == "province_location":
        return (parts[1], parts[0]) if len(parts) > 1 else (parts[0], "")
    if mode == "location_province":
        return parts[0], (parts[1] if len(parts) > 1 else "")
    return geography, None


def columns_for(spec):
    """The public column order for one collection."""
    extras = [e for e in (spec["extra_columns"] or "").split(";") if e]
    second = {"location_locality": "Locality", "province_location": "Province", "location_province": "Province"}.get(spec["geography_split"])
    cols = ["Period", "Location"]
    if second:
        cols.append(second)
    cols += ["Measure", spec["category_header"]]
    if spec["subcategory_header"]:
        cols.append(spec["subcategory_header"])
    if "Fuel classification basis" in extras:
        cols.append("Fuel classification basis")
    cols += ["Value", "Unit", "Period type"]
    if "Reporting interval" in extras:
        cols.append("Reporting interval")
    cols += ["Location level", "Evidence"]
    if "Source status" in extras:
        cols.append("Source status")
    cols += ["Source series", "Use note", "Source reference", "Record ID"]
    return cols


def render(row, spec, reg):
    """One technical row into one readable row. Values are copied, never recomputed."""
    collection = row["collection"]
    series = reg.series.get(row["source_id"])
    if not series:
        raise UnlabelledValue("%s: no series_label in activity_files.csv" % row["source_id"])
    location, second = split_geography(spec["geography_split"], row["geography"])
    location = reg.label(collection, location)
    if second:
        second = reg.label(collection, second)
    out = {
        "Period": period_display(row["period"], row["period_basis"]),
        "Location": location,
        "Measure": reg.measure(row),
        spec["category_header"]: reg.label(collection, row["category"]),
        "Value": row["value"],
        "Unit": reg.unit(row),
        "Period type": PERIOD_TYPE[row["period_basis"]],
        "Location level": mechanical(row["geography_level"]),
        "Evidence": reg.evidence[row["evidence"]],
        "Source series": series,
        "Use note": reg.use_note(row),
        "Source reference": source_reference(row, series),
        "Record ID": row_id(DETAILS_TABLE, [row[k] for k in DETAILS_KEY]),
    }
    if second is not None:
        out[{"location_locality": "Locality"}.get(spec["geography_split"], "Province")] = second
    if spec["subcategory_header"]:
        out[spec["subcategory_header"]] = reg.label(collection, row["subcategory"])
    extras = spec["extra_columns"] or ""
    if "Fuel classification basis" in extras:
        out["Fuel classification basis"] = reg.label(collection, row["evidence_note"])
    if "Reporting interval" in extras:
        out["Reporting interval"] = REPORTING_INTERVAL.get(row["source_period"], row["source_period"])
    if "Source status" in extras:
        out["Source status"] = reg.label(collection, row["evidence_note"])
    return out


MEANING = {
    "Period": "Reporting period: FY yyyy-yy for a fiscal year, yyyy-mm for a month, yyyy for a calendar year, a survey round by its name, or the date a stock was counted. Set this column to Text when importing into Excel.",
    "Location": "Reported place. A composite place is split into this column and Locality or Province.",
    "Locality": "Urban or rural, where the source reports by locality.",
    "Province": "The province a district or airport lies in.",
    "Measure": "The quantity Value represents. Monetary values are named as values, not quantities.",
    "Value": "The source's own figure, with no unit or thousands separator. Blank means the source printed nothing; it is never zero.",
    "Unit": "The unit, spelt out. Quantities are never rescaled: thousand tonnes stays thousand tonnes.",
    "Period type": "Fiscal year, calendar year, calendar month, survey round or snapshot date.",
    "Reporting interval": "Single-month report or cumulative report; cumulative editions overlap the months they cover.",
    "Location level": "The geographic level of Location: national, province, district, sales area, airport or plant.",
    "Evidence": "Reported, survey estimate, allocated estimate, calculated, projection, assumption, modelled estimate, or not printed in source.",
    "Fuel classification basis": "How the fuel label was attributed - reported by PBS or NEPRA, carried from another year, inferred, or not assigned. Generation is reported regardless.",
    "Source status": "The source's own status word for this cell, as it printed or as PakEmis transcribed it.",
    "Source series": "The source dataset this row comes from. Series overlap; it is not a summation key.",
    "Use note": "What this row may and may not be added to, and the caveats its source carries.",
    "Source reference": "The citation, without file paths or digests. The full reference is in the source details table.",
    "Record ID": "Joins this row to its twenty technical fields in the source details table.",
}


def build_all(tables):
    """tables: name -> technical rows. Writes the public tables, the details table and the guide."""
    reg = Registers()
    os.makedirs(OUT_DIR, exist_ok=True)
    details, guide = [], []
    for name in sorted(tables):
        spec = reg.collections[name]
        cols = columns_for(spec)
        public = [render(row, spec, reg) for row in tables[name]]
        write_table(asset_path(OUT_DIR, "activity_%s.csv" % name), cols, public, lineterminator="\n")
        for row, pub in zip(tables[name], public):
            details.append(dict({"Record ID": pub["Record ID"], "Public file": "activity_%s.csv" % name},
                                **{k: row[k] for k in TECHNICAL}))
        for c in cols:
            meaning = MEANING.get(c) or ("Readable original subcategory." if c == spec["subcategory_header"]
                                         else "Readable original category.")
            guide.append({"file": "activity_%s.csv" % name, "column": c, "meaning": meaning})
        print("  %-28s %7d rows -> public/" % (name, len(public)))
    write_table(DETAILS, ("Record ID", "Public file") + TECHNICAL, details, lineterminator="\n")
    write_table(GUIDE, ("file", "column", "meaning"), guide, lineterminator="\n")
    print("  %-28s %7d rows" % ("source_details", len(details)))
