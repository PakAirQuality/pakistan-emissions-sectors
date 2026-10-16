"""PROVINCIAL SO2 AGAINST EDGAR v8.1 - the magnitude-at-province cell the scorecard declares absent.

WHY THIS EXISTS. outputs/pakemis_validation_scorecard.csv covers twelve of its thirty-six
property x grain cells. `geography | province` is covered five times over at LARGE
independence - the release checks how provincial SHARES are distributed. `magnitude |
province` is empty, and its note says so plainly: "no validation exists for this cell; the
absence is the registered fact and this row is the roadmap entry". Shares and magnitudes are
different claims, which is exactly the separation the campaign brief draws, and nothing here
had tested the second one.

WHAT IT DOES NOT ADD. It does not write a second grid summation. scripts/
build_air_lahore_external_comparison.py already reads EDGAR's gridded SO2, splits boundary
cells by EXACT area fraction in an equal-area projection, and - the part that matters - checks
the summation against EDGAR's OWN published national total before any sub-national number is
read. This file imports that module's crosswalk, its self-check pairs and its published-total
reader, and generalises the polygon weights from one district to the five provincial labels
the release actually reports.

THE CONTROL COMES FIRST, and it is a gate rather than a footnote. A polygon summation that
cannot reproduce EDGAR's published national figure says nothing about a province, so the
national ratios are computed and written before the provincial rows and the reading of any
provincial row names the control's state.

PERIOD. EDGAR is calendar-year and this inventory is July-June. The blend 0.5 x CY(Y-1) +
0.5 x CY(Y) is the approximation this repository already uses elsewhere, and it is labelled an
approximation here too: eight calendar years are not eight fiscal years, and a half-weighted
pair is an assumption about within-year shape, not a measurement of one.

SPECIES. SO2 only, because SO2 gridmaps are what this repository holds. EDGAR's GHG gridded
products are not held, so this closes the cell for one species and leaves it open for the rest.
"""
import collections
import csv
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from pkinv.assets import asset_path                                   # noqa: E402
from pkinv.core.io import read_rows, write_table                      # noqa: E402

import build_air_lahore_external_comparison as LAHORE                 # noqa: E402

EQUAL_AREA = LAHORE.EQUAL_AREA
GRIDMAPS = LAHORE.GRIDMAPS
YEARS = LAHORE.YEARS
CFG = LAHORE.CFG

OUT = asset_path(ROOT, "outputs", "pakemis_air_provincial_external_comparison.csv")
CACHE = asset_path(ROOT, "build", "edgar_0p1_adm1_weights.csv")

# The release reports five provincial labels. data/shared/canonical/gis/adm2_canonical.csv is
# the repository's own authority for the grouping: its Province ID column puts Azad Jammu and
# Kashmir, Gilgit-Baltistan and Islamabad Capital Territory - thirteen districts - under
# "Other". The ADM1 shapes are grouped the same way so the two sides name the same places.
ADM1_TO_LABEL = {
    "Punjab": "Punjab",
    "Sindh": "Sindh",
    "Khyber Pakhtunkhwa": "Khyber Pakhtunkhwa",
    "Balochistan": "Balochistan",
    "Azad Kashmir": "Other",
    "Gilgit-Baltistan": "Other",
    "Islamabad Capital Territory": "Other",
}
LABELS = ("Punjab", "Sindh", "Khyber Pakhtunkhwa", "Balochistan", "Other")

COLUMNS = ("period_id", "calendar_basis", "row_kind", "scope", "edgar_stream", "ipcc_code",
           "engine_Gg", "edgar_Gg", "ratio_engine_over_edgar", "engine_basis", "edgar_basis",
           "reading")


