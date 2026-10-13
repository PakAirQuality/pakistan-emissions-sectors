"""What drives the national uncertainty, read from the ensemble that is actually released.

WHY THIS EXISTS (rc67, the review's Priority 6). Statements about uncertainty drivers were
resting on three different things: the Approach 1 quadrature (enteric 58 per cent,
wastewater 16), a Sobol decomposition of a SURROGATE of the model (mean-preserving lognormals
in place of the engines' own draws, first-order indices summing to 1.33), and prose. The
released ensemble said something else again. A statement about what drives an interval has to
come from the distribution that produced the interval, so this module computes every driver
statement from outputs/mc_draws/pakemis_ensemble_annual.parquet: 10,000 joint draws of every
category and of the national total, on one draw_id, with the waste and fugitives engines' own
draws injected.

WHAT IS COMPUTED, and nothing more is claimed.

  variance_share            Cov(category, total) / Var(total). The categories' shares sum to
                            one EXACTLY, because the total is their sum, so this is a
                            decomposition and not a ranking heuristic. A share can be negative
                            (a category that moves against the total).
  upper_tail_excess_share   over the draws in the top 2.5 per cent of the total, the
                            category's mean above its own all-draw mean, divided by the
                            total's. What the upper end of the interval is made of. Sums to one.
  lower_tail_excess_share   the same for the bottom 2.5 per cent.
  interval_if_fixed         the national interval with that ONE category held at its
                            deterministic value in every draw: total(d) - category(d) +
                            deterministic. A conditional scenario, not a variance reduction
                            promise: it holds the category's value, not its parameters.

Rows are at two grains, category and sector (the categories of one module summed per draw),
and one further row is a PARAMETER: the wastewater effluent factor frozen at its default, from
a rerun of the waste engine on the ensemble's own streams. It is the only parameter-level
statement made, because it is the only one that can be made on the engine's own draws without
storing every sampled parameter. Parameter-level importance in general is NOT claimed; the
surrogate Sobol products that claimed it are retired.

COMPARATOR ONLY. Nothing here enters a total, a factor or an allocation.

Usage:  python3 -m pkinv.report.ensemble_drivers
Writes: outputs/pakemis_uncertainty_drivers.csv
"""
import os

from pkinv.core.io import write_table
from pkinv.paths import OUTPUTS

OUT = os.path.join(OUTPUTS, "pakemis_uncertainty_drivers.csv")
ENSEMBLE = os.path.join(OUTPUTS, "mc_draws", "pakemis_ensemble_annual.parquet")
TOTAL = "NATIONAL_TOTAL"
TAIL = 0.025
WASTEWATER = "Domestic wastewater"
FROZEN_PARAMETER = "ww_ef_effluent"
SUM_TOLERANCE = 1e-9

FIELDS = ("grain", "name", "sector", "deterministic_Mt", "mean_Mt", "sd_Mt",
          "variance_share", "upper_tail_excess_share", "lower_tail_excess_share",
          "national_p2_5_if_fixed", "national_p97_5_if_fixed", "rank_by_variance_share",
          "n_draws", "basis")


def _mean(values):
    return sum(values) / len(values)


def _cov(a, b):
    ma, mb = _mean(a), _mean(b)
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (len(a) - 1)


def _percentile(values, q):
    from pkinv.core import montecarlo
    return montecarlo.percentile(sorted(values), q)


def load():
    """({category: [draw]}, [total]) in draw_id order."""
    import pyarrow.parquet as pq
    table = pq.read_table(ENSEMBLE).to_pydict()
    order = sorted(range(len(table["draw_id"])), key=lambda i: table["draw_id"][i])
    columns = {name: [values[i] for i in order] for name, values in table.items()
               if name not in ("draw_id", TOTAL)}
    return columns, [table[TOTAL][i] for i in order]


def _sector_of():
    """{category: (module, deterministic Mt)} from the engines themselves."""
    from pkinv.core import registry
    out = {}
    for sector in registry.all_sectors():
        for c in sector.build_components(sector.load_data()):
            module, value = out.get(c["category"], (sector.NAME, 0.0))
            out[c["category"]] = (module, value + c["co2e_Mt_AR5"])
    return out


def _tails(total):
    n = len(total)
    order = sorted(range(n), key=lambda i: total[i])
    k = int(round(n * TAIL))
    return order[n - k:], order[:k]


def _row(grain, name, sector, det, draws, total, var_total, top, bottom, basis):
    excess_top = _mean([total[i] for i in top]) - _mean(total)
    excess_bottom = _mean([total[i] for i in bottom]) - _mean(total)
    fixed = [t - x + det for t, x in zip(total, draws)]
    return {"grain": grain, "name": name, "sector": sector,
            "deterministic_Mt": det, "mean_Mt": _mean(draws),
            "sd_Mt": _cov(draws, draws) ** 0.5,
            "variance_share": _cov(draws, total) / var_total,
            "upper_tail_excess_share":
                (_mean([draws[i] for i in top]) - _mean(draws)) / excess_top,
            "lower_tail_excess_share":
                (_mean([draws[i] for i in bottom]) - _mean(draws)) / excess_bottom,
            "national_p2_5_if_fixed": _percentile(fixed, 0.025),
            "national_p97_5_if_fixed": _percentile(fixed, 0.975),
            "n_draws": len(total), "basis": basis}


