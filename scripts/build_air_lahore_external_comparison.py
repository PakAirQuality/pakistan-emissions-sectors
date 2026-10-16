"""LAHORE'S SO2 AGAINST EDGAR v8.1 - two compilations at one district, never a calibration.

WHY. The release publishes Lahore District SO2 falling 63.95 % across nine fiscal years, 27.298 to
9.842 Gg. The figure is restated whenever it moves rather than left to describe a superseded
engine: it read 54 % when this file was written, 59.75 % once main-activity power was admitted
and industrial furnace oil got its own product geography, and 63.95 % once the sulfur evidence
was adopted at rc63 - the last of those steepened the curve without changing any stream's own
trend, purely by re-weighting the total toward power, which falls faster than it does. The companion table
outputs/pakemis_air_lahore_so2_attribution.csv shows what that curve is made of: two national fuel
series spread onto Lahore by patterns that BARELY move - furnace oil now carries its own observed
province shares for three of the nine years and brick coal still carries none - plus one declared
fuel-specification step. Lahore's brick SO2 is exactly HDIP's national brick-coal column times the single constant
0.001014126. Nothing inside this repository can test a claim like that, because every part of it is
this repository's own choice. EDGAR resolves 0.1 degree cells - about four across Lahore - and builds
them from its own proxies.

THE CROSSWALK, AND THE ERROR IT CORRECTS. An earlier version of this product compared our brick-kiln
stream against EDGAR's NMM grid and reported that EDGAR books no brick at Lahore. That was wrong.
NMM is IPCC 2.A.1, mineral-production PROCESS emissions; kiln FUEL is combustion and belongs to
1.A.2, which is EDGAR's IND grid. The finding built on it is withdrawn.

The crosswalk is therefore a checked table rather than a reading of labels, and the check is
arithmetic: the IND grid summed over Pakistan must reproduce EDGAR's OWN published 1.A.2 country
total, and NMM must reproduce 2.A.1. Those rows are in this product with scope=pakistan, and a test
holds them at 1.0. A polygon summation that cannot reproduce EDGAR's national figure says nothing
about a district.

EVERY SECTOR IS FETCHED, so no sector is read by leftover and TOTALS decomposes completely.

WHAT IS COMPARED. EDGAR's gridded SO2, in tonnes per cell, summed over the same census-district
polygon the release uses (geoBoundaries shape 60131773B12131197496886), with boundary cells split by
EXACT area fraction in an equal-area projection. EDGAR is calendar-year; it is put on our fiscal
years by the blend this repository already uses, 0.5 x CY(Y-1) + 0.5 x CY(Y). That is an
approximation and it is labelled one: eight calendar years are not eight July-June years. Where the
monthly grids are held the exact fiscal year is computed beside the blend.

WHAT IS NOT COMPARED, and why the absence is a row rather than a silence: CEDS is 0.5 degree,
wider than the district. Public CAMS and HTAP downloads exist; this district comparison has
not acquired their SO2 grids. The held public HTAP NH3 country/month bundle instead supports
the separate matched national evaluation. The Urban Unit's underlying Lahore data is not held.

COMPARED, NEVER FITTED. Nothing here is read back into any register. A test hashes the five
registers, runs this script, and hashes them again.
"""

from pkinv.assets import asset_path
import collections
import csv
import glob
import os
import zipfile

