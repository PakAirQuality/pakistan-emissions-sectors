#!/usr/bin/env python3
"""WAVE 1, OUTPUT 2 OF THE INDUSTRIAL-COAL RECONSTRUCTION: the national coal balance,
per fiscal year, in tonnes AND terajoules, with the two hypotheses the reconstruction
rests on TESTED and printed - never adopted.

THE IDENTITY (positive stock change = accumulation):
    Production + Imports - Exports - dStocks
      = Power + Industrial (brick + cement/others) + Household + Losses + Statistical discrepancy

WHAT IS HELD ON EACH SIDE. Supply: Finance Division Table 14.3 imports and production
(Petroleum Division), with PBS Table 3.1A as a second production lane (coal_supply.csv);
UNSD's balance (TJ, calendar year) as the only independent check, carrying the exports,
stock changes ('..' - not available) and statistical difference the Supplement omits.
Consumption: HDIP's allocation (coal_by_consumer.csv) AND, for power, NEPRA's metered
named-station burn (plant_fuel_ledger.csv). The supply figures are EVIDENCE TO ASSESS,
not an unquestionable constraint: FY2023-24 supply is publisher-flagged partial, and
the two production lanes disagree by 300-500 kt in FY2015-16..FY2019-20.

THE TWO HYPOTHESES, TESTED NOT ASSUMED:
  H1  HDIP's sectoral split is a SUPPLY-ORIGIN ALLOCATION: power <- domestic production,
      industry <- imports. Test: |power - production| and |non-power - imports| per year
      against the 2 percent-of-supply tolerance. HDIP's own words (Survey 2025-26 ch.14):
      Thar coal to the Thar plants, other coalfields' coal to brick kilns, imports to
      power and industry.
  H2  The POWER SEAM misallocates: HDIP's estimated power column and NEPRA's metered burn
      disagree with opposite signs in the brick-spike and brick-collapse years. Test: the
      residual per year, and what the metered ORIGIN split implies for non-power coal:
        domestic non-power = production - Thar burned in power
        imported non-power = imports - imported burned in power
      CONFOUND, CARRIED: HDIP may book coal DELIVERED, NEPRA coal BURNED - the residual
      may be plant stockpiling (the Thar ramp), so it is a band with named candidates,
      never moved to bricks by arithmetic. And "production - Thar burned" cannot
      separate NON-THAR coal (the brick-kiln coal HDIP's own rule names) from THAR
      STOCKPILE: Pakistan's two Thar mines (SECMC Block-II, SSRL Block-I) could
      together supply nearly all of FY2023-24's 19.3 Mt production, and BY-FIELD
      production is not held (typed negative; the single most valuable acquisition).
      UNSD independently shows a large unaccounted quantity in exactly these years:
      statistical differences of -191,264 TJ (CY2022) and -103,220 TJ (CY2023).

THE FUEL-QUALITY AXIS. The engine converts every industrial coal tonne at one NCV
(Other Bituminous Coal, 25.8 TJ/Gg). If the coal reaching kilns shifted origin, the
energy - and the CO2 - per tonne shifted with it. The TJ columns therefore carry an
ORIGIN BAND from IPCC 2006 Vol 2 Table 1.2 defaults (lignite 11.9, sub-bituminous 18.9,
other bituminous 25.8 TJ/Gg) - transferred defaults, declared as such, not Pakistani
measurements. This is the "fuel-quality revisions" stage of the Wave 4 bridge.

Nothing here enters any total. Verdicts are printed to stdout and carried per row.

Reads:  data/activity/industry/coal_supply.csv, coal_by_consumer.csv,
        data/activity/power/plant_fuel_ledger.csv, outputs/unsd_coal_supply_control.csv
Writes: outputs/pakemis_coal_balance.csv
Usage:  python3 scripts/build_coal_balance.py [--check]
"""
import csv
import io
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from pkinv.assets import asset_path
from pkinv.paths import DATA, OUTPUTS  # noqa: E402

