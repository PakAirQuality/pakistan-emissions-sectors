"""INDUSTRIAL COAL SCENARIOS - what the reported industrial fall would have to be, if the
power-coal discrepancy belonged to industry (rc55 preparation).

WHERE THIS CAME FROM. An external conditional reconstruction (2026-09-14) computed a set of
alternatives for FY2023-24 industry and concluded that a near-flat BROADER industrial trend is
arithmetically reachable while a rising DIRECT-combustion trend is not. Most of its evidence was
already here: the eight-plant NEPRA coal table is in data/activity/power/plant_fuel_ledger.csv with
its fuel origin resolved, the 3.32 Mt power-coal gap is already published for five years in
outputs/industry_coal_reconciliation.csv, and the FY2015-16 supply-versus-use gap is already the
R = -203.8 kt row of the coal balance, already diagnosed as a brick vintage revision. What the
analysis genuinely added is this arithmetic, and it is rebuilt here on the repository's own
factors rather than copied.

WHAT EVERY ROW IS, AND IS NOT. A SCENARIO: what follows IF a stated quantity of coal were
industrial. Not a candidate central estimate, not a correction, not a confidence interval, and not
additive with anything. The deduction rows are sensitivity tests on an unresolved split, not
measured quantities. Nothing here enters a total; the reported series is untouched.

THE 3.32 Mt IS NOT REALLOCATED. It is a difference between two published tables - HDIP's power
allocation and NEPRA's metered plant burn - and it stays unallocated. Candidates the account cannot
yet separate: generators outside the eight-plant table, deliveries against combustion, stock
change, and error in either source. There is also a hard physical constraint: most of the swing is
Thar lignite, and Thar mine output cannot be moved to brick or cement kilns without evidence of
delivery, so the gross case is a bound on an accounting question, not a fuel account.

THE FACTOR IS THE ENGINE'S OWN CHAIN, not a ratio of rounded published totals. The external
analysis back-derived 2.460145 tCO2e per tonne by dividing rounded emissions by rounded tonnage;
this module builds 2.4586755 from data/emission_factors.csv and the AR5 GWPs the engine applies,
with coal CH4 as FOSSIL (GWP 30, not 28). The two agree to 0.06 percent, which is a finding in
itself - the external arithmetic reproduces the engine without having seen it - and the row carries
both so the difference is attributable rather than silent.

THE CEMENT INTENSITY IS AN UNVERIFIED EXTERNAL INPUT. 3.5322 GJ/t clinker and a 99 percent coal
energy share are attributed to a 2026 Mineral Economics paper whose DOI is Crossref-confirmed and
whose full text is PAYWALLED - the acquisition is logged blocked in
data/raw/ACQUISITION_LOG_industry_boundary.csv. The numbers reach this repository only through the
external analysis, so they are typed `external-unverified` here and are NOT ingested into
data/activity/: cement_thermal_evidence.csv is a ledger of company disclosures, and the brick
evidence table's own test requires every row to cite a document this repository holds.

Reads:  outputs/pakemis_atomic_annual.csv, outputs/industry_coal_reconciliation.csv,
        outputs/pakemis_cement_kiln_coal_reconstruction.csv,
        data/activity/industry/coal_by_consumer.csv, data/emission_factors.csv
Writes: outputs/pakemis_industrial_coal_scenarios.csv
"""
import csv
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from pkinv.assets import asset_path

from pkinv.core.gwp import GWP  # noqa: E402
from pkinv.paths import DATA, OUTPUTS, ROOT  # noqa: E402
from pkinv.report import reporting_sectors  # noqa: E402

ATOMS = asset_path(OUTPUTS, "pakemis_atomic_annual.csv")
RECON = asset_path(OUTPUTS, "industry_coal_reconciliation.csv")
CEMENT = asset_path(OUTPUTS, "pakemis_cement_kiln_coal_reconstruction.csv")
FACTORS = asset_path(DATA, "emission_factors.csv")
OUT = asset_path(OUTPUTS, "pakemis_industrial_coal_scenarios.csv")

START, END = "FY2015-16", "FY2023-24"
COAL_STREAMS = ("Brick-kiln coal", "Cement-sector coal")
CONFIG = "REF_2023_24"

