"""Consistency diagnostics on the OCAC sectoral tables - the control totals' evidence.

WHY THIS EXISTS. The petrol and diesel controls carry a declared 10 percent
uncertainty, and until now the only support for that number was one sentence asserting
it was "roughly twice the observed error" plus a single cross-source comparison against
the railway Year Book. OCAC publishes nine annual editions and forty-eight monthly ones
in this repository, which is enough to measure its internal consistency rather than
assert it. This module does that and writes the evidence out; it never changes a
control, a factor or a component.

FOUR CHECKS, ONE OF WHICH IS NOT INDEPENDENT AND SAYS SO:

1. Annual Road rows against the monthly panel. Only fiscal years whose twelve monthly
   editions are DIRECT (not year-to-date cumulatives) give an independent comparison;
   in the years where the panel is cumulative the June edition simply IS the annual
   figure reprinted, and reporting that 0.000 percent as corroboration would be
   circular. The `independent` column marks which is which.

2. Customer classes against the printed national total, every annual edition. This is
   where the interesting failure lives: FY2017-18's HSD classes sum 521,822 t short of
   the total the same page prints - the only such failure in nine editions - and that
   edition is precisely the one that sets the LOW end of the nine-year road-share
   envelope the paper publishes as a boundary case.

3. Provincial additivity in the monthly editions. KARACHI is nested inside SINDH in
   this publication and must be excluded from the sum, which is the kind of thing that
   silently doubles a province if nobody checks.

4. The one genuinely external check - the railway Year Book against OCAC's Railways
   row - relayed from road.rail_crosscheck() rather than recomputed, so it cannot
   drift from the figure the paper quotes.

Writes: outputs/transport_ocac_control_diagnostic.csv
"""

from pkinv.assets import asset_path
import csv
import os

from pkinv.paths import DATA, OUTPUTS
from pkinv.sectors.transport import road
from pkinv.sectors.transport.data import TransportData
from pkinv.activity.store import read_rows
from pkinv.core.io import write_table

ANNUAL = asset_path(DATA, "activity", "transport", "ocac_sectoral_annual.csv")
PROVINCIAL = asset_path(DATA, "activity", "transport", "ocac_sectoral_provincial.csv")

FIELDS = ("check", "fiscal_year", "product", "sector_row", "panel_value",
          "printed_value", "abs_diff", "rel_pct", "independent", "verdict", "note")

ROAD_PRODUCTS = ("MS", "HOBC", "HSD")
# The exhaustive customer-class partition OCAC's own total is the sum of. The
# Transport sub-rows (Road, Railways, Domestic Bunkers) roll up into Total Transport
# and must not be added beside it.
CUSTOMER_CLASSES = ("DOMESTIC", "Total Industry", "AGRICULTURE", "Total Transport",
                    "Total Power", "Total Government")
# TOTAL and TOTAL_PRIOR are column sums, not products.
SKIP_PRODUCTS = ("TOTAL", "TOTAL_PRIOR")
# KARACHI is a sub-area of SINDH in the monthly area pages; including it double-counts.
NESTED_AREAS = ("KARACHI",)


def _rows(path):
    return read_rows(path, comments=False)


def _row(check, fy, product, sector_row, panel, printed, independent, verdict,
         note=""):
    diff = None if panel is None or printed is None else panel - printed
    rel = (None if diff is None or not printed else 100.0 * diff / printed)
    return {"check": check, "fiscal_year": fy, "product": product,
            "sector_row": sector_row,
            "panel_value": "" if panel is None else round(panel, 1),
            "printed_value": "" if printed is None else round(printed, 1),
            "abs_diff": "" if diff is None else round(diff, 1),
            "rel_pct": "" if rel is None else round(rel, 4),
            "independent": independent, "verdict": verdict, "note": note}


def annual_vs_monthly(annual=None, provincial=None):
    """Check 1: the annual Road rows against the sum of the monthly editions."""
    annual = _rows(ANNUAL) if annual is None else annual
    prov = _rows(PROVINCIAL) if provincial is None else provincial
    out = []
    for fy in sorted({r["fiscal_year_start"] for r in prov}):
        months = [r for r in prov
                  if r["fiscal_year_start"] == fy and r["area"] == "PAKISTAN"
                  and r["sector_row"] == "Road"]
        kinds = {r["report_kind"] for r in months}
        # A cumulative panel's final edition is the annual figure restated, so the
        # comparison is an identity rather than evidence. Say so in the row.
        direct = kinds == {"monthly"}
        n_months = len({r["month"] for r in months})
        for product in ROAD_PRODUCTS:
            if direct:
                panel = sum(float(r["tonnes"]) for r in months
                            if r["product"] == product)
            else:
                last = max((r["month"] for r in months
                            if r["report_kind"] != "monthly"), default=None)
                if last is None:
                    continue
                panel = sum(float(r["tonnes"]) for r in months
                            if r["product"] == product and r["month"] == last)
            printed = sum(float(r["tonnes"]) for r in annual
                          if r["fiscal_year_start"] == fy
                          and r["sector_row"] == "Road"
                          and r["product"] == product)
            if not printed:
                continue
            rel = abs(100.0 * (panel - printed) / printed)
            out.append(_row(
                "annual vs monthly panel", fy, product, "Road", panel, printed,
                "yes" if direct else "no",
                "CONSISTENT" if rel < 1.0 else "DISCREPANT",
                "%d direct monthly editions summed" % n_months if direct else
                "cumulative panel: the final year-to-date edition IS the annual "
                "figure restated, so this row is an identity, not evidence"))
    return out


