#!/usr/bin/env python3
"""Parse NEPRA State of Industry Report plant-level fuel tables into a versioned ledger.

WHY THIS EXISTS. The power sector was built on four national fuel rows (SoIR Table 3), which
is a fine Tier-1 control total and a ceiling on everything else: no plant geography, no coal
origin, no technology, and - the binding problem - Table 3 stops at FY2022-23 while the rest
of the report runs to FY2023-24.

Tables 18, 21 and 26 carry what Table 3 does not: plant x year x physical fuel quantity x net
generation, separately for GENCOs, IPPs and K-Electric, through FY2023-24. That is the ledger
this inventory needs, and it was in a document already sitting in sources/.

THE UNITS DECIDE THE METHOD, so they are preserved rather than normalised here:

  gas and RLNG are reported in MMBTU - already energy. Any comparison against Table 3's TOE
  therefore carries NO calorific assumption, which is what makes the gross-versus-net TOE
  question (this sector's largest declared risk) attackable by arithmetic;

  coal and RFO are reported in 000 M. Tons - mass, needing a calorific value downstream.

HOW THE LAYOUT IS PARSED. The PDF text puts each plant's name in fragments spread down the
rows of its own block, because the name is vertically centred against five year rows:

        Huaneng        2019-20   6,167.19   2,270.37
    Shandong Ruyi     2020-21   7,342.70   2,750.14
       (Sahiwal       2021-22   6,881.38   1,443.97
      Imported        2022-23   2,876.85   1,180.00
         Coal)        2023-24   2,075.55     772.00

So a plant is not a line. A plant is a RUN OF ASCENDING FISCAL YEARS, and its name is every
scrap of text sitting to the left of those rows, joined. A new block starts when the year
stops increasing. That rule survives page breaks, repeated headers and blank name cells.

WHAT IT DELIBERATELY DOES NOT DO. Multi-fuel sections - "(Gas+RLNG based Power Plant)" and
similar - are wide tables with repeated quantity blocks per fuel, and they are NOT parsed here.
They are counted and reported so the coverage shortfall is visible rather than silent; see the
`sections_skipped` line in the run output and the coverage assertions in tests.

Usage:  python3 scripts/ingest_nepra_plants.py
Writes: data/activity/power/plant_fuel_ledger.csv
"""

from pkinv.assets import asset_path
import csv
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF = asset_path(ROOT, "sources", "Power Plants",
                   "NEPRA State of Industry Report 2024.pdf")
from pkinv.core.io import write_or_check

OUT = asset_path(ROOT, "data", "activity", "power", "plant_fuel_ledger.csv")

# NEPRA SoIR 2024 Table 17, FY2023-24, for the coverage statement below.
TABLE17_THERMAL_GWH = 67243.62
TABLE17_COAL_CPPAG_GWH = 20217.91

# (table, system) - the boundary question this ledger exists to settle.
TABLES = {18: "GENCO", 21: "IPP", 26: "K-Electric"}

# Coal origin, read off the plant's own name. NEPRA names carry it: "(Sahiwal Imported Coal)"
# says so outright, and the Thar-mine-mouth units are named for the field. This replaces the
# 35-percent lignite share the sector currently infers from generation shares.
THAR = re.compile(r"\bthar\b|\bthal\s*nova\b", re.IGNORECASE)
IMPORTED = re.compile(r"\bimported\b|port\s*qasim|\bhub\b|sahiwal", re.IGNORECASE)

# Exact: 1 MMBTU = 1.05505585262 GJ, so MMBTU -> TJ is a definition, not an assumption. This
# is why the gas leg of the energy closure carries no calorific uncertainty at all.
TJ_PER_MMBTU = 1.05505585262e-3


def _origin(fuel, plant):
    """Coal origin from the plant name; blank for other fuels, 'unknown' where names do not say."""
    if fuel != "Coal":
        return ""
    if IMPORTED.search(plant):
        return "imported"
    if THAR.search(plant):
        return "Thar lignite"
    return "unknown"

