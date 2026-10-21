"""Figures for the national contribution evidence, drawn from generated tables.

Run after ``make contribution-evidence`` using the optional matplotlib dependency:
    python -m pkinv.report.contribution_figures

The figures compare represented accounts. Neither a benchmark difference nor a
conditional factor substitution is an observational emissions error estimate.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from pkinv.core.io import read_rows
from pkinv.paths import OUTPUTS


def _number(row, column):
    value = row.get(column, "")
    if value in (None, ""):
        raise ValueError(f"Missing {column} in {row.get('subject', row.get('flow', row))}")
    return float(value)


def _one(rows, column, value):
    matches = [row for row in rows if row.get(column) == value]
    if len(matches) != 1:
        raise ValueError(f"Expected one {column}={value!r}; found {len(matches)}")
    return matches[0]


def btr_values(path):
    rows = read_rows(str(path))
    # The restated waste and residue-burning rows overlap other categories.
    # Scope-gap and absent-category rows cannot be treated as equal boundaries.
    matched = [row for row in rows if row["tier"] in ("exact", "aggregate")]
    if not matched:
        raise ValueError("No comparable BTR category rows")
    by_subject = [row["subject"] for row in matched]
    if len(by_subject) != len(set(by_subject)):
        raise ValueError("Duplicate comparable BTR subjects")
    matched.sort(key=lambda row: _number(row, "pakemis_Mt_co2e") - _number(row, "btr_Mt_co2e"))
    differences = [_number(row, "pakemis_Mt_co2e") - _number(row, "btr_Mt_co2e") for row in matched]
    uniform = [_number(row, "pakemis_Mt_co2e_ch4_uniform_28") - _number(row, "btr_Mt_co2e") for row in matched]
    headline = _one(rows, "subject", "TOTAL (excluding LULUCF)")
    return matched, differences, uniform, headline


def nitrogen_values(path):
    rows = [row for row in read_rows(str(path)) if row["row_kind"] == "attribution"]
    labels = ("managed soils, current engine", "managed soils, EF1-only substitution",
              "managed soils, EF1 + EF3PRP substitution")
    chosen = [_one(rows, "flow", label) for label in labels]
    values = [_number(row, "pakemis") for row in chosen]
    target = _number(chosen[0], "faostat")
    if any(abs(_number(row, "faostat") - target) > 1e-8 for row in chosen):
        raise ValueError("Nitrogen comparator totals differ between substitution rows")
    if abs(target - values[0]) < 1e-12:
        raise ValueError("No nitrogen gap to decompose")
    return values, target


def _save(fig, output_dir, name):
    output_dir.mkdir(parents=True, exist_ok=True)
    for extension in ("svg", "png"):
        path = output_dir / f"{name}.{extension}"
        fig.savefig(path, dpi=220,
                    bbox_inches="tight", facecolor="white",
                    # no Date and no Creator/Software stamp: the files answer to the pinned
                    # matplotlib in requirements.lock, not to whichever version drew them
                    metadata={"Date": None, "Creator": None} if extension == "svg"
                    else {"Software": None})
        if extension == "svg":
            # Matplotlib leaves spaces before newlines in path attributes.
            # Newlines preserve token separation; trim spaces for clean patches.
            path.write_text("\n".join(line.rstrip() for line in
                                      path.read_text().splitlines()) + "\n")


def build(output_dir=None, inputs_dir=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    inputs = Path(inputs_dir or OUTPUTS)
    dest = Path(output_dir or inputs / "figures")
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "axes.spines.left": False, "svg.fonttype": "none",
                         "svg.hashsalt": "pakemis-contribution-evidence"})
    blue, orange, ink, grey = "#197B91", "#C36B32", "#183649", "#647786"

    rows, deltas, uniform, total = btr_values(inputs / "pakemis_btr_comparison.csv")
    fig, ax = plt.subplots(figsize=(10.8, 8.1))
    y = np.arange(len(rows))
    ax.barh(y, deltas, color=[blue if x < 0 else orange for x in deltas], height=.65)
    ax.scatter(uniform, y, color=ink, marker="D", s=20, zorder=4,
               label="PakEmis methane weighted uniformly at 28 (sensitivity)")
    ax.axvline(0, color=ink, linewidth=.8)
    ax.set_yticks(y, [row["subject"].replace(" (CH4 and direct N2O)", "") for row in rows])
    ax.tick_params(axis="y", length=0, labelsize=9)
    ax.grid(axis="x", alpha=.2)
    ax.set_axisbelow(True)
    ax.set_xlabel("PakEmis minus BTR (Mt CO2e, AR5 family)", labelpad=10)
    fig.text(.03, .965, "Similar national totals conceal category differences",
             fontweight="bold", fontsize=15, color=ink)
    a, b = _number(total, "pakemis_Mt_co2e"), _number(total, "btr_Mt_co2e")
    fig.text(.03, .905, f"FY2020-21  |  Headline totals: PakEmis {a:.2f}, BTR {b:.2f} Mt CO2e\n"
             f"Headline difference {a-b:+.2f} Mt; net difference in plotted categories {sum(deltas):+.2f} Mt.",
             fontsize=10, color=grey)
    for iy, value in enumerate(deltas):
        ax.text(value + (.45 if value >= 0 else -.45), iy, f"{value:+.2f}",
                va="center", ha="left" if value >= 0 else "right", fontsize=8.5, color=ink)
    ax.margins(x=.14)
    ax.legend(loc="upper center", bbox_to_anchor=(.50, -0.13), frameon=False, fontsize=8)
    fig.text(.03, .025, "Plotted rows are nonoverlapping exact/aggregate crosswalk categories; scope gaps and restated rows are excluded.\n"
             "The headline has a wider scope. BTR methane convention is unresolved; the diamond changes only PakEmis.\n"
             "Differences compare two compilations and do not identify which estimate is closer to actual emissions.",
             fontsize=8, color=grey, linespacing=1.45)
    fig.subplots_adjust(left=.34, right=.94, top=.84, bottom=.19)
    _save(fig, dest, "pakemis_contribution_btr_offsets")
    plt.close(fig)

    values, target = nitrogen_values(inputs / "pakemis_faostat_nitrogen_flows.csv")
    starts = [0, values[0], values[1], values[2], 0]
    heights = [values[0], values[1]-values[0], values[2]-values[1], target-values[2], target]
    labels = ["PakEmis\ncurrent engine", "Change EF1\nonly", "Also change\nEF3PRP", "Remaining\ndifference", "FAOSTAT\ncomparison"]
    fig, ax = plt.subplots(figsize=(9.8, 5.7))
    bars = ax.bar(range(5), heights, bottom=starts, width=.65,
                  color=[blue, orange, orange, "#DFE6EA", ink], edgecolor="white")
    bars[3].set_hatch("///")
    for i in range(4):
        ax.plot([i+.325, i+.675], [starts[i]+heights[i]]*2, color=grey, linewidth=.8)
    for i, (start, height) in enumerate(zip(starts, heights)):
        ax.text(i, max(start, start+height)+1.1, f"{height:+.2f}" if i in (1,2,3) else f"{height:.2f}",
                ha="center", fontsize=10, color=ink, fontweight="bold")
    explained = 100*(values[2]-values[0])/(target-values[0])
    ax.set_xticks(range(5), labels)
    ax.set_ylabel("Managed-soils emissions (Mt CO2e, AR5)")
    ax.set_ylim(min(0, min(starts)+min(heights)), max(target, *values)*1.20)
    ax.grid(axis="y", alpha=.2); ax.set_axisbelow(True)
    ax.set_title("Two direct-factor substitutions account for much of the gap", loc="left",
                 fontweight="bold", fontsize=14, color=ink, pad=38)
    fig.text(.07, .87, f"Conditional substitutions close {explained:.1f}% of the numerical difference; other assumptions remain current.",
             color=grey, fontsize=10)
    fig.text(.07, .035, "PakEmis FY2023-24 versus FAOSTAT CY2023: periods are not identical.\n"
             "Substitutions change EF1 and EF3PRP; they do not reproduce the complete FAOSTAT method.\n"
             "The residual includes unresolved activity, timing, routing and factor differences; neither account is a truth benchmark.",
             color=grey, fontsize=8, linespacing=1.5)
    fig.subplots_adjust(left=.09, right=.97, bottom=.24, top=.80)
    _save(fig, dest, "pakemis_contribution_nitrogen_attribution")
    plt.close(fig)
    return [dest / (name + ".png") for name in
            ("pakemis_contribution_btr_offsets", "pakemis_contribution_nitrogen_attribution")]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--inputs-dir", type=Path)
    args = parser.parse_args(argv)
    for path in build(args.output_dir, args.inputs_dir):
        print(path)


if __name__ == "__main__":
    main()
