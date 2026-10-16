"""Run the full national inventory end-to-end.

Sequences every phase as an isolated subprocess, times each, and prints a status table.
The isolation originally existed because each script did its own sys.path surgery and those
collided; the package makes that moot, but isolation is kept deliberately so that one
sector's failure cannot abort the whole run.

WHAT THIS NO LONGER RUNS. Before the repository split this orchestrator also drove the
satellite nowcasters, the ML training pipeline, the gridded and district surfaces, the LULUCF
extension and the agriculture-manuscript layers (time series, agriculture-scoped Monte Carlo
and key categories, the air trend and uncertainty layers). rc36 put those back: their
products turned out to be national inputs, not research. The research-grade sector grids
(agriculture's category maps, the air layers) still live with their sectors and are
hand-run - EXCEPT the district panel
(agriculture.gis.district_downscale), promoted to a canonical input in rc9 because
the national cube reads it (docs/spatial_products_contract.md); the NATIONAL 0.05-degree monthly cube runs
here, in the cross-sector layer, against the committed proxy caches. What

Usage (both are the same program):
  python3 -m pkinv.run_all            # everything
  python3 -m pkinv.run_all --quick    # omit any task explicitly requiring network
  python3 -m pkinv.build             # cached developer build; Make and CI share PHASES
  python3 -m pkinv.run_all --strict --ledger logs/pakemis_run_ledger.json [--seeded logs/seeded_products.json]
                                      # rc41: every phase must exit 0 (a non-core error is a
                                      # FAIL, not a skip) and a ledger records per phase what
                                      # was written - the mode a reproduction runs in
  python3 -m pkinv.run_all --from "Aviation"   # resume at one phase (development only; the
                                      # earlier phases are recorded SKIP (resume), never OK)
  python3 -m pkinv.run_all --only "Aviation,Cement"
                                      # run exactly these phases and nothing else
  python3 -m pkinv.run_all --changed  # skip every phase whose inputs, imported code and
                                      # outputs are unchanged since it last ran. Development
                                      # only: refused under --strict, and the first --changed
                                      # run is a full build that populates the cache. See the
                                      # incremental block below the ledger for what it will
                                      # not do.

NOT PHASES, ON PURPOSE: scripts/make_readme_tables.py and
scripts/make_release_cover.py regenerate prose from these outputs. They run
from the Makefile's `national` target and the release fixpoint (the cover
quotes the manifest's hash, which only exists once the tree is clean), and CI
runs both as --check. tests/test_build_definition.py carries them as EXEMPT.
"""
import fnmatch
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import time
import tempfile
import shlex
from dataclasses import dataclass, replace

from pkinv.paths import ROOT


@dataclass(frozen=True)
class Phase:
    """One build phase. `target` is a dotted module run with -m (an optional
    trailing word is an argument), or a repo-relative .py path for the scripts
    that live outside the package - keep it double-quoted on ONE line, because
    tests/test_build_definition.py parses this file's text for those strings.

    writes[0] is the KEY OUTPUT the run checks (see below); the rest are the
    side outputs other phases read. `reads` is a tri-state: None means the
    phase's inputs have NOT been audited yet and check_order() skips it; a
    tuple - even an empty one - is a declaration. Read forms: "outputs/x.csv",
    "data/x.csv", "glob:outputs/*pattern*" for the two consumers that glob,
    "held:outputs/x.csv" for a committed hand-run product no phase writes (the
    road graph), and "prior:outputs/x.csv" for a read of the PREVIOUS release's
    artefact by design (the deposit manifest takes document hashes from the
    release manifest the fixpoint cut last time, rather than re-hashing 3.8 GB).
    The checker skips held: and prior: but the declaration is on record.

    The three flags replace the label-keyed side tuples this file used to
    carry 260 lines below the list, where renaming a label silently un-skipped
    a network phase:
      network      needs network or a cached download; --quick skips it
      prints_only  COMPUTES AND PRINTS but writes nothing of its own - its CSV
                   is written by that sector's runner earlier in the list, so
                   its declared path is checked against the whole run's start,
                   not the phase's. Five of the seven air-pollutant phases are
                   in this state, and each used to declare an artefact a
                   different phase had produced. check_order() treats a
                   prints_only phase's writes as READS for the same reason.
      idempotent   brings a destination into line with a source and correctly
                   writes NOTHING when already in line; only existence is
                   checked here - the real check (every manuscript figure at
                   least as new as its source) is tests/paper_numbers/test_release_integrity.py's
                   test_no_shipped_figure_predates_its_source.
    """
    label: str
    target: str
    core: bool = False
    writes: tuple = ()
    reads: tuple = None
    network: bool = False
    prints_only: bool = False
    idempotent: bool = False
    # rc42: third-party packages the phase imports unconditionally, checked BEFORE the
    # first phase runs so a missing pin in requirements.lock stops a strict run at second
    # zero with the package named, not at phase forty with an ImportError traceback (the
    # twentieth review's reproduction stopped on openap that way).
    requires: tuple = ()
    # True only after complete inputs AND exclusive output ownership were audited.
    # Observing one run is useful evidence, but is not such an audit.
    audited: bool = False
    # science | validation | manuscript | release, from CATEGORIES below (rc69); the build
    # groups select on it. None only before _with_categories() has run.
    category: str = None

    @property
    def key_output(self):
        return self.writes[0]


#
# THE KEY OUTPUT IS CHECKED, NOT DECORATIVE. It used to be a string printed in the summary
# and read by nothing, and it drifted: when the sectors were harmonised onto one reporting
# period their outputs were renamed, and four of these paths went on naming files that no
# longer existed anywhere while their phases reported OK beside them. A fifth pointed at a
# superseded vintage that was still sitting in outputs/ and therefore looked fine. _wrote()
# now requires the declared path to have been written DURING this run, so a phase cannot
# claim an artefact it did not produce and a rename cannot go unnoticed.
#
# Order matters. Sectors first, because the cross-sector layer reads what they write; the
# figure sync last, because it copies regenerated figures into the manuscripts and running
# it earlier ships whatever PNGs happened to be there.

# rc69: the complete inputs of the two slowest uncertainty phases, as their own runs observed
# them through the build's file-open audit (no native reader: every input is a CSV), so both
# can be AUDITED and run side by side. Re-derive from logs/build_cache.json observed_reads if
# either phase starts reading something new; tests/test_build_categories.py holds the two
# phases audited, adjacent and free of shared writes.
GHG_UNCERTAINTY_READS = (
    "data/catalog/assets.csv",
    "data/catalog/canonical.json",
    "data/catalog/canonical_tables.csv",
    "data/sectors/agriculture/activity/crops_2024.csv",
    "data/sectors/agriculture/activity/es_fiscal_series.csv",
    "data/sectors/agriculture/activity/fertilizer_2024.csv",
    "data/sectors/agriculture/activity/historical/crops.csv",
    "data/sectors/agriculture/activity/historical/fertilizer_n.csv",
    "data/sectors/agriculture/activity/historical/livestock_stocks.csv",
    "data/sectors/agriculture/activity/livestock_2024.csv",
    "data/sectors/agriculture/canonical/activity/crops_2024.csv",
    "data/sectors/agriculture/canonical/activity/es_fiscal_series.csv",
    "data/sectors/agriculture/canonical/activity/fertilizer_2024.csv",
    "data/sectors/agriculture/canonical/activity/historical/crops.csv",
    "data/sectors/agriculture/canonical/activity/historical/fertilizer_n.csv",
    "data/sectors/agriculture/canonical/activity/historical/livestock_stocks.csv",
    "data/sectors/agriculture/canonical/activity/livestock_2024.csv",
    "data/sectors/agriculture/canonical/parameters/burning_params.csv",
    "data/sectors/agriculture/canonical/parameters/mms_shares.csv",
    "data/sectors/agriculture/canonical/parameters/parameters.csv",
    "data/sectors/agriculture/canonical/parameters/residue_params.csv",
    "data/sectors/agriculture/parameters/burning_params.csv",
    "data/sectors/agriculture/parameters/mms_shares.csv",
    "data/sectors/agriculture/parameters/parameters.csv",
    "data/sectors/agriculture/parameters/residue_params.csv",
    "data/sectors/aviation/activity/fuel_sales.csv",
    "data/sectors/aviation/activity/movements_airport.csv",
    "data/sectors/aviation/canonical/activity/fuel_sales.csv",
    "data/sectors/aviation/canonical/activity/movements_airport.csv",
    "data/sectors/aviation/canonical/evidence/benchmarks.csv",
    "data/sectors/aviation/canonical/lookups/aircraft_aliases.csv",
    "data/sectors/aviation/canonical/lookups/operator_groups.csv",
    "data/sectors/aviation/canonical/parameters/aviation_engine_map.csv",
    "data/sectors/aviation/canonical/parameters/aviation_fleet_mix.csv",
    "data/sectors/aviation/canonical/parameters/aviation_params.csv",
    "data/sectors/aviation/evidence/benchmarks.csv",
    "data/sectors/aviation/lookups/aircraft_aliases.csv",
    "data/sectors/aviation/lookups/operator_groups.csv",
    "data/sectors/aviation/parameters/aviation_engine_map.csv",
    "data/sectors/aviation/parameters/aviation_fleet_mix.csv",
    "data/sectors/aviation/parameters/aviation_params.csv",
    "data/sectors/fugitives/activity/anchor_activity_2021_23.csv",
    "data/sectors/fugitives/activity/anchor_activity_2023_24.csv",
    "data/sectors/fugitives/activity/fertilizer_gas_class.csv",
    "data/sectors/fugitives/activity/gas_flow_controls_2021_24.csv",
    "data/sectors/fugitives/activity/gas_network.csv",
    "data/sectors/fugitives/activity/infrastructure_2023_24.csv",
    "data/sectors/fugitives/activity/infrastructure_history_2015_21.csv",
    "data/sectors/fugitives/activity/production.csv",
    "data/sectors/fugitives/activity/production_province.csv",
    "data/sectors/fugitives/activity/provincial_controls_2023_24.csv",
    "data/sectors/fugitives/canonical/activity/anchor_activity_2021_23.csv",
    "data/sectors/fugitives/canonical/activity/anchor_activity_2023_24.csv",
    "data/sectors/fugitives/canonical/activity/gas_flow_controls_2021_24.csv",
    "data/sectors/fugitives/canonical/activity/gas_network.csv",
    "data/sectors/fugitives/canonical/activity/infrastructure_2023_24.csv",
    "data/sectors/fugitives/canonical/activity/infrastructure_history_2015_21.csv",
    "data/sectors/fugitives/canonical/activity/production.csv",
    "data/sectors/fugitives/canonical/activity/production_province.csv",
    "data/sectors/fugitives/canonical/activity/provincial_controls_2023_24.csv",
    "data/sectors/fugitives/canonical/parameters/fugitives_ipcc2019_factors.csv",
    "data/sectors/fugitives/canonical/parameters/fugitives_params.csv",
    "data/sectors/fugitives/parameters/fugitives_ipcc2019_factors.csv",
    "data/sectors/fugitives/parameters/fugitives_params.csv",
    "data/sectors/industry/activity/coal_by_sector_vintages.csv",
    "data/sectors/industry/activity/gas_consumption.csv",
    "data/sectors/industry/activity/ocac_non_energy_sectoral.csv",
    "data/sectors/industry/canonical/activity/coal_by_sector_vintages.csv",
    "data/sectors/industry/canonical/activity/gas_consumption.csv",
    "data/sectors/industry/canonical/activity/ocac_non_energy_sectoral.csv",
    "data/sectors/industry/canonical/parameters/industry_params.csv",
    "data/sectors/industry/parameters/industry_params.csv",
    "data/sectors/ippu/activity/cement_monthly_2022.csv",
    "data/sectors/ippu/activity/cement_producer_census_2023_24.csv",
    "data/sectors/ippu/activity/chemical_plant_activity.csv",
    "data/sectors/ippu/activity/clinker_trade_annual.csv",
    "data/sectors/ippu/activity/clinker_trade_annual_controls.csv",
    "data/sectors/ippu/activity/clinker_trade_monthly.csv",
    "data/sectors/ippu/activity/company_clinker_2023_24.csv",
    "data/sectors/ippu/activity/facilities.csv",
    "data/sectors/ippu/activity/hfc_consumption_controls.csv",
    "data/sectors/ippu/activity/national_activity.csv",
    "data/sectors/ippu/activity/nitric_acid_monitoring.csv",
    "data/sectors/ippu/activity/nitric_acid_monitoring_detail.csv",
    "data/sectors/ippu/activity/production.csv",
    "data/sectors/ippu/canonical/activity/cement_monthly_2022.csv",
    "data/sectors/ippu/canonical/activity/cement_producer_census_2023_24.csv",
    "data/sectors/ippu/canonical/activity/chemical_plant_activity.csv",
    "data/sectors/ippu/canonical/activity/clinker_trade_annual.csv",
    "data/sectors/ippu/canonical/activity/clinker_trade_annual_controls.csv",
    "data/sectors/ippu/canonical/activity/clinker_trade_monthly.csv",
    "data/sectors/ippu/canonical/activity/company_clinker_2023_24.csv",
    "data/sectors/ippu/canonical/activity/facilities.csv",
    "data/sectors/ippu/canonical/activity/hfc_consumption_controls.csv",
    "data/sectors/ippu/canonical/activity/national_activity.csv",
    "data/sectors/ippu/canonical/activity/nitric_acid_monitoring.csv",
    "data/sectors/ippu/canonical/activity/nitric_acid_monitoring_detail.csv",
    "data/sectors/ippu/canonical/activity/production.csv",
    "data/sectors/ippu/canonical/evidence/chemical_plant_evidence.csv",
    "data/sectors/ippu/canonical/evidence/company_boundary_audit.csv",
    "data/sectors/ippu/canonical/lookups/facility_geocoding_overrides.csv",
    "data/sectors/ippu/canonical/parameters/ippu_params.csv",
    "data/sectors/ippu/evidence/chemical_plant_evidence.csv",
    "data/sectors/ippu/evidence/company_boundary_audit.csv",
    "data/sectors/ippu/lookups/facility_geocoding_overrides.csv",
    "data/sectors/ippu/metadata/cdm_access_manifest.csv",
    "data/sectors/ippu/parameters/ippu_params.csv",
    "data/sectors/power/activity/bagasse_generation.csv",
    "data/sectors/power/activity/captive_gas.csv",
    "data/sectors/power/activity/coal_energy_booking.csv",
    "data/sectors/power/activity/coal_rank_account.csv",
    "data/sectors/power/activity/fuel_consumed.csv",
    "data/sectors/power/activity/generation_by_fuel.csv",
    "data/sectors/power/canonical/activity/bagasse_generation.csv",
    "data/sectors/power/canonical/activity/captive_gas.csv",
    "data/sectors/power/canonical/activity/coal_rank_account.csv",
    "data/sectors/power/canonical/activity/fuel_consumed.csv",
    "data/sectors/power/canonical/activity/generation_by_fuel.csv",
    "data/sectors/power/canonical/parameters/power_coal_blend_by_year.csv",
    "data/sectors/power/canonical/parameters/power_fuel_quality.csv",
    "data/sectors/power/canonical/parameters/power_params.csv",
    "data/sectors/power/parameters/power_coal_blend_by_year.csv",
    "data/sectors/power/parameters/power_fuel_quality.csv",
    "data/sectors/power/parameters/power_params.csv",
    "data/sectors/railways/activity/fuel_consumption.csv",
    "data/sectors/railways/activity/fuel_detail.csv",
    "data/sectors/railways/canonical/activity/fuel_consumption.csv",
    "data/sectors/railways/canonical/activity/fuel_detail.csv",
    "data/sectors/railways/canonical/parameters/railways_params.csv",
    "data/sectors/railways/parameters/railways_params.csv",
    "data/sectors/residential/activity/fuel_supply.csv",
    "data/sectors/residential/activity/fuel_supply_history.csv",
    "data/sectors/residential/activity/hies/hies_national_totals.csv",
    "data/sectors/residential/activity/woodfuel.csv",
    "data/sectors/residential/canonical/activity/fuel_supply.csv",
    "data/sectors/residential/canonical/activity/fuel_supply_history.csv",
    "data/sectors/residential/canonical/activity/hies/hies_national_totals.csv",
    "data/sectors/residential/canonical/activity/woodfuel.csv",
    "data/sectors/residential/canonical/parameters/residential_params.csv",
    "data/sectors/residential/parameters/residential_params.csv",
    "data/sectors/transport/activity/cng_gas.csv",
    "data/sectors/transport/activity/emission_factors_gkm.csv",
    "data/sectors/transport/activity/fuel_split.csv",
    "data/sectors/transport/activity/ocac_sectoral_annual.csv",
    "data/sectors/transport/activity/vehicles_district.csv",
    "data/sectors/transport/activity/vkt.csv",
    "data/sectors/transport/canonical/activity/cng_gas.csv",
    "data/sectors/transport/canonical/activity/emission_factors_gkm.csv",
    "data/sectors/transport/canonical/activity/fuel_split.csv",
    "data/sectors/transport/canonical/activity/ocac_sectoral_annual.csv",
    "data/sectors/transport/canonical/activity/vehicles_district.csv",
    "data/sectors/transport/canonical/activity/vkt.csv",
    "data/sectors/transport/canonical/parameters/transport_params.csv",
    "data/sectors/transport/parameters/transport_params.csv",
    "data/sectors/waste/activity/hies_disposal_routes.csv",
    "data/sectors/waste/activity/population_district.csv",
    "data/sectors/waste/activity/wastewater/protein.csv",
    "data/sectors/waste/activity/wastewater/sanitation_shares.csv",
    "data/sectors/waste/canonical/activity/hies_disposal_routes.csv",
    "data/sectors/waste/canonical/activity/population_district.csv",
    "data/sectors/waste/canonical/activity/wastewater/protein.csv",
    "data/sectors/waste/canonical/activity/wastewater/sanitation_shares.csv",
    "data/sectors/waste/canonical/parameters/waste_params.csv",
    "data/sectors/waste/parameters/waste_params.csv",
    "data/shared/activity/monthly/pbs_qim_month_item.csv",
    "data/shared/activity/nfdc/afr2025_fertilizer_gas_by_plant.csv",
    "data/shared/activity/nfdc/afr2025_fertilizer_gas_monthly.csv",
    "data/shared/activity/nfdc/afr2025_offtake_by_product.csv",
    "data/shared/activity/nfdc/afr2025_production_by_manufacturer.csv",
    "data/shared/activity/nfdc/annex5_national_month_product.csv",
    "data/shared/activity/nfdc/nfdc_production_by_product_series.csv",
    "data/shared/canonical/activity/monthly/pbs_qim_month_item.csv",
    "data/shared/canonical/activity/nfdc/afr2025_fertilizer_gas_by_plant.csv",
    "data/shared/canonical/activity/nfdc/afr2025_fertilizer_gas_monthly.csv",
    "data/shared/canonical/activity/nfdc/afr2025_offtake_by_product.csv",
    "data/shared/canonical/activity/nfdc/afr2025_production_by_manufacturer.csv",
    "data/shared/canonical/activity/nfdc/annex5_national_month_product.csv",
    "data/shared/canonical/activity/nfdc/nfdc_production_by_product_series.csv",
    "data/shared/canonical/parameters/coal_booking_policy.csv",
    "data/shared/canonical/parameters/emission_factors.csv",
    "data/shared/metadata/dependency_group_rules.csv",
    "data/shared/metadata/member_bindings.csv",
    "data/shared/parameters/coal_booking_policy.csv",
    "data/shared/parameters/emission_factors.csv",
    "data/shared/parameters/parameter_scope.csv",
    "data/shared/parameters/parameter_scope_exclusions.csv",
    "data/shared/parameters/uncertainty_reconciliation.csv",
    "outputs/agriculture_uncertainty_inputs_2024.csv",
    "outputs/fugitives_uncertainty_inputs_2024.csv",
    "outputs/pakemis_national_series.csv",
    "outputs/waste_uncertainty_inputs_2024.csv",
    "glob:outputs/*uncertainty_inputs*",
)
AIR_UNCERTAINTY_READS = (
    "data/catalog/assets.csv",
    "data/catalog/canonical.json",
    "data/catalog/canonical_tables.csv",
    "data/sectors/agriculture/activity/crops_2024.csv",
    "data/sectors/agriculture/activity/es_fiscal_series.csv",
    "data/sectors/agriculture/activity/fertilizer_2024.csv",
    "data/sectors/agriculture/activity/historical/crops.csv",
    "data/sectors/agriculture/activity/historical/fertilizer_n.csv",
    "data/sectors/agriculture/activity/historical/livestock_stocks.csv",
    "data/sectors/agriculture/activity/livestock_2024.csv",
    "data/sectors/agriculture/canonical/activity/crops_2024.csv",
    "data/sectors/agriculture/canonical/activity/es_fiscal_series.csv",
    "data/sectors/agriculture/canonical/activity/fertilizer_2024.csv",
    "data/sectors/agriculture/canonical/activity/historical/crops.csv",
    "data/sectors/agriculture/canonical/activity/historical/fertilizer_n.csv",
    "data/sectors/agriculture/canonical/activity/historical/livestock_stocks.csv",
    "data/sectors/agriculture/canonical/activity/livestock_2024.csv",
    "data/sectors/agriculture/canonical/parameters/burning_params.csv",
    "data/sectors/agriculture/canonical/parameters/mms_shares.csv",
    "data/sectors/agriculture/canonical/parameters/parameters.csv",
    "data/sectors/agriculture/canonical/parameters/residue_params.csv",
    "data/sectors/agriculture/parameters/burning_params.csv",
    "data/sectors/agriculture/parameters/mms_shares.csv",
    "data/sectors/agriculture/parameters/parameters.csv",
    "data/sectors/agriculture/parameters/residue_params.csv",
    "data/sectors/fugitives/activity/anchor_activity_2021_23.csv",
    "data/sectors/fugitives/activity/anchor_activity_2023_24.csv",
    "data/sectors/fugitives/activity/fertilizer_gas_class.csv",
    "data/sectors/fugitives/activity/gas_flow_controls_2021_24.csv",
    "data/sectors/fugitives/activity/gas_network.csv",
    "data/sectors/fugitives/activity/infrastructure_2023_24.csv",
    "data/sectors/fugitives/activity/infrastructure_history_2015_21.csv",
    "data/sectors/fugitives/activity/production.csv",
    "data/sectors/fugitives/activity/production_province.csv",
    "data/sectors/fugitives/activity/provincial_controls_2023_24.csv",
    "data/sectors/fugitives/canonical/activity/anchor_activity_2021_23.csv",
    "data/sectors/fugitives/canonical/activity/anchor_activity_2023_24.csv",
    "data/sectors/fugitives/canonical/activity/gas_flow_controls_2021_24.csv",
    "data/sectors/fugitives/canonical/activity/gas_network.csv",
    "data/sectors/fugitives/canonical/activity/infrastructure_2023_24.csv",
    "data/sectors/fugitives/canonical/activity/infrastructure_history_2015_21.csv",
    "data/sectors/fugitives/canonical/activity/production.csv",
    "data/sectors/fugitives/canonical/activity/production_province.csv",
    "data/sectors/fugitives/canonical/activity/provincial_controls_2023_24.csv",
    "data/sectors/fugitives/canonical/parameters/fugitives_ipcc2019_factors.csv",
    "data/sectors/fugitives/canonical/parameters/fugitives_params.csv",
    "data/sectors/fugitives/parameters/fugitives_ipcc2019_factors.csv",
    "data/sectors/fugitives/parameters/fugitives_params.csv",
    "data/sectors/residential/activity/fuel_supply.csv",
    "data/sectors/residential/activity/woodfuel.csv",
    "data/sectors/residential/canonical/activity/fuel_supply.csv",
    "data/sectors/residential/canonical/activity/woodfuel.csv",
    "data/sectors/residential/canonical/parameters/residential_params.csv",
    "data/sectors/residential/parameters/residential_params.csv",
    "data/sectors/waste/activity/hies_disposal_routes.csv",
    "data/sectors/waste/activity/population_district.csv",
    "data/sectors/waste/activity/wastewater/protein.csv",
    "data/sectors/waste/activity/wastewater/sanitation_shares.csv",
    "data/sectors/waste/canonical/activity/hies_disposal_routes.csv",
    "data/sectors/waste/canonical/activity/population_district.csv",
    "data/sectors/waste/canonical/activity/wastewater/protein.csv",
    "data/sectors/waste/canonical/activity/wastewater/sanitation_shares.csv",
    "data/sectors/waste/canonical/parameters/waste_params.csv",
    "data/sectors/waste/parameters/waste_params.csv",
    "data/shared/activity/nfdc/afr2025_fertilizer_gas_monthly.csv",
    "data/shared/activity/nfdc/annex5_national_month_product.csv",
    "data/shared/canonical/activity/nfdc/afr2025_fertilizer_gas_monthly.csv",
    "data/shared/canonical/activity/nfdc/annex5_national_month_product.csv",
    "data/shared/canonical/parameters/emission_factors.csv",
    "data/shared/parameters/emission_factors.csv",
    "outputs/pakemis_air_atomic_annual.csv",
)

