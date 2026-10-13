.DEFAULT_GOAL := build
.PHONY: dev release-check build full ingest build-plan data-index data-check test-fast changed eval release-fixpoint edgar-ghg-categories clinker-trade btr-comparison forest-flux release-sequence all quick test dashboard sectors agriculture waste aviation aviation-controls aviation-fallback aviation-study aviation-opensky aviation-adsblol-pilot aviation-era5 aviation-ledger aviation-anchor power transport railways fugitives ippu industry residential air national sync-figures paper-national paper-v3 paper-v3-review sector-papers papers figures clean

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

# The nine-year station/fuel/year coal account an outside reader re-derives the series from,
# and the four candidate coal-energy readings built on top of it. Both are in the release
# build; these targets are for running them alone while the coal account is under revision.
power-fuel-reconciliation:
	python3 -m pkinv.sectors.power.fuel_reconciliation

# The dung balance as an assignment question: the asymmetry between the two configurations
# term by term, and the falsifiable implication of the larger one.
dung-balance:
	python3 -m pkinv.report.dung_balance

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
	python3 -m pkinv.build --target "Air source classes (nine fiscal years)" $(BUILD_ARGS)

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

# Optional, network. Asks UN Comtrade for the monthly HS 252310 clinker trade before
# FY2023-24, and for the annual totals that let a silent month be PROVED zero rather than
# assumed zero. Writes nothing on failure; whether any fiscal year is actually closed is
# decided by pkinv.sectors.ippu.trade_evidence, not by this fetch.
clinker-trade:
	python3 scripts/fetch_comtrade_clinker.py
	python3 -m pkinv.sectors.ippu.trade_evidence

# Optional, network. Tries to replace the transport paper's air-pollutant-derived
# EDGAR scope inference with direct GHG category data. Exits non-zero and writes
# nothing when the product is unavailable, which is the current state.
edgar-ghg-categories:
	python3 scripts/fetch_edgar_ghg_categories.py

# The release dance: commit content first, then this regenerates manifest + cover + PDFs
# on the clean tree so the shipped provenance box names the content commit with no
# "(working tree modified)" suffix. Finish with the artifacts-only commit it prints.
release-fixpoint:
	python3 scripts/release_fixpoint.py

# The hand-run evaluation lane (rc36): products the manuscripts and the uncertainty
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

sync-figures:
	python3 scripts/sync_figures.py

# --- Manuscripts ------------------------------------------------------------
# All share paper_common/{preamble,references}. Every target syncs figures from
# outputs/ first, so a manuscript cannot quietly ship a stale chart.
#
# These target names collide with the directories of the same name, which is why
# they are all in .PHONY above - without that, make sees the directory, decides
# there is nothing to be done, and silently does nothing.
# The copy into papers/pdf/ is not cosmetic. This target compiled in place and stopped,
# so papers/pdf/national_paper.pdf was whatever an earlier manual copy had left there -
# a distributed PDF that could disagree with the tested manuscript indefinitely, with no
# test able to see it. The same directory had already shipped a stale README to a reviewer.
# The national article is a Copernicus (ESSD) manuscript; the class is vendored under
# paper_common/copernicus/ and reached through TEXINPUTS/BSTINPUTS rather than installed.
# Article, then supplement, then the article again: the two resolve each other's labels
# through xr (.aux files), so the first pass of the article runs before the supplement's
# .aux exists and the third pass picks it up. latexmk makes the extra pass a no-op when
# nothing changed.
# ABSOLUTE, not ../: the national paper now lives one version directory deeper
# (paper_national/versions/<v>/), and a relative TEXINPUTS would have to be recounted for
# every version. $(CURDIR) is the repository root whatever the target's cwd is, so a v3 at
# any depth needs no Makefile edit.
COPERNICUS = TEXINPUTS=$(CURDIR)/paper_common/copernicus//: BSTINPUTS=$(CURDIR)/paper_common/copernicus//:

# THE NATIONAL PAPER IS VERSIONED. paper_national/versions/<v>/ holds one self-contained
# version; NATIONAL_VERSION names the one the release builds, hashes and ships, and
# paper_national/CURRENT is a symlink to it for a reader arriving at the directory. The
# figures and the stored-query registry are shared at paper_national/ because they are
# inputs to every version rather than part of any one.
#
# To promote a version: change NATIONAL_VERSION here and PAPER_NATIONAL_CURRENT in
# src/pkinv/paths.py, repoint CURRENT, and run the release dance. Those are the only two
# strings; everything else resolves through them.
NATIONAL_VERSION ?= v1
NATIONAL_DIR = paper_national/versions/$(NATIONAL_VERSION)

