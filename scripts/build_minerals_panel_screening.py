#!/usr/bin/env python3
"""Which province-years of the minerals panel are whole, and what does a hole cost?

THE SHORT VERSION, because one number carries it: the monthly profile this project serves
for crude oil in FY2021-22 puts 78.76% of the year in a single month, and labels it T2 -
observed. It is Balochistan's record alone, and `covers()` asks only for twelve months
rather than for the country.

AND THE PROVINCES ARE NOT MISSING FROM THE SOURCE. PBS prints all four. The mineral's
name cell is vertically centred across its five province rows, so `pdftotext -layout`
emits the name on the MIDDLE line - the rows printed above it belong to that mineral and
the parser, which treats the name line as the group's first row, loses them. The identity
proves it to the unit: for FY2021-22 coal, the Punjab and Sindh rows printed above the
"13 COAL KPK" line, plus KPK and Balochistan, equal the printed Total in every one of the
twelve months exactly (year 9,678,139 both sides). The panel carries 42% of that year's
coal.

WORSE, THE GROUP CONTROL CANNOT SEE IT. The parse reports "1571 of 1683 mineral-years
closing the group control" as assurance, and that control compares the rows it BUFFERED
against the printed Total - not the rows the panel ships. For FY2021-22 coal it closes
exactly while the panel holds 4,072,263 of the 9,678,139 it just certified. Nine canonical
(mineral, year) cells disagree between the closing control and the shipped panel, in both
directions: limestone FY2016-17 ships 7% of what its control counted, coal FY2015-16 47%,
coal FY2021-22 42%, natural gas FY2023-24 34%, crude oil FY2023-24 46% - and crude oil and
natural gas FY2020-21 ship 2.19x and 2.31x, which is the worksheet duplication. A control
that passes while its subject is short is not a control, and this screening now computes
the comparison the parse never made.

    python3 scripts/build_minerals_panel_screening.py
    -> outputs/pakemis_minerals_panel_screening.csv

WHAT THIS FOUND. The PBS minerals panel is wired into the inventory as a monthly SHAPE:
pkinv.core.pbs_minerals serves upstream gas and oil timing to fugitives, and its docstring
defends the arrangement with "the profile is a shape, never a magnitude ... a published
quantity could be wrong by any amount without moving the inventory". That defence is
sound against a magnitude error and it does not cover a MISSING PROVINCE, because a shape
computed over part of the country is a different quantity wearing the same name. Both
kinds are present and the parse's own summary reported neither as such - it publishes
"1571 of 1683 mineral-years closing the group control" without ever saying whether a
failing one is a mineral the inventory reads.

Two of the 112 failures are: natural gas FY2019-20 and limestone FY2020-21.

  MAGNITUDE. The spreadsheet editions are read across EVERY worksheet, and some workbooks
  carry the same table on several - FY2017-18 ships '17-18', 'Sheet1', 'merging',
  'Quarterly' and 'final'; FY2020-21 ships 'Electricity generation' and 'mineral
  production'. So those years are counted once per sheet that repeats them. FY2020-21
  natural gas carries 31 rows per month against FY2017-18's 4, and reads 18.4 million
  against 1.44 million the year before. It is a published activity figure that is simply
  wrong.
  AND IT DOES NOT MOVE THE SHAPE, which this file reports rather than assumes: the
  duplication is uniform at 31 rows in every one of the twelve months, so the normalised
  profile matches a clean year to within a quarter of a percentage point. The defence
  holds here.

  SHAPE. Several years are missing whole provinces. FY2019-20 natural gas has no KPK rows
  at all - 11.9% of the national total, which is exactly why its group control fails.
  FY2021-22 and FY2023-24 carry only Balochistan and KPK; FY2022-23 has no Balochistan.
  The defence does NOT hold here, and the cost is BOUNDED rather than asserted: taking
  the years where all four provinces are present and recomputing the shape from the
  subsets the broken years actually have moves a monthly share by at most 1.1 percentage
  points, and on average under 0.3. Pakistani gas production has almost no seasonality
  and the provinces' curves are alike, which is the only reason losing 62% of the mass
  costs so little. That bound is the finding: without it, a missing majority of
  production looks fatal, and with it the timing is tolerable and the magnitude is not.

SCOPE. This is a screening beside the panel. It changes no parse, no quantity and no
profile: repairing the duplication would move a published activity table and repairing
the missing provinces would move a published monthly shape, and both are decisions rather
than audit edits. What it does is make the holes countable and the cost measured.
"""
import collections
import csv
import os
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.assets import asset_path                                   # noqa: E402
from pkinv.core.io import write_table                                 # noqa: E402
from pkinv.core import pbs_minerals                                   # noqa: E402

