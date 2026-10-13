"""Parse APCMA's monthly cement despatches, and check them against PBS's QIM production.

WHAT THIS IS FOR, AND WHAT IT IS NOT. Cement already takes its monthly shape from PBS Table 2,
its own fiscal-year output, class TE2 in all nine years. It does not need a second source to
shape it and does not get one. What APCMA buys is a CHECK: the industry association counts
DESPATCHES leaving the factory gate, PBS counts PRODUCTION, and the two are compiled by
different bodies from different returns. If cement's seasonality looks the same from both, the
QIM shape is standing on something.

DESPATCHES ARE NOT PRODUCTION, so the comparison is on SHAPE ALONE. Cement moves into and out
of stock between the kiln and the gate, and exports are dispatched on a shipping schedule
rather than a kiln one. Comparing magnitudes would be comparing two different quantities;
comparing normalised twelve-month shares asks the question that actually has an answer.

THREE CONTROLS, and the third is free. Each row prints its own Total across the four regional
columns; each block prints an annual Total across its twelve months; and because every file
carries the reported year AND its predecessor, five of the years appear TWICE across the five
files and the two copies must agree.

THE YEAR IS READ FROM THE BLOCK, not the filename. Each block is preceded by its own
"2015 - 2016" label, and a file named 1516 contains 2014-2015 as well.

A SOURCE DEFECT THIS FINDS RATHER THAN REPAIRS. FY2015-16's South Export annual total is
printed "2,02,989" where its own twelve months sum to 2,020,569 - a digit-grouping error in
the published page. The months are internally consistent and the printed total is not, so the
column control fails, the row is quarantined with its raw text, and nothing is corrected.

Usage:  python3 scripts/ingest_apcma_dispatches.py
Writes: data/activity/monthly/apcma_month_region_dispatch.csv
        outputs/apcma_dispatch_quarantine.csv
        outputs/apcma_dispatch_parse_summary.csv
        outputs/apcma_qim_cement_crosscheck.csv
"""

from pkinv.assets import asset_path
import collections
import csv
import glob
import os
import re
import sys

from pkinv.paths import DATA, OUTPUTS, ROOT

RAW = asset_path(ROOT, "data", "raw", "apcma")
ACTIVITY_DIR = asset_path(DATA, "activity", "monthly")
OUT = asset_path(ACTIVITY_DIR, "apcma_month_region_dispatch.csv")
QUARANTINE = asset_path(OUTPUTS, "apcma_dispatch_quarantine.csv")
SUMMARY = asset_path(OUTPUTS, "apcma_dispatch_parse_summary.csv")
CROSSCHECK = asset_path(OUTPUTS, "apcma_qim_cement_crosscheck.csv")

MONTHS = ("July", "August", "September", "October", "November", "December",
          "January", "February", "March", "April", "May", "June")
# The four data columns in the order the page prints them, under the North/South header.
COLUMNS = (("North", "local"), ("North", "export"), ("South", "local"), ("South", "export"))

YEAR = re.compile(r"^(20\d\d)\s*-\s*(20\d\d)$")
ROW_TOLERANCE = 1.0
COLUMN_TOLERANCE = 1.0
# Two copies of one year come off two different pages of the same publication; they should be
# identical, and a tolerance here is for nothing but float noise.
DUPLICATE_TOLERANCE = 1.0

# The fiscal years this inventory reports.
WINDOW = tuple(range(2015, 2024))


def _number(cell):
    cleaned = cell.replace(",", "").replace("&nbsp;", "").strip()
    if cleaned in ("", "-", "–"):
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _cells(row_html):
    out = []
    for cell in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row_html, re.S | re.I):
        text = re.sub(r"<[^>]+>", "", cell).replace("&nbsp;", " ")
        out.append(re.sub(r"\s+", " ", text).strip())
    return out


def parse(path):
    """([row dicts], [quarantine dicts]) for every year-block in one page."""
    text = open(path, encoding="utf-8", errors="replace").read()
    source = os.path.basename(path)
    rows, bad = [], []
    fy_start, pending, collecting = None, [], False
    for chunk in re.findall(r"<tr[^>]*>(.*?)</tr>", text, re.S | re.I):
        cells = [c for c in _cells(chunk) if c]
        if not cells:
            continue
        match = YEAR.match(cells[0])
        if match:
            _flush(fy_start, pending, rows, bad, source)
            fy_start, pending, collecting = int(match.group(1)), [], True
            continue
        if not collecting:
            continue
        values = [_number(c) for c in cells[1:]]
        if cells[0] in MONTHS and len(values) >= len(COLUMNS) + 1 and None not in \
                values[:len(COLUMNS) + 1]:
            pending.append((cells[0], values[:len(COLUMNS) + 1]))
        elif cells[0].lower().startswith("total") and len(values) >= len(COLUMNS) + 1:
            # A BLOCK ENDS AT ITS OWN TOTAL ROW, and this is not tidiness. Every page carries
            # FURTHER tables below the two despatch blocks - per-channel or per-company
            # breakdowns with their own July..June rows - and without this the last block
            # swallowed them, arrived with twenty month rows, and was discarded whole. Two
            # fiscal years disappeared that way while the parse reported no row-level failure.
            pending.append(("TOTAL", values[:len(COLUMNS) + 1]))
            _flush(fy_start, pending, rows, bad, source)
            fy_start, pending, collecting = None, [], False
    _flush(fy_start, pending, rows, bad, source)
    return rows, bad


