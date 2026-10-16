"""Category-specific spatial proxy rasters for dasymetric allocation.

Per-category proxies, each read as remote COG windows via /vsicurl (no full download) and
resampled onto the national grid:
- `cropland`  - ESA WorldCover 2021 cropland fraction (class 40) -> soils, rice, burning, urea.
- `glw_livestock` - Gridded Livestock of the World 4 (ref. 2020), species density weighted by
  per-head enteric EF, so the surface represents where CH4 is actually produced -> enteric, manure.
  GLW 4 is OPEN on FAO Google Cloud Storage (no login).
- `population` - WorldPop 2020 (fallback / peri-urban proxy).
- Manual drop-in: files placed in data/gis/manual/ (e.g. spam_rice.tif) are used when present.

MapSPAM crop rasters and NASA FIRMS fire remain user-supplied via data/gis/manual/ (see
docs/DATA_ACQUISITION.md); the pipeline falls back to `cropland` when they are absent.
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import os

import numpy as np
import rasterio
from rasterio.transform import from_bounds
from rasterio.warp import reproject, Resampling
from rasterio.windows import from_bounds as window_from_bounds

from pkinv.core.gis.grid import DATA_GIS, RES
from pkinv.paths import ROOT

os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif")

WORLDCOVER = ("/vsicurl/https://s3.eu-central-1.amazonaws.com/esa-worldcover/v200/2021/"
              "map/ESA_WorldCover_10m_2021_v200_{tile}_Map.tif")
WORLDPOP = ("https://data.worldpop.org/GIS/Population/Global_2000_2020_1km/2020/PAK/"
            "pak_ppp_2020_1km_Aggregated.tif")
CROPLAND_CLASS = 40
BUILTUP_CLASS = 50

# GLW 4 (2020) dasymetric livestock density on FAO Google Cloud Storage (open, no login).
GLW_URL = ("/vsicurl/https://storage.googleapis.com/fao-gismgr-glw4-2020-data/DATA/"
           "GLW4-2020/MAPSET/D-DA/GLW4-2020.D-DA.{sp}.tif")
# species -> per-head enteric CH4 EF (kg/head/yr); weights where the methane is produced
GLW_EF_WEIGHT = {"CTL": 40.0, "BFL": 55.0, "SHP": 5.0, "GTS": 5.0}
MANUAL_DIR = asset_path(DATA_GIS, "manual")


def _grid_transform(grid):
    minx, miny, maxx, maxy = grid.bounds
    return from_bounds(minx, miny, maxx, maxy, grid.width, grid.height)


def build_cropland_proxy(grid, tile_subres=300):
    """Cropland fraction per grid cell from ESA WorldCover tiles (0..1)."""
    minx, miny, maxx, maxy = grid.bounds
    dst = np.zeros((grid.height, grid.width), dtype=np.float32)
    dst_transform = _grid_transform(grid)
    lat0 = int(np.floor(miny / 3) * 3)
    lon0 = int(np.floor(minx / 3) * 3)
    used = 0
    for ts in range(lat0, int(np.ceil(maxy)), 3):
        for tw in range(lon0, int(np.ceil(maxx)), 3):
            tile = "N%02dE%03d" % (ts, tw)
            url = WORLDCOVER.format(tile=tile)
            try:
                with rasterio.open(url) as src:
                    band = src.read(1, out_shape=(tile_subres, tile_subres),
                                    resampling=Resampling.nearest)
            except Exception:
                continue  # tile does not exist (ocean) or transient error
            crop = (band == CROPLAND_CLASS).astype(np.float32)
            src_transform = from_bounds(tw, ts, tw + 3, ts + 3, tile_subres, tile_subres)
            tmp = np.zeros_like(dst)  # reproject re-inits its dst, so warp per-tile then merge
            reproject(crop, tmp, src_transform=src_transform, src_crs="EPSG:4326",
                      dst_transform=dst_transform, dst_crs="EPSG:4326",
                      resampling=Resampling.average)
            np.maximum(dst, tmp, out=dst)  # tiles don't overlap; max avoids seam double-count
            used += 1
    dst[grid.province_id < 0] = 0.0
    return dst, "ESA WorldCover 2021 cropland fraction (%d tiles)" % used


def build_builtup_proxy(grid, tile_subres=300):
    """Built-up fraction per grid cell from ESA WorldCover tiles (0..1) - urbanisation signal used as
    an independent weak label for livestock management intensity (confined/stall-fed dairy)."""
    minx, miny, maxx, maxy = grid.bounds
    dst = np.zeros((grid.height, grid.width), dtype=np.float32)
    dst_transform = _grid_transform(grid)
    lat0 = int(np.floor(miny / 3) * 3)
    lon0 = int(np.floor(minx / 3) * 3)
    used = 0
    for ts in range(lat0, int(np.ceil(maxy)), 3):
        for tw in range(lon0, int(np.ceil(maxx)), 3):
            url = WORLDCOVER.format(tile="N%02dE%03d" % (ts, tw))
            try:
                with rasterio.open(url) as src:
                    band = src.read(1, out_shape=(tile_subres, tile_subres),
                                    resampling=Resampling.nearest)
            except Exception:
                continue
            built = (band == BUILTUP_CLASS).astype(np.float32)
            src_transform = from_bounds(tw, ts, tw + 3, ts + 3, tile_subres, tile_subres)
            tmp = np.zeros_like(dst)
            reproject(built, tmp, src_transform=src_transform, src_crs="EPSG:4326",
                      dst_transform=dst_transform, dst_crs="EPSG:4326",
                      resampling=Resampling.average)
            np.maximum(dst, tmp, out=dst)
            used += 1
    dst[grid.province_id < 0] = 0.0
    return dst, "ESA WorldCover 2021 built-up fraction (%d tiles)" % used


def build_population_proxy(grid):
    """Population density per grid cell from WorldPop 2020 (1 km), resampled.

    Prefers the locally held raster (data/gis/worldpop_pak_2020_1km.tif, fetched whole
    in August 2026 when data.worldpop.org stopped serving range requests, which broke
    the /vsicurl streaming path); falls back to streaming if the local file is absent.
    """
    dst = np.zeros((grid.height, grid.width), dtype=np.float32)
    local = asset_path(DATA_GIS, "worldpop_pak_2020_1km.tif")
    url = local if os.path.exists(local) else "/vsicurl/" + WORLDPOP
    with rasterio.open(url) as src:
        src_data = src.read(1)
        src_data = np.where(src_data < 0, 0, src_data).astype(np.float32)
        reproject(src_data, dst, src_transform=src.transform, src_crs=src.crs,
                  dst_transform=_grid_transform(grid), dst_crs="EPSG:4326",
                  resampling=Resampling.average)
    dst[grid.province_id < 0] = 0.0
    return dst, "WorldPop 2020 population (1 km)"


def build_glw_livestock_proxy(grid):
    """Emission-weighted livestock density from GLW 4 (2020): Σ species_density × enteric_EF."""
    minx, miny, maxx, maxy = grid.bounds
    dst_transform = _grid_transform(grid)
    dst = np.zeros((grid.height, grid.width), dtype=np.float32)
    used = []
    for sp, weight in GLW_EF_WEIGHT.items():
        try:
            with rasterio.open(GLW_URL.format(sp=sp)) as src:
                win = window_from_bounds(minx, miny, maxx, maxy, src.transform)
                data = src.read(1, window=win).astype(np.float32)
                data = np.where(data < 0, 0.0, data)          # nodata -> 0
                src_transform = src.window_transform(win)
                tmp = np.zeros_like(dst)
                reproject(data, tmp, src_transform=src_transform, src_crs=src.crs,
                          dst_transform=dst_transform, dst_crs="EPSG:4326",
                          resampling=Resampling.average)
                dst += tmp * weight
                used.append(sp)
        except Exception:
            continue
    dst[grid.province_id < 0] = 0.0
    return dst, "GLW4-2020 emission-weighted livestock density (%s)" % "+".join(used or ["none"])


def _glw_species(grid, sp):
    """Single GLW4 species density reprojected onto the grid (0 where nodata/unavailable)."""
    minx, miny, maxx, maxy = grid.bounds
    dst = np.zeros((grid.height, grid.width), dtype=np.float32)
    try:
        with rasterio.open(GLW_URL.format(sp=sp)) as src:
            win = window_from_bounds(minx, miny, maxx, maxy, src.transform)
            data = src.read(1, window=win).astype(np.float32)
            data = np.where(data < 0, 0.0, data)
            reproject(data, dst, src_transform=src.window_transform(win), src_crs=src.crs,
                      dst_transform=_grid_transform(grid), dst_crs="EPSG:4326",
                      resampling=Resampling.average)
    except Exception:
        pass
    return dst


def build_buffalo_share_proxy(grid):
    """Buffalo share of total livestock, GLW4 (2020): BFL/(CTL+BFL+SHP+GTS). Buffalo are Pakistan's
    stall-fed dairy animal, so a high share independently signals confined management -- and because it
    is a species-composition ratio it does NOT derive from the built-up management label (non-circular)."""
    bfl = _glw_species(grid, "BFL")
    total = sum(_glw_species(grid, sp) for sp in ("CTL", "BFL", "SHP", "GTS"))
    share = np.divide(bfl, total, out=np.zeros_like(bfl), where=total > 0).astype(np.float32)
    share[grid.province_id < 0] = 0.0
    return share, "GLW4-2020 buffalo share BFL/(CTL+BFL+SHP+GTS)"


def build_firms_fire_proxy(grid, period=None):
    """Fire-occurrence density from data/gis/manual/firms_fire.csv (VIIRS active fire),
    FRP-weighted (fire radiative power ~ biomass burned). Returns (array, desc) or None.

    Detections are filtered to the REPORTING PERIOD's own dates. The rc13 season fix
    made period-matching a correction, not a preference, and the Wave-3 backfetch put
    nine fiscal years in this one file - pooling them here would quietly turn the
    reference year's fire geography into a multi-year climatology."""
    path = asset_path(MANUAL_DIR, "firms_fire.csv")
    if not os.path.exists(path):
        return None
    # rc42 (S-3): the SAME attribution ladder as the temporal profile (pkinv.core.gis.firms:
    # burning window, Pakistan, cropland, away from kilns) and the same bare-FRP weight. The
    # rc41 raster kept every in-Pakistan detection and added 1 to each FRP, so 17.35 % of
    # its weight - 0.116 of the 0.670 Mt burning stream - rode kiln plumes and non-cropland
    # fires the temporal method had rejected. One event table, one answer.
    from pkinv.core.gis import firms
    from pkinv.sectors.agriculture import burn_windows
    # THE PERIOD'S OWN DATES, WHICH IS WHAT THE DOCSTRING ABOVE HAS ALWAYS ASKED FOR. This
    # was the literal 2023 from when the inventory placed one year, and it outlived that: the
    # nine-year build ran with every period's fires attributed to FY2023-24, which is the
    # "multi-year climatology" the rc13 fix exists to prevent, wearing the reference year's
    # face. firms.attribute() already took the year; nothing was missing but the argument.
    fy_start = int(period.fiscal_start_year) if period is not None else 2023
    windows = burn_windows.windows(fy_start)
    hits, counts = firms.attribute(fy_start, lambda when: burn_windows.in_window(windows, when))
    dst = np.zeros((grid.height, grid.width), dtype=np.float32)
    for row, col, frp, _month in hits:
        dst[row, col] += frp
    dst[grid.province_id < 0] = 0.0
    n = counts["attributed"]
    in_country = counts["detections_in_year"] - counts["outside_pakistan"]
    fetched = " of %d in Pakistan (%d in the year)" % (in_country, counts["detections_in_year"])
    sidecar = asset_path(MANUAL_DIR, "FIRMS_SOURCES.json")
    if os.path.exists(sidecar):
        import json
        try:
            with open(sidecar, encoding="utf-8") as handle:
                fetched = (" of %d fetched across the nine-year record"
                           % json.load(handle)["detections"])
        except (KeyError, ValueError):
            pass
    return dst, ("NASA FIRMS VIIRS fire-occurrence density "
                 "(%d attributed FY2023-24 detections%s: burning window, cropland, "
                 "away from kilns; FRP-weighted)" % (n, fetched))


