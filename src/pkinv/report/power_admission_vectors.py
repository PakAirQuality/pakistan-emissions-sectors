"""The spatial frames the admitted power SO2 rides (rc61).

WHY THIS EXISTS. rc60 admitted oil- and diesel-fired main-activity power SO2 to the nine-year air
panel from data/activity/power/power_so2_admission.csv, and then could not place it. The air sink
multiplies a class's mass onto ITS ANCHOR greenhouse-gas stream's vectors, and here the anchor -
`power|electricity-and-heat-production|furnace-oil-co2|co2` - describes the WHOLE CPPA furnace-oil
fleet, while the admitted mass is the 54-89 percent of that fuel the register could price, station
by station. Riding the whole fleet's pattern is not an allocation of this mass; it is a
reconstruction with a measured bias, and the bias was measured: Lahore came out 1.3 to 2.2 times
the register's own figure in every period, and 7 Gg landed in Quetta, which has no furnace-oil
station at all. So the mass was typed `below_national` - published at national grain and placed
nowhere - which was honest and useless.

The register has known where the mass is the whole time: a reviewed `adm2_id` on all 144 admitted
rows, audited in the same pass that found four stations in the wrong district. This module turns
that into the three things the sink needs.

WHAT IS DIFFERENT ABOUT THESE FRAMES. The kiln frames (kiln_frame_vectors.py) redistribute WITHIN
a province and assert their province marginal equals the anchor stream's to 1e-9. These cannot: the
admitted subset's provinces genuinely differ from the whole fleet's - Balochistan is 43.5 percent
of the admitted mass at FY2015-16 against a fleet vector that barely carries it - because the two
describe DIFFERENT POPULATIONS, not the same population two ways. So a frame here declares its own
province marginal, `inherits_anchor_marginal` is False, and the sink takes ADM1 from the frame.
That is the one architectural amendment this round makes, and it is narrow: a frame either inherits
its anchor's provinces or declares its own, and ADM1 comes from whichever vector carried the mass.

PER PERIOD, NECESSARILY. The province split moves from Balochistan 0.435 / Punjab 0.565 at
FY2015-16 to Punjab 1.000 at FY2023-24, as the furnace-oil fleet collapsed. One vector for nine
years would misplace up to 43.5 points of the split. There are 29 frames: one per (class, period)
that carries mass.

HOW EACH STATION IS PLACED, and the grades are not interchangeable:

  point            19 of 21 stations, 78.40 percent of the mass. The held coordinate's own
                   point-in-polygon district is EXACTLY the district the register reviewed, so
                   the raster cell and the ADM2 row agree with no judgement in between.
  snapped          Hub Power alone, 129.40 Gg and 21.59 percent. Its coordinate falls 818 m
                   outside the Lasbela polygon, in Karachi. rc60's province gate refused that
                   point for the district because it contradicts both NEPRA SoIR Table 5 ("Hub,
                   Balochistan") and GEM ("Las Bela"); 818 m is 0.15 of a 0.05-degree cell, so
                   this is a boundary-precision disagreement and not a wrong coordinate. The mass
                   goes to the nearest cell inside the reviewed district and THE DISPLACEMENT IS
                   PUBLISHED, per station, in the output this module writes.
  district         Halmore Power alone, 0.019 Gg and 0.003 percent. No coordinate is held in any
                   of the three tables; the mass spreads over its district's own cells. Climate
                   TRACE carries a candidate point for it (31.6335, 73.8704, consistent with
                   Bhikki) and GEM carries one that is internally contradictory - its coordinate
                   lands near Quetta while its own city field says Sheikhupura. Neither has been
                   reviewed, so neither is used.

THE DISTRICT VECTOR IS THE REGISTER'S, NOT THE RASTER'S. `shape_vec` is built from the reviewed
`adm2_id` directly rather than by projecting the cells, because the cell is the neighbourhood and
the register is the answer - the same reasoning grid_cube.PointProjection gives for keeping a
point's district off its cell's area split, applied one step further back.

Usage:  python3 -m pkinv.report.power_admission_vectors
Reads:  data/activity/power/power_so2_admission.csv, data/facility_registry.csv,
        data/adm2_canonical.csv
Writes: outputs/pakemis_power_admission_adm2_by_class.csv
"""

from pkinv.assets import asset_path
import csv
import os
from collections import defaultdict

import numpy as np

from pkinv.activity.store import read_rows
from pkinv.paths import DATA, OUTPUTS

REGISTER = asset_path(DATA, "activity", "power", "power_so2_admission.csv")
REGISTRY = asset_path(DATA, "facility_registry.csv")
OUT = asset_path(OUTPUTS, "pakemis_power_admission_adm2_by_class.csv")

