"""Province and district allocations for ALL SEVEN sector air-pollutant layers (Wave C of
the air spatial lane): every pollutant row inherits ITS OWN greenhouse-gas stream's shipped
allocation, never a fresh guess.

- ADM1: each six-sector air row's kt times the anchoring stream's declared province vector
  from pakemis_grid_provincial_check.csv, the vector's status carried (derived_from_grid for
  railways traction, declared_divergence for aviation LTO, unallocated_below_adm1 for
  cruise - cruise IS placed at ADM1, exactly as its greenhouse-gas mass is). Agriculture's
  rows are its own provincial layer, byte-copied.
- ADM2: kt times the stream's normalized shape vector from pakemis_adm2_stream_reference.csv
  (the cube's own stream_shape accumulation). Aviation cruise is ABSENT here - typed in the
  query layer, never zeroed. Agriculture is its own allocator (air_spatial.build), called
  in-memory and re-keyed from district names to the canonical shape frame; the two
  no-polygon census units and the GB/AJK/ICT residual ride allocation_status.
- Every inherited row carries its stream's evidence_grade and located_share from the
  support ledger, so nothing grades better than the geography it borrowed.

Closures (check()): ADM1 sums equal the national layer per (sector, pollutant); ADM2 sums
equal ADM1 per (sector, province, pollutant) net of the cruise retention and the OUTSIDE
term; every shape_id is the canonical frame's. RTOL is relative (kt spans five orders)."""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import collections
import csv
import io
import os

from pkinv.report import air_join

ROOT = asset_path(os.path.dirname(__file__), "..", "..", "..")
OUTPUTS = asset_path(ROOT, "outputs")
RTOL = 1e-6
# agriculture's provincial and district tables are byte-copied from its own layer, whose
# shipped rows are rounded (3 dp provincial, 5 dp district); a sum of n rounded rows can
# miss by up to n x half-ulp, an ABSOLUTE bound - a relative one breaks on the small
# species (BC is 3.6 kt over 70 rows)
HALF_ULP = {"adm1": 0.0005, "adm2": 0.000005}
REFERENCE_PERIOD = "FY2023-24"

AIR_FILES = {
    "agriculture": "air_pollutants_2024.csv",
    "residential": "residential_air_pollutants_2024.csv",
    "transport": "transport_air_pollutants_2024.csv",
    "waste": "waste_air_pollutants_2024.csv",
    "aviation": "aviation_air_pollutants_fy2023_24.csv",
    "power": "power_air_pollutants_fy2023_24.csv",
    "railways": "railways_air_pollutants_2024.csv",
}
PERIODS = {sector: REFERENCE_PERIOD for sector in AIR_FILES}
CRUISE_ANCHOR = "Domestic aviation cruise CO2"

ADM1_FIELDS = ["sector_id", "period_id", "province", "category", "subitem", "proxy",
               "pollutant", "emissions_kt", "share_status", "evidence_grade", "located_share",
               "estimate_kind"]
ADM2_FIELDS = ["sector_id", "period_id", "shape_id", "adm2_ids", "unit_name", "province",
               "category", "subitem", "proxy", "pollutant", "emissions_kt",
               "allocation_status", "evidence_grade", "located_share", "estimate_kind"]
# rc68 air review (criterion 3): the power reference-year file this layer places is the
# UNCONTROLLED SCREENING scenario (coal, gas, bagasse and the unadmitted oil remainder). Until
# rc68 its rows sat beside the covered estimates here with nothing on the row to say so, and a
# sum over this file added 211 Gg of screened coal SO2 to covered mass. Every row now carries
# its kind; a screening row is never a covered estimate and never enters a covered total.
COVERED = "covered_estimate"
SCREENING = "screening_scenario_not_in_covered_total"


def estimate_kind(sector, row):
    if sector != "power":
        return COVERED
    if "SCREENING" not in row.get("basis", "").upper():
        raise ValueError("a power air row that is not declared a screening scenario: %r" % row)
    return SCREENING


def _read(path):
    return [r for r in _activity_rows(asset_path(OUTPUTS, path), comments=True)]


def _province_vectors():
    """{stream: ({province: declared_share}, status)} from the cube's own check table."""
    out = {}
    for r in _read("pakemis_grid_provincial_check.csv"):
        vec, _ = out.setdefault(r["source_stream_id"], ({}, r["status"]))
        vec[r["province"]] = float(r["declared_share"])
    return out