# THE GRID-RESOLUTION CACHES OF THE MANUAL RASTERS (rc69). The three SPAM 2020 rice
# rasters (CC BY 4.0, RICE_SOURCES.json) are restricted layers: a public clone does not hold
# the 38 MB global files. Without them the cube placed rice on its declared fallback and the
# agriculture water-regime axis refused to run, so a public clone could not rebuild what
# the release publishes. Each raster's resample to the inventory grid - the only thing any
# reader takes from it - is committed beside the other proxy caches. The raster wins when it
# is mounted; tests/test_manual_proxy_caches.py holds every cache byte-identical to a fresh
# resample whenever the raster is present.
MANUAL_CACHED = ("spam_rice.tif", "spam2020_V2r2_global_A_RICE_I.tif",
                 "spam2020_V2r2_global_A_RICE_R.tif")
MANUAL_CACHE_DIR = os.path.join(ROOT, "data", "sectors", "agriculture", "gis")


def manual_cache_path(grid, filename):
    stem = os.path.splitext(filename)[0]
    return os.path.join(MANUAL_CACHE_DIR, "proxy_manual_%s_%dx%d.npy"
                        % (stem, grid.height, grid.width))


def build_manual_proxy(grid, filename):
    """Load a user-supplied raster from data/gis/manual/<filename>, resampled to the grid.
    Returns (array, desc) or None if the file is absent and has no committed grid cache."""
    path = asset_path(MANUAL_DIR, filename)
    if not os.path.exists(path):
        cache = manual_cache_path(grid, filename)
        if filename in MANUAL_CACHED and os.path.exists(cache):
            cached = np.load(cache)
            if cached.shape != (grid.height, grid.width):
                raise ValueError("manual proxy cache %s has shape %s against a %dx%d grid"
                                 % (os.path.basename(cache), cached.shape, grid.height,
                                    grid.width))
            return cached, "manual: data/gis/manual/%s" % filename
        return None
    return _resample_manual(grid, path, filename)


