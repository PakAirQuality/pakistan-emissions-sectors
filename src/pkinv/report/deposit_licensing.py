"""Separate primary records from ODbL components and unreviewed legacy descendants.

These are packaging decisions, not an assertion that changing a filename clears an
upstream right. The compatible primary is calculated with primary_geography filters.
Historical products are preserved without changing their contents or source licences.
"""
import fnmatch
import os

from pkinv.assets import legacy_path
from pkinv.paths import ROOT

ODBL_INPUTS = (
    "data/gis/landfills/pak_landfill_assets.csv", "data/gis/landfills/pak_landfill_coverage.csv",
    "data/activity/ippu/facility_geocoding_overrides.csv", "data/gis/rail/pak_rail_network.geojson",
    "data/gis/rail/yards.csv", "data/gis/roads/pak_road_density_267x340.npy",
    "data/gis/osm_building_fraction_267x340.npy", "data/facility_registry.csv",
    "outputs/pakemis_facility_registry.csv", "data/activity/aviation/adsblol_pilot_fy2023_24.json",
)

# Positive scopes regenerated through compatible primary dispatch. A matching file
# cannot be released until the integration run and geographical audit have passed.
PRIMARY_SPATIAL = (
    "outputs/pakemis_grid_0p05_monthly.nc", "outputs/pakemis_grid_0p05_monthly_ledger.nc",
    "outputs/pakemis_grid_0p05_annual_ref_fy2015_16_fy2024_25.nc",
    "outputs/pakemis_ghg_grid_0p05_annual_*_fy2015_16_fy2024_25.nc",
    "outputs/pakemis_ghg_configuration_*.csv",
    "outputs/pakemis_air_grid_0p05_*fy2015_16_fy2024_25*.nc",
    "outputs/pakemis_air_grid_0p05_*_s_tan.nc", "outputs/pakemis_air_grid_0p05_*_l_tan.nc",
    "outputs/pakemis_air_grid_0p05_*_s_ipcc.nc", "outputs/pakemis_air_grid_0p05_*_l_ipcc.nc",
    "outputs/pakemis_air_adm1_by_year.csv", "outputs/pakemis_air_adm2_by_year.csv",
    "outputs/pakemis_air_adm1_monthly_by_year.csv", "outputs/pakemis_air_adm2_monthly_by_year.csv",
    "outputs/pakemis_air_spatial_unallocated_by_year.csv", "outputs/pakemis_air_spatial_lineage_by_year.csv",
    "outputs/pakemis_air_unallocated_by_year.csv", "outputs/pakemis_air_monthly_unallocated.csv",
    "outputs/pakemis_adm1_by_year.csv", "outputs/pakemis_adm2_by_year.csv",
    "outputs/pakemis_adm1_monthly_by_year.csv", "outputs/pakemis_adm2_monthly_by_year.csv",
    "outputs/pakemis_spatial_unallocated_by_year.csv", "outputs/pakemis_spatial_weights_by_year.csv",
    "outputs/pakemis_grid_provincial_check.csv", "outputs/pakemis_adm2_monthly_sector.csv",
    "outputs/pakemis_adm2_by_category.csv", "outputs/pakemis_adm2_registry.csv",
    "outputs/pakemis_grid_stream_check.csv", "outputs/pakemis_grid_unallocated.csv",
    "outputs/pakemis_grid_fallbacks.csv", "outputs/pakemis_grid_placement_notes.csv",
    "outputs/pakemis_ghg_configuration_unallocated.csv",
    "outputs/pakemis_primary_geography_licence_audit.csv",
)

LEGACY_SENSITIVE = (
    "outputs/*facility*", "outputs/*rail*grid*", "outputs/*rail*gis*",
    "outputs/*adsblol*", "outputs/*landfill*", "outputs/*spatial*",
    "outputs/*grid*", "outputs/*adm1*", "outputs/*adm2*", "outputs/*geocod*",
    "outputs/*geometr*", "outputs/*map*",
    # rc68: the held legacy spatial products entered the deposit; their proxy surfaces and
    # networks were not cleared one by one, so they travel with the companion.
    "outputs/gis/*", "outputs/districts/*", "outputs/pakemis_road_links.parquet",
    "outputs/railways_network_audit_*", "outputs/railways_route_province_shares_*",
    "outputs/residential_gis_*", "outputs/eval/proxy_attribution.csv",
)