def _flush(fy_start, pending, rows, bad, source):
    """Apply both controls to one year-block and emit it."""
    if fy_start is None or not pending:
        return
    months = [(name, values) for name, values in pending if name in MONTHS]
    totals = [values for name, values in pending if name == "TOTAL"]
    if len(months) != len(MONTHS):
        bad.append({"fiscal_year_start": fy_start, "scope": "block", "column": "",
                    "months_sum": "", "printed": "",
                    "raw": "block has %d month rows, not 12" % len(months),
                    "source_file": source})
        return

    kept = []
    for name, values in months:
        index = MONTHS.index(name)
        month = "%04d%02d" % (fy_start + (0 if index < 6 else 1),
                              7 + index if index < 6 else index - 5)
        parts, printed = values[:len(COLUMNS)], values[len(COLUMNS)]
        if abs(sum(parts) - printed) > ROW_TOLERANCE:
            bad.append({"fiscal_year_start": fy_start, "scope": "row", "column": name,
                        "months_sum": round(sum(parts), 1), "printed": round(printed, 1),
                        "raw": "%s: %s vs printed %s" % (name, parts, printed),
                        "source_file": source})
            continue
        for (region, channel), tonnes in zip(COLUMNS, parts):
            kept.append({"fiscal_year_start": fy_start, "month": month,
                         "region": region, "channel": channel, "tonnes": tonnes,
                         "row_total_printed": printed, "source_file": source})

    # THE COLUMN CONTROL, which is what catches the published digit-grouping error.
    if totals:
        printed_totals = totals[0]
        for index, (region, channel) in enumerate(COLUMNS):
            summed = sum(r["tonnes"] for r in kept
                         if r["region"] == region and r["channel"] == channel)
            if abs(summed - printed_totals[index]) > COLUMN_TOLERANCE:
                bad.append({"fiscal_year_start": fy_start, "scope": "column",
                            "column": "%s %s" % (region, channel),
                            "months_sum": round(summed, 1),
                            "printed": round(printed_totals[index], 1),
                            "raw": "twelve months sum to %.0f against a printed %.0f"
                                   % (summed, printed_totals[index]),
                            "source_file": source})
    rows.extend(kept)


def duplicate_agreement(rows):
    """[(fy, month, region, channel, a, b)] where two files disagree about one cell.

    Every page carries its own year and the one before it, so five in-window years are
    published twice. Two copies of one number from one publisher are the cheapest control
    there is, and it costs nothing to demand they agree.
    """
    seen = collections.defaultdict(dict)
    clashes = []
    for row in rows:
        key = (row["fiscal_year_start"], row["month"], row["region"], row["channel"])
        previous = seen[key].get("tonnes")
        if previous is not None and abs(previous - row["tonnes"]) > DUPLICATE_TOLERANCE:
            clashes.append(key + (previous, row["tonnes"]))
        seen[key]["tonnes"] = row["tonnes"]
    return clashes


def crosscheck(rows):
    """APCMA despatch shape against QIM production shape, as normalised twelve-month shares."""
    from pkinv.core import pbs_qim

    despatch = collections.defaultdict(float)
    for row in rows:
        despatch[(row["fiscal_year_start"], row["month"])] += row["tonnes"]

    out = []
    for fy_start in sorted({fy for fy, _m in despatch}):
        if fy_start not in WINDOW or not pbs_qim.covers(pbs_qim.CEMENT, fy_start):
            continue
        theirs = pbs_qim.profile(pbs_qim.CEMENT, fy_start)
        mine = {month: value for (fy, month), value in despatch.items() if fy == fy_start}
        total = sum(mine.values())
        if len(mine) != 12 or not total:
            continue
        for month in sorted(theirs):
            apcma = mine.get(month, 0.0) / total
            out.append({
                "fiscal_year_start": fy_start, "month": month,
                "apcma_despatch_share": round(apcma, 6),
                "qim_production_share": round(theirs[month], 6),
                "difference_pp": round(100 * (apcma - theirs[month]), 4),
                "compares": "shape only - despatches are sales and QIM is production",
            })
    return out


