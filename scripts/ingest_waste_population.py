"""Ingest the district population panel that drives the open-waste-burning sector.

Source workbook: Domestic.xlsx in the pakistan-emissions-sectors repository, sheet
`Interpolated` — a gapless 133-district x 2000-2023 panel of total / rural / urban
population, built from the 6th (2017) and 7th (2023) Population and Housing Censuses
with geometric interpolation between the two anchors.

We deliberately ingest POPULATION, not the workbook's `Waste Burned (kg/year)` column.
That column embeds four undocumented constants inline in a formula repeated 3,192 times
(0.35 / 0.55 kg/cap/day generation, 0.50 / 0.20 burned fractions) with no label, unit or
source anywhere in the workbook. The burn calculation belongs in the engine, driven by
cited parameters in data/waste_params.csv, so it can be reviewed and varied.

Three normalisations happen here, all recorded rather than silently applied:
  * province `KP` -> `Khyber Pakhtunkhwa` (the engine's vocabulary)
  * district names -> the engine's district list, via district_aliases.csv
  * Islamabad Capital Territory added as province `Other`

Usage:  python3 scripts/ingest_waste_population.py [path/to/Domestic.xlsx]
Writes: data/activity/waste/population_district.csv
"""

from pkinv.assets import asset_path
import csv
import os
import sys

import openpyxl

from pkinv.paths import ROOT, DATA

DEFAULT_SRC = asset_path(ROOT, "sources", "Domestic.xlsx")   # rc37: the held workbook
OUT_DIR = asset_path(DATA, "activity", "waste")
OUT = asset_path(OUT_DIR, "population_district.csv")
ALIASES = asset_path(OUT_DIR, "district_aliases.csv")

PROVINCE_FIX = {"KP": "Khyber Pakhtunkhwa"}

# Islamabad Capital Territory is absent from the workbook, which covers only the four
# provinces. ICT is the whole of the engine's "Other" province that the 7th Census counts:
# Azad Jammu & Kashmir and Gilgit-Baltistan are separately administered and are outside the
# 2023 census frame entirely, so they cannot be added from the same source.
# 2023 total from the 7th Census; the urban share is the 6th Census (2017) ratio
# 1,009,832 / 2,003,368 held constant, which is the assumption to revisit first.
ICT_2023_POP = 2363863
ICT_URBAN_SHARE = 1009832.0 / 2003368.0
ICT_GROWTH = (2363863.0 / 2003368.0) ** (1.0 / 6.0)   # 2017 -> 2023 CAGR, applied both ways


def _aliases():
    return {r["source_name"]: r["engine_district"] for r in read_rows(ALIASES, comments=False)}


# The engine's district-name normaliser now lives in one place.
from pkinv.core.adm2 import normalise as _norm  # noqa: E402
from pkinv.core.io import read_rows


def _canonical():
    """Engine district names, keyed by their normalised form.

    Most workbook names differ from the engine's only by a ' District' suffix, so they
    resolve here; district_aliases.csv covers the 20 that differ by spelling, word order
    or abbreviation. Resolving to canonical names at ingest means nothing downstream has
    to normalise, and an unresolvable name fails loudly here rather than silently
    dropping a district out of a join later.
    """
    path = asset_path(DATA, "activity", "livestock_district_2024.csv")
    return {_norm(r["district"]): r["district"] for r in read_rows(path, comments=False)}


def main(src=DEFAULT_SRC):
    alias = _aliases()
    canon = _canonical()
    wb = openpyxl.load_workbook(src, data_only=True)
    rows, unresolved = [], set()
    for r in wb["Interpolated"].iter_rows(min_row=2, values_only=True):
        if not r or r[2] is None:
            continue
        province, district, year, total, rural, urban = r[0], str(r[1]).strip(), int(r[2]), r[3], r[4], r[5]
        name = alias.get(district, district)
        name = canon.get(_norm(name), name)
        if _norm(name) not in canon:
            unresolved.add(district)
        rows.append({
            "province": PROVINCE_FIX.get(province, province),
            "district": name,
            "year": year,
            "pop_total": round(float(total), 1),
            "pop_rural": round(float(rural), 1),
            "pop_urban": round(float(urban), 1),
            "source": "PBS 6th (2017) + 7th (2023) Population and Housing Census, interpolated",
        })

    years = sorted({r["year"] for r in rows})
    for y in years:
        pop = ICT_2023_POP * (ICT_GROWTH ** (y - 2023))
        urban = pop * ICT_URBAN_SHARE
        rows.append({
            "province": "Other", "district": "Islamabad District", "year": y,
            "pop_total": round(pop, 1), "pop_rural": round(pop - urban, 1),
            "pop_urban": round(urban, 1),
            "source": "PBS 7th Census 2023 ICT total; 2017 urban share held constant (extrapolated)",
        })

    rows.sort(key=lambda r: (r["province"], r["district"], r["year"]))
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["province", "district", "year", "pop_total",
                                          "pop_rural", "pop_urban", "source"])
        w.writeheader()
        w.writerows(rows)

    if unresolved:
        raise SystemExit("districts not in the engine's list and not aliased: %s\n"
                         "Add them to %s." % (sorted(unresolved), ALIASES))

    districts = {r["district"] for r in rows}
    latest = [r for r in rows if r["year"] == max(years)]
    print("wrote %s" % os.path.relpath(OUT, os.path.dirname(os.path.dirname(OUT_DIR))))
    print("  %d rows | %d districts | %d-%d" % (len(rows), len(districts), min(years), max(years)))
    print("  %d population %.1fM (rural %.1fM, urban %.1fM)"
          % (max(years), sum(r["pop_total"] for r in latest) / 1e6,
             sum(r["pop_rural"] for r in latest) / 1e6,
             sum(r["pop_urban"] for r in latest) / 1e6))


if __name__ == "__main__":
    from pkinv.activity.store import staging_inputs
    with staging_inputs():
        main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SRC)
