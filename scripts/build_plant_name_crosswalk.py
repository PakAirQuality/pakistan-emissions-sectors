#!/usr/bin/env python3
"""The plant-name crosswalk: every generation-panel spelling, resolved or typed (rc46 Wave 1).

WHY. The plant-month panel spans two report lanes and 547 distinct plant spellings for what
the locations register knows as 78 emitting stations - "UCH Power I", "UCH Power Plant" and
"UCH Power I Ga" are one station; "KE(Formly KESCL)" is not a station at all. rc44's deferral
list named this file as the thing that would turn power's four backcast years into per-object
activity, and nothing could consume the panel spatially until it existed.

TWO LAYERS, BECAUSE THE ARTIFACTS AND THE IDENTIFICATIONS ARE DIFFERENT KINDS OF FACT.
Normalization strips only the grid-parse's mechanical artifacts - fuel-column bleed
(' Ga', ' RL', ' RF', ' Ba'...), Unit-/Block- qualifiers, trailing commas - and is applied
repeatedly until stable. Every SEMANTIC identification is a hand-written stem alias: a token
join was measured and refused at rc41 ("China Power Hub" binds to "Hub Power"), and the same
refusal holds here. Zero stem collisions is asserted, not hoped.

ROW CLASSES. grid_station rows carry a canonical plant (the locations register's name, or
the coal ledger's for the Thar/imported fleet). system_total is a utility aggregate
(K-Electric) that must never receive a point. captive_lane rows belong to the 1,105-row
captive register's own geocoding. station_not_in_locations is a GENCO-era station the SIR
register no longer lists. non_emitting rows leaked into the panel's fossil view. unmapped is
the measured remainder - 0.37% of fossil GWh - typed rather than guessed.

Deterministic; --check re-derives and diffs (write_or_check discipline).

Usage:  python3 scripts/build_plant_name_crosswalk.py [--check]
Writes: data/activity/power/plant_name_crosswalk.csv
"""
import csv
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from pkinv.assets import asset_path

from pkinv.core.io import read_rows, write_or_check  # noqa: E402
from pkinv.paths import DATA  # noqa: E402

PANEL = asset_path(DATA, "activity", "power", "generation_monthly.csv")
LOCATIONS = asset_path(DATA, "activity", "power", "plant_locations.csv")
OUT = asset_path(DATA, "activity", "power", "plant_name_crosswalk.csv")
FIELDS = ("panel_name", "normalized_stem", "canonical_plant", "row_class", "gwh_nine_years",
          "note")

GRID = "grid_station"
SYSTEM = "system_total"
CAPTIVE = "captive_lane"
GENCO_OLD = "station_not_in_locations"
NONEMIT = "non_emitting"
UNMAPPED = "unmapped"

_SUFFIXES = [
    # rc60: HS joined the bleed list. It is the truncation of HSD, and it had been missing
    # while its four siblings were present, so eleven diesel unit rows normalized to nothing
    # the stem table could recognise and stayed `unmapped`: "Balloki Unit-2 HS", "KAPCO
    # Block-1, Unit-3 HS", "Saif Power Limited Unit-2 HS" and so on. They are not stations.
    # Each is one unit of a station the ledger already meters, all of them in FY2020-21, and
    # anything joining the panel to the ledger by name would have priced them a second time
    # on top of their parent - which is exactly what the power admission register did before
    # this line existed.
    r"\s+(Ga|RL|RF|Ba|P|U|RFO|HSD|HS|Coal|Gas|Diesel|Mixed|RLNG)$",
    r"\s+Unit[-\s]*(RL\s*)?[0-9IVX]+$",
    r"\s+Units?[-\s]*[0-9]+\s*[-&]\s*[0-9]+$",
    r"\s+Block[-\s]*[0-9]+$",
    r"\s+block[-\s]*[0-9]+$",
    r",$",
]


def normalize(name):
    s = " ".join(name.split())
    while True:
        before = s
        for pattern in _SUFFIXES:
            s = re.sub(pattern, "", s)
        s = s.strip().rstrip(",")
        if s == before:
            return s


