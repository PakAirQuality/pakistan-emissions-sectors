"""What an application lag would do to the fertiliser profile, shown rather than done.

THE ASSUMPTION THIS FILE DECLINES TO MAKE. Offtake times the DEPOT: fertiliser leaving a
dealer, weeks before a field needs it - dealers stock ahead of sowing and farmers buy on
price and credit. The soil emits after APPLICATION, which nobody meters nationally. The
temptation is to shift the offtake shape forward a month or two and call that
application timing; the baseline refuses, keeps the offtake profile graded T2 for what
it observes (the commodity leaving the depot), and prices the refusal here instead: the
reference shares beside each lagged reading, with the agronomic calendar - when the
crops NEED the nitrogen - as the independent comparator neither is calibrated to.

WHAT THE LAGS ARE, AND ARE NOT. lag-0 is the applied profile. lag-1 and lag-2 shift the
twelve fiscal months circularly - July's offtake feeding August's soil, and so on - which
is the whole crude model an unobserved application date supports; a sub-monthly or
crop-specific lag would be an invented precision. These are CONFIGURATIONS in the
sixteenth review's sense: published, priced against the agronomic comparator, never
averaged with the reference and never entering a shipped product. Their grade, were one
ever applied, would be T3: a model of when soil received nitrogen, not a record.

Usage:  python3 scripts/fertilizer_timing_variant.py [--dry-run]
Writes: outputs/pakemis_fertilizer_timing_variant.csv
"""
import argparse
import csv
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.assets import asset_path

from pkinv.core import monthly as core_monthly  # noqa: E402
from pkinv.report import monthly_crosschecks  # noqa: E402
from pkinv.sectors.agriculture import nfdc_monthly  # noqa: E402

FY_START = 2023
OUT = asset_path(ROOT, "outputs", "pakemis_fertilizer_timing_variant.csv")
FIELDS = ("profile_variant", "fiscal_year", "month", "reference_share",
          "variant_share", "agronomic_share", "worst_gap_to_agronomy_pp",
          "assumption")
ASSUMPTION = ("soil receives nitrogen a fixed whole number of months after it leaves "
              "the depot, identically for every crop and province; the reference "
              "refuses this and stays on observed offtake")


def build(fy_start=FY_START):
    shares, _methods = nfdc_monthly.profile(fy_start)
    months = core_monthly.months_for(fy_start)
    agronomy = monthly_crosschecks.agronomic_profile(fy_start)
    rows = []
    for lag in (0, 1, 2):
        lagged = {months[(i + lag) % 12]: shares[months[i]] for i in range(12)}
        worst = max(abs(lagged[m] - agronomy.get(m, 0.0)) for m in months)
        for month in months:
            rows.append({
                "profile_variant": "fertilizer_application_lag%d" % lag,
                "fiscal_year": "FY%d-%02d" % (fy_start, (fy_start + 1) % 100),
                "month": month,
                "reference_share": round(shares[month], 6),
                "variant_share": round(lagged[month], 6),
                "agronomic_share": round(agronomy.get(month, 0.0), 6),
                "worst_gap_to_agronomy_pp": round(100 * worst, 2),
                "assumption": ASSUMPTION,
            })
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description="Price the application-lag assumption.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    rows = build()
    print("the fertiliser profile under whole-month application lags, which the "
          "baseline refuses")
    for lag in (0, 1, 2):
        row = next(r for r in rows
                   if r["profile_variant"].endswith(str(lag)))
        print("  lag-%d: worst month vs the agronomic calendar %.1f pp"
              % (lag, row["worst_gap_to_agronomy_pp"]))
    if args.dry_run:
        print("--dry-run: nothing written.")
        return 0
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print("wrote %s" % os.path.relpath(OUT, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
