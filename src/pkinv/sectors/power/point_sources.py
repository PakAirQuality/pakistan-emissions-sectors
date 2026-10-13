"""Per-fuel provincial shares from the plant ledger joined to Table 5's locations.

WHAT CHANGED. The provincial allocation ran on one aggregate share for every fossil fuel,
built from FY2022 plant-wise generation, because the national fuel table has no geography.
downscale.py's own docstring called per-fuel proxies "the obvious next refinement" once
plant-wise fuel existed. It exists: the FY2023-24 ledger carries fuel per plant, Table 5
carries every station's location, and this module joins them - so coal stops riding a
blended surrogate and rides the plants that burned it.

WHY IT MOVES PROVINCES MATERIALLY, AND WHY THAT IS A CORRECTION RATHER THAN A CHOICE. On
the aggregate FY2022 share, half the sector's coal emissions landed in Punjab. The coal
fleet is not there: Thar's four mine-mouth plants, Port Qasim and Lucky are Sindh, Sahiwal
is the one Punjab coal plant, and China Power Hub (Balochistan) burned 132 kt in FY2023-24.
On ledger energy the coal split is 89 percent Sindh. Balochistan's previous 16 percent of
the whole sector likewise dated from years when Hub burned furnace oil; in FY2023-24 Hub
reports zero, and Balochistan's remaining thermal weight is the Uch pair's gas.

THE ENERGY WEIGHTS, BY EVIDENCE CLASS - same discipline as the closure. Gas and RLNG
metered in MMBTU are exact; MMCFT volumes take the sector's declared heating value; COAL
MASS TAKES THE PER-PLANT IMPLIED NCVs from implied_cv (Tables 20/23/28), with outlier and
no-heat-rate plant-years carried at the fleet CV - the one place the Phase-A channel feeds
a published allocation, and it is an allocation WEIGHT, never a total. RFO takes the IPCC
default NCV and HSD its default with a 0.84 kg/L density. Shares weight energy, not
energy times emission factor; the lignite/bituminous factor difference would move the coal
split by well under one percent and is noted rather than modelled.

K-ELECTRIC IS EXCLUDED from the shares for the same reason it is excluded from the gas
technology split: the boundary audit finds the national fuel rows cover the CPPA side
only, and a share should describe the fleet behind the activity it allocates. K-E plants
still appear in the point-source output with their system labelled.

THE THREE BLANK LOCATIONS. Table 5 prints no location for Thar Energy, Thar Coal Block-I
and ThalNova. They are mine-mouth plants - the ledger's own coal-origin logic rests on
their names carrying the field - and a mine-mouth plant sits at its mine: Tharparkar,
Sindh. That rule is declared here, tested, and applied to exactly those three plants.

THE COMMITTED SHARES ARE PINNED, NOT TRUSTED. data/province_shares.csv carries the four
power_<fuel> rows as static data with this module named as their source; a test recomputes
them from the ledger and fails on drift, so the CSV cannot quietly outlive its derivation.
"""

from pkinv.assets import asset_path
import csv
import os

from pkinv.paths import DATA
from pkinv.sectors.power import implied_cv, plant_ledger
from pkinv.sectors.power.plant_ledger import TJ_PER_MMCF_PER_BTU
from pkinv.activity.store import read_rows

LOCATIONS_CSV = asset_path(DATA, "activity", "power", "plant_locations.csv")

TJ_PER_MMBTU = 1.05505585262e-3
RFO_NCV_TJ_PER_GG = 40.4          # IPCC 2006 Vol 2 Ch 1 Table 1.2, residual fuel oil
HSD_NCV_TJ_PER_GG = 43.0          # gas/diesel oil
HSD_KG_PER_L = 0.84

