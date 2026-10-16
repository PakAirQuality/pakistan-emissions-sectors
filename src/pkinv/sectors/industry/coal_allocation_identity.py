"""HDIP's coal consumption is its coal supply, and the consumer split is a redistribution.

WHY THIS EXISTS. The industrial module books HDIP's coal-by-consumer allocation: the brick
kiln column and the cement column reach 1.A.2 directly, and the brick fleet's own survey
evidence sits beside them explicitly not booked ("NOTHING HERE IS BOOKED. The engine burns
HDIP's national brick column"). That arrangement rests on the booked column being a
measurement of brick coal. It is not, and this measures the difference.

FIRST, THE IDENTITY. HDIP's coal supply (imports plus production) and HDIP's coal
consumption (the consumer columns summed) are both held here, republished in the same
Pakistan Economic Survey statistical supplement. Across the fourteen years both tables cover
they close to within 1 kt in thirteen of them - to zero in most - with ONE exception, -204 kt
in FY2015-16, which no held note explains. FY2023-24 was a second exception until 2026-10-06
and was never a data fact: it was this builder reading the superseded provisional print that
coal_by_consumer.csv deliberately retains. The reason recorded for it inverted the supply
table's own note, which says the 2024-25 edition moved production down 434 and the
consumption total "-434.8 in step" - i.e. together, which is why they still close.
Supply and consumption are therefore not two measurements that happen to agree.
Consumption is apparent consumption, constructed from supply, carrying no stock change and
no statistical residual of its own.

SECOND, WHAT THAT MEANS FOR THE SPLIT, AND OVER WHICH YEARS. It does NOT mean the columns
always trade against each other: across the whole held span the total grew 17,436 kt, because
there was almost no coal power in 2010, and a redistribution claim would be false there. It
is the recent window that is constrained. Over FY2019-20 to FY2023-24 the total moved -438 kt
- 1.7 per cent of the opening total, and 5.3 per cent of the swing inside it - while power's
column gained 8,299 and brick kilns plus cement lost 8,739. There almost every tonne the power
sector gained had to come out of another column, and the
brick column's 81 per cent fall - 8,184 to 1,564 kt - happens inside that constraint, over
exactly the years the Thar fleet ramped. The product emits both windows so the claim carries
its own scope.

THIRD, THE BOOKED COLUMN AGAINST THE FLEET'S OWN EVIDENCE. The brick fleet was counted
twice, in Punjab: 10,394 kilns in November 2020 on one reading and the July 2023 census on the
other. A count is compared with the booked national column only in the fiscal year it was made,
scaled to national by the Punjab kiln-count share (since rc68; until then both counts were
carried into every year and set, Punjab-only, against the national column). In FY2020-21 the
booked 8,678 kt sits inside the fleet's conditional range; in FY2023-24 the booked 1,129 kt is
below the low case of 3,571 kt by about two thirds. In the other years nothing is compared,
because nothing was counted.

Read in kilns, at the survey's own 328.2 tonnes of coal per kiln-year, the booked column
supports about 2.2 times the counted fleet in FY2020-21 and about 0.3 times it in FY2023-24.
A fleet that size cannot have shrunk by that factor in three years, so at least one end of the
booked series is not a count of kilns burning coal.

WHAT THIS DOES NOT ESTABLISH. It does not say what brick coal was, and it does not license
swapping the fleet estimate into the books - the fleet has no time axis at all, which is why
the repository declared it unbooked in the first place. Nor does it say HDIP is wrong: an
apparent-consumption series is a legitimate national statistic and the only one published.
What it establishes is that the booked brick series cannot be read as evidence about brick
activity, that its decline is not independent of the power sector's growth, and that by the
reference year it falls outside the only independent bound the repository holds.

Usage:  python3 -m pkinv.sectors.industry.coal_allocation_identity [--check]
Writes: outputs/pakemis_coal_allocation_identity.csv
"""
import argparse
import collections
import csv
import io
import os

