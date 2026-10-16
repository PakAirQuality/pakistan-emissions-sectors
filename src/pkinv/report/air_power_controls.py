"""Public plant design evidence and conditional SO2 cases, outside central totals.

Licence applications establish proposed equipment and design performance. They
do not establish commissioning, continuous operation, measured removal or fuel
assays. The separate cases apply the stated design efficiency once to AP-42's
uncontrolled factor and the same recorded station fuel mass. Neither endpoint
is a mathematical bound or a parameter confidence interval.
"""
import hashlib
import os

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows
from pkinv.core.io import write_table
from pkinv.core.reporting_window import CORE_FY_STARTS
from pkinv.paths import ROOT, DATA, OUTPUTS

EVIDENCE = asset_path(OUTPUTS, "pakemis_air_power_control_evidence.csv")
CASES = asset_path(OUTPUTS, "pakemis_air_power_design_cases.csv")
BASE = "data/raw/nepra/air_controls/"
SOURCES = {
    "Port Qasim Electric Power": ("port_qasim_generation_application_2014.pdf",
        "59f9820a214179ae65a55dffbf9ccf4ed865a0d5cd4f05771a14eeb986b8a4cf", 69),
    "China Power Hub": ("cihc_pak_generation_application_2017.pdf",
        "ab7823c32d42a6dc1be678a73accb3be4d14deab26f4b76b5d256051181b04db", 204),
}
EVIDENCE_FIELDS = ("plant", "fuel", "pollutant_or_property", "device", "evidence_class",
    "design_removal_fraction", "design_limit", "operation_evidence", "admission_status",
    "source_file", "source_sha256", "source_pdf_page", "interpretation",
    "installation_evidence", "assumed_removal_in_screening")
# rc68 air review (criterion 4): the four things a control claim can rest on are kept in four
# fields. INSTALLED equipment (installation_evidence), DESIGN efficiency (design_removal_fraction
# / design_limit, from the application), ASSUMED efficiency (assumed_removal_in_screening: what
# the fleet-wide controlled screening case credits, which is a technology transfer and not this
# plant's design) and DEMONSTRATED operation (operation_evidence). A licence application
# proposes a device; it does not show that one was installed, let alone run.
INSTALLATION = "not_established: licence application proposes the device; no commissioning or inspection record held"
ASSUMED_IN_SCREENING = {
    "SO2": "controlled_case credits wet lime/limestone FGD residual 0.05-0.20 (AP-42 1.1-1/1.7-2 range) on all coal; uncontrolled case credits none; neither is this plant's design or demonstrated removal",
    "bulk fly ash": "controlled_case credits AP-42 1.1-6 ESP-column PM factors (about 99.2 pct collection) on all coal; uncontrolled case credits none",
    "NOx": "controlled_case credits AP-42 1.1-3 low-NOx-burner row (11 lb/ton) on bituminous coal; uncontrolled case credits none",
    "monitoring": "not applicable; no removal is assumed from monitoring",
}
CASE_FIELDS = ("period_id", "plant", "pollutant", "fuel_mass_t", "activity_source",
    "sulfur_proxy_pct", "sulfur_low_pct", "sulfur_high_pct", "uncontrolled_case_Gg",
    "design_removal_fraction", "design_case_Gg", "design_case_low_sulfur_Gg",
    "design_case_high_sulfur_Gg", "case_kind", "coverage_scope", "source_pdf_page",
    "limitations")


def evidence_rows():
    for filename, digest, _page in SOURCES.values():
        with open(os.path.join(ROOT, BASE, filename), "rb") as handle:
            actual = hashlib.sha256(handle.read()).hexdigest()
        if actual != digest:
            raise ValueError("plant control source changed: " + filename)
    entries = (
        ("Port Qasim Electric Power", "SO2", "limestone-gypsum wet FGD", .92, "",
         "minimum proposed design efficiency; not demonstrated removal"),
        ("Port Qasim Electric Power", "bulk fly ash", "five-electric-field ESP", .997, "",
         "bulk ash design removal cannot be transferred to PM2.5; additional FGD dust removal assumed in application"),
        ("Port Qasim Electric Power", "NOx", "low-NOx burner and staged air", "", "450 mg/Nm3, dry standard gas, 6% O2",
         "design concentration is not an annual emission factor or measured annual release"),
        ("Port Qasim Electric Power", "monitoring", "continuous online monitoring proposed", "", "",
         "application states planned monitoring; no time series or demonstrated operation supplied"),
        ("China Power Hub", "SO2", "seawater FGD", .93, "",
         "minimum proposed design efficiency at BMCR; final operation and availability not demonstrated"),
    )
    rows = []
    for plant, pol, device, removal, limit, interpretation in entries:
        filename, digest, page = SOURCES[plant]
        rows.append(dict(plant=plant, fuel="imported coal", pollutant_or_property=pol,
            device=device, evidence_class="licence_application_design", design_removal_fraction=removal,
            design_limit=limit, operation_evidence="not_demonstrated_by_this_document",
            admission_status="scenario_only", source_file=BASE + filename,
            source_sha256=digest, source_pdf_page=page, interpretation=interpretation,
            installation_evidence=INSTALLATION, assumed_removal_in_screening=ASSUMED_IN_SCREENING[pol]))
    return rows


