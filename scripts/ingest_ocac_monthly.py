"""Check the OCAC panel's differenced months against OCAC's own directly published ones.

WHAT THIS IS NOT. It is NOT a second activity table, and it deliberately writes nothing into
data/activity/. The panel this project already ships - data/activity/transport/
ocac_sectoral_provincial.csv, built by scripts/ingest_ocac_sectoral.py from the editions in
sources/Aviation/ocac_monthly/ - already carries every month, every province and all ten
sector rows. This file started life as a second ingest of it, which is the defect this
repository has now found roughly a dozen times: a second arithmetic path is a second vintage
waiting to disagree. Demoting it to a check is the fix.

WHAT IT IS FOR. The panel recovers most months by DIFFERENCING consecutive cumulative
year-to-date editions ("JULY - DECEMBER 2023"), an identity that core/ocac_monthly.py
documents carefully and that four modules - transport, railways, power, industry - depend on.
OCAC also publishes a SINGLE-MONTH edition of those same months ("DECEMBER, 2023"), and the
media library still serves them. Those are an independent measurement of the same quantity,
so the differencing can be tested rather than trusted. It is: 144 comparisons across four
customer classes and three fiscal years.

WHAT THIS BUYS. These reports time fuel SALES for road transport, railways, domestic
aviation, industrial liquids, liquid-fuel power and agricultural machinery. July 2021
through June 2024.

TWO CONTROLS THE DOCUMENT SUPPLIES ABOUT ITSELF, and both are enforced rather than trusted:

  row closure     every sector row prints a TOTAL beside its products, so the products must
                  sum to it
  sector closure  "A. TOTAL INTERNAL VOL M.TONS" is the sum of the sector totals above it

A page failing either is QUARANTINED with its raw text, never repaired and never silently
dropped. The pass rate is printed, because a parse whose failures are invisible is a parse
nobody can size.

WHAT A ROW IS EVIDENCE OF. Sales, and the registry must say so: a tonne sold in June is not
a tonne burned in June, and this file's output feeds `timing_target = fuel_sale`, never
`emitting_process`. The distinction is the reason temporal_profiles carries that column.

THE REVISION TRAP, handled upstream and restated here because it is easy to undo. Nine of the
36 months were re-uploaded by OCAC under -1..-4 suffixes; the HIGHEST suffix is the current
edition and the unsuffixed file is the superseded first upload. scripts/fetch_ocac_monthly.py
resolves that and records which is which; this parser reads the files that fetcher chose.

FIVE PARSING DEFECTS, each hidden behind the last, and the sequence is recorded because each
one closed the national control a little further and only the last one closed it:

  1  the report prints the whole table TWICE, energy then non-energy, under identical AREA
     headers, so the non-energy "A. TOTAL INTERNAL" (~25,000 t) overwrote the real control
  2  the product set is not constant across EDITIONS, so a fixed ten-column slice put the
     TOTAL inside the products
  3  "Others" appears under INDUSTRY and again under GOVERNMENT; the label alone is ambiguous
  4  OVERSEAS/FOREIGN was not a recognised heading, so the overseas Aviation and Bunkers rows
     were still tagged GOVERNMENT and added B. TOTAL OVERSEAS on top of A. TOTAL INTERNAL -
     the one per cent overshoot, and neither of the two causes guessed at beforehand
  5  the number of trailing CONTROL columns is not constant across PAGES either (Pakistan
     prints this month and last year's, a province prints one), and a lone footnote asterisk
     parsed as 0.0 and shifted every value after it one column right

Fixes 4 and 5 are the ones worth remembering: both were scope errors wearing the costume of
arithmetic errors. Nothing here was settled by widening a tolerance - a tolerance chosen to
make a check succeed is not a check.

RESULT: 36 of 36 months close on BOTH published controls, A. TOTAL INTERNAL and B. TOTAL
OVERSEAS. Two rows of 6,057 are quarantined because OCAC's own arithmetic does not close on
them - Balochistan Road, July 2023, prints 5 + 6,814 + 5,435 against a stated 12,118 - and
they are kept with their raw text rather than repaired.

Usage:  python3 scripts/ingest_ocac_monthly.py
Writes: outputs/ocac_direct_edition_crosscheck.csv   the differenced month against the
                                                     published month, per comparison
        outputs/ocac_direct_edition_quarantine.csv   rows failing the document's own control
"""

