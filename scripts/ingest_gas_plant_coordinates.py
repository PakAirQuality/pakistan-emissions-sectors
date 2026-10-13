#!/usr/bin/env python3
"""Coordinates for the gas, RFO and bagasse grid fleet, from GEM's GOGPT/GBPT (rc46 Wave 1).

WHY. After rc42 located the coal fleet, grid gas still placed half its mass on the built-up
raster (substituted_share 0.50) and RFO a third, because 25 of the crosswalk's canonical
stations - 245 TWh of nine-year generation - had no coordinate row. The Global Oil and Gas
Plant Tracker holds 46 Pakistani plants (82 of 88 unit rows located `exact`) and the Global
Bioenergy Power Tracker the sugar-mill sellers; both arrived through the same registered
CC-BY flow as the coal tracker (scripts/fetch_gem_trackers.py).

THE JOIN IS EXPLICIT, NOT TOKENISED - the same refusal as the coal ingest. ALIASES maps each
canonical station to its GEM plant name by hand; the one trap worth naming is at Bhikki,
where "Halmore power station" and "Bhikki power station" (QATPL) are DIFFERENT stations in
one town. Two gates before a row is written: GEM accuracy must be `exact`, and the point
must land in the province the locations register declares (the grid's own province raster
decides). Climate TRACE corroboration is recorded WHERE a compatible asset sits within
AGREEMENT_KM, and its absence is a recorded tier, not a failure - TRACE's gas fleet is
thinner than its coal fleet, and refusing every uncorroborated exact point would keep half
the fleet on a raster to honour a corroborator that never covered it.

STATIONS THE TRACKERS DO NOT HOLD stay substituted, each with a typed reason in SKIPPED -
printed at every run so the residual is a visible decision, not a silent gap.

Deterministic; --check re-derives and diffs (write_or_check discipline).

Usage:  python3 scripts/ingest_gas_plant_coordinates.py [--check]
Writes: data/activity/power/gas_plant_coordinates.csv
"""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from pkinv.assets import asset_path

from pkinv.core.io import read_rows, write_or_check  # noqa: E402
from pkinv.paths import DATA  # noqa: E402

GOGPT = asset_path(DATA, "activity", "power", "gem_gas_oil_pak.csv")
GBPT = asset_path(DATA, "activity", "power", "gem_bioenergy_pak.csv")
TRACE = asset_path(DATA, "activity", "power", "climatetrace_power_assets_pak.csv")
LOCATIONS = asset_path(DATA, "activity", "power", "plant_locations.csv")
OUT = asset_path(DATA, "activity", "power", "gas_plant_coordinates.csv")
FIELDS = ("plant", "latitude", "longitude", "gem_plant", "gem_tracker", "gem_accuracy",
          "gem_city", "corroboration", "agreement_km", "province", "note")
AGREEMENT_KM = 5.0

# canonical station (locations-register name) -> (tracker, GEM plant/project name)
ALIASES = {
    "NPPMCL (HBS)": ("gogpt", "Haveli Bahadur Shah (HBS) power station"),
    "KAPCO": ("gogpt", "KAPCO power station"),
    "TPS Guddu (Units 5-10)": ("gogpt", "Guddu power station"),
    "TPS Guddu (Units 14-16)": ("gogpt", "Guddu power station"),
    "Hub Power": ("gogpt", "Hub power plant"),
    "TPS Nandipur": ("gogpt", "Nandipur power station"),
    "Rousch Power": ("gogpt", "Rousch power station"),
    "Engro Power Gen. Qadirpur": ("gogpt", "Engro power station"),
    "Lal Pir Power": ("gogpt", "Lalpir Power Limited power station"),
    "Pak Gen. Power": ("gogpt", "Pakgen Power Limited power plant"),
    "Orient Power": ("gogpt", "Orient power station"),
    "Sapphire Electric": ("gogpt", "Sapphire Electric power station"),
    "Attock Gen.": ("gogpt", "Attock Gen Limited power station (AGL)"),
    "Tapal Energy": ("gogpt", "Tapal Energy Power Project power plant"),
    "Punjab Thermal Power": ("gogpt", "Trimmu power station"),
    "GTPS Faisalabad": ("gogpt", "GTPS Faisalabad power station"),
    "RYK Mills": ("gbpt", "RYK Sugar Mill power station"),
}

