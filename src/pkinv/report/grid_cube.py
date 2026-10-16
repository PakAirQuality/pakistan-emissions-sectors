"""The 0.05 degree monthly cube: the inventory's mass, placed and timed, conserving exactly.

WHAT THIS IS. The reviewer's Stage 6 product: every one of the 190 source streams spread
over the national 0.05 degree grid by the most native geography its evidence supports, and
over the twelve months of FY2023-24 by the published monthly layer, under the identity

    E(s, m, g, i) = E(s, g) x p(s, m) x w(s, i)

with sum(p) = 1 (the monthly layer's tested property) and sum(w) = 1 (this module's,
enforced per stream). The per-stream surfaces are built and tested in memory and NOT shipped
(175 MB of rasters in a tracked repository buys nothing a regeneration cannot).

THE CLOSURE IDENTITY HAS TWO TERMS, AND THAT IS THIS RELEASE'S CHANGE. It read
annual = monthly = native = grid = ADM2 = province. It now reads

    national == ADM1        (unchanged, and this is the safety property)
    ADM1     == ADM2 + unallocated_below_adm1

because twenty-four industry streams - 9.01 Mt, 2.01% of the national total, the whole of the
industry module - carry the geometry id S4:no-native-geometry. They used to be spread across
cells on the declared industrial proxy, with an `s4_co2e_share` raster layer telling a reader
how much of each cell rested on no geometry at all. Flagging placed mass is not the same as
not placing it: the number still arrived in the cell, and the flag was a layer one had to
know to open. Those streams now contribute to the ADM1 marginal and to NO cell, their mass is
published per stream and month in outputs/pakemis_spatial_unallocated.csv, and the grid total
is strictly less than the national total by exactly that amount. tests/test_grid_cube.py
holds the identity in both terms, and holds the inequality, so a stream cannot creep back in.

WHAT SHIPS: the gas x month cube and per-category annual group in one compressed NetCDF
(native gas mass, no CO2e per cell - a GWP is one multiplication and storing it would be
invented precision), the ADM2 x month view, the provincial check (where the grid marginal
is exact by construction, where it is derived, and where it DECLARES divergence - Islamabad
International sits administratively in ICT and physically in Attock, and the cube follows
the coordinates), and the fallback declarations (an absent raster, a missing polygon, a
plantless province - substitutions as data, not log lines).

TWO CONFIGURATIONS since rc41, ROLES SWAPPED AT rc67. This file is scenario REF_2023_24,
whose residential dung is the household survey's (axis S). Its sibling
pakemis_grid_0p05_monthly_ledger.nc is configuration L, all the diverted dung burned in
households: the same weights, the two dung-cake streams' masses replaced. The L delta is
priced in each file's global attributes.

Usage:  python3 -m pkinv.report.grid_cube
Writes: outputs/pakemis_grid_0p05_monthly.nc
        outputs/pakemis_adm2_monthly.csv
        outputs/pakemis_adm2_monthly_sector.csv
        outputs/pakemis_grid_provincial_check.csv
        outputs/pakemis_grid_fallbacks.csv
        outputs/pakemis_spatial_unallocated.csv
"""

from pkinv.assets import asset_path
import collections
import csv
import os

import pkinv
from pkinv.paths import DATA, OUTPUTS
from pkinv.activity.store import read_rows
from pkinv.core.io import write_table

GASES = ("CO2", "CH4", "N2O")
NO_NATIVE_GEOMETRY = "S4:no-native-geometry"

# A SHARE BELOW THIS IS ROUNDING, NOT A FALLBACK. The located fractions are sums of ledger
# quantities, so they carry the usual float sliver - power_coal's comes out as
# 1.0000000000000002, which makes `share - share * located` land at +1.4e-17 for one province
# and negative for the next. Left alone that emits fallback events of 1e-17 and, because the
# sign flips per province, makes the cube's own ledger and the nine-year one disagree by six
# rows for no reason at all. The fractions are clamped to 1.0 and the residual must clear this
# threshold to be an event.
RESIDUAL_SHARE_FLOOR = 1e-12
# THE PERIOD, AS AN OBJECT RATHER THAN A PINNED STRING. This module used to name FY2023-24
# in nine spellings - a month tuple, a `year == "2023"` filter on the population panel, a
# `fiscal_year != "2023"` filter on the plant ledger, a `_2024.csv` filename, a NetCDF time
# origin - and each was a separate chance to key one read to the wrong year while the rest
# stayed right. That would not fail; it would place one year's mass on another year's surface
# and close every conservation test while doing it. One namedtuple carries every spelling,
# built from the registries that already publish them, so a period is chosen once and the
# spellings cannot disagree. REFERENCE and MONTHS are bound below, beside _rows.
PeriodKeys = collections.namedtuple(
    "PeriodKeys",
    "period_id months fiscal_start_year population_years label file_token days")

REFERENCE_PERIOD = "FY2023-24"
AR5 = {"CO2": 1.0, "CH4_biogenic": 28.0, "CH4_fossil": 30.0, "N2O": 265.0}

# The two ways a row of an ADM2 view can carry no number, both of them DECLARED rather than
# blank. `unresolved-in-grid` is the older one: a canonical unit with no drawable polygon,
# where silence would read as zero emissions. `unallocated-below-adm1` is this release's:
# mass that has a provincial control and no geography under it, so it is not in any cell and
# must not be summed into an ADM2 table. Both are non-numeric ON PURPOSE - a downstream sum
# cannot absorb them, and a downstream reader cannot miss them.
#
# One frozenset rather than a string literal repeated at each reader. The older literal was
# already spelled out at fifteen sites across five modules, and adding a second the same way
# is how one of the fifteen gets missed.
UNRESOLVED_IN_GRID = "unresolved-in-grid"
UNALLOCATED_BELOW_ADM1 = "unallocated-below-adm1"
DECLARED_ABSENCES = frozenset({UNRESOLVED_IN_GRID, UNALLOCATED_BELOW_ADM1})

# The provincial-check status for a stream the cube deliberately does not place. It is not a
# divergence (the grid share equals the declared share exactly, by construction); it says the
# agreement is all there is, because there is no finer claim to check.
UNALLOCATED_STATUS = "unallocated_below_adm1"

# THE THIRD SPATIAL AXIS: what a placement CLAIMS TO BE. The spatial class says how finely mass
# is placed and `geometry_available` says whether geometry exists at all; neither says whether
# the place is where the emission happens.
#
#   physical    the allocation puts mass where it is emitted
#   origin      it puts mass where the activity that generates it originates, and the release
#               is somewhere else this inventory does not hold - waste at the people rather
#               than at the landfill, the drain or the burn site
#   accounting  it puts mass where the statistic is BOOKED - road and industrial fuel at the
#               province of sale, burnt wherever the vehicle or the boiler is
#
# 88.91 Mt, 19.85% of the inventory, is not physical, and until this release every product
# added the three together and returned one number. This is the last way a reader could take a
# correct figure from this release and draw a wrong map with it.
#
# Declared, not derived, and deliberately so: a view is a property of what an activity
# statistic MEANS, and no register here holds that. The burden is carried instead by
# data/stream_geometry.csv, where a row that is not physical must name the release geography
# it does not hold, and by a test that makes the naming mechanical.
VIEWS = ("physical", "origin", "accounting")


def _rows(name, root=OUTPUTS):
    rows = read_rows(asset_path(root, name))
    if os.path.basename(name) == "facility_registry.csv":
        from pkinv.core.primary_geography import compatible_facilities
        rows = compatible_facilities(rows)
    return rows


def population_years(fiscal_start_year):
    """The calendar years a fiscal period's population is read from, and their weights.

    POPULATION IS A STOCK, NOT A FLOW (rc45). Until now a fiscal period took the population
    of the calendar year it OPENS in - FY2015-16 read 2015 - which is the value six months
    before the period's midpoint, and it is the wrong instant twice over: it is not the mean
    over the interval and it is not the middle of it.

    A fiscal year runs 1 July to 30 June, so its midpoint is 1 January. The panel's annual
    values are mid-year estimates, and 1 January sits exactly halfway between two of them, so
    the population integrated over the fiscal year is the mean of the year it opens in and
    the year it closes in. FY2015-16 is mean(2015, 2016); FY2023-24 is mean(2023, 2024), and
    the panel carries 2000 to 2024, so every period including the reference has both.

    Returned as (year, weight) pairs rather than a single label because that is the shape of
    the fact: a period reads two vintages, and a consumer that only knew how to read one is a
    consumer that would have to guess.
    """
    start = int(fiscal_start_year)
    return ((str(start), 0.5), (str(start + 1), 0.5))


def period_keys(period_id=REFERENCE_PERIOD):
    """The spellings of one fiscal period, read from the registries and never computed.

    `months` comes from data/months.csv rather than "%s%02d" arithmetic on purpose: that file
    carries the day counts and the special-period flag, and a computed tuple would be right
    about the labels and wrong about everything the labels are for."""
    periods = {r["period_id"]: r
               for r in _rows(asset_path(DATA, "periods.csv"), root="/")}
    if period_id not in periods:
        raise ValueError("unknown period %r; data/periods.csv holds %s"
                         % (period_id, ", ".join(sorted(periods))))
    row = periods[period_id]
    months = tuple(m["month_id"] for m in _rows(asset_path(DATA, "months.csv"), root="/")
                   if m["fiscal_year"] == period_id)
    if len(months) != 12:
        raise ValueError("%s carries %d months in data/months.csv"
                         % (period_id, len(months)))
    return PeriodKeys(period_id=period_id, months=months,
                      fiscal_start_year=row["fiscal_start_year"],
                      population_years=population_years(row["fiscal_start_year"]),
                      label=period_id,
                      # the reference year's products keep their historical `_2024` names:
                      # this change adds years, it does not rename files
                      file_token=row["fiscal_end_year"],
                      days=int(row["days"]))


REFERENCE = period_keys()
# MONTHS keeps its name and its meaning for every existing reader - it is now DERIVED from
# data/months.csv rather than spelled out, and asserted equal to what it always was.
MONTHS = REFERENCE.months


PANEL = "pakemis_monthly_fy2015_16_fy2024_25.csv"


def monthly_layer(period):
    """Use the canonical monthly native mass and shares for every fiscal period.

    The old reference-only path read rounded shares from a presentation table;
    multiplying those shares into annual mass lost mass at ADM1 and grid grain.
    A common monthly source avoids that separate numerical vintage.
    """
    from pkinv.report.source_streams import stream_id
    out = {}
    rows = [r for r in _rows(PANEL) if r["period_id"] == period.period_id]
    if not rows:
        raise ValueError("the monthly panel carries no row for " + period.period_id)
    for row in rows:
        module, category, subitem, gas = (row[k] for k in
                                         ("sector_id", "category", "subitem", "gas"))
        sid = stream_id(module, category, subitem, gas)
        entry = out.setdefault(sid, {"module": module, "engine_category": category,
                                     "sub_category": subitem, "gas": gas,
                                     "months": {}, "annual": 0.0})
        if row["month"] in entry["months"]:
            raise ValueError("duplicate source-stream month: " + sid + " " + row["month"])
        entry["months"][row["month"]] = float(row["share"])
        if row["native_unit"] != "Gg":
            raise ValueError("%s carries %s in %s; the cube's mass is Gg"
                             % (sid, row["native_unit"], period.period_id))
        entry["annual"] += float(row["emission_native_mass"])
    return out


def load_streams(period=None):
    """The period's streams: engine names from the monthly layer, everything else from the
    ledger, joined by stream_id - the one key that maps them one-to-one with zero mismatch.

    A YEAR CARRIES THE STREAMS IT HAS, WHICH IS NOT ALWAYS ALL OF THEM. The ledger is the
    reference year's, and three groups of streams do not exist in every earlier year: cement
    gas in FY2020-21 (the gas-curtailment year), bagasse power before FY2019-20, railway
    furnace oil before FY2021-22. Those are structural non-occurrences - there is no mass to
    place - so a year that builds 183 streams is correct, and the old
    `len(streams) != len(ledger)` equality would have called it broken. The direction that
    must still hold is the other one, and it is asserted: every stream the panel carries is a
    stream the ledger knows."""
    period = period or REFERENCE
    ledger = {r["source_stream_id"]: r for r in _rows("pakemis_source_streams.csv")}
    layer = monthly_layer(period)
    unknown = sorted(set(layer) - set(ledger))
    if unknown:
        raise ValueError("%s carries %d stream(s) the ledger does not know: %s"
                         % (period.period_id, len(unknown), ", ".join(unknown[:3])))
    if period.period_id == REFERENCE_PERIOD and set(layer) != set(ledger):
        raise ValueError("the reference year must carry every ledger stream; %d missing"
                         % len(set(ledger) - set(layer)))
    streams = {}
    for sid, entry in layer.items():
        if sid not in streams:
            led = ledger[sid]
            streams[sid] = {
                "source_stream_id": sid,
                "module": entry["module"],
                # WHERE THE GUIDELINES REPORT IT, beside the module that computed it
                # (data/stream_reporting_sector.csv, declared per stream at rc53). The cube
                # carries it so the district layer can partition a module's mass by it -
                # captive self-generation is 1.A.2 and reports under industry although the
                # power module computes it.
                "reporting_sector": led["reporting_sector"],
                "engine_category": entry["engine_category"],
                "sub_category": entry["sub_category"],
                "gas": entry["gas"],
                "fossil": led["methane_origin"] == "fossil",
                "ipcc_code": led["ipcc_code"],
                "ipcc_category": led["ipcc_category"],
                "geometry_id": led["geometry_id"],
                "spatial_profile_id": led["spatial_profile_id"],
                "spatial_class": led["spatial_class"],
                "spatial_view": led["spatial_view"],
                "emissions_Gg": (float(led["emissions_native"]) if entry["annual"] is None
                                 else entry["annual"]),
                "monthly_share": dict(entry["months"]),
            }
    stray = sorted({m for s in streams.values() for m in s["monthly_share"]}
                   - set(period.months))
    if stray:
        raise ValueError("%s carries months outside its own year: %s"
                         % (period.period_id, ", ".join(stray[:3])))
    for s in streams.values():
        total = sum(s["monthly_share"].values())
        if abs(total - 1.0) > 1e-6:
            raise ValueError("monthly shares for %s sum to %.8f"
                             % (s["source_stream_id"], total))
    from pkinv.core.primary_geography import primary_stream
    return [primary_stream(stream) for stream in streams.values()]


# --- panels ------------------------------------------------------------------------------

# The crop categories whose within-province split can be YEAR-KEYED from the PBS district
# crop panel (rc46 Wave 3). Rice cultivation splits by the period's own district rice area;
# Managed soils and Urea application by the period's total crop area over the five engine
# crops - the same lever the reference panel provides, measured for the period instead of
# borrowed from it. The livestock categories (Enteric fermentation, Manure management) stay
# on the reference panel: one census anchor is held and interpolating district herds between
# nothing and it would be invention, which is the named remainder of the backcast.
_CROP_PANEL_CATEGORIES = {"Rice cultivation": ("rice",),
                          "Managed soils": ("maize", "rice", "sugarcane", "wheat", "cotton"),
                          "Urea application": ("maize", "rice", "sugarcane", "wheat", "cotton")}
# Field burning is deliberately NOT in the table above (rc47 Wave 1): its district
# factor was the one reference borrow left in the crop family (the product's FRP-based
# 2024 split for all nine years), but the repair is not a crop-area panel - area is a
# weaker proxy for WHERE burning happens than the fires themselves, and the divergence
# table measures them 0.49 apart in D.I. Khan. The category instead carries NO district
# panel at all: the period's own FIRMS raster is the evidence at every grain below the
# province, so the raster carries the whole within-province split (factor_key_for).


def _crop_panel(period_id):
    """{crop: {adm2_id: area_kha}} for one period, QA rows excluded."""
    out = {}
    for row in _rows(asset_path(DATA, "activity", "agriculture",
                                  "crop_district_panel.csv"), root="/"):
        if row["period_id"] != period_id or row["qa_flag"] == "excluded_corrupt":
            continue
        out.setdefault(row["crop"], {})
        out[row["crop"]][row["adm2_id"]] = \
            out[row["crop"]].get(row["adm2_id"], 0.0) + float(row["area_kha"])
    return out


def agriculture_panels(period=None):
    """{engine_category: {district: weight}} - the reference product's panel, with the
    crop-driven categories overridden by the period's OWN district crop areas.

    EVERY period, the reference included, reads the crop categories from the PBS
    panel (rc47 Wave 1): the committed product's within-province crop split is the
    MapSPAM satellite proxy, the panel is the statistical record of the same split,
    and when the two disagreed (rice shares apart by up to 0.26 in a district) the
    proxy had been silently winning for the one year every golden anchors on. The
    product remains the within-district raster source and the livestock panel, and
    the disagreement ships measured in outputs/agri_reference_panel_divergence.csv
    instead of being adjudicated by a docstring.

    rc47 Wave 1, the frame fix: panel units are named by their CANONICAL name (from
    data/adm2_canonical.csv) rather than translated through the reference product's
    117-name frame. district_factors resolves every canonical name and sums units
    sharing a shape onto that shape, so collision-group children (Chiniot on Jhang's
    polygon, the Karachi districts on Karachi's) come back together at the geometry
    they actually share instead of being dropped - the old `continue` silently
    discarded 20 mainland units carrying ~5.5% of national crop area (the comment
    blamed "AJK/GB rows" the panel never contained) and re-seated their mass on
    their provinces' remaining districts.
    """
    from pkinv.core import adm2
    period = period or REFERENCE
    out = {}
    for row in _rows("district_totals_2024.csv"):
        out.setdefault(row["category"], {})
        out[row["category"]][row["district"]] = \
            out[row["category"]].get(row["district"], 0.0) + float(row["co2e_Mt_AR5"])
    canonical_name = {u["adm2_id"]: u["canonical_name"]
                      for u in adm2.load_canonical().values()}
    crops = _crop_panel(period.period_id)
    for category, wanted in _CROP_PANEL_CATEGORIES.items():
        panel = {}
        dropped = []
        for crop in wanted:
            for adm2_id, area in crops.get(crop, {}).items():
                if not adm2_id:
                    # the excluded-corrupt rows carry no id by design; their pinned
                    # areas are a record, never mass to place
                    continue
                name = canonical_name.get(adm2_id)
                if name is None:
                    dropped.append(adm2_id)
                    continue
                panel[name] = panel.get(name, 0.0) + area
        if dropped:
            raise ValueError(
                "crop panel ids outside the canonical frame: %s - the panel and "
                "adm2_canonical.csv have diverged and silence here is the rc46 "
                "frame-drop defect returning" % sorted(set(dropped)))
        if panel:
            out[category] = panel
    return out


_RESIDENTIAL_INPUTS = {}


