"""Ammonia (2.B.1) and nitric acid (2.B.2) as NINE-YEAR series - the back-cast the boundary rule demands
before either can enter any aggregate.

AMMONIA. The user's Tier-1 method, year by year: A_NH3 = the ammonia embodied in NFDC's domestic
production by nitrogen stoichiometry (every ammoniacal product x its NH3 content; the PRIMARY activity
pathway), EF the Pakistan-calibrated 1.815 t CO2/t NH3 (forces the 2020-21 NFDC year to reproduce the
BTR's 3.02 Mt filing), recovery = urea produced x 44/60. The envelope is the METHOD envelope (EF
modern 1.694 .. total-energy 2.104), not a confidence interval. FY2023-24 reproduces the reference
component the engine prices since rc52 (3.243 Mt) - the test holds it. Activity: the NFDC
production series (data/nfdc/nfdc_production_by_product_series.csv), every year closing on its printed
total; two editions where both print a year, identical.

NITRIC ACID. No national HNO3 series is published. The activity here is DERIVED from the nitrate the
NFDC products carry: CAN (26 percent N; ammonium nitrate carries half its N as nitrate) and NP
(22 percent N nitrophosphate; nitrate share bracketed 0.4..0.6). HNO3 (100 percent) per tonne of
product = N share x nitrate fraction x 63.01/14.007. One plant-level datum is held for reconciliation
(Fatima Sadiqabad 563,701 t HNO3 in CY2022, data/activity/ippu/chemical_plant_activity.csv) - the
derived national figure must sit ABOVE it (Pakarab Multan also produces). EF: IPCC medium-pressure 7 kg
N2O/t (unabated) .. high-pressure 9; ABATED at the ACM0019 destruction the CDM monitoring verified
(the shipped pair 0.733/1.046 = 30 percent of unabated). Abatement operation after 2022 is not
documented, so every year is a PAIR (unabated, abated), never averaged. GWP AR5 N2O 265.

Ammonia is IN the reference since rc52 (this product is its nine-year audit trail and method envelope); nitric acid stays a configuration pair.

Reads:  data/nfdc/nfdc_production_by_product_series.csv, data/emission_factors.csv (ammonia_embodied),
        data/ippu_params.csv (ammonia_ef_*, urea_co2_recovery_factor, nitric_acid_ef_*),
        data/activity/ippu/chemical_plant_activity.csv (the one HNO3 plant datum)
Writes: outputs/pakemis_ammonia_nitric_series.csv
"""
import csv
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from pkinv.assets import asset_path

from pkinv.paths import DATA, OUTPUTS  # noqa: E402
from pkinv.sectors.ippu.data import IppuData  # noqa: E402

SERIES = asset_path(DATA, "nfdc", "nfdc_production_by_product_series.csv")
PLANTS = asset_path(DATA, "activity", "ippu", "chemical_plant_activity.csv")
OUT = asset_path(OUTPUTS, "pakemis_ammonia_nitric_series.csv")
PRODUCTS = ("Urea", "CAN", "NP", "DAP", "NPK", "SSP", "SOP")
YEARS = ["%d-%02d" % (y, (y + 1) % 100) for y in range(2015, 2025)]        # nine periods + FY2024-25 (extra, labelled)
GWP_N2O_AR5 = 265.0
M_HNO3_PER_N = 63.012 / 14.007
CAN_N, CAN_NITRATE = 0.26, 0.5                    # ammonium nitrate: half the N is nitrate
NP_N, NP_NITRATE_LOW, NP_NITRATE_HIGH = 0.22, 0.4, 0.6
ABATED_SHARE = 0.733 / 1.046                       # the shipped pair: ACM0019-verified destruction

FIELDS = ("fiscal_year", "in_reference_window", "category", "ipcc_code",
          "urea_kt", "can_kt", "np_kt", "dap_kt", "npk_kt", "activity_kt", "activity_unit", "activity_basis",
          "ef", "ef_unit", "gross_mt_co2e", "recovered_to_urea_mt", "central_mt_co2e",
          "envelope_low_mt", "envelope_high_mt", "envelope_kind", "abated_mt_co2e", "unabated_mt_co2e",
          "plant_check", "status", "note")
