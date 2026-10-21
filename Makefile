.DEFAULT_GOAL := build
.PHONY: contribution-evidence contribution-figures contribution-check gas-pilot dev release-check layers public-check build full ingest build-plan data-index data-check test-fast changed eval release-fixpoint edgar-ghg-categories clinker-trade btr-comparison forest-flux release-sequence all quick test dashboard sectors agriculture waste aviation aviation-controls aviation-fallback aviation-study aviation-opensky aviation-adsblol-pilot aviation-era5 aviation-ledger aviation-anchor power transport railways fugitives ippu industry residential air national figures clean

# Full national pipeline: nine sectors, then the cross-sector layer.
all: full

# Everyday iteration: source tables, model products and semantic release.
dev: build

build:
	python3 -m pkinv.build --group dev $(BUILD_ARGS)

build-plan:
	python3 -m pkinv.build --group dev --dry-run --explain $(BUILD_ARGS)

data-index:
	python3 -m pkinv.data_index

data-check:
	python3 -m pkinv.data_requests --check
	python3 -m pkinv.data_index --check
	python3 -m pkinv.activity.compatibility_views --check
	python3 -m pkinv.activity.build --check

# Release/reproduction always bypasses the developer cache. It ends by re-hashing every
# held source document against the retention ledger (17 GB, a minute or two): a release is
# not checked while a document it cites may have gone or changed.
release-check: full
	python3 scripts/retain_document.py --verify
	python3 scripts/check_public_tree.py

# Which restricted layers this checkout can read (docs/restricted_layers.md).
layers:
	python3 -m pkinv.core.layers

# Nothing tracked here may be unpublishable; run before every push.
public-check:
	python3 scripts/check_public_tree.py

full:
	python3 -m pkinv.build --group full --full --strict $(BUILD_ARGS)

# Explicit acquisition/extraction lane; ordinary builds consume committed extracts.
ingest:
	python3 -m pkinv.build --group ingest --full $(BUILD_ARGS)

# Everything that needs no network.
quick:
	python3 run_all.py --quick

test:
	python3 -m unittest discover tests

# The parallel test runner: the same tests, one process per test module, about a third of
# the wall time on ten cores. `make test` stays canonical - scripts/record_test_run.py shells
# it and publishes its count, and tests/test_parallel_runner.py holds this runner to
# dispatching exactly what discovery finds.
test-fast:
	python3 scripts/run_tests.py

# DEVELOPMENT ONLY. Skips every phase whose declared inputs, imported code and produced
# outputs are unchanged since it last ran. Refused under --strict, so no release path can
# reach it; see the incremental block in src/pkinv/run_all.py for what it will not do.
changed: build

dashboard:
	python3 -m pkinv.report.dashboard

# --- Sectors -----------------------------------------------------------------
# Every registered sector, then the national layer that pools them.
sectors:
	python3 -m pkinv.build --group sectors $(BUILD_ARGS)

agriculture:
	python3 -m pkinv.build --sector agriculture $(BUILD_ARGS)

waste:
	python3 -m pkinv.build --sector waste $(BUILD_ARGS)

# The runner prices its ladder configuration from the fallback study's resolution table
# and its monthly layer reads the reconciliation study's OCAC series, so both studies run
# first (rc41; run_all.py orders the phases the same way). The controls ingest stays its
# own target.
aviation:
	python3 -m pkinv.build --sector aviation $(BUILD_ARGS)

aviation-controls:
	python3 scripts/build_aviation_anchor_controls.py

aviation-fallback: aviation-controls
	python3 -m pkinv.build --target "Aviation fallback study" $(BUILD_ARGS)

aviation-study: aviation-fallback
	python3 -m pkinv.build --target "Aviation reconciliation study" $(BUILD_ARGS)

aviation-opensky:
	python3 -m pkinv.sectors.aviation.extract_opensky

# Optional empirical pilots. The ADSB raw cache is several GiB and ODbL; only
# aggregate diagnostics enter the versioned source snapshot used by aviation-study.
aviation-adsblol-pilot:
	python3 scripts/fetch_adsblol_pilot.py --download
	python3 scripts/run_adsblol_pilot.py

aviation-era5:
	python3 scripts/fetch_era5_aviation.py

aviation-ledger:
	python3 -m pkinv.sectors.aviation.build_ledger

aviation-anchor:
	python3 -m pkinv.sectors.aviation.run_anchor_year

power:
	python3 -m pkinv.build --sector power $(BUILD_ARGS)

# The ten-year station/fuel/year coal account an outside reader re-derives the series from,
# and the four candidate coal-energy readings built on top of it. Both are in the release
# build; these targets are for running them alone while the coal account is under revision.
power-fuel-reconciliation:
	python3 -m pkinv.sectors.power.fuel_reconciliation

# The dung balance as an assignment question: the asymmetry between the two configurations
# term by term, and the falsifiable implication of the larger one.
dung-balance:
	python3 -m pkinv.report.dung_balance

# The gas-reallocation application (docs/gas_reallocation_application.md): moves the two network-supplied
# urea plants' gas to grid power with urea and electricity held fixed. Reads the inventory, writes only
# outputs/pakemis_transition_gas_* and two figures. GAS_ARGS="--draws 1000" is a labelled development sample.
gas-pilot:
	PYTHONPATH=$(CURDIR)/src python3 -m pkinv.applications.gas_reallocation $(GAS_ARGS)

power-coal-configurations:
	python3 -m pkinv.sectors.power.coal_configurations

transport:
	python3 -m pkinv.build --sector transport $(BUILD_ARGS)

