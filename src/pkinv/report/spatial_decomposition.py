"""Why each coarse allocation is coarse: geometry, or ignorance, and never the two as one.

THE PROBLEM THIS SOLVES, AND IT IS THE THIRD TIME THIS SHAPE HAS APPEARED. `spatial_method` is
a hand-assigned literal on every component - S1 to S4 written into each sector's evidence
triple and checked against nothing. That is the same construction as `flatness_class`, which
carried its own observed/unobserved answer so the published temporal gap could not move when
PBS's monthly series arrived, and as the per-sector `source_id` constant that labelled every
power profile OCAC including the ones built from PBS. A class that answers from a declaration
cannot report a change, and a repository that keeps improving is a repository where those
declarations keep quietly going false. Two notes went false this week: `geometry_sets.csv` said
the grid fleet was wholly coordinate-unresolved and `stream_grid_proxy.csv` said built-up area
was the surface "until coordinates land". Coordinates landed. Nothing noticed but a person.

So every stream is placed on a second axis, orthogonal to the class it declares:

  diffuse_by_nature   the source has no location to find. Enteric fermentation is spread over
                      a herd and managed soils over cropland; a district allocation is the
                      RIGHT answer and a coordinate campaign would not improve it.
  network_resolved    the source is a network and is allocated along it.
  point_resolved      the source is a set of real places, those places are geocoded, and the
                      allocation uses them.
  point_unresolved    THE GAP. A real location exists and the allocation does not use it -
                      because the members are not geocoded, or because they are and the
                      surface is still a raster. Grid power is the case: 42 of 157 stations
                      now carry a corroborated coordinate and every one of them is still
                      spread over built-up area, because allocating the whole fleet onto the
                      located quarter would misplace the rest.

NOTHING HERE IS DECLARED THAT COULD BE READ. The physics comes from `data/geometry_sets.csv`'s
own `kind`, which already distinguishes a facility set from an administrative one. The
geocoding comes from `data/facility_registry.csv` by evaluating each set's `member_rule`. The
surface actually used comes from `data/stream_grid_proxy.csv`. The mass and the declared class
come from the source-stream ledger. This module adds no new judgement; it joins four registers
that were never asked to agree.

Usage:  python3 -m pkinv.report.spatial_decomposition
Writes: outputs/pakemis_spatial_decomposition.csv
"""

from pkinv.assets import asset_path
import collections
import csv
import os

from pkinv.paths import DATA, OUTPUTS
from pkinv.activity.store import read_rows
from pkinv.core.io import write_table

STREAMS = asset_path(OUTPUTS, "pakemis_source_streams.csv")
GEOMETRY_SETS = asset_path(DATA, "geometry_sets.csv")
REGISTRY = asset_path(DATA, "facility_registry.csv")
GRID_PROXY = asset_path(DATA, "stream_grid_proxy.csv")
OUT = asset_path(OUTPUTS, "pakemis_spatial_decomposition.csv")

FIELDS = ("module", "sub_category", "gas", "geometry_id", "geometry_kind", "placement_class",
          "members", "geocoded_members", "emitting_members", "emitting_geocoded",
          "geocoded_fraction", "allocation_surface",
          "declared_spatial_class", "within_province_placement",
          "measured_spatial_class", "finest_placement_level", "placement_status",
          "geometry_available",
          "class_supported_by_measurement",
          "co2e_Mt_AR5", "unresolved_Mt_AR5", "located_mass_fraction",
          "share_of_national_pct", "basis")

DIFFUSE = "diffuse_by_nature"
NETWORK = "network_resolved"
RESOLVED = "point_resolved"
# rc42 (S-1b): a point geometry the cube consumes, part of whose mass rode a declared
# province-scope fallback; the fallback mass is the stream's unresolved mass
POINT_PARTIAL = "point_partial"
UNRESOLVED = "point_unresolved"
CLASSES = (DIFFUSE, NETWORK, RESOLVED, POINT_PARTIAL, UNRESOLVED)

NO_GEOMETRY = "S4:no-native-geometry"