def residential_panels(period=None):
    """{stream_word: {district: co2e}} for the period's census year.

    UNTIL rc44 THIS READ THE SHIPPED REFERENCE-YEAR PRODUCT for every period, so all nine
    years split a province by the 2023 district population - 184 stream-years of residential
    mass placed on geography measured up to eight years after the fact. The population panel
    it needs has carried 2000 to 2024 all along, and waste has read it per period since rc31.

    Only the district POPULATION moves with the period. The component magnitudes and the HIES
    urban/rural strata stay the reference year's, because that is what this sector has, and
    the cube rescales the magnitudes to each period's own provincial control anyway - what a
    period needs from this panel is its geography, not its size. The reference period is
    asserted to reproduce the shipped product exactly.
    """
    period = period or REFERENCE
    if not _RESIDENTIAL_INPUTS:
        from pkinv.sectors.residential import engine as resi_engine
        from pkinv.sectors.residential.data import ResidentialData
        data = ResidentialData()
        _RESIDENTIAL_INPUTS["data"] = data
        _RESIDENTIAL_INPUTS["comps"] = resi_engine.build_components(data)
    from pkinv.sectors.residential.gis import district_downscale as resi_gis
    rows, _totals = resi_gis.district_rows(_RESIDENTIAL_INPUTS["data"],
                                           _RESIDENTIAL_INPUTS["comps"],
                                           population_years=period.population_years)
    out = {}
    for row in rows:
        word = row["stream"].split()[0]
        out.setdefault(word, {})
        # ROUNDED TO 7dp, exactly as district_downscale.main writes the shipped product. The
        # panel used to be READ from that file, so the reference period must keep reading the
        # same numbers now that it is computed: without this the reference year would move by
        # rounding alone, and this commit is about the eight periods that borrowed it.
        out[word][row["district"]] = out[word].get(row["district"], 0.0) \
            + round(float(row["co2e_Mt_AR5"]), 7)
    return out


def waste_panel(period=None):
    """{district: population} at the period's midpoint - the declared district basis."""
    period = period or REFERENCE
    weights = dict(period.population_years)
    out = {}
    for row in _rows(asset_path(DATA, "activity", "waste", "population_district.csv"),
                     root="/"):
        weight = weights.get(row["year"])
        if weight:
            out[row["district"]] = (out.get(row["district"], 0.0)
                                    + float(row["pop_total"]) * weight)
    return out


# --- facility points ---------------------------------------------------------------------

def captive_points():
    """{province: [(lon, lat, gas_mmcfd)]} for geocoded captive plants; ICT maps onto the
    inventory's Other; a geocoded row with a blank province gets its province from the
    grid cell it lands in (resolved by the caller)."""
    out = {}
    blanks = []
    for row in _rows(asset_path(DATA, "activity", "power", "captive_register.csv"),
                     root="/"):
        if not row["latitude"].strip():
            continue
        # rc42 (S-4): rows that repeat another field for field are connection records, not
        # duplicates - the register's metered sum reconciles to OGRA's 288 MMCFD only with
        # every row (scripts/ingest_captive_register.py) - so each row keeps its own weight.
        #
        # THE WEIGHT IS THE METERED GAS (rc44). It used to be `... or 1.0`, which gave a row
        # with no gas figure the weight of a 1 MMCFD plant - three times the 0.319 MMCFD an
        # average metered plant actually reports. 204 of the 1,068 geocoded rows have no
        # figure, so 42.5 percent of the pool's weight was synthetic, and 62.2 percent of
        # Punjab's. The 204 are two populations and NEITHER wants a unit weight:
        #
        #   130 rows read "0" and every one carries an OGRA metered basis. A metered zero is
        #       a measurement, not a silence: the plant is in the return and drew no gas.
        #    74 rows are blank and every one has an empty gas_basis - NEPRA-licensed plants
        #       OGRA never metered. They are outside the mass being placed, which run_power
        #       declares as "from OGRA metered captive gas ... A FLOOR ON 1A2". Weighting
        #       them spreads metered gas over plants that contributed none of it, the same
        #       shape as the K-Electric defect one commit earlier.
        #
        # The two populations are also structurally disjoint - 99 percent of the blanks carry
        # a capacity_mw and 1 percent of the metered rows do - so the seven-row overlap
        # cannot calibrate a capacity-per-gas imputation, and inventing one here would be an
        # activity model smuggled into a spatial weight. Both go to zero, for two reasons.
        activity = float(row["gas_mmcfd"] or 0.0)
        province = {"Islamabad Capital Territory": "Other"}.get(
            row["province_region"], row["province_region"])
        record = (float(row["longitude"]), float(row["latitude"]), activity)
        if province:
            out.setdefault(province, []).append(record)
        else:
            blanks.append(record)
    return out, blanks


# Grid stream profile -> the plant ledger's fuel labels it burns. RLNG rides the gas
# stream (the engine books it there); bagasse has no FY2023-24 plant-fuel row, so the
# bagasse_grid profile stays on the fallback surface with its event.
GRID_PROFILE_FUELS = {"power_coal": ("Coal",), "power_gas": ("Gas", "RLNG"),
                      "power_rfo": ("RFO",), "power_hsd": ("HSD",),
                      "bagasse_grid": ()}


def _grid_plant_name_key(name):
    """The ledger<->coordinates join key, which now lives in sectors/power/plant_names.py.

    IT MOVED (rc44) because the generation panel is a second consumer, and a name-matching
    rule written twice is how two readers come to disagree about which station is which. It
    is unchanged: asserted to produce an identical key for all 198 station names across the
    four tables that use it.

    The import is INSIDE the function because the report layer must not import a sector
    module at import time - test_the_report_layer_imports_no_sector_module_at_import_time
    holds that, and it caught this as a module-level import."""
    from pkinv.sectors.power.plant_names import plant_key
    return plant_key(name)


# rc42 (S-1): plant_coordinates.csv first (the corroborated town-gated points), then the
# coal table for the ledger keys it does not locate - seven of the eight FY2023-24 coal
# stations, 34.7 Mt that rode built-up while GEM and Climate TRACE held their exact points
# in tables this repository already carried. The coal table is keyed by the ledger's own
# plant string, so the join is exact by construction.
# rc46 Wave 1 adds the gas/RFO/bagasse fleet (gas_plant_coordinates.csv, GEM GOGPT/GBPT
# exact points, TRACE-corroborated) - 17 stations carrying 233 TWh of the panel's nine-year
# generation that until now pooled onto built-up whenever their ledger fuel had no point.
GRID_COORDINATE_TABLES = ("plant_coordinates.csv", "coal_plant_coordinates.csv",
                          "gas_plant_coordinates.csv")


def _grid_gas_hhv():
    """The heating value the ledger's MMCFT rows convert at: the SECTOR's parameter, read,
    not a second copy of it kept here. One million cubic feet at h Btu/scf is h MMBTU, so
    at today's 1,000 this is exactly the constant it replaces and nothing moves."""
    for r in _rows("power_params.csv", root=DATA):
        if r["param"] == "captive_hhv_btu_per_scf":
            return float(r["value"])
    raise KeyError("captive_hhv_btu_per_scf is not in power_params.csv")


def _grid_fuel_ledger(fuels, period=None):
    """{plant name key: the period's fuel quantity} for the ledger rows burning one of
    `fuels`, in units commensurable WITHIN the pool."""
    # The gas pool mixes billing units (MMCFT and MMBTU); both convert to MMBTU at
    # the sector's declared 1,000 Btu/scf reference so the RELATIVE weights are
    # commensurable - the HHV choice moves nothing else here. Any unit outside this
    # table still fails loudly rather than weighting apples by oranges.
    from pkinv.sectors.power.plant_ledger import in_boundary
    period = period or REFERENCE
    to_common = {"MMBTU": 1.0, "MMCFT": _grid_gas_hhv()}
    ledger = {}
    units = set()
    for row in _rows(asset_path(DATA, "activity", "power",
                                  "plant_fuel_ledger.csv"), root="/"):
        if row["fiscal_year"] != period.fiscal_start_year or row["fuel"] not in fuels \
                or not in_boundary(row):
            continue
        key = _grid_plant_name_key(row["plant"])
        unit = row["quantity_unit"]
        factor = to_common.get(unit, 1.0) if len(fuels) > 1 or unit in to_common \
            else 1.0
        ledger[key] = ledger.get(key, 0.0) + float(row["quantity"] or 0.0) * factor
        units.add(unit)
    unconverted = units - set(to_common)
    if len(unconverted) > 1:
        raise SystemExit("grid plant pool for %r mixes units %s - the relative "
                         "weights would be meaningless" % (fuels, sorted(units)))
    return ledger


def located_activity_share(profile_id, period=None):
    """The share of a grid stream's FY2023-24 plant-ledger fuel that sits on a station
    the dispatch can locate, or None where the profile has no ledger fuel (bagasse).

    WHY IT SURVIVES rc44. It arrived in rc42 (the twentieth review's S-1b) as a
    CORRECTION. `grid_weight` pooled each province's share across that province's located
    stations and recorded nothing: a station with no point was not a fallback event - its
    fuel rode its siblings' points - so the fallback ledger alone read "1.0 located" for a
    gas fleet half of which was not. rc44's proportional fallback prices that fuel as an
    event, so the ledger no longer understates, and multiplying by this share on top of it
    squares the located fraction rather than correcting it. What survives is an
    INDEPENDENT measure of the same quantity from different inputs - ledger and coordinate
    tables only, no grid - which the source-stream ledger phase can use because it runs
    before the cube. The two must now AGREE, and a test holds them to it: that agreement
    is the check that would have caught the squaring on its own."""
    fuels = GRID_PROFILE_FUELS.get(profile_id)
    if not fuels:
        return None
    ledger = _grid_fuel_ledger(fuels, period)
    coverage = 1.0
    if sum(ledger.values()) <= 0:
        # rc47 Wave 2: the four panel years used to return None here, and grid_weight
        # read None as 1.0 - 187 Mt of the weakest-evidenced years graded S1 while
        # the blank-fuel and unmatched panel mass was silently renormalised onto the
        # located stations. The located share for a panel year is now MEASURED:
        # located-labelled GWh over the profile's labelled pool, discounted by the
        # period's fuel-labelling coverage (labelled GWh over ALL grid generation,
        # blank rows included) - the declared assumption being that the unlabelled
        # mass carries the labelled fuel mix, which is the weakest statement that
        # still refuses to pretend the blank mass does not exist.
        ledger = _panel_fuel_ledger(fuels, period or REFERENCE)
        if sum(ledger.values()) <= 0:
            return None
        labelled, total_gwh = _panel_labelling_coverage(period or REFERENCE)
        coverage = (labelled / total_gwh) if total_gwh > 0 else 1.0
    total = sum(ledger.values())
    located = set()
    for name in GRID_COORDINATE_TABLES:
        path = asset_path(DATA, "activity", "power", name)
        if not os.path.exists(path):
            continue
        for row in _rows(path, root="/"):
            key = _grid_plant_name_key(row["plant"])
            if key in ledger:
                located.add(key)
    return (sum(ledger[k] for k in located) / total) * coverage


def captive_located_share():
    """The share of the captive register's metered gas that sits on a geocoded row.

    The register carries a province for every row but a coordinate for only some, and the 37
    rows without one carry no province either - so, exactly as for the grid fleet, the
    unlocated fraction is knowable nationally and not per province."""
    total = located = 0.0
    for row in _rows(asset_path(DATA, "activity", "power", "captive_register.csv"), root="/"):
        gas = float(row["gas_mmcfd"] or 0.0)
        total += gas
        if row["latitude"].strip():
            located += gas
    return (located / total) if total > 0 else None


def _cement_census():
    """(census clinker by company token, tokens with at least one located works).

    ONE token match, shared: ippu_register_points weights with it, ippu_located_share
    measures with it, and the fallback event names companies from it. Three readers making
    the same join three times is how the three lists drift apart."""
    clinker = {}
    for row in _rows(asset_path(DATA, "activity", "ippu",
                                  "company_clinker_2023_24.csv"), root="/"):
        token = CEMENT_COMPANY_TOKENS.get(row["company"])
        if token:
            clinker[token] = clinker.get(token, 0.0) \
                + float(row["clinker_production_t"] or 0.0)
    located = set()
    for row in _rows(asset_path(DATA, "facility_registry.csv"), root="/"):
        if row["module"] != "ippu" or not row["latitude"].strip():
            continue
        if row["facility_id"].startswith("cement_"):
            located.add(row["facility_id"].split("_")[1])
    return clinker, located


def ippu_unlocated_companies():
    """Census companies with clinker and no located works, largest first.

    DERIVED, because the hand-written list it replaces named Bestway, Power and Flying, and
    rc44 located Bestway and Power - a sentence that would have gone on naming them while
    the number beside it fell from 20.75 to 0.77 percent."""
    clinker, located = _cement_census()
    return [token.title() for token, tonnes
            in sorted(clinker.items(), key=lambda kv: -kv[1])
            if token not in located and tonnes > 0]


def ippu_located_share():
    """The share of census clinker belonging to companies with at least one located works.

    Until rc44 an unlocated company's clinker was not merely unplaced: the province share was
    renormalised over the works that ARE located, so it was placed on other companies'
    plants. rc44 priced that as a fallback (20.75 percent), and this commit resolves all but
    Flying's 0.77 - whose GEM coordinate lands 4.8 km inside Chakwal while the registry, and
    Flying's own annual report, place the works in Khushab."""
    clinker, located = _cement_census()
    total = sum(clinker.values())
    if total <= 0:
        return None
    return sum(v for t, v in clinker.items() if t in located) / total


def _panel_fuel_ledger(fuels, period):
    """{plant name key: the period's fuel-labelled GWh} from the generation panel, via the
    crosswalk - the HISTORICAL pool for periods the plant-fuel ledger does not reach.

    The panel holds all nine fiscal years at plant-month grain (PBS to FY2020-21, NEPRA SIR
    after); the crosswalk resolves its 547 spellings to canonical stations or typed classes.
    Only grid_station rows whose panel fuel is one of `fuels` contribute, and the weight is
    the period's own GENERATION, not fuel: within a single-fuel pool GWh-share stands in for
    fuel-share up to heat-rate differences between stations, which is declared here rather
    than modelled - the alternative was leaving 100 percent of four years' coal on a
    built-up raster. Blank-fuel panel rows contribute nothing to the POOL - and since
    rc47 Wave 2 their mass share genuinely rides the fallback raster as a priced event
    (located_activity_share discounts by the labelling coverage); before that, this
    sentence said "typed, never spread" while the renormalisation spread it. And a
    spelling the crosswalk types system_total, captive_lane or unmapped contributes nothing
    by construction.
    """
    crosswalk = {}
    for row in _rows(asset_path(DATA, "activity", "power",
                                  "plant_name_crosswalk.csv"), root="/"):
        if row["row_class"] == "grid_station":
            crosswalk[row["panel_name"]] = row["canonical_plant"]
    ledger = {}
    label = "FY" + period.period_id[2:] if not period.period_id.startswith("FY")         else period.period_id
    for row in _rows(asset_path(DATA, "activity", "power",
                                  "generation_monthly.csv"), root="/"):
        if row["fiscal_year"] != label or row["fuel"] not in fuels or not row["gwh"]:
            continue
        canonical = crosswalk.get(row["plant"])
        if canonical is None:
            continue
        key = _grid_plant_name_key(canonical)
        ledger[key] = ledger.get(key, 0.0) + float(row["gwh"])
    return ledger


def _panel_labelling_coverage(period):
    """(fuel-labelled GWh, total GWh) over the period's grid_station panel rows.

    The denominator includes blank-fuel rows - the mass whose existence the old
    construction renormalised away. system_total, captive_lane and unmapped rows are
    outside both terms: they are not grid stations, whatever their labels say."""
    crosswalk = {}
    for row in _rows(asset_path(DATA, "activity", "power",
                                  "plant_name_crosswalk.csv"), root="/"):
        if row["row_class"] == "grid_station":
            crosswalk[row["panel_name"]] = row["canonical_plant"]
    label = "FY" + period.period_id[2:] if not period.period_id.startswith("FY") \
        else period.period_id
    labelled = total = 0.0
    for row in _rows(asset_path(DATA, "activity", "power",
                                  "generation_monthly.csv"), root="/"):
        if row["fiscal_year"] != label or not row["gwh"]:
            continue
        if row["plant"] not in crosswalk:
            continue
        gwh = float(row["gwh"])
        total += gwh
        if (row["fuel"] or "").strip():
            labelled += gwh
    return labelled, total



_SHAPE_INDEX_CACHE = {}


def district_index_by_shape(grid):
    """{geoBoundaries shapeID: the grid's district index}, built once.

    FOUR identical copies of this join stood in this module (adm2_view_rows,
    the module view, the stream view and the residential view) and a fifth was
    about to be written for the curated-district lane. The ADM2 polygon index is
    the join between a geography the catalog knows by shape_id and a raster that
    knows it by position in `grid.districts`; a join written five times is how two
    readers come to disagree about which polygon is which, which is the defect
    this module already carries a comment about for the ADM1 ordering.
    """
    # KEYED ON THE DISTRICT NAME LIST, not on id(grid). An identity key is wrong twice
    # over: CPython reuses an id once the object is collected, so a later grid could read
    # an earlier grid's map - and this map decides which polygon a station's mass lands in
    # - and entries for dead grids would never be released. The map is a pure function of
    # the ordered district names and the ADM2 frame, so the names ARE the key.
    key = tuple(grid.districts)
    if key not in _SHAPE_INDEX_CACHE:
        import json
        from pkinv.core.gis.grid import ADM2_PATH
        name_to_idx = {name: i for i, name in enumerate(grid.districts)}
        out = {}
        with open(ADM2_PATH, encoding="utf-8") as handle:
            for feature in json.load(handle)["features"]:
                props = feature["properties"]
                if props["shapeName"] in name_to_idx:
                    out[props["shapeID"]] = name_to_idx[props["shapeName"]]
        _SHAPE_INDEX_CACHE[key] = out
    return _SHAPE_INDEX_CACHE[key]


def _curated_station_districts():
    """{plant name key: adm2_id} from the curated station-district record.

    data/activity/power/grid_plant_district.csv - the project's own 2024 compilation over
    NEPRA/OGRA/SNGPL/SSGC/OCAC records, ingested with its printed district resolved through
    data/adm2_canonical.csv (a spelling that resolves nowhere raises at ingest). It places
    107 thermal stations where the three coordinate tables resolve 76, and until 2026-10-07
    the spatial allocation did not read it at all: the districts were ingested, verified and
    unused, which is the four-layer mistake CLAUDE.md is about.

    It is used for GEOGRAPHY ONLY, which is the scope its own banner declares. Its fuel
    column is a per-plant-year capability label (GAS+RFO+RLNG, Dual) and not a quantity, and
    its emission columns are held apart in evidence/workbook_emissions_crosscheck.csv
    precisely so they cannot be mistaken for this inventory's own estimates.

    THREE JOIN RULES, in order, each one refusing rather than guessing.

    1. The exact name key, as everywhere else in this module.
    2. The key of the name plant_name_crosswalk.csv canonicalises it to. This is how HUBCO
       reaches Hub Power - a record this repository already holds, not a new inference.
    3. A STRICT SUBSET of a coordinate-table key, of at least two tokens, and only when
       every workbook row matching it names ONE district. Rule 3 exists for TPS Guddu: the
       workbook prints "TPS Guddu" and "TPS Guddu (GENCO-II)" where the coordinate table
       prints "(Units 5-10)" and "(Units 14-16)", so no one-to-one match exists - but both
       workbook rows say Kashmore, so the answer does not depend on which block is which.
       The two-token floor is not a tuning constant, it is the rule's whole safety: measured
       over the live tables a one-token subset matches a COMPANY and not a station, and
       three such matches would have been wrong - Foundation Wind Energy (Sindh coast) would
       have taken Foundation Power Dharki's Ghotki, Liberty Power Tech. would have taken
       Liberty Power's Ghotki, and Sapphire Electric would have taken a district on the
       strength of the single word "Sapphire". With the floor the join is exact 38, crosswalk
       -resolved, subset-unanimous 5, ambiguous 0. An ambiguous subset is refused outright.
    """
    crosswalk = {}
    for row in _rows(asset_path(DATA, "activity", "power",
                                  "plant_name_crosswalk.csv"), root="/"):
        if row["canonical_plant"]:
            crosswalk[row["panel_name"]] = row["canonical_plant"]
    claims = {}
    for row in _rows(asset_path(DATA, "activity", "power",
                                  "grid_plant_district.csv"), root="/"):
        adm2_id = (row.get("adm2_id") or "").strip()
        if not adm2_id:
            continue
        for name in {row["plant"], crosswalk.get(row["plant"], row["plant"])}:
            claims.setdefault(_grid_plant_name_key(name), set()).add(adm2_id)
    out = {key: next(iter(ids)) for key, ids in claims.items() if len(ids) == 1}
    # Rule 3, applied only where rules 1 and 2 left a coordinate-table station unplaced.
    for key in _grid_coordinate_keys():
        if key in out:
            continue
        candidates = set()
        for claim, ids in claims.items():
            if len(claim) >= SUBSET_JOIN_MIN_TOKENS and set(claim) < set(key):
                candidates |= ids
        if len(candidates) == 1:
            out[key] = next(iter(candidates))
    return out


