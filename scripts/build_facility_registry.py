"""Build the national facility registry: one stable id per physical facility.

WHY. The reviewer's highest-leverage Stage 5 step: no shared facility identity existed
outside IPPU's 34 rows, cross-sector joining ran on name strings repaired by a hand-written
26-entry alias dict, and the largest geocoded asset in the repository - 1,068
coordinate-bearing captive plants - was read by nothing. This registry gives every physical
facility one id, one coordinate record with a confidence grade, and one ADM2 link, so a
source stream can name the geometry it emits from instead of a province share.

WHAT IS AND IS NOT A ROW. A row is a physical facility the inventory allocates to, wants to
allocate to, or (status=prospective) will need the day its category is estimated. VIIRS
flare sites and MARS plumes are NOT rows: they are observation evidence, derived into
outputs/ by the fugitives runner, and putting outputs-derived points into a data/ registry
would invert the data->outputs flow. They are registered as observation sets in
data/geometry_sets.csv instead.

STATUS IS THE HONESTY COLUMN.
  active                 allocated to by an estimated stream, geometry present
  coordinate_unresolved  the facility is real and referenced; its coordinates are not held
                         (157 grid plants located only to towns; 33 of 34 IPPU works;
                         the two LNG terminals) - never invented, never geocoded by guess
  prospective            real, geocoded, and referenced by NO estimated stream yet
                         (11,272 brick kilns awaiting the industrial-solids category)

Deterministic; --check re-derives and diffs.

Usage:  python3 scripts/build_facility_registry.py [--check]
Writes: data/facility_registry.csv
"""
import csv
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.assets import asset_path

from pkinv.core import adm2                                # noqa: E402
from pkinv.core.gis import adm2_point                      # noqa: E402
from pkinv.core.io import read_rows

OUT = asset_path(ROOT, "data", "facility_registry.csv")

FIELDS = ("facility_id", "module", "name", "category_hint", "latitude", "longitude",
          "coord_confidence", "coordinate_source", "coordinate_source_reference",
          "coordinate_quality", "boundary_scope", "geocode_status",
          "adm2_id", "geometry_kind", "status", "source_file",
          "source_key", "note", "licence", "emits",
          # Pass 2 (sixteenth review, Wave 0): the time-validity and activity columns a
          # facility-resolved spatial allocation needs. A plant cannot receive emissions
          # before it operated, so valid_from/valid_to are first-class; capacity and
          # activity_source are what turn a located facility into a weighted one. They
          # are POPULATED ONLY where a held source states them (the IPPU register today;
          # the grid fleet in Wave 5) - an empty cell is not-stated, never a guess.
          "technology", "fuel_or_process", "valid_from", "valid_to",
          "capacity", "capacity_unit", "activity_source")

# WHETHER THE FACILITY CAN EMIT AT ALL, which is not the same question as whether it is in the
# register. The grid fleet is 157 stations and 79 of them are wind, solar or hydel: real assets,
# correctly registered, and incapable of emitting a gramme. A coverage fraction for an EMISSIONS
# allocation that counts them is measuring the wrong fleet - it read 42 of 157 when the fact is
# 30 of 78, which overstates the distance to a located fleet and hides that the job is 48
# stations rather than 115. The station types are listed rather than inferred from a name.
NON_EMITTING_STATION_TYPES = frozenset({
    "WTs", "Solar", "Run of River", "Run of Canal", "Reservoir", "Hydro",
    "Canal Fall/Run of River", "Run of River/Canal", "High Head",
})

# The licence a row's GEOMETRY travels under, derived from its coordinate source
# (rc11, the seventh review's ODbL item: 71 OSM-derived rows shipped unlicensed).
# Extracted coordinate tables built from OpenStreetMap are DERIVATIVE DATABASES
# under ODbL 1.0 and carry share-alike obligations - not CC-BY, and not covered by
# a produced-work notice. Rows whose geometry comes from a non-OSM source carry
# that source's licence where declared, and source-document-register otherwise
# (the licence_status column of data/source_documents.csv is the authority).
def _licence(coordinate_source):
    src = (coordinate_source or "").lower()
    if src.startswith(("openstreetmap", "osm")):
        return "odbl-1.0 (OpenStreetMap contributors; derivative database)"
    if src.startswith("hamdani"):
        return "cc-by-4.0 (Hamdani et al. 2025, Zenodo)"
    return "source-document-register"

