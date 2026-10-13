"""WHAT MOVED BETWEEN EDITIONS, AND WHETHER IT WAS A REVISION OR A REALLOCATION (rc53 Wave A1).

data/activity/industry/coal_by_sector_vintages.csv keeps every published print of HDIP's
coal-by-sector allocation. This builder pairs consecutive prints of the SAME reference period and
asks one question of each pair:

    did the total move, or did the users' shares move inside an unchanged total?

The second is a REALLOCATION. It is not a physical change in consumption and cannot be read as one.
Two are already visible in the held record:

  July-March FY2023-24   brick 2,572.26 -> 1,072.30 kt, cement/others 2,800 -> 4,300, total 17,279
                         unchanged (Economic Survey 2023-24 T14.11 -> Economic Survey 2024-25 T14.10)
  full-year FY2024-25    brick 3,483 -> 3,616, cement 5,155 -> 5,022, total 25,726.5 unchanged
                         (Statistical Supplement 2024-25 -> Economic Survey 2025-26 annex)

THE TRAP THIS PRODUCT EXISTS TO PREVENT. Restoring an earlier brick print while keeping the later
cement print counts the moved tonnage twice: brick + cement/others is invariant across a
reallocation (5,372.3 kt in the July-March FY2024 pair, 8,638 kt in the FY2024-25 pair). Reversing a
reallocation therefore changes WHICH SUBSECTOR burns the coal, never how much industrial coal was
burned - the combined industrial decline survives it. The pair rows carry that invariance as a
column so the arithmetic is checkable, not asserted.

A pair is only ever formed between prints of the SAME reference_fiscal_year AND the same
period_coverage: a nine-month July-March figure is never differenced against a full year.

Reads:  data/activity/industry/coal_by_sector_vintages.csv
Writes: outputs/pakemis_coal_vintage_ledger.csv
Nothing here enters any total; the booking policy is data/coal_booking_policy.csv.
"""
import csv
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from pkinv.assets import asset_path

from pkinv.paths import DATA, OUTPUTS, ROOT  # noqa: E402

SRC = asset_path(DATA, "activity", "industry", "coal_by_sector_vintages.csv")
OUT = asset_path(OUTPUTS, "pakemis_coal_vintage_ledger.csv")
FIELDS = ("reference_fiscal_year", "period_coverage", "months_covered", "sector_mapped",
          "earlier_publication", "earlier_edition_year", "earlier_table", "earlier_page",
          "earlier_label_printed", "earlier_flag", "earlier_kt",
          "later_publication", "later_edition_year", "later_table", "later_page",
          "later_label_printed", "later_flag", "later_kt",
          "delta_kt", "pct_change", "pair_total_delta_kt", "industrial_pair_kt_earlier",
          "industrial_pair_kt_later", "industrial_pair_invariant", "revision_kind", "note")
SECTORS = ("power", "brick_kilns", "cement_other", "household", "pak_steel", "other_govt", "total")
INDUSTRIAL_PAIR = ("brick_kilns", "cement_other")
TOTAL_TOL = 1.5          # kt: the later editions print integers, so an unchanged total can wobble
MOVE_TOL = 1.0           # kt: below this a sector "did not move"


def rows(path):
    from pkinv.activity.store import read_rows as canonical_rows
    return canonical_rows(path, comments=True)


def _val(r):
    return None if r["value"] == "" else float(r["value"])


def _order_key(r):
    """Prints are ordered by publication date: edition year, then the annex before the narrative
    (the annex reprints the settled series; the narrative carries the newest nine months)."""
    return (int(r["edition_year"]), 0 if "14.1 sec.4" in r["table_id"] else 1, r["table_id"])


