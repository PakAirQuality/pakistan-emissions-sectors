# Contribution evidence: what the restricted layers returned

Written 21 October 2026 in answer to the "Handoff for restricted material" table in
`docs/contribution_evidence_review.md`. Extract tables and their provenance are returned; the
documents stay in the restricted layer.

Every document read was searched for with `scripts/holdings.py` first. A new document was kept
through `pkinv.core.retention` before it was read. Every acquisition attempt, hit or miss, has a row in
`data/raw/ACQUISITION_LOG_cooking_manure_20261021.csv`, written by
`scripts/fetch_cooking_manure_evidence.py`.

No outside author or agency was contacted. No national total moves: none of the tables below is read
by an inventory engine.

## Summary

| Handoff item | Returned | Not returned, and why |
|---|---|---|
| CCAC assessment and model export | The household tables of the held 2022 report, transcribed with pages (`ccac_sei_2022_household.csv`, in `8b2050d`). | The LEAP model export: not public. The ACS article PDF returned 403. |
| FAOSTAT four-pool extract | The unrounded pools (`faostat_soils_pools.csv`, in `8b2050d`), and now the manure-nitrogen activities by species (`faostat_manure_nitrogen.csv`). | None. |
| Household survey and stove evidence | The HIES 2024-25 dung-cake definitions (`hies_dung_definitions.csv`), the World Bank survey's stove shares and stacking, and two laboratory efficiency studies (`cookstove_efficiency_evidence.csv`). | Any efficiency measured in Pakistan, or for dung cake: none exists in any source found. |
| Manure handling and field use | FAOSTAT's own manure pools by species. | Storage duration, system shares and agronomic substitution: no Pakistani source found. The source of `mms_shares.csv` burned_fuel was not found. |
| Private manuscript | Edited on a private branch, held for the next mint. | Not applicable. |

## The CCAC/SEI household assessment

Returned in `8b2050d` as `data/sectors/residential/evidence/ccac_sei_2022_household.csv`, from the held
report `sources/Papers/ccac_sei_pakistan_assessment.pdf` (sha256 3694359f…):
- Table 5 (pp.42-43): 2021 household characteristics;
- Table 12 (p.60): national totals in kt;
- the statements on pp.37, 40 and 59 that the comparison depends on.

The year convention is 2021. "Other Biomass" is defined no further than "solid fuels (wood, charcoal
and other biomass, coal)" (p.40), so its dung and crop-residue composition is not stated.

**Not returned: the LEAP model export.** Three routes were tried on 2026-10-21:
- SEI's publication page, now kept as `data/raw/literature/sei_2024_publication_page_pakistan_clean_air_policy.html`,
  links only the article's DOI;
- the ACS article PDF returned 403;
- web searches found CCAC project pages describing the LEAP-IBC assessment, but no data file.

Whether the article's supporting information carries household activities is therefore unknown. The
attempts are logged.

## FAOSTAT

**The four-pool extract.** Returned in `8b2050d` as
`data/sectors/agriculture/evidence/faostat_soils_pools.csv` (1,235 rows):
- items 5061-5064, every element, year, unit and flag, unrounded;
- written by `scripts/ingest_faostat_soils_pools.py` from the held Emissions Totals extract, retrieved
  2026-06-30.

**The manure-nitrogen activities behind it.** New in this commit:
`data/sectors/agriculture/evidence/faostat_manure_nitrogen.csv`.
- Content: 1,701 rows, Pakistan, 2015-2023. Head counts (flag A or I) and nitrogen excreted, treated,
  lost, applied to soils, left on pasture, volatilised and leached (flag E), for 19 species and
  aggregate items.
- Source: written by `scripts/ingest_faostat_manure_nitrogen.py` from FAOSTAT's Livestock Manure bulk,
  kept 2026-10-21 (sha256 026c3cc2…, CC BY 4.0).

What the rows show:
- **Applied N is treated N less losses**, item by item and year by year. `tests/test_returned_contribution_evidence.py`
  holds the extract to that identity.
- **FAOSTAT's pools do not cover all excreted N.** Excreted N less treated N less pasture N is
  14.2-14.5% of national excretion in every year. That share is N that FAOSTAT assigns to neither pool.