OUT = os.path.join(ROOT, "outputs", "pakemis_minerals_panel_screening.csv")
PANEL = "data/activity/monthly/pbs_minerals_month_province.csv"
NATIONAL = "National (edition prints no province split)"
PROVINCES = ("Balochistan", "KPK", "Punjab", "Sindh")


def panel():
    path = asset_path(ROOT, PANEL)
    with open(path, encoding="utf-8") as handle:
        return [r for r in csv.DictReader(line for line in handle
                                          if not line.startswith("#"))]


def shape(rows, mineral, fy, provinces=None):
    """{month: share} over the chosen provinces, or {} if there is nothing to normalise."""
    total = collections.defaultdict(float)
    for row in rows:
        if (row["canonical_mineral"] != mineral
                or int(row["fiscal_year_start"]) != fy
                or (provinces is not None and row["province"] not in provinces)):
            continue
        total[row["month"]] += float(row["quantity"])
    whole = sum(total.values())
    if not whole:
        return {}
    return {month: total[month] / whole for month in sorted(total)}


def cost_of_subset(rows, mineral, present):
    """(max, mean) percentage-point move from using `present` instead of all provinces.

    Measured on the years where ALL FOUR provinces are in the panel, because those are
    the only years where both shapes can be computed from the same data. A year with its
    own hole cannot price its own hole.
    """
    worst, means = 0.0, []
    for fy in sorted({int(r["fiscal_year_start"]) for r in rows}):
        provinces = {r["province"] for r in rows
                     if r["canonical_mineral"] == mineral
                     and int(r["fiscal_year_start"]) == fy}
        if not set(PROVINCES) <= provinces:
            continue
        full = shape(rows, mineral, fy)
        sub = shape(rows, mineral, fy, present)
        if not full or not sub:
            continue
        diffs = [abs(full[m] - sub.get(m, 0.0)) for m in full]
        worst = max(worst, max(diffs))
        means.append(statistics.fmean(diffs))
    if not means:
        return None, None
    return 100.0 * worst, 100.0 * statistics.fmean(means)


def control_vs_panel():
    """{(mineral, fy): (control_declared, panel_sum)} - the comparison the parse omits.

    The group control sums the rows the parser BUFFERED and compares them with the
    printed Total; the panel ships a different set. Re-parsing the raw editions here is
    the only way to see both numbers at once, which is precisely why nothing noticed.
    """
    import glob
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_minerals_ingest", os.path.join(ROOT, "scripts", "ingest_pbs_minerals.py"))
    ingest = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ingest)
    out = {}
    for path in sorted(glob.glob(os.path.join(ROOT, "data", "raw", "pbs",
                                              "minerals", "*"))):
        parsed, _bad, groups = ingest.parse(path)
        canonical = {r["mineral"]: r["canonical_mineral"] for r in parsed
                     if r["canonical_mineral"]}
        shipped, declared = collections.defaultdict(float), collections.defaultdict(float)
        for row in parsed:
            if row["canonical_mineral"]:
                shipped[(row["canonical_mineral"],
                         row["fiscal_year_start"])] += row["quantity"]
        for group in groups:
            name = canonical.get(group["mineral"])
            if name:
                declared[(name, group["fiscal_year_start"])] += group["provinces_sum"]
        for key in set(shipped) | set(declared):
            out[key] = (declared.get(key, 0.0), shipped.get(key, 0.0))
    return out


