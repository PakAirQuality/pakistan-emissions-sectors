"""Uncapped, distribution-explicit uncertainty for the fugitive method ladder."""
from __future__ import annotations

import math
import os
import random
from collections import defaultdict

from pkinv.core.components import co2e_Mt
from pkinv.core.montecarlo import percentile
from pkinv.sectors.fugitives import leakage, segment_inventory

N_ITER = 10000
SEED = 42


def _summary(samples):
    ordered = sorted(samples)
    return {
        "mean": sum(ordered) / len(ordered),
        "p025": percentile(ordered, 0.025),
        "p50": percentile(ordered, 0.50),
        "p975": percentile(ordered, 0.975),
        "minimum": ordered[0],
        "maximum": ordered[-1],
    }


def legacy_loguniform(data, year=2020, n_iter=N_ITER, seed=SEED):
    """One bounded log-uniform EF draw per physical 2006 stream."""
    rng = random.Random(seed)
    samples = []
    for _ in range(n_iter):
        total = 0.0
        quantiles = {stream: rng.random() for stream, _gas, _item, _fuel in leakage.STREAMS}
        for stream, gas, item, fuel in leakage.STREAMS:
            lo, hi = leakage.bounds(data, fuel, item)
            # CH4/CO2/N2O rows for one physical stream share a location within their
            # published ranges. Splitting gases must not manufacture independence.
            q = quantiles[stream]
            factor = math.exp(math.log(lo) + q * (math.log(hi) - math.log(lo)))
            emissions = leakage.activity(data, fuel, year) * factor
            total += co2e_Mt(gas, emissions, "AR5", fossil=(gas == "CH4"))
        samples.append(total)
    result = _summary(samples)
    result.update({"method": "legacy_2006", "distribution": "bounded log-uniform",
                   "year": int(year), "n_iter": n_iter, "seed": seed})
    return result, samples


def _split_triangular_from_u(u, low_pct, high_pct):
    """Inverse CDF of two half-triangles meeting at the reported value.

    Exactly half of the probability lies on each side, so 1 is the median and mode.
    IPCC uncertainty limits are treated as bounded expert ranges, not fitted 95% intervals.
    """
    low = max(0.0, 1.0 - low_pct / 100.0)
    high = 1.0 + high_pct / 100.0
    if u < 0.5:
        return low + (1.0 - low) * math.sqrt(2.0 * u)
    return high - (high - 1.0) * math.sqrt(2.0 * (1.0 - u))


def _multiplier_from_u(u, low_pct, high_pct, distribution):
    low = max(0.0, 1.0 - low_pct / 100.0)
    high = 1.0 + high_pct / 100.0
    if distribution == "bounded_split_triangular":
        return _split_triangular_from_u(u, low_pct, high_pct)
    if distribution == "bounded_uniform":
        return low + u * (high - low)
    if distribution == "bounded_loguniform_positive":
        # A logarithmic distribution is undefined at zero. Zero-bounded inputs use
        # the same bounded-uniform alternative and are disclosed in the registry.
        if low <= 0.0:
            return low + u * (high - low)
        return math.exp(math.log(low) + u * (math.log(high) - math.log(low)))
    raise ValueError("unknown 2019 uncertainty distribution %r" % distribution)


def _draw_multiplier(rng, low_pct, high_pct, distribution):
    return _multiplier_from_u(rng.random(), low_pct, high_pct, distribution)


def _activity_uncertainty_structure(ledger):
    """Decompose reused control totals into shared base and proxy residual errors."""
    by_activity = {}
    by_group = defaultdict(list)
    for row in ledger:
        if row["activity_id"] not in by_activity:
            by_activity[row["activity_id"]] = row
            by_group[row["activity_corr_group"]].append(row)
    group_base = {}
    for group, rows in by_group.items():
        # Reused production controls share the smallest source uncertainty. Larger
        # gathering/processing ranges retain an independent coverage residual.
        group_base[group] = (
            min(row["activity_uncertainty_low_pct"] for row in rows),
            min(row["activity_uncertainty_high_pct"] for row in rows),
        )
    return by_activity, by_group, group_base


