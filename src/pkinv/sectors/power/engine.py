"""Electricity generation as a registered sector: grid (IPCC 1A1a) and captive (IPCC 1A2).

Two IPCC codes in one module, as the transport sector carries road (1A3b) alongside off-road
machinery (1A4c). Grid generation is main-activity production for sale and takes Chapter 2's
Table 2.2; captive generation serves the factory that owns it and takes Table 2.3. They share
this module because they share the subject and the plant register, and nothing downstream
conflates them - the rollup, the key-category screen and the completeness table all work on
categories, not modules.
"""
from pkinv.core import evidence, period
from pkinv.core.components import enrich_co2e
from pkinv.sectors.power import bagasse, captive, combustion, downscale
from pkinv.sectors.power.data import PowerData, YEAR

NAME = "power"
CATEGORIES = ("Electricity and heat production", captive.CATEGORY)
GASES = ("CO2", "CH4", "N2O")
HAS_SINKS = False
YEAR = YEAR                  # fiscal year, July to June

# The reference PERIOD, not just a year. See core.period: this sector's YEAR is the calendar
# year its reporting period OPENS in, a convention that was implicit until it collided
# with the opposite one in a neighbouring sector.
YEAR_CONVENTION = 'fiscal-start'
PERIOD_START, PERIOD_END = period.from_year(YEAR, YEAR_CONVENTION)

MC_DISTRIBUTION = "lognormal"

load_data = PowerData
proxy_for = downscale.proxy_for
load_shares = downscale.load_shares


