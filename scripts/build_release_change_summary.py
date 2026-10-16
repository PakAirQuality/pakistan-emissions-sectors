#!/usr/bin/env python3
"""Compare preserved rc67 and rebuilt rc68 at matched native units and periods.

Totals describe each release's admitted coverage. Component-count changes flag
coverage changes; the difference is not attributed solely to activity or factors.
"""
import collections
import csv
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pkinv.core.io import read_rows
from pkinv.core.configurations import REFERENCE

BASE = ROOT / "data/baselines/rc67_integrated_campaign/outputs"
OUT = ROOT / "outputs/pakemis_release_change_summary.csv"


def collect(folder, reference, air=False):
    sums, identities = collections.defaultdict(float), collections.defaultdict(set)
    name = "pakemis_air_atomic_annual.csv" if air else "pakemis_atomic_annual.csv"
    for row in read_rows(str(folder / name)):
        if row["configuration_id"] != reference:
            continue
        if air and row["core7"] != "yes":
            continue
        gas = row["pollutant"] if air else row["gas"]
        mass = row["emissions_Gg"] if air else row["emission_native_mass"]
        if mass == "":
            continue
        metrics = [(gas, "Gg", float(mass))]
        if not air:
            metrics.extend((ar, "Mt_CO2e", float(row["co2e_Mt_" + ar])) for ar in ("AR5", "AR6"))
        identity = (row["category"], row["subitem"], gas)
        for metric, unit, value in metrics:
            for sector in (row["sector_id"], "national_covered"):
                key = (row["period_id"], sector, metric, unit)
                sums[key] += value
                identities[key].add(identity)
    return sums, identities


def build():
    rows = []
    for air in (False, True):
        old, old_ids = collect(BASE, "REF_2023_24", air)
        new, new_ids = collect(ROOT / "outputs", REFERENCE, air)
        for key in sorted(old.keys() | new.keys()):
            prior, current = old.get(key), new.get(key)
            rows.append(dict(panel="air" if air else "GHG", period_id=key[0],
                sector_id=key[1], species_or_metric=key[2], unit=key[3],
                baseline_configuration="REF_2023_24", current_configuration=REFERENCE,
                baseline_release="1.0.0rc67", current_release="1.0.0rc68",
                baseline_quantity=prior if prior is not None else "",
                current_quantity=current if current is not None else "",
                change=(current - prior) if prior is not None and current is not None else "",
                change_pct=(100 * (current / prior - 1)) if prior and current is not None else "",
                component_coverage_changed="yes" if old_ids.get(key) != new_ids.get(key) else "no",
                comparison_status="matched_period" if key in old and key in new else "period_extension",
                note="Release change includes repaired activity, methods and admitted coverage; structural configurations have no assigned probabilities."))
    return rows


def main():
    rows = build()
    with OUT.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, rows[0], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print("Release changes:", len(rows), "matched unit/sector/species-period records")


if __name__ == "__main__":
    main()
