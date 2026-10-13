"""Provincial shape for road fuel, and the bracket that says how much it can be trusted.

THE PROBLEM THIS SOLVES. The magnitude control and the spatial shape do not come from the
same publication in the same year. OCAC prints an annual Road row for nine fiscal years;
monthly provincial AREA pages exist in the direct single-month editions, and the panel now
holds twelve of them for each of FY2021-22, FY2022-23, FY2023-24 and FY2024-25 (the old
claim that only FY2021-22/FY2024-25 had them was an artefact of reading the cumulative
editions, retracted below - and it was wrong about FY2022-23 too, whose twelve direct
months sit in the panel unread until rc47 Wave 5). The six years before July 2021 have no
provincial pages at all, which is the real geography gap.

The sector used to resolve that by reporting FY2021-22 - moving the whole inventory backwards
to where the map was, which left the national total carrying a transport figure from before
the post-2022 demand contraction. That is the wrong trade. Under this architecture the
control sets the magnitude and the allocation only distributes it, so:

    MAGNITUDE from the reference period.
    SHAPE from the nearest period that has one, declared as borrowed.

BRACKETED, NOT ASSERTED. FY2021-22 and FY2024-25 straddle the reference year - one 24 months
before its midpoint, one 12 months after - so both are computed and the spread is published.
A borrowed shape is a claim about how little provincial composition moves between years, and
the honest way to support that claim is to show the two ends rather than to state it.

WHY A BORROWED SHAPE IS SAFE AND A BORROWED MAGNITUDE IS NOT. Shares sum to one by
construction, so substituting one year's shape for another cannot create or destroy a tonne;
it can only move tonnes between provinces. The national total, every sector total and every
category total are invariant to this choice. That is the same property the monthly layer
relies on, and it is why the reference period is set by the control rather than by the map.

Usage:  python3 -m pkinv.sectors.transport.province_shape
Writes: outputs/transport_provincial_shape_brackets.csv
"""

from pkinv.assets import asset_path
import collections
import csv
import os

from pkinv.core.geography import PROVINCES
from pkinv.paths import DATA, OUTPUTS
from pkinv.activity.store import read_rows

PANEL = asset_path(DATA, "activity", "transport", "ocac_sectoral_provincial.csv")

# THE REFERENCE YEAR'S OWN SHAPE, AND FOR A RELEASE IT WAS BORROWED ON A FALSE PREMISE.
# This module used to publish FY2024-25's shape for the FY2023-24 magnitude, on the claim
# that OCAC "printed twelve complete area pages for FY2024-25 and FY2021-22 but not for the
# reference period between them". That was true of the CUMULATIVE editions the panel was
# built from - they print a PAKISTAN page only - and false of the publication: the direct
# single-month editions carry full area pages for every month, the repository held all 36 of
# them, and the ingest now reads their area pages for the months the cumulative editions
# cannot serve. The reference year has its own twelve provincial months and nothing is
# borrowed.
#
# THE BORROWING WAS NEARLY RIGHT, WHICH IS RECORDED RATHER THAN QUIETLY ENJOYED. The paper
# bounded the borrowed shape's error at 3.86 points using FY2021-22 as the bracket; measured
# against the reference year's own pages, the borrowed FY2024-25 shape was off by at most
# 0.45 points on any (province, fuel) share. The bounding argument was sound. The claim
# beneath it was not, and a sound bound over a false premise is not a substitute for the
# year's own data.
REFERENCE_SHAPE_YEAR = 2024          # FY2023-24: the reference period's OWN area pages
BRACKET_SHAPE_YEARS = (2022, 2025)   # the complete panel years either side of it

PRODUCTS = {"petrol": ("MS", "HOBC"), "diesel": ("HSD",)}

# OCAC's area vocabulary is not the engine's. KARACHI is a sub-total of SINDH and is flagged
# additive=0 in the panel for exactly that reason; FATA merged into Khyber Pakhtunkhwa in 2018
# and the older editions still list it separately; Gilgit-Baltistan and Azad Kashmir are the
# engine's "Other".
AREA_TO_PROVINCE = {
    "PUNJAB": "Punjab",
    "SINDH": "Sindh",
    "KHYBER PAKHTUNKHWA": "Khyber Pakhtunkhwa",
    "FATA": "Khyber Pakhtunkhwa",
    "BALOCHISTAN": "Balochistan",
}


def _fiscal_year(month):
    """OCAC's YYYY-MM to the fiscal year it falls in, keyed by END year."""
    year, mo = int(month[:4]), int(month[5:7])
    return year + 1 if mo >= 7 else year


def _panel():
    return [r for r in read_rows(PANEL, comments=False) if r["sector_row"] == "Road" and r["area"] != "PAKISTAN" and r["additive"] == "1"]


def months_covered(fiscal_year, rows=None):
    rows = _panel() if rows is None else rows
    return len({r["month"] for r in rows if _fiscal_year(r["month"]) == fiscal_year})


