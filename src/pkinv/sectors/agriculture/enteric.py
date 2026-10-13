"""Enteric fermentation CH4 - IPCC Tier 1 (2006 V4 Ch10 Eq 10.19/10.20).

Emissions(Gg CH4) = sum_species  N(head) * EF(kg/head/yr) / 1e6
"""
from pkinv.core.uncertainty import product


def compute(data):
    components = []
    cattle = data.livestock["cattle"]
    dairy_share = data.p("dairy_cattle_share")

    # split total cattle into dairy / non-dairy (assumption)
    species_heads = {
        "dairy_cattle": cattle["head"] * dairy_share,
        "other_cattle": cattle["head"] * (1 - dairy_share),
        "buffalo": data.livestock["buffalo"]["head"],
        "sheep": data.livestock["sheep"]["head"],
        "goats": data.livestock["goats"]["head"],
        "camels": data.livestock["camels"]["head"],
    }
    ad_uncert = {
        "dairy_cattle": cattle["uncert_pct"], "other_cattle": cattle["uncert_pct"],
        "buffalo": data.livestock["buffalo"]["uncert_pct"],
        "sheep": data.livestock["sheep"]["uncert_pct"],
        "goats": data.livestock["goats"]["uncert_pct"],
        "camels": data.livestock["camels"]["uncert_pct"],
    }

    for sp, head in species_heads.items():
        ef = data.efv("enteric", sp)
        emis_gg = head * ef / 1e6
        u = product(ad_uncert[sp], data.efu("enteric", sp))
        components.append({
            "category": "Enteric fermentation", "subitem": sp, "gas": "CH4",
            "emissions_Gg": emis_gg, "uncert_pct": u,
        })
    return components
