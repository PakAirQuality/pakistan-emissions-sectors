"""The national gas closure: every delivered molecule's claim, stated once.

WHY (the seventh review). Fugitives applies a post-meter leakage factor to delivered
industrial and power gas while the combustion modules burn the same delivered
quantities, and nothing stated the identity

    delivered = combusted + feedstock + unestimated end uses + (leak riding the same gas)

so the double-claim - a leak factor on gas that is also fully combusted - lived in
two modules' docstrings and nowhere as arithmetic. This module states it as rows:
OGRA's Table 3.31 end-use disposition of delivered gas (the one table that partitions
the deliveries) joined against what each module actually claims, every stream carrying
its METERING BASIS, and the known double-claim QUANTIFIED rather than silently fixed.

THE RE-FREEZE HAPPENED (rc19, the fourteenth review). For five releases this module
quantified the double-claim while the reference kept it, because repairing it moves
frozen totals and deserved a deliberate re-freeze, not a hotfix. That re-freeze is
rc19: the combustion engines now book delivered gas NET of the whole-gas leaked
share (one home: sectors/fugitives/post_meter), so the identity holds in the booking
itself. This module remains a diagnostic - it alters no total - and its variant now
prices the OTHER direction: gross delivered-gas accounting as the named alternative.

METERING BASES (closed vocabulary):
  delivered-sold             utility sales meter, downstream of transmission losses,
                             upstream of end-use combustion (OGRA Table 3.31)
  metered-downstream-of-loss the same reading seen from the leak's perspective: the
                             post-meter factor applies AFTER this meter
  consumed-reported          the consuming module's own publication (NEPRA TOE for
                             power stations) - a different meter for the same gas
  feedstock                  delivered but not burned: chemical feedstock

Usage:  python3 -m pkinv.report.gas_closure
Writes: outputs/national_gas_closure.csv
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import csv
import os

from pkinv.paths import DATA, OUTPUTS
from pkinv.core.io import write_table

END_USE = asset_path(DATA, "activity", "fugitives", "post_meter_end_use_2023_24.csv")
OUT = asset_path(OUTPUTS, "national_gas_closure.csv")

# The post-meter CH4 factor and the whole-gas leak share both have ONE home:
# the fugitives registry, through sectors/fugitives/post_meter. This module
# carried its own 6.1 for two releases after the density/CH4-fraction twins
# were repaired - the same defect class, now closed the same way.


def _fug():
    """The fugitives engine, by name - its declared post-meter accessors are the
    one home of the factor and the leak share (rc34: no sector import at module
    level, so importing this report drags no sector code)."""
    from pkinv.core import registry
    return registry.get("fugitives")


def _fugitives_param(name):
    """A declared fugitives parameter, read from its home so no twin can drift.

    The density and CH4 mass fraction below were re-declared here as local
    constants for two releases, and the twin hid a defect: the double-claim
    share divided CH4 mass by whole-gas mass (0.897%) when the mass leaving the
    burned stream is WHOLE GAS (0.997%). Reading the declared values keeps the
    conversion visible where it happens."""
    for r in _activity_rows(asset_path(DATA, "fugitives_params.csv"), comments=False):
        if r["param"] == name:
            return float(r["value"])
    raise KeyError(name)

# end_use -> (ipcc_destination, combustion_module, basis_note)
CLAIMS = {
    "Power": ("1.A.1.a", "power (grid)",
              "combusted against NEPRA SIR Table 3 TOE - a DIFFERENT publication's "
              "meter for the same gas; the two are reconciled in the power sector's "
              "energy closure, not assumed equal"),
    "Captive power": ("1.A.2", "power (captive)",
                      "combusted against OGRA's own captive register (288.01 MMCFD "
                      "reconciled to the published 288)"),
    "General industry": ("1.A.2", "industry",
                         "combusted against OGRA's sector-wise gas table"),
    "Cement": ("1.A.2", "industry", "combusted against OGRA's sector-wise gas table"),
    "Residential": ("1.A.4.b", "residential",
                    "combusted against SNGPL/SSGC utility returns; the fugitives "
                    "post-meter base EXCLUDES this use (appliance-count fallback "
                    "covers residential leakage separately)"),
    "Commercial": ("1.A.4.a", "NOT ESTIMATED",
                   "delivered and burned in commercial buildings this inventory does "
                   "not estimate - part of the declared commercial-buildings gap"),
    # OGRA prints one Fertilizer row; the ledger carries it as two, because the two
    # parts are different flows with different factor boundaries (rc67). The split is
    # NFDC's metered feed and fuel gas (sectors/fugitives data.fertilizer_feed_fraction).
    "Fertilizer: feedstock": (
        "2.B.1 feedstock", "EXCLUDED FROM COMBUSTION",
        "chemical feedstock: reformed to hydrogen and carbon dioxide, not burned. Outside "
        "every combustion module and, since rc67, OUTSIDE the post-meter leak base, whose "
        "factor is defined on gas consumed in combustion equipment. Its carbon is booked "
        "by 2.B.1 on ammonia production and, for the part recovered into urea, by 3.C.3 "
        "where the urea is applied. Every release through rc66 kept it inside the base; "
        "that membership survives as the fugitives scenario "
        "post_meter_including_feedstock"),
    "Fertilizer: process fuel": (
        "2.B.1 process fuel", "ippu (2.B.1, on production)",
        "burned at the fertiliser plants (reformer furnaces, boilers) and INSIDE the "
        "post-meter leak base, where the factor's definition holds. Its carbon is booked "
        "by 2.B.1, whose factor is on the plant's total gas requirement per tonne of "
        "ammonia and so covers fuel with feed. That booking is on production, not on "
        "delivered gas, so no delivered-gas combustion row exists to net the leak from"),
    "CNG": ("1.A.3.b", "transport (inside the road control)",
            "vehicle CNG, burned within the road module's own control totals; the "
            "post-meter base excludes it"),
    "Other and independent systems": ("mixed", "NOT SEPARABLE HERE",
                                      "OGRA's own residual class; carried as "
                                      "delivered mass with no combustion claim "
                                      "resolved to a single module"),
}


# --- The live joins (rc14, the ninth review's #1) ------------------------------------
#
# Until this round the closure read ONE CSV and restated the claims as prose: the
# ledger now joins every Table 3.31 class to the LIVE module quantity - the number
# the combustion engine actually burns - and ABORTS when a matched class drifts.
# Everything stays in MMCFD/volume: the combustion modules embed the 0.90
# gross-to-net inside their TJ conversions, so a TJ-basis join would inherit a 10%
# conversion artefact that has nothing to do with the gas.
LEDGER_STATUSES = ("matched_same_publication", "reconciled_different_meter",
                   "not_estimated_declared", "feedstock_excluded",
                   # rc67: burned, with its carbon booked by a process category on a
                   # production basis and not by a delivered-gas combustion module.
                   "combusted_booked_on_production",
                   "residual_unresolved",
                   # 2026-10-07, the twenty-second review's item 3: a stream that IS
                   # estimated but whose MEASUREMENT POINT is not established. It needed a
                   # word of its own: not_estimated_declared means nothing is booked, and
                   # reconciled_different_meter names the reconciliation rather than what
                   # remains unsettled after it. Only GAP rows carry it, and a GAP row
                   # carries no volume - see the guard in tests/test_gas_closure.py.
                   "not_established_declared")
MATCH_TOL_PCT = 0.5      # same-publication numbers may differ only by rounding


def _live_quantities():
    """Each consuming module's own gas activity, MMCFD, from the live engines.

    Power-grid is deliberately NOT here: its activity is NEPRA TOE - a different
    publication's meter - and pretending it were an MMCFD to match would erase
    exactly the different-meter fact the ledger exists to state. Its
    reconciliation (plant-summed TJ vs national TJ, implied HHV) rides the row's
    note instead, from the power sector's own bridge."""
    from pkinv.core import registry
    live = {}
    for name in ("residential", "industry", "transport"):
        sector = registry.get(name)
        live.update(sector.gas_activity(sector.load_data()))
    captive = asset_path(DATA, "activity", "power", "captive_gas.csv")
    live["Captive power"] = next(
        float(r["total_mmcfd"]) for r in _activity_rows(captive, comments=False)
        if r["fiscal_year"] == "2024")
    return live


