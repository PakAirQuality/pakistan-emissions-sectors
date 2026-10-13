"""National crosswalk against Pakistan's Common Reporting Tables (CY2022).

WHAT THIS IS. A join, not a calculation. Eight sectors already extract the CRT cells that
correspond to their own categories, each with a workbook hash and a cell reference; this
assembles them into one table so the inventory can be read against the country's own filing
in one place instead of eight. It computes no emissions and reproduces no arithmetic - if a
number here is wrong, it is wrong in the sector module that produced it.

WHY THE PERIOD COLUMN IS THE POINT. The CRT reports calendar 2022. Nine of the ten sectors
here report FY2023-24 and one reports FY2024-25, so for most codes the two describe NO
OVERLAPPING MONTHS at all. That is not a defect in either - a fiscal-year inventory and a
calendar-year filing are both legitimate - but a ratio computed across a two-year gap is a
statement about how Pakistan's emissions changed, not about whether two methods agree, and
the two are routinely confused. Every row therefore carries the overlap in months, and a row
with zero overlap is labelled as a vintage comparison rather than a method comparison.

WHAT IT REPORTS ABOUT ABSENCE. The rows without a cell-level comparator matter as much as
the rows with one. Where the filing enters NE for a category this inventory estimates, the
disagreement is total and a ratio would be meaningless; where this inventory does not
estimate a category the filing reports, the gap is ours. Both appear as rows.

Usage:  python3 -m pkinv.report.crt_crosswalk
Writes: outputs/national_crt_crosswalk.csv
"""

from pkinv.assets import asset_path
import csv
import os

from pkinv.core import period, registry
from pkinv.paths import OUTPUTS
from pkinv.activity.store import read_rows
from pkinv.core.io import write_table

CRT_INVENTORY_YEAR = 2022
CRT_PERIOD = period.calendar(CRT_INVENTORY_YEAR)
CRT_SOURCE = "Pakistan First Biennial Transparency Report (2024), Common Reporting Tables"


def _rows(name):
    path = asset_path(OUTPUTS, name)
    if not os.path.exists(path):
        return []
    return read_rows(path, comments=False)


def _first(name, col, **where):
    for r in _rows(name):
        if all(str(r.get(k, "")) == str(v) for k, v in where.items()):
            try:
                return float(r[col])
            except (TypeError, ValueError):
                return None
    return None


# (IPCC code, label, sector, CRT value in Mt CO2e, engine categories).
# The CRT extractions are per-sector and heterogeneous by design - each sector pulled the
# cells its own category needed - so the accessor is named per row rather than guessed.
def _crt_values():
    return {
        "1.A.1.a": ("Electricity and heat production", "power",
                    _pick(_first("power_crt_comparison.csv", "value",
                                 item="CRT 1.A.1.a CO2 (kt)"), 1e-3)),
        "1.A.3.a": ("Domestic aviation", "aviation",
                    _pick(_first("aviation_unfccc_crt_extracted.csv", "total_co2e_t",
                                 scope="domestic territory"), 1e-6)),
        "1.B.2": ("Fugitive emissions from oil and gas", "fugitives",
                  _pick(_first("fugitives_unfccc_crt_total.csv", "total_co2e_kt"), 1e-3)),
        "2.A.1": ("Cement production", "ippu",
                  _pick(_first("ippu_unfccc_crt_summary_2022.csv", "total_co2e_kt",
                               category="2.A.1.  Cement production"), 1e-3)),
    }


def _pick(value, scale):
    return None if value is None else value * scale


# Engine categories behind each code, so the comparison is like-for-like on our side too.
ENGINE_CATEGORIES = {
    "1.A.1.a": ("Electricity and heat production",),
    "1.A.3.a": ("Domestic aviation",),
    "1.B.2": ("Fugitive emissions from oil and gas",),
    "2.A.1": ("Cement production",),
}


def build():
    components, _categories, _sector_of = registry.build_all()
    engine_by_category = {}
    for c in components:
        engine_by_category[c["category"]] = (engine_by_category.get(c["category"], 0.0)
                                             + c["co2e_Mt_AR5"])
    sectors = {s.NAME: s for s in registry.all_sectors()}

    out = []
    for code, (label, sector_name, crt_mt) in sorted(_crt_values().items()):
        s = sectors[sector_name]
        engine_mt = sum(engine_by_category.get(cat, 0.0)
                        for cat in ENGINE_CATEGORIES[code])
        overlap = period.overlap_months((s.PERIOD_START, s.PERIOD_END), CRT_PERIOD)
        out.append({
            "ipcc_code": code,
            "category": label,
            "sector": sector_name,
            "crt_period": period.label(*CRT_PERIOD),
            "engine_period": period.label(s.PERIOD_START, s.PERIOD_END),
            "overlap_months": overlap,
            "crt_Mt_co2e": round(crt_mt, 4) if crt_mt is not None else "",
            "engine_Mt_co2e": round(engine_mt, 4),
            "ratio_engine_over_crt": (round(engine_mt / crt_mt, 4)
                                      if crt_mt else ""),
            "comparison_kind": ("method" if overlap >= 6 else
                                "vintage" if overlap > 0 else "no overlap"),
            "note": ("the two periods share %d of twelve months; a ratio across a gap this "
                     "wide measures how the source changed, not whether two methods agree"
                     % overlap) if overlap < 6 else "",
        })
    return out


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    rows = build()
    path = asset_path(OUTPUTS, "national_crt_crosswalk.csv")
    write_table(path, list(rows[0].keys()), rows)

    print("CRT crosswalk against %s -> %s" % (period.label(*CRT_PERIOD), path))
    print("  %s" % CRT_SOURCE)
    for r in rows:
        print("  %-8s %-38s CRT %8s  engine %8.3f  %-10s overlap %2d mo"
              % (r["ipcc_code"], r["category"][:38], r["crt_Mt_co2e"],
                 r["engine_Mt_co2e"], r["comparison_kind"], r["overlap_months"]))
    zero = [r for r in rows if r["overlap_months"] == 0]
    print("  %d of %d codes share NO months with the filing: a fiscal-year inventory and a "
          "calendar-year submission two years apart" % (len(zero), len(rows)))


if __name__ == "__main__":
    main()
