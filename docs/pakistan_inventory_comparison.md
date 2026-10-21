# Pakistan inventory precedents and the contribution of PakEmis

Source check: **21 October 2026**. Repository baseline: public commit `41b5636`;
the companion contribution products are additions on
`research/contribution-evidence`. This is a focused comparison of the closest
retrievable precedents, not a systematic review or a claim that no other work
exists. Publication dates, inventory years and scenario years are different
attributes throughout this note.

## What can be claimed

Pakistani studies already combine greenhouse gases and air pollutants, estimate
national and provincial emissions, use plant records, and examine mitigation
scenarios. A claim to be the first integrated inventory, first national
multi-sector synthesis, or first analysis of air–climate co-benefits would not
survive the precedents below.

The defensible contribution is more specific: **a public, evidence-linked
reconstruction in which competing activity accounts, physical transfers,
emission methods and missing coverage remain distinguishable, and their effects
on reported conclusions can be recomputed**. The gas application demonstrates
one use of that account: holding delivered services fixed while following
emissions across production, replacement supply and receiving sectors. It does
not establish that every national transition has been evaluated, nor that the
preferred account is more accurate than every comparator.

This claim is supported by the existing atomic inventories, source registers,
coverage matrices, structural cases, paired trend uncertainty and comparison
products. The new [contribution synthesis](contribution_evidence_methods.md)
connects those products to explicit conclusions. The comparison should therefore
show what a user can investigate and reproduce, with concrete disagreements,
rather than score datasets by number of files or by nominal grid resolution.

## Closest precedents and their actual scope

AP denotes air pollutants; a listed species does not imply complete coverage of
every emitting source. A finer output grid does not establish finer observed
activity.

| Work / version | Period and geography | Verified emissions capability | Evidence and access relevant to comparison |
|---|---|---|---|
| **Slater et al. (2024)** [S1] | Historical 2010–2021; scenarios 2022–2050; national and subnational | LEAP; nine AP species and CO2, CH4, N2O; 18 measures | National statistics, EMEP/EEA 2019 and IPCC factors; 116 historical power plants. Public article; model export and supplementary files not acquired in this check. |
| **Mir et al. (2022)** [S2] | 2015 baseline; scenarios to 2050; four Pakistan model regions | GAINS with EnerNEO; SO2, NOx, primary PM2.5 and CO2, CH4, N2O explicitly reported | Sector–fuel–technology activity, controls and air-quality/health modelling already combined. Published PDF acquired; named GAINS scenario uses a separate model portal. |
| **Mir et al. (2024)** [S3] | 2021 national BC inventory; scenarios to 2050 | Seven broad sectors, including sources often omitted from BC inventories | GAINS; primary abstract establishes scope. Full model inputs, grid resolution and reproducible release not established by the abstract. |
| **ICIMOD data note (2026), record v1 / revision 6** [S4] | Displayed maps: 2022; Pakistan and Bangladesh; 1 km | Verified displayed species: PM2.5 | Spatial redistribution of EDGAR v8.1 using proxies. Only the note is attached; full data available from named contacts. More species/years must not be inferred from EDGAR's full release. |
| **Urban Unit, Punjab 1990–2020** [S5] | Seven five-year snapshots, 1990–2020; Punjab | PM10, PM2.5, NOx, SO2, CO, VOC; six sectors | GAINS South Asia / Tier 1 BAU. Public report, not a verified annual 31-year numerical dataset. |
| **Urban Unit, Lahore report (2023)** [S6] | 2021-based, mixed-vintage activity; Lahore district | CO, SOx, NOx, NMVOC, TSP, PM10, PM2.5; six sectors | Tier 1 calculation with IPCC/EEA factors; report tables. Publication year 2023 is not its uniform activity year. |
| **Pakistan BTR (2024)** [S7] | FY2020–21 inventory used by the existing comparison; national | Official GHG reporting | Authoritative national reporting comparator; neither an AP inventory nor independent observation of emitted mass. |
| **EDGAR v8.1 AP** [S8] | Annual 1970–2022; monthly 2000–2022; 0.1° | Nine AP species | Public country/sector and gridded data; harmonised international inputs overlap national fuel/agricultural statistics. This named version is a comparison target, not a claim to use the latest EDGAR release. |
| **HTAP v3.2, retained September 2025 release** [S9] | Monthly 2000–2020; 0.1° | Nine AP species in release; seven used by PakEmis comparison | Regional inventories including REAS, with EDGAR gap filling/trends; public numerical downloads. Shared ancestry limits independence. |
| **PakEmis at the audit baseline** | Ten FYs, July 2015–June 2025; national, administrative and gridded allocations | Native GHG masses; seven core AP species; additional species/process products with explicit coverage | Public code and compiled input tables; restricted original documents have manifests. Annual activity evidence, monthly allocation and spatial proxies have different support. FY2025–26 extension is provisional and does not supply a common-scope national total. |