def uncertainty_input_rows(data, scenario="reference", year=None,
                           distribution="bounded_split_triangular"):
    """Complete, source-traceable parametric input register."""
    ledger = segment_inventory.inventory_rows(data, scenario, year=year)
    by_activity, _by_group, group_base = _activity_uncertainty_structure(ledger)
    rows = []
    for activity_id, row in by_activity.items():
        low = row["activity_uncertainty_low_pct"]
        high = row["activity_uncertainty_high_pct"]
        group = row["activity_corr_group"]
        base_low, base_high = group_base[group]
        rows.append({
            "input_id": "activity:" + activity_id,
            "input_type": "activity",
            "central_value": row["activity_value"],
            "lower_bound": max(0.0, row["activity_value"] * (1.0 - low / 100.0)),
            "upper_bound": row["activity_value"] * (1.0 + high / 100.0),
            "unit": row["activity_unit"],
            "distribution": distribution,
            "source": row["activity_source"],
            "correlation_group": group,
            "shared_base_low_pct": base_low,
            "shared_base_high_pct": base_high,
            "applies_to": row["subitem"],
            "bounds_interpretation": ("source/proxy range; shared source error plus independent "
                                      "coverage residual where the row range is wider"),
            "zero_bound_loguniform_fallback": (
                distribution == "bounded_loguniform_positive" and
                max(0.0, row["activity_value"] * (1.0 - low / 100.0)) == 0.0),
        })
    for row in ledger:
        rows.append({
            "input_id": "factor:" + row["factor_id"],
            "input_type": "emission factor",
            "central_value": row["factor_value"],
            "lower_bound": max(0.0, row["factor_value"] *
                               (1.0 - row["factor_uncertainty_low_pct"] / 100.0)),
            "upper_bound": row["factor_value"] *
                           (1.0 + row["factor_uncertainty_high_pct"] / 100.0),
            "unit": row["factor_unit"],
            "distribution": distribution,
            "source": row["factor_source"],
            "correlation_group": "factor:" + row["factor_corr_group"],
            "shared_base_low_pct": row["factor_uncertainty_low_pct"],
            "shared_base_high_pct": row["factor_uncertainty_high_pct"],
            "applies_to": "%s %s" % (row["subitem"], row["gas"]),
            "bounds_interpretation": ("IPCC table uncertainty range/expert range; not assumed "
                                      "to be a fitted confidence interval"),
            "zero_bound_loguniform_fallback": (
                distribution == "bounded_loguniform_positive" and
                max(0.0, row["factor_value"] *
                    (1.0 - row["factor_uncertainty_low_pct"] / 100.0)) == 0.0),
        })
    return rows


def _rank(values):
    order = sorted(range(len(values)), key=lambda index: values[index])
    output = [0.0] * len(values)
    for rank, index in enumerate(order, 1):
        output[index] = float(rank)
    return output


def _correlation(xs, ys):
    xbar, ybar = sum(xs) / len(xs), sum(ys) / len(ys)
    numerator = sum((x - xbar) * (y - ybar) for x, y in zip(xs, ys))
    denominator = math.sqrt(sum((x - xbar) ** 2 for x in xs) *
                            sum((y - ybar) ** 2 for y in ys))
    return numerator / denominator if denominator else 0.0


