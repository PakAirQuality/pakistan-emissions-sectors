"""PBS's monthly plant generation, read into a series the monthly layer can use.

WHAT THIS UNLOCKS. Grid power is the largest single item in the monthly gap - 12.3 percent of
the inventory's mass is time-variable and carried flat - and the reason was never that
electricity has no monthly record. It was that nobody had read one. PBS publishes "Electricity
Generation Data" plant by plant and month by month, FY1999-2000 to FY2020-21 continuous, and
the six fiscal years it covers inside this inventory's window are exactly the six with no OCAC
monthly panel.

THE TABLE IS A GRID, AND WHITESPACE IS NOT ITS STRUCTURE. A month in which a plant did not run
is printed as empty space, so splitting a line on whitespace slides every later month one
column to the left; a plant whose name is too long for the column has its name wrapped onto
the line above and its last month's figure onto the line below. Reading the tables that way
lost between eight and sixteen percent of four of the six years. This module therefore reads
by COLUMN POSITION, and it does not take the column positions from the header - the figures
sit several characters right of their own headings, differently on each of the fifteen page
layouts in the file. It LEARNS the grid from the rows that prove themselves:

  * a row carrying thirteen figures whose thirteenth equals the sum of the first twelve can
    only be Jul..Jun plus the annual total, in that order. Between 100 and 190 rows a year
    say so, and the median of their positions is the grid.
  * every other row - blanks, wrapped names, spilled figures - is then placed on that grid,
    and a row that carries its own annual total must still reconcile to it (PROOF ONE).
  * the plant rows must then reconstruct the printed monthly Grand Total, month by month
    (PROOF TWO). All six years now do, exactly.

Proof two is also what licenses reading a blank cell as nil rather than as unknown: the
source's own arithmetic says the blanks are nil. A plant with NO ROW AT ALL is still missing
and still never becomes a zero.

TWO AMBIGUITIES, NEITHER GUESSED.

Units. The tables are headed `Unit:GWH`, `Unit: MW` and `Unit:GWh` in different years and the
magnitudes are none of those. The scale is derived, not assumed, and it is derived from the
TOTAL generation rather than from any fuel-assigned subset: total generation must exceed
fossil-only generation and must fall well short of three times it, because hydel, nuclear and
renewables are about a third of Pakistan's electricity. Every year lands between 1.47 and 1.66
at a scale of 1000; the neighbouring scales would put it at 15.6 or at 0.156. Only one scale
survives, and if more than one did this would raise rather than choose.

Fuel. The Fuel column is populated from FY2018-19 and blank before it. It is read POSITIONALLY,
from the column the header names, and only when the cell holds a fuel word exactly - so
`Coal Fire/Huaneng Shandong Ruyi` is a plant name and not a coal label. Blank years are filled
by carry-back from PBS's own later labelling of the same plant, then from plant_fuel_ledger.csv.
A plant that no source labels stays UNASSIGNED, and a plant the ledger gives MORE THAN ONE fuel
is ambiguous rather than labelled with whichever row came first. Coverage is then a reported
fraction per fuel per year, not a gate: a fuel the file covers thinly keeps its flat profile.

Usage:  python3 scripts/ingest_pbs_generation.py [--dry-run] [--year 2015]
Writes: data/activity/power/generation_monthly.csv
        data/activity/power/generation_monthly_coverage.csv
"""

from pkinv.assets import asset_path
import argparse
import collections
import csv
import hashlib
import os
import re
import shutil
import statistics
import subprocess
import sys

from pkinv.core.io import write_or_check

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF = asset_path(ROOT, "sources", "Power Plants", "pbs_generation",
                   "pbs_electricity_generation_1999_2021.pdf")
OUT = asset_path(ROOT, "data", "activity", "power", "generation_monthly.csv")
COVERAGE = asset_path(ROOT, "data", "activity", "power",
                        "generation_monthly_coverage.csv")
CONTROL = asset_path(ROOT, "data", "activity", "power", "generation_by_fuel.csv")
LEDGER = asset_path(ROOT, "data", "activity", "power", "plant_fuel_ledger.csv")
PANEL = asset_path(ROOT, "data", "activity", "power", "plant_fuel_generation.csv")
ALIASES = asset_path(ROOT, "data", "activity", "power", "plant_aliases.csv")

FIELDS = ("fiscal_year", "month", "plant", "fuel", "fuel_source", "gwh", "unit_basis",
          "source_file", "source_sha256", "note")
COVERAGE_FIELDS = ("fiscal_year", "subitem", "fuel_words", "control_gwh", "observed_gwh",
                   "coverage", "temporal_class", "decision")

