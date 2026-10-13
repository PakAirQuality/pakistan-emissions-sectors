"""IPCC-2019 segment ledger with explicit, composable structural choices."""
from __future__ import annotations

from dataclasses import dataclass, replace
import math

from pkinv.sectors.fugitives.leakage import CATEGORY


# What the non-residential post-meter leak base contains, and at what factor.
#
#   feed_excluded        THE REFERENCE since rc67. Chemical feedstock is out; the process
#                        fuel fertiliser plants burn stays in. The factor (IPCC 2019
#                        Table 4.2.4k) is defined on gas CONSUMED in non-residential
#                        combustion equipment. Feed gas is reformed to hydrogen and
#                        carbon dioxide, not burned, so the factor has no basis on it.
#   full                 the membership every release through rc66 used: the whole
#                        fertiliser class inside the base. Kept as a qualified
#                        alternative, not as a reading anyone defends.
#   fertilizer_excluded  the whole class out, process fuel with it. A lower member: it
#                        leaves burned gas with no post-meter term.
#   half, excluded       the factor's transferability, on the reference base.
POST_METER_STATES = ("feed_excluded", "full", "fertilizer_excluded", "half", "excluded")


@dataclass(frozen=True)
class StructuralConfig:
    """One deterministic model configuration; no field carries a probability."""

    name: str
    upstream_practice: str = "higher"
    transmission_practice: str = "higher"
    distribution_practice: str = "higher"
    tnd_basis: str = "pipeline"
    post_meter_state: str = "feed_excluded"
    processing_basis: str = "gross"
    sour_fraction: float = 0.32
    excluded_streams: frozenset[str] = frozenset()

    def __post_init__(self):
        # "central" is the geometric mean of the published high/low factor stems
        # per stream - the legacy 2006 module's midpoint mechanism carried into
        # this engine as a PRICED, NON-SELECTED member (the twelfth review: the
        # reference is the envelope's top, and until now no central reading
        # existed anywhere in the 2019 machinery). It is a practice leg only:
        # coverage and scope axes have no published bounds to average.
        if self.upstream_practice not in {"higher", "lower", "central"}:
            raise ValueError("upstream_practice must be higher, lower or central")
        for field in ("transmission_practice", "distribution_practice"):
            if getattr(self, field) not in {"higher", "lower", "central"}:
                raise ValueError("%s must be higher, lower or central" % field)
        if self.tnd_basis not in {"pipeline", "throughput"}:
            raise ValueError("tnd_basis must be pipeline or throughput")
        if self.post_meter_state not in POST_METER_STATES:
            raise ValueError("post_meter_state must be one of %s"
                             % ", ".join(POST_METER_STATES))
        if self.processing_basis not in {"gross", "marketable", "excluded"}:
            raise ValueError("processing_basis must be gross, marketable or excluded")
        if self.sour_fraction not in {0.0, 0.16, 0.32}:
            raise ValueError("sour_fraction must be 0, 0.16 or 0.32")
        if self.processing_basis == "excluded" and self.sour_fraction != 0.0:
            raise ValueError("excluded processing requires zero sour fraction")

    @property
    def post_meter_multiplier(self):
        # The membership states act on the ACTIVITY (the withheld share is taken
        # out in inventory_rows, with the derivation printed), so their factor
        # multiplier stays 1.0. "half" halves the factor on the reference base.
        return {"feed_excluded": 1.0, "full": 1.0, "fertilizer_excluded": 1.0,
                "half": 0.5, "excluded": 0.0}[self.post_meter_state]

    def as_dict(self):
        return {
            "configuration": self.name,
            "upstream_practice": self.upstream_practice,
            "transmission_practice": self.transmission_practice,
            "distribution_practice": self.distribution_practice,
            "tnd_basis": self.tnd_basis,
            "post_meter_state": self.post_meter_state,
            "processing_basis": self.processing_basis,
            "sour_fraction": self.sour_fraction,
        }


# subitem, activity, high factor stem, low factor stem (or None), correlation group
BASE_STREAMS = (
    ("Oil production", "oil_onshore_production", "oil_prod_high", "oil_prod_low", "oil-production"),
    ("Oil pipeline transport", "oil_pipeline_transport", "oil_transport_pipeline", None, "oil-transport"),
    ("Oil refining", "oil_refining", "oil_refining", None, "oil-refining"),
    ("Gas production", "gas_onshore_production", "gas_prod_high", "gas_prod_low", "gas-production"),
    ("Gas gathering", "gas_gathering", "gas_gathering", None, "gas-gathering"),
    ("Gas processing", "gas_processing", "gas_processing_high", "gas_processing_low", "gas-processing"),
    ("Sour-gas processing", "sour_gas_processing", "gas_processing_sour", None, "sour-processing"),
    ("LNG import terminals", "lng_import_terminals", "lng_import", None, "lng-import"),
    ("Post-meter appliances", "post_meter_appliances", "post_meter_appliance", None, "post-meter-appliances"),
    ("Post-meter industrial and power", "post_meter_nonresidential", "post_meter_industrial", None, "post-meter-industry"),
)

