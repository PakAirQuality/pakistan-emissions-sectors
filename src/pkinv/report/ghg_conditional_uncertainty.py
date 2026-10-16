"""Paired native-gas and GWP uncertainty conditional on a named configuration.

Nitrogen, waste fate and fugitives use their native parameter engines; power coal
uses rank heat directly. Remaining streams retain the existing parameter graph.
Structural configurations and missing categories are never sampled into intervals.
"""
import argparse
import collections
import csv
import math
import numpy as np

from pkinv.assets import asset_path
from pkinv.core import configurations as conf, gwp, parameters, registry
from pkinv.core.shared_parameter_draws import (SEED, Draws, nitrogen_realisations,
    waste_realisations, fugitives_realisations, power_coal_realisations, dung_mass_multiplier, rng_for,
    parameter_kind, residue_burning_realisations)
from pkinv.core.reporting_window import CORE_FY_ENDS, fiscal_label
from pkinv.core.io import read_rows
from pkinv.paths import OUTPUTS
from pkinv.report import annual_product

OUT = asset_path(OUTPUTS, "pakemis_ghg_conditional_uncertainty.csv")
TREND = asset_path(OUTPUTS, "pakemis_ghg_trend_uncertainty.csv")
DRIVERS = asset_path(OUTPUTS, "pakemis_ghg_uncertainty_drivers.csv")
PARAMETERS = asset_path(OUTPUTS, "pakemis_ghg_uncertainty_parameters.csv")
CASES = ("persistent_parameters", "annual_activity_errors")
LIMITATIONS = ("conditional on admitted sources, fixed process/control and management shares; "
               "unestimated categories and structural choices excluded; allocation uncertainty separate; "
               "waste management parameters persist across years; other unsigned parameter graph approximations retained")


def _stats(values):
    low, median, high = np.quantile(values, [.025, .5, .975])
    return dict(mean_quantity=float(np.mean(values)), P2_5_quantity=float(low),
                P50_quantity=float(median), P97_5_quantity=float(high))