PHASES = [
    # rc41: the ADM2 reporting-unit registry and crosswalk were a hand-run script. They are
    # deterministic (the script rewrites only what differs, so a rerun is byte-identical)
    # and read only data/, so they run first - every district product downstream reads them.
    Phase("ADM2 reporting units", "scripts/build_adm2_package.py", True,
          writes=("outputs/pakemis_adm2_crosswalk.csv", "data/adm2_canonical.csv",
                  "data/adm2_crosswalk.csv"),
          reads=("data/gis/PAK_ADM2.geojson", "data/activity/waste/population_district.csv",
                 "data/activity/livestock_district_2024.csv",
                 "data/activity/transport/vehicles_district.csv"),
          idempotent=True),
    # ---- the ten sectors ----
    Phase("Agriculture", "pkinv.sectors.agriculture.run_inventory", True,
          writes=("outputs/national_totals_2024.csv",
                  "outputs/agriculture_livestock_reconciliation_2024.csv",
                  "outputs/agriculture_fertiliser_composition_2024.csv",
                  "outputs/agriculture_crop_residue_ledger_2024.csv",
                  # rc64: declared when the table entered the shipped set. The runner
                  # wrote it all along and the Phase named four of its outputs, not five.
                  "outputs/agriculture_monthly_2024.csv",)),
    # MOVED HERE IN rc39, from after the whole cross-sector layer. The 1990-2024 series
    # was declared as an OUTPUT of the fiscal history below and as no output at all of
    # this phase, and both declarations were false: fiscal_series only opens the file to
    # read it, and this module is its sole writer. check_order() therefore believed the
    # series was produced at the top of the build and consumed after, when the truth was
    # the reverse - so the fiscal backcast, key categories and the national series had
    # all along been reading the PREVIOUS run's series. Invisible while the reference
    # year did not move; the moment rc39 re-based the herd it surfaced as a 0.1847 Mt
    # splice against agriculture's own anchor. It reads only the FAOSTAT history files
    # and computes the engine in process, so it has no build-internal input and belongs
    # with the sector that produces it.
    Phase("Agriculture timeseries (1990-2024)", "pkinv.sectors.agriculture.timeseries", True,
          writes=("outputs/timeseries_1990_2024.csv",
                  "outputs/timeseries_validation.csv",
                  "outputs/crt_AFOLU_table.csv",)),
    # The fiscal history, and the price of having moved it there. Runs with the sector
    # rather than with the cross-sector layer because national_series computes it in
    # process: these files are the published record of a reconstruction the series does
    # not read back, which is what keeps them from becoming a second vintage of it.
    Phase("Agriculture fiscal history", "pkinv.sectors.agriculture.fiscal_series", True,
          writes=("outputs/pakemis_agriculture_fiscal_series.csv",
                  "outputs/pakemis_agriculture_basis_change.csv",
                  "outputs/pakemis_agriculture_crop_calendar.csv",
                  "outputs/agriculture_urea_basis.csv",),
          reads=("outputs/timeseries_1990_2024.csv",)),
    # THE LANE THAT LEFT THE BUILD (rc36). The docstring above called these
    # "agriculture research, hand-run"; the byte audit found that
    # uncertainty_montecarlo.csv is read by twelve national modules and
    # key_categories.csv by three manuscripts, while nothing in make all wrote
    # either - the product_catalog class again, at the inventory's core.
    Phase("Agriculture Monte Carlo", "pkinv.sectors.agriculture.montecarlo", True,
          writes=("outputs/uncertainty_montecarlo.csv",
                  "outputs/uncertainty_distribution.png",),
          reads=("outputs/national_totals_2024.csv",)),
    Phase("Agriculture key categories", "pkinv.sectors.agriculture.key_categories", True,
          writes=("outputs/key_categories.csv", "outputs/key_categories_report.md",),
          # rc39: the 1990-2024 series added - the third consumer, now declared so
          # check_order() holds the ordering it depends on.
          reads=("outputs/national_totals_2024.csv", "outputs/timeseries_1990_2024.csv",)),
    Phase("Agriculture nitrogen ledger", "pkinv.sectors.agriculture.n_ledger", True,
          writes=("outputs/n_ledger_2024.csv", "outputs/n_ledger_2024.md",
                  "outputs/n_ledger_stage_comparison.csv",
                  "outputs/agriculture_n_ledger_qa_2024.csv",),
          reads=("outputs/national_totals_2024.csv",)),
    Phase("LULUCF (exploratory, outside every total)", "pkinv.lulucf.run_lulucf", False,
          writes=("outputs/lulucf_totals.csv", "outputs/afolu_summary.csv",
                  "outputs/lulucf_report.md",),
          reads=("outputs/national_totals_2024.csv",)),
    Phase("Agriculture provincial", "pkinv.sectors.agriculture.downscale", True,
          writes=("outputs/provincial_totals_2024.csv",)),
    Phase("Agriculture districts", "pkinv.sectors.agriculture.gis.district_downscale", True,
          writes=("outputs/district_totals_2024.csv",)),
    # WIRED IN rc39, the product_catalog class again (rc41): the district x year panel
    # is committed, is asserted by tests/test_district_annual.py, and was in NO build
    # definition - so it held the reference year's 2024 slice from whenever someone last
    # ran it by hand. The re-based herd made that visible as a written panel 0.19 Mt below
    # the national control it claims to reconcile to. It costs 0.7 s.
    Phase("Agriculture district panel (1990-2024)",
          "pkinv.sectors.agriculture.gis.district_annual", True,
          writes=("outputs/districts/district_totals_by_year.csv",),
          reads=("outputs/district_totals_2024.csv",
                 "outputs/timeseries_1990_2024.csv",)),
    Phase("Agriculture air pollutants", "pkinv.sectors.agriculture.air_pollutants", False,
          # The current implementation reads held history only; acquisition lives in
          # fetch_history.py. Keeping the historical network flag skipped live products.
          writes=("outputs/air_pollutants_2024.csv",
                  "outputs/air_pollutants_provincial_2024.csv")),
    # The air-pollutant research layers, after the air layer they read.
    Phase("Agriculture air key categories", "pkinv.sectors.agriculture.air_key_categories", False,
          writes=("outputs/air_key_categories.csv", "outputs/air_key_categories.md",),
          reads=("outputs/air_pollutants_2024.csv",)),
    Phase("Agriculture air uncertainty", "pkinv.sectors.agriculture.air_uncertainty", False,
          writes=("outputs/air_uncertainty_montecarlo.csv",
                  "outputs/air_uncertainty_distribution.png",),
          reads=("outputs/air_pollutants_2024.csv",)),
    Phase("Agriculture air time series", "pkinv.sectors.agriculture.air_timeseries", False,
          writes=("outputs/air_pollutants_timeseries_1990_2024.csv",
                  "outputs/air_trend_chart.png",),
          reads=("outputs/air_pollutants_2024.csv",)),
    Phase("Waste", "pkinv.sectors.waste.run_waste", False,
          writes=("outputs/waste_totals_2024.csv",
                  "outputs/waste_air_pollutants_2024.csv",
                  # declared because the activity publication reads it: the modelled fate ledger
                  "outputs/waste_ledger_2024.csv",
                  # cycle 37: declared when these entered the shipped set. run_waste writes
                  # the stream split and the provincial table itself; the runner names them
                  # with a %d year format, so no literal grep for the path ever found them.
                  "outputs/waste_by_stream_2024.csv",
                  "outputs/waste_provincial_2024.csv",
                  # cycle 40: monthly.main() at line 134
                  "outputs/waste_monthly_2024.csv",)),
    Phase("Waste air pollutants", "pkinv.sectors.waste.air_pollutants", False,
          writes=("outputs/waste_air_pollutants_2024.csv",), prints_only=True),
    # rc41: the sector's own uncertainty stage (approach 1, the inputs register and the
    # structural scenarios) was a Makefile step that no run_all phase ran - the national
    # rollup reads waste_uncertainty_scenarios_2024.csv, and the strict empty-outputs
    # The summary consumes the same 10,000-draw prefix of the national pool.
    Phase("Waste MC draw file", "pkinv.sectors.waste.uncertainty draws", True,
          writes=("outputs/mc_draws/waste_parameter_rerun.csv",
                  "outputs/mc_draws/waste_parameter_rerun.meta.json")),
    # rc67: the ALTERNATIVE wastewater nitrous-oxide method (the 2006 equation, the reference
    # through rc66) on the reference draw file's own streams. Injected nowhere and in no
    # total; pakemis_wastewater_method_comparison.csv differences it against the ensemble.
    Phase("Waste MC alternative draw file", "pkinv.sectors.waste.uncertainty alternative-draws",
          True,
          writes=("outputs/mc_draws/waste_parameter_rerun_ipcc2006.csv",
                  "outputs/mc_draws/waste_parameter_rerun_ipcc2006.meta.json")),
    Phase("Waste uncertainty", "pkinv.sectors.waste.uncertainty", False,
          writes=("outputs/waste_uncertainty_2024.csv",
                  "outputs/waste_uncertainty_inputs_2024.csv",
                  "outputs/waste_uncertainty_scenarios_2024.csv",
                  "outputs/waste_parameter_mc_2024.csv"),
          reads=("outputs/mc_draws/waste_parameter_rerun.csv",
                 "outputs/mc_draws/waste_parameter_rerun.meta.json")),
    Phase("Road transport", "pkinv.sectors.transport.run_transport", False,
          writes=("outputs/transport_totals_2024.csv",
                  "outputs/transport_fuel_ledger_2024.csv",
                  "outputs/transport_air_pollutants_2024.csv",
                  # rc64: declared when the file entered the shipped set. The runner wrote
                  # it all along; the Phase named two of its outputs and not this one, which
                  # is invisible until a product registry asks who writes it.
                  "outputs/transport_provincial_proxy_comparison_2024.csv",
                  # cycle 36, the same omission one round later: the runner writes these two
                  # with a %d year format, so nothing that greps for a literal path found
                  # them and the product registry called them orphans the moment they
                  # entered the shipped set.
                  "outputs/transport_cng_2024.csv",
                  "outputs/transport_cng_crosscheck_2024.csv",
                  # cycle 37, same reason: the runner writes the split and calls
                  # uncertainty.main() (line 306) and monthly.main() (line 309)
                  "outputs/transport_by_stream_2024.csv",
                  "outputs/transport_provincial_2024.csv",
                  "outputs/transport_uncertainty_2024.csv",
                  # cycle 40: monthly.main() at line 309, declared with the rest
                  "outputs/transport_monthly_2024.csv",),
          reads=()),
    # rc41: the provincial shape bracket (the borrowed-shape ends, FY2021-22 and FY2024-25)
    # was a hand-run module - not in the Makefile, not a phase - and the spatial-allocation
    # brackets read its table; the strict rebuild stopped there. It reads the OCAC
    # provincial panel under data/activity only.
    Phase("Transport provincial shape", "pkinv.sectors.transport.province_shape", False,
          writes=("outputs/transport_provincial_shape_brackets.csv",),
          reads=("data/activity/transport/ocac_sectoral_provincial.csv",)),
    Phase("Transport air pollutants", "pkinv.sectors.transport.air_pollutants", False,
          writes=("outputs/transport_air_pollutants_2024.csv",), prints_only=True),
    Phase("Power generation", "pkinv.sectors.power.run_power", False,
          writes=("outputs/power_totals_fy2023_24.csv",
                  # rc64: declared when the adjudication entered the shipped set. The
                  # runner calls it between the implied-CV diagnostic it reads and the
                  # hypotheses register that reads it.
                  "outputs/pakemis_power_coal_energy_adjudication.csv",
                  # cycle 37, same reason: run_power writes both of these
                  "outputs/power_by_stream_fy2023_24.csv",
                  "outputs/power_provincial_fy2023_24.csv",
                  # cycle 40: run_power calls monthly.main() at line 530 and writes the
                  # sector interval; both carry the fy2023_24 suffix built from the year
                  "outputs/power_monthly_fy2023_24.csv",
                  "outputs/power_uncertainty_fy2023_24.csv",
                  # 2026-10-06: run_power writes the implied-CV diagnostic too (implied_cv.py
                  # via run_power line ~412) and never declared it, so the build graph had a
                  # file three later phases read and nothing wrote. The coal-configurations
                  # phase declared it as a read and the order checker found the hole.
                  "outputs/power_implied_coal_cv_fy2023_24.csv",
                  # rc68: and the Table 3 hypotheses register (run_power line ~503). It
                  # had been registered as a hand-run held product on the belief that no
                  # phase wrote it; the clean rebuild found this phase rewriting it.
                  "outputs/power_table3_hypotheses.csv",),
          reads=()),
    Phase("Power air pollutants", "pkinv.sectors.power.air_pollutants", False,
          writes=("outputs/power_air_pollutants_fy2023_24.csv",)),
    # Which basis is closer to the one emissions actually follow, measured in the single
    # fiscal year both bases cover. This is the evidence for re-basing furnace oil and not
    # gas, published so the decision can be re-examined rather than re-argued.
    Phase("Power grid basis change", "pkinv.sectors.power.generation_panel", True,
          writes=("outputs/pakemis_power_grid_basis_change.csv",),
          reads=()),
    Phase("Residential fuel", "pkinv.sectors.residential.run_residential", False,
          writes=("outputs/residential_totals_2024.csv",
                  "outputs/residential_air_pollutants_2024.csv",
                  "outputs/residential_district_2024.csv",
                  "outputs/residential_configurations_2024.csv",
                  "outputs/residential_configurations_by_year.csv",
                  # UNDER-DECLARED until the dung-balance phase read them. run_residential
                  # writes both - dung_ledger.write() at line 126 and the HIES comparison at
                  # line 143 - and neither was listed, so from the scheduler's view no phase
                  # produced them and any later phase declaring a read of them was a rule-1
                  # violation. Two files produced by this phase and owned by nothing.
                  "outputs/residential_dung_ledger_2024.csv",
                  "outputs/residential_hies_comparison_2024.csv",
                  # cycle 37, same reason: run_residential calls uncertainty.main() (line
                  # 198) and monthly (line 206), and writes the stream and provincial tables
                  "outputs/residential_by_stream_2024.csv",
                  "outputs/residential_provincial_2024.csv",
                  "outputs/residential_uncertainty_2024.csv",
                  "outputs/residential_monthly_2024.csv",
                  "outputs/residential_emissions_monthly_2024.csv",)),
    Phase("Residential air pollutants", "pkinv.sectors.residential.air_pollutants", False,
          writes=("outputs/residential_air_pollutants_2024.csv",), prints_only=True),
    Phase("Industrial processes", "pkinv.sectors.ippu.run_ippu", False,
          writes=("outputs/ippu_totals_2024.csv",
                  "outputs/ippu_urea_co2_bridge_2025.csv",
                  "outputs/ippu_chemicals_screening_2024.csv",
                  # cycle 38, same reason: run_ippu writes these three and calls
                  # monthly.main() at line 558
                  "outputs/ippu_by_stream_2024.csv",
                  "outputs/ippu_provincial_2024.csv",
                  "outputs/ippu_fertilizer_gas_monthly_2024.csv",
                  "outputs/ippu_monthly_2024.csv",
                  "build/ippu/numerical_context.json", "build/ippu/numerical_qa_2024.csv"),
          reads=()),
    Phase("IPPU metadata", "pkinv.sectors.ippu.metadata", False,
          writes=("outputs/ippu_completeness_2024.csv", "outputs/ippu_evidence_maturity.csv",
                  "outputs/ippu_data_acquisition_requests.csv", "outputs/ippu_hfc_inventory_import_contract.csv",
                  "outputs/ippu_data_request_packets.csv", "outputs/ippu_source_manifest.csv",
                  "outputs/ippu_qa_2024.csv", "outputs/ippu_run_manifest_2024.json"),
          reads=("build/ippu/numerical_context.json", "build/ippu/numerical_qa_2024.csv",
                 "data/activity/ippu/master_data_gap_matrix.csv", "data/activity/ippu/evidence_maturity.csv",
                 "data/activity/ippu/hfc_inventory_import_contract.csv", "data/activity/ippu/data_request_packets.csv",
                 "data/activity/ippu/source_manifest.csv")),
    Phase("Industrial combustion", "pkinv.sectors.industry.run_industry", False,
          writes=("outputs/industry_totals_2024.csv",
                  "outputs/industry_solid_screenings_2024.csv",
                  "outputs/industry_captive_screening_2024.csv",
                  # cycle 39, same reason: run_industry writes the stream and provincial
                  # tables and calls monthly.main() at line 218
                  "outputs/industry_by_stream_2024.csv",
                  "outputs/industry_provincial_2024.csv",
                  "outputs/industry_monthly_2024.csv")),
    # rc46 Wave 4: the species-resolved HFC bank over the committed import-contract rows.
    # The ippu phase's screening file quotes the same total, computed LIVE by the same
    # module (fgas_screening._species_bank_latest calls hfc_bank.build in-memory), so the
    # two cannot disagree whatever order the phases run in; this phase materializes the
    # per-stratum product.
    Phase("HFC species bank", "pkinv.sectors.ippu.hfc_bank", False,
          writes=("outputs/ippu_hfc_species_bank.csv",),
          reads=("data/activity/ippu/hfc_inventory_rows.csv",)),
    # rc46 Wave 2: the two power-coal lanes reconciled per year, the unmatched tonnage
    # typed and never spread; reads two committed inputs and must follow neither engine.
    Phase("Coal lane reconciliation", "scripts.build_coal_reconciliation", False,
          writes=("outputs/industry_coal_reconciliation.csv",),
          reads=("data/activity/industry/coal_by_consumer.csv",
                 "data/activity/power/plant_fuel_ledger.csv",)),
    # rc47 Wave 1: the reference-year crop split measured proxy-vs-panel, the record
    # of what putting FY2023-24 on the PBS panel changed; runs after the district
    # product it reads.
    Phase("Agri reference-panel divergence", "scripts.build_agri_panel_divergence",
          False,
          writes=("outputs/agri_reference_panel_divergence.csv",),
          reads=("data/activity/agriculture/crop_district_panel.csv",
                 "outputs/district_totals_2024.csv",)),
    # rc47 Wave 6: the frame settlement's two products. The crosswalk prepares the
    # v1.1 re-rasterisation without re-keying anything; the 0.1-degree grid is the
    # EDGAR-aligned derived aggregation with its conservation identity asserted.
    Phase("ADM2 frame 2022 crosswalk", "scripts.build_adm2_frame_2022", False,
          writes=("outputs/pakemis_adm2_frame_2022.csv",),
          reads=("data/adm2_canonical.csv",
                 "data/gis/cod_ab/pak_admin2.geojson",)),
    Phase("Fugitive oil and gas", "pkinv.sectors.fugitives.run_fugitives", False,
          writes=("outputs/fugitives_totals_2024.csv",
                  "outputs/fugitives_post_meter_end_use_2024.csv",
                  "outputs/fugitives_structural_factorial_2024.csv",
                  "outputs/fugitives_conditional_intervals_2024.csv",
                  # rc36: the seven products the fugitives paper cites were written
                  # in-process but undeclared here, so their freshness was unguarded
                  "outputs/fugitives_qa_2024.csv",
                  "outputs/fugitives_uncertainty_inputs_2024.csv",
                  "outputs/fugitives_unfccc_crt_reproduction.csv",
                  "outputs/fugitives_unfccc_crt_cell_audit.csv",
                  "outputs/fugitives_unfccc_crt_waterfall_2022.csv",
                  "outputs/fugitives_observation_match_audit_2024.csv",
                  "outputs/fugitives_run_manifest_2024.json",
                  # cycle 38: the headline family, declared when it entered the shipped set.
                  # run_fugitives writes these five and calls monthly.main() at line 528;
                  # each is named with a %d year format, so no literal grep found them.
                  "outputs/fugitives_by_stream_2024.csv",
                  "outputs/fugitives_completeness_2024.csv",
                  "outputs/fugitives_provincial_2024.csv",
                  "outputs/fugitives_uncertainty_2024.csv",
                  "outputs/fugitives_observation_provincial_evaluation_2024.csv",
                  "outputs/fugitives_monthly_2024.csv",)),
    Phase("Railways", "pkinv.sectors.railways.run_railways", False,
          writes=("outputs/railways_totals_2024.csv",
                  # written in-process by the runner AND by the phase below (rc41: declared
                  # here so the runner's manifest lists what the runner wrote)
                  "outputs/railways_air_pollutants_2024.csv",
                  # cycle 37, same reason: run_railways calls uncertainty.main and
                  # monthly.main in its own phase list (lines 260-263)
                  "outputs/railways_by_stream_2024.csv",
                  "outputs/railways_provincial_2024.csv",
                  "outputs/railways_uncertainty_2024.csv",
                  "outputs/railways_monthly_2024.csv")),
    # The one air-pollutant layer that had NO phase (every other sector's
    # does): run_railways already executes it in-process, so the file was
    # regenerating - but nothing checked that THIS run wrote it, and its
    # consumers (figures, the paper claims) would have read a stale file
    # silently. rc41: the runner declares the table it writes in-process, so
    # this phase is the same prints-only freshness declaration as the other
    # sectors' air layers (one producer per artefact; the module still
    # rewrites identical bytes when run).
    Phase("Railways air pollutants", "pkinv.sectors.railways.air_pollutants", False,
          writes=("outputs/railways_air_pollutants_2024.csv",), prints_only=True),
    Phase("Railways ELK crosscheck", "pkinv.sectors.railways.gis.elk_crosscheck", False,
          writes=("outputs/railways_elk_crosscheck_2024.csv",)),
    # The fallback anchor's own QA table was the guard file's opening story: a
    # producer that never ran in the build, so its table could go stale for
    # releases. It runs here now (reads only committed data/activity files;
    # the controls ingest stays a Makefile step). rc41: it runs BEFORE the
    # aviation runner, which prices the ladder configuration from this study's
    # aviation_model_resolution_fy2023_24.csv - the strict empty-outputs rebuild
    # stopped on that read while the study still ran after the runner (every
    # earlier build had priced it from the previous release's ladder).
    Phase("Aviation fallback study", "pkinv.sectors.aviation.run_fallback", False,
          requires=("openap",),
          writes=("outputs/aviation_fallback_qa_fy2023_24.csv",
                  "outputs/aviation_model_resolution_fy2023_24.csv",
                  "outputs/aviation_route_ledger_fy2023_24.csv",
                  "outputs/aviation_aircraft_ledger_fy2023_24.csv",
                  "outputs/aviation_resident_international_ledger_fy2023_24.csv",
                  "outputs/aviation_openap_lookup_fy2023_24.csv"),
          reads=()),
    # rc37: the reconciliation study was `make aviation-study` only, so the five
    # validation-catalog rows it produces (the OECD gross-boundary closure, the 21
    # hash-pinned CRT cells, the Climate TRACE month and airport comparisons, the
    # departures calibration) were `fresh = exempt` - the configuration that left
    # the IPPU QA table stale for four releases. It is a gated phase now.
    Phase("Aviation reconciliation study",
          "pkinv.sectors.aviation.run_reconciliation_study", False,
          writes=("outputs/aviation_reconciliation_qa.csv",
                  "outputs/aviation_ocac_oecd_annual_comparison.csv",
                  "outputs/aviation_unfccc_crt_cell_audit.csv",
                  "outputs/aviation_climatetrace_national_monthly.csv",
                  "outputs/aviation_climatetrace_airport_comparison.csv",
                  "outputs/aviation_departure_control_comparison.csv",
                  "outputs/aviation_ocac_monthly.csv",),
          reads=("outputs/aviation_aircraft_ledger_fy2023_24.csv",
                 "outputs/aviation_openap_lookup_fy2023_24.csv")),

    # rc41: the runner's monthly layer reads aviation_ocac_monthly.csv, a product of the
    # reconciliation study, so the runner follows BOTH aviation studies now.
    Phase("Aviation", "pkinv.sectors.aviation.run_aviation", False,
          writes=("outputs/aviation_totals_fy2023_24.csv",
                  "outputs/aviation_air_pollutants_fy2023_24.csv",
                  # cycle 39: the headline family, declared when it entered the shipped set.
                  # run_aviation writes four of these and calls monthly_layer.main() at line
                  # 350; the fy2023_24 suffix is built from the year, so no literal grep found
                  # them and the product registry would have called each one an orphan.
                  "outputs/aviation_by_stream_fy2023_24.csv",
                  "outputs/aviation_fuel_constrained_by_stream_fy2023_24.csv",
                  "outputs/aviation_provincial_fy2023_24.csv",
                  "outputs/aviation_completeness_fy2023_24.csv",
                  "outputs/aviation_monthly_fy2023_24.csv",),
          reads=("outputs/aviation_model_resolution_fy2023_24.csv",)),
    Phase("Aviation air pollutants", "pkinv.sectors.aviation.air_pollutants", False,
          writes=("outputs/aviation_air_pollutants_fy2023_24.csv",), prints_only=True),

    # ---- the cross-sector layer: everything that belongs to no single sector ----
    # rc41: the completeness matrix reads the sector engines and data/data_gaps.csv only,
    # and the national rollup reads it (its EDGAR scope coverage takes the notation keys
    # from it) - so it runs BEFORE the rollup. It ran six phases after, and every build
    # had handed the rollup the previous run's matrix; the strict rebuild stopped here.
    Phase("Completeness table", "pkinv.report.completeness", True,
          writes=("outputs/completeness.csv",)),
    Phase("National rollup", "pkinv.report.national_rollup", True,
          writes=("outputs/national_all_sectors.csv",
                  "outputs/national_all_sectors_ledger.csv",
                  "outputs/national_benchmark_comparison.csv",
                  # UNDECLARED UNTIL 2026-10-07. This phase writes the structural bridge
                  # (national_rollup.py:539) and two phases read it - priority_rankings
                  # and the effluent tail diagnostic - so until it was declared here no
                  # ordering constraint existed between the writer and either reader, and
                  # check_order could not see the read at all.
                  "outputs/national_structural_bridge.csv",)),
    Phase("National key categories", "pkinv.report.key_categories_all", True,
          writes=("outputs/national_key_categories.csv",),
          reads=("outputs/national_all_sectors.csv",)),
    # The injected-engine draw stages (rc12): each native sector engine persists its
    # 100,000 seeded draws BEFORE the national pool consumes them. Waste's rebuild
    # loop costs ~4-5 minutes; both are deterministic, so an unchanged sector
    # rewrites byte-identical files.
    Phase("Fugitives MC draw file", "pkinv.sectors.fugitives.uncertainty draws", True,
          writes=("outputs/mc_draws/fugitives_bounded.csv",
                  "outputs/mc_draws/fugitives_bounded.meta.json")),
    # Before the national pool: the registry globs outputs/*uncertainty_inputs*
    # and agriculture's factor parameters (rc18) must exist when it does.
    Phase("Agriculture uncertainty inputs", "pkinv.sectors.agriculture.uncertainty_inputs", True,
          writes=("outputs/agriculture_uncertainty_inputs_2024.csv",)),
    Phase("National uncertainty", "pkinv.report.uncertainty_all", True,
          writes=("outputs/national_uncertainty_montecarlo.csv",
                  "outputs/national_uncertainty_sources.csv"),
          reads=("glob:outputs/*uncertainty_inputs*",)),
    # These four were in the Makefile's `national` target and not here, so `make all` and
    # `make national` produced different sets of outputs. Same list, one order, both places.
    Phase("National category ledger", "pkinv.report.category_ledger", True,
          writes=("outputs/national_category_gas.csv",)),
    Phase("Parameter decomposition", "pkinv.core.parameters", True,
          writes=("outputs/national_uncertainty_decomposition.csv",
                  "outputs/national_uncertainty_parameters.csv")),
    Phase("Priority rankings", "pkinv.report.priority_rankings", True,
          writes=("outputs/national_priority_rankings.csv",)),
    Phase("Dung destination variants", "pkinv.report.dung_variants", True,
          writes=("outputs/national_dung_variants.csv",)),
    # AFTER the variants, which it reads: the balance table prices no destination itself,
    # it reports the four the phase above already priced and adds the asymmetry audit.
    Phase("Dung balance", "pkinv.report.dung_balance", True,
          writes=("outputs/pakemis_dung_balance.csv",),
          reads=("outputs/national_dung_variants.csv",
                 "outputs/residential_dung_ledger_2024.csv",
                 "outputs/residential_hies_comparison_2024.csv",
                 "data/sectors/residential/parameters/residential_params.csv",)),
    # v3: the unresolved residual by species in nitrogen, volatile solids and cake, through
    # the engine's own chain; the species split is a declared assumption. COMPARATOR ONLY.
    Phase("Dung residual ledger", "pkinv.report.dung_residual_ledger", True,
          writes=("outputs/pakemis_dung_residual_ledger.csv",),
          reads=("outputs/residential_dung_ledger_2024.csv",
                 "data/activity/agriculture/livestock_2024.csv",
                 "data/sectors/agriculture/parameters/parameters.csv",
                 "data/sectors/agriculture/parameters/mms_shares.csv",
                 "data/sectors/residential/parameters/residential_params.csv",)),
    # rc41: the named configurations read commercial_scope_configuration_2024.csv (the
    # commercial audit) and national_gas_closure_variant.csv (the gas closure); both
    # ran AFTER this phase, so every build had priced two configurations from the
    # previous release's files. They read sector products and data/ only, so they
    # come first now.
    Phase("Commercial/institutional audit", "pkinv.report.commercial_audit", True,
          writes=("outputs/commercial_institutional_audit_2024.csv",)),
    Phase("National gas closure", "pkinv.report.gas_closure", True,
          # the variant is this module's second output (VARIANT_OUT), declared in cycle 36
          # when it entered the deposit; the configurations module READS it, and the phase
          # that writes a file is the one that must name it
          writes=("outputs/national_gas_closure.csv",
                  "outputs/national_gas_closure_variant.csv",)),
    Phase("Named national configurations", "pkinv.report.national_configurations", True,
          writes=("outputs/national_configurations.csv",)),
    Phase("Uncertainty reconciliation", "pkinv.report.uncertainty_reconciliation", True,
          writes=("outputs/national_uncertainty_reconciliation.csv",)),
    Phase("Kiln allocation benchmark", "pkinv.eval.benchmark_kiln_allocation", True,
          writes=("outputs/benchmark_kiln_allocation.csv",)),
    Phase("Kiln allocation product", "pkinv.report.kiln_allocation", True,
          writes=("outputs/pakemis_kiln_allocation_adm2.csv",)),
    Phase("Waste release objects", "pkinv.sectors.waste.gis.release_candidates", True,
          writes=("outputs/waste_release_assignment_2024.csv",)),
    Phase("GEM asset-census audit", "pkinv.report.gem_audit", True,
          writes=("outputs/power_gem_audit.csv",)),
    Phase("National axis register", "pkinv.report.national_axis_register", True,
          writes=("outputs/national_axis_register.csv",)),
    Phase("National series", "pkinv.report.national_series", True,
          writes=("outputs/pakemis_national_series.csv",
                  "outputs/pakemis_series_splice_agriculture.csv",
                  "outputs/pakemis_national_series_coverage.csv",),
          # rc39: it prices agriculture's basis splice against the 1990-2024 series, and
          # declared no reads at all - so the splice compared THIS run's engine with the
          # PREVIOUS run's series and read a genuine re-base as a method difference.
          reads=("outputs/timeseries_1990_2024.csv",)),
    # rc67: the diverted dung year by year - what the survey has households burning (the
    # reference), what is unresolved in mass and nitrogen, and the price of each candidate
    # destination. Agriculture is re-run per year for the manure and field destinations. It
    # reads the series' totals, so it runs after the series.
    Phase("Dung fate by year", "pkinv.report.dung_fate_by_year", True,
          writes=("outputs/pakemis_dung_fate_by_year.csv",),
          reads=("outputs/pakemis_national_series.csv",
                 "outputs/national_dung_variants.csv",
                 "data/scenario_variants.csv", "data/periods.csv",
                 "data/activity/residential/hies/hies_national_totals.csv",
                 "data/mms_shares.csv", "data/residential_params.csv")),
    Phase("Annual product (supported fiscal panel)", "pkinv.report.annual_product", True,
          writes=("outputs/pakemis_annual_fy2015_16_fy2024_25.csv",
                  "outputs/pakemis_annual_fy2015_16_fy2024_25.parquet"),
          # rc39: this read was NEVER DECLARED, so check_order could not see that the
          # phase writing it ran AFTERWARDS. The annual product recomputes each sector's
          # detail and closes it against the published series, so with a stale series it
          # was closing this run's detail against the PREVIOUS run's totals - invisible
          # while nothing moved, and a hard failure the moment the herd re-base did.
          reads=("outputs/pakemis_national_series.csv",)),
    # After the annual product and the configurations, because it reads both and turns
    # them into a denominator: every cell the completeness register takes a position on,
    # in every year, with a state rather than an absence.
    # The period registry the atomic table keys on, then the atom itself. Both run after
    # the annual product because they read the series it validates against.
    Phase("Period registry", "pkinv.report.periods", True,
          writes=("data/periods.csv",), reads=(), audited=True),
    Phase("Atomic annual table", "pkinv.report.atomic_annual", True,
          writes=("outputs/pakemis_atomic_annual.csv",
                  "outputs/pakemis_ghg_configuration_atoms.csv",
                  "outputs/pakemis_atomic_annual_aggregates.csv"),
          reads=("data/periods.csv",)),
    # Downstream of the atomic annual table because it needs a HISTORICAL year: the BTR's
    # inventory year is FY2020-21, and the national benchmark register's resolver can only
    # answer for the reference year (tests/test_national_rollup.py holds that line).
    # A screening over held inputs: the FAOSTAT extract under data/raw/land/ and the BTR
    # transcription. Offline, and nothing it writes enters a total.
    Phase("Forest flux adjudication", "scripts/build_forest_flux_adjudication.py", True,
          writes=("outputs/pakemis_forest_flux_adjudication.csv",),
          reads=("data/shared/evidence/btr1_national_inventory.csv",)),
    # Reads the minerals panel and calls the same profile server the sectors do, so its
    # verdicts describe the shape the engine actually serves rather than a re-derivation.
    Phase("Minerals panel screening", "scripts/build_minerals_panel_screening.py", True,
          writes=("outputs/pakemis_minerals_panel_screening.csv",),
          reads=("data/activity/monthly/pbs_minerals_month_province.csv",)),
    # Reads the source register and, for each row with no pointer there, the produced
    # table's own per-row source column - so its inputs are the whole ingest tree and
    # `reads` stays None rather than naming a fraction of it.
    Phase("Citation pointer audit", "scripts/build_citation_pointer_audit.py", True,
          writes=("outputs/pakemis_citation_pointer_audit.csv",)),
    # Re-runs the species bank in-process to price one stratum's leak rate against
    # IPCC Table 7.9, so its input is the bank's own activity table. Nothing it writes
    # enters a total - 2.F contributes zero.
    Phase("F-gas leak-rate adjudication",
          "scripts/build_fgas_leak_rate_adjudication.py", True,
          writes=("outputs/pakemis_fgas_leak_rate_adjudication.csv",),
          reads=("outputs/ippu_hfc_species_bank.csv",)),
    Phase("BTR comparison (year-matched)", "scripts/build_btr_comparison.py", True,
          writes=("outputs/pakemis_btr_comparison.csv",),
          reads=("outputs/pakemis_atomic_annual.csv",
                 "data/shared/evidence/btr1_national_inventory.csv")),
    Phase("Cement activity sources and their overlap", "pkinv.report.cement_activity_sources", True,
          writes=("outputs/pakemis_cement_activity_sources.csv",)),
    # Activity the inventory holds and cannot yet turn into emissions, and the modelled
    # years it declines to publish. Both exist so an NE cell is auditable rather than blank.
    Phase("Unallocated activity controls", "pkinv.report.unallocated_controls", True,
          writes=("outputs/pakemis_unallocated_activity_controls.csv",)),
    Phase("Bridge configurations (declared, unpopulated)", "pkinv.report.bridge_configurations", True,
          writes=("outputs/pakemis_bridge_configurations.csv",)),
    Phase("Coverage matrix (year x category x gas x configuration)", "pkinv.report.coverage_matrix", True,
          writes=("outputs/pakemis_coverage_matrix.csv",
                  "outputs/pakemis_coverage_summary.csv")),
    Phase("National monthly layer", "pkinv.report.monthly_all", True,
          writes=("outputs/national_monthly_2024.csv",
                  # the timing-evidence table the module writes beside the monthly layer
                  "outputs/temporal_profile.csv")),
    # rc41: the source-stream ledger reads the national monthly layer and the
    # spatial-allocation brackets read the ledger; both ran elsewhere (the brackets 30
    # phases BEFORE the ledger, priced from the previous release's ledger), so the two
    # follow the monthly layer now, in dependency order.
    Phase("Source-stream ledger", "pkinv.report.source_streams", True,
          writes=("outputs/pakemis_source_streams.csv",)),
    Phase("Spatial-allocation brackets", "pkinv.report.spatial_brackets", True,
          writes=("outputs/pakemis_spatial_brackets.csv",),
          reads=("outputs/pakemis_source_streams.csv",
                 "outputs/pakemis_adm2_stream_by_year.csv")),
    # The 108-month layer, in the order it depends on: the calendar, then the profiles that
    # key on it, then the product that multiplies the atomic table by them.
    # Configuration S at the monthly grain: a canonical product of rc31 whose
    # producer was in no build definition until rc36.
    # Before the ADM2 brackets, which price the same GCD surface this measures; the ADM2
    # brackets also read the source-stream ledger (rc41: undeclared until the strict
    # rebuild stopped on it), so both follow the ledger.
    Phase("Rice geography crosscheck", "pkinv.report.rice_geography_crosscheck", True,
          writes=("outputs/pakemis_rice_geography_crosscheck.csv",)),
    Phase("Survey monthly (configuration S)", "pkinv.report.monthly_ledger", True,
          writes=("outputs/pakemis_monthly_ledger_2024.csv",),
          reads=("outputs/national_monthly_2024.csv",)),
    Phase("Month registry", "pkinv.report.months", True,
          writes=("data/months.csv",), reads=(), audited=True),
    Phase("Temporal profile registry", "pkinv.report.temporal_profiles", True,
          writes=("outputs/pakemis_temporal_profiles.csv",),
          reads=("data/months.csv",)),
    Phase("Monthly layer, supported fiscal panel", "pkinv.report.monthly_all_years", True,
          writes=("outputs/pakemis_monthly_fy2015_16_fy2024_25.csv",
                  "outputs/pakemis_ghg_configuration_monthly.csv",
                  "outputs/pakemis_monthly_evidence.csv")),
    # rc68: after the fiscal panel, which it reads through grid_cube.load_streams (the
    # engine names per stream come from the monthly layer). It sat three phases earlier with
    # that read undeclared, so every build priced the brackets on the PREVIOUS build's panel;
    # the first rc68 clean rebuild, with no previous panel, stopped here.
    Phase("Spatial brackets (ADM2)", "pkinv.report.spatial_brackets_adm2", True,
          writes=("outputs/pakemis_spatial_brackets_adm2.csv",),
          reads=("outputs/pakemis_rice_geography_crosscheck.csv",
                 "outputs/pakemis_source_streams.csv",
                 "outputs/pakemis_monthly_fy2015_16_fy2024_25.csv",
                 "held:outputs/pakemis_road_weights_adm2.csv",)),
    # Why each flat month is flat. Runs after the monthly product because it reads it.
    Phase("Temporal decomposition (physics vs ignorance)", "pkinv.report.temporal_decomposition", True,
          writes=("outputs/pakemis_temporal_decomposition.csv",),
          reads=("outputs/pakemis_monthly_fy2015_16_fy2024_25.csv",)),
    # WIRED IN rc39 A2, the product_catalog class a third time. data/temporal_driver_registry.csv
    # is GENERATED from the decomposition above - its own header says "GENERATED ... Do not edit
    # by hand" - and a test asserts it regenerates identically, yet no build definition ran the
    # generator. So it held whatever the last hand-run left and went stale on every pass that
    # moved a number: twice in this round alone, once in A1 and again here. It runs in under a
    # second and reads only the file written immediately above it.
    Phase("Temporal driver registry", "scripts/build_temporal_driver_registry.py", True,
          writes=("data/temporal_driver_registry.csv",),
          reads=("outputs/pakemis_temporal_decomposition.csv",)),
    # After the monthly layer and the decomposition, because it reads both.
    Phase("Monthly coverage, all 120 months", "pkinv.report.monthly_coverage", True,
          writes=("outputs/pakemis_monthly_coverage.csv",
                  "outputs/pakemis_monthly_coverage_summary.csv",),
          reads=("outputs/pakemis_monthly_fy2015_16_fy2024_25.csv",
                 "outputs/pakemis_temporal_decomposition.csv",)),
    Phase("Flatness crosswalk (TE class vs physics)", "pkinv.report.flatness_crosswalk", True,
          writes=("outputs/pakemis_flatness_crosswalk.csv",)),
    # rc39 A8. The sector-level companion to the crosswalk above: agriculture's TE evidence
    # and its physical timing class per category, plus the NFDC national-province residual.
    # Runs here because it reads the monthly coverage and the decomposition, both written
    # immediately above.
    Phase("Agriculture timing classes + NFDC residual", "pkinv.report.agriculture_timing",
          True,
          writes=("outputs/agriculture_timing_classes.csv",
                  "outputs/agriculture_nfdc_province_residual.csv",),
          reads=("outputs/pakemis_monthly_coverage.csv",
                 "outputs/pakemis_temporal_decomposition.csv",)),
    # The gap, priced. Runs after the decomposition because every figure it prints is read
    # from it rather than typed into the request texts.
    Phase("Monthly data requests (the gap, priced)", "pkinv.report.monthly_data_requests", True,
          writes=("outputs/pakemis_monthly_data_requests.csv",),
          reads=("outputs/pakemis_temporal_decomposition.csv",)),
    Phase("Monthly cross-checks", "pkinv.report.monthly_crosschecks", True,
          writes=("outputs/monthly_crosschecks.csv",)),
    # rc41: two timing-variant products were hand-run scripts and therefore manifest
    # products no phase wrote - a reproduction from an empty outputs/ could only copy them.
    # Both read data/ and the cross-check above; promoted to phases, in the three build
    # definitions tests/test_build_definition.py holds to agreement.
    Phase("Bagasse timing variant", "scripts/bagasse_timing_variant.py", True,
          writes=("outputs/pakemis_bagasse_timing_variant.csv",),
          reads=("data/activity/monthly/pbs_qim_month_item.csv",)),
    Phase("Fertilizer timing variant", "scripts/fertilizer_timing_variant.py", True,
          writes=("outputs/pakemis_fertilizer_timing_variant.csv",),
          reads=("outputs/monthly_crosschecks.csv",)),
    Phase("Power profile variant", "scripts/power_profile_variant.py", True,
          writes=("outputs/pakemis_power_profile_variant.csv",),
          reads=("data/activity/power/generation_monthly.csv",)),
    Phase("Monthly controls register", "pkinv.report.monthly_controls", True,
          writes=("outputs/pakemis_monthly_controls.csv",)),
    Phase("CRT crosswalk", "pkinv.report.crt_crosswalk", True,
          writes=("outputs/national_crt_crosswalk.csv",)),
    Phase("EDGAR transport comparison", "pkinv.report.edgar_transport_comparison", True,
          writes=("outputs/national_edgar_transport_comparison.csv",)),
    # The rc33 validation lane: the district/livestock validators regenerate
    # every build (they were stale Aug-5 artifacts a manuscript claim rested
    # on), then the unified catalog gates existence + freshness + verdicts and
    # writes the (property x grain) scorecard. Order matters: the validators
    # need the district panels above; the catalog needs every validation
    # product, so it runs after them all.
    Phase("District rice records validation", "pkinv.eval.validation.district_rice_records", True,
          writes=("outputs/eval/validation/district_rice_vs_records.json",),
          reads=("outputs/district_totals_2024.csv",)),
    Phase("District records validation (multi)", "pkinv.eval.validation.district_records_multi", True,
          writes=("outputs/eval/validation/district_records_multi.json",)),
    # The province-rank livestock validation is NOT a phase: its producer
    # (pkinv.eval.validation.livestock_val) needs models/livestock_mgmt_card.json,
    # which lives in the companion repo - the catalog carries it as hand_run
    # with its age published, and the district-grain GLW lane below is the
    # live check at finer grain.
    Phase("Livestock district validation (GLW)", "scripts/validate_glw_districts.py", True,
          writes=("outputs/eval/validation/livestock_district_validation.csv",)),
    # Joint uncertainty. After the registry because it reads the same products, and after the
    # Monte Carlo because it recomputes none of it - the parametric term is READ from
    # national_uncertainty_montecarlo.csv, never re-derived.
    # rc41: the two benchmark suites ran after the joint-uncertainty layer that reads
    # the temporal hindcast (every build had read the previous release's); they read
    # sector and district products only, so they come first, and the joint layer now
    # declares every product it reads.
    Phase("Benchmark: spatial allocation", "pkinv.eval.benchmark_spatial", True,
          writes=("outputs/benchmark_spatial_allocation.csv",)),
    Phase("Benchmark: temporal hindcast", "pkinv.eval.benchmark_temporal", True,
          writes=("outputs/benchmark_temporal_hindcast.csv",)),
    Phase("Joint uncertainty by resolution", "pkinv.report.joint_uncertainty", True,
          writes=("outputs/pakemis_joint_uncertainty.csv",),
          reads=("outputs/national_uncertainty_montecarlo.csv",
                 "outputs/pakemis_atomic_annual.csv",
                 "outputs/benchmark_temporal_hindcast.csv",
                 "outputs/monthly_crosschecks.csv",
                 "outputs/pakemis_power_profile_variant.csv",
                 "outputs/national_priority_rankings.csv",
                 "outputs/pakemis_spatial_brackets.csv",
                 "outputs/pakemis_spatial_brackets_adm2.csv")),
    # After joint uncertainty because it asserts agreement with completeness_national();
    # after the configurations and every screening file because it joins them. The first
    # deliberate reader of the Pass-2 scope registry (Wave 4, through the doorway test).
    Phase("Completeness-mass ledger", "pkinv.report.completeness_mass", True,
          writes=("outputs/pakemis_completeness_mass.csv",),
          reads=("outputs/national_configurations.csv",)),
    # The exit scorecard, after everything it scores (Wave 6, the science freeze).
    # The supported fiscal-panel ensemble. After the series and the joint table, because it reads the
    # published series to gate itself: an interval around a total the release does not
    # publish would be worse than no interval.
    Phase("Longitudinal uncertainty", "pkinv.report.longitudinal_uncertainty", True,
          writes=("outputs/pakemis_longitudinal_uncertainty.csv",
                  "outputs/pakemis_trend_uncertainty.csv",
                  "outputs/pakemis_longitudinal_prefix.csv",),
          reads=("outputs/pakemis_national_series.csv",
                 "outputs/pakemis_joint_uncertainty.csv",)),
    # Last of the cross-sector layer: it describes the shape of everything above it, so it
    # runs after all of them. The claims registry reads it, which is how a manuscript and a
    # product stop being able to disagree in silence.
    # Last of all: it inventories everything above it, so it runs after everything above it.
    # rc37: the data/ counterpart of scripts/audit_outputs.py - every committed data
    # product classed as produced / hand-made-with-document / hand-made-without /
    # parameter / sidecar, so the re-derivation and transcription checks each have a list
    Phase("Data provenance audit", "pkinv.report.data_provenance", True,
          writes=("outputs/pakemis_data_provenance.csv",),
          reads=("data/source_documents.csv",)),
    # The two long tables in a second representation. After the atomic table and the
    # monthly panel, before the inventory that lists them. rc40: the catalog had declared
    # a monthly parquet for releases without one existing.
    Phase("Parquet twins", "pkinv.report.parquet_twins", True,
          writes=("outputs/pakemis_atomic_annual.parquet",
                  "outputs/pakemis_monthly_fy2015_16_fy2024_25.parquet"),
          reads=("outputs/pakemis_atomic_annual.csv",
                 "outputs/pakemis_monthly_fy2015_16_fy2024_25.csv")),
    # rc41: the product-coverage table (a manifest product and the supplement's generated
    # table) was a hand-run script; it globs outputs/, so it runs after the inventory.
    # What the archive deposit ships and by whose permission. After the manifest, because
    # the source register reads the manifest's document hashes rather than re-hashing
    # 3.8 GB - and before nothing, because it publishes rather than consumes.
    Phase("Facility registry", "pkinv.report.facility_registry", True,
          writes=("outputs/pakemis_facility_registry.csv",)),
    Phase("Gridded monthly cube", "pkinv.report.grid_cube", False,
          writes=("outputs/pakemis_grid_0p05_monthly.nc",
                  "outputs/pakemis_grid_provincial_check.csv",
                  "outputs/pakemis_spatial_unallocated.csv",
                  "outputs/pakemis_adm2_monthly.csv",
                  "outputs/pakemis_adm2_monthly_sector.csv",
                  "outputs/pakemis_adm2_stream_reference.csv",
                  "outputs/pakemis_grid_fallbacks.csv",
                  # rc41: configuration S gridded through the same dispatch, the priced
                  # register above, and the cube's own per-stream surface record
                  "outputs/pakemis_grid_0p05_monthly_ledger.nc",
                  "outputs/pakemis_adm1_ledger_2024.csv",
                  "outputs/pakemis_adm2_ledger_2024.csv",
                  "outputs/pakemis_grid_stream_surfaces.csv",),
          reads=("outputs/pakemis_source_streams.csv",
                 "outputs/national_monthly_2024.csv",
                 "outputs/pakemis_monthly_ledger_2024.csv",
                 "outputs/district_totals_2024.csv",
                 "outputs/residential_district_2024.csv",
                 "outputs/national_all_sectors.csv",
                 "outputs/national_all_sectors_ledger.csv",)),
    # The nine-fiscal-year air panel (air program Wave 3): atoms + rollup + the 630-cell
    # coverage matrix + the power screening scenario, each sector's air engine called
    # per year in-process under its own fiscal convention. Reads the stream register
    # (every atom anchors its stream fail-closed) and only committed activity beyond it.
    # Wave 2b: cement kiln COAL from clinker as a band per year (Q = K x H x s / NCV), the
    # independent activity constraint on HDIP's "Cement / Cement/Others" column; reads the
    # producer census and the cement statistics under data/, nothing this build writes.
    # Moved ahead of the air panel at rc58: the industrial air layer reads the band to size
    # the other-industry coal inside HDIP's cement column (a typed absence with its tonnage).
    Phase("Cement kiln coal reconstruction", "scripts/build_cement_kiln_coal_reconstruction.py", False,
          writes=("outputs/pakemis_cement_kiln_coal_reconstruction.csv",),
          reads=("data/activity/ippu/company_clinker_2023_24.csv",
                 "data/activity/industry/coal_by_consumer.csv",)),
    # rc60: the reviewed power SO2 admission register. It must precede the air panel, which
    # reads it through the source-class register's power.admitted_fuel_kt activity function -
    # the four grid classes have no activity without it.
    Phase("Power SO2 admission register", "scripts/build_power_admission_register.py", False,
          writes=("data/activity/power/power_so2_admission.csv",),
          reads=("data/activity/power/plant_fuel_ledger.csv",
                 "data/activity/power/plant_fuel_2024_25.csv",
                 "data/activity/power/plant_heat_rates.csv",
                 "data/activity/power/generation_monthly.csv",
                 "data/activity/power/plant_name_crosswalk.csv",
                 "data/activity/power/plant_locations.csv",
                 "data/facility_registry.csv",
                 "data/activity/industry/fuel_sulfur_evidence.csv",)),
    Phase("Air annual panel (supported fiscal panel)", "pkinv.report.air_annual", False,
          writes=("outputs/pakemis_air_atomic_annual.csv",
                  "outputs/pakemis_air_annual_fy2015_16_fy2024_25.csv",
                  "outputs/pakemis_air_annual_fy2015_16_fy2023_24.csv",
                  "outputs/pakemis_air_coverage_matrix.csv",
                  "outputs/pakemis_air_source_coverage.csv",
                  "outputs/power_air_screening_fy2015_16_fy2024_25.csv",
                  "outputs/power_air_screening_fy2015_16_fy2023_24.csv"),
          reads=("outputs/pakemis_source_streams.csv",
                 # rc58: the industry atoms are computed in-process from the register
                 "data/air_source_classes.csv",
                 "data/air_emission_factors.csv",
                 "data/activity/industry/fuel_sulfur_evidence.csv",
                 "data/physical_sources.csv",
                 "data/air_coverage_absences.csv",
                 "data/activity/power/power_so2_admission.csv",
                 "outputs/pakemis_kiln_allocation_adm2.csv",
                 "outputs/pakemis_cement_kiln_coal_reconstruction.csv",)),
    Phase("Air monthly allocation", "pkinv.report.air_monthly", False,
          writes=("outputs/pakemis_air_monthly.csv",
                  "outputs/pakemis_air_temporal_support.csv"),
          reads=("outputs/pakemis_air_atomic_annual.csv",
                 "outputs/pakemis_monthly_fy2015_16_fy2024_25.csv")),
    Phase("GHG conditional uncertainty", "pkinv.report.ghg_conditional_uncertainty", False,
          writes=("outputs/pakemis_ghg_conditional_uncertainty.csv",
                  "outputs/pakemis_ghg_trend_uncertainty.csv",
                  "outputs/pakemis_ghg_uncertainty_drivers.csv",
                  "outputs/pakemis_ghg_uncertainty_parameters.csv"),
          reads=GHG_UNCERTAINTY_READS + ("outputs/pakemis_ghg_configuration_atoms.csv",),
          audited=True),
    # rc69: moved up beside the GHG case. Both are audited, read disjoint products and write
    # disjoint files, so the scheduler runs them side by side (about 280 s of a cold build).
    Phase("Air conditional uncertainty", "pkinv.report.air_uncertainty", False,
          writes=("outputs/pakemis_air_conditional_uncertainty.csv",
                  "outputs/pakemis_air_trend_uncertainty.csv",
                  "outputs/pakemis_air_uncertainty_drivers.csv",
                  "outputs/pakemis_air_uncertainty_parameters.csv"),
          reads=AIR_UNCERTAINTY_READS, audited=True),
    Phase("HTAP air comparison", "pkinv.report.air_external_htap", False,
          writes=("outputs/pakemis_htap_nh3_annual.csv", "outputs/pakemis_htap_nh3_monthly.csv",
                  "outputs/pakemis_air_htap_comparison.csv",
                  "outputs/pakemis_air_htap_species_comparison.csv"),
          reads=("outputs/pakemis_air_atomic_annual.csv", "data/raw/htap/edgar_HTAPv32_NH3.zip",
                 "data/raw/htap/edgar_HTAPv32_NOx.zip", "data/raw/htap/edgar_HTAPv32_SO2.zip",
                 "data/raw/htap/edgar_HTAPv32_PM2.5.zip", "data/raw/htap/edgar_HTAPv32_BC.zip",
                 "data/raw/htap/edgar_HTAPv32_CO.zip", "data/raw/htap/edgar_HTAPv32_NMVOC.zip")),
    # rc69: road exhaust particulates under the guidebook's own technology-specific Tier 2
    # factors, against the matched HTAP road sector (the review's road PM2.5/BC question)
    Phase("Road technology case", "pkinv.report.road_technology_case", False,
          writes=("outputs/pakemis_road_technology_case.csv",),
          reads=("outputs/pakemis_air_atomic_annual.csv",
                 "outputs/pakemis_air_htap_species_comparison.csv",
                 "data/sectors/transport/activity/emep_tier2_road_pm_by_technology.csv")),
    # rc58/rc59: the source-class air layer (industry, ippu, fugitives) is a COVERED
    # estimate - the panel above computes its atoms in-process (air_annual.register_atoms);
    # this phase writes the class-level detail (estimates, typed absences and IE pointers
    # alike) and the per-sector, per-period uncertainty. Then the absence ledger: power's grid-only scenario pair
    # beside the panel, and industry's remaining typed absences read from the matrix.
    Phase("Air source classes (supported fiscal panel)",
          "pkinv.sectors.industry.air_pollutants", False,
          writes=("outputs/pakemis_air_source_classes_fy2015_16_fy2024_25.csv",
                  "outputs/pakemis_air_source_classes_fy2015_16_fy2023_24.csv",
                  "outputs/pakemis_air_source_class_uncertainty_by_year.csv",),
          reads=("data/air_source_classes.csv",
                 "data/air_emission_factors.csv",
                 "data/activity/industry/fuel_sulfur_evidence.csv",
                 "data/physical_sources.csv",
                 "data/activity/industry/coal_by_consumer.csv",
                 "data/activity/industry/gas_consumption.csv",
                 "data/activity/transport/ocac_sectoral_annual.csv",
                 "data/activity/power/captive_gas.csv",
                 "data/gis/kilns/pak_brick_kiln_assets.csv",
                 "outputs/pakemis_kiln_allocation_adm2.csv",
                 "outputs/pakemis_cement_kiln_coal_reconstruction.csv",)),
    # rc60: the account of what the admission moved, which needs both the panel it changed and
    # the screening it narrowed, so it runs after them.
    Phase("Power SO2 admission bridge", "scripts/build_power_admission_bridge.py", False,
          writes=("outputs/pakemis_air_power_admission_bridge.csv",),
          reads=("data/activity/power/power_so2_admission.csv",
                 "outputs/pakemis_air_annual_fy2015_16_fy2024_25.csv",
                 "outputs/power_air_screening_fy2015_16_fy2024_25.csv",)),
    Phase("Power air-control evidence", "pkinv.report.air_power_controls", False,
          writes=("outputs/pakemis_air_power_control_evidence.csv",
                  "outputs/pakemis_air_power_design_cases.csv"),
          reads=("data/activity/power/plant_fuel_ledger.csv", "data/power_fuel_quality.csv",
                 "data/raw/nepra/air_controls/port_qasim_generation_application_2014.pdf",
                 "data/raw/nepra/air_controls/cihc_pak_generation_application_2017.pdf",
                 "data/raw/nepra/air_controls/RETRIEVALS.csv")),
    Phase("Air absence-screening ledger", "scripts/build_air_absence_screening.py",
          False,
          writes=("outputs/pakemis_air_absence_screening_by_year.csv",),
          reads=("outputs/power_air_screening_fy2015_16_fy2024_25.csv",
                 "outputs/pakemis_air_coverage_matrix.csv",)),
    # rc69: what the covered total leaves out at power stacks, per species and year, as a share
    Phase("Air power-stack omission", "pkinv.report.air_power_omission", False,
          writes=("outputs/pakemis_air_power_omission.csv",),
          reads=("outputs/power_air_screening_fy2015_16_fy2024_25.csv",
                 "outputs/pakemis_air_annual_fy2015_16_fy2024_25.csv",
                 "outputs/pakemis_air_coverage_matrix.csv")),
    # rc59: the brick-kiln frame by kiln type - the FCBK and ZZ vectors the air sink rides
    # for the typed brick classes (built once; the brick shares are period-invariant).
    # Published so the district shares are inspectable; the sink builds the same frames
    # in-process from the same inputs.
    # rc62: the fleet's dated observations, and the year axis they support. Both precede the
    # kiln frame vectors, which still read the undated asset table - the frames are the cube's
    # placement and these are evidence beside it, not a replacement for it.
    Phase("Brick kiln fleet observations",
          "scripts/ingest_brick_kiln_fleet_observations.py", False,
          writes=("data/activity/industry/brick_kiln_fleet_observations.csv",),
          reads=("data/gis/kilns/pak_brick_kiln_assets.csv",)),
    Phase("Brick kiln fleet by year", "scripts/build_brick_kiln_fleet_by_year.py", False,
          writes=("outputs/pakemis_brick_kiln_fleet_by_year.csv",),
          reads=("data/activity/industry/brick_kiln_fleet_observations.csv",
                 "data/industry_params.csv",)),
    # Whether HDIP's coal consumer split is a measurement or a redistribution inside an
    # apparent-consumption identity. Reads the fleet bounds above, because the point of the
    # comparison is the booked brick column against the only independent bound held.
    Phase("Coal allocation identity", "pkinv.sectors.industry.coal_allocation_identity",
          False,
          writes=("outputs/pakemis_coal_allocation_identity.csv",),
          reads=("data/activity/industry/coal_supply.csv",
                 "data/activity/industry/coal_by_consumer.csv",
                 "outputs/pakemis_brick_kiln_fleet_by_year.csv",)),
    Phase("Kiln frame vectors", "pkinv.report.kiln_frame_vectors", False,
          writes=("outputs/pakemis_kiln_frame_adm2_by_type.csv",),
          reads=("data/ml/brick_kilns_pk.csv", "data/province_shares.csv",
                 "data/adm2_canonical.csv",)),
    # rc61: the same idea for the admitted power SO2 - published so the shares are inspectable,
    # while the sink builds the identical frames in-process from the identical inputs.
    Phase("Power admission vectors", "pkinv.report.power_admission_vectors", False,
          writes=("outputs/pakemis_power_admission_adm2_by_class.csv",),
          reads=("data/activity/power/power_so2_admission.csv",
                 "data/facility_registry.csv",
                 "data/adm2_canonical.csv",)),
    # The same dispatch, run for all nine registered periods and published annually. It
    # rebuilds the cube per period rather than reading its products, because the cube writes
    # the reference year only; nine builds cost about a minute.
    Phase("Fiscal-panel spatial products (ADM1 and ADM2)", "pkinv.report.spatial_by_year", False,
          writes=("outputs/pakemis_adm1_by_year.csv",
                  "outputs/pakemis_adm2_by_year.csv",
                  "outputs/pakemis_adm2_monthly_by_year.csv",
                  "outputs/pakemis_adm2_sector_by_year.csv",
                  "outputs/pakemis_adm2_stream_by_year.csv",
                  "outputs/pakemis_grid_fallbacks_by_year.csv",
                  "outputs/pakemis_spatial_unallocated_by_year.csv",
                  "outputs/pakemis_grid_0p05_annual_ref_fy2015_16_fy2024_25.nc",
                  "outputs/pakemis_ghg_grid_0p05_annual_l_tan_fy2015_16_fy2024_25.nc",
                  "outputs/pakemis_ghg_grid_0p05_annual_s_ipcc_fy2015_16_fy2024_25.nc",
                  "outputs/pakemis_ghg_grid_0p05_annual_l_ipcc_fy2015_16_fy2024_25.nc",
                  "outputs/pakemis_ghg_configuration_adm1.csv",
                  "outputs/pakemis_ghg_configuration_adm2.csv",
                  "outputs/pakemis_ghg_configuration_adm1_monthly.csv",
                  "outputs/pakemis_ghg_configuration_adm2_monthly.csv",
                  "outputs/pakemis_ghg_configuration_unallocated.csv",
                  "outputs/pakemis_grid_stream_surfaces_by_year.csv",
                  # the air sink on the same residency (air spatial Wave B): the
                  # pollutant masses ride the very vectors each period's cube placed
                  # their anchors on, which is why this is a second sink here and
                  # not a separate build
                  "outputs/pakemis_air_grid_0p05_annual_s_tan_fy2015_16_fy2024_25.nc",
                  "outputs/pakemis_air_grid_0p05_annual_l_tan_fy2015_16_fy2024_25.nc",
                  "outputs/pakemis_air_grid_0p05_annual_s_ipcc_fy2015_16_fy2024_25.nc",
                  "outputs/pakemis_air_grid_0p05_annual_l_ipcc_fy2015_16_fy2024_25.nc",
                  "outputs/pakemis_air_grid_0p05_monthly_s_tan_fy2015_16_fy2024_25.nc",
                  "outputs/pakemis_air_grid_0p05_monthly_l_tan_fy2015_16_fy2024_25.nc",
                  "outputs/pakemis_air_grid_0p05_monthly_s_ipcc_fy2015_16_fy2024_25.nc",
                  "outputs/pakemis_air_grid_0p05_monthly_l_ipcc_fy2015_16_fy2024_25.nc",
                  "outputs/pakemis_air_adm1_by_year.csv",
                  "outputs/pakemis_air_adm2_by_year.csv",
                  "outputs/pakemis_air_unallocated_by_year.csv",
                  "outputs/pakemis_air_monthly_unallocated.csv",),
          reads=("data/air_source_classes.csv",           # rc59: spatial_override per class
                 "data/ml/brick_kilns_pk.csv",
                 "outputs/pakemis_source_streams.csv",
                 "outputs/pakemis_monthly_fy2015_16_fy2024_25.csv",
                 "outputs/national_monthly_2024.csv",
                 "outputs/district_totals_2024.csv",
                 "outputs/residential_district_2024.csv",
                 "outputs/pakemis_air_atomic_annual.csv",
                 "outputs/pakemis_air_monthly.csv",
                 "outputs/pakemis_ghg_configuration_monthly.csv",
                 "data/activity/agriculture/crop_district_panel.csv",)),
    # rc47 Wave 6: the EDGAR-aligned derived aggregation reads the annual cube the
    # phase above writes, so it must follow it (the rc40 check_order lesson).
    Phase("EDGAR-aligned 0.1-degree grid", "scripts.build_grid_01deg", False,
          writes=("outputs/pakemis_grid_0p1_edgar_aligned.nc",),
          reads=("outputs/pakemis_grid_0p05_annual_ref_fy2015_16_fy2024_25.nc",)),
    # Reads the substitution record the phase above writes, so it must follow it: the registry
    # grades a stream-year from what the build DID, and the record of that is its input.
    Phase("Spatial weight registry (per stream-year)", "pkinv.report.spatial_weights", True,
          writes=("outputs/pakemis_spatial_weights_by_year.csv",),
          reads=("outputs/pakemis_source_streams.csv",
                 "outputs/pakemis_grid_stream_surfaces_by_year.csv",
                 "outputs/pakemis_grid_fallbacks_by_year.csv",
                 "outputs/pakemis_monthly_fy2015_16_fy2024_25.csv",
                 "data/periods.csv", "data/province_shares.csv",
                 "data/activity/waste/population_district.csv",
                 "data/activity/agriculture/crop_district_panel.csv",
                 "data/activity/fugitives/flare_sites_pak.csv",
                 "data/activity/residential/hies/hies_national_totals.csv",
                 "data/activity/residential/hies/hies_fuel_quantities.csv")),
    # The air support join runs AFTER the registry because the registry IS its input:
    # the by-year air tables carry no evidence columns (the badge is the registry's to
    # derive from what the build did), and this is the phase that publishes the join.
    Phase("Air spatial support ledger", "scripts/build_air_spatial_support.py", False,
          writes=("outputs/pakemis_air_spatial_support_by_year.csv",
                  "outputs/pakemis_air_uncertainty_split_by_year.csv",),
          reads=("outputs/pakemis_air_atomic_annual.csv",
                 "outputs/pakemis_air_conditional_uncertainty.csv",
                 "outputs/pakemis_spatial_weights_by_year.csv",
                 "data/air_source_classes.csv",
                 "data/ml/brick_kilns_pk.csv",)),
    # Configuration S at ADM2: reads the cube's sector view; the cube itself
    # reads THIS file's previous vintage for the S-class label array, which is
    # why the two are declared and ordered rather than left to chance.
    # rc39 A9. Reads the cube's fallback register and the ADM2 product, so it runs after
    # both: the register says a substitution happened, this says what it cost.
    # rc47 Wave 7: the audit's deliverable - joins the atomic table, the weight
    # registry and both remainder ledgers at (period, stream); must follow them all.
    Phase("Stream-to-support ledger", "scripts.build_stream_support_ledger", False,
          writes=("outputs/pakemis_stream_support_ledger.csv",),
          reads=("outputs/pakemis_atomic_annual.csv",
                 "outputs/pakemis_spatial_weights_by_year.csv",
                 "outputs/pakemis_grid_stream_surfaces_by_year.csv",
                 "outputs/pakemis_grid_fallbacks_by_year.csv",
                 "outputs/pakemis_spatial_unallocated_by_year.csv",)),
    # v3: the coal fleet's commissioning check. The weight registry says every power_coal
    # stream-year is its own period's pattern; this joins each period's station pool to GEM
    # start/retired years and prints the mass outside the window (expected zero) beside the
    # mass on the fallback raster (the real exposure). COMPARATOR ONLY.
    # rc63: THIS PHASE AND "Power fuel reconciliation" READ EACH OTHER, and until now only one
    # direction was declared. The check takes each period's coal stations and their energy from
    # the reconciliation; the reconciliation takes each station's window verdict back from the
    # check, for one descriptive column. Neither can run first on a fresh tree with the other's
    # output in hand, so the check reads the reconciliation the PREVIOUS run wrote - which is
    # what `prior:` means, and what it had been doing undeclared since rc62. That is sound
    # because the station list and energies do not depend on the verdict column: the pair
    # settles in one pass, and tests/test_power_station_status.py holds the check to
    # reproducing its own output from the tree the build leaves. The undeclared read was found
    # when a development run recorded it and the scheduler refused the order.
    Phase("Power station commissioning check", "pkinv.report.power_station_status", True,
          writes=("outputs/pakemis_power_station_status.csv",),
          reads=("prior:outputs/pakemis_power_fuel_reconciliation.csv",
                 "data/activity/power/gem_coal_pak.csv",
                 "data/activity/power/plant_fuel_ledger.csv",
                 "data/activity/power/generation_monthly.csv",
                 "data/activity/power/plant_name_crosswalk.csv",
                 "data/periods.csv")),
    # Year-specific grid-power geography, fuel by fuel. Compare the current activity
    # mass placed on own-year shares with that same mass placed on reference-year
    # shares; retain the archived source-vintage comparison as a separate diagnostic.
    Phase("Power provincial basis by year", "pkinv.report.power_provincial_basis", True,
          writes=("outputs/pakemis_power_provincial_basis_by_year.csv",),
          reads=("outputs/pakemis_adm1_by_year.csv",
                 "data/baselines/pre_rc66_power_provincial/pakemis_adm1_by_year_power.csv",
                 "data/activity/power/plant_fuel_ledger.csv",
                 "data/activity/power/plant_fuel_quantity_back_years.csv",
                 "data/activity/power/coal_plant_fuel_back_years.csv",
                 "data/activity/power/coal_energy_booking.csv",
                 "data/activity/power/bagasse_generation.csv",
                 "data/activity/power/generation_monthly.csv",
                 "data/activity/power/plant_name_crosswalk.csv",
                 "data/activity/power/plant_locations.csv",
                 "data/activity/power/fuel_consumed.csv",
                 "data/periods.csv")),
    Phase("Air spatial (all sectors)", "pkinv.report.air_spatial_sectors", False,
          writes=("outputs/air_pollutants_adm1.csv",
                  "outputs/air_pollutants_adm2.csv",),
          reads=("outputs/pakemis_grid_provincial_check.csv",
                 "outputs/pakemis_adm2_stream_reference.csv",
                 "outputs/pakemis_stream_support_ledger.csv",
                 "outputs/air_pollutants_2024.csv",
                 "outputs/air_pollutants_provincial_2024.csv",
                 "outputs/residential_air_pollutants_2024.csv",
                 "outputs/transport_air_pollutants_2024.csv",
                 "outputs/waste_air_pollutants_2024.csv",
                 "outputs/power_air_pollutants_fy2023_24.csv",
                 "outputs/railways_air_pollutants_2024.csv",
                 "outputs/aviation_air_pollutants_fy2023_24.csv",)),
    # rc58: three views of the industrial air layer that read the panel and its spatial
    # family - Lahore District by sector beside the unplaced remainder, calendar 2023
    # composed from two fiscal years on the monthly cube's own shares, and the EDGAR v8.1
    # matched-year comparison (a comparison, never a fit: the registers are held byte-
    # identical across it by test).
    Phase("Lahore air view", "scripts/build_air_lahore_view.py", False,
          writes=("outputs/pakemis_air_lahore_by_year.csv",),
          reads=("outputs/pakemis_air_adm2_by_year.csv",
                 "outputs/pakemis_air_unallocated_by_year.csv",
                 "outputs/pakemis_air_spatial_support_by_year.csv",
                 "data/adm2_canonical.csv",)),
    Phase("Industry air, calendar 2023", "pkinv.report.air_calendar_2023", False,
          writes=("outputs/pakemis_air_industry_cy2023.csv",),
          reads=("outputs/pakemis_air_source_classes_fy2015_16_fy2024_25.csv",
                 "outputs/pakemis_monthly_fy2015_16_fy2024_25.csv",
                 "data/air_source_classes.csv",)),
    Phase("Industry air vs EDGAR", "scripts/build_industry_air_edgar_comparison.py", False,
          writes=("outputs/pakemis_industry_air_edgar_comparison.csv",),
          reads=("outputs/pakemis_air_annual_fy2015_16_fy2024_25.csv",
                 "data/activity/industry/edgar_pak_industry_ap_series.csv",)),
    Phase("Spatial exceptions + ADM2 nesting", "pkinv.report.spatial_exceptions", True,
          writes=("outputs/pakemis_spatial_exceptions.csv",
                  "outputs/pakemis_adm2_nesting_check.csv",),
          reads=("outputs/pakemis_grid_fallbacks.csv",
                 "outputs/pakemis_adm2_monthly_sector.csv",
                 "outputs/provincial_totals_2024.csv",)),
    # Coarse by geometry, or coarse by ignorance. rc41: runs after the cube, whose own
    # dispatch record (pakemis_grid_stream_surfaces.csv) is the allocation_surface it
    # publishes - the per-geometry reconstruction it used to make named the wrong raster
    # for 77 streams and a raster for the 24 the cube never grids.
    Phase("Spatial decomposition (geometry vs ignorance)", "pkinv.report.spatial_decomposition", True,
          writes=("outputs/pakemis_spatial_decomposition.csv",),
          reads=("outputs/pakemis_source_streams.csv",)),
    # After the cube and the joint product: the ensemble reads the provincial
    # check, the S4 ledger and the joint timing rows, and its annual layer is a
    # bit-identical prefix of the National uncertainty phase's own draws.
    Phase("Common draw ensemble", "pkinv.report.common_ensemble", True,
          writes=("outputs/pakemis_ensemble_summary.csv",
                  "outputs/pakemis_ensemble_ledger_summary.csv",
                  "outputs/pakemis_ensemble_spatial_conditionals.csv",
                  "outputs/mc_draws/pakemis_ensemble_annual.parquet",
                  "outputs/mc_draws/pakemis_ensemble_monthly.parquet",
                  "outputs/mc_draws/pakemis_ensemble_spatial.parquet",
                  "outputs/mc_draws/pakemis_ensemble_annual.meta.json",
                  "outputs/mc_draws/pakemis_ensemble_monthly.meta.json",
                  "outputs/mc_draws/pakemis_ensemble_spatial.meta.json"),
          reads=("outputs/national_monthly_2024.csv",
                 "outputs/pakemis_joint_uncertainty.csv",
                 "outputs/pakemis_source_streams.csv",
                 "outputs/pakemis_grid_provincial_check.csv",
                 "outputs/pakemis_spatial_unallocated.csv",
                 "outputs/national_uncertainty_montecarlo.csv",
                 "outputs/pakemis_spatial_brackets.csv",
                 "outputs/pakemis_spatial_brackets_adm2.csv",
                 "outputs/residential_configurations_2024.csv",
                 "data/province_shares.csv",)),
    # The effluent factor's upper tail (2026-10-07, the twenty-second review's item 9).
    # IT SITS HERE, AFTER THE COMMON ENSEMBLE, AND THE FIRST PLACEMENT WAS WRONG. It was
    # put after the variance attribution, which is where its other two inputs are written
    # - but it divides Jansen's numerator by the NATIONAL ensemble's variance, and that
    # parquet is written by the phase above. At line 522 the index would have been computed
    # against the PREVIOUS release's variance in every build, which is the rc41 defect its
    # own comment cites. The three earlier inputs are all written well before here, so this
    # position satisfies every read rather than three of four.
    # rc67: domestic wastewater nitrous oxide under the 2019 Refinement (the reference) and
    # the 2006 Guidelines (the alternative), on the same draws: the gas for every year and
    # each method's interval for the category and the national total. It refuses to write
    # unless the ensemble's wastewater column is the reference draw file's own prefix.
    Phase("Wastewater method comparison", "pkinv.report.wastewater_method_comparison", True,
          writes=("outputs/pakemis_wastewater_method_comparison.csv",),
          reads=("outputs/mc_draws/pakemis_ensemble_annual.parquet",
                 "outputs/mc_draws/waste_parameter_rerun.csv",
                 "outputs/mc_draws/waste_parameter_rerun.meta.json",
                 "outputs/mc_draws/waste_parameter_rerun_ipcc2006.csv",
                 "outputs/mc_draws/waste_parameter_rerun_ipcc2006.meta.json",
                 "outputs/national_all_sectors.csv",
                 "data/waste_params.csv", "data/periods.csv",
                 "data/activity/wastewater/sanitation_shares.csv",
                 "data/activity/wastewater/protein.csv")),
    # rc67: what drives the national uncertainty, from the released ensemble itself -
    # category and sector shares of variance and of the tails, the interval with one
    # category fixed, and the wastewater effluent factor frozen in a waste-engine rerun on
    # the ensemble's own streams. It REPLACES the surrogate Sobol attribution, its
    # estimator sweep and the effluent tail diagnostic, which compared the engine with
    # that surrogate; all three are retired.
    Phase("Uncertainty drivers", "pkinv.report.ensemble_drivers", True,
          writes=("outputs/pakemis_uncertainty_drivers.csv",),
          reads=("outputs/mc_draws/pakemis_ensemble_annual.parquet",
                 "outputs/mc_draws/waste_parameter_rerun.csv",
                 "outputs/mc_draws/waste_parameter_rerun.meta.json",
                 "data/waste_params.csv")),
    # rc41: the exit scorecard grades the common ensemble's summary, a product of the
    # phase that ran eleven places after it; it follows the ensemble now.
    Phase("Pass-2 exit scorecard", "pkinv.report.pass2_scorecard", True,
          writes=("outputs/pakemis_pass2_scorecard.csv",),
          reads=("outputs/pakemis_temporal_decomposition.csv",
                 "outputs/pakemis_completeness_mass.csv",
                 "outputs/pakemis_spatial_decomposition.csv",
                 "outputs/pakemis_ensemble_summary.csv")),
    # THE COAL-ENERGY ACCOUNTS, moved up on 2026-10-07 from beside the rest of the Stage 2
    # power work. Structural trajectories prices the non-circular coal axis from the
    # configurations table, so the pair has to precede it; left where they were, the
    # trajectories phase read a file written twenty phases later and the ordering check
    # refused the build. They only need the Power runner's implied-CV table, which is
    # written a hundred phases earlier, so moving them up costs nothing.
    #
    # The supported fiscal-panel plant/fuel/year reconciliation. Reads the committed ledger, the back-year
    # transcription from the editions its producer does not read, and the generation series.
    Phase("Power fuel reconciliation", "pkinv.sectors.power.fuel_reconciliation", False,
          writes=("outputs/pakemis_power_fuel_reconciliation.csv",),
          # WHAT IT ACTUALLY READS. This tuple listed fuel_consumed.csv and
          # coal_by_consumer.csv, which the module never opens; those belong to the
          # reference audit next to it. An over-declared read costs only a needless
          # rebuild, but it misdescribes the dependency graph that --group dev reuses.
          # held: - the campaign file is an INPUT this build does not produce. Only a
          # data/ path is exempt from rule 1 implicitly; research_campaign/ is not,
          # and declaring it bare made check_order report a read before its writer.
          reads=("data/activity/power/plant_fuel_year_controls.csv",
                 "data/activity/power/coal_plant_fuel_back_years.csv",
                 "data/activity/power/coal_energy_booking.csv",
                 "data/activity/power/generation_by_fuel.csv",
                 "data/periods.csv",)),
    # The four candidate coal-energy accounts, read off the reconciliation above it.
    Phase("Power coal configurations", "pkinv.sectors.power.coal_configurations", False,
          writes=("outputs/pakemis_power_coal_configurations.csv",),
          reads=("outputs/pakemis_power_fuel_reconciliation.csv",
                 "data/activity/power/fuel_consumed.csv",
                 "data/activity/industry/coal_by_consumer.csv",
                 "outputs/power_implied_coal_cv_fy2023_24.csv",)),
    Phase("Structural trajectories", "pkinv.report.structural_trajectories", True,
          writes=("outputs/pakemis_structural_trajectories.csv",)),
    # the activity data behind the estimates, normalised under one declared vocabulary so it can be
    # used without running PakEmis; it must precede the semantic release, which republishes it
    Phase("Activity publication", "pkinv.activity.publish", True,
          writes=("outputs/activity/activity_fuel_sales_national.csv",
                  "outputs/activity/activity_fuel_sales_area.csv",
                  "outputs/activity/activity_livestock.csv",
                  "outputs/activity/activity_crops.csv",
                  "outputs/activity/activity_fertiliser.csv",
                  "outputs/activity/activity_power_plants.csv",
                  "outputs/activity/activity_power_monthly.csv",
                  "outputs/activity/activity_household_fuel.csv",
                  "outputs/activity/activity_industry_fuel.csv",
                  "outputs/activity/activity_industry_production.csv",
                  "outputs/activity/activity_gas_supply.csv",
                  "outputs/activity/activity_gas_network.csv",
                  "outputs/activity/activity_waste_services.csv",
                  "outputs/activity/activity_waste_flows.csv",
                  "outputs/activity/activity_railways.csv",
                  "outputs/activity/activity_aviation.csv",
                  "outputs/activity/activity_vehicles.csv",
                  "outputs/activity/activity_source_details.csv",
                  "outputs/activity/activity_column_guide.csv",
                  "outputs/activity/public/activity_aviation.csv",
                  "outputs/activity/public/activity_crops.csv",
                  "outputs/activity/public/activity_fertiliser.csv",
                  "outputs/activity/public/activity_fuel_sales_area.csv",
                  "outputs/activity/public/activity_fuel_sales_national.csv",
                  "outputs/activity/public/activity_gas_network.csv",
                  "outputs/activity/public/activity_gas_supply.csv",
                  "outputs/activity/public/activity_household_fuel.csv",
                  "outputs/activity/public/activity_industry_fuel.csv",
                  "outputs/activity/public/activity_industry_production.csv",
                  "outputs/activity/public/activity_livestock.csv",
                  "outputs/activity/public/activity_power_monthly.csv",
                  "outputs/activity/public/activity_power_plants.csv",
                  "outputs/activity/public/activity_railways.csv",
                  "outputs/activity/public/activity_vehicles.csv",
                  "outputs/activity/public/activity_waste_flows.csv",
                  "outputs/activity/public/activity_waste_services.csv",),
          # plain data reads: these are committed inputs, not manifest products, so `held:` (which
          # data/held_products.csv governs) is the wrong form for them
          reads=("data/activity_files.csv",
                 "data/activity_columns.csv",
                 "data/activity_evidence_classes.csv",
                 "data/activity_evidence_map.csv",
                 "data/activity_item_map.csv",
                 "data/activity_collections.csv",
                 "data/activity_measures.csv",
                 "data/activity_units.csv",
                 "data/activity_labels.csv",
                 "data/activity_use_notes.csv",
                 "data/adm2_canonical.csv",
                 "data/activity/",
                 "data/nfdc/afr2025_fertilizer_gas_by_plant.csv",
                 "data/nfdc/afr2025_fertilizer_gas_monthly.csv",
                 "outputs/waste_ledger_2024.csv",)),
    # v1.0.0: the semantic release - the one numerical truth layer the paper's stored
    # queries, the Explorer and the downloads consume by release id and hash
    Phase("Semantic release", "pkinv.semantic.build", True,
          idempotent=True,
          # prior: - AND IT CANNOT BE OTHERWISE. The semantic build opens
          # outputs/release_manifest.json (semantic/release_json.py for reporting_period and
          # the baseline configuration code, semantic/downloads.py for the product name set),
          # and the manifest HASHES 56 semantic products. So the manifest cannot precede the
          # semantic build, and the semantic build's read is necessarily of the PREVIOUS
          # release's manifest - the same fixpoint constraint release_fixpoint.py documents
          # for the paper hashes. The strict build observed the concrete forward edge and
          # refused it, correctly: an undeclared forward edge reads last run's data silently.
          # Declared here so it is a stated prior read instead.
          #
          # WHAT THE LAG COSTS. The version and the commit do NOT come from it - the version
          # is pkinv.__version__ and the commit is published as a pointer for the consumer to
          # resolve - and reporting_period and the baseline code do not move within a release
          # line. The one quantity that does lag is downloads.py's name set, which unions the
          # previous manifest's product paths: a product added in this release joins the
          # download catalogue's name set at the NEXT mint. That is a one-release lag in a
          # name list, not in any number.
          writes=("outputs/semantic/",
                  "outputs/semantic/fact_annual.csv",
                  "outputs/semantic/fact_spatial_basis_year.csv",
                  # NAMED, not left to the directory write. It is the semantic CONTRACT, the
                  # release manifest hashes it, and the published-vintages register reads it
                  # by name - and a reader of a named file is not matched by a directory
                  # owner here, so the register's read looked like a read of something no
                  # phase produces.
                  "outputs/semantic/semantic_release.json",),
          reads=("prior:outputs/release_manifest.json",
                 "outputs/pakemis_atomic_annual.csv",
                 "outputs/pakemis_annual_fy2015_16_fy2024_25.csv",
                 "outputs/pakemis_monthly_fy2015_16_fy2024_25.csv",
                 "outputs/pakemis_monthly_ledger_2024.csv",
                 "outputs/pakemis_adm2_monthly_sector.csv",
                 "outputs/pakemis_adm2_ledger_2024.csv",
                 "outputs/pakemis_adm1_ledger_2024.csv",
                 "outputs/pakemis_spatial_unallocated.csv",
                 "outputs/pakemis_grid_provincial_check.csv",
                 "outputs/pakemis_joint_uncertainty.csv",
                 "outputs/pakemis_longitudinal_uncertainty.csv",
                 "outputs/pakemis_trend_uncertainty.csv",
                 "outputs/national_uncertainty_montecarlo.csv",
                 "outputs/completeness.csv",
                 "outputs/pakemis_completeness_mass.csv",
                 "outputs/pakemis_source_streams.csv",
                 "outputs/pakemis_spatial_decomposition.csv",
                 "outputs/pakemis_temporal_decomposition.csv",
                 "outputs/pakemis_grid_fallbacks.csv",
                 "outputs/national_configurations.csv",
                 "outputs/timeseries_1990_2024.csv",
                 "data/periods.csv", "data/months.csv", "data/adm2_canonical.csv",
                 "data/province_shares.csv", "data/cross_sector_ledger_map.csv",
                 "data/product_schemas.csv",
                 # rc63: THE AIR PRODUCTS THIS PHASE HAS ALWAYS READ AND NEVER DECLARED.
                 # pkinv.semantic.facts resolves twelve air ids through product_schemas.csv at
                 # RUN TIME, so the dependency is invisible to the static `reads` above. The
                 # consequence is not cosmetic: --changed would skip the semantic build whenever
                 # only an air product moved, and the semantic build is what regenerates the
                 # table behind tests/semantic/golden/air_panel_so2_series.json - the golden that
                 # exists to make exactly that kind of move visible.
                 "outputs/pakemis_air_annual_fy2015_16_fy2024_25.csv",
                 "outputs/pakemis_air_source_classes_fy2015_16_fy2024_25.csv",
                 "outputs/pakemis_air_absence_screening_by_year.csv",
                 "outputs/pakemis_air_lahore_by_year.csv",
                 "outputs/air_pollutants_2024.csv",
                 "outputs/air_pollutants_timeseries_1990_2024.csv",
                 "outputs/power_air_pollutants_fy2023_24.csv",
                 "outputs/transport_air_pollutants_2024.csv",
                 "outputs/residential_air_pollutants_2024.csv",
                 "outputs/railways_air_pollutants_2024.csv",
                 "outputs/aviation_air_pollutants_fy2023_24.csv",
                 "outputs/waste_air_pollutants_2024.csv",
                 # FOUR READS OF ARTIFACTS THIS PHASE PRECEDES, declared as `prior:`
                 # because that is what they are. pkinv.semantic.assets requires the source
                 # register and the three validation products as release evidence and HASHES
                 # each one, but their producers - "Deposit manifest" and "Validation catalog
                 # + scorecard" - are declared later, and they must stay later: the catalog
                 # probes fifteen products written between here and there, and two of those
                 # phases in turn read outputs/semantic/. That is a genuine cycle, so one edge
                 # has to be the previous run's copy, and the release dance builds twice for
                 # this reason. Declaring it makes a stale digest a visible contract rather
                 # than an accident; the build's forward-edge check raised it, and it is
                 # recorded here instead of being suppressed.
                 "prior:outputs/pakemis_source_register.csv",
                 "prior:outputs/pakemis_validation_catalog.csv",
                 "prior:outputs/pakemis_validation_scorecard.csv",
                 "prior:outputs/pakemis_validation_sector_scorecard.csv",
                 # 2026-10-07, the same cycle one link further out. The vintages table is
                 # a catalog of PUBLISHED releases, and its builder verifies each row by
                 # hashing the semantic release this phase writes - so the two read each
                 # other. The cycle is cut here rather than there because the vintages
                 # table only changes when a release is minted, while semantic_release.json
                 # changes every build: giving the vintages builder last build's JSON would
                 # blind the very divergence it exists to detect.
                 "prior:data/catalog/published_release_vintages.csv",)),
    # The industrial boundary ledger: what "industrial emissions" contains under
    # 1.A.2 (incl. captive) + 2.A-2.G, and what of it this release prices - the
    # priced series, the screening brackets, the typed absences with their named
    # acquisitions, and the registered EDGAR 1.A.2 gap as a DIAGNOSTIC.
    # Wave 1 of the boundary program: OGRA's own gas classes per fiscal year - the
    # feedstock/captive/general-industry separation the 1.A.2 closure depends on.
    # THE RELEASE-HISTORY PAIR, moved here on 2026-10-07 from two hundred lines above.
    # Neither declares `reads`, because each answers from git rather than from one input -
    # which is exactly why the scheduler could not order them and why they sat in the wrong
    # place for releases. The first complete build recorded their real writes and reads in
    # the cache and the ordering check then refused them twice in a row: the fingerprints
    # phase read the vintages table before its producer, and the vintages builder hashes
    # outputs/semantic/semantic_release.json, which the phase directly above writes. Both
    # violations were real the whole time; only the evidence is new.
    # v3: the spatial evidence taxonomy weighted by mass, with the five classes defined in
    # plain words - the table the "61.5 percent static structural" sentence cites.
    # v3: enteric CH4 by species against the BTR's Figure 1 (a declared transcription).
    Phase("Enteric BTR bridge", "pkinv.report.enteric_btr_bridge", True,
          writes=("outputs/pakemis_enteric_btr_bridge.csv",),
          reads=("outputs/semantic/fact_annual.csv",)),
    Phase("Spatial basis taxonomy", "pkinv.report.spatial_basis_taxonomy", True,
          writes=("outputs/pakemis_spatial_basis_classes.csv",
                  "outputs/pakemis_spatial_basis_shares.csv",
                  "outputs/pakemis_spatial_basis_shares_by_sector.csv"),
          reads=("outputs/semantic/fact_spatial_basis_year.csv",)),
    Phase("Published release vintages", "scripts/build_published_vintages.py", True,
          # prior: - this register is ABOUT previous releases. It hashes
          # outputs/release_manifest.json out of git at each published commit and checks the
          # digest that was served. It also hashes the working-tree copy, to answer one
          # question: is this tree the vintage already published under this version string?
          # For a version never served the answer is "not-yet-published" whatever the file
          # holds, and for one that was, a mismatch is the finding the register exists to
          # report. Declared prior: because the forward edge is real and unavoidable - the
          # manifest is written at the end of the build and this phase runs long before it.
          # Only the MANIFEST is prior:. The semantic contract is written by the Semantic
          # release phase, which runs EARLIER, so reading it is an ordinary backward edge -
          # and marking it prior: claimed a forward edge that does not exist, which
          # test_held_products refuses for exactly that reason.
          reads=("prior:outputs/release_manifest.json",
                 "outputs/semantic/semantic_release.json"),
          writes=("data/catalog/published_release_vintages.csv",)),
    Phase("Release axis fingerprints", "scripts/build_release_axis_fingerprints.py", True,
          writes=("outputs/pakemis_release_axis_fingerprints.csv",)),
    Phase("OGRA gas-class series", "scripts/build_ogra_gas_class_series.py", False,
          writes=("outputs/ogra_gas_class_series.csv",),
          reads=("data/raw/ogra/state_of_industry/ogra_petroleum_industry_report_2023_24.pdf",)),
    # Wave 1b: an independent 1.A.2 combustion control from the UNSD balances (the
    # public HDIP stand-in), the release's own IPCC factors applied - a second
    # benchmark the boundary ledger's diagnostic lane carries beside EDGAR.
    Phase("UNSD industrial-combustion control", "scripts/build_unsd_industry_combustion.py", False,
          writes=("outputs/unsd_industry_combustion_control.csv",),
          reads=("data/raw/unsd/energy_balances/unsd_energy_balances_2023_countries_M_Q.pdf",
                 "data/emission_factors.csv",)),
    # Industrial-coal reconstruction, Wave 1 (2026-09-10): the reference's brick and cement
    # coal are HDIP's allocation; these three products hold the diagnosis OPEN with held
    # evidence - the UNSD supply block (the one independent supply control), the source
    # reconciliation (official value, edition, actual period, three labels, evidence,
    # decision-rule row), and the coal balance with H1/H2 tested per year. None enters
    # any total; the reconciliation reads the coal-lane product written at the top of
    # the national layer, the balance reads the UNSD supply product written just above.
    Phase("UNSD coal supply control", "scripts/build_unsd_coal_supply.py", False,
          writes=("outputs/unsd_coal_supply_control.csv",),
          reads=("data/raw/unsd/energy_balances/unsd_energy_balances_2023_countries_M_Q.pdf",)),
    # rc53 Wave A1: every published print of HDIP's coal-by-sector allocation, paired by reference
    # period, so a REALLOCATION inside an unchanged total is visible as one. It reads only the
    # vintages ingest, so it has no build dependency; which print the engine books is declared in
    # data/coal_booking_policy.csv and resolved by sectors/industry/solid_fuels.py.
    Phase("Coal vintage ledger", "scripts/build_coal_vintage_ledger.py", False,
          writes=("outputs/pakemis_coal_vintage_ledger.csv",),
          reads=("data/activity/industry/coal_by_sector_vintages.csv",)),
    Phase("Coal source reconciliation", "scripts/build_coal_source_reconciliation.py", False,
          writes=("outputs/pakemis_coal_source_reconciliation.csv",),
          reads=("data/activity/industry/coal_by_consumer.csv",
                 "data/activity/industry/coal_supply.csv",
                 "data/activity/power/plant_fuel_ledger.csv",
                 "outputs/industry_coal_reconciliation.csv",)),
    Phase("Coal balance", "scripts/build_coal_balance.py", False,
          writes=("outputs/pakemis_coal_balance.csv",),
          reads=("data/activity/industry/coal_supply.csv",
                 "data/activity/industry/coal_by_consumer.csv",
                 "data/activity/industry/coal_production_by_province.csv",
                 "data/activity/power/plant_fuel_ledger.csv",
                 "outputs/unsd_coal_supply_control.csv",)),
    # Wave 4: the replacement bridge - official atoms -> activity -> fuel-quality -> boundary
    # -> reconstructed, with the reference decision per component. Reads the atom table
    # (written far above) and the two Wave 1/2b products written just above.
    Phase("Industrial coal bridge", "scripts/build_industrial_coal_bridge.py", False,
          writes=("outputs/pakemis_industrial_coal_bridge.csv",),
          reads=("outputs/pakemis_atomic_annual.csv",
                 "outputs/pakemis_coal_balance.csv",
                 "outputs/pakemis_cement_kiln_coal_reconstruction.csv",
                 "data/activity/industry/coal_by_consumer.csv",)),
    # Wave B1 of the boundary program: brick-kiln coal as bounded alternatives - the official value
    # (a residual of domestic production by HDIP's own footnote), the joint band, and the
    # implied-intensity sensitivity at CCAC's one held brick output. No central is manufactured.
    Phase("Brick coal alternatives", "scripts/build_brick_coal_alternatives.py", False,
          writes=("outputs/pakemis_brick_coal_alternatives.csv",),
          reads=("outputs/pakemis_industrial_coal_bridge.csv",
                 "outputs/pakemis_coal_balance.csv",
                 "data/activity/industry/coal_by_consumer.csv",
                 "data/activity/industry/coal_by_sector_pey_compendium.csv",)),
    # rc53 Wave D: the same stream from a kiln COUNT and a MEASURED fuel rate - the first estimate
    # of brick coal that does not read HDIP's own residual column. No central: two independent
    # sources agree on intensity and disagree on scale by a factor of three.
    Phase("Brick activity reconstruction", "scripts/build_brick_activity_reconstruction.py", False,
          writes=("outputs/pakemis_brick_activity_reconstruction.csv",),
          reads=("data/activity/industry/brick_kiln_activity_evidence.csv",
                 "data/activity/industry/coal_by_sector_vintages.csv",
                 "data/coal_booking_policy.csv",
                 "data/province_shares.csv",)),
    # rc53 Wave E: the decision record - what is booked, what the alternatives are, and whether
    # any has EARNED the booking against four tests. rc53 adopts nothing; the record says why.
    Phase("Industrial coal decision", "scripts/build_industrial_coal_decision.py", False,
          writes=("outputs/pakemis_industrial_coal_decision.csv",
                  "outputs/pakemis_fuel_sulfur_decision.csv",),
          reads=("outputs/pakemis_coal_balance.csv",
                 "outputs/pakemis_cement_kiln_coal_reconstruction.csv",
                 "outputs/pakemis_brick_activity_reconstruction.csv",
                 "outputs/pakemis_brick_coal_alternatives.csv",
                 "outputs/pakemis_coal_vintage_ledger.csv",
                 "data/coal_booking_policy.csv",
                 # rc63: DECLARED AT LAST. This phase has read the sulfur register and the
                 # observations beside it since item 3 (build_industrial_coal_decision.py
                 # SULFUR_REGISTER / OBSERVATIONS / GRADE_MIX) and declared neither, so
                 # --changed would skip the phase that writes the adoption verdict whenever only
                 # the sulfur evidence moved - which is exactly when that verdict changes.
                 "data/activity/industry/fuel_sulfur_evidence.csv",
                 "data/activity/industry/fuel_sulfur_observations.csv",
                 "data/activity/industry/furnace_oil_grade_mix.csv",)),
    # rc60: the two tables that answer "is the Lahore SO2 decline a fact about Lahore".
    # The first decomposes the published change into the channels that made it and closes
    # exactly on it; the second sets the same district polygon against EDGAR's own 0.1 degree
    # gridmaps, with a like-for-like national self-check. Both are comparisons and diagnoses:
    # the registers are held byte-identical across each by test, and no number moves.
    # rc60 Package 4: the grid-plant geography this project held but never read, and what it
    # costs Lahore. The ingest is deterministic and --check-able; the register enters no total.
    Phase("Power plant workbooks", "scripts/ingest_power_plant_workbooks.py", False,
          writes=("data/activity/power/grid_plant_district.csv",
                  "data/activity/power/grid_monthly_workbook.csv",
                  "data/activity/power/workbook_emissions_crosscheck.csv",),
          reads=("data/adm2_canonical.csv",
                 "data/activity/power/plant_coordinates.csv",)),
    Phase("Lahore power register", "scripts/build_lahore_power_register.py", False,
          writes=("outputs/pakemis_air_lahore_power_register.csv",),
          reads=("data/activity/power/grid_plant_district.csv",
                 "data/activity/power/workbook_emissions_crosscheck.csv",
                 "data/activity/power/generation_monthly.csv",
                 "data/activity/power/plant_heat_rates.csv",
                 "data/activity/power/plant_name_crosswalk.csv",
                 "data/activity/industry/fuel_sulfur_evidence.csv",)),
    Phase("Lahore SO2 attribution", "scripts/build_air_lahore_so2_attribution.py", False,
          writes=("outputs/pakemis_air_lahore_so2_attribution.csv",),
          reads=("outputs/pakemis_air_lahore_by_year.csv",
                 "outputs/pakemis_air_spatial_support_by_year.csv",
                 "outputs/pakemis_adm2_stream_by_year.csv",
                 "outputs/pakemis_kiln_frame_adm2_by_type.csv",
                 "outputs/pakemis_brick_coal_alternatives.csv",
                 "data/air_source_classes.csv",
                 "data/activity/transport/fuel_sulfur_by_year.csv",)),
    Phase("Lahore SO2 vs EDGAR gridmaps", "scripts/build_air_lahore_external_comparison.py", False,
          writes=("outputs/pakemis_air_lahore_external_comparison.csv",),
          reads=("outputs/pakemis_air_lahore_by_year.csv",
                 "data/activity/industry/edgar_pak_industry_ap_series.csv",)),
    # The same comparison at ADM1, for all five provincial labels and the national sum. The
    # national SO2 ratio is 0.96 and the provincial ones span 0.21 to 2.06, so this is the row
    # that stops a cancelling national agreement from reading as a spatial result.
    Phase("Provincial SO2 vs EDGAR gridmaps",
          "scripts/build_air_provincial_external_comparison.py", False,
          writes=("outputs/pakemis_air_provincial_external_comparison.csv",),
          reads=("outputs/pakemis_air_adm1_by_year.csv",
                 "outputs/power_air_screening_fy2015_16_fy2024_25.csv",
                 "data/activity/industry/edgar_pak_industry_ap_series.csv",)),
    # Which located stations the 0.05 degree province raster misplaces, and how much
    # generation they carry. Reads the coordinate tables and the grid, writes no correction:
    # province and district are one decision in pkinv.core.gis.grid, so a relabel would break
    # the ADM1 == ADM2 + outside + unallocated identity spatial_by_year asserts.
    # Verifies the coal-energy adjudication's own refutation on every basis that could
    # rescue the reference, so it must run after the Power phase writes that file.
    # Reads the atomic product to attach live-component counts to each crosswalk rule, so it
    # runs after it; the registry it publishes is an input that nothing generates.
    Phase("Category crosswalk", "pkinv.report.published_crosswalk", False,
          writes=("outputs/pakemis_category_crosswalk.csv",),
          reads=("data/category_crosswalk.csv",
                 "outputs/pakemis_atomic_annual.csv",)),
    # What the power re-base would do to the industrial column. Reads the configurations and
    # the allocation identity, so it runs after both.
    # What the coal re-base moved and what caused it, per year. Reads the configurations, the
    # booking table, the legacy axis in the structural trajectories and the national series, so
    # it runs after all four. It books nothing: it measures a pin move that already happened.
    Phase("Power coal re-base ledger", "pkinv.sectors.power.rebase_ledger", False,
          writes=("outputs/pakemis_power_coal_rebase_ledger.csv",),
          reads=("outputs/pakemis_power_coal_configurations.csv",
                 "outputs/pakemis_structural_trajectories.csv",
                 "outputs/pakemis_national_series.csv",
                 "data/activity/power/coal_energy_booking.csv")),
    Phase("Coal sector reallocation", "pkinv.sectors.industry.coal_reallocation", False,
          writes=("outputs/pakemis_coal_sector_reallocation.csv",
                  "outputs/pakemis_coal_allocation_cases.csv"),
          reads=("outputs/pakemis_power_coal_configurations.csv",
                 "outputs/pakemis_coal_allocation_identity.csv",
                 "outputs/pakemis_ghg_configuration_atoms.csv",
                 "outputs/pakemis_brick_kiln_fleet_by_year.csv",
                 "data/activity/power/generation_by_fuel.csv",
                 "data/activity/industry/coal_supply.csv",
                 "data/activity/industry/coal_by_consumer.csv",)),
    # rc69: the year-on-year coal change per species, split into supply balance, allocation
    # seam, consumer split, source vintage and factor (the review's latest-year SO2 question).
    Phase("Coal change decomposition", "pkinv.sectors.industry.coal_change_decomposition", False,
          writes=("outputs/pakemis_coal_change_decomposition.csv",),
          reads=("outputs/pakemis_coal_sector_reallocation.csv",
                 "outputs/pakemis_air_atomic_annual.csv",
                 "data/activity/industry/coal_by_sector_vintages.csv")),
    Phase("Air structural sensitivities", "pkinv.report.air_sensitivities", False,
          writes=("outputs/pakemis_air_structural_sensitivities.csv",
                  "outputs/pakemis_nitrogen_partition_sensitivity.csv",
                  "outputs/pakemis_nitrogen_no_pathways.csv"),
          reads=("outputs/pakemis_air_atomic_annual.csv",
                 "outputs/pakemis_ghg_configuration_atoms.csv",
                 "outputs/pakemis_coal_allocation_cases.csv")),
    Phase("Power reference audit", "pkinv.sectors.power.reference_audit", False,
          writes=("outputs/pakemis_power_reference_audit.csv",),
          reads=("data/activity/power/fuel_consumed.csv",
                 "data/activity/power/generation_by_fuel.csv",
                 "data/activity/industry/coal_by_consumer.csv",
                 "data/activity/industry/coal_supply.csv",
                 "outputs/pakemis_power_coal_energy_adjudication.csv",)),
    Phase("Power province boundary audit",
          "scripts/build_power_province_boundary_audit.py", False,
          writes=("outputs/pakemis_power_province_boundary_audit.csv",),
          reads=("data/activity/power/plant_coordinates.csv",
                 "data/activity/power/coal_plant_coordinates.csv",
                 "data/activity/power/gas_plant_coordinates.csv",
                 "data/activity/power/plant_fuel_ledger.csv",
                 "data/adm2_canonical.csv",)),
    # (the 0.1 degree cell x polygon weights are a derived cache the builder makes on first run,
    # like data/gis/adm2_intersections_267x340.csv - not a tracked input)
    # rc55 preparation: the conditional alternatives an external reconstruction computed, rebuilt on
    # this release's own factor chain and clinker ledger. Every row is a SCENARIO - none replaces the
    # reported series and the power-coal discrepancy stays unallocated. Runs after the atoms and the
    # cement reconstruction it reads.
    Phase("Industrial coal scenarios", "scripts/build_industrial_coal_scenarios.py", False,
          writes=("outputs/pakemis_industrial_coal_scenarios.csv",),
          reads=("outputs/pakemis_atomic_annual.csv",
                 "outputs/industry_coal_reconciliation.csv",
                 "outputs/pakemis_cement_kiln_coal_reconstruction.csv",
                 "data/activity/industry/coal_by_consumer.csv",
                 "data/emission_factors.csv",
                 "data/stream_reporting_sector.csv",)),
    # rc53 Wave A3: where the 1.A.2 decline comes from - activity, source revision, classification,
    # coverage or calculation assumption, one row per (stream, channel), with only the booked rows
    # summing to the published change. Reads the atoms and the bridge, so it runs after both.
    Phase("Industrial change attribution", "scripts/build_industrial_change_attribution.py", False,
          writes=("outputs/pakemis_industrial_change_attribution.csv",),
          reads=("outputs/pakemis_atomic_annual.csv",
                 "outputs/pakemis_industrial_coal_bridge.csv",
                 "outputs/pakemis_coal_vintage_ledger.csv",
                 "outputs/industry_captive_screening_2024.csv",
                 "data/activity/industry/coal_by_sector_vintages.csv",
                 "data/coal_booking_policy.csv",)),
    # Wave B2/B4/B5/B6 of the boundary program: the categories outside the reference as NINE-YEAR
    # series (the back-cast the boundary rule demands before any may enter an aggregate) - ammonia
    # and the nitric pair on NFDC production; soda ash (NA in IPPU for a Solvay country), steel
    # Tier 1, lubricants Tier 1 on OCAC's non-energy sales, industrial wastewater as a band.
    Phase("Ammonia and nitric acid series", "scripts/build_ammonia_nitric_series.py", False,
          writes=("outputs/pakemis_ammonia_nitric_series.csv",),
          reads=("data/nfdc/nfdc_production_by_product_series.csv",
                 "data/emission_factors.csv", "data/ippu_params.csv",
                 "data/activity/ippu/chemical_plant_activity.csv",)),
    # rc67: every delivered gas stream by fiscal year - the kind of flow it is, whether the
    # post-meter leak factor rides it, and which category books its carbon. It reads the class
    # series and the ammonia series above, and refuses to write unless every year's streams
    # sum to the regulator's printed consumption and to the base the fugitives engine charges.
    Phase("Gas-flow crosswalk", "pkinv.report.gas_flow_crosswalk", True,
          writes=("outputs/pakemis_gas_flow_crosswalk.csv",),
          reads=("outputs/ogra_gas_class_series.csv",
                 "outputs/pakemis_ammonia_nitric_series.csv",
                 "data/activity/fugitives/fertilizer_gas_class.csv",
                 "data/activity/fugitives/ogra_sector_gas_2021_2023.csv",
                 "data/activity/fugitives/infrastructure_history_2015_21.csv",
                 "data/activity/fugitives/gas_flow_controls_2021_24.csv",
                 "data/activity/fugitives/anchor_activity.csv",
                 "data/nfdc/afr2025_fertilizer_gas_monthly.csv",
                 "data/fugitives_ipcc2019_factors.csv", "data/fugitives_params.csv",
                 "data/periods.csv")),
    # Wave B3: the household HFC equipment bank as a band per year from the first stock indicator
    # held (HIES ownership) - a FLOOR on the bank, the stock-side cross-check of the supply lanes.
    Phase("HFC household bank series", "scripts/build_hfc_bank_series.py", False,
          writes=("outputs/pakemis_hfc_bank_series.csv",),
          reads=("data/activity/ippu/hies_appliance_ownership.csv",)),
    Phase("Industrial screening series", "scripts/build_industrial_screening_series.py", False,
          writes=("outputs/pakemis_industrial_screening_series.csv",),
          reads=("data/activity/monthly/pbs_qim_month_item.csv",
                 "data/activity/industry/ocac_non_energy_sectoral.csv",
                 "data/ippu_params.csv",)),
    # Wave A of the boundary program: the engine's industrial series against EDGAR's for all
    # matched fiscal periods at the fiscal blend - a diagnostic of SHAPE the ledger carries per
    # period (never a residual). The ingest is extracted from the held booklet by
    # scripts/extract_edgar_industry_series.py.
    Phase("Industry vs EDGAR divergence", "scripts/build_industry_edgar_divergence.py", False,
          writes=("outputs/pakemis_industry_edgar_divergence.csv",),
          reads=("outputs/semantic/fact_annual.csv",
                 "data/activity/industry/edgar_pak_industry_series.csv",)),
    Phase("Industrial boundary ledger", "scripts/build_industry_boundary_ledger.py",
          False,
          writes=("outputs/pakemis_industry_boundary_ledger.csv",),
          reads=("outputs/semantic/fact_annual.csv",
                 "outputs/pakemis_industry_edgar_divergence.csv",
                 "outputs/industry_solid_screenings_2024.csv",
                 "outputs/industry_captive_screening_2024.csv",
                 "outputs/ippu_chemicals_screening_2024.csv",
                 "outputs/national_benchmark_comparison.csv",
                 "outputs/unsd_industry_combustion_control.csv",)),
    # v1.0.0 Wave 4: the national manuscript's tables and figures are STORED QUERIES against
    # the semantic release (paper_national/queries/paper_artefacts.csv) - nothing numerical
    # is computed outside pakemis_query, and every printed number is an envelope's display
    # string with a receipt. The registry is a held input (it is edited by hand, like data/).
    # The PNGs it draws go to outputs/paper_figures/ (outputs/figures/ belongs to the
    # figures phase); scripts/sync_figures.py copies them into paper_national/figures/ as it
    # does every other figure, and the script also copies its own PNGs there so `make
    # national` alone leaves the manuscript current.
    # AFTER the semantic release, not before it. product_catalog.main() refuses when a
    # catalogued product has no artifact on disk, and the semantic tables ARE catalogued
    # (semantic.release, semantic.facts, semantic.dimensions, added in Wave 4). Running it
    # first passes on a warm tree, where last build's files are still there, and fails on the
    # only tree that matters - a reproduction from an empty outputs/, which is what the
    # rc43 validation package's reproduce.sh found. A phase that verifies artifacts exist
    # cannot precede the phase that writes them.
    # rc41: the validation catalog and the product catalog write products the inventory
    # and the deposit manifest list and the product facts read, so they precede all three.
    Phase("Product catalog", "pkinv.report.product_catalog", True,
          writes=("outputs/pakemis_product_catalog.csv",
                  "paper_national/versions/v1/sections/generated_products.tex",),
          reads=("outputs/pakemis_monthly_coverage_summary.csv",
                 "outputs/semantic/",)),

    Phase("Derivation chains", "pkinv.report.derivation_chain", True,
          # every file the module writes, ALL ten sectors: an under-enumerated
          # writes tuple leaks the missing names into the sector runners'
          # written_by_other_phases subtraction, and their run manifests then
          # inventory another producer's files - the rc48 package reproduce
          # caught exactly that on the eight undeclared sectors
          writes=("outputs/agriculture_derivation_chain.csv",
                  "outputs/agriculture_activity_factor_ledger.csv",
                  "outputs/aviation_derivation_chain.csv",
                  "outputs/aviation_activity_factor_ledger.csv",
                  "outputs/fugitives_derivation_chain.csv",
                  "outputs/fugitives_activity_factor_ledger.csv",
                  "outputs/industry_derivation_chain.csv",
                  "outputs/industry_activity_factor_ledger.csv",
                  "outputs/ippu_derivation_chain.csv",
                  "outputs/ippu_activity_factor_ledger.csv",
                  "outputs/power_derivation_chain.csv",
                  "outputs/power_activity_factor_ledger.csv",
                  "outputs/railways_derivation_chain.csv",
                  "outputs/railways_activity_factor_ledger.csv",
                  "outputs/residential_derivation_chain.csv",
                  "outputs/residential_activity_factor_ledger.csv",
                  "outputs/transport_derivation_chain.csv",
                  "outputs/transport_activity_factor_ledger.csv",
                  "outputs/waste_derivation_chain.csv",
                  "outputs/waste_activity_factor_ledger.csv",),
          reads=("outputs/semantic/",
                 "outputs/national_all_sectors.csv",
                 "outputs/national_category_gas.csv",
                 "glob:outputs/*_totals_*.csv",
                 # + the per-sector bridges, ledgers and reconciliations the registry names,
                 # each written by its own sector phase above; data/verification_chain.csv is
                 # the list, and tests/test_derivation_chain.py fails if one goes missing.
                 "data/verification_chain.csv",)),
    # FAOSTAT's managed soils against this inventory's, at the nitrogen FLOWS rather than
    # the total - because the flows agree and the manuscript had attributed the difference
    # to one of them. Placed here because it reads the activity-factor ledger the phase
    # above writes; the EF1 scenario is `held:` because pkinv.eval.sensitivity_table is a
    # Makefile target and no phase writes it.
    Phase("FAOSTAT nitrogen flows",
          "pkinv.sectors.agriculture.faostat_nitrogen_flows", False,
          writes=("outputs/pakemis_faostat_nitrogen_flows.csv",),
          reads=("outputs/agriculture_activity_factor_ledger.csv",
                 "held:outputs/eval/sensitivity.csv",
                 "data/benchmarks.csv",
                 "data/activity/historical/fertilizer_n.csv",
                 "data/activity/historical/livestock_stocks.csv",)),
    # rc53: and it runs AFTER every phase it grades. Its freshness gate compares each cited
    # product's mtime to this build's sentinel, so a product written by a LATER phase still
    # carried the previous build's mtime and failed STALE on any build more than two hours
    # after that product's last hand-run - which is what bit rc52 and rc53. Sitting after the
    # products and before its three consumers satisfies both constraints.
    # 2026-10-07: and the hole reopened, because that was prose and not a check. FAOSTAT
    # nitrogen flows was added BELOW this phase and is wired in the catalog, so a build
    # whose only stale wired product was that one failed STALE on a file it was about to
    # write. The phase now sits after the last wired producer, and
    # tests/test_validation_catalog.py asserts that position instead of describing it.
    Phase("Validation catalog + scorecard", "pkinv.report.validation_catalog", True,
          writes=("outputs/pakemis_validation_scorecard.csv",
                  "outputs/pakemis_validation_catalog.csv",
                  "outputs/pakemis_validation_sector_scorecard.csv"),
          reads=("data/validation_catalog.csv",
                 "outputs/national_totals_2024.csv",)),
    # v3: the catalogue regrouped by what each comparison can establish (the supplement's
    # five-class table is generated from the summary).
    Phase("Validation five classes", "pkinv.report.validation_five_classes", True,
          writes=("outputs/pakemis_validation_five_classes.csv",
                  "outputs/pakemis_validation_five_classes_summary.csv"),
          reads=("outputs/pakemis_validation_catalog.csv",)),
    # v3: the terms of every external comparison in one lookup (source, gas metric, year
    # basis, units, boundary, independence), from the catalog and the BTR table.
    # rc69: the measured validation, one row per check, for the paper's compact table
    Phase("Measured validation", "pkinv.report.validation_measured", False,
          writes=("outputs/pakemis_validation_measured.csv",),
          # reads=None, deliberately: besides the held parse summaries and the closure
          # products it reads the rc68 reproduction record under docs/reproduction/ and the
          # release test record, which are committed records no phase writes and no read
          # form declares; an unaudited phase takes the conservative input boundary.
          reads=None),
    Phase("Comparison crosswalk", "pkinv.report.comparison_crosswalk", True,
          writes=("outputs/pakemis_comparison_crosswalk.csv",),
          reads=("outputs/pakemis_validation_catalog.csv",
                 "outputs/pakemis_btr_comparison.csv")),
    Phase("Sector technical-note facts", "pkinv.report.air_sector_facts", True,
          writes=("outputs/pakemis_sector_note_facts.csv",) + tuple(
              "papers/%s/generated/%s.tex" % (sector, name)
              for sector in ("agriculture", "power", "residential")
              for name in ("integrated_air_facts", "integrated_air_table", "integrated_ghg_table")),
          reads=("outputs/pakemis_atomic_annual.csv",
                 "outputs/pakemis_air_annual_fy2015_16_fy2024_25.csv",)),
    Phase("Manuscript figures", "pkinv.report.figures", False,
          writes=("outputs/figures/",)),
    # THE GRIDDED FIGURES WERE IN NO PHASE. A version bump rebuilt the papers and left
    # fig_ghg_grid.pdf, its evidence companion and their provenance behind: at rc61 the
    # provenance JSON said rc59, the figure PDFs and the \input TeX said rc60, the cover
    # said rc61. The script reads pkinv.__version__ correctly; nothing ran it. Declared here
    # so the figures regenerate with the release, and tests/test_v3_documents.py holds the
    # artefacts to the engine's version.
    # THE OTHER FIVE FIGURES WERE IN NO PHASE EITHER (rc63). The plot tables, the two tables
    # generated from them and figures 1, 2, 3, 7 and 8 were run by hand, so a re-base could move
    # a number and leave the figure that prints it behind. One driver, in dependency order.
    Phase("Manuscript figures, v3 (tables and charts)", "scripts/build_manuscript_figures.py", False,
          writes=("paper_national/figures/f01_construction.pdf",
                  "paper_national/figures/f02_inventory.pdf",
                  "paper_national/figures/f03_evidence_uncertainty.pdf",
                  "paper_national/figures/f07_btr_ratios.pdf",
                  "paper_national/figures/f08_managed_soils.pdf",
                  "paper_national/figures/rewrite_inputs/data/",
                  "paper_national/figures/rewrite_inputs/previews/",
                  "paper_national/versions/v3/generated/tab_closure.tex",
                  "paper_national/versions/v3/generated/tab_btr_qualified.tex"),
          reads=("outputs/national_all_sectors.csv",
                 "outputs/pakemis_national_series.csv",
                 "outputs/national_uncertainty_montecarlo.csv",
                 "outputs/pakemis_trend_uncertainty.csv",
                 "outputs/temporal_profile.csv",
                 "outputs/pakemis_btr_comparison.csv",
                 "outputs/pakemis_faostat_nitrogen_flows.csv",
                 # held: pkinv.eval.sensitivity_table is a hand-run evaluation, as it is for the
                 # nitrogen-flow phase above
                 "held:outputs/eval/sensitivity.csv",
                 "outputs/pakemis_air_provincial_external_comparison.csv",
                 "outputs/pakemis_stream_support_ledger.csv",
                 "outputs/pakemis_spatial_unallocated.csv")),
    Phase("Gridded figures", "scripts/make_fig_ghg_grid.py", False,
          writes=("paper_national/figures/f04_gas_maps.pdf",
                  "paper_national/figures/f05_spatial_evidence.pdf",
                  "paper_national/figures/f06_proxy_concentration.pdf",
                  "paper_national/figures/fig_ghg_grid_provenance.json",
                  "paper_national/figures/fig_ghg_grid_provenance.tex",
                  "paper_national/figures/fig_ghg_grid_cells_fy2023_24.csv",
                  "paper_national/figures/fig_ghg_grid_evidence.csv",
                  "paper_national/figures/fig_ghg_grid_proxy.csv",
                  "paper_national/figures/fig_ghg_grid_proxy_surfaces.csv",
                  "paper_national/figures/fig_ghg_grid_concentration.csv"),
          reads=("outputs/pakemis_grid_0p05_annual_ref_fy2015_16_fy2024_25.nc",
                 "outputs/pakemis_stream_support_ledger.csv",
                 "outputs/pakemis_spatial_weights_by_year.csv",
                 "outputs/pakemis_spatial_unallocated_by_year.csv",
                 "data/shared/gis/PAK_ADM1.geojson",
                 "data/shared/gis/BOUNDARY_SOURCES.json",
                 "data/shared/gis/adm2_canonical.csv")),
    Phase("Sync paper figures", "scripts/sync_figures.py", True,
          writes=("paper_national/figures/",), idempotent=True),
    Phase("Integrated GHG and air manuscript figures", "scripts/build_integrated_figures.py", False,
          writes=tuple("paper_national/figures/" + name + ".pdf" for name in (
                     "f09_integrated_composition", "f10_integrated_trends", "f11_integrated_maps",
                     "f12_air_sensitivity", "f13_air_evaluation")) +
                 tuple("paper_national/figures/integrated_inputs/" + name + ".csv" for name in (
                     "f09_integrated_composition", "f10_integrated_trends", "f11_integrated_maps",
                     "f11_integrated_map_scales", "f12_air_sensitivity", "f13_air_evaluation", "integrated_facts")) +
                 tuple("paper_national/figures/integrated_inputs/previews/" + name + ".png" for name in (
                     "f09_integrated_composition", "f10_integrated_trends", "f11_integrated_maps",
                     "f12_air_sensitivity", "f13_air_evaluation")) +
                 ("paper_national/versions/v3/generated/integrated_facts.tex",),
          reads=("outputs/pakemis_atomic_annual.csv", "outputs/pakemis_air_annual_fy2015_16_fy2024_25.csv",
                 "outputs/pakemis_ghg_conditional_uncertainty.csv", "outputs/pakemis_air_conditional_uncertainty.csv",
                 "outputs/pakemis_nitrogen_partition_sensitivity.csv",
                 "outputs/pakemis_coal_change_decomposition.csv",
                 "outputs/pakemis_air_source_coverage.csv", "outputs/pakemis_air_coverage_matrix.csv",
                 "outputs/pakemis_air_power_omission.csv",
                 "outputs/pakemis_road_technology_case.csv",
                 "outputs/pakemis_air_structural_sensitivities.csv", "outputs/pakemis_industry_air_edgar_comparison.csv",
                 "outputs/pakemis_air_htap_comparison.csv", "outputs/pakemis_grid_0p05_annual_ref_fy2015_16_fy2024_25.nc",
                 "outputs/pakemis_air_grid_0p05_annual_s_tan_fy2015_16_fy2024_25.nc",
                 "held:src/pkinv/report/manuscript_style.py"), requires=("matplotlib", "numpy", "netCDF4")),
    Phase("Integrated manuscript figure verification", "scripts/verify_manuscript_figures.py", True,
          writes=("paper_national/figures/integrated_inputs/figure_value_checks.csv",),
          reads=("paper_national/figures/integrated_inputs/integrated_facts.csv",
                 "outputs/pakemis_atomic_annual.csv", "outputs/pakemis_air_annual_fy2015_16_fy2024_25.csv",
                 "outputs/pakemis_ghg_conditional_uncertainty.csv", "outputs/pakemis_air_conditional_uncertainty.csv",
                 "outputs/pakemis_nitrogen_partition_sensitivity.csv",
                 "outputs/pakemis_air_structural_sensitivities.csv", "outputs/pakemis_air_htap_comparison.csv",
                 "outputs/pakemis_industry_air_edgar_comparison.csv",
                 "outputs/pakemis_grid_0p05_annual_ref_fy2015_16_fy2024_25.nc",
                 "outputs/pakemis_air_grid_0p05_annual_s_tan_fy2015_16_fy2024_25.nc")),
    Phase("Validation table", "scripts/make_validation_table.py", False,
          writes=("paper_national/versions/v3/generated/tab_validation_measured.tex",),
          reads=("outputs/pakemis_validation_measured.csv",)),
    Phase("Paper artefacts (stored queries)", "scripts/make_paper_artefacts.py", True,
          writes=("outputs/pakemis_paper_artefact_hashes.csv",
                  # rc69: outputs/paper_figure_data/ and outputs/paper_figures/ are no longer
                  # declared: rc68 retired the four stored-query figures, the registry names no
                  # figure, and git keeps no empty folder, so a fresh clone has neither
                  "paper_national/versions/v1/sections/gen_tab_categorygas.tex",
                  "paper_national/versions/v1/sections/gen_tab_completeness.tex"),
          # + the registry paper_national/queries/paper_artefacts.csv (prose-side, not a product)
          reads=("outputs/semantic/",)),
    # THE DERIVATION CHAINS ARE A BUILD PHASE, not a hand-run product, because they are pure
    # derivations of files this build already wrote: the chain re-keys shipped tables onto one
    # schema and the ledger joins dim_stream's parameter ids to their values. They shipped
    # committed with no producer in this definition, and the rc48 package build is what found
    # it - reproduce.sh rebuilt a tree without them and all four receipts diverged (artifact
    # inventory 761 rows against 740). A committed product no build definition writes is
    # exactly what data/held_products.csv exists to declare, and these do not qualify: nothing
    # about them needs a document the build lacks.
    #
    # AFTER the semantic release (the ledger reads dim_stream and fact_annual) and after the
    # national tables; BEFORE the artifact inventory, which sizes every file under outputs/.
    Phase("Dashboard", "pkinv.report.dashboard", False,
          writes=("outputs/dashboard.html",)),
    # rc41: the artifact inventory records the size of EVERY file under outputs/ and the
    # deposit manifest enumerates the products, so both must run after the last phase
    # that writes one - the figures and the dashboard included - and before the product
    # facts that read them. They ran before the cube, the ensemble, the figures and
    # the dashboard, complete only because the previous release's files were on disk;
    # an empty outputs/ made both differ. The release-run records they list
    # (pakemis_test_run.json, pakemis_paper_hashes.csv) are held products.
    Phase("Release numerical changes", "scripts/build_release_change_summary.py", True,
          writes=("outputs/pakemis_release_change_summary.csv",),
          reads=("outputs/pakemis_atomic_annual.csv", "outputs/pakemis_air_atomic_annual.csv",
                 "data/baselines/rc67_integrated_campaign/outputs/pakemis_atomic_annual.csv",
                 "data/baselines/rc67_integrated_campaign/outputs/pakemis_air_atomic_annual.csv")),
    Phase("Artifact inventory", "pkinv.report.artifact_inventory", True,
          writes=("outputs/pakemis_artifact_inventory.csv",)),
    # THE SUPPLEMENT'S PRODUCT LIST WAS IN NO PHASE (rc69): `make figures-v3` ran it by hand,
    # after the four figure stages the registry already held. It reads the artifact
    # inventory's roles and every product's leading comment, so it follows that phase.
    Phase("Supplement product list", "scripts/make_v3_product_list.py", False,
          writes=("paper_national/versions/v3/products_appendix.tex",)),
    Phase("Product coverage", "scripts/make_product_coverage.py", True,
          writes=("outputs/pakemis_product_coverage.csv",
                  "paper_national/versions/v1/sections/generated_coverage.tex"),
          reads=("glob:outputs/*provincial*.csv",)),
    Phase("Deposit manifest", "pkinv.report.deposit_manifest", True,
          writes=("outputs/pakemis_deposit_manifest.csv",
                  "outputs/pakemis_primary_geography_licence_audit.csv",
                  "outputs/pakemis_source_register.csv",),
          reads=("data/raw_manifest.csv", "data/source_documents.csv",
                 "data/manifests/source_manifest.csv", "data/not_retained_register.csv",
                 "data/canonical_tables.csv", "data/public_documents.csv",
                 "data/extracted/unfccc/")),
    # Product facts moved here in rc34: it also reads the cube's unallocated
    # ledger (pakemis_spatial_unallocated.csv), which the Gridded monthly cube
    # writes, so running it before the cube published the PREVIOUS build's
    # figure - the same class as the artifact-count regression the comment
    # below records. check_order() now refuses that ordering.
    # LAST OF THE THREE, and the ordering is load-bearing. product_facts READS the artefact
    # inventory and the deposit manifest, and it used to run BEFORE both - so `artifact_count`
    # published the PREVIOUS run's number: 409 against an inventory holding 411. The clean-room
    # rebuild found it, which is what a clean-room rebuild is for.
    # Which files the manuscripts cite that a reader could not open. It runs AFTER the
    # deposit manifest, so both reads are ordinary. The manifest does hash this file back -
    # it is a pakemis_* product - but that resolves in one pass and moves nothing: the only
    # path this audit adds to the manifest is its own, and no manuscript cites it, so its
    # rows are identical on the next run.
    Phase("Citation deposit audit", "scripts/build_citation_deposit_audit.py", False,
          writes=("outputs/pakemis_citation_deposit_audit.csv",),
          # prior: ON THE THREE GENERATED FRAGMENTS, because the dependency is a CYCLE and
          # no ordering satisfies it:
          #   this audit            reads the v1 generated fragments (it scans the
          #                         manuscript for citations, and they are part of it)
          #   Availability fragments  are GENERATED FROM outputs/release_manifest.json
          #                         (make_availability.py's own header says so), so they
          #                         must follow the manifest
          #   Release manifest      HASHES outputs/pakemis_citation_deposit_audit.csv, so it
          #                         must follow this audit
          # audit -> fragments -> manifest -> audit. Exactly the shape release_fixpoint.py
          # documents for the paper hashes, and it is broken at the same place: the edge
          # whose content does not move. The fragments carry the deposit identifiers, and a
          # release candidate has none - the DOI and the review link are the two items the
          # availability statement declares outstanding - so what this audit reads from them
          # is stable across the mint. If a DOI is ever minted, the fragments change and this
          # audit is one build behind until the next run; that is the cost, and it is stated
          # rather than hidden behind an undeclared read of last run's bytes.
          reads=("outputs/pakemis_deposit_manifest.csv",
                 "outputs/pakemis_artifact_inventory.csv",
                 "prior:paper_national/versions/v1/generated/abstract_doi.tex",
                 "prior:paper_national/versions/v1/generated/availability.tex",
                 "prior:paper_national/versions/v1/generated/claim_matrix.tex",)),
    Phase("Product facts registry", "pkinv.report.product_facts", True,
          writes=("outputs/pakemis_product_facts.csv",),
          reads=("outputs/pakemis_annual_fy2015_16_fy2024_25.csv",
                 "outputs/pakemis_monthly_fy2015_16_fy2024_25.csv",
                 "outputs/pakemis_artifact_inventory.csv",
                 "outputs/pakemis_agriculture_fiscal_series.csv",
                 "outputs/pakemis_agriculture_basis_change.csv",
                 "outputs/pakemis_agriculture_crop_calendar.csv",
                 "outputs/pakemis_trend_uncertainty.csv",
                 "outputs/pakemis_longitudinal_uncertainty.csv",
                 "outputs/pakemis_deposit_manifest.csv",
                 "outputs/pakemis_source_register.csv",
                 "outputs/pakemis_source_streams.csv",
                 "outputs/pakemis_spatial_unallocated.csv",
                 "outputs/national_axis_register.csv",
                 "outputs/national_configurations.csv",
                 "outputs/fugitives_structural_factorial_2024.csv",
                 "outputs/fugitives_conditional_intervals_2024.csv",)),
    # v1.0.0 Wave 4: the claim matrix resolves every headline claim of the national paper
    # against the semantic release, the product facts and the shipped cells it cites, so it
    # runs after the facts registry (which the deposit manifest and the inventory precede) and
    # before the release manifest, which hashes its CSV as a pakemis_*.csv product. The section
    # files it reads are hand-written prose (held:). The paper-artefacts phase, when present,
    # sits after "Semantic release" and therefore before this one.
    Phase("Claim matrix", "scripts/make_claim_matrix.py", True,
          writes=("outputs/pakemis_claim_matrix.csv",
                  "outputs/pakemis_claim_matrix.md",
                  "paper_national/versions/v1/generated/claim_matrix.tex"),
          reads=("outputs/semantic/",
                 "data/claim_matrix.csv",
                 "data/claims_registry.csv",
                 "outputs/pakemis_product_facts.csv",
                 "paper_national/versions/v3/generated/integrated_facts.tex",
                 "outputs/pakemis_ghg_configuration_atoms.csv",
                 "outputs/pakemis_air_annual_fy2015_16_fy2024_25.csv",
                 "outputs/pakemis_ghg_conditional_uncertainty.csv",
                 "outputs/pakemis_air_conditional_uncertainty.csv",
                 "outputs/pakemis_air_structural_sensitivities.csv",
                 "outputs/pakemis_nitrogen_partition_sensitivity.csv",
                 "held:paper_national/versions/v3/paper.tex")),
    # The catalog audits every validation product for freshness, so it must be
    # nearly LAST - after the benchmarks, the grid cube and the ensemble have
    # written the products it gates (it ran mid-list once and correctly failed
    # itself on a product a later phase was about to write).
    # The product catalog was in NO build definition - the README generator
    # imported it in-process and nothing ever wrote its file - so the shipped
    # catalog and the supplement's generated product table went stale when the
    # reference-year flat share moved (53.3 -> 52.8 per cent); the rc35 writer
    # sweep's byte gate found it. It stats every product's artifact, so it runs
    # after the last producer.
    Phase("Release manifest", "pkinv.report.release_manifest", True,
          writes=("outputs/release_manifest.json",)),
    # The ESSD availability statements print the manifest's version, identifiers and
    # licences, so they are rendered from it, after it (v1.0.0 program, Wave 4).
    Phase("Availability fragments", "scripts/make_availability.py", True,
          writes=("paper_national/versions/v1/generated/availability.tex",
                  "paper_national/versions/v1/generated/abstract_doi.tex",
                  "paper_common/generated_availability_tn.tex"),
          reads=("outputs/release_manifest.json",)),

]