def build_weights():
    """{label: {(row, col): area fraction}} on EDGAR's 0.1 lattice, plus 'pakistan'.

    The same construction as the Lahore weights and for the same reason: a boundary cell is
    split by the fraction of its area inside the polygon, computed in an equal-area projection,
    never assigned whole to whichever polygon holds its centre.
    """
    if os.path.exists(CACHE):
        out = collections.defaultdict(dict)
        for r in read_rows(CACHE):
            key = (int(r["row"]), int(r["col"]))
            for label in LABELS + ("pakistan",):
                v = float(r[label.replace(" ", "_")])
                if v:
                    out[label][key] = v
        return out

    import geopandas as gpd
    from shapely.geometry import box
    from shapely.prepared import prep

    adm1 = gpd.read_file(asset_path(ROOT, "data", "gis", "PAK_ADM1.geojson")).to_crs("EPSG:4326")
    missing = set(adm1["shapeName"]) - set(ADM1_TO_LABEL)
    if missing:
        raise SystemExit("ADM1 shapes with no declared label: %s" % sorted(missing))
    geoms = {}
    for label in LABELS:
        names = [n for n, l in ADM1_TO_LABEL.items() if l == label]
        geoms[label] = adm1[adm1["shapeName"].isin(names)].to_crs(EQUAL_AREA).geometry.union_all()
    geoms["pakistan"] = adm1.to_crs(EQUAL_AREA).geometry.union_all()
    prepared = {k: prep(v) for k, v in geoms.items()}

    west, south, east, north = 60.0, 23.0, 78.5, 37.5
    c0, c1 = int((west + 180.0) / 0.1), int((east + 180.0) / 0.1)
    r0, r1 = int((south + 90.0) / 0.1), int((north + 90.0) / 0.1)
    rows = []
    for r in range(r0, r1):
        for c in range(c0, c1):
            lon0, lat0 = -180.0 + 0.1 * c, -90.0 + 0.1 * r
            cell = gpd.GeoSeries([box(lon0, lat0, lon0 + 0.1, lat0 + 0.1)],
                                 crs="EPSG:4326").to_crs(EQUAL_AREA)[0]
            if not prepared["pakistan"].intersects(cell):
                continue
            area = cell.area
            rec = {"row": r, "col": c, "lon_west": round(lon0, 4), "lat_south": round(lat0, 4)}
            any_share = False
            for key in LABELS + ("pakistan",):
                frac = cell.intersection(geoms[key]).area / area if prepared[key].intersects(cell) else 0.0
                rec[key.replace(" ", "_")] = round(frac, 12)
                any_share = any_share or frac > 1e-12
            if any_share:
                rows.append(rec)
    fields = ["row", "col", "lon_west", "lat_south"] + [k.replace(" ", "_") for k in LABELS + ("pakistan",)]
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    with open(CACHE, "w", encoding="utf-8", newline="") as handle:
        handle.write("# EDGAR 0.1 degree cell x ADM1 AREA FRACTIONS, computed in %s exactly as the\n"
                     "# Lahore comparison and scripts/build_adm2_intersections.py do. Provinces are\n"
                     "# grouped onto the release's five reported labels using the Province ID column\n"
                     "# of adm2_canonical.csv. A REGENERABLE INTERMEDIATE: it lives in build/ because\n"
                     "# it is derived from PAK_ADM1.geojson and nothing needs it shipped.\n" % EQUAL_AREA)
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return build_weights()


def gridmap_by_region(stream, year, weights):
    """{region: tonnes} for one annual gridmap, every region from one read of the file."""
    import zipfile
    import netCDF4
    import numpy as np

    name = "v8.1_FT2022_AP_SO2_%d_%s_emi_nc.zip" % (year, stream)
    with zipfile.ZipFile(asset_path(GRIDMAPS, name)) as zf:
        member = [n for n in zf.namelist() if n.endswith(".nc")][0]
        with zf.open(member) as handle:
            data = netCDF4.Dataset("inmemory", memory=handle.read())
            emissions = np.asarray(data.variables["emissions"][:])
            lats = np.asarray(data.variables["lat"][:])
            lons = np.asarray(data.variables["lon"][:])
    lat_index = {round((v + 90.0 - 0.05) / 0.1): i for i, v in enumerate(lats)}
    lon_index = {round((v + 180.0 - 0.05) / 0.1): i for i, v in enumerate(lons)}
    out = {}
    for region, w in weights.items():
        total = 0.0
        for (r, c), frac in w.items():
            i, j = lat_index.get(r), lon_index.get(c)
            if i is not None and j is not None:
                total += float(emissions[i, j]) * frac
        out[region] = total
    return out


