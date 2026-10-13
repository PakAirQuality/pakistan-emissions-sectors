"""The remaining industrial categories as NINE-YEAR screening series - each a full FY2015-16..FY2023-24
series before it may enter any aggregate, each typed for what it is, none inserted anywhere.

  2.B.7  Soda ash.        Pakistan's two producers (LCI Khewra, Olympia) run the SOLVAY process. IPCC 2006
                          Vol 3 s3.8.3.1 allocates Solvay emissions to the ENERGY sector (coke in the lime
                          kilns) and provides NO IPPU method - so 2.B.7 is NA for Pakistan, not a ceiling.
                          The QIM soda-ash series and LCI's reported production are carried so the coke
                          term can be priced under 1.A.2 when coke tonnage is held. The earlier natural-
                          process ceiling (0.0974 t/t) was the wrong method for a Solvay country.
  2.C.1  Iron and steel.  Pig iron is zero from FY2016-17 (QIM): no blast furnace operates, so Tier 1 is
                          the EAF/induction factor (IPCC Vol 3 Table 4.1, 0.08 t CO2/t steel) on QIM
                          billets and ingots (crude steel). Rolled products are downstream and excluded.
                          A point per year under Tier 1; the route uncertainty (scrap-EAF vs DRI-fed) is
                          the named limitation.
  2.D.1  Lubricants.      IPCC Vol 3 Ch 5 Tier 1: CO2 = LC x ODU x 44/12 with LC = tonnes x NCV 40.2 TJ/Gg
                          x 20.0 t C/TJ (Vol 2 Tables 1.2-1.3); ODU 0.2 lubricating oil, 0.05 grease
                          (Table 5.2). Activity: OCAC's non-energy sectoral sales (LUBES, GREASES; M. Tons),
                          FY2015-16 from the 2016-17 edition's previous-year column. Two-stroke use is not
                          separated (Table 5.2's exclusion) - a small upward bias named, not corrected.
  4.D.2  Industrial       IPCC Vol 5 s6.2.3: TOW = P x W x COD; CH4 = TOW x B0 0.25 x MCF. Industries with
         wastewater.      a QIM production series and a Table 6.9 default: sugar (W 4..18 m3/t - no default,
                          the range; COD 3.2 kg/m3) and paper (W 162, COD 9; ranges 85..240 and 1..15). MCF
                          is a BAND (0.1 untreated river discharge .. 0.8 anaerobic; Table 6.8) - treatment
                          is not surveyed. A band per year, no central; coded WASTE, industrial in the
                          economic view only.

Reads:  data/activity/monthly/pbs_qim_month_item.csv, data/activity/industry/ocac_non_energy_sectoral.csv,
        data/raw/company_reports/soda_ash (LCI production, transcribed here from the notes),
        data/ippu_params.csv (steel_eaf_ef)
Writes: outputs/pakemis_industrial_screening_series.csv
"""
import csv
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from pkinv.assets import asset_path

from pkinv.paths import DATA, OUTPUTS  # noqa: E402

QIM = asset_path(DATA, "activity", "monthly", "pbs_qim_month_item.csv")
OCAC = asset_path(DATA, "activity", "industry", "ocac_non_energy_sectoral.csv")
PARAMS = asset_path(DATA, "ippu_params.csv")
OUT = asset_path(OUTPUTS, "pakemis_industrial_screening_series.csv")
YEARS = ["%d-%02d" % (y, (y + 1) % 100) for y in range(2015, 2024)]

# IPCC 2006 defaults, from the held chapters (data/raw/ipcc/)
LUBE_NCV_TJ_PER_KT = 40.2                 # Vol 2 Table 1.2, lubricants
LUBE_C_T_PER_TJ = 20.0                    # Vol 2 Table 1.3, lubricants
ODU_OIL, ODU_GREASE = 0.2, 0.05           # Vol 3 Table 5.2
B0 = 0.25                                 # Vol 5 Table 6.2, kg CH4 / kg COD
MCF_LOW, MCF_HIGH = 0.1, 0.8              # Vol 5 Table 6.8: untreated river discharge .. anaerobic
GWP_CH4_AR5 = 28.0
WASTEWATER = {                            # Vol 5 Table 6.9: (W low, W high, COD low, COD high) m3/t, kg/m3
    "sugar": ("Sugar refining", 4.0, 18.0, 1.0, 6.0, "Sugar, Bakery products and Chocolate & sugar confectionery", "canonical sugar"),
    "paper": ("Pulp and paper (combined)", 85.0, 240.0, 1.0, 15.0, "Paper", "QIM 'Paper' (unit blank; tonnes by magnitude)"),
}
# LCI annual reports (data/raw/company_reports/soda_ash), the notes' "production of ... metric tonnes soda ash"
LCI_SODA_ASH_T = {"2015-16": 337869, "2016-17": 342416, "2017-18": 378248, "2018-19": 422168, "2019-20": 372518,
                  "2020-21": 395609, "2021-22": 443974, "2022-23": 512002, "2023-24": 544572}

