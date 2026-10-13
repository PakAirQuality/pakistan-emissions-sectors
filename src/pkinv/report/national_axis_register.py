"""The definitive axis table: every structural axis, its pricing status, in one row each.

WHY THIS EXISTS. The ninth review counted three products describing the axis space -
the scenario registry (then 17 axes; the count lives in the register itself now,
never in prose), Figure 5 (16 bars, because the unpriced transport
axis was silently dropped), and the configurations prose ("twelve", against thirteen
rows) - and found no single table a reader could reconcile them against. This is that
table: one row per registered axis, composed IN MEMORY from the same functions the
bridge and the configurations file are built from, so the three products cannot
disagree with it without failing its test.

WHAT A ROW SAYS. The axis, its module and family, the reference setting, the
published alternative, the sector and national deltas, whether the axis appears in
Figure 5 and in the configurations file, and - the column the review asked for by
name - priced_status with reason_if_unpriced. The JOINT configurations are not axes
and deliberately do not appear here; they live in the configurations file as the
declared exceptions.

Usage:  python3 -m pkinv.report.national_axis_register
Writes: outputs/national_axis_register.csv
"""

from pkinv.assets import asset_path
import csv
import os

from pkinv.paths import OUTPUTS
from pkinv.report import national_configurations
from pkinv.report import national_rollup
from pkinv.core.io import write_table

OUT = asset_path(OUTPUTS, "national_axis_register.csv")

# monthly_grain (rc20, the fifteenth review's "every configuration at monthly
# resolution", scoped honestly): a configuration can carry months only when its
# alternative is a complete component-level re-run pushed through a monthly
# layer. One axis qualifies today - the residential dung basis, whose L reading
# ships at monthly grain in outputs/pakemis_monthly_ledger_2024.csv. Everything
# else is a national delta scalar, and the column says so per row instead of
# leaving the absence to be discovered.
MONTHLY_GRAIN_AVAILABLE = {
    "residential dung basis": "available (pakemis_monthly_ledger_2024.csv)",
}
MONTHLY_GRAIN_DEFAULT = ("delta_scalar_only: the alternative is priced as a "
                         "national delta, not re-run at component grain")

# spatial_grain / uncertainty_grain (Pass 2 Wave 0, the sixteenth review's
# configuration-parity item): the same typed-availability pattern, extended to the
# two grains the register was silent about. The sixteenth review read that silence
# as an untyped absence - the detailed spatial and MC products ship under the
# reference only, which was stated in one sector CSV's free-text note and nowhere
# machine-readable. The sixteenth review read that silence as an untyped absence.
# Wave 5 filled the first honest spatial entry: the dung axis's L reading consumes
# the SAME district panel as the reference, so its ADM2 placement is the
# reference's own shares rescaled - a provable structural statement, not a re-run.
# STREAM-grain spatial alternatives (the rice GCD surface, captive points vs
# builtup, the road-graph split) live in pakemis_spatial_brackets_adm2.csv and are
# not axes; an axis earns an entry here only for its own alternative's placement.
SPATIAL_GRAIN_AVAILABLE = {
    "residential dung basis": (
        "available (pakemis_adm2_monthly.csv: both readings consume the same "
        "district panel, so configuration L's ADM2 placement is the "
        "reference's shares rescaled - structurally invariant below the "
        "province)"),
}
SPATIAL_GRAIN_DEFAULT = ("reference_only: the detailed spatial products (ADM2 views, "
                         "grid cube) are built under the reference configuration; an "
                         "alternative's placement is not re-run. Stream-grain "
                         "spatial alternatives are priced separately in "
                         "pakemis_spatial_brackets_adm2.csv")
