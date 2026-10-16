"""One figure system for the manuscript: sizes, type, colour and glyphs, set once.

WHY THIS EXISTS. The seven figures of the v2 manuscript were drawn by three scripts, each with
its own rcParams and its own palette, and placed by LaTeX at `\\textwidth` or `\\columnwidth` with
a height cap. Two consequences reached print. A single-column figure doubled in the review
layout, where the column IS the text block, and its labels were set at 16.9 pt. A tall figure was
shrunk by the height cap, by a different factor in each layout, to 4.6 pt in one and 5.2 pt in
the other. Neither was a property of the figure; both came from letting the page decide the size.

So the size is decided HERE, from the class: a figure is drawn at one of two physical widths, no
taller than the review page allows, and included at that width in both layouts. What is 8 pt in
the script is 8 pt on the page.

WHAT A COLOUR MEANS is fixed per variable and never shared between variables: a gas is always
its gas colour, an evidence class its class colour, a proxy surface its surface colour. A panel
that needs none of those is neutral with one accent.

WHAT A GLYPH MEANS is fixed across figures: a filled diamond is a deterministic estimate, a short
tick is an ensemble median, a bar is a percentile interval, an open circle is an alternative (a
factor substitution, another weighting), a square is a total and a grey filled circle is another
inventory's value. Two figures used one circle for a median and for a deterministic difference.

ONE FONT, ONE WEIGHT. The journal counts regular, bold and italic as three fonts, each embedded
and each a production cost. Everything is DejaVu Sans regular, and gas formulae are written with
Unicode subscripts, so no mathtext font is embedded beside it.
"""
import os

MM = 1.0 / 25.4

# copernicus.cls: \textwidth 177 mm in both layouts; \columnwidth (177 - 7) / 2 = 85 mm in the
# two-column one. The review layout's text block is 587 pt high, the shorter of the two.
FULL_WIDTH = 177.0 * MM
COLUMN_WIDTH = 85.0 * MM
REVIEW_TEXT_HEIGHT = 587.2 / 72.0
MAX_HEIGHT = 0.70 * REVIEW_TEXT_HEIGHT       # caption and float separation take the rest

# points, at the size the figure is printed
SIZE_TICK = 8.0          # ticks, legends, annotations, direct labels
SIZE_LABEL = 9.0         # axis titles
SIZE_HEAD = 10.0         # panel headings
SIZE_FLOOR = 7.5         # nothing a reader needs is smaller than this

INK = "#1b1f23"          # text and the marks that carry a value
MUTED = "#59616a"        # secondary text, axes
RULE = "#aab1b9"         # reference lines
GRID = "#e4e7ea"         # grid lines, visible in print and behind everything
FILL = "#eef1f4"         # a band or a neutral node
PAPER = "#ffffff"
# THE ACCENT IS NOT A GAS COLOUR. It was #0072B2, which is also CO2: blue then meant "carbon
# dioxide" in one figure and "everything" in four others, one of them a figure of N2O alone.
ACCENT = "#4a5b6c"       # the one accent of a panel that needs one: a slate, no gas and no class
NEUTRAL = "#8b939c"      # a comparator, or a bar that is context

# A GAS IS ALWAYS THIS COLOUR, and is always labelled in words as well.
GAS = {"CO2": "#0072B2", "CH4": "#D55E00", "N2O": "#009E73"}
GAS_LABEL = {"CO2": "CO₂", "CH4": "CH₄", "N2O": "N₂O"}
GAS_DASH = {"CO2": "-", "CH4": (0, (5, 1.6)), "N2O": (0, (1.4, 1.4))}

# THE EVIDENCE BEHIND A SPATIAL WEIGHT, in the order it is stacked: the year's own activity
# first. Lightness separates the classes in greyscale; the rescaled class is hatched as well,
# because its lightness is the nearest to its neighbour's.
EVIDENCE = (
    ("annual_observed_activity", "Observed own-period activity", "#08306b", None),
    ("calendar_activity_proxy", "Calendar-year activity proxy", "#2171b5", ".."),
    ("modelled_population_proxy", "Modelled population proxy", "#6baed6", None),
    ("static_structural", "Timeless structural surface", "#c6dbef", None),
    ("reference_shape_backcast", "Reference pattern, backcast", "#fdd0a2", "////"),
    ("reference_shape_forward", "Reference pattern, later reuse", "#fdae6b", "\\\\"),
    ("substituted_surface", "Declared stand-in surface", "#d94801", None),
    ("unallocated", "Retained at province level", "#252525", None),
)

