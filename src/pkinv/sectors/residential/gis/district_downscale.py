"""District allocation of the residential province totals - the survey's urban/rural
rates on the census's urban/rural people.

THE MECHANISM. Each stream's province total is first split urban/rural by the HIES
strata (the survey's own weighted quantities per province and region), then each
portion is spread over the province's districts by that portion's census population:
district = province_total x [urban_share x urban_pop(d)/urban_pop(p)
                             + rural_share x rural_pop(d)/rural_pop(p)].
Firewood concentrates where the survey says rural households burn it AND where the
census says rural people live - a dasymetric split with both factors measured, unlike a
flat population spread. Sums to the province total exactly by construction, and the
check asserts it.

WHAT THIS IS NOT. No district fuel survey exists (HIES is representative at province x
region, not district), so these are allocations, not observations - the same honest
label agriculture's district layer carries. The Census 2023 district cooking-fuel
tables (data/data_gaps.csv, residential-provincial-allocation) would upgrade the
within-province distribution from population-prevalence to fuel-prevalence; until then
the strata rates are the best measured within-province lever.

POPULATION VINTAGE. The census interpolation (data/activity/waste/
population_district.csv, shared with the waste sector) runs to 2023; FY2023-24
emissions ride the 2023 district populations, a half-year offset stated rather than
smoothed. 'Other' (GB/AJK/ICT) stays a province-level residual, matching the grid's
convention - HIES measures its strata, but the shared district population file does
not resolve its districts.

Usage:  python3 -m pkinv.sectors.residential.gis.district_downscale
Writes: outputs/residential_district_2024.csv
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import csv
import os

from pkinv.core.geography import PROVINCES
from pkinv.paths import DATA, OUTPUTS
from pkinv.sectors.residential import downscale, engine, hies
from pkinv.sectors.residential.data import ResidentialData

POP_CSV = asset_path(DATA, "activity", "waste", "population_district.csv")
# The population vintages the district split is read for when no period is named: the
# reference period's own, which rc45 makes the MEAN of the two calendar years a fiscal year
# spans rather than the one it opens in. Population is a stock and a fiscal year's midpoint
# is 1 January, exactly between two mid-year estimates. Held here as the default so the
# sector runner and the cube's reference period read the identical panel.
POP_YEARS = (("2023", 0.5), ("2024", 0.5))
NAMED = ["Punjab", "Sindh", "Khyber Pakhtunkhwa", "Balochistan"]
OTHER = "Other"
TOL = 1e-9

# stream first-word -> HIES fuel for the urban/rural split; None -> total population
STRATA_FUEL = {"Firewood": "firewood", "Dung": "dung_cake", "LPG": "lpg",
               "Natural": "natural_gas", "Crop": None, "Kerosene": None,
               "Charcoal": None, "Coal": None, "Generators": None}


def district_population(population_years=None):
    """{province: {district: (rural, urban)}} at a period's midpoint, the reference by default.

    The same file waste reads and on the same terms: one row per district per year from 2000
    to 2024, weighted across the two calendar years a fiscal period spans. The sector runner
    passes nothing and gets the reference period's own pair, so its product and the cube's
    reference panel are one panel and not two.
    """
    weights = dict(population_years or POP_YEARS)
    out = {}
    for r in _activity_rows(POP_CSV, comments=False):
        weight = weights.get(r["year"])
        if not weight or r["province"] not in NAMED:
            continue
        rural, urban = out.setdefault(r["province"], {}).get(r["district"], (0.0, 0.0))
        out[r["province"]][r["district"]] = (rural + float(r["pop_rural"]) * weight,
                                             urban + float(r["pop_urban"]) * weight)
    return out


def _region_split(fuel, prov):
    """(rural_share, urban_share) of a fuel's quantity within one province, HIES."""
    shares = hies.strata_shares(fuel)
    prov_names = {prov} if prov != OTHER else downscale._OTHER
    rural = sum(v for (p, reg), v in shares.items()
                if p in prov_names and reg == "rural")
    urban = sum(v for (p, reg), v in shares.items()
                if p in prov_names and reg == "urban")
    tot = rural + urban
    return (rural / tot, urban / tot) if tot > 0 else (0.5, 0.5)


