#!/usr/bin/env python3
"""The 2022 COD-AB ADM2 frame, crosswalked to the canonical 152-unit set (rc47 Wave 6).

The twenty-first review's frame finding: 152 canonical IDs resolve to 126 drawable
shapes in the frozen 2019 geoBoundaries file - 14 collision groups, Larkana missing
outright, 21.4% of district mass on shared polygons. This product settles the DATA
half: OCHA COD-AB Pakistan (WFP-sourced, valid 2022-09-09, CC BY-IGO) carries 160
ADM2 units and resolves twelve of the fourteen collision groups plus Larkana and
Tor Ghar. What it does NOT do this release is re-rasterise: every shipped shape_id,
golden and grid cell stays on the frozen 2019 frame, because swapping the boundary
file re-keys every district product at once - that is v1.1's one declared migration,
and this crosswalk is its complete, tested preparation.

Statuses:
  resolves           the canonical unit gets its own 2022 polygon (was shared/missing)
  same_as_2019       one-to-one in both vintages
  part_of            still inside a 2022 neighbour (Keamari in West Karachi; Surab in Kalat)
  no_geometry        a census unit no vintage draws (Cholistan; the Other residual)
  outside_product_frame  a 2022 unit outside the canonical set (AJK/GB districts, and
                     post-frame carves folded back onto their canonical parents)

Usage:  python3 scripts/build_adm2_frame_2022.py [--check]
Writes: outputs/pakemis_adm2_frame_2022.csv
"""
import json
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from pkinv.assets import asset_path

from pkinv.core import adm2  # noqa: E402
from pkinv.core.io import write_or_check  # noqa: E402
from pkinv.paths import DATA, OUTPUTS  # noqa: E402

SRC = asset_path(DATA, "gis", "cod_ab", "pak_admin2.geojson")
OUT = asset_path(OUTPUTS, "pakemis_adm2_frame_2022.csv")
FIELDS = ("adm2_id", "canonical_name", "shape_id_2019", "relation_2019",
          "pcode_2022", "name_2022", "status_2022", "note")

ALIAS = {"CENTRAL KARACHI": "KARACHI CENTRAL", "EAST KARACHI": "KARACHI EAST",
         "SOUTH KARACHI": "KARACHI SOUTH", "WEST KARACHI": "KARACHI WEST",
         "KORANGI KARACHI": "KORANGI", "MALIR KARACHI": "MALIR",
         "CHITRAL LOWER": "LOWER CHITRAL", "CHITRAL UPPER": "UPPER CHITRAL",
         "KOHISTAN LOWER": "LOWER KOHISTAN", "KOHISTAN UPPER": "UPPER KOHISTAN",
         "KOLAI PALAS KOHISTAN": "KOLAI PALAS", "TOR GHAR": "TORGHAR",
         "D I KHAN": "DERA ISMAIL KHAN", "LEIAH": "LAYYAH",
         "SHAHEED BENAZIR ABAD": "SHAHEED BENAZIRABAD"}
# 2022 units with no canonical row of their own: folded onto the canonical unit
# that contains them in the frame, typed outside_product_frame.
FOLDED = {"Lehri": "balochistan_sibi",
          "Shaheed Sikandarabad": "balochistan_nasirabad",
          "Darel": "other_residual", "Tangir": "other_residual",
          "Gupis-Yasin": "other_residual", "Rondu": "other_residual",
          "Diamir": "other_residual", "Malakand": "kp_malakand_protected_area"}
# canonical units the 2022 vintage still cannot draw on their own
PART_OF = {"sindh_keamari": ("West Karachi", "carved 2020; the 2022 vintage still "
                             "draws it inside West Karachi"),
           "balochistan_surab": ("Kalat", "carved 2022; not yet in the 2022-09 file")}


def _norm(s):
    s = s.upper().replace(" DISTRICT", "").strip()
    return " ".join(re.sub(r"[^A-Z ]", "", s).split())


