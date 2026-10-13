"""Brick-kiln coal: the bounded alternatives, per fiscal year - decision-rule row 3, NO manufactured central.

WHAT THE OFFICIAL VALUE IS. HDIP's own footnote to its coal-by-sector table (PBS Compendium on
Environment Statistics, Table A-45; data/activity/industry/coal_by_sector_pey_compendium.csv):
"* Estimated by deducting other uses of indigenous coal from the total production." The brick-kiln
column is a RESIDUAL of domestic production by construction: every tonne of indigenous coal the
other columns book (power first) is a tonne the brick column loses. That is why the HDIP-NEPRA
power residual flips sign in exactly the brick-spike years (coal balance, H2) and why recomputing
the residual from the same inputs can never be a correction.

THE ALTERNATIVES (each labelled, none preferred):
  (A) official   the HDIP value as published (Finance Division Supplement T14.1(4)), preserved;
  (B) band       the joint non-power band from the coal balance minus the cement kiln-coal band
                 (the bridge's brick row): low..high in kt, where a NEPRA lane exists (FY2019-20 on);
  (C) intensity  a SENSITIVITY, not an estimate: fired-brick output is held for ONE year only -
                 CCAC's fact sheet gives 82.5 billion bricks (2018; data/raw/brick_kilns/
                 ccac_fact_sheet_brick_sector_pakistan.pdf) - so the check runs the other way:
                 the coal per brick the official tonnage IMPLIES at constant 2018 output, against
                 the MEASURED Pakistani intensity (155 g zig-zag .. 184 g FCBTK, Hasnain et al.
                 2026, 60 kilns in Faisalabad). The 70-100 g band carried here until rc52 appears in
                 NO held document and is retired.
                 A physical firing needs tens of grams of coal per brick; an implied 14 g/brick
                 says the tonnage is not the sector's firing. BUT THE DENOMINATOR IS ITSELF THE
                 DISPUTED QUANTITY: CCAC's 82.5 billion bricks is about four times the output the
                 counted Punjab fleet implies, so the ratio is biased downward and is evidence about
                 the PAIR (tonnage, brick count), never about the tonnage alone. Printed as the
                 directional plausibility reading it is; no multiplier is formed from it.
The Compendium's own vintage of the official value (where it prints the year) is carried beside
the Supplement's, as the inter-edition comparison.

Reads:  outputs/pakemis_industrial_coal_bridge.csv, outputs/pakemis_coal_balance.csv,
        data/activity/industry/coal_by_consumer.csv, data/activity/industry/coal_by_sector_pey_compendium.csv
Writes: outputs/pakemis_brick_coal_alternatives.csv
"""
import csv
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from pkinv.assets import asset_path

from pkinv.paths import DATA, OUTPUTS  # noqa: E402

BRIDGE = asset_path(OUTPUTS, "pakemis_industrial_coal_bridge.csv")
BALANCE = asset_path(OUTPUTS, "pakemis_coal_balance.csv")
CONSUMERS = asset_path(DATA, "activity", "industry", "coal_by_consumer.csv")
COMPENDIUM = asset_path(DATA, "activity", "industry", "coal_by_sector_pey_compendium.csv")
OUT = asset_path(OUTPUTS, "pakemis_brick_coal_alternatives.csv")

# CCAC, "Fact sheet: brick sector in Pakistan" (2018 figures, from an APBKOA interview): the ONE
# fired-brick output held - the DENOMINATOR of the implied-intensity check, and the reason that
# check is a plausibility reading and not an estimate. It is a single national figure applied to
# every year because no annual brick production series exists.
CCAC_BRICKS_2018 = 82.5e9
CCAC_BRICKS_BASIS = ("CCAC/ICIMOD fact sheet, 2018, from an APBKOA interview - a single national "
                     "estimate, applied CONSTANT to every year because no annual series is held")
