"""What every one of the 108 months is evidenced by, and where a month genuinely does not exist.

THE QUESTION THIS ANSWERS, in the words it was asked in: for each of the 108 months, per sector
and category, is the timing TE1, TE2, TE3, TE4 or genuinely missing, and which source supports
it. Everything needed has been in the release for several versions - the monthly product carries
a temporal class on every one of its rows, and the atomic annual table declares the sector-years
that have no months at all - but nothing assembled the two into that view, so the answer existed
and could not be read.

TWO FILES AT TWO GRAINS, AND THEY ARE NEVER MIXED.

  pakemis_monthly_coverage.csv          one row per (month, sector, category, class), with the
                                        mass under it. Additive within itself and only within
                                        itself.
  pakemis_monthly_coverage_summary.csv  EXACTLY 108 rows, one per month. This is the direct
                                        answer; the detail is what backs it.

Summing the two together would double the inventory, which is why they are separate files
rather than one file with a total row in it.

"MISSING" IS A STATE WITH A REASON, NOT A HOLE. Two sector-years are genuinely absent -
industry and transport in FY2015-16 - and the atom already says so with `estimate_status =
absent`, while pakemis_coverage_matrix.csv carries the notation key and the basis for the same
cells. Those are expanded to their twelve months each and carry the reason across, because a
reader meeting a blank cannot tell "nobody estimated this" from "the report lost it".

IT READS THE CLASSES, IT DOES NOT DECIDE THEM. `temporal_profiles` owns that judgement for the
whole release, and re-deriving it here would be a second vintage of the same answer - which is
the failure this repository has watched happen twice with declared tables.

WHAT A READER SHOULD TAKE FROM IT, and the report does not hide it: the strong classes are
concentrated in the last three fiscal years, because that is where OCAC's monthly panel
reaches. A coverage report whose headline averaged that away would be worse than none.

Usage:  python3 -m pkinv.report.monthly_coverage
Writes: outputs/pakemis_monthly_coverage.csv
        outputs/pakemis_monthly_coverage_summary.csv
"""

from pkinv.assets import asset_path
import collections
import csv
import os

from pkinv.core import monthly as core_monthly
from pkinv.paths import DATA, OUTPUTS
from pkinv.activity.store import read_rows

MONTHLY = asset_path(OUTPUTS, "pakemis_monthly_fy2015_16_fy2023_24.csv")
ATOM = asset_path(OUTPUTS, "pakemis_atomic_annual.csv")
MATRIX = asset_path(OUTPUTS, "pakemis_coverage_matrix.csv")
MONTHS = asset_path(DATA, "months.csv")

DETAIL_OUT = asset_path(OUTPUTS, "pakemis_monthly_coverage.csv")
SUMMARY_OUT = asset_path(OUTPUTS, "pakemis_monthly_coverage_summary.csv")

CLASSES = ("TE1", "TE2", "TE3", "TE4")
MISSING = "missing"

DETAIL_FIELDS = ("month", "period_id", "sector_id", "ipcc_code", "category",
                 "temporal_evidence_class", "timing_target", "co2e_Mt_AR5",
                 "evidence_class", "source_id", "state_basis")
SUMMARY_FIELDS = ("month", "period_id", "special_period_flag", "sectors_present",
                  "sectors_missing", "missing_sectors", "co2e_Mt_AR5",
                  "TE1_Mt", "TE2_Mt", "TE3_Mt", "TE4_Mt",
                  "observed_share_pct", "flat_share_pct")


def _rows(path):
    return read_rows(path)


def months():
    """The 108 month ids and their flags, from the registry that materialises core/monthly."""
    return [(r["month_id"], r["special_period_flag"]) for r in _rows(MONTHS)]


