"""What proportional allocation would do to the power profile, shown rather than done.

THE ASSUMPTION THIS FILE DECLINES TO MAKE. NEPRA's panel says how much of each station's YEAR
came from each fuel. PBS says how much that station generated each MONTH. Neither says how much
of each MONTH came from each fuel, and the obvious way to bridge them is to assume a station's
fuel mix is constant within the year:

    G(p,f,m) = G(p,m) x E(p,f,y) / SUM_f E(p,f,y)

The baseline refuses that, and only labels a plant-year where one fuel is already 95 percent or
more of it. The reason is not caution in general, it is caution in a KNOWN DIRECTION. Pakistani
thermal plant swings to furnace oil at the summer demand peak and back to gas in winter, so a
constant within-year mix does not merely add noise: it takes a station's total-generation curve
- which peaks in summer - and prints it onto gas and furnace oil alike, manufacturing exactly
the seasonal signal the monthly product exists to measure, in exactly the months a reader would
look at. A profile that is wrong at random is weak evidence. A profile that is wrong the same
way every year is a finding that is not there.

SO THE ASSUMPTION IS PRICED INSTEAD. This writes, per subitem and fiscal year, the twelve
reference shares beside the twelve shares proportional allocation would give, the coverage
under each, and whether the variant would newly earn a shape at all. A reader who thinks the
constant-mix assumption is acceptable can see precisely what accepting it buys and costs.

WHAT THIS IS NOT. It is not a second run of the monthly product. One arithmetic path stays
load-bearing; a second full vintage of 108 months is a second vintage waiting to disagree with
the first, and nothing here is worth that. No row this writes reaches the published product,
the profile registry or the decomposition's gap.

Usage:  python3 scripts/power_profile_variant.py [--dry-run]
Writes: outputs/pakemis_power_profile_variant.csv
"""
import argparse
import collections
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pkinv.assets import asset_path
import ingest_pbs_generation as pbs  # noqa: E402
from pkinv.core.io import read_rows

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERIES = asset_path(ROOT, "data", "activity", "power", "generation_monthly.csv")
OUT = asset_path(ROOT, "outputs", "pakemis_power_profile_variant.csv")

VARIANT = "power_constant_within_year_fuel_mix"
FIELDS = ("profile_variant", "fiscal_year", "subitem", "month", "reference_share",
          "variant_share", "reference_coverage", "variant_coverage", "reference_class",
          "variant_class", "newly_shaped", "assumption")
ASSUMPTION = ("a station's fuel mix is constant within the year: its monthly generation is "
              "split between fuels in the same proportions as its annual total")


def _series():
    return read_rows(SERIES, comments=False)


def allocate():
    """({(year, subitem, month): GWh} reference, the same under the variant).

    The reference counts a plant's generation towards one subitem only where a source labels
    it. The variant additionally splits the plant-years the panel covers but the baseline
    left unassigned, in the annual proportions the panel states.
    """
    panel = pbs.panel_totals()
    alias = pbs.aliases()
    reference = collections.defaultdict(float)
    variant = collections.defaultdict(float)
    for row in _series():
        year, month, gwh = row["fiscal_year"], row["month"], float(row["gwh"])
        if row["fuel"]:
            subitem = next((s for s, group in pbs.FUEL_GROUPS if row["fuel"] in group), None)
            if subitem:
                reference[(year, subitem, month)] += gwh
                variant[(year, subitem, month)] += gwh
            continue
        names = alias.get(pbs._normalise(row["plant"]), [pbs._normalise(row["plant"])])
        merged = collections.defaultdict(float)
        for name in names:
            for subitem, value in panel.get((name, year), {}).items():
                merged[subitem] += value
        total = sum(merged.values())
        if total <= 0:
            continue
        for subitem, value in merged.items():
            variant[(year, subitem, month)] += gwh * value / total
    return reference, variant


def _grade(share):
    if share > pbs.COVERAGE_IMPOSSIBLE:
        return "TE4"
    if share >= pbs.COVERAGE_STRONG:
        return "TE2"
    if share >= pbs.COVERAGE_WEAK:
        return "TE3"
    return "TE4"


def build():
    reference, variant = allocate()
    controls = pbs.control_by_fuel()
    rows = []
    for start in range(pbs.FIRST_FY_START, pbs.LAST_FY_START + 1):
        year = "FY%d-%02d" % (start, (start + 1) % 100)
        months = sorted({m for (y, _s, m) in variant if y == year})
        if not months:
            continue
        for subitem, group in pbs.FUEL_GROUPS:
            control = sum(controls.get(start, {}).get(f, 0.0) for f in group)
            if not control:
                continue
            ref_total = sum(reference.get((year, subitem, m), 0.0) for m in months)
            var_total = sum(variant.get((year, subitem, m), 0.0) for m in months)
            ref_share, var_share = ref_total / control, var_total / control
            ref_class, var_class = _grade(ref_share), _grade(var_share)
            for month in months:
                rows.append({
                    "profile_variant": VARIANT, "fiscal_year": year, "subitem": subitem,
                    "month": month,
                    "reference_share": (round(reference.get((year, subitem, month), 0.0)
                                              / ref_total, 6) if ref_total else ""),
                    "variant_share": (round(variant.get((year, subitem, month), 0.0)
                                            / var_total, 6) if var_total else ""),
                    "reference_coverage": round(ref_share, 4),
                    "variant_coverage": round(var_share, 4),
                    "reference_class": ref_class, "variant_class": var_class,
                    "newly_shaped": ("yes" if ref_class == "TE4" and var_class != "TE4"
                                     else "no"),
                    "assumption": ASSUMPTION,
                })
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description="Price the constant-mix assumption.")
    parser.add_argument("--dry-run", action="store_true", help="report and write nothing")
    args = parser.parse_args(argv)

    rows = build()
    print("the power profile under a constant within-year fuel mix, which the baseline refuses")
    seen = set()
    for row in rows:
        key = (row["fiscal_year"], row["subitem"])
        if key in seen:
            continue
        seen.add(key)
        same = [r for r in rows if (r["fiscal_year"], r["subitem"]) == key
                and r["reference_share"] != "" and r["variant_share"] != ""]
        worst = max((abs(float(r["variant_share"]) - float(r["reference_share"]))
                     for r in same), default=0.0)
        print("  %-9s %-12s coverage %5.1f%% -> %5.1f%%  %s -> %s%s%s"
              % (row["fiscal_year"], row["subitem"], 100 * float(row["reference_coverage"]),
                 100 * float(row["variant_coverage"]), row["reference_class"],
                 row["variant_class"],
                 "  NEWLY SHAPED" if row["newly_shaped"] == "yes" else "",
                 ("  worst month moves %.1f pp" % (100 * worst)) if same else ""))
    gained = len({(r["fiscal_year"], r["subitem"]) for r in rows if r["newly_shaped"] == "yes"})
    print("\n  %d subitem-years would newly carry a shape under the assumption; none of them "
          "does, and this file is why that is a decision rather than an oversight." % gained)
    if args.dry_run:
        print("\n--dry-run: nothing written.")
        return 0
    with open(OUT, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print("\nwrote %s" % os.path.relpath(OUT, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
