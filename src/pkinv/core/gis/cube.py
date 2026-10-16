"""The cube's weight engine: one normalised surface per source stream.

THE CONTRACT (the reviewer's Stage 6, section 6.7): for stream s, month m, gas g, cell i,

    E(s, m, g, i) = E(s, g) x p(s, m) x w(s, i),   sum_m p = 1,   sum_i w = 1.

This module builds w. E comes from the source-stream ledger and p from the monthly layer -
both read, never recomputed. w is month-invariant, declared: no stream in this release has
evidence that its GEOGRAPHY moves with the season (the monthly shape is p's job), and
asserting otherwise would manufacture precision.

NATIVE GEOMETRY FIRST. A stream's weight is built from the most native geography its
evidence supports, in this order: registered facility points with activity weights (captive
plants, airports), a network surface (railways), district panels through the canonical ADM2
package, and only then province-share x raster proxy. Where geometry is claimed but
coordinates are not held (power grid towns, LNG terminals), the surface is the declared
proxy - no faked points, ever.

THE NESTED CONDITIONAL WEIGHT is what makes two marginals exact at once:

    w(s, cell) = share_s(province) x d(shape | province) x proxy(cell) / proxy(shape)

The district factor is conditional WITHIN its province and sums to one there, so the
province marginal is exactly the sector's declared share vector while the district marginal
reproduces the panel exactly. Every fallback - an absent manual raster, a missing polygon
(Larkana), a province with no geocoded plant - is returned as a FallbackEvent and published
as data, because a fallback that lives in a log line is a substitution nobody audits.
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import csv
import os

import numpy as np

from pkinv.core import adm2
from pkinv.core.declared import match_prefix
from pkinv.core.geography import PROVINCES
from pkinv.core.gis import proxy_map
from pkinv.core.gis.proxies import get_proxy
from pkinv.paths import DATA, OUTPUTS

WEIGHT_TOL = 1e-9

RASTER_NAMES = ("cropland", "builtup", "population", "glw_livestock", "manure_applied",
                "spam_rice", "firms_fire", "uniform",
                # rc47 Wave 5: the OSM road raster, promoted from priced bracket to
                # the road-transport within-province basis
                "road_density")


class FallbackEvent(dict):
    """A declared substitution: (source_stream_id, scope, declared, used, reason), plus -
    rc41 - what the substitution COSTS: `weight_share`, the fraction of the stream's
    national weight that rides the substitute surface, recorded at the site that knows it
    (a shape's share x district share, a province's share, the whole stream for an absent
    raster) so the cube can price every event per stream, gas and methane origin. A
    district-panel event records `province` and `fraction` instead, because the panel is
    shared by every stream on it and the province share is the stream's own."""


def load_grid_proxy_registry():
    path = asset_path(DATA, "stream_grid_proxy.csv")
    rows = list(_activity_rows(path, comments=True))
    for row in rows:
        if row["raster_proxy"] not in RASTER_NAMES:
            raise ValueError("stream_grid_proxy names raster %r, outside the vocabulary %s"
                             % (row["raster_proxy"], RASTER_NAMES))
    return rows


def check_weight(arr, stream_id, tol=WEIGHT_TOL):
    total = float(arr.sum())
    if not np.isfinite(total) or abs(total - 1.0) > tol:
        raise ValueError("weight for %s sums to %.12f, not 1" % (stream_id, total))
    if float(arr.min()) < 0:
        raise ValueError("weight for %s carries negative mass" % stream_id)


def province_marginals(grid, arr):
    out = {}
    for province in PROVINCES:
        out[province] = float(arr[grid.province_mask(province)].sum())
    return out


_FRACTION_CACHE = {}


