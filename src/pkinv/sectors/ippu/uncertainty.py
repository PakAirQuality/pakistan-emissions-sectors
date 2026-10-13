"""Structural and conditional parametric uncertainty for the IPPU cement module."""
from __future__ import annotations

import random

from pkinv.core.montecarlo import percentile
from pkinv.sectors.ippu import cement

N_ITER = 10000
SEED = 42
REFERENCE_ACTIVITY_SOURCE = "pbs_qim_fy2023_24"
CLINKER_FRACTIONS = (0.75, 0.95)


def structural_scenarios(data, year=None):
    """Valid current Tier-1 configurations.

    Observed clinker trade is required by IPCC Equation 2.1 and is included in every
    current configuration.  The superseded no-trade calculation is emitted separately
    by :func:`method_benchmarks`; it is not part of the structural envelope.
    """
    output = []
    ef = data.efv("ippu_cement", "Clinker")
    census = cement.census_production(data, year)
    output.append({
        "scenario_id": "producer_census_observed",
        "cement_source": census["cement_source"],
        "cement_activity_kt": "",
        "clinker_fraction": "", "trade_included": census["trade_included"],
        "clinker_imports_kt": "", "clinker_exports_kt": "",
        "clinker_production_kt": census["clinker_production_kt"],
        "co2_Gg": census["clinker_production_kt"] * ef,
        "co2e_Mt_AR5": census["clinker_production_kt"] * ef / 1000.0,
        "probability_weight": "",
        "interpretation": "REFERENCE (rc30): observed 16-company census production; "
                          "no fraction, no trade term",
    })
    for fraction in CLINKER_FRACTIONS:
        balance = cement.clinker_balance(
            data, year, REFERENCE_ACTIVITY_SOURCE, fraction, True)
        output.append({
            "scenario_id": "%s_f%.2f_trade" % (REFERENCE_ACTIVITY_SOURCE, fraction),
            "cement_source": REFERENCE_ACTIVITY_SOURCE,
            "cement_activity_kt": balance["cement_activity_kt"],
            "clinker_fraction": fraction, "trade_included": True,
            "clinker_imports_kt": balance["clinker_imports_kt"],
            "clinker_exports_kt": balance["clinker_exports_kt"],
            "clinker_production_kt": balance["clinker_production_kt"],
            "co2_Gg": balance["clinker_production_kt"] * ef,
            "co2e_Mt_AR5": balance["clinker_production_kt"] * ef / 1000.0,
            "probability_weight": "",
            "interpretation": "named structural diagnostic: the Tier-1 PBS-QIM+trade "
                              "model this census superseded as reference",
        })
    return output


def method_benchmarks(data, year=None):
    """Return provenance benchmarks that are excluded from the valid model range."""
    ef = data.efv("ippu_cement", "Clinker")
    current_no_trade = cement.clinker_balance(
        data, year, REFERENCE_ACTIVITY_SOURCE, 0.75, False)
    original_clinker_kt = 48011.0 * 0.75
    return [
        {
            "benchmark_id": "cement_no_trade_method_benchmark",
            "period": "FY2023-24", "cement_activity_kt": 39566.0,
            "clinker_fraction": 0.75, "trade_included": False,
            "clinker_production_kt": current_no_trade["clinker_production_kt"],
            "co2e_Mt_AR5": current_no_trade["clinker_production_kt"] * ef / 1000.0,
            "status": "screening_only",
            "interpretation": "isolates the bias from omitting observed clinker trade",
        },
        {
            "benchmark_id": "original_misdated_no_trade_calculation",
            "period": "superseded; 48,011 kt is FY2021-22, not FY2023-24",
            "cement_activity_kt": 48011.0, "clinker_fraction": 0.75,
            "trade_included": False, "clinker_production_kt": original_clinker_kt,
            "co2e_Mt_AR5": original_clinker_kt * ef / 1000.0,
            "status": "screening_only",
            "interpretation": "original paper result; combines a period-tagging error with trade omission",
        },
    ]