def _with_canonical_prerequisites(phases):
    """Stage source-derived inputs before the canonical snapshot and its consumers.

    Source producers and the pure period registries used to be interleaved with
    reporting phases, which left earlier consumers reading previous-run data.
    """
    import csv
    from pkinv.build_support import physical_paths
    registry_path = physical_paths("data/canonical_tables.csv", ROOT)[0]
    registry_file = os.path.join(ROOT, registry_path)
    if not os.path.exists(registry_file):
        return phases
    with open(registry_file, encoding="utf-8", newline="") as handle:
        tables = list(csv.DictReader(handle))
        inputs = tuple(sorted({row.get("storage_path") or row["source_path"] for row in tables}))
    compatibility = Phase(
        "Compatibility input views", "pkinv.activity.compatibility_views", True,
        writes=tuple("data/activity/" + path for path in (
            "aviation/fuel_controls_2023_24.csv", "fugitives/anchor_activity_2021_23.csv",
            "fugitives/anchor_activity_2023_24.csv", "residential/fuel_supply.csv",
            "residential/fuel_supply_history.csv", "ippu/company_clinker_2023_24.csv",
            "ippu/company_clinker_series.csv", "ippu/cement_producer_census_2023_24.csv")),
        reads=tuple("data/activity/" + path for path in (
            "aviation/fuel_sales.csv", "fugitives/anchor_activity.csv",
            "residential/fuel_supply_observations.csv", "residential/fuel_supply_annotations.csv",
            "ippu/company_production.csv", "ippu/company_production_evidence.csv",
            "ippu/company_roster.csv")) + ("data/compatibility_view_formats.json",),
        idempotent=True, audited=True)
    coal_booking = Phase(
        "Power station coal booking", "pkinv.sectors.power.coal_booking", True,
        writes=("data/activity/power/coal_energy_booking.csv",
                "data/activity/power/coal_rank_account.csv"),
        reads=("data/activity/power/plant_fuel_year_controls.csv",
               "data/activity/power/coal_plant_fuel_back_years.csv",
               "data/activity/power/generation_by_fuel.csv",
               "data/activity/power/plant_fuel_2024_25.csv",
               "data/activity/power/fuel_consumed.csv"))
    extension = Phase(
        "Fiscal extension source tables", "scripts/ingest_release_extension.py", True,
        writes=("data/activity/agriculture/es_fiscal_series.csv", "data/activity/crops_2024.csv",
                "data/activity/monthly/pbs_qim_month_item.csv", "data/activity/ippu/national_activity.csv",
                "data/activity/power/plant_fuel_ledger.csv", "data/activity/power/fuel_consumed.csv",
                "data/activity/power/generation_by_fuel.csv", "data/activity/power/bagasse_generation.csv",
                "data/activity/power/captive_gas.csv", "data/activity/fugitives/fertilizer_gas_class.csv",
                "data/activity/aviation/movements_airport.csv", "data/activity/aviation/fuel_sales.csv",
                "outputs/pakemis_power_extension_controls.csv", "outputs/pakemis_extension_activity_revisions.csv",
                "outputs/pakemis_fy2025_26_provisional_activity.csv", "outputs/pakemis_ocac_extension_revisions.csv",
                "outputs/pakemis_extension_source_controls.csv", "outputs/pakemis_extension_source_availability.csv",
                "outputs/pakemis_fy2025_26_provisional_emissions.csv", "outputs/pakemis_fy2025_26_provisional_monthly.csv"),
        reads=("held:sources/Power Plants/NEPRA State of Industry Report 2025.pdf",
               "data/raw/finance_division/survey_2025_26/", "data/raw/pbs/qim/extension_2026/",
               "data/raw/ocac/extension_2026/", "data/activity/power/plant_fuel_2024_25.csv",
               "data/raw/pcaa/extension_2025/", "data/raw/ogra/state_of_industry/ogra_petroleum_industry_report_2024_25.pdf",
               "data/activity/aviation/airport_aliases.csv", "data/activity/aviation/ocac_annual_sources.csv",
               "held:sources/Aviation/ocac_annual/OCAC_FY2024_25.pdf", "held:scripts/ingest_aviation.py",
               "held:sources/Aviation/2006-2007-apt.pdf", "held:sources/Aviation/2007-2008-apt.pdf",
               "held:sources/Aviation/2008-2009-apt.pdf", "held:sources/Aviation/2009-2010-apt.pdf",
               "held:sources/Aviation/2010-2011-apt.pdf", "held:sources/Aviation/2011-2012-apt.pdf",
               "held:sources/Aviation/2012-2013-apt.pdf", "held:sources/Aviation/2013-2014-apt.pdf",
               "held:sources/Aviation/2014-2015-apt.pdf", "held:sources/Aviation/2015-2016-apt.pdf",
               "held:sources/Aviation/2016-2017-apt.pdf", "held:sources/Aviation/2017-2018-apt.pdf",
               "held:sources/Aviation/2018-2019-apt.pdf", "held:sources/Aviation/2019-2020-apt.pdf",
               "held:sources/Aviation/2020-2021-apt.pdf", "held:sources/Aviation/2021-2022-apt.pdf",
               "held:sources/Aviation/major-traffic-flow-airports-2022-23.pdf",
               "held:sources/Aviation/major-traffic-flow-airports-2023-24.pdf",
               "data/emission_factors.csv", "data/shared/activity/extension/rc67_agricultural_revision_controls.csv"))
    household_weather = Phase(
        "Residential own-year degree-days", "scripts/fetch_hdd.py --offline", True,
        writes=("data/activity/residential/monthly_degree_days.csv",),
        reads=("data/raw/nasa_power/",), idempotent=True)
    phases = [extension, household_weather, coal_booking] + phases
    labels = ("Period registry", "Month registry", "ADM2 reporting units",
              "Brick kiln fleet observations", "Power plant workbooks", "Fiscal extension source tables",
              "Residential own-year degree-days", "Power station coal booking", "Power SO2 admission register")
    by_label = {p.label: p for p in phases}
    canonical = Phase("Canonical activity tables", "pkinv.activity.build", True,
                      writes=tuple(row["path"] for row in tables) +
                             physical_paths("data/canonical/catalog.json", ROOT),
                      reads=(registry_path, "data/canonical_columns.csv") + inputs,
                      idempotent=True, audited=True)
    return [by_label[label] for label in labels] + [compatibility, canonical] + [
        p for p in phases if p.label not in labels]


