"""Figures for the manuscripts, generated from the engine's own outputs.

WHY THIS IS ONE MODULE AND NOT NINE. Until now exactly one sector could draw anything:
agriculture, through five matplotlib modules of its own. The other eight had no plotting
code at all, which is why no non-agriculture manuscript could exist - a paper needs
figures and there were none to include.

They do not need eight modules. Every sector writes the same shaped CSVs by contract -
`<sector>_by_stream_<year>.csv`, `_provincial_<year>.csv`, `_timeseries_<year>.csv` - so
one reader that understands that contract can draw all of them. Agriculture predates the
contract and uses different filenames, so it is mapped explicitly rather than special-cased
in the drawing code.

EVERY FIGURE IS DERIVED, NEVER TYPED. Each function reads a CSV that the engine wrote and
draws exactly what is in it. Nothing here recomputes an emission, applies a factor, or
carries a number of its own - which is what lets tests/paper_numbers/ compare a
figure byte-for-byte against its source and lets a reviewer trace any pixel back to a run.

Output goes to outputs/figures/, and scripts/sync_figures.py copies into each manuscript's
figures/ directory. That indirection exists so a manuscript never reads outputs/ directly:
the paper ships the figure it was written against, and the sync step is what makes staleness
visible instead of silent.

Usage:  python3 -m pkinv.report.figures
"""

from pkinv.assets import asset_path
import csv
import os
import re
from collections import defaultdict

from pkinv.core.gwp import GWP
from pkinv.paths import OUTPUTS
from pkinv.activity.store import read_rows

FIGDIR = asset_path(OUTPUTS, "figures")
DPI = 150

# Sector -> (by_stream, provincial, timeseries) basenames. None where the sector has none.
# Agriculture predates the naming contract and keeps its own filenames.
SECTOR_FILES = {
    # No timeseries entry: outputs/timeseries_1990_2024.csv IS produced in this
    # repository (sectors/agriculture/timeseries.py) but its trend figure is
    # rendered by the agriculture pipeline itself, not by this module's
    # sector_timeseries path - listing the filename here once made
    # sector_timeseries render a duplicate from before that split.
    "agriculture": ("by_category.csv", "provincial_totals_2024.csv", None),
    "waste": ("waste_by_stream_2023.csv", "waste_provincial_2023.csv", None),
    "aviation": ("aviation_by_stream_fy2023_24.csv", "aviation_provincial_fy2023_24.csv",
                 "aviation_timeseries_2006_fy2023_24.csv"),
    "power": ("power_by_stream_fy2023_24.csv", "power_provincial_fy2023_24.csv",
              "power_timeseries_fy2023_24.csv"),
    "transport": ("transport_by_stream_2022.csv", "transport_provincial_2022.csv", None),
    "railways": ("railways_by_stream_2024.csv", "railways_provincial_2024.csv",
                 "railways_timeseries_2024.csv"),
    "fugitives": ("fugitives_by_stream_2024.csv", "fugitives_provincial_2024.csv",
                  "fugitives_timeseries_2011_2025.csv"),
    "residential": ("residential_by_stream_2024.csv", "residential_provincial_2024.csv",
                    None),
    "ippu": ("ippu_by_stream_2024.csv", "ippu_provincial_2024.csv", None),
}

# The <sector>_totals_*.csv every sector writes carries its published sensitivities as rows
# whose category begins "Sensitivity:". A paper needs those as a figure, because a range the
# reader has to reconstruct from prose is a range they will not reconstruct. One entry per
# sector rather than one function per sector.
TOTALS_FILES = {
    "waste": "waste_totals_2023.csv", "power": "power_totals_fy2023_24.csv",
    "transport": "transport_totals_2022.csv", "residential": "residential_totals_2024.csv",
    "ippu": "ippu_totals_2024.csv",
    "railways": "railways_totals_2024.csv", "aviation": "aviation_totals_fy2023_24.csv",
}

# Activity composition: the physical quantity each sector burns, treats or produces, before
# any emission factor is applied. Separating activity from emissions is what lets a reader see
# that a fuel can be a third of the energy and a tenth of the emissions.
ACTIVITY_FILES = {
    "power": ("power_fuel_fy2023_24.csv", "fuel", "TJ", "Fuel input (TJ)"),
    "transport": ("transport_fuel_2022.csv", "fuel", "TJ", "Fuel supplied (TJ)"),
    "residential": ("residential_fuel_2024.csv", "stream", "TJ", "Household fuel (TJ)"),
    "railways": ("railways_fuel_2024.csv", "stream", "TJ", "Traction fuel (TJ)"),
}

# How much assurance each air-pollutant layer carries. The layers are NOT comparable: two of
# the seven are bounds or screening estimates and two large sources have none at all, so a bar
# chart that draws them all the same way invites a ranking the evidence does not support.
# tests/paper_numbers/ asserts these classes are the ones the manuscript's beta table
# prints, so the figure and the table cannot drift apart.
AIR_ASSURANCE = {
    "residential": "estimated", "agriculture": "estimated", "waste": "estimated",
    "railways": "estimated", "transport": "Tier 1", "power": "uncontrolled bound",
    "aviation": "LTO screening", "industry": "provisional estimate",
    "ippu": "provisional estimate", "fugitives": "provisional estimate",
}

# Each sector's air-pollutant layer, where it has one. The year is resolved at read time -
# see resolve().
AIR_FILES = {
    "agriculture": "air_pollutants_2024.csv", "waste": "waste_air_pollutants_2023.csv",
    "transport": "transport_air_pollutants_2022.csv",
    "residential": "residential_air_pollutants_2024.csv",
    "power": "power_air_pollutants_fy2023_24.csv",
    "aviation": "aviation_air_pollutants_fy2023_24.csv",
    "railways": "railways_air_pollutants_2024.csv",
}

# A single palette so a category keeps its colour across every figure in every manuscript.
# Chosen to stay distinguishable in greyscale print, which most of these journals still are.
PALETTE = ["#2b6a99", "#c1553b", "#4f8f5b", "#8a6fa8", "#c9a227", "#5b8fa8",
           "#a4553b", "#6f8f4f", "#8a5b8a", "#7a7a7a"]


def _plt():
    """Import matplotlib lazily so the engine keeps running without it."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


class MissingOutput(Exception):
    """A figure's declared source is not in outputs/."""


def resolve(name):
    """The output file a declared basename means, with the year resolved at read time.

    WHY THE YEAR IS NOT DECLARED. These tables used to name files outright -
    `waste_by_stream_2023.csv`, `transport_fuel_2022.csv`. When the harmonisation round put
    every sector on FY2023-24 the engine started writing `..._2024.csv` and the declarations
    kept pointing at files that no longer existed. `_read` returned None, the drawing
    functions returned None, and `outputs/figures/` simply stopped gaining a transport or
    waste figure - while the PNGs already sitting in each manuscript's figures/ directory went
    on looking current, because the currency test inspects manuscript directories and cannot
    see a figure that was never redrawn. Two manuscripts shipped pre-harmonisation figures.

    So the year is matched rather than declared: `waste_by_stream` resolves to whichever
    `waste_by_stream_<year>.csv` the engine wrote. The tail must be years and nothing else, or
    `transport_fuel` would also match `transport_fuel_bridge_2024.csv`.

    Absence RAISES. A figure whose source has gone is a defect, and the previous behaviour -
    return None, draw nothing, keep the stale PNG - is precisely how it stayed invisible.
    """
    path = asset_path(OUTPUTS, name)
    if os.path.exists(path):
        return name
    # (?:fy|cy)? since rc15: the fiscal-start sectors' outputs carry the PERIOD
    # (power_totals_fy2023_24.csv), not a bare year, and a resolver that cannot
    # see the new form raises MissingOutput on every power and aviation figure.
    stem = re.sub(r"_(?:fy|cy)?\d{4}(_\d{2,4})?\.csv$", "", name)
    if stem == name[:-4]:            # no year in the declaration: it meant that exact file
        raise MissingOutput("figure source %s is not in outputs/" % name)
    pattern = re.compile(r"^%s_(?:fy|cy)?\d{4}(_\d{2,4})?\.csv$" % re.escape(stem))
    found = sorted(f for f in os.listdir(OUTPUTS) if pattern.match(f))
    if len(found) == 1:
        return found[0]
    raise MissingOutput(
        "figure source %s is not in outputs/ and %s"
        % (name, "no %s_<year>.csv replaces it" % stem if not found
           else "several could: %s" % ", ".join(found)))


def _read(name):
    path = asset_path(OUTPUTS, resolve(name))
    return read_rows(path, comments=False)


def _run_note(rows, field="n_iter", noun="draw"):
    """Describe the run a figure is plotting, FROM the rows it plots.

    The national uncertainty figure carried the axis label "10,000-draw Monte Carlo" for a
    release after the published run went to 100,000. The caption above it, the section text
    and every row of the CSV it reads all said 100,000; only the label, typed once into this
    module, disagreed -- and nothing compared a figure's own words to its own data.

    Raising on an empty or inconsistent column is the point. A helper that quietly took the
    first row would restate whatever it was given and could never fail, which is the same
    kind of check-that-checks-nothing this repair exists to remove.
    """
    values = {str(r[field]).strip() for r in rows if str(r.get(field, "")).strip()}
    if len(values) != 1:
        raise ValueError("cannot describe the run: %r holds %d distinct values (%s)"
                         % (field, len(values), sorted(values)))
    return "{:,}-{}".format(int(float(values.pop())), noun)


def _num(row, *names):
    """First numeric field among `names`, so one reader handles the small header drift
    between sectors written at different times."""
    for n in names:
        if n in row and str(row[n]).strip():
            try:
                return float(row[n])
            except ValueError:
                continue
    return None


def _save(fig, name):
    os.makedirs(FIGDIR, exist_ok=True)
    # metadata Software=None drops the "Matplotlib version x.y.z" tEXt chunk the
    # Agg writer embeds by default - the one byte-source in a shipped PNG that
    # tracks the environment rather than the inventory (gap
    # figures-not-byte-reproducible). Pixels must answer to the pinned
    # requirements.lock; the chunk answered to whatever pip resolved.
    fig.savefig(asset_path(FIGDIR, name), dpi=DPI, bbox_inches="tight",
                metadata={"Software": None})
    _plt().close(fig)
    return name


def _style(ax):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="x", linestyle=":", linewidth=0.6, alpha=0.6)
    ax.set_axisbelow(True)


def sector_streams(sector):
    """Horizontal bar of a sector's streams, largest first. The composition figure."""
    fname = SECTOR_FILES.get(sector, (None, None, None))[0]
    rows = _read(fname) if fname else None
    if not rows:
        return None
    items = []
    for r in rows:
        label = r.get("subitem") or r.get("category") or ""
        value = _num(r, "co2e_Mt_AR5")
        if label and value:
            items.append((label, value))
    if not items:
        return None
    items.sort(key=lambda kv: kv[1])
    plt = _plt()
    fig, ax = plt.subplots(figsize=(7.2, max(2.4, 0.34 * len(items) + 1.0)))
    ax.barh([k for k, _v in items], [v for _k, v in items],
            color=PALETTE[0], edgecolor="white", linewidth=0.5)
    ax.set_xlabel("Mt CO$_2$e (AR5 GWP-100)")
    ax.set_title("%s: emissions by stream" % sector.capitalize(), loc="left", fontsize=11)
    _style(ax)
    return _save(fig, "%s_streams.png" % sector)


def sector_provincial(sector):
    """Provincial allocation. The figure that shows a proxy doing its work."""
    fname = SECTOR_FILES.get(sector, (None, None, None))[1]
    rows = _read(fname) if fname else None
    if not rows:
        return None
    items = [(r.get("province", ""), _num(r, "co2e_Mt_AR5", "TOTAL")) for r in rows]
    items = [(k, v) for k, v in items if k and v is not None and k.upper() != "TOTAL"]
    if not items:
        return None
    plt = _plt()
    fig, ax = plt.subplots(figsize=(6.0, 3.0))
    ax.bar([k for k, _v in items], [v for _k, v in items],
           color=PALETTE[1], edgecolor="white", linewidth=0.5)
    ax.set_ylabel("Mt CO$_2$e")
    ax.set_title("%s: provincial allocation" % sector.capitalize(), loc="left", fontsize=11)
    ax.tick_params(axis="x", labelrotation=20)
    for label in ax.get_xticklabels():
        label.set_horizontalalignment("right")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", linestyle=":", linewidth=0.6, alpha=0.6)
    ax.set_axisbelow(True)
    return _save(fig, "%s_provincial.png" % sector)