def refinement_analysis(data, scenario="reference", n_iter=N_ITER, seed=SEED, year=None,
                        distribution="bounded_split_triangular",
                        return_inputs=False, return_native=False, parameter_draws=None):
    """Conditional Monte Carlo plus a transparent rank-sensitivity diagnostic."""
    config = segment_inventory.configuration(scenario)
    ledger = segment_inventory.inventory_rows(data, config, year=year)
    by_activity, by_group, group_base = _activity_uncertainty_structure(ledger)
    rng = random.Random(seed)
    total_samples = []
    segment_samples = {row["subitem"]: [] for row in ledger}
    input_samples = defaultdict(list)
    native = {}
    uniforms = {}
    if parameter_draws is not None:
        from pkinv.core.shared_parameter_draws import rng_for
        def uniform(identity, kind):
            key = parameter_draws.identity(identity, kind, year or data.year)
            if key not in uniforms:
                uniforms[key] = rng_for(key, seed).random(n_iter)
            return uniforms[key]
    for iteration in range(n_iter):
        group_u = {group: (rng.random() if parameter_draws is None else
                          uniform("activity:fugitives:" + group, "activity")[iteration])
                   for group in by_group}
        activities = {}
        for activity_id, row in by_activity.items():
            group = row["activity_corr_group"]
            base_low, base_high = group_base[group]
            base = _multiplier_from_u(group_u[group], base_low, base_high, distribution)
            input_samples["activity-source:" + group].append(base)
            low = row["activity_uncertainty_low_pct"]
            high = row["activity_uncertainty_high_pct"]
            residual_low = math.sqrt(max(0.0, low ** 2 - base_low ** 2))
            residual_high = math.sqrt(max(0.0, high ** 2 - base_high ** 2))
            residual = 1.0
            if residual_low or residual_high:
                residual = (_draw_multiplier(rng, residual_low, residual_high, distribution)
                            if parameter_draws is None else _multiplier_from_u(
                                uniform("activity:fugitives:residual:" + activity_id, "activity")[iteration],
                                residual_low, residual_high, distribution))
                input_samples["activity-residual:" + activity_id].append(residual)
            activities[activity_id] = row["activity_value"] * base * residual

        factor_u = {row["factor_corr_group"]: (rng.random() if parameter_draws is None else
                     uniform("factor:fugitives:" + row["factor_corr_group"], "factor")[iteration])
                    for row in ledger}
        if return_native:
            for activity_id, quantity in activities.items():
                central = by_activity[activity_id]["activity_value"]
                multiplier = quantity / central if central else 1.0
                native.setdefault("activity:" + activity_id, []).append(multiplier)
        for group, value in factor_u.items():
            input_samples["factor:" + group].append(value)

        segment_iter = {key: 0.0 for key in segment_samples}
        native_iter = defaultdict(float)
        for row in ledger:
            factor = row["factor_value"] * _multiplier_from_u(
                factor_u[row["factor_corr_group"]],
                row["factor_uncertainty_low_pct"],
                row["factor_uncertainty_high_pct"], distribution)
            emissions_Gg = (activities[row["activity_id"]] * factor *
                            row["structural_multiplier"] / 1000.0)
            if return_native:
                native_iter[row["subitem"] + "|" + row["gas"]] += emissions_Gg
            segment_iter[row["subitem"]] += co2e_Mt(
                row["gas"], emissions_Gg, "AR5", fossil=(row["gas"] == "CH4"))
        for key, value in segment_iter.items():
            segment_samples[key].append(value)
        for key, value in native_iter.items():
            native.setdefault(key, []).append(value)
        total_samples.append(sum(segment_iter.values()))

    stats = {key: _summary(values) for key, values in segment_samples.items()}
    stats["TOTAL"] = _summary(total_samples)
    for value in stats.values():
        value.update({"method": "ipcc_2019", "scenario": config.name,
                      "distribution": distribution, "n_iter": n_iter,
                      "seed": seed})

    total_ranks = _rank(total_samples)
    sensitivity = []
    squared_sum = 0.0
    for input_id, samples in input_samples.items():
        # A source group may have been appended once for every member. Retain one value
        # per iteration; within an iteration the duplicates are identical.
        if len(samples) != n_iter:
            group_size = len(samples) // n_iter
            samples = [samples[index * group_size] for index in range(n_iter)]
        rho = _correlation(_rank(samples), total_ranks)
        squared_sum += rho * rho
        sensitivity.append({"input_group": input_id, "spearman_r": rho,
                            "squared_spearman": rho * rho})
    for row in sensitivity:
        row["normalized_squared_spearman_pct"] = (
            100.0 * row["squared_spearman"] / squared_sum if squared_sum else 0.0)
        row["interpretation"] = ("rank-based sensitivity share; normalized squared "
                                 "correlations are diagnostic, not an exact Sobol decomposition")
    sensitivity.sort(key=lambda row: row["normalized_squared_spearman_pct"], reverse=True)
    if return_native:
        return stats, total_samples, sensitivity, native, dict(input_samples)
    if return_inputs:
        # Wave 6 (per-draw gas): the caller that persists the draw file needs the
        # factor groups' uniform streams to re-express one factor's multiplier per
        # draw. Returning them is a read, not a re-draw - the RNG order is untouched
        # and every existing caller's three-tuple is unchanged.
        return stats, total_samples, sensitivity, dict(input_samples)
    return stats, total_samples, sensitivity


