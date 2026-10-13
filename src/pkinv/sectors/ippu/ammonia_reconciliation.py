"""Four independent ammonia-activity pathways, kept apart on purpose.

THE TABLE DOES NOT AVERAGE. Four ways of asking "how much ammonia does Pakistan make"
give four different answers, and the difference is the finding: an average would bury the
inconsistency this table exists to locate. No pathway here is a national estimate, none
enters ippu_totals or the national rollup, and 2.B.1 stays NE until the pathways agree.

THE RED FLAG, ARITHMETICALLY. Pakistan's 2022 CRT reports 11,467.472 kt of ammonia
(Table2(I).A-H row 21; the arithmetic of activity x factor - recovery reproduces to
1e-12). But making a tonne of ammonia from gas takes about 37.5 GJ of gas, feed and fuel
together, and the ENTIRE fertilizer sector drew 274,449 MMCF in FY2023-24 - 751.9 MMCFD
on NFDC's plant meters, 756 on OGRA's utility table - and 281,153 MMCF in FY2024-25. On
the sector's own billing basis that gas supports roughly 6.3-7.1 Mt of ammonia even if
every cubic foot served ammonia production - and it did not, since the same gas also made
nitric acid heat and ran Hazara's phosphate line. Reaching 11.5 Mt would need roughly
1,240 MMCFD at 1,000 Btu/scf, over half again what the sector draws. The official
activity looks less like ammonia output than like a total-fertilizer-product or capacity
figure - the exact substitution the IPPU paper warns against. The CRT recovery term, by
contrast, implies 6,442 kt of urea, which is the right neighbourhood of NFDC's audited
production; the suspect leg is the activity, not the recovery.

THE REFERENCE YEAR IS NOW MEASURED TWICE. The gas pathway carries two rows for FY2023-24,
not one: OGRA's regulator-side 756 MMCFD and NFDC's Annex-28 at 751.9, a manufacturers'
association counting its members' plant meters. Nothing upstream is shared and they agree
to 0.54 percent. They are kept apart for the same reason the four pathways are kept
apart - an average would hide the one property that makes a cross-source check worth
anything, which is that two records were made independently and still landed together.
Round 11 had only the OGRA figure and borrowed the FOLLOWING year's feed/fuel shares to
describe this one; the annex makes the reference year observed and the borrowing is
withdrawn.

WHAT EACH PATHWAY IS FOR (roles fixed 2026-09-10 at the user's direction, once the
Tier-1 calibrated estimate settled the category):
  * PRODUCT stoichiometry - the PRIMARY national activity estimate. Converts NFDC's
    production by product into embodied ammonia by nitrogen stoichiometry (~4.45 Mt
    NH3); the Tier-1 2.B.1 calculation (chemicals_screening.ammonia_rows) anchors on
    it. Misses merchant ammonia and trade, so it is a strong floor-to-central, not a
    ceiling.
  * NFDC NITROGEN x 17/14 - the PREFERRED INDEPENDENT VALIDATION, arguably the cleaner
    activity series (national nitrogen production, one number, no product weighting);
    it corroborates the product reconstruction to within a rounding.
  * GAS balance - a QA CHECK ONLY until ammonia versus downstream gas is allocated. It
    bounds from above (the same gas also made nitric acid and urea), so it caps but
    does not estimate.
  * CRT 11,470 kt - QUARANTINED. It is almost certainly a misread, misalignment or a
    different quantity: an official workbook cannot imply 19.4 Mt while the same
    country's BTR publishes 3.02 Mt for the same IPCC category. Documented as an
    apparent official inconsistency, never adopted as an input.
  * PLANT census - FACILITY-DISAGGREGATION work (per-plant actuals for spatial and
    attribution use), not a national floor or a competing national estimate.

THE UREA BRIDGE, separately, is the cross-sector identity: production + imports -
exports +/- stock change = agricultural use + other uses. IPPU's recovery term rides
urea PRODUCED; agriculture's 3.H rides urea APPLIED; the two reconcile through the
bridge and must never be forced equal - the residual is inventories and industrial use,
and zeroing it would fabricate agreement.
"""
from __future__ import annotations

