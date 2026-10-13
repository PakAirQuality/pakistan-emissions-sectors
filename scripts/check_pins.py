#!/usr/bin/env python3
"""The national pins: the two reference totals the release publishes, to the last printed digit.

A content commit may move placement, attribution and prose; it may not move these unless the
commit says so by name (a re-base). The gate runs this after the manuscripts are repaired and
before the suite. Exit 1 when either pin moved by more than half a unit in the fifth decimal.
"""

from pkinv.assets import asset_path
import csv
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# rc46 Wave 2 - THE SOLID-FUEL ACTIVATION, the release's single deliberate pin move:
# brick-kiln coal (+2.776) and cement-sector coal (+10.796) entered 1A2 through the
# industrial_solid_fuels_1a2 gate on the HDIP coal-by-consumer series; +13.57189 on both
# configurations (industry is configuration-independent). Previous pins, rc39..rc46w1:
# L 452.34662 / S 447.21383. The per-stream ledger is in the Wave 2 commit message and
# outputs/industry_fuel_ledger_2024.csv.
# rc50 - THE CLINKER RE-BASE, and the pins do NOT move: the reference year's cement is the
# audited producer census already, so promoting the census-implied fraction (0.965, replacing
# the IPCC blended default 0.75) changes the EIGHT HISTORICAL 2.A.1 values (+3.96..+5.57 Mt a
# year, +37.13 in total) and not FY2023-24. Those eight totals are pinned, with their reason,
# in tests/test_unallocated_controls.py; the bridge is outputs/pakemis_industrial_coal_bridge.csv.
# rc52 - THREE CATEGORIES ENTER THE REFERENCE (the boundary program's Wave C): ammonia 2.B.1
# (Tier 1 calibrated on NFDC production, 3.24330), iron and steel 2.C.1 (Tier 1 EAF on QIM
# billets, 0.39312) and lubricant use 2.D.1 (Tier 1 ODU on OCAC sales, 0.08329), each a full
# nine-year series before it entered; +3.71971 on both configurations (IPPU is
# configuration-independent). Previous pins, rc46..rc51: L 465.91851 / S 460.78572. The
# nine-year ledger is in tests/test_unallocated_controls.py and the rc52 commit message.
# 2026-10-07 - THE POWER COAL RE-BASE, the twenty-second review's item 2 and the first pin
# move since rc39's agriculture correction. The engine books public-power coal energy on the
# STATIONS' OWN METERED COAL at IPCC Vol.2 Ch.1 Table 1.2 rank defaults
# (data/activity/power/coal_energy_booking.csv) instead of NEPRA SoIR Table 3's published
# energy. Grid 1.A.1.a falls 57.82049 -> 40.04008 at the reference year; both configurations
# move by the same -17.78041, because the coal account is residential-configuration-independent.
# Previous pins, rc52..this: L 469.63822 / S 464.50543.
#
# WHY. Table 3's coal energy is HDIP's tonnage times a CONVERSION: 0.4474 TOE per tonne, held
# constant across FY2015-16..FY2020-21 to 0.016 per cent while the fleet went from imported
# bituminous to 92 per cent Thar lignite, then breaking UPWARD exactly as the fleet's physical
# calorific value fell. Divided into NEPRA's own printed generation it implies net fleet
# efficiencies inside 28-47 per cent in TWO of nine years; the booked account is inside in NINE
# of nine, with the whole interval inside in each of the four years whose mass is reconstructed.
# Neither test touches a heat rate. outputs/pakemis_power_coal_configurations.csv publishes the
# four candidate accounts with their verdicts and docs/power_coal_energy_basis.md is the report.
#
# THE OLD PINS ARE NOT LOST. They are reproduced to the fifth decimal by the retained legacy
# control: outputs/national_configurations.csv, power_table3_legacy_control, 469.63823.
#
# rc67 RE-BASE, DECLARED (three reference changes in one release; CHANGELOG 1.0.0rc67).
# The reference file now carries survey dung (S), so the keys below name each file's own
# configuration: through rc66 they read L 451.85782 (the reference) and S 446.72502.
#   451.85782  rc66 reference
#   -1.19473   chemical feedstock out of the post-meter gas leakage base
#   -5.24626   household dung on the HIES survey series in place of all diverted dung
#   -0.46141   domestic wastewater nitrous oxide on the 2019 Refinement
#   444.95542  rc67 reference
PINS = {"S": ("outputs/national_all_sectors.csv", 444.95542),
        "L": ("outputs/national_all_sectors_ledger.csv", 450.20168)}


def national_total(path):
    with open(asset_path(ROOT, path), encoding="utf-8") as handle:
        for row in csv.DictReader(line for line in handle if not line.startswith("#")):
            if row["row_kind"] == "national_total":
                return float(row["co2e_Mt_AR5"])
    raise SystemExit("no national_total row in %s" % path)


def main():
    moved = []
    for key, (path, pin) in PINS.items():
        value = national_total(path)
        if abs(value - pin) > 5e-6:
            moved.append("%s %.5f (pin %.5f)" % (key, value, pin))
    print("pins hold" if not moved else "pins moved: " + "; ".join(moved))
    return 1 if moved else 0


if __name__ == "__main__":
    sys.exit(main())
