"""Benchmark task: monthly-shape hindcasts on the OCAC panel, on the frozen origins.

WHY. The monthly layer distributes each annual control over twelve months using the
OCAC shape, and T4's implicit claim is that this beats assuming nothing. This module
makes that claim scoreable: at each frozen origin (data/benchmark_splits/
temporal_origins.csv) it predicts the test fiscal year's 12-month shape from data
available at its start - the FLAT baseline (1/12 each: the assume-nothing shape) and
the LAST-YEAR-SHAPE baseline (the previous fiscal year's normalized shape, which is
what the monthly layer effectively asserts transfers) - and scores both against the
year that actually happened. The 2022-07 and 2024-07 measurement-regime changes
(direct monthly editions vs cumulative-differenced) are declared per origin by the
split itself; a regime change between train and test years is part of what the
error measures.

Aviation is the one stream where an independent publisher can arbitrate: the same
baselines are additionally scored against the OECD and Climate TRACE monthly
series, and the OCAC JP-1 shape itself is scored against each comparator's observed
year (cross-publisher agreement, labelled as such).

Metric: WAPE on monthly shares (shares sum to 1, so this is the L1 distance between
shapes) plus a peak-month hit; flat has no peak, so that cell is blank.

Usage:  python3 -m pkinv.eval.benchmark_temporal [--check]
Writes: outputs/benchmark_temporal_hindcast.csv
"""

from pkinv.assets import asset_path
import csv
import io
import os
import sys

from pkinv.core import ocac_monthly
from pkinv.paths import ROOT
from pkinv.core.io import read_rows

ORIGINS = asset_path(ROOT, "data", "benchmark_splits", "temporal_origins.csv")
OUT = asset_path(ROOT, "outputs", "benchmark_temporal_hindcast.csv")

# the six OCAC-anchored controls the annual engine actually uses; aviation's
# anchor is NOT a panel sector_row - the panel's "Domestic Bunkers" is marine
# HSD - it is the differenced domestic JP-1 in outputs/aviation_ocac_monthly.csv
STREAMS = (
    ("transport_petrol", ocac_monthly.ROAD, ocac_monthly.PETROL),
    ("transport_diesel", ocac_monthly.ROAD, ocac_monthly.DIESEL),
    ("railways_diesel", ocac_monthly.RAILWAYS, ocac_monthly.DIESEL),
    ("industry_diesel", ocac_monthly.TOTAL_INDUSTRY, ocac_monthly.DIESEL),
    ("power_liquids", ocac_monthly.TOTAL_POWER, ("FO", "HSD")),
    ("aviation_domestic_jp1", None, ocac_monthly.JET),
)
AVIATION = asset_path(ROOT, "outputs", "aviation_ocac_monthly.csv")

OECD = asset_path(ROOT, "outputs", "aviation_oecd_monthly.csv")
TRACE = asset_path(ROOT, "outputs",
                     "aviation_climatetrace_national_monthly.csv")


def _origins():
    return read_rows(ORIGINS, comments=False)


def _shape(sector_row, products, fy_start):
    """The fiscal year's 12 monthly shares, in July-June order."""
    if sector_row is None:
        return _aviation_shape(fy_start)
    values, _ = ocac_monthly.tonnes(sector_row, products, fy_start)
    months = [m.replace("-", "") for m in ocac_monthly._panel_months(fy_start)]
    total = sum(values[m] for m in months)
    return [values[m] / total for m in months], total