def sector_timeseries(sector):
    """Multi-year series, for the four sectors that have one plus agriculture."""
    fname = SECTOR_FILES.get(sector, (None, None, None))[2]
    rows = _read(fname) if fname else None
    if not rows:
        return None
    series = []
    for r in rows:
        year = _num(r, "fiscal_year", "year")
        value = _num(r, "mt_co2e_AR5", "co2e_Mt_AR5",
                     "legacy_2006_production_mt_co2e_ar5")
        if value is None:
            # Aviation reports its series in kt; everything else is in Mt.
            kt = _num(r, "domestic_kt_co2e_AR5")
            value = kt / 1000.0 if kt is not None else None
        if year and value is not None:
            series.append((int(year), value))
    if len(series) < 2:
        return None
    series.sort()
    if sector == "agriculture":
        # The agriculture series is per category and per year; keep the TOTAL rows only.
        totals = {}
        for r in rows:
            if (r.get("category") or "").upper() == "TOTAL":
                y = _num(r, "year")
                v = _num(r, "co2e_Mt_AR5")
                if y and v is not None:
                    totals[int(y)] = v
        if len(totals) >= 2:
            series = sorted(totals.items())
    plt = _plt()
    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    ax.plot([y for y, _v in series], [v for _y, v in series],
            marker="o", markersize=3.5, linewidth=1.6, color=PALETTE[0])
    ax.set_ylabel("Mt CO$_2$e")
    ax.set_xlabel("Fiscal year")
    ax.set_title("%s: reported series" % sector.capitalize(), loc="left", fontsize=11)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(linestyle=":", linewidth=0.6, alpha=0.6)
    ax.set_axisbelow(True)
    return _save(fig, "%s_timeseries.png" % sector)


def sector_sensitivity(sector):
    """The sector's published sensitivities against its reference estimate.

    Every sector that has an assumption it cannot settle reports the alternatives as rows in
    its totals file rather than choosing quietly - the clinker ratio, the sewer MCF, the coal
    blend, the firewood volume, the captive heating value. This draws them as a range around
    the reported figure, which is the honest shape of those results.
    """
    fname = TOTALS_FILES.get(sector)
    rows = _read(fname) if fname else None
    if not rows:
        return None
    central, items = None, []
    for r in rows:
        cat = (r.get("category") or "").strip()
        val = _num(r, "co2e_Mt_AR5")
        if val is None or not cat:
            continue
        if cat.startswith("Sensitivity:"):
            items.append((cat.split(":", 1)[1].strip(), val))
        elif cat == "TOTAL" or central is None:
            central = val if cat == "TOTAL" else central or val
    if not items or central is None:
        return None
    items.sort(key=lambda kv: kv[1])
    plt = _plt()
    fig, ax = plt.subplots(figsize=(6.6, 0.5 * len(items) + 1.4))
    ys = range(len(items))
    ax.barh(list(ys), [v for _k, v in items], color=PALETTE[5], edgecolor="white",
            linewidth=0.5)
    ax.axvline(central, color=PALETTE[1], lw=1.6, zorder=3)
    ax.annotate("reported %.2f" % central, (central, len(items) - 0.35),
                textcoords="offset points", xytext=(5, 0), fontsize=8.5, color=PALETTE[1])
    ax.set_yticks(list(ys))
    ax.set_yticklabels([k[:46] for k, _v in items], fontsize=8)
    ax.set_xlabel("Mt CO$_2$e (AR5)")
    ax.set_title("What the unsettled assumptions are worth", loc="left", fontsize=11)
    _style(ax)
    return _save(fig, "%s_sensitivity.png" % sector)


def sector_activity(sector):
    """Activity composition - the physical quantity, before any factor is applied."""
    spec = ACTIVITY_FILES.get(sector)
    rows = _read(spec[0]) if spec else None
    if not rows:
        return None
    _f, keycol, valcol, xlabel = spec
    items = [(r[keycol], _num(r, valcol)) for r in rows
             if r.get(keycol) and _num(r, valcol) is not None]
    items = [(k, v) for k, v in items if v > 0]
    if len(items) < 2:
        return None
    items.sort(key=lambda kv: kv[1])
    total = sum(v for _k, v in items)
    plt = _plt()
    fig, ax = plt.subplots(figsize=(6.6, 0.45 * len(items) + 1.3))
    ax.barh([k for k, _v in items], [v for _k, v in items], color=PALETTE[0],
            edgecolor="white", linewidth=0.5)
    for i, (_k, v) in enumerate(items):
        ax.annotate("%.0f%%" % (100 * v / total), (v, i), textcoords="offset points",
                    xytext=(5, -3), fontsize=8.5)
    ax.set_xlabel(xlabel)
    ax.set_title("Activity composition", loc="left", fontsize=11)
    _style(ax)
    return _save(fig, "%s_activity.png" % sector)


def sector_air(sector):
    """The sector's air-pollutant layer, mass only, log scale.

    Log because these span three orders of magnitude within one sector - carbon monoxide in
    the thousands of kilotonnes against black carbon in the tens - and a linear axis renders
    everything except the largest as a line of zero width.
    """
    fname = AIR_FILES.get(sector)
    rows = _read(fname) if fname else None
    if not rows:
        return None
    # Subset metrics are excluded from the bars: PM2.5 is contained in PM10 is
    # contained in TSP, so plotting all three beside each other double-counts
    # visually, and the residential pair is coal-only anyway (the paper's air table
    # promises their exclusion; they live in the factor appendix and the matrix).
    # transport since the EMEP Tier 1 refactor: the wear strata (TSP, PM10) are
    # supplemental beside the PM2.5 core, same containment, same exclusion
    exclude = {"PM10", "TSP"} if sector in ("residential", "transport") else set()
    totals = {}
    for r in rows:
        pol = (r.get("pollutant") or "").strip()
        v = _num(r, "emissions_kt")
        if pol and pol not in exclude and v is not None:
            totals[pol] = totals.get(pol, 0.0) + v
    items = sorted(((k, v) for k, v in totals.items() if v > 0), key=lambda kv: kv[1])
    if len(items) < 2:
        return None
    plt = _plt()
    fig, ax = plt.subplots(figsize=(6.6, 0.42 * len(items) + 1.3))
    ax.barh([k for k, _v in items], [v for _k, v in items], color=PALETTE[2],
            edgecolor="white", linewidth=0.5)
    ax.set_xscale("log")
    for i, (_k, v) in enumerate(items):
        label = ("%.2g t" % (v * 1000.0)) if v < 0.1 else ("%.3g kt" % v)
        ax.annotate(label, (v, i), textcoords="offset points", xytext=(5, -3),
                    fontsize=8.5)
    ax.set_xlabel("kt/yr (log scale)")
    ax.set_title("Air-pollutant co-emissions", loc="left", fontsize=11)
    _style(ax)
    return _save(fig, "%s_air.png" % sector)


def waste_partition():
    """The exhaustive partition, which is the waste paper's central claim.

    Deliberately bespoke rather than generic: no other sector splits one activity figure
    across two categories, and the point of the figure is that the two bars beneath the
    generation bar sum to it exactly. A stacked bar makes that visible in a way a table of
    three numbers does not.
    """
    from pkinv.sectors.waste import open_burning, swds
    from pkinv.sectors.waste.data import WasteData
    d = WasteData()
    gen = swds.waste_generated(d) / 1e6
    disposed = swds.waste_disposed(d) / 1e6
    uncollected = gen - disposed
    burnt = open_burning.waste_burnt(d) / 1e6
    plt = _plt()
    fig, ax = plt.subplots(figsize=(6.6, 2.4))
    ax.barh(["Generated"], [gen], color=PALETTE[6], edgecolor="white", linewidth=0.5)
    ax.barh(["Fate"], [disposed], color=PALETTE[0], edgecolor="white", linewidth=0.5,
            label="Collected to disposal (4A)")
    ax.barh(["Fate"], [burnt], left=disposed, color=PALETTE[1], edgecolor="white",
            linewidth=0.5, label="Uncollected and burned (4C2)")
    ax.barh(["Fate"], [uncollected - burnt], left=disposed + burnt, color="#c9c9c9",
            edgecolor="white", linewidth=0.5, label="Uncollected, not burned")
    for x, lab in ((gen, "%.2f" % gen),):
        ax.annotate(lab, (x, 1), textcoords="offset points", xytext=(5, -3), fontsize=8.5)
    ax.annotate("%.2f" % disposed, (disposed / 2, 0), ha="center", va="center",
                fontsize=8.5, color="white")
    ax.annotate("%.2f" % burnt, (disposed + burnt / 2, 0), ha="center", va="center",
                fontsize=8.5, color="white")
    ax.set_xlabel("Mt of municipal solid waste per year")
    ax.set_title("One generation figure, partitioned exhaustively", loc="left", fontsize=11)
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    _style(ax)
    return _save(fig, "waste_partition.png")


def national_sectors():
    """The nine sectors that make the national total, with their Approach-1 bands."""
    rows = _read("national_all_sectors.csv")
    if not rows:
        return None
    items = [(r["sector"], float(r["co2e_Mt_AR5"]), float(r["uncert_pct_95"]))
             for r in rows if r["row_kind"] == "sector"]
    items.sort(key=lambda t: t[1])
    plt = _plt()
    fig, ax = plt.subplots(figsize=(7.2, 4.0))
    names = [k for k, _v, _u in items]
    values = [v for _k, v, _u in items]
    # The band is a relative percentage, so it is drawn as an absolute error bar. The
    # fugitives bar runs off the axis by design - a 311% band is the honest width.
    errs = [v * u / 100.0 for _k, v, u in items]
    ax.barh(names, values, color=PALETTE[0], edgecolor="white", linewidth=0.5)
    ax.errorbar(values, range(len(names)), xerr=errs, fmt="none",
                ecolor="#444444", elinewidth=1.0, capsize=3)
    ax.set_xlabel("Mt CO$_2$e (AR5 GWP-100), Approach-1 95% band")
    ax.set_title("Pakistan national inventory by sector", loc="left", fontsize=11)
    ax.set_xlim(left=0)
    _style(ax)
    return _save(fig, "national_sectors.png")


def national_key_categories():
    """Level against variance share - the figure that carries the finding.

    A category far below the diagonal is large and well constrained; far above it is small
    and uncertain. Effort belongs above the line, not to the right of it.
    """
    rows = _read("national_key_categories.csv")
    if not rows:
        return None
    plt = _plt()
    fig, ax = plt.subplots(figsize=(7.0, 5.2))
    pts = sorted([(float(r["level_pct"]), float(r["variance_share_pct_independent_approx"]),
                   r["category"], r["key_by_level"] == "YES") for r in rows],
                 key=lambda t: -t[0])

    # Points are NUMBERED rather than labelled in place. Ten of the seventeen categories
    # sit inside a few percent of each other in the low corner, and any in-place labelling
    # either overlaps or trails leader lines off the axes. A numbered key is the honest
    # way to keep every category visible without moving anything.
    floor_pts = [p for p in pts if p[1] <= 0]
    for i, (x, y, _label, key) in enumerate(pts, start=1):
        y = max(y, 0.004)                      # a log axis has no zero; the key says which
        ax.scatter(x, y, s=120 if key else 70,
                   color=PALETTE[0] if key else "#aaaaaa",
                   edgecolor="white", linewidth=0.8, zorder=3)
        ax.annotate(str(i), (x, y), ha="center", va="center", fontsize=6.5,
                    color="white", zorder=4, fontweight="bold")

    # LOG-LOG, because the linear version was unreadable and said so. Enteric fermentation is
    # 34 percent of the total and 61 percent of the variance; eleven of the eighteen categories
    # sit below 4 percent on both axes and were compressed into a single blot near the origin,
    # which is where the figure's actual finding lives. On log axes the diagonal still means
    # "level share equals variance share", so the reading is unchanged and the low corner is
    # legible. Zero-variance categories are drawn at the floor and marked in the key.
    floor = 0.004
    lo = min(min(p[0] for p in pts), min(p[1] for p in pts if p[1] > 0)) * 0.5
    lo = max(lo, floor)
    hi = max(max(p[0] for p in pts), max(p[1] for p in pts)) * 1.6
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.plot([lo, hi], [lo, hi], linestyle="--", linewidth=0.9, color="#bbbbbb", zorder=1)
    ax.annotate("above this line: more uncertain than large",
                (lo * 2.2, lo * 3.4), fontsize=7.5, color="#999999", rotation=38,
                ha="left", va="bottom")

    key_text = "\n".join(
        "%2d  %s%s" % (i, label, " *" if v <= 0 else "")
        for i, (_x, v, label, _k) in enumerate(pts, start=1))
    if floor_pts:
        key_text += "\n\n * variance share below 0.005%,\n   drawn at the axis floor"
    fig.subplots_adjust(right=0.60)
    fig.text(0.63, 0.94, "Categories, largest first", fontsize=8, va="top",
             fontweight="bold")
    fig.text(0.63, 0.895, key_text, fontsize=7.2, va="top", family="DejaVu Sans Mono",
             linespacing=1.5)

    ax.set_xlabel("Share of the national total (%, log scale)")
    ax.set_ylabel("Share of the national variance (%, log scale)")
    ax.set_title("Being large is not being uncertain", loc="left", fontsize=11)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(linestyle=":", linewidth=0.6, alpha=0.6)
    ax.set_axisbelow(True)
    return _save(fig, "national_key_categories.png")


