"""Municipal solid waste as a registered sector: open burning (4C2) and disposal (4A).

The first sector built against the contract rather than derived from it, and now the first
to carry two categories that partition one physical stream. Waste that is collected goes to
a disposal site (4A); waste that is not is partly burned in the open (4C2). Both read the
same population panel and the same generation and collection parameters, so the two cannot
disagree about how much waste Pakistan produces - see swds.py for the closure identity and
tests/test_waste.py for the assertion.
"""
from pkinv.core import period
from pkinv.core.components import enrich_co2e
from pkinv.sectors.waste import downscale, open_burning, swds, wastewater
from pkinv.sectors.waste.data import WasteData, YEAR

NAME = "waste"
# Globally unique across sectors: key-category analysis and the dashboard pool every
# sector into one category namespace.
CATEGORIES = ("Open burning of waste", "Solid waste disposal",
              "Domestic wastewater")
GASES = ("CO2", "CH4", "N2O")
HAS_SINKS = False
YEAR = YEAR

# The reference PERIOD, not just a year. See core.period: this sector's YEAR is the calendar
# year its reporting period CLOSES in. The population panel is projected to the fiscal
# midpoint; see waste/data.py.
YEAR_CONVENTION = "fiscal-end"
PERIOD_START, PERIOD_END = period.from_year(YEAR, YEAR_CONVENTION)

# core.evidence classes for the whole sector, adopted together because a half-classified
# sector reads as a fully classified one (see the contract test).
#
# E3, not E2, and the demotion is this round's doing. Every stream here is population times a
# rate, and the population is now PROJECTED one year past the 7th Census rather than
# interpolated between two censuses - derived from a published quantity plus a growth
# assumption rather than read from one. The disposal category is E3 for a second, older
# reason as well: a first-order-decay stock is a model over decades of past generation, not
# an observation of this year.
#
# T4 because no monthly waste statistic was obtained here; the seasonal profile that open
# burning plainly has is not in this release, and a flat one is not asserted, it is absent.
# S3 because the allocation rides district population, an administrative statistic.
EVIDENCE_CLASS = "E3"
TEMPORAL_METHOD = "T4"
SPATIAL_METHOD = "S3"
SOURCE_ID = "pbs_census_population_district"

MC_DISTRIBUTION = "lognormal"

load_data = WasteData
proxy_for = downscale.proxy_for
load_shares = downscale.load_shares


def build_components(data, year=None):
    burning, _memo = open_burning.compute(data, year)
    disposal, _d = swds.compute(data, year)
    sewage, _w = wastewater.compute(data, year)
    rows = burning + disposal + sewage
    for row in rows:
        row.setdefault("activity_year", year if year is not None else data.year)
        row.setdefault("activity_period_kind", "span")
        row.setdefault("evidence_class", EVIDENCE_CLASS)
        # T3 for the disposal stock since rc20: the monthly layer runs the FOD
        # at a monthly step over the observed deposit history (a physical model,
        # not an observation - which is what keeps it off T2). The other
        # categories keep the sector default.
        if row["category"] == "Domestic wastewater":
            # S2 since rc47 Wave 3: the served share of each covered district sits at
            # its HydroWASTE plant (a facility set with per-object served population);
            # coverage is partial and the untreated remainder rides the population
            # raster, which is what keeps the letter at S2.
            row.setdefault("spatial_method", "S2")
        if row["category"] == "Solid waste disposal":
            row.setdefault("temporal_method", "T3")
            # S2 since rc46 Wave 5: within covered districts the disposal mass sits at the
            # mapped sites (a facility proxy the allocation actually opens); coverage is
            # partial and site tonnage unheld, which is what keeps the letter at S2 and
            # not S1. The other categories keep the sector's administrative S3.
            row.setdefault("spatial_method", "S2")
        row.setdefault("temporal_method", TEMPORAL_METHOD)
        row.setdefault("spatial_method", SPATIAL_METHOD)
        row.setdefault("source_id", SOURCE_ID)
    return enrich_co2e(rows)


def memo_items(data, year=None):
    """Biogenic CO2 - reported alongside the inventory, never summed into it."""
    _components, memo = open_burning.compute(data, year)
    return memo
