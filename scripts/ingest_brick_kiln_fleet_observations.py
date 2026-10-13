"""EVERY DATED OBSERVATION OF THE BRICK-KILN FLEET THIS REPOSITORY HOLDS (rc62).

WHY. `outputs/pakemis_brick_activity_reconstruction.csv` carries `punjab_kilns = 10394` in all
nine fiscal years, and `kiln_shares()` splits FCBK from zig-zag on counts that have no year
either. The fleet is not flat - it is UNDATED, which is a different thing and a fixable one:
the repository holds three observations of it, on three dates, and only two scalars of one of
them had ever been read.

THE THREE OBSERVATIONS, AND THEY CONTRADICT EACH OTHER:

  Nov 2020   BKOAP, via ICIMOD WP p.29 and the Qeyas thesis Table 1: 10,394 kilns across 36
             Punjab districts, 2,330 "converted / being converted" to zig-zag = 22.4 percent.
             PER DISTRICT - this ingest is the first time that detail is read.
  Jul 2023   Hamdani et al., Sentinel-2 detection: 9,491 Punjab kilns, 1,299 morphologically
             zig-zag = 13.7 percent. Already held as the fleet the cube places mass on.
  FY2015-16  PBS Census of Manufacturing Industries, PSIC 2392: 10,095 "clay building
             materials" establishments nationally, with 7,393 Punjab brick units imputed from
             a sample of 1,000. Held and never read for this.

The fleet SHRANK 8.7 percent between the first two and the zig-zag share FELL. A conversion
programme is one-way, so the two cannot both be counting the same thing: BKOAP is an owners'
association's administrative status, including kilns "being converted", and Hamdani is a
morphological classification from imagery. NEITHER IS AVERAGED INTO THE OTHER. Both are carried
with their definitions attached, and the disagreement is the finding.

A TRANSCRIPTION CORRECTION, RECOVERED FROM THE TABLE'S OWN ARITHMETIC. The printed row for
Bahawalnagar reads 450 kilns / 82 converted / 33.1 percent. Those three numbers are mutually
impossible: 82 of 450 is 18.2 percent. Two independent checks give the same answer - 82 / 0.331
= 248, and the column sums to 10,596 against a printed total of 10,394, an overshoot of exactly
202 = 450 - 248. The row immediately above prints Bahawalpur 450, which is where the 450 came
from. The table is transcribed with 248 and the printed value is kept beside it.

Usage:  python3 scripts/ingest_brick_kiln_fleet_observations.py [--check]
Writes: data/activity/industry/brick_kiln_fleet_observations.csv
"""
import csv
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.assets import asset_path

from pkinv.core import adm2                                              # noqa: E402
from pkinv.core.io import read_rows, write_or_check                      # noqa: E402

OUT = asset_path(ROOT, "data", "activity", "industry",
                   "brick_kiln_fleet_observations.csv")
KILN_ASSETS = asset_path(ROOT, "data", "gis", "kilns", "pak_brick_kiln_assets.csv")

BKOAP_SOURCE = "BKOAP real-time statistics, November 2020"
BKOAP_FILE = "data/raw/brick_kilns/qeyas_2025_uiii_thesis_punjab_brick_kilns.pdf"
BKOAP_PAGE = "Table 1 (p.11); the same census is printed at ICIMOD WP 2022 p.29"
BKOAP_DEFINITION = ("an owners' association's administrative roll: kilns it lists as operating, "
                    "and kilns 'converted OR BEING CONVERTED' to zig-zag counted together")
BKOAP_LIMITS = ("does not distinguish converted from converting; does not state which kilns "
                "were firing; is a single date with no series behind it")

HAMDANI_SOURCE = "Hamdani et al. 2025, Sci Data 12:830 (Zenodo 14718244)"
HAMDANI_FILE = "data/gis/kilns/pak_brick_kiln_assets.csv"
HAMDANI_PAGE = "Sentinel-2 MSI L2A, 1-15 July 2023"
HAMDANI_DEFINITION = ("a morphological classification from imagery: a structure detected and "
                      "typed FCBK or ZZ by its shape")
HAMDANI_LIMITS = ("detection is not operation - the asset table types every row `prospective`; "
                  "a kiln idle on the image dates is indistinguishable from one demolished; a "
                  "kiln converted on paper but not rebuilt in plan reads as FCBK")