from pkinv.assets import asset_path
import csv
import glob
import hashlib
import os
import re
import subprocess
import sys

from pkinv.paths import ROOT

RAW = asset_path(ROOT, "data", "raw", "ocac", "monthly_sector_province")
# outputs/, NOT data/activity/. A check belongs beside the other published diagnostics; a file
# under data/activity/ is a source, and something would eventually read it as one.
OUT_DIR = asset_path(ROOT, "outputs")
OUT = asset_path(OUT_DIR, "ocac_direct_edition_crosscheck.csv")
QUARANTINE = asset_path(OUT_DIR, "ocac_direct_edition_quarantine.csv")
CURRENCY = asset_path(OUT_DIR, "ocac_edition_currency.csv")
SUMMARY = asset_path(OUT_DIR, "ocac_parse_summary.csv")
PANEL_EDITIONS = asset_path(ROOT, "sources", "Aviation", "ocac_monthly")

# The customer classes to test the differencing on, and the products each one is read through.
# Chosen because they are what the four dependent modules actually ask the panel for.
CROSSCHECK_CASES = (
    ("Road", ("MS", "HOBC")), ("Road", ("HSD",)),
    ("Railways", ("HSD",)), ("DOMESTIC", ("KERO",)),
)
CROSSCHECK_FY = (2021, 2022, 2023)
# A month is a few tonnes on a million; the editions round and one of them restates. Anything
# above this is a disagreement about the METHOD, which is what the check is for.
CROSSCHECK_REL_TOL = 0.005

# The product columns, in the order the layout prints them. TOTAL and the prior-year TOTAL
# are read as controls, not as products.
PRODUCTS = ("100LL", "HOBC", "NAPHTHA", "MS", "JP-8", "JP-1", "KERO", "HSD", "LDO", "FO")

AREAS = {
    "AREA - PAKISTAN": "Pakistan",
    "SINDH": "Sindh", "PUNJAB": "Punjab",
    "KHYBER PAKHTUNKHWA": "Khyber Pakhtunkhwa", "BALOCHISTAN": "Balochistan",
    "GILGIT BALTISTAN": "Gilgit Baltistan", "AZAD KASHMIR": "Azad Kashmir",
}

# Sector rows worth carrying, and what each one times in this inventory. A row absent here is
# not an error - "Total Industry" is a subtotal of rows already taken, and taking both would
# double the sector.
# Keyed on (SECTION, row label), because the label alone is ambiguous: "Others" appears under
# INDUSTRY and again under GOVERNMENT, and collapsing them booked government fuel as
# industrial. The section headings are printed in capitals with no numbers, which is how they
# are recognised.
SECTIONS = ("INTERNAL USE", "INDUSTRY", "AGRICULTURE", "TRANSPORT", "POWER", "GOVERNMENT",
            "OVERSEAS/FOREIGN")
SECTORS = {
    "DOMESTIC": "residential",
    "Cement": "ippu_cement_fuel", "Others": "industry_other",
    "AGRICULTURE": "transport_offroad_agri",
    "Road": "transport_road", "Railways": "railways",
    "Domestic Bunkers": "domestic_navigation",
    "Domestic Avi-PIA": "aviation_pia", "Domestic Avi-Others": "aviation_others",
    "K-Electric": "power_ke", "PEPCO": "power_pepco", "HUBCO": "power_hubco",
    "Narowal Energy": "power_narowal", "Private Power": "power_private",
    "KAPCO (LSFO)": "power_kapco",
}
# Rows whose meaning depends on the section they sit in. "Aviation" and "Bunkers" each appear
# TWICE on the page - once under GOVERNMENT inside the national total, and again under
# OVERSEAS/FOREIGN outside it - and the label alone cannot tell them apart. That collision is
# what the one per cent overshoot was: OVERSEAS/FOREIGN was not a recognised heading, so
# `section` was still "GOVERNMENT" when the overseas rows arrived and they were booked as
# government fuel, adding B. TOTAL OVERSEAS on top of A. TOTAL INTERNAL.
SECTION_SECTORS = {
    ("GOVERNMENT", "Aviation"): "government_aviation",
    ("GOVERNMENT", "Bunkers"): "government_bunkers",
    ("GOVERNMENT", "Others"): "government_other",
    ("OVERSEAS/FOREIGN", "Aviation"): "international_aviation_bunkers",
    ("OVERSEAS/FOREIGN", "Bunkers"): "international_marine_bunkers",
    ("OVERSEAS/FOREIGN", "Export"): "export",
}
# The IPCC memo items. They are kept, because international bunkers are reported beside a
# national inventory rather than inside it - but they are kept in their own SCOPE, and the
# closure identity below sums the internal scope only.
OVERSEAS_SECTION = "OVERSEAS/FOREIGN"