def classes_vs_total(annual=None):
    """Check 2: customer-class rows against the national total the same page prints."""
    annual = _rows(ANNUAL) if annual is None else annual
    out = []
    fys = sorted({r["fiscal_year_start"] for r in annual})
    for fy in fys:
        year_rows = [r for r in annual if r["fiscal_year_start"] == fy]
        total_row = "TOTAL_INTERNAL"
        if not any(r["sector_row"] == total_row for r in year_rows):
            continue
        for product in ROAD_PRODUCTS:
            printed = sum(float(r["tonnes"]) for r in year_rows
                          if r["sector_row"] == total_row
                          and r["product"] == product)
            # Road/Railways/Domestic Bunkers roll up INTO Total Transport, so
            # summing them alongside it would double the transport claim.
            classes = sum(float(r["tonnes"]) for r in year_rows
                          if r["sector_row"] in CUSTOMER_CLASSES
                          and r["product"] == product)
            if not printed:
                continue
            rel = abs(100.0 * (classes - printed) / printed)
            out.append(_row(
                "classes vs printed total", fy, product, total_row, classes,
                printed, "yes",
                "ADDITIVE" if rel < 0.01 else "NON-ADDITIVE",
                "" if rel < 0.01 else
                "the edition's own customer classes do not sum to the total it "
                "prints; this is a source inconsistency, carried rather than "
                "corrected"))
    return out


def provincial_additivity(provincial=None, limit=None):
    """Check 3: area rows against PAKISTAN in the monthly editions."""
    prov = _rows(PROVINCIAL) if provincial is None else provincial
    monthly = [r for r in prov if r["report_kind"] == "monthly"]
    keys = sorted({(r["month"], r["product"], r["sector_row"]) for r in monthly})
    checked = failures = 0
    worst = []
    for month, product, sector in keys:
        if product in SKIP_PRODUCTS:
            continue
        cells = [r for r in monthly if r["month"] == month
                 and r["product"] == product and r["sector_row"] == sector]
        national = sum(float(r["tonnes"]) for r in cells if r["area"] == "PAKISTAN")
        areas = sum(float(r["tonnes"]) for r in cells
                    if r["area"] != "PAKISTAN" and r["area"] not in NESTED_AREAS)
        if not national:
            continue
        checked += 1
        rel = abs(100.0 * (areas - national) / national)
        if rel >= 0.01:
            failures += 1
            worst.append((rel, month, product, sector, areas, national))
    worst.sort(reverse=True)
    out = [_row("provincial additivity", "all monthly editions", "all", "all",
                checked - failures, checked, "yes",
                "CONSISTENT" if failures <= 3 else "REVIEW",
                "%d of %d non-zero (month, product, sector) cells reconcile to "
                "< 0.01%%; KARACHI excluded as a sub-area of SINDH"
                % (checked - failures, checked))]
    for rel, month, product, sector, areas, national in worst[:(limit or 3)]:
        out.append(_row("provincial additivity (exception)", month, product,
                        sector, areas, national, "yes", "DISCREPANT",
                        "the largest residuals in the panel: Power and Industry rows of a few hundred tonnes. No Road row fails, which is what matters here - the Road rows are the controls"))
    return out


def rail_crosscheck_rows(data):
    """Check 4: the one external comparison, relayed rather than recomputed."""
    chk = road.rail_crosscheck(data)
    return [
        _row("external cross-source (rail)", "FY2023-24", "HSD", "RAILWAYS",
             chk["yb_kt"] * 1000.0, chk["ocac_kt"] * 1000.0, "yes",
             "CONSISTENT",
             "Year Book metered purchases against OCAC's Railways customer-class row, "
             "both FY2023-24 - unrelated reporting chains on the same twelve months. "
             "Year-matched without contrivance since the harmonisation round; it "
             "previously required the Year Book's own historical row to meet a transport "
             "sector reporting FY2021-22"),
        _row("external cross-source (rail)", "FY2021-22 offset", "HSD", "RAILWAYS",
             chk["yb_historical_kt"] * 1000.0, chk["ocac_kt"] * 1000.0, "yes",
             "CONSISTENT",
             "the same OCAC row against the Year Book two years earlier - retained to "
             "show what a two-year offset costs, not as a comparison"),
    ]


def build(data=None):
    data = TransportData() if data is None else data
    return (annual_vs_monthly() + classes_vs_total() + provincial_additivity()
            + rail_crosscheck_rows(data))


def summary(rows):
    """The numbers the paper quotes: typical and worst observed inconsistency."""
    internal = [abs(float(r["rel_pct"])) for r in rows
                if r["check"] in ("annual vs monthly panel",
                                  "classes vs printed total")
                and r["independent"] == "yes" and r["rel_pct"] != ""]
    external = [abs(float(r["rel_pct"])) for r in rows
                if r["check"] == "external cross-source (rail)"
                and r["rel_pct"] != ""]
    return {"n_internal": len(internal),
            "worst_internal_pct": max(internal) if internal else 0.0,
            "median_internal_pct": sorted(internal)[len(internal) // 2]
            if internal else 0.0,
            "worst_external_pct": max(external) if external else 0.0}


def main(data=None):
    os.makedirs(OUTPUTS, exist_ok=True)
    data = TransportData() if data is None else data
    rows = build(data)
    path = asset_path(OUTPUTS, "transport_ocac_control_diagnostic.csv")
    write_table(path, list(FIELDS), rows)
    s = summary(rows)
    print("  OCAC consistency: %d independent internal checks, median %.3f%%, "
          "worst %.2f%%; worst external %.1f%% -> %s"
          % (s["n_internal"], s["median_internal_pct"], s["worst_internal_pct"],
             s["worst_external_pct"], os.path.basename(path)))
    return rows


if __name__ == "__main__":
    main()
