"""Agriculture as a registered sector (IPCC 3.A-3.H).

Currently a facade over the modules in pkinv.inventory: the contract is written against,
and proven by, the sector that already works before anything relocates. The modules move
underneath this file in a later step, and this interface does not change when they do.
"""
from pkinv.core import evidence, period
from pkinv.sectors.agriculture import downscale, run_inventory
from pkinv.sectors.agriculture.ef_library import InventoryData
from pkinv.sectors.agriculture import pipeline

NAME = "agriculture"

# Order is the published column order of provincial_totals_2024.csv. A tuple because it
# is a fixed public interface, not a working list.
CATEGORIES = tuple(run_inventory.CATEGORIES)
GASES = ("CO2", "CH4", "N2O")
HAS_SINKS = False          # agriculture emits; the land sector holds the sinks
YEAR = run_inventory.YEAR

# The reference PERIOD, not just a year. Declaring it is what found this sector a fiscal year
# adrift: the integer 2024 meant FY2024-25 here, because the crop quantities were the Pakistan
# Economic Survey 2024-25 tables and the nitrogen offtake the NFDC Review 2024-25, while the
# same integer meant FY2023-24 in six other sectors and a calendar year in waste. The integer
# was carrying three meanings across the inventory and nothing could see it.
#
# Both activity files now read FY2023-24 from the 2023-24 editions, archived under
# sources/Agriculture/, so the convention here is fiscal-END like the six sectors it now
# matches. All ten sectors report the same twelve months.
#
# The sector is internally mixed, and that is stated rather than smoothed: enteric fermentation
# and manure management - two thirds of the sector - ride the PBS 7th Agricultural Census 2024
# herd, a point-in-time enumeration rather than a flow over any period. The Economic Survey
# publishes its own livestock ESTIMATES for the same year, and this sector deliberately does
# not use them (data/activity/livestock_2024.csv carries both and selects basis=census): a
# count is evidence and a projection is not, and moving the herd onto the fiscal year would
# trade the measurement for the estimate to buy a tidiness the census cannot support.
YEAR_CONVENTION = "fiscal-end"
PERIOD_START, PERIOD_END = period.from_year(YEAR, YEAR_CONVENTION)

# The categories whose activity is a COUNT rather than a flow. data/activity/livestock_2024.csv
# carries the census enumeration beside the Economic Survey's fiscal-year projection and
# selects the census, so these rows describe an instant and the others describe twelve months.
ENUMERATED_CATEGORIES = ("Enteric fermentation", "Manure management")
ENUMERATION_SOURCE = "PBS 7th Agricultural Census 2024"

MC_DISTRIBUTION = "lognormal"

load_data = InventoryData


