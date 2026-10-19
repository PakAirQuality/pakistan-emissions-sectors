# Changelog — PakEmis

All release-cycle history lives here: the documentation describes the current method, and
this file records how it got there. Each release candidate below
answers an external review round. Historical totals appear here labelled as history — the only
current national figures are the manifest's.

## [1.0.0rc70] — 19 October 2026

The inventory-only release. No number moves: every emissions product, the four configuration
pins and the uncertainty products are byte-identical to rc69 apart from version stamps.

### The papers leave this repository

The national article, its supplement, the long report, the sector technical notes, their
LaTeX, figure and table generators, their tests and the release steps that built them now live
in a separate repository that reads this one's outputs and never writes into it. This
repository builds, tests and releases the inventory alone, and names no other repository.

- **Removed:** `paper_national/`, `papers/`, `paper_common/`, `tests/paper_numbers/`, the paper
  copies in the rc67 baseline, the claim matrix and claims registry, 31 paper-only scripts, the
  paper modules, 24 paper-only test modules and the 19 historical `mint_rc*.py` scripts.
- **Products no longer published here:** `pakemis_claim_matrix.csv/.md`,
  `pakemis_citation_deposit_audit.csv`, `pakemis_paper_hashes.csv`,
  `pakemis_paper_artefact_hashes.csv` and `pakemis_sector_note_facts.csv`. Each described the
  papers; none carried an inventory quantity of its own.
- **The build:** the `manuscript` build kind is now `figures` (the inventory's
  `outputs/figures/` and the dashboard; `make figures`). The release fixpoint regenerates the
  manifest and `SHA256SUMS` only.
- **The deposit:** no manuscript rows. The documentation archive carries the README, `docs/`,
  the licences and `CITATION.cff`.
- **The release manifest:** the product block no longer carries a manuscript status or
  submission identifier.
- **Where a product is documented:** every `documentation_anchor` in
  `pakemis_product_catalog.csv` now names a heading of `README.md` or a document under
  `docs/`, resolved by `tests/test_product_catalog_anchors.py`.
- **What counts as cited:** the artifact inventory reads `README.md` and `docs/`. Products
  named only in the papers are now recorded `cited_in=none`; the uncited ceilings were raised
  to the live counts (canonical 156, sector headline 54, diagnostic 100) with that reason.
- **Author-year citations in `data/`** resolve against `data/catalog/data_references.csv`
  (16 references), extracted from the bibliography that left with the papers.
- **Tests:** the inventory half of the release-integrity suite is
  `tests/test_release_integrity.py`. Tests that checked a paper's text moved with the papers;
  the inventory checks beside them stayed.

## [1.0.0rc69] — 17 October 2026

The first release developed in this repository, and the answer to the review of the rc68
public copy.

### Development moves to the public repository

Through rc68 the work was done in a private repository and each release was then COPIED
here without its third-party source documents. From now on the work is committed here
directly. The documents stay in the private checkout and become the **restricted layers**.
`src/pkinv/core/layers.py` lists them, `docs/restricted_layers.md` explains them, and a
clone mounts them as ignored symlinks with `scripts/overlay.py`.

- Every question put to git about a document goes to the repository that owns it: whether it
  is tracked, whether it is in LFS, and what an old release held. This covers
  `raw_data_manifest.py`, the frozen `sources/` guard, the retention-ledger history, the two
  release-history phases and the LFS test. The release manifest and the test record now name
  the private checkout's commit beside this repository's. Without the layers:
  - the raw manifest refuses to run;
  - the release manifest refuses to build;
  - `pkinv.build` refuses any group but `deposit` when the selection reads documents;
  - `holdings.py` says NOT MOUNTED instead of reporting zero hits.
- A public clone without the layers skips the document tests with the fixed reason
  `restricted layers absent:`. The runner fails if that set differs, in either direction,
  from `data/catalog/restricted_gated_tests.txt`, and a run with the layers mounted fails on
  any such skip. `tests/test_layers_exercised.py` asserts counts only a real mount can produce,
  and treats a configured overlay that does not resolve as an error, not as absence.
- `scripts/make_public_copy.py` became `scripts/check_public_tree.py`, which copies nothing. It
  fails on any of these:
  - a tracked restricted path;
  - a file over GitHub's size limit;
  - a restricted name `.gitignore` does not ignore (without a trailing slash, since a mount is a
    symlink);
  - a stale `NOTICE-ODbL.md`.
- **Two defects of the rc68 public copy, fixed:**
  - Its note said the data were under CC BY 4.0, while 198 files it carried are ODbL-derived or
    were packaged with the deposit's ODbL companion. `NOTICE-ODbL.md` now lists them, using the
    deposit's rule.
  - It shipped the agent instructions (`CLAUDE.md`) and 41 working notes (`research_campaign/`).
    Both are now restricted.

  They remain in the history of the two copy commits.
- Smaller fixes:
  - `pkinv.assets` keeps the lexical path before resolving symlinks, so a mounted raster keeps
    its catalog identity, and it never aliases a restricted directory.
  - The data provenance audit follows mounted folders.
  - The PDF-age test reads commit times for files git holds unmodified, because a fresh clone
    stamps every file with the moment of checkout.
- Tests that hold only at a release commit (the committed release and deposit manifests, the
  deposit archives, the shipped PDFs) skip with the reason `release-time check:` when
  `PKINV_RELEASE_CHECKS=0`. Only the public CI sets that variable; the release path never does.

### FY2024–25 residue burning has its own fire record

Until now FY2024–25 burning was timed by elapsed days and placed on a substitute cropland
surface, because the VIIRS area-API record ends in June 2024 and refetching needs a personal
key. NASA's keyless country-year file for 2025 is now held beside the 2024 one.
`fetch_firms --from-country-archive 2024` fills that year's burning windows from the two files
into `firms_fire.csv`. They are the same VIIRS S-NPP standard product, for Pakistan only:
69,282 detections. Every country-file detection inside the earlier nine years' windows is in
the area-API record, so the substitution is the same product rather than a different one.

FY2024–25 burning is now TE3, timed and placed by its own detections, on its own FIRMS
surface. Only FY2024–25 monthly, spatial and gridded rows move. Every annual total is
unchanged.

### Road particulates under the guidebook's own technology factors

`pakemis_road_technology_case.csv` (`pkinv.report.road_technology_case`) recomputes road
exhaust PM2.5 and BC with the EMEP/EEA 2023 Tier 2 factors, holding each class's fuel fixed.
The 22 rows (PM2.5 per km, fuel per km and f-BC per technology, read off the held chapter's
pages) are in `data/sectors/transport/activity/emep_tier2_road_pm_by_technology.csv`. Two
cases:
- **Pre-Euro fleet.** Road PM2.5 rises to 2.5 times the central value, or 0.59–0.83 of matched
  HTAP (central 0.23–0.33), and BC to 0.42–0.59 of HTAP (central 0.16–0.23).
- **Euro II fleet.** Slightly below central, because Euro 2 motorcycles emit less than the
  Tier 1 mean.

Fleet technology therefore explains part of the particulate difference, not all of it. No
held source gives the fleet's composition by emission standard, so the central inventory keeps
the Tier 1 means.

### Building without the restricted layers, continued

- The build's input snapshot now walks mounted folders. Before this, every document under a
  mount read as edited during a task and stopped the build.
- The paper-artefacts phase no longer declares the two output folders rc68 emptied, which git
  does not keep.
- A clone without the layers keeps the committed records of restricted files in the
  provenance audit and the semantic release (rasters, boundary documents). Both now rebuild
  byte-identically there.
- The Table 2 caption now says that wear contributes particulate mass but not BC.

### The nitrogen partition, pathway by pathway against EMEP/EEA 2023

The review called the agricultural nitrogen partition a major structural assumption: the
all-NH3 diagnostic moves national NOx by 150 Gg. The EMEP/EEA 2023 chapters 3.B and 3.D are
now held. `pakemis_nitrogen_no_pathways.csv` (`pkinv.report.nitrogen_no_pathways`) compares
every agricultural NOx pathway with the factor the Guidebook publishes for it:

| Pathway | Central basis | EMEP/EEA 2023 factor |
|---|---|---|
| Synthetic fertiliser | 0.007 kg NO-N per kg N | 0.04 kg NO2 per kg N (3.D Table 3-1) |
| Applied manure | 0.007 kg NO-N per kg N | 0.04 kg NO2 per kg N (3.D Table 3-1) |
| Grazing excreta | 5 percent of grazing volatilisation | 0.04 kg NO2 per kg N (3.D Table 3-1) |
| Manure management | 5 percent of every stage's mixed loss | 0.01 kg NO-N per kg TAN entering solid storage (3.B Table 3-10) |

The resulting case, `nitrogen_no_emep2023_process_factors`, is carried through national
totals for every year and configuration. It raises reference-year NOx by 118.2 Gg: the
stored-manure term falls by 85 Gg, and the applied and deposited terms rise. The two nitrogen
cases lie on opposite sides of the central estimate. National NOx changes from FY2015–16 to
FY2024–25 by:
- 18.2 percent centrally;
- 17.4 percent with the EMEP/EEA factors;
- 11.5 percent under the all-NH3 diagnostic.

The central value is unchanged: replacing it would be a declared re-base, and the choice is
the authors'.

### What the covered air total leaves out at power stacks

`pakemis_air_power_omission.csv` (`pkinv.report.air_power_omission`) gives, per year and
species, the screened power-stack pair for the fuels the covered panel does not hold, of
which coal, as a share of the covered national total. It is never added to a total. The
omitted SO2 is:
- 0.04–0.31 percent of covered SO2 in FY2015–16;
- 6.4–64.2 percent in FY2024–25, almost all coal.

For primary PM2.5 the omission rises to at most 9.0 percent. The paper now gives these
shares beside the SO2 trend.

### Smaller fixes

- The paper says why FY2023–24 is the detailed reference year: it is the latest year with
  its own district crop areas. It also says that FY2025–26 is provisional because its source
  series are incomplete, not because the year has not ended.
- COD-AB: only the two boundary files are restricted. The project's own provenance note
  `COD_AB_SOURCES.json` is tracked. A clone without the layers builds the semantic release
  from the committed release's record of the two library assets.

### Presentation: measured validation in one table, and road separated from off-road

- **New Table 4** in the evaluation section: what was measured, one row per check.
  `pakemis_validation_measured.csv` (`pkinv.report.validation_measured`) reads the parse
  summaries, closure ledgers and reproduction record, and recomputes two closures from the
  released tables: air monthly against annual, and districts against provinces.
  `scripts/make_validation_table.py` renders the table. It shows:
  - OCAC 36/36 months closing within 0.14 percent;
  - NFDC 58/58 product-years;
  - PBS minerals 36/36;
  - QIM 1,128/1,137 item-years;
  - air monthly against annual, 70/70 within 7e-6 Gg;
  - the rc68 rebuilds, with 0 differing files.

  Fifteen gridded rows that do not close are named as declared divergences: the Islamabad
  airport LTO streams, which are ICT in the share table and Attock on the grid.
- **Table 2** (species coverage) has separate road transport and off-road machinery rows.
  Off-road machinery has GHG estimates only.

### What moved coal emissions in the latest year

The review asked how much of the FY2024–25 coal revision is physical activity and how much
is source vintage or consumer allocation. `pakemis_coal_change_decomposition.csv`
(`pkinv.sectors.industry.coal_change_decomposition`) splits every year-on-year coal change,
per species and for GHG, into the supply balance, the allocation seam, the consumer split,
the source vintage, the emission factor, and power-station and household coal. The split is
an additive identity on the final exports, closing to within 2×10⁻⁵, and its GHG terms
reproduce the published supply-balance and seam split to within the whole-kilotonne
rounding of that file.

- **SO2.** Brick-kiln SO2 rises by 173.2 Gg from FY2023–24 to FY2024–25:
  - −6.1 Gg follows the physical supply balance;
  - +50.5 Gg follows the seam between HDIP's power column and metered station burn;
  - +119.5 Gg follows the shift of the published consumer split towards brick kilns;
  - +9.3 Gg follows the choice of the Economic Survey 2025–26 print over the Statistical
    Supplement 2024–25 one.

  Without the three allocation terms national SO2 would have changed by −24.0 Gg rather than
  rising by 155.3 Gg.
- **Other species.** PM2.5 would have changed by −8.7 Gg, BC by −0.5 Gg and CO by −9.5 Gg.
- **GHG.** The GHG seam is 69.0 percent of the national one-year change, as printed.

The mechanism is that cement-kiln air pollutants follow clinker, not booked cement coal, so a
reallocation from cement to brick kilns adds air emissions with no change in coal burned.
The paper's trend section now says so with these numbers. No total moved.

A public clone's deposit build also reuses the committed product of any phase that declares
a restricted read (the ADM2 2022 frame crosswalk reads the OCHA COD-AB boundaries), as the
fifteen source phases already do.

### The build workflow

- **Every phase declares its kind.** `run_all.CATEGORIES` gives each phase one of science,
  validation, manuscript or release, and the registry refuses a phase it does not list.
  `make dev` builds science and validation only. Before this it was "every phase except
  eleven labels", and the figure stages written after that list (the v3 tables and charts,
  the gridded figures, the integrated figures and their check, the sector-note TeX) ran on
  every development build. `make figures-v3` is now the manuscript group.
- **Each manuscript is compiled once.** `paper.tex`, `technical_supplement.tex` and
  `submission.tex` are each built once and copied to their release names; the wrapper files
  that compiled the same PDF a second time are gone. The paper targets depend on the figure
  target, so `make -j` cannot compile a paper before its figures.
- **The two slowest phases run side by side.** GHG and Air conditional uncertainty (about
  640 s of a cold build together) declare their complete reads, are audited, and sit next to
  each other, so `--jobs` batches them.
- **Repeated test setup removed.** `weights.build()` once per class instead of six times;
  the longitudinal-uncertainty components read once instead of nine times (that module:
  100 s to 29 s); one fresh release manifest for the two tests that compare against it.
- **Continuous integration in two workflows.** `public-checks.yml` runs on every push without
  the restricted layers: the public-tree check, the whole suite (its summary counts the
  skips of each class), and the deposit-group rebuild, which must reproduce every committed
  product. `reproduce.yml` is the complete reproduction, run by hand where the layers are
  mounted. The old workflow compiled a manuscript file that no longer existed and installed
  unpinned packages. Without the layers the deposit group also reuses the committed products
  of the release category (the manifests, source register and inventories describe the
  release with its documents), and the job sets `PKINV_RELEASE_CHECKS=0`.
- Timings are in `docs/build_performance.md`: cold 2,056 s for 189 phases, unchanged 1.2 s.
- **What the first Ubuntu runs found.**
  - Two tests depended on the machine. One searched with ripgrep, which the runner lacks;
    it now reads the same files in Python. The OGRA OCR test checked for tesseract before
    the document, so it skipped for the wrong reason; it now checks the document first.
  - The rebuilt products differ from the macOS-committed ones only in floating-point last
    places: about seventy files of draws, quantiles, shares and grids, plus two rasterised
    PNGs. Measured on run 38974615431: the largest relative difference is 1.5e-13 in the
    gridded netCDF and at most 1.5e-15 in the Monte Carlo draws; the 3e-9 in two ADM2 files
    is an eight-decimal value whose last printed digit flipped. `scripts/compare_rebuild.py`
    now compares them to a declared tolerance (rtol 1e-9, or one unit in the last printed
    place), prints the largest difference per file, and fails on any text difference or any
    number beyond it. Byte identity remains the release contract on one platform.

### A sum that depended on the hash seed

The grid's located share of each power fuel summed plant fuel over a set of plant names. A
set of strings iterates in an order set by `PYTHONHASHSEED`, which no part of the build
fixes, so the share moved in its last binary place from run to run, and two FY2018–19
furnace-oil rows of `pakemis_grid_fallbacks_by_year.csv` changed their twelfth printed digit.
It showed up as a difference between a public-clone rebuild and a full build of the same
commit. The sum is now `math.fsum`, which gives the same correctly rounded result in any
order, and a test runs it under two seeds.

### What the rc69 rebuilds found

The first rc69 cut passed its test record (4,111 executed, 0 failed) and its archive
checksums, and the two reproductions then failed, as did the public-checks run on the
release commit. None of the four defects moved a number:
- The measured-validation table read `docs/reproduction/rc68/`, which the deposit did not
  carry, so both the clean rebuild and a reader's unpacked deposit stopped there. The
  reproduction records are now deposited with the documentation.
- That table's test-run row read the live test record, which the suite writes after the
  table is built, so the table was stale on every release commit and put the new count
  under an "rc68" label. It now reads rc68's own record, published byte for byte as
  `docs/reproduction/rc68/test_run.json`.
- The rule that a tree without the restricted layers reuses the committed release products
  and the 2022 ADM2 frame applied to deposit trees as well as to public clones. A deposit
  tree carries the boundaries and every deposited file, so at rc68 those phases rebuilt
  there byte for byte; under the rule ten products went unbuilt. It now applies only to a
  git checkout without the layers (`layers.public_clone_without_layers`).
- The strict build's order check, the sync's figure scan and the release finish needed the
  repairs listed under the build workflow above; the validation package, which
  `release_finish.sh` still builds, is no longer on the release path (rc68 shipped through
  `scripts/build_deposit_zip.py`).

## [1.0.0rc68] — 14 October 2026

The integrated national greenhouse-gas and air-pollutant release now covers ten fiscal
years, July 2015–June 2025, with a separately labelled source-only FY2025–26
provisional extension. The survey/TAN reference is 457.239832 Mt CO2e (AR5) in
FY2024–25 and 444.607755 Mt in the FY2023–24 detailed reference year. The latter
is 0.347666 Mt below rc67. FY2024–25 core air totals include 422.696 Gg primary
PM2.5, 833.128 Gg NOx as NO2 and 2690.089 Gg NH3.

The PBS minerals parser now preserves vertically centred province labels and selects
distinct worksheets. FY2021–22 oil activity changes from a 12-row Balochistan-only
export to the source-controlled 48 province-month records; FY2020–21 gas changes
from 372 duplicate-inflated rows to 48. This materially repairs fugitive monthly
timing but leaves its annual totals unchanged. The coal account keeps station fuel
mass times rank-specific NCV, exposes unresolved industrial allocation, and separates
K-Electric and kiln structural cases. Conditional native-gas and air-pollutant
uncertainty, paired trends and nitrogen-pathway sensitivity are provided separately
from unestimated sources. The spatial evidence register now marks borrowed crop
district shapes, projected-population geography and calendar-year flare proxies.

The previous release and product hashes are preserved in
`data/baselines/rc67_integrated_campaign`; the repair register and numerical change
table accompany this candidate. The package is prepared locally for review. No
external deposit, DOI or journal submission is claimed.


### Integration review (15 October 2026)

The first full test run of the integrated tree, and three review workstreams, found these;
each is in `campaign/v3_readiness/repair_register.csv`.
- **A road-diesel print that did not add up.** OCAC's FY2017-18 edition prints an HSD total
  of 9,038,298 t while its customer classes sum to 8,516,476 t. The FY2018-19 edition
  restores exactly the 521,822 t difference to Road. The core had carried the short
  figure; it now books the correction under a fail-closed rule with the amount declared.
  Road diesel in FY2017-18 is 7,988,245 t (was 7,466,423). The national total for
  FY2017-18 rises 1.698 Mt CO2e in every configuration (S_TAN 453.009 to 454.708 Mt), all of
  it road and off-road transport; FY2017-18 NOx rises 11.6 Gg, CO 3.0 Gg and PM2.5 0.32 Gg.
  No other year moves.
- **Cement placement lost to the licence rule.** Eight works had only OpenStreetMap
  coordinates, which the primary geography cannot use, so 42.3 percent of census clinker
  went unplaced. They carry the GEM cement tracker's exact coordinates (CC BY), 0.02 to
  0.74 km from the old points; no district changes, and unplaced clinker is 0.77 percent.
  Mass the shared provincial shape had spread elsewhere is now at the works: Lahore, which
  has no cement works, falls 0.082 Mt CO2e in July 2018 and 0.125 Gg PM2.5 in FY2019-20, and
  the two semantic goldens that pin those cells record the reason.
- **Kiln counts as annual series.** Fleets counted in November 2020 and July 2023 (Punjab)
  were compared with the national booked brick column in every year. A count is now
  compared only in its own fiscal year, scaled to national: inside the fleet case in
  FY2020-21, below it in FY2023-24 (1,129 against 3,571 kt).
- **Coal allocation measured.** The HDIP allocation seam is 1.1 percent of the
  FY2015-16 to FY2024-25 rise in the national total, and 69 percent of the one-year rise
  to FY2024-25.
- **Air records.** Every air atom states its mass basis; the legacy FY2023-24 ADM1/ADM2
  layers label their 213.55 Gg of screened power SO2, which had sat unmarked beside
  39.40 Gg covered; SO2 records state their sulfur boundary. The EDGAR industry comparison
  is on the matched 1A2 + 2A1 boundary, and HTAPv3.2 is compared process by process for
  seven species. CAMS-GLOB-ANT has no keyless download and is not used.
- **Smaller.** Aviation declares the T3 timing its layer uses; GEM's Jamshoro coal unit is
  matched to NEPRA's FY2024-25 account; the AR6 limitation names the table that holds AR6;
  the HTAP NH3 benchmark is read from the held workbook (1,489.4 Gg, not a derived
  1,372.5); cold-start excess is IE inside the Tier 1 factors, not NE; the retired nine-year
  GHG panels are removed from outputs/ (kept in the rc67 baseline) after seven tests were
  found reading them.
- **Method text the tables still carried.** The transport tier table, the runner's method
  note and three waste completeness rows described superseded methods (a Punjab g/km exhaust
  layer, a retired open-burning bound, the 2006 wastewater equation); each is corrected where
  it is generated. The national Monte Carlo is described as the legacy reference-year run.
- **Citations counted by substring.** The artifact register counted
  `semantic/fact_activity_*.csv` as citing every `activity/activity_*.csv` working file. It
  now matches whole names; every canonical product is named in the technical supplement's
  generated list, and the evidence tables behind the source checks are named where those
  checks are described. Twelve diagnostics whose subjects the rewritten texts no longer
  discuss stay uncited, and the ceiling says so.
- **FY2025-26** stays provisional: power station fuel, gas and coal have no full-year
  observation. Full-year NFDC nitrogen offtake is added to the provisional activity.
- **What the clean rebuild found.** Rebuilding from the deposit's compiled inputs in an empty
  directory exposed defects a warm tree hides, none of which moved a number. The ADM2 spatial
  brackets read the ten-year monthly panel three phases before it was written, so each build
  priced them on the previous build's panel; the phase now follows the panel. The citation
  deposit audit is written after the deposit manifest that hashed it and is now
  context-stamped. The Table 3 hypotheses register was wrongly registered as hand-run; the power
  runner writes it, and the phase now declares it. The deposit gained the proxy-grid
  provenance notes, the stored-query registry and the v3 figure scripts. Five more phases that
  open retained raw archives (FAOSTAT forests and nitrogen, UNFCCC CRT, EDGAR gridmaps) are
  seeded at their released digests, so the clean rebuild is at the compiled-input level.
  Declared `prior:` reads are seeded from the release and must be rewritten to the same bytes.
  Verifying the built deposit found the rc67 campaign baseline's checksum list naming three
  v3 `.tex` sources that no input pattern deposited; they now ship, and a test requires every
  deposited `SHA256SUMS` to name only deposited files.
  The second clean rebuild built every phase and its comparison found five more, again with no
  emission number moved. The four rc67 query figures (`fig_trend`, `fig_sectors`, `fig_months`,
  `fig_uncertainty`), with their data and images, were still hashed and shipped although the
  rewritten query registry no longer writes them and no manuscript draws them; `fig_trend`
  carried rc67's nine-year values. They are retired with their schema rows. The five-class
  regrouping of the validation catalogue was stale at 103 entries against the catalogue's 104
  (the HTAP species comparison): it now reads 64 partially independent benchmarks and 104
  entries, and a test checks the product against the catalogue rather than only the table
  against the product. The source register named a document's folder by asking the disk, so
  a tree without the documents named the migrated CSV folder; it now asks the raw manifest.
  The two release-history phases read earlier releases from git and are seeded at their
  released digests (fifteen seeded phases). The ADM2 partition's provenance note now ships
  beside the partition.
  A third clean rebuild left two: three Parquet twins kept an older single-row-group layout
  because their cells matched (the twin check now compares the layout too), and the semantic
  contract recorded digests for three undeposited internal files because they sat on the
  maintainer's disk (a data file now carries a digest only if the deposit can carry it).
  Unpacking the built release with its own helper, as `docs/deposit_rebuild_limits.md`
  instructs, failed twice: `scripts/unpack_deposit.py` verified each archive against the first
  `SHA256SUMS` in name order, which in the data archive and the ODbL companion is a nested
  list (the campaign reproduction folder, a preserved baseline), and it refused the
  companion's top-level `docs/` note. It now verifies against the archive's own list and
  restores that note in place. Building from the unpacked tree then stopped at "Derivation
  chains": 66 of the 97 held products (13.7 MB) were seeded by the clean rebuild from the
  maintainer's checkout and were never in the deposit. Every held product under `outputs/`
  now ships, with the legacy spatial ones conservatively in the ODbL companion, and a test
  requires it. The build from the unpacked release then passed every phase; its artifact
  inventory still differed by five files, the four hand-run figures (excluded as
  "regenerable", which no phase makes them) and the fixpoint's `outputs/SHA256SUMS`. The
  figures now ship and the checksum list is inventoried by declaration.

### The public repository and the explorer

**The repository a reader can open, and the explorer.** No emission estimate changes with
this part.
- **The defect.** Every manuscript, the citation file and the release manifest gave the
  repository as `github.com/RehanAhmad13/pakistan-emissions-sectors`, which is private and
  returned 404 to an anonymous reader. It could not simply be opened: it holds 6,193
  third-party documents, among them household survey microdata PBS forbids redistributing.
- **The public repository** is `github.com/PakAirQuality/pakistan-emissions-sectors`, a copy
  of each release without those documents. `scripts/make_public_copy.py` holds the rule for
  what is left out (the two document trees, a download cache, five older document folders,
  thirteen third-party rasters, working notes) and writes `PUBLIC_MIRROR.md` into the copy.
  The copy carries no history, so the commits a release manifest names do not exist in it;
  the manifest now says so beside the address (`repository_note`).
  `tests/test_public_copy.py` holds the rule to the tracked tree: no path of the retention
  ledger ships, no record-level survey file, no raster under `data/` that was not judged.
- **One place.** `pkinv.release` names the public repository, the explorer and the
  initiative's website. The companion repository keeps its own owner; it did not move.
- **The explorer** at `https://emissions.hawanama.org`, a website of the Pakistan Air Quality
  Initiative (`https://pakairquality.com`), is named in the article's data availability
  statement, the README, the citation file (`url`) and the manifest. It is deployed
  separately and can serve an earlier release, so nothing says which release it serves; the
  archived release is the version of record.
- **The README** no longer says the repository holds the government source documents without
  saying which repository.
- **Not done.** The DOI, the anonymous review link and the deposit itself. The explorer was
  last pinned to rc59 and is not redeployed here.


## [1.0.0rc67] — October 2026
**Three reference changes, made together as ONE DECLARED RE-BASE. The national pins move:**
the reference total 451.85782 → **444.95542** Mt CO2e AR5 (AR6 438.19061), and the retained
configuration L 451.85782 → **450.20168**. The reference is now the household-survey reading
of dung, so the pin that was "S" (446.72502) is the reference and the pin that was "L" is the
alternative. This answers Priorities 2 to 6 of the review of the v3 manuscript. Every one of
the three changes reaches FY2015-16.
- **What moved, and by how much (FY2023-24).** −1.19473: chemical feedstock leaves the
  post-meter gas leakage base (fugitives 24.694 → 23.499). −5.24626: household dung is taken
  from the household survey, not from all the dung agriculture diverts (residential 29.467 →
  24.220). −0.46141: domestic wastewater N2O follows the 2019 Refinement (waste 37.914 →
  37.453). Sum −6.90240. No other sector moves in any year
  (`data/baselines/pre_rc67_reference/` holds the account before).
- **The nine-year series** is 393.836, 419.440, 447.910, 444.081, 445.514, 483.446, 483.449,
  438.341, 444.955 Mt (it was 400.898 … 451.858). The change over the window is 51.119 Mt
  (was 50.960). FY2020-21 and FY2021-22 are within 0.003 Mt; FY2021-22 is now marginally the
  higher. The fall is 6.9 to 7.1 Mt in every year; the waste part is larger in the early years
  (−1.64 Mt in FY2015-16) because each year now takes its own sanitation shares.
- **Priority 2, fertiliser feedstock.** The post-meter factor (2019 Refinement Table 4.2.4k) is
  defined on gas consumed in non-residential combustion equipment. It had been applied to the
  whole fertiliser gas class, 31.0 percent of the base. NFDC's metered feed and fuel gas
  (Annual Fertilizer Review 2024-25, Annex-28) puts 83.5 percent of the class in feedstock:
  observed for FY2023-24 and FY2024-25, carried and labelled carried for the seven earlier
  years. Feedstock is now outside the base and process fuel inside
  (`post_meter_state="feed_excluded"`). The old membership is the scenario
  `post_meter_including_feedstock` and the national configuration
  `fugitives_including_feedstock` (446.150), retained and not defended; it is now the top of
  the fugitive envelope (9.601 to 24.694), and the reference is not. The fertiliser class is
  held for all nine years (`fertilizer_gas_class.csv`; FY2020-21 read from the page image,
  FY2022-23 restated from the next edition), so the axis is priced in every year. New:
  `outputs/pakemis_gas_flow_crosswalk.csv`, one row per delivered stream and year with its flow
  kind, the activity its factor is defined on, and the category that books its carbon.
