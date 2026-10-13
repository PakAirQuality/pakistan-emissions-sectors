"""BRICK-KILN COAL FROM A KILN COUNT AND A MEASURED FUEL RATE - the first estimate of this stream
that does not read HDIP's own column (rc53 Wave D).

WHY IT IS NOT CIRCULAR. HDIP's brick column is a RESIDUAL of domestic coal production by the
publisher's own footnote, so reconstructing it from the same balance can only reproduce it. Every
input here is counted, surveyed or measured by somebody else:

    level          6.5 Mt/yr nationally - ICIMOD's own national statement (p.27), NOT this
                   release's scale-out of the Punjab survey (see the rc54 correction below)
    kilns          10,394 operating in Punjab, BKOAP's real-time census, November 2020
    fuel per kiln  328.2 t/year, ICIMOD's 440-kiln baseline survey, 2020 (144,430 t over the sample)
    intensity      184 g of coal per brick (FCBTK) and 155 g (zig-zag), MEASURED on 60 kilns in
                   Faisalabad in 2023 - 4,600 kg of coal against 25,000 bricks a day, and 3,250
                   against 21,000
    scale-out      the release's own kiln frame gives Punjab 0.8668 of national kiln weight

TWO INDEPENDENT LANES, AND THEY AGREE ON INTENSITY WHILE DISAGREEING ON SCALE. The measured
Pakistani intensity (155-184 g/brick) and the intensity implied by the CCAC fact sheet's own
national figures (13 Mt over 82.5 billion bricks = 158 g/brick) agree closely. The SCALES do not:
CCAC's 19,000 kilns and 13 Mt are about three times the ICIMOD census and survey scaled nationally.
So the intensity is the settled part of this evidence and the scale is not, which is why this
product prints a BAND and no central.

WHAT IT CANNOT DO. One surveyed year cannot make a nine-year series. A kiln census in 2020 and a
fuel measurement in 2023 bound a LEVEL; they do not measure the year-to-year path, and inventing
one by scaling the level on an untested indicator would be the manufactured-central move the
decision rule forbids. The nine-year column here is therefore the RATIO of the official series to
the independent level, printed per year - the question "does the official series behave like this
sector's firing?" answered arithmetically, with no value replaced.

Reads:  data/activity/industry/brick_kiln_activity_evidence.csv, data/province_shares.csv,
        data/activity/industry/coal_by_sector_vintages.csv, data/coal_booking_policy.csv
Writes: outputs/pakemis_brick_activity_reconstruction.csv
Nothing here enters any total; the official series stays booked.

MORE MEASURED INTENSITIES ARE PUBLISHED AND NOT HELD (2026-09-14). Sheikh et al., Pakistan Journal
of Science 76(3) 363-371 (2024, doi:10.57041/vol76iss03pp363-371, Crossref-confirmed) is reported to
carry batch observations for three coal-fired kilns - 231 t per 1.2 million bricks, 210 t per 1.2
million, and 264 t per 1.0 million, or 192.5, 175.0 and 264.0 g per brick. All three are ABOVE the
155-184 g pair this module uses, so they would widen the implied-output diagnostic rather than
settle it.

They are NOT ingested and nothing here uses them. The publisher's whole domain returns HTTP 500 -
checked at the article, the issue archive and the site root before logging a negative - so the
numbers reach this repository only through a third-party analysis, and
data/activity/industry/brick_kiln_activity_evidence.csv requires every row to cite a document this
repository holds (tests/test_brick_activity_reconstruction.py enforces it). That test is the reason
this paragraph is a comment and not four new evidence rows. The acquisition is logged blocked;
retry when the journal is back up.
"""
import csv
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from pkinv.assets import asset_path

from pkinv.paths import DATA, OUTPUTS, ROOT  # noqa: E402

EVIDENCE = asset_path(DATA, "activity", "industry", "brick_kiln_activity_evidence.csv")
SHARES = asset_path(DATA, "province_shares.csv")
VINTAGES = asset_path(DATA, "activity", "industry", "coal_by_sector_vintages.csv")
POLICY = asset_path(DATA, "coal_booking_policy.csv")
OUT = asset_path(OUTPUTS, "pakemis_brick_activity_reconstruction.csv")

