"""The records and tables the gas-reallocation application reads, and nothing it computes.

Every number here comes from a held record or an application table with its source beside it.
Inventory factors are read from the inventory's own files through `inventory_value`, so the
application never carries a second copy of a factor the inventory may later revise.
"""
import os

from pkinv.assets import asset_path
from pkinv.core.io import read_rows
from pkinv.paths import DATA, OUTPUTS

TABLES = asset_path(DATA, "shared", "parameters", "gas_reallocation")
NFDC = asset_path(DATA, "shared", "activity", "nfdc")
POWER = asset_path(DATA, "sectors", "power", "activity")

# The fiscal year as each record keys it. NFDC prints "2023-24"; the power station files key the
# fiscal START year (2023 = FY2023-24); the national products print "FY2023-24".
YEARS = {
    "FY2023-24": {"nfdc": "2023-24", "power": "2023", "national": "FY2023-24"},
    "FY2024-25": {"nfdc": "2024-25", "power": "2024", "national": "FY2024-25"},
}
REFERENCE_YEAR = "FY2023-24"
REPLICATION_YEAR = "FY2024-25"

MMCF_TO_M3 = 28316.846592          # 1e6 cubic feet in cubic metres (exact definition of the foot)


def table(filename):
    """One of the application's own tables, data/shared/parameters/gas_reallocation/<filename>."""
    return read_rows(os.path.join(TABLES, filename))


def inventory_value(ref):
    """(value, uncert_pct) of an inventory row named `file:key`.

    The key column is the file's first column (param or ef_id), the convention every parameter
    file in data/ follows. An unknown key raises: a reference that has stopped resolving is a
    defect, not a reason to fall back to a typed number.
    """
    path, key = ref.rsplit(":", 1)
    rows = read_rows(asset_path(os.path.dirname(DATA), path))
    first = next(iter(rows[0]))
    for row in rows:
        if row[first] == key:
            pct = row.get("uncert_pct", "")
            return float(row["value"]), (float(pct) if str(pct).strip() else 0.0)
    raise KeyError("%s has no row %s" % (path, key))


def parameters():
    """The parameter table with inventory references resolved: id -> dict(value, low, high, ...)."""
    out = {}
    for row in table("parameter_ranges.csv"):
        entry = dict(row)
        for field in ("value", "low", "high", "uncert_pct"):
            entry[field] = float(row[field]) if str(row[field]).strip() else None
        if row["inventory_ref"]:
            value, pct = inventory_value(row["inventory_ref"])
            entry["value"] = value
            if entry["uncert_pct"] is None:
                entry["uncert_pct"] = pct
        out[row["parameter_id"]] = entry
    return out


def air_register(ef_id):
    """(value, uncert_pct) of a row of the inventory's air-pollutant factor register."""
    for row in read_rows(asset_path(DATA, "shared", "parameters", "air_emission_factors.csv")):
        if row["ef_id"] == ef_id:
            return float(row["value"]), float(row["uncert_pct"] or 0)
    raise KeyError(ef_id)


def air_factors():
    """factor_set -> pollutant -> dict(value, low, high, unit, so2_method) or None where NE."""
    out = {}
    for row in table("air_factors.csv"):
        entry = None
        if str(row["value"]).strip():
            entry = {"value": float(row["value"]), "low": float(row["low"]),
                     "high": float(row["high"]), "unit": row["unit"], "source": row["source"]}
        elif row["so2_method"]:
            entry = {"so2_method": row["so2_method"], "source": row["source"]}
        if entry is not None and row["so2_method"]:
            entry["so2_method"] = row["so2_method"]
        out.setdefault(row["factor_set"], {})[row["pollutant"]] = entry
    return out


def scope_plants():
    return [r for r in table("scope_plants.csv") if r["in_scope"] == "yes"]


def plant_gas(year):
    """{plant: {"feed": MMCF, "fuel": MMCF, "suppliers": {...}}} for the in-scope plants.

    FY2023-24 is read from Annex-28 (plant x supplier x month, feed and fuel); FY2024-25 from
    Table 40 (plant x supplier, the year's feed and fuel). Both are NFDC prints of plant meters.
    """
    key = YEARS[year]["nfdc"]
    names = {r["nfdc_plant"] for r in scope_plants()}
    out = {n: {"feed": 0.0, "fuel": 0.0, "suppliers": {}} for n in names}
    if year == REFERENCE_YEAR:
        rows = read_rows(os.path.join(NFDC, "afr2025_fertilizer_gas_monthly.csv"))
        for r in rows:
            if r["fiscal_year"] != key or r["plant"] not in names:
                continue
            leg = r["consumption"].strip().lower()
            mmcf = float(r["mmcf"] or 0)
            out[r["plant"]][leg] += mmcf
            out[r["plant"]]["suppliers"][r["gas_supplier"]] = (
                out[r["plant"]]["suppliers"].get(r["gas_supplier"], 0.0) + mmcf)
        source = "NFDC AFR 2024-25 Annex-28 (afr2025_fertilizer_gas_monthly.csv)"
    else:
        rows = read_rows(os.path.join(NFDC, "afr2025_fertilizer_gas_by_plant.csv"))
        for r in rows:
            if r["fiscal_year"] != key or r["plant"] not in names:
                continue
            out[r["plant"]]["feed"] += float(r["feed_mmcf"])
            out[r["plant"]]["fuel"] += float(r["fuel_mmcf"])
            out[r["plant"]]["suppliers"][r["gas_supplier"]] = float(r["total_mmcf"])
        source = "NFDC AFR 2024-25 Table 40 (afr2025_fertilizer_gas_by_plant.csv)"
    for name, entry in out.items():
        if entry["feed"] <= 0:
            raise ValueError("%s %s: no feed gas printed" % (name, year))
        entry["source"] = source
    return out