def design_cases(evidence=None, fuel_rows=None):
    from pkinv.sectors.power.air_pollutants import BITUMINOUS_LB_PER_TON
    from pkinv.sectors.power.data import PowerData
    evidence = evidence_rows() if evidence is None else evidence
    removals = {r["plant"]: r for r in evidence if r["pollutant_or_property"] == "SO2"}
    fuel_rows = (read_rows(asset_path(DATA, "activity/power/plant_fuel_ledger.csv"))
                 if fuel_rows is None else fuel_rows)
    sulfur_low, sulfur_high = PowerData().fuel_quality("Coal", "sulfur_pct")
    sulfur = (sulfur_low * sulfur_high) ** .5
    # AP-42 lb/short ton -> kg/metric tonne; NCV cancels on physical mass.
    kg_per_t_per_pct = BITUMINOUS_LB_PER_TON["SO2"][0] * .45359237 / .90718474
    rows, seen = [], set()
    for source in fuel_rows:
        plant, year = source["plant"], int(source["fiscal_year"])
        if plant not in removals or source["fuel"] != "Coal" or year not in CORE_FY_STARTS:
            continue
        key = (plant, year)
        if key in seen:
            raise ValueError("duplicate station coal consumption: %r" % (key,))
        seen.add(key)
        if source["quantity_unit"] != "000 t" or source["fuel_origin"] != "imported":
            raise ValueError("unsupported selected-station fuel basis: %r" % source)
        tonnes = float(source["quantity"]) * 1000
        if tonnes < 0:
            raise ValueError("negative coal consumption")
        removal = float(removals[plant]["design_removal_fraction"])
        uncontrolled = tonnes * kg_per_t_per_pct * sulfur / 1e6
        rows.append(dict(period_id="FY%d-%02d" % (year, (year + 1) % 100), plant=plant,
            pollutant="SO2", fuel_mass_t=tonnes, activity_source=source["source_table"],
            sulfur_proxy_pct=sulfur, sulfur_low_pct=sulfur_low, sulfur_high_pct=sulfur_high,
            uncontrolled_case_Gg=uncontrolled, design_removal_fraction=removal,
            design_case_Gg=uncontrolled * (1 - removal),
            design_case_low_sulfur_Gg=tonnes * kg_per_t_per_pct * sulfur_low * (1 - removal) / 1e6,
            design_case_high_sulfur_Gg=tonnes * kg_per_t_per_pct * sulfur_high * (1 - removal) / 1e6,
            case_kind="plant_design_and_sulfur_sensitivity_no_probability",
            coverage_scope="two_selected_coal_plants_only_not_in_central_panel",
            source_pdf_page=removals[plant]["source_pdf_page"],
            limitations="Imported-coal assay absent: existing Thar range retained as explicit proxy, not observed imported composition. Design removal credited for all annual fuel only as a scenario; control operation, bypass and availability unobserved. AP-42 typical uncontrolled rate, not a maximum; sulfur endpoints are not percentiles."))
    return sorted(rows, key=lambda r: (r["period_id"], r["plant"]))


def main():
    evidence = evidence_rows()
    cases = design_cases(evidence)
    write_table(EVIDENCE, EVIDENCE_FIELDS, evidence)
    write_table(CASES, CASE_FIELDS, cases)
    print("plant control evidence: %d design records; %d separate coal SO2 cases" % (len(evidence), len(cases)))


if __name__ == "__main__":
    main()