# Hydel, nuclear, solar and wind rows leak into the panel's name space at scale (Tarbela
# alone is 66,672 GWh over the nine years). They carry no combustion mass, so they are typed
# non_emitting by NAME MARKER rather than aliased one by one - the marker list is closed and
# reviewable, and anything it does not catch stays typed unmapped rather than guessed.
import re as _re
_NON_EMITTING = _re.compile(
    r"Hydro|Hydel|\bHy\b|Nuclear|\bNu\b|CHASNUPP|CHASHNUPP|KANUPP|\bK-[23]\b|"
    r"TARBELA|MANGLA|GHAZI BAROTHA|Ghazi B|Neelum|Jhelum|Warsak|CHASMA|"
    r"Solar|Wind|WTs|Jabban|Malakand|Allai|Khan Khwar|Dubair|"
    r"Golen Gol|Jinnah|Duber|Patrind|Gulpur|Karot|Laraib|New Bong|Daral|"
    r"\bDKHP\b|\bAKHP\b|\bKKHP\b|\bGGHP\b|\bNJHP\b|\bUBC\b", _re.I)

STEMS = {
    # -------- system totals: never a point
    "KE(Formly KESCL)": (None, SYSTEM, "K-Electric utility total in the PBS lane"),
    "K Electric": (None, SYSTEM, "K-Electric utility total in the SIR lane"),
    # -------- gas / RLNG
    "KAPCO": ("KAPCO", GRID, ""), "Kot Addu Power Company (KAPCO)": ("KAPCO", GRID, ""),
    "KAPCO Block-1": ("KAPCO", GRID, ""), "KAPCO Block-2": ("KAPCO", GRID, ""),
    "KAPCO Block-3": ("KAPCO", GRID, ""),
    "UCH Power I": ("Uch Power", GRID, ""), "UCH Power Plant": ("Uch Power", GRID, ""),
    "UCH Power": ("Uch Power", GRID, ""),
    "UCH Power II": ("Uch-II Power", GRID, ""), "UCH-II Power (Pvt) Ltd.": ("Uch-II Power", GRID, ""),
    "(NPPMCL) - Balloki": ("NPPMCL (Balloki)", GRID, ""), "Balloki": ("NPPMCL (Balloki)", GRID, ""),
    "Havali Bahadar Shah": ("NPPMCL (HBS)", GRID, ""),
    "(NPPCL) - Haveli Bahadar Shah": ("NPPMCL (HBS)", GRID, ""),
    "(NPPMCL) - Haveli Bahadar Shah": ("NPPMCL (HBS)", GRID, ""),
    "Quaid-e-Azam Thermal Power (Pvt) Ltd. (QATPL)": ("QATPL (Bhikki)", GRID, ""),
    "Quaid-e-Azam Thermal PowerR": ("QATPL (Bhikki)", GRID, ""),
    "Quaid-e-Azam Thermal RL Power Pvt. Ltd": ("QATPL (Bhikki)", GRID, ""),
    # the HSD twin of the RL row above: the bleed lands INSIDE the name, where no suffix rule
    # can reach it, so it is identified by hand exactly as its RLNG sibling already was
    "Quaid-e-Azam Thermal HS Power Pvt. Ltd": ("QATPL (Bhikki)", GRID, "HSD fuel-column bleed, mid-name"),
    "Quaid-e-Azam Thermal": ("QATPL (Bhikki)", GRID, ""),
    "Quaid-e-Azam Thermal Power": ("QATPL (Bhikki)", GRID, ""),
    "CCPP Nandipur": ("TPS Nandipur", GRID, ""), "Nandipur Power Plant": ("TPS Nandipur", GRID, ""),
    "Roush Power": ("Rousch Power", GRID, ""), "Rousch Power": ("Rousch Power", GRID, ""),
    "ROUSCH Power Plant": ("Rousch Power", GRID, ""),
    "TNB Liberty Power": ("Liberty Daharki Power", GRID, "the Daharki station"),
    "Liberty Power Limited.": ("Liberty Daharki Power", GRID, ""),
    "Liberty Power Tech": ("Liberty Power Tech.", GRID, ""),
    "Liberty Power Tech Ltd. (LPTL)": ("Liberty Power Tech.", GRID, ""),
    "FKPCL": ("Fauji Kabirwala", GRID, ""), "Fauji Kabirwala": ("Fauji Kabirwala", GRID, ""),
    "Fauji Kabirwala Power Company Limited. (FKPCL)": ("Fauji Kabirwala", GRID, ""),
    "Foundation Power": ("Foundation Power", GRID, ""),
    "Foundation Power Company (Daharki) Ltd.": ("Foundation Power", GRID, ""),
    "Foundation Power-I": ("Foundation Power", GRID, ""),
    "Foundation Power-II": ("Foundation Power", GRID, ""),
    "engro powrgen": ("Engro Power Gen. Qadirpur", GRID, ""),
    "engro powergen": ("Engro Power Gen. Qadirpur", GRID, ""),
    "Engro Power Gen. Qadirpur": ("Engro Power Gen. Qadirpur", GRID, ""),
    "Engro Powergen Qadirpur Ltd (EPQL)": ("Engro Power Gen. Qadirpur", GRID, ""),
    "Halmore Power": ("Halmore Power", GRID, ""),
    "Halmore Power Generation Company (Pvt) Ltd. (HPGCL)": ("Halmore Power", GRID, ""),
    "Saif Power": ("Saif Power", GRID, ""), "Saif Power Limited": ("Saif Power", GRID, ""),
    "Saif Power Ltd (SPL)": ("Saif Power", GRID, ""),
    "Sapphire Electric": ("Sapphire Electric", GRID, ""),
    "Sapphire electric company": ("Sapphire Electric", GRID, ""),
    "Sapphire electric company Unit": ("Sapphire Electric", GRID, ""),
    "Sapphire Electric Company Ltd (SECL)": ("Sapphire Electric", GRID, ""),
    "Orient Power": ("Orient Power", GRID, ""), "Orient company": ("Orient Power", GRID, ""),
    "Orient Power company": ("Orient Power", GRID, ""),
    "Orient Power Company (Pvt) Ltd. (OPCL)": ("Orient Power", GRID, ""),
    "Orient Power company Unit-": ("Orient Power", GRID, ""),
    "Orient Power company Unit- HS 2": ("Orient Power", GRID, "HSD fuel-column bleed, mid-name; "
                                        "the unit number sits AFTER the bleed so no suffix rule reaches it"),
    "Davis Energen": ("Davis Energen.", GRID, ""), "Davis Energen.": ("Davis Energen.", GRID, ""),
    "Altern Energy": ("Altern Energy", GRID, ""), "Altern Power": ("Altern Energy", GRID, ""),
    "Habibullah Coastal": ("Habibullah Coastal", GRID, ""),
    "Habibullah Power": ("Habibullah Coastal", GRID, ""),
    "Narowal Energy Ltd. (HUBCO)": ("Narowal Energy", GRID, ""),
    "Narowal Energy Ltd.": ("Narowal Energy", GRID, ""),
    "Narowal Energy": ("Narowal Energy", GRID, ""),
    "HUBCO Narowal plant": ("Narowal Energy", GRID, ""),
    "HUBCO NORWAL": ("Narowal Energy", GRID, ""),
    "Saba Power": ("Saba Power", GRID, ""),
    "Saba Power Company (Pvt) Ltd.": ("Saba Power", GRID, ""),
    "Punjab Thermal Power (Pvt) Ltd": ("Punjab Thermal Power", GRID, ""),
    "Punjab Thermal Power": ("Punjab Thermal Power", GRID, ""),
    "Chiniot Power": ("Chiniot Power", GRID, ""),
    "Chiniot Power Limited. (CPL)": ("Chiniot Power", GRID, ""),
    "Chanar Energy": ("Chanar Energy", GRID, ""),
    "Engro Power Gen": ("Engro Power Gen. Qadirpur", GRID, ""),
    # -------- Guddu: one site, several unit-group spellings
    "Guddu 747": ("TPS Guddu (Units 14-16)", GRID, "the 747 MW CCPP"),
    "Thermal Power Station Guddu 747": ("TPS Guddu (Units 14-16)", GRID, ""),
    "TPS GUDDU(5-13)": ("TPS Guddu (Units 5-10)", GRID, "pooled 5-13; same site as 11-13"),
    "Thermal Power Station Guddu 5-13": ("TPS Guddu (Units 5-10)", GRID, "pooled; same site"),
    "TPS GUDDU(5-16)": ("TPS Guddu (Units 5-10)", GRID, "pooled all units; same site"),
    "TPS GUDDU(1-4)": ("TPS Guddu (Units 5-10)", GRID, "retired 1-4 units; same site"),
    "Guddu": ("TPS Guddu (Units 5-10)", GRID, "bare-name rows; same site"),
    "Guddu 747 Ga": ("TPS Guddu (Units 14-16)", GRID, ""),
    "Central Block-2": (None, GENCO_OLD, "an SIR block label with no station name; not identifiable to a locations row - typed rather than guessed"),
    "Central": (None, GENCO_OLD, "same block-label family as Central Block-2"),
    # -------- RFO
    "HUBCO": ("Hub Power", GRID, "the RFO station; distinct from China Power Hub coal"),
    "Hub Power": ("Hub Power", GRID, ""),
    "Hub Power Company (HUBCO)": ("Hub Power", GRID, ""),
    "AES Lal Pir": ("Lal Pir Power", GRID, ""), "Lal Pir Power": ("Lal Pir Power", GRID, ""),
    "AES Lalpir power limited.": ("Lal Pir Power", GRID, ""),
    "AES Pak. Gen.": ("Pak Gen. Power", GRID, ""), "Pak Gen. Power": ("Pak Gen. Power", GRID, ""),
    "AES Pakgen Power Limited.": ("Pak Gen. Power", GRID, ""),
    "TPS M GARH": ("TPS Muzaffargarh", GRID, ""),
    "Thermal Power Station Muzaffargarh": ("TPS Muzaffargarh", GRID, ""),
    "TPS JAMSHORO": ("TPS Jamshoro", GRID, ""),
    "JAMSHORO": ("TPS Jamshoro", GRID, ""),
    "Jamshoro Power Generation Company Limited.": ("TPS Jamshoro", GRID, ""),
    "Tapal Power": ("Tapal Energy", GRID, ""), "Tapal Energy": ("Tapal Energy", GRID, ""),
    "Attock Gen Limited": ("Attock Gen.", GRID, ""), "Attock Gen.": ("Attock Gen.", GRID, ""),
    "Attock Gen Ltd (AGL)": ("Attock Gen.", GRID, ""),
    "Atlas Power": ("Atlas Power", GRID, ""), "Atlas Power Ltd (APL)": ("Atlas Power", GRID, ""),
    "Nishat Power": ("Nishat Power", GRID, ""), "Nishat Power Ltd (NPL)": ("Nishat Power", GRID, ""),
    "Nishat Chunian Ltd.": ("Nishat Chunian", GRID, ""), "Nishat Chunian": ("Nishat Chunian", GRID, ""),
    "Nishat Chunian Power Ltd (NCPL)": ("Nishat Chunian", GRID, ""),
    "Gul Ahmed": ("Gul Ahmed", GRID, ""),
    "Kohinoor Energy": ("Kohinoor Energy", GRID, ""),
    "Kohinoor Energy Limited. (KEL)": ("Kohinoor Energy", GRID, ""),
    "Southern Electric": ("Southern Electric", GRID, ""),
    "Japan Power": ("Japan Power", GRID, ""),
    "Reshma Power": ("Reshma Power", GRID, ""),
    "SNPC": ("SNPCL-I (IPP-2002)", GRID, "pooled SNPC rows; both IPP-2002 units share the Jamshoro site"),
    "SNPCL": ("SNPCL-I (IPP-2002)", GRID, "same site"),
    "GTPS Faisalabad": ("GTPS Faisalabad", GRID, ""), "GTPS FAISALABAD": ("GTPS Faisalabad", GRID, ""),
    # -------- coal: canonical keys are the ledger names coal_plant_coordinates uses
    "Port Qasim": ("Port Qasim Electric Power", GRID, ""),
    "Port Qasim Co": ("Port Qasim Electric Power", GRID, ""),
    "Port Qasim Electric Power Company (Private) Limited. (PQEPCL)": ("Port Qasim Electric Power", GRID, ""),
    "China Power Hub Generation Company (Private) Limited. (CPHGCL)": ("China Power Hub", GRID, ""),
    "China Hub Power Co": ("China Power Hub", GRID, ""), "China Hub Power": ("China Power Hub", GRID, ""),
    "Coal Fire/Huaneng Shandong": ("Huaneng Shandong Ruyi (Sahiwal Imported Coal)", GRID, ""),
    "Coal Fire/Huaneng Shandong Ru Co": ("Huaneng Shandong Ruyi (Sahiwal Imported Coal)", GRID, ""),
    "Coal Fire": ("Huaneng Shandong Ruyi (Sahiwal Imported Coal)", GRID, "the PBS lane's bare rows are Sahiwal"),
    "Coal Power": ("Huaneng Shandong Ruyi (Sahiwal Imported Coal)", GRID, "same bare-row family"),
    "Huaneng Shandong Ruyi (Pakistan) Energy (Private) Limited. (HSRPEL)": ("Huaneng Shandong Ruyi (Sahiwal Imported Coal)", GRID, ""),
    "engro Powergen Thar": ("Engro Powergen Thar", GRID, ""),
    "engro Powergen Thar Co": ("Engro Powergen Thar", GRID, ""),
    "Engro Powergen Thar (Private) Limited. (EPTPL)": ("Engro Powergen Thar", GRID, ""),
    "Thar Coal Block-I Power Generation Company (Private) Limited (TCB-I)": ("Thar Coal Block-I", GRID, ""),
    "Thar Energy Limited (TEL)": ("Thar Energy", GRID, ""),
    "ThalNova Power Thar (Pvt.) Limited (TPTPL)": ("ThalNova", GRID, ""),
    "Lucky Electric Power Company Limited (LEPCL)": ("Lucky Electric", GRID, ""),
    "Lucky Electric Power Limited.": ("Lucky Electric", GRID, ""),
    "Lucky Electric Power": ("Lucky Electric", GRID, ""),
    "FBC Lakhra": ("FBC Lakhra", GRID, ""), "FBC LAKHRA": ("FBC Lakhra", GRID, ""),
    # -------- bagasse / biomass grid sellers
    "JDW (Unit II &III)": ("Jamal Din Wali-II", GRID, "pooled II+III; adjacent RYK mills"),
    "JDW - II": ("Jamal Din Wali-II", GRID, ""), "JDW- III": ("Jamal Din Wali-III", GRID, ""),
    "JDW Sugar Mills Limited. (Unit-II) Rahim Yar Khan": ("Jamal Din Wali-II", GRID, ""),
    "JDW Sugar Mills Limited. (Unit-III) Ghotki": ("Jamal Din Wali-III", GRID, ""),
    "RYK": ("RYK Mills", GRID, ""), "RYK Mills Limited. (RYKML)": ("RYK Mills", GRID, ""),
    "RYK Mills": ("RYK Mills", GRID, ""),
    "Almoiz Industries": ("Almoiz Industries", GRID, ""),
    "Fatima Energy": ("Fatima Energy", GRID, ""),
    "Fatima Energy Limited. (FEL)": ("Fatima Energy", GRID, ""),
    "Hamza Sugar Mills": ("Hamza Sugar Mills", GRID, ""),
    "Chanar Energy Limited": ("Chanar Energy", GRID, ""),
    # -------- old GENCO stations absent from the SIR locations register
    "GTPS KOTRI": (None, GENCO_OLD, "GENCO-era gas turbine station, PBS years only; absent from the SIR locations register - Wave 1 adds coordinates directly if wired"),
    "SPS FAISALABAD": (None, GENCO_OLD, "GENCO-era steam station, PBS years only; absent from the SIR locations register"),
    "TPS Quetta": ("TPS Quetta", GRID, ""), "TPS QUETTA": ("TPS Quetta", GRID, ""),
    # -------- captive/CPP rows in the PBS lane: the captive register's geocoding owns these
    "Lucky Cement Pezo": (None, CAPTIVE, "captive plant; the 1,105-row captive register is the coordinate lane"),
    "Lucky Cement Karachi": (None, CAPTIVE, "captive plant"),
    "Lucky Cement": (None, CAPTIVE, "captive plant (grid sales rows exist but the site is the cement works)"),
    "Bestway Cement Chakwal": (None, CAPTIVE, "captive plant"),
    "Gadoon Textile Mills": (None, CAPTIVE, "captive plant"),
    "Sitara Energy Ltd": (None, CAPTIVE, "captive plant"),
    "FPCL/FFBL": (None, CAPTIVE, "Fauji power/fertilizer complex captive"),
    "International Steel": (None, CAPTIVE, "captive plant"),
    "Intl. Steel Limited (CPP)": (None, CAPTIVE, "captive plant"),
    "International Industries": (None, CAPTIVE, "captive plant"),
    "Intl. Ind. Limited (CPP)": (None, CAPTIVE, "captive plant"),
    "Lotte Chemicals": (None, CAPTIVE, "captive plant"),
    "Lotte Powergen": (None, CAPTIVE, "captive plant"),
    "Anoud Power": (None, CAPTIVE, "captive/IGC plant"),
    "Anoud Power (IGC)": (None, CAPTIVE, "captive/IGC plant"),
    "Liberty Power Tech.": ("Liberty Power Tech.", GRID, ""),
    "Hawali Bahadur Shah": ("NPPMCL (HBS)", GRID, "spelling variant"),
    "Davis Energy Pvt": ("Davis Energen.", GRID, ""),
    "JDW-II": ("Jamal Din Wali-II", GRID, ""), "JDW- III": ("Jamal Din Wali-III", GRID, ""),
    "JDW - II": ("Jamal Din Wali-II", GRID, ""), "JDW-III": ("Jamal Din Wali-III", GRID, ""),
    "Hamza Sugar Mills Limited. (HSML)": ("Hamza Sugar Mills", GRID, ""),
    "Thal Industries Corporation Limited. (TICL) - Layyah Sugar Mills": (None, CAPTIVE, "sugar-mill captive"),
    "Layyah Sugar Mill": (None, CAPTIVE, "sugar-mill captive"),
    "Layyah Sugar Mills": (None, CAPTIVE, "sugar-mill captive"),
    "Fatima Sugar Mill": (None, CAPTIVE, "sugar-mill captive"),
    "Fatima Sugar Mills": (None, CAPTIVE, "sugar-mill captive"),
    # -------- non-emitting rows that leak into the fossil view
    "Quaid-e-Azam Solar Power": (None, NONEMIT, "solar"),
    "Quaid-e-Azam Solar Powe": (None, NONEMIT, "solar; grid-parse truncation"),
    "Quaid-e-Azam Solar Power Solar": (None, NONEMIT, "solar"),
    "Appolo Solar": (None, NONEMIT, "solar"),
    "Metro Wind": (None, NONEMIT, "wind"),
}


