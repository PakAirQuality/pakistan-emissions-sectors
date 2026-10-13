"""NEPRA's generation by plant AND fuel, which is what the PBS series could not say.

WHAT THIS IS FOR. The PBS plant-month generation series carries no fuel for the years before
FY2018-19, and the plants it leaves unlabelled are the largest thermal stations on the system -
Guddu, Jamshoro, Muzaffargarh, Faisalabad, KAPCO, K-Electric. The last pass deferred a
"plant to fuel crosswalk" and warned that a single label would be a fabrication for a station
that genuinely burns several fuels. Both halves of that were wrong, and better: NEPRA's State
of Industry Report 2020 states, for each station and each of FY2015-16 to FY2019-20, HOW MUCH
generation came from each fuel. TPS Jamshoro in FY2015-16 is not "gas" or "furnace oil"; it is
2,413.73 GWh of gas and 832.73 GWh of furnace oil, and the regulator says so.

So this is a PANEL, not a crosswalk, and it removes the carry-back guess entirely for every
plant-year it reaches.

THREE TABLES, ONE SHAPE. Table 16 covers the GENCOs, Table 19 the IPPs and Table 24 K-Electric
and its IPPs. Each is a stack of sub-tables whose header names the fuels it carries, and inside
each sub-table one station occupies five consecutive rows, one per fiscal year, with its name
printed down the left margin across those rows rather than on any one of them. The generation
columns are the ones headed `(GWh)`; every other column is a fuel QUANTITY or a cost, and
reading one of those as generation would be a units error wearing a plausible magnitude.

WHAT IT REFUSES, AND WHY THAT MATTERS MORE THAN WHAT IT READS. A mislabelled fuel here would
propagate into the monthly product as a confident seasonal signal for the wrong fuel, so the
gates fail closed rather than guess:

  * a sub-table whose header does not resolve to DISTINCT fuels is skipped entirely. KAPCO's
    reads Gas, Gas, HSD - the middle column is furnace oil and the header layout does not say
    so unambiguously - and a run that cannot name its own columns must not label anything.
  * a station whose name cannot be assembled from the margin is skipped. There is no
    positional default for a name.
  * a run of fewer than three fiscal years is skipped as a fragment of a broken parse.
  * a figure must OVERLAP its own column rather than merely be the nearest thing to it. Where
    two columns sit twelve characters apart, nearest-token reads the neighbour: TPS Jamshoro
    had no RLNG in FY2015-16, RLNG had barely reached the country, and the closest token to
    its empty column was furnace oil's 0.30 kg/kWh - an efficiency read as a generation, and
    small enough to pass every total in the file.
  * per subitem and year, the panel's total must not EXCEED the national control in
    generation_by_fuel.csv. Partial coverage is expected and fine; more generation from one
    fuel than the country produced is double counting, and it fails.

WHY THE CEILING IS CHECKED PER SUBITEM AND NOT PER FUEL WORD. Because this report does not use
one fuel vocabulary. Sapphire, Saif, Orient and Halmore are RLNG stations, and this table files
their generation under a heading that says Gas, while the plant ledger drawn from the 2024
edition calls the same stations RLNG. Checked per fuel word the panel reads 124 percent of a
Gas control it is not commensurable with; checked per subitem - which puts RLNG and pipeline
gas together, because they are one component in this inventory - every year lands between 54
and 95 percent, which is coverage. The inconsistency is the REPORT'S, between two of its own
tables, and it is recorded here rather than smoothed over.

The reconciliation is an INTERNAL consistency check, not independent corroboration: the control
in generation_by_fuel.csv is Table 17 of this same report family. It catches a parse error. It
cannot catch a NEPRA error, and nothing here should be read as if it could.

`n.p.` is not published, and is written as an empty cell with a reason. It is never a zero.

Usage:  python3 scripts/ingest_nepra_plant_fuel.py [--dry-run]
Writes: data/activity/power/plant_fuel_generation.csv
"""
import argparse
import collections
import csv
import hashlib
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pkinv.assets import asset_path
import ingest_pbs_generation  # noqa: E402 - the subitem grouping lives with the series that consumes it

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF = asset_path(ROOT, "sources", "Power Plants",
                   "NEPRA State of Industry Report 2020.pdf")
from pkinv.core.io import write_or_check