def _shape_vectors():
    """{stream: [(shape_id, adm2_ids, province, status, share)]}, normalized over shapes
    plus the OUTSIDE term - the cube's stream_shape accumulation, reused as shares."""
    rows = collections.defaultdict(list)
    for r in _read("pakemis_adm2_stream_reference.csv"):
        rows[r["source_stream_id"]].append(r)
    out = {}
    for sid, rs in rows.items():
        total = sum(float(r["emissions_Gg"]) for r in rs if r["emissions_Gg"])
        if total <= 0:
            continue
        out[sid] = [(r["shape_id"], r["adm2_ids"], r["province"], r["allocation_status"],
                     float(r["emissions_Gg"]) / total) for r in rs if r["emissions_Gg"]]
    return out


def _grades():
    """{stream: (evidence_grade, located_share)} from the support ledger's reference rows."""
    out = {}
    for r in _read("pakemis_stream_support_ledger.csv"):
        if r["period_id"] == REFERENCE_PERIOD:
            out[r["source_stream_id"]] = (r["evidence_grade"], r["located_share"])
    return out


def _profiles():
    return {r["source_stream_id"]: r["spatial_profile_id"]
            for r in _activity_rows(asset_path(OUTPUTS, "pakemis_source_streams.csv"), comments=False)}


def build():
    index = air_join.stream_index()
    vectors = _province_vectors()
    shapes = _shape_vectors()
    grades = _grades()
    profiles = _profiles()
    adm1, adm2 = [], []

    # --- the six inherited sectors -----------------------------------------------------
    for sector, fname in AIR_FILES.items():
        if sector == "agriculture":
            continue
        for row in _read(fname):
            sid = air_join.stream_for(sector, row, index)
            kt = float(row["emissions_kt"])
            subitem = row.get("subitem") or (row.get("fuel", "") +
                                             ("|" + row["fuel_detail"] if row.get("fuel_detail") else ""))
            grade, located = grades.get(sid, ("", ""))
            proxy = profiles.get(sid, "")
            vec, status = vectors[sid]
            base = {"sector_id": sector, "period_id": PERIODS[sector],
                    "category": row["category"], "subitem": subitem,
                    "proxy": proxy, "pollutant": row["pollutant"],
                    "evidence_grade": grade, "located_share": located,
                    "estimate_kind": estimate_kind(sector, row)}
            for province, share in sorted(vec.items()):
                adm1.append(dict(base, province=province,
                                 emissions_kt="%.9g" % (kt * share), share_status=status))
            if status == "unallocated_below_adm1":
                continue                      # ADM1 only, exactly like its stream's mass
            for shape_id, adm2_ids, province, astatus, share in shapes[sid]:
                adm2.append(dict(base, shape_id=shape_id, adm2_ids=adm2_ids, unit_name="",
                                 province=province, emissions_kt="%.9g" % (kt * share),
                                 allocation_status=astatus))

    # --- agriculture: its own allocator, re-keyed to the canonical frame ----------------
    for r in _read("air_pollutants_provincial_2024.csv"):
        adm1.append({"sector_id": "agriculture", "period_id": PERIODS["agriculture"],
                     "province": r["province"], "category": r["category"],
                     "subitem": r["subitem"], "proxy": r["proxy"],
                     "pollutant": r["pollutant"], "emissions_kt": r["emissions_kt"],
                     "share_status": "own_layer", "evidence_grade": "", "located_share": "",
                     "estimate_kind": COVERED})
    adm2.extend(_agriculture_adm2())
    return adm1, adm2