def _power_grid_gas_mt():
    """The grid gas CO2e the engine books, Mt - the magnitude the gap row is a band on."""
    from pkinv.core import registry
    engine = registry.get("power")
    return sum(c["co2e_Mt_AR5"] for c in engine.build_components(engine.load_data())
               if c["category"] == "Electricity and heat production"
               and c["subitem"].startswith("Gas"))


def _power_bridge():
    from pkinv.core import registry
    return registry.diagnostics("power").gas_bridge(registry.get("power").load_data())


def _supply_note():
    """The volume-basis supply identity, from the fugitives sector's own balance."""
    fugitives = _fug()
    return fugitives.gas_supply_balance_row(fugitives.load_data())


def _end_uses():
    """Table 3.31's end uses, the Fertilizer row carried as its two flows.

    The printed row is one number. NFDC meters what the plants do with it: feed gas to
    the reformers and fuel gas to the furnaces. Each part keeps the printed row's source
    fields and gets its share of the volume; only the process fuel stays in the post-meter
    leak base. The two parts sum back to the printed row exactly."""
    fugitives = _fug()
    feed = fugitives.fertilizer_feed_fraction(fugitives.load_data(), 2024)
    out = []
    for r in _activity_rows(END_USE, comments=False):
        if r["fiscal_year"] != "2024" or r["end_use"].startswith("Total"):
            continue
        if r["end_use"] != "Fertilizer":
            out.append(dict(r))
            continue
        for label, part, in_base in (("Fertilizer: feedstock", feed["value"], "no"),
                                     ("Fertilizer: process fuel", 1.0 - feed["value"],
                                      "yes")):
            piece = dict(r)
            piece["end_use"] = label
            piece["throughput_mmcfd"] = "%.2f" % (float(r["throughput_mmcfd"]) * part)
            piece["annual_million_m3"] = float(r["annual_million_m3"]) * part
            piece["include_in_ipcc_post_meter"] = in_base
            piece["split_note"] = (
                "%.2f%% of OGRA's printed Fertilizer row (%s MMCFD), the feed fraction %s "
                "from FY%s; %s" % (100.0 * part, r["throughput_mmcfd"], feed["basis"],
                                   feed["observed_year"], feed["source"]))
            out.append(piece)
    return out