SUPPLY = asset_path(DATA, "activity", "industry", "coal_supply.csv")
CONSUMERS = asset_path(DATA, "activity", "industry", "coal_by_consumer.csv")
LEDGER = asset_path(DATA, "activity", "power", "plant_fuel_ledger.csv")
UNSD = asset_path(OUTPUTS, "unsd_coal_supply_control.csv")
OUT = asset_path(OUTPUTS, "pakemis_coal_balance.csv")

YEARS = ["2015-16", "2016-17", "2017-18", "2018-19", "2019-20", "2020-21", "2021-22",
         "2022-23", "2023-24", "2024-25"]
NCV_ENGINE = 25.8            # TJ/Gg, Other Bituminous Coal - the engine's single bucket
NCV_LIGNITE = 11.9           # IPCC 2006 Vol 2 Table 1.2 defaults (transferred; declared)
NCV_SUBBIT = 18.9
NCV_OBC = 25.8
H1_TOL = 0.02                # 2 percent of total supply
# ORIGIN-RESOLVED CALORIFIC VALUES (rc53 Wave B). A tonnage account can close while the ENERGY
# account does not, because Pakistan's coal changed origin across the window: the Thar ramp is
# lignite and the industrial lane is imported bituminous. Thar's own measured quality is held
# (data/emission_factors.csv: about 3,030 kcal/kg at 46 percent moisture = 12.7 TJ/Gg); the other
# two are IPCC defaults, transferred and declared as such.
NCV_THAR = 12.7              # measured (SECMC/NEPRA, via data/emission_factors.csv)
NCV_DOMESTIC_NON_THAR = (NCV_LIGNITE, NCV_SUBBIT)     # Balochistan/Punjab/KP: a band, not a value
NCV_IMPORTED = (NCV_SUBBIT, NCV_OBC)                  # Indonesian sub-bituminous .. South African OBC
ENERGY_TOL = 0.05            # 5 percent of supply energy: below this the energy account "closes"

FIELDS = (
    "fiscal_year",
    # supply (kt)
    "imports_kt", "production_kt_petroleum_division", "production_kt_pbs", "production_lanes_gap_kt",
    "total_supply_kt", "supply_reporting_period",
    # consumption, HDIP (kt)
    "hdip_power_kt", "hdip_brick_kt", "hdip_cement_others_kt", "hdip_household_kt", "hdip_total_kt",
    "hdip_nonpower_kt", "closure_supply_minus_hdip_total_kt",
    # consumption, NEPRA metered power (kt)
    "nepra_power_kt", "nepra_power_thar_kt", "nepra_power_imported_kt", "nepra_power_unknown_origin_kt",
    "nepra_plants", "power_residual_hdip_minus_nepra_kt",
    # H1
    "h1_power_minus_production_kt", "h1_nonpower_minus_imports_kt", "h1_verdict",
    # H2
    "nepra_anchored_nonpower_kt", "domestic_nonpower_implied_kt", "imported_nonpower_implied_kt", "h2_verdict",
    "production_sindh_kt", "production_nonsindh_kt", "thar_stock_proxy_kt", "domestic_non_thar_coal_kt",
    "hdip_brick_minus_domestic_non_thar_kt", "h3_verdict",
    # THE IDENTITY, WITH THE RESIDUAL RETAINED (rc53 Wave B)
    "identity_production_kt", "identity_imports_kt", "identity_exports_kt", "identity_stock_change_kt",
    "identity_supply_kt", "identity_consumption_kt", "identity_residual_R_kt",
    "power_lane_low_kt", "power_lane_high_kt", "power_lane_basis",
    # the same identity in ENERGY, origin-resolved (a tonnage that closes can still fail here)
    "supply_TJ_low", "supply_TJ_high", "consumption_TJ_low", "consumption_TJ_high",
    "residual_R_TJ_low", "residual_R_TJ_high", "engine_priced_nonpower_TJ", "supply_use_reading",
    # stocks / discrepancy
    "stock_change_kt", "statistical_discrepancy_note",
    # energy lane
    "hdip_nonpower_TJ_engine_ncv", "hdip_nonpower_TJ_if_lignite", "hdip_nonpower_TJ_if_subbituminous",
    "hdip_nonpower_TJ_if_other_bituminous",
    # UNSD cross-check (TJ, calendar years straddling the FY)
    "unsd_cy_start", "unsd_start_total_supply_TJ", "unsd_start_statistical_difference_TJ",
    "unsd_start_final_non_metallic_TJ", "unsd_cy_end", "unsd_end_total_supply_TJ",
    "unsd_end_statistical_difference_TJ", "unsd_end_final_non_metallic_TJ",
    "note",
)

