#!/usr/bin/env python3
"""Figures 4, 5 and 6: the three gases on the released grid, what supports the placement, and
which surface placed the mass and how concentrated it is.

READ-AND-PLOT ONLY. Every number drawn is read from a released product; the only arithmetic is
summing cells, summing stream masses and dividing by a total.

Inputs (products of the release this is run against):
  outputs/pakemis_grid_0p05_annual_ref_fy2015_16_fy2023_24.nc   the nine-period cube
  outputs/pakemis_stream_support_ledger.csv                     mass x spatial support
  outputs/pakemis_spatial_weights_by_year.csv                   surface and vintage per stream
  outputs/pakemis_spatial_unallocated_by_year.csv               the mass NOT on the map
  data/shared/gis/PAK_ADM1.geojson, BOUNDARY_SOURCES.json, adm2_canonical.csv

Outputs, in paper_national/figures/:
  f04_gas_maps.pdf                      three maps of placed mass, one per gas
  f05_spatial_evidence.pdf              evidence class behind the placement, nine years x gas
  f06_proxy_concentration.pdf           surface and vintage; concentration of placed mass
  fig_ghg_grid_cells_fy2023_24.csv      the per-cell values behind the maps
  fig_ghg_grid_evidence.csv             the shares behind figure 5
  fig_ghg_grid_proxy.csv                the shares behind figure 6(a)
  fig_ghg_grid_concentration.csv        points on the curves of figure 6(b, c)
  fig_ghg_grid_provenance.json / .tex   declarations, digests and the closure checks

ONE PLATE BECAME TWO (rc63). The evidence figure carried five panels and two legends on one
page, and LaTeX shrank it by a height cap: its legend was 4.6 pt in the review layout and
5.2 pt in the two-column one. It answers three different questions - what supports the
placement, which surface did the placing, how concentrated the result is - so the first is now
its own figure and the other two share a second. Each is drawn at its printed size through
pkinv.report.manuscript_style and is never rescaled.

THREE THINGS THIS FILE USED TO SAY THAT WERE NOT TRUE, found when every label was traced:
  - "every raster predates the year it places": the road surface is an OpenStreetMap extract of
    August 2026, later than every period;
  - "all in-country cells are strictly positive for every gas": 2,835 valid cells hold exactly
    zero N2O, and are now drawn as their own state;
  - the cropland surface was called "SPAM 2020" (it is ESA WorldCover 2021) while the MapSPAM
    rice surface had no label at all; corrected at the product (pkinv.report.spatial_weights).
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from pkinv.report import manuscript_style as S  # noqa: E402

plt = S.use()

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import xarray as xr  # noqa: E402
from matplotlib.colors import ListedColormap, LogNorm  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch, Polygon as MplPolygon  # noqa: E402

OUT = REPO / "paper_national" / "figures"
PREVIEWS = OUT / "rewrite_inputs" / "previews"
SCRIPT = "scripts/make_fig_ghg_grid.py"

CUBE = REPO / "outputs/pakemis_grid_0p05_annual_ref_fy2015_16_fy2023_24.nc"
LEDGER = REPO / "outputs/pakemis_stream_support_ledger.csv"
WEIGHTS = REPO / "outputs/pakemis_spatial_weights_by_year.csv"
UNALLOC = REPO / "outputs/pakemis_spatial_unallocated_by_year.csv"
ADM1 = REPO / "data/shared/gis/PAK_ADM1.geojson"
BSRC = REPO / "data/shared/gis/BOUNDARY_SOURCES.json"
ADM2C = REPO / "data/shared/gis/adm2_canonical.csv"

YEAR = "FY2023-24"          # the reference period
GASES = ("CO2", "CH4", "N2O")

# The spatial-evidence vocabulary, in stacking order, with the registry's plain names.
BASIS_ORDER = [(code, label, colour) for code, label, colour, _ in S.EVIDENCE]
BASIS_HATCH = {label: hatch for _, label, _, hatch in S.EVIDENCE}

# WHICH SURFACE PLACED THE MASS. The product names a surface per stream; a reader needs nine
# kinds, not twenty-two identifiers.
#
# A REGISTER WITH A FALLBACK IS TWO SURFACES, AND ITS MASS IS SPLIT BETWEEN THEM. The first
# version of this figure filed every "<points>+<raster>_fallback" stream under its points. The
# wastewater-plant register locates 5 % of its stream and the waste-site register 29 %; the rest
# falls back to population. Filed whole under "facility locations" they put 16 % of CH4 at
# register points where 5 % is, and drew population at 2 % where it carries 13 % - and the
# evidence figure beside it calls that same mass a stand-in surface. `located_share` in the
# ledger says how much of each stream its points hold; the remainder goes to the fallback.
PROXY_OF = {
    "builtup": "builtup", "builtup+ocac_area_shares": "builtup",
    "road_density": "roads", "glw_livestock": "livestock", "cropland": "cropland",
    "manure_applied": "manure", "spam_rice": "rice", "population": "population",
    "firms_fire": "other", "rail_network_line_density": "other", "uniform": "other",
    "none": "kept",                      # no surface at all: the mass retained at province level
}
FALLBACK_OF = {"builtup_fallback": "builtup", "population_fallback": "population",
               "uniform_fallback": "other"}
PROXY_ORDER = [(code, label, colour) for code, label, colour in S.PROXY]


def proxy_parts(surface, located_share):
    """[(group, fraction of the stream's mass)]: one part for a plain surface, two for a point
    register with a fallback."""
    surface = "" if surface is None or (isinstance(surface, float) and np.isnan(surface)) else str(surface)
    if "points" not in surface:
        return [(PROXY_OF.get(surface, "other"), 1.0)]
    if "+" not in surface:
        return [("points", 1.0)]
    fallback = FALLBACK_OF[surface.split("+", 1)[1]]
    located = 1.0 if located_share is None or np.isnan(located_share) else float(located_share)
    assert 0.0 <= located <= 1.0, (surface, located)
    return [("points", located), (fallback, 1.0 - located)]


def digest(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for blk in iter(lambda: fh.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


# ---------------------------------------------------------------- load
ds = xr.open_dataset(CUBE, decode_times=False)
periods = [str(x) for x in ds.period_id.values]
iy = periods.index(YEAR)
lat = ds.lat.values
lon = ds.lon.values
lat_b = ds.lat_bnds.values
lon_b = ds.lon_bnds.values
pak_frac = ds.pakistan_fraction.values
cell_area = ds.cell_area.values

# The three spatial views are DISJOINT and partition the mass, so the mass placed
# in a cell is their sum. Summing them is not double counting; dropping one would
# be undercounting. _FillValue (-9999) is already NaN here; np.nansum would turn
# an out-of-country NaN into 0, so the mask is rebuilt explicitly instead.
def placed(gas: str, i: int) -> np.ndarray:
    # float64 BEFORE the sum. The cube stores float32, and a running sum of 33,674 float32
    # cells stops growing once a cell is smaller than the sum's last bit: the concentration
    # table reached "100 %" of CH4 at 33,039 cells though every one of the 33,674 is positive.
    v = ds[f"{gas}_emissions"].isel(time=i).values.astype("float64")     # (view, lat, lon)
    inside = np.isfinite(v).all(axis=0)
    tot = np.where(inside, np.nansum(v, axis=0), np.nan)
    return tot

co2 = placed("co2", iy)
ch4 = placed("ch4", iy)
n2o = placed("n2o", iy)
inside = np.isfinite(co2)

ledger = pd.read_csv(LEDGER, comment="#")
weights = pd.read_csv(WEIGHTS)
unal = pd.read_csv(UNALLOC)

key = ["period_id", "source_stream_id", "gas"]
ev = ledger.merge(weights[key + ["surface_vintage"]], on=key, how="left", validate="one_to_one")
ev["surface_vintage"] = ev["surface_vintage"].fillna("")
# one row per (stream, surface group), with the stream's mass divided by its located share
_parts = []
for row in ev.itertuples(index=False):
    for group, fraction in proxy_parts(row.surface, row.located_share):
        if fraction > 0.0:
            _parts.append({"period_id": row.period_id, "gas": row.gas, "surface": row.surface,
                           "surface_vintage": row.surface_vintage, "proxy_group": group,
                           "share_of_stream": fraction, "emissions_Gg": row.emissions_Gg * fraction})
surf = pd.DataFrame(_parts)
assert abs(surf.emissions_Gg.sum() - ev.emissions_Gg.sum()) <= 1e-9 * ev.emissions_Gg.sum()

# ---------------------------------------------------------------- closure checks
checks = {}
for gas_l, gas_u, arr_name in (("co2", "CO2", "co2"), ("ch4", "CH4", "ch4"), ("n2o", "N2O", "n2o")):
    rows = []
    for i, p in enumerate(periods):
        grid = float(np.nansum(placed(gas_l, i)))
        L = float(ledger.loc[(ledger.period_id == p) & (ledger.gas == gas_u), "emissions_Gg"].sum())
        U = float(unal.loc[(unal.period_id == p) & (unal.gas == gas_u), "emissions_Gg"].sum())
        rows.append({"period_id": p, "grid_Gg": grid, "unallocated_Gg": U,
                     "ledger_Gg": L, "residual_Gg": grid + U - L,
                     "residual_ppm_of_ledger": 1e6 * (grid + U - L) / L})
    checks[gas_u] = rows
worst = max(abs(r["residual_ppm_of_ledger"]) for rs in checks.values() for r in rs)

# the ledger's own 'unallocated' basis rows must equal the unallocated product
for gas_u in ("CO2", "CH4", "N2O"):
    a = ledger[(ledger.period_id == YEAR) & (ledger.gas == gas_u) &
               (ledger.spatial_time_basis == "unallocated")].emissions_Gg.sum()
    b = unal[(unal.period_id == YEAR) & (unal.gas == gas_u)].emissions_Gg.sum()
    # the ledger publishes emissions_Gg rounded, so compare at the published precision
    assert abs(a - b) <= max(1e-5, 1e-7 * abs(b)), (gas_u, a, b)

# ---------------------------------------------------------------- evidence shares
def shares(gas_u: str, col: str, order, frame=None) -> pd.DataFrame:
    frame = ev if frame is None else frame
    out = []
    for p in periods:
        q = frame[(frame.gas == gas_u) & (frame.period_id == p)]
        tot = q.emissions_Gg.sum()
        row = {"period_id": p, "total_Gg": tot}
        for kcode, label, _ in order:
            row[label] = 100.0 * q.loc[q[col] == kcode, "emissions_Gg"].sum() / tot
        out.append(row)
    return pd.DataFrame(out)


basis_co2 = shares("CO2", "spatial_time_basis", BASIS_ORDER)
basis_ch4 = shares("CH4", "spatial_time_basis", BASIS_ORDER)
basis_n2o = shares("N2O", "spatial_time_basis", BASIS_ORDER)
proxy = pd.concat([shares(g, "proxy_group", PROXY_ORDER, surf).assign(gas=g) for g in GASES])
# every stream's mass is in exactly one evidence class and one surface group
for _df in (basis_co2, basis_ch4, basis_n2o):
    assert np.allclose(_df[[l for _, l, _ in BASIS_ORDER]].sum(axis=1), 100.0, atol=1e-9)
assert np.allclose(proxy[[l for _, l, _ in PROXY_ORDER]].sum(axis=1), 100.0, atol=1e-9)

# ---------------------------------------------------------------- concentration
conc = {}
for name, arr in (("CO2", co2), ("CH4", ch4), ("N2O", n2o)):
    # every valid cell, zeros included, ranked from the highest mass; float64 throughout
    v = np.sort(arr[inside].astype("float64"))[::-1]
    c = np.cumsum(v) / v.sum()
    conc[name] = (np.arange(1, v.size + 1) / v.size, c, v)

# ---------------------------------------------------------------- boundary frame
gj = json.load(open(ADM1))
STAT = {"Balochistan", "Sindh", "Khyber Pakhtunkhwa", "Punjab", "Islamabad Capital Territory"}
frame = []
for f in gj["features"]:
    nm = f["properties"].get("shapeName")
    rings = f["geometry"]["coordinates"]
    if f["geometry"]["type"] == "Polygon":
        rings = [rings]
    for poly in rings:
        frame.append((nm, np.asarray(poly[0] if isinstance(poly[0][0], list) else poly)))


def draw_frame(ax):
    """The boundary layer, quiet and in one colour. A territory that is inside the gridded frame
    and outside the national statistical panels is dashed, which is a statement about the
    reporting frame and about nothing else."""
    for nm, ring in frame:
        ax.add_patch(MplPolygon(ring, closed=True, fill=False, ec=S.MUTED, lw=0.45,
                                ls="-" if nm in STAT else (0, (2.6, 1.6)), zorder=5))


# ================================================================ Figure 4: the three maps
# Cell edges, so each native 0.05 degree cell is drawn as itself: no interpolation, no smoothing.
X, Y = np.meshgrid(np.append(lon_b[:, 0], lon_b[-1, 1]), np.append(lat_b[:, 0], lat_b[-1, 1]))
MID_LAT = float((lat_b.min() + lat_b.max()) / 2.0)
ASPECT = 1.0 / np.cos(np.deg2rad(MID_LAT))     # plate carree, undistorted at the mid-latitude

# FOUR STATES, FOUR TREATMENTS. Outside the reporting mask there is no value and the page shows
# through. A valid cell with exactly zero mass is a statement about that cell and is a neutral
# grey that is not on the ramp. Positive mass is on the ramp, dark for high, because the page is
# white. A log scale has no place for zero, so zero is never nudged to a small number. And a cell
# below the scale's floor takes one pale colour of its own, marked by the bar's pointed end.
ZERO = "#d5d8dc"
UNDER = "#fbf7d0"
RAMP = plt.get_cmap("viridis_r").copy()
RAMP.set_bad((0, 0, 0, 0))
RAMP.set_under(UNDER)
FLOOR_MASS_SHARE = 0.999          # the scale spans the cells that together hold this much mass
SUP = str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹")


def scale_limits(arr):
    """A log scale that is spent on the mass.

    The first version ran from the fifth percentile of the positive cells to the next decade
    above the largest: nine decades for CO2, of which the lower half held 64 % of the cells and
    0.6 % of the mass, while the 78 cells that hold half the CO2 shared the top sliver. The
    floor is now the decade at or below the smallest cell among those that together hold 99.9 %
    of the gas's placed mass; everything under it, together under a thousandth of the mass, is
    one pale colour. The ceiling is the next of 1, 2 or 5 times a power of ten above the largest
    cell, so the top of the ramp is used.
    """
    values = np.sort(arr[inside & (arr > 0)])[::-1]
    held = np.cumsum(values) / values.sum()
    smallest_needed = values[int(np.searchsorted(held, FLOOR_MASS_SHARE))]
    low = 10.0 ** np.floor(np.log10(smallest_needed))
    decade = 10.0 ** np.floor(np.log10(values[0]))
    high = next(m * decade for m in (1.0, 2.0, 5.0, 10.0) if m * decade >= values[0])
    return low, high


MAPS = {"CO2": co2, "CH4": ch4, "N2O": n2o}
map_facts = {}
fig = S.figure(S.FULL_WIDTH, 3.30)
left, width, gap = 0.058, 0.292, 0.030
for k, gas in enumerate(GASES):
    arr = MAPS[gas]
    ax = fig.add_axes([left + k * (width + gap), 0.350, width, 0.565])
    ax.set_anchor("S")
    vmin, vmax = scale_limits(arr)
    valid = arr[inside]
    n_zero = int((valid == 0).sum())
    below = (valid > 0) & (valid < vmin)
    n_below = int(below.sum())
    assert int((valid > vmax).sum()) == 0, gas
    ax.pcolormesh(X, Y, np.where(inside & (arr == 0), 1.0, np.nan), cmap=ListedColormap([ZERO]),
                  shading="flat", zorder=1, rasterized=True)
    mesh = ax.pcolormesh(X, Y, np.where(inside & (arr > 0), arr, np.nan), cmap=RAMP,
                         norm=LogNorm(vmin=vmin, vmax=vmax), shading="flat", zorder=2,
                         rasterized=True)
    draw_frame(ax)
    ax.set_xlim(lon_b.min(), lon_b.max())
    ax.set_ylim(lat_b.min(), lat_b.max())
    ax.set_aspect(ASPECT)
    ax.set_xticks([65, 70, 75], ["65° E", "70° E", "75° E"])
    ax.set_yticks([25, 30, 35], ["25° N", "30° N", "35° N"] if k == 0 else ["", "", ""])
    ax.tick_params(length=2.5)
    for side in ("top", "right"):
        ax.spines[side].set_visible(True)
    ax.set_title("(%s) %s, placed mass %s Gg" % ("abc"[k], S.GAS_LABEL[gas],
                                                 S.thousands(np.nansum(arr))),
                 loc="left", pad=4.0, fontsize=S.SIZE_LABEL)
    box = ax.get_position()
    # inset from the map's edges, so the end labels of neighbouring bars cannot meet
    cax = fig.add_axes([box.x0 + 0.06 * box.width, 0.235, 0.88 * box.width, 0.030])
    bar = fig.colorbar(mesh, cax=cax, orientation="horizontal",
                       extend="min" if n_below else "neither")
    bar.outline.set_linewidth(0.4)
    bar.outline.set_edgecolor(S.MUTED)
    decades = np.arange(np.ceil(np.log10(vmin)), np.floor(np.log10(vmax)) + 0.5)
    # every decade, every one written the same way: powers of ten in Unicode superscripts
    bar.set_ticks([10.0 ** d for d in decades], labels=["10" + str(int(d)).translate(SUP) for d in decades])
    bar.ax.minorticks_off()
    bar.ax.tick_params(length=2.5)
    bar.set_label("%s mass (Gg cell⁻¹ yr⁻¹)" % S.GAS_LABEL[gas], fontsize=S.SIZE_TICK, labelpad=2.0)
    map_facts[gas] = {"log_limits_Gg": [vmin, vmax], "valid_cells": int(inside.sum()),
                      "zero_cells": n_zero, "cells_below_lower_limit": n_below,
                      "mass_share_below_lower_limit_pct": float(100.0 * valid[below].sum() / valid.sum()),
                      "placed_Gg": float(np.nansum(arr))}
    assert map_facts[gas]["mass_share_below_lower_limit_pct"] < 100.0 * (1.0 - FLOOR_MASS_SHARE) + 1e-9

row_one = [Line2D([], [], color=S.MUTED, lw=0.8, label="Administrative boundary, first level"),
           Patch(facecolor=UNDER, edgecolor=S.RULE, linewidth=0.4,
                 label="Below the scale: together under 0.1 % of the mass")]
if any(f["zero_cells"] for f in map_facts.values()):
    row_one.append(Patch(facecolor=ZERO, edgecolor="none", label="Zero mass"))
fig.legend(handles=row_one, loc="lower left", bbox_to_anchor=(left, 0.062), ncol=len(row_one),
           columnspacing=1.6, handletextpad=0.6)
# named as the technical supplement's vocabulary table names them (tab:other_units); what is
# stated is the reporting frame and nothing else
fig.legend(handles=[Line2D([], [], color=S.MUTED, lw=0.8, ls=(0, (2.6, 1.6)),
                           label="Gilgit-Baltistan and Azad Jammu and Kashmir: gridded, outside the national statistical tables")],
           loc="lower left", bbox_to_anchor=(left, 0.0), handletextpad=0.6)
# the boundary source is credited on the map itself, as the journal asks, and in the caption
# (in the blank north-west corner of the first map, where it covers no cell)
fig.axes[0].text(0.025, 0.965, "Boundaries:\ngeoBoundaries 2019", transform=fig.axes[0].transAxes,
                 ha="left", va="top", fontsize=S.SIZE_FLOOR, color=S.MUTED, zorder=6)
S.save(fig, "f04_gas_maps", str(OUT), str(PREVIEWS), SCRIPT,
       "Placed mass of CO2, CH4 and N2O on the 0.05 degree grid, fiscal year 2023-24")


# ================================================================ Figure 5: evidence by year
def stack_panel(ax, df, gas, letter, first):
    bottom = np.zeros(len(df))
    xs = np.arange(len(df))
    for _, label, colour in BASIS_ORDER:
        vals = df[label].values
        ax.bar(xs, vals, bottom=bottom, width=0.78, color=colour, hatch=BASIS_HATCH[label],
               edgecolor=S.PAPER, linewidth=0.6, zorder=3)
        dark = colour in ("#08306b", "#d94801", "#252525")
        for x, b, v in zip(xs, bottom, vals):
            if v >= 12.0:          # a label only where the segment can hold one
                ax.text(x, b + v / 2, "%.0f" % v, ha="center", va="center",
                        fontsize=S.SIZE_FLOOR, color=S.PAPER if dark else S.INK, zorder=4)
        bottom = bottom + vals
    ax.set_xticks(xs, [S.fiscal(p) if i % 4 == 0 else "" for i, p in enumerate(df.period_id)])
    ax.set_xlim(-0.6, len(df) - 0.4)
    ax.set_ylim(0, 100)
    ax.set_yticks([0, 25, 50, 75, 100], None if first else ["", "", "", "", ""])
    if first:
        ax.set_ylabel("Share of the gas's\nnational mass in the year (%)")
    S.quiet(ax, grid="y")
    S.panel(ax, letter, S.GAS_LABEL[gas])


fig = S.figure(S.FULL_WIDTH, 3.20)
left, width, gap = 0.098, 0.262, 0.050
for k, (gas, df) in enumerate((("CO2", basis_co2), ("CH4", basis_ch4), ("N2O", basis_n2o))):
    stack_panel(fig.add_axes([left + k * (width + gap), 0.345, width, 0.565]), df, gas,
                "abc"[k], k == 0)
# the province-retained class is in every bar and too thin to see: say how thin, from the data
_kept = max(float(d["Retained at province level"].max()) for d in (basis_co2, basis_ch4, basis_n2o))
_kept_note = " (at most %.1f %%)" % (np.ceil(_kept * 10) / 10)
fig.legend(handles=[Patch(facecolor=c, edgecolor=S.PAPER, hatch=BASIS_HATCH[l],
                          label=l + (_kept_note if code == "unallocated" else ""))
                    for code, l, c in BASIS_ORDER],
           loc="lower left", bbox_to_anchor=(left, 0.0), ncol=2, columnspacing=2.0,
           handletextpad=0.6, title="Evidence behind the spatial weight", alignment="left",
           title_fontsize=S.SIZE_TICK)
S.save(fig, "f05_spatial_evidence", str(OUT), str(PREVIEWS), SCRIPT,
       "Evidence class behind the spatial weight, by gas and fiscal year")


# ================================================================ Figure 6: surface; concentration
ref_proxy = {g: proxy[(proxy.gas == g) & (proxy.period_id == YEAR)].iloc[0] for g in GASES}
half = {g: int(np.searchsorted(conc[g][1], 0.5)) + 1 for g in GASES}

FIG6_H = 4.90
fig = S.figure(S.FULL_WIDTH, FIG6_H)
# (a) which surface carried the reference year's mass
ax = fig.add_axes([0.085, 0.785, 0.895, 0.150])
ys = np.arange(len(GASES))
edge = np.zeros(len(GASES))
for code, label, colour in PROXY_ORDER:
    vals = np.array([ref_proxy[g][label] for g in GASES])
    ax.barh(ys, vals, left=edge, height=0.62, color=colour, edgecolor=S.PAPER, linewidth=0.6,
            zorder=3)
    dark = code in ("points", "population", "manure", "builtup", "kept")
    for y, l_, v in zip(ys, edge, vals):
        if v >= 4.5:
            ax.text(l_ + v / 2, y, "%.0f" % v, ha="center", va="center", fontsize=S.SIZE_FLOOR,
                    color=S.PAPER if dark else S.INK, zorder=4)
    edge = edge + vals
ax.set_yticks(ys, [S.GAS_LABEL[g] for g in GASES])
ax.invert_yaxis()
ax.set_xlim(0, 100)
ax.set_xticks([0, 25, 50, 75, 100])
ax.set_xlabel("Share of the gas's national mass, %s (%%)" % S.fiscal(YEAR))
S.quiet(ax, keep=("bottom",))
S.panel(ax, "a", "Surface that placed the mass", x=-0.062)
fig.legend(handles=[Patch(facecolor=c, edgecolor=S.PAPER, label=l) for _, l, c in PROXY_ORDER],
           loc="upper left", bbox_to_anchor=(0.085, 0.690), ncol=3, columnspacing=1.4,
           handletextpad=0.6)

# (b) the whole curve on a linear axis: cells ranked from the highest mass
bx = fig.add_axes([0.085, 0.200, 0.385, 0.275])
for gas in GASES:
    fx, fy, _ = conc[gas]
    bx.plot(100 * fx, 100 * fy, color=S.GAS[gas], linestyle=S.GAS_DASH[gas], linewidth=S.LW_CURVE,
            zorder=3)
bx.plot([0, 100], [0, 100], color=S.RULE, linewidth=0.8, zorder=2)
bx.set_xlim(0, 100)
bx.set_ylim(0, 101)
bx.set_xticks([0, 25, 50, 75, 100])
bx.set_yticks([0, 25, 50, 75, 100])
bx.set_xlabel("Valid cells ranked from the highest mass\n(%% of %s cells)" % S.thousands(conc["CO2"][0].size))
bx.set_ylabel("Cumulative mass (%)")
S.quiet(bx, grid="both")
S.panel(bx, "b", "Concentration, all cells")
bx.text(62, 55, "Equal mass per cell", rotation=np.degrees(np.arctan2(0.275 * FIG6_H, 0.385 * S.FULL_WIDTH)),
        ha="center", va="top", fontsize=S.SIZE_TICK, color=S.MUTED, rotation_mode="anchor")

# (c) the same curves by number of cells, on a logarithmic axis that starts at one cell
cx = fig.add_axes([0.580, 0.200, 0.400, 0.275])
n_cells = conc["CO2"][0].size
for gas in GASES:
    fx, fy, _ = conc[gas]
    cx.plot(np.arange(1, n_cells + 1), 100 * fy, color=S.GAS[gas], linestyle=S.GAS_DASH[gas],
            linewidth=S.LW_CURVE, zorder=3)
    cx.plot([half[gas]], [100 * fy[half[gas] - 1]], marker="o", markersize=4.2, color=S.GAS[gas],
            markeredgecolor=S.PAPER, markeredgewidth=0.8, linestyle="none", zorder=4)
ref_x = np.logspace(0, np.log10(n_cells), 300)
cx.plot(ref_x, 100 * ref_x / n_cells, color=S.RULE, linewidth=0.8, zorder=2)
cx.set_xscale("log")
cx.set_xlim(1, n_cells)
cx.set_ylim(0, 101)
cx.set_xticks([1, 10, 100, 1000, 10000], ["1", "10", "100", S.thousands(1000), S.thousands(10000)])
cx.minorticks_off()
cx.set_yticks([0, 25, 50, 75, 100])
cx.set_xlabel("Number of cells ranked from the highest mass\n(logarithmic axis, from one cell)")
S.quiet(cx, grid="both")
S.panel(cx, "c", "Concentration, by number of cells")
fig.legend(handles=[Line2D([], [], color=S.GAS[g], linestyle=S.GAS_DASH[g], linewidth=S.LW_CURVE,
                           marker="o", markersize=4.2, markeredgecolor=S.PAPER,
                           label="%s; marker: half the mass, in %s cells"
                                 % (S.GAS_LABEL[g], S.thousands(half[g]))) for g in GASES]
           + [Line2D([], [], color=S.RULE, linewidth=0.8, label="Equal mass per cell")],
           loc="lower left", bbox_to_anchor=(0.085, 0.0), ncol=2, handlelength=2.6,
           columnspacing=2.0)
S.save(fig, "f06_proxy_concentration", str(OUT), str(PREVIEWS), SCRIPT,
       "Surface that placed the mass, and concentration of placed mass")


# ================================================================ declarations and companion data
u_year = unal[unal.period_id == YEAR]
u = {g: float(u_year[u_year.gas == g].emissions_Gg.sum()) for g in GASES}
u_mt = float(u_year.co2e_Mt_AR5.sum())          # all three gases together, on AR5
national = {g: float(ledger.loc[(ledger.period_id == YEAR) & (ledger.gas == g), "emissions_Gg"].sum())
            for g in GASES}
mods = sorted(ledger[(ledger.period_id == YEAR) & (ledger.status == "present")].module.unique())
terr = pd.read_csv(ADM2C, comment="#")
nterr = int((terr.unit_kind == "territory_unit").sum())
bsrc = json.load(open(BSRC))


def not_own(df, row):
    """The share placed by a weight that is NOT the period's own observed activity."""
    return 100.0 - df.iloc[row]["That year's observed activity"] - df.iloc[row]["Retained at province level"]


ref_not_own = {"CO2": not_own(basis_co2, -1), "CH4": not_own(basis_ch4, -1), "N2O": not_own(basis_n2o, -1)}
first_not_own = {"CO2": not_own(basis_co2, 0), "CH4": not_own(basis_ch4, 0), "N2O": not_own(basis_n2o, 0)}
zero_text = "; ".join("%s %s" % (g, "{:,}".format(map_facts[g]["zero_cells"])) for g in GASES)
below_text = "; ".join("%s %s" % (g, "{:,}".format(map_facts[g]["cells_below_lower_limit"])) for g in GASES)
# the vintages actually in use in the reference year, by mass, read from the product
_vint = ev[(ev.period_id == YEAR) & (ev.surface_vintage != "") & (ev.surface_vintage != "n/a")]
vintages = sorted(_vint.surface_vintage.unique())
later = sorted(v for v in vintages if "2026" in v)

paras = [
    ("WHAT THE MAPS ARE. ",
     "The map figure draws the released 0.05-degree annual grid for %s (release %s, the reference "
     "configuration), read and not recomputed. Each cell carries the mass emitted in it over the "
     "fiscal year, in Gg of the native gas: no GWP is applied, no CO2e is formed, and the value is "
     "not divided by cell area, so it is a mass and not a flux density. The cube's three spatial "
     "views (physical, origin, accounting) are disjoint and partition the mass, so a cell's value "
     "is their sum." % (S.fiscal(YEAR), S.release_version())),
    ("PERIOD. ",
     "%s is a Pakistani fiscal year, 1 July 2023 to 30 June 2024. It is not a calendar year and is "
     "not relabelled as one. The evidence figure runs the nine fiscal years %s to %s."
     % (S.fiscal(YEAR), S.fiscal(periods[0]), S.fiscal(periods[-1]))),
    ("SOURCES INCLUDED. ",
     "Every estimated source stream of the %d calculation modules: %s. F-gases, lime (2.A.2), LULUCF "
     "and commercial and institutional buildings are not estimated by this release and are "
     "therefore absent from the maps. Their absence is a coverage gap, not a zero."
     % (len(mods), ", ".join(mods))),
    ("THE MASS NOT ON THE MAPS. ",
     "%s Gg CO2 (%.5f Mt; %.2f%% of national CO2), with %.6f Gg CH4 and %.6f Gg N2O (the three "
     "gases together %.5f Mt CO2e on AR5), is domestic-aviation cruise, which has no native "
     "location below the province and is held at province level. It is the fifth class "
     "of the evidence figure and is not spread to make the maps close. The identity grid + "
     "unallocated = national stream ledger holds for all %d period-by-gas combinations; the worst "
     "residual is %.3f ppm of the ledger, which is float32 storage and not a disagreement."
     % ("{:,.2f}".format(u["CO2"]), u["CO2"] / 1000.0, 100 * u["CO2"] / national["CO2"],
        u["CH4"], u["N2O"], u_mt, len(periods) * len(GASES), worst)),
    ("PROJECTION, SCALE AND THE THREE STATES OF A CELL. ",
     "EPSG:4326 (WGS 84), drawn plate carree with the aspect set for latitude %.1f degrees N; no "
     "reprojection and no interpolation, so each native cell is drawn as itself. The lattice is "
     "equal-angle: a cell's area runs from 24.678 km2 at the northern edge to 28.298 km2 at the "
     "southern, which changes the apparent size of a cell and not its colour, because the "
     "quantity is a mass. The colour scale is logarithmic and separate for each gas, so equal "
     "colours on two maps are not equal masses. Its floor is the decade at or below the smallest "
     "of the cells that together hold 99.9 per cent of the gas's placed mass, and its ceiling the "
     "next of 1, 2 or 5 times a power of ten above the largest cell. Of the %s valid cells, those "
     "holding exactly zero mass (%s) are drawn in a neutral grey that is not on the scale, and "
     "those below the floor (%s), which together hold under 0.1 per cent of the mass, take one "
     "pale colour marked by the pointed end of the bar. A cell cut by the coast or the border "
     "holds only the mass of its in-country part. Cells outside every district carry no value "
     "and are left blank."
     % (MID_LAT, "{:,}".format(int(inside.sum())), zero_text, below_text)),
    ("BOUNDARY FRAME. ",
     "%s gbOpen PAK ADM1/ADM2, represented year 2019, release commit %s (%s; %s). The gridded "
     "frame includes the %d territory units of Gilgit-Baltistan and Azad Jammu and Kashmir, drawn dashed: "
     "they are inside the gridded frame and outside the national statistical tables, and several "
     "comparator products draw them differently, so a cell-by-cell comparison against those "
     "products is not like-for-like there. Districts carry the 2023 census vocabulary on 2019 "
     "geometry." % (bsrc["provider"], bsrc["release_commit"], bsrc["citation"], bsrc["license"], nterr)),
    ("WHAT SUPPORTS THE PLACEMENT. ",
     "No cell is an observation. In the reference year %.0f%% of CO2, %.0f%% of CH4 and %.0f%% of "
     "N2O are placed by a weight that is not that year's own observed activity; in %s those "
     "shares are %.0f%%, %.0f%% and %.0f%%. The surfaces in use in the reference year are: %s. "
     "A surface's vintage is not a measure of its error, and not every surface predates the year "
     "it places: %s. Per-cell uncertainty is deliberately not stored: within a category the "
     "parametric error is perfectly correlated, so a per-cell standard deviation would invite "
     "addition in quadrature and understate every aggregate."
     % (ref_not_own["CO2"], ref_not_own["CH4"], ref_not_own["N2O"], S.fiscal(periods[0]),
        first_not_own["CO2"], first_not_own["CH4"], first_not_own["N2O"], "; ".join(vintages),
        "; ".join(later) + (" postdate" if len(later) > 1 else " postdates") + " every period"
        if later else "none is later than the reference year")),
    ("CONCENTRATION. ",
     "The concentration curves rank all %s valid cells of the reference year from the highest mass, "
     "zero-valued cells included. Half of the placed mass sits in %s cells for CO2, %s for CH4 "
     "and %s for N2O. These counts belong to this grid, this mask and this allocation: a finer "
     "display grid would add no evidence about where sources are."
     % ("{:,}".format(int(inside.sum())), "{:,}".format(half["CO2"]), "{:,}".format(half["CH4"]),
        "{:,}".format(half["N2O"]))),
]


def _tex_escape(text):
    """LaTeX-safe. A per cent sign starts a comment, and these paragraphs are full of them: an
    unescaped one would silently drop the rest of its line."""
    for a, b in (("\\", "\\textbackslash{}"), ("%", "\\%"), ("_", "\\_"),
                 ("&", "\\&"), ("#", "\\#"), ("$", "\\$"), ("–", "--")):
        text = text.replace(a, b)
    return text


_prov = [
    "%% GENERATED by scripts/make_fig_ghg_grid.py. Do not edit: the edit is overwritten.",
    "%% The provenance of the gridded figures, as prose.",
    "\\newcommand{\\GridProvenance}{%",
]
for head, body in paras:
    _prov.append("\\par\\smallskip\\noindent\\textbf{%s}%s"
                 % (_tex_escape(head.strip()), _tex_escape(" " + body.strip())))
_prov.append("}")
(OUT / "fig_ghg_grid_provenance.tex").write_text("\n".join(_prov) + "\n", encoding="utf-8")

rr, cc = np.where(inside)
pd.DataFrame({
    "lat": lat[rr], "lon": lon[cc],
    "lat_south": lat_b[rr, 0], "lat_north": lat_b[rr, 1],
    "lon_west": lon_b[cc, 0], "lon_east": lon_b[cc, 1],
    "cell_area_km2": cell_area[rr, cc],
    "pakistan_fraction": pak_frac[rr, cc],
    "co2_Gg": co2[rr, cc], "ch4_Gg": ch4[rr, cc], "n2o_Gg": n2o[rr, cc],
}).to_csv(OUT / "fig_ghg_grid_cells_fy2023_24.csv", index=False, lineterminator="\n")

pd.concat([basis_co2.assign(gas="CO2"), basis_ch4.assign(gas="CH4"), basis_n2o.assign(gas="N2O")],
          ignore_index=True).assign(classification="spatial_time_basis",
                                    denominator="the gas's national ledger mass in the period, province-retained mass included"
                                    ).to_csv(OUT / "fig_ghg_grid_evidence.csv", index=False,
                                             lineterminator="\n")
proxy.assign(classification="surface group",
             denominator="the gas's national ledger mass in the period, province-retained mass included"
             ).to_csv(OUT / "fig_ghg_grid_proxy.csv", index=False, lineterminator="\n")
# the surface-to-group mapping and each surface's vintage, so the grouping can be undone
(surf[surf.period_id == YEAR].groupby(["gas", "proxy_group", "surface", "surface_vintage"], dropna=False)
   .emissions_Gg.sum().reset_index()
   .to_csv(OUT / "fig_ghg_grid_proxy_surfaces.csv", index=False, lineterminator="\n"))

crows = []
for name in GASES:
    fx, fy, v = conc[name]
    for frac in (0.1, 0.25, 0.5, 0.8, 0.9, 0.95, 0.99, 1.0):
        n = min(int(np.searchsorted(fy, frac - 1e-12)) + 1, v.size)
        crows.append({"gas": name, "mass_fraction": frac, "cells": n,
                      "share_of_valid_cells_pct": 100 * n / fx.size,
                      "threshold_Gg": float(v[n - 1])})
pd.DataFrame(crows).to_csv(OUT / "fig_ghg_grid_concentration.csv", index=False, lineterminator="\n")

json.dump({
    "figures": ["f04_gas_maps.pdf", "f05_spatial_evidence.pdf", "f06_proxy_concentration.pdf"],
    "built_by": SCRIPT,
    "release_version": str(ds.attrs.get("release_version")),
    "configuration_id": str(ds.attrs.get("configuration_id")),
    "grid_spec_id": str(ds.attrs.get("grid_spec_id")),
    "period_plotted": YEAR,
    "period_basis": "Pakistani fiscal year 1 July - 30 June; not a calendar year",
    "quantity": "per-cell mass of the native gas over the fiscal year",
    "unit": "Gg (gas mass), NOT Gg/km2 and NOT CO2e",
    "gwp_applied_to_the_maps": "none",
    "projection": "EPSG:4326 WGS 84, plate carree, aspect set at the mid-latitude, no reprojection",
    "mid_latitude_deg_N": MID_LAT,
    "area_convention": "equal-angle 0.05 deg lattice; cell_area 24.678-28.298 km2; no area normalisation because the quantity is a mass",
    "colour_scale": "viridis reversed (dark = high), logarithmic, separate per gas; floor at the decade at or below the smallest cell among those holding 99.9 % of placed mass; ceiling at the next 1-2-5 step above the largest cell; cells below the floor in one pale colour",
    "maps": map_facts,
    "spatial_views_summed": ["physical", "origin", "accounting"],
    "in_country_cells": int(inside.sum()),
    "lattice_cells": int(inside.size),
    "boundary_frame": bsrc,
    "territory_units_in_frame": nterr,
    "modules_included": mods,
    "not_estimated_and_therefore_absent": ["F-gases", "lime 2.A.2", "LULUCF",
                                           "commercial and institutional buildings"],
    "unallocated_not_on_map": {
        "co2_Gg": u["CO2"], "co2_Mt": u["CO2"] / 1000.0, "ch4_Gg": u["CH4"], "n2o_Gg": u["N2O"],
        "co2e_Mt_AR5": u_mt, "co2e_Mt_AR5_is": "all three gases, CH4 at its fossil GWP",
        "reason": "domestic-aviation cruise: no native location below the province",
        "treatment": "carried as its own class in the evidence figure; never spread",
    },
    "national_ledger_Gg": national,
    "reference_year_share_not_own_activity_pct": ref_not_own,
    "half_mass_cells": half,
    "concentration_population": "all valid cells of the reference year, zero-valued cells included, summed in float64",
    "surface_vintages_in_use": vintages,
    "closure_identity": "grid + unallocated == national stream ledger, per period and gas",
    "closure_worst_residual_ppm": float(worst),
    "closure_detail": checks,
    "input_digests": {str(p.relative_to(REPO)): digest(p)
                      for p in (CUBE, LEDGER, WEIGHTS, UNALLOC, ADM1, ADM2C)},
}, open(OUT / "fig_ghg_grid_provenance.json", "w"), indent=2)

print("worst closure residual: %.4f ppm of the ledger" % worst)
print("reference-year share not placed by the year's own activity: %s"
      % ", ".join("%s %.1f%%" % (g, ref_not_own[g]) for g in GASES))
print("half-mass cells: %s" % ", ".join("%s %s" % (g, half[g]) for g in GASES))
print("wrote f04, f05, f06 and their companion files")
