"""The K-Electric leg of the boundary question, computed rather than gestured at.

THE QUESTION IT SERVES. ke_boundary_audit finds the national fuel table brackets the plant
sum only without the K-Electric system, in every year - evidence that Table 3 covers the
CPPA side only, never proof. The decision (add a K-E category on ledger evidence, or
establish that Table 3 includes K-E) is the author's. What this module does is make that
decision DECISION-READY: the exact fuel, energy and CO2 the K-E system's ledger rows
imply, per plant-year, with each number's evidence class attached.

THE FINDING THAT REPLACES A FLAT CLAIM. Earlier prose said the K-E system was worth
"five to six megatonnes a year". It is not a flat number - it is a strongly trending
series: 7.1, 7.7, 6.1, 4.8, 4.0 Mt CO2 across FY2019-23, a 48 percent decline in five
years, driven almost entirely by furnace-oil retirement (977 down to 209 kt) while gas
collapsed into RLNG (Bin Qasim TPS-III alone reaching 25,940 MMCFT). The old claim was
accurate for FY2023 only; whichever way the boundary decision goes, the correction is a
trend, not an adder.

TWO CORROBORATIONS RIDE ALONG. First, implied net efficiency rises 36.9 to 45.5 percent
across the window - what RFO steam giving way to RLNG combined cycle should do, and an
independent check that the MMCFT heating-value assumption is not badly wrong for K-E.
Second, the FY2023-24 furnace-oil year is the sharpest single discriminator in the whole
boundary panel: the national RFO row sits at 1.256 times the with-KE plant sum and 0.890
times the without-KE sum, the widest split in the series, because K-E's RFO collapsed in
the same year the national row did.

EVIDENCE CLASSES, WEAKER THAN THE CPPA LEG AND SAID SO. Only the two Sindh Nooriabad
units are MMBTU-metered (exact). Everything else is MMCFT at the sector's assumed heating
value, or mass and litres at IPCC default NCVs. That weakness is exactly why the case is
published as a labelled sensitivity - "grid + K-Electric ledger fuel" - rather than a
category: the arithmetic is sound, the boundary question and the evidence classes are
what keep it conditional.

CO2 ONLY. CH4 and N2O at Table 2.2 factors would add under half a percent and would
suggest a precision the activity classes do not support. The sensitivity row's note says
so. DIAGNOSTIC: combustion.py and engine.py never import this module.
"""
from pkinv.sectors.power import plant_ledger
from pkinv.sectors.power.plant_ledger import TJ_PER_MMCF_PER_BTU

TJ_PER_MMBTU = 1.05505585262e-3
RFO_NCV_TJ_PER_GG = 40.4          # IPCC 2006 Vol 2 Ch 1 Table 1.2
HSD_NCV_TJ_PER_GG = 43.0
HSD_KG_PER_L = 0.84

# kg CO2/TJ, IPCC Table 2.2 (Energy Industries) - same rows the grid streams use.
CO2_KG_PER_TJ = {"Gas": 56100.0, "RLNG": 56100.0, "RFO": 77400.0, "HSD": 74100.0}


def _energy_TJ(r, hhv):
    q, unit = float(r["quantity"]), r["quantity_unit"]
    if unit == "MMBTU":
        return q * TJ_PER_MMBTU, "exact"
    if unit == "MMCFT":
        return q * hhv * TJ_PER_MMCF_PER_BTU, "assumed HHV"
    if unit == "000 t":
        return q * RFO_NCV_TJ_PER_GG, "default NCV"
    if unit == "000 L":
        return q * HSD_KG_PER_L * HSD_NCV_TJ_PER_GG / 1000.0, "default NCV"
    return None, None


def series(data):
    """One row per fiscal year: K-E fuel energy, CO2 and implied net efficiency."""
    hhv = data.p("captive_hhv_btu_per_scf")
    out = []
    for year in sorted({int(r["fiscal_year"]) for r in plant_ledger._all_rows()}):
        tj_by_fuel, co2_kt, gwh = {}, 0.0, 0.0
        for r in plant_ledger.rows(year):
            if plant_ledger.in_boundary(r):   # this leg IS the complement
                continue
            tj, _cls = _energy_TJ(r, hhv)
            if tj is None:
                continue
            tj_by_fuel[r["fuel"]] = tj_by_fuel.get(r["fuel"], 0.0) + tj
            co2_kt += tj * CO2_KG_PER_TJ[r["fuel"]] / 1e6
            gwh += float(r["net_generation_GWh"])
        total_tj = sum(tj_by_fuel.values())
        # A YEAR WITH NO K-ELECTRIC FUEL IS NOT A K-ELECTRIC YEAR. This used to emit a row for
        # every fiscal year the ledger carried, whoever the rows belonged to, with a None
        # efficiency where this leg had nothing - so extending the ledger back to FY2018-19
        # for two IPP coal stations silently gave the K-E series an empty leading year and
        # broke a test that reads effs[0]. The complement of a boundary is only defined where
        # the boundary has members; skipping is the correct answer, not a None.
        if not total_tj:
            continue
        out.append({"fiscal_year": year,
                    "gas_TJ": tj_by_fuel.get("Gas", 0.0),
                    "rlng_TJ": tj_by_fuel.get("RLNG", 0.0),
                    "rfo_TJ": tj_by_fuel.get("RFO", 0.0),
                    "hsd_TJ": tj_by_fuel.get("HSD", 0.0),
                    "total_TJ": total_tj,
                    "co2_Mt": co2_kt / 1000.0,
                    "net_GWh": gwh,
                    "implied_net_efficiency": (gwh * 3600e3) / (total_tj * 1e6)
                    if total_tj else None})
    return out