from pkinv.core.io import read_rows
from pkinv.core import configurations as conf
from pkinv.core.reporting_window import CORE_FY_STARTS, CORE_FY_ENDS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRIDMAPS = asset_path(ROOT, "data", "raw", "edgar", "gridmaps")
OUT = asset_path(ROOT, "outputs", "pakemis_air_lahore_external_comparison.csv")
# a REGENERABLE INTERMEDIATE, and it lives in build/ for that reason: it is derived from
# PAK_ADM2.geojson in a minute and it is not an input anyone needs shipped, so putting it
# under data/ would have added a file to the deposit that a fresh clone does not have
CACHE = asset_path(ROOT, "build", "edgar_0p1_lahore_weights.csv")
SHAPE_ID = "60131773B12131197496886"
ADM2_ID = "punjab_lahore"
CFG = conf.REFERENCE
EQUAL_AREA = "ESRI:54034"          # World Cylindrical Equal Area, as build_adm2_intersections uses
# (edgar_stream, ipcc_code, our sector or None, words). The third column is the ONLY place a
# comparison pair is declared; a stream with None has no like-for-like row on our side and is shown
# for the shape of EDGAR's Lahore series, never as a ratio.
CROSSWALK = (
    ("IND", "1.A.2", "industry", "combustion for manufacturing - kiln and boiler FUEL"),
    ("NMM", "2.A.1", "ippu", "non-metallic mineral PROCESS emissions, not fuel"),
    ("ENE", "1.A.1.a", "power", "power industry"),
    ("TRO", "1.A.3.b", "transport", "road transport"),
    ("RCO", "1.A.4", "residential", "residential and commercial"),
    ("PRO_FFF", "1.B", "fugitives", "fuel exploitation"),
    ("AWB", "3.F", "agriculture", "agricultural waste burning"),
    ("SWD_INC", "4.C", "waste", "waste incineration"),
    ("TNR_Aviation_LTO", "1.A.3.a", "aviation", "aviation landing and take-off"),
    ("REF_TRF", "1.A.1.b", None, "refineries and other transformation"),
    ("CHE", "2.B", None, "chemical process"),
    ("IRO", "2.C.1", None, "iron and steel process"),
    ("NFE", "2.C", None, "non-ferrous process"),
    ("FOO_PAP", "1.A.2", None, "food, paper and wood, inside 1.A.2"),
    ("TNR_Other", "1.A.5", None, "other non-road transport"),
    ("TNR_Ship", "1.A.3.d", None, "shipping"),
    ("TNR_Aviation_CDS", "1.A.3.a", None, "aviation climb and descent"),
    ("TNR_Aviation_CRS", "1.A.3.a", None, "aviation cruise"),
    # TNR_Aviation_SPS is not here: EDGAR publishes no supersonic SO2 in any year of the window
)
STREAMS = ("TOTALS",) + tuple(row[0] for row in CROSSWALK)
STREAM_WORDS = {row[0]: row[3] for row in CROSSWALK}
STREAM_WORDS["TOTALS"] = "every EDGAR sector"
OUR_SECTOR = {row[0]: row[2] for row in CROSSWALK}
IPCC_OF = {row[0]: row[1] for row in CROSSWALK}
# the country x sector workbook this repository holds covers only these categories, so only these
# can be checked against EDGAR's own published national total
# (edgar streams that make up the category, ipcc code, fossil/bio parts the workbook prints)
SELF_CHECK = (
    (("IND",), "1.A.2", ("fossil", "bio")),
    (("NMM",), "2.A.1", ("fossil",)),
    (("CHE",), "2.B", ("fossil",)),
    (("IRO", "NFE"), "2.C", ("fossil",)),
)
YEARS = tuple(range(2015, 2023))
PERIODS = tuple("FY%d-%02d" % (y, (y + 1) % 100) for y in CORE_FY_STARTS)
COLUMNS = ("period_id", "calendar_year", "row_kind", "calendar_basis", "scope",
           "edgar_stream", "engine_Gg", "edgar_Gg", "ratio_engine_over_edgar", "engine_basis",
           "edgar_basis", "reading")


def path(*parts):
    return asset_path(ROOT, *parts)


# ---------------------------------------------------------------- the polygon weights

