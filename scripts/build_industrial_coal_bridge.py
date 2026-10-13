#!/usr/bin/env python3
"""WAVE 4, OUTPUT 3 OF THE INDUSTRIAL-COAL RECONSTRUCTION: the REPLACEMENT BRIDGE and the
reference decision, per fiscal year - what the official series books, what each held
line of evidence would revise, and what the release therefore does with it.

    official-series emissions
      -> activity revisions       (clinker basis; the power seam; the cement kiln-coal band;
                                   the brick + others band)
      -> fuel-quality revisions   (the NCV-by-origin band the engine's single bucket hides)
      -> boundary / overlap       (the cement column's other-industry share; the screening
                                   is a replacement comparator, never added; captive stays
                                   in power)
      -> reconstructed            (a CENTRAL only where the decision rule's row 2 is met;
                                   otherwise a BAND, and the official value stays booked)

and the identity the waterfall obeys:  dE_new = dE_official + dE_end - dE_start.

THE DECISION RULE, APPLIED (2026-09-11):
  * CLINKER BASIS (2.A.1 and the cement kiln-coal activity)  ->  PROMOTE (row 2). The
    16-company census fixes FY2023-24 and implies a clinker-in-cement fraction f* = 0.965,
    derived here from held data; GEM's per-plant substitution (30 of 32 at 0-5 percent)
    corroborates it and IPCC's all-portland 0.95 brackets it. Applied to the eight earlier
    years it removes the +9,027 kt FY2022-23 -> FY2023-24 method break the 0.75 splice
    manufactured (to +109 kt) and raises 2.A.1 by +3.96..+5.57 Mt a year. The reference
    year is the census already, so the national pins do NOT move; the eight historical
    totals do. One clinker series serves process CO2 and the kiln-fuel term.
  * CEMENT KILN COAL  ->  BOUNDED (row 3). Production evidence exists (the clinker series);
    FUEL evidence does not: kiln heat, coal share and NCV are transferred bands, and zero
    of sixteen held company reports prints coal tonnage or kcal/kg. The band is published
    beside the official column; no central is manufactured.
  * THE "OTHERS" INSIDE THE CEMENT COLUMN  ->  BOUNDED (row 3). column - cement band is
    1.4-6.4 Mt of other-industry coal in FY2016-19 and FY2021-22 and ~0 (or under-booking)
    in FY2023-24; a retained stream in the bridge, not yet a booked point.
  * BRICK KILNS  ->  BOUNDED (row 3). No fired-brick production, coal-per-brick or operating
    days are held; the joint non-power band minus the cement band is the widest honest
    statement. Acquisition: PBS Compendium on Environment Statistics 2020 (production),
    intensity by FCBK vs zig-zag.
  * THE POWER SEAM  ->  BOUNDED (row 3, pending row 1 audit). HDIP's power column is not in
    the reference (grid coal rides NEPRA already); what it decides is the NON-POWER total.
    "supply - NEPRA burned" cannot separate non-Thar brick coal from Thar stockpile without
    by-field production, and FY2023-24 supply is publisher-flagged partial (imports to
    January 2024) - a coverage audit needs the monthly trade series, never a 12/7 multiplier.

The official series therefore stays booked for brick and cement coal in the reference; the
Industry (1.A.2) -11.69 Mt endpoint does not change in this release, and the label
"Industry: reported-fuel estimate" and its caveat stay until the acquisitions above land.
What changes is IPPU 2.A.1's eight back-years - and with them the national trend the
waterfall prints.

Reads:  outputs/pakemis_atomic_annual.csv (the official atoms), outputs/pakemis_coal_balance.csv,
        outputs/pakemis_cement_kiln_coal_reconstruction.csv, data/activity/industry/coal_by_consumer.csv
Writes: outputs/pakemis_industrial_coal_bridge.csv
Usage:  python3 scripts/build_industrial_coal_bridge.py [--check]
"""
import csv
import io
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from pkinv.assets import asset_path
from pkinv.paths import DATA, OUTPUTS  # noqa: E402

ATOMS = asset_path(OUTPUTS, "pakemis_atomic_annual.csv")
BALANCE = asset_path(OUTPUTS, "pakemis_coal_balance.csv")
CEMENT = asset_path(OUTPUTS, "pakemis_cement_kiln_coal_reconstruction.csv")
CONSUMERS = asset_path(DATA, "activity", "industry", "coal_by_consumer.csv")
OUT = asset_path(OUTPUTS, "pakemis_industrial_coal_bridge.csv")

# the engine's single solid-fuel bucket (Other Bituminous Coal) and the IPCC origin band
NCV_ENGINE, NCV_LIGNITE, NCV_SUBBIT, NCV_OBC = 25.8, 11.9, 18.9, 25.8
CO2_KG_TJ = 94600.0
CLINKER_EF_T_PER_T = 0.52

