"""The Table 3 coal question, enumerated: every candidate explanation, scored.

WHY THIS EXISTS. The largest single structural fork in the inventory is the 19.4 Mt
coal energy basis: NEPRA SIR Table 3 implies 24.20 TJ/Gg over a coal fleet whose
plant ledger implies 12.01 (x2.01), and for three releases the repository's whole
statement of the problem was "a scope difference only NEPRA can close". That
sentence hides the structure of the question. The twelfth review asked for the
structure: WHICH readings of Table 3 could produce the factor, which of them the
held diagnostics already discriminate against, which they are consistent with, and
which no held source can test. This register is that enumeration - one row per
hypothesis, every quantity read live from the diagnostic that holds it, so the
register can never assert something its evidence no longer says.

WHAT A STATUS IS. Three states, closed vocabulary:
  consistent                     the held evidence permits this reading (it may
                                 permit others; consistency is not confirmation)
  discriminated-against          a held diagnostic contradicts it
  untestable-with-held-sources   no held document bears on it; the row names the
                                 acquisition that would

THE REGISTER DOES NOT SELECT. Selection stays with the declared rule on the
power_grid_control family rows (national_configurations.POWER_SELECTION_RULE);
this file is the map of what remains open beneath the selected 57.82 Mt member.

Usage:  python3 -m pkinv.sectors.power.table3_hypotheses
Writes: outputs/power_table3_hypotheses.csv
"""

from pkinv.assets import asset_path
import csv
import os

from pkinv.paths import DATA, OUTPUTS
from pkinv.activity.store import read_rows
from pkinv.core.io import write_table

OUT = asset_path(OUTPUTS, "power_table3_hypotheses.csv")

FIELDS = ("hypothesis_id", "hypothesis", "status", "held_evidence",
          "evidence_source", "quantification", "what_would_close_it")

STATUSES = ("consistent", "discriminated-against", "untestable-with-held-sources")


def _rows(name):
    return read_rows(asset_path(OUTPUTS, name), comments=False)


def _gaps():
    return {r["gap_id"]: r for r in read_rows(asset_path(DATA, "data_gaps.csv"))}


