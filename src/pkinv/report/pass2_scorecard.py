"""Historical Pass-2 targets compared with current supporting diagnostics.

These internal targets predate the integrated release. They are retained for
traceability, not as scientific quality grades or a release completion gate. The
reported quantities come from the named products; none enters emissions totals.
A candidate-source range is not a confidence interval, a spatial fallback is not
an observed facility release, and conditional profile draws do not establish
uncertainty coverage at every resolution.
"""
from __future__ import annotations

from pkinv.assets import asset_path
from pkinv.paths import OUTPUTS
from pkinv.activity.store import read_rows
from pkinv.core.io import write_table
from pkinv.core.reporting_window import CORE_FY_STARTS, REFERENCE_PERIOD, fiscal_label

OUT = asset_path(OUTPUTS, "pakemis_pass2_scorecard.csv")
TARGET_VARIABLE_UNOBSERVED_PCT = 15.0
REFERENCE_PERIOD_ID = REFERENCE_PERIOD
HISTORICAL_ANNUAL_TARGET_MT = 47.0
FIELDS = ("outcome_id", "verdict", "target", "measured", "evidence_output", "note")


def _rows(name, root=OUTPUTS):
    return read_rows(asset_path(root, name))


def _variable_unobserved(rows=None):
    rows = _rows("pakemis_temporal_decomposition.csv") if rows is None else rows
    total = sum(float(r["co2e_Mt_AR5"] or 0.0) for r in rows)
    unobserved = sum(float(r["unobserved_Mt_AR5"] or 0.0) for r in rows
                     if r.get("activity_should_vary_but_unobserved") == "yes")
    if total <= 0.0 or not 0.0 <= unobserved <= total:
        raise ValueError("Invalid temporal diagnostic mass account")
    return unobserved, total