SUBTOTALS = ("Total Industry", "Total Transport", "Total Power", "Total Government",
             "B. TOTAL OVERSEAS", "GRAND TOTAL")
CONTROL = "A. TOTAL INTERNAL VOL M.TONS"
OVERSEAS_CONTROL = "B. TOTAL OVERSEAS VOL M.TONS"

# The document rounds to whole tonnes, so a row of ten products can miss its printed total by
# a few units without anything being wrong. Anything larger is a parse defect.
ROW_TOLERANCE = 12.0
SECTOR_TOLERANCE = 60.0


def _number(token):
    token = token.strip().replace(",", "").replace("*", "")
    if token in ("-", "", "—"):
        return 0.0
    try:
        return float(token)
    except ValueError:
        return None


def _cells(text):
    """The numeric cells of a table line, with footnote markers removed rather than counted.

    A LONE ASTERISK IS NOT A ZERO. From FY2023-24 the Export row carries a footnote, printed
    as its own whitespace-separated token ("-    *    165,140"), and stripping the asterisk
    left an empty string that read as 0.0 - a phantom column that shifted every value after
    it one place right. Eleven months' memo-item control failed for that one character.
    """
    tokens = [t for t in re.split(r"\s{2,}", text.strip()) if t.strip().strip("*")]
    return [v for v in (_number(t) for t in tokens) if v is not None]


def _text(path):
    result = subprocess.run(["pdftotext", "-layout", path, "-"],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True)
    return result.stdout.decode("utf-8", "replace")


def _area_of(line):
    stripped = line.strip()
    for key, name in AREAS.items():
        if stripped.startswith(key):
            return name
    return None


def parse(path, year, month):
    """[(area, sector_label, sector_id, product, tonnes)] plus per-area control rows.

    ONLY THE ENERGY SECTION. Each report prints the whole area x sector x product table
    TWICE - energy products first, then non-energy (lubricants, solvents, asphalt) with
    different columns under the same headers and its own "A. TOTAL INTERNAL". Reading both
    into one table silently overwrote every control with the non-energy total: about 25,000
    tonnes standing in for a real 1,432,706, and every month failed closure for a reason that
    looked like a parse bug and was a scope bug. The section boundary is the SECOND time the
    Pakistan header appears.
    """
    rows, controls, area, header = [], {}, None, list(PRODUCTS)
    pakistan_seen, section = 0, ""
    for line in _text(path).splitlines():
        found = _area_of(line)
        if found:
            if found == "Pakistan":
                pakistan_seen += 1
                if pakistan_seen > 1:
                    break
            area = found
            continue
        if area is None:
            continue
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("SECTOR"):
            names = [c.strip() for c in re.split(r"\s{2,}", stripped[len("SECTOR"):].strip())]
            names = [c for c in names if c and not c.upper().startswith("TOTAL")]
            if len(names) >= 4:
                header = names
            continue

        if stripped in SECTIONS or stripped.rstrip(":") in SECTIONS:
            section = stripped.rstrip(":")
            continue

        control = next((c for c in (CONTROL, OVERSEAS_CONTROL)
                        if stripped.startswith(c)), None)
        if control is not None:
            values = _cells(stripped[len(control):])
            if values:
                slot = "internal" if control is CONTROL else "overseas"
                controls[(area, slot)] = values[-2] if len(values) >= 3 else values[-1]
            continue
        if any(stripped.startswith(s) for s in SUBTOTALS):
            continue

        label, sector_id = None, None
        for (sec, cand), sid in SECTION_SECTORS.items():
            if sec == section and stripped.startswith(cand):
                label, sector_id = cand, sid
                break
        if label is None:
            for candidate in sorted(SECTORS, key=len, reverse=True):
                if stripped.startswith(candidate):
                    label, sector_id = candidate, SECTORS[candidate]
                    break
        if label is None:
            continue
        values = _cells(stripped[len(label):])
        # THE COLUMN COUNT IS NOT CONSTANT, IN TWO INDEPENDENT WAYS, and each was a defect.
        # Across EDITIONS the product set differs - FY2021-22 does not print what FY2023-24
        # does - so a fixed ten-column slice put the TOTAL inside the products. And across
        # PAGES of one edition the number of trailing CONTROL columns differs: the Pakistan
        # page prints TOTAL and then last year's TOTAL, while every province page prints one
        # TOTAL alone. Counting back from the end therefore reads FO as the total on five
        # pages in six.
        #
        # The page's own SECTOR header settles both: it names the products, so its length is
        # the product count and the total is the column straight after them. Nothing here is
        # positional guesswork.
        if len(values) < len(header) + 1:
            continue
        products = values[:len(header)]
        printed_total = values[len(header)]
        if abs(sum(products) - printed_total) > ROW_TOLERANCE:
            # The WHOLE line, not a 160-character prefix. The columns a reader needs in order
            # to judge a closure failure are the ones on the right, and truncating cut off
            # precisely those.
            rows.append(("QUARANTINE", area, label, re.sub(r"\s+", " ", stripped),
                         sum(products), printed_total))
            continue
        scope = "overseas" if section == OVERSEAS_SECTION else "internal"
        for index, tonnes in enumerate(products):
            if not tonnes:
                continue
            name = header[index] if index < len(header) else "col%d" % (index + 1)
            rows.append(("OK", area, label, sector_id, name, tonnes, scope))
    return rows, controls