def build_weights():
    """{(row, col): fraction inside Lahore} and the same for Pakistan, on EDGAR's 0.1 lattice.

    Cached, because it is the slow half and it cannot change unless the boundary file does.
    """
    if os.path.exists(CACHE):
        lahore, pakistan = {}, {}
        for r in read_rows(CACHE):
            key = (int(r["row"]), int(r["col"]))
            if float(r["lahore_fraction"]):
                lahore[key] = float(r["lahore_fraction"])
            if float(r["pakistan_fraction"]):
                pakistan[key] = float(r["pakistan_fraction"])
        return lahore, pakistan

    import geopandas as gpd
    from shapely.geometry import box
    from pkinv.core.gis.grid import ADM2_PATH

    gdf = gpd.read_file(ADM2_PATH).to_crs("EPSG:4326")
    id_field = "shapeID" if "shapeID" in gdf.columns else "ADM2_NAME"
    lahore_geom = gdf[gdf[id_field] == SHAPE_ID].to_crs(EQUAL_AREA).geometry.union_all()
    pakistan_geom = gdf.to_crs(EQUAL_AREA).geometry.union_all()

    # EDGAR: 3600 x 1800, centres at -179.95 + 0.1 c and 89.95 - 0.1 r (row zero NORTH after the
    # flip applied when the array is read; here we index by the file's own ascending latitude)
    west, south = 60.0, 23.0
    east, north = 78.5, 37.5
    rows = []
    c0, c1 = int((west + 180.0) / 0.1), int((east + 180.0) / 0.1)
    r0, r1 = int((south + 90.0) / 0.1), int((north + 90.0) / 0.1)
    for r in range(r0, r1):
        for c in range(c0, c1):
            lon0, lat0 = -180.0 + 0.1 * c, -90.0 + 0.1 * r
            cell = gpd.GeoSeries([box(lon0, lat0, lon0 + 0.1, lat0 + 0.1)],
                                 crs="EPSG:4326").to_crs(EQUAL_AREA)[0]
            area = cell.area
            f_lah = cell.intersection(lahore_geom).area / area
            f_pak = cell.intersection(pakistan_geom).area / area
            if f_lah > 1e-12 or f_pak > 1e-12:
                rows.append({"row": r, "col": c, "lon_west": round(lon0, 4),
                             "lat_south": round(lat0, 4),
                             "lahore_fraction": round(f_lah, 12),
                             "pakistan_fraction": round(f_pak, 12)})
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    with open(CACHE, "w", encoding="utf-8", newline="") as handle:
        handle.write("# EDGAR 0.1 degree cell x polygon AREA FRACTIONS for the Lahore comparison,\n"
                     "# computed in %s exactly as scripts/build_adm2_intersections.py does for our\n"
                     "# own 0.05 degree lattice. row/col index EDGAR's own global array with\n"
                     "# ascending latitude and longitude from -90/-180. Cached because it cannot\n"
                     "# change unless the boundary file does.\n" % EQUAL_AREA)
        writer = csv.DictWriter(handle, fieldnames=("row", "col", "lon_west", "lat_south",
                                                    "lahore_fraction", "pakistan_fraction"),
                                lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return build_weights()


# ---------------------------------------------------------------- EDGAR

def gridmap_tonnes(stream, year, lahore_w, pakistan_w):
    """(lahore_tonnes, pakistan_tonnes) for one EDGAR annual gridmap."""
    import netCDF4
    import numpy as np

    name = "v8.1_FT2022_AP_SO2_%d_%s_emi_nc.zip" % (year, stream)
    archive = asset_path(GRIDMAPS, name)
    with zipfile.ZipFile(archive) as zf:
        member = [n for n in zf.namelist() if n.endswith(".nc")][0]
        with zf.open(member) as handle:
            data = netCDF4.Dataset("inmemory", memory=handle.read())
            emissions = np.asarray(data.variables["emissions"][:])
            lats = np.asarray(data.variables["lat"][:])
            lons = np.asarray(data.variables["lon"][:])
    # index by the file's own axes rather than assuming their direction
    lat_index = {round((v + 90.0 - 0.05) / 0.1): i for i, v in enumerate(lats)}
    lon_index = {round((v + 180.0 - 0.05) / 0.1): i for i, v in enumerate(lons)}

    def total(weights):
        out = 0.0
        for (r, c), frac in weights.items():
            i, j = lat_index.get(r), lon_index.get(c)
            if i is None or j is None:
                continue
            out += float(emissions[i, j]) * frac
        return out

    return total(lahore_w), total(pakistan_w)


MONTHLY_DIR = asset_path(ROOT, "data", "raw", "edgar", "gridmaps_monthly")
# the monthly bulk groupings are BROADER than the annual sector codes. That is the point of
# reading them: if bkl_POWER_INDUSTRY does not equal ENE, the difference is autoproducers, and
# this release books captive self-generation under 1.A.2 rather than power.
MONTHLY_GROUPING = {"bkl_POWER_INDUSTRY": "ENE", "bkl_IND_COMBUSTION": "IND"}


def monthly_tonnes(grouping, lahore_w, pakistan_w):
    """{(year, month): (lahore_Gg, pakistan_Gg)} from a monthly bulk archive, or None if absent.

    The archive holds one NetCDF per YEAR with a time dimension of twelve, `emissions(time, lat,
    lon)` in tonnes, so a month is a slice rather than a file. Only the years the fiscal window
    needs are opened.
    """
    import re
    import netCDF4
    import numpy as np

    archive = asset_path(MONTHLY_DIR, "%s_emi_nc.zip" % grouping)
    if not os.path.exists(archive):
        return None
    out = {}
    with zipfile.ZipFile(archive) as zf:
        for member in zf.namelist():
            if not member.endswith(".nc"):
                continue
            found = re.search(r"_SO2_(\d{4})_", os.path.basename(member))
            if not found or not 2015 <= int(found.group(1)) <= 2022:
                continue
            year = int(found.group(1))
            with zf.open(member) as handle:
                data = netCDF4.Dataset("inmemory", memory=handle.read())
                emissions = np.asarray(data.variables["emissions"][:])
                lats = np.asarray(data.variables["lat"][:])
                lons = np.asarray(data.variables["lon"][:])
            if emissions.ndim != 3 or emissions.shape[0] != 12:
                raise ValueError("%s: expected twelve monthly slices, got shape %s"
                                 % (member, emissions.shape))
            lat_index = {round((v + 90.0 - 0.05) / 0.1): i for i, v in enumerate(lats)}
            lon_index = {round((v + 180.0 - 0.05) / 0.1): i for i, v in enumerate(lons)}
            cells = [(lat_index.get(r), lon_index.get(c), f)
                     for (r, c), f in lahore_w.items()]
            pak_cells = [(lat_index.get(r), lon_index.get(c), f)
                         for (r, c), f in pakistan_w.items()]
            for month in range(1, 13):
                plane = emissions[month - 1]
                lah = sum(float(plane[i, j]) * f for i, j, f in cells
                          if i is not None and j is not None)
                pak = sum(float(plane[i, j]) * f for i, j, f in pak_cells
                          if i is not None and j is not None)
                out[(year, month)] = (lah / 1000.0, pak / 1000.0)
    return out or None


def fiscal_exact(by_month, fy_end, which):
    """July(fy_end-1) .. June(fy_end), summed. None when a month is missing."""
    months = [(fy_end - 1, m) for m in range(7, 13)] + [(fy_end, m) for m in range(1, 7)]
    if any(k not in by_month for k in months):
        return None
    return sum(by_month[k][which] for k in months)


def blend(by_year, fy_end):
    """0.5 x CY(Y-1) + 0.5 x CY(Y) for FY(Y-1)/Y - the convention this repository already uses."""
    a, b = by_year.get(fy_end - 1), by_year.get(fy_end)
    if a is None or b is None:
        return None
    return 0.5 * a + 0.5 * b


# ---------------------------------------------------------------- ours

def engine_lahore():
    """Lahore District SO2 by period and by sector, Gg, from the shipped district view."""
    total = collections.defaultdict(float)
    by_sector = collections.defaultdict(float)
    for r in read_rows(path("outputs", "pakemis_air_lahore_by_year.csv")):
        if r["pollutant"] != "SO2" or r["configuration_id"] != CFG or r["row_kind"] != "district":
            continue
        total[r["period_id"]] += float(r["emissions_Gg"])
        by_sector[(r["period_id"], r["sector_id"])] += float(r["emissions_Gg"])
    return total, by_sector


def edgar_published_national():
    """EDGAR's OWN Pakistan SO2 by IPCC category and calendar year, from the country x sector
    workbook this repository already holds - the yardstick the polygon summation must reproduce.

    The pairing is LIKE FOR LIKE: the IND gridmap is IPCC 1.A.2 (fossil and bio together, as the
    grid does not separate them) and the NMM gridmap is 2.A.1. A ratio near 1.0 says the summation
    reads the grid correctly, in the right units, over the right country.
    """
    out = collections.defaultdict(dict)
    for r in read_rows(path("data", "activity", "industry",
                            "edgar_pak_industry_ap_series.csv")):
        if r["species"] == "SO2":
            out[(r["ipcc_code_2006"], r["fossil_bio"])][int(r["calendar_year"])] = \
                float(r["emissions_Gg"])
    return out


# ---------------------------------------------------------------- the product

def band(ratio):
    if ratio is None:
        return ""
    if 0.5 <= ratio <= 2.0:
        return "within a factor of two"
    return "above a factor of two" if ratio > 2.0 else "below a factor of two"


BANNER = """\
# LAHORE DISTRICT SO2 AGAINST EDGAR v8.1, MATCHED YEARS - a comparison of two compilations, never a
# calibration: nothing in the registers is read back from this table (a test holds them byte-identical
# across a run of the builder). engine = the release's own ADM2 allocation for the census district
# punjab_lahore (geoBoundaries shape 60131773B12131197496886), Gg SO2, configuration S_TAN.
# edgar = the v8.1 0.1 degree annual gridmaps summed over that SAME polygon, boundary cells split by
# exact area fraction in an equal-area projection, at the fiscal blend 0.5 x CY(Y-1) + 0.5 x CY(Y).
# EDGAR ends at calendar 2022, so FY2022-23 and FY2023-24 are NOT compared and say so rather than
# borrowing. The scope=pakistan rows are the self-check: the same summation against EDGAR's own
# published country total, which this repository already holds. CEDS, CAMS-GLOB-ANT, HTAP v3 and the
# Urban Unit inventory appear as typed not-compared rows with the reason, never as silence.
# Generated by scripts/build_air_lahore_external_comparison.py.
"""

NOT_COMPARED = (
    ("CEDS", "0.5 degree grid - one cell is wider than Lahore District, so there is no district "
             "figure to compare. Not acquired: it could not answer the question."),
    ("CAMS-GLOB-ANT", "public downloads are advertised, but SO2 grids were not acquired for "
                      "this district comparison; shared EDGAR/CEDS inputs also limit independence."),
    ("HTAP v3.2", "public JRC country bundles are available and NH3 country/month data are held "
                  "for a separate exact fiscal national comparison; no SO2 district grid is used here."),
    ("Urban Unit Lahore inventory", "a local inventory exists in the literature; "
                                    "docs/completeness.md records that the underlying data has "
                                    "not been obtained, and a published headline is not a series."),
)


def main():
    lahore_w, pakistan_w = build_weights()
    print("weights: %d cells touch Lahore, %d touch Pakistan" % (len(lahore_w), len(pakistan_w)))

    edgar_lahore = collections.defaultdict(dict)
    edgar_pakistan = collections.defaultdict(dict)
    for stream in STREAMS:
        for year in YEARS:
            lah, pak = gridmap_tonnes(stream, year, lahore_w, pakistan_w)
            edgar_lahore[stream][year] = lah / 1000.0        # tonnes -> Gg
            edgar_pakistan[stream][year] = pak / 1000.0
        print("read %s" % stream)

    engine_total, engine_sector = engine_lahore()
    published = edgar_published_national()
    rows = []

    # the self-check first, LIKE FOR LIKE: our summation of EDGAR's own grid against EDGAR's own
    # published country total for the same category. Without this the Lahore rows are unreadable.
    for streams, code, parts in SELF_CHECK:
        for year in YEARS:
            ours = sum(edgar_pakistan[st][year] for st in streams)
            theirs = sum(published[(code, part)][year] for part in parts
                         if (code, part) in published)
            if not theirs:
                rows.append({
                    "period_id": "", "calendar_year": year, "row_kind": "self_check",
                    "calendar_basis": "calendar year", "scope": "pakistan",
                    "edgar_stream": "+".join(streams), "engine_Gg": round(ours, 6),
                    "edgar_Gg": "", "ratio_engine_over_edgar": "",
                    "engine_basis": "the 0.1 degree %s gridmap(s) over Pakistan's ADM2 union"
                                    % "+".join(streams),
                    "edgar_basis": "EDGAR's published Pakistan %s is zero or absent" % code,
                    "reading": "SELF-CHECK not formed: EDGAR's own workbook prints no mass for %s, "
                               "so there is nothing for the gridded sum to reproduce. Recorded "
                               "rather than dropped" % code,
                })
                continue
            ratio = ours / theirs
            rows.append({
                "period_id": "", "calendar_year": year, "row_kind": "self_check",
                "calendar_basis": "calendar year", "scope": "pakistan",
                "edgar_stream": "+".join(streams), "engine_Gg": round(ours, 6),
                "edgar_Gg": round(theirs, 6), "ratio_engine_over_edgar": round(ratio, 6),
                "engine_basis": "the 0.1 degree %s gridmap(s) summed over Pakistan's ADM2 union, "
                                "boundary cells split by exact area fraction" % "+".join(streams),
                "edgar_basis": "EDGAR's own published Pakistan %s total (%s)"
                               % (code, " + ".join(parts)),
                "reading": "SELF-CHECK, not a finding: the two sides are the SAME compilation read "
                           "two ways, so the ratio should be 1. It is %.4f. This is what licenses "
                           "the Lahore rows - a polygon summation that could not reproduce EDGAR's "
                           "own country total would say nothing about a district - and it is what "
                           "PROVES the crosswalk by arithmetic rather than by reading a label: %s "
                           "pairs with IPCC %s. %s"
                           % (ratio, "+".join(streams), code,
                              ("Exact, so the pairing is settled."
                               if abs(ratio - 1.0) < 0.005 else
                               "The %.1f %% gap is not resolved: this category is a UNION of grid "
                               "sectors and EDGAR's printed %s may not be exactly that union, so "
                               "the pairing is confirmed in kind but not to the last tonne."
                               % (100 * abs(ratio - 1.0), code))),
            })

    # and a completeness check: the sectors must add up to TOTALS, so no sector is read by leftover
    for year in YEARS:
        parts_sum = sum(edgar_pakistan[st][year] for st in STREAMS if st != "TOTALS")
        whole = edgar_pakistan["TOTALS"][year]
        rows.append({
            "period_id": "", "calendar_year": year, "row_kind": "self_check",
            "calendar_basis": "calendar year", "scope": "pakistan", "edgar_stream": "ALL SECTORS",
            "engine_Gg": round(parts_sum, 6), "edgar_Gg": round(whole, 6),
            "ratio_engine_over_edgar": round(parts_sum / whole, 6) if whole else "",
            "engine_basis": "the %d sector gridmaps summed over Pakistan" % (len(STREAMS) - 1),
            "edgar_basis": "the TOTALS gridmap over Pakistan",
            "reading": "COMPLETENESS CHECK: every EDGAR sector is fetched, so the parts must "
                       "reconstruct the whole and no sector is ever read as a leftover. A ratio "
                       "below 1 is a sector this product does not hold",
        })

    # Lahore: every EDGAR sector, and a RATIO only where the crosswalk declares a counterpart
    for stream in STREAMS:
        ours_sector = OUR_SECTOR.get(stream)
        for fy_end in CORE_FY_ENDS:
            period = "FY%d-%02d" % (fy_end - 1, fy_end % 100)
            theirs = blend(edgar_lahore[stream], fy_end)
            if stream == "TOTALS":
                ours = engine_total.get(period)
                basis = "outputs/pakemis_air_lahore_by_year.csv, all nine sectors"
            elif ours_sector == "power":
                # rc61: Lahore HAS a power SO2 row now. It was typed NE here in every period
                # because the admitted oil and diesel mass was published at national grain and
                # placed in no district; it rides the admission register's own districts as of
                # this release, so the comparison is live. It is still only PART of power -
                # coal and gas stay in the screening - and the basis says so rather than letting
                # a ratio below 1 read as a disagreement.
                ours = engine_sector.get((period, ours_sector), 0.0)
                basis = ("outputs/pakemis_air_lahore_by_year.csv, sector power: the ADMITTED oil and diesel classes only (rc61 placed them on the admission register's own districts). Coal and gas power SO2 are NOT in this figure - they remain a screening scenario at Lahore - so this is a PARTIAL counterpart to EDGAR ENE and the ratio cannot validate total power emissions")
            elif ours_sector:
                ours = engine_sector.get((period, ours_sector), 0.0)
                basis = ("outputs/pakemis_air_lahore_by_year.csv, sector %s (IPCC %s)"
                         % (ours_sector, IPCC_OF[stream]))
            else:
                ours = None
                basis = ("no counterpart declared in the crosswalk at this grain - shown for the "
                         "SHAPE of EDGAR's Lahore series, never as a ratio")
            if theirs is None:
                rows.append({
                    "period_id": period, "calendar_year": "", "row_kind": "comparison",
                    "calendar_basis": "not compared", "scope": "lahore", "edgar_stream": stream,
                    "engine_Gg": round(ours, 4) if ours is not None else "",
                    "edgar_Gg": "", "ratio_engine_over_edgar": "",
                    "engine_basis": basis, "edgar_basis": "",
                    "reading": "not compared (EDGAR v8.1 ends at calendar 2022); the engine value "
                               "stands alone rather than being set against a borrowed year",
                })
                continue
            ratio = (ours / theirs) if (ours is not None and theirs) else None
            rows.append({
                "period_id": period, "calendar_year": "", "row_kind": "comparison",
                "calendar_basis": "0.5 x CY%d + 0.5 x CY%d (a BLEND, not an exact July-June year)"
                                  % (fy_end - 1, fy_end),
                "scope": "lahore", "edgar_stream": stream,
                "engine_Gg": round(ours, 4) if ours is not None else "",
                "edgar_Gg": round(theirs, 6), "ratio_engine_over_edgar": round(ratio, 4) if ratio else "",
                "engine_basis": basis,
                "edgar_basis": "v8.1 0.1 degree %s gridmap (IPCC %s) over the district polygon"
                               % (stream, IPCC_OF.get(stream, "all")),
                "reading": ("contextual engine/EDGAR ratio %s, on %s; source boundaries and shared inputs must be checked"
                            % (band(ratio), STREAM_WORDS[stream]) if ratio else
                            "EDGAR's %s at Lahore; no ratio is formed because %s"
                            % (STREAM_WORDS[stream],
                               "this release types the sector NE" if ours_sector == "power"
                               else "the crosswalk declares no counterpart at this grain")),
            })

    # ---------------------------------------------------------------- the findings, restated
    def at(stream, fy_end):
        return blend(edgar_lahore[stream], fy_end)

    ours_ind_s, ours_ind_e = (engine_sector.get(("FY2015-16", "industry"), 0.0),
                              engine_sector.get(("FY2021-22", "industry"), 0.0))
    rows.append({
        "period_id": "", "calendar_year": "", "row_kind": "finding",
        "calendar_basis": "FY2015-16 -> FY2021-22", "scope": "lahore", "edgar_stream": "IND",
        "engine_Gg": "", "edgar_Gg": "", "ratio_engine_over_edgar": "",
        "engine_basis": "outputs/pakemis_air_lahore_by_year.csv, sector industry (all 1.A.2)",
        "edgar_basis": "v8.1 0.1 degree IND gridmap (IPCC 1.A.2) over the district polygon",
        "reading": "CONTEXTUAL INDUSTRY COMPARISON. The engine/EDGAR ratio changes from %.2f to %.2f "
                   "across the matched window. EDGAR changes %.3f -> %.3f Gg (%.0f %%) and "
                   "the engine %.3f -> %.3f Gg (%.0f %%). PakEmis industry includes an "
                   "integrated cement-stack factor, while IND is fuel combustion only; the "
                   "district ratio is therefore not a fully matched factor test. The national "
                   "comparison separately includes EDGAR cement process emissions. Shared "
                   "HDIP/energy statistics limit independence, and fixed location proxies "
                   "do not observe changing local activity."
                   % (ours_ind_s / at("IND", 2016), ours_ind_e / at("IND", 2022),
                      at("IND", 2016), at("IND", 2022),
                      100 * (at("IND", 2022) / at("IND", 2016) - 1),
                      ours_ind_s, ours_ind_e, 100 * (ours_ind_e / ours_ind_s - 1)),
    })

    fo_kt = at("ENE", 2016) * 1000.0 / (2 * 0.030) / 1000.0
    rows.append({
        "period_id": "FY2015-16", "calendar_year": "", "row_kind": "finding",
        "calendar_basis": "0.5 x CY2015 + 0.5 x CY2016", "scope": "lahore", "edgar_stream": "ENE",
        "engine_Gg": round(engine_sector.get(("FY2015-16", "power"), 0.0), 4) or "",
        "edgar_Gg": round(at("ENE", 2016), 4),
        "ratio_engine_over_edgar": "",
        "engine_basis": ("the admitted oil and diesel power SO2 at Lahore (rc61); coal and gas "
                         "power stay typed NE, so this is a partial counterpart"),
        "edgar_basis": "v8.1 0.1 degree ENE gridmap (IPCC 1.A.1.a) over the district polygon",
        "reading": "PARTIAL POWER-BOUNDARY COMPARISON. EDGAR allocates %.0f %% of its Lahore SO2 "
                   "to power. Interpreting that mass as 3.0 %%-sulfur furnace oil would imply "
                   "%.0f kt, against the retained national industrial-furnace-oil control of "
                   "%.0f kt. This fuel interpretation is a sensitivity, not observed plant fuel. "
                   "PakEmis centrally admits reviewed oil/diesel SO2 only; coal, gas and other "
                   "plant/control boundaries differ. The discrepancy therefore does not "
                   "identify an EDGAR error or establish complete PakEmis coverage."
                   % (100 * at("ENE", 2016) / at("TOTALS", 2016), fo_kt, 1465.0),
    })

    rows.append({
        "period_id": "", "calendar_year": "", "row_kind": "finding",
        "calendar_basis": "every matched year", "scope": "lahore", "edgar_stream": "TRO",
        "engine_Gg": "", "edgar_Gg": "", "ratio_engine_over_edgar": "",
        "engine_basis": "data/activity/transport/fuel_sulfur_by_year.csv, 500 ppm from FY2017-18",
        "edgar_basis": "v8.1 0.1 degree TRO gridmap (IPCC 1.A.3.b)",
        "reading": "ROAD SULFUR-ASSUMPTION SENSITIVITY. The engine is %.0f times EDGAR at "
                   "Lahore for the matched comparison. PakEmis uses the declared 500 ppm "
                   "policy/specification case, not measured universal pump compliance. "
                   "Fuel sulfur, activity, control and location assumptions may all contribute; "
                   "the ratio alone cannot identify which inventory is closer to actual releases."
                   % (engine_sector.get(("FY2021-22", "transport"), 0.0) / at("TRO", 2022)),
    })

    rows.append({
        "period_id": "", "calendar_year": "", "row_kind": "finding",
        "calendar_basis": "every matched year", "scope": "lahore", "edgar_stream": "RCO",
        "engine_Gg": "", "edgar_Gg": "", "ratio_engine_over_edgar": "",
        "engine_basis": "outputs/pakemis_air_lahore_by_year.csv, sector residential",
        "edgar_basis": "v8.1 0.1 degree RCO gridmap (IPCC 1.A.4)",
        "reading": "HOUSEHOLD-BOUNDARY CONTEXT. PakEmis is %.2f of EDGAR in the selected "
                   "comparison. PakEmis household gross appliance emissions and EDGAR's "
                   "residential-plus-commercial sector are different source boundaries. "
                   "This contextual ratio is not independent validation or an ambient release test."
                   % (engine_sector.get(("FY2021-22", "residential"), 0.0) / at("RCO", 2022)),
    })

    rows.append({
        "period_id": "", "calendar_year": "", "row_kind": "finding",
        "calendar_basis": "every matched year", "scope": "lahore", "edgar_stream": "NMM",
        "engine_Gg": "", "edgar_Gg": "0.0", "ratio_engine_over_edgar": "",
        "engine_basis": "outputs/pakemis_air_lahore_by_year.csv, sector ippu (IPCC 2.A/2.B/2.C)",
        "edgar_basis": "v8.1 0.1 degree NMM gridmap (IPCC 2.A.1)",
        "reading": "MINERAL-PROCESS BOUNDARY. NMM describes mineral process emissions, "
                   "whereas brick firing fuel belongs to combustion. A zero NMM grid allocation "
                   "does not establish the absence of brick emissions. The PakEmis IPPU module "
                   "also includes chemical and metal processes, so its aggregate is not a "
                   "fully matched NMM counterpart.",
    })

    # ------------------------------------------------ exact fiscal years, where monthly is held
    for grouping, sector in MONTHLY_GROUPING.items():
        by_month = monthly_tonnes(grouping, lahore_w, pakistan_w)
        if by_month is None:
            rows.append({
                "period_id": "", "calendar_year": "", "row_kind": "not_compared",
                "calendar_basis": "not compared", "scope": "lahore", "edgar_stream": grouping,
                "engine_Gg": "", "edgar_Gg": "", "ratio_engine_over_edgar": "",
                "engine_basis": "", "edgar_basis": "",
                "reading": "the monthly bulk archive for this grouping is not held, so the fiscal "
                           "years stay on the 0.5/0.5 calendar blend and say so",
            })
            continue
        ours_sector = OUR_SECTOR.get(sector)
        for fy_end in range(2016, 2023):
            period = "FY%d-%02d" % (fy_end - 1, fy_end % 100)
            exact = fiscal_exact(by_month, fy_end, 0)
            if exact is None:
                continue
            blended = blend(edgar_lahore[sector], fy_end)
            ours = (engine_sector.get((period, ours_sector), 0.0) if ours_sector else None)
            ratio = (ours / exact) if (ours is not None and exact) else None
            rows.append({
                "period_id": period, "calendar_year": "", "row_kind": "comparison_exact_fy",
                "calendar_basis": "July %d - June %d, the twelve monthly grids summed"
                                  % (fy_end - 1, fy_end),
                "scope": "lahore", "edgar_stream": grouping,
                "engine_Gg": round(ours, 4) if ours is not None else "",
                "edgar_Gg": round(exact, 6),
                "ratio_engine_over_edgar": round(ratio, 4) if ratio else "",
                "engine_basis": ("outputs/pakemis_air_lahore_by_year.csv, sector power: the ADMITTED oil and diesel classes only (rc61 placed them on the admission register's own districts). Coal and gas power SO2 are NOT in this figure - they remain a screening scenario at Lahore - so this is a PARTIAL counterpart to EDGAR ENE and the ratio cannot validate total power emissions" if ours_sector == "power"
                                 else "outputs/pakemis_air_lahore_by_year.csv, sector %s"
                                      % ours_sector),
                "edgar_basis": "v8.1 0.1 degree %s monthly grids over the district polygon"
                               % grouping,
                "reading": "the EXACT July-June year rather than the calendar blend. The blend "
                           "gives %.4f Gg and the exact year %.4f, a difference of %.1f %%; the "
                           "blend is an approximation and this row is what measures it"
                           % (blended, exact, 100 * (blended / exact - 1) if exact else 0.0),
            })
        # the boundary test the monthly groupings exist for
        whole_pak = fiscal_exact(by_month, 2022, 1)
        annual_pak = blend(edgar_pakistan[sector], 2022)
        if whole_pak and annual_pak:
            rows.append({
                "period_id": "FY2021-22", "calendar_year": "", "row_kind": "self_check",
                "calendar_basis": "July 2021 - June 2022", "scope": "pakistan",
                "edgar_stream": grouping, "engine_Gg": round(whole_pak, 6),
                "edgar_Gg": round(annual_pak, 6),
                "ratio_engine_over_edgar": round(whole_pak / annual_pak, 6),
                "engine_basis": "the monthly bulk grouping %s over Pakistan" % grouping,
                "edgar_basis": "the annual sector grid %s over Pakistan, same fiscal blend" % sector,
                "reading": "THE BOUNDARY TEST. The monthly bulk groupings are broader than the "
                           "annual sector codes. A ratio above 1 means the grouping carries mass "
                           "the sector code does not - for %s that would be autoproducers, which "
                           "matters here because this release books captive self-generation under "
                           "IPCC 1.A.2 and not under power. A ratio at 1 means the two boundaries "
                           "agree and the comparison above is safe to read" % grouping,
            })

    # the autoproducer question, answered rather than left open
    boundary = [r for r in rows if r["row_kind"] == "self_check"
                and r["edgar_stream"].startswith("bkl_") and r["ratio_engine_over_edgar"]]
    if boundary:
        worst = max(abs(float(r["ratio_engine_over_edgar"]) - 1.0) for r in boundary)
        rows.append({
            "period_id": "FY2021-22", "calendar_year": "", "row_kind": "finding",
            "calendar_basis": "July 2021 - June 2022", "scope": "pakistan",
            "edgar_stream": "bkl_POWER_INDUSTRY", "engine_Gg": "", "edgar_Gg": "",
            "ratio_engine_over_edgar": "",
            "engine_basis": "this release books captive self-generation under IPCC 1.A.2, not power "
                            "(data/activity/power/captive_register.csv, priced in the industry "
                            "module)",
            "edgar_basis": "the monthly bulk groupings against the annual sector codes, over Pakistan",
            "reading": "EDGAR INTERNAL BOUNDARY CHECK. Its monthly grids come in bulk "
                       "groupings that are broader than its annual sector codes, so a power "
                       "grouping could carry autoproducers that the ENE code does not - which "
                       "would matter, because this release books captive generation under 1.A.2. "
                       "The maximum checked difference is %.1f %% over Pakistan. This is an internal "
                       "comparison of EDGAR products, not independent evidence of a PakEmis boundary "
                       "match. Exact fiscal and adjacent-calendar blends retain their own timing "
                       "differences; agreement in a national sum does not establish district equivalence."
                       % (100 * worst),
        })

    for name, why in NOT_COMPARED:
        rows.append({
            "period_id": "", "calendar_year": "", "row_kind": "not_compared",
            "calendar_basis": "not compared",
            "scope": "lahore", "edgar_stream": name, "engine_Gg": "", "edgar_Gg": "",
            "ratio_engine_over_edgar": "", "engine_basis": "", "edgar_basis": "",
            "reading": why,
        })

    with open(OUT, "w", encoding="utf-8", newline="") as handle:
        handle.write(BANNER)
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print("%s: %d rows" % (os.path.relpath(OUT, ROOT), len(rows)))


if __name__ == "__main__":
    main()