def national_structural_bridge():
    """What the conditional interval leaves out, as a bridge from the baseline total.

    Each bar is one named structural alternative's deterministic effect on the national total.
    They are NOT summable and NOT a distribution: two of the power axes describe the same coal
    energy in different ways and cannot both be taken. Drawn because the +/-11 percent
    parametric interval is narrower than several of these single choices, and a reader given
    only the interval has no way to see that.
    """
    all_rows = _read("national_structural_bridge.csv")
    rows = [r for r in all_rows if r["national_delta_Mt_co2e"]]
    # The unpriced axes stay VISIBLE (rc14, the ninth review): the caption said
    # the figure "prices each one" while this filter silently dropped the
    # transport retail non-road row - an unpriced axis is a fact to draw, not a
    # row to hide.
    unpriced = [r for r in all_rows if not r["national_delta_Mt_co2e"]]
    if not rows:
        return None
    baseline = float(rows[0]["national_total_Mt_co2e"]) - float(
        rows[0]["national_delta_Mt_co2e"])
    rows.sort(key=lambda r: float(r["national_delta_Mt_co2e"]))
    labels = ["%s (%s)" % (r["axis"], r["module"]) for r in rows] +              ["%s (%s) - UNPRICED" % (r["axis"], r["module"]) for r in unpriced]
    deltas = [float(r["national_delta_Mt_co2e"]) for r in rows] +              [0.0 for _ in unpriced]
    plt = _plt()
    fig, ax = plt.subplots(figsize=(7.0, 3.6))
    ax.barh(labels, deltas,
            color=[PALETTE[1] if d < 0 else PALETTE[2] for d in deltas],
            edgecolor="white", linewidth=0.5)
    n_priced = len(rows)
    for i, d in enumerate(deltas):
        if i >= n_priced:
            ax.annotate("no published alternative - priced as a cross-sector "
                        "transfer (axis register)", (0, i),
                        textcoords="offset points", xytext=(6, -3), fontsize=7,
                        ha="left", color="#777777", style="italic")
            continue
        ax.annotate("%+.1f  (%.0f Mt)" % (d, baseline + d), (d, i),
                    textcoords="offset points",
                    xytext=(6 if d > 0 else -6, -3), fontsize=8,
                    ha="left" if d > 0 else "right")
    span = max(abs(min(deltas)), abs(max(deltas)))
    ax.set_xlim(-span * 1.55, span * 1.55)
    ax.axvline(0.0, color="#222222", linewidth=1.0)
    ax.set_xlabel("Change in the national total, Mt CO$_2$e (AR5), from %.2f Mt" % baseline)
    ax.set_title("Named structural alternatives, one at a time", loc="left", fontsize=11)
    ax.annotate("Not additive and not a distribution: these are alternative readings of "
                "evidence, not draws.", (0, -0.22), xycoords="axes fraction", fontsize=8,
                color="#555555")
    _style(ax)
    return _save(fig, "national_structural_bridge.png")


def national_series():
    """The nine-year series in BOTH published views, drawn so the difference
    between them is the visible fact: the full-scope line rises where sectors
    ENTER the record, the common-scope line only where emissions move."""
    series = _read("pakemis_national_series.csv")
    annual = _read("pakemis_annual_fy2015_16_fy2023_24.csv")
    if not series or not annual:
        return None
    full = {r["period_label"]: float(r["co2e_Mt_AR5"])
            for r in series if r["row_kind"] == "covered_total"}
    common = {}
    for r in annual:
        if r["harmonized_common_scope"] != "yes" or not r["co2e_Mt_AR5"]:
            continue
        common[r["period_label"]] = (common.get(r["period_label"], 0.0)
                                     + float(r["co2e_Mt_AR5"]))
    labels = sorted(full)
    plt = _plt()
    fig, ax = plt.subplots(figsize=(7.0, 3.2))
    ax.plot(labels, [full[k] for k in labels], marker="o", color=PALETTE[0],
            linewidth=1.6, label="best available, full scope (10 sectors)")
    ck = [k for k in labels if k in common]
    ax.plot(ck, [common[k] for k in ck], marker="s", color=PALETTE[2],
            linewidth=1.6, linestyle="--",
            label="constant sector scope (8 sectors, FY2016-17 on)")
    ax.set_ylabel("Mt CO$_2$e (AR5)")
    ax.set_title("The national series in two views, FY2015-16 to FY2023-24",
                 loc="left", fontsize=11)
    ax.annotate("The full-scope line rises partly because SECTORS ENTER the record: the "
                "sectors present at FY2015-16 carry 84.7% of the reference year's MASS "
                "(not 84.7% of its\nemissions). Only the constant-scope line may be "
                "differenced, and it carries a declared livestock-basis step.",
                (0, -0.30), xycoords="axes fraction", fontsize=8, color="#555555")
    ax.legend(fontsize=8, frameon=False)
    for lab in ax.get_xticklabels():
        lab.set_rotation(45)
        lab.set_ha("right")
    _style(ax)
    return _save(fig, "national_series.png")


def national_uncertainty():
    """The two Monte-Carlo scenarios side by side; the gap between them is the point."""
    rows = _read("national_uncertainty_montecarlo.csv")
    if not rows:
        return None
    nat = {r["scenario"]: r for r in rows if r["scope"] == "national"}
    if len(nat) < 2:
        return None
    plt = _plt()
    fig, ax = plt.subplots(figsize=(7.0, 2.1))
    order = ["within_sector", "cross_sector"]
    labels = {"within_sector": "Parameters shared within a module",
              "cross_sector": "Shared by physical identity across modules"}
    for i, key in enumerate(order):
        r = nat[key]
        lo, mid, hi = (float(r["P2.5_Mt"]), float(r["P50_Mt"]), float(r["P97.5_Mt"]))
        ax.plot([lo, hi], [i, i], linewidth=6, solid_capstyle="butt",
                color=PALETTE[i], alpha=0.85)
        ax.plot([mid], [i], marker="|", markersize=18, color="#222222")
        ax.annotate("%.0f-%.0f Mt  (+/- %.1f%%)"
                    % (lo, hi, float(r["rel_uncert_pct_MC_95"])),
                    (hi, i), textcoords="offset points", xytext=(8, -3), fontsize=8.5)
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels([labels[k] for k in order], fontsize=9)
    ax.set_xlabel("Mt CO$_2$e (AR5), %s Monte Carlo" % _run_note(nat.values()))
    ax.set_title("National uncertainty under two correlation assumptions",
                 loc="left", fontsize=11)
    ax.set_ylim(-0.7, len(order) - 0.3)
    ax.set_xlim(left=min(float(r["P2.5_Mt"]) for r in nat.values()) * 0.97,
                right=max(float(r["P97.5_Mt"]) for r in nat.values()) * 1.14)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.grid(axis="x", linestyle=":", linewidth=0.6, alpha=0.6)
    ax.set_axisbelow(True)
    return _save(fig, "national_uncertainty.png")


def national_seasonality():
    """The national year in twelve months, stacked by how well the timing is known.

    The bars are the inventory resolved in time; the shading is the evidence for the
    resolution, and the two are deliberately drawn together. Read the height and the layer
    at once: the flat T4 band is a declared assumption of no seasonality, so the visible
    curvature in the total comes from a minority of the inventory and the figure should not
    let a reader forget it. The dashed line is one twelfth of the year - what the whole
    inventory would look like if every profile were flat.
    """
    rows = _read("national_monthly_2024.csv")
    if not rows:
        return None
    months = sorted({r["month"] for r in rows})
    classes = ["T1", "T2", "T3", "T4"]
    stack = {c: [0.0] * len(months) for c in classes}
    index = {m: i for i, m in enumerate(months)}
    for r in rows:
        stack[r["temporal_method"]][index[r["month"]]] += float(r["co2e_Mt_AR5"])
    total = sum(sum(v) for v in stack.values())

    plt = _plt()
    fig, ax = plt.subplots(figsize=(7.0, 3.4))
    bottom = [0.0] * len(months)
    labels = {"T1": "T1 observed monthly", "T2": "T2 monthly administrative records",
              "T3": "T3 process-based profile", "T4": "T4 flat, declared"}
    for i, cls in enumerate(classes):
        if not any(stack[cls]):
            continue
        share = 100.0 * sum(stack[cls]) / total
        ax.bar(range(len(months)), stack[cls], bottom=bottom, width=0.78,
               color=PALETTE[i], edgecolor="white", linewidth=0.5,
               label="%s  (%.0f%% of the year)" % (labels[cls], share))
        bottom = [b + v for b, v in zip(bottom, stack[cls])]
    ax.axhline(total / 12.0, color="#222222", linewidth=1.0, linestyle="--")
    ax.annotate("a flat year", (len(months) - 0.4, total / 12.0),
                textcoords="offset points", xytext=(4, 4), fontsize=8, color="#444444")
    ax.set_xticks(range(len(months)))
    ax.set_xticklabels([m[4:] + "\n" + m[:4] for m in months], fontsize=7.5)
    ax.set_ylabel("Mt CO$_2$e (AR5)")
    ax.set_title("The national inventory by month, shaded by the evidence for its timing",
                 loc="left", fontsize=11)
    ax.legend(fontsize=7.5, loc="upper center", frameon=False, ncol=2,
              bbox_to_anchor=(0.5, 1.02), handlelength=1.4, columnspacing=1.2)
    ax.set_ylim(0, max(bottom) * 1.45)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", linestyle=":", linewidth=0.6, alpha=0.6)
    ax.set_axisbelow(True)
    return _save(fig, "national_seasonality.png")


def national_monthly_crosschecks():
    """The fertiliser profile against the agronomic calendar it is not.

    Two independent answers to when Pakistan's nitrogen reaches the field: NFDC's observed
    offtake, which is what the inventory uses, and the crop calendars weighted by each crop's
    share of national nitrogen. Drawn because the disagreement is large - a quarter of the
    annual nitrogen changes month between them - and because neither can be checked against
    an observation of uptake. The width between the two lines is the honest width of the
    monthly claim for the largest category in the inventory.
    """
    rows = [r for r in _read("monthly_crosschecks.csv") if r["check"] == "fertiliser"]
    if not rows:
        return None
    rows.sort(key=lambda r: r["month"])
    months = [r["month"] for r in rows]
    published = [100 * float(r["published_share"]) for r in rows]
    alternative = [100 * float(r["alternative_share"]) for r in rows]
    plt = _plt()
    fig, ax = plt.subplots(figsize=(7.0, 2.9))
    x = range(len(months))
    ax.fill_between(x, published, alternative, color="#cccccc", alpha=0.55, linewidth=0)
    ax.plot(x, published, marker="o", markersize=3.5, linewidth=1.6, color=PALETTE[0],
            label="NFDC offtake: when urea left the depot (used)")
    ax.plot(x, alternative, marker="s", markersize=3.5, linewidth=1.6, color=PALETTE[1],
            linestyle="--", label="Crop calendars: when agronomy says the crop needs it")
    borrowed = [i for i, r in enumerate(rows) if "T3" in r["published_basis"]]
    if borrowed:
        ax.axvspan(min(borrowed) - 0.5, max(borrowed) + 0.5, color=PALETTE[4], alpha=0.13)
        ax.annotate("borrowed from\nthe opening year", (max(borrowed), max(published)),
                    textcoords="offset points", xytext=(-6, -14), fontsize=7.5,
                    ha="right", color="#6b5a13")
    ax.set_xticks(list(x))
    ax.set_xticklabels([m[4:] for m in months], fontsize=8)
    ax.set_ylabel("Share of the year, %")
    ax.set_title("Nitrogen: two monthly profiles, neither observed at the field",
                 loc="left", fontsize=11)
    ax.legend(fontsize=7.5, frameon=False, loc="upper center")
    ax.set_ylim(0, max(max(published), max(alternative)) * 1.45)
    _style(ax)
    ax.grid(axis="y", linestyle=":", linewidth=0.6, alpha=0.6)
    return _save(fig, "national_monthly_crosschecks.png")


def national_air_pollutants():
    """Primary PM2.5 by layer, drawn so the unequal assurance is visible in the figure.

    Solid bars are estimated layers; hatched bars are the bound and the screening estimate,
    which a reader should not rank against an estimate. The labels carry the class as well,
    because hatching does not survive every reproduction.
    """
    labels = {"residential": "Residential solid fuel", "waste": "Open waste burning",
              "agriculture": "Crop-residue burning", "transport": "Road transport (exhaust)",
              "power": "Power generation", "railways": "Railways",
              "aviation": "Domestic aviation (LTO)",
              "industry": "Industrial combustion (provisional)",
              "ippu": "Industrial processes (provisional)",
              "fugitives": "Oil and gas fugitives and flaring (provisional)"}
    items = []
    for sector, fname in AIR_FILES.items():
        rows = _read(fname)          # raises if the layer's output has gone
        total = sum(_num(r, "emissions_kt") or 0.0 for r in rows
                    if (r.get("pollutant") or "").upper() in ("PM2.5", "PM25")
                    and (r.get("process") or "exhaust") == "exhaust")
        items.append((labels[sector], total, AIR_ASSURANCE[sector]))
    # rc58/rc59: the register modules have no single-year layer of their own - their
    # reference-year PM2.5 is the nine-year panel's FY2023-24 slice (the same atoms, one
    # configuration)
    panel = _read("pakemis_air_annual_fy2015_16_fy2023_24.csv")
    for sector in ("industry", "ippu", "fugitives"):
        total = sum(_num(r, "emissions_Gg") or 0.0
                    for r in panel
                    if r["sector_id"] == sector and r["pollutant"] == "PM2.5"
                    and r["period_id"] == "FY2023-24" and r["configuration_id"] == "REF_2023_24")
        items.append((labels[sector], total, AIR_ASSURANCE[sector]))
    items.sort(key=lambda kv: kv[1])
    plt = _plt()
    fig, ax = plt.subplots(figsize=(6.8, 3.4))
    firm = [a == "estimated" for _k, _v, a in items]
    ax.barh([k for k, _v, _a in items], [v for _k, v, _a in items],
            color=[PALETTE[2] if f else "#ffffff" for f in firm],
            edgecolor=[PALETTE[2] if f else PALETTE[6] for f in firm],
            hatch=[None if f else "///" for f in firm], linewidth=0.9)
    for i, (_k, v, a) in enumerate(items):
        note = "%.1f kt" % v if v < 10 else "%.0f kt" % v
        if a != "estimated":
            note += "  (%s)" % a
        ax.annotate(note, (v, i), textcoords="offset points", xytext=(5, -3), fontsize=8.5)
    ax.set_xlim(right=max(v for _k, v, _a in items) * 1.32)
    ax.set_xlabel("Primary PM$_{2.5}$ (kt/yr)")
    ax.set_title("Household solid fuel dominates primary particulate", loc="left",
                 fontsize=11)
    ax.annotate("Hatched: not an estimate. Industry and IPPU have no layer at all.",
                (0, -0.20), xycoords="axes fraction", fontsize=8, color="#555555")
    _style(ax)
    return _save(fig, "national_pm25.png")