def shift_mutation_caught(parsed_rows):
    """How many comparisons a one-month shift in the published side would break.

    THE POINT OF A POSITIVE CONTROL. "144 comparisons, 0 disagreements" is only evidence if
    the comparison could have disagreed, and a check wired up wrongly - reading the same
    numbers on both sides, or reading nothing - reports exactly the same clean result. So the
    defect this check exists to find is injected deliberately and the count of comparisons
    that notice is published beside the count that pass.

    The injected defect is a ONE-MONTH SHIFT, chosen because it is not hypothetical: an
    off-by-one at a fiscal-year boundary is a mistake this project has made and found twice.
    """
    shifted = []
    for row in parsed_rows:
        year, month = int(row["month"][:4]), int(row["month"][4:])
        month += 1
        if month > 12:
            year, month = year + 1, 1
        moved = dict(row)
        moved["month"] = "%04d%02d" % (year, month)
        shifted.append(moved)
    compared = [c for c in crosscheck(shifted) if c["agrees"] in ("yes", "NO")]
    return sum(1 for c in compared if c["agrees"] == "NO"), len(compared)


def edition_currency():
    """Which edition of each month the SHIPPED panel is built on, against what OCAC serves now.

    WHY THIS IS A SEPARATE QUESTION. The cross-check above asks whether the differencing is
    right. This asks whether the documents are current, which is independent: a perfectly
    executed identity over a withdrawn edition is still wrong. OCAC restates months - nine of
    the thirty-six carry a -1..-4 revision suffix - and a panel assembled before a restatement
    keeps the superseded numbers with nothing to signal it.

    Three outcomes, and only one of them is a finding:

      identical        the panel holds the same bytes now served
      cumulative-form  the panel holds the year-to-date edition of that month, which is a
                       DIFFERENT DOCUMENT and not a stale one - this is the ordinary case and
                       the differencing exists precisely to read it
      SUPERSEDED       the panel holds a single-month edition that OCAC has since restated
    """
    out = []
    for path in sorted(glob.glob(asset_path(RAW, "ocac_sector_province_*.pdf"))):
        match = re.search(r"_(\d{4})_(\d{2})\.pdf$", path)
        year, month = int(match.group(1)), int(match.group(2))
        panel_path = asset_path(PANEL_EDITIONS, "OCAC_%04d_%02d.pdf" % (year, month))
        row = {"month": "%04d%02d" % (year, month),
               "panel_edition": os.path.relpath(panel_path, ROOT) if
               os.path.exists(panel_path) else "",
               "served_edition": os.path.relpath(path, ROOT),
               "status": "", "panel_control_t": "", "served_control_t": "", "delta_t": ""}
        if not os.path.exists(panel_path):
            row["status"] = "not-in-panel"
            out.append(row)
            continue
        with open(panel_path, "rb") as handle:
            panel_digest = hashlib.sha256(handle.read()).hexdigest()
        with open(path, "rb") as handle:
            served_digest = hashlib.sha256(handle.read()).hexdigest()
        if panel_digest == served_digest:
            row["status"] = "identical"
            out.append(row)
            continue
        _rows, panel_controls = parse(panel_path, year, month)
        panel_control = panel_controls.get(("Pakistan", "internal"))
        _rows, served_controls = parse(path, year, month)
        served_control = served_controls.get(("Pakistan", "internal"))
        if panel_control is None:
            # The single-month control label is absent, which is how a cumulative edition
            # presents itself: "JULY - DECEMBER 2023" under a PAKISTAN header, with
            # "A. TOTAL INTERNAL VOLUME" rather than "... VOL M.TONS".
            row["status"] = "cumulative-form"
        else:
            row["status"] = ("SUPERSEDED" if abs(panel_control - served_control) > 0.5
                             else "identical-numbers-different-bytes")
            row["panel_control_t"] = round(panel_control, 1)
            row["served_control_t"] = round(served_control, 1)
            row["delta_t"] = round(served_control - panel_control, 1)
        out.append(row)
    return out


