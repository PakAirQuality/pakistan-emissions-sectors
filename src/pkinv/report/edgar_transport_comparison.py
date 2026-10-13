"""Every EDGAR transport comparison this inventory can honestly make, ranked.

THE PROBLEM THIS SOLVES. A single ratio against EDGAR hides three separate choices -
which categories are being compared, which years, and whether the off-road class counts
- and earlier editions of the transport paper quoted one number without saying which
choices produced it. Worse, the comparison was labelled "year-matched" while comparing a
July-June fiscal year against EDGAR's calendar 2022, which is only half matched.

WHAT IS PRIMARY, AND WHY. This sector's reference period is FY2023-24: six months in
calendar 2023 and six in calendar 2024. The closest annual approximation EDGAR's data
supports is therefore the half-and-half blend of its 2023 and 2024 columns, and that is
the primary row. The single-calendar-year comparisons remain, labelled as secondary,
because a reader may want them and because the spread between them IS the temporal
uncertainty - it should be visible, not chosen.

THE SUPERSEDED ROW IS A CONFESSION, NOT A COMPARISON. rc4 and earlier editions led with
a 0.70 ratio built from live FY2023-24 road plus FY2021-22 rail and aviation against a
CY2021/CY2022 EDGAR blend - three vintages in one number, labelled "all FY2021-22" by a
string this module hard-coded. That construction is reproduced here under rank
`superseded` so the published history remains checkable, and so nobody quotes it as
current again: the honest current-period ratio is the PRIMARY row's.

SCOPE IS INFERRED, NOT PUBLISHED. The booklet gives one "Transport" number with no IPCC
split. Which Pakistani categories it covers is inferred from EDGAR's category-resolved
AIR-POLLUTANT files, a different release - Pakistan has road, rail and civil aviation
rows and no navigation row at all. That inference is evidence, not documentation, and
every row here says so. The comparison is a scope-approximate diagnostic, never a
validation: the boundaries are only partly aligned, which is why the national paper
declines to quote a single transport ratio at all.

Writes: outputs/national_edgar_transport_comparison.csv
"""

from pkinv.assets import asset_path
import csv
import os

from pkinv.paths import DATA, OUTPUTS
from pkinv.activity.store import read_rows
from pkinv.core.io import write_table

SERIES = asset_path(DATA, "activity", "transport",
                      "edgar_pak_transport_series.csv")
CATEGORIES = asset_path(DATA, "activity", "transport",
                          "edgar_pak_transport_categories.csv")
FIELDS = ("construction", "rank", "engine_Mt", "engine_scope", "edgar_basis",
          "edgar_Mt", "ratio_engine_over_edgar", "note")

# Six of twelve months of FY2023-24 fall in each calendar year.
FY_WEIGHTS = ((2023, 0.5), (2024, 0.5))
# The rc4-era blend, kept only for the superseded row.
SUPERSEDED_FY_WEIGHTS = ((2021, 0.5), (2022, 0.5))


def _rows(path):
    return read_rows(path, comments=False)


def _out(name):
    return asset_path(OUTPUTS, name)


def _year():
    """The transport sector's reference period, so this comparison follows it rather than
    reading an output filename that no longer exists after a harmonisation."""
    from pkinv.sectors.transport.data import TransportData
    return TransportData().year


def _cell(path, key_col, key, col):
    for r in _rows(path):
        if r[key_col] == key:
            return float(r[col])
    raise KeyError((path, key))


def edgar_series():
    return {int(r["year"]): float(r["total_Mt_co2e_AR5"]) for r in _rows(SERIES)}


def fy_blend(series=None, weights=FY_WEIGHTS):
    """EDGAR at this sector's fiscal year: half of each calendar column."""
    series = edgar_series() if series is None else series
    return sum(series[y] * w for y, w in weights)


def engine_terms():
    """The pieces of an EDGAR-scope-matched construction, all on the reference period.

    Rail and aviation are read from their sectors' own series at the SAME fiscal year
    as the road figure - the rc4 edition hard-coded them to FY2021-22 rows beside a
    live FY2023-24 road term and shipped the mix for a full release. The superseded
    terms are kept separately and explicitly."""
    road = _cell(_out("transport_totals_%d.csv" % _year()), "category", "Road transport",
                 "co2e_Mt_AR5")
    offroad = _cell(_out("transport_totals_%d.csv" % _year()), "category",
                    "Mixed off-road (1A4c/1A2)", "co2e_Mt_AR5")
    # STRICT 1A3c, not the module total (the eighth review): EDGAR's inferred scope
    # is 1.A.3.a + 1.A.3.b + 1.A.3.c, and since the rc11 re-base the module total
    # carries 0.00498 Mt at a non-1A3c category. Like-for-like takes the traction row.
    rail = _cell(_out("railways_totals_2024.csv"), "category", "Railways",
                 "co2e_Mt_AR5")
    aviation = _cell(_out("aviation_timeseries_2006_fy2023_24.csv"), "fiscal_year",
                     "2023", "domestic_kt_co2e_AR5") / 1000.0
    rail_fy22 = _cell(_out("railways_timeseries_2024.csv"), "fiscal_year", "2022",
                      "mt_co2e_AR5")
    aviation_fy22 = _cell(_out("aviation_timeseries_2006_fy2023_24.csv"), "fiscal_year",
                          "2022", "domestic_kt_co2e_AR5") / 1000.0
    calendar = _cell(_out("transport_uncertainty_scenarios_%d.csv" % _year()),
                     "structural_scenario", "calendar_2022_controls", "road_Mt")
    return {"road": road, "offroad": offroad, "rail": rail, "aviation": aviation,
            "rail_fy22": rail_fy22, "aviation_fy22": aviation_fy22,
            "calendar_road": calendar}


