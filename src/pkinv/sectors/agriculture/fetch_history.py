"""Build Pakistan historical activity-data CSVs (1961-latest) from FAOSTAT bulks.

Reads the QCL (crops & livestock), RFN (fertiliser by nutrient) and Emissions Totals
normalized bulks held under data/raw/faostat/, streams them from the zip (no full
extraction), filters Pakistan, and writes compact time-series CSVs under
data/activity/historical/.

THE BULKS ARE HELD DOCUMENTS (October 2026). They used to be downloaded to a gitignored
cache, which is why the register said "no byte-stable file ever existed to hash" while the
files sat on the maintainer's disk. A bulk that is not held is downloaded and kept
(pkinv.core.retention); a held one is never replaced, because FAOSTAT revises its bulks and
the tables here were read from these bytes.

--check re-derives the four tables from the held bulks and compares; it writes none.

Usage:  python3 -m pkinv.sectors.agriculture.fetch_history [--check]
"""

from pkinv.assets import asset_path
import csv
import io
import os
import sys
import zipfile

from pkinv.core import retention
from pkinv.paths import ROOT, DATA

HIST = asset_path(DATA, "activity", "historical")

QCL_URL = ("https://bulks-faostat.fao.org/production/"
           "Production_Crops_Livestock_E_All_Data_(Normalized).zip")
RFN_URL = ("https://bulks-faostat.fao.org/production/"
           "Inputs_FertilizersNutrient_E_All_Data_(Normalized).zip")
EMIS_URL = ("https://bulks-faostat.fao.org/production/"
            "Emissions_Totals_E_All_Data_(Normalized).zip")

# FAOSTAT Emissions item -> engine category bucket (element "Emissions (CO2eq) (AR5)")
EMIS_ITEMS = {"Enteric Fermentation": "Enteric fermentation",
              "Manure Management": "Manure management",
              "Rice Cultivation": "Rice cultivation",
              "Synthetic Fertilizers": "Managed soils",
              "Manure applied to Soils": "Managed soils",
              "Manure left on Pasture": "Managed soils",
              "Crop Residues": "Managed soils",
              "Burning - Crop residues": "Field burning of residues"}

# FAOSTAT item name -> engine species (element "Stocks")
LIVESTOCK = {"Cattle": "cattle", "Buffalo": "buffalo", "Sheep": "sheep",
             "Goats": "goats", "Camels": "camels", "Chickens": "poultry"}
# FAOSTAT item name -> engine crop
CROPS = {"Rice": "rice", "Wheat": "wheat", "Maize (corn)": "maize",
         "Sugar cane": "sugarcane", "Seed cotton; unginned": "cotton"}


def _download(url, name=None):
    """The held bulk for `url`, downloading and keeping it only if it is not held."""
    held = "faostat_" + url.rsplit("/", 1)[1]
    path = os.path.join(retention.RAW, "faostat", held)
    if not os.path.exists(path):
        print("  downloading %s ..." % held)
        path = retention.fetch_and_keep(url, "faostat", held, timeout=300)
    return path


_differences = []


def _emit(name, header, rows, check):
    text = io.StringIO()
    w = csv.writer(text)
    w.writerow(header)
    w.writerows(rows)
    path = asset_path(HIST, name)
    if check:
        _differences.append(retention.report_check("FAOSTAT " + name, path, text.getvalue()))
        return
    with open(path, "w", newline="") as f:
        f.write(text.getvalue())


def _rows(zip_path):
    z = zipfile.ZipFile(zip_path)
    name = [n for n in z.namelist() if n.endswith("(Normalized).csv")][0]
    with z.open(name) as fb:
        r = csv.reader(io.TextIOWrapper(fb, encoding="latin-1"))
        hdr = next(r)
        ci = {k: i for i, k in enumerate(hdr)}
        for row in r:
            yield row, ci