def _with_spatial_prerequisites(phases):
    """Price allocation uncertainty from the spatial products of this build.

    The Karachi bracket consumes the published fiscal-panel stream surface. Its
    downstream uncertainty tables must therefore follow that surface as well.
    """
    deferred = {"Spatial-allocation brackets", "Joint uncertainty by resolution",
                "Completeness-mass ledger", "Longitudinal uncertainty"}
    after = "Fiscal-panel spatial products (ADM1 and ADM2)"
    result = []
    for phase in phases:
        if phase.label not in deferred:
            result.append(phase)
        if phase.label == after:
            result.extend(p for p in phases if p.label in deferred)
    return result


def _with_asset_paths(phases):
    from pkinv.build_support import physical_paths
    def expanded(paths):
        if paths is None:
            return None
        return tuple(dict.fromkeys(path for declaration in paths
                                   for path in physical_paths(declaration, ROOT)))
    return [replace(phase, reads=expanded(phase.reads), writes=expanded(phase.writes))
            for phase in phases]



# EVERY PHASE DECLARES WHAT KIND OF WORK IT IS (rc69), and the build groups are chosen by
# kind. Until rc68 the development group excluded eleven labels by name, so each figure
# stage added later (the v3 tables and charts, the gridded and integrated figures, their
# verification) entered every `make dev` without anyone deciding it should. Now:
#   science     the inventory itself: sources, engines, national, uncertainty, spatial
#   validation  comparisons, benchmarks and audits that read the science and write evidence
#   manuscript  figures, tables and TeX for the papers, and the dashboard
#   release     the release's bookkeeping: inventories, manifests, deposit, provenance
# `make dev` builds science and validation. Every label is listed under exactly one kind,
# and there is no default: a new phase that is not listed stops the import, so it cannot
# drift into a group by omission (tests/test_build_categories.py holds both directions).
CATEGORIES = {
    "science": (
        "Period registry",
        "Month registry",
        "ADM2 reporting units",
        "Brick kiln fleet observations",
        "Power plant workbooks",
        "Fiscal extension source tables",
        "Residential own-year degree-days",
        "Power station coal booking",
        "Power SO2 admission register",
        "Compatibility input views",
        "Canonical activity tables",
        "Agriculture",
        "Agriculture timeseries (1990-2024)",
        "Agriculture fiscal history",
        "Agriculture Monte Carlo",
        "Agriculture key categories",
        "Agriculture nitrogen ledger",
        "LULUCF (exploratory, outside every total)",
        "Agriculture provincial",
        "Agriculture districts",
        "Agriculture district panel (1990-2024)",
        "Agriculture air pollutants",
        "Agriculture air key categories",
        "Agriculture air uncertainty",
        "Agriculture air time series",
        "Waste",
        "Waste air pollutants",
        "Waste MC draw file",
        "Waste MC alternative draw file",
        "Waste uncertainty",
        "Road transport",
        "Transport provincial shape",
        "Transport air pollutants",
        "Power generation",
        "Power air pollutants",
        "Power grid basis change",
        "Residential fuel",
        "Residential air pollutants",
        "Industrial processes",
        "IPPU metadata",
        "Industrial combustion",
        "HFC species bank",
        "Coal lane reconciliation",
        "Agri reference-panel divergence",
        "ADM2 frame 2022 crosswalk",
        "Fugitive oil and gas",
        "Railways",
        "Railways air pollutants",
        "Aviation fallback study",
        "Aviation reconciliation study",
        "Aviation",
        "Aviation air pollutants",
        "Completeness table",
        "National rollup",
        "National key categories",
        "Fugitives MC draw file",
        "Agriculture uncertainty inputs",
        "National uncertainty",
        "National category ledger",
        "Parameter decomposition",
        "Priority rankings",
        "Dung destination variants",
        "Dung balance",
        "Dung residual ledger",
        "Commercial/institutional audit",
        "National gas closure",
        "Named national configurations",
        "Uncertainty reconciliation",
        "Kiln allocation product",
        "Waste release objects",
        "National axis register",
        "National series",
        "Dung fate by year",
        "Annual product (supported fiscal panel)",
        "Atomic annual table",
        "Forest flux adjudication",
        "Minerals panel screening",
        "F-gas leak-rate adjudication",
        "Cement activity sources and their overlap",
        "Unallocated activity controls",
        "Bridge configurations (declared, unpopulated)",
        "Coverage matrix (year x category x gas x configuration)",
        "National monthly layer",
        "Source-stream ledger",
        "Survey monthly (configuration S)",
        "Temporal profile registry",
        "Monthly layer, supported fiscal panel",
        "Spatial brackets (ADM2)",
        "Temporal decomposition (physics vs ignorance)",
        "Temporal driver registry",
        "Monthly coverage, all 120 months",
        "Flatness crosswalk (TE class vs physics)",
        "Agriculture timing classes + NFDC residual",
        "Monthly data requests (the gap, priced)",
        "Bagasse timing variant",
        "Fertilizer timing variant",
        "Power profile variant",
        "Monthly controls register",
        "CRT crosswalk",
        "Parquet twins",
        "Facility registry",
        "Gridded monthly cube",
        "Cement kiln coal reconstruction",
        "Air annual panel (supported fiscal panel)",
        "Air monthly allocation",
        "GHG conditional uncertainty",
        "Air conditional uncertainty",
        "Air source classes (supported fiscal panel)",
        "Power SO2 admission bridge",
        "Power air-control evidence",
        "Air absence-screening ledger",
        "Air power-stack omission",
        "Brick kiln fleet by year",
        "Coal allocation identity",
        "Kiln frame vectors",
        "Power admission vectors",
        "Fiscal-panel spatial products (ADM1 and ADM2)",
        "Spatial-allocation brackets",
        "Joint uncertainty by resolution",
        "Completeness-mass ledger",
        "Longitudinal uncertainty",
        "EDGAR-aligned 0.1-degree grid",
        "Spatial weight registry (per stream-year)",
        "Air spatial support ledger",
        "Stream-to-support ledger",
        "Power provincial basis by year",
        "Air spatial (all sectors)",
        "Lahore air view",
        "Industry air, calendar 2023",
        "Spatial exceptions + ADM2 nesting",
        "Spatial decomposition (geometry vs ignorance)",
        "Common draw ensemble",
        "Wastewater method comparison",
        "Uncertainty drivers",
        "Power fuel reconciliation",
        "Power coal configurations",
        "Structural trajectories",
        "Activity publication",
        "Semantic release",
        "Enteric BTR bridge",
        "Spatial basis taxonomy",
        "OGRA gas-class series",
        "Coal vintage ledger",
        "Coal source reconciliation",
        "Coal balance",
        "Industrial coal bridge",
        "Brick coal alternatives",
        "Brick activity reconstruction",
        "Industrial coal decision",
        "Lahore power register",
        "Lahore SO2 attribution",
        "Category crosswalk",
        "Power coal re-base ledger",
        "Coal sector reallocation",
        "Coal change decomposition",
        "Air structural sensitivities",
        "Industrial coal scenarios",
        "Industrial change attribution",
        "Ammonia and nitric acid series",
        "Gas-flow crosswalk",
        "HFC household bank series",
        "Industrial screening series",
        "Industrial boundary ledger",
        "Derivation chains",
        "FAOSTAT nitrogen flows",
    ),
    "validation": (
        "Railways ELK crosscheck",
        "Kiln allocation benchmark",
        "GEM asset-census audit",
        "Citation pointer audit",
        "BTR comparison (year-matched)",
        "Rice geography crosscheck",
        "Monthly cross-checks",
        "EDGAR transport comparison",
        "District rice records validation",
        "District records validation (multi)",
        "Livestock district validation (GLW)",
        "Benchmark: spatial allocation",
        "Benchmark: temporal hindcast",
        "Data provenance audit",
        "HTAP air comparison",
        "Road technology case",
        "Power station commissioning check",
        "Industry air vs EDGAR",
        "Pass-2 exit scorecard",
        "UNSD industrial-combustion control",
        "UNSD coal supply control",
        "Lahore SO2 vs EDGAR gridmaps",
        "Provincial SO2 vs EDGAR gridmaps",
        "Power reference audit",
        "Power province boundary audit",
        "Industry vs EDGAR divergence",
        "Validation catalog + scorecard",
        "Validation five classes",
        "Measured validation",
        "Comparison crosswalk",
    ),
    "manuscript": (
        "Sector technical-note facts",
        "Manuscript figures",
        "Manuscript figures, v3 (tables and charts)",
        "Gridded figures",
        "Sync paper figures",
        "Integrated GHG and air manuscript figures",
        "Integrated manuscript figure verification",
        "Validation table",
        "Paper artefacts (stored queries)",
        "Dashboard",
        "Supplement product list",
        "Availability fragments",
    ),
    "release": (
        "Published release vintages",
        "Release axis fingerprints",
        "Product catalog",
        "Release numerical changes",
        "Artifact inventory",
        "Product coverage",
        "Deposit manifest",
        "Citation deposit audit",
        "Product facts registry",
        "Claim matrix",
        "Release manifest",
    ),
}