SKIPPED = {
    "TPS Quetta": "not in GOGPT's Pakistani rows; 165 GWh over nine years stays on builtup",
    "Davis Energen.": "not in GOGPT's Pakistani rows; 146 GWh",
    "Altern Energy": "not in GOGPT's Pakistani rows; 546 GWh (Fateh Jang gas)",
    "Fatima Energy": "not in GBPT's Pakistani rows; 832 GWh (Muzaffargarh biomass/coal)",
    "Jamal Din Wali-II": "GBPT holds ONE JDW project, at 28.0476/69.3213 in Ghotki, Sindh; "
                         "the unit-II site at Jamal Din Wali (Rahim Yar Khan) is not "
                         "separately located - 1,899 GWh stays substituted",
    "Jamal Din Wali-III": "a THREE-WAY IDENTITY CONFLICT, unresolved rather than adjudicated: "
                          "the SIR locations register places unit-III in Rahim Yar Khan "
                          "(Punjab), the PBS panel spelling reads '(Unit-III) Ghotki' (Sindh), "
                          "and GEM's exact point is in Ghotki. Two held sources against the "
                          "register is not a majority vote - the register is this file's "
                          "declared authority, so the 1,111 GWh stays substituted until a "
                          "register correction is argued on its own evidence",
    "Halmore Power": "SOURCE DEFECT in GOGPT August 2026: the 'Halmore power station' row "
                     "carries City=Sheikhupura (correct) but an exact-tagged coordinate "
                     "1.1 km from Habibullah Coastal, Quetta - the Bhikki plant printed on "
                     "the Quetta plant's site, 700 km away. Caught by the province gate; "
                     "4,944 GWh stays substituted rather than adopting a wrong point. The "
                     "neighbouring 'Bhikki power station' point is QATPL, a DIFFERENT "
                     "station, and is not borrowed",
    "SNPCL-I (IPP-2002)": "GOGPT's Nooriabad rows are location accuracy `approximate`, and "
                          "this file's contract is exact-only - 2,651 GWh stays substituted "
                          "rather than accepting a town-level point as if it were exact",
}

TOWN_NOTES = {}


