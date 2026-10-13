"""The gas-flow crosswalk: what each delivered stream is, which factor may ride it, and where
its carbon is booked. One row per stream and fiscal year.

WHY THIS EXISTS (rc67). Through rc66 the post-meter leak factor was charged on the whole
fertiliser gas class, of which five sixths is chemical feedstock that is reformed and never
burned. The account that should have shown this was the gas ledger, and it did show it, as a
sentence on one row. What it did not do was classify every stream by the KIND of flow it is,
and that is the question the membership turns on: a factor defined on "gas consumed" in
combustion equipment has a boundary, and each stream is inside it or not.

THE SIX FLOW KINDS (closed vocabulary):
  chemical_feedstock             delivered and reformed, not burned (fertiliser feed gas)
  process_fuel                   burned inside a process plant whose carbon a process
                                 category books on production (fertiliser fuel gas)
  other_combustion               burned in equipment a combustion category books
  loss_before_metering           gas that never reaches a customer meter: the utilities'
                                 transmission and distribution losses (unaccounted-for gas)
  loss_after_metering            leakage downstream of the customer meter. A MEMO row: the
                                 gas is inside the streams above, not beside them
  leakage_represented_elsewhere  a stream whose leakage another segment prices on another
                                 activity (pipeline length, appliance count), or does not
                                 price and says so

WHAT EACH ROW CARRIES. The volume and where it was printed; whether the stream is in the
non-residential post-meter base; the factor and the activity its source defines it on; the
category that books the stream's carbon and on what basis; and, where the booking is not on
delivered gas or is absent, a status word saying which.

THE CHECKS ARE IN THE BUILD. For every year: the additive rows sum to the regulator's printed
consumption; feed and process fuel sum to the fertiliser class; the streams flagged as in the
base, less the feed, equal the activity the fugitives engine actually charges. Any failure
raises instead of writing.

THE CARBON SIDE IS REPORTED, NOT CLOSED. For fertiliser gas the row carries the carbon the
delivered volume could hold beside the gross process carbon 2.B.1 books on ammonia production.
The potential is a band on the heating value the industry sector publishes for utility gas;
most fertiliser gas arrives on dedicated lines from the fields, no held document prints its
heating value, and the band may not bound it. The two figures are not expected to be equal
either way: the same gas also fires nitric acid, phosphate and utility plant. The difference
is published as open and assigned to no cause.

COMPARATOR ONLY. Nothing here enters a total, a factor or an allocation.

Usage:  python3 -m pkinv.report.gas_flow_crosswalk
Writes: outputs/pakemis_gas_flow_crosswalk.csv
"""
import csv
import os

from pkinv.assets import asset_path
from pkinv.core.io import write_table
from pkinv.core.units import mmcfd_to_TJ
from pkinv.paths import DATA, OUTPUTS

OUT = os.path.join(OUTPUTS, "pakemis_gas_flow_crosswalk.csv")
CLASS_SERIES = os.path.join(OUTPUTS, "ogra_gas_class_series.csv")
AMMONIA_SERIES = os.path.join(OUTPUTS, "pakemis_ammonia_nitric_series.csv")
RESTATED = asset_path(DATA, "activity", "fugitives", "ogra_sector_gas_2021_2023.csv")
HISTORY = asset_path(DATA, "activity", "fugitives", "infrastructure_history_2015_21.csv")
CONTROLS = asset_path(DATA, "activity", "fugitives", "gas_flow_controls_2021_24.csv")
PERIODS = asset_path(DATA, "periods.csv")

FLOW_KINDS = ("chemical_feedstock", "process_fuel", "other_combustion",
              "loss_before_metering", "loss_after_metering",
              "leakage_represented_elsewhere")
CARBON_STATUSES = ("booked_on_delivered_gas_net_of_leak", "booked_on_delivered_gas",
                   "booked_on_production", "booked_on_consumed_reported_net_of_leak",
                   "booked_inside_another_control", "not_estimated_declared",
                   "not_established", "not_applicable_no_carbon_claim")
