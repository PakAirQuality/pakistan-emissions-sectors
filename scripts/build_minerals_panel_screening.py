"""Validate final minerals exports and report source quality and timing eligibility.

The repaired panel has one selected printed-year source group for each supported
mineral-year. Source-quality anomalies remain separate from extraction defects.
"""
import collections
import os
from pkinv.assets import asset_path
from pkinv.core.io import read_rows, write_table
from pkinv.core import pbs_minerals
from pkinv.paths import ROOT

OUT = asset_path(ROOT, "outputs/pakemis_minerals_panel_screening.csv")
PANEL = asset_path(ROOT, "data/activity/monthly/pbs_minerals_month_province.csv")
NATIONAL = "National (edition prints no province split)"

def panel():
    return read_rows(PANEL)

def build(rows=None):
    rows = panel() if rows is None else rows
    out = []
    cells = sorted({(r["canonical_mineral"], int(r["fiscal_year_start"])) for r in rows})
    for mineral, fy in cells:
        members = [r for r in rows if r["canonical_mineral"] == mineral and int(r["fiscal_year_start"]) == fy]
        provinces = sorted({r["province"] for r in members})
        expected = set(members[0]["source_expected_provinces"].split(";"))
        missing = sorted(expected - set(provinces))
        counts = collections.Counter(r["month"] for r in members)
        shipped = sum(float(r["quantity"]) for r in members if r["quantity"] != "")
        printed = {r["month"]: float(r["source_national_month_quantity"]) for r in members
                   if r["source_national_month_quantity"] != ""}
        declared = sum(printed.values())
        residual = max((abs(sum(float(r["quantity"]) for r in members if r["month"] == month
                               and r["quantity"] != "") - control)
                        for month, control in printed.items()), default=0.0)
        shares, methods, covered = pbs_minerals.profile_or_flat(mineral, fy, rows)
        agrees = residual <= 2 and not missing
        verdict = ("source-quality fallback" if members[0]["timing_usable"] == "no" else
                   "national only, as the edition printed it" if provinces == [NATIONAL] else
                   "complete source-controlled provincial panel" if agrees else "invalid exported coverage")
        out.append({"canonical_mineral": mineral, "fiscal_year_start": fy,
            "provinces_present": ";".join(provinces), "provinces_missing": ";".join(missing) or "none",
            "rows_per_month": ";".join(str(n) for n in sorted(set(counts.values()))),
            "months_covered": len(counts), "panel_quantity": "%.3f" % shipped,
            "verdict": verdict, "shape_cost_max_pp": "n.a.", "shape_cost_mean_pp": "n.a.",
            "served_worst_month_share_pct": "%.5f" % (100 * max(shares.values())),
            "served_profile_pct": ";".join("%.5f" % (100 * shares[m]) for m in sorted(shares)),
            "served_timing_method": ";".join(sorted(set(methods.values()))),
            "served_as_covered": "yes" if covered else "no",
            "group_control_declared": "%.3f" % declared, "panel_ships": "%.3f" % shipped,
            "control_agrees_with_panel": "yes" if agrees else "NO",
            "panel_share_of_control_pct": "%.5f" % (100 * shipped / declared) if declared else "n.a.",
            "max_month_control_residual": residual, "quantity_unit": members[0]["quantity_unit"],
            "note": members[0]["quality_note"] or "Final exported records checked against source national months"})
    return out

def main():
    rows = build()
    write_table(OUT, list(rows[0]), rows, banner=[
        "Corrected minerals final-export validation; each supported mineral-year is source-controlled.",
        "FY2021-22 oil/gas observations retained but source-quality anomalies require days-weighted T4 timing.",
        "Structural timing fallback is not a parameter uncertainty interval."])
    print("Minerals screening: %d cells; maximum national monthly residual %.6g native units" %
          (len(rows), max(r["max_month_control_residual"] for r in rows)))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