def _resample_manual(grid, path, filename):
    dst = np.zeros((grid.height, grid.width), dtype=np.float32)
    with rasterio.open(path) as src:
        data = src.read(1).astype(np.float32)
        data = np.where(data < 0, 0.0, data)
        reproject(data, dst, src_transform=src.transform, src_crs=src.crs or "EPSG:4326",
                  dst_transform=_grid_transform(grid), dst_crs="EPSG:4326",
                  resampling=Resampling.average)
    dst[grid.province_id < 0] = 0.0
    return dst, "manual: data/gis/manual/%s" % filename


def build_manure_applied_proxy(grid):
    """Where collected manure is actually spread: cropland presence x livestock density, per cell.

    Neither parent proxy is right on its own. Manure is applied to fields, so it cannot follow animal
    density alone; but transport cost keeps it near the herd that produced it, so it cannot follow
    cropland alone either -- a Balochistan herd's dung does not reach a Punjab field. The per-cell
    product is the dasymetric intersection: cropland that has livestock nearby.

    This must be formed per CELL. Multiplying province-level shares and renormalising is not the same
    operation and over-concentrates (it puts Punjab above its own cropland share).
    """
    crop, _ = get_proxy("cropland", grid)
    live, _ = get_proxy("glw_livestock", grid)
    dst = (crop.astype(np.float32) * live.astype(np.float32))
    dst[grid.province_id < 0] = 0.0
    return dst, "ESA WorldCover cropland x GLW4-2020 livestock density (per-cell intersection)"