# The state the class axis was missing, and the reviewer found it. `spatial_class` is about
# HOW MASS IS PLACED BELOW THE PROVINCE - the module's own docstring says so - and S3 asserts
# that "a raster or an administrative share does the placing". For 24 industrial-combustion
# streams NOTHING places them below the province: they are controlled at ADM1 and retained
# whole in pakemis_spatial_unallocated.csv rather than spread. Calling that S3 claimed a
# sub-provincial placement that does not exist.
#
# NOT `NA` FOR THE STREAM, though, because these streams ARE placed - at ADM1, with a province
# on every row. What is absent is a level below it. So the class says NA (there is no
# below-province placement to classify), and two new columns say what IS true: the finest level
# the mass reaches, and whether anything below ADM1 carries it. Evidence quality and product
# availability stop sharing one letter.
NOT_PLACED = "NA"
ALLOCATED = "allocated_below_adm1"
UNALLOCATED = "unallocated_below_adm1"
# A set whose members are this well geocoded can carry an allocation on its own points; below
# it, allocating the whole stream onto the located members would misplace the remainder.
GEOCODED_ENOUGH = 0.95


def _rows(path):
    return read_rows(path)


def selects(rule):
    """A predicate from a geometry set's member_rule, or None where the rule is prose.

    Handles the two forms the registry uses - `module=power` and `facility_id LIKE grid_%` -
    and refuses anything else rather than guessing at a selection.
    """
    tests = []
    for part in rule.split(" AND "):
        part = part.strip()
        if " LIKE " in part:
            key, pattern = part.split(" LIKE ", 1)
            if not pattern.strip().endswith("%"):
                return None
            tests.append((key.strip(), pattern.strip().rstrip("%"), True))
        elif "=" in part:
            key, value = part.split("=", 1)
            tests.append((key.strip(), value.strip(), False))
        else:
            return None
    return lambda row: all(row.get(k, "").startswith(v) if like else row.get(k) == v
                           for k, v, like in tests)


def geocoding():
    """{geometry_id: (members, geocoded, emitting, emitting_geocoded)} from the registry.

    THE FRACTION THAT DECIDES A PLACEMENT IS OVER THE MEMBERS THAT CAN EMIT, and the register's
    own `emits` column says which those are. The grid fleet is 157 stations of which 79 are
    wind, solar or hydel - real assets, correctly registered, and incapable of emitting a
    gramme. Counting them read 42 of 157 where the fact is 30 of 78: it overstated how far the
    fleet is from being locatable and hid that the job is 48 stations rather than 115. Both
    counts are returned, because the register and the metric are different things and a reader
    is owed both.
    """
    registry = _rows(REGISTRY)
    out = {}
    for row in _rows(GEOMETRY_SETS):
        if row["member_source"] != "data/facility_registry.csv":
            # A set drawn from a COORDINATE FILE has coordinates by construction - the rail
            # yards come from yards.csv and the kilns from a detected-asset file, and there is
            # nothing to geocode because the members are points already. Reading that as
            # "membership not resolvable" put 7 located rail yards in the gap.
            members = int(row["expected_members"] or 0)
            out[row["geometry_id"]] = (members, members, members, members)
            continue
        predicate = selects(row["member_rule"])
        if predicate is None:
            count = int(row["expected_members"] or 0)
            out[row["geometry_id"]] = (count, None, count, None)
            continue
        members = [r for r in registry if predicate(r)]
        located = [r for r in members
                   if r.get("geocode_status") == "exact_coordinate_resolved"]
        emitting = [r for r in members if r.get("emits", "yes") != "no"]
        emitting_located = [r for r in located if r.get("emits", "yes") != "no"]
        out[row["geometry_id"]] = (len(members), len(located),
                                   len(emitting), len(emitting_located))
    return out


SURFACES = asset_path(OUTPUTS, "pakemis_grid_stream_surfaces.csv")


