"""The transport class split's parameters, written from the engine as two CSVs.

Every quantity that determines the class split, in one place: per-class registered stock,
survival-weighted active fleet, annual kilometres, survival parameters, fuel splits,
district-cell counts, and the resulting within-fuel vehicle-kilometre weights - including the
two-wheeler share of the petrol control and the off-road partition share with its actual
numerator and denominator. Computed from the engine at generation time.

Usage:  python3 scripts/make_transport_class_table.py
Writes: outputs/transport_class_parameters_<year>.csv,
        outputs/transport_class_fuel_weights_<year>.csv
"""
import csv
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.assets import asset_path

from pkinv.sectors.transport import fleet, road  # noqa: E402
from pkinv.sectors.transport.data import TransportData  # noqa: E402

OUT_CSV = asset_path(ROOT, "outputs",
                       "transport_class_parameters_%d.csv" % TransportData().year)
OUT_WEIGHTS_CSV = asset_path(ROOT, "outputs",
                               "transport_class_fuel_weights_%d.csv" % TransportData().year)

LABELS = {"2W": "Two-wheelers", "3W": "Three-wheelers", "4W1": "Cars (small)",
          "4W2": "Cars (large/SUV)", "4WT": "Taxis", "LDV": "Light duty",
          "BUS": "Buses", "HDV": "Heavy duty", "NRV": "Off-road (mixed)"}


def compute(data=None):
    data = TransportData() if data is None else data
    # The FLEET year, not the control year: the registration panel's last year is
    # partial (see TransportData.fleet_year), and asking for it drops whole vehicle
    # classes out of the table with no error.
    year = data.fleet_year()
    per_class = {}
    for cls in fleet.CLASSES:
        per_class[cls] = {"active": 0.0, "registered": 0.0, "cells": 0,
                          "capped": 0}
    for province, district, cls in data.cells(year):
        series = data.stock_series(province, district, cls)
        if year not in series:
            continue
        active, was_capped = fleet.active_fleet(
            series, data.p("weibull_beta_%s" % cls),
            data.p("weibull_life_%s" % cls), year)
        per_class[cls]["active"] += active
        per_class[cls]["registered"] += series[year]
        per_class[cls]["cells"] += 1
        per_class[cls]["capped"] += 1 if was_capped else 0

    vkt, _cells, _capped = road.effective_vkt(data, year)
    shares = road._shares(data, vkt)
    rows = []
    for cls in fleet.CLASSES:
        d = per_class[cls]
        split = data.split_for(cls, year)
        rows.append({
            "ei_class": cls, "label": LABELS[cls],
            "active_fleet": round(d["active"], 1),
            "registered": round(d["registered"], 0),
            "active_over_registered": round(d["active"] / d["registered"], 4)
            if d["registered"] else "",
            "vkt_km_per_vehicle": data.vkt_for(cls, year),
            "weibull_beta": data.p("weibull_beta_%s" % cls),
            "weibull_life_yr": data.p("weibull_life_%s" % cls),
            "fuel_split": "; ".join("%s %.4g" % (f, s)
                                    for f, s in sorted(split.items()) if s),
            "district_cells": d["cells"], "cells_capped": d["capped"],
        })
    # The published weights are energy, not distance: the MJ/km midpoint is printed
    # beside the kilometres it multiplies, so a reader can rebuild every weight.
    weights = [{"ei_class": cls, "fuel": f,
                "vkt_vehicle_km": round(km, 0),
                "mjkm_mid": data.mjkm(cls, f),
                "energy_MJ": round(km * data.mjkm(cls, f), 0),
                "within_fuel_weight": round(shares[(cls, f)], 6)}
               for (cls, f), km in sorted(vkt.items())]
    energy = {k: v * data.mjkm(k[0], k[1]) for k, v in vkt.items() if k[1] == "Diesel"}
    off_mj = sum(v for k, v in energy.items() if k[0] == road.OFF_ROAD)
    on_mj = sum(v for k, v in energy.items() if k[0] != road.OFF_ROAD)
    derivation = {"off_MJ": off_mj, "on_diesel_MJ": on_mj,
                  "share": off_mj / (off_mj + on_mj),
                  "off_road_TJ": road.off_road_TJ(data)}
    return rows, weights, derivation


def main():
    rows, weights, der = compute()
    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    # rc41 (D-1): one table per file. The within-fuel weights used to follow the class
    # table in the SAME csv after a blank line - a second header eighteen rows down that
    # every csv reader parsed as eighteen malformed rows of the first table.
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    with open(OUT_WEIGHTS_CSV, "w", newline="", encoding="utf-8") as f:
        w2 = csv.DictWriter(f, fieldnames=list(weights[0].keys()))
        w2.writeheader()
        w2.writerows(weights)
    print("wrote %s (%d classes) and %s (%d weights)"
          % (os.path.relpath(OUT_CSV, ROOT), len(rows), os.path.relpath(OUT_WEIGHTS_CSV, ROOT),
             len(weights)))


if __name__ == "__main__":
    main()
