"""Figures 2, 3, 7 and 8: composition and history, timing evidence and the parameter interval,
the ratios to the national submission, and the managed-soils factor cases.

Every value is read from a table under data/, which scripts/build_rewrite_figure_data.py builds
from the released products and tests/test_rewrite_figure_data.py holds to a fresh build. Nothing
is typed here that a release could move: axis windows are derived from the data and asserted to
contain it, and labels are formatted from the values they sit beside.

One style (pkinv.report.manuscript_style), two widths, and one glyph grammar:
  filled diamond   a deterministic estimate (and a ratio of two of them)
  short tick       an ensemble median
  bar              a 95 % interval, the 2.5th to 97.5th percentile
  open circle      an alternative (a factor substitution, or another weighting convention)
  square           a total
  grey circle      another inventory's value
A deterministic difference and an ensemble median used to share one circle across two figures.

A LABEL IS FORMATTED FROM THE VALUE'S OWN PRECISION. The plot tables print two decimals; a label
that rounds one of those to one decimal rounds twice, and 223.45447 Mt came out as "223.4".
"""
import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "src"))

from pkinv.report import manuscript_style as S  # noqa: E402

plt = S.use()
import numpy as np  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

DATA = HERE / "data"
FIGURES = HERE.parent
PREVIEWS = HERE / "previews"
SCRIPT = "paper_national/figures/rewrite_inputs/plot_figures.py"
UNIT = "Mt CO₂e (AR5 GWP100)"