Two recent works prevent overly broad transition/synthesis claims. Mir et al.
(2026) [S10] evaluates transport AP/GHG scenarios through 2050. Rasheed et al.
(2026), published **19 October 2026**, describes a multi-sector review combining
plant information, EDGAR and TROPOMI [S11]. Only the latter's abstract and data
availability statement were accessible; its detailed calculations were not
audited. Neither paper should be dismissed as a duplicate merely from its title.

Mir et al. (2026) is a particularly informative comparator. Its full text
specifies a **tank-to-wheel** boundary: electricity-generation and fuel-refining
emissions are excluded (§4, pp19–20). It also excludes non-exhaust particles.
The authors explicitly recognise that electrification can transfer emissions
to power plants and identify wider supply-chain accounting as further work.
This supplies a concrete motivation for PakEmis's service-replacement and
cross-sector accounting. It does not establish that such accounting is novel
as a general method, or that an annual gas application resolves transport
dispatch, charging geography or upstream production.

## Household comparison: what the primary source establishes

For Slater [S1], section 3.1, Table 11 and Figure 2 establish **641 kt national
primary PM2.5 in 2021** and households at **around 35%**. Their product,
`641 × 0.35 = 224.35 kt`, is an approximate endpoint derived from rounded
statements, not an independently tabulated household measurement.

Table 3 includes **Other Biomass, 1.7 tonnes/household/year**. Its dung/residue
split and the annual fiscal/calendar convention remain unresolved. Section
2.2.1 derives household intensities from national consumption divided by
fuel-using households. Thus this endpoint cannot independently validate the same
consumption control. Reference 16 identifies EMEP/EEA **2019**, not a GAINS
factor family. Article reference 53 points to the original CCAC project report
[S12]; that report was not reacquired here, so equivalence is not assumed.

The existing `outputs/residential_ccac_bridge_2024.csv` is the correct place to
retain the comparison, with three separate statements:

1. The difference after PakEmis's explicitly assumed year alignment remains an
   **unexplained difference between models**.
2. Removing PakEmis household crop-residue combustion is a **hypothetical
   boundary sensitivity**. It is not an established correction to match the
   comparator without its fuel-level export.
3. Neither residual is a measured factor error. Fuel quantity, fuel definition,
   appliance/technology, factor vintage, particulate definition and the release
   boundary have not all been matched.

The denominator also matters. A household share of a national primary-PM2.5
inventory cannot be compared directly with a share of PakEmis's narrower
covered-source total, a district inventory, ambient PM2.5 source apportionment,
or the sum of several pollutant masses. A model-to-model mass comparison should
come before any percentage-share comparison.

## What the newly retrieved ICIMOD and local evidence adds

The actual ICIMOD DOCX was downloaded, its checksum verified, and all map panels
inspected. Figure 1 displays these **2022 PM2.5** quantities [S4]:

| Displayed sector | Pakistan (Gg/year) | Punjab (Gg/year) |
|---|---:|---:|
| Transport | 3.36 | 0.78 |
| Energy | 39.20 | 9.13 |
| Industry | 149.22 | 34.74 |
| Residential | 249.33 | 58.05 |
| Agricultural waste burning | 94.68 | 22.05 |

The five sectors are not established as a complete national denominator. Their
sum must not become a national residential share. Punjab/Pakistan ratios are
nearly identical across these displayed sectors, approximately 23.3%; the
underlying grids, masks and aggregation need inspection before these values can
serve as a spatial check. The note documents EDGAR downscaling, so it is not an
independent reconstruction of national fuel or household quantities.

The Punjab report's seven snapshots provide local historical context [S5].
Lahore Table 3 provides species-specific masses, whereas its headline transport
percentage pools pollutant masses [S6]. Those are different denominators. The
Lahore inventory also uses 2021 development/energy information and older
manufacturing inputs. These reports are useful for checking local assumptions
and category definitions; they do not directly validate a FY2023–24 national
household total.