def build(live_overrides=None):
    uses = _end_uses()
    live = _live_quantities()
    if live_overrides:
        live.update(live_overrides)
    power_bridge = _power_bridge()
    supply = _supply_note()

    rows = []
    delivered_mm3 = 0.0
    leak_base_mm3 = 0.0
    combusted_mm3 = 0.0
    feedstock_mm3 = 0.0
    unestimated_mm3 = 0.0
    for r in uses:
        mm3 = float(r["annual_million_m3"])
        delivered_mm3 += mm3
        dest, module, basis_note = CLAIMS[r["end_use"]]
        in_leak = r["include_in_ipcc_post_meter"].strip().lower() == "yes"
        if in_leak:
            leak_base_mm3 += mm3
        if module.startswith(("power", "industry", "residential", "transport", "ippu")):
            combusted_mm3 += mm3
        elif dest.endswith("feedstock"):
            feedstock_mm3 += mm3
        else:
            unestimated_mm3 += mm3

        # The live join: what does the consuming engine actually burn?
        table_mmcfd = float(r["throughput_mmcfd"])
        live_mmcfd = ""
        if r["end_use"] in live:
            live_mmcfd = live[r["end_use"]]
            gap_pct = (100.0 * abs(live_mmcfd - table_mmcfd) / table_mmcfd
                       if table_mmcfd else 0.0)
            if gap_pct > MATCH_TOL_PCT:
                raise SystemExit(
                    "gas ledger: %s reads %.2f MMCFD from OGRA Table 3.31 while "
                    "the consuming module burns %.2f - a %.2f%% gap where the "
                    "two are the same publication's number (tolerance %.1f%%)"
                    % (r["end_use"], table_mmcfd, live_mmcfd, gap_pct,
                       MATCH_TOL_PCT))
            status = "matched_same_publication"
        elif r["end_use"] == "Power":
            status = "reconciled_different_meter"
            basis_note = (basis_note +
                          "; live bridge: plant-summed %.0f TJ vs national %.0f "
                          "TJ (ratio %.3f), implied HHV %.0f Btu/scf - the "
                          "reconciliation is printed, never assumed away"
                          % (power_bridge["plant_TJ"],
                             power_bridge["national_TJ"], power_bridge["ratio"],
                             power_bridge["implied_hhv_btu_per_scf"]))
        elif dest.endswith("feedstock"):
            status = "feedstock_excluded"
        elif module.startswith("ippu"):
            status = "combusted_booked_on_production"
        elif module == "NOT ESTIMATED":
            status = "not_estimated_declared"
        else:
            status = "residual_unresolved"
        rows.append({
            "stream": r["end_use"], "mmcfd": r["throughput_mmcfd"],
            "annual_million_m3": round(mm3, 1),
            "live_module_mmcfd": ("" if live_mmcfd == ""
                                  else round(live_mmcfd, 2)),
            "ledger_status": status,
            "metering_basis": ("delivered-sold; also metered-downstream-of-loss "
                               "for the leak factor" if in_leak else "delivered-sold"),
            "ipcc_destination": dest, "claimed_by": module,
            "in_post_meter_leak_base": "yes" if in_leak else "no",
            "note": (basis_note + ("; " + r["split_note"] if r.get("split_note") else ""))})

    ch4_fraction = _fugitives_param("gas_ch4_fraction")
    leak_kt_ch4 = (leak_base_mm3 * _fug().post_meter_factor(
        "post_meter_industrial_ch4") / 1000.0)
    leaked_gas_kt = leak_kt_ch4 / ch4_fraction
    gas_kt = leak_base_mm3 * _fugitives_param("gas_density_kg_per_m3")
    rows.append({
        "stream": "CLOSURE: delivered total", "mmcfd": "",
        "annual_million_m3": round(delivered_mm3, 1),
        "live_module_mmcfd": "", "ledger_status": "",
        "metering_basis": "delivered-sold",
        "ipcc_destination": "", "claimed_by": "",
        "in_post_meter_leak_base": "",
        "note": "the identity's left side: OGRA Table 3.31 partitions deliveries by "
                "end use (the Fertilizer row carried as feed and process fuel), so "
                "combusted + feedstock + unestimated = delivered exactly "
                "(%.1f + %.1f + %.1f)" % (combusted_mm3, feedstock_mm3,
                                          unestimated_mm3)})
    rows.append({
        "stream": "CLOSURE: supply identity", "mmcfd": "",
        "annual_million_m3": round(supply["reported_total_supply_million_m3"], 1),
        "live_module_mmcfd": "", "ledger_status": "",
        "metering_basis": "physical-flow control",
        "ipcc_destination": "", "claimed_by": "",
        "in_post_meter_leak_base": "",
        "note": "the identity ABOVE the meter, from the fugitives balance: "
                "production %.0f + RLNG %.0f MMCFD -> supply %.0f, of which "
                "categorized consumption %.0f + UFG %.0f, downstream statistical "
                "discrepancy %.1f MMCFD (%.2f%% of supply) - a statistical "
                "quantity, never atmospheric methane"
                % (supply["gross_domestic_production_mmcfd"],
                   supply["rlng_supply_mmcfd"],
                   supply["reported_total_supply_mmcfd"],
                   supply["categorized_consumption_mmcfd"],
                   supply["ufg_mmcfd"],
                   supply["downstream_statistical_discrepancy_mmcfd"],
                   supply["downstream_statistical_discrepancy_pct_supply"])})
    rows.append({
        "stream": "CLOSURE: shared activity, drawn independently", "mmcfd": "",
        "annual_million_m3": "",
        "live_module_mmcfd": "", "ledger_status": "",
        "metering_basis": "",
        "ipcc_destination": "", "claimed_by": "",
        "in_post_meter_leak_base": "",
        "note": "DECLARED BOUNDARY (per-draw identity, rc19; CLOSED both sides at "
                "Wave 6): the delivered-gas activities of the OGRA-metered "
                "combustion and feedstock modules share one activity draw - the "
                "cross-module group delivered_gas_ogra_3_31 in "
                "data/parameter_scope.csv - and since Wave 6 the LEAK side holds "
                "per draw too: the fugitives draw file persists its post-meter "
                "factor multiplier as a parameter channel "
                "(POST_METER_INDUSTRIAL_MULTIPLIER) and every net-of-leak "
                "combustion component scales by its draw's own combusted "
                "fraction (uncertainty_all.gas_coupling_scalers). The rc12 "
                "injection stays a separately injected island for its OWN draws "
                "- the channel re-expresses a draw the island already made and "
                "consumes no randomness - and the grid-power volume rides its "
                "own NEPRA meter, reconciled here, never the shared draw"})
    rows.append({
        "stream": "CLOSURE: declared double-claim", "mmcfd": "",
        "annual_million_m3": round(leak_base_mm3, 1),
        "live_module_mmcfd": "", "ledger_status": "",
        "metering_basis": "metered-downstream-of-loss",
        "ipcc_destination": "1.B.2 post-meter", "claimed_by": "fugitives",
        "in_post_meter_leak_base": "yes",
        "note": "the double-claim the reference REMOVED at rc19: the post-meter leak "
                "factor rides gas the combustion modules meter - about %.0f kt CH4 "
                "of leakage, %.0f kt of whole gas at the declared %.2f CH4 mass "
                "fraction, %.1f%% of roughly %.0f kt of gas throughput. Since rc19 "
                "the combustion engines book delivered gas NET of that share "
                "(fugitives.post_meter.combusted_fraction(), all three gases), so "
                "no molecule is claimed both burned and leaked; the gross "
                "delivered-gas booking survives as the named alternative "
                "configuration, which prices the double-claim's restoration. The "
                "factor itself remains a transferred Tier-1 value whose removal "
                "and halving are priced as fugitives scenarios"
                % (leak_kt_ch4, leaked_gas_kt, ch4_fraction,
                   100.0 * leaked_gas_kt / gas_kt, gas_kt)})

    # THE ONE GAP ROW (2026-10-07, the twenty-second review's item 3). Eight of the nine
    # customer streams are matched or declared against the same publication. The ninth -
    # grid power, the largest single gas stream in the account - is
    # reconciled_different_meter: its activity is NEPRA SoIR Table 3's TOE, a
    # CONSUMED-REPORTED basis, and not OGRA's delivered sales, so the measurement POINT is
    # not established relative to the customer meter. The two publications' own bridge is
    # printed on the power row (plant-summed against national, ratio 1.085); this row
    # states what rides on it, as a BAND, because its decomposition between the meter point
    # and the heating-value assumption inside the plant sum is unresolved. A reader asking
    # "what is not established about the gas boundary?" previously found no row at all -
    # the nearest was about NMVOC.
    bridge_gap_TJ = power_bridge["plant_TJ"] - power_bridge["national_TJ"]
    power_gas_mt = _power_grid_gas_mt()
    rows.append({
        "stream": "GAP: power gas measurement point", "mmcfd": "",
        "annual_million_m3": "", "live_module_mmcfd": "",
        "ledger_status": "not_established_declared",
        "metering_basis": "consumed-reported",
        "ipcc_destination": "1.A.1.a", "claimed_by": "power (grid)",
        "in_post_meter_leak_base": "yes",
        "note": "NOT A MISSING SOURCE and not an addition to any total: the gas IS "
                "estimated (%.2f Mt CO2e booked). What is unestablished is which meter the "
                "activity describes. The regulator's two publications differ by %.0f TJ on "
                "this stream (%.1f per cent), worth up to %.2f Mt CO2e at the gas "
                "combustion factor if the whole difference were activity - and an unknown "
                "share of it is the heating value the plant sum assumes (implied %.0f "
                "Btu/scf) rather than a quantity. The band is therefore 0 to %.2f Mt and "
                "its decomposition is the open question. Settling it needs OGRA's "
                "delivered-sales series for the power customer class beside NEPRA's "
                "consumed figure for the same twelve months, which no held publication "
                "prints together"
                % (power_gas_mt, bridge_gap_TJ,
                   100.0 * bridge_gap_TJ / power_bridge["national_TJ"],
                   bridge_gap_TJ * power_gas_mt / power_bridge["national_TJ"],
                   power_bridge["implied_hhv_btu_per_scf"],
                   bridge_gap_TJ * power_gas_mt / power_bridge["national_TJ"])})

    # arithmetic identity, asserted before anything ships
    parts = combusted_mm3 + feedstock_mm3 + unestimated_mm3
    if abs(parts - delivered_mm3) > 0.5:
        raise SystemExit("gas closure does not close: %.2f vs %.2f"
                         % (parts, delivered_mm3))
    return rows