FIELDS = (
    "fiscal_year", "component", "decision",
    "official_kt", "official_mt_co2e",
    "activity_low_kt", "activity_central_kt", "activity_high_kt", "activity_basis",
    "fuel_quality_note",
    "boundary_note",
    "reconstructed_low_mt", "reconstructed_central_mt", "reconstructed_high_mt",
    "delta_vs_official_low_mt", "delta_vs_official_high_mt",
    "reason",
)

BANNER = (
    "# Industrial coal - THE REPLACEMENT BRIDGE and reference decision (Wave 4, Output 3), per fiscal year x component:",
    "# official-series emissions -> activity revisions -> fuel-quality revisions -> boundary/overlap -> reconstructed.",
    "# decision = PROMOTE (row 2: the clinker basis) | BOUNDED (row 3: cement kiln coal, the others inside the cement",
    "# column, brick, the power seam) | PENDING_AUDIT (row 1: FY2023-24 partial supply). A reconstructed CENTRAL exists",
    "# only where row 2 is met; elsewhere the band is published and the official value stays booked. The national pins",
    "# do not move (FY2023-24 is the census); the eight historical 2.A.1 values do. scripts/build_industrial_coal_bridge.py",
)


def _rows(path):
    from pkinv.activity.store import read_rows as canonical_rows
    return canonical_rows(path, comments=True)


def f(x, nd=3):
    return "" if x in (None, "") else "%.*f" % (nd, float(x))


def kt_to_mt_co2(kt, ncv=NCV_ENGINE):
    return kt * ncv * CO2_KG_TJ / 1e9          # kt = Gg; Gg x TJ/Gg = TJ; TJ x kg/TJ / 1e9 = Mt


