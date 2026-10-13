"""The coal fleet's commissioning check: does any period place coal mass on a station
before GEM says it started, or after GEM says it retired?

WHY. The 23rd review read the power geography as "the FY2023-24 station pattern applied to
every year", under which Sahiwal (2017), Hubco (2019) and the Thar stations (2019-2023)
would carry FY2015-16 coal they did not burn. The weight registry says otherwise - every
power_coal stream-year is `own_period_pattern` with weight_period equal to the period
(pakemis_spatial_weights_by_year.csv) - but the registry records WHICH pattern, not whether
the pattern's stations existed. This module joins each period's coal station pool (the
plant-fuel ledger where it reaches, the generation panel before it - the same two pools
grid_cube.located_activity_share reads) to Global Energy Monitor's unit start and retired
years and prints the exposure per period: the coal mass placed on a station outside its
GEM operating window. The number is expected to be ZERO; the product exists so that the
claim is a measurement a reader can reproduce rather than a sentence.

THE PROVINCIAL SIDE MOVED OUT AT rc66. Through rc65 this module also printed a second table,
pakemis_power_fixed_pattern_exposure.csv: the coal the FIXED reference-year provincial vector
booked against what each period's own stations would book. It measured a defect (up to 11.6 Mt
CO2e in one province-year) that the release declared and had not repaired. The repair is
pkinv.sectors.power.province_panel, which gives every fuel-year its own stations, and the
record of what moved is outputs/pakemis_power_provincial_basis_by_year.csv
(pkinv.report.power_provincial_basis). With the vector no longer fixed there is no exposure to
print, and the table is retired. What stays here is the station-level check: is any coal
placed on a station outside its GEM operating window?

COMPARATOR ONLY. Nothing here enters a total, a factor or an allocation.

Usage:  python3 -m pkinv.report.power_station_status
Writes: outputs/pakemis_power_station_status.csv       station x period
"""
import csv
import io
import os

from pkinv.assets import asset_path
from pkinv.core.io import write_table
from pkinv.paths import DATA, OUTPUTS
from pkinv.report.gem_audit import GEM_TO_LEDGER

# gem_audit declares the correspondence for OPERATING units only. The generation panel's
# FY2015-16 coal is GENCO's FBC Lakhra, which GEM carries as "Lakhra power station"
# (three 50 MW units, start 1995-96, status mothballed, no retired year). Declared here so
# the first panel year has a window to check against; the pairing was checked by site.
EXTRA_CORRESPONDENCE = {"Lakhra power station": "FBC Lakhra"}

GEM_COAL = asset_path(DATA, "activity", "power", "gem_coal_pak.csv")
PERIODS = asset_path(DATA, "periods.csv")
OUT_STATUS = os.path.join(OUTPUTS, "pakemis_power_station_status.csv")

STATUS_FIELDS = ("period_id", "station", "province", "province_source", "pool",
                 "pool_quantity", "pool_unit", "pool_share", "gem_plant", "gem_units",
                 "gem_status", "gem_start_year", "gem_retired_year", "fiscal_start_year",
                 "window_check", "note")


def _csv(path):
    with io.open(path, encoding="utf-8") as handle:
        return list(csv.DictReader(line for line in handle if not line.startswith("#")))


def _gem_windows():
    """{ledger plant string: (gem plant, n units, status, min start, max retired)} over the
    declared GEM<->NEPRA correspondence. A plant's window opens with its FIRST unit and
    closes with its LAST retired unit (empty while any unit is unretired)."""
    mapping = dict(GEM_TO_LEDGER, **EXTRA_CORRESPONDENCE)
    by_plant = {}
    for r in _csv(GEM_COAL):
        if r["Plant name"] not in mapping:
            continue
        key = mapping[r["Plant name"]]
        rec = by_plant.setdefault(key, {"gem_plant": r["Plant name"], "units": 0,
                                        "status": set(), "start": [], "retired": [],
                                        "unretired": False,
                                        "province": r["Subnational unit (province, state)"]})
        rec["units"] += 1
        rec["status"].add(r["Status"])
        if r["Start year"].strip():
            rec["start"].append(int(float(r["Start year"])))
        if r["Retired year"].strip():
            rec["retired"].append(int(float(r["Retired year"])))
        else:
            rec["unretired"] = True
    out = {}
    for key, rec in by_plant.items():
        start = min(rec["start"]) if rec["start"] else None
        retired = None if rec["unretired"] or not rec["retired"] else max(rec["retired"])
        out[key] = (rec["gem_plant"], rec["units"], "|".join(sorted(rec["status"])),
                    start, retired, rec["province"].strip())
    return out


def _station_province(station, window):
    """(province, source): the curated station record where it has one, else GEM's own
    subnational field - a record either way, never the raster cell."""
    from pkinv.report.grid_cube import _curated_station_provinces
    from pkinv.sectors.power.plant_names import plant_key
    curated = _curated_station_provinces().get(plant_key(station))
    if curated:
        return curated, "plant_locations.csv"
    if window and window[5]:
        return window[5], "gem_coal_pak.csv"
    return "", "unlocated"


