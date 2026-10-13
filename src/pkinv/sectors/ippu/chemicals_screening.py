"""Non-cement IPPU screening: the categories the register bounded but never priced.

WHY (Wave 4, the sixteenth review's annual-completeness program). The Pass-2 baseline
names "non-cement IPPU" as a component of the countable annual-scope floor, and until
this module it carried NO number anywhere in the tree: 35 of the 36 IPPU completeness
rows are NE, four of them at critical/high materiality, while the activity that would
price them sits held in data/activity/ippu/. This module runs the screening arithmetic
the held activity supports and publishes every result in one file with its evidence
state - a priced configuration where the mass is material, a bound-below-materiality
row where it is not, and a typed refusal where the activity is missing. Nothing here
enters the reference total; the categories stay NE (Pass-2 Rule 3).

THE FOUR DECISIONS, stream by stream:

- NITRIC ACID (2.B.2, materiality critical). One of the two identified plants has
  production: Fatima Sadiqabad, 563,701 t of acid, CALENDAR 2022 - a prior vintage,
  declared like the brick kiln's. Its own activation gate names the two configurations
  this module ships: `nitric_acid_unabated_in_scope` (the plant's output under the
  technology-matched IPCC medium-pressure factor - a dual-pressure train's N2O forms in
  its medium-pressure combustion stage) and `nitric_acid_abated_in_scope` (the same,
  minus the destruction the plant's OWN ACM0019 record verified in its last monitored
  year). CDM CERs are denominated at the SAR N2O GWP of 310, so the verified reduction
  is converted to tonnes of N2O before this inventory's AR5 265 is applied - quoting
  the CER figure as AR5 CO2e would overstate the destruction by 17 percent. Both
  configurations are FLOORS of the category: Pakarab Multan's nitric line is
  identified with no activity. Reference entry stays refused - the gate demands
  operating evidence for the abatement, and the last verified year is 2018-19.

- AMMONIA (2.B.1). Priced by a Tier-1 CALIBRATED estimate (the method is in
  ammonia_rows below; the pathway roles are in ammonia_reconciliation):

      E_2.B.1 = A_NH3 x EF_gross - CO2_recovered_to_urea

  A_NH3 is the product-stoichiometry activity (~4.45 Mt NH3, the PRIMARY national
  activity estimate; NFDC nitrogen x 17/14 = 4.40 Mt validates it independently);
  EF is the Pakistan-calibrated 1.815 t CO2/t central (derived to reproduce the
  BTR's 3.02 Mt 2020-21 filing); recovery is the year's audited urea x 44/60. The
  `ammonia_feedstock_in_scope` configuration prices the CENTRAL 3.24 Mt, with a
  2.70-4.53 method envelope spanning the IPCC modern (1.694) and conventional
  (2.104) factors - a methodological sensitivity, not a statistical interval. The
  recovery split keeps 2.B.1 and agriculture's 3.H apart: IPPU's term rides urea
  PRODUCED, 3.H rides urea APPLIED. Pakistan's 2022 CRT implies ~19.4 Mt under
  chemical industries - QUARANTINED as an apparent official inconsistency with the
  same country's 3.02 Mt BTR filing, never adopted; the gas balance, plant census
  and CRT survive as QA evidence in the reconciliation, not as competing estimates.
  Feedstock gas is excluded from every combustion total (the gas closure's
  feedstock_excluded lane) and the total-energy factor already prices process fuel,
  so nothing double-counts 1.A.2 combustion. Since rc67 the post-meter leak factor
  rides the process fuel only; the feedstock is outside its base, and the old
  membership is a separately priced axis.

- STEEL (2.C.1) and SODA ASH (2.B.7): countable, and BELOW the 1 Mt materiality line
  the commercial audit uses, so they ship as bound rows rather than configurations -
  axis noise is a cost too. Steel: 4.914 Mt of billets beside ZERO reported pig iron
  (PBS QIM), so the scrap-based electric route is the only one the observed record
  supports, and the EAF factor prices it at ~0.4 Mt; the blast-furnace factor is
  eighteen times larger, which is why the ROUTE evidence is what the request must
  confirm. Soda ash: the QIM tonnage under the natural-process factor as a
  route-agnostic ceiling, ~0.08 Mt - bounded SMALL, the bagasse pattern.

- GLASS (2.A.3) and LIME (2.A.2): typed refusals. Glass activity is held as AREA
  (thousand m2) and no thickness/density evidence converts it to mass; no
  lime-production series is held in any acquired source. Each refusal names its
  closer.

Usage:  written by run_ippu on every run; also
        python3 -m pkinv.sectors.ippu.chemicals_screening
Writes: outputs/ippu_chemicals_screening_2024.csv
"""
from __future__ import annotations

