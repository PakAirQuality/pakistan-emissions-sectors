"""Release periods: common core, candidate extension and detailed reference are distinct.

FY2025–26 is a candidate, not automatically a common-scope national estimate. The
source availability register determines which candidate source records may be emitted.
Reference-year constants remain independent of the latest annual core year.
"""
FIRST_FY_START = 2015
CORE_LAST_FY_START = 2024
REFERENCE_FY_START = 2023
CANDIDATE_FY_START = 2025
CORE_FY_STARTS = tuple(range(FIRST_FY_START, CORE_LAST_FY_START + 1))
CORE_FY_ENDS = tuple(year + 1 for year in CORE_FY_STARTS)
REFERENCE_PERIOD = "FY2023-24"
CORE_SUFFIX = "fy2015_16_fy2024_25"
AUDIT_DATE = "2026-10-14"


def fiscal_label(start):
    return "FY%d-%02d" % (start, (start + 1) % 100)


CORE_PERIOD_IDS = tuple(fiscal_label(year) for year in CORE_FY_STARTS)

# These exact former GHG panels contain superseded rc67 source values and are no
# longer products of the current producers. The immutable rc67 campaign baseline
# retains the original CSVs and their hashes. The current ten-year files replace
# them; separately regenerated nine-year air compatibility views are not retired.
RETIRED_GHG_PANEL_PRODUCTS = frozenset({
    "outputs/pakemis_annual_fy2015_16_fy2023_24.csv",
    "outputs/pakemis_annual_fy2015_16_fy2023_24.parquet",
    "outputs/pakemis_monthly_fy2015_16_fy2023_24.csv",
    "outputs/pakemis_monthly_fy2015_16_fy2023_24.parquet",
})


def is_common_core(period_id):
    return period_id in {fiscal_label(year) for year in CORE_FY_STARTS}


CORE_PERIOD_TEXT = "July 2015-June 2025, ten fiscal years (FY2015-16 to FY2024-25)"
CANDIDATE_PERIOD_TEXT = ("FY2025-26 (July 2025-June 2026): separate provisional source "
                         "extension, partial process coverage, no national total")


def require_common_core(period_id, purpose="a national total"):
    """Refuse any non-core period for a common-scope aggregate.

    A national or sector-complete sum is defined only on the ten core fiscal years. The
    FY2025-26 candidate has full-year evidence for some processes (liquid sales, QIM output,
    crop seasons, nitrogen offtake) and only July-March or nothing for others (station fuel,
    gas, coal, upstream production), so a sum over it is a partial-source total and is
    refused here rather than labelled.
    """
    if not is_common_core(period_id):
        raise ValueError("%s is not a common-core fiscal period; %s is defined only for %s"
                         % (period_id, purpose, CORE_PERIOD_TEXT))
    return period_id