def _fraction_matrix(grid):
    """(indices, fractions, outside) from the committed intersection table (rc32).

    Per district index i: (flat cell indices, area fractions) - the exact
    partition scripts/build_adm2_intersections.py computed, replacing the
    all_touched alphabetical-last-wins tie-break of the label raster. The label
    array is unchanged and still serves the S-class derivation; only the
    marginals consume the fractions. Returns None when the table is absent so a
    partial checkout degrades to the label path loudly in the tests rather than
    silently here."""
    key = id(grid)
    if key in _FRACTION_CACHE:
        return _FRACTION_CACHE[key]
    import csv as _csv
    import os as _os
    from pkinv.paths import DATA
    path = asset_path(DATA, "gis", "adm2_intersections_267x340.csv")
    if not _os.path.exists(path):
        _FRACTION_CACHE[key] = None
        return None
    name_to_idx = {}
    for i, name in enumerate(grid.districts):
        name_to_idx[name] = i
    per_district = {}
    outside_idx, outside_frac = [], []
    for r in _activity_rows(path, comments=True):
        flat = int(r["row"]) * grid.width + int(r["col"])
        frac = float(r["area_fraction"])
        if r["shape_id"] == "OUTSIDE":
            outside_idx.append(flat)
            outside_frac.append(frac)
            continue
        idx = name_to_idx.get(r["shape_id"])
        if idx is None:
            idx = name_to_idx.get(r["shape_name"])
        if idx is None:
            # a polygon the grid's district list does not carry (the same
            # naming gap the label path has); its mass stays OUTSIDE
            outside_idx.append(flat)
            outside_frac.append(frac)
            continue
        per_district.setdefault(idx, ([], []))
        per_district[idx][0].append(flat)
        per_district[idx][1].append(frac)
    # RENORMALIZE per cell over its polygon claimants: a coastal cell's field
    # value is land activity (every proxy is a land surface and every point is a
    # land facility), so its sea fraction carries no separate mass - splitting
    # it to OUTSIDE would dilute a known facility into the sea. OUTSIDE keeps
    # only cells no polygon claims at all, the -1 semantics the label path had.
    claimed_total = {}
    for i, (ix, fr) in per_district.items():
        for flat, f in zip(ix, fr):
            claimed_total[flat] = claimed_total.get(flat, 0.0) + f
    packed = {}
    for i, (ix, fr) in per_district.items():
        arr_ix = np.asarray(ix, dtype=np.int64)
        arr_fr = np.asarray([f / claimed_total[flat]
                             for flat, f in zip(ix, fr)])
        packed[i] = (arr_ix, arr_fr)
    pure_outside = [(flat, f) for flat, f in zip(outside_idx, outside_frac)
                    if flat not in claimed_total]
    packed[-1] = (np.asarray([x for x, _ in pure_outside], dtype=np.int64),
                  np.asarray([f for _, f in pure_outside]))
    _FRACTION_CACHE[key] = packed
    return packed


_SHAPE_PROVINCE_CACHE = {}


def canonical_shape_province(grid):
    """index -> canonical province for every district the grid carries (rc40 G2).

    From adm2_canonical through the ADM2 geojson's shapeID, NOT from grid.district_province,
    which is a majority vote over the label raster. The ADM2 product labels its rows from the
    canonical register, so the nesting must use the same authority or the two can disagree
    at exactly the border cells this fix is about. A shape whose canonical members sit in more
    than one province would break the rule; there are none, and this raises if one appears.
    """
    key = id(grid)
    if key in _SHAPE_PROVINCE_CACHE:
        return _SHAPE_PROVINCE_CACHE[key]
    import json
    from pkinv.core.gis.grid import ADM2_PATH
    canonical = adm2.load_canonical()
    members = adm2.shape_to_adm2()
    name_to_idx = {name: i for i, name in enumerate(grid.districts)}
    out = [None] * len(grid.districts)
    with open(ADM2_PATH, encoding="utf-8") as handle:
        for feature in json.load(handle)["features"]:
            p = feature["properties"]
            idx = name_to_idx.get(p["shapeName"])
            if idx is None or p["shapeID"] not in members:
                continue
            provinces = {canonical[m]["province_id"] for m in members[p["shapeID"]]}
            if len(provinces) != 1:
                raise ValueError("shape %s spans provinces %s; the nested partition needs "
                                 "one province per shape" % (p["shapeID"], sorted(provinces)))
            out[idx] = provinces.pop()
    _SHAPE_PROVINCE_CACHE[key] = out
    return out