def haversine_km(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 2 * 6371.0088 * math.asin(math.sqrt(h))


def _gem_plants(path, name_key, accuracy_key):
    out = {}
    for r in read_rows(path, comments=False):
        # A nine-year panel legitimately includes stations that have since mothballed or
        # retired (GTPS Faisalabad generated through the PBS years and is mothballed in
        # GEM's August 2026 edition). The location is what is taken here, not the status.
        if r.get("Status", "").strip().lower() not in ("operating", "mothballed", "retired"):
            continue
        if r.get(accuracy_key, "").strip().lower() != "exact":
            continue
        out.setdefault(r[name_key], r)               # units share the plant's location
    return out


def build():
    from pkinv.core.geography import PROVINCES
    from pkinv.core.gis.grid import build_grid
    grid = build_grid()
    locations = {r["plant"]: r for r in read_rows(LOCATIONS, comments=False)}
    gogpt = _gem_plants(GOGPT, "Plant name", "Location accuracy")
    gbpt = _gem_plants(GBPT, "Project Name", "Location Accuracy")
    trace = [r for r in read_rows(TRACE)
             if any(k in r.get("asset_type", "") for k in ("gas", "oil", "biomass"))]
    rows = []
    for plant in sorted(ALIASES):
        tracker, gem_name = ALIASES[plant]
        book = gogpt if tracker == "gogpt" else gbpt
        g = book.get(gem_name)
        if g is None:
            raise SystemExit("%s -> %r: not an operating, exactly located %s plant"
                             % (plant, gem_name, tracker.upper()))
        lat, lon = float(g["Latitude"]), float(g["Longitude"])
        col, row_i = (~grid.transform) * (lon, lat)
        row_i, col = int(row_i), int(col)
        pid = int(grid.province_id[row_i, col]) if (0 <= row_i < grid.height and 0 <= col < grid.width) else -1
        if not (0 <= pid < len(PROVINCES)):
            raise SystemExit("%s: (%.5f, %.5f) lands outside every province" % (plant, lat, lon))
        province = PROVINCES[pid]
        declared = locations.get(plant, {}).get("province", "")
        boundary_note = ""
        if declared and declared != province:
            # THE GATE CATCHES WRONG COORDINATES, NOT BOUNDARY CELLS. At 0.05 degrees a
            # station on a provincial boundary can land in the neighbouring cell - Attock
            # Gen sits at Morgah, Rawalpindi, and its cell is ICT-classified ("Other")
            # while the cell one step west is Punjab. Accept when the DECLARED province
            # appears in the 3x3 neighbourhood, and say so on the row; a genuinely
            # misplaced point (wrong city, wrong district) still fails, because its
            # declared province is nowhere near it.
            neighbours = set()
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    rr, cc = row_i + dr, col + dc
                    if 0 <= rr < grid.height and 0 <= cc < grid.width:
                        npid = int(grid.province_id[rr, cc])
                        if 0 <= npid < len(PROVINCES):
                            neighbours.add(PROVINCES[npid])
            if declared not in neighbours:
                raise SystemExit("%s: GEM point is in %s (neighbourhood %s) but the "
                                 "locations register says %s"
                                 % (plant, province, sorted(neighbours), declared))
            boundary_note = ("boundary cell: the point's 0.05 degree cell is %s-classified; "
                             "the declared province %s adjoins it" % (province, declared))
            province = declared
        nearest = None
        for t in trace:
            km = haversine_km((lat, lon), (float(t["lat"]), float(t["lon"])))
            if nearest is None or km < nearest[0]:
                nearest = (km, t["name"])
        if nearest and nearest[0] <= AGREEMENT_KM:
            corrob, km_s = "gem_exact+trace(%s)" % nearest[1], "%.2f" % nearest[0]
        else:
            corrob, km_s = "gem_exact", ""
        note = TOWN_NOTES.get(plant, "")
        if plant.startswith("TPS Guddu"):
            note = "both Guddu unit groups share the one GEM site"
        if boundary_note:
            note = (note + "; " if note else "") + boundary_note
        city = (g.get("City") or "").strip()
        rows.append({"plant": plant, "latitude": "%.6f" % lat, "longitude": "%.6f" % lon,
                     "gem_plant": gem_name, "gem_tracker": tracker.upper(),
                     "gem_accuracy": "exact", "gem_city": city,
                     "corroboration": corrob, "agreement_km": km_s,
                     "province": province, "note": note})
    return rows


def main(check=False):
    rows = build()
    corroborated = sum(1 for r in rows if r["corroboration"].startswith("gem_exact+"))
    banner = [
        "GAS, RFO AND BAGASSE GRID STATION COORDINATES (rc46 Wave 1): %d canonical stations" % len(rows),
        "located by GEM's GOGPT/GBPT (accuracy exact, operating), %d with a Climate TRACE" % corroborated,
        "asset within %.0f km recorded as corroboration; province-gated against the grid's own" % AGREEMENT_KM,
        "raster. The canonical -> GEM name map is explicit in",
        "scripts/ingest_gas_plant_coordinates.py (no token join); stations the trackers do",
        "not hold are typed in SKIPPED there and stay substituted.",
    ]
    for plant, why in sorted(SKIPPED.items()):
        print("  SKIPPED %-24s %s" % (plant, why))
    return write_or_check(OUT, list(FIELDS), rows, check=check, banner=banner, lineterminator="\n")


if __name__ == "__main__":
    raise SystemExit(main(check="--check" in sys.argv))