def uncertainty_inputs(data, activity_source=REFERENCE_ACTIVITY_SOURCE, fraction=0.75,
                       include_trade=True):
    """The REFERENCE component's named parameters (census basis since rc30).

    The model's fraction and trade rows moved to the diagnostic where the model
    itself now lives: keeping them here made the named registry imply a sigma
    the census component never declared, which is exactly the silent-clamp
    class the national reconciliation guard exists to refuse.
    """
    census_kt = data.census_clinker_kt()
    balance = cement.clinker_balance(data, activity_source=activity_source,
                                     fraction=fraction, include_trade=include_trade)
    return [
        {"input": "census clinker production", "central": census_kt,
         "lower": census_kt * 0.95,
         "upper": census_kt * 1.05, "unit": "kt clinker",
         "distribution": "bounded triangular", "correlation_group": "cement_activity",
         "source": "16-company producer census", "uncertainty_type": "parametric"},
        {"input": "diagnostic model clinker fraction", "central": fraction,
         "lower": fraction,
         "upper": fraction, "unit": "fraction", "distribution": "fixed in scenario",
         "correlation_group": "clinker_fraction", "source": data.ps("clinker_fraction"),
         "uncertainty_type": "structural (diagnostic model only)"},
        {"input": "diagnostic model clinker exports",
         "central": balance["clinker_exports_kt"],
         "lower": balance["clinker_exports_kt"],
         "upper": balance["clinker_exports_kt"], "unit": "kt clinker",
         "distribution": "not sampled in the reference (diagnostic model term)",
         "correlation_group": "trade_export",
         "source": balance["trade_source"],
         "uncertainty_type": "parametric (diagnostic model only)"},
        {"input": "diagnostic model clinker imports",
         "central": balance["clinker_imports_kt"],
         "lower": balance["clinker_imports_kt"],
         "upper": balance["clinker_imports_kt"], "unit": "kt clinker",
         "distribution": "not sampled in the reference (diagnostic model term)",
         "correlation_group": "trade_import",
         "source": balance["trade_source"],
         "uncertainty_type": "parametric (diagnostic model only)"},
        {"input": "clinker CO2 emission factor", "central": data.efv("ippu_cement", "Clinker"),
         "lower": data.efv("ippu_cement", "Clinker") * 0.92,
         "upper": data.efv("ippu_cement", "Clinker") * 1.08,
         "unit": "t CO2/t clinker", "distribution": "bounded triangular",
         "correlation_group": "clinker_factor",
         "source": data.efs("ippu_cement", "Clinker"),
         "uncertainty_type": "parametric"},
        {"input": "clinker stock change", "central": 0.0, "lower": "", "upper": "",
         "unit": "kt clinker", "distribution": "not sampled; unresolved",
         "correlation_group": "clinker_stock", "source": balance["stock_source"],
         "uncertainty_type": "structural/data gap"},
    ] + activated_inputs(data)


