"""WHERE THE 1.A.2 DECLINE COMES FROM: activity, source revision, classification, coverage or
calculation assumption (rc53 Wave A3).

The question this product answers is the one a reader actually asks of the industrial bar: the
series falls, but is the FALL PHYSICAL? It cannot be answered by a single number, so the answer is a
decomposition with one row per (stream, channel) and an explicit kind:

  booked          what the release publishes today, at the booked vintage and the current boundary
  counterfactual  the same quantity computed under a DIFFERENT defensible choice (another edition's
                  print, another boundary) - the signed effect on the measured change
  bound           a quantity the series does not contain at all, carried as a band, never a point
  note            a statement about what the number is, with no arithmetic attached

Only `booked` rows sum: their total is exactly the published change. A counterfactual is not added
to it; it says what the change would have been instead. A bound is not added to anything.

WHAT THE ROWS SAY, IN ONE PARAGRAPH. The published industrial-fuel bar falls 11.69 Mt because the
module holds 1.A.2 minus captive generation. On the IPCC category the release itself files (both
modules), 1.A.2 falls 13.63 Mt: fixing the boundary makes the decline LARGER, not smaller, because
captive self-generation fell too. Two thirds of the fall is the two coal streams, whose activity is
HDIP's estimated allocation - and the vintage of that allocation is a choice worth 0.50 Mt on the
brick endpoint alone. The cement column's own clinker-implied kiln-fuel band spans a change from
-2.17 to +6.83 Mt, so the reconstruction does not even agree on the SIGN of that stream's change.
Nothing here corrects a number; it says which parts of the decline rest on what.

Reads:  outputs/pakemis_atomic_annual.csv, outputs/pakemis_coal_vintage_ledger.csv,
        outputs/pakemis_industrial_coal_bridge.csv, data/activity/industry/coal_by_sector_vintages.csv,
        data/coal_booking_policy.csv, outputs/industry_captive_screening_2024.csv
Writes: outputs/pakemis_industrial_change_attribution.csv
"""
import csv
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from pkinv.assets import asset_path

from pkinv.paths import DATA, OUTPUTS, ROOT  # noqa: E402

ATOMS = asset_path(OUTPUTS, "pakemis_atomic_annual.csv")
VINT_LEDGER = asset_path(OUTPUTS, "pakemis_coal_vintage_ledger.csv")
VINTAGES = asset_path(DATA, "activity", "industry", "coal_by_sector_vintages.csv")
BRIDGE = asset_path(OUTPUTS, "pakemis_industrial_coal_bridge.csv")
CAPTIVE = asset_path(OUTPUTS, "industry_captive_screening_2024.csv")
OUT = asset_path(OUTPUTS, "pakemis_industrial_change_attribution.csv")

START, END = "FY2015-16", "FY2023-24"
CONFIG = "S_TAN"
FIELDS = ("stream", "module", "ipcc_code", "channel", "kind", "start_Mt", "end_Mt",
          "change_Mt", "effect_on_change_Mt", "low_Mt", "high_Mt", "evidence", "reading")
# kt of coal -> Mt CO2e at the engine's single industrial-coal bucket (Other Bituminous Coal)
COAL_MT_PER_KT = 25.8 * (94600.0 + 10.0 * 28.0 + 1.5 * 265.0) / 1e9


def rows(path):
    from pkinv.activity.store import read_rows as canonical_rows
    return canonical_rows(path, comments=True)


def endpoints():
    """(module, stream) -> {period: Mt} for every priced 1.A.2 atom."""
    out = {}
    for r in rows(ATOMS):
        if r["ipcc_code"] != "1.A.2" or r["configuration_id"] != CONFIG:
            continue
        if r["period_id"] not in (START, END):
            continue
        key = (r["sector_id"], r["subitem"].rsplit(" ", 1)[0])
        out.setdefault(key, {}).setdefault(r["period_id"], 0.0)
        out[key][r["period_id"]] += float(r["co2e_Mt_AR5"] or 0.0)
    return out


def _f(x):
    return "" if x is None else "%.4f" % x