HHV_BAND_BTU = (900.0, 1000.0)       # the industry sector's published band
GROSS_TO_NET = 0.90
GAS_CO2_T_PER_TJ = 56.1
ROUNDING_MMCFD = 1.5                 # printed integers, eight rows to a subtotal

# class -> (stream label, flow kind, in the non-residential post-meter base,
#           carbon category, carbon status, carbon basis, leak treatment)
POST_METER = "post-meter non-residential factor"
STREAMS = {
    "residential": (
        "Residential", "other_combustion", False, "1.A.4.b", "booked_on_delivered_gas",
        "utility returns of gas sold to households",
        "leakage_represented_elsewhere: 1.B.2.b.vi post-meter appliances, priced per "
        "domestic connection and not on this volume"),
    "commercial": (
        "Commercial", "other_combustion", True, "1.A.4.a", "not_estimated_declared",
        "burned in commercial buildings the inventory does not estimate (the declared "
        "commercial-buildings gap); the leak is priced and the combustion is not",
        POST_METER),
    "general_industry": (
        "General industry", "other_combustion", True, "1.A.2",
        "booked_on_delivered_gas_net_of_leak",
        "the regulator's sector row, net of the post-meter leaked share", POST_METER),
    "fertilizer_feedstock": (
        "Fertiliser: feedstock", "chemical_feedstock", False, "2.B.1 (and 3.C.3 for the "
        "carbon recovered into urea)", "booked_on_production",
        "ammonia production times a factor on the plant's total gas requirement; the "
        "carbon recovered into urea is deducted there and booked where the urea is applied",
        "none: reformed, not burned, so the factor's activity definition does not hold; "
        "withheld from the base since rc67"),
    "fertilizer_process_fuel": (
        "Fertiliser: process fuel", "process_fuel", True, "2.B.1", "booked_on_production",
        "inside the same total-gas-requirement factor as the feed; no delivered-gas "
        "combustion row exists, so there is nothing to net the leak from", POST_METER),
    "cement": (
        "Cement", "other_combustion", True, "1.A.2",
        "booked_on_delivered_gas_net_of_leak",
        "the regulator's sector row, net of the post-meter leaked share", POST_METER),
    "captive_power": (
        "Captive power", "other_combustion", True, "1.A.2 (captive generation)",
        "booked_on_delivered_gas_net_of_leak",
        "the regulator's captive register, net of the post-meter leaked share",
        POST_METER),
    "power": (
        "Power", "other_combustion", True, "1.A.1.a",
        "booked_on_consumed_reported_net_of_leak",
        "NEPRA's consumed energy, a different publication's meter for the same gas, net "
        "of the post-meter leaked share. The K-Electric system's gas is inside this "
        "delivered row and inside the leak base while its combustion is outside the "
        "reference boundary (priced as the coverage alternative power_with_kelectric)",
        POST_METER),
    "transport_cng": (
        "Transport (CNG)", "other_combustion", False, "1.A.3.b",
        "booked_inside_another_control",
        "burned inside the road module's own fuel control",
        "leakage_represented_elsewhere: not estimated, declared; a vehicle-count factor "
        "would be needed and none is applied"),
    "industry_independent_unclassified": (
        "Industry on independent systems (class not printed)", "other_combustion", True,
        "not established", "not_established",
        "printed under bare Industry on the independent systems in one edition only",
        POST_METER),
    "own_use_and_other": (
        "Own use and other", "other_combustion", False, "mixed", "not_established",
        "the regulator's residual class (company own use, inter-company, swaps); "
        "delivered mass with no combustion claim resolved to one module",
        "none applied"),
    "td_losses": (
        "Transmission and distribution losses", "loss_before_metering", False,
        "1.B.2.b (transmission, distribution)", "not_applicable_no_carbon_claim",
        "unaccounted-for gas is a statistical quantity (theft, meter error, leakage "
        "together) and is never booked as methane",
        "leakage_represented_elsewhere: the network segments of 1.B.2.b, priced on "
        "pipeline length"),
}
IN_BASE = tuple(k for k, v in STREAMS.items() if v[2])
SERIES_CLASSES = ("residential", "commercial", "general_industry", "fertilizer", "cement",
                  "captive_power", "power", "transport_cng")

