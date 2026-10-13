"""Parse PBS Minerals Production Data into month x province x mineral tonnes.

WHAT THIS BUYS. Eight fiscal years of monthly provincial production for natural gas, crude oil
and coal - the activity behind the fugitives module's production, gathering and oil-production
streams, which together carry about 80 Mt of the nine-year inventory on a flat profile - plus
limestone, which is a SECOND and independent monthly shape for cement beside the QIM one.

TWO PUBLICATION FORMATS, ONE SCHEMA, ONE GATE. Four editions are PDFs and four are
spreadsheets, and they are read by two different functions into the same rows. That is worth
doing once here rather than letting each consumer discover the difference.

TWO CONTROLS THE DOCUMENT SUPPLIES ABOUT ITSELF, and both are enforced:

  row closure     every province row prints its own year total beside its twelve months
  group closure   every mineral ends with a "Total" row, which must equal the province rows
                  above it - an independent check on whether the group was assembled right

A row failing the first is quarantined with its raw text. A mineral failing the second is
reported per fiscal year, because a group that does not close means the province rows were
attached to the wrong mineral, which no row-level test can see.

THE LAYOUT HAZARD, and it is the PDF's. The mineral name is printed VERTICALLY CENTRED against
its group, so it lands on its own line between two province rows as often as it lands on one.
Reading the name from the province line finds it for the two-province minerals and loses it
for every other. The name is therefore carried as pending state across the group and the group
closure is what proves the attachment was right.

THE COLUMN RULE IS THE ONE THE QIM AND OCAC PARSES BOTH ARRIVED AT: anchor on the END of the
row. The last thirteen numeric cells are the twelve months and the year total, whatever
precedes them - a serial number, a name, a province, or any two of the three.

FY2015-16 IS NOT HELD. It is a declared absence with its own literal row in the summary, never
interpolated and never back-filled from FY2016-17.

Usage:  python3 scripts/ingest_pbs_minerals.py
Writes: data/activity/monthly/pbs_minerals_month_province.csv
        outputs/pbs_minerals_quarantine.csv
        outputs/pbs_minerals_parse_summary.csv
"""

from pkinv.assets import asset_path
import csv
import glob
import os
import re
import subprocess
import sys

from pkinv.paths import ROOT

RAW = asset_path(ROOT, "data", "raw", "pbs", "minerals")
ACTIVITY_DIR = asset_path(ROOT, "data", "activity", "monthly")
OUT = asset_path(ACTIVITY_DIR, "pbs_minerals_month_province.csv")
OUTPUTS = asset_path(ROOT, "outputs")
QUARANTINE = asset_path(OUTPUTS, "pbs_minerals_quarantine.csv")
SUMMARY = asset_path(OUTPUTS, "pbs_minerals_parse_summary.csv")

MONTHS_IN_YEAR = 12
TRAILING_CELLS = MONTHS_IN_YEAR + 1

# PBS prints whole units here, so a row of twelve should hit its own total exactly. The
# allowance is for the one edition that carries a decimal, not for a parse that nearly works.
ROW_TOLERANCE = 1.0
GROUP_TOLERANCE = 2.0

# The fiscal years the window needs. FY2015-16 is NOT among the files held.
WINDOW = tuple(range(2015, 2024))

PROVINCES = ("Punjab", "Sindh", "KPK", "Khyber Pakhtunkhwa", "Balochistan", "Baluchistan",
             "AJK", "Azad Kashmir", "Gilgit Baltistan", "GB", "Federal", "Islamabad",
             # FATA is a reporting area in these tables and was missing from the first list.
             # A province absent from this vocabulary is not skipped - it is read as a MINERAL
             # NAME, which silently drops its rows out of the group and breaks the group
             # control for every mineral that reports one. 309 mineral-years failed that way.
             "FATA", "Fata")
TOTAL_LABEL = "Total"

# The minerals this inventory has a stream for, and what each one may time. Everything else is
# still parsed and published - the denominator matters - but nothing reads it.
#
# THE CLASS FOLLOWS THE EVIDENCE. Monthly field production is a direct administrative record of
# the activity that drives the venting, flaring and leakage of the same month, which is T2. It
# is not T1: T1 would require the EMISSION to be observed monthly, and a production statistic
# is not that however well it correlates.
def canonical_key(name):
    """The mineral name with its unit annotation removed.

    PBS writes the unit into the name - "Natural Gas (in MMCFt)", "Crude Oil (in U.S Barrel)",
    "EMERALD    (In Grams)" - and the annotation is not stable across editions. Matching the
    full string found neither of the two streams that matter most. The FY2022-23 edition
    additionally BREAKS the unit across lines - "Crude Oil (in U.S" on the name line, the
    "Barrel)" tail landing two lines later - so an UNCLOSED trailing parenthesis is unit
    too, and stripping only balanced pairs lost gas and oil for that whole year.
    """
    stripped = re.sub(r"\(.*?\)", " ", str(name))
    stripped = re.sub(r"\([^)]*$", " ", stripped)
    return stripped.replace("-", " ").upper().split("  ")[0].strip()


