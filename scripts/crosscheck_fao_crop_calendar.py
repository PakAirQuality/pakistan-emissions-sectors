"""Check the rice calendar the methane profile rides against FAO's published windows.

WHAT IS ON TEST. `data/rice_calendar.csv` gives the transplant and harvest weeks that shape
rice methane - the flooded window is the profile - and every one of its provincial rows carries
`provenance_class = working-pointer`, whose own note says the source string "names a body of
literature but not a specific author, title and volume". A profile resting on a citation nobody
can retrieve is the kind of thing a reviewer finds, and FAO's crop calendar is a retrievable
publication covering the same crop and country.

WHAT IS COMPARED, AND WHAT DELIBERATELY IS NOT. Only HARVEST. FAO publishes a sowing window and
this calendar publishes a TRANSPLANT week, and for rice those are different operations three to
four weeks apart - nursery sowing precedes transplanting into the flooded paddy. Comparing them
would produce a disagreement that is real about the operations and meaningless about the
calendar. Harvest is harvest in both, so harvest is what is checked and the sowing columns are
carried alongside for a reader without being scored.

WHY NO PROVENANCE CLASS CHANGES, WHICH WAS THE POINT OF RUNNING THIS. Three of the four zones
agree within three weeks, and it is still not enough to lift a row off `working-pointer`. The
profile rides the FLOODED WINDOW - transplant, flood, drain - and FAO corroborates the HARVEST
END, which is one endpoint of four and not one the profile reads. Upgrading a row's provenance
on the strength of a column the profile does not use would be the overclaim this check was
supposed to guard against. So the corroboration is published and the classes stand.

AND A DISAGREEMENT NEVER OVERWRITES. FAO's windows are climatological and zone-based, this
calendar is provincial and PARC-derived, and neither is entitled to correct the other. Khyber
Pakhtunkhwa differs by four weeks; it keeps its values.

FAO IS A CLIMATOLOGY. It can shape a season and can never date one, so nothing here becomes a
year-specific input, and this changes no profile.

THE ZONE AND CROP MAPPINGS ARE DECLARED, and an unmapped zone raises. FAO's crops are French
and its geography is seventeen agro-ecological zones rather than provinces; a default would
silently score a province against the wrong zone.

Usage:  python3 scripts/crosscheck_fao_crop_calendar.py
Writes: outputs/fao_crop_calendar_crosscheck.csv
"""

from pkinv.assets import asset_path
import csv
import datetime
import json
import os
import sys

from pkinv.paths import DATA, OUTPUTS, ROOT
from pkinv.core.io import read_rows

FAO = asset_path(ROOT, "data", "raw", "fao_crop_calendar", "Pakistan_crop_calendar.json")
CALENDAR = asset_path(DATA, "rice_calendar.csv")
OUT = asset_path(OUTPUTS, "fao_crop_calendar_crosscheck.csv")

RICE = "Riz"

# FAO agro-ecological zone -> the province this inventory allocates rice to. Declared, because
# the two geographies are not the same kind of thing: a zone is agro-ecological and a province
# is administrative, and where a province spans zones the rice-growing one is named.
ZONE_PROVINCE = {
    "Punjab central": "Punjab",
    "Upper Sindh": "Sindh",
    "Basse Sindh": "Sindh",
    "Les zones irriguées de la NWFP (Plaines de NWFP)": "Khyber Pakhtunkhwa",
}

# How close two harvest-end weeks must be to count as agreement. Three weeks: FAO's windows are
# climatological decadal ranges and this calendar is a provincial mid-point, so demanding the
# same week would fail on precision neither source claims. Stated here rather than tuned.
AGREEMENT_WEEKS = 3

FIELDS = ("province", "fao_zone", "fao_sowing_window", "fao_harvest_window",
          "fao_harvest_end_week", "calendar_harvest_end_week", "difference_weeks",
          "agrees", "calendar_transplant_week", "compared", "provenance_outcome")


def _rows(path):
    return read_rows(path)


def _week(month, day):
    """ISO week of a month/day in a non-leap reference year - a climatology has no year."""
    return datetime.date(2021, int(month), int(day)).isocalendar()[1]