def _with_categories(phases):
    kind = {}
    for category, labels in CATEGORIES.items():
        for label in labels:
            if label in kind:
                raise ValueError("phase %r is listed under both %s and %s"
                                 % (label, kind[label], category))
            kind[label] = category
    unlisted = [p.label for p in phases if p.label not in kind]
    if unlisted:
        raise ValueError("phases with no category in run_all.CATEGORIES (add each under "
                         "science, validation, manuscript or release): %s" % unlisted)
    stale = sorted(set(kind) - {p.label for p in phases})
    if stale:
        raise ValueError("run_all.CATEGORIES names phases that do not exist: %s" % stale)
    return [replace(phase, category=kind[phase.label]) for phase in phases]


PHASES = _with_categories(_with_asset_paths(_with_spatial_prerequisites(
    _with_canonical_prerequisites(PHASES))))

def declared_writes_after(label, inclusive=False):
    """Repo-relative paths every phase AFTER `label` declares it writes (with `inclusive`,
    the named phase's own writes too - the inventory lists itself).

    rc41: the artifact inventory and the deposit manifest enumerate the universe of
    products. A first run from an EMPTY outputs/ has not yet written the ones that come
    later in the build, so both take the declared set as well as the disk - the same rows
    in a first run and at the fixpoint - and the inventory records no size for a file
    written after it, extending the context-stamped rule to everything it cannot honestly
    measure.
    """
    labels = [phase.label for phase in PHASES]
    out = set()
    for phase in PHASES[labels.index(label) + (0 if inclusive else 1):]:
        out.update(w for w in phase.writes if not w.endswith("/"))
    return out