def build():
    # the official atoms: brick, cement coal (CO2e AR5, all gases) and 2.A.1 clinker per FY
    atoms = defaultdict(lambda: defaultdict(float))
    for r in _rows(ATOMS):
        if r.get("configuration_id", "REF_2023_24") != "REF_2023_24":
            continue
        fy = r["period_label"] if "period_label" in r else r.get("period_id", "")
        fy = fy.replace("FY", "")
        sub = r.get("subitem", "")
        v = r.get("co2e_Mt_AR5", "")
        if not v:
            continue
        if sub.startswith("Brick-kiln coal"):
            atoms[fy]["brick"] += float(v)
        elif sub.startswith("Cement-sector coal"):
            atoms[fy]["cement_coal"] += float(v)
        elif sub == "Clinker calcination CO2":
            atoms[fy]["clinker"] += float(v)
    bal = {r["fiscal_year"]: r for r in _rows(BALANCE)}
    cem = {r["fiscal_year"]: r for r in _rows(CEMENT)}
    hdip = defaultdict(dict)
    for r in _rows(CONSUMERS):
        if r["revision_status"] in ("final", "provisional"):
            hdip[r["fiscal_year"]][r["consumer"]] = float(r["coal_kt"]) if r["coal_kt"] else None

    out = []
    years = [fy for fy in sorted(cem) if fy in atoms]
    for fy in years:
        c, b, h = cem[fy], bal.get(fy, {}), hdip.get(fy, {})
        # --- 2.A.1 clinker basis: PROMOTE -------------------------------------------
        # Both ends of this row are computed from the clinker quantities, NEVER read from the atom
        # table: the atoms carry whatever basis the reference currently rides, so a builder that
        # read "official" from them booked the re-based value as official once rc50 landed and
        # added the delta a second time (FY2015-16 printed 17.779 -> 21.743; correct 13.815 ->
        # 17.779). The reconstructed end must EQUAL the reference atom after the re-base; the
        # test holds that identity, and the builder is now invariant to build order.
        k_off = float(c["clinker_kt_legacy_0p75"]) if not c["clinker_kt_census_actual"] else float(c["clinker_kt_census_actual"])
        k_new = float(c["clinker_kt_census_actual"]) if c["clinker_kt_census_actual"] else float(c["clinker_kt_census_anchored"])
        d_mt = (k_new - k_off) * CLINKER_EF_T_PER_T / 1000.0
        out.append({
            "fiscal_year": fy, "component": "2.A.1 clinker calcination CO2", "decision": "PROMOTE (row 2)" if d_mt else "unchanged (census year)",
            "official_kt": f(k_off, 0), "official_mt_co2e": f(k_off * CLINKER_EF_T_PER_T / 1000.0),
            "activity_low_kt": f(k_new, 0), "activity_central_kt": f(k_new, 0), "activity_high_kt": f(k_new, 0),
            "activity_basis": c["clinker_basis"] + "; f* = " + c["clinker_fraction_census_derived"],
            "fuel_quality_note": "n/a (process CO2)",
            "boundary_note": "one clinker series serves 2.A.1 and the kiln-fuel activity",
            "reconstructed_low_mt": f(k_new * CLINKER_EF_T_PER_T / 1000.0), "reconstructed_central_mt": f(k_new * CLINKER_EF_T_PER_T / 1000.0),
            "reconstructed_high_mt": f(k_new * CLINKER_EF_T_PER_T / 1000.0),
            "delta_vs_official_low_mt": f(d_mt), "delta_vs_official_high_mt": f(d_mt),
            "reason": ("census-derived fraction replaces the IPCC blended default 0.75 for the back-years; GEM 0-5 percent "
                       "substitution corroborates; removes the FY2022-23 -> FY2023-24 method break" if d_mt else
                       "the reference year is the audited census itself"),
        })
        # --- cement kiln coal: BOUNDED ---------------------------------------------
        off_c_kt = h.get("cement")
        lo, ce, hi = (float(c[k]) for k in ("coal_kt_low", "coal_kt_central", "coal_kt_high"))
        e_lo, e_ce, e_hi = (float(c[k]) for k in ("kiln_coal_co2_mt_low", "kiln_coal_co2_mt_central", "kiln_coal_co2_mt_high"))
        out.append({
            "fiscal_year": fy, "component": "1.A.2 cement kiln coal", "decision": "BOUNDED (row 3)",
            "official_kt": f(off_c_kt, 0), "official_mt_co2e": f(atoms[fy]["cement_coal"]),
            "activity_low_kt": f(lo, 0), "activity_central_kt": f(ce, 0), "activity_high_kt": f(hi, 0),
            "activity_basis": "K x H x s / NCV: H 3.0/3.4/3.8 GJ/t, s 0.85/0.95/1.0, NCV 24/25.8/27 - all TRANSFERRED",
            "fuel_quality_note": "imported bituminous around the engine's OBC 25.8; petcoke share unheld",
            "boundary_note": ("the 13.59 Mt screening is the s=1 H=3.4 member (replacement comparator, cement_kiln_fuel_in_scope "
                              "net +2.80), never added; residual vs the HDIP column: %s" % c["residual_reading"][:90]),
            "reconstructed_low_mt": f(e_lo), "reconstructed_central_mt": "", "reconstructed_high_mt": f(e_hi),
            "delta_vs_official_low_mt": f(e_lo - atoms[fy]["cement_coal"]), "delta_vs_official_high_mt": f(e_hi - atoms[fy]["cement_coal"]),
            "reason": "production evidence held, FUEL evidence not (zero of 16 company reports prints coal or kcal/kg); the official column stays booked",
        })
        # --- others inside the cement column: BOUNDED --------------------------------
        r_lo, r_hi = c["residual_kt_low"], c["residual_kt_high"]
        out.append({
            "fiscal_year": fy, "component": "1.A.2 other industrial coal (inside the HDIP cement column)", "decision": "BOUNDED (row 3)",
            "official_kt": "0 (unsplit inside 'Cement')", "official_mt_co2e": "0.000",
            "activity_low_kt": f(max(float(r_lo), 0.0), 0) if r_lo else "", "activity_central_kt": "", "activity_high_kt": f(max(float(r_hi), 0.0), 0) if r_hi else "",
            "activity_basis": "HDIP cement column minus the cement kiln-coal band; the column is 'Cement/Other Industry' in the PEY",
            "fuel_quality_note": "unknown origin; the engine's OBC bucket assumed",
            "boundary_note": "a RETAINED stream, not discarded; a negative residual means the column under-books cement itself",
            "reconstructed_low_mt": f(kt_to_mt_co2(max(float(r_lo), 0.0))) if r_lo else "", "reconstructed_central_mt": "",
            "reconstructed_high_mt": f(kt_to_mt_co2(max(float(r_hi), 0.0))) if r_hi else "",
            "delta_vs_official_low_mt": f(kt_to_mt_co2(max(float(r_lo), 0.0))) if r_lo else "", "delta_vs_official_high_mt": f(kt_to_mt_co2(max(float(r_hi), 0.0))) if r_hi else "",
            "reason": "the split cannot be booked as a point; steel/textile/chemical coal is inside the column by the primary label",
        })
        # --- brick + the power seam: BOUNDED ------------------------------------------
        off_b_kt = h.get("brick_kilns")
        np_hdip = b.get("hdip_nonpower_kt"); np_nepra = b.get("nepra_anchored_nonpower_kt")
        hh = float(b.get("hdip_household_kt") or 0.0)
        if np_nepra:
            joint_lo, joint_hi = sorted((float(np_hdip) - hh, float(np_nepra)))
            b_lo, b_hi = max(joint_lo - hi, 0.0), max(joint_hi - lo, 0.0)      # joint minus the cement band
            basis = ("joint non-power band (HDIP as published .. supply - NEPRA metered power - household) minus the "
                     "cement kiln-coal band; H2 residual %s kt" % b.get("power_residual_hdip_minus_nepra_kt", ""))
        else:
            b_lo = b_hi = None
            basis = "no NEPRA lane this year; no band beyond the official value"
        out.append({
            "fiscal_year": fy, "component": "1.A.2 brick-kiln coal (+ unsplit others)", "decision": "BOUNDED (row 3)",
            "official_kt": f(off_b_kt, 0), "official_mt_co2e": f(atoms[fy]["brick"]),
            "activity_low_kt": f(b_lo, 0), "activity_central_kt": "", "activity_high_kt": f(b_hi, 0),
            "activity_basis": basis,
            "fuel_quality_note": ("engine OBC 25.8 TJ/Gg; if the coal is non-Thar domestic (HDIP's own rule) the origin band "
                                  "sub-bituminous %.1f .. OBC %.1f applies - TJ per tonne, not tonnes, moves" % (NCV_SUBBIT, NCV_OBC)),
            "boundary_note": ("'supply - NEPRA burned' cannot separate non-Thar brick coal from Thar STOCKPILE (by-field production "
                              "not held); FY2023-24 supply publisher-partial (imports to Jan 2024) - row 1 audit pending the "
                              "monthly trade series" if fy == "2023-24" else
                              "'supply - NEPRA burned' cannot separate non-Thar brick coal from Thar STOCKPILE (by-field production not held)"),
            "reconstructed_low_mt": f(kt_to_mt_co2(b_lo, NCV_SUBBIT)) if b_lo is not None else "",
            "reconstructed_central_mt": "",
            "reconstructed_high_mt": f(kt_to_mt_co2(b_hi, NCV_OBC)) if b_hi is not None else "",
            "delta_vs_official_low_mt": f(kt_to_mt_co2(b_lo, NCV_SUBBIT) - atoms[fy]["brick"]) if b_lo is not None else "",
            "delta_vs_official_high_mt": f(kt_to_mt_co2(b_hi, NCV_OBC) - atoms[fy]["brick"]) if b_hi is not None else "",
            "reason": "no fired-brick production, coal-per-brick or operating days held (acquire PBS Compendium on Environment Statistics 2020; intensity by FCBK/zig-zag); the official value stays booked",
        })
    return out, years, atoms


