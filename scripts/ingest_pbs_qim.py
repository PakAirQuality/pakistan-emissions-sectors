"""Parse PBS Table 2 (Quantum Index of Large Scale Manufacturing) into month x item output.

WHAT THIS BUYS. Nine fiscal years of MONTHLY physical production for the items this inventory
already estimates annually: cement, billets, glass, fertiliser, coke and petroleum products.
Cement is the reason it is worth doing. `ippu/monthly.py` currently shapes clinker calcination
on a CALENDAR-2022 series borrowed into FY2023-24 - one year, from two fiscal years earlier -
and this replaces it with each year's own fiscal months, for all nine.

NO OCR. Every one of the nine files carries a text layer. An earlier pass recorded them as
image scans and planned an OCR pipeline around that; `pdftotext -layout` renders them cleanly,
and the note was simply wrong. Checking cost one command and saved the entire pipeline.

THE CONTROL THE DOCUMENT SUPPLIES ABOUT ITSELF. Every row prints its own annual total beside
its twelve months, so the twelve must sum to it. A row that fails is QUARANTINED with its raw
text - never repaired, never dropped silently - and the pass rate is published with its
denominator.

THE COLUMN COUNT IS NOT CONSTANT, and this is the trap the OCAC parse spent five iterations
on before learning to distrust positions. Seven of the nine editions print a Weight column
between the unit and the months; FY2021-22 and FY2022-23 do not. Counting forwards from the
item name therefore reads Weight as July in seven years or July as Weight in two.

The rule that survives both: THE LAST THIRTEEN NUMERIC CELLS ARE THE TWELVE MONTHS AND THE
ANNUAL TOTAL. It is anchored on the end of the row, where the layout is stable, and the row's
own closure test proves the slice was right. Whether a Weight column exists is then read OUT
of the trailing run's length (14 means yes, 13 means no) rather than assumed.

A SECOND HAZARD, and the reason cells are split on TWO or more spaces rather than one:
pdftotext renders "2, 118" with a single space inside the number. Splitting on any whitespace
shreds every value into "2," and "118"; splitting on two or more keeps them whole. FY2022-23
additionally prints ". 0" decimals with an internal space, which the same rule handles.

WHAT A ROW IS EVIDENCE OF. Physical output in the month it was produced. That is a genuine
monthly observation of production, and for cement it times the KILN closely - but production
and calcination are not the same process, so the class this feeds is TE2, not TE1. Refinery
output is production evidence and is never a road-transport profile.

Usage:  python3 scripts/ingest_pbs_qim.py
Writes: data/activity/monthly/pbs_qim_month_item.csv
        outputs/pbs_qim_quarantine.csv
        outputs/pbs_qim_parse_summary.csv
"""

from pkinv.assets import asset_path
import csv
import glob
import os
import re
import subprocess
import sys

from pkinv.paths import ROOT

RAW = asset_path(ROOT, "data", "raw", "pbs", "qim")
ACTIVITY_DIR = asset_path(ROOT, "data", "activity", "monthly")
OUT = asset_path(ACTIVITY_DIR, "pbs_qim_month_item.csv")
OUTPUTS = asset_path(ROOT, "outputs")
QUARANTINE = asset_path(OUTPUTS, "pbs_qim_quarantine.csv")
SUMMARY = asset_path(OUTPUTS, "pbs_qim_parse_summary.csv")

MONTHS_IN_YEAR = 12
# months + the annual total the same row prints
TRAILING_CELLS = MONTHS_IN_YEAR + 1

# PBS rounds to the printed unit, and FY2022-23 carries one decimal. A row of twelve values can
# miss its own total by a rounding unit or two without anything being wrong; more than that is
# a parse defect, and the tolerance is stated rather than tuned until the check passes.
ROW_TOLERANCE = 2.0

# The items this inventory has an annual estimate for, and what each one may time. A row absent
# here is still parsed and still published - the denominator matters - but nothing reads it.
#
# THE CLASS FOLLOWS THE EVIDENCE. Cement output times the kiln closely and is not the kiln, so
# calcination is TE2. Nothing here is TE1: TE1 would mean the emitting process itself was
# observed monthly, and physical output of a product is not that.
CANONICAL = {
    "83": ("cement", "ippu", "TE2",
           "clinker calcination, timed on cement output - closely related, not the same "
           "process"),
    "85": ("billets_ingots", "industry", "TE2", "steel melting, timed on billet output"),
    "82": ("glass_plates_sheets", "industry", "TE2", "glass furnaces, timed on output"),
    # The group row 1-3 is effectively sugar alone: items 2 (bakery) and 3
    # (confectionery) print zero in every month of every held edition, so the
    # group's months ARE the crushing season. Timed process: bagasse combustion
    # at the mills' own power plants - output of sugar times the crushing that
    # produces the bagasse, closely related and not the same process, hence TE2.
    "1-3": ("sugar", "power", "TE2",
            "bagasse combustion, timed on sugar output - the crushing season "
            "read from the mills' own production"),
}