from pkinv.activity.store import input_exists as _input_exists
from pkinv.activity.store import read_rows as _activity_rows
import csv
import os

from pkinv.core.units import mmcfd_to_TJ
from pkinv.paths import DATA
from pkinv.sectors.ippu import chemicals
from pkinv.assets import asset_path


def _gross_to_net():
    """The industry sector's gross-to-net ratio, read from its parameter file.

    The gas pathway converts the same billed gas the industry sector reads, so it must
    ride the same ratio - a copied literal here would drift the day that file moves.
    """
    rows = {row["param"]: float(row["value"]) for row in _activity_rows(asset_path(DATA, "industry_params.csv"), comments=False)}
    return rows["industry_gross_to_net"]

DIAGNOSTIC = ("diagnostic pathway; not a national estimate; pathways disagree and the "
              "table exists to locate the inconsistency")

# OGRA State of the Regulated Petroleum Industry 2023-24, Table 3.31, Fertiliser row.
# Deliberately NOT a row in data/activity/industry/gas_consumption.csv: the industry
# sector books every stream in that file as 1.A.2 combustion, and this gas belongs to
# 2.B.1 whole. Holding it here keeps the trap shut.
OGRA_FERTILIZER_MMCFD_FY2023_24 = 756.0
OGRA_SOURCE = "OGRA State of the Regulated Petroleum Industry 2023-24 Table 3.31"

# rc42 (the twentieth review's P-3): the CO2 recovered into urea is production x 44/60
# exactly (CO(NH2)2, IPCC 2006 Vol 3 Eq 3.10); the four-digit 0.7333 that
# data/ippu_params.csv used to carry moved the bridge by 0.22 kt CO2. The params row stays
# as documentation of the same ratio; the arithmetic reads this constant.
UREA_CO2_RECOVERY = 44.0 / 60.0

TABLE5_SOURCE = ("NFDC AFR 2024-25 Table 5 "
                 "(data/nfdc/afr2025_offtake_by_product.csv)")
NFDC_ANNEX28_SOURCE = ("NFDC AFR 2024-25 Annex-28, monthly plant-wise gas "
                       "(data/nfdc/afr2025_fertilizer_gas_monthly.csv)")

HHV_LOW_BTU, HHV_HIGH_BTU = 900.0, 1000.0    # the industry sector's published band

# July-June, so a fiscal year's months sort in the order the annex prints them.
MONTH_ORDER = ("Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
               "Jan", "Feb", "Mar", "Apr", "May", "Jun")


def _production_kt(data, product, fiscal_year):
    return sum(float(r["production_000t"])
               for r in data.fertilizer_production_rows
               if r["product"] == product and r["fiscal_year"] == fiscal_year
               and str(r["production_000t"]).strip())


ANNEX5 = asset_path(DATA, "nfdc", "annex5_national_month_product.csv")


def _annex5_urea_kt(fiscal_year):
    """Urea offtake for a fiscal year from Annex-5's printed national monthly row, in kt;
    None when the year is not in the file."""
    from pkinv.activity.store import read_rows
    if not _input_exists(ANNEX5):
        return None
    tonnes = [float(r["offtake_product_tonnes"]) for r in read_rows(ANNEX5, comments=False)
              if r["product"] == "Urea" and r["fiscal_year"] == fiscal_year]
    return sum(tonnes) / 1000.0 if len(tonnes) == 12 else None


def _offtake_kt(data, product, fiscal_year, supply_basis=None):
    """Offtake for one product, optionally one supply basis, from the extracted Table 5."""
    return sum(float(r["offtake_kt"]) for r in data.fertilizer_offtake_rows
               if r["product"] == product and r["fiscal_year"] == fiscal_year
               and (supply_basis is None or r["supply_basis"] == supply_basis)
               and str(r["offtake_kt"]).strip())


