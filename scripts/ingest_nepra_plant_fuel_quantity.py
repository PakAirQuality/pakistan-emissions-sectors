#!/usr/bin/env python3
"""NEPRA's fuel QUANTITY by station and fuel for FY2015-16 to FY2019-20.

WHAT THIS IS FOR. The provincial split of grid power used one share vector per fuel, measured
on FY2023-24, for all nine years. A review asked why, when the manuscript itself showed a
province-year off by 11.6 Mt CO2e and said a per-year split was possible. For FY2019-20 onward
the answer was already in the repository (the plant fuel ledger from the 2024 report). For the
four years before it, the only station record ingested was GENERATION
(scripts/ingest_nepra_plant_fuel.py), and a provincial split on generation gives an efficient
station too little fuel and an inefficient one too much: where both exist, generation puts
Sindh's gas share eight to ten points under what the fuel says.

The fuel was on the same page. Tables 16 and 19 of the State of Industry Report 2020 print,
beside each station's generation, the quantity of each fuel it burned. That ingest read the
`(GWh)` columns and, correctly, refused to read anything else as generation. This script reads
the other columns as what they are.

HOW A ROW IS READ. A sub-table's columns are found from the UNIT words in its header
(`(GWh)`, `(MMCFT)`, `(MMBTU)`, `M.Ton)`, `Ltrs.)`, `(Average)`, `(Kg/kWh)`, the cost units),
ordered left to right. A data row's figures are then assigned to those columns IN ORDER, with
the fewest total characters of horizontal displacement. Order is what makes this safe: a figure
can never be read into a column to the left of the one before it, which is the failure
position-only matching has (the generation ingest's docstring records furnace oil's 0.30 kg/kWh
being read as an RLNG generation). A blank group (RLNG before it reached the country) is left
blank because no ordered assignment puts a figure there more cheaply.

WHAT IT REFUSES. A station-year-fuel is written only if its generation here EQUALS the figure
the generation ingest already holds for it (two independent readings of the same cell), and its
quantity implies a physically possible specific consumption for that fuel. The report has
misprints in exactly these columns: TPS Muzaffargarh's furnace oil reads 8,799.58 thousand
tonnes for 2,892 GWh in FY2017-18 and 92,801.55 for 289 GWh in FY2019-20. Where a quantity
fails the band and the table prints the station's specific consumption beside it, the quantity
is taken as generation times that printed rate and the row says so. Where neither stands, the
row is written with an EMPTY quantity and the reason, and the consumer falls back to generation
for that one station-year. Nothing is repaired silently and nothing is dropped silently.

THREE STATIONS THE TABLES DO NOT CARRY. Bhikki, Haveli Bahadur Shah and Balloki are public-
sector RLNG plants and are not in the 2020 report's IPP table. Their FY2018-19 fuel is printed
in the 2023 report's IPP table and is transcribed below with its page; their commissioning
generation in FY2016-17 and FY2017-18 has no fuel quantity in any held edition.

K-ELECTRIC (Table 24) IS NOT READ: the provincial split describes the fleet behind the national
fuel control, which the boundary audit finds to be the CPPA side
(pkinv.sectors.power.plant_ledger.in_boundary).

Usage:  python3 scripts/ingest_nepra_plant_fuel_quantity.py [--check]
Writes: data/activity/power/plant_fuel_quantity_back_years.csv
--check re-derives the table from the held report and compares; it writes nothing.
"""
import csv
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pkinv.assets import asset_path                       # noqa: E402
import ingest_nepra_plant_fuel as generation              # noqa: E402  (regions, sub-tables, names)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = asset_path(ROOT, "data", "activity", "power", "plant_fuel_quantity_back_years.csv")
GENERATION = asset_path(ROOT, "data", "activity", "power", "plant_fuel_generation.csv")

FIELDS = ("fiscal_year", "system", "plant", "fuel", "quantity", "quantity_unit",
          "generation_gwh", "printed_quantity", "printed_specific_consumption",
          "quantity_basis", "source_table", "note")

SCOPES = {"GENCOs": ("GENCO", "NEPRA SoIR 2020 Table 16"),
          "IPPs": ("IPP", "NEPRA SoIR 2020 Table 19")}

