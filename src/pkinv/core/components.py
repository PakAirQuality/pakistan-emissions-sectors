"""The component row contract, shared by every sector.

A component is one (category, subitem, gas) emission stream. Sectors produce them; core
allocates, aggregates and reconciles them without knowing any sector's science.

Emissions are always in Gg of the named gas, never CO2e. The CO2e columns are derived
here, once, so no sector can arrive at its own GWP convention.

Deliberately a plain dict, not a dataclass: every downstream consumer already indexes it
as a mapping, and air_pollutants synthesises pseudo-components to reuse proxy lookup.
"""
from pkinv.core import gwp

# Bump when a key is added or its meaning changes. Recorded in the release manifest so a
# published dataset says which contract produced it.
# v2 promoted the six provenance keys below from optional to required. A dataset produced
# under v1 and one produced under v2 are not interchangeable: the v1 rows may say nothing about
# how they were resolved in time or space, and the whole point of the promotion is that saying
# nothing is no longer an available answer.
# v3 gives every row a stable IDENTITY - component_id and sector_id - derived here rather
# than authored by sectors. They are DERIVED, not required, and that is the whole design:
# component_id was already being synthesised at report time by source_streams.stream_id(),
# so the identity of a row depended on which product happened to be building it. Deriving
# it once, centrally, is the same move enrich_co2e makes for GWP and for the same reason -
# a second construction is a second vintage waiting to disagree.
#
# What is NOT here, deliberately. ipcc_code needs outputs/completeness.csv, and core may
# not read the report layer; estimate_status is "E" for every component that exists, so on
# this row it would be a constant, and the real E/NE/IE/NO lives in the coverage matrix
# where absent cells can carry it; activity_status varies by PERIOD and this row is
# period-free. All three belong on the atomic annual table, which is period-scoped and sits
# in the report layer where those joins are legal.
# v4 registers the optional uncertainty-driver/reconstruction metadata now emitted
# by the reconciled coal calculation; required native-mass fields are unchanged.
SCHEMA_VERSION = "pkinv.component/v4"

REQUIRED_KEYS = frozenset({
    "category", "subitem", "gas", "emissions_Gg", "uncert_pct",
    # --- promoted from optional in v2 ----------------------------------------------------
    # These were optional while ten sectors adopted them one at a time, and that was the right
    # way to introduce them. It stopped being the right way to keep them: two sectors had
    # adopted the full set, one had adopted two keys, and seven had adopted none, so the
    # honest answer to "how much of this dataset is observed?" was "of the fifth of it that
    # says". A provenance field that most rows omit describes the rows that bothered.
    "activity_year", "activity_period_kind", "evidence_class", "temporal_method",
    "spatial_method", "source_id",
})
# corr_group: fully-correlated uncertainty group (see core.uncertainty.combine_sum).
# fossil:     CH4 of fossil origin, which carries a higher AR6 GWP than biogenic CH4.
#
# The five below carry the metadata a spatiotemporal dataset needs on the row rather than
# in a module attribute or a function. They are OPTIONAL on purpose: adding them here
# makes them legal for all ten sectors immediately, with no sector edit and no downstream
# change, because nothing iterates this key set to build a header - every consumer indexes
# by name. Sectors adopt them one at a time, and tests/test_sector_contract.py tracks which
# have. Making them required is a separate, later decision.
#
# activity_year:   the year of the ACTIVITY DATUM behind the row, which is not always the
#                  sector's reference year - a carve-out relayed from another sector's
#                  survey, or a factor from a different vintage, differs and should say so.
# activity_period_kind: "span" for a flow accumulated over the period, "enumeration" for a
#                  stock counted once (core.period.PERIOD_KINDS). Absent means span, which is
#                  the common case. It exists because the largest category in this inventory
#                  rides a livestock census count rather than a twelve-month flow, and the
#                  monthly layer must not spread a stock the way it spreads a flow.
# evidence_class:  core.evidence class of the estimate itself (E1..E4).
# temporal_method: how the row is resolved in time (T1..T4). Annual rows carry the class
#                  their monthly profile would inherit, or T4 where none exists.
#                  A SCALAR SUMMARY OF A VECTOR, and it can flatter. 81 of the 190 source
#                  streams have monthly profiles that MIX classes across the twelve months
#                  - aviation is T1 in the months OCAC publishes and T2 elsewhere, the
#                  agricultural soils rows are T2 in fertiliser-offtake months and T3 in
#                  the rest - and this one field reports the modal month, not the weakest.
#                  So pakemis_source_streams.csv can read T2 for a stream whose worst month
#                  is T3, and it records zero T1 streams while the monthly product emits 75
#                  T1 rows. Neither number is wrong; they answer different questions, and
#                  until now nothing said so. Re-deriving the annual class as the FLOOR of
#                  its months is the right rule and it moves the published T-class mass
#                  shares, so it belongs to the 108-month build rather than to a release
#                  freeze - see the temporal-class-scalar gap.
# spatial_method:  how the row is allocated in space (S1..S4).
# source_id:       stable key into the source register for the activity datum.
# net_of_leak (Wave 6): marks a component whose deterministic value is booked
# NET of the post-meter gas leak share, so the national MC can scale it by
# each draw's own combusted fraction (the per-draw gas identity). A flag like
# fossil: declared where the engine nets, consumed by uncertainty_all.
# Optional uncertainty metadata: driver widths describe the existing decomposition;
# the Approach-1 width remains distinct from the sampled lognormal marginal, and
# reconstruction endpoints remain structural cases rather than 95% parameters.
OPTIONAL_KEYS = frozenset({"corr_group", "fossil", "net_of_leak",
                           "uncertainty_driver_widths", "approach1_uncert_pct",
                           "reconstruction_interval_kind"})
