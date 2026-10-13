"""The industrial fuel claimant ledger: what is controlled, what is only named.

WHY. The fifth and sixth reviews asked for the identity
F_industrial = F_brick + F_cement_fuel + F_other_industry + F_unresolved as an
executable ledger BEFORE any brick emissions estimate exists. This module is that
ledger, built honestly around the one structural fact the transport and waste ledgers
never had to face: there is NO OPENING CONTROL on the solid side. OCAC's customer
classes sum to a printed total (transport closes); waste generation is computed and
its fates partition it (waste closes); industrial solid fuel has no national
publication in this repository - the HDIP Pakistan Energy Yearbook is paywalled and
absent - so the solid tier CANNOT close arithmetically, and pretending otherwise
would manufacture the very number the reviews want exposed as missing.

TWO TIERS, TWO EPISTEMIC STATES.

  fluid  CLOSES. Opening = OGRA's sector-wise gas (Cement + General Industry rows)
         plus OCAC's Total Industry liquid products. The claimants are the engine's
         own streams; they sum to the opening to 1e-9 relative or this module aborts.
         Captive gas (5.55 Mt, power sector) is listed as ADJACENT on its own OGRA
         control, and the disjointness of the captive and General Industry rows is
         the engine's own tested property, restated here.

  solid  DECLARED OPEN. The opening is not a control but the EDGAR 1A2 benchmark
         residual (43.98 - engine estimate), kind=benchmark_residual: closure against
         an external estimate is not evidence about composition - the transport
         ledger's own caveat about its residual, repeated. The claimants carry
         Mt_co2e=None (never entering any sum) and a four-way control_status:

    control_held                   gas, liquids (the fluid tier)
    screening_intensity_transferred  cement kiln fuel (rc17): observed own-year
                                   clinker under a transferred heat intensity
    screening_ceiling_bound        sugar-mill process bagasse (rc17): the all-cane
                                   ceiling, because the crush share is unheld
    geometry_held_no_control       (retired for bricks by the rc13 screening)
    neither                        industrial coal and petroleum coke generally;
                                   captive plants burning solids

Usage:  python3 -m pkinv.sectors.industry.fuel_ledger
Writes: outputs/industry_fuel_ledger_2024.csv
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import csv
import os

from pkinv.core.components import enrich_co2e
from pkinv.paths import DATA, OUTPUTS
from pkinv.sectors.industry import combustion
from pkinv.sectors.industry.data import IndustryData
from pkinv.core.io import write_table

FIELDS = ("tier", "claimant", "ipcc_code", "fuel_class", "Mt_co2e",
          "share_of_opening", "kind", "control_status", "basis",
          "geometry_status", "gap_id", "note")

TOL = 1e-9

CONTROL_STATUSES = ("control_held", "activity_held_no_fuel_control",
                    "geometry_held_no_control", "neither", "benchmark_residual",
                    "adjacent_own_control",
                    # rc46 Wave 2: the two statuses the activation created. A claimant whose
                    # quantity now flows through a reference stream is SUPERSEDED - its row
                    # stays as the record of what screened it and what replaced it; and the
                    # petcoke/other-coal refusal CLOSED BY IDENTITY when the exhaustive
                    # series arrived (see the row's own note).
                    "superseded_by_reference_stream",
                    "closed_by_exhaustive_series",
                    # rc47 Wave 0: a claimant whose quantity sits INSIDE a booked
                    # reference stream (captive coal inside the brick residual
                    # column, per the activation gate's own text) is a bound on a
                    # share of booked mass, not a claim on the benchmark residual -
                    # adding it anywhere would double-count.
                    "contained_in_reference_stream",
                    # rc13: a screening-grade control at a declared prior vintage -
                    # the brick-kiln row's status once the PEY coal series was
                    # formalized. A quantity under this status is OUTSIDE every
                    # closure and every reference total; it exists so the largest
                    # solid claimant states its screened magnitude instead of
                    # implying ignorance the tree no longer has.
                    "screening_control_held_prior_vintage",
                    # rc17, the same graduation for the two claimants whose
                    # activity was already held: cement kiln fuel rides OBSERVED
                    # own-year clinker under a TRANSFERRED heat intensity (no
                    # Pakistani kiln audit is held), and process bagasse is a
                    # CEILING at the all-cane bound because the mill crush share
                    # was never acquired. Both quantities stay outside every
                    # closure and total, exactly as the brick screening does.
                    "screening_intensity_transferred",
                    "screening_ceiling_bound",
                    # Wave 4, the last two claimants decided: the captive fleet's
                    # coal is priced from the register's own capacity under a
                    # DECLARED utilization/heat-rate bracket (the judgement is
                    # the screening), and industrial coal/petcoke - with no
                    # series held anywhere - is REFUSED BY TYPE rather than left
                    # as the shrug 'neither' was. Both stay outside every
                    # closure and total.
                    "screening_capacity_bracket",
                    "refused_no_series_held")


def _benchmark_residual():
    """EDGAR 1A2 (data/benchmarks.csv) minus the engine's 1A2 across BOTH sectors that
    carry the category - industry's process heat and power's captive self-generation -
    the sum national_rollup.benchmark_comparison publishes as "1A2 (all estimated)".

    rc41: computed here from the sector engines. This module read the published
    comparison table back from outputs/, a product of the national rollup that runs
    AFTER the industry phase - so the first strict empty-outputs rebuild stopped here,
    and every earlier build had silently read the previous release's copy.
    """
    from pkinv.core import registry
    row = next(r for r in _activity_rows(asset_path(DATA, "benchmarks.csv"), comments=False)
               if r["source"] == "EDGAR" and r["engine_category"] == "1A2 (all estimated)")
    engine = 0.0
    for name in ("power", "industry"):
        sector = registry.get(name)
        engine += sum(c["co2e_Mt_AR5"] for c in sector.build_components(sector.load_data())
                      if c["category"].endswith("(1A2)"))
    # At the comparison table's own precision (2 dp, 14.56): the shares below were always
    # taken against that published figure, and the residual is quoted to 2 dp. Using the
    # unrounded sum would move three screening shares in their sixth decimal - a change
    # of arithmetic, not of the products' bytes, and so a named decision, not a side effect.
    return float(row["value_Mt_co2e"]) - round(engine, 2)


def build(data=None):
    data = data or IndustryData()
    from pkinv.sectors.industry import solid_fuels
    comps = enrich_co2e(combustion.compute(data)[0])
    solid_comps = enrich_co2e(solid_fuels.compute(data)[0])
    by_fuel = {}
    for c in comps:
        fuel = c["subitem"].rsplit(" ", 1)[0]
        by_fuel[fuel] = by_fuel.get(fuel, 0.0) + c["co2e_Mt_AR5"]
    solid_by_fuel = {}
    for c in solid_comps:
        fuel = c["subitem"].rsplit(" ", 1)[0]
        solid_by_fuel[fuel] = solid_by_fuel.get(fuel, 0.0) + c["co2e_Mt_AR5"]
    # The OPENING is the whole module - fluids and, since rc46 Wave 2, the two solid
    # reference streams. The fluid tier still closes against its own sum below; the solid
    # control_held rows close against theirs; and the module total is both.
    opening = sum(by_fuel.values()) + sum(solid_by_fuel.values())

    rows = []
    for fuel, mt in sorted(by_fuel.items()):
        gas_stream = fuel.endswith(" gas")
        rows.append({
            "tier": "fluid", "claimant": fuel, "ipcc_code": "1.A.2",
            "fuel_class": "gas" if gas_stream else "liquid",
            "Mt_co2e": mt, "share_of_opening": round(mt / opening, 6),
            "kind": "claim", "control_status": "control_held",
            "basis": ("OGRA sector-wise gas table" if gas_stream
                      else "OCAC Total Industry customer class"),
            "geometry_status": "", "gap_id": "",
            "note": ""})
    for fuel, mt in sorted(solid_by_fuel.items()):
        rows.append({
            "tier": "solid", "claimant": fuel, "ipcc_code": "1.A.2",
            "fuel_class": "solid",
            "Mt_co2e": mt, "share_of_opening": round(mt / opening, 6),
            "kind": "claim", "control_status": "control_held",
            "basis": "HDIP coal-by-consumer series (Statistical Supplement Table 14.1(4)), "
                     "activated at rc46 Wave 2 through the industrial_solid_fuels_1a2 gate",
            "geometry_status": ("11,272 kiln assets + coverage mask" if "Brick" in fuel
                                else "GEM register, 24 geocoded works"),
            "gap_id": "",
            "note": "REFERENCE STREAM: inside the module total and every closure; the "
                    "column's residual-style construction is priced as the stream's "
                    "30 percent activity band"})
    rows.append({
        "tier": "fluid", "claimant": "Captive gas self-generation",
        "ipcc_code": "1.A.2", "fuel_class": "gas", "Mt_co2e": "",
        "share_of_opening": "", "kind": "adjacent",
        "control_status": "adjacent_own_control",
        "basis": "OGRA captive row (power sector, 5.55 Mt on its own control)",
        "geometry_status": "1,068 geocoded plants in the facility registry",
        "gap_id": "",
        "note": "reported by the power module; the engine asserts the captive and "
                "General Industry rows are distinct values, so the two controls do "
                "not double-count"})

    residual = _benchmark_residual()
    rows.append({
        "tier": "solid", "claimant": "UNRESOLVED solid-fuel combustion",
        "ipcc_code": "1.A.2", "fuel_class": "solid",
        "Mt_co2e": round(residual, 2), "share_of_opening": "",
        "kind": "benchmark_residual",
        "control_status": "benchmark_residual",
        "basis": "EDGAR 1A2 (43.98) minus the engine estimate - "
                 "outputs/national_benchmark_comparison.csv",
        "geometry_status": "", "gap_id": "1A2-industrial-fuel",
        "note": "UNRESOLVED-AGAINST-EXTERNAL-BENCHMARK: an external estimate bounds "
                "the gap, it is not evidence about its composition - the transport "
                "ledger's caveat about its own residual, repeated. Shrunk by 13.57 Mt "
                "at rc46 Wave 2 when the solid reference streams above entered the "
                "engine; the SCREENING claimants below still carry no quantity into "
                "any sum"})
    from pkinv.sectors.industry import kiln_screening
    kiln_mt = kiln_screening.screening_mt()
    rows.append({
        "tier": "solid", "claimant": "Brick kilns (clay brick firing)",
        "ipcc_code": "1.A.2", "fuel_class": "solid",
        "Mt_co2e": round(kiln_mt, 5),
        "share_of_opening": round(kiln_mt / residual, 6),
        "kind": "claim",
        "control_status": "superseded_by_reference_stream",
        "basis": "screening_vintage_fy2022_23 - PEY Table 4.4 national brick-kiln "
                 "coal series (data/activity/industry/brick_kiln_coal.csv)",
        "geometry_status": "11,272 assets on the canonical ADM2 frame "
                           "(data/gis/kilns/pak_brick_kiln_assets.csv) with a "
                           "declared coverage mask",
        "gap_id": "brick-kiln-activity",
        "note": "SUPERSEDED at rc46 Wave 2: the graduation this row named "
                "happened - the Brick-kiln coal REFERENCE stream above prices the "
                "same flow on the full nine-year HDIP series at each year's own "
                "vintage (FY2023-24: 1,129 kt against this screening's FY2022-23 "
                "2,991). The row stays as the record of what screened it; its "
                "quantity enters no sum, and the screening module remains the "
                "air-pollutant lane"})
    from pkinv.sectors.industry import solid_screenings
    cement_bounds, cement_meta = solid_screenings.cement_screening()
    bagasse_mt = solid_screenings.bagasse_ceiling_mt()
    rows.append({
        "tier": "solid", "claimant": "Cement kiln fuel", "ipcc_code": "1.A.2",
        "fuel_class": "solid", "Mt_co2e": round(cement_bounds["central"], 5),
        "share_of_opening": round(cement_bounds["central"] / residual, 6),
        "kind": "claim", "control_status": "superseded_by_reference_stream",
        "basis": "producer census clinker (%.2f Mt, %d companies, own-year) x "
                 "the transferred dry-process heat-intensity range - "
                 "outputs/industry_solid_screenings_2024.csv"
                 % (cement_meta["clinker_t"] / 1e6, cement_meta["companies"]),
        "geometry_status": "", "gap_id": "cement-kiln-fuel",
        "note": "SUPERSEDED at rc46 Wave 2, and DEMOTED TO A COMPARATOR with a "
                "finding attached: the measured Cement-sector coal stream (10.72 Mt "
                "on HDIP's 4,391 kt) sits BELOW this model's %.2f-%.2f Mt bracket "
                "floor - either the transferred heat intensity overstates Pakistani "
                "kilns or part of the kiln heat is not coal (petcoke and RDF are "
                "not in the coal table). Recorded, not reconciled away. "
                "share_of_opening is against the benchmark residual above; the "
                "quantity enters no closure and no total - the category stays NE "
                "and the national configuration cement_kiln_fuel_in_scope prices "
                "the inclusion. The screening reads the residual's largest "
                "claimant at about half the residual"
                % (cement_bounds["low"], cement_bounds["high"])})
    rows.append({
        "tier": "solid", "claimant": "Sugar-mill process bagasse",
        "ipcc_code": "1.A.2", "fuel_class": "solid",
        "Mt_co2e": round(bagasse_mt, 5),
        "share_of_opening": round(bagasse_mt / residual, 6),
        "kind": "claim", "control_status": "screening_ceiling_bound",
        "basis": "the ENTIRE cane crop's bagasse at Table 2.3 biomass EFs, "
                 "CH4+N2O only - outputs/industry_solid_screenings_2024.csv",
        "geometry_status": "", "gap_id": "1A2-industrial-fuel",
        "note": "CEILING, rc17, not an estimate: the mill crush share is unheld "
                "(PSMA publishes it; never acquired), so this burns every tonne "
                "of cane's bagasse and still stays under half a megatonne of "
                "countable gas - its CO2 is biogenic and outside every total by "
                "construction, so bagasse cannot be a material part of the "
                "fossil-CO2 residual. Eight cogeneration plants are separately "
                "estimated in power"})
    from pkinv.sectors.industry import captive_screening
    captive_coal = [r for r in captive_screening.rows()
                    if r["configuration"] == "captive_coal_in_scope"][0]
    rows.append({
        "tier": "solid", "claimant": "Captive plants burning solids",
        "ipcc_code": "1.A.2", "fuel_class": "solid",
        "Mt_co2e": captive_coal["bracket_high_Mt"],
        "share_of_opening": round(captive_coal["bracket_high_Mt"] / residual, 6),
        "kind": "claim", "control_status": "contained_in_reference_stream",
        "basis": "the captive register's own coal-primary capacity (%.1f MW, %d "
                 "plants) under a DECLARED utilization and heat-rate bracket - "
                 "outputs/industry_captive_screening_2024.csv"
                 % (captive_coal["capacity_MW"], captive_coal["plants"]),
        "geometry_status": "", "gap_id": "captive-nongas-fuels",
        "note": "SCREENING BAND, Wave 4 (%.2f-%.2f Mt, quoted at the top): the "
                "capacity is the register's own, the unheld quantities are "
                "utilization and heat rate, both declared judgements the row "
                "names - the kiln-intensity pattern. Coal only: captive "
                "FO/diesel are excluded on double-count risk with this ledger's "
                "own fluid tier, captive bagasse as a sub-claimant of the "
                "all-cane ceiling, each a named row in the screening file. "
                "rc47 Wave 0: the bracket bounds the captive share OF the booked "
                "brick-residual stream (the activation gate records that captive "
                "coal sits inside that column), so the configuration "
                "captive_coal_in_scope is RETIRED - pricing it on top of the "
                "reference double-counted; NEPRA's captive licensing returns "
                "(annual generation) would still collapse the bracket"
                % (captive_coal["bracket_low_Mt"],
                   captive_coal["bracket_high_Mt"])})
    rows.append({
        "tier": "solid", "claimant": "Industrial coal and petroleum coke",
        "ipcc_code": "1.A.2", "fuel_class": "solid", "Mt_co2e": "",
        "share_of_opening": "", "kind": "claim",
        "control_status": "closed_by_exhaustive_series", "basis": "",
        "geometry_status": "", "gap_id": "1A2-industrial-fuel",
        "note": "THE REFUSAL CLOSED, rc46 Wave 2. The named closer arrived: the "
                "HDIP coal-by-consumer series (Statistical Supplement Table "
                "14.1(4)), whose categories EXHAUST supply - so 'other "
                "industrial coal' is definitionally zero in the national "
                "accounting, with steel/chemical/textile coal absorbed by the "
                "brick residual column and priced inside the activated "
                "brick-kiln stream's 30 percent activity band. PETCOKE is not "
                "in the coal table at all and remains its own trade-screen "
                "lane (1A2_petcoke_trade_screen). A refusal closed by identity "
                "rather than by a measured row is stated as such"})

    # BOTH tiers' control_held rows close against the module opening (rc46 Wave 2: the
    # opening includes the solid reference streams, so the closure does too). Screening,
    # superseded and residual rows carry no quantity into this sum by construction.
    held_sum = sum(r["Mt_co2e"] for r in rows
                   if r["control_status"] == "control_held" and r["Mt_co2e"] != "")
    if abs(held_sum - opening) > TOL * max(1.0, opening):
        raise SystemExit("control_held rows do not close: %r vs opening %r"
                         % (held_sum, opening))
    for r in rows:
        if r["control_status"] not in CONTROL_STATUSES:
            raise SystemExit("unknown control_status %r" % r["control_status"])
        if isinstance(r["Mt_co2e"], float):
            r["Mt_co2e"] = round(r["Mt_co2e"], 5)
    return rows


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    data = IndustryData()
    rows = build(data)
    path = asset_path(OUTPUTS, "industry_fuel_ledger_%d.csv" % data.year)
    write_table(path, list(FIELDS), rows)
    fluid = sum(float(r["Mt_co2e"]) for r in rows
                if r["tier"] == "fluid" and r["Mt_co2e"] != "")
    screened = [r for r in rows if r["tier"] == "solid" and r["kind"] == "claim"
                and r["Mt_co2e"] != ""]
    print("industry fuel ledger -> %s: fluid tier closes at %.4f Mt; solid tier "
          "opens on the %.2f Mt benchmark residual with %d no-quantity claimants "
          "and %d screened (%s), every screening outside every total"
          % (os.path.basename(path), fluid,
             next(float(r["Mt_co2e"]) for r in rows
                  if r["kind"] == "benchmark_residual"),
             sum(1 for r in rows if r["tier"] == "solid" and r["kind"] == "claim"
                 and r["Mt_co2e"] == ""),
             len(screened),
             "; ".join("%s %.2f Mt" % (r["claimant"], float(r["Mt_co2e"]))
                       for r in screened)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