_NESTED_CACHE = {}


def _fraction_matrix_nested(grid, shape_province):
    """The rc32 area partition, renormalised per cell over claimants IN THE CELL'S PROVINCE.

    A boundary cell claimed by S (Punjab) and T (Sindh) gives all of its Punjab-allocated mass
    to S: T is not a claimant for a cell the province mask calls Punjab. Cells with no
    same-province claimant fall back to the plain partition and are counted in
    NESTED_ORPHANS so a boundary-file change that creates one is visible; at the release this
    was written against, there were none.
    """
    key = id(grid)
    if key in _NESTED_CACHE:
        return _NESTED_CACHE[key]
    from pkinv.core.geography import PROVINCES
    packed = _fraction_matrix(grid)
    if packed is None:
        _NESTED_CACHE[key] = None
        return None
    cell_province = grid.province_id.ravel()
    # claimants per cell, then keep only those whose shape is in the cell's province
    claimants = {}
    for i, (ix, fr) in packed.items():
        if i < 0:
            continue
        for flat, f in zip(ix.tolist(), fr.tolist()):
            claimants.setdefault(flat, []).append((i, f))
    per_district = {}
    orphans = 0
    for flat, items in claimants.items():
        code = int(cell_province[flat])
        province = PROVINCES[code] if 0 <= code < len(PROVINCES) else None
        same = [(i, f) for i, f in items if province is not None
                and shape_province[i] == province]
        if not same:
            orphans += 1
            same = items
        total = sum(f for _, f in same)
        for i, f in same:
            per_district.setdefault(i, ([], []))
            per_district[i][0].append(flat)
            per_district[i][1].append(f / total)
    nested = {}
    for i, (ix, fr) in per_district.items():
        nested[i] = (np.asarray(ix, dtype=np.int64), np.asarray(fr, dtype=np.float64))
    for i in range(len(grid.districts)):
        nested.setdefault(i, (np.zeros(0, dtype=np.int64), np.zeros(0)))
    nested[-1] = packed[-1]
    NESTED_ORPHANS[key] = orphans
    _NESTED_CACHE[key] = nested
    return nested


NESTED_ORPHANS = {}


def shape_marginals(grid, arr, shape_province=None):
    """Per-district-index mass of a surface.

    NESTED SINCE rc40 G2 when `shape_province` is given: a cell's mass is split only among
    claimant shapes in the cell's own province, so the shapes of each province sum to that
    province's marginal exactly. Without it, the rc32 behaviour below is unchanged.

    FRACTIONAL since rc32: boundary cells are split by exact polygon area
    (data/gis/adm2_intersections_267x340.csv) instead of donated whole to the
    alphabetically last district that touched them; the off-polygon remainder
    is key -1, now an explicit fraction row class rather than a bincount
    accident. Falls back to the label bincount only when the table is absent
    (a partial checkout), which the fraction tests catch."""
    packed = (_fraction_matrix_nested(grid, shape_province) if shape_province is not None
              else _fraction_matrix(grid))
    flat = arr.ravel()
    if packed is not None:
        out = {}
        for i, (idx, fr) in packed.items():
            out[i] = float((flat[idx] * fr).sum()) if len(idx) else 0.0
        for i in range(len(grid.districts)):
            out.setdefault(i, 0.0)
        return out
    ids = grid.district_id
    valid = ids >= 0
    sums = np.bincount(ids[valid].ravel().astype(np.int64),
                       weights=arr[valid].ravel(),
                       minlength=len(grid.districts))
    out = {i: float(sums[i]) for i in range(len(grid.districts))}
    out[-1] = float(arr[~valid].sum())
    return out