# WHICH SURFACE PLACED THE MASS. A different variable from the evidence class, so a different
# set of colours: none of these is an evidence colour or a gas colour. Neighbours in the bars
# differ in lightness as well as hue: built-up area was an olive that printed as the same grey
# as the livestock segment beside it, which the greyscale simulation showed and the screen hid.
PROXY = (
    ("points", "Facility and site locations", "#332288"),
    ("roads", "Roads (OpenStreetMap 2026)", "#88CCEE"),
    ("builtup", "Built-up area (WorldCover 2021)", "#117733"),
    ("livestock", "Livestock (GLW 2020)", "#CC6677"),
    ("cropland", "Cropland (WorldCover 2021)", "#DDCC77"),
    ("manure", "Cropland × livestock (derived)", "#AA4499"),
    ("rice", "Rice area (MapSPAM 2020)", "#44AA99"),
    ("population", "Population (WorldPop 2020)", "#882255"),
    ("other", "Other surfaces", "#BBBBBB"),
    # not a surface at all: mass no surface placed, kept so that the shares sum to the whole
    ("kept", "Retained at province level", "#252525"),
)

# THE MAIN FIGURES, in manuscript order, named as the journal asks (f01, f02, ...). One list:
# the plotting scripts write these, the build phase declares them, and the guards walk them, so
# a figure cannot be added, renamed or split without every one of those noticing.
LEGACY_FIGURES = ("f01_construction", "f02_inventory", "f03_evidence_uncertainty", "f04_gas_maps",
                  "f05_spatial_evidence", "f06_proxy_concentration", "f07_btr_ratios", "f08_managed_soils")
FIGURES = ("f09_integrated_composition", "f10_integrated_trends", "f12_air_sensitivity",
           "f11_integrated_maps", "f13_air_evaluation")
NARROW = ("f08_managed_soils",)                  # drawn and placed at the column width
FIGURE_SCRIPTS = ("paper_national/figures/rewrite_inputs/plot_construction.py",
                  "paper_national/figures/rewrite_inputs/plot_figures.py",
                  "scripts/make_fig_ghg_grid.py", "scripts/build_integrated_figures.py")

LW_AXIS = 0.6
LW_GRID = 0.5
LW_CURVE = 1.2
LW_INTERVAL = 2.0

_FISCAL_DASH = "–"


def thousands(value):
    """33674 -> '33 674': a thin space, as the manuscript sets its numbers, never a comma."""
    return "{:,}".format(int(round(value))).replace(",", "\u2009")


def fiscal(period_id):
    """'FY2023-24' -> '2023–24', the form the manuscript prints."""
    return str(period_id).replace("FY", "").replace("-", _FISCAL_DASH)


def use():
    """Apply the style. Called once by each plotting script, before any figure is made."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.weight": "normal", "font.size": SIZE_TICK,
        "axes.titlesize": SIZE_HEAD, "axes.titleweight": "normal", "axes.titlecolor": INK,
        "axes.labelsize": SIZE_LABEL, "axes.labelcolor": INK, "axes.labelweight": "normal",
        "axes.edgecolor": MUTED, "axes.linewidth": LW_AXIS,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.axisbelow": True, "axes.unicode_minus": True,
        "xtick.labelsize": SIZE_TICK, "ytick.labelsize": SIZE_TICK,
        "xtick.color": MUTED, "ytick.color": MUTED,
        "xtick.labelcolor": INK, "ytick.labelcolor": INK,
        "xtick.major.width": LW_AXIS, "ytick.major.width": LW_AXIS,
        "xtick.major.size": 3.0, "ytick.major.size": 3.0,
        "grid.color": GRID, "grid.linewidth": LW_GRID,
        "lines.linewidth": LW_CURVE, "lines.solid_capstyle": "butt",
        "legend.fontsize": SIZE_TICK, "legend.frameon": False,
        "legend.handlelength": 1.4, "legend.handleheight": 0.9, "legend.borderaxespad": 0.0,
        "hatch.linewidth": 0.5, "hatch.color": "#9a5b1e",
        "figure.facecolor": PAPER, "axes.facecolor": PAPER, "savefig.facecolor": PAPER,
        "figure.dpi": 100, "savefig.dpi": 300,
        "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none",
        "text.usetex": False,
    })
    return plt


def figure(width, height):
    """A figure at its printed size. Width is one of the two the class gives; height is held
    under what the review page can carry, so no height cap ever rescales it."""
    import matplotlib.pyplot as plt
    if abs(width - FULL_WIDTH) > 1e-6 and abs(width - COLUMN_WIDTH) > 1e-6:
        raise ValueError("a figure is %.0f mm or %.0f mm wide, not %.1f mm"
                         % (FULL_WIDTH / MM, COLUMN_WIDTH / MM, width / MM))
    if height > MAX_HEIGHT:
        raise ValueError("%.2f in is taller than the review page carries (%.2f in)"
                         % (height, MAX_HEIGHT))
    return plt.figure(figsize=(width, height))


def panel(ax, letter, title="", x=0.0, pad=5.0):
    """'(a) Calculation modules', left-aligned above the axes, regular weight."""
    text = "(%s)" % letter + (" %s" % title if title else "")
    ax.set_title(text, loc="left", x=x, pad=pad, fontsize=SIZE_HEAD, color=INK)


def quiet(ax, grid=None, keep=("left", "bottom")):
    """Quiet axes: only the spines that carry a scale, and a grid across the value axis."""
    for side in ("left", "bottom", "top", "right"):
        ax.spines[side].set_visible(side in keep)
    if "left" not in keep:
        ax.tick_params(axis="y", length=0)
    if "bottom" not in keep:
        ax.tick_params(axis="x", length=0)
    if grid:
        ax.grid(axis=grid)


# --- the glyph grammar -------------------------------------------------------------------------

def deterministic(ax, x, y, size=5.2, color=INK, **kw):
    """A deterministic estimate: filled diamond."""
    return ax.plot([x], [y], marker="D", markersize=size, color=color, markeredgecolor=color,
                   linestyle="none", zorder=5, **kw)[0]


def median(ax, x, y, half=0.16, color=INK, vertical=True, **kw):
    """An ensemble median: a short tick across the interval."""
    if vertical:
        return ax.plot([x, x], [y - half, y + half], color=color, linewidth=1.3, zorder=4, **kw)[0]
    return ax.plot([x - half, x + half], [y, y], color=color, linewidth=1.3, zorder=4, **kw)[0]


def interval(ax, low, high, y, color=ACCENT, **kw):
    """A percentile interval: a bar from one end to the other."""
    return ax.plot([low, high], [y, y], color=color, linewidth=LW_INTERVAL,
                   solid_capstyle="butt", zorder=3, **kw)[0]


def alternative(ax, x, y, size=5.4, color=ACCENT, **kw):
    """A structural alternative: open circle."""
    return ax.plot([x], [y], marker="o", markersize=size, markerfacecolor=PAPER,
                   markeredgecolor=color, markeredgewidth=1.3, linestyle="none", zorder=5, **kw)[0]


def comparator(ax, x, y, size=5.4, **kw):
    """Another inventory's value: a grey filled circle."""
    return ax.plot([x], [y], marker="o", markersize=size, color=NEUTRAL, linestyle="none",
                   zorder=5, **kw)[0]