def aviation_reconciliation():
    """Matched-period movement, fuel-bridge and OECD domestic estimates."""
    recon = _read("aviation_reconciliation_fy2023_24.csv")
    bench = _read("aviation_benchmark_summary_fy2023_24.csv")
    if not recon or not bench:
        return None
    central = next(r for r in recon if r["scenario"] == "flight_fuel_weighted")
    b = bench[0]
    items = [
        ("Movement model", float(central["bottom_up_domestic_co2_Gg"])),
        ("Fuel bridge", float(central["domestic_co2_Gg"])),
        ("OECD territory", float(b["oecd_domestic_co2_t"]) / 1000.0),
    ]
    plt = _plt()
    fig, ax = plt.subplots(figsize=(6.6, 2.7))
    ax.barh([k for k, _v in items], [v for _k, v in items],
            color=[PALETTE[0], PALETTE[2], PALETTE[1]], edgecolor="white")
    for i, (_label, value) in enumerate(items):
        ax.annotate("%.0f kt" % value, (value, i), textcoords="offset points",
                    xytext=(5, -3), fontsize=8.5)
    ax.set_xlabel("Domestic aviation CO$_2$ (kt), FY2023-24")
    ax.set_title("Three matched-period estimates", loc="left", fontsize=11)
    ax.set_xlim(0, max(v for _k, v in items) * 1.22)
    _style(ax)
    return _save(fig, "aviation_reconciliation.png")


def aviation_structural_uncertainty():
    """Parametric intervals nested within discrete boundary-mapping choices."""
    rows = _read("aviation_uncertainty_scenarios_fy2023_24.csv")
    if not rows:
        return None
    labels = {"representative_stage": "Movement model",
              "literal_customer": "Literal customer labels",
              "movement_count": "Movement-share bridge",
              "flight_fuel_weighted": "Flight-fuel bridge"}
    order = ["representative_stage", "flight_fuel_weighted", "movement_count",
             "literal_customer"]
    selected = {r["structural_scenario"]: r for r in rows}
    plt = _plt()
    fig, ax = plt.subplots(figsize=(6.6, 3.0))
    for i, key in enumerate(order):
        r = selected[key]
        lo, mid, hi = float(r["P2.5_Mt"]), float(r["P50_Mt"]), float(r["P97.5_Mt"])
        ax.plot([lo, hi], [i, i], linewidth=6, solid_capstyle="butt",
                color=PALETTE[i], alpha=0.85)
        ax.plot([mid], [i], marker="|", markersize=16, color="#222222")
        ax.annotate("%.3f" % mid, (hi, i), textcoords="offset points",
                    xytext=(6, -3), fontsize=8.5)
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels([labels[k] for k in order], fontsize=9)
    ax.set_xlabel("Domestic aviation (Mt CO$_2$e or CO$_2$ for bridge scenarios)")
    ax.set_title("Structural choice dominates parametric fuel uncertainty",
                 loc="left", fontsize=11)
    _style(ax)
    return _save(fig, "aviation_uncertainty.png")


def aviation_framework():
    """Accounting architecture: data, ledgers, controls, products and evaluation."""
    plt = _plt()
    fig, ax = plt.subplots(figsize=(8.0, 4.4))
    ax.set_xlim(0, 9.9)
    ax.set_ylim(0, 7)
    ax.axis("off")
    columns = [
        (0.2, "Source data", ["PCAA + OCAC", "Pakistan UNFCCC", "OECD + TRACE"]),
        (2.15, "Shared ledgers", ["Flight-stage ledger", "Fuel source-row\nledger", "Provenance + tiers"]),
        (4.1, "Accounting", ["Customer $\\rightarrow$\ngeography", "M0--M2 models", "Six fuel accounts"]),
        (6.05, "Controls", ["Exact row closure", "Airport/airline\nmargins", "Coverage + residuals"]),
        (8.0, "Products", ["9-year + monthly", "Scenarios + bounds", "External evaluation"]),
    ]
    for x, title, lines in columns:
        ax.add_patch(plt.Rectangle((x, 1.5), 1.65, 4.2, facecolor="#f5f7f9",
                                   edgecolor="#4d6475", linewidth=1.0))
        ax.text(x + 0.825, 5.25, title, ha="center", va="center", fontsize=9.0,
                fontweight="bold")
        for j, line in enumerate(lines):
            ax.add_patch(plt.Rectangle((x + 0.12, 4.25 - j * 1.05), 1.41, 0.68,
                                       facecolor="white", edgecolor="#a9b5bd", linewidth=0.7))
            ax.text(x + 0.825, 4.59 - j * 1.05, line, ha="center", va="center", fontsize=7.4)
        if x < 8.0:
            ax.annotate("", xy=(x + 1.91, 3.6), xytext=(x + 1.67, 3.6),
                        arrowprops={"arrowstyle": "->", "color": "#4d6475", "lw": 1.4})
    ax.text(0.2, 6.35, "A reproducible, fuel-constrained aviation accounting system",
            ha="left", fontsize=12, fontweight="bold")
    ax.text(5.0, 0.65,
            "ADSB Tier A pilot and future PCAA/OpenSky records replace Tier C/D without changing accounting",
            ha="center", fontsize=8.5, color="#4d6475")
    return _save(fig, "aviation_framework.png")


def aviation_source_row_bridge():
    """Every OCAC source row partitioned into non-overlapping accounting destinations."""
    rows = _read("aviation_bridge_source_rows_all_scenarios.csv")
    if not rows:
        return None
    rows = [r for r in rows if r["fiscal_year"] == "2023" and
            r["scenario"] == "flight_fuel_weighted"]
    rows.sort(key=lambda r: float(r["reported_t"]))
    accounts = [("ipcc_domestic", "Domestic civil"),
                ("international_bunker", "International bunker"),
                ("military_1a5b", "Military/government"),
                ("general_aviation", "General aviation"),
                ("export_other", "Export/other"), ("residual", "Residual")]
    plt = _plt()
    fig, ax = plt.subplots(figsize=(7.4, 3.7))
    left = [0.0] * len(rows)
    labels = [r["customer_category"] + " (" + r["fuel_type"] + ")" for r in rows]
    for index, (key, label) in enumerate(accounts):
        values = [float(r[key]) / 1000.0 for r in rows]
        ax.barh(labels, values, left=left, label=label, color=PALETTE[index],
                edgecolor="white", linewidth=0.4)
        left = [a + b for a, b in zip(left, values)]
    ax.set_xlabel("Fuel (kt), FY2023-24")
    ax.set_title("OCAC source rows close exactly across six accounts", loc="left", fontsize=11)
    ax.legend(ncol=3, fontsize=7.5, frameon=False, loc="lower right")
    _style(ax)
    return _save(fig, "aviation_source_bridge.png")


def aviation_component_offsets():
    """Carrier-group errors whose cancellation makes aggregate closure look stronger."""
    rows = _read("aviation_annual_component_comparison.csv")
    if not rows:
        return None
    labels, values, colors = [], [], []
    for year in (2022, 2023):
        for component in ("resident", "foreign", "combined"):
            row = next(r for r in rows if int(r["fiscal_year"]) == year and
                       r["component"] == component)
            labels.append("FY%d %s" % (year, component.capitalize()))
            values.append(float(row["difference_co2_t"]) / 1000.0)
            colors.append(PALETTE[0] if component == "resident" else
                          PALETTE[1] if component == "foreign" else PALETTE[7])
    plt = _plt()
    fig, ax = plt.subplots(figsize=(7.2, 3.5))
    ax.barh(labels, values, color=colors, edgecolor="white")
    ax.axvline(0, color="#333333", linewidth=0.8)
    for i, value in enumerate(values):
        ax.annotate("%+.0f" % value, (value, i), textcoords="offset points",
                    xytext=(4 if value >= 0 else -4, -3),
                    ha="left" if value >= 0 else "right", fontsize=8.5)
    ax.set_xlabel("OCAC-derived minus OECD CO$_2$ (kt)")
    ax.set_title("Near-total closure is produced by offsetting carrier-group differences",
                 loc="left", fontsize=11)
    ax.grid(axis="x", linestyle=":", linewidth=0.6, alpha=0.6)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    return _save(fig, "aviation_component_offsets.png")


