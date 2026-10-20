"""The two threshold figures of the gas-reallocation application, drawn from its own CSVs.

Nothing here computes an emission: each figure reads outputs/pakemis_transition_gas_thresholds.csv
and _baselines.csv and draws what is in them (the rule pkinv.report.figures follows).

T1  territorial CO2e change per PJ of reallocated gas against the intensity of the generation the new
    gas-fired GWh displace, for both leak bases and both power readings. Each line is (GWh per PJ) x
    (threshold - intensity); the markers are the explicit displaced pathways and the dotted line is the
    average fossil grid, which is not a displaced-generation intensity.
T2  the imported-urea intensity at which territorial-plus-external CO2e stops falling, case by case,
    against the two import routes.
"""
import os

from pkinv.core.io import read_rows
from pkinv.paths import OUTPUTS
from pkinv.report.figures import PALETTE, _plt, _save, _style

THRESHOLDS = os.path.join(OUTPUTS, "pakemis_transition_gas_thresholds.csv")
BASELINES = os.path.join(OUTPUTS, "pakemis_transition_gas_baselines.csv")
LABELS = {"R1": "RLNG combined cycle (1.2 GW stations)", "R2": "older network RLNG combined cycle",
          "D1": "oil engines", "D2": "oil steam", "D3": "imported coal", "D4": "RLNG import falls",
          "M1": "oil engines to their FY output, rest RLNG", "M3": "imported coal to its FY output, rest RLNG",
          "LB1": "leak base LB1 (reference)", "LB2": "leak base LB2 (feedstock inside)"}


def _f(x):
    return float(x) if str(x).strip() else None


def t1():
    plt = _plt()
    rows = read_rows(THRESHOLDS)
    slope = {(r["axis"].split(":")[1], r["baseline_id"]): _f(r["p50"]) for r in read_rows(BASELINES)
             if r["axis"].startswith("power_conversion")}
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.0), sharey=True)
    grid = None
    for ax, receiving in zip(axes, ("R1", "R2")):
        xs = [i / 100.0 for i in range(0, 121)]
        for colour, lb in ((PALETTE[0], "LB1"), (PALETTE[1], "LB2")):
            for style, pa in (("-", "PA1"), ("--", "PA2")):
                row = [r for r in rows if r["threshold"].startswith("T1 displaced") and r["receiving"] == receiving
                       and r["baseline_fertilizer"] == "FA2" and r["baseline_power"] == pa and r["leak_base"] == lb][0]
                k = slope[(receiving, pa)]
                star, lo, hi = _f(row["threshold_p50"]), _f(row["threshold_p2_5"]), _f(row["threshold_p97_5"])
                ax.plot(xs, [k * (star - x) for x in xs], style, color=colour, lw=1.5,
                        label="%s, %s" % (LABELS[lb], pa))
                if pa == "PA1":
                    ax.fill_between(xs, [k * (lo - x) for x in xs], [k * (hi - x) for x in xs],
                                    color=colour, alpha=0.12, lw=0)
                grid = float(row["comparison"].split()[-1])
        for i, d in enumerate(("D1", "D2", "D3")):
            row = [r for r in rows if r["threshold"].startswith("T1 intensity") and r["receiving"] == receiving
                   and r["displaced"] == d and r["baseline_fertilizer"] == "FA2" and r["baseline_power"] == "PA1"
                   and r["leak_base"] == "LB1"][0]
            mid, lo, hi = _f(row["threshold_p50"]), _f(row["threshold_p2_5"]), _f(row["threshold_p97_5"])
            ax.errorbar([mid], [0], xerr=[[mid - lo], [hi - mid]], fmt="o", ms=4, color=PALETTE[2 + i],
                        capsize=2, zorder=4)
            ax.annotate(LABELS[d], (mid, 0), textcoords="offset points", xytext=(0, 7 + 9 * i),
                        ha="center", fontsize=7.5, color=PALETTE[2 + i])
        ax.axvline(grid, color="#777777", ls=":", lw=1.2)
        ax.annotate("average fossil grid\n(not a displaced intensity)", (grid, ax.get_ylim()[0]),
                    textcoords="offset points", xytext=(3, 8), fontsize=7, color="#555555")
        ax.axhline(0, color="#333333", lw=0.8)
        ax.set_title("Gas received by %s" % LABELS[receiving], fontsize=9.5)
        ax.set_xlabel("Intensity of displaced generation (t CO$_2$e per MWh)", fontsize=8.5)
        _style(ax)
        ax.grid(axis="y", linestyle=":", linewidth=0.6, alpha=0.6)
    axes[0].set_ylabel("Territorial CO$_2$e change\n(Gg per PJ of gas, HHV)", fontsize=8.5)
    axes[0].legend(fontsize=7, frameon=False, loc="lower left")
    fig.suptitle("Where the territorial CO$_2$e change of moving the two plants' gas to power changes sign "
                 "(FY2023-24, FA2; band: 95% conditional interval, PA1)", fontsize=9.5)
    fig.tight_layout()
    return _save(fig, "pakemis_transition_gas_t1_displaced_intensity.png")


def t2():
    plt = _plt()
    rows = read_rows(THRESHOLDS)
    routes = {r["threshold"].split()[5].rstrip(","): r for r in rows
              if r["threshold"].startswith("T2 imported-urea intensity of route")}
    cases = [r for r in rows if r["threshold"].startswith("T2 imported-urea intensity for zero")
             and r["baseline_fertilizer"] == "FA2" and r["baseline_power"] == "PA1"
             and r["receiving"] in ("R1", "none") and r["displaced"] in ("D1", "D3", "M1", "M3", "D4")]
    cases.sort(key=lambda r: (r["displaced"], r["leak_base"]))
    fig, ax = plt.subplots(figsize=(7.2, 0.42 * len(cases) + 1.4))
    for colour, route in ((PALETTE[5], "F1"), (PALETTE[1], "F2")):
        r = routes[route]
        ax.axvspan(_f(r["threshold_p2_5"]), _f(r["threshold_p97_5"]), color=colour, alpha=0.15, lw=0)
        ax.axvline(_f(r["threshold_p50"]), color=colour, lw=1.2,
                   label="import route %s %s" % (route, "(gas reforming)" if route == "F1"
                                                 else "(coal-gasification hydrogen)"))
    for i, r in enumerate(cases):
        mid, lo, hi = _f(r["threshold_p50"]), _f(r["threshold_p2_5"]), _f(r["threshold_p97_5"])
        ax.errorbar([mid], [i], xerr=[[mid - lo], [hi - mid]], fmt="o", ms=4, color=PALETTE[0], capsize=2)
    ax.legend(fontsize=7.5, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=2)
    ax.set_yticks(range(len(cases)))
    ax.set_yticklabels(["%s; %s%s" % (LABELS[r["displaced"]], r["leak_base"],
                                      "" if r["receiving"] == "none" else ", R1") for r in cases], fontsize=7.5)
    ax.set_xlabel("Imported-urea intensity at which territorial + external CO$_2$e stops falling "
                  "(t CO$_2$e per t urea)", fontsize=8.5)
    ax.set_title("Below a case's threshold the combined change falls, before the exporter stages not "
                 "estimated (FA2, PA1; 95% conditional interval)", fontsize=9)
    _style(ax)
    fig.tight_layout()
    return _save(fig, "pakemis_transition_gas_t2_import_route.png")


def main():
    for draw in (t1, t2):
        print("wrote outputs/figures/%s" % draw())