def glyph_handles(*kinds, color=ACCENT):
    """Legend handles for the glyphs a panel uses, in the order given."""
    from matplotlib.lines import Line2D
    made = {
        "deterministic": Line2D([], [], marker="D", markersize=5.2, color=INK, linestyle="none",
                                label="Deterministic estimate"),
        "median": Line2D([], [], marker="|", markersize=7.0, markeredgewidth=1.3, color=INK,
                         linestyle="none", label="Ensemble median"),
        "interval": Line2D([], [], color=color, linewidth=LW_INTERVAL,
                           label="95 % interval"),
        "alternative": Line2D([], [], marker="o", markersize=5.4, markerfacecolor=PAPER,
                              markeredgecolor=color, markeredgewidth=1.3, linestyle="none",
                              label="Alternative factors"),
        "total": Line2D([], [], marker="s", markersize=5.0, color=INK, linestyle="none",
                        label="Total"),
        "comparator": Line2D([], [], marker="o", markersize=5.4, color=NEUTRAL, linestyle="none",
                             label="External comparator"),
    }
    return [made[k] for k in kinds]


# --- saving ------------------------------------------------------------------------------------

def release_version():
    import pkinv
    return pkinv.__version__


def save(fig, stem, figures_dir, preview_dir, script, title, configuration="S_TAN"):
    """The PDF beside the manuscript and a PNG preview beside the script.

    THE RELEASE IS IN THE FILE, NOT ON THE PLOT. A version string printed under a title is
    plot text a reader has to step over and a caption already carries; removing it would have
    switched off the guard that reads it. The identity lives in the PDF's metadata instead,
    where tests/test_v3_documents.py reads it for every figure, not for two.

    No creation date is written, so the same inputs give the same bytes.
    """
    os.makedirs(figures_dir, exist_ok=True)
    os.makedirs(preview_dir, exist_ok=True)
    width, height = fig.get_size_inches()
    figure_check = (abs(width - FULL_WIDTH) < 1e-6 or abs(width - COLUMN_WIDTH) < 1e-6)
    if not figure_check or height > MAX_HEIGHT:
        raise ValueError("%s is %.2f x %.2f in, outside the two widths and the height limit"
                         % (stem, width, height))
    meta = {"Title": title, "Author": "PakEmis",
            "Subject": "PakEmis %s; configuration %s" % (release_version(), configuration),
            "Keywords": "release=%s; configuration=%s; script=%s"
                        % (release_version(), configuration, script),
            "Creator": script, "Producer": "Matplotlib", "CreationDate": None}
    pdf = os.path.join(figures_dir, stem + ".pdf")
    fig.savefig(pdf, format="pdf", metadata=meta)
    fig.savefig(os.path.join(preview_dir, stem + ".png"), format="png", dpi=200,
                metadata={"Software": None})
    import matplotlib.pyplot as plt
    plt.close(fig)
    return pdf