- **The 0.288 Mt figure is a different adjustment.** `gross_delivered_gas_accounting` undoes
  the netting of leakage from the combustion of four burned streams. It has no fertiliser term
  and the manuscripts no longer cite it as the size of the feedstock correction.
- **Not closed:** the carbon in the fertiliser class's gas (13.2 to 14.7 Mt CO2 across the
  utility heating-value band) against 8.08 Mt booked on ammonia production. Published as an
  open difference with a `data_gaps.csv` row; assigned to no cause.
- **Priority 3, household dung.** The reference burns what the two HIES rounds observe
  households burning, in every year: 6.50 Mt (2018-19) and 11.97 Mt (2024-25) anchor a
  per-household quantity, interpolated between the rounds and held at the first round's rate
  before it. FY2023-24 takes 10.93 Mt. Configuration L (all 58.74 Mt diverted from manure
  management burned by households) is retained as a bounded destination assumption.
  `pkinv.core.configurations` holds the one switch (`REFERENCE_DUNG_BASIS = "survey"`).
  Greenhouse gases and air pollutants now share one dung quantity: residential PM2.5 is
  282.7 kt (631.9 under L), and the bridge to the CCAC/SEI assessment closes to −33 kt with no
  configuration wedge (it had needed 314 kt). The covered air totals fall with it in every year: the
  national SO2 ratio to EDGAR for FY2021-22 is 0.92 (was 0.96), Sindh 0.18 (was 0.21).
- **The dung with no household destination is unresolved, in every year.** 47.81 Mt of
  air-dry cake holding 1,026 kt N in FY2023-24: a typed row of the annual product, outside the
  total, with no emission applied. `outputs/pakemis_dung_fate_by_year.csv` prices its
  destinations for nine years: burned by non-household users (+5.246, which is configuration
  L), never left manure management (+4.485; agriculture is RE-RUN with the diversion reduced,
  so volatile solids and nitrogen move together), applied to fields (+3.486). No
  probabilities.
- **What the survey leaves open.** The two rounds differ by a factor of 1.53 per household. In
  2024-25 the top 5 percent of reporting households hold 44.7 percent of the reported dung
  (19.6 percent in 2018-19). Dung activity carries 35 percent under the reference; scenarios
  `dung_survey_rate_2018_19` (residential 23.852) and `dung_survey_round_2024_25_as_measured`
  (24.334) price the two rounds. Firewood still takes the 2024-25 round as measured in the
  reference year while dung is interpolated; the two fuels are not treated alike there.
- **Crop-residue fuel** keeps the ledger's quantity: the survey records rupees, and its price
  bracket (7.8 to 24.7 Mt air-dry) contains the ledger's 10.5. The two ends are scenarios
  `residue_fuel_survey_bracket_low` (residential 23.924) and `…_high` (25.778).
- **Renamed.** Products `*_survey*` are `*_ledger*` and carry configuration L
  (`national_all_sectors_ledger.csv`, `pakemis_monthly_ledger_2024.csv`,
  `pakemis_adm1_ledger_2024.csv`, `pakemis_adm2_ledger_2024.csv`,
  `pakemis_grid_0p05_monthly_ledger.nc`, `pakemis_ensemble_ledger_summary.csv`,
  `pakemis_air_grid_0p05_annual_ledger_fy2015_16_fy2023_24.nc`). Configuration ids:
  `REF_2023_24` (reference, survey dung), `L_2023_24`, `L_HERD1624`. RETIRED: `S_2023_24`,
  `S_HIES1925`, national configuration `observed_household_demand` (now
  `all_diverted_dung_household_fuel`), scenario `dung_activity_hies`, scenario
  `post_meter_excluding_feedstock` and configuration `fugitives_excluding_feedstock` (what
  they priced is the reference).
- **Priority 5, wastewater N2O.** The 2019 Refinement chapter is now held
  (`data/raw/ipcc/19R_V5_6_Ch06_Wastewater.pdf`); eleven manifest rows that called the 2006
  chapter "2019" are corrected. The reference allocates nitrogen to the sanitation pathways
  the methane estimate uses (Eq. 6.10, protein consumed), removes what each treatment type
  removes, and counts plant and effluent emissions for every pathway: 9.706 Gg N2O against
  11.447 under the 2006 equation. The effluent factor's range is 0.0005 to 0.075 (2006:
  0.0005 to 0.25). The 2006 method is retained with its own draws
  (`waste_parameter_rerun_ipcc2006`); `outputs/pakemis_wastewater_method_comparison.csv`
  compares the two for nine years. Sanitation shares are each year's own (JMP 2015 to 2023,
  `scripts/ingest_jmp_sanitation.py`), which also moves wastewater methane before FY2023-24.
- **Three wastewater inputs are declared, not measured,** each priced as a scenario: the
  treated share of sewered flow (1 percent), nitrogen from septic tanks, latrines and open
  defecation reaching water (to soil: waste 35.866), receiving waters not nutrient-impacted
  (impacted: 44.569).
- **Priority 4, K-Electric. No number moves.** `national_configurations.csv` gains
  `family_kind`; the power family separates a fuel-property alternative (38.45, circular), a
  coverage alternative (K-Electric, 44.05) and the previously published account (57.82), and
  `range_within_kind()` is the only way a range is formed. The abstract's 450.27 to 469.64
  range, which ran across all three, is gone. K-Electric is priced for nine years
  (`ke_station_fuel_back_years.csv`: 6.92, 7.21, 7.41, 7.63, 7.13, 7.71, 6.29, 4.86, 4.01
  Mt; three furnace-oil cells printed "n.p." stay typed absences and are estimated beside).
  Whether the national fuel statistic already contains K-Electric's fuel is not established:
  gas ratios favour omission, furnace-oil ratios favour inclusion in four of five years.
- **Coal wording.** The audit's B1 verdict "INFEASIBLE" is now "EXCEEDS SUPPLY UNLESS STOCKS
  FELL": the published account needs a drawdown of 19 percent of the year's supply for power
  alone and 42 percent with the other consumers, and no stock record is held.
  `power_table3_hypotheses.csv` printed "the reference 57.996" three releases after the coal
  re-base; it now reads the reference.
- **Priority 6, uncertainty drivers.** WITHDRAWN: the surrogate Sobol decomposition
  (`national_variance_attribution.csv`), its estimator sweep, the effluent-tail diagnostic and
  `sobol_convergence.csv`, with their modules and tests. It did not decompose the released
  ensemble and its first-order indices summed to 1.325. `outputs/pakemis_uncertainty_drivers.csv`
  (`pkinv.report.ensemble_drivers`) is read from the released draws: each category's
  covariance share of the national variance (they sum to one), its share of the upper-tail
  excess, and the interval with it held fixed. Enteric fermentation 59.8 percent, managed
  soils 14.0, domestic wastewater 9.0. The priority ranking loses its parametric block.
- **The interval.** 100,000 draws: median 446.5, 400.3 to 505.0 Mt (was 406.7 to 532.9).
  Released 10,000-draw ensemble: 399.8 to 505.4; on the same draws under the 2006 wastewater
  method, 401.0 to 524.4. The narrower upper bound comes from the Refinement's range for one
  factor, not from new measurement.
- **A defect in a product of this round, found while writing.** The dung balance's
  falsifiable row divided the diversion by the reference's interpolated quantity while quoting
  one round's user share (79.5 percent, 5.4 times). It is set against that round's own total
  again (72.6 percent, 4.9 times).
- **A held measurement that the re-base would have corrupted.**
  `pakemis_sulfur_adoption_effect.csv` measures what the rc63 sulfur adoption moved, against a
  preserved baseline, and read its other end from `outputs/`. Residential SO2 fell at rc67, and
  a rerun booked that as an unattributed effect of the sulfur adoption (Lahore residential
  "unchanged" became −65 percent). Its candidate is now preserved too
  (`data/baselines/post_rc63_sulfur_adoption/`, the two air products as released at rc66); the
  141 rows are unchanged in value.
- **A hand-run lane the build does not reach.** The residential grid
  (`pkinv.sectors.residential.gis.run_gis`: three rasters, two maps and
  `residential_gis_provincial_2024.csv`) is a held product no build phase writes. It kept
  configuration L after the reference changed, with its registry digests still matching. It is
  rerun on the reference (24.220 Mt, 282.7 kt PM2.5 placed; Punjab 13.69 Mt) and its map
  titles no longer say "configuration L".
- **A second rounding.** `waste_totals_2024.csv` was written at four decimals; at the new
  values its rows summed 1.1e-4 from the engine and two release-integrity tests read it as
  stale. It is written at five, as the other sectors' totals are. Its wastewater row carried
  the disposal row's note ("First Order Decay"); corrected.
- **A guard that a re-base blinds.** `tests/test_figure_literals.py` learned the national
  totals from the live configurations product only, so after a re-base it no longer knew the
  totals a stale literal would hold. It now also reads the totals of every pinned baseline.
  A figure caption in the v3 article still printed the rc66 interval (406.71 to 532.86); it
  was protected only as a repeat of body values and is now a claim of its own.
- **Manuscripts.** v3 `paper.tex` and `technical_supplement.tex`, the v1 national report and
  the sector reports are brought to this account. `versions/v2` is frozen and untouched.
  Passages written with AI assistance are listed in `campaign/v3_readiness/ai_use_record.md`
  (AIP-20) and in `author_actions.md` (AA-027) for the author's own wording.
- **Not done.** The Explorer stays pinned to rc59. Sub-annual and gridded products of
  configuration L exist for the reference year only. The fertiliser feed fraction is observed
  for two years. Whether the two HIES rounds measure the same thing is not established.


## [1.0.0rc66] — October 2026
**Grid power is split between provinces by each year's own stations. A DECLARED PROVINCIAL
RE-BASE; NO NATIONAL PIN MOVES:** L 451.85782 and S 446.72502 Mt CO2e AR5 stand, and the
national total of every fuel, gas and fiscal year is unchanged. This answers the first
priority of the review of the v3 manuscript, which had reported the defect itself.
- **The defect.** One provincial share vector per grid fuel, measured on FY2023-24, was
  applied to all nine fiscal years for coal and gas, to bagasse, and to furnace oil in
  FY2020-21 to FY2022-23 (which booked every tonne to Punjab while Hub and Jamshoro burned
  it; the cube dropped those stations without an event). The manuscript gave the size of the
  worst province-year, 11.6 Mt, and said a per-year split was possible from the same records.
- **The split.** `src/pkinv/sectors/power/province_panel.py` returns, for each fuel and fiscal
  year, the shares that year's stations imply, with the basis, the coverage and any reason
  for falling back. Coal: station tonnage at the rank-default calorific value, which is how
  the national coal account is booked, so the split conserves by construction. Gas, furnace
  oil and diesel: station fuel quantities. Bagasse: generation.
  `downscale.load_shares(period)` asks the panel; with no period it returns the committed
  table, which is now the reference year of a per-year series.
- **The record for FY2015-16 to FY2018-19 was on a page already read.**
  `scripts/ingest_nepra_plant_fuel_quantity.py` reads the fuel-quantity columns of NEPRA's
  2020 State of Industry Report, Tables 16 and 19, beside the generation columns the first
  ingest took, into `plant_fuel_quantity_back_years.csv` (234 station-year-fuel rows; its
  generation equals the earlier ingest on every non-zero cell; 27 of 29 FY2019-20 quantities
  agree with the 2024 report within 2 percent). It reads KAPCO, which the first ingest
  refused. Three misprinted quantities are restored by the station's own ratio in its other
  years (Muzaffargarh's furnace oil reads 92,801.55 thousand tonnes for 289 GWh; the 2024
  report prints 92.8). The report files Narowal Energy under gas and Altern Energy under
  furnace oil, each on the wrong side of a page break; the quantities, Table 5 and three later
  editions say otherwise, and the ingest corrects both with that evidence checked at every
  run. Where no quantity is printed a station is weighted by its generation and its own
  specific consumption: at most 20 percent of a year's gas energy.
- **The test that refused gas was unsound.** rc44 left gas on the reference vector because
  own-year generation scored worse than it against FY2019-20's fuel. The generation panel
  held 47.5 percent of that year's gas generation.
- **What moved.** `outputs/pakemis_power_provincial_basis_by_year.csv`: emissions before and
  after per fuel, year and province, in Mt CO2e (AR5), with the basis and coverage of each
  applied split; the build refuses to write it if any fuel-year's national total differs.
  Largest row: coal, Sindh, FY2020-21, -11.63 Mt CO2e (the stations put 47 percent of that
  year's coal in Sindh and 28 percent in Balochistan; the borrowed vector said 89 and under
  1). Gas in FY2015-16: Punjab 29 percent, not 60. The rig's record is in
  `outputs/pakemis_spatial_rebase_rc44.csv`, net 0.000000000 Mt in all nine periods.
- **The reference year moves, as declared.** Coal's row is now on the booking's calorific
  basis (Punjab 0.0964, Sindh 0.88715, Balochistan 0.01645; it read 0.09734 / 0.89436 /
  0.0083 on per-plant implied values, which the coal reconciliation calls circular): 0.17 Mt
  CO2e moves to Balochistan. Bagasse's row reads 0.712 / 0.248 / 0.040 for Punjab, Sindh and
  Khyber Pakhtunkhwa, not Punjab 1.0: two plants' coordinates and the generation workbook
  contradict the districts Table 5 prints. The reference-year grids, configuration S, the
  provincial air table and the spatial uncertainty products follow.
- **Still borrowed, with the reason:** diesel in FY2018-19 and FY2019-20, where the station
  record covers under half of the national diesel control. Both are wholly Punjab on either
  reading.
- **Not changed:** K-Electric stays outside the split, as outside the national fuel control
  it allocates. Sahiwal's FY2021-22 tonnage and Guddu's assumed gas heating value are used as
  booked and flagged. The nine-year air products are byte-identical to rc65.
- **Retired:** `outputs/pakemis_power_fixed_pattern_exposure.csv`, the comparator that
  measured the fixed vector's exposure. Its header called a column of Mt CO2e "coal mass".
  The station commissioning check stays (`pakemis_power_station_status.csv`).
- **Uncertainty.** The spatial brackets gain `power_coal_provincial_basis`: the applied
  weighting against the one rc65 shipped, 0.8 percentage points at most. The uncertainty
  products have no period axis, so they carry the reference year's split only.
- **Guards.** `tests/test_province_panel.py` (every cell is a split with a stated basis or a
  stated reason; the reference year is the committed row; no station sits in a province the
  split gives nothing; the polygon evidence for the bagasse placements is re-run; the fuel
  record re-derives from the held report) and `tests/test_power_provincial_basis.py` (no
  national total moved, with a positive control). The tripwire in
  `tests/test_power_station_status.py` that asked to be retired "with the re-base" is.

## [1.0.0rc65] — October 2026
**Every cited document held or named, and a held document that cannot disappear. NO PIN
MOVES** and no estimate changes: L 451.85782 and S 446.72502 Mt CO2e AR5 stand. A reviewer
quoted the manuscript's own sentence, "some cited primary documents have not been retained,
and some held validation products have only partial re-derivation checks"; this release is
the answer to both halves.
- **Why they were not retained.** No cited document had been deleted. Of the twenty sources
  the not-retained register listed, three were held all along (the Fatima reports and a FAOSTAT
  extract under `data/raw/`, the Punjab Pocket Book 2025 inside a zip under `sources/`: the
  stale-claim test searched `sources/` file names only), and seventeen had never been saved.
  Fetchers parsed a response in memory and let it go (UN Comtrade, the World Bank API, NASA
  POWER, HydroWASTE, the GEM workbooks, FIRMS); pages were read live. One row described a
  document that never existed (a "private correspondence" with the National Ozone Unit: the
  file is the compiler's own unsent request schema).
- **What is held now.** 542 files entered `data/raw/` with a retrieval record each
  (`RETRIEVALS.csv` per source directory; every attempt in
  `data/raw/ACQUISITION_LOG_retention_2026_10.csv`): the five FAOSTAT bulks as read (copied
  from a gitignored cache; all six tables reproduce), 274 UN Comtrade clinker responses (240
  of 240 rows agree) and six HFC ones (18 of 18), the World Bank and NASA POWER responses
  (both tables reproduce exactly), the HydroWASTE archive and three GEM workbooks served
  byte-identical to their pinned digests, the Zenodo kiln file (publisher md5), the State Bank
  supplement, the JMP country file, the Cherat and three PSX-filed annual reports, the 2023
  census Table 1 workbooks, NASA's keyless FIRMS country-year files (all 523,936 in-window
  Pakistan detections of the fire layer are in them), CDM project pages from Internet Archive
  captures, and the web pages the aviation and fuel-sulfur tables cite. Restored from git
  history: the 103 Climate TRACE responses and the Punjab-industry code archive that commit
  `c3d6ee44` removed in August as "read by nothing".
- **Per document, not per directory.** `data/catalog/cited_documents.csv` (521 rows) names,
  for each document a data file cites, the file that holds it and how that was established.
  An audit of all 135 rows the register called archived found eight files citing a document
  their directory did not contain. The register now reads 149 archived, 52 derived, 12
  not-archived (it read 135 / 51 / 27), and the twelve are real: a priced HDIP yearbook, a
  railway year book the publisher no longer lists, a superseded GEM edition, the 2017 census
  district tables, the FIRMS API responses, two CDM review pages, and pages that are built in
  the browser or gone. Each has its held reprint recorded where one exists.
- **A saved page is not the cited fact.** `scripts/fetch_cited_documents.py --verify` reads
  the held bytes for the words or figures each page is cited for; nine pages are held without
  them and are reported so, never counted as holding the citation.
- **Never deleted.** `data/catalog/document_retention.csv` lists 6,143 documents under
  `sources/` and `data/raw/` and only grows; `tests/test_document_retention.py` fails on a
  missing or changed document, an unlisted one, and any earlier committed version of the
  ledger that listed more. `scripts/raw_data_manifest.py` refuses to write a manifest that
  has lost a listed path, and the `sources/` freeze is now checked in both directions.
- **Keep before parsing.** `src/pkinv/core/retention.py`: a fetcher writes the bytes it
  received, then parses the kept file; a second fetch that returns other bytes is written
  beside the first. Twelve fetchers are held to it, and each gained a `--check` that compares
  the kept document with the table and writes nothing.
- **Validation checks.** Six of the eight hand-run validation products re-derive and compare
  without being overwritten (`src/pkinv/core/checkmode.py`); the held-product ratchets moved
  (unverified 83 to 81, coverage 9 to 21). Two do not, and the registry says why: the
  livestock validation's model card exists in no commit, and the IPPU coordinate agreement's
  producer is not idempotent.
- **What this release does not do.** It adopts nothing from a re-fetched document: where a
  later copy differs from a table the difference is reported (the GEM bioenergy v4 workbook,
  three HFC lines Comtrade now reports), and the table stands. Eight pages still need a
  browser, the HDIP PDFs need the collaborator's archive, and the FIRMS responses need a key
  (`campaign/v3_readiness/author_actions.md`, AA-025).

## [1.0.0rc64] — October 2026
**The rewritten article becomes `versions/v3`; `versions/v2` goes back to what rc62 shipped. NO
PIN MOVES** and no product changes: L 451.85782 and S 446.72502 Mt CO2e AR5 stand. This release
moves files and the names that point at them.
- **`paper_national/versions/v3/`** holds the rewritten article, its review layout and its
  technical supplement, with the eight redesigned figures (`figures/f01_…f08_*.pdf`). It is
  what `versions/v2` was at rc63, unchanged in text. Everything that built, patched or checked
  the article follows it: the Makefile targets (`figures-v3`, `paper-v3`, `paper-v3-review`,
  `paper-v3-supplement`, `papers-v3`), the figure phase and the five generated tables, the mint
  script, the release-identity registry, the claim registry's document key (`national-v3`) and
  the document guard (`tests/test_v3_documents.py`).
- **`paper_national/versions/v2/` is the article as release 1.0.0rc62 shipped it**: the text
  before the figure redesign and the seven figures it printed (`figures/fig1_…fig5_*.pdf`,
  `fig_ghg_grid.pdf`, `fig_ghg_grid_evidence.pdf`), restored byte for byte from the rc62 record
  commit. At rc63 the redesign had overwritten it in place, so the two could not be compared.
- **Frozen is a digest.** `paper_national/versions/FROZEN.csv` lists the twenty files with their
  release, commit and SHA-256; `tests/test_frozen_versions.py` holds the tree to it, fails on a
  file added to a frozen version, on a builder that still names one, and on a release record
  that hashes a different PDF. v2's three PDFs carry the digests rc62's own record published.
- **What v2 does not promise.** Its `.tex` inputs the shared macros, the generated release cover
  and the gridded-figure provenance text, which follow the current release; the PDFs are the
  record, and rebuilding them means checking out the commit the register names.
## [1.0.0rc63] — October 2026

**The figure redesign, the activity query, and three labels corrected at their source. NO PIN
MOVES**: L 451.85782 and S 446.72502 Mt CO2e AR5 stand, and no estimate in any product changes.
One column of one product is relabelled; the manuscript gains a figure and loses none of its
numbers.

- **Eight manuscript figures on one style.** The seven main figures of the v2 manuscript were
  drawn by three scripts with three palettes and placed by LaTeX at a width and a height cap: a
  single-column figure doubled in the review layout (16.9 pt labels) and a five-panel plate was
  shrunk to 4.6 pt in one layout and 5.2 pt in the other. `src/pkinv/report/manuscript_style.py`
  now sets two widths from the class, 7.5 to 10 pt type, one embedded font, one colour per
  meaning and one glyph grammar (diamond: deterministic estimate; tick: ensemble median; bar:
  percentile interval; open circle: alternative). Every figure is drawn at its printed size and
  both layouts place it at scale 1.0000. The evidence plate is split, so there are eight
  figures, named `f01` to `f08` as the journal asks. The reference study, figure inventory,
  change log, colour-vision simulations and before/after sheets are in
  `paper_national/figures/redesign/`.
- **Figure 1 is the pipeline's graph.** The monthly grid has both of its inputs, the province
  and district tables are on the page, the unallocated account sits beside the spatial
  products, and no quantity is printed in a node that stands for nine years.
- **No plotted value moves.** `scripts/verify_manuscript_figures.py` re-reads 243 plotted
  values from the released products, through neither plot-table builder; none disagrees.
- **Surface labels corrected at the product.** `surface_vintage` in
  `pakemis_spatial_weights_by_year.csv` called the cropland surface "SPAM 2020"; it is ESA
  WorldCover 2021 (class 40). The MapSPAM rice surface, the OpenStreetMap road and rail
  networks, the derived manure surface and the fire detections carried no label, so the figure
  filed a quarter of national CO2 under "point set or ADM2 panel". 495 rows of one column.
- **Three statements withdrawn.** "Every raster predates the fiscal year it places" (the roads
  are an extract of August 2026); "all in-country cells are strictly positive for every gas"
  (2,835 valid cells hold exactly zero N2O, now drawn as their own state); and, in a plot
  table, that the BTR comparison needs no harmonisation, which its own product denies: the
  ratio at a uniform CH4 weighting of 28 is carried and drawn where it moves a point.
- **Running sums in float64.** The concentration table reached 100 % of CH4 at 33,039 of
  33,674 cells because the cube's float32 was summed as float32; the worst closure residual
  falls from 0.111 to 0.032 ppm.
- **The figures are built.** Figures 1, 2, 3, 7, 8 and their plot tables were in no build phase
  and no Makefile target. `make figures-v2` builds all eight and runs the value check;
  `make papers-v2` also compiles both layouts and the supplement. Guards cover every figure and
  fail on a missing one; release identity is read from PDF metadata instead of plot text.
  `xarray`, imported by a build phase, is declared.
- **`query_activity`.** A typed read of the seventeen activity tables (vehicle registers,
  livestock, crops, fuel sales, generation and the rest): each row as its source printed it,
  with measure, class, place, period, unit, evidence class, source series, use note and its
  row in the deposit. One arithmetic is offered, a total over the classes of one place at one
  date, refused wherever the release marks rows as not to be combined. A period or place the
  release does not hold is refused with what it does hold.
- **The deposit build group** and the measured account of what the deposit can rebuild
  (`docs/deposit_rebuild_limits.md`: 156 of 195 phases, five causes).

Known and left for the next release: the activity table labels the vehicle class 4W1 "Small
cars" where, for registered vehicles, the row is the register's whole class of motor cars, jeeps
and station wagons; and the vehicle rows' source reference points at a workbook sheet instead
of carrying the publication, table and address that sheet holds.


## [1.0.0rc62] — October 2026

**The v3 submission-readiness pass against the 23rd review's PDFs. NO PIN MOVES**: L 451.85782
and S 446.72502 Mt CO2e AR5 stand; every change is a product added, a label corrected, a figure
regenerated from the products, or a guard that now exists. The campaign record (findings,
evidence, decisions, author actions, change impact) is under `campaign/v3_readiness/`.

- **Release identity.** The gridded figures are a build phase (`Gridded figures`) and `make
  figures` runs them, so a version bump regenerates them; a test holds every figure PDF's text
  layer and the provenance JSON to `__version__` (rc59/rc60/rc61 had been shipped together).
  The unallocated mass is printed per gas (CH4 0.001741 Gg and N2O 0.006963 Gg were printed
  as 0.0); 0.251 Mt is stated as the three-gas CO2e it is, beside 0.24946 Mt CO2.
- **Conservation by gas.** `scripts/check_conservation.py` recomputes eight identities by gas
  (monthly = annual = atoms; ADM1 across views = annual; ADM2 + unallocated = ADM1; the
  nine-year series; typed notation keys) and is in the suite with a positive control.
- **Seven products.** `pakemis_power_station_status.csv` and
  `pakemis_power_fixed_pattern_exposure.csv` (the GEM commissioning check: no station carries
  coal outside its window; the FY2023-24 provincial vector differs from each period's own pool
  by up to 11.63 Mt in a province-year, 0.17 Mt in the reference year);
  `pakemis_spatial_basis_{classes,shares,shares_by_sector}.csv` (the evidence taxonomy by
  mass, 61.5 / 30.9 / 7.5 / 0.06 percent for FY2023-24, classes defined in plain words);
  `pakemis_comparison_crosswalk.csv` (the terms of every external comparison);
  `pakemis_dung_residual_ledger.csv` (the 46.77 Mt residual as 1,003 kt N and 30.9 Mt VS by
  species, the species split declared as an assumption); `pakemis_enteric_btr_bridge.csv`
  (enteric CH4 by species against the BTR's Figure 1: four species identical, the whole 21.7 Mt
  in buffalo and other cattle, 1.82 Mt BTR-only). All comparator-only; nothing reads them.
- **Engine.** `wastewater.n2o_gg` carries `ww_n_sludge_kg` explicitly (IPCC 2006 Vol. 5 Eq. 6.8,
  default zero), so the supplement's "no sludge term" is corrected to "at its default of zero"
  and the parameter is in the uncertainty register. `docs/waste_fod_worked_example.md`
  reproduces `ddocm_accumulated(2023)` to the printed Gg.
- **Reconciliation.** Six basis columns on `pakemis_power_fuel_reconciliation.csv` (calorific
  basis, moisture basis as stated by the source, gross/net generation, rank weighting,
  reporting period, GEM station status). The 45.6 vs 45.7 pair is explained: the
  configurations' C3 includes the 77.56 GWh commissioning lane, the adjudication's plant route
  does not.
- **Manuscripts, corrections only.** The BTR inventory year is FY2020-21 (the CRT's calendar
  2022 is a different table); the 32.4–45.7 % range is the heat-rate configuration's; the
  Figure 3 caption prints the endpoint shifts (−0.06 / +0.34 Mt); 0.2678 is stated as an
  engine numerator over the surrogate denominator and removed from the ranking, with the
  "largest driver" sentence deleted; "None rescues it." is a generated table
  (`tab:coal_audit`); the livestock inputs are a generated table (`tab:livestock_factors`);
  the five-class validation table and the GB/AJK/ICT definition table are added; six
  phrasing edits (release commentary) are listed in `campaign/v3_readiness/assistive_edits.diff`.
  Figure 2 gains the full-period change intervals; Figure 5 gains a qualified panel for the
  fourteen subjects that are not ratios; the uniform reference in Figure 6 is sampled on the
  symlog axis; `placeins` keeps every figure before the references in the one-column build.
- **Guards.** Positive code sweep (every shipped code is authored in `completeness.py::ROWS`
  or a sub-leaf of one); generated-table byte identity; Figure 1 per-gas closure; the
  post-meter base's two definitions pinned equal; twelve registered claims for the new numbers.
- **Editorial rewrite of the article at the author's instruction (8 October brief).** The period
  is defined once ("nine fiscal years from July 2015 to June 2024") and the title carries it;
  the abstract is self-contained; the Introduction opens on the records problem; Sect. 2.2
  states the reference public-power coal calculation; Sect. 2.4 separates parameter
  uncertainty, source-interpretation alternatives and unestimated categories; Sect. 3.1 names
  calculation modules and states the change with its three dependence settings; Sect. 3.2 is
  "Uncertainty and allocation evidence"; Sect. 4 is four comparisons (transcription checks,
  the BTR and EDGAR, the coal supply bound stated conditionally, facility locations), with the
  provincial SO2 comparison in Appendix A; Sect. 5 opens on what users receive; the
  Conclusions give the contribution directly; the availability statements are concise and the
  release cover follows them. Seven figures: the construction schematic is a routing diagram,
  the BTR comparison stands alone with its non-ratio subjects as a table, managed soils is its
  own figure, the grid figures carry only the dataset version and the evidence figure gains
  N2O. Every number is preserved and registered (70 claims re-anchored, 31 added). The practice
  is written down in `paper_national/writing/sub.md`.