SUBSET_JOIN_MIN_TOKENS = 2


def _grid_coordinate_keys():
    """Every name key the three coordinate tables carry."""
    keys = set()
    for name in GRID_COORDINATE_TABLES:
        path = asset_path(DATA, "activity", "power", name)
        if not os.path.exists(path):
            continue
        for row in _rows(path, root="/"):
            keys.add(_grid_plant_name_key(row["plant"]))
    return keys


def curated_district_indices(grid, keys=None):
    """{plant name key: grid district index} for curated stations whose ADM2 unit has a
    polygon in the live frame. A unit with no geometry is left out rather than coerced.
    """
    from pkinv.core import adm2 as adm2_core
    shapes = adm2_core.adm2_to_shape()
    by_shape = district_index_by_shape(grid)
    out = {}
    for key, adm2_id in _curated_station_districts().items():
        if keys is not None and key not in keys:
            continue
        shape = shapes.get(adm2_id)
        index = by_shape.get(shape) if shape else None
        if index is not None:
            out[key] = index
    return out


def grid_plant_points(fuels, period=None, with_keys=False):
    """{province: [(lon, lat, own_fuel_quantity)]} for corroborated grid stations
    whose plant-fuel ledger rows FOR THAT PERIOD carry one of `fuels`.

    The ledger holds FY2019-20..FY2023-24; those years weight stations by METERED FUEL.
    An earlier period's pool comes from the generation panel through the crosswalk
    (_panel_fuel_ledger): the period's own fuel-labelled GWh per canonical station - a
    generation weight standing in for a fuel weight, declared as such. Before rc46 an early
    period got an empty pool and four years of grid power sat wholly on built-up; before
    rc44 the reference fleet was silently used for every period. The ledger stays first
    where it exists, because metered fuel beats generated GWh as a fuel weight.

    The join is EXACT on the numeral-preserving name key: a miss sends the plant to
    the fallback pool (conservative), never onto a neighbour's point - the
    containment join that would bind Bin Qasim II's fuel to Bin Qasim I's point was
    measured and refused. Units are per-fuel consistent in the ledger (MMCFT for
    gas, tonnes otherwise) and only relative weight within a fuel pool is used.

    THE PROVINCE COMES FROM THE CURATED RECORD WHERE THERE IS ONE (2026-10-07, the
    twenty-second review's item 7). It used to come from the province of the RASTER CELL the
    coordinate falls in, and for a station near a provincial line a 0.05 degree cell is about
    5.5 km across. Seven stations sit 0.13 to 3.36 km from a boundary and the cell put every
    one of them in the wrong province: Hub Power, both TPS Guddu blocks and Tapal Energy where
    the curated record and the source record AGREE and only the frame dissents; Mangla and
    Attock Gen. where the raster and the ADM2 polygon contradict EACH OTHER, so no frame value
    is preferable; and China Power Hub, which no ADM2 polygon contains at all and whose
    coordinate table carried a raster-derived province of Sindh while Hub Power, 1.11 km away
    in the same cell, carried Balochistan from its record - two stations on one site in two
    provinces, invisible to any check that compares a table against the raster.

    This does NOT move a provincial total. point_sources reads the same curated record, so
    province_shares.csv and pakemis_adm1_by_year already book these stations correctly; the
    control was right and the placement inside it was not. What moves is which province's
    nested split a point participates in, and therefore its cell and its district.

    WHAT IT DOES NOT FIX, and I predicted otherwise before measuring it. PointProjection
    below refuses to move a point to its exact district when that district lies outside the
    province the point was pooled under, because the provincial marginal is a control and the
    district is not. I expected the curated province to end that refusal for all seven. It
    ends it for TWO - Mangla and Attock Gen., where the ADM2 polygon agrees with the record -
    and not for the other five, because for four of them the POLYGON disagrees with the record
    as well as the raster does (Hub Power and Tapal Energy on the Sindh/Balochistan line, both
    TPS Guddu blocks on the Sindh/Punjab one), and China Power Hub falls in no polygon at all.
    The boundary audit said this and I should have read it as written: for four of seven the
    defect is in boundary GEOMETRY, not only in the 5.5 km rasterisation.

    So the outcome is a strict improvement rather than a repair. Before, a misplaced point was
    pooled into the WRONG province and its mass distributed entirely within it. Now it is
    pooled into the right one, and where the polygon denies the district the mass goes to the
    fallback surface at its own cell, where the nested split keeps it in the right province.
    The province is right for all seven; the district is landed exactly for two and left to
    the cell's own geometry for five. Claiming a district the polygon denies would be
    inventing one, and grid_plant_province_sources() publishes which case each station is in
    rather than leaving the reader to infer it.
    """
    from pkinv.core.geography import PROVINCES as PROVS, curated_province
    from pkinv.core.gis.grid import build_grid
    ledger = _grid_fuel_ledger(fuels, period)
    if not ledger and fuels:
        ledger = _panel_fuel_ledger(fuels, period or REFERENCE)
    grid = build_grid()
    curated = _curated_station_provinces()
    out = {}
    located = set()
    for name in GRID_COORDINATE_TABLES:
        path = asset_path(DATA, "activity", "power", name)
        if not os.path.exists(path):
            continue
        for row in _rows(path, root="/"):
            key = _grid_plant_name_key(row["plant"])
            qty = ledger.get(key)
            if not qty or key in located:
                continue
            lon, lat = float(row["longitude"]), float(row["latitude"])
            province = curated.get(key)
            if province is None:
                col, row_i = (~grid.transform) * (lon, lat)
                row_i, col = int(row_i), int(col)
                pid = int(grid.province_id[row_i, col]) if (
                    0 <= row_i < grid.height and 0 <= col < grid.width) else -1
                province = PROVS[pid] if 0 <= pid < len(PROVS) else None
            if province is not None:
                out.setdefault(province, []).append(
                    (lon, lat, qty, key) if with_keys else (lon, lat, qty))
                located.add(key)
    return out


def grid_plant_province_sources(fuels=None, period=None):
    """Which province each located grid station was pooled under, and on whose authority.

    Published so the correction is auditable rather than asserted: a reader can see which
    stations take a curated province, which fall back to the raster cell, and - the row that
    matters - which of the curated ones DISAGREE with the cell they stand in. That last set is
    the boundary audit's finding, measured from the live tables rather than transcribed.
    """
    from pkinv.core.geography import PROVINCES as PROVS
    from pkinv.core.gis.grid import build_grid, district_index_at
    grid = build_grid()
    curated = _curated_station_provinces()
    districts = _curated_station_districts()
    rescues = curated_district_indices(grid)
    out = []
    for name in GRID_COORDINATE_TABLES:
        path = asset_path(DATA, "activity", "power", name)
        if not os.path.exists(path):
            continue
        for row in _rows(path, root="/"):
            key = _grid_plant_name_key(row["plant"])
            lon, lat = float(row["longitude"]), float(row["latitude"])
            col, row_i = (~grid.transform) * (lon, lat)
            row_i, col = int(row_i), int(col)
            pid = int(grid.province_id[row_i, col]) if (
                0 <= row_i < grid.height and 0 <= col < grid.width) else -1
            cell = PROVS[pid] if 0 <= pid < len(PROVS) else ""
            rec = curated.get(key)
            booked = rec or cell
            index = district_index_at([(lon, lat)])[0]
            dp = grid.district_province[index] if index >= 0 else ""
            rescue = rescues.get(key)
            rescue_province = grid.district_province[rescue] if rescue is not None else ""
            if not booked:
                verdict = "unlocated"
            elif index < 0:
                verdict = "FRAME GAP: no ADM2 polygon contains the point"
            elif dp == booked:
                verdict = "district agrees with the booked province"
            else:
                verdict = "CROSSING: the ADM2 polygon puts this point in %s" % dp
            # The repair column. A point-in-polygon district OUTSIDE the booked province
            # used to send the mass to the fallback surface; the curated record now places
            # it where its own district is, provided that district's polygon majority keeps
            # the province. Stated per station so a reader sees which rule placed each one.
            if verdict.startswith(("CROSSING", "FRAME GAP")):
                if rescue is None:
                    placement = ("fallback surface at the point's cell: the record names "
                                 "no district for this station")
                elif rescue_province != booked:
                    placement = ("fallback surface at the point's cell: the curated "
                                 "district %s is majority %s, not %s"
                                 % (districts.get(key, ""), rescue_province, booked))
                else:
                    placement = ("curated district %s (polygon majority %s)"
                                 % (districts.get(key, ""), rescue_province))
            elif not booked:
                placement = "not placed"
            else:
                placement = "the point's own ADM2 polygon"
            out.append({"plant": row["plant"], "table": name,
                        "curated_province": rec or "",
                        "raster_cell_province": cell,
                        "adm2_polygon_province": dp,
                        "booked_province": booked,
                        "authority": "curated record" if rec else "raster cell",
                        "agrees_with_cell": "" if not rec else
                                            ("yes" if rec == cell else "NO"),
                        "district_verdict": verdict,
                        "curated_district": districts.get(key, ""),
                        "curated_district_province": rescue_province,
                        "adm2_placement": placement})
    return out


def _curated_station_provinces():
    """{name key: inventory province} from the curated station record.

    ONE record, read once. data/activity/power/coal_plant_coordinates.csv also carries a
    Province column and it is RASTER-DERIVED (scripts/ingest_coal_plant_coordinates.py took
    it from the grid), which is how China Power Hub came to sit in Sindh while the station
    1.11 km away on the same site sat in Balochistan. That column is renamed
    raster_province so no reader can mistake it for a record; this function reads
    plant_locations.csv and nothing else.
    """
    from pkinv.core.geography import curated_province
    out = {}
    for row in _rows(asset_path(DATA, "activity", "power", "plant_locations.csv"),
                     root="/"):
        name = (row.get("province") or "").strip()
        if name:
            out[_grid_plant_name_key(row["plant"])] = curated_province(name)
    return out


# rc62: the industrial liquid profiles whose PROVINCE vector has a year axis, and the surface
# label that records it. The label exists because the weight registry keys year-awareness on
# (surface, district_panel) and district_panel is empty for every diffuse industry stream: the
# only key otherwise available is ("builtup", ""), which nine profiles share, so year-keying it
# would claim a year axis for industry gas, two fugitive, two IPPU and two transport streams
# that do not have one. The raster is unchanged - only the province vector is dated.
LIQUID_AREA_PROFILES = frozenset(
    {"industry_furnace_oil", "industry_diesel", "industry_minor_liquids"})
LIQUID_AREA_SURFACE = "builtup+ocac_area_shares"


class PointProjection:
    """The exact district vector that belongs beside a point-built raster.

    A point-supported stream has two different right answers. On the GRID a facility's mass
    belongs in the cell containing it - a raster's unit is the cell. At ADM2 it belongs in the
    district containing it, and deriving that from the cell throws the point away: the cell is
    split by its own district area fractions, so a plant near a boundary is apportioned by the
    geometry of its neighbourhood rather than by where it stands.

    Measured over the facility register: 2,063 of 12,529 located facilities sit in a cell that
    straddles a district line, and for those a mean 29 percent of the mass lands in a district
    the facility is not in. 203 keep under a tenth of their own mass and several keep none -
    a captive plant declared in Islamabad with nothing of it in Islamabad.

    So this accumulates, beside the raster, the vector the raster cannot express: point mass to
    the point's own district, and FALLBACK mass left to project through the cells, because a
    fallback surface genuinely is a raster and has no point to be exact about.
    """

    def __init__(self, grid):
        import numpy as np
        self.grid = grid
        self.vector = {}
        self.fallback = np.zeros((grid.height, grid.width), dtype=np.float64)
        self._district = {}
        # points whose exact district lies outside the province they were pooled under
        self.crossings = 0
        # of those, the ones a curated district record rescued, and the mass each class
        # carries. The counters are READ: grid_point_district_sources publishes them, and
        # before 2026-10-07 `crossings` was incremented and never looked at, so a
        # regression in the single most exposed placement in the grid fleet - up to 43.9%
        # of a profile-period's pool stands on the five boundary stations - could not have
        # been noticed from any output.
        self.curated_rescues = 0
        self.crossing_share = 0.0
        self.rescued_share = 0.0

    def add_points(self, points, scale, province=None, curated=None):
        """`points` are (lon, lat, activity) or (lon, lat, activity, plant key); `scale` is
        the share they carry between them. `curated` is {plant key: district index} from the
        curated station-district record, consulted only when the frame denies the point.

        THE PROVINCE IS A CONTROL AND THE DISTRICT IS NOT (rc45). A point is pooled under the
        province its CELL lands in - province_id is rasterised all_touched - while the exact
        point-in-polygon district may belong to a neighbouring province, because the two
        geographies disagree along a boundary. Moving a point's mass to its exact district
        would then move it across a provincial line, and the provincial share vector is the
        control the cube must reproduce exactly: shape_marginals is already NESTED for this
        reason, splitting a cell only among claimant shapes of its own province.

        So a point whose district sits outside the province it was allocated to keeps the
        raster projection - its mass goes to the fallback surface at its own cell, where the
        nested split will keep it in the right province. Correcting a district must not cost a
        provincial marginal; that trade is not available.

        THE CURATED RECORD IS CONSULTED BEFORE THAT FALLBACK (2026-10-07). The trade above is
        unavailable only because the point-in-polygon answer is the sole candidate district.
        It is not: grid_plant_district.csv names a district for 105 stations, and a NAMED
        district is adjudicated by the majority of its own cells in the ADM1 control rather
        than by the one cell a near-boundary coordinate happens to fall in. For the five
        stations the frame denies, every curated district's polygon returns the booked
        province - Lasbela 703 cells Balochistan, Kashmore 128 Sindh, Karachi 124 Sindh,
        Rawalpindi 294 Punjab, Attock 219 Punjab - so naming the district lands the mass in
        the right district AND keeps the provincial marginal, which the point could not do.
        The guard stays: a curated district whose own polygon majority leaves the pooled
        province is refused exactly as the point was, so the control is never traded.
        """
        from pkinv.core.gis.grid import district_index_at
        import numpy as np
        total = float(sum(p[2] for p in points))
        if total <= 0:
            return
        unknown = [(p[0], p[1]) for p in points if (p[0], p[1]) not in self._district]
        if unknown:
            self._district.update(zip(unknown, district_index_at(unknown)))
        inverse = ~self.grid.transform
        for point in points:
            lon, lat, activity = point[0], point[1], point[2]
            key = point[3] if len(point) > 3 else None
            index = self._district[(lon, lat)]
            share = scale * activity / total
            if province is not None and (
                    index < 0 or self.grid.district_province[index] != province):
                self.crossings += 1
                self.crossing_share += share
                rescue = (curated or {}).get(key)
                if rescue is not None and self.grid.district_province[rescue] == province:
                    self.curated_rescues += 1
                    self.rescued_share += share
                    self.vector[rescue] = self.vector.get(rescue, 0.0) + share
                    continue
                column, row = inverse * (lon, lat)
                row, column = int(row), int(column)
                if 0 <= row < self.grid.height and 0 <= column < self.grid.width:
                    self.fallback[row, column] += share
                continue
            self.vector[index] = self.vector.get(index, 0.0) + share

    def add_fallback(self, block, scale):
        self.fallback = self.fallback + block * scale

    def finish(self, divisor):
        """Normalised by the same divisor the raster was, so the two describe one placement."""
        if divisor:
            self.vector = {i: v / divisor for i, v in self.vector.items()}
            self.fallback = self.fallback / divisor
        return self


def _place_inside_province(grid, arr, activity, province, province_mask,
                           district_index, cell):
    """Put `activity` in cells of `province`, preferring the station's curated district.

    Returns True when it placed the mass. The district's cells are intersected with the
    province mask rather than trusted whole: a district's polygon majority can be the
    pooled province while some of its cells are not, and a cell outside the province is
    the very thing this function exists to avoid.

    The fallback is the NEAREST cell of the pooled province, by grid distance from the
    station's own cell. Nearest rather than spread, because the station is a point: a
    boundary station belongs in the cell across the line from where the raster put it,
    not smeared over a province.
    """
    import numpy as np
    if district_index is not None:
        cells = (grid.district_id == district_index) & province_mask
        count = int(cells.sum())
        if count:
            arr[cells] += activity / count
            return True
    rows, cols = np.nonzero(province_mask)
    if not rows.size:
        return False
    distance = (rows - cell[0]) ** 2 + (cols - cell[1]) ** 2
    nearest = int(np.argmin(distance))
    arr[rows[nearest], cols[nearest]] += activity
    return True