def _effluent_frozen(columns, total):
    """The wastewater column with the effluent factor frozen at its default in every draw:
    the waste engine rerun on the ensemble's own identity-seeded streams. Returns None,
    with the reason, if the ensemble's wastewater column is not that engine's prefix."""
    from pkinv.core import mc_draws
    from pkinv.sectors.waste import uncertainty
    n = len(total)
    reference, _meta = mc_draws.read("waste_parameter_rerun")
    worst = max(abs(reference[WASTEWATER][i] - columns[WASTEWATER][i]) for i in range(n))
    if worst > 1e-9:
        raise SystemExit("the ensemble's wastewater column is not the waste draw file's "
                         "prefix (largest difference %.3g Mt): one of the two is stale"
                         % worst)
    _out, sums, _totals = uncertainty.parameter_rerun_mc(
        n_iter=n, return_samples=True, freeze=(FROZEN_PARAMETER,))
    return sums[WASTEWATER]


def build():
    columns, total = load()
    sector_of = _sector_of()
    missing = sorted(set(columns) - set(sector_of))
    if missing:
        raise SystemExit("ensemble categories no engine produces: %s" % missing)
    var_total = _cov(total, total)
    top, bottom = _tails(total)
    rows = []
    for name, draws in columns.items():
        module, det = sector_of[name]
        rows.append(_row("category", name, module, det, draws, total, var_total, top,
                         bottom, "the released ensemble's own draws of this category"))
    for label in ("variance_share", "upper_tail_excess_share", "lower_tail_excess_share"):
        got = sum(r[label] for r in rows)
        if abs(got - 1.0) > SUM_TOLERANCE:
            raise SystemExit("category %s sums to %.12f, not one: the ensemble's total "
                             "is not the sum of its categories" % (label, got))
    for module in sorted({m for m, _d in sector_of.values()}):
        members = [n for n in columns if sector_of[n][0] == module]
        if not members:
            continue
        draws = [sum(columns[m][i] for m in members) for i in range(len(total))]
        rows.append(_row("sector", module, module,
                         sum(sector_of[m][1] for m in members), draws, total, var_total,
                         top, bottom, "this module's %d categor%s summed draw by draw"
                         % (len(members), "y" if len(members) == 1 else "ies")))

    frozen = _effluent_frozen(columns, total)
    moved = [x - f for x, f in zip(columns[WASTEWATER], frozen)]   # the factor's own part
    row = _row("parameter", "wastewater effluent N2O factor (%s)" % FROZEN_PARAMETER,
               "waste", 0.0, moved, total, var_total, top, bottom,
               "the waste engine rerun on the ensemble's own streams with this one factor "
               "frozen at its default; the row is the difference between the two "
               "wastewater columns, so its shares are the factor's own")
    row["deterministic_Mt"] = ""
    rows.append(row)

    for grain in ("category", "sector"):
        ranked = sorted((r for r in rows if r["grain"] == grain),
                        key=lambda r: -r["variance_share"])
        for rank, r in enumerate(ranked, 1):
            r["rank_by_variance_share"] = rank
    rows[-1]["rank_by_variance_share"] = ""
    order = {"sector": 0, "category": 1, "parameter": 2}
    rows.sort(key=lambda r: (order[r["grain"]], r["rank_by_variance_share"] or 0))
    for r in rows:
        for key in ("mean_Mt", "sd_Mt", "national_p2_5_if_fixed", "national_p97_5_if_fixed"):
            r[key] = "%.5f" % r[key]
        if r["deterministic_Mt"] != "":
            r["deterministic_Mt"] = "%.5f" % r["deterministic_Mt"]
        for key in ("variance_share", "upper_tail_excess_share", "lower_tail_excess_share"):
            r[key] = "%.6f" % r[key]
    return rows


def main():
    rows = build()
    _columns, total = load()
    write_table(OUT, FIELDS, rows, banner=(
        "# What drives the national uncertainty, from the released ensemble itself: each",
        "# category's and sector's share of the national variance (covariance with the total;",
        "# shares sum to one), its share of the excess in the top and bottom 2.5 per cent of",
        "# draws, and the national interval with that one category held at its deterministic",
        "# value. One parameter row: the wastewater effluent factor, frozen in a rerun of the",
        "# waste engine on the same streams. The unconditional interval is %.2f to %.2f Mt."
        % (_percentile(total, 0.025), _percentile(total, 0.975)),
        "# pkinv.report.ensemble_drivers. COMPARATOR ONLY.",))
    top = [r for r in rows if r["grain"] == "category"][:4]
    print("uncertainty drivers: %d rows from %d draws; variance: %s"
          % (len(rows), len(total), "; ".join(
              "%s %.1f%%" % (r["name"], 100 * float(r["variance_share"])) for r in top)))


if __name__ == "__main__":
    main()