# Ledger plant name -> Table 5 name, for the rows whose ledger names are SHORT FORMS of
# the Table 5 spelling. The normalisation lives HERE, in the join, so the ledger stays
# verbatim against its source.
#
# rc60: EIGHT KEYS LEFT THIS TABLE, and they are the more interesting half of its history.
# They read "(000 M. Tons) & Gul Ahmed", "RLNG RFO HSD Overall kWh) KAPCO" and so on -
# not short forms at all but column headings that the ingest had joined onto the plant
# name, and this table quietly absorbed them. That is why the defect survived: the only
# consumer that needed these names to be right had been taught to expect them wrong, so
# nothing ever failed. The ingest now rejects a bare unit heading
# (scripts/ingest_nepra_plants.py, HEADER_TOKENS), the ledger carries the plain names,
# and the aliases below are once again only the short forms they claim to be. Three of
# the eight still need a mapping because their Table 5 spellings genuinely differ, and
# they appear in the list on their clean names; the other five now match Table 5
# directly and need no entry at all.
ALIAS = {
    # rc44: spellings the EARLIER ledger years use and the reference year does not. They
    # were invisible until the generation panel needed FY2019-20 as a control and 26.5
    # percent of that year's furnace oil turned out to be unplaced - Jamshoro, which is
    # Sindh, and KAPCO, which is Punjab. The reference year has NO unmatched rows at all,
    # so these move no published share; they close a hole in a diagnostic that was
    # quietly reporting Sindh furnace oil as zero because it could not see it.
    "TPS Jamshoro (GENCO-I)": "TPS Jamshoro",
    "Lal Pir": "Lal Pir Power",
    "TPS Guddu (Units 5-10) (GENCO-II)": "TPS Guddu (Units 5-10)",
    "TPS Guddu (Units 11-13) (GENCO-II)": "TPS Guddu (Units 11-13)",
    "Atlas": "Atlas Power",
    "Engro Powergen. Qadirpur": "Engro Power Gen. Qadirpur",
    "Foundation": "Foundation Power",
    "Halmore": "Halmore Power",
    "Hub": "Hub Power",
    "Liberty Daharki": "Liberty Daharki Power",
    "Lucky Electric": "Lucky Electric Power",
    "Nishat": "Nishat Power",
    "Orient": "Orient Power",
    "Pak Gen.": "Pak Gen. Power",
    "Punjab Thermal": "Punjab Thermal Power",
    "Rousch": "Rousch Power",
    "Saba": "Saba Power",
    "Saif": "Saif Power",
    "Sindh Nooriabad-I": "SNPCL-I (IPP-2002)",
    "Sindh Nooriabad-II": "SNPCL-II (IPP-2002)",
    "TPS Guddu (Units 14-16) (GENCO-II)": "TPS Guddu (Units 14-16)",
    "TPS Muzaffargarh (GENCO-III)": "TPS Muzaffargarh",
    "TPS Nandipur (GENCO-III)": "TPS Nandipur",
    "Uch": "Uch Power",
    "Uch-II": "Uch-II Power",
}

def equipment_class(station_type):
    """Boiler, reciprocating engine or gas turbine, from NEPRA Table 5's own station type.

    IT LIVES HERE because it is a fact about Table 5's vocabulary, and two registers need the
    same answer from it - the national power SO2 admission register and the Lahore one. It
    matters because AP-42 Section 1.3's 157 lb/kgal-per-%S is a factor for BOILERS and half
    this fleet is not boilers: Kohinoor, Nishat, Narowal, Liberty, Atlas, Attock, Gul Ahmed,
    Tapal and Nishat Chunian are reciprocating-engine stations, and every HSD burner in the
    fleet is a gas turbine. Sections 3.4 and 3.1 cover those, and both state that conversion
    of fuel sulfur to SO2 is complete, so they are priced as a full balance rather than with a
    boiler's ash retention.

    Order is safe because the data permits it: no station in this fleet prints both a turbine
    and a reciprocating engine. A station whose type cannot be read returns None, and the
    caller must type that row rather than take a default - choosing an equipment class for a
    station we cannot identify is the guess this function exists to refuse.
    """
    t = (station_type or "").upper()
    if not t:
        return None
    if "GT" in t or "CCPP" in t:
        return "gas_turbine"
    if "DE" in t or "DG" in t or "RE" in t:
        return "reciprocating_engine"
    if "ST" in t:
        return "oil_fired_boiler"
    return None


