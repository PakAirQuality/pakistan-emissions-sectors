"""Province allocation for road transport.

FUEL SOLD, NOT VEHICLES REGISTERED (August 2026 re-anchor). The petrol and diesel
streams ride provincial fuel-sales shares built from OCAC's monthly area editions -
the same publication the national controls come from - allocated per fuel, because
freight geography is not passenger geography: Sindh carries 19.7 percent of road
diesel where the registration proxy gave it 6.3, which is the Karachi port effect
this sector always said the registration basis was missing. The registration proxy
(transport_vkt) is retained as a diagnostic and the comparison is a published output.
Fuel sold is still not fuel consumed - freight crosses provincial boundaries - which
is the residual caveat, stated rather than hidden.
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import csv
import os

from pkinv.core.geography import PROVINCES
from pkinv.paths import DATA

PETROL_PROXY = "transport_fuel_petrol"
DIESEL_PROXY = "transport_fuel_diesel"
# The superseded registration-based proxy, kept as the diagnostic comparator.
REGISTRATION_PROXY = "transport_vkt"
PROXY = PETROL_PROXY
# Off-road rides cropland, not fuel sales: the class is dominated by tractors, and
# tractors follow the crop area. See the transport_offroad row in province_shares.csv for
# why that is right for the tractors and wrong for the residual bucket sharing the class.
OFFROAD_PROXY = "transport_offroad"
# CNG rides its OWN vehicle-kilometres, not fuel sales: OGRA's metered gas is national,
# and 71 percent of CNG travel is three-wheelers, whose geography is not the petrol
# fleet's. Geography only: the magnitude comes from OGRA's metered gas.
CNG_PROXY = "transport_cng_vkt"
PROXY_MAP = {("Road transport", "CNG CO2"): CNG_PROXY,
             ("Road transport", "CNG CH4"): CNG_PROXY,
             ("Road transport", "CNG N2O"): CNG_PROXY}
PROXY_FALLBACK = {"Road transport": PETROL_PROXY,
                  "Mixed off-road (1A4c/1A2)": OFFROAD_PROXY}


def load_shares(period=None):
    """Provincial share vectors; petrol and diesel read the period's OWN OCAC area
    pages where a complete twelve-month panel exists (rc47 Wave 5 - the rc44 period
    argument finally consumed). FY2021-22 onward have full direct-edition panels;
    the reference table serves every other year and every other proxy, and the
    switch is by panel completeness, never by a hand-kept year list."""
    shares = {}
    for r in _activity_rows(asset_path(DATA, "province_shares.csv"), comments=False):
        shares[r["proxy"]] = {p: float(r[p]) for p in PROVINCES}
    if period is not None and hasattr(period, "fiscal_start_year"):
        from pkinv.sectors.transport import province_shape
        fiscal_year = int(period.fiscal_start_year) + 1  # panel keys on the END year
        # The REFERENCE year keeps the committed table: the own-year path reproduces
        # it only to the table's printed precision, and a last-digit difference would
        # give the reference a pattern digest its own backcast years cannot match -
        # the committed product stays canonical, and a test holds the two equal.
        if fiscal_year != province_shape.REFERENCE_SHAPE_YEAR:
            rows = province_shape._panel()
            if province_shape.months_covered(fiscal_year, rows) == 12:
                shares[PETROL_PROXY] = province_shape.shares("petrol", fiscal_year, rows)
                shares[DIESEL_PROXY] = province_shape.shares("diesel", fiscal_year, rows)
    return shares


def proxy_for(c):
    # Indexed with [], not .get(): an unknown category must raise rather than silently
    # allocate onto the wrong geography at an unchanged national total.
    mapped = PROXY_MAP.get((c["category"], c["subitem"]))
    if mapped is not None:
        return mapped
    if c["category"] == "Road transport" and " Diesel " in " %s " % c["subitem"]:
        return DIESEL_PROXY
    return PROXY_FALLBACK[c["category"]]
