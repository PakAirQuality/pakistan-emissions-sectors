# National article and sector technical notes

The current integrated national article is [national_paper.pdf](national_paper.pdf),
with a [review-layout copy](national_submission.pdf),
[technical supplement](national_supplement.pdf), and maintained
[long technical report](national_long_report.pdf). All four describe release
1.0.0rc68 and the July 2015–June 2025 common core.

One Sector Technical Note per sector module of Pakistan's integrated greenhouse-gas and air-pollutant inventory
(TN01–TN10, numbered in `src/pkinv/release.py`; TN08, industrial combustion, is numbered and
reserved), built by `make sector-papers` from `papers/<sector>/paper.tex`. This folder is
the collected output — these are the files to hand to someone. Each note documents one
module of the release named on its first page; the national data-description article
(`paper_national/`, *Earth System Science Data*, in preparation) is the only document that
states the national totals as its own result.

Each paper documents its own sector end to end: data and their provenance, method and the
choices inside it, emission factors, validation against what external estimates exist, results
with their uncertainty and published sensitivities, air pollutants where the sector has a
layer, discussion, limitations and conclusion. Method that spans sectors — the module
contract, the cross-sector closures, the correlated-uncertainty treatment — is in
`paper_national/` and each paper points there rather than repeating it.

<!-- BEGIN GENERATED: papers -->
| TN | PDF | Sector | IPCC | Mt CO₂e | The argument |
|---|---|---|---|---:|---|
| TN01 | `agriculture_paper.pdf` | Agriculture | 3.A-3.H | 223.04 | One nitrogen ledger serving two inventories, with mass-conserving allocation to a 0.05° grid and 114 districts plus a declared residual unit |
| TN02 | `power_paper.pdf` | Electricity | 1A1a + 1A2 | 45.66 | Physical station fuel and rank-specific calorific values, with public/captive and K-Electric boundaries and control assumptions kept explicit |
| TN03 | `transport_paper.pdf` | Road + off-road | 1A3b + 1A4c/1A2 | 41.93 | Product-specific fuel balances with exhaust, evaporation and wear; transferred fleet factors tested separately from the carbon balance |
| TN04 | `waste_paper.pdf` | Waste | 4A, 4C2, 4D1 | 37.45 | Disposal history, wastewater and open burning with shared activity and separate method and treatment alternatives |
| TN05 | `residential_paper.pdf` | Residential fuel | 1A4b | 24.22 | Survey-based household fuel and an explicit diverted-dung alternative; gross appliance emissions, with no assumed outdoor escape fraction |
| TN06 | `fugitives_paper.pdf` | Oil & gas fugitives | 1B2 | 23.50 | The published envelope spans 9.60-24.69 Mt across 280 structural configurations; 5.3% of emissions and 3.1% of national Approach-1 variance |
| TN07 | `ippu_paper.pdf` | Industrial processes | 2A1 | 25.54 | Physical cement, ammonia, steel and lubricant accounts; process carbon separated from fuel, and admitted air-process boundaries recorded explicitly |
| TN09 | `railways_paper.pdf` | Railways | 1A3c + 1A2/1A4c | 0.39 | Operator diesel and traction accounts checked against traffic; national fuel, network allocation and unplaced mass kept distinct |
| TN10 | `aviation_paper.pdf` | Domestic aviation | 1A3a ii | 0.30 | Domestic airport movements and modelled stage fuel, with landing/take-off, cruise and international-bunker boundaries stated separately |
<!-- END GENERATED: papers -->


**These are technical reports, not submissions.** One article is being prepared for
submission from this programme — `paper_national/` — and these nine documents are the
maintained technical specification of the release it describes. They are compiled and test-guarded on every
release, and they carry what a reader needs in order to audit and maintain the inventory:
cell-level source audits, full parameter registers, every structural scenario, extended
historical tables and the complete QA assertion catalogue. The article carries what a reader
needs in order to judge the dataset.

Nine reports for ten sectors: industrial fuel combustion (1A2, 22.58 Mt) was added after
these were written, out of a data-availability audit that found the sector's absence was an
unread table rather than a missing statistic. It is documented in
`src/pkinv/sectors/industry/`, in the completeness table and in `paper_national/` §9. A tenth
report would complete the set, but no tenth *paper* is outstanding — that framing belonged to
the superseded nine-submission plan.

A sector returns to standalone publication only if it gains substantial new scientific
evidence that is not already in the national article — field manure-management data, dissolved
methane measurements, utility leak surveys, observed flight trajectories, plant control-device
records. Repackaging these v1.0 calculations afterwards would not qualify.

Every number printed in these papers is checked against the CSV it came from by
`tests/paper_numbers/`, and every figure must byte-match the output it plots. Both are
build failures rather than warnings, so a paper cannot quietly drift from the engine.