import csv
import os

from pkinv.core.gwp import GWP
from pkinv.core.units import mmcfd_to_TJ
from pkinv.paths import OUTPUTS
from pkinv.sectors.ippu import chemicals
from pkinv.core.io import write_table
from pkinv.assets import asset_path

GWP_N2O_AR5 = GWP["AR5"]["N2O"]
CDM_CER_GWP_N2O = 310.0     # SAR, the CDM's denomination for ACM0019 CERs
NITRIC_PLANT = "fert_fatima_sadiqabad"
NITRIC_VINTAGE_YEAR = 2022  # calendar; the prior-vintage declaration, brick-kiln style
MATERIALITY_MT = 1.0        # the commercial audit's line, reused deliberately

FIELDS = ("configuration", "ipcc_code", "stream", "vintage", "adjustment_Mt_co2e",
          "bracket_low_Mt", "bracket_high_Mt", "evidence_state", "note")


def _nitric_production_t(data):
    for r in data.chemical_plant_activity_rows:
        if (r["facility_id"] == NITRIC_PLANT and r["product"] == "Nitric acid"
                and int(r["period_end_year"]) == NITRIC_VINTAGE_YEAR):
            return float(r["production_t"])
    raise KeyError("the Sadiqabad 2022 nitric-acid row has left the activity file; "
                   "the screening has lost its basis")


def _last_verified_reduction_t_co2e(data):
    """The plant's last monitored ACM0019 period, ANNUALISED (SAR CO2e per year).

    Monitoring periods are not calendar years - the final Sadiqabad period spans
    twenty months - so the verified total is scaled by the period's own day count.
    Reading the period total as an annual rate overstated the destruction by two
    thirds on the very first run of this module."""
    from datetime import date
    annual = [r for r in data.nitric_acid_monitoring_rows
              if r["facility_id"] == NITRIC_PLANT
              and r["issuance_status"] == "issued"
              and r["metric"] == "verified emission reductions"]
    if not annual:
        raise KeyError("no issued ACM0019 monitoring rows; the abated variant has "
                       "lost its evidence")
    last = max(annual, key=lambda r: r["monitoring_end"])
    start = date.fromisoformat(last["monitoring_start"])
    end = date.fromisoformat(last["monitoring_end"])
    days = (end - start).days + 1
    per_year = float(last["value_t_co2e"]) * 365.25 / days
    return per_year, last["monitoring_start"], last["monitoring_end"]


def nitric_rows(data):
    production_t = _nitric_production_t(data)
    ef_med = data.p("nitric_acid_ef_medium_pressure")
    ef_high = data.p("nitric_acid_ef_high_pressure")
    gross_n2o_t = production_t * ef_med / 1000.0
    unabated_mt = gross_n2o_t * GWP_N2O_AR5 / 1e6
    unabated_hi_mt = production_t * ef_high / 1000.0 * GWP_N2O_AR5 / 1e6

    cer_t, mon_start, mon_end = _last_verified_reduction_t_co2e(data)
    destroyed_n2o_t = cer_t / CDM_CER_GWP_N2O
    abated_mt = max(gross_n2o_t - destroyed_n2o_t, 0.0) * GWP_N2O_AR5 / 1e6

    shared = {"ipcc_code": "2.B.2", "stream": "Nitric acid (Fatima Sadiqabad)",
              "vintage": "calendar 2022 production (declared prior vintage)"}
    return [
        dict(shared, configuration="nitric_acid_unabated_in_scope",
             adjustment_Mt_co2e=round(unabated_mt, 5),
             bracket_low_Mt=round(unabated_mt, 5),
             bracket_high_Mt=round(unabated_hi_mt, 5),
             evidence_state="screening_transferred_factor_prior_vintage",
             note="the plant's 563,701 t of acid under the technology-matched IPCC "
                  "medium-pressure factor (7 kg N2O/t; the dual-pressure train's N2O "
                  "forms in its medium-pressure combustion stage), no abatement "
                  "operating. A FLOOR of the category: Pakarab Multan's nitric line "
                  "is identified with no activity. The high-pressure default (9) "
                  "bounds the bracket"),
        dict(shared, configuration="nitric_acid_abated_in_scope",
             adjustment_Mt_co2e=round(abated_mt, 5),
             bracket_low_Mt="", bracket_high_Mt="",
             evidence_state="screening_abatement_last_verified_rate",
             note="the same production minus the destruction the plant's own ACM0019 "
                  "record verified in its last monitored period (%s to %s), "
                  "ANNUALISED over the period's own day count: %.0f t CO2e/yr of "
                  "CERs at the SAR GWP of 310 = %.0f t N2O/yr destroyed, "
                  "re-expressed at AR5 265 here. Whether the catalyst still operates "
                  "is exactly the operating evidence the activation gate demands "
                  "before either reading can enter the reference"
                  % (mon_start, mon_end, cer_t, destroyed_n2o_t)),
    ]