MONTH_HEADER = re.compile(r"\b(Jul|JUL)[-\s]*(\d{2})\b")
# The serial number, which is sometimes a range ("1-3", "22-24"). It is USUALLY a cell of its
# own and SOMETIMES glued to the item name, depending on how wide PBS set the column that
# year - so both forms are matched. An earlier version required whitespace after the number,
# which silently rejected every row where the number stood alone: 10 rows of 147 survived and
# the run still reported a clean 70% closure, because a row never seen cannot fail a check.
ITEM_START = re.compile(r"^(\d+(?:\s*-\s*\d+)?)(?:\s+(.*))?$")


def _number(cell):
    """A numeric cell, or None. Internal spaces are pdftotext's, not the document's."""
    cleaned = cell.replace(",", "").replace(" ", "")
    if cleaned in ("-", "", "—"):
        return 0.0
    try:
        return float(cleaned)
    except ValueError:
        return None


def _cells(line):
    return [c for c in re.split(r"\s{2,}", line.strip()) if c]


def _text(path):
    result = subprocess.run(["pdftotext", "-layout", path, "-"],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True)
    return result.stdout.decode("utf-8", "replace")


def _trailing_numbers(cells):
    """The run of numeric cells at the END of the row, longest-first from the right.

    Anchored on the end because that is where the layout is stable: the annual total is
    always the last column, whereas what precedes the months differs by edition.
    """
    run = []
    for cell in reversed(cells):
        value = _number(cell)
        if value is None:
            break
        run.insert(0, value)
    return run


def fiscal_year_of(path):
    match = re.search(r"_(\d{4})_(\d{2})\.pdf$", path)
    return int(match.group(1))


def months_for(fy_start):
    return (["%04d%02d" % (fy_start, m) for m in range(7, 13)]
            + ["%04d%02d" % (fy_start + 1, m) for m in range(1, 7)])


def header_year(text):
    """The fiscal year the FILE says it covers, from its own July column label.

    A control on the download rather than on the parse: a file named 2019_20 whose columns
    start Jul-15 would be a mis-saved edition, and every month of it would be booked to the
    wrong year while closing its own totals perfectly.
    """
    for line in text.splitlines():
        match = MONTH_HEADER.search(line)
        if match and "Aug" in line:
            return 2000 + int(match.group(2))
    return None