class Context:
    """Everything the weight builder reads, loaded once; finished weights cached by
    identity so 184 streams build ~80 arrays."""

    def __init__(self, grid, period=None):
        self.grid = grid
        # The period must arrive HERE and not be assigned afterwards: the FIRMS proxy is built
        # in this constructor, so a period set on the instance later is already too late for
        # it - which is why threading the period onto the context fixed the plant fleet and
        # left the fires on the reference year.
        self.period = period
        self.proxies = {}
        # {weight cache key: PointProjection} - the exact district vector
        # for weights built from facility points (rc45).
        self.point_projections = {}
        # The area array is built FIRST because every measure below is expressed in it.
        from pkinv.core.gis.grid import cell_area_km2
        self.cell_area = cell_area_km2(grid)
        # THE MEASURE, NOT THE RASTER (rc45). A fraction raster says "this share of the
        # cell is cropland"; the measure it generates is square kilometres of cropland, and
        # a 0.05-degree cell is 28.298 km2 in Sindh against 24.678 in Gilgit. Normalisation
        # cannot absorb the difference because cell area is not constant - it divides by a
        # scalar sum, so a per-row factor re-ranks cells against each other. What it CANNOT
        # do is move a provincial marginal or a national total: the factor sits inside the
        # per-province normaliser and the share is re-applied outside it.
        from pkinv.core.gis.proxies import as_measure
        for name in ("cropland", "builtup", "population", "glw_livestock",
                     "manure_applied"):
            self.proxies[name] = as_measure(
                name, get_proxy(name, grid)[0].astype(np.float64), self.cell_area)
        # rc47 Wave 5: the road raster is its OWN committed product (built by
        # scripts/build_road_network.py, sha-pinned in ROAD_SOURCES.json), so it
        # loads directly rather than through the get_proxy cache - a second copy
        # under data/gis/ would be an unregistered duplicate of a manifested file.
        # Extensive (km in the cell): no area weighting, per its registry row.
        from pkinv.core.primary_geography import PRIMARY_COMPATIBLE
        if not PRIMARY_COMPATIBLE:
            road = np.load(asset_path(DATA, "gis", "roads",
                                        "pak_road_density_%dx%d.npy"
                                        % (grid.height, grid.width)))
            if road.shape != (grid.height, grid.width):
                raise ValueError("road raster shape %s vs grid" % (road.shape,))
            self.proxies["road_density"] = road.astype(np.float64)
        # UNIFORM MEANS UNIFORM PER SQUARE KILOMETRE (rc44). This was np.ones, which is
        # uniform per square DEGREE, and a 0.05-degree cell is 28.298 km2 at 23.75 N against
        # 24.678 km2 at 37.05 N - so spreading a province's mass "evenly" over its cells put
        # 14.7 percent more per km2 in the north than in the south, purely because the cells
        # are smaller there. The array is held on the context because six other sites spread
        # mass over a bare mask for the same reason and must use the same measure.
        self.proxies["uniform"] = self.cell_area
        # The manual drop-in rasters, loaded WHEN HELD (rc13: the period-matched
        # FIRMS extraction finally landed, so the cube must consume it rather
        # than keep declaring it absent). Absence still produces the declared
        # fallback row in raster_for - this loop simply stops the ledger lying
        # in the other direction once the file exists.
        from pkinv.core.gis.proxies import build_firms_fire_proxy, build_manual_proxy
        for name, built in (("spam_rice", build_manual_proxy(grid, "spam_rice.tif")),
                            ("firms_fire", build_firms_fire_proxy(grid, period))):
            if built is not None and float(built[0].sum()) > 0:
                self.proxies[name] = built[0].astype(np.float64)
        self.registry_rows = load_grid_proxy_registry()
        self.shares = {}            # module -> load_shares(self.period) result
        self.weight_cache = {}
        self.fallbacks = []
        # rc41: the events each cached weight / district panel emitted while it was built,
        # so a stream that rides a cached surface is credited with the surface's events
        # (the register used to name only the first stream that built the cache).
        self.weight_events = {}
        self.factor_events = {}
        self.shape_masks = None     # shape_id -> boolean mask, built lazily
        self.adm2_to_shape = adm2.adm2_to_shape()
        self._district_index = None # grid district name -> district_id index

    def sector_shares(self, module):
        if module not in self.shares:
            from pkinv.core import registry as reg
            sector = next(s for s in reg.all_sectors() if s.NAME == module)
            # The CUBE is period-aware and the sector runners are not: a runner calls
            # load_shares() with no period and keeps the reference-year vector for the
            # annual provincial products, while this context passes the period it was
            # built for. One function, two callers, and the difference is explicit.
            self.shares[module] = sector.load_shares(self.period)
        return self.shares[module]

    def raster_for(self, stream):
        """The declared within-shape raster for a stream, with absent-manual fallback."""
        module = stream["module"]
        if module == "agriculture":
            # The sector's own declared mapping (proxy_map), keyed on the stream's
            # provincial proxy - duplicated nowhere, per the registry header note.
            name = proxy_map.gis_proxy(stream["spatial_profile_id"],
                                       stream["sub_category"], self.proxies)
            declared = proxy_map.GIS_PROXY_FOR.get(stream["spatial_profile_id"],
                                                   "cropland")
            # rc13, the eighth review's latent-defect fix: the residue-burning
            # streams' DECLARED raster is the manual fire layer (the gis_proxy
            # special case above uses it whenever it is loaded), but the declared
            # name used to collapse to the cropland fallback's own name, so the
            # firms_fire absence NEVER reached the machine-readable fallback
            # ledger - it was documented in prose only, and the ledger test
            # passed on spam_rice's substring alone. Declaring the intent here
            # makes the absence a recorded, allow-listed fallback event.
            if stream["engine_category"].startswith("Field burning"):
                declared = "firms_fire"
                # gis_proxy's own special case keys on the category STRING the
                # sector layer passes ("Field burning of residues"), which the
                # cube path never sends - it passes sub_category ("Residue
                # burning CH4"). So the held-layer routing must happen here,
                # beside the declaration, or the cube would keep gridding fire
                # on cropland while the ledger said nothing was wrong.
                if "firms_fire" in self.proxies:
                    name = "firms_fire"
        else:
            declared = match_prefix(self.registry_rows, module,
                                    stream["engine_category"], stream["sub_category"],
                                    "raster_proxy", "grid proxy")
            name = declared if declared in self.proxies else "cropland"
        if name != declared:
            self.fallbacks.append(FallbackEvent(
                source_stream_id=stream["source_stream_id"], scope="raster",
                declared=declared, used=name, weight_share=1.0,
                reason="manual raster absent from data/gis/manual (see PROXY_SOURCES.md)"))
        return self.proxies[name]

    def shape_mask(self, shape_id):
        if self.shape_masks is None:
            self.shape_masks = {}
            name_to_id = {name: i for i, name in enumerate(self.grid.districts)}
            import json
            from pkinv.core.gis.grid import ADM2_PATH as ADM2_GEOJSON
            with open(ADM2_GEOJSON, encoding="utf-8") as handle:
                features = json.load(handle)["features"]
            for feature in features:
                p = feature["properties"]
                idx = name_to_id.get(p["shapeName"])
                if idx is not None:
                    self.shape_masks[p["shapeID"]] = self.grid.district_id == idx
        return self.shape_masks.get(shape_id)