def district_rows(data=None, comps=None, population_years=None):
    """The district split. `population_years` moves ONLY the district population that splits a
    province - the component magnitudes and the HIES strata are the reference year's either
    way, because that is what this sector has. The cube rescales the magnitudes to each
    period's own provincial control, so what a period needs from here is its geography."""
    data = data or ResidentialData()
    comps = comps or engine.build_components(data)
    shares = downscale.load_shares()
    pop = district_population(population_years)

    # province totals per stream, from the same allocation the provincial file uses
    prov_totals = {}
    for c in comps:
        proxy = downscale.proxy_for(c)
        word = c["subitem"].split()[0]
        for prov in PROVINCES:
            key = (word, prov)
            prov_totals[key] = (prov_totals.get(key, 0.0)
                                + c["co2e_Mt_AR5"] * shares[proxy][prov])

    rows = []
    for (word, prov), total in sorted(prov_totals.items()):
        if prov == OTHER or total == 0.0:
            if total != 0.0:
                rows.append({"district": "Other (GB/AJK/ICT residual)",
                             "province": OTHER, "stream": word,
                             "co2e_Mt_AR5": total,
                             "basis": "province-level residual; the shared district "
                                      "population file does not resolve GB/AJK/ICT"})
            continue
        fuel = STRATA_FUEL[word]
        if fuel is not None:
            rural_share, urban_share = _region_split(fuel, prov)
            basis = ("HIES %s urban/rural split x census district population"
                     % fuel)
        else:
            rural_share, urban_share = None, None
            basis = "total census district population (no reliable strata)"
        dists = pop[prov]
        p_rural = sum(r for r, _u in dists.values())
        p_urban = sum(u for _r, u in dists.values())
        p_tot = p_rural + p_urban
        for d, (r_pop, u_pop) in sorted(dists.items()):
            if fuel is not None:
                frac = (rural_share * (r_pop / p_rural if p_rural else 0.0)
                        + urban_share * (u_pop / p_urban if p_urban else 0.0))
            else:
                frac = (r_pop + u_pop) / p_tot
            if frac > 0:
                rows.append({"district": d, "province": prov, "stream": word,
                             "co2e_Mt_AR5": total * frac, "basis": basis})
    return rows, prov_totals


def check(rows, prov_totals):
    """Per (province, stream): sum of districts == the province allocation, exactly."""
    agg = {}
    for r in rows:
        agg[(r["stream"], r["province"])] = (agg.get((r["stream"], r["province"]), 0.0)
                                             + r["co2e_Mt_AR5"])
    worst = 0.0
    for key, total in prov_totals.items():
        if total == 0.0:
            continue
        worst = max(worst, abs(agg.get(key, 0.0) - total))
    if worst > TOL:
        raise AssertionError("district allocation does not reconcile: worst gap %.3g Mt"
                             % worst)
    return worst


# The canonical district system - see core.adm2. Until rc14 this module used only
# its normaliser and painted by raw string match, which lost 27 of 126 polygons
# to spellings, renames, census splits and the GB/AJK/ICT residual; every one of
# those names resolves through the crosswalk, so the bypass WAS the defect.
from pkinv.core import adm2 as _adm2
from pkinv.core.adm2 import normalise as _norm  # noqa: E402
from pkinv.core.io import write_table