PERIODS = ["%d-%02d" % (y, (y + 1) % 100) for y in range(2015, 2024)]
FIELDS = ("fiscal_year", "official_kt", "official_estimate_id",
          "independent_level_low_kt", "independent_level_central_kt", "independent_level_high_kt",
          "official_over_independent", "reading",
          "punjab_kilns", "punjab_share_of_national_kilns", "coal_per_kiln_t",
          "punjab_kt_surveyed", "kiln_frame_scale_out_kt", "scale_out_vs_source_national",
          "implied_bricks_per_kiln_million", "implied_national_bricks_billion",
          "intensity_g_per_brick_measured_low", "intensity_g_per_brick_measured_high",
          "basis", "note")
# THE INDEPENDENT LEVEL IS THE SOURCE'S OWN NATIONAL FIGURE (rc54). Until rc54 this product
# scaled ICIMOD's Punjab total up on the release's kiln frame and called the result the
# independent national level - 3.94 Mt - without reading the national number the same page
# prints: 6.5 Mt. That was a defect, not a judgement, and the scale-out is demoted to what it
# always was: a cross-check, which DISAGREES. The two imply different Punjab shares of national
# brick coal (the kiln frame 87 percent, the source's own pair 52 percent) and neither is
# corrected here.


def rows(path):
    from pkinv.activity.store import read_rows as canonical_rows
    return canonical_rows(path, comments=True)


def evidence():
    return {r["evidence_id"]: r for r in rows(EVIDENCE)}


def punjab_kiln_share():
    """Punjab's share of the national kiln frame, from the release's own allocation."""
    for r in rows(SHARES):
        if r["proxy"] == "brick_coal":
            return float(r["Punjab"])
    raise SystemExit("no brick_coal row in province_shares.csv")


def official():
    prints = {r["estimate_id"]: r for r in rows(VINTAGES)}
    out = {}
    for r in rows(POLICY):
        if r["consumer"] != "brick_kilns":
            continue
        p = prints[r["booked_estimate_id"]]
        out[r["reference_fiscal_year"]] = (float(p["value"]), p["estimate_id"])
    return out


def build():
    ev = evidence()
    share = punjab_kiln_share()
    kilns = float(ev["icimod_kilns_punjab_2020"]["value"])
    per_kiln = float(ev["icimod_coal_per_kiln_2020"]["value"])
    i_lo = float(ev["hasnain_intensity_zigzag_2023"]["value"])      # kg per 1,000 bricks
    i_hi = float(ev["hasnain_intensity_fcbtk_2023"]["value"])
    punjab_kt = kilns * per_kiln / 1000.0
    scaled_out_kt = punjab_kt / share                       # the kiln-frame cross-check
    national_kt = float(ev["icimod_coal_national_2020"]["value"]) * 1000.0
    lo, hi = national_kt, float(ev["ccac_coal_2018"]["value"]) * 1000.0
    # what the measured intensity says the surveyed fuel rate implies in bricks
    bricks_per_kiln = per_kiln * 1000.0 / (i_hi / 1000.0) / 1e6        # million bricks per kiln-year
    national_bricks = bricks_per_kiln * kilns / share / 1000.0          # billion
    off = official()
    out = []
    for fy in PERIODS:
        o_kt, o_id = off[fy]
        ratio = o_kt / national_kt
        if o_kt > hi:
            reading = ("ABOVE even the high end of the independent band (%.2f x the source's own "
                       "national figure): more coal than either independent reading of the sector"
                       % ratio)
        elif o_kt < lo * 0.5:
            reading = ("BELOW HALF the independent level (%.2f x the source's own national "
                       "figure): the official column is not this sector's firing on any held "
                       "reading of the sector" % ratio)
        elif o_kt < lo:
            reading = "below the independent level (%.2f x the source's own national figure)" % ratio
        else:
            reading = "inside the independent band (%.2f x the source's own national figure)" % ratio
        out.append({
            "fiscal_year": fy, "official_kt": "%.1f" % o_kt, "official_estimate_id": o_id,
            "independent_level_low_kt": "%.0f" % lo, "independent_level_central_kt": "",
            "independent_level_high_kt": "%.0f" % hi,
            "official_over_independent": "%.2f" % ratio, "reading": reading,
            "punjab_kilns": "%.0f" % kilns, "punjab_share_of_national_kilns": "%.4f" % share,
            "coal_per_kiln_t": "%.1f" % per_kiln,
            "punjab_kt_surveyed": "%.0f" % punjab_kt,
            "kiln_frame_scale_out_kt": "%.0f" % scaled_out_kt,
            "scale_out_vs_source_national": ("%.2fx the source's own national figure - the kiln "
                                             "frame puts %.0f percent of national brick coal in "
                                             "Punjab, the source's own pair puts %.0f percent"
                                             % (scaled_out_kt / national_kt, 100 * share,
                                                100 * punjab_kt / national_kt)),
            "implied_bricks_per_kiln_million": "%.2f" % bricks_per_kiln,
            "implied_national_bricks_billion": "%.1f" % national_bricks,
            "intensity_g_per_brick_measured_low": "%.0f" % i_lo,
            "intensity_g_per_brick_measured_high": "%.0f" % i_hi,
            "basis": ("the SOURCE'S OWN national figure (ICIMOD 2022 p.27, 6.5 Mt/yr) as the floor and "
                      "CCAC's 13 Mt as the top. Both rest on the same measured intensity and disagree "
                      "about scale by a factor of two; the kiln-frame scale-out of the Punjab survey "
                      "is carried beside them as a third reading that agrees with neither"),
            "note": ("NO CENTRAL: the level is bounded by a scale disagreement between two "
                     "independent sources, and one surveyed year cannot make a nine-year series - "
                     "the ratio column compares the official path to a fixed independent level, it "
                     "does not replace any year. The implied brick output is also unreconciled: "
                     "this product's surveyed fuel rate at the measured intensity implies 18.5 "
                     "billion bricks in Punjab against ICIMOD's own reported 5.87 billion molded "
                     "and 35.9 billion of stacking capacity - rc55's utilisation model"),
        })
    return out, dict(punjab_kt=punjab_kt, national_kt=national_kt, lo=lo, hi=hi,
                     scaled_out_kt=scaled_out_kt,
                     bricks_per_kiln=bricks_per_kiln, national_bricks=national_bricks,
                     share=share, i_lo=i_lo, i_hi=i_hi)


