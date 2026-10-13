"""Build research_campaign/missing_sources/coverage_matrix.csv.

READ-ONLY on the repository. The mechanical columns (ipcc_code, category, gas,
notation_key) are read from outputs/completeness.csv - the EXECUTABLE inventory -
so they cannot drift from it; the script FAILS if a non-E row of that file has no
judgement here, which is the guard against the matrix going stale when the
inventory moves. The judgement columns are this worker's, sourced per row.

TWO VOCABULARIES, CARRIED SIDE BY SIDE AND NEVER MERGED.

  notation_key    the inventory's own IPCC/UNFCCC reporting key, answering
                  "what does the national account say about this cell?"
                  E / NE / IE / NO / NA, read from the file.

  campaign_status this worker's judgement, answering ONE different question:
                  "what grade of treatment is supportable TODAY from data held
                  in this repository or openly available?"

                    SUPPORTED          a source-supported quantitative treatment
                                       exists now or could be produced now from
                                       held/open data (an evidenced NO, NA or IE
                                       counts: the treatment is supported)
                    CONDITIONAL        producible, but conditional on a declared
                                       configuration choice, a boundary decision
                                       or a reconciliation not yet made
                    SCREENING          only a bound or a screen is supportable;
                                       no emissions estimate is
                    UNESTIMATED/BLOCKED no supported path; a named input is
                                       missing or access-controlled

A cell can be NE in the inventory and SUPPORTED here (the estimate is feasible,
the inventory has simply not activated it) or IE in the inventory and CONDITIONAL
here (the mass is counted, in a category that misstates it). Reading one column
off the other is the error this layout exists to prevent.

MAGNITUDE DISCIPLINE. plausible_magnitude_range is populated ONLY where a cited
source supports it, and magnitude_basis names that source every time. Units are
written into the cell, never implied. "unknown" is a legitimate and common value.
No completeness percentage is computed anywhere: the denominator - the true size
of what is missing - is exactly what is unknown, so a percentage would be a
measured-looking statement about an unmeasured quantity.

EXTERNAL INVENTORIES ARE SCOPE SCREENING, NOT TRUTH. EDGAR and the Pakistan
BTR/CRT magnitudes recorded here bound the scope question. They are never values
to paste into this inventory: EDGAR is an external model and the BTR is a
different national account with its own vintage (inventory year 2021), its own
methods and, in places, a flat contradiction of PakEmis (BTR books 4.C.2 open
burning at 0.20 Mt where PakEmis estimates 3.83 Mt).

Run:  python3 research_campaign/missing_sources/build_coverage_matrix.py
"""
import csv
import os

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
COMPLETENESS = os.path.join(REPO, "outputs", "completeness.csv")
OUT = os.path.join(REPO, "research_campaign", "missing_sources", "coverage_matrix.csv")

COLUMNS = ["ipcc_code", "category", "gas", "notation_key", "campaign_status",
           "plausible_magnitude_range", "magnitude_basis", "open_data_strength",
           "overlap_risk", "work_needed", "blocking_input", "notes"]

