"""Where the national fuels go - a two-tier claimant ledger that must close.

WHY A LEDGER, AND WHAT CHANGED IN THE RE-ANCHOR. The first edition of this ledger
partitioned a national supply figure into resolved carve-outs and a road residual,
with agricultural and captive diesel as unresolved claims inside it. The August 2026
re-anchor on OCAC's Sectoral Sales table makes most of that structure OBSERVED
rather than argued: the national tier now reads OCAC's customer-class rows directly
- Railways, Power, Industry, Government, Domestic Bunkers and Road are separate rows
of one table whose classes sum to the printed national total exactly - and only the
road tier still carries unresolved claims, because a customer class cannot see end
uses. Retail-bought diesel for stationary agricultural plant and captive generation
remains inside the Road row, biased high, conditional on the other deductions.

THE TWO TIERS. Tier "national": opening = OCAC TOTAL_INTERNAL, claims = the customer
classes, closing = the Road control. Tier "road": opening = Road, claims = the
off-road partition (diesel) or the household-generator carve-out (petrol), closing =
the on-road residual, plus the UNRESOLVED status rows with no quantity - the
nine-year Road share of national HSD (0.826-0.907) is a customer-class boundary
sensitivity, and the retail_nonroad scenarios price the within-channel claim. Both tiers close to TOL relative, per fuel; the run aborts
otherwise.

WHAT THIS LEDGER IS NOT. CNG never appears here - a different fuel from a different
statistic (OGRA metered sector gas), asserted by tests/test_cng.py to claim no share
of either petroleum control. And closure is an arithmetic property of the ledger,
not evidence that the residual is road: the evidence for the residual's composition
is the customer-class semantics of the Road row, and its remaining contamination is
carried as the unresolved rows, never as silence.

Every resolved quantity is read from the module or table that owns it -
data.ocac_t(), road.off_road_TJ(), road.generator_petrol_kt() - never transcribed.
tests/test_transport.py asserts each row equals its accessor and that all four
(fuel, tier) ledgers close.

Usage:  python3 -m pkinv.sectors.transport.fuel_ledger
Writes: outputs/transport_fuel_ledger_2022.csv
"""

from pkinv.assets import asset_path
import csv
import os

from pkinv.core import period, registry
from pkinv.paths import OUTPUTS
from pkinv.sectors.transport import road
from pkinv.sectors.transport.data import TransportData

TOL = 1e-9

FIELDS = ("fuel", "tier", "claimant", "ipcc_code", "kt", "share_of_opening",
          "kind", "status", "basis", "gap_id", "note")


def _row(fuel, tier, claimant, code, kt, kind, status, basis, gap_id="", note=""):
    return {"fuel": fuel, "tier": tier, "claimant": claimant, "ipcc_code": code,
            "kt": kt, "kind": kind, "status": status, "basis": basis,
            "gap_id": gap_id, "note": note}


