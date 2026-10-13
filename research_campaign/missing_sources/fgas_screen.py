"""T-MISS-2: what a defensible Pakistani F-gas estimate would need, and a first
STOCK-SIDE calculation that tests the three numbers currently in circulation.

READ-ONLY on the repository; every output goes to this directory. Writes:
  fgas.csv                      the input-requirements ledger: every input an IPCC
                                bank/emissions method needs, its held status, its
                                held value, its source, and what it blocks
  fgas_stock_screen.csv         a NEW stock-side bank screen (SCREENING grade)
  fgas_benchmark_consistency.csv three consistency tests of EDGAR's 11.54 Mt

THE RULE THAT GOVERNS ALL OF IT. Refrigerant consumption and refrigerant imports
are NOT annual emissions. Gas entering equipment leaks over the equipment's life,
so in a market whose bank is still filling, annual emissions are far BELOW annual
supply, and in a mature market they converge on it. Pakistan's market is filling.
Every number below is therefore typed as supply, as stock, or as emissions, and
the three are never added or averaged.

WHAT IS ALREADY IN THE REPOSITORY (verified, not assumed, 2026-10-05):
  - a mass-conserving bank kernel with a per-year closure assertion
    (src/pkinv/sectors/ippu/material_flows.fgas_bank_step)
  - a species x application bank run over 143 strata-years
    (outputs/ippu_hfc_species_bank.csv: 5.854 Mt CO2e AR5 for 2024)
  - a one-stratum CO2e bounded bank (4.42 Mt, bracket 2.3-6.2)
  - the UNEP Article-7 consumption control series, with 2021-23 typed `missing`
  - UN Comtrade HS-2022 bulk and mixture import lines, 2022-2024
  - the UNDP RAC inventory's Table 13 species imports, 2012-2019
  - IPCC 2006 Vol 3 Ch 7 itself (data/raw/ipcc/ipcc2006_V3_7_Ch7_ODS_Substitutes.pdf)
  - HIES design-weighted household ownership of HFC-bearing appliances, the
    equipment-STOCK indicator
  - a STOCK-SIDE household bank band already built on it, FY2015-16..FY2023-24
    (scripts/build_hfc_bank_series.py -> outputs/pakemis_hfc_bank_series.csv;
    FY2023-24 household floor 0.191-2.423 Mt CO2e)
So 2.F is not an unstarted category and this screen is NOT the first stock-side
calculation. CORRECTION LOGGED: this worker first concluded it was, having
grepped only src/pkinv/sectors/ippu/ and missed a scripts/ phase that run_all
registers. The shipped band and this screen are two independent parameterisations
of the same method, and they agree.

WHAT IS NEW HERE, STATED NARROWLY. The shipped band compares household EMISSIONS
against the supply lanes' emissions and reads the comparison one way ("the
household equipment bank cannot absorb that supply"). This file compares the two
banks in TONNES OF REFRIGERANT, per application, which is what separates a
stock-coverage gap from a leak-rate gap - and for refrigeration the two banks
agree to 1.3x while the emissions differ 107x, which the emissions-only
comparison cannot see. It also adds a central alongside the band, an explicit
AC-fitment discount on the mobile lane, and three consistency tests of EDGAR.

SCOPE OF THE STOCK LANE, DECLARED: HOUSEHOLD equipment only. HIES asks
households. Commercial and industrial refrigeration, cold stores, chillers,
transport refrigeration and non-household vehicles are OUTSIDE it, so the stock
lane is a LOWER BOUND on the national bank and must never be read as a national
total. It is published as a bound precisely because it is one.
"""
import csv
import os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
GWP_AR5 = {"HFC-134a": 1300.0, "HFC-32": 677.0, "HFC-125": 3170.0,
           "HFC-143a": 4800.0, "HFC-23": 12400.0, "HFC-152a": 138.0,
           "SF6": 23500.0}
# blend GWPs at published ASHRAE mass shares, the same arithmetic hfc_bank.py uses
GWP_R410A = 0.50 * GWP_AR5["HFC-32"] + 0.50 * GWP_AR5["HFC-125"]   # 1923.5


def _rows(path, skip_comments=True):
    with open(os.path.join(REPO, path)) as fh:
        lines = [l for l in fh if not (skip_comments and l.startswith("#"))]
    return list(csv.DictReader(lines))


# ---------------------------------------------------------------- lane readings
def species_bank():
    """The held supply-side bank, by year and by 2024 application."""
    rows = _rows("outputs/ippu_hfc_species_bank.csv")
    by_year, app_2024, bank_2024_t = defaultdict(float), defaultdict(float), 0.0
    for r in rows:
        by_year[int(r["year"])] += float(r["emissions_Mt_co2e_AR5"])
        if r["year"] == "2024":
            app_2024[r["application"]] += float(r["emissions_Mt_co2e_AR5"])
            bank_2024_t += float(r["bank_end_t"])
    # strata that simply STOP: present in some year, absent in 2024
    strata_years = defaultdict(set)
    bank_at_last = {}
    for r in rows:
        key = (r["species"], r["application"])
        strata_years[key].add(int(r["year"]))
        if int(r["year"]) == max(strata_years[key]):
            bank_at_last[key] = (int(r["year"]), float(r["bank_end_t"]),
                                 float(r["bank_end_t"]) * _gwp(r["species"]) / 1e6)
    truncated = {k: v for k, v in bank_at_last.items()
                 if v[0] < 2024 and v[1] > 0}
    return by_year, app_2024, bank_2024_t, truncated


