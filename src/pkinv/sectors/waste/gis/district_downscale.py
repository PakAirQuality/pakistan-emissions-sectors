"""District allocation of the waste province totals - an ORIGIN allocation, declared.

THE MECHANISM. Each category's provincial total (from the sector's own proxy-declared
provincial allocation: waste_disposed_pop for SWDS, waste_burned_pop for open burning,
wastewater_load for wastewater) is spread over the province's districts by total census
population. Sums to the province total exactly by construction; the check asserts it
at 1e-9 and raises otherwise - the residential district product's harness, copied.

WHAT THIS LOCATES, EXACTLY. The ORIGIN of the waste and wastewater - where the
generating people live - never the release: SWDS methane is emitted at landfills and
dumps, wastewater methane along drains and at treatment works, burning at burn sites,
none of which this inventory holds allocation-grade geometry for. The 56 OSM landfill
polygons in data/gis/landfills/ are a prospective asset seed (four real named metro
sites), far too sparse to carry an allocation; the waste paper's section 6.4 states
the distinction and this file's basis column repeats it on every row.

POPULATION VINTAGE. The census interpolation runs to 2023; FY2023-24 emissions ride
the 2023 district populations, the same declared half-year offset the residential
product carries. 'Other' (GB/AJK/ICT) stays a province-level residual row per stream.

Usage:  python3 -m pkinv.sectors.waste.gis.district_downscale
Writes: outputs/waste_district_2024.csv
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import csv
import os

from pkinv.core.downscale import allocate_rows
from pkinv.core.geography import PROVINCES
from pkinv.paths import DATA, OUTPUTS
from pkinv.sectors.waste import downscale, engine
from pkinv.sectors.waste.data import WasteData

POP_CSV = asset_path(DATA, "activity", "waste", "population_district.csv")
POP_YEAR = "2023"
NAMED = ["Punjab", "Sindh", "Khyber Pakhtunkhwa", "Balochistan"]
OTHER = "Other"
TOL = 1e-9

BASIS = ("total census district population - an ORIGIN allocation; release geometry "
         "(landfills, drains, treatment works, burn sites) is not held, see "
         "data/gis/landfills and the waste paper section 6.4")


def district_population():
    """{province: {district: pop_total}} for the reference year, named provinces."""
    out = {}
    for r in _activity_rows(POP_CSV, comments=False):
        if r["year"] != POP_YEAR or r["province"] not in NAMED:
            continue
        d = out.setdefault(r["province"], {})
        d[r["district"]] = d.get(r["district"], 0.0) + float(r["pop_total"])
    return out


def province_stream_totals(data=None):
    """{(province, category): Mt} from the sector's own provincial allocation."""
    data = data or WasteData()
    comps = engine.build_components(data)
    rows = allocate_rows(comps, downscale.load_shares(), downscale.proxy_for, PROVINCES)
    out = {}
    for r in rows:
        key = (r["province"], r["category"])
        out[key] = out.get(key, 0.0) + r["co2e_Mt_AR5"]
    return out


def district_rows(data=None):
    pop = district_population()
    totals = province_stream_totals(data)
    rows = []
    for (province, category), total in sorted(totals.items()):
        if province == OTHER:
            rows.append({"district": "Other (GB/AJK/ICT residual)",
                         "province": OTHER, "stream": category,
                         "co2e_Mt_AR5": total,
                         "basis": "province-level residual; the shared district "
                                  "population file does not resolve its districts"})
            continue
        districts = pop[province]
        prov_pop = sum(districts.values())
        for district, p in sorted(districts.items()):
            rows.append({"district": district, "province": province,
                         "stream": category,
                         "co2e_Mt_AR5": total * p / prov_pop,
                         "basis": BASIS})
    return rows


def check(rows, data=None):
    """Per-(province, stream) district sums equal the provincial allocation, or raise."""
    totals = province_stream_totals(data)
    got = {}
    for r in rows:
        key = (r["province"], r["stream"])
        got[key] = got.get(key, 0.0) + r["co2e_Mt_AR5"]
    worst = max(abs(got[k] - v) for k, v in totals.items())
    if worst > TOL:
        raise ValueError("waste district allocation does not reconcile: worst "
                         "per-(province, stream) residual %.3e Mt" % worst)
    return worst


def main():
    data = WasteData()
    rows = district_rows(data)
    check(rows, data)
    path = asset_path(OUTPUTS, "waste_district_%d.csv" % data.year)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["district", "province", "stream",
                                          "co2e_Mt_AR5", "basis"])
        w.writeheader()
        for r in rows:
            w.writerow({**r, "co2e_Mt_AR5": round(r["co2e_Mt_AR5"], 7)})
    n_districts = len({r["district"] for r in rows})
    top = sorted(((r["district"], r["co2e_Mt_AR5"]) for r in rows
                  if r["province"] != OTHER), key=lambda kv: -kv[1])
    by_district = {}
    for r in rows:
        by_district[r["district"]] = by_district.get(r["district"], 0.0) \
            + r["co2e_Mt_AR5"]
    lead = sorted(by_district.items(), key=lambda kv: -kv[1])[:3]
    print("waste district (ORIGIN) -> %s: %d rows, %d districts; top %s"
          % (os.path.basename(path), len(rows), n_districts,
             ", ".join("%s %.2f" % (d, v) for d, v in lead)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