def plant_urea(year):
    """{plant: urea production kt} for the in-scope plants (NFDC Table 1, production by manufacturer)."""
    key = YEARS[year]["nfdc"]
    by_maker = {r["manufacturer"]: r["nfdc_plant"] for r in scope_plants()}
    out = {}
    for r in read_rows(os.path.join(NFDC, "afr2025_production_by_manufacturer.csv")):
        if r["fiscal_year"] == key and r["product"] == "Urea" and r["manufacturer"] in by_maker:
            out[by_maker[r["manufacturer"]]] = float(r["production_000t"])
    missing = set(by_maker.values()) - set(out)
    if missing:
        raise ValueError("%s: no urea production printed for %s" % (year, sorted(missing)))
    return out


def _matches(label, stations):
    return any(label.startswith(s[:-1]) if s.endswith("*") else label == s for s in stations)


def pathways():
    return {r["pathway_id"]: r for r in table("pathways.csv")}


def station_records(pathway, year=REFERENCE_YEAR):
    """Each station of a receiving or displaced pathway with its printed fuel, generation and heat rate.

    Returns a list of dicts: station, fuel quantity and unit, generation GWh (all from the ledger rows
    of the pathway's fuel), and the SoIR net efficiency (fraction, LHV) where printed. A station with
    a ledger row and no printed heat rate, or the reverse, is kept with the missing field None.
    """
    entry = pathways()[pathway]
    stations = [s for s in entry["stations"].split(";") if s]
    fuels = [f.strip() for f in entry["ledger_fuel"].split(";") if f.strip()]
    key = YEARS[year]["power"]
    found = {}
    for r in read_rows(os.path.join(POWER, "plant_fuel_ledger.csv")):
        if r["fiscal_year"] != key or not _matches(r["plant"], stations):
            continue
        fuel = (r["fuel"].strip() + " " + r["fuel_origin"].strip()).strip()
        if fuel not in fuels and r["fuel"].strip() not in fuels:
            continue
        rec = found.setdefault(r["plant"], {"station": r["plant"], "legs": [], "eff_net": []})
        rec["legs"].append({"fuel": fuel, "quantity": float(r["quantity"]),
                            "unit": r["quantity_unit"].strip(),
                            "gwh": float(r["net_generation_GWh"] or 0)})
    for r in read_rows(os.path.join(POWER, "plant_heat_rates.csv")):
        if r["fiscal_year"] != key or not _matches(r["plant"], stations):
            continue
        eff = float(r["eff_net_pct"] or 0)
        if eff > 0:
            rec = found.setdefault(r["plant"], {"station": r["plant"], "legs": [], "eff_net": []})
            rec["eff_net"].append(eff / 100.0)
    return [found[k] for k in sorted(found)]


def station_capacity_mw(pathway):
    """Operating capacity (MW) of a pathway's stations from the GEM gas/oil tracker, by name match.

    Used only to state an annual energy ceiling; availability and dispatch are not modelled.
    """
    words = {"R1": ("Balloki", "Bhikki", "Haveli Bahadur Shah", "Trimmu"),
             "R2": ("Uch power", "Foundation", "Orient", "Saif", "Sapphire", "Halmore"),
             "R3": ("Guddu",)}.get(pathway)
    if not words:
        return None
    total = 0.0
    for r in read_rows(os.path.join(POWER, "gem_gas_oil_pak.csv")):
        if r["Status"] == "operating" and any(w in r["Plant name"] for w in words):
            total += float(r["Capacity (MW)"] or 0)
    return total


def fossil_grid_average(year=REFERENCE_YEAR):
    """(t CO2e AR5 per MWh, CO2e Mt, fossil GWh): the inventory's grid combustion over CPPA-G fossil GWh.

    The D5 comparator only. The inventory's grid row excludes K-Electric, so the denominator is the
    CPPA-G system's fossil generation printed in SoIR Table 17.
    """
    co2e = 0.0
    for r in read_rows(os.path.join(OUTPUTS, "pakemis_annual_fy2015_16_fy2024_25.csv")):
        if (r["period_label"] == YEARS[year]["national"] and r["category"] == "Electricity and heat production"
                and r["configuration_id"] == "S_TAN" and r["grain"] == "category_gas"):
            co2e += float(r["co2e_Mt_AR5"])
    gwh = sum(float(r["gwh_net"]) for r in read_rows(os.path.join(POWER, "generation_by_fuel.csv"))
              if r["fiscal_year"] == YEARS[year]["power"] and r["system"] == "CPPA-G")
    if not co2e or not gwh:
        raise ValueError("no grid row or no CPPA-G generation for %s" % year)
    return co2e * 1e6 / (gwh * 1e3), co2e, gwh


def nfdc_ogra_agreement():
    """The inventory's FY2023-24 cross-source check of fertilizer gas (NFDC plant meters vs OGRA)."""
    return read_rows(os.path.join(OUTPUTS, "ippu_fertilizer_gas_cross_source_2024.csv"))