paper-national: sync-figures
	@mkdir -p papers/pdf
	cd $(NATIONAL_DIR) && $(COPERNICUS) latexmk -pdf -interaction=nonstopmode paper_national.tex
	cd $(NATIONAL_DIR) && latexmk -pdf -interaction=nonstopmode supplement.tex
	cd $(NATIONAL_DIR) && $(COPERNICUS) latexmk -pdf -interaction=nonstopmode paper_national.tex
	cp $(NATIONAL_DIR)/paper_national.pdf papers/pdf/national_paper.pdf
	cp $(NATIONAL_DIR)/supplement.pdf papers/pdf/national_supplement.pdf

# v3, the compact editorial rewrite, built BESIDE the shipped version rather than in place
# of it. (It was versions/v2 through rc63. v2 is now the frozen rc62 record: nothing here
# builds it, and tests/test_frozen_versions.py holds it to its recorded bytes.) It is one
# self-contained file: no sections/, no xr pairing with a supplement, so one latexmk pass
# is enough. paper-v3-review goes through submission.tex, which
# defines \reviewversion and makes the file choose the one-column [essd,manuscript] layout
# a reviewer reads.
#
# Not wired into `papers`, deliberately: these targets do not copy into papers/pdf/,
# because pakemis_paper_hashes.csv hashes what is there and a second national article
# appearing in the release set is a decision to take at the promotion, not a side effect of
# a build target.
# THE EIGHT MAIN FIGURES OF v3, FROM THE RELEASED PRODUCTS, IN ONE COMMAND. Plot tables and the
# two tables generated from them, then figures 1, 2, 3, 7, 8; then the gridded figures 4, 5, 6.
# All are drawn at their printed size by src/pkinv/report/manuscript_style.py. `make papers-v3`
# rebuilds the figures and all three documents.
figures-v3:
	python3 scripts/build_manuscript_figures.py
	python3 scripts/make_fig_ghg_grid.py
	python3 scripts/verify_manuscript_figures.py

papers-v3: figures-v3 paper-v3 paper-v3-review paper-v3-supplement

paper-v3: sync-figures
	cd paper_national/versions/v3 && $(COPERNICUS) latexmk -pdf -interaction=nonstopmode paper.tex

paper-v3-review: sync-figures
	cd paper_national/versions/v3 && $(COPERNICUS) latexmk -pdf -interaction=nonstopmode submission.tex

# THE TECHNICAL COMPANION, WHICH NOTHING BUILT UNTIL 2026-10-07. The comment above says it
# is "one self-contained file: no sections/, no xr pairing with a supplement", and that was
# true when it was written. technical_supplement.tex now exists, is substantial and is
# where the review's items 5, 8, 9 and 10 are answered - and its PDF was nine hours older
# than its own source, because no target compiled it. It is a standalone copernicus
# document, so one latexmk pass is enough, the same as its two siblings.
paper-v3-supplement: sync-figures
	cd paper_national/versions/v3 && $(COPERNICUS) latexmk -pdf -interaction=nonstopmode technical_supplement.tex

# One self-contained manuscript per sector. Skips papers not yet written, so this target is
# usable from the first one onwards rather than only when all nine exist.
SECTORS = agriculture waste transport power residential ippu fugitives railways aviation

# Each paper compiles in its own directory - LaTeX needs \graphicspath and the aux files
# beside the source - then lands in papers/pdf/ under its sector's name. Nine files called
# paper.pdf in nine directories is not something you can hand to anyone; one folder of
# <sector>_paper.pdf is. The in-place paper.pdf is the intermediate and is gitignored.
sector-papers: sync-figures
	@mkdir -p papers/pdf
	@for s in $(SECTORS); do \
		if [ -f papers/$$s/paper.tex ]; then \
			echo "-> papers/$$s"; \
			( cd papers/$$s && latexmk -pdf -interaction=nonstopmode paper.tex ) || exit 1; \
			cp papers/$$s/paper.pdf papers/pdf/$$s\_paper.pdf; \
			if [ -f papers/$$s/supplement.tex ]; then \
				( cd papers/$$s && latexmk -pdf -interaction=nonstopmode supplement.tex ) || exit 1; \
				cp papers/$$s/supplement.pdf papers/pdf/$$s\_supplement.pdf; \
			fi; \
		fi; \
	done
	@echo "collected $$(ls papers/pdf/*.pdf 2>/dev/null | wc -l | tr -d ' ') PDFs in papers/pdf/"

papers: paper-national paper-v3 paper-v3-review paper-v3-supplement sector-papers

# Regenerate every figure the manuscripts use, straight from the engine outputs.
figures: figures-v3
	python3 -m pkinv.report.figures

clean:
	rm -f outputs/*.csv outputs/*.md outputs/*.html outputs/*.png
	rm -f outputs/figures/*.png
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
