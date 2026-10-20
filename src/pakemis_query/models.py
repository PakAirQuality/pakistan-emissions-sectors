"""Request models: frozen dataclasses with the contract's defaults and one canonical JSON form.

Every request names exactly one basis, one configuration and one GWP basis (Compare names two
configurations OR two periods, never two bases). Defaults come from semantic_release.json and
are recorded on the request as `defaults_applied`, so an envelope says which choices the caller
made and which the contract made for them."""
import dataclasses
import json
from dataclasses import dataclass, field

GEOGRAPHY_LEVELS = ("national", "adm1", "adm2")
VIEWS = ("all", "physical", "origin", "accounting")
GROUPS = ("sector_id", "ipcc_code", "category", "gas", "component_id", "period_id", "month",
          "province", "shape_id", "module", "spatial_view", "configuration_id",
          "reporting_sector")


def canonical_json(request):
    """The request as sorted, compact JSON - the string the receipt hashes."""
    payload = dataclasses.asdict(request)
    payload["_type"] = type(request).__name__
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


@dataclass(frozen=True)
class QueryEmissions:
    periods: tuple = ()                 # ("FY2023-24",); empty -> the default period
    basis: str = ""                     # fiscal | calendar; empty -> default
    configuration_id: str = ""          # S_TAN | L_TAN | S_IPCC | L_IPCC
    gwp_basis: str = ""                 # AR5 | AR6
    gases: tuple = ()                   # subset of CO2 CH4 N2O; empty -> all
    sectors: tuple = ()                 # sector_id filter (the module that computed the stream)
    reporting_sectors: tuple = ()       # reporting_sector filter (where IPCC 2006 files it;
                                        # module vocabulary; captive generation -> industry)
    ipcc_codes: tuple = ()              # exact code or prefix ("1.A")
    categories: tuple = ()
    streams: tuple = ()                 # component_id / source_stream_id filter
    geography_level: str = ""           # national | adm1 | adm2; empty -> national
    geography_ids: tuple = ()           # province names or shape_ids
    months: tuple = ()                  # YYYYMM; empty -> annual
    spatial_view: str = ""              # all | physical | origin | accounting
    group_by: tuple = ()
    order_by: str = ""                  # "value desc" | "value asc" | ""
    limit: int = 0
    defaults_applied: tuple = field(default=(), compare=False)


@dataclass(frozen=True)
class QueryAir:
    """The air tables: native kt of a named species, never CO2e. `periods` (fiscal) asks the
    covered-sources family - the national panel and its province and district marginals -
    and `years` (calendar) the national agriculture series; a request naming neither is
    answered for the reference period and says so. Which sectors a grain holds is read from
    its table, not listed here. A sum across pollutants is refused - the particulate strata
    contain one another - so a request either filters to one pollutant or groups by it."""
    pollutants: tuple = ()              # subset of dim_pollutant; empty -> all, grouped
    sectors: tuple = ()                 # sector_id filter (Engine.AIR_SECTORS)
    categories: tuple = ()
    geography_level: str = ""           # national | adm1 | adm2; empty -> national
    geography_ids: tuple = ()           # province names or district labels
    years: tuple = ()                   # 1990..2024 -> the agriculture timeseries grain
    periods: tuple = ()                 # FY2015-16..FY2024-25 -> the covered-sources panel;
                                        # empty with no years -> the reference period,
                                        # national or (rc49) adm1/adm2 spatial by-year
    configuration_id: str = ""          # panel + spatial by-year: S_TAN (default) | L_TAN | S_IPCC | L_IPCC
    group_by: tuple = ()                # subset of pollutant sector_id category subitem province district year
    order_by: str = ""
    limit: int = 0
    defaults_applied: tuple = field(default=(), compare=False)


@dataclass(frozen=True)
class QueryActivity:
    """A record from the activity tables behind the inventory (fact_activity_*): a count, a
    quantity or a rate AS ITS SOURCE PRINTED IT, with the definitions that make it readable -
    the measure, the class, the place and its level, the period and its type, the unit, the
    evidence class, the source series and the use note. Never an emission and never converted:
    a vehicle register is a registered stock, not traffic, and the use note says so. The one
    arithmetic offered is `total`, a sum over the classes of ONE place at ONE date - or over the
    districts of ONE province named on its own, at that province's register date - marked as
    computed here and refused wherever the release says the rows may not be combined."""
    table: str = ""                     # fact_activity_vehicles | fact_activity_livestock | ... (empty -> refused, with the list)
    measure: str = ""                   # the table's Measure as printed ("Registered vehicles"); empty -> every measure
    locations: tuple = ()               # Location names as printed ("Lahore", "Pakistan"), or a Province of a district table ("Punjab": its districts); empty -> every location
    location_level: str = ""            # national | province | district | sales area | airport | plant; empty -> any level
    categories: tuple = ()              # the table's first class column ("Small cars (4W1)", "buffalo"); empty -> every class
    periods: tuple = ()                 # Period strings as printed ("2023-06-30", "FY2023-24") or a date's year ("2023"); empty -> the latest period of each place and class
    total: bool = False                 # true -> one more value after the rows: their sum, for one measure, place (or one province's districts) and period only
    order_by: str = ""                  # "value desc" | "value asc" | ""
    limit: int = 0                      # 0 -> the contract's row cap
    defaults_applied: tuple = field(default=(), compare=False)


@dataclass(frozen=True)
class CompareRequest:
    left: QueryEmissions
    right: QueryEmissions
    mode: str = "absolute"              # absolute | relative


@dataclass(frozen=True)
class TimeseriesRequest:
    query: QueryEmissions
    step: str = "annual"                # annual | monthly


@dataclass(frozen=True)
class UncertaintyRequest:
    scope: str = "national"             # national | category | series
    category: str = ""
    module: str = ""
    resolution: str = ""                # annual | monthly | adm1 | adm2 | grid (joint table)
    configuration_id: str = ""
    period_id: str = ""


@dataclass(frozen=True)
class CompletenessRequest:
    notation_keys: tuple = ()           # filter; empty -> every row
    ipcc_codes: tuple = ()


@dataclass(frozen=True)
class EvidenceRequest:
    source_stream_id: str = ""
    category: str = ""
    module: str = ""


@dataclass(frozen=True)
class MethodRequest:
    method_id: str = ""
    category: str = ""


@dataclass(frozen=True)
class SpatialLineageRequest:
    shape_id: str = ""                  # ADM2 shape
    province: str = ""                  # or an ADM1 province
    month: str = ""                     # YYYYMM or "" for the year
    gas: str = ""
    configuration_id: str = ""


@dataclass(frozen=True)
class TransferRequest:
    ledger_id: str = ""
    configuration_id: str = ""


@dataclass(frozen=True)
class GridCellRequest:
    lat: float = 0.0
    lon: float = 0.0
    month: str = ""                     # YYYYMM or "annual"
    gas: str = "CO2"
    configuration_id: str = ""
    period_id: str = ""                 # "" means the reference year
    # "" sums the three views, which is the only reading that closes: the views PARTITION the
    # placed mass (physical where emitted, origin for waste, accounting for transport), so a
    # default of one view would return 68% of the cell and look like the whole of it.
    spatial_view: str = ""


@dataclass(frozen=True)
class DownloadRequest:
    receipt_id: str = ""
    format: str = "csv"                 # csv | parquet