# Single-fuel section headings -> (fuel, unit). Multi-fuel headings carry a '+' and are skipped.
SECTION = re.compile(r"\((?P<fuels>[A-Za-z0-9+. ]+?)\s+based Power Plant\)")
FUEL_UNIT = {
    "Coal": ("Coal", "000 t"),
    "Gas": ("Gas", "MMBTU"),
    "RLNG": ("RLNG", "MMBTU"),
    "Residual Furnace Oil": ("RFO", "000 t"),
    "HSD": ("HSD", "000 t"),
}

# ---------------------------------------------------------------------------
# MULTI-FUEL SECTIONS. These carry most of the fleet - the RLNG combined-cycle plants and every
# GENCO - and none of them can be read the way the single-fuel sections are.
#
# Why an explicit spec per section rather than a general algorithm. The layouts genuinely
# differ: some fuels carry an intensity column (CFT/kWh, Kg/kWh), some a cost column, some
# neither, and the trailing cost columns vary in number. A general "groups of three" reader is
# how the first version of this parser wrote 50,545,992 kt of coal for a gas plant. So each
# section states how many numbers its rows must contain and which positions hold generation and
# quantity; a row whose count does not match is SKIPPED AND COUNTED, never guessed at.
#
# Positional reading is safe here, and that had to be checked rather than assumed: "n.p." (not
# published) cells would shift every column after them, but they are essentially absent from
# the multi-fuel sections - 2 rows out of 104. Rows carrying one fail the count check and drop
# out. The single-fuel sections, where n.p. IS common, are read by taking the first two numbers
# instead, which is immune to trailing n.p.
#
# UNITS DIFFER BETWEEN TABLES AND IT MATTERS. Table 21 meters gas in MMBTU - already energy.
# Tables 18 and 26 meter it in MMCFT - a VOLUME, needing a heating value the repo does not pin.
# Only the MMBTU rows support an energy comparison with no calorific assumption, so the unit is
# carried per row and never normalised here.
#
# (start_line_key, expected_number_count, [(fuel, unit, gwh_index, qty_index), ...])
MULTI_SPECS = {
    # Table 18 GENCOs - name on its own centred line, gas in MMCFT
    "T18_GAS_RFO":  (8,  [("Gas", "MMCFT", 0, 1), ("RFO", "000 t", 3, 4)]),
    "T18_GAS":      (5,  [("Gas", "MMCFT", 0, 1)]),
    "T18_RLNG":     (5,  [("RLNG", "MMCFT", 0, 1)]),
    # Table 21 IPPs - dual and tri fuel. The tri-fuel block is KAPCO's, and its header
    # reads RLNG | RFO | HSD in that order - verified against the printed block, after the
    # first guess labelled the RLNG column Gas and read 638 kt of furnace oil as "RLNG"
    # (the intensity screen caught it at 0.198 MMBTU per GWh).
    "T21_2FUEL":    (8,  [("RLNG", "MMBTU", 0, 1), ("HSD", "000 L", 3, 4)]),
    "T21_3FUEL":    (11, [("RLNG", "MMBTU", 0, 1), ("RFO", "000 t", 3, 4),
                          ("HSD", "000 L", 6, 7)]),
    # The same block where one cost cell is "n.p.": everything after the gap shifts left one.
    "T21_3FUEL_10": (10, [("RLNG", "MMBTU", 0, 1), ("RFO", "000 t", 3, 4),
                          ("HSD", "000 L", 5, 6)]),
    # A dual- or tri-fuel plant's row with the other fuels blank: the metered fuel and its
    # quantity lead, costs trail. Labelled RLNG because Table 21's wide section is the
    # RLNG combined-cycle fleet; the intensity screen rejects the label where it is wrong.
    "T21_1FUEL":    (None, [("RLNG", "MMBTU", 0, 1)]),
    # Table 26 K-Electric - MMCFT throughout
    # Layout verified against the printed Bin Qasim TPS-I block: gas carries an intensity
    # column (CFT/kWh) before the RFO pair begins, so RFO sits at 3,4 and RLNG at 5,6 - not
    # at 2,3 and 4,5. The original guess produced 227 kg of furnace oil per kWh, which is how
    # the per-row intensity screen below came to exist.
    "T26_G_RFO_RLNG": (9, [("Gas", "MMCFT", 0, 1), ("RFO", "000 t", 3, 4),
                           ("RLNG", "MMCFT", 5, 6)]),
    "T26_G_RLNG":   (7,  [("Gas", "MMCFT", 0, 1), ("RLNG", "MMCFT", 3, 4)]),
    "T26_G_RLNG_HSD": (9, [("Gas", "MMCFT", 0, 1), ("RLNG", "MMCFT", 3, 4),
                           ("HSD", "000 L", 6, 7)]),
    "T26_HSD_RLNG": (6,  [("HSD", "000 L", 0, 1), ("RLNG", "MMCFT", 2, 3)]),
}

