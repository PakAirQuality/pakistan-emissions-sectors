"""Air-pollutant co-emissions over 1990-2024, on the same historical activity as the GHG series.

Mirrors src/pkinv/inventory/timeseries.py: the emission factors are held constant and only the activity
data varies, so the trajectory reflects herd growth, fertiliser use and crop production rather than
moving factors. Years 1990-2023 are rebuilt from data/activity/historical (FAOSTAT); 2024 is the
PBS-census anchor, exactly as in the GHG series.

Known discontinuity at the anchor (shared with the GHG series, disclosed in the paper): the historical
crop file carries no cotton, so burning-derived pollutants for 1990-2023 sit a few per cent below the
2024 anchor, which does include cotton residue.

Usage:  python3 -m pkinv.sectors.agriculture.air_timeseries
Writes: outputs/air_pollutants_timeseries_1990_2024.csv, outputs/air_trend_chart.png
"""

from pkinv.assets import asset_path
import collections
import csv
import os
import sys


from pkinv.sectors.agriculture import air_pollutants as ap  # noqa: E402
from pkinv.sectors.agriculture import timeseries as ts  # noqa: E402
from pkinv.sectors.agriculture.ef_library import InventoryData  # noqa: E402

from pkinv.paths import ROOT

OUT = asset_path(ROOT, "outputs")
CSV_PATH = asset_path(OUT, "air_pollutants_timeseries_1990_2024.csv")
PNG_PATH = asset_path(OUT, "air_trend_chart.png")
POLLUTANTS = ["NH3", "NOx", "CO", "PM2.5", "NMVOC", "BC", "SO2"]


def build_series():
    """{year: {pollutant: {category: kt}}} for every year with historical activity, plus the anchor."""
    live, crops, nitro = ts._load_history()
    years = [y for y in range(ts.START, ts.ANCHOR) if y in live and y in crops and y in nitro]
    series = {}

    data = InventoryData()          # reused across years; _apply_year overwrites the activity fields
    for y in years:
        ts._apply_year(data, live[y], crops[y], nitro[y])
        series[y] = _aggregate(ap.compute(data))

    series[ts.ANCHOR] = _aggregate(ap.compute(InventoryData()))   # census anchor
    return series, years + [ts.ANCHOR]


def _aggregate(rows):
    out = collections.defaultdict(lambda: collections.defaultdict(float))
    for r in rows:
        out[r["pollutant"]][r["category"]] += r["emissions_kt"]
    return {p: dict(c) for p, c in out.items()}


def _write_csv(series, years):
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["year", "pollutant", "category", "emissions_kt"])
        for y in years:
            for poll in POLLUTANTS:
                cats = series[y].get(poll, {})
                for cat, v in sorted(cats.items()):
                    w.writerow([y, poll, cat, round(v, 4)])
                w.writerow([y, poll, "TOTAL", round(sum(cats.values()), 4)])


def _write_chart(series, years):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:                                  # plotting is optional
        print("  (skipped air trend chart: %s)" % e)
        return
    fig, ax = plt.subplots(figsize=(9, 5.5))
    for poll in POLLUTANTS:
        vals = [sum(series[y].get(poll, {}).values()) for y in years]
        ax.plot(years, vals, linewidth=1.6, label=poll)
    ax.set_yscale("log")
    ax.set_xlabel("Year")
    ax.set_ylabel("kt yr$^{-1}$ (log scale)")
    ax.set_title("Pakistan agricultural air-pollutant co-emissions 1990-2024")
    ax.axvline(ts.ANCHOR, color="#555", ls=":", lw=1.2)
    ax.text(ts.ANCHOR, ax.get_ylim()[0] * 1.5, " PBS-census anchor", rotation=90,
            va="bottom", ha="right", fontsize=7, color="#555")
    ax.legend(fontsize=8, ncol=4, frameon=False)
    ax.grid(True, alpha=0.3, which="both")
    fig.tight_layout()
    fig.savefig(PNG_PATH, dpi=130)
    plt.close(fig)


def main():
    os.makedirs(OUT, exist_ok=True)
    series, years = build_series()
    _write_csv(series, years)
    _write_chart(series, years)
    y0, y1 = years[0], years[-1]
    print("Air-pollutant time series %d-%d -> air_pollutants_timeseries_1990_2024.csv" % (y0, y1))
    for poll in POLLUTANTS:
        a = sum(series[y0].get(poll, {}).values())
        b = sum(series[y1].get(poll, {}).values())
        print("  %-6s %8.1f -> %8.1f kt  (x%.1f)" % (poll, a, b, (b / a) if a else 0.0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
