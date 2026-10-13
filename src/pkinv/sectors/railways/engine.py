"""Railway transport as a registered sector (IPCC 1A3c)."""
from pkinv.core import evidence, period
from pkinv.core.components import enrich_co2e
from pkinv.sectors.railways import downscale, traction
from pkinv.sectors.railways.data import RailwaysData, YEAR

NAME = "railways"
CATEGORIES = (traction.CATEGORY, traction.NON_TRACTION_CATEGORY)
GASES = ("CO2", "CH4", "N2O")
HAS_SINKS = False
YEAR = YEAR

# The reference PERIOD, not just a year. See core.period: this sector's YEAR is the calendar
# year its reporting period CLOSES in, a convention that was implicit until it collided
# with the opposite one in a neighbouring sector.
YEAR_CONVENTION = 'fiscal-end'
PERIOD_START, PERIOD_END = period.from_year(YEAR, YEAR_CONVENTION)

MC_DISTRIBUTION = "lognormal"

load_data = RailwaysData
proxy_for = downscale.proxy_for
load_shares = downscale.load_shares


# core.evidence classes. E1 because the annual quantity is the operator's OWN METERED
# PURCHASE, published in its Year Book - a single state operator counting fuel it bought, which
# is as close to measurement as this inventory gets. T2 because the OCAC monthly sectoral
# returns carry a Railways customer-class row for every month of the period, so the seasonal
# shape is reconstructed from monthly administrative records rather than assumed.
#
# S2, WAS S1, AND THE TRACK IS NOT THE ISSUE. The allocation is constrained to the audited
# OpenStreetMap network, which is native geometry and stays native geometry - traction fuel
# can burn nowhere else. What decides how much burns on WHICH stretch of it is the corridor
# service tier, and pkinv.sectors.railways.gis.run_gis says in its own docstring that those
# tiers are "DECLARED JUDGMENT". Pakistan Railways publishes no per-corridor fuel of any kind.
# A network proxy without per-object activity is the definition of S2, and this module's
# non-traction category has carried S2 on exactly that reasoning since rc11 - it applies to
# the line as much as to the yards. S1 returns with a per-corridor or per-train fuel record.
EVIDENCE_CLASS, TEMPORAL_METHOD, SPATIAL_METHOD = "E1", "T2", "S2"
SOURCE_ID = "pakistan_railways_year_book"


def build_components(data, year=None):
    components, _memo = traction.compute(data, year)
    # The non-traction category is NOT track-constrained: its fuel runs workshops,
    # power houses, pumps and track machinery at railway facilities, so it rides the
    # seven divisional yards as facility geometry rather than the line. It reached S2
    # first, one release before the traction streams followed it there for the same
    # reason - facility or network geometry, no per-object activity - so the override
    # now agrees with the module default and is kept only to say that the GEOMETRY
    # differs even where the class does not.
    evidence.stamp(components, (EVIDENCE_CLASS, TEMPORAL_METHOD, SPATIAL_METHOD),
                   SOURCE_ID, year if year is not None else YEAR,
                   category_overrides={
                       traction.NON_TRACTION_CATEGORY: (None, None, "S2")})
    return enrich_co2e(components)


def memo_items(data, year=None):
    """None. Rail has no bunker, biogenic or out-of-boundary stream."""
    return []