- **The unassigned share sits in two species.** In 2023 it is 0.261 for cattle and 0.275 for buffalo;
  for sheep, goats, camels and equines it is zero.
- **Corrected 22 October: the remainder is not the inventory's burned-fuel share.** This note first said
  the two shares "lie close to" the burned-fuel shares in `mms_shares.csv` (cattle 0.28, buffalo 0.30), and
  that both might come from one IPCC default. FAOSTAT's methodological note, kept the next day, says what
  the remainder is (see "Second brief" below):
  - FAOSTAT books half the N in manure burned for fuel as pasture N, the urine, and the other half in
    neither pool;
  - its burned-for-fuel shares are the IPCC 2006 Indian-subcontinent defaults: 51, 53 and 55% of
    excreted N for dairy cows, other cattle and buffalo.

  The inventory books 28 and 30%, so the default share is nearly twice the inventory's. The closeness
  compared half of one quantity with the whole of another, and it does not supply the missing citation.

## HIES 2024-25: how dung cake is recorded

`data/sectors/residential/evidence/hies/hies_dung_definitions.csv` has 18 rows, from two held
documents:
- the household questionnaire, `sources/HIES/Male-Questionnaire-HIES-2024-25-English.pdf`;
- the Manual of Instruction, `sources/HIES/Manual-of-Instruction-HIES-2024-25.pdf`.

**The quantity item.** Section 6-M Part C records "Dung cake (dry)" as item 045404, in kg (questionnaire
p.17).
- **Recall:** the last month. The manual defines this as the preceding 30 days (p.91).
- **Annualisation:** the manual multiplies Part C totals by 12 (p.143).
- **Four routes:**
  - paid and consumed;
  - wages in kind;
  - own produced;
  - gifts, assistance and other sources.

  `scripts/ingest_hies.py` sums these four routes (q1-q4) and multiplies by 12, which matches what the
  documents print.
- **Exclusion:** business consumption is excluded.
- **Heading:** the item sits under COICOP 04.5.4 Solid fuels (manual p.102), whose heading text does not
  name dung.

**The main-fuel questions** carry Dung cake as code 6 for cooking and code 9 for heating
(questionnaire p.11, manual p.70). This is one main fuel per household.

**The agriculture sheet** records the rupee value of dung cakes produced for home use or sale, code 172
(questionnaire p.27, manual p.133). This is a value, not a quantity.

What the documents do not say:
- **No end-use split.** The 045404 quantity is not split into cooking and heating.
- **No physical basis.** Neither document gives a dung cake's moisture, mass or heating value beyond
  the word "dry".

The inventory's air-dry moisture (`dung_cake_moisture_ar`, 0.12) and heating values are its own
literature-range parameters in `data/sectors/residential/parameters/residential_params.csv`. They are
not survey facts.

## Stove efficiency and fuel stacking

`data/sectors/residential/evidence/cookstove_efficiency_evidence.csv` has 16 rows.

**World Bank ESMAP (2024) Pakistan Energy Survey** (held; fieldwork 2022):
- **Main stove** (p.55, Figure 70), as shares of households:
  - three-stone fires and traditional or locally built stoves, together: 55.7% (rural 71.8%);
  - piped-gas stoves: 38.6%;
  - LPG stoves: 5.7%;
  - manufactured biomass stoves: none.
- **Stacking** (p.57): 93.8% of households use one stove; 6.2% stack stoves.
  - Nearly 60% of stacking households keep LPG as the backup stove (Figure 73 prints 58.9%).
  - 81.5% of LPG stackers rarely use it, because the fuel is too expensive.
- **Efficiency:** the survey "did not collect data to analyze the efficiency attribute" (p.10).

**Two laboratory studies,** kept 2026-10-21 because the survey prints no efficiency:
- **Jetter et al. (2012)**, US EPA, Water Boiling Test (WBT) Version 4: twenty-two cookstoves on six
  fuels (wood, charcoal, pellets, corn cobs, rice hulls, plant oil).
  - Three-stone fire: about 14-15% overall thermal efficiency.
  - Best stove tested: 53%.
- **Shen et al. (2017)**, US EPA, WBT 4.2.3, thermal efficiency:
  - LPG: about 57%;
  - kerosene: about 42%;
  - forced-draft wood stove: 31%;
  - natural-draft wood stove: 25%.

