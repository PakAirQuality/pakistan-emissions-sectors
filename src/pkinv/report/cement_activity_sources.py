"""Cement activity by fiscal year, per source, and what the two sources say where they meet.

WHY A PRODUCT AND NOT A FOOTNOTE. The nine-year cement series stands on two publications: the
State Bank's FY2023-24 Statistical Supplement for FY2019-20 onward, and the Pakistan
Statistical Year Book 2020 for the four years before it. Every join between two sources is a
place a series can break silently, and the reviewer's rule for them is explicit - quantify the
transition or mark the portion not comparable. This is the quantification, as a table a reader
can check rather than a sentence they have to believe.

WHAT IT SHOWS. One row per fiscal year, the value each source publishes for it, and the
difference where both do. They overlap in exactly one year, FY2019-20, and disagree there by
1 kt in 39,122 - one part in forty thousand, which is rounding rather than a basis difference.
That is what licenses carrying the earlier years on the yearbook without declaring a break.

WHAT IT DOES NOT SHOW. A single overlapping year bounds the join; it does not establish that
the two series would agree across the window. If a later edition adds overlap, this table is
where the extra years belong, and a disagreement appearing in them is a finding, not a nuisance.

Usage:  python3 -m pkinv.report.cement_activity_sources
Writes: outputs/pakemis_cement_activity_sources.csv
"""
from __future__ import annotations

from pkinv.assets import asset_path

import csv
import os

from pkinv.core import period
from pkinv.paths import DATA, OUTPUTS
from pkinv.activity.store import read_rows
from pkinv.core.io import write_table

OUT = asset_path(OUTPUTS, "pakemis_cement_activity_sources.csv")
ACTIVITY = asset_path(DATA, "activity", "ippu", "national_activity.csv")

FIELDS = ("period_id", "period_end_year", "source_id", "cement_kt", "overlap_with",
          "overlap_kt", "difference_kt", "difference_pct", "note")

# Publication order, oldest edition first. Only used to name the counterpart in an overlap.
SOURCES = ("psyb_2020_table_13_2", "sbp_stat_supplement_fy2024", "pbs_qim_fy2023_24")


def _activity():
    return [r for r in read_rows(ACTIVITY, comments=False) if r["product"] == "Cement"]


def build():
    by_year = {}
    for row in _activity():
        year = int(row["period_end_year"])
        by_year.setdefault(year, {})[row["source_id"]] = float(row["quantity"])

    rows = []
    for year in sorted(by_year):
        start, end = period.fiscal(year - 1)
        label = period.label(start, end)
        published = by_year[year]
        for source in sorted(published, key=lambda s: SOURCES.index(s)
                             if s in SOURCES else len(SOURCES)):
            others = {s: v for s, v in published.items() if s != source}
            counterpart, counter_value = ("", "")
            difference, difference_pct, note = "", "", ""
            if others:
                counterpart, counter_value = sorted(others.items())[0]
                difference = round(published[source] - counter_value, 3)
                difference_pct = round(100.0 * difference / counter_value, 4)
                note = ("both publications carry this year; the difference is what bounds "
                        "the join between them")
            elif source == "psyb_2020_table_13_2":
                note = "carried on the yearbook alone; the join is bounded at FY2019-20"
            else:
                note = "carried on this source alone"
            rows.append({
                "period_id": label, "period_end_year": year, "source_id": source,
                "cement_kt": published[source], "overlap_with": counterpart,
                "overlap_kt": counter_value, "difference_kt": difference,
                "difference_pct": difference_pct, "note": note,
            })
    return rows


def overlaps(rows=None):
    rows = rows if rows is not None else build()
    return [r for r in rows if r["overlap_with"]]


def main():
    rows = build()
    os.makedirs(OUTPUTS, exist_ok=True)
    write_table(OUT, FIELDS, rows)
    print("cement activity sources -> %s" % OUT)
    print("  %d rows over %d fiscal years, %d sources"
          % (len(rows), len({r["period_id"] for r in rows}),
             len({r["source_id"] for r in rows})))
    for row in overlaps(rows):
        print("  overlap %s: %s %.0f vs %s %.0f -> %+.0f kt (%+.4f%%)"
              % (row["period_id"], row["source_id"], row["cement_kt"],
                 row["overlap_with"], row["overlap_kt"], row["difference_kt"],
                 row["difference_pct"]))
    if not overlaps(rows):
        print("  NO OVERLAPPING YEAR: the join between sources is unbounded, which is a "
              "declared break rather than a bridge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