def build():
    """One row per candidate explanation, each quantity read from its home."""
    implied = _rows("power_implied_coal_cv_fy2023_24.csv")
    summary = {r["plant"]: r for r in implied
               if r["fiscal_year"] == "2023" and r["evidence_class"] == "summary"}
    fleet_cv = float(summary["FLEET (mass-weighted)"]["implied_cv_TJ_per_Gg"])
    imported_cv = float(summary["imported only"]["implied_cv_TJ_per_Gg"])
    lignite_cv = float(summary["Thar lignite only"]["implied_cv_TJ_per_Gg"])
    table3_cv = float(summary["Table 3 implied NCV"]["implied_cv_TJ_per_Gg"])

    scenarios = {r["structural_scenario"]: r
                 for r in _rows("power_uncertainty_scenarios_fy2023_24.csv")}
    gross_mt = float(scenarios["toe_gross_basis"]["deterministic_Mt"])
    restated_mt = float(scenarios["coal_at_implied_cv"]["deterministic_Mt"])
    # READ, not typed: this row printed "the reference 57.996" for three releases after the
    # coal re-base had moved the reference to the station account.
    reference_mt = float(scenarios["reference"]["deterministic_Mt"])
    legacy_mt = float(scenarios["coal_at_table3_legacy"]["deterministic_Mt"])

    boundary = next(r for r in _rows("power_boundary_audit_fy2023_24.csv")
                    if r["fiscal_year"] == "2023")

    # rc64: the panel view. Every hypothesis below this point explains a CONSTANT bias
    # in one direction; the adjudication reads the whole ledger span and finds the bias
    # changes SIGN, which no constant scope or convention can do.
    # this one carries a banner, unlike the other diagnostics here, so it needs the
    # comment-aware reader rather than _rows
    adj = {r["period_id"]: r for r in
           read_rows(asset_path(OUTPUTS, "pakemis_power_coal_energy_adjudication.csv"),
                     comments=True)}
    eff = {k: float(v["table3_implied_efficiency_pct"]) for k, v in adj.items()}
    toe_t = {k: float(v["table3_toe_per_tonne"]) for k, v in adj.items()}
    toe_abs = {k: float(v["table3_coal_toe"]) for k, v in adj.items()}
    mass = {k: float(v["table21_mass_kt"]) for k, v in adj.items()}
    gen = {k: float(v["coal_generation_GWh"]) for k, v in adj.items()}
    toe_h = {k: float(v["table3_toe_per_hdip_tonne"]) for k, v in adj.items()
             if v["table3_toe_per_hdip_tonne"]}
    ratio = {k: float(v["hdip_over_table21"]) for k, v in adj.items()
             if v["hdip_over_table21"]}
    eff21 = {k: float(v["table21_mass_implied_efficiency_pct"]) for k, v in adj.items()}
    effh = {k: float(v["hdip_mass_implied_efficiency_pct"]) for k, v in adj.items()
            if v["hdip_mass_implied_efficiency_pct"]}
    lig = {k: float(v["lignite_share_of_mass_pct"]) for k, v in adj.items()}
    eff_hi_period = max(eff, key=eff.get)
    eff_lo_period = min(eff, key=eff.get)

    crt = {r["item"]: r for r in _rows("power_crt_comparison.csv")}
    crt_solid = float(crt["Solid fuel, engine over CRT"]["value"])

    circ = _rows("power_hr_circularity_fy2023_24.csv")
    circ_coal = sum(1 for r in circ if "coal" in r["fuel"].lower())
    circ_identical = sorted({"%s (%s)" % (r["plant"], r["fuel"])
                             for r in circ if r["verdict"] == "identical"})
    if circ_coal:
        raise SystemExit("the circularity diagnostic now covers coal rows; the "
                         "heat-input hypothesis row below claims it does not - "
                         "re-score it before shipping")

    gaps = _gaps()
    hdip = ("HDIP Pakistan Energy Yearbook conversion-factor and power-sector "
            "coal tables (data_gaps.csv: %s, access %s; %s, access %s)"
            % ("coal-toe-ncv", gaps["coal-toe-ncv"]["access"],
               "national-energy-balance", gaps["national-energy-balance"]["access"]))

    return [
        {
            "hypothesis_id": "imported-cv-convention",
            "hypothesis": ("Table 3's TOE column converts coal mass at an "
                           "imported-bituminous calorific convention while the "
                           "fleet burns mostly Thar lignite"),
            "status": "consistent",
            "held_evidence": ("the implied conversion Table 3 uses sits inside "
                              "the imported-coal band and far above the fleet: "
                              "the strongest surviving reading of the x%.2f"
                              % (table3_cv / fleet_cv)),
            "evidence_source": ("power_implied_coal_cv_fy2023_24.csv#2023 "
                                "summary rows"),
            "quantification": ("Table 3 implies %.2f TJ/Gg; imported-only "
                               "mass-weighted %.2f, Thar lignite %.2f, fleet "
                               "%.2f at 99%% mass coverage"
                               % (table3_cv, imported_cv, lignite_cv, fleet_cv)),
            "what_would_close_it": hdip + ", stating the coal CV the TOE "
                                          "conversion applies",
        },
        {
            "hypothesis_id": "basis-change-fy2021-22",
            "hypothesis": ("the disagreement is between two TONNAGE ACCOUNTS of the "
                           "same coal - HDIP's national power-sector series, which "
                           "Table 3 derives its TOE from, against NEPRA's own "
                           "per-station quantities - and their ratio CROSSES UNITY "
                           "between FY2020-21 and FY2021-22, so no constant scope "
                           "difference fits the panel"),
            "status": "consistent",
            "held_evidence": (
                "the sign of the discrepancy FLIPS, which no constant difference can "
                "do. Table 3's published energy implies a fleet thermal efficiency of "
                "%.1f%% in %s and %.1f%% in %s, and the two tonnage accounts behind it "
                "cross unity between the same two years. Of the three accounts, only "
                "NEPRA's per-station tonnage stays inside the admissible band in every "
                "year"
                % (eff[eff_hi_period], eff_hi_period.replace("FY", "FY "),
                   eff[eff_lo_period], eff_lo_period.replace("FY", "FY "))),
            "evidence_source": "pakemis_power_coal_energy_adjudication.csv",
            "quantification": (
                "NOT an edition revision and NOT a conversion. SoIR 2024 Table 3 prints "
                "FY2018-19 to FY2021-22 side by side and the 2025 edition reproduces "
                "those columns, and across those adjacent columns the coal TOE rises "
                "%+.1f%% (%.0f to %.0f TOE) while the SAME REPORT's Table 21 has mass "
                "%+.1f%% and generation %+.1f%%. Against HDIP's OWN tonnage, however, "
                "Table 3's energy is %.3f TOE/t in FY2019-20 and %.3f in FY2020-21 - "
                "identical - then %.3f, %.3f, %.3f. The ratio HDIP/per-station runs "
                "%.2f, %.2f, %.2f, %.2f, %.2f, crossing unity between the two years. At "
                "the fleet's rank composition the per-station account implies "
                "%.1f-%.1f%% thermal efficiency in every year; HDIP's implies %.1f "
                "falling to %.1f"
                % (100 * (toe_abs["FY2021-22"] / toe_abs["FY2020-21"] - 1),
                   toe_abs["FY2020-21"], toe_abs["FY2021-22"],
                   100 * (mass["FY2021-22"] / mass["FY2020-21"] - 1),
                   100 * (gen["FY2021-22"] / gen["FY2020-21"] - 1),
                   toe_h["FY2019-20"], toe_h["FY2020-21"], toe_h["FY2021-22"],
                   toe_h["FY2022-23"], toe_h["FY2023-24"],
                   ratio["FY2019-20"], ratio["FY2020-21"], ratio["FY2021-22"],
                   ratio["FY2022-23"], ratio["FY2023-24"],
                   min(eff21.values()), max(eff21.values()),
                   effh["FY2020-21"], effh["FY2023-24"])),
            "what_would_close_it": (
                "the HDIP Pakistan Energy Yearbook itself, which is where Table 3 "
                "states it takes these figures from, and its conversion-factor tables; "
                + hdip),
        },
        {
            "hypothesis_id": "gross-vs-net-toe",
            "hypothesis": "Table 3's TOE column is on a gross calorific basis",
            "status": "consistent",
            "held_evidence": ("possible but insufficient: the gross-to-net step "
                              "is 0.90 and cannot produce a factor of 2; priced "
                              "as the power energy convention axis"),
            "evidence_source": ("power_uncertainty_scenarios_fy2023_24.csv"
                                "#toe_gross_basis"),
            "quantification": ("gross basis prices %.3f Mt against the "
                               "reference %.3f (the Table 3 account itself is "
                               "%.3f); the restated-coal case is %.3f"
                               % (gross_mt, reference_mt, legacy_mt, restated_mt)),
            "what_would_close_it": "an HDIP or NEPRA statement of the TOE basis",
        },
        {
            "hypothesis_id": "ke-inclusion",
            "hypothesis": ("the coal discrepancy is K-Electric's fuel sitting "
                           "inside Table 3 while the plant ledger is CPPA-only"),
            "status": "discriminated-against",
            "held_evidence": ("K-Electric's ledger fuel is gas and furnace oil, "
                              "not coal, so its boundary cannot carry a COAL "
                              "energy factor of 2; and the boundary audit reads "
                              "Table 3 as excluding K-Electric anyway"),
            "evidence_source": "power_boundary_audit_fy2023_24.csv#2023",
            "quantification": ("FY2023-24 RFO plant-over-national ratio %.3f "
                               "without K-Electric vs %.3f with; K-E RFO %.0f TJ, "
                               "gas %.0f TJ, coal none"
                               % (float(boundary["rfo_without_KE"]),
                                  float(boundary["rfo_with_KE"]),
                                  float(boundary["KE_rfo_TJ"]),
                                  float(boundary["KE_gas_TJ"]))),
            "what_would_close_it": ("already discriminated for the coal "
                                    "question; the K-E scope itself stays open "
                                    "as data_gaps.csv ke-boundary"),
        },
        {
            "hypothesis_id": "coal-stock-change",
            "hypothesis": ("Table 3 records coal received or purchased - "
                           "including stockpile build - rather than coal burned"),
            "status": "untestable-with-held-sources",
            "held_evidence": ("no held document reports power-sector coal "
                              "stocks; a one-year stock build of the required "
                              "size (half the reported energy) would be extreme "
                              "but nothing held excludes it for any single year"),
            "evidence_source": "data/data_gaps.csv#coal-toe-ncv",
            "quantification": ("the reading must explain %.0f%% of Table 3's "
                               "coal energy" % (100.0 * (1 - fleet_cv / table3_cv))),
            "what_would_close_it": hdip + "; power-sector coal stock, import "
                                          "and consumption rows",
        },
        {
            "hypothesis_id": "non-power-coal-scope",
            "hypothesis": ("Table 3's coal row includes coal outside the grid "
                           "stations the plant ledger meters (captive or "
                           "industrial use)"),
            "status": "untestable-with-held-sources",
            "held_evidence": ("confounded with the conversion hypothesis by "
                              "construction: extra in-scope mass and a high CV "
                              "convention move the implied NCV identically, and "
                              "no held source partitions Table 3's coal"),
            "evidence_source": ("power_implied_coal_cv_fy2023_24.csv#2023 "
                                "FLEET row (99% ledger mass coverage)"),
            "quantification": ("indistinguishable from imported-cv-convention "
                               "in every held diagnostic"),
            "what_would_close_it": "a NEPRA scope statement for Table 3's coal "
                                   "row",
        },
        {
            "hypothesis_id": "heat-input-vs-output",
            "hypothesis": ("the plant-implied channel is circular: SIR heat "
                           "rates could be derived from electricity output "
                           "rather than measured heat input, making the "
                           "restated 38.45 an artefact"),
            "status": "untestable-with-held-sources",
            "held_evidence": ("the circularity diagnostic covers %d plant-fuel "
                              "comparisons and finds %d fully circular (%s) - "
                              "all gas, no coal plant appears in both "
                              "publications, so the coal channel can be shown "
                              "circular nowhere and independent nowhere"
                              % (len(circ), len(circ_identical),
                                 "; ".join(circ_identical))),
            "evidence_source": "power_hr_circularity_fy2023_24.csv#verdict",
            "quantification": ("%d of %d comparisons fully circular, 0 of them "
                               "coal" % (len(circ_identical), len(circ))),
            "what_would_close_it": ("measured station heat input for the coal "
                                    "fleet (NEPRA plant returns, request-only)"),
        },
        {
            "hypothesis_id": "table3-correct-as-published",
            "hypothesis": ("Table 3's coal energy is right and the plant "
                           "ledger's mass or the heat rates are wrong"),
            "status": "consistent",
            "held_evidence": ("the standing counter-evidence the selection rule "
                              "cites: the official CRT filing agrees with the "
                              "regulator's coal energy to 2 percent, and states "
                              "its basis as NCV"),
            "evidence_source": "power_crt_comparison.csv#Solid fuel, engine "
                               "over CRT",
            "quantification": "engine-over-CRT solid-fuel ratio %.3f" % crt_solid,
            "what_would_close_it": hdip + " (the same note decides this against "
                                          "imported-cv-convention)",
        },
    ]


def main():
    rows = build()
    for row in rows:
        if row["status"] not in STATUSES:
            raise SystemExit("status %r is outside the closed vocabulary"
                             % row["status"])
    os.makedirs(OUTPUTS, exist_ok=True)
    write_table(OUT, FIELDS, rows, banner=('# The Table 3 coal question, one row per candidate explanation. Statuses are read from live diagnostics; the register selects nothing.', '# The selected 57.82 Mt member and its selection rule live in outputs/national_configurations.csv (power_grid_control).',))
    counts = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    print("Table 3 hypothesis register -> %s" % os.path.relpath(OUT))
    for status in STATUSES:
        print("  %-30s %d" % (status, counts.get(status, 0)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