DERIVED_KEYS = frozenset({"co2e_Mt_AR5", "co2e_Mt_AR6", "component_id", "sector_id"})
ALL_KEYS = REQUIRED_KEYS | OPTIONAL_KEYS | DERIVED_KEYS


def component_id(sector_name, category, subitem, gas):
    """The stable identity of one emission stream: sector|category|subitem|gas, slugified.

    This construction is not new - it is source_streams.stream_id(), moved here unchanged
    so the ids in the shipped ledger do not move. What is new is WHERE it lives. An
    identity synthesised by one report is an identity that report owns; every other
    consumer either re-derives it (and may drift) or does without. Deriving it on the row
    means the atomic table, the ledger and the monthly layer all name a stream the same
    way because they are reading the same field rather than each computing it.

    Uniqueness is already proved by the sector contract: category names are globally unique
    and (category, subitem) is unique within a sector, so this tuple cannot collide.
    """
    parts = [sector_name, category, subitem, gas]
    slug = "|".join(str(p).strip().lower().replace(" ", "-") for p in parts)
    return "".join(ch for ch in slug if ch.isalnum() or ch in "|-_./+()")


def enrich_identity(components, sector_name):
    """Add sector_id and component_id in place, returning the list for chaining."""
    for c in components:
        c["sector_id"] = sector_name
        c["component_id"] = component_id(sector_name, c["category"], c["subitem"],
                                         c["gas"])
    return components


def co2e_Mt(gas, emissions_Gg, ar, fossil=False):
    """Gg gas * GWP = Gg CO2e; /1000 -> Mt (Tg) CO2e."""
    return gwp.to_co2e(gas, emissions_Gg, ar, fossil) / 1000.0


def enrich_co2e(components):
    """Add co2e_Mt_AR5/AR6 in place, returning the same list for chaining."""
    for c in components:
        fossil = c.get("fossil", False)
        c["co2e_Mt_AR5"] = co2e_Mt(c["gas"], c["emissions_Gg"], "AR5", fossil)
        c["co2e_Mt_AR6"] = co2e_Mt(c["gas"], c["emissions_Gg"], "AR6", fossil)
    return components


def category_total(components, category):
    """Mt CO2e (AR5) for one category."""
    return sum(c["co2e_Mt_AR5"] for c in components if c["category"] == category)