# Unit words in a header, and what the column under each one holds.
MARKERS = (
    (re.compile(r"\(GWh\)", re.I), "gwh"),
    (re.compile(r"\(MMCFT\)", re.I), "MMCFT"),
    (re.compile(r"\(MMBTU\)", re.I), "MMBTU"),
    (re.compile(r"M\.\s?Tons?\)", re.I), "000 t"),
    (re.compile(r"Ltrs\.?\)", re.I), "000 L"),
    (re.compile(r"\(Average\)", re.I), "rate"),
    (re.compile(r"\(Kg/kWh\)", re.I), "rate"),
    (re.compile(r"\(Paisa/kWh\)|\(Rs\.\s?/kWh\)|\(Rs\.\s?Million\)", re.I), "cost"),
)
QUANTITY_UNITS = ("MMCFT", "MMBTU", "000 t", "000 L")
# Which fuels a quantity unit can belong to. A header that puts a unit under the wrong fuel is
# a misread header, and the sub-table is refused.
UNIT_FUELS = {"MMCFT": ("Gas", "RLNG"), "MMBTU": ("Gas", "RLNG"),
              "000 t": ("RFO", "Coal"), "000 L": ("HSD",)}

# Physically possible specific consumption, per unit of quantity and GWh. Wide on purpose:
# these separate a misprint (a factor of ten or more) from a station, not a good station from
# a poor one. Gas: 5 to 22 cubic feet per kWh, or 5,500 to 22,000 Btu per kWh. Furnace oil:
# 0.17 to 0.45 kg per kWh. Diesel: 0.17 to 0.50 litres per kWh.
BANDS = {"MMCFT": (5.0, 22.0), "MMBTU": (5500.0, 22000.0),
         "000 t": (0.17, 0.45), "000 L": (0.17, 0.50)}
# Below this generation a station-year is a start-up or a trickle; its ratio means nothing
# (TPS Muzaffargarh prints 7.46 MMCFT for 10.90 GWh), so the band is not applied and the
# quantity is taken as printed.
BAND_FLOOR_GWH = 25.0
# TWO STATIONS THE REPORT PRINTS UNDER THE WRONG HEADING. Table 19 breaks across a page between
# its furnace-oil and gas sub-tables, and the two stations either side of the break are each
# printed on the other's side: Altern Energy closes the furnace-oil sub-table with 1,736,978
# against 184.60 GWh, and Narowal Energy opens the gas sub-table (heading: MMBTU) with 229.65
# against 1,161.91 GWh. Read under their headings those are 9,410 tonnes of oil per kWh and
# 0.2 Btu per kWh. Read the other way they are 9,410 Btu/kWh and 0.198 kg/kWh, a gas engine
# and an oil engine, which is what NEPRA's own Table 5 says the stations are (Altern `GEs`,
# Narowal `DEs+ST`) and how the 2021, 2022 and 2024 editions print them. Each correction is
# applied only if the corrected reading passes the physical band for EVERY year it touches,
# so the evidence is checked at each run and not taken on this comment's word. The generation
# ingest still files Narowal's generation under Gas; that is its misreading of the same page.
MISFILED = {
    "Narowal Energy": ("Gas", "RFO", "000 t"),
    "Altern Energy": ("RFO", "Gas", "MMBTU"),
}
MISFILED_NOTE = ("the report prints this station under its %s sub-table; the quantity is "
                 "physically a %s figure, and Table 5 and the later editions agree")
TOKEN = re.compile(r"\S+")
BLANK = re.compile(r"^(-+|n\.?p\.?\*{0,2})$", re.I)