# The one pair of numbers this product takes from outside. Paywalled; see the module docstring.
EXT_THERMAL_GJ_PER_T_CLINKER = 3.5322
EXT_COAL_ENERGY_SHARE = 0.99
EXT_CEMENT_NCV_GJ_PER_T = 27.0   # the external analysis's illustrative cement-coal NCV
EXT_SOURCE = "Sumair, Ali and Tanzeel-ur-Rashid 2026, Mineral Economics, doi:10.1007/s13563-026-00653-8 (FY2022-23 basis)"

FIELDS = ("scenario_id", "kind", "industrial_coal_Mt", "direct_1a2_MtCO2e",
          "broader_industry_MtCO2e", "direct_change_MtCO2e", "broader_change_MtCO2e",
          "external_value_MtCO2e", "conditions", "note")


def rows(path):
    from pkinv.activity.store import read_rows as canonical_rows
    return canonical_rows(path, comments=True)


def coal_factor():
    """tCO2e per tonne of industrial coal, built from the registry the engine reads.

    Coal CH4 is fossil-origin in the atom table (`gas_origin = fossil`), so it takes AR5's
    fossil-methane GWP of 30. Using 28 here would silently disagree with the shipped series.
    """
    f = {r["ef_id"]: float(r["value"]) for r in rows(FACTORS) if r.get("value")}
    ncv = f["res_ncv_coal"]                       # 25.8 TJ/Gg, Other Bituminous Coal
    per_tj = (f["ind_coal_co2"]
              + f["ind_coal_ch4"] * GWP["AR5"]["CH4_fossil"]
              + f["ind_coal_n2o"] * GWP["AR5"]["N2O"])
    return ncv * per_tj / 1e6, ncv, per_tj


def totals():
    """Reporting-axis industry and IPPU at both endpoints, and the coal streams inside them."""
    reg = reporting_sectors.rows()
    by_sector, coal = {}, {}
    for r in rows(ATOMS):
        if r["configuration_id"] != CONFIG or r["period_id"] not in (START, END):
            continue
        value = float(r["co2e_Mt_AR5"] or 0.0)
        rep = reporting_sectors.resolve(reg, r["sector_id"], r["category"], r.get("subitem", ""))
        by_sector[(rep, r["period_id"])] = by_sector.get((rep, r["period_id"]), 0.0) + value
        if r["subitem"].startswith(COAL_STREAMS):
            coal[r["period_id"]] = coal.get(r["period_id"], 0.0) + value
    return by_sector, coal


def coal_mass(coal_emissions_mt, factor):
    """Mt of booked industrial coal, recovered from the SHIPPED emissions and the engine's factor.

    Not re-read from data/activity/industry/coal_by_consumer.csv: that file carries one row per
    EDITION as well as per year, so a naive sum over a fiscal year adds superseded vintages
    together - a first draft of this module did exactly that and produced 11.475 Mt against the
    true 5.520. Which print is booked is declared in data/coal_booking_policy.csv and applied by
    the industry module; dividing the shipped emissions by the factor that produced them cannot
    disagree with the series, and a test asserts the recovered mass against the booked prints.
    """
    return coal_emissions_mt / factor