def _gwp(species):
    if species in GWP_AR5:
        return GWP_AR5[species]
    blends = {"R-410A": {"HFC-32": .50, "HFC-125": .50},
              "R-404A": {"HFC-125": .44, "HFC-143a": .52, "HFC-134a": .04},
              "R-407C": {"HFC-32": .23, "HFC-125": .25, "HFC-134a": .52},
              "R-507A": {"HFC-125": .50, "HFC-143a": .50},
              "R-417A": {"HFC-125": .466, "HFC-134a": .500},
              "R-508B": {"HFC-23": .46}}
    return sum(GWP_AR5[c] * s for c, s in blends.get(species, {}).items())


def unep_supply():
    out = {}
    for r in _rows("data/sectors/ippu/activity/hfc_consumption_controls.csv"):
        if r["status"] == "reported":
            out[int(r["calendar_year"])] = float(r["value_t_co2e"]) / 1e6
    return out


def edgar_fgas():
    """EDGAR 2025 booklet Pakistan F-gases, GWP_100_AR5, sector Processes."""
    import openpyxl
    wb = openpyxl.load_workbook(
        os.path.join(REPO, "sources/EDGAR/EDGAR_2025_GHG_booklet_2025.xlsx"),
        read_only=True, data_only=True)
    ws = wb["GHG_by_sector_and_country"]
    rows = list(ws.iter_rows(values_only=True))
    years = rows[0][4:]
    for r in rows:
        if r[0] == "GWP_100_AR5_F-gases" and r[3] == "Pakistan":
            return {y: v for y, v in zip(years, r[4:]) if v is not None}, r[1]
    raise SystemExit("EDGAR: no Pakistan F-gas row")


def hies_stock():
    out = {}
    for r in _rows("data/sectors/ippu/activity/hies_appliance_ownership.csv"):
        if r["region"] == "" and r["survey"] == "HIES 2024-25":
            if r["weighted_units_owned"]:
                out[r["appliance"]] = float(r["weighted_units_owned"])
    return out


# ------------------------------------------------- the stock-side bank screen
# IPCC 2006 Vol 3 Ch 7 TABLE 7.9 (held: data/raw/ipcc/ipcc2006_V3_7_Ch7_ODS_Substitutes.pdf
# p.7.52) gives charge M, lifetime d, initial-emission k and operation-emission x
# per sub-application. Footnote 2,3: "Lower value for developed countries and higher
# value for developing countries" - so Pakistan sits at the HIGH end of lifetime and
# initial emission. Footnote 4: the 0% recovery threshold "highlights that there is
# no recovery in some countries", which matches UNEP's record of no HFC licensing
# system in Pakistan.
#
# Each lane below states: the Table 7.9 sub-application it is priced as, the charge
# bracket, and the HFC SHARE of the installed base. The share is NOT an IPCC default
# and is NOT held for Pakistan - it is this screen's declared assumption, bracketed
# wide, and it is the single largest uncertainty here. The lower end of each share
# is what the non-HFC alternative implies: isobutane R-600a in domestic
# refrigeration (zero GWP) and HCFC-22 in older room air conditioners (an ODS
# controlled under the Montreal Protocol and NOT a UNFCCC F-gas).
STOCK_LANES = [
    dict(lane="domestic refrigeration (refrigerators)", appliance="refrigerator",
         ipcc_subapplication="Domestic Refrigeration",
         charge_kg=(0.05, 0.15, 0.50), charge_basis="Table 7.9 M range 0.05-0.5 kg, used whole",
         op_loss=(0.001, 0.003, 0.005), op_loss_basis="Table 7.9 x = 0.1-0.5 %/yr",
         species="HFC-134a", hfc_share=(0.50, 0.75, 0.95),
         share_basis="DECLARED, not held: balance is R-600a isobutane (zero GWP), which has taken a growing share of new Pakistani domestic units"),
    dict(lane="domestic refrigeration (deep freezers)", appliance="deep_freezer",
         ipcc_subapplication="Domestic Refrigeration",
         charge_kg=(0.10, 0.25, 0.50), charge_basis="Table 7.9 M range 0.05-0.5 kg, narrowed upward: a chest freezer is the large end of the domestic class",
         op_loss=(0.001, 0.003, 0.005), op_loss_basis="Table 7.9 x = 0.1-0.5 %/yr",
         species="HFC-134a", hfc_share=(0.50, 0.75, 0.95),
         share_basis="DECLARED, as refrigerators"),
    dict(lane="residential air conditioning (room units)", appliance="air_conditioner",
         ipcc_subapplication="Residential and Commercial A/C, including Heat Pumps",
         charge_kg=(0.60, 1.00, 1.50), charge_basis="Table 7.9 M range is 0.5-100 kg; DECLARED NARROWING to room split/window units, which is what a household owns - the 100 kg end is central plant",
         op_loss=(0.01, 0.055, 0.10), op_loss_basis="Table 7.9 x = 1-10 %/yr, whole range; central is the midpoint",
         species="R-410A", hfc_share=(0.30, 0.55, 0.80),
         share_basis="DECLARED, not held: the balance is HCFC-22, which dominated the older installed base and is Montreal-controlled, NOT a UNFCCC F-gas. R-32 units (GWP 677) are displacing R-410A in new sales, which would LOWER the CO2e of this lane."),
    dict(lane="mobile air conditioning (household cars)", appliance="motor_car",
         ipcc_subapplication="Mobile A/C",
         charge_kg=(0.50, 0.70, 1.50), charge_basis="Table 7.9 M range 0.5-1.5 kg, used whole",
         op_loss=(0.10, 0.15, 0.20), op_loss_basis="Table 7.9 x = 10-20 %/yr, whole range",
         species="HFC-134a", hfc_share=(0.50, 0.75, 0.95),
         share_basis="DECLARED, not held: this share does double duty here - it is the product of AC FITMENT (a large part of the Pakistani household fleet is small cars that may be unfitted) and of the HFC-134a share of what is fitted (HFO-1234yf is not documented in Pakistan)"),
]


