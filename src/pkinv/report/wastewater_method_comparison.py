"""Domestic wastewater nitrous oxide under the 2019 Refinement and under the 2006 Guidelines,
side by side: the estimate for every year, each method's interval, and what each does to the
national total and its upper tail.

WHY THIS EXISTS (rc67). The review asked for the 2019 Refinement to be tested coherently:
pathway-allocated nitrogen, removal, pathway factors, and a comparison of the national estimate
and its uncertainty with the implementation it would replace, not a new upper bound dropped into
the old equation. The reference now runs the Refinement (sectors/waste/wastewater.py). This
table is the comparison, and it is the place a reader checks that the choice of method was not
made on one number.

THREE SCOPES, ONE ROW PER METHOD.
  wastewater_n2o       the gas alone, every fiscal year: Gg N2O and Mt CO2e (AR5), deterministic
  wastewater_category  methane + nitrous oxide, reference year, with the parameter-rerun interval
  national_total       the national total, reference year, with its interval

THE TWO METHODS ARE COMPARED ON THE SAME DRAWS. Every parameter stream of the waste engine is
seeded by the parameter's own name, so draw d of the 2006 rerun used the random numbers draw d of
the 2019 rerun used. The national row for the alternative is therefore the released ensemble's
draw d with that draw's wastewater replaced:

    national_2006(d) = NATIONAL_TOTAL(d) - wastewater_2019(d) + wastewater_2006(d)

which is a paired difference, not two unrelated intervals. The build first checks that the
ensemble's wastewater column IS the reference draw file's prefix; if it is not, one of them is
stale and nothing is written.

WHAT DIFFERS BETWEEN THE METHODS, so the difference is not read as one factor: the 2019 method
puts nitrogen on protein consumed (x 0.96), adds household products (x 1.1), applies the
industrial factor to the sewered population only, removes a fraction by treatment type, adds
plant emissions, and draws the effluent factor over 0.0005-0.075; the 2006 method does none of
the first five and draws it over 0.0005-0.25.

upper_tail_excess_share is the part of the national upper tail a category accounts for: over the
draws in the top 2.5 per cent of the national total, the category's mean above its all-draw mean,
divided by the national total's mean above its all-draw mean.

COMPARATOR ONLY. Nothing here enters a total, a factor or an allocation.

Usage:  python3 -m pkinv.report.wastewater_method_comparison
Writes: outputs/pakemis_wastewater_method_comparison.csv
"""
import csv
import os

from pkinv.assets import asset_path
from pkinv.core.io import write_table
from pkinv.core.reporting_window import REFERENCE_PERIOD
from pkinv.paths import DATA, OUTPUTS

OUT = os.path.join(OUTPUTS, "pakemis_wastewater_method_comparison.csv")
ENSEMBLE = os.path.join(OUTPUTS, "mc_draws", "pakemis_ensemble_annual.parquet")
PERIODS = asset_path(DATA, "periods.csv")
CATEGORY = "Domestic wastewater"
METHODS = (("ipcc2019", "yes", "IPCC 2019 Refinement Vol 5 Ch 6, Eqs 6.7-6.10a"),
           ("ipcc2006", "no", "IPCC 2006 Guidelines Vol 5 Ch 6, Eqs 6.7-6.8"))
REFERENCE_DRAWS, ALTERNATIVE_DRAWS = "waste_parameter_rerun", "waste_parameter_rerun_ipcc2006"
TAIL = 0.025
PREFIX_TOLERANCE = 1e-9
N2O_GWP_AR5 = 265.0

FIELDS = ("scope", "period_id", "method", "is_reference", "method_source", "unit",
          "deterministic", "mean", "p2_5", "p50", "p97_5", "upper_tail_excess_share",
          "n_draws", "note")
WHY = ("the reference since rc67: the Refinement allocates nitrogen to the sanitation "
       "pathways the methane estimate already uses and removes what treatment removes; its "
       "own text says the 2006 equation 'does not account for the removal' of nitrogen and "
       "'can result in a significant overestimate of N discharged' (Section 6.3.1.3)")
WAS = "the reference through rc66, retained as the alternative"


def _rows(path):
    with open(path, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(line for line in handle if not line.startswith("#")))


def _percentile(ordered, q):
    from pkinv.core import montecarlo
    return montecarlo.percentile(ordered, q)


def _summary(values):
    ordered = sorted(values)
    return {"mean": sum(values) / len(values), "p2_5": _percentile(ordered, 0.025),
            "p50": _percentile(ordered, 0.5), "p97_5": _percentile(ordered, 0.975)}


def _tail_share(component, total):
    """The component's share of the national total's excess over its mean, in the top tail."""
    n = len(total)
    order = sorted(range(n), key=lambda i: total[i])
    top = order[int(round(n * (1.0 - TAIL))):]
    excess_total = sum(total[i] for i in top) / len(top) - sum(total) / n
    excess_part = sum(component[i] for i in top) / len(top) - sum(component) / n
    return excess_part / excess_total


def _ensemble():
    import pyarrow.parquet as pq
    table = pq.read_table(ENSEMBLE).to_pydict()
    order = sorted(range(len(table["draw_id"])), key=lambda i: table["draw_id"][i])
    return ([table[CATEGORY][i] for i in order], [table["NATIONAL_TOTAL"][i] for i in order])