- **Not done, and said so** (`campaign/v3_readiness/author_actions.md`): the functional DOI and
  review link; the 500-character summary; the AI-use declaration per passage; the ammonia
  process factor (absent everywhere; the `fugitives_excluding_feedstock` row already prices
  the scope); the per-year provincial coal re-base (now measured, not done); the cause of the
  buffalo gap against the BTR.

## [1.0.0rc61] — October 2026

**The remainder of the 23rd review's item 6. NO NUMBER MOVES AT ALL**: the pins stay at
L 451.85782 and S 446.72502 Mt CO2e AR5 and no product changes except the version stamps.

- **The four deferred source questions are named open items now, ranked by what each would
  move**, which is the reviewer's own instruction to prioritise by influence rather than by
  ease. Managed soils is the largest: the reference books 28.53 Mt CO2e in FY2023-24 while
  two factor substitutions inside the same method give 40.43 and 54.72, and FAOSTAT reports
  58.50 - the choice of emission factor alone spans more than the whole waste module. The
  livestock bridge is next by variance: enteric fermentation is 58.0 per cent of the
  Approach 1 category screen and runs 1.19 times Pakistan's own submission for FY2020-21,
  while manure management from the SAME herd runs 0.99, so the disagreement is about factors
  rather than about the animal population. Crop residues carries the panel's largest
  relative gap at 0.18, against a wider aggregate than the inventory's own row. Solid-waste
  specification moves its row by about a factor of two: disposal 0.49, the broader fate
  account 0.68. Every ratio resolves through pakemis_btr_comparison.csv by subject, so the
  paragraph that ranks them cannot drift from the comparison it ranks them by.
- **The wastewater sludge term is restated as the DEFAULT ZERO it is.** The companion said
  "sludge is largely not collected in Pakistan ... so there is no sludge stream to deduct",
  which reads as a demonstration; no measurement of sludge removal is held. The grounds -
  near-absent centralised treatment, and a Tier 1 equation that carries no sludge term -
  make zero the defensible default and do not establish that no nitrogen leaves as sludge.
  What would settle it is named, and its direction stated: a deduction could only reduce
  that row.
- **mint_rc61.py derives the dashed CITATION.cff spelling from OLD/NEW** instead of carrying
  it as a literal pair. The pair had been copied from mint to mint, so this script inherited
  rc59->rc60 while its own OLD/NEW said rc60->rc61 and reported the site "already applied"
  when nothing had touched it. The whole mint_rc* family differs only in two strings and a
  changelog body and should be collapsed into one parameterised producer.

## [1.0.0rc60] — October 2026

**The 23rd review's work order, items 1 to 7. NO NATIONAL NUMBER MOVES: the pins stay at
L 451.85782 and S 446.72502 Mt CO2e AR5.** The round's subject is consistency and evidence,
not magnitude — a substantial revision had shipped at rc59 without being propagated, so the
methods said 57.82 where the results said 40.04 and the gridded figure printed a pin from
before the coal re-base.

- **A test that ran zero tests, and the gap it was hiding.**
  `tests/test_power_fuel_reconciliation.py` was written against a design rather than the
  module: it keyed on `row_kind`, `evidence_grade`, `mass_lo_kt` and `source_table`, none of
  which the producer writes, so `setUpClass` raised `KeyError` and unittest counted the class
  as one error while running none of its seven tests. Rewritten against the shipped `FIELDS`
  it immediately closed on generation and found four years whose CPPA-G coal generation no
  station row placed — FY2016-17 873.17, FY2017-18 11,783.11, FY2018-19 538.24 and FY2021-22
  77.56 GWh. `coal_plant_fuel_back_years.csv` had named the first two in its own header for
  releases and said this product reconstructs them; it did not. They are now a declared
  `plant_coverage_class = unplaced generation` row per year with `quantity_class =
  not_estimated` and a typed-absent mass. **No mass is invented**: a diagnostic gap is never
  inserted as a residual. Every new test file carries a schema check against the producer's
  own `FIELDS` so the same drift fails loudly instead of silently.
- **`--check` could not pass in any tree** (`fuel_reconciliation.py`): it rebuilt the
  expected text by hand instead of calling `core.io.table_text`, and read the held file in
  text mode, where universal newlines collapse CRLF to LF — so a CRLF product came back 59
  characters shorter than it is on disk and compared unequal to itself.
- **The coal account, reproducible by an outsider.** The reconciliation now spans all nine
  years (58 rows), typing metered quantities apart from derived ones and publishing both
  energy bases in separate columns. The matched-boundary arithmetic enters the article: the
  aggregate control needs **29,531 kt** of coal in FY2023-24 against the **24,719 kt** the
  national accounts report as imports plus production — 119.5 per cent of everything supplied
  — while the station account the reference uses needs **15,876 kt**, 64 per cent of the same
  supply and below the 19,196 kt the energy yearbook books to generation.
- **External comparisons state their metric.** `pakemis_btr_comparison.csv` gains a
  harmonised view: this inventory weights fossil CH4 at AR5's 30 and the BTR prints AR5 CO2e
  per gas with no native mass, so its own weighting cannot be recovered. Both readings ship.
  1.B.2 is where it bites — 100 per cent of its CH4 is fossil and fossil CH4 is 96.2 per cent
  of the category's CO2e — and the ratio moves 7.27 as published to **6.80** harmonised; the
  national ratio 1.008 to 1.004. The claim that the comparison "needs no harmonisation" is
  deleted from the builder, the product banner, the figure script and the caption.
- **Uncertainty says what kind it is.** The wastewater ceiling is relabelled a
  **parameter-ceiling** scenario, not a structural endpoint — it is the ceiling of a
  parameter's own sampled support. Its exceedance frequency is reported as the Monte Carlo
  estimate it is: 12 of 10,000 draws, with an exact binomial 95 per cent interval of
  **0.062 to 0.210 per cent**. A stable sum of total-effect indices is stated not to
  establish converged individual rankings.
- **Two evidence results that were cited without being given.** The paddy crosscheck against
  the own-year 30 m classified-paddy raster: 76 of 126 districts agree within 2.0 pp, and per
  province the share of rice mass the instrument would place in different districts is
  25.3 (Punjab), 38.0 (Sindh), **62.3** (Khyber Pakhtunkhwa), 34.3 (Balochistan) and 41.5 per
  cent. And the gas deduction's boundary: it applies to **delivered, post-meter** gas and
  never to gross supply; 6 of 9 streams carrying 71.0 per cent of the volume are inside the
  base, and fertiliser **feedstock** — outside every combustion module — is inside it at a
  combustion-derived factor and is 31.0 per cent of that base.
- **The dung question is an assignment question** (`pakemis_dung_balance.csv`, new): L is all
  excreted nitrogen leaving manure management for any burner, S is formed cake entering a
  sampled dwelling, and the table states the asymmetry term by term with a comparability
  verdict on each. Configuration L is falsifiable: it requires either 72.6 per cent of
  weighted households to burn cake against the 14.79 per cent observed, or those that do to
  burn 4.9 times the observed daily quantity. No residual is distributed.
- **The provincial control's own basis, stated.** Each grid fuel carries a share vector from
  the FY2023-24 plant ledger joined to the curated station record, energy-weighted — so the
  control already reads station records rather than the raster, which is why the seven raster
  misplacements never entered it. There is **one vector per fuel and all nine periods reuse
  it**. "Other" is named as Gilgit-Baltistan, Azad Kashmir and Islamabad Capital Territory.
- **Transport's `accounting` justification was stale, not its verdict.** Since rc47 Wave 5 the
  sha-pinned OSM road raster is the within-province basis for petrol and diesel; the
  `view_reason` still said the road geometry was "not held as an allocation basis" and that
  highway fuel was under-represented "by the built-up surface". The verdict is unchanged and
  rests on the ADM1 marginal being a point-of-sale statistic, which no within-province surface
  can change. The same staleness is corrected in every row of
  `pakemis_road_weights_adm2.csv`; its shares are byte-unchanged and the raster's digest is
  identical.
- **The figures fit a page.** The gridded figure was 11.60 x 16.00 inches, larger than both
  Letter and A4 in both dimensions. It is split into a three-gas map and a separate evidence
  figure, each 7.2 inches wide, with an assertion that every figure fits; the 24-line 6.3 pt
  provenance block that forced the height is now generated LaTeX the companion inputs.
  Figure 3(b) had `xlim(411, 568)` against a plotted low of 406.71, so the interval's cap and
  label were never drawn and ticks starting at 425 hid the truncation — the limits are now
  derived from the data with an assertion that nothing plotted falls outside. Figure 4 was
  too short for its own labels and a `[:46]` slice had cut a subject name into a different
  claim.
- **Guards for the classes, not the instances.** A figure script may not hold a release pin
  as a literal; a manuscript may not name a release version that is not this one (the
  availability statement said rc59 while the engine had moved); `run_all`'s `reads` outside
  `data/` must be declared `held:`; and the Residential phase's two undeclared writes
  (`residential_dung_ledger_2024.csv`, `residential_hies_comparison_2024.csv`) are declared,
  so a later phase may legitimately read them.

## [1.0.0rc59] — September 2026

**The four things rc58 declared and did not build, in one mint. NO NATIONAL GREENHOUSE-GAS NUMBER
MOVES; the air panel's totals do.** IPPU process pollutants and fugitive NMVOC with flaring enter the
covered air panel as provisional estimates from the same source-class register industrial combustion
rides; the brick classes ride their own kiln-type frames in the spatial sink; the seventeen readable
activity tables carry one id, not two. The air PM2.5 pins move by exactly the two layers' particulate
(771.482 -> 771.873 Gg REF; 429.845 -> 430.235 S; the residential-only difference 341.637 is
unchanged); the covered NOx headline FY2022-23 moves 814.03 -> 819.81 kt.

- **The register is cross-module** (`data/air_source_classes.csv`, moved from
  `data/activity/industry/`; 40 classes over 19 physical sources): `computing_module` and
  `reporting_sector` now span industry, ippu and fugitives; the executor learns `ippu.nh3_kt`,
  `ippu.billets_kt`, `ippu.qim_tonnes:<item>`, `fugitives.activity:<anchor>`, `fugitives.flare_bcm`
  (the satellite calendar volumes blended half-and-half to the fiscal year, basis `calendar_blend`) and
  `transport.ocac_tonnes:MS:TOTAL_INTERNAL`; the factor loader learns per-product, per-gas-volume and
  per-oil-volume units. Whole-activity classes may coexist as DISTINCT PROCESSES on one quantity
  (refinery process species and refinery flaring both ride the feed); partitions still sum to one.
- **Acquired** (public, `data/raw/emep/`, `data/raw/epa_ap42/`, every attempt logged): EMEP/EEA 2023
  2.B (consolidated: 2.B.1, 2.B.2, 2.B.10.a), 2.B.7, 2.C.1, 1.B.2.a.i+b, 1.B.2.a.iv, 1.B.2.a.v,
  1.B.2.c; AP-42 13.5 (the 1995 reformat - the 2018 address 404s). AP-42 8.2 (urea) could not be
  fetched: every epa.gov address returned 403, logged. 52 factor rows added (163 total), each with page
  and digest; the inadmissible ones (2.B.10.a sector ratio for urea; 2.C.1 Tier 1 for the electric
  route; AP-42 13.5 heat-basis rows) are HELD, NOT CITED, with the reason on the row.
- **IPPU** (FY2023-24 NOx 5.1 kt, CO 15.9, NH3 0.75, PM2.5 0.10): ammonia synthesis on the NFDC
  tonnes behind the greenhouse-gas ammonia stream (2.B.1 Tier 1); electric-route steel on the QIM
  billets behind the steel stream (2.C.1 Tier 2 electric-arc rows, 200 percent declared on the
  particulate so the band reaches the uncontrolled Tier 1 held beside); Solvay soda ash on the QIM item
  read by name (2.B.7; no greenhouse-gas stream exists, the general-industry gas vector is a DECLARED
  geography proxy). Urea finishing, nitric acid, lime and glass are typed absent with their activity
  beside them; cement process particulate is an explicit IE pointer into the integrated kiln (gap
  air-ippu-cement closed).
- **Fugitives** (FY2023-24 NMVOC 80.3 kt, SO2 3.6, CO 1.2, NOx 1.2, PM2.5 0.29, BC 0.06): NMVOC per
  segment on the module's own volumes - gas exploration/production/processing on gross production
  (one summed factor, applied once), transmission and distribution on transmission throughput (one
  summed factor), domestic crude at the chapter's 1.16 m3/t, refining and storage on the module's
  refinery-feed proxy (the other-regions row; NOx, CO, SO2 and particulate from process units beside
  it), petrol depot, delivery and refuelling on OCAC's motor-spirit total (uncontrolled, the chapter's
  instruction for countries without Stage I/II; vehicle-side evaporation stays in transport). Field
  flaring on the satellite volumes at 1.B.2.c Tier 1 (density 0.85 kg/m3; SO2 at the chapter's 6.4 ppm
  because no flare-gas sulfur evidence is held; BC 24 percent of PM2.5 with its own wide range);
  refinery flaring per m3 of feed. Venting, post-meter NMVOC and LNG terminals are typed absent (gaps
  air-fugitives-venting, -composition, -segments; air-fugitives-flaring closed).
- **The kiln-frame override is honoured** (`pkinv.report.kiln_frame_vectors`,
  `pakemis_kiln_frame_adm2_by_type.csv`): the FCBK and zig-zag classes ride their own kiln-type frames
  (FCBK 9,959 kilns, hash d833193a0ff77be5; ZZ 1,329 incl. Balochistan's 16 pooled kilns, declared,
  hash 2589e78ae487f7fd), province marginal equal to the brick stream's shares by construction so ADM1
  does not move; the coal outside the surveyed frame is placed at ADM1 and typed unallocated below it
  (a second typed below-ADM1 class beside aviation cruise, 90 rows). The support ledger gains
  `spatial_frame` with each frame's own hash.
- **`result_row_id`**: the seventeen readable activity tables declare `id_column: Record ID`
  (`semantic_release.json` records it; the build asserts uniqueness) and carry one id.
- **EDGAR** (`pakemis_industry_air_edgar_comparison.csv`, two new column sets; catalogue rows
  mag-ippu-air-edgar, mag-fugitives-air-edgar): FY2021-22 fugitives NMVOC 1.46x EDGAR's 1.B.2, CO 0.98x;
  ippu NOx 1.26x EDGAR's 2.B+2.C; the flare sulfur and particulate and the ippu CO compare an estimate
  with EDGAR's near-absence (ratios in the tens to hundreds) and rank neither. Compared, never fitted;
  the registers are byte-identical across it.
- **Coverage**: ippu E for all seven core species; fugitives E for six (NH3 typed absent, the chapters
  decline it); nine new gap rows, two closed; the completeness ledger, supplement, limitations, release
  limitation texts, the query engine's air sectors and the assurance figure follow, held together by
  `tests/test_air_prose_drift.py`.
- **Renamed**: `industry_air_pollutants_fy2015_16_fy2023_24.csv` ->
  `pakemis_air_source_classes_fy2015_16_fy2023_24.csv` (+ `sector_id`),
  `pakemis_air_industry_uncertainty_by_year.csv` -> `pakemis_air_source_class_uncertainty_by_year.csv`,
  semantic `fact_air_industry` -> `fact_air_source_classes`.

**Industrial combustion enters the covered air panel. NO NATIONAL GREENHOUSE-GAS NUMBER MOVES; the air
panel's totals do.** Through rc57 the air panel covered six sectors and typed industry, IPPU and fugitives
NE, so "the largest source" of PM2.5 meant the largest of six. The assistant said it bare. The user's
admission rule - a defensible activity basis, an applicable factor for the actual source class, an explicit
process boundary and documented assumptions, with uncertainty - is now met source class by source class,
and the result is inside the panel as a provisional estimate: FY2023-24 industry NOx 143 kt, SO2 138 kt,
CO 99 kt, PM2.5 13.3 kt, NMVOC 11.7 kt, BC 5.5 kt, uncertainties 47-70 percent. The air PM2.5 pins move
by exactly that (758.219 -> 771.482 Gg REF; 416.582 -> 429.845 S; the residential-only difference 341.637
is unchanged).

