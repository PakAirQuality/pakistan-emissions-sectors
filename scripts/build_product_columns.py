#!/usr/bin/env python3
"""The typed column registry of every CSV product in data/product_schemas.csv (rc41).

Writes: data/product_columns.csv

WHY (the nineteenth review's D-2). The product registry declared primary keys and the
tests held them; nothing declared what a COLUMN is. A status string could sit in a numeric
column, a sector id could name a sector no registry knows, a month could fall outside the
window, and every reader that parsed the file found out one row at a time. This registry
says, per product and column: the type (int, float, str), whether an empty cell is allowed,
and the constraint where one is known - an enumeration (the vocabulary a column draws
from) or a foreign key (the registry column its values must exist in).

HOW MUCH IS INFERRED AND HOW MUCH DECLARED, stated so a reader can weigh the registry.
Type and nullability are inferred from the shipped file (the narrowest type every
non-empty cell parses as), with explicit nullable numeric contracts for entirely
unestimated bounds, and frozen here; a rebuild that widens a column - a number
becoming text - fails tests/validation/test_product_columns.py. Constraints are DECLARED
below by column name, never inferred: a small distinct-value set is not evidence of a
vocabulary. --check re-derives the registry and reports any drift.

Usage:  python3 scripts/build_product_columns.py [--check]
"""
import os
import sys
import csv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.assets import asset_path

from pkinv.core.io import read_rows, write_or_check  # noqa: E402
from pkinv.core import configurations as conf  # noqa: E402
from pkinv.core import registry as _registry  # noqa: E402

SCHEMAS = asset_path(ROOT, "data", "product_schemas.csv")
OUT = asset_path(ROOT, "data", "product_columns.csv")
FIELDS = ("product_id", "column", "type", "nullable", "constraint")

