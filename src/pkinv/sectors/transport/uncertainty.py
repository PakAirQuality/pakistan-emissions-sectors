"""The transport sector's uncertainty: parametric where a percentage is honest,
structural where a choice is discrete, and the fuel anchor made to say what it
constrains and what it does not.

THE SHAPE OF THIS SECTOR'S UNCERTAINTY. The national total rides three fuel controls -
OCAC's Road customer-class sales at a declared 10 percent, their IPCC net calorific
values at 3-4, and a metered CNG volume chain at about 13 - so the sector band is
narrow. Everything the fleet model touches is far softer: the class split has no
independent validation, the off-road partition inherits a residual bucket, and the
per-kilometre air factors carry no primary citation. And the boundary itself is a
structural axis now priced by scenario: the superseded PES controls, the corrected
arithmetic at the wrong vintage, the alternative national-minus-bulk construction and
the nine-year Road-share envelope. One number cannot describe all of that; this
module publishes the decomposition.

PARAMETRIC - GROUPED VS INDEPENDENT, ADAPTED TO FUEL ANCHORING. Each fuel's control
total and calorific value are ONE perfectly-shared error across every row that fuel
feeds (off-road rows join the diesel group: they partition the same control). The
25-percent fleet term stamped on every road row is deliberately DEMOTED from the
sector-total band, because vehicle-km shares are normalised within each fuel - a fleet
error redistributes a fixed fuel total between classes and cannot move the sector. That
demotion is why the grouped figure can sit near the independent one despite full
correlation within fuels: the grouped treatment removes distribution noise the
independent view mistakes for magnitude uncertainty, then restores the true shared
terms. Computed HERE, analytically: stamping corr_group on the shipped components would
reorder the national Monte Carlo's seed-42 gauss stream (core/montecarlo.py docstring),
and the natural group - the diesel control - spans both reported categories, which
test_sector_contract.py forbids on shipped rows.

STRUCTURAL - named cases, conditional intervals, no probabilities. The CNG heating
value (the published 900 Btu/scf case), the off-road N2O table choice (the pinned
Table 3.3.1 against the road table), the CNG exclusion bound (the pre-August-2026
sector), and the CNG fleet-energy band (the two-basis crosscheck priced at its
plausibility bounds). Two rows are declarations rather than samples: the class split
(per-class fuel-consumption rates with provenance have not been obtained here to
build an alternative from - road.py's docstring says inventing them would be worse
than declaring the gap) and the air-factor provenance (Punjab-workbook per-km factors
without a located primary citation - the air layer's factors are the scope decision,
not a samplable parameter).

SCENARIO_SEED = 1811 keeps this module's draws off the national seed-42 stream
entirely, and off residential's 1404, railways' 1435 and power's 4242.

Usage:  python3 -m pkinv.sectors.transport.uncertainty
Writes: outputs/transport_uncertainty_2022.csv,
        outputs/transport_variance_decomposition_2022.csv,
        outputs/transport_uncertainty_inputs_2022.csv,
        outputs/transport_uncertainty_scenarios_2022.csv
"""

from pkinv.assets import asset_path
import csv
import math
import os

from pkinv.core import montecarlo as mc_core
from pkinv.core.uncertainty import combine_sum, product
from pkinv.paths import OUTPUTS
from pkinv.sectors.transport import cng_gap, engine, offroad, road
from pkinv.sectors.transport.data import TransportData
from pkinv.core.io import write_table

SCENARIO_SEED = 1811          # private stream; the national MC's seed 42 is untouched
INTERPRETATION = "conditional parametric interval; no structural probability"

# Every scenario row carries every column. The writer takes its field list from HERE
# rather than from the first row's keys, which is what it used to do: a row that
# forgot a column would then have silently truncated the whole file to whatever the
# reference row happened to carry, and a row that added one would have crashed the
# writer halfway through. _scen_row builds them; main() refuses to write a row whose
# keys do not match this tuple exactly.
#
# road_Mt/offroad_Mt exist because a sector total hides the thing these scenarios are
# actually about. The off-road partition cases move the sector by a rounding error
# while moving the off-road CATEGORY by half its own size, and a reader given only the
# total would conclude the partition barely matters.
SCEN_FIELDS = ("structural_scenario", "scope", "deterministic", "mean", "P2.5",
               "P50", "P97.5", "road_Mt", "offroad_Mt", "receiving_category",
               "receiving_Mt", "national_delta_Mt", "note", "interpretation")


def _scen_row(name, det, comps=None, mean="", p025="", p50="", p975="",
              receiving_category="", receiving_Mt="", national_delta_Mt="",
              note="", scope="GHG Mt CO2e AR5"):
    """One scenario row with every column present.

    road_Mt/offroad_Mt are this scenario's own per-category split, taken from its own
    component list. They are BLANK, not zero, where no component list exists (the
    declaration rows): zero would assert the category is empty in that scenario, which
    is false - the scenario simply does not restate it.

    receiving_* and national_delta_Mt are for the cross-sector transfer cases, where
    fuel leaves this sector for another IPCC category rather than ceasing to burn.
    """
    road_Mt = offroad_Mt = ""
    if comps is not None:
        road_Mt = sum(c["co2e_Mt_AR5"] for c in comps
                      if c["category"] == road.CATEGORY)
        offroad_Mt = sum(c["co2e_Mt_AR5"] for c in comps
                         if c["category"] == offroad.CATEGORY)
    return {"structural_scenario": name, "scope": scope, "deterministic": det,
            "mean": mean, "P2.5": p025, "P50": p50, "P97.5": p975,
            "road_Mt": road_Mt, "offroad_Mt": offroad_Mt,
            "receiving_category": receiving_category,
            "receiving_Mt": receiving_Mt,
            "national_delta_Mt": national_delta_Mt,
            "note": note, "interpretation": INTERPRETATION}