# Table 5 prints these three with blank location cells. Mine-mouth by name and by the
# ledger's fuel_origin; a mine-mouth plant sits at its mine.
MINE_MOUTH = {"Thar Energy": ("Tharparkar", "Sindh"),
              "Thar Coal Block-I": ("Tharparkar", "Sindh"),
              "ThalNova": ("Tharparkar", "Sindh")}

# Ledger fuel -> the emission stream (and share row) it allocates. Gas and RLNG are one
# Table 3 row and one emission stream, so they share a proxy.
FUEL_GROUP = {"Coal": "power_coal", "Gas": "power_gas", "RLNG": "power_gas",
              "RFO": "power_rfo", "HSD": "power_hsd"}


def locations(path=LOCATIONS_CSV):
    return {r["plant"]: r for r in read_rows(path, comments=False)}


def rows(data, year=None):
    """One row per ledger fuel row: energy, province, and how each was established."""
    year = data.year if year is None else year
    loc = locations()
    cv = {r["plant"]: r for r in implied_cv.implied_coal_cv(data)
          if r["fiscal_year"] == year}
    fleet = implied_cv.fleet_cv(data, year)["fleet_cv"]
    hhv = data.p("captive_hhv_btu_per_scf")
    out = []
    for r in plant_ledger.rows(year):
        q, unit = float(r["quantity"]), r["quantity_unit"]
        if unit == "MMBTU":
            tj, evidence = q * TJ_PER_MMBTU, "exact (MMBTU)"
        elif unit == "MMCFT":
            tj, evidence = q * hhv * TJ_PER_MMCF_PER_BTU, "assumed heating value"
        elif unit == "000 t" and r["fuel"] == "Coal":
            c = cv.get(r["plant"])
            if (c and c["implied_cv_TJ_per_Gg"]
                    and c["evidence_class"] not in ("no-hr", "outlier")):
                tj, evidence = q * float(c["implied_cv_TJ_per_Gg"]), "implied CV"
            else:
                tj, evidence = q * fleet, "fleet CV (outlier or no heat rate)"
        elif unit == "000 t":
            tj, evidence = q * RFO_NCV_TJ_PER_GG, "IPCC default NCV"
        elif unit == "000 L":
            tj = q * HSD_KG_PER_L * HSD_NCV_TJ_PER_GG / 1000.0
            evidence = "IPCC default NCV x 0.84 kg/L"
        else:
            continue
        t5 = ALIAS.get(r["plant"], r["plant"])
        if t5 in MINE_MOUTH:
            town, province = MINE_MOUTH[t5]
            located = "mine-mouth rule (Table 5 location blank)"
        elif t5 in loc:
            town, province = loc[t5]["town"], loc[t5]["province"]
            located = "Table 5"
        else:
            town, province, located = "", "", "UNMATCHED"
        out.append({"fiscal_year": year, "system": r["system"], "plant": r["plant"],
                    "fuel": r["fuel"], "energy_TJ": round(tj, 1),
                    "energy_evidence": evidence, "town": town, "province": province,
                    "located_by": located})
    return out


def fuel_province_shares(data, year=None):
    """{share_row: {province: share}} over the CPPA fleet, plus the unmatched residual.

    Unmatched energy is REPORTED, never silently spread: if a future ledger year brings a
    plant this module cannot place, its energy appears under 'UNMATCHED' and the test on
    this function fails until the join is extended.
    """
    energy, unmatched = {}, {}
    for r in rows(data, year):
        if not plant_ledger.in_boundary(r):
            continue
        grp = FUEL_GROUP[r["fuel"]]
        if r["located_by"] == "UNMATCHED":
            unmatched[grp] = unmatched.get(grp, 0.0) + r["energy_TJ"]
            continue
        d = energy.setdefault(grp, {})
        d[r["province"]] = d.get(r["province"], 0.0) + r["energy_TJ"]
    shares = {}
    for grp, d in energy.items():
        total = sum(d.values()) + unmatched.get(grp, 0.0)
        shares[grp] = {p: v / total for p, v in d.items()}
        if unmatched.get(grp):
            shares[grp]["UNMATCHED"] = unmatched[grp] / total
    return shares
