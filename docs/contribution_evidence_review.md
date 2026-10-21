# Contribution evidence: implementation review

Prepared 21 October 2026 on `research/contribution-evidence`, based on public
`41b56365df9195d6a028a66630d0395b0d7c5de1`. This is a contribution-development
pass, not a new inventory release or a completed submission assessment.

## What this adds

The national synthesis now makes ten conclusions reproducible from their exact
source tables and records which evidence could change each conclusion. It
connects national trends, sector leadership, structural disagreements and the
gas application. Three existing benchmark comparisons have been repaired where
their explanations exceeded what their inputs could establish.

| Product | Substantive result | Interpretation limit |
|---|---|---|
| BTR category offsets | Wider-scope headline totals differ by only 1.155 Mt CO2e. Sixteen disjoint exact/aggregate crosswalk rows have +72.295 Mt and −53.956 Mt offsets, net +18.339 Mt. | Near-equal totals conceal large differences. Shared activity, aggregate boundaries and unresolved BTR methane weighting prevent an accuracy claim. |
| Managed-soils comparison | Current engine 28.493727 Mt; EF1 substitution 40.788901; EF3PRP substitution 42.776577; both 55.071751; retained FAOSTAT comparator 58.499700. | Direct-factor substitutions bridge 88.576% of this numerical gap conditionally. FY/CY, N routing, coverage and remaining methods are not harmonised. |
| Household PM2.5 bridge | Approximate CY2021 PakEmis estimate of 259.037 kt versus rounded-implied Slater endpoint 224.350 kt: unadjusted gap +34.687 kt. | Removing 67.578 kt of crop-residue emissions reverses the gap but is an unverified boundary scenario. Slater explicitly includes Other Biomass. |
| National conclusion table | GHG decade change remains positive across the eight represented parameter intervals. PM2.5 rises about 24%; SO2 falls about 42–45% across the four configurations. Residential leads covered PM2.5; the NOx leader changes. | Four configurations are a bounded sensitivity set, including a diagnostic dung allocation. Their agreement is not exhaustive structural robustness. |
| Gas application summary | Territorial CO2e falls across 56 admitted full-scope cases. Methane and all 112 combined footprint cases remain unresolved under the existing admission rules. | Repeated cells are not independent observations. Negative partial footprints cannot establish reductions when missing stages could reverse them. |

The BTR subtotal excludes the wider-scope Other Sectors row and overlapping
restatements. Its matched-category difference is 4.13%, versus 0.24% for the
wider headline totals. A uniform-28 methane sensitivity changes PakEmis only;
it is not demonstrated harmonisation of both accounts.

The nitrogen comparator is now publicly reproducible. (Follow-up, 21 October 2026: the rounded
four-row snapshot this pass introduced was replaced by FAOSTAT's own unrounded Pakistan rows,
`data/sectors/agriculture/evidence/faostat_soils_pools.csv`, written from the held extract;
that does supply the primary values and their direct/indirect split.) Current
emissions and substitutions are recomputed from the engine. The old sensitivity
table has also been regenerated. Summed livestock heads, dominated by poultry,
are no longer used to establish agreement in excreted nitrogen.

The household source is LEAP with EMEP/EEA 2019 factors, not GAINS. Its 224.35 kt
endpoint is calculated from 641 kt times an approximately 35% share. The exact
2021 year convention and biomass subcategories remain unverified. The bridge
therefore cannot select a preferred dung quantity by numerical closeness.

## Reproduce this pass efficiently

```bash
PYTHONPATH=src make contribution-figures contribution-check
PYTHONPATH=src:tests python3 -m unittest \
  test_btr_comparison test_faostat_nitrogen_flows test_residential_crt \
  test_validation_catalog test_contribution_evidence \
  test_build_definition.TestOneBuildDefinition -v
```

`contribution-evidence` uses shipped national/application panels and a small
agriculture kernel. It also rebuilds the household bridge without opening the
restricted CRT workbook. `contribution-figures` adds two SVG/PNG figures using
matplotlib. These optional targets do not alter the default build or rerun the
large spatial products. They accelerate this review task; they are not a
measured optimisation of the complete inventory build.

On this checkout, the focused build, figures and reproduction checks completed
in **2.49 seconds** using already-shipped inputs. This is a local timing for that
limited target, not a clean full-build benchmark.

The targeted suite passes **100 tests**. BTR, nitrogen and national synthesis
products pass byte-identical reproduction checks; the household bridge has
targeted numerical/source-boundary tests. Phase dependency ordering and the
public-tree check pass. Figures were visually inspected.

The whole inventory and release fixpoint were not run. The environment lacks
the unrelated `openap` dependency required by the full-build preflight. The
release manifest remains the existing release's manifest; this branch must not
be advertised as newly minted or as passing all release checks.