def build():
    src = rows(SRC)
    prints = {}
    for r in src:
        key = (r["reference_fiscal_year"], r["period_coverage"])
        prints.setdefault(key, {}).setdefault(r["sector_mapped"], []).append(r)
    out = []
    for (fy, cov), by_sector in sorted(prints.items()):
        # the publication sequence for this reference period, from any sector that carries it
        seq = []
        for sector_rows in by_sector.values():
            for r in sector_rows:
                sig = (_order_key(r), r["publication"], r["table_id"], r["page"], r["edition_year"])
                if sig not in seq:
                    seq.append(sig)
        seq.sort()
        if len(seq) < 2:
            continue
        for a, b in zip(seq, seq[1:]):
            pair_vals = {}
            for sector in SECTORS:
                ra = next((r for r in by_sector.get(sector, []) if _order_key(r) == a[0] and r["table_id"] == a[2]), None)
                rb = next((r for r in by_sector.get(sector, []) if _order_key(r) == b[0] and r["table_id"] == b[2]), None)
                if ra is None or rb is None:
                    continue
                pair_vals[sector] = (ra, rb, _val(ra), _val(rb))
            if not pair_vals:
                continue
            tot = pair_vals.get("total")
            total_delta = None if (tot is None or tot[2] is None or tot[3] is None) else tot[3] - tot[2]
            ind_a = sum(pair_vals[s][2] or 0.0 for s in INDUSTRIAL_PAIR if s in pair_vals) if any(s in pair_vals for s in INDUSTRIAL_PAIR) else None
            ind_b = sum(pair_vals[s][3] or 0.0 for s in INDUSTRIAL_PAIR if s in pair_vals) if any(s in pair_vals for s in INDUSTRIAL_PAIR) else None
            moved = [s for s in SECTORS if s != "total" and s in pair_vals
                     and pair_vals[s][2] is not None and pair_vals[s][3] is not None
                     and abs(pair_vals[s][3] - pair_vals[s][2]) >= MOVE_TOL]
            reallocation = (total_delta is not None and abs(total_delta) < TOTAL_TOL and len(moved) >= 2)
            # A COLUMN THE LATER EDITION DOES NOT PRINT. The Compendium/PEY carry Pak Steel
            # (imported coal/coke as coke) and Domestic as their own columns; the Finance Division
            # Supplement prints neither and its Cement column is larger by exactly the dropped
            # amount. That is a classification change, not a revision of consumption - and it is why
            # the Supplement's "Cement" is the PEY's "Cement/Other Industry" plus Pak Steel.
            folded = None
            if total_delta is not None and abs(total_delta) < TOTAL_TOL and moved == ["cement_other"]:
                gain = pair_vals["cement_other"][3] - pair_vals["cement_other"][2]
                for dropped in ("pak_steel", "household", "other_govt"):
                    d = pair_vals.get(dropped)
                    if d and d[2] is not None and d[3] is None and abs(d[2] - gain) < TOTAL_TOL:
                        folded = (dropped, d[2])
                        break
                if folded is None:
                    # the dropped column may be absent from the later print entirely (no row)
                    src_only = {r["sector_mapped"]: _val(r) for sector_rows in by_sector.values()
                                for r in sector_rows if _order_key(r) == a[0] and r["table_id"] == a[2]}
                    for dropped in ("pak_steel", "household", "other_govt"):
                        v = src_only.get(dropped)
                        if v is not None and dropped not in pair_vals and abs(v - gain) < TOTAL_TOL:
                            folded = (dropped, v)
                            break
            for sector, (ra, rb, va, vb) in sorted(pair_vals.items()):
                delta = None if (va is None or vb is None) else vb - va
                if delta is None:
                    kind = "not_printed_in_one_edition"
                elif abs(delta) < MOVE_TOL:
                    kind = "unchanged"
                elif folded and sector == "cement_other":
                    kind = "column_folded_into_cement"
                elif reallocation:
                    kind = "reallocation_within_total"
                elif ra["provisional_flag"] == "P" and rb["provisional_flag"] != "P":
                    kind = "provisional_to_final"
                else:
                    kind = "level_revision"
                note = ""
                if ra["sector_label_printed"] != rb["sector_label_printed"]:
                    note = "printed label changed: '%s' -> '%s' (one HDIP column)" % (
                        ra["sector_label_printed"], rb["sector_label_printed"])
                if folded and sector == "cement_other":
                    note = (note + "; " if note else "") + (
                        "the later edition drops the %s column (%.3f kt) and its Cement column is "
                        "larger by exactly that amount: a classification change, not a revision"
                        % (folded[0], folded[1]))
                if reallocation and sector in INDUSTRIAL_PAIR:
                    note = (note + "; " if note else "") + (
                        "brick + cement/others is invariant across this pair - reversing the move "
                        "changes which subsector burns the coal, not how much")
                out.append({
                    "reference_fiscal_year": fy, "period_coverage": cov, "months_covered": ra["months_covered"],
                    "sector_mapped": sector,
                    "earlier_publication": ra["publication"], "earlier_edition_year": ra["edition_year"],
                    "earlier_table": ra["table_id"], "earlier_page": ra["page"],
                    "earlier_label_printed": ra["sector_label_printed"], "earlier_flag": ra["provisional_flag"],
                    "earlier_kt": ra["value"],
                    "later_publication": rb["publication"], "later_edition_year": rb["edition_year"],
                    "later_table": rb["table_id"], "later_page": rb["page"],
                    "later_label_printed": rb["sector_label_printed"], "later_flag": rb["provisional_flag"],
                    "later_kt": rb["value"],
                    "delta_kt": "" if delta is None else "%.2f" % delta,
                    "pct_change": "" if (delta is None or not va) else "%.1f" % (100.0 * delta / va),
                    "pair_total_delta_kt": "" if total_delta is None else "%.2f" % total_delta,
                    "industrial_pair_kt_earlier": "" if ind_a is None else "%.2f" % ind_a,
                    "industrial_pair_kt_later": "" if ind_b is None else "%.2f" % ind_b,
                    "industrial_pair_invariant": ("" if (ind_a is None or ind_b is None) else
                                                  ("yes" if abs(ind_b - ind_a) < TOTAL_TOL else "no")),
                    "revision_kind": kind, "note": note,
                })
    return out