# core.evidence classes. Half the national inventory sits here, and its streams differ more
# than any other sector's.
#
#   Enteric fermentation, manure management  E2 - the 7th Agricultural Census counts the herd.
#     A census is a published enumeration, and its rows are ENUMERATION rather than span, which
#     is why the monthly layer must not spread them.
#   Managed soils, direct N2O from synthetic fertiliser  E2 - NFDC's audited annual nutrient
#     offtake. Its INDIRECT streams are E3: volatilisation and leaching fractions are IPCC
#     defaults applied to that same nitrogen, not quantities of their own.
#   Rice cultivation  E2 - Economic Survey area, with the cultivation period declared.
#   Field burning  E3 - production times a residue ratio times a burned fraction, three
#     assumptions deep.
#   Liming and urea  E2 - urea offtake from the same NFDC series; liming itself is NE.
#
# T3 by default: crop calendars and application timing are process profiles. Fertiliser is T2,
# because NFDC's Annex-7 publishes offtake by province, month and product. The livestock
# categories are T4 and flat by contract - a census stock has no month.
# S3 throughout: district crop area and livestock counts are administrative statistics.
EVIDENCE_CLASS, TEMPORAL_METHOD, SPATIAL_METHOD = "E2", "T3", "S3"
SOURCE_ID = "pbs_agricultural_census_and_economic_survey"
STREAM_CLASSES = {
    "Direct N2O - synthetic": (None, "T2", None, "nfdc_fertilizer_review_annex7"),
    # rc39 A7: the generic indirect rule no longer carries the FERTILISER annexe as its
    # source. It caught seven rows that are livestock nitrogen, not fertiliser nitrogen -
    # manure management's indirect N2O and, in managed soils, the volatilisation and
    # leaching streams of organic manure and of pasture deposition. Their DIRECT
    # counterparts were sourced to the census correctly, so the same nitrogen carried two
    # different provenances depending on which side of the volatilisation step it was on.
    # The three synthetic streams below keep NFDC by their own longer prefixes, which is
    # where the fertiliser annexe genuinely belongs.
    "Indirect N2O": ("E3", None, None, "pbs_agricultural_census_and_economic_survey"),
    # Only the synthetic-fertiliser indirect streams inherit NFDC's monthly offtake; the
    # organic and pasture ones ride the livestock census and fall to the category's T4.
    "Indirect N2O - volatilisation (synthetic": ("E3", "T2", None,
                                                 "nfdc_fertilizer_review_annex7"),
    "Indirect N2O - leaching/runoff (synthetic": ("E3", "T2", None,
                                                  "nfdc_fertilizer_review_annex7"),
    "Direct N2O - organic": ("E3", None, None, "pbs_agricultural_census_and_economic_survey"),
    "Direct N2O - pasture": ("E3", None, None, "pbs_agricultural_census_and_economic_survey"),
    # T3 since Wave 3: the returned-residue streams ride the mineralization kernel
    # (harvest windows + declared e-folding) rather than the category's flat default.
    # The longer prefix wins over "Direct N2O - crop" below, and the leaching prefix
    # over the generic "Indirect N2O" above.
    "Direct N2O - crop residues": ("E3", "T3", None,
                                   "pbs_agricultural_census_and_economic_survey"),
    "Indirect N2O - leaching/runoff (crop residues": (
        "E3", "T3", None, "pbs_agricultural_census_and_economic_survey"),
    "Direct N2O - crop": ("E3", None, None, "pbs_agricultural_census_and_economic_survey"),
    "Continuously": (None, None, None, "economic_survey_2023_24_rice_area"),
    # rc39 A7: 3.H claimed the agricultural census as its source and listed crops_2024.csv
    # and livestock_2024.csv as its documents - neither of which contains a tonne of urea.
    # Since A3 the mass is NFDC's printed national offtake, so the stream names it.
    "Urea application CO2": (None, "T2", None, "nfdc_annex5_national_offtake"),
    # rc39 A7: E3, which is what the comment block above this table has said all along -
    # "production times a residue ratio times a burned fraction, three assumptions deep".
    # There was no override, so both rows fell to the module default of E2, and E2 claims
    # "a published statistic for this source and period". Nobody publishes Pakistan's burned
    # residue mass; it is derived from crop production through two ratios, which is E3's
    # definition exactly. A declaration the code never honoured is worse than no declaration,
    # because it reads as evidence that someone checked.
    "Residue burning": ("E3", None, None, "pbs_agricultural_census_and_economic_survey"),
}

# The temporal axis divides this sector by category, not by subitem: the enteric subitems are
# animal names. Each entry is the class that governs most of the year in the monthly layer
# (sectors/agriculture/monthly.py), and tests/test_monthly_layer.py asserts the two agree - the
# declaration is a claim about evidence and the layer is what was actually built with it.
TEMPORAL_BY_CATEGORY = {
    # A census stock has no month; flat by contract, T4 whatever the biology does.
    "Enteric fermentation": (None, "T4", None),
    "Manure management": (None, "T4", None),
    # Most of this category's nitrogen is deposited or applied off the livestock census, so
    # T4 is the category default and the synthetic-fertiliser streams override it to T2.
    "Managed soils": (None, "T4", None),
    "Urea application": (None, "T2", None),
    # T3 since rc20, and year-specific in ALL NINE YEARS: each fiscal year carries its own
    # FRP-weighted VIIRS profile from the held fire record, not the reference year's borrowed
    # across the panel - nine distinct weight vectors, none marked borrowed_from_year. This
    # comment claimed a single borrowed profile while the archive had long since been
    # extended. The windows themselves are the calendar's claim, which is what keeps this
    # off T2.
    "Field burning of residues": (None, "T3", None),
}


def build_components(data, year=None, **kwargs):
    """run_inventory.build_components, with the stock-versus-flow distinction stamped on.

    A thin wrapper rather than an edit inside run_inventory: the arithmetic is unchanged and
    the sector's own tests pin it, so the wrapper adds metadata and nothing else.

    THE YEAR ARGUMENT IS REFUSED, LOUDLY, AND IT USED TO BE EATEN. This signature was
    `(data, *args, **kwargs)` forwarding straight into `run_inventory.build_components(data,
    ef1_override=None)`, so a caller passing a year positionally had it consumed as an
    EMISSION FACTOR: `build_components(data, 2024)` returned 4,819,139 Mt against a published
    223.26. The contract this sector is admitted under says no sector may return a plausible
    wrong number for a year its sources do not cover; this one returned an implausible wrong
    number and nothing noticed, because the guard computed its own reference through the same
    poisoned call and so scaled its acceptance band by the defect.

    This module is pinned to one period by construction: enteric fermentation and manure
    management ride the PBS 7th Agricultural Census head count, which is an enumeration of one
    year and not a series. The multi-year reconstruction lives in `timeseries.py`, on FAOSTAT
    stocks, and is a different basis rather than the same one re-run.
    """
    if year is not None and year != YEAR:
        raise ValueError(
            "agriculture is pinned to %d (FY%d-%s): its herd is a census enumeration, not an "
            "annual flow. The multi-year reconstruction is agriculture.timeseries, which is a "
            "declared change of basis to FAOSTAT stocks." % (YEAR, YEAR - 1, str(YEAR)[-2:]))
    rows = run_inventory.build_components(data, **kwargs)
    for row in rows:
        row["activity_year"] = YEAR
        row["activity_period_kind"] = ("enumeration" if row["category"] in ENUMERATED_CATEGORIES
                                       else "span")
    evidence.stamp(rows, (EVIDENCE_CLASS, TEMPORAL_METHOD, SPATIAL_METHOD),
                   SOURCE_ID, YEAR, overrides=STREAM_CLASSES,
                   category_overrides=TEMPORAL_BY_CATEGORY)
    return rows
