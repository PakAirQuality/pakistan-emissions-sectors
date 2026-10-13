"""The monthly controls register: every stream-month with its edition stamps.

WHY. The monthly layer's inputs were auditable only by opening the OCAC panel and the
aviation edition record separately - and core/ocac_monthly.tonnes() DROPS the per-row
edition columns (source PDF, sha256, report kind), so nothing downstream could say
which publication a month came from. This register is the seed of the operational
monthly lane (docs/monthly_lane.md): one row per (stream, month), each carrying the
edition it was read from, its measurement basis, its lifecycle status, and an as_of
date - the record schema the future provisional lane extends.

ONE ROW PER (STREAM, MONTH), STRUCTURALLY. The cube's temporal join is last-write-wins
on extra rows for the same key (the rc10 exploration's join hazard), so the lane lives
in its own product and never adds rows to national_monthly_2024.csv.

VOCABULARIES, generalized from the aviation record rather than invented:
  measurement  direct | cumulative_differenced      (report_kind on the panel)
  status       final | provisional | corrected | superseded
               - every fiscal year the panel holds is CLOSED, so every row here is
                 "final"; the provisional lane activates with the first post-FY2024-25
                 edition, and this column is where its states will live
  revision_note  aviation's published vocabulary passes through verbatim
                 (direct monthly report / July-only / corrected ... / final revised
                 annual); panel streams carry the edition's coverage note if any

Usage:  python3 -m pkinv.report.monthly_controls [--check]
Writes: outputs/pakemis_monthly_controls.csv
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import csv
import io
import os
import sys

from pkinv.core import ocac_monthly
from pkinv.paths import OUTPUTS, ROOT

OUT = asset_path(OUTPUTS, "pakemis_monthly_controls.csv")
AVIATION = asset_path(OUTPUTS, "aviation_ocac_monthly.csv")

# the same six streams the temporal benchmark scores (eval/benchmark_temporal)
STREAMS = (
    ("transport_petrol", ocac_monthly.ROAD, ocac_monthly.PETROL),
    ("transport_diesel", ocac_monthly.ROAD, ocac_monthly.DIESEL),
    ("railways_diesel", ocac_monthly.RAILWAYS, ocac_monthly.DIESEL),
    ("industry_diesel", ocac_monthly.TOTAL_INDUSTRY, ocac_monthly.DIESEL),
    ("power_liquids", ocac_monthly.TOTAL_POWER, ("FO", "HSD")),
)
FY_STARTS = (2021, 2022, 2023, 2024)

FIELDS = ("stream", "sector_row", "products", "month", "tonnes", "t_class",
          "measurement", "status", "as_of", "source_file", "source_sha256",
          "revision_note")


def _as_of(source_file):
    """OCAC_YYYY_MM.pdf -> YYYY-MM: the edition's own cover month."""
    stem = os.path.splitext(os.path.basename(source_file))[0]
    parts = stem.replace("OCAC_", "").split("_")
    return "%s-%s" % (parts[0], parts[1])


def compute():
    rows = []
    for stream, sector_row, products in STREAMS:
        for fy in FY_STARTS:
            values, method = ocac_monthly.tonnes(sector_row, products, fy)
            stamps = ocac_monthly.editions(sector_row, products, fy)
            for key in sorted(values):
                stamp = stamps[key]
                rows.append({
                    "stream": stream, "sector_row": sector_row,
                    "products": "+".join(products),
                    "month": "%s-%s" % (key[:4], key[4:]),
                    "tonnes": round(values[key], 3), "t_class": method[key],
                    "measurement": ("direct" if stamp["report_kind"] == "monthly"
                                    else "cumulative_differenced"),
                    "status": "final",
                    "as_of": _as_of(stamp["source_file"]),
                    "source_file": stamp["source_file"],
                    "source_sha256": stamp["source_sha256"],
                    "revision_note": ""})
    # aviation: the edition record already carries the revision vocabulary; sum the
    # domestic customer categories per period, keep the stamps (identical per period)
    by_month = {}
    for r in _activity_rows(AVIATION, comments=False):
        if not r["customer_category"].startswith("Domestic Avi"):
            continue
        m = r["period_end"]
        if m in by_month:
            held = by_month[m]
            if (held["source_file"], held["source_sha256"]) != \
                    (r["source_file"], r["source_sha256"]):
                raise ValueError("aviation editions disagree within %s" % m)
            held["tonnes"] += float(r["monthly_t"])
        else:
            by_month[m] = {"tonnes": float(r["monthly_t"]),
                           "report_kind": r["report_kind"],
                           "source_file": r["source_file"],
                           "source_sha256": r["source_sha256"],
                           "revision_note": r["revision_note"]}
    for m in sorted(by_month):
        r = by_month[m]
        rows.append({
            "stream": "aviation_domestic_jp1", "sector_row": "(aviation record)",
            "products": "JP-1", "month": m,
            "tonnes": round(r["tonnes"], 3),
            "t_class": "T1" if r["report_kind"] == "monthly" else "T2",
            "measurement": ("direct" if r["report_kind"] == "monthly"
                            else "cumulative_differenced"),
            "status": "final", "as_of": _as_of(r["source_file"]),
            "source_file": r["source_file"],
            "source_sha256": r["source_sha256"],
            "revision_note": r["revision_note"]})
    return rows


def main(check=False):
    rows = compute()
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    text = out.getvalue()
    if check:
        if not os.path.exists(OUT) or open(OUT, encoding="utf-8").read() != text:
            print("pakemis_monthly_controls stale; rerun "
                  "python3 -m pkinv.report.monthly_controls")
            return 1
        print("monthly controls register is current.")
        return 0
    open(OUT, "w", encoding="utf-8").write(text)
    streams = sorted({r["stream"] for r in rows})
    print("monthly controls register: %d rows, %d streams x %d months -> %s"
          % (len(rows), len(streams), len(rows) // len(streams),
             os.path.relpath(OUT, ROOT)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(check="--check" in sys.argv))