railways:
	python3 -m pkinv.build --sector railways $(BUILD_ARGS)

# Route-constrained spatial products (needs the [gis] extra); not CI-built, like the
# agriculture grid.
railways-gis:
	python3 -m pkinv.sectors.railways.gis.run_gis

fugitives:
	python3 -m pkinv.build --sector fugitives $(BUILD_ARGS)

ippu:
	python3 -m pkinv.build --sector ippu $(BUILD_ARGS)

industry:
	python3 -m pkinv.build --sector industry $(BUILD_ARGS)

residential:
	python3 -m pkinv.build --sector residential $(BUILD_ARGS)

# Air-pollutant co-emissions: mass only, never CO2e, never in the GHG totals.
air:
	python3 -m pkinv.build --target "Air source classes (supported fiscal panel)" $(BUILD_ARGS)

# Cross-sector rollup, key-category screen, pooled Monte Carlo and completeness.
national:
	python3 -m pkinv.build --group dev $(BUILD_ARGS)

# The year-matched comparison against Pakistan's own submission. Offline: the BTR table is a
# verified transcription held in data/shared/evidence/, and the engine side is the atomic
# annual table, so this needs no network and no reference-year rebuild.
# Did the release dance happen in the right order? Reads git, not the tree. Run it AFTER the
# record is committed; mid-dance it declines to judge rather than guessing. This is not a
# suite test because the record is produced by running the suite, so at that moment the
# committed record is necessarily the previous release's.
release-sequence:
	python3 scripts/check_release_sequence.py

# What the power coal re-base moved, per year, with the cause rather than only the size.
coal-rebase-ledger:
	python3 -m pkinv.sectors.power.rebase_ledger

# What drives the national uncertainty, from the released ensemble itself: category and
# sector shares of variance and of the tails. Replaces the surrogate Sobol products (rc67).
uncertainty-drivers:
	python3 -m pkinv.report.ensemble_drivers

# The forest-land sign disagreement, as a screening beside the inventory. Offline.
forest-flux:
	python3 scripts/build_forest_flux_adjudication.py

# Which province-years of the minerals panel are whole, and what a hole costs. Offline.
minerals-panel-screening:
	python3 scripts/build_minerals_panel_screening.py

# Can a reader find the FIGURE in the document, or only the document? Offline.
citation-pointers:
	python3 scripts/build_citation_pointer_audit.py

# Which AXIS of a release moved: national totals, or only the spatial allocation. Offline.
axis-fingerprints:
	python3 scripts/build_release_axis_fingerprints.py

# Which commit each served release actually was, re-checked against git. Offline.
published-vintages:
	python3 scripts/build_published_vintages.py

# The F-gas bank's one leak rate per stratum against IPCC Table 7.9's rate per
# sub-application. Re-runs the bank kernel; offline.
fgas-leak-rates:
	python3 scripts/build_fgas_leak_rate_adjudication.py

btr-comparison:
	python3 scripts/build_btr_comparison.py

# Focused optional evaluation: uses the shipped panels and reruns only the small
# nitrogen kernel, so a contribution review does not trigger the full inventory.
contribution-evidence: btr-comparison
	python3 -m pkinv.sectors.agriculture.faostat_nitrogen_flows
	python3 -m pkinv.report.contribution_evidence

contribution-figures: contribution-evidence
	python3 -m pkinv.report.contribution_figures

contribution-check:
	python3 scripts/build_btr_comparison.py --check
	python3 -m pkinv.sectors.agriculture.faostat_nitrogen_flows --check
	python3 -m pkinv.report.contribution_evidence --check

# Optional, network. Asks UN Comtrade for the monthly HS 252310 clinker trade before
# FY2023-24, and for the annual totals that let a silent month be PROVED zero rather than
# assumed zero. Writes nothing on failure; whether any fiscal year is actually closed is
# decided by pkinv.sectors.ippu.trade_evidence, not by this fetch.
clinker-trade:
	python3 scripts/fetch_comtrade_clinker.py
	python3 -m pkinv.sectors.ippu.trade_evidence

# Optional, network. Tries to replace the transport sector's air-pollutant-derived
# EDGAR scope inference with direct GHG category data. Exits non-zero and writes
# nothing when the product is unavailable, which is the current state.
edgar-ghg-categories:
	python3 scripts/fetch_edgar_ghg_categories.py

# The release dance: commit content first, then this regenerates the manifest and checksums
# on the clean tree so the release names the content commit with no "(working tree
# modified)" flag. Finish with the artifacts-only commit it prints.
release-fixpoint:
	python3 scripts/release_fixpoint.py

# The hand-run evaluation lane (rc36): products the documentation and the uncertainty
# contract cite, whose writers are in this repository but outside `national` by design
# (research-grade, slow, or waiting on an acquisition). Runnable by name, never orphaned.
eval:
	python3 -m pkinv.eval.proxy_attribution
	python3 -m pkinv.eval.mms_structural_uncertainty
	python3 -m pkinv.sectors.agriculture.mms_sensitivity
	python3 -m pkinv.eval.n_ledger_runs
	python3 -m pkinv.eval.sensitivity_table
	python3 -m pkinv.eval.uncertainty_inputs
	python3 -m pkinv.eval.buffalo_implied_ef
	python3 -m pkinv.eval.spatial_nh3_validation

# The inventory's own figures (outputs/figures/) and the dashboard: the `figures` build kind.
figures:
	python3 -m pkinv.build --group figures $(BUILD_ARGS)

clean:
	rm -f outputs/*.csv outputs/*.md outputs/*.html outputs/*.png
	rm -f outputs/figures/*.png
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