FIELDS = ("period_id", "stream", "flow_kind", "additive_to_delivered", "mmcfd",
          "million_m3", "volume_status", "volume_source", "in_post_meter_base",
          "post_meter_factor_id", "post_meter_factor_activity_definition",
          "post_meter_ch4_kt", "leak_treatment", "carbon_category", "carbon_status",
          "carbon_basis", "gas_carbon_potential_Mt_CO2_low",
          "gas_carbon_potential_Mt_CO2_high", "carbon_booked_Mt_CO2", "note")


def _rows(path):
    with open(path, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(line for line in handle if not line.startswith("#")))


def _fugitives():
    # imported at call time: the report layer loads no sector module on import
    from pkinv.core import registry
    return registry.get("fugitives")


def class_volumes():
    """{fiscal_end_year: {class: (mmcfd, status, source)}} from each year's own print."""
    out = {}
    for r in _rows(CLASS_SERIES):
        if r["class_comparable"] != "yes" or r["gas_class"] not in SERIES_CLASSES:
            continue
        year = int(r["period_id"][2:6]) + 1
        out.setdefault(year, {})[r["gas_class"]] = (
            float(r["mmcfd_total"]), "verified",
            "OGRA sector-wise gas table, %s" % os.path.basename(r["edition_source"]))
    for r in _rows(RESTATED):
        out.setdefault(int(r["fiscal_year"]), {})[r["gas_class"]] = (
            float(r["total_mmcfd"]), r["status"], r["source"])
    return out


def controls():
    """{fiscal_end_year: (categorized consumption, unaccounted-for gas)} in MMCFD."""
    out = {}
    for path in (HISTORY, CONTROLS):
        for r in _rows(path):
            out[int(r["fiscal_year"])] = (float(r["categorized_consumption_mmcfd"]),
                                          float(r["ufg_mmcfd"]))
    return out


def _potential(mmcfd):
    return tuple(mmcfd_to_TJ(mmcfd, hhv, GROSS_TO_NET) * GAS_CO2_T_PER_TJ / 1e6
                 for hhv in HHV_BAND_BTU)