def _stream(c):
    """Fuel stream a component belongs to: Petrol, Diesel (incl. off-road) or CNG."""
    if c["subitem"].startswith("CNG"):
        return "CNG"
    if c["category"] == offroad.CATEGORY:
        return "Diesel"
    return c["subitem"].split()[1]        # "{cls} {fuel} {GAS}"


def _stamped_ad_u(data, stream):
    """The activity term the engine stamped on the stream's rows - what must be
    subtracted in quadrature to recover each row's factor-only residual."""
    if stream == "CNG":
        return product(data.p("cng_activity_uncert"), data.pu("cng_hhv_btu_per_scf"),
                       data.pu("cng_gross_to_net"))
    return road.activity_uncert(data)


def _shared_u(data, stream):
    """The error genuinely shared across a stream's rows at SECTOR level: the control
    total and its energy conversion. For petrol and diesel this is smaller than the
    stamped term because the 25-percent fleet component is distribution-only."""
    if stream == "CNG":
        return _stamped_ad_u(data, "CNG")       # the whole chain scales one metered total
    item = road.IPCC_FUEL[stream]
    return product(data.efu("transport_fuel_supply", item),
                   data.efu("transport_ncv", item))


def _stream_terms(data):
    """[(stream, shared_variance, [(row_value, factor_residual_u), ...])] in Mt/%."""
    comps = engine.build_components(data)
    out = []
    for stream in ("Petrol", "Diesel", "CNG"):
        rows = [c for c in comps if _stream(c) == stream]
        total = sum(c["co2e_Mt_AR5"] for c in rows)
        stamped = _stamped_ad_u(data, stream)
        shared = _shared_u(data, stream)
        residuals = []
        for c in rows:
            fu = math.sqrt(max(c["uncert_pct"] ** 2 - stamped ** 2, 0.0))
            residuals.append((c["co2e_Mt_AR5"], fu))
        out.append((stream, (shared * total) ** 2, residuals))
    return out, comps


def approach1(data):
    """Grouped and independent Approach-1 percentages for the sector total.

    Grouped: per fuel, control-and-NCV shared linearly across the stream (off-road
    included in diesel), factor residuals in quadrature, fleet distribution term
    demoted. Independent: the published per-row uncertainties combined as if
    unrelated - the national rollup's generic view.
    """
    terms, comps = _stream_terms(data)
    total = sum(c["co2e_Mt_AR5"] for c in comps)
    var = 0.0
    for _stream_name, shared_var, residuals in terms:
        var += shared_var
        for v, fu in residuals:
            var += (fu * v) ** 2
    grouped = math.sqrt(var) / total
    # The cross-fuel case: petrol and diesel controls come from ONE publication and
    # ONE Jul-Mar x12/9 annualisation, so their 15-percent errors are plausibly a
    # single shared error, not two. Control term linear across both petroleum streams,
    # NCVs per-fuel, CNG chain its own, factor residuals unchanged. This is the
    # conservative bound of the grouped family and the honest headline: the
    # within-fuel grouped figure below it prices only what is provably shared.
    var_x = 0.0
    petroleum = 0.0
    for stream, _shared_var, residuals in terms:
        stream_total = sum(v for v, _fu in residuals)
        if stream == "CNG":
            var_x += (_shared_u(data, "CNG") * stream_total) ** 2
        else:
            petroleum += stream_total
            var_x += (data.efu("transport_ncv", road.IPCC_FUEL[stream])
                      * stream_total) ** 2
        var_x += sum((fu * v) ** 2 for v, fu in residuals)
    var_x += (data.efu("transport_fuel_supply", "Motor Gasoline") * petroleum) ** 2
    grouped_x = math.sqrt(var_x) / total
    _t, indep = combine_sum([(c["co2e_Mt_AR5"], c["uncert_pct"], None) for c in comps])
    return {"scope": "sector", "co2e_Mt_AR5": total,
            "approach1_pct_grouped": grouped,
            "approach1_pct_grouped_crossfuel": grouped_x,
            "approach1_pct_independent": indep}


def variance_decomposition(data):
    """Per-stream, per-term (control+NCV vs emission factors) shares of the grouped
    Approach-1 variance - which lever actually carries the sector's band."""
    terms, comps = _stream_terms(data)
    total = sum(c["co2e_Mt_AR5"] for c in comps)
    parts = []
    for stream, shared_var, residuals in terms:
        parts.append((stream, "control+NCV", shared_var))
        parts.append((stream, "emission factors",
                      sum((fu * v) ** 2 for v, fu in residuals)))
    var_total = sum(v for _s, _t, v in parts)
    out = []
    for stream, term, v in sorted(parts, key=lambda t: -t[2]):
        out.append({"stream": stream, "term": term,
                    "variance_share_pct": round(100.0 * v / var_total, 2),
                    "sd_contribution_pct_of_total": round(math.sqrt(v) / total, 2)})
    return out