- **Every factor chapter the earlier screening called "not held" was public and is now held**
  (`data/raw/emep/`, `data/raw/epa_ap42/`, `data/raw/edgar/`; every attempt logged in
  `data/raw/ACQUISITION_LOG_industrial_air.csv` - the first-guess addresses all 404'd). EMEP/EEA 2023
  1.A.2, 2.A.1, 2.A.2, 2.A.3, 2.A.5.c, 2.A.6; AP-42 1.3, 1.4, 3.2, 3.3, 3.4, 11.3, 11.6, 11.17; EDGAR v8.1
  SO2, CO, NMVOC, NH3, BC.
- **`data/air_emission_factors.csv`**: 111 factor rows as their sources print them - unit, activity basis,
  equipment, control state, particulate basis, sulfur/ash scaling, rating, document, table, page and
  digest. A held row without a page fails the build; an absent row is a typed NE a class may cite.
- **`data/activity/industry/industrial_air_sources.csv`**: 22 source classes over six physical sources
  (`data/physical_sources.csv`), each burning the ENGINE's own quantity - OGRA gas, OCAC liquids, HDIP coal,
  the cement engine's clinker, the power module's captive gas. Shares of one activity sum to one (tested);
  declared shares say so and name the acquisition that would replace them. Control posture: source-class
  typical (cement kilns carry the particulate collection inherent to clinker production; boilers, engines
  and brick kilns are uncontrolled).
- **SO2 is a sulfur balance on DATED evidence** (`data/activity/industry/fuel_sulfur_evidence.csv`): the
  HSFO grade mix, the diesel regime by year, Punjab coalfield ranges for brick coal. Thar lignite - the
  rc57 screening's proxy for every fuel - is inadmissible for brick and cement coal by register. A class
  whose evidence is not valid for a year gets a typed absence for SO2, never a zero.
- **Double counting refused by construction**: cement gas and HDIP's cement-coal column are IE into the
  clinker-based integrated kiln (a kiln is never also a boiler); captive oil is IE into the OCAC liquids;
  captive gas is priced once, under industry (IPCC 1.A.2), and the power screening is grid-only; the three
  brick classes (FCBK, zig-zag, outside the surveyed frame) partition HDIP's brick coal exactly.
- **Typed absences with their activity beside them**: NH3 for every fuel (EMEP lists it not estimated),
  other-industry coal inside HDIP's cement column, captive solids, industrial bagasse - five new gap rows.
- **The coverage matrix's absences are data** (`data/air_coverage_absences.csv`); a cell nobody types fails
  the build. Six descriptions of the layer that disagreed (matrix, ledger, axis, power table, supplement,
  limitations) are held to each other by `tests/test_air_prose_drift.py`, written to fail on rc57.
- **Three views**: Lahore District by sector beside the national unplaced remainder
  (`pakemis_air_lahore_by_year.csv`), calendar 2023 composed from two fiscal years on the monthly cube's
  own shares (`pakemis_air_industry_cy2023.csv`), and EDGAR v8.1 at matched years - a comparison, never a
  fit; the registers are held byte-identical across it (`pakemis_industry_air_edgar_comparison.csv`:
  FY2021-22 NOx 1.14x, PM2.5 0.65x, SO2 2.35x, CO 0.19x EDGAR's fossil 1.A.2).
- **Retired**: `industry_air_screening_fy2015_16_fy2023_24.csv` and its module; superseded by the estimate.
- **Declared, not yet built**: the kiln-frame spatial override (FCBK/ZZ typing of the kiln-point pattern;
  the unmapped remainder typed unallocated below the province) - rc59, with IPPU process pollutants;
  fugitive NMVOC and flaring - rc60.

**The activity tables in a reader's shape. NO NATIONAL NUMBER MOVES.** The seventeen `fact_activity_*`
tables published in rc55 and rc56 answered the six questions in a machine's vocabulary - `head_count`,
`kha`, `province_by_locality`, a period `2014` whose meaning depended on the sector. They now read
`Period · Location · Measure · Animal type · Value · Unit · Period type · Location level · Evidence ·
Source series · Use note · Source reference · Record ID`, following the reshaping the user did by
hand and checked row for row. All 101,808 rows and every value are unchanged; a test joins each
readable row to its technical row and asserts it.

- **One companion table, `fact_activity_source_details`**: the twenty technical fields of every row,
  verbatim, under the same Record ID. The readable table is a view; this is the record.
- **One data dictionary, `dim_activity_columns`**: what every column of every readable table means.
- **The labels are registers, not code.** `data/activity_measures.csv` (what a variable is called),
  `activity_units.csv` (units spelt out, never rescaled), `activity_labels.csv` (the labels the
  mechanical default gets wrong: HSD, 2W, SNGPL), `activity_collections.csv` (each table's public
  shape), `activity_use_notes.csv` (the conditional caveats), and a `label` column on the evidence
  vocabulary. A value with no register entry fails the build naming it.
- **Every fiscal period is now spelt one way.** A bare year meant two different things in the tree -
  a railway `2014` is FY2013-14 and an airport `2006` is FY2006-07 - and the sector engines had
  always declared which. `fiscal_convention` carries that into the publication, so every fiscal
  period reads FYyyyy-yy, every month yyyy-mm, and a vehicle stock counted at 30 June carries the
  date it was counted. A bare year the publisher cannot resolve fails the build.
- **Six defects in the rc56 export, found by the user's review and fixed upstream rather than
  mirrored.** Three were one bug: the melt's own labels overwrote a declared category column, which
  is how 5,445 aviation rows lost their airport and 235 lost their airline. The airport is now the
  place it always was, at airport level. OCAC's per-row additivity flag is published on every area
  row (12,500 rows are not additive; the rule used to name the flag and withhold its value). NFDC's
  monthly plant gas carried a month with no year while the file had a year column. The livestock
  following-year projections sat under the base year. HIES waste-service provinces sat in the
  subcategory while the location said Pakistan - and the same national-marker rule that fixed them
  fixed 7,700 OCAC PAKISTAN rows levelled as a province. The provenance of a plant-month's fuel label
  was welded into the fuel itself; it is provenance, and it travels as such.
- **Crop districts are named, not coded.** `kp_bannu` is Khyber Pakhtunkhwa · Bannu District, from
  the canonical district registry; every district row carries its province.

**The activity publication finished: all nine collections, and the sector data beside them. NO
NATIONAL NUMBER MOVES.** rc55 published six collections; this adds the three it left pending -
industrial fuel and production, the gas tables, waste services and waste flows - and the three
datasets that belong in their sectors without a card of their own: railway fuel and traffic, airport
movements and passengers, and registered vehicles by district. Seventeen tables, 101,808 rows.

- **Nine new tables.** `fact_activity_industry_fuel`, `..._industry_production`, `..._gas_supply`,
  `..._gas_network`, `..._waste_services`, `..._waste_flows`, `..._railways`, `..._aviation`,
  `..._vehicles`.
- **A seventh evidence class, `modelled`**, and it is the first row in this collection that is not
  something a publisher printed. The waste flow ledger is a per-capita rate over an interpolated
  population panel and a fate partition; typing it `reported` would have been the most damaging
  label in the release, and the household survey published beside it reads a different split.
- **The separations this wave had to carry.** Printed TOTAL rows are withheld rather than published
  beside their own members, which is what a declared row filter is for. Unaccounted-for gas carries
  its source's own words - NOT AN EMISSION FIGURE AND MUST NEVER BE USED AS ONE - onto every
  published row. Registered vehicles are cumulative stock as at 30 June, not observed traffic and
  not an active fleet. The HIES `collected` and `uncollected` rows are sums of routes 1-3 and 4-7
  and are typed `derived`, not published as an eighth and ninth category beside their own parts.
  Company clinker is company-reported and is never allocated to plants, because nothing in this
  release allocates it. Aviation counts its fiscal year from the START, the opposite of the railway,
  waste and transport tables in the same collection, and the period basis says so on every row.
- **The feedstock/fuel split, which exists nowhere else.** Gas a fertiliser plant turns into ammonia
  is not gas it burns; NFDC prints them separately and this is the first release to publish the
  distinction.
- **What is deliberately NOT published.** Ten IPPU and industry working files - source manifests, a
  gap matrix, a readiness diagnostic, geocoding overrides, a plant register, a self-declared
  screening table and a third-party emissions series - are measurements of nothing. The PBS minerals
  panel is withheld because the file carries no unit anywhere and its mineral labels are uncleaned
  OCR, including one cell holding an entire unparsed table row. The QIM panel is filtered to the
  four mapped items on quantity rows: its index rows are index points on a 100 base, and 108 of them
  carry a one-column shift from the extraction.
- **UNEP MARS stays out.** The plume and source tables carry `LICENSE-CC-BY-NC-SA.txt` in their own
  banners - non-commercial and share-alike, incompatible with this release's CC-BY-4.0 either way -
  and the manifest already records them as rights-undetermined, evaluation-only.

**The activity data behind the estimates, published so it can be used on its own. NO NATIONAL
NUMBER MOVES.** Someone who wants Pakistan's livestock counts, fuel sales, fertiliser offtake or
plant-level generation should not have to run an emissions engine to get them, or be studying
emissions at all. Six collections leave the ingest tree as eight tables, 79,676 rows, under one
declared vocabulary.

- **Eight new semantic tables.** `fact_activity_fuel_sales_national` and `..._area` (OCAC's
  customer-class and monthly area pages, kept apart because OCAC never prints their joint
  breakdown), `..._livestock`, `..._crops`, `..._fertiliser`, `..._power_plants`,
  `..._power_monthly` and `..._household_fuel`. Each carries its aggregation rule and, in
  `closure`, the sentence a reader needs before adding two rows together.
- **Every row answers six questions on its own**: what the quantity is, where and when it applies,
  what kind of evidence it is, where it came from, what this project changed, and whether it may be
  combined. The ingest tree could answer none of them uniformly - 167 files, 937 distinct column
  names, 705 of them appearing exactly once, units baked into column names and status spread over
  more than sixty columns.
- **The judgements are five registers, not a melt function.** `data/activity_files.csv`,
  `activity_columns.csv`, `activity_evidence_classes.csv`, `activity_evidence_map.csv` and
  `activity_item_map.csv`. Every mapping from a source status to an evidence class carries its
  reason, because a judgement buried in code is one nobody can review.
- **An unmapped status fails the build.** Nothing falls back to `reported`: falling back is how
  `verified` - a statement about this project's TRANSCRIPTION, not about what the publisher offered
  - would come to be published as `observed`. The source's own word survives beside the class.
- **The separations that make the tables safe to reuse.** Tonnes of fertiliser product are never
  tonnes of nitrogen (an earlier draft of the register published all five of the 2024 nutrients as
  `t N`, which would have restated 996,000 t of phosphate and 6,579,000 t of urea product as
  nitrogen). Monthly power is GENERATION - the source never measured fuel monthly. A pooled
  district split by a declared rule is an ALLOCATION, and 1,562 crop rows say so rather than
  posing as observed district production. A projection is never summed with a count. An empty cell
  is typed `not_printed` and stays empty: an absence is not a zero.
- **Two ambiguities left visible.** PBS prints two rows under the truncated plant name "Sapphire
  electric company U" with the same month and different generation, 24 times; neither summing them
  (inventing a total nobody printed) nor dropping them (losing real generation) is honest, so both
  ship and `source_row` tells them apart. Seven crop rows carry real figures against a district
  that could not be identified; they are withheld, with the reason in the register, rather than
  published against a blank place.
- **Prose corrected against the generated catalogue.** README.md and docs/uncertainty_contract.md
  said 20 structural axes and 19 named configurations; `pakemis_product_facts.csv` says 22 and 27,
  and the files on disk agree with the facts.

Licensing is unchanged and was checked before a byte was published: 195 of 196 register rows carry
`derived_file_in_deposit = yes`, the documents themselves still ship nowhere, and the HIES rule -
microdata never redistributed, design-weighted aggregates always - is asserted by a test that walks
every published row back to its register entry.

**One meaning of "industry" across the product, and an acceptance policy that can tell an absence
from a contradiction. NO NATIONAL NUMBER MOVES.** rc53 filed captive self-generation where IPCC 2006
reports it and then left two things wrong: the correction reached one page, and the decision record
that accompanied it scored missing evidence as though the candidate had been tested and failed.

- **The district layer answers the reporting axis.** rc53 refused it at district grain on the ground
  that the district tables were module-resolved, and that ground was wrong: the cube computes each
  stream's district vector for every period and folded it into a module key two lines later. The
  accumulator now keys on (module, reporting_sector), so a module's district mass is partitioned by
  where the Guidelines report it - exactly, from the same per-stream vectors, with the module total
  recoverable by summing over the pair. Industry and power read 28.13 and 57.82 at national,
  provincial AND district grain, which is the consistency the axis existed for and did not deliver.
  The 5.54 Mt that moves is captive generation's own measured district vector - a point allocation
  over 1,060 geocoded plants - never a proportional share of the power module's districts, and the
  release already quantifies that a surface-based substitute would differ by more than 5 points.
- **The per-stream district vector, for all nine periods.** pakemis_adm2_stream_by_year.csv, 223,774
  rows. The reference year's has shipped since rc47; the other eight were computed in the same loop
  and dropped. Same generator as the reference-year file, which a test holds row-for-row, and the
  same closure: a stream's district rows sum, with its OUTSIDE row, to its provincial mass at 1e-9.
- **The acceptance policy, rewritten before any new evidence meets it.** Every test RESULT now
  carries a kind: `constraint` (a bound, and THE OFFICIAL SERIES IS SCORED ON IT TOO), `validation`
  (two estimates, neither the truth), `untested` (the input is not held, and it NEVER favours either
  side). The same evidence re-scores as 11 constraints, 19 validations and 33 untested - and the
  three violated constraints belong to the OFFICIAL series, conditionally, not to the candidates.
  rc53's verdicts ship beside them under policy_version.
- **A pinned verdict, retracted.** tests/test_industrial_coal_decision.py asserted
  `decision.startswith("OFFICIAL STAYS BOOKED")` on every row - the only place in the tree where a
  scientific conclusion was pinned rather than a number, so a build in which the evidence had
  changed its mind would have failed the suite. The test now asserts the record's SHAPE: that an
  absence is never phrased as a failure, and that the objection blocking adoption is the defensible
  one (a single cross-section does not establish a TREND) and not the indefensible one (no
  reconstruction without an annual survey - IPCC 2006 Vol 1 Ch 5 permits a single-year surrogate).
- **A shipped number of ours was wrong, and is repaired.** ICIMOD prints a NATIONAL brick-coal
  figure of 6.5 Mt/yr on page 27. rc53 ignored it and scaled the paper's Punjab total up on this
  release's kiln frame to 3.94 Mt - 39 percent below the source's own national number. The
  independent level is now the source's figure and the scale-out is a cross-check that disagrees
  with it by a factor of 1.65; the official column reads 0.17x to 1.34x that level. Two further
  discrepancies are recorded rather than smoothed: the paper prints 3.1 Mt on the same page where
  its own arithmetic gives 3.41, and its national pair implies Punjab is 52 percent of national
  brick coal where the kiln frame says 87.

## [1.0.0rc53] — September 2026

**The industrial boundary, the diagnosis release: WHY the series falls, and what is not established.
NO NATIONAL NUMBER MOVES.** rc52 expanded what the inventory calculates. rc53 asks the prior
question - is the fall in reported industrial fuel physical, a reporting change, incomplete
coverage, or a combination - and answers it per channel, per stream and per year, without
correcting a single value until something earns it. Nothing does.

- **The source-vintage ledger.** HDIP's coal-by-sector allocation is published more than once per
  reference year and the prints differ, so every published print is now a row
  (data/activity/industry/coal_by_sector_vintages.csv, 303 prints across nine editions) with
  reference year, publication year and REPORTING-PERIOD LENGTH as separate columns - a nine-month
  July-March figure can never be differenced against a full year.
  pakemis_coal_vintage_ledger.csv pairs consecutive prints and classifies what moved. TWO
  REALLOCATIONS are in the record: July-March FY2023-24 moves 1,500 kt from brick kilns to
  cement/others between two Economic Survey editions with power and the total unchanged, and
  full-year FY2024-25 moves 133 kt back. Neither is a change in consumption, neither touches a
  booked endpoint, and brick + cement/others is INVARIANT across both - so reversing one would
  redistribute between subsectors and repair no industrial total. Also found: the Supplement folds
  the Pak Steel column into "Cement" (FY2013-14 and FY2014-15, to the tonne; the column is zero
  from FY2015-16, so no reported year carries it, but "Cement" has never meant cement alone).
- **The booking policy is now declared data.** data/coal_booking_policy.csv names the estimate the
  engine books for each year and consumer, with its reason, replacing a rule inside
  sectors/industry/solid_fuels.py plus one hard-coded override. It refuses July-March prints and
  reproduces rc52's booked values to the gram. It also makes a method transition visible: the brick
  series is NOT single-vintage - FY2015-16 books the older print because the Supplement's revision
  breaks the supply balance - a transition IPCC 2006 Vol 1 Ch 5 (acquired this release) requires be
  documented and tested rather than hidden. It is worth 0.50 Mt on the measured decline.
- **Where the decline comes from.** pakemis_industrial_change_attribution.csv splits the FY2015-16
  to FY2023-24 change in every priced 1.A.2 stream into the channel that produced it, with only the
  booked rows summing to the published change and counterfactuals never added to it. THE HEADLINE
  IS UNCOMFORTABLE AND STANDS: the industry MODULE falls 11.69 Mt while IPCC 1.A.2 - including the
  captive self-generation the power module computes - falls 13.63. Correcting the boundary makes
  the decline LARGER, not smaller, because captive generation fell too.
- **The reporting-sector axis.** A stream is now filed where IPCC 2006 reports it, beside the
  module that computes it: data/stream_reporting_sector.csv declares `reporting_sector` per stream
  and the column rides source_streams -> atoms -> months -> ADM1 -> fact_annual/fact_monthly/
  dim_stream. One row differs - captive gas self-generation reports under industry - and the axis
  is ADDITIVE with sector_id in every period, so the power bar loses exactly what the industry bar
  gains and no mass moves. The economic-sector view is re-expressed on top of it, so "industrial"
  is the industry and ippu reporting sectors by construction rather than by a second code rule.
  The district tables are module-resolved upstream and so do NOT carry the column: the axis is
  REFUSED at ADM2 rather than answered with the module, because answering would return the industry
  module alone and silently drop the captive generation the axis exists to include.
- **The coal account closes; the division does not.** The national coal balance now writes the
  identity out with its residual RETAINED as a column (exports and stock change typed, never
  zeroed), carries the power lane as a BAND from NEPRA's metered burn to HDIP's allocation so
  industry is not made to absorb the seam, and adds an origin-resolved energy account. Per year:
  FY2019-20 and FY2020-21 read MISDIVIDED between users - the tonnage closes while the brick column
  exceeds all domestic coal mined outside the Thar plants' burn - and the other metered years
  CLOSE. Two honesty guards ride with it: the tonnage closure is labelled a TRANSCRIPTION CHECK
  because the two published tables balance by construction, and the energy residual is reported as
  a WIDTH (44-71 percent of supply energy) because two of its three calorific values are IPCC
  defaults and the test cannot fail.
- **Brick kilns, from a counted fleet instead of a residual.** Six documents acquired.
  pakemis_brick_activity_reconstruction.csv estimates this stream for the first time without
  reading HDIP's own column: an association kiln census (10,394 operating in Punjab, November 2020)
  times a 440-kiln baseline survey (328.2 t per kiln-year) gives 3.41 Mt for Punjab, 3.94 Mt
  scaled nationally. THE OFFICIAL COLUMN RUNS FROM 0.29x THAT LEVEL IN FY2023-24 TO 2.21x IN
  FY2020-21 - a factor of 7.7 - while the counted fleet does not move. The 70-100 g of coal per
  brick carried here until rc52 APPEARS IN NO HELD DOCUMENT and is retired, replaced by measured
  Pakistani values: 184 g per brick for fixed-chimney kilns and 155 for zig-zag, 60 kilns in
  Faisalabad, 2023. Two independent sources agree on that intensity and disagree on SCALE by a
  factor of three, so the level is a band with no central, and the implied-intensity reading now
  names its own denominator bias.
- **Cement, tested against the producers' own books.** Sixteen held annual reports yield a
  company clinker series and a TYPED NEGATIVE: none of them discloses kiln thermal energy under
  about 35 patterns, so the reconstruction's heat term stays transferred rather than measured.
  Two tests became possible anyway. Fourteen companies print both FY2022-23 and FY2023-24, and
  their matched clinker agrees with this release's census-derived back-cast to 1.46 percent - the
  first independent test that basis has had. And HDIP's FY2023-24 cement column, at a 100 percent
  coal share, implies 2.70 GJ per tonne of clinker, BELOW the 2.85 GJ/t design floor of the most
  efficient line any held source names: in the reference year that column cannot cover cement's
  own kiln fuel, so it holds no other industry and is short.
- **The decision record adopts nothing.** pakemis_industrial_coal_decision.csv scores every
  candidate against four tests in every year. None beats the official series on all of them, so
  every official value stays booked and the pins do not move: L 469.63822 / S 464.50543, unchanged
  from rc52. The brick candidate beats the official column as a LEVEL and is refused as a SERIES,
  because one surveyed cross-section is not a nine-year path and imposing a flat one would
  manufacture the central the decision rule forbids. The cement candidate is refused because its
  own heat term is assumed. What changed is what the series MEANS, not what it holds.
- **The build-order debt named in rc52 is closed.** The validation catalogue's freshness gate
  compares each cited product's mtime to the build sentinel, but the catalogue phase ran BEFORE
  a dozen of the products it grades, so those still carried the previous build's mtime and any
  build more than two hours after their last hand-run failed STALE on them. The catalogue now runs
  after every phase it grades and still before the three phases that read its outputs (the product
  catalogue, the artifact inventory and the deposit manifest), in all three build definitions.
- **Also.** A completeness row corrected: captive-generation diesel AND furnace oil bought in bulk
  are inside the estimated 1.A.2 industrial liquids (the transport fuel ledger excludes that
  customer class from the road control by construction), and only retail-pump diesel remains inside
  1.A.3.b - the previous row claimed the whole of it sat in Road and omitted furnace oil. The
  FY2023-24 and FY2024-25 Economic Survey energy chapters and IPCC 2006 Vol 1 Ch 5 acquired.

## [1.0.0rc52] — September 2026

**The industrial boundary, Wave B and C: the evidence products, and THREE CATEGORIES ENTER THE
REFERENCE.** The second deliberate re-base of the boundary program. Ammonia (2.B.1), iron and steel
(2.C.1) and lubricant use (2.D.1) enter the reference as full FY2015-16..FY2023-24 series, each
through its gate (data/scope_registry.csv): the national totals move in every year (the ledger is
in the commit message and scripts/check_pins.py), by +3.72 Mt in FY2023-24 (469.64 from 465.92).

- **Ammonia, Tier 1 calibrated.** NFDC production by product and fiscal year (a new ingest,
  data/nfdc/nfdc_production_by_product_series.csv, every year closing on its printed total and
  identical across editions) x the NH3 embodied per product x the Pakistan-calibrated 1.815 t
  CO2/t NH3, net of the CO2 recovered into urea (44/60). 2.73 Mt in FY2015-16, 3.24 in FY2023-24;
  the method envelope (1.694..2.104) stays beside it in pakemis_ammonia_nitric_series.csv and the
  four-pathway reconciliation stays diagnostic. The `ammonia_feedstock_in_scope` configuration is
  retired - the mass is in the reference. Plant-level output and recovered CO2 for every plant
  is the Tier 2 step, named.
- **Iron and steel, Tier 1 EAF.** QIM billets and ingots (the year's own twelve months) x IPCC
  Table 4.1's 0.08 t CO2/t; pig iron is zero from FY2016-17, so the electric route is the only one
  operating. 0.25 Mt in FY2015-16, 0.39 in FY2023-24; the scrap/DRI split is named in the
  uncertainty.
- **Lubricant use, Tier 1 ODU.** OCAC's sectoral sales of non-energy products (a new ingest,
  data/activity/industry/ocac_non_energy_sectoral.csv, 2,846 cells FY2015-16..FY2024-25) - LUBES
  and GREASES grand totals x NCV 40.2 x 20.0 t C/TJ x ODU 0.2/0.05 x 44/12. 0.05..0.10 Mt.
- **What stays outside, and why.** Nitric acid: a PAIR per year (unabated/abated) on a
  nitrate-derived activity - abatement operation after 2022 is undocumented, so no central. Soda
  ash: NA in IPPU for a Solvay country (IPCC Vol 3 s3.8.3.1 allocates the emissions to the coke) -
  the earlier natural-process ceiling was the wrong method. HFCs: the first STOCK-based band, from
  HIES 2018-19 and 2024-25 ownership (data/activity/ippu/hies_appliance_ownership.csv) x IPCC
  Table 7.9 ranges - the household bank's operating losses reach a few tenths of a Mt against
  Annex F consumption of 7-10 Mt CO2e a year, so the supply cannot be absorbed by household
  equipment (commercial and industrial banks are unsurveyed). Industrial wastewater: a band over
  IPCC's own W, COD and MCF ranges (sugar, paper), coded Waste.
- **The brick question, narrowed by HDIP's own footnote.** The PBS Compendium on Environment
  Statistics reprints HDIP's coal-by-sector table with its footnote: the brick-kiln column is
  "Estimated by deducting other uses of indigenous coal from the total production" - a RESIDUAL of
  domestic production by construction. The new by-province ingest (PBS minerals, every table
  closing to the tonne; Sindh 1.49 -> 14.67 Mt on the Thar ramp) gives the coal balance a third
  test: in FY2019-20 and FY2020-21 the official brick residual EXCEEDS all coal mined outside the
  Thar plants' burn by 3.5 and 3.1 Mt - not domestic coal under HDIP's own definition. Read at
  CCAC's one held brick output (82.5 billion, 2018), the official tonnage implies 14 g of coal
  per brick in FY2023-24 against 70-100 g by kiln type. pakemis_brick_coal_alternatives.csv
  carries the alternatives with no central; the official series stays booked.
- **Also.** UNSD per-period rows beside EDGAR's in the boundary ledger; the OGRA class extension
  is a typed negative (no captive-textile class, feed/fuel only in the tariff section); IPCC 2006
  Vol 3 Ch 3/4/5/7 and Vol 5 Ch 6 acquired; the monthly minerals ingest's COAL rows are found to
  mis-attribute other minerals' rows in several editions (registered; no shipped number reads them). BUILD-ORDER DEBT, named: the validation catalogue's freshness gate (2-hour slack against the national totals sentinel) runs BEFORE the boundary-program phases that it grades, so a build more than two hours after their last run fails on them until they are regenerated by hand - the gate should follow those phases or grade them by their own phase; not fixed this release.

## [1.0.0rc51] — September 2026

**The industrial boundary, Wave A: what the Industry bar is, said plainly; the same atoms
regrouped by what they are; two repairs.** No reference number moves and the pins are
untouched. The Analyze waterfall's Industry bar is the industry MODULE - IPCC 1.A.2 direct
industrial fuels (the official HDIP coal allocation, OGRA's industrial gas, OCAC's industry
liquids) - and it was labelled as if it were Pakistan's industrial sector. Captive generation
(1.A.2, computed by the power module) and cement process CO2 (2.A.1) were never inside it.

- **The contract's limitation text.** `industry_reported_fuel_series` now leads with the
  reading the bar deserves: "Covered industrial-combustion emissions fell, reflecting lower
  recorded fuel use. This does not mean Pakistan's total industrial emissions declined;
  several industrial sources are reported elsewhere or remain outside the inventory." - then
  the reported-fuel caveat as before. The Explorer labels the module "Industrial fuel use -
  covered sources" (short form "Industrial fuel use" mid-sentence and on an axis).
- **The economic-sector view.** `group_by: ["economic_sector"]` is a derived group key of the
  query core (`pakemis_query.engine.ECONOMIC_SECTOR_SQL`): the same fact_annual atoms grouped
  by what the IPCC code says the activity IS - 'industrial' = 1.A.2 exactly or its children
  (so the captive generation the power module computes is inside, and railways' unresolved
  '1.A.2/1.A.4.c' is not) plus every 2.x process category; every other sector keeps its
  module. Additive with the IPCC view every period, and its industrial aggregate reproduces
  the boundary ledger's priced total to the ledger's own rounding (59.54 Mt in FY2015-16,
  49.95 in FY2023-24: -9.60). A new limitation, `economic_sector_view`, says what that
  aggregate does NOT contain - ammonia and nitric acid process emissions, HFCs and SF6, iron
  and steel, lime, glass, lubricants and industrial wastewater are screened or absent, and each
  enters only as a full FY2015-16..FY2023-24 series, never in the reference year alone
  (adding them to FY2023-24 alone would manufacture about +12 Mt of "growth"). The view is
  labelled "covered direct industrial sources" until that back-cast is complete. No fact
  column was added: the rule lives in one place and is held to the ledger by test.
- **A repair to the rc50 bridge.** `pakemis_industrial_coal_bridge.csv` read the "official"
  2.A.1 emissions from the atom table, which after the re-base already carried the re-based
  value, and then added the delta a second time (FY2015-16 printed official 17.779 and
  reconstructed 21.743 Mt; correct 13.815 and 17.779). Both ends are now computed from the
  clinker quantities and the reconstructed end is held equal to the reference atom by test;
  the builder is invariant to build order. National numbers were never affected.
- **The nine-year EDGAR diagnostic.** EDGAR's Pakistani Industrial Combustion and Processes
  rows (every gas, 2015-2024) are extracted from the held 2025 booklet to
  `data/activity/industry/edgar_pak_industry_series.csv`, and
  `pakemis_industry_edgar_divergence.csv` sets the engine's 1.A.2 (industry + captive) and
  its covered industrial aggregate against EDGAR at the fiscal blend for all nine years. At
  the blend the two 1.A.2 series differ by -4.6..+6.6 Mt with alternating sign from FY2015-16
  through FY2021-22, then the engine falls 17.9 and 17.5 Mt below EDGAR in FY2022-23 and
  FY2023-24 - the two years HDIP's power allocation sits above NEPRA's metered burn. The
  boundary ledger carries one diagnostic row per period from it. EDGAR is IEA-balance-derived
  and HDIP-fed upstream and its 2023-2024 columns are preliminary: a diagnostic of where the
  compilations part, never an independent verification, never a residual. The reference-year
  EDGAR benchmark note, which still described the engine as "gas and liquid fuels only" four
  releases after coal entered, is rewritten to the rc50 boundary.

## [1.0.0rc50] — September 2026

**The industrial-coal reconstruction, and the clinker re-base.** The Analyze waterfall's
Industry (1.A.2) bar read -11.69 Mt over FY2015-16 -> FY2023-24 on HDIP's coal-by-consumer
allocation - an '** Estimated' series the engine reproduces exactly. Matching the official
table closes the transcription question and not the inventory-quality one, so this release
holds that diagnosis OPEN with held evidence and moves only what the evidence supports. ONE
deliberate re-base, and it is not the coal: the national pins are UNTOUCHED (FY2023-24's
cement is the audited census already); the eight historical 2.A.1 values move.

- **The clinker basis is promoted (decision-rule row 2).** The 16-company producer census
  implies a clinker-in-cement fraction of 0.965 (derived from the census balance, never
  typed; GEM's 30-of-32 plants at 0-5 percent substitution corroborate; IPCC's all-portland
  0.95 brackets it). Applied to the eight earlier years in place of the IPCC blended-cement
  default 0.75 it removes the +9,027 kt FY2022-23 -> FY2023-24 method break the splice had
  manufactured (to +109 kt) and raises 2.A.1 by +3.96..+5.57 Mt a year, +37.1 Mt in total.
  One clinker series now serves process CO2 and the cement kiln-fuel activity. The fraction
  is one held quantity, typed `persists` and scoped - but NOT yet bound as a shared draw: a
  scope rule binds by stream, not by year, and the census year does not multiply the
  fraction, so binding it would over-declare FY2023-24's width. Its 2.5 percent therefore
  still sits in the per-year residual this release; a year-conditional scope binding is
  named debt, not closed.
- **Brick, cement and other industrial coal stay on the official series - bounded (row 3).**
  Production evidence exists; fuel evidence does not. Cement kiln coal is reconstructed as a
  band (K x H x s / NCV; H, s and NCV transferred - zero of sixteen held company reports
  prints coal tonnage or kiln heat); the HDIP "Cement" column - printed "Cement/Others" by
  the Economic Survey and "Cement/Other Industry" by the PEY - sits ABOVE that band by
  1.4-6.4 Mt of other-industry coal in FY2016-19 and FY2021-22 and inside it in FY2023-24.
  Brick has no held production or intensity. The power seam (NEPRA's metered burn against
  HDIP's estimate) flips sign across the window and would lower the FY21 peak and raise the
  FY24 trough, but "production minus Thar burned" cannot separate non-Thar brick coal from
  Thar stockpile without by-field production, and FY2023-24 supply is publisher-flagged
  partial. Every band is published beside the official value; no central is manufactured;
  the label "Industry: reported-fuel estimate" and its caveat stay.
- **The evidence products.** `coal_supply.csv` (two production lanes, the partial-period
  footnotes per row), `unsd_coal_supply_control.csv` (the one independent supply control),
  `pakemis_coal_source_reconciliation.csv`, `pakemis_coal_balance.csv` (H1/H2 tested per
  year: the supply-origin allocation matches in four of ten years and breaks in five),
  `pakemis_cement_kiln_coal_reconstruction.csv`, and `pakemis_industrial_coal_bridge.csv`
  (official -> activity -> fuel-quality -> boundary -> reconstructed, with the identity
  dE_new = dE_official + dE_end - dE_start as a band).
- **Acquired.** Economic Survey 2025-26 ch.14 Energy and ch.3 Manufacturing (Table 3.11 -
  the document the fugitives ingests cited but did not hold). The Statistical Supplement
  2025-26 is unpublished; the FY2024-25 brick figure cannot yet be verified.

Named and not closed: by-field coal production (the one acquisition that separates
non-Thar brick coal from Thar stockpile); fired-brick production and coal-per-brick by kiln
technology (PBS Compendium on Environment Statistics 2020); plant kiln heat and coal share
(the extended IPPU-CEM-01 request); the FY2023-24 monthly import series for the coverage
audit; the Supplement 2025-26.

## [1.0.0rc49] — September 2026

**The nine-year air spatial family.** The covered-sources air panel leaves the national
grain: nine fiscal years x seven species on the frozen 0.05-degree lattice, through the
greenhouse-gas cube's own dispatch - every pollutant mass rides the cell vector its
anchor stream was placed on for that period, so the grid, the ADM2 table and the ADM1
table are three marginals of ONE allocation and the identity
panel = grid = ADM1 = ADM2 + outside + unallocated_below_adm1 is asserted for all 126
(pollutant, period, configuration) cells, not a sample. National greenhouse-gas pins
are UNTOUCHED.

- **The supports were corrected before anything was gridded.** The railway air layer
  splits per traction stream (54 furnace-oil atoms had anchored a stream marked
  not_present for six of the nine periods; they now ride the non-traction yards stream
  that exists all nine - every pollutant total conserved to the bit, the FY2016
  traction furnace-oil rows ABSENT, not zero). Agriculture's 14 rows became 76 on the
  surfaces each mass actually leaves from: fertiliser NH3 per product, livestock NH3
  per (species, stage) - housing/storage on the volatilisation stream, application on
  organic manure, grazing on the two pasture streams - soil NOx as three N pools
  riding their own surfaces (the single row had put manure-N and residue-N on the
  fertiliser surface), residue burning per crop. A regrouping, byte-stable at every
  national total. A guard now refuses any (period, anchor) whose stream has no mass in
  the period's own atomic table: the registry join may never inherit dead geometry.
- **Uncertainty is invariant under the regrouping, and now provably.** The per-row
  independent Monte-Carlo draw would have silently HALVED the NH3 interval
  (+/-23.6% to +/-12%) by sqrt-N cancellation across sub-rows that share one factor
  family. The MC and its Approach-1 cross-check now draw per POOL (the key-category
  grouping, with the three soil-NOx pools folded onto their one shared emission
  fraction): five of seven pollutants reproduce the pre-split file bit-for-bit.
- **A second configuration for the nine years.** `S_HIES1925` joins the closed
  vocabulary: the survey-anchored dung series (HIES 2018-19 and 2024-25 per-household
  anchors, interpolated, flat before 2019, each year's basis labelled in
  `residential_configurations_by_year.csv`); the air panel, the fact table, `query_air`
  and the spatial family carry it at every grain, as separate files and slices, never
  summed; the greenhouse-gas engine refuses the new id everywhere.
- **The products.** Two physical-only NetCDFs on the shared frame
  (`pakemis_air_grid_0p05_annual_fy2015_16_fy2023_24.nc` and `..._survey_...`;
  `annual_grid.write_frame` is now one function for both families so the frames cannot
  drift - the greenhouse-gas cube reproduced byte-identically through the refactor),
  anchor-grain `pakemis_air_adm1_by_year.csv`, canonical-frame
  `pakemis_air_adm2_by_year.csv`, typed `pakemis_air_unallocated_by_year.csv` (the
  aviation cruise class, never zeros). The by-year tables carry the (period, stream)
  join key and NO evidence badge of their own - the badge is the weight registry's to
  derive from what the build DID - and the join ships:
  `pakemis_air_spatial_support_by_year.csv` (basis, proxy year, operator, pattern
  hash, grade as separate columns) and `pakemis_air_uncertainty_split_by_year.csv`
  (the activity/factor and spatial halves side by side, never combined).
- **Release mechanics live in the tree now.** `scripts/release_finish.sh` (receipts
  deposit-last -> fixpoint -> record -> package -> split, the ordering's WHY in
  comments) and `scripts/build_release_split.py` (fail-closed on the package's own
  exit codes; a per-release RELEASE_NOTES entry is REQUIRED - a version without notes
  refuses to split).

Named and not closed: semantic/query and explorer wiring of the by-year air family;
and beside this lane the standing acquisitions - the dung inter-round reconciliation,
the power/industry plant-unit-year control-equipment record, road-fuel sulfur
supply-weighting from the OGRA import shares, the HIES waste-route burn split - each
a gap-register row or coverage-matrix absence, none a silent omission.

## [1.0.0rc48] — September 2026

**The air-pollutant panel release.** The seven air species (BC, CO, NH3, NMVOC, NOx as
NO2, PM2.5, SO2) leave their single reference year: a nine-fiscal-year covered-sources
panel (FY2015-16..FY2023-24), built the way the greenhouse-gas national series is built
- each sector's own air engine per year under its own fiscal convention, never a
national total distributed downward. National greenhouse-gas pins are UNTOUCHED.

- **The atomic ledger** (`pakemis_air_atomic_annual.csv`): 2,790 atoms at period x
  sector x category x process x species in Gg, each carrying its activity basis, its
  factor source and its own source-stream anchor, fail-closed through the air join.
  The rollup (`pakemis_air_annual_fy2015_16_fy2023_24.csv`) declares
  `coverage_scope=covered_sources_only` on every row: this is NOT a complete national
  seven-species inventory and does not claim to be.
- **Coverage as a product** (`pakemis_air_coverage_matrix.csv`): all 630 period x
  module x species cells typed under the closed IPCC notation keys - 360 estimated,
  270 typed absences each carrying its reason and gap row. A missing estimate is its
  key, never a zero. Power runs the same nine years as the UNCONTROLLED screening
  scenario it declares itself to be, shipped BESIDE the panel
  (`power_air_screening_fy2015_16_fy2023_24.csv`), never inside it.
- **Road transport re-based on cited factors.** The exploratory Punjab-workbook
  diagnostic (uncited g/km, one anchor per fuel, no BC, exhaust only) is replaced by
  the EMEP/EEA guidebook 2023 Tier 1 chapters - held under sources/EMEP, 204
  transcribed cells verified against the chapters' own text - with fuel reconciled to
  the OCAC Road control by construction and four processes as separate atoms (exhaust,
  evaporative NMVOC, tyre-and-brake and road-surface wear). BC exists for the first
  time; SO2 is sulfur stoichiometry under a declared per-year regime with the cited
  Euro-II (Jan 2017) and Euro-V (Jan 2021) import-mandate boundaries; every row anchors
  its own vehicle class's stream. FY2023-24 totals move as a declared re-base (NOx
  172.1 kt was 112.7; CO 1430.4 was 3588.2; PM2.5 8.2 was 21.6), the old-vs-new
  comparison printed in the paper with the superseded column frozen in the registries,
  and the residential-to-road particulate ratio re-based to 109 (L) / 50 (S) on the
  exhaust definition with Tier 1's own uncontrolled-to-modern spans as its honest width.
- **The engines honour the year they are asked about.** Power's air layer takes the
  same three-regime lignite share the CO2 side burns (no Thar lignite before the fleet
  existed), passes bagasse its year and captive the fiscal-END year the OGRA panel is
  keyed on; railways SO2 burns each year's own declared diesel sulfur (0.5 percent
  before the January 2017 Euro-II import mandate - FY2015-16 is 1.23 kt against the
  0.12 a flat modern spec would claim); residential's series slice generalises from
  PM2.5 alone to every species, absent - never zero - where the reference emits none.
- **The panel is servable.** `fact_air_panel` enters the semantic layer on real fiscal
  period ids (plain foreign keys - the CY2024 column escapes are single-year-layer
  only), and `query_air` answers fiscal-period questions with the covered-sources
  limitation verbatim on every envelope and three typed refusals (periods below
  national grain; years and periods together, which are two time bases; a period
  grouping without periods). Two goldens freeze the first answers, the SO2 series'
  Euro-II step among them.
- **A dead column came back to life.** `pakemis_stream_support_ledger.csv` shipped
  `emissions_Gg=0.000000` on every one of its 1,753 present rows - the builder read a
  column name the atomic table does not have, and the closure test checked only the
  co2e column beside it. The builder now reads `emission_native_mass` and a closure
  test refuses a dead mass column outright.
- **Beside this release's own lane**, the external verification bundle became the
  whole package (its own commits): per-sector archives plus a `_common.zip` carrying
  every outputs file, a four-stage derivation chain per sector, and a withheld-files
  register so nothing this project may not republish ships by accident.

Named and not closed: the air spatial-by-year and NetCDF family, monthly pollutants,
air engines for industry, IPPU and non-flare fugitives, the flare submodule, controlled
power (`air-power-controlled`), the livestock fiscal enumeration, and the residential
LPG/kerosene/coal archive transcription - each a typed absence in the coverage matrix
or a gap-register row, none a silent omission.

## [1.0.0rc47] — September 2026

**The stabilization release.** The twenty-first review audited rc46 and returned ten
findings; three verification passes confirmed every one against the tree, several worse
than stated. This release fixes all ten under FROZEN national pins - not one reference
total moves - which makes its headline unusual: the scorecard gets WORSE where the old
numbers were flattering, and that is the point. Measurement, not regression.

- **The configuration double count is dead.** Three scope configurations kept adding
  their full screening estimates to a reference that already booked the measured coal:
  brick (+7.35) and captive (+1.31) are retired, cement re-priced as the model's net
  excess (+2.60), and a ratchet test now forbids any configuration from pricing mass the
  reference contains. The completeness ledger's negative unclaimed remainder - the
  arithmetic signature, shipped in plain sight - is gone.
- **The crop geography is real.** The pooled-district split that claimed a reference-year
  provenance had NEVER executed (a name-vs-id key mismatch made every split silently
  uniform); it is now uniform by declaration and allocation-inert. Twenty dropped
  mainland districts (~5.5% of crop area) re-enter through canonical naming; the
  reference year reads the PBS panel instead of the MapSPAM proxy, with the disagreement
  shipped measured; field burning declines both panels and rides its own year's FIRMS
  raster.
- **Historical power is graded by measurement.** The four panel years' located share is
  computed (labelled-and-located over everything, blank rows in the denominator) instead
  of a None read as 1.0: FY2015-16..FY2017-18 regrade S1 to S2 wholesale, FY2018-19
  keeps its S1 because 0.97-0.98 earns it, and 13-18 Mt a year of genuinely unplaceable
  fuel is priced as events instead of renormalised onto located stations.
- **Mass rides its own evidence.** Fugitive segments pool only their own Field Type's
  flare sites (3.6 Mt was on the wrong field type); the waste coverage reports its
  measured located share (0.287 SWDS / 0.050 wastewater) instead of a silent 1.0;
  wastewater's served share sits at the 25 HydroWASTE plants, fractionally; and domestic
  aviation splits LTO from cruise the rail-recode way - the 16.5% that burns at
  airports stays S1 there, the cruise remainder is booked at uplift provinces and NOT
  placed below them, because corridor weights without an OD matrix would be invented
  physics. 195 of 198 streams are gridded; the three cruise streams are the entire
  unallocated set (0.05%).
- **Industry has geography at last.** All 22.58 Mt leaves S4: brick coal on the 11,272
  surveyed kiln points, cement coal on the geocoded clinker register, gas and liquids on
  built-up within their provincial shares - registers the repository held all along.
- **Transport reads its own years.** FY2021-22 and FY2022-23 get their measured OCAC
  provincial shapes (twelve direct monthly editions each, held and unread until now);
  the road-density raster is promoted from priced bracket to the petrol/diesel basis
  with built-up as the priced comparator; CNG stays urban on built-up.
- **The frames are settled.** The OCHA COD-AB 2022 vintage is landed and crosswalked
  (`pakemis_adm2_frame_2022.csv`: twelve of fourteen collision groups plus Larkana and
  Tor Ghar resolve) with the one re-rasterisation declared as v1.1's migration; the
  0.05-degree lattice's exact odd-parity 2x2 relationship to EDGAR ships as
  `pakemis_grid_0p1_edgar_aligned.nc` with its conservation identity asserted.
- **`pakemis_stream_support_ledger.csv`** is the audit's deliverable: one row per
  (period, stream) - mass, support, measured located share, priced remainders and the
  per-row monthly refusal - rectangular over the full panel with typed absence.

Named and not closed: the v1.1 ADM2 re-rasterisation (prepared, tested, deliberately not
performed in a release candidate); 2.F activation and the HIES disposal routes (the
standing review items); the livestock second census anchor; Keamari and Surab polygons.

## [1.0.0rc46] — September 2026

**The revision release: activity controls from open data.** The twentieth review asked for
the inventory's remaining borrowed geography and modelled activity to be replaced with the
public series that carry them, and this release is that program: six gated waves, ONE
deliberate re-base, and every delta named. The national pins move for the first time since
rc39: **L 452.34662 -> 465.91851, S 447.21383 -> 460.78572 (+13.57189 Mt both)**, the entire
delta the industrial solid-fuel activation and its per-stream ledger sums exactly.

- **Industrial solid fuels enter the reference total** through the written
  `industrial_solid_fuels_1a2` activation gate: brick-kiln coal (+2.77584 Mt) and cement kiln
  coal (+10.79604 Mt) on the Finance Division Statistical Supplement 2024-25 Table 14.1(4)
  coal-by-consumer series (25 years, 118 cells checker-verified). Supply and consumption
  close to ~0.5 kt in eight of nine years, so the brick residual column absorbs all
  non-power/cement/household coal and the old 7.0 Mt typed refusal closes by identity. The
  one year that does not close (FY2015-16, by exactly the 204 kt brick vintage delta) adopts
  the balance-consistent PEY value, typed. The rc13 kiln screening (7.35 Mt) retires as the
  claimant; the measured reference year is a trough (1,129 kt brick coal vs 8,678 in
  FY2020-21).
- **Power on point support.** 17 more stations located (GEM GOGPT + bioenergy trackers, all
  TRACE-corroborated <=5 km); a 547-spelling plant-name crosswalk; the four pre-FY2019-20
  grid-coal years draw per-station pools from the generation panel instead of 100%
  substitution; gas located share 0.50 -> 0.9658 and the letter follows the measurement
  (S2 -> S1). Two source defects typed rather than adjudicated: GOGPT's "Halmore" pinned on
  Habibullah's Quetta site, and JDW-III's three-way identity conflict.
- **Eight years of crop geography stop borrowing the reference year's map.** The PBS
  crop-by-district API yields district panels for all nine years and five crops; the
  agriculture allocation reads each period's own panel, controlled to the unchanged fiscal
  series so no national number moves. Agricultural `reference_shape_backcast` stream-years
  fall 256 -> 120 (livestock and fertilizer legitimately remain), verified by pattern hash.
  Sujawal's rice cell is corrupt at source in seven of nine years - excluded by pinned
  value, with an assertion that fires when PBS repairs it.
- **The F-gas bank goes species-resolved and stays outside the total.** Fourteen species
  from the UNDP RAC inventory (108 transcription checks) drive a bank-and-retirement model
  priced at blend-component GWPs: 5.854 Mt CO2e for the reference year, inside the old
  one-stratum bracket [2.3, 6.2]. 2.F's activation is an explicit rc47 review; the lanes
  (CRT / bank / Art.7 / EDGAR) remain contractually unblended.
- **The geography the registers always held.** The 130 World Bank flare sites (per-site
  annual volumes 2012-2025) become the allocation basis for the five field-sited fugitive
  segments, year-keyed; the two LNG FSRUs are located and the "0 of 2 located" refusal
  retired; the mapped disposal sites (56 OSM landfill polygons + 2 ClimateTRACE points)
  concentrate covered districts' waste within-district under the kiln coverage-mask
  pattern. Pure-uniform fugitive rows fall 171 -> 36. Every promoted letter was forced by
  the derived-class guard, not declared. Three defects that no closure test could see were
  caught by a provincial-marginal diff and killed before the gate: a flare cache key
  missing the stream's profile (gas segments briefly rode oil's provincial split), a waste
  surface built beside the district panel instead of from it, and an `or True` admitting 25
  wastewater plants into the disposal-site register.