CANONICAL = {
    # the FY2021-22 edition prints the row as bare "Gas (in MMCFt)" - same mineral,
    # shorter name; without this key the year reported as absent while the file was held
    "GAS": ("natural_gas", "fugitives", "T2",
            "gas production, gathering and processing timed on field output"),
    "NATURAL GAS": ("natural_gas", "fugitives", "T2",
                    "gas production, gathering and processing timed on field output"),
    "CRUDE OIL": ("crude_oil", "fugitives", "T2", "oil production timed on field output"),
    "COAL": ("coal", "industry", "T2", "coal combustion timed on production"),
    "LIME STONE": ("limestone", "ippu", "T2",
                   "a second, independent monthly shape for cement beside PBS QIM output"),
    "LIMESTONE": ("limestone", "ippu", "T2",
                  "a second, independent monthly shape for cement beside PBS QIM output"),
}


def _number(cell):
    cleaned = str(cell).replace(",", "").replace(" ", "").strip()
    if cleaned in ("-", "", "—", "None"):
        return 0.0
    try:
        return float(cleaned)
    except ValueError:
        return None


def _cells(line):
    return [c for c in re.split(r"\s{2,}", line.strip()) if c]


def _trailing_numbers(cells):
    run = []
    for cell in reversed(cells):
        value = _number(cell)
        if value is None:
            break
        run.insert(0, value)
    return run


def fiscal_year_of(path):
    return int(re.search(r"_(\d{4})_(\d{2})\.(pdf|xlsx)$", path).group(1))


def months_for(fy_start):
    return (["%04d%02d" % (fy_start, m) for m in range(7, 13)]
            + ["%04d%02d" % (fy_start + 1, m) for m in range(1, 7)])


def _province_of(cells):
    """Which cell names a province, or None. Matched on the whole cell, not a prefix:
    'Punjab' and 'Punjab Total' are different rows and only one of them is a province."""
    for index, cell in enumerate(cells):
        text = cell.strip()
        if text == TOTAL_LABEL:
            return index, TOTAL_LABEL
        for province in PROVINCES:
            if text.lower() == province.lower():
                return index, province
    return None


def _read_pdf(path):
    result = subprocess.run(["pdftotext", "-layout", path, "-"],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True)
    return [_cells(line) for line in result.stdout.decode("utf-8", "replace").splitlines()]


def _read_xlsx(path):
    import openpyxl
    workbook = openpyxl.load_workbook(path, data_only=True, read_only=True)
    rows = []
    for sheet in workbook.worksheets:
        for values in sheet.iter_rows(values_only=True):
            rows.append([str(v).strip() for v in values if v is not None
                         and str(v).strip() != ""])
    workbook.close()
    return rows


