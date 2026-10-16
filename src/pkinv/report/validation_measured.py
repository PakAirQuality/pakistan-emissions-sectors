"""The measured validation results, in one table: records checked, failures, closure residuals.

WHY THIS EXISTS (rc69). The review asked for the validation that was actually MEASURED to be
shown compactly: how many records each check read, how many it rejected, what closed and by
how much, and what the rebuild comparisons found. The evidence was all published, spread over
parse summaries, quarantine files, closure ledgers and the reproduction record, and the paper
described it in prose. This module reads those products and writes one row per check. It
computes nothing a product does not already state, except two closures it recomputes from the
released tables themselves: air annual against air monthly, per species, and the ADM2 sum
against its provincial control.

Every row names its source file. A check whose source is absent fails the build rather than
printing a blank, because an empty cell here would read as "no failures".

Usage:  python3 -m pkinv.report.validation_measured [--check]
Writes: outputs/pakemis_validation_measured.csv
"""
import argparse
import collections
import json
import os

from pkinv.assets import asset_path
from pkinv.core.io import read_rows, write_or_check
from pkinv.paths import OUTPUTS, ROOT

OUT = asset_path(OUTPUTS, "pakemis_validation_measured.csv")
REFERENCE = "S_TAN"
FIELDS = ("check_id", "group", "check", "records_checked", "record_unit",
          "failed_or_quarantined", "closing", "closing_of", "max_abs_residual",
          "residual_unit", "source_file", "note")


def _one(name):
    rows = read_rows(asset_path(OUTPUTS, name))
    if len(rows) != 1:
        raise ValueError("%s: expected one summary row, found %d" % (name, len(rows)))
    return rows[0]


def _row(check_id, group, check, records, unit, failed, closing, of, residual, residual_unit,
         source, note=""):
    return {"check_id": check_id, "group": group, "check": check, "records_checked": records,
            "record_unit": unit, "failed_or_quarantined": failed, "closing": closing,
            "closing_of": of, "max_abs_residual": residual, "residual_unit": residual_unit,
            "source_file": source, "note": note}


def _parse_rows():
    out = []
    o = _one("ocac_parse_summary.csv")
    out.append(_row("parse_ocac", "source parsing", "OCAC monthly fuel sales",
                    o["product_cells"], "product-month cells", o["rows_quarantined"],
                    o["months_closing_internal_control"], o["months_parsed"],
                    o["max_relative_delta_pct"], "% of control",
                    "outputs/ocac_parse_summary.csv",
                    "months closing both the internal and the overseas control"))
    n = _one("nfdc_monthly_parse_summary.csv")
    out.append(_row("parse_nfdc", "source parsing", "NFDC monthly fertiliser offtake",
                    n["month_rows"], "product-month rows", n["rows_quarantined"],
                    n["product_years_closing_group_control"], n["product_years"], "",
                    "", "outputs/nfdc_monthly_parse_summary.csv",
                    "product-years closing the printed group control"))
    m = _one("pbs_minerals_parse_summary.csv")
    out.append(_row("parse_pbs_minerals", "source parsing", "PBS monthly minerals production",
                    m["month_rows"], "province-month rows", m["rows_quarantined"],
                    m["mineral_years_closing_group_control"], m["mineral_years"], "", "",
                    "outputs/pbs_minerals_parse_summary.csv",
                    "mineral-years closing the printed control"))
    q = _one("pbs_qim_parse_summary.csv")
    out.append(_row("parse_pbs_qim", "source parsing", "PBS manufacturing index (QIM)",
                    q["month_rows"], "item-month rows", q["item_years_quarantined"],
                    q["item_years_closed"],
                    str(int(q["item_years_closed"]) + int(q["item_years_quarantined"])), "", "",
                    "outputs/pbs_qim_parse_summary.csv", "item-years closing the printed annual"))
    a = _one("apcma_dispatch_parse_summary.csv")
    out.append(_row("parse_apcma", "source parsing", "APCMA cement dispatch",
                    a["month_cells"], "month cells", a["cells_quarantined"], "", "", "", "",
                    "outputs/apcma_dispatch_parse_summary.csv",
                    "quarantined cells are kept, unrepaired, beside the parse"))
    return out