def build():
    series = edgar_series()
    blend = fy_blend(series)
    superseded_blend = fy_blend(series, SUPERSEDED_FY_WEIGHTS)
    t = engine_terms()
    matched = t["road"] + t["rail"] + t["aviation"]
    incl_off = matched + t["offroad"]
    superseded = t["road"] + t["rail_fy22"] + t["aviation_fy22"]
    scope = "road residual + railways + domestic aviation, all FY2023-24"
    cat_note = ("scope inferred from EDGAR's category-resolved Pakistani air-pollutant "
                "files (v8.1), not from the GHG booklet, which publishes no IPCC "
                "split: Pakistan has 1.A.3.a, 1.A.3.b and 1.A.3.c rows and NO 1.A.3.d "
                "navigation row")
    rows = [
        {"construction": "EDGAR-scope match at the fiscal-year blend", "rank": "PRIMARY",
         "engine_Mt": matched, "engine_scope": scope,
         "edgar_basis": "0.5 x CY2023 + 0.5 x CY2024", "edgar_Mt": blend,
         "note": "the closest annual approximation to July 2023-June 2024 that EDGAR's "
                 "calendar series supports - six months fall in each column. This is "
                 "the comparison the paper leads with, and it is NOT 'year-matched': "
                 "it is fiscal-year blended, and a scope-approximate diagnostic rather "
                 "than a validation. " + cat_note},
        {"construction": "EDGAR-scope match against calendar 2024", "rank": "secondary",
         "engine_Mt": matched, "engine_scope": scope,
         "edgar_basis": "CY2024", "edgar_Mt": series[2024],
         "note": "the single-column comparison; it overlaps this sector's fiscal year "
                 "by six months only"},
        {"construction": "EDGAR-scope match against calendar 2023", "rank": "secondary",
         "engine_Mt": matched, "engine_scope": scope,
         "edgar_basis": "CY2023", "edgar_Mt": series[2023],
         "note": "the other half of the fiscal year; the spread between this row and "
                 "the CY2024 row is the temporal uncertainty the blend averages"},
        {"construction": "including mixed off-road machinery", "rank": "secondary",
         "engine_Mt": incl_off, "engine_scope": scope + ", plus mixed off-road",
         "edgar_basis": "0.5 x CY2023 + 0.5 x CY2024", "edgar_Mt": blend,
         "note": "EDGAR books machinery outside its transport aggregate, so this "
                 "construction deliberately exceeds EDGAR's scope. Worth reporting "
                 "because it is nearly invariant to the class reweighting: energy "
                 "weighting moves diesel BETWEEN 1A3b and 1A4c, so a total spanning "
                 "both barely moves"},
        {"construction": "rc4's mixed-vintage construction", "rank": "superseded",
         "engine_Mt": superseded,
         "engine_scope": "FY2023-24 road + FY2021-22 railways + FY2021-22 domestic "
                         "aviation - three vintages, labelled 'all FY2021-22' when "
                         "published",
         "edgar_basis": "0.5 x CY2021 + 0.5 x CY2022", "edgar_Mt": superseded_blend,
         "note": "reproduced so the 0.70 that rc4's abstract promoted as current "
                 "remains checkable. It mixed the harmonised road figure with "
                 "pre-harmonisation rail and aviation rows against a demand-peak "
                 "EDGAR window; it must not be quoted as the current comparison"},
        {"construction": "calendar-2022 controls, road only", "rank": "superseded",
         "engine_Mt": t["calendar_road"] + t["rail_fy22"] + t["aviation_fy22"],
         "engine_scope": "road residual rebuilt on CY2022 controls, plus FY2021-22 "
                         "rail and aviation",
         "edgar_basis": "CY2022", "edgar_Mt": series[2022],
         "note": "the rc4-era calendar-year construction, retained as history: CY2022 "
                 "straddles the mid-2022 demand collapse, which is why it sits so far "
                 "below the fiscal-year rows of its era"},
        {"construction": "whole sector against EDGAR (coarse)", "rank": "context",
         "engine_Mt": _cell(_out("transport_totals_%d.csv" % _year()), "category", "TOTAL",
                            "co2e_Mt_AR5"),
         "engine_scope": "this sector's reported total (road + mixed off-road + CNG)",
         "edgar_basis": "CY2024", "edgar_Mt": series[2024],
         "note": "the ratio a reader gets by dividing the two headline numbers "
                 "without matching scope or year; kept so the difference from the "
                 "primary row is visible rather than argued"},
    ]
    for r in rows:
        r["ratio_engine_over_edgar"] = round(r["engine_Mt"] / r["edgar_Mt"], 4)
        r["engine_Mt"] = round(r["engine_Mt"], 5)
        r["edgar_Mt"] = round(r["edgar_Mt"], 4)
    return rows


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    rows = build()
    path = _out("national_edgar_transport_comparison.csv")
    write_table(path, list(FIELDS), rows)
    print("EDGAR transport comparison -> %s" % os.path.basename(path))
    for r in rows:
        print("  %-46s %-10s %7.3f / %7.3f = %.3f"
              % (r["construction"], r["rank"], r["engine_Mt"], r["edgar_Mt"],
                 r["ratio_engine_over_edgar"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