Named and not closed: 2.F activation and the HIES disposal-route promotion (the same rc47
review); the livestock second census anchor; fertilizer province-month backfill; the
SPAM -> GCD rice allocator; transmission and distribution line geometry; the road raster.

## [1.0.0rc45] — September 2026

**The nine-period annual grid.** rc44 shipped nine fiscal years of district products and,
deliberately, no historical raster: nine cubes were declined because for two thirds of
stream-years they would carry the reference year's within-province pattern multiplied into 3.4
million cells a year. That objection was right and this release answers it rather than
overriding it - the pattern's provenance now ships beside the pattern, and is measured rather
than asserted.

- **`pakemis_grid_0p05_annual_ref_fy2015_16_fy2023_24.nc`**: nine fiscal periods x three
  spatial views x three gases on the frozen `pk_0p05_epsg4326_v1` lattice, 9.0 MB. Every period
  is generated from its own atomic streams, not by rescaling the reference map, and a test
  compares NORMALISED layers so a rescaled cube could not pass it. Cells plus
  `pakemis_spatial_unallocated_by_year.csv` reproduce each period's national control to a worst
  relative 2.2e-7. The three views PARTITION the placed mass and must not be added to one
  another's totals.
- **The pattern, hashed.** `pattern_hash` digests the normalised weight vector where the
  allocator uses it, so "borrowed" stops being a claim about the build. All 918 stream-years
  labelled a backcast do carry the reference year's pattern; of the 351 labelled as resting on
  their own year's evidence, none does. The grading and the thing it grades now have
  independent sources and they agree.
- **The registry was reading the reference year for all nine periods.**
  `pakemis_grid_stream_surfaces.csv` is the reference year's file and the join used
  `source_stream_id` alone, so the surface and placement reported against FY2015-16 were
  FY2023-24's. Now joined on (period, stream) via the new
  `pakemis_grid_stream_surfaces_by_year.csv`; 29 rows change, all of them streams carrying no
  mass in that period.
- **The grid query stops answering wrongly.** `get_grid_cell` was declared in the contract with
  no caller and no test. It resolved months by subtracting a hardcoded `date(2023, 7, 1)`;
  `argmin` snapped any point on earth to a Pakistani edge cell; and a masked cell - outside the
  country - was returned as a number. The epoch is now read from the file, the domain is
  checked, and the mask is a refusal.
- **`cell_area` and `pakistan_fraction` ship as variables**, because a 0.05 degree cell is 28.3
  square kilometres in Sindh and 24.7 in the north and that gradient otherwise reads as a real
  north-south signal. `crs_wkt` and `spatial_ref` are declared, which is what GDAL actually
  reads.
- **Nine release gates**, including the annual FY2023-24 layer against the twelve monthly cells
  cell by cell, and a period-isolation gate for a leak that every closure test would survive.

Named and not closed: no historical monthly grain and no historical configuration S, neither
being evidenced; the by-module and by-category cube groups; a CF checker is neither installed
nor pinned, so the CF check covers the conventions the file relies on rather than certifying
conformance.

## [1.0.0rc44] — August 2026

**The nine-year spatial reconstruction.** The inventory had a nine-year national ledger
attached to a one-year spatial renderer; this release places the other eight years and says,
per stream-year, on what evidence.

- **Territorial membership.** An "Other" share is now placed only where its own source put it:
  every row of `data/province_shares.csv` carries a machine-read `other_membership`, and
  transport's 0.80 Mt of CO2e leaves Islamabad District, whose OCAC area pages never reported
  it. No national pin and no ADM1 marginal moves.
- **The period is a parameter.** `report/grid_cube.py` named FY2023-24 in nine spellings; one
  `PeriodKeys` object now carries them all, read from `data/periods.csv` and
  `data/months.csv`. Two silent borrowings were found by measuring rather than reading: the
  grid plant fleet and the FIRMS fire raster were both keyed to the reference year for every
  period, and neither raised anything.
- **Nine years published**: `pakemis_adm1_by_year.csv`, `pakemis_adm2_by_year.csv`,
  `pakemis_adm2_monthly_by_year.csv` (all 108 months at district grain),
  `pakemis_adm2_sector_by_year.csv` and `pakemis_grid_fallbacks_by_year.csv`. Each period
  closes: national == ADM1, and ADM1 == ADM2 + the mass unallocated below it, to 1e-12 for the
  eight panel-controlled years.
- **Provenance per stream-year.** `pakemis_spatial_weights_by_year.csv` types all 1,701
  stream-periods on two axes - was the geography measured for THIS year, and how much of the
  placement was substituted. 299 of 1,672 live stream-years were measured in their own year;
  1,102 carry the reference year's pattern rescaled.
- **The substitution record, per year.** Grid power's plant ledger begins FY2019-20, so the
  four years before it place 42.6-53.3 Mt CO2e a year on a built-up substitute - two orders of
  magnitude more than the reference year's 0.34 Mt, and previously invisible.
- **The query surface serves it**: `fact_adm2_year` beside `fact_adm2_month`, with the engine
  routing historical district requests to the annual table and refusing monthly ones for a
  reason that is true.
- **A receipt no longer depends on the tree it was built in.** `result_sha256` digested the
  release manifest's git hash, so every commit invalidated every frozen golden receipt,
  whatever the data did. It had already gone unnoticed through rc42.

Named and not closed: the district frame is fixed at the 2019 boundary set for all nine
periods (`abs-adm2-frame-vintage`), the historical periods are annual at ADM2 module grain,
and a plant-name crosswalk between the generation panel and the coordinate tables would turn
power's four backcast years into per-object activity.

## [1.0.0rc43] — August 2026

**The nine-year spatial reconstruction.** The inventory had a nine-year national ledger
attached to a one-year spatial renderer; this release places the other eight years and says,
per stream-year, on what evidence.

- **Territorial membership.** An "Other" share is now placed only where its own source put it:
  every row of `data/province_shares.csv` carries a machine-read `other_membership`, and
  transport's 0.80 Mt of CO2e leaves Islamabad District, whose OCAC area pages never reported
  it. No national pin and no ADM1 marginal moves.
- **The period is a parameter.** `report/grid_cube.py` named FY2023-24 in nine spellings; one
  `PeriodKeys` object now carries them all, read from `data/periods.csv` and
  `data/months.csv`. Two silent borrowings were found by measuring rather than reading: the
  grid plant fleet and the FIRMS fire raster were both keyed to the reference year for every
  period, and neither raised anything.
- **Nine years published**: `pakemis_adm1_by_year.csv`, `pakemis_adm2_by_year.csv`,
  `pakemis_adm2_monthly_by_year.csv` (all 108 months at district grain),
  `pakemis_adm2_sector_by_year.csv` and `pakemis_grid_fallbacks_by_year.csv`. Each period
  closes: national == ADM1, and ADM1 == ADM2 + the mass unallocated below it, to 1e-12 for the
  eight panel-controlled years.
- **Provenance per stream-year.** `pakemis_spatial_weights_by_year.csv` types all 1,701
  stream-periods on two axes - was the geography measured for THIS year, and how much of the
  placement was substituted. 299 of 1,672 live stream-years were measured in their own year;
  1,102 carry the reference year's pattern rescaled.
- **The substitution record, per year.** Grid power's plant ledger begins FY2019-20, so the
  four years before it place 42.6-53.3 Mt CO2e a year on a built-up substitute - two orders of
  magnitude more than the reference year's 0.34 Mt, and previously invisible.
- **The query surface serves it**: `fact_adm2_year` beside `fact_adm2_month`, with the engine
  routing historical district requests to the annual table and refusing monthly ones for a
  reason that is true.
- **A receipt no longer depends on the tree it was built in.** `result_sha256` digested the
  release manifest's git hash, so every commit invalidated every frozen golden receipt,
  whatever the data did. It had already gone unnoticed through rc42.

Named and not closed: the district frame is fixed at the 2019 boundary set for all nine
periods (`abs-adm2-frame-vintage`), the historical periods are annual at ADM2 module grain,
and a plant-name crosswalk between the generation panel and the coordinate tables would turn
power's four backcast years into per-object activity.

## [1.0.0rc42] — August 2026

The twentieth review audited the rc41 validation package and returned
Conditional B+: the numerical core is sound (all 104 manifest products match
their hashes, the annual aggregates reconcile to the atoms, the ensembles
reproduce, every manuscript renders), and the release fails on four fronts —
clean-room reproduction on Linux, a spatial placement that conserved mass but
misrepresented where it was, validation commands that were not green, and
stale manuscript claims. Its fourteen gates are closed in four gated commits.
No central number moved: the reference totals are rc39's to the last printed
digit (L 452.34662 / S 447.21383 Mt CO2eq). What moved is placement,
attribution and prose, each a named re-base with its movement measured.

- *Wave 1 — a reproduction the package can run.* Sequential accumulation
  (`core.io.seq_sum`) reproduces the published series under CPython 3.11,
  3.12 and 3.13 (the reviewer's closure failure was `sum()`'s compensated
  summation on an exact 5-dp tie, not a Linux effect); openap and jsonschema
  are pinned in the lock and every phase's third-party imports are checked
  against it before phase one; the packager writes stub records first, runs
  `reproduce.sh` before the suites, compares all 104 manifest products, and
  ships a SHA256SUMS that plain `sha256sum -c` accepts and a manifest its
  own JSON Schema accepts; the source manifest's `sha256` is the named
  file's digest with the document's beside it. The validation gate is split:
  a self-contained tier that must be green in the package, and a documents
  tier that runs only against a mounted vault (`validate.sh --documents DIR`,
  `reproduce.sh --sources DIR`); no document leaves the machine. CI's claim
  is what CI does.
- *Wave 2 — the placement says what the map does.* All eight FY2023–24
  coal stations are located from GEM (exact) corroborated by Climate TRACE:
  coal fallback mass 34.715 → 0.319 Mt, the coal streams S1 with the class
  graded per stream on located activity; the decomposition's unresolved mass
  is the cube's own fallback ledger. The 2024 livestock census reaches the
  grid through the canonical crosswalk (137 census districts consumed; 15
  shapes left the GLW proxy; 25.5 Mt moved between districts inside their
  provinces; Karachi's seven census districts land on their one polygon).
  One FIRMS attribution ladder serves the temporal profile and the spatial
  raster (52,428 attributed detections; 17 % of the burning raster's weight
  had ridden rejected detections). The NetCDF cubes are CF-1.8 with
  `_FillValue` −9999 on out-of-country cells only. The captive "duplicates"
  were built, measured and REVERSED: the register reconciles to OGRA's
  independent 288 MMCFD only with every row (275.14 without), so the 25
  repeated rows are connection records, named on the row and kept.
- *Wave 3 — the crosswalk at the atom, the covariance counted.* The flatness
  crosswalk joins each month-row's own temporal grade to its physics (TE4
  62.36 %, equal to the coverage summary; grain difference 0; no cell the
  definitions forbid). The longitudinal variance shares add a dependency
  group's members before squaring: FY2023–24 reads 76.95 / 20.85 / 2.20
  (persists / resamples / residual) where rc41 printed 86.63 / 10.67 / 2.70.
  The district ranking the census join moved is regenerated with its labels
  (Karachi 10.18 Mt leads), and the held air-district product is rebuilt.
- *Wave 4 — the manuscripts say what the tree holds.* 74 of 75 registered
  tables are joined by row label; the agriculture sensitivity table is
  computed, not read from an rc40 file; the FAOSTAT prose compares on the
  calendar-2023 basis its table uses; the IPPU paper counts sixteen producers
  with Fecto's exact clinker; LULUCF is stated as an exploratory module
  outside every total; both agriculture→energy transfers are stated; 3.G and
  the cropland/grassland soil-carbon rows carry NE, not 0; the urea bridge
  uses 44/60 and Annex-5's exact 6,578.838 kt; the fertiliser feedstock row
  is unresolved while 2.B.1 is NE.

**Reviewer errata, stated so the next audit does not inherit them.** The
captive rows are connection records, not duplicates (the OGRA reconciliation
is the evidence; the 0.114 Mt "reallocation" does not happen); 17.67 % of
livestock activity "bypassed" is not reproducible (14.76 % was placed by
proxy, 19.63 % counting the unread census districts); the "stale" monthly
request text was chained rounding on an exact tie (4.765) in a document that
regenerates identically; the longitudinal closure failure is CPython ≥ 3.12
`sum()` on a 5-dp tie, not a Linux/libm effect; the schema finding is right
in substance (ten values) but contradicts itself as worded; the agriculture
paper never called dung "the only" transfer — the omission of the residue
transfer was real and is repaired.

## [1.0.0rc41] — August 2026

The nineteenth review audited the rc40 validation package and returned
Conditional B: the reference annual inventory, its 108-month product, the
reference-year Monte Carlo, the cross-sector mass balance and the reference
spatial conservation all pass; what failed was the release around them. Its
eighteen gates are closed in six gated commits. No central number moved: the
reference totals are rc39's to the last printed digit (L 452.34662 /
S 447.21383 Mt CO2eq). What moved is uncertainty, by design and measured, and
the one thing the reviewer allowed to be graded rather than fixed is graded.

- *Wave 1 — reproduction that cannot lie (R1–R4, K1).* `run_all --strict`
  ends the run on any non-zero phase; a phase ledger records what each phase
  wrote; `reproduce.sh` copies the tree WITHOUT outputs and seeds only the
  registered held products; `compare_outputs.py` reads the ledger and reports
  `rebuilt_identical` only for a file an OK phase wrote in THIS run (rc40
  reported 82 of 83 identical after rebuilding about eleven). Eight document
  dependencies became consumed derivatives with registered digests, one public
  document (the UNFCCC CRT) ships; the definitive empty-outputs rebuild ran all
  114 phases strict, 79 identical, 4 seeded.
- *Wave 2 — configuration S at stream × gas × month (S1–S4).* The S spatial
  product had rescaled every residential row by one per-province CO2e ratio
  (CO2 −3206.85 Gg against a configuration that changes no CO2). The cube now
  runs S through the same placement as REF: only the two dung streams differ,
  the weights are the same objects, and S closes per gas at national, ADM1,
  ADM2 (+outside) and grid. Exception masses are stream-specific with the gas
  and methane-origin GWPs (0.48 Mt, not 8.36; the reviewer's 0.97 is not
  reproducible either); the per-stream allocation surface is what the cube
  used; every GLW remainder is a priced fallback; `emissions_Gg` is numeric or
  null with a typed `absence_reason`.
- *Wave 3 — schemas that reject (D1, D2).* Ten malformed CSV payloads repaired
  where they were written; `read_rows` raises on a ragged row; a typed column
  registry (98 products, 1,154 columns, 40 enumerations, 20 foreign keys) is
  enforced in the repository and inside the package.
- *Wave 4 — provenance that resolves (P1, P2).* Every one of 1,672 estimated
  atoms names its method and uncertainty model (was 1,366 unresolved); every
  source stream names its activity, conversion, factor and identity
  parameters (178 unresolved fields → 0) through scoped, role-typed parameter
  groups; seventeen rows whose declared width predated the groups now derive
  from the parameter graph, so intervals move (residential MC ±37.0 → ±50.9 %;
  the unnamed share of national variance ≈⅛ → 2.2 %). `SOURCE_MANIFEST.csv`
  joins its registers on the keys they are keyed by — rc40's 0/5,431 filled
  publisher/URL/edition/locator, and mtimes for dates, is gone.
- *Wave 5 — manuscripts from labelled tuples (M1–M8).* Table cells are
  compared BY LABEL, and the swapped manure/cement rows are a stored defect
  that fails by name. The agriculture headline is 223.5 everywhere (223.3 was
  the evaluation harness, 223.4 a second rounding; the totals files carry three
  decimals). The cement reference is the sixteen-company census, 21.816 Mt;
  the 0.75-fraction model is the diagnostic it displaced, and the
  configuration that priced it is renamed to say so. The residue-fuel
  justification reads the ledger. The cover prints both digests under their
  own names. Four closures, eight ledgers, counted from the map.
- *Wave 6 — graded, and seeded without floats (T1, T2).* The historical
  monthly product is graded BELOW A− explicitly: 20.98 % of nine-year monthly
  mass is time-variable but unobserved against a 15 % gate (the reference year
  alone 9.04 %), one acquisition (MON-OCAC-01, unsent) would land 13.40 %.
  Every longitudinal stream seed carries identity and pin year, never a
  float string; the first 200 draws of every stream ship as a prefix a rerun
  must reproduce (exact on the producing platform, 1e-12 elsewhere).

**Reviewer errata, stated so the next audit does not inherit them.** The
exception mass 0.966572 is not reproducible (stream-specific: 0.482 Mt); the
25.5192 Mt "undocumented GLW fallback" is the routed remainder 0.359 Mt plus
species proxies that collapse to one raster (25.86 Mt), all now priced; "21
read sites" for the status sentinels were about twelve, and there was a second
sentinel the review did not see; `repr(float)` is platform-stable — the hazard
was the libm-sensitive value it printed; "~1 Mt" was unmeasured (the phase
never ran in the rc40 reproduction) and the measured re-seeding effect is
≤ 1.24 Mt on a level end and ≤ 1.83 Mt on a difference end; `retrieval_date`
was not blank but populated with file mtimes, which is worse.

## [1.0.0rc40] — August 2026

The release-integrity round answering the second external audit of the
agriculture sector (engine A−, release B+ conditional on five gates) and the
reviewer's specification for **one national validation package**. No
deterministic emission moved; the reference totals are rc39's to the last
printed digit (L 452.34662 / S 447.21383 Mt CO2eq). What moved is the
uncertainty model, by design and measured.

**The five gates.**

- *G1 — the manuscript reads its products.* The appendix's CRT activity column
  had been hand-written and never opened by a claim: 245.3 M ruminants, 3.50 Mha
  rice, 3.78 Mt N and 5.89 Mt urea were rc38's numbers. Every cell now reads the
  product that computes it (245.524371 M head, 3.637 Mha, the
  F_SN/F_ON/F_PRP/F_CR vector, 6.578838 Mt urea), Table 7 prints the computed
  FracGASF 0.1608, the two remaining "114 districts" sentences read the
  registered count, the poultry source is labelled by its true edition, and the
  reproduction paragraph names a command the package can run. Thirteen claims
  were registered; `repair_claims` and `repair_tables` are at a fixed point.
- *G2 — ADM2 nests exactly.* rc39 published a 1.836 Mt gap between the
  agriculture ADM2 view summed per province and the provincial controls. The
  five deltas summed to zero: mass was crossing provinces on paper. The
  allocation restricts each stream to a shape's HARD label mask inside its
  province, while rc32's exact-area partition read the surface back out
  splitting boundary cells among every polygon that touches them — including
  a neighbour in the other province. Cells are now partitioned only among
  claimant shapes in the cell's own province, renormalised; the sum over a
  province's shapes is the provincial marginal by construction (per-province
  residual ≤ 4e-6 Mt, total 7e-6). The check compares against the unrounded
  allocation, not the 4-s.f. provincial files. 37 of 126 shapes moved, gross
  2.31 Mt, net +5e-9; Larkana's unplaced mass and the seven rice fallbacks are
  re-pinned; the national paper's captive-power ADM2 bracket moved 21.59 →
  21.39 Mt because both ADM2 products now share the partition.
- *G3 — every agriculture stream names its factor.* The source-stream ledger
  sorted dependency groups by NAME (`factor:` → factor, `factor:ncv:` →
  conversion, else activity), so agriculture's `ef:` groups were filed as
  activity and every factor column read `unresolved`. `ef:` groups are factors
  and identities; a group that is itself an ef id names its own table row;
  conversion reads `none` where there is no calorific step. The licence field
  is deliberately NOT asserted: `not-established` is the tested position for
  a government PDF with no stated terms.
- *G3b — the herd and crop draws reach the N2O streams they drive.* G3 exposed
  thirteen streams with no activity group: manure N2O and the organic-manure,
  pasture and residue soils rows. The Monte Carlo had never shared the herd
  draw with manure N2O nor the crop draws with residue N2O. Twenty-three scope
  rows attach them; the decomposition refused twelve rows whose declared width
  was the factor's alone and they now derive from their parameters
  (`stale_row_sigma`, 101–114 % → 106–124 %). Measured: agriculture
  −17.60/+22.67 % → −18.67/+24.29 %; national −10.30/+15.85 % → −10.67/+16.39 %;
  the sum of first-order indices 1.124 → 0.957 — the old model counted the
  herd twice. All 34 agriculture streams resolve every parameter column.
- *G4/G5 — the common draws ship, inside one national package.* The
  agriculture capsule is retired. `scripts/build_validation_package.py` builds
  the two files the validator receives — `pakemis_<version>_full_validation.zip`
  and its byte-identical manifest — from a clean release checkout: a
  repo-shaped runnable tree filtered by the deposit manifest, the validator's
  folders as hashed presentation copies or declared views, `validate.sh
  --quick|--full` and `reproduce.sh` run inside it before hashing, the common
  draws and `test_common_ensemble` in the quick tier, every failure named in
  `KNOWN_EXCEPTIONS.json`. Parquet twins of the atomic table and the monthly
  panel are now built (the catalog had promised the monthly one for releases
  without it existing). `data/product_schemas.csv` declares and verifies every
  product's primary key; `data/cross_sector_ledger_map.csv` projects the seven
  sector ledgers into one schema by pointers, and every ledger closes.

**Cleanup.** The false numeric header row in the district livestock
transcription is gone and guarded. The rc4 PDFs the reviewer holds as
`(6)`/`(5)` are browser duplicates from the 14 August send, not repository
files; only the same-release PDFs inside the package are current.

## [1.0.0rc39] — August 2026

The agriculture correction round, answering an external audit that graded the
sector B+ with A− arithmetic. Twelve ordered passes, and **the reference totals
move for the first time since rc30**: L 452.14350 → 452.34662, S 447.01683 →
447.21383 Mt CO2eq. That is a named re-base, not a drift — the 2024 census herd
had been carried at three significant figures, and de-rounding it was declared
and deliberately deferred in rc38.

The audit supplied expected values for every agriculture category. Four
independent corrections — the herd, the fertiliser window, the urea mass and the
3.G/3.H split — **reproduce all six of them and the sector total to six decimal
places**, and none of those values was used as an input anywhere:

    3.A Enteric fermentation     151.657650      3.D Managed soils    28.525954
    3.B Manure management         21.228487      3.F Field burning     0.669549
    3.C Rice cultivation          16.548350      3.H Urea application  4.824481
                                     TOTAL     223.454471

`tests/test_agriculture_control.py` now pins those figures against the atomic
product, with a companion test that greps `data/` for each of them and fails if
any appears in an input — a control the engine can reach is not a control.

**What the round changed in the accounts.** The herd is the census's exact
enumeration (245,524,371 ruminants); the fertiliser composition is weighted over
the fiscal year it describes rather than an April–March annexe year, giving
FracGASF 0.1608191992; urea CO2 is applied to NFDC's printed national offtake of
6,578,838 t instead of a reconstruction that fell 0.207 per cent short; and 3.G
Liming stopped being published as a numeric zero under a Not-Estimated heading.

