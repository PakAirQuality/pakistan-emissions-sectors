"""Rice cultivation CH4 - IPCC Tier 1 (2006 V4 Ch5 Eq 5.1-5.2).

Emissions(Gg CH4) = EFc * SFw * SFp * SFo * area(ha) * period(days) * 1e-6

Pakistan rice is ~100% irrigated continuously flooded -> SFw = 1; default
pre-season and no-amendment scaling factors = 1.
"""
from pkinv.core.uncertainty import product


def compute(data):
    rice = data.crops["rice"]
    efc = data.efv("rice", "EFc")
    sfw = data.efv("rice", "SFw_continuous")
    sfp = data.efv("rice", "SFp_default")
    sfo = data.efv("rice", "SFo_none")
    area = rice["area_ha"]
    period = data.p("rice_cultivation_period_days")

    emis_gg = efc * sfw * sfp * sfo * area * period * 1e-6
    u = product(rice["uncert_pct"], data.efu("rice", "EFc"), data.efu("rice", "SFw_continuous"))
    return [{"category": "Rice cultivation", "subitem": "Continuously flooded",
             "gas": "CH4", "emissions_Gg": emis_gg, "uncert_pct": u}]
