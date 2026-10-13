#!/usr/bin/env python3
"""WAVE 1, OUTPUT 1 OF THE INDUSTRIAL-COAL RECONSTRUCTION: the source-reconciliation
table - one row per fiscal year and HDIP consumer, carrying the official value, its
edition and ACTUAL reporting period, the category's scope as three publications print
it, the independent evidence held against it, and the proposed treatment under the
decision rule. coal_by_consumer.csv stays the untouched original-source record.

THE DIAGNOSIS THIS TABLE HOLDS OPEN (2026-09-10). The reference's Industry (1.A.2)
series falls -11.69 Mt over FY2015-16 -> FY2023-24, driven by HDIP's brick-kiln coal
(8,678 -> 1,129 kt) and "Cement" coal (10,184 -> 4,391 kt). The engine reproduces the
official table exactly - which closes the TRANSCRIPTION question and not the
inventory-QUALITY one. Working diagnosis: a material industrial-coal time-series
inconsistency requiring independent reconciliation; the magnitude and direction of
any correction remain to be established. Nothing here moves the reference.

THE DECISION RULE (applied per row in `decision_rule_row`):
  1  wrong unit / incomplete reporting period / transcription error / superseded value
     -> correct directly, preserving the original, documenting the change
  2  correctly transcribed, but independent production + fuel evidence supports a
     better estimate -> publish a reconstructed estimate; consider for the new reference
  3  independent evidence too weak to select a preferred estimate -> publish BOUNDED
     alternatives; never manufacture a precise corrected central

WHAT THE HELD EVIDENCE SAYS, ROW BY ROW:
  * POWER: the one consumer with an independently METERED lane - NEPRA's named-station
    coal (data/activity/power/plant_fuel_ledger.csv, 8 of 8 commissioned coal IPPs in
    FY2023-24; Jamshoro U5 pre-COD; FFBL Power ~118 MW is the one small unnamed unit).
    HDIP's power column equals domestic PRODUCTION (Table 14.3) to within 63 kt in
    FY2023-24, 15 kt in FY2020-21 and 480 kt in FY2022-23 - and HDIP's own narrative
    (Economic Survey 2025-26 ch.14) states the rule: Thar coal to the Thar plants, other
    coalfields' coal to brick kilns, imports to power and industry. The HDIP-NEPRA
    residual FLIPS SIGN across the window (outputs/industry_coal_reconciliation.csv):
    NEPRA above HDIP by 1,427 / 3,896 kt in FY2019-20 / FY2020-21 (the brick-spike
    years), HDIP above NEPRA by 3,320 kt in FY2023-24 (the brick-collapse year).
    Decision-rule row 2 CANDIDATE - replacing an estimated allocation with a metered
    quantity is not "reducing power to make room"; but the delivered-vs-burned STOCK
    confound is carried explicitly and resolves the residual to a band, not a point.
  * BRICK KILNS: no fired-brick production, no coal-per-brick, no operating days are
    held (kiln COUNTS only: 10,590 census / 11,272 detections / 7,393 Punjab CMI
    establishments). Row 3 - bounded alternatives until B and I are acquired.
  * CEMENT / OTHERS: the column is "Cement" in the Supplement, "Cement/Others" in the
    Survey (2025-26 Table 14.10), "Cement/Other Industry" in the PEY - other industrial
    coal may sit inside it unsplit. Clinker is held for nine years but on a SPLICED
    basis (fraction 0.75 for eight years, census FY2023-24), and no plant discloses
    coal tonnage or kiln heat. Row 3 now; row 2 once the census-anchored clinker series
    and a heat/coal-share bracket exist (Wave 2).
  * FY2023-24 SUPPLY is publisher-flagged PARTIAL (Balochistan production to March 2024;
    Punjab+Sindh production to February 2024; imports to January 2024). Row 1 AUDIT -
    coverage to be established, never multiplied up mechanically.

Reads:  data/activity/industry/coal_by_consumer.csv, coal_supply.csv,
        data/activity/power/plant_fuel_ledger.csv, outputs/industry_coal_reconciliation.csv
Writes: outputs/pakemis_coal_source_reconciliation.csv
Usage:  python3 scripts/build_coal_source_reconciliation.py [--check]
"""
import csv
import io
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from pkinv.assets import asset_path
from pkinv.paths import DATA, OUTPUTS  # noqa: E402

CONSUMERS = asset_path(DATA, "activity", "industry", "coal_by_consumer.csv")
SUPPLY = asset_path(DATA, "activity", "industry", "coal_supply.csv")
LEDGER = asset_path(DATA, "activity", "power", "plant_fuel_ledger.csv")
RECON = asset_path(OUTPUTS, "industry_coal_reconciliation.csv")
OUT = asset_path(OUTPUTS, "pakemis_coal_source_reconciliation.csv")

YEARS = ["2015-16", "2016-17", "2017-18", "2018-19", "2019-20", "2020-21", "2021-22",
         "2022-23", "2023-24", "2024-25"]
