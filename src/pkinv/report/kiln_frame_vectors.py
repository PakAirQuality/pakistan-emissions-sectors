"""The brick-kiln frame by KILN TYPE: the spatial vectors the industrial air layer's brick classes
ride (rc59).

WHY. The brick-coal greenhouse-gas stream places its mass on the 11,272 surveyed kilns as one
object-uniform pattern. The air layer prices that coal in three classes - fixed-chimney Bull's
trench kilns (FCBK), zig-zag kilns (ZZ), and the coal HDIP books outside the surveyed frame -
because the two kiln types differ by a factor of two or more on particulate and the remainder has
no kiln to stand on. Through rc58 all three inherited the pooled vector; the district pattern was
right for the sum and wrong for the parts. This module builds, ONCE (the brick provincial shares
are period-invariant: industry/downscale.load_shares ignores the period), the FCBK and ZZ vectors
the same way the cube builds the pooled one - points burned into the grid per province at the
province's declared share, an exact point-in-polygon district vector beside the raster
(grid_cube.PointProjection), and the nested shape marginal (cube_core.shape_marginals) - so each
type's province marginal equals the stream's share vector by construction and ADM1 does not move.

A province with a brick share and no kiln of one type keeps that type on the province's POOLED
kilns (both types), declared in Frame.notes - the pattern is still the kiln frame, not built-up.
The remainder has no vector here: the sink places it at ADM1 and types the rest unallocated.

Usage:  python3 -m pkinv.report.kiln_frame_vectors
Reads:  data/ml/brick_kilns_pk.csv (lat, lon, type), data/province_shares.csv (brick_coal)
Writes: outputs/pakemis_kiln_frame_adm2_by_type.csv (kiln_type x shape: the exact district share)
"""

from pkinv.assets import asset_path
import csv
import os
from collections import defaultdict

import numpy as np

from pkinv.core.geography import PROVINCES
from pkinv.core.gis import cube as cube_core
from pkinv.activity.store import read_rows
from pkinv.paths import DATA, OUTPUTS

KILNS = asset_path(DATA, "ml", "brick_kilns_pk.csv")
OUT = asset_path(OUTPUTS, "pakemis_kiln_frame_adm2_by_type.csv")
TYPES = ("FCBK", "ZZ")
STREAM_PROXY = "brick_coal"
FIELDS = ("kiln_type", "shape_id", "adm2_ids", "province", "share", "kilns", "note")


class Frame:
    """One kiln type's placement: `cells` (h, w) sums to 1; `shape_vec` per district index
    (the cube's district order, -1 = outside) sums with `outside` to 1; `province_marginal`
    is the raster's own province marginal (equals the brick shares); `pattern_hash`."""

    # rc61: these frames INHERIT their anchor stream's provinces. That was always true and was
    # asserted in the sink; it is now said here, because a second kind of frame exists that does
    # not (pkinv.report.power_admission_vectors, whose mass is a reviewed subset of its anchor's
    # fleet rather than the same mass split differently). The sink reads this attribute to decide
    # whether the equality is an invariant to enforce or a difference to respect.
    inherits_anchor_marginal = True

    def __init__(self, kiln_type, cells, shape_vec, outside, province_marginal, counts, notes):
        self.kiln_type = kiln_type
        self.cells = cells
        self.shape_vec = shape_vec
        self.outside = outside
        self.province_marginal = province_marginal
        self.counts = counts
        self.notes = notes
        from pkinv.report.grid_cube import pattern_hash
        self.pattern_hash = pattern_hash(cells)


def _points_by_province(grid):
    """{type: {province: [(lon, lat, 1.0)]}} plus {province: pooled}, pooled by the province each
    kiln's CELL rasterises into - coordinates outrank labels (the grid-fleet rule)."""
    inv = ~grid.transform
    by_type = {t: defaultdict(list) for t in TYPES}
    pooled = defaultdict(list)
    for row in read_rows(KILNS):
        lon, lat = float(row["lon"]), float(row["lat"])
        col, row_i = inv * (lon, lat)
        row_i, col = int(row_i), int(col)
        if not (0 <= row_i < grid.height and 0 <= col < grid.width):
            continue
        pid = int(grid.province_id[row_i, col])
        if not (0 <= pid < len(PROVINCES)):
            continue
        if row["type"] not in by_type:
            raise ValueError("kiln type %r is neither FCBK nor ZZ" % row["type"])
        by_type[row["type"]][PROVINCES[pid]].append((lon, lat, 1.0))
        pooled[PROVINCES[pid]].append((lon, lat, 1.0))
    return by_type, pooled