FIELDS = ("fiscal_year", "category", "ipcc_code", "sector_code", "activity", "activity_unit", "activity_source",
          "method", "factor", "factor_unit", "central_mt_co2e", "low_mt_co2e", "high_mt_co2e", "band_kind",
          "status", "note")
HEADER = """\
# THE REMAINING INDUSTRIAL CATEGORIES AS NINE-YEAR SCREENING SERIES - full FY2015-16..FY2023-24 before any may enter an
# aggregate. Steel (2.C.1) and lubricants (2.D.1) entered the reference at rc52 - their rows here are the audit
# trail. 2.B.7 soda ash is NA in IPPU for a Solvay country (IPCC Vol 3 s3.8.3.1) - the
# activity is carried for the 1.A.2 coke term. 2.C.1 steel is a Tier 1 point (EAF 0.08 t/t on billets and ingots).
# 2.D.1 lubricants is Tier 1 on OCAC's non-energy sales. 4.D.2 industrial wastewater is a BAND (W, COD and MCF ranges),
# coded Waste, industrial in the economic view only. scripts/build_industrial_screening_series.py
"""


def _rows(path):
    from pkinv.activity.store import read_rows as canonical_rows
    return canonical_rows(path, comments=True)


def _param(name):
    for r in _rows(PARAMS):
        if r[list(r.keys())[0]] == name:
            return float(r[list(r.keys())[1]])
    raise KeyError(name)


def qim_annual(item=None, unit=None, canonical=None):
    agg = defaultdict(float)
    for r in _rows(QIM):
        if r["row_kind"] != "quantity" or not r["quantity"]:
            continue
        if canonical is not None and r["canonical_item"] != canonical:
            continue
        if item is not None and (r["item"].strip() != item or (unit is not None and r["unit"] != unit)):
            continue
        fy = "%s-%02d" % (r["fiscal_year_start"], (int(r["fiscal_year_start"]) + 1) % 100)
        agg[fy] += float(r["quantity"])
    return agg


def ocac_lubes():
    """Grand-total LUBES and GREASES tonnes per fiscal year: the year's own edition where held,
    FY2015-16 from the 2016-17 edition's previous-year column (status carried)."""
    out = {}
    for r in _rows(OCAC):
        if r["section"] != "GRAND TOTAL" or r["product"] not in ("LUBES", "GREASES") or not r["quantity"]:
            continue
        own = "(A+B)" in r["sector_row"]
        key = (r["fiscal_year"], r["product"])
        if own or key not in out:
            out[key] = (float(r["quantity"]), r["status"], r["edition_file"])
    return out


