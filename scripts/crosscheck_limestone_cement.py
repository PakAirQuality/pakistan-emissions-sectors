"""PBS limestone production against PBS QIM cement output, as shapes.

WHY THESE TWO. Limestone is cement's feedstock, and the two series reach PBS through two
different collection systems - the provincial mines departments for minerals, the large-scale
manufacturing survey for QIM. If cement's monthly shape is real, the quarry that feeds it
should move with it; if the two disagree badly, one of the collection systems is smoothing or
lagging and the cement profile's TE2 grade is standing on softer ground than it claims.

SHAPE ONLY, OVERLAPPING YEARS ONLY. Limestone goes to lime, aggregate and chemicals as well as
kilns, and quarry-to-kiln stockpiles decouple the months a little, so the magnitudes are
different quantities and only the seasonality is a question with an answer. Neither series
becomes a profile for the other: cement keeps its own QIM months.

Usage:  python3 scripts/crosscheck_limestone_cement.py
Writes: outputs/limestone_qim_cement_crosscheck.csv
"""
import csv
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.assets import asset_path

from pkinv.core import pbs_minerals, pbs_qim  # noqa: E402
from pkinv.paths import OUTPUTS  # noqa: E402

OUT = asset_path(OUTPUTS, "limestone_qim_cement_crosscheck.csv")

FIELDS = ("fiscal_year_start", "month", "limestone_share", "cement_share",
          "difference_pp", "compares", "flag")
NOTE = "shape only - limestone feeds lime and aggregate too, and stockpiles decouple months"

# A single month whose share exceeds this is a reporting anomaly in the SOURCE, not a
# seasonality signal. November 2016 carried 36.7% of FY2016-17's limestone in the defective
# parse of rc67 and carries 9.9% in the repaired one (the FATA cell, 8.6 times its own row
# median, printed in both held editions), while cement shows nothing of the kind. Flagged, never dropped -
# the reader decides, and the flag is what keeps the year's mean from being read as signal.
ANOMALY_SHARE = 0.25


def build():
    rows = []
    for fy_start in range(2015, 2024):
        if not (pbs_minerals.covers(pbs_minerals.LIMESTONE, fy_start)
                and pbs_qim.covers(pbs_qim.CEMENT, fy_start)):
            continue
        lime, _ = pbs_minerals.profile(pbs_minerals.LIMESTONE, fy_start)
        cement = pbs_qim.profile(pbs_qim.CEMENT, fy_start)
        for month in sorted(lime):
            rows.append({
                "fiscal_year_start": fy_start, "month": month,
                "limestone_share": round(lime[month], 6),
                "cement_share": round(cement[month], 6),
                "difference_pp": round(100 * (lime[month] - cement[month]), 4),
                "compares": NOTE,
                "flag": ("source-anomaly: limestone share %.1f%% of the year in one month"
                         % (100 * lime[month]) if lime[month] > ANOMALY_SHARE else ""),
            })
    return rows


def main():
    rows = build()
    if not rows:
        print("no overlapping limestone/cement years")
        return 1
    os.makedirs(OUTPUTS, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as handle:
        handle.write("# PBS limestone production shape against PBS QIM cement output shape, "
                     "per overlapping fiscal year.\n")
        handle.write("# Two series from one publisher through two collection systems. SHAPE "
                     "ONLY; neither becomes a profile for the other.\n")
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    years = sorted({r["fiscal_year_start"] for r in rows})
    mean = sum(abs(r["difference_pp"]) for r in rows) / len(rows)
    worst = max(abs(r["difference_pp"]) for r in rows)
    print("limestone/cement cross-check -> %s" % os.path.relpath(OUT, ROOT))
    print("  %d months over %d overlapping years (%s)"
          % (len(rows), len(years), ", ".join("FY%d-%02d" % (y, (y + 1) % 100)
                                              for y in years)))
    flagged = [r for r in rows if r["flag"]]
    clean = [abs(r["difference_pp"]) for r in rows if not r["flag"]]
    print("  mean absolute share difference %.2f pp, worst %.2f pp" % (mean, worst))
    print("  %d month(s) flagged as source anomalies; excluding them: mean %.2f, worst %.2f"
          % (len(flagged), sum(clean) / len(clean), max(clean)))
    return 0


if __name__ == "__main__":
    import sys as _sys
    if "--check" in _sys.argv[1:]:
        # re-derive into a temporary directory and compare; nothing in the tree is written
        from pkinv.core.checkmode import compare_only
        _sys.exit(compare_only(globals(), ("OUT",), main))
    sys.exit(main())
