"""The spatial weight registry: what geography each stream-year was placed on, and from when.

THE MIRROR OF THE TEMPORAL REGISTRY. pakemis_temporal_profiles.csv publishes one row per
component-year saying WHEN within the year a mass falls, with `borrowed_from_year` naming the
year a shape came from when it was not the year's own. This publishes the same for the other
axis: one row per (source stream, fiscal period) saying WHERE the mass fell, on what surface,
and from which year that surface was measured.

TWO AXES, BECAUSE THEY ANSWER DIFFERENT QUESTIONS AND ONE CANNOT STAND FOR THE OTHER.

    spatial_time_basis   was this year's geography measured for THIS year, or borrowed?
    substituted_share    how much of the placement was a FALLBACK rather than the declared
                         surface, measured from the events the build actually emitted?

The pass that produced this registry is itself the argument for keeping them apart. Grid
power's plant fleet was, for a while, silently BORROWED from the reference year for all nine
periods - the code read the ledger without a period. Nothing was substituted, so the emitted
fallback record was clean, and a registry reading only that record would have called those
years well-placed. Once the period was threaded, the four years before FY2019-20 turned out to
have no per-plant fuel evidence at all: 42.6 to 53.3 Mt CO2e a year moved onto a built-up
substitute, which the record now shows loudly. Borrowing is silent and must be DERIVED;
substitution is loud and must be READ. A registry with one column would miss whichever of the
two it was not built for.

DERIVED, NEVER DECLARED. Every field comes from what the cube dispatched
(pakemis_grid_stream_surfaces.csv), what it substituted
(pakemis_grid_fallbacks_by_year.csv), the stream ledger and the share registry. Nothing here
is hand-maintained, so the registry cannot drift from the build it describes.
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import collections
import csv
import os

from pkinv.core.geography import members_of, other_membership
from pkinv.core.io import write_table
from pkinv.paths import DATA, OUTPUTS

OUT = asset_path(OUTPUTS, "pakemis_spatial_weights_by_year.csv")

FIELDS = ("source_stream_id", "module", "ipcc_category", "gas", "period_id",
          "spatial_profile_id", "geometry_id", "surface", "district_panel",
          "within_province_placement", "spatial_view", "spatial_time_basis",
          "weight_period", "borrowed_from_period", "substituted_share",
          "control_level", "geometry_vintage", "surface_vintage",
          "other_membership", "allowed_geographies", "evidence_grade", "basis",
          "pattern_hash", "temporal_operator", "correlation_group_id",
          "evidence_role", "validation_ids")

# THE FUSED ROLE, derived - never declared - from the placement the build recorded. The
# twentieth review asked for a single role vocabulary per stream-year (its proposal named
# seven values); four of those seven describe the SPATIAL evidence and are derivable from
# within_province_placement, so they are derived here. The other three are properties of
# instruments, not placements: CONTROL_* describes the quantity lane (evidence_class E1-E4
# already carries it in the monthly panel), and BENCHMARK / VALIDATION_EVENT describe what
# an instrument is FOR, which is the validation catalog's independence_class - joined per
# stream-year through validation_ids below rather than flattened into a role that would
# have to lie about one axis to state the other.
EVIDENCE_ROLE = {
    "per_object_activity": "support_direct",
    "object_partial_activity": "support_direct",
    "object_uniform": "support_direct",
    "raster_or_administrative": "proxy_weight",
    "declared_judgement": "proxy_weight",
    "not_placed": "unlocated",
    "": "",
}

REFERENCE = "FY2023-24"
GEOMETRY_VINTAGE = "geoBoundaries-gbOpen-PAK-ADM2-2019"
NO_NATIVE = "S4:no-native-geometry"

# THE VOCABULARY ANSWERS ONE QUESTION: does the evidence behind this surface have a time axis
# the engine reads for THIS period?
#
# It used to answer a different one. `direct_activity`, `administrative_activity` and
# `dynamic_proxy` were a pure function of `within_province_placement` - a column already in the
# same row - so they carried no information the row did not already hold, and one of them was
# actively misleading. `dynamic_proxy` was applied to a stream placed on ESA WorldCover 2021
# built-up in FY2023-24: nothing about that surface is dynamic, and being the reference year
# does not make a 2021 snapshot an observation of FY2023-24. 196 rows and 632.9 Mt carried that
# label, and a reader counting "measured in their own year" counted all of them.
#
#   annual_observed_activity  the evidence has a time axis AND the engine reads it for this
#                             period (YEAR_KEYED below is the whole of that test)
#   static_structural         a timeless surface - a raster snapshot or a declared judgement
#                             with no time axis at all, in any period including the reference
#   reference_shape_backcast  the reference year's pattern, rescaled to this year's control
#   substituted_surface       the declared surface had no evidence and a substitute placed the
#                             majority of the mass
#   unallocated               never placed below ADM1, in any year
#   not_present               the stream carries no mass this period
#
# Two further values the review proposed - interpolated_between_anchors and nearest_vintage -
# are NOT declared here. No code path produces them, and a value in a closed enum that the
# build never emits makes the vocabulary test pass vacuously: the "derived, never declared"
# rule in this module's own header, broken by the module itself. They are reserved in
# docs/spatial_products_contract.md and will be declared by whatever first emits them.
NOT_PLACED = "not_placed"

# A stream-year earns a year-specific basis only where its evidence HAS a year axis AND the
# engine reads that axis. Both halves are load-bearing: the plant fleet satisfied the first
# while failing the second for the whole of this pass, invisibly.
#
# THE CAPABILITY IS NOT A PROPERTY OF THE SURFACE. `population` is the same static WorldPop
# 2020 raster for nineteen streams; what differs is the DISTRICT PANEL riding on it. Six waste
# streams ride `waste:population`, the 2000-2024 district panel the cube now keys to the
# period; thirteen residential streams ride `resi:*` panels built for the reference year alone.
# Keying on the surface name would have credited all nineteen. So the rule reads the pair.
#
#   (surface, district_panel) -> the periods whose own evidence the engine actually reads,
#                                or None for every registered period
YEAR_KEYED = {
    ("airport_points", ""): None,                 # movements panel, FY2006-07 onward
    ("population", "waste:population"): None,     # district population panel, 2000-2024
    # rc46 Wave 1: the window widened from the ledger's five years to all nine. The
    # plant-fuel ledger still weights FY2019-20 onward by METERED FUEL; the four earlier
    # periods now draw a per-station pool from the generation panel through the name
    # crosswalk (grid_cube._panel_fuel_ledger) - the period's own fuel-labelled GWh, a
    # generation weight standing in for a fuel weight, declared in the engine. Both halves
    # of the year-keyed test hold for every period: the evidence has a year axis, and the
    # engine reads it.
    ("grid_station_points+builtup_fallback", ""): None,
    # FIRMS holds all nine fiscal windows and the proxy is built for the period asked
    # for. rc47 Wave 1 removed the pair's other half outright: the district panel was
    # a reference borrow (2024's FRP split for all nine years) and its candidate
    # replacement - own-year crop area - is a weaker proxy for WHERE burning happens
    # than the fires themselves, so the category carries NO panel and the period's
    # own FIRMS raster is the whole within-province split. The key follows: empty
    # panel half, and the year axis rides the surface alone.
    ("firms_fire", ""): None,
    # rc46 Wave 3: the PBS district crop panel carries the time axis for these pairs - the
    # SURFACE stays a static raster (cropland/SPAM/GLW-derived), and what is year-keyed is
    # the district panel factoring the within-province split, exactly the waste:population
    # construction. The livestock panels (Enteric, Manure management) are NOT here: one
    # census anchor, no interpolation, still a declared backcast.
    ("cropland", "agri:Managed soils"): None,
    ("cropland", "agri:Urea application"): None,
    ("spam_rice", "agri:Rice cultivation"): None,
    ("spam_rice", "agri:Managed soils"): None,
    ("manure_applied", "agri:Managed soils"): None,
    ("glw_livestock", "agri:Managed soils"): None,
    # rc44: the residential district panels, on exactly the terms waste's has been since rc31
    # and for the same reason. Both split a province by that period's district population from
    # population_district.csv (2000-2024) while holding a reference-year per-capita or
    # per-household parameter - waste its generation rate, residential its HIES urban/rural
    # fuel strata. They are the same construction, and until this release residential took the
    # 2023 population for all nine periods while waste took each period's own.
    #
    # The key is (surface, district_panel), and the SURFACE is a fixed raster in both cases:
    # what carries the time axis is the panel that factors it, which is the whole point of the
    # pair being the key rather than the surface alone.
    ("population", "resi:Charcoal"): None,
    ("population", "resi:Coal"): None,
    ("population", "resi:Firewood"): None,
    ("population", "resi:Kerosene"): None,
    ("population", "resi:LPG"): None,
    ("builtup", "resi:Generators"): None,
    ("builtup", "resi:Natural"): None,
    ("cropland", "resi:Crop"): None,
    ("glw_livestock", "resi:Dung"): None,
    # rc47 Wave 5: road transport's provincial shares read the period's OWN OCAC
    # area pages where a complete twelve-month panel exists - FY2021-22 and
    # FY2022-23 (the reference year reads the committed table, graded
    # reference_period on its own). The surface is the static road raster; what
    # carries the year axis in this WINDOW is the provincial share vector, and the
    # six pre-panel years genuinely borrow, which is why this is a window and not
    # a None. The window widens by panel completeness, never by hand.
    ("road_density", ""): ("FY2021-22", "FY2022-23"),
    # rc62: the INDUSTRIAL LIQUIDS, the same mechanism one sector over. The surface is the
    # static built-up raster; what carries the year axis is the provincial share vector, now
    # read per product from OCAC's own Total Industry area pages
    # (pkinv.sectors.industry.province_shape). The panel prints twelve provincial months for
    # FY2021-22, FY2022-23 and FY2023-24 - the reference year reads the committed table and is
    # graded reference_period on its own, so the window names the two before it. The six
    # pre-panel years genuinely borrow, which is why this is a window and not a None.
    #
    # AND WHY THE SURFACE HAS ITS OWN NAME. The key is (surface, district_panel), and the panel
    # is empty for every diffuse industry stream, so the only key otherwise available would be
    # ("builtup", "") - which industry gas, two fugitive streams, two IPPU streams and two
    # transport streams also share. Keying that pair would have claimed a year axis for seven
    # profiles that do not have one. The raster is unchanged; the label records that the
    # PROVINCE vector is read from the year's own area pages.
    #
    # The within-province half of the placement is NOT improved by this and is not claimed to
    # be: it is bracketed in data/stream_spatial_alternatives.csv against the one within-province
    # figure OCAC publishes.
    ("builtup+ocac_area_shares", ""): ("FY2021-22", "FY2022-23"),
    # rc46 Wave 5: solid waste disposal kept its year-keyed panel and changed its
    # surface name - the base is still the per-period district population weight
    # (the ("population", "waste:population") pair above), and the site re-seat only
    # moves each district's mass within that district. The time axis rides the panel,
    # exactly as before; a key that names the surface must follow the rename.
    ("waste_site_points+population_fallback", "waste:population"): None,
    # rc46 Wave 5: the World Bank flare product carries per-site annual volumes 2012-2025
    # and grid_cube.flare_points_for_year reads the period's own calendar column, so every
    # one of the nine periods rides its own year's flares. Here the SURFACE carries the
    # time axis (no district panel factors it) - the airport-movements shape of the key.
    ("flare_points+uniform_fallback", ""): None,
    # rc60: the captive fleet's FRANCHISE MIX has a year axis even though its plant map does
    # not. OGRA publishes the split between the two gas utilities every year in
    # data/activity/power/captive_gas.csv, and it swings hard - the SNGPL captive lane runs
    # 138, 204, 169, 117, 110, 1, 51, 78, 107 MMCFD - while SNGPL's network is Punjab and KP
    # and SSGCL's is Sindh and Balochistan. power.captive_panel weights each franchise's own
    # register geography by those lane totals and power.downscale.load_shares reads it per
    # period, so the engine reads the axis as well as the evidence having one.
    #
    # WHAT THIS DOES NOT CLAIM. The geography WITHIN each franchise is still the one FY2023-24
    # pattern the register measures; only the mix between them is dated. And the register's
    # own disconnection dates are deliberately NOT the key: its gas column is a FY2024
    # snapshot, so the 103 dated plants carry 2.925 MMCFD of 288.01 between them, and keying
    # on membership would be false precision. The surface, not a district panel, carries the
    # axis - the flare shape of the key.
    ("captive_register_points+builtup_fallback", ""): None,
}

# NOT year-keyed, though a register exists - listed so the absence is a decision on the
# record rather than an oversight. Both are absences of DATES, not of data: the register names
# the facilities but not when each began or ceased operating, so no period can be honoured.
#
# This block used to name `firms_fire` as its sharpest case. That was written before the same
# commit added ("firms_fire", "agri:Field burning of residues") to YEAR_KEYED above, and it
# survived - four lines below the table that contradicts it - claiming field burning is the
# reference year's in every period when the registry already said otherwise. A reader who
# trusted the comment over the code would have had it exactly backwards.
KNOWN_UNKEYED = {
    "ippu_register_points+builtup_fallback": "the clinker census is published for one year",
    # rc62: the brick kilns were in NEITHER table - not year-keyed, and not recorded as
    # unkeyed either, which is the silence this block exists to prevent. The placement rides
    # 11,272 points detected from Sentinel-2 imagery of 1-15 July 2023, a single cross-section
    # with no date column, and kiln_frame_vectors builds its FCBK/ZZ split once because both
    # its inputs are timeless.
    #
    # THIS IS NO LONGER AN ABSENCE OF DATA, ONLY OF WIRING. rc62 ingested three dated
    # observations of the fleet (data/activity/industry/brick_kiln_fleet_observations.csv) and
    # laid them on the year axis, and they contradict each other hard enough that chaining them
    # would be a fabrication: between November 2020 and July 2023 the Punjab count falls 10,394
    # to 9,491 while the zig-zag share falls 22.4 to 13.7 percent, which a one-way conversion
    # programme cannot do. Until a reading is chosen ON EVIDENCE rather than by averaging, the
    # placement keeps the one cross-section it can defend and says so here.
    "brick_kiln_points+builtup_fallback": (
        "the kiln detection is a single July 2023 cross-section with no date column; rc62's "
        "dated observations exist but contradict each other and are not yet wired to the "
        "placement"),
}

# Where a surface's own vintage is a single snapshot, name it: the declared 2-3 year offset
# becomes -5..+4 across nine years, and that belongs on the row rather than in a limitation.
# EVERY RASTER SURFACE IS NAMED BY WHAT IT IS (rc63). Three things were wrong here until a
# figure redesign traced each label to data/shared/gis/PROXY_SOURCES.md and the cache sidecars:
#   - `cropland` said "SPAM 2020". It is ESA WorldCover v200 2021, class 40. MapSPAM is the
#     RICE surface, and that one carried no vintage at all.
#   - `road_density`, `manure_applied`, `firms_fire` and the rail network had no entry, so a
#     reader of the product saw a blank and the manuscript figure filed a quarter of national
#     CO2 under "point set or administrative panel".
#   - the roads are an OpenStreetMap extract dated AFTER every period they place, which is why
#     no sentence may say that each surface predates its year.
# A point register has no raster vintage and stays blank; its own date is in geometry_vintage.
SURFACE_VINTAGE = {
    "builtup": "ESA WorldCover 2021", "population": "WorldPop 2020",
    "cropland": "ESA WorldCover 2021", "glw_livestock": "GLW 2020", "uniform": "n/a",
    "spam_rice": "MapSPAM 2020",
    "manure_applied": "derived: ESA WorldCover 2021 cropland x GLW 2020",
    "road_density": "OpenStreetMap roads, Geofabrik extract 2026-08-06",
    "rail_network_line_density": "OpenStreetMap railways, Geofabrik extract 2026-08-06",
    "firms_fire": "VIIRS active-fire detections (per period)",
    # rc62: same raster, and the province vector dated by OCAC's own monthly area editions
    "builtup+ocac_area_shares": "ESA WorldCover 2021 + OCAC area pages (per period)",
}

SUBSTITUTION_MAJORITY = 0.5      # above this, the declared surface did not place the mass

# The nine-year panel, which says which streams a year actually HAS. Not every stream exists in
# every year and the absences are structural, not missing data: cement gas in the FY2020-21
# curtailment year, bagasse power before FY2019-20, railway furnace oil before FY2021-22. A row
# for a stream-year with no mass cannot be graded on how its mass was placed - it would read as
# a backcast of nothing, which is how this was caught - so it is typed `not_present` instead.
PANEL = "pakemis_monthly_fy2015_16_fy2023_24.csv"


def _rows(path):
    return list(_activity_rows(path, comments=True))


def periods():
    return [r["period_id"] for r in _rows(asset_path(DATA, "periods.csv"))]


def substituted_shares():
    """{(stream, period): fraction of the stream's mass placed on a substitute}, read from
    the emitted record rather than inferred from what the stream declares."""
    by_stream = collections.defaultdict(float)
    path = asset_path(OUTPUTS, "pakemis_grid_fallbacks_by_year.csv")
    for row in _rows(path):
        by_stream[(row["source_stream_id"], row["period_id"])] += float(row["weight_share"])
    return by_stream


def present_stream_periods():
    """{(stream, period)} the panel actually carries, so an absence is never graded."""
    from pkinv.report.source_streams import stream_id
    out = set()
    for row in _rows(asset_path(OUTPUTS, PANEL)):
        out.add((stream_id(row["sector_id"], row["category"], row["subitem"], row["gas"]),
                 row["period_id"]))
    return out


# The placements whose class depends on HOW MUCH MASS sits on a located object, mirrored from
# spatial_decomposition so the two cannot drift into grading the same stream differently.
OBJECT_PLACEMENTS = ("per_object_activity", "object_partial_activity", "object_uniform")


def period_grade(placement, substituted_share):
    """The stream's spatial class FOR THIS PERIOD, derived from that period's own placement.

    WHY THIS IS NOT stream["spatial_class"] (rc44, A6b). The source-stream ledger grades a
    stream once, on the reference year, because that is the year its own evidence describes.
    Publishing that letter against all nine periods says a historical year's mass was placed
    as well as the reference year's, and for 36 stream-periods it was not: a year with no
    plant fuel ledger substitutes the entire grid fleet, and the letter should say S2 where
    the reference year earns S1. The substituted share is already measured per period two
    lines above this call - the grade simply reads it instead of ignoring it.

    A TRAP WORTH NAMING. spatial_decomposition.NOT_PLACED is "NA", the CLASS letter, and this
    module's NOT_PLACED is "not_placed", the PLACEMENT value; the two constants share a name
    and mean different things. spatial_class compares its argument against the class letter,
    so handing it this module's placement column verbatim returns S2 for a stream that is not
    placed at all. The translation is explicit here rather than left for the next reader.
    """
    from pkinv.report import spatial_decomposition as spatial
    if placement == NOT_PLACED:
        return spatial.NOT_PLACED
    located = (1.0 - substituted_share) if placement in OBJECT_PLACEMENTS else None
    return spatial.spatial_class(placement, None, located)


def _validation_index():
    """validation_id lists per module - the stream-year <-> instrument join the catalog lacked.

    data/validation_catalog.csv is keyed by validation_id and scoped by module and grain; no
    key in it reaches a (source_stream_id, period_id). The join here is deliberately COARSE:
    a stream-year lists every wired instrument of its module (plus the cross-sector ones),
    because the catalog's own grain column is free text and inventing a finer parse of it
    would claim a precision the catalog does not have. A reader lands on the instrument row
    and reads its scope there. Only wired instruments are listed - a catalog row whose
    wired column says otherwise is an intention, not evidence.
    """
    index = {}
    for row in _rows(asset_path(DATA, "validation_catalog.csv")):
        # wired vocabulary: run_all_phase (built every run), hand_run (built by a person,
        # result committed), declared_absence (no instrument exists - the row documents that).
        # The first two are real instruments; a declared absence is not listable as one.
        if row.get("wired", "").strip() == "declared_absence":
            continue
        index.setdefault(row["module"], []).append(row["validation_id"])
    for lists in index.values():
        lists.sort()
    return index


def build():
    ledger = {r["source_stream_id"]: r
              for r in _rows(asset_path(OUTPUTS, "pakemis_source_streams.csv"))}
    # PER PERIOD, not the reference year's row read nine times. See SURFACES_FIELDS in
    # spatial_by_year: the reference-only file is still written and still describes the
    # reference year; what changed is that a period's grading now reads the period's own
    # placement instead of inheriting FY2023-24's.
    surfaces = {(r["period_id"], r["source_stream_id"]): r
                for r in _rows(asset_path(OUTPUTS,
                                            "pakemis_grid_stream_surfaces_by_year.csv"))}
    reference_pattern = {sid: r.get("pattern_hash", "")
                         for (per, sid), r in surfaces.items() if per == REFERENCE}
    validation = _validation_index()
    substituted = substituted_shares()
    present = present_stream_periods()
    rows = []
    for period in periods():
        for stream_id, stream in sorted(ledger.items()):
            surface_row = surfaces.get((period, stream_id), {})
            surface = surface_row.get("surface", "")
            placement = surface_row.get("within_province_placement", "")
            geometry = stream.get("geometry_id", "")
            proxy = stream.get("spatial_profile_id", "")
            membership = other_membership(proxy) if proxy else "unresolved_group"
            share = min(1.0, substituted.get((stream_id, period), 0.0))
            digest = surface_row.get("pattern_hash", "")
            # DERIVED FROM THE VECTOR, NOT DECLARED ALONGSIDE IT. Reusing the reference year's
            # pattern is a fact about the two hashes and nothing else; a stream whose hash
            # differs from the reference year's was placed on its own pattern even if no
            # column anywhere says so.
            if not digest:
                operator = "not_placed"
            elif period == REFERENCE:
                operator = "reference_period"
            elif digest == reference_pattern.get(stream_id, ""):
                operator = "reference_pattern_reused"
            else:
                operator = "own_period_pattern"

            panel = surface_row.get("district_panel", "")
            allowed = YEAR_KEYED.get((surface, panel), ())
            keyed = allowed is None or period in allowed
            # A surface absent from YEAR_KEYED is keyed for NO period: it has no time axis in
            # any year, which is a different fact from "not keyed for this one" and is what
            # separates a timeless surface from a genuine backcast below.
            never_keyed = allowed is not None and not allowed

            if (stream_id, period) not in present:
                basis, weight_period, borrowed, control = "not_present", "", "", ""
                share = 0.0
            elif geometry == NO_NATIVE or placement == NOT_PLACED:
                basis, weight_period, borrowed, control = "unallocated", "", "", "adm1"
            elif share > SUBSTITUTION_MAJORITY:
                # The declared surface did not place the majority of this mass, whatever the
                # period: calling it a backcast would credit a pattern that was not used.
                basis, weight_period, borrowed, control = ("substituted_surface", period, "",
                                                           "grid")
            elif keyed:
                # the year's own evidence, read for this period
                basis, weight_period, borrowed, control = ("annual_observed_activity", period,
                                                           "", "grid")
            elif never_keyed:
                # A SURFACE WITH NO TIME AXIS AT ALL IS TIMELESS IN EVERY PERIOD, which is
                # what this module's own vocabulary note says static_structural means - "in
                # any period including the reference". The code applied that only to the
                # reference year, so 62 streams whose surface is never year-keyed in any
                # period carried static_structural in FY2023-24 and reference_shape_backcast
                # in the eight others. Their pattern_hash is IDENTICAL across those periods,
                # so nothing was backcast: there was no time-specific pattern to backcast
                # from. The label asserted an operation that did not happen, and a reader
                # counting "rests on a borrowed shape" by period counted all of them, in
                # every year but one. Found 2026-10-05 by comparing the two NE universes of
                # the evidence column against pattern_hash, which rc45 added to make
                # "borrowed" measurable - this is the first thing it measured.
                basis, weight_period, borrowed, control = ("static_structural", period, "",
                                                           "grid")
            elif period == REFERENCE:
                # the reference year cannot be a backcast of itself: its surface is simply
                # timeless, which is what static_structural says
                basis, weight_period, borrowed, control = ("static_structural", period, "",
                                                           "grid")
            else:
                # A GENUINE BACKCAST: the surface HAS a time axis - the engine reads it for
                # some period - and this period is not one of them, so the reference year's
                # pattern is carried and rescaled.
                #
                # WHAT THIS STILL DOES NOT SAY, declared rather than left to be found. For
                # road_density and builtup+ocac_area_shares the axis exists only in FY2021-22
                # and FY2022-23, so the REFERENCE year is not keyed either and its own row
                # says static_structural for the very pattern these rows call a backcast. The
                # label is literally true - these periods do carry the reference year's
                # pattern - and it is kept, because the alternative empties the value: no
                # surface in YEAR_KEYED is keyed in the reference year and unkeyed before it,
                # so relabelling these too would leave reference_shape_backcast emitted by no
                # code path, which this module's header rules out as making the vocabulary
                # test pass vacuously. 51 streams per period are in this state.
                basis, weight_period, borrowed, control = ("reference_shape_backcast",
                                                           REFERENCE, REFERENCE, "grid")

            rows.append({
                "source_stream_id": stream_id, "module": stream.get("module", ""),
                "ipcc_category": stream.get("ipcc_category", ""),
                "gas": stream.get("gas", ""), "period_id": period,
                "spatial_profile_id": proxy, "geometry_id": geometry, "surface": surface,
                "district_panel": panel,
                "within_province_placement": placement,
                "spatial_view": stream.get("spatial_view", ""),
                "spatial_time_basis": basis, "weight_period": weight_period,
                "borrowed_from_period": borrowed, "substituted_share": "%.6f" % share,
                "control_level": control, "geometry_vintage": GEOMETRY_VINTAGE,
                "surface_vintage": SURFACE_VINTAGE.get(surface, ""),
                "other_membership": membership,
                "allowed_geographies": "|".join(members_of(membership)),
                "evidence_grade": ("" if (stream_id, period) not in present
                                   else period_grade(placement, share)),
                "basis": _sentence(basis, period, share),
                "pattern_hash": digest,
                "temporal_operator": operator,
                # WHICH STREAMS MOVE TOGETHER. Streams sharing a (surface, district panel) pair
                # are placed by the SAME vector, so an error in that vector displaces all of
                # them the same way and their spatial errors are perfectly correlated, not
                # independent. Nineteen streams ride `population`; treating them as nineteen
                # independent placements is how a spatial uncertainty gets divided by root
                # nineteen it has not earned. The pair is the same key YEAR_KEYED grades on.
                "correlation_group_id": ("unplaced" if not surface
                                         else "%s|%s" % (surface, panel)),
                "evidence_role": ("not_present" if (stream_id, period) not in present
                                  else EVIDENCE_ROLE[placement]),
                "validation_ids": "|".join(validation.get(stream.get("module", ""), [])
                                           + validation.get("cross-sector", [])),
            })
    return rows


def _sentence(basis, period, share):
    if basis == "annual_observed_activity":
        return ("the evidence behind this surface has a time axis and the engine read it for "
                "%s" % period)
    if basis == "static_structural":
        return ("a timeless surface - a raster snapshot or a declared judgement with no time "
                "axis - so %s is not an observation of it, only the period it was applied to"
                % period)
    if basis == "not_present":
        return ("this stream carries no mass in %s: the national panel has no row for it, and "
                "a stream-year with nothing to place has no geography to grade" % period)
    if basis == "unallocated":
        return ("no native geometry: the mass is published at ADM1 and explicitly "
                "unallocated below it, in every year")
    if basis == "substituted_surface":
        return ("the declared surface had no evidence for %s: %.1f%% of this stream's weight "
                "rode a substitute, and the substitution is priced per province in "
                "pakemis_grid_fallbacks_by_year.csv" % (period, 100.0 * share))
    if basis == "reference_shape_backcast":
        return ("the reference year's surface, rescaled to this year's own control: the "
                "national trajectory is evidenced per year, the within-province split is not "
                "observed for %s" % period)
    raise ValueError("no sentence for basis %r" % basis)


def main():
    rows = build()
    os.makedirs(OUTPUTS, exist_ok=True)
    write_table(OUT, FIELDS, rows)
    counts = collections.Counter(r["spatial_time_basis"] for r in rows)
    print("spatial weight registry -> %s" % OUT)
    print("  %d rows over %d stream-periods"
          % (len(rows), len({(r["source_stream_id"], r["period_id"]) for r in rows})))
    for basis, n in sorted(counts.items()):
        print("  %-26s %5d rows" % (basis, n))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