def district_factors(ctx, panel, stream_id):
    """{province: {shape_id: share}} from a district panel, sums to 1 per province.

    panel: {district_name: value}. Names resolve through the canonical package; several
    adm2 units on one shape sum onto the shape. A unit whose shape is declared missing
    (Larkana) becomes a FallbackEvent: its mass is spread by the within-province proxy
    instead of a polygon the boundary file does not have.
    """
    by_shape = {}
    lost = {}
    canonical = adm2.load_canonical()
    for name, value in panel.items():
        if not value:
            continue
        unit = canonical[adm2.resolve(name)]
        province = unit["province_id"]
        shape_id = unit["shape_id"]
        if not shape_id:
            lost[province] = lost.get(province, 0.0) + value
            continue
        by_shape.setdefault(province, {})
        by_shape[province][shape_id] = by_shape[province].get(shape_id, 0.0) + value
    for province, amount in lost.items():
        fraction = amount / (amount + sum(by_shape.get(province, {}).values()) or 1.0)
        ctx.fallbacks.append(FallbackEvent(
            source_stream_id=stream_id, scope="district",
            declared="panel share for a unit with no polygon",
            used="within-province proxy spread",
            province=province, fraction=fraction,
            reason="the boundary file has no shape for the unit (Larkana defect, declared "
                   "in adm2_canonical); %.4f of the %s panel mass falls back"
                   % (fraction, province)))
    out = {}
    for province, shapes in by_shape.items():
        total = sum(shapes.values()) + lost.get(province, 0.0)
        if total <= 0:
            continue
        out[province] = {shape: value / total for shape, value in shapes.items()}
        # The lost fraction is deliberately NOT renormalised away: it stays as
        # (1 - sum(shares)) and is spread by the plain province proxy below, so the
        # province marginal still closes to 1.
    return out


