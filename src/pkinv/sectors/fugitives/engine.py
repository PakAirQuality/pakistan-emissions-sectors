"""Registered FY2023-24 IPCC-2019 oil-and-gas fugitive inventory."""
from pkinv.core import evidence, period
from pkinv.core.components import enrich_co2e
from pkinv.sectors.fugitives import downscale, leakage, segment_inventory
from pkinv.sectors.fugitives.data import FugitivesData, YEAR

NAME = "fugitives"
CATEGORIES = (leakage.CATEGORY,)
GASES = ("CO2", "CH4", "N2O")
HAS_SINKS = False
YEAR = YEAR

# The reference PERIOD, not just a year. See core.period: this sector's YEAR is the calendar
# year its reporting period CLOSES in, a convention that was implicit until it collided
# with the opposite one in a neighbouring sector.
YEAR_CONVENTION = 'fiscal-end'
PERIOD_START, PERIOD_END = period.from_year(YEAR, YEAR_CONVENTION)

MC_DISTRIBUTION = "lognormal"

load_data = FugitivesData
proxy_for = downscale.proxy_for
load_shares = downscale.load_shares


# core.evidence classes. E3 is the honest default: no segment of this sector is metered for
# emissions, and every row is a published INFRASTRUCTURE quantity - pipeline kilometres, well
# counts, throughput - multiplied by an IPCC per-unit factor. That is derivation from a related
# published quantity, which is what E3 means.
#
# Post-meter is E4 and says so: there is no Pakistani measurement of appliance or industrial
# post-meter leakage at all, and the row exists because omitting a known source is worse than
# bounding it with a default.
#
# T4 throughout. Gas production has a real seasonality and this release does not have it; a
# flat profile is not claimed, it is absent.
#
# S3, WAS S2, AND THE OLD REASON WAS ABOUT INTENT RATHER THAN ABOUT THE ALLOCATION. It read:
# "the allocation rides infrastructure geography - fields, pipelines and processing plants are
# real objects with locations, but without per-object activity". The objects are real. The
# allocation does not ride them. data/stream_geometry.csv gives these segments
# `diffuse:adm1_provinces` and data/stream_grid_proxy.csv spreads them `uniform` within the
# province, saying so four times over - "no field or wellhead raster is held", "plant locations
# not held", "pipeline topology not held", "field locations not held". A provincial share
# spread uniformly is an administrative statistic, which is S3; S2 requires a facility or
# network proxy, and there is none in the path.
#
# This is the same correction the LNG row below already made for itself - S1 to S2, because
# "native geometry means coordinates" and a station count is not one. A segment's objects being
# real does not make the allocation use them, and the class describes the allocation.
EVIDENCE_CLASS, TEMPORAL_METHOD, SPATIAL_METHOD = "E3", "T4", "S3"
SOURCE_ID = "ogra_sorpi_segment_infrastructure"
STREAM_CLASSES = {
    # T2 ON THE UPSTREAM STREAMS, matching what the monthly layer actually does: production,
    # gathering, processing, sour-gas and oil production ride PBS's monthly production series
    # in the years the panel covers (the reference year among them), and a declared T4 over a
    # shaped layer is the declared-versus-used mismatch the modal-class guard exists to catch.
    # S1 since rc46 Wave 5, on the letter's own stated terms: the module docstring above
    # says "the class describes the allocation", and the allocation now opens the World
    # Bank flare register - 130 sites, each weighted by ITS OWN YEAR's flared volume, so
    # the placement is per-object WITH per-object activity, which is the S1 case by the
    # power fleet's own precedent. What the volume proxies is the field's activity, not
    # its emissions - that caveat lives on the geometry_sets row and the weight registry,
    # not in a weaker letter the derivation would refuse.
    "Gas production": (None, "T2", "S1", None),
    "Gas gathering": (None, "T2", "S1", None),
    "Gas processing": (None, "T2", "S1", None),
    "Sour-gas processing": (None, "T2", "S1", None),
    "Oil production": (None, "T2", "S1", None),
    "Post-meter": ("E4", None, "S3", None),
    # S2 since rc46 Wave 5, closing the walk this comment has narrated for three
    # releases: S1 first (two real terminals), then S2 (a count is not a coordinate),
    # then S3 (zero of two geocoded, nothing reached the allocation) - and the comment's
    # own last line said "S2 returns when a coordinate does". Both coordinates did
    # (GEM exact, Wave 0), the allocation opens them as two equal points, and equal
    # weights without a send-out split is a facility proxy, not per-object activity -
    # hence S2 and not S1.
    "LNG import terminals": ("E2", None, "S2", None),
}


def build_components(data, year=None, bound=None, method="ipcc2019", scenario="reference",
                     config=None):
    if method == "legacy2006":
        components, _memo = leakage.compute(data, year, bound)
    elif method == "ipcc2019":
        if year is not None and not data.has_anchor_year(year):
            raise ValueError("no segment-resolved activity ledger for FY%d" % year)
        if bound is not None:
            raise ValueError("2019 bounds are sampled parametrically; use scenario= for structure")
        if config is not None:
            if scenario != "reference":
                raise ValueError("pass either scenario or config, not both")
            scenario = config
        components = segment_inventory.compute(data, scenario, year=year)
    else:
        raise ValueError("unknown fugitives method %r" % method)
    evidence.stamp(components, (EVIDENCE_CLASS, TEMPORAL_METHOD, SPATIAL_METHOD),
                   SOURCE_ID, year if year is not None else YEAR,
                   overrides=STREAM_CLASSES)
    return enrich_co2e(components)


def memo_items(data, year=None):
    return []


# --- Declared accessors (rc34). The report layer reaches these BY NAME through
# the registry instead of importing sector internals; each wraps one module of
# this sector and nothing here recomputes anything.


def post_meter_factor(factor_id):
    from pkinv.sectors.fugitives import post_meter
    return post_meter.factor_value(factor_id)


def post_meter_param(name):
    from pkinv.sectors.fugitives import post_meter
    return post_meter.param_value(name)


def whole_gas_leak_share():
    from pkinv.sectors.fugitives import post_meter
    return post_meter.whole_gas_leak_share()


def fertilizer_feed_fraction(data, year=None):
    """The part of fertiliser gas that is chemical feedstock, with its basis."""
    return data.fertilizer_feed_fraction(year)


def post_meter_feedstock_share(data, year=None, scope="feed"):
    """The share of the non-residential post-meter base a membership withholds."""
    return data.post_meter_feedstock_share(year, scope=scope)


def gas_supply_balance_row(data):
    """The reference year's volume-basis supply identity row."""
    from pkinv.sectors.fugitives import gas_balance
    return next(r for r in gas_balance.balance_rows(data)
                if str(r["fiscal_year"]) in ("2024", "FY2023-24"))


def coal_screen_rows(fiscal_year):
    """The 1.B.1 surface screen for one fiscal-START year; raises ValueError
    where the plant ledger holds no Thar mine-mouth deliveries."""
    from pkinv.sectors.fugitives import coal_screen
    return coal_screen.rows(fiscal_year=fiscal_year)