# The closed confidence vocabulary the fifth review asked for, replacing the eleven
# ad-hoc strings that had accumulated. Source-specific grades map DOWN into it; the
# original grade survives verbatim in coordinate_quality.
CONFIDENCE_VOCAB = ("explicit-source", "high", "medium", "low", "unresolved")
_CONFIDENCE_MAP = {
    "explicit": "explicit-source", "high": "high", "tier-a": "high", "author": "high",
    "mapped industrial facility": "high", "medium": "medium",
    # The Global Energy Monitor cement tracker grades its own coordinates. `exact` is a
    # coordinate the compiler placed on the plant, which is what explicit-source means here;
    # `approximate` is deliberately not promoted to it by having passed the same district
    # test as its neighbours.
    "exact": "explicit-source", "approximate": "medium",
    "read-from-scan": "medium", "low": "low", "weak": "low", "none": "unresolved",
    "": "unresolved",
}


def _confidence(raw):
    return _CONFIDENCE_MAP[raw.strip().lower() if raw else ""]

BBOX = (60.5, 23.5, 77.5, 37.5)

# The two LNG import terminals the fugitives sector counts (OGRA SoIR station count = 2).
# Both at Port Qasim, Malir district. Coordinates deliberately absent: none are held in any
# archived source, and a coordinate typed from memory is a fabricated one.
LNG_TERMINALS = [
    ("lng_engro_elengy", "Engro Elengy Terminal", "Port Qasim"),
    ("lng_pgpc", "Pakistan GasPort Consortium Terminal", "Port Qasim"),
]


def _read(relative):
    return read_rows(asset_path(ROOT, relative))


def _slug(text):
    s = re.sub(r"[^a-z0-9]+", "_", text.strip().lower()).strip("_")
    return re.sub(r"_+", "_", s)


def _adm2_of_point(lat, lon, _cache={}):
    """The canonical unit whose polygon contains a point, or "unresolved".

    rc60. The point is the better evidence than a name wherever both exist, and
    scripts/ingest_grid_plant_coordinates.py now resolves its own rows this way. The gas-fleet
    table reaches this builder for the first time in the same release, so its points get the
    same treatment rather than depending on whether GEM's city string happens to be a district.
    """
    if not str(lat).strip() or not str(lon).strip():
        return "unresolved"
    if "grid" not in _cache:
        from pkinv.core.gis.grid import build_grid
        _cache["grid"] = build_grid()
    grid = _cache["grid"]
    from pkinv.core.gis.grid import district_index_at
    index = district_index_at([(float(lon), float(lat))])[0]
    if index is None or index < 0:
        return "unresolved"
    return _adm2_or_unresolved(grid.districts[index])


_PROVINCE_OF_ADM2 = {}


def _province_of(adm2_id):
    """The province a canonical unit belongs to, for the consistency gate below."""
    if not _PROVINCE_OF_ADM2:
        for row in _read("data/adm2_canonical.csv"):
            _PROVINCE_OF_ADM2[row["adm2_id"]] = row["adm1_name"] or row["province_id"]
    return _PROVINCE_OF_ADM2.get(adm2_id, "")


def _point_agrees_with_stated_province(adm2_id, stated_province):
    """Whether a point's district sits in the province the source says the station is in.

    rc60. THIS GATE EXISTS BECAUSE TWO STATIONS WERE SWAPPED and nothing noticed. NEPRA Table 5
    prints "Hub, Balochistan" for Hub Power and "Karachi, Sindh" for Tapal Energy; GEM's own
    city strings agree ("Las Bela" and "Keamari"). But the held coordinates fall on the wrong
    sides of a boundary the ADM2 file draws differently from either source - Hub's point lands
    5 km south of Lasbela's southern edge, in Karachi, and Tapal's lands 45 km west of Tapal,
    in Lasbela - so the ladder placed Hub Power, the largest furnace-oil station in the country,
    in Karachi, and Tapal Energy in Balochistan.

    A point is better evidence than a name, which is why the ladder prefers it. It is not better
    evidence than a name PLUS a second independent name, and when a point contradicts both it is
    the point that has to justify itself. Where they disagree the station keeps its stated
    location and the row says the coordinate disagreed - an observation kept, not discarded.
    """
    if not stated_province or not adm2_id or adm2_id == "unresolved":
        return True
    resolved = _province_of(adm2_id)
    if not resolved:
        return True
    return _province_key(resolved) == _province_key(stated_province)