def build(data=None, rail_data=None, res_data=None):
    """Return (rows, checks): the two-tier claimant ledger for both fuels.

    checks: {(fuel, tier): closing residual in kt} - each must be ~0 relative to
    its opening. Unresolved rows carry kt=None and never enter a sum.
    """
    data = TransportData() if data is None else data
    t = lambda s, p: data.ocac_t(s, p) / 1000.0            # tonnes -> kt
    rows, checks = [], {}
    # The fiscal-year label is READ FROM THE SECTOR, not written down. It was written down,
    # and when the sector moved from FY2021-22 to FY2023-24 the numbers moved and the labels
    # did not: this output described its own current controls as "OCAC Sectoral Sales
    # FY2021-22" for a whole release. A basis string that names the wrong year is worse than
    # no basis string, because it is checkable and wrong.
    _s = registry.get("transport")
    fy = period.label(_s.PERIOD_START, _s.PERIOD_END)

    # ---- Diesel, national tier: OCAC's own partition -----------------------------
    opening_d = t("TOTAL_INTERNAL", "HSD")
    chk = road.rail_crosscheck(data, rail_data)
    classes_d = [
        ("Domestic", "1.A.4.b", t("DOMESTIC", "HSD"), "",
         "household HSD; nil in %s" % fy),
        ("Agriculture (bulk)", "1.A.4.c i", t("AGRICULTURE", "HSD"), "",
         "OCAC books ZERO bulk HSD to Agriculture in all nine editions (its "
         "agriculture row is LDO, 11,822 t) - the agricultural diesel claim is "
         "retail-channel only, inside Road"),
        ("Industry", "1.A.2", t("Total Industry", "HSD"), "",
         "bulk industrial deliveries, incl. whatever captive generation buys in "
         "bulk; excluded from the road control by construction"),
        ("Railways", "1.A.3.c", t("Railways", "HSD"), "",
         "cross-checked against the Year Book on two bases: the matched "
         "FY2023-24 pair (%.1f kt metered vs %.1f kt sold, %.1f%% apart) "
         "and the FY2021-22 historical bracket (%.1f kt, %.1f%%) - two "
         "unrelated reporting chains, the boundary's one independent check"
         % (chk["yb_kt"], chk["ocac_kt"], 100 * chk["rel_diff_matched"],
            chk["yb_historical_kt"], 100 * chk["rel_diff"])),
        ("Domestic bunkers", "1.A.3.d", t("Domestic Bunkers", "HSD"), "",
         "domestic navigation - a visible quantity, not an absent mode. The "
         "screening conversion on IPCC water-borne factors is computed per "
         "edition in outputs/transport_navigation_screen_2024.csv rather than "
         "quoted here: a hard-coded Mt figure in this note sat at the FY2021-22 "
         "value for two editions while the row underneath it halved"),
        ("Power", "1.A.1.a", t("Total Power", "HSD"), "",
         "utility liquid fuel; NEPRA's independent series bounds it"),
        ("Government", "various", t("Total Government", "HSD"), "",
         "government fuel incl. military and government aviation/bunkers rows"),
    ]
    road_d = t("Road", "HSD")
    resolved_d = sum(kt for _c, _i, kt, _g, _n in classes_d)
    checks[("Diesel", "national")] = opening_d - (resolved_d + road_d)

    rows.append(_row("Diesel", "national", "National internal HSD sales", "",
                     opening_d, "opening", "CONTROL",
                     "OCAC Sectoral Sales %s, TOTAL INTERNAL row "
                     "(data/activity/transport/ocac_sectoral_annual.csv)" % fy,
                     note="The printed total the customer classes sum to exactly."))
    for claimant, code, kt, gap, note in classes_d:
        rows.append(_row("Diesel", "national", claimant, code, kt, "claim",
                         "RESOLVED-OBSERVED", "OCAC customer-class row", gap, note))
    rows.append(_row("Diesel", "national", "Road (retail pump sales)", "1.A.3.b",
                     road_d, "closing", "CONTROL",
                     "OCAC Road row - the diesel control this sector anchors on",
                     note="A customer class, not an end use: the road tier below "
                          "partitions it."))

    # ---- Diesel, road tier -------------------------------------------------------
    ncv_d = data.efv("transport_ncv", "Gas/Diesel Oil")
    offroad_kt = road.off_road_TJ(data) / ncv_d
    onroad_d = road_d - offroad_kt
    checks[("Diesel", "road")] = road_d - (offroad_kt + onroad_d)
    shares = [data.ocac_t("Road", "HSD", y)
              / data.ocac_t("TOTAL_INTERNAL", "HSD", y)
              for y in data.ocac_years()]
    share_band = "%.3f-%.3f" % (min(shares), max(shares))
    rows += [
        _row("Diesel", "road", "Off-road machinery", "1.A.4.c ii / 1.A.2 gvii",
             offroad_kt, "claim", "RESOLVED-ALLOCATED",
             "partitioned: road.off_road_TJ() by vehicle-km share over all classes",
             note="The class absorbs the source workbook's 'Other vehicles' "
                  "residual, so construction machinery that IPCC books to 1A2 gvii "
                  "is inside it - declared, and priced by the "
                  "offroad_reallocated_1a2 scenario."),
        _row("Diesel", "road", "On-road transport", "1.A.3.b", onroad_d,
             "closing", "RESOLVED-RESIDUAL", "closing residual of the Road row",
             note="Biased high by the unresolved claimants below, conditional on "
                  "the other deductions."),
        _row("Diesel", "road", "Stationary agricultural plant (retail)",
             "1.A.4.c i", None, "unresolved", "UNRESOLVED-INSIDE-ON-ROAD",
             "retail channel; no within-Road end-use split exists in the source",
             "transport-hsd-end-use",
             "Tube wells and stationary engines fuelled at retail stations. "
             "Bounded: the nine-year Road share of national HSD spans %s, and "
             "bulk agricultural HSD is zero." % share_band),
        _row("Diesel", "road", "Captive generation (retail)", "1.A.2", None,
             "unresolved", "UNRESOLVED-INSIDE-ON-ROAD",
             "retail channel; no within-Road end-use split exists in the source",
             "transport-hsd-end-use",
             "Captive gensets fuelled at retail stations; the bulk captive "
             "channel is inside the Industry row above."),
        _row("Diesel", "road", "Other retail stationary/non-road uses", "various",
             None, "unresolved", "UNRESOLVED-INSIDE-ON-ROAD",
             "retail channel; the named claimants above are not proven exhaustive",
             "transport-hsd-end-use",
             "Whatever other stationary or non-road engines buy diesel at retail "
             "pumps. Listed so the ledger does not silently assert that "
             "agriculture and captive generation are the only possibilities; the "
             "retail_nonroad_* scenarios price the whole within-channel claim at "
             "2.5/5/10 percent of the Road row."),
    ]

    # ---- Petrol, national tier ---------------------------------------------------
    opening_p = t("TOTAL_INTERNAL", "MS") + t("TOTAL_INTERNAL", "HOBC")
    classes_p = [
        ("Industry", "1.A.2",
         t("Total Industry", "MS") + t("Total Industry", "HOBC"), "",
         "bulk industrial petrol"),
        ("Government", "various",
         t("Total Government", "MS") + t("Total Government", "HOBC"), "",
         "government fleets and aviation ground use"),
        ("Domestic", "1.A.4.b",
         t("DOMESTIC", "MS") + t("DOMESTIC", "HOBC"), "",
         "household petrol delivered outside the retail pump channel; nil in "
         "%s" % fy),
    ]
    road_p = t("Road", "MS") + t("Road", "HOBC")
    resolved_p = sum(kt for _c, _i, kt, _g, _n in classes_p)
    checks[("Petrol", "national")] = opening_p - (resolved_p + road_p)

    rows.append(_row("Petrol", "national", "National internal MS+HOBC sales", "",
                     opening_p, "opening", "CONTROL",
                     "OCAC Sectoral Sales %s, TOTAL INTERNAL row" % fy))
    for claimant, code, kt, gap, note in classes_p:
        rows.append(_row("Petrol", "national", claimant, code, kt, "claim",
                         "RESOLVED-OBSERVED", "OCAC customer-class row", gap, note))
    rows.append(_row("Petrol", "national", "Road (retail pump sales)", "1.A.3.b",
                     road_p, "closing", "CONTROL",
                     "OCAC Road row - the petrol control this sector anchors on"))

    # ---- Petrol, road tier -------------------------------------------------------
    gen_kt = road.generator_petrol_kt(res_data)
    onroad_p = road_p - gen_kt
    checks[("Petrol", "road")] = road_p - (gen_kt + onroad_p)
    rows += [
        _row("Petrol", "road", "Household generators", "1.A.4.b", gen_kt, "claim",
             "RESOLVED-CARVED-OUT",
             "relayed: pkinv.sectors.residential.combustion.generator_petrol_kt()",
             note="HIES 2024-25 generator-fuel expenditure over the administered "
                  "price; exact-equality tested in tests/test_residential.py."),
        _row("Petrol", "road", "On-road transport", "1.A.3.b", onroad_p,
             "closing", "RESOLVED-RESIDUAL", "closing residual of the Road row",
             note="No off-road petrol claim: the fleet model's off-road class is "
                  "modelled 100% diesel."),
    ]

    openings = {("Diesel", "national"): opening_d, ("Diesel", "road"): road_d,
                ("Petrol", "national"): opening_p, ("Petrol", "road"): road_p}
    for r in rows:
        opening = openings[(r["fuel"], r["tier"])]
        r["share_of_opening"] = (None if r["kt"] is None
                                 else r["kt"] / opening)
    return rows, checks


