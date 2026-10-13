"""Provisional province allocation for industrial processes.

The legacy cement/limestone shares are retained only to keep current national and province
outputs reconciled.  Their former Punjab anchor was not period-matched.  The populated
facility registry is the permanent replacement once every producer has plant-level clinker
activity; no new provincial evidence is inferred from the legacy proxy.
"""
from pkinv.activity.store import read_rows as _activity_rows
import csv
import os

from pkinv.core.geography import PROVINCES
from pkinv.paths import DATA
from pkinv.assets import asset_path

PROXY = "ippu_cement_prod"
PROXY_MAP = {}
# rc52: the activated categories' ADM1 proxies (data/province_shares.csv): ammonia on the eight
# plants' NH3-weighted nameplate capacity by province; steel on the CMI 2015-16 basic-iron-and-steel
# establishment shares (an administrative count, S3 - large Karachi mills are under-weighted, said
# in the row's note); lubricants on vehicle activity (the accounting placement of a product sold
# nationally). All three are declared S3 administrative statistics, none a native geometry.
PROXY_FALLBACK = {"Cement production": PROXY,
                  "Ammonia production": "ippu_ammonia_capacity",
                  "Iron and steel production": "ippu_steel_establishments",
                  "Lubricant use": "transport_vkt"}


def load_shares(period=None):   # rc44 A1: accepted, not yet used here
    shares = {}
    for r in _activity_rows(asset_path(DATA, "province_shares.csv"), comments=False):
        shares[r["proxy"]] = {p: float(r[p]) for p in PROVINCES}
    return shares


def proxy_for(c):
    # Indexed with [], not .get(): an unknown category must raise rather than silently
    # allocate onto the wrong geography at an unchanged national total.
    return PROXY_MAP.get((c["category"], c["subitem"]), PROXY_FALLBACK[c["category"]])
