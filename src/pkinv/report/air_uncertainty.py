"""Conditional air uncertainty on shared inputs, paired across years/configurations.

Every admitted atom participates. Nitrogen emissions are regenerated from the
conserved manure/soil ledger, not independently multiplied after calculation.
The two dependence cases expose unidentified persistence of annual activity
errors. They are separate conditional models, not a mixture of probabilities.
"""
import argparse
import collections
import csv
import json
import os
import numpy as np

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows
from pkinv.core import configurations as conf
from pkinv.core.shared_parameter_draws import SEED, Draws, nitrogen_realisations, waste_realisations, dung_mass_multiplier, fugitives_realisations
from pkinv.paths import OUTPUTS
from pkinv.report.air_annual import ATOMS_OUT, CORE7, atom_configuration

OUT = asset_path(OUTPUTS, "pakemis_air_conditional_uncertainty.csv")
TREND = asset_path(OUTPUTS, "pakemis_air_trend_uncertainty.csv")
DRIVERS = asset_path(OUTPUTS, "pakemis_air_uncertainty_drivers.csv")
PARAMETERS = asset_path(OUTPUTS, "pakemis_air_uncertainty_parameters.csv")
N_ITER = 10000
DEPENDENCE_CASES = ("persistent_parameters", "annual_activity_errors")
LIMITATIONS = ("conditional on admitted source coverage, fixed technology/control assumptions and "
               "central sulfur specification cases; missing sources and structural endpoints are "
               "not included in these percentiles; management-system shares and excretion rates held; nitrogen fate factors "
               "and shared N inputs replayed physically; spatial/temporal allocation uncertainty separate")


def composed_atoms(rows):
    own = collections.defaultdict(set)
    for r in rows:
        own[r["configuration_id"]].add(r["sector_id"])
    configurations = tuple(getattr(conf, "AIR_ALL", own))
    for configuration in configurations:
        for r in rows:
            if r["core7"] != "yes":
                continue
            if conf.canonical(r["configuration_id"]) == atom_configuration(configuration, r["sector_id"]):
                yield dict(r, configuration_id=configuration)



def _stats(values):
    lo, median, hi = np.quantile(values, [0.025, 0.5, 0.975])
    return {"mean_Gg": float(values.mean()), "P2_5_Gg": float(lo),
            "P50_Gg": float(median), "P97_5_Gg": float(hi)}


def diagnostic_values(draws, identity):
    """Use actual cached input draws for positive, fraction or native drivers.

    Native asymmetric source controls do not have a symmetric uncert_pct field.
    Their distributions must not be coerced to a new lognormal for diagnostics.
    """
    candidates = [value for key, value in draws.cache.items() if key[0] == identity]
    if not candidates:
        raise ValueError("registered uncertainty input lacks actual draws: " + identity)
    return candidates[0]