def grid_weight(ctx, grid, stream, shares, projection_key=None):
    """The Wave-5 grid-fleet weight: per province, corroborated stations weighted by
    their OWN FY2023-24 fuel from the plant ledger (per-object activity), the
    builtup fallback for provinces whose share has no located-and-fuelled plant of
    this stream's fuel - every fallback a declared event, the captive pattern.
    Coordinates outrank labels here too: a station pools under the province its
    point lands in."""
    import numpy as np

    from pkinv.core.gis import cube as cube_core
    fuels = GRID_PROFILE_FUELS.get(stream["spatial_profile_id"], ())
    period = getattr(ctx, "period", None)
    by_province = grid_plant_points(fuels, period, with_keys=True) if fuels else {}
    # The curated district for every station in this pool, so a point the ADM2 frame denies
    # can still land in the district its record names (see PointProjection.add_points).
    pooled = {p[3] for pts in by_province.values() for p in pts}
    curated_districts = curated_district_indices(grid, pooled) if pooled else {}
    # What fraction of this stream's fuel is on a plant we can place at all. None where the
    # profile has no ledger fuel class (bagasse), in which case the whole share falls back as
    # it always has.
    located_share = located_activity_share(stream["spatial_profile_id"], period) if fuels \
        else None
    if located_share is not None:
        located_share = min(1.0, located_share)
    weight = np.zeros((grid.height, grid.width), dtype=np.float64)
    projection = PointProjection(grid)
    inv = ~grid.transform
    from pkinv.core.geography import PROVINCES as PROVS
    for province, share in shares.items():
        if share <= 0:
            continue
        points = by_province.get(province)
        if points:
            arr = np.zeros_like(weight)
            province_mask = None
            for point in points:
                lon, lat, activity = point[0], point[1], point[2]
                col, row_i = inv * (lon, lat)
                row_i, col = int(row_i), int(col)
                if not (0 <= row_i < grid.height and 0 <= col < grid.width):
                    continue
                # A POINT MAY NOT PUT ITS MASS IN ANOTHER PROVINCE'S CELL, and until
                # 2026-10-07 this line could. A station used to be pooled under the
                # province of its own cell, so pool and cell agreed by construction and
                # the provincial marginal held trivially. Pooling under the CURATED
                # province broke that: a station whose record says Balochistan and whose
                # 0.05 degree cell reads Sindh added to Sindh's raster sum while drawing
                # on Balochistan's share. pakemis_grid_provincial_check.csv caught it as
                # 18 exact_by_construction rows breaching 2e-6 in paired, opposite
                # amounts - 0.0083 Mt of coal between Sindh and Balochistan, 0.0767 Mt of
                # furnace oil between Punjab and Other.
                #
                # The station is in the province its record names; the cell is simply
                # 5.5 km across. So the mass goes to the curated DISTRICT's cells inside
                # the pooled province - the same set the ADM2 vector uses, which is what
                # keeps the two views from disagreeing - and to the nearest cell of the
                # pooled province where no district resolves. Neither is a trade: the
                # marginal is reproduced and the geography is the record's.
                if grid.province_id[row_i, col] != PROVS.index(province):
                    if province_mask is None:
                        province_mask = grid.province_id == PROVS.index(province)
                    placed = _place_inside_province(
                        grid, arr, activity, province, province_mask,
                        curated_districts.get(point[3] if len(point) > 3 else None),
                        (row_i, col))
                    if placed:
                        continue
                arr[row_i, col] += activity
            total = float(arr.sum())
            if total > 0:
                placed = share * (located_share if located_share is not None else 1.0)
                weight += arr * (placed / total)
                projection.add_points(points, placed, province,
                                      curated=curated_districts)
                residual = share - placed
                if residual <= RESIDUAL_SHARE_FLOOR:
                    continue
                ctx.fallbacks.append(cube_core.FallbackEvent(
                    source_stream_id=stream["source_stream_id"], scope="province",
                    declared="grid station points", used="builtup",
                    province=province, weight_share=residual,
                    reason="%.1f%% of this stream's national ledger fuel sits on plants with "
                           "no coordinate; that fraction of %s's share rides built-up rather "
                           "than the located stations. The register gives no province to a "
                           "plant it cannot locate, so the fraction is national"
                           % (100.0 * (1.0 - located_share), province)))
                mask = cube_core.province_cells(grid, stream, province)
                block = ctx.proxies["builtup"] * mask
                block_total = float(block.sum())
                if block_total <= 0:
                    block = mask * ctx.cell_area
                    block_total = float(block.sum())
                if block_total > 0:
                    weight += block * (residual / block_total)
                    projection.add_fallback(block, residual / block_total)
                continue
        ctx.fallbacks.append(cube_core.FallbackEvent(
            source_stream_id=stream["source_stream_id"], scope="province",
            declared="grid station points", used="builtup",
            province=province, weight_share=share,
            reason="no corroborated station with own %s fuel in %s"
                   % ("/".join(fuels) if fuels else "(no ledger fuel class)",
                      province)))
        mask = cube_core.province_cells(grid, stream, province)
        block = ctx.proxies["builtup"] * mask
        total = float(block.sum())
        if total <= 0:
            block = mask * ctx.cell_area
            total = float(block.sum())
        weight += block * (share / total)
        projection.add_fallback(block, share / total)
    divisor = float(weight.sum())
    if projection_key is not None:
        ctx.point_projections[projection_key] = projection.finish(divisor)
    return weight / divisor


# Producer-census company -> the facility_id company token (cement_<token>_<site>).
# All sixteen census companies map since rc30 (Fecto's clinker arrived with the
# census completion); a census company with no registered plant fails loudly
# rather than dropping clinker on the floor.
CEMENT_COMPANY_TOKENS = {
    "Fecto Cement Limited": "fecto",
    "Lucky Cement Limited": "lucky", "D.G. Khan Cement Company Limited": "dgk",
    "Attock Cement Pakistan Limited": "attock", "Power Cement Limited": "power",
    "Cherat Cement Company Limited": "cherat", "Pioneer Cement Limited": "pioneer",
    "Thatta Cement Company Limited": "thatta", "Bestway Cement Limited": "bestway",
    "Kohat Cement Company Limited": "kohat", "Dandot Cement Company Limited": "dandot",
    "Gharibwal Cement Limited": "gharibwal", "Dewan Cement Limited": "dewan",
    "Fauji Cement Company Limited": "fauji",
    "Maple Leaf Cement Factory Limited": "maple",
    "Flying Cement Company Limited": "flying",
}


def brick_kiln_points(grid):
    """{province: [(lon, lat, 1.0)]} for the 11,272 surveyed kilns - uniform weights,
    because no per-kiln output is held; the point DENSITY is the allocation, and it is
    the same density the WAPE-benchmarked ADM2 product was derived from (rc24).

    Kilns pool under the province THEIR CELL rasterises into, not the register's
    label column - coordinates outrank labels (the grid-fleet rule), and the first
    build of this function proved why: register-Punjab kilns on the ICT line put
    0.5% of Punjab's share in the wrong province marginal."""
    from pkinv.core.geography import PROVINCES
    inv = ~grid.transform
    out = {}
    for row in _rows(asset_path(DATA, "ml", "brick_kilns_pk.csv"), root="/"):
        lon, lat = float(row["lon"]), float(row["lat"])
        col, row_i = inv * (lon, lat)
        row_i, col = int(row_i), int(col)
        if not (0 <= row_i < grid.height and 0 <= col < grid.width):
            continue
        pid = int(grid.province_id[row_i, col])
        if not (0 <= pid < len(PROVINCES)):
            continue
        out.setdefault(PROVINCES[pid], []).append((lon, lat, 1.0))
    return out


def brick_kiln_weight(ctx, grid, stream, shares, projection_key=None):
    """rc47 Wave 4: the brick-coal stream on its own register - provincial shares
    split over each province's kiln points (object-uniform), builtup fallback with a
    declared event for a province with share and no surveyed kiln."""
    import numpy as np

    from pkinv.core.gis import cube as cube_core
    by_province = brick_kiln_points(grid)
    weight = np.zeros((grid.height, grid.width), dtype=np.float64)
    projection = PointProjection(grid)
    inv = ~grid.transform
    for province, share in shares.items():
        if share <= 0:
            continue
        points = by_province.get(province)
        if points:
            arr = np.zeros_like(weight)
            for lon, lat, w in points:
                col, row_i = inv * (lon, lat)
                row_i, col = int(row_i), int(col)
                if 0 <= row_i < grid.height and 0 <= col < grid.width:
                    arr[row_i, col] += w
            total = float(arr.sum())
            if total > 0:
                weight += arr * (share / total)
                projection.add_points(points, share, province)
                continue
        ctx.fallbacks.append(cube_core.FallbackEvent(
            source_stream_id=stream["source_stream_id"], scope="province",
            declared="brick kiln points", used="builtup",
            province=province, weight_share=share,
            reason="no surveyed kiln in %s; its share of the brick-coal stream "
                   "rides built-up" % province))
        mask = cube_core.province_cells(grid, stream, province)
        block = ctx.proxies["builtup"] * mask
        total = float(block.sum())
        if total <= 0:
            block = mask * ctx.cell_area
            total = float(block.sum())
        weight += block * (share / total)
        projection.add_fallback(block, share / total)
    divisor = float(weight.sum())
    if projection_key is not None:
        ctx.point_projections[projection_key] = projection.finish(divisor)
    return weight / divisor


def ippu_register_points():
    """{province: [(lon, lat, weight)]} for located IPPU register plants (cement).

    The weight is OBJECT-PARTIAL activity: the producer census reports clinker per
    COMPANY, so a company's tonnage splits uniformly across its own located works -
    per-plant clinker is not published anywhere acquired, and inventing a split
    would claim precision the census does not carry. Since rc30 every located
    plant's company is inside the census, so the mean-weight residual path for
    census-less companies is empty by construction (it remains for honesty)."""
    from pkinv.core.geography import PROVINCES as PROVS
    from pkinv.core.gis.grid import build_grid
    clinker = {}
    for row in _rows(asset_path(DATA, "activity", "ippu",
                                  "company_clinker_2023_24.csv"), root="/"):
        token = CEMENT_COMPANY_TOKENS.get(row["company"])
        if token is None:
            raise SystemExit("census company %r has no facility token - a plant "
                             "map that silently drops clinker misplaces it"
                             % row["company"])
        clinker[token] = clinker.get(token, 0.0) \
            + float(row["clinker_production_t"] or 0.0)
    located = {}
    for row in _rows(asset_path(DATA, "facility_registry.csv"), root="/"):
        if row["module"] != "ippu" or not row["latitude"].strip():
            continue
        if not row["facility_id"].startswith("cement_"):
            continue
        token = row["facility_id"].split("_")[1]
        located.setdefault(token, []).append(
            (float(row["longitude"]), float(row["latitude"])))
    weights = []
    for token, points in located.items():
        tonnage = clinker.get(token)
        for lon, lat in points:
            weights.append((lon, lat, tonnage / len(points) if tonnage else None))
    known = [w for _lon, _lat, w in weights if w]
    mean_w = sum(known) / len(known) if known else 1.0
    grid = build_grid()
    out = {}
    for lon, lat, w in weights:
        col, row_i = (~grid.transform) * (lon, lat)
        row_i, col = int(row_i), int(col)
        pid = int(grid.province_id[row_i, col]) if (
            0 <= row_i < grid.height and 0 <= col < grid.width) else -1
        if 0 <= pid < len(PROVS):
            out.setdefault(PROVS[pid], []).append((lon, lat, w or mean_w))
    return out


def ippu_weight(ctx, grid, stream, shares, projection_key=None):
    """The IPPU register weight: located cement works at their company's census
    clinker (object-partial activity), builtup fallback per province with a
    declared event - the captive/grid pattern at this register's honest grain."""
    import numpy as np

    from pkinv.core.gis import cube as cube_core
    by_province = ippu_register_points()
    located = ippu_located_share()
    if located is not None:
        located = min(1.0, located)
    weight = np.zeros((grid.height, grid.width), dtype=np.float64)
    projection = PointProjection(grid)
    inv = ~grid.transform
    for province, share in shares.items():
        if share <= 0:
            continue
        points = by_province.get(province)
        if points:
            arr = np.zeros_like(weight)
            for lon, lat, activity in points:
                col, row_i = inv * (lon, lat)
                row_i, col = int(row_i), int(col)
                if 0 <= row_i < grid.height and 0 <= col < grid.width:
                    arr[row_i, col] += activity
            total = float(arr.sum())
            if total > 0:
                placed = share * (located if located is not None else 1.0)
                weight += arr * (placed / total)
                projection.add_points(points, placed, province)
                residual = share - placed
                if residual <= RESIDUAL_SHARE_FLOOR:
                    continue
                ctx.fallbacks.append(cube_core.FallbackEvent(
                    source_stream_id=stream["source_stream_id"], scope="province",
                    declared="ippu register points", used="builtup",
                    province=province, weight_share=residual,
                    reason="%.1f%% of census clinker belongs to companies with no located "
                           "works (%s); that fraction of %s's share rides built-up rather "
                           "than other companies' plants"
                           % (100.0 * (1.0 - located),
                              ", ".join(ippu_unlocated_companies()) or "none", province)))
                mask = cube_core.province_cells(grid, stream, province)
                block = ctx.proxies["builtup"] * mask
                block_total = float(block.sum())
                if block_total <= 0:
                    block = mask * ctx.cell_area
                    block_total = float(block.sum())
                if block_total > 0:
                    weight += block * (residual / block_total)
                    projection.add_fallback(block, residual / block_total)
                continue
        ctx.fallbacks.append(cube_core.FallbackEvent(
            source_stream_id=stream["source_stream_id"], scope="province",
            declared="ippu register points", used="builtup",
            province=province, weight_share=share,
            reason="no located cement works in %s" % province))
        mask = cube_core.province_cells(grid, stream, province)
        block = ctx.proxies["builtup"] * mask
        total = float(block.sum())
        if total <= 0:
            block = mask * ctx.cell_area
            total = float(block.sum())
        weight += block * (share / total)
        projection.add_fallback(block, share / total)
    divisor = float(weight.sum())
    if projection_key is not None:
        ctx.point_projections[projection_key] = projection.finish(divisor)
    return weight / divisor


def airport_points(period=None):
    """[(lon, lat, the period's domestic movements)] over the national airports."""
    period = period or REFERENCE
    movements = {}
    for row in _rows(asset_path(DATA, "activity", "aviation", "movements_airport.csv"),
                     root="/"):
        if row["year"] == period.fiscal_start_year:
            movements[row["icao"]] = float(row["com_dom_mv"] or 0.0)
    points = []
    for row in _rows(asset_path(DATA, "activity", "aviation", "airports.csv"), root="/"):
        if not str(row.get("latitude_deg", "")).strip():
            continue
        weight = movements.get(row["airport_icao"], 0.0)
        if weight > 0:
            points.append((float(row["longitude_deg"]), float(row["latitude_deg"]),
                           weight))
    if not points:
        raise ValueError("no airport carries domestic movements in %s" % period.label)
    return points


# --- the build ---------------------------------------------------------------------------

def captive_weight(ctx, grid, stream, shares, projection_key=None):
    """The captive point-pooling weight, lifted from build() in rc9 so the ADM2
    bracket module can price points-vs-fallback without a second full build.
    Behaviour identical: coordinates outrank labels, province pools, builtup
    fallback with a declared FallbackEvent."""
    import numpy as np
    # EVERY point is pooled by the province its coordinates land in, not by the
    # register's administrative label. First draft pooled by the register column and
    # the Punjab marginal missed by 0.0097: several plants are registered under one
    # province with coordinates in another (border industrial estates), and forcing
    # the declared share onto label-pools puts mass in cells outside the labelled
    # province. Coordinates outrank labels - the aviation principle, applied here.
    by_register, blanks = captive_points()
    located = captive_located_share()
    if located is not None:
        located = min(1.0, located)
    from pkinv.core.gis import cube as cube_core
    from pkinv.core.geography import PROVINCES as PROVS
    by_province = {}
    for pool in list(by_register.values()) + [blanks]:
        for lon, lat, activity in pool:
            col, row_i = (~grid.transform) * (lon, lat)
            row_i, col = int(row_i), int(col)
            pid = int(grid.province_id[row_i, col]) if (
                0 <= row_i < grid.height and 0 <= col < grid.width) else -1
            if 0 <= pid < len(PROVS):
                by_province.setdefault(PROVS[pid], []).append((lon, lat, activity))
    
    weight = np.zeros((grid.height, grid.width), dtype=np.float64)
    projection = PointProjection(grid)
    for province, share in shares.items():
        if share <= 0:
            continue
        points = by_province.get(province)
        if points:
            arr = np.zeros_like(weight)
            inv = ~grid.transform
            for lon, lat, activity in points:
                col, row_i = inv * (lon, lat)
                row_i, col = int(row_i), int(col)
                if 0 <= row_i < grid.height and 0 <= col < grid.width:
                    arr[row_i, col] += activity
            total = float(arr.sum())
            if total > 0:
                placed = share * (located if located is not None else 1.0)
                weight += arr * (placed / total)
                projection.add_points(points, placed, province)
                residual = share - placed
                if residual <= RESIDUAL_SHARE_FLOOR:
                    continue
                ctx.fallbacks.append(cube_core.FallbackEvent(
                    source_stream_id=stream["source_stream_id"], scope="province",
                    declared="captive register points", used="builtup",
                    province=province, weight_share=residual,
                    reason="%.1f%% of the register's metered gas sits on rows with no "
                           "coordinate; that fraction of %s's share rides built-up. The "
                           "unlocated rows carry no province either, so the fraction is "
                           "national" % (100.0 * (1.0 - located), province)))
                mask = cube_core.province_cells(grid, stream, province)
                block = ctx.proxies["builtup"] * mask
                block_total = float(block.sum())
                if block_total <= 0:
                    block = mask * ctx.cell_area
                    block_total = float(block.sum())
                if block_total > 0:
                    weight += block * (residual / block_total)
                    projection.add_fallback(block, residual / block_total)
                continue
        ctx.fallbacks.append(cube_core.FallbackEvent(
            source_stream_id=stream["source_stream_id"], scope="province",
            declared="captive register points", used="builtup",
            province=province, weight_share=share,
            reason="no geocoded captive plant in %s" % province))
        mask = cube_core.province_cells(grid, stream, province)
        block = ctx.proxies["builtup"] * mask
        total = float(block.sum())
        if total <= 0:
            block = mask * ctx.cell_area
            total = float(block.sum())
        weight += block * (share / total)
        projection.add_fallback(block, share / total)
    divisor = float(weight.sum())
    if projection_key is not None:
        ctx.point_projections[projection_key] = projection.finish(divisor)
    return weight / divisor


def _gwp_for(stream):
    return AR5["CH4_fossil" if (stream["gas"] == "CH4" and stream["fossil"])
               else "CH4_biogenic" if stream["gas"] == "CH4"
               else stream["gas"]]


def _methane_origin(stream):
    if stream["gas"] != "CH4":
        return ""
    return "fossil" if stream["fossil"] else "biogenic"


def load_ledger_streams(reference_streams):
    """The residential streams under configuration L, from the shipped monthly L product.

    rc41 (the nineteenth review's S-1): L differs from the reference in exactly two
    streams - the dung-cake CH4 and N2O magnitudes under the ledger dung basis - and in
    nothing else: the residential engine assigns no spatial profile per basis
    (downscale.PROXY_MAP keys on the subitem), so every L stream rides the SAME weight the
    reference stream rides, and the L grid is the reference grid with those two streams'
    masses replaced. The identity is asserted here and again in the tests rather than
    assumed: a stream set that differs, a profile that differs, or a non-dung magnitude
    that differs is a build failure, not a silent rescale.
    """
    from pkinv.core import configurations as conf
    from pkinv.report.source_streams import stream_id
    ref = {s["source_stream_id"]: s for s in reference_streams if s["module"] == "residential"}
    by_stream = {}
    for row in _rows("pakemis_monthly_ledger_2024.csv"):
        if row["configuration_id"] != conf.LEDGER:
            raise ValueError("ledger monthly product carries configuration %r" % row["configuration_id"])
        sid = stream_id("residential", row["category"], row["subitem"], row["gas"])
        entry = by_stream.setdefault(sid, {"months": {}, "annual": 0.0})
        entry["months"][row["month"]] = float(row["share"])
        entry["annual"] += float(row["emissions_Gg"])
    if set(by_stream) != set(ref):
        raise ValueError("ledger monthly product names %d residential streams, the ledger %d: "
                         "only in one - %s"
                         % (len(by_stream), len(ref), sorted(set(by_stream) ^ set(ref))[:5]))
    out = []
    for sid, base in ref.items():
        entry = by_stream[sid]
        for month, share in base["monthly_share"].items():
            if abs(entry["months"].get(month, 0.0) - share) > 1e-6:
                raise ValueError("%s: the L monthly profile differs from the reference in %s "
                                 "(%.8f vs %.8f) - L changes magnitudes, never timing"
                                 % (sid, month, entry["months"].get(month, 0.0), share))
        stream = dict(base)
        stream["configuration_id"] = conf.LEDGER
        if "dung" in base["sub_category"].lower():
            stream["emissions_Gg"] = entry["annual"]
        elif abs(entry["annual"] - base["emissions_Gg"]) > 1e-6 * max(1.0, base["emissions_Gg"]):
            raise ValueError("%s is not a dung stream and differs under L (%.8f vs %.8f)"
                             % (sid, entry["annual"], base["emissions_Gg"]))
        # a non-dung stream keeps the REFERENCE mass to the bit: the L product's 8-dp
        # rounding must not become a 1e-8 Gg difference in cells L does not touch
        out.append(stream)
    return out


