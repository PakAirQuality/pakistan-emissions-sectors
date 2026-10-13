"""Two independent monthly profiles, each checked against the one this inventory publishes.

A seasonal profile cannot be validated against the truth - nobody meters when Pakistan's
nitrogen is taken up or when its furnace oil is burned. What can be done is to build the same
profile a second way, from evidence the first one did not use, and publish the disagreement.
Neither check can change the annual total, so a large disagreement is not an inventory error;
it is a statement about how much the monthly dimension should be trusted, and it belongs in
the paper rather than in a footnote saying the profiles are plausible.

CHECK 1: DOES FERTILISER MOVE WHEN AGRONOMY SAYS IT SHOULD BE APPLIED? The layer spreads
synthetic-fertiliser nitrogen on NFDC's Annex-7 offtake - when urea LEFT THE DEPOT. The
agronomic alternative is data/fertilizer_calendar.csv: each crop's share of national nitrogen
times its own application calendar - when agronomy says the crop NEEDS it. The two differ for
a real reason and not only through error: farmers buy on price, credit and availability, and a
Rabi sowing is preceded by weeks of dealer stocking. Whichever is further from uptake, the gap
between them is the honest width of the monthly claim.

CHECK 2: DO THE RECOVERED MONTHS ADD UP TO WHAT THE ANNUAL EDITION PRINTS? Four modules
recover months by differencing OCAC's cumulative year-to-date columns. Summing them back to
the year is not circular, because the ANNUAL edition is a separate publication issued later:
it revises, and the monthly editions it revises are the ones this inventory's shapes are built
from. Any gap is a vintage disagreement inside a single publisher's own numbers, and it bounds
how much of the seasonal shape is a fact about fuel rather than about editions. Note what this
does NOT threaten: every module normalises its profile, so a class whose monthly total is 2
percent light still distributes its own annual control exactly.

And the answer is regime-dependent in a way worth stating rather than averaging away. For
FY2023-24 every class agrees to the tonne - because OCAC's annual edition reprints the June
cumulative column unchanged, so that comparison confirms the ingest and the arithmetic and has
no power at all to detect revision. FY2021-22 is where the check bites: its months are twelve
separately printed direct editions, reassembling them into a year is a real test, and they
come back within 0.34 percent.

Usage:  python3 -m pkinv.report.monthly_crosschecks
Writes: outputs/monthly_crosschecks.csv
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import csv
import os

from pkinv.core import monthly as core_monthly
from pkinv.core import ocac_monthly
from pkinv.paths import DATA, OUTPUTS

FY_START = 2023
OUT = asset_path(OUTPUTS, "monthly_crosschecks.csv")
CALENDAR = asset_path(DATA, "fertilizer_calendar.csv")

MONTH_COLUMNS = ("jan", "feb", "mar", "apr", "may", "jun",
                 "jul", "aug", "sep", "oct", "nov", "dec")

def agronomic_profile(fy_start=FY_START):
    """{month: share} - national nitrogen demand from the crop calendars.

    Each crop's calendar is a set of CALENDAR-month shares repeated every year, so the
    fiscal-year key is assembled by taking July-December from the opening year and
    January-June from the closing one. Weighted by each crop's share of national N.
    """
    weights = {m: 0.0 for m in core_monthly.months_for(fy_start)}
    for row in _activity_rows(CALENDAR, comments=False):
        n_share = float(row["n_share"])
        for i, column in enumerate(MONTH_COLUMNS, start=1):
            year = fy_start if i >= 7 else fy_start + 1
            weights["%d%02d" % (year, i)] += n_share * float(row[column] or 0.0)
    return core_monthly.normalise(weights)


def fertiliser_check(fy_start=FY_START):
    from pkinv.sectors.agriculture import monthly as agriculture_monthly
    """Rows comparing the published offtake profile against the agronomic one.

    THE published profile - the same selection the monthly layer makes
    (published_nitrogen_profile). This check called the Annex-7 helper directly
    until rc28, so it compared agronomy against a profile the layer had stopped
    using two releases earlier, and its borrowed-month T3 labels contradicted
    the shipped no-borrowing product - the seventeenth review's first defect."""
    offtake, method, basis = agriculture_monthly.published_nitrogen_profile(fy_start)
    agronomic = agronomic_profile(fy_start)
    rows = []
    for m in core_monthly.months_for(fy_start):
        m_method = method[m] if isinstance(method, dict) else method
        rows.append({"check": "fertiliser", "month": m,
                     "published_share": offtake[m], "alternative_share": agronomic[m],
                     "difference": offtake[m] - agronomic[m],
                     "published_basis": "%s (%s)" % (basis.split(";")[0], m_method),
                     "alternative_basis": "crop calendars weighted by N share (T3)"})
    return rows


ANNUAL = asset_path(DATA, "activity", "transport", "ocac_sectoral_annual.csv")

