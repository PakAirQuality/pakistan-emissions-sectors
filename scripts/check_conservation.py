#!/usr/bin/env python3
"""Conservation by gas across the release's grains, as one script a reader can run.

WHY. The release asserts that its grains agree - monthly with annual, atom with category,
category with the national total, placed with placed-plus-unallocated - but the assertions
were scattered over a dozen tests at the CO2e grain, and a gas that moved while the CO2e
total held (a CH4 to N2O relabel, say) would pass every one of them. This script recomputes
each identity BY GAS and prints the largest relative discrepancy against a stated
tolerance, then checks the notation keys separately: an absence must be typed (NE, IE, NA,
NO, C) and never a zero, and no typed absence may carry a mass.

Identities (configuration REF_2023_24 unless stated), each per (period, gas):
  I1  sum fact_monthly            == sum fact_annual
  I2  sum pakemis_atomic_annual   == sum fact_annual            (atom -> category)
  I3  sum fact_annual (all gases) == pakemis_national_series total per period (category -> national)
  I3b sum fact_annual, reference year == national_all_sectors national_total
  I4  sum fact_adm1_year, ALL spatial views   == sum fact_annual   (the views partition the mass)
  I5  sum fact_adm2_year + unallocated, per view == sum fact_adm1_year, per view
Notation:
  N1  completeness.csv notation keys are from the closed set {E, NE, IE, NA, NO, C} and never '0'
  N2  fact_adm2_year rows with an absence_reason carry no mass; rows with mass carry none

Exit 0 when every identity holds within tolerance, 1 otherwise. --json writes the table.
"""
import argparse
import collections
import csv
import io
import json
import os
import sys
from decimal import Decimal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "outputs")
SEM = os.path.join(OUT, "semantic")
CONFIG = "S_TAN"
REL_TOL = Decimal("1e-6")
NOTATION_KEYS = {"NE", "IE", "NA", "NO", "C", "E"}  # E = estimated, the project's positive key


def rows(path):
    with io.open(path, encoding="utf-8") as handle:
        return list(csv.DictReader(line for line in handle if not line.startswith("#")))


def agg(table, key, value="co2e_Mt_AR5", where=None):
    out = collections.defaultdict(Decimal)
    for r in table:
        if where and not where(r):
            continue
        raw = (r.get(value) or "").strip()
        if raw and raw not in NOTATION_KEYS:
            out[key(r)] += Decimal(raw)
    return out