def build():
    eaf = _param("steel_eaf_ef")
    soda = qim_annual("Soda ash", "MT")
    billets = qim_annual("Billets/Ingots", "MT")
    pig = qim_annual("Pig iron", "MT")
    sugar = qim_annual(canonical="sugar")
    paper = qim_annual("Paper")
    lubes = ocac_lubes()
    out = []
    for fy in YEARS:
        # 2.B.7
        if fy in soda:
            out.append({"fiscal_year": fy, "category": "Soda ash production", "ipcc_code": "2.B.7", "sector_code": "ippu",
                        "activity": "%.0f" % soda[fy], "activity_unit": "t soda ash (QIM); LCI reports %s t" % (
                            "{:,}".format(LCI_SODA_ASH_T[fy]) if fy in LCI_SODA_ASH_T else "n/a"),
                        "activity_source": "PBS QIM monthly 'Soda ash' (MT), twelve months summed; LCI annual reports",
                        "method": "IPCC Vol 3 s3.8.3.1: Solvay process - emissions allocated to ENERGY (coke in lime kilns); no IPPU method",
                        "factor": "", "factor_unit": "", "central_mt_co2e": "", "low_mt_co2e": "", "high_mt_co2e": "",
                        "band_kind": "NA (not applicable in IPPU for a Solvay country)",
                        "status": "NA in 2.B.7; the coke term belongs to 1.A.2 and is typed absent until coke tonnage is held",
                        "note": "both producers (LCI Khewra, Olympia) are Solvay; the earlier natural-process ceiling 0.0974 t/t was the wrong method"})
        # 2.C.1
        if fy in billets:
            mt = billets[fy] * eaf / 1e6
            out.append({"fiscal_year": fy, "category": "Iron and steel production", "ipcc_code": "2.C.1", "sector_code": "ippu",
                        "activity": "%.0f" % billets[fy], "activity_unit": "t billets and ingots (crude steel); pig iron %s t" % ("%.0f" % pig.get(fy, 0.0)),
                        "activity_source": "PBS QIM monthly 'Billets/Ingots' (MT), twelve months summed",
                        "method": "IPCC Vol 3 Table 4.1 Tier 1, EAF (no blast furnace operates: pig iron zero from FY2016-17)",
                        "factor": "%.2f" % eaf, "factor_unit": "t CO2/t steel",
                        "central_mt_co2e": "%.5f" % mt, "low_mt_co2e": "%.5f" % mt, "high_mt_co2e": "%.5f" % mt,
                        "band_kind": "Tier 1 point; route limitation named (scrap-EAF/induction vs DRI-fed)",
                        "status": "reference component since rc52 (audit trail; the engine prices the same QIM billets x 0.08)",
                        "note": "rolled products (H/C.R. coils) are downstream of the billet and excluded to avoid double counting"})
        # 2.D.1
        lo_t = lubes.get((fy, "LUBES"))
        gr_t = lubes.get((fy, "GREASES"))
        if lo_t:
            def co2(t, odu):
                return t / 1000.0 * LUBE_NCV_TJ_PER_KT * LUBE_C_T_PER_TJ * odu * 44.0 / 12.0 / 1e6   # kt -> TJ -> t C -> Mt CO2
            mt = co2(lo_t[0], ODU_OIL) + (co2(gr_t[0], ODU_GREASE) if gr_t else 0.0)
            out.append({"fiscal_year": fy, "category": "Lubricant use", "ipcc_code": "2.D.1", "sector_code": "ippu",
                        "activity": "%.0f" % (lo_t[0] + (gr_t[0] if gr_t else 0.0)),
                        "activity_unit": "t lubricants sold (LUBES %.0f + GREASES %s)" % (lo_t[0], "%.0f" % gr_t[0] if gr_t else "n/a"),
                        "activity_source": "OCAC non-energy sectoral sales, grand total (%s; %s)" % (os.path.basename(lo_t[2]), lo_t[1]),
                        "method": "IPCC Vol 3 Ch 5 Tier 1: LC x ODU x 44/12; NCV 40.2 TJ/Gg, 20.0 t C/TJ; ODU 0.2 oil / 0.05 grease",
                        "factor": "%.3f" % (LUBE_NCV_TJ_PER_KT * LUBE_C_T_PER_TJ * ODU_OIL * 44.0 / 12.0 / 1000.0), "factor_unit": "t CO2/t lubricating oil",
                        "central_mt_co2e": "%.5f" % mt, "low_mt_co2e": "%.5f" % mt, "high_mt_co2e": "%.5f" % mt,
                        "band_kind": "Tier 1 point; two-stroke share not separated (upward bias named)",
                        "status": "reference component since rc52 (audit trail; the engine prices the same OCAC sales x ODU)" + ("; FY2015-16 activity from the next edition's previous-year column, unchecked" if lo_t[1] == "unchecked" else ""),
                        "note": "sales are the 2.D activity basis (deliveries, not combustion); lubricants burned in engines are covered by the ODU fraction"})
        # 4.D.2
        for key, (industry, w_lo, w_hi, cod_lo, cod_hi, qim_item, basis) in WASTEWATER.items():
            series = sugar if key == "sugar" else paper
            if fy not in series or not series[fy]:
                continue
            p_t = series[fy]
            tow_lo, tow_hi = p_t * w_lo * cod_lo, p_t * w_hi * cod_hi           # kg COD
            lo = tow_lo * B0 * MCF_LOW * GWP_CH4_AR5 / 1e9                       # kg CH4 -> Mt CO2e
            hi = tow_hi * B0 * MCF_HIGH * GWP_CH4_AR5 / 1e9
            out.append({"fiscal_year": fy, "category": "Industrial wastewater - %s" % industry, "ipcc_code": "4.D.2", "sector_code": "waste",
                        "activity": "%.0f" % p_t, "activity_unit": "t product (%s)" % basis,
                        "activity_source": "PBS QIM monthly, twelve months summed",
                        "method": "IPCC Vol 5 s6.2.3 Tier 1: TOW = P x W x COD; CH4 = TOW x B0 x MCF; W %g..%g m3/t, COD %g..%g kg/m3, MCF %g..%g" % (w_lo, w_hi, cod_lo, cod_hi, MCF_LOW, MCF_HIGH),
                        "factor": "%.2f" % B0, "factor_unit": "kg CH4/kg COD (B0); GWP AR5 28",
                        "central_mt_co2e": "", "low_mt_co2e": "%.5f" % lo, "high_mt_co2e": "%.5f" % hi,
                        "band_kind": "band over W, COD and MCF ranges; no central (treatment and effluent unsurveyed)",
                        "status": "band series (screening; outside every total); coded Waste 4.D.2, industrial in the economic view only",
                        "note": "the ranges are IPCC's own; PCRWR/EPD effluent data would collapse W and COD, a treatment survey would fix MCF"})
    return out


def main():
    rows = build()
    with open(OUT, "w", newline="", encoding="utf-8") as h:
        h.write(HEADER)
        w = csv.DictWriter(h, fieldnames=list(FIELDS), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print("industrial screening series -> %s (%d rows)" % (os.path.relpath(OUT), len(rows)))
    for r in rows:
        if r["fiscal_year"] in ("2015-16", "2023-24"):
            print("  %s %-38s act %12s  central %8s  [%s..%s]" % (r["fiscal_year"], r["category"][:38], r["activity"],
                                                                 r["central_mt_co2e"] or "-", r["low_mt_co2e"] or "-", r["high_mt_co2e"] or "-"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