def ammonia_rows(data):
    """The Tier-1 CALIBRATED ammonia estimate (2026-09-10, at the user's direction):

        E_2.B.1 = A_NH3 x EF_gross - CO2_recovered_to_urea      (IPCC Eq 3.9/3.10)

    with A_NH3 the product-stoichiometry activity (the PRIMARY national activity
    estimate, ~4.45 Mt NH3 embodied in NFDC's production), EF the Pakistan-calibrated
    1.815 t CO2/t NH3 central (2.B.1 params, derived to reproduce the BTR's 3.02 Mt
    2020-21 filing), and recovery urea x 44/60. Central ~3.24 Mt; the method envelope
    2.70-4.53 spans the IPCC modern (1.694) and conventional (2.104) factors - a
    methodological sensitivity, NOT a statistical interval. This REPLACES the old
    gas-balance ceiling as the configuration's estimate; the gas balance, plant
    census and CRT survive as QA evidence in the reconciliation, not as competing
    estimates."""
    from pkinv.sectors.ippu.ammonia_reconciliation import product_nh3_kt, _production_kt
    nh3_kt = product_nh3_kt(data, "2023-24")
    urea_kt = _production_kt(data, "Urea", "2023-24")
    recovered_kt = urea_kt * data.p("urea_co2_recovery_factor")

    def net_co2_mt(ef):
        component, _ledger = chemicals.ammonia_component(
            nh3_kt, ef, recovered_to_urea_kt=recovered_kt)
        return component["emissions_Gg"] / 1000.0

    central_mt = net_co2_mt(data.p("ammonia_ef_calibrated"))
    low_mt = net_co2_mt(data.p("ammonia_ef_modern"))
    high_mt = net_co2_mt(data.p("ammonia_ef_total_energy"))

    return [
        {"configuration": "ammonia_feedstock_in_scope", "ipcc_code": "2.B.1",
         "stream": "Ammonia process CO2 (Tier-1 calibrated)",
         "vintage": "FY2023-24",
         "adjustment_Mt_co2e": round(central_mt, 5),
         "bracket_low_Mt": round(low_mt, 5),
         "bracket_high_Mt": round(high_mt, 5),
         "evidence_state": "tier1_calibrated_central",
         "note": "%.0f kt NH3 (product-stoichiometry activity, the primary estimate; "
                 "NFDC nitrogen x 17/14 validates it independently) x the calibrated "
                 "1.815 t CO2/t total-energy factor, minus the %.0f kt CO2 recovered "
                 "into the year's audited urea (44/60) - the recovery split that keeps "
                 "2.B.1 and agriculture's 3.H apart. Central %.2f Mt; the 2.70-4.53 "
                 "envelope spans the IPCC modern (1.694) and conventional (2.104) "
                 "factors, a method sensitivity not a confidence interval. Calibrated "
                 "to reproduce Pakistan's own 3.02 Mt (2020-21) BTR filing, with the "
                 "~2.7 Mt (2018) filing a second check; the CRT's implied 19.4 Mt is "
                 "quarantined as an apparent official inconsistency, not adopted. "
                 "Feedstock gas is outside every combustion total (gas closure: "
                 "feedstock_excluded) and the total-energy factor already prices "
                 "process fuel, so nothing double-counts 1.A.2 combustion; the "
                 "recovered carbon re-emerges at urea application under 3.H"
                 % (nh3_kt, recovered_kt, central_mt)},
    ]


def _national_activity_t(data, ipcc_code, product):
    for r in data.activity_rows:
        if r["ipcc_code"] == ipcc_code and r["product"] == product:
            return float(r["quantity"]), r["source_reference"]
    raise KeyError("%s %s has left national_activity.csv" % (ipcc_code, product))