def _province_key(name):
    """A province name reduced to what two sources can be expected to agree on.

    NEPRA writes "Azad Jammu & Kashmir" and the canonical register writes "Azad Jammu and
    Kashmir". A literal comparison made that a disagreement and unplaced Mangla, which is the
    one station of the five this gate flagged where the two sources were in fact saying the
    same thing - a gate that cries wolf costs real placements, so the normalisation is part of
    the gate rather than an afterthought.
    """
    text = (name or "").strip().lower().replace("&", " and ")
    return " ".join(text.split())


def _adm2_or_unresolved(name):
    if not name or not name.strip():
        return "unresolved"
    try:
        return adm2.resolve(name)
    except KeyError:
        return "unresolved"


def build():
    rows = []

    def add(facility_id, module, name, category, lat, lon, confidence, adm2_id, kind,
            status, source_file, source_key, note="", coordinate_source="",
            coordinate_source_reference="", coordinate_quality="", boundary_scope="",
            geocode_status="", emits="yes", technology="", fuel_or_process="",
            valid_from="", valid_to="", capacity="", capacity_unit="",
            activity_source=""):
        if not geocode_status:
            geocode_status = ("exact_coordinate_resolved" if str(lat).strip()
                              else "exact_coordinate_unresolved")
        rows.append({"facility_id": facility_id, "module": module, "name": name,
                     "category_hint": category, "latitude": lat, "longitude": lon,
                     "coord_confidence": _confidence(confidence),
                     "coordinate_source": coordinate_source,
                     "coordinate_source_reference": coordinate_source_reference,
                     "coordinate_quality": coordinate_quality or confidence or "none",
                     "boundary_scope": boundary_scope,
                     "geocode_status": geocode_status,
                     "adm2_id": adm2_id,
                     "geometry_kind": kind, "status": status, "source_file": source_file,
                     "source_key": source_key, "note": note,
                     "licence": _licence(coordinate_source),
                     "emits": emits, "technology": technology,
                     "fuel_or_process": fuel_or_process, "valid_from": valid_from,
                     "valid_to": valid_to, "capacity": capacity,
                     "capacity_unit": capacity_unit,
                     "activity_source": activity_source})

    # --- power: captive fleet (geocoded) --------------------------------------------------
    # 54 company names appear at more than one site (multi-plant groups: Interloop runs
    # three registered sets). The id disambiguates by district, then by position within the
    # district - deterministic because the register is sorted by (province, district, name).
    captive_rows = _read("data/activity/power/captive_register.csv")
    name_counts = {}
    for r in captive_rows:
        name_counts[r["physical_plant"]] = name_counts.get(r["physical_plant"], 0) + 1
    seen = {}
    for r in captive_rows:
        base = "captive_%s" % _slug(r["physical_plant"])
        if name_counts[r["physical_plant"]] > 1:
            base = "%s_%s" % (base, _slug(r["district"]) or "x")
        seen[base] = seen.get(base, 0) + 1
        if seen[base] > 1:
            base = "%s_%d" % (base, seen[base])
        r["_facility_id"] = base
    for r in captive_rows:
        has = bool(r["latitude"].strip())
        add(r["_facility_id"], "power", r["physical_plant"],
            "Captive gas self-generation (1A2)",
            r["latitude"] if has else "", r["longitude"] if has else "",
            r["coord_confidence"] if has else "none",
            _adm2_or_unresolved(r["district"]), "point",
            "active" if has else "coordinate_unresolved",
            "data/activity/power/captive_register.csv", r["physical_plant"],
            "" if has else "in the register without coordinates",
            coordinate_source="captive register connection records" if has else "",
            coordinate_source_reference=("data/activity/power/captive_register.csv"
                                         if has else ""),
            boundary_scope="plant site" if has else "district",
            # rc60: the first real use of the two columns this registry declared for exactly
            # this purpose and then populated on two rows in its whole life. A NEPRA licence
            # year is when a plant could first have generated; a utility's disconnection date
            # is when its metered gas stopped. Both come from source sheets the captive ingest
            # had never read, and both are empty where the sheet states nothing - an empty
            # cell here is not-stated, never a guess.
            valid_from=r.get("licence_year", ""),
            valid_to=r.get("date_of_disconnection", ""))

    # --- power: grid plants -------------------------------------------------------------
    # Coordinates land here for the stations two independently compiled databases place
    # inside the district or province this inventory already declared for them
    # (scripts/ingest_grid_plant_coordinates.py). The rest keep the town they always had:
    # the fleet was wholly coordinate-unresolved and is now partly resolved, which is a
    # statement about the REGISTRY. Whether the cube's allocation uses these points is a
    # separate question and a separate gate.
    located = {r["plant"]: r
               for r in _read("data/activity/power/plant_coordinates.csv")}
    # rc42 (the twentieth review's S-1): the coal fleet's coordinates, keyed by the ledger's
    # station names. Three of the eight coal stations (ThalNova, Thar Coal Block-I, Thar
    # Energy) have no row in plant_locations.csv - NEPRA's table prints no location for
    # them - so they never entered the registry at all; they enter here from the coal table,
    # with it as their source file, and the fleet count moves 157 -> 160 by name.
    coal = {r["plant"]: r for r in _read("data/activity/power/coal_plant_coordinates.csv")} \
        if os.path.exists(asset_path(ROOT, "data", "activity", "power", "coal_plant_coordinates.csv")) else {}
    # rc60: the GAS fleet's coordinates. grid_cube.py has read this table since rc42 but this
    # builder never did, so the registry said "no coordinate source corroborates a point" for
    # stations whose GEM-exact point was sitting in the repo - TPS Nandipur among them.
    gas = {r["plant"]: r for r in _read("data/activity/power/gas_plant_coordinates.csv")} \
        if os.path.exists(asset_path(ROOT, "data", "activity", "power",
                                       "gas_plant_coordinates.csv")) else {}
    # rc60: the district a station is placed in by the source workbook, for the stations that
    # have no coordinate in any held table AND whose town is a locality the ADM2 register
    # cannot spell-correct. It is the weakest placement here and it says so: the workbook
    # states a district per plant with no per-plant provenance, and its grid sheets carry no
    # coordinates at all, so this is an administrative assignment rather than an observation.
    # through plant_name_crosswalk.csv, because the workbook and NEPRA spell the same station
    # differently - HUBCO against Hub Power, Kot Addu (KAPCO) against KAPCO - and a lookup that
    # misses on spelling would leave a station unplaced while its district sat one row away.
    crosswalk = {}
    for r in _read("data/activity/power/plant_name_crosswalk.csv"):
        crosswalk[r["panel_name"]] = r["canonical_plant"] or r["panel_name"]
    workbook = {}
    for r in _read("data/activity/power/grid_plant_district.csv"):
        for key in {r["plant"], crosswalk.get(r["plant"], r["plant"])}:
            workbook.setdefault(key, r["adm2_id"])
    towns = {r["plant"] for r in _read("data/activity/power/plant_locations.csv")}
    for plant, r in sorted(coal.items()):
        if plant in towns:
            continue
        # THE GEOMETRY DECIDES, AND THE SOURCE'S CLAIM IS RECORDED BESIDE IT. This used to
        # read _adm2_or_unresolved(r["gem_district"]) - the district STRING the third-party
        # tracker supplies next to the coordinates - and on 2026-10-05 that shipped ThalNova
        # and Thar Energy in sindh_thatta, about 250 km from the coordinates in the same row.
        # GEM gives "Thatta" for all three Thar coalfield stations; Engro Powergen Thar
        # escaped only because NEPRA's location table lists it and it leaves through the
        # branch above, so three stations about a kilometre apart landed in two districts.
        # The province boundary audit had computed Tharparkar for every one of them from this
        # same frame. A district name is a claim ABOUT a coordinate, not an independent fact,
        # and this repository holds the frame that adjudicates it.
        #
        # An empty answer is kept rather than coerced: China Power Hub falls inside no ADM2
        # polygon at all, which is a boundary error the audit reports and not a station error,
        # and for it the source's district (Lasbela, correct) is still the best available
        # answer. So the geometry wins where it resolves, the string is the fallback where it
        # does not, and a disagreement is written into the row's note either way.
        shape = adm2_point.containing(float(r["longitude"]), float(r["latitude"]))
        gem_claim = (r["gem_district"] or "").strip()
        resolved = _adm2_or_unresolved(shape) if shape else _adm2_or_unresolved(gem_claim)
        provenance = ("ADM2 polygon containing the point" if shape
                      else "no ADM2 polygon contains the point; the source's district stands")
        disagreement = ""
        if shape and gem_claim and shape.lower() != gem_claim.lower():
            disagreement = ("; the source names district %r, which does not contain this "
                            "point" % gem_claim)
        add("grid_%s" % _slug(plant), "power", plant, "Electricity and heat production",
            r["latitude"], r["longitude"], "high",
            resolved, "point", "active",
            "data/activity/power/coal_plant_coordinates.csv", plant,
            "GEM exact location corroborated by Climate TRACE within %s km (%s); absent from "
            "NEPRA's location table; district from the %s%s"
            % (r["agreement_km"], r["gem_plant"], provenance, disagreement),
            coordinate_source="Global Energy Monitor coal plant tracker / Climate TRACE power assets",
            coordinate_source_reference="data/activity/power/coal_plant_coordinates.csv",
            coordinate_quality="high", boundary_scope="plant site", emits="yes")
    for r in _read("data/activity/power/plant_locations.csv"):
        found = located.get(r["plant"])
        from_gas = None if found else gas.get(r["plant"])
        point = found or from_gas
        # the district, in descending order of evidence: the point's own polygon, the gas
        # table's GEM district, the town, and last the workbook's administrative assignment
        district = ""
        scope = "town"
        disputed = ""
        if found and found["adm2_id"] != "unresolved":
            district, scope = found["adm2_id"], "plant site"
        elif found:
            # rc61: THE LADDER SKIPPED ITS OWN TOP RUNG. `found` is the primary coordinate table,
            # and where its `adm2_id` column reads `unresolved` - because the coordinate ingest
            # could only spell-check the TOWN, and "Farooqabad" or "Bhikki" is a locality rather
            # than a district - this branch fell straight past a held point to the town and then
            # to the workbook's administrative assignment. The gas branch below has resolved its
            # points by polygon since rc60; this one never did. Saba Power and QATPL (Bhikki)
            # carried 14.0 Gg of admitted power SO2 at `boundary_scope = district` with an exact
            # coordinate sitting in the row. The polygon returns the same district the workbook
            # stated for both, so nothing moves - what changes is that the placement is now an
            # observation rather than an administrative assignment.
            district = _adm2_of_point(found["latitude"], found["longitude"])
            if district != "unresolved":
                scope = "plant site"
        elif from_gas:
            district = _adm2_of_point(from_gas["latitude"], from_gas["longitude"])
            if district == "unresolved":
                district = _adm2_or_unresolved(from_gas.get("gem_city", "") or r["town"])
            scope = "plant site"
        # rc60: the province gate. A point that puts the station in another province than the
        # one NEPRA prints for it is refused, and the refusal is recorded rather than hidden.
        if district not in ("", "unresolved") and not _point_agrees_with_stated_province(
                district, r["province"]):
            disputed = district
            stated_city = _adm2_or_unresolved(
                (from_gas or {}).get("gem_city", "") or r["town"])
            district = stated_city if stated_city != "unresolved" else ""
            scope = "town"
        if district in ("", "unresolved"):
            district, scope = _adm2_or_unresolved(r["town"]), "town"
        stated = workbook.get(r["plant"]) or workbook.get(
            crosswalk.get(r["plant"], r["plant"]))
        if district == "unresolved" and stated:
            district, scope = stated, "district"
        if scope == "district":
            # the district came from the workbook even where a point exists, because the point
            # placed no district: say which, rather than printing the coordinate's own note
            why = ("located to district by sources/Power Plants/"
                   "power_plants_data_preparation.xlsx#Grid_power_plants, which states a "
                   "district per plant with no per-plant provenance and carries no coordinate; "
                   "an administrative assignment, not an observation%s"
                   % (" (a coordinate is held but falls in no single canonical unit)"
                      if point else ""))
        elif point is from_gas and from_gas is not None:
            why = ("GEM exact location corroborated within %s km (%s); this builder read only "
                   "the grid and coal coordinate tables until rc60"
                   % (from_gas.get("agreement_km", "?"), from_gas.get("corroboration", "")))
        elif found:
            why = "%s; %s" % (found["corroboration"], found["note"])
        else:
            why = "located to town %r; no coordinate source corroborates a point" % r["town"]
        # the disagreement note PREFIXES whatever the ladder said, rather than replacing it:
        # the reader needs both the placement that stands and the coordinate that was refused
        if disputed:
            why = ("THE HELD COORDINATE DISAGREES WITH THE SOURCE: the point falls in %s, in a "
                   "different province from the %s NEPRA SoIR Table 5 prints for this station, "
                   "so the stated location stands and the point is not used for the district. "
                   "%s" % (disputed, r["province"], why))
        add("grid_%s" % _slug(r["plant"]), "power", r["plant"],
            "Electricity and heat production",
            point["latitude"] if point else "", point["longitude"] if point else "",
            "high" if point else "none",
            district,
            "point", "active" if point else "coordinate_unresolved",
            "data/activity/power/plant_locations.csv", r["plant"], why,
            coordinate_source=("WRI Global Power Plant Database / ClimateTRACE power assets"
                               if found else
                               "Global Energy Monitor gas/oil tracker / Climate TRACE power assets"
                               if from_gas else ""),
            coordinate_source_reference=("data/activity/power/plant_coordinates.csv" if found
                                         else "data/activity/power/gas_plant_coordinates.csv"
                                         if from_gas else ""),
            coordinate_quality="high" if point else "official locality only",
            boundary_scope=scope,
            emits="no" if r["station_type"] in NON_EMITTING_STATION_TYPES else "yes")

    # --- ippu (ids grandfathered verbatim; 1 of 34 geocoded via overrides) ----------------
    overrides = {r["facility_id"]: r
                 for r in _read("data/activity/ippu/facility_geocoding_overrides.csv")}
    for r in _read("data/activity/ippu/facilities.csv"):
        o = overrides.get(r["facility_id"])
        lat = (o or {}).get("latitude", "") or r["latitude"]
        lon = (o or {}).get("longitude", "") or r["longitude"]
        has = bool(str(lat).strip())
        add(r["facility_id"], "ippu", r["facility_name"], r["ipcc_code"],
            lat if has else "", lon if has else "",
            ((o or {}).get("coordinate_quality") or "explicit") if has else "none",
            _adm2_or_unresolved(r["district"]), "point",
            "active" if has else "coordinate_unresolved",
            "data/activity/ippu/facilities.csv", r["facility_id"],
            "" if has else "exact coordinate unresolved (registry note)",
            coordinate_source=(o or {}).get("coordinate_source",
                                            "facility source reference"),
            coordinate_source_reference=(o or {}).get("coordinate_source_reference",
                                                      r["source_reference"]),
            coordinate_quality=(o or {}).get("coordinate_quality",
                                             "official locality only"),
            boundary_scope=(o or {}).get("boundary_scope",
                                         "district or named locality"),
            geocode_status=(o or {}).get("geocode_status",
                                         "exact_coordinate_unresolved"),
            technology=r.get("process_route", ""),
            valid_from=r.get("valid_from", ""), valid_to=r.get("valid_to", ""),
            capacity=r.get("capacity", ""),
            capacity_unit=r.get("capacity_unit", ""))

    # --- aviation: airports ---------------------------------------------------------------
    for relative in ("data/activity/aviation/airports.csv",
                     "data/activity/aviation/international_airports.csv"):
        for r in _read(relative):
            icao = r.get("airport_icao") or r.get("icao") or ""
            lat = r.get("latitude_deg") or r.get("latitude") or ""
            lon = r.get("longitude_deg") or r.get("longitude") or ""
            name = r.get("airport") or r.get("name") or icao
            has = bool(str(lat).strip())
            inside = relative.endswith("aviation/airports.csv")
            add("airport_%s" % _slug(icao), "aviation", name, "Domestic aviation",
                lat if has else "", lon if has else "",
                "explicit" if has else "none",
                _adm2_or_unresolved(r.get("district", "")) if inside else "not-applicable",
                "point", "active" if has else "coordinate_unresolved",
                relative, icao,
                "" if inside else "foreign airport, outside the national geometry",
                coordinate_source="airport coordinate table" if has else "",
                coordinate_source_reference=relative if has else "",
                boundary_scope="aerodrome reference point" if has else "")

    # --- railways: yards ------------------------------------------------------------------
    for r in _read("data/gis/rail/yards.csv"):
        add("railyard_%s" % _slug(r["yard"]), "railways", "%s yard" % r["yard"],
            "Railways", r["lat"], r["lon"], "explicit",
            _adm2_or_unresolved(r["yard"]), "point", "active",
            "data/gis/rail/yards.csv", r["yard"],
            coordinate_source="OSM rail network snapshot",
            coordinate_source_reference="data/gis/rail/RAIL_SOURCES.json",
            boundary_scope="yard site")

    # --- fugitives: LNG terminals ---------------------------------------------------------
    for facility_id, name, place in LNG_TERMINALS:
        add(facility_id, "fugitives", name, "Fugitive emissions from oil and gas",
            "", "", "none", adm2.resolve("Malir District"), "point",
            "coordinate_unresolved", "declared", name,
            "at %s; the OGRA station count is the activity, no coordinate source held"
            % place,
            coordinate_quality="named port area only", boundary_scope="port area")

    # --- industry: brick kilns, prospective -----------------------------------------------
    # Ids and district assignments come from the asset table
    # (scripts/build_brick_kiln_assets.py): content-hash ids that survive re-sorting,
    # and the point-in-polygon ADM2 join. Kilns on shared geoBoundaries shapes carry
    # the joined member list; the five outside the simplified boundary stay unresolved.
    for r in _read("data/gis/kilns/pak_brick_kiln_assets.csv"):
        if r["adm2_status"] == "one_to_one":
            adm2_id = r["adm2_ids"]
        elif r["adm2_status"] == "shared_shape":
            adm2_id = r["adm2_ids"]
        else:
            adm2_id = "unresolved"
        add(r["kiln_id"], "industry", "brick kiln (%s)" % r["kiln_type"],
            "Industrial fuel combustion (1A2)", r["latitude"], r["longitude"],
            "explicit", adm2_id, "point", "prospective",
            "data/gis/kilns/pak_brick_kiln_assets.csv",
            "%s|%s" % (r["latitude"], r["longitude"]),
            "detected kiln; no estimated stream references informal brick "
            "manufacture yet - the industrial-solids category will need these points",
            coordinate_source="Hamdani et al. 2025 detection dataset",
            coordinate_source_reference="data/gis/kilns/BRICK_KILN_SOURCES.json",
            boundary_scope="kiln site")

    # --- waste: landfill polygons, prospective -------------------------------------------
    # The OSM disposal-site seed (scripts/build_landfill_assets.py): 56 polygons, 13
    # named, quality-flagged. Registered so the release can cite what it holds; far
    # too sparse for an SWDS allocation, and the discipline test keeps every
    # prospective set untouched by streams.
    for r in _read("data/gis/landfills/pak_landfill_assets.csv"):
        add(r["landfill_id"], "waste",
            r["name"] or "unnamed landfill polygon (%s)" % r["quality"],
            "Solid waste disposal (4A)", r["latitude"], r["longitude"],
            "explicit", r["adm2_ids"] or "unresolved", "polygon-centroid",
            "prospective",
            "data/gis/landfills/pak_landfill_assets.csv", r["landfill_id"],
            "OSM landuse=landfill; quality=%s, area %s m2; a release-geometry seed - "
            "no estimated stream references disposal sites" % (r["quality"],
                                                               r["area_m2"]),
            coordinate_source="OpenStreetMap snapshot 2026-08-06 (landfill polygon "
                              "centroid)",
            coordinate_source_reference="data/gis/landfills/LANDFILL_SOURCES.json",
            boundary_scope="disposal site polygon")

    return rows


