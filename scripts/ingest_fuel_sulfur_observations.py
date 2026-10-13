#!/usr/bin/env python3
"""Transcribe what the acquired documents actually say about fuel sulfur AS CONSUMED.

WHY THIS TABLE EXISTS. `data/activity/industry/fuel_sulfur_evidence.csv` is the REGISTER the engine
reads: one row per (fuel, period) with the single central the SO2 balance multiplies. Its basis
vocabulary declares five words and the first is `measured_avg` - "consignment analyses of consumed
fuel" - which for the whole life of the air panel no row used. At rc63 brick-kiln coal became the
first, on the three as-fired analyses this file transcribes. The rest are still a ceiling, a
resource range or a mandate date. This file is the other half: the OBSERVATIONS, transcribed one row per (source, date, fuel),
each saying what it measured and what it cannot. The register may then cite an observation instead
of a specification, and where it does not, the disagreement is on the page rather than in nobody's
head.

WHAT EACH ROW IS, and the distinction the whole table turns on - `what_it_measures`:
  as_fired      an analysis of the fuel a specific burner actually burned
  as_delivered  an analysis of a fuel received at a burner that blends it. A component of a
                charge is NOT the charge: the CDPR fixed-chimney kiln is fed a two-to-one
                Hyderabad-Balochistan mixture, so its Hyderabad sample describes an input and
                not a fired fuel, and averaging it in alongside fired fuels understates the
                charge. This row typed itself `as_fired` for one afternoon and pulled the mean
                of the held analyses from 4.64 down to 4.17 - across the booked 4.5, and so
                across the sign of the finding.
  as_sold       an analysis of fuel sampled at the point of sale
  specification a published grade ceiling or target - what the fuel is ALLOWED to be
  resource      a proximate analysis of a seam or field - what is in the GROUND
An `as_fired` observation and a `resource` range are not two measurements of one quantity. The
booked brick-coal central is a `resource` figure.

A READING THIS TABLE ALREADY OVERTURNED ONCE. With only the SAARC audit in hand (2.38 percent)
the obvious conclusion was that the booked 4.5 percent was uncorroborated and high. Acquiring the
CDPR/IGC kiln study put three more as-fired analyses beside it - 5.60, 2.75 and 5.95 - and the
booked central now sits INSIDE the four rather than above them. One observation was not evidence
that a number was wrong; it was one observation. That is why this file records n and date on every
row, and why the conclusion lives in the decision record where it can be re-scored.

NOTHING HERE IS BOOKED BY THIS SCRIPT. It transcribes; adoption is a separate, published verdict in
outputs/pakemis_industrial_coal_decision.csv. Several rows are n=1 and say so.

Usage:  python3 scripts/ingest_fuel_sulfur_observations.py [--check]
Reads:  data/raw/literature/saarc_pakistan_brick_sector_report.pdf
        data/raw/literature/yasin_commercial_hsd_quality.pdf
        data/raw/fuel_specs/parcogunvor_industrial_fuels_spec.html
        data/raw/petroleum_gov/pakistan_brownfield_refinery_policy_2023.pdf
        data/raw/literature/cdpr_igc_energy_efficient_brick_kilns.pdf
        data/raw/pbs/compendium_environment/pbs_compendium_environment_statistics_2020.pdf (HELD)
Writes: data/activity/industry/fuel_sulfur_observations.csv
        data/activity/industry/furnace_oil_grade_mix.csv
"""

from pkinv.assets import asset_path
import csv
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_OBS = asset_path(ROOT, "data", "activity", "industry", "fuel_sulfur_observations.csv")
OUT_MIX = asset_path(ROOT, "data", "activity", "industry", "furnace_oil_grade_mix.csv")
CHECK = "--check" in sys.argv

SAARC = "data/raw/literature/saarc_pakistan_brick_sector_report.pdf"
YASIN = "data/raw/literature/yasin_commercial_hsd_quality.pdf"
PARCO = "data/raw/fuel_specs/parcogunvor_industrial_fuels_spec.html"
POLICY = "data/raw/petroleum_gov/pakistan_brownfield_refinery_policy_2023.pdf"
CDPR = "data/raw/literature/cdpr_igc_energy_efficient_brick_kilns.pdf"
PBS = "data/raw/pbs/compendium_environment/pbs_compendium_environment_statistics_2020.pdf"