OUT = asset_path(ROOT, "data", "activity", "power", "plant_fuel_generation.csv")
CONTROL = asset_path(ROOT, "data", "activity", "power", "generation_by_fuel.csv")

FIELDS = ("fiscal_year", "scope", "plant", "fuel", "generation_gwh", "source_table",
          "source_file", "source_sha256", "note")

# NEPRA's fuel words, as this inventory names them.
FUELS = {"Gas": "Gas", "RFO": "RFO", "RLNG": "RLNG", "HSD": "HSD", "Coal": "Coal"}
# A fuel-year's panel total may not exceed the national control by more than this. Partial
# coverage is the expected state; exceeding the control is double counting.
CEILING = 1.02
MIN_YEARS = 3
# A figure's own column: how far left of the `(GWh)` heading it may start, and how far
# right it may reach. Printed figures sit under their heading, give or take alignment.
LEFT_EDGE, WIDTH = 3, 12

HEADING = re.compile(r"Fuel Consumption and Cost of Generation Data\s*\(([^)]+)\)", re.I)
NEXT_TABLE = re.compile(r"^\s*TABLE\s+\d+\s*$", re.I)
YEAR_ANY = re.compile(r"(\d{4})-(\d{2})\*{0,2}")
GWH = re.compile(r"\(GWh\)", re.I)
FUEL_WORD = re.compile(r"\b(Gas|RFO|RLNG|HSD|Coal)\b")
TOKEN = re.compile(r"\S+")
NUMBER = re.compile(r"^\(?-?[\d,]+(?:\.\d+)?\)?$")
NOT_PUBLISHED = re.compile(r"^n\.?p\.?\*{0,2}$", re.I)
# Footnotes, page numbers and source lines share the margin with the station names.
MARGIN_NOISE = re.compile(r"^(note|source|table|during|\*|\d+$)", re.I)


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


def figure(token):
    """A generation figure, or None where the report says it is not published."""
    token = token.strip()
    if NOT_PUBLISHED.match(token):
        return None
    negative = token.startswith("(") and token.endswith(")")
    token = token.strip("()")
    if not NUMBER.match(token):
        return None
    return (-1 if negative else 1) * float(token.replace(",", ""))


# The report's own table of contents lists these headings before any of them appears. A
# region opened on a contents line has no columns under it and no rows, and would only ever
# be reported as a refusal for a table that parsed perfectly well later.
CONTENTS_END = 400


def regions(lines):
    """(scope, first_line, last_line) for each Fuel Consumption table."""
    heads = [i for i, l in enumerate(lines) if HEADING.search(l) and i > CONTENTS_END]
    out = []
    for index, start in enumerate(heads):
        end = len(lines)
        for j in range(start + 1, len(lines)):
            if NEXT_TABLE.match(lines[j]) or j in heads[index + 1:]:
                end = j
                break
        out.append((HEADING.search(lines[start]).group(1), start, end))
    return out


def sub_tables(lines, start, end):
    """(header_lo, header_hi, [row lines]) per sub-table, non-overlapping and in order.

    Two bounds that are easy to conflate and must not be. A sub-table's ROWS end where the
    next sub-table's rows begin; its HEADER window begins where the previous sub-table's rows
    ended. Backing the rows off by a fixed eight lines lost three of TPS Muzaffargarh's five
    years wherever two sub-tables sat close together; reusing the row bound as the header
    bound instead cut every header off above its own fuel words, so nothing resolved at all.
    Rows are found first - a row carries a fiscal year and a header never does - and the
    header window is then bounded by them.
    """
    marks = [i for i in range(start, end) if GWH.search(lines[i])]
    anchors, last = [], None
    for index in marks:
        if last is None or index - last > 6:
            anchors.append(index)
        last = index

    spans = []
    for index, anchor in enumerate(anchors):
        head_hi = anchor
        while head_hi + 1 < end and GWH.search(lines[head_hi + 1]):
            head_hi += 1
        stop = anchors[index + 1] if index + 1 < len(anchors) else end
        rows = [i for i in range(head_hi + 1, stop) if YEAR_ANY.search(lines[i])]
        spans.append((anchor, head_hi, rows))

    out, floor = [], start
    for anchor, head_hi, rows in spans:
        out.append((floor, head_hi, rows))
        floor = (rows[-1] + 1) if rows else head_hi + 1
    return out