# The classes whose monthly shapes the four OCAC-driven modules actually consume.
CONSUMED = (
    ("road petrol", ocac_monthly.ROAD, ocac_monthly.PETROL),
    ("road diesel", ocac_monthly.ROAD, ocac_monthly.DIESEL),
    ("railways diesel", ocac_monthly.RAILWAYS, ocac_monthly.DIESEL),
    ("power furnace oil", ocac_monthly.TOTAL_POWER, ocac_monthly.FURNACE_OIL),
    ("industry diesel", ocac_monthly.TOTAL_INDUSTRY, ocac_monthly.DIESEL),
    ("aviation jet fuel", "Domestic Bunkers", ocac_monthly.JET),
)




def burning_check(fy_start=FY_START):
    """CHECK 3 (rc20): the FIRMS-driven burning profile against the FAO crop
    calendar's harvest windows, weighted by each crop's burned dry matter.

    The two disagree for a knowable reason and the disagreement is the point: the
    held VIIRS record covers the two dominant burning windows (rice stubble
    Oct-Dec, wheat residue Apr-May) and nothing else, while the calendar places
    the cotton-stick, maize and cane-trash residues - roughly two fifths of
    burned dry matter - across harvest and crush windows the fetch never covered.
    The difference column is therefore a measured bound on what the two-window
    fire record cannot see, published beside the profile it grades."""
    from pkinv.core import registry as sector_registry
    from pkinv.sectors.agriculture import monthly as agri_monthly
    if not agri_monthly.firms_covers(fy_start):
        return []
    published = agri_monthly.burning_profile(fy_start)

    sector = sector_registry.get("agriculture")
    data = sector.load_data()
    burned = {}
    for crop, bp in data.burning.items():
        prod = data.crops.get(crop, {}).get("production_t")
        rr = data.residue.get(crop, {}).get("residue_ratio_ag")
        if prod and rr:
            burned[crop] = prod * rr * bp["frac_burned"]

    # rc40: the harvest sessions come from the derived table the burning windows read
    # (data/activity/agriculture/fao_harvest_sessions.csv), not from the FAO JSON, which a
    # validation package cannot carry. Same sessions, same months.
    from pkinv.sectors.agriculture import burn_windows
    windows = {}
    for crop, early, late in burn_windows.harvest_sessions():
        a, b = early[0], late[0]
        months = ([a] if a == b else
                  [(m - 1) % 12 + 1 for m in range(a, b + 1)] if b >= a else
                  [(m - 1) % 12 + 1 for m in range(a, b + 13)])
        windows.setdefault(crop, set()).update(months)

    rival = {m: 0.0 for m in sorted(published)}
    for crop, mass in burned.items():
        months = sorted(windows.get(crop, ()))
        if not months:
            continue
        for cal_month in months:
            year = fy_start if cal_month >= 7 else fy_start + 1
            key = "%d%02d" % (year, cal_month)
            if key in rival:
                rival[key] += mass / len(months)
    total = sum(rival.values())
    rival = {m: v / total for m, v in rival.items()}

    out = []
    for month in sorted(published):
        out.append({
            "check": "burning",
            "month": month,
            "published_share": published[month],
            "alternative_share": rival[month],
            "difference": published[month] - rival[month],
            "published_basis": "VIIRS FRP-weighted acquisition dates, two season windows",
            "alternative_basis": ("FAO crop-calendar harvest windows, all five burned "
                                  "crops weighted by burned dry matter"),
        })
    return out


def annual_tonnes(sector_row, products, fy_start=FY_START):
    """The annual edition's own figure for one customer class and product set."""
    total = None
    for r in _activity_rows(ANNUAL, comments=False):
        if (int(r["fiscal_year_start"]) == fy_start and r["sector_row"] == sector_row
                and r["product"] in products):
            total = (total or 0.0) + float(r["tonnes"] or 0.0)
    if total is None:
        raise KeyError("the OCAC annual edition has no FY%d %s row for %s"
                       % (fy_start, sector_row, "+".join(products)))
    return total


# Both regimes, because they test different things. FY2023-24's months are CUMULATIVE, so
# the sum is the June column and this compares two documents that may or may not have been
# revised between them. FY2021-22's months are twelve INDEPENDENT direct editions, so the sum
# is a genuine reassembly of the year from twelve separately printed numbers.
VINTAGE_YEARS = (2021, 2023)


def vintage_check(years=VINTAGE_YEARS):
    """Rows comparing summed monthly editions against the annual edition, per class."""
    rows = []
    for fy_start in years:
        label_year = "FY%d-%02d" % (fy_start, (fy_start + 1) % 100)
        for label, sector_row, products in CONSUMED:
            try:
                months, method = ocac_monthly.tonnes(sector_row, products, fy_start)
                published = annual_tonnes(sector_row, products, fy_start)
            except KeyError:
                continue        # a class the editions of that year do not carry
            recovered = sum(months.values())
            regime = "cumulative" if "T2" in method.values() else "direct"
            rows.append({"check": "vintage:%s:%s" % (label_year, label), "month": label_year,
                         "published_share": published, "alternative_share": recovered,
                         "difference": (recovered / published - 1.0) if published else 0.0,
                         "published_basis": "OCAC annual edition, tonnes",
                         "alternative_basis": "twelve %s monthly editions summed, tonnes"
                                              % regime})
    return rows


