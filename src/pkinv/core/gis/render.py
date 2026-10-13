"""GeoTIFF and hotspot-map writers for Phase 4."""
import os

import numpy as np
import rasterio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LogNorm  # noqa: E402

from pkinv.core.gis.proxies import _grid_transform  # noqa: E402


def write_geotiff(path, arr, grid, nodata=-9999.0):
    data = arr.astype(np.float32).copy()
    data[grid.province_id < 0] = nodata
    with rasterio.open(
        path, "w", driver="GTiff", height=grid.height, width=grid.width, count=1,
        dtype="float32", crs="EPSG:4326", transform=_grid_transform(grid),
        nodata=nodata, compress="deflate",
    ) as dst:
        dst.write(data, 1)


def _masked(arr, grid):
    m = np.ma.masked_where(grid.province_id < 0, arr)
    return np.ma.masked_where(arr <= 0, m)


def _overlay_provinces(ax):
    """Draw the 5-province ADM1 outline on a map for geographic reference (best-effort)."""
    try:
        import geopandas as gpd
        from pkinv.core.gis.grid import ADM1_PATH
        gpd.read_file(ADM1_PATH).to_crs("EPSG:4326").boundary.plot(
            ax=ax, edgecolor="#888", linewidth=0.6, alpha=0.7)
    except Exception:      # noqa: BLE001
        pass


def plot_total(path, total, grid, title, cbar_label="Mt CO2e per cell (log scale)",
               zero_label="grey: in-country cells with zero allocation"):
    """zero_label is CALL-SITE SEMANTICS, not decoration. For the gridded proxy maps
    a grey cell is genuine data (the proxy assigns nothing there). For the
    residential district choropleth the same grey means NO DATA - an ADM2 boundary
    district whose census row failed the name match, with real non-zero emissions in
    the CSV - and until rc12 this function asserted 'zero allocation' for both,
    which the eighth review flagged. A caller painting no-data must say so."""
    fig, ax = plt.subplots(figsize=(8, 6.5))
    minx, miny, maxx, maxy = grid.bounds
    data = _masked(total, grid)
    vmax = float(total.max())
    vmin = max(total[total > 0].min(), vmax * 1e-4) if (total > 0).any() else 1e-6
    # Grey layer under the log ramp for in-country zero-valued cells (meaning per
    # zero_label), leaving out-of-country cells white.
    zero_in_country = np.ma.masked_where(
        ~((grid.province_id >= 0) & ~(total > 0)), np.zeros_like(total))
    ax.imshow(zero_in_country, extent=(minx, maxx, miny, maxy), origin="upper",
              cmap=matplotlib.colors.ListedColormap(["#dddddd"]), vmin=0, vmax=1)
    im = ax.imshow(data, extent=(minx, maxx, miny, maxy), origin="upper",
                   cmap="inferno", norm=LogNorm(vmin=vmin, vmax=vmax))
    _overlay_provinces(ax)
    ax.text(0.01, 0.01, zero_label,
            transform=ax.transAxes, fontsize=7, color="#555555")
    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    ax.set_title(title)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    cb = fig.colorbar(im, ax=ax, shrink=0.8)
    cb.set_label(cbar_label)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


# display-only labels (core category keys are load-bearing; relabel at plot time only)
_DISPLAY = {"Urea application": "Urea application"}


def plot_by_category(path, allocated, grid):
    cats = list(allocated.keys())
    ncol = 3 if len(cats) > 4 else 2
    nrow = -(-len(cats) // ncol)  # ceil
    fig, axes = plt.subplots(nrow, ncol, figsize=(5.2 * ncol, 4.3 * nrow))
    minx, miny, maxx, maxy = grid.bounds
    axflat = axes.ravel()
    for ax in axflat[len(cats):]:
        ax.axis("off")  # hide unused panels
    for ax, cat in zip(axflat, cats):
        arr = allocated[cat]
        data = _masked(arr, grid)
        if (arr > 0).any():
            vmax = float(arr.max())
            vmin = max(arr[arr > 0].min(), vmax * 1e-4)
            norm = LogNorm(vmin=vmin, vmax=vmax)
        else:
            norm = None
        im = ax.imshow(data, extent=(minx, maxx, miny, maxy), origin="upper",
                       cmap="viridis", norm=norm)
        ax.set_title("%s (%.1f Mt)" % (_DISPLAY.get(cat, cat), arr.sum()))
        fig.colorbar(im, ax=ax, shrink=0.7)
    fig.suptitle("Pakistan agricultural emissions by category (2024, provisional)")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