def _nfdc_gas_mmcf(data, fiscal_year, consumption=None):
    """Fertilizer-sector gas from Annex-28's monthly cells, summed rather than quoted.

    The printed year lines are asserted at extraction; the reconciliation reads the
    component rows, so there is one path from the annex to every figure here.
    """
    return sum(float(r["mmcf"]) for r in data.fertilizer_gas_monthly_rows
               if r["fiscal_year"] == fiscal_year
               and (consumption is None or r["consumption"] == consumption)
               and str(r["mmcf"]).strip())


def urea_recovery(urea_production_kt, recovery_factor, nh3_per_urea):
    """The one leg urea production determines directly: CO2 recovered, and an NH3 floor."""
    return {
        "recovered_co2_kt": urea_production_kt * recovery_factor,
        "nh3_floor_kt": urea_production_kt * nh3_per_urea,
    }


def _implied(nh3_kt, gross_ef, recovered_kt):
    component, ledger = chemicals.ammonia_component(
        nh3_kt, gross_ef, recovered_to_urea_kt=recovered_kt)
    assert component["emissions_Gg"] == ledger["emitted_co2_kt"]
    return {"implied_gross_co2_kt": ledger["gross_process_co2_kt"],
            "implied_recovered_co2_kt": ledger["recovered_to_urea_kt"],
            "implied_net_co2_kt": ledger["emitted_co2_kt"]}


def crt_pathway(background_rows, data):
    """The official record: comparator, red-flagged, never an input."""
    row = next(r for r in background_rows if r["category"].startswith("2.B.1."))
    activity_kt = float(row["activity_kt"])
    recovery_kt = -float(row["co2_fossil_recovery_kt"])
    # Gas the CRT activity would need, on the sector's own billing basis: NH3 x GJ/t
    # (net) -> gross energy -> MMCFD at the nominal 1,000 Btu/scf.
    net_tj = activity_kt * data.p("ammonia_fuel_requirement")
    gross_tj = net_tj / _gross_to_net()
    mmcfd_needed = gross_tj / mmcfd_to_TJ(1.0, HHV_HIGH_BTU)
    return {
        "pathway": "official CRT", "period": "2022", "period_basis": "calendar",
        "nh3_kt_central": activity_kt, "nh3_kt_low": "", "nh3_kt_high": "",
        "method": "Pakistan 2022 CRT Table2(I).A-H row 21, activity as reported",
        "inputs": "official activity %.3f kt; official recovery %.3f kt" %
                  (activity_kt, recovery_kt),
        "independent_of_crt": False, "floor_flag": False,
        **_implied(activity_kt, data.p("ammonia_ef_total_energy"), recovery_kt),
        "red_flag": ("reported activity needs ~%.0f MMCFD of gas at 37.5 GJ/t; the "
                     "whole fertilizer sector drew 752-756 in FY2023-24 (NFDC Annex-28 "
                     "and OGRA, half a percent apart) and ~770 in FY2024-25 (NFDC); "
                     "the activity basis looks like total "
                     "fertilizer product or capacity, not ammonia output. The "
                     "recovery term implies %.0f kt urea, which IS plausible "
                     "against NFDC production" %
                     (mmcfd_needed, recovery_kt / UREA_CO2_RECOVERY)),
        "activation_status": DIAGNOSTIC,
        "source_id": "unfccc_crt_2024", "note": "comparator only; never copied into "
        "any independent pathway or total",
    }