def identity_lines(rows, years, atoms):
    """dE_new = dE_official + dE_end - dE_start, for the 1.A.2 solid streams, as a band."""
    first, last = years[0], years[-1]
    off = lambda fy: atoms[fy]["brick"] + atoms[fy]["cement_coal"]
    d_official = off(last) - off(first)
    def band(fy, which):
        tot = 0.0
        for r in rows:
            if r["fiscal_year"] == fy and r["component"].startswith("1.A.2") and r[which]:
                tot += float(r[which])
        return tot
    d_end_lo, d_end_hi = band(last, "delta_vs_official_low_mt"), band(last, "delta_vs_official_high_mt")
    d_start_lo, d_start_hi = band(first, "delta_vs_official_low_mt"), band(first, "delta_vs_official_high_mt")
    new_lo = d_official + d_end_lo - d_start_hi
    new_hi = d_official + d_end_hi - d_start_lo
    return [
        "# IDENTITY (1.A.2 solid streams, %s -> %s): dE_official = %+.2f Mt; dE_end in [%+.2f, %+.2f]; dE_start in [%+.2f, %+.2f];"
        % (first, last, d_official, d_end_lo, d_end_hi, d_start_lo, d_start_hi),
        "#   dE_new = dE_official + dE_end - dE_start  lies in [%+.2f, %+.2f] Mt - a BAND, because no row-2 central exists for the"
        % (new_lo, new_hi),
        "#   solid streams; the official %+.2f stays booked. The 2.A.1 PROMOTE moves the eight back-years by +%.2f Mt in total."
        % (d_official, sum(float(r["delta_vs_official_low_mt"]) for r in rows if r["component"].startswith("2.A.1") and r["fiscal_year"] != last)),
    ]


def render(rows, years, atoms):
    buf = io.StringIO()
    for b in BANNER + tuple(identity_lines(rows, years, atoms)):
        buf.write(b + "\n")
    w = csv.DictWriter(buf, fieldnames=list(FIELDS), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    rows, years, atoms = build()
    text = render(rows, years, atoms)
    if "--check" in argv:
        held = open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else ""
        print("industrial coal bridge: %s" % ("byte-identical" if held == text else "DIFFERS"))
        return 0 if held == text else 1
    with open(OUT, "w", encoding="utf-8", newline="") as h:
        h.write(text)
    print("industrial coal bridge -> %s (%d rows)" % (OUT, len(rows)))
    for line in identity_lines(rows, years, atoms):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
