"""Residential fuel combustion as a registered sector (IPCC 1A4b)."""
from pkinv.core import evidence, period
from pkinv.core.components import enrich_co2e
from pkinv.sectors.residential import combustion, downscale
from pkinv.sectors.residential.data import ResidentialData, YEAR

NAME = "residential"
CATEGORIES = (combustion.CATEGORY,)
GASES = ("CO2", "CH4", "N2O")
HAS_SINKS = False
YEAR = YEAR

# The reference PERIOD, not just a year. See core.period: this sector's YEAR is the calendar
# year its reporting period CLOSES in, a convention that was implicit until it collided
# with the opposite one in a neighbouring sector.
YEAR_CONVENTION = 'fiscal-end'
PERIOD_START, PERIOD_END = period.from_year(YEAR, YEAR_CONVENTION)

MC_DISTRIBUTION = "lognormal"

load_data = ResidentialData
proxy_for = downscale.proxy_for
load_shares = downscale.load_shares


# core.evidence classes. This sector has the widest spread of any in the inventory, and a
# single class would misrepresent every stream in it.
#
#   Natural gas, LPG, kerosene, coal  E2 - utility and petroleum returns for domestic
#     customers: published statistics for this period, not verified here.
#   Firewood, crop residues           E2 - the HIES survey's own measured household
#     consumption, design-weighted. A survey measurement is a published statistic, not a
#     derivation.
#   Dung cake                         E3 - not measured here at all. It is DERIVED from
#     agriculture's manure nitrogen balance through the cross-sector closure, which is why
#     its source_id points at that ledger rather than at a residential source.
#   Generators                        E3 - HIES generator-fuel EXPENDITURE divided by the
#     administered pump price. A quantity reconstructed from a value.
#   Charcoal                          E4 - no national charcoal quantity exists; the row is a
#     declared judgement kept so the fuel is not silently absent.
#
# T3 throughout: the monthly layer spreads household fuel on a measured degree-day curve
# (NASA POWER), which is a process-based profile rather than an observation of monthly fuel.
# S3 because the district allocation rides HIES shares and census population.
EVIDENCE_CLASS, TEMPORAL_METHOD, SPATIAL_METHOD = "E2", "T3", "S3"
SOURCE_ID = "ogra_sorpi_domestic_and_hies"
STREAM_CLASSES = {
    "Dung cake": ("E3", None, None, "agriculture_manure_nitrogen_ledger"),
    "Generators": ("E3", None, None, "hies_generator_fuel_expenditure"),
    # T3 like every other residential stream: the quantity is the weak part, not the shape.
    "Charcoal": ("E4", "T3", None, "no_national_quantity"),
    "Firewood": (None, None, None, "hies_2024_25_firewood"),
    "Crop residues": (None, None, None, "hies_2024_25_residues"),
}


def build_components(data, year=None, woodfuel_override="__unset__", dung_basis=None):
    if woodfuel_override == "__unset__":
        woodfuel_override = None
    components, _memo = combustion.compute(data, year, woodfuel_override,
                                           dung_basis=dung_basis)
    evidence.stamp(components, (EVIDENCE_CLASS, TEMPORAL_METHOD, SPATIAL_METHOD),
                   SOURCE_ID, year if year is not None else YEAR,
                   overrides=STREAM_CLASSES)
    return enrich_co2e(components)


def memo_items(data, year=None, dung_basis=None):
    """Biogenic CO2 from dung cake and firewood - outside the national total."""
    _c, memo = combustion.compute(data, year, dung_basis=dung_basis)
    return memo


# --- Declared accessors (rc34). The report layer reaches these BY NAME through
# the registry instead of importing sector internals; each wraps one module of
# this sector and nothing here recomputes anything.


def gas_activity(data):
    return {"Residential": data.quantity("Natural Gas")}


def components_for_year(data, fy_end, dung_basis=None):
    """The per-year residential components, from the sector's own time series. dung_basis
    None is the reference (the survey series); "ledger" is configuration L."""
    from pkinv.sectors.residential import timeseries
    return timeseries.components_for_year(data, fy_end, dung_basis)