The residential source-extract receipt changed only its producer fingerprint:
the module fingerprint includes the edited bridge code. Extraction functions,
helpers, constants, source identity and extracted results were checked unchanged.
This is metadata maintenance, not fresh source ingestion. The official comparison
output and canonical benchmark hashes were refreshed for corrected source labels.

## What the contribution still needs

The [precedent review](pakistan_inventory_comparison.md) establishes that Pakistan
already has integrated AP/GHG studies. The contribution should be the reusable
evidence and material-flow account, the differences it exposes, and the
conclusions it permits. More code, files or scenarios alone do not establish
scientific breadth or external validity.

Priorities are ordered by what could materially change the inference:

1. **Resolve one major independent activity disagreement.** Obtain the
   Slater/CCAC household fuel-by-technology export and verify time, moisture,
   end-use and Other Biomass definitions. Decompose activity, factor and
   coverage effects only after those boundaries are known. Preserve an
   unexplained residual if they remain unknown.
2. **Add evidence to the AP assumptions that dominate the result.** Prioritise
   household fuel/appliance use and measured performance, road fleet activity
   and technology, or demonstrated plant control operation. A design standard
   or an imported default is not evidence of realised operating performance.
   Select observations using the claim table's sensitivity and evidence needs.
3. **Complete a second physically different application only after a data
   gate.** Cooking–manure is useful because it links household combustion,
   manure storage and field nitrogen. Start per unit of useful cooking heat;
   national adoption totals require reconciled household quantities and end uses.
4. **Keep ESSD's reusable data product central.** Publish versioned activity,
   flow, factor, source-choice, coverage and conclusion tables. The applications
   demonstrate reuse. Whether the process-analysis material belongs in the data
   paper or a companion paper is an editorial choice after the dataset is stable.

## Cooking–manure application: concrete admission gate

This protocol is a next work package; no cooking transition estimate was produced
in this pass. Define a functional unit of 1 GJ useful cooking heat. For each fuel,
derive consumed energy from useful heat divided by a cited appliance efficiency,
then convert to wet/dry fuel mass with explicitly matched heating values and
moisture. Compare the same cooking service and retain fuel stacking where supported.

Follow the diverted dung's carbon and nitrogen through its alternative storage,
handling and field pathways. Include responsive storage CH4 and N losses, field
N2O and NH3, and the electricity or LPG supplying replacement cooking. Do not
hold manure-management CH4 constant if the management pathway changes.

If a fertilizer substitution is claimed, preserve a defined plant-available-N
service, with timing, losses and substitution efficiency supported explicitly;
equal total nitrogen is insufficient. Otherwise report additional field N and
its emissions without granting a fertilizer credit. Preserve crop-output claims
as unresolved without agronomic support.

Use paired baseline/transition draws with common uncertain inputs, native gas
masses and separate territorial/external results. Test energy, dry matter,
carbon and nitrogen closure and show thresholds for appliance efficiency,
storage methane and displaced electricity. Declare a reduction only when the
represented boundary and missing-stage bounds support it. Do not nationally
scale a per-service result using the unresolved five-fold household quantity gap.

## Handoff for restricted material

Public analysis and implementation can continue here. The local agent is needed
for the following specific material, not as a substitute for doing the analysis:

| Needed item | What to return | Why it matters |
|---|---|---|
| Existing restricted CCAC assessment and model export, if held | Source hash, page/table, reporting-year convention, household fuel/technology activities, unrounded sector emissions, Other Biomass definition | Distinguishes a real scope mismatch from the hypothetical crop-residue removal. |
| Original FAOSTAT four-pool extract and metadata | Source version/date, unrounded values, units, item and element codes; corresponding N activities and species coverage if available | Replaces retained-output provenance and allows stronger activity/method attribution. |
| Household survey documentation and stove evidence | Variable/unit/end-use definitions; moisture/heating-value basis; source-supported efficiencies and fuel-stacking evidence | Determines whether cooking service and national quantities can be compared coherently. |
| Manure handling and field-use evidence | Storage duration, system shares, responsive CH4/N losses and agronomic substitution basis | Closes the second application's physical and service accounts. |
| Private manuscript | Apply verified results and limits; remove claims that benchmark closeness validates a dung reading or that national-total agreement proves accuracy | Prevents stale prose from contradicting the public evidence. |

Return extract tables and provenance rather than copying restricted documents
into the public repository. No outside authors were contacted in this pass.

## Figures

- `outputs/figures/pakemis_contribution_btr_offsets.png` and `pakemis_contribution_btr_offsets.svg`:
  the BTR category offsets behind the near-equal national totals.
- `outputs/figures/pakemis_contribution_nitrogen_attribution.png` and
  `pakemis_contribution_nitrogen_attribution.svg`: the conditional EF1 and EF3PRP substitutions
  against the FAOSTAT comparator.
