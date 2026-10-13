"""The national manuscript's generated figures: drawn from query envelopes, never from CSVs.

v1.0.0 Wave 4. The drawers port the national figures of pkinv.report.figures onto the
semantic layer: each takes the envelopes a registry row's stored query returned
(paper_national/queries/paper_artefacts.csv) and draws exactly what they carry. Bar heights
and line points are the cells' `value` (the float of the exact decimal string); every number
a reader can read off the image - an annotation, a tick label - is a `display` string the
query core inserted. No figure recomputes, shares, sums or annotates a number of its own;
what the contract does not carry (an Approach-1 band per module, a symmetric +/-%) is not
drawn, and the registry's caption_facts say so.

Determinism: Agg, a fixed DPI, no Software/CreationDate/Producer metadata, so the PNG and
PDF bytes are a function of the release and the pinned matplotlib alone - the same rule
figures._save applies, extended to the PDF twin.

Each drawer has the signature `draw(envelopes, png_path, pdf_path)`.
"""
import os

from pkinv.report.figures import DPI, PALETTE, _plt, _style

PNG_METADATA = {"Software": None}
PDF_METADATA = {"Creator": None, "Producer": None, "CreationDate": None}


def _save(fig, png_path, pdf_path):
    os.makedirs(os.path.dirname(png_path), exist_ok=True)
    fig.savefig(png_path, dpi=DPI, bbox_inches="tight", metadata=PNG_METADATA)
    if pdf_path:
        fig.savefig(pdf_path, bbox_inches="tight", metadata=PDF_METADATA)
    _plt().close(fig)


def trend(envelopes, png_path, pdf_path=None):
    """The national series, one point per fiscal period, in the order the release lists
    them (get_timeseries, annual step)."""
    cells = envelopes[0]["values"]
    labels = [c["group"]["period_id"] for c in cells]
    plt = _plt()
    fig, ax = plt.subplots(figsize=(7.0, 3.2))
    ax.plot(labels, [c["value"] for c in cells], marker="o", color=PALETTE[0],
            linewidth=1.6, label="ten sectors, reference configuration")
    for label, c in zip(labels, cells):
        ax.annotate(c["display"], (label, c["value"]), textcoords="offset points",
                    xytext=(0, 9), fontsize=7, ha="center", color="#444444",
                    bbox={"boxstyle": "round,pad=0.15", "fc": "white", "ec": "none", "alpha": 0.85})
    ax.set_ylabel("Mt CO$_2$e (AR5)")
    ax.set_title("The national series, FY2015-16 to FY2023-24", loc="left", fontsize=11)
    ax.legend(fontsize=8, frameon=False)
    for lab in ax.get_xticklabels():
        lab.set_rotation(45)
        lab.set_ha("right")
    _style(ax)
    _save(fig, png_path, pdf_path)


def sectors(envelopes, png_path, pdf_path=None):
    """Sector composition of the reference year (query_emissions grouped by sector_id)."""
    cells = list(envelopes[0]["values"])
    cells.sort(key=lambda c: c["value"])
    names = [c["group"]["sector_id"] for c in cells]
    plt = _plt()
    fig, ax = plt.subplots(figsize=(7.2, 4.0))
    ax.barh(names, [c["value"] for c in cells], color=PALETTE[0], edgecolor="white",
            linewidth=0.5)
    for i, c in enumerate(cells):
        ax.annotate(c["display"], (c["value"], i), textcoords="offset points",
                    xytext=(4, -3), fontsize=8)
    ax.set_xlabel("Mt CO$_2$e (AR5 GWP-100)")
    ax.set_title("Pakistan national inventory by sector, FY2023-24", loc="left", fontsize=11)
    ax.set_xlim(left=0)
    _style(ax)
    _save(fig, png_path, pdf_path)


def months(envelopes, png_path, pdf_path=None):
    """The 108-month national product (get_timeseries, monthly step), July 2015 to June
    2024, with the fiscal-year boundaries ticked."""
    cells = envelopes[0]["values"]
    labels = [c["group"]["month"] for c in cells]
    plt = _plt()
    fig, ax = plt.subplots(figsize=(7.4, 3.2))
    ax.bar(range(len(cells)), [c["value"] for c in cells], width=0.85, color=PALETTE[0],
           edgecolor="none")
    starts = [i for i, m in enumerate(labels) if m.endswith("07")]
    ax.set_xticks(starts)
    ax.set_xticklabels(["FY%s-%s" % (labels[i][:4], str(int(labels[i][:4]) + 1)[2:])
                        for i in starts], fontsize=7.5, rotation=45, ha="right")
    for i in starts[1:]:
        ax.axvline(i - 0.5, color="#bbbbbb", linewidth=0.6, linestyle=":")
    ax.set_ylabel("Mt CO$_2$e (AR5) per month")
    ax.set_title("The national inventory in 108 months, July 2015 to June 2024",
                 loc="left", fontsize=11)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", linestyle=":", linewidth=0.6, alpha=0.6)
    ax.set_axisbelow(True)
    ax.set_xlim(-0.6, len(cells) - 0.4)
    _save(fig, png_path, pdf_path)


def uncertainty(envelopes, png_path, pdf_path=None):
    """The two Monte-Carlo scenarios side by side (get_uncertainty, national scope): the
    P2.5-P97.5 interval with the median ticked, labelled with the release's own quantile
    strings."""
    cells = {c["scenario"]: c for c in envelopes[0]["values"]}
    order = ["within_sector", "cross_sector"]
    labels = {"within_sector": "Parameters shared within a module",
              "cross_sector": "Shared by physical identity across modules"}
    plt = _plt()
    fig, ax = plt.subplots(figsize=(7.0, 2.1))
    for i, key in enumerate(order):
        c = cells[key]
        lo, hi = float(c["quantiles"]["P2.5"]), float(c["quantiles"]["P97.5"])
        ax.plot([lo, hi], [i, i], linewidth=6, solid_capstyle="butt", color=PALETTE[i],
                alpha=0.85)
        ax.plot([c["value"]], [i], marker="|", markersize=18, color="#222222")
        ax.annotate("%s-%s Mt (median %s)"
                    % (c["quantiles"]["P2.5"], c["quantiles"]["P97.5"], c["display"]),
                    (hi, i), textcoords="offset points", xytext=(8, -3), fontsize=8.5)
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels([labels[k] for k in order], fontsize=9)
    ax.set_xlabel("Mt CO$_2$e (AR5), Monte Carlo 95 percent interval")
    ax.set_title("National uncertainty under two correlation assumptions", loc="left",
                 fontsize=11)
    ax.set_ylim(-0.7, len(order) - 0.3)
    lows = [float(c["quantiles"]["P2.5"]) for c in cells.values()]
    highs = [float(c["quantiles"]["P97.5"]) for c in cells.values()]
    ax.set_xlim(left=min(lows) * 0.97, right=max(highs) * 1.16)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.grid(axis="x", linestyle=":", linewidth=0.6, alpha=0.6)
    ax.set_axisbelow(True)
    _save(fig, png_path, pdf_path)


DRAWERS = {"pkinv.report.paper_figures.trend": trend,
           "pkinv.report.paper_figures.sectors": sectors,
           "pkinv.report.paper_figures.months": months,
           "pkinv.report.paper_figures.uncertainty": uncertainty}