# The window this inventory reports. PBS reaches FY2020-21 and no further, so FY2021-22 onward
# keep whatever profile they have and the decomposition goes on naming them.
FIRST_FY_START, LAST_FY_START = 2015, 2020

# Fuel words PBS prints in its Fuel column. Matched as the WHOLE cell, never inferred from a
# plant's name and never from a company name that spilled into the column.
FUEL_TOKENS = {
    "nuclear": "Nuclear", "hydel": "Hydel", "hydro": "Hydel", "coal": "Coal",
    "gas": "Gas", "rlng": "RLNG", "rfo": "RFO", "fo": "RFO", "hsd": "HSD",
    "diesel": "HSD", "wind": "Wind", "solar": "Solar", "bagasse": "Bagasse",
    "baggase": "Bagasse", "mixed": "Mixed",
}
# What generation_by_fuel.csv accounts for; the reconciliation is fossil-to-fossil.
FOSSIL = ("Coal", "Gas", "RLNG", "RFO", "HSD")

# The monthly layer's own subitems, and the fuel words each one covers. Coverage is judged at
# THIS resolution rather than PBS's, because it is the resolution a profile is applied at.
# Grouping RLNG with pipeline gas is not a convenience: they are one component in this
# inventory - same molecule, same factor - and it is also what makes the carry-back safe for
# them, since a plant labelled RLNG in a later year was burning pipeline gas in an earlier one
# and both readings land on the same component.
FUEL_GROUPS = (
    ("Coal", ("Coal",)),
    ("Gas", ("Gas", "RLNG")),
    ("Furnace Oil", ("RFO",)),
    ("Diesel Oil", ("HSD",)),
)

# A fuel needs this much of its own annual control observed in labelled plants before its
# monthly shape is worth more than the flat line it would replace.
COVERAGE_STRONG, COVERAGE_WEAK = 0.85, 0.60
# And carrying a fuel label BACK to a year the publication left blank assumes the plant burned
# then what it burned later, which for Pakistan's RLNG conversions is sometimes false. Labelled
# generation running well past the year's own control is the test of that assumption failing -
# FY2016-17 reads 580 percent of an RLNG control that was barely open yet - so the shape is
# refused rather than fitted to a fleet that did not exist.
COVERAGE_IMPOSSIBLE = 1.15

HEADER = re.compile(r"Electricity Generation Data(?:\s+For The Year)?\s+"
                    r"(\d{4})\s*-\s*(\d{2,4})", re.I)
COLUMN_HEADER = re.compile(r"name of establishment", re.I)
MONTH_HEADER = re.compile(r"([A-Za-z]{3,9})[.,]\s?\d{2}")
MONTH_WORDS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov",
               "dec")
FUEL_HEADER = re.compile(r"\bFuel\b")
TOKEN = re.compile(r"\S+")
NUMBER = re.compile(r"^-?[\d,]+(?:\.\d+)?$")
SERIAL = re.compile(r"^\s{0,5}\d{1,3}(\s|$)")
GRAND_TOTAL = re.compile(r"grand\s+total", re.I)
# The serial number belongs to the page, not to the plant: the same station is 54 one year
# and 48 the next, so leaving it in the name is enough to stop a fuel label carrying back.
# Only a serial in the serial column is stripped - the "1" of a wrapped "Unit-1" sits further
# right and stays part of the name.
SERIAL_PREFIX = re.compile(r"^\s{0,5}\d{1,3}(?=\s|$)")
SUBTOTAL = re.compile(r"(^|\s)TOTAL\s", re.I)
# The publication writes a month in which a plant produced nothing as a dash, an ellipsis or
# simply as empty space. That is the SOURCE saying nil, in a table of production. It is not
# the same as a plant being absent from the table altogether, which is what "missing" means
# here and is why a plant with no row at all never becomes a zero. Nil markers are recognised
# so that an all-nil row is kept as an observed zero, but they are never placed on the grid:
# nil is zero wherever it sits, so letting a four-character ellipsis compete with a
# right-aligned figure for a column would only ever displace real data.
DOTS = re.compile(r"^[.…]+$")
WORD_NIL = {"-", "--", "---", "----", "nil", "n.a.", "na", "*"}
# A wrapped name can be printed hard against its first figure - "Coal Energy Pvt Ltd891318".
# Split only where the numeric tail is long enough to be a generation figure in MWh, so that
# "Unit-1" and "Block-3" keep their names intact.
GLUED = re.compile(r"^(\D{2,}?)(\d[\d,]{3,}(?:\.\d+)?)$")
# Two proving rows belong to the same page layout when every one of their thirteen columns
# agrees to within this many characters.
LAYOUT_FIT = 3.0