def render(rows):
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=list(FIELDS), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def main(check=False):
    rows = build()
    ids = [r["facility_id"] for r in rows]
    assert len(ids) == len(set(ids)), "duplicate facility ids"
    for r in rows:
        if r["latitude"]:
            lon, lat = float(r["longitude"]), float(r["latitude"])
            assert BBOX[0] <= lon <= BBOX[2] and BBOX[1] <= lat <= BBOX[3] \
                or r["adm2_id"] == "not-applicable", \
                "%s outside Pakistan bbox" % r["facility_id"]
    text = render(rows)
    if check:
        if not os.path.exists(OUT) or open(OUT, encoding="utf-8").read() != text:
            print("data/facility_registry.csv is stale; run "
                  "python3 scripts/build_facility_registry.py")
            return 1
        print("facility registry is current.")
        return 0
    open(OUT, "w", encoding="utf-8").write(text)
    import collections
    by = collections.Counter((r["module"], r["status"]) for r in rows)
    print("wrote data/facility_registry.csv: %d facilities" % len(rows))
    for (module, status), n in sorted(by.items()):
        print("  %-10s %-22s %d" % (module, status, n))
    return 0


if __name__ == "__main__":
    from pkinv.activity.store import staging_inputs
    with staging_inputs():
        raise SystemExit(main(check="--check" in sys.argv))