def _new_accumulator(grid):
    import numpy as np
    acc = {"grid": grid, "view_gas_month": {}, "category_annual": {}, "category_view": {},
           "view_co2e": {}, "total_co2e": np.zeros((grid.height, grid.width), dtype=np.float64),
           "marginals": {}, "check_rows": [], "module_shape_month": {}, "module_outside": {},
           "unallocated": [], "stream_shape": {}, "stream_outside": {}, "surfaces": [],
           "view_gas_shape_month": {}, "view_gas_outside_month": {},
           "module_shape_month_co2e": {}, "module_outside_co2e": {},
           "captured_cells": {}, "exceptions": [], "streams": []}
    for view in VIEWS:
        for gas in GASES:
            acc["view_gas_month"][(view, gas)] = np.zeros((12, grid.height, grid.width),
                                                          dtype=np.float64)
            # THE DISTRICT LEG OF THE SAME ACCUMULATION (rc45). The aggregate ADM2 view used
            # to project the RASTER through the nested fraction matrix while the sector leg
            # projected each stream's own vector, and the two agreed only because both were
            # the raster. Once a point-supported stream projects from its points, a raster
            # projection is a second vintage of the same geography - and the partition test
            # measured the disagreement at 57.44 Gg. One accumulation now feeds both.
            acc["view_gas_shape_month"][(view, gas)] = np.zeros(
                (12, len(grid.districts)), dtype=np.float64)
            acc["view_gas_outside_month"][(view, gas)] = np.zeros(12, dtype=np.float64)
    return acc