def per_stream_surfaces():
    """{source_stream_id: surface} from the cube's own dispatch record.

    rc41 (the nineteenth review's S-3): this used to ask each sector for a per-stream
    dispatcher (only agriculture had one) and fall back to a per-GEOMETRY union of the
    registry's rasters, which named "builtup+cropland" for streams the cube placed on one
    of them and "builtup" for the twenty-four S4 streams the cube never grids. The cube
    now writes what it did, stream by stream (pakemis_grid_stream_surfaces.csv), and this
    phase runs after it and reads that - one arithmetic path, not a reconstruction.
    """
    return {row["source_stream_id"]: row["surface"] for row in _rows(SURFACES)}


def surfaces():
    """{geometry_id: raster} - kept for readers of the register, no longer the source of
    allocation_surface (see per_stream_surfaces)."""
    geometry = _rows(asset_path(DATA, "stream_geometry.csv"))
    out = collections.defaultdict(set)
    for proxy in _rows(GRID_PROXY):
        for stream in geometry:
            if (stream["module"] == proxy["module"]
                    and stream["category"] == proxy["category"]
                    and stream["subitem_prefix"].startswith(proxy["subitem_prefix"])):
                out[stream["geometry_id"]].add(proxy["raster_proxy"])
    return {geometry_id: "+".join(sorted(rasters)) for geometry_id, rasters in out.items()}


def unallocated_streams():
    """{(module, sub_category slug)} retained whole at ADM1 rather than placed below it.

    THE CUBE'S OWN RULE, applied to the register the cube dispatches on: a stream whose
    geometry is S4:no-native-geometry has a provincial control and nothing below it, and
    grid_cube retains exactly those whole at ADM1 (`if stream["geometry_id"] ==
    NO_NATIVE_GEOMETRY` -> the unallocated ledger). rc41: this function used to READ the
    cube's ledger back - a product of a phase that runs after the class axis and that
    itself reads the class axis - so every build had compared against the previous
    release's file, and an empty outputs/ made the class axis grade the industry streams
    S3. Derived here from the stream ledger's geometry column instead; the cube's ledger
    is asserted equal to this set by tests/test_spatial_decomposition.py, so the two still
    cannot disagree - now by test rather than by reading one into the other.
    """
    return {(row["module"], _slug(row["sub_category"]))
            for row in _rows(STREAMS) if row["geometry_id"] == NO_GEOMETRY}


def unallocated_ledger_streams():
    """{(module, sub_category slug)} the cube's unallocated ledger actually names - the
    product side of the identity unallocated_streams() derives; empty when the cube has not
    run in this tree."""
    path = asset_path(OUTPUTS, "pakemis_spatial_unallocated.csv")
    if not os.path.exists(path):
        return set()
    out = set()
    for row in _rows(path):
        # The ledger keys streams as "module|category|SUBITEM|gas" with the subitem slugified;
        # the decomposition carries the subitem in its readable form. The join is on the slug,
        # made the same way on both sides rather than matched by eye.
        parts = row["source_stream_id"].split("|")
        if len(parts) >= 3:
            out.add((row["module"], parts[2]))
    return out


def _slug(text):
    return text.strip().lower().replace(" ", "-")


def fallback_mass_by_stream():
    """{source_stream_id: (fallback share of the stream's mass, Mt CO2e AR5 on a fallback
    surface)} from the cube's own ledger of province-scope fallback events (rc42, S-1b)."""
    path = asset_path(OUTPUTS, "pakemis_grid_fallbacks.csv")
    out = {}
    if not os.path.exists(path):
        return out
    for row in _rows(path):
        if row["scope"] != "province":
            continue
        share, mass = out.get(row["source_stream_id"], (0.0, 0.0))
        out[row["source_stream_id"]] = (share + float(row["weight_share"] or 0.0),
                                        mass + float(row["affected_Mt_AR5"] or 0.0))
    return out