OBS_FIELDS = ("observation_id", "fuel", "what_it_measures", "s_pct_central", "s_pct_lo", "s_pct_hi",
              "n_samples", "geography", "observed_date", "applies_to_technology",
              "source", "source_path", "source_page", "what_it_does_not_measure", "note")

OBSERVATIONS = (
    # ---- brick-kiln coal ------------------------------------------------------------------
    {"observation_id": "saarc_2012_btk_lohe_bher_as_fired", "fuel": "Brick-kiln coal",
     "what_it_measures": "as_fired", "s_pct_central": "2.38", "s_pct_lo": "", "s_pct_hi": "",
     "n_samples": "1", "geography": "Lohe Bher, Islamabad Capital Territory",
     "observed_date": "2012-06", "applies_to_technology": "BTK",
     "source": "SAARC Energy Centre, Evaluating Energy Conservation Potential of Brick Kilns in "
               "SAARC Countries - Pakistan Context, Annexure C 'ENERGY AUDIT at BTK', unit "
               "'Sarhad - Punjab Brick, Lohe Bher, Islamabad'. The same audit block prints GCV "
               "23,202 kJ/kg, volatile matter 41.76 %, fixed carbon 32.15 %, moisture 4.85 %",
     "source_path": SAARC, "source_page": "Annexure C (energy-audit performa)",
     "what_it_does_not_measure": "one kiln on one date - it is not a fleet average, carries no "
                                 "dispersion, and is not Punjab: Lohe Bher is in Islamabad Capital "
                                 "Territory, while the register's coal row is scoped to Punjab. It "
                                 "also predates the panel by three fiscal years",
     "note": "THE LOWEST OF THE FOUR AS-FIRED PAKISTANI ANALYSES NOW HELD, and for a short while the "
             "only one. At 2.38 % it is 47 percent below the booked 4.5 % and sits just below the "
             "bottom of that row's own 2.6-10.7 resource range, which is why the band's lo end was "
             "moved to admit it. IT WAS BRIEFLY READ AS EVIDENCE THAT THE BOOKED CENTRAL WAS HIGH; "
             "the three CDPR/IGC analyses acquired straight afterwards (5.60, 2.75, 5.95) put the "
             "booked value inside the observed spread instead. The audit block also prints two "
             "mutually inconsistent dates (start 25 June 2012, completion 1 July 2011) - recorded, "
             "not silently repaired"},

    {"observation_id": "saarc_vsbk_coal_specification", "fuel": "Brick-kiln coal",
     "what_it_measures": "specification", "s_pct_central": "", "s_pct_lo": "1.0", "s_pct_hi": "2.0",
     "n_samples": "", "geography": "Pakistan", "observed_date": "2016",
     "applies_to_technology": "VSBK",
     "source": "SAARC Energy Centre, Pakistan Context, Table 4.3 'Standard Characteristics of "
               "Coal', VSBK specification: sulphur 1-2 %, ash 25-40 %, moisture 1-2 %, volatile "
               "matter 15-20 %, fixed carbon 35-45 %, 8100-9900 Btu/lb",
     "source_path": SAARC, "source_page": "Table 4.3",
     "what_it_does_not_measure": "a TARGET for a technology the Pakistani fleet does not use. VSBK "
                                 "is the vertical shaft kiln; the register's coal row applies to "
                                 "FCBK and zigzag. It states what coal such a kiln SHOULD be fed, "
                                 "never what the BTK fleet was fed",
     "note": "carried because it points the same way as the as-fired audit and not because it is "
             "independent evidence of the fleet: a specification for another technology is weak, "
             "and calling it corroboration would be the error this table exists to prevent"},

    # ---- CDPR/IGC: three lab analyses of the coal actually fired, and the paired stack test ----
    # These are the acquisition gap industry-coal-sulfur names, and they OVERTURN the reading the
    # SAARC row alone supported. Four as-fired analyses now exist and the booked 4.5 percent sits
    # inside them rather than above them.
    {"observation_id": "cdpr_igc_zzk_balochistan_as_fired", "fuel": "Brick-kiln coal",
     "what_it_measures": "as_fired", "s_pct_central": "5.60", "s_pct_lo": "", "s_pct_hi": "",
     "n_samples": "1", "geography": "Punjab (zigzag kiln; coal from Balochistan)",
     "observed_date": "2022", "applies_to_technology": "ZZK",
     "source": "CDPR/IGC, Investigating the Environmental and Economic Benefits of Energy "
               "Efficient Brick Kilns, Table 2 'Ultimate Analysis of Coal Samples at Kilns' "
               "(printed p.17): Balochistan coal N 1.17, C 68.52, S 5.60, H 5.25 percent. Table 1 "
               "gives the same sample's moisture 3.88, ash 13.59, volatile matter 38.80 percent "
               "and GCV 26.78 MJ/kg",
     "source_path": CDPR, "source_page": "Table 2 (printed p.17); Table 1 (p.17)",
     "what_it_does_not_measure": "one batch from one kiln. The authors state explicitly that these "
                                 "'do not reflect the average elemental composition' and 'represent "
                                 "the properties of the particular batch of coal from which we "
                                 "collected each sample'. No analytical basis (as-received or dry) "
                                 "is printed, so a moisture conversion cannot be checked",
     "note": "THE KILN BURNS BALOCHISTAN COAL, NOT PUNJAB COAL. The register's coal_punjab_fields "
             "row is scoped to 'Punjab (Salt Range, Makarwal)'; this Punjab kiln's fuel came from "
             "Balochistan, and the BTK in the same study burned a Hyderabad-Balochistan mixture. "
             "The resource ranges the booked central is built from may be the wrong fields"},

    {"observation_id": "cdpr_igc_hyderabad_as_delivered", "fuel": "Brick-kiln coal",
     "what_it_measures": "as_delivered", "s_pct_central": "2.75", "s_pct_lo": "", "s_pct_hi": "",
     "n_samples": "1", "geography": "Punjab (fixed-chimney kiln; coal from Hyderabad, Sindh)",
     "observed_date": "2022", "applies_to_technology": "BTK",
     "source": "CDPR/IGC, Table 2 (printed p.17): Hyderabad coal N 1.07, C 58.13, S 2.75, H 5.74 "
               "percent; Table 1 moisture 3.69, ash 11.53, VM 30.75 percent, GCV 18.59 MJ/kg. "
               "Hyderabad coal costs Rs. 9,000/t against Balochistan's Rs. 14,000/t, which is why "
               "the BTK mixes them",
     "source_path": CDPR, "source_page": "Table 2 (printed p.17)",
     "what_it_does_not_measure": "WHAT ANY KILN FIRES. The study is explicit that the "
                                 "fixed-chimney kiln burns a two-to-one Hyderabad-Balochistan "
                                 "MIXTURE; this pure sample was collected there but is a component "
                                 "of that charge, not the charge. Also one batch, with no "
                                 "analytical basis printed, and the authors' caution against "
                                 "reading any of these as averages applies",
     "note": "TYPED as_delivered, NOT as_fired, and the distinction changes the sign of the "
             "round's conclusion. Counted as a fired fuel it drags the mean of the held analyses "
             "to 4.17 percent, just below the booked 4.5, and the evidence reads as mildly "
             "supporting a lower central. Excluded, the fired fuels are 2.38, 5.60 and the "
             "mixture, the mean is 4.64, and the evidence reads as mildly supporting a HIGHER "
             "one. Proportioning this sample into the charge its own kiln burns gives "
             "(2 x 2.75 + 5.60)/3 = 3.70 percent, which is what the mixture would assay if it "
             "were made of the two pure samples - the study measured 5.95 for a different batch, "
             "and that gap is unresolved. Price selects sulfur: Hyderabad coal costs Rs. 9,000/t "
             "and assays 2.75, Balochistan costs Rs. 14,000/t and assays 5.60"},

    {"observation_id": "cdpr_igc_btk_mixture_as_fired", "fuel": "Brick-kiln coal",
     "what_it_measures": "as_fired", "s_pct_central": "5.95", "s_pct_lo": "", "s_pct_hi": "",
     "n_samples": "1", "geography": "Punjab (fixed-chimney kiln; two-to-one Hyderabad-Balochistan mixture)",
     "observed_date": "2022", "applies_to_technology": "BTK",
     "source": "CDPR/IGC, Table 2 (printed p.17): the mixture N 0.86, C 50.63, S 5.95, H 4.38 "
               "percent; Table 1 moisture 10.00, ash 21.00, VM 45.90 percent, GCV 23.13 MJ/kg",
     "source_path": CDPR, "source_page": "Table 2 (printed p.17)",
     "what_it_does_not_measure": "the study states the mixture sample came from a DIFFERENT BATCH, "
                                 "and possibly different mines, than the two pure samples - which "
                                 "is why the mixture's sulfur (5.95) exceeds both its components "
                                 "(5.60 and 2.75) instead of lying between them. It is not the "
                                 "proportional sum of the other two rows and must not be read as one",
     "note": "the highest of the four as-fired Pakistani analyses now held"},

    {"observation_id": "cdpr_igc_paired_stack_and_fuel", "fuel": "Brick-kiln coal",
     "what_it_measures": "as_fired", "s_pct_central": "", "s_pct_lo": "", "s_pct_hi": "",
     "n_samples": "2 kilns", "geography": "Punjab", "observed_date": "2022",
     "applies_to_technology": "ZZK;BTK",
     "source": "CDPR/IGC Table 5 'Emission Factors and Emission Rates', fuel-mass-based SO2: ZZK "
               "7.97 g/kg, BTK 299.00 g/kg; CO2 2,836 and 8,453 g/kg. Stack sampling used US EPA "
               "Methods 2 and 17 with O2, stack velocity, temperature and flow recorded - the "
               "terms the Faisalabad campaign omits",
     "source_path": CDPR, "source_page": "Table 5 (printed p.20)",
     "what_it_does_not_measure": "RETENTION, although it is the only paired fuel-sulfur and "
                                 "stack-SO2 measurement on Pakistani kilns and ought to determine "
                                 "it. It cannot, because the two kilns give irreconcilable answers",
     "note": "THE FACTORS FAIL ELEMENTAL CONSERVATION AT ONE OF THE TWO KILNS, which is a finding "
             "about the document and is why nothing here is booked. Complete conversion of the "
             "fuel's own sulfur bounds SO2 at 2 x S: 112 g/kg for the ZZK (5.60 percent S) and 119 "
             "for the BTK (5.95). The ZZK's measured 7.97 g/kg is 7 percent of that bound and "
             "implies 0.93 retention. The BTK's measured 299.00 g/kg is 2.51 TIMES the bound - "
             "impossible from fuel sulfur - and implies a retention of -1.51. The same pattern "
             "holds for carbon: the BTK's 8,453 g CO2/kg is 4.55 times what its 50.63 percent "
             "carbon can yield, while the ZZK's 2,836 is 1.13 times. The two published factors are "
             "internally consistent with each other (EF_e x GCV reproduces EF_m to three figures), "
             "so the error is upstream in the BTK's fuel-consumption or stack-flow term, not in "
             "the normalisation. CONSEQUENCE: the BTK factors cannot be used, and retention stays "
             "unmeasured. The ZZK's 0.93 is a single kiln against a booked 0.25 and rests on a CO2 "
             "closure that is itself 13 percent over its own bound"},

    # ---- high speed diesel ----------------------------------------------------------------
    {"observation_id": "yasin_2012_hsd_multan_as_sold", "fuel": "Gas/Diesel Oil",
     "what_it_measures": "as_sold", "s_pct_central": "0.295", "s_pct_lo": "0.22", "s_pct_hi": "0.46",
     "n_samples": "4 marketers", "geography": "Multan", "observed_date": "2012-01",
     "applies_to_technology": "",
     "source": "Yasin, Bhanger et al., 'Quality of commercial high speed diesel and its "
               "environmental impact', J. Petroleum Technology & Alternative Fuels, accepted 10 "
               "January 2012; sulphur by ASTM D-4294 on an Asooma T-2000 analyser. By marketer: "
               "TOTAL PARCO 0.25-0.29 (0.265 +/- 0.025), PSO 0.27-0.46 (0.354 +/- 0.099), SHELL "
               "0.25-0.29 (0.265 +/- 0.025), CALTEX 0.22-0.37 (0.295 +/- 0.077) wt %",
     "source_path": YASIN, "source_page": "Results and discussion; Table 2 for the specifications",
     "what_it_does_not_measure": "one city, four marketers, one sampling campaign, four fiscal "
                                 "years BEFORE the panel opens. It cannot speak to any year after "
                                 "the January 2017 Euro-II import mandate",
     "note": "TWO SEARCH-ENGINE READINGS OF THIS PAPER WERE WRONG and are recorded so the error is "
             "not repeated: one returned '0.24-0.89 wt %, 10 samples', the other '1.0 % by "
             "weight'. The second is the paper's Table 2 PSI LIMIT (1.0 wt % max) mistaken for a "
             "measurement. The values above are transcribed from the held PDF. NOTE AN "
             "INCONSISTENCY IN THE SOURCE ITSELF: the text states 'the average concentration of "
             "sulphur in our analyzed samples is 0.393 wt%', which is higher than every one of its "
             "own four per-marketer means (0.265, 0.354, 0.265, 0.295). The central above is the "
             "mean of the marketer means; the paper's own 0.393 is carried in this note rather "
             "than chosen, because the source does not reconcile them",
     },

    {"observation_id": "psi_hsd_specification", "fuel": "Gas/Diesel Oil",
     "what_it_measures": "specification", "s_pct_central": "", "s_pct_lo": "", "s_pct_hi": "1.0",
     "n_samples": "", "geography": "Pakistan", "observed_date": "2026-09",
     "applies_to_technology": "",
     "source": "Pakistan Standards Institute high speed diesel specification, 1.0 wt % sulphur "
               "maximum, as printed in Yasin et al. Table 2 and as marketed on the PARCO/Gunvor "
               "industrial fuels page",
     "source_path": PARCO, "source_page": "Industrial fuels / High Speed Diesel",
     "what_it_does_not_measure": "a ceiling, not a content. The as-sold row above measures 0.22-"
                                 "0.46 wt % against this same 1.0 ceiling, so the ceiling overstates "
                                 "the measured fuel by roughly a factor of three",
     "note": "recorded because it is the number the industrial grade is sold against, and because "
             "a reader meeting '1.0 percent' in the literature needs to know it is the limit"},

    # ---- the industrial liquids that currently borrow road-diesel sulfur -------------------
    {"observation_id": "psi_ldo_specification", "fuel": "Light Diesel Oil",
     "what_it_measures": "specification", "s_pct_central": "", "s_pct_lo": "", "s_pct_hi": "1.8",
     "n_samples": "", "geography": "Pakistan", "observed_date": "2026-09",
     "applies_to_technology": "",
     "source": "PARCO/Gunvor industrial fuels page, Light Diesel Oil: sulphur 1.8 % maximum, pour "
               "point 12 C, stated to follow Pakistan Standards Institute standards",
     "source_path": PARCO, "source_page": "Industrial fuels / Light Diesel Oil",
     "what_it_does_not_measure": "a ceiling, and a marketer's page rather than the standard itself; "
                                 "no Pakistani LDO assay was located",
     "note": "THE ROW THE REGISTER SAID DID NOT EXIST. `hsd_pre_euro2`/`hsd_euro2_onward` carry "
             "ind_ldo_boiler and ind_kero_boiler as a declared proxy on the stated grounds that "
             "'no Pakistani LDO or kerosene sulfur specification is held'. One is held now. LDO is "
             "a DIFFERENT product from road diesel with its own ceiling 36 times the 500 ppm the "
             "proxy applies from FY2018 onward"},

    {"observation_id": "psi_furnace_oil_specification", "fuel": "Residual Fuel Oil",
     "what_it_measures": "specification", "s_pct_central": "", "s_pct_lo": "", "s_pct_hi": "3.5",
     "n_samples": "", "geography": "Pakistan", "observed_date": "2026-09",
     "applies_to_technology": "",
     "source": "PARCO/Gunvor industrial fuels page, furnace oil (HSFO): sulphur 3.5 % maximum, "
               "kinematic viscosity 180 cSt at 50 C, gross calorific value 18,200 BTU/lb",
     "source_path": PARCO, "source_page": "Industrial fuels / Furnace Oil",
     "what_it_does_not_measure": "a ceiling. No consignment assay of Pakistani industrial furnace "
                                 "oil was located, which is the acquisition fo_hsfo_grade_mix names "
                                 "in its own note and which remains open",
     "note": "corroborates the 3.5 % ceiling the register already cites from the PBS Compendium, "
             "from a second and current source"},

    {"observation_id": "refinery_policy_2023_domestic_diesel_grades", "fuel": "Gas/Diesel Oil",
     "what_it_measures": "specification", "s_pct_central": "", "s_pct_lo": "", "s_pct_hi": "",
     "n_samples": "5 refineries", "geography": "Pakistan", "observed_date": "2023",
     "applies_to_technology": "",
     "source": "Pakistan Oil Refining Policy for Upgradation of Existing Refineries 2023, the "
               "current-versus-post-upgrade capacity table. Diesel grade by refinery, with diesel "
               "capacity in tons/day: PARCO Euro-III 5,600; ARL Euro-III 2,071; NRL Euro-V 3,273; "
               "PRL none-stated 1,793; CPL none-stated 8,500. The table's own footnote: 'Current "
               "production by refineries in Euro V compliant is in terms of sulphur content only'",
     "source_path": POLICY, "source_page": "section 6.1.1 capacity table",
     "what_it_does_not_measure": "production capacity and permitted grade, not the sulfur of any "
                                 "litre sold, and a 2023 snapshot rather than a series. It says "
                                 "nothing about imports, which supply a large share of the pool",
     "note": "⚠ BEARS ON ITEM 4 (road diesel), WHICH THIS ROUND DOES NOT CHANGE. On the table's own "
             "capacity numbers, 10,293 of 21,237 tons/day of domestic diesel capacity - 48 percent "
             "- carried NO stated Euro grade in 2023, and a further 7,671 t/d was Euro-III "
             "(350 ppm). The road-fuel regime in data/activity/transport/fuel_sulfur_by_year.csv "
             "books a 500 ppm central from FY2018 onward. Transcribed here and left unbooked: "
             "changing the road regime is item 4's business and would move transport, railways and "
             "industrial HSD together"},
)