def compare(name, left, right, results, tol=REL_TOL):
    keys = set(left) | set(right)
    worst = Decimal(0)
    worst_key = None
    for k in sorted(keys):
        a, b = left.get(k, Decimal(0)), right.get(k, Decimal(0))
        scale = max(abs(a), abs(b), Decimal("1e-12"))
        rel = abs(a - b) / scale
        if rel > worst:
            worst, worst_key = rel, k
    ok = worst <= tol
    results.append({"identity": name, "cells": len(keys), "worst_relative": float(worst),
                    "worst_cell": "" if worst_key is None else "|".join(map(str, worst_key)),
                    "tolerance": float(tol), "holds": ok})
    return ok


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", help="write the result table here")
    ap.add_argument("--tolerance", type=Decimal, default=REL_TOL,
                    help="relative tolerance for the mass identities (default 1e-6); "
                         "the suite's positive control runs with 0")
    args = ap.parse_args(argv)
    tol = args.tolerance
    results = []
    ok = True

    annual = rows(os.path.join(SEM, "fact_annual.csv"))
    ref = lambda r: r["configuration_id"] == CONFIG
    by_pg = lambda r: (r["period_id"], r["gas"])
    a_pg = agg(annual, by_pg, where=ref)

    monthly = rows(os.path.join(SEM, "fact_monthly.csv"))
    ok &= compare("I1 monthly == annual, by gas", agg(monthly, by_pg, where=ref), a_pg, results, tol=tol)

    atomic = rows(os.path.join(OUT, "pakemis_atomic_annual.csv"))
    ok &= compare("I2 atoms == annual, by gas", agg(atomic, by_pg, where=ref), a_pg, results, tol=tol)

    series = rows(os.path.join(OUT, "pakemis_national_series.csv"))
    totals = {(r["period_label"],): Decimal(r["co2e_Mt_AR5"]) for r in series
              if r["row_kind"] in ("total", "national_total", "covered_total")}
    if not totals:
        totals = agg(series, lambda r: (r["period_label"],), where=lambda r: r["row_kind"] == "sector")
    a_p = agg(annual, lambda r: (r["period_id"],), where=ref)
    ok &= compare("I3 annual == national series total, by period", a_p, totals, results,
                  tol=Decimal("5e-6"))
    national = rows(os.path.join(OUT, "national_all_sectors.csv"))
    ref_total = {(r["period_label"],): Decimal(r["co2e_Mt_AR5"]) for r in national
                 if r["row_kind"] == "national_total"}
    ok &= compare("I3b annual == national_all_sectors total, reference year",
                  {k: v for k, v in a_p.items() if k in ref_total}, ref_total, results,
                  tol=Decimal("5e-6"))

    adm1 = rows(os.path.join(SEM, "fact_adm1_year.csv"))
    ok &= compare("I4 ADM1 (all views) == annual, by gas", agg(adm1, by_pg, where=ref), a_pg, results, tol=tol)

    adm2 = rows(os.path.join(SEM, "fact_adm2_year.csv"))
    by_pvg = lambda r: (r["period_id"], r["spatial_view"], r["gas"])
    placed = agg(adm2, by_pvg, where=ref)
    unalloc = rows(os.path.join(OUT, "pakemis_spatial_unallocated_by_year.csv"))
    for r in unalloc:
        raw = (r.get("co2e_Mt_AR5") or "").strip()
        if raw:
            placed[(r["period_id"], r["spatial_view"], r["gas"])] += Decimal(raw)
    ok &= compare("I5 ADM2 + unallocated == ADM1, by view and gas", placed,
                  agg(adm1, by_pvg, where=ref), results, tol=tol)

    comp = rows(os.path.join(OUT, "completeness.csv"))
    bad = [r for r in comp if r["notation_key"].strip()
           and r["notation_key"].strip() not in NOTATION_KEYS]
    zeros = [r for r in comp if r["notation_key"].strip() in ("0", "0.0")]
    results.append({"identity": "N1 completeness notation keys typed, never zero",
                    "cells": len(comp), "worst_relative": len(bad) + len(zeros),
                    "worst_cell": "; ".join("%s/%s=%r" % (r["code"], r["gas"], r["notation_key"])
                                            for r in (bad + zeros)[:5]),
                    "tolerance": 0, "holds": not bad and not zeros})
    ok &= not bad and not zeros

    typed_with_mass = [r for r in adm2 if r["absence_reason"].strip()
                       and (r["co2e_Mt_AR5"] or "").strip() not in ("", "0", "0.0")
                       and Decimal(r["co2e_Mt_AR5"]) != 0]
    results.append({"identity": "N2 typed absences carry no mass (fact_adm2_year)",
                    "cells": len(adm2), "worst_relative": len(typed_with_mass),
                    "worst_cell": "; ".join(r["result_row_id"] for r in typed_with_mass[:5]),
                    "tolerance": 0, "holds": not typed_with_mass})
    ok &= not typed_with_mass

    width = max(len(r["identity"]) for r in results)
    for r in results:
        print("%-*s  %6d cells  worst %-12.3e  %s%s" % (
            width, r["identity"], r["cells"], float(r["worst_relative"]),
            "HOLDS" if r["holds"] else "FAILS",
            ("  at " + r["worst_cell"]) if r["worst_cell"] and not r["holds"] else ""))
    if args.json:
        with io.open(args.json, "w", encoding="utf-8") as handle:
            json.dump(results, handle, indent=1)
    print("conservation: %s" % ("ALL HOLD" if ok else "FAILURES"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
