"""Figure 1: how the data products are constructed.

THE GRAPH IS THE CODE'S, NOT A TIDY GUESS. Each arrow below is a dependency the pipeline has:

  annual estimates   E(s, g)             one estimate per source stream, gas and year
  monthly tables     E(s, g) p(s, m)     the annual estimate times that stream's monthly profile
                                         (pkinv.report.monthly_all_years)
  annual grids       E(s, g) w(s, i)     the annual estimate times that stream's cell weights,
                                         a province share and then cells within the province
                                         (pkinv.report.grid_cube, written per period by
                                         pkinv.report.annual_grid)
  administrative     the SAME allocation read at province and district grain; it is not a sum of
  tables             the raster file (pkinv.report.spatial_by_year, through the cube's own
                                         district partition). The PROVINCE tables hold every
                                         stream, the unallocated ones included: national == ADM1,
                                         and ADM1 == ADM2 + unallocated. So the unallocated
                                         account completes the grids and the district tables,
                                         and must not be added to the province tables.
  monthly grid       E(s, g) p(s, m) w(s, i)   the published monthly layer times the cell
                                         weights, reference year only (pkinv.report.grid_cube)
  unallocated        streams with no supported location below the province: they reach the
                     province tables and no cell (outputs/pakemis_spatial_unallocated.csv)

WHAT THE PREVIOUS DRAWING GOT WRONG. The monthly grid had one incoming arrow, from spatial
allocation, though it needs the monthly tables as well; a note about conservation sat on top of
the temporal box; the reference year's total was printed inside a node that stands for nine
years; and the province and district tables were not in the picture at all.

No quantity is drawn. The closure arithmetic is a table in the technical supplement
(generated/tab_closure.tex), built from the same construction_quantities.csv this script used
to read one number from.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "src"))

from pkinv.report import manuscript_style as S  # noqa: E402

plt = S.use()
from matplotlib.patches import FancyArrowPatch, Rectangle  # noqa: E402

FIGURES = HERE.parent
W, H = S.FULL_WIDTH, 4.06
fig = S.figure(W, H)
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, W * 72)            # the canvas is in points, so a 1 pt line is 1 unit
ax.set_ylim(0, H * 72)
ax.axis("off")

# --- the lattice: five lanes, six rows ----------------------------------------------------------
NODE_W, NODE_H = 86.0, 28.0
LANE_X = [8.0, 108.0, 208.0, 308.0, 408.0]           # left edge of each lane
ROW_Y = [216.0, 178.0, 140.0, 102.0, 64.0, 26.0]     # bottom edge of each row, top to bottom
HEAD_Y = 254.0
LANES = ("Sources", "Harmonised inputs", "Estimation", "Allocation", "Data products")

for x, name in zip(LANE_X, LANES):
    ax.text(x + NODE_W / 2, HEAD_Y, name, ha="center", va="bottom", fontsize=S.SIZE_LABEL,
            color=S.MUTED)
    ax.plot([x, x + NODE_W], [HEAD_Y - 4, HEAD_Y - 4], color=S.RULE, linewidth=0.5)

nodes = {}


def node(key, lane, row, text, kind="step"):
    """kind: step (a calculation or an input), product (a released file), or kept (the
    unallocated account: a released file too, dashed because its mass is not placed below the
    province)."""
    x, y = LANE_X[lane], ROW_Y[row]
    face = S.PAPER if kind == "step" else S.FILL
    ax.add_patch(Rectangle((x, y), NODE_W, NODE_H, facecolor=face, edgecolor=S.INK,
                           linewidth=0.7, linestyle=(0, (3, 2)) if kind == "kept" else "-",
                           zorder=3))
    ax.text(x + NODE_W / 2, y + NODE_H / 2, text, ha="center", va="center",
            fontsize=S.SIZE_TICK, color=S.INK, linespacing=1.25, zorder=4)
    nodes[key] = (x, y)


def port(key, side, frac=0.5):
    x, y = nodes[key]
    return {"l": (x, y + NODE_H * frac), "r": (x + NODE_W, y + NODE_H * frac),
            "t": (x + NODE_W * frac, y + NODE_H), "b": (x + NODE_W * frac, y)}[side]


def run(points, head=True):
    """An orthogonal connector through the given points, with one arrowhead at the end."""
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    ax.plot(xs, ys, color=S.INK, linewidth=0.8, solid_capstyle="butt",
            solid_joinstyle="miter", zorder=2)
    if head:
        ax.add_patch(FancyArrowPatch(points[-2], points[-1], arrowstyle="-|>",
                                     mutation_scale=9.5, linewidth=0.0, color=S.INK,
                                     shrinkA=0, shrinkB=0, zorder=2))


def junction(point):
    ax.plot([point[0]], [point[1]], marker="o", markersize=2.6, color=S.INK, zorder=3)


node("records", 0, 2, "Source records")
node("profiles", 1, 0, "Monthly profiles\nby source")
node("activity", 1, 2, "Reconciled\nactivity")
node("factors", 1, 3, "Emission factors\nand methods")
node("weights", 1, 4, "Spatial weights\nby source")
node("annual", 2, 2, "Annual estimates\nby source and gas")
node("temporal", 3, 0, "Temporal\nallocation")
node("spatial", 3, 4, "Spatial\nallocation")
node("monthly", 4, 0, "Monthly tables\nnine years", "product")
node("mgrid", 4, 1, "Monthly grid\n2023–24, 0.05°", "product")
node("agrid", 4, 2, "Annual grids\nnine years, 0.05°", "product")
node("adm2", 4, 3, "District tables\nnine years", "product")
node("kept", 4, 4, "Unallocated\naccount", "kept")
node("adm1", 4, 5, "Province tables\nnine years", "product")

# --- sources feed the four harmonised inputs ----------------------------------------------------
rail = LANE_X[0] + NODE_W + 7.0
run([port("records", "r"), (rail, port("records", "r")[1])], head=False)
run([(rail, port("weights", "l")[1]), (rail, port("profiles", "l")[1])], head=False)
for key in ("profiles", "activity", "factors", "weights"):
    run([(rail, port(key, "l")[1]), port(key, "l")])
junction((rail, port("records", "r")[1]))

# --- estimation: activity times factors ---------------------------------------------------------
run([port("activity", "r"), port("annual", "l")])
run([port("factors", "r"), (port("annual", "b")[0], port("factors", "r")[1]), port("annual", "b")])

# --- the annual estimates feed each allocation by its own line, so that the two lines cannot be
#     read as one two-headed arrow between the allocations ----------------------------------------
up_x = LANE_X[3] + NODE_W * 0.35
down_x = LANE_X[3] + NODE_W * 0.65
run([port("annual", "r", 0.70), (up_x, port("annual", "r", 0.70)[1]), (up_x, port("temporal", "b")[1])])
run([port("annual", "r", 0.30), (down_x, port("annual", "r", 0.30)[1]), (down_x, port("spatial", "t")[1])])

# --- the weights feed their own allocation, straight across -------------------------------------
run([port("profiles", "r"), port("temporal", "l")])
run([port("weights", "r"), port("spatial", "l")])

# --- products ------------------------------------------------------------------------------------
run([port("temporal", "r"), port("monthly", "l")])
bus = LANE_X[3] + NODE_W + 7.0
run([port("spatial", "r"), (bus, port("spatial", "r")[1])], head=False)
run([(bus, port("adm1", "l")[1]), (bus, port("mgrid", "l")[1])], head=False)
for key in ("mgrid", "agrid", "adm2", "kept", "adm1"):
    run([(bus, port(key, "l")[1]), port(key, "l")])
junction((bus, port("spatial", "r")[1]))
# the monthly grid's second input: the monthly tables, entering from above
run([port("monthly", "b"), port("mgrid", "t")])

# --- the key, top left: what a box's style means ------------------------------------------------
key_y = H * 72 - 10.0
kx = LANE_X[0]
for label, face, dash in (("Calculation or input", S.PAPER, "-"),
                          ("Released product", S.FILL, "-"),
                          ("Released product: mass not placed below the province", S.FILL, (0, (3, 2)))):
    ax.add_patch(Rectangle((kx, key_y - 4.0), 13.0, 8.0, facecolor=face, edgecolor=S.INK,
                           linewidth=0.7, linestyle=dash))
    ax.text(kx + 18.0, key_y, label, ha="left", va="center", fontsize=S.SIZE_TICK, color=S.MUTED)
    kx += 18.0 + 4.55 * len(label) + 16.0

# --- the footer: what is conserved, outside every node and arrow --------------------------------
ax.text(LANE_X[0], 7.5,
        "Conserved for each source, gas and period: months sum to the annual estimate;\n"
        "grid cells + unallocated = districts + unallocated = province tables = annual estimate.",
        ha="left", va="center", fontsize=S.SIZE_FLOOR, color=S.MUTED, linespacing=1.3)

S.save(fig, "f01_construction", str(FIGURES), str(HERE / "previews"),
       "paper_national/figures/rewrite_inputs/plot_construction.py",
       "Construction of the data products")
print("f01_construction rebuilt (%d nodes)" % len(nodes))