def province_cells(grid, stream, province):
    """The cells a stream's share for `province` may occupy.

    For the four named provinces this is the province mask. For "Other" - a reporting
    group of three territories, not a place - it is the mask restricted to the units the
    stream's OWN share row admits (data/province_shares.csv `other_membership`, read by
    core.geography.other_membership). Without this an OCAC row, whose Other is AJK + GB
    because Islamabad is folded into Punjab on its area pages, is spread over a mask that
    includes Islamabad and - built-up being what it is - lands there.
    """
    if province != "Other":
        return grid.province_mask(province)
    from pkinv.core import geography as geo
    return grid.members_mask(
        province, geo.members_of(geo.other_membership(stream.get("spatial_profile_id"))))


def diffuse_weight(ctx, stream, share_vector, factors=None):
    """province share x (district factor x) within-shape proxy, normalised."""
    grid = ctx.grid
    proxy = ctx.raster_for(stream)
    weight = np.zeros((grid.height, grid.width), dtype=np.float64)
    for province, share in share_vector.items():
        if share <= 0:
            continue
        mask = province_cells(grid, stream, province)
        if not mask.any():
            continue
        assigned = 0.0
        if factors and province in factors:
            for shape_id, d_share in factors[province].items():
                shape_mask = ctx.shape_mask(shape_id)
                if shape_mask is None:
                    continue
                cell_mask = shape_mask & mask
                if not cell_mask.any():
                    cell_mask = shape_mask
                block = proxy * cell_mask
                total = float(block.sum())
                if total <= 0:
                    block = cell_mask * ctx.cell_area
                    total = float(block.sum())
                    ctx.fallbacks.append(FallbackEvent(
                        source_stream_id=stream["source_stream_id"], scope="shape",
                        declared=stream["module"], used="uniform",
                        province=province, shape=shape_id, weight_share=share * d_share,
                        reason="proxy empty within shape %s" % shape_id))
                weight += block * (share * d_share / total)
                assigned += share * d_share
        remainder = share - assigned
        if remainder > 1e-15:
            block = proxy * mask
            total = float(block.sum())
            if total <= 0:
                block = mask * ctx.cell_area
                total = float(block.sum())
                ctx.fallbacks.append(FallbackEvent(
                    source_stream_id=stream["source_stream_id"], scope="province",
                    declared="proxy", used="uniform",
                    province=province, weight_share=remainder,
                    reason="proxy empty in %s" % province))
            weight += block * (remainder / total)
    total = float(weight.sum())
    if total <= 0:
        raise ValueError("empty weight for %s" % stream["source_stream_id"])
    return weight / total


def point_weight(ctx, points, stream_id, projection_key=None):
    """Normalised surface from (LON, LAT, activity) triples - native geometry, no
    province conditioning unless the caller applies it.

    rc45: a PURE point weight, so its district vector is entirely exact - there is no fallback
    half to project through cells. The raster still burns each point into its own cell, which
    is what a raster is for; the vector says which district the point is actually in.
    """
    from pkinv.core.gis.lines import burn_points
    grid = ctx.grid
    arr = burn_points(grid, points)
    total = float(arr.sum())
    if total <= 0:
        raise ValueError("no point mass for %s" % stream_id)
    if projection_key is not None:
        from pkinv.report.grid_cube import PointProjection
        projection = PointProjection(grid)
        projection.add_points([(lon, lat, activity) for lon, lat, activity in points], 1.0)
        ctx.point_projections[projection_key] = projection.finish(1.0)
    return arr / total