BRIDGE_FIELDS = ("fuel", "step", "kind", "kt", "ncv_TJ_per_Gg", "TJ", "basis",
                 "ipcc_code", "note")


def bridge(data=None, res_data=None):
    """The mass-to-energy bridge: OCAC row -> deduction/partition -> operative basis.

    THE ASYMMETRY THIS EXISTS TO MAKE VISIBLE. The published fuel table prints petrol
    at 401,856 TJ and diesel at 339,123 TJ side by side, and they are not the same
    kind of number: the petrol figure is NET of the household-generator carve-out
    (which is subtracted in mass, before the calorific conversion) while the diesel
    figure is GROSS of the off-road partition that happens downstream. Gross petrol is
    404,351 TJ. Nothing was wrong with either number; what was missing was the label,
    and a reader who multiplied the printed 9,128 kt by 44.3 got a third number again.

    Kept out of the claimant ledger deliberately. That ledger's contract is that MASS
    closes to a residual, and mixing an energy column into it invites a reader to check
    the wrong closure; CNG cannot appear there at all, because it claims no share of
    either petroleum control - yet CNG is exactly what this bridge has to show, since
    the fuel table's two rows sum to 100% while 23,568 TJ of metered gas sits outside
    them.
    """
    from pkinv.sectors.transport import cng
    data = TransportData() if data is None else data
    gen = road.generator_petrol_kt(res_data)
    p_kt = (data.ocac_t("Road", "MS") + data.ocac_t("Road", "HOBC")) / 1e3
    d_kt = data.ocac_t("Road", "HSD") / 1e3
    p_ncv = data.efv("transport_ncv", "Motor Gasoline")
    d_ncv = data.efv("transport_ncv", "Gas/Diesel Oil")
    off_TJ = road.off_road_TJ(data)
    tj = road.fuel_TJ(data)
    gas_TJ = cng.gas_TJ(data)
    gross_gas = gas_TJ / data.p("cng_gross_to_net")

    def r(fuel, step, kind, kt, ncv, TJ, basis, code="", note=""):
        return {"fuel": fuel, "step": step, "kind": kind,
                "kt": None if kt is None else round(kt, 4),
                "ncv_TJ_per_Gg": ncv, "TJ": round(TJ, 1), "basis": basis,
                "ipcc_code": code, "note": note}

    return [
        r("Petrol", "OCAC Road row (MS + HOBC)", "opening", p_kt, p_ncv,
          p_kt * p_ncv, "GROSS", "1.A.3.b",
          "the customer-class row as published, before any carve-out"),
        r("Petrol", "less household generators", "deduction", -gen, p_ncv,
          -gen * p_ncv, "carve-out", "1.A.4.b",
          "relayed from the residential sector; subtracted in MASS, before the "
          "calorific conversion"),
        r("Petrol", "operative petrol control", "closing", p_kt - gen, p_ncv,
          tj["Petrol"], "NET", "1.A.3.b",
          "what the engine distributes - and what the fuel table prints"),
        r("Diesel", "OCAC Road row (HSD)", "opening", d_kt, d_ncv,
          d_kt * d_ncv, "GROSS", "1.A.3.b",
          "no deduction applies at this stage: Railways is its own OCAC row, so "
          "the printed diesel energy IS the gross row - unlike petrol"),
        r("Diesel", "less off-road partition", "partition", -off_TJ / d_ncv, d_ncv,
          -off_TJ, "partition", "1.A.4.c ii / 1.A.2 g vii",
          "energy-weighted share of the same normalisation that splits the on-road "
          "classes; a partition, not a deduction - the fuel stays in the inventory"),
        r("Diesel", "operative on-road control", "closing",
          d_kt - off_TJ / d_ncv, d_ncv, tj["Diesel"] - off_TJ, "NET of partition",
          "1.A.3.b", "the 1A3b diesel energy"),
        r("Diesel", "off-road partition (memo)", "memo", off_TJ / d_ncv, d_ncv,
          off_TJ, "partition", "1.A.4.c ii / 1.A.2 g vii",
          "reported as its own category, not excluded"),
        r("CNG", "OGRA metered sector gas", "opening", None, "", gross_gas,
          "GROSS", "1.A.3.b",
          "a third control on its own activity basis; no share of either "
          "petroleum control, which is why it cannot appear in the claimant ledger"),
        r("CNG", "x gross-to-net %.2f" % data.p("cng_gross_to_net"), "conversion",
          None, "", gas_TJ - gross_gas, "conversion", "",
          "IPCC net calorific convention"),
        r("CNG", "operative CNG control", "closing", None, "", gas_TJ, "NET",
          "1.A.3.b", "what the CNG stream burns"),
        r("--", "Table asymmetry, stated", "note", None, "", 0.0, "", "",
          "the published fuel table prints petrol NET of the generator carve-out "
          "(%.0f TJ) beside diesel GROSS of the off-road partition (%.0f TJ). "
          "Gross petrol is %.0f TJ. Both printed numbers are correct; this row is "
          "the label they were missing."
          % (tj["Petrol"], tj["Diesel"], p_kt * p_ncv)),
    ]