# --- The gas boundary: canonical since rc19, and the gross view beside it ------------
#
# HISTORY, kept because each step was a review gate: rc14 quantified the
# double-claim; rc17 priced its removal and corrected two nearly-
# cancelling defects in that price (a CH4-vs-whole-gas share, an imputed-vs-
# booked base - the pre-fix prints read -0.286/-0.287; the shipped restoration
# is +0.28767); rc19 made the NET booking canonical - the fourteenth review's
# requirement that the physical-atmosphere inventory not book leaked molecules
# as burned. The engines now net their gas rows (all three gases) by
# fugitives.post_meter.combusted_fraction(), and this variant prices the OTHER
# direction: gross delivered-gas accounting, the administrative-fuel view that
# books the full metered delivery as combusted, restored as a named alternative
# (+0.288 to the old 448.00456). The leaked molecules are in the inventory
# either way - 1.B.2 books them as fugitive CH4; the choice is whether the
# combustion side ALSO claims them.
VARIANT_OUT = asset_path(os.path.dirname(OUT), "national_gas_closure_variant.csv")
HHV_BTU_PER_SCF = 1000.0
GROSS_TO_NET = 0.90
GAS_CO2_T_PER_TJ = 56.1
E6M3_PER_MMCF = 0.0283168466
TJ_PER_MMCF_PER_BTU = 1.05505585262e-3