FIELDS = ("fiscal_year", "consumer", "official_kt", "edition", "revision_status",
          "reporting_period", "category_scope", "independent_evidence", "independent_kt",
          "proposed_low_kt", "proposed_high_kt", "proposed_basis", "decision_rule_row",
          "reason")

SCOPE = {
    "power": "HDIP allocation rule (Survey 2025-26 ch.14): Thar coal -> Thar plants; imports -> power "
             "and industry. HDIP power ~= domestic production by construction in FY2020-21, FY2022-23, "
             "FY2023-24 (H1); FY2021-22 breaks the rule",
    "brick_kilns": "HDIP's OWN footnote (PBS Compendium on Environment Statistics Table A-45, reprinting the PEY): "
                   "'* Estimated by deducting other uses of indigenous coal from the total production' - a RESIDUAL "
                   "of domestic production BY CONSTRUCTION, not a measurement; the HDIP-NEPRA power residual flips "
                   "sign in exactly the brick-spike years (H2) because an over-booked power column IS an "
                   "under-booked brick column",
    "cement": "printed 'Cement' (Supplement T14.1), 'Cement/Others' (Survey 2025-26 T14.10), "
              "'Cement/Other Industry' (PEY T4.4): other industrial coal may sit inside, unsplit",
    "household": "printed 'Household'; near-zero in every year",
}
FY24_PARTIAL = ("supply-side PARTIAL per publisher: Balochistan production upto Mar 2024 (T14.3); "
                "Punjab+Sindh production till Feb 2024, imports up to Jan 2024 (Survey 2025-26 fn #)")


def _rows(path):
    from pkinv.activity.store import read_rows as canonical_rows
    return canonical_rows(path, comments=True)