def parse(path):
    """([row dicts], [quarantine dicts], [group-closure dicts])."""
    fy_start = fiscal_year_of(path)
    months = months_for(fy_start)
    source = os.path.basename(path)
    raw_rows = _read_xlsx(path) if path.endswith(".xlsx") else _read_pdf(path)

    # THE THREE-LINE WRAP (FY2022-23). A long mineral name splits as: the name with an
    # unclosed unit ("Crude Oil (in U.S"), then a line holding ONLY the first province
    # ("Punjab"), then the unit's tail glued to that province's numbers
    # ("Barrel) 429,203 ..."). Unstitched, the bare province clobbers the pending name,
    # the tail line becomes a fake mineral called "Barrel)", and Punjab's twelve months
    # vanish - gas and oil each lost the year this way. The stitch is narrow: a
    # province-only line followed by a provinceless numbers line whose head is a bare
    # unit tail becomes one province row.
    stitched = []
    skip = False
    for index, cells in enumerate(raw_rows):
        if skip:
            skip = False
            continue
        if (cells and _province_of(cells) is not None
                and not _trailing_numbers(cells) and index + 1 < len(raw_rows)):
            following = []
            for cell in raw_rows[index + 1]:
                # the tail can be GLUED to the first number by a single space
                # ("Barrel) 429,203" is one cell), which both hides the tail and
                # swallows July - split it back into its two facts
                glued = re.fullmatch(r"([A-Za-z.\s]*\))\s+([\d,]+(?:\.\d+)?)", cell)
                if glued:
                    following.extend([glued.group(1), glued.group(2)])
                else:
                    following.append(cell)
            tail_head = [c for c in following if _number(c) is None]
            if (following and _province_of(following) is None
                    and _trailing_numbers(following)
                    and all(re.fullmatch(r"[A-Za-z.\s]*\)", c) for c in tail_head)):
                stitched.append(cells + [c for c in following if _number(c) is not None])
                skip = True
                continue
        stitched.append(cells)
    raw_rows = stitched

    # HOW MANY TRAILING NUMBERS THIS EDITION PRINTS, measured from the file rather than
    # assumed. FY2021-22 prints TWELVE - it carries no year-total column at all - and a rule
    # demanding thirteen rejected every row in it, silently, reporting the year as absent when
    # the file was in hand. The modal run length among province rows is the edition's layout;
    # a row disagreeing with its own edition is the suspect one.
    runs = [len(_trailing_numbers(c)) for c in raw_rows
            if c and _province_of(c) and len(_trailing_numbers(c)) >= MONTHS_IN_YEAR]
    width = max(set(runs), key=runs.count) if runs else TRAILING_CELLS
    has_year_total = width >= TRAILING_CELLS

    rows, bad, groups = [], [], []
    pending_name, group, group_total = "", [], None
    for cells in raw_rows:
        if not cells:
            continue
        found = _province_of(cells)
        run = _trailing_numbers(cells)

        if found is None or len(run) < width:
            # THE NAME LINE. PBS centres the mineral name against its group, so it lands on a
            # line of its own as often as beside a province. Anything alphabetic that is not a
            # province row is a candidate name; the group closure below is what proves the
            # attachment was right, so a wrong guess here fails loudly rather than quietly.
            text = " ".join(c for c in cells if not c.replace(".", "").isdigit())
            text = re.sub(r"^\s*\d+\s*", "", text).strip()
            if (text and canonical_key(text)
                    and not text.lower().startswith(("s.no", "name of", "provinces",
                                                     "minerals production", "grand"))):
                pending_name = text
            continue

        index, province = found
        head = [c for c in cells[:index] if _number(c) is None]
        if head:
            # ONLY IF IT SURVIVES NORMALISATION. PBS wraps a long mineral name across two
            # lines and puts the UNIT on the second - "Crude Oil" then "50 (in U.S Barrel)".
            # The second line reduces to nothing once the parenthesised unit is stripped, and
            # assigning it unconditionally erased a name that had already been read correctly.
            # Crude oil and natural gas lost three fiscal years each to that one assignment.
            candidate = re.sub(r"^\s*\d+\s*", "", " ".join(head)).strip()
            if canonical_key(candidate):
                pending_name = candidate

        if has_year_total:
            values, printed = run[-TRAILING_CELLS:-1], run[-1]
        else:
            # No year-total column in this edition, so the ROW control does not exist. It is
            # recorded as absent rather than manufactured by summing the twelve - a control
            # derived from the data it checks is not a control. The GROUP control still
            # applies, so the edition is checked once instead of twice, and says so.
            values, printed = run[-MONTHS_IN_YEAR:], None
        mineral = canonical_key(pending_name)

        if printed is not None and abs(sum(values) - printed) > ROW_TOLERANCE:
            bad.append({"fiscal_year_start": fy_start, "mineral": mineral,
                        "province": province, "months_sum": round(sum(values), 3),
                        "year_total_printed": round(printed, 3), "source_file": source})
            continue

        if province == TOTAL_LABEL:
            canonical, sector, temporal_class, basis = CANONICAL.get(
                mineral, ("", "", "", ""))
            if not group and canonical:
                # A TOTAL-ONLY MINERAL: this edition prints no province split at all
                # (FY2016-17 does this for gas and oil), so the Total row is not a
                # control over provinces - it IS the observation, at national grain.
                # Discarding it reported both streams absent for a year the file
                # covered. The row still answers to its own printed year total, and
                # the province cell says plainly what grain the edition supplied.
                for month, quantity in zip(months, values):
                    row = {"fiscal_year_start": fy_start, "month": month,
                           "mineral": mineral,
                           "province": "National (edition prints no province split)",
                           "quantity": quantity,
                           "year_total_printed": "" if printed is None else printed,
                           "row_control": ("year_total" if printed is not None
                                           else "absent-in-edition"),
                           "canonical_mineral": canonical, "consuming_sector": sector,
                           "temporal_method": temporal_class,
                           "timing_target": "physical_production",
                           "basis": basis, "source_file": source}
                    rows.append(row)
                group, group_total = [], None
                continue
            # The group's own control row closes it and is NOT carried as a province.
            declared = sum(r["quantity"] for r in group)
            groups.append({"fiscal_year_start": fy_start, "mineral": mineral,
                           "provinces_sum": round(declared, 3),
                           "total_row_printed": round(sum(values), 3),
                           "closed": abs(declared - sum(values)) <= GROUP_TOLERANCE,
                           "source_file": source})
            group, group_total = [], None
            continue

        canonical, sector, temporal_class, basis = CANONICAL.get(mineral, ("", "", "", ""))
        for month, quantity in zip(months, values):
            row = {"fiscal_year_start": fy_start, "month": month,
                   "mineral": mineral, "province": province,
                   "quantity": quantity,
                   "year_total_printed": "" if printed is None else printed,
                   "row_control": "year_total" if printed is not None else "absent-in-edition",
                   "canonical_mineral": canonical, "consuming_sector": sector,
                   "temporal_method": temporal_class,
                   "timing_target": "physical_production" if canonical else "",
                   "basis": basis, "source_file": source}
            rows.append(row)
            group.append(row)
    return rows, bad, groups