**The gap this records.** No source found measures a Pakistani chulha, and none tests dung cake. The
two studies are US laboratory results on other fuels. Under the admission gate, a cooking-service
comparison would have to borrow a wood-fire efficiency for dung and say so; this table does not make
that substitution.

The acquisition notes written on 2026-10-21 got two details wrong. They describe Jetter as "22
stove-fuel combinations" under "WBT 4.1.2", and Shen under "WBT 4.2". The table, the corrected
fetcher and this note follow the papers. The log rows are left as written, because the log is
append-only.

## Manure handling and field use

The evidence returned is FAOSTAT's own pools by species, from `faostat_manure_nitrogen.csv` above.
These are Tier 1 estimates, not observations.

**Not found:**
- **The source of the burned-fuel shares.** `mms_shares.csv` points to an "MDPI Sustainability 2021"
  dung-cake study, but names no author, title or volume, and searches found no matching paper. The
  shares stay unsourced, under data gap `mms-distribution`.
- **Pakistani storage evidence:** neither storage durations nor management-system shares were found
  in a public Pakistani source.
- **The agronomic substitution basis:** no evidence was found for timing, plant-available N or
  substitution efficiency.

The admission gate's manure leg therefore stays closed: a transition estimate would rest on IPCC
defaults for the very shares it changes.

## The papers that could not be fetched

Both are logged as failed:
- **Slater et al. (2024), ACS ES&T Air 1(8) 815-836**, the peer-reviewed version of the CCAC/SEI
  assessment. `pubs.acs.org` returned 403.
- **Mir et al. (2026), Sustainability 18(8) 3954**, cited by `docs/pakistan_inventory_comparison.md`
  [S10]. `mdpi.com` returned 403.

## How the transcriptions are checked

`tests/test_returned_contribution_evidence.py` makes the checks below.
- **The quotes are on the cited pages.** Every row of the two transcribed tables carries a short quote
  from its document. With the restricted layers mounted, the test looks for each quote on the cited
  page of the held bytes. It also checks that a quote put on the wrong page is caught.
- **The FAOSTAT extract re-derives.** The FAOSTAT manure extract must re-derive from the held bulk.
- **Without the layers**, both tables are checked for shape. The FAOSTAT extract is also held to
  FAOSTAT's own identities.

## Second brief, 22 October 2026

A follow-up brief said most of the missing evidence is public, and named where to find it. The new
attempts are logged in `data/raw/ACQUISITION_LOG_contribution_followup_20261022.csv`, written by
`scripts/fetch_contribution_followup_evidence.py`. That fetcher takes an address only from bytes it kept
first, or from a web search named in the note. The five FAOSTAT addresses it tried by pattern (the EMN
note and the four CSVs beside it) are marked as such.

**FAOSTAT's manure assumptions: the burned-for-fuel question is answered.**
- **The source.** FAOSTAT's Livestock Manure methodological note (`EMN_e.pdf`, 5 pp., created 2025-10-08)
  and its Emissions from Livestock note (`GLE_e.pdf`) say that cattle and buffalo shares come from IPCC
  2006 Vol.4 Annex 10A.2, Tables 10A-4 to 10A-9. The note counts half of the burned-for-fuel N as pasture.
- **The transcription.** The Indian-subcontinent rows of Tables 10A-4/5/6 (pp.10.77-10.79 of the held
  chapter) are in `data/sectors/agriculture/evidence/ipcc2006_indian_subcontinent_mms.csv`.
- **The test.** `tests/test_returned_contribution_evidence.py` rebuilds FAOSTAT's Pakistan pasture and
  treated shares from those rows, for every year 2015-2023, within the table's printed rounding:
  - dairy: pasture 52.5%, treated 21%;
  - other cattle: 48.5% and 26%;
  - buffalo: 46.5% and 26%.
- **What it shows.** FAOSTAT's implied burned-for-fuel share for Pakistan is 51-55% of cattle and buffalo
  N. The inventory's unsourced `mms_shares.csv` books 28-30%. Both are assumptions; neither is an
  observation.