def build():
    # imported at call time: the report layer loads no sector module on import
    from pkinv.core import mc_draws, registry
    from pkinv.sectors.waste import wastewater
    waste = registry.get("waste")
    data = waste.load_data()
    periods = sorted((int(r["fiscal_end_year"]), r["period_id"]) for r in _rows(PERIODS))
    # The paired stored draws remain tied to the detailed reference year even
    # when another annual activity year is admitted to the common core.
    reference_period = REFERENCE_PERIOD
    rows = []

    def row(scope, period, method, is_ref, source, unit, det, stats=None, tail="", n="",
            note=""):
        stats = stats or {}
        return {"scope": scope, "period_id": period, "method": method,
                "is_reference": is_ref, "method_source": source, "unit": unit,
                "deterministic": "%.5f" % det,
                "mean": "%.5f" % stats["mean"] if stats else "",
                "p2_5": "%.5f" % stats["p2_5"] if stats else "",
                "p50": "%.5f" % stats["p50"] if stats else "",
                "p97_5": "%.5f" % stats["p97_5"] if stats else "",
                "upper_tail_excess_share": "%.4f" % tail if tail != "" else "",
                "n_draws": n, "note": note}

    # 1. the gas alone, every year, both methods
    for year, period in periods:
        for method, is_ref, source in METHODS:
            gg = wastewater.n2o_gg(data, year, method=method)
            rows.append(row("wastewater_n2o", period, method, is_ref, source, "Gg N2O", gg,
                            note="%.5f Mt CO2e (AR5). %s" % (
                                gg * N2O_GWP_AR5 / 1000.0, WHY if is_ref == "yes" else WAS)))

    # 2 and 3. the reference year's intervals, paired draw by draw
    ref_cols, ref_meta = mc_draws.read(REFERENCE_DRAWS)
    alt_cols, alt_meta = mc_draws.read(ALTERNATIVE_DRAWS)
    ensemble_ww, ensemble_total = _ensemble()
    n = len(ensemble_total)
    if len(alt_cols[CATEGORY]) < n or len(ref_cols[CATEGORY]) < n:
        raise SystemExit("the draw files are shorter than the ensemble (%d draws)" % n)
    worst = max(abs(ref_cols[CATEGORY][i] - ensemble_ww[i]) for i in range(n))
    if worst > PREFIX_TOLERANCE:
        raise SystemExit(
            "the ensemble's wastewater column is not the reference draw file's prefix "
            "(largest difference %.3g Mt): one of the two is stale, rebuild both" % worst)
    ww = {"ipcc2019": [ref_cols[CATEGORY][i] for i in range(n)],
          "ipcc2006": [alt_cols[CATEGORY][i] for i in range(n)]}
    national = {"ipcc2019": list(ensemble_total),
                "ipcc2006": [ensemble_total[i] - ww["ipcc2019"][i] + ww["ipcc2006"][i]
                             for i in range(n)]}
    det_ww = {"ipcc2019": ref_meta["deterministic"][CATEGORY],
              "ipcc2006": alt_meta["deterministic"][CATEGORY]}
    reference_total = next(
        float(r["co2e_Mt_AR5"]) for r in _rows(os.path.join(OUTPUTS, "national_all_sectors.csv"))
        if r["row_kind"] == "national_total")
    det_national = {"ipcc2019": reference_total,
                    "ipcc2006": reference_total - det_ww["ipcc2019"] + det_ww["ipcc2006"]}
    for method, is_ref, source in METHODS:
        rows.append(row("wastewater_category", reference_period, method, is_ref, source,
                        "Mt CO2e AR5", det_ww[method], _summary(ww[method]),
                        _tail_share(ww[method], national[method]), n,
                        "methane + nitrous oxide; the methane is the same under both "
                        "methods. Parameter rerun, the fate ledger asserted in every draw"))
    for method, is_ref, source in METHODS:
        rows.append(row("national_total", reference_period, method, is_ref, source,
                        "Mt CO2e AR5", det_national[method], _summary(national[method]),
                        "", n,
                        "the released ensemble" if is_ref == "yes" else
                        "the released ensemble with each draw's wastewater replaced by the "
                        "2006 method's value on the same draw"))
    return rows


def main():
    rows = build()
    write_table(OUT, FIELDS, rows, banner=(
        "# Domestic wastewater nitrous oxide under the 2019 Refinement (the reference since",
        "# rc67) and the 2006 Guidelines (the reference before): the gas for every fiscal year,",
        "# and for the reference year the category's and the national total's interval under",
        "# each method, on the same draws. upper_tail_excess_share is the category's part of",
        "# the national total's excess over its mean in the top 2.5 per cent of draws.",
        "# pkinv.report.wastewater_method_comparison. COMPARATOR ONLY.",))
    by = {(r["scope"], r["method"]): r for r in rows if r["period_id"] == rows[-1]["period_id"]}
    print("wastewater method comparison: %d rows" % len(rows))
    for method in ("ipcc2019", "ipcc2006"):
        nat, cat = by[("national_total", method)], by[("wastewater_category", method)]
        print("  %s  N2O %s Gg; national %s Mt [%s, %s]; wastewater share of the upper tail %s"
              % (method, by[("wastewater_n2o", method)]["deterministic"],
                 nat["deterministic"], nat["p2_5"], nat["p97_5"],
                 cat["upper_tail_excess_share"]))


if __name__ == "__main__":
    main()