YEAR_ROW = re.compile(r"^(?P<name>.*?)(?P<year>(?:19|20)\d{2}-\d{2})\s+(?P<rest>.*)$")
NUM = re.compile(r"^-?[\d,]+(?:\.\d+)?$")

# A MULTI-FUEL SECTION ANNOUNCES ITSELF ONLY BY ITS COLUMN HEADER. Table 21's dual- and
# tri-fuel blocks carry no "(X based Power Plant)" heading at all - just a header line with one
# unit group per fuel, e.g. "(GWh) (MMBTU) Million) (GWh) (Net) (000 Liters) Million)". Without
# detecting that, the previous section's fuel persists and its rows are silently mis-attributed:
# the first run of this parser wrote 50,545,992 "kt of coal" for a plant whose quantity column
# was actually MMBTU of gas. Two or more unit groups on one line means multi-fuel, so stop.
# The discriminator is REPEATED columns, not the presence of units. A single-fuel header
# legitimately carries one generation unit and one quantity unit - "(GWh) (Net) ... (MMBTU)" -
# so counting all unit tokens kills the very sections we want. Multi-fuel headers repeat the
# pair: two "(GWh)" or two quantity units.
GEN_TOKEN = re.compile(r"\(GWh\)")
QTY_TOKEN = re.compile(r"\((?:MMBTU|000 [A-Za-z.]+)\)")


def _is_multi_fuel_header(line):
    return len(GEN_TOKEN.findall(line)) >= 2 or len(QTY_TOKEN.findall(line)) >= 2

# Text that is page furniture or a column heading rather than part of a plant's name.
NOT_A_NAME = re.compile(
    r"^(?:power|station|year|units?|generated|quantity|cost|average|overall|net|table"
    r"|statistical data|state of the industry|fuel|gen\.|consumption|rs\.|million|\d+)\b",
    re.IGNORECASE)

# A second, containment-based filter. The prefix list above missed "Gas Consumption Residual
# Furnace Oil" (starts with a fuel name) and "[1] Based on Units Sent Out" (starts with a
# bracket), and both became plant names with data rows attached. Any line carrying header or
# footnote vocabulary anywhere is furniture, whatever it starts with.
HEADER_TOKENS = re.compile(
    r"Consumption|MMCFT|MMBTU|\(GWh\)|\(Net\)|CFT/kWh|Kg/kWh|Quantity|Gen\. on"
    r"|Based on|Sent Out|Rs\./"
    # rc60: the UNIT vocabulary, which this list did not carry and which cost eight plant names.
    # "-layout" wraps a stacked column heading, so a line can hold the unit and NOTHING else:
    # "(000 M. Tons)      [1] & [2]" is the whole of source line 9972. It starts with a bracket,
    # so the prefix filter below never saw it; it names no fuel and no column, so this filter did
    # not either; and it was therefore kept and joined to the plant under it. The result shipped
    # as the plant NAME - "(000 M. Tons) & Gul Ahmed", "(Rs. Million) TPS Jamshoro (GENCO-I)",
    # "RLNG RFO HSD Overall kWh) KAPCO", "kWh) & Korangi CCPP" and four more. Nothing failed:
    # the quantities were all correct, and the damage was that 73 percent of the RFO mass in
    # this ledger could not be joined to any other table by name.
    r"|M\. Tons|000 liters|\(Average\)|Rs\. Million|Overall|kWh\)", re.IGNORECASE)

