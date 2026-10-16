"""Structural sensitivities and separately typed inventory comparisons.

Structural cases rank deterministic consequences within their named assumptions.
Signed comparator-minus-estimate differences identify activity, factor, coverage
and period questions; their absolute sizes order those questions, not missing
emissions. Comparators without a common engine metric remain unmatched context.
None of these quantities establishes a floor, upper bound or distribution for
unestimated sources. The coverage registers retain their notation statuses.

Usage: python3 -m pkinv.report.priority_rankings
Writes: outputs/national_priority_rankings.csv
"""

from pkinv.assets import asset_path
import csv
import os

from pkinv.paths import OUTPUTS
from pkinv.activity.store import read_rows

# Comparator rows that describe the whole inventory rather than one missing piece; a
# coverage RANKING is about pieces.
COVERAGE_SKIP_NAMES = ("NATIONAL", "TOTAL", "transport", "waste",
                       "Fugitive emissions from oil and gas")


def _rows(name):
    return read_rows(asset_path(OUTPUTS, name), comments=False)


def build():
    out = []

    # 2026-10-07, AND THIS CHANGED THE TOP OF THE RANKING. The power coal-energy basis led
    # this list at 19.4 Mt for every release up to the coal re-base. The re-base BOOKED the
    # station account, so what remains of that fork is (a) the heat-rate route, 1.59 Mt from
    # the reference, which stays in the ranking where it now belongs, and (b) NEPRA Table 3's
    # published conversion at 17.78 Mt, which is excluded by the rule below because its own
    # registry note declares it not equally probable with the reference - it is a REFUTED
    # account retained as a control, not an unresolved choice. The question this ranking
    # answers is "which unresolved model choice most moves the deterministic total", and an
    # account that failed a physical audit is not a candidate answer to it. The consequence
    # is that the sewer methane correction factor now leads at 9.07 Mt, and the abstract says
    # so rather than quoting a number the re-base retired.
    #
    # Endpoint-statement axes are excluded from the STRUCTURAL ranking: the
    # wastewater effluent-EF axis prices a published range's CEILING (+148.6 Mt),
    # which its own note declares NOT equally probable with the reference - ranking
    # it beside co-equal readings of evidence would let one deliberate extreme
    # dominate the "which unresolved model choice" question.
    #
    # THE SECOND HALF OF THAT ARGUMENT USED TO BE FALSE. It said "the endpoint's
    # leverage is not hidden: it leads the PARAMETRIC ranking through the bounded
    # factor". It does not lead it and is not in it: the published parametric top five
    # is ef:enteric_buffalo 0.258, livestock:buffalo 0.067, ef:enteric_other_cattle
    # 0.066, waste:ww_mcf_sewer 0.057 and ef:enteric_dairy_cattle 0.054, and
    # waste:ww_ef_effluent sits sixth at 0.049. So an axis excluded from one ranking
    # was justified by a claim about its standing in the other, and that claim did not
    # hold - the exclusion rests on the first half alone, which is enough.
    #
    # Where the factor's leverage IS visible, and this is the honest pointer: the
    # sector's own bounded-draw percentiles and outputs/national_structural_bridge.csv,
    # which prices the endpoint at +148.6 Mt beside the reference rather than inside
    # it. The waste paper reports it sixth in the parametric ranking at 401 per cent
    # declared width, which is also where a reader should be sent.
    axes = [r for r in _rows("national_structural_bridge.csv")
            if "not equally probable" not in r["note"].lower()]
    axes.sort(key=lambda r: -abs(float(r["national_delta_Mt_co2e"] or 0.0)))
    for rank, r in enumerate(axes, 1):
        out.append({
            "ranking": "structural", "rank": rank, "name": r["axis"],
            "metric": abs(float(r["national_delta_Mt_co2e"] or 0.0)),
            "unit": "Mt CO2e (AR5), |deterministic delta|",
            "question": "which unresolved model choice most moves the deterministic total",
            "source_output": "national_structural_bridge.csv",
            "note": r["note"]})

    comparisons, unmatched = [], []
    for r in _rows("national_benchmark_comparison.csv"):
        if r["comparison_role"] not in ("coverage", "diagnostic"):
            continue
        if r["engine_category"] in COVERAGE_SKIP_NAMES:
            continue
        try:
            benchmark = float(r["benchmark_Mt_co2e"])
        except ValueError:
            # rc41 (D-2): a benchmark that is not a number is REPORTED, not dropped - a
            # dropped row is a gap the ranking silently forgets
            raise ValueError("national_benchmark_comparison.csv: %s / %s carries a "
                             "non-numeric benchmark %r" % (r["source"], r["engine_category"],
                                                            r["benchmark_Mt_co2e"]))
        try:
            difference = benchmark - float(r["engine_Mt_co2e"])
        except ValueError:
            # An unresolved common metric can mean a period/species mismatch,
            # not an absent category (the native-CO2 ammonia comparator is one).
            unmatched.append((benchmark, r))
            continue
        if abs(difference) <= 0.5:
            continue
        comparisons.append((difference, r))
    comparisons.sort(key=lambda t: -abs(t[0]))
    for rank, (difference, r) in enumerate(comparisons, 1):
        out.append({
            "ranking": "comparison", "rank": rank,
            "name": "%s (%s)" % (r["engine_category"], r["source"]),
            "metric": round(difference, 2), "unit": "Mt CO2e (%s), comparator minus estimated sources" % r["gwp"],
            "question": "which magnitude differences require activity, factor, coverage and period reconciliation",
            "source_output": "national_benchmark_comparison.csv",
            "note": "Signed comparison difference, not missing emissions or a bound. " + r["note"]})
    for rank, (benchmark, r) in enumerate(sorted(unmatched, key=lambda t: -abs(t[0])), 1):
        out.append({
            "ranking": "unmatched_comparator", "rank": rank,
            "name": "%s (%s)" % (r["engine_category"], r["source"]),
            "metric": benchmark, "unit": "Mt on comparator's %s basis; no common-metric difference" % r["gwp"],
            "question": "which source comparator needs a matched period, species and boundary before comparison",
            "source_output": "national_benchmark_comparison.csv",
            "note": "Comparator magnitude only; no inference of absent mass, floor or bound. " + r["note"]})
    return out


FIELDS = ("ranking", "rank", "name", "metric", "unit", "question", "source_output", "note")


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    rows = build()
    path = asset_path(OUTPUTS, "national_priority_rankings.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print("priority rankings -> %s" % path)
    for ranking in ("structural", "comparison", "unmatched_comparator"):
        top = next((r for r in rows if r["ranking"] == ranking and r["rank"] == 1), None)
        if top is None:
            continue
        print("  %-11s #1  %-46s %s %s"
              % (ranking, top["name"][:46], top["metric"], top["unit"].split(",")[0]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