def aviation_monthly_closure():
    rows = _read("aviation_monthly_reconciliation.csv")
    if not rows:
        return None
    plt = _plt()
    fig, ax = plt.subplots(figsize=(7.4, 3.5))
    x = list(range(len(rows)))
    for index, (key, label) in enumerate((
            ("resident_ratio", "Resident carriers"),
            ("foreign_ratio", "Foreign carriers"),
            ("combined_ratio", "Combined"))):
        ax.plot(x, [float(r[key]) for r in rows], marker="o", markersize=2.8,
                linewidth=1.35, color=PALETTE[index], label=label)
    ax.axhline(1.0, color="#333333", linewidth=0.8, linestyle="--")
    ax.set_xticks(x[::3])
    ax.set_xticklabels([rows[i]["month"] for i in x[::3]], rotation=30, ha="right")
    ax.set_ylabel("OCAC-derived / OECD CO$_2$")
    ax.set_title("Monthly aggregate closure is variable; component offsets persist",
                 loc="left", fontsize=11)
    ax.legend(frameon=False, ncol=3, fontsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", linestyle=":", linewidth=0.6, alpha=0.6)
    return _save(fig, "aviation_monthly_closure.png")


def aviation_two_year_comparison():
    rows = _read("aviation_two_year_replication.csv")
    if not rows:
        return None
    plt = _plt()
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    names = ["Movement M0", "Route M1", "Calibrated bridge", "OECD territory"]
    keys = ["movement_model_fuel_t", "route_resolved_fuel_t",
            "flight_fuel_weighted_domestic_fuel_t", "oecd_domestic_co2_t"]
    width = 0.35
    positions = list(range(len(names)))
    for j, row in enumerate(rows):
        values = []
        for key in keys:
            value = float(row[key]) / 1000.0
            if key != "oecd_domestic_co2_t":
                value *= 3.16
            values.append(value)
        ax.bar([x + (j - 0.5) * width for x in positions], values, width=width,
               label="FY%d-%02d" % (int(row["fiscal_year"]),
                                      (int(row["fiscal_year"]) + 1) % 100),
               color=PALETTE[j], edgecolor="white")
    ax.set_xticks(positions)
    ax.set_xticklabels(names)
    ax.set_ylabel("Domestic CO$_2$ (kt)")
    ax.set_title("The principal comparisons replicate across two fiscal years",
                 loc="left", fontsize=11)
    ax.legend(frameon=False, fontsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", linestyle=":", linewidth=0.6, alpha=0.6)
    return _save(fig, "aviation_two_year.png")


def aviation_resolution_ladders():
    rows = _read("aviation_common_support_ladder.csv")
    if not rows:
        return None
    common = [r for r in rows if r["experiment"] == "common_support"]
    completion = [r for r in rows if r["experiment"] == "coverage_completion" and
                  r["step"] != "completed_total"]
    pretty = {"aggregate_factor": "Aggregate factor", "route_distance": "Route distance",
              "route_aircraft_openap": "Route-aircraft OpenAP",
              "native_openap": "Native OpenAP", "unsupported_aircraft_icao_imputation": "Aircraft imputation",
              "supported_route_operator_residual": "Route/operator residual",
              "endpoint_residual_aggregate_imputation": "Endpoint residual"}
    plt = _plt()
    fig, axes = plt.subplots(1, 2, figsize=(8.0, 3.5), gridspec_kw={"width_ratios": [1.1, 1]})
    axes[0].barh([pretty[r["step"]] for r in common],
                 [float(r["fuel_t"]) / 1000 for r in common], color=PALETTE[:3])
    axes[0].set_xlabel("Fuel (kt)")
    axes[0].set_title("Identical 17,491-stage support", loc="left", fontsize=10)
    left = 0.0
    for i, row in enumerate(completion):
        value = float(row["fuel_t"]) / 1000.0
        axes[1].barh(["Completed inventory"], [value], left=left, label=pretty[row["step"]],
                     color=PALETTE[i], edgecolor="white")
        left += value
    axes[1].set_xlabel("Fuel (kt)")
    axes[1].set_title("Coverage completion", loc="left", fontsize=10)
    axes[1].set_yticklabels([])
    axes[1].legend(frameon=False, fontsize=7, loc="lower center", bbox_to_anchor=(0.5, -0.48))
    for ax in axes:
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(axis="x", linestyle=":", linewidth=0.6, alpha=0.6)
        ax.set_axisbelow(True)
    fig.suptitle("Resolution and missing coverage are separate experiments", x=0.08,
                 ha="left", fontsize=11)
    return _save(fig, "aviation_resolution_ladders.png")


def aviation_uncertainty_sensitivity():
    rows = _read("aviation_uncertainty_sensitivity.csv")
    if not rows:
        return None
    rows = sorted(rows, key=lambda r: float(r["max_absolute_change_pct"]))
    plt = _plt()
    fig, ax = plt.subplots(figsize=(7.0, 3.5))
    ax.barh([r["variable"] for r in rows],
            [float(r["max_absolute_change_pct"]) for r in rows], color=PALETTE[5])
    ax.set_xlabel("Maximum absolute change in domestic CO$_2$ (%)")
    ax.set_title("One-at-a-time sensitivity of the completed flight-stage estimate",
                 loc="left", fontsize=11)
    _style(ax)
    return _save(fig, "aviation_sensitivity.png")


def aviation_m2_uncertainty():
    """Completed-M2 parametric intervals, structural envelope, and named contributions."""
    intervals = _read("aviation_m2_uncertainty_intervals.csv")
    envelope = _read("aviation_m2_structural_envelope.csv")
    contributions = _read("aviation_m2_uncertainty_contributions.csv")
    if not intervals or not envelope or not contributions:
        return None
    selected = [row for row in intervals
                if row["route_graph"] == "central_ipf" and row["metric"] == "CO2"]
    specifications = (
        ("primary", "current_icao_route_m1_endpoint_m0", "Current completion"),
        ("weather_augmented", "current_icao_route_m1_endpoint_m0", "Current + ERA5 audit"),
        ("primary", "route_matched_openap_analogue", "OpenAP analogue"),
        ("primary", "all_missing_stages_m0", "All missing at M0"),
    )
    by_key = {(row["interval_type"], row["completion_method"]): row for row in selected}
    rows = [by_key[(interval_type, method)] for interval_type, method, _label in specifications]
    structural = next(row for row in envelope
                      if row["interval_type"] == "primary" and row["metric"] == "CO2")

    plt = _plt()
    fig, axes = plt.subplots(1, 2, figsize=(8.4, 3.45), gridspec_kw={"width_ratios": [1.15, 1]})
    ax = axes[0]
    y = list(range(len(rows)))
    means = [float(row["mean_Mt"]) for row in rows]
    lows = [float(row["P2.5_Mt"]) for row in rows]
    highs = [float(row["P97.5_Mt"]) for row in rows]
    ax.axvspan(float(structural["structural_low_Mt"]),
               float(structural["structural_high_Mt"]), color=PALETTE[4], alpha=0.12,
               label="All-config. envelope")
    ax.errorbar(means, y,
                xerr=[[mean - low for mean, low in zip(means, lows)],
                      [high - mean for mean, high in zip(means, highs)]],
                fmt="o", color=PALETTE[0], capsize=3, label="95% parametric interval")
    ax.set_yticks(y)
    ax.set_yticklabels([label for _interval_type, _method, label in specifications])
    ax.invert_yaxis()
    ax.set_xlabel("Domestic CO$_2$ (Mt)")
    ax.set_title("Parametric intervals within structure", loc="left", fontsize=10)
    _style(ax)

    ax = axes[1]
    contributions = sorted(contributions, key=lambda row: float(row["variance_reduction_pct"]))
    ax.barh([row["uncertainty_group"].capitalize() for row in contributions],
            [float(row["variance_reduction_pct"]) for row in contributions],
            color=PALETTE[5])
    ax.set_xlabel("Variance reduction when frozen (%)")
    ax.set_title("Named M2 inputs, not legacy $\\pm$60%", loc="left", fontsize=10)
    _style(ax)
    fig.suptitle("Completed-M2 uncertainty separates parametric draws from structural choices",
                 x=0.08, ha="left", fontsize=11)
    return _save(fig, "aviation_m2_uncertainty.png")


def aviation_long_run_controls():
    """Nine OCAC years and the five complete matched OECD fiscal years."""
    fuel = _read("aviation_ocac_annual_summary.csv")
    comparison = _read("aviation_ocac_oecd_annual_comparison.csv")
    if not fuel or not comparison:
        return None
    comparison = [row for row in comparison if row["period_status"] == "complete"]
    plt = _plt()
    fig, axes = plt.subplots(1, 2, figsize=(8.2, 3.55))
    years = [int(row["fiscal_year"]) for row in fuel]
    resident = [float(row["resident_commercial_jp1_t"]) / 1000 for row in fuel]
    foreign = [float(row["foreign_commercial_jp1_t"]) / 1000 for row in fuel]
    axes[0].bar(years, resident, color=PALETTE[0], label="Resident customers")
    axes[0].bar(years, foreign, bottom=resident, color=PALETTE[1],
                label="Foreign customers")
    axes[0].set_ylabel("Commercial JP-1 (kt)")
    axes[0].set_title("Nine official fuel years", loc="left", fontsize=10)
    axes[0].legend(frameon=False, fontsize=7.5)
    matched_years = [int(row["fiscal_year"]) for row in comparison]
    for index, (key, label) in enumerate((
            ("resident_ratio", "Resident"), ("foreign_ratio", "Foreign"),
            ("combined_ratio", "Combined"))):
        axes[1].plot(matched_years, [float(row[key]) for row in comparison],
                     marker="o", linewidth=1.5, color=PALETTE[index], label=label)
    axes[1].axhline(1, color="#333333", linewidth=0.8, linestyle="--")
    axes[1].set_ylabel("OCAC-derived / OECD CO$_2$")
    axes[1].set_title("Five complete matched fiscal years", loc="left", fontsize=10)
    axes[1].legend(frameon=False, fontsize=7.5, ncol=3)
    for ax in axes:
        ax.set_xlabel("Fiscal year starting")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(axis="y", linestyle=":", linewidth=0.6, alpha=0.6)
        ax.set_axisbelow(True)
    fig.suptitle("Long-run fuel evidence: aggregate closure improves through component offsets",
                 x=0.08, ha="left", fontsize=11)
    return _save(fig, "aviation_long_run_controls.png")


def aviation_official_reporting():
    """Official Pakistan CRT allocation against matched OECD flight geography."""
    rows = _read("aviation_unfccc_official_comparison.csv")
    if not rows:
        return None
    rows = [row for row in rows if row["submission"] == "Pakistan CRT 2024"]
    if len(rows) != 2:
        return None
    rows.sort(key=lambda row: 0 if row["scope"] == "domestic territory" else 1)
    labels = ["Domestic", "International bunker"]
    official = [float(row["value_co2e_t"]) / 1000 for row in rows]
    oecd = [float(row["oecd_matched_period_co2_t"]) / 1000 for row in rows]
    plt = _plt()
    fig, ax = plt.subplots(figsize=(6.8, 3.2))
    x = list(range(2))
    width = 0.34
    ax.bar([value - width / 2 for value in x], official, width=width,
           color=PALETTE[0], label="Pakistan CRT")
    ax.bar([value + width / 2 for value in x], oecd, width=width,
           color=PALETTE[1], label="OECD flight geography")
    for j, values in enumerate((official, oecd)):
        for i, value in enumerate(values):
            ax.annotate("%.0f" % value, (i + (j - 0.5) * width, value),
                        textcoords="offset points", xytext=(0, 3), ha="center", fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_yscale("log")
    ax.set_ylabel("Calendar-2022 CO$_2$ (kt; log scale)")
    ax.set_title("Official 80/20 allocation is inconsistent with matched evidence",
                 loc="left", fontsize=11)
    ax.legend(frameon=False, fontsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", linestyle=":", linewidth=0.6, alpha=0.6, which="both")
    return _save(fig, "aviation_official_reporting.png")


def aviation_climatetrace_airports():
    """PCAA airport activity against Climate TRACE airport emissions."""
    rows = _read("aviation_climatetrace_airport_comparison.csv")
    if not rows:
        return None
    plt = _plt()
    fig, axes = plt.subplots(1, 2, figsize=(8.0, 3.5))
    for ax, scope, color in zip(axes, ("domestic", "international"), PALETTE[:2]):
        points = [(float(row["pcaa_%s_movements" % scope]),
                   float(row["climatetrace_%s_co2_t" % scope]), row["airport_icao"])
                  for row in rows if float(row["pcaa_%s_movements" % scope]) > 0 and
                  float(row["climatetrace_%s_co2_t" % scope]) > 0]
        ax.scatter([x for x, _y, _a in points], [y for _x, y, _a in points],
                   color=color, edgecolor="white", s=35)
        label_offsets = ((5, 4), (5, -9), (-23, 5))
        for (x, y, airport), offset in zip(sorted(points, reverse=True)[:3],
                                           label_offsets):
            ax.annotate(airport, (x, y), textcoords="offset points", xytext=offset,
                        fontsize=7)
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel("PCAA commercial movements")
        ax.set_title(scope.capitalize(), loc="left", fontsize=10)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(linestyle=":", linewidth=0.6, alpha=0.6, which="both")
    axes[0].set_ylabel("Climate TRACE CO$_2$ (t)")
    fig.suptitle("Airport rankings are strongly spatially consistent in FY2023-24",
                 x=0.08, ha="left", fontsize=11)
    return _save(fig, "aviation_climatetrace_airports.png")


def aviation_era5_weather_audit():
    """Weather-duration sensitivity for the representative OpenAP route audit."""
    rows = _read("aviation_era5_openap_audit.csv")
    if not rows:
        return None
    rows = [row for row in rows if row["payload_scenario"] == "central"]
    grouped = {}
    for row in rows:
        grouped.setdefault(row["route"], []).append(float(row["weather_fuel_change_pct"]))
    if not grouped:
        return None
    labels = sorted(grouped)
    means = [sum(grouped[label]) / len(grouped[label]) for label in labels]
    lows = [min(grouped[label]) for label in labels]
    highs = [max(grouped[label]) for label in labels]
    plt = _plt()
    fig, ax = plt.subplots(figsize=(7.0, 3.3))
    ax.errorbar(means, range(len(labels)),
                xerr=[[mean - low for mean, low in zip(means, lows)],
                      [high - mean for mean, high in zip(means, highs)]],
                fmt="o", color=PALETTE[0], capsize=3)
    ax.axvline(0, color="#333333", linewidth=0.8, linestyle="--")
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels)
    ax.set_xlabel("ERA5 duration-scaled fuel change from still air (%)")
    ax.set_title("Weather sensitivity does not validate the OpenAP fuel level",
                 loc="left", fontsize=11)
    _style(ax)
    return _save(fig, "aviation_era5_weather_audit.png")


def fugitives_framework():
    """Compact scientific workflow for the fugitive-emissions study."""
    plt = _plt()
    from matplotlib.patches import FancyBboxPatch
    fig, ax = plt.subplots(figsize=(9.0, 3.6))
    ax.set_xlim(0, 12.4)
    ax.set_ylim(0, 4.8)
    ax.axis("off")
    boxes = [
        (0.2, 1.65, 2.7, 1.35, "Pakistan activity +\nIPCC methods",
         "production • infrastructure • throughput\n2006 Guidelines • 2019 Refinement"),
        (3.35, 1.65, 2.7, 1.35, "Segment inventory",
         "production • processing • network\npost-meter • native gases"),
        (6.50, 1.65, 2.7, 1.35, "Uncertainty",
         "factorial structural models\nconditional parametric intervals"),
        (9.65, 1.65, 2.55, 1.35, "Evaluation",
         "gas flow + UFG • official CRT\nflare and plume observations"),
    ]
    for x, y, w, h, title, detail in boxes:
        patch = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.04",
                               facecolor="#eaf1f6", edgecolor="#5b7891", linewidth=1.0)
        ax.add_patch(patch)
        ax.text(x + w / 2, y + h * 0.68, title, ha="center", va="center",
                fontsize=9.5, fontweight="bold")
        ax.text(x + w / 2, y + h * 0.24, detail, ha="center", va="center", fontsize=7.4)
    for start, end in [((2.9, 2.325), (3.35, 2.325)),
                       ((6.05, 2.325), (6.50, 2.325)),
                       ((9.20, 2.325), (9.65, 2.325))]:
        ax.annotate("", xy=end, xytext=start,
                    arrowprops={"arrowstyle": "->", "color": "#6c7d88", "lw": 1.1})
    ax.text(0.2, 4.45, "Building and evaluating Pakistan's oil-and-gas fugitive inventory",
            fontsize=12, fontweight="bold", ha="left")
    return _save(fig, "fugitives_framework.png")


def fugitives_method_ladder():
    rows = _read("fugitives_method_ladder_2024.csv")
    if not rows:
        return None
    rows.sort(key=lambda row: int(row["order"]))
    labels = [row["method"] for row in rows]
    values = [float(row["mt_co2e_ar5"]) for row in rows]
    plt = _plt()
    fig, ax = plt.subplots(figsize=(8.0, 3.5))
    ax.barh(labels, values, color=[PALETTE[7], PALETTE[7], PALETTE[0], PALETTE[2], PALETTE[1]],
            edgecolor="white")
    for index, value in enumerate(values):
        ax.annotate("%.2f" % value, (value, index), textcoords="offset points",
                    xytext=(5, -3), fontsize=8.5)
    ax.set_xlabel("Mt CO$_2$e (AR5)")
    ax.set_title("Method change and segment completion are separate experiments",
                 loc="left", fontsize=11)
    _style(ax)
    return _save(fig, "fugitives_method_ladder.png")


def fugitives_structural_uncertainty():
    factorial = _read("fugitives_structural_factorial_2024.csv")
    intervals = _read("fugitives_conditional_intervals_2024.csv")
    attribution = _read("fugitives_uncertainty_attribution_2024.csv")[:6]
    if not factorial or not intervals or not attribution:
        return None
    complete = [float(row["mt_co2e_ar5"]) for row in factorial
                if row["coverage_complete_under_configuration"] == "True"]
    coverage_sensitive = [float(row["mt_co2e_ar5"]) for row in factorial]
    plt = _plt()
    fig, axes = plt.subplots(1, 3, figsize=(12.0, 3.7),
                             gridspec_kw={"width_ratios": [1.5, 0.95, 1.25]})
    ranges = [(min(coverage_sensitive), max(coverage_sensitive)),
              (min(complete), max(complete))]
    axes[0].hlines([0, 1], [item[0] for item in ranges], [item[1] for item in ranges],
                   color=[PALETTE[7], PALETTE[0]], linewidth=7, alpha=0.82)
    for y, (low, high), color in zip([0, 1], ranges, [PALETTE[7], PALETTE[0]]):
        axes[0].scatter([low, high], [y, y], s=32, color=color, edgecolor="white",
                        linewidth=0.6, zorder=3)
        axes[0].annotate("%.2f" % low, (low, y), textcoords="offset points",
                         xytext=(0, 8), ha="center", fontsize=7.5)
        axes[0].annotate("%.2f" % high, (high, y), textcoords="offset points",
                         xytext=(0, 8), ha="center", fontsize=7.5)
    axes[0].axvline(max(complete), color=PALETTE[1], linewidth=1.1, linestyle="--")
    axes[0].set_yticks([0, 1])
    axes[0].set_yticklabels(["coverage may be excluded", "all public-data segments"])
    axes[0].set_xlabel("Deterministic Mt CO$_2$e")
    axes[0].set_title("Unweighted joint envelopes", loc="left", fontsize=10)
    _style(axes[0])
    short_labels = {"reference": "reference", "lower_practices": "lower practices",
                    "no_post_meter_industrial": "no post-meter",
                    "minimum_coverage_combined": "minimum coverage"}
    interval_labels = [short_labels.get(row["configuration"], row["configuration"])
                       for row in intervals]
    medians = [float(row["mc_p50_mt_co2e_ar5"]) for row in intervals]
    lows = [float(row["mc_p025_mt_co2e_ar5"]) for row in intervals]
    highs = [float(row["mc_p975_mt_co2e_ar5"]) for row in intervals]
    deterministic = [float(row["deterministic_mt_co2e_ar5"]) for row in intervals]
    positions = list(range(len(intervals)))
    axes[1].errorbar(medians, positions,
                     xerr=[[median - low for median, low in zip(medians, lows)],
                           [high - median for median, high in zip(medians, highs)]],
                     fmt="o", color=PALETTE[0], capsize=3, markersize=5)
    axes[1].scatter(deterministic, positions, marker="|", s=80, color=PALETTE[1],
                    label="deterministic")
    axes[1].set_yticks(positions)
    axes[1].set_yticklabels(interval_labels, fontsize=7)
    axes[1].set_xlabel("Mt CO$_2$e")
    axes[1].set_title("Conditional 95% intervals", loc="left", fontsize=10)
    axes[1].legend(frameon=False, fontsize=8)
    _style(axes[1])
    importance_labels = [row["input_group"].replace("factor:", "").replace("_", " ")
                         .replace("activity-source:", "activity: ")
                         .replace("activity-residual:", "coverage: ")
                         for row in attribution][::-1]
    importance_values = [float(row["normalized_squared_spearman_pct"])
                         for row in attribution][::-1]
    axes[2].barh(importance_labels, importance_values, color=PALETTE[5],
                 edgecolor="white")
    axes[2].set_xlabel("Normalized squared rank sensitivity (%)")
    axes[2].set_title("Conditional input importance", loc="left", fontsize=10)
    _style(axes[2])
    fig.suptitle("Practice, activity basis and coverage are not hidden in one confidence interval",
                 x=0.08, ha="left", fontsize=11)
    return _save(fig, "fugitives_structural_uncertainty.png")


def fugitives_observations():
    flares = _read("fugitives_viirs_flaring_2012_2025.csv")
    flare_sites = _read("fugitives_viirs_flare_sites.csv")
    sources = _read("fugitives_mars_sources.csv")
    stats = _read("fugitives_observation_field_statistics_2024.csv")
    if not flares or not sources or not flare_sites or not stats:
        return None
    plt = _plt()
    fig, axes = plt.subplots(1, 3, figsize=(12.0, 4.2),
                             gridspec_kw={"width_ratios": [0.9, 1.35, 0.95]})
    axes[0].plot([int(row["year"]) for row in flares],
                 [float(row["flare_volume_bcm"]) for row in flares],
                 marker="o", linewidth=1.5, color=PALETTE[1])
    axes[0].set_xlabel("Calendar year")
    axes[0].set_xticks([2012, 2015, 2018, 2021, 2024])
    axes[0].set_ylabel("Satellite-derived flare volume (bcm)")
    axes[0].set_title("World Bank flare observations", loc="left", fontsize=10)
    axes[0].grid(linestyle=":", linewidth=0.6, alpha=0.6)
    axes[0].spines["top"].set_visible(False)
    axes[0].spines["right"].set_visible(False)
    try:
        import geopandas as gpd
        from pkinv.core.gis.grid import ADM1_PATH
        boundaries = gpd.read_file(ADM1_PATH).to_crs("EPSG:4326")
        boundaries.plot(ax=axes[1], facecolor="#f4f3ef", edgecolor="#777777",
                        linewidth=0.6)
    except Exception:  # noqa: BLE001
        pass
    active = [row for row in flare_sites if float(row.get("2024") or 0.0) > 0]
    flare_sizes = [12 + 1500 * float(row["2024"]) ** 0.5 for row in active]
    axes[1].scatter([float(row["Longitude"]) for row in active],
                    [float(row["Latitude"]) for row in active], s=flare_sizes,
                    color=PALETTE[1], edgecolor="white", linewidth=0.3,
                    alpha=0.55, label="VIIRS flare (2024)")
    colors = ["#b2182b" if row["persistency_category"].lower() == "persistent"
              else PALETTE[0] for row in sources]
    sizes = [20 + 2.0 * float(row["n_plumes_detected"]) for row in sources]
    axes[1].scatter([float(row["lon"]) for row in sources],
                    [float(row["lat"]) for row in sources], s=sizes, color=colors,
                    marker="^", edgecolor="white", linewidth=0.4, alpha=0.9,
                    label="MARS source")
    axes[1].set_xlabel("Longitude")
    axes[1].set_ylabel("Latitude")
    axes[1].set_title("Independent observations over Pakistan", loc="left", fontsize=10)
    axes[1].set_xlim(60.5, 77.9)
    axes[1].set_ylim(23.4, 37.2)
    axes[1].legend(frameon=False, fontsize=7, loc="upper left")
    axes[1].text(0.02, 0.02, "19/20 MARS sources within 10 km of a listed flare",
                 transform=axes[1].transAxes, fontsize=7,
                 bbox={"facecolor": "white", "alpha": 0.8, "edgecolor": "none"})
    axes[1].grid(linestyle=":", linewidth=0.4, alpha=0.35)
    axes[1].spines["top"].set_visible(False)
    axes[1].spines["right"].set_visible(False)
    labels = [row["comparison"].replace(" assigned by nearest flare", "")
              .replace("VIIRS named-field ", "VIIRS ") for row in stats]
    spearman = [float(row["spearman_rho_with_ties"]) for row in stats]
    kendall = [float(row["kendall_tau_b"]) for row in stats]
    positions = list(range(len(stats)))
    axes[2].barh([position + 0.18 for position in positions], spearman,
                 height=0.34, color=PALETTE[0], label="Spearman")
    axes[2].barh([position - 0.18 for position in positions], kendall,
                 height=0.34, color=PALETTE[5], label="Kendall tau-b")
    axes[2].set_yticks(positions)
    axes[2].set_yticklabels(labels, fontsize=7)
    axes[2].set_xlim(0, 0.5)
    axes[2].set_xlabel("Rank association with official field supply")
    axes[2].set_title("Field-level evaluation (n=73)", loc="left", fontsize=10)
    axes[2].text(0.02, 0.04, "Named observations cover 71.1%\nof marketable field supply",
                 transform=axes[2].transAxes, fontsize=7)
    axes[2].legend(frameon=False, fontsize=7)
    _style(axes[2])
    fig.suptitle("Observations quantitatively evaluate upstream geography without being annualized",
                 x=0.08, ha="left", fontsize=11)
    return _save(fig, "fugitives_observations.png")


def fugitives_official_comparison():
    waterfall = _read("fugitives_unfccc_crt_waterfall_2022.csv")
    series = _read("fugitives_infrastructure_timeseries_2016_2024.csv")
    segments = _read("fugitives_infrastructure_segment_timeseries_2016_2024.csv")
    if not waterfall or not series or not segments:
        return None
    plt = _plt()
    fig, axes = plt.subplots(1, 2, figsize=(10.2, 3.8),
                             gridspec_kw={"width_ratios": [1.45, 1.2]})
    groups = [
        ("CRT\n(common GWP)", float(waterfall[0]["cumulative_common_mt_co2e"]), "total"),
        ("boundary", sum(float(row["delta_common_mt_co2e"]) for row in waterfall
                         if row["order"] == "1"), "delta"),
        ("oil", sum(float(row["delta_common_mt_co2e"]) for row in waterfall
                    if row["step"].startswith("Replace oil")), "delta"),
        ("gas upstream", sum(float(row["delta_common_mt_co2e"]) for row in waterfall
                             if row["step"] in ("Replace gas production and gathering",
                                                "Replace gas processing")), "delta"),
        ("T&D", sum(float(row["delta_common_mt_co2e"]) for row in waterfall
                    if row["step"] in ("Replace gas transmission", "Replace gas distribution")),
         "delta"),
        ("LNG +\npost-meter", sum(float(row["delta_common_mt_co2e"]) for row in waterfall
                                  if row["step"].startswith("Add ")), "delta"),
    ]
    running = groups[0][1]
    for index, (label, value, role) in enumerate(groups):
        if role == "total":
            axes[0].bar(index, value, color=PALETTE[7])
        else:
            bottom = running if value >= 0 else running + value
            axes[0].bar(index, abs(value), bottom=bottom,
                        color=PALETTE[2] if value >= 0 else PALETTE[4])
            running += value
            axes[0].plot([index - 0.5, index + 0.5], [running, running],
                         color="#555555", linewidth=0.6)
    axes[0].bar(len(groups), running, color=PALETTE[1])
    axes[0].set_xticks(range(len(groups) + 1))
    axes[0].set_xticklabels([item[0] for item in groups] + ["reconstructed"],
                            rotation=25, ha="right", fontsize=7)
    axes[0].set_ylabel("Mt CO$_2$e (CO$_2$=1, fossil CH$_4$=%g, N$_2$O=%g)"
                       % (GWP["AR5"]["CH4_fossil"], GWP["AR5"]["N2O"]))
    axes[0].set_title("CRT-to-reconstruction waterfall", loc="left", fontsize=10)
    _style(axes[0])
    years = sorted({int(item["fiscal_year"]) for item in series})
    totals_by_year = {int(item["fiscal_year"]): float(item["co2e_Mt_AR5"])
                      for item in series}
    group_names = ["upstream/processing", "network/import", "post-meter"]
    group_labels = ["Upstream + processing", "Network + LNG", "Post-meter"]
    group_values = []
    for group in group_names:
        annual = defaultdict(float)
        for item in segments:
            if item["reporting_group"] == group:
                annual[int(item["fiscal_year"])] += float(item["co2e_Mt_AR5"])
        group_values.append([annual[year] for year in years])
    axes[1].stackplot(years, *group_values, labels=group_labels,
                      colors=[PALETTE[0], PALETTE[5], PALETTE[7]], alpha=0.82)
    totals = [totals_by_year[year] for year in years]
    axes[1].plot(years, totals, marker="o", markersize=3.5, color=PALETTE[1],
                 linewidth=1.4, label="Total")
    for year, value in ((years[0], totals[0]), (years[-1], totals[-1])):
        axes[1].annotate("%.2f" % value, (year, value), textcoords="offset points",
                         xytext=(0, 7), ha="center", fontsize=8)
    axes[1].set_xticks(years[::2] + ([years[-1]] if years[-1] not in years[::2] else []))
    axes[1].set_ylabel("Mt CO$_2$e")
    axes[1].set_title("Network growth offsets upstream decline", loc="left", fontsize=10)
    axes[1].legend(frameon=False, fontsize=7, ncol=2, loc="lower left")
    _style(axes[1])
    fig.suptitle("The official discrepancy is decomposed and robust to adjacent fiscal periods",
                 x=0.08, ha="left", fontsize=11)
    return _save(fig, "fugitives_official_comparison.png")


def fugitives_native_gases():
    rows = _read("fugitives_segment_native_gases_2024.csv")
    if not rows:
        return None
    rows.sort(key=lambda row: float(row["co2e_Mt_AR5"]))
    labels = [row["segment"] for row in rows]
    ch4 = [float(row["ch4_Gg"]) * 30.0 / 1000.0 for row in rows]
    co2 = [float(row["co2_Gg"]) / 1000.0 for row in rows]
    n2o = [float(row["n2o_Gg"]) * 265.0 / 1000.0 for row in rows]
    plt = _plt()
    fig, ax = plt.subplots(figsize=(8.2, 4.6))
    ax.barh(labels, ch4, color=PALETTE[0],
            label="CH$_4$ (GWP$_{100}$=%g)" % GWP["AR5"]["CH4_fossil"])
    ax.barh(labels, co2, left=ch4, color=PALETTE[7], label="CO$_2$")
    left = [a + b for a, b in zip(ch4, co2)]
    ax.barh(labels, n2o, left=left, color=PALETTE[4], label="N$_2$O")
    ax.set_xlabel("Mt CO$_2$e (AR5)")
    ax.set_title("Native-gas rows preserve the physical inventory beneath CO$_2$e",
                 loc="left", fontsize=11)
    ax.legend(frameon=False, fontsize=8, ncol=3, loc="lower right")
    _style(ax)
    return _save(fig, "fugitives_streams.png")


def fugitives_gas_flow_ufg():
    flows = _read("fugitives_gas_flow_balance_2022_2024.csv")
    compatibility = _read("fugitives_ufg_network_compatibility_2024.csv")
    if not flows or not compatibility:
        return None
    plt = _plt()
    fig, axes = plt.subplots(1, 2, figsize=(9.0, 3.7))
    years = [int(row["fiscal_year"]) for row in flows]
    supply = [float(row["reported_total_supply_mmcfd"]) for row in flows]
    use = [float(row["categorized_consumption_mmcfd"]) for row in flows]
    ufg = [float(row["ufg_mmcfd"]) for row in flows]
    gross = [float(row["gross_domestic_production_mmcfd"]) for row in flows]
    marketable = [float(row["indigenous_marketable_supply_mmcfd"]) for row in flows]
    axes[0].plot(years, gross, marker="^", linestyle="--", color=PALETTE[4],
                 label="gross domestic production")
    axes[0].plot(years, marketable, marker="v", linestyle=":", color=PALETTE[6],
                 label="indigenous marketable")
    axes[0].plot(years, supply, marker="o", color=PALETTE[0], label="reported supply")
    axes[0].plot(years, use, marker="s", color=PALETTE[2], label="categorized use")
    axes[0].bar(years, ufg, color=PALETTE[7], alpha=0.65, label="UFG")
    axes[0].set_xticks(years)
    axes[0].set_ylabel("MMCFD")
    axes[0].set_title("Gas-flow controls", loc="left", fontsize=10)
    axes[0].legend(frameon=False, fontsize=7)
    _style(axes[0])
    keep = [row for row in compatibility if row["scenario"] in
            ("reference", "lower_practices", "throughput", "lower_throughput")]
    labels = [row["scenario"].replace("_", " ") for row in keep]
    values = [float(row["ufg_physical_fraction_required_pct"]) for row in keep]
    axes[1].barh(labels, values, color=[PALETTE[1], PALETTE[2], PALETTE[5], PALETTE[6]])
    axes[1].axvline(10, color="#777777", linestyle=":", linewidth=1)
    axes[1].axvline(25, color="#333333", linestyle="--", linewidth=1)
    for index, value in enumerate(values):
        axes[1].annotate("%.1f%%" % value, (value, index), textcoords="offset points",
                         xytext=(4, -3), fontsize=8)
    axes[1].set_xlabel("Share of UFG required to be physical CH$_4$ loss")
    axes[1].set_title("Network plausibility", loc="left", fontsize=10)
    _style(axes[1])
    fig.suptitle("UFG constrains physical plausibility but is not itself an emission estimate",
                 x=0.08, ha="left", fontsize=11)
    return _save(fig, "fugitives_gas_flow_ufg.png")


def fugitives_uncertainty_attribution():
    rows = _read("fugitives_uncertainty_attribution_2024.csv")[:8]
    if not rows:
        return None
    labels = [row["input_group"].replace("factor:", "").replace("_", " ")
              .replace("activity-source:", "activity: ")
              .replace("activity-residual:", "coverage: ") for row in rows][::-1]
    values = [float(row["normalized_squared_spearman_pct"]) for row in rows][::-1]
    plt = _plt()
    fig, ax = plt.subplots(figsize=(7.8, 3.8))
    ax.barh(labels, values, color=PALETTE[5], edgecolor="white")
    ax.set_xlabel("Normalized squared Spearman sensitivity (%)")
    ax.set_title("Distribution and post-meter factors dominate conditional uncertainty",
                 loc="left", fontsize=11)
    _style(ax)
    return _save(fig, "fugitives_uncertainty_attribution.png")


def ippu_framework():
    """Scientific workflow from activity evidence to evaluated IPPU estimates."""
    plt = _plt()
    from matplotlib.patches import FancyBboxPatch
    fig, ax = plt.subplots(figsize=(9.0, 3.5))
    ax.set_xlim(0, 12.4)
    ax.set_ylim(0, 4.6)
    ax.axis("off")
    boxes = [
        (0.2, 1.55, 2.7, 1.4, "Pakistan activity +\nIPCC methods",
         "production • trade • companies\ncategory-specific methods"),
        (3.35, 1.55, 2.7, 1.4, "Material\nbalances",
         "clinker • ammonia CO₂ recovery\nF-gas equipment stocks"),
        (6.50, 1.55, 2.7, 1.4, "Estimates +\nuncertainty",
         "process activity • factors\nstructural + parametric cases"),
        (9.65, 1.55, 2.55, 1.4, "Evaluation",
         "producer data • official CRT\nfacilities • completeness"),
    ]
    for x, y, width, height, title, detail in boxes:
        patch = FancyBboxPatch((x, y), width, height, boxstyle="round,pad=0.04",
                               facecolor="#eaf1f6", edgecolor="#5b7891", linewidth=1.0)
        ax.add_patch(patch)
        ax.text(x + width / 2, y + height * 0.68, title, ha="center", va="center",
                fontsize=9.4, fontweight="bold")
        ax.text(x + width / 2, y + height * 0.25, detail, ha="center", va="center",
                fontsize=7.4)
    for start, end in [((2.9, 2.25), (3.35, 2.25)),
                       ((6.05, 2.25), (6.50, 2.25)),
                       ((9.20, 2.25), (9.65, 2.25))]:
        ax.annotate("", xy=end, xytext=start,
                    arrowprops={"arrowstyle": "->", "color": "#6c7d88", "lw": 1.1})
    ax.text(0.2, 4.25, "From industrial activity data to evaluated IPPU estimates",
            fontsize=12, fontweight="bold", ha="left")
    return _save(fig, "ippu_framework.png")


def ippu_cement_evidence():
    """Valid cement models, superseded benchmarks and conditional intervals."""
    scenarios = _read("ippu_cement_valid_structural_2024.csv")
    benchmarks = _read("ippu_cement_method_benchmarks_2024.csv")
    intervals = _read("ippu_cement_conditional_intervals_2024.csv")
    if not scenarios or not benchmarks or not intervals:
        return None
    plt = _plt()
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 4.0), gridspec_kw={"width_ratios": [1.25, 1]})
    labels = [("producer census (reference)" if not row["clinker_fraction"]
               else "FY2024, trade, f=%s" % row["clinker_fraction"])
              for row in scenarios]
    values = [float(row["co2e_Mt_AR5"]) for row in scenarios]
    colors = [PALETTE[5]] * len(scenarios)
    for row in benchmarks:
        labels.append("benchmark: " + ("omit FY2024 trade" if
                      row["benchmark_id"] == "cement_no_trade_method_benchmark" else
                      "original misdated/no-trade"))
        values.append(float(row["co2e_Mt_AR5"]))
        colors.append("#9aa3aa")
    order = sorted(range(len(values)), key=lambda index: values[index])
    axes[0].barh([labels[index] for index in order], [values[index] for index in order],
                 color=[colors[index] for index in order], edgecolor="white")
    for y, index in enumerate(order):
        axes[0].annotate("%.2f" % values[index], (values[index], y),
                         textcoords="offset points", xytext=(4, -3), fontsize=7.5)
    axes[0].set_xlabel("Mt CO$_2$")
    axes[0].set_title("Valid models and method benchmarks", loc="left", fontsize=10)
    _style(axes[0])

    short = {"reference": "reference f=0.75",
             "all-Portland upper clinker fraction": "upper f=0.95"}
    labels = [short.get(row["configuration"], row["configuration"])
              for row in intervals][::-1]
    medians = [float(row["p50_mt_co2"]) for row in intervals][::-1]
    lows = [float(row["p025_mt_co2"]) for row in intervals][::-1]
    highs = [float(row["p975_mt_co2"]) for row in intervals][::-1]
    axes[1].errorbar(medians, range(len(labels)),
                     xerr=[[median - low for median, low in zip(medians, lows)],
                           [high - median for median, high in zip(medians, highs)]],
                     fmt="o", color=PALETTE[1], capsize=3)
    axes[1].set_yticks(range(len(labels)))
    axes[1].set_yticklabels(labels, fontsize=8)
    axes[1].set_xlabel("Mt CO$_2$")
    axes[1].set_title("Conditional 95% intervals", loc="left", fontsize=10)
    _style(axes[1])
    fig.suptitle("Observed trade is mandatory; clinker content remains structural",
                 x=0.08, ha="left", fontsize=11)
    return _save(fig, "ippu_cement_evidence.png")


