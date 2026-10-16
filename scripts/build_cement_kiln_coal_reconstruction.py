#!/usr/bin/env python3
"""WAVE 2b OF THE INDUSTRIAL-COAL RECONSTRUCTION: cement kiln COAL, reconstructed from
clinker, as a BAND per fiscal year - the independent activity constraint on the
"Cement / Cement/Others / Cement/Other Industry" column of HDIP's coal allocation.

    Q_coal,t = K_t x H_t x s_coal,t / NCV_coal,t        (tonnes of coal)

  K_t   domestically produced clinker. For FY2023-24 the audited 16-company census; for
        the eight earlier years the IPCC clinker balance (cement x fraction - imports +
        exports, stocks unresolved) at the CENSUS-DERIVED fraction f* - the FY2023-24
        clinker-in-cement ratio the census itself implies, computed here from held data,
        never typed - beside the legacy 0.75 series for comparison. The census-anchored
        series is the activity basis the user approved for the JOINT re-base (2.A.1 and
        this fuel term on one clinker series); until that re-base lands this column is a
        diagnostic and the reference's 2.A.1 still rides 0.75 for the back-years.
  H_t   kiln heat, GJ/t clinker: 3.0 / 3.4 / 3.8 - the dry-process range international
        audits publish (IEA/WBCSD; GNR ~3.5). TRANSFERRED: no Pakistani kiln heat audit
        is held, and no held company report prints kcal/kg or GJ/t (all 16 searched).
  s_t   coal's share of kiln heat: 0.85 / 0.95 / 1.00. Held evidence: GEM flags 16 of 32
        plants as using alternative fuels (RDF/TDF/biomass, types only); Fauji reports
        69,426 t of AF in FY2023-24 and an 11 percent-BY-HEAT TARGET for FY2024-25, so
        its FY2023-24 share sat materially below 11 percent; petcoke is imported but its
        quantity is not held. A national band, declared; plant-level s is a typed negative.
  NCV   24.0 / 25.8 / 27.0 TJ/Gg - imported bituminous coal around the engine's Other
        Bituminous Coal default (IPCC 2006 Vol 2 Table 1.2). Cement kilns burn imported
        (and some Afghan) coal; Thar lignite does not reach them.

WHAT THE BAND IS FOR. Compared with HDIP's column it gives, per year, the residual
`column - cement band`: where positive it is the OTHER-INDUSTRY coal the column's own
primary label admits (steel, textile, chemical) - retained, never discarded; where the
column falls BELOW the band's floor, the column under-books cement itself. The FY2023-24
screening (13.59 Mt, clinker x 3.4 GJ/t x all-coal EF) is reproduced as the s=1, H=3.4
member so the two products cannot drift apart, and is NOT added to anything: the
replacement configuration cement_kiln_fuel_in_scope already prices it net (+2.80).

Plant-by-plant is a TYPED NEGATIVE: zero of sixteen held annual reports discloses coal
tonnage or kiln heat (coal appears only as PKR). Power Cement's Scope 1 (1.66 / 2.05 Mt,
FY2021/FY2022) is the one single-plant cross-check and is carried as a note.

Nothing here enters any total.

Reads:  data/activity/ippu (census, cement activity, clinker trade), data/activity/industry/coal_by_consumer.csv
Writes: outputs/pakemis_cement_kiln_coal_reconstruction.csv
Usage:  python3 scripts/build_cement_kiln_coal_reconstruction.py [--check]

A PAKISTANI THERMAL INTENSITY NOW EXISTS IN THE LITERATURE, AND IS NOT HELD (2026-09-14). The heat
rate here is transferred, and it has been the weakest joint in this reconstruction since rc53.
Sumair, Ali and Tanzeel-ur-Rashid (Mineral Economics 2026, doi:10.1007/s13563-026-00653-8,
Crossref-confirmed) publish 3.5322 GJ/t clinker and a 99 percent coal energy share on a FY2022-23
basis. The paper is PAYWALLED - the acquisition is logged blocked in
data/raw/ACQUISITION_LOG_industry_boundary.csv - so nothing here rests on it and the transferred
band is unchanged.

Two things are worth recording while it is out of reach. Applied to this release's own
census-anchored clinker the figure implies about 5.69 Mt of kiln coal, which sits INSIDE the band
this module already publishes (3,962 - 6,643 kt, central 5,252) - so the external number is not a
different answer, it is a better-founded one, and obtaining it would narrow the band's BASIS rather
than move its centre. And the paper's own abstract-level totals (3.83 Mtoe sectoral energy, 38.45
MtCO2) are public and consistent with that. See outputs/pakemis_industrial_coal_scenarios.csv,
where the figure is carried as an explicitly unverified external input.
"""
import csv
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from pkinv.assets import asset_path
from pkinv.paths import DATA, OUTPUTS  # noqa: E402
from pkinv.sectors.ippu import cement, trade_evidence  # noqa: E402
from pkinv.sectors.ippu.data import IppuData  # noqa: E402

