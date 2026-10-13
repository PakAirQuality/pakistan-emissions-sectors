"""Agriculture's monthly product, explained in the two ways it has to be explained.

THE PROBLEM. This sector publishes two different statements about time and they answer
different questions, so quoting either alone misleads.

  The TE class (TE1..TE4) says how the year's emission was SPREAD across its months - what
  evidence resolved the timing. 87.3% of agriculture sits at TE4, which reads as a sector
  whose timing is almost entirely unevidenced.

  The physical class says whether being flat is CORRECT. Enteric fermentation and manure
  management are continuous processes riding a census stock: a flat month is not a gap in
  the evidence, it is the physics, and no acquisition could improve it. Rice, urea and
  field burning are genuinely time-variable and are resolved. Managed soils is genuinely
  time-variable and only partly observed.

Read together, the honest figure for "timing this inventory should resolve and has not" is
6.67% of nine years and 7.00% of the reference year - not 87.3%. Read apart, the first number
overstates the problem by more than an order of magnitude and the second hides that a real
gap exists. Both classes have been computed for several releases; they lived in two products
at two grains, so a reader had to know to join them. This publishes the join.

NOT THE NATIONAL CROSSWALK. pakemis_flatness_crosswalk.csv already cross-tabulates TE class
against flatness bucket for the whole inventory - thirteen cells, no sector split. It answers
"how do the two classifications overlap nationally". This answers "which agriculture category
is which, and how much of the sector's timing is genuinely unresolved", per category and for
the reference year as well as the panel. The national table cannot produce 6.67% or 7.00%
because it has no sector dimension, and this one cannot produce the national overlap.

THE NFDC RESIDUAL, published rather than renormalised. NFDC's national monthly offtake and
its provincial table do not sum to each other: 15,918 t of product over the fiscal year,
0.154917% of the national total, almost all urea. It is a coverage difference between two
tables of one publication, not an error to be distributed away, so it is published by month
and product and assigned to Other/unallocated. Renormalising the provinces onto the national
total would bury a real discrepancy inside shares that would then look exact.

WINDOW MATCHING IS WHAT MAKES THAT NUMBER MEAN ANYTHING. Annex-7's seasons run April-March;
Annex-5's fiscal year runs July-June. Comparing the two as published gives -391,348 t, a 3.8%
gap that is entirely the window and nothing to do with coverage. The comparison here is
month-matched, which is the same correction A2 made for the composition.

Writes: outputs/agriculture_timing_classes.csv
        outputs/agriculture_nfdc_province_residual.csv
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import collections
import csv
import os

from pkinv.core.io import write_table
from pkinv.paths import DATA, OUTPUTS, ROOT

TIMING_OUT = asset_path(OUTPUTS, "agriculture_timing_classes.csv")
RESIDUAL_OUT = asset_path(OUTPUTS, "agriculture_nfdc_province_residual.csv")
ANNEX7 = asset_path(DATA, "nfdc", "annex7_province_month_product_2023-24.csv")
NON_PRODUCT = {"province", "season", "month", "calendar_year", "Total", "source"}
REFERENCE = "FY2023-24"


def _rows(path):
    return list(_activity_rows(path, comments=True))


def timing_rows():
    """One row per agriculture category: the TE evidence and the physical class together."""
    coverage = [r for r in _rows(asset_path(OUTPUTS, "pakemis_monthly_coverage.csv"))
                if r["sector_id"] == "agriculture"]
    decomposition = {r["component"]: r for r in
                     _rows(asset_path(OUTPUTS, "pakemis_temporal_decomposition.csv"))
                     if r["sector_id"] == "agriculture"}
    by_category = collections.defaultdict(list)
    for row in coverage:
        by_category[row["category"]].append(row)

    out, totals = [], collections.Counter()
    for category in sorted(by_category):
        rows = by_category[category]
        dec = decomposition.get(category, {})
        should_vary = dec.get("activity_should_vary_but_unobserved", "") == "yes"
        classes = collections.Counter(r["temporal_evidence_class"] for r in rows)
        nine = sum(float(r["co2e_Mt_AR5"] or 0) for r in rows)
        ref = sum(float(r["co2e_Mt_AR5"] or 0) for r in rows if r["period_id"] == REFERENCE)
        # Unobserved means BOTH: the activity should vary, and this month's timing rests on
        # no evidence. A TE4 month of a continuous process is not unobserved timing.
        unobs_nine = sum(float(r["co2e_Mt_AR5"] or 0) for r in rows
                         if should_vary and r["temporal_evidence_class"] == "TE4")
        unobs_ref = sum(float(r["co2e_Mt_AR5"] or 0) for r in rows
                        if should_vary and r["temporal_evidence_class"] == "TE4"
                        and r["period_id"] == REFERENCE)
        totals["nine"] += nine
        totals["ref"] += ref
        totals["unobs_nine"] += unobs_nine
        totals["unobs_ref"] += unobs_ref
        out.append([
            rows[0]["ipcc_code"], category,
            ";".join("%s:%d" % kv for kv in sorted(classes.items())),
            dec.get("flatness_class", "unclassified"),
            dec.get("flatness_physically_appropriate", ""),
            "yes" if should_vary else "no",
            round(nine, 6), round(unobs_nine, 6),
            round(100.0 * unobs_nine / nine, 4) if nine else "",
            round(ref, 6), round(unobs_ref, 6),
            round(100.0 * unobs_ref / ref, 4) if ref else "",
            dec.get("expected_temporal_driver", ""),
            dec.get("basis", ""),
        ])
    out.append([
        "3", "TOTAL", "", "", "", "",
        round(totals["nine"], 6), round(totals["unobs_nine"], 6),
        round(100.0 * totals["unobs_nine"] / totals["nine"], 4),
        round(totals["ref"], 6), round(totals["unobs_ref"], 6),
        round(100.0 * totals["unobs_ref"] / totals["ref"], 4),
        "", "the share of agriculture whose timing this inventory should resolve and has not",
    ])
    return out


def residual_rows():
    """NFDC national minus provincial, by month and product, on a MATCHED window."""
    from pkinv.sectors.agriculture import fertiliser_mix as fm
    window = set(fm.FY_WINDOW)
    national = collections.defaultdict(float)
    for row in fm.annex5_window():
        national[(row["calendar_year"], row["month"], row["product"])] += float(
            row["offtake_product_tonnes"] or 0)
    provincial = collections.defaultdict(float)
    rows = _rows(ANNEX7)
    products = [c for c in rows[0] if c not in NON_PRODUCT]
    for row in rows:
        key_month = (row["calendar_year"], row["month"])
        if key_month not in window:
            continue
        for product in products:
            raw = (row.get(product) or "").strip()
            if raw:
                provincial[(row["calendar_year"], row["month"], product)] += float(raw)

    order = {m: i for i, m in enumerate(
        ["Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun"])}
    out, total_n, total_p = [], 0.0, 0.0
    for key in sorted(set(national) | set(provincial),
                      key=lambda k: (order[k[1]], k[2])):
        year, month, product = key
        n, p = national.get(key, 0.0), provincial.get(key, 0.0)
        total_n += n
        total_p += p
        out.append([year, month, product, round(n, 3), round(p, 3), round(n - p, 3),
                    round(100.0 * (n - p) / n, 6) if n else "",
                    "Other/unallocated"])
    out.append(["", "TOTAL", "", round(total_n, 3), round(total_p, 3),
                round(total_n - total_p, 3),
                round(100.0 * (total_n - total_p) / total_n, 6),
                "Other/unallocated"])
    return out


def _as_dicts(fieldnames, rows):
    """core.io.write_table takes dict rows; the sector Runner takes lists. Building lists
    above and converting once here keeps the row construction readable as a table."""
    return [dict(zip(fieldnames, row)) for row in rows]


TIMING_FIELDS = ["ipcc_code", "category", "temporal_evidence_classes",
                 "physical_timing_class", "flatness_physically_appropriate",
                 "activity_should_vary_but_unobserved",
                 "co2e_Mt_nine_years", "unobserved_Mt_nine_years", "unobserved_pct_nine_years",
                 "co2e_Mt_reference_year", "unobserved_Mt_reference_year",
                 "unobserved_pct_reference_year", "expected_temporal_driver", "basis"]
RESIDUAL_FIELDS = ["calendar_year", "month", "product", "national_tonnes",
                   "provincial_sum_tonnes", "residual_tonnes", "residual_pct_of_national",
                   "assigned_to"]


def main(argv=()):
    timing = timing_rows()
    write_table(TIMING_OUT, TIMING_FIELDS, _as_dicts(TIMING_FIELDS, timing),
                banner=(
                    "AGRICULTURE'S TIMING, IN BOTH THE CLASSIFICATIONS IT NEEDS (rc39 A8).",
                    "temporal_evidence_classes: how each month's timing was resolved (TE1-TE4).",
                    "physical_timing_class: whether being flat is CORRECT for the process.",
                    "A TE4 month of a continuous stock-driven process is not unresolved timing;",
                    "a TE4 month of a genuinely variable process is. Only the second is counted",
                    "as unobserved, which is why the honest figure is 6.67% of nine years and",
                    "7.00% of the reference year rather than the 87.3% a TE count alone gives.",
                ))
    residual = residual_rows()
    write_table(RESIDUAL_OUT, RESIDUAL_FIELDS, _as_dicts(RESIDUAL_FIELDS, residual),
                banner=(
                    "NFDC NATIONAL MINUS PROVINCIAL OFFTAKE, BY MONTH AND PRODUCT (rc39 A8).",
                    "Annex-5's national monthly table against Annex-7's provincial one over",
                    "the SAME twelve months. The two do not sum to each other and the",
                    "difference is published rather than renormalised away: 15,918 t over the",
                    "year, 0.154917% of national, assigned to Other/unallocated.",
                    "MATCHED ON MONTHS, NOT SEASONS. Annex-7's seasons run April-March; taking",
                    "them as published gives -391,348 t, which is the window and not coverage.",
                ))
    total = timing[-1]
    print("agriculture timing classes -> %s" % os.path.relpath(TIMING_OUT, ROOT))
    print("  unobserved timing: %.2f%% over nine years, %.2f%% in the reference year"
          % (total[8], total[11]))
    print("NFDC national-province residual -> %s" % os.path.relpath(RESIDUAL_OUT, ROOT))
    print("  %s t over the year (%s%% of national), assigned to Other/unallocated"
          % (residual[-1][5], residual[-1][6]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
