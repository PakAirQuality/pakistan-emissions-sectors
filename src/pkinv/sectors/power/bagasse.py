"""Bagasse grid generation (IPCC 1A1a, biomass): CH4 and N2O counted, CO2 a memo.

WHAT THIS IS. Eight sugar-mill cogeneration plants sell bagasse-fired electricity to the
CPPA-G grid; NEPRA SoIR 2024 Table 8's E3 block publishes their generation for five fiscal
years (parsed by scripts/ingest_nepra_bagasse.py, reconciled against the table's own Total
row). This module turns that generation into the sector's smallest stream - about 0.02 Mt
CO2e of CH4 and N2O - and its first memo item, roughly a megatonne of biogenic CO2.

WHY THE ACTIVITY IS STRUCTURALLY WEAKER, SAID OUT LOUD. Every other stream in this sector
starts from metered fuel. This one starts from metered GENERATION times an assumed heat
rate (bagasse_heat_rate_kj_per_kwh, 15,000 kJ/kWh +/- 20 percent), because no bagasse fuel
tonnage or plant heat rate has been found in anything read for this inventory. Deriving
activity that way is exactly what this sector refuses to do for its fossil streams, and
the review's condition for doing it at all was that the derivation be labelled
lower-quality rather than blended in silently - hence this paragraph, the parameter's own
note, and the fact that the assumption can only touch CH4/N2O and the memo, never a fossil
CO2 figure.

THE CONVENTION, same as residential biomass: biogenic CO2 goes to the memo and never into
a total - the carbon was fixed by last season's cane, and any net stock change belongs to
agriculture/LULUCF, not to the power station. CH4 and N2O are counted as components because
incomplete combustion is a net source whatever the carbon's origin; the CH4 is non-fossil
and takes AR5 28, unlike every other stream in this module's sector.

THE FACTOR TABLE IS THE ENERGY-INDUSTRIES ONE. IPCC Table 2.2 gives Other Primary Solid
Biomass 30 kg CH4/TJ; the residential table (2.5) gives 300 for the same fuel. Grid
boilers are 1A1a and take 2.2 - the parallel-table trap this inventory documents for gas
in four other sectors, now documented for biomass too.

CO-FIRING IS NAMED, NOT SPLIT. The E3 block lists alternate fuels - three plants carry
Biomass, and The Thal Industries Corporation carries furnace oil. The alternate-fuel share
has not been found in anything read here, so all generation is treated as bagasse-fired
and the FO co-firing is carried as a named caveat: whatever share was FO belongs in the
fossil rows, and the completeness note says so rather than inventing a split.
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import csv
import os

from pkinv.core.uncertainty import product
from pkinv.paths import DATA
from pkinv.sectors.power import combustion

CATEGORY = combustion.CATEGORY          # grid plants selling to CPPA-G: 1A1a
ITEM = "Other Primary Solid Biomass"    # IPCC's rank for sugar-cane bagasse
CSV = asset_path(DATA, "activity", "power", "bagasse_generation.csv")


def rows(year=None, path=CSV):
    out = [r for r in _activity_rows(path, comments=False)
           if year is None or int(r["fiscal_year"]) == year]
    return out


def generation_GWh(data, year=None):
    year = data.year if year is None else year
    return sum(float(r["generation_GWh"]) for r in rows(year))


def fuel_TJ(data, year=None):
    """GWh x assumed heat rate. kJ/kWh x GWh = GJ x 1e-3 = TJ x 1e-3 x 1e3; net: GWh x
    1e6 kWh x kJ/kWh x 1e-9 TJ/kJ = GWh x hr x 1e-3."""
    return generation_GWh(data, year) * data.p("bagasse_heat_rate_kj_per_kwh") * 1e-3


def compute(data, year=None):
    """(components, memo): CH4 and N2O into 1A1a, biogenic CO2 to the memo."""
    tj = fuel_TJ(data, year)
    if not tj:
        return [], []           # years before the E3 series starts (the FY2018 row)
    ad_u = product(data.p("activity_uncert"), data.pu("bagasse_heat_rate_kj_per_kwh"))
    components = [
        # Non-fossil CH4: no "fossil" flag, so enrich_co2e applies AR5 28, as in
        # residential biomass and waste - the one non-fossil CH4 in this sector.
        {"category": CATEGORY, "subitem": "Bagasse CH4", "gas": "CH4",
         "emissions_Gg": tj * data.efv("power_combustion_ch4", ITEM) / 1e6,
         "uncert_pct": product(ad_u, data.efu("power_combustion_ch4", ITEM))},
        {"category": CATEGORY, "subitem": "Bagasse N2O", "gas": "N2O",
         "emissions_Gg": tj * data.efv("power_combustion_n2o", ITEM) / 1e6,
         "uncert_pct": product(ad_u, data.efu("power_combustion_n2o", ITEM))},
    ]
    memo = [{
        "item": "Biogenic CO2 from grid bagasse (IPCC memo item)", "gas": "CO2",
        "emissions_Gg": tj * data.efv("power_combustion_co2", ITEM) / 1e6,
        "note": "Reported outside the national total: the carbon was fixed by the cane "
                "crop within the year. CH4 and N2O are counted as components because "
                "incomplete combustion is a net source whatever the carbon's origin - the "
                "same convention as residential dung and firewood. The activity is "
                "generation x an assumed 15,000 kJ/kWh heat rate, the sector's one "
                "generation-derived stream, labelled structurally weaker than its metered "
                "fuel streams."}]
    return components, memo