# Declared constraints, by column name. An enum names the vocabulary; a foreign key names
# the registry file and column the values must exist in (repo-relative path#column).
# A column absent here carries no constraint beyond its type.
ENUMS = {
    "gas": "CO2|CH4|N2O",
    "configuration_id": "|".join(conf.ALL),
    "spatial_view": "physical|origin|accounting|all",
    "absence_reason": "unresolved-in-grid|unallocated-below-adm1",
    "estimate_status": "E|NE|IE|NO|NA",
    # the reporting-sector axis (data/stream_reporting_sector.csv): the module vocabulary,
    # from the sector registry - never a second list
    "reporting_sector": "|".join(sorted(s.NAME for s in _registry.all_sectors())),
    # The air beta's species union across the seven sector layers. Deliberately wider than
    # the agriculture seven: VOC (power), HC (aviation), HCl (waste), OC/PM10/TSP/PM
    # (particulate strata) - the vocabulary is unharmonised at the sources and the dimension
    # table (dim_pollutant) is where the containment story lives, not this constraint.
    "pollutant": "BC|CO|HC|HCl|NH3|NMVOC|NOx|OC|PM|PM10|PM2.5|SO2|TSP|VOC",
}
FOREIGN_KEYS = {
    "source_stream_id": "outputs/pakemis_source_streams.csv#source_stream_id",
    "period_id": "data/periods.csv#period_id",
    "component_id": "outputs/pakemis_atomic_annual.csv#component_id",
}
# Columns whose values are a ';'-joined list of ids rather than one id (shared shapes);
# their membership is checked element-wise against the same registry.
LIST_FOREIGN_KEYS = {
    "adm2_ids": "data/adm2_canonical.csv#adm2_id",
}
# Per-product overrides, declared with the reason: a column of the same name that draws
# from a different vocabulary (the ADM2 views' absence rows say gas=all; the coverage
# matrix carries the F-gases; the configuration products key on the named-configuration
# registry, not the two gridded ids) or from none ("" - a free label).
OVERRIDES = {
    ("uncertainty.longitudinal", "model_basis"):
        ("enum:legacy_parameter_graph_sensitivity_not_native_material_flow",
         "this retained sensitivity diagnostic is not the native material-flow ensemble"),
    ("uncertainty.longitudinal_prefix", "model_basis"):
        ("enum:legacy_parameter_graph_sensitivity_not_native_material_flow",
         "paired historical-prefix sensitivity uses the same legacy parameter graph"),
    ("uncertainty.trend", "model_basis"):
        ("enum:legacy_parameter_graph_sensitivity_not_native_material_flow",
         "legacy parameter-graph trend diagnostics remain distinct from native paired draws"),
    ("semantic.fact_air_adm1", "period_id"):
        ("enum:CY2024|FY2023-24", "the air layers are single-period; CY2024 is a calendar "
         "label of dim_period's calendar block, not a fiscal registry row"),
    ("semantic.fact_air_adm2", "period_id"):
        ("enum:CY2024|FY2023-24", "the air layers are single-period; CY2024 is a calendar "
         "label of dim_period's calendar block, not a fiscal registry row"),
    ("air.adm1", "period_id"):
        ("enum:CY2024|FY2023-24", "the air layers are single-period; CY2024 is a calendar "
         "label of dim_period's calendar block, not a fiscal registry row"),
    ("air.adm2", "period_id"):
        ("enum:CY2024|FY2023-24", "the air layers are single-period; CY2024 is a calendar "
         "label of dim_period's calendar block, not a fiscal registry row"),
    ("semantic.fact_air_annual", "period_id"):
        ("enum:CY2024|FY2023-24", "the air layers are single-period: five sectors on the "
         "calendar year, two on the fiscal reference year; CY2024 is a calendar label of "
         "dim_period's calendar block, not a row of the fiscal period registry the "
         "period_id foreign key points at"),
    ("annual.atomic", "gas"): ("", "the atomic table carries air pollutants beside the three GHGs"),
    ("annual.agriculture_basis_change", "comparison_status"):
        ("enum:compared_to_archived_calendar|archived_calendar_comparator_absent",
         "the FY2024-25 fiscal estimate has no archived calendar comparator; missing comparison values are nullable, not zero"),
    ("extension.power_controls", "estimate_status"):
        ("enum:physical_station_fuel|derived_fleet_intensity_gap|not_estimated_missing_fuel",
         "this control audit uses physical-fuel evidence states rather than IPCC E/NE notation"),
    ("spatial.adm2_monthly", "gas"): ("enum:CO2|CH4|N2O|all", "absence rows say gas=all"),
    ("spatial.adm2_monthly_sector", "gas"): ("enum:CO2|CH4|N2O|all", "absence rows say gas=all"),
    ("spatial.adm2_ledger_2024", "gas"): ("enum:CO2|CH4|N2O|all", "absence rows say gas=all"),
    ("spatial.adm2_by_year", "gas"): ("enum:CO2|CH4|N2O|all", "absence rows say gas=all"),
    ("spatial.adm2_sector_by_year", "gas"):
        ("enum:CO2|CH4|N2O|all", "absence rows say gas=all"),
    ("spatial.adm2_sector_by_year", "spatial_view"):
        ("enum:physical|origin|accounting|all", "absence rows say spatial_view=all"),
    ("spatial.adm2_monthly_by_year", "gas"):
        ("enum:CO2|CH4|N2O|all", "absence rows say gas=all"),
    ("spatial.configuration_adm2", "gas"):
        ("enum:CO2|CH4|N2O|all", "typed absence rows have no species-specific estimate and say gas=all"),
    ("spatial.configuration_adm2_monthly", "gas"):
        ("enum:CO2|CH4|N2O|all", "typed absence rows have no species-specific estimate and say gas=all"),
    ("spatial.adm2_monthly_by_year", "spatial_view"):
        ("enum:physical|origin|accounting|all", "absence rows say spatial_view=all"),
    ("spatial.weights_by_year", "spatial_time_basis"):
        ("enum:annual_observed_activity|static_structural|"
         "modelled_population_proxy|calendar_activity_proxy|reference_shape_backcast|reference_shape_forward|"
         "substituted_surface|unallocated|not_present",
         "does the evidence behind this surface have a time axis the engine reads for this "
         "period? The three values this replaced answered a different question - they were a "
         "function of within_province_placement, already a column in the same row"),
    ("spatial.weights_by_year", "other_membership"):
        ("enum:ict_only|ajk_gb|ict_ajk_gb|unresolved_group|none",
         "the territorial membership vocabulary of data/province_shares.csv"),
    ("spatial.weights_by_year", "control_level"):
        ("enum:adm1|grid|", "empty where the stream-year carries no mass"),
    ("spatial.adm2_by_year", "spatial_view"):
        ("enum:physical|origin|accounting|all", "absence rows say spatial_view=all"),
    ("completeness.table", "gas"): ("", "a slash-joined list of the gases a category reports"),
    # SF6 joined the vocabulary on 2026-10-05, when closing the completeness table's universe
    # added 2.G.1 (electrical equipment) and 2.G.2 - the two categories whose gas IS SF6. The
    # enum had HFC and PFC because 2.F was already declared; a gas a category reports has to
    # be nameable here even when every one of its cells is NE, or the typed contract rejects
    # the inventory for admitting an absence it had always had.
    ("completeness.coverage_matrix", "gas"):
        ("enum:CO2|CH4|N2O|HFC|PFC|SF6", "the matrix carries the F-gas and SF6 categories"),
    # the air panel's two configurations (air spatial Wave A): the reference plus the
    # air-only survey-anchored dung series - conf.AIR_ALL, not the GHG pair
    ("air.atomic_annual", "configuration_id"):
        ("enum:" + "|".join(conf.AIR_ALL),
         "the air panel's own configuration vocabulary (conf.AIR_ALL)"),
    ("air.annual", "configuration_id"):
        ("enum:" + "|".join(conf.AIR_ALL),
         "the air panel's own configuration vocabulary (conf.AIR_ALL)"),
    ("semantic.fact_air_panel", "configuration_id"):
        ("enum:" + "|".join(conf.AIR_ALL),
         "the air panel's own configuration vocabulary (conf.AIR_ALL)"),
    ("air.adm1_by_year", "configuration_id"):
        ("enum:" + "|".join(conf.AIR_ALL),
         "the air panel's own configuration vocabulary (conf.AIR_ALL)"),
    ("air.adm2_by_year", "configuration_id"):
        ("enum:" + "|".join(conf.AIR_ALL),
         "the air panel's own configuration vocabulary (conf.AIR_ALL)"),
    ("air.unallocated_by_year", "configuration_id"):
        ("enum:" + "|".join(conf.AIR_ALL),
         "the air panel's own configuration vocabulary (conf.AIR_ALL)"),
    ("air.spatial_support_by_year", "configuration_id"):
        ("enum:" + "|".join(conf.AIR_ALL),
         "the air panel's own configuration vocabulary (conf.AIR_ALL)"),
    ("air.lahore", "configuration_id"):
        ("enum:" + "|".join(conf.AIR_ALL),
         "the air panel's own configuration vocabulary (conf.AIR_ALL); rc58 Lahore view"),
    ("semantic.fact_air_lahore", "configuration_id"):
        ("enum:" + "|".join(conf.AIR_ALL),
         "the air panel's own configuration vocabulary (conf.AIR_ALL); rc58 Lahore view"),
    ("air.uncertainty_split_by_year", "configuration_id"):
        ("enum:" + "|".join(conf.AIR_ALL),
         "the air panel's own configuration vocabulary (conf.AIR_ALL)"),
    ("semantic.fact_air_adm1_year", "configuration_id"):
        ("enum:" + "|".join(conf.AIR_ALL),
         "the air panel's own configuration vocabulary (conf.AIR_ALL)"),
    ("semantic.fact_air_adm2_year", "configuration_id"):
        ("enum:" + "|".join(conf.AIR_ALL),
         "the air panel's own configuration vocabulary (conf.AIR_ALL)"),
    ("configurations.national", "configuration_id"): ("", "the registry of named configurations itself"),
    ("configurations.bridge", "configuration_id"): ("", "the bridge configurations' own ids, declared unpopulated"),
    # The coverage matrix keys on the reference id AND the named alternatives: the named
    # registry calls the reference `inventory_reference`, the gridded vocabulary calls it
    # REF_2023_24, so the vocabulary is spelled out from both at generation time.
    ("completeness.coverage_matrix", "configuration_id"):
        ("enum:" + "|".join(sorted(set(conf.ALL) | {r["configuration_id"] for r in read_rows(
            asset_path(ROOT, "outputs", "national_configurations.csv"))})),
         "the reference id plus the named-configuration registry"),
    ("completeness.mass", "configuration_id"):
        ("fk:outputs/national_configurations.csv#configuration_id", "keys on the named-configuration registry"),
    # v1.0.0: the semantic layer's dimensions ARE the vocabularies, and two of its facts
    # carry rows the atomic registries do not (the survey's category x gas rows; the
    # calendar periods), so they key on the semantic dimensions instead.
    ("semantic.dim_configuration", "configuration_id"): ("", "the semantic configuration dimension itself"),
    ("semantic.dim_period", "period_id"): ("", "the semantic period dimension itself: fiscal and calendar"),
    ("semantic.dim_gas", "gas"): ("", "the semantic gas dimension itself"),
    ("semantic.fact_annual_calendar", "period_id"): ("fk:outputs/semantic/dim_period.csv#period_id", "calendar periods"),
    ("semantic.fact_annual", "gas"): ("", "the atoms carry air pollutants beside the three GHGs"),
    ("semantic.fact_annual", "component_id"): ("", "atoms plus the survey's category x gas rows"),
    ("semantic.fact_monthly", "component_id"): ("", "atoms plus the survey's category x subitem x gas rows"),
    ("semantic.fact_completeness", "gas"): ("", "a slash-joined list of the gases a category reports"),
    ("semantic.fact_transfer", "configuration_id"): ("", "the ledger map's own configuration labels"),
    ("semantic.fact_adm2_month", "gas"): ("enum:CO2|CH4|N2O|all", "absence rows say gas=all"),
    ("semantic.fact_adm2_year", "gas"): ("enum:CO2|CH4|N2O|all", "absence rows say gas=all"),
    ("semantic.fact_completeness_mass", "configuration_id"):
        ("fk:outputs/national_configurations.csv#configuration_id", "keys on the named-configuration registry"),
}