# The burned-and-leaked classes' gas emission rows: (module, category, subitem
# prefix), resolved against the LIVE engines so the variant prices exactly what
# the modules book (which, since rc19, is the NET figure), never a
# re-derivation. All three gases: leaked gas produces no combustion CO2, CH4 or
# N2O.
BOOKED_GAS_ROWS = (
    ("power", "Electricity and heat production", "Gas "),
    ("power", "Captive gas self-generation (1A2)", "Captive natural gas "),
    ("industry", "Industrial fuel combustion (1A2)", "General Industry gas "),
    ("industry", "Industrial fuel combustion (1A2)", "Cement gas "),
)


def _booked_gas_co2e_mt():
    """Sum of the burned-and-leaked classes' gas rows (three gases, co2e AR5)
    as their engines book them - net of leakage, since rc19."""
    from pkinv.core import registry
    components = {}
    for name in ("power", "industry"):
        sector = registry.get(name)
        components[name] = sector.build_components(sector.load_data())
    total = 0.0
    for module, category, prefix in BOOKED_GAS_ROWS:
        matched = [c for c in components[module]
                   if c["category"] == category
                   and c["subitem"].startswith(prefix)]
        if len(matched) != 3:
            raise SystemExit("gas ledger variant: expected the three gas rows "
                             "for %s/%s/%s*, found %d"
                             % (module, category, prefix, len(matched)))
        total += sum(c["co2e_Mt_AR5"] for c in matched)
    return total


