"""Process-matched provincial allocation for the FY2023-24 segment ledger."""
from __future__ import annotations

from pkinv.assets import asset_path

from pkinv.activity.store import read_rows as _activity_rows
import csv
import os

from pkinv.core.geography import PROVINCES
from pkinv.paths import DATA

GAS_PROXY = "fugitive_gas_prod"
OIL_PROXY = "fugitive_oil_prod"
TRANSMISSION_PROXY = "fugitive_gas_transmission"
DISTRIBUTION_PROXY = "fugitive_gas_distribution"
CONSUMPTION_PROXY = "fugitive_gas_consumption"
REFINERY_PROXY = "fugitive_oil_refining"
LNG_PROXY = "fugitive_lng_terminal"
PROXY = GAS_PROXY


def _normalise(values):
    total = sum(values.values())
    if total <= 0:
        raise ValueError("fugitives provincial control has no positive total")
    return {province: values.get(province, 0.0) / total for province in PROVINCES}


def load_shares(period=None):   # rc44 A1: accepted, not yet used here
    shares = {}
    for row in _activity_rows(asset_path(DATA, "province_shares.csv"), comments=False):
        shares[row["proxy"]] = {p: float(row[p]) for p in PROVINCES}

    path = asset_path(DATA, "activity", "fugitives", "provincial_controls_2023_24.csv")
    transmission = {p: 0.0 for p in PROVINCES}
    distribution = {p: 0.0 for p in PROVINCES}
    consumption = {p: 0.0 for p in PROVINCES}
    aliases = {"Other territories": "Other"}
    for row in _activity_rows(path, comments=False):
        province = aliases.get(row["province"], row["province"])
        transmission[province] += float(row["transmission_km"])
        distribution[province] += float(row["distribution_km"])
        consumption[province] += float(row["gas_consumption_mmcfd"])
    shares[TRANSMISSION_PROXY] = _normalise(transmission)
    shares[DISTRIBUTION_PROXY] = _normalise(distribution)
    shares[CONSUMPTION_PROXY] = _normalise(consumption)
    shares[REFINERY_PROXY] = _normalise({"Punjab": 4.90 + 1.74, "Sindh": 1.47 + 1.45 + 1.12})
    shares[LNG_PROXY] = _normalise({"Sindh": 2.0})
    return shares


def proxy_for(component):
    if component["category"] != "Fugitive emissions from oil and gas":
        raise KeyError(component["category"])
    subitem = component["subitem"]
    if subitem.startswith("Oil refining"):
        return REFINERY_PROXY
    if subitem.startswith("Oil"):
        return OIL_PROXY
    if subitem.startswith("Gas transmission"):
        return TRANSMISSION_PROXY
    if subitem.startswith("Gas distribution") or subitem.startswith("Post-meter appliances"):
        return DISTRIBUTION_PROXY
    if subitem.startswith("Post-meter industrial"):
        return CONSUMPTION_PROXY
    if subitem.startswith("LNG import"):
        return LNG_PROXY
    return GAS_PROXY
