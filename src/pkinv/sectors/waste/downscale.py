"""Province allocation for open waste burning.

Two geographies, because the sector's two categories live on opposite sides of the same
split. Burning follows the waste that is NOT collected, which is disproportionately rural;
disposal follows the waste that IS, which is disproportionately urban. Both proxies are
derived from the same panel and the same collection parameters as the national totals, so
neither can drift from the mass it allocates - and using one proxy for both would leave
the national total untouched while quietly moving megatonnes between provinces.
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import csv
import os

from pkinv.core.geography import PROVINCES
from pkinv.paths import DATA

PROXY = "waste_burned_pop"
DISPOSAL_PROXY = "waste_disposed_pop"
# Wastewater rides the methane-generating load, not headcount: sewered flow carries a
# five-times-higher MCF than a rural latrine, so the urban provinces weigh more.
WASTEWATER_PROXY = "wastewater_load"

PROXY_MAP = {
    ("Open burning of waste", "Open waste burning CO2 (fossil)"): PROXY,
    ("Open burning of waste", "Open waste burning CH4"): PROXY,
    ("Open burning of waste", "Open waste burning N2O"): PROXY,
}
# Indexed with [], not .get(): an unknown category must raise here rather than silently
# allocate a whole stream onto the wrong geography, which would leave the national total
# unchanged and be invisible in the headline table.
PROXY_FALLBACK = {"Open burning of waste": PROXY,
                  "Solid waste disposal": DISPOSAL_PROXY,
                  "Domestic wastewater": WASTEWATER_PROXY}


def load_shares(period=None):   # rc44 A1: accepted, not yet used here
    shares = {}
    for r in _activity_rows(asset_path(DATA, "province_shares.csv"), comments=False):
        shares[r["proxy"]] = {p: float(r[p]) for p in PROVINCES}
    return shares


def proxy_for(c):
    return PROXY_MAP.get((c["category"], c["subitem"]),
                         PROXY_FALLBACK[c["category"]])
