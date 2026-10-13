"""Scientific audit tables for dominant fugitive assumptions."""
from __future__ import annotations

from pkinv.assets import asset_path

from collections import defaultdict
import csv
import os

from pkinv.core.components import co2e_Mt
from pkinv.paths import DATA
from pkinv.sectors.fugitives import segment_inventory
from pkinv.activity.store import read_rows


DISTRIBUTION_EVIDENCE_PATH = asset_path(
    DATA, "activity", "fugitives", "distribution_practice_evidence.csv")
POST_METER_END_USE_PATH = asset_path(
    DATA, "activity", "fugitives", "post_meter_end_use_2023_24.csv")


def _csv_rows(path):
    return read_rows(path, comments=False)


def native_gas_table(data, scenario="reference", year=2024):
    grouped = defaultdict(lambda: {"CH4": 0.0, "CO2": 0.0, "N2O": 0.0})
    for row in segment_inventory.inventory_rows(data, scenario, year=year):
        grouped[row["subitem"]][row["gas"]] += row["emissions_Gg"]
    output = []
    for segment, gases in grouped.items():
        total = sum(co2e_Mt(gas, mass, "AR5", fossil=(gas == "CH4"))
                    for gas, mass in gases.items())
        output.append({
            "segment": segment,
            "ch4_Gg": gases["CH4"],
            "co2_Gg": gases["CO2"],
            "n2o_Gg": gases["N2O"],
            "co2e_Mt_AR5": total,
            "ch4_gwp100_ar5_fossil": 30.0,
            "activity_status": _activity_status(data, segment, year),
        })
    grand = sum(row["co2e_Mt_AR5"] for row in output)
    for row in output:
        row["share_pct"] = 100.0 * row["co2e_Mt_AR5"] / grand
    return sorted(output, key=lambda row: row["co2e_Mt_AR5"], reverse=True)


def _activity_status(data, segment, year):
    row = next(row for row in segment_inventory.inventory_rows(
        data, "reference", year=year) if row["subitem"] == segment)
    return row["activity_method_tier"]


def _segment_total(data, scenario, segment, year=2024):
    return sum(co2e_Mt(row["gas"], row["emissions_Gg"], "AR5",
                       fossil=(row["gas"] == "CH4"))
               for row in segment_inventory.inventory_rows(data, scenario, year=year)
               if row["subitem"] == segment)


def assumption_audit(data, year=2024):
    reference_distribution = _segment_total(data, "reference", "Gas distribution", year)
    reference_post = _segment_total(data, "reference", "Post-meter industrial and power", year)
    specifications = [
        ("distribution composite practice", "reference", "Gas distribution",
         "less than half plastic and/or limited LDAR"),
        ("distribution composite practice", "lower_distribution_only", "Gas distribution",
         "more than half plastic and LDAR; Tier 1 cannot separate the two effects"),
        ("distribution activity basis", "throughput", "Gas distribution",
         "reported gas throughput rather than measured pipeline length"),
        ("post-meter factor transferability", "reference", "Post-meter industrial and power",
         "IPCC 6.1 t CH4/million m3 transferred from Revised 1996 basis"),
        ("post-meter factor transferability", "post_meter_half_factor",
         "Post-meter industrial and power", "50% factor stress test"),
        ("post-meter factor transferability", "no_post_meter_industrial",
         "Post-meter industrial and power", "segment excluded pending Pakistan-specific evidence"),
    ]
    output = []
    for assumption, scenario, segment, evidence in specifications:
        value = _segment_total(data, scenario, segment, year)
        baseline = reference_distribution if segment == "Gas distribution" else reference_post
        ledger = [row for row in segment_inventory.inventory_rows(data, scenario, year=year)
                  if row["subitem"] == segment]
        output.append({
            "assumption": assumption,
            "scenario": scenario,
            "segment": segment,
            "segment_mt_co2e": value,
            "difference_from_reference_mt_co2e": value - baseline,
            "ch4_factor_id": next((row["factor_id"] for row in ledger
                                   if row["gas"] == "CH4"), "excluded"),
            "ch4_factor_value": next((row["factor_value"] * row["structural_multiplier"]
                                      for row in ledger if row["gas"] == "CH4"), 0.0),
            "activity_value": next((row["activity_value"] for row in ledger), 0.0),
            "activity_unit": next((row["activity_unit"] for row in ledger), ""),
            "evidence_or_limitation": evidence,
        })
    return output


def distribution_practice_evidence(path=DISTRIBUTION_EVIDENCE_PATH):
    """Expose the two-part IPCC practice test and the evidence coverage.

    The lower Tier-1 factor requires both a majority-plastic network and LDAR.
    Documented leak surveys therefore cannot, by themselves, select that factor.
    """
    output = []
    for row in _csv_rows(path):
        parsed = dict(row)
        for field in ("fiscal_year", "evidence_value", "national_denominator",
                      "coverage_pct"):
            parsed[field] = float(row[field]) if row[field] else ""
        parsed["ipcc_lower_factor_test"] = (
            "plastic share >50% AND LDAR in use")
        parsed["reference_selection"] = (
            "higher/default conditional factor while either national criterion is unresolved")
        output.append(parsed)
    return output