CCAC_COAL_ESTIMATE_MT = 13.0                                       # CCAC's own "estimated", 70% coal / 30% biomass assumption
# THE INTENSITY BAND IS NOW MEASURED, AND PAKISTANI (rc53 Wave D). Until rc52 this pair was 70-100
# g/brick attributed to "the same programme" - a figure that appears NOWHERE in the held fact sheet,
# which prints only aggregate tonnes. The replacement is measured: Hasnain et al. 2026 (Int. J.
# Analytical Chemistry), 60 kilns in Faisalabad, 2023 - 4,600 kg of coal against 25,000 bricks a day
# for FCBTK (184 g/brick) and 3,250 against 21,000 for zig-zag (155 g/brick). It is corroborated by
# the fact sheet's OWN implied figure (13 Mt / 82.5e9 = 158 g/brick) and by the World Bank's
# comparative specific energies (1.3 MJ/kg fired brick x 3 kg / ~20 MJ/kg coal = about 195 g).
# data/activity/industry/brick_kiln_activity_evidence.csv carries each with its page.
MEASURED_G_PER_BRICK_LOW, MEASURED_G_PER_BRICK_HIGH = 154.8, 184.0   # zig-zag .. FCBTK, Faisalabad 2023
CCAC_IMPLIED_G_PER_BRICK = CCAC_COAL_ESTIMATE_MT * 1e12 / CCAC_BRICKS_2018
FOOTNOTE = "* Estimated by deducting other uses of indigenous coal from the total production."

FIELDS = ("fiscal_year", "official_kt", "official_edition", "compendium_2020_kt", "vintage_difference_kt",
          "what_the_official_value_is",
          "band_low_kt", "band_high_kt", "band_basis",
          "domestic_non_thar_ceiling_kt", "official_minus_ceiling_kt", "ceiling_reading",
          "implied_g_per_brick_at_2018_output", "intensity_reading",
          "constant_output_low_kt", "constant_output_high_kt", "ccac_own_estimate_kt",
          "preferred_estimate", "decision_rule_row", "note")
HEADER = """\
# BRICK-KILN COAL - THE BOUNDED ALTERNATIVES, per fiscal year (decision-rule row 3: no preferred estimate).
# official_kt = HDIP as the Finance Division Supplement prints it (preserved); compendium_2020_kt = the same
# series as the PBS Compendium 2020 reprints it (an earlier vintage where the year is printed).
# what_the_official_value_is = HDIP's OWN footnote: the brick column is a RESIDUAL of domestic production.
# band_* = the joint non-power band minus the cement kiln-coal band (the bridge), where a NEPRA lane exists.
# implied_g_per_brick_at_2018_output = official coal / CCAC's 82.5 billion bricks (2018) - a SENSITIVITY: brick
# output is held for one year only; constant_output_* = the MEASURED 155..184 g/brick x that output.
# domestic_non_thar_ceiling_kt = (D) all coal mined minus NEPRA's Thar burn (the PBS by-province lane): the most
# DOMESTIC coal kilns could have burned under HDIP's own definition; official_minus_ceiling_kt > 0 means the official
# residual is not domestic coal. preferred_estimate is EMPTY in every row by design. scripts/build_brick_coal_alternatives.py
"""


def _rows(path):
    from pkinv.activity.store import read_rows as canonical_rows
    return canonical_rows(path, comments=True)