def main():
    rows = panel()
    control = control_vs_panel()
    minerals = sorted({r["canonical_mineral"] for r in rows if r["canonical_mineral"]})
    out = []
    for mineral in minerals:
        years = sorted({int(r["fiscal_year_start"]) for r in rows
                        if r["canonical_mineral"] == mineral})
        for fy in years:
            year_rows = [r for r in rows if r["canonical_mineral"] == mineral
                         and int(r["fiscal_year_start"]) == fy]
            provinces = sorted({r["province"] for r in year_rows})
            months = collections.Counter(r["month"] for r in year_rows)
            per_month = sorted(set(months.values()))
            missing = [p for p in PROVINCES if p not in provinces]
            national_mixed = NATIONAL in provinces and any(p in provinces
                                                           for p in PROVINCES)
            quantity = sum(float(r["quantity"]) for r in year_rows)
            # The shape the ENGINE actually serves for this mineral-year, and the method
            # it labels it with. This is the column that shows the defect rather than
            # pricing a counterfactual: a profile built from one province is still served
            # as T2 "observed", and its worst month says how badly.
            served, methods, covered = pbs_minerals.profile_or_flat(mineral, fy)
            worst_month = max(served.values()) if served else 0.0
            method = ";".join(sorted(set(methods.values()))) if methods else ""

            if provinces == [NATIONAL]:
                verdict = "national only, as the edition printed it"
            elif national_mixed:
                verdict = "DOUBLE COUNTED: a national row beside the provinces"
            elif missing:
                verdict = "PROVINCE MISSING"
            else:
                verdict = "all four provinces present"

            worst = mean = ""
            if missing and provinces != [NATIONAL]:
                present = {p for p in provinces if p in PROVINCES}
                w, m = cost_of_subset(rows, mineral, present)
                if w is not None:
                    worst, mean = "%.3f" % w, "%.3f" % m

            declared, shipped = control.get((mineral, fy), (0.0, 0.0))
            agrees = (not declared) or abs(declared - shipped) <= 0.01 * max(declared, 1.0)
            out.append({
                "canonical_mineral": mineral,
                "fiscal_year_start": fy,
                "provinces_present": ";".join(provinces),
                "provinces_missing": ";".join(missing) or "none",
                "rows_per_month": ";".join(str(n) for n in per_month),
                "months_covered": len(months),
                "panel_quantity": "%.3f" % quantity,
                "verdict": verdict,
                "shape_cost_max_pp": worst,
                "shape_cost_mean_pp": mean,
                "served_worst_month_share_pct": "%.2f" % (100.0 * worst_month),
                # The twelve shares themselves, because the SHAPE is the finding and a
                # single worst month cannot show it. The claim/evidence table quoted all
                # twelve from a console run while the product published only the maximum,
                # so a reader following the command saw one number of the twelve.
                "served_profile_pct": ";".join("%.2f" % (100.0 * served[m])
                                               for m in sorted(served)) or "n.a.",
                "served_timing_method": method,
                "served_as_covered": "yes" if covered else "no",
                "group_control_declared": "%.3f" % declared,
                "panel_ships": "%.3f" % shipped,
                "control_agrees_with_panel": "yes" if agrees else "NO",
                "panel_share_of_control_pct": ("%.1f" % (100.0 * shipped / declared)
                                               if declared else "n.a."),
                "note": ("the rows-per-month figure is the duplication: a spreadsheet "
                         "edition is read across every worksheet, so a workbook that "
                         "repeats its table on working sheets is counted once per sheet. "
                         "Uniform duplication leaves the normalised shape intact and the "
                         "published quantity wrong; a missing province does the opposite, "
                         "and shape_cost_* prices it against the years where all four "
                         "provinces are present"),
            })

    counts = collections.Counter(r["verdict"] for r in out)
    banner = [
        "MINERALS PANEL SCREENING: which (mineral, fiscal year) cells of the monthly",
        "province panel are whole, and what a hole costs the SHAPE the inventory actually",
        "consumes. A screening beside the panel - no parse, quantity or profile changes.",
        "Two kinds of defect, with opposite consequences: uniform duplication across",
        "worksheets leaves the shape intact and the published quantity wrong, while a",
        "missing province leaves the quantity plausible and the shape wrong.",
    ] + ["%s: %d" % (verdict, n) for verdict, n in sorted(counts.items())]
    write_table(OUT, list(out[0]), out, banner=banner)
    print("Minerals panel screening -> %s" % OUT)
    for verdict, n in sorted(counts.items()):
        print("   %-48s %d" % (verdict, n))
    top = max(out, key=lambda r: float(r["served_worst_month_share_pct"]))
    print("   worst SERVED shape: %s FY%s puts %s%% of the year in one month, method %s"
          % (top["canonical_mineral"], top["fiscal_year_start"],
             top["served_worst_month_share_pct"], top["served_timing_method"]))
    incomplete = [r for r in out if r["provinces_missing"] != "none"
                  and r["served_as_covered"] == "yes"]
    print("   %d mineral-year(s) are served as COVERED (T2) from an incomplete province "
          "set" % len(incomplete))
    disagree = [r for r in out if r["control_agrees_with_panel"] == "NO"]
    print("   %d mineral-year(s) where the CLOSING group control and the shipped panel "
          "disagree:" % len(disagree))
    for row in sorted(disagree, key=lambda r: float(r["panel_share_of_control_pct"])):
        print("      %-12s FY%-6s panel ships %6s%% of what its control counted"
              % (row["canonical_mineral"], row["fiscal_year_start"],
                 row["panel_share_of_control_pct"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