# Judgements keyed by (code, category) from outputs/completeness.csv.
# Fields: status, magnitude, magnitude_basis, open_data, overlap, work, blocker, notes
J = {
("3.D", "Agricultural soils - N from SOC mineralisation (FSOM)"): (
 "UNESTIMATED/BLOCKED", "unknown",
 "no source supports a range; IPCC Tier 1 sets FSOM to zero by construction, which is a method convention and not a measurement",
 "none",
 "would overlap the LULUCF cropland/grassland SOC rows below: the same soil carbon-and-nitrogen response cannot be booked once as 3.D N2O and again as a LULUCF stock change without an explicit split",
 "a national land-use and management-change time series at Tier 2 resolution",
 "Tier 2 land-use/management-change activity data for Pakistan, which the gap register records as not existing at the required resolution",
 "claim_class no-data-exists. Distinct from the categories below where the statistic exists and has not been fetched."),
("3.E", "Prescribed burning of savannas"): (
 "SUPPORTED", "nil", "occurrence: no managed savanna burning in Pakistani agriculture (inventory justification)",
 "strong",
 "THE LAND-LANE PRECEDENT APPLIES HERE. Pakistan's own CRT reports land biomass-burning non-CO2 in the AGRICULTURE block (3.E fires, 3.F crop residue) while its BTR folds the same mass into the land block - the same emission in two places in one official account. PakEmis's 3.E NO and its separate crop-residue and land rows must be read against that, or a future land-fire addition will double count.",
 "none; the NO is evidenced",
 "none",
 "A documented non-occurrence, not an omission. Retained in the matrix because its overlap risk is live for any future land-fire component."),
("3.G", "Liming"): (
 "UNESTIMATED/BLOCKED", "unknown",
 "believed near-nil on alkaline/calcareous cropland but NO national lime-application statistic has been sought, so no range is supported; the inventory deliberately withdrew an earlier 0.000000 Gg row because a zero asserts a measurement",
 "weak",
 "lime applied to soils (3.G) must not be confused with lime PRODUCED (2.A.2, also NE here) or with limestone quarried; the three are different masses and 2.A.2's own note says limestone mined cannot substitute for lime produced",
 "obtain national limestone/dolomite application to agricultural soils; Eq 11.12 and IPCC Table 11.2 factors are already held",
 "national agricultural lime-application statistic (Ministry of National Food Security / provincial agriculture departments, by request)",
 "The method side is complete; only the activity statistic is missing. NE rather than NO because absence of the activity has not been demonstrated."),
("3.I", "Other carbon-containing fertilisers"): (
 "CONDITIONAL", "unknown",
 "the urea bridge (outputs/ippu_urea_co2_bridge_2025.csv) reports a residual of 233 kt urea FY2023-24 and 890 kt FY2024-25 as stocks and industrial use, but that is a urea mass not a 3.I CO2 estimate, and no source apportions it to 3.I",
 "strong",
 "HIGH. The same urea carbon appears at 2.B.1 (ammonia, recovery term), 3.H (urea application) and 3.I. The bridge is the accounting frame that keeps them apart; any 3.I activation must enter through it.",
 "decide the 3.I/2.B.1/3.H boundary inside the existing urea bridge; the activity (fertiliser N) is already held in this repository",
 "none external - this is a reconciliation, not an acquisition",
 "Two open items noted in the gap register: 3.H derives urea as N x 0.80/0.46 = 6,565,217 t instead of reading the observed 6,579,000 t offtake in the same file (0.2 percent apart), and the 0.80 urea_N_share provenance is open."),
("3.J", "Other (agriculture)"): (
 "SUPPORTED", "nil", "residual category; no other agriculture source identified (inventory justification)",
 "moderate", "none - a residual bucket, by construction empty once the named categories are enumerated",
 "none", "none",
 "A NO on a residual category is weaker evidence than a NO on a named source: it asserts that enumeration was complete. Recorded as supported because the enumeration is published and auditable, not because an occurrence survey was run."),
("(x-sector)", "Dung-cake combustion (N and C)"): (
 "SUPPORTED", "nil (transfer, not a new mass)",
 "a closed transfer: 28 percent of cattle and 30 percent of buffalo excreted N leaves Manure Management and is received by 1.A.4.b, tested with exact equality in both directions",
 "strong",
 "THIS IS THE MODEL OF A HANDLED OVERLAP. The nitrogen leaves one category and enters another, and a test asserts the equality. Any new component in this matrix should be required to close the same way.",
 "none", "none",
 "Included as a positive control: it shows what IE should look like when the transfer is actually closed."),
("1.A.4.a", "Commercial and institutional combustion"): (
 "SCREENING", "2.4 Mt CO2e floor (two streams); 3.8 Mt filed by Pakistan's own BUR-1; 36.80 Mt is the BTR 2021 whole of 1.A.4",
 "outputs/commercial_institutional_audit_2024.csv (OGRA commercial gas 45 MMCFD + chart-read commercial LPG ~520 kt); Pakistan BUR-1 commercial filing 3.8 Mt; Pakistan BTR1 2024 Table 3 line 1.A.4 = 36.80 Mt CO2e for inventory year 2021 (all of Other Sectors, residential dominant)",
 "moderate",
 "HIGH AND ALREADY REALISED ONCE. The commercial gas stream sits in this repository counted ONLY as post-meter leakage (1.B.2) and never as combustion; activating 1.A.4.a on the same gas without removing it from the leakage term would double count it. The LPG figure is chart-read, so it is also at risk of overlapping OCAC's held LPG classes.",
 "resolve the commercial share of retail petroleum, then activate with an explicit deduction from the post-meter leakage term",
 "HDIP commercial energy balance (paid). The commercial share of retail petroleum is unresolvable within OCAC's held customer classes.",
 "The register's one silent omission until the August 2026 audit: no NE row and no EDGAR map code existed for this category at all. Material (floor above the 1 Mt line) and screened; stays NE because the reference-year totals are frozen through the release-candidate series."),
("1.A.4.b", "Residential - biogenic CO2 (dung cake, firewood, residues, charcoal)"): (
 "SUPPORTED", "0.175 Mt CO2 is what Pakistan's BTR1 books as its biomass memo item for 2021",
 "Pakistan BTR1 2024 Table 3, 'CO2 emissions from biomass' memo line = 0.175 Mt. PakEmis reports its own biogenic stream as a memo item outside the total; the two memo figures are not compared here and differ by orders of magnitude (PakEmis's cake stream alone is 58.7 Mt of fuel).",
 "strong",
 "the convention itself IS the overlap control: biogenic combustion CO2 is a memo item and any net stock loss belongs in LULUCF. Counting it in both places is the classic double count.",
 "none for the GHG total; a cross-check of PakEmis's memo against the BTR's 0.175 Mt would be informative and is not attempted here",
 "none",
 "IE by IPCC's biomass convention and Pakistan's own BUR-1. The BTR comparison is logged because a 0.175 Mt national biomass memo against a 58.7 Mt cake fuel stream is a disagreement someone should explain; it is NOT evidence against PakEmis."),
("1.A.4.b", "Residential - electricity"): (
 "SUPPORTED", "nil (counted at 1.A.1.a)",
 "boundary convention; a test asserts no residential electricity stream exists",
 "strong",
 "the row exists PRECISELY to prevent the double count. Household electricity is near half of national consumption; counting it at the meter as well as at the station would be the single largest possible error in the inventory.",
 "none", "none",
 "A deliberate absence with a test behind it."),
("1.A.4.b", "Residential - biogas digesters"): (
 "UNESTIMATED/BLOCKED", "unknown",
 "no source supports a range: no national operating count or gas-production statistic located, and HIES 2024-25 carries no biogas consumption item",
 "weak",
 "MODERATE AND TWO-SIDED. Dung diverted to a digester must leave Manure Management exactly as cake dung does (the closed transfer above); activating digesters without that deduction would count the same dung twice.",
 "obtain a national digester count and gas production, then write both the leakage CH4 and the manure-management transfer",
 "PCRET / provincial energy department / RSPN biogas programme installation and operating records (by request)",
 "Combustion CO2 would be biogenic; the reportable quantities are digester leakage CH4 and the manure transfer. Believed small against the 58.7 Mt cake stream - believed, not bounded."),
("1.A.4.b", "Residential - charcoal production wood"): (
 "SCREENING", "35-50 kt of wood carbonised upstream (wood mass, NOT CO2e)",
 "derived in the inventory justification from the 8.3 kt of charcoal burned at 4-6 kg wood per kg charcoal. A wood mass, deliberately not converted: the CO2 is biogenic and the reportable term is kiln CH4, for which no kiln-method split is held.",
 "none",
 "LOW but real: the wood is a forestry removal that LULUCF would also want, and FAOSTAT carries a Pakistani charcoal item from the same flagged-estimate family the firewood stream just escaped.",
 "obtain a Pakistani charcoal-production statistic with kiln method",
 "any national charcoal-production statistic; none located at any scale",
 "Bounded above by the burned charcoal itself and far below the firewood stream's uncertainty band. The range given is an ACTIVITY range, not an emissions range - do not read it as Mt CO2e."),
("1.A.4.c", "Stationary agriculture/forestry and railway workshops"): (
 "CONDITIONAL", "railway workshop/pump/track-machine fuel 1,599 thousand litres (1.21 percent of the p.163 detail total); stationary farm plant unquantified",
 "pkinv.sectors.railways.reconcile for the railway figure (measured); the farm-plant share is an UNRESOLVED claimant row of outputs/transport_fuel_ledger_2024.csv with no magnitude",
 "moderate",
 "HIGH, AND IT IS A MISCATEGORISATION RATHER THAN AN OMISSION. Stationary farm diesel is inside the 1.A.3.b ROAD control total and is reported at ROAD factors. Moving it to 1.A.4.c must remove it from the road total in the same operation, or road transport will be doubly reduced or the fuel doubly counted.",
 "split the OCAC agriculture row out of the road control and reassign at stationary factors; publish the railway workshop split below the measured 1,599 thousand litres",
 "OCAC agriculture end-use row (held but unsplit) and the source-level split below the railway figure (unpublished)",
 "IE, not NE - and the inventory explicitly records that this row previously carried the wrong key. The fuel IS estimated, in the wrong category at the wrong factors."),
("1.A.2", "Captive-generation diesel and furnace oil"): (
 "CONDITIONAL", "unknown for the retail-pump remainder",
 "bulk purchases are inside the estimated 1.A.2 industrial liquids (OCAC Total Industry customer class); only the retail-pump remainder is misplaced, and it has no magnitude - it is an UNRESOLVED claimant row of outputs/transport_fuel_ledger_2024.csv",
 "moderate",
 "HIGH. Already handled in one direction (the transport ledger excludes the Industry claimant from the road control by construction) and declared in the other (retail captive diesel biases road transport HIGH). Captive GAS self-generation is separately estimated by the power module and reported under industry via data/stream_reporting_sector.csv - a third place the same concept lives.",
 "resolve the retail-pump captive claimant in the transport fuel ledger",
 "an end-use split of retail HSD (gap transport-hsd-end-use)",
 "IE in two places at once. The declared direction of bias is the useful part: road transport is biased high, not the total."),
("1.A.2", "Construction and industrial mobile machinery (1A2gvii)"): (
 "CONDITIONAL", "unknown",
 "the fuel sits inside the Mixed off-road (1A4c/1A2) category, which is the source workbook's residual bucket as well as its tractor class; no source decomposes the residual",
 "none",
 "MODERATE. Whatever construction plant the residual holds is estimated at Table 3.3.1 tractor factors and allocated on a CROPLAND proxy that is wrong for construction - a spatial as well as a categorical error, with no mass effect on the national total.",
 "split the off-road residual by equipment stock",
 "equipment stock data for construction and industrial off-road machinery; no held source provides it",
 "The inventory records that it previously overgeneralised this mapping to 1.A.4.c. IE: the mass is counted, the category and the geography are wrong."),
("1.B.2", "Fugitive emissions - refining, well drilling, testing and servicing"): (
 "UNESTIMATED/BLOCKED", "unknown; 3.64 Mt CO2e is Pakistan's own BTR 2021 figure for ALL of 1.B.2",
 "Pakistan BTR1 2024 Table 3, line 1.B.2 Oil and Natural Gas = 3.64 Mt CO2e (0.009 CO2 + 3.63 CH4 + 0.00001 N2O), inventory year 2021. That is the whole of 1.B.2 including the segments PakEmis DOES estimate, so it is an upper bound on this row and not a value for it.",
 "weak",
 "LOW on mass, HIGH on arithmetic: the BTR 3.64 Mt covers segments PakEmis already estimates. Subtracting PakEmis's estimated 1.B.2 from the BTR total to 'derive' this row would be exactly the residual-insertion error the numbers discipline forbids.",
 "obtain refinery-wise crude throughput and well/field counts",
 "OCAC Pakistan Oil Report refinery throughput (registration) and PPIS well and field records (registration). Access-controlled, not nonexistent - the register was corrected on this point.",
 "Small against production per the inventory. The BTR comparator is recorded as a scope bound only."),
("1.B.2", "Fugitive emissions - gas transmission and distribution"): (
 "CONDITIONAL", "unknown",
 "the inventory names this the largest omission inside 1.B.2 and the cheapest to close, but prices NO range: the available UFG line is not a leakage rate. outputs/fugitives_ufg_diagnostic_2024.csv exists as a diagnostic.",
 "strong",
 "HIGH, TWO WAYS. (1) The post-meter leakage term already in the fugitives module covers part of the distribution network; a T&D addition must not re-count it. (2) The commercial gas class counted as post-meter leakage (see 1.A.4.a) is entangled with the same stream.",
 "drive the IPCC Tier 1 T&D method from utility throughput (gas received and sold, network length), which SNGPL and SSGC both publish annually",
 "nothing is blocked - the utilities' annual reports are public and free. This is an extraction, not an acquisition.",
 "EXPLICIT CAUTION FROM THE GAP REGISTER, repeated because it is the trap: UFG is the gap between gas purchased and gas billed and includes theft, meter error and billing differences as well as physical leakage. It BOUNDS the category; it must never be multiplied by a GWP and reported as leakage."),
("1.B.1", "Fugitive emissions from solid fuels"): (
 "SCREENING", "0.07-0.55 Mt CO2e for the SURFACE share only; 0.73 Mt CO2e is Pakistan's own BTR 2021 figure for all of 1.B.1",
 "outputs/fugitives_coal_screen_2024.csv (Tier 1 surface band on NEPRA Table 21 mine-mouth deliveries, 13.24 Mt Thar lignite FY2023-24); Pakistan BTR1 2024 Table 3 line 1.B.1 = 0.73 Mt CO2e, inventory year 2021",
 "weak for the missing half",
 "LOW. Post-mining emissions are kept separate per the activation gate. No energy or process stream counts coal-mine gas.",
 "obtain underground coal production by mine type; the surface share is already screened",
 "underground coal production by mine type (Economic Survey / HDIP Energy Yearbook, paid), and a Pakistani mine-gas measurement, which does not exist at all (gap coal-mine-gas)",
 "The screen is PARTIAL BY CONSTRUCTION and the asymmetry is the point: underground mining runs about thirty times the surface low per tonne, so the unscreened half can dominate the screened one. The BTR's 0.73 Mt sits above the surface band, consistent with underground being non-trivial."),
("4.A", "Solid waste disposal - industrial waste"): (
 "UNESTIMATED/BLOCKED", "unknown",
 "no national tonnage of industrial solid waste reaching disposal sites is held; no source supports a range",
 "moderate",
 "MODERATE. Industrial waste that is open-burned or composted may already sit inside the collected municipal tonnage feeding the 4.A decay model; adding an industrial stream without checking would double count.",
 "obtain provincial EPA industrial waste returns, or industrial output by sector as a generation proxy",
 "provincial EPA industrial waste returns (public but not obtained)",
 "Split from a shared industrial-and-construction row at rc17 because two different absences with two different closing acquisitions were sharing one state."),
("4.A", "Solid waste disposal - construction waste"): (
 "UNESTIMATED/BLOCKED", "small by composition; no numeric range supported",
 "construction and demolition waste is largely inert (near-zero degradable organic carbon), which bounds the CH4 potential qualitatively; the tonnage is unquantified so no range is cited",
 "moderate",
 "LOW", 
 "obtain the Urban Unit's tehsil-level solid-waste service and facility mapping (Punjab)",
 "Urban Unit Punjab tehsil service mapping (public, not obtained)",
 "The Urban Unit mapping would not give a national figure but would replace a national assumption for the covered population. A qualitative bound on composition is recorded instead of a number, deliberately."),
("4.A", "Solid waste disposal - CO2 from landfill gas"): (
 "SUPPORTED", "nil (tracked as an AFOLU stock change)",
 "IPCC convention: biogenic, and unlike open burning IPCC does not request it as a memo item",
 "strong",
 "the convention prevents the double count with AFOLU; recorded so the absence is not read as an omission",
 "none", "none",
 "Correctly IE. Note the asymmetry with 4.C.2 open burning, where IPCC DOES request the memo - the two conventions differ and the inventory follows each."),
("4.B", "Biological treatment of solid waste (composting, anaerobic digestion)"): (
 "UNESTIMATED/BLOCKED", "unknown; Pakistan's own BTR 2021 leaves 4.B BLANK, i.e. it does not estimate it either",
 "Pakistan BTR1 2024 Table 3: the 4.B row carries no value in any gas column. The latest official national account has the same gap.",
 "moderate",
 "THE SIGN OF THE OMISSION IS KNOWN AND IT IS NOT UPWARD. The streams composting diverts currently sit inside the collected tonnage and decay at the disposal MCF, so estimating 4.B would MOVE emissions out of 4.A, not add to the total. The omission biases 4.A up.",
 "compile a national composting throughput series",
 "Lahore composting facility throughput records and Urban Unit facility mapping (public, not compiled)",
 "A rare case where the direction of the error is established without the magnitude. Worth more than a number: it tells a user the total is not understated by this row."),
("4.C.1", "Waste incineration"): (
 "SCREENING", "bounded far below 4.C.2's 3.83 Mt of open burning; 0.11 Mt CO2e is Pakistan's own BTR 2021 figure for 4.C.1",
 "Pakistan BTR1 2024 Table 3 line 4.C.1 = 0.11 Mt CO2e (0.08 CO2 + 0.01 CH4 + 0.02 N2O), inventory year 2021. PakEmis's own bound is relative (far below its 3.83 Mt open-burning estimate) and carries no number.",
 "moderate",
 "LOW on mass. BUT NOTE THE DIRECTION OF DISAGREEMENT: the same BTR table books 4.C.2 open burning at 0.20 Mt where PakEmis estimates 3.83 Mt - a factor of 19. The BTR's 4.C.1 figure is therefore not a calibrated comparator; it is one account's number next to another's.",
 "obtain provincial EPA hospital-waste returns under the Hospital Waste Management Rules",
 "provincial EPA / Pak-EPA hospital-waste returns (public, not obtained)",
 "No municipal-scale incineration operates in Pakistan; hospital and clinical-waste incinerators do. The category must appear as NE rather than silently not existing - which is what this matrix is for."),
("4.D", "Industrial wastewater"): (
 "UNESTIMATED/BLOCKED", "unknown; 2.22 Mt CO2e is Pakistan's own BTR 2021 figure for 4.D.2",
 "Pakistan BTR1 2024 Table 3 line 4.D.2 Industrial Wastewater = 2.22 Mt CO2e (CH4), inventory year 2021. An official magnitude for a category PakEmis does not estimate - the single largest BTR-vs-PakEmis scope gap outside 2.F.",
 "weak",
 "MODERATE. Industrial effluent discharged to municipal sewers may already be inside the 4.D.1 domestic load; a 4.D.2 addition needs the sewer boundary drawn first (the waste round's sewer-MCF work is the place it would be drawn).",
 "obtain industrial output by sector and wastewater organic loading (COD); PCRWR drain BOD/COD measurements constrain loading but do not supply output",
 "industrial output by sector - the SAME HDIP/industry data that blocks 1A2-industrial-fuel. One acquisition unblocks two categories.",
 "The BTR's 2.22 Mt is recorded as a scope screen, not a value to adopt: it rests on methods and an industrial-output series PakEmis has not seen."),
("1.A.2", "Captive self-generation - furnace oil / diesel / coal / bagasse"): (
 "SCREENING", "capacity only: 769 MW furnace oil (64 plants), 366 MW bagasse (25), 351 MW coal (9), 126 MW biomass (9), 64 MW diesel (3), against 1,294 MW of gas",
 "the captive plant register's own fuel fields (SNGPL/SSGC register, 1,105 plants). A CAPACITY inventory, not a fuel series: no metered tonne is held for any non-gas plant.",
 "weak",
 "HIGH IF DONE CARELESSLY, and it has already gone wrong once: the brick and captive screenings were RETIRED at rc47 Wave 0 as superseded_by_reference_stream because adding them to a reference that books the measured HDIP series double counted. Bagasse additionally overlaps the power module's grid-connected bagasse cogeneration.",
 "obtain operator or association fuel returns for the non-gas captive fleet",
 "metered fuel for the non-gas captive plants (operator/association returns, by request)",
 "EXPLICIT INSTRUCTION FROM THE GAP REGISTER: do not estimate from capacity times assumed factors except as a labelled structural case. The unestimated fleet is comparable in CAPACITY to the estimated one, which is a scope statement and not a mass one."),
("1.A.2", "Manufacturing industries and construction - all other"): (
 "SCREENING", "~15.9 Mt CO2e benchmark residual, bounded but NOT decomposable; named claimants inside it: cement transferred-intensity excess +1.2 to +4.9 Mt and a process-bagasse ceiling 0.39 Mt",
 "outputs/industry_fuel_ledger_2024.csv against EDGAR Industrial Combustion (~44 Mt vs engine 22.58). EDGAR is a screening benchmark here, not truth - and the gap register records that EDGAR is IEA-balance-derived and HDIP-fed upstream, so it is NOT independent of PakEmis's own coal series.",
 "weak for what remains",
 "VERY HIGH AND REALISED. Two screenings (brick, captive) had to be retired at rc47 Wave 0 because they double counted against the activated HDIP measured series. The remaining claimants are a benchmark DISAGREEMENT over an exhaustive consumer series, not an identified missing mass.",
 "a Pakistani kiln heat-intensity audit to settle the cement excess, plus industrial fuel by type beyond the Statistical Supplement consumer split",
 "HDIP Pakistan Energy Yearbook (paid) or OCAC member series (members-only)",
 "NO LONGER THE GAP IT WAS - the clearest case in this matrix of why prose must not be trusted over the executable inventory. rc46 activated the measured HDIP coal-by-consumer series (+13.57 Mt), and the supply-consumption identity closed the old 'other industrial coal' refusal: it is definitionally near-zero. The row was narrowed TWICE and both narrowings corrected a claim that data did not exist when it was already in the repository, unread."),
("1.A.5.b", "Military and general aviation"): (
 "CONDITIONAL", "~0.435 Mt CO2 (120,758 t military/government jet fuel + 4,542 t 100LL + 12,282 t unresolved government JP-1)",
 "the OCAC customer bridge, priced as memo rows in outputs/aviation_totals_fy2023_24.csv and restated per tonne with an evidence class and a named closer in outputs/aviation_unallocated_fuel_fy2023_24.csv",
 "moderate",
 "HANDLED. The streams are memo rows and three independent configurations, outside the 1.A.3.a total, so they cannot double count today. The risk is on activation: 1.A.5.b and 1.A.3.a draw on the same OCAC jet-fuel supply.",
 "attribute the activity between military operations and civil government use",
 "military/government flight activity records - stages, aircraft, purpose split (Ministry of Defence / CAA, by request)",
 "THE FUEL IS IDENTIFIED AND PRICED; only the SCOPE attribution is missing. This is the cleanest CONDITIONAL in the matrix: a decision, not an acquisition, stands between it and an estimate."),
("1.A.3.b", "Electric road vehicles"): (
 "SUPPORTED", "nil direct combustion by definition",
 "zero by definition for direct combustion; the registered electric fleet is negligible in the 2022 registration data",
 "strong",
 "the row exists to make the road-scope boundary explicit; electricity is counted at 1.A.1.a (the Orange Line convention)",
 "none; revisit if the registered electric fleet becomes non-negligible",
 "none",
 "A boundary row rather than an implicit omission - the practice this whole matrix is trying to generalise."),
("2.F.1", "Mobile air-conditioning (road vehicles)"): (
 "CONDITIONAL", "PakEmis's own species bank assigns mobile AC 1.5876 Mt CO2e AR5 for 2024 (HFC-134a plus R-134a-bearing blends in the mobile AC application)",
 "computed in this campaign from outputs/ippu_hfc_species_bank.csv, which is a CONFIGURATION outside every total; the application split inside it is the UNDP report's own declared structure (HFC-134a 70 percent mobile / 30 percent refrigeration), declared and never measured",
 "moderate",
 "HIGH AND STRUCTURAL. 2.F.1 mobile AC must be reported ONCE - under IPPU 2.F.1, not under transport - and the transport GHG total excludes it by construction (combustion only). The risk is that a transport-side activation and the IPPU bank would both claim it.",
 "reconcile the mobile-AC application split out of the 2.F bank: charge sizes, fleet penetration, leakage and end-of-life recovery for the vehicle application",
 "none absolutely - this is a reconciliation on data largely in hand; see fgas.csv for what would make it defensible rather than merely computable",
 "The magnitude is PakEmis's own configuration output, not an external number, and it rests on a DECLARED application share. Do not promote it."),
("1.A.3.c", "Urban electric rail (Lahore Orange Line)"): (
 "SUPPORTED", "nil direct combustion by definition",
 "the Orange Line is an electric metro outside Pakistan Railways; electricity counted at 1.A.1.a",
 "strong", "the row prevents an implicit omission in the railway scope statement",
 "none", "none", "A boundary row."),
("1.A.3.d", "Water-borne navigation - domestic"): (
 "CONDITIONAL", "0.0098 Mt CO2e in FY2023-24 (3,054 t HSD); the ten held OCAC editions span 32 to 8,342 t, i.e. 0.0001-0.0268 Mt, with no trend",
 "outputs/transport_navigation_screen_2024.csv, built by sectors/transport/navigation_screen.py from every held OCAC edition's Domestic Bunkers row on IPCC Tables 3.5.2/3.5.3",
 "moderate",
 "DECLARED IN THE SCREEN: fishing vessels fuelling at retail pumps are inside the Road row, so a domestic-navigation activation on OCAC's bunkers row alone would leave that fuel in road transport.",
 "obtain a port-side activity series stable enough to carry an E, and rebuild at the next reference year",
 "nothing is absolutely blocked; the factor choice and boundary review are MADE. What is missing is a stable activity basis - the port-side series.",
 "The two blockers the earlier register row named are closed. It stays NE for two stated reasons: frozen reference-year totals, and an activity series that swings 260-fold across held editions with no trend. Volatility, not absence."),
("1.A.3.d", "Water-borne navigation - international bunkers"): (
 "UNESTIMATED/BLOCKED", "0.040 Mt CO2e is what Pakistan's BTR 2021 books as its international marine bunkers memo item",
 "Pakistan BTR1 2024 Table 3, Memo Items, 1A3d1 International Marine (Bunkers) = 0.040 Mt CO2e, inventory year 2021",
 "weak",
 "none (a memo item, outside the total by definition)",
 "obtain port-side bunker deliveries",
 "a Pakistani bunker-delivery statistic; the inventory records that Pakistan had no formal bunkering market until 2026",
 "A CONTRADICTION WORTH RAISING, NOT RESOLVING HERE: PakEmis says there was no formal bunkering market before 2026, while the BTR books 0.040 Mt of international marine bunkers for 2021. One of the two is wrong about the activity, and the matrix records the disagreement. SEPARATE TRAP, from the inventory's own note: the 'Overseas/Export' line of OGRA Table 2.1 is exported furnace-oil CARGO (1.01 Mt FY2023-24), not fuel bunkered at Pakistani ports. Nobody should build this category on that line."),
("(air)", "Air pollutants - road transport cold-start excess"): (
 "UNESTIMATED/BLOCKED", "unknown",
 "no range supported; the exploratory diagnostic is hot-exhaust-only",
 "moderate",
 "LOW: cold-start excess is additive to hot exhaust by construction in the EMEP method, so there is no double-count risk - but it must be added as an excess, never as a replacement factor.",
 "acquire the EMEP/EEA 2023 ch 1.A.3.b cold-start methodology and assemble trip counts, trip lengths and ambient temperature",
 "Pakistani trip statistics - trips per day and trip length. None identified. The guidebook chapter itself is on the same public endpoint earlier chapters came from.",
 "Material for CO and NMVOC in cold months. The guidebook is acquirable; the Pakistani trip survey is the real blocker."),
("(air)", "Air pollutants - aviation NMVOC speciation"): (
 "CONDITIONAL", "unknown as NMVOC; the unspeciated HC series ships as a supplemental species across the nine-year panel",
 "ICAO EEDB publishes HC (unspeciated exhaust hydrocarbons). dim_pollutant's vocabulary rule forbids renaming HC to NMVOC without a documented methane basis.",
 "moderate",
 "none - a naming question, not a mass question",
 "acquire an HC-to-NMVOC speciation basis (methane share of exhaust hydrocarbons per engine and mode)",
 "ICAO/FOCA speciation guidance (public, exists in the literature, not acquired here)",
 "A VOCABULARY absence, not a data absence: the mass is computed and shipped under its honest name. Converting it would take one published ratio."),
("(air)", "Air pollutants - power generation, as actually emitted"): (
 "UNESTIMATED/BLOCKED", "unknown; the published PakEmis bound is the UNCONTROLLED case, and controlled-vs-uncontrolled spans an order of magnitude",
 "no source supports a controlled range. The five NEPRA Licensees HSE Performance Evaluation Reports (2021-2024/25) were fetched and read in August 2026: they publish NO per-plant control equipment, emissions or measurements.",
 "weak",
 "none on mass; this is a factor question, not a scope question",
 "obtain licensee environmental monitoring submissions to NEPRA under the Power Safety Code, or the plants' EIA approvals at provincial EPAs",
 "per-plant control-device inventory and removal efficiency. Established to EXIST at NEPRA as unpublished licensee submissions (the evaluation questionnaire scores licensees on air-quality controls and on submitting environmental monitoring reports) - unpublished, not unmeasured. Route: a request to the HSE department.",
 "RECLASSED FROM no-data-exists BY AN AUDIT. Applying a removal rate without the data would be inventing the number that matters most."),
("(air)", "Air pollutants - industrial combustion NH3"): (
 "UNESTIMATED/BLOCKED", "one field measurement exists for South Asian kilns: below detection for a zig-zag kiln, 0.429 g/kg fuel for a clamp kiln (Stockwell et al. 2016, NAMaSTE)",
 "EMEP/EEA 2023 Tables 3-2/3-3/3-4 type NH3 as NOT ESTIMATED for solid, gaseous and liquid fuel combustion in industry; AP-42's combustion chapters carry no NH3 row. The one measurement is open-access and NOT held.",
 "strong (the paper is open access)",
 "LOW", 
 "acquire Stockwell et al. 2016 and decide whether one clamp-kiln measurement can carry a national factor",
 "nothing is blocked; the paper is open access. What is genuinely absent is a Pakistani SCR/SNCR population - NH3 slip needs units that run it, and none is documented.",
 "ABSENT, NOT ZERO. The chapters DECLINE to estimate; they do not say the emission is nil. This distinction recurs across the (air) rows and is the single most important thing the notation key is carrying here."),
("(air)", "Air pollutants - other-industry coal inside HDIP's cement column"): (
 "SCREENING", "1.4-6.4 Mt of coal per year sits outside the kilns in most years (COAL TONNAGE, not emissions)",
 "the clinker-implied kiln-coal reconstruction (outputs/pakemis_cement_kiln_coal_reconstruction.csv) differenced against HDIP's Cement/Other Industry column, per year. A tonnage; no factor can be chosen because the users are unidentified.",
 "weak",
 "HIGH IF A FACTOR IS GUESSED: the same tonnage is already inside the GHG coal series, so the air layer must price it without re-pricing the carbon.",
 "identify the users (steel re-rolling? textile boilers? sugar? misfiled bricks?) before any equipment or control can be assigned",
 "HDIP coal-by-consumer detail below the Cement/Other Industry label (request), PBS CMI fuel-by-industry (coal not separable from firewood), UNSD manufacturing coal",
 "The air layer writes the TONNAGE and a typed absence (other_industry_coal_in_cement_column) rather than a stoker-boiler default. Exactly the right behaviour: a quantified activity beside a declared inability to price it."),
("(air)", "Air pollutants - captive self-generation on coal"): (
 "SCREENING", "capacity only (351 MW coal, 9 plants); the GHG screening prices a utilisation x heat-rate bracket outside every total",
 "the captive register's capacity fields and captive_screening.py's bracket. No metered tonne is held.",
 "weak",
 "shares the 1.A.2 captive overlap above; the air layer types the class absent rather than multiply a bracket by a factor",
 "obtain NEPRA captive licensing returns (annual generation and fuel by plant) or SECMC/Thar and imported-coal delivery records to captive plants",
 "a metered coal series for the register's coal-fired captive plants (NEPRA / licensees, by request)",
 "The air layer's refusal to multiply a bracket by a factor is the correct call and is recorded here as precedent."),
("(air)", "Air pollutants - industrial bagasse process heat"): (
 "UNESTIMATED/BLOCKED", "unknown; the all-cane ceiling is a GHG configuration, not an activity",
 "no mill-level bagasse fuel series is held. EMEP 1.A.2 Table 3-5 biomass factors ARE held and would price it immediately.",
 "weak",
 "MODERATE: grid-connected bagasse cogeneration stays in the power screening, so a mill-level series must exclude it.",
 "obtain PSMA / Cane Commissioner crushing and bagasse-use returns by mill, or SECP sugar-mill annual reports",
 "a mill-level bagasse fuel series (PSMA / provincial Cane Commissioners, by request)",
 "The factors are held; only the activity is missing. A one-acquisition category."),
("(air)", "Air pollutants - cement kilns and quarrying (IPPU)"): (
 "SUPPORTED", "estimated since rc58 in the industry layer's integrated kiln class",
 "EMEP 2.A.1 Tier 1 per tonne of clinker with the abatement inherent to clinker production, beside the AP-42 11.6 kiln gases",
 "strong",
 "HANDLED BY AN EXPLICIT POINTER: the register carries ippu_cement_process_pm -> cement_kiln_integrated so the one kiln is never priced twice. The named-pointer pattern is what every IE row in this matrix should have.",
 "none", "none",
 "Gap air-ippu-cement is CLOSED. Listed because old prose describing it as missing would be wrong - checking the executable inventory is what caught it."),
("(air)", "Air pollutants - urea prilling and granulation particulate and ammonia"): (
 "UNESTIMATED/BLOCKED", "unknown. An inadmissible factor would print 330 kt of TSP from 6.6 Mt of urea - recorded to show WHY it is inadmissible, not as a range.",
 "the EMEP 2.B.10.a Table 3-6 row is held and is an E-PRTR/Eurostat ratio for the whole basic-chemicals sector; applying it to a prilling tower gives 330 kt TSP, which is the reductio. AP-42 Section 8.2 is the applicable chapter and is NOT held.",
 "weak (public in principle, 403 in practice)",
 "LOW",
 "acquire AP-42 Section 8.2 (prilling tower and granulator factors) and apply to the NFDC urea tonnage already held",
 "US EPA AP-42 Section 8.2. Every epa.gov address tried on 2026-09-17 returned 403, including the 2020-10 documents path that served the rc58 chapters - logged in data/raw/ACQUISITION_LOG_industrial_air.csv.",
 "The urea tonnage is written beside the typed absence. A rare case where the ACTIVITY is held to high quality and the FACTOR is what is missing."),
("(air)", "Air pollutants - nitric acid process NOx"): (
 "UNESTIMATED/BLOCKED", "unknown as a series; the held factor is EMEP 2.B.2 at 10 kg NOx per tonne of 100 percent acid and the held activity is ONE calendar-2022 point (563,701 t)",
 "EMEP 2.B.2 factor held; Fatima Sadiqabad calendar-2022 production held from the ACM0019 record. One point, which cannot back-cast to FY2015-16.",
 "moderate",
 "none",
 "compile a fiscal nitric-acid production series for both identified plants",
 "a fiscal nitric-acid production series (Pakarab / Fatima annual reports, public but not compiled; PBS QIM lists no nitric-acid item)",
 "BLOCKED BY A DISCIPLINE RULE, NOT BY ABSENCE: a new category must back-cast to FY2015-16 before entering a comparable aggregate, and one calendar-2022 point cannot. The same single point already carries the GHG N2O screening."),
("(air)", "Air pollutants - lime kiln process particulate"): (
 "UNESTIMATED/BLOCKED", "unknown",
 "EMEP 2.A.2 chapter held; no lime production series held. PBS QIM lists no lime item.",
 "weak",
 "shares the 2.A.2 blocker exactly - limestone quarried is not lime produced",
 "obtain a national lime production series by type",
 "national lime production (PBS / provincial mines departments). THE SAME MISSING SERIES blocks 2.A.2 lime CO2: one acquisition closes a GHG category and an air category together.",
 "Paired with 2.A.2 below. The air absence is typed beside the GHG one for the same reason."),
("(air)", "Air pollutants - glass furnace process particulate"): (
 "UNESTIMATED/BLOCKED", "unknown",
 "EMEP 2.A.3 chapter held; the held QIM glass item is an AREA (square metres of sheet) and pricing it per tonne needs a thickness-and-density conversion nobody publishes",
 "weak",
 "the QIM index is already used for TIMING only, never mass, per the scope registry - that exclusion must hold",
 "obtain glass production TONNAGE with cullet ratio and carbonate inputs",
 "glass production tonnage (Ghani Glass / Tariq Glass annual reports, public, not compiled)",
 "A UNIT mismatch, not an absence: the series exists in the wrong units. Pairs with 2.A.3 glass CO2."),
("(air)", "Air pollutants - ammonia and soda ash process species not estimated by the chapters"): (
 "UNESTIMATED/BLOCKED", "unknown",
 "EMEP/EEA 2023 2.B.1 lists NMVOC, SOx and PM2.5 as NOT ESTIMATED for ammonia production; 2.B.7 lists PM10, PM2.5 and BC as not estimated for soda ash",
 "none (no factor exists to acquire)",
 "none",
 "plant-level stack measurements would be needed; no Tier 1 factor exists to apply",
 "operator stack monitoring at Fauji Fertilizer / Engro / Fatima / ICI / Olympia (by request)",
 "NOT ZERO: the chapters decline to estimate, they do not say the emission is nil. Typed absent per species inside the class detail, beside the species the chapters DO price."),
("(air)", "Air pollutants - vented gas NMVOC"): (
 "UNESTIMATED/BLOCKED", "unknown",
 "no vented-volume series held; EMEP 1.B.2.c Tier 1 prices FLARING only",
 "weak",
 "MODERATE: the fugitives module already carries venting inside its production CH4 factors, so a vented-volume series must be reconciled against those factors rather than added to them.",
 "obtain operator venting returns, or a vented-fraction study for Pakistani fields",
 "vented volumes (DGPC / OGRA operator returns, by request)",
 "The CH4 is implicitly carried; the NMVOC is not. An asymmetry inside one module."),
("(air)", "Air pollutants - post-meter leakage NMVOC"): (
 "UNESTIMATED/BLOCKED", "unknown",
 "gas_ch4_fraction 0.90 is CH4 BY MASS, not an NMVOC fraction; no C2+ composition of sales gas is held",
 "weak",
 "none - it would be a new species on a leak already quantified",
 "obtain SNGPL / SSGC sales-gas composition (C2+ content by network and year)",
 "sales-gas C2+ composition (utilities, by request)",
 "A GOOD CATCH TO PRESERVE: using 1 - 0.90 as an NMVOC share would be a units error dressed as a chemistry assumption. The register says so explicitly."),
("(air)", "Air pollutants - LNG import terminal and oil pipeline NMVOC"): (
 "UNESTIMATED/BLOCKED", "unknown",
 "EMEP/EEA 2023 1.B.2 prints NO Tier 1 NMVOC factor for regasification terminals. The imported-oil transport factor IS held (0.054 kg/m3, EMEP 1.B.2.a.i Table 3-3) but the module's oil-pipeline anchor is a diagnostic LENGTH, not a throughput.",
 "weak",
 "none",
 "a pipeline throughput series (PARCO / PAPCO) and, for the terminal, a factor that does not exist in the guidebook",
 "two different blockers in one row: a missing FACTOR for terminals and a missing ACTIVITY (throughput) for pipelines",
 "Recorded as one row because the inventory does, but it is two absences of different kinds. A factor that does not exist cannot be acquired."),
("(air)", "Air pollutants - flare and refinery species not estimated by the chapters"): (
 "UNESTIMATED/BLOCKED", "unknown",
 "EMEP/EEA 2023 1.B.2.c lists NH3 as not estimated for flaring; 1.B.2.a.iv lists BC as not estimated for refining; refinery flaring prints no particulate",
 "none (no factor exists to acquire)",
 "none",
 "operator stack and flare monitoring",
 "no Tier 1 factor exists; plant monitoring would be needed (operators, by request)",
 "The fugitives NH3 cell of the air coverage matrix rests on this row. Typed absence, not zero."),
("2.A.2", "Lime production"): (
 "SCREENING", "1.33 Mt CO2 is what Pakistan's own account books for 2.A.2 (BTR 2021); the 2022 CRT carries the activity and the factor",
 "Pakistan BTR1 2024 Table 3 line 2.A.2 = 1.33 Mt CO2, inventory year 2021. The 2022 CRT activity and factor are extracted into this repository.",
 "moderate",
 "MODERATE: cement process CO2 is a SEPARATE carbonate and is excluded per the scope registry. The arithmetic trap is limestone QUARRIED (which PBS minerals does publish) standing in for lime PRODUCED (which it does not) - the register says so in as many words.",
 "compile an independent FY2023-24 marketed-PLUS-captive lime series by type (quicklime/hydrated)",
 "lime output by type. The CRT gives one year on someone else's method; an independent fiscal series does not exist here.",
 "THE BEST-SUPPORTED MAGNITUDE OF ANY NE ROW IN THIS MATRIX - Pakistan's own inventory prints it. That makes it a strong scope screen and still not a PakEmis estimate: adopting 1.33 Mt would import another account's method and vintage into a supposedly independent inventory. Pairs with the lime-kiln air row."),
("2.B.2", "Nitric acid production"): (
 "SCREENING", "0.733-1.046 Mt CO2e: 1.046 unabated (one of two plants, calendar-2022 vintage) and 0.733 at the last ACM0019-verified destruction rate",
 "outputs/ippu_chemicals_screening_2024.csv, published as two configurations (nitric_acid_unabated_in_scope, nitric_acid_abated_in_scope) from Fatima Sadiqabad's calendar-2022 production and its 2007-2020 CDM abatement history",
 "moderate",
 "none (a new category; the scope registry records no exclusions)",
 "obtain matched-year production for BOTH plants and evidence the ACM0019 catalyst still operates",
 "matched-year production and operating abatement evidence (Fatima Fertilizer, Pakarab Fertilizers, CDM registry; by request)",
 "THE SILENT-ABSENCE CLASS, CAUGHT: the national completeness table had NO 2.B.2 row until Wave 4, while the sector-level IPPU view carried the category at CRITICAL materiality. The screening bracket's whole width is the abatement question - whether a catalyst installed under a CDM project that ended in 2020 still runs."),
("2.B.7", "Soda ash production"): (
 "SUPPORTED", "nil in IPPU by method; the QIM tonnage is 785,283 t FY2023-24 and is carried for the ENERGY-side term",
 "IPCC 2006 Vol 3 s3.8.3.1: both producers (LCI Khewra, Olympia) run the SOLVAY process, whose emissions IPCC allocates to the Energy sector (coke burned in the lime kilns) with no IPPU method provided",
 "strong",
 "THE OVERLAP IS THE POINT AND IT IS HANDLED BY RECLASSIFICATION: the carbon belongs under 1.A.2 and is typed absent THERE until coke tonnage is held. NA in IPPU plus a typed absence in Energy is the correct pair; NA alone would hide the term.",
 "obtain coke tonnage for the soda-ash lime kilns, then book it under 1.A.2",
 "coke tonnage at LCI Khewra and Olympia",
 "The ONLY NA in the inventory, and I checked it: the earlier natural-process ceiling (0.0974 t/t) was the wrong method for a Solvay country. An NA that moves a term to another sector must leave a visible row in that sector, and this one does."),
("2.F", "Product uses as substitutes for ODS (F-gases)"): (
 "SCREENING", "5.854 Mt CO2e AR5 (species bank, 2024); 4.42 Mt [2.3-6.2] (one-stratum bounded bank); 9.815 Mt potential-consumption ceiling; 0.00294 Mt Pakistan's own 2022 CRT; 11.54 Mt EDGAR",
 "outputs/ippu_hfc_species_bank.csv and outputs/ippu_fgas_screening_2024.csv - FIVE typed lanes, never blended. A SIXTH lane also ships: outputs/pakemis_hfc_bank_series.csv, the household equipment-stock band (FY2023-24 floor 0.191-2.423 Mt CO2e). See fgas.csv in this directory for the full treatment and fgas_benchmark_consistency.csv for three tests of the EDGAR figure.",
 "strong for supply, weak for the bank",
 "LOW against energy/waste/process streams (refrigerant leakage is chemically distinct and cannot be confused with a fuel). The real overlap risk is INTERNAL: 2.F.1 mobile AC is also a transport-row claim (see above), and the 2.F.2-2.F.6 applications below are inside this same bank.",
 "see fgas.csv - the single unmet activation criterion is PRE-CHARGED EQUIPMENT imports",
 "pre-charged-equipment import and export series (National Ozone Unit / FBR Customs, REQ-NOU-01, drafted and not sent). Species- and application-resolved Article-7 detail is the second ask.",
 "THE LARGEST SINGLE OMISSION IN THE INVENTORY AND THE BEST-INSTRUMENTED. Four of the five activation-gate criteria are MET; the fifth (charged equipment) is not. Pakistan's own latest reporting - BTR1 2024, inventory year 2021 - books 2.F as ZERO, so the official record has not moved either."),
("LU", "Cropland (SOC)"): (
 "UNESTIMATED/BLOCKED", "unknown; set to 0 at Tier 1, which matches FAOSTAT",
 "no source supports a range. A Tier 1 zero is a method convention, and matching FAOSTAT means matching the same convention, not corroborating it.",
 "none",
 "overlaps 3.D FSOM above: the same soil carbon-nitrogen response must not be booked twice",
 "obtain land-use-change areas and management data at Tier 1 minimum",
 "soil organic carbon stock-change activity data. Not sought.",
 "Four LULUCF rows in this matrix all read 'not sought'. That is an honest claim class and it is also the campaign's cheapest open front - FAOSTAT and PBS carry pieces of it."),
("LU", "Grassland (SOC)"): (
 "UNESTIMATED/BLOCKED", "unknown; set to 0 at Tier 1, which matches FAOSTAT",
 "as cropland SOC: a Tier 1 convention, not a measurement",
 "none", "overlaps 3.D FSOM",
 "obtain land-use-change areas and management data",
 "soil organic carbon stock-change activity data. Not sought.",
 "As cropland SOC."),
("LU", "Settlements / Other land"): (
 "UNESTIMATED/BLOCKED", "unknown",
 "not quantified; described as small and outside the agricultural land base, with no source behind the smallness",
 "none",
 "settlement expansion overlaps the cropland and grassland conversions above; the land lane's own finding was that Pakistan's official account books the same biomass mass in two blocks",
 "obtain land-use-change areas for settlements and other land",
 "land-use-change areas. Not sought.",
 "'Small' here is an assertion, not a bound. Recorded as unknown."),
("LU", "Harvested wood products"): (
 "CONDITIONAL", "unknown",
 "no range supported, but BOTH inputs are public: FAOSTAT publishes roundwood production and PBS publishes wood trade. What is missing is the half-life model, which is a choice rather than an acquisition.",
 "strong",
 "MODERATE: the HWP pool and the forest-land biomass loss describe the same harvested carbon at different times. Booking both without the pool accounting is the standard HWP double count.",
 "assemble FAOSTAT roundwood + PBS wood trade and choose a half-life model",
 "nothing is blocked. 'Not attempted' is the honest status.",
 "The most tractable LULUCF row: public inputs on both sides and a documented IPCC method. CONDITIONAL rather than SUPPORTED because the half-life choice materially moves the answer and has not been made."),
}