def crosscheck(parsed_rows):
    """One row per (fiscal year, customer class, product set, month): differenced vs published.

    THE POINT. core/ocac_monthly.py recovers a month by subtracting one cumulative edition
    from the next. That is an arithmetic identity on two published numbers rather than a
    model, which is why the module trusts it - but "it should hold" and "it holds" are
    different statements, and only the second one is evidence. OCAC's single-month editions
    are an independent measurement of the same quantity, so the identity can be measured.

    A missing panel year is reported as such rather than skipped: the panel opens partway
    through this inventory's window, and a comparison that quietly disappears when the panel
    cannot serve a year would make thin coverage look like agreement.
    """
    from pkinv.core import ocac_monthly as panel

    published = {}
    for row in parsed_rows:
        if row["area"] != "Pakistan" or row["scope"] != "internal":
            continue
        key = (row["sector_label"], row["product"].replace(" ", ""), row["month"])
        published[key] = published.get(key, 0.0) + row["tonnes"]

    out = []
    for fy_start in CROSSCHECK_FY:
        for sector_row, products in CROSSCHECK_CASES:
            try:
                differenced, method = panel.tonnes(sector_row, products, fy_start)
            except (KeyError, ValueError) as error:
                out.append({"fiscal_year_start": fy_start, "sector_row": sector_row,
                            "products": "+".join(products), "month": "",
                            "panel_differenced_t": "", "published_month_t": "",
                            "delta_t": "", "relative_delta": "", "panel_t_class": "",
                            "agrees": "panel-cannot-serve",
                            "note": "%s: %s" % (type(error).__name__, str(error)[:90])})
                continue
            for month in sorted(differenced):
                theirs = differenced[month]
                mine = sum(published.get((sector_row, p, month), 0.0) for p in products)
                delta = mine - theirs
                relative = abs(delta) / theirs if theirs else (0.0 if not mine else 1.0)
                out.append({
                    "fiscal_year_start": fy_start, "sector_row": sector_row,
                    "products": "+".join(products), "month": month,
                    "panel_differenced_t": round(theirs, 1),
                    "published_month_t": round(mine, 1),
                    "delta_t": round(delta, 1), "relative_delta": round(relative, 6),
                    "panel_t_class": method[month],
                    "agrees": "yes" if relative <= CROSSCHECK_REL_TOL else "NO",
                    "note": ""})
    return out


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    files = sorted(glob.glob(asset_path(RAW, "ocac_sector_province_*.pdf")))
    if not files:
        print("no OCAC files under %s" % RAW)
        return 1

    out, bad = [], []
    per_month = {}
    for path in files:
        match = re.search(r"_(\d{4})_(\d{2})\.pdf$", path)
        year, month = int(match.group(1)), int(match.group(2))
        parsed, controls = parse(path, year, month)
        kept = 0
        for row in parsed:
            if row[0] == "QUARANTINE":
                bad.append({"month": "%04d%02d" % (year, month), "area": row[1],
                            "sector": row[2], "raw": row[3],
                            "products_sum": round(row[4], 2), "printed_total": round(row[5], 2)})
                continue
            _ok, area, label, sector_id, product, tonnes, scope = row
            out.append({"month": "%04d%02d" % (year, month), "fiscal_year_of_month": "",
                        "area": area, "scope": scope,
                        "sector_label": label, "sector_id": sector_id,
                        "product": product, "tonnes": tonnes,
                        "timing_target": "fuel_sale", "source_file": os.path.basename(path)})
            kept += 1
        # Sector closure against the document's own A. TOTAL, for Pakistan only: the province
        # pages repeat the structure and their control is the same identity one level down.
        # INTERNAL SCOPE ONLY. A. TOTAL INTERNAL excludes the overseas bunkers printed below
        # it, so summing every parsed row against it compares two different scopes and fails
        # by exactly B. TOTAL OVERSEAS - which is what it did.
        key = "%04d%02d" % (year, month)
        national = sum(r["tonnes"] for r in out if r["month"] == key
                       and r["area"] == "Pakistan" and r["scope"] == "internal")
        printed = controls.get(("Pakistan", "internal"))
        closed = printed is not None and abs(national - printed) <= SECTOR_TOLERANCE
        overseas = sum(r["tonnes"] for r in out if r["month"] == key
                       and r["area"] == "Pakistan" and r["scope"] == "overseas")
        overseas_printed = controls.get(("Pakistan", "overseas"))
        overseas_closed = (overseas_printed is not None
                           and abs(overseas - overseas_printed) <= SECTOR_TOLERANCE)
        per_month[key] = (kept, national, printed, closed, overseas, overseas_printed,
                          overseas_closed)

    comparisons = crosscheck(out)
    with open(OUT, "w", newline="", encoding="utf-8") as handle:
        handle.write("# THE PANEL'S DIFFERENCED MONTHS AGAINST OCAC'S DIRECTLY PUBLISHED "
                     "ONES. Not an activity table and nothing reads it as one.\n")
        handle.write("# The shipped panel recovers most months by differencing consecutive "
                     "cumulative year-to-date editions. OCAC also publishes a\n")
        handle.write("# single-month edition of the same months; this compares the two. A "
                     "disagreement is a defect in the differencing identity that\n")
        handle.write("# core/ocac_monthly.py applies and that transport, railways, power and "
                     "industry all depend on.\n")
        writer = csv.DictWriter(handle, fieldnames=list(comparisons[0]))
        writer.writeheader()
        writer.writerows(comparisons)
    if bad:
        with open(QUARANTINE, "w", newline="", encoding="utf-8") as handle:
            handle.write("# Rows whose products did not sum to the total the SAME ROW prints. "
                         "Kept with their raw text, never repaired.\n")
            writer = csv.DictWriter(handle, fieldnames=list(bad[0]))
            writer.writeheader()
            writer.writerows(bad)

    print("OCAC direct-edition cross-check -> %s" % os.path.relpath(OUT, ROOT))
    print("  %d files parsed, %d product cells, %d rows quarantined"
          % (len(files), len(out), len(bad)))
    failed = [m for m, v in sorted(per_month.items()) if not v[3]]
    print("  national sector closure (A. TOTAL INTERNAL): %d of %d months"
          % (len(per_month) - len(failed), len(per_month)))
    for month in failed[:10]:
        _kept, national, printed, _, _, _, _ = per_month[month]
        print("    %s parsed %.0f against a printed %s" % (month, national, printed))
    over_failed = [m for m, v in sorted(per_month.items()) if not v[6]]
    print("  memo-item closure (B. TOTAL OVERSEAS):      %d of %d months"
          % (len(per_month) - len(over_failed), len(per_month)))
    for month in over_failed[:10]:
        _k, _n, _p, _c, overseas, printed, _ = per_month[month]
        print("    %s parsed %.0f against a printed %s" % (month, overseas, printed))
    areas = sorted({r["area"] for r in out})
    print("  areas: %s" % ", ".join(areas))

    currency = edition_currency()
    with open(CURRENCY, "w", newline="", encoding="utf-8") as handle:
        handle.write("# WHICH EDITION OF EACH MONTH THE SHIPPED PANEL IS BUILT ON. "
                     "'cumulative-form' is the ordinary case, not a defect:\n")
        handle.write("# the panel reads year-to-date editions and differences them. "
                     "'SUPERSEDED' means OCAC has restated a month the panel\n")
        handle.write("# still carries at its first-upload values.\n")
        writer = csv.DictWriter(handle, fieldnames=list(currency[0]))
        writer.writeheader()
        writer.writerows(currency)
    stale = [c for c in currency if c["status"] == "SUPERSEDED"]
    print("  edition currency: %s"
          % ", ".join("%s %d" % (status, sum(1 for c in currency if c["status"] == status))
                      for status in sorted({c["status"] for c in currency})))
    for case in stale:
        print("    SUPERSEDED %s: panel %s t, OCAC now publishes %s t (%+.0f)"
              % (case["month"], case["panel_control_t"], case["served_control_t"],
                 case["delta_t"]))

    tested = [c for c in comparisons if c["agrees"] in ("yes", "NO")]
    disagree = [c for c in tested if c["agrees"] == "NO"]
    unserved = [c for c in comparisons if c["agrees"] == "panel-cannot-serve"]

    caught, mutated = shift_mutation_caught(out)
    summary = [{
        "months_parsed": len(files),
        "product_cells": len(out),
        "rows_quarantined": len(bad),
        "months_closing_internal_control": sum(1 for v in per_month.values() if v[3]),
        "months_closing_overseas_control": sum(1 for v in per_month.values() if v[6]),
        "comparisons": len(tested),
        "comparisons_disagreeing": len(disagree),
        "comparisons_exact": sum(1 for c in tested if c["delta_t"] == 0.0),
        "max_relative_delta_pct": round(100 * max([c["relative_delta"] for c in tested]
                                                  or [0.0]), 4),
        "shift_mutation_caught": caught,
        "shift_mutation_comparisons": mutated,
        "editions_superseded": sum(1 for c in currency if c["status"] == "SUPERSEDED"),
    }]
    with open(SUMMARY, "w", newline="", encoding="utf-8") as handle:
        handle.write("# THE PARSE'S OWN ACCOUNTING, one row. Denominators live here so that "
                     "a count published in the paper - two quarantined\n")
        handle.write("# rows, 144 comparisons - is read against the size of what was parsed "
                     "rather than on its own. shift_mutation_caught is\n")
        handle.write("# the positive control: comparisons that break when a one-month shift "
                     "is injected, without which a clean result is\n")
        handle.write("# indistinguishable from a check that tests nothing.\n")
        writer = csv.DictWriter(handle, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)
    print("  differencing check: %d comparisons, %d disagreements above %.1f%%"
          % (len(tested), len(disagree), CROSSCHECK_REL_TOL * 100))
    for case in disagree[:10]:
        print("    %s %s %s  panel %s vs published %s (%+.2f%%)"
              % (case["month"], case["sector_row"], case["products"],
                 case["panel_differenced_t"], case["published_month_t"],
                 100 * case["relative_delta"]))
    for case in unserved:
        print("    FY%s %s %s: %s" % (case["fiscal_year_start"], case["sector_row"],
                                      case["products"], case["note"]))
    # The check is only worth reporting if it actually compared something. A run that served
    # no year would otherwise print "0 disagreements" and read as success.
    if not tested:
        print("  NOTHING WAS COMPARED - the panel served no case; this is a failure, not a "
              "pass")
        return 1
    return 1 if disagree else 0


if __name__ == "__main__":
    import sys as _sys
    if "--check" in _sys.argv[1:]:
        # re-derive into a temporary directory and compare; nothing in the tree is written
        from pkinv.core.checkmode import compare_only
        _sys.exit(compare_only(globals(), ("OUT", "QUARANTINE", "CURRENCY", "SUMMARY"), main))
    sys.exit(main())