GCD_RICE_TIF = asset_path(DATA_GIS, "manual", "gcd_rice_2023.tif")


def build_gcd_rice_proxy(grid):
    """GCD-Rice 2023 (30 m 0/1 paddy band) aggregated to the inventory grid: the
    fraction of each 0.05-degree cell classified paddy. Streamed row-by-row (the
    raster is strip-blocked); pixels outside the grid bounds are dropped, cells
    outside the country masked to 0 like every other proxy.

    rc41: moved here from report/rice_geography_crosscheck so the aggregate is a
    CACHED proxy (data/gis/proxy_gcd_rice_267x340.npy) like the five others - the
    validation package ships the 267x340 grid the engine actually reads, and the
    30 MB classified raster is read only on a cache miss. It is the crosscheck
    INSTRUMENT, never an allocation surface (PROXY_SOURCES.md)."""
    if not os.path.exists(GCD_RICE_TIF):
        raise FileNotFoundError(
            "%s absent and no proxy_gcd_rice cache to read - the own-year instrument "
            "is part of the Wave-5 deposit (RICE_SOURCES.json)" % GCD_RICE_TIF)
    import rasterio
    from rasterio.windows import Window

    minx, miny, maxx, maxy = grid.bounds
    res = (maxx - minx) / grid.width
    paddy = np.zeros((grid.height, grid.width), dtype=np.float64)
    count = np.zeros((grid.height, grid.width), dtype=np.float64)
    with rasterio.open(GCD_RICE_TIF) as src:
        tr = src.transform
        lons = tr.c + (np.arange(src.width) + 0.5) * tr.a
        cols = np.floor((lons - minx) / res).astype(np.int64)
        keep = (cols >= 0) & (cols < grid.width)
        cols_k = cols[keep]
        ones = np.bincount(cols_k, minlength=grid.width).astype(np.float64)
        for i in range(src.height):
            lat = tr.f + (i + 0.5) * tr.e
            row = int((maxy - lat) / res)
            if row < 0 or row >= grid.height:
                continue
            band = src.read(1, window=Window(0, i, src.width, 1))[0]
            vals = band[keep]
            paddy[row] += np.bincount(cols_k, weights=vals, minlength=grid.width)
            count[row] += ones
    with np.errstate(invalid="ignore", divide="ignore"):
        frac = np.where(count > 0, paddy / count, 0.0)
    frac[grid.province_id < 0] = 0.0
    return frac.astype(np.float32), ("GCD-Rice 2023 30 m classified paddy extent, "
                                     "fraction of each cell (crosscheck instrument)")