def rows(name):
    with (DATA / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def inside(ax, values, axis="x"):
    """A clipped endpoint is invisible in a PDF unless someone measures it: fail the build."""
    low, high = ax.get_xlim() if axis == "x" else ax.get_ylim()
    low, high = min(low, high), max(low, high)
    for value in values:
        assert low < value < high, "%s is outside the %s window %s..%s" % (value, axis, low, high)


def nice_ceiling(value, step):
    return step * np.ceil(value / step)


# =================================================================================================
# Figure 2: reference-year composition, the nine annual estimates, and the change with its interval
# =================================================================================================
module = rows("module_totals.csv")
annual = rows("annual_national_series.csv")
change = rows("period_change_intervals.csv")
unc = rows("national_uncertainty.csv")
assert len(module) == 10 and len(annual) == 9 and len(change) == 3
mod_v = np.array([float(r["emissions_Mt_CO2e"]) for r in module])
ann_v = np.array([float(r["emissions_Mt_CO2e"]) for r in annual])
reference = float(unc[0]["point_Mt_CO2e"])
# the modules are the whole of the reference estimate, at the precision the table prints
assert abs(mod_v.sum() - reference) < 0.05, (mod_v.sum(), reference)
assert abs(ann_v[-1] - reference) < 0.005, (ann_v[-1], reference)
order = np.argsort(-mod_v)                      # ranked, largest first
year = S.fiscal(module[0]["period"])


def signed(value, fmt="%.0f"):
    """A typographic minus, never a hyphen."""
    return (fmt % value).replace("-", "−")


fig = S.figure(S.FULL_WIDTH, 3.55)
# (a) spans the height at left; (b) over (c) at right. The three-column alternative put the
# nine fiscal years on a 38 mm axis, where only three of them could be labelled.
a = fig.add_axes([0.205, 0.130, 0.225, 0.775])
y = np.arange(len(module))
# an edge of the bar's own colour, so a module of 0.3 Mt is a visible line and not an absence
a.barh(y, mod_v[order], height=0.66, color=S.ACCENT, edgecolor=S.ACCENT, linewidth=0.8, zorder=3)
a.set_yticks(y, [module[i]["module"] for i in order])
a.invert_yaxis()
a.set_xlim(0, nice_ceiling(mod_v.max() * 1.30, 50))
a.set_xticks(np.arange(0, a.get_xlim()[1] + 1, 100))
a.set_xlabel("Mt CO₂e in %s (AR5 GWP100)" % year)
for yy, i in zip(y, order):
    # the table's own string: two decimals, as the text prints these values
    a.text(mod_v[i] + a.get_xlim()[1] * 0.025, yy, module[i]["emissions_Mt_CO2e"], va="center",
           fontsize=S.SIZE_TICK, color=S.INK)
S.quiet(a, grid="x", keep=("bottom",))
# a heading starts at the left edge of its panel, labels included: one rule for every panel
S.panel(a, "a", "Calculation modules", x=-0.86)

b = fig.add_axes([0.560, 0.585, 0.420, 0.320])
x = np.arange(len(annual))
b.plot(x, ann_v, color=S.ACCENT, linewidth=S.LW_CURVE, zorder=3)
for xi, value in zip(x, ann_v):
    S.deterministic(b, xi, value, size=3.4)
# THE AXIS DOES NOT START AT ZERO, AND SAYS SO. A line may use a partial range where a bar may
# not; the window is derived from the data and its lower bound is printed in the axis title.
floor = 20 * np.floor((ann_v.min() - 12) / 20)
ceiling = 20 * np.ceil((ann_v.max() + 18) / 20)
b.set_ylim(floor, ceiling)
b.set_yticks(np.arange(50 * np.ceil(floor / 50), ceiling + 1, 50))
b.set_xlim(-0.40, len(annual) - 0.60)
b.set_xticks(x, [S.fiscal(r["period"]) if i % 2 == 0 else "" for i, r in enumerate(annual)])
b.set_ylabel("Mt CO₂e\n(axis from %d)" % floor)
# first, last, and the two highest years: the pair that must read as a tie, not as one peak.
# The two labels sit side by side, the earlier one ending at its point and the later starting at
# its own, because centred they ran into each other and read as one ten-digit number.
top_two = sorted(int(i) for i in np.argsort(-ann_v)[:2])
assert top_two[1] - top_two[0] == 1, "the two highest years are no longer adjacent; lay their labels out again"
for i, align, dx, dy in ((0, "left", 5, -11), (len(annual) - 1, "right", 4, 7),
                         (top_two[0], "right", 3, 7), (top_two[1], "left", -3, 7)):
    b.annotate("%.1f" % ann_v[i], (i, ann_v[i]), xytext=(dx, dy), textcoords="offset points",
               ha=align, fontsize=S.SIZE_TICK, color=S.INK)
S.quiet(b, grid="y")
S.panel(b, "b", "Annual estimates, fiscal years", x=-0.20)
inside(b, ann_v, "y")

c = fig.add_axes([0.700, 0.215, 0.175, 0.175])
NAMES = {"time_correlated": "Fully time-correlated",
         "parameter_typed": "Reference setting",
         "time_independent": "Time-independent"}
lows = [float(r["p025_Mt_CO2e"]) for r in change]
highs = [float(r["p975_Mt_CO2e"]) for r in change]
diffs = [float(r["difference_Mt_CO2e"]) for r in change]
assert max(diffs) - min(diffs) < 1e-9, "one deterministic difference, the same in every row"
span = max(highs) - min(lows)
c.set_xlim(min(lows) - 0.06 * span, max(highs) + 0.06 * span)
c.set_ylim(len(change) - 0.45, -0.55)
for i, r in enumerate(change):
    S.interval(c, lows[i], highs[i], i)
    S.deterministic(c, diffs[i], i, size=3.6)
    # the interval's own ends, at the right of the panel where no bar reaches
    c.text(1.035, i, "%s to %s" % (signed(lows[i]), signed(highs[i])),
           transform=c.get_yaxis_transform(), ha="left", va="center",
           fontsize=S.SIZE_TICK, color=S.MUTED)
c.axvline(0, color=S.RULE, linewidth=0.8, zorder=1)
c.set_yticks(range(len(change)), [NAMES[r["scenario"]] for r in change])
c.set_xticks([t for t in range(-50, 200, 50) if c.get_xlim()[0] < t < c.get_xlim()[1]])
c.set_xlabel("Change (Mt CO₂e)")
S.quiet(c, grid="x", keep=("bottom",))
c.set_title("(c) Change, %s to %s" % (S.fiscal(change[0]["from_period"]),
                                      S.fiscal(change[0]["to_period"])),
            loc="left", x=-0.800, pad=5.0)        # flush with (b), whose axes start further left
inside(c, lows + highs + diffs)
fig.legend(handles=[Line2D([], [], marker="D", markersize=4.2, color=S.INK, linestyle="none",
                           label="Deterministic difference, %s Mt" % signed(diffs[0], "%+.1f")),
                    Line2D([], [], color=S.ACCENT, linewidth=S.LW_INTERVAL,
                           label="95 % interval")],
           loc="lower left", bbox_to_anchor=(0.490, 0.005), ncol=2, columnspacing=1.4,
           handletextpad=0.6)
S.save(fig, "f02_inventory", str(FIGURES), str(PREVIEWS), SCRIPT,
       "Composition, annual estimates and change")

# =================================================================================================
# Figure 3: what supports the monthly allocation, and the conditional parameter interval
# =================================================================================================
ev = rows("reference_temporal_evidence.csv")
share = np.array([float(r["share_percent"]) for r in ev])
# four published two-decimal shares can sum to 100 give or take their rounding
assert abs(share.sum() - 100) < 0.05, share.sum()
assert [r["evidence_class"] for r in ev] == ["TE1", "TE2", "TE3", "TE4"]


def two_lines(text):
    """Break a class name near its middle, at a space."""
    words = text.split()
    best = min(range(1, len(words)), key=lambda k: abs(len(" ".join(words[:k])) - len(text) / 2))
    return " ".join(words[:best]) + "\n" + " ".join(words[best:])


fig = S.figure(S.FULL_WIDTH, 2.55)
a = fig.add_axes([0.268, 0.250, 0.230, 0.620])
y = np.arange(len(ev))
a.barh(y, share, height=0.62, color=S.ACCENT, zorder=3)
# the plain name first; the registry code after it, in brackets
a.set_yticks(y, ["%s (%s)" % (two_lines(r["description"]), r["evidence_class"]) for r in ev])
a.invert_yaxis()
a.set_xlim(0, nice_ceiling(share.max() * 1.30, 10))
a.set_xticks(np.arange(0, a.get_xlim()[1] + 1, 20))
a.set_xlabel("Share of %s emissions (%%)" % S.fiscal(ev[0]["period"]))
for yy, r in zip(y, ev):
    a.text(float(r["share_percent"]) + a.get_xlim()[1] * 0.025, yy, r["share_percent"], va="center",
           fontsize=S.SIZE_TICK, color=S.INK)
S.quiet(a, grid="x", keep=("bottom",))
S.panel(a, "a", "Evidence for monthly timing", x=-1.13)

b = fig.add_axes([0.705, 0.250, 0.275, 0.620])
det = float(unc[0]["point_Mt_CO2e"])
low, mid, high = (float(unc[1][k]) for k in ("p025_Mt_CO2e", "point_Mt_CO2e", "p975_Mt_CO2e"))
assert unc[1]["point_type"] == "Monte_Carlo_median" and unc[0]["point_type"] == "accounting_reference"
# the window runs between round numbers that enclose the interval, so its last tick is past the
# interval's end and not short of it
b.set_xlim(50 * np.floor((low - 8) / 50) - 4, 50 * np.ceil((high + 8) / 50) + 4)
b.set_ylim(1.62, -0.72)
S.deterministic(b, det, 0)
b.text(det, -0.36, unc[0]["point_Mt_CO2e"], ha="center", va="center", fontsize=S.SIZE_TICK, color=S.INK)
S.interval(b, low, high, 1)
S.median(b, mid, 1, half=0.17, color=S.INK)
for key in ("p025_Mt_CO2e", "point_Mt_CO2e", "p975_Mt_CO2e"):
    b.text(float(unc[1][key]), 0.62, unc[1][key], ha="center", va="center", fontsize=S.SIZE_TICK,
           color=S.INK)
b.set_yticks([0, 1], ["Deterministic\nreference", "Ensemble"])
b.set_xticks([t for t in range(300, 700, 50) if b.get_xlim()[0] < t < b.get_xlim()[1]])
b.set_xlabel("National total, %s (Mt CO₂e)" % S.fiscal(unc[0]["period"]))
S.quiet(b, grid="x", keep=("bottom",))
S.panel(b, "b", "Conditional parameter uncertainty", x=-0.47)
inside(b, [det, low, mid, high])
fig.legend(handles=S.glyph_handles("deterministic", "median", "interval"), loc="lower right",
           bbox_to_anchor=(0.985, 0.0), ncol=3, columnspacing=1.0, handletextpad=0.5)
S.save(fig, "f03_evidence_uncertainty", str(FIGURES), str(PREVIEWS), SCRIPT,
       "Temporal evidence and conditional parameter uncertainty")

# =================================================================================================
# Figure 7: the ratio to Pakistan's national submission, category by category
# =================================================================================================
btr = rows("btr_subject_comparison.csv")
subjects = [r for r in btr if not r["tier"].startswith("total")]
TOTAL_ORDER = ("TOTAL of the like-for-like categories", "TOTAL on categories both accounts estimate",
               "TOTAL (excluding LULUCF)")
totals = [next(r for r in btr if r["subject"] == name) for name in TOTAL_ORDER]
assert len(subjects) + len(totals) == len(btr)
SHORT = {"TOTAL of the like-for-like categories": "Total of the %d categories above" % len(subjects),
         "TOTAL on categories both accounts estimate": "Total with other sectors, both estimate",
         "TOTAL (excluding LULUCF)": "Total, excluding land use",
         "Indirect N2O from manure management": "Manure management, indirect N₂O",
         "Manure management (CH4 and direct N2O)": "Manure management, CH₄ and direct N₂O",
         "Oil and natural gas fugitives": "Oil and gas fugitives"}

fig = S.figure(S.FULL_WIDTH, 4.10)
ax = fig.add_axes([0.372, 0.175, 0.600, 0.770])
positions = list(range(len(subjects))) + [len(subjects) + 0.7 + k for k in range(len(totals))]
ratios = [float(r["ratio_pakemis_over_btr"]) for r in subjects + totals]
ax.set_xscale("log")
# ticks a factor of two apart over the whole range: the reader counts doublings
lo_pow = int(np.floor(np.log2(min(ratios) / 1.25)))
hi_pow = int(np.ceil(np.log2(max(ratios) * 1.5)))   # room for the largest ratio's label
ticks = [2.0 ** k for k in range(lo_pow, hi_pow + 1)]
ax.set_xlim(ticks[0], ticks[-1])
ax.set_xticks(ticks, [("%g" % t) for t in ticks])
ax.minorticks_off()
ax.axvspan(0.5, 2.0, color=S.FILL, zorder=0, linewidth=0)
ax.axvline(1.0, color=S.RULE, linewidth=0.9, zorder=1)
ax.axhline(len(subjects) - 0.15, color=S.RULE, linewidth=0.5, zorder=1)
labels = []
for pos, r in zip(positions, subjects + totals):
    ratio = float(r["ratio_pakemis_over_btr"])
    is_total = r["tier"].startswith("total")
    text = r["ratio_pakemis_over_btr"]
    # THE OTHER WEIGHTING, WHEREVER IT CHANGES WHAT IS PRINTED. PakEmis weights fossil methane at
    # 30; the ratio at a uniform 28 is drawn open and printed in brackets on every row whose two
    # printed ratios differ. A visibility threshold used to decide this, and it hid the two rows
    # (transport, and the total the text quotes) that change by one in the last printed digit.
    other = (r.get("ratio_ch4_uniform_28") or "").strip()
    if other and other != r["ratio_pakemis_over_btr"]:
        S.alternative(ax, float(other), pos, size=4.8)
        text = "%s (%s)" % (r["ratio_pakemis_over_btr"], other)
    if is_total:
        ax.plot([ratio], [pos], marker="s", markersize=5.0, color=S.INK, linestyle="none", zorder=5)
    else:
        S.deterministic(ax, ratio, pos, size=4.6, color=S.ACCENT)
    ax.annotate(text, (ratio, pos), xytext=(7, 0), textcoords="offset points", va="center",
                fontsize=S.SIZE_TICK, color=S.INK)
    labels.append(SHORT.get(r["subject"], r["subject"]))
ax.set_yticks(positions, labels)
ax.set_ylim(positions[-1] + 0.65, -0.75)
ax.set_xlabel("PakEmis ÷ Pakistan's First Biennial Transparency Report, 2020–21 "
              "(ratio of Mt CO₂e, log scale)")
ax.xaxis.set_label_coords(0.19, -0.075)
S.quiet(ax, grid="x", keep=("bottom",))
ax.text(1.0, 1.012, "equal", transform=ax.get_xaxis_transform(), ha="center", va="bottom",
        fontsize=S.SIZE_TICK, color=S.MUTED)
inside(ax, ratios)
ax.legend(handles=[
    Line2D([], [], marker="D", markersize=4.6, color=S.ACCENT, linestyle="none",
           label="Category, as reported"),
    Line2D([], [], marker="o", markersize=4.8, markerfacecolor=S.PAPER, markeredgecolor=S.ACCENT,
           markeredgewidth=1.3, linestyle="none", label="Fossil CH₄ at 28, not 30 (in brackets)"),
    Line2D([], [], marker="s", markersize=5.0, color=S.INK, linestyle="none", label="Total"),
    Patch(facecolor=S.FILL, edgecolor="none", label="Half to double (for orientation)")],
    loc="upper left", bbox_to_anchor=(-0.60, -0.135), ncol=4, columnspacing=1.3,
    handletextpad=0.5)
S.save(fig, "f07_btr_ratios", str(FIGURES), str(PREVIEWS), SCRIPT,
       "Ratios to Pakistan's First Biennial Transparency Report")

# =================================================================================================
# Figure 8: managed soils under the reference factors and two substitutions, beside FAOSTAT
# =================================================================================================
soil = rows("managed_soils_factor_scenarios.csv")
assert [r["group"] for r in soil] == ["PakEmis"] * 4 + ["FAOSTAT"]
values = [float(r["emissions_Mt_CO2e"]) for r in soil]
WRAP = {"Reference factors": "Reference factors\n(2019, dry climate)",
        "2006 direct soil factor": "2006 direct\nsoil factor",
        "2006 pasture factors": "2006 pasture\nfactors",
        "Both 2006 factors": "Both 2006\nfactors",
        "FAOSTAT": "FAOSTAT"}
PERIOD = {"FY2023-24": "fiscal year 2023–24", "CY2023": "calendar year 2023"}

fig = S.figure(S.COLUMN_WIDTH, 3.15)
ax = fig.add_axes([0.375, 0.250, 0.590, 0.700])
pos = [0.0, 1.0, 2.0, 3.0, 4.55]                 # a gap before the external comparator
ax.set_xlim(0, nice_ceiling(max(values) * 1.24, 10))
ax.set_ylim(pos[-1] + 0.60, -1.05)
for p, r, value in zip(pos, soil, values):
    ax.plot([0, value], [p, p], color=S.GRID, linewidth=2.2, zorder=2, solid_capstyle="butt")
    if r["group"] == "FAOSTAT":
        S.comparator(ax, value, p)
    elif r["case"] == "PakEmis reference":
        S.deterministic(ax, value, p)
    else:
        S.alternative(ax, value, p)
    ax.text(value + ax.get_xlim()[1] * 0.055, p, r["emissions_Mt_CO2e"], va="center",
            fontsize=S.SIZE_TICK, color=S.INK)
ax.set_yticks(pos, [WRAP[r["figure_label"]] for r in soil])
# the two groups, and the two different years, named where the rows are
ax.text(0.0, -0.72, "PakEmis, %s" % PERIOD[soil[0]["period"]], ha="left", va="center",
        fontsize=S.SIZE_TICK, color=S.MUTED)
ax.text(0.0, pos[-1] - 0.72, "Comparator, %s" % PERIOD[soil[-1]["period"]], ha="left",
        va="center", fontsize=S.SIZE_TICK, color=S.MUTED)
ax.set_xticks(np.arange(0, ax.get_xlim()[1] + 1, 20))
ax.set_xlabel("Managed-soils N₂O\n(Mt CO₂e, AR5 GWP100)")
ax.xaxis.set_label_coords(0.30, -0.115)
S.quiet(ax, grid="x", keep=("bottom",))
inside(ax, values)
fig.legend(handles=[
    Line2D([], [], marker="D", markersize=5.2, color=S.INK, linestyle="none", label="Reference"),
    Line2D([], [], marker="o", markersize=5.4, markerfacecolor=S.PAPER, markeredgecolor=S.ACCENT,
           markeredgewidth=1.3, linestyle="none", label="Alternative factors"),
    Line2D([], [], marker="o", markersize=5.4, color=S.NEUTRAL, linestyle="none",
           label="Comparator")],
    loc="lower center", bbox_to_anchor=(0.5, 0.0), ncol=3, columnspacing=0.9, handletextpad=0.2)
S.save(fig, "f08_managed_soils", str(FIGURES), str(PREVIEWS), SCRIPT,
       "Managed-soils factor cases beside FAOSTAT")
print("f02, f03, f07, f08 rebuilt")