HEADER = """\
# BRICK-KILN COAL FROM A KILN COUNT AND A MEASURED FUEL RATE (rc53 Wave D) - the first estimate of
# this stream built from evidence that is NOT HDIP's own residual column. Independent level: BKOAP's
# November 2020 Punjab kiln census (10,394) x ICIMOD's 440-kiln 2020 baseline survey (328.2 t per
# kiln-year), scaled nationally on the release's own kiln frame. The band's top is CCAC's national
# figure, which uses the SAME intensity but about three times the scale - the intensity is the
# settled part of this evidence and the scale is not. Measured Pakistani intensity for comparison:
# 184 g of coal per brick (FCBTK) and 155 g (zig-zag), 60 kilns, Faisalabad 2023.
# NO CENTRAL, and no year is replaced: the ratio column asks whether the official series behaves
# like this sector's firing. rc54 CORRECTION: the level is now the source's OWN national figure
# (ICIMOD 2022 p.27, 6.5 Mt/yr). rc53 scaled the paper's Punjab total up on the release's kiln
# frame to 3.94 Mt and never read the national line on the same page - a defect, now demoted to a
# cross-check that disagrees with the source by a factor of 1.65.
# Generated by scripts/build_brick_activity_reconstruction.py.
"""


def main():
    out, facts = build()
    with open(OUT, "w", newline="", encoding="utf-8") as h:
        h.write(HEADER)
        w = csv.DictWriter(h, fieldnames=list(FIELDS), lineterminator="\n")
        w.writeheader()
        w.writerows(out)
    print("brick activity reconstruction -> %s (%d rows)" % (os.path.relpath(OUT, ROOT), len(out)))
    print("  Punjab surveyed %.2f Mt; the SOURCE's own national %.2f Mt; band %.2f .. %.2f Mt"
          % (facts["punjab_kt"] / 1000, facts["national_kt"] / 1000,
             facts["lo"] / 1000, facts["hi"] / 1000))
    print("  the kiln-frame scale-out is %.2f Mt (%.2fx the source's national figure) - a "
          "cross-check that disagrees, not the level"
          % (facts["scaled_out_kt"] / 1000, facts["scaled_out_kt"] / facts["national_kt"]))
    print("  the surveyed fuel rate at the measured intensity implies %.2f million bricks per "
          "kiln-year and %.1f billion nationally" % (facts["bricks_per_kiln"], facts["national_bricks"]))
    for r in out:
        print("  %-8s official %8s kt  %5sx  %s" % (r["fiscal_year"], r["official_kt"],
                                                    r["official_over_independent"], r["reading"][:78]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