def build():
    factor, ncv, per_tj = coal_factor()
    by_sector, coal_e = totals()
    broader = {p: by_sector[("industry", p)] + by_sector[("ippu", p)] for p in (START, END)}
    direct = {p: by_sector[("industry", p)] for p in (START, END)}
    mass24 = coal_mass(coal_e[END], factor)

    # what stays fixed in every scenario: everything that is not the two coal streams
    non_coal_direct = direct[END] - coal_e[END]
    non_coal_broader = broader[END] - coal_e[END]

    gap = next(float(r["unmatched_kt"]) for r in rows(RECON)
               if r["fiscal_year"] == "2023-24" and r["unmatched_kt"]) / 1000.0
    clinker_kt = next(float(r["clinker_kt_census_actual"]) for r in rows(CEMENT)
                      if r["fiscal_year"] == "2023-24")

    def case(coal_mt):
        return (non_coal_direct + coal_mt * factor, non_coal_broader + coal_mt * factor)

    out = []

    def add(sid, kind, mt, d, b, ext, conditions, note):
        out.append({
            "scenario_id": sid, "kind": kind,
            "industrial_coal_Mt": "" if mt is None else "%.5f" % mt,
            "direct_1a2_MtCO2e": "" if d is None else "%.3f" % d,
            "broader_industry_MtCO2e": "" if b is None else "%.3f" % b,
            "direct_change_MtCO2e": "" if d is None else "%+.3f" % (d - direct[START]),
            "broader_change_MtCO2e": "" if b is None else "%+.3f" % (b - broader[START]),
            "external_value_MtCO2e": ext, "conditions": conditions, "note": note,
        })

    add("reported", "reported", mass24, direct[END], broader[END], "53.67",
        "none - this is the shipped series",
        "the reference estimate, on the reporting axis. Every other row is measured against it and "
        "none of them replaces it.")

    # cement coal from the external thermal intensity, on THIS release's clinker and factors
    heat_tj = clinker_kt * EXT_THERMAL_GJ_PER_T_CLINKER * EXT_COAL_ENERGY_SHARE
    cement_e = heat_tj * per_tj / 1e9
    brick_e = _stream_total(END, "Brick-kiln coal")
    sub_direct = non_coal_direct + brick_e + cement_e
    sub_broader = non_coal_broader + brick_e + cement_e
    add("cement_thermal_substitution", "scenario", None, sub_direct, sub_broader, "56.98",
        "the external FY2022-23 thermal intensity (%.4f GJ/t clinker, %.0f%% coal energy) transferred "
        "to FY2023-24 and applied to this release's own census-anchored clinker; reported brick coal "
        "retained" % (EXT_THERMAL_GJ_PER_T_CLINKER, 100 * EXT_COAL_ENERGY_SHARE),
        "%.1f PJ of kiln coal heat on %.0f kt clinker. The external analysis used a 41,302 kt clinker "
        "floor from rc21 with Fecto missing; this release's census-anchored figure is %.0f kt. Note "
        "what this does NOT resolve: the column being replaced is 'Cement/Other Industry', so the "
        "other-industry remainder inside it is unsplit either way."
        % (heat_tj / 1000, clinker_kt, clinker_kt))

    for ded in (0.0, 0.5, 1.0, 2.0):
        mt = mass24 + gap - ded
        d, b = case(mt)
        add("gross_reallocation_less_%s" % ("%.1f" % ded).replace(".", "p"), "sensitivity", mt, d, b,
            {0.0: "61.84", 0.5: "60.61", 1.0: "59.38", 2.0: "56.92"}[ded],
            "IF the whole %.5f Mt power-coal discrepancy were industrial, less %.1f Mt assigned "
            "elsewhere" % (gap, ded),
            "the deduction is a TEST, not a measurement: generators outside the eight-plant table, "
            "deliveries against burn, stock change and source error are all unseparated. Most of the "
            "discrepancy is Thar lignite, which cannot reach a kiln without evidence of delivery.")

    # THE QUALITY CASE IS AN NCV CASE, AND ONLY AN NCV CASE. Pricing the kiln's heat directly and
    # pricing the tonnage that carries it are the SAME arithmetic when both use one NCV - a first
    # draft did that and produced a row identical to the gross case. What the external analysis
    # actually assumes is that cement coal is BETTER coal (27 GJ/t against this release's 25.8), so
    # the same heat needs fewer tonnes and MORE of the gross mass is left in the remainder, priced
    # at the ordinary factor. That difference is the whole of the row.
    mt = mass24 + gap
    cement_mass = heat_tj / (1000 * EXT_CEMENT_NCV_GJ_PER_T)
    remainder = mt - cement_mass
    add("gross_plus_cement_quality", "scenario", mt,
        non_coal_direct + cement_e + remainder * factor,
        non_coal_broader + cement_e + remainder * factor, "62.78",
        "IF the whole %.5f Mt power-coal discrepancy were industrial AND cement coal were the "
        "external illustrative %.0f GJ/t rather than the %.1f this release burns every industrial "
        "tonne at, with the remainder priced at the release's own factor"
        % (gap, EXT_CEMENT_NCV_GJ_PER_T, ncv),
        "%.3f Mt of cement coal at the higher NCV against %.3f at this release's, leaving %.3f Mt as "
        "the remainder - which is 'brick AND other industrial', never brick alone. The external analysis "
        "reached +0.20 Mt against the start year here; a difference that small cannot establish "
        "growth while the allocation, the calorific value and the start-year balance are all open."
        % (cement_mass, heat_tj / (1000 * ncv), remainder))

    # both thresholds are computed once and BOTH are printed in each row: a first draft reused the
    # row's own value in a sentence that names both boundaries, so the direct row claimed the
    # broader boundary needed 25.2 percent
    need_broader = (broader[START] - non_coal_broader) / mt
    need_direct = (direct[START] - non_coal_direct) / mt
    for label, need, boundary in (("broader", need_broader, "broader covered industry"),
                                  ("direct", need_direct, "direct combustion, 1.A.2")):
        add("break_even_%s" % label, "break_even", mt, None, None, "",
            "the average coal factor at which %s would return to its FY2015-16 level, on the gross "
            "coal mass" % boundary,
            "%.3f tCO2e per tonne against this release's own %.4f. THE POINT OF THIS ROW: even on "
            "the gross coal mass the broader boundary needs a factor %.1f%% above the engine's and "
            "the direct boundary %.1f%% above - which is why a near-flat broader trend is "
            "arithmetically reachable and a rising direct-combustion trend is not. These are "
            "thresholds, not fuel properties: no coal grade in the registry reaches the second."
            % (need, factor, 100 * (need_broader / factor - 1), 100 * (need_direct / factor - 1)))

    return out, dict(factor=factor, gap=gap, mass24=mass24, clinker_kt=clinker_kt,
                     heat_tj=heat_tj, broader=broader, direct=direct)