def ippu_producer_census():
    """Observed clinker disclosures and their relation to national Tier-1 inferences."""
    rows = _read("ippu_cement_producer_census_2024.csv")
    scenarios = _read("ippu_cement_valid_structural_2024.csv")
    if not rows or not scenarios:
        return None
    observed = sorted([row for row in rows if _num(row, "clinker_production_t") is not None],
                      key=lambda row: float(row["clinker_production_t"]), reverse=True)
    unresolved = [row for row in rows if _num(row, "clinker_production_t") is None]
    short_name = {"D.G. Khan Cement Company Limited": "D.G. Khan",
                  "Maple Leaf Cement Factory Limited": "Maple Leaf",
                  "Fauji Cement Company Limited": "Fauji",
                  "Attock Cement Pakistan Limited": "Attock",
                  "Flying Cement Company Limited": "Flying"}
    labels = [short_name.get(row["company"], row["company"].replace(" Cement Limited", "")
                             .replace(" Cement Company Limited", "")) for row in observed]
    values = [float(row["clinker_production_t"]) / 1e6 for row in observed]
    # The rc30 census reference row carries no clinker fraction (production is
    # observed directly, so its cell is empty by design) - skip it when pulling
    # the structural-model bracket, or float('') aborts the whole figure run,
    # which is exactly what silently froze these PNGs from rc30 to rc32.
    low = next(float(row["clinker_production_kt"]) / 1000.0 for row in scenarios
               if row["clinker_fraction"] and float(row["clinker_fraction"]) == 0.75)
    high = next(float(row["clinker_production_kt"]) / 1000.0 for row in scenarios
                if row["clinker_fraction"] and float(row["clinker_fraction"]) == 0.95)
    cumulative, running = [], 0.0
    for value in values:
        running += value
        cumulative.append(running)
    plt = _plt()
    fig, axes = plt.subplots(1, 2, figsize=(10.4, 4.6),
                             gridspec_kw={"width_ratios": [1.25, 1.0]})
    positions = list(range(len(values)))
    axes[0].barh(positions, values, color=PALETTE[0], edgecolor="white")
    axes[0].set_yticks(positions)
    axes[0].set_yticklabels(labels, fontsize=7)
    axes[0].invert_yaxis()
    axes[0].set_xlabel("Reported FY2023–24 clinker (Mt)")
    words = {15: "Fifteen", 16: "Sixteen", 17: "Seventeen"}
    axes[0].set_title("%s producer disclosures" % words.get(len(observed), str(len(observed))),
                      loc="left", fontsize=10)
    _style(axes[0])
    axes[1].plot(range(1, len(cumulative) + 1), cumulative, marker="o", markersize=3.5,
                 color=PALETTE[1], linewidth=1.6, label="observed cumulative")
    axes[1].axhline(low, color=PALETTE[5], linestyle="--", linewidth=1.2,
                    label="Tier 1, f=0.75")
    axes[1].axhline(high, color=PALETTE[7], linestyle=":", linewidth=1.5,
                    label="Tier 1, f=0.95")
    axes[1].scatter([len(observed) + index + 1 for index in range(len(unresolved))],
                    [cumulative[-1]] * len(unresolved), marker="x", color="#555555", s=35)
    for index, row in enumerate(unresolved):
        axes[1].annotate(short_name.get(row["company"], row["company"].split()[0]),
                         (len(observed) + index + 1, cumulative[-1]),
                         textcoords="offset points", xytext=(0, -12 - index * 9),
                         ha="center", fontsize=7)
    axes[1].set_xticks(range(2, len(rows) + 1, 2))
    axes[1].set_xlabel("Producer records accumulated")
    axes[1].set_ylabel("Cumulative clinker (Mt)")
    axes[1].set_title("Observed subset tests the activity boundary", loc="left", fontsize=10)
    axes[1].legend(frameon=False, fontsize=7, loc="lower right")
    _style(axes[1])
    fig.suptitle("Company evidence exceeds the low-clinker inference and nearly reaches the high case",
                 x=0.08, ha="left", fontsize=11)
    return _save(fig, "ippu_producer_census.png")


