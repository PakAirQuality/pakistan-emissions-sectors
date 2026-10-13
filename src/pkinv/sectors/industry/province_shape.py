"""Industrial liquid fuels by province, from OCAC's own area pages (rc62).

WHY THIS EXISTS. `data/province_shares.csv` carried ONE row, `industry_liquid_fuel`, for every
OCAC liquid this sector burns, and its own source note says what it is: the Total Industry
customer-class rows "for FO, HSD, LDO, KERO, MS and HOBC summed" over one fiscal year. Two things
follow, and both are defects rather than approximations.

FURNACE OIL DOES NOT LIVE WHERE THE BLEND LIVES. Measured from the same panel, the same customer
class, the same twelve months:

    furnace oil alone, FY2023-24   Punjab 0.7844  Sindh 0.1722  KP 0.0394  Balochistan 0.0040
    the six-product blend          Punjab 0.6536  Sindh 0.2703  KP 0.0539  Balochistan 0.0139

High-speed diesel, motor spirit and kerosene are sold through a far more Karachi-weighted network
than furnace oil is, and averaging them in costs Punjab thirteen points. The furnace-oil stream is
the largest single contributor to Lahore's SO2, and it was riding the retail geography of fuels it
does not burn.

AND THE YEAR AXIS WAS SITTING IN A FILE THE MODULE ALREADY OPENS. The blend was built from a
single fiscal year and applied to all nine. `src/pkinv/sectors/industry/monthly.py` reads this very
panel and filters `area == "PAKISTAN"`, discarding the provincial rows at the filter. OCAC's direct
single-month editions carry full area pages, the repository holds forty-eight of them, and the
ingest has them: `Total Industry` x `FO` is complete for twelve months in each of FY2021-22,
FY2022-23, FY2023-24 and FY2024-25, closing to the annual control to 0.02 percent.

A RETRACTION. The `industry_liquid_fuel` note claims the reference year "cannot supply this:
OCAC printed one direct monthly edition that year (July 2023) and eleven cumulative ones". That is
false of the repository as it stands - all twelve FY2023-24 area months are held and ingested - and
`src/pkinv/sectors/transport/province_shape.py:43-58` is a written retraction of the identical
premise for road fuels. The industry row never received the correction; it does now.

WHAT THIS MODULE REFUSES. A partial year. `shares()` raises rather than returning a shape built
from three months, for the reason the transport module states: a one-month shape is not a worse
annual shape, it is a different quantity wearing the same name.
"""

from pkinv.assets import asset_path
import collections
import os

from pkinv.core.geography import PROVINCES
from pkinv.activity.store import read_rows
from pkinv.paths import DATA

PANEL = asset_path(DATA, "activity", "transport", "ocac_sectoral_provincial.csv")

# The OCAC customer class this sector's liquid activity is already taken from - the same rows
# src/pkinv/sectors/industry/data.py reads for the national tonnes.
SECTOR_ROW = "Total Industry"

# The reference period's own area pages ARE the committed rows in data/province_shares.csv, so
# the own-year path skips it - see pkinv.sectors.industry.downscale.load_shares for why
# recomputing a row to a different last digit would break its own backcast years' digest.
REFERENCE_SHAPE_YEAR = 2024          # FY2023-24

# THREE GROUPS, AND THE SPLIT IS EARNED RATHER THAN TIDY. Furnace oil and high-speed diesel are
# each large enough and steady enough to carry their own geography; measured over the four complete
# panel years their Punjab shares sit in 0.760-0.802 and 0.425-0.447 respectively, on 642-818 kt
# and 368-494 kt a year. The other four together are 34 kt at the reference year - three percent of
# industrial liquid tonnage - and their shares swing far too hard to be read as geography: LDO's
# Punjab share runs 0.67 to 1.00 and kerosene's 0.53 to 0.89 on a few thousand tonnes. Giving each
# of them its own vector would dress sampling noise as a map, so they are blended, and this comment
# is the reason rather than an oversight.
FURNACE_OIL = ("FO",)
DIESEL = ("HSD",)
MINOR_LIQUIDS = ("LDO", "KERO", "MS", "HOBC")
PRODUCTS = {"furnace_oil": FURNACE_OIL, "diesel": DIESEL, "minor_liquids": MINOR_LIQUIDS}