def variant_rows():
    """The gross delivered-gas alternative: the WHOLE-GAS leaked share divided
    back out of the booked (net) gas rows of exactly the classes that are both
    burned by a delivered-gas combustion module and inside the leak base. This is
    NOT the price of the fertiliser-feedstock membership, and it holds no fertiliser
    term: feedstock is outside the base (rc67), fertiliser process fuel is burned but
    booked on production by 2.B.1, and commercial gas is in the base with its
    combustion not estimated - none of the three has a delivered-gas combustion row to
    restore. The membership's own price is the fugitives scenario
    post_meter_including_feedstock."""
    uses = _end_uses()
    burned_leaked_mm3 = 0.0
    for r in uses:
        _dest, module, _note = CLAIMS[r["end_use"]]
        in_leak = r["include_in_ipcc_post_meter"].strip().lower() == "yes"
        if in_leak and module.startswith(("power", "industry")):
            burned_leaked_mm3 += float(r["annual_million_m3"])
    leak_share = _fug().whole_gas_leak_share()
    tj = (burned_leaked_mm3 / E6M3_PER_MMCF) * HHV_BTU_PER_SCF \
        * TJ_PER_MMCF_PER_BTU * GROSS_TO_NET
    imputed_co2_mt = tj * GAS_CO2_T_PER_TJ / 1e6
    booked_net_mt = _booked_gas_co2e_mt()
    restoration_mt = booked_net_mt * leak_share / (1.0 - leak_share)
    shared = {"burned_and_leaked_million_m3": round(burned_leaked_mm3, 1),
              "leaked_mass_share_pct": round(100.0 * leak_share, 3),
              "booked_net_gas_co2e_of_those_classes_Mt": round(booked_net_mt, 3),
              "imputed_gas_co2_superseded_Mt": round(imputed_co2_mt, 3)}
    return [
        dict(shared, configuration="reference", adjustment_Mt_co2e=0.0,
             note="CANONICAL SINCE rc19: combustion books delivered gas NET of "
                  "the post-meter leaked share (all three gases), so the "
                  "physical-atmosphere identity holds in the booking itself - "
                  "no molecule is claimed both burned and leaked"),
        dict(shared, configuration="gross_delivered_gas_accounting",
             adjustment_Mt_co2e=round(restoration_mt, 5),
             note="the administrative-fuel view: the full metered delivery "
                  "booked as combusted, restoring the double-claim the "
                  "reference removed (power grid, captive, general industry, "
                  "cement - %.1f e6 m3 at %.3f%% leaked whole-gas mass over "
                  "the %.2f Mt those modules book net; the superseded "
                  "volume-imputed base %.2f Mt printed beside it). A "
                  "cross-sector adjustment no single-axis scenario can "
                  "express, so it ships as a JOINT national configuration"
                  % (burned_leaked_mm3, 100.0 * leak_share, booked_net_mt,
                     imputed_co2_mt)),
    ]


def main():
    rows = build()
    fields = ["stream", "mmcfd", "annual_million_m3", "live_module_mmcfd",
              "ledger_status", "metering_basis",
              "ipcc_destination", "claimed_by", "in_post_meter_leak_base", "note"]
    write_table(OUT, fields, rows)
    variants = variant_rows()
    vfields = ["configuration", "adjustment_Mt_co2e", "burned_and_leaked_million_m3",
               "leaked_mass_share_pct", "booked_net_gas_co2e_of_those_classes_Mt",
               "imputed_gas_co2_superseded_Mt", "note"]
    write_table(VARIANT_OUT, vfields, variants)
    print("national gas closure -> %s (%d rows; identity holds); variant %.3f Mt"
          % (os.path.relpath(OUT), len(rows),
             float(variants[1]["adjustment_Mt_co2e"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