def _scaled(comps, scale, match):
    out = []
    for c in comps:
        c2 = dict(c)
        if match(c):
            for k in ("co2e_Mt_AR5", "co2e_Mt_AR6", "emissions_Gg"):
                c2[k] = c2[k] * scale
        out.append(c2)
    return out


def _diesel_co2e_per_TJ(data, prefix):
    """kg CO2e (AR5) per TJ of diesel booked under one factor set.

    prefix names the category stem: "transport_fuel" is road diesel (Tables 3.2.1 and
    3.2.2), "stationary_diesel_1a4ci" is Table 2.5, "stationary_diesel_1a2" is Table
    2.3. Used only by the retail non-road transfer rows, to compute what a
    reclassification actually costs the NATIONAL total rather than this sector's.
    Fossil CH4, as everywhere else in this sector.
    """
    from pkinv.core import gwp
    return (data.efv(prefix + "_co2", "Gas/Diesel Oil")
            + gwp.to_co2e("CH4", data.efv(prefix + "_ch4", "Gas/Diesel Oil"),
                          "AR5", fossil=True)
            + gwp.to_co2e("N2O", data.efv(prefix + "_n2o", "Gas/Diesel Oil"), "AR5"))


def _road_share_panel(data):
    """(min, max) of Road HSD / national internal HSD across the nine OCAC years -
    the observed envelope on the diesel boundary, computed from the data, never
    hardcoded."""
    shares = [data.ocac_t("Road", "HSD", y) / data.ocac_t("TOTAL_INTERNAL", "HSD", y)
              for y in data.ocac_years()]
    return min(shares), max(shares)


