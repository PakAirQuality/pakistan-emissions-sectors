"""Sector registration.

A sector is a *module* exposing the attributes below — matching how this codebase already
works (`enteric.compute(data)`), rather than introducing classes it has no other use for.

The manifest is hand-maintained, not scraped: a scraper that silently stops matching covers nothing while still passing, which is
indistinguishable from having no check at all.

    NAME: str               registry key, e.g. "agriculture"
    CATEGORIES: tuple       ordered reporting categories -- THIS IS THE PUBLISHED COLUMN ORDER
    GASES: tuple            must be a subset of core.gwp.GWP's keys
    HAS_SINKS: bool         True iff a component may legitimately be negative
    YEAR: int               reference year of the single-year run

    load_data() -> data                                   opaque per-sector data object
    build_components(data, **overrides) -> list[dict]     co2e already enriched; fixed order
    proxy_for(component) -> str                           must RAISE on unknown, never default
    intermediates(data) -> Mapping

Every engine also exports YEAR_CONVENTION, PERIOD_START/PERIOD_END (from
core.period), MC_DISTRIBUTION, and (all but agriculture) memo_items(data,
year=None); tests/test_sector_contract.py asserts the period trio.

OPTIONAL ACCESSORS (rc34) - the declared extension mechanism. Where the
report layer needs a sector's internals beyond the contract, the sector's
ENGINE exports a named accessor and the report reaches it through
registry.get(name); the report never imports sector modules. Present today:
  parameter_overrides()                          agriculture (swept by core.parameters)
  gas_activity(data) -> {stream: MMCFD}          industry, residential, transport
  post_meter_factor(id), post_meter_param(name), whole_gas_leak_share(),
  gas_supply_balance_row(data), coal_screen_rows(fy)      fugitives
  clinker_co2_Mt(data, year, fraction=None)      ippu
  brick_kiln_screen_Mt(), bagasse_ceiling_Mt(cane_t)      industry
  components_for_year(data, fy_end)              residential
  components_for_fiscal_year(fy_end), series_components_for_year(fy_end),
  activity_basis(category)                       agriculture
An accessor an engine does not export is absent, never a stub; the report
asks the registry and gets AttributeError, which is the honest answer.

DIAGNOSTIC MODULES. Where an accessor would put an evidence class on the
emissions path that the isolation guards keep off it (power's plant-side
closure and implied calorific value - tests/test_plant_closure.py,
tests/test_power_implied_cv.py), it lives in the sector's `diagnostics`
module instead, registered in DIAGNOSTIC_MODULES and reached through
diagnostics(name): gas_bridge(data), coal_energy_restatement(data, year).                        optional; shared physical bus
"""
import importlib

from pkinv.core import components as components_mod

# Dotted module paths, in reporting order.
SECTOR_MODULES = (
    "pkinv.sectors.agriculture.engine",
    "pkinv.sectors.waste.engine",
    "pkinv.sectors.aviation.engine",
    "pkinv.sectors.power.engine",
    "pkinv.sectors.transport.engine",
    "pkinv.sectors.railways.engine",
    "pkinv.sectors.fugitives.engine",
    "pkinv.sectors.residential.engine",
    "pkinv.sectors.ippu.engine",
    "pkinv.sectors.industry.engine",
)

# Each sector's monthly layer, by registry name. Hand-maintained for the same reason
# SECTOR_MODULES is: a convention-scraper that stopped matching would report a module as
# having no monthly layer and as having one, depending on which side of the import it failed.
#
# A layer module must expose
#
#     rows(data=None, fy_start=...) -> (annual_components, month_rows)
#
# where month_rows carry core.monthly.FIELDS and close against annual_components exactly.
# The two aviation entries are not a typo: `aviation.monthly` is a fuel-reconciliation study
# against OCAC and OECD that predates this layer and is not a component layer.
MONTHLY_LAYERS = {
    "agriculture": "pkinv.sectors.agriculture.monthly",
    "waste": "pkinv.sectors.waste.monthly",
    "aviation": "pkinv.sectors.aviation.monthly_layer",
    "power": "pkinv.sectors.power.monthly",
    "transport": "pkinv.sectors.transport.monthly",
    "railways": "pkinv.sectors.railways.monthly",
    "fugitives": "pkinv.sectors.fugitives.monthly",
    "residential": "pkinv.sectors.residential.monthly",
    "ippu": "pkinv.sectors.ippu.monthly",
    "industry": "pkinv.sectors.industry.monthly",
}

_CACHE = {}


DIAGNOSTIC_MODULES = {
    "power": "pkinv.sectors.power.diagnostics",
}


def diagnostics(name):
    """The sector's diagnostic accessors (the closure channel, off the engine).
    Raises KeyError for a sector that registers none - absent, never a stub."""
    import importlib
    return importlib.import_module(DIAGNOSTIC_MODULES[name])


def monthly_layer(name):
    """The monthly-layer module for a registered sector.

    Raises if a sector has no entry, so a new module cannot ship without one.
    """
    if name not in MONTHLY_LAYERS:
        raise KeyError("sector %r has no monthly layer registered in MONTHLY_LAYERS" % name)
    path = MONTHLY_LAYERS[name]
    if path not in _CACHE:
        _CACHE[path] = importlib.import_module(path)
    return _CACHE[path]


def all_sectors():
    """Every registered sector module, import-cached."""
    out = []
    for path in SECTOR_MODULES:
        if path not in _CACHE:
            _CACHE[path] = importlib.import_module(path)
        out.append(_CACHE[path])
    return out


def get(name):
    for sector in all_sectors():
        if sector.NAME == name:
            return sector
    raise KeyError("no registered sector named %r (have %s)"
                   % (name, [s.NAME for s in all_sectors()]))


def build_all():
    """Return (components, categories, sector_of_category) across every registered sector.

    Each component is a COPY carrying an added `_sector` key, so a caller may decorate rows
    -- with a correlation group, say -- without touching what the sector itself returned.
    Categories are globally unique by contract (tests/test_sector_contract.py), which is
    what makes pooling them safe.

    Building all sectors takes several seconds, dominated by transport's fleet model and
    residential's import of the agriculture manure chain, so callers that need it more than
    once should hold the result rather than call again.
    """
    components, categories, sector_of = [], [], {}
    for sector in all_sectors():
        # _sector is kept beside the schema's sector_id: eleven call sites read it, and
        # renaming them is churn without a finding. sector_id is the contract field.
        built = components_mod.enrich_identity(
            [dict(c, _sector=sector.NAME)
             for c in sector.build_components(sector.load_data())], sector.NAME)
        components.extend(built)
        for category in sector.CATEGORIES:
            categories.append(category)
            sector_of[category] = sector.NAME
    return components, categories, sector_of