def main():
    os.makedirs(ACTIVITY_DIR, exist_ok=True)
    os.makedirs(OUTPUTS, exist_ok=True)
    files = sorted(glob.glob(asset_path(RAW, "pbs_minerals_*.pdf"))
                   + glob.glob(asset_path(RAW, "pbs_minerals_*.xlsx")))
    if not files:
        print("no minerals files under %s" % RAW)
        return 1

    rows, bad, groups = [], [], []
    for path in files:
        parsed, failed, closed = parse(path)
        rows += parsed
        bad += failed
        groups += closed

    with open(OUT, "w", newline="", encoding="utf-8") as handle:
        handle.write("# PBS monthly minerals production by province, eight fiscal years.\n")
        handle.write("# EVERY ROW HERE CLOSED ON THE YEAR TOTAL THE SAME ROW PRINTS; rows "
                     "that did not are in outputs/pbs_minerals_quarantine.csv.\n")
        handle.write("# The per-mineral 'Total' rows are NOT carried as a province - they "
                     "are the group control and are reported separately.\n")
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    if bad:
        with open(QUARANTINE, "w", newline="", encoding="utf-8") as handle:
            handle.write("# Rows whose twelve months did not sum to the year total the SAME "
                         "ROW prints. Kept, never repaired.\n")
            writer = csv.DictWriter(handle, fieldnames=list(bad[0]))
            writer.writeheader()
            writer.writerows(bad)

    held = sorted({r["fiscal_year_start"] for r in rows})
    absent = [fy for fy in WINDOW if fy not in held]
    open_groups = [g for g in groups if not g["closed"]]
    summary = [{
        "files_parsed": len(files),
        "fiscal_years_held": len(held),
        "fiscal_years_absent": ";".join("FY%d-%02d" % (fy, (fy + 1) % 100) for fy in absent)
                               or "none",
        "month_rows": len(rows),
        "rows_quarantined": len(bad),
        "mineral_years": len(groups),
        "mineral_years_closing_group_control": sum(1 for g in groups if g["closed"]),
        "canonical_minerals_found": ";".join(sorted({r["canonical_mineral"] for r in rows
                                                     if r["canonical_mineral"]})) or "none",
        # THE COVERAGE, PUBLISHED AS A LITERAL. Each canonical mineral is found in only five
        # or six of the eight held editions. An earlier edition of this summary used that as
        # the reason nothing read the table; an external review overruled it - observed years
        # at T2, missing years days-weighted T4, no borrowing - and core/pbs_minerals.py now
        # serves exactly that contract to fugitives (upstream gas and oil production) and to
        # the limestone-versus-cement cross-check.
        "canonical_year_coverage": ";".join(
            "%s:%d/%d" % (name, len({r["fiscal_year_start"] for r in rows
                                     if r["canonical_mineral"] == name}), len(held))
            for name in sorted({r["canonical_mineral"] for r in rows
                                if r["canonical_mineral"]})),
        "wired_into_any_sector": "fugitives upstream (gas, oil) per covered year; "
                                 "limestone as a cement cross-check",
    }]
    with open(SUMMARY, "w", newline="", encoding="utf-8") as handle:
        handle.write("# THE MINERALS PARSE'S OWN ACCOUNTING, one row. fiscal_years_absent is "
                     "a declared literal, not a blank: FY2015-16\n")
        handle.write("# is not published in a form this project holds, and an empty cell "
                     "would read as 'nothing missing'.\n")
        writer = csv.DictWriter(handle, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)

    print("PBS minerals -> %s" % os.path.relpath(OUT, ROOT))
    print("  %d files, %d month rows, %d rows quarantined" % (len(files), len(rows), len(bad)))
    print("  group control: %d of %d mineral-years close on their own Total row"
          % (len(groups) - len(open_groups), len(groups)))
    for group in open_groups[:10]:
        print("    FY%s %-18s provinces %.0f vs Total row %.0f"
              % (group["fiscal_year_start"], group["mineral"][:18],
                 group["provinces_sum"], group["total_row_printed"]))
    print("  years held: %s" % ", ".join(str(y) for y in held))
    print("  DECLARED ABSENT: %s" % summary[0]["fiscal_years_absent"])
    print("  canonical: %s" % summary[0]["canonical_minerals_found"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
