"""Iron and steel production (IPCC 2.C.1), Tier 1 - a reference component since rc52.

Pakistan makes crude steel by melting scrap (electric arc and induction furnaces) and, at one
works, from direct-reduced iron: PBS's QIM prints ZERO pig iron from FY2016-17, so no blast furnace
operates. IPCC 2006 Vol 3 Table 4.1's Tier 1 factor for that route is 0.08 t CO2/t steel
(data/ippu_params.csv steel_eaf_ef), applied to QIM's 'Billets/Ingots' - the crude-steel product -
summed over the fiscal year's own twelve months (data/activity/monthly/pbs_qim_month_item.csv).
Rolled products (hot- and cold-rolled sheets, strips, coils) are downstream of the billet and are
excluded so the tonnage is not counted twice.

WHY IT ENTERS NOW. The activity is a full nine-year national statistic; the factor is the IPCC
default for the only route the country operates; the mass is small (0.25-0.51 Mt) and was already
bounded to this figure by the screening. What remains open - the scrap-vs-DRI split and the plants'
own carbon inputs - is a Tier 2 refinement named in the uncertainty (route bracket), not a reason
to keep the category NE.
"""
from __future__ import annotations

from pkinv.core import pbs_qim
from pkinv.core.uncertainty import product

CATEGORY = "Iron and steel production"
SUBITEM = "Crude steel (electric route) process CO2"
ACTIVITY_UNCERT_PCT = 10.0        # the QIM tonnage against producer reports: an administrative index


def fiscal_label(year):
    return "%d-%02d" % (year - 1, year % 100)


def billets_kt(data, year):
    """QIM billets and ingots, the fiscal year's own twelve months summed, in kt."""
    months = pbs_qim.series(pbs_qim.BILLETS, year - 1)
    if not months:
        raise ValueError("QIM billets/ingots are not held for FY%s" % fiscal_label(year))
    return sum(months.values()) / 1000.0


def compute(data, year=None):
    year = data.year if year is None else int(year)
    kt = billets_kt(data, year)
    ef = data.p("steel_eaf_ef")
    component = {
        "category": CATEGORY, "subitem": SUBITEM, "gas": "CO2",
        "emissions_Gg": kt * ef,
        "uncert_pct": product(ACTIVITY_UNCERT_PCT, data.pu("steel_eaf_ef")),
    }
    memo = {"fiscal_year": fiscal_label(year), "billets_kt": kt, "ef_t_co2_per_t": ef,
            "route": "electric (scrap EAF/induction; one DRI-fed works) - pig iron zero",
            "configuration_status": "reference_tier1_eaf"}
    return [component], [memo]