# --- The four years before the plant ledger begins (rc67, the review's Priority 4) -------
#
# The ledger starts at FY2019-20, so through rc66 the K-Electric leg existed for five
# years and the "power scope" axis was refused for the other four. NEPRA's 2020 report
# prints the same stations' fuel for FY2015-16 to FY2018-19 (Table 24), transcribed in
# data/sectors/power/activity/ke_station_fuel_back_years.csv. Three furnace-oil cells are
# printed "n.p." there and in every other held edition. They stay typed absences in the
# table; here each is ESTIMATED from the same station's own printed fuel per unit of
# generation in the adjacent year of the same table, and the series carries both the sum
# of printed fuel alone (a floor) and the sum with the estimates, so no reader mistakes
# one for the other.
# K-Electric's own stations; the rest of the system (Gul Ahmed, Tapal Energy, Sindh
# Nooriabad I and II) are independent producers that sell to it.
OWN_STATIONS = ("Bin Qasim TPS-I", "Bin Qasim TPS-II", "Bin Qasim TPS-III",
                "Korangi CCPP", "Korangi Town GTPS-II", "Site GTPS-II")
ESTIMATE_FROM = {2015: 2016, 2018: 2017}   # the n.p. year -> the adjacent printed year


def back_year_rows():
    from pkinv.activity.store import read_rows
    from pkinv.assets import asset_path
    from pkinv.paths import DATA
    return read_rows(asset_path(DATA, "activity", "power",
                                "ke_station_fuel_back_years.csv"), comments=False)


def back_years(data):
    """One row per fiscal START year 2015-2018: the K-Electric system's fuel CO2 from
    NEPRA's 2020 report, printed fuel alone and with the unprinted cells estimated."""
    hhv = data.p("captive_hhv_btu_per_scf")
    rows = back_year_rows()
    rate = {}                                   # (plant, year) -> 000 t RFO per GWh
    for r in rows:
        if r["fuel"] == "RFO" and r["quantity"]:
            rate[(r["plant"], int(r["fiscal_year"]))] = (
                float(r["quantity"]) / float(r["generation_GWh"]))
    out = []
    for year in sorted({int(r["fiscal_year"]) for r in rows}):
        printed = estimated = own = 0.0
        cells = []
        for r in rows:
            if int(r["fiscal_year"]) != year:
                continue
            row = {"quantity": r["quantity"], "quantity_unit": r["quantity_unit"]}
            guessed = False
            if not r["quantity"]:
                neighbour = rate[(r["plant"], ESTIMATE_FROM[year])]
                row["quantity"] = neighbour * float(r["generation_GWh"])
                guessed = True
                cells.append("%s RFO (%.0f kt at the FY%d-%02d rate)"
                             % (r["plant"], row["quantity"], ESTIMATE_FROM[year],
                                (ESTIMATE_FROM[year] + 1) % 100))
            tj, _cls = _energy_TJ(row, hhv)
            co2 = tj * CO2_KG_PER_TJ[r["fuel"]] / 1e9
            if guessed:
                estimated += co2
            else:
                printed += co2
            if r["plant"] in OWN_STATIONS:
                own += co2
        out.append({"fiscal_year": year, "co2_Mt_printed_fuel_only": printed,
                    "co2_Mt": printed + estimated, "co2_Mt_own_stations": own,
                    "estimated_cells": "; ".join(cells),
                    "basis": "NEPRA SoIR 2020 Table 24"})
    return out


def coverage_series(data):
    """The K-Electric system's fuel CO2 for every fiscal START year held, 2015-2023: the
    back years above, then the plant ledger. The coverage alternative's own series."""
    hhv = data.p("captive_hhv_btu_per_scf")
    out = back_years(data)
    for row in series(data):
        own = 0.0
        for r in plant_ledger.rows(row["fiscal_year"]):
            if plant_ledger.in_boundary(r) or r["plant"] not in OWN_STATIONS:
                continue
            tj, _cls = _energy_TJ(r, hhv)
            if tj is not None:
                own += tj * CO2_KG_PER_TJ[r["fuel"]] / 1e9
        out.append({"fiscal_year": row["fiscal_year"],
                    "co2_Mt_printed_fuel_only": row["co2_Mt"], "co2_Mt": row["co2_Mt"],
                    "co2_Mt_own_stations": own, "estimated_cells": "",
                    "basis": "plant fuel ledger (NEPRA SoIR 2024 and 2025)"})
    return out


def fy2023_case(data):
    """The sensitivity's K-E term for the anchor year, CO2 only."""
    row = next(r for r in series(data) if r["fiscal_year"] == data.year)
    return row["co2_Mt"]