def plant_pathway(data, utilization, util_low, util_high):
    """Reported plant output plus documented capacity: a floor, not an estimate.

    Two of the eight census plants are quantifiable - Fatima Sheikhupura reports an
    actual, Agritech a design capacity. The other six have neither, so this pathway
    bounds national ammonia from below and is never scaled up.
    """
    reported_t = sum(
        float(r["production_t"]) for r in data.chemical_plant_activity_rows
        if r["product"] == "Ammonia" and str(r["production_t"]).strip()
        and int(r["period_end_year"]) == 2024 and r["period_basis"] == "calendar")
    capacity_tpd = sum(
        float(r["capacity"]) for r in data.facility_rows
        if r["facility_id"].startswith("fert_") and str(r["capacity"]).strip()
        and r["capacity_unit"] == "t NH3/day")
    central = (reported_t + capacity_tpd * 365.0 * utilization) / 1000.0
    low = (reported_t + capacity_tpd * 365.0 * util_low) / 1000.0
    high = (reported_t + capacity_tpd * 365.0 * util_high) / 1000.0
    return {
        "pathway": "plant census", "period": "2024", "period_basis": "calendar",
        "nh3_kt_central": central, "nh3_kt_low": low, "nh3_kt_high": high,
        "method": "reported actuals where they exist, documented capacity x IPCC "
                  "utilization (0.80, 0.70-0.90) where only capacity is public",
        "inputs": "%.0f t reported (Fatima Sheikhupura); %.0f t/day documented "
                  "capacity (Agritech); six census plants unquantified" %
                  (reported_t, capacity_tpd),
        "independent_of_crt": True, "floor_flag": True,
        "implied_gross_co2_kt": "", "implied_recovered_co2_kt": "",
        "implied_net_co2_kt": "",
        "red_flag": "",
        "activation_status": DIAGNOSTIC,
        "source_id": "fatima_annual_2024",
        "note": "a FLOOR from 2 of 8 census plants; implied-CO2 columns left empty "
                "because a floor's carbon arithmetic would read as an estimate",
    }


def product_nh3_kt(data, fiscal_year):
    """Ammonia embodied in NFDC's domestic production, by nitrogen stoichiometry -
    the PRIMARY national activity estimate the Tier-1 2.B.1 calculation anchors on.
    Sums every ammoniacal product; the urea-only figure is a floor, this is the full
    product reconstruction (~4.45 Mt NH3 for 2023-24)."""
    total_kt = 0.0
    for product in ("Urea", "CAN", "NP", "DAP", "NPK", "SSP", "SOP"):
        total_kt += _production_kt(data, product, fiscal_year) * data.efv("ammonia_embodied", product)
    return total_kt


def product_pathway(data, fiscal_year):
    """Ammonia embodied in NFDC's domestic production, by nitrogen stoichiometry."""
    detail, total_kt = [], 0.0
    for product in ("Urea", "CAN", "NP", "DAP", "NPK", "SSP", "SOP"):
        production = _production_kt(data, product, fiscal_year)
        factor = data.efv("ammonia_embodied", product)
        total_kt += production * factor
        if production and factor:
            detail.append("%s %.0f kt x %.3f" % (product, production, factor))
    period_end = int(fiscal_year.split("-")[0]) + 1
    urea_kt = _production_kt(data, "Urea", fiscal_year)
    recovery = urea_recovery(urea_kt, UREA_CO2_RECOVERY, data.p("nh3_per_urea"))
    return {
        "pathway": "product stoichiometry", "period": fiscal_year,
        "period_basis": "fiscal", "nh3_kt_central": total_kt,
        "nh3_kt_low": recovery["nh3_floor_kt"], "nh3_kt_high": "",
        "method": "sum over NFDC production by product of embodied NH3 (N grade x "
                  "17.031/14.007); the low bound is the urea-only floor",
        "inputs": "; ".join(detail),
        "independent_of_crt": True, "floor_flag": False,
        **_implied(total_kt, data.p("ammonia_ef_total_energy"),
                   recovery["recovered_co2_kt"]),
        "red_flag": "",
        "activation_status": DIAGNOSTIC,
        "source_id": "nfdc_afr_2024_25",
        "note": ("no ammonia-trade adjustment - no import/export series for ammonia "
                 "itself is held; misses non-fertilizer ammonia uses; period ends "
                 "June %d" % period_end),
    }


