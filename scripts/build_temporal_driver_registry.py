"""The Pass-2 temporal-driver registry: every stream's timing state and its planned move.

WHY THIS EXISTS. The sixteenth review's Pass-2 program sets one measurable monthly
outcome - genuinely time-variable-but-unobserved mass falls from 22.7% to at most ~15% -
and forbids the two ways that number could be gamed: inventing seasonality for processes
that are physically continuous, and letting "flat" mean both "correct physics" and
"nobody read the records". This registry is the program's ledger: one row per
decomposition stream, its CURRENT state derived from outputs/pakemis_temporal_decomposition.csv
(never retyped), and its PLANNED state from a reviewed plan table in this script. The
derived columns cannot drift because they are regenerated; the planned columns cannot
hide because an unplanned variable-unobserved stream defaults to request_gated, which is
a status a reader can audit, not a silence.

THE PROCESS CLASS is the review's six-way vocabulary, derived - not judged - from the
decomposition's own columns: physically-appropriate flatness splits into
physically_continuous and stock_driven on the decomposition's flatness_class;
should-vary-but-unobserved is variable_unobserved regardless of how much of the stream
is already timed (direct_months_available carries that); what remains is timed, and the
evidence grade says how: TE2 administrative_proxy, TE3 modeled_seasonality, TE1
observed_activity.

MASS IS NEVER PLANNED, ONLY MEASURED. expected_te_after_pass2 and driver_source are
plans; mass_potentially_moved is the stream's own unobserved mass from the decomposition
- the ceiling on what the plan could move, not a promise of what it will.

Usage:  python3 scripts/build_temporal_driver_registry.py
Writes: data/temporal_driver_registry.csv
"""
import csv
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.assets import asset_path
import pkinv  # noqa: E402

DECOMPOSITION = asset_path(ROOT, "outputs", "pakemis_temporal_decomposition.csv")
OUT = asset_path(ROOT, "data", "temporal_driver_registry.csv")

FIELDS = ("stream_id", "sector_id", "component", "annual_mass_Mt", "current_te",
          "current_process_class", "driver_source", "direct_months_available_pct",
          "expected_te_after_pass2", "mass_potentially_moved_Mt", "status",
          "algorithm_version")

# The reviewed plan: (sector_id, component) -> (expected TE after Pass 2, the named
# driver, the wave or gate it rides). A stream absent here keeps its derived state:
# variable_unobserved defaults to request_gated (the honest exit), everything else to
# no_action_needed. Nothing in this table moves mass; each entry names the evidence
# that would.
PLAN = {
    ("agriculture", "Managed soils"): (
        "TE2", "the FERTILISER half is DELIVERED (NFDC Annex 5/7, all twelve own "
        "months, held); the remaining unobserved mass is deposited and applied "
        "CENSUS NITROGEN, which rides a livestock count and a harvest and which "
        "the decomposition's own note forbids the offtake shape from reaching "
        "(a test asserts it did not come along) - so the registry no longer "
        "carries it as movable open-data mass. The rc26 registry said "
        "open_data_wave2 over 116 Mt the physics had already refused: a status "
        "the arithmetic contradicted, corrected at the Wave-6 freeze",
        "no_action_needed"),
    ("power", "Electricity and heat production"): (
        "TE2", "the seven-year SIR listing panel delivered (Wave 2); the residual is "
        "FY2015-16/FY2016-17, whose FCA determination corpus is HELD "
        "(data/raw/nepra/fca, 49 XWDISCO documents) but refused for parse - scan-grade "
        "digits, plant-wise annex in few months (search log power-fy2015-17-*); "
        "MON-CPPAG-01 is the remedy",
        "request_gated"),
    ("fugitives", "Gas production"): (
        "TE2", "PBS Energy & Mining bulletin vintages (revision-resolved)",
        "open_data_wave2"),
    ("fugitives", "Gas gathering"): (
        "TE2", "PBS Energy & Mining bulletin vintages (revision-resolved)",
        "open_data_wave2"),
    ("fugitives", "Gas processing"): (
        "TE2", "PBS Energy & Mining bulletin vintages (revision-resolved)",
        "open_data_wave2"),
    ("fugitives", "Sour-gas processing"): (
        "TE2", "PBS Energy & Mining bulletin vintages (revision-resolved)",
        "open_data_wave2"),
    ("fugitives", "Oil production"): (
        "TE2", "PBS Energy & Mining bulletin vintages (revision-resolved)",
        "open_data_wave2"),
    ("agriculture", "Field burning of residues"): (
        "TE3", "Held VIIRS crop-window detections cover FY2015-16 through FY2023-24 "
        "with the shared national/cropland/kiln attribution ladder. FY2024-25 "
        "has no held detection window and retains TE4 elapsed-days timing; its "
        "open source-evidence gap is not an observed fire profile or a promised acquisition.",
        "open_data_wave3"),
    ("waste", "Solid waste disposal"): (
        "TE3", "DELIVERED (Wave 3): the continuous monthly FOD state engine "
        "(single-pool recursion from the 1960 spin-up, own-year deposits, "
        "calendar-day months, declared reaction delay) as FOD_shaped_allocation "
        "- annual control preserved exactly; nothing further is open-data-gated",
        "no_action_needed"),
    ("agriculture", "Rice cultivation"): (
        "TE3", "DELIVERED (Wave 3): cultivation area-days across the provincial "
        "calendars, harvested-area weighted, FAO-corroborated harvest end. The "
        "water-regime alternative is PRICED since Wave 6 as the "
        "rice_water_regime_weighted configuration (SPAM-weighted SFw 0.594 "
        "against the continuous 1.0 - the earlier '~0.71' in this note matched "
        "no IPCC value and was computed by nothing; the weighted value now has "
        "one home, water_regime.py, and this note quotes it rather than "
        "re-deriving it)",
        "no_action_needed"),
    ("power", "Captive gas self-generation (1A2)"): (
        "TE3", "monthly captive-generation gas use - request-gated (CPPA/OGRA); no "
        "open monthly series held",
        "request_gated"),
    ("transport", "Road transport"): (
        "TE4", "the OCAC monthly panel opens July 2021; the six earlier years need "
        "the historical editions (MON-OCAC-01)",
        "request_gated"),
}