def missing_requirements(quick=False):
    """[(phase label, module)] for every declared requirement that cannot be imported in
    this interpreter, over the phases this run would execute."""
    import importlib.util
    out = []
    for phase in PHASES:
        if quick and phase.network:
            continue
        for module in phase.requires:
            if importlib.util.find_spec(module) is None:
                out.append((phase.label, module))
    return out


def written_by_other_phases(target_module):
    """Basenames every phase whose target is NOT `target_module` declares it writes.

    rc41: two runners listed their generated outputs by globbing outputs/<sector>_* from
    disk, which in the repository swept in files a LATER phase writes (the ELK crosscheck,
    the provincial shape bracket) and the manifest itself, so a first run from an empty
    outputs/ wrote a different manifest. A manifest that reports what is lying around
    cannot detect the one thing a manifest is for; the glob now excludes what another
    phase declares.
    """
    out, own = set(), set()
    for phase in PHASES:
        names = {os.path.basename(w) for w in phase.writes if not w.endswith("/")}
        if phase.target.split()[0] == target_module:
            own |= names
        elif not phase.prints_only:
            # a prints_only phase DECLARES the runner's own table (its writes are reads)
            out |= names
    # a file this runner writes in-process AND a later phase rewrites (the railways air
    # layer) is this runner's output too; a HELD product (data/held_products.csv, written by
    # no phase) is nobody's build output and is excluded as well
    try:
        from pkinv.core.io import read_rows
        from pkinv.build_support import physical_paths
        held = {os.path.basename(r["path"])
                for r in read_rows(os.path.join(ROOT, physical_paths("data/held_products.csv", ROOT)[0]))}
    except OSError:
        held = set()
    return (out | held) - own