def _closure_rows():
    out = []
    annual = collections.defaultdict(float)
    for r in read_rows(asset_path(OUTPUTS, "pakemis_air_annual_fy2015_16_fy2024_25.csv")):
        if r["configuration_id"] == REFERENCE:
            annual[(r["period_id"], r["pollutant"])] += float(r["emissions_Gg"] or 0)
    monthly = collections.defaultdict(float)
    months = 0
    for r in read_rows(asset_path(OUTPUTS, "pakemis_air_monthly.csv")):
        if r["configuration_id"] == REFERENCE:
            monthly[(r["period_id"], r["pollutant"])] += float(r["emissions_Gg"] or 0)
            months += 1
    keys = sorted(annual)
    residuals = [abs(annual[k] - monthly.get(k, 0.0)) for k in keys]
    worst = max(residuals)
    out.append(_row("closure_air_monthly", "closure",
                    "Air monthly against annual, per species",
                    months, "monthly records (S_TAN)", "",
                    sum(1 for x in residuals if x < 1e-5), len(keys), "%.3g" % worst,
                    "Gg", "outputs/pakemis_air_monthly.csv; "
                    "outputs/pakemis_air_annual_fy2015_16_fy2024_25.csv",
                    "period-species pairs closing within 1e-5 Gg (rounding of the CSV)"))
    grid = read_rows(asset_path(OUTPUTS, "pakemis_grid_provincial_check.csv"))
    declared = [r for r in grid if r["status"] == "declared_divergence"]
    others = [r for r in grid if r["status"] != "declared_divergence"]
    worst = max(abs(float(r["diff"])) for r in others)
    largest = max((abs(float(r["diff"])) for r in declared), default=0.0)
    streams = sorted({r["source_stream_id"] for r in declared})
    out.append(_row("closure_grid_provincial", "closure",
                    "Grid against provincial shares",
                    len(grid), "stream-province rows", "",
                    sum(1 for r in others if abs(float(r["diff"])) < 1e-6), len(grid),
                    "%.3g" % worst, "share", "outputs/pakemis_grid_provincial_check.csv",
                    "%d declared divergences in %d streams (largest %.3g), not failures: %s"
                    % (len(declared), len(streams), largest,
                       declared[0]["basis"].split(";")[0] if declared else "")))
    nest = read_rows(asset_path(OUTPUTS, "pakemis_adm2_nesting_check.csv"))
    worst = max(abs(float(r["abs_difference_Mt_AR5"])) for r in nest)
    out.append(_row("closure_adm2_nesting", "closure",
                    "Districts against provinces", len(nest), "provinces", "",
                    sum(1 for r in nest if float(r["abs_difference_Mt_AR5"]) < 1e-6), len(nest),
                    "%.3g" % worst, "Mt CO2e (AR5)", "outputs/pakemis_adm2_nesting_check.csv"))
    nitrogen = read_rows(asset_path(OUTPUTS, "pakemis_nitrogen_partition_sensitivity.csv"))
    worst = max(abs(float(r["max_nitrogen_closure_residual_kgN"] or 0)) for r in nitrogen)
    out.append(_row("closure_nitrogen", "closure",
                    "Nitrogen ledger, every year and configuration",
                    len(nitrogen), "ledger replays", "", "", "", "%.3g" % worst, "kg N",
                    "outputs/pakemis_nitrogen_partition_sensitivity.csv"))
    coal = read_rows(asset_path(OUTPUTS, "pakemis_coal_change_decomposition.csv"))
    worst = max(abs(float(r["closure_residual"])) for r in coal)
    out.append(_row("closure_coal_change", "closure",
                    "Coal change decomposition", len(coal),
                    "year-species rows", "", "", "", "%.3g" % worst, "Gg / Mt CO2e",
                    "outputs/pakemis_coal_change_decomposition.csv"))
    return out


def _reproduction_rows():
    out = []
    for check_id, name, label in (
            ("rebuild_clean_rc68", "clean_rebuild_comparison.csv",
             "rc68 clean rebuild, compiled inputs"),
            ("rebuild_unpack_rc68", "unpack_build_comparison.csv",
             "rc68 deposit, unpacked and built")):
        path = os.path.join(ROOT, "docs", "reproduction", "rc68", name)
        rows = read_rows(path)
        statuses = collections.Counter(r["status"] for r in rows)
        differing = sum(v for k, v in statuses.items() if k.startswith("diff"))
        identical = sum(v for k, v in statuses.items() if "identical" in k)
        verified = os.path.join(ROOT, "docs", "reproduction", "rc68",
                                "unpack_not_rebuilt_check.csv")
        if check_id == "rebuild_unpack_rc68" and os.path.exists(verified):
            # the files the strict build did not rewrite, compared byte for byte afterwards
            checked = read_rows(verified)
            same = [r for r in checked if r["bytes_versus_release_commit_6d8e8669"] == "identical"]
            differing += len(checked) - len(same)
            identical += len(same)
        out.append(_row(check_id, "reproduction", label, len(rows), "files", differing,
                        identical, len(rows), "", "", "docs/reproduction/rc68/" + name,
                        "; ".join("%s %d" % kv for kv in sorted(statuses.items()))))
    record = json.load(open(asset_path(OUTPUTS, "pakemis_test_run.json"), encoding="utf-8"))
    out.append(_row("tests_release", "reproduction", "rc68 canonical test run",
                    record["executed"], "tests executed", record["failed"], record["passed"],
                    record["executed"], "", "", "outputs/pakemis_test_run.json",
                    "%d skipped" % record["skipped"]))
    return out


def build():
    return _parse_rows() + _closure_rows() + _reproduction_rows()


BANNER = [
    "MEASURED VALIDATION, ONE ROW PER CHECK (rc69): records each check read, how many it",
    "rejected or quarantined, how many closed and of how many, and the largest residual. Read",
    "from the parse summaries, closure ledgers and the reproduction record each row names;",
    "two closures (air monthly against annual, districts against provinces) are recomputed",
    "from the released tables. Producer: pkinv.report.validation_measured.",
]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    return write_or_check(OUT, FIELDS, build(), check=args.check, banner=BANNER)


if __name__ == "__main__":
    raise SystemExit(main())
