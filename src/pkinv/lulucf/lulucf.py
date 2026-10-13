"""LULUCF land sector - Tier 1 carbon stock change for Pakistan (IPCC 3.B).

A SEPARATE sector from agriculture: emissions are CO2 and dominated by removals (sinks),
so values are signed (sink = negative). Reported alongside agriculture as an AFOLU total.

Components (single-year 2024):
  3.B.1 Forest land     - net afforestation sink (Billion Tree / Ten Billion Tree)
  3.B.2 Cropland (SOC)  - 0 at Tier 1
  3.B.3 Grassland (SOC) - 0 at Tier 1
  3.B.4 Wetlands        - Indus-delta mangrove blue carbon sink (FAOSTAT omits this)
"""

from pkinv.assets import asset_path
import csv
import os

from pkinv.paths import ROOT

PARAMS = asset_path(ROOT, "data", "lulucf_params.csv")
C_TO_CO2 = 44.0 / 12.0


def load_params(path=PARAMS):
    p = {}
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            p[r["param"]] = {"value": float(r["value"]), "unit": r["unit"],
                             "source": r["source"], "note": r["note"]}
    return p


def _v(p, k):
    return p[k]["value"]


def compute(params=None):
    """Return signed LULUCF components: list of dicts (Mt CO2e; sink negative)."""
    p = params or load_params()

    # 3.B.1 Forest land: net afforestation sink minus (small/zero) deforestation source
    forest_sink = -(_v(p, "afforestation_growing_area_ha") * _v(p, "forest_seq_rate_tC_ha_yr")
                    * C_TO_CO2) / 1e6
    deforest_src = (_v(p, "deforestation_area_ha_yr") * _v(p, "forest_c_density_tC_ha")
                    * C_TO_CO2) / 1e6
    forest_net = forest_sink + deforest_src
    forest_stock = _v(p, "forest_area_ha") * _v(p, "forest_c_density_tC_ha") * C_TO_CO2 / 1e6

    # 3.B.4 Wetlands - mangrove blue carbon sink (restored area x sequestration rate)
    mangrove_net = -(_v(p, "mangrove_restored_area_ha") * _v(p, "mangrove_seq_rate_tCO2_ha_yr")) / 1e6
    mangrove_stock = (_v(p, "mangrove_area_ha")
                      * (_v(p, "mangrove_agb_c_tC_ha") + _v(p, "mangrove_soil_c_tC_ha"))
                      * C_TO_CO2) / 1e6

    return [
        {"code": "3.B.1", "subcategory": "Forest land", "gas": "CO2",
         "co2e_Mt": forest_net, "c_stock_Mt_co2e": forest_stock},
        # rc42 (the twentieth review's P-2): cropland and grassland soil carbon are NOT
        # ESTIMATED at Tier 1 (completeness.csv 3.B.2/3.B.3). A numeric 0.0 here entered the
        # NET sum and contradicted the notation key; the flux is None and the notation says
        # why. The params rows stay as the record of what an estimate would need.
        {"code": "3.B.2", "subcategory": "Cropland (SOC)", "gas": "CO2",
         "co2e_Mt": None, "notation": "NE", "c_stock_Mt_co2e": None},
        {"code": "3.B.3", "subcategory": "Grassland (SOC)", "gas": "CO2",
         "co2e_Mt": None, "notation": "NE", "c_stock_Mt_co2e": None},
        {"code": "3.B.4", "subcategory": "Wetlands - mangrove blue carbon", "gas": "CO2",
         "co2e_Mt": mangrove_net, "c_stock_Mt_co2e": mangrove_stock},
    ]


def net(components):
    """The net over the ESTIMATED components; an NE component contributes nothing, and is
    not a zero."""
    return sum(c["co2e_Mt"] for c in components if c["co2e_Mt"] is not None)