RECONCILIATION = os.path.join(OUTPUTS, "pakemis_power_fuel_reconciliation.csv")
LANE_TOLERANCE = 0.10  # a commissioning lane under a tenth of the period's panel is noted, not pooled


def _pool(period):
    """(pool name, {ledger plant string: quantity}, unit, note) for the period's coal stations.

    ENERGY WHERE THE RECONCILIATION HAS IT. pakemis_power_fuel_reconciliation.csv books
    every enumerated coal station's energy (TJ, booked basis) per period, which is the
    basis the fixed provincial vector was measured on - so a pool in TJ reproduces the
    vector in the reference year up to the vector's own calorific choices, and the
    reference-year row is the calibration a reader scales the other years by. A pool in
    tonnes would overweight Thar lignite and manufacture a difference in every year.

    THE GENERATION PANEL FOR THE TWO COMMISSIONING YEARS. FY2016-17 and FY2017-18 carry
    their coal as a reconstructed "commissioning lane" with no per-station split, so the
    panel's fuel-labelled GWh (grid_cube._panel_fuel_ledger, the pool the cube itself uses
    for those years) stands in. A lane smaller than LANE_TOLERANCE of the period's panel
    (FY2018-19, FY2021-22) is noted and left out of the pool."""
    from pkinv.report import grid_cube
    from pkinv.sectors.power.plant_names import plant_key
    names = {plant_key(v): v for v in list(GEM_TO_LEDGER.values())
             + list(EXTRA_CORRESPONDENCE.values())}
    energy, lane_gwh = {}, 0.0
    for r in _csv(RECONCILIATION):
        if r["period_id"] != period.period_id or r["fuel"] != "Coal":
            continue
        if r["plant_coverage_class"] == "reconstructed lane":
            rule = r["reconstruction_rule"]
            if "mass interval = " in rule:
                lane_gwh += float(rule.split("mass interval = ")[1].split(" GWh")[0])
            continue
        if r["plant"].startswith("ALL STATIONS") or not r["energy_TJ_booked_basis"]:
            continue
        key = names.get(plant_key(r["plant"]), r["plant"])
        energy[key] = energy.get(key, 0.0) + float(r["energy_TJ_booked_basis"])
    panel = grid_cube._panel_fuel_ledger(("Coal",), period)
    panel = {names.get(k, " ".join(k)): v for k, v in panel.items()}
    panel_total = sum(panel.values())
    if energy and (lane_gwh == 0 or lane_gwh < LANE_TOLERANCE * panel_total):
        note = ("" if lane_gwh == 0 else
                "a commissioning lane of %.2f GWh (%.1f%% of the panel) has no station split "
                "and is not in the pool" % (lane_gwh, 100 * lane_gwh / panel_total))
        return "reconciliation_energy", energy, "TJ", note
    return ("generation_panel", panel, "GWh",
            "the period's coal is a reconstructed commissioning lane (%.2f GWh) with no "
            "per-station energy; the panel's fuel-labelled generation is the pool" % lane_gwh)


def build():
    from pkinv.report.grid_cube import period_keys
    windows = _gem_windows()
    status_rows = []
    for p in _csv(PERIODS):
        pid = p["period_id"]
        period = period_keys(pid)
        fy = int(p["fiscal_start_year"])
        pool, quantities, unit, pool_note = _pool(period)
        total = sum(quantities.values())
        for station, q in sorted(quantities.items()):
            w = windows.get(station)
            share = (q / total) if total > 0 else 0.0
            province, province_source = _station_province(station, w)
            if w is None:
                check, note = "no_gem_window", ("no declared GEM correspondence; the station "
                                                "is a NEPRA account GEM's coal tracker does "
                                                "not carry under that name")
                gem = ("", "", "", None, None, "")
            else:
                gem = w
                start, retired = w[3], w[4]
                # a fiscal year starting 1 July of `fy` overlaps calendar years fy and fy+1
                if start is not None and start > fy + 1:
                    check, note = "before_gem_start", "coal placed before the first unit's start year"
                elif retired is not None and retired < fy:
                    check, note = "after_gem_retired", "coal placed after the last unit retired"
                else:
                    check, note = "inside_window", ""
            status_rows.append({
                "period_id": pid, "station": station, "province": province,
                "province_source": province_source, "pool": pool,
                "pool_quantity": "%.3f" % q, "pool_unit": unit,
                "pool_share": "%.6f" % share, "gem_plant": gem[0], "gem_units": gem[1],
                "gem_status": gem[2],
                "gem_start_year": "" if gem[3] is None else gem[3],
                "gem_retired_year": "" if gem[4] is None else gem[4],
                "fiscal_start_year": fy, "window_check": check, "note": note})
    return status_rows


def main():
    status_rows = build()
    write_table(OUT_STATUS, STATUS_FIELDS, status_rows, banner=(
        "# Coal stations carrying each period's coal geography, joined to GEM unit start and",
        "# retired years (pkinv.report.power_station_status). COMPARATOR ONLY.",))
    flagged = [r for r in status_rows if r["window_check"] in ("before_gem_start", "after_gem_retired")]
    print("power_station_status: %d station-periods, %d outside the GEM window"
          % (len(status_rows), len(flagged)))


if __name__ == "__main__":
    main()
