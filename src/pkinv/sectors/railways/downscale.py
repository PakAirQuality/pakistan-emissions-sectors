"""Province allocation for railway transport.

One proxy, because there is only one activity figure to allocate and Pakistan Railways
publishes no fuel breakdown of any kind below the national level. The proxy is now the
ROUTE-CONSTRAINED MODEL: line-haul fuel along the audited OSM railway network with
corridor weights, shunting at the divisional yards (pkinv.sectors.railways.gis), its
shares transcribed onto a province_shares.csv row so the stdlib engine never needs the
gis extra, and pinned against a fresh computation by a gis-marked test.

The previous proxy - freight wagons loaded by division, whose two declared biases credited
Sindh with fuel burnt across Punjab - stays in the shares file as the structural
alternative, and the uncertainty module publishes the split under both. Each row's basis
and biases are recorded on the row itself, so they travel with the numbers.
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import csv
import os

from pkinv.core.geography import PROVINCES
from pkinv.paths import DATA

PROXY = "railways_route_model"
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
