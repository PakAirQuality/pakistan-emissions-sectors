"""Physical gas-flow closure and UFG plausibility diagnostics."""
from __future__ import annotations

from pkinv.assets import asset_path

from pkinv.activity.store import read_rows as _activity_rows
import csv
import os

from pkinv.core.components import co2e_Mt
from pkinv.paths import DATA
from pkinv.sectors.fugitives import leakage, segment_inventory


FLOW_PATH = asset_path(DATA, "activity", "fugitives",
                         "gas_flow_controls_2021_24.csv")


def controls(path=FLOW_PATH):
    output = []
    for row in _activity_rows(path, comments=False):
        parsed = dict(row)
        parsed["fiscal_year"] = int(row["fiscal_year"])
        for key in ("gross_domestic_production_mmcfd",
                    "indigenous_marketable_supply_mmcfd", "rlng_supply_mmcfd",
                    "total_supply_mmcfd", "categorized_consumption_mmcfd",
                    "ufg_mmcfd"):
            parsed[key] = float(row[key])
        output.append(parsed)
    return output


def balance_rows(data, path=FLOW_PATH):
    """A two-stage conserved bridge from gross production to reported end use.

    Residuals are statistical/accounting quantities. They are never interpreted as
    atmospheric methane without additional evidence.
    """
    conversion = 365.0 * data.p("mcf_to_e6m3")
    output = []
    for row in controls(path):
        gross = row["gross_domestic_production_mmcfd"]
        indigenous = row["indigenous_marketable_supply_mmcfd"]
        rlng = row["rlng_supply_mmcfd"]
        supply = row["total_supply_mmcfd"]
        consumption = row["categorized_consumption_mmcfd"]
        ufg = row["ufg_mmcfd"]
        output.append({
            "fiscal_year": row["fiscal_year"],
            "gross_domestic_production_mmcfd": gross,
            "indigenous_marketable_supply_mmcfd": indigenous,
            "upstream_statistical_difference_mmcfd": gross - indigenous,
            "upstream_difference_pct_gross": 100.0 * (gross - indigenous) / gross,
            "rlng_supply_mmcfd": rlng,
            "reported_total_supply_mmcfd": supply,
            "supply_identity_residual_mmcfd": supply - indigenous - rlng,
            "categorized_consumption_mmcfd": consumption,
            "ufg_mmcfd": ufg,
            "downstream_statistical_discrepancy_mmcfd": supply - consumption - ufg,
            "downstream_statistical_discrepancy_pct_supply":
                100.0 * (supply - consumption - ufg) / supply,
            "gross_domestic_production_million_m3": gross * conversion,
            "reported_total_supply_million_m3": supply * conversion,
            "categorized_consumption_million_m3": consumption * conversion,
            "ufg_million_m3": ufg * conversion,
            "source": row["source"],
            "source_reference": row["source_reference"],
            "interpretation": ("physical-flow control with explicit statistical discrepancies; "
                               "neither residual is methane emissions"),
        })
    return output


def upstream_disposition_rows(data, flare_volume_bcm=None, path=FLOW_PATH):
    """Expose, rather than relabel, the gross-to-marketable upstream difference.

    Public national controls do not currently split the difference among reinjection,
    field/plant own use, processing shrinkage, flaring/venting and other adjustments.
    The satellite flare volume is shown as a period-mismatched observation memo and is
    not subtracted from the fiscal control.
    """
    conversion = 365.0 * data.p("mcf_to_e6m3")
    output = []
    for row in controls(path):
        difference = (row["gross_domestic_production_mmcfd"] -
                      row["indigenous_marketable_supply_mmcfd"])
        satellite_mmcfd = ""
        satellite_share = ""
        if row["fiscal_year"] == 2024 and flare_volume_bcm is not None:
            satellite_mmcfd = float(flare_volume_bcm) * 1000.0 / conversion
            satellite_share = 100.0 * satellite_mmcfd / difference
        output.append({
            "fiscal_year": row["fiscal_year"],
            "gross_production_mmcfd": row["gross_domestic_production_mmcfd"],
            "marketable_supply_mmcfd": row["indigenous_marketable_supply_mmcfd"],
            "reported_reinjection_mmcfd": "",
            "reported_upstream_own_use_mmcfd": "",
            "reported_processing_shrinkage_mmcfd": "",
            "reported_vented_gas_mmcfd": "",
            "reported_flared_gas_mmcfd": "",
            "other_identified_adjustments_mmcfd": "",
            "unresolved_upstream_difference_mmcfd": difference,
            "unresolved_upstream_difference_pct_gross": (
                100.0 * difference / row["gross_domestic_production_mmcfd"]),
            "calendar_2024_viirs_flare_equivalent_mmcfd": satellite_mmcfd,
            "calendar_2024_viirs_share_of_fiscal_difference_pct": satellite_share,
            "closure_status": "unresolved; no component is treated as leakage",
            "data_priority": ("plant throughput, reinjection, own use, NGL/shrinkage and "
                              "operator vent/flare volumes"),
        })
    return output


def _network_ch4_Gg(data, scenario, year=2024):
    names = {"Gas transmission", "Gas distribution"}
    return sum(row["emissions_Gg"] for row in
               segment_inventory.inventory_rows(data, scenario, year=year)
               if row["gas"] == "CH4" and row["subitem"] in names)


def ufg_compatibility(data, year=2024):
    """Compare IPCC pre-meter network CH4 with the UFG physical-loss envelope."""
    ufg_activity = data.activity("ufg_diagnostic", year=year)["value"]
    ufg_ch4_Gg = (ufg_activity * data.p("gas_density_kg_per_m3") *
                  data.p("gas_ch4_fraction"))
    output = []
    for scenario in ("reference", "lower_practices", "throughput",
                     "lower_throughput", "lower_distribution_only",
                     "lower_transmission_only"):
        ch4 = _network_ch4_Gg(data, scenario, year=year)
        output.append({
            "scenario": scenario,
            "network_ch4_Gg": ch4,
            "network_co2e_Mt_AR5": co2e_Mt("CH4", ch4, "AR5", fossil=True),
            "ufg_100pct_ch4_Gg": ufg_ch4_Gg,
            "ufg_physical_fraction_required_pct": 100.0 * ch4 / ufg_ch4_Gg,
            "compatible_with_10pct_ufg": ch4 <= 0.10 * ufg_ch4_Gg,
            "compatible_with_25pct_ufg": ch4 <= 0.25 * ufg_ch4_Gg,
            "interpretation": ("fraction of reported UFG that would need to be physical "
                               "methane loss to equal IPCC transmission plus distribution CH4"),
        })
    return output