def absent_sector_periods():
    """{(sector_id, period_id): reason} - the sector-years with no months, and why.

    The atom declares WHICH; the coverage matrix declares WHY, in the notation-key vocabulary
    the annual product already publishes. Neither is retyped here.
    """
    absent = {(r["sector_id"], r["period_id"]) for r in _rows(ATOM)
              if r["estimate_status"] == "absent"}
    reasons = {}
    for row in _rows(MATRIX):
        key = (row["sector"], row["period_label"])
        if key in absent and row.get("state_basis"):
            reasons.setdefault(key, "%s: %s" % (row["state"], row["state_basis"]))
    return {key: reasons.get(key, "declared absent by the annual product") for key in absent}


def _evidence_by_component():
    """{component_id: evidence class} from the atom, so the two axes appear side by side."""
    out = {}
    for row in _rows(ATOM):
        if row["component_id"]:
            out.setdefault(row["component_id"], row["evidence_class"])
    return out


def detail():
    """One row per (month, sector, category, temporal class), plus the missing cells."""
    evidence = _evidence_by_component()
    grouped = collections.defaultdict(lambda: {"mass": 0.0, "targets": set(),
                                               "sources": set(), "evidence": set(),
                                               "ipcc": set()})
    for row in _rows(MONTHLY):
        key = (row["month"], row["period_id"], row["sector_id"], row["category"],
               row["temporal_evidence_class"])
        bucket = grouped[key]
        bucket["mass"] += float(row["co2e_Mt_AR5"] or 0.0)
        bucket["targets"].add(row["timing_target"])
        if row["source_id"]:
            bucket["sources"].add(row["source_id"])
        bucket["evidence"].add(evidence.get(row["component_id"], ""))
        bucket["ipcc"].add(row["ipcc_code"])

    out = []
    for (month, period, sector, category, cls), bucket in sorted(grouped.items()):
        out.append({
            "month": month, "period_id": period, "sector_id": sector,
            "ipcc_code": ";".join(sorted(c for c in bucket["ipcc"] if c)),
            "category": category, "temporal_evidence_class": cls,
            "timing_target": ";".join(sorted(t for t in bucket["targets"] if t)),
            "co2e_Mt_AR5": round(bucket["mass"], 8),
            # An empty evidence class is carried as the literal "unclassified" rather than a
            # blank, because a blank cell in a coverage report is exactly the ambiguity the
            # report exists to remove.
            "evidence_class": ";".join(sorted(e or "unclassified"
                                              for e in bucket["evidence"])),
            "source_id": ";".join(sorted(bucket["sources"])) or "",
            "state_basis": "",
        })

    for (sector, period), reason in sorted(absent_sector_periods().items()):
        for month in core_monthly.months_for(int(period[2:6])):
            out.append({
                "month": month, "period_id": period, "sector_id": sector,
                "ipcc_code": "", "category": "(sector not estimated)",
                "temporal_evidence_class": MISSING, "timing_target": "",
                "co2e_Mt_AR5": "", "evidence_class": "", "source_id": "",
                "state_basis": reason,
            })
    return sorted(out, key=lambda r: (r["month"], r["sector_id"], r["category"],
                                      r["temporal_evidence_class"]))


def summary(detail_rows=None):
    """Exactly 108 rows: what each month is evidenced by, and which sectors it lacks."""
    detail_rows = detail_rows if detail_rows is not None else detail()
    flags = dict(months())
    by_month = collections.defaultdict(lambda: collections.defaultdict(float))
    present = collections.defaultdict(set)
    missing = collections.defaultdict(set)
    period_of = {}
    for row in detail_rows:
        period_of[row["month"]] = row["period_id"]
        if row["temporal_evidence_class"] == MISSING:
            missing[row["month"]].add(row["sector_id"])
            continue
        present[row["month"]].add(row["sector_id"])
        by_month[row["month"]][row["temporal_evidence_class"]] += float(row["co2e_Mt_AR5"])

    out = []
    for month, flag in months():
        masses = by_month[month]
        total = sum(masses.values())
        observed = masses.get("TE1", 0.0) + masses.get("TE2", 0.0)
        out.append({
            "month": month, "period_id": period_of.get(month, ""),
            "special_period_flag": flag,
            "sectors_present": len(present[month]),
            "sectors_missing": len(missing[month]),
            "missing_sectors": ";".join(sorted(missing[month])),
            "co2e_Mt_AR5": round(total, 6),
            "TE1_Mt": round(masses.get("TE1", 0.0), 6),
            "TE2_Mt": round(masses.get("TE2", 0.0), 6),
            "TE3_Mt": round(masses.get("TE3", 0.0), 6),
            "TE4_Mt": round(masses.get("TE4", 0.0), 6),
            "observed_share_pct": round(100.0 * observed / total, 2) if total else "",
            "flat_share_pct": round(100.0 * masses.get("TE4", 0.0) / total, 2) if total else "",
        })
    return out