def build():
    eps = endpoints()
    out = []

    def add(stream, module, channel, kind, start=None, end=None, effect=None,
            low=None, high=None, evidence="", reading=""):
        change = None if (start is None or end is None) else end - start
        out.append({"stream": stream, "module": module, "ipcc_code": "1.A.2", "channel": channel,
                    "kind": kind, "start_Mt": _f(start), "end_Mt": _f(end), "change_Mt": _f(change),
                    "effect_on_change_Mt": _f(effect), "low_Mt": _f(low), "high_Mt": _f(high),
                    "evidence": evidence, "reading": reading})

    # ---- booked: every priced 1.A.2 atom, exactly as published -------------------------------
    for (module, stream), by_period in sorted(eps.items()):
        a, b = by_period.get(START, 0.0), by_period.get(END, 0.0)
        add(stream, module, "recorded activity (booked)", "booked", start=a, end=b,
            evidence="outputs/pakemis_atomic_annual.csv (%s)" % CONFIG,
            reading=("the published series; the emission factor is constant across the window, so "
                     "this change IS the change in recorded fuel"))

    ind = {k: v for k, v in eps.items() if k[0] == "industry"}
    cap = {k: v for k, v in eps.items() if k[0] == "power"}
    ind_change = sum(v.get(END, 0.0) - v.get(START, 0.0) for v in ind.values())
    cap_change = sum(v.get(END, 0.0) - v.get(START, 0.0) for v in cap.values())

    # ---- classification: the boundary the bar is drawn on -------------------------------------
    add("1.A.2 Manufacturing industries and construction", "industry+power", "classification: the module bar vs the IPCC category",
        "counterfactual",
        start=sum(v.get(START, 0.0) for v in eps.values()), end=sum(v.get(END, 0.0) for v in eps.values()),
        effect=(ind_change + cap_change) - ind_change,
        evidence="outputs/national_category_gas.csv (1.A.2 rows, two modules); IPCC 2006 Vol 2 Ch 2",
        reading=("the industry MODULE falls %.2f Mt; IPCC 1.A.2, which includes the captive "
                 "self-generation the power module computes, falls %.2f Mt. Fixing the boundary makes "
                 "the decline LARGER by %.2f Mt, because captive generation fell too - the narrow bar "
                 "understates the fall it is accused of overstating"
                 % (ind_change, ind_change + cap_change, cap_change)))

    # ---- source revision: what the vintage choice is worth ------------------------------------
    prints = {}
    for r in rows(VINTAGES):
        if r["period_coverage"] == "full_year" and r["value"]:
            prints.setdefault((r["reference_fiscal_year"], r["sector_mapped"]), {})[r["estimate_id"]] = float(r["value"])
    policy = {(r["reference_fiscal_year"], r["consumer"]): r for r in rows(asset_path(DATA, "coal_booking_policy.csv"))}
    for consumer, sector, stream in (("brick_kilns", "brick_kilns", "Brick-kiln coal"),
                                     ("cement", "cement_other", "Cement-sector coal")):
        booked_start = policy[(START[2:], consumer)]["booked_estimate_id"]
        booked_end = policy[(END[2:], consumer)]["booked_estimate_id"]
        start_prints, end_prints = prints[(START[2:], sector)], prints[(END[2:], sector)]
        alt = [(eid, v) for eid, v in sorted(start_prints.items()) if abs(v - start_prints[booked_start]) > 1.0]
        if not alt:
            add(stream, "industry", "source revision: the start-year vintage", "note",
                evidence="outputs/pakemis_coal_vintage_ledger.csv",
                reading="every edition prints the same start-year value; the endpoint is not vintage-dependent")
            continue
        alt_id, alt_kt = alt[0]
        booked_change_kt = end_prints[booked_end] - start_prints[booked_start]
        alt_change_kt = end_prints[booked_end] - alt_kt
        add(stream, "industry", "source revision: the start-year vintage", "counterfactual",
            start=alt_kt * COAL_MT_PER_KT, end=end_prints[booked_end] * COAL_MT_PER_KT,
            effect=(alt_change_kt - booked_change_kt) * COAL_MT_PER_KT,
            evidence="data/coal_booking_policy.csv books %s; %s also prints this year" % (booked_start, alt_id),
            reading=("the series is NOT single-vintage: %s is booked at %.3f kt and every other year at "
                     "the Supplement print, because the Supplement's %.1f kt breaks the supply balance. "
                     "Booking the Supplement throughout would make the decline %.3f Mt instead of %.3f - "
                     "a declared method transition worth %.3f Mt, which IPCC 2006 Vol 1 Ch 5 requires be "
                     "documented and tested rather than hidden"
                     % (START, start_prints[booked_start], alt_kt, alt_change_kt * COAL_MT_PER_KT,
                        booked_change_kt * COAL_MT_PER_KT, (alt_change_kt - booked_change_kt) * COAL_MT_PER_KT)))

    # a reallocation inside the window would move a booked endpoint; say whether one does
    realloc = [r for r in rows(VINT_LEDGER) if r["revision_kind"] == "reallocation_within_total"]
    in_window = [r for r in realloc if r["period_coverage"] == "full_year"
                 and "FY" + r["reference_fiscal_year"] in (START, END)]
    add("Brick-kiln coal + Cement-sector coal", "industry", "source revision: reallocation between users", "note",
        evidence="outputs/pakemis_coal_vintage_ledger.csv (%d reallocation rows)" % len(realloc),
        reading=("the two reallocations in the held record are July-March FY2023-24 (1,500 kt from brick "
                 "kilns to cement/others, total unchanged) and full-year FY2024-25 (133 kt back). NEITHER "
                 "touches a booked endpoint: the first is a nine-month figure the release never books, the "
                 "second is outside the reporting window%s. And brick + cement/others is invariant across "
                 "both, so reversing one would redistribute between subsectors and change no industrial "
                 "total" % ("" if not in_window else "; %d DO fall in the window" % len(in_window))))

    # ---- the cement reconstruction: does it agree on the SIGN? --------------------------------
    br = {(r["fiscal_year"], r["component"]): r for r in rows(BRIDGE)}
    comp = "1.A.2 cement kiln coal"
    a, b = br.get((START[2:], comp)), br.get((END[2:], comp))
    if a and b and a["reconstructed_low_mt"] and b["reconstructed_low_mt"]:
        lo = float(b["reconstructed_low_mt"]) - float(a["reconstructed_high_mt"])
        hi = float(b["reconstructed_high_mt"]) - float(a["reconstructed_low_mt"])
        official = eps[("industry", "Cement-sector coal")][END] - eps[("industry", "Cement-sector coal")][START]
        add("Cement-sector coal", "industry", "activity: kiln fuel reconstructed from clinker", "bound",
            low=lo, high=hi,
            evidence="outputs/pakemis_industrial_coal_bridge.csv (K x H x s / NCV; H and NCV transferred)",
            reading=("the clinker-implied kiln-fuel band puts this stream's change between %+.2f and "
                     "%+.2f Mt against the booked %+.2f: the reconstruction does not agree on the SIGN, "
                     "because the official column sits ABOVE the band's top in %s (other industry inside "
                     "it) and inside the band in %s. Until the thermal intensity is measured rather than "
                     "transferred, this stream's change is not established in either direction"
                     % (lo, hi, official, START, END)))

    # ---- classification: the folded Pak Steel column ------------------------------------------
    steel = {r["reference_fiscal_year"]: float(r["value"]) for r in rows(VINTAGES)
             if r["sector_mapped"] == "pak_steel" and r["value"] and r["edition_year"] == "2020"}
    add("Cement-sector coal", "industry", "classification: the Pak Steel column", "note",
        evidence="data/activity/industry/coal_by_sector_vintages.csv (Compendium 2020 Table A-45)",
        reading=("the Supplement's 'Cement' column is the primary publication's 'Cement/Other Industry' "
                 "PLUS Pak Steel's imported coal/coke, which the Supplement stops printing separately "
                 "(FY2013-14 110 kt, FY2014-15 385 kt). Pak Steel is %s in every reported year, so no "
                 "booked value carries it - but the label does, and 'Cement' has never meant cement alone"
                 % ("zero" if all(v == 0 for k, v in steel.items() if k >= "2015-16") else "NOT zero")))

    # ---- calculation assumption: one NCV for every industrial coal tonne ----------------------
    for stream, sector in (("Brick-kiln coal", "brick_kilns"), ("Cement-sector coal", "cement_other")):
        start_kt = prints[(START[2:], sector)][policy[(START[2:], "brick_kilns" if sector == "brick_kilns" else "cement")]["booked_estimate_id"]]
        end_kt = prints[(END[2:], sector)][policy[(END[2:], "brick_kilns" if sector == "brick_kilns" else "cement")]["booked_estimate_id"]]
        lo, hi = 11.9, 27.0            # IPCC 2006 Vol 2 Table 1.2: lignite .. the top of other bituminous
        per_kt = (94600.0 + 10.0 * 28.0 + 1.5 * 265.0) / 1e9
        add(stream, "industry", "calculation assumption: one NCV for every industrial coal tonne", "bound",
            low=(end_kt - start_kt) * lo * per_kt, high=(end_kt - start_kt) * hi * per_kt,
            effect=None,
            evidence="IPCC 2006 Vol 2 Table 1.2 (lignite 11.9 .. other bituminous 25.8 TJ/Gg); the engine uses 25.8 throughout",
            reading=("the tonnage is converted at one calorific value for the whole window although the "
                     "domestic/imported mix changed (the Thar ramp is lignite). The change in this stream "
                     "is therefore known only to within the origin band printed here; the sign is unaffected"))

    # ---- coverage: what is not in the series at all -------------------------------------------
    for r in rows(CAPTIVE):
        state, fuel = r["status"].strip(), r["fuel_class"].strip()
        if state in ("reference", "estimated_elsewhere", "excluded_nothing_burns") or not fuel:
            continue
        lo, hi = r["bracket_low_Mt"], r["bracket_high_Mt"]
        add("captive %s" % fuel, "industry", "coverage: outside the priced series", "bound",
            low=float(lo) if lo else None, high=float(hi) if hi else None,
            evidence="outputs/industry_captive_screening_2024.csv (%s; %s MW, %s plants)"
                     % (state, r["capacity_MW"], r["plants"]),
            reading=(("a register-sized band, reference-year only: it has no nine-year series, so it "
                      "bounds the LEVEL and says nothing about the change" if lo else
                      "typed absent with its reason; no band is claimed") +
                     ". Screened mass sits beside the total, never inside it"))
    add("1.A.2 coverage", "industry", "coverage: what a band cannot do", "note",
        evidence="outputs/pakemis_completeness_mass.csv; outputs/industry_captive_screening_2024.csv",
        reading=("every coverage band above is a reference-year screening. None of them back-casts to "
                 "%s, so none can be added to or subtracted from a CHANGE: a category that enters only "
                 "at the end of the window manufactures growth, which is exactly the move the boundary "
                 "rule forbids" % START))
    return out


HEADER = """\
# WHERE THE 1.A.2 DECLINE COMES FROM (rc53 Wave A3). One row per (stream, channel). kind=booked rows
# sum to exactly the published change; kind=counterfactual says what the change would have been under
# a different defensible choice and is NEVER added to it; kind=bound is a quantity the series does not
# contain, carried as a band; kind=note carries no arithmetic. Mt CO2e AR5, FY2015-16 -> FY2023-24.
# Generated by scripts/build_industrial_change_attribution.py.
"""


def main():
    out = build()
    with open(OUT, "w", newline="", encoding="utf-8") as h:
        h.write(HEADER)
        w = csv.DictWriter(h, fieldnames=list(FIELDS), lineterminator="\n")
        w.writeheader()
        w.writerows(out)
    booked = sum(float(r["change_Mt"]) for r in out if r["kind"] == "booked")
    print("industrial change attribution -> %s (%d rows)" % (os.path.relpath(OUT, ROOT), len(out)))
    print("  booked 1.A.2 change (both modules): %+.3f Mt" % booked)
    for r in out:
        if r["kind"] in ("counterfactual",):
            print("  %-46s %-44s effect %+8s Mt" % (r["stream"][:46], r["channel"][:44], r["effect_on_change_Mt"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