def post_meter_factor_lineage(data):
    """Reproduce the transferred Revised-1996 energy-to-volume conversion."""
    source_kg_per_pj = 175000.0
    energy_mj_per_m3 = 35.0
    derived_t_per_million_m3 = source_kg_per_pj * energy_mj_per_m3 / 1_000_000.0
    registered = data.factor2019("post_meter_industrial_ch4")["value"]
    return [{
        "factor_id": "post_meter_industrial_ch4",
        "source_value_kg_per_PJ": source_kg_per_pj,
        "energy_conversion_MJ_per_m3": energy_mj_per_m3,
        "derived_t_CH4_per_million_m3": derived_t_per_million_m3,
        "registered_t_CH4_per_million_m3": registered,
        "rounding_difference_t_per_million_m3": registered - derived_t_per_million_m3,
        "ipcc_activity_definition": "non-residential and commercial gas consumed",
        "source_reference": ("IPCC 2019 Refinement Volume 2 Chapter 4, Table 4.2.4k "
                             "note c and Table 4.2.7"),
        "transfer_status": "Tier-1 transferred factor; not Pakistan-specific measurement",
    }]


def post_meter_end_use_audit(data, path=POST_METER_END_USE_PATH):
    """Disaggregate the dominant transferred factor by observed end-use throughput."""
    factor = data.factor2019("post_meter_industrial_ch4")["value"]
    registered_activity = data.activity("post_meter_nonresidential")["value"]
    rows = []
    included_activity = 0.0
    for source in _csv_rows(path):
        annual = float(source["annual_million_m3"])
        included = source["include_in_ipcc_post_meter"] == "yes"
        if included:
            included_activity += annual
        ch4 = annual * factor / 1000.0 if included else 0.0
        rows.append({
            **source,
            "throughput_mmcfd": float(source["throughput_mmcfd"]),
            "annual_million_m3": annual,
            "factor_t_CH4_per_million_m3": factor if included else 0.0,
            "ch4_Gg": ch4,
            "co2e_Mt_AR5_fossil_CH4": ch4 * 30.0 / 1000.0,
            "activity_role": "estimated" if included else "excluded/control",
        })
    for row in rows:
        row["included_activity_control_million_m3"] = included_activity
        row["registered_activity_million_m3"] = registered_activity
        row["rounding_residual_million_m3"] = included_activity - registered_activity
    return rows


def structural_data_priorities(reference_total, scenarios, sensitivity):
    """Put discrete model value and conditional sensitivity in one priority table."""
    output = []
    structural_labels = {
        "lower_distribution_only": "distribution material/LDAR practice",
        "lower_transmission_only": "transmission LDAR/compressor practice",
        "post_meter_half_factor": "post-meter factor transferability (half)",
        "no_post_meter_industrial": "post-meter segment transferability (exclude)",
        "no_processing_proxy": "processing throughput coverage",
    }
    by_name = {row["scenario"]: row for row in scenarios}
    for scenario, label in structural_labels.items():
        if scenario not in by_name:
            continue
        value = by_name[scenario]["mt_co2e_ar5"]
        output.append({
            "priority_type": "structural",
            "input_or_decision": label,
            "scenario": scenario,
            "effect_mt_co2e": value - reference_total,
            "absolute_effect_mt_co2e": abs(value - reference_total),
            "conditional_sensitivity_pct": "",
            "interpretation": "change from the deterministic reference configuration",
        })
    for row in sensitivity[:10]:
        output.append({
            "priority_type": "parametric",
            "input_or_decision": row["input_group"],
            "scenario": "reference Monte Carlo",
            "effect_mt_co2e": "",
            "absolute_effect_mt_co2e": "",
            "conditional_sensitivity_pct": row["normalized_squared_spearman_pct"],
            "interpretation": row["interpretation"],
        })
    return output


def completeness_materiality(rows, reference_total):
    """Add a transparent screen: numeric where held activity permits a bound, and
    explicitly non-numeric where it does not."""
    classifications = {
        ("1.B.1", "Coal mining"): ("partially screened",
                                   "national coal production by mine type; mine-gas "
                                   "content"),
        ("1.B.2.a.i", "Exploration"): ("unknown", "exploration and testing events"),
        ("1.B.2.a.vii", "Abandoned wells"): ("unknown", "plugged/unplugged well census"),
        ("1.B.2.b.i", "Exploration"): ("unknown", "exploration and testing events"),
        ("1.B.2.b.iv", "Underground and surface storage"): (
            "probably minor/NO", "reassess when an operating storage facility is reported"),
        ("1.B.2.b.vi", "Natural-gas vehicles"): (
            "unknown", "active CNG vehicle count by technology"),
        ("1.B.2.b.vii", "Other and accidents"): (
            "potentially material", "incident, rupture, blowdown and super-emitter records"),
    }
    output = []
    for source in rows:
        row = dict(source)
        key = (row["ipcc_code"], row["subsegment"])
        materiality, data_need = classifications.get(
            key, ("estimated/included" if row["central_inventory"] == "yes" else "not applicable",
                  row["principal_gap"]))
        screen_upper = ""
        screen_basis = ("No numerical upper bound assigned without defensible public activity"
                        if "unknown" in materiality or materiality == "potentially material"
                        else "central ledger or reported non-occurrence/NA")
        if key == ("1.B.1", "Coal mining"):
            # The held NEPRA mine-mouth deliveries bound the SURFACE share only; the
            # column carries that number with its partial scope in the basis, because a
            # bare figure here would read as the category's ceiling and underground
            # factors run thirty times the surface low.
            from pkinv.sectors.fugitives import coal_screen
            lo, hi = coal_screen.surface_band_mt()
            screen_upper = hi
            screen_basis = ("PARTIAL: Thar surface mine-mouth deliveries only "
                            "(%.4f-%.4f Mt, outputs/fugitives_coal_screen_2024.csv); "
                            "underground production not held and not bounded" % (lo, hi))
        row.update({
            "materiality_class": materiality,
            "screen_threshold_mt_co2e": 0.01 * reference_total,
            "screen_upper_mt_co2e": screen_upper,
            "screen_basis": screen_basis,
            "priority_data_requirement": data_need,
        })
        output.append(row)
    return output