def gas_pathway(data, period, total_mmcf, source_id, source, note_extra=""):
    """Sector gas divided by the IPCC total energy requirement: an upper bound."""
    mmcfd = total_mmcf / 365.0
    gj_per_t = data.p("ammonia_fuel_requirement")
    gross_to_net = _gross_to_net()

    def nh3_kt(hhv):
        net_tj = mmcfd_to_TJ(mmcfd, hhv, gross_to_net)
        return net_tj / gj_per_t

    low, high = nh3_kt(HHV_LOW_BTU), nh3_kt(HHV_HIGH_BTU)
    central = (low + high) / 2.0
    return {
        "pathway": "gas balance", "period": period, "period_basis": "fiscal",
        "nh3_kt_central": central, "nh3_kt_low": low, "nh3_kt_high": high,
        "method": "sector gas / %.1f GJ (net)/t NH3; %.0f-%.0f Btu/scf HHV band; "
                  "gross-to-net %.2f" % (gj_per_t, HHV_LOW_BTU, HHV_HIGH_BTU,
                                         gross_to_net),
        "inputs": "%.0f MMCF (%.0f MMCFD), every cubic foot generously assumed to "
                  "serve ammonia" % (total_mmcf, mmcfd),
        "independent_of_crt": True, "floor_flag": False,
        "implied_gross_co2_kt": "", "implied_recovered_co2_kt": "",
        "implied_net_co2_kt": "",
        "red_flag": "",
        "activation_status": DIAGNOSTIC,
        "source_id": source_id,
        "note": ("an UPPER bound: the same gas also made nitric acid and phosphate "
                 "heat. " + source + (". " + note_extra if note_extra else "")),
    }


def reconciliation_table(data, background_rows):
    """One row per pathway-period; periods are never merged and nothing is averaged."""
    nfdc_total_mmcf = sum(
        float(r["total_mmcf"]) for r in data.fertilizer_gas_rows
        if r["plant"] != "Total")
    rows = [
        crt_pathway(background_rows, data),
        plant_pathway(data, data.p("ammonia_capacity_utilization"), 0.70, 0.90),
        product_pathway(data, "2023-24"),
        product_pathway(data, "2024-25"),
        gas_pathway(data, "2023-24",
                    OGRA_FERTILIZER_MMCFD_FY2023_24 * 365.0,
                    "ogra_industry_gas", OGRA_SOURCE,
                    "the NFDC Annex-28 row beside it is the same fiscal year read off "
                    "the plants' own meters and agrees to 0.5 percent; the two records "
                    "are kept apart rather than averaged"),
        # The reference year twice, from two institutions. Round 11 had only OGRA here
        # and borrowed the following year's feed/fuel shares to describe this one; the
        # annex makes the year observed, and keeping BOTH rows is what makes the
        # agreement between them visible. Same pathway and period, told apart by
        # source_id - the anti-averaging rule applies between records as well as between
        # pathways.
        gas_pathway(data, "2023-24", _nfdc_gas_mmcf(data, "2023-24"),
                    "nfdc_afr_2024_25", NFDC_ANNEX28_SOURCE,
                    "the FY2023-24 feed/fuel split is OBSERVED here at 83.5/16.5 and is "
                    "no longer borrowed from the year after it; 751.9 MMCFD against "
                    "OGRA's 756 for the same fiscal year"),
        gas_pathway(data, "2024-25", nfdc_total_mmcf,
                    "nfdc_afr_2024_25",
                    "NFDC AFR 2024-25 Table 40, plant-wise with feed/fuel split"),
    ]
    assert len({r["pathway"] for r in rows}) == 4
    return rows