AVAILABLE_RASTERS = frozenset(
    {"glw_livestock", "cropland", "spam_rice", "manure_applied", "firms_fire"})


def grid_surface_for(category, subitem):
    """The RASTER this stream is actually spread on (rc39 A9).

    The spatial decomposition used to resolve a surface per GEOMETRY, through
    data/stream_grid_proxy.csv. Agriculture is deliberately absent from that register - its
    mapping already exists here and duplicating it was judged worse - so the join found
    nothing for this sector and fell through to whatever another module had declared for the
    same shared `diffuse:adm2_*` geometry. Every agriculture stream was published as
    `population`, which is true of none of them: livestock rides GLW, rice MapSPAM, burning
    the FIRMS record, fertiliser and residue cropland, applied manure its own surface.

    One geometry carries thirty-four streams on five different rasters, so a per-geometry
    answer cannot be right for more than one of them. This is the per-stream answer, from the
    same two functions the gridded product allocates with - not a third copy of the mapping.
    """
    from pkinv.core.gis.proxy_map import gis_proxy
    return gis_proxy(downscale.proxy_for({"category": category, "subitem": subitem}),
                     category, AVAILABLE_RASTERS)


def grid_surface_by_stream(data=None):
    """{source_stream_id: raster} for every stream this sector emits.

    KEYED ON THE STREAM IDENTITY, not on a category name. The published ledger carries the
    IPCC category ("Agricultural soils") while the engine works in its own ("Managed soils"),
    and a join on the label silently resolved four categories and left two - 29.2 Mt - falling
    back to another module's surface. component_id is the identity both sides already derive
    from the same function, so the join cannot half-work.
    """
    from pkinv.core.components import component_id
    if data is None:
        data = InventoryData()
    return {component_id(NAME, c["category"], c["subitem"], c["gas"]):
            grid_surface_for(c["category"], c["subitem"])
            for c in run_inventory.build_components(data)}


intermediates = pipeline.intermediates
proxy_for = downscale.proxy_for
load_shares = downscale.load_shares


def parameter_overrides():
    """Runtime parameter values the national registry must publish (rc33).

    The engine-contract hook that ended core/parameters.py's one downward
    import: the registry sweeps every sector for this optional function
    instead of core knowing agriculture's internals. The content is the
    eighth review's NH3 item - soils FracGASF runs on the product-weighted
    fertiliser mix, not the Table 11.3 default the CSV keeps as the
    annexe-missing fallback.
    """
    from pkinv.sectors.agriculture import fertiliser_mix
    value, source = fertiliser_mix.fracgasf()
    return {"ef:soils_fracgasf": {
        "value": round(value, 6),
        "uncert_pct_95": fertiliser_mix.fracgasf_uncert(),
        "source": source,
        "note": "soils / FracGASF (runtime value; data/emission_factors.csv 0.15 "
                "is the annexe-missing fallback only)",
    }}


# --- Declared accessors (rc34). The report layer reaches these BY NAME through
# the registry instead of importing sector internals; each wraps one module of
# this sector and nothing here recomputes anything.


def components_for_fiscal_year(fy_end):
    """The BACKCAST build for one fiscal year - the runner's own build on the
    fiscal activity data, exactly as the longitudinal ensemble consumed it. Not
    the reference-year build_components(), whose year guard is deliberate."""
    from pkinv.sectors.agriculture import fiscal_activity
    return run_inventory.build_components(fiscal_activity.data_for_fiscal_year(fy_end))


def activity_basis(category):
    """The declared per-category activity basis of the backcast driver."""
    from pkinv.sectors.agriculture import fiscal_activity
    return fiscal_activity.DRIVER[category][1]


def series_components_for_year(fy_end):
    """The published fiscal-series components for one year (nothing recomputed) -
    what the annual product carries for backcast years."""
    from pkinv.sectors.agriculture import fiscal_series
    return fiscal_series.components_for_year(fy_end)
