"""CNG's two activity bases, and what they say about each other.

WHAT THIS MODULE USED TO BE. Written when CNG had no emissions estimate at all, to measure the
size of the omission in the one unit available: vehicle-kilometres. The gas quantity has since
been fetched from OGRA (sectors/transport/cng.py), so the omission is closed and the module's
job has changed rather than ended.

WHAT IT IS NOW. This sector holds two independent descriptions of the same CNG vehicles:

  the METERED GAS - OGRA's sector-wise consumption, which sets the emissions;
  the FLEET MODEL - survival-weighted vehicle-kilometres times each class's CNG share, which
  sets the geography and drives the air-pollutant layer.

Neither is derived from the other, so dividing one by the other gives an implied energy
intensity in joules per vehicle-kilometre - a quantity with known bounds, in exactly the way
the power sector's implied heat rate is. It tests whether the two descriptions are of the same
fleet.

WHAT IT FINDS, AND WHY IT MATTERS MORE THAN THE NUMBER. The implied intensity comes out near
0.9 MJ per vehicle-kilometre. Published consumption rates put a CNG three-wheeler nearer 1.6
and a CNG car nearer 3, and this fleet is seven-tenths three-wheelers by distance, so the
metered gas is well short of what the modelled travel would need. The two bases disagree, and
the direction says the FLEET MODEL OVERSTATES CNG TRAVEL.

That is a result about a known weakness rather than a new one. This sector already records that
its class split rides vehicle-kilometres and over-weights small vehicles, and already argues
that the national total must therefore come from metered fuel rather than from the fleet. CNG
is the first place where an independent fuel quantity exists for a class the fleet model
covers, so it is the first direct evidence for that argument rather than an assertion of it.

THE BOUNDS ARE THE WEAK PART, AND ARE TREATED AS SUCH. Per-vehicle CNG consumption rates for
the Pakistani fleet have not been obtained (data/data_gaps.csv, transport-hsd-end-use covers
the liquid-fuel counterpart). The band below is generic engineering judgement, not a Pakistani
measurement, so this module LABELS a disagreement and never adjusts anything. The emissions
come from metered gas whatever the fleet model says.
"""
from pkinv.sectors.transport import cng, road

FUEL = "CNG"

# Joules per vehicle-kilometre a CNG road fleet could plausibly average. Wide on purpose: the
# low end is a fleet of nothing but three-wheelers, the high end one with a large bus and
# heavy-vehicle share. Judgement, not measurement - see the docstring.
PLAUSIBLE_MJ_PER_KM = (1.2, 6.0)


def vkt_by_class(data, year=None):
    """{ei_class: vehicle-km on CNG} for the year, from the sector's own fleet model."""
    vkt, _cells, _capped = road.effective_vkt(data, year)
    out = {}
    for (cls, fuel), v in vkt.items():
        if fuel == FUEL:
            out[cls] = out.get(cls, 0.0) + v
    return out


def summary(data, year=None):
    """Both bases and the implied intensity between them.

    by_class is ordered largest first, because the mix is what makes the intensity
    interpretable: a three-wheeler-dominated fleet should sit near the bottom of the band.
    """
    vkt, _cells, _capped = road.effective_vkt(data, year)
    total = sum(vkt.values())
    by_cls = vkt_by_class(data, year)
    cng_vkt = sum(by_cls.values())
    tj = cng.gas_TJ(data, year)
    mj_per_km = (tj * 1e6 / cng_vkt) if cng_vkt else None
    lo, hi = PLAUSIBLE_MJ_PER_KM
    if mj_per_km is None:
        verdict = "no CNG travel modelled"
    elif mj_per_km < lo:
        verdict = "FLEET-MODEL-HIGH"
    elif mj_per_km > hi:
        verdict = "FLEET-MODEL-LOW"
    else:
        verdict = "consistent"
    return {"cng_vkt": cng_vkt, "total_vkt": total,
            "share_pct": 100.0 * cng_vkt / total if total else 0.0,
            "gas_TJ": tj, "mj_per_km": mj_per_km, "verdict": verdict,
            "by_class": sorted(((c, v, 100.0 * v / cng_vkt if cng_vkt else 0.0)
                                for c, v in by_cls.items()), key=lambda t: -t[1])}