def build():
    fallbacks = fallback_mass_by_stream()
    kinds = {r["geometry_id"]: r["kind"] for r in _rows(GEOMETRY_SETS)}
    placements = {r["geometry_id"]: r["within_province_placement"]
                  for r in _rows(GEOMETRY_SETS)}
    measured = geocoding()
    by_geometry = surfaces()
    by_stream = per_stream_surfaces()
    unallocated = unallocated_streams()

    out = []
    for stream in _rows(STREAMS):
        geometry = stream["geometry_id"]
        kind = NO_GEOMETRY if geometry == NO_GEOMETRY else kinds.get(geometry)
        if kind is None:
            raise KeyError("%s cites geometry %r, which data/geometry_sets.csv does not "
                           "register" % (stream["sub_category"], geometry))
        members, geocoded, emitting, emitting_geocoded = measured.get(
            geometry, (0, None, 0, None))
        fraction = ((emitting_geocoded / emitting)
                    if (emitting_geocoded is not None and emitting) else None)
        # rc39 A9: ASK THE SECTOR FIRST. by_geometry answers per GEOMETRY, and one diffuse
        # ADM2 geometry can carry thirty-four streams on five different rasters - so a
        # per-geometry answer is wrong for at least twenty-nine of them, and agriculture's
        # were all published as `population`, inherited from another module declaring that
        # surface for the same shared geometry. A sector that knows its own stream -> raster
        # dispatch now supplies it; the geometry join remains for sectors that do not.
        # rc41: the cube's own record, stream by stream; a stream the cube did not place
        # (S4) reads "none", and a stream absent from the record is a build failure
        if stream["source_stream_id"] not in by_stream:
            raise KeyError("%s is not in pakemis_grid_stream_surfaces.csv - the cube did not "
                           "record a surface for it" % stream["source_stream_id"])
        surface = by_stream[stream["source_stream_id"]]
        mass = float(stream["emissions_ar5"] or 0.0)

        if kind in (NO_GEOMETRY, "adm_diffuse"):
            placement, basis = DIFFUSE, (
                "the source has no location to find; an administrative allocation is the "
                "right answer and coordinates would not improve it")
        elif kind == "network":
            placement, basis = NETWORK, "allocated along the network it runs on"
        elif placements.get(geometry) in ("per_object_activity",
                                          "object_partial_activity",
                                          "object_uniform") and \
                fallbacks.get(stream["source_stream_id"], (0.0, 0.0))[1] > 1e-9:
            # rc42 (S-1b): THE MASS DECIDES, not the member count. rc41 called the coal
            # grid stream point_resolved with 0 unresolved while 90 percent of its mass
            # rode the built-up fallback - the fraction it printed was over register
            # members, and the declared placement made every point geometry RESOLVED by
            # construction. A point geometry whose ledger carries fallback mass is
            # point_partial, and the fallback mass is its unresolved mass, so this table
            # and pakemis_grid_fallbacks.csv cannot disagree by 34.7 Mt again.
            fb_share, fb_mass = fallbacks[stream["source_stream_id"]]
            placement, basis = POINT_PARTIAL, (
                "%s of %d members that can emit carry a coordinate, and %.1f%% of the "
                "stream's mass (%.3f Mt) fell back to %s where a province had no located "
                "member with its own activity - every fallback a ledger event"
                % (str(emitting_geocoded), emitting, 100.0 * fb_share, fb_mass,
                   surface or "the proxy"))
        elif placements.get(geometry) in ("per_object_activity",
                                          "object_partial_activity",
                                          "object_uniform"):
            # THE DISCRIMINATOR IS WHETHER THE CUBE'S DISPATCH CONSUMES THE POINTS,
            # read from the placement register the dispatch is proved against - not
            # the geocoded fraction alone. Until Wave 5 a below-95% fleet was
            # UNRESOLVED by definition because no allocation used partial points;
            # the captive pattern (own points for the located share, a declared
            # fallback event for the rest) changed that, and calling a consumed
            # fleet "a location the allocation does not use" would be the exact
            # stale-note class this file exists to kill. The geocoded fraction
            # still decides the S-class (S1 needs >= 95%), and it is printed here.
            placement, basis = RESOLVED, (
                "%s of %d members that can emit carry a coordinate; the "
                "allocation rests on its own points and %s is the declared "
                "fallback where a province has none - every fallback a ledger "
                "event"
                % ("all" if fraction is not None
                   and fraction >= GEOCODED_ENOUGH
                   else str(emitting_geocoded), emitting,
                   surface or "the proxy"))
        elif fraction is not None and fraction < GEOCODED_ENOUGH:
            placement, basis = UNRESOLVED, (
                "%d of %d members that can emit carry a coordinate, and the "
                "ALLOCATION spreads on %s without consuming them; below %.0f%% "
                "the located members cannot carry the whole stream, and the "
                "placement register records no point mechanism"
                % (emitting_geocoded, emitting,
                   surface or "the declared fallback", 100 * GEOCODED_ENOUGH))
        elif fraction is None:
            placement, basis = UNRESOLVED, (
                "the set's membership is not resolvable from the facility registry, so "
                "whether its places are located cannot be measured")
        else:
            placement, basis = UNRESOLVED, (
                "%d of %d members located, but the placement register records no "
                "point mechanism - a located fleet the allocation ignores"
                % (emitting_geocoded, emitting))

        declared = stream["spatial_class"]
        # A stream with no native geometry is not automatically raster-placed: the cube may
        # place it on a proxy surface, or may not place it below ADM1 at all. Which of those
        # happened is read from the unallocated ledger rather than assumed from the absence
        # of geometry, because those are different products and used to share a letter.
        if geometry == NO_GEOMETRY:
            placement_basis = (NOT_PLACED
                               if (stream["module"], _slug(stream["sub_category"]))
                               in unallocated
                               else "raster_or_administrative")
        else:
            placement_basis = placements[geometry]
        located_mass = (None if geometry == NO_GEOMETRY or placements.get(geometry) not in
                        ("per_object_activity", "object_partial_activity", "object_uniform")
                        else 1.0 - fallbacks.get(stream["source_stream_id"], (0.0, 0.0))[0])
        # THE rc42 (S-1b) CORRECTION IS GONE, AND ITS REMOVAL IS THE POINT OF THIS COMMIT.
        # It multiplied `1.0 - fallback_fraction` by the located share because the cube pooled
        # a province's share across located siblings WITHOUT emitting an event, so the ledger
        # alone read the gas fleet as "1.0 located" with half of it unlocated. The cube now
        # emits that event and prices it, so the fallback fraction already carries the
        # unlocated fuel: multiplying again would square it, and nothing would fail - the
        # letters would simply get quietly pessimistic. One measure, one place.
        derived = spatial_class(placement_basis, fraction, located_mass)
        out.append({
            "module": stream["module"], "sub_category": stream["sub_category"],
            "gas": stream["gas"], "geometry_id": geometry, "geometry_kind": kind,
            "placement_class": placement,
            "members": members, "geocoded_members": "" if geocoded is None else geocoded,
            "emitting_members": emitting,
            "emitting_geocoded": "" if emitting_geocoded is None else emitting_geocoded,
            "geocoded_fraction": "" if fraction is None else round(fraction, 4),
            "allocation_surface": surface,
            "declared_spatial_class": declared,
            "within_province_placement": placement_basis,
            "measured_spatial_class": derived,
            "finest_placement_level": "adm1" if derived == NOT_PLACED else "below_adm1",
            "placement_status": UNALLOCATED if derived == NOT_PLACED else ALLOCATED,
            "geometry_available": "no" if geometry == NO_GEOMETRY else "yes",
            "class_supported_by_measurement": "yes" if derived == declared else "no",
            "co2e_Mt_AR5": round(mass, 8),
            "unresolved_Mt_AR5": (round(mass, 8) if placement == UNRESOLVED else
                                  round(fallbacks[stream["source_stream_id"]][1], 8)
                                  if placement == POINT_PARTIAL else 0.0),
            "located_mass_fraction": ("" if located_mass is None else round(located_mass, 4)),
            "share_of_national_pct": 0.0, "basis": basis,
        })
    total = sum(r["co2e_Mt_AR5"] for r in out)
    for row in out:
        row["share_of_national_pct"] = round(100.0 * row["co2e_Mt_AR5"] / total, 4)
    return sorted(out, key=lambda r: (-r["unresolved_Mt_AR5"], r["module"],
                                      r["sub_category"], r["gas"]))