def activated_inputs(data):
    """rc52: the named parameters of the three categories that entered the reference - each
    pair (activity, factor) is exactly the width its component declares (product of the two),
    so the shared groups bound in data/parameter_scope.csv leave no undeclared excess. The
    factors persist across years (one quantity), the activities resample (a statistic per
    year) - typed in longitudinal_uncertainty.GROUP_TYPE."""
    from pkinv.sectors.ippu import ammonia, lubricants, steel
    _c, (amm,) = ammonia.compute(data)
    _c, (stl,) = steel.compute(data)
    _c, (lub,) = lubricants.compute(data)
    ef_a, ef_s = data.p("ammonia_ef_calibrated"), data.p("steel_eaf_ef")
    odu = data.p("lubricant_odu_oil")
    pct = lambda name: data.pu(name) / 100.0
    return [
        {"input": "ammonia embodied in NFDC production", "central": amm["nh3_kt"],
         "lower": amm["nh3_kt"] * (1 - ammonia.ACTIVITY_UNCERT_PCT / 100.0), "upper": amm["nh3_kt"] * (1 + ammonia.ACTIVITY_UNCERT_PCT / 100.0),
         "unit": "kt NH3", "distribution": "lognormal", "correlation_group": "ammonia_activity",
         "source": "NFDC production by product x NH3 stoichiometry", "uncertainty_type": "parametric"},
        {"input": "ammonia CO2 factor (calibrated)", "central": ef_a,
         "lower": ef_a * (1 - pct("ammonia_ef_calibrated")), "upper": ef_a * (1 + pct("ammonia_ef_calibrated")),
         "unit": "t CO2/t NH3", "distribution": "lognormal", "correlation_group": "ammonia_factor",
         "source": data.ps("ammonia_ef_calibrated"), "uncertainty_type": "parametric"},
        {"input": "urea CO2 recovery (structural, not sampled)", "central": amm["recovered_to_urea_Gg"],
         "lower": amm["recovered_to_urea_Gg"], "upper": amm["recovered_to_urea_Gg"],
         "unit": "Gg CO2", "distribution": "fixed (IPCC Eq 3.10 stoichiometry)", "correlation_group": "urea_recovery",
         "source": data.ps("urea_co2_recovery_factor"), "uncertainty_type": "structural"},
        {"input": "crude steel (QIM billets and ingots)", "central": stl["billets_kt"],
         "lower": stl["billets_kt"] * (1 - steel.ACTIVITY_UNCERT_PCT / 100.0), "upper": stl["billets_kt"] * (1 + steel.ACTIVITY_UNCERT_PCT / 100.0),
         "unit": "kt steel", "distribution": "lognormal", "correlation_group": "steel_activity",
         "source": "PBS QIM monthly billets/ingots, twelve months summed", "uncertainty_type": "parametric"},
        {"input": "steel CO2 factor (EAF, Tier 1)", "central": ef_s,
         "lower": ef_s * (1 - pct("steel_eaf_ef")), "upper": ef_s * (1 + pct("steel_eaf_ef")),
         "unit": "t CO2/t steel", "distribution": "lognormal", "correlation_group": "steel_factor",
         "source": data.ps("steel_eaf_ef"), "uncertainty_type": "parametric"},
        {"input": "lubricants sold (OCAC lubes + greases)", "central": lub["lubricating_oil_t"] + lub["grease_t"],
         "lower": (lub["lubricating_oil_t"] + lub["grease_t"]) * (1 - lubricants.ACTIVITY_UNCERT_PCT / 100.0),
         "upper": (lub["lubricating_oil_t"] + lub["grease_t"]) * (1 + lubricants.ACTIVITY_UNCERT_PCT / 100.0),
         "unit": "t", "distribution": "lognormal", "correlation_group": "lubricant_activity",
         "source": "OCAC sectoral sales of non-energy products, grand totals", "uncertainty_type": "parametric"},
        {"input": "lubricant oxidised-during-use fraction", "central": odu,
         "lower": odu * (1 - pct("lubricant_odu_oil")), "upper": odu * (1 + pct("lubricant_odu_oil")),
         "unit": "fraction", "distribution": "lognormal", "correlation_group": "lubricant_odu",
         "source": data.ps("lubricant_odu_oil"), "uncertainty_type": "parametric"},
    ]