GASES_BY_STEM = {
    "oil_prod_high": ("CH4", "CO2", "N2O"),
    "oil_prod_low": ("CH4", "CO2", "N2O"),
    "oil_transport_pipeline": ("CH4", "CO2"),
    "oil_refining": ("CH4", "CO2", "N2O"),
    "gas_prod_high": ("CH4", "CO2", "N2O"),
    "gas_prod_low": ("CH4", "CO2", "N2O"),
    "gas_gathering": ("CH4", "CO2", "N2O"),
    "gas_processing_high": ("CH4", "CO2", "N2O"),
    "gas_processing_low": ("CH4", "CO2", "N2O"),
    "gas_processing_sour": ("CH4", "CO2", "N2O"),
    "lng_import": ("CH4", "CO2"),
    "post_meter_appliance": ("CH4", "CO2"),
    "post_meter_industrial": ("CH4", "CO2"),
    "gas_transmission_high_km": ("CH4", "CO2"),
    "gas_transmission_low_km": ("CH4", "CO2"),
    "gas_transmission_high_volume": ("CH4", "CO2"),
    "gas_transmission_low_volume": ("CH4", "CO2"),
    "gas_distribution_high_km": ("CH4", "CO2"),
    "gas_distribution_low_km": ("CH4", "CO2"),
    "gas_distribution_high_volume": ("CH4", "CO2"),
    "gas_distribution_low_volume": ("CH4", "CO2"),
}


REFERENCE = StructuralConfig(name="reference")


def _named_configurations():
    return {
        "reference": REFERENCE,
        "lower_practices": replace(
            REFERENCE, name="lower_practices", upstream_practice="lower",
            transmission_practice="lower", distribution_practice="lower"),
        "throughput": replace(REFERENCE, name="throughput", tnd_basis="throughput"),
        "lower_throughput": replace(
            REFERENCE, name="lower_throughput", upstream_practice="lower",
            transmission_practice="lower", distribution_practice="lower",
            tnd_basis="throughput"),
        "lower_distribution_only": replace(
            REFERENCE, name="lower_distribution_only", distribution_practice="lower"),
        "lower_transmission_only": replace(
            REFERENCE, name="lower_transmission_only", transmission_practice="lower"),
        "post_meter_half_factor": replace(
            REFERENCE, name="post_meter_half_factor", post_meter_state="half"),
        "post_meter_including_feedstock": replace(
            REFERENCE, name="post_meter_including_feedstock",
            post_meter_state="full"),
        "post_meter_excluding_fertilizer": replace(
            REFERENCE, name="post_meter_excluding_fertilizer",
            post_meter_state="fertilizer_excluded"),
        "no_post_meter_industrial": replace(
            REFERENCE, name="no_post_meter_industrial", post_meter_state="excluded"),
        "central": replace(
            REFERENCE, name="central", upstream_practice="central",
            transmission_practice="central", distribution_practice="central"),
        "processing_marketable": replace(
            REFERENCE, name="processing_marketable", processing_basis="marketable"),
        "half_sour_processing": replace(
            REFERENCE, name="half_sour_processing", sour_fraction=0.16),
        "no_sour_processing": replace(
            REFERENCE, name="no_sour_processing", sour_fraction=0.0),
        "no_processing_proxy": replace(
            REFERENCE, name="no_processing_proxy", processing_basis="excluded",
            sour_fraction=0.0),
        "core_network_only": replace(
            REFERENCE, name="core_network_only", processing_basis="excluded",
            sour_fraction=0.0,
            excluded_streams=frozenset({
                "Oil pipeline transport", "Oil refining", "LNG import terminals",
                "Post-meter appliances", "Post-meter industrial and power",
            })),
    }


def configuration(scenario="reference"):
    """Resolve a named scenario or accept a structural object directly.

    "central" used to be a compatibility alias for the reference; it now names
    the real geometric-mean member above, so the alias is gone - resolving it
    returns the central configuration, not the envelope's top."""
    if isinstance(scenario, StructuralConfig):
        return scenario
    try:
        return _named_configurations()[scenario]
    except KeyError as exc:
        raise ValueError("unknown 2019 structural scenario %r" % scenario) from exc