def upstream_dependencies(relative, source_rows=None):
    """ODbL-sensitive dependencies; no database is cleared by hiding its input."""
    logical = legacy_path(relative, root=ROOT)
    if logical.startswith("data/baselines/"):
        return ["preserved prior release: mixed geographic dependencies not independently cleared"]
    if logical in ODBL_INPUTS:
        return [logical]
    source = (source_rows or {}).get(relative, {})
    if "odbl" in source.get("licence_status", "").lower():
        return [relative]
    if any(fnmatch.fnmatch(logical, pattern) for pattern in PRIMARY_SPATIAL):
        return []
    if any(fnmatch.fnmatch(logical, pattern) for pattern in LEGACY_SENSITIVE):
        return ["legacy spatial/geometry workflow: conservatively retained as ODbL-sensitive"]
    return []


def package_group(relative, source_rows=None):
    return "odbl-companion" if upstream_dependencies(relative, source_rows) else "primary"


def audit_rows():
    from pkinv.core import primary_geography
    from pkinv.core.manifest import sha256_file
    if not primary_geography.PRIMARY_COMPATIBLE:
        raise ValueError("the primary package requires compatible primary geography")
    components = (
        ("facility coordinates", "data/facility_registry.csv",
         "src/pkinv/core/primary_geography.py", "compatible_facilities excludes ODbL and OSM coordinate rows before placement"),
        ("rail corridor and yards", "data/gis/rail/pak_rail_network.geojson;data/gis/rail/yards.csv",
         "src/pkinv/core/primary_geography.py", "primary_stream replaces OSM network/yard geometry with declared accounting geography and unallocated fine mass"),
        ("waste disposal", "data/gis/landfills/pak_landfill_assets.csv;data/gis/landfills/pak_landfill_coverage.csv",
         "src/pkinv/report/grid_cube.py", "OSM landfill polygons excluded; independently sourced sites retained; uncovered mass remains origin geography"),
        ("road and building diagnostics", "data/gis/roads/pak_road_density_267x340.npy;data/gis/osm_building_fraction_267x340.npy",
         "src/pkinv/core/primary_geography.py", "OSM diagnostics remain companion inputs; they are not primary allocation surfaces"),
        ("ADS-B diagnostics", "data/activity/aviation/adsblol_pilot_fy2023_24.json",
         "src/pkinv/sectors/aviation/run_reconciliation_study.py", "ODbL pilot retained in companion; admitted national fuel/LTO calculations use operator and public traffic evidence"),
    )
    rows = []
    for component, dependencies, code, treatment in components:
        rows.append(dict(row_kind="dependency", component=component, scope=dependencies,
                         package_group="odbl-companion", licence_id="ODbL-1.0",
                         evidence_file=code, evidence_sha256=sha256_file(os.path.join(ROOT, code)),
                         treatment=treatment, verification="primary-geography tests and integrated closure required"))
    for pattern in PRIMARY_SPATIAL:
        rows.append(dict(row_kind="supported_scope", component="primary greenhouse-gas/air allocation",
                         scope=pattern, package_group="primary", licence_id="CC-BY-4.0 with upstream terms",
                         evidence_file="src/pkinv/core/primary_geography.py",
                         evidence_sha256=sha256_file(os.path.join(ROOT, "src/pkinv/core/primary_geography.py")),
                         treatment="regenerated without ODbL coordinates, geometry or weights; fixed allocation assumptions retained explicitly",
                         verification="not a historical clearance: requires current integrated rebuild and NetCDF geographic_licence_basis"))
    rows.append(dict(row_kind="preserved_scope", component="previous releases", scope="data/baselines/**",
                     package_group="odbl-companion", licence_id="ODbL-1.0 conservative database packaging; original contents licences retained",
                     evidence_file="data/baselines/rc67_integrated_campaign/README.md", evidence_sha256="",
                     treatment="unchanged baseline bytes and original terms; no blanket own-work classification",
                     verification="baseline checksums"))
    return rows