## Use the comparison machinery already present

The repository already does substantially more than compare national totals.
The residual task is to interpret and extend the evidence, not build another
parallel comparison framework.

| Existing product / entry point | What it already establishes | What remains outside that evidence |
|---|---|---|
| `outputs/pakemis_btr_comparison.csv`; `scripts/build_btr_comparison.py` | Explicit GHG category and reporting-scope comparison | A near-matching national total can conceal offsetting category differences; the new `pakemis_btr_category_offsets.csv` exposes those offsets. Agreement does not independently verify shared activity or defaults. |
| `outputs/pakemis_air_htap_species_comparison.csv`; `src/pkinv/report/air_external_htap.py` | Seven-species process comparisons, exact July–June sums where twelve external months exist, provider/source hashes, boundary notes and implied-factor diagnostics | HTAP ends December 2020. Later FYs have no complete counterpart. REAS/EDGAR shared activity and extrapolated trends prevent independent validation; household, industry, waste and power boundaries often preclude a ratio. |
| `outputs/pakemis_air_htap_comparison.csv` | Separate NH3 sector comparison with time and boundary qualification | Sector agreement is not a test of every nitrogen stage or of actual volatilisation. |
| `outputs/national_benchmark_scope_coverage.csv`; `outputs/pakemis_industry_edgar_divergence.csv` | Coverage accounting and a named industrial disagreement | A total ratio is not percentage completeness. An external-minus-PakEmis residual is not an estimate of omitted emissions. |
| `outputs/pakemis_power_reference_audit.csv`; `outputs/pakemis_power_fuel_reconciliation.csv` | Alternative power controls and physical fuel/accounting checks | Metered fuel is valuable activity evidence but does not establish stack controls, SO2 removal or marginal generation displaced. |
| `outputs/pakemis_faostat_nitrogen_flows.csv` | Existing nitrogen-pool and factor-vintage diagnostic | Calendar/FY alignment, item-level inputs and denominator compatibility must be checked before attributing an emissions gap to one cause. A retained output snapshot is not a fresh FAOSTAT retrieval. |
| `outputs/pakemis_road_technology_case.csv` | Sensitivity of emissions to technology/factor choices at fixed fuel | Alternative European technology factors do not identify the Pakistani fleet mix. |
| `outputs/pakemis_validation_catalog.csv`; `outputs/pakemis_validation_five_classes_summary.csv` | Distinguishes calibration, shared-source checks, partially independent compilations, internal checks and declared absence | Counts are not emission-weighted coverage and are not counts of independent emissions observations. |
| `outputs/pakemis_contribution_claims.csv`; `outputs/pakemis_contribution_evidence_summary.csv` | Newly consolidated conclusions, source products and evidence needs | Invariance across a finite set of cases is conditional robustness, not a probability of correctness or exhaustive structural uncertainty. |

Useful disagreement decomposition is conditional: first align period and
included processes, then replace one activity or factor assumption at a time,
and retain the unexplained residual. Order-dependent interactions should remain
visible. It is misleading to choose assumptions merely because they move a
number toward the benchmark.

Validation should be claim-specific. A gas bill can challenge a fuel intensity;
a metered heat input can challenge an energy conversion; an independent crop or
household survey can challenge an allocation. None alone validates a whole
multi-pollutant total. Ambient measurements or satellite columns require an
appropriate transport/chemistry or plume-inversion analysis before they test
emissions; visual map agreement does not suffice.

## Minimum evidence that would materially improve the comparison

The smallest useful external acquisition is **one complete household comparator
export**, rather than a new country-wide modelling exercise. Request the
Slater/CCAC 2021 residential fuel-by-technology activity and factor table,
unrounded PM2.5 total, time convention, biomass moisture/mass basis,
other-biomass split, and particulate/release definitions.

The original CCAC report is held (`sources/Papers/ccac_sei_pakistan_assessment.pdf`) and was read
on 21 October 2026. Its household tables are transcribed as printed in
`data/sectors/residential/evidence/ccac_sei_2022_household.csv`:
- Table 5 (pp.42–43): 2021 household fuel shares and intensities by province and urban/rural;
- Table 12 (p.60): the 2010–2021 national totals;
- the data-source table (p.37): Census 2017, PSLM 2018-19 and the Compendium on Environment
  Statistics 2020;
- the factor sources (p.40): IPCC 2006 and EMEP/EEA 2019.

