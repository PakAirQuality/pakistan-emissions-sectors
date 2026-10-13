"""Province allocation for power generation.

Unusually for this inventory, the geography is a real one rather than a statistical
surrogate: thermal power plants are point sources, and the proxy is now built from their
PLANT-WISE GENERATION rather than from a capacity database.

WHY THE PROXY CHANGED, AND WHAT IT COST KHYBER PAKHTUNKHWA. The previous proxy came from
WRI's Global Power Plant Database v1.3 and was described in data/province_shares.csv as
provisional and the weakest element of this sector. It named its own likely failure - that
assigning provinces by a coordinate rule "likely overstates Khyber Pakhtunkhwa" - and asked
to be replaced with plant-wise generation. It was right. On generation, KP is 0.02 percent
of national thermal output, not 14.24: its 20 GWh against a national 93,942 GWh, because
KP's electricity is hydro, which burns nothing and belongs nowhere in this sector. That
moves roughly 7.8 Mt of CO2e out of KP, almost all of it into Punjab.

THERMAL ONLY. Hydro, wind, solar and nuclear generate electricity without combustion, so
they must carry no share of a combustion sector's emissions. The source assigns no province
to non-thermal plants, which is consistent with that and is why the normalisation runs over
thermal plants alone.

THE REFINEMENT THE PREVIOUS PARAGRAPH ASKED FOR NOW EXISTS. This docstring used to close
by noting that once plant-wise fuel was available, each fuel could take its own proxy,
"since Thar coal is entirely Sindh while gas is spread across Punjab and Sindh". The
FY2023-24 ledger carries plant-wise fuel and Table 5 carries locations, so the four fossil
streams now ride per-fuel point-source shares built in point_sources.py (power_coal,
power_gas, power_rfo, power_hsd), each drift-pinned by a test that recomputes it from the
ledger. The correction is largest exactly where the old note predicted: coal is 89 percent
Sindh on ledger energy, where the aggregate FY2022 surrogate had put half of it in Punjab.
The aggregate power_generation row remains in province_shares.csv as the documented
fallback, but no current component rides it.
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import csv
import os

from pkinv.core.geography import PROVINCES
from pkinv.paths import DATA
from pkinv.sectors.power import captive

PROXY = "power_generation"

# Captive generation does not follow the grid fleet's geography at all: it follows the
# factories, so it takes the plant register's own measured gas-by-province split. Routing it
# through the grid proxy would put 60 percent of Sindh's captive gas in Punjab.
PROXY_FALLBACK = {"Electricity and heat production": PROXY,
                  captive.CATEGORY: "captive_gas"}
# Every grid stream rides its own point-source geography. The four fossil rows come from
# the ledger x Table 5 join (point_sources.py); bagasse's plants all list Punjab districts
# (Table 5, D3). Keys are exact (category, subitem) pairs so an unmapped new stream falls
# through to the documented fallback rather than silently borrowing a fuel's geography.
_GRID = "Electricity and heat production"
PROXY_MAP = {(_GRID, "Bagasse CH4"): "bagasse_grid",
             (_GRID, "Bagasse N2O"): "bagasse_grid"}
for _fuel, _proxy in (("Coal", "power_coal"), ("Gas", "power_gas"),
                      ("Furnace Oil", "power_rfo"), ("Diesel Oil", "power_hsd")):
    for _gas in ("CO2", "CH4", "N2O"):
        PROXY_MAP[(_GRID, "%s %s" % (_fuel, _gas))] = _proxy


def load_shares(period=None):
    """The provincial share vector for this sector, for one fiscal period.

    WITH NO PERIOD it is the committed table, data/province_shares.csv: the reference year,
    FY2023-24. Every caller that has no period (the sector runner, the reference cube, the
    uncertainty products) is describing that year.

    WITH A PERIOD each grid fuel takes ITS OWN YEAR'S stations (rc66). Through rc65 coal and
    gas rode the reference year's vector in all nine periods, and furnace oil rode it for
    FY2020-21 to FY2022-23, which booked every tonne to Punjab while Hub and Jamshoro were
    burning it. The manuscript carried that as a stated limitation, with the size of the
    worst province-year (11.6 Mt CO2e) and the remark that a per-year split was possible
    from the same records. pkinv.sectors.power.province_panel is that split: station fuel
    quantities by fuel and year, coal on the national booking's own basis. A fuel-year whose
    station record falls under the panel's coverage floor keeps the committed row, and the
    panel's record says which and why; the reference year is the committed row by
    definition, and tests hold the panel to reproducing it.

    This replaces the rc44 override that gave furnace oil and diesel own-year GENERATION
    shares for FY2015-16 to FY2019-20 and deliberately left gas alone: the fuel quantities
    were on the same pages of the same report, and the test that refused gas had run on a
    panel holding 47.5 percent of that year's gas generation.
    """
    shares = {}
    for r in _activity_rows(asset_path(DATA, "province_shares.csv"), comments=False):
        shares[r["proxy"]] = {p: float(r[p]) for p in PROVINCES}
    from pkinv.sectors.power import province_panel
    year = province_panel.panel_year(getattr(period, "fiscal_start_year", None))
    if year is not None:
        for stream, vector in province_panel.province_shares(year).items():
            shares[stream] = {p: vector.get(p, 0.0) for p in PROVINCES}
    # AND THE CAPTIVE FLEET'S OWN YEAR (rc60). The committed captive_gas row is the FY2023-24
    # register's split, and it was being applied to all nine periods - including FY2020-21,
    # where OGRA reports the SNGPL captive lane at 1 MMCFD against SSGCL's 202 and Punjab's
    # share is nearer 0.008 than the 0.340 the engine used. captive_panel weights each
    # utility's own franchise geography by the lane totals OGRA publishes per year; the
    # within-franchise map stays the one year the register measures, and the module says so.
    # The reference year reproduces the committed row to 1.4e-5, so nothing shipped moves
    # there - the same discipline transport's own-year override applies.
    from pkinv.sectors.power import captive_panel
    captive_year = captive_panel.panel_year(getattr(period, "fiscal_start_year", None))
    vector = captive_panel.province_shares(captive_year) if captive_year else None
    if vector:
        shares[captive_panel.STREAM] = {p: vector.get(p, 0.0) for p in PROVINCES}
    return shares


def proxy_for(c):
    # Indexed with [], not .get(): an unknown category must raise rather than silently
    # allocate onto the wrong geography at an unchanged national total.
    return PROXY_MAP.get((c["category"], c["subitem"]), PROXY_FALLBACK[c["category"]])
