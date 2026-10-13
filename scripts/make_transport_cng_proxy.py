"""Recompute the CNG provincial proxy row of data/province_shares.csv.

WHY THIS SCRIPT EXISTS. The `transport_cng_vkt` row is derived from this sector's own
fleet model, but it was hand-entered and nothing recomputed it, so it could drift from
the model silently - and in August 2026 it did. The class split became energy-weighted
(vehicle-km x declared MJ/km) while this row was still pure vehicle-km, which made its
own stored justification false: it argued from three-wheelers being 71 percent of CNG
travel, and on the energy basis they are 43 percent of CNG *consumption*. Since the row
allocates a metered ENERGY quantity (OGRA's gas), energy is the right weight.

The script PRINTS the row rather than editing data/province_shares.csv, which is
hand-curated with source and note prose - the same convention the power sector's ledger
rows follow. A test recomputes the shares and fails on drift, so the stored row cannot
go stale again without something failing.

Writes: outputs/transport_cng_proxy_<year>.csv (both bases, side by side).
"""

from pkinv.assets import asset_path
import csv
import os
import sys

from pkinv.core.geography import PROVINCES
from pkinv.paths import OUTPUTS
from pkinv.sectors.transport import fleet, road
from pkinv.sectors.transport.data import TransportData

OUT_CSV = asset_path(OUTPUTS, "transport_cng_proxy_%d.csv" % TransportData().year)


def shares(data=None, year=None, weight_by_energy=True):
    """{province: share} of CNG activity, on the energy or the distance basis."""
    data = TransportData() if data is None else data
    year = data.year if year is None else year
    by_province = dict.fromkeys(PROVINCES, 0.0)
    for province, district, cls in data.cells(year):
        series = data.stock_series(province, district, cls)
        if year not in series:
            continue
        cng_share = data.split_for(cls, year).get("CNG", 0.0)
        if not cng_share:
            continue
        active, _capped = fleet.active_fleet(
            series, data.p("weibull_beta_%s" % cls),
            data.p("weibull_life_%s" % cls), year)
        km = active * data.vkt_for(cls, year) * cng_share
        w = km * data.mjkm(cls, "CNG") if weight_by_energy else km
        if province in by_province:
            by_province[province] += w
    total = sum(by_province.values())
    return {p: (v / total if total else 0.0) for p, v in by_province.items()}


def main():
    data = TransportData()
    energy = shares(data, weight_by_energy=True)
    distance = shares(data, weight_by_energy=False)
    os.makedirs(OUTPUTS, exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["province", "share_energy_basis", "share_distance_basis",
                    "delta_pp", "note"])
        for p in PROVINCES:
            w.writerow([p, round(energy[p], 6), round(distance[p], 6),
                        round(100 * (energy[p] - distance[p]), 3),
                        "energy basis = vehicle-km x declared MJ/km, matching the "
                        "class split; distance basis is what the row used before "
                        "August 2026"])
    print("wrote %s" % OUT_CSV)
    print("\nPaste this row into data/province_shares.csv (keeping its source/note):")
    print("transport_cng_vkt,%s,0.000000" % ",".join(
        "%.6f" % energy[p] for p in PROVINCES if p != "Other"))
    print("\n  province                 energy    distance   delta(pp)")
    for p in PROVINCES:
        print("  %-22s %.6f  %.6f  %+7.3f"
              % (p, energy[p], distance[p], 100 * (energy[p] - distance[p])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