NON_EMITTING_FUELS = {"Hydel", "Wind", "Solar", "Nuclear"}


def build_rows():
    gwh = defaultdict(float)
    fuel_labels = defaultdict(set)
    for row in read_rows(PANEL):
        if row["gwh"]:
            gwh[row["plant"]] += float(row["gwh"])
        if row["fuel"]:
            fuel_labels[row["plant"]].add(row["fuel"])
    # every canonical target must be a real locations-register or coal-ledger name
    known = {r["plant"] for r in read_rows(LOCATIONS)}
    known |= {"Thar Coal Block-I", "Thar Energy", "ThalNova", "Lucky Electric",
              "China Power Hub", "Engro Powergen Thar", "Port Qasim Electric Power",
              "Huaneng Shandong Ruyi (Sahiwal Imported Coal)"}
    out = []
    collisions = defaultdict(set)
    for panel_name in sorted(gwh):
        stem = normalize(panel_name)
        if stem in STEMS:
            canonical, row_class, note = STEMS[stem]
            if canonical:
                if canonical not in known:
                    raise SystemExit("crosswalk names unknown canonical plant %r (from %r)"
                                     % (canonical, panel_name))
                collisions[stem].add(canonical)
        elif fuel_labels.get(panel_name) and fuel_labels[panel_name] <= NON_EMITTING_FUELS:
            canonical, row_class, note = None, NONEMIT, (
                "every panel fuel label is %s - the panel's own fuel column is the typing "
                "evidence" % "/".join(sorted(fuel_labels[panel_name])))
        elif _NON_EMITTING.search(panel_name):
            canonical, row_class, note = None, NONEMIT, (
                "hydel, nuclear, solar or wind by name marker; carries no combustion mass "
                "and needs no point in the emission map")
        else:
            canonical, row_class, note = None, UNMAPPED, "no stem alias; typed, never guessed"
        out.append({"panel_name": panel_name, "normalized_stem": stem,
                    "canonical_plant": canonical or "", "row_class": row_class,
                    "gwh_nine_years": "%.3f" % gwh[panel_name], "note": note})
    bad = {k: v for k, v in collisions.items() if len(v) > 1}
    if bad:
        raise SystemExit("stem collisions: %r" % bad)
    return out


def main(argv):
    rows = build_rows()
    total = sum(float(r["gwh_nine_years"]) for r in rows)
    mapped = sum(float(r["gwh_nine_years"]) for r in rows if r["row_class"] == GRID)
    unmapped = sum(float(r["gwh_nine_years"]) for r in rows if r["row_class"] == UNMAPPED)
    banner = (
        "# Panel spelling -> canonical station, or a typed class (rc46 Wave 1). See",
        "# scripts/build_plant_name_crosswalk.py for the two-layer design and the refusal",
        "# of token joins. %d spellings; grid_station rows carry %.1f%% of panel GWh," % (
            len(rows), 100.0 * mapped / total),
        "# unmapped %.2f%%." % (100.0 * unmapped / total),
    )
    check = "--check" in argv
    write_or_check(OUT, FIELDS, rows, banner=banner, check=check)
    print("%s: %d rows (%s)" % (OUT, len(rows), "check" if check else "written"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