# (printed district label, canonical name, kilns, converted). See the docstring for Bahawalnagar.
BKOAP = [
    ("Attack", "Attock", 250, 7), ("Rawalpindi", "Rawalpindi", 220, 32),
    ("Jehlam", "Jhelum", 163, 3), ("Chakwal", "Chakwal", 118, 16),
    ("Sargodha", "Sargodha", 403, 19), ("khushab", "Khushab", 156, 25),
    ("Mainwali", "Mianwali", 158, 0), ("Chiniot", "Chiniot", 67, 2),
    ("Gujrat", "Gujrat", 254, 61), ("Mandi Bahauddin", "Mandi Bahauddin", 245, 75),
    ("Hafiz abad", "Hafizabad", 93, 62), ("narowal", "Narowal", 205, 105),
    ("Sialkot", "Sialkot", 265, 60), ("Gujranwala", "Gujranwala", 332, 74),
    ("Sheikhupura", "Sheikhupura", 312, 91), ("Nankana", "Nankana Sahib", 107, 35),
    ("Faisalabad", "Faisalabad", 607, 207), ("Toba Tek Singh", "Toba Tek Singh", 415, 15),
    ("Jhang", "Jhang", 280, 3), ("Bhakar", "Bhakkar", 198, 1),
    ("Layyah", "Layyah", 254, 1), ("Muzaffargarh", "Muzaffargarh", 426, 7),
    ("D.G. Khan", "Dera Ghazi Khan", 156, 0), ("Multan", "Multan", 614, 12),
    ("Rajanpur", "Rajanpur", 162, 1), ("Rahim Yar khan", "Rahim Yar Khan", 350, 10),
    ("Bahawalpur", "Bahawalpur", 450, 25), ("Lodhran", "Lodhran", 292, 7),
    ("Vehari", "Vehari", 380, 74), ("Bahawalnagar", "Bahawalnagar", 248, 82),
    ("Pakpattan", "Pakpattan", 221, 20), ("Khanewal", "Khanewal", 320, 24),
    ("Sahiwal", "Sahiwal", 230, 59), ("Okara", "Okara", 332, 129),
    ("Lahore", "Lahore", 277, 250), ("Kasur", "Kasur", 834, 736),
]
BKOAP_PRINTED_TOTAL, BKOAP_PRINTED_CONVERTED = 10394, 2330
BAHAWALNAGAR_PRINTED = 450

FIELDS = ("observation_id", "source", "source_file", "source_page", "observation_date",
          "geography_level", "geography_printed", "adm2_id", "kilns_total", "kilns_zigzag",
          "zigzag_share", "printed_value_if_corrected", "definition",
          "what_it_does_not_measure", "note")


def _adm2(name):
    try:
        return adm2.resolve(name)
    except KeyError:
        return "unresolved"


def hamdani_by_district():
    """{adm2_id: (total, zigzag)} from the held asset table - computed, not transcribed."""
    out = {}
    for r in read_rows(KILN_ASSETS):
        if r["province"] != "Punjab":
            continue
        for member in r["adm2_ids"].split(";"):
            if not member or member.startswith("unresolved"):
                continue
            total, zz = out.get(member, (0.0, 0.0))
            share = 1.0 / len(r["adm2_ids"].split(";"))
            out[member] = (total + share, zz + (share if r["kiln_type"] == "ZZ" else 0.0))
    return out