HEADER = """\
# CONSECUTIVE PRINTS OF THE SAME REFERENCE PERIOD, PAIRED (rc53 Wave A1). A pair is formed only
# within one reference_fiscal_year AND one period_coverage - a nine-month July-March figure is never
# differenced against a full year. revision_kind: unchanged | provisional_to_final | level_revision |
# reallocation_within_total (the total held to within 1.5 kt while two or more users moved by >= 1 kt)
# | column_folded_into_cement (the later edition stops printing a column - Pak Steel, Domestic - and
# its Cement column grows by exactly that amount: a classification change, not a revision) |
# not_printed_in_one_edition. industrial_pair_* is brick + cement/others: invariant across a
# reallocation, which is why reversing one cannot repair the combined industrial decline, and why
# restoring an earlier brick print beside a later cement print would double-count the moved tonnage.
# Nothing here is booked; the booking policy is data/coal_booking_policy.csv.
# Generated by scripts/build_coal_vintage_ledger.py.
"""


def main():
    out = build()
    with open(OUT, "w", newline="", encoding="utf-8") as h:
        h.write(HEADER)
        w = csv.DictWriter(h, fieldnames=list(FIELDS), lineterminator="\n")
        w.writeheader()
        w.writerows(out)
    print("coal vintage ledger -> %s (%d pair rows)" % (os.path.relpath(OUT, ROOT), len(out)))
    flagged = [r for r in out if r["revision_kind"] == "reallocation_within_total"]
    seen = set()
    for r in flagged:
        key = (r["reference_fiscal_year"], r["period_coverage"], r["earlier_edition_year"], r["later_edition_year"])
        if key in seen:
            continue
        seen.add(key)
        print("  REALLOCATION %s %s: %s -> %s (total delta %s kt; brick+cement %s -> %s, invariant %s)"
              % (r["reference_fiscal_year"], r["period_coverage"], r["earlier_publication"],
                 r["later_publication"], r["pair_total_delta_kt"], r["industrial_pair_kt_earlier"],
                 r["industrial_pair_kt_later"], r["industrial_pair_invariant"]))
    for r in flagged:
        if r["sector_mapped"] in INDUSTRIAL_PAIR:
            print("      %-13s %10s -> %10s  (%s kt)" % (r["sector_mapped"], r["earlier_kt"], r["later_kt"], r["delta_kt"]))
    for r in out:
        if r["revision_kind"] in ("provisional_to_final", "level_revision", "column_folded_into_cement") and r["sector_mapped"] != "total":
            print("  %-12s %s %s %s: %s -> %s (%s kt, %s)" % (r["revision_kind"], r["reference_fiscal_year"],
                  r["period_coverage"], r["sector_mapped"], r["earlier_kt"], r["later_kt"], r["delta_kt"],
                  "%s -> %s" % (r["earlier_edition_year"], r["later_edition_year"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