def factorial_configurations():
    """All valid joint configurations; coverage choices are not probability-weighted."""
    processing_states = [
        (basis, sour) for basis in ("gross", "marketable")
        for sour in (0.32, 0.16, 0.0)
    ] + [("excluded", 0.0)]
    output = []
    for upstream in ("higher", "lower"):
        for network in ("higher", "lower"):
            for basis in ("pipeline", "throughput"):
                for post in POST_METER_STATES:
                    for processing, sour in processing_states:
                        name = ("u-%s__n-%s__td-%s__pm-%s__proc-%s__sour-%02d" %
                                (upstream, network, basis, post, processing,
                                 round(100 * sour)))
                        output.append(StructuralConfig(
                            name=name, upstream_practice=upstream,
                            transmission_practice=network,
                            distribution_practice=network, tnd_basis=basis,
                            post_meter_state=post, processing_basis=processing,
                            sour_fraction=sour))
    return output


def selected_conditional_configurations(factorial_rows=None):
    configs = factorial_configurations()
    by_name = {config.name: config for config in configs}
    minimum_name = None
    if factorial_rows:
        minimum_name = min(factorial_rows, key=lambda row: row["mt_co2e_ar5"])["configuration"]
    minimum = by_name.get(minimum_name, StructuralConfig(
        name="minimum_coverage_combined", upstream_practice="lower",
        transmission_practice="lower", distribution_practice="lower",
        tnd_basis="throughput", post_meter_state="excluded",
        processing_basis="excluded", sour_fraction=0.0))
    return (
        REFERENCE,
        configuration("central"),
        configuration("lower_practices"),
        configuration("no_post_meter_industrial"),
        replace(minimum, name="minimum_coverage_combined"),
    )


def _network_streams(config):
    """Both practice stems per network stream; the practice leg picks between
    them (or, for central, averages them) at factor-resolution time."""
    suffix = "volume" if config.tnd_basis == "throughput" else "km"
    activity_suffix = "throughput" if config.tnd_basis == "throughput" else "pipeline"
    return (
        ("Gas transmission", "gas_transmission_%s" % activity_suffix,
         "gas_transmission_high_%s" % suffix, "gas_transmission_low_%s" % suffix,
         config.transmission_practice, "gas-transmission"),
        ("Gas distribution", "gas_distribution_%s" % activity_suffix,
         "gas_distribution_high_%s" % suffix, "gas_distribution_low_%s" % suffix,
         config.distribution_practice, "gas-distribution"),
    )


def _factor_for(data, high_stem, low_stem, practice, gas):
    """One gas's factor under a practice leg.

    higher/lower resolve to a single published stem exactly as before. central
    synthesizes the geometric mean of the two published bounds - the mechanism
    the retired 2006 module always used for its midpoint (leakage.compute,
    math.sqrt(lo*hi)) and the 2019 engine never carried until the twelfth
    review asked what a central reading would even be. Streams with a single
    published stem have no bounds to average: their one value IS the central
    reading and passes through unchanged."""
    if low_stem is None or practice == "higher":
        return data.factor2019("%s_%s" % (high_stem, gas.lower()))
    if practice == "lower":
        return data.factor2019("%s_%s" % (low_stem, gas.lower()))
    hi = data.factor2019("%s_%s" % (high_stem, gas.lower()))
    lo = data.factor2019("%s_%s" % (low_stem, gas.lower()))
    factor = dict(hi)
    factor["value"] = math.sqrt(hi["value"] * lo["value"])
    factor["factor_id"] = "central(%s,%s)" % (hi["factor_id"], lo["factor_id"])
    factor["uncertainty_low_pct"] = max(hi["uncertainty_low_pct"],
                                        lo["uncertainty_low_pct"])
    factor["uncertainty_high_pct"] = max(hi["uncertainty_high_pct"],
                                         lo["uncertainty_high_pct"])
    factor["source_reference"] = ("geometric mean of the published practice "
                                  "bounds: %s | %s" % (hi["source_reference"],
                                                       lo["source_reference"]))
    factor["note"] = ("Synthesized central reading, not a published value: the "
                      "geometric mean of the high- and low-practice factors. "
                      "Priced as a named configuration, never selected.")
    return factor


def _processing_activity(data, config, subitem, year):
    if config.processing_basis == "gross":
        parent = dict(data.activity("gas_processing", year=year))
        parent_id = "gas_processing"
    else:
        parent = data.marketable_processing_activity(year=year)
        parent_id = "gas_processing_marketable"
    if subitem == "Gas processing":
        return parent_id, parent, data.processing_corr_group(config.processing_basis)
    activity = dict(parent)
    activity["value"] *= config.sour_fraction
    activity["source_reference"] += "; structural sour share %.0f%%" % (
        100 * config.sour_fraction)
    activity["note"] = ("Processing activity multiplied by the structural sour-gas share; "
                        "the share is not sampled as a conventional parameter.")
    return ("sour_gas_processing_%s_%02d" %
            (config.processing_basis, round(100 * config.sour_fraction)),
            activity, data.processing_corr_group(config.processing_basis))