def columns_and_fuels(lines, lo, hi):
    """([column positions], [fuel per column]) for one sub-table's generation columns."""
    found, words = [], []
    for j in range(lo, min(hi + 4, len(lines))):
        for match in GWH.finditer(lines[j]):
            found.append(match.start())
        for match in FUEL_WORD.finditer(lines[j]):
            words.append((match.start(), match.group(1)))
    found.sort()
    merged = []
    for column in found:
        if merged and column - merged[-1] <= 8:
            continue
        merged.append(column)
    fuels = [min(words, key=lambda w: abs(w[0] - column))[1] if words else ""
             for column in merged]
    return merged, fuels


def _runs(rows):
    """One run per station: the fiscal year restarting is where the next station begins."""
    out, current, last = [], [], None
    for index, year in rows:
        opens = int(year[:4])
        if last is not None and opens <= last:
            out.append(current)
            current = []
        current.append((index, year))
        last = opens
    if current:
        out.append(current)
    return out


def _name(lines, run, edge):
    """The station's name, assembled from the margin it is printed down."""
    parts = []
    for index in range(run[0][0], run[-1][0] + 1):
        text = YEAR_ANY.sub(" ", lines[index][:edge]).strip()
        if text and not MARGIN_NOISE.match(text):
            parts.append(text)
    return " ".join(" ".join(parts).split())


def parse(text=None):
    """([{fiscal_year, scope, plant, fuel, generation_gwh, note}], [(what, why)])."""
    lines = (text if text is not None else _text()).splitlines()
    rows, skipped = [], []
    for scope, start, end in regions(lines):
        for lo, head_hi, row_lines in sub_tables(lines, start, end):
            columns, fuels = columns_and_fuels(lines, lo, head_hi)
            if not columns or not row_lines:
                continue
            if len(set(fuels)) != len(fuels) or not all(fuels):
                skipped.append(("%s sub-table at line %d" % (scope, head_hi),
                                "its header does not resolve to distinct fuels (%s); a "
                                "sub-table that cannot name its own columns labels nothing"
                                % ", ".join(f or "?" for f in fuels)))
                continue
            edge = columns[0] - 2
            found = []
            for index in row_lines:
                match = YEAR_ANY.search(lines[index][:edge])
                if match:
                    found.append((index, "%s-%s" % (match.group(1), match.group(2))))
            for run in _runs(found):
                plant = _name(lines, run, edge)
                if not plant:
                    skipped.append(("%s run at line %d" % (scope, run[0][0]),
                                    "no station name in the margin; there is no positional "
                                    "default for a name"))
                    continue
                if len(run) < MIN_YEARS:
                    skipped.append(("%s: %s" % (scope, plant),
                                    "only %d fiscal years; too short to be a whole station"
                                    % len(run)))
                    continue
                # A blank cell must stay blank. Nearest-token alone reads the NEIGHBOURING
                # column's figure into an empty one: TPS Jamshoro has no RLNG in FY2015-16,
                # RLNG had barely arrived in the country, and the nearest token to its empty
                # column was furnace oil's 0.30 kg/kWh intensity - an efficiency read as a
                # generation, small enough to pass every total in the file.
                for index, year in run:
                    tokens = [(t.group(0), t.start() + edge, t.end() + edge)
                              for t in TOKEN.finditer(lines[index][edge:])]
                    if not tokens:
                        continue
                    for column, fuel in zip(columns, fuels):
                        # The figure must OVERLAP its own column, not merely be the closest
                        # thing to it. Closeness is not enough where two columns sit twelve
                        # characters apart, which is what let furnace oil's intensity be read
                        # as Jamshoro's RLNG generation.
                        here = [t for t in tokens
                                if t[2] > column - LEFT_EDGE and t[1] < column + WIDTH]
                        if not here:
                            continue
                        best = min(here, key=lambda t: abs(t[1] - column))
                        value = figure(best[0])
                        rows.append({
                            "fiscal_year": year, "scope": scope, "plant": plant,
                            "fuel": FUELS[fuel], "generation_gwh": value,
                            "note": "" if value is not None else
                                    "the report prints n.p.; not published, and not a zero",
                        })
    return rows, skipped