def _aviation_shape(fy_start):
    """Domestic JP-1 from the aviation edition record (already differenced)."""
    months = ocac_monthly._panel_months(fy_start)
    values = {}
    with open(AVIATION, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if (r["customer_category"].startswith("Domestic Avi")
                    and r["period_end"] in months):
                values[r["period_end"]] = (values.get(r["period_end"], 0.0)
                                           + float(r["monthly_t"]))
    if len(values) < 12:
        raise KeyError("aviation edition record is missing months of FY%d"
                       % fy_start)
    total = sum(values.values())
    return [values[m] / total for m in months], total


def _wape(pred, actual):
    return round(sum(abs(p - a) for p, a in zip(pred, actual)), 4)


def _peak_hit(pred, actual):
    return "yes" if pred.index(max(pred)) == actual.index(max(actual)) else "no"


def _comparator_shape(path, value_of, fy_start):
    """A comparator's July-June shape for one fiscal year, or None if incomplete."""
    months = ocac_monthly._panel_months(fy_start)
    values = {}
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            v = value_of(r)
            if v is not None and r["month"] in months:
                values[r["month"]] = values.get(r["month"], 0.0) + v
    if len(values) < 12:
        return None
    total = sum(values.values())
    return [values[m] / total for m in months]


COMPARATORS = (
    ("oecd_territory_domestic", OECD,
     lambda r: float(r["territory_domestic_co2_t"])),
    ("climatetrace_domestic", TRACE,
     lambda r: float(r["co2_t"]) if r["scope"] == "domestic" else None),
)


def compute():
    rows = []
    for origin in _origins():
        train_fy, test_fy = (int(origin["train_fy_start"]),
                             int(origin["test_fy_start"]))
        base = {"origin_id": origin["origin_id"],
                "train_fy_start": train_fy, "test_fy_start": test_fy,
                "train_regime": origin["train_regime"],
                "test_regime": origin["test_regime"],
                "regime_change": origin["regime_change"]}
        for stream_id, sector_row, products in STREAMS:
            train, _ = _shape(sector_row, products, train_fy)
            actual, total = _shape(sector_row, products, test_fy)
            for candidate, pred in (("flat", [1.0 / 12] * 12),
                                    ("last_year_shape", train)):
                rows.append(dict(base, task_id="temporal_ocac_hindcast",
                                 stream=stream_id, scored_against="ocac_panel",
                                 candidate=candidate,
                                 wape_monthly_shares=_wape(pred, actual),
                                 peak_month_hit=("" if candidate == "flat"
                                                 else _peak_hit(pred, actual)),
                                 test_year_tonnes=round(total, 1),
                                 status="scored", note=""))
        # aviation vs the independent publishers
        ocac_test, _ = _aviation_shape(test_fy)
        for comp_id, path, value_of in COMPARATORS:
            comp_train = _comparator_shape(path, value_of, train_fy)
            comp_actual = _comparator_shape(path, value_of, test_fy)
            if comp_actual is None:
                rows.append(dict(base, task_id="temporal_aviation_independent",
                                 stream="aviation_domestic_jp1",
                                 scored_against=comp_id, candidate="",
                                 wape_monthly_shares="", peak_month_hit="",
                                 test_year_tonnes="", status="NO_RECORD",
                                 note="comparator does not cover all twelve "
                                      "months of the test fiscal year"))
                continue
            candidates = [("flat", [1.0 / 12] * 12),
                          ("ocac_shape", ocac_test)]
            if comp_train is not None:
                candidates.insert(1, ("last_year_shape", comp_train))
            for candidate, pred in candidates:
                note = ("cross-publisher agreement: the OCAC JP-1 shape of the "
                        "SAME test year, not a forecast" if candidate ==
                        "ocac_shape" else "")
                rows.append(dict(base, task_id="temporal_aviation_independent",
                                 stream="aviation_domestic_jp1",
                                 scored_against=comp_id, candidate=candidate,
                                 wape_monthly_shares=_wape(pred, comp_actual),
                                 peak_month_hit=("" if candidate == "flat"
                                                 else _peak_hit(pred,
                                                                comp_actual)),
                                 test_year_tonnes="", status="scored",
                                 note=note))
    rows.append({"origin_id": "", "train_fy_start": "", "test_fy_start": "",
                 "train_regime": "", "test_regime": "", "regime_change": "",
                 "task_id": "temporal_ocac_hindcast", "stream": "",
                 "scored_against": "", "candidate": "",
                 "wape_monthly_shares": "", "peak_month_hit": "",
                 "test_year_tonnes": "", "status": "NO_RECORD",
                 "note": "monthly-anchored streams outside the OCAC panel (gas "
                         "via SNGPL/SSGC, electricity via NEPRA) hold a single "
                         "reporting year, so no origin has both a train and a "
                         "test year; excluded by declaration, not silently"})
    order = ["task_id", "origin_id", "stream", "scored_against", "candidate",
             "train_fy_start", "test_fy_start", "train_regime", "test_regime",
             "regime_change", "wape_monthly_shares", "peak_month_hit",
             "test_year_tonnes", "status", "note"]
    return [{k: r.get(k, "") for k in order} for r in rows], order


def main(check=False):
    rows, order = compute()
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=order, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    text = out.getvalue()
    if check:
        if not os.path.exists(OUT) or open(OUT, encoding="utf-8").read() != text:
            print("benchmark_temporal_hindcast stale; rerun "
                  "python3 -m pkinv.eval.benchmark_temporal")
            return 1
        print("benchmark temporal hindcast is current.")
        return 0
    open(OUT, "w", encoding="utf-8").write(text)
    scored = [r for r in rows if r["status"] == "scored"]
    for origin in sorted({r["origin_id"] for r in scored if r["origin_id"]}):
        flat = [r for r in scored if r["origin_id"] == origin
                and r["candidate"] == "flat"
                and r["scored_against"] == "ocac_panel"]
        lys = [r for r in scored if r["origin_id"] == origin
               and r["candidate"] == "last_year_shape"
               and r["scored_against"] == "ocac_panel"]
        print("  %s: flat wape %s | last-year-shape wape %s (6 streams)"
              % (origin,
                 round(sum(r["wape_monthly_shares"] for r in flat) / len(flat), 3),
                 round(sum(r["wape_monthly_shares"] for r in lys) / len(lys), 3)))
    print("wrote %d rows (%d scored) -> %s"
          % (len(rows), len(scored), os.path.relpath(OUT, ROOT)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(check="--check" in sys.argv))