def fao_rice_windows():
    """{zone: {sowing/harvest bounds}} for rice, from FAO's own record."""
    with open(FAO, encoding="utf-8") as handle:
        records = json.load(handle)
    out = {}
    for record in records:
        if record["crop"]["name"] != RICE:
            continue
        zone = record["aez"]["name"]
        for session in record["sessions"]:
            need = ("early_sowing", "later_sowing", "early_harvest", "late_harvest")
            if not all(isinstance(session.get(k), dict) for k in need):
                continue
            out[zone] = {k: (int(session[k]["month"]), int(session[k]["day"])) for k in need}
    return out


def build():
    windows = fao_rice_windows()
    unmapped = sorted(set(ZONE_PROVINCE) - set(windows))
    if unmapped:
        raise KeyError("declared FAO zones missing from the file: %s - the mapping names a "
                       "zone the publication does not carry" % unmapped)

    calendar = {row["province"]: row for row in _rows(CALENDAR)}
    rows = []
    for zone, province in sorted(ZONE_PROVINCE.items()):
        if province not in calendar:
            raise KeyError("%s maps to province %r, which data/rice_calendar.csv does not "
                           "carry" % (zone, province))
        window = windows[zone]
        fao_end = _week(*window["late_harvest"])
        theirs = int(calendar[province]["harvest_end_week"])
        difference = fao_end - theirs
        agrees = abs(difference) <= AGREEMENT_WEEKS
        rows.append({
            "province": province, "fao_zone": zone,
            "fao_sowing_window": "%02d-%02d to %02d-%02d" % (window["early_sowing"] +
                                                            window["later_sowing"]),
            "fao_harvest_window": "%02d-%02d to %02d-%02d" % (window["early_harvest"] +
                                                             window["late_harvest"]),
            "fao_harvest_end_week": fao_end,
            "calendar_harvest_end_week": theirs,
            "difference_weeks": difference,
            "agrees": "yes" if agrees else "NO",
            "calendar_transplant_week": calendar[province]["transplant_start_week"],
            "compared": "harvest only - FAO publishes SOWING and this calendar publishes "
                        "TRANSPLANT, which are different operations",
            # NO ROW'S CLASS MOVES EITHER WAY. Agreement corroborates an endpoint the
            # profile does not read; disagreement is between two calendars of different kinds.
            "provenance_outcome": ("harvest end corroborated by FAO; class unchanged because "
                                   "the profile rides the flooded window, not the harvest"
                                   if agrees else
                                   "no agreement; the calendar keeps its values and its class"),
        })
    return rows


def main():
    rows = build()
    os.makedirs(OUTPUTS, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as handle:
        handle.write("# FAO's published rice windows against the calendar that shapes rice "
                     "methane. HARVEST ONLY: FAO publishes sowing and\n")
        handle.write("# this calendar publishes TRANSPLANT, which for rice are different "
                     "operations three to four weeks apart.\n")
        handle.write("# A DISAGREEMENT DOES NOT OVERWRITE. FAO is climatological and "
                     "zone-based; this calendar is provincial. Where they agree the\n")
        handle.write("# row gains a retrievable source; where they do not, it keeps its "
                     "values and its working-pointer provenance.\n")
        handle.write("# FAO is a CLIMATOLOGY: it can shape a season and can never date one, "
                     "so nothing here is a year-specific input.\n")
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    agreed = [r for r in rows if r["agrees"] == "yes"]
    print("FAO rice calendar cross-check -> %s" % os.path.relpath(OUT, ROOT))
    print("  %d FAO zones compared against %d provinces"
          % (len(rows), len({r["province"] for r in rows})))
    print("  %d of %d harvest windows agree within %d weeks"
          % (len(agreed), len(rows), AGREEMENT_WEEKS))
    for row in rows:
        print("    %-20s %-46s FAO wk %2d vs %2d  %s"
              % (row["province"], row["fao_zone"][:46], row["fao_harvest_end_week"],
                 row["calendar_harvest_end_week"], row["agrees"]))
    return 0


if __name__ == "__main__":
    import sys as _sys
    if "--check" in _sys.argv[1:]:
        # re-derive into a temporary directory and compare; nothing in the tree is written
        from pkinv.core.checkmode import compare_only
        _sys.exit(compare_only(globals(), ("OUT",), main))
    sys.exit(main())