def conditional_monte_carlo(data, activity_source=REFERENCE_ACTIVITY_SOURCE,
                            fraction=0.75, include_trade=True, n_iter=N_ITER, seed=SEED):
    balance = cement.clinker_balance(data, activity_source=activity_source,
                                     fraction=fraction, include_trade=include_trade)
    rng, samples = random.Random(seed), []
    for _ in range(n_iter):
        activity = rng.triangular(balance["cement_activity_kt"] * 0.95,
                                  balance["cement_activity_kt"] * 1.05,
                                  balance["cement_activity_kt"])
        exports = rng.triangular(balance["clinker_exports_kt"] * 0.90,
                                 balance["clinker_exports_kt"] * 1.10,
                                 balance["clinker_exports_kt"])
        imports = rng.triangular(balance["clinker_imports_kt"] * 0.90,
                                 balance["clinker_imports_kt"] * 1.10,
                                 balance["clinker_imports_kt"])
        ef_central = data.efv("ippu_cement", "Clinker")
        factor = rng.triangular(ef_central * 0.92, ef_central * 1.08, ef_central)
        samples.append((activity * fraction - imports + exports) * factor / 1000.0)
    ordered = sorted(samples)
    deterministic = balance["clinker_production_kt"] * data.efv(
        "ippu_cement", "Clinker") / 1000.0
    return {
        "cement_source": activity_source, "clinker_fraction": fraction,
        "trade_included": include_trade, "deterministic_mt_co2": deterministic,
        "mean_mt_co2": sum(samples) / len(samples),
        "p025_mt_co2": percentile(ordered, 0.025),
        "p50_mt_co2": percentile(ordered, 0.5),
        "p975_mt_co2": percentile(ordered, 0.975),
        "n_iter": n_iter, "seed": seed, "distribution": "bounded triangular",
        "interpretation": "conditional parametric interval; no structural probability",
    }, samples


def census_monte_carlo(data, n_iter=N_ITER, seed=SEED):
    """The reference interval on the census basis: activity and factor only.

    No fraction and no trade draw exist because the census observes production
    directly; the seed is offset so the census stream cannot silently alias the
    model stream it replaced."""
    production_kt = data.census_clinker_kt()
    ef_central = data.efv("ippu_cement", "Clinker")
    rng, samples = random.Random(seed + 1), []
    for _ in range(n_iter):
        activity = rng.triangular(production_kt * 0.95, production_kt * 1.05,
                                  production_kt)
        factor = rng.triangular(ef_central * 0.92, ef_central * 1.08, ef_central)
        samples.append(activity * factor / 1000.0)
    ordered = sorted(samples)
    return {
        "cement_source": "16-company producer census", "clinker_fraction": "",
        "trade_included": "not applicable",
        "deterministic_mt_co2": production_kt * ef_central / 1000.0,
        "mean_mt_co2": sum(samples) / len(samples),
        "p025_mt_co2": percentile(ordered, 0.025),
        "p50_mt_co2": percentile(ordered, 0.5),
        "p975_mt_co2": percentile(ordered, 0.975),
        "n_iter": n_iter, "seed": seed + 1, "distribution": "bounded triangular",
        "interpretation": "conditional parametric interval; no structural probability",
    }, samples


def selected_intervals(data, n_iter=N_ITER, seed=SEED):
    output = []
    census_summary, _ = census_monte_carlo(data, n_iter=n_iter, seed=seed)
    output.append({"configuration": "reference (producer census)", **census_summary})
    selections = (("diagnostic model f=0.75", REFERENCE_ACTIVITY_SOURCE, 0.75, True),
                  ("diagnostic model f=0.95 (all-Portland)",
                   REFERENCE_ACTIVITY_SOURCE, 0.95, True))
    for label, source, fraction, trade in selections:
        summary, _samples = conditional_monte_carlo(
            data, source, fraction, trade, n_iter=n_iter, seed=seed)
        output.append({"configuration": label, **summary})
    return output


def one_at_a_time(data):
    reference = next(row for row in structural_scenarios(data)
                     if row["clinker_fraction"] == 0.75)
    alternatives = (("all-Portland clinker fraction",
                     REFERENCE_ACTIVITY_SOURCE, 0.95, True),)
    output = []
    for label, source, fraction, trade in alternatives:
        row = next(value for value in structural_scenarios(data)
                   if value["cement_source"] == source
                   and value["clinker_fraction"] == fraction
                   and value["trade_included"] == trade)
        output.append({"change": label, "reference_mt_co2": reference["co2e_Mt_AR5"],
                       "alternative_mt_co2": row["co2e_Mt_AR5"],
                       "difference_mt_co2": row["co2e_Mt_AR5"] - reference["co2e_Mt_AR5"],
                       "difference_pct": 100.0 * (row["co2e_Mt_AR5"] /
                                                   reference["co2e_Mt_AR5"] - 1.0)})
    return output