def build():
    rows = []
    total = sum(r[2] for r in BKOAP)
    converted = sum(r[3] for r in BKOAP)
    if (total, converted) != (BKOAP_PRINTED_TOTAL, BKOAP_PRINTED_CONVERTED):
        raise SystemExit("the transcribed BKOAP table sums to %d/%d against a printed %d/%d - "
                         "the correction recorded in this module's docstring no longer closes"
                         % (total, converted, BKOAP_PRINTED_TOTAL, BKOAP_PRINTED_CONVERTED))

    for printed, canonical, kilns, zz in BKOAP:
        # THE COLUMN CARRIES THE PRINTED VALUE, so it opens with it. An earlier version of
        # this string opened with the USED value, which made the column a second copy of
        # kilns_total and left the printed figure findable only inside the prose - a silent
        # edit of a source in all but name. The reviewed wording was corrected in the
        # committed table and never here, so the first cold build after the sector-layout
        # migration re-derived the table and put the old wording back.
        corrected = ("%d - THE PRINTED VALUE, which this row does not use. kilns_total "
                     "above is %d. The printed %d is impossible against the same row's own "
                     "%d converted at 33.1 percent (%d/0.331 = 247.7), and the column as "
                     "printed overshoots its own printed total by exactly the difference "
                     "(%s - %s = %d = %d - %d). The row immediately above prints Bahawalpur "
                     "450, so the transcription duplicated it downward. The printed TOTAL, "
                     "not the printed row, is the arbiter here."
                     % (BAHAWALNAGAR_PRINTED, kilns, BAHAWALNAGAR_PRINTED, zz, zz,
                        format(BKOAP_PRINTED_TOTAL + BAHAWALNAGAR_PRINTED - kilns, ","),
                        format(BKOAP_PRINTED_TOTAL, ","),
                        BAHAWALNAGAR_PRINTED - kilns, BAHAWALNAGAR_PRINTED, kilns)
                     ) if canonical == "Bahawalnagar" else ""
        rows.append({
            "observation_id": "bkoap_2020_%s" % canonical.lower().replace(" ", "_"),
            "source": BKOAP_SOURCE, "source_file": BKOAP_FILE, "source_page": BKOAP_PAGE,
            "observation_date": "2020-11", "geography_level": "district",
            "geography_printed": printed, "adm2_id": _adm2(canonical),
            "kilns_total": kilns, "kilns_zigzag": zz,
            "zigzag_share": "%.4f" % (zz / kilns) if kilns else "",
            "printed_value_if_corrected": corrected,
            "definition": BKOAP_DEFINITION, "what_it_does_not_measure": BKOAP_LIMITS,
            "note": "",
        })

    hamdani = hamdani_by_district()
    for adm2_id, (tot, zz) in sorted(hamdani.items()):
        rows.append({
            "observation_id": "hamdani_2023_%s" % adm2_id,
            "source": HAMDANI_SOURCE, "source_file": HAMDANI_FILE, "source_page": HAMDANI_PAGE,
            "observation_date": "2023-07", "geography_level": "district",
            "geography_printed": "", "adm2_id": adm2_id,
            "kilns_total": "%.1f" % tot, "kilns_zigzag": "%.1f" % zz,
            "zigzag_share": "%.4f" % (zz / tot) if tot else "",
            "printed_value_if_corrected": "",
            "definition": HAMDANI_DEFINITION, "what_it_does_not_measure": HAMDANI_LIMITS,
            "note": ("COMPUTED from the held asset table, not transcribed; a kiln on a shared "
                     "geoBoundaries shape is split equally between its members, which is why "
                     "counts are fractional"),
        })

    rows.append({
        "observation_id": "pbs_cmi_2015_16_punjab_bricks", "source":
        "PBS Census of Manufacturing Industries 2015-16",
        "source_file": "data/raw/pbs/cmi/pbs_cmi_2015_16_report.pdf",
        "source_page": "frame table 9.A and the establishment table, PSIC 2392",
        "observation_date": "2016-06", "geography_level": "province",
        "geography_printed": "Punjab", "adm2_id": "",
        "kilns_total": 7393, "kilns_zigzag": "", "zigzag_share": "",
        "printed_value_if_corrected": "",
        "definition": ("registered ESTABLISHMENTS in PSIC 2392 'clay building materials', not "
                       "kilns: 7,393 Punjab brick units excluded from the census exercise and "
                       "imputed from a sample of 1,000"),
        "what_it_does_not_measure": ("an establishment is a legal unit and a kiln is a "
                                     "structure; the two counts are not interchangeable and no "
                                     "ratio between them is held"),
        "note": ("the earliest dated observation of the population held anywhere in this "
                 "repository, and the only one inside the panel's own first year"),
    })
    return rows


def main():
    rows = build()
    write_or_check(OUT, FIELDS, rows, check="--check" in sys.argv, lineterminator="\n")
    kinds = Counter(r["source"].split(",")[0] for r in rows)
    print("%s: %d rows" % (os.path.relpath(OUT, ROOT), len(rows)))
    for k, n in sorted(kinds.items()):
        print("   %-46s %3d" % (k[:46], n))
    b = {r["adm2_id"]: r for r in rows if r["observation_date"] == "2020-11"}
    h = {r["adm2_id"]: r for r in rows if r["observation_date"] == "2023-07"}
    print("\n   %-22s %10s %10s   %10s %10s" % ("", "BKOAP 2020", "zigzag", "Hamdani 23", "zigzag"))
    for adm2_id in ("punjab_lahore", "punjab_kasur", "punjab_faisalabad"):
        bb, hh = b.get(adm2_id), h.get(adm2_id)
        print("   %-22s %10s %10s   %10s %10s" % (adm2_id,
              bb["kilns_total"] if bb else "-", bb["kilns_zigzag"] if bb else "-",
              hh["kilns_total"] if hh else "-", hh["kilns_zigzag"] if hh else "-"))


if __name__ == "__main__":
    from pkinv.activity.store import staging_inputs
    with staging_inputs():
        main()