def gas_monthly_table(data):
    """The fertilizer sector's gas by month, and the finding that it barely moves.

    This is the first OBSERVED monthly profile for this stream, and what it observes is
    that there is almost no profile: peak to trough is about 1.19 and no month sits more
    than a point off a flat twelfth. Cement's borrowed shape in this same sector runs past
    a factor of two. A flat assumption would have been very nearly right here, which is
    worth knowing precisely because nothing had measured it.

    It is applied to NOTHING. 2.B.1 is NE, so no reported category takes this shape, and
    the temporal-method column says what class it WOULD carry rather than claiming one.
    """
    rows = []
    for fiscal_year in ("2023-24", "2024-25"):
        year_total = _nfdc_gas_mmcf(data, fiscal_year)
        months = {}
        for row in data.fertilizer_gas_monthly_rows:
            if row["fiscal_year"] != fiscal_year or not str(row["mmcf"]).strip():
                continue
            key = (row["month"], int(row["calendar_year"]))
            feed, fuel = months.get(key, (0.0, 0.0))
            if row["consumption"] == "Feed":
                feed += float(row["mmcf"])
            else:
                fuel += float(row["mmcf"])
            months[key] = (feed, fuel)
        ordered = sorted(months, key=lambda k: (k[1], MONTH_ORDER.index(k[0])))
        totals = [sum(months[k]) for k in ordered]
        peak, trough = max(totals), min(totals)
        for (month, calendar_year) in ordered:
            feed, fuel = months[(month, calendar_year)]
            total = feed + fuel
            note = ""
            if total == peak:
                note = ("the year's peak; peak over trough is %.2f across the year, "
                        "against cement's borrowed shape at more than a factor of two "
                        "- this stream is baseload" % (peak / trough))
            elif total == trough:
                note = "the year's trough; see the peak row for the range"
            rows.append({
                "fiscal_year": fiscal_year, "month": month,
                "calendar_year": calendar_year,
                "feed_mmcf": round(feed, 3), "fuel_mmcf": round(fuel, 3),
                "total_mmcf": round(total, 3),
                "share_of_year": round(total / year_total, 6),
                "feed_share_pct": round(feed / total * 100.0, 3) if total else "",
                "temporal_method_if_applied": "T1",
                "applied_to": "nothing - 2.B.1 is NE, so no reported category takes "
                              "this shape",
                "activation_status": DIAGNOSTIC,
                "source": NFDC_ANNEX28_SOURCE, "note": note})
    return rows


def gas_cross_source_table(data):
    """Two institutions on the same fiscal year, and what their agreement does not buy.

    A manufacturers' association reading its members' plant meters, against a regulator
    reading utility sales. Nothing upstream is shared, which is what makes the 0.5 percent
    worth reporting - and what it corroborates is the sector's gas VOLUME, not the share
    of that gas which became ammonia. Both remain upper bounds on activity.
    """
    nfdc = _nfdc_gas_mmcf(data, "2023-24")
    nfdc_feed = _nfdc_gas_mmcf(data, "2023-24", "Feed")
    ogra = OGRA_FERTILIZER_MMCFD_FY2023_24 * 365.0
    return [
        {"fiscal_year": "2023-24", "record": "NFDC Annex-28 monthly plant meters",
         "institution": "National Fertilizer Development Centre",
         "source_id": "nfdc_afr_2024_25", "quantity_mmcf": round(nfdc, 1),
         "mmcfd": round(nfdc / 365.0, 2),
         "feed_share_pct": round(nfdc_feed / nfdc * 100.0, 2),
         "fuel_share_pct": round((nfdc - nfdc_feed) / nfdc * 100.0, 2),
         "split_basis": "observed, plant by plant and month by month",
         "independence": "large - members' plant meters, compiled by the industry's own "
                         "development centre",
         "agreement_pct": "", "activation_status": DIAGNOSTIC,
         "source": NFDC_ANNEX28_SOURCE,
         "note": "the reference year's own record; Round 11 borrowed the FY2024-25 "
                 "shares for this year because this annex had not been read"},
        {"fiscal_year": "2023-24", "record": "OGRA Table 3.31 sector-wise gas",
         "institution": "Oil and Gas Regulatory Authority",
         "source_id": "ogra_industry_gas", "quantity_mmcf": round(ogra, 1),
         "mmcfd": round(OGRA_FERTILIZER_MMCFD_FY2023_24, 2),
         "feed_share_pct": "", "fuel_share_pct": "",
         "split_basis": "not published - OGRA reports the sector's volume, not its use",
         "independence": "large - utility sales returns to the regulator",
         "agreement_pct": "", "activation_status": DIAGNOSTIC, "source": OGRA_SOURCE,
         "note": "the figure Round 11's gas pathway rested on alone"},
        {"fiscal_year": "2023-24", "record": "difference",
         "institution": "", "source_id": "", "quantity_mmcf": round(nfdc - ogra, 1),
         "mmcfd": round((nfdc - ogra) / 365.0, 2),
         "feed_share_pct": "", "fuel_share_pct": "",
         "split_basis": "", "independence": "no upstream input is shared between them",
         "agreement_pct": round((nfdc - ogra) / ogra * 100.0, 3),
         "activation_status": DIAGNOSTIC,
         "source": "identity over the two rows above",
         "note": "WHAT THIS DOES NOT BUY: agreement on the sector's gas volume is not "
                 "agreement on how much of that gas became ammonia. Both records remain "
                 "UPPER bounds on ammonia activity and neither activates 2.B.1"},
    ]