# Footnote markers appear inside legitimate plant names - "Korangi CCPP [3]" - so they are
# STRIPPED from a candidate rather than used to reject it; rejecting on them unnamed every
# Korangi row until this comment existed.
FOOTNOTE = re.compile(r"\[\d+\]")

# ...but stripping "[1] & [2]" leaves the conjunction "&" standing alone, and a lone conjunction
# passed every filter there was. It is the residue of the removal rather than anything the
# document says, so a scrap with no letter or digit in it is not a name fragment.
NO_WORD = re.compile(r"[^\W_]")



def _multi_section(line, table, ncount=None):
    """Spec key for a multi-fuel section header, or None.

    Detection is by header text where the document gives one, and by the row's number count
    only where it does not - Table 21's dual and tri fuel blocks are unheaded, but 8 numbers
    and 11 numbers are unambiguous within that table.
    """
    t = re.sub(r"\s+", " ", line)
    if table == 18:
        if "Gas Consumption" in t and "RFO Consumption" in t:
            return "T18_GAS_RFO"
        if "RLNG Consumption" in t:
            return "T18_RLNG"
        if "Gas Consumption" in t:
            return "T18_GAS"
    if table == 26:
        m = re.search(r"\(([A-Za-z0-9+. ]+?) based Power Plant\)", t)
        if m:
            return {"Gas+RFO+RLNG": "T26_G_RFO_RLNG", "Gas+RLNG": "T26_G_RLNG",
                    "Gas+RLNG+HSD": "T26_G_RLNG_HSD"}.get(m.group(1).strip())
        if "Gen. on HSD" in t and "Gen. on RLNG" in t:
            return "T26_HSD_RLNG"
    if ncount is not None:
        # Width-based fallback, only where the width is unambiguous within that table.
        # Table 21's one wide section mixes plants of different fuel counts under a single
        # header - dual-fuel rows are 8 numbers, tri-fuel 10 or 11, and rows where a fuel's
        # columns are simply blank collapse to 4 or 5 - so the width map is also consulted
        # PER ROW when a row does not fit the section's spec. The 4/5-wide rows are the
        # metered fuel alone with trailing costs, and the intensity screen vetoes any row
        # this heuristic gets wrong.
        return {21: {8: "T21_2FUEL", 10: "T21_3FUEL_10", 11: "T21_3FUEL",
                     5: "T21_1FUEL", 4: "T21_1FUEL"},
                18: {8: "T18_GAS_RFO", 5: "T18_GAS"},
                26: {7: "T26_G_RLNG", 6: "T26_HSD_RLNG"}}.get(table, {}).get(ncount)
    return None


def _unit_from_header(lines, start, default, window=8):
    """The quantity unit as the SECTION ITSELF states it, not as a lookup table assumes.

    This exists because a lookup was wrong. Gas is metered in MMBTU in Table 21 and in Table
    26's own gas section, but in MMCFT in Table 18 and in Table 26's RLNG section - the unit
    varies by section, not by table or by fuel. A global map labelled Table 26's RLNG volumes
    as MMBTU, which would have fed a volume into an energy comparison and silently turned the
    one assumption-free leg of the closure into an assumed one.
    """
    for line in lines[start:start + window]:
        if "MMBTU" in line:
            return "MMBTU"
        if "MMCFT" in line:
            return "MMCFT"
        if re.search(r"M\.?\s?Ton", line):
            return "000 t"
        if "Liters" in line or "litres" in line.lower():
            return "000 L"
    return default


# Plausibility bands for fuel intensity in NATIVE units per GWh. Generous on purpose - China
# Hub's printed 0.28 kg/kWh partial-load year is document truth and must pass - but a column
# mix-up is off by orders of magnitude and cannot. Rows failing the screen are dropped and
# counted: a mis-parsed row in a national ledger is worse than a missing one.
INTENSITY_BANDS = {
    "MMBTU": (4000.0, 20000.0),     # MMBTU/GWh: 17-86 percent implied efficiency
    "MMCFT": (4.0, 30.0),           # MMCFT/GWh = cft/kWh at typical heating values
    "000 t": (0.10, 2.5),           # kt/GWh = kg/kWh, spanning bituminous to wet lignite
    "000 L": (100.0, 600.0),        # kL/GWh = L/MWh for oil engines and turbines
}