# subitem prefix -> group. The SAME product supplies both the quantity and its geography: the
# tonnes come from data.LIQUID_ITEMS keyed on these OCAC codes, and the map now comes from the
# same publication's area pages for the same code. A subitem that reaches here unmatched raises.
GROUP_OF_SUBITEM = {
    "Industrial furnace oil": "furnace_oil",
    "Industrial diesel": "diesel",
    "Industrial light diesel oil": "minor_liquids",
    "Industrial kerosene": "minor_liquids",
    "Industrial gasoline": "minor_liquids",
    "Industrial HOBC": "minor_liquids",
}
PROFILE_OF_GROUP = {"furnace_oil": "industry_furnace_oil",
                    "diesel": "industry_diesel",
                    "minor_liquids": "industry_minor_liquids"}


def group_for_subitem(subitem):
    """The product group a liquid subitem belongs to, or None if it is not a liquid."""
    for prefix, group in GROUP_OF_SUBITEM.items():
        if subitem.startswith(prefix):
            return group
    return None

# OCAC's area vocabulary is not the engine's, and the mapping is the transport module's - one
# reading of one publication, not two. KARACHI is a SUB-TOTAL of SINDH (the panel flags it
# additive=0 for that reason); FATA merged into Khyber Pakhtunkhwa in 2018 and older editions
# still list it; Gilgit-Baltistan and Azad Kashmir are the engine's "Other".
from pkinv.sectors.transport.province_shape import AREA_TO_PROVINCE, _fiscal_year  # noqa: E402

# KARACHI is excluded from the shares by the additive filter, but it is the ONE within-province
# observation OCAC publishes, and it is what tests the built-up surface. Kept as its own reader.
KARACHI = "KARACHI"


def _panel(rows=None):
    return [r for r in (read_rows(PANEL, comments=False) if rows is None else rows)
            if r["sector_row"] == SECTOR_ROW and r["area"] != "PAKISTAN"
            and r["additive"] == "1" and r["report_kind"] == "monthly"]


def months_covered(fiscal_year, group="furnace_oil", rows=None):
    """Distinct provincial months OCAC printed for this group in this fiscal-END year."""
    wanted = PRODUCTS[group]
    return len({r["month"] for r in _panel(rows)
                if _fiscal_year(r["month"]) == fiscal_year and r["product"] in wanted})


def complete_years(group="furnace_oil", rows=None):
    """The fiscal-END years with all twelve provincial months - the only ones shares() serves."""
    panel = _panel(rows)
    years = {_fiscal_year(r["month"]) for r in panel}
    return tuple(sorted(y for y in years if months_covered(y, group, panel) == 12))


def shares(group, fiscal_year, rows=None):
    """{province: share} for one product group in one fiscal-END year, summing to exactly 1.

    RAISES on a year without twelve months. See the module docstring.
    """
    panel = _panel(rows)
    covered = months_covered(fiscal_year, group, panel)
    if covered != 12:
        raise ValueError(
            "OCAC printed %d provincial month(s) of %s for FY%d-%02d, not 12; a shape cannot be "
            "built from a partial year" % (covered, group, fiscal_year - 1, fiscal_year % 100))
    wanted = PRODUCTS[group]
    acc = collections.Counter()
    for r in panel:
        if _fiscal_year(r["month"]) != fiscal_year or r["product"] not in wanted:
            continue
        acc[AREA_TO_PROVINCE.get(r["area"], "Other")] += float(r["tonnes"] or 0)
    total = sum(acc.values())
    if total <= 0:
        raise ValueError("no %s tonnage in FY%d-%02d" % (group, fiscal_year - 1, fiscal_year % 100))
    return {p: acc[p] / total for p in PROVINCES}


def karachi_share_of_sindh(group, fiscal_year, rows=None):
    """Karachi's share of SINDH's own tonnage - the one within-province figure OCAC publishes.

    It exists to be compared against what the cube's built-up surface gives the Karachi shape.
    They disagree by about a factor of two, which is the only direct test available of the
    within-province surface every diffuse industry stream rides.
    """
    wanted = PRODUCTS[group]
    karachi = sindh = 0.0
    for r in read_rows(PANEL, comments=False):
        if (r["sector_row"] != SECTOR_ROW or r["product"] not in wanted
                or r["report_kind"] != "monthly" or _fiscal_year(r["month"]) != fiscal_year):
            continue
        if r["area"] == KARACHI:
            karachi += float(r["tonnes"] or 0)
        elif r["area"] == "SINDH" and r["additive"] == "1":
            sindh += float(r["tonnes"] or 0)
    return (karachi / sindh) if sindh else None