def brick_shares():
    from pkinv.sectors.industry.downscale import load_shares
    return load_shares()[STREAM_PROXY]


def build(grid):
    """{kiln_type: Frame} on the cube's own grid."""
    from pkinv.report.grid_cube import PointProjection
    shares = brick_shares()
    by_type, pooled = _points_by_province(grid)
    shape_province = cube_core.canonical_shape_province(grid)
    inv = ~grid.transform
    out = {}
    for kiln_type in TYPES:
        weight = np.zeros((grid.height, grid.width), dtype=np.float64)
        projection = PointProjection(grid)
        notes, counts = [], {}
        for province, share in shares.items():
            if share <= 0:
                continue
            points = by_type[kiln_type].get(province)
            if not points:
                points = pooled.get(province)
                if not points:
                    raise ValueError("%s: province %s carries a brick share and no surveyed kiln at "
                                     "all - the pooled stream would have fallen back to built-up, "
                                     "which this frame refuses" % (kiln_type, province))
                notes.append("%s: no %s kiln surveyed; the province's %d pooled kilns carry its share"
                             % (province, kiln_type, len(points)))
            arr = np.zeros_like(weight)
            for lon, lat, w in points:
                col, row_i = inv * (lon, lat)
                arr[int(row_i), int(col)] += w
            total = float(arr.sum())
            weight += arr * (share / total)
            projection.add_points(points, share, province)
            counts[province] = len(points)
        divisor = float(weight.sum())
        cells = weight / divisor
        projection.finish(divisor)
        shape_sums = cube_core.shape_marginals(grid, projection.fallback, shape_province)
        for index, value in projection.vector.items():
            shape_sums[index] = shape_sums.get(index, 0.0) + value
        shape_vec = np.array([shape_sums.get(i, 0.0) for i in range(len(grid.districts))])
        outside = float(shape_sums.get(-1, 0.0))
        marginal = cube_core.province_marginals(grid, cells)
        for province, share in shares.items():
            if abs(marginal.get(province, 0.0) - share) > 1e-9:
                raise AssertionError("%s frame's %s marginal %.12f != declared share %.12f"
                                     % (kiln_type, province, marginal.get(province, 0.0), share))
        if abs(float(shape_vec.sum()) + outside - 1.0) > 1e-9:
            raise AssertionError("%s frame's shape vector does not close: %.12f + %.12f"
                                 % (kiln_type, float(shape_vec.sum()), outside))
        out[kiln_type] = Frame(kiln_type, cells, shape_vec, outside, marginal, counts, notes)
    return out


def rows(frames, grid):
    from pkinv.report.air_spatial_by_year import shape_frame
    frame_rows = shape_frame(grid)
    out = []
    for kiln_type, f in frames.items():
        for idx, shape_id, adm2_ids, _status, province in frame_rows:
            share = float(f.shape_vec[idx])
            if share == 0.0:
                continue
            out.append({"kiln_type": kiln_type, "shape_id": shape_id, "adm2_ids": adm2_ids,
                        "province": province, "share": "%.12g" % share,
                        "kilns": "", "note": "; ".join(f.notes)})
        out.append({"kiln_type": kiln_type, "shape_id": "OUTSIDE", "adm2_ids": "",
                    "province": "", "share": "%.12g" % f.outside, "kilns": "",
                    "note": "off-polygon remainder of the frame's raster, carried so the closure is exact"})
    return out


def main():
    from pkinv.core.gis.grid import build_grid
    grid = build_grid()
    frames = build(grid)
    with open(OUT, "w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=list(FIELDS), lineterminator="\n")
        w.writeheader()
        w.writerows(rows(frames, grid))
    for t, f in frames.items():
        print("kiln frame %-4s hash %s  kilns %s  outside %.6f  notes: %s"
              % (t, f.pattern_hash, sum(f.counts.values()), f.outside, "; ".join(f.notes) or "none"))
    print("kiln frame vectors -> %s" % os.path.relpath(OUT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
