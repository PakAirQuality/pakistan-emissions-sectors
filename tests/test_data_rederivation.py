"""The committed data products that a producer can rebuild are rebuilt and compared.

WHY. run_all never runs the ingest layer: it writes data/periods.csv and data/months.csv
and nothing else under data/. So the clean-room's "every tracked file unchanged after a
build" is a null test for the raw -> data/activity step, and eight producers shipped a
`--check` mode that no test and no CI job ever ran. This module runs them. A producer whose
re-derivation does not match the committed file is a FINDING - the file, or the raw input,
or the script changed and nobody re-ran - and it fails here rather than being overwritten.

SKIPS ARE PRINTED, NEVER SILENT. rc36 retired two test files whose every test had skipped
for releases on a deleted companion file, and nobody had noticed because a skip is green.
Each skip below names its reason, and test_the_skips_are_the_declared_ones fails if the set
of producers that skipped on this machine is not the set this file declares may skip (the
geospatial stack, the 317 MB shapefile read) - so a new silent skip is a failure.

Run:  python3 -m unittest discover tests -p "test_data_rederivation.py"
      PKINV_SLOW=1 to include the road-network rebuild (minutes; reads the OSM shapefile).
"""
import os
import subprocess
import sys
import unittest

from _support import ROOT, require_documents

SCRIPTS = os.path.join(ROOT, "scripts")

# (script, what it writes, requirement) - requirement is None, "gis" (geopandas+shapely) or
# "slow" (PKINV_SLOW=1). Every entry with a requirement may skip; nothing else may.
PRODUCERS = (
    ("build_adm2_package.py", "data/adm2_canonical.csv + data/adm2_crosswalk.csv", None),
    ("build_facility_registry.py", "data/facility_registry.csv", None),
    ("build_benchmark_splits.py", "data/benchmark_splits/*.csv", None),
    ("ingest_captive_register.py", "data/activity/power/captive_register.csv", "document:sources/Power Plants"),
    # rc38, the agriculture pass: both read held NFDC documents and need no network.
    ("ingest_nfdc_annex7.py",
     "data/nfdc/annex7_province_month_product_2023-24.csv", "document:sources/Agriculture/NFDC_Fertilizer_Review_2023-24.pdf"),
    ("ingest_nfdc_afr2025_fertilizer.py", "data/nfdc/afr2025_*.csv (four tables)", None),
    # The nine-year production series. It was absent from this registry, and that absence
    # cost a real defect: after the sector layout moved its input and its output, the
    # script still named the old locations, so it read a file that was gone and would have
    # written a second vintage beside the raw PDFs while every reader used the catalog's
    # copy. Nothing here noticed, because nothing here ran it.
    ("ingest_nfdc_production_series.py",
     "data/nfdc/nfdc_production_by_product_series.csv",
     "document:data/raw/nfdc/nfdc_fertilizer_statistics_2012_13_to_2022_23.pdf;"
     "data/raw/nfdc/nfdc_annual_fertilizer_review_2023_24.pdf"),
    # rc39, the power pass: nine producers read held NEPRA/PBS documents and none of them
    # had a --check. Seven are single-lane and are here; the two-lane monthly generation
    # pair needs a check on the rows each lane OWNS (see the note in its own step) because
    # _merge writes preserved rows first, so the file's order records which lane ran last.
    ("ingest_power.py", "data/activity/power/generation_by_fuel.csv + fuel_consumed.csv", "document:sources/Power Plants"),
    ("ingest_nepra_plants.py", "data/activity/power/plant_fuel_ledger.csv", "document:sources/Power Plants"),
    ("ingest_nepra_heat_rates.py", "data/activity/power/plant_heat_rates.csv", "document:sources/Power Plants"),
    ("ingest_nepra_plant_fuel.py", "data/activity/power/plant_fuel_generation.csv", "document:sources/Power Plants"),
    ("ingest_nepra_locations.py", "data/activity/power/plant_locations.csv", "document:sources/Power Plants"),
    ("ingest_nepra_bagasse.py", "data/activity/power/bagasse_generation.csv", "document:sources/Power Plants"),
    # rc42: the coal fleet's coordinates, from two tables the package ships (no document)
    ("ingest_coal_plant_coordinates.py", "data/activity/power/coal_plant_coordinates.csv", None),
    ("ingest_grid_plant_coordinates.py", "data/activity/power/plant_coordinates.csv", "document:sources/Power Plants/climatetrace_power_assets_PAK.csv;sources/Power Plants/wri_gppd_PAK.csv"),
    # The two-lane pair. Each rewrites only its own fiscal years and preserves the other's
    # rows, and they write in opposite orders - PBS puts its own rows first, SIR puts its
    # own last - so with PBS holding the earlier years both run orders land on the same
    # layout and a whole-file check is sound for EITHER lane. Confirmed by running both.
    ("ingest_pbs_generation.py",
     "data/activity/power/generation_monthly.csv (FY2017-18..FY2020-21) + coverage", "document:sources/Power Plants/pbs_generation"),
    ("ingest_sir_generation.py",
     "data/activity/power/generation_monthly.csv (FY2021-22 on) + coverage", "document:data/raw/nepra/sir_detail"),
    ("build_brick_kiln_assets.py", "data/gis/kilns/pak_brick_kiln_*.csv", "gis"),
    ("build_landfill_assets.py", "data/gis/landfills/pak_landfill_*.csv", "gis|document:sources/OSM/pakistan-20260809"),
    ("build_building_fraction.py", "data/gis/osm_building_fraction_267x340.npy", "gis|document:sources/OSM/pakistan-20260809"),
    ("build_road_network.py", "data/gis/roads/pak_road_density_267x340.npy", "slow"),
    # rc41: the typed column registry, inferred from the shipped products and frozen
    ("build_product_columns.py", "data/product_columns.csv", None),
    # rc41: the consumed derivatives (data/consumed_derivatives.csv) - each re-derived from
    # its document where the document is held, skipped by name where it is not.
    ("ingest_climatetrace_power.py", "data/activity/power/climatetrace_power_assets_pak.csv",
     "document:sources/Power Plants/climatetrace_power_assets_PAK.csv"),
    ("ingest_elk_rail.py", "data/activity/railways/elk_rail_pak_2019.csv",
     "document:sources/ELK/ELK_CO2-rep_land_rail-freight_2019_v2.1_global_annual.nc"),
    ("ingest_climatetrace_waste.py", "data/activity/waste/climatetrace_waste_sites_pak.csv",
     "document:sources/ClimateTRACE/climatetrace_waste_PAK_sources.json"),
    ("ingest_fugitives_observations.py",
     "data/activity/fugitives/{flare_sites,mars_plumes,mars_sources}_pak.csv",
     "document:sources/Fugitives/world_bank_flare_sites_2012_2025.xlsx;"
     "sources/Fugitives/unep_mars_plumes.zip"),
    ("ingest_aviation_study_inputs.py",
     "data/activity/aviation/*_extract.csv + adsblol_pilot_fy2023_24.json",
     "document:sources/Aviation/ocac_monthly;sources/Aviation/ocac_annual;"
     "sources/Aviation/OECD_air_transport_PAK_2019_2025.csv;"
     "sources/Aviation/climatetrace_aviation_PAK_2015_2024.json;"
     "sources/Aviation/climatetrace_airports_PAK_2021_2024.json;"
     "sources/Aviation/ERA5_route_weather_FY2023_24.nc;"
     "sources/Aviation/ADSBLOL_pilot_FY2023_24.json"),
)