def bound_rows(data):
    steel_t, steel_src = _national_activity_t(data, "2.C.1", "Billets and ingots")
    steel_mt = steel_t * data.p("steel_eaf_ef") / 1e6
    soda_t, soda_src = _national_activity_t(data, "2.B.7", "Soda ash")
    soda_mt = soda_t * data.p("soda_ash_natural_process_ef") / 1e6
    if steel_mt >= MATERIALITY_MT or soda_mt >= MATERIALITY_MT:
        raise SystemExit("a bound row crossed the %.0f Mt materiality line - promote "
                         "it to a configuration instead of shipping it quietly"
                         % MATERIALITY_MT)
    return [
        {"configuration": "(bound, below materiality)", "ipcc_code": "2.C.1",
         "stream": "Iron and steel (electric route)", "vintage": "FY2023-24",
         "adjustment_Mt_co2e": "", "bracket_low_Mt": round(steel_mt, 5),
         "bracket_high_Mt": round(steel_mt, 5),
         "evidence_state": "bounded_below_materiality",
         "note": "4.914 Mt of billets (%s) beside ZERO reported pig iron, so the "
                 "scrap-based electric route is the only one the observed record "
                 "supports: ~%.2f Mt at the EAF factor. The blast-furnace factor is "
                 "eighteen times larger - the ROUTE evidence, not the factor, is what "
                 "a data request must confirm, and the bound holds only while no "
                 "primary ironmaking operates" % (steel_src, steel_mt)},
        {"configuration": "(bound, below materiality)", "ipcc_code": "2.B.7",
         "stream": "Soda ash production", "vintage": "FY2023-24",
         "adjustment_Mt_co2e": "", "bracket_low_Mt": 0.0,
         "bracket_high_Mt": round(soda_mt, 5),
         "evidence_state": "bounded_below_materiality",
         "note": "the QIM tonnage (%s) under the natural-process factor as a "
                 "route-agnostic CEILING (~%.2f Mt): Pakistan's plants are "
                 "Solvay-route, whose net process CO2 is smaller, so either route "
                 "stays under a tenth of a megatonne - bounded SMALL, the bagasse "
                 "pattern, not an estimate" % (soda_src, soda_mt)},
    ]


def refusal_rows():
    return [
        {"configuration": "(refused)", "ipcc_code": "2.A.3", "stream": "Glass",
         "vintage": "", "adjustment_Mt_co2e": "", "bracket_low_Mt": "",
         "bracket_high_Mt": "", "evidence_state": "refused_activity_not_mass",
         "note": "the held activity is AREA (20,205 thousand m2 of plates and "
                 "sheets, PBS QIM item 82) and no thickness/density evidence "
                 "converts it to the glass MASS the carbonate arithmetic needs; "
                 "closer: producer product-mix disclosure or the HDIP/PBS mass "
                 "series (REQ-IPPU-01)"},
        {"configuration": "(refused)", "ipcc_code": "2.A.2", "stream": "Lime",
         "vintage": "", "adjustment_Mt_co2e": "", "bracket_low_Mt": "",
         "bracket_high_Mt": "", "evidence_state": "refused_no_activity",
         "note": "no national lime-production series is held in any acquired source; "
                 "marketed plus captive lime output by type is the closer "
                 "(REQ-IPPU-01), and no bound is assigned without defensible public "
                 "activity - the fugitives completeness rule, applied here"},
    ]


def rows(data=None):
    if data is None:
        from pkinv.sectors.ippu.data import IppuData
        data = IppuData()
    reference = [{
        "configuration": "reference", "ipcc_code": "2.B.1;2.B.2;2.B.7;2.C.1",
        "stream": "(all non-cement IPPU screening streams)", "vintage": "",
        "adjustment_Mt_co2e": 0.0, "bracket_low_Mt": "", "bracket_high_Mt": "",
        "evidence_state": "reference",
        "note": "every category here stays NE in the reference (Pass-2 Rule 3): "
                "screenings are priced configurations and bounds, never bookings"}]
    return (reference + nitric_rows(data) + ammonia_rows(data) + bound_rows(data)
            + refusal_rows())


OUT = asset_path(OUTPUTS, "ippu_chemicals_screening_2024.csv")


def main():
    out = rows()
    path = OUT
    write_table(path, list(FIELDS), out, banner=('# Non-cement IPPU screenings, bounds and refusals in one file; the', '# configuration rows are read by national_configurations and every', '# category stays NE in the reference. See chemicals_screening.py.',), lineterminator="\n")
    print("non-cement IPPU screening -> %s" % path)
    for r in out:
        print("  %-34s %-8s %s" % (r["configuration"][:34], r["ipcc_code"],
                                   r["adjustment_Mt_co2e"] or r["bracket_high_Mt"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
