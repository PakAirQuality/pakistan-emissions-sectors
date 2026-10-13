#!/usr/bin/env python3
"""Can a reader find the figure IN the document, or only the document?

    python3 scripts/build_citation_pointer_audit.py
    -> outputs/pakemis_citation_pointer_audit.csv

THE QUESTION. This release's source register answers "where did this come from" at the
level of a DOCUMENT: publisher, edition, archive digest, and how to obtain it. The
reviewer's standing objection is finer and it is a different question - given the
document, can a reader find the specific table the number was read from? That is a table
pointer, and until now nothing counted them. The acceptance blocker said pointers were
"still missing for HDIP, OGRA, OCAC, operator yearbooks, PBS QIM, APCMA and the spatial
and meteorological inputs", which is a list of worries rather than a measurement - and
one of its entries is already wrong: every HDIP row carries a pointer.

THE DENOMINATOR IS THE WHOLE POINT, and getting it wrong in either direction makes the
number meaningless. A registered source is one of three things:

  archived      an extraction from a document this project holds. A table pointer is
                exactly the right notion and its absence is a real gap.
  derived       built from other files already in this repository. Its provenance is the
                derivation chain, not a page number; demanding a table pointer here would
                inflate the gap with rows that cannot have one.
  not-archived  a document this project does not hold. A pointer would still help a
                reader who obtains it, but this repository cannot verify one.

And within `archived`, a second split that a first version of this audit missed: a source
may be a DOCUMENT (a report with tables and pages) or a DATASET (a CSV export, a satellite
product, a statistical API). For a dataset the honest pointer is a file and a variable,
not a table, and scoring it as a missing table pointer would be scoring it against a
convention it does not have.

WHERE A POINTER MAY LIVE. Two layers, and checking only the first is how the gap was
previously overstated. It may be in the register row itself (`primary_source` or `note`),
or in the produced table's OWN per-row source column - which is where this project's
hand-verified ingests put it, one citation per row. A source whose ingest cites
"HDIP Energy Yearbook 2024, Table 4.2" on every row is cited precisely; the register row
simply does not repeat it.

POINTED IS NOT THE SAME AS CHECKABLE, which the first version of this audit conflated. A
pointer is stated in the register whether or not this repository holds the document it
points into, so `pointed` mixed two things: 94 rows whose document is archived here, where
a reader can open it and confirm the figure, and 10 where they cannot - 6 whose document
is not archived (the Economic Survey Statistical Supplement among them) and 4 derived
inside this repository. The `pointer_checkable_here` column separates them. It changes no
verdict: a pointer into a document the reader must obtain is still a pointer, and far
better than none. It only stops the audit's strongest number from implying more than it
has.

A KNOWN LIMITATION OF THE DATASET TEST, declared because it makes the unpointed count
CONSERVATIVE rather than exact. `is_dataset` recognises a source as a dataset from markers
in its own description, and the marker list does not know every publisher: the Global
Energy Monitor trackers, the ELK rail layers, the Global Mangrove Watch release and the
HIES microdata are all datasets whose honest pointer is a file and a row filter, and
several of them carry one in substance ("Pakistani rows (88 units)"), yet they score
`unpointed` because no marker matched. Widening the marker list would move them to
`not-applicable` and improve the pointed share WITHOUT citing anything, which is exactly
what the not-applicable ratchet exists to make visible - so the list is left alone and the
count is left overstating the gap. Overstating a gap is the safe direction; a reader who
acts on it loses nothing but effort.

WHAT IT REPORTS. One row per registered source, with the pointer's location or the reason
there is none, and the publisher it belongs to, so the blocker can be answered per
publisher instead of in the aggregate. tests/test_citation_pointer_audit.py holds the
unpointed count as a ratchet that may only fall.
"""
import csv
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.assets import asset_path                                  # noqa: E402
from pkinv.core.io import read_rows, write_table                     # noqa: E402

OUT = os.path.join(ROOT, "outputs", "pakemis_citation_pointer_audit.csv")
REGISTER = os.path.join(ROOT, "data", "catalog", "source_documents.csv")

# What a locator looks like in THIS project's citations, as actually written. The list
# was not invented: each alternative was counted in data/catalog/source_documents.csv
# before being added, so the detector matches the vocabulary in use rather than a
# vocabulary it would like to see. The first version carried only the formal words and
# scored eleven real citations as unpointed - "audit report, para 2.5.99", "HIES 2024-25
# Sec 5 Mod 3", "Agriculture chapter, Fig-2.8" are locators by any reading. A detector
# that misses the citation style a project actually uses measures the style, not the gap.
POINTER = re.compile(
    r"\b(?:Table|Annexure|Annex|Appendix|Sheet|sheet|worksheet|pp?\.|page|Figure|"
    r"Fig[-. ]|Statement|Chapter|Section|Sec[. ]|Mod\s|Exhibit|Schedule|[Pp]ara|"
    r"Part\s+[IVX0-9]|row\s+\d|line\s+\d)")
# The per-row citation columns this project's ingests use.
SOURCE_COLUMNS = ("source", "source_reference", "source_ref", "primary_source",
                  "citation", "source_note", "reference")
# A source whose document IS a dataset: the pointer notion is a file and a variable.
DATASET_MARKERS = (".csv", ".json", ".geojson", ".npy", ".nc", ".zip", ".xlsx",
                   "api", "ourairports", "climate trace", "climatetrace", "era5",
                   "nasa power", "worldpop", "comtrade", "edgar", "faostat",
                   "microdata", "satellite", "mars", "geoboundaries", "osm",
                   "openstreetmap", "spam", "glw", "worldcover")