# PBS Compendium on Environment Statistics 2020, Table B-10 'Import of Petroleum Products',
# quantity in TONNES (the first of the three lines each product prints; the second is TOE and the
# third is value in million US dollars). Fiscal years as the table labels them.
GRADE_MIX = (
    # (fiscal_end_year, period_id, hsfo_tonnes, lsfo_tonnes)
    (2015, "",           6701000,      None),   # FY2014-15: before the panel; LSFO not printed
    (2016, "FY2015-16",  5219995,   903147),
    (2017, "FY2016-17",  5869157,   663889),
    (2018, "FY2017-18",  3791786,   455588),
    (2019, "FY2018-19",   552239,        0),
)
MIX_FIELDS = ("fiscal_end_year", "period_id", "hsfo_tonnes", "lsfo_tonnes", "hsfo_share",
              "grade_weighted_s_pct", "source", "source_path", "source_page", "note")
# the grades' own ceilings, which is all that is held; see psi_furnace_oil_specification
S_HSFO, S_LSFO = 3.5, 1.0


def mix_rows():
    out = []
    for fy, period, hsfo, lsfo in GRADE_MIX:
        share = weighted = ""
        if lsfo is not None and (hsfo + lsfo) > 0:
            f = hsfo / float(hsfo + lsfo)
            share, weighted = "%.6f" % f, "%.4f" % (f * S_HSFO + (1.0 - f) * S_LSFO)
        out.append({
            "fiscal_end_year": fy, "period_id": period, "hsfo_tonnes": hsfo,
            "lsfo_tonnes": "" if lsfo is None else lsfo,
            "hsfo_share": share, "grade_weighted_s_pct": weighted,
            "source": "PBS Compendium on Environment Statistics 2020, Table B-10 'Import of "
                      "Petroleum Products', quantity in tonnes",
            "source_path": PBS, "source_page": "161",
            "note": "IMPORTS, NOT CONSUMPTION, and the table stops at FY2018-19 - four of the nine "
                    "panel years. grade_weighted_s_pct applies the two grades' CEILINGS (HSFO 3.5, "
                    "LSFO 1.0) to the tonnage split, so it is an upper envelope of the import "
                    "pool's sulfur, not an assay. Domestic refinery output is not in this table "
                    "and furnace-oil imports collapse after FY2018-19, so this series must not be "
                    "extrapolated forward"
                    if period else
                    "FY2014-15 is outside the panel and is carried only so the trend into "
                    "FY2015-16 is visible. LSFO is not printed for this year, so no share is "
                    "computed - an absence, never a zero",
        })
    return out