# IPPU categories that the SECTOR gap matrix carries as NE but that have NO ROW AT
# ALL in outputs/completeness.csv. Same silent-absence class as the 1.A.4.a audit
# and the Wave-4 insertion of 2.B.2. Fields as above, preceded by gas.
ABSENT_FROM_COMPLETENESS = [
("2.A.3", "Glass production", "CO2", "NE", "UNESTIMATED/BLOCKED", "unknown",
 "the held QIM glass item is an AREA (square metres of sheet); no tonnage source is held",
 "weak", "the QIM index is used for TIMING only, never mass (scope registry exclusion)",
 "convert output to tonnes and obtain glass type, cullet ratio and carbonate inputs",
 "glass production tonnage with cullet and carbonates (PBS / producers)",
 "NOT IN outputs/completeness.csv. Carried in data/sectors/ippu/metadata/master_data_gap_matrix.csv at MEDIUM materiality with an estimator already implemented. Pairs with the glass air row, which IS in the completeness table - so the air panel declares an absence the GHG panel does not."),
("2.A.4", "Other process uses of carbonates", "CO2", "NE", "SCREENING",
 "0.27 Mt CO2 is what Pakistan's own account books for 2.A.4 (BTR 2021)",
 "Pakistan BTR1 2024 Table 3 line 2.A.4 = 0.27 Mt CO2, inventory year 2021",
 "weak", "cement and lime carbonates must be excluded; this row is ceramics, refractories and fluxes",
 "screen ceramics, refractories and carbonate fluxes",
 "PBS CMI ceramics and mineral statistics (not compiled)",
 "NOT IN outputs/completeness.csv, yet Pakistan's own inventory prints a number for it. An omitted category with an official magnitude is the clearest kind of finding this matrix can produce."),
("2.B.3", "Adipic acid production", "N2O", "NE", "UNESTIMATED/BLOCKED", "unknown",
 "occurrence not established - which is NOT the same as established absence",
 "weak", "none",
 "establish occurrence before assigning NO",
 "PBS CMI / customs evidence of adipic acid production in Pakistan",
 "NOT IN outputs/completeness.csv. The right discipline is visible in the sector matrix: NE until occurrence is screened, then NO with evidence. Assigning NO without the screen is the error."),
("2.B.4", "Caprolactam, glyoxal and glyoxylic acid", "CO2/N2O", "NE", "UNESTIMATED/BLOCKED", "unknown",
 "occurrence not established", "weak", "none",
 "establish occurrence before assigning NO",
 "PBS CMI / customs evidence of occurrence",
 "NOT IN outputs/completeness.csv."),
("2.B.5", "Carbide production", "CO2/CH4", "NE", "UNESTIMATED/BLOCKED", "unknown",
 "occurrence not established", "weak", "none",
 "establish occurrence and production route",
 "PBS CMI / customs evidence of occurrence",
 "NOT IN outputs/completeness.csv."),
("2.B.6", "Titanium dioxide production", "CO2", "NE", "UNESTIMATED/BLOCKED", "unknown",
 "occurrence not established", "weak", "none",
 "establish occurrence and process route",
 "PBS CMI / customs evidence of occurrence",
 "NOT IN outputs/completeness.csv."),
("2.B.8", "Petrochemical and carbon black production", "CO2/CH4", "NE", "UNESTIMATED/BLOCKED", "unknown",
 "not compiled; no production or process-route series held",
 "weak",
 "MODERATE: petrochemical feedstock gas may already be inside the gas ledger's feedstock deduction, as ammonia feedstock is",
 "compile products and process routes",
 "PBS CMI/QIM and company reports (public, not compiled)",
 "NOT IN outputs/completeness.csv. MEDIUM materiality in the sector matrix. Pakistan has an operating petrochemical sector (PTA, polyester, carbon black), so 'not compiled' here is a real omission rather than a non-occurrence."),
("2.B.9", "Fluorochemical production", "F-gases", "NE", "SCREENING",
 "unknown as emissions; the supply-side screen is that Pakistan's Article-7 reporting shows CONSUMPTION (production + imports - exports) and the species bank treats domestic_production_t as zero on every row",
 "data/sectors/ippu/activity/hfc_inventory_rows.csv sets domestic_production_t = 0 for all 143 species-application-years, sourced to the UNDP RAC import table and Comtrade. That is a modelling assumption consistent with an import-only market, not an occurrence screen.",
 "moderate",
 "HIGH FOR THE F-GAS PROGRAMME: if any domestic HCFC-22 production exists, its HFC-23 by-product belongs at 2.B.9 and NOT in the 2.F bank - and HFC-23 is the one species Pakistan's 2022 CRT actually reports (0.237 t under 2.F.1.a commercial refrigeration, which is the wrong category for by-product HFC-23).",
 "separate domestic production from imports in the Article-7 detail",
 "National Ozone Unit confirmation that no Annex-F or HCFC production facility operates in Pakistan",
 "NOT IN outputs/completeness.csv. See fgas.csv: this is the one place where the CRT's single reported F-gas species looks misfiled, and it matters because 2.B.9 by-product HFC-23 is a large term wherever it occurs."),
("2.B.10", "Other chemical production", "CO2/CH4/N2O", "NE", "UNESTIMATED/BLOCKED", "unknown",
 "not compiled", "weak", "hydrogen production may overlap the ammonia feedstock gas already deducted",
 "screen hydrogen and the remaining processes",
 "PBS CMI (not compiled)",
 "NOT IN outputs/completeness.csv. Materiality recorded as unknown in the sector matrix, which is itself the finding."),
("2.C.2", "Ferroalloys production", "CO2/CH4", "NE", "UNESTIMATED/BLOCKED", "unknown",
 "occurrence not established", "weak",
 "would overlap 2.C.1 iron and steel if the same furnaces were counted twice",
 "establish occurrence and reductant inputs",
 "PBS CMI / customs evidence of occurrence",
 "NOT IN outputs/completeness.csv. MEDIUM materiality."),
("2.C.3", "Aluminium production", "CO2/PFCs", "NE", "SCREENING",
 "nil for PFCs if no primary smelter operates; Pakistan's own BTR 2021 books ALL of 2.C Metal Industry at 0",
 "Pakistan BTR1 2024 Table 3: line 2.C Metal Industry = 0 across CO2, CH4 and N2O for inventory year 2021. The sector matrix records 'primary production not established'.",
 "moderate",
 "PFCs from aluminium are an F-GAS term. EDGAR reports Pakistan's F-gases ONLY under Processes, so if any primary smelting existed its PFCs would be inside EDGAR's 11.54 Mt and outside the HFC bank entirely - a reason the EDGAR-vs-bank gap cannot be read as HFCs alone.",
 "separate primary aluminium from remelting and fabrication",
 "PBS CMI / customs evidence distinguishing primary smelting from remelting",
 "NOT IN outputs/completeness.csv. Anode-effect PFCs arise ONLY in primary electrolysis; remelting produces none. Establishing that Pakistan has no primary smelter would convert this to a defensible NO and would also narrow the F-gas benchmark question."),
("2.C.4", "Magnesium production", "CO2/SF6/HFCs", "NE", "UNESTIMATED/BLOCKED", "unknown",
 "occurrence not established", "weak",
 "SF6 and HFC cover gases are F-gas terms and would sit inside EDGAR's Processes F-gas total, not in the 2.F bank",
 "establish occurrence and cover-gas use",
 "PBS CMI / customs evidence of occurrence",
 "NOT IN outputs/completeness.csv."),
("2.C.5", "Lead production", "CO2", "NE", "UNESTIMATED/BLOCKED", "unknown",
 "occurrence not established; secondary (battery recycling) lead smelting is known to operate in Pakistan but is not quantified here",
 "weak", "none",
 "separate primary and secondary production",
 "PBS CMI / company reports",
 "NOT IN outputs/completeness.csv."),
("2.C.6", "Zinc production", "CO2", "NE", "UNESTIMATED/BLOCKED", "unknown",
 "occurrence not established", "weak", "none",
 "separate primary and secondary production",
 "PBS CMI / company reports",
 "NOT IN outputs/completeness.csv."),
("2.C.7", "Other metal production", "multiple", "NE", "UNESTIMATED/BLOCKED", "unknown",
 "not compiled", "weak", "none",
 "complete the occurrence screen",
 "PBS CMI",
 "NOT IN outputs/completeness.csv. Materiality unknown."),
("2.D.2", "Paraffin wax use", "CO2", "NE", "CONDITIONAL", "unknown",
 "no range compiled, but the estimator is implemented and OCAC non-energy product sales are the same source family that already carries 2.D.1 lubricants at 0.08329 Mt",
 "moderate",
 "MODERATE: wax must not be double counted against the OCAC non-energy totals already used for 2.D.1",
 "compile apparent consumption and oxidation assumptions",
 "nothing absolutely - OCAC non-energy sectoral sales are already in the repository for 2.D.1",
 "NOT IN outputs/completeness.csv. A one-extraction category on data already held: the same table, a different column. Low materiality, but the cheapest IPPU row in this matrix."),
("2.D.3", "Other non-energy products", "CO2", "NE", "UNESTIMATED/BLOCKED", "unknown",
 "not compiled", "weak", "asphalt and solvent uses overlap the OCAC non-energy classes used for 2.D.1",
 "screen solvent, asphalt and urea-catalyst uses",
 "PBS QIM/CMI and OCAC (not compiled)",
 "NOT IN outputs/completeness.csv."),
("2.E", "Electronics industry", "F-gases", "NE", "SCREENING",
 "nil if no semiconductor, PV-cell or flat-panel FABRICATION occurs; Pakistan's own BTR 2021 books 2.E at 0",
 "Pakistan BTR1 2024 Table 3: line 2.E Electronics Industry = 0 for inventory year 2021. The sector matrix records 'manufacturing output controls only'.",
 "moderate",
 "an F-GAS term outside the 2.F bank. Electronics process gases (NF3, SF6, C2F6) are reported at 2.E, so any occurrence would widen the F-gas omission beyond HFCs.",
 "determine whether semiconductor, PV or flat-panel process gases occur (assembly is not fabrication)",
 "Ministry of Industries / PBS evidence distinguishing electronics ASSEMBLY from wafer or panel FABRICATION",
 "NOT IN outputs/completeness.csv. Pakistan assembles electronics; fabrication is what emits. LOW materiality, and a defensible NO is one confirmation away."),
("2.F.2", "Foam blowing agents", "HFCs", "NE", "SCREENING",
 "inside the 2.F bank total; NOT separately resolved - the species bank has no foam application stratum at all (its five strata are refrigeration, stationary AC, mobile AC, aerosol, fire protection)",
 "data/sectors/ippu/activity/hfc_inventory_rows.csv application vocabulary, checked in this campaign: 'foam' is in the import contract's controlled vocabulary but has zero rows",
 "weak",
 "foam is INSIDE the aggregate Article-7 consumption the screening prices, so the potential-consumption ceiling already covers it; resolving foam separately redistributes the bank, it does not add to it",
 "acquire chemical and application consumption for foam",
 "application-resolved Article-7 detail (National Ozone Unit)",
 "NOT IN outputs/completeness.csv. MEDIUM materiality. Foam is the application with the LONGEST bank lifetime and the slowest release - treating it at refrigeration loss rates would badly misstate the time profile, which is why its absence from the strata matters more than its share."),
("2.F.3", "Fire protection", "HFCs/PFCs", "NE", "CONDITIONAL",
 "the species bank carries a fire protection stratum through 2021 only; its 2024 contribution is ZERO because the stratum's supply rows stop and the bank is dropped (defect D1)",
 "outputs/ippu_hfc_species_bank.csv application 'fire protection' (HFC-23, 2012-2021; 3.196 t = 0.0396 Mt CO2e of bank abandoned after 2021)",
 "weak", "inside the same bank; no external overlap",
 "acquire agent imports and installed banks, and continue the stratum past its last supply year",
 "installed fire-protection agent banks (National Ozone Unit)",
 "NOT IN outputs/completeness.csv although the bank prices it in earlier years. LOW materiality, but HFC-23's AR5 GWP is 12,400, so a small abandoned mass is not a small CO2e. See defects_found.md D1."),
("2.F.4", "Aerosols", "HFCs", "NE", "CONDITIONAL",
 "the species bank carries an aerosol stratum (HFC-152a) through 2015 only - the UNDP source's R-152a row ends there and the bank is then dropped (defect D1), so the 2024 aerosol contribution is zero",
 "outputs/ippu_hfc_species_bank.csv application 'aerosol' (2012-2015; 39.5 t = 0.0055 Mt CO2e of bank abandoned after 2015)",
 "weak", "inside the same bank",
 "acquire chemical and application consumption",
 "application-resolved Article-7 detail (National Ozone Unit)",
 "NOT IN outputs/completeness.csv. MEDIUM materiality. Aerosols are the one application that is PROMPT-RELEASE - essentially all of the charge is emitted within two years - so for aerosols, and only for aerosols, consumption IS close to annual emissions."),
("2.F.5", "Solvents", "HFCs/PFCs", "NE", "UNESTIMATED/BLOCKED", "unknown",
 "no solvent stratum exists in the bank and no solvent consumption is held",
 "weak", "inside the aggregate consumption ceiling",
 "acquire chemical and application consumption",
 "application-resolved Article-7 detail (National Ozone Unit)",
 "NOT IN outputs/completeness.csv. LOW materiality."),
("2.F.6", "Other ODS-substitute applications", "HFCs/PFCs", "NE", "UNESTIMATED/BLOCKED", "unknown",
 "residual application; materiality recorded as UNKNOWN in the sector matrix",
 "weak", "inside the aggregate consumption ceiling",
 "complete the application screen",
 "application-resolved Article-7 detail (National Ozone Unit)",
 "NOT IN outputs/completeness.csv. A residual whose materiality is unknown is the one kind of residual that cannot be dismissed."),
("2.G.1", "Electrical equipment", "SF6", "NE", "UNESTIMATED/BLOCKED", "unknown",
 "equipment counts exist but NO gas balance does. Pakistan's own BTR 2021 books all of 2.G at 0, which for a country with an extensive high-voltage grid is an NE dressed as a zero.",
 "sector matrix: 'equipment counts but no gas balance'; Pakistan BTR1 2024 Table 3 line 2.G = 0 for inventory year 2021",
 "weak",
 "AN F-GAS TERM COMPLETELY OUTSIDE THE HFC BANK. SF6 from switchgear would sit inside EDGAR's Processes F-gas total. Any attempt to explain the EDGAR-vs-bank gap with HFCs alone ignores this row.",
 "acquire equipment banks, gas purchases, refills and recovery records",
 "SF6 nameplate banks and annual refill records from NTDC, the DISCOs and K-Electric (by request)",
 "NOT IN outputs/completeness.csv, and the HIGHEST materiality (medium-high) of any row the national table omits. Pakistan operates 500 kV and 220 kV transmission; SF6 switchgear is standard at those voltages. The equipment counts being held while the gas balance is not is the classic 2.G.1 position, and the IPCC Tier 1 method runs on nameplate charge times a default leak rate - so this is closer to an estimate than any other row here."),
("2.G.2", "Other SF6 and PFC product use", "SF6/PFCs", "NE", "UNESTIMATED/BLOCKED", "unknown",
 "not compiled", "weak", "an F-gas term outside the HFC bank",
 "complete the occurrence screen",
 "customs and industry survey (Ministry of Industries)",
 "NOT IN outputs/completeness.csv."),
("2.G.3", "N2O product uses", "N2O", "NE", "CONDITIONAL", "unknown",
 "no range compiled, but the estimator is implemented and the activity is medical and aerosol N2O sales",
 "moderate", "none",
 "compile medical and aerosol N2O sales",
 "medical and customs N2O statistics (Ministry of Health, customs)",
 "NOT IN outputs/completeness.csv. Medical nitrous oxide is PROMPT-RELEASE (anaesthetic N2O is vented), so sales are close to emissions here - one of the few places a consumption figure legitimately approximates an annual emission."),
("2.G.4", "Other product manufacture and use", "multiple", "NE", "UNESTIMATED/BLOCKED", "unknown",
 "not compiled", "weak", "none",
 "complete the occurrence screen",
 "PBS CMI and customs",
 "NOT IN outputs/completeness.csv. Materiality unknown."),
("2.H", "Other industrial processes (pulp and paper, food and beverage)", "CO2/CH4/N2O", "NE", "SCREENING",
 "1.35 Mt CO2e is what Pakistan's own account books for 2.H (BTR 2021): 2.H.1 pulp and paper 0.02 + 2.H.2 food and beverages 1.33",
 "Pakistan BTR1 2024 Table 3 lines 2.H, 2.H.1 and 2.H.2, inventory year 2021",
 "weak",
 "HIGH AND SUBTLE. 2.H.2 food and beverage is largely FERMENTATION CO2 and CH4; Pakistan's sugar and distillery sector is already present in this inventory as bagasse fuel and as cane activity. A 2.H activation must not re-count carbon already in the biomass memo or the waste streams.",
 "audit the pulp/paper and food/beverage boundary against the CRT rows already extracted",
 "PBS CMI output for pulp, paper, food and beverage, plus the boundary decision",
 "NOT IN outputs/completeness.csv, and it is the SECOND-LARGEST official magnitude the national table omits entirely (after 4.D.2's 2.22 Mt). The sector matrix rates it LOW materiality; Pakistan's own 1.35 Mt filing suggests that rating deserves a recheck."),
]