def inventory_rows(data, scenario="reference", year=None):
    """Detailed source-row ledger for one explicit structural configuration."""
    config = configuration(scenario)
    excluded = set(config.excluded_streams)
    if config.processing_basis == "excluded":
        excluded.update({"Gas processing", "Sour-gas processing"})
    if config.sour_fraction == 0.0:
        excluded.add("Sour-gas processing")
    if config.post_meter_state == "excluded":
        excluded.add("Post-meter industrial and power")

    rows = []
    streams = [(subitem, activity_id, high_stem, low_stem,
                config.upstream_practice, group)
               for subitem, activity_id, high_stem, low_stem, group in BASE_STREAMS]
    streams.extend(_network_streams(config))

    for subitem, activity_id, high_stem, low_stem, practice, group in streams:
        if subitem in excluded:
            continue
        if subitem in {"Gas processing", "Sour-gas processing"}:
            activity_id, activity, activity_corr_group = _processing_activity(
                data, config, subitem, year)
        else:
            activity = data.activity(activity_id, year=year)
            activity_corr_group = data.activity_corr_group(activity_id)
        withheld = (data.POST_METER_WITHHOLDS[config.post_meter_state]
                    if subitem == "Post-meter industrial and power" else None)
        if withheld:
            share = data.post_meter_feedstock_share(year, scope=withheld)
            activity = dict(activity)
            activity["value"] *= (1.0 - share)
            if withheld == "feed":
                feed = data.fertilizer_feed_fraction(year)
                activity["source_reference"] += (
                    "; minus fertiliser feedstock, %.1f%% of the base (the fertiliser "
                    "class times a feed fraction of %.4f, %s from FY%s)"
                    % (100.0 * share, feed["value"], feed["basis"], feed["observed_year"]))
                activity["note"] = (
                    "Feedstock gas is reformed, not burned, and the post-meter factor is "
                    "defined on gas consumed in combustion equipment, so it is withheld "
                    "from the feed. The process fuel the same plants burn stays in the "
                    "base. %s" % feed["source"])
            else:
                activity["source_reference"] += ("; minus the whole fertiliser class, "
                                                 "%.1f%% of the base" % (100.0 * share))
                activity["note"] = ("Structural leg: the fertiliser class is withheld "
                                    "entire, the burned process fuel with the feed.")
        stem = (low_stem if practice == "lower" and low_stem else high_stem)
        multiplier = (config.post_meter_multiplier
                      if subitem == "Post-meter industrial and power" else 1.0)
        for gas in GASES_BY_STEM[stem]:
            factor = _factor_for(data, high_stem, low_stem, practice, gas)
            emissions_t = activity["value"] * factor["value"] * multiplier
            activity_u = max(activity["uncertainty_low_pct"],
                             activity["uncertainty_high_pct"])
            factor_u = max(factor["uncertainty_low_pct"],
                           factor["uncertainty_high_pct"])
            rows.append({
                "scenario": config.name,
                **config.as_dict(),
                "ipcc_code": factor["ipcc_code"],
                "subitem": subitem,
                "gas": gas,
                "activity_id": activity_id,
                "activity_value": activity["value"],
                "activity_unit": activity["unit"],
                "activity_uncertainty_low_pct": activity["uncertainty_low_pct"],
                "activity_uncertainty_high_pct": activity["uncertainty_high_pct"],
                "activity_source": activity["source"],
                "activity_source_reference": activity.get("source_reference", ""),
                "activity_method_tier": activity.get("method_tier", ""),
                "activity_note": activity.get("note", ""),
                "factor_id": factor["factor_id"],
                "factor_value": factor["value"],
                "factor_unit": factor["unit"],
                "factor_uncertainty_low_pct": factor["uncertainty_low_pct"],
                "factor_uncertainty_high_pct": factor["uncertainty_high_pct"],
                "factor_source": factor["source_reference"],
                "factor_note": factor["note"],
                "structural_multiplier": multiplier,
                "emissions_Gg": emissions_t / 1000.0,
                "uncert_pct": math.hypot(activity_u, factor_u),
                "corr_group": "fugitives-" + group,
                "activity_corr_group": activity_corr_group,
                "factor_corr_group": stem,
            })
    return rows


def compute(data, scenario="reference", year=None):
    components = []
    for row in inventory_rows(data, scenario, year=year):
        component = {
            "category": CATEGORY,
            "subitem": "%s %s" % (row["subitem"], row["gas"]),
            "gas": row["gas"],
            "emissions_Gg": row["emissions_Gg"],
            "uncert_pct": row["uncert_pct"],
            "corr_group": row["corr_group"],
        }
        if row["gas"] == "CH4":
            component["fossil"] = True
        components.append(component)
    return components


def scenario_totals(data):
    names = tuple(_named_configurations())
    return {name: sum(r["emissions_Gg"] for r in inventory_rows(data, name))
            for name in names}