BANNER = (
    "# National COAL BALANCE per fiscal year (Wave 1, Output 2): supply lanes vs HDIP's allocation vs NEPRA's",
    "# metered power burn, in kt and TJ, with H1 (supply-origin allocation) and H2 (power-seam misallocation)",
    "# TESTED per year and printed as verdicts. Stock change is NOT PUBLISHED by any held source (UNSD '..'),",
    "# so it is carried as an unresolved term, never zero; the HDIP-NEPRA residual is a band with named",
    "# candidates, never moved to bricks by arithmetic. TJ columns carry an IPCC-default ORIGIN BAND (the",
    "# fuel-quality axis), declared transferred. rc53 Wave B adds the IDENTITY with its residual R",
    "# RETAINED as a column (exports and stock change typed, never zeroed), the power lane as a BAND",
    "# [NEPRA metered .. HDIP allocated] so industry is not made to absorb the seam, and an",
    "# origin-resolved energy account - whose band is reported as a WIDTH because two of its three",
    "# calorific values are IPCC defaults and cannot fail. Nothing here enters any total.",
    "# scripts/build_coal_balance.py",
)


def _rows(path):
    from pkinv.activity.store import read_rows as canonical_rows
    return canonical_rows(path, comments=True)


def _f(x):
    return float(x) if x not in (None, "") else None


def fmt(x, nd=1):
    return "" if x is None else ("%.*f" % (nd, x))


PROVINCE = asset_path(DATA, "activity", "industry", "coal_production_by_province.csv")


def _province_lanes():
    """Sindh vs non-Sindh production per fiscal year from the PBS by-province table (the public
    by-field proxy: Sindh is Thar plus Lakhra/Sonda; every other field is non-Sindh). Where two
    editions print a year the values agree to the tonne; the first is taken."""
    sindh, total = {}, {}
    if not os.path.exists(PROVINCE):
        return sindh, total
    for r in _rows(PROVINCE):
        fy = r["fiscal_year"].replace("FY", "")
        if r["province_canonical"] == "Sindh" and fy not in sindh:
            sindh[fy] = float(r["production_tonnes"]) / 1000.0
        if r["province_canonical"] == "Pakistan" and fy not in total:
            total[fy] = float(r["production_tonnes"]) / 1000.0
    return sindh, total


