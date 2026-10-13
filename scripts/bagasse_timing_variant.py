"""Price the bagasse timing lag: same-month vs +/-1-month against the sugar shape.

The eighteenth review's caveat on the rc30 crushing-season fix: PBS prints the
month sugar is REPORTED, and reporting may lag the crushing that produced the
bagasse slightly. The reference applies the sugar months as-is (lag 0); this
script publishes the one-month-earlier and one-month-later readings beside it so
the choice is priced, not assumed. Circular whole-month shifts, the
fertilizer_timing_variant pattern; annual controls are untouched by construction.

Usage:  python3 scripts/bagasse_timing_variant.py [--dry-run]
Writes: outputs/pakemis_bagasse_timing_variant.csv
"""

from pkinv.assets import asset_path
import csv
import io
import os
import sys

from pkinv.paths import DATA, OUTPUTS

SRC = asset_path(DATA, "activity", "monthly", "pbs_qim_month_item.csv")
OUT = asset_path(OUTPUTS, "pakemis_bagasse_timing_variant.csv")
LAGS = (0, 1, -1)


def sugar_shares():
    body = [l for l in open(SRC, encoding="utf-8") if not l.startswith("#")]
    rows = [r for r in csv.DictReader(io.StringIO("".join(body)))
            if r["item_no"] == "1-3"]
    by_year = {}
    for r in rows:
        by_year.setdefault(int(r["fiscal_year_start"]), []).append(
            (r["month"], float(r["quantity"])))
    out = {}
    for fy, months in by_year.items():
        months.sort()
        total = sum(q for _m, q in months)
        out[fy] = [(m, q / total if total else 0.0) for m, q in months]
    return out


def main():
    dry = "--dry-run" in sys.argv
    rows = []
    for fy, shares in sorted(sugar_shares().items()):
        base = [s for _m, s in shares]
        labels = [m for m, _s in shares]
        for lag in LAGS:
            shifted = base[-lag:] + base[:-lag] if lag else list(base)
            worst = max(abs(a - b) for a, b in zip(shifted, base)) * 100.0
            for month, ref, var in zip(labels, base, shifted):
                rows.append({
                    "profile_variant": "lag_%+d_month" % lag if lag else "lag_0_reference",
                    "fiscal_year_start": fy, "month": month,
                    "reference_share": round(ref, 6), "variant_share": round(var, 6),
                    "worst_month_gap_pp": round(worst, 3),
                    "assumption": ("sugar reported the month it was crushed" if lag == 0
                                   else "reporting lags crushing by one month" if lag == 1
                                   else "crushing lags reporting by one month"),
                })
    if dry:
        print("%d rows (dry run)" % len(rows))
        return
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print("bagasse timing variants -> %s (%d rows; the reference is lag 0 and the "
          "shifts are published, never applied)" % (OUT, len(rows)))


if __name__ == "__main__":
    main()