# core.evidence classes. THE GRID DEFAULT IS E1 and the exceptions matter more than the rule.
# NEPRA publishes fuel consumed PLANT BY PLANT, so a grid fuel row is a metered quantity for
# this source and period. Two streams are not:
#
#   Captive natural gas - OGRA's metered captive-gas return is a published statistic for a
#     class of consumers rather than a per-plant meter, and its heating value is a declared
#     Pakistani range rather than a measurement (E2).
#   Bagasse - the sugar mills' own generation is reconstructed from crushing statistics and a
#     bagasse-per-tonne-cane ratio, which is a derived quantity (E3).
#
# The grid's default is T4, but at the reference year only bagasse and captive still carry
# it: NEPRA's SIR Detail-of-Generation listings supply plant-month generation for FY2021-22
# onward (scripts/ingest_sir_generation.py), so grid coal is T2 and grid gas T3 - gas is T3
# rather than T2 because a fifth of its observed generation is assigned to gas by the
# annual-control bound rather than stated per plant. The liquid-fuel streams are T2 because
# OCAC's monthly Total Power customer-class row covers them.
#
# S3, AND IT HAS NOW BEEN WRONG TWICE IN THE SAME DIRECTION. It first read "S1 throughout:
# the plant register carries coordinates, so emissions sit on the facilities that produce
# them", and data/activity/power/plant_locations.csv has columns plant/town/province/
# station_type - no coordinate column ever existed. That was corrected to S2 on the reasoning
# that a register locating plants to TOWNS is a facility proxy. It is not, because the cube
# never opens the register: the grid streams are placed by PROVINCIAL generation shares spread
# on the BUILT-UP raster, and thirty of the seventy-eight stations that can emit now carry a
# corroborated coordinate without one gramme riding on them. data/geometry_sets.csv says so
# itself - "the surface stays built-up until coverage supports points". A registered fleet the
# allocation does not consume is not a facility proxy; it is an administrative statistic with a
# fleet standing beside it, which is S3. The class returns to S2 when an allocation actually
# uses the points, and to S1 when it uses them with per-station generation.
EVIDENCE_CLASS, TEMPORAL_METHOD, SPATIAL_METHOD = "E1", "T4", "S2"
SOURCE_ID = "nepra_state_of_industry_plant_fuel"
STREAM_CLASSES = {
    # S2, was S3: the captive allocation is the one place in this inventory that DOES open its
    # register below the province. 1,068 of 1,105 plants are geocoded and the cube pools them
    # by the province their coordinates land in, then splits each province's share across its
    # own plants.
    #
    # The letter is unchanged in rc44 and its REASON is not. It used to read "S2 rather than S1
    # because 864 of those 1,068 carry a gas allocation and the remaining 204 fall back to an
    # equal weight". Those 204 no longer fall back to anything: 130 of them carry an OGRA
    # metered zero, which is a measurement, and 74 are NEPRA-licensed plants OGRA never metered
    # and so are outside the mass being placed at all. Both now weigh zero and the pool is the
    # metered gas exactly. What holds the letter at S2 is the placement being
    # object_partial_activity - 4.3 percent of the register's metered gas sits on rows with no
    # coordinate and rides built-up as a declared event, so 0.9574 of the mass is on a plant.
    "Captive natural gas": ("E2", "T4", "S2", "ogra_sorpi_captive_gas"),
    # T4, not T3: the crushing season is real and documentable and this release does not
    # T2 since rc30: the crushing season is READ from PBS QIM's sugar months (group
    # row 1-3, all nine editions parsed once the wrapped-row rule landed), and the
    # bagasse months ride the mills' own reported production - the flat-by-assertion
    # admission this line used to carry is withdrawn. S3 with the module: bagasse
    # rides the same provincial-share-on-built-up path as the grid streams, and the
    # sugar mills - real facilities, none of them geocoded here - are no more
    # consumed by that allocation than the grid stations are.
    "Bagasse": ("E3", "T2", None, "pbs_sugar_crushing"),
    # rc60: S1, and the way it got there is the point. This entry carried no spatial letter,
    # so furnace oil took the module default of S2, and the Gas paragraph above used to explain
    # the 0.8299 by pointing at the typed skip list in scripts/ingest_gas_plant_coordinates.py -
    # the GOGPT defect on Halmore, the JDW-III identity conflict, Nooriabad approximate-only.
    # THAT EXPLANATION WAS WRONG. None of those three burns furnace oil. The entire 0.1701 was
    # ONE station, Lal Pir, holding 86.4 of the reference year's 508.1 thousand tonnes - and Lal
    # Pir has had a GEM-exact coordinate in gas_plant_coordinates.csv since rc46. It failed to
    # match because scripts/ingest_nepra_plants.py had joined a column heading onto its name, so
    # the ledger called it "(000 M. Tons) Lal Pir" and the join key came out
    # ('000', 'lal', 'm', 'pir', 'tons') - a key no coordinate table could ever carry.
    #
    # With the ingest fixed, all twelve RFO stations in the reference year sit on a real
    # coordinate row: Nishat, Lal Pir, Pak Gen., Atlas, Nishat Chunian, Liberty Power Tech.,
    # Kohinoor, Narowal, Attock, Saba, TPS Muzaffargarh and Hub. The letter is earned by located
    # activity, not declared here. THE TEMPORAL CLASS IS UNTOUCHED at T2: the first draft of
    # this change added a SECOND "Furnace Oil" key further down the dict, which silently
    # overwrote this one and carried T3 with it - a duplicate literal key that Python accepts
    # without a word and that moved a class nobody had asked to move.
    "Furnace Oil": (None, "T2", "S1", None),
    # S1 since rc44, and NOT because diesel acquired a coordinate. Every CPPA station that
    # burns HSD was already located; the fuel that held the stream at 0.732 belonged to
    # K-Electric, which is outside the mass this sector places - SoIR Table 3 is CPPA-only,
    # and until rc44 the cube read the plant ledger without the boundary filter the rest of
    # the sector applies. With K-E out of the denominator the located share is exactly
    # 1.0000. Raising a share by removing rows is the shape of a flattered number, so the
    # justification is stated rather than assumed: the emissions left with the plants.
    "Diesel Oil": (None, "T2", "S1", None),
    # The SIR listing lane (FY2021-22 onward, reference year included): coal is stated
    # plant-by-plant (TE2 -> T2); gas includes the bound-assigned RLNG/HSD group and is
    # capped at T3 by the inferred-fuel rule.
    # S1 since rc42 (the twentieth review's S-1): the cube reads all eight FY2023-24 coal
    # stations from data/activity/power/coal_plant_coordinates.csv (GEM exact, Climate
    # TRACE within 0.4 km) and each carries its OWN plant-ledger generation, so the
    # allocation uses the points with per-station activity - the S1 case the paragraph
    # above names. 99.17 percent of the stream's mass sits on a located station; the
    # remainder (Balochistan's 0.32 Mt, whose one station lands in the grid's Sindh cell)
    # stays a named fallback event, and the decomposition measures the class from that
    # mass, not from this declaration. HSD reached S1 in rc44 - see its entry above.
    "Coal": (None, "T2", "S1", None),
    # S1 since rc46 Wave 1: seventeen gas/RFO stations acquired GEM-exact,
    # TRACE-corroborated coordinates (data/activity/power/gas_plant_coordinates.csv) and
    # the located share of the gas fleet rose 0.499 -> 0.9658, over the 95 percent line,
    # with each station carrying its own ledger fuel.
    "Gas": (None, "T3", "S1", None),
}


def build_components(data, year=None, coal_override=None, hhv_btu=None):
    """Grid combustion plus captive self-generation.

    year applies to the grid stream directly and to captive through a fiscal-convention
    shift (grid is fiscal-start, the OGRA captive panel fiscal-end, so grid year Y and
    captive year Y+1 name the same twelve months). With year=None captive keeps its own
    pinned reference (power_params.captive_year). coal_override applies to grid only;
    hhv_btu drives the captive heating-value sensitivity.
    """
    components, _memo = combustion.compute(data, year, coal_override)
    # +1: the grid year is fiscal-START, the captive panel fiscal-END (OGRA labels
    # FY2023-24 as 2024). None keeps captive's own pinned reference.
    cap, _cap_memo = captive.compute(data, hhv_btu,
                                     year=None if year is None else year + 1)
    bag, _bag_memo = bagasse.compute(data, year)
    rows = components + cap + bag
    evidence.stamp(rows, (EVIDENCE_CLASS, TEMPORAL_METHOD, SPATIAL_METHOD),
                   SOURCE_ID, year if year is not None else YEAR,
                   overrides=STREAM_CLASSES)
    return enrich_co2e(rows)


def memo_items(data, year=None):
    """Biogenic CO2 from grid bagasse - the sector's one memo item."""
    _c, memo = bagasse.compute(data, year)
    return memo