CONSUMERS = asset_path(DATA, "activity", "industry", "coal_by_consumer.csv")
OUT = asset_path(OUTPUTS, "pakemis_cement_kiln_coal_reconstruction.csv")

HEAT = (3.0, 3.4, 3.8)             # GJ/t clinker, transferred
COAL_SHARE = (0.85, 0.95, 1.00)    # of kiln heat, national band, declared
NCV = (24.0, 25.8, 27.0)           # TJ/Gg, imported bituminous around IPCC OBC
CO2_KG_TJ = 94600.0                # IPCC 2006 Table 2.3 Other Bituminous Coal
LEGACY_FRACTION = 0.75
from pkinv.core.reporting_window import CORE_FY_ENDS
YEARS = CORE_FY_ENDS

PRODUCER_SERIES = asset_path(DATA, "activity", "ippu", "company_clinker_series.csv")
# A kiln cannot fire below its own physics. The lowest figure any held source names for a Pakistani
# line is DG Khan's announced NEW line at 680-690 kcal/kg clinker = 2.85-2.89 GJ/t (a DESIGN target
# for best-available technology, recorded as such in data/acquisition_attempts.csv); the fleet runs
# older wet- and dry-process lines above it. A column implying less than that at a 100 percent coal
# share is not cement kiln fuel.
SEC_DESIGN_FLOOR_GJ_PER_T = 2.85

FIELDS = ("fiscal_year", "cement_kt", "cement_source", "clinker_fraction_legacy", "clinker_fraction_census_derived",
          "clinker_kt_legacy_0p75", "clinker_kt_census_anchored", "clinker_kt_census_actual", "clinker_basis",
          "clinker_imports_kt", "clinker_exports_kt", "stock_change_kt",
          "heat_gj_per_t_low", "heat_gj_per_t_central", "heat_gj_per_t_high",
          "coal_share_low", "coal_share_central", "coal_share_high",
          "ncv_tj_gg_low", "ncv_tj_gg_central", "ncv_tj_gg_high",
          "coal_kt_low", "coal_kt_central", "coal_kt_high",
          "kiln_coal_co2_mt_low", "kiln_coal_co2_mt_central", "kiln_coal_co2_mt_high",
          "screening_reproduced_co2_mt", "hdip_cement_others_kt",
          "residual_kt_low", "residual_kt_central", "residual_kt_high", "residual_reading",
          # rc53 Wave C: the two tests the producers' own books make possible
          "implied_sec_at_full_coal_GJ_per_t", "sec_floor_reading",
          "producer_clinker_kt", "producer_companies", "producer_vs_basis_reading", "note")