def main():
    comp = [r for r in csv.DictReader(open(COMPLETENESS)) if r["notation_key"] != "E"]
    missing = [(r["code"], r["category"]) for r in comp
               if (r["code"], r["category"]) not in J]
    if missing:
        raise SystemExit(
            "coverage_matrix: %d non-E row(s) of outputs/completeness.csv have no "
            "judgement here - the inventory moved and this matrix is stale:\n  %s"
            % (len(missing), "\n  ".join(map(repr, missing))))
    stale = [k for k in J if k not in {(r["code"], r["category"]) for r in comp}]
    if stale:
        raise SystemExit("coverage_matrix: judgement(s) for row(s) no longer in the "
                         "inventory: %s" % stale)

    out = []
    for r in comp:
        j = J[(r["code"], r["category"])]
        out.append(dict(zip(COLUMNS, [r["code"], r["category"], r["gas"],
                                      r["notation_key"]] + list(j))))
    for row in ABSENT_FROM_COMPLETENESS:
        out.append(dict(zip(COLUMNS, list(row))))

    allowed = {"SUPPORTED", "CONDITIONAL", "SCREENING", "UNESTIMATED/BLOCKED"}
    bad = sorted({r["campaign_status"] for r in out} - allowed)
    if bad:
        raise SystemExit("coverage_matrix: campaign_status outside the closed "
                         "vocabulary: %s" % bad)
    for r in out:
        if r["plausible_magnitude_range"] not in ("unknown",) and not r["magnitude_basis"]:
            raise SystemExit("coverage_matrix: magnitude without a basis: %r" % r)

    with open(OUT, "w", newline="") as fh:
        fh.write("# PakEmis campaign coverage matrix (T-MISS-1), 2026-10-05. One row per\n")
        fh.write("# omitted or partially covered category-gas. Built by\n")
        fh.write("# research_campaign/missing_sources/build_coverage_matrix.py from the\n")
        fh.write("# EXECUTABLE inventory (outputs/completeness.csv, 108 rows, 52 E / 43 NE /\n")
        fh.write("# 8 IE / 4 NO / 1 NA) - never from prose. notation_key is the inventory's\n")
        fh.write("# own IPCC key; campaign_status is a DIFFERENT vocabulary answering a\n")
        fh.write("# different question. Both are carried; neither may be read off the other.\n")
        fh.write("# The last %d rows are IPPU categories that the ippu sector gap matrix\n"
                 % len(ABSENT_FROM_COMPLETENESS))
        fh.write("# carries as NE but that have NO ROW AT ALL in outputs/completeness.csv.\n")
        fh.write("# No completeness percentage is computed: the denominator is unknown.\n")
        w = csv.DictWriter(fh, COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(out)
    print("wrote %s: %d rows (%d from the completeness table, %d absent from it)"
          % (os.path.relpath(OUT, REPO), len(out), len(comp),
             len(ABSENT_FROM_COMPLETENESS)))
    from collections import Counter
    print("  campaign_status:", dict(Counter(r["campaign_status"] for r in out)))
    print("  notation_key:   ", dict(Counter(r["notation_key"] for r in out)))
    known = sum(1 for r in out if r["plausible_magnitude_range"] != "unknown")
    print("  magnitude supported by a source: %d of %d rows" % (known, len(out)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