# (fuel, equipment_class) -> the source_class_id in data/air_source_classes.csv, and the suffix
# its spatial_override carries. FOUR DISTINCT FRAME IDS ARE LOAD-BEARING: the sink groups atoms
# by (configuration, anchor, frame) and drops the class id, so a shared frame string would merge
# the boiler and engine classes under one anchor; and `spatial_frame` is part of the support
# ledger's declared primary key (data/product_schemas.csv).
CLASS_OF = {
    ("RFO", "oil_fired_boiler"): ("power_rfo_boiler", "rfo_boiler"),
    ("RFO", "reciprocating_engine"): ("power_rfo_engine", "rfo_engine"),
    ("RFO", "gas_turbine"): ("power_rfo_turbine", "rfo_turbine"),
    ("HSD", "gas_turbine"): ("power_hsd_turbine", "hsd_turbine"),
}
FRAME_PREFIX = "power_admission:"
FIELDS = ("class_id", "period_id", "shape_id", "adm2_ids", "province", "share",
          "stations", "placement", "max_displacement_km", "note")


def frame_id(class_id):
    return FRAME_PREFIX + CLASS_OF_BY_ID[class_id]


CLASS_OF_BY_ID = {cid: suffix for (cid, suffix) in CLASS_OF.values()}


class Frame:
    """One (class, period) placement, in the shape the air sink consumes.

    `cells` (h, w) sums to 1; `shape_vec` is per grid district index and sums with `outside` to
    1; `province_marginal` is keyed by the five province names and sums to 1. Unlike the kiln
    frames, `inherits_anchor_marginal` is False: the sink must take ADM1 from `province_marginal`
    rather than from the anchor stream's.
    """

    inherits_anchor_marginal = False

    def __init__(self, class_id, period_id, cells, shape_vec, outside, province_marginal,
                 placements):
        self.class_id = class_id
        self.period_id = period_id
        self.cells = cells
        self.shape_vec = shape_vec
        self.outside = outside
        self.province_marginal = province_marginal
        self.placements = placements          # [{plant, basis, displacement_km, adm2_id, share}]
        from pkinv.report.grid_cube import pattern_hash
        self.pattern_hash = pattern_hash(cells)

    @property
    def notes(self):
        kinds = defaultdict(float)
        for p in self.placements:
            kinds[p["basis"]] += p["share"]
        return ["%s %.4f" % (k, v) for k, v in sorted(kinds.items())]

    def district_grade_share(self):
        """The share placed no finer than a district - what the support ledger must declare."""
        return sum(p["share"] for p in self.placements if p["basis"] == "district")


def district_index(grid):
    """{adm2_id: grid district index}, through the sink's own canonical shape frame."""
    from pkinv.report.air_spatial_by_year import shape_frame
    out = {}
    for idx, _shape_id, adm2_ids, _status, _province in shape_frame(grid):
        for adm2_id in adm2_ids.split(";"):
            out[adm2_id] = idx
    return out


def province_of_adm2():
    return {r["adm2_id"]: (r["province_id"] or r["adm1_name"])
            for r in read_rows(asset_path(DATA, "adm2_canonical.csv"))}


def held_points():
    """{plant: (lon, lat)} for the admitted fleet, from the reviewed facility registry."""
    out = {}
    from pkinv.core.primary_geography import compatible_facilities
    for r in compatible_facilities(read_rows(REGISTRY)):
        if r["module"] != "power" or not r["latitude"].strip():
            continue
        out.setdefault(r["name"], (float(r["longitude"]), float(r["latitude"])))
    return out


def admitted():
    """{(class_id, period_id): {plant: (so2_Gg, adm2_id)}} from the reviewed register."""
    out = defaultdict(lambda: defaultdict(lambda: [0.0, ""]))
    for r in read_rows(REGISTER):
        if r["disposition"] != "provisional_estimate":
            continue
        key = CLASS_OF.get((r["fuel"], r["equipment_class"]))
        if key is None:
            raise ValueError("%s %s: no air source class for (%s, %s)"
                             % (r["plant"], r["period_id"], r["fuel"], r["equipment_class"]))
        cell = out[(key[0], r["period_id"])][r["plant"]]
        cell[0] += float(r["so2_Gg"])
        cell[1] = r["adm2_id"]
    return out


def _cell_centres(grid):
    """(lons, lats) of every cell centre, as (h, w) arrays - cached on the grid object."""
    cached = getattr(grid, "_admission_centres", None)
    if cached is not None:
        return cached
    rows = np.arange(grid.height) + 0.5
    cols = np.arange(grid.width) + 0.5
    col_grid, row_grid = np.meshgrid(cols, rows)
    lons, lats = grid.transform * (col_grid, row_grid)
    grid._admission_centres = (np.asarray(lons), np.asarray(lats))
    return grid._admission_centres