**What it changed in what the release can show.** Every estimated agriculture
atom names the IPCC equation that produced it, where all 1,672 rows repo-wide
had carried `method_id=unresolved`. Every agriculture stream names the raster it
is actually spread on, where all 34 had claimed `population`. The crop-residue
ledger accounts for all 86.14 Mt the crops produce and names the 48.10 Mt (55.8
per cent) whose destination this inventory does not price. The share of the
sector's timing that is genuinely unresolved is 6.67 per cent of the nine-year
panel, not the 87.3 per cent a TE-class count alone suggests. Larkana's missing
polygon costs 8.01 Mt of sub-provincial placement, and the seven rice shapes
where MapSPAM shows no paddy cost 0.27 Mt — both quantified for the first time.

**Three of the audit's own premises did not survive checking, and are recorded
rather than adopted.** Its replacement energy figure (122,082.15 TJ) cannot be
reproduced from its own air-dry mass at the held calorific value, which gives
the 122,192 TJ it asked to delete. The joint uncertainty it called stale is not
stale — `estimate_Mt` holds the Monte Carlo mean, and the defect is the column
name, so the deterministic figure is now published beside it. And the `pytest`
reproduction claim it called false is true: the full suite runs under it, 2,383
passed and 4 failed, those four being the release-integrity set that fails under
`unittest` too until the fixpoint.

**The deposit capsule reruns.** 1,326 files, 167 tests, all passing in a virtual
environment with nothing installed into it — the agriculture engine and its
tests need no third-party package, which `requirements.txt` has asserted for
releases and nothing had proved. `capsule/VERIFIED.txt` records one run on one
machine (macOS 15.6, CPython 3.11.10) and says plainly that Linux, Windows and
other CPython minors were not tested.

**Build-integrity defects found along the way**, each fixed at the root: the
1990–2024 series was declared an output of a module that only reads it and no
output of the module that writes it, so three consumers had been reading the
previous run's series; the district × year panel and the temporal driver
registry were in no build definition; and a claim regex hard-coded a denominator
that changed, silently unbinding the claim so it could no longer fail.

## [1.0.0rc38] — August 2026

The agriculture pass: the first sector taken through the rc37 instruments,
and the sector that carries 49.4 per cent of the inventory. Nothing moved in
the accounts — the pins hold at L 452.14350 / S 447.01683 Mt CO2eq. What
changed is what the release can show: 823 activity cells are now checked
against the documents they were typed from, seven identities the manuscript
calls enforced are published where a reader can see them, three comparisons
claim less than they did because each reads something the product is built
from, and four manuscript credits pointed at code that is not there.

- **823 hand-typed cells re-read from the documents they were typed from:
  817 agree, six are declared, none disagree.** 685 livestock district cells
  (137 districts × 5 species — the herd behind enteric fermentation and
  manure management), 25 province cells, 6 crop cells, 3 fertiliser cells,
  the 5 national-herd cells, and all 99 rows of `es_fiscal_series.csv` — the
  nine-year reconstruction the whole historical series rests on. Each fiscal
  row is checked against ITS OWN declared `source_table`, which matters: the
  Economic Survey's Table 2.9 prints 3,086 kt of nitrogen for FY2023-24, a
  provisional part-year figure, where the file holds the NFDC review's 3,775
  and says so in the row. `data/transcription_checks.csv` is the register and
  `scripts/check_transcriptions.py` re-runs every row on every build; it
  gained a page cache (one `pdftotext` per cell was 719 subprocesses for one
  sector), a `document_scale` column for tables published in thousands, a
  dash convention for the census's "none reported", and composite
  `column=value;column=value` row keys — because two files in a row could not
  be identified by their first column, and an ambiguous key must fail rather
  than silently take the first match. The scale and the dash are declared per
  row, never inferred: a factor of a thousand inferred from a thousand-fold
  disagreement is how a real error gets absorbed.
- **The national herd is a rounded transcription, and that is now written
  down rather than discovered.** `livestock_2024.csv` carries the census at
  three significant figures — cattle 55,800,000 against 55,862,560, camels
  −0.75% — while `livestock_district_2024.csv` is exact and sums to the
  census to within eight head. *(Erratum, rc39: this bullet originally read
  "within one head". That was true of cattle and buffalo and false of sheep
  and camels, which differ by eight head each in opposite directions. The
  wording is corrected here rather than removed, and rc39's re-base publishes
  the residual per species instead of characterising it in prose.)* Enteric fermentation and manure management, 77% of
  the sector, are computed on the rounded figures, so de-rounding would move
  the reference pins by roughly 0.15 Mt. Declared and left alone by decision:
  a named re-base for a later round, not a transcription fix. The same
  register row's `archived_path` was a seeded guess pointing at
  `sources/Agriculture`, which holds the Economic Survey and the NFDC review
  and not the census; it points at `data/pbs_census` now.
- **Two more producers re-run.** `scripts/ingest_nfdc_annex7.py` and
  `scripts/ingest_nfdc_afr2025_fertilizer.py` gained `--check` and are
  enrolled in `tests/test_data_rederivation.py`: five committed files
  re-derive from held documents, among them the Annex-7 offtake table that
  `agriculture/monthly.nitrogen_profile()` reads — the file behind the
  calibration this release reclassified.
- **Seven checks the manuscript calls "enforced on every run" are gates
  now.** `agriculture_qa_2024.csv` publishes the reconciliation identity on
  both metrics — the AR6 one was covered by no test at all — and the new
  `agriculture_n_ledger_qa_2024.csv` publishes the nitrogen ledger's four
  closure residuals (0, 6.1e-17, 0, 1.2e-16 relative to 7.7766 Mt N
  excreted) instead of only aborting the process. The ledger has its own
  Runner and its table is enrolled in the QA guard registry.