def _cmd(target, importtime=False):
    """Dotted module (+ optional args) -> -m invocation; .py path -> run the file."""
    flags = ["-X", "importtime"] if importtime else []
    parts = shlex.split(target)
    if parts[0].endswith(".py"):
        return [sys.executable] + flags + [os.path.join(ROOT, parts[0])] + parts[1:]
    return [sys.executable] + flags + ["-m"] + parts


def _run(target, owned=None):
    """Run one phase. With `owned` - the repository's module map, passed only under --changed -
    the child also reports its imports via -X importtime, and the report is stripped back out
    of stderr so a build looks exactly as it always did."""
    t0 = time.time()
    environment = os.environ.copy()
    environment.pop("PKINV_BUILD_VERIFIED_OUTPUTS", None)
    r = subprocess.run(_cmd(target, importtime=owned is not None),
                       capture_output=True, text=True, cwd=ROOT, env=environment)
    closure = _closure_from(r.stderr, target, owned) if owned is not None else None
    stderr = _strip_importtime(r.stderr) if owned is not None else r.stderr.strip()
    return r.returncode, time.time() - t0, r.stdout.strip(), stderr, closure


def _wrote(out, started_at):
    """Did the phase actually write its declared output during this run?

    A directory counts if anything inside it was written; a missing path never counts. The
    one-second grace is for filesystems whose mtime resolution is coarser than the phase.
    """
    path = os.path.join(ROOT, out.rstrip("/"))
    if not os.path.exists(path):
        return False
    if os.path.isdir(path):
        return any(os.path.getmtime(os.path.join(path, n)) >= started_at - 1.0
                   for n in os.listdir(path))
    return os.path.getmtime(path) >= started_at - 1.0