def _slug(sector, component):
    keep = "".join(c if c.isalnum() else "_" for c in component.lower())
    while "__" in keep:
        keep = keep.replace("__", "_")
    return "%s:%s" % (sector, keep.strip("_"))


def process_class(row):
    if row["flatness_class"] == "stock_driven":
        return "stock_driven"
    if row["flatness_class"] == "continuous_by_process":
        return "physically_continuous"
    if row["activity_should_vary_but_unobserved"] == "yes":
        return "variable_unobserved"
    return {"TE1": "observed_activity", "TE2": "administrative_proxy",
            "TE3": "modeled_seasonality"}.get(row["evidence_grade"],
                                              "administrative_proxy")


def build():
    with open(DECOMPOSITION, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    out = []
    for row in rows:
        key = (row["sector_id"], row["component"])
        cls = process_class(row)
        planned = PLAN.get(key)
        if planned:
            expected, driver, status = planned
        elif cls == "variable_unobserved":
            expected, driver, status = row["evidence_grade"], \
                row["expected_temporal_driver"], "request_gated"
        else:
            expected, driver, status = row["evidence_grade"], \
                row["expected_temporal_driver"], "no_action_needed"
        out.append({
            "stream_id": _slug(*key), "sector_id": key[0], "component": key[1],
            "annual_mass_Mt": row["co2e_Mt_AR5"], "current_te": row["evidence_grade"],
            "current_process_class": cls, "driver_source": driver,
            "direct_months_available_pct": row["months_observed_pct"],
            "expected_te_after_pass2": expected,
            "mass_potentially_moved_Mt": row["unobserved_Mt_AR5"],
            "status": status, "algorithm_version": pkinv.__version__,
        })
    return out


def main():
    rows = build()
    with open(OUT, "w", newline="", encoding="utf-8") as handle:
        handle.write("# Pass-2 temporal-driver registry (sixteenth review, Wave 0).\n")
        handle.write("# GENERATED by scripts/build_temporal_driver_registry.py - the\n")
        handle.write("# derived columns come from outputs/pakemis_temporal_decomposition.csv\n")
        handle.write("# and regenerate; the plan columns come from the PLAN table in the\n")
        handle.write("# script. Do not edit by hand.\n")
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    import collections
    print("temporal driver registry -> %s (%d streams)"
          % (os.path.relpath(OUT, ROOT), len(rows)))
    for status, n in collections.Counter(r["status"] for r in rows).most_common():
        mass = sum(float(r["mass_potentially_moved_Mt"]) for r in rows
                   if r["status"] == status)
        print("  %-20s %2d streams, %8.1f Mt potentially moved" % (status, n, mass))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