def _gis_available():
    try:
        import geopandas  # noqa: F401
        import shapely  # noqa: F401
        return True
    except ImportError:
        return False


SKIPPED = {}


class TestProducersRederiveByteIdentically(unittest.TestCase):

    def _check(self, script, writes, requirement):
        # rc42: a producer may need BOTH an environment and a document ("gis|document:...");
        # every token is a gate, the first unmet one skips, then the check runs once
        for token in (requirement or "").split("|"):
            if token:
                self._gate(script, writes, token)
        return self._run_check(script, writes)

    def _gate(self, script, writes, requirement):
        if requirement == "gis" and not _gis_available():
            SKIPPED[script] = "geopandas/shapely not installed"
            self.skipTest("%s: geopandas/shapely not installed (writes %s)" % (script, writes))
        if requirement == "slow" and os.environ.get("PKINV_SLOW") != "1":
            SKIPPED[script] = "PKINV_SLOW unset"
            self.skipTest("%s: set PKINV_SLOW=1 to run (317 MB shapefile; writes %s)"
                          % (script, writes))
        if requirement and requirement.startswith("document:"):
            # rc41: a consumed derivative re-derives only where its document is held; the
            # validation package registers the document without shipping it. rc42: the skip
            # is the documents gate's (tests/_support.require_documents) - inside a package
            # a registered, unshipped document skips by name; in the repository a missing
            # document FAILS, because the repository must hold what it registers.
            try:
                require_documents(*requirement[len("document:"):].split(";"))
            except unittest.SkipTest as skip:
                SKIPPED[script] = str(skip)
                raise

    def _run_check(self, script, writes):
        result = subprocess.run([sys.executable, os.path.join(SCRIPTS, script), "--check"],
                                capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(result.returncode, 0,
                         "%s --check does not reproduce %s:\n%s%s"
                         % (script, writes, result.stdout[-2000:], result.stderr[-2000:]))


def _make(script, writes, requirement):
    def test(self):
        self._check(script, writes, requirement)
    test.__doc__ = "%s --check reproduces %s" % (script, writes)
    return test


for _script, _writes, _req in PRODUCERS:
    setattr(TestProducersRederiveByteIdentically,
            "test_" + _script.replace(".py", "").replace("-", "_"),
            _make(_script, _writes, _req))


class TestTheSkipsAreTheDeclaredOnes(unittest.TestCase):
    """Runs last (alphabetical class order): whatever skipped above must have been allowed to."""

    def test_the_skips_are_the_declared_ones(self):
        allowed = {s for s, _w, r in PRODUCERS if r is not None}
        self.assertTrue(set(SKIPPED) <= allowed,
                        "undeclared skips: %s" % sorted(set(SKIPPED) - allowed))
        for script, reason in sorted(SKIPPED.items()):
            print("  re-derivation SKIPPED %s: %s" % (script, reason))
