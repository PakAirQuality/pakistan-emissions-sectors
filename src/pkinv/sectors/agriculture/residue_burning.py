"""Field burning of agricultural residues - CH4 + N2O (IPCC 2006 V4 Ch2 Eq 2.27).

Emission (Gg) = mass_burnt(t) * Cf * Gef(g/kg) / 1e6
  mass_burnt = crop production x above-ground residue ratio x fraction burned
  Cf  = combustion factor; Gef = gas emission factor (g per kg dry matter burned)

Small GHG category (more an air-quality concern), but completes the inventory. The burned
residue is excluded from the soils residue-N return (residue_params frac_returned already
reflects removal+burning), so there is no double counting with managed-soils FCR.
"""
from pkinv.core.uncertainty import product

CATEGORY = "Field burning of residues"


def mass_burnt_by_crop(data):
    """{crop: tonnes dry matter burned} (production x residue ratio x frac burned).

    Public since the air spatial Wave A: the per-crop loop used to be internal to
    mass_burnt and discarded, so the burning atoms could not say which crop's residue
    they were - and crop identity is what a crop-specific burned-area support would
    key on. mass_burnt stays as the sum, so the greenhouse-gas term is unmoved."""
    out = {}
    for crop, bp in data.burning.items():
        prod = data.crops.get(crop, {}).get("production_t")
        rr = data.residue.get(crop, {}).get("residue_ratio_ag")
        if not prod or not rr:
            continue
        out[crop] = prod * rr * bp["frac_burned"]
    return out


def mass_burnt(data):
    """Tonnes dry matter burned, summed over crops (production x residue ratio x frac burned).
    Shared by the GHG burning term and the air-pollutant layer (air_pollutants.py)."""
    return sum(mass_burnt_by_crop(data).values())


def compute(data):
    cf = data.efv("burning", "combustion_factor")
    gef_ch4 = data.efv("burning", "Gef_CH4")
    gef_n2o = data.efv("burning", "Gef_N2O")
    cf_u = data.efu("burning", "combustion_factor")

    mb = mass_burnt(data)

    ch4_gg = mb * cf * gef_ch4 / 1e6
    n2o_gg = mb * cf * gef_n2o / 1e6
    return [
        {"category": CATEGORY, "subitem": "Residue burning CH4", "gas": "CH4",
         "emissions_Gg": ch4_gg, "uncert_pct": product(20, cf_u, data.efu("burning", "Gef_CH4"))},
        {"category": CATEGORY, "subitem": "Residue burning N2O", "gas": "N2O",
         "emissions_Gg": n2o_gg, "uncert_pct": product(20, cf_u, data.efu("burning", "Gef_N2O"))},
    ]