def _implausible(fuel_unit, qty, gwh):
    if not gwh or not qty:
        return False                 # zero rows mean "did not run", not "misread"
    lo, hi = INTENSITY_BANDS[fuel_unit]
    return not (lo <= qty / gwh <= hi)

def _text():
    """The report's text layer, extracted on demand rather than committed."""
    if not os.path.exists(PDF):
        sys.exit("missing source: %s" % PDF)
    return subprocess.run(["pdftotext", "-layout", PDF, "-"],
                          capture_output=True, text=True, check=True).stdout.splitlines()


def _table_bounds(lines):
    """{table number: (start, end)} from the standalone 'TABLE n' headings."""
    marks = [(i, int(m.group(1)))
             for i, l in enumerate(lines)
             if (m := re.match(r"^\s+TABLE (\d+)\s*$", l))]
    out = {}
    for idx, (i, n) in enumerate(marks):
        end = marks[idx + 1][0] if idx + 1 < len(marks) else len(lines)
        out[n] = (i, end)          # later occurrences win: contents page first, body last
    return out


def _fy(token):
    """'2023-24' -> 2023, the repo's power convention (year N = FY N/N+1)."""
    return int(token.split("-")[0])


def _num(tok):
    return float(tok.replace(",", "")) if NUM.match(tok) else None