def stock_screen():
    units = hies_stock()
    rows, totals = [], {"low": 0.0, "central": 0.0, "high": 0.0}
    bank_t = {"low": 0.0, "central": 0.0, "high": 0.0}
    for lane in STOCK_LANES:
        n = units[lane["appliance"]]
        gwp = GWP_R410A if lane["species"] == "R-410A" else GWP_AR5[lane["species"]]
        vals = {}
        for i, end in enumerate(("low", "central", "high")):
            charge_t = n * lane["charge_kg"][i] / 1000.0 * lane["hfc_share"][i]
            em_t = charge_t * lane["op_loss"][i]
            vals[end] = (charge_t, em_t, em_t * gwp / 1e6)
            totals[end] += em_t * gwp / 1e6
            bank_t[end] += charge_t
        rows.append({
            "lane": lane["lane"],
            "ipcc_subapplication_table_7_9": lane["ipcc_subapplication"],
            "units_in_service": "%.0f" % n,
            "units_source": "PBS HIES 2024-25 design-weighted units owned (data/sectors/ippu/activity/hies_appliance_ownership.csv); 'validation only' Stata release, 30,123 of 35,792 designed households; NO published weighted household count exists to verify the frame against",
            "species_priced": lane["species"],
            "gwp_ar5": "%.1f" % gwp,
            "charge_kg_low_central_high": "%.2f / %.2f / %.2f" % lane["charge_kg"],
            "charge_basis": lane["charge_basis"],
            "hfc_share_low_central_high": "%.2f / %.2f / %.2f" % lane["hfc_share"],
            "hfc_share_basis": lane["share_basis"],
            "operating_loss_low_central_high": "%.4f / %.4f / %.4f" % lane["op_loss"],
            "operating_loss_basis": lane["op_loss_basis"],
            "installed_bank_t_low": "%.1f" % vals["low"][0],
            "installed_bank_t_central": "%.1f" % vals["central"][0],
            "installed_bank_t_high": "%.1f" % vals["high"][0],
            "emissions_Mt_co2e_low": "%.4f" % vals["low"][2],
            "emissions_Mt_co2e_central": "%.4f" % vals["central"][2],
            "emissions_Mt_co2e_high": "%.4f" % vals["high"][2],
        })
    return rows, totals, bank_t


