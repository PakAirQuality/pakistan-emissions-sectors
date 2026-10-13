"""Legacy 2006 production-only Tier-1 benchmark.

This module is intentionally not the registered national estimate. It preserves the old
developing-country range calculation so the paper can measure what changes when the 2019
Refinement and infrastructure activity are introduced. Published ranges are kept bounded
and uncapped; the probabilistic experiment samples them directly in log space.
"""
from __future__ import annotations

import math

CATEGORY = "Fugitive emissions from oil and gas"

STREAMS = (
    ("Gas production fugitives", "CH4", "Fugitives CH4", "gas"),
    ("Gas production fugitives", "CO2", "Fugitives CO2", "gas"),
    ("Gas production flaring", "CH4", "Flaring CH4", "gas"),
    ("Gas production flaring", "CO2", "Flaring CO2", "gas"),
    ("Gas production flaring", "N2O", "Flaring N2O", "gas"),
    ("Oil production fugitives", "CH4", "Fugitives CH4", "oil"),
    ("Oil production fugitives", "CO2", "Fugitives CO2", "oil"),
    ("Oil production venting", "CH4", "Venting CH4", "oil"),
    ("Oil production venting", "CO2", "Venting CO2", "oil"),
    ("Oil production flaring", "CH4", "Flaring CH4", "oil"),
    ("Oil production flaring", "CO2", "Flaring CO2", "oil"),
    ("Oil production flaring", "N2O", "Flaring N2O", "oil"),
)


def bounds(data, fuel, item):
    return (data.efv("fugitive_%s_low" % fuel, item),
            data.efv("fugitive_%s_high" % fuel, item))


def range_uncert_pct(lo, hi):
    """Uncapped symmetric display half-width around the geometric median.

    The legacy Monte Carlo does not use this approximation; it samples the bounded
    log-uniform range directly. This value exists only for the shared component contract.
    """
    if lo <= 0 or hi <= lo:
        return 0.0
    centre = math.sqrt(lo * hi)
    return (hi - lo) / (2.0 * centre) * 100.0


def activity(data, fuel, year=None):
    return data.gas_e6m3(year) if fuel == "gas" else data.oil_e3m3(year)


def ufg_bound_Gg_CH4(data, year=None):
    """All UFG treated as physical gas loss: a diagnostic upper bound, not emissions."""
    y = data.year if year is None else int(year)
    if data.has_anchor_year(y):
        e6m3 = data.activity("ufg_diagnostic", year=y)["value"]
    else:
        e6m3 = data.network_e6m3("T&D losses (UFG)", year=y)
    # 1 million m3 * kg/m3 = 1 million kg = 1 Gg. No factor of 1,000 belongs here.
    return e6m3 * data.p("gas_density_kg_per_m3") * data.p("gas_ch4_fraction")


def compute(data, year=None, bound=None):
    if bound not in (None, "low", "high"):
        raise ValueError("bound must be None, 'low' or 'high', not %r" % (bound,))
    components = []
    for stream, gas, item, fuel in STREAMS:
        lo, hi = bounds(data, fuel, item)
        ef = {"low": lo, "high": hi}.get(bound) if bound else math.sqrt(lo * hi)
        row = {
            "category": CATEGORY,
            "subitem": "%s %s" % (stream, gas),
            "gas": gas,
            "emissions_Gg": activity(data, fuel, year) * ef,
            "uncert_pct": range_uncert_pct(lo, hi),
        }
        if gas == "CH4":
            row["fossil"] = True
        components.append(row)
    return components, []
