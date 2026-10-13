"""LMDI decomposition of the grid emissions series - what the rise actually was.

THE QUESTION. Grid emissions run 43.43 to 58.00 Mt across FY2018-24, through a peak, a
fall and a recovery. The paper attributes those movements to the coal build-out in prose;
this module attributes them in megatonnes, with an identity that must close exactly.

THE FACTORISATION, AND WHY IT IS FUEL-SIDE. Emissions are decomposed as

    E = TJ_total x sum_f( share_f x ef_f )

giving three additive LMDI-I terms per fuel, summed: ACTIVITY (total fuel energy), MIX
(each fuel's share of that energy) and FACTOR (each fuel's CO2e intensity per TJ). The
factorisation deliberately stays inside Table 3 - the same four rows the estimate burns -
because folding in the generation table would import the coal coverage mismatch this
paper documents (Table 3's and Table 17's coal rows do not describe the same plants, with
implied efficiencies swinging 19-58 percent), and a decomposition that absorbed a
coverage artefact into an 'efficiency' term would be narrating the mismatch, not the
fleet.

WHAT THE FACTOR TERM CAN AND CANNOT SEE. Gas and oil factors are constants, so their
factor terms are zero by construction. Coal's factor is the blended lignite/bituminous
value, and it is now the blend of the YEAR: the plant fuel ledger's origin split, held per
fiscal year in data/power_coal_blend_by_year.csv, runs from zero before the Thar fleet
existed to 0.79 at the reference year.

This paragraph used to record the opposite as a limitation - the engine applied the
FY2023-24 blend to every year, so the factor term was exactly zero, and the text said the
true series would carry a small positive one. It does: FY2018-19 to FY2023-24 decomposes
to +1.12 Mt of factor against +8.64 of mix and +5.34 of activity. The limitation is lifted
and the prediction it made was right, which is the better reason to have written it down.

LMDI-I IS EXACT. The logarithmic-mean weights make the three terms sum to the total
change to machine precision, which the test asserts; a decomposition that needs a
residual is a decomposition hiding something. Zero-valued fuels (diesel in some years)
take the standard zero-limit convention: a fuel absent at both ends contributes nothing;
one absent at exactly one end attributes its whole change to the mix term.

DIAGNOSTIC ONLY: the emissions path never imports this module.
"""
import math

from pkinv.sectors.power import combustion, engine


def _lmean(a, b):
    if a == b:
        return a
    if a <= 0 or b <= 0:
        return 0.0
    return (a - b) / (math.log(a) - math.log(b))


def _state(data, year):
    """{fuel: (TJ, co2e_Mt)} plus totals, from the same components the estimate uses."""
    tj = combustion.fuel_TJ(data, year)
    # The GRID stream directly, not the whole engine. This used to call
    # engine.build_components(data, year) and filter to the combustion category - which
    # built captive rows only to discard them, and broke outright once captive learned to
    # take the year seriously: the captive panel starts at FY2016 and the grid history
    # this decomposition walks starts at FY2013-14. The filter below is unchanged; only
    # the wasted (and now impossible) captive build is gone.
    from pkinv.core.components import enrich_co2e
    comps, _memo = combustion.compute(data, year, None)
    comps = enrich_co2e(comps)
    e = {}
    for fuel in tj:
        e[fuel] = sum(c["co2e_Mt_AR5"] for c in comps
                      if c["category"] == combustion.CATEGORY
                      and c["subitem"].startswith(fuel + " "))
    return tj, e


def decompose(data, y0, y1):
    """Additive LMDI-I terms, Mt CO2e, y0 -> y1."""
    tj0, e0 = _state(data, y0)
    tj1, e1 = _state(data, y1)
    T0, T1 = sum(tj0.values()), sum(tj1.values())
    fuels = sorted(set(tj0) | set(tj1))
    activity = mix = factor = 0.0
    per_fuel = {}
    for f in fuels:
        a0, a1 = e0.get(f, 0.0), e1.get(f, 0.0)
        w = _lmean(a1, a0)
        s0 = tj0.get(f, 0.0) / T0
        s1 = tj1.get(f, 0.0) / T1
        i0 = (e0[f] / tj0[f]) if tj0.get(f) else 0.0
        i1 = (e1[f] / tj1[f]) if tj1.get(f) else 0.0
        if w == 0.0:
            # A fuel present at exactly one end: its whole change is a mix effect.
            per_fuel[f] = {"activity": 0.0, "mix": a1 - a0, "factor": 0.0}
        else:
            per_fuel[f] = {"activity": w * math.log(T1 / T0),
                           "mix": w * math.log(s1 / s0) if s0 and s1 else a1 - a0
                           - w * math.log(T1 / T0),
                           "factor": w * math.log(i1 / i0) if i0 and i1 else 0.0}
        activity += per_fuel[f]["activity"]
        mix += per_fuel[f]["mix"]
        factor += per_fuel[f]["factor"]
    total0, total1 = sum(e0.values()), sum(e1.values())
    return {"y0": y0, "y1": y1, "E0_Mt": total0, "E1_Mt": total1,
            "delta_Mt": total1 - total0, "activity_Mt": activity, "mix_Mt": mix,
            "factor_Mt": factor, "per_fuel": per_fuel,
            "closure": (activity + mix + factor) - (total1 - total0)}


def series_rows(data):
    """Year-over-year decomposition across the fuel series, plus the end-to-end row."""
    years = sorted({r["fiscal_year"] for r in data.fuel})
    out = []
    for y0, y1 in zip(years, years[1:]):
        out.append(decompose(data, y0, y1))
    out.append(decompose(data, years[0], years[-1]))
    return out