def shares(fuel, fiscal_year, rows=None):
    """{province: share} for one fuel in one fiscal year, summing to exactly 1.

    RAISES on a year without twelve months rather than returning a share set built from a
    partial year. A one-month shape is not a worse annual shape, it is a different quantity
    wearing the same name, and the sector spent a release pinned to the wrong reference
    period precisely to avoid that trap.
    """
    rows = _panel() if rows is None else rows
    covered = months_covered(fiscal_year, rows)
    if covered != 12:
        raise ValueError(
            "OCAC printed %d provincial month(s) for FY%d-%02d, not 12; a shape cannot be "
            "built from a partial year (see this module's docstring for the years that have "
            "complete panels)" % (covered, fiscal_year - 1, fiscal_year % 100))
    acc = collections.Counter()
    for r in rows:
        if _fiscal_year(r["month"]) != fiscal_year or r["product"] not in PRODUCTS[fuel]:
            continue
        acc[AREA_TO_PROVINCE.get(r["area"], "Other")] += float(r["tonnes"])
    total = sum(acc.values())
    return {p: acc[p] / total for p in PROVINCES}


def brackets():
    """The reference year's own shape against each neighbouring panel year, per fuel/province.

    The role reversed when the borrowing ended. These rows used to price a borrowed shape
    against its bracket; they now measure how much the provincial composition actually moves
    between adjacent years - which is the empirical answer to whether any future borrowing
    (a year whose direct editions stop being published, say) would be defensible.
    """
    rows = _panel()
    out = []
    for fuel in sorted(PRODUCTS):
        ref = shares(fuel, REFERENCE_SHAPE_YEAR, rows)
        for bracket_year in BRACKET_SHAPE_YEARS:
            alt = shares(fuel, bracket_year, rows)
            for p in PROVINCES:
                out.append({
                    "fuel": fuel, "province": p,
                    "share_reference_shape": ref[p], "share_bracket_shape": alt[p],
                    "spread_pp": 100.0 * (ref[p] - alt[p]),
                    "reference_shape_year": "FY%d-%02d" % (REFERENCE_SHAPE_YEAR - 1,
                                                           REFERENCE_SHAPE_YEAR % 100),
                    "bracket_shape_year": "FY%d-%02d" % (bracket_year - 1,
                                                         bracket_year % 100),
                })
    return out


def max_spread_pp():
    """The largest disagreement between the own-year shape and any neighbouring year.

    Under the borrowed shape this number DECIDED something - whether the borrowing was
    defensible. It now only describes how fast the composition drifts; it is kept published
    because it is what makes the next borrowing decision, anywhere, an informed one.
    """
    return max(abs(r["spread_pp"]) for r in brackets())


def borrowing_error_pp():
    """What the retired borrowing actually cost, per (fuel, province), worst case.

    The FY2024-25 shape stood in for the reference year for one release. Measured against
    the reference year's own pages it was off by this much at worst - the honest epitaph
    for a defensible-but-unnecessary choice.
    """
    rows = _panel()
    worst = 0.0
    for fuel in sorted(PRODUCTS):
        own = shares(fuel, REFERENCE_SHAPE_YEAR, rows)
        borrowed = shares(fuel, 2025, rows)
        for p in PROVINCES:
            worst = max(worst, abs(100.0 * (borrowed[p] - own[p])))
    return worst


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    rows = brackets()
    path = asset_path(OUTPUTS, "transport_provincial_shape_brackets.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["fuel", "province", "share_reference_shape",
                                          "share_bracket_shape", "spread_pp",
                                          "reference_shape_year", "bracket_shape_year"])
        w.writeheader()
        for r in rows:
            w.writerow({**r, "share_reference_shape": round(r["share_reference_shape"], 6),
                        "share_bracket_shape": round(r["share_bracket_shape"], 6),
                        "spread_pp": round(r["spread_pp"], 3)})
    print("Transport provincial shape, the reference year's OWN area pages -> %s" % path)
    print("  reference shape FY%d-%02d (%d months, nothing borrowed); brackets %s"
          % (REFERENCE_SHAPE_YEAR - 1, REFERENCE_SHAPE_YEAR % 100,
             months_covered(REFERENCE_SHAPE_YEAR),
             ", ".join("FY%d-%02d" % (y - 1, y % 100) for y in BRACKET_SHAPE_YEARS)))
    for fuel in sorted(PRODUCTS):
        ref = shares(fuel, REFERENCE_SHAPE_YEAR)
        print("  %-7s %s" % (fuel, "  ".join("%s %.3f" % (p[:3], ref[p]) for p in PROVINCES)))
    print("  largest drift against a neighbouring panel year: %.2f points" % max_spread_pp())
    print("  the retired FY2024-25 borrowing, measured against these pages: %.2f points "
          "worst case" % borrowing_error_pp())


if __name__ == "__main__":
    main()