def parse(lines):
    bounds = _table_bounds(lines)
    rows, skipped, unparsed, skipped_rows = [], [], 0, []
    for table, system in sorted(TABLES.items()):
        if table not in bounds:
            continue
        start, end = bounds[table]
        fuel = unit = spec_key = None
        block = []                 # accumulating (name_fragment, year, numbers)
        prev_year = None

        def flush():
            """Close the current plant block: join its name scraps, emit one row per year."""
            if not block or (fuel is None and spec_key in (None, "PENDING")):
                return
            scraps = []
            for f, _y, _n in block:
                f = FOOTNOTE.sub("", f).strip()
                if (f and NO_WORD.search(f)
                        and not HEADER_TOKENS.search(f) and not NOT_A_NAME.match(f)):
                    scraps.append(f)
            name = re.sub(r"\s+", " ", " ".join(scraps)).strip()
            if not name:
                name = "UNNAMED"
            for _f, year, nums in block:
                if spec_key:
                    # Multi-fuel: one output row per fuel, positions from the section spec.
                    # A row that does not fit the section's width is re-resolved on its own
                    # width first - Table 21 mixes plant shapes under one header - and only
                    # skipped when no spec fits.
                    want, fuels = MULTI_SPECS[spec_key]
                    if want is not None and len(nums) != want:
                        rekey = _multi_section("", table, ncount=len(nums))
                        if rekey and MULTI_SPECS[rekey][0] in (len(nums), None):
                            want, fuels = MULTI_SPECS[rekey]
                        else:
                            skipped_rows.append("%s FY%d: %d numbers, spec wants %d"
                                                % (spec_key, year, len(nums), want))
                            continue
                    for fname, funit, gi, qi in fuels:
                        g, q = nums[gi], nums[qi]
                        if not g and not q:
                            continue          # plant did not run on this fuel that year
                        if _implausible(funit, q, g):
                            skipped_rows.append("%s %s FY%d: %.3g %s per GWh"
                                                % (name, fname, year, q / g if g else 0,
                                                   funit))
                            continue
                        tj = round(q * TJ_PER_MMBTU, 3) if funit == "MMBTU" else ""
                        hr = round(tj * 1e9 / (g * 1e6), 1) if (tj and g) else ""
                        rows.append({
                            "fiscal_year": year, "system": system, "plant": name,
                            "fuel": fname, "fuel_origin": _origin(fname, name),
                            "quantity": q, "quantity_unit": funit,
                            "energy_TJ": tj, "net_generation_GWh": g,
                            "implied_heat_rate_kJ_per_kWh": hr,
                            "source_table": "NEPRA SoIR 2024 Table %d" % table,
                        })
                    continue
                gwh = nums[0] if len(nums) > 0 else None
                qty = nums[1] if len(nums) > 1 else None
                if gwh is None or qty is None:
                    continue
                if _implausible(unit, qty, gwh):
                    skipped_rows.append("%s %s FY%d: %.3g %s per GWh"
                                        % (name, fuel, year, qty / gwh if gwh else 0, unit))
                    continue
                # Gas and RLNG are metered in MMBTU, so their energy is exact. Coal and RFO
                # are masses and need a calorific value, which is a downstream choice - left
                # blank here rather than assumed inside a parser.
                tj = round(qty * TJ_PER_MMBTU, 3) if unit == "MMBTU" else ""
                hr = round(tj * 1e9 / (gwh * 1e6), 1) if (tj and gwh) else ""
                rows.append({
                    "fiscal_year": year, "system": system, "plant": name,
                    "fuel": fuel, "fuel_origin": _origin(fuel, name),
                    "quantity": qty, "quantity_unit": unit,
                    "energy_TJ": tj, "net_generation_GWh": gwh,
                    "implied_heat_rate_kJ_per_kWh": hr,
                    "source_table": "NEPRA SoIR 2024 Table %d" % table,
                })

        pending = []               # name fragments on their own lines, awaiting a year row
        for idx, raw in enumerate(lines[start:end]):
            line = raw.rstrip()
            m = SECTION.search(line)
            if m:
                flush(); block, prev_year, pending = [], None, []
                fuels = m.group("fuels").strip()
                if "+" in fuels:                       # multi-fuel: resolve against the specs
                    spec_key = _multi_section(line, table)
                    fuel = unit = None
                    if spec_key is None:
                        skipped.append("Table %d: %s" % (table, fuels))
                else:
                    spec_key = None
                    fuel, unit = FUEL_UNIT.get(fuels, (None, None))
                    if fuel is not None:
                        unit = _unit_from_header(lines, start + idx + 1, unit)
                    if fuel is None:
                        skipped.append("Table %d: %s (unknown fuel)" % (table, fuels))
                continue
            key = _multi_section(line, table)
            if key:
                flush(); block, prev_year, pending = [], None, []
                spec_key, fuel, unit = key, None, None
                continue
            if spec_key is None and _is_multi_fuel_header(line):   # unheaded: resolve on width
                flush(); block, prev_year, pending = [], None, []
                spec_key, fuel, unit = "PENDING", None, None
                continue
            ym = YEAR_ROW.match(line)
            if not ym:
                # A plant's name is often on rows of its own between the year rows, so those
                # have to be kept rather than skipped - Port Qasim and China Power Hub came out
                # UNNAMED until they were.
                text = FOOTNOTE.sub("", line).strip()
                if (text and not NOT_A_NAME.match(text) and not NUM.match(text)
                        and not HEADER_TOKENS.search(text)):
                    pending.append(text)
                continue
            year = _fy(ym.group("year"))
            nums = [v for v in (_num(t) for t in ym.group("rest").split()) if v is not None]
            if not nums:
                unparsed += 1
                continue
            if spec_key == "PENDING":
                spec_key = _multi_section("", table, ncount=len(nums))
                if spec_key is None:
                    skipped.append("Table %d: unresolved multi-fuel block (%d numbers)"
                                   % (table, len(nums)))
            if prev_year is not None and year <= prev_year:
                flush(); block = []                    # years stopped ascending: new plant
            block.append((" ".join(pending + [ym.group("name")]), year, nums))
            pending = []
            prev_year = year
        flush()
    return rows, skipped, unparsed, skipped_rows