def build(with_district_factors=True, ledger=True, period=None, capture_cells=None,
          configuration_id=None):
    """The reference cube and, with `ledger`, configuration L beside it under
    result["ledger"] - the same accumulators, the same weights (cache hits by
    construction), the residential streams swapped for their L magnitudes.

    `period` selects the fiscal year to place. It defaults to the reference period, and every
    read it keys is the same read the module made when the year was a literal."""
    import numpy as np

    period = period or REFERENCE
    months = period.months

    from pkinv.core.gis import cube as cube_core
    from pkinv.core.gis.grid import build_grid
    from pkinv.core.geography import PROVINCES

    grid = build_grid()
    # The weight functions take (ctx, grid, stream, shares) and cannot grow a period argument
    # without touching every dispatch entry; the period rides the context they already have,
    # and it is passed at CONSTRUCTION because the context builds period-dependent rasters.
    ctx = cube_core.Context(grid, period)
    streams = load_streams(period)
    from pkinv.core import configurations as conf
    configuration_id = conf.canonical(configuration_id or conf.REFERENCE)
    if configuration_id not in conf.ALL:
        raise ValueError("unknown GHG spatial configuration " + configuration_id)
    if configuration_id != conf.REFERENCE:
        ledger = False
        configured = {}
        for row in _rows("pakemis_ghg_configuration_monthly.csv"):
            if row["period_id"] != period.period_id or row["configuration_id"] != configuration_id:
                continue
            entry = configured.setdefault(row["component_id"], {"mass": 0.0, "months": {}})
            entry["mass"] += float(row["emission_native_mass"])
            entry["months"][row["month"]] = float(row["share"])
        expected = {stream["source_stream_id"] for stream in streams}
        if set(configured) != expected:
            raise ValueError("configuration stream identities differ: " + str(sorted(set(configured) ^ expected)))
        for stream in streams:
            values = configured[stream["source_stream_id"]]
            stream["emissions_Gg"] = values["mass"]
            stream["monthly_share"] = values["months"]
            stream["configuration_id"] = configuration_id

    agri = agriculture_panels(period)
    resi = residential_panels(period)
    waste = waste_panel(period) if with_district_factors else {}
    factor_cache = {}

    def factor_key_for(stream):
        if not with_district_factors:
            return None, None
        module = stream["module"]
        if module == "agriculture":
            if stream["engine_category"] == "Field burning of residues":
                # rc47 Wave 1: no district panel - the period's own FIRMS fire raster
                # carries the whole within-province split (see _CROP_PANEL_CATEGORIES
                # note). A panel here would either borrow 2024's fires or substitute
                # crop area for observed burning; both lose to the raster.
                return None, None
            return ("agri", stream["engine_category"]), agri.get(stream["engine_category"])
        if module == "residential":
            word = stream["sub_category"].split()[0]
            return ("resi", word), resi.get(word)
        if module == "waste":
            return ("waste", "population"), waste
        return None, None

    def factors_for(stream):
        key, panel = factor_key_for(stream)
        if key is None or panel is None:
            return None, None
        if key not in factor_cache:
            start = len(ctx.fallbacks)
            factor_cache[key] = cube_core.district_factors(
                ctx, panel, stream["source_stream_id"])
            # rc41: the panel's events belong to every stream that rides the panel
            ctx.factor_events[key] = list(ctx.fallbacks[start:])
        return factor_cache[key], key

    def share_vector(stream):
        shares = ctx.sector_shares(stream["module"])
        return shares[stream["spatial_profile_id"]]

    def cached(key, make):
        """A weight built once; the fallback events it emitted are kept under its key so
        every stream that later hits the cache is credited with them (rc41, S-4)."""
        if key not in ctx.weight_cache:
            start = len(ctx.fallbacks)
            ctx.weight_cache[key] = make()
            ctx.weight_events[key] = list(ctx.fallbacks[start:])
        return ctx.weight_cache[key]

    took = {}

    def rail_surface():
        from pkinv.sectors.railways.data import RailwaysData
        from pkinv.sectors.railways.gis import run_gis as rail_gis
        surf = rail_gis.fuel_surface(grid, RailwaysData())
        # Clip to in-country cells before normalising: the network is entirely
        # inside Pakistan, and the ~0.05% of line mass that lands in cells whose
        # centre falls outside the ADM1 rasterisation is an edge artefact of
        # midpoint binning, not emissions at sea.
        surf = surf * (grid.province_id >= 0)
        return surf / float(surf.sum())

    def yard_surface():
        from pkinv.core.gis.lines import burn_points
        from pkinv.sectors.railways.gis import network as rail_network
        loaded = rail_network.load_yards()
        yards = burn_points(grid, loaded)
        yards = yards * (grid.province_id >= 0)
        # A pure point weight: the seven divisional yards are where they are, and their
        # district is the district containing them, not their cells' apportionment.
        projection = PointProjection(grid)
        projection.add_points([(lon, lat, activity) for lon, lat, activity in loaded], 1.0)
        ctx.point_projections[("points", "rail_yards")] = projection.finish(1.0)
        return yards / float(yards.sum())

    def waste_site_surface(base, stream_id=""):
        """The factored waste weight, with covered districts' mass re-seated at their sites.

        rc46 Wave 5, the kiln coverage-mask pattern on the waste register: 56 OSM landfill
        polygons (area-weighted centroid points) plus the two ClimateTRACE solid-waste
        sites, each serving the district that contains it. The input is the SAME
        provincial-share x district-panel x population weight the diffuse branch ships,
        so the district (and therefore ADM1) marginals are conserved by construction:
        within a COVERED district that district's factored mass moves to its sites, split
        by mapped area where the register has one and equally otherwise; every uncovered
        district is untouched. The first build of this wave took the raw population
        raster as the base instead and silently re-drew the district attribution the
        PBS panel controls - the provincial marginal check caught it.
        """
        import numpy as np
        base = base.astype(np.float64).copy()
        sites = []
        # OSM disposal polygons are retained as a separate historical alternative.
        # The compatible primary uses independently sourced sites only; uncovered
        # mass retains its declared origin geography rather than a invented landfill.
        for row in _rows(asset_path(DATA, "activity", "waste",
                                      "climatetrace_waste_sites_pak.csv"), root="/"):
            # solid-waste sites only: 25 of the 27 TRACE rows are wastewater
            # treatment plants and belong to a different category's geography
            if "solid" in (row.get("subsector") or "").lower():
                sites.append((float(row["longitude"]), float(row["latitude"]), 1.0))
        district = grid.district_id
        province = grid.province_id
        covered = {}
        for lon, lat, w in sites:
            col, row_i = (~grid.transform) * (lon, lat)
            row_i, col = int(row_i), int(col)
            if not (0 <= row_i < grid.height and 0 <= col < grid.width):
                continue
            did = int(district[row_i, col])
            if did < 0:
                continue
            # The re-seat region is the district x province-raster INTERSECTION, not the
            # district alone: 13 of the 58 sites sit in border cells whose province label
            # disagrees with their district's (Rawalpindi dumps in ICT-labelled cells,
            # Lasbela's on the Karachi line), and re-seating a whole border district onto
            # them moved the ADM1 marginal. Keyed this way both the district and the
            # province marginal are conserved exactly; the sliver of a border district
            # that lies in the other province's cells simply stays diffuse.
            covered.setdefault((did, int(province[row_i, col])),
                               []).append((row_i, col, w))
        import numpy as np
        base_total = float(base.sum())
        province_mass = {}
        covered_mass = {}
        for (did, pid), cells in covered.items():
            mask = (district == did) & (province == pid)
            region_mass = float(base[mask].sum())
            if region_mass <= 0:
                continue
            covered_mass[pid] = covered_mass.get(pid, 0.0) + region_mass
            base[mask] = 0.0
            total_w = sum(w for _r, _c, w in cells)
            for row_i, col, w in cells:
                base[row_i, col] += region_mass * w / total_w
        # rc47 Wave 3: the uncovered share is PRICED. Until now this construction
        # emitted no event, so the ledger read located_mass_fraction = 1.0 for a
        # stream whose mapped sites carry 24.9% of the mass - the decomposition's
        # located column reported the construction's own silence. Each province's
        # population-raster remainder is an event; the class stays S2 either way,
        # but the fraction beside it stops lying.
        from pkinv.core.geography import PROVINCES as PROVS
        for pid, pname in enumerate(PROVS):
            pmask = province == pid
            pm = float(np.where(pmask, base, 0.0).sum()) + 0.0
            # province mass measured BEFORE re-seat equals after (conserving), so
            # base post-re-seat serves; covered_mass is what sits at sites.
            cm = covered_mass.get(pid, 0.0)
            uncovered = pm - cm
            if base_total <= 0 or uncovered <= 1e-12:
                continue
            ctx.fallbacks.append(cube_core.FallbackEvent(
                source_stream_id=stream_id, scope="province",
                declared="waste disposal site points", used="population raster",
                province=pname, weight_share=uncovered / base_total,
                reason="no mapped disposal site serves these districts; %.1f%% of "
                       "%s's share keeps the population raster - 58 sites cover 21 "
                       "of ~134 districts and this is the measured remainder"
                       % (100.0 * uncovered / pm if pm > 0 else 0.0, pname)))
        return base / base.sum()

    def wwtp_surface(base, stream_id=""):
        """The factored wastewater weight, with each plant's SERVED share re-seated.

        rc47 Wave 3, the fractional variant of the SWDS re-seat: HydroWASTE's 25
        Pakistani WWTPs carry coordinates AND a served population, so within a covered
        district only min(1, POP_SERVED / district population) of the district's mass
        moves to its plant - the treated share, approximately - and the rest stays on
        the population raster, because Pakistani domestic wastewater is dominantly
        UNTREATED discharge and concentrating a whole district at a treatment plant
        would misplace exactly the mass the category is mostly made of. DECLARED
        LIMITATION: served population stands in for the treated-emission share; the
        treated/open-drain MCF difference is not applied here (it lives in the
        magnitude engine), so the plant share is an upper bound on the plant's
        emission share. The uncovered remainder is priced per province, as for SWDS.
        """
        import numpy as np
        from pkinv.core import adm2
        from pkinv.core.geography import PROVINCES as PROVS
        base = base.astype(np.float64).copy()
        base_total = float(base.sum())
        pop = waste_panel(period)
        canonical = adm2.load_canonical()
        district = grid.district_id
        province = grid.province_id
        plants = {}
        for row in _rows(asset_path(DATA, "activity", "waste",
                                      "hydrowaste_pak.csv"), root="/"):
            lon, lat = float(row["LON_WWTP"]), float(row["LAT_WWTP"])
            served = float(row["POP_SERVED"] or 0.0)
            col, row_i = (~grid.transform) * (lon, lat)
            row_i, col = int(row_i), int(col)
            if not (0 <= row_i < grid.height and 0 <= col < grid.width):
                continue
            did = int(district[row_i, col])
            if did < 0 or served <= 0:
                continue
            plants.setdefault((did, int(province[row_i, col])),
                              []).append((row_i, col, served))
        moved_by_province = {}
        for (did, pid), cells in plants.items():
            mask = (district == did) & (province == pid)
            region_mass = float(base[mask].sum())
            if region_mass <= 0:
                continue
            name = grid.districts[did]
            try:
                district_pop = pop.get(name) or pop.get(
                    canonical[adm2.resolve(name)]["canonical_name"], 0.0)
            except KeyError:
                district_pop = 0.0
            served_total = sum(w for _r, _c, w in cells)
            frac = min(1.0, served_total / district_pop) if district_pop > 0 else 0.0
            if frac <= 0:
                continue
            moved = region_mass * frac
            base[mask] *= (1.0 - frac)
            for row_i, col, w in cells:
                base[row_i, col] += moved * w / served_total
            moved_by_province[pid] = moved_by_province.get(pid, 0.0) + moved
        for pid, pname in enumerate(PROVS):
            pmask = province == pid
            pm = float(np.where(pmask, base, 0.0).sum())
            plant_mass = moved_by_province.get(pid, 0.0)
            remainder = pm - 0.0  # base already holds post-re-seat mass incl. plants
            uncovered = pm - plant_mass
            if base_total <= 0 or uncovered <= 1e-12:
                continue
            ctx.fallbacks.append(cube_core.FallbackEvent(
                source_stream_id=stream_id, scope="province",
                declared="WWTP points at served share", used="population raster",
                province=pname, weight_share=uncovered / base_total,
                reason="wastewater outside the plants' served populations - %.1f%% of "
                       "%s's share, the dominantly untreated part - keeps the "
                       "population raster; 25 HydroWASTE plants, served share capped "
                       "at the district population, MCF difference declared unapplied"
                       % (100.0 * uncovered / pm if pm > 0 else 0.0, pname)))
        return base / base.sum()

    def lng_points():
        """(lon, lat, weight) for the two FSRUs - equal weights, no send-out split held."""
        out = []
        for row in _rows(asset_path(DATA, "activity", "fugitives",
                                      "lng_terminal_coordinates.csv"), root="/"):
            out.append((float(row["longitude"]), float(row["latitude"]), 1.0))
        return out

    def flare_points_for_year(fiscal_start, field_types=None):
        """(lon, lat, bcm) per flare site for the period's own calendar year.

        The fiscal year FYn-(n+1) reads calendar year n as a spatial proxy;
        the periods overlap for six months, with no strict majority. This is
        labelled calendar_activity_proxy in the spatial evidence register; the product's columns run 2012-2025 so every period resolves. A site
        with zero volume that year carries zero weight and its cell gets nothing, which
        is the honest reading of a flare that did not burn.

        rc47 Wave 3: `field_types` filters on the register's own Field Type column
        (GAS 62 / OIL 47 / NA 21 sites), which the twenty-first review found the
        allocation never read - 3.59 Mt of gas-segment mass sat on OIL and untyped
        flares. The NA sites are INCLUDED in every pool, declared: an untyped flare is
        evidence of flaring, not evidence of the other field type, and excluding 21
        sites on missing metadata would trade a typed error for a coverage hole.
        """
        year = str(max(2012, min(2025, int(fiscal_start))))
        out = []
        for row in _rows(asset_path(DATA, "activity", "fugitives",
                                      "flare_sites_pak.csv"), root="/"):
            if field_types is not None:
                ftype = (row.get("Field Type") or "NA").strip().upper() or "NA"
                if ftype not in field_types:
                    continue
            bcm = float(row.get(year) or 0.0)
            if bcm > 0:
                out.append((float(row["Longitude"]), float(row["Latitude"]), bcm))
        return out

    # The register's own typing decides which sites a segment may ride (rc47 Wave 3):
    # a gas-production tonne on an OIL field's flare was the review's 3.59 Mt finding.
    # NA sites serve both pools, declared in flare_points_for_year.
    _FLARE_FIELD_TYPES = {"fugitive_gas_prod": ("GAS", "NA"),
                          "fugitive_oil_prod": ("OIL", "NA")}

    def flare_weight(ctx_, grid_, stream, shares, projection_key):
        """Provincial shares split across each province's own field-type-matched flare
        sites by flared volume, uniform fallback for provinces with share and no
        matching flare - the grid_weight construction on a different register."""
        import numpy as np
        from pkinv.core.geography import PROVINCES as PROVS
        points = flare_points_for_year(
            period.fiscal_start_year,
            _FLARE_FIELD_TYPES.get(stream["spatial_profile_id"]))
        by_province = {}
        for lon, lat, bcm in points:
            col, row_i = (~grid_.transform) * (lon, lat)
            row_i, col = int(row_i), int(col)
            pid = int(grid_.province_id[row_i, col]) if (
                0 <= row_i < grid_.height and 0 <= col < grid_.width) else -1
            if 0 <= pid < len(PROVS):
                by_province.setdefault(PROVS[pid], []).append((lon, lat, bcm))
        weight = np.zeros((grid_.height, grid_.width), dtype=np.float64)
        proj = PointProjection(grid_)
        for province, share in shares.items():
            if share <= 0:
                continue
            sites = by_province.get(province, [])
            total = sum(b for _l, _t, b in sites)
            if sites and total > 0:
                for lon, lat, bcm in sites:
                    col, row_i = (~grid_.transform) * (lon, lat)
                    weight[int(row_i), int(col)] += share * bcm / total
                proj.add_points(sites, share, province=province)
            else:
                mask = grid_.province_mask(province)
                # uniform means per square kilometre, never per cell: cells shrink
                # with latitude and a ones-array would overweight the north
                area = ctx.proxies.get("uniform")
                fallback = area if area is not None else ctx.cell_area
                m = np.where(mask, fallback, 0.0)
                if m.sum() > 0:
                    weight += share * m / m.sum()
                    proj.fallback += share * m / m.sum()
                ctx.weight_events.setdefault(projection_key, []).append({
                    "scope": "raster", "declared": "flare points",
                    "used": "uniform", "province": province,
                    "weight_share": share,
                    "reason": "no flare site recorded in this province this year"})
        ctx.point_projections[projection_key] = proj.finish(1.0)
        total = weight.sum()
        return weight / total if total > 0 else weight

    def weight_for(stream):
        """(weight, cache key, factor key, surface label). Every branch records what it
        distributes mass BY, at the branch, so the derived spatial class rests on what
        the cube did rather than on a mirror of this dispatch written somewhere else.
        data/geometry_sets.csv declares the same fact for readers that never run the
        cube, and tests/test_spatial_decomposition.py holds the two together."""
        geometry = stream["geometry_id"]
        module = stream["module"]
        if geometry == "network:pak_rail":
            took["network:pak_rail"] = "declared_judgement"
            key = ("network", "pak_rail")
            return cached(key, rail_surface), key, None, "rail_network_line_density"
        if geometry == "points:pak_rail_yards":
            took["points:pak_rail_yards"] = "object_uniform"
            # The rc11 rail re-base's non-traction category: workshops and power
            # houses at the seven divisional yards - facility points, not the line
            # network, which is exactly why the stream claims S2 while traction
            # keeps the network's S1.
            key = ("points", "rail_yards")
            return cached(key, yard_surface), key, None, "rail_yard_points"
        if geometry == "points:wwtp_hydrowaste":
            took["points:wwtp_hydrowaste"] = "object_partial_activity"
            factors, factor_key = factors_for(stream)
            key = ("points", "wwtp", stream["spatial_profile_id"])
            return cached(key, lambda: wwtp_surface(
                cube_core.diffuse_weight(ctx, stream, share_vector(stream), factors),
                stream["source_stream_id"])), key, \
                factor_key, "wwtp_points+population_fallback"
        if geometry == "points:waste_disposal_sites":
            took["points:waste_disposal_sites"] = "object_partial_activity"
            factors, factor_key = factors_for(stream)
            key = ("points", "waste_sites", stream["spatial_profile_id"])
            return cached(key, lambda: waste_site_surface(
                cube_core.diffuse_weight(ctx, stream, share_vector(stream), factors),
                stream["source_stream_id"])), key, \
                factor_key, "waste_site_points+population_fallback"
        if geometry == "facilities:lng_terminals":
            # rc46 Wave 5: the two FSRUs, located at Wave 0 from GEM's exact-tagged
            # coordinates. No per-terminal send-out is held, so the two points weigh
            # equally - object_uniform, declared, and the geometry_sets row that read
            # "0 of 2 located" is retired by this branch.
            took["facilities:lng_terminals"] = "object_uniform"
            key = ("points", "lng_terminals")
            return cached(key, lambda: cube_core.point_weight(
                ctx, lng_points(), stream["source_stream_id"], key)), \
                key, None, "lng_terminal_points"
        if geometry == "points:wb_flares":
            # rc46 Wave 5: the field-sited upstream segments ride the World Bank flare
            # sites, weighted by each site's OWN YEAR's flared volume (the product carries
            # 2012-2025 per site) within the provincial shares - so upstream fugitives are
            # year-keyed like everything else this release touched. A province with share
            # but no flare falls back to uniform, priced as an event.
            took["points:wb_flares"] = "per_object_activity"
            # The stream's own provincial profile is part of the identity: oil and gas
            # segments carry different share vectors, and a key without the profile let
            # every segment inherit whichever weight was built first. The rc47 field-type
            # filter is a function of the same profile id, so this key covers it too.
            key = ("points", "wb_flares", period.fiscal_start_year,
                   stream["spatial_profile_id"])
            return cached(key, lambda: flare_weight(ctx, grid, stream,
                                                    share_vector(stream), key)), \
                key, None, "flare_points+uniform_fallback"
        if geometry == "facilities:airports_domestic":
            took["facilities:airports_domestic"] = "per_object_activity"
            key = ("points", "airports")
            return cached(key, lambda: cube_core.point_weight(
                ctx, airport_points(period), stream["source_stream_id"], key)), \
                key, None, "airport_points"
        if geometry == "facilities:power_captive":
            took["facilities:power_captive"] = "object_partial_activity"
            key = ("points", "captive")
            return cached(key, lambda: captive_weight(ctx, grid, stream, share_vector(stream), key)), \
                key, None, "captive_register_points+builtup_fallback"
        if geometry == "points:pak_brick_kilns":
            # rc47 Wave 4: the brick-coal stream at last rides the register the
            # screening built - 11,272 surveyed kilns, object-uniform.
            took["points:pak_brick_kilns"] = "object_uniform"
            key = ("points", "brick_kilns", stream["spatial_profile_id"])
            return cached(key, lambda: brick_kiln_weight(
                ctx, grid, stream, share_vector(stream), key)), \
                key, None, "brick_kiln_points+builtup_fallback"
        if geometry == "facilities:ippu_register":
            # Wave 5: located cement works at their company's census clinker
            # (the census is company-grained, so the split within a company is
            # object-uniform - object-partial activity, S2 at the honest grain).
            # rc47 Wave 4: the industry cement-COAL stream rides this geometry
            # too, at its own provincial profile - the profile id joins the key
            # so the two streams cannot inherit each other's vectors (the rc46
            # flare lesson).
            took["facilities:ippu_register"] = "object_partial_activity"
            key = ("points", "ippu", stream["spatial_profile_id"])
            return cached(key, lambda: ippu_weight(ctx, grid, stream, share_vector(stream), key)), \
                key, None, "ippu_register_points+builtup_fallback"
        if geometry == "facilities:power_grid":
            # Wave 5: located stations weighted by their own plant-ledger fuel,
            # builtup fallback per province with a declared event - the captive
            # pattern, which is what answered the recorded objection to naive
            # points ("the whole fleet on the located quarter"). The class is
            # per_object_activity at the fleet's honest geocoded fraction.
            took["facilities:power_grid"] = "per_object_activity"
            key = ("points", "grid", stream["spatial_profile_id"])
            return cached(key, lambda: grid_weight(ctx, grid, stream, share_vector(stream), key)), \
                key, None, "grid_station_points+builtup_fallback"
        took[geometry] = "raster_or_administrative"
        factors, factor_key = factors_for(stream)
        raster = id_raster(stream)
        key = ("diffuse", module, stream["spatial_profile_id"], raster, factor_key)
        # rc62: the industrial liquids get a surface label of their own. The RASTER is still
        # built-up and the within-province split is unchanged; what is different is that their
        # PROVINCE vector is read from the period's own OCAC area pages where the panel prints
        # twelve provincial months. The weight registry keys year-awareness on (surface,
        # district_panel), and the district_panel is empty for every diffuse industry stream -
        # so without this label the only available key would be ("builtup", ""), which nine
        # profiles share, and year-keying it would have claimed a year axis for industry gas,
        # two fugitive streams, two IPPU streams and two transport streams that do not have one.
        surface = (LIQUID_AREA_SURFACE
                   if stream["spatial_profile_id"] in LIQUID_AREA_PROFILES else raster)
        return cached(key, lambda: cube_core.diffuse_weight(
            ctx, stream, share_vector(stream), factors)), key, factor_key, surface

    def id_raster(stream):
        # the cache key component naming which raster raster_for would choose,
        # WITHOUT emitting a fallback event twice
        from pkinv.core.gis import proxy_map
        if stream["module"] == "agriculture":
            name = proxy_map.gis_proxy(stream["spatial_profile_id"],
                                       stream["sub_category"], ctx.proxies)
            # the same held-layer routing raster_for applies (rc13): field burning rides
            # the FIRMS layer whenever it is loaded; the record must say what the cube did
            if stream["engine_category"].startswith("Field burning") \
                    and "firms_fire" in ctx.proxies:
                name = "firms_fire"
            return name
        from pkinv.core.declared import match_prefix
        declared = match_prefix(ctx.registry_rows, stream["module"],
                                stream["engine_category"], stream["sub_category"],
                                "raster_proxy", "grid proxy")
        return declared if declared in ctx.proxies else "cropland"

    def price_events(stream, key, factor_key, acc):
        """rc41 (S-2, S-4): every fallback the stream's surface or panel emitted, priced
        for THIS stream - its own mass, its own gas, its own methane origin - as the
        fraction of its national weight that rode the substitute."""
        shares = share_vector(stream) if factor_key is not None else {}
        gwp = _gwp_for(stream)
        for event in ctx.weight_events.get(key, []) + ctx.factor_events.get(factor_key, []):
            if "weight_share" in event:
                weight_share = float(event["weight_share"])
            elif "fraction" in event:
                weight_share = float(shares.get(event["province"], 0.0)) * float(event["fraction"])
            else:
                weight_share = 1.0
            affected = stream["emissions_Gg"] * weight_share
            acc["exceptions"].append({
                "source_stream_id": stream["source_stream_id"], "module": stream["module"],
                "gas": stream["gas"], "methane_origin": _methane_origin(stream),
                "scope": event["scope"], "declared": event["declared"], "used": event["used"],
                "province": event.get("province", ""), "shape": event.get("shape", ""),
                "weight_share": weight_share, "affected_Gg": affected,
                "affected_Mt_AR5": affected * gwp / 1000.0, "reason": event["reason"]})

    # --- accumulate ----------------------------------------------------------------------
    # ACCUMULATED PER VIEW, and the total derived by summing over views. A view says whether
    # a placement is where the emission happens (physical), where the activity that generates
    # it originates (origin - waste, placed at the people rather than at the landfill), or
    # where the statistic is booked (accounting - road and industrial fuel, placed at the
    # point of sale rather than at the road). Roughly a fifth of the inventory is not
    # physical, and until this release every product added the three together and returned
    # one number. Regrouping the same additions: no total moves.
    # rc40 G2: the sector ADM2 leg partitions each cell within its own province, so the shapes
    # of a province sum to the provincial marginal the check above holds exactly.
    shape_province = cube_core.canonical_shape_province(grid)

    def place(stream, acc, record_surface=True):
        weight, key, factor_key, surface = weight_for(stream)
        cube_core.check_weight(weight, stream["source_stream_id"])
        annual = stream["emissions_Gg"]
        sid = stream["source_stream_id"]
        acc["streams"].append(stream)
        if record_surface:
            acc["surfaces"].append({
                "source_stream_id": sid, "module": stream["module"],
                "geometry_id": stream["geometry_id"],
                "within_province_placement": ("not_placed" if stream["geometry_id"] == NO_NATIVE_GEOMETRY
                                              else took.get(stream["geometry_id"], "")),
                "surface": "none" if stream["geometry_id"] == NO_NATIVE_GEOMETRY else surface,
                "district_panel": "" if factor_key is None else "%s:%s" % factor_key,
                "spatial_profile_id": stream["spatial_profile_id"],
                # EMPTY WHERE NO WITHIN-PROVINCE PATTERN WAS USED. weight_for returns a vector
                # for an S4 stream too, and hashing it recorded a pattern that was COMPUTED and
                # then not used - which read out as 189 unallocated stream-years "reusing the
                # reference pattern" when what they actually did was stop at the provincial
                # control. The hash answers "what pattern was this mass placed on"; for mass
                # that was never placed below ADM1 the honest answer is none, not a digest.
                "pattern_hash": ("" if stream["geometry_id"] == NO_NATIVE_GEOMETRY
                                 else pattern_hash(weight))})
            price_events(stream, key, factor_key, acc)

        # S4 IS NOT PLACED. A stream with no native geometry has a provincial control and
        # nothing below it, so it belongs to the ADM1 marginal and to no cell. It used to be
        # spread on the declared industrial proxy with an `s4_co2e_share` layer flagging how
        # much of each cell rested on no geometry - but flagging placed mass is not the same
        # as not placing it: every reader still received a number in a cell, and the flag was
        # a layer they had to know to open. The closure identity carries the second term
        # instead: ADM2 == grid + unallocated_below_adm1.
        if stream["geometry_id"] == NO_NATIVE_GEOMETRY:
            gwp = _gwp_for(stream)
            shares = cube_core.province_marginals(grid, weight)
            for province, share in sorted(shares.items()):
                for index, month in enumerate(months):
                    mass = annual * stream["monthly_share"].get(month, 0.0) * share
                    if mass <= 0:
                        continue
                    acc["unallocated"].append({
                        "source_stream_id": sid,
                        "module": stream["module"],
                        "reporting_sector": stream["reporting_sector"],
                        "ipcc_category": stream["ipcc_category"],
                        "gas": stream["gas"], "month": month,
                        "spatial_view": stream["spatial_view"],
                        "level": "adm1", "province": province,
                        # Unrounded. The identity is asserted on these numbers, and the
                        # smallest S4 stream is 3.5e-05 Gg spread over sixty rows - rounding
                        # here at 9 dp cost 9e-09 Gg of it, which is a quarter of the stream.
                        # Rounding is a presentation concern and happens at the writer.
                        "emissions_Gg": mass,
                        "co2e_Mt_AR5": mass * gwp / 1000.0,
                        "reason": "no native geometry below the provincial control; the "
                                  "stream is placed at ADM1 and nowhere finer",
                    })
            acc["marginals"][sid] = shares
            # The provincial share is now the ONLY claim this stream makes, so it is checked
            # here rather than skipped with the placement. Dropping these rows was the first
            # thing this change got wrong: the check file fell from 950 rows to 830, which is
            # exactly the twenty-four streams times five provinces.
            declared = ctx.sector_shares(stream["module"]).get(
                stream["spatial_profile_id"], {})
            for province in PROVINCES:
                acc["check_rows"].append({
                    "source_stream_id": sid, "province": province,
                    "declared_share": round(float(declared.get(province, 0.0)), 6),
                    "grid_share": round(shares.get(province, 0.0), 6),
                    "diff": round(shares.get(province, 0.0)
                                  - float(declared.get(province, 0.0)), 6),
                    "status": UNALLOCATED_STATUS,
                    "basis": ("province share applied as a factor of the weight; the stream "
                              "is placed at ADM1 and nowhere finer, and its mass is "
                              "published in outputs/pakemis_spatial_unallocated.csv")})
            return
        for index, month in enumerate(months):
            acc["view_gas_month"][(stream["spatial_view"], stream["gas"])][index] += weight * (
                annual * stream["monthly_share"].get(month, 0.0))
        cat_key = (stream["module"], stream["ipcc_category"], stream["gas"])
        # A category layer that mixed views would be a raster a reader cannot label, so the
        # cube refuses to build one rather than shipping it with the coarser of the two
        # names. It has never happened - the view is declared at (module, category) and the
        # layers are keyed on IPCC category, which is coarser only across modules - but a
        # cheap assertion is what keeps "has never happened" true.
        if acc["category_view"].setdefault(cat_key, stream["spatial_view"]) \
                != stream["spatial_view"]:
            raise ValueError("category layer %r carries both %s and %s placements; a raster "
                             "that mixes views cannot be labelled"
                             % (cat_key, acc["category_view"][cat_key], stream["spatial_view"]))
        if cat_key not in acc["category_annual"]:
            acc["category_annual"][cat_key] = np.zeros((grid.height, grid.width),
                                                       dtype=np.float64)
        acc["category_annual"][cat_key] += weight * annual
        gwp = _gwp_for(stream)
        acc["total_co2e"] += weight * (annual * gwp / 1000.0)
        # rc41 (S-6): the view shares are priced PER STREAM with the stream's own methane
        # origin - a category layer can carry both (power: fossil gas beside biogenic
        # bagasse), so pricing the layer under one GWP was wrong for every such layer.
        acc["view_co2e"][stream["spatial_view"]] = (
            acc["view_co2e"].get(stream["spatial_view"], 0.0) + annual * gwp / 1000.0)

        marginals = cube_core.province_marginals(grid, weight)
        acc["marginals"][sid] = marginals
        # The air spatial lane's capture (never mutated downstream): the placed cell
        # vector itself, so a pollutant mass can ride EXACTLY the vector its anchor's
        # greenhouse-gas mass rode - not a re-derivation of it. S4 streams return
        # above and are deliberately never captured; their air mass stays at ADM1.
        if capture_cells and sid in capture_cells:
            acc["captured_cells"][sid] = weight

        # The sector-resolved ADM2 leg: one bincount per stream weight, then the
        # month split is scalar arithmetic - never a per-module grid accumulation.
        # A POINT-SUPPORTED STREAM PROJECTS FROM ITS POINTS (rc45). Everything else projects
        # the raster through the exact cell-district fractions, which is right for a surface.
        # For a facility it is not: the cell is split by ITS OWN geometry, so a plant near a
        # boundary is apportioned by its neighbourhood instead of by the district it stands in.
        # The fallback half of a mixed weight keeps the raster projection, because a fallback
        # surface has no point to be exact about.
        projection = ctx.point_projections.get(key)
        if projection is None:
            shape_sums = cube_core.shape_marginals(grid, weight, shape_province)
        else:
            shape_sums = cube_core.shape_marginals(grid, projection.fallback, shape_province)
            for index, value in projection.vector.items():
                shape_sums[index] = shape_sums.get(index, 0.0) + value
        shape_vec = np.array([shape_sums[i] for i in range(len(grid.districts))])
        acc["stream_shape"][sid] = shape_vec * annual
        acc["stream_outside"][sid] = annual * shape_sums[-1]
        # THE DISTRICT ACCUMULATOR KEYS ON BOTH SECTOR AXES (rc54). Keying on the module
        # alone is what made the district tables unable to answer the reporting axis: the
        # per-stream vector two lines above was folded into a module bucket and the stream's
        # reporting home was lost, so a district query for industrial fuel use could only be
        # answered with the industry MODULE - captive generation silently dropped. Keying on
        # the pair partitions each module's district mass exactly; the module total is the sum
        # over its reporting sectors, so no existing number moves.
        mkey = (stream["module"], stream["reporting_sector"], stream["gas"], stream["spatial_view"])
        if mkey not in acc["module_shape_month"]:
            acc["module_shape_month"][mkey] = np.zeros((12, len(grid.districts)),
                                                       dtype=np.float64)
            acc["module_outside"][mkey] = np.zeros(12, dtype=np.float64)
            acc["module_shape_month_co2e"][mkey] = np.zeros((12, len(grid.districts)),
                                                            dtype=np.float64)
            acc["module_outside_co2e"][mkey] = np.zeros(12, dtype=np.float64)
        vkey = (stream["spatial_view"], stream["gas"])
        # PRICED BEFORE THE MODULE AGGREGATION: each stream's mass carries ITS OWN
        # methane origin (gwp above), so the module x shape co2e is EXACT where the
        # module-grain mass alone could only bound it - power's fossil gas beside
        # biogenic bagasse, residential's wood and dung beside LPG. The interval the
        # ADM2 products used to publish existed because this sum was taken after the
        # origin was thrown away; taking it here is the same arithmetic the national
        # total has always done (rc41 S-6).
        price = gwp / 1000.0
        for index, month in enumerate(months):
            month_mass = annual * stream["monthly_share"].get(month, 0.0)
            acc["module_shape_month"][mkey][index] += month_mass * shape_vec
            acc["module_outside"][mkey][index] += month_mass * shape_sums[-1]
            acc["module_shape_month_co2e"][mkey][index] += (month_mass * price) * shape_vec
            acc["module_outside_co2e"][mkey][index] += (month_mass * price) * shape_sums[-1]
            acc["view_gas_shape_month"][vkey][index] += month_mass * shape_vec
            acc["view_gas_outside_month"][vkey][index] += month_mass * shape_sums[-1]
        if stream["geometry_id"] == "facilities:airports_domestic":
            status = "declared_divergence"
            basis = ("Islamabad International is administratively ICT in the share row "
                     "and physically in Attock, Punjab; the cube follows the coordinates")
        elif stream["geometry_id"] == "network:pak_rail":
            status = "derived_from_grid"
            basis = "the declared share row was itself derived from this network surface"
        elif stream["geometry_id"] == "points:pak_rail_yards":
            status = "declared_divergence"
            basis = ("the declared share row transcribes the Year Book wagons-loaded "
                     "shares; the cube burns the seven yard coordinates with the same "
                     "weights, and midpoint cell binning shifts a border yard's mass "
                     "between adjacent provinces - the coordinates govern the grid")
        else:
            status = "exact_by_construction"
            basis = "province share applied as a factor of the weight"
        declared = ctx.sector_shares(stream["module"]).get(
            stream["spatial_profile_id"], {})
        for province in PROVINCES:
            acc["check_rows"].append({
                "source_stream_id": sid, "province": province,
                "declared_share": round(float(declared.get(province, 0.0)), 6),
                "grid_share": round(marginals.get(province, 0.0), 6),
                "diff": round(marginals.get(province, 0.0)
                              - float(declared.get(province, 0.0)), 6),
                "status": status, "basis": basis})

    def finish(acc):
        acc["period"] = period
        acc["gas_month"] = {gas: sum(acc["view_gas_month"][(view, gas)] for view in VIEWS)
                            for gas in GASES}
        acc["within_province_placement"] = dict(took)
        acc["fallbacks"] = list(ctx.fallbacks)
        return acc

    reference = _new_accumulator(grid)
    reference["configuration_id"] = configuration_id
    for stream in streams:
        place(stream, reference)
    finish(reference)

    if ledger:
        from pkinv.core import configurations as conf
        ledger_residential = {s["source_stream_id"]: s
                              for s in load_ledger_streams(streams)}
        acc_l = _new_accumulator(grid)
        for stream in streams:
            s_stream = ledger_residential.get(stream["source_stream_id"], stream)
            # THE WEIGHT IS THE REFERENCE'S, BY IDENTITY: the L stream carries the same
            # keys the cube dispatches on, so weight_for hits the cache; asserted, not
            # assumed, because a second allocation would be a second vintage.
            w_ref = weight_for(stream)[0]
            w_s = weight_for(s_stream)[0]
            if w_s is not w_ref:
                raise ValueError("%s: configuration L built a different weight from the "
                                 "reference" % stream["source_stream_id"])
            place(s_stream, acc_l, record_surface=False)
        finish(acc_l)
        acc_l["configuration_id"] = conf.LEDGER
        acc_l["ledger_stream_ids"] = sorted(ledger_residential)
        reference["ledger"] = acc_l
    return reference