def main():
    by_year, app_2024, bank_2024_t, truncated = species_bank()
    unep = unep_supply()
    edgar, edgar_sector = edgar_fgas()
    srows, stotals, sbank = stock_screen()

    # ---- consistency tests of the external benchmark
    tests = []
    # T1: what bank does EDGAR's 2024 number require?
    #     emissions = bank x operating loss, so bank = emissions / loss
    gwp_mix = 1923.5   # priced at R-410A, the dominant AC blend; see note
    for loss, label in ((0.10, "10 %/yr"), (0.055, "5.5 %/yr (Table 7.9 A/C midpoint)")):
        implied_t = edgar[2024] * 1e6 / gwp_mix / loss
        tests.append(dict(
            test="T1 implied bank behind EDGAR 2024",
            assumption="EDGAR 11.54 Mt CO2e priced at the R-410A AR5 GWP %.1f and an operating loss of %s" % (gwp_mix, label),
            result_value="%.0f t of refrigerant in service" % implied_t,
            compare_against="the held supply-side bank ends 2024 at %.0f t; this screen's household stock lane is %.0f-%.0f t (central %.0f t)"
                            % (bank_2024_t, sbank["low"], sbank["high"], sbank["central"]),
            ratio="EDGAR's implied bank is %.1fx the supply-side bank and %.1fx the household stock-screen central"
                  % (implied_t / bank_2024_t, implied_t / sbank["central"]),
            reading="A national refrigerant bank of this size is not reachable from either an observed equipment stock or an observed import history. The gap is too large to be a parameter choice."))
    # T2: cumulative emissions must not exceed cumulative supply
    cum_edgar = sum(v for y, v in edgar.items() if 1990 <= y <= 2024)
    cum_unep_reported = sum(unep[y] for y in sorted(unep) if y <= 2024)
    tests.append(dict(
        test="T2 cumulative emissions against cumulative reported supply",
        assumption="a bank cannot emit gas that was never supplied: cumulative emissions <= cumulative supply, for any leak rate and any bank age",
        result_value="EDGAR cumulative F-gas emissions 1990-2024 = %.1f Mt CO2e" % cum_edgar,
        compare_against="Pakistan's REPORTED Article-7 Annex-F consumption totals %.1f Mt CO2e across the four reported years at or before 2024 (2019, 2020, 2024); 2021-2023 are publicly unreported, and the one-stratum bounded bank's interpolated 2019-2024 supply sums to about 55.6 Mt"
                        % cum_unep_reported,
        ratio="EDGAR's cumulative emissions are %.1fx the whole interpolated Article-7-era supply" % (cum_edgar / 55.6),
        reading="NOT A CONTRADICTION ON ITS OWN - Article-7 reporting begins in 2019 and HFC supply before it is simply unreported, so a pre-2019 supply history could in principle carry the difference. What it does establish is that EDGAR's series implies a Pakistani HFC supply history several times larger than anything Pakistan has ever reported, and that difference is not evidenced anywhere in this repository."))
    # T3: is EDGAR's Pakistan series a model or an observation?
    diffs = [edgar[y] - edgar[y - 1] for y in range(2019, 2025)]
    tests.append(dict(
        test="T3 shape of the EDGAR series",
        assumption="an observation-fed series moves irregularly; a trend extrapolation moves by a near-constant increment",
        result_value="year-on-year increments 2019-2024: " + ", ".join("%+.4f" % d for d in diffs),
        compare_against="the same series is 0.994 Mt in 1990 and FALLS to 0.453 Mt by 1995, before HFCs were in general use anywhere in South Asia",
        ratio="the 2020-2024 increments span %.4f to %.4f Mt, a spread of %.1f%% about their mean"
              % (min(diffs[1:]), max(diffs[1:]),
                 100 * (max(diffs[1:]) - min(diffs[1:])) / (sum(diffs[1:]) / len(diffs[1:]))),
        reading="HYPOTHESIS, NOT A FINDING ABOUT EDGAR'S INTERNALS: a series whose last five increments agree to within ~3 percent, and which is non-zero and declining in the early 1990s, has the shape of an extrapolation rather than of country data. It is used here as a SCOPE SCREEN and nothing more. Confirming it would mean reading EDGAR's own F-gas documentation, which this worker did not do."))
    # T4: application by application, supply-side bank against stock-side screen.
    #     Published per application rather than as one national ratio, because the
    #     national ratio hides the one comparison that isolates the decisive parameter.
    lane_bank_t, lane_em = {}, {}
    for r in srows:
        if r["lane"].startswith("TOTAL"):
            continue
        key = ("refrigeration" if "refrigeration" in r["lane"]
               else "stationary AC" if "air conditioning (room" in r["lane"]
               else "mobile AC")
        lane_bank_t[key] = lane_bank_t.get(key, 0.0) + float(r["installed_bank_t_central"])
        for end in ("low", "central", "high"):
            lane_em.setdefault(key, {}).setdefault(end, 0.0)
            lane_em[key][end] += float(r["emissions_Mt_co2e_" + end])
    supply_bank_t = defaultdict(float)
    for r in _rows("outputs/ippu_hfc_species_bank.csv"):
        if r["year"] == "2024":
            supply_bank_t[r["application"]] += float(r["bank_end_t"])
    readings = {
"refrigeration": "THE DECISIVE COMPARISON. The two banks agree to within a factor of 1.3 - an import accumulation since 2012 and a 2024-25 household equipment count land on almost the same mass of refrigerant - while the EMISSIONS differ by about two orders of magnitude. With the bank size agreed, only one thing can cause that: the leak rate. The supply-side bank prices this stratum at 8 %/yr; IPCC Table 7.9 gives DOMESTIC refrigeration 0.1-0.5 %/yr and only the commercial sub-applications reach 8 %. A domestic/commercial split of this stratum - which nobody holds - decides roughly 1.2 Mt CO2e, and it is the largest single lever in the whole 2.F question.",
"stationary AC": "The supply-side bank is 3.7x the household stock bank. Both of those are expected to differ: HIES counts HOUSEHOLD room units only, and offices, shops, hotels and institutions hold a large AC stock outside it, while this screen's 55 percent central HFC share (the balance HCFC-22) pushes its own bank down. The emissions ratio (9.0x) is close to the bank ratio, so unlike refrigeration the gap here is about STOCK COVERAGE and species share, not about the leak rate: 6 %/yr sits comfortably inside Table 7.9's 1-10 percent for this sub-application.",
"mobile AC": "The supply-side bank is 2.9x the household stock bank, and the emissions ratio (5.1x) is of the same order, so again this is a coverage question rather than a parameter question. HIES counts household cars; taxis, ride-hailing, company and government fleets, light commercial vehicles and buses are outside it, and the registered 2022 fleet of 2,754,229 cars is itself only the 4W1 class. 15 %/yr is inside Table 7.9's 10-20 percent for mobile A/C.",
}
    for app in ("refrigeration", "stationary AC", "mobile AC"):
        sb, hb = supply_bank_t[app], lane_bank_t[app]
        tests.append(dict(
            test="T4 %s: supply-side bank against stock-side screen" % app,
            assumption="the two are independent - one accumulates imports from an empty 2012, the other counts equipment in service in 2024-25; the stock lane is HOUSEHOLDS ONLY and is a lower bound",
            result_value="bank: supply-side %.0f t, stock-side household central %.0f t. emissions: supply-side %.4f Mt CO2e, stock-side %.4f-%.4f Mt (central %.4f)"
                         % (sb, hb, app_2024[app], lane_em[app]["low"],
                            lane_em[app]["high"], lane_em[app]["central"]),
            compare_against="supply-side operating loss applied to this stratum, against IPCC Table 7.9 for the matching sub-application",
            ratio="bank ratio %.1fx; emissions ratio %.1fx" % (sb / hb, app_2024[app] / lane_em[app]["central"]),
            reading=readings[app]))

    # ---- fgas.csv: the input requirements ledger
    req = [
# input, role, status, held_value, source_or_route, blocks, note
("individual HFC species", "gas identity", "HELD (partial)",
 "12 species and blends priced in the bank: HFC-23, 32, 125, 134a, 143a, 152a and R-404A, R-407C, R-410A, R-417A, R-507A, R-508B",
 "UNDP RAC inventory Table 13 (2012-2019) + UN Comtrade HS-2022 lines 2903.41/42/45/49 and 3827 (2022-2024)",
 "nothing - this is met",
 "HS 3827 is 'mixtures containing HFCs' and does NOT resolve to species; the species split inside it is assumed from the UNDP structure. Pakistan's own CRT reports ONE species, HFC-23, for all of 2.F."),
("blend compositions", "GWP of a mixture", "HELD",
 "six blends at published ASHRAE mass shares (R-410A 50/50 HFC-32/125 -> AR5 GWP 1923.5, etc.)",
 "ASHRAE designations, fixed by definition; implemented in src/pkinv/sectors/ippu/hfc_bank.py",
 "nothing",
 "Quoting a blend at one component's GWP is a known 17-percent class of error; the implementation avoids it."),
("non-HFC refrigerants in the same equipment", "scope boundary", "NOT HELD",
 "no Pakistani split of the installed base between HFC, HCFC-22 and hydrocarbon (R-600a/R-290)",
 "National Ozone Unit HCFC phase-out management plan (HPMP) reporting; UNEP Ozone Secretariat Article-7 HCFC data (public)",
 "the HFC SHARE of every stock lane in fgas_stock_screen.csv - the single largest uncertainty in this file",
 "CRITICAL AND UNDER-APPRECIATED: HCFC-22 is Montreal-controlled and is NOT a UNFCCC F-gas, and R-600a has GWP ~0. A room-AC base that is half R-22 halves this category. Pakistan is an Article 5 party with an active HPMP, so its HCFC consumption IS publicly reported - this is an acquirable input, not an absent one."),
("equipment and use categories", "bank strata", "HELD (partial)",
 "five applications carry rows: refrigeration, stationary AC, mobile AC, aerosol, fire protection. FOAM has zero rows although the import contract's vocabulary includes it; solvents have none.",
 "the UNDP report's own structure, DECLARED and never measured (application_split_basis column)",
 "2.F.2 foam and 2.F.5 solvents entirely; the domestic/commercial split inside 'refrigeration'",
 "The application split is the UNDP report's structure, e.g. HFC-134a declared 70 percent mobile / 30 percent refrigeration. A declared split is not a measured one and the file says so."),
("domestic vs commercial split of refrigeration", "LEAK RATE SELECTION", "NOT HELD",
 "the bank prices the whole refrigeration stratum at one operating loss of 8 %/yr",
 "UNDP RAC inventory sub-application detail; National Ozone Unit RAC survey",
 "the difference between about 0.08 and about 1.29 Mt CO2e in 2024 for that stratum alone",
 "THE DECISIVE MISSING INPUT FOR THE ANSWER'S SIZE. IPCC Table 7.9 gives domestic refrigeration 0.1-0.5 %/yr and medium/large commercial 10-35 %/yr. One stratum cannot carry both. 8 %/yr is admissible for commercial and is 16-80x too high for domestic."),
("equipment STOCKS in service", "the bank itself", "HELD AND USED",
 "HIES 2024-25 design-weighted units: 23,845,872 refrigerators, 2,182,475 deep freezers, 5,701,612 room air conditioners, 3,033,324 household cars (air coolers are EVAPORATIVE and carry no refrigerant)",
 "PBS HIES 2024-25 and 2018-19 Stata microdata Section 7, ingested as data/sectors/ippu/activity/hies_appliance_ownership.csv and already consumed by scripts/build_hfc_bank_series.py -> outputs/pakemis_hfc_bank_series.csv",
 "nothing for households; everything for the rest of the bank (next row)",
 "The stock side is BUILT: a household band of 0.191-2.423 Mt CO2e for FY2023-24, outside every total. fgas_stock_screen.csv in this directory is a second, independently parameterised run of the same method and lands inside that band (0.119-2.520, central 0.654), which is mutual corroboration between two parameter sets. Caveats on the input: households only; PBS 'validation only' release (30,123 of 35,792 designed households); no published weighted household count to verify the 40.1 M frame against."),
("commercial, industrial and transport equipment stocks", "the rest of the bank", "NOT HELD",
 "none: no cold-store, supermarket, chiller, industrial-process or refrigerated-transport inventory",
 "National Ozone Unit RAC sector survey (the UNDP 2021 report was built from one); provincial food-authority cold-store registers",
 "converting the household stock screen from a lower bound into a national stock estimate",
 "Medium and large commercial refrigeration carries 50-2000 kg per system at 10-35 %/yr - the highest-leaking class in Table 7.9 and entirely unobserved here."),
("bulk imports and exports by species", "supply flow", "HELD (partial)",
 "2012-2019 by species (UNDP Table 13); 2022-2024 from Comtrade; 2020-2021 a typed geometric bridge",
 "UNDP Table 13; UN Comtrade public API; the bridge is declared `modelled` per row",
 "nothing for the bulk channel",
 "Comtrade years before 2022 file under HS-2017's 2903.39 and are NOT comparable, which is why the extract starts in 2022."),
("PRE-CHARGED EQUIPMENT imports and exports", "supply flow", "NOT HELD",
 "none",
 "FBR Customs HS 8415 (air-conditioning machines) and 8418 (refrigerators and freezers) import quantities, plus a charge-per-unit schedule; or the National Ozone Unit's own licensing records. Request REQ-NOU-01 names it and is DRAFTED NOT SENT.",
 "THE ONE UNMET CRITERION on the 2.F activation gate in data/shared/parameters/scope_registry.csv",
 "Gas inside imported appliances never appears in bulk-substance Article-7 reporting, so a bulk-only supply series understates the bank by the whole factory-charge channel. In a country that imports most of its appliances this is not a correction, it is a large part of the inflow."),
("domestic production", "supply flow", "ASSUMED ZERO",
 "domestic_production_t = 0 on all 143 strata-years",
 "an assumption consistent with an import-only market; Pakistan's 2022 CRT reports 2.B.9 fluorochemical production as NE (not NO)",
 "2.B.9 by-product HFC-23, which belongs outside the 2.F bank",
 "NE is not NO. A one-line confirmation from the National Ozone Unit that no Annex-F or HCFC-22 production facility operates would convert this assumption into an evidenced zero."),
("destruction and recovery", "supply flow / end of life", "EVIDENCED ZERO",
 "recovery_fraction = 0 and destruction = 0 on every row",
 "UNEP records no HFC licensing system in Pakistan and no recovery infrastructure is documented; IPCC Table 7.9 footnote 4 explicitly allows 0 percent recovery",
 "nothing",
 "A zero that is EVIDENCED rather than assumed, which is the distinction the rest of this ledger turns on."),
("charge per unit (M)", "stock -> bank conversion", "HELD (method defaults)",
 "IPCC Table 7.9: domestic refrigeration 0.05-0.5 kg; residential/commercial A/C 0.5-100 kg; mobile A/C 0.5-1.5 kg; stand-alone commercial 0.2-6 kg; medium/large commercial 50-2000 kg",
 "data/raw/ipcc/ipcc2006_V3_7_Ch7_ODS_Substitutes.pdf p.7.52, HELD IN THE REPOSITORY",
 "nothing, but the A/C range spans 0.5 to 100 kg and must be narrowed by equipment type - a judgement, declared in fgas_stock_screen.csv",
 "A Pakistani charge survey would replace the judgement. The defaults are adequate for a screen and not for a reported estimate."),
("bank lifetimes (d) and retirement", "end-of-life emissions", "HELD (method defaults), APPLIED CRUDELY",
 "IPCC Table 7.9 lifetimes: domestic refrigeration 12-20 y, mobile A/C 9-16 y, residential A/C 10-20 y, chillers 15-30 y. The bank applies flat RETIRE_FRACTION tokens of 0.067 (=1/15) and 0.083 (=1/12).",
 "Table 7.9 (held). Footnote 2,3: use the HIGHER value for developing countries - which would LOWER Pakistani retirement below the applied fractions.",
 "the end-of-life term, which for domestic refrigeration is where most of the charge is released (Table 7.9 allows 0-80 percent of initial charge still present at disposal)",
 "A flat 1/lifetime retirement is an exponential-decay approximation of a vintage cohort. For domestic refrigeration, where operating leakage is 0.1-0.5 %/yr, the DISPOSAL term dominates the lifetime emission - so the crude retirement assumption matters more than it looks."),
("operating leak rate (x)", "annual emissions", "HELD (method defaults)",
 "IPCC Table 7.9: domestic refrigeration 0.1-0.5 %/yr; stand-alone commercial 1-15; medium/large commercial 10-35; transport 15-50; industrial 7-25; chillers 2-15; residential/commercial A/C 1-10; mobile A/C 10-20",
 "Table 7.9 (held)",
 "nothing for the method; everything for the ANSWER, via the stratum split above",
 "The bank's own choices - 6 %/yr stationary AC, 15 %/yr mobile AC, 8 %/yr refrigeration - are all inside Table 7.9 for SOME sub-application. The refrigeration one is outside it for the domestic sub-application."),
("initial / assembly loss (k)", "manufacturing emissions", "HELD (method defaults)",
 "IPCC Table 7.9: 0.2-1 %/yr for domestic refrigeration and residential A/C, 0.2-0.5 for mobile A/C. The bank uses 1.0 percent and 0.5 percent - the TOP of each range.",
 "Table 7.9 (held)",
 "nothing",
 "Choosing the top is consistent with Table 7.9 footnote 2,3 for a developing country. Worth recording as a deliberate, correct choice rather than leaving it to look arbitrary."),
("SF6 in electrical equipment (2.G.1)", "a DIFFERENT F-gas category", "NOT HELD",
 "equipment counts exist; no gas balance. Pakistan's BTR1 2024 books all of 2.G at 0 and its 2022 CRT books 2.G.1 SF6 as NE.",
 "NTDC, the DISCOs and K-Electric nameplate SF6 charges and annual refill records; IPCC Tier 1 runs on nameplate charge x a default leak rate",
 "any claim that the F-gas omission is 'HFCs'",
 "OUTSIDE THE HFC BANK ENTIRELY, and the ippu sector matrix rates it medium-high materiality. Pakistan operates 500 kV and 220 kV transmission where SF6 switchgear is standard. SF6's AR5 GWP is 23,500 - the highest of any gas here."),
("PFCs from primary aluminium (2.C.3) and electronics (2.E)", "DIFFERENT F-gas categories", "NOT HELD",
 "occurrence not established for either; BTR1 2024 books 2.C and 2.E at 0",
 "PBS CMI and customs evidence distinguishing primary smelting from remelting, and electronics FABRICATION from assembly",
 "the interpretation of EDGAR's 11.54 Mt, which is reported for 'Processes' as a whole and is not HFC-specific",
 "If either occurs, its F-gases are inside EDGAR's benchmark and outside the 2.F bank - so the EDGAR-minus-bank difference cannot be attributed to HFCs without ruling these out."),
("2021-2023 Article-7 consumption", "supply flow", "NOT PUBLICLY REPORTED",
 "three `missing` rows in the control file; the series reads 7.435 (2019), 9.456 (2020), [missing], [missing], [missing], 9.815 (2024), 12.487 (2025) Mt CO2e",
 "Ozone Secretariat country data (public, consulted 2026-08-21); the gap is in the source",
 "a continuous supply series; currently bridged and labelled `modelled`",
 "Addressed rather than closed: the bridge is typed per row. Note the 2025 observation of 12.487 Mt CO2e of SUPPLY - higher than EDGAR's 2024 EMISSIONS, which is the normal relationship for a filling market and the reverse of what EDGAR implies for 2024."),
("a reported-emissions comparator", "validation", "HELD",
 "Pakistan's 2022 CRT books 2.F at 0.00294 Mt CO2e: ONE species (HFC-23, 0.236955 t) from a declared average stock of 23.6954857 t at a 1 percent product-life factor, entered at 2.F.1.a Commercial refrigeration with the other subcategories marked IE. BTR1 2024 (inventory year 2021) prints 2.F = 0.",
 "sources/Aviation/PAK_CRT_2024.zip IPPU-PAK-CRT.xlsx Table2(II).B-Hs2 rows 53/72/86/99/129; sources/UNFCCC/btr1_2024.txt Table 3",
 "nothing; it is the floor of the comparison",
 "VERIFIED IN THE LATEST AVAILABLE REPORTING, not assumed from an older statement. Two things stand out: HFC-23 (GWP 12,400) is a very-low-temperature cascade component and an HCFC-22 production by-product, not a commercial refrigeration refrigerant, so the species assignment looks misfiled; and 1 percent of a 23.7 t national stock is three orders of magnitude below any supply observation. The official record neither models the bank nor claims the supply."),
]

    # ---- write
    with open(os.path.join(HERE, "fgas.csv"), "w", newline="") as fh:
        fh.write("# T-MISS-2: the input ledger for a defensible Pakistani F-gas estimate, 2026-10-05.\n")
        fh.write("# CONSUMPTION AND IMPORTS ARE NOT ANNUAL EMISSIONS. A bank/emissions method is\n")
        fh.write("# required; this file is what that method needs, input by input, with each one's\n")
        fh.write("# held status. Companion files: fgas_stock_screen.csv (a first stock-side\n")
        fh.write("# calculation) and fgas_benchmark_consistency.csv (three tests of EDGAR's 11.54 Mt).\n")
        fh.write("# NOTHING HERE IS PROMOTED INTO ANY TOTAL. 2.F remains NE in the reference inventory.\n")
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["input", "role_in_the_method", "status", "held_value",
                    "source_or_acquisition_route", "what_its_absence_blocks", "note"])
        w.writerows(req)

    with open(os.path.join(HERE, "fgas_stock_screen.csv"), "w", newline="") as fh:
        fh.write("# A STOCK-SIDE BANK SCREEN FOR PAKISTANI HFCs - SCREENING GRADE, OUTSIDE EVERY TOTAL.\n")
        fh.write("# NOT THE FIRST: outputs/pakemis_hfc_bank_series.csv already ships a household\n")
        fh.write("# stock band on the same HIES indicator and the same IPCC Table 7.9 basis\n")
        fh.write("# (FY2023-24 floor 0.191-2.423 Mt CO2e). This is a SECOND, independently\n")
        fh.write("# parameterised run - different AC charge range, an explicit AC-fitment discount\n")
        fh.write("# on the mobile lane, and a central beside the band - and it lands inside the\n")
        fh.write("# shipped band, which is corroboration between two parameter sets rather than a\n")
        fh.write("# new result. Its purpose is the per-application BANK-MASS comparison in\n")
        fh.write("# fgas_benchmark_consistency.csv, which the shipped emissions-only comparison\n")
        fh.write("# cannot make. Independent of the supply-side bank, which accumulates imports\n")
        fh.write("# from an empty 2012 start and cannot see equipment installed before then.\n")
        fh.write("# SCOPE: HOUSEHOLD equipment only (HIES asks households). Commercial and industrial\n")
        fh.write("# refrigeration, cold stores, chillers, transport refrigeration and non-household\n")
        fh.write("# vehicles are OUTSIDE it, so this is a LOWER BOUND on the national bank.\n")
        fh.write("# Charge and loss brackets are IPCC 2006 Vol 3 Table 7.9 (held at\n")
        fh.write("# data/raw/ipcc/ipcc2006_V3_7_Ch7_ODS_Substitutes.pdf p.7.52). THE HFC SHARE OF THE\n")
        fh.write("# INSTALLED BASE IS THIS SCREEN'S OWN DECLARED ASSUMPTION - not held for Pakistan,\n")
        fh.write("# bracketed wide, and the largest uncertainty in the file.\n")
        fh.write("# Air coolers (9.1 M units) are EVAPORATIVE and carry no refrigerant: excluded.\n")
        w = csv.DictWriter(fh, list(srows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(srows)
        for end in ("low", "central", "high"):
            w.writerow({"lane": "TOTAL (household lane, %s)" % end,
                        "installed_bank_t_%s" % end: "%.1f" % sbank[end],
                        "emissions_Mt_co2e_%s" % end: "%.4f" % stotals[end],
                        "units_source": "sum of the four lanes above; row_kind is a TOTAL - never add it to the lane rows"})

    with open(os.path.join(HERE, "fgas_benchmark_consistency.csv"), "w", newline="") as fh:
        fh.write("# Three consistency tests of the EDGAR F-gas benchmark (11.54 Mt CO2e, Pakistan\n")
        fh.write("# 2024, GWP_100_AR5, sector '%s' - EDGAR reports Pakistani F-gases under\n" % edgar_sector)
        fh.write("# that one sector only). EDGAR IS A SCOPE SCREEN, NOT TRUTH AND NOT A VALUE TO\n")
        fh.write("# ADOPT. These tests ask only whether it is physically reachable from observed\n")
        fh.write("# Pakistani supply and observed Pakistani equipment stocks.\n")
        w = csv.DictWriter(fh, ["test", "assumption", "result_value",
                                "compare_against", "ratio", "reading"],
                           lineterminator="\n")
        w.writeheader()
        w.writerows(tests)

    # ---- console
    print("EDGAR Pakistan F-gases, sector %r: 2024 = %.4f Mt CO2e AR5" % (edgar_sector, edgar[2024]))
    print("held supply-side species bank 2024: %.4f Mt CO2e AR5, bank end %.0f t" % (by_year[2024], bank_2024_t))
    print("  by application:", {k: round(v, 4) for k, v in sorted(app_2024.items())})
    print("stock-side HOUSEHOLD screen 2024-25 (NEW): %.4f / %.4f / %.4f Mt CO2e (low/central/high)"
          % (stotals["low"], stotals["central"], stotals["high"]))
    print("  installed household bank: %.0f / %.0f / %.0f t of HFC" % (sbank["low"], sbank["central"], sbank["high"]))
    print("truncated strata (bank silently dropped when the supply rows stop):")
    for k, v in sorted(truncated.items()):
        print("  %-28s last year %d, bank %.3f t = %.5f Mt CO2e abandoned" % (k, v[0], v[1], v[2]))
    print("wrote fgas.csv (%d inputs), fgas_stock_screen.csv, fgas_benchmark_consistency.csv"
          % len(req))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