def structural_scenarios(data, n_iter=10000, seed=SCENARIO_SEED):
    n2o_scale = (data.efv("transport_fuel_n2o", "Gas/Diesel Oil")
                 / data.efv("offroad_machinery_n2o", "Gas/Diesel Oil"))
    lo, hi = _road_share_panel(data)
    natl_hsd = data.ocac_t("TOTAL_INTERNAL", "HSD") / 1000.0
    road_hsd = data.ocac_t("Road", "HSD") / 1000.0
    minus_bulk = (natl_hsd
                  - sum(data.ocac_t(s, "HSD") / 1000.0
                        for s in ("Railways", "Total Power", "Total Industry",
                                  "Total Government"))) / road_hsd

    def _diesel_scaled(scale):
        return lambda: _scaled(
            engine.build_components(data), scale,
            lambda c: (c["category"] == offroad.CATEGORY
                       or " Diesel " in " %s " % c["subitem"]))

    cases = [
        ("reference", lambda: engine.build_components(data),
         "the estimate: OCAC FY2021-22 Road customer-class controls"),
        ("legacy_pes_control",
         lambda: engine.build_components(
             data, control_category="transport_fuel_supply_legacy",
             deduct_rail=True),
         "the superseded control arrangement, reconstructed exactly: the "
         "PES-derived national figures (whose stored values were the source "
         "times 16/9, not the documented 12/9) minus the rail relay - the bridge "
         "to this paper's previously published numbers, retained the way the "
         "residential sector retains its superseded dung basis"),
        ("pes_corrected_12_9",
         lambda: engine.build_components(
             data, control_category="transport_fuel_supply_pes12",
             deduct_rail=True),
         "the legacy note's arithmetic done correctly: PES Jul-Mar FY2025 times "
         "12/9, rail deducted - the corrected number at the WRONG VINTAGE, "
         "showing what the FY2025-for-2022 mismatch was hiding"),
        ("national_hsd_minus_bulk", _diesel_scaled(minus_bulk),
         "the alternative boundary construction: national internal HSD minus the "
         "observed bulk rows (Railways, Power, Industry, Government) instead of "
         "the Road row read directly - the two constructions agree to "
         "%.2f%%, because Road plus Domestic Bunkers IS the national total minus "
         "the bulk rows" % (100 * abs(minus_bulk - 1.0))),
        ("road_share_low", _diesel_scaled(lo * natl_hsd / road_hsd),
         "the boundary envelope, low end: diesel at the nine-year minimum Road "
         "share of national HSD (%.3f, the FY2017-18 edition on its own printed "
         "total)" % lo),
        ("road_share_high", _diesel_scaled(hi * natl_hsd / road_hsd),
         "the boundary envelope, high end: diesel at the nine-year maximum Road "
         "share of national HSD (%.3f)" % hi),
        ("cng_hhv_900",
         lambda: engine.build_components(data, cng_hhv_btu=900),
         "the published heating-value case: Pakistani pipeline gas runs 900-1,000 "
         "Btu/scf and nothing read here pins it; equals the 'Sensitivity: CNG at 900 "
         "Btu/scf' row of transport_totals and the captive category's treatment"),
        ("offroad_n2o_road_factor",
         lambda: _scaled(engine.build_components(data), n2o_scale,
                         lambda c: c["category"] == offroad.CATEGORY
                         and c["gas"] == "N2O"),
         "the table-choice case: 1A4c N2O on road Table 3.2.2 (3.9 kg/TJ) instead of "
         "the pinned Table 3.3.1 (28.6) - the trap tests/test_transport.py exists to "
         "keep shut, priced"),
        ("cng_excluded",
         lambda: [c for c in engine.build_components(data)
                  if not c["subitem"].startswith("CNG")],
         "the exclusion bound: the sector as it stood before August 2026, with the "
         "OGRA transport row unread - what the stale 'absent entirely' description "
         "would cost today"),
    ]
    out = []
    for i, (name, build, note) in enumerate(cases):
        comps = build()
        det = sum(c["co2e_Mt_AR5"] for c in comps)
        stats, _s = mc_core.run(comps, list(engine.CATEGORIES), n_iter=n_iter,
                                seed=seed + i)
        s = stats["TOTAL"]
        out.append(_scen_row(name, det, comps=comps, mean=s["mean"], p025=s["p025"],
                             p50=s["p50"], p975=s["p975"], note=note))

    # The two-basis crosscheck priced as a conditional band: if CNG energy were the
    # fleet model's vehicle-km at the plausibility bounds instead of OGRA's metered
    # gas, the CNG stream scales by (vkt x MJ/km) / metered TJ. Deterministic rows,
    # no sampling - the bounds are judgement, not a Pakistani measurement.
    summary = cng_gap.summary(data)
    ref = sum(c["co2e_Mt_AR5"] for c in engine.build_components(data))
    for bound, mj in zip(("low", "high"), cng_gap.PLAUSIBLE_MJ_PER_KM):
        scale = (summary["cng_vkt"] * mj / 1e6) / summary["gas_TJ"]
        comps = _scaled(engine.build_components(data), scale,
                        lambda c: c["subitem"].startswith("CNG"))
        out.append(_scen_row(
            "cng_fleet_energy_%s" % bound,
            sum(c["co2e_Mt_AR5"] for c in comps), comps=comps,
            note="the fleet-basis bound: CNG at the modelled vehicle-km "
                 "times %.1f MJ/km instead of metered gas (x%.2f the "
                 "metered energy). The verdict is %s - the sector reports "
                 "the metered basis and this row prices the disagreement"
                 % (mj, scale, summary["verdict"])))

    # --- The within-channel and calendar-boundary cases (August 2026 round 3).
    # All deterministic post-loop rows: the seeded streams above are untouched, so
    # the pre-existing scenario rows regenerate bit-identically.
    from pkinv.sectors.transport import timeseries as _ts
    cy = _ts.calendar_year_road_t(2022)
    gen_kt = road.generator_petrol_kt()
    fy_petrol = data.efv("transport_fuel_supply", "Motor Gasoline")
    fy_diesel = data.efv("transport_fuel_supply", "Gas/Diesel Oil")
    cy_petrol = (cy["MS"] + cy["HOBC"]) / 1000.0
    cy_diesel = cy["HSD"] / 1000.0
    petrol_scale = (cy_petrol - gen_kt) / (fy_petrol - gen_kt)
    diesel_scale = cy_diesel / fy_diesel
    cy_comps = _scaled(
        _scaled(engine.build_components(data), petrol_scale,
                lambda c: c["category"] == road.CATEGORY
                and " Petrol " in " %s " % c["subitem"]),
        diesel_scale,
        lambda c: (c["category"] == offroad.CATEGORY
                   or " Diesel " in " %s " % c["subitem"]))
    out.append(_scen_row(
        "calendar_2022_controls", sum(c["co2e_Mt_AR5"] for c in cy_comps),
        comps=cy_comps,
        note="the calendar-year construction: Road controls rebuilt for "
             "January-December 2022 from the monthly panel (petrol %.0f "
             "kt, diesel %.0f kt - CY2022 straddles the mid-2022 demand "
             "collapse, hence well below the FY2021-22 rows). Petrol "
             "streams scaled net of the generator carve-out, which is "
             "held at its absolute expenditure-derived quantity; CNG "
             "held at the OGRA fiscal-year figure; off-road partition "
             "share held. Provincial detail is structurally unavailable "
             "for Jul-Dec (cumulative editions are national-only)"
             % (cy_petrol, cy_diesel)))
    onroad_diesel_match = (lambda c: c["category"] == road.CATEGORY
                           and " Diesel " in " %s " % c["subitem"])
    # These are TRANSFERS, not reductions. Diesel bought at a pump and burnt in a tube
    # well still burns; it books to 1A4c i instead of 1A3b. The national effect is
    # therefore only the difference between the two factor tables - and since CO2 is
    # 74,100 kg/TJ in the road table and in both stationary tables alike, not one tonne
    # of CO2 moves. Reporting only the transport-side fall would have read as a
    # national saving, which is exactly backwards.
    road_per_TJ = _diesel_co2e_per_TJ(data, "transport_fuel")
    recv_per_TJ = _diesel_co2e_per_TJ(data, "stationary_diesel_1a4ci")
    alt_per_TJ = _diesel_co2e_per_TJ(data, "stationary_diesel_1a2")
    onroad_TJ = road.fuel_TJ(data)["Diesel"] - road.off_road_TJ(data)
    for pct, name in ((0.025, "retail_nonroad_2p5pct"),
                      (0.05, "retail_nonroad_5pct"),
                      (0.10, "retail_nonroad_10pct")):
        comps = _scaled(engine.build_components(data), 1.0 - pct,
                        onroad_diesel_match)
        x_TJ = pct * onroad_TJ
        out.append(_scen_row(
            name, sum(c["co2e_Mt_AR5"] for c in comps), comps=comps,
            receiving_category="1.A.4.c i (stationary agriculture, Table 2.5)",
            receiving_Mt=x_TJ * recv_per_TJ / 1e9,
            national_delta_Mt=x_TJ * (recv_per_TJ - road_per_TJ) / 1e9,
            note="the within-channel case, as a CROSS-SECTOR TRANSFER: %.1f%% of "
                 "on-road Road-row diesel (%.0f TJ) assumed retail-bought by "
                 "non-road users (stationary agricultural plant, captive "
                 "generation) and REBOOKED to 1A4c i. deterministic is this sector "
                 "after the transfer; receiving_Mt is what the receiving category "
                 "gains; national_delta_Mt is the whole national effect, %+.4f Mt, "
                 "which is the TRACE-GAS TABLE DIFFERENCE ALONE - CO2 is 74,100 "
                 "kg/TJ in Table 3.2.1 and Table 2.5 alike, so no CO2 moves at "
                 "all. On Table 2.3 (1A2 captive generation, the ledger's other "
                 "unresolved claimant) the national delta is %+.4f Mt instead. "
                 "This inventory does not estimate 1A4c i stationary agriculture, "
                 "so the receiving quantity goes to an UNESTIMATED category and is "
                 "not a national saving. This is the sensitivity the customer-class "
                 "boundary panel cannot provide - that panel bounds the sales "
                 "channel, not the contamination within it"
                 % (100 * pct, x_TJ, x_TJ * (recv_per_TJ - road_per_TJ) / 1e9,
                    x_TJ * (alt_per_TJ - road_per_TJ) / 1e9)))
    # Off-road partition share cases: rebalance between the two factor tables at a
    # fixed alternative share; diesel mass is conserved by construction.
    s_ref = road.off_road_TJ(data) / road.fuel_TJ(data)["Diesel"]
    for s_alt, name in ((0.05, "offroad_share_5pct"), (0.15, "offroad_share_15pct")):
        comps = _scaled(
            _scaled(engine.build_components(data), s_alt / s_ref,
                    lambda c: c["category"] == offroad.CATEGORY),
            (1.0 - s_alt) / (1.0 - s_ref), onroad_diesel_match)
        out.append(_scen_row(
            name, sum(c["co2e_Mt_AR5"] for c in comps), comps=comps,
            note="the partition case: off-road at %.0f%% of Road-row diesel "
                 "instead of the fleet model's %.2f%%. Diesel mass is conserved - "
                 "only the CH4/N2O table moves with the share - so the SECTOR "
                 "total barely moves while the off-road CATEGORY moves by about "
                 "half its own size. Read road_Mt and offroad_Mt, not the total: "
                 "the reported +/-28%% off-road interval is conditional on this "
                 "share, and this row is what the condition costs"
                 % (100 * s_alt, 100 * s_ref)))
    # The factor-mix question, answered by invariance: IPCC Table 3.3.1's Industry
    # diesel row is numerically identical to its Agriculture row (verified against
    # the chapter PDF), so the mixed class's agriculture-vs-construction
    # composition cannot move the estimate under the correct table.
    mix_scale_ch4 = (data.efv("offroad_machinery_ch4_industry", "Gas/Diesel Oil")
                     / data.efv("offroad_machinery_ch4", "Gas/Diesel Oil"))
    mix_scale_n2o = (data.efv("offroad_machinery_n2o_industry", "Gas/Diesel Oil")
                     / data.efv("offroad_machinery_n2o", "Gas/Diesel Oil"))
    mix_comps = _scaled(
        _scaled(engine.build_components(data), mix_scale_ch4,
                lambda c: c["category"] == offroad.CATEGORY and c["gas"] == "CH4"),
        mix_scale_n2o,
        lambda c: c["category"] == offroad.CATEGORY and c["gas"] == "N2O")
    out.append(_scen_row(
        "offroad_factor_mix_construction",
        sum(c["co2e_Mt_AR5"] for c in mix_comps), comps=mix_comps,
        note="INVARIANCE, proved executably: the mixed class rebuilt on "
                        "Table 3.3.1's Industry diesel row instead of Agriculture. "
                        "The two rows are numerically identical (CH4 4.15, N2O "
                        "28.6 kg/TJ - verified against the chapter PDF), so the "
                        "agriculture-vs-construction composition question is "
                        "factor-invariant under the correct table; only the "
             "road-table trap (offroad_n2o_road_factor) moves the answer"))

    # The reporting-recode scenario for the renamed mixed off-road class: the
    # sector total is unchanged by construction - only which IPCC code receives
    # the 1A4c-reported quantity moves - so the row is deterministic and its note
    # carries the category-level consequence.
    off_total = sum(c["co2e_Mt_AR5"] for c in engine.build_components(data)
                    if c["category"] == offroad.CATEGORY)
    out.append(_scen_row(
        "offroad_reallocated_1a2", ref, comps=engine.build_components(data),
        scope="GHG reporting allocation",
        receiving_category="1.A.2 g vii (construction/industrial mobile)",
        receiving_Mt=off_total, national_delta_Mt=0.0,
        note="REPORTING RECODE, not a sample: the mixed off-road class "
                        "(%.3f Mt) reported under 1A2 instead of 1A4c. The sector "
                        "total cannot move - the fuel partition is unchanged - "
                        "which is what the deterministic column shows; what moves "
                        "is which IPCC category receives the quantity, and no "
                        "equipment-stock data here supports splitting the residual "
             "between the two codes. national_delta_Mt is exactly zero: the same "
             "fuel, the same factors, a different code" % off_total))
    # --- The class-composition axis (August 2026 round 4). The split is now
    # VKT x declared MJ/km; these rows are what the declaration costs. Deterministic:
    # the bands are engineering judgement, not a distribution, and sampling them would
    # dress judgement as measurement.
    for basis, name in (("lo", "class_intensity_low"), ("hi", "class_intensity_high")):
        comps = engine.build_components(data, intensity_basis=basis)
        vkt, _c, _cap = road.effective_vkt(data)
        alt = road._shares(data, vkt, basis)
        out.append(_scen_row(
            name, sum(c["co2e_Mt_AR5"] for c in comps), comps=comps,
            note="the class-composition case: every within-fuel weight rebuilt at "
                 "the %s end of the declared MJ/km bands instead of their "
                 "midpoints. The two-wheeler petrol weight moves to %.4f and the "
                 "off-road partition to %.5f. The SECTOR total barely moves, "
                 "because the weights are normalised within each fuel and only the "
                 "partition escapes into a second category - that invariance is "
                 "the point. Note this is a CORRELATED shift, every class to the "
                 "same end of its band, which the normalisation largely absorbs; "
                 "the intensity_ratio_* rows below perturb the classes against one "
                 "another, which is what actually moves composition"
                 % (basis, alt[("2W", "Petrol")], alt[(road.OFF_ROAD, "Diesel")])))

    # The contrast cases. A uniform band shift mostly cancels in the normalisation, so
    # reporting only class_intensity_low/high would understate composition uncertainty
    # by construction. These move the classes AGAINST each other - light vehicles at
    # one end of their bands while heavy vehicles sit at the other - which is the
    # honest envelope on "which class burns the fuel".
    LIGHT = ("2W", "3W")
    for light, name in (("lo", "intensity_ratio_light_low"),
                        ("hi", "intensity_ratio_light_high")):
        heavy = "hi" if light == "lo" else "lo"
        vkt, _c, _cap = road.effective_vkt(data)
        mixed = {k: v * data.mjkm(k[0], k[1], light if k[0] in LIGHT else heavy)
                 for k, v in vkt.items()}
        shares = {}
        for fuel in road.FUELS:
            cells = {k: v for k, v in mixed.items() if k[1] == fuel}
            tot = sum(cells.values())
            for k, v in cells.items():
                shares[k] = v / tot if tot else 0.0
        base = engine.build_components(data)
        ref_shares = road._shares(data, vkt)
        off_key = (road.OFF_ROAD, "Diesel")
        comps = []
        for c in base:
            c2 = dict(c)
            # The off-road category is the same normalisation's NRV-diesel cell, but
            # its components are named for the category rather than the class, so it
            # has to be matched separately - miss it and the diesel control stops
            # being conserved, which is the one thing these rows must not do.
            if c["category"] == offroad.CATEGORY:
                key = off_key
            else:
                key = next(((cls, f) for (cls, f) in shares
                            if c["subitem"].startswith("%s %s " % (cls, f))), None)
            if key and ref_shares.get(key):
                for col in ("emissions_Gg", "co2e_Mt_AR5", "co2e_Mt_AR6"):
                    if col in c2:
                        c2[col] = c2[col] * shares[key] / ref_shares[key]
            comps.append(c2)
        out.append(_scen_row(
            name, sum(c["co2e_Mt_AR5"] for c in comps), comps=comps,
            note="the contrast case: two- and three-wheelers at the %s end of "
                 "their MJ/km bands while every heavier class sits at the %s end. "
                 "The two-wheeler petrol weight moves to %.4f against the "
                 "reference %.4f - a far wider swing than the correlated "
                 "class_intensity_* rows produce, because a uniform shift cancels "
                 "in the within-fuel normalisation and an opposing one does not. "
                 "The fuel totals are still untouched: this moves only which class "
                 "is said to have burnt them. The sector total coincides with a "
                 "class_intensity_* row because two- and three-wheelers burn no "
                 "diesel, so the off-road partition - the only route by which any "
                 "of this reaches a category total - is set by the heavy classes "
                 "alone in both cases"
                 % (light, heavy, shares[("2W", "Petrol")],
                    ref_shares[("2W", "Petrol")])))

    out.append(_scen_row(
        "class_split_declaration", ref, comps=engine.build_components(data),
        scope="GHG distribution between classes",
        note="SCOPE DECLARATION, not a sample: the fuel control is split between "
             "classes by vehicle-km times a DECLARED ENGINEERING-JUDGEMENT energy "
             "intensity (data/transport_params.csv, mjkm_lo_*/mjkm_hi_*), not by "
             "any Pakistani fuel-economy measurement - none has been obtained. "
             "Until August 2026 the split used distance alone, which asserts that "
             "a motorcycle-kilometre and a truck-kilometre burn the same fuel; "
             "correcting it moved the two-wheeler petrol weight from 0.8119 (distance "
             "alone) to 0.6100 and made heavy diesel, not two-wheelers, the largest share of "
             "on-road CO2. The judgement is bounded by construction - weights are "
             "normalised within each fuel, so no intensity choice can move the "
             "sector TOTAL, which is what the deterministic column shows - and "
             "priced by class_intensity_* and intensity_ratio_*"))
    out.append(_scen_row(
        "air_factor_provenance", "", scope="air: all pollutants",
        note="SCOPE DECLARATION, not a sample: the per-kilometre air factors are "
             "Punjab-workbook transcriptions with no primary citation located "
             "(air_pollutants.py; data/activity/transport/emission_factors_gkm.csv "
             "has no source column). Exhaust only - no cold start, evaporation, or "
             "brake/tyre/road wear. The air layer should be read as "
             "order-of-magnitude until factors with provenance replace them; no "
             "published Pakistani alternative supports sampling"))
    return out