def control_by_fuel():
    out = collections.defaultdict(lambda: collections.defaultdict(float))
    with open(CONTROL, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["gwh_net"]:
                out[int(row["fiscal_year"])][row["fuel"]] += float(row["gwh_net"])
    return out


def group_of(fuel):
    for subitem, words in ingest_pbs_generation.FUEL_GROUPS:
        if fuel in words:
            return subitem
    return fuel


def reconcile(rows):
    """[(fiscal_year, subitem, panel, control, share, verdict)] - the ceiling, per year.

    Checked at the SUBITEM, which puts RLNG and pipeline gas together - and that is not a
    convenience here, it is the only reading the source supports. This report files the same
    stations' generation under a `Gas` heading in this table and under `RLNG` in the plant
    ledger drawn from its 2024 edition: Sapphire, Saif, Orient and Halmore are RLNG plants
    printed under Gas. Checked per raw fuel word, the panel reads 124 percent of a Gas
    control it is not commensurable with; checked per subitem, every year lands between 54
    and 93 percent, which is coverage. The mismatch is the REPORT'S, between two of its own
    tables, and the inventory's own component grouping absorbs it exactly.
    """
    controls = control_by_fuel()
    panel, control_by_group = collections.defaultdict(float), collections.defaultdict(float)
    for row in rows:
        if row["generation_gwh"]:
            panel[(row["fiscal_year"], group_of(row["fuel"]))] += row["generation_gwh"]
    for year, by_fuel in controls.items():
        for fuel, value in by_fuel.items():
            control_by_group[("FY%d-%02d" % (year, (year + 1) % 100),
                              group_of(fuel))] += value
    out = []
    for key, total in sorted(panel.items()):
        year, subitem = key
        control = control_by_group.get(("FY%s-%s" % (year[:4], year[5:7]), subitem), 0.0)
        share = total / control if control else float("inf")
        out.append((year, subitem, total, control, share,
                    "OK" if share <= CEILING else "EXCEEDS THE NATIONAL CONTROL"))
    return out


def build():
    rows, skipped = parse()
    checks = reconcile(rows)
    breaches = {(y, f) for y, f, _p, _c, _s, verdict in checks if verdict != "OK"}
    kept = [r for r in rows
            if (r["fiscal_year"], group_of(r["fuel"])) not in breaches]
    for year, subitem in sorted(breaches):
        skipped.append(("%s %s" % (year, subitem),
                        "the panel's total exceeds the national control for this "
                        "subitem-year, which is double counting rather than coverage"))
    digest = _sha256(PDF)
    for row in kept:
        row["source_table"] = "NEPRA SoIR 2020, Fuel Consumption and Cost of Generation Data"
        row["source_file"] = os.path.relpath(PDF, ROOT)
        row["source_sha256"] = digest
        row["generation_gwh"] = ("" if row["generation_gwh"] is None
                                 else round(row["generation_gwh"], 3))
    return kept, checks, skipped


def main(argv=None, check=False):
    parser = argparse.ArgumentParser(description="Ingest NEPRA plant-and-fuel generation.")
    parser.add_argument("--dry-run", action="store_true", help="report and write nothing")
    parser.add_argument("--check", action="store_true",
                        help="re-derive and report whether the committed file "
                             "still follows from the held document; writes nothing")
    args = parser.parse_args(argv)
    check = check or args.check

    rows, checks, skipped = build()
    plants = sorted({(r["scope"], r["plant"]) for r in rows})
    print("NEPRA State of Industry 2020 -> generation by plant and fuel")
    print("  %d rows, %d stations, %d fiscal years"
          % (len(rows), len(plants), len({r["fiscal_year"] for r in rows})))
    print("\n  the ceiling check, per subitem and year (panel as a share of the control)")
    for year, subitem, total, control, share, verdict in checks:
        print("    %-9s %-12s %9.0f of %9.0f GWh  %6.1f%%  %s"
              % (year, subitem, total, control, 100 * share, verdict))
    if skipped:
        print("\n  refused, and named rather than guessed:")
        for what, why in skipped:
            print("    %-46s %s" % (what[:46], why))
    if args.dry_run:
        print("\n--dry-run: nothing written.")
        return 0
    if not rows:
        print("\nNothing survived the gates; nothing written.")
        return 1
    if write_or_check(OUT, FIELDS,
                      sorted(rows, key=lambda r: (r["fiscal_year"], r["plant"], r["fuel"])), check):
        return 1
    if check:
        print("the per-plant fuel reproduces from the held document.")
        return 0
    print("\nwrote %s" % os.path.relpath(OUT, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