# An entirely unestimated numeric column contains only empty cells, so its type
# cannot be learned from values. These are optional numerical bounds, never
# notation strings or a zero-valued completeness estimate.
DECLARED_TYPES = {
    ("uncertainty.joint", "completeness_bound_Mt"): ("float", "yes"),
    ("semantic.fact_uncertainty", "completeness_bound_Mt"): ("float", "yes"),
}


def _infer(values):
    """(type, nullable) for a column's cell values."""
    non_empty = [v for v in values if v != ""]
    nullable = "yes" if len(non_empty) < len(values) else "no"
    if not non_empty:
        return "str", nullable
    kind = "int"
    for v in non_empty:
        if kind == "int":
            try:
                int(v)
                continue
            except ValueError:
                kind = "float"
        if kind == "float":
            try:
                float(v)
                continue
            except ValueError:
                return "str", nullable
    return kind, nullable


def build():
    rows = []
    for product in read_rows(SCHEMAS):
        rel = product["relative_path"]
        if not rel.endswith(".csv"):
            continue
        path = asset_path(ROOT, rel)
        if not os.path.exists(path):
            continue
        # Stream large monthly spatial products; inferring each column must not
        # retain millions of dictionaries and another list per column.
        with open(path, newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(line for line in handle if not line.startswith("#"))
            state = {column: ["int", False, False] for column in reader.fieldnames or []}
            count = 0
            for row in reader:
                count += 1
                for column, value in row.items():
                    item = state[column]
                    if value == "":
                        item[1] = True
                        continue
                    item[2] = True
                    if item[0] == "int":
                        try:
                            int(value)
                            continue
                        except ValueError:
                            item[0] = "float"
                    if item[0] == "float":
                        try:
                            float(value)
                        except ValueError:
                            item[0] = "str"
        if not count:
            continue
        for column, (kind, has_empty, has_value) in state.items():
            nullable = "yes" if has_empty else "no"
            if not has_value:
                kind = "str"
            kind, nullable = DECLARED_TYPES.get((product["product_id"], column),
                                                (kind, nullable))
            constraint = ""
            if (product["product_id"], column) in OVERRIDES:
                constraint = OVERRIDES[(product["product_id"], column)][0]
            elif column in ENUMS:
                constraint = "enum:" + ENUMS[column]
            elif column in FOREIGN_KEYS and not rel.endswith(FOREIGN_KEYS[column].split("#")[0].split("/")[-1]):
                constraint = "fk:" + FOREIGN_KEYS[column]
            elif column in LIST_FOREIGN_KEYS:
                constraint = "fk-list:" + LIST_FOREIGN_KEYS[column]
            rows.append({"product_id": product["product_id"], "column": column, "type": kind,
                         "nullable": nullable, "constraint": constraint})
    return rows


def main(check=False):
    rows = build()
    return write_or_check(OUT, FIELDS, rows, check=check, lineterminator="\n", banner=(
        "THE TYPED COLUMN REGISTRY (rc41): per CSV product in data/product_schemas.csv, every",
        "column's type (int|float|str) and nullability, inferred from the shipped file and",
        "frozen here, and its declared constraint - enum:<a|b|c> or fk:<file>#<column> or",
        "fk-list:<file>#<column> for ';'-joined ids. tests/validation/test_product_columns.py",
        "holds every product to this; scripts/build_product_columns.py --check re-derives it."))


if __name__ == "__main__":
    raise SystemExit(main(check="--check" in sys.argv))
