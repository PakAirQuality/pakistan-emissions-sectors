"""Extract the grid-plant geography and activity this project already holds but never read.

WHY. Two workbooks sit under sources/Power Plants/. One of them,
power_plants_data_preparation.xlsx, has ten sheets and the engine reads two: CPP_master became
data/activity/power/captive_register.csv, and Grid_power_plants set one row of
data/province_shares.csv. The other, power_plants_emissions.xlsx, is hashed in the release
manifest and READ BY NOTHING. Between them they carry the thing the power module most lacks:

    107 of 107 thermal grid plants carry a DISTRICT.
    data/activity/power/plant_coordinates.csv resolves 34.

That gap is why outputs/pakemis_air_lahore_by_year.csv carried no power row at all until rc61,
which placed the admitted fleet on the admission register's own districts; Lahore now publishes
4.842 Gg falling to 1.051. The workbook places three stations inside Lahore District - Kohinoor Energy, Japan Power and Reshma
Power, the Raiwind cluster that scripts/ingest_grid_plant_coordinates.py left `unresolved`
because rung 2b could only confirm the province.

WHAT IS TAKEN, AND WHAT IS NOT. Activity and geography are taken. The workbooks' own emission
numbers are NOT taken as estimates: their method is `Emissions(t) = activity[MWh] x EF[kg/MWh]`
on factors their own sheet describes as a "typical literature range consistent with US EPA
AP-42", and this repository computes SO2 from a sulfur balance on a dated evidence register,
which is better sourced. So the emission columns land in a CROSS-CHECK file, with the band
(Mid/Max) and the factor basis on every row, and nothing reads them as an estimate.

The workbooks are this project's own 2024 compilation, not a third-party dataset. Their README
sheets name the sources underneath: the SNGPL captive register, the SSGC geocoded list, the
NEPRA generation-CPP licence register, OGRA gas data, OCAC/PBS activity, a national thermal
inventory. So they are a derived layer over records this repository already partly ingests, and
the ingest records that rather than treating them as primary.

YEAR CONVENTION, established rather than assumed. The workbooks' `Year` is the fiscal END year:
Atlas Power Year 2020 is 259.34 GWh against this repository's FY2019-20 sum of 259.33, and Anoud
Power Year 2021 is 12.51 against FY2020-21's 12.50. Converted here, once, with the check in
tests/test_power_plant_workbooks.py.

A DEFECT THE MONTHLY SHEET CARRIES, caught rather than absorbed. Grid_monthly_generation is not
twelve clean months per plant-year. For Kohinoor Energy in Year 2019 the `June` cell holds
387.50, which is the ANNUAL total: the other eleven months sum to exactly that. Other plant-years
are short of twelve months entirely. So the monthly sheet is ingested as a CROSS-CHECK with a
per-plant-year closure against the annual sheet and a typed `reading`, and this repository's own
data/activity/power/generation_monthly.csv - twelve months in all nine fiscal years, summing
correctly - stays the monthly record.

Deterministic; --check re-derives and diffs.

Usage:  python3 scripts/ingest_power_plant_workbooks.py [--check]
Writes: data/activity/power/grid_plant_district.csv
        data/activity/power/grid_monthly_workbook.csv
        data/activity/power/workbook_emissions_crosscheck.csv
"""
import csv
import io
import os
import sys

import openpyxl

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.assets import asset_path

from pkinv.core import adm2                                              # noqa: E402

PREP = asset_path(ROOT, "sources", "Power Plants",
                    "power_plants_data_preparation.xlsx")
EMIS = asset_path(ROOT, "sources", "Power Plants", "power_plants_emissions.xlsx")
OUT_DISTRICT = asset_path(ROOT, "data", "activity", "power", "grid_plant_district.csv")
OUT_MONTHLY = asset_path(ROOT, "data", "activity", "power", "grid_monthly_workbook.csv")
OUT_CROSSCHECK = asset_path(ROOT, "data", "activity", "power",
                              "workbook_emissions_crosscheck.csv")