def ippu_official_audit():
    """Official CRT category composition and public-data completeness status."""
    summary = _read("ippu_unfccc_crt_summary_2022.csv")
    completeness = _read("ippu_completeness_2024.csv")
    if not summary or not completeness:
        return None
    rows = [row for row in summary if row["category"].startswith(
        ("2.A.  ", "2.B.  ", "2.C.  ", "2.D.  ", "2.E.  ", "2.F.  ", "2.G.  ", "2.H.  "))]
    values, labels = [], []
    for row in rows:
        value = _num(row, "total_co2e_kt")
        if value is not None and value > 0:
            values.append(value / 1000.0)
            labels.append(row["category"].split(".", 1)[-1].strip())
    plt = _plt()
    fig, axes = plt.subplots(1, 2, figsize=(8.8, 3.5))
    order = sorted(range(len(values)), key=lambda index: values[index])
    axes[0].barh([labels[index] for index in order], [values[index] for index in order],
                 color=PALETTE[0], edgecolor="white")
    axes[0].set_xscale("log")
    axes[0].set_xlabel("Official 2022 Mt CO$_2$e (log scale)")
    axes[0].set_title("Pakistan CRT category composition", loc="left", fontsize=10)
    _style(axes[0])
    selected = ["2.A.1", "2.A.2", "2.A.3", "2.B.1", "2.B.2", "2.C.1",
                "2.D.1", "2.F.1", "2.G.1"]
    selected_rows = [next(row for row in completeness if row["ipcc_code"] == code)
                     for code in selected]
    state = []
    for row in selected_rows:
        if row["notation_key_2024"] == "E":
            state.append(2)
        elif row["source_role"] == "control":
            state.append(1)
        else:
            state.append(0)
    from matplotlib.colors import ListedColormap
    axes[1].imshow([state], aspect="auto",
                   cmap=ListedColormap(["#d9d9d9", PALETTE[7], PALETTE[2]]), vmin=0, vmax=2)
    axes[1].set_xticks(range(len(selected)))
    axes[1].set_xticklabels(selected, rotation=45, ha="right", fontsize=7)
    axes[1].set_yticks([0])
    axes[1].set_yticklabels(["FY2023–24"])
    for index, value in enumerate(state):
        axes[1].text(index, 0, ("E" if value == 2 else "control" if value == 1 else "acquire"),
                     ha="center", va="center", rotation=90, fontsize=6.5,
                     color="white" if value == 2 else "#333333")
    axes[1].set_title("Evidence status of material modules", loc="left", fontsize=10)
    fig.suptitle("Official reporting is broad; the new public-data estimate is evidence-gated",
                 x=0.08, ha="left", fontsize=11)
    return _save(fig, "ippu_official_audit.png")