def build():
    bridge = {r["fiscal_year"]: r for r in _rows(BRIDGE) if r["component"].startswith("1.A.2 brick")}
    balance = {r["fiscal_year"]: r for r in _rows(BALANCE)}
    official = {}
    for r in _rows(CONSUMERS):
        if r["consumer"] == "brick_kilns" and r["revision_status"] in ("final", "provisional") and r["coal_kt"]:
            official[r["fiscal_year"]] = (float(r["coal_kt"]), r.get("edition_provenance", ""))
    comp = {r["fiscal_year"].replace("FY", ""): float(r["brick_kiln_t"]) / 1000.0
            for r in _rows(COMPENDIUM) if r["compendium_edition"] == "2020"}
    out = []
    for fy in sorted(bridge):
        b = bridge[fy]
        off_kt, edition = official.get(fy, (None, ""))
        if off_kt is None:
            continue
        g = off_kt * 1e6 * 1e3 / CCAC_BRICKS_2018          # kt -> g: x1e9; / bricks
        # THE DENOMINATOR IS THE DISPUTED QUANTITY, SO THIS READING IS DIRECTIONAL ONLY. CCAC's
        # 82.5 billion bricks is about four times the output the counted Punjab fleet implies
        # (pakemis_brick_activity_reconstruction.csv), so dividing by it biases the implied
        # intensity DOWNWARD in every year. A figure below the measured intensity is therefore
        # evidence about the pair (tonnage, brick count) and not about the tonnage alone - which is
        # why this stays a plausibility reading and no multiplier is ever formed from it.
        bias = " (the 2018 brick count is ~4x the counted fleet's output, so this ratio is biased low)"
        if g < MEASURED_G_PER_BRICK_LOW * 0.25:
            reading = ("far below the measured Pakistani intensity (%.0f-%.0f g/brick): not this sector's "
                       "firing on any reading of the pair" % (MEASURED_G_PER_BRICK_LOW, MEASURED_G_PER_BRICK_HIGH)) + bias
        elif g < MEASURED_G_PER_BRICK_LOW:
            reading = ("below the measured Pakistani intensity (%.0f-%.0f g/brick)"
                       % (MEASURED_G_PER_BRICK_LOW, MEASURED_G_PER_BRICK_HIGH)) + bias
        elif g <= MEASURED_G_PER_BRICK_HIGH:
            reading = ("inside the measured Pakistani range (%.0f-%.0f g/brick)"
                       % (MEASURED_G_PER_BRICK_LOW, MEASURED_G_PER_BRICK_HIGH))
        else:
            reading = ("above the measured FCBTK intensity (%.0f g/brick)" % MEASURED_G_PER_BRICK_HIGH)
        c_kt = comp.get(fy)
        bal = balance.get(fy, {})
        ceiling = bal.get("domestic_non_thar_coal_kt", "")
        gap = bal.get("hdip_brick_minus_domestic_non_thar_kt", "")
        if gap:
            ceiling_reading = ("official EXCEEDS the domestic ceiling by %s kt: not domestic coal under HDIP's own definition" % gap
                               if float(gap) > 0 else "official within the domestic ceiling (%s kt headroom)" % ("%.0f" % -float(gap)))
        else:
            ceiling_reading = "no NEPRA Thar-burn lane this year"
        out.append({
            "fiscal_year": fy, "official_kt": "%.0f" % off_kt, "official_edition": edition,
            "compendium_2020_kt": ("%.1f" % c_kt) if c_kt is not None else "",
            "vintage_difference_kt": ("%.1f" % (off_kt - c_kt)) if c_kt is not None else "",
            "what_the_official_value_is": "HDIP footnote (Compendium Table A-45): %s A RESIDUAL of domestic production by construction." % FOOTNOTE,
            "band_low_kt": b["activity_low_kt"], "band_high_kt": b["activity_high_kt"],
            "band_basis": b["activity_basis"],
            "domestic_non_thar_ceiling_kt": ceiling, "official_minus_ceiling_kt": gap, "ceiling_reading": ceiling_reading,
            "implied_g_per_brick_at_2018_output": "%.1f" % g, "intensity_reading": reading,
            "constant_output_low_kt": "%.0f" % (MEASURED_G_PER_BRICK_LOW * CCAC_BRICKS_2018 / 1e9),
            "constant_output_high_kt": "%.0f" % (MEASURED_G_PER_BRICK_HIGH * CCAC_BRICKS_2018 / 1e9),
            "ccac_own_estimate_kt": "%.0f" % (CCAC_COAL_ESTIMATE_MT * 1000),
            "preferred_estimate": "",
            "decision_rule_row": "3 (bounded alternatives; no central)",
            "note": ("(A) official preserved; (B) joint band, cement kiln-coal band removed; (C) intensity at "
                     "CONSTANT 2018 output is a sensitivity - fired-brick production per year, coal per brick by "
                     "kiln type and operating days are not held; FY2020-21 is not presumed the anchor; (D) the "
                     "domestic ceiling from the PBS by-province lane caps what HDIP's residual can be as domestic coal"),
        })
    return out


def main():
    rows = build()
    with open(OUT, "w", newline="", encoding="utf-8") as h:
        h.write(HEADER)
        w = csv.DictWriter(h, fieldnames=list(FIELDS), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print("brick coal alternatives -> %s (%d years)" % (os.path.relpath(OUT), len(rows)))
    for r in rows:
        print("  %s official %6s kt  band %5s..%5s  ceiling %5s (%5s)  implied %5s g/brick  %s" % (
            r["fiscal_year"], r["official_kt"], r["band_low_kt"] or "-", r["band_high_kt"] or "-",
            r["domestic_non_thar_ceiling_kt"] or "-", r["official_minus_ceiling_kt"] or "-",
            r["implied_g_per_brick_at_2018_output"], r["intensity_reading"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
