#!/usr/bin/env python3
"""WAVE 1b OF THE INDUSTRIAL BOUNDARY PROGRAM: an INDEPENDENT 1.A.2 industrial
combustion control total from the UN Statistics Division energy balances - the
public stand-in for the purchase-only HDIP energy yearbook (roadmap step 1).

UNSD publishes Pakistan's "Manufacturing, const., mining" FINAL ENERGY by fuel in
Terajoules; this applies the release's OWN IPCC 2006 CO2-per-TJ factors
(data/emission_factors.csv, full provenance there) to give a second external
benchmark beside EDGAR's single one in the boundary ledger's diagnostic lane.

BOUNDARY, STATED NOT HIDDEN. This is a benchmark, not a like-for-like:
  * UNSD "manufacturing" EXCLUDES industry's own captive generation (the engine
    computes that in the power module, 1.A.2 at 5.55 Mt) and purchased grid
    electricity (Scope 2, out of scope both sides);
  * it INCLUDES non-metallic-minerals coal - Pakistan's cement kiln fuel, which
    the engine SCREENS (11.99-15.65 Mt), so UNSD's coal line is expected to
    exceed the engine's priced combustion by roughly that screening;
  * biofuels and waste are a BIOGENIC memo, never in the fossil total.
The coal and oil emission factors are the documented IPCC defaults for the fuel
the engine already assigns (bituminous coal; residual fuel oil); a different coal
rank (lignite) or petcoke would shift the coal line, which is why this is a
bracket, not a point.

Reads:  data/raw/unsd/energy_balances/unsd_energy_balances_<edition>_countries_M_Q.pdf
        data/emission_factors.csv (the release's own IPCC 2006 CO2 factors)
Writes: outputs/unsd_industry_combustion_control.csv
"""
import csv
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from pkinv.assets import asset_path
from pkinv.paths import OUTPUTS  # noqa: E402

ROOT = os.path.dirname(OUTPUTS)
RAW = asset_path(ROOT, "data", "raw", "unsd", "energy_balances")
OUT = asset_path(OUTPUTS, "unsd_industry_combustion_control.csv")
EF_CSV = asset_path(ROOT, "data", "emission_factors.csv")

# The Manufacturing row's numeric columns, in printed order. UNSD prints ".." for
# nil; adjacent columns can merge under -layout, so we read the row's numbers
# left-to-right into these named slots.
COLUMNS = ["primary_coal", "coal_products", "primary_oil", "oil_products",
           "natural_gas", "biofuels_waste", "nuclear", "electricity", "heat",
           "total_energy", "renewables"]

# fuel column -> (emission_factors.csv key, in the fossil total?)
FUEL_EF = {
    "primary_coal":   ("pow_co2_coal_bit", True),   # non-metallic-minerals coal = cement kiln
    "coal_products":  ("pow_co2_coal_bit", True),
    "oil_products":   ("pow_co2_rfo", True),         # industry's furnace oil
    "natural_gas":    ("pow_co2_gas", True),
    "biofuels_waste": ("pow_co2_bagasse", False),    # BIOGENIC memo, never in total
}

FIELDS = ("year", "fuel", "tj", "co2_ef_kg_per_tj", "ef_source", "co2_Mt",
          "in_total", "source_edition", "note")


def load_efs():
    efs = {}
    with open(EF_CSV, encoding="utf-8") as h:
        for r in csv.DictReader(l for l in h if not l.startswith("#")):
            efs[r["ef_id"]] = (float(r["value"]), "%s (%s)" % (r["source"], r["ef_id"]))
    return efs


def numbers(line):
    """The row's numbers, ".." read as a held slot so columns stay aligned."""
    toks = re.findall(r"\*?-?\d[\d,]*\.?\d*|\.\.", line)
    out = []
    for t in toks:
        out.append(None if t == ".." else float(t.lstrip("*").replace(",", "")))
    return out


def parse_edition(path):
    txt = subprocess.run(["pdftotext", "-layout", path, "-"], capture_output=True,
                         text=True, check=True).stdout
    lines = txt.splitlines()
    blocks = [i for i, l in enumerate(lines) if l.strip() == "Pakistan"]
    out = []
    for start in blocks:
        window = lines[start:start + 60]
        year = None
        for l in window:
            m = re.match(r"\s*(20\d{2})\s*$", l)
            if m:
                year = int(m.group(1))
                break
        man = next((l for l in window if l.strip().startswith("Manufacturing, const")), None)
        if year is None or man is None:
            continue
        nums = numbers(man)
        if len(nums) < len(COLUMNS):        # a merged/short row: skip, do not guess
            continue
        row = dict(zip(COLUMNS, nums[:len(COLUMNS)]))
        out.append((year, row))
    return out


def main():
    efs = load_efs()
    seen = {}   # year -> (row, edition); later editions revise earlier years
    for name in sorted(os.listdir(RAW)):
        if not name.endswith(".pdf"):
            continue
        for year, row in parse_edition(asset_path(RAW, name)):
            seen[year] = (row, name)   # keep the latest edition's value for each year

    out_rows = []
    for year in sorted(seen):
        row, edition = seen[year]
        fossil = 0.0
        for fuel, (ef_key, in_total) in FUEL_EF.items():
            tj = row.get(fuel)
            if tj is None:
                continue
            ef, ef_src = efs[ef_key]
            co2 = tj * ef / 1e9
            if in_total:
                fossil += co2
            out_rows.append({"year": year, "fuel": fuel, "tj": "%g" % tj,
                             "co2_ef_kg_per_tj": "%g" % ef, "ef_source": ef_src,
                             "co2_Mt": "%.4f" % co2,
                             "in_total": "yes" if in_total else "biogenic_memo",
                             "source_edition": asset_path("data/raw/unsd/energy_balances", edition),
                             "note": ""})
        out_rows.append({"year": year, "fuel": "FOSSIL_COMBUSTION_TOTAL", "tj": "",
                         "co2_ef_kg_per_tj": "", "ef_source": "",
                         "co2_Mt": "%.4f" % fossil, "in_total": "total",
                         "source_edition": asset_path("data/raw/unsd/energy_balances", edition),
                         "note": "coal + coal products + oil products + natural gas; "
                                 "biofuels excluded (biogenic); a BENCHMARK for 1.A.2, "
                                 "not a like-for-like (UNSD manufacturing excludes captive "
                                 "generation and includes cement kiln coal)"})
    with open(OUT, "w", newline="", encoding="utf-8") as h:
        h.write("# INDEPENDENT 1.A.2 industrial-combustion control total from the UNSD\n"
                "# energy balances (the public stand-in for HDIP), the release's own IPCC\n"
                "# 2006 CO2 factors applied to Pakistan's Manufacturing/const/mining fuel\n"
                "# use. A BENCHMARK beside EDGAR, boundary stated: UNSD excludes captive\n"
                "# generation, includes cement kiln coal, and biofuels are a biogenic memo.\n")
        w = csv.DictWriter(h, fieldnames=list(FIELDS), lineterminator="\n")
        w.writeheader()
        w.writerows(out_rows)
    totals = {r["year"]: r["co2_Mt"] for r in out_rows if r["fuel"] == "FOSSIL_COMBUSTION_TOTAL"}
    print("UNSD industrial-combustion control -> %s (%d years: %s)"
          % (os.path.relpath(OUT), len(totals),
             ", ".join("%s=%s" % (y, totals[y]) for y in sorted(totals))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