def inputs_register(data):
    def row(variable, central, unit, u, dist, source, applies_to, group, klass,
            note=""):
        return {"variable": variable, "central_value": central, "unit": unit,
                "uncert_pct_95": u, "distribution": dist, "source": source,
                "applies_to": applies_to, "correlation_group": group,
                "uncertainty_class": klass, "note": note}

    d = data
    lo, hi = _road_share_panel(d)
    chk = road.rail_crosscheck(d)
    rows = [
        row("Petrol control total", d.efv("transport_fuel_supply", "Motor Gasoline"),
            "kt/yr", d.efu("transport_fuel_supply", "Motor Gasoline"), "lognormal",
            "OCAC Sectoral Sales FY2021-22, Road row (MS + HOBC)",
            "all petrol rows", "1a3b_petrol_control", "parametric",
            "declared judgement at 10%: OCAC's data are member-supplied and "
            "unverified by its own disclaimer; internal additivity is exact, the "
            "monthly panel closes to this row within 0.2%, and the one independent "
            "cross-check on a sibling row disagrees by 5.2% - so 10% is roughly "
            "twice the observed error. Net of the household-generator carve-out "
            "relayed from residential"),
        row("Diesel control total", d.efv("transport_fuel_supply", "Gas/Diesel Oil"),
            "kt/yr", d.efu("transport_fuel_supply", "Gas/Diesel Oil"), "lognormal",
            "OCAC Sectoral Sales FY2021-22, Road row (HSD)",
            "all diesel rows incl. off-road", "1a3b_diesel_control", "parametric",
            "declared judgement at 10%% (see the petrol row). Rail is excluded by "
            "construction (its own OCAC row); retail agricultural and captive "
            "diesel remain inside - the boundary structural axis, bounded by the "
            "Road-share panel %.3f-%.3f" % (lo, hi)),
        row("Rail figure cross-check (year-matched FY2021-22)",
            chk["rel_diff_matched"], "relative difference", "", "not sampled",
            "Year Book 2022-23 Principal Statistics FY2021-22 row (%.1f kt) vs "
            "OCAC Railways row (%.1f kt)"
            % (chk["yb_kt"], chk["ocac_kt"]),
            "the diesel boundary", "", "parametric",
            "two unrelated reporting chains 1.6% apart at the matched year - the "
            "one independent check the boundary has"),
        row("Rail figure cross-check (FY2023-24 relay)", chk["rel_diff"],
            "relative difference", "", "not sampled",
            "Year Book FY2023-24 relay (%.1f kt) vs OCAC FY2021-22 Railways row "
            "(%.1f kt)" % (chk["yb_kt"], chk["ocac_kt"]),
            "the diesel boundary", "", "parametric",
            "the conservative cross-year comparison at 5.2%; together with the "
            "matched pair it anchors the controls' declared 10%"),
        row("Petrol NCV", d.efv("transport_ncv", "Motor Gasoline"), "TJ/Gg",
            d.efu("transport_ncv", "Motor Gasoline"), "lognormal",
            "IPCC 2006 Vol 2 Ch 1 Table 1.2", "all petrol rows",
            "1a3b_petrol_control", "parametric"),
        row("Diesel NCV", d.efv("transport_ncv", "Gas/Diesel Oil"), "TJ/Gg",
            d.efu("transport_ncv", "Gas/Diesel Oil"), "lognormal",
            "IPCC 2006 Vol 2 Ch 1 Table 1.2", "all diesel rows incl. off-road",
            "1a3b_diesel_control", "parametric"),
        row("CNG metered volume FY2021-22", d.cng_mmcfd(), "MMCFD",
            d.p("cng_activity_uncert"), "lognormal",
            "OGRA State of the Regulated Petroleum Industry, Tables 3.31 and 6.1 "
            "(they agree)", "all CNG rows", "delivered_gas_ogra_3_31", "parametric",
            "SHARED GROUP (rc19): one OGRA Table 3.31 publication behind the "
            "residential, CNG, industrial and captive delivered volumes; the "
            "heating-value and gross-to-net members stay module-local in "
            "1a3b_cng_chain"),
        row("CNG gross heating value", d.p("cng_hhv_btu_per_scf"), "Btu/scf gross",
            d.pu("cng_hhv_btu_per_scf"), "lognormal", d.ps("cng_hhv_btu_per_scf"),
            "all CNG rows", "1a3b_cng_chain", "parametric",
            "pinned equal to the captive category's value by test; the 900 case is "
            "scenario cng_hhv_900"),
        row("CNG gross-to-net conversion", d.p("cng_gross_to_net"), "fraction",
            d.pu("cng_gross_to_net"), "lognormal", d.ps("cng_gross_to_net"),
            "all CNG rows", "1a3b_cng_chain", "parametric",
            "IPCC works on a net basis and the utilities bill gross"),
        row("Fleet composition and VKT", d.p("activity_uncert"), "percent", "",
            "distribution-only", "IPCC 2006 Vol 2 Ch 3 s3.2.1",
            "class split within each fuel", "", "parametric",
            "DEMOTED from the sector band: shares are normalised within each fuel, "
            "so this term moves the split, never the total"),
        row("IPCC road factors (Tables 3.2.1/3.2.2)", "per-row", "kg/TJ",
            "row-specific", "lognormal", "IPCC 2006 Vol 2 Ch 3",
            "road CO2/CH4/N2O rows", "", "parametric",
            "CO2 tight; CH4 and N2O carry the chapter's wide default intervals"),
        row("IPCC off-road factors (Table 3.3.1)", "per-row", "kg/TJ",
            "row-specific", "lognormal", "IPCC 2006 Vol 2 Ch 3",
            "off-road rows", "", "parametric",
            "N2O at 28.6 kg/TJ vs the road table's 3.9; the choice is pinned by "
            "test and priced by scenario offroad_n2o_road_factor"),
        row("Railway diesel carve-out", road.rail_diesel_kt(), "kt/yr", "",
            "not sampled here", "relayed: railways.traction.diesel_kt()",
            "diesel control", "", "parametric",
            "sampled in the railways sector; the relay is exact by test"),
        row("Household-generator petrol carve-out", road.generator_petrol_kt(),
            "kt/yr", "", "not sampled here",
            "relayed: residential.combustion.generator_petrol_kt()",
            "petrol control", "", "parametric",
            "sampled in the residential sector; the relay is exact by test"),
        row("Weibull survival (beta, median life)", "per-class", "shape, years",
            "", "not sampled", "Punjab Transport manuscript s3.7.3 Table 5",
            "class split", "", "structural",
            "moves the distribution, not the total; the cap diagnostic "
            "(fleet cap binds on ~49% of cells) bounds how much the source "
            "workbook's convention distorts it"),
        row("Diesel end-use boundary", "retail-channel residual", "choice",
            "", "not sampled", "outputs/transport_fuel_ledger (UNRESOLVED rows)",
            "diesel rows", "", "structural",
            "retail-bought agricultural-stationary and captive diesel remain "
            "inside the Road row, biased high conditional on the other "
            "deductions; scenarios road_share_low/high and national_hsd_minus_bulk "
            "bound the boundary (transport-hsd-end-use)"),
        row("Control provenance", "OCAC Road rows (FY2021-22)", "choice", "",
            "not sampled", "scenario legacy_pes_control / pes_corrected_12_9",
            "all petroleum rows", "", "structural",
            "the superseded PES-derived controls (stored values x16/9 of their "
            "source figures) are retained as executable scenarios - the bridge to "
            "previously published numbers"),
        row("Class split basis", "vehicle-km x declared MJ/km band midpoint",
            "choice", "", "not sampled",
            "data/transport_params.csv mjkm_lo_*/mjkm_hi_* (declared judgement)",
            "class split", "", "structural",
            "scenarios class_split_declaration, class_intensity_low/high and "
            "intensity_ratio_light_low/high; normalised within fuel, so it moves "
            "composition and never the sector total"),
        row("Air-factor provenance", "Punjab workbook, uncited", "choice", "",
            "not sampled", "air_pollutants.py module docstring", "air layer", "",
            "structural", "scenario air_factor_provenance"),
        row("CNG energy basis", "metered gas, not fleet vehicle-km", "choice", "",
            "not sampled", "cng_gap.py two-basis crosscheck (FLEET-MODEL-HIGH)",
            "CNG rows", "", "structural",
            "scenarios cng_fleet_energy_low/high price the disagreement"),
    ]
    return rows


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    data = TransportData()

    a1 = approach1(data)
    with open(asset_path(OUTPUTS, "transport_uncertainty_%d.csv" % data.year),
              "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(a1.keys()))
        w.writeheader()
        w.writerow({k: (round(v, 5) if isinstance(v, float) else v)
                    for k, v in a1.items()})

    decomp = variance_decomposition(data)
    write_table(asset_path(OUTPUTS,
                           "transport_variance_decomposition_%d.csv" % data.year), list(decomp[0].keys()), decomp)

    with open(asset_path(OUTPUTS,
                           "transport_uncertainty_inputs_%d.csv" % data.year),
              "w", newline="", encoding="utf-8") as f:
        rows = inputs_register(data)
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    scen = structural_scenarios(data)
    # Fieldnames come from the contract, not from whatever the first row happens to
    # carry, and a row that does not match it is a failure rather than a silently
    # truncated file.
    bad = [r["structural_scenario"] for r in scen if set(r) != set(SCEN_FIELDS)]
    if bad:
        raise SystemExit("scenario rows with missing or extra columns: %s" % bad)
    with open(asset_path(OUTPUTS,
                           "transport_uncertainty_scenarios_%d.csv" % data.year),
              "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(SCEN_FIELDS))
        w.writeheader()
        for r in scen:
            w.writerow({k: (round(v, 5) if isinstance(v, float) else v)
                        for k, v in r.items()})

    print("Transport Approach 1: %.1f%% grouped (within-fuel), %.1f%% grouped "
          "(cross-fuel controls), %.1f%% independent on %.5f Mt"
          % (a1["approach1_pct_grouped"], a1["approach1_pct_grouped_crossfuel"],
             a1["approach1_pct_independent"], a1["co2e_Mt_AR5"]))
    for r in scen:
        if isinstance(r["deterministic"], float) and r["P2.5"] != "":
            print("  %-26s %.5f Mt  [%.3f, %.3f]"
                  % (r["structural_scenario"], r["deterministic"], r["P2.5"],
                     r["P97.5"]))
        elif isinstance(r["deterministic"], float):
            print("  %-26s %.5f Mt  (deterministic)"
                  % (r["structural_scenario"], r["deterministic"]))


if __name__ == "__main__":
    main()