from pkinv.assets import asset_path
from pkinv.core.io import read_rows, write_table
from pkinv.paths import DATA, OUTPUTS

OUT = asset_path(OUTPUTS, "pakemis_coal_allocation_identity.csv")

# The fleet product's own low-basis figure: ICIMOD's 440-kiln 2020 survey, tonnes of coal
# per kiln-year. Used here only to express the booked column in kilns, which is the
# comparison the fleet count makes possible.
ICIMOD_T_PER_KILN_YEAR = 328.2

CONSUMERS = ("power", "brick_kilns", "cement", "household", "other_govt")

FIELDS = ("period_id", "row_kind", "subject", "coal_imports_kt", "coal_production_kt",
          "supply_kt", "consumption_kt", "supply_minus_consumption_kt", "value_kt",
          "share_of_total_pct", "fleet_low_kt", "fleet_high_kt", "fleet_kilns",
          "implied_firing_kiln_years", "implied_over_counted_fleet", "verdict")

BANNER = """\
# HDIP'S COAL CONSUMPTION IS ITS COAL SUPPLY, AND THE CONSUMER SPLIT IS A REDISTRIBUTION
#
# row_kind=balance       supply (imports + production) against the consumer columns summed.
#                        It closes to 0 kt, which is the point: consumption is APPARENT
#                        consumption, constructed from supply, carrying no stock change.
# row_kind=allocation    one row per consumer per year, with its share of the fixed total.
# row_kind=redistribution  what each consumer gained or lost over the whole panel, beside
#                        how little the total moved.
# row_kind=brick_bound   the booked brick column against the brick fleet's own coal bounds
#                        (counted once in late 2020, two declared firing seasons), and the
#                        firing kiln-years the booked column implies at the survey's own
#                        328.2 t per kiln-year.
#
# The industrial module BOOKS the brick and cement columns. This corrects nothing: the fleet
# evidence has no time axis, which is why it was declared unbooked, and an apparent-
# consumption series is the only national coal statistic published. See the module docstring.
"""


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def build():
    supply = {r["fiscal_year"]: r for r in
              read_rows(asset_path(DATA, "activity", "industry", "coal_supply.csv"))
              if r["period_coverage"] == "full_year" and r["revision_status"] in ("final", "provisional")}
    # THE VINTAGE FILTER IS NOT OPTIONAL, and the supply reader above already has one.
    # coal_by_consumer.csv deliberately RETAINS superseded prints (its own banner: FY2023-24
    # brick kilns "1,564 kt provisional -> 1,129 kt final; the superseded provisional row is
    # retained below with revision_status=superseded_provisional"). Those rows sit AFTER the
    # final ones, so an unfiltered dict assignment is last-write-wins and silently published
    # the superseded print: FY2023-24 brick kilns 1,564 instead of 1,129, every share on a
    # 25,153 denominator instead of 24,718, and a -434 kt balance residual that contradicted
    # this module's own documented invariant that the two tables close to 0. Accepted
    # statuses match solid_fuels.py: final and provisional, never superseded.
    cons = collections.defaultdict(dict)
    for r in read_rows(asset_path(DATA, "activity", "industry", "coal_by_consumer.csv")):
        if r["coal_kt"] and r["revision_status"] in ("final", "provisional"):
            cons[r["fiscal_year"]][r["consumer"]] = float(r["coal_kt"])

    # A DATED COUNT, COMPARED ONLY IN ITS OWN PERIOD AND AT NATIONAL SCOPE (rc68). Through rc67
    # every period of the fleet-by-year product was read here, including the periods it marks
    # "carried from 2020-11 - the fleet was counted once and this period is not that year",
    # and the Punjab-only fleet was set against the NATIONAL booked column. That turned one
    # count into an annual series and mixed two geographic scopes. The carried periods are a
    # spatial frame, not activity; only the observation's own period is compared, scaled to
    # national by the declared Punjab kiln-count share (the same scale-out as the cases).
    from pkinv.sectors.industry.coal_reallocation import PUNJAB_KILN_SHARE
    fleet_bounds = collections.defaultdict(lambda: collections.defaultdict(
        lambda: [0.0, 0.0, 0.0]))
    for r in read_rows(asset_path(OUTPUTS, "pakemis_brick_kiln_fleet_by_year.csv")):
        if not r["year_basis"].startswith("the observation's OWN period"):
            continue
        acc = fleet_bounds[r["period_id"]][r["reading"]]
        acc[0] += (_num(r["coal_kt_low"]) or 0.0) / PUNJAB_KILN_SHARE
        acc[1] += (_num(r["coal_kt_high"]) or 0.0) / PUNJAB_KILN_SHARE
        acc[2] += (_num(r["kilns_total"]) or 0.0) / PUNJAB_KILN_SHARE

    years = sorted(y for y in supply if y in cons and "total" in cons[y])
    rows = []

    for y in years:
        period = "FY" + y
        s = supply[y]
        imp = _num(s["coal_imports_kt"]) or 0.0
        prod = _num(s["coal_production_kt_petroleum_division"]) or 0.0
        tot_sup = imp + prod
        tot_con = cons[y]["total"]
        resid = tot_sup - tot_con
        rows.append({
            "period_id": period, "row_kind": "balance",
            "subject": "HDIP supply against HDIP consumption",
            "coal_imports_kt": "%.0f" % imp, "coal_production_kt": "%.0f" % prod,
            "supply_kt": "%.0f" % tot_sup, "consumption_kt": "%.0f" % tot_con,
            "supply_minus_consumption_kt": "%.0f" % resid,
            "value_kt": "", "share_of_total_pct": "",
            "fleet_low_kt": "", "fleet_high_kt": "", "fleet_kilns": "",
            "implied_firing_kiln_years": "", "implied_over_counted_fleet": "",
            "verdict": ("closes to %+.0f kt (%+.2f%%): consumption is constructed from "
                        "supply, not measured against it"
                        % (resid, 100 * resid / tot_sup)),
        })

    for y in years:
        period = "FY" + y
        tot = cons[y]["total"]
        for c in CONSUMERS:
            v = cons[y].get(c)
            if v is None:
                continue
            rows.append({
                "period_id": period, "row_kind": "allocation", "subject": c,
                "coal_imports_kt": "", "coal_production_kt": "", "supply_kt": "",
                "consumption_kt": "", "supply_minus_consumption_kt": "",
                "value_kt": "%.0f" % v,
                "share_of_total_pct": "%.1f" % (100 * v / tot),
                "fleet_low_kt": "", "fleet_high_kt": "", "fleet_kilns": "",
                "implied_firing_kiln_years": "", "implied_over_counted_fleet": "",
                "verdict": "",
            })

    # TWO WINDOWS, and the difference between them matters. Over the whole held span the
    # total GREW - there was almost no coal power in 2010 - so a redistribution claim is
    # false there. It is the recent window, over which the total is flat to 4 kt, where
    # every tonne the power column gains has to come out of another column. Both are
    # emitted so the claim carries its own scope.
    windows = [(years[0], years[-1])]
    recent = [y for y in years if y >= "2019-20"]
    if len(recent) >= 2:
        windows.append((recent[0], recent[-1]))
    if "2023-24" in cons:
        # Retain the reviewed reference windows beside the extended endpoints;
        # a new year must not silently erase the historical comparison.
        windows.append((years[0], "2023-24"))
        if "2019-20" in cons:
            windows.append(("2019-20", "2023-24"))
    windows = list(dict.fromkeys(windows))
    for first, last in windows:
        span = "FY%s..FY%s" % (first, last)
        tot_delta = cons[last]["total"] - cons[first]["total"]
        flat = abs(tot_delta) < 0.01 * cons[first]["total"]
        for c in CONSUMERS + ("total",):
            a, b = cons[first].get(c), cons[last].get(c)
            if a is None or b is None:
                continue
            rows.append({
                "period_id": span, "row_kind": "redistribution",
                "subject": c, "coal_imports_kt": "", "coal_production_kt": "",
                "supply_kt": "", "consumption_kt": "",
                "supply_minus_consumption_kt": "%+.0f" % tot_delta,
                "value_kt": "%+.0f" % (b - a),
                "share_of_total_pct": "%+.1f" % (100 * (b / a - 1)) if a else "",
                "fleet_low_kt": "", "fleet_high_kt": "", "fleet_kilns": "",
                "implied_firing_kiln_years": "", "implied_over_counted_fleet": "",
                "verdict": ("%+.0f kt; the total moved %+.0f kt over this window, which is "
                            "%s, so the columns %s"
                            % (b - a, tot_delta,
                               "FLAT" if flat else "not flat",
                               "trade against each other" if flat
                               else "are not constrained to trade")),
            })

    for period in sorted(fleet_bounds):
        y = period.replace("FY", "")
        from pkinv.sectors.industry import solid_fuels
        try:
            booked = solid_fuels.coal_kt(y, "brick_kilns")
        except KeyError:
            booked = None
        for reading, (lo, hi, kilns) in sorted(fleet_bounds[period].items()):
            implied = (booked * 1000.0 / ICIMOD_T_PER_KILN_YEAR) if booked else None
            if booked is None:
                where = "the booked column has no value for this period"
            elif booked < lo:
                where = ("BELOW conditional fleet case by %.0f kt (%.0f%% of it); no annual physical floor"
                         % (lo - booked, 100 * booked / lo))
            elif booked > hi:
                where = "ABOVE conditional fleet case by %.0f kt; no annual physical ceiling" % (booked - hi)
            else:
                where = "inside the conditional fleet range; activity/operating status are not observed annually"
            rows.append({
                "period_id": period, "row_kind": "brick_bound", "subject": reading,
                "coal_imports_kt": "", "coal_production_kt": "", "supply_kt": "",
                "consumption_kt": "", "supply_minus_consumption_kt": "",
                "value_kt": "%.0f" % booked if booked else "",
                "share_of_total_pct": "",
                "fleet_low_kt": "%.0f" % lo, "fleet_high_kt": "%.0f" % hi,
                "fleet_kilns": "%.0f" % kilns,
                "implied_firing_kiln_years": "%.0f" % implied if implied else "",
                "implied_over_counted_fleet":
                    "%.2f" % (implied / kilns) if implied and kilns else "",
                "verdict": where,
            })
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="verify the shipped file matches a fresh build; write nothing")
    args = ap.parse_args(argv)
    rows = build()
    if args.check:
        if not os.path.exists(OUT):
            raise SystemExit("%s does not exist" % OUT)
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
        if io.open(OUT, encoding="utf-8").read() != BANNER + buf.getvalue():
            raise SystemExit("%s differs from a fresh build" % OUT)
        print("%s: current" % OUT)
        return
    write_table(OUT, FIELDS, rows, banner=BANNER.splitlines())
    bal = [r for r in rows if r["row_kind"] == "balance"]
    print("Coal allocation identity -> %s (%d rows)" % (OUT, len(rows)))
    print("  HDIP supply minus consumption, kt: %s"
          % ", ".join("%s %s" % (r["period_id"], r["supply_minus_consumption_kt"])
                      for r in bal))
    for r in rows:
        if r["row_kind"] == "redistribution" and r["subject"] in (
                "power", "brick_kilns", "cement", "total"):
            print("  %-12s %s" % (r["subject"], r["value_kt"]))
    out = [r for r in rows if r["row_kind"] == "brick_bound"
           and r["verdict"].startswith("BELOW")]
    print("  brick column below the fleet's low bound in %d period-readings"
          % len(out))


if __name__ == "__main__":
    main()