# --- writers -----------------------------------------------------------------------------

def write_netcdf(result, path, ledger=False):
    import numpy as np
    months = result["period"].months
    from netCDF4 import Dataset

    grid = result["grid"]
    lons, lats = _axes(grid)
    delta_s = _s_delta()

    ds = Dataset(path, "w", format="NETCDF4")
    try:
        ds.Conventions = "CF-1.8"
        ds.title = "PakEmis 0.05 degree monthly emissions, %s" % result["period"].label + (
            " - configuration L" if ledger else "")
        ds.release_version = pkinv.__version__
        from pkinv.core import configurations as conf
        ds.scenario_id = conf.LEDGER if ledger else conf.REFERENCE
        ds.configuration_id = ds.scenario_id
        if ledger:
            # rc41 (S-1): L is GRIDDED at stream x gas x month through the same dispatch as
            # the reference, not rescaled per province; it differs from the reference cube
            # in the two residential dung-cake streams' masses (CH4, N2O) and in no other
            # cell, which tests/test_grid_cube_ledger.py asserts per gas and month.
            ds.differs_from_reference = (
                "residential dung-cake CH4 and N2O only (ledger dung basis); CO2 layers are "
                "bit-identical to pakemis_grid_0p05_monthly.nc; weights are the reference's")
        # rc31 stated the configuration axis as a per-province rescale; rc41 grids L through
        # the same dispatch as the reference (pakemis_grid_0p05_monthly_ledger.nc and the
        # ADM1/ADM2 L views), so the two cubes are siblings, not a cube and a ratio.
        ds.configurations = ("S_TAN and L_TAN both gridded at stream x gas x month "
                             "through one dispatch; L differs in the two residential dung-cake "
                             "streams' masses only - see pakemis_grid_0p05_monthly_ledger.nc, "
                             "pakemis_adm1_ledger_2024.csv, pakemis_adm2_ledger_2024.csv")
        ds.residential_dung_axis = "L" if ledger else "S"
        # What configuration L adds to the reference: all the diverted dung burned in
        # households, against the survey reading whose residual has no observed
        # destination (residential_dung_ledger / pakemis_dung_fate_by_year). Through
        # rc66 this attribute was survey_configuration_delta_* and negative.
        ds.ledger_configuration_delta_Mt_co2e_AR5 = delta_s
        # rc42 (S-5): the L cube carries the gas layers only (size budget), and its
        # attribute says so instead of promising an annual group it does not contain
        ds.conservation = ("per gas and month, the grid sums to the national monthly "
                           "total less the mass published in "
                           "pakemis_spatial_unallocated.csv" + (
                               "; this configuration-L file carries the three gas layers "
                               "only (no annual_by_category group - see "
                               "pakemis_grid_0p05_monthly.nc)" if ledger else
                               "; per category, the annual layer sums to the ledger") +
                           "; held by tests/test_grid_cube.py")
        ds.contents = ("gas layers co2_Gg, ch4_Gg, n2o_Gg" + ("" if ledger else
                       "; group annual_by_category with emissions_Gg per category layer"))
        ds.uncertainty = ("no per-cell interval is stored: within a category the parametric "
                          "error is perfectly correlated, so a per-cell sigma would invite "
                          "quadrature and understate every aggregate. The bound for a cell "
                          "is in pakemis_joint_uncertainty.csv at resolution monthly_adm2 "
                          "and adds linearly within a category; across categories defer to "
                          "national_uncertainty_montecarlo.csv")
        shares = _view_shares(result)
        ds.spatial_views = ("every layer here is labelled physical, origin or accounting - "
                            "whether it places mass where the emission happens, where the "
                            "generating activity originates, or where the statistic is "
                            "booked. This release: "
                            + "; ".join("%s %.2f%%" % (view, shares[view])
                                        for view in VIEWS if shares.get(view))
                            + ". Summing across views is a choice and "
                              "pakemis_adm2_monthly.csv carries the axis so it can be made "
                              "deliberately.")
        ds.weights = ("spatial weights are month-invariant; the monthly shape is the "
                      "published temporal layer p(s,m) only - no stream carries "
                      "seasonal-geography evidence")
        ds.licence = "CC-BY-4.0"
        ds.geographic_licence_basis = "independent_primary_geography; ODbL alternatives excluded"
        ds.institution = "Pakistan Air Quality Initiative (PAQI)"

        ds.createDimension("time", 12)
        ds.createDimension("lat", grid.height)
        ds.createDimension("lon", grid.width)
        ds.createDimension("bnds", 2)

        import datetime
        # The origin is the period's own first day. Written out, it was a fourth place the
        # year was spelled: a cube built for another year with this origin would carry twelve
        # correct months on an axis that dated them to 2023.
        origin = datetime.date(int(months[0][:4]), int(months[0][4:]), 1)
        period_end = datetime.date(int(result["period"].file_token), 7, 1)
        time = ds.createVariable("time", "f8", ("time",))
        time.units = "days since %s" % origin.isoformat()
        time.calendar = "standard"
        time.standard_name = "time"
        time.axis = "T"
        time.bounds = "time_bnds"
        starts = [datetime.date(int(m[:4]), int(m[4:]), 1) for m in months]
        ends = starts[1:] + [period_end]
        time[:] = [(d - origin).days for d in starts]
        time_b = ds.createVariable("time_bnds", "f8", ("time", "bnds"))
        time_b[:, 0] = [(d - origin).days for d in starts]
        time_b[:, 1] = [(d - origin).days for d in ends]
        label = ds.createVariable("month_label", str, ("time",))
        for i, m in enumerate(months):
            label[i] = m

        lat = ds.createVariable("lat", "f8", ("lat",))
        lat.units = "degrees_north"
        lat.standard_name = "latitude"
        lat.axis = "Y"
        lat.bounds = "lat_bnds"
        lat[:] = lats
        lon = ds.createVariable("lon", "f8", ("lon",))
        lon.units = "degrees_east"
        lon.standard_name = "longitude"
        lon.axis = "X"
        lon.bounds = "lon_bnds"
        lon[:] = lons
        lat_b = ds.createVariable("lat_bnds", "f8", ("lat", "bnds"))
        lat_b[:, 0] = lats + 0.025
        lat_b[:, 1] = lats - 0.025
        lon_b = ds.createVariable("lon_bnds", "f8", ("lon", "bnds"))
        lon_b[:, 0] = lons - 0.025
        lon_b[:, 1] = lons + 0.025

        crs = ds.createVariable("crs", "i4")
        crs.grid_mapping_name = "latitude_longitude"
        crs.epsg_code = "EPSG:4326"
        crs.longitude_of_prime_meridian = 0.0
        crs.semi_major_axis = 6378137.0
        crs.inverse_flattening = 298.257223563
        crs.crs_wkt = ('GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563]],'
                       'PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433],AUTHORITY["EPSG","4326"]]')
        # rc42 (S-5): only the cells outside every province are missing; an in-country zero
        # is a measurement (no emission of that gas there) and is stored as 0, not masked.
        # rc41 wrote _FillValue = 0, which masked 57 % of the in-country category cells.
        FILL = -9999.0
        outside = grid.province_id < 0

        for gas in GASES:
            var = ds.createVariable(gas.lower() + "_Gg", "f4",
                                    ("time", "lat", "lon"),
                                    zlib=True, complevel=4, shuffle=True,
                                    fill_value=FILL)
            var.units = "Gg month-1"
            var.long_name = "%s emissions, native gas mass" % gas
            var.cell_methods = "time: sum"
            var.coordinates = "lat lon"
            var.grid_mapping = "crs"
            var.comment = ("no CF standard_name exists for a per-cell emitted mass; units are "
                           "gigagrams of %s per month, summed over the cell" % gas)
            data = result["gas_month"][gas].astype(np.float32)
            data[:, outside] = FILL
            var[:] = data


        if ledger:
            # the L cube carries the three gas layers only: its annual-by-category group
            # would repeat the reference's for every layer but two, and the size budget
            # (tests/test_grid_cube.py) is the reference cube's
            return
        group = ds.createGroup("annual_by_category")
        keys = sorted(result["category_annual"])
        group.createDimension("category", len(keys))
        cat = group.createVariable("category", str, ("category",))
        module_var = group.createVariable("module", str, ("category",))
        gas_var = group.createVariable("gas", str, ("category",))
        # The view axis rides here as a LABEL rather than as nine more rasters. The file is
        # 6.0 MB against a hard 8 MB budget whose test names the agreed fallback - drop the
        # annual group to CO2e-only, do not raise the bound - and per-view surfaces would
        # spend that budget on something pakemis_adm2_monthly.csv already carries as a real
        # dimension. A string per layer costs nothing and answers the question a reader of a
        # cell actually has: is this where it is emitted, or only where it is booked.
        view_var = group.createVariable("spatial_view", str, ("category",))
        view_var.long_name = ("whether the layer places mass where it is emitted "
                              "(physical), where the generating activity originates "
                              "(origin), or where the statistic is booked (accounting)")
        annual = group.createVariable("emissions_Gg", "f4",
                                      ("category", "lat", "lon"),
                                      zlib=True, complevel=4, shuffle=True,
                                      fill_value=FILL)
        annual.units = "Gg yr-1"
        annual.long_name = "annual emissions per category layer, native gas mass"
        annual.cell_methods = "time: sum"
        annual.coordinates = "lat lon"
        annual.grid_mapping = "crs"
        for i, key in enumerate(keys):
            module, category, gas = key
            cat[i] = category
            module_var[i] = module
            gas_var[i] = gas
            view_var[i] = result["category_view"][key]
            layer = result["category_annual"][key].astype(np.float32)
            layer[outside] = FILL
            annual[i] = layer
    finally:
        ds.close()


def _view_shares(result):
    """{view: percent of gridded CO2e-AR5}, priced per stream with each stream's own
    methane origin (rc41, S-6: this used to price every CH4 layer as fossil, 30 against
    28 for the biogenic half, and the published 82.11/8.76/9.13 shares carried it) - what
    a reader of THIS FILE is looking at, which excludes the unallocated mass."""
    totals = result["view_co2e"]
    grand = sum(totals.values())
    return {view: 100.0 * mass / grand for view, mass in totals.items()} if grand else {}


def _axes(grid):
    import numpy as np
    t = grid.transform
    lons = np.array([t.c + t.a * (i + 0.5) for i in range(grid.width)])
    lats = np.array([t.f + t.e * (j + 0.5) for j in range(grid.height)])
    return lons, lats


def _s_delta():
    """Configuration L's national total less the reference's (positive since rc67)."""
    reference_total = next(float(r["co2e_Mt_AR5"])
                           for r in _rows("national_all_sectors.csv")
                           if r["row_kind"] == "national_total")
    ledger_total = next(float(r["co2e_Mt_AR5"])
                        for r in _rows("national_all_sectors_ledger.csv")
                        if r["row_kind"] == "national_total")
    return round(ledger_total - reference_total, 5)


def _unallocated_markers(result, module=None, reporting_sector=None):
    """One non-numeric row per (province, gas) whose mass is controlled at ADM1 and placed
    nowhere finer. `module` restricts to one module and adds the column the sector view
    carries; `reporting_sector` adds the second sector column the district tables key on
    (rc54) and restricts to the streams filed under it; passing None gives the aggregate
    view's rows."""
    keys = sorted({(row["province"], row["gas"], row["spatial_view"])
                   for row in result["unallocated"]
                   if (module is None or row["module"] == module)
                   and (reporting_sector is None
                        or (row.get("reporting_sector") or row["module"]) == reporting_sector)})
    rows = []
    for province, gas, view in keys:
        # rc41 (S-5): the absence is TYPED in its own column and the numeric column is
        # empty - a reader summing emissions_Gg meets a blank it cannot mistake for a
        # number, and a reader of the absence meets the vocabulary, not a sentinel string
        row = {"shape_id": "", "adm2_ids": "",
               "allocation_status": UNALLOCATED_BELOW_ADM1,
               "province": province, "gas": gas, "month": "all",
               "spatial_view": view,
               "emissions_Gg": "", "absence_reason": UNALLOCATED_BELOW_ADM1}
        if module is not None:
            row = dict({"module": module}, **row)
        if reporting_sector is not None:
            row = dict({"reporting_sector": reporting_sector}, **row)
        rows.append(row)
    return rows


UNCERTAINTY_NOTE = (
    "# NO INTERVAL IS WRITTEN ON THESE ROWS, ON PURPOSE. Within a category the parametric "
    "error is perfectly correlated -\n"
    "# one emission factor moves every district and every month of it together - so a "
    "per-cell sigma repeated down this\n"
    "# file would invite a reader to combine them in quadrature and make the national total "
    "look an order of magnitude more\n"
    "# certain than the Monte Carlo says it is. The bound for any figure here is in\n"
    "# outputs/pakemis_joint_uncertainty.csv at resolution monthly_adm2, and it adds "
    "LINEARLY across districts and months\n"
    "# within a category. Across categories do not add at all: the Monte Carlo measures the "
    "dependence and publishes it.\n")


def adm2_view_rows(result):
    """The ADM2 view of one built period: shape x gas x view x month, plus the declared
    absences. Extracted from write_adm2 unchanged so that anything else needing this view -
    the nine-year annual product - consumes the SAME rows rather than re-deriving them.

    That matters more than it looks. The binning here is not grid.districts; it is the
    canonical shape frame under the nested fractional partition (rc32, and rc40 G2: "the same
    nested partition the sector leg uses, or the two views disagree"). A second consumer that
    binned on the raw district vector would close every total and disagree with this one at
    every shared boundary cell - a second vintage of one geography, discoverable only by
    someone who went looking."""
    months = result["period"].months
    import numpy as np
    grid = result["grid"]
    from pkinv.core import adm2 as adm2_core
    shape_members = adm2_core.shape_to_adm2()
    canonical = adm2_core.load_canonical()
    idx_by_shape = district_index_by_shape(grid)

    # rc32: the fractional path - identical weights to shape_marginals, so the
    # aggregate and sector views cannot disagree at a boundary cell again
    from pkinv.core.gis import cube as cube_core
    # rc40 G2: the same nested partition the sector leg uses, or the two views disagree.
    packed = cube_core._fraction_matrix_nested(grid, cube_core.canonical_shape_province(grid))
    rows = []
    for shape_id, members in sorted(shape_members.items()):
        idx = idx_by_shape.get(shape_id)
        if idx is None:
            continue
        if packed is not None and idx in packed:
            frac_ix, frac_w = packed[idx]
        else:
            frac_ix = frac_w = None
        mask = grid.district_id == idx
        provinces = {canonical[m]["province_id"] for m in members}
        status = "one_to_one" if len(members) == 1 else "shared_shape"
        for gas in GASES:
            for view in VIEWS:
                district = result["view_gas_shape_month"][(view, gas)]
                for month_index, month in enumerate(months):
                    # ONE accumulation, not a second projection of the raster (rc45).
                    value = float(district[month_index][idx])
                    rows.append({
                        "shape_id": shape_id,
                        "adm2_ids": ";".join(members),
                        "allocation_status": status,
                        "province": ";".join(sorted(provinces)),
                        "gas": gas, "month": month, "spatial_view": view,
                        "emissions_Gg": round(value, 8), "absence_reason": ""})
    # The declared hole: units with no polygon cannot have grid rows, and silence would
    # read as zero emissions. One row per such unit says why (rc41: in absence_reason,
    # with the numeric column empty).
    for adm2_id, row in sorted(canonical.items()):
        if row["geometry_relation"] in ("shape_missing", "no_geometry") \
                and row["status"] == "active":
            rows.append({"shape_id": "", "adm2_ids": adm2_id,
                         "allocation_status": row["geometry_relation"],
                         "province": row["province_id"], "gas": "all", "month": "all",
                         "spatial_view": "all",
                         "emissions_Gg": "", "absence_reason": UNRESOLVED_IN_GRID})
    # The second declared absence: this file no longer sums to the national total, and it
    # says so here rather than leaving a reader to discover a two per cent shortfall by
    # subtraction. The masses are in outputs/pakemis_spatial_unallocated.csv; what belongs
    # in an ADM2 table is the fact that they are not in it.
    rows.extend(_unallocated_markers(result))
    return rows


def write_adm2(result, path):
    rows = adm2_view_rows(result)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        handle.write(UNCERTAINTY_NOTE)
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def adm2_sector_rows(result):
    """The module-resolved ADM2 view of one period, extracted from write_adm2_sector so that
    the nine-year annual product is that view SUMMED rather than a second derivation of it.
    The rule adm2_view_rows established: one geography, one generator."""
    months = result["period"].months
    """The ADM2 x month view WITH the module axis - the split the coverage matrix
    carried as a declared deferral until this round. Same conventions as write_adm2:
    native gas mass only, the shared-shape and declared-hole statuses carried, and a
    row appears only for gases the module actually emits (a zero in a shape is a
    real allocation result; a gas the module never reports would be noise)."""
    import numpy as np
    grid = result["grid"]
    from pkinv.core import adm2 as adm2_core
    shape_members = adm2_core.shape_to_adm2()
    canonical = adm2_core.load_canonical()
    idx_by_shape = district_index_by_shape(grid)

    series = result["module_shape_month"]      # keyed (module, reporting_sector, gas, spatial_view)
    # A module can be wholly unallocated - industry is, all twenty-four of its streams
    # carrying no native geometry - and it must still appear here, carrying its declared
    # holes and its ADM1 marker. A module that vanishes from the sector view reads as a
    # module with no emissions.
    modules = sorted({module for module, _rep, _gas, _view in series}
                     | {row["module"] for row in result["unallocated"]})
    # A MODULE MAY NOW HAVE MORE THAN ONE REPORTING SECTOR (power: its own, plus industry for
    # captive self-generation), so the frame's typed absences and the ADM1 markers are emitted
    # once per (module, reporting sector) the module actually carries. Emitting them once per
    # module would leave the partition incomplete for whichever sector missed out - a reader
    # filtering to the industry reporting sector would meet the mass and not the absences.
    reps_by_module = {}
    for m, rep, _gas, _view in series:
        reps_by_module.setdefault(m, set()).add(rep)
    for row in result["unallocated"]:
        reps_by_module.setdefault(row["module"], set()).add(
            row.get("reporting_sector") or row["module"])
    rows = []
    for module in modules:
        gas_views = sorted((rep, gas, view) for m, rep, gas, view in series if m == module)
        for shape_id, members in sorted(shape_members.items()):
            idx = idx_by_shape.get(shape_id)
            if idx is None:
                continue
            provinces = {canonical[m]["province_id"] for m in members}
            status = "one_to_one" if len(members) == 1 else "shared_shape"
            for rep, gas, view in gas_views:
                arr = series[(module, rep, gas, view)]
                co2e = result["module_shape_month_co2e"][(module, rep, gas, view)]
                for month_index, month in enumerate(months):
                    rows.append({
                        "module": module, "reporting_sector": rep,
                        "shape_id": shape_id,
                        "adm2_ids": ";".join(members),
                        "allocation_status": status,
                        "province": ";".join(sorted(provinces)),
                        "gas": gas, "month": month, "spatial_view": view,
                        "emissions_Gg": round(float(arr[month_index, idx]), 8),
                        # EXACT, priced per stream at accumulation (each stream's own
                        # CH4 origin) - the interval the module grain used to force
                        "co2e_Mt_AR5": round(float(co2e[month_index, idx]), 12),
                        "absence_reason": ""})
        for rep in sorted(reps_by_module.get(module, {module})):
            for adm2_id, row in sorted(canonical.items()):
                if row["geometry_relation"] in ("shape_missing", "no_geometry") \
                        and row["status"] == "active":
                    rows.append({"module": module, "reporting_sector": rep,
                                 "shape_id": "", "adm2_ids": adm2_id,
                                 "allocation_status": row["geometry_relation"],
                                 "province": row["province_id"], "gas": "all",
                                 "month": "all", "spatial_view": "all",
                                 "emissions_Gg": "", "co2e_Mt_AR5": "",
                                 "absence_reason": UNRESOLVED_IN_GRID})
            for marker in _unallocated_markers(result, module=module, reporting_sector=rep):
                marker["co2e_Mt_AR5"] = ""
                rows.append(marker)
    return rows