MONTHS = ("July", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May", "June")

DISTRICT_FIELDS = ("plant", "fiscal_year", "fiscal_end_year", "plant_type", "province",
                   "district_printed", "adm2_id", "fuel", "generation_gwh", "source_sheet",
                   "repo_coordinate", "repo_adm2_id", "geography_agreement", "note")
MONTHLY_FIELDS = ("plant", "fiscal_year", "month", "fuel", "generation_gwh",
                  "months_present", "annual_sheet_gwh", "months_sum_gwh",
                  "closure_residual_gwh", "reading")
CROSSCHECK_FIELDS = ("plant", "fiscal_year", "province", "district_printed", "adm2_id", "fuel",
                     "generation_gwh", "band", "so2_t", "nox_t", "pm10_t", "pm25_t", "co_t",
                     "factor_basis", "reading")


def fiscal(year):
    """The workbook's Year is the fiscal END year: 2016 -> FY2015-16."""
    year = int(year)
    return "FY%d-%02d" % (year - 1, year % 100)


def sheet_rows(path, name):
    book = openpyxl.load_workbook(path, read_only=True, data_only=True)
    grid = list(book[name].iter_rows(values_only=True))
    book.close()
    header = [c for c in grid[0]]
    return [dict(zip(header, r)) for r in grid[1:] if r and r[0] is not None]


def text(value):
    return "" if value is None else str(value).strip()


def number(value):
    return "" if value is None else repr(round(float(value), 6))


def repo_geography():
    """{plant: (coordinate, adm2_id)} as this repository resolves it today."""
    from pkinv.core.io import read_rows
    out = {}
    for row in read_rows(asset_path(ROOT, "data", "activity", "power",
                                      "plant_coordinates.csv")):
        coord = ""
        if row.get("latitude") and row.get("longitude"):
            coord = "%s,%s" % (row["latitude"], row["longitude"])
        resolved = row.get("adm2_id", "")
        out[row["plant"]] = (coord, "" if resolved in ("", "unresolved") else resolved)
    return out


def build_district():
    """One row per thermal plant-year, with the district resolved to a canonical adm2_id."""
    held = repo_geography()
    rows = []
    for r in sheet_rows(PREP, "Grid_power_plants"):
        printed = text(r.get("District"))
        if not printed:
            continue                     # non-thermal rows carry no district, by the sheet's own design
        adm2_id = adm2.resolve(printed)  # raises on an unknown spelling: never dropped silently
        plant = text(r.get("Plant"))
        coord, repo_adm2 = held.get(plant, ("", ""))
        if not repo_adm2 and coord:
            agreement = "workbook places it; this repository has a point but left adm2 unresolved"
        elif not repo_adm2:
            agreement = "workbook places it; this repository holds no coordinate for it"
        elif repo_adm2 == adm2_id:
            agreement = "agree"
        else:
            agreement = "CONFLICT: this repository resolves %s" % repo_adm2
        rows.append({
            "plant": plant,
            "fiscal_year": fiscal(r["Year"]),
            "fiscal_end_year": str(int(r["Year"])),
            "plant_type": text(r.get("type")),
            "province": text(r.get("State")),
            "district_printed": printed,
            "adm2_id": adm2_id,
            "fuel": text(r.get("Fuels")),
            "generation_gwh": number(r.get("GWh")),
            "source_sheet": "power_plants_data_preparation.xlsx#Grid_power_plants",
            "repo_coordinate": coord,
            "repo_adm2_id": repo_adm2,
            "geography_agreement": agreement,
            "note": "",
        })
    rows.sort(key=lambda r: (r["plant"], r["fiscal_end_year"]))
    return rows


def build_monthly(_district_rows):
    """The monthly sheet as a CROSS-CHECK, with its closure against the annual sheet typed.

    The annual side is read from the WHOLE Grid_power_plants sheet, not from the district file:
    wind and solar plants carry no district and so are absent there, and closing them against
    nothing would report a missing annual row that is not missing.
    """
    annual = {}
    for r in sheet_rows(PREP, "Grid_power_plants"):
        if r.get("GWh") is not None:
            annual[(text(r.get("Plant")), fiscal(r["Year"]))] = float(r["GWh"])
    raw = sheet_rows(PREP, "Grid_monthly_generation")
    grouped = {}
    for r in raw:
        key = (text(r.get("Plant")), fiscal(r["Year"]))
        grouped.setdefault(key, []).append(r)

    rows = []
    for (plant, period), months in sorted(grouped.items()):
        values = {text(m.get("Month")): float(m.get("Generation_GWh") or 0) for m in months}
        total = sum(values.values())
        published = annual.get((plant, period))
        # THE DEFECT: a month whose value equals the plant-year's annual total, with the other
        # eleven summing to it as well. Kohinoor Energy, FY2018-19, the June cell.
        duplicated = [name for name, v in values.items()
                      if published and abs(v - published) < 1e-6 and len(values) > 1
                      and abs((total - v) - published) < 1e-3]
        if duplicated:
            reading = ("the %s cell repeats the ANNUAL total and the other %d months sum to it "
                       "exactly; the annual figure is right and this month is not a month"
                       % (duplicated[0], len(values) - 1))
        elif len(values) < 12:
            reading = ("only %d of twelve months are present, so this plant-year cannot be "
                       "summed to a year here" % len(values))
        elif published is None:
            reading = "no annual row on the other sheet to close against"
        elif abs(total - published) < 1e-3:
            reading = "twelve months, closing on the annual sheet"
        else:
            reading = ("twelve months that do NOT close on the annual sheet; the difference is "
                       "carried, never absorbed")
        for name in sorted(values, key=lambda n: MONTHS.index(n) if n in MONTHS else 99):
            rows.append({
                "plant": plant, "fiscal_year": period, "month": name,
                "fuel": text(months[0].get("Fuel")),
                "generation_gwh": number(values[name]),
                "months_present": str(len(values)),
                "annual_sheet_gwh": "" if published is None else repr(round(published, 6)),
                "months_sum_gwh": repr(round(total, 6)),
                "closure_residual_gwh": ("" if published is None
                                         else repr(round(total - published, 6))),
                "reading": reading,
            })
    return rows


def build_crosscheck():
    """The workbook's own emissions, held as a comparison and never as an estimate."""
    factors = {}
    for r in sheet_rows(EMIS, "Emission_factors"):
        if text(r.get("Pollutant")) == "SO2":
            factors[text(r.get("Fuel Type"))] = (r.get("Min"), r.get("Mid"), r.get("Max"),
                                                 text(r.get("Source")), text(r.get("Notes")))
    rows = []
    for r in sheet_rows(EMIS, "Grid_emissions_calc"):
        printed = text(r.get("District"))
        fuel = text(r.get("Fuel"))
        band = text(r.get("band"))
        low, mid, high, source, notes = factors.get(fuel, (None, None, None, "", ""))
        chosen = {"Min": low, "Mid": mid, "Max": high}.get(band)
        basis = ("%s kg/MWh (%s band) - %s" % (chosen, band, source)) if chosen is not None else ""
        if fuel.upper() == "BAGASSE":
            reading = ("NOT USABLE for SO2: the workbook's own factor sheet marks the bagasse "
                       "value an UNSOURCED PLACEHOLDER of 0.0")
        else:
            reading = ("a literature kg/MWh factor, not a sulfur balance on Pakistani fuel; held "
                       "to be compared against this repository's own estimate, never adopted")
        rows.append({
            "plant": text(r.get("Plant")),
            "fiscal_year": fiscal(r["Year"]),
            "province": text(r.get("State")),
            "district_printed": printed,
            "adm2_id": adm2.resolve(printed) if printed else "",
            "fuel": fuel, "generation_gwh": number(r.get("GWh")), "band": band,
            "so2_t": number(r.get("SO2_t")), "nox_t": number(r.get("NOx_t")),
            "pm10_t": number(r.get("PM10_t")), "pm25_t": number(r.get("PM2.5_t")),
            "co_t": number(r.get("CO_t")),
            "factor_basis": basis, "reading": reading,
        })
    rows.sort(key=lambda r: (r["plant"], r["fiscal_year"], r["band"]))
    return rows


BANNERS = {
    OUT_DISTRICT: (
        "# GRID POWER PLANTS, PLACED IN A DISTRICT. One row per thermal plant-year from\n"
        "# sources/Power Plants/power_plants_data_preparation.xlsx sheet Grid_power_plants, whose\n"
        "# Year is the fiscal END year (established against this repository's own monthly sums, not\n"
        "# assumed). district_printed is the sheet's spelling; adm2_id is that name resolved through\n"
        "# data/adm2_canonical.csv, and a spelling that resolves nowhere RAISES rather than dropping\n"
        "# a plant. geography_agreement compares the placement against plant_coordinates.csv, which\n"
        "# resolves 34 plants where this sheet places 107. The workbook is this project's own 2024\n"
        "# compilation over NEPRA/OGRA/SNGPL/SSGC/OCAC records, not a third-party dataset; its\n"
        "# coordinates are factory footprints to town centroids by its own README, not surveyed\n"
        "# stacks. Activity and geography only - the workbook's emission columns are held apart in\n"
        "# workbook_emissions_crosscheck.csv. scripts/ingest_power_plant_workbooks.py\n"),
    OUT_MONTHLY: (
        "# THE WORKBOOK'S MONTHLY GENERATION, AS A CROSS-CHECK ONLY. Grid_monthly_generation covers\n"
        "# fiscal end years 2018-2024 and is NOT twelve clean months per plant-year: some plant-years\n"
        "# are short, and at least one repeats the ANNUAL total inside a month cell (Kohinoor Energy\n"
        "# FY2018-19, the June cell, with the other eleven months summing to exactly that). Every row\n"
        "# therefore carries its plant-year's month count, the annual sheet's figure, the months' sum\n"
        "# and the residual, with a typed reading. This repository's own\n"
        "# data/activity/power/generation_monthly.csv - twelve months in all nine fiscal years -\n"
        "# stays the monthly record. scripts/ingest_power_plant_workbooks.py\n"),
    OUT_CROSSCHECK: (
        "# THE WORKBOOK'S OWN EMISSION NUMBERS, HELD TO BE COMPARED AND NEVER ADOPTED. Method, from\n"
        "# its README: Emissions(t) = activity[MWh] x EF[kg/MWh] / 1000, on factors its own sheet\n"
        "# calls a 'typical literature range consistent with US EPA AP-42', with MODERN units on the\n"
        "# Mid band and TRADITIONAL units (old GENCO plus FO/RFO/HSD steam) on Max. This repository\n"
        "# computes SO2 from a sulfur balance on a dated evidence register instead, which is better\n"
        "# sourced, so these columns are evidence about where two methods part. The workbook's\n"
        "# bagasse SO2 factor is an UNSOURCED PLACEHOLDER of 0.0 by its own admission and is typed as\n"
        "# such per row. scripts/ingest_power_plant_workbooks.py\n"),
}


def render(path, fields, rows):
    out = io.StringIO()
    out.write(BANNERS[path])
    writer = csv.DictWriter(out, fieldnames=list(fields), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def main(check=False):
    district = build_district()
    products = ((OUT_DISTRICT, DISTRICT_FIELDS, district),
                (OUT_MONTHLY, MONTHLY_FIELDS, build_monthly(district)),
                (OUT_CROSSCHECK, CROSSCHECK_FIELDS, build_crosscheck()))
    stale = []
    for path, fields, rows in products:
        body = render(path, fields, rows)
        if check:
            if not os.path.exists(path) or open(path, encoding="utf-8").read() != body:
                stale.append(os.path.relpath(path, ROOT))
            continue
        open(path, "w", encoding="utf-8").write(body)
        print("wrote %s: %d rows" % (os.path.relpath(path, ROOT), len(rows)))
    if check:
        if stale:
            print("stale; run python3 scripts/ingest_power_plant_workbooks.py:\n  %s"
                  % "\n  ".join(stale))
            return 1
        print("the power-plant workbook ingests are current.")
        return 0
    placed = {r["adm2_id"] for r in district}
    lahore = sorted({r["plant"] for r in district if r["adm2_id"] == "punjab_lahore"})
    print("  %d districts carry a thermal plant; Lahore District: %s"
          % (len(placed), ", ".join(lahore) or "none"))
    return 0


if __name__ == "__main__":
    from pkinv.activity.store import staging_inputs
    with staging_inputs():
        raise SystemExit(main(check="--check" in sys.argv))
