"""Ingest NEPRA State of Industry Report thermal generation by fuel.

Source: NEPRA's annual State of the Industry Report, Table 17 "Thermal Electricity
Generation by Sector and by Fuel (GWh) (Net)". Each edition carries five fiscal years, so
stacking editions reaches back well past FY2006.

This is the table that unblocks the power sector. Capacity is useless for emissions, and
the Pakistan Economic Survey publishes NEPRA generation with "Thermal" aggregated into one
line — no coal, gas or oil split. Table 17 has exactly that split, separated further into
the CPPA-G and K-Electric systems.

Two things it fixes for free. NEPRA includes K-Electric, which the Economic Survey does
not: SIR's FY2023-24 national total of 137,196 GWh against the Survey's 127,523 is almost
entirely Karachi. And it separates RLNG from domestic gas, which matters for cost but not
for emissions, so the split is preserved here and merged only at the emission-factor step.

YEARS ARE FISCAL, July to June, matching the aviation sector's convention.

Usage:  python3 scripts/ingest_power.py [dir-of-SIR-pdfs]
Writes: data/activity/power/generation_by_fuel.csv
"""

from pkinv.assets import asset_path
import csv
import os
import re
import subprocess
import sys

from pkinv.core.io import write_or_check
from pkinv.paths import DATA

DEFAULT_SRC = asset_path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "sources", "Power Plants")

# The 2025 edition's text layer is OCR (Paper Capture) and renders several thousands-
# separators as decimal points, so its Table 3 numbers are corrupt as extracted. Its one
# novel Table 3 year (FY2023-24) is carried by the OCR-REPAIRED rows preserved below;
# every other year it covers exists natively in the 2023/2024 editions. Table 17 in the
# same edition extracts cleanly and reconciles, so only Table 3 is skipped.
SKIP_TABLE3_EDITIONS = {"2025"}
OUT_DIR = asset_path(DATA, "activity", "power")
OUT = asset_path(OUT_DIR, "generation_by_fuel.csv")
OUT_FUEL = asset_path(OUT_DIR, "fuel_consumed.csv")

# Table 3 fuel labels -> the IPCC fuel the emission factor is keyed on
TABLE3_FUELS = ("Gas", "Furnace Oil", "Diesel Oil", "Coal")

FUELS = ("Gas", "RLNG", "RFO", "HSD", "Coal")
NUM = re.compile(r"-?[\d,]+\.\d{2}|-?[\d,]{1,3}(?:,\d{3})+|\b\d+\.\d{2}\b")
# "2019-20   2020-21   2021-22 ..." on the header line under the table title
YEARS = re.compile(r"(20\d{2})-\d{2}")


def _nums(s):
    return [float(m.group(0).replace(",", "")) for m in NUM.finditer(s)]