What it does not settle:
- "Other Biomass" is never defined beyond "wood, charcoal and other biomass".
- The intensities print "kg" per household per year where the magnitudes are tonnes.
- The year is "2021" with no calendar or fiscal convention.
- The LEAP model export is not held.

No contact has been made as part of this source check.

With those fields, the current bridge can distinguish activity, factor and
boundary contributions rather than offer only a sensitivity. If they cannot be
obtained, retain the unexplained difference and identify which missing fields
prevent attribution. That is a useful published result when traceable; a
numerically close but unsupported reconciliation is not.

For ICIMOD, the focused request is the 2022 PM2.5 raster or country/province
sector export, exact EDGAR sector mapping, proxy source/vintage, geographic
masks and mass-conservation checks. This would permit a matched spatial
comparison; it would still not supply independent national activity evidence.

For the transition contribution, finish the gas example with its material
feasibility and missing-stage limits explicit, and make the evidence-choice
comparison work across the existing national account. A second application is
valuable only if its replacement service, physical flows and decisive parameters
are supported. Adding a speculative dung or electrification case merely to
increase application count would weaken the inference. Which records need
collecting should follow from a threshold that could actually change a
conclusion.

## Manuscript-ready positioning

Pakistan has established national and subnational air-pollution and greenhouse-
gas assessments, including integrated policy scenarios [S1–S3, S10], official
reporting [S7], local inventories [S5–S6] and spatial downscaling [S4]. PakEmis
adds a public reconstruction that preserves the links between source records,
activity and material flows, emissions methods, coverage decisions and reported
results. Alternative evidence choices are retained as explicit cases rather
than absorbed into a single unexplained national estimate.

We evaluate the consequences of those choices using matched-period,
matched-process comparisons and conclusion-level sensitivity analyses.
Comparisons with other inventories are treated as diagnostics with documented
shared inputs and boundary differences, not as independent observations. A
fertilizer–power gas example demonstrates how the account can distinguish a
sectoral reduction from the emissions change after replacement services and
import pathways are included. Its result remains conditional on the represented
pathways and evidence; dispatch feasibility and unquantified stages are not
resolved by annual accounting.

For an ESSD data paper, the central case is dataset quality, traceability,
fitness for reuse and an intelligible assessment of limitations. A concise
application can establish reuse value; a large policy interpretation should not
displace the data description. The journal's [review criteria][essd-review] and
[scope][essd-scope] are the relevant standards, not an inferred acceptance
percentage.

## Sources, versions and acquisition limits

