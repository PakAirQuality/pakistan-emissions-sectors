"""Road transport (1A3b) and off-road machinery (1A4c) as a registered sector.

Two categories from one fuel control total. The national diesel figure covers both, and
road._shares() carves the off-road share out by construction, so the two cannot
double-count - the same arrangement the waste sector uses for disposal and open burning.
Off-road is not road transport and its category name says so; it lives here because it is
built from this sector's fleet model, not because IPCC groups them.
"""
from pkinv.core import evidence, period
from pkinv.core.components import enrich_co2e
from pkinv.sectors.transport import cng, downscale, offroad, road
from pkinv.sectors.transport.data import TransportData, YEAR

NAME = "transport"
CATEGORIES = ("Road transport", offroad.CATEGORY)
GASES = ("CO2", "CH4", "N2O")
HAS_SINKS = False
YEAR = YEAR

# The reference PERIOD, not just a year. See core.period: this sector's YEAR is the calendar
# year its reporting period CLOSES in, a convention that was implicit until it collided
# with the opposite one in a neighbouring sector.
YEAR_CONVENTION = 'fiscal-end'
PERIOD_START, PERIOD_END = period.from_year(YEAR, YEAR_CONVENTION)

MC_DISTRIBUTION = "lognormal"

load_data = TransportData
proxy_for = downscale.proxy_for
load_shares = downscale.load_shares


# core.evidence classes. THE MAGNITUDE AND THE SPLIT HAVE DIFFERENT SUPPORT, and this is the
# sector where saying so matters most. The Road customer-class fuel total is a published
# petroleum statistic (E2). But no component row IS that total: each class row is the total
# times a vehicle-kilometre share weighted by a declared energy intensity, which is a quantity
# derived from a published one - E3. Reporting the class rows as E2 would lend the fleet model
# the support that belongs to the fuel statistic, and the fleet model is this sector's weakest
# element by its own account.
#
# CNG is E2: OGRA meters gas to the CNG sector directly, so that row is not a share of
# anything. Off-road is E3 for the same reason as the road classes, and its IPCC allocation is
# separately declared unresolved.
#
# T2 because OCAC's monthly sectoral returns carry the Road customer-class rows for every month
# of the period. S3 because the provincial allocation rides provincial fuel sales - an
# administrative statistic, and one whose shape this sector borrows from a neighbouring year.
EVIDENCE_CLASS, TEMPORAL_METHOD, SPATIAL_METHOD = "E3", "T2", "S3"
SOURCE_ID = "ocac_sectoral_road_customer_class"
STREAM_CLASSES = {
    # T4: OGRA meters CNG gas annually and no monthly series was obtained, so the twelve
    # months are equal twelfths by assertion - which for a fuel rationed by season and by
    # load-shedding is the least defensible profile in the inventory.
    "CNG": ("E2", "T4", None, "ogra_sorpi_cng_metered"),
    "Off-road machinery": ("E3", None, None, "ocac_sectoral_road_residual"),
}


def build_components(data, year=None, cng_hhv_btu=None,
                     control_category="transport_fuel_supply", deduct_rail=False,
                     intensity_basis="mid"):
    """Road transport (petrol, diesel and CNG) plus off-road machinery.

    CNG joins the SAME category as petrol and diesel - it is road transport - but on a
    different activity basis: metered gas from OGRA rather than a share of the petroleum
    control total. That is why it is a separate module and not another fuel in road.py.

    cng_hhv_btu overrides the gas heating value for the published sensitivity;
    control_category and deduct_rail rebuild the superseded control arrangements for
    the structural boundary scenarios; intensity_basis rebuilds the class split at the
    ends of the declared MJ/km bands for the class-composition scenarios.
    """
    on_road, _memo = road.compute(data, year, control_category=control_category,
                                  deduct_rail=deduct_rail,
                                  intensity_basis=intensity_basis)
    off_road, _m = offroad.compute(data, year, control_category=control_category,
                                   deduct_rail=deduct_rail,
                                   intensity_basis=intensity_basis)
    gas = cng.compute(data, year, cng_hhv_btu)
    rows = on_road + off_road + gas
    evidence.stamp(rows, (EVIDENCE_CLASS, TEMPORAL_METHOD, SPATIAL_METHOD),
                   SOURCE_ID, year if year is not None else YEAR,
                   overrides=STREAM_CLASSES)
    return enrich_co2e(rows)


def memo_items(data, year=None):
    """None. Off-road machinery used to be this sector's memo item and is now a reported
    category; keeping the memo would report the same diesel twice."""
    return []


# --- Declared accessors (rc34). The report layer reaches these BY NAME through
# the registry instead of importing sector internals; each wraps one module of
# this sector and nothing here recomputes anything.


def gas_activity(data):
    return {"CNG": data.cng_mmcfd(YEAR)}