# The three public-sector RLNG plants, FY2018-19, from the 2023 report's IPP table ("Fuel
# Consumption and Cost of Generation Data of IPPs (Net)", PDF p. 115), read by eye and typed:
# the first of each station's five fiscal-year rows. Their FY2019-20 rows in the same table
# equal the plant fuel ledger's (33,462,106; 44,350,901; 38,060,169 MMBTU), which is the check
# that these are the same series.
TRANSCRIBED = (
    ("2018-19", "IPP", "QATPL (Bhikki)", "RLNG", 39877621.0, "MMBTU", 6149.75),
    ("2018-19", "IPP", "NPPMCL (HBS)", "RLNG", 44670837.0, "MMBTU", 7027.24),
    ("2018-19", "IPP", "NPPMCL (Balloki)", "RLNG", 31594264.0, "MMBTU", 5284.19),
)
TRANSCRIBED_SOURCE = "NEPRA SoIR 2023 Table 21 (IPPs, Net), transcribed"
# The same three plants while commissioning. No held edition prints their fuel for these
# years; the 2021 report's station-wise generation table (section B2, Thermal IPPs of the
# CPPA-G system, PDF p. 106) prints their generation, typed here. Written with an empty
# quantity, so the consumer weights them by generation and says so.
COMMISSIONING = (
    ("2016-17", "IPP", "QATPL (Bhikki)", "RLNG", 502.77),
    ("2017-18", "IPP", "QATPL (Bhikki)", "RLNG", 3655.62),
    ("2016-17", "IPP", "NPPMCL (HBS)", "RLNG", 155.11),
    ("2017-18", "IPP", "NPPMCL (HBS)", "RLNG", 2856.73),
    ("2017-18", "IPP", "NPPMCL (Balloki)", "RLNG", 2050.62),
)
COMMISSIONING_SOURCE = "NEPRA SoIR 2021 station-wise generation table, section B2 (PDF p. 106), transcribed"


def number(token):
    """A printed figure, None for a blank mark (n.p., -), or False if it is not a figure."""
    token = token.strip()
    if BLANK.match(token):
        return None
    negative = token.startswith("(") and token.endswith(")")
    body = token.strip("()").rstrip("*")
    if not re.match(r"^-?[\d,]+(?:\.\d+)?$", body):
        return False
    return (-1 if negative else 1) * float(body.replace(",", ""))


def header_columns(lines, lo, hi):
    """[(x, kind)] for one sub-table, left to right, from the unit words in its header."""
    found = []
    for index in range(lo, min(hi + 4, len(lines))):
        for pattern, kind in MARKERS:
            for match in pattern.finditer(lines[index]):
                found.append(((match.start() + match.end()) / 2.0, kind))
    found.sort()
    merged = []
    for x, kind in found:
        # `Cft/kWh` over `(Average)` and a wrapped cost heading print one column's unit twice
        if merged and kind == merged[-1][1] and x - merged[-1][0] <= 9 and kind in ("rate", "cost"):
            continue
        merged.append((x, kind))
    return merged


def fuel_words(lines, lo, hi):
    return [((m.start() + m.end()) / 2.0, m.group(1))
            for index in range(lo, min(hi + 4, len(lines)))
            for m in generation.FUEL_WORD.finditer(lines[index])]


def groups(columns, words):
    """[{fuel, gwh, quantity, unit, rate}] column indexes per fuel, or a refusal string."""
    out, current = [], None
    for index, (x, kind) in enumerate(columns):
        if kind == "gwh":
            if not words:
                return "no fuel word in the header"
            fuel = min(words, key=lambda w: abs(w[0] - x))[1]
            current = {"fuel": fuel, "gwh": index, "quantity": None, "unit": None, "rate": None}
            out.append(current)
        elif kind in QUANTITY_UNITS:
            if current is None or current["quantity"] is not None:
                return "a quantity column with no generation column before it"
            if current["fuel"] not in UNIT_FUELS[kind]:
                return "a %s column filed under %s" % (kind, current["fuel"])
            current["quantity"], current["unit"] = index, kind
        elif kind == "rate":
            if current is not None and current["rate"] is None and current["quantity"] is not None:
                current["rate"] = index
    fuels = [g["fuel"] for g in out]
    if len(set(fuels)) != len(fuels):
        return "its header does not resolve to distinct fuels (%s)" % ", ".join(fuels)
    return out


def assign(tokens, columns):
    """{column index: token} placing the tokens on the columns IN ORDER at least displacement.

    tokens are (text, centre x). Fewer tokens than columns leaves columns blank; more is a
    row this cannot read. Classic order-preserving alignment: cost[i][j] is the best way to
    place the first i tokens on the first j columns."""
    n, m = len(tokens), len(columns)
    if n > m or n == 0:
        return None
    infinity = float("inf")
    cost = [[infinity] * (m + 1) for _ in range(n + 1)]
    back = [[False] * (m + 1) for _ in range(n + 1)]
    for j in range(m + 1):
        cost[0][j] = 0.0
    for i in range(1, n + 1):
        for j in range(i, m + 1):
            skip = cost[i][j - 1]
            take = cost[i - 1][j - 1] + abs(tokens[i - 1][1] - columns[j - 1][0])
            if take <= skip:
                cost[i][j], back[i][j] = take, True
            else:
                cost[i][j] = skip
    placed, i, j = {}, n, m
    while i > 0:
        if back[i][j]:
            placed[j - 1] = tokens[i - 1][0]
            i -= 1
        j -= 1
    return placed