def transport_framework():
    """The re-anchored transport calculation: OCAC customer-class ledger to outputs."""
    plt = _plt()
    from matplotlib.patches import FancyBboxPatch
    fig, ax = plt.subplots(figsize=(9.6, 4.1))
    ax.set_xlim(0, 12.4)
    ax.set_ylim(0, 5.2)
    ax.axis("off")
    boxes = [
        (0.2, 2.0, 2.7, 1.5, "OCAC sectoral\nsales ledger",
         "customer class × product, t\nclasses sum to national exactly"),
        (3.35, 2.0, 2.7, 1.5, "Road controls\n(FY2021-22)",
         "petrol 9,128 kt • diesel 7,887 kt\nbulk rows excluded by construction"),
        (6.50, 2.0, 2.7, 1.5, "Fleet allocation",
         "registrations × VKT shares\noff-road partition • class split"),
        (9.65, 2.0, 2.55, 1.5, "Outputs",
         "by class, gas, province\nledger • scenarios • series"),
    ]
    for x, y, width, height, title, detail in boxes:
        patch = FancyBboxPatch((x, y), width, height, boxstyle="round,pad=0.04",
                               facecolor="#eaf1f6", edgecolor="#5b7891", linewidth=1.0)
        ax.add_patch(patch)
        ax.text(x + width / 2, y + height * 0.70, title, ha="center", va="center",
                fontsize=9.2, fontweight="bold")
        ax.text(x + width / 2, y + height * 0.24, detail, ha="center", va="center",
                fontsize=7.2)
    for start, end in [((2.9, 2.75), (3.35, 2.75)),
                       ((6.05, 2.75), (6.50, 2.75)),
                       ((9.20, 2.75), (9.65, 2.75))]:
        ax.annotate("", xy=end, xytext=start,
                    arrowprops={"arrowstyle": "->", "color": "#6c7d88", "lw": 1.1})
    # The cross-sector relays and the unresolved residual, below the main flow.
    small = [
        (0.9, 0.35, 2.3, 1.0, "Railways module", "Year Book 112 kt vs\nOCAC 118 kt: cross-check",
         "dashed", (3.6, 1.05, 4.05, 2.0)),
        (4.15, 0.35, 2.3, 1.0, "Residential module", "generator petrol 56 kt\ncarved out by relay",
         "solid", (5.3, 1.35, 4.7, 2.0)),
        (7.4, 0.35, 2.6, 1.0, "Unresolved (retail)", "agri-stationary + captive\ninside Road, bounded",
         "dashed", (7.6, 1.35, 6.0, 2.02)),
    ]
    for x, y, w, h, title, detail, style, arrow in small:
        patch = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.04",
                               facecolor="#f7f3ea" if style == "dashed" else "#eaf1f6",
                               edgecolor="#8a7d5b" if style == "dashed" else "#5b7891",
                               linewidth=1.0,
                               linestyle="dashed" if style == "dashed" else "solid")
        ax.add_patch(patch)
        ax.text(x + w / 2, y + h * 0.68, title, ha="center", va="center",
                fontsize=8.0, fontweight="bold")
        ax.text(x + w / 2, y + h * 0.24, detail, ha="center", va="center", fontsize=6.8)
        ax.annotate("", xy=(arrow[2], arrow[3]), xytext=(arrow[0], arrow[1]),
                    arrowprops={"arrowstyle": "->", "color": "#8a7d5b", "lw": 1.0,
                                "linestyle": "dashed" if style == "dashed" else "solid"})
    ax.text(0.2, 4.85, "Fuel controls set the magnitude; the fleet model distributes it",
            fontsize=12, fontweight="bold", ha="left")
    return _save(fig, "transport_framework.png")


def transport_composition():
    """CO2 by class and fuel (left) beside the small CH4/N2O panel (right)."""
    plt = _plt()
    rows = _read("transport_by_stream_2022.csv")
    co2, trace = {}, {"CH4": 0.0, "N2O": 0.0}
    for r in rows:
        v = float(r["co2e_Mt_AR5"])
        if r["gas"] == "CO2":
            sub = r["subitem"].rsplit(" ", 1)[0]
            label = "Off-road (mixed)" if "Off-road" in sub else sub
            co2[label] = co2.get(label, 0.0) + v
        else:
            trace[r["gas"]] += v
    ordered = sorted(co2.items(), key=lambda kv: kv[1])
    fig, (ax1, ax2) = plt.subplots(
        1, 2, figsize=(9.0, 4.2), gridspec_kw={"width_ratios": [3.0, 1.0]})
    ax1.barh([k for k, _ in ordered], [v for _, v in ordered], color="#5b7891")
    ax1.set_xlabel("Mt CO$_2$ (AR5)")
    ax1.set_title("CO$_2$ by class and fuel", fontsize=10, loc="left")
    for i, (_k, v) in enumerate(ordered):
        ax1.text(v + 0.18, i, "%.1f" % v, va="center", fontsize=7.5)
    ax1.set_xlim(0, max(v for _k, v in ordered) * 1.12)
    ax2.bar(list(trace), list(trace.values()), color="#8a7d5b", width=0.6)
    ax2.set_ylabel("Mt CO$_2$e (AR5)")
    ax2.set_title("Trace gases", fontsize=10, loc="left")
    for i, (_k, v) in enumerate(trace.items()):
        ax2.text(i, v + 0.015, "%.2f" % v, ha="center", fontsize=7.5)
    fig.tight_layout()
    return _save(fig, "transport_composition.png")


def transport_provincial_proxy_gap():
    """The failure diagnostic: fuel-sales allocation vs the registration proxy."""
    plt = _plt()
    import numpy as np
    rows = _read("transport_provincial_proxy_comparison_2022.csv")
    provinces = [r["province"] for r in rows]
    fuel = [float(r["fuel_sales_Mt"]) for r in rows]
    reg = [float(r["registration_Mt"]) for r in rows]
    x = np.arange(len(provinces))
    fig, ax = plt.subplots(figsize=(7.4, 3.6))
    ax.bar(x - 0.19, fuel, width=0.38, label="Fuel sales (OCAC provincial)",
           color="#5b7891")
    ax.bar(x + 0.19, reg, width=0.38, label="Vehicle registration (superseded)",
           color="#c4a35a")
    ax.set_xticks(x)
    ax.set_xticklabels(provinces, rotation=12, fontsize=8)
    ax.set_ylabel("Mt CO$_2$e (AR5)")
    ax.legend(fontsize=8, frameon=False)
    ax.set_title("Where the registration proxy failed: Sindh carries the Karachi "
                 "port traffic its registrations never showed", fontsize=9.5,
                 loc="left")
    fig.tight_layout()
    return _save(fig, "transport_provincial_proxy_gap.png")


def transport_fuel_series():
    """The fuel-based national series - nine OCAC years, petroleum and incl-CNG."""
    plt = _plt()
    rows = _read("transport_fuel_series.csv")
    years = [r["fy_label"].replace("FY", "") for r in rows]
    petroleum = [float(r["co2e_Mt_AR5_petroleum"]) for r in rows]
    incl = [float(r["co2e_Mt_AR5_incl_cng"]) if r["co2e_Mt_AR5_incl_cng"] else None
            for r in rows]
    fig, ax = plt.subplots(figsize=(7.8, 3.6))
    ax.plot(years, petroleum, marker="o", color="#5b7891",
            label="Road petrol + diesel (whole Road class)")
    xi = [i for i, v in enumerate(incl) if v is not None]
    ax.plot([years[i] for i in xi], [incl[i] for i in xi], marker="s",
            color="#8a7d5b", linestyle="--", label="incl. CNG (to FY2023-24)")
    ax.set_ylabel("Mt CO$_2$e (AR5)")
    ax.tick_params(axis="x", labelsize=7.5, rotation=25)
    ax.legend(fontsize=8, frameon=False)
    ax.set_title("The fuel-based series the anchoring philosophy makes possible "
                 "without a fleet history", fontsize=9.5, loc="left")
    fig.tight_layout()
    return _save(fig, "transport_fuel_series.png")


def build_all():
    """Every figure. Returns the list of basenames written."""
    written = []
    for sector in SECTOR_FILES:
        for fn in (sector_streams, sector_provincial, sector_timeseries,
                   sector_sensitivity, sector_activity, sector_air):
            name = fn(sector)
            if name:
                written.append(name)
    for fn in (national_sectors, national_key_categories, national_uncertainty,
               national_series,
               national_structural_bridge, national_seasonality,
               national_monthly_crosschecks,
               national_air_pollutants, waste_partition, aviation_reconciliation,
               aviation_structural_uncertainty, aviation_framework,
               aviation_source_row_bridge, aviation_component_offsets,
               aviation_monthly_closure, aviation_two_year_comparison,
               aviation_resolution_ladders, aviation_uncertainty_sensitivity,
               aviation_m2_uncertainty,
               aviation_long_run_controls, aviation_official_reporting,
               aviation_climatetrace_airports, aviation_era5_weather_audit,
               fugitives_framework, fugitives_method_ladder,
               fugitives_structural_uncertainty, fugitives_native_gases,
               fugitives_gas_flow_ufg, fugitives_uncertainty_attribution,
               fugitives_observations, fugitives_official_comparison):
        name = fn()
        if name:
            written.append(name)
    for fn in (ippu_framework, ippu_cement_evidence, ippu_producer_census,
               ippu_official_audit):
        name = fn()
        if name:
            written.append(name)
    for fn in (transport_framework, transport_composition,
               transport_provincial_proxy_gap, transport_fuel_series):
        name = fn()
        if name:
            written.append(name)
    return written


def main():
    try:
        _plt()
    except Exception as exc:                                    # pragma: no cover
        print("matplotlib unavailable (%s); no figures written." % exc)
        return
    written = build_all()
    print("Wrote %d figures to %s" % (len(written), os.path.relpath(FIGDIR, os.getcwd())))
    by_sector = {}
    for name in written:
        by_sector.setdefault(name.split("_")[0], []).append(name)
    for key in sorted(by_sector):
        print("  %-13s %s" % (key, ", ".join(sorted(by_sector[key]))))
    missing = [s for s in SECTOR_FILES
               if not any(n.startswith(s + "_") for n in written)]
    if missing:
        print("  no figures for: %s" % ", ".join(sorted(missing)))


if __name__ == "__main__":
    main()