def _stream_total(period, prefix):
    total = 0.0
    for r in rows(ATOMS):
        if r["configuration_id"] == CONFIG and r["period_id"] == period and r["subitem"].startswith(prefix):
            total += float(r["co2e_Mt_AR5"] or 0.0)
    return total


HEADER = """\
# INDUSTRIAL COAL SCENARIOS - what the reported industrial fall would have to be if the power-coal
# discrepancy belonged to industry. EVERY ROW IS A SCENARIO, NOT AN ESTIMATE: none replaces the
# reported series, none is additive with a total, and the deduction rows are sensitivity tests on an
# unresolved split rather than measured quantities. The 3.32 Mt discrepancy stays UNALLOCATED - it is
# a difference between HDIP's power allocation and NEPRA's metered plant burn, and most of it is Thar
# lignite, which cannot reach a kiln without evidence of delivery.
# The coal factor is built from data/emission_factors.csv and the engine's AR5 GWPs (coal CH4 is
# FOSSIL, GWP 30). external_value_MtCO2e carries the figure the 2026-09-14 external analysis
# published for the same case, so the difference is attributable; its cement thermal intensity is
# paywalled and unverified - the acquisition is logged blocked.
# Generated by scripts/build_industrial_coal_scenarios.py.
"""


def main():
    out, facts = build()
    with open(OUT, "w", newline="", encoding="utf-8") as handle:
        handle.write(HEADER)
        writer = csv.DictWriter(handle, fieldnames=list(FIELDS), lineterminator="\n")
        writer.writeheader()
        writer.writerows(out)
    print("industrial coal scenarios -> %s (%d rows)" % (os.path.relpath(OUT, ROOT), len(out)))
    print("  engine coal factor %.7f tCO2e/t; external back-derived 2.460145 (%.2f%% apart)"
          % (facts["factor"], 100 * (2.460145 / facts["factor"] - 1)))
    print("  power-coal discrepancy %.5f Mt, UNALLOCATED; reported industrial coal %.3f Mt"
          % (facts["gap"], facts["mass24"]))
    for r in out:
        print("  %-34s %-12s %8s %8s  %s" % (r["scenario_id"], r["kind"],
                                             r["direct_1a2_MtCO2e"], r["broader_industry_MtCO2e"],
                                             r["broader_change_MtCO2e"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