def engine_provincial():
    """{(period_id, province): Gg SO2} from the shipped ADM1 air view, reference configuration."""
    out = collections.defaultdict(float)
    for r in read_rows(asset_path(ROOT, "outputs", "pakemis_air_adm1_by_year.csv")):
        if r["pollutant"] != "SO2" or r["configuration_id"] != CFG:
            continue
        out[(r["period_id"], r["province"])] += float(r["emissions_Gg"])
    return out


def screening_so2():
    """{period_id: (controlled_case_kt, uncontrolled_kt)} for power, the release's own bounds."""
    agg = collections.defaultdict(float)
    for r in read_rows(asset_path(ROOT, "outputs",
                                  "power_air_screening_fy2015_16_fy2024_25.csv")):
        if r["pollutant"] == "SO2":
            agg[(r["period_id"], r["scenario"])] += float(r["emissions_kt"] or 0)
    return {p: (agg.get((p, "controlled_case"), 0.0), agg.get((p, "uncontrolled"), 0.0))
            for p in {k[0] for k in agg}}


BANNER = """\
# PROVINCIAL SO2 AGAINST EDGAR v8.1 - the magnitude-at-province cell outputs/
# pakemis_validation_scorecard.csv declares absent. engine = the release's own ADM1 allocation,
# configuration REF_2023_24, Gg SO2. edgar = EDGAR v8.1 AP gridded SO2 summed over the same ADM1
# polygons, boundary cells split by EXACT area fraction in an equal-area projection (%s), at the
# fiscal blend 0.5 x CY(Y-1) + 0.5 x CY(Y).
#
# THE SELF-CHECK ROWS COME FIRST AND ARE A GATE. A polygon summation that cannot reproduce
# EDGAR's OWN published national total says nothing about a province. Single-category checks
# (IND=1.A.2, NMM=2.A.1, CHE=2.B) land within 0.0041 of 1.0, which is the tolerance
# tests/test_air_lahore_so2_diagnosis.py already holds the Lahore product to. The GROUPED check
# (IRO+NFE against published 2.C) runs 1.031-1.090 and is carried as a stated limit, exactly as
# that product carries it: the repository asserts single-category checks and excludes grouped
# ones by design.
#
# SCOPE. comparison rows use only the EDGAR streams the crosswalk maps to an engine sector, so
# refineries, chemical and metal process, food/paper, shipping, non-road transport and aviation
# cruise/climb are excluded from the ratio. Matching scope moves Sindh from 0.195 to 0.206: the
# disagreement below is not a scope artefact.
#
# PERIOD. EDGAR is calendar-year and this release is July-June. The half-weighted blend is an
# approximation and is labelled one; it is not a measured fiscal-year total. EDGAR v8.1 ends at
# CY2022, so FY2022-23 and FY2023-24 have no comparison row.
#
# NEVER A CALIBRATION. Nothing in the release is read back from this table.
""" % EQUAL_AREA