def _agriculture_adm2():
    """air_spatial.build() in-memory (its 4-tuple signature untouched), district names
    re-keyed to the canonical shape frame the way the survey writer does it."""
    import json
    from pkinv.core import adm2 as adm2_core
    from pkinv.core.gis.grid import build_grid, ADM2_PATH
    from pkinv.sectors.agriculture.gis import air_spatial
    from pkinv.sectors.agriculture.gis.run_gis import resolve_proxies

    grid = build_grid()
    if grid.district_id is None:
        raise RuntimeError("PAK_ADM2.geojson is required for the agriculture air re-key")
    proxies, cat_proxy, _ = resolve_proxies(grid)
    _, district_rows, _, _ = air_spatial.build(grid, proxies, cat_proxy)

    name_to_shape = {}
    with open(ADM2_PATH, encoding="utf-8") as handle:
        for feature in json.load(handle)["features"]:
            p = feature["properties"]
            name_to_shape.setdefault(p["shapeName"], p["shapeID"])
    shape_members = adm2_core.shape_to_adm2()

    out = []
    for r in district_rows:
        base = {"sector_id": "agriculture", "period_id": PERIODS["agriculture"],
                "category": r["category"], "subitem": "", "proxy": r["proxy"],
                "pollutant": r["pollutant"], "emissions_kt": "%.9g" % r["emissions_kt"],
                "evidence_grade": "", "located_share": "", "estimate_kind": COVERED}
        shape = name_to_shape.get(r["district"])
        if shape:
            members = shape_members.get(shape, [])
            out.append(dict(base, shape_id=shape, adm2_ids=";".join(members),
                            unit_name=r["district"], province=r["province"],
                            allocation_status="one_to_one" if len(members) <= 1 else "shared_shape"))
        else:
            # the two no-polygon census units and the GB/AJK/ICT residual: named, not dropped
            status = "outside_provinces" if r["province"] == "Other" else "no_polygon_unit"
            out.append(dict(base, shape_id="", adm2_ids="", unit_name=r["district"],
                            province=r["province"], allocation_status=status))
    return out


def check(adm1, adm2):
    """The lane's closures; returns the worst relative gap."""
    worst = 0.0
    national = collections.defaultdict(float)
    for sector, fname in AIR_FILES.items():
        for r in _read(fname):
            national[(sector, r["pollutant"])] += float(r["emissions_kt"])
    a1 = collections.defaultdict(float)
    for r in adm1:
        a1[(r["sector_id"], r["pollutant"])] += float(r["emissions_kt"])
    for key, nat in national.items():
        if nat <= 0:
            continue
        gap = abs(a1[key] - nat)
        if key[0] == "agriculture":
            n = sum(1 for r in adm1 if (r["sector_id"], r["pollutant"]) == key)
            assert gap <= n * HALF_ULP["adm1"] + 1e-9, "ADM1 %s: %.6g vs national %.6g" % (key, a1[key], nat)
        else:
            assert gap / nat < RTOL, "ADM1 %s: %.6g vs national %.6g" % (key, a1[key], nat)
            worst = max(worst, gap / nat)
    a2 = collections.defaultdict(float)
    for r in adm2:
        a2[(r["sector_id"], r["pollutant"])] += float(r["emissions_kt"])
    cruise = collections.defaultdict(float)
    for r in adm1:
        if r["share_status"] == "unallocated_below_adm1":
            cruise[(r["sector_id"], r["pollutant"])] += float(r["emissions_kt"])
    for key, nat in national.items():
        if nat <= 0:
            continue
        want = nat - cruise.get(key, 0.0)
        gap = abs(a2[key] - want)
        if key[0] == "agriculture":
            n = sum(1 for r in adm2 if (r["sector_id"], r["pollutant"]) == key)
            # the copied district rows are 5 dp, but their PROVINCIAL control was the
            # 3 dp provincial table, so the bound is the coarser one
            assert gap <= n * HALF_ULP["adm2"] + 70 * HALF_ULP["adm1"] + 1e-9, "ADM2 %s: %.6g vs %.6g" % (key, a2[key], want)
        else:
            assert gap / nat < RTOL, "ADM2 %s: %.6g vs %.6g" % (key, a2[key], want)
            worst = max(worst, gap / nat)
    return worst


def main():
    adm1, adm2 = build()
    worst = check(adm1, adm2)
    for path, fields, rows in (("air_pollutants_adm1.csv", ADM1_FIELDS, adm1),
                               ("air_pollutants_adm2.csv", ADM2_FIELDS, adm2)):
        with open(asset_path(OUTPUTS, path), "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(sorted(rows, key=lambda r: tuple(r.get(k, "") for k in fields[:7])))
    print("air spatial (all sectors): %d ADM1 rows, %d ADM2 rows; worst closure %.2e"
          % (len(adm1), len(adm2), worst))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