def write_adm2_sector(result, path):
    rows = adm2_sector_rows(result)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        handle.write(UNCERTAINTY_NOTE)
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def write_check(rows, path):
    write_table(path, list(rows[0]), rows)


FALLBACK_FIELDS = ["source_stream_id", "module", "gas", "methane_origin", "scope", "declared",
                   "used", "province", "shape", "weight_share", "affected_Gg", "affected_Mt_AR5",
                   "reason"]


def fallback_rows(exceptions):
    """The priced fallback events as rows, deduplicated. Extracted from write_fallbacks so the
    nine-year product can publish the same record per period without re-deriving it."""
    seen = set()
    rows = []
    for event in sorted(exceptions, key=lambda e: (e["source_stream_id"], e["scope"],
                                                    e["province"], e["shape"], e["reason"])):
        row = {f: event.get(f, "") for f in FALLBACK_FIELDS}
        row["weight_share"] = "%.10g" % event["weight_share"]
        row["affected_Gg"] = "%.12g" % event["affected_Gg"]
        row["affected_Mt_AR5"] = "%.12g" % event["affected_Mt_AR5"]
        key = tuple(row[f] for f in FALLBACK_FIELDS)
        if key not in seen:
            seen.add(key)
            rows.append(row)
    return rows


def write_fallbacks(exceptions, path):
    """The fallback register, PRICED (rc41, S-2/S-4): one row per stream and event, with
    the fraction of the stream's national weight that rode the substitute surface and the
    mass that fraction carries in the stream's own gas and methane origin. Every stream
    that rides a cached surface is credited with the surface's events - the register used
    to name only the first stream that built the cache, so nineteen of twenty-one GLW
    streams were absent from it. The allow-list (data/allowed_grid_fallbacks.csv) still
    matches on (scope, declared, used)."""
    rows = fallback_rows(exceptions)
    write_table(path, FALLBACK_FIELDS, rows)
    return len(rows)


SURFACE_FIELDS = ["source_stream_id", "module", "spatial_profile_id", "geometry_id",
                  "within_province_placement", "surface", "district_panel", "pattern_hash"]


def pattern_hash(weight):
    """A digest of the NORMALISED weight vector, taken where the vector is used.

    WHY A HASH AND NOT A LABEL. pakemis_spatial_weights_by_year.csv already says, per
    stream-year, whether a period's pattern is its own or the reference year's carried back.
    That column is derived from what the engine CAN read for a (surface, district_panel) pair,
    which is the right rule and is still a statement ABOUT the build rather than a measurement
    OF it - the plant fleet satisfied the surface half of that rule while failing the panel
    half for an entire pass, invisibly. A hash cannot be wrong in that direction: two periods
    whose weight vectors hash equal WERE placed on the same pattern, whatever any column says,
    and two that differ were not.

    Quantised to 1e-12 before hashing because the vector is normalised floating point and the
    question asked of it is "the same pattern?", not "the same bits". check_weight has already
    established that it sums to 1, so the quantum is absolute and comparable across streams.
    """
    import hashlib
    import numpy as np
    quantised = np.rint(np.asarray(weight, dtype=np.float64).ravel() * 1e12).astype(np.int64)
    return hashlib.sha256(quantised.tobytes()).hexdigest()[:16]


def write_surfaces(result, path):
    """rc41 (S-3): the surface each stream was actually placed on, from the dispatcher
    itself - the register spatial_decomposition used to reconstruct per geometry, which
    unioned rasters across a geometry's streams ("builtup+cropland") and named a surface
    for streams the cube never grids."""
    rows = sorted(result["surfaces"], key=lambda r: r["source_stream_id"])
    write_table(path, SURFACE_FIELDS, rows, banner=(
        "# The surface the cube placed each stream on, recorded at the dispatch (rc41).",
        "# surface: a proxy raster (cropland, builtup, population, glw_livestock, manure_applied,",
        "# spam_rice, firms_fire), a point set or network, or none (retained at ADM1).",
        "# district_panel: the ADM2 panel whose shares factor the within-province placement, if any."))
    return len(rows)


def write_adm1_ledger(acc, path):
    if acc["period"].period_id != REFERENCE_PERIOD:
        raise ValueError("configuration L is built for %s only; the monthly layer it needs "
                         "exists for no other period (asked for %s)"
                         % (REFERENCE_PERIOD, acc["period"].period_id))
    months = acc["period"].months
    """Configuration L at ADM1, stream x gas x month x province: every residential stream's
    provincial marginal (the reference weight's) times its L mass and monthly share."""
    from pkinv.core.geography import PROVINCES
    rows = []
    for stream in acc["streams"]:
        if stream["module"] != "residential":
            continue
        gwp = _gwp_for(stream)
        marginals = acc["marginals"][stream["source_stream_id"]]
        for month in months:
            month_mass = stream["emissions_Gg"] * stream["monthly_share"].get(month, 0.0)
            for province in PROVINCES:
                mass = month_mass * marginals.get(province, 0.0)
                rows.append({"configuration_id": acc["configuration_id"],
                             "source_stream_id": stream["source_stream_id"],
                             "module": stream["module"],
                             "sub_category": stream["sub_category"], "gas": stream["gas"],
                             "spatial_view": stream["spatial_view"],
                             "province": province, "month": month,
                             "emissions_Gg": "%.12g" % mass,
                             "co2e_Mt_AR5": "%.12g" % (mass * gwp / 1000.0)})
    fields = ["configuration_id", "source_stream_id", "module", "sub_category", "gas",
              "spatial_view", "province", "month", "emissions_Gg", "co2e_Mt_AR5"]
    write_table(path, fields, rows, banner=(
        "# Configuration L at ADM1 grain, stream x gas x month x province (rc41). Only the",
        "# residential module is here: L differs from the reference in the two dung-cake streams'",
        "# magnitudes and nowhere else; every other module's rows are the reference's",
        "# (pakemis_grid_provincial_check.csv, pakemis_adm2_monthly_sector.csv) by construction.",
        "# Weights are the reference weights: L changes masses, never placement."))
    return len(rows)


def _adm2_stream_rows(acc, precision=12):
    grid = acc["grid"]
    from pkinv.core import adm2 as adm2_core
    shape_members = adm2_core.shape_to_adm2()
    canonical = adm2_core.load_canonical()
    idx_by_shape = district_index_by_shape(grid)
    rows = []
    for stream in acc["streams"]:
        sid = stream["source_stream_id"]
        if sid not in acc["stream_shape"]:
            continue
        shape_annual = acc["stream_shape"][sid]
        outside_annual = acc["stream_outside"][sid]
        base = {"configuration_id": acc["configuration_id"], "module": stream["module"],
                "reporting_sector": stream["reporting_sector"],
                "source_stream_id": sid, "sub_category": stream["sub_category"],
                "gas": stream["gas"], "spatial_view": stream["spatial_view"]}
        for shape_id, members in sorted(shape_members.items()):
            idx = idx_by_shape.get(shape_id)
            if idx is None:
                continue
            provinces = {canonical[m]["province_id"] for m in members}
            status = "one_to_one" if len(members) == 1 else "shared_shape"
            rows.append(dict(base, shape_id=shape_id, adm2_ids=";".join(members),
                             allocation_status=status,
                             province=";".join(sorted(provinces)),
                             emissions_Gg=("%%.%dg" % precision) % float(shape_annual[idx]),
                             absence_reason=""))
        rows.append(dict(base, shape_id="", adm2_ids="", allocation_status="outside_all_shapes",
                         province="OUTSIDE",
                         emissions_Gg=("%%.%dg" % precision) % float(outside_annual),
                         absence_reason=""))
    return rows


def adm2_stream_rows(acc, precision=10):
    """The per-stream ADM2 vectors of ONE period, annual (Gg) - factored out of
    write_adm2_stream_reference so the nine-year product is the same rows collected per period
    rather than a second derivation of them (the rule adm2_view_rows established: one geometry,
    one generator).

    TEN SIGNIFICANT DIGITS, NOT TWELVE, AND THE REASON IS REPRODUCIBILITY. The district vector is
    a floating-point reduction over grid cells, and two runs of the same code can differ in the
    last bits: one FY2018-19 cell printed 4.24697407637e-06 in one build and ...36e-06 in the next,
    a relative difference of 2e-12 that straddled the twelfth-digit rounding boundary and failed
    the build's own noise gate. Twelve digits is precision the arithmetic does not carry. Ten is
    inside every closure this product is held to (RTOL 1e-9) and is stable. The reference-year
    file keeps twelve because the air spatial lane reads its bytes; the two therefore agree to
    1e-10 rather than character for character, and the test says so."""
    return _adm2_stream_rows(acc, precision=precision)


def write_adm2_stream_reference(acc, path):
    """The reference configuration's per-stream ADM2 vectors, ANNUAL, all modules: the
    `stream_shape` accumulation the shipped ADM2 marginals are built from, published at the
    grain downstream layers inherit from (the air spatial lane is the first consumer - a
    pollutant row rides its stream's normalized shape vector). One row per stream x shape,
    plus each stream's OUTSIDE term and the frame's typed absences; a stream's rows sum,
    with OUTSIDE, to its annual mass exactly (the closure the tests pin)."""
    rows = _adm2_stream_rows(acc)
    fields = ["configuration_id", "module", "reporting_sector", "source_stream_id",
              "sub_category", "gas", "spatial_view", "shape_id", "adm2_ids",
              "allocation_status", "province", "emissions_Gg", "absence_reason"]
    with open(path, "w", newline="", encoding="utf-8") as handle:
        handle.write("# The reference configuration's per-stream ADM2 vectors, ANNUAL (Gg), all modules:\n"
                     "# the stream_shape accumulation the shipped ADM2 marginals are built from, at the\n"
                     "# grain downstream layers inherit from. A stream's rows sum, with its OUTSIDE row,\n"
                     "# to its annual mass exactly. Zero rows are real zeros of the surface, not absences;\n"
                     "# absences are the frame's shape_missing/no_geometry units, typed in the ADM2\n"
                     "# products proper. First consumer: the air spatial lane (air_spatial_sectors.py).\n")
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def write_adm2_ledger(acc, path):
    if acc["period"].period_id != REFERENCE_PERIOD:
        raise ValueError("configuration L is built for %s only; the monthly layer it needs "
                         "exists for no other period (asked for %s)"
                         % (REFERENCE_PERIOD, acc["period"].period_id))
    months = acc["period"].months
    """Configuration L at ADM2, stream x gas x month x shape, with the outside term and the
    declared absences typed - the v2 of the product survey_spatial.py used to write by
    rescaling every residential row, every gas, by one per-province CO2e ratio."""
    grid = acc["grid"]
    from pkinv.core import adm2 as adm2_core
    shape_members = adm2_core.shape_to_adm2()
    canonical = adm2_core.load_canonical()
    idx_by_shape = district_index_by_shape(grid)
    rows = []
    for stream in acc["streams"]:
        if stream["module"] != "residential":
            continue
        sid = stream["source_stream_id"]
        shape_annual = acc["stream_shape"][sid]
        outside_annual = acc["stream_outside"][sid]
        base = {"configuration_id": acc["configuration_id"], "module": stream["module"],
                "source_stream_id": sid, "sub_category": stream["sub_category"],
                "gas": stream["gas"], "spatial_view": stream["spatial_view"]}
        # stream grain keeps the CH4 origin, so the row's co2e is the stream's own
        # price - the module-grain L summation downstream sums these exactly
        price = _gwp_for(stream) / 1000.0
        for shape_id, members in sorted(shape_members.items()):
            idx = idx_by_shape.get(shape_id)
            if idx is None:
                continue
            provinces = {canonical[m]["province_id"] for m in members}
            status = "one_to_one" if len(members) == 1 else "shared_shape"
            for month in months:
                share = stream["monthly_share"].get(month, 0.0)
                rows.append(dict(base, shape_id=shape_id, adm2_ids=";".join(members),
                                 allocation_status=status,
                                 province=";".join(sorted(provinces)), month=month,
                                 emissions_Gg=round(float(shape_annual[idx]) * share, 8),
                                 co2e_Mt_AR5=round(float(shape_annual[idx]) * share * price, 12),
                                 absence_reason=""))
        for month in months:
            share = stream["monthly_share"].get(month, 0.0)
            rows.append(dict(base, shape_id="", adm2_ids="", allocation_status="outside_all_shapes",
                             province="OUTSIDE", month=month,
                             emissions_Gg=round(float(outside_annual) * share, 8),
                             co2e_Mt_AR5=round(float(outside_annual) * share * price, 12),
                             absence_reason=""))
        for adm2_id, row in sorted(canonical.items()):
            if row["geometry_relation"] in ("shape_missing", "no_geometry") \
                    and row["status"] == "active":
                rows.append(dict(base, shape_id="", adm2_ids=adm2_id,
                                 allocation_status=row["geometry_relation"],
                                 province=row["province_id"], month="all",
                                 emissions_Gg="", co2e_Mt_AR5="",
                                 absence_reason=UNRESOLVED_IN_GRID))
    fields = ["configuration_id", "module", "source_stream_id", "sub_category", "gas",
              "spatial_view", "shape_id", "adm2_ids", "allocation_status", "province", "month",
              "emissions_Gg", "co2e_Mt_AR5", "absence_reason"]
    with open(path, "w", newline="", encoding="utf-8") as handle:
        handle.write("# Configuration L at ADM2 grain, stream x gas x month x shape (rc41, v2). Only the\n"
                     "# residential module is here: L differs from the reference in the two dung-cake\n"
                     "# streams' magnitudes and nowhere else. Each stream's rows sum, with its OUTSIDE\n"
                     "# row, to its ADM1 marginal (pakemis_adm1_ledger_2024.csv) exactly; the declared\n"
                     "# absences are typed in absence_reason with the numeric column empty.\n")
        handle.write(UNCERTAINTY_NOTE)
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    result = build()

    nc_path = asset_path(OUTPUTS, "pakemis_grid_0p05_monthly.nc")
    write_netcdf(result, nc_path)
    adm2_rows = write_adm2(result, asset_path(OUTPUTS, "pakemis_adm2_monthly.csv"))
    sector_rows = write_adm2_sector(
        result, asset_path(OUTPUTS, "pakemis_adm2_monthly_sector.csv"))
    write_check(result["check_rows"],
                asset_path(OUTPUTS, "pakemis_grid_provincial_check.csv"))
    n_fallbacks = write_fallbacks(result["exceptions"],
                                  asset_path(OUTPUTS, "pakemis_grid_fallbacks.csv"))
    n_surfaces = write_surfaces(result, asset_path(OUTPUTS, "pakemis_grid_stream_surfaces.csv"))
    ledger = result["ledger"]
    write_netcdf(ledger, asset_path(OUTPUTS, "pakemis_grid_0p05_monthly_ledger.nc"), ledger=True)
    n_adm1_s = write_adm1_ledger(ledger, asset_path(OUTPUTS, "pakemis_adm1_ledger_2024.csv"))
    n_adm2_s = write_adm2_ledger(ledger, asset_path(OUTPUTS, "pakemis_adm2_ledger_2024.csv"))
    n_stream_ref = write_adm2_stream_reference(result, asset_path(OUTPUTS, "pakemis_adm2_stream_reference.csv"))
    unallocated_path = asset_path(OUTPUTS, "pakemis_spatial_unallocated.csv")
    fields = ("source_stream_id", "module", "reporting_sector", "ipcc_category", "gas", "month",
              "spatial_view", "level", "province", "emissions_Gg", "co2e_Mt_AR5", "reason")
    with open(unallocated_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in sorted(result["unallocated"],
                          key=lambda r: (r["source_stream_id"], r["province"], r["month"])):
            # Twelve significant figures, not a fixed number of decimals: these streams span
            # nine orders of magnitude and a fixed dp truncates the small ones to nothing.
            writer.writerow(dict(row, emissions_Gg="%.12g" % row["emissions_Gg"],
                                 co2e_Mt_AR5="%.12g" % row["co2e_Mt_AR5"]))

    size_mb = os.path.getsize(nc_path) / 1e6
    print("grid cube -> %s (%.1f MB)" % (nc_path, size_mb))
    print("  %d streams over %d months; %d category-gas annual layers"
          % (len(result["streams"]), len(result["period"].months),
             len(result["category_annual"])))
    print("  per-stream ADM2 reference: %d rows" % n_stream_ref)
    import numpy as np
    for gas in GASES:
        print("  %s annual: %.2f Gg on the grid" % (gas,
              float(result["gas_month"][gas].sum())))
    divergent = sorted({r["source_stream_id"] for r in result["check_rows"]
                        if r["status"] == "declared_divergence"})
    print("  provincial check: %d rows; %d streams declare divergence (aviation)"
          % (len(result["check_rows"]), len(divergent)))
    print("  %d ADM2 rows (%d sector-resolved); %d priced fallback rows; %d stream surfaces"
          % (adm2_rows, sector_rows, n_fallbacks, n_surfaces))
    print("  configuration L: %d ADM1 rows, %d ADM2 rows; grid differs from the reference by "
          "%s" % (n_adm1_s, n_adm2_s, ", ".join(
              "%s %+.6f Gg" % (gas, float((ledger["gas_month"][gas] - result["gas_month"][gas]).sum()))
              for gas in GASES)))
    unplaced = sorted({r["source_stream_id"] for r in result["unallocated"]})
    print("  unallocated below ADM1: %d rows, %d streams, %.4f Mt CO2e-AR5 -> %s"
          % (len(result["unallocated"]), len(unplaced),
             sum(r["co2e_Mt_AR5"] for r in result["unallocated"]),
             os.path.relpath(unallocated_path, os.path.dirname(OUTPUTS))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