def _write(path, rows, fields, header_lines):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        for line in header_lines:
            handle.write("# %s\n" % line)
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    detail_rows = detail()
    summary_rows = summary(detail_rows)

    _write(DETAIL_OUT, detail_rows, DETAIL_FIELDS, [
        "WHAT EACH MONTH'S TIMING RESTS ON, one row per (month, sector, category, class).",
        "ADDITIVE WITHIN ITSELF ONLY. Do not sum this file together with the summary beside "
        "it; they are the same mass at two grains.",
        "temporal_evidence_class = missing means the SECTOR-YEAR is not estimated at all, and "
        "state_basis carries the annual product's own reason.",
        "A class here is READ from pakemis_temporal_profiles.csv, never re-decided.",
    ])
    _write(SUMMARY_OUT, summary_rows, SUMMARY_FIELDS, [
        "EXACTLY 108 ROWS, one per month of FY2015-16..FY2023-24.",
        "observed_share_pct is TE1+TE2 STRICTLY: timing carried by a monthly RECORD of the "
        "activity. It is a different and narrower question than the",
        "'observed' column of pakemis_temporal_decomposition.csv, which also counts TE3 - a "
        "process proxy such as degree days or a crop calendar - as",
        "carrying a stream's within-year variation. Both are published because both are "
        "true; they are not two vintages of one number, and the",
        "narrower one is here because a coverage report should not let a modelled shape "
        "stand in for an observed one.",
        "flat_share_pct is TE4, which is a CLAIM that a source is aseasonal and for most of "
        "this inventory is a claim made because no monthly statistic exists.",
        "sectors_missing counts sector-years with no months at all, named in missing_sectors.",
    ])

    total = sum(r["co2e_Mt_AR5"] for r in summary_rows)
    observed = sum(r["TE1_Mt"] + r["TE2_Mt"] for r in summary_rows)
    flat = sum(r["TE4_Mt"] for r in summary_rows)
    print("monthly coverage -> %s" % os.path.relpath(DETAIL_OUT, OUTPUTS))
    print("  %d detail rows, %d summary rows" % (len(detail_rows), len(summary_rows)))
    print("  %.1f Mt over 108 months; observed (TE1+TE2) %.1f%%, flat (TE4) %.1f%%"
          % (total, 100 * observed / total, 100 * flat / total))
    gapped = [r for r in summary_rows if r["sectors_missing"]]
    print("  %d months are missing a sector entirely: %s"
          % (len(gapped), ", ".join(sorted({r["missing_sectors"] for r in gapped})) or "none"))
    by_year = collections.defaultdict(lambda: [0.0, 0.0])
    for row in summary_rows:
        by_year[row["period_id"]][0] += row["TE1_Mt"] + row["TE2_Mt"]
        by_year[row["period_id"]][1] += row["co2e_Mt_AR5"]
    print("  observed share by fiscal year - the concentration a single headline would hide:")
    for period, (obs, tot) in sorted(by_year.items()):
        print("    %-10s %5.1f%%" % (period, 100 * obs / tot if tot else 0.0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