def build():
    fugitives = _fugitives()
    data = fugitives.load_data()
    factor_id = "post_meter_industrial_ch4"
    factor = fugitives.post_meter_factor(factor_id)
    definition = ("IPCC 2019 Refinement Table 4.2.4k: t CH4 per million m3 of "
                  "non-residential and commercial gas CONSUMED")
    leak_share = fugitives.whole_gas_leak_share()
    per_mmcfd = 365.0 * fugitives.post_meter_param("mcf_to_e6m3")
    volumes, control = class_volumes(), controls()
    ammonia = {r["fiscal_year"]: float(r["gross_mt_co2e"]) for r in _rows(AMMONIA_SERIES)
               if r["category"] == "Ammonia production" and r["gross_mt_co2e"]}
    periods = [(r["period_id"], int(r["fiscal_end_year"])) for r in _rows(PERIODS)]

    rows, problems = [], []
    for period_id, year in sorted(periods):
        held = dict(volumes.get(year, {}))
        if "fertilizer" not in held:
            problems.append("%s: no fertiliser class" % period_id)
            continue
        feed = fugitives.fertilizer_feed_fraction(data, year)
        fert_mmcfd, fert_status, fert_source = held.pop("fertilizer")
        engine_class = data.fertilizer_gas_class(year)["mmcfd"]
        if abs(engine_class - fert_mmcfd) > 1e-9:
            problems.append("%s: the engine reads fertiliser gas as %.2f MMCFD and the "
                            "class table as %.2f" % (period_id, engine_class, fert_mmcfd))
        split_note = ("%.2f%% of the printed fertiliser class (%.0f MMCFD); feed fraction "
                      "%s from FY%s, %s")
        held["fertilizer_feedstock"] = (
            fert_mmcfd * feed["value"], fert_status, fert_source)
        held["fertilizer_process_fuel"] = (
            fert_mmcfd * (1.0 - feed["value"]), fert_status, fert_source)
        categorized, ufg = control[year]
        printed = sum(v[0] for k, v in held.items() if k != "td_losses")
        if "own_use_and_other" not in held:
            residual = categorized - printed
            if residual < -ROUNDING_MMCFD:
                problems.append("%s: the classes sum to %.1f MMCFD, above the printed "
                                "consumption %.1f" % (period_id, printed, categorized))
            if residual > ROUNDING_MMCFD:
                held["own_use_and_other"] = (
                    residual, "derived",
                    "printed consumption less the sum of the classes")
        held.setdefault("td_losses", (ufg, "verified",
                                      "OGRA sector-wise gas table, T&D losses row"))

        base_mmcfd = sum(v[0] for k, v in held.items() if k in IN_BASE)
        engine_base = data.activity("post_meter_nonresidential", year=year)["value"] * (
            1.0 - data.post_meter_feedstock_share(year, scope="feed"))
        if abs(base_mmcfd * per_mmcfd - engine_base) > 1e-3 * engine_base:
            problems.append("%s: streams in the base sum to %.1f million m3, the engine "
                            "charges %.1f" % (period_id, base_mmcfd * per_mmcfd, engine_base))

        fiscal = "%d-%02d" % (year - 1, year % 100)
        for key in STREAMS:
            if key not in held:
                continue
            (label, kind, in_base, category, status, basis, leak) = STREAMS[key]
            mmcfd, volume_status, source = held[key]
            row = {
                "period_id": period_id, "stream": label, "flow_kind": kind,
                "additive_to_delivered": "yes", "mmcfd": "%.2f" % mmcfd,
                "million_m3": "%.1f" % (mmcfd * per_mmcfd),
                "volume_status": volume_status, "volume_source": source,
                "in_post_meter_base": "yes" if in_base else "no",
                "post_meter_factor_id": factor_id if in_base else "",
                "post_meter_factor_activity_definition": definition if in_base else "",
                "post_meter_ch4_kt": ("%.3f" % (mmcfd * per_mmcfd * factor / 1000.0)
                                      if in_base else ""),
                "leak_treatment": leak, "carbon_category": category,
                "carbon_status": status, "carbon_basis": basis,
                "gas_carbon_potential_Mt_CO2_low": "",
                "gas_carbon_potential_Mt_CO2_high": "",
                "carbon_booked_Mt_CO2": "", "note": ""}
            if key.startswith("fertilizer_"):
                part = feed["value"] if key.endswith("feedstock") else 1.0 - feed["value"]
                row["note"] = split_note % (100.0 * part, fert_mmcfd, feed["basis"],
                                            feed["observed_year"], feed["source"])
            if key == "td_losses":
                row["additive_to_delivered"] = "no"
                row["note"] = ("beside the delivered streams, not among them: supply = "
                               "delivered + this row")
            rows.append(row)

        # the fertiliser class whole, as a memo row: the only place the gas-carbon
        # potential can be set beside what 2.B.1 books, because 2.B.1 books feed and
        # process fuel in one production-based number
        low, high = _potential(fert_mmcfd)
        booked = ammonia.get(fiscal)
        rows.append({
            "period_id": period_id, "stream": "MEMO: fertiliser class (feed + process fuel)",
            "flow_kind": "chemical_feedstock", "additive_to_delivered": "no",
            "mmcfd": "%.2f" % fert_mmcfd, "million_m3": "%.1f" % (fert_mmcfd * per_mmcfd),
            "volume_status": fert_status, "volume_source": fert_source,
            "in_post_meter_base": "partly", "post_meter_factor_id": "",
            "post_meter_factor_activity_definition": "", "post_meter_ch4_kt": "",
            "leak_treatment": "see the two fertiliser rows",
            "carbon_category": "2.B.1", "carbon_status": "booked_on_production",
            "carbon_basis": "gross process CO2 on ammonia production, before the "
                            "deduction for carbon recovered into urea",
            "gas_carbon_potential_Mt_CO2_low": "%.3f" % low,
            "gas_carbon_potential_Mt_CO2_high": "%.3f" % high,
            "carbon_booked_Mt_CO2": "" if booked is None else "%.3f" % booked,
            "note": ("OPEN DIFFERENCE, not a closure. The potential is the delivered "
                     "volume at %.0f to %.0f Btu/scf gross, net basis %.2f, %.1f t CO2/TJ: "
                     "the band published for utility gas, which may not bound gas drawn "
                     "on dedicated field lines, whose heating value no held document "
                     "prints. The booked figure is on ammonia alone; the same gas also "
                     "fires nitric acid, phosphate and utility plant, so the two are not "
                     "expected to be equal and the gap is assigned to no cause"
                     % (HHV_BAND_BTU[0], HHV_BAND_BTU[1], GROSS_TO_NET, GAS_CO2_T_PER_TJ))})
        base_mm3 = base_mmcfd * per_mmcfd
        rows.append({
            "period_id": period_id, "stream": "MEMO: post-meter leak, non-residential",
            "flow_kind": "loss_after_metering", "additive_to_delivered": "no",
            "mmcfd": "%.2f" % (base_mmcfd * leak_share),
            "million_m3": "%.1f" % (base_mm3 * leak_share), "volume_status": "derived",
            "volume_source": "the base streams above times the whole-gas leaked share "
                             "the factor implies (%.4f%%)" % (100.0 * leak_share),
            "in_post_meter_base": "", "post_meter_factor_id": factor_id,
            "post_meter_factor_activity_definition": definition,
            "post_meter_ch4_kt": "%.3f" % (base_mm3 * factor / 1000.0),
            "leak_treatment": POST_METER, "carbon_category": "1.B.2.b.vi",
            "carbon_status": "not_applicable_no_carbon_claim",
            "carbon_basis": "leaked gas is booked as fugitive methane and is not burned; "
                            "the delivered-gas combustion rows are net of it",
            "gas_carbon_potential_Mt_CO2_low": "", "gas_carbon_potential_Mt_CO2_high": "",
            "carbon_booked_Mt_CO2": "",
            "note": "inside the base streams above, not beside them"})
    if problems:
        raise SystemExit("the gas-flow crosswalk does not close:\n  " + "\n  ".join(problems))
    for row in rows:
        assert row["flow_kind"] in FLOW_KINDS and row["carbon_status"] in CARBON_STATUSES, row
    return rows


def main():
    rows = build()
    write_table(OUT, FIELDS, rows, banner=(
        "# Every delivered gas stream by fiscal year: the kind of flow it is, whether the",
        "# post-meter leak factor rides it, and which category books its carbon and on what",
        "# basis. Fertiliser gas is carried as feedstock (outside the leak base since rc67)",
        "# and process fuel (inside). MEMO rows are not additive. The fertiliser carbon",
        "# comparison is an open difference, not a closure.",
        "# pkinv.report.gas_flow_crosswalk. COMPARATOR ONLY.",))
    reference = [r for r in rows if r["period_id"] == "FY2023-24"]
    feed = next(r for r in reference if r["stream"] == "Fertiliser: feedstock")
    leak = next(r for r in reference if r["stream"].startswith("MEMO: post-meter"))
    print("gas-flow crosswalk: %d rows, %d periods; FY2023-24 feedstock %s million m3 "
          "outside the base, base leak %s kt CH4"
          % (len(rows), len({r["period_id"] for r in rows}), feed["million_m3"],
             leak["post_meter_ch4_kt"]))


if __name__ == "__main__":
    main()
