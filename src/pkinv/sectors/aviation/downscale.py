"""Province allocation for civil aviation.

Domestic and international traffic have genuinely different geographies and need
separate proxies: Sindh is about 43% of domestic movements but only 27% of
international, while Punjab is 18% of domestic and 41% of international, because the
Sialkot, Multan and Faisalabad international services sit in Punjab. A single blended
proxy would misallocate both.

Only the domestic proxy affects published provincial greenhouse-gas figures, since the
international stream is a memo item outside the national total.
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import csv
import os

from pkinv.core.geography import PROVINCES
from pkinv.paths import DATA

PROXY = "aviation_lto_domestic"
PROXY_INTL = "aviation_lto_intl"

# rc47 Wave 3: both stages ride the domestic-movements proxy at PROVINCE level -
# LTO because the cycles happen there, cruise because the fuel is UPLIFTED there
# (the accounting view; below the province cruise is not placed at all).
PROXY_MAP = {
    ("Domestic aviation", "Domestic aviation LTO CO2"): PROXY,
    ("Domestic aviation", "Domestic aviation LTO CH4"): PROXY,
    ("Domestic aviation", "Domestic aviation LTO N2O"): PROXY,
    ("Domestic aviation", "Domestic aviation cruise CO2"): PROXY,
    ("Domestic aviation", "Domestic aviation cruise CH4"): PROXY,
    ("Domestic aviation", "Domestic aviation cruise N2O"): PROXY,
}
# Indexed with [], not .get(): an unknown category must raise rather than silently
# allocate a stream onto the wrong geography at an unchanged national total.
PROXY_FALLBACK = {"Domestic aviation": PROXY}


def load_shares(period=None):   # rc44 A1: accepted, not yet used here
    shares = {}
    for r in _activity_rows(asset_path(DATA, "province_shares.csv"), comments=False):
        shares[r["proxy"]] = {p: float(r[p]) for p in PROVINCES}
    return shares


def proxy_for(c):
    return PROXY_MAP.get((c["category"], c["subitem"]),
                         PROXY_FALLBACK[c["category"]])