- **Not obtained:** the four "Related Documents" CSVs the note names (`TAM_Country`, `N_ExcrRate_Country`,
  `Share_MMS_Lvstck_Country`, `FracLoss_MMS_Lvstck_Country`).
  - FAOSTAT's documents API returned 401 on one host and 521 on the other.
  - The four addresses beside the note returned 403.
  - The cattle and buffalo shares are settled without them. For other species, and to confirm that
    FAOSTAT assigns Pakistan to the Indian subcontinent, they would still help.

**FAOSTAT versions and activities.**
- **The catalogue.** FAOSTAT's bulk-download catalogue (`datasets_E.json`) is kept. Every held bulk is
  joined to its catalogue entry in `data/sectors/agriculture/evidence/faostat_versions.csv`
  (`scripts/ingest_faostat_versions.py`).
- **Two differences:**
  - **RFN predates the current release.** The held Fertilizers by Nutrient bulk was retrieved
    2026-06-30, but the catalogue's RFN update is dated 2026-07-30 and its printed size differs. The
    synthetic-N rows behind the soils comparison may since have been revised.
  - **GCE does not match the catalogue.** The Emissions from Crops bulk fetched on 2026-10-22 does not
    match the catalogue's printed size (6,690 against 7,436 KB). The catalogue entry may be stale; that
    is not established.
- **New bulks.**
  - GCE and GLE are now held.
  - GCE's Pakistan rows for 2015-2023 are published unrounded in
    `data/sectors/agriculture/evidence/faostat_crops_nitrogen.csv` (598 rows): synthetic-N applied,
    crop-residue N, harvested area, and their N2O and CH4. FAOSTAT's 2030 and 2050 projections are
    left out.
  - GCE's 2023 synthetic-N (3,808,775 t) equals the held RFN figure.
- **No fertilizer-year note.** The held RFN bulk carries no note on fertilizer years for Pakistan
  (2012-2023 notes: "Official data from questionnaire"; 2018 imputed). FAOSTAT's country-notes document
  sits behind the same documents API.

**The HIES correction is already in the held microdata.** PBS's HIES page (kept) says Section 6 was
re-uploaded "due to a technical glitch that caused some duplicate and missing values", corrected
16-01-2026, with no impact on the tables or results.
- The held `sources/HIES/SPSS-data-2.zip` was retrieved on 2026-08-09.
- Its `Sec 6a-consum-Exp.sav` is dated 2026-03-18.
- The live file at the same address reports the same size, 46,095,824 bytes, last modified 2026-03-18.

The held archive therefore postdates the correction, and the dung-cake ingest already reads the
corrected file. It was not downloaded again, because a byte-identical second copy would be a new
cross-tree duplicate.

**Stoves.**
- **Aneeq & Mahmood (2022)** is now held as its open-access PDF (CC BY 4.0). It is the first Pakistani
  efficiency measurement: one improved two-burner mud stove with chimney, built in Khipro, Sindh, tested
  on wood (about 10% moisture). The test ran the cold-start high-power phase only and measured about 30%
  (printed pages 1, 5 and 6, now in `cookstove_efficiency_evidence.csv`). It is one stove on wood: not a
  national figure, and not dung.
- **Usman et al. (2023)** is paywalled; only its landing page is held. The abstract reports the relative
  gains after loading-height optimisation for two common Pakistani LPG stoves (+20% and +13% in the
  high-power phase), not their absolute efficiencies.
- **Clean Cooking Catalog:** not searched in this pass. Product test results do not establish what
  Pakistani households use.

**Manure handling.**
- **Ali et al. (2019)**, a buffalo-manure storage experiment in Pakistan: its ICRISAT record returned 403
  to the fetcher, and the article is paywalled. The N-loss figures a web search reported for it are not
  transcribed, because no held bytes print them.
- **Zuhra et al. (2025):** an OpenAlex search and a web search found no title or DOI.

Both are logged.

**Slater et al. (2024)** is open access (CC BY, per OpenAlex), but every automated route returned 403 or
found nothing:
- the ACS PDF and full-text HTML;
- Europe PMC (no record);
- OpenAlex lists no repository copy.

A browser download by the user, or with their permission, is the remaining route to Table 3.

**The author request.** Asking the corresponding author for the CCAC/SEI residential export is for the
user to do. This repository contacts no one.