MONTH_ORDER = [7, 8, 9, 10, 11, 12, 1, 2, 3, 4, 5, 6]


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _text():
    if not shutil.which("pdftotext"):
        raise SystemExit("pdftotext is not installed; nothing read")
    out = subprocess.run(["pdftotext", "-layout", PDF, "-"], check=True,
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    return out.stdout.decode("utf-8", "replace")


def blocks(text=None):
    """{fiscal_start_year: [lines]} for each year's table."""
    text = text if text is not None else _text()
    found, current, lines = {}, None, []
    for line in text.splitlines():
        match = HEADER.search(line)
        if match:
            if current is not None:
                found.setdefault(current, []).extend(lines)
            current, lines = int(match.group(1)), []
            continue
        if current is not None:
            lines.append(line.rstrip())
    if current is not None:
        found.setdefault(current, []).extend(lines)
    return found


def _header_line(lines):
    for line in lines:
        if not COLUMN_HEADER.search(line):
            continue
        months = [m for m in MONTH_HEADER.finditer(line)
                  if m.group(1).lower()[:3] in MONTH_WORDS]
        if len(months) >= 12:
            return line, months
    return None, None


def figure_zone(lines):
    """Where the figures start. Left of this is the plant's name and its fuel."""
    _line, months = _header_line(lines)
    return None if months is None else months[0].start() - 10


def fuel_zone(lines):
    """The Fuel column's span, or None where the table has no such column."""
    line, _months = _header_line(lines)
    if line is None:
        return None
    match = FUEL_HEADER.search(line)
    return (match.start() - 4, match.end() + 4) if match else None


def figures(line, zone):
    """[(value, centre)] for the real figures on a line. Nil markers are not figures."""
    out = []
    for match in TOKEN.finditer(line):
        if match.start() < zone:
            continue
        token, start, end = match.group(0).strip(), match.start(), match.end()
        glued = GLUED.match(token)
        if glued:
            token = glued.group(2)
            start = end - len(token)
        if NUMBER.match(token):
            out.append((float(token.replace(",", "")), (start + end) / 2.0))
    return out


def states_nil(line, zone):
    """True where the line prints an explicit nil - a dash or an ellipsis - past the names."""
    for match in TOKEN.finditer(line):
        if match.start() < zone:
            continue
        token = match.group(0).strip().lower()
        if DOTS.match(token) or token in WORD_NIL:
            return True
    return False


def _proving_rows(lines, zone):
    """[(line_index, [13 centres])] for rows whose own printed total proves their layout."""
    proofs = []
    for index, line in enumerate(lines):
        found = figures(line, zone)
        if len(found) != 13:
            continue
        values = [v for v, _c in found]
        if abs(sum(values[:12]) - values[12]) > max(1.0, 0.001 * abs(values[12])):
            continue
        proofs.append((index, [c for _v, c in found]))
    return proofs


def layouts(proofs):
    """One median grid per page layout, from the proving rows that share it."""
    clusters = []
    for index, centres in proofs:
        for cluster in clusters:
            if max(abs(a - b) for a, b in zip(cluster["median"], centres)) <= LAYOUT_FIT:
                cluster["rows"].append((index, centres))
                cluster["median"] = [statistics.median(column) for column
                                     in zip(*[c for _i, c in cluster["rows"]])]
                break
        else:
            clusters.append({"rows": [(index, centres)], "median": centres})
    return [{"grid": c["median"], "lines": [i for i, _c in c["rows"]], "n": len(c["rows"])}
            for c in clusters if len(c["rows"]) >= 3]


def place(found, grid):
    """[13 values or None] - or None where two figures claim one column, or order breaks."""
    tolerance = min(grid[i + 1] - grid[i] for i in range(12)) / 2.0
    slots, last = [None] * 13, -1
    for value, centre in found:
        best = min(range(13), key=lambda i: abs(grid[i] - centre))
        if abs(grid[best] - centre) > tolerance or best <= last or slots[best] is not None:
            return None
        slots[best] = value
        last = best
    return slots


def _groups(lines, zone):
    """One record per printed row, gathering the lines a wrapped name spread it over."""
    groups, pending = [], []
    for index, line in enumerate(lines):
        if COLUMN_HEADER.search(line):
            continue
        found = figures(line, zone)
        if GRAND_TOTAL.search(line[:zone]):
            groups.append({"index": index, "lines": [line], "anchor": line,
                           "figures": list(found), "grand": True,
                           "nil": states_nil(line, zone)})
            pending = []
            continue
        if SERIAL.match(line):
            groups.append({"index": index, "lines": pending + [line], "anchor": line,
                           "figures": list(found), "grand": False,
                           "nil": states_nil(line, zone)})
            pending = []
        elif found and groups:
            groups[-1]["lines"].append(line)
            groups[-1]["figures"].extend(found)
        elif line.strip():
            if states_nil(line, zone) and groups:
                groups[-1]["nil"] = True
            else:
                pending.append(line)
    return groups


def _fuel_of(group, fzone):
    """The Fuel column's own word on the row's PRINCIPAL line, or ''.

    Only the line carrying the serial number is read. A wrapped continuation is name text by
    definition, and it lands in the Fuel column often enough to matter: Sahiwal's second line
    is `Coal Energy Pvt Ltd891318`, whose first word sits exactly where a fuel word would and
    is a company's name. Reading it would have labelled the plant from its owner - true here,
    by luck, and not a way to label anything.
    """
    if fzone is None or group["anchor"] is None:
        return ""
    low, high = fzone
    for line in (group["anchor"],):
        for match in TOKEN.finditer(line):
            if match.start() < low or match.end() > high:
                continue
            word = match.group(0).strip().strip(".,").lower()
            if word in FUEL_TOKENS:
                return FUEL_TOKENS[word]
    return ""


def parse_year(lines):
    """([{plant, fuel, months[12]}], printed_totals[12] or None, [(label, why)])."""
    zone = figure_zone(lines)
    if zone is None:
        return [], None, [("(whole year)", "no column header naming twelve months")]
    fzone = fuel_zone(lines)
    grids = layouts(_proving_rows(lines, zone))
    if not grids:
        return [], None, [("(whole year)", "no row proves its own layout")]

    rows, totals, dropped = [], None, []
    for group in _groups(lines, zone):
        label = " ".join(" ".join(SERIAL_PREFIX.sub("", line[:zone])
                                  for line in group["lines"]).split())
        found = sorted(group["figures"], key=lambda cell: cell[1])
        if not found:
            if group["nil"] and not group["grand"] and label:
                # A row of nothing but nils is the source stating a nil year, and it is kept.
                rows.append({"plant": label, "fuel": _fuel_of(group, fzone),
                             "months": [0.0] * 12})
            continue
        near = sorted(grids, key=lambda g: min(abs(group["index"] - i) for i in g["lines"]))
        slots = None
        for layout in near:
            candidate = place(found, layout["grid"])
            if candidate is None:
                continue
            if candidate[12] is not None and not group["grand"]:
                months = [0.0 if v is None else v for v in candidate[:12]]
                if abs(sum(months) - candidate[12]) > max(1.0, 0.001 * abs(candidate[12])):
                    continue                      # PROOF ONE: the row must meet its own total
            slots = candidate
            break
        if slots is None:
            dropped.append((label[:60], "%d figures could not be placed on any layout, or "
                                        "did not meet the row's own printed total"
                            % len(found)))
            continue
        months = [0.0 if value is None else value for value in slots[:12]]
        if group["grand"]:
            totals = months
            continue
        if SUBTOTAL.search(label):
            continue                              # a subtotal of rows already counted
        rows.append({"plant": label, "fuel": _fuel_of(group, fzone), "months": months})
    return rows, totals, dropped


def _ledger_name(name):
    """The ledger's plant names carry column headings and company suffixes into the field."""
    cleaned = re.sub(r"^\(Rs\.?\s*Million\)\s*", "", name.strip())
    cleaned = re.sub(r"\((GENCO[- ]?[IVX0-9]+)\)", " ", cleaned)
    return cleaned.strip()


def ledger_fuels():
    """{normalised plant: fuel} - and NOTHING for a plant the ledger gives several fuels.

    Fifteen of the ledger's fifty-two plants burn more than one fuel: Jamshoro is gas and
    furnace oil, KAPCO is RLNG, furnace oil and diesel, Bin Qasim I is all three. Taking
    whichever row was read first would label each of them with a fuel they only partly burn,
    silently and in a file nobody would think to check.
    """
    seen = collections.defaultdict(set)
    if os.path.exists(LEDGER):
        with open(LEDGER, newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                if row.get("fuel"):
                    seen[_normalise(_ledger_name(row["plant"]))].add(row["fuel"])
    return {plant: next(iter(fuels)) for plant, fuels in seen.items() if len(fuels) == 1}


def _normalise(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


def aliases():
    """{normalised PBS name: normalised panel name} - declared, never inferred.

    PBS prints `Coal Fire/Huaneng Shandong` for the station NEPRA calls `Huaneng Shandong
    Ruyi (Sahiwal Imported Coal)`, and no rule connects those two strings. A containment join
    was measured last pass and refused: it does not find Sahiwal at all, and it binds HUBCO
    Narowal to `hub`, which is a different power station. So each pairing is written down by
    hand with its reason - and then CORROBORATED, in tests, against the two sources' own
    annual generation for the same year. A wrong alias fails arithmetic rather than passing
    quietly.

    Some are many-to-one and have to be: PBS bills Guddu as `TPS GUDDU(5-13)` where NEPRA
    reports Units 5-10 and Units 11-13 separately. The unit numbers line up exactly, the sum
    is what the magnitude check tests, and a mapping that did not add up would fail it.
    """
    out = {}
    if not os.path.exists(ALIASES):
        return out
    with open(ALIASES, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            out[_normalise(row["pbs_name"])] = [_normalise(_ledger_name(name))
                                                for name in row["panel_name"].split("+")]
    return out


def panel_totals():
    """{(normalised plant, fiscal_year): {subitem: GWh}} straight out of the NEPRA panel."""
    if not os.path.exists(PANEL):
        return {}
    totals = collections.defaultdict(lambda: collections.defaultdict(float))
    with open(PANEL, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if not row["generation_gwh"]:
                continue
            label = "FY%s-%s" % (row["fiscal_year"][:4], row["fiscal_year"][5:7])
            subitem = next((s for s, group in FUEL_GROUPS if row["fuel"] in group), None)
            if subitem:
                totals[(_normalise(_ledger_name(row["plant"])), label)][subitem] += \
                    float(row["generation_gwh"])
    return totals


def dominant_fuel(totals, names, label):
    """(fuel word, share) for the subitem that dominates these stations in this year.

    Keyed on the PLANT-YEAR, which is the whole reason this beats a crosswalk. A station is
    not one fuel: TPS Jamshoro is 74 percent gas in FY2015-16 and 30 percent in FY2019-20, and
    a single label would be wrong in one of those years whichever way it was written.
    """
    merged = collections.defaultdict(float)
    seen = False
    for name in names:
        for subitem, value in totals.get((name, label), {}).items():
            merged[subitem] += value
            seen = True
    total = sum(merged.values())
    if not seen or total <= 0:
        return None
    subitem, value = max(merged.items(), key=lambda kv: kv[1])
    group = dict(FUEL_GROUPS)[subitem]
    return (group[0], value / total)


# How much of a plant-year's generation one subitem must be before the plant-year counts as
# effectively single-fuel. Below it the station genuinely burned a mixture, and splitting that
# mixture across the months would assert a seasonality nobody measured - Pakistani plant swings
# to furnace oil at the summer peak, so a constant within-year mix is wrong in a known
# direction and in exactly the direction the monthly product is trying to detect.
DOMINANT = 0.95


def fuel_map(parsed):
    """{normalised plant: (fuel, source)} from PBS's own later labelling, then the ledger.

    Later years label the same plants this publication leaves blank earlier, so the label is
    carried BACK from the same source rather than assigned by judgement.
    """
    mapping = {}
    for year in sorted(parsed):
        for row in parsed[year][0]:
            if row["fuel"]:
                mapping.setdefault(_normalise(row["plant"]),
                                   (row["fuel"], "pbs_fuel_column_fy%d" % year))
    for plant, fuel in ledger_fuels().items():
        mapping.setdefault(plant, (fuel, "plant_fuel_ledger"))
    return mapping


# Fuels a station cannot convert away from. A gas/RLNG label carried across years once
# produced the 580-percent impossibility this file's own docstring records, because
# Pakistan's fleet really did convert; a coal boiler is not convertible, so a COAL label
# from the nearest later listing sheet is a statement about the same physical plant in
# any year it generated. The carry is still guarded twice: the alias must be a declared
# pairing (pbs_sir_aliases.csv), and the year's own annual control polices the result
# through COVERAGE_IMPOSSIBLE like every other label.
IMMUTABLE_FUELS = ("Coal",)


def sheet_carry_labels():
    """{normalised PBS name: (fuel, source)} - immutable-fuel labels carried back from
    the EARLIEST SIR listing sheet, for years before any sheet exists.

    The one live case is Sahiwal in its commissioning year: PBS prints it as
    "Coal Power" in FY2016-17 (873 GWh), no sheet covers that year, and the year's coal
    control corroborates the identity by exclusion - Lakhra's labelled 124 GWh plus
    this row's 873 sum to 94 percent of the 1,059 GWh control, and no other coal
    station had commissioned by June 2017.
    """
    try:
        import ingest_sir_generation as sir
    except ImportError:
        return {}
    if not os.path.exists(SIR_ALIASES):
        return {}
    earliest = min((fy for fy, path in sir.VALIDATION_LISTINGS.items()
                    if os.path.exists(path)), default=None)
    if earliest is None:
        return {}
    sheet = {plant["plant"]: plant["fuel_label"]
             for plant in sir.parse_sheet(sir.VALIDATION_LISTINGS[earliest])[0]}
    out = {}
    with open(SIR_ALIASES, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(line for line in handle
                                  if not line.startswith("#")):
            label = sheet.get(row["sir_name"], "")
            fuel = sir.SINGLE_FUEL.get(label.lower())
            if fuel in IMMUTABLE_FUELS:
                out[_normalise(row["pbs_name"])] = (
                    fuel, "sir_sheet_label_carried_fy%d" % earliest)
    return out


SIR_ALIASES = asset_path(ROOT, "data", "activity", "power", "pbs_sir_aliases.csv")
# The magnitude gate for a same-year SIR sheet label: PBS gross over NEPRA net runs to
# about a tenth at old thermal stations, the same physics as the NEPRA-panel alias band.
SIR_BAND = (0.85, 1.20)


def sir_sheet_labels(fy_start, controls):
    """{normalised PBS name: (fuel, source, sheet_total)} from the SAME YEAR's listing.

    The rc20 discovery, consumed at last: NEPRA's Detail-of-Generation listing sheets
    label the stations PBS's fuel column leaves blank - Sahiwal's coal, the RLNG
    combined-cycle fleet - in the SAME fiscal year, so nothing is carried across years.
    A single-fuel label is stated evidence; a mixed label is assigned only where the
    per-member annual-control bound forces one fuel (sixteenth-review rule: an inferred
    fuel is never TE2, which coverage_rows enforces by capping any subitem carrying
    bound mass). The pairing itself is a declared alias, and it is corroborated AT USE:
    the caller assigns only where the two records' own annual magnitudes agree.
    """
    try:
        import ingest_sir_generation as sir
    except ImportError:
        return {}
    path = sir.VALIDATION_LISTINGS.get(fy_start)
    if not path or not os.path.exists(path) or not os.path.exists(SIR_ALIASES):
        return {}
    sheet = {}
    for plant in sir.parse_sheet(path)[0]:
        sheet[plant["plant"]] = (plant["fuel_label"], plant["printed_sum"])
    out = {}
    with open(SIR_ALIASES, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(line for line in handle
                                  if not line.startswith("#")):
            found = sheet.get(row["sir_name"])
            if not found:
                continue
            fuel, kind = sir.member_bound(found[0], found[1], controls)
            if fuel is None or fuel not in dict(
                    (f, None) for _s, group in FUEL_GROUPS for f in group):
                continue                      # mixed and unforceable, or non-fossil
            source = ("sir_sheet_label" if kind == "stated" else "sir_sheet_bound")
            out[_normalise(row["pbs_name"])] = (fuel, source, found[1])
    return out


def control_by_fuel():
    """{fiscal_start_year: {fuel: gwh_net}} over both systems combined."""
    out = collections.defaultdict(lambda: collections.defaultdict(float))
    with open(CONTROL, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["gwh_net"]:
                out[int(row["fiscal_year"])][row["fuel"]] += float(row["gwh_net"])
    return out


def unit_scale(total_raw, fossil_control):
    """The one power of ten that puts total generation between once and three times fossil.

    Total generation is necessarily more than fossil-only generation and, in a system a third
    of whose electricity is hydel, nuclear and renewable, is nowhere near three times it. The
    scales are a decade apart, so at most one can satisfy that - and this returns the
    candidates rather than a choice, so the caller raises if the answer is not unique.
    """
    return [scale for scale in (1, 10, 100, 1000, 10000)
            if 1.0 <= (total_raw / scale) / fossil_control <= 3.0]


def months_for(fy_start):
    return ["%04d%02d" % (fy_start if m >= 7 else fy_start + 1, m) for m in MONTH_ORDER]


def coverage_rows(plants, controls, scale, label):
    """Per subitem: how much of the annual control the labelled plants actually observe.

    One cap rides on top of the ladder (Pass 2, mirroring the SIR panel lane): a subitem
    whose observed mass includes BOUND-assigned fuel - a mixed sheet label forced by the
    annual control rather than stated - is capped at TE3, because an inferred fuel is
    never TE2 however tight the inference.
    """
    observed = collections.defaultdict(float)
    inferred = collections.defaultdict(float)
    for plant in plants:
        if plant["fuel"]:
            observed[plant["fuel"]] += sum(plant["months"]) / scale
            if plant.get("fuel_source", "").startswith("sir_sheet_bound"):
                inferred[plant["fuel"]] += sum(plant["months"]) / scale
    out = []
    for subitem, fuels in FUEL_GROUPS:
        control = sum(controls.get(f, 0.0) for f in fuels)
        if not control:
            continue
        share = sum(observed.get(f, 0.0) for f in fuels) / control
        bound_mass = sum(inferred.get(f, 0.0) for f in fuels)
        if share > COVERAGE_IMPOSSIBLE:
            grade, decision = "TE4", ("labelled generation exceeds the annual control; the "
                                      "carried-back fuel label does not hold in this year")
        elif share >= COVERAGE_STRONG:
            grade, decision = "TE2", "fuel-specific monthly shape"
        elif share >= COVERAGE_WEAK:
            grade, decision = "TE3", "fuel-specific monthly shape, partial sample"
        else:
            grade, decision = "TE4", "no shape; the fuel keeps its flat profile"
        if grade == "TE2" and bound_mass > 0:
            grade = "TE3"
            decision = ("fuel-specific monthly shape; %.0f GWh of the observed mass is "
                        "assigned by annual-control bound rather than stated, so the "
                        "grade is capped at TE3" % bound_mass)
        elif grade == "TE3" and bound_mass > 0:
            decision += ("; %.0f GWh assigned by annual-control bound" % bound_mass)
        out.append({"fiscal_year": label, "subitem": subitem, "fuel_words": "+".join(fuels),
                    "control_gwh": round(control, 2),
                    "observed_gwh": round(sum(observed.get(f, 0.0) for f in fuels), 2),
                    "coverage": round(share, 4), "temporal_class": grade,
                    "decision": decision})
    return out


def build(only_year=None):
    parsed = {year: parse_year(lines) for year, lines in blocks().items()}
    mapping = fuel_map(parsed)
    panel = panel_totals()
    alias = aliases()
    controls = control_by_fuel()
    digest = _sha256(PDF)

    rows, coverage, report = [], [], []
    for fy_start in range(FIRST_FY_START, LAST_FY_START + 1):
        if only_year and fy_start != only_year:
            continue
        label = "FY%d-%02d" % (fy_start, (fy_start + 1) % 100)
        if fy_start not in parsed:
            report.append((label, "SKIPPED", "no table for this year in the document"))
            continue
        plants, totals, dropped = parsed[fy_start]
        if not plants:
            report.append((label, "SKIPPED", "no plant rows parsed"))
            continue
        if not totals:
            report.append((label, "SKIPPED", "no Grand Total row to check the parse against"))
            continue

        # PROOF TWO: the plant rows must reconstruct the printed monthly Grand Total.
        summed = [sum(p["months"][i] for p in plants) for i in range(12)]
        worst = max(abs(summed[i] - totals[i]) / max(totals[i], 1.0) for i in range(12))
        if worst > 0.005:
            report.append((label, "SKIPPED",
                           "plant rows miss the printed Grand Total by %.2f%% in the worst "
                           "month; the parse is not trustworthy%s"
                           % (100 * worst,
                              " (%d rows dropped)" % len(dropped) if dropped else "")))
            continue

        fossil_control = sum(controls.get(fy_start, {}).get(f, 0.0) for f in FOSSIL)
        if not fossil_control:
            report.append((label, "SKIPPED", "no annual fossil control for this year"))
            continue
        candidates = unit_scale(sum(totals), fossil_control)
        if len(candidates) != 1:
            report.append((label, "SKIPPED",
                           "the unit scale is not decided - %s satisfy the bracket; total "
                           "generation reads %.0f against a fossil control of %.0f"
                           % (candidates or "no power of ten", sum(totals), fossil_control)))
            continue
        scale = candidates[0]

        sheet_labels = sir_sheet_labels(fy_start, controls.get(fy_start, {}))
        carried_sheet = sheet_carry_labels() if fy_start < 2017 else {}
        for plant in plants:
            if plant["fuel"]:
                plant["fuel_source"] = "pbs_fuel_column"
                continue
            # The panel first, because it is keyed on the PLANT-YEAR and every other source
            # here carries a label across years it was not observed in.
            names = alias.get(_normalise(plant["plant"]), [_normalise(plant["plant"])])
            found = dominant_fuel(panel, names, label)
            if found and found[1] >= DOMINANT:
                plant["fuel"] = found[0]
                plant["fuel_source"] = "nepra_panel_%.0f%%" % (100 * found[1])
                continue
            # The SAME-YEAR SIR sheet label next (Pass 2): keyed on this fiscal year's
            # own listing, so nothing crosses a year - and gated on the two records'
            # magnitudes agreeing for this year, so a wrong alias fails arithmetic.
            sheet = sheet_labels.get(_normalise(plant["plant"]))
            if sheet:
                own = sum(plant["months"]) / scale
                if sheet[2] > 0 and SIR_BAND[0] <= own / sheet[2] <= SIR_BAND[1]:
                    plant["fuel"], plant["fuel_source"] = sheet[0], sheet[1]
                    continue
            carried = mapping.get(_normalise(plant["plant"])) \
                or carried_sheet.get(_normalise(plant["plant"]))
            plant["fuel"], plant["fuel_source"] = carried if carried else ("", "unassigned")

        year_coverage = coverage_rows(plants, controls.get(fy_start, {}), scale, label)
        coverage.extend(year_coverage)
        shaped = [c["subitem"] for c in year_coverage if c["temporal_class"] != "TE4"]
        report.append((label, "OK",
                       "unit scale %d, %d plants, %d months reconstruct the Grand Total to "
                       "%.4f%%; shaped fuels: %s%s"
                       % (scale, len(plants), 12, 100 * worst,
                          ", ".join(shaped) if shaped else "none",
                          "; %d rows dropped" % len(dropped) if dropped else "")))

        keys = months_for(fy_start)
        for plant in plants:
            for index, month in enumerate(keys):
                rows.append({
                    "fiscal_year": label, "month": month, "plant": plant["plant"],
                    "fuel": plant["fuel"], "fuel_source": plant["fuel_source"],
                    "gwh": round(plant["months"][index] / scale, 4),
                    "unit_basis": "MWh in the document, written here as GWh"
                                  if scale == 1000 else "as printed",
                    "source_file": os.path.relpath(PDF, ROOT), "source_sha256": digest,
                    "note": "" if plant["fuel"] else
                            "no source labels this plant's fuel; excluded from the "
                            "fuel-specific monthly profiles",
                })
    return rows, coverage, report


def main(argv=None):
    parser = argparse.ArgumentParser(description="Ingest PBS monthly plant generation.")
    parser.add_argument("--dry-run", action="store_true", help="report and write nothing")
    parser.add_argument("--check", action="store_true",
                        help="re-derive and report whether the committed panel still "
                             "follows from the held tables; writes nothing")
    parser.add_argument("--year", type=int, help="one fiscal start year only")
    args = parser.parse_args(argv)

    rows, coverage, report = build(args.year)
    print("PBS Electricity Generation Data -> monthly plant generation")
    for label, status, detail in report:
        print("  %-10s %-8s %s" % (label, status, detail))
    accepted = sorted({r["fiscal_year"] for r in rows})
    print("  %d rows over %d fiscal years: %s"
          % (len(rows), len(accepted), ", ".join(accepted) if accepted else "none"))
    if coverage:
        print("\n  coverage against the annual control, by the subitem a profile applies to")
        for row in coverage:
            print("    %-10s %-12s %7.1f%% of %8.0f GWh  %s  %s"
                  % (row["fiscal_year"], row["subitem"], 100 * row["coverage"],
                     row["control_gwh"], row["temporal_class"], row["decision"]))
    if args.dry_run:
        print("\n--dry-run: nothing written.")
        return 0
    if not rows:
        print("\nNo year passed its checks; nothing written.")
        return 1
    # The panel is shared with the SIR listing ingest (scripts/ingest_sir_generation.py),
    # which carries FY2021-22 onward. Each script rewrites only its own fiscal years and
    # preserves the other lane's rows, so re-running either cannot silently delete the
    # other's work.
    own_years = {r["fiscal_year"] for r in rows}
    for path, fields, own in ((OUT, FIELDS, rows), (COVERAGE, COVERAGE_FIELDS, coverage)):
        preserved = []
        if os.path.exists(path):
            with open(path, newline="", encoding="utf-8") as handle:
                preserved = [r for r in csv.DictReader(handle)
                             if r["fiscal_year"] not in own_years]
        # own FIRST here and own LAST in the SIR lane; since this lane holds the earlier
        # fiscal years both run orders land on the same layout, which is what makes a
        # whole-file --check sound for either lane (confirmed by running both).
        if write_or_check(path, fields, list(own) + list(preserved), args.check):
            return 1
    if args.check:
        print("the PBS lane's years reproduce from the held tables.")
        return 0
    print("\nwrote %s\n      %s"
          % (os.path.relpath(OUT, ROOT), os.path.relpath(COVERAGE, ROOT)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
