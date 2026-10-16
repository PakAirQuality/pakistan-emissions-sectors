# The national paper as an ESSD data-description article — outline and claim map

**Target**: *Earth System Science Data*, regular data-description article (not a Living Data
paper, not a methods paper). **Title**: *PakEmis v1.0: an evidence-graded public-data
reconstruction of Pakistan's non-LULUCF greenhouse-gas emissions, FY2015–16 to FY2023–24*.
**Object described**: the frozen PakEmis release identified by `outputs/release_manifest.json`
and the semantic contract `outputs/semantic/semantic_release.json`; the manuscript's tables and
figures are stored queries against that release (`paper_national/queries/paper_artefacts.csv`),
never typed by hand, and its headline claims are the rows of `data/claim_matrix.csv`.

## Vocabulary the manuscript uses, and avoids

Use: public-data reconstruction · monthly estimate · spatial allocation · evidence-graded
product · reference configuration · estimated / NE / NO / IE · proxy-distributed or
point-allocated. Avoid: official national inventory · definitive or complete inventory ·
observed gridded emissions · true national emissions · live emissions system · AI-derived
inventory. `tests/paper_numbers/test_essd_structure.py` holds both lists.

## Structure (numbered sections; Copernicus one-column `manuscript` layout with line numbers)

| § | ESSD section | Existing fragments that move here (file-preserving) | Stored artefacts |
|---|---|---|---|
| — | Abstract (≤ 250 words; the dataset DOI enters at publication via `generated/abstract_doi.tex`) | `00_abstract.tex` rewritten | — |
| 1 | Introduction: the community need and the inventory-data gap; why PakEmis is unique and reusable; the four product layers in one paragraph | `01_introduction.tex` (absorbs the surviving paragraphs of `02_related_work.tex`) | Fig. 1 architecture (static, source-hashed) |
| 2 | Dataset scope and architecture: system boundary, fiscal years, gases, GWPs (AR5 reported, AR6 secondary), configurations L/S and the structural registry; estimated vs NE/NO/IE; the atomic schema and mass conservation | `20_scope.tex` (new) + `03_architecture.tex` (trimmed) + the notation-key part of `09_completeness.tex` | Tab. completeness (stored) |
| 3 | Source data and processing: source hierarchy, transcription, transformations, custody and redistribution terms | `30_sources.tex` (new) + `14c_sources.tex` (split from the appendix) | Tab. source register summary (stored) |
| 4 | Dataset generation: 4.1 annual reconstruction · 4.2 monthly disaggregation · 4.3 spatial allocation · 4.4 uncertainty and structural configurations | `40_generation.tex` (new) + `06_results.tex` (product description only) + `14b_months_geography.tex` + `07_uncertainty.tex` (compressed) + `04_closures.tex` (ledgers) | Fig. 2 trend, Fig. 3 composition, Fig. 4 108-month product and temporal evidence, Fig. 5 spatial allocation beside the evidence/fallback map, Fig. 6 parametric uncertainty and structural configurations; Tab. sectors, Tab. category×gas, Tab. temporal, Tab. spatial, Tab. dung variants |
| 5 | Data records: every released CSV, Parquet, spatial file and registry — dimensions, keys, units, coverage, intended use, relationships (a central section) | `50_data_records.tex` (new) + `generated_products.tex` + `generated_coverage.tex` promoted from the supplement | Tab. data records per family (stored from the product catalogue, schemas and columns) |
| 6 | Technical validation: annual/category/gas closure; annual→monthly closure; national→spatial+unallocated closure; cross-sector ledgers; external comparisons and plausibility; evidence-quality variation and proxy regions | `60_validation.tex` (new) + `04_closures.tex` + `10_benchmarks.tex` + the variance/evidence paragraphs of `07_uncertainty.tex`; `08_key_categories.tex` summarised, full text to Supplement S2 | Tab. benchmarks, Tab. correlation; Fig. 7 completeness/validation summary only if it adds beyond the tables |
| 7 | Usage notes and limitations: what can be inferred at national, monthly, administrative and grid scales; what must not be read as observed facility emissions; completeness, temporal and spatial limitations | `12_limitations.tex` (labelled `lim:` paragraphs) + the implications paragraphs of `11_discussion.tex` | — |
| 8 | Data availability (repository review link or DOI when available, citation, CC BY primary package, separately licensed ODbL companion, non-redistributed source documents) | maintained v3 article and release manifest | — |
| 9 | Code availability (software DOI, repository, the validation package and reproduce entry points) | same generator | — |
| 10 | Conclusions | `13_conclusion.tex` rewritten | — |
| S | Supplement (article class): S1 air-pollutant beta · S2 key categories · S3 the parallel-table rule · S4 reproduction detail · S5 the claim matrix | `supplement.tex`, `05_factor_tables.tex`, `08_key_categories.tex`, `14_appendix.tex`, `generated/claim_matrix.tex` | — |

Sector manuscripts become **PakEmis Sector Technical Notes TN01–TN10** (TN01 agriculture,
TN02 power, TN03 transport, TN04 waste, TN05 residential, TN06 fugitives, TN07 IPPU,
TN08 industry — reserved, written after the Explorer shell — TN09 railways, TN10 aviation),
deposited with the data under the documentation DOI; they do not repeat the national headline
totals (`data/claims_registry.csv`, `exclusive` rows).

## The claim matrix

`data/claim_matrix.csv` lists every headline claim: the sentence, its section and fragment, the
quantities it prints (`claim:` / `fact:` / `registry:` / `table:` references into the existing
claims machinery), the source product and pointer, the stored query id and parameters, the
configuration, unit and rounding, the evidence class (closure-exact, estimated-TE1..TE4,
spatial-S1..S4, parametric, structural, external-comparison, coverage-count,
provenance-count), the limitation paragraph it is bounded by, the technical notes it rests on,
and the figure or table that shows it. A claim is headline when it is stated in the abstract,
introduction or conclusions; when it leads a limitation paragraph; when it is a product fact
printed in the body; when it is a `claims_registry` row allowed for the national paper; or when
it is what a main figure or table shows. `scripts/make_claim_matrix.py` resolves every row
against the release and renders `outputs/pakemis_claim_matrix.csv`, the Markdown view and
Supplement S5; `tests/paper_numbers/test_claim_matrix.py` holds the printed value to the resolved
one and the matrix to the headline rule in both directions.

## Submission requirements carried by the build

Copernicus `manuscript` option (one column, line numbers); figures near first mention, ≥ 8 cm,
CVD-safe, one file each; map figures with provider credits in the figure and boundaries under
UN naming with the disputed line marked; a 500-character non-technical summary
(`paper_national/short_summary.txt`, number-free); formal Data and Code availability sections
generated from the manifest; the dataset citation in the reference list; the three persistent
identifiers (data, software, documentation) reserved before the release is minted and printed
only from the manifest.