# THE LEDGER (rc41). Every run can write a record of what each phase did - status, exit
# code, seconds, and the files that CHANGED under outputs/ (and the declared non-outputs
# write directories) while it ran - so a reproduction can tie every product it compares
# to a phase that logged OK in THAT run. The rc40 validation package compared 83
# products and called 82 identical while 59 of 107 phases had never executed: the
# products were the copied ones. A ledger makes that shape impossible to miss.
LEDGER_SCHEMA = "pkinv.run_ledger/v1"
SNAPSHOT_ROOTS = ("outputs", "data", "paper_national/versions/v1/sections", "paper_national/figures",
                  "papers", "docs")


def _snapshot():
    """{relative path: (st_mtime_ns, st_size)} for every file under SNAPSHOT_ROOTS."""
    seen = {}
    for rel_root in SNAPSHOT_ROOTS:
        base = os.path.join(ROOT, rel_root)
        if not os.path.isdir(base):
            continue
        for folder, dirs, names in os.walk(base):
            dirs[:] = [d for d in dirs if d not in ("__pycache__", "raw", "cache")]
            for name in names:
                path = os.path.join(folder, name)
                try:
                    st = os.stat(path)
                except OSError:
                    continue
                seen[os.path.relpath(path, ROOT)] = (st.st_mtime_ns, st.st_size)
    return seen


def _written(before, after):
    """Paths new or changed between two snapshots - 'observed changed', not 'attempted'."""
    return sorted(p for p, sig in after.items() if before.get(p) != sig)


# ---------------------------------------------------------------------------------------
# THE INCREMENTAL MODE (--only, --changed). A full run rewrites 706 of 792 products in about
# 26 minutes, and until now there was no way to ask for less: --from resumes at a phase and
# runs everything after it, and _wrote() actively FAILS a phase that correctly wrote nothing.
# A one-line edit to one producer cost the whole build, four to seven times per content commit.
#
# WHAT IT IS NOT ALLOWED TO DO. rc40's validation package compared 83 products and called 82
# of them identical while 59 of its 107 phases had never executed - the products were the
# copied ones. An incremental build is that hazard with better manners, so:
#
#   - --changed is REFUSED under --strict. A reproduction rebuilds everything by definition,
#     and the mode a release runs in is untouched by any of this.
#   - a skip is recorded in the ledger as SKIP (current), so a run that skipped a phase can
#     never be read as a run that executed it.
#   - legacy phases whose `reads` is None and have no complete developer receipt
#     NEVER skip. This mode is a strict subset of correct behaviour, and the unaudited
#     phases are a debt that shrinks as reads are declared, not a thing to guess at.
#
# THE FINGERPRINT is sha256 over the content hashes of the phase's resolved reads plus the
# repository files it actually imported when it last ran. Content, never mtimes: a phase that
# reruns and writes byte-identical output must not invalidate everything downstream, and a
# file whose mtime moved without its bytes moving is not a reason to rebuild anything. A phase
# also reruns when any declared write is missing or has been edited since it produced it.
#
# THE CODE CLOSURE IS LEARNED BY RUNNING, never parsed. core/registry.py loads every sector
# engine through importlib.import_module() from a registry, so a static import scan would miss
# all ten and a sector edit would invalidate nothing. Each phase already runs as an isolated
# subprocess; -X importtime reports loaded module names and the parent maps them to files.
# The developer CLI additionally records file IO through build_trace; failed children do
# not receive a successful cache record.
#
# The assumption, stated so it can be argued with: a file can only enter a closure it was not
# in before through an edit to a file already in that closure, which invalidates it anyway.
CACHE_SCHEMA = "pkinv.build_cache/v3"


def cache_path():
    """logs/build_cache.json, resolved at CALL time. ROOT is substituted by the tests that
    drive main() over a temporary tree, and a path baked at import would point at the real
    repository from inside them."""
    return os.path.join(ROOT, "logs", "build_cache.json")

# THE CODE CLOSURE, VIA -X importtime. The child is asked to name every module it imports and
# the PARENT maps those names onto repository files - no instrumentation inside the phase, no
# sitecustomize on its PYTHONPATH, and nothing about the child's environment changed beyond
# one interpreter flag.
#
# Two earlier designs failed, and the way they failed is the reason this one is written down.
# Walking sys.modules from an atexit hook recorded NOTHING for a script phase: by the time
# atexit runs, CPython has cleared __main__'s namespace and the modules' __file__ attributes
# with it. Collecting from an audit hook on the "import" event recorded only the entry point:
# that event's filename argument is None for an ordinary import. Both failures are SILENT and
# both land in the safe direction - an empty closure reads as "never observed running", so the
# phase simply never skips - which is exactly why they survived a first round of testing and
# why the tests now assert the closure's CONTENT rather than its existence.
_IMPORTTIME = re.compile(r"^import time:\s+[\d.]+\s*\|\s+[\d.]+\s*\|\s+(\S+)\s*$")


def _module_files():
    """{dotted module name: repo-relative path} for every Python file this repository owns.

    A pure string mapping over src/ and scripts/ - nothing is imported to build it, so the
    runner's own process never grows a phase's dependencies.
    """
    out = {}
    for folder, dirs, names in os.walk(os.path.join(ROOT, "src")):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for name in names:
            if not name.endswith(".py"):
                continue
            rel = os.path.relpath(os.path.join(folder, name), os.path.join(ROOT, "src"))
            dotted = rel[:-3].replace(os.sep, ".")
            if dotted.endswith(".__init__"):
                dotted = dotted[:-len(".__init__")]
            out[dotted] = os.path.join("src", rel)
    scripts = os.path.join(ROOT, "scripts")
    if os.path.isdir(scripts):
        for name in os.listdir(scripts):
            if name.endswith(".py"):
                out.setdefault(name[:-3], os.path.join("scripts", name))
    return out


def _closure_from(stderr, target, owned):
    """The repository files a phase imported, from its -X importtime report plus its own
    entry point - which is the one file no import line ever names."""
    seen = set()
    for line in (stderr or "").splitlines():
        match = _IMPORTTIME.match(line)
        if match and match.group(1) in owned:
            seen.add(owned[match.group(1)])
    entry = target.split()[0]
    if entry.endswith(".py"):
        seen.add(entry)
    elif entry in owned:
        seen.add(owned[entry])
    return sorted(seen)


def _strip_importtime(stderr):
    """The report is the runner's business, not the phase's: a build's stderr must look
    exactly as it always did, or every consumer of it has to learn about this mode."""
    return "\n".join(l for l in (stderr or "").splitlines()
                      if not l.startswith("import time:")).strip()


def _sha(path):
    """Content identity, including directory membership and every member's bytes."""
    if os.path.isdir(path):
        digest = hashlib.sha256()
        visited = set()
        for folder, dirs, names in os.walk(path, followlinks=True):
            real_folder = os.path.realpath(folder)
            if real_folder in visited:
                dirs[:] = []
                continue
            visited.add(real_folder)
            dirs[:] = sorted(d for d in dirs if d != "__pycache__")
            for name in dirs:
                member = os.path.join(folder, name)
                digest.update((os.path.relpath(member, path) + "/").encode("utf-8"))
                if os.path.islink(member):
                    digest.update(os.readlink(member).encode("utf-8"))
            for name in sorted(names):
                member = os.path.join(folder, name)
                digest.update(os.path.relpath(member, path).encode("utf-8"))
                digest.update(_sha(member).encode("ascii"))
        return digest.hexdigest()
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
    except OSError:
        return "MISSING"
    return digest.hexdigest()


def _glob_universe():
    """Every file under outputs/ and data/, repo-relative - what a glob: read draws from."""
    found = []
    for rel_root in ("outputs", "data"):
        for folder, dirs, names in os.walk(os.path.join(ROOT, rel_root)):
            dirs[:] = [d for d in dirs if d not in ("__pycache__", "raw", "cache")]
            found.extend(os.path.relpath(os.path.join(folder, n), ROOT) for n in names)
    return sorted(found)


def _resolved_reads(phase):
    """A phase's declared reads as concrete repo-relative paths, or None when it declares
    nothing and therefore cannot be fingerprinted.

    held: and prior: are INCLUDED here, unlike in check_order(): the ordering check skips them
    because no phase produces them, and the fingerprint wants them because their content is
    an input all the same. A glob: read contributes its whole matched list, so a NEW match
    changes the fingerprint even when every file that already matched is untouched.
    """
    if phase.reads is None:
        return None
    out, universe = [], None
    for read in phase.reads:
        if read.startswith(("held:", "prior:")):
            out.append(read.split(":", 1)[1])
        elif read.startswith("glob:"):
            universe = _glob_universe() if universe is None else universe
            out.extend(p for p in universe if fnmatch.fnmatch(p, read[5:]))
        else:
            out.append(read)
    return sorted(set(out))


def _fingerprint(phase, cache):
    """The phase's input fingerprint, or None when it may not be skipped at all."""
    entry = cache.get("phases", {}).get(phase.label) or {}
    reads = _resolved_reads(phase)
    declared_reads = set(reads or ())
    if entry.get("observation_complete"):
        reads = list(reads or ()) + entry.get("observed_reads", []) + entry.get("conservative_reads", [])
    if reads is None:
        return None
    if not phase.audited and not entry.get("observation_complete"):
        # Legacy --changed declarations originally listed build edges, not every raw
        # input. Never interpret reads=() as a promise that a sector reads no data.
        reads = list(reads)
        for source_root in ("data", "sources"):
            for folder, dirs, names in os.walk(os.path.join(ROOT, source_root)):
                dirs[:] = [d for d in dirs if d != "__pycache__"]
                reads.extend(os.path.relpath(os.path.join(folder, name), ROOT) for name in names)
    closure = entry.get("closure")
    if not closure:
        return None                 # never yet observed running: nothing to compare against
    digest = hashlib.sha256()
    from pkinv.build_support import environment_identity, phase_identity
    digest.update(json.dumps({"phase": phase_identity(phase),
                              "environment": environment_identity(ROOT),
                              "conservative_identity": entry.get("conservative_identity")},
                             sort_keys=True).encode("utf-8"))
    # Tools invoked outside Python are part of a phase's implementation as well.
    import shutil
    for command in entry.get("external_commands", []):
        words = shlex.split(command) if isinstance(command, str) else command
        if words:
            executable = shutil.which(words[0]) or words[0]
            digest.update(executable.encode("utf-8"))
            digest.update(_sha(executable).encode("ascii"))
    from pkinv.build_support import physical_paths, asset_bindings
    catalog_path = physical_paths("data/canonical/catalog.json", ROOT)[0]
    table_registry = physical_paths("data/canonical_tables.csv", ROOT)[0]
    for rel in sorted(set(reads) | set(closure)):
        if entry.get("canonical_tables") and rel in (catalog_path, table_registry):
            continue
        if (rel == "data/catalog/assets.csv" and entry.get("assets")
                and not entry.get("whole_asset_catalog") and rel not in declared_reads):
            continue
        digest.update(rel.encode("utf-8"))
        digest.update(_sha(os.path.join(ROOT, rel)).encode("ascii"))
    if entry.get("canonical_tables"):
        try:
            with open(os.path.join(ROOT, catalog_path), encoding="utf-8") as handle:
                catalog = json.load(handle)
            tables = {table["table_id"]: table for table in catalog["tables"]}
            selected = {key: tables.get(key, "MISSING") for key in entry["canonical_tables"]}
            digest.update(json.dumps({"schema": catalog.get("schema_version"), "tables": selected},
                                     sort_keys=True).encode("utf-8"))
        except (OSError, ValueError, KeyError):
            digest.update(b"MISSING_CANONICAL_CATALOG")
    if entry.get("assets"):
        fields = ("asset_id", "legacy_path", "path", "canonical_path", "kind")
        bindings = {row["asset_id"]: {key: row.get(key, "") for key in fields}
                    for row in asset_bindings(ROOT)}
        selected = {key: bindings.get(key, "MISSING") for key in entry["assets"]}
        digest.update(json.dumps(selected, sort_keys=True).encode("utf-8"))
    for rel in sorted(entry.get("directory_reads", [])):
        path = os.path.join(ROOT, rel)
        names = sorted(os.listdir(path)) if os.path.isdir(path) else ["MISSING"]
        digest.update(json.dumps([rel, names]).encode("utf-8"))
    return digest.hexdigest()


def is_current(phase, cache):
    """True when nothing this phase reads, imports or produced has moved since it last ran."""
    entry = cache.get("phases", {}).get(phase.label)
    if not entry or not entry.get("fingerprint"):
        return False
    if _fingerprint(phase, cache) != entry["fingerprint"]:
        return False
    # the outputs themselves: a deleted product must be rebuilt, and a hand-edited one must be
    # overwritten rather than quietly kept
    for rel, recorded in (entry.get("writes") or {}).items():
        if recorded == "MISSING" or _sha(os.path.join(ROOT, rel)) != recorded:
            return False
    return True


def record_current(phase, cache, closure, observation=None, conservative_reads=()):
    entry = cache.setdefault("phases", {}).setdefault(phase.label, {})
    if closure:
        entry["closure"] = closure
    entry["target"] = phase.target
    if observation is not None:
        entry["observation_complete"] = bool(observation.get("complete"))
        entry["observed_reads"] = observation.get("reads", [])
        entry["directory_reads"] = observation.get("directories", [])
        entry["conservative_reads"] = sorted(set(conservative_reads))
        entry["external_commands"] = observation.get("external_commands", [])
        entry["canonical_tables"] = observation.get("canonical_tables", [])
        entry["assets"] = observation.get("assets", [])
        entry["whole_asset_catalog"] = observation.get("whole_asset_catalog", False)
    entry["fingerprint"] = _fingerprint(phase, cache)
    writes = set(phase.writes) | set((observation or {}).get("writes", []))
    entry["writes"] = {w: _sha(os.path.join(ROOT, w)) for w in sorted(writes)}


def load_cache():
    try:
        with open(cache_path(), encoding="utf-8") as handle:
            cache = json.load(handle)
        if (cache.get("schema") == CACHE_SCHEMA and
                os.path.realpath(cache.get("root", "")) == os.path.realpath(ROOT)):
            cache["root"] = ROOT
            return cache
    except (OSError, ValueError):
        pass
    return {"schema": CACHE_SCHEMA, "root": ROOT, "phases": {}}


def save_cache(cache):
    os.makedirs(os.path.dirname(cache_path()), exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".build-cache-", dir=os.path.dirname(cache_path()))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(cache, handle, indent=1, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, cache_path())
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _finish(results, ledger, code, ledger_path, seeded_path):
    """One exit path: write the ledger if asked, print the summary, return the code."""
    if ledger_path:
        seeded = []
        if seeded_path and os.path.exists(seeded_path):
            with open(seeded_path, encoding="utf-8") as handle:
                seeded = json.load(handle)
        record = {"schema": LEDGER_SCHEMA, "root": ROOT, "argv": ledger["argv"],
                  "quick": ledger["quick"], "strict": ledger["strict"],
                  "python": sys.version.split()[0], "platform": platform.platform(),
                  "started": ledger["started"], "finished": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                  "exit_code": code, "seeded": seeded, "phases": ledger["phases"]}
        os.makedirs(os.path.dirname(os.path.abspath(ledger_path)), exist_ok=True)
        with open(ledger_path, "w", encoding="utf-8") as handle:
            json.dump(record, handle, indent=1, sort_keys=True)
            handle.write("\n")
        print("ledger -> %s (%d phases)" % (os.path.relpath(ledger_path, ROOT), len(ledger["phases"])))
    _summary(results)
    return code


def _argv_value(argv, flag):
    if flag in argv:
        i = argv.index(flag)
        return argv[i + 1] if i + 1 < len(argv) else None
    return None


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    quick = "--quick" in argv
    # --strict: every phase must exit 0 and write its key output; a non-core failure is
    # no longer a skip, and the run stops at the first one with the phase's name. This is
    # the mode a reproduction runs in - a phase that cannot run is a finding, not a gap.
    strict = "--strict" in argv
    ledger_path = _argv_value(argv, "--ledger")
    seeded_path = _argv_value(argv, "--seeded")
    # --from LABEL: resume a run at one phase, the earlier ones recorded as "SKIP (resume)".
    # A development flag for iterating a strict rebuild in a kept tree; reproduce.sh never
    # passes it, and a ledger that carries a resume skip is not a reproduction ledger.
    resume_from = _argv_value(argv, "--from")
    if resume_from is not None and resume_from not in {p.label for p in PHASES}:
        raise SystemExit("--from: no phase labelled %r" % resume_from)
    resumed = resume_from is None
    # --only LABEL[,LABEL]: run exactly these phases. --changed: skip a phase whose inputs,
    # code and outputs have not moved since it last ran. Both are DEVELOPMENT modes; see the
    # incremental block above for why neither may run under --strict.
    labels = {p.label for p in PHASES}
    only = _argv_value(argv, "--only")
    only = {l.strip() for l in only.split(",")} if only else None
    if only and only - labels:
        raise SystemExit("--only: no phase labelled %s" % ", ".join(sorted(only - labels)))
    changed = "--changed" in argv
    if changed and strict:
        raise SystemExit("--changed and --strict are mutually exclusive: a reproduction "
                         "rebuilds every phase, which is the whole of what --strict asserts")
    if changed:
        if resume_from is not None or seeded_path is not None:
            raise SystemExit("--changed uses the shared developer scheduler; use "
                             "python3 -m pkinv.build --target LABEL for a partial build, "
                             "or omit --changed for --from/--seeded reproduction work")
        # Every entry point uses the same complete input/membership checks and lock.
        # The developer ledger names reused tasks CACHED and claims no output writes.
        from pkinv.build import main as developer_main
        forwarded = ["--group", "full"]
        if quick:
            forwarded.append("--quick")
        if ledger_path:
            forwarded += ["--ledger", ledger_path]
        for label in sorted(only or ()):
            forwarded += ["--target", label]
        return developer_main(forwarded)
    ledger = {"argv": list(argv), "quick": quick, "strict": strict, "phases": [],
              "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

    def record(phase, status, code, secs, written, stderr=""):
        ledger["phases"].append({
            "label": phase.label, "target": phase.target, "core": phase.core,
            "status": status, "exit_code": code, "seconds": round(secs, 2),
            "key_output": phase.key_output, "declared_writes": list(phase.writes),
            "written": written,
            "declared_not_written": [w for w in phase.writes
                                     if not w.endswith("/") and w not in set(written)],
            "stderr_tail": (stderr or "").splitlines()[-3:]})

    results = []
    run_started = time.time()
    missing = missing_requirements(quick)
    if missing:
        for label, module in missing:
            print("   [%s] phase %r imports %r, which is not installed; requirements.lock "
                  "pins it (pip install -r requirements.lock, or -e '.[gis,build]')"
                  % ("STRICT" if strict else "WARN", label, module))
        if strict:
            return _finish(results, ledger, 1, ledger_path, seeded_path)
    before = _snapshot() if ledger_path else {}
    for phase in PHASES:
        label, out = phase.label, phase.key_output
        if only is not None and label not in only:
            results.append((label, "SKIP (--only)", 0.0, out))
            record(phase, "SKIP (--only)", 0, 0.0, [])
            continue
        if not resumed:
            if label != resume_from:
                results.append((label, "SKIP (resume)", 0.0, out))
                record(phase, "SKIP (resume)", 0, 0.0, [])
                continue
            resumed = True
        if quick and phase.network:
            results.append((label, "SKIP (quick)", 0.0, out))
            record(phase, "SKIP (quick)", 0, 0.0, [])
            continue

        print("-> %s ..." % label)
        started_at = run_started if phase.prints_only else time.time()
        if phase.idempotent:
            started_at = 0.0            # existence only; see Phase.idempotent
        code, secs, stdout, stderr, _closure = _run(phase.target)
        if stdout:
            print("   " + stdout.replace("\n", "\n   "))
        after = _snapshot() if ledger_path else {}
        written = _written(before, after) if ledger_path else []
        before = after
        if code == 0 and not _wrote(out, started_at):
            results.append((label, "NO OUTPUT", secs, out))
            record(phase, "NO OUTPUT", code, secs, written, stderr)
            print("   [NO OUTPUT] the phase succeeded and %s did not write %s. Either the "
                  "declared path is stale or it stopped being produced."
                  % ("this run" if phase.prints_only else "the phase", out))
            return _finish(results, ledger, 1, ledger_path, seeded_path)
        if code == 0:
            results.append((label, "OK", secs, out))
            record(phase, "OK", code, secs, written)
        else:
            status = "FAIL" if (phase.core or strict) else "skip (error)"
            results.append((label, status, secs, out))
            record(phase, status, code, secs, written, stderr)
            print("   [%s] %s" % (status, (stderr or "").splitlines()[-1] if stderr else ""))
            if strict:
                print("   [STRICT] phase %r exited %d; a reproduction stops at the first phase "
                      "that cannot run" % (label, code))
            if phase.core or strict:
                return _finish(results, ledger, 1, ledger_path, seeded_path)
    return _finish(results, ledger, 0, ledger_path, seeded_path)


def check_order(phases):
    """Every declared read must be produced by an EARLIER phase. Returns the
    list of violations (empty = consistent); each names the rule that fired.

    Rules: (1) a literal read is produced earlier, or is a data/ path no phase
    writes; (2) a glob: read matches at least one earlier write; (3) one
    producer per artefact - two non-prints_only phases may not both write it
    (a prints_only phase's writes are freshness declarations, counted as
    reads, so declaring a real producer prints_only would silence this rule:
    the message says which rule fired for exactly that reason).
    """
    produced, producer, problems = set(), {}, []
    phase_written = set()
    for phase in phases:
        if not phase.prints_only:
            phase_written.update(phase.writes)
    for phase in phases:
        wanted = list(phase.reads or ())
        if phase.prints_only:
            wanted += list(phase.writes)
        for read in wanted:
            if read.startswith(("held:", "prior:")):
                continue
            if read.startswith("glob:"):
                if not any(fnmatch.fnmatch(w, read[5:]) for w in produced):
                    problems.append("rule 2 (glob unmatched): %s reads %s and no earlier "
                                    "phase writes a match" % (phase.label, read))
            elif read in produced:
                continue
            elif read.startswith("data/") and read not in phase_written:
                continue
            else:
                problems.append("rule 1 (read before write): %s reads %s, which %s"
                                % (phase.label, read,
                                   "a LATER phase writes" if read in phase_written
                                   else "no phase writes"))
        if phase.prints_only:
            continue
        for w in phase.writes:
            if w in producer:
                problems.append("rule 3 (two producers): %s and %s both write %s"
                                % (producer[w], phase.label, w))
            producer[w] = phase.label
            produced.add(w)
    return problems


def _summary(results):
    width = max(len(r[0]) for r in results) if results else 28
    print("\n%-*s %-16s %8s   %s" % (width, "PHASE", "STATUS", "SEC", "OUTPUT"))
    print("-" * (width + 56))
    for label, status, secs, out in results:
        print("%-*s %-16s %8.1f   %s" % (width, label, status, secs, out))
    print("\nNational total: see outputs/national_all_sectors.csv")


if __name__ == "__main__":
    sys.exit(main())
