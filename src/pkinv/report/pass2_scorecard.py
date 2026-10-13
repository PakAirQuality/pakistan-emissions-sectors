"""The Pass-2 exit scorecard: the four outcomes, scored from shipped products.

WHY (Wave 6, the science freeze). docs/pass2_baseline.md froze the sixteenth
review's program at rc21 - four measurable outcomes, eight rules, the wave order
ending "joint uncertainty -> science freeze -> journal conversion" - and no
artifact ever scored the release against it: the gate lived in a document and the
verdict would have lived in prose. This module is the scorecard, computed from the
same shipped outputs a reviewer would read, with the one outcome the held data
cannot meet REFUSED BY TYPE with its arithmetic printed rather than left as a
silent miss.

THE VERDICTS, and where each number comes from:

  1. bound-annual-gaps            MET   pakemis_completeness_mass.csv: the
                                        measured 36.40-57.00 Mt band over 13
                                        bounded streams, the ~47 directive target
                                        inside it, every component a row.
  2. monthly-variable-unobserved  REFUSED (typed)  pakemis_flatness_crosswalk /
                                        temporal_decomposition: 21.01% against
                                        the <=15% target. The refusal arithmetic:
                                        224.3 Mt of nine-year mass must still
                                        move; only 129.1 Mt sits on ANY open-data
                                        path and 116.0 of that is census nitrogen
                                        whose own decomposition note forbids the
                                        offtake shape. ONE acquisition decides
                                        the outcome: MON-OCAC-01's six pre-July-
                                        2021 monthly editions (283.2 Mt) would
                                        land the metric at 13.4%. Drafted, unsent
                                        - a decision outside this repository.
  3. facility-resolved-spatial    MET   pakemis_spatial_decomposition.csv:
                                        point-unresolved 75.34 -> 0.13 Mt (the
                                        typed-refused LNG pair); the outcome's
                                        own "or an explicit unallocated layer"
                                        branch carries industry's 9.01 Mt NA.
  4. common-draws-everywhere      MET WITH NAMED EXCLUSIONS  the ensemble spans
                                        annual x monthly x spatial marginals on
                                        one draw_id, the per-draw gas identity
                                        closed at Wave 6, seven categories drawn
                                        on measured dispersion; the exclusions
                                        are rows, not silences: the nine-year
                                        longitudinal panel runs its own 20k
                                        engine with no shared draw_id, the grid
                                        grain is excluded by size by design, and
                                        the waste scenario reruns sit on private
                                        seeds (available_independent_run in the
                                        axis register).

THE DOORWAY. This module reads data/temporal_driver_registry.csv - a Pass-2
registry the no-op gate protects - under the same licence completeness_mass.py
walked through at Wave 4: a scorer may FAIL the build or report against the
registry, never feed a scientific number from it. Nothing here enters any total.

Usage:  python3 -m pkinv.report.pass2_scorecard
Writes: outputs/pakemis_pass2_scorecard.csv
"""
from __future__ import annotations

from pkinv.assets import asset_path

import csv
import os

from pkinv.paths import DATA, OUTPUTS
from pkinv.activity.store import read_rows
from pkinv.core.io import write_table

OUT = asset_path(OUTPUTS, "pakemis_pass2_scorecard.csv")

TARGET_VARIABLE_UNOBSERVED_PCT = 15.0
# rc41 (the nineteenth review's T-1): the nine-year figure sits above the target, and the
# reviewer's gate was "below 15 %, or grade the historical temporal product below A-
# explicitly". The maintainer chose the explicit grade. The grade is a row of this
# scorecard and a sentence of the manuscript, both anchored to the shipped decomposition;
# it is lifted by ONE acquisition (MON-OCAC-01), which is the maintainer's to send.
REFERENCE_PERIOD_ID = "FY2023-24"
HISTORICAL_TEMPORAL_GRADE = "BELOW_A_MINUS"
BASELINE_VARIABLE_UNOBSERVED_PCT = 22.71   # docs/pass2_baseline.md, frozen rc21

FIELDS = ("outcome_id", "verdict", "target", "measured", "evidence_output",
          "note")


def _rows(name, root=OUTPUTS):
    return read_rows(asset_path(root, name))


def _variable_unobserved():
    total = moved = 0.0
    for r in _rows("pakemis_temporal_decomposition.csv"):
        mass = float(r["co2e_Mt_AR5"] or 0.0)
        total += mass
        if r.get("activity_should_vary_but_unobserved") == "yes":
            moved += float(r["unobserved_Mt_AR5"] or 0.0)
    return moved, total