def main():
    os.makedirs(ACTIVITY_DIR, exist_ok=True)
    os.makedirs(OUTPUTS, exist_ok=True)
    files = sorted(glob.glob(asset_path(RAW, "apcma_dispatches_*.html")))
    if not files:
        print("no APCMA pages under %s" % RAW)
        return 1

    rows, bad = [], []
    for path in files:
        parsed, failed = parse(path)
        rows += parsed
        bad += failed

    clashes = duplicate_agreement(rows)
    for fy, month, region, channel, first, second in clashes:
        bad.append({"fiscal_year_start": fy, "scope": "duplicate-year",
                    "column": "%s %s" % (region, channel),
                    "months_sum": first, "printed": second,
                    "raw": "%s published twice as %.0f and %.0f" % (month, first, second),
                    "source_file": "two pages"})

    # De-duplicate AFTER the agreement check: the same cell from two pages is one cell.
    unique = {}
    for row in rows:
        unique[(row["fiscal_year_start"], row["month"], row["region"], row["channel"])] = row
    rows = [unique[key] for key in sorted(unique)]

    with open(OUT, "w", newline="", encoding="utf-8") as handle:
        handle.write("# APCMA monthly cement DESPATCHES by region and channel.\n")
        handle.write("# DESPATCHES ARE SALES, not production and not clinker calcination. "
                     "NOTHING SHAPES A PROFILE FROM THIS FILE: cement takes\n")
        handle.write("# its months from PBS QIM, and this exists to check that shape against "
                     "an independently compiled one.\n")
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    if bad:
        with open(QUARANTINE, "w", newline="", encoding="utf-8") as handle:
            handle.write("# Cells failing one of the three controls. Kept with their raw "
                         "text, never repaired.\n")
            handle.write("# scope=row: the four regional columns do not reach the row's own "
                         "printed Total.\n")
            handle.write("# scope=column: the twelve months do not reach the block's printed "
                         "annual Total - this is where APCMA's own\n")
            handle.write("#              digit-grouping error in FY2015-16 South Export "
                         "surfaces.\n")
            handle.write("# scope=duplicate-year: two pages of the publication disagree about "
                         "one cell.\n")
            writer = csv.DictWriter(handle, fieldnames=list(bad[0]))
            writer.writeheader()
            writer.writerows(bad)

    comparisons = crosscheck(rows)
    if comparisons:
        with open(CROSSCHECK, "w", newline="", encoding="utf-8") as handle:
            handle.write("# APCMA despatch shape against PBS QIM production shape, as "
                         "normalised twelve-month shares.\n")
            handle.write("# SHAPE ONLY. Cement moves into and out of stock between kiln and "
                         "gate and exports follow a shipping schedule,\n")
            handle.write("# so the magnitudes are different quantities and only the "
                         "seasonality is a question with an answer.\n")
            writer = csv.DictWriter(handle, fieldnames=list(comparisons[0]))
            writer.writeheader()
            writer.writerows(comparisons)

    years = sorted({r["fiscal_year_start"] for r in rows})
    in_window = [y for y in years if y in WINDOW]
    summary = [{
        "pages_parsed": len(files),
        "year_blocks": len(years),
        "fiscal_years_in_window": len(in_window),
        "window_years": ";".join("FY%d-%02d" % (y, (y + 1) % 100) for y in in_window),
        "month_cells": len(rows),
        "cells_quarantined": len(bad),
        "duplicate_year_clashes": len(clashes),
        "crosscheck_months": len(comparisons),
        "crosscheck_years": len({c["fiscal_year_start"] for c in comparisons}),
    }]
    with open(SUMMARY, "w", newline="", encoding="utf-8") as handle:
        handle.write("# THE APCMA PARSE'S OWN ACCOUNTING, one row. duplicate_year_clashes is "
                     "the third control: five in-window years are\n")
        handle.write("# published twice across the five pages and the two copies must agree.\n")
        writer = csv.DictWriter(handle, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)

    print("APCMA despatches -> %s" % os.path.relpath(OUT, ROOT))
    print("  %d pages, %d year-blocks, %d in the window: %s"
          % (len(files), len(years), len(in_window), summary[0]["window_years"]))
    print("  %d month cells, %d quarantined" % (len(rows), len(bad)))
    print("  duplicate-year control: %d clashes across the years published twice" % len(clashes))
    for row in bad[:6]:
        print("    %s FY%s %-16s %s" % (row["scope"], row["fiscal_year_start"],
                                        row["column"], row["raw"][:64]))
    if comparisons:
        worst = max(abs(c["difference_pp"]) for c in comparisons)
        mean = sum(abs(c["difference_pp"]) for c in comparisons) / len(comparisons)
        print("  shape cross-check against QIM: %d months over %d years"
              % (len(comparisons), summary[0]["crosscheck_years"]))
        print("    mean absolute difference %.2f percentage points, worst %.2f" % (mean, worst))
    return 0


if __name__ == "__main__":
    import sys as _sys
    if "--check" in _sys.argv[1:]:
        # re-derive into a temporary directory and compare; nothing in the tree is written
        from pkinv.core.checkmode import compare_only
        _sys.exit(compare_only(globals(), ("OUT", "QUARANTINE", "SUMMARY", "CROSSCHECK"), main))
    sys.exit(main())