def urea_bridge(data):
    """Production + imports - exports +/- stock = agricultural use + other uses.

    The residual row is the bridge's finding, not its failure: it is inventories,
    industrial use and timing, and it is REPORTED, never zeroed.
    """
    factor = UREA_CO2_RECOVERY
    rows = []
    for fiscal_year in ("2023-24", "2024-25"):
        production = _production_kt(data, "Urea", fiscal_year)
        # rc42 (P-3): the application side reads Annex-5's printed national row exactly
        # (6,578.838 kt in 2023-24) where the extracted Table 5 rounds it to 6,579; the
        # bridge's own method note already named the exact figure
        offtake = _annex5_urea_kt(fiscal_year) or _offtake_kt(data, "Urea", fiscal_year)
        imported = _offtake_kt(data, "Urea", fiscal_year, "imported")
        residual = production + imported - offtake
        rows += [
            {"fiscal_year": fiscal_year, "flow": "production",
             "urea_kt": production, "co2_kt_at_44_60": production * factor,
             "ipcc_side": "2.B.1 recovery basis",
             "source": ("NFDC AFR 2024-25 Table 1 "
                        "(data/nfdc/afr2025_production_by_manufacturer.csv)"),
             "status": "extracted",
             "note": "the recovery term rides urea PRODUCED"},
            {"fiscal_year": fiscal_year, "flow": "imports",
             "urea_kt": imported, "co2_kt_at_44_60": "",
             "ipcc_side": "bridge only; imported urea carries no domestic 2.B.1 "
                          "recovery",
             "source": TABLE5_SOURCE, "status": "extracted",
             "note": "imported-offtake basis, the closest printed proxy for imports"},
            {"fiscal_year": fiscal_year, "flow": "exports",
             "urea_kt": 0.0, "co2_kt_at_44_60": "",
             "ipcc_side": "bridge only",
             "source": TABLE5_SOURCE, "status": "inferred nil",
             "note": "no export line is printed for urea"},
            {"fiscal_year": fiscal_year, "flow": "offtake (agricultural use)",
             "urea_kt": offtake, "co2_kt_at_44_60": offtake * factor,
             "ipcc_side": "3.H application basis",
             "source": TABLE5_SOURCE,
             "status": ("Annex-5 national row, exact (Table 5 prints 6,579; "
                        "data/activity/fertilizer_2024.csv holds 6,579,000 t)"
                        if fiscal_year == "2023-24" else "Annex-5 national row, exact"),
             "note": "3.H rides urea APPLIED; production and application differ by "
                     "design"},
            {"fiscal_year": fiscal_year, "flow": "stock change and other uses "
             "(residual)",
             "urea_kt": residual, "co2_kt_at_44_60": "",
             "ipcc_side": "bridge residual; NOT forced to zero",
             "source": "identity over the rows above", "status": "derived",
             "note": "inventories, industrial and technical urea, and period timing"},
        ]
    rows.append({
        "fiscal_year": "2023-24", "flow": "3.H method note",
        "urea_kt": 6578.838, "co2_kt_at_44_60": "",
        "ipcc_side": "method note",
        "source": "pkinv.sectors.agriculture.liming_urea",
        "status": "closed by rc39 A3",
        "note": "3.H used to derive urea as N x 0.80 / 0.46 = 6,565,217 t rather than read "
                "the observed offtake in the same file, 0.207 percent apart. It now reads "
                "NFDC Annex-5's printed national row for Jul-2023..Jun-2024 directly: "
                "6,578,838 t, carried as urea_activity_basis=direct_product_offtake. The "
                "reconstruction survives for the historical years, which have a FAOSTAT "
                "total-N series and no product split, and says so on every row. The 0.80 "
                "urea_N_share is no longer load-bearing for the reference year",
    })
    return rows
