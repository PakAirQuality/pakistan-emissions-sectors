"""Crop-residue burning windows, derived from the FAO calendar's own harvest dates.

WHY DERIVED AND NOT TYPED. The first fire fetch hard-coded two windows (rice stubble,
wheat residue) and the burning cross-check's own docstring then measured the cost:
cotton sticks, maize stover and cane trash - roughly two fifths of burned dry matter -
burn in windows the fetch never covered, and the comparator disagreed by up to 46.5
points in exactly those months. The windows now come from the held FAO calendar
(data/raw/fao_crop_calendar/Pakistan_crop_calendar.json): for each burnable crop, the
burning window opens at the EARLIEST harvest date any agro-ecological zone reports and
closes TAIL_DAYS after the LATEST - residue is burned in the weeks after harvest, and
the tail is the one declared judgement here, a parameter with a name rather than a
number inside a date literal.

ONE IMPLEMENTATION, TWO CONSUMERS. The fetcher scopes its API windows with these, and
burning_profile() restricts attribution with the same objects - so a detection can
never be attributed inside a window the fetch did not cover, and widening a window is
one change in one place.

The crop set is the burning ledger's own (data/burning_params.csv): rice, wheat,
cotton, maize, sugarcane. The FAO name map lives here beside its consumer; note the
JSON spells maize "Mais, sucre" (with accents) - matching bare "Mais" silently
dropped maize for two releases, which is why the map is exact strings.
"""

from pkinv.assets import asset_path
import json
import os
from datetime import date, timedelta

from pkinv.paths import ROOT

CALENDAR = asset_path(ROOT, "data", "raw", "fao_crop_calendar",
                        "Pakistan_crop_calendar.json")

# FAO's French crop names -> the burning ledger's crops. Exact strings from the JSON.
FAO_CROPS = {
    "Riz": "rice",
    "Pain de blé": "wheat",
    "Coton": "cotton",
    "Maïs, sucré": "maize",
    "Canne à sucre": "sugarcane",
}

# Residue is burned in the weeks after harvest; 45 days after the latest zone's
# harvest closes the window. A declared judgement, not an observation - the FRP
# weighting inside the window is what carries the observed signal.
TAIL_DAYS = 45


# The consumed derivative of the calendar: one row per FAO harvest session, written by
# scripts/derive_fao_harvest_sessions.py. rc40: the engine reads THIS, not the JSON. The
# JSON is a publisher document with no stated redistribution terms, so a validation
# package cannot carry it, and a monthly layer that parsed it directly could not run
# anywhere the document is absent. tests/test_burn_windows.py asserts table == parser
# output whenever the JSON is present.
SESSIONS = asset_path(ROOT, "data", "activity", "agriculture", "fao_harvest_sessions.csv")


def _load():
    with open(CALENDAR, encoding="utf-8") as handle:
        return json.load(handle)


def sessions_from_calendar():
    """[(crop, fao_name, session_index, early (month, day), late (month, day))] parsed
    from the FAO JSON - the deriver's input, kept here so the parser lives beside the
    reader that consumes its output."""
    sessions = []
    for entry in _load():
        fao_name = entry.get("crop", {}).get("name", "")
        crop = FAO_CROPS.get(fao_name)
        if not crop:
            continue
        for index, session in enumerate(entry.get("sessions", [])):
            early = session.get("early_harvest") or {}
            late = session.get("late_harvest") or {}
            if not (early.get("month") and late.get("month")):
                continue
            sessions.append((crop, fao_name, index,
                             (int(early["month"]), int(early.get("day") or 1)),
                             (int(late["month"]), int(late.get("day") or 28))))
    return sessions


def harvest_sessions():
    """[(crop, early (month, day), late (month, day))] - one entry per FAO session,
    read from the derived table.

    Sessions stay separate because a crop's harvest can WRAP the calendar year
    (sugarcane is cut November into March): min/max over (month, day) tuples turns a
    Nov-Mar season into a nonsense Feb-Dec one, which is exactly what the first cut
    of this module did. The wrap is resolved per session when the dates are anchored
    into a fiscal year, never by tuple arithmetic.
    """
    from pkinv.activity.store import read_rows
    sessions = []
    for r in read_rows(SESSIONS):
        sessions.append((r["crop"],
                         (int(r["early_month"]), int(r["early_day"])),
                         (int(r["late_month"]), int(r["late_day"]))))
    return sessions


def _anchor(md, fy_start):
    """The (month, day) placed in the fiscal year fy_start (Jul..Jun)."""
    month, day = md
    year = fy_start if month >= 7 else fy_start + 1
    return date(year, month, min(day, 28))


def _merge(spans):
    """Overlapping or touching (start, end) spans folded into disjoint ones."""
    merged = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1] + timedelta(days=1):
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def windows(fy_start):
    """[(crop, start_date, end_date)] - the burning windows inside one fiscal year.

    Per session: harvest start to TAIL_DAYS after harvest end, wrap resolved by
    date arithmetic (a late date earlier in the calendar than its early date is the
    next calendar year). Sessions of one crop merge where they overlap. A window
    whose tail crosses June 30 is clipped to the fiscal year: the layer contract
    normalises within the year, and a window is an attribution boundary, not a
    mass claim.
    """
    fiscal_end = date(fy_start + 1, 6, 30)
    fiscal_start = date(fy_start, 7, 1)
    by_crop = {}
    for crop, early, late in harvest_sessions():
        start = _anchor(early, fy_start)
        end = _anchor(late, fy_start)
        if end < start:                      # the session wraps the calendar year
            end = date(end.year + 1, end.month, end.day)
        end = end + timedelta(days=TAIL_DAYS)
        start = max(start, fiscal_start)
        end = min(end, fiscal_end)
        if start <= end:
            by_crop.setdefault(crop, []).append((start, end))
    out = []
    for crop, spans in sorted(by_crop.items()):
        for start, end in _merge(spans):
            out.append((crop, start, end))
    return out


def in_window(crop_windows, when):
    """The crops whose window contains this date (a detection can sit in several)."""
    return [crop for crop, start, end in crop_windows if start <= when <= end]
