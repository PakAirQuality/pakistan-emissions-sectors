"""Cell-audited extraction of Pakistan's 2022 UNFCCC CRT for public electricity (1.A.1.a).

WHY. This sector's only external comparison has been EDGAR, which is a model. Pakistan filed
its first Common Reporting Tables with the UNFCCC in 2024 (inventory year 2022), and they are
the official statement of what the country itself reports for this category - the comparator
the fugitives and IPPU papers already use and this one did not.

WHAT THE TABLES SAY, READ OFF THE CELLS. Table 1.A(a)s1 reports 1.A.1.a at 777,243 TJ and
62,841 kt CO2 for calendar 2022 - liquid fuels 452,519 TJ, solid fuels 324,724 TJ, and
GASEOUS FUELS NOT ESTIMATED. Three findings sit in those five rows:

  THE NCV COLUMN SETTLES A DECLARED RISK OFFICIALLY. Every 1.A.1.a row carries "NCV" in the
  units column: Pakistan reports this category on the net calorific basis. The plant-meter
  evidence (48.7 percent implied efficiency) said the same thing physically; the CRT says it
  administratively. The sector's largest declared risk is now covered from two independent
  directions.

  GAS IS MISSING FROM THE OFFICIAL CATEGORY. "NE" for gaseous fuels, in a country whose
  regulator reports gas and RLNG as 43 percent of thermal fuel energy. The CRT's liquid-fuel
  activity (452,519 TJ) is roughly seven times what the regulator reports for fuel oil and
  diesel together, so some reallocation may be at work - but as filed, the official public-
  electricity category either omits nearly half the fleet's fuel or books it unlabelled.

  THE OFFICIAL SOLID-FUEL LINE AGREES WITH TABLE 3 AND NOT WITH THE STATIONS, AND THAT IS
  NOT CORROBORATION. 324,724 TJ of solid fuel is within 2 percent of the regulator's
  FY2022-23 coal energy (331,553 TJ) and 1.5 times the stations' own metered coal at IPCC
  rank defaults (216,081 TJ), which the inventory now books. This paragraph used to read the
  2 percent as evidence against the coal-NCV diagnostic - "the UNFCCC filing would have to
  overstate it identically". It would: Pakistan's filing is compiled from the same HDIP
  apparent-consumption series Table 3 reports, so the agreement establishes that both
  transcribe one source faithfully and establishes nothing about whether that source is a
  measurement. data/validation_catalog.csv has said so for this row all along (independence
  class `none`), and the inference here contradicted the register it sits beside. Both
  ratios are now returned - solid_ratio_table3_over_crt and solid_ratio_engine_over_crt -
  so neither can be mistaken for the other.

  The implied CO2 factor of 97.57 t/TJ sits between IPCC's bituminous 94.6 and lignite 101.0
  at a 46 percent lignite share - between this paper's superseded 35 percent and its
  ledger-derived 79, dating from 2022 when the Thar fleet was mid-ramp. That reading is
  unaffected: it is a property of the CRT's own emission factor, not of its activity.

The ingestion command re-derives the CSV extracts from the workbook bytes. Runtime
comparisons use those verified extracts, with the archive hash pinned.
"""

from pkinv.assets import asset_path
import hashlib
import io
import os
import zipfile

from pkinv.paths import ROOT
from pkinv.core import documents
from pkinv.core.source_extracts import materialized

CRT_SOURCE = asset_path(ROOT, "sources", "Aviation", "PAK_CRT_2024.zip")
CRT_WORKBOOK = "ENERGY-PAK-CRT.xlsx"
CRT_SHA256 = None   # filled by tests from the committed archive; module recomputes each run

SHEET = "Table1.A(a)s1"
# Row layout verified by inspection: 24 = 1.A.1.a aggregate, then liquid/solid/gas/other.
ROWS = {"1.A.1.a total": 24, "Liquid fuels": 25, "Solid fuels": 26,
        "Gaseous fuels": 27, "Other fossil fuels": 28}
COLS = {"activity_TJ": 2, "basis": 3, "ief_co2_t_per_TJ": 4, "ief_ch4_kg_per_TJ": 5,
        "ief_n2o_kg_per_TJ": 6, "co2_kt": 7, "ch4_kt": 8, "n2o_kt": 9}