def spatial_class(placement, fraction, located_mass=None):
    """THE SPATIAL CLASS, DERIVED. Not a check on a letter someone typed - the letter itself.

    Every stream in this inventory is controlled provincially, because that is the level the
    activity statistics exist at. So the class cannot be about what binds the total; if it
    were, every stream would be S3 and the axis would carry no information. It is about HOW
    THE MASS IS PLACED BELOW THE PROVINCE, which is the only part an allocation invents, and
    it is read from two measured facts:

      * `within_province_placement` on the geometry set - what the cube's own weight actually
        distributes mass by, one row per set, proved against the cube's dispatch by test;
      * the geocoded fraction over the members that CAN EMIT, from the facility registry.

    S1  native source geometry consuming observed per-object activity: the allocation knows
        which object emitted how much, and enough of the objects are located to carry it.
    S2  the geometry IS used below the province, but what distributes mass across it is not
        observed per-object activity - a uniform spread, a partial one, or declared judgement.
    S3  nothing of the geometry reaches below the province: a raster or an administrative
        share does the placing, whether or not a facility register exists.

    The last is the one that moves mass, and it is deliberate. A registered fleet whose
    coordinates the allocation never opens is not a facility proxy; `geometry_sets.csv` says
    as much about the grid fleet in its own note - the surface stays built-up until coverage
    supports points - and the class now says the same thing in the column a reader sorts on.
    """
    if placement == NOT_PLACED:
        # Nothing reaches below the province. There is no sub-provincial placement to grade,
        # and grading it S3 would assert a raster or administrative share that is not there.
        return NOT_PLACED
    if placement in ("raster_or_administrative", "not_used", ""):
        return "S3"
    if placement == "per_object_activity":
        # rc42 (S-1b): the MASS the located objects carry decides, where the cube's ledger
        # measures it; the member fraction stands in only where no ledger row exists. A
        # fleet 44 percent located by count but 100 percent located by activity places
        # every tonne on its own point, and a class that said S2 for it would be reading
        # the register instead of the allocation.
        if located_mass is not None:
            return "S1" if located_mass >= GEOCODED_ENOUGH else "S2"
        # rc47 Wave 2: `fraction is None` used to fall through to S1 - the absence
        # of a located measurement earning the BEST grade, which is how 187 Mt of
        # panel-year power shipped S1 on evidence nobody had computed. No
        # measurement, no S1: the burden of proof points the other way.
        if fraction is not None and fraction >= GEOCODED_ENOUGH:
            return "S1"
    return "S2"