def parse(text=None):
    """([row dicts], [(what, why)]) for the GENCO and IPP tables."""
    lines = (text if text is not None else generation._text()).splitlines()
    rows, refused = [], []
    for scope, start, end in generation.regions(lines):
        if scope not in SCOPES:
            continue
        system, table = SCOPES[scope]
        for lo, head_hi, row_lines in generation.sub_tables(lines, start, end):
            columns = header_columns(lines, lo, head_hi)
            if not columns or not row_lines:
                continue
            layout = groups(columns, fuel_words(lines, lo, head_hi))
            if isinstance(layout, str):
                refused.append(("%s sub-table at line %d" % (scope, head_hi), layout))
                continue
            edge = int(min(x for x, _kind in columns)) - 12
            found = []
            for index in row_lines:
                match = generation.YEAR_ANY.search(lines[index][:max(edge, 0) + 14])
                if match:
                    found.append((index, "%s-%s" % (match.group(1), match.group(2)), match.end()))
            for run in generation._runs([(i, y) for i, y, _e in found]):
                ends = {i: e for i, _y, e in found}
                # the margin runs to the end of the year label; cutting it shorter leaves half
                # a year ("2015-1") in the station's name
                plant = generation._name(lines, run, max(ends[i] for i, _y in run))
                if not plant or len(run) < generation.MIN_YEARS:
                    refused.append(("%s run at line %d" % (scope, run[0][0]),
                                    "no station name or fewer than three years"))
                    continue
                for index, year in run:
                    body = lines[index][ends[index]:]
                    tokens = [(t.group(0), ends[index] + (t.start() + t.end()) / 2.0)
                              for t in TOKEN.finditer(body)]
                    if any(number(t) is False for t, _x in tokens):
                        refused.append(("%s %s %s" % (scope, plant, year),
                                        "a remark in place of figures: %s"
                                        % " ".join(t for t, _x in tokens)[:70]))
                        continue
                    placed = assign(tokens, columns)
                    if placed is None:
                        refused.append(("%s %s %s" % (scope, plant, year),
                                        "%d figures for %d columns" % (len(tokens), len(columns))))
                        continue
                    for group in layout:
                        gwh = number(placed[group["gwh"]]) if group["gwh"] in placed else None
                        if gwh is None:
                            continue
                        quantity = rate = None
                        if group["quantity"] is not None and group["quantity"] in placed:
                            quantity = number(placed[group["quantity"]])
                        if group["rate"] is not None and group["rate"] in placed:
                            rate = number(placed[group["rate"]])
                        rows.append({"fiscal_year": year, "system": system, "plant": plant,
                                     "fuel": group["fuel"], "generation_gwh": gwh,
                                     "printed_quantity": quantity, "unit": group["unit"],
                                     "printed_rate": rate, "source_table": table})
    return rows, refused