_BUILDERS = {"cropland": build_cropland_proxy, "population": build_population_proxy,
             "glw_livestock": build_glw_livestock_proxy, "builtup": build_builtup_proxy,
             "buffalo_share": build_buffalo_share_proxy,
             "manure_applied": build_manure_applied_proxy,
             "gcd_rice": build_gcd_rice_proxy}


# --- what a proxy's numbers ARE -------------------------------------------------------------

_SEMANTICS = {}


def semantics():
    """{proxy: row} from data/grid_proxy_semantics.csv, read once.

    rc44 measured every tag and shipped the registry; nothing read it. The `area_weight`
    column was a description of what the allocator ought to do, sitting beside an allocator
    that did not do it - for the FALLBACK surfaces only, rc44 applied cell area by hand, so a
    stream whose built-up proxy was empty in Balochistan got an area-correct spread and the
    same stream in Punjab did not. This function makes the registry the authority.
    """
    if not _SEMANTICS:
        import csv
        import os
        from pkinv.paths import DATA
        path = asset_path(DATA, "grid_proxy_semantics.csv")
        for row in _activity_rows(path, comments=True):
            _SEMANTICS[row["proxy"]] = row
    return _SEMANTICS


_KIND_EXPONENT = {"fraction": 1, "constant": 1, "count": 0, "feature_weight": 0}