- **Three comparisons now claim less than they did, and one states its
  limit for the first time.** `tim-fertiliser-offtake` is a calibration,
  not a validation: `nitrogen_profile()` reads the same NFDC Annex-7 urea
  offtake and uses it AS the monthly weights, so the twelve differences
  measure the spread between two structural alternatives rather than error
  against an observation — which moves agriculture's timing cell from
  validated to corroborated, resting on the FAO crop-calendar row. The
  satellite fire detections are registered as a calibration for the same
  reason (they are the burning profile's weights), and the row publishes
  the attribution ladder instead: of 169,657 FY2023-24 detections, 61.2 per
  cent fall outside Pakistan, 2.4 per cent near kilns, 5.5 per cent off
  cropland, 30.9 per cent attributed. Cui 2021 is registered as
  corroboration rather than the scored anchor this release had planned:
  zero of its 1,507 field observations are in Pakistan and the country
  value is model-extrapolated. `mag-agriculture-benchmarks` keeps its class
  and gains the limit it never had — FAOSTAT, EDGAR and the CRT read the
  same activity statistics, so what can fail there is method, and it has.
- **The manuscripts may no longer credit code that is not there.** Four
  credits were wrong at once: two named `src/pkinv/inventory/...` paths
  that predate the sectors layout, and two named modules rc36 removed —
  including `eval/buffalo_implied_ef.py`, the generator the buffalo
  supplement names for a published table, which is restored and joins
  `make eval`. rc36 audited code, docs and figure includes but not the
  papers' own generator credits; `tests/test_manuscript_module_credits.py`
  closes the class, honouring globs (the waste appendix credits three
  scripts by pattern) and failing on a glob that matches nothing.
- The agriculture paper carries an independence matrix in the aviation
  `tab:independence` form: eight comparisons, each stating what it shares
  with the engine and whether it is a calibration.

## [1.0.0rc37] — August 2026

The validation program's instruments. rc36's presence audit answered "is
all the raw and processed data here?" with a full-hash yes and then
measured what "here" did not mean: the raw → `data/activity` layer had no
audit, eight producers shipped a `--check` no test ran, and the validation
scorecard had no sector axis. This release builds the instruments every
sector pass (rc38 onward, one per sector by share) is held to. No inventory
number moved: the pins hold at L 452.14350 / S 447.01683 Mt CO2eq.

- **`pkinv.report.data_provenance`** (`scripts/audit_data.py`, a build
  phase): every git-tracked data product classed as produced by a named
  script, hand-made with its document held, hand-made and derived,
  hand-made with no held source (and the gap that says so), a root
  parameter table, or a provenance sidecar; `unregistered` is asserted
  empty and the three products read by nothing are frozen by name. First
  run: 256 products — 106 / 62 / 17 / 9 / 46 / 16 — and 14 unregistered,
  now zero: the census transcriptions, the district benchmark records, the
  GLEAM and Global Mangrove Watch transcriptions and the run-time-named
  proxy rasters were in no register. The filename-generalising search
  moved to `pkinv.core.filenames` so the outputs audit and this one share
  it; the audit excludes its own contract test from the reader scan
  (naming an orphan is not reading it — the first run reported zero).
- **The census contradiction, resolved on the evidence**: the source
  register said the 7th Agricultural Census tables were read from portal
  views with "no single file to keep" while `data/pbs_census/` has held
  the Table 4/6 workbooks and PDFs since 2026-08-04 beside the
  hierarchical transcription the activity files roll up. The register's
  universe gained the four transcription directories, the two livestock
  files are archived, the not-retained row is gone and the gap row is
  closed with its artefacts named. `data/raw_manifest.csv` covers those
  directories and `data/nfdc` now (5,374 files, 15.10 GB).
- **`tests/test_data_rederivation.py`**: the eight `--check` producers as
  generated tests; four had never been run by anything and all four
  reproduce their committed files (captive register, landfill assets,
  building fraction, the 317 MB road-network rebuild behind
  `PKINV_SLOW=1`). Skips print their reason and are asserted to be the
  declared set.
- **`data/transcription_checks.csv` + `scripts/check_transcriptions.py`**:
  the register of hand-typed cells re-read from their documents (pdftotext,
  OCR, or a person), the checker that re-runs the automatable rows under
  the half-ulp rule, and a test that plants a wrong cell and watches it
  fail. Empty at this release; the sector passes populate it.
- **The sector scorecard** (`pakemis_validation_sector_scorecard.csv`): the
  (module × property) projection of the catalog — 30 cells, each carrying
  its best row and what that row may claim. 20 validated (9 by a
  large-independence record), the rest corroborated, calibrated only, or
  declared absent; no cell is silent any more.
- **Catalog hygiene that needed no data**: aviation's reconciliation study
  is a gated build phase (its five rows were `makefile_target`/`exempt`,
  the configuration that left IPPU's QA table stale for four releases; its
  outputs were byte-identical when run); the fugitives timing absence now
  names the non-production streams it actually covers instead of
  contradicting the PBS calibration row; ERA5 is reclassified
  corroboration on its own limit; the CCAC bridge — the one independent
  number that prefers a residential configuration — is a catalog row; the
  industry non-kiln geography silence is an absence row, and the power
  coal/gas and industry gas timing silences are stated on the hindcast rows
  that score the liquid streams (a declared absence may not stand over a
  scored result, so the statement lives on the result).
- Deferred to the sector passes by design: the runner gates each paper
  claims as "enforced on every run" (they live in `tests/`), the
  `inputs_register()` for the five sectors without one, and the held-data
  fills (FIRMS, HydroWASTE, GHSL, Cui 2021, the GEM trackers).

## [1.0.0rc36] — August 2026

The repository carries only what is load-bearing. Three audits — code,
outputs, and data/docs/root — produced candidate lists with negative
evidence, and every removal went back through the registers (artifact
roles, the deposit manifest, the validation catalog's out-of-scope list,
the claims twins). No inventory number moved: the pins hold at
L 452.14350 / S 447.01683 Mt CO2eq. Every batch was accepted only when the
full suite passed and a full `--quick` build changed nothing beyond the
manifest's tree-dirty flag.

- **Removed, each with zero references** (batch 1): a 135 MB duplicate of
  `data/raw/` (`PakEmis_108_month_data_bundle/`, 94 files, every payload
  byte-identical to its twin); `data/climatetrace/` (103 files no code
  read — every consumer reads `sources/`); seven page rasters at the root;
  a dropped-in code archive and its nine unpacked scripts; three manuscript
  PDFs committed under names that slipped the ignore rule (now closed);
  thirteen figures no manuscript includes.
- **The companion lane's leftovers** (batch 2): 46 orphan files under
  `outputs/eval/` that nothing writes, the desk-label CSVs under
  `data/validation/`, and the dead modules `eval/buffalo_implied_ef`,
  `eval/run_desk_validation` (imported three modules that no longer
  exist), `eval/vision_label`, `eval/district_crosscheck` with their
  unread products; `scripts/ingest_railways.py` and `railway_data/`; the
  always-skipping `test_spatial_nh3_validation.py` and
  `test_baseline_spatial.py`; the `test_paper_numbers.py` shim. Kept on
  evidence: the five `outputs/districts/` products and their frozen driver
  — the agriculture paper includes `district_totals.png`.
- **Duplicates and a frozen vintage** (batch 3): four outputs written
  twice by their runner (byte-identical aliases) and two Aug-15 aviation
  `_2023` files that live code and three claims read in preference to the
  `fy2023_24` twins the runner writes since rc15 — readers repointed,
  files gone, no number moved.
- **The producers of live inputs join the build** (batch 4): nine
  producers — the agriculture Monte Carlo, key categories and nitrogen
  ledger, the LULUCF exploratory module, the three air-pollutant research
  layers, and configuration S at the monthly and ADM2 grains — were in no
  build definition while the inventory read what they write. They are
  phases now, with declared reads and writes. Running them exposed a stale
  shipped product: the nitrogen ledger dated from 5 August, before the
  census re-base, and the agriculture paper's `tab:nledger`, `tab:stages`
  and F_ON claim were quoting it (twenty-five cells; total N excreted
  7.88 → 7.78 Mt; F_ON 2.40 → 2.33 Mt; the IPCC/EMEP chain ratio 1.23 →
  1.24). `scripts/repair_tables.py` — the companion of `repair_claims.py`
  for the TABLES registry, walking each registered tabular exactly as the
  test does — made the repair; its first version matched the first run of
  digits in a cell and mangled thousands-separated numbers across fourteen
  files before the suite refused the commit, and now locates the parsed
  value itself and dry-runs unless `--apply` is passed. `make eval` names
  the seven runnable evaluation products the manuscripts cite. Drift
  fixed: the generated completeness table no longer cites a module that
  does not exist; the rebuild log is version-free in name.
- **Docs** (batch 5): the uncertainty contract linked from the README, the
  eight acquisition request letters linked from their index, and the
  claims machinery with `scripts/repair_claims.py` documented in `qa_qc.md`.
- **The registers see everything** (batch 6): the artifact inventory is
  recursive over every file under `outputs/` with roles for the classes it
  could not see (figures, prose reports, the dashboard, the Tier-3 research
  products, the evaluation lane, the draw files); `data/raw_manifest.csv`
  covers `data/raw/` — the 4,764-document NEPRA corpus, kept by decision,
  is hashed for the first time — and `data/gis/` (229 MB of rasters and
  boundaries that had been in neither hash manifest); `scripts/
  audit_outputs.py` no longer exempts whole directories. A full-hash
  presence audit (`verify_raw_data.py`: 370 files, 12.88 GB, every file
  present and unaltered; 130/130 activity files registered; 0 of 130
  declared outputs missing; no LFS pointer anywhere) found three stale
  sentences rather than missing data: two headers still said
  `data/cache/aviation/adsblol/` was outside git (it has been in LFS since
  the raw-data round); two `tracked=external` manifest rows described
  files that are in git (regenerated); and the fugitives phase now
  declares the seven products its paper cites, whose freshness the build
  had not been guarding.
- Deferred, named: the two `data/raw` ⇔ `sources/` duplicate documents
  and the `sources/` duplicate pairs (collapse when the two raw registers
  are unified); the 19 generated-but-uncited figures (`figures.py` emits a
  fixed set per sector).

## [1.0.0rc35] — August 2026

The mechanical sweeps and the retirements (Wave C, the last wave of the
modularization program). No inventory number moved: the pins hold at
L 452.14350 / S 447.01683 Mt CO2eq. Before any sweep, a full `--quick`
build on the clean rc34 tree was recorded as the noise baseline: it changes
exactly one file (the release manifest's tree-dirty flag), so every sweep
batch below was accepted only when regenerating the modules it touched
changed nothing else.

- **`tests/paper_numbers/`**: the 13,179-line `test_paper_numbers.py` is a
  package - four data modules (`_common`, `doc_claims`, `tables`,
  `quantity_policy`) and six test modules that import only from them; a shim
  of the old name re-exports data and helpers, never a TestCase (which
  discover would run twice). Every symbol was placed by an AST ownership map;
  the 14 dead helpers went. The published test count is invariant under the
  move (2242 by the old and the new counting method); the deposit gained the
  twelve new files (1051 → 1063). `tests/_support.py` is the shared
  infrastructure unittest has no conftest for: paths from `pkinv.paths`, the
  io kernel re-exported, `scripts_on_path()` for the six bare scripts/
  imports.
- **Reader sweep**: 203 local CSV reader helpers (report 40, sectors/core/
  eval 51, scripts 28, tests 84) rewritten onto `core.io.read_rows` by an AST
  tool with an exact match - a function ending in `with open(P) as h: return
  EXPR` with the handle used once inside `csv.DictReader`. Semantics are
  preserved by construction: a helper without the `#` filter gets
  `comments=False`, so the raw/filtered split survives as an explicit flag at
  each site. In `tests/`, the same edits retired 77 local ROOT/OUT constants
  and 40 `sys.path` insertions (34 redundant under the editable install; the
  six load-bearing scripts/ ones became `scripts_on_path()`).
- **Writer sweep (`src/` only)**: 77 canonical `DictWriter` blocks onto
  `core.io.write_table` (report 42; sectors, eval and the multi-line banners
  35), including the banner writers - a banner written as one multi-line constant is split on newlines
  and each piece, already starting with `#`, is written verbatim. Every
  module a batch touched was re-run and its outputs compared byte-for-byte
  (one site, the FIRMS fetcher's cache writer, could not be re-run without a
  key and is verified by construction: plain shape, default terminator).
  Deferred, named: `scripts/` writers (84 sites; their outputs are committed
  data/ inputs, unverifiable by regeneration), the 62 list-row `csv.writer`
  sites (no list-row kernel yet), and `scripts/` ROOTs.
- **Found by the byte gate**: `pkinv.report.product_catalog` was in none of
  the three build definitions - the README generator imported it in-process,
  nothing wrote its file - so `pakemis_product_catalog.csv` and the
  supplement's generated product table had gone stale (reference-year flat
  share 53.3 → 52.8 per cent). Now a core phase in all three definitions -
  and `check_order()` earned its keep on that commit: the catalog's read of
  the monthly coverage summary was a side output no phase had declared.
- **The retirements**: `benchmark_kiln_allocation.csv` carries `task_id`,
  `role` and `status` like its siblings (the catalog reads its verdicts now;
  `declared_unscorable` joins the legacy map as a declared absence); the
  aviation controls builder keeps hand-resolved coordinates through
  `data/activity/aviation/airport_coordinate_overrides.csv` (held-row-wins,
  the IPPU geocoding pattern) - the rc34 regression cannot recur; the
  fugitives monthly layer builds before the run manifest, which now lists it;
  `data/validation_registry.csv` and its lane are retired - the catalog is
  the register, and the uncertainty section's register paragraph now quotes
  the catalog (68 entries; 24/19/25 by property; 19 large, 35 partial, 4
  none, 10 not applicable; 9 declared absences); the narrow
  `benchmark_comparison.csv` twin is retired - the agriculture runner no
  longer writes it, every consumer reads `national_benchmark_comparison.csv`
  (row-for-row, a column superset), the three catalog rows name their real
  producer, and the agriculture benchmark table follows the rich file's
  values (FAOSTAT field burning at 2 dp; Climate TRACE rows in AR6).
- A full `--quick` build on the swept tree (the C34 gate) changed only the
  manifest's tree-dirty flag. `tests/test_csv_terminators.py` freezes the
  set of LF-terminated outputs (140 files) so a writer that loses its terminator pin fails by name.

## [1.0.0rc34] — August 2026

The runner and build contract (Wave B of the modularization program). No
inventory number moved: the pins hold at L 452.14350 / S 447.01683 Mt CO2eq,
and every regenerated product outside the QA tables is byte-identical.

- **The runner contract** (`pkinv.core.runner`): every sector runner builds
  one `Runner`, routes its CSVs through `write()`/`write_dicts()`, registers
  out-of-band files with `record()`, states its checks with `gate()`, and
  ends with `finalize()`, which appends the automatic "declared outputs
  written" gate, WRITES the QA table on the one schema
  (`check, passed, actual, expected, note`), and only then raises. Twelve
  QA tables now ship (the ten registered runners plus the two aviation
  siblings) where three did on three incompatible schemas; seven sectors
  gained their first table. The write-then-raise ordering closes the
  fugitives class: its QA raise used to fire BEFORE the table was written, so
  a red build shipped the previous run's green table.
- **The guard consolidated** (`tests/test_sector_qa_checks.py`): one UNIFIED
  schema with a ratchet that keeps it so; the table floor 3→12; the
  `*_qa.csv` glob shape enrolled, which had let the aviation reconciliation
  table escape the guard for three releases; aviation's one true warning
  (Juzzak has no coordinate) is `passed=False`, tolerated by the runner and
  declared in the guard's ratchet in both directions. The fallback study's
  table is renamed `aviation_fallback_qa_fy2023_24.csv` and the study runs as
  a build phase - the guard file's opening story was a QA producer that never
  ran in the build. Two `generated_at` timestamps left the aviation manifests
  (the only nondeterminism a double-run found).
- **Typed build phases** (`pkinv.run_all.Phase`): the 91 phases are frozen
  dataclasses with `writes` (key output plus side outputs), a tri-state
  `reads` (None = not audited; a tuple is a declaration) and three flags
  replacing the label-keyed side tuples. `check_order()` refuses a read before
  its writer, an unmatched glob, or two producers of one file, naming the
  rule; `tests/test_build_order.py` proves it on three sabotage mutations and
  floors the audited set at 20 (22 declared, every edge verified against the
  consumer's source). The audit paid on contact: `product_facts` read
  `release_manifest.json` - written by a LATER phase - under keys it does not
  carry, so its `release_id` and `commit` rows had shipped "unresolved" for
  releases; and it read the grid cube's unallocated ledger from the previous
  build. The rows are repaired and the phase runs after the cube in all three
  build definitions. The railways air-pollutant layer, the one sector layer
  with no phase, has its freshness check.
- **The report layer reaches sectors by name**: sixteen declared accessors on
  seven engines (documented in `core/registry.py` as the extension
  mechanism), and `longitudinal_uncertainty`, `gas_closure`,
  `structural_trajectories` and `annual_product` import nothing from
  `pkinv.sectors`. The brick-kiln and bagasse screening arithmetic moved out
  of the trajectory report into the industry sector. Three private
  cross-boundary calls are public names; no report module imports sector
  code at import time (asserted). The 26 lesser sector imports in twelve
  report modules are the Wave-C sweep.
- **Found on the way, guarded, not yet fixed**: the aviation controls ingest
  (`scripts/build_aviation_anchor_controls.py`, run by `make aviation-fallback`)
  regenerates `data/activity/aviation/airports.csv` from OurAirports and
  discards the hand-resolved OpenStreetMap centroid for Islamkot (OPZZ),
  leaving the row UNRESOLVED; the grid cube reads that file, so a whole
  build's ADM2 views moved with no inventory number changing. The committed
  register is restored and `tests/test_aviation_airport_register.py` now
  refuses a register that loses a resolved coordinate; teaching the builder
  to keep manual resolutions is a Wave-C item.
- Declared byte diffs: the twelve QA tables (three migrated, nine new), the
  railways/transport run manifests' `generated_outputs` gaining their QA
  entry, the aviation manifests' timestamps, the reconciliation manifest's
  QA count and digest, and the two product_facts rows.

## [1.0.0rc33] — August 2026

The validation layer (Wave A of the modularization program). No inventory
number moved: the reference pins are unchanged at L 452.14350 / S 447.01683 Mt
CO2eq, and every change below is validation plumbing or the retirement of dead
code.

- **One verdict vocabulary** (`pkinv.validation.verdicts`): the closed set
  `pass / review / fail / no_record / by_construction / declared_absent /
  refused_typed`, with a LEGACY_MAP projecting the six incompatible verdict
  vocabularies the validation products had grown (YES/REVIEW, closes/passed/
  agrees booleans, PASS/FAIL, agree/disagree, MET-grades,
  exact_by_construction) onto it at read time. No legacy file is rewritten.
- **The unified validation catalog** (`data/validation_catalog.csv`, 68 rows):
  the validation registry joined to the benchmark tasks (the two registries
  were structurally disjoint), with grain, producer, wiring class and verdict
  adapter first-class. Builder `pkinv.report.validation_catalog` keeps the old
  existence gate and adds a FRESHNESS gate: a validation product wired as a
  run_all phase must be at least as new as the build's first key output, or
  the build fails naming it. On first contact the gate caught four real
  defects: `timeseries_validation.csv` was QA-cited but produced by nothing in
  the build (now a phase); the livestock province-rank validation's producer
  needs a model card held only in the companion repo (reclassified hand_run;
  ages are printed at build time, never written into the product, so the
  bytes stay deterministic); the road-weights row named its reader as its
  producer; and the railways ELK crosscheck regenerated cleanly but was wired
  nowhere (now a phase).
- **The validation scorecard**
  (`outputs/pakemis_validation_scorecard.csv`): the full (property × grain)
  space — magnitude/timing/geography × twelve grains — one row per cell,
  covered cells carrying verdict tallies and the best independence class
  achieved, empty cells as declared_absent ROADMAP rows. 9 of 36 cells are
  covered today; advancing validation step by step means turning one row.
- **Wired the live**: five validation producers that ran only by hand now run
  every build (agriculture timeseries validation, district rice records,
  district records multi, GLW district livestock, railways ELK crosscheck),
  plus the catalog+scorecard phase itself.
- **Retired the dead**: `pkinv.eval.run_system_eval`, `system_eval`,
  `timeseries_nowcast` and `rice_model_benchmark` pointed at directories that
  moved to the companion repository (`outputs/nowcast`, `outputs/ml`,
  `outputs/backcast`, `models/`) and their tests skipped silently; deleted,
  with the companion-repo lane carried as a typed catalog absence. The
  dashboard's system-eval panel degrades to empty by design.
- **Minimal io kernel** (`pkinv.core.io`): the one comment-tolerant CSV
  reader and the one banner-writing CSV writer (never a timestamp), used
  exclusively by new code; the ~145 existing reader clones migrate in a later
  declared sweep. The one core→sectors layering violation
  (`core/parameters.py` importing agriculture's fertiliser mix) inverted via
  an engine `parameter_overrides()` hook, byte-identical.
- The registry completeness sweep now recurses into `outputs/eval/` with six
  more name patterns; 32 previously-invisible files classified (5 new catalog
  rows, 27 typed out-of-scope entries). The benchmark-twin retirement
  (`benchmark_comparison.csv` vs `national_benchmark_comparison.csv`) is
  DEFERRED to the Wave-C sweep: the narrow twin has twelve consumers, wider
  than the map first showed, and a partial re-point would ship two half-moved
  lanes.

## [1.0.0rc32] — August 2026

### Exact ADM2 nesting: the boundary cells stop voting alphabetically

The eighteenth review's third wave. The grid's cell→district assignment had
been a rasterized `all_touched=True` label whose boundary-cell ties broke by
rasterization order — **alphabetical-last-wins**, an arbitrary rule at ~5.5 km
cells over 152 districts, with a ~2% off-polygon remainder hiding under a
bincount key of −1. Now: `data/gis/adm2_intersections_267x340.csv` (98,069
rows, committed like the proxy caches, manifest-hashed) carries the **exact
per-cell area fraction of every claimant polygon** (equal-area projection),
partition-of-unity asserted per cell; claimed cells renormalize over their
land claimants (a coastal facility's cell no longer donates its sea fraction
to nowhere), and OUTSIDE is an explicit row class for wholly-unclaimed cells.
Both ADM2 views consume the same fractional weights — the partition identity
that had silently drifted 92–103 Gg between the aggregate and sector views
under mixed mask/label paths is exact again — and the label array survives
solely for the S-class derivation. The old tie-break is documented here as
found-and-fixed.

**The native→ADM2 leg is asserted at last**: the shipped agriculture district
panel re-aggregates to the shipped provincial panel category-by-category at
the published precision (`tests/test_adm2_fractions.py`, alongside the
per-cell partition invariants).

**GLW validated at district grain, honestly**: GLW-4 EF-weighted shares vs
the PBS 2024 census through the fractional table — Spearman **0.586 over 99
matched districts**, a sober step down from the 0.8 province-rank figure, and
exactly the number a reader of the 15 GLW-fallback districts should see. It
validates the proxy, never the census-driven allocation.

## [1.0.0rc31] — August 2026

### Configuration S, propagated: one vocabulary, every grain

The eighteenth review's second wave. The survey configuration stops being a
national delta wearing four names (`S`, `observed_household_demand`,
`residential_dung_axis=S`, absence) and becomes ONE key —
`pkinv.core.configurations` holds the closed vocabulary
(`REF_2023_24`/`S_2023_24`), the three module constants consume it, and
`tests/test_configuration_keys.py` holds the closure.

**Per grain:** the annual product gains `configuration_id` plus residential S
rows and a TYPED dung-residual row (46.72 Mt diverted mass, no emissions
pathway — in the same frame as the rows it haunts, not only in the variants
file); the ADM2 view ships as `pakemis_adm2_survey_2024.csv` — the dung
provinces re-based to HIES's own reported split (the survey that supplies the
quantity supplies its geography), reference weights within provinces, the
declared module-grain coarseness stated; the cube states the configuration
axis rather than duplicating 6 MB of identical geography; and the ensemble
prices S **on the same draw_id** as the reference (dung components scaled
deterministically per draw through the rc27 component_scalers channel — no
RNG consumed, deterministic 447.01683 reproduced exactly, and the
configuration delta is now a per-draw difference).

**Acquisitions:** GHS-BUILT-S R2023A total+NRES surfaces landed (eight 1 km
tiles, hash sidecar) — the residential-built fourth member is HELD-NOT-YET-
WIRED, pricing deferred to rc32's fractional intersections and declared so in
the register; the PBS Census 2023 district cooking-fuel tables refused typed
(the census23 portal is an interactive dashboard with no stable table URLs;
province × urban/rural is already served by the held HIES quantities).

## [1.0.0rc30] — August 2026

### The eighteenth review's open-data corrections: the census re-base

**THE REFERENCE MOVED, deliberately, for the first time since rc27:
L 447.71688 → 452.14350, S 442.59021 → 447.01683 (+4.42662 Mt).** The
eighteenth review found Fecto's exact FY2023-24 clinker production publicly
reported — 651,048 t in the FY2025 annual report's comparative operational
table, fetched free from the PSX financials portal (the announcement stream
carries only briefing decks; the `annQtrStmts.php` API carries the report) —
which completes the 16-company producer census at **41,953,170 t** of observed
clinker production. Per the review's ask, the audited census is now the
reference activity for 2.A.1 (21.816 Mt CO2, no clinker fraction, no trade
term); the PBS-QIM×0.75+trade model it replaces (17.389 Mt) survives intact as
the named structural diagnostic with the census-vs-model residuals published
(census = 125.5% of the f=0.75 inference, 101.4% of f=0.95), and the fraction
axis is re-expressed as the model's own sensitivity. Earlier fiscal years keep
the model as their declared activity basis — a series discontinuity carried in
the annual product's `activity_basis` column, never a silent back-cast. The
kiln-fuel screening rides the completed census (13.38 → 13.59 Mt central).

**Sugar crushing timing, read not assumed.** PBS QIM's group row 1-3 is
effectively sugar alone, and its months print the crushing season — but the
label wraps, so seven of nine editions dropped the row SILENTLY (never even
quarantined). The wrapped-row rule (plus a fused-cell rescue for FY2022-23's
one-space layout) recovers all nine years of textbook seasons (July zero,
December peak); the power bagasse streams now ride their own year's sugar
months at TE2 where the activity reaches (FY2019-20..FY2023-24), and the
±1-month reporting-lag alternatives ship priced beside the reference
(`pakemis_bagasse_timing_variant.csv`), never applied.

**The F-gas free module.** The reviewer's premise was half-stale — the UNEP
anchor has been cited since rc22 — but two instruments were genuinely missing
and both are now free-built: UN Comtrade's HS-2022 HFC lines land as the
fourth typed screening lane (net imports 6.0 kt of substance in 2024, bulk +
mixtures, corroborating the UNEP supply without resolving species), and a
one-stratum CO2e-weighted equipment bank runs on the consumption series itself
under declared IPCC defaults — **4.42 Mt CO2e for 2024, bracketed 2.3–6.2 by
the 5–15% loss range**, shipping as `scope_plus_fgas_bounded_bank`, outside
every reference total, sitting exactly where a bank answer must: between the
CRT's near-zero and the 9.815 consumption ceiling. Kigali ratification
(2025-10-22, Article 5 Group 2) is now in the prose, and the UNEP profile is
archived as a dated snapshot.

**The NEPRA/K-Electric ladder in one table**
(`outputs/power_toe_reconciliation.csv`): national Table-3 energy (recovered
from the audit's own ratio pair — no calorific constant of the table's own),
CPPA plant sum, K-Electric plant sum, and heat-rate-implied coal energy, per
year and fuel. It settles nothing the configuration family leaves open — that
needs HDIP's metadata, the sector's one paid item — but every rung is now in
one place, with the review's proposed post-HDIP names mapped in prose.

**Access classes on the not-retained register**: every row now carries one of
six closed classes (openly-licensed / free-to-read / available-on-request /
paid / computational / dead-with-official-alternative), guard-tested.

**Stale-premise corrections owed to the reviewer**: OCAC industrial monthly
data was ALREADY fully ingested (36 editions; industry liquids ride Total
Industry at TE1/TE2 from July 2021, and the pre-2021 editions do not exist
publicly — that acquisition is the letter, not a download), and no "no HFC
anchor" claim existed to correct.

## [1.0.0rc29] — August 2026

### The clean-room round: the seventeenth review's reconstruction contract

**The re-audit came first, and it cut the number the reviewer was quoting.** The
review asked for "the 40 not-retained sources" to be reacquired; the rc29
re-audit tested every not-archived claim against the archive itself — the check
the register never had, now permanent in `tests/test_data_provenance.py` — and
found **eleven rows stale**: the CAA traffic tables, the OurAirports snapshot,
the OECD SDMX extracts, the SNGPL annual report, the OGRA pipeline tables
(whose transmission rows sum to the report's printed 13,526 km exactly), the
PBS QIM editions and the cement producers' fifteen annual reports were on disk
and hashed all along, their register rows simply predating the archive.
A twelfth row closed by genuine reacquisition (below). 40 → **28** of 146,
with `CLASSIFIED` in `scripts/make_source_register.py` now authoritative over
the committed CSV so a corrected judgement can never again be outvoted by a
stale row.

**The not-retained register** (`data/not_retained_register.csv`, 21 source
documents): exact URL, access date, page/table coordinates, retrieval script,
sha256 and the legal reason for non-retention — under a tested contract
(sha256 XOR-at-least legal reason; bijection with the not-archived rows;
named scripts must exist). The deposit view inherits it row by row.

**The reacquisition sweep** (fifteen typed outcomes in
`data/acquisition_attempts.csv`): HydroWASTE re-fetched and **hash-verified
byte-identical**; the Zenodo kiln record re-fetched and **identity-verified**
(all 11,272 keys); OurAirports re-fetched with all 195 held Pakistani airports
coordinate-identical; the PIA privatisation teaser re-fetched and **archived**
(closing its row); Comtrade/WDI/NASA-POWER/FAOSTAT routes verified live; the
Fatima PSX link found dead (portal IDs churn), the CDM pages bot-walled, the
PIA fleet page empty to unattended clients, PBS census and SBP supplement
undiscoverable unauthenticated — each a typed refusal, none a silent blank.

**Determinism before the rebuild:** every shipped PNG now drops the
matplotlib-version tEXt chunk (the one environment-tracking byte source;
in-place double builds byte-identical), and the stale
`archived-docs-not-in-git` gap row closed against a corrected audit — all 288
manifest-hashed documents are tracked (the manifest's document patterns now
also cover the .csv/.json/.nc/.txt witnesses that previously fell through).

**The empty-environment rebuild** (`scripts/clean_room_full.sh`, beside the
untouched quick gate): fresh `file://` clone, LFS materialisation with a
pointer preflight, fresh venv from `requirements.lock`, an unroutable proxy so
any network attempt fails loudly, the full offline build, the full suite, the
PDF build, and the manifest comparison — with the run published as
`docs/rebuild_log_rc29.json` + `docs/rebuild_log_rc29.md`, unresolved
failures typed. **Verdict: PASS_WITH_NOTE** — clone of the phase-2 record
commit, Python 3.11.10, 2,192 tests all green offline, every committed data
output byte-for-byte including the figures (closing the
figures-not-byte-reproducible gap on the run's own evidence); the only
differences are the two declared artifact classes (in-place national PDF;
the manifest's describes_commit block, zero substantive lines). The gate bit
twice organically before the sabotage check passed: the pointer preflight
caught its own materialisation defect, and the clone's suite caught a stale
committed deposit manifest — now held by a regeneration-identity guard.

**Identifier preparation, minting user-only:** the manifest carries the third
DOI slot (software/data/**documentation**), the data record's metadata is
prepared not-yet-deposited (`docs/zenodo_data_record.md`), and the
reproducibility checklist now walks all three deposits plus the LFS push that
unblocks a stranger's clone. FAIR fixes riding along: `outputs/SHA256SUMS`
(the flat file `shasum -a 256 -c` reads), and the ODbL carve-out lists
reconciled (7-vs-8 drift; now guard-tested identical).

## [1.0.0rc28] — August 2026

### The seventeenth review's consistency tier

No number moved. Seven internal inconsistencies the review named — every one a
manuscript describing a superseded state of the engine — are repaired at the
root, and each carries a ban or positive test so it cannot regress:

1. **NFDC timing** — the real defect was structural: two vintages of the
   fertiliser profile were alive at once (`nitrogen_profile()`, the Annex-7
   borrower, still fed the monthly crosscheck while the layer used the
   consolidated Table 3.4 months). One shared selector
   (`published_nitrogen_profile()`) now serves both; the crosscheck rebased
   (Σ|Δ| 51.34 → 51.5 pp/yr, zero borrowed months), the figure legend and both
   prose sites follow, and "remaining three are borrowed" is banned while
   `borrowed_from_year` stays empty.
2. **Axis count** — twenty-four registered / twenty-three priced, corrected in
   the abstract, results, product catalog **generator**, uncertainty contract
   and the trajectories docstring (now deliberately non-numeric). The same
   paragraph hid a **fifth count defect the review did not name**: "Three
   further rows are declared exceptions" was eight; fixed and the five scope
   screenings are named.
3. **"Reaches the grid from nowhere"** — rewritten to the shipped truth: the
   2.01% never reaches the grid; it is retained at province level in
   `pakemis_spatial_unallocated.csv` under the closure identity
   ADM1 == ADM2 + unallocated. Phrase banned.
4. **Rice geography** — the review's premise ran **backwards**: MapSPAM rice has
   been HELD since rc26 (`data/gis/manual/spam_rice.tif`, hash-pinned,
   fallback class deleted fail-closed); the stale side was fourteen "not
   held" prose sites and a never-regenerated `gis_report.md`. All rewritten to
   held + GCD-Rice 2023 crosscheck + priced bracket; "MapSPAM is not held"
   banned while the file exists.
5. **Transport nine vs ten** — the fuel series is genuinely ten editions
   (FY2015-16..FY2024-25; road-share envelope 0.83–0.91 re-verified over all
   ten rows); eight sites flipped and one declaring sentence added: the tenth
   edition extends **beyond** the national panel — a declared extension, not a
   disagreement.
6. **Sector-paper monthly synchronization** — the three sector papers whose
   streams the national monthly product resolves now document their own
   engines: power (PBS plant-month FY2015-21 / NEPRA SIR FY2021-24, coal TE2 /
   gas TE3, the refused years named), fugitives (upstream-only per-source-year
   timing with the wrong-driver refusal for demand-side streams), waste (the
   continuous single-pool monthly FOD recursion with own-year deposits and the
   exact annual control).
7. **IPPU cement** — `06_results` still described the pre-rc26
   province-proxy-only allocation while `08_limitations` overclaimed
   "facility-resolved". Both now agree on the shipped hybrid
   **facility-assisted** mechanism: province shares control, located works at
   company census clinker (uniform within company), built-up fallback per
   ledger event, S2 not S1 at 19/34 coverage.

Plus the review's framing ask on fugitives, made standing: the abstract and
conclusion now state the reference is an **upper-practice conservative
configuration, not an empirically centred best estimate** — no probability
attaches to any point in the 9.601–24.694 envelope — and
`TestFugitivesEnvelopePolicy` asserts the disclaimer positively, so it cannot
be edited out.

The two binding ceilings (21.01% variable-unobserved monthly; the ~47 Mt scope
floor) are typed by the scorecard as letter-gated and are deliberately not this
release's work; the clean-room rebuild is its own subsequent round.

## [1.0.0rc27] — August 2026

### Pass 2, Wave 6: joint uncertainty + THE SCIENCE FREEZE

The last engineering wave. The exit gate is now a shipped artifact
(`pakemis_pass2_scorecard.csv`): **outcomes 1 and 3 MET, outcome 4 MET with
named exclusions, outcome 2 REFUSED BY TYPE** with its arithmetic printed —
21.01% variable-unobserved against the ≤15% target, and exactly one acquisition
(MON-OCAC-01's pre-July-2021 monthly editions, drafted and unsent) decides it at
13.4%. Journal conversion is unblocked.

**Two envelope defects repaired.** Power's measured hindcast dispersion (WAPE
45.24%) was being silently clobbered by the structural fuel-mix variant's 13.61%
— the largest category in the inventory excluded from the drawn set while rc20's
changelog claimed it was in; the variant is now a fallback and power is the
seventh drawn category. And the rc26 rice GCD bracket, joined by MODULE, had
priced its 4.66 pp onto Enteric fermentation (151.5 Mt of livestock whose
placement rides a census) — the sole cause of the rc26 envelope widening; the
placement join is now stream-scoped, the captive bracket no longer reaches the
grid, the grid prices its own points-vs-builtup bracket (9.47 pp), and
residential's structural-invariance proof is a priced zero, not an absence.

**Per-draw gas closed.** The rc19 identity — leaked gas is never also burned —
held at the mean and in no single realisation: combustion netted by a fixed
0.997% while fugitives drew the same factor ±60% inside its CRN island. The
fugitives draw file now persists its post-meter factor multiplier as a parameter
channel (no randomness consumed, prefix property untouched), every net-of-leak
component scales by its draw's own combusted fraction, and the coupling is the
one licensed cross-island channel — the tripwire names it, positive controls
prove severing it breaks the identity. The national interval moved by less than
0.02 points.

**The water-regime axis, priced from held data**: SPAM's irrigated/rainfed split
(98.2/1.8) gives weighted SFw 0.594 — the registry's unanchored "~0.71" matched
no IPCC value and is retired — and `rice_water_regime_weighted` prices −6.71 Mt,
never averaged. **The aviation re-base question is a configuration**
(`aviation_route_resolved_reading`, −0.030 Mt) with the reference move refused by
type on the provisional stamps and the 0.98–3.81× reconciliation spread. 24 axes,
28 configurations.

**The uncertainty grain fills in two honest tiers**: seven axes `available (…)`
on the national seed, waste's two `available_independent_run (…)` on their
private per-scenario seeds — a new typed state, because implying per-draw
comparability would be false.

**Freeze state corrections**: the managed-soils 116 Mt the registry carried as
open-data-movable is reclassified (the decomposition's own note forbids the
offtake shape — a status the arithmetic contradicted); the field-burning driver
names VIIRS, not the never-acquired MCD64A1; the FY2015-16 bridges are
`declared_historical_moot`; the declared-absence-untested gap row — still
asserting "TRANSPORT STILL OPEN" two releases after the recovery — is closed;
"Waste remains flat throughout" is fixed and FALSE_WHILE-banned beside its
fugitives sibling; the IPPU limitations no longer await locations Wave 5
consumed. The rc25 changelog's "screened 54 → 189" overstated: the shipped count
was 153, recorded here rather than edited there.

## [1.0.0rc26] — August 2026

### Pass 2, Wave 5: the spatial facility program

The point-unresolved gap — 75.34 Mt (16.8% of the inventory) with real locations
the allocation did not use — collapses to **0.13 Mt**: the two LNG terminals, now
a typed refusal rather than a silence. No annual or provincial figure moves; the
whole wave is below-province placement.

**The rice contract is fulfilled, then measured.** MapSPAM 2020 (V2r2) landed as
`data/gis/manual/spam_rice.tif` — the declared proxy since rc9 — and its
cropland-fallback class was DELETED from the allow-list, the firms precedent, so a
checkout without the raster now refuses the fixpoint. Beside it, the OWN-YEAR
instrument: GCD-Rice 2023 (30 m classified paddy, doi:10.57760/sciencedb.21665,
~88.9% accuracy) aggregated to the grid and published as
`pakemis_rice_geography_crosscheck.csv` — and the two surfaces disagree hard
(25–62% of each province's rice mass in different districts), so the disagreement
ships as a priced ADM2 bracket (`agriculture_rice_gcd2023_adm2`, max per-shape
spread 4.66 pp). The reference stays SPAM until that evidence is reviewed.

**The grid fleet is consumed.** A new corroboration rung — province contains the
point AND the source's own name confirms the declared town — takes the fleet from
42 to 56 corroborated stations (34 of 78 emitting), and the cube now routes
`facilities:power_grid` through the captive pattern: located stations weighted by
their OWN FY2023-24 plant-ledger fuel per stream (coal/gas/RFO/HSD, billing units
made commensurable at the declared reference HHV), built-up fallback per province
with a declared ledger event. 57.82 Mt moves S3 → **S2, earned by the dispatch**
— and pinned against S1 while coverage sits below 95%.

**The IPPU register is consumed at its honest grain**: located cement works carry
their company's producer-census clinker, split uniformly within a company because
the census is company-grained and a per-plant split is published nowhere acquired.
17.39 Mt S3 → S2. The eight fertilizer complexes stay unlocated with their
screening categories.

**The gap metric learns the difference** between a located fleet the allocation
ignores (still `point_unresolved`) and partial points the allocation consumes with
declared fallbacks (`point_resolved`): the discriminator is now the placement
register the cube's dispatch is proved against, not the geocoded fraction alone.
Spatial profile: S2 rises 5.94 → 81.3 Mt; S3 falls to ~78%.

**The spatial-grain register gains its first entry** (the reserved Wave-5 schema):
the dung axis's S reading consumes the same district panel as the reference, so
its ADM2 placement is provably the reference's shares rescaled.

## [1.0.0rc25] — August 2026

### Pass 2, Wave 4: annual completeness — every gap decided, the floor measured

The annual-scope wave. No reference figure moves; six new configurations price what
was countable and every remaining absence is typed.

**The completeness-mass ledger** (`outputs/pakemis_completeness_mass.csv`): the
first artifact that joins an absence's state to its mass. One row per candidate
stream outside the reference, carrying the scope status, notation key, coverage
state, configuration and the bound the shipped arithmetic supports — with contained
claimants excluded from every sum. The reviewer's "countable floor ≈ 47 Mt", which
the tree could not previously reconstruct, is now quoted beside a MEASURED band:
**36.40–57.00 Mt** over thirteen bounded streams, the target inside it, every
component a row.

**Six configurations join the register** (20 → 26 rows, 22 axes):
- `commercial_institutional_in_scope` (+2.43): the 1.A.4.a audit's two-stream floor,
  configured at last — BUR-1's filed 3.8 above it, as a floor should sit.
- `coal_mining_fugitives_in_scope` (+0.55): the Thar surface screen's top, PARTIAL
  by construction and labelled so on every row.
- `captive_coal_in_scope` (+1.31): one of the fuel ledger's two `neither` claimants
  priced from the captive register's own capacity under declared utilization and
  heat-rate judgements; captive FO/diesel excluded on double-count risk, captive
  bagasse as a sub-claimant of the all-cane ceiling. The other `neither` claimant
  (industrial coal/petcoke) becomes a typed refusal naming HDIP PEY.
- `nitric_acid_unabated_in_scope` (+1.05) and `nitric_acid_abated_in_scope`
  (+0.73): the pair 2.B.2's own activation gate names, from the Sadiqabad plant's
  calendar-2022 production and its ACM0019 record (CERs re-expressed from the SAR
  GWP, annualised over the monitoring period's own days). 2.B.2 was MISSING from
  the national completeness register entirely — the same silent-absence class the
  1.A.4.a audit once closed — and now has its row.
- `ammonia_feedstock_in_scope` (+9.87): the gas-balance ceiling the fertilizer
  sector's own metered draw supports, net of urea-recovered CO2. Even the ceiling
  is roughly HALF Pakistan's filed 19.4 Mt comparator — the reconciliation's red
  flag made quantitative.

**Bounds below materiality, no axis noise**: steel 2.C.1 at the route-matched EAF
factor (~0.39, zero reported pig iron makes the electric route the only supported
one), soda ash 2.B.7 route-agnostic ceiling (~0.08), navigation 1.A.3.d typed
refusal of a configuration at 0.01. Glass and lime: typed refusals naming closers.

**The scope registry walks through its own doorway**: `completeness_mass.py` is the
first deliberate reader — a VALIDATOR that fails the build when a screening row
names a configuration that does not ship or a mass the build does not price. The
no-op gate test admits exactly this reader and guards everything else.

**The coverage matrix's screened state moves from module-keyed to code-mapped**,
fixing two defects: the F-gas screening never lit 2.F at all (its id lacks the
`in_scope` substring the old gate matched), and any module-wide gate would have lit
unrelated NE cells. Screened cells 54 → 189; both directions of the map are
validated so a screening can never again be invisible to the matrix.

Also: the stale −0.286/−0.287 gas-deduction prints corrected to the shipped
+0.28767; the axis-register and coverage-matrix docstrings stop carrying frozen
counts; the configurations prose count re-anchored (eighteen single-axis).

## [1.0.0rc24] — August 2026

### Pass 2, Wave 3: timing becomes computed physics

The process-reconstruction wave, all five workstreams:

**Rice moves onto cultivation area-days.** The old profile was Punjab-only,
week-counted, landed all of rice CH4 in Jul–Sep through a drifting week→month
map, and contradicted its own annual model (63 flooded days vs the area-weighted
125-day cultivation period). Now: per-province cultivation windows (transplant →
harvest end, FAO-corroborated) as real dates, weighted by the audited MNFSR
harvested-area shares — the ~126 Mt CH4 stream spans Jul–Nov and the two models
describe one process. Three defects fixed on the way: the dead "crop calendar"
needle that had every rice row's provenance crediting the FERTILIZER annex; the
"Maïs" key mismatch that silently dropped maize from the burning comparator; the
malformed Punjab calendar row.

**Returned residue nitrogen gets a mineralization kernel**: FAO harvest windows
followed by a declared-e-folding release (residue_mineralization_efold_months, a
named judgement), crops weighted by returned-N, the prior season's tail folded
across June 30 at cyclic steady state — the two Managed-soils residue subitems
leave the flat catch-all as T3.

**The fire record now spans all nine years, and the attribution ladder corrects a
real error.** 1,664,876 VIIRS detections fetched over FAO-derived crop windows
(burn_windows.py, wrap-safe for the cane season; zero failed spans). The ladder —
national mask, cropland raster, kiln exclusion — publishes its counts through the
crosschecks, and the headline is the mask's: **71% of the raw record inside the
fetch box is Indian Punjab's fires**, which the pre-Wave-3 profile weighted into
Pakistan's burning months. Attributed-only, Pakistan's burning is wheat-season
led (May peaks, 0.20–0.34, differing year to year — the nine-identical-shares
era ends) and eight sector-years leave flat T4.

**The FOD becomes one continuous monthly state engine** from the 1960 spin-up:
stock flows across fiscal boundaries, each month deposits its own calendar
year's tonnage (killing the max(series) leak that injected 2024's rate into
2015's stock), leap-exact month lengths, and the reaction delay a declared
parameter applied as shape only — the annual control preserved exactly. The
spread figure is COMPUTED into the basis at build; its hard-coded predecessor
was the "number no code computes" failure class again. First-ever gates on the
monthly shape, including the delay positive control.

**Crosscheck-licensed dispersion**: a published two-instrument share comparison
is a measured mean absolute error — the same L1 quantity a hindcast WAPE is — so
Managed soils (fertiliser check) and Field burning (burning check) join the
drawn-profile family under an explicit timing_basis vocabulary. Livestock's
continuous-by-process classification is pinned by test; rice and the FOD stay
degenerate honestly (no second instrument measures their shapes).

No annual figure moves.

## [1.0.0rc23] — August 2026

### Pass 2, Wave-2 remainder: the pre-sheet years answered honestly

The last Wave-2 items, each resolved by held evidence or a typed refusal:

**FY2016-17 Coal TE4→TE2 (0.117→0.942, 1.52 Mt)** through the immutable-fuel carry:
"Coal Power" is Sahiwal's commissioning-year spelling, identified by control
exclusion (Lakhra's labelled 124 GWh + this 873 = 94% of the 1,059 GWh coal
control; no other coal station by June 2017) and labelled from the earliest listing
sheet under a coal-only rule — a coal boiler cannot convert away from coal, which
is the entire licence, and the lane is gated to coal alone by test.

**PBS minerals reach 8 of 9 years for BOTH gas and crude oil** (from 5 and 6) with
zero new documents: the bare-"Gas" canonical key (FY2021-22), the three-line
name-wrap stitch whose glued cell was also swallowing Punjab's July (FY2022-23),
and the total-only recovery — FY2016-17 prints gas and oil as national-Total rows
the parser had discarded as empty-group controls; the total IS that edition's
observation. Only FY2015-16 (bulletin not held) remains: the one live request.
Fugitives' upstream timing re-grades accordingly.

**The FCA corpus is held, typed, and refused.** 180 determinations fetched and
hash-pinned (data/raw/nepra/fca: 49 XWDISCO 2015-2017+2020, 132 K-Electric
2015-2021; one fetch failure typed). The recon's missing months are CORRECTED —
April 2016 and a combined Feb-Mar 2017 determination exist under non-guessable
names — but the parse refusal stands: scans whose OCR corrupts digits, plant-wise
annexes in only a subset of 2016 months. The COVID fuel-wise crosscheck was
attempted and REFUSED on the same grounds (4 of 8 blocks render; digits corrupt) —
Feb-Jun 2020 is anyway carried plant-wise by the held FY2019-20 listing sheet.
K-Electric's structural negative is recorded: no plant-wise KE generation exists
anywhere on NEPRA; the determinations reference a submitted "plant wise generation
statistics sheet" never annexed, and the CPPA/NEPRA/KE letter now requests exactly
that named sheet. Four search-log rows carry all of it.

**The eight request packets are complete** (drafts only, nothing sent): four new
non-timing lanes paying into scope-registry activation gates (HDIP fuel balances,
PBS-CMI industry-by-fuel, NFDC plant-level gas separation, IPPU facility operating
data), PPIS and WASA recipients added, seven letters drafted.

No annual figure moves.

## [1.0.0rc22] — August 2026

### Pass 2, Waves 0–2: the control layer, the NFDC false gap, and the seven-year power record

The sixteenth review's Pass-2 program opens (science before prose; manuscript
conversion deferred to the science freeze). **Wave 0** froze the rc21 baseline
(`docs/pass2_baseline.md`), added the control layer — scope registry with activation
gates, temporal-driver registry generated from the decomposition (304 Mt of unobserved
mass has an open-data path), facility-registry time-validity columns, source-manifest
revision lineage, request-log lifecycle — under a structural no-op gate, and fixed the
review's seven science-truth defects at their generators (the "partial by declaration"
status two releases stale, the S4 cube-layer caption, one unanchored 87, the "observed
gas months" category error, the transport ten-year window, the typed
spatial/uncertainty configuration grains, and the published flat-share bridge
`pakemis_flatness_crosswalk.csv`).

**The NFDC false gap** (Wave 2, the review's pointed case): the held Annual Fertilizer
Review 2023-24's Annex-5 carries all twelve July–June FY2023-24 offtake months — the
same document whose Annex-7 layout had the reference year borrowing April–June for two
releases. `scripts/ingest_nfdc_annex5.py` reads it into the Table 3.4 panel under the
page's three printed identities; the consumer flipped lanes with zero code change;
every reference fertilizer month is now observed T2; the Annex-7 provincial table
became the cross-check (exact to the tonne July–November, then up to half a percent
under — a boundary difference, bounded in its direction). The whole-month application
lags are priced and refused (`pakemis_fertilizer_timing_variant.csv`: no lag improves
on lag-0 against the agronomic calendar).

**The power record now spans seven SIR years.** The four earlier listing sheets
(FY2017-18..FY2020-21) were fetched and serve two jobs without ever entering the
panel: the PBS-overlap validation (`power_sir_pbs_overlap.csv`, 144 subitem-months,
worst share gap 4.6 pp — two independent vintages of one fleet agreeing within five
points of a month) and the SAME-YEAR fuel crosswalk: thirteen declared PBS↔SIR name
pairings, corroborated by magnitude at use, label the stations PBS's fuel column
leaves blank. Grid coal rises to TE2 in FY2017-18/18-19/19-20/20-21
(0.29→0.95, 0.48→0.98, 0.75→0.98, 0.72→0.98 of the annual control, all stated labels);
gas reaches TE3 in FY2018-19 and FY2019-20 through the per-member annual-control bound
(HSD controls of 28 and 1 GWh), and the bound honestly refuses FY2017-18 (788 GWh) and
FY2020-21 (402). Sahiwal is finally labelled — by the regulator's same-year sheet,
never by its "Coal Fire" name. The full 4,644-document daily archive download runs as
Wave 1 (resumable, hash-derived manifest statuses).

No annual figure moves. Deferred, typed in the registries: the CPPA-FCA corpus crawl
and FY2015-17 parse, the K-Electric lane, PBS bulletin vintages.

## [1.0.0rc21] — August 2026

### The power archive parsed: the reference year's grid gets its months

**The SIR listing sheets ARE the plant-month table.** rc20 typed NEPRA's
Detail-of-Generation archive as a 4,644-document parse backlog; this release found the
archive's own company listings (`data/raw/nepra/sir_detail/sir_companies_20*.htm`, held
since rc20) carry the complete plant×fuel×month table for FY2021-22..FY2023-24 — twelve
(utilization %, GWh) pairs plus a printed Sum per plant row. `scripts/ingest_sir_generation.py`
reads them under the row identity (twelve months meet the printed Sum) into the same
panel the PBS lane feeds (`generation_monthly.csv`, now 15,564 rows over nine years),
and `pbs_generation.shapes()` consumed the new years with **zero code change**. Both
ingests are now lane-preserving: re-running either cannot delete the other's years.

**Grid coal and gas leave the flat profile at the reference year.** Coverage against
NEPRA's own Table-17 annual control: Coal 98.3/97.4/98.5% → TE2 in all three years; Gas
reaches TE3 in FY2022-23 (80.2%) and FY2023-24 (75.1%) through the **annual-control
bound** — the RLNG/HSD combined-cycle group (22,944 GWh at the reference year) is
assigned to gas because the country's entire HSD control (126.6 GWh) cannot account for
even one percent of it; the bound reuses the PBS lane's DOMINANT=0.95 and any subitem
carrying bound-assigned mass is **capped at TE3** (inferred fuel is never TE2). The same
rule *refuses* FY2021-22 gas: the bound reaches 94.0%, one point short, so the year
stays TE4 on the record. Furnace oil and diesel deliberately stay on the OCAC panel —
a TE3 generation shape must not displace T1/T2 sale months — and the two instruments
are published against each other in `monthly_crosschecks.csv` (worst monthly gap 8.1
points, the honest width of the liquids' timing claim). Power's reference-year flat
share falls 96.96% → 8.79% (captive and bagasse remain, by design).

**Five sheet defects found and arbitrated by the archive itself.** FY2021-22 has five
rows whose printed Sum fails its own months (~49 GWh of 143,253). 68 per-plant daily
reports were fetched from the archive (64 of the 68 compared cells agree exactly; the
four disagreements are the four corrections): UCH-II's January repeats February, FFC's May drops a
leading digit, FWEL-II's March and Daral Khwar's September misprint one cell — each
corrected in `sir_month_corrections.csv`, hash-pinned to the daily report that decides
it, applied by the ingest under a close-or-refuse gate; Jamshoro's twelve months all
agree and its printed *Sum* is the typo. The discrepancy ledger
(`sir_row_discrepancies.csv`) keeps all five with their resolutions. The document
manifest now derives download/parse status and per-document sha256 from the held tree;
the month manifest's 36 SIR months read `sir_listing_ingested+sir_discovered`.

No annual figure moves: this is a timing/evidence release. The national flat (T4) share
and the monthly product's peak/trough re-anchor in this release's regenerated claims.

## [1.0.0rc20] — August 2026

### The fifteenth review's two passes: public-record recovery + modeling

**The panel is complete: FY2015-16 recovered from the public record.** The last two
absent sector-years — road transport and industrial combustion FY2015-16, "blocked on
an OCAC edition that exists nowhere in the record" for four releases — closed when the
review pointed out the Pakistan Oil Report 2015-2016 is publicly served on ocac.org.pk
as a 602-pixel image flipbook, page 50 being the product-by-sector table. Transcribed
under a quadruple identity gate (`sectors/transport/ocac_image_edition.py`: row sums,
block sums, column sums, and the TWO-DOCUMENT gate — the recovered Road and Total
Industry totals equal the FY2016-17 edition's independently held prior-year column,
12,440,195 and 2,023,377 t, exactly). Both engines built the year with zero code
change: transport 43.36, industry 12.58 Mt → **FY2015-16 = 372.39 Mt, ten sectors,
100% scope; the 90-sector-year rectangle has no NE cell**. The harmonized window opens
at FY2015-16; the trend product's two windows merged into one full-panel window whose
decadal change (75.33 Mt) resolves under **every** correlation scenario — even full
time-independence, for the first time. The unallocated-controls ledger's rows became
the recovery's cross-document gate; the FY2015_16_FULL_SCOPE_BRIDGE stays declared and
permanently unpopulated.

**The power lane (staged per the review).** NEPRA's SIR Detail-of-Generation archive
discovered: a plant-month (daily-grain) PDF archive of 4,644 documents covering exactly
FY2021-22..FY2023-24 — the years the ingested PBS panel stops at — with the GENCO
directories (CPGCL/JPCL/NPGCL) as the named fuel crosswalk for the two years PBS cannot
label. All **108 service months now carry a typed source** in
`data/manifests/power_month_manifest.csv` (72 pbs_ingested + 36 sir_discovered, zero
untyped gaps); the per-document backlog is typed (`parse_status`), the pilot parse
established the schema (energy-only — settlement never becomes fuel burn, per the
review's own rule), and MON-CPPAG-01 shrank to the residual.

**Timing recovered from records already held.** Residue burning rides the 109,693
held VIIRS detections (FRP-weighted, T3 — the windows are the calendar's claim), with
a real FIRMS-vs-FAO-calendar crosscheck bounding what the two windows cannot see;
industry's gas streams ride PBS QIM production as a declared proxy (T3; the sector's
months went 71% flat → 62% T3); solid-waste disposal runs the FOD at a monthly step
(measured spread 7.1% of a flat month, of which month lengths are 6.7 — the flat
profile was approximately right, now measured). Three falsifiable prose claims in the
temporal decomposition (FIRMS "used as a crosscheck", a monthly-FOD spread no code
computed, QIM "calendar 2022 only") replaced by statements the shipped code computes.

**F-gases priced, not added.** UNEP's aggregate Annex-F consumption (2019/2020/2024/
2025 reported; 2021-23 missing-not-zero) anchors `scope_plus_fgas_screening` — a
potential-consumption-equivalent scope bound (+9.815 Mt) OUTSIDE every reference
total, with three typed evidence lanes never blended (consumption 9.815 / Pakistan's
own CRT 2.F filing 0.003 / EDGAR benchmark 11.54). 2.F stays NE.

**Ensemble and schema.** The measured-dispersion license now covers every
hindcast-scored stream (drawn monthly profiles 2 → 4 categories); configuration S
ships at monthly grain (`pakemis_monthly_survey_2024.csv`) and the axis register
carries a typed `monthly_grain` column; every raw acquisition carries an
`extraction_method` from a closed vocabulary with the identity-gate pricing rule
documented; the request register gained the NOU/FBR, NHA and PBS-FY2015-16 lanes with
ready-to-send letters (nothing sent).

## [1.0.0rc19] — August 2026

### The fourteenth review's semantic release freeze (Pass 1): the gas boundary decision

**The re-freeze this changelog has promised since rc14 happened: net-of-leakage gas
combustion is canonical.** The post-meter leak factor prices ~1.0% of delivered
industrial and power gas as leaked; until now the reference booked the same molecules
as fully combusted, keeping the double-claim on both sides deliberately. The
combustion engines (power grid gas, captive, general industry, cement) now book their
gas rows NET of the whole-gas leaked share — all three gases, because gas that leaves
upstream of the burner tip produces none of them. The share has one home
(`sectors/fugitives/post_meter`, (6.1/0.90)/680 = 0.997%), replacing the twin 6.1
constant `report/gas_closure.py` had carried for two releases. The leaked molecules
stay in the inventory as 1.B.2 fugitive CH4 — this removes a double-claim, not
emissions (CO2-negative, CH4-neutral at the national level; fugitives 24.694
unchanged).

- **New reference totals**: L 448.00456 → **447.71688**, S 442.87788 → **442.59021**;
  grid power 57.99582 → 57.82049, captive 5.605 → 5.549, industry 1A2 9.066 → 9.010.
  The nine-year series, annual product, monthly layer, cube and every family member
  re-based; family deltas are invariant (the netting shifts both sides of each power
  reading identically).
- **The gross view survives as the named alternative**: the joint configuration
  `gas_combustion_net_of_leakage` (−0.287) is retired and inverted into
  `gross_delivered_gas_accounting` (+0.288 back to the administrative fuel-accounting
  total), for readers reconciling against fuel-sales statistics.
- **The per-draw gas identity**: the first cross-module dependency group,
  `delivered_gas_ogra_3_31`, shares one activity draw across the residential, CNG,
  industrial and captive delivered volumes (one OGRA Table 3.31 publication, each
  module keeping its own declared width via the select rule). The industry module
  gained its first uncertainty-inputs register to carry its member. The fugitives
  island and the NEPRA-metered grid volume stay outside, declared in the sources
  registry and the closure ledger. The CRN-island tripwire holds.
- **The fourteenth review's two textual defects**: the limitations sentence claiming a
  complete trend needed "four further years of national cement activity" (all nine
  IPPU years estimated for two releases) replaced with the FY2015-16-product-splits
  statement, anchored to the product-facts registry in both directions plus a
  predicate phrase ban; `papers/pdf/README.md`'s "is submitted" claim corrected to
  "being prepared for submission", with `release.MANUSCRIPT_STATUS = "preparation"` /
  `SUBMISSION_IDENTIFIER = None` now carried in the manifest and both READMEs swept
  by a status-conditional guard (the papers/pdf SKIP no longer shelters the claim).

## [1.0.0rc18] — August 2026

### The thirteenth review's consistency freeze (Pass 0)

No numerical product moved. The seven cross-document contradictions the review found are
fixed, each with a guard that makes its recurrence a build failure:

- **Transport shape**: three national-paper sites said provincial AND fleet shares were
  borrowed; the provincial shape has been the reference year's own twelve direct OCAC area
  pages since the re-base. The canonical statement (provincial direct, fleet/class
  composition borrowed from FY2022-23) now stands everywhere, with a predicate-guarded
  phrase ban.
- **Cement timing**: the "borrows a monthly production shape from calendar 2022" sentence
  was a retired vintage contradicted 81 lines later in the same section; removed, banned
  while cement's own months stay wholly TE2.
- **Trend resolution**: the "spans zero (-7.43 to 117.33)" interval matched NO live row -
  a superseded run quoted as current. The resolution statement is now written once from
  pakemis_trend_uncertainty.csv with scenario and scope on every number: under the typed
  scenario 0 of 8 consecutive changes resolve, the common-scope FY2016-17..FY2023-24
  window resolves at 16.95-92.00 Mt, the coverage-transition FY2015-16 window at
  44.64-118.05 Mt; only full time-independence leaves the common-scope change spanning
  zero. The superseded bounds are banned literals; README aligned.
- **Fugitives flat**: "Waste and fugitives are flat throughout" replaced by the split
  statement (upstream monthly at 40.9% TE2; demand side deliberately flat), banned while
  the temporal profile shows fugitives T2 above zero.
- **Fugitives 168 and the missing central member**: the supplement said 168 configurations
  against the engine's 224 and its conditional-interval table omitted the central member
  the paper describes; the table is now a GENERATED fragment
  (scripts/make_fugitives_conditional_table.py) and the README generator counts the
  factorial instead of remembering it. "168 structural" is a banned literal.
- **Transport scenario status**: "will be published as scenario rows" - the
  class-composition cases ship in transport_uncertainty_scenarios_2024.csv and the paper
  now names the rows. The 48-vs-36 edition confusion is resolved by
  outputs/ocac_edition_inventory.csv: two true counts of two different populations
  (cumulative aviation-fetched vs direct area-page editions), now distinguished.
- **README "is submitted"**: the review flagged a claim the README does not make - it
  already states no manuscript has been submitted. No change; recorded here as the
  review's own erratum.

Also: the abstract states the scope plainly (448.00 is the total of the estimated PakEmis
scope; FY2015-16 explicitly partial at eight of ten sectors); the superseded-vintage sweep
now reads every manuscript via its own input graph plus docs/*.md, which immediately caught
a pre-transport-round total surviving in docs/reproducibility.md - whose release-history
section moved here, where history belongs; configuration counts are product facts
(structural_axes 20, named_configurations 19, fugitives factorial 224, conditional
intervals 5), counted at build time.

## [1.0.0rc17] — August 2026

### Removed
- `docs/ROADMAP_STATE.md`, `data/v1_gate.csv` and `tests/test_v1_gate.py`. The roadmap tracked
  the **rc1** reviewer's eleven stages across 1,004 lines and had been superseded by several
  review rounds; keeping it meant two documents competed to say what was outstanding, which in
  a project whose hardest problem is cross-document contradiction is a contradiction generator
  rather than a record.

  The gate register went with it for a sharper reason. Its gate G1 read *"No material
  cross-paper contradiction remains — met"*, and a review then listed nine. The register was
  asserting a whole-corpus property that nothing in it could check: `tests/test_v1_gate.py`
  verified that the roadmap's table agreed with the CSV row for row, which is agreement between
  two documents about a claim, not evidence for the claim. A gate that can only check its own
  paperwork is worse than no gate, because it reads as assurance.

  What the roadmap actually tracked is not lost: the per-claim machinery it pointed at —
  `data/claims_registry.csv`, `tests/test_paper_numbers.py`, the completeness matrix and
  `data/data_gaps.csv` — remains and is checked against outputs rather than against prose.


The three items that stood between this inventory and an A− acceptance standard, and the
defects that closing them exposed. Each pass found something it was not sent for, which is
the honest summary of the release.

- **The agriculture seam was an off-by-one, not a philosophy.** The nine-year history read
  the FAOSTAT series at the fiscal-END year for every crop. FAOSTAT labels a crop by its own
  harvest calendar year, and a Pakistani fiscal year holds the *kharif* crop harvested in the
  preceding calendar year and the *rabi* crop harvested in its own — so the mapping was right
  for wheat and a full year out for rice, maize, sugarcane and cotton. Measured against the
  Economic Survey's fiscal tables, those crops agree to 0.01–0.13 % one year back and disagree
  by 7–11 % where they were read. **FY2022-23, the year of the floods, shipped with 3.64 Mha
  of rice — the *following* year's recovered crop, against an actual 2.98 Mha.** The fiscal
  replacement had been transcribed into `data/activity/agriculture/es_fiscal_series.csv` in
  August and read by no code for eighty-eight commits: a declared *source* that did no work.
  The history is rebuilt per driver — four categories on observed fiscal activity, enteric
  fermentation and manure management (77.36 %) still on the FAOSTAT livestock projection
  because Pakistan publishes no fiscal *enumeration* of the herd, with the residual six-month
  phase error measured at under 2 % rather than asserted. Cotton, absent from all eight
  history years and present at the anchor, is priced separately from the basis change because
  a scope break and a source break are different claims. Eight backcast years move −4.05 to
  +3.38 Mt; the reference year and 448.00456 do not.
  **This supersedes rc16's statement that the pre-anchor record is a hybrid diagnostic series
  rather than a trend-safe one.** That was true of the FAOSTAT-calendar history it described.
- **Every fiscal year now carries an interval, and so does every difference — and the result
  is negative.** The Monte Carlo was mature at the reference year and stopped there, so the
  panel a reader is most likely to difference was the one product with no uncertainty on it.
  Worse, the only available bound was a *level* interval, which does not apply to a *change*.
  Differencing draw by draw under three correlation scenarios — one typed from the parameter
  graph, all seventy-five dependency groups classified with reasons — **resolves one of eight
  consecutive year-on-year changes at 95 %, and that one is FY2015-16 to FY2016-17, where two
  sectors enter the record.** The full window (+131.27 Mt) is resolved under every scenario.
  The reason is published rather than argued around: 81.16 % of national variance is
  row-private residual the parameter graph attributes to no named quantity, against 7.94 % in
  parameters that persist across years. Correlation can only cancel what it can name, so
  attributing more of that residual — not collecting more years — is what would narrow a trend
  band.
- **The deposit would have republished sixty documents this project does not own.** `sources/`
  holds 3.8 GB of OGRA, NEPRA, PBS, NFDC and PCAA publications plus HIES microdata, 60 of the
  65 archived sources have no established licence, and `.zenodo.json` declared the whole tree
  open under `LICENSE-data`'s CC-BY grant. The fix is architectural: **one column was answering
  two questions**, and whether a document may be *read and derived from* is not whether it may
  be *republished*. Separated, "not established" becomes the correct answer for a government
  publication and the deposit is built so it costs nothing — 941 files, every one
  under a licence this project can grant, with `pakemis_source_register.csv` naming every
  excluded document, hashing it and saying where to obtain it.
- **The release manifest was hashing 116 of 257 source documents.** `core.manifest.
  sha256_sources` called `glob.glob` without `recursive=True`, so `**` degraded to a
  single-level `*` and 141 documents one directory deeper were silently skipped. The manifest's
  central promise is the hash of every primary source; it had been keeping it for 45 % while
  reporting no problem. Found because the new source register asked every archived document
  for its hash and most had none.
- **The clean-room rebuild ran to completion for the first time** — rc16's finding, that
  sixteen archived documents lived only on the maintainer's disk, is closed by the raw-data
  pass. It then failed on three files, and that failure was real: `product_facts` ran *before*
  `artifact_inventory` in all three build definitions and read the previous run's file,
  publishing `artifact_count=409` against an inventory holding 411. A registry that exists so
  nobody retypes a number wrong was computing it wrong from a build order nobody had declared.
  Run again, it found the same shape a second time: **the deposit manifest listed itself**,
  with its own size and digest, which is a fixpoint that cannot close — and did the same for
  the sixteen PDFs built after it and the sidecar built after those. `release_manifest.py`
  had already written down the rule that was broken and already solved it the same way. Those
  twenty rows now carry no digest and name the artefact that holds one; the artefact inventory
  stops recording a size for the same class. **With that closed the clean-room rebuild PASSES**: every product, hash, total and count reproduces byte-for-byte from a fresh clone, and the sole declared difference — `describes_commit`, which names the content commit the manifest was cut against and which the release dance then commits twice more on top of — is verified to be the only differing line rather than assumed to be.
- **Two manuscript passages contradicted the products they describe.** §12 and §8 went on
  calling agriculture's history a hybrid diagnostic series carrying a declared change of basis
  while §6 said it was a fiscal reconstruction — the same paper, opposite claims, about half
  the inventory. `DOC_CLAIMS` binds quantities and had nothing to bind a qualitative assertion
  to, so `tests/test_basis_vocabulary.py` now holds retired basis vocabulary out of the panel
  documents, permitting it only inside a supersession window.

## [1.0.0rc16] — August 2026

The eleventh review's release-integrity freeze. The defect it named was not a wrong
number but a wrong identity: every shipped PDF declared `1.0.0rc15`, commit `53f307c`
and manifest digest `706f8e90a2bcea6e` while the content behind them had moved on
through three rc16 commits — tests 1,643 to 1,664, activity files 129 to 132, the Monte
Carlo re-run, agriculture and IPPU changed. Two scientifically different releases were
claiming one immutable identity.

- **Why nothing caught it, and the guard that now does.** The manifest test compared the
  on-disk file to a fresh build, but CI regenerates the manifest *before* the tests run,
  so it compared fresh to fresh; `release_manifest.json` was also absent from CI's
  `git diff` list; the commit and digest lines are excluded from the cover's `--check` by
  design (they move on every push); and PDF-staleness only watched `sections/` inputs, so
  a regenerated cover never marked a PDF stale. Nothing anywhere asserted *the manifest
  committed at HEAD was generated from HEAD's content*. That assertion now exists.
- **The agriculture time-basis lineage, corrected against the data.** The limitations
  section claimed crop and fertiliser activity was "reconstructed on Pakistani fiscal
  statistics for every year". The engine says otherwise and always did: 238 rows
  `calendar_faostat` against 7 `fiscal_census_anchor`, and the national series marks
  agriculture `change-of-basis` in all eight pre-anchor years. The pre-anchor record is a
  hybrid diagnostic series and is now labelled one, not trend-safe.
- **Manuscript contradictions.** The agriculture supplement asserted the main text stated
  a correlation treatment it flatly denied — the sector stream samples component totals
  and cannot express those couplings, while the national parameter graph carries two of
  them, and all four sites now say so. The lognormal category table said it fed "both
  propagation methods" while its own caption said it fed only the analytic comparison.
  An obsolete "supplied out of band" reproduction caveat contradicted three statements
  that the default build needs nothing. Two `Appendix~\ref` sites rendered "Appendix
  Appendix A". The bare 448.00 headline now carries its `REF_2023_24` conditioning like
  every other instance. "Everything here is reproducible" is now the narrower and true
  claim: computationally reproducible from committed activity tables, with 39 of 132
  activity files citing documents this project read and did not keep.
- **Four findings from an audit of the generated files, not the prose.** The two
  fiscal-start sectors, power and aviation, shipped monthly files named `fy2024_25` whose
  rows were FY2023-24 throughout — a suffix rename had treated every sector as end-keyed.
  `named_share_of_var` was never a share: it is named variance over *declared* variance,
  it exceeds 1 on 37 rows, and that is the diagnostic the reconciliation columns act on,
  so it is renamed to what it measures. Two further disagreements are recorded rather than
  papered over: 81 of 190 streams carry a monthly profile that mixes temporal classes
  while the annual row reports only the modal month, and four district-unit vocabularies
  are live at once.
- **The README is a release landing page.** It now states the four products with their
  honest status — no 108-month product exists, the uncertainty layer has no year axis at
  all — plus units, the E/T/S evidence-grade definitions with their national mass shares,
  how to sum rows without double counting, the configuration policy, expected checksums,
  and the manuscripts' status as in preparation.

## [1.0.0rc15] — August 2026

- The tenth review's pre-backcast list, closed at source: the agriculture supplement's
  Monte-Carlo description (it denied a correlation the engine models and claimed
  category-level draws the engine does not make), the calendar-versus-fiscal basis
  break now a `year_basis` column and named in the prose, the MapSPAM residue, the
  IPPU 8-of-34 geocoding count, the ADM2 four-frame declaration, README product
  inventory and citation, and the recomputed stream-ledger counts.
- The conservation claim is precise: national mass is invariant across
  representations; subnational marginals may differ under documented
  physical-versus-administrative rules (875 exact / 45 declared / 30 derived).
- No bare 58.00 travels without the power family beside it — a sweep with a
  table-aware window, red at twelve sites.
- Output naming: the fiscal-start sectors' 52 outputs carry the period
  (`_fy2023_24`) via `period.file_suffix`, with the audit and the figure resolver
  taught the form first.
- **The annual product**: `pakemis_annual_fy2015_16_fy2023_24.csv` (+ parquet),
  sector × category × gas over nine fiscal years, absences as named-gap rows, and
  two views — only the harmonized common scope may be differenced. The national
  paper presents the series it already had; "publishes no national trend" is gone.
- The manifest declares its ODbL carveouts and MARS's undetermined,
  evaluation-only status; the supplement carries the four-product contract.

## [1.0.0rc14] — August 2026

- The ninth review's hotfix tier: the transport two-wheeler weight prose re-derived
  from the live engine (the printed "0.786 → 0.563" pair had no source; current basis
  is 0.8119 → 0.6100), the fire figure's in-image title derived from the fetched
  artifact's sidecar, the national interval published on both bases (−10.0/+15.7
  about the median; −9.1/+16.9 about the deterministic reference), the waste effluent
  factor's retired "±100%" cell replaced by its distribution identity.
- `outputs/national_axis_register.csv`: one row per structural axis with pricing
  status; Figure 5 draws the unpriced axis as a labelled slot; the configurations
  count prose is derived-guarded.
- The gas ledger joins OGRA Table 3.31 to the live module quantities (abort on
  same-publication drift), quantifies the ~0.9% post-meter double-claim, and prices
  its removal as the joint configuration `gas_combustion_net_of_leakage` (−0.286 Mt).
  Per-draw closure deferred and declared.
- The fugitives envelope ships as a configuration family (reference 24.694 declared
  the envelope's top); the missing all-Portland cement configuration added (+4.115);
  aviation's identified-but-unattributed fuel restated as an observed-unallocated
  account.
- The residential district map resolves through the canonical ADM2 crosswalk: 114 of
  126 polygons painted, 12 GB/AJK/ICT polygons a declared residual class, every
  disposition in a map-audit product; the crosswalk published as a release artifact.
- README gains a generated release block; review-cycle narration moved out of the
  manuscripts into this file.

## [1.0.0rc13] — August 2026 (ninth review's input; the geospatial evidence release)

- Brick kilns: the PEY Table 4.4 coal series formalized, screened at ~7.35 Mt CO2e,
  priced as the seventeenth axis, and allocated under the survey coverage mask.
- Roads: a routable OSM graph (32,136 nodes) with declared unfitted calibration,
  priced as the first information-bearing transport ADM2 alternative.
- Waste: origin-to-release objects with explicit unassigned mass (75% across 113
  districts); HydroWASTE and Climate TRACE candidate registries fetched.
- Built-form bracket gains its hybrid third member; EMC-BUILT named as the absent
  fourth. Period-matched FIRMS fires fetched (109,693 detections) and consumed by
  the cube; the firms_fire fallback class retired fail-closed.
- GEM coal and cement trackers fetched; the power asset census cross-check ships
  (8/8 NEPRA coal accounts matched; Jamshoro Unit 5 the one census finding).

## [1.0.0rc12] — August 2026 (eighth review: the "rc11.1" hotfix + the native MC)

- The national Monte Carlo consumes the waste and fugitives sector engines' persisted
  draw files (seeded, hashed) instead of lognormal surrogates; the national interval
  becomes honestly asymmetric (−10.0%/+15.7% about the median).
- Agriculture NH3 scalar generated once (0.1605/0.1675); the rail statement made
  canonical everywhere (0.39437 = 1A3c 0.38939 + non-traction 0.00498); EDGAR's
  three lineages declared and twelve citations repointed; waste seeds published.
- The residential district map's grey relabelled NO DATA (was "zero allocation").

## [1.0.0rc11] — August 2026 (seventh review: the correctness freeze)

- Wastewater effluent N2O re-priced as a bounded asymmetric draw (the ±100%
  symmetric treatment retired); the waste sector interval re-run.
- Rail re-based: strict locomotive 1A3c (0.38939 Mt) split from measured
  non-traction fuel; the aviation scope fork split into three independently
  switchable configurations; EDGAR/ODbL licensing pinned.

## [1.0.0rc8–rc10] — August 2026 (fifth and sixth reviews)

- rc10: the source-stream ledger (E = ledger × monthly × spatial weights), the
  release-height axis, the spatial class published, the gate registry and benchmark
  suite with hashed frozen splits.
- rc9: nine reviewer contradictions traced to stale prose describing a superseded
  engine; a guard dead since rc5 revived; citation metadata repaired.
- rc8: the component schema frozen; parameter uncertainty; the monthly layer; a
  rebuild that found six defects, four of them checks reporting passing while
  testing nothing.

## [1.0.0rc5–rc7] — August 2026 (fourth review and the geospatial opening)

- rc7: ADM2×month sector surfaces, kiln assets and coverage mask, OSM road density,
  the geo hash surface.
- rc6: ten contradictions fixed; the rail ledger and boundary configuration; the
  repo-URL guard.
- rc5: the transport period rebuild onto FY2023-24 (EDGAR ratio 0.85; the 0.70
  comparison superseded), the claims registry, seven named configurations.

## [1.0.0rc1–rc4] — August 2026 (first three reviews)

- rc4: all nine sectors under the release sweep; the cube in the record; the
  coverage matrix.
- rc3: nine prose defects; the uncertainty engine repaired (one resolver bug, CRN,
  ±11.21 both scopes); the dung fate ledger with priced destination variants.
- rc1/rc2: release-integrity round — three circulating national vintages (454.48,
  461, 455.14 — all historical) reconciled into one manifest-anchored figure; the
  IPCC hierarchy unified; the semantic claims registry; 100k-draw MC with standard
  errors; the release manifest and fixpoint discipline established.

## Pre-rc17 history (moved from docs/reproducibility.md at rc18)

### Since `1.0.0rc1` was first cut — the review-response rounds

- **One reporting period.** All ten sectors moved onto FY2023-24 with explicit dates. The
  national total is **448.00 Mt** (configuration L) and **442.88 Mt** (S), against 455.14 and
  450.01 before the harmonisation. This page described the mixed-year state for three rounds
  after it stopped being true, which is why it is now under test.
- **One component schema.** All 190 component rows carry an evidence class, a temporal class,
  a spatial class, a source key, an activity year and a period kind, frozen as
  `pkinv.component/v3`, which adds a derived identity - `component_id` and `sector_id` - so
  every product names a stream the same way instead of each rebuilding the key.
  Classification is per stream: transport's road rows are E3, not E2,
  because no row *is* the OCAC total.
- **Uncertainty rebuilt at the level of parameters**, which overturned a published finding.
  Sharing fuel-carbon factors across modules was reported to widen road transport from 11.96
  to 18.46 percent; at parameter level it goes 13.25 to 13.24. The old figure was an artefact
  of one correlation group per row. A Sobol attribution over 440 dependency groups finds that
  79 percent of the national variance belongs to no named parameter, and that the largest
  named parameter under the current registry is the buffalo population.
- **A monthly layer for all ten modules**, closing exactly, with the evidence for the timing
  declared separately from the evidence for the quantity. Building it audited the schema:
  34 of 184 declared temporal classes were wrong and moved, in both directions.
- **A structural scenario registry** (`REF_2023_24`, thirteen axes) and a published bridge pricing
  each single alternative, three of which move the total further than the parametric interval.
- **Coverage against EDGAR reported as three numbers rather than one ratio**, because a
  magnitude ratio nets absence in one domain against disagreement in another and reads as
  completeness when it is not.
- **The release-integrity round found four silent failures**, all of the same shape: a check
  that reported passing while testing nothing. A staleness guard reading a superseded vintage;
  a per-sector totals check that covered three sectors of nine because six files lacked the
  row it looked for; a run manifest listing a directory scrape as its own products; an
  orchestrator printing output paths that four of its phases no longer wrote.

### Against the state before there was a version

The earlier repository had no version, no tag and no manifest, so this list is what a reader
of it would need to know:

- The transport sector was re-anchored on OCAC's Road customer-class rows and its class split
  changed from distance-weighted to energy-weighted, moving road transport to 53.51 Mt and
  mixed off-road to 2.17 Mt, and reversing which class dominates on-road CO2.
- The national total moved 454.48 → 455.14 Mt (configuration L) across the transport,
  residential and waste rounds; three vintages had been in simultaneous circulation across
  the README, the national abstract and its results table, and were reconciled here.
- Residential gained its two-configuration treatment; the national layer now computes both.
- The completeness registry grew from 63 to 81 category–gas combinations.
- Power gained an air-pollutant layer, including PM2.5 from AP-42's size distribution — a
  layer two sections of that paper still described as not reported until this release.