- **[S1]** Slater et al. (2024), *Modeling Air Pollutant Emission Reductions from
  Implementation of Pakistan's 2023 Clean Air Policy*, ACS ES&T Air 1(8),
  815–836, [doi:10.1021/acsestair.4c00003](https://doi.org/10.1021/acsestair.4c00003).
  Online 21 June 2024; issue 9 August 2024. Primary publisher-indexed text:
  §§2.1, 2.2.1, 3.1, Tables 3/11, Figure 2 and references 16/53. Direct
  article/PDF requests returned HTTP 403; PDF page numbers and any supplementary
  file were not verified. Publisher identifies CC BY 4.0.
- **[S2]** Mir et al. (2022), [doi:10.1016/j.envsci.2022.03.008](https://doi.org/10.1016/j.envsci.2022.03.008),
  Environmental Science & Policy 133, 31–43. Online 19 March 2022. Actual
  [author-repository PDF](https://pure.iiasa.ac.at/17904/1/1-s2.0-S1462901122000958-main.pdf)
  acquired: §§2.2.2–2.2.4, printed p33; §3.1.1 and scenario-access footnote,
  p34; uncertainty §5. CC BY-NC-ND 4.0. Supplementary material not acquired.
- **[S3]** Mir et al. (2024), *Black carbon emissions inventory and scenario
  analysis for Pakistan*, Environmental Pollution 340, 122745,
  [doi:10.1016/j.envpol.2023.122745](https://doi.org/10.1016/j.envpol.2023.122745).
  [Primary author abstract](https://pubmed.ncbi.nlm.nih.gov/37863248/) inspected;
  do not infer unavailable input/code access from abstract availability.
- **[S4]** ICIMOD, *Data note: Downscaled emission inventory for Pakistan and
  Bangladesh*, [record](https://lib.icimod.org/records/yrn7e-wmg45).
  Published 15 January 2026; updated 10 March 2026; version 1, revision 6.
  Actual attached DOCX acquired; MD5 `3264fd23d6d5d852b61009519d4916b7`.
  Methodology/contact paragraphs and Figure 1 inspected. CC BY 4.0 verified in
  record metadata. Page numbers depend on DOCX rendering; figure labels are the
  stable locator. Underlying grids not acquired.
- **[S5]** Urban Unit, [*Emission Inventory of Punjab 1990–2020*](https://urbanunit.gov.pk/Download/publications/Files/8/2023/Emission%20Inventory%20of%20Punjab%201990-2020_FD.pdf).
  Official URL's publication folder is 2023; a precise publication date was not
  verified. Scope §1.1, printed p7; methods §3.4, p22. Official PDF text
  inspected. All-rights-reserved notice; results may be referenced with
  acknowledgement. No source PDF added to the public repository.
- **[S6]** Urban Unit, [*Sectoral Emission Inventory of Lahore 2023*](https://urbanunit.gov.pk/Download/publications/Files/8/2023/Emission%20Inventory%20of%20Lahore%202023.pdf).
  Actual official PDF acquired; Table 3, printed p21, visually checked;
  conclusion §10, p31, and limitations §11, p33 establish 2021-based inputs
  and July 2022–January 2023 study work. All-rights-reserved notice; source PDF
  retained outside the repository.
- **[S7]** Government of Pakistan, [First Biennial Transparency Report (2024)](https://unfccc.int/sites/default/files/resource/Pakistan%27s%20Biennial%20Transparency%20Report%20%28BTR%29%202024.pdf),
  inventory Table 8.2. Use the source locators and category definitions retained
  in the existing BTR comparison rather than an unqualified total comparison.
- **[S8]** European Commission JRC, [EDGAR v8.1 AP release](https://edgar.jrc.ec.europa.eu/dataset_ap81).
  Version-specific scope and downloads checked 21 October 2026; release page
  notes a November 2024 SO2 shipping correction. Preserve per-file version and
  checksum when acquiring numerical data.
- **[S9]** European Commission JRC, [HTAP v3.2 release](https://edgar.jrc.ec.europa.eu/dataset_htap_v32);
  [ESSD data paper](https://doi.org/10.5194/essd-17-5915-2025).
  PakEmis records its retained September 2025 release and original workbook
  labels, including the documented v3.1 `_info` / v3.2 filename discrepancy.
- **[S10]** Mir et al. (2026), *Air Quality and Climate Co-Benefits of Pakistan's
  Transport Sector: A Multi-Pollutant Scenario Assessment*,
  [Sustainability 18(8), 3954](https://www.mdpi.com/2071-1050/18/8/3954),
  [doi:10.3390/su18083954](https://doi.org/10.3390/su18083954), published
  16 April 2026. Actual official PDF acquired, CC BY 4.0: §3.1.1, p11
  (2024 inventory and species); §4, pp19–20 (boundaries); p21 (public
  [supplementary tables S1–S9](https://www.mdpi.com/article/10.3390/su18083954/s1));
  p22 (author-request data statement). SHA-256
  `963888c1d4606ea2d940ce9827cb37c032af78b1385b47f65542cc1f31249967`.
  A public supplement is present; full scenario datasets/code must not be
  assumed open or wholly absent from the publication.
- **[S11]** Rasheed et al. (2026), *Air pollution and sectoral anthropogenic
  emissions in Pakistan: a comprehensive review*, Air Quality, Atmosphere &
  Health 19, 239, [doi:10.1007/s11869-026-02132-z](https://doi.org/10.1007/s11869-026-02132-z).
  Published 19 October 2026. Publisher abstract/data-availability text only;
  subscription full text not acquired.
- **[S12]** Slater et al., [*Integrated Assessment of Air Pollution and Climate
  Change Mitigation in Pakistan*](https://www.ccacoalition.org/policy-database/integrated-assessment-air-pollution-and-climate-change-mitigation-pakistan).
  Official CCAC record identifies year 2022 and addition date 21 February 2023.
  Landing-page indexed metadata retrieved; direct access returned HTTP 403.
  The held copy was read on 21 October 2026 (see the transcription above). It is
  the same team's work as [S1] and must not be counted as independent of it.

[essd-review]: https://www.earth-system-science-data.net/peer_review/review_criteria.html
[essd-scope]: https://www.earth-system-science-data.net/about/aims_and_scope.html