BANNER = (
    "# Cement kiln COAL reconstructed from clinker (Wave 2b): Q = K x H x s / NCV as a BAND per fiscal year.",
    "# K is the census (FY2023-24) or the IPCC clinker balance at the CENSUS-DERIVED fraction f* (computed from",
    "# held data, never typed) beside the legacy 0.75; H, s and NCV are declared TRANSFERRED bands (no Pakistani",
    "# kiln heat audit; zero of 16 held company reports prints coal tonnage or kcal/kg). residual = HDIP's",
    "# 'Cement / Cement/Others / Cement/Other Industry' column minus the band: positive = other-industry coal",
    "# the label admits (retained), negative = the column under-books cement. The 13.59 Mt screening is the",
    "# s=1, H=3.4 member (reproduced, never added). rc53 Wave C adds two tests from the producers' own",
    "# books: implied_sec_at_full_coal_GJ_per_t asks what thermal intensity HDIP's cement column would",
    "# imply if EVERY tonne of it were cement kiln fuel (below a kiln's physical floor means the column",
    "# cannot even cover cement, so the other-industry remainder is negative), and producer_clinker_kt",
    "# carries the company-reported clinker where enough companies print it - the FIRST independent test",
    "# of the census-derived back-cast. The thermal band stays TRANSFERRED: a 16-document sweep over ~35",
    "# patterns found ZERO disclosures of kcal/kg, GJ/t or MJ/t (data/activity/ippu/cement_thermal_evidence.csv",
    "# types that negative per company). Nothing enters any total. scripts/build_cement_kiln_coal_reconstruction.py",
)


def _rows(path):
    from pkinv.activity.store import read_rows as canonical_rows
    return canonical_rows(path, comments=True)


def census_derived_fraction(d):
    """f* = (census clinker - exports + imports) / cement, at the reference year."""
    ref = d.year
    cen = d.census_clinker_kt(ref)
    cem = d.cement_activity_kt(d.cement_activity_source(ref), ref)
    v = trade_evidence.require(ref)
    return (cen - v["export_kt"] + v["import_kt"]) / cem


def fmt(x, nd=1):
    return "" if x is None else "%.*f" % (nd, x)


def producer_clinker():
    """Company-reported clinker per fiscal year, and how many companies printed it.

    Only two years are near-complete: most held reports print six or ten years of PURELY FINANCIAL
    "at a glance" data and no production row at all, so the earlier years rest on one to three
    companies and cannot be a national series. Where two consecutive years share a company set, the
    MATCHED ratio is an independent test of the census-derived back-cast - the first this release
    has had."""
    by_year = {}
    if not os.path.exists(PRODUCER_SERIES):
        return by_year
    with open(PRODUCER_SERIES, encoding="utf-8") as h:
        for r in csv.DictReader(l for l in h if not l.startswith("#")):
            if not r["clinker_production_t"]:
                continue
            by_year.setdefault(r["fiscal_year"], {})[r["company"]] = float(r["clinker_production_t"])
    return by_year