def build(n=10000, seed=SEED, years=CORE_FY_ENDS, configurations=conf.ALL):
    context = annual_product.build_context()
    available = {(int(r["fiscal_end_year"]), r["sector"]) for r in read_rows(
        asset_path(OUTPUTS, "pakemis_national_series.csv"))
        if r["row_kind"] == "sector" and r["co2e_Mt_AR5"] not in ("", "absent")}
    levels, trends, drivers, parameter_rows = [], [], [], []
    for case in CASES:
        draws = Draws(n, case, seed)
        sums, central = {}, collections.defaultdict(float)
        native_cache = {}
        max_residual = 0.0
        for year in years:
            native_cache[(year, "waste")] = waste_realisations(year, draws)
            native_cache[(year, "fugitives")] = fugitives_realisations(year, draws)
            native_cache[(year, "coal")] = power_coal_realisations(year, draws)
            native_cache[(year, "crop_burning")] = residue_burning_realisations(year, draws)
            for method in ("tan", "ipcc"):
                values, residual = nitrogen_realisations(year, draws, method)
                native_cache[(year, method)] = values
                max_residual = max(max_residual, residual)
            for configuration in configurations:
                for sector in registry.all_sectors():
                    name = sector.NAME
                    if (year, name) not in available:
                        continue
                    components = annual_product.components_for(name, year, context,
                                                              configuration_id=configuration)
                    native, ordinary = {}, []
                    for row in components:
                        row = dict(row, _sector=name)
                        identity = "%s|%s|%s" % (row["category"], row["subitem"], row["gas"])
                        values = None
                        if (name == "agriculture" and row["gas"] == "N2O"
                                and row["category"] in ("Manure management", "Managed soils")):
                            values = native_cache[(year, conf.nitrogen_method(configuration))]["ghg:" + identity]
                        elif name == "agriculture" and row["category"] == "Field burning of residues":
                            values = native_cache[(year, "crop_burning")][row["gas"]]
                        elif name == "waste":
                            values = native_cache[(year, "waste")][identity]
                        elif name == "fugitives":
                            source = row["subitem"].removesuffix(" " + row["gas"])
                            values = native_cache[(year, "fugitives")][source + "|" + row["gas"]]
                        elif name == "power" and row["subitem"].startswith("Coal "):
                            values = native_cache[(year, "coal")][row["gas"]]
                        if values is None:
                            ordinary.append(row)
                        else:
                            native[identity] = values
                    plans = parameters.decompose(ordinary)
                    for row, shared, residual, _derived in plans:
                        identity = "%s|%s|%s" % (row["category"], row["subitem"], row["gas"])
                        log = np.zeros(n)
                        ledger_dung = (name == "residential" and row["subitem"].startswith("Dung cake ")
                                       and conf.dung_basis(configuration) == "ledger")
                        for group, sigma in shared.items():
                            if ledger_dung and (group.startswith(("livestock:", "activity:livestock:"))
                                                or group in ("1a4b_dung", "1a4b_dung_chain")):
                                continue
                            log += draws.normal(group, year) * sigma - sigma * sigma / 2
                            uncertainty = math.sqrt(math.expm1(sigma * sigma)) * 196
                            identity_g = draws.identity(group, parameter_kind(group), year)
                            draws.cache.setdefault((identity_g, uncertainty),
                                np.exp(draws.normal(group, year) * abs(sigma) - sigma * sigma / 2))
                            draws.registry.setdefault(identity_g, dict(id=identity_g, kind=parameter_kind(group),
                                uncert_pct=uncertainty,
                                distribution="mean_preserving_lognormal", evidence="existing component parameter graph"))
                        if residual:
                            suffix = ":FY%d" % year if case == "annual_activity_errors" else ""
                            z = rng_for("component_residual:" + name + ":" + identity + suffix, seed).standard_normal(n)
                            log += z * residual - residual * residual / 2
                        values = float(row["emissions_Gg"]) * np.exp(log)
                        if ledger_dung:
                            values *= dung_mass_multiplier(year, draws)
                        if row.get("net_of_leak"):
                            from pkinv.sectors.fugitives import post_meter
                            leak = post_meter.whole_gas_leak_share()
                            values *= (1 - leak * native_cache[(year, "fugitives")]["post_meter_factor_multiplier"]) / (1 - leak)
                        native[identity] = values
                    for row in components:
                        identity = "%s|%s|%s" % (row["category"], row["subitem"], row["gas"])
                        values = native[identity]
                        mass = float(row["emissions_Gg"])
                        metrics = [(row["gas"], "Gg", values, mass)]
                        for ar in ("AR5", "AR6"):
                            factor = gwp.to_co2e(row["gas"], 1., ar, fossil=row.get("fossil", False)) / 1000
                            metrics.append(("CO2e_" + ar, "Mt_CO2e", values * factor, mass * factor))
                        for metric, unit, quantity, deterministic in metrics:
                            for aggregation in (name, "national_covered"):
                                key = (year, configuration, aggregation, metric, unit)
                                sums.setdefault(key, np.zeros(n))[:] += quantity
                                central[key] += deterministic
        for key, values in sorted(sums.items()):
            year, configuration, sector, metric, unit = key
            levels.append(dict(period_id=fiscal_label(year - 1), configuration_id=configuration,
                sector_id=sector, species_or_metric=metric, unit=unit, dependence_case=case,
                deterministic_quantity=central[key], **_stats(values), draws=n, seed=seed,
                interval_kind="conditional_parameter_percentiles", limitations=LIMITATIONS,
                max_nitrogen_closure_residual_kgN=max_residual))
            if sector == "national_covered" and metric == "CO2e_AR5":
                ranked = []
                for identity, entry in draws.registry.items():
                    candidates = [v for k, v in draws.cache.items() if k[0] == identity]
                    if not candidates:
                        continue
                    x = candidates[0]
                    if np.std(x) and np.std(values):
                        rho = float(np.corrcoef(values, x)[0, 1])
                        ranked.append((rho * rho, identity, rho))
                for rank, (r2, identity, rho) in enumerate(sorted(ranked, reverse=True)[:8], 1):
                    drivers.append(dict(period_id=fiscal_label(year - 1), configuration_id=configuration,
                        dependence_case=case, rank=rank, driver_id=identity, correlation=rho,
                        squared_correlation=r2, attribution="sensitivity diagnostic; not additive variance shares"))
        groups = {(cfg, sec, metric, unit) for year, cfg, sec, metric, unit in sums}
        for cfg, sector, metric, unit in sorted(groups):
            support = sorted(year for year in years if (year, cfg, sector, metric, unit) in sums)
            pairs = list(zip(support[:-1], support[1:]))
            if len(support) > 2:
                pairs.append((support[0], support[-1]))
            for early, late in pairs:
                a, b = (early, cfg, sector, metric, unit), (late, cfg, sector, metric, unit)
                trends.append(dict(start_period=fiscal_label(early - 1), end_period=fiscal_label(late - 1),
                    configuration_id=cfg, sector_id=sector, species_or_metric=metric, unit=unit,
                    dependence_case=case, deterministic_change=central[b] - central[a],
                    **_stats(sums[b] - sums[a]), draws=n, seed=seed,
                    interval_kind="paired_change_parameter_percentiles", limitations=LIMITATIONS))
        parameter_rows.extend(dict(entry, dependence_case=case) for entry in draws.registry.values())
    return levels, trends, drivers, parameter_rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draws", type=int, default=10000)
    args = parser.parse_args()
    for path, rows in zip((OUT, TREND, DRIVERS, PARAMETERS), build(n=args.draws)):
        if not rows:
            raise ValueError("empty conditional uncertainty product " + path)
        fields = list(dict.fromkeys(key for row in rows for key in row))
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)


if __name__ == "__main__":
    main()