def build():
    sindh_kt, prov_total_kt = _province_lanes()
    supply = {r["fiscal_year"]: r for r in _rows(SUPPLY)
              if r["period_coverage"] == "full_year" and r["revision_status"] != "superseded_provisional"}
    official = defaultdict(dict)
    for r in _rows(CONSUMERS):
        if r["revision_status"] in ("final", "provisional"):
            official[r["fiscal_year"]][r["consumer"]] = _f(r["coal_kt"])
    nepra = defaultdict(lambda: defaultdict(float))
    plants = defaultdict(set)
    for r in _rows(LEDGER):
        if r["fuel"].lower() == "coal" and r["quantity_unit"].strip() == "000 t":
            fy = "%s-%02d" % (r["fiscal_year"], (int(r["fiscal_year"]) + 1) % 100)
            nepra[fy][r["fuel_origin"] or "unknown"] += float(r["quantity"])
            nepra[fy]["total"] += float(r["quantity"])
            plants[fy].add(r["plant"])
    unsd = {}
    if os.path.exists(UNSD):
        for r in _rows(UNSD):               # later editions overwrite earlier for the same year
            unsd[int(r["calendar_year"])] = r

    out, verdicts = [], []
    for fy in YEARS:
        s = supply.get(fy, {})
        imp = _f(s.get("coal_imports_kt"))
        prod1 = _f(s.get("coal_production_kt_petroleum_division"))
        prod2 = _f(s.get("coal_production_kt_pbs_extraction"))
        total = (imp + prod1) if imp is not None and prod1 is not None else None
        o = official.get(fy, {})
        hp, hb, hc, hh = o.get("power"), o.get("brick_kilns"), o.get("cement"), (o.get("household") or 0.0)
        ht = o.get("total")
        hnp = (hb or 0.0) + (hc or 0.0) + hh if hb is not None and hc is not None else None
        n = nepra.get(fy)
        nt = n["total"] if n else None
        n_thar = n.get("Thar lignite", 0.0) if n else None
        n_imp = n.get("imported", 0.0) if n else None
        n_unk = n.get("unknown", 0.0) if n else None
        resid = (hp - nt) if hp is not None and nt is not None else None

        # H1
        d_pp = (hp - prod1) if hp is not None and prod1 is not None else None
        d_ni = (hnp - imp) if hnp is not None and imp is not None else None
        if total and d_pp is not None and d_ni is not None:
            tol = H1_TOL * total
            h1 = ("MATCH: power~=production and non-power~=imports within %.0f kt" % tol
                  if abs(d_pp) <= tol and abs(d_ni) <= tol else
                  "BREAK: power-production %+.0f, non-power-imports %+.0f kt (tol %.0f)" % (d_pp, d_ni, tol))
        else:
            h1 = "n/a"

        # H2
        if nt is not None and total is not None:
            nepra_np = total - nt - hh
            dom_np = (prod1 - n_thar) if prod1 is not None else None
            imp_np = (imp - n_imp) if imp is not None else None
            h2 = ("residual %+.0f kt (%s); NEPRA-anchored non-power %.0f vs HDIP %.0f; implied domestic "
                  "non-power %.0f (production - Thar burned: NON-THAR coal OR THAR STOCKPILE - by-field "
                  "production not held), imported non-power %.0f (imports - imported burned; %.0f kt of "
                  "origin-unknown burn unassigned); candidates: plant/mine stock change, FFBL Power "
                  "(~118 MW, unnamed), misallocation - a BAND, not a transfer"
                  % (resid, "HDIP above metered" if resid > 0 else "metered above HDIP", nepra_np,
                     hnp if hnp is not None else float("nan"), dom_np if dom_np is not None else float("nan"),
                     imp_np if imp_np is not None else float("nan"), n_unk))
        else:
            nepra_np = dom_np = imp_np = None
            h2 = "n/a (no NEPRA lane)"

        # H3 - the by-province lane. HDIP's own footnote makes the brick column a residual of
        # INDIGENOUS production ("Estimated by deducting other uses of indigenous coal from the
        # total production"), so the most domestic coal bricks could burn is everything mined
        # that Thar plants did not: domestic_non_thar = production - NEPRA's Thar burn (Sindh
        # includes Lakhra/Sonda, which do reach kilns; Thar lignite does not). An official brick
        # value ABOVE that ceiling cannot be domestic coal under HDIP's definition - it is
        # imported coal booked into the residual, or the residual artefact of an under-booked
        # power column (H2). Sindh production minus Thar burned is the Thar STOCK proxy.
        s_kt = sindh_kt.get(fy)
        p_kt = prov_total_kt.get(fy)
        ns_kt = (p_kt - s_kt) if p_kt is not None and s_kt is not None else None
        thar_stock = (s_kt - n_thar) if s_kt is not None and n_thar is not None else None
        dom_non_thar = (p_kt - n_thar) if p_kt is not None and n_thar is not None else None
        brick_gap = (hb - dom_non_thar) if hb is not None and dom_non_thar is not None else None
        if brick_gap is not None:
            h3 = ("EXCEEDS the domestic ceiling by %+.0f kt: the official brick residual is larger than ALL "
                  "coal mined outside Thar plants' burn - not domestic coal under HDIP's own definition "
                  "(imported coal in the residual, or the artefact of under-booked power, H2 %+.0f)" % (brick_gap, resid)
                  if brick_gap > 0 else
                  "within the domestic ceiling (%.0f kt of headroom); Sindh minus Thar burned %+.0f kt = Thar "
                  "stock proxy (plus Lakhra/Sonda to kilns)" % (-brick_gap, thar_stock))
        elif hb is not None and ns_kt is not None:
            h3 = ("no NEPRA lane: non-Sindh production %.0f kt vs official brick %.0f (%+.0f); Sindh %.0f kt "
                  "pre-Thar is Lakhra/Sonda" % (ns_kt, hb, hb - ns_kt, s_kt))
        else:
            h3 = "n/a"
        cy0, cy1 = int(fy[:4]), int(fy[:4]) + 1
        u0, u1 = unsd.get(cy0, {}), unsd.get(cy1, {})
        stock_note = ("not published: Supplement prints no stock line; UNSD prints '..' - carried unresolved, "
                      "never zero")
        disc = ("supply - HDIP total = %s kt (forced closure: the two tables balance by construction)"
                % fmt(total - ht if total is not None and ht is not None else None))
        note = []
        if fy == "2023-24":
            note.append("supply publisher-flagged PARTIAL (Balochistan to Mar 2024; Punjab+Sindh to Feb 2024; "
                        "imports to Jan 2024) - audit coverage, never multiply up")
        if prod1 is not None and prod2 is not None and abs(prod1 - prod2) > 100:
            note.append("production lanes disagree by %+.0f kt (Petroleum Division minus PBS)" % (prod1 - prod2))
        # ---- THE IDENTITY, WITH ITS RESIDUAL RETAINED (rc53 Wave B) --------------------------
        # P + M - X - dS = C_power + C_cement + C_brick + C_other + R, and R is a COLUMN, never
        # allocated to a user. Exports and stock change are not published by any held source, so
        # they are typed rather than zeroed - which is itself the reason R cannot be read as
        # "missing coal" on its own.
        exports = "not_published (no held source prints a coal export line; Pakistan is a net importer)"
        supply_kt = total
        consumption_kt = ht
        residual_kt = (supply_kt - consumption_kt) if (supply_kt is not None and consumption_kt is not None) else None
        # THE POWER LANE IS A BAND, NOT A FIXED POINT. HDIP's power column is an allocation and
        # NEPRA's is metered burn; they disagree with opposite signs in the brick-spike years, and
        # holding either fixed would force industry to absorb the difference.
        power_lo = min(x for x in (hp, nt) if x is not None) if (hp is not None or nt is not None) else None
        power_hi = max(x for x in (hp, nt) if x is not None) if (hp is not None or nt is not None) else None
        power_basis = ("NEPRA metered burn .. HDIP allocation" if (hp is not None and nt is not None)
                       else "one lane only" if power_lo is not None else "")

        # ---- the same identity in ENERGY, resolved by ORIGIN ---------------------------------
        def _band(kt, ncv):
            if kt is None:
                return None, None
            lo, hi = (ncv, ncv) if isinstance(ncv, float) else ncv
            return kt * lo, kt * hi

        thar_lo, thar_hi = _band(n_thar, NCV_THAR)
        dnt_lo, dnt_hi = _band(dom_non_thar, NCV_DOMESTIC_NON_THAR)
        imp_lo, imp_hi = _band(imp, NCV_IMPORTED)
        supply_tj_lo = supply_tj_hi = None
        if None not in (thar_lo, dnt_lo, imp_lo):
            supply_tj_lo, supply_tj_hi = thar_lo + dnt_lo + imp_lo, thar_hi + dnt_hi + imp_hi
        # consumption: the metered power burn at its own origins, the rest at the industrial band
        cons_lo = cons_hi = None
        if n_thar is not None and n_imp is not None and hnp is not None:
            p_thar_lo, p_thar_hi = _band(n_thar, NCV_THAR)
            p_imp_lo, p_imp_hi = _band(n_imp, NCV_IMPORTED)
            p_unk_lo, p_unk_hi = _band(n_unk or 0.0, (NCV_LIGNITE, NCV_OBC))
            np_lo, np_hi = _band(hnp, (NCV_LIGNITE, NCV_OBC))
            cons_lo = p_thar_lo + p_imp_lo + p_unk_lo + np_lo
            cons_hi = p_thar_hi + p_imp_hi + p_unk_hi + np_hi
        r_tj_lo = (supply_tj_lo - cons_hi) if None not in (supply_tj_lo, cons_hi) else None
        r_tj_hi = (supply_tj_hi - cons_lo) if None not in (supply_tj_hi, cons_lo) else None

        # ---- the decisive reading -------------------------------------------------------------
        # Is industrial coal MISSING from the account, or merely DIVIDED WRONGLY between users?
        # They need different corrections, so the verdict names which one the evidence supports.
        if residual_kt is None:
            reading = "undetermined (a supply or consumption lane is not published for this year)"
        elif h3.startswith("EXCEEDS"):
            reading = ("MISDIVIDED between users: the tonnage account closes (R = %+.0f kt) but the brick "
                       "column exceeds every tonne of domestic coal mined outside the Thar plants' burn, "
                       "so that coal cannot be what HDIP's own footnote says it is" % residual_kt)
        elif supply_tj_lo is not None and abs(residual_kt) < ENERGY_TOL * (supply_kt or 1) and (r_tj_lo or 0) <= 0 <= (r_tj_hi or 0):
            # AN ENERGY BAND THIS WIDE CANNOT FAIL, AND SAYING SO IS THE POINT. Two of the three
            # calorific values are IPCC defaults spanning lignite to other bituminous, so the band
            # is about half the supply energy; it spans zero for every year and would span zero for
            # almost any allocation. It is reported as a width, not as a passed test - the test
            # becomes real only when Pakistani coal qualities are measured by origin.
            width = (r_tj_hi - r_tj_lo) / supply_tj_hi if supply_tj_hi else 0.0
            reading = ("CLOSES in tonnes (R = %+.0f kt, and the two tables balance BY CONSTRUCTION so "
                       "this is a transcription check, not evidence). The origin-resolved energy "
                       "residual spans %+.0f .. %+.0f TJ, a band %.0f percent as wide as supply energy: "
                       "%s. Nothing is missing from the national account at this resolution; what the "
                       "account cannot test is how the closed total is DIVIDED between users"
                       % (residual_kt, r_tj_lo, r_tj_hi, 100 * width,
                          "too wide to fail, so it is a width and not a verdict" if width > 0.10
                          else "narrow enough to be informative"))
        elif supply_tj_lo is not None and not ((r_tj_lo or 0) <= 0 <= (r_tj_hi or 0)):
            reading = ("TONNES CLOSE BUT ENERGY DOES NOT: R = %+.0f kt against an origin-resolved energy "
                       "residual of %+.0f .. %+.0f TJ that does not span zero - the tonnage allocation and "
                       "the calorific values it implies are not simultaneously satisfiable"
                       % (residual_kt, r_tj_lo, r_tj_hi))
        else:
            reading = ("undetermined: R = %+.0f kt in tonnes and the origin-resolved energy lane is "
                       "incomplete for this year (no NEPRA origin split)" % residual_kt)

        verdicts.append((fy, h1, h2))
        out.append({
            "fiscal_year": fy,
            "imports_kt": fmt(imp, 0), "production_kt_petroleum_division": fmt(prod1, 0),
            "production_kt_pbs": fmt(prod2, 0),
            "production_lanes_gap_kt": fmt(prod1 - prod2, 0) if prod1 is not None and prod2 is not None else "",
            "total_supply_kt": fmt(total, 0),
            "supply_reporting_period": s.get("reporting_period_note", "") or "full fiscal year",
            "hdip_power_kt": fmt(hp), "hdip_brick_kt": fmt(hb), "hdip_cement_others_kt": fmt(hc),
            "hdip_household_kt": fmt(hh), "hdip_total_kt": fmt(ht), "hdip_nonpower_kt": fmt(hnp),
            "closure_supply_minus_hdip_total_kt": fmt(total - ht if total is not None and ht is not None else None),
            "nepra_power_kt": fmt(nt), "nepra_power_thar_kt": fmt(n_thar), "nepra_power_imported_kt": fmt(n_imp),
            "nepra_power_unknown_origin_kt": fmt(n_unk), "nepra_plants": str(len(plants[fy])) if n else "",
            "power_residual_hdip_minus_nepra_kt": fmt(resid),
            "h1_power_minus_production_kt": fmt(d_pp, 0), "h1_nonpower_minus_imports_kt": fmt(d_ni, 0),
            "h1_verdict": h1,
            "nepra_anchored_nonpower_kt": fmt(nepra_np, 0), "domestic_nonpower_implied_kt": fmt(dom_np, 0),
            "imported_nonpower_implied_kt": fmt(imp_np, 0), "h2_verdict": h2,
            "production_sindh_kt": fmt(s_kt, 0), "production_nonsindh_kt": fmt(ns_kt, 0),
            "thar_stock_proxy_kt": fmt(thar_stock, 0), "domestic_non_thar_coal_kt": fmt(dom_non_thar, 0),
            "hdip_brick_minus_domestic_non_thar_kt": fmt(brick_gap, 0), "h3_verdict": h3,
            "identity_production_kt": fmt(prod1, 0), "identity_imports_kt": fmt(imp, 0),
            "identity_exports_kt": exports,
            "identity_stock_change_kt": ("not_published; Thar stock proxy %s kt is a PARTIAL candidate"
                                         % fmt(thar_stock, 0) if thar_stock is not None else "not_published"),
            "identity_supply_kt": fmt(supply_kt, 0), "identity_consumption_kt": fmt(consumption_kt, 0),
            "identity_residual_R_kt": fmt(residual_kt, 1),
            "power_lane_low_kt": fmt(power_lo, 0), "power_lane_high_kt": fmt(power_hi, 0),
            "power_lane_basis": power_basis,
            "supply_TJ_low": fmt(supply_tj_lo, 0), "supply_TJ_high": fmt(supply_tj_hi, 0),
            "consumption_TJ_low": fmt(cons_lo, 0), "consumption_TJ_high": fmt(cons_hi, 0),
            "residual_R_TJ_low": fmt(r_tj_lo, 0), "residual_R_TJ_high": fmt(r_tj_hi, 0),
            "engine_priced_nonpower_TJ": fmt(hnp * NCV_ENGINE if hnp is not None else None, 0),
            "supply_use_reading": reading,
            "stock_change_kt": "", "statistical_discrepancy_note": stock_note + "; " + disc,
            "hdip_nonpower_TJ_engine_ncv": fmt(hnp * NCV_ENGINE if hnp is not None else None, 0),
            "hdip_nonpower_TJ_if_lignite": fmt(hnp * NCV_LIGNITE if hnp is not None else None, 0),
            "hdip_nonpower_TJ_if_subbituminous": fmt(hnp * NCV_SUBBIT if hnp is not None else None, 0),
            "hdip_nonpower_TJ_if_other_bituminous": fmt(hnp * NCV_OBC if hnp is not None else None, 0),
            "unsd_cy_start": str(cy0) if u0 else "", "unsd_start_total_supply_TJ": u0.get("total_energy_supply_TJ", ""),
            "unsd_start_statistical_difference_TJ": u0.get("statistical_difference_TJ", ""),
            "unsd_start_final_non_metallic_TJ": u0.get("final_non_metallic_minerals_TJ", ""),
            "unsd_cy_end": str(cy1) if u1 else "", "unsd_end_total_supply_TJ": u1.get("total_energy_supply_TJ", ""),
            "unsd_end_statistical_difference_TJ": u1.get("statistical_difference_TJ", ""),
            "unsd_end_final_non_metallic_TJ": u1.get("final_non_metallic_minerals_TJ", ""),
            "note": "; ".join(note),
        })
    return out, verdicts


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
    rows, verdicts = build()
    text = render(rows)
    if "--check" in argv:
        held = open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else ""
        print("coal balance: %s" % ("byte-identical" if held == text else "DIFFERS"))
        return 0 if held == text else 1
    with open(OUT, "w", encoding="utf-8", newline="") as h:
        h.write(text)
    print("coal balance -> %s" % OUT)
    for fy, h1, h2 in verdicts:
        print("  %s  H1 %s" % (fy, h1))
        print("  %s  H2 %s" % (" " * len(fy), h2[:150]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