def _area_exponent(name, seen=()):
    """How many times cell area multiplies this proxy: 0 for a count, 1 for a fraction.

    A DERIVED proxy takes the sum of its parents' exponents, which is what "apply area
    exactly once" means for manure_applied - cropland is a fraction and glw_livestock is a
    count, so their product carries area once and not twice. Declared in the registry's
    derived_from column rather than special-cased here."""
    row = semantics().get(name)
    if row is None:
        raise KeyError("%s has no row in data/grid_proxy_semantics.csv; every raster the "
                       "allocator uses must declare what its numbers are" % name)
    kind = row["semantics"]
    if kind in ("fraction", "constant"):
        return 1
    if kind in ("count", "feature_weight"):
        return 0
    if kind == "derived":
        parents = [p for p in row.get("derived_from", "").split(";") if p]
        if not parents:
            raise ValueError("%s is derived and names no parents in derived_from" % name)
        if name in seen:
            raise ValueError("derived_from is cyclic at %s" % name)
        return sum(_area_exponent(p, seen + (name,)) for p in parents)
    raise ValueError("%s declares unknown semantics %r" % (name, kind))


def as_measure(name, array, cell_area, declared=None):
    """The spatial MEASURE a proxy generates, ready to be normalised into a weight.

    `uniform` is already the area array, so its exponent of 1 is satisfied by the value it
    was given; every other constant would need the multiplication. The rule is applied here
    and nowhere else, so there is one place to read and one place to be wrong."""
    if name == "uniform":
        return array
    # `declared` lets a caller name the semantics of a proxy that is not in the registry -
    # a synthetic fixture exercising the allocation identity, for instance. It is NOT a
    # default: an unregistered name with no declaration still raises, because a silent
    # fallback is precisely how a fraction came to be spread as though it were a count.
    exponent = (_KIND_EXPONENT[declared] if declared is not None
                else _area_exponent(name))
    out = array
    for _ in range(exponent):
        out = out * cell_area
    return out


def get_proxy(name, grid, use_cache=True, cache_dir=None):
    """Return (array, description). Cached to data/gis/proxy_<name>_<HxW>.npy.

    The five caches are COMMITTED inputs (data/gis/PROXY_SOURCES.md) so the cube is
    offline-deterministic. A cache whose shape disagrees with the grid is refused loudly:
    a stale raster silently reshaped or broadcast would place emissions on the wrong cells
    with no error anywhere downstream. cache_dir exists so the guard's own test can plant a
    wrong-shape file in a scratch directory instead of data/.
    """
    base = cache_dir or DATA_GIS
    cache = asset_path(base, "proxy_%s_%dx%d.npy" % (name, grid.height, grid.width))
    desc_f = cache + ".txt"
    if use_cache and os.path.exists(cache):
        with open(desc_f) as f:
            cached = np.load(cache)
            if cached.shape != (grid.height, grid.width):
                raise ValueError(
                    "proxy cache %s has shape %s against a %dx%d grid - a mis-shaped "
                    "raster would place emissions on the wrong cells; rebuild it with "
                    "use_cache=False" % (os.path.basename(cache), cached.shape,
                                         grid.height, grid.width))
            if np.nansum(cached) > 0:
                return cached, f.read()
    arr, desc = _BUILDERS[name](grid)
    # A network-unavailable remote source returns an empty array.  It is a runtime
    # fallback condition, not a valid reusable spatial product: caching it would
    # silently preserve a transient download failure after connectivity returns.
    if np.nansum(arr) > 0:
        np.save(cache, arr)
        with open(desc_f, "w") as f:
            f.write(desc)
    return arr, desc