def build():
    canonical = adm2.load_canonical()
    feats = json.load(open(SRC, encoding="utf-8"))["features"]
    by_norm = defaultdict(set)
    for u in canonical.values():
        by_norm[_norm(u["canonical_name"])].add(u["adm2_id"])
    match = {}
    outside = []
    for f in feats:
        p = f["properties"]
        name = p["adm2_name"]
        if p["adm1_name"] in ("Azad Kashmir", "Gilgit Baltistan") \
                and name not in FOLDED:
            outside.append((p["adm2_pcode"], name, "other_residual",
                            "AJK/GB district; the product frame keeps the Other "
                            "residual by design"))
            continue
        if name in FOLDED:
            outside.append((p["adm2_pcode"], name, FOLDED[name],
                            "no canonical row of its own; folded onto its "
                            "containing canonical unit"))
            continue
        n = ALIAS.get(_norm(name), _norm(name))
        ids = by_norm.get(n, set())
        if len(ids) != 1:
            raise SystemExit("2022 unit %r resolves to %s - extend ALIAS/FOLDED "
                             "rather than letting a unit vanish" % (name, sorted(ids)))
        match[next(iter(ids))] = (p["adm2_pcode"], name)
    rows = []
    shared_2019 = defaultdict(list)
    for u in canonical.values():
        if u["shape_id"]:
            shared_2019[u["shape_id"]].append(u["adm2_id"])
    for u in sorted(canonical.values(), key=lambda x: x["adm2_id"]):
        aid = u["adm2_id"]
        pcode, name2022 = match.get(aid, ("", ""))
        if aid in PART_OF:
            host, why = PART_OF[aid]
            status, note = "part_of", why
        elif not u["shape_id"] and pcode:
            status, note = "resolves", ("no 2019 polygon at all (the %s defect); "
                                        "the 2022 vintage draws it"
                                        % u["canonical_name"])
        elif not u["shape_id"]:
            status, note = "no_geometry", "no vintage draws this unit"
        elif pcode and len(shared_2019[u["shape_id"]]) > 1:
            status, note = "resolves", ("shares its 2019 polygon with %s; own "
                                        "polygon in 2022"
                                        % ";".join(i for i in shared_2019[u["shape_id"]]
                                                   if i != aid))
        elif pcode:
            status, note = "same_as_2019", ""
        else:
            status, note = "part_of", "no matching 2022 unit found"
        rows.append({"adm2_id": aid, "canonical_name": u["canonical_name"],
                     "shape_id_2019": u["shape_id"],
                     "relation_2019": u["geometry_relation"],
                     "pcode_2022": pcode, "name_2022": name2022,
                     "status_2022": status, "note": note})
    for pcode, name, folded_onto, why in sorted(outside):
        rows.append({"adm2_id": folded_onto, "canonical_name": "",
                     "shape_id_2019": "", "relation_2019": "",
                     "pcode_2022": pcode, "name_2022": name,
                     "status_2022": "outside_product_frame", "note": why})
    banner = [
        "THE 2022 COD-AB ADM2 FRAME, CROSSWALKED (rc47 Wave 6). OCHA COD-AB Pakistan",
        "(WFP-sourced, valid 2022-09-09, CC BY-IGO, 160 units) against the canonical",
        "152-unit set and its frozen 2019 rasterisation. Twelve of fourteen collision",
        "groups plus Larkana and Tor Ghar RESOLVE; Keamari and Surab stay part_of.",
        "NOTHING here re-keys a shipped product: the re-rasterisation is v1.1's one",
        "declared migration, and this table is its complete, tested preparation.",
    ]
    check = "--check" in sys.argv
    write_or_check(OUT, list(FIELDS), rows, check=check, banner=banner,
                   lineterminator="\n")
    from collections import Counter
    c = Counter(r["status_2022"] for r in rows)
    print("frame 2022: %d rows; %s" % (len(rows), dict(c)))


if __name__ == "__main__":
    build()