def write(path, fields, rows, banner):
    with open(path, "w", newline="", encoding="utf-8") as h:
        for line in banner:
            h.write("# %s\n" % line)
        w = csv.DictWriter(h, fieldnames=list(fields), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def main():
    missing = [p for p in (SAARC, YASIN, PARCO, POLICY, PBS, CDPR)
               if not os.path.exists(asset_path(ROOT, p))]
    if missing:
        raise SystemExit("not held: %s (run scripts/fetch_fuel_sulfur_evidence.py, and "
                         "scripts/holdings.py first)" % ", ".join(missing))
    obs = [dict(r) for r in OBSERVATIONS]
    mix = mix_rows()
    if CHECK:
        for path, fields, rows in ((OUT_OBS, OBS_FIELDS, obs), (OUT_MIX, MIX_FIELDS, mix)):
            held = [r for r in csv.DictReader(
                l for l in open(path, encoding="utf-8") if not l.startswith("#"))]
            if len(held) != len(rows):
                raise SystemExit("%s: %d rows held, %d would be written" % (path, len(held), len(rows)))
        print("fuel sulfur observations: unchanged")
        return 0
    write(OUT_OBS, OBS_FIELDS, obs, (
        "FUEL SULFUR OBSERVATIONS: what the acquired documents say about sulfur AS CONSUMED,",
        "beside the register (fuel_sulfur_evidence.csv) which books one central per fuel-period.",
        "what_it_measures separates as_fired / as_sold / specification / resource - an as-fired",
        "analysis and a resource range are NOT two measurements of one quantity. Nothing here is",
        "booked; adoption is a published verdict in outputs/pakemis_industrial_coal_decision.csv.",
        "Written by scripts/ingest_fuel_sulfur_observations.py.",
    ))
    write(OUT_MIX, MIX_FIELDS, mix, (
        "FURNACE OIL IMPORT GRADE MIX: high- against low-sulphur furnace oil imports by fiscal",
        "year, PBS Compendium on Environment Statistics 2020 Table B-10 (p.161), a HELD document.",
        "The register's fo_hsfo_grade_mix row cites this page for the grade trajectory and then",
        "applies ONE flat central to all nine years; this table is the trajectory it cites.",
        "IMPORTS ARE NOT CONSUMPTION and the table ends at FY2018-19. Written by",
        "scripts/ingest_fuel_sulfur_observations.py.",
    ))
    print("fuel sulfur observations -> %s (%d rows)" % (os.path.relpath(OUT_OBS, ROOT), len(obs)))
    for r in obs:
        print("  %-42s %-16s %s" % (r["observation_id"][:42], r["what_it_measures"],
                                    r["s_pct_central"] or "%s-%s" % (r["s_pct_lo"] or "?", r["s_pct_hi"] or "?")))
    print("furnace oil grade mix -> %s (%d rows)" % (os.path.relpath(OUT_MIX, ROOT), len(mix)))
    for r in mix:
        print("  %-10s HSFO %-10s LSFO %-9s share %-9s weighted S %s"
              % (r["period_id"] or "(pre-panel)", r["hsfo_tonnes"], r["lsfo_tonnes"],
                 r["hsfo_share"] or "-", r["grade_weighted_s_pct"] or "-"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
