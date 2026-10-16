"""NFDC Table 3.4 monthly offtake, as a seasonal shape for agriculture's synthetic nitrogen.

WHY THIS IS IN THE SECTOR AND NOT IN CORE. Only agriculture reads it. `core/ocac_monthly.py`
and `core/pbs_qim.py` are in core because four modules and two modules respectively read them;
promoting a single-consumer reader would be the same over-generalisation this project has
already paid for in declared tables nobody used.

WHAT IT FIXES. `monthly.py` shaped nitrogen from NFDC's Annex-7, which covers ONE fiscal year
and runs APRIL TO MARCH, so three of its twelve months had to be borrowed from the opening year
and graded T3. Table 3.4 of the consolidated volume publishes the same offtake for FY2012-13
through FY2022-23 on a JULY-TO-JUNE basis - the inventory's own fiscal year - so those eight
years need no borrowing and every month is observed. Since Pass 2 the panel carries a second
lane: the Annual Fertilizer Review 2023-24's Annex-5 supplies the reference year's own twelve
months (scripts/ingest_nfdc_annex5.py), so FY2023-24 rides this module too and the borrowing
branch is never taken for it. source_name() reads the lane from the rows' own source_file.

The two vintages agree where they overlap. Annex-7's April, May and June 2023 are also the last
three months of Table 3.4's FY2022-23, and the two independently transcribed sources differ by
two tonnes on four hundred thousand. That is the check that makes this admissible.

WHAT IT IS STILL NOT. Offtake is fertiliser leaving a DEALER'S DEPOT. Eight more years of a
depot ledger is still a depot ledger, so the class stays T2 and the timing target stays
`commodity_offtake`; nothing here brings the record any closer to when a soil actually emitted.

UREA ALONE, and deliberately, matching what `monthly.py` already did: urea is about four fifths
of the nitrogen and the only product whose N content is a single number, so weighting months by
urea is the closest thing to weighting them by nitrogen without re-deriving the nutrient split.
"""

from pkinv.assets import asset_path
from pkinv.activity.store import input_exists as _input_exists
import csv
import os
import re

from pkinv.core import monthly as core_monthly
from pkinv.paths import DATA
from pkinv.activity.store import read_rows
from pkinv.core.reporting_window import CORE_FY_STARTS

PANEL = asset_path(DATA, "activity", "monthly", "nfdc_month_product_offtake.csv")
ANNEX5 = asset_path(DATA, "nfdc", "annex5_national_month_product.csv")
UREA = "UREA"


def _panel():
    rows = list(read_rows(PANEL)) if _input_exists(PANEL) else []
    existing_years = {int(row["fiscal_year_start"]) for row in rows}
    # The 2024-25 review's already transcribed Annex5 holds complete national
    # product-month quantities. Do not confuse an unconnected extraction with
    # absent evidence. Existing-year agency-resolved observations remain intact.
    if _input_exists(ANNEX5):
        numbers = {name: index for index, name in enumerate(
            ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1)}
        for row in read_rows(ANNEX5):
            start = int(row["fiscal_year"].split("-")[0])
            if start in existing_years or start not in CORE_FY_STARTS:
                continue
            year, month = int(row["calendar_year"]), numbers[row["month"]]
            if year - (month < 7) != start:
                raise ValueError("NFDC Annex5 observation is outside its stated fiscal year")
            rows.append(dict(fiscal_year_start=str(start), month="%d%02d" % (year, month),
                product=row["product"].upper(), agency="National total",
                tonnes=row["offtake_product_tonnes"], source_file="data/nfdc/AFR_2024-25.pdf",
                source_page="", timing_target="commodity_offtake", t_class="T2"))
    return rows


def series(fy_start, product=UREA, rows=None):
    """{YYYYMM: tonnes} for one product in one fiscal year, or {} where the table stops.

    An EMPTY DICT for "this year is not in the table" and an exception only for a year that is
    present and incomplete. A caller with a second source - and this one has Annex-7 - must be
    able to tell those apart, because an exception thrown past it discards the second source
    too. That is the failure that left agriculture's rice calendar unused for eight years.
    """
    rows = rows if rows is not None else _panel()
    matched = [r for r in rows
               if r["product"] == product and int(r["fiscal_year_start"]) == fy_start]
    if not matched:
        return {}
    out = {}
    for row in matched:
        out[row["month"]] = out.get(row["month"], 0.0) + float(row["tonnes"])
    missing = set(core_monthly.months_for(fy_start)) - set(out)
    if missing:
        raise KeyError("NFDC Table 3.4 has FY%d-%02d but is missing month(s) %s - a partial "
                       "year cannot be normalised into twelve shares"
                       % (fy_start, (fy_start + 1) % 100, sorted(missing)))
    return out


def covers(fy_start, product=UREA, rows=None):
    try:
        return bool(series(fy_start, product, rows))
    except KeyError:
        return False


def source_name(fy_start, rows=None):
    """The publication behind this year's panel rows, read from the rows themselves.

    The panel carries two lanes - Table 3.4 of the consolidated Fertilizer Statistics
    to FY2022-23, and the Annual Fertilizer Review 2023-24's Annex-5 for the reference
    year (Pass 2, the sixteenth review's false-gap fix). The basis line must name the
    lane the year actually came from; deciding by fiscal year would silently mislabel
    the day either lane's window moves.
    """
    rows = rows if rows is not None else _panel()
    files = {r["source_file"] for r in rows
             if int(r["fiscal_year_start"]) == fy_start}
    review = {f for f in files if re.search(r"annual_fertilizer_review|AFR_", f, re.I)}
    if review and review != files:
        raise ValueError("FY%d mixes NFDC source lanes: %s" % (fy_start, sorted(files)))
    if review:
        editions = {tuple(re.search(r"(?:annual_fertilizer_review_|AFR_)(\d{4})[_-](\d{2})",
                                    f, re.I).groups()) for f in review}
        if len(editions) != 1:
            raise ValueError("NFDC fiscal year mixes review editions: " + repr(sorted(files)))
        first, last = next(iter(editions))
        return "AFR %s-%s Annex-5" % (first, last)
    return "Table 3.4"


def profile(fy_start, product=UREA, rows=None):
    """({month: share summing to 1}, {month: "T2"}) - every month observed, none borrowed.

    The T-class is uniform here, unlike the Annex-7 path it supersedes, because Table 3.4 is
    published on the fiscal year this inventory reports. There is no April-to-March offset to
    absorb and so nothing to borrow.
    """
    values = series(fy_start, product, rows)
    return core_monthly.normalise(values), {month: "T2" for month in values}