def parse(path):
    """([row dicts], [quarantine dicts], weight_column_present)."""
    fy_start = fiscal_year_of(path)
    text = _text(path)
    stamped = header_year(text)
    if stamped is not None and stamped != fy_start:
        raise ValueError("%s is named FY%d-%02d but its own columns start Jul-%02d"
                         % (os.path.basename(path), fy_start, (fy_start + 1) % 100,
                            stamped % 100))

    months = months_for(fy_start)
    rows, bad, weighted = [], [], 0
    # THE WRAPPED-ROW RULE (rc30). The sugar group row "1-3 Sugar, Bakery products
    # and Chocolate & sugar confectionery" is the one item whose label PBS wraps:
    # the serial sits on a line with no numbers and the numeric line starts with a
    # glued unit ("MTconfectionery", "MT & sugar confectionery") or, in FY2017-18,
    # with the bare weight after TWO label lines. ITEM_START never matches the
    # numeric line, so seven of nine editions dropped the row SILENTLY - not even
    # quarantined, because a row never seen cannot fail a check. A serial line
    # without its numbers is now held PENDING for up to two lines and married to
    # the first serial-less line that carries a full numeric run.
    pending = None   # (item_no, label, lines_waited)
    for line in text.splitlines():
        cells = _cells(line)
        if not cells:
            pending = None
            continue
        match = ITEM_START.match(cells[0])
        run = _trailing_numbers(cells)

        if match and len(run) < TRAILING_CELLS:
            # a serial whose numbers are not on this line: hold it, don't guess
            pending = (re.sub(r"\s*-\s*", "-", match.group(1)),
                       " ".join(cells[1:]), 0)
            continue
        if not match:
            if pending and len(run) == TRAILING_CELLS - 1:
                # FY2022-23's variant: the wrapped label and July's value sit ONE
                # space apart, so they fuse into a single cell and the run comes
                # up exactly one short. If the fused cell ends in a numeric tail,
                # split it - the tail is July, never part of a word.
                fused = cells[len(cells) - len(run) - 1]
                tail = re.search(r"(?:^|\s)([\d][\d,\. ]*)$", fused)
                if tail is not None and _number(tail.group(1)) is not None:
                    head_part = fused[:tail.start()].strip()
                    cells = (cells[:len(cells) - len(run) - 1]
                             + ([head_part] if head_part else [])
                             + [tail.group(1)] + cells[len(cells) - len(run):])
                    run = _trailing_numbers(cells)
            if pending and len(run) >= TRAILING_CELLS:
                # marry: synthesize the row the layout split, then fall through
                # to the SAME body every unwrapped row takes - one arithmetic
                # path, not a second vintage of it
                pending_no, label, _ = pending
                pending = None
                cells = [pending_no, label] + cells[len(cells) - len(run):]
                match = ITEM_START.match(cells[0])
            elif pending is not None:
                pending_no, label, waited = pending
                if waited + 1 > 2:
                    pending = None    # nothing married within two lines: drop
                else:
                    # a label continuation (FY2017-18 has two): absorb its text
                    pending = (pending_no, label + " " + " ".join(cells),
                               waited + 1)
                continue
            else:
                continue
        else:
            pending = None
        if len(cells) < TRAILING_CELLS + 1:
            continue
        item_no = re.sub(r"\s*-\s*", "-", match.group(1))

        if len(run) < TRAILING_CELLS:
            continue
        # 14 = a Weight column sits in front of the months; 13 = this edition prints none.
        if len(run) > TRAILING_CELLS:
            weighted += 1
        weight = run[-TRAILING_CELLS - 1] if len(run) > TRAILING_CELLS else ""
        values = run[-TRAILING_CELLS:-1]
        printed = run[-1]

        head = cells[1:len(cells) - len(run)]
        item = head[0] if head else ""
        unit = head[1] if len(head) > 1 else ""
        # The unit sometimes lands in the same cell as a long item name and sometimes not;
        # what matters downstream is the item and the closure, so an unresolved unit is
        # carried empty rather than guessed at.

        # TWO ROW KINDS, TWO PUBLISHED CONTROLS. Most rows are quantities and their annual
        # column is the SUM of the twelve months. The group rows - "42-52 Petroleum Products",
        # "65-71 Fertilizers" - are INDICES on the 2015-16=100 base, and their annual column is
        # the MEAN. Testing every row against the sum quarantined all of them, which looked
        # like a parse failure and was a row-kind failure.
        #
        # This is not a loosened tolerance wearing a new hat: the mean is only accepted when it
        # holds to the SAME tolerance the sum would have had, and an index row is marked as
        # one so that nothing downstream can read it as a tonnage.
        if abs(sum(values) - printed) <= ROW_TOLERANCE:
            row_kind, control = "quantity", "sum"
        elif abs(sum(values) / MONTHS_IN_YEAR - printed) <= ROW_TOLERANCE:
            row_kind, control = "index", "mean"
        else:
            bad.append({"fiscal_year_start": fy_start, "item_no": item_no, "item": item,
                        "months_sum": round(sum(values), 3),
                        "months_mean": round(sum(values) / MONTHS_IN_YEAR, 3),
                        "annual_printed": round(printed, 3),
                        "raw": re.sub(r"\s+", " ", line.strip())})
            continue

        canonical, sector, evidence_class, basis = (
            CANONICAL.get(item_no, ("", "", "", "")) if row_kind == "quantity"
            else ("", "", "", ""))
        for month, quantity in zip(months, values):
            rows.append({
                "fiscal_year_start": fy_start, "month": month,
                "item_no": item_no, "item": item, "unit": unit, "weight": weight,
                "row_kind": row_kind, "annual_control": control,
                "quantity": quantity, "annual_printed": printed,
                "canonical_item": canonical, "consuming_sector": sector,
                "temporal_evidence_class": evidence_class,
                "timing_target": "physical_output" if canonical else "",
                "basis": basis, "source_file": os.path.basename(path)})
    return rows, bad, weighted