def write_bridge(data=None):
    os.makedirs(OUTPUTS, exist_ok=True)
    data = TransportData() if data is None else data
    rows = bridge(data)
    path = asset_path(OUTPUTS, "transport_fuel_bridge_%d.csv" % data.year)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(BRIDGE_FIELDS))
        w.writeheader()
        for row in rows:
            w.writerow({k: ("" if row[k] is None else row[k]) for k in BRIDGE_FIELDS})
    print("  fuel bridge: %d rows -> %s" % (len(rows), os.path.basename(path)))
    return rows


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    data = TransportData()
    rows, checks = build(data)
    path = asset_path(OUTPUTS, "transport_fuel_ledger_%d.csv" % data.year)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(FIELDS)
        for r in rows:
            w.writerow([r["fuel"], r["tier"], r["claimant"], r["ipcc_code"],
                        "" if r["kt"] is None else round(r["kt"], 4),
                        "" if r["share_of_opening"] is None
                        else round(r["share_of_opening"], 6),
                        r["kind"], r["status"], r["basis"], r["gap_id"],
                        r["note"]])

    print("Transport fuel ledger, %d (kt):" % data.year)
    tier = None
    for r in rows:
        if (r["fuel"], r["tier"]) != tier:
            tier = (r["fuel"], r["tier"])
            print("  -- %s, %s tier --" % tier)
        qty = "     (unresolved)" if r["kt"] is None else "%9.1f kt" % r["kt"]
        print("    %-38s %-20s %s" % (r["claimant"], r["ipcc_code"], qty))

    openings = {("Diesel", "national"): data.ocac_t("TOTAL_INTERNAL", "HSD") / 1e3,
                ("Petrol", "national"):
                    (data.ocac_t("TOTAL_INTERNAL", "MS")
                     + data.ocac_t("TOTAL_INTERNAL", "HOBC")) / 1e3,
                ("Diesel", "road"): data.ocac_t("Road", "HSD") / 1e3,
                ("Petrol", "road"):
                    (data.ocac_t("Road", "MS")
                     + data.ocac_t("Road", "HOBC")) / 1e3}
    bad = [k for k, resid in checks.items()
           if abs(resid) > TOL * openings[k]]
    if bad:
        raise SystemExit("LEDGER DOES NOT CLOSE: " + ", ".join(map(str, bad)))
    print("  All four (fuel, tier) ledgers close to < %.0e relative." % TOL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