def build(rows=None, n=N_ITER, seed=SEED, dependence_cases=DEPENDENCE_CASES):
    if n < 2:
        raise ValueError("conditional ensemble needs at least two realisations")
    rows = rows if rows is not None else read_rows(ATOMS_OUT)
    atoms = list(composed_atoms(rows))
    levels, trends, drivers, registry = [], [], [], []
    max_n_residual = 0.0
    for case in dependence_cases:
        draws = Draws(n, case, seed)
        nitrogen, waste, dung, fugitives = {}, {}, {}, {}
        sums = collections.defaultdict(lambda: np.zeros(n))
        deterministic = collections.defaultdict(float)
        for atom in atoms:
            year = 2000 + int(atom["period_id"][-2:])
            cfg, sector, pol = atom["configuration_id"], atom["sector_id"], atom["pollutant"]
            central = float(atom["emissions_Gg"])
            recipe = atom.get("nitrogen_recipe", "")
            if recipe:
                recipe = json.loads(recipe)
                method = "ipcc" if cfg in (getattr(conf, "IPCC_REFERENCE", "S_IPCC"),
                                           getattr(conf, "IPCC_LEDGER", "L_IPCC")) else "tan"
                if (year, method) not in nitrogen:
                    nitrogen[(year, method)], residual = nitrogen_realisations(year, draws, method)
                    max_n_residual = max(max_n_residual, residual)
                key = recipe["pool"] if "pool" in recipe else (recipe["species"], recipe["stage"])
                if key not in nitrogen[(year, method)]:
                    raise ValueError("unknown nitrogen emission recipe %r for %s" % (key, atom.get("source_class_id")))
                values = nitrogen[(year, method)][key]
            elif atom.get("uncertainty_model") == "shared_waste_flow":
                if year not in waste:
                    waste[year] = waste_realisations(year, draws)
                activity = float(atom["activity_value"])
                if activity <= 0:
                    raise ValueError("nonpositive dry burned mass for an admitted waste atom")
                values = waste[year]["burned_dry_t"] * central / activity
                for parameter in json.loads(atom["parameter_drivers"]):
                    values *= draws.multiplier(parameter, year)
            elif atom.get("uncertainty_model") == "shared_diverted_dung_flow":
                if year not in dung:
                    dung[year] = dung_mass_multiplier(year, draws)
                values = central * dung[year]
                for parameter in json.loads(atom["parameter_drivers"]):
                    values *= draws.multiplier(parameter, year)
            elif atom.get("uncertainty_model") == "shared_fugitive_activity":
                if year not in fugitives:
                    fugitives[year] = fugitives_realisations(year, draws)
                activity = atom["activity_provenance"].split(":", 1)[1]
                key = "activity:" + activity
                if key not in fugitives[year]:
                    raise ValueError("no native fugitive activity realisation for " + activity)
                values = central * fugitives[year][key]
                for parameter in json.loads(atom["parameter_drivers"]):
                    values *= draws.multiplier(parameter, year)
            else:
                values = np.full(n, central)
                for parameter in json.loads(atom["parameter_drivers"]):
                    values *= draws.multiplier(parameter, year)
                if atom.get("uncertainty_model") == "shared_net_gas_combustion":
                    from pkinv.sectors.fugitives import post_meter
                    if year not in fugitives:
                        fugitives[year] = fugitives_realisations(year, draws)
                    leak = post_meter.whole_gas_leak_share()
                    values *= (1 - leak * fugitives[year]["post_meter_factor_multiplier"]) / (1 - leak)
            if not np.all(np.isfinite(values)) or np.any(values < 0):
                raise ValueError("nonphysical native air realisations for " + atom.get("source_class_id", sector))
            for sec in (sector, "national_covered"):
                key = (year, cfg, pol, sec)
                sums[key] += values
                deterministic[key] += central
        for (year, cfg, pol, sec), values in sorted(sums.items()):
            levels.append(dict(period_id="FY%d-%02d" % (year - 1, year % 100),
                               fiscal_end_year=year, configuration_id=cfg, pollutant=pol,
                               sector_id=sec, dependence_case=case, deterministic_Gg=deterministic[(year, cfg, pol, sec)],
                               **_stats(values), draws=n, seed=seed, interval_kind="conditional_parameter_percentiles",
                               coverage_scope="covered_sources_only", limitations=LIMITATIONS,
                               max_nitrogen_closure_residual_kgN=max_n_residual))
            if sec == "national_covered" and np.std(values):
                correlations = []
                for identity, entry in draws.registry.items():
                    if case == "annual_activity_errors" and ":FY" in identity and not identity.endswith(":FY%d" % year):
                        continue
                    x = diagnostic_values(draws, identity)
                    if np.std(x):
                        r = float(np.corrcoef(values, x)[0, 1])
                        correlations.append((r * r, identity, r))
                for rank, (r2, identity, r) in enumerate(sorted(correlations, reverse=True)[:8], 1):
                    drivers.append(dict(period_id="FY%d-%02d" % (year - 1, year % 100), configuration_id=cfg,
                                        pollutant=pol, dependence_case=case, rank=rank, driver_id=identity,
                                        correlation=r, squared_correlation=r2,
                                        attribution="sensitivity diagnostic; squared correlations are not additive variance shares"))
        groups = {(cfg, pol, sec) for year, cfg, pol, sec in sums}
        for cfg, pol, sec in sorted(groups):
            years = sorted(y for y, c, p, s in sums if (c, p, s) == (cfg, pol, sec))
            pairs = list(zip(years[:-1], years[1:])) + [(years[0], years[-1])]
            for early, late in pairs:
                delta = sums[(late, cfg, pol, sec)] - sums[(early, cfg, pol, sec)]
                stats = _stats(delta)
                trends.append(dict(start_period="FY%d-%02d" % (early - 1, early % 100),
                                   end_period="FY%d-%02d" % (late - 1, late % 100), configuration_id=cfg,
                                   pollutant=pol, sector_id=sec, dependence_case=case,
                                   deterministic_change_Gg=deterministic[(late, cfg, pol, sec)] - deterministic[(early, cfg, pol, sec)],
                                   **stats, draws=n, seed=seed, interval_kind="paired_change_parameter_percentiles",
                                   coverage_scope="covered_sources_only", limitations=LIMITATIONS))
        registry.extend(dict(value, dependence_case=case) for _identity, value in sorted(draws.registry.items()))
    return levels, trends, drivers, registry


def _write(path, rows):
    if not rows:
        raise ValueError("empty uncertainty product " + path)
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draws", type=int, default=N_ITER)
    args = parser.parse_args()
    products = build(n=args.draws)
    for path, rows in zip((OUT, TREND, DRIVERS, PARAMETERS), products):
        _write(path, rows)
    print("conditional air ensemble: %d draws, %d level rows; paired years and conserved N ledger" % (args.draws, len(products[0])))


if __name__ == "__main__":
    main()