def main(check=False):
    rows, skipped, unparsed, skipped_rows = parse(_text())

    # The report itself repeats plants - Punjab Thermal appears in two Table 21 blocks, with
    # generation differing by one percent between them (3,197.29 against 3,163.70 GWh in
    # FY2023-24, same fuel quantity). Summing both would over-count the fleet, so duplicates
    # of (year, system, plant, fuel) keep the first occurrence in document order; a duplicate
    # whose values differ by more than 2 percent is a parse fault and reported loudly.
    seen, deduped, dupes = {}, [], []
    for r in rows:
        key = (r["fiscal_year"], r["system"], r["plant"], r["fuel"])
        if key in seen:
            kept = seen[key]
            for col in ("quantity", "net_generation_GWh"):
                a, b = float(kept[col]), float(r[col])
                if a and abs(a - b) / a > 0.02:
                    dupes.append("CONFLICT %s: %s %s vs %s" % (key, col, a, b))
                    break
            else:
                dupes.append("duplicate dropped: FY%s %s %s (document repeats the plant)"
                             % (r["fiscal_year"], r["plant"], r["fuel"]))
            continue
        seen[key] = r
        deduped.append(r)
    rows = deduped
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    cols = ["fiscal_year", "system", "plant", "fuel", "fuel_origin", "quantity",
            "quantity_unit", "energy_TJ", "net_generation_GWh",
            "implied_heat_rate_kJ_per_kWh", "source_table"]
    if write_or_check(OUT, cols,
                      sorted(rows, key=lambda r: (r["system"], r["fuel"], r["plant"],
                                            r["fiscal_year"])), check):
        return 1
    if check:
        print("the plant fuel ledger reproduces from the held document.")
        return 0

    plants = {(r["system"], r["plant"], r["fuel"]) for r in rows}
    print("wrote %s" % os.path.relpath(OUT, ROOT))
    print("  %d rows, %d plant-fuel series, FY%d-FY%d"
          % (len(rows), len(plants), min(r["fiscal_year"] for r in rows),
             max(r["fiscal_year"] for r in rows)))
    for system in sorted(TABLES.values()):
        sub = [r for r in rows if r["system"] == system]
        by_fuel = {}
        for r in sub:
            by_fuel[r["fuel"]] = by_fuel.get(r["fuel"], 0) + 1
        print("  %-11s %3d rows  %s" % (system, len(sub),
                                        ", ".join("%s %d" % kv for kv in sorted(by_fuel.items()))))
    # COVERAGE, STATED RATHER THAN IMPLIED. The multi-fuel sections are not parsed, so this
    # ledger is a subset of the fleet and every downstream use has to know by how much.
    latest = max(r["fiscal_year"] for r in rows)
    parsed_gwh = sum(r["net_generation_GWh"] for r in rows if r["fiscal_year"] == latest)
    print("  FY%d-%d coverage: %.0f GWh of %.0f GWh total thermal (Table 17) = %.1f%%"
          % (latest, (latest + 1) % 100, parsed_gwh, TABLE17_THERMAL_GWH,
             100 * parsed_gwh / TABLE17_THERMAL_GWH))
    coal = sum(r["net_generation_GWh"] for r in rows
               if r["fiscal_year"] == latest and r["fuel"] == "Coal")
    print("  coal is effectively complete: %.1f GWh against CPPA-G's %.1f GWh (Table 17)"
          % (coal, TABLE17_COAL_CPPAG_GWH))
    origins = {}
    for r in rows:
        if r["fuel"] == "Coal" and r["fiscal_year"] == latest:
            origins[r["fuel_origin"]] = origins.get(r["fuel_origin"], 0.0) + r["net_generation_GWh"]
    for o, v in sorted(origins.items(), key=lambda kv: -kv[1]):
        print("      %-14s %8.1f GWh  %4.1f%%" % (o, v, 100 * v / coal))
    print("  duplicates: %d" % len(dupes))
    for m in dupes:
        print("      %s" % m)
    print("  rows dropped by the intensity screen: %d" % len(skipped_rows))
    for m in skipped_rows:
        print("      %s" % m)
    print("  sections_skipped (multi-fuel, not parsed): %d" % len(skipped))
    for s in sorted(set(skipped)):
        print("      %s" % s)
    if unparsed:
        print("  year rows with no numbers (headers/notes): %d" % unparsed)


if __name__ == "__main__":
    sys.exit(main(check="--check" in sys.argv))