def choropleth(rows):
    """Paint each boundary polygon through the canonical ADM2 crosswalk.

    Every CSV row resolves to a stable adm2_id; every polygon's id set comes from
    shape_to_adm2(), so a polygon carrying several census units (Karachi's seven,
    the Chitral/Kohistan splits) paints their SUM. The twelve GB/AJK/ICT polygons
    are covered by the single residual row, which cannot honestly be split among
    them - they stay unpainted as a DECLARED class, not a matching failure. The
    audit CSV records every polygon's disposition; the map is presentation and
    the CSV stays the product."""
    try:
        import numpy as np
        from pkinv.core.gis import render
        from pkinv.core.gis.grid import build_grid
    except ImportError:
        return None
    grid = build_grid()
    if grid.district_id is None:
        return None
    canonical = _adm2.load_canonical()
    a2s = _adm2.adm2_to_shape()
    s2a = _adm2.shape_to_adm2()
    agg = {}
    for r in rows:
        uid = _adm2.resolve(r["district"])
        agg[uid] = agg.get(uid, 0.0) + r["co2e_Mt_AR5"]
    arr = np.zeros((grid.height, grid.width), dtype=np.float64)
    audit = []
    painted = 0
    for did, dname in enumerate(grid.districts):
        shape_id = a2s[_adm2.resolve(dname)]
        adm2_ids = s2a[shape_id]
        vals = [agg[a] for a in adm2_ids if a in agg]
        if vals:
            m = grid.district_mask(did)
            if int(m.sum()) > 0:
                arr[m] = sum(vals)
            painted += 1
            audit.append({"shape_id": shape_id, "shape_name": dname,
                          "adm2_ids": ";".join(adm2_ids),
                          "value_Mt_co2e": round(sum(vals), 7),
                          "status": "painted",
                          "reason": ("sum of %d census units on one polygon"
                                     % len(vals) if len(vals) > 1
                                     else "one census unit, one polygon")})
        elif all(canonical[a]["province_id"] == "Other" for a in adm2_ids):
            audit.append({"shape_id": shape_id, "shape_name": dname,
                          "adm2_ids": ";".join(adm2_ids),
                          "value_Mt_co2e": "",
                          "status": "residual_declared",
                          "reason": "covered by the single GB/AJK/ICT residual "
                                    "row; splitting it among these polygons "
                                    "would manufacture an allocation the shared "
                                    "population file cannot support"})
        else:
            raise AssertionError("polygon %r has allocation rows the crosswalk "
                                 "cannot reach - the 99-of-126 defect returning"
                                 % dname)
    audit_path = asset_path(OUTPUTS,
                              "residential_district_map_audit_2024.csv")
    write_table(audit_path, ["shape_id", "shape_name", "adm2_ids",
                                          "value_Mt_co2e", "status", "reason"], audit)
    figdir = asset_path(OUTPUTS, "figures")
    os.makedirs(figdir, exist_ok=True)
    path = asset_path(figdir, "residential_district_map.png")
    render.plot_total(path, arr, grid,
                      "Residential CO2e by district, FY2023-24 (reference)",
                      cbar_label="District total (Mt CO2e, log scale)",
                      zero_label="grey: GB/AJK/ICT units, covered by the single "
                                 "residual row (declared, not district-allocated)")
    print("  district choropleth: %d of %d polygons painted, %d residual-declared"
          " -> %s" % (painted, len(grid.districts), len(audit) - painted,
                      os.path.basename(path)))
    return path


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    data = ResidentialData()
    rows, prov_totals = district_rows(data)
    check(rows, prov_totals)
    choropleth(rows)
    with open(asset_path(OUTPUTS, "residential_district_%d.csv" % data.year),
              "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["district", "adm2_id", "province",
                                          "stream", "co2e_Mt_AR5", "basis"])
        w.writeheader()
        for r in rows:
            w.writerow({**r, "adm2_id": _adm2.resolve(r["district"]),
                        "co2e_Mt_AR5": round(r["co2e_Mt_AR5"], 7)})
    n_dist = len({r["district"] for r in rows})
    top = {}
    for r in rows:
        top[r["district"]] = top.get(r["district"], 0.0) + r["co2e_Mt_AR5"]
    lead = sorted(top.items(), key=lambda kv: -kv[1])[:3]
    print("Residential district allocation: %d districts, reconciled exactly; "
          "largest: %s" % (n_dist, ", ".join("%s %.2f Mt" % kv for kv in lead)))


if __name__ == "__main__":
    main()
