"""The comparison crosswalk: for every external comparison the release makes, what was
compared with what - source, gas metric, year basis, units, category boundary and the
inputs the two sides share - in one lookup a reader can hold beside the figure.

WHY. The comparison figure and the validation catalog state the ratios; the terms of each
comparison were spread over the catalog's long text columns and the BTR table's own note
column, and a reader could not tell from the figure which comparisons are like-for-like on
year and gas and which are declared mismatches (the BTR's FY2020-21 inventory year is
matched by the inventory's own FY2020-21, while the CRT cells are calendar 2022; AR5 CO2e
with no fossil-CH4 split). This table is that declaration, built
from the two products and nothing else, so it cannot drift from them.

Usage:  python3 -m pkinv.report.comparison_crosswalk
Writes: outputs/pakemis_comparison_crosswalk.csv
"""
import csv
import io
import os

from pkinv.core.io import write_table
from pkinv.paths import OUTPUTS

CATALOG = os.path.join(OUTPUTS, "pakemis_validation_catalog.csv")
BTR = os.path.join(OUTPUTS, "pakemis_btr_comparison.csv")
OUT = os.path.join(OUTPUTS, "pakemis_comparison_crosswalk.csv")

FIELDS = ("comparison_id", "kind", "source", "gas_metric", "pakemis_year_basis",
          "comparator_year_basis", "year_match", "units", "category_boundary",
          "independence_class", "shared_inputs", "what_the_ratio_can_say", "note")

EXTERNAL = ("btr", "crt", "edgar", "faostat", "climate trace", "gcd", "bur", "tnc",
            "elk", "pcaa", "official")


def _rows(path):
    with io.open(path, encoding="utf-8") as handle:
        return list(csv.DictReader(line for line in handle if not line.startswith("#")))


def _year_match(pak, comp):
    pak, comp = pak.lower(), comp.lower()
    if "not-applicable" in comp:
        return "not applicable"
    if "cy" in comp and "fy" in pak:
        return "declared mismatch: fiscal vs calendar"
    if "straddle" in comp or "blend" in comp or "matched" in comp:
        return "declared blend or straddle"
    if comp and pak and (comp == pak or comp in pak or pak in comp):
        return "same basis"
    return "declared in the catalog row"


def build():
    out = []
    for r in _rows(CATALOG):
        src = r["source"].lower()
        if not any(k in src for k in EXTERNAL) or r["independence_class"] == "not-applicable":
            continue
        pak_basis = "FY2023-24" if "FY" not in r["period"] else r["period"]
        out.append({
            "comparison_id": r["validation_id"], "kind": "catalog entry",
            "source": r["source"],
            "gas_metric": r["result_metric"] or "co2e_Mt_AR5",
            "pakemis_year_basis": pak_basis, "comparator_year_basis": r["period"],
            "year_match": _year_match(pak_basis, r["period"]),
            "units": "Mt CO2e AR5" if "co2e" in (r["result_metric"] or "co2e").lower()
                     else r["result_metric"],
            "category_boundary": r["boundary"],
            "independence_class": r["independence_class"],
            "shared_inputs": r["shared_inputs"],
            "what_the_ratio_can_say": r["interpretation_limit"],
            "note": "calibration" if r["calibration_or_validation"] == "calibration" else ""})
    for r in _rows(BTR):
        out.append({
            "comparison_id": "btr:%s" % r["pakemis_codes"], "kind": "BTR category row",
            "source": "Pakistan First BTR, inventory year 2020-21 (a Pakistani fiscal year by "
                      "the BTR's own statement); the CRT's calendar-2022 cells are not used here",
            "gas_metric": "co2e_Mt_AR5 (BTR prints AR5 CO2e, no fossil/biogenic CH4 split)",
            "pakemis_year_basis": "FY2020-21 (the inventory's own FY2020-21 estimate)",
            "comparator_year_basis": "FY2020-21",
            "year_match": "same fiscal year",
            "units": "Mt CO2e AR5",
            "category_boundary": "%s (BTR %s) %s, tier %s" % (r["pakemis_codes"], r["btr_codes"],
                                                            r["subject"], r["tier"]),
            "independence_class": "shared-upstream",
            "shared_inputs": "national statistics both inventories read",
            "what_the_ratio_can_say": ("ratio %s; within 0.5-2.0x: %s; uniform-28 ratio %s"
                                       % (r["ratio_pakemis_over_btr"], r["within_0.5_2.0x"],
                                          r["ratio_ch4_uniform_28"])),
            "note": r["ch4_convention_note"][:160]})
    return out


def main():
    rows = build()
    write_table(OUT, FIELDS, rows, banner=(
        "# What each external comparison compares: source, gas metric, year basis, units,",
        "# category boundary, independence. Built from pakemis_validation_catalog.csv and",
        "# pakemis_btr_comparison.csv by pkinv.report.comparison_crosswalk; nothing reads it.",))
    print("comparison_crosswalk: %d rows (%d catalog, %d BTR)"
          % (len(rows), sum(r["kind"] == "catalog entry" for r in rows),
             sum(r["kind"] != "catalog entry" for r in rows)))


if __name__ == "__main__":
    main()