def build():
    official = defaultdict(dict)
    for r in _rows(CONSUMERS):
        if r["revision_status"] in ("final", "provisional"):
            official[r["fiscal_year"]][r["consumer"]] = r
    supply = {r["fiscal_year"]: r for r in _rows(SUPPLY)
              if r["period_coverage"] == "full_year" and r["revision_status"] != "superseded_provisional"}
    recon = {r["fiscal_year"]: r for r in _rows(RECON)}
    # NEPRA metered power coal by fiscal START year, split by origin
    nepra = defaultdict(lambda: defaultdict(float))
    plants = defaultdict(set)
    for r in _rows(LEDGER):
        if r["fuel"].lower() == "coal" and r["quantity_unit"].strip() == "000 t":
            fy = "%s-%02d" % (r["fiscal_year"], (int(r["fiscal_year"]) + 1) % 100)
            nepra[fy][r["fuel_origin"] or "unknown"] += float(r["quantity"])
            nepra[fy]["total"] += float(r["quantity"])
            plants[fy].add(r["plant"])

    out = []
    for fy in YEARS:
        off = official.get(fy, {})
        sup = supply.get(fy)
        imports = float(sup["coal_imports_kt"]) if sup and sup["coal_imports_kt"] else None
        production = float(sup["coal_production_kt_petroleum_division"]) if sup else None
        total_supply = (imports + production) if imports is not None and production is not None else None
        rec = recon.get(fy, {})
        edition = ("Supplement 2024-25 (P)" if fy == "2024-25" else "Supplement 2024-25 final")
        period = FY24_PARTIAL if fy == "2023-24" else "full fiscal year (July-June)"

        # POWER
        p = off.get("power")
        p_kt = float(p["coal_kt"]) if p and p["coal_kt"] else None
        n_tot = nepra[fy]["total"] if fy in nepra else None
        if n_tot is not None:
            thar = nepra[fy].get("Thar lignite", 0.0)
            imp = nepra[fy].get("imported", 0.0)
            unk = nepra[fy].get("unknown", 0.0)
            ev = ("NEPRA named-station coal %s kt (%d plants: Thar lignite %.0f, imported %.0f, origin "
                  "unknown %.0f); HDIP-NEPRA residual %s kt (%s)"
                  % (("%.1f" % n_tot), len(plants[fy]), thar, imp, unk,
                     rec.get("unmatched_kt", ""), rec.get("unmatched_direction", "")))
            low = high = "%.1f" % n_tot
            basis = ("NEPRA metered burn as the anchor; the HDIP-NEPRA residual is NOT moved to industry - "
                     "it is a band whose candidates are plant stock change (delivered vs burned), the "
                     "~118 MW FFBL Power unit, and misallocation; resolved in Wave 4")
            rule = "2 candidate (independently metered quantity)"
            reason = ("HDIP power is an '** Estimated' allocation equal to domestic production by construction "
                      "(power - production = %s kt); NEPRA is metered per station"
                      % (("%.0f" % (p_kt - production)) if p_kt is not None and production is not None else "n/a"))
        else:
            ev = "no NEPRA plant-fuel lane this year (ledger covers FY2019-20..FY2023-24)"
            low = high = ""
            basis = "none held"
            rule = "3 (no independent lane)"
            reason = ("HDIP power - domestic production = %s kt"
                      % (("%.0f" % (p_kt - production)) if p_kt is not None and production is not None else "n/a"))
        out.append({"fiscal_year": fy, "consumer": "power", "official_kt": p["coal_kt"] if p else "",
                    "edition": edition, "revision_status": p["revision_status"] if p else "",
                    "reporting_period": period, "category_scope": SCOPE["power"],
                    "independent_evidence": ev, "independent_kt": ("%.1f" % n_tot) if n_tot is not None else "",
                    "proposed_low_kt": low, "proposed_high_kt": high, "proposed_basis": basis,
                    "decision_rule_row": rule, "reason": reason})

        # NON-POWER pair: brick + cement/others (+ household) - bounded jointly
        b = off.get("brick_kilns")
        c = off.get("cement")
        hh = off.get("household")
        b_kt = float(b["coal_kt"]) if b and b["coal_kt"] else 0.0
        c_kt = float(c["coal_kt"]) if c and c["coal_kt"] else 0.0
        hh_kt = float(hh["coal_kt"]) if hh and hh["coal_kt"] else 0.0
        hdip_nonpower = b_kt + c_kt + hh_kt
        nepra_nonpower = (total_supply - n_tot - hh_kt) if (total_supply is not None and n_tot is not None) else None
        pair_low = min(hdip_nonpower - hh_kt, nepra_nonpower) if nepra_nonpower is not None else ""
        pair_high = max(hdip_nonpower - hh_kt, nepra_nonpower) if nepra_nonpower is not None else ""
        h1 = ("non-power - imports = %s kt" % ("%.0f" % (hdip_nonpower - imports))) if imports is not None else "n/a"
        for consumer, row, kt in (("brick_kilns", b, b_kt), ("cement", c, c_kt)):
            ev = ("no activity-grain evidence held (%s); joint brick+cement/others band from the supply "
                  "identity: HDIP non-power %.0f kt vs supply - NEPRA power - household = %s kt; H1: %s"
                  % ("no fired-brick production series; the one output anchor is CCAC's 82.5 billion bricks (2018) "
                     "and 70-100 g coal/brick by kiln type - the implied-intensity sensitivity is in "
                     "pakemis_brick_coal_alternatives.csv" if consumer == "brick_kilns"
                     else "clinker held on a spliced 0.75/census basis; no plant discloses coal or kiln heat",
                     hdip_nonpower - hh_kt,
                     ("%.0f" % nepra_nonpower) if nepra_nonpower is not None else "n/a", h1))
            out.append({"fiscal_year": fy, "consumer": consumer, "official_kt": row["coal_kt"] if row else "",
                        "edition": edition, "revision_status": row["revision_status"] if row else "",
                        "reporting_period": period, "category_scope": SCOPE[consumer],
                        "independent_evidence": ev, "independent_kt": "",
                        "proposed_low_kt": ("%.0f" % pair_low) if pair_low != "" else "",
                        "proposed_high_kt": ("%.0f" % pair_high) if pair_high != "" else "",
                        "proposed_basis": ("JOINT brick+cement/others band (not this consumer alone): low = HDIP "
                                           "as published, high = NEPRA-anchored non-power residual; the split "
                                           "between the two waits on Wave 2 (clinker-based cement) and Wave 3 "
                                           "(brick production x intensity)") if pair_low != "" else "none held",
                        "decision_rule_row": "3 (bounded; no preferred estimate)",
                        "reason": ("individual reconstruction not yet supportable; the pair is bounded, the "
                                   "official value preserved as one labelled alternative")})
        out.append({"fiscal_year": fy, "consumer": "household", "official_kt": hh["coal_kt"] if hh else "",
                    "edition": edition, "revision_status": hh["revision_status"] if hh else "",
                    "reporting_period": period, "category_scope": SCOPE["household"],
                    "independent_evidence": "none; immaterial (<= 2 kt)", "independent_kt": "",
                    "proposed_low_kt": hh["coal_kt"] if hh else "", "proposed_high_kt": hh["coal_kt"] if hh else "",
                    "proposed_basis": "as published", "decision_rule_row": "n/a (immaterial)", "reason": ""})
    return out


BANNER = (
    "# Industrial coal - SOURCE RECONCILIATION (Wave 1, Output 1): one row per fiscal year x HDIP consumer.",
    "# official_kt is coal_by_consumer.csv as published (the untouched record); category_scope is the label",
    "# as THREE publications print it; independent_evidence is what is held against it; proposed_* is a BAND",
    "# only where held evidence supports one (decision_rule_row 3 = bounded, 2 = reconstructed candidate,",
    "# 1 = direct correction after audit). Nothing here enters any total. scripts/build_coal_source_reconciliation.py",
)


def render(rows):
    buf = io.StringIO()
    for b in BANNER:
        buf.write(b + "\n")
    w = csv.DictWriter(buf, fieldnames=list(FIELDS), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    text = render(build())
    if "--check" in argv:
        held = open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else ""
        print("coal source reconciliation: %s" % ("byte-identical" if held == text else "DIFFERS"))
        return 0 if held == text else 1
    with open(OUT, "w", encoding="utf-8", newline="") as h:
        h.write(text)
    print("coal source reconciliation -> %s" % OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