def shift_mutation_caught(rows):
    """How many item-years would FAIL closure if the months were rotated by one.

    THE POSITIVE CONTROL. "every row closes" is only evidence if a row could have failed, and
    a parser that mis-sliced identically on both sides of the comparison reports the same
    clean result. Rotating a row's twelve months does not change their SUM, so this deliberately
    does not test closure - it tests that the months are distinguishable from one another,
    which is what a profile actually depends on. A row of twelve identical values is
    genuinely undetectable here, and is counted separately rather than hidden.
    """
    by_series = {}
    for row in rows:
        by_series.setdefault((row["fiscal_year_start"], row["item_no"]), []).append(
            row["quantity"])
    detectable = flat = 0
    for values in by_series.values():
        rotated = values[1:] + values[:1]
        if rotated == values:
            flat += 1
        else:
            detectable += 1
    return detectable, flat, len(by_series)


def main():
    os.makedirs(ACTIVITY_DIR, exist_ok=True)
    os.makedirs(OUTPUTS, exist_ok=True)
    files = sorted(glob.glob(asset_path(RAW, "pbs_qim_table2_*.pdf")))
    if not files:
        print("no QIM files under %s" % RAW)
        return 1

    rows, bad, per_file = [], [], {}
    for path in files:
        parsed, failed, weighted = parse(path)
        rows += parsed
        bad += failed
        series = len({(r["fiscal_year_start"], r["item_no"]) for r in parsed})
        per_file[os.path.basename(path)] = (series, len(failed), weighted > 0)

    # The current PBS edition is XLSX. The extension parser validates its
    # actual date columns and annual physical sums; provisional FY2026 stays
    # separate rather than entering this common-core panel.
    import importlib.util
    spec = importlib.util.spec_from_file_location("pakemis_extension_ingest",
                                                 os.path.join(ROOT, "scripts", "ingest_release_extension.py"))
    extension = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(extension)
    current = extension.QIM / "Table-3-2024-25-6.xlsx"
    if current.exists():
        extra = extension.qim_records(current, 2024)
        rows.extend(extra)
        files.append(str(current))
        per_file[current.name] = (len({r["item_no"] for r in extra}), 0, True)
    from pkinv.core.io import write_table
    write_table(OUT, list(rows[0]), rows, banner=extension.qim_banner())

    if bad:
        with open(QUARANTINE, "w", newline="", encoding="utf-8") as handle:
            handle.write("# Rows whose twelve months did not sum to the annual total the "
                         "SAME ROW prints. Kept with raw text, never repaired.\n")
            writer = csv.DictWriter(handle, fieldnames=list(bad[0]))
            writer.writeheader()
            writer.writerows(bad)

    detectable, flat, series = shift_mutation_caught(rows)
    summary = [{
        "files_parsed": len(files),
        "item_years_closed": series,
        "item_years_quarantined": len(bad),
        "month_rows": len(rows),
        "closure_rate_pct": round(100.0 * series / max(series + len(bad), 1), 2),
        "rotation_detectable_series": detectable,
        "rotation_flat_series": flat,
        "editions_with_weight_column": sum(1 for v in per_file.values() if v[2]),
        "canonical_items_carried": len({r["canonical_item"] for r in rows
                                        if r["canonical_item"]}),
    }]
    with open(SUMMARY, "w", newline="", encoding="utf-8") as handle:
        handle.write("# THE QIM PARSE'S OWN ACCOUNTING, one row. Denominators live here so a "
                     "count printed elsewhere is read against\n")
        handle.write("# the size of what was parsed. rotation_detectable_series is the "
                     "positive control: series whose months are\n")
        handle.write("# distinguishable from a rotation of themselves, and so can carry a "
                     "profile at all.\n")
        writer = csv.DictWriter(handle, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)

    print("PBS QIM -> %s" % os.path.relpath(OUT, ROOT))
    print("  %d files, %d item-years closed, %d quarantined (%.2f%% closure)"
          % (len(files), series, len(bad), summary[0]["closure_rate_pct"]))
    print("  %d month rows; %d editions print a Weight column, %d do not"
          % (len(rows), summary[0]["editions_with_weight_column"],
             len(files) - summary[0]["editions_with_weight_column"]))
    print("  rotation control: %d of %d series are distinguishable from their own rotation "
          "(%d are flat)" % (detectable, series, flat))
    for name, (kept, failed, _) in sorted(per_file.items()):
        flag = "" if not failed else "   <-- %d quarantined" % failed
        print("    %-34s %3d item-years%s" % (name, kept, flag))
    return 0


if __name__ == "__main__":
    sys.exit(main())