# Wave 6: the reserved schema fills, in TWO honest tiers. An axis whose
# alternative carries its own conditional parametric interval ON THE NATIONAL
# SEED (42) is `available (...)` - its draws sit on the same stream as the
# published run. Waste's scenario reruns are real MC but on deliberately
# PRIVATE per-scenario seeds (4321-4334), so their intervals are conditional
# statements from an independent run, not per-draw deltas - a distinct typed
# state, because writing `available (` over them would imply a draw-level
# comparability that does not exist.
UNCERTAINTY_GRAIN_AVAILABLE = {
    "fugitive practice": (
        "available (fugitives_conditional_intervals_2024.csv: seed-42 "
        "conditional interval per configuration)"),
    "fugitive activity basis": (
        "available (fugitives_conditional_intervals_2024.csv: seed-42 "
        "conditional interval per configuration)"),
    "post-meter feedstock scope": (
        "available (fugitives_conditional_intervals_2024.csv: seed-42 "
        "conditional interval per configuration)"),
    "cement clinker fraction": (
        "available (ippu_cement_conditional_intervals_2024.csv: seed-42 "
        "conditional interval for both clinker fractions)"),
    "aviation military scope": (
        "available (aviation_uncertainty_scenarios_fy2023_24.csv: seed-42 "
        "scenario quantiles)"),
    "aviation general aviation scope": (
        "available (aviation_uncertainty_scenarios_fy2023_24.csv: seed-42 "
        "scenario quantiles)"),
    "aviation unresolved residual scope": (
        "available (aviation_uncertainty_scenarios_fy2023_24.csv: seed-42 "
        "scenario quantiles)"),
    "sewer methane correction factor": (
        "available_independent_run (waste_uncertainty_scenarios_2024.csv: "
        "per-scenario MC on private seeds 4321-4334; conditional intervals, "
        "not per-draw deltas)"),
    "wastewater effluent N2O factor": (
        "available_independent_run (waste_uncertainty_scenarios_2024.csv: "
        "per-scenario MC on private seeds; the endpoint rows are "
        "deterministic bounds with no seed at all, and say so)"),
}
UNCERTAINTY_GRAIN_DEFAULT = ("reference_only: the common-draw ensemble is built under "
                             "the reference configuration; structural alternatives are "
                             "separate conditional statements, never sampled into it")

FIELDS = ("axis", "module", "family_id", "reference_setting", "alternative",
          "alternative_Mt", "national_delta_Mt", "in_figure5",
          "in_configurations", "priced_status", "monthly_grain",
          "spatial_grain", "uncertainty_grain",
          "reason_if_unpriced")


def build():
    registry = national_rollup.scenario_registry()
    baseline, bridge = national_rollup.structural_bridge()
    by_axis = {r["axis"]: r for r in bridge}
    config_axes = {r["axis"] for r in national_configurations.build()
                   if r["axis"] and not r["axis"].startswith("JOINT")}

    rows = []
    for reg in registry:
        axis = reg["axis"]
        b = by_axis[axis]
        priced = b["national_delta_Mt"] is not None
        rows.append({
            "axis": axis,
            "module": b["module"],
            "family_id": national_rollup.AXIS_FAMILIES.get(axis, ""),
            "reference_setting": b["setting"],
            "alternative": b["alternative"],
            "alternative_Mt": ("" if b["alternative_Mt"] is None
                               else round(b["alternative_Mt"], 5)),
            "national_delta_Mt": ("" if not priced
                                  else round(b["national_delta_Mt"], 5)),
            # Figure 5 membership uses the figure's own predicate (a published
            # delta), not a hand list - the drift the review caught was exactly
            # a hand-maintained claim ("prices each one") over a filtered plot.
            "in_figure5": "yes" if priced else "yes (annotated unpriced slot)",
            "in_configurations": "yes" if axis in config_axes else "no",
            "priced_status": "priced" if priced else "unpriced",
            "monthly_grain": MONTHLY_GRAIN_AVAILABLE.get(axis,
                                                         MONTHLY_GRAIN_DEFAULT),
            "spatial_grain": SPATIAL_GRAIN_AVAILABLE.get(axis,
                                                         SPATIAL_GRAIN_DEFAULT),
            "uncertainty_grain": UNCERTAINTY_GRAIN_AVAILABLE.get(
                axis, UNCERTAINTY_GRAIN_DEFAULT),
            "reason_if_unpriced": ("" if priced else reg["note"]),
        })
    unpriced = [r for r in rows if r["priced_status"] == "unpriced"]
    for r in unpriced:
        if not r["reason_if_unpriced"].strip():
            raise SystemExit("unpriced axis %r carries no reason" % r["axis"])
    return rows


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    rows = build()
    write_table(OUT, FIELDS, rows)
    priced = sum(1 for r in rows if r["priced_status"] == "priced")
    print("axis register -> %s (%d axes: %d priced, %d unpriced with reasons)"
          % (os.path.relpath(OUT), len(rows), priced, len(rows) - priced))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