def burning_attribution_rows(fy_start=FY_START):
    """CHECK 5 (Wave 3): the attribution ladder's own counts, published.

    Every rung a detection can fail is a row - the directive's rule that an
    unattributed detection is COUNTED, never forced. The headline this publishes:
    the fetch box necessarily includes Indian Punjab, whose stubble fires dominate
    the raw record (~71 percent of FY2023-24 detections fall outside Pakistan), and
    the pre-Wave-3 profile weighted Pakistan's burning months by them. The
    attributed remainder is the profile's evidence base."""
    from pkinv.sectors.agriculture import monthly as agri_monthly
    try:
        _weights, counts = agri_monthly.burning_attribution(fy_start)
    except (KeyError, OSError):
        return []
    total = counts["detections_in_year"] or 1
    label = "FY%d-%02d" % (fy_start, (fy_start + 1) % 100)
    return [{"check": "burning_attribution:%s" % label, "month": rung,
             "published_share": count, "alternative_share": count / total,
             "difference": 0.0,
             "published_basis": "detections at this rung (count)",
             "alternative_basis": "share of the year's detections"}
            for rung, count in counts.items()]


def sir_fo_check(years=(2021, 2022, 2023)):
    """CHECK 4 (rc21): furnace oil's two instruments, published against each other.

    In FY2021-22 onward the SIR listing lane carries RFO-labelled plant generation month
    by month, but the shipped furnace-oil profile deliberately stays on the OCAC Total
    Power row - a fuel SALE - because OCAC's T1/T2 months outrank a TE3 generation shape.
    These two time DIFFERENT events (a depot sale precedes the burn it fuels), so their
    disagreement is not an error to fix; it is the honest width of the liquid streams'
    monthly claim, published the same way the fertiliser check publishes its own.
    """
    from pkinv.sectors.power import pbs_generation
    rows = []
    for fy_start in years:
        label_year = "FY%d-%02d" % (fy_start, (fy_start + 1) % 100)
        generation = pbs_generation.generation(fy_start).get("RFO", {})
        total = sum(generation.values())
        if not generation or total <= 0:
            continue
        try:
            months, _method = ocac_monthly.tonnes(
                ocac_monthly.TOTAL_POWER, ocac_monthly.FURNACE_OIL, fy_start)
        except KeyError:
            continue
        sales_total = sum(months.values())
        for month in sorted(generation):
            sales = months.get(month, 0.0)
            rows.append({
                "check": "power_fo_instruments:%s" % label_year, "month": month,
                "published_share": (sales / sales_total) if sales_total else 0.0,
                "alternative_share": generation[month] / total,
                "difference": generation[month] / total
                              - ((sales / sales_total) if sales_total else 0.0),
                "published_basis": "OCAC Total Power furnace oil, monthly editions "
                                   "(the shipped profile's instrument; times the sale)",
                "alternative_basis": "NEPRA SIR listings, RFO-labelled plant generation "
                                     "(times the generation; deliberately not applied)"})
    return rows


def summarise(rows):
    """{check: (max absolute difference, sum of absolute differences)}.

    Both are read in the units of their own check: shares for the fertiliser comparison,
    a relative gap for the vintage one.
    """
    out = {}
    for r in rows:
        gap = abs(r["difference"])
        biggest, total = out.get(r["check"], (0.0, 0.0))
        out[r["check"]] = (max(biggest, gap), total + gap)
    return dict(sorted(out.items()))


def main():
    rows = (fertiliser_check() + burning_check() + vintage_check() + sir_fo_check()
            + burning_attribution_rows())
    os.makedirs(OUTPUTS, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["check", "month", "published_share", "alternative_share", "difference",
                    "published_basis", "alternative_basis"])
        for r in rows:
            w.writerow([r["check"], r["month"], round(r["published_share"], 6),
                        round(r["alternative_share"], 6), round(r["difference"], 6),
                        r["published_basis"], r["alternative_basis"]])

    print("monthly cross-checks -> %s" % OUT)
    biggest, total = summarise(rows)["fertiliser"]
    print("  fertiliser: the offtake profile and the agronomic calendar disagree by %.1f "
          "points in the worst month" % (100 * biggest))
    print("    and by %.1f points summed over the year - a quarter of the annual nitrogen "
          "moves month" % (100 * total))
    if "burning" in summarise(rows):
        b_biggest, b_total = summarise(rows)["burning"]
        print("  burning: the FIRMS profile and the all-crop FAO harvest calendar disagree "
              "by %.1f points in the worst month (%.1f summed) - the measured bound on "
              "what the two-window fire record cannot see"
              % (100 * b_biggest, 100 * b_total))
    for r in rows:
        if r["check"].startswith("vintage"):
            print("  %-40s %+6.2f%% vs the annual edition (%s)"
                  % (r["check"][len("vintage:"):], 100 * r["difference"],
                     r["alternative_basis"].split()[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