def payload_sha256(path=CRT_SOURCE):
    return documents.digest(path, quiet=True)


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None            # notation keys: NE, NA, NO


@materialized("power_extract")
def extract(path=CRT_SOURCE):
    """{row label: {field: value-or-None, 'notation': str-or-None}} for 1.A.1.a."""
    from openpyxl import load_workbook
    documents.require(path, "the UNFCCC CRT tables are read here")
    with zipfile.ZipFile(path) as z:
        wb = load_workbook(io.BytesIO(z.read(CRT_WORKBOOK)), read_only=True, data_only=True)
    ws = wb[SHEET]
    grid = {r: [c.value for c in row]
            for r, row in enumerate(ws.iter_rows(min_row=1, max_row=40, max_col=12), 1)}
    out = {}
    for label, r in ROWS.items():
        row = grid[r]
        rec = {k: _num(row[i]) for k, i in COLS.items() if k != "basis"}
        rec["basis"] = str(row[COLS["basis"]] or "").strip()
        rec["notation"] = (str(row[COLS["activity_TJ"]]).strip()
                           if rec["activity_TJ"] is None else None)
        out[label] = rec
    return out


def arithmetic_check(rows=None):
    """activity x implied EF must reproduce the reported emissions, per fuel and gas.

    The same discipline the fugitives CRT extraction applies: before comparing against the
    filing, prove we are reading the cells the filing computes with.
    """
    rows = rows or extract()
    failures = []
    for label in ("Liquid fuels", "Solid fuels"):
        r = rows[label]
        for gas, ief_key, out_key, scale in (
                ("CO2", "ief_co2_t_per_TJ", "co2_kt", 1e-3),
                ("CH4", "ief_ch4_kg_per_TJ", "ch4_kt", 1e-6),
                ("N2O", "ief_n2o_kg_per_TJ", "n2o_kt", 1e-6)):
            want = r[out_key]
            got = r["activity_TJ"] * r[ief_key] * scale
            if want and abs(got - want) / want > 1e-6:
                failures.append("%s %s: %.6g vs %.6g" % (label, gas, got, want))
    return failures


def comparison(data, rows=None):
    """The CRT against this inventory's FY2022-23 grid, stated at its real comparability.

    Calendar 2022 against fiscal 2022-23 (July 2022-June 2023) - overlapping half-years, so
    this bounds rather than tests, like the EDGAR row. What it CAN say precisely is which
    fuels each side covers and on what basis.
    """
    rows = rows or extract()
    fuel = data.fuel_for(2022)
    ours = {
        "solid_TJ": fuel["Coal"] * data.p("toe_to_tj"),
        # Both sides of the solid-fuel comparison, because the two now differ and which one
        # agrees with the CRT is the finding. The booked account is what this inventory
        # reports; the Table 3 account is what Pakistan's own filing is compiled from.
        "solid_table3_TJ": data.table3_coal_toe(2022) * data.p("toe_to_tj"),
        "liquid_TJ": (fuel["Furnace Oil"] + fuel["Diesel Oil"]) * data.p("toe_to_tj"),
        "gas_TJ": fuel["Gas"] * data.p("toe_to_tj"),
    }
    crt_solid = rows["Solid fuels"]["activity_TJ"]
    lig_share = None
    ief = rows["Solid fuels"]["ief_co2_t_per_TJ"]
    if ief:
        # The implied lignite share of the CRT's own solid-fuel factor, from IPCC endpoints.
        lig_share = (ief - 94.6) / (101.0 - 94.6)
    return {
        "crt_total_TJ": rows["1.A.1.a total"]["activity_TJ"],
        "crt_co2_kt": rows["1.A.1.a total"]["co2_kt"],
        "crt_gas_notation": rows["Gaseous fuels"]["notation"],
        "solid_ratio_engine_over_crt": ours["solid_TJ"] / crt_solid if crt_solid else None,
        "solid_ratio_table3_over_crt": (ours["solid_table3_TJ"] / crt_solid
                                        if crt_solid else None),
        "liquid_ratio_engine_over_crt": (ours["liquid_TJ"]
                                         / rows["Liquid fuels"]["activity_TJ"]),
        "engine_gas_TJ_unmatched_in_crt": ours["gas_TJ"],
        "crt_implied_lignite_share": lig_share,
        "basis": rows["Solid fuels"]["basis"],
    }
