"""Province allocation for railway transport.

The primary administrative allocation uses Pakistan Railways' published freight
wagons loaded by division. This represents freight origin, not measured locomotive
fuel use along a route, and its freight/passenger and port-origin biases remain
explicit. It changes geography only; the national fuel account is unchanged.

The ODbL-derived route/corridor model remains a separately licensed structural
alternative under railways_route_model. Its independently computed shares must
match that alternative row, not the primary origin proxy.
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import csv
import os

from pkinv.core.geography import PROVINCES
from pkinv.paths import DATA

PROXY = "railways_freight_div"
WAGONS_PROXY = "railways_freight_div"    # the retained structural alternative
PROXY_MAP = {}
# The non-traction category (rc11 re-base) allocates on the divisional-yard
# distribution rather than the route model: workshops and power houses sit at the
# seven yards, not along the line - the same distinction its S2 spatial class and
# points:pak_rail_yards cube geometry state.
PROXY_FALLBACK = {"Railways": PROXY,
                  "Railway non-traction energy (1A2/1A4c unresolved)": WAGONS_PROXY}


def load_shares(period=None):   # rc44 A1: accepted, not yet used here
    shares = {}
    for r in _activity_rows(asset_path(DATA, "province_shares.csv"), comments=False):
        shares[r["proxy"]] = {p: float(r[p]) for p in PROVINCES}
    return shares


def proxy_for(c):
    # Indexed with [], not .get(): an unknown category must raise rather than silently
    # allocate onto the wrong geography at an unchanged national total.
    return PROXY_MAP.get((c["category"], c["subitem"]), PROXY_FALLBACK[c["category"]])