def build():
    cm = _rows("pakemis_completeness_mass.csv")
    summary = next(r for r in cm if r["row_type"] == "summary")
    raw_low, raw_high = summary["mass_low_Mt"], summary["mass_high_Mt"]
    if (raw_low == "") != (raw_high == ""):
        raise ValueError("Incomplete candidate-source range")
    low, high = ((float(raw_low), float(raw_high)) if raw_low != "" else (None, None))
    if low is not None and not 0.0 <= low <= high:
        raise ValueError("Invalid remaining candidate-source range")
    bounded_streams = sum(r["row_type"] == "stream" and r["composable"] == "True"
                          and bool(r["mass_high_Mt"]) for r in cm)
    annual_verdict = ("RETIRED_TARGET_NO_QUANTIFIED_AGGREGATE" if low is None else
                      "HISTORICAL_TARGET_WITHIN_REMAINING_RANGE"
                      if low <= HISTORICAL_ANNUAL_TARGET_MT <= high else
                      "HISTORICAL_TARGET_OUTSIDE_REMAINING_RANGE")
    annual_metric = ("National missing-emissions mass unquantified; source cases are not composed"
                     if low is None else "%g-%g Mt remaining candidate-source range; %d composable streams"
                     % (low, high, bounded_streams))

    unobserved, total = _variable_unobserved()
    pct = 100.0 * unobserved / total
    threshold_verdict = ("HISTORICAL_THRESHOLD_SATISFIED"
                         if pct <= TARGET_VARIABLE_UNOBSERVED_PCT else
                         "HISTORICAL_THRESHOLD_EXCEEDED")
    window = "%s through %s (%d fiscal years)" % (
        fiscal_label(CORE_FY_STARTS[0]), fiscal_label(CORE_FY_STARTS[-1]),
        len(CORE_FY_STARTS))
    from pkinv.report import temporal_decomposition as td
    ref_unobserved, ref_total, ref_pct = td.variable_unobserved(REFERENCE_PERIOD_ID)

    sd = _rows("pakemis_spatial_decomposition.csv")
    unresolved_mt = sum(float(r["unresolved_Mt_AR5"] or 0.0) for r in sd)
    spatial_total = sum(float(r["co2e_Mt_AR5"] or 0.0) for r in sd)
    if not 0.0 <= unresolved_mt <= spatial_total:
        raise ValueError("Invalid spatial diagnostic mass account")
    unresolved = sorted(((float(r["unresolved_Mt_AR5"] or 0.0),
                           r["module"], r["sub_category"]) for r in sd
                          if float(r["unresolved_Mt_AR5"] or 0.0) > 0), reverse=True)
    unresolved_detail = "; ".join("%s %s %.2f Mt" % (mod, sub, mt)
                                  for mt, mod, sub in unresolved[:3]) or "none"

    ens = _rows("pakemis_ensemble_summary.csv")
    categories = [r for r in ens if r["name"] != "NATIONAL_TOTAL"]
    drawn = sum(r.get("profile_uncertainty_status", "").startswith("drawn")
                for r in categories)
    return [
        {"outcome_id": "1-bound-annual-gaps", "verdict": annual_verdict,
         "target": "historical internal target approximately %.0f Mt" % HISTORICAL_ANNUAL_TARGET_MT,
         "measured": annual_metric,
         "evidence_output": "pakemis_completeness_mass.csv",
         "note": "The source ledger distinguishes NE categories, conditional source cases and "
                 "external comparisons. Comparator differences are not missing-source floors "
                 "or upper bounds and are not a statistical confidence interval. No target "
                 "is satisfied by adding those quantities. The retired internal target does "
                 "not grade completeness of the current inventory."},
        {"outcome_id": "2-monthly-variable-unobserved", "verdict": threshold_verdict,
         "target": "historical internal threshold <= %.0f%% variable-but-unobserved GHG mass"
                   % TARGET_VARIABLE_UNOBSERVED_PCT,
         "measured": "%.2f%% (%.1f of %.1f Mt CO2e AR5); %s"
                     % (pct, unobserved, total, window),
         "evidence_output": "pakemis_temporal_decomposition.csv",
         "note": "Computed from streams marked activity_should_vary_but_unobserved=yes. "
                 "Physically continuous processes are distinguished in the source diagnostic. "
                 "This GHG mass-weighted metric does not describe pollutant-specific temporal "
                 "evidence, and the historical threshold is not an externally established "
                 "quality standard. No assumed future acquisition is subtracted."},
        {"outcome_id": "2b-historical-temporal-grade", "verdict": "RETIRED_INTERNAL_GRADE",
         "target": "historical A- label; retired as a scientific product grade",
         "measured": "%s reference %.2f%% (%.1f of %.1f Mt CO2e AR5) variable-but-unobserved"
                     % (REFERENCE_PERIOD_ID, ref_pct, ref_unobserved, ref_total),
         "evidence_output": "pakemis_temporal_decomposition.csv",
         "note": "The former letter grade is retained only as a historical target identifier. "
                 "The current product reports evidence classes and their mass shares; a letter "
                 "grade is neither a measurement nor a parameter uncertainty interval."},
        {"outcome_id": "3-facility-resolved-spatial", "verdict": "DIAGNOSTIC_UNRESOLVED_MASS",
         "target": "historical facility-location or explicit-unallocated criterion; not graded",
         "measured": "%.2f of %.2f Mt CO2e AR5 unresolved in the %s spatial diagnostic"
                     % (unresolved_mt, spatial_total, REFERENCE_PERIOD_ID),
         "evidence_output": "pakemis_spatial_decomposition.csv",
         "note": "Largest unresolved components: %s. The source's unresolved column includes "
                 "mass placed with fallback proxies; it is not identical to an unallocated "
                 "layer. Coordinates alone do not establish own-year facility activity or "
                 "emitting-process location. No fixed pass verdict is inferred from this sum."
                 % unresolved_detail},
        {"outcome_id": "4-common-draws-everywhere", "verdict": "RETIRED_UNIVERSAL_DRAW_GATE",
         "target": "historical universal annual/monthly/spatial draw criterion; not graded",
         "measured": "%d of %d category rows have drawn conditional monthly profiles"
                     % (drawn, len(categories)),
         "evidence_output": "pakemis_ensemble_summary.csv",
         "note": "This supporting reference-year ensemble summary identifies profile-draw "
                 "statuses. It does not demonstrate full spatial, temporal, structural or "
                 "missing-source uncertainty. Current native multi-year GHG and air-pollutant "
                 "conditional level/trend products and their parameter registers specify "
                 "their own configurations, dependence cases and fixed allocation limits. "
                 "Structural cases carry no assigned probability."},
    ]


def main():
    rows = build()
    write_table(OUT, list(FIELDS), rows, banner=(
        "# Historical Pass-2 targets and current supporting diagnostics; no scientific release grade.",
        "# Conditional candidate-source ranges, evidence metrics and parameter uncertainty are distinct.",
        "# See pkinv.report.pass2_scorecard; none of these rows feeds an emissions estimate.",
    ), lineterminator="\n")
    print("historical pass-2 diagnostic -> %s" % OUT)
    for row in rows:
        print("  %-34s %-42s %s" %
              (row["outcome_id"], row["verdict"], row["measured"][:60]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
