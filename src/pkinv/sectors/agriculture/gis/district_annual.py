"""District x year annual emission panel, 1990-2024 (ADM2), reconciled to the national series.

(Distinct from district_timeseries.py, which computes intra-year district *timing* weights. This
module builds the annual multi-year panel.)

District spatial shares (province split via province_shares.csv, then the within-province dasymetric
proxy split in district_downscale.py) are held constant across years -- there is no multi-year
district activity survey. Under that constant-share assumption the district x year panel is the
audited 2024 district pattern (outputs/district_totals_2024.csv) rescaled, per category, to each
year's national control total from the 1990-2024 series (outputs/timeseries_1990_2024.csv):

    E_{d,cat,year} = E_{d,cat,2024} * ( national_{cat,year} / Sigma_d E_{d,cat,2024} )

so Sigma_d E_{d,cat,year} == national_{cat,year} exactly for every category and year (the
reconciliation invariant, extended over time). Holding shares constant is a first-order
simplification -- district magnitudes move with the national trajectory, not with any observed
change in where the activity sits (a documented limitation).

Usage:  python3 -m pkinv.sectors.agriculture.gis.district_annual
Writes: outputs/districts/district_totals_by_year.csv, outputs/districts/district_trajectory.png
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import collections
import csv
import os

from pkinv.paths import ROOT

BASE_CSV = asset_path(ROOT, "outputs", "district_totals_2024.csv")
TS_CSV = asset_path(ROOT, "outputs", "timeseries_1990_2024.csv")
OUT_DIR = asset_path(ROOT, "outputs", "districts")
OUT_CSV = asset_path(OUT_DIR, "district_totals_by_year.csv")
OUT_PNG = asset_path(OUT_DIR, "district_trajectory.png")
TOL = 1e-6

# EVERY ROW BUT ONE YEAR'S IS A BACKCAST, AND THE FILE NOW SAYS SO. The docstring above
# has always been honest that district shares are held at the audited 2024 pattern and
# rescaled to each year's national total, but the CSV carried no column saying it: a
# reader opening the file saw year, district, category, value and could reasonably take a
# 1990 row for a 1990 observation. It is not one. Nothing in this panel observes where
# emissions sat in any year other than the anchor; the district geography is one year's
# pattern projected backwards, and only the national trajectory is evidenced per year.
ANCHOR_YEAR = 2024
ANCHOR_NOTE = ("the audited district pattern for the reference year, from "
               "outputs/district_totals_2024.csv")
BACKCAST_NOTE = ("district shares held at the 2024 audited pattern and rescaled to this "
                 "year's national control total - the national trajectory is evidenced "
                 "per year, the district split is not observed for any year but 2024")


def _base():
    """2024 district panel: list of (district, province, category, value)."""
    return [(r["district"], r["province"], r["category"], float(r["co2e_Mt_AR5"]))
            for r in _activity_rows(BASE_CSV, comments=False)]


def _national_series():
    """{year: {category: co2e_Mt_AR5}} from the 1990-2024 series (excludes the TOTAL row)."""
    ns = collections.defaultdict(dict)
    for r in _activity_rows(TS_CSV, comments=False):
        if r["category"] == "TOTAL":
            continue
        ns[int(r["year"])][r["category"]] = float(r["co2e_Mt_AR5"])
    return ns


def build_panel():
    """Return (rows, years, national) where rows = list of dicts year/district/province/category/value,
    reconciled so Sigma_districts == national per (category, year)."""
    base = _base()
    national = _national_series()
    years = sorted(national)
    base_cat = collections.defaultdict(float)          # Sigma_d 2024 value, per category
    for _, _, cat, v in base:
        base_cat[cat] += v
    rows = []
    for year in years:
        for district, province, cat, v in base:
            nat = national[year].get(cat)
            if nat is None or base_cat[cat] <= 0:
                continue
            scale = nat / base_cat[cat]
            rows.append({"year": year, "district": district, "province": province,
                         "category": cat, "co2e_Mt_AR5": v * scale})
    return rows, years, national


def check(rows, national):
    """Worst |Sigma_districts - national| over all (category, year)."""
    agg = collections.defaultdict(float)
    for r in rows:
        agg[(r["year"], r["category"])] += r["co2e_Mt_AR5"]
    worst = 0.0
    for (year, cat), got in agg.items():
        worst = max(worst, abs(got - national[year][cat]))
    return worst


def _plot(rows, years):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:                              # plotting is optional
        print("  (skipped trajectory plot: %s)" % e)
        return
    tot = collections.defaultdict(lambda: collections.defaultdict(float))  # district -> year -> total
    for r in rows:
        if r["province"] == "Other":
            continue
        tot[r["district"]][r["year"]] += r["co2e_Mt_AR5"]
    top = sorted(tot, key=lambda d: -tot[d][years[-1]])[:8]
    fig, ax = plt.subplots(figsize=(8, 5))
    for d in top:
        ax.plot(years, [tot[d][y] for y in years], linewidth=1.6, label=d.split(" District")[0])
    ax.set_xlabel("Year")
    ax.set_ylabel("District agricultural emissions (Mt CO$_2$e, AR5)")
    ax.set_title("Top-8 districts by 2024 emissions: 1990-2024 trajectory")
    ax.legend(fontsize=8, ncol=2, frameon=False)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT_PNG, dpi=150)
    plt.close(fig)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    rows, years, national = build_panel()
    worst = check(rows, national)
    assert worst < TOL, "district x year reconciliation failed: worst residual %.2e Mt" % worst

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["year", "district", "province", "category", "co2e_Mt_AR5",
                    "spatial_basis", "note"])
        for r in rows:
            backcast = r["year"] != ANCHOR_YEAR
            w.writerow([r["year"], r["district"], r["province"], r["category"],
                        round(r["co2e_Mt_AR5"], 5),
                        "reference_shape_backcast" if backcast
                        else "reference_year_pattern",
                        BACKCAST_NOTE if backcast else ANCHOR_NOTE])
    _plot(rows, years)

    # national trajectory endpoints + leading districts (final year)
    nat_year = {y: sum(national[y].values()) for y in years}
    dtot = collections.defaultdict(float)
    for r in rows:
        if r["year"] == years[-1] and r["province"] != "Other":
            dtot[r["district"]] += r["co2e_Mt_AR5"]
    top = sorted(dtot.items(), key=lambda kv: -kv[1])[:5]
    ndist = len({r["district"] for r in rows})
    print("District x year panel: %d districts x %d categories x %d years -> district_totals_by_year.csv"
          % (ndist, len({r["category"] for r in rows}), len(years)))
    print("  reconciliation: worst Sigma_districts - national residual %.2e Mt (all years/categories)" % worst)
    print("  national total: %.1f Mt (%d) -> %.1f Mt (%d)"
          % (nat_year[years[0]], years[0], nat_year[years[-1]], years[-1]))
    print("  top %d districts (Mt CO2e): " % len(top)
          + ", ".join("%s %.1f" % (d.split(" District")[0], v) for d, v in top))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