def parse_table17(path):
    """Return (years, {(fuel, system): [GWh per year]}, total_thermal[list]).

    NEPRA's server truncates large transfers, so a half-downloaded PDF is a normal
    occurrence rather than an exceptional one. Treat it as a skip, not a crash.
    """
    r = subprocess.run(["pdftotext", "-layout", path, "-"], capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout.strip():
        raise SystemExit("unreadable PDF (likely a truncated download)")
    text = r.stdout
    lines = text.split("\n")

    start = None
    for i, ln in enumerate(lines):
        if "Thermal Electricity Generation by Sector and by Fuel" in ln and i > 500:
            start = i
            break
    if start is None:
        raise SystemExit("Table 17 not found in %s" % os.path.basename(path))

    block = lines[start:start + 60]
    years = []
    for ln in block[:4]:
        found = YEARS.findall(ln)
        if len(found) >= 3:
            years = [int(y) for y in found]
            break
    if not years:
        raise SystemExit("no fiscal-year header under Table 17 in %s" % os.path.basename(path))

    out, total = {}, []
    fuel = None
    for ln in block:
        for f in FUELS:
            # the fuel label sits alone in the left margin of its own row group
            if re.match(r"^\s{4,}%s\s*$" % re.escape(f), ln):
                fuel = f
        m = re.search(r"Generation on (\w+) \(GWh\)", ln)
        if m and m.group(1) in FUELS:
            v = _nums(ln.split("(GWh)")[1])[:len(years)]
            if len(v) == len(years):
                # CPPA-G row comes first, then KE, then Total; keep the first two
                key_system = "CPPA-G" if (m.group(1), "CPPA-G") not in out else (
                    "K-Electric" if (m.group(1), "K-Electric") not in out else "Total")
                out[(m.group(1), key_system)] = v
        if re.match(r"^\s*Total Thermal Generation", ln) and not total:
            v = _nums(ln)[:len(years)]
            if len(v) == len(years):
                total = v
    return years, out, total


def parse_table3(path):
    """Return (years, {fuel: [TOE per year]}, total[list]) from SIR Table 3.

    Fuel consumption for thermal power generation, in tonnes of oil equivalent, sourced
    by NEPRA from the HDIP Pakistan Energy Yearbook. This is the activity basis the
    sector uses: TOE is already an energy unit, so the ruinous net-calorific-value
    uncertainty on lignite (IPCC range 5.50-21.6 TJ/Gg) never enters the calculation.
    """
    r = subprocess.run(["pdftotext", "-layout", path, "-"], capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout.strip():
        raise SystemExit("unreadable PDF (likely a truncated download)")
    lines = r.stdout.split("\n")
    # Two anchors, because the 2019 edition prints the body table with NO title line at
    # all - just prose ending "given in table 3 as follows:" above the Source/Unit
    # header. The list-of-tables entry at the back of that edition carries the title and
    # would otherwise be the only (useless) match.
    starts = [i for i, ln in enumerate(lines)
              if "Fuel Consumption for Thermal Power Generation (TOE)" in ln and i > 500]
    starts += [i for i, ln in enumerate(lines)
               if re.search(r"in table 3 as follows", ln, re.IGNORECASE)]
    block, years = None, []
    for start in starts:
        cand = lines[start:start + 22]
        for ln in cand[:6]:
            found = YEARS.findall(ln)
            if len(found) >= 3:
                years = [int(y) for y in found]
                block = cand
                break
        if block:
            break
    if block is None:
        raise SystemExit("no fiscal-year header under Table 3")

    out, total = {}, []
    for i, ln in enumerate(block):
        for f in TABLE3_FUELS:
            # Two layouts across editions. 2019-2022 and 2024: the fuel label sits on its
            # own line with its TOE row directly ABOVE it (and % share below). 2023: label,
            # the unit word TOE and the values share one line.
            if re.match(r"^\s{2,}%s\s*$" % re.escape(f), ln) and i > 0:
                v = _nums(block[i - 1])[:len(years)]
                if len(v) == len(years) and f not in out:
                    out[f] = v
            m = re.match(r"^\s+%s\s+TOE\s+(.*)$" % re.escape(f), ln)
            if m and f not in out:
                v = _nums(m.group(1))[:len(years)]
                if len(v) == len(years):
                    out[f] = v
        if re.match(r"^\s{2,}Total\s*$", ln) and i > 0 and not total:
            v = _nums(block[i - 1])[:len(years)]
            if len(v) == len(years):
                total = v
        m = re.match(r"^\s+Total\s+TOE\s+(.*)$", ln)
        if m and not total:
            v = _nums(m.group(1))[:len(years)]
            if len(v) == len(years):
                total = v
    return years, out, total


def _edition_year(fn):
    m = re.search(r"(20\d{2})", fn)
    return m.group(1) if m else fn


def main(src=DEFAULT_SRC, check=False):
    # Both naming shapes on disk: the original scratchpad copies were nepra_sir_YYYY.pdf;
    # the committed sources carry NEPRA's own filenames.
    pdfs = sorted(f for f in os.listdir(src)
                  if f.lower().endswith(".pdf")
                  and (f.lower().startswith("nepra_sir")
                       or f.startswith("NEPRA State of Industry Report")))
    if not pdfs:
        raise SystemExit("no SIR PDFs in %s" % src)

    rows, checks = {}, []
    fuel_rows, fuel_checks = {}, []
    for fn in sorted(pdfs, key=_edition_year):
        path = asset_path(src, fn)
        edition = _edition_year(fn)
        years = []
        # Table 17 failure must not cost the edition its Table 3: the two tables entered
        # the report in different years and fail independently.
        try:
            years, table, total = parse_table17(path)
            # ONLY VERIFIED YEARS ENTER THE LEDGER. A year whose fuel-system rows do not
            # reproduce the report's own printed Total Thermal row is a mis-parse, and a
            # mis-parsed row in a national dataset is worse than a missing one.
            verified = set()
            for i, y in enumerate(years):
                got = sum(v[i] for (f, s), v in table.items() if s != "Total")
                if total and i < len(total):
                    checks.append((edition, y, total[i], got))
                    if abs(total[i] - got) < 1.0:
                        verified.add(y)
            for (fuel, system), vals in table.items():
                if system == "Total":
                    continue
                for y, v in zip(years, vals):
                    if y not in verified:
                        continue
                    # later editions supersede earlier ones for a repeated fiscal year
                    rows[(y, fuel, system)] = {
                        "fiscal_year": y, "fuel": fuel, "system": system, "gwh_net": v,
                        "source": "NEPRA State of Industry Report %s, Table 17" % edition,
                    }
        except SystemExit as e:
            print("  %-45s (no Table 17: %s)" % (fn, e))
        if edition in SKIP_TABLE3_EDITIONS:
            print("  %-45s Table 3 skipped: OCR text layer corrupts its numbers; the "
                  "novel year is carried by the preserved repaired rows" % fn)
        else:
            try:
                fyears, ftable, ftotal = parse_table3(path)
                fverified = set()
                for i, y in enumerate(fyears):
                    got = sum(v[i] for v in ftable.values())
                    if ftotal and i < len(ftotal):
                        fuel_checks.append((edition, y, ftotal[i], got))
                        if abs(ftotal[i] - got) < 1.0:
                            fverified.add(y)
                for fuel, vals in ftable.items():
                    for y, v in zip(fyears, vals):
                        if y not in fverified:
                            continue
                        fuel_rows[(y, fuel)] = {
                            "fiscal_year": y, "fuel": fuel, "toe": v,
                            "source": "NEPRA State of Industry Report %s, Table 3 "
                                      "(from HDIP Pakistan Energy Yearbook)" % edition}
            except SystemExit as e:
                print("    (no Table 3: %s)" % e)
        print("  %-45s %d Table 17 fiscal years: %s"
              % (fn, len(years), ", ".join(str(y) for y in years) or "-"))

    # Rows the parser cannot reproduce but the record must keep: the FY2023-24 Table 3
    # values exist only in the OCR edition and were repaired by documented cross-check.
    # They survive a rerun unless a native edition later supplies the same (year, fuel).
    if os.path.exists(OUT_FUEL):
        with open(OUT_FUEL, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                key = (int(r["fiscal_year"]), r["fuel"])
                if "OCR REPAIRED" in r["source"] and key not in fuel_rows:
                    fuel_rows[key] = {"fiscal_year": int(r["fiscal_year"]),
                                      "fuel": r["fuel"], "toe": float(r["toe"]),
                                      "source": r["source"]}

    out = sorted(rows.values(), key=lambda r: (r["fiscal_year"], r["fuel"], r["system"]))
    os.makedirs(OUT_DIR, exist_ok=True)
    if write_or_check(OUT, ["fiscal_year", "fuel", "system", "gwh_net", "source"],
                      out, check):
        return 1

    fuel_out = sorted(fuel_rows.values(), key=lambda r: (r["fiscal_year"], r["fuel"]))
    if fuel_out:
        if write_or_check(OUT_FUEL, ["fiscal_year", "fuel", "toe", "source"],
                          fuel_out, check):
            return 1
    if check:
        print("the generation and fuel tables reproduce from the held document.")
        return 0

    yrs = sorted({r["fiscal_year"] for r in out})
    print("\nwrote %s" % os.path.relpath(OUT, os.path.dirname(DATA)))
    print("  %d rows | FY%d-FY%d | fuels %s" % (len(out), min(yrs), max(yrs), ", ".join(FUELS)))
    print("\n  reconciliation against the report's own Total Thermal Generation:")
    bad = 0
    for ed, y, printed, got in checks:
        ok = abs(printed - got) < 1.0
        bad += 0 if ok else 1
        print("    SIR %s FY%d  printed %10.2f  summed %10.2f  %s"
              % (ed, y, printed, got, "OK" if ok else "MISMATCH"))
    print("  %d of %d year-checks reconcile" % (len(checks) - bad, len(checks)))
    if fuel_out:
        fy = sorted({r["fiscal_year"] for r in fuel_out})
        print("\nwrote %s" % os.path.relpath(OUT_FUEL, os.path.dirname(DATA)))
        print("  %d rows | FY%d-FY%d | TOE by fuel" % (len(fuel_out), min(fy), max(fy)))
        fbad = 0
        for ed, y, printed, got in fuel_checks:
            ok = abs(printed - got) < 1.0
            fbad += 0 if ok else 1
            print("    SIR %s FY%d  printed %12.0f  summed %12.0f  %s"
                  % (ed, y, printed, got, "OK" if ok else "MISMATCH"))
        print("  %d of %d fuel-year checks reconcile" % (len(fuel_checks) - fbad, len(fuel_checks)))


if __name__ == "__main__":
    _src = next((a for a in sys.argv[1:] if not a.startswith("--")), DEFAULT_SRC)
    sys.exit(main(_src, check="--check" in sys.argv))