def summary(rows=None):
    rows = rows if rows is not None else build()
    total = sum(r["co2e_Mt_AR5"] for r in rows)
    out = collections.defaultdict(float)
    for row in rows:
        out[row["placement_class"]] += row["co2e_Mt_AR5"]
    return {k: (v, 100.0 * v / total) for k, v in sorted(out.items())}


def main():
    rows = build()
    os.makedirs(OUTPUTS, exist_ok=True)
    write_table(OUT, FIELDS, rows)
    print("spatial decomposition -> %s" % OUT)
    print("  %d streams" % len(rows))
    for name, (mass, share) in summary(rows).items():
        print("    %-20s %8.2f Mt  %5.1f%%" % (name, mass, share))
    gap = [r for r in rows if r["unresolved_Mt_AR5"] > 0]
    total = sum(r["co2e_Mt_AR5"] for r in rows)
    print("  THE GAP: %.1f%% of national mass has a real location the allocation does not use"
          % (100.0 * sum(r["unresolved_Mt_AR5"] for r in gap) / total))
    seen = set()
    for row in gap:
        key = (row["module"], row["geometry_id"])
        if key in seen:
            continue
        seen.add(key)
        print("    %-11s %-28s %s" % (row["module"], row["geometry_id"][:28], row["basis"]))
    unsupported = [r for r in rows if r["class_supported_by_measurement"] == "no"]
    print("  %d streams declare a spatial class the measurement does not support"
          % len(unsupported))
    for row in unsupported[:6]:
        print("    %-11s %-30s declares %s on a %s geometry"
              % (row["module"], row["sub_category"][:30], row["declared_spatial_class"],
                 row["geometry_kind"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