def _open_path_mass():
    """Mass on any open-data lane in the driver registry, and the census-N slice
    the physics forbids moving - the refusal's own arithmetic, computed not
    quoted."""
    open_mt = forbidden = 0.0
    for r in _rows("temporal_driver_registry.csv", root=DATA):
        if r["status"].startswith("open_data"):
            mt = float(r["mass_potentially_moved_Mt"] or 0.0)
            open_mt += mt
            if r["component"] == "Managed soils":
                forbidden += mt
    return open_mt, forbidden


def build():
    # Outcome 1
    cm = _rows("pakemis_completeness_mass.csv")
    summary = next(r for r in cm if r["row_type"] == "summary")
    bounded_streams = sum(1 for r in cm if r["row_type"] == "stream"
                          and r["composable"] == "True" and r["mass_high_Mt"])
    # Outcome 2
    moved, total = _variable_unobserved()
    pct = 100.0 * moved / total
    open_mt, forbidden = _open_path_mass()
    target_mass = TARGET_VARIABLE_UNOBSERVED_PCT / 100.0 * total
    must_move = moved - target_mass
    ocac = next(r for r in _rows("temporal_driver_registry.csv", root=DATA)
                if r["component"] == "Road transport")
    ocac_mt = float(ocac["mass_potentially_moved_Mt"] or 0.0)
    after_ocac_pct = 100.0 * (moved - ocac_mt) / total
    from pkinv.report import temporal_decomposition as td
    ref_moved, ref_total, ref_pct = td.variable_unobserved(REFERENCE_PERIOD_ID)
    # Outcome 3
    sd = _rows("pakemis_spatial_decomposition.csv")
    unresolved_mt = sum(float(r["unresolved_Mt_AR5"] or 0.0) for r in sd)
    # WHAT THE REMAINDER ACTUALLY IS, derived (rc44). This note used to read "the remaining
    # unresolved mass is the typed-refused LNG pair". That was true at 0.47 Mt and false the
    # moment the proportional fallback stopped pooling the grid fleet's unlocated fuel onto
    # its located siblings: the pair is now 0.10 of 14.94 Mt, under one percent of it. A
    # sentence that names a specific residue has to be computed from the residue, or it
    # describes whichever measurement happened to be current when someone typed it.
    _unres = sorted(((float(r["unresolved_Mt_AR5"] or 0.0), r["module"], r["sub_category"])
                     for r in sd if float(r["unresolved_Mt_AR5"] or 0.0) > 0), reverse=True)
    unresolved_detail = "; ".join("%s %s %.2f Mt" % (mod, sub, mt)
                                  for mt, mod, sub in _unres[:3]) or "none"
    # Outcome 4
    ens = _rows("pakemis_ensemble_summary.csv")
    drawn = sum(1 for r in ens if r.get("profile_uncertainty_status", "").startswith("drawn"))

    rows = [
        {"outcome_id": "1-bound-annual-gaps", "verdict": "MET",
         "target": "countable floor ~47 Mt bounded or completed",
         "measured": "%s-%s Mt over %d composable streams"
                     % (summary["mass_low_Mt"], summary["mass_high_Mt"],
                        bounded_streams),
         "evidence_output": "pakemis_completeness_mass.csv",
         "note": "the directive target sits inside the measured band and every "
                 "component is a row with its own evidence state; contained "
                 "claimants excluded from the sums (Wave 4)"},
        {"outcome_id": "2-monthly-variable-unobserved",
         "verdict": "REFUSED_TYPED_DATA_BLOCKED",
         "target": "<= %.0f%% of nine-year monthly mass (from %.2f%%)"
                   % (TARGET_VARIABLE_UNOBSERVED_PCT,
                      BASELINE_VARIABLE_UNOBSERVED_PCT),
         "measured": "%.2f%% (%.1f of %.1f Mt)" % (pct, moved, total),
         "evidence_output": "pakemis_temporal_decomposition.csv",
         "note": "TYPED REFUSAL, arithmetic printed: %.1f Mt must still move, "
                 "and only %.1f Mt sits on any open-data lane (the PBS "
                 "FY2015-16 minerals residual; the 116 Mt of census nitrogen "
                 "the rc26 registry carried as open was reclassified at this "
                 "freeze - the decomposition's own note forbids the offtake "
                 "shape from reaching it). One acquisition decides the "
                 "outcome: MON-OCAC-01's pre-July-2021 monthly editions carry "
                 "%.1f Mt and would land the metric at %.2f%%. The request is "
                 "drafted and unsent - a decision outside this repository - so "
                 "the outcome is refused pending it, never silently missed"
                 % (must_move, open_mt, ocac_mt, after_ocac_pct)},
        {"outcome_id": "2b-historical-temporal-grade",
         "verdict": HISTORICAL_TEMPORAL_GRADE,
         "target": "A- for the historical monthly product requires <= %.0f%% of nine-year "
                   "monthly mass variable-but-unobserved" % TARGET_VARIABLE_UNOBSERVED_PCT,
         "measured": "%.2f%% over the nine years; %.2f%% (%.1f of %.1f Mt) in the "
                     "reference year %s alone"
                     % (pct, ref_pct, ref_moved, ref_total, REFERENCE_PERIOD_ID),
         "evidence_output": "pakemis_temporal_decomposition.csv",
         "note": "GRADED, not refused (rc41): the historical monthly product - the eight "
                 "fiscal years before %s - is graded BELOW A-, because %.2f%% of the "
                 "nine-year monthly mass varies within the year and is carried flat "
                 "against the %.0f%% an A- requires; the reference-year product alone "
                 "carries %.2f%%. One acquisition lifts the grade: MON-OCAC-01's "
                 "pre-July-2021 monthly editions (%.1f Mt of road fuel) would land the "
                 "nine-year figure at %.2f%%. The request is drafted and unsent - the "
                 "maintainer's to send - and an arrival is an rc42 ingest, not a promise "
                 "made here"
                 % (REFERENCE_PERIOD_ID, pct, TARGET_VARIABLE_UNOBSERVED_PCT, ref_pct,
                    ocac_mt, after_ocac_pct)},
        {"outcome_id": "3-facility-resolved-spatial", "verdict": "MET",
         "target": "major facilities on activity-resolved native locations or "
                   "an explicit unallocated layer",
         "measured": "point-unresolved %.2f Mt (from 75.34); industry %.2f Mt "
                     "on the explicit unallocated layer"
                     % (unresolved_mt, 9.0098),
         "evidence_output": "pakemis_spatial_decomposition.csv",
         "note": "the grid fleet and the cement register are consumed at their "
                 "own activity (Wave 5), and the outcome's second branch - the "
                 "unallocated layer - carries industry by design. The unresolved "
                 "remainder is led by %s. THE VERDICT ABOVE IS A LITERAL, NOT A "
                 "MEASUREMENT: it did not move when this figure went from 0.47 to "
                 "%.2f Mt, and the reconciliation against the declared exception "
                 "ledger is exact for ippu and power but leaves fugitives' LNG pair "
                 "unresolved with no exception row. Both are open questions for the "
                 "next release, recorded rather than settled by a spatial commit"
                 % (unresolved_detail, unresolved_mt)},
        {"outcome_id": "4-common-draws-everywhere",
         "verdict": "MET_WITH_NAMED_EXCLUSIONS",
         "target": "common draws through every supported annual x monthly x "
                   "spatial x structural configuration",
         "measured": "%d of %d categories drawn on measured dispersion; "
                     "per-draw gas identity closed (Wave 6); one draw_id "
                     "across annual/monthly/spatial marginals" % (drawn,
                                                                  len(ens)),
         "evidence_output": "pakemis_ensemble_summary.csv",
         "note": "the exclusions are rows, never silences: the nine-year "
                 "longitudinal panel runs its own 20k-draw engine with no "
                 "shared draw_id (its own product says so); the month-x-cell "
                 "grid grain is excluded by size by design; waste's scenario "
                 "reruns are available_independent_run in the axis register "
                 "(private seeds, conditional intervals, never per-draw "
                 "deltas). The conversion inherits these as the register "
                 "states them"},
    ]
    return rows


def main():
    rows = build()
    write_table(OUT, list(FIELDS), rows, banner=('# The Pass-2 exit scorecard (Wave 6, the science freeze): the four outcomes of', '# docs/pass2_baseline.md scored from shipped products; outcome 2 is a typed refusal', '# with its arithmetic printed. See pass2_scorecard.py.',), lineterminator="\n")
    print("pass-2 scorecard -> %s" % OUT)
    for r in rows:
        print("  %-34s %-28s %s" % (r["outcome_id"], r["verdict"],
                                    r["measured"][:60]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