def write_draw_file(data=None, n_iter=100000, seed=SEED):
    """Persist the bounded split-triangular engine's draws for the national pool (rc12).

    The sector loop draws one strictly sequential Random(seed) stream, so a
    100,000-draw run's first 10,000 draws are bit-identical to the published
    10,000-draw analysis - the prefix a test asserts, and the reason a future
    reordering of the loop would be caught rather than silently reshuffling the
    national row. The module is one national category, so the file carries that
    column plus an identical MODULE_TOTAL.
    """
    from pkinv.core import mc_draws
    from pkinv.sectors.fugitives.data import FugitivesData
    from pkinv.sectors.fugitives import engine, leakage
    base = data or FugitivesData()
    _stats, total_samples, _sens, inputs = refinement_analysis(
        base, n_iter=n_iter, seed=seed, return_inputs=True)
    det = sum(c["co2e_Mt_AR5"] for c in engine.build_components(base))
    # Wave 6 (per-draw gas): the post-meter industrial factor's per-draw multiplier,
    # re-expressed from its recorded uniform stream. The combustion sectors book gas
    # NET of the leak share this factor sets, and until this column existed the
    # share was FIXED across national draws while fugitives drew the same factor
    # +/-60% - the physical-atmosphere identity held at the mean and in no single
    # realisation. uncertainty_all.gas_coupling_scalers consumes it; the column is
    # deterministic given the same seed, so the 10k prefix property is untouched.
    pm_u = inputs["factor:post_meter_industrial"]
    pm_mult = [_multiplier_from_u(u, 60.0, 60.0, "bounded_split_triangular")
               for u in pm_u]
    columns = {leakage.CATEGORY: total_samples, "MODULE_TOTAL": list(total_samples),
               "POST_METER_INDUSTRIAL_MULTIPLIER": pm_mult}
    path, meta = mc_draws.write("fugitives_bounded", columns, {
        "seed": seed, "n_iter": n_iter,
        "engine": "pkinv.sectors.fugitives.uncertainty.refinement_analysis",
        "distribution_id": "bounded_split_triangular",
        "deterministic": {c: (1.0 if c == "POST_METER_INDUSTRIAL_MULTIPLIER"
                              else det) for c in columns},
        "note": "reference configuration; first 10000 draws bit-identical to the "
                "published sector analysis (sequential seed-42 stream)",
    })
    print("fugitives draw file -> %s (%d draws, seed %d, sha256 %s...)"
          % (os.path.basename(path), n_iter, seed, meta["sha256"][:12]))
    return path


def refinement_monte_carlo(data, scenario="reference", n_iter=N_ITER, seed=SEED, year=None,
                           distribution="bounded_split_triangular"):
    """Compatibility wrapper returning summary statistics and total samples."""
    stats, total_samples, _sensitivity = refinement_analysis(
        data, scenario=scenario, n_iter=n_iter, seed=seed, year=year,
        distribution=distribution)
    return stats, total_samples


def conditional_interval_rows(data, configurations, n_iter=N_ITER, seed=SEED, year=None):
    """Parametric intervals conditional on selected discrete structural models."""
    output = []
    for config in configurations:
        resolved = segment_inventory.configuration(config)
        stats, _samples, _sensitivity = refinement_analysis(
            data, scenario=resolved, n_iter=n_iter, seed=seed, year=year)
        deterministic = sum(
            co2e_Mt(row["gas"], row["emissions_Gg"], "AR5", fossil=(row["gas"] == "CH4"))
            for row in segment_inventory.inventory_rows(data, resolved, year=year))
        output.append({
            **resolved.as_dict(),
            "deterministic_mt_co2e_ar5": deterministic,
            "mc_mean_mt_co2e_ar5": stats["TOTAL"]["mean"],
            "mc_p025_mt_co2e_ar5": stats["TOTAL"]["p025"],
            "mc_p50_mt_co2e_ar5": stats["TOTAL"]["p50"],
            "mc_p975_mt_co2e_ar5": stats["TOTAL"]["p975"],
            "distribution": "bounded_split_triangular",
            "n_iter": n_iter,
            "seed": seed,
            "interpretation": "conditional parametric interval; no structural probability",
        })
    return output


def distribution_shape_rows(data, scenario="reference", n_iter=N_ITER, seed=SEED,
                            year=None):
    """Test whether the conditional interval is driven by distributional shape."""
    output = []
    for distribution in ("bounded_split_triangular", "bounded_uniform",
                         "bounded_loguniform_positive"):
        stats, _samples, _sensitivity = refinement_analysis(
            data, scenario=scenario, n_iter=n_iter, seed=seed, year=year,
            distribution=distribution)
        total = stats["TOTAL"]
        output.append({
            "scenario": segment_inventory.configuration(scenario).name,
            "distribution": distribution,
            "mean_mt_co2e_ar5": total["mean"],
            "p025_mt_co2e_ar5": total["p025"],
            "p50_mt_co2e_ar5": total["p50"],
            "p975_mt_co2e_ar5": total["p975"],
            "n_iter": n_iter,
            "seed": seed,
            "zero_bound_treatment": (
                "not applicable" if distribution != "bounded_loguniform_positive"
                else "bounded uniform for inputs whose lower bound is zero"),
        })
    return output


if __name__ == "__main__":
    import sys
    if "draws" in sys.argv[1:]:
        # The national draw-file stage (rc12): deterministic, seeded, ~a minute.
        raise SystemExit(0 if write_draw_file() else 1)
    raise SystemExit("usage: python3 -m pkinv.sectors.fugitives.uncertainty draws")