def place(grid, lon, lat, idx, indices):
    """((row, col) mask, basis, displacement_km) for one station.

    Three grades, and the caller publishes which. A point whose own polygon is the reviewed
    district is used as it stands. A point that falls outside it goes to the NEAREST cell inside
    it, with the distance reported - never silently. A station with no point spreads over the
    district's cells, which claims only what the register claims.
    """
    mask = grid.district_id == idx
    if not mask.any():
        raise ValueError("district index %d rasterises to no cell" % idx)
    if lon is None:
        return mask / float(mask.sum()), "district", 0.0

    inverse = ~grid.transform
    column, row = inverse * (lon, lat)
    row, column = int(row), int(column)
    inside = (0 <= row < grid.height and 0 <= column < grid.width)
    if inside and indices.get((lon, lat)) == idx:
        out = np.zeros((grid.height, grid.width), dtype=np.float64)
        out[row, column] = 1.0
        return out, "point", 0.0

    # snap: nearest cell centre inside the reviewed district, by great-circle-ish metres
    lons, lats = _cell_centres(grid)
    dx = (lons - lon) * 111.32 * np.cos(np.radians(lat))
    dy = (lats - lat) * 110.57
    distance = np.hypot(dx, dy)
    distance = np.where(mask, distance, np.inf)
    flat = int(np.argmin(distance))
    r, c = divmod(flat, grid.width)
    out = np.zeros((grid.height, grid.width), dtype=np.float64)
    out[r, c] = 1.0
    return out, "snapped", float(distance[r, c])


def build(grid):
    """{(class_id, period_id): Frame} for every admitted class and period that carries mass."""
    from pkinv.core.gis.grid import district_index_at

    by_key = admitted()
    points = held_points()
    idx_of = district_index(grid)
    province_of = province_of_adm2()

    wanted = sorted({p for plants in by_key.values() for p in plants})
    coords = [points[p] for p in wanted if p in points]
    resolved = district_index_at(coords) if coords else []
    indices = dict(zip(coords, resolved))

    out = {}
    for (class_id, period_id), plants in sorted(by_key.items()):
        total = sum(v[0] for v in plants.values())
        if total <= 0:
            continue
        cells = np.zeros((grid.height, grid.width), dtype=np.float64)
        shape_sums, marginal, placements = defaultdict(float), defaultdict(float), []
        for plant, (mass, adm2_id) in sorted(plants.items()):
            share = mass / total
            idx = idx_of.get(adm2_id)
            if idx is None:
                raise ValueError("%s: district %r is in no canonical shape" % (plant, adm2_id))
            lon, lat = points.get(plant, (None, None))
            block, basis, displacement = place(grid, lon, lat, idx, indices)
            cells += block * share
            shape_sums[idx] += share
            marginal[province_of[adm2_id]] += share
            placements.append({"plant": plant, "basis": basis, "adm2_id": adm2_id,
                               "displacement_km": displacement, "share": share})

        divisor = float(cells.sum())
        if abs(divisor - 1.0) > 1e-9:
            raise AssertionError("%s %s: cells sum to %.12f, not 1"
                                 % (class_id, period_id, divisor))
        shape_vec = np.array([shape_sums.get(i, 0.0) for i in range(len(grid.districts))])
        outside = 0.0          # every admitted district resolves to a canonical shape
        if abs(float(shape_vec.sum()) + outside - 1.0) > 1e-9:
            raise AssertionError("%s %s: shape vector does not close: %.12f"
                                 % (class_id, period_id, float(shape_vec.sum())))
        if abs(sum(marginal.values()) - 1.0) > 1e-9:
            raise AssertionError("%s %s: province marginal does not close: %.12f"
                                 % (class_id, period_id, sum(marginal.values())))
        out[(class_id, period_id)] = Frame(class_id, period_id, cells, shape_vec, outside,
                                           dict(marginal), placements)
    return out


def rows(frames, grid):
    from pkinv.report.air_spatial_by_year import shape_frame
    frame_rows = shape_frame(grid)
    out = []
    for (class_id, period_id), f in sorted(frames.items()):
        by_idx = defaultdict(list)
        for p in f.placements:
            by_idx[p["adm2_id"]].append(p)
        idx_of = district_index(grid)
        for idx, shape_id, adm2_ids, _status, province in frame_rows:
            share = float(f.shape_vec[idx])
            if share == 0.0:
                continue
            here = [p for p in f.placements if idx_of[p["adm2_id"]] == idx]
            bases = sorted({p["basis"] for p in here})
            worst = max((p["displacement_km"] for p in here), default=0.0)
            out.append({
                "class_id": class_id, "period_id": period_id, "shape_id": shape_id,
                "adm2_ids": adm2_ids, "province": province, "share": "%.12g" % share,
                "stations": ";".join(sorted(p["plant"] for p in here)),
                "placement": ";".join(bases),
                "max_displacement_km": "%.3f" % worst,
                "note": ("the reviewed district of every station in this shape "
                         "(data/activity/power/power_so2_admission.csv); the raster cell is "
                         "the station's own point where its polygon agrees, the nearest cell "
                         "inside the reviewed district where it does not, and the district's "
                         "own cells where no coordinate is held"),
            })
    return out


def main():
    from pkinv.core.gis.grid import build_grid
    grid = build_grid()
    frames = build(grid)
    with open(OUT, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(FIELDS), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows(frames, grid))
    snapped = {}
    for f in frames.values():
        for p in f.placements:
            if p["basis"] != "point":
                snapped.setdefault((p["plant"], p["basis"]), p["displacement_km"])
    print("%d frames over %d classes" % (len(frames), len({k[0] for k in frames})))
    for (plant, basis), km in sorted(snapped.items()):
        print("   %-16s %-9s displacement %.3f km" % (plant, basis, km))
    print("power admission vectors -> %s" % os.path.relpath(OUT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