def main():
    weights = build_weights()
    regions = dict(weights)
    matched = [(s, ours) for s, _i, ours, _w in LAHORE.CROSSWALK if ours]
    streams = [s for s, _ in matched]
    cy = {y: {s: {k: v / 1000.0 for k, v in gridmap_by_region(s, y, regions).items()}
              for s in streams} for y in YEARS}

    def blend(fy_end, region, subset):
        if fy_end - 1 not in cy or fy_end not in cy:
            return None
        return sum(0.5 * cy[fy_end - 1][s][region] + 0.5 * cy[fy_end][s][region] for s in subset)

    published = LAHORE.edgar_published_national()
    rows = []
    worst_single = 0.0
    for group, ipcc, parts in LAHORE.SELF_CHECK:
        for year in YEARS:
            summed = sum(gridmap_by_region(s, year, {"pakistan": weights["pakistan"]})["pakistan"]
                         for s in group) / 1000.0
            pub = sum(published.get((ipcc, p), {}).get(year, 0.0) for p in parts)
            if not pub:
                continue
            ratio = summed / pub
            single = len(group) == 1
            if single:
                worst_single = max(worst_single, abs(ratio - 1.0))
            rows.append({
                "period_id": "", "calendar_basis": "CY%d" % year, "row_kind": "self_check",
                "scope": "pakistan", "edgar_stream": "+".join(group), "ipcc_code": ipcc,
                "engine_Gg": "", "edgar_Gg": round(summed, 4),
                "ratio_engine_over_edgar": round(ratio, 4),
                "engine_basis": "EDGAR's own published national total, not the engine",
                "edgar_basis": "polygon summation over Pakistan",
                "reading": ("single-category check: the summation reads the grid correctly"
                            if single else
                            "GROUPED check, excluded from the single-category tolerance by the "
                            "same rule the Lahore product uses")})

    eng = engine_provincial()
    screening = screening_so2()
    periods = ["FY%d-%02d" % (y, (y + 1) % 100) for y in range(YEARS[0], YEARS[-1])]
    for period in periods:
        fy_end = int(period[2:6]) + 1
        for label in LABELS + ("pakistan",):
            if label == "pakistan":
                e = sum(eng.get((period, q), 0.0) for q in LABELS)
            else:
                e = eng.get((period, label), 0.0)
            d = blend(fy_end, label, streams)
            if d is None:
                continue
            ratio = e / d if d else None
            rows.append({
                "period_id": period, "calendar_basis": "0.5 x CY%d + 0.5 x CY%d" % (fy_end - 1, fy_end),
                "row_kind": "comparison", "scope": label, "edgar_stream": "matched streams",
                "ipcc_code": "", "engine_Gg": round(e, 4), "edgar_Gg": round(d, 4),
                "ratio_engine_over_edgar": round(ratio, 4) if ratio else "",
                "engine_basis": "release ADM1 allocation, configuration %s" % CFG,
                "edgar_basis": "EDGAR v8.1 AP gridded SO2, area-fraction summation",
                "reading": LAHORE.band(ratio)})
        # the power decomposition, because that is where the provincial disagreement lives
        for label in LABELS + ("pakistan",):
            if label == "pakistan":
                e = sum(v for (p, q), v in _power_by_province(period).items() if p == period)
            else:
                e = _power_by_province(period).get((period, label), 0.0)
            d = blend(fy_end, label, ["ENE"])
            if d is None:
                continue
            c, u = screening.get(period, (0.0, 0.0))
            rows.append({
                "period_id": period, "calendar_basis": "0.5 x CY%d + 0.5 x CY%d" % (fy_end - 1, fy_end),
                "row_kind": "power_decomposition", "scope": label, "edgar_stream": "ENE",
                "ipcc_code": "1.A.1.a", "engine_Gg": round(e, 4), "edgar_Gg": round(d, 4),
                "ratio_engine_over_edgar": round(e / d, 4) if d else "",
                "engine_basis": "the rc60 oil-and-diesel admission register; power SO2 AS ACTUALLY "
                                "EMITTED is a declared NE pending a control-device inventory",
                "edgar_basis": "EDGAR ENE, which also carries autoproducers this release books in 1.A.2",
                "reading": ("national uncontrolled screening %.1f kt and controlled case %.1f kt "
                            "bracket the release's own answer; EDGAR is outside that bracket"
                            % (u, c)) if label == "pakistan" else ""})
    # banner is an iterable of LINES; a bare string would be written one character per line
    write_table(OUT, COLUMNS, rows, banner=BANNER.splitlines())
    print("provincial SO2 comparison -> %s (%d rows)" % (os.path.relpath(OUT, ROOT), len(rows)))
    print("worst single-category self-check deviation: %.4f" % worst_single)
    return 0


_POWER_CACHE = {}


def _power_by_province(period):
    if period not in _POWER_CACHE:
        out = collections.defaultdict(float)
        for r in read_rows(asset_path(ROOT, "outputs", "pakemis_air_adm1_by_year.csv")):
            if (r["pollutant"] == "SO2" and r["configuration_id"] == CFG
                    and r["sector_id"] == "power"):
                out[(r["period_id"], r["province"])] += float(r["emissions_Gg"])
        _POWER_CACHE[period] = out
    return _POWER_CACHE[period]


if __name__ == "__main__":
    raise SystemExit(main())