def build():
    producers = producer_clinker()
    basis_kt = {}
    d = IppuData()
    f_star = census_derived_fraction(d)
    hdip = {}
    for r in _rows(CONSUMERS):
        if r["consumer"] == "cement" and r["revision_status"] in ("final", "provisional"):
            hdip[int(r["fiscal_year"][:4]) + 1] = float(r["coal_kt"])
    out = []
    for y in YEARS:
        src = d.cement_activity_source(y)
        b75 = cement.clinker_balance(d, year=y, activity_source=src, fraction=LEGACY_FRACTION)
        bfs = cement.clinker_balance(d, year=y, activity_source=src, fraction=f_star)
        try:
            actual = d.census_clinker_kt(y)
        except ValueError:
            actual = None
        k = actual if actual is not None else bfs["clinker_production_kt"]
        basis = ("producer census (16 companies)" if actual is not None
                 else "IPCC clinker balance at the census-derived fraction f* (stocks unresolved, zero assumed)")
        # bands: low = low heat x low share / high NCV ; high = high heat x high share / low NCV
        k_t = k * 1000.0                                   # kt -> t
        def coal_kt(h, s, ncv):
            tj = k_t * h * s / 1000.0                      # t x GJ/t = GJ -> TJ
            return tj / ncv                                # TJ / (TJ/Gg) = Gg = kt
        def co2_mt(h, s):
            return k_t * h * s / 1000.0 * CO2_KG_TJ / 1e9
        c_lo, c_ce, c_hi = coal_kt(HEAT[0], COAL_SHARE[0], NCV[2]), coal_kt(HEAT[1], COAL_SHARE[1], NCV[1]), coal_kt(HEAT[2], COAL_SHARE[2], NCV[0])
        e_lo, e_ce, e_hi = co2_mt(HEAT[0], COAL_SHARE[0]), co2_mt(HEAT[1], COAL_SHARE[1]), co2_mt(HEAT[2], COAL_SHARE[2])
        screening = co2_mt(HEAT[1], 1.0)
        h = hdip.get(y)
        r_lo = (h - c_hi) if h is not None else None       # column minus the band's top
        r_ce = (h - c_ce) if h is not None else None
        r_hi = (h - c_lo) if h is not None else None       # column minus the band's floor
        if h is None:
            reading = "no HDIP column this year"
        elif r_hi < 0:
            reading = "column BELOW the band's floor: HDIP under-books cement coal even with no other industry inside"
        elif r_lo > 0:
            reading = "column ABOVE the band's top: %.0f-%.0f kt of other-industry coal inside the column" % (r_lo, r_hi)
        else:
            reading = "column INSIDE the band: consistent with cement-only at some (H, s, NCV); other-industry share indeterminate"
        # ---- TEST 1: what thermal intensity would HDIP's column imply if it were ALL cement? ----
        fy_label = "%d-%02d" % (y - 1, y % 100)
        k_used = actual if actual else bfs["clinker_production_kt"]
        implied_sec = (h * NCV[1] / k_used) if (h and k_used) else None
        if implied_sec is None:
            sec_reading = ""
        elif implied_sec < SEC_DESIGN_FLOOR_GJ_PER_T:
            sec_reading = ("%.2f GJ/t at a 100 percent coal share - BELOW the %.2f GJ/t design floor of the "
                           "most efficient line any held source names. The column cannot cover cement's own "
                           "kiln fuel, so the other-industry remainder inside it is NEGATIVE: this is not a "
                           "cement-plus-others column in this year, it is a short cement column"
                           % (implied_sec, SEC_DESIGN_FLOOR_GJ_PER_T))
        else:
            sec_reading = ("%.2f GJ/t at a 100 percent coal share - above the %.2f GJ/t design floor, so the "
                           "column can physically cover cement kiln fuel and the remainder above the band is "
                           "other industry" % (implied_sec, SEC_DESIGN_FLOOR_GJ_PER_T))

        # ---- TEST 2: the producers' own books against the census-derived back-cast ---------------
        this_year = producers.get(fy_label, {})
        prod_n = len(this_year)
        prod_kt = sum(this_year.values()) / 1000.0 if this_year else None
        prev_label = "%d-%02d" % (y - 2, (y - 1) % 100)
        prev_year = producers.get(prev_label, {})
        matched = sorted(set(this_year) & set(prev_year))
        prod_reading = ""
        if len(matched) >= 10 and prev_label in basis_kt and basis_kt[prev_label]:
            m_ratio = sum(this_year[c] for c in matched) / sum(prev_year[c] for c in matched)
            b_ratio = k_used / basis_kt[prev_label]
            prod_reading = ("%d companies print both %s and this year: their MATCHED clinker moved x%.5f "
                            "while this release's basis moved x%.5f - the back-cast is %+.2f percent against "
                            "the producers' own books, the first independent test it has had"
                            % (len(matched), prev_label, m_ratio, b_ratio, 100 * (b_ratio / m_ratio - 1)))
        elif prod_n:
            prod_reading = ("only %d compan%s print clinker for this year - most held reports print six or ten "
                            "years of purely financial data and no production row, so this is NOT a national "
                            "series and is carried for coverage only" % (prod_n, "y" if prod_n == 1 else "ies"))
        else:
            prod_reading = ("NO company-reported clinker is held for this year: the sixteen held annual reports "
                            "are FY2024 editions and their multi-year tables reach back only as far as each "
                            "company chooses to print production, which for most is not at all. A typed absence, "
                            "not an untested year - the census-derived back-cast is unchecked here")
        note = []
        if y == d.year:
            note.append("census year; the screening (13.59 Mt) is reproduced by the s=1 H=3.4 all-coal member")
        if y in (2021, 2022):
            note.append("Power Cement Scope 1 cross-check available (1.66 / 2.05 Mt, single plant) - Wave 4")
        basis_kt[fy_label] = k_used
        out.append({
            "fiscal_year": fy_label, "cement_kt": fmt(b75["cement_activity_kt"], 0), "cement_source": src,
            "clinker_fraction_legacy": "%.2f" % LEGACY_FRACTION, "clinker_fraction_census_derived": "%.5f" % f_star,
            "clinker_kt_legacy_0p75": fmt(b75["clinker_production_kt"], 0),
            "clinker_kt_census_anchored": fmt(bfs["clinker_production_kt"], 0),
            "clinker_kt_census_actual": fmt(actual, 0), "clinker_basis": basis,
            "clinker_imports_kt": fmt(bfs["clinker_imports_kt"], 1), "clinker_exports_kt": fmt(bfs["clinker_exports_kt"], 1),
            "stock_change_kt": "",
            "heat_gj_per_t_low": HEAT[0], "heat_gj_per_t_central": HEAT[1], "heat_gj_per_t_high": HEAT[2],
            "coal_share_low": COAL_SHARE[0], "coal_share_central": COAL_SHARE[1], "coal_share_high": COAL_SHARE[2],
            "ncv_tj_gg_low": NCV[0], "ncv_tj_gg_central": NCV[1], "ncv_tj_gg_high": NCV[2],
            "coal_kt_low": fmt(c_lo, 0), "coal_kt_central": fmt(c_ce, 0), "coal_kt_high": fmt(c_hi, 0),
            "kiln_coal_co2_mt_low": fmt(e_lo, 3), "kiln_coal_co2_mt_central": fmt(e_ce, 3), "kiln_coal_co2_mt_high": fmt(e_hi, 3),
            "screening_reproduced_co2_mt": fmt(screening, 3), "hdip_cement_others_kt": fmt(h, 0),
            "residual_kt_low": fmt(r_lo, 0), "residual_kt_central": fmt(r_ce, 0), "residual_kt_high": fmt(r_hi, 0),
            "residual_reading": reading,
            "implied_sec_at_full_coal_GJ_per_t": fmt(implied_sec, 2), "sec_floor_reading": sec_reading,
            "producer_clinker_kt": fmt(prod_kt, 0), "producer_companies": str(prod_n) if prod_n else "",
            "producer_vs_basis_reading": prod_reading,
            "note": "; ".join(note),
        })
    return out, f_star


def render(rows):
    buf = io.StringIO()
    for b in BANNER:
        buf.write(b + "\n")
    w = csv.DictWriter(buf, fieldnames=list(FIELDS), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    rows, f_star = build()
    text = render(rows)
    if "--check" in argv:
        held = open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else ""
        print("cement kiln coal reconstruction: %s" % ("byte-identical" if held == text else "DIFFERS"))
        return 0 if held == text else 1
    with open(OUT, "w", encoding="utf-8", newline="") as h:
        h.write(text)
    print("cement kiln coal reconstruction -> %s (f* = %.5f)" % (OUT, f_star))
    for r in rows:
        print("  %s  K %s kt  coal %s-%s-%s kt  HDIP %s  -> %s" % (
            r["fiscal_year"], r["clinker_kt_census_anchored"] if not r["clinker_kt_census_actual"] else r["clinker_kt_census_actual"],
            r["coal_kt_low"], r["coal_kt_central"], r["coal_kt_high"], r["hdip_cement_others_kt"] or "-", r["residual_reading"][:70]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