HEADER = """\
# AMMONIA (2.B.1) AND NITRIC ACID (2.B.2) AS NINE-YEAR SERIES - the back-cast that must exist before either enters any
# aggregate; ammonia entered the reference at rc52 (this is its audit trail), nitric acid stays a pair outside. Ammonia: NFDC production x NH3
# stoichiometry x the calibrated EF 1.815, minus urea x 44/60; envelope = METHOD envelope (EF 1.694..2.104), not a CI.
# Nitric acid: activity DERIVED from the nitrate CAN and NP carry (no national HNO3 series is published) - a PAIR per
# year, unabated (IPCC medium-pressure 7 kg N2O/t) and abated at the ACM0019-verified destruction; never averaged.
# FY2024-25 is carried as an extra, outside the nine-period window. scripts/build_ammonia_nitric_series.py
"""


def _rows(path):
    from pkinv.activity.store import read_rows as canonical_rows
    return canonical_rows(path, comments=True)


def production():
    """kt by (fiscal_year, product): the first row wins where two editions print a year (identical)."""
    out = {}
    for r in _rows(SERIES):
        k = (r["fiscal_year"], r["product"])
        if k not in out and r["production_000t"]:
            out[k] = float(r["production_000t"])
    return out


def build():
    data = IppuData()
    prod = production()
    ef_c, ef_lo, ef_hi = data.p("ammonia_ef_calibrated"), data.p("ammonia_ef_modern"), data.p("ammonia_ef_total_energy")
    rec = data.p("urea_co2_recovery_factor")
    n2o_mp, n2o_hp = data.p("nitric_acid_ef_medium_pressure"), data.p("nitric_acid_ef_high_pressure")
    plant = next((float(r["production_t"]) / 1000.0 for r in _rows(PLANTS)
                  if r["product"] == "Nitric acid" and r["production_t"]), None)
    out = []
    for fy in YEARS:
        kt = {p: prod.get((fy, p)) for p in PRODUCTS}
        if kt["Urea"] is None:
            continue
        in_window = "yes" if fy != "2024-25" else "no (extra year)"
        nh3 = sum((kt[p] or 0.0) * data.efv("ammonia_embodied", p) for p in PRODUCTS)
        gross = nh3 * ef_c / 1000.0
        recovered = kt["Urea"] * rec / 1000.0
        out.append({
            "fiscal_year": fy, "in_reference_window": in_window, "category": "Ammonia production", "ipcc_code": "2.B.1",
            "urea_kt": "%.3f" % kt["Urea"], "can_kt": "%.3f" % (kt["CAN"] or 0), "np_kt": "%.3f" % (kt["NP"] or 0),
            "dap_kt": "%.3f" % (kt["DAP"] or 0), "npk_kt": "%.3f" % (kt["NPK"] or 0),
            "activity_kt": "%.3f" % nh3, "activity_unit": "kt NH3",
            "activity_basis": "NFDC production x NH3 stoichiometry per product (data/emission_factors.csv ammonia_embodied)",
            "ef": "%.3f" % ef_c, "ef_unit": "t CO2/t NH3 (calibrated to the BTR 2020-21 filing)",
            "gross_mt_co2e": "%.5f" % gross, "recovered_to_urea_mt": "%.5f" % recovered,
            "central_mt_co2e": "%.5f" % (gross - recovered),
            "envelope_low_mt": "%.5f" % (nh3 * ef_lo / 1000.0 - recovered),
            "envelope_high_mt": "%.5f" % (nh3 * ef_hi / 1000.0 - recovered),
            "envelope_kind": "method envelope (EF modern .. total-energy), not a confidence interval",
            "abated_mt_co2e": "", "unabated_mt_co2e": "", "plant_check": "",
            "status": "reference component since rc52 (audit trail; the engine prices the same activity, factor and recovery)",
            "note": "recovered CO2 re-emerges at urea application (3.H); the gas ledger already deducts the feedstock share",
        })
        # nitric acid: derived activity, a pair per year
        hno3_low = ((kt["CAN"] or 0) * CAN_N * CAN_NITRATE + (kt["NP"] or 0) * NP_N * NP_NITRATE_LOW) * M_HNO3_PER_N
        hno3_high = ((kt["CAN"] or 0) * CAN_N * CAN_NITRATE + (kt["NP"] or 0) * NP_N * NP_NITRATE_HIGH) * M_HNO3_PER_N
        hno3_c = (hno3_low + hno3_high) / 2.0
        unabated_c = hno3_c * n2o_mp * GWP_N2O_AR5 / 1e6          # kt x kg/t = t N2O -> x GWP / 1e6 = Mt
        unabated_hi = hno3_high * n2o_hp * GWP_N2O_AR5 / 1e6
        unabated_lo = hno3_low * n2o_mp * GWP_N2O_AR5 / 1e6
        abated_c = unabated_c * ABATED_SHARE
        check = ""
        if plant is not None and fy == "2021-22":
            check = ("derived national HNO3 %.0f..%.0f kt vs Fatima Sadiqabad CY2022 %.0f kt (one of two producers): %s"
                     % (hno3_low, hno3_high, plant, "consistent (national above the plant)" if hno3_low >= plant else "INCONSISTENT"))
        out.append({
            "fiscal_year": fy, "in_reference_window": in_window, "category": "Nitric acid production", "ipcc_code": "2.B.2",
            "urea_kt": "", "can_kt": "%.3f" % (kt["CAN"] or 0), "np_kt": "%.3f" % (kt["NP"] or 0), "dap_kt": "", "npk_kt": "",
            "activity_kt": "%.3f" % hno3_c, "activity_unit": "kt HNO3 (100 percent), DERIVED",
            "activity_basis": ("nitrate carried by CAN (0.26 N x 0.5 nitrate) and NP (0.22 N x 0.4..0.6 nitrate) x 63.01/14.007; "
                               "no national HNO3 series is published"),
            "ef": "%.0f..%.0f" % (n2o_mp, n2o_hp), "ef_unit": "kg N2O/t HNO3 (IPCC medium..high pressure); GWP AR5 265",
            "gross_mt_co2e": "", "recovered_to_urea_mt": "", "central_mt_co2e": "",
            "envelope_low_mt": "%.5f" % (unabated_lo * ABATED_SHARE), "envelope_high_mt": "%.5f" % unabated_hi,
            "envelope_kind": "pair band: abated (low activity, medium pressure) .. unabated (high activity, high pressure)",
            "abated_mt_co2e": "%.5f" % abated_c, "unabated_mt_co2e": "%.5f" % unabated_c,
            "plant_check": check,
            "status": "pair series (configuration lane; outside the reference); no central",
            "note": ("abatement operation after the last ACM0019 verification (2022) is undocumented - the pair is the "
                     "honest statement; the activity is a stoichiometric derivation, not a production statistic"),
        })
    return out


def main():
    rows = build()
    with open(OUT, "w", newline="", encoding="utf-8") as h:
        h.write(HEADER)
        w = csv.DictWriter(h, fieldnames=list(FIELDS), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print("ammonia + nitric series -> %s (%d rows)" % (os.path.relpath(OUT), len(rows)))
    for r in rows:
        if r["ipcc_code"] == "2.B.1":
            print("  %s NH3 %8s kt  central %7s Mt  [%s..%s]" % (r["fiscal_year"], r["activity_kt"], r["central_mt_co2e"],
                                                                  r["envelope_low_mt"], r["envelope_high_mt"]))
        else:
            print("  %s HNO3 %7s kt  abated %7s / unabated %7s Mt  %s" % (r["fiscal_year"], r["activity_kt"],
                                                                        r["abated_mt_co2e"], r["unabated_mt_co2e"], r["plant_check"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