def held_generation():
    """{(fiscal_year, plant, fuel): GWh} as the generation ingest read the same tables."""
    out = {}
    with open(GENERATION, encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(line for line in handle if not line.startswith("#")):
            if row["generation_gwh"]:
                out[(row["fiscal_year"], row["plant"], row["fuel"])] = float(row["generation_gwh"])
    return out


def own_ratio(row, parsed):
    """The station's median quantity per GWh on this fuel over its OTHER years that pass the
    band, or None. What a misprinted year is compared with."""
    lo, hi = BANDS[row["unit"]]
    ratios = sorted(r["printed_quantity"] / r["generation_gwh"] for r in parsed
                    if r is not row and r["plant"] == row["plant"] and r["fuel"] == row["fuel"]
                    and r["unit"] == row["unit"] and r["printed_quantity"]
                    and r["generation_gwh"] >= BAND_FLOOR_GWH
                    and lo <= r["printed_quantity"] / r["generation_gwh"] <= hi)
    if len(ratios) < 2:
        return None
    middle = len(ratios) // 2
    return ratios[middle] if len(ratios) % 2 else (ratios[middle - 1] + ratios[middle]) / 2.0


def judge(row, parsed=()):
    """(quantity, basis, note) for one parsed station-year-fuel. quantity may be None."""
    gwh, printed, unit, rate = (row["generation_gwh"], row["printed_quantity"], row["unit"],
                                row["printed_rate"])
    if unit is None:
        return None, "generation only", "the table prints generation for this fuel and no quantity"
    if gwh <= 0:
        return (printed or 0.0), "printed", "no generation on this fuel"
    lo, hi = BANDS[unit]
    scale = 1.0     # every unit here is quantity per GWh in the band's own terms
    ratio = (printed / gwh * scale) if printed else None
    if gwh < BAND_FLOOR_GWH:
        if printed is None:
            return None, "generation only", "quantity not published for a trickle of generation"
        return printed, "printed", "under %d GWh: the ratio of a start-up is not tested" % BAND_FLOOR_GWH
    if ratio is not None and lo <= ratio <= hi:
        return printed, "printed", ""
    # A MISPLACED DECIMAL POINT. TPS Muzaffargarh's furnace oil is printed as 92,801.55
    # thousand tonnes for 289 GWh in FY2019-20; the 2024 edition prints 92.8 for the same
    # station-year. The same slip is in FY2017-18 (8,799.58 for 2,892 GWh) and in Nandipur's
    # gas (2,133.61 MMCFT for 2,382 GWh), and the 2021 and 2022 editions reprint both
    # unchanged, so no later edition arbitrates them. A power of ten is accepted only if it
    # brings the station to within 15 percent of its OWN ratio in its other years: the
    # station's record decides where the point goes, not this script.
    usual = own_ratio(row, parsed) if printed else None
    if usual:
        for shift in (10.0, 100.0, 1000.0, 0.1, 0.01, 0.001):
            candidate = printed / shift
            if lo <= candidate / gwh <= hi and abs(candidate / gwh - usual) <= 0.15 * usual:
                return round(candidate, 2), "printed, decimal point restored", (
                    "printed %g, which is %.3g per kWh; divided by %g it is %.3g, against "
                    "this station's %.3g in its other years" % (printed, ratio, shift,
                                                                candidate / gwh, usual))
    if rate and lo <= rate * (1.0 if unit != "000 t" and unit != "000 L" else 1.0) <= hi:
        derived = round(gwh * rate, 2)
        return derived, "generation x printed specific consumption", (
            "the printed quantity (%s) implies %s per kWh, outside %s to %s; the table prints %s "
            "beside it" % ("none" if printed is None else "%g" % printed,
                           "nothing" if ratio is None else "%.3g" % ratio, lo, hi, rate))
    return None, "generation only", (
        "the printed quantity (%s) implies %s per kWh, outside %s to %s, and no usable specific "
        "consumption is printed" % ("none" if printed is None else "%g" % printed,
                                    "nothing" if ratio is None else "%.3g" % ratio, lo, hi))


def refile(parsed):
    """Apply MISFILED, each only if the corrected reading is physically possible throughout."""
    notes = {}
    for plant, (printed_as, really, unit) in MISFILED.items():
        mine = [r for r in parsed if r["plant"] == plant and r["fuel"] == printed_as]
        if not mine:
            raise SystemExit("%s is no longer printed under %s; MISFILED is stale"
                             % (plant, printed_as))
        lo, hi = BANDS[unit]
        tested = [r for r in mine if r["printed_quantity"] and r["generation_gwh"] >= BAND_FLOOR_GWH]
        if not tested or not all(lo <= r["printed_quantity"] / r["generation_gwh"] <= hi
                                 for r in tested):
            raise SystemExit("%s: read as %s the quantities are not physically possible in "
                             "every year, so the correction does not stand" % (plant, really))
        for r in mine:
            notes[id(r)] = MISFILED_NOTE % (printed_as, really)
            r["fuel"], r["unit"], r["printed_as"] = really, unit, printed_as
    return notes


def build():
    parsed, refused = parse()
    held = held_generation()
    refiled = refile(parsed)
    out, disagreements = [], []
    for row in parsed:
        key = (row["fiscal_year"], row["plant"], row.get("printed_as", row["fuel"]))
        if key in held and abs(held[key] - row["generation_gwh"]) > 0.005:
            disagreements.append("%s %s %s: this reading %.2f GWh, the generation ingest %.2f"
                                 % (key + (row["generation_gwh"], held[key])))
            continue
        quantity, basis, note = judge(row, parsed)
        if row["generation_gwh"] == 0 and not quantity:
            continue                                    # a printed zero on both sides
        out.append({
            "fiscal_year": row["fiscal_year"], "system": row["system"], "plant": row["plant"],
            "fuel": row["fuel"],
            "quantity": "" if quantity is None else "%.2f" % quantity,
            "quantity_unit": row["unit"] or "",
            "generation_gwh": "%.2f" % row["generation_gwh"],
            "printed_quantity": "" if row["printed_quantity"] is None else "%.2f" % row["printed_quantity"],
            "printed_specific_consumption": "" if row["printed_rate"] is None else "%g" % row["printed_rate"],
            "quantity_basis": basis, "source_table": row["source_table"],
            "note": "; ".join(x for x in (refiled.get(id(row), ""), note) if x) + ("" if key in held else
                            ("; " if note else "") + "not in the generation ingest (its sub-table "
                            "was refused there); read here from the same table")})
    for year, system, plant, fuel, quantity, unit, gwh in TRANSCRIBED:
        out.append({"fiscal_year": year, "system": system, "plant": plant, "fuel": fuel,
                    "quantity": "%.2f" % quantity, "quantity_unit": unit,
                    "generation_gwh": "%.2f" % gwh, "printed_quantity": "%.2f" % quantity,
                    "printed_specific_consumption": "", "quantity_basis": "printed",
                    "source_table": TRANSCRIBED_SOURCE,
                    "note": "public-sector RLNG plant, absent from the 2020 report's IPP table"})
    for year, system, plant, fuel, gwh in COMMISSIONING:
        out.append({"fiscal_year": year, "system": system, "plant": plant, "fuel": fuel,
                    "quantity": "", "quantity_unit": "MMBTU",
                    "generation_gwh": "%.2f" % gwh, "printed_quantity": "",
                    "printed_specific_consumption": "", "quantity_basis": "generation only",
                    "source_table": COMMISSIONING_SOURCE,
                    "note": "commissioning generation of a public-sector RLNG plant; no held "
                            "edition prints its fuel for this year"})
    out.sort(key=lambda r: (r["system"], r["plant"], r["fuel"], r["fiscal_year"]))
    return out, refused, disagreements


HEADER = (
    "# Station fuel quantities, FY2015-16 to FY2019-20, from NEPRA State of Industry Report 2020\n"
    "# Tables 16 (GENCOs) and 19 (IPPs): the columns beside the generation that\n"
    "# plant_fuel_generation.csv holds. Written by scripts/ingest_nepra_plant_fuel_quantity.py.\n"
    "# quantity_basis: `printed` (the table's own figure, physically possible for its GWh);\n"
    "# `printed, decimal point restored` (a power-of-ten misprint, placed by the station's own\n"
    "# ratio in its other years);\n"
    "# `generation x printed specific consumption` (the printed quantity is a misprint and the\n"
    "# table prints the station's rate beside it); `generation only` (no usable quantity: the\n"
    "# consumer weights this station-year by generation and says so).\n"
    "# fiscal_year is the report's label (2015-16); K-Electric is not read.\n")


def text(rows):
    handle = io.StringIO()
    handle.write(HEADER)
    writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return handle.getvalue()


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    rows, refused, disagreements = build()
    for what, why in refused:
        print("  refused  %s: %s" % (what, why))
    for line in disagreements:
        print("  DISAGREES  %s" % line)
    by_basis = {}
    for row in rows:
        by_basis[row["quantity_basis"]] = by_basis.get(row["quantity_basis"], 0) + 1
    print("%d station-year-fuel rows: %s" % (len(rows), ", ".join(
        "%d %s" % (n, b) for b, n in sorted(by_basis.items()))))
    if disagreements:
        print("nothing written: two readings of the same table disagree")
        return 1
    body = text(rows)
    if "--check" in argv:
        if os.path.exists(OUT):
            with open(OUT, encoding="utf-8", newline="") as handle:
                same = handle.read() == body
        else:
            same = False
        print("checked: %s" % os.path.relpath(OUT, ROOT) if same else
              "DIFFERS: %s is not what the held report yields" % os.path.relpath(OUT, ROOT))
        return 0 if same else 1
    if "--dry-run" in argv:
        return 0
    with open(OUT, "w", encoding="utf-8", newline="") as handle:
        handle.write(body)
    print("wrote %s" % os.path.relpath(OUT, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