def build(check=False):
    os.makedirs(HIST, exist_ok=True)
    qcl = _download(QCL_URL, "QCL.zip")
    rfn = _download(RFN_URL, "RFN.zip")

    livestock = {}   # year -> {species: head}
    crops = {}       # (year, crop) -> {area_ha, production_t}
    print("  parsing QCL (Pakistan rows)...")
    for row, ci in _rows(qcl):
        if row[ci["Area"]] != "Pakistan":
            continue
        item, elem = row[ci["Item"]], row[ci["Element"]]
        val = row[ci["Value"]]
        if not val:
            continue
        year = int(row[ci["Year"]])
        if item in LIVESTOCK and elem == "Stocks":
            v = float(val)
            if row[ci["Unit"]].startswith("1000"):
                v *= 1000.0
            livestock.setdefault(year, {})[LIVESTOCK[item]] = v
        elif item in CROPS and elem in ("Production", "Area harvested"):
            d = crops.setdefault((year, CROPS[item]), {})
            d["production_t" if elem == "Production" else "area_ha"] = float(val)

    nitrogen = {}    # year -> tonnes N
    print("  parsing RFN (Pakistan N)...")
    for row, ci in _rows(rfn):
        if row[ci["Area"]] != "Pakistan":
            continue
        if row[ci["Item"]] == "Nutrient nitrogen N (total)" \
                and row[ci["Element"]] == "Agricultural Use" and row[ci["Value"]]:
            nitrogen[int(row[ci["Year"]])] = float(row[ci["Value"]])

    # FAOSTAT's own emission series (AR5 CO2eq) per category, for validation
    emis = _download(EMIS_URL, "Emissions_Totals.zip")
    # dedup per (year, item) first - FAOSTAT has multiple Source rows per item-year that
    # must NOT be summed; then map items to category buckets.
    per_item = {}    # (year, item) -> Mt CO2e (single value)
    print("  parsing FAOSTAT emissions (Pakistan AR5)...")
    for row, ci in _rows(emis):
        if row[ci["Area"]] != "Pakistan" or row[ci["Element Code"]] != "723113":
            continue
        item = row[ci["Item"]]
        if item in EMIS_ITEMS and row[ci["Value"]]:
            per_item[(int(row[ci["Year"]]), item)] = float(row[ci["Value"]]) / 1000.0
    faostat = {}     # year -> {category: Mt CO2e}
    for (y, item), v in per_item.items():
        faostat.setdefault(y, {}).setdefault(EMIS_ITEMS[item], 0.0)
        faostat[y][EMIS_ITEMS[item]] += v

    _write_livestock(livestock, check)
    _write_crops(crops, check)
    _write_nitrogen(nitrogen, check)
    _write_faostat(faostat, check)
    if check:
        return max(_differences)
    yrs = sorted(set(livestock) & set(nitrogen))
    print("  wrote historical CSVs; livestock %d-%d, N %d-%d, overlap %d-%d"
          % (min(livestock), max(livestock), min(nitrogen), max(nitrogen),
             yrs[0], yrs[-1]))


def _write_faostat(faostat, check=False):
    # "Urea application" has no FAOSTAT GT item -> column of 0 (validation reports n/a)
    cats = ["Enteric fermentation", "Manure management", "Rice cultivation", "Managed soils",
            "Field burning of residues", "Urea application"]
    _emit("faostat_emissions.csv", ["year"] + cats,
          [[y] + [round(faostat[y].get(c, 0.0), 3) for c in cats] for y in sorted(faostat)],
          check)


def _write_livestock(livestock, check=False):
    species = ["cattle", "buffalo", "sheep", "goats", "camels", "poultry"]
    _emit("livestock_stocks.csv", ["year"] + species,
          [[y] + [int(livestock[y].get(s, 0)) for s in species] for y in sorted(livestock)],
          check)


def _write_crops(crops, check=False):
    _emit("crops.csv", ["year", "crop", "area_ha", "production_t"],
          [[y, crop, crops[(y, crop)].get("area_ha", ""),
            crops[(y, crop)].get("production_t", "")] for (y, crop) in sorted(crops)], check)


def _write_nitrogen(nitrogen, check=False):
    _emit("fertilizer_n.csv", ["year", "n_tonnes"],
          [[y, int(nitrogen[y])] for y in sorted(nitrogen)], check)


if __name__ == "__main__":
    sys.exit(build(check="--check" in sys.argv[1:]) or 0)
