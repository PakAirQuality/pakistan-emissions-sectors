"""Industrial processes and product use as a registered sector (IPCC sector 2)."""
from pkinv.core import evidence, period
from pkinv.core.components import enrich_co2e
from pkinv.sectors.ippu import ammonia, cement, downscale, lubricants, steel
from pkinv.sectors.ippu.data import IppuData, YEAR

NAME = "ippu"
# rc52 (boundary program Wave C): three categories entered the reference through their gates -
# ammonia (Tier 1 calibrated on NFDC production), iron and steel (Tier 1 EAF on QIM billets) and
# lubricant use (Tier 1 ODU on OCAC non-energy sales) - each a full FY2015-16..FY2023-24 series
# BEFORE it entered, the boundary rule. Nitric acid stays a configuration pair, soda ash is NA in
# IPPU (Solvay), the F-gas and wastewater bands stay outside.
CATEGORIES = (cement.CATEGORY, ammonia.CATEGORY, steel.CATEGORY, lubricants.CATEGORY)
GASES = ("CO2",)
HAS_SINKS = False
YEAR = YEAR

# The reference PERIOD, not just a year. See core.period: this sector's YEAR is the calendar
# year its reporting period CLOSES in, a convention that was implicit until it collided
# with the opposite one in a neighbouring sector.
YEAR_CONVENTION = 'fiscal-end'
PERIOD_START, PERIOD_END = period.from_year(YEAR, YEAR_CONVENTION)

MC_DISTRIBUTION = "lognormal"

load_data = IppuData
proxy_for = downscale.proxy_for
load_shares = downscale.load_shares


# core.evidence classes. E2 because clinker is derived from PBS's Quantum Index of
# Manufacturing cement series and matched HS 252310 trade - published statistics for this
# period, not independently verified here.
#
# T2, AND IT WAS T3 WHILE THE ONLY QIM EDITION HELD WAS CALENDAR 2022. The seasonal shape used
# to be borrowed from a neighbouring year, which is a process-based profile rather than a
# record of these months - T3, correctly. All nine fiscal editions of PBS Table 2 are now
# parsed (scripts/ingest_pbs_qim.py), so the shape is this period's OWN monthly administrative
# record, which is what T2 means. It is not T1: T1 would require the calcination itself to be
# observed monthly, and cement OUTPUT is a closely-related different process.
#
# The borrowed shape was not a small error to have carried. Calendar 2022 peaks at 2.27 times
# its trough where FY2023-24 peaks at 1.48 times its own, so the borrowing overstated cement's
# seasonality by roughly half and moved single months by up to 3.1 points of the year.
#
# S3, AND IT WAS S1 FOR THREE RELEASES ON THE STRENGTH OF A REGISTRY THAT DOES NOT LOCATE
# ANYTHING. The claim was "the allocation rides the facility registry: cement plants are point
# sources with coordinates and published capacities". The registry has 34 facilities and ZERO
# populated latitudes, and the allocation does not ride it at all - it rides
# `ippu_cement_prod` in data/province_shares.csv, a legacy row whose own note reads
# "PROVISIONAL GEOGRAPHY ... must not be interpreted as measured FY2023-24 provincial
# production". S1 means native source geometry. A provincial share derived from a superseded
# national tonnage is an administrative statistic, which is S3.
#
# Wave 5: the coordinates landed AND the allocation consumes them - located works
# carry their company's producer-census clinker (object-partial activity: the
# census is company-grained, the within-company split is uniform, and the
# builtup fallback for unlocated provinces is a declared ledger event). S2 is
# EARNED by the dispatch, exactly as the sentence above demanded; S1 waits for
# per-plant production and >=95% located.
# E2 still, on a different document class since rc30: the reference activity is
# the sixteen producers' own audited annual reports (published statements, not
# independently verified here) rather than the QIM+trade model, which remains
# the named diagnostic beside it.
EVIDENCE_CLASS, TEMPORAL_METHOD, SPATIAL_METHOD = "E2", "T2", "S2"
SOURCE_ID = "producer_census_16_annual_reports"
# The activated categories' own axes (rc52). Ammonia: NFDC's published national production (E2),
# no monthly production record (T4, declared flat), placed by the plants' provinces on NH3-weighted
# capacity (S3). Steel: QIM's published index (E2), the year's own twelve billet months (T2),
# provincial establishment shares from the CMI (S3). Lubricants: OCAC's published sales (E2), no
# monthly non-energy table (T4), an administrative allocation on vehicle activity (S3).
CATEGORY_AXES = {
    ammonia.CATEGORY: ("E2", "T4", "S3", "nfdc_fertilizer_production_series"),
    steel.CATEGORY: ("E2", "T2", "S3", "pbs_qim_billets_ingots"),
    lubricants.CATEGORY: ("E2", "T4", "S3", "ocac_non_energy_sectoral_sales"),
}


def build_components(data, year=None, clinker_override=None,
                     activity_source=None, include_trade=True):
    """activity_source=None resolves the source that carries THIS year.

    It used to default to the reference year's PBS QIM edition whatever year was asked for,
    which is why a per-year build failed on the activity lookup before it ever reached the
    trade gate. The resolver returns the reference source at the reference year, so nothing
    about the published figure changes; for FY2021-22 and FY2022-23 it returns the State
    Bank statistical supplement, and for earlier years it raises, because cement activity is
    not held for them and the year is NE.
    """
    components, _memo = cement.compute(
        data, year, clinker_override,
        activity_source=(data.cement_activity_source(year) if activity_source is None
                         else activity_source),
        include_trade=include_trade)
    for module in (ammonia, steel, lubricants):
        rows, _m = module.compute(data, year)
        components = components + rows
    evidence.stamp(components, (EVIDENCE_CLASS, TEMPORAL_METHOD, SPATIAL_METHOD),
                   SOURCE_ID, year if year is not None else YEAR,
                   category_overrides=CATEGORY_AXES)
    return enrich_co2e(components)


def memo_items(data, year=None):
    """None. Process CO2 is inside the national total; the kiln FUEL is 1A2 and is not
    estimated by this inventory at all."""
    return []


# --- Declared accessors (rc34). The report layer reaches these BY NAME through
# the registry instead of importing sector internals; each wraps one module of
# this sector and nothing here recomputes anything.


def clinker_co2_Mt(data, year, fraction=None):
    """Process CO2 (Mt) from the clinker balance for one year, optionally under a
    fixed clinker fraction; raises where the balance is not held for the year."""
    source = data.cement_activity_source(year)
    ef = data.efv("ippu_cement", "Clinker")
    kwargs = {} if fraction is None else {"fraction": fraction}
    return cement.clinker_balance(
        data, year=year, activity_source=source, **kwargs)[
        "clinker_production_kt"] * ef / 1000.0
