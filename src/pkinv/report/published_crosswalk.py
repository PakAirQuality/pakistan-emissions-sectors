"""Publish the classification scheme and its CRT crosswalk, with the data beside the claim.

The registry itself is data/shared/lookups/category_crosswalk.csv, which is an INPUT. This
publishes it as a release product and attaches what the release actually did with each rule:
how many live components resolved through it and what they sum to in the reference year. A
crosswalk nobody can check against the data is a table of assertions; the counts are what make
a reader able to see that the two categories which split really did split, and that the rows
marked unmapped carry no mass because nothing resolves through them.

The CRT column travels because the comparison a reader most often needs is against Pakistan's
own reporting, which is CRT - and because the submission's own codes are shifted against the
2006 Guidelines in two places (it books urea at 3.C.2, which Table 8.2 uses for liming), so a
join on the code string is wrong in a way that looks right.
"""
import argparse

from pkinv.assets import asset_path
from pkinv.core.io import read_rows, write_or_check
from pkinv.paths import OUTPUTS
from pkinv.report import category_crosswalk

OUT = asset_path(OUTPUTS, "pakemis_category_crosswalk.csv")
REFERENCE = "FY2023-24"

FIELDS = ("scheme_version", "ipcc2006_code", "ipcc2006_name", "crt_code", "crt_name",
          "module", "engine_category", "subitem_prefix", "gas", "applies_to", "tier",
          "basis", "live_components", "reference_co2e_Mt_AR5", "note")

BANNER = """\
# THE CLASSIFICATION SCHEME THIS RELEASE IS CODED IN, AND THE CROSSWALK TO THE UNFCCC CRT.
#
# IPCC 2006 is canonical, from Volume 1 Chapter 8 Table 8.2. Until 2026-10-06 the shipped
# `ipcc_code` column mixed two schemes - CRT in sector 3, IPCC 2006 in sector 4 - which an
# external reviewer found in a printed table. Renaming the column would not have been enough:
# the exports carried the mixed codes, so the migration went through the registry and every
# product derived from it.
#
# THE GRAIN IS THE COMPONENT. Two CRT categories split when expressed in IPCC 2006, along a
# line the engines already compute: manure management's indirect N2O leaves the livestock
# block for 3.C.6, and agricultural soils divides into direct 3.C.4 and indirect 3.C.5. So a
# rule matches on (engine_category, subitem_prefix, gas) and the most specific prefix wins.
#
# live_components and reference_co2e_Mt_AR5 are what resolved through each rule in the
# reference year, read from outputs/pakemis_atomic_annual.csv. They are the check a reader can
# run: the two split pairs must sum to the single CRT category they replace, and a row marked
# unmapped must carry nothing.
#
# WHAT IS NOT MAPPED. CRT 3.I and 3.J have no IPCC 2006 counterpart and none is invented -
# 3.C.8 "Other" is a different scope. CRT 4.E Settlements and 4.F Other land arrive as one
# PakEmis row facing two codes and are declared needs_separation rather than apportioned.
#
# Energy (1.x) and IPPU (2.x) carry the same codes in both schemes and are not enumerated;
# tests/test_category_crosswalk.py asserts the live code set against this registry instead.
"""


def build():
    atoms = [r for r in read_rows(asset_path(OUTPUTS, "pakemis_atomic_annual.csv"),
                                  comments=True)
             if r["period_id"] == REFERENCE]
    counts, mass = {}, {}
    for a in atoms:
        try:
            _, rule = category_crosswalk.resolve(a["category"], a["subitem"], a["gas"])
        except KeyError:
            continue
        key = (rule["engine_category"], rule["subitem_prefix"], rule["gas"])
        counts[key] = counts.get(key, 0) + 1
        try:
            mass[key] = mass.get(key, 0.0) + float(a["co2e_Mt_AR5"])
        except (TypeError, ValueError):
            pass

    rows = []
    for r in category_crosswalk.rules():
        key = (r["engine_category"], r["subitem_prefix"], r["gas"])
        row = {k: r.get(k, "") for k in FIELDS if k in r}
        row["live_components"] = str(counts.get(key, 0)) if r["applies_to"] == "component" else ""
        row["reference_co2e_Mt_AR5"] = (("%.6f" % mass[key]) if key in mass else "")
        rows.append({k: row.get(k, "") for k in FIELDS})
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="verify the shipped file matches a fresh build; write nothing")
    args = ap.parse_args(argv)
    rows = build()
    status = write_or_check(OUT, FIELDS, rows, check=args.check, banner=BANNER.splitlines())
    if args.check:
        return status
    live = sum(1 for r in rows if r["live_components"] not in ("", "0"))
    print("Category crosswalk -> %s (%d rules, %d resolving live components)"
          % (OUT, len(rows), live))
    for r in rows:
        if r["tier"] in ("split", "reclassified") or r["live_components"] not in ("", "0"):
            print("  %-9s %-28s %-14s %s comps  %s Mt"
                  % (r["ipcc2006_code"], r["engine_category"][:28], r["tier"],
                     r["live_components"] or "-", r["reference_co2e_Mt_AR5"] or "-"))


if __name__ == "__main__":
    raise SystemExit(main())