PUBLISHERS = ("HDIP", "OGRA", "OCAC", "PBS", "APCMA", "NFDC", "NEPRA", "PCAA",
              "Pakistan Railways", "Economic Survey", "FAO", "UNFCCC", "EDGAR",
              "Comtrade", "UNEP", "IPCC", "WorldPop", "ERA5", "NASA", "Climate TRACE",
              "OECD", "UNDP", "Ozone Secretariat", "IEA", "geoBoundaries")


def publisher_of(row):
    text = "%s %s" % (row.get("primary_source") or "", row.get("archived_path") or "")
    for name in PUBLISHERS:
        if name.lower() in text.lower():
            return name
    return "other"


def is_dataset(row):
    text = "%s %s" % (row.get("primary_source") or "", row.get("archived_path") or "")
    return any(marker in text.lower() for marker in DATASET_MARKERS)


def pointer_in_rows(data_file):
    """The first per-row citation carrying a pointer, or None."""
    try:
        path = asset_path(ROOT, data_file)
    except Exception:
        path = os.path.join(ROOT, data_file)
    if not os.path.exists(path) or not path.endswith(".csv"):
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            reader = csv.DictReader(line for line in handle if not line.startswith("#"))
            columns = [c for c in (reader.fieldnames or [])
                       if c.strip().lower() in SOURCE_COLUMNS]
            if not columns:
                return None
            for row in reader:
                for column in columns:
                    value = (row.get(column) or "").strip()
                    if POINTER.search(value):
                        return "%s: %s" % (column, value[:90])
    except (OSError, UnicodeDecodeError, csv.Error):
        return None
    return None


def checkable(row):
    """Can a reader confirm this pointer from what this repository holds?"""
    state = row.get("archival_state") or ""
    if state == "archived":
        return "yes"
    if state == "derived":
        return "derived-file: its provenance is the derivation chain, not a document"
    return "document-not-held: the pointer is stated and must be checked against a copy "\
           "obtained from the publisher"


def classify(row):
    """(verdict, where, evidence) for one registered source."""
    register_text = "%s %s" % (row.get("primary_source") or "", row.get("note") or "")
    match = POINTER.search(register_text)
    if match:
        window = register_text[max(0, match.start() - 40):match.start() + 60]
        return "pointed", "register", window.strip()
    found = pointer_in_rows(row["data_file"])
    if found:
        return "pointed", "ingest rows", found
    state = row.get("archival_state") or ""
    if state == "derived":
        return "not-applicable", "derived", ("built from files already in this "
                                             "repository; its provenance is the "
                                             "derivation chain, not a page number")
    if is_dataset(row):
        return "not-applicable", "dataset", ("the source is a dataset or export, whose "
                                             "pointer is a file and a variable rather "
                                             "than a table")
    if state == "not-archived":
        return "unverifiable", "document not held", ("a pointer would help a reader who "
                                                     "obtains it; this repository cannot "
                                                     "check one")
    return "unpointed", "nowhere", ("an extraction from a held document with no table "
                                    "pointer in the register and none in the produced "
                                    "table's own source column")


def main():
    rows = []
    for row in read_rows(REGISTER):
        verdict, where, evidence = classify(row)
        rows.append({
            "data_file": row["data_file"],
            "publisher": publisher_of(row),
            "archival_state": row.get("archival_state") or "",
            "primary_source": (row.get("primary_source") or "")[:120],
            "verdict": verdict,
            "pointer_checkable_here": checkable(row) if verdict == "pointed" else "n.a.",
            "pointer_found_in": where,
            "evidence_or_reason": evidence,
        })
    rows.sort(key=lambda r: (r["verdict"], r["publisher"], r["data_file"]))

    counts = {}
    for row in rows:
        counts[row["verdict"]] = counts.get(row["verdict"], 0) + 1
    unpointed = counts.get("unpointed", 0)
    pointed = counts.get("pointed", 0)
    scored = unpointed + pointed
    banner = [
        "CITATION POINTER AUDIT: can a reader find the FIGURE in the document, or only the",
        "document? One row per registered source. The denominator excludes rows that cannot",
        "have a table pointer - files derived inside this repository, and sources that are",
        "datasets rather than documents - because scoring those would inflate the gap with",
        "rows no citation could close. A pointer counts whether it is in the register row or",
        "in the produced table's own per-row source column; checking only the first is how",
        "this gap was previously overstated.",
        "%d of %d scored sources are pointed (%.0f%%); %d are not."
        % (pointed, scored, 100.0 * pointed / scored if scored else 0.0, unpointed),
    ]
    write_table(OUT, list(rows[0]), rows, banner=banner)
    print("Citation pointer audit -> %s" % OUT)
    for verdict in sorted(counts):
        print("   %-16s %d" % (verdict, counts[verdict]))
    by_check = {}
    for row in rows:
        if row["verdict"] == "pointed":
            key = row["pointer_checkable_here"].split(":")[0]
            by_check[key] = by_check.get(key, 0) + 1
    print("   of the pointed rows: %s"
          % ", ".join("%s %d" % (k, v) for k, v in sorted(by_check.items())))
    gaps = {}
    for row in rows:
        if row["verdict"] == "unpointed":
            gaps[row["publisher"]] = gaps.get(row["publisher"], 0) + 1
    if gaps:
        print("   unpointed by publisher: %s"
              % ", ".join("%s %d" % (k, v) for k, v in sorted(gaps.items(),
                                                              key=lambda kv: -kv[1])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
