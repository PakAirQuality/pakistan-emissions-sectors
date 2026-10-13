#!/usr/bin/env python3
"""The nine-year district crop panel from the PBS National Accounts dashboard (rc46 Wave 3).

WHAT THIS RETIRES. Every crop-driven agriculture stream-year before the reference period has
carried the reference year's within-province pattern - 'reference_shape_backcast' in the
weight registry, 64 stream-years across eight periods. The PBS dashboard serves district-wise
area and production for the five engine crops in every year of the window
(data/raw/pbs/crops_district/, Wave 0), and this panel is the frozen, QA'd form the cube
reads (grid_cube._crop_panel; no province-share loader reads it - an earlier draft of this
docstring claimed one did).

THE CONCORDANCE IS FROZEN AND KEYED (id, name), NEVER id ALONE. The dashboard's district ids
are not unique - the 2022-carved districts (Kot Addu, Wazirabad) share their parent's id -
and its names carry a typo ('CHIRTAL') and one division-level row (KARACHI DIVISION). Nine
names are OLD-BOUNDARY PARENTS whose canonical frame holds two children (Mansehra/Torghar,
Jhang/Chiniot, Thatta/Sujawal, Kalat/Surab, Kharan/Washuk, Sibi/Harnai, ...): such a row is
mapped to a POOLED id list and split within the pool by the reference year's own
within-pool crop split - a partial borrow four orders smaller than whole-pattern borrowing,
declared per row in the panel's split_rule column.

ROW-LEVEL QA, EACH RULE NAMED IN qa_flag:
  summed_duplicate  - the same (id, name) twice in one payload (D.I. Khan, every year):
                      the rows partition one geography and are summed
  excluded_corrupt  - the Sujawal rice cell in 2015-16 (719.8) and 2019-20 (775.9): each
                      equals the ENTIRE excess of the payload over the Economic Survey
                      national control to 0.5 kt, and is excluded by this named rule with
                      the residual republished
  pooled_parent     - an old-boundary parent row split UNIFORMLY over its pool (declared;
                      allocation-inert because the cube re-sums the pool onto its shared shape)

Usage:  python3 scripts/build_crop_district_panel.py [--check]
Writes: data/activity/agriculture/crop_district_panel.csv
"""
import csv
import json
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from pkinv.assets import asset_path

from pkinv.core.io import write_or_check  # noqa: E402
from pkinv.paths import DATA, ROOT  # noqa: E402

RAW = asset_path(DATA, "raw", "pbs", "crops_district")
OUT = asset_path(DATA, "activity", "agriculture", "crop_district_panel.csv")
BASE = asset_path(ROOT, "outputs", "district_totals_2024.csv")
FIELDS = ("period_id", "crop", "adm2_id", "area_kha", "production_kt", "qa_flag",
          "split_rule", "source_row")
CROPS = {1: "maize", 2: "rice", 3: "sugarcane", 4: "wheat", 5: "cotton"}
PERIODS = ("2015-16", "2016-17", "2017-18", "2018-19", "2019-20",
           "2020-21", "2021-22", "2022-23", "2023-24")

# (dashboard id, exact name) -> canonical adm2_id, or a tuple for a pooled parent.
# Hand-written; the auto-normalised 112 are asserted against this table at build.
POOLED = {
    ("009", "MANSEHRA DISTRICT"): ("kp_mansehra", "kp_torghar"),
    ("035", "JHANG DISTRICT"): ("punjab_jhang", "punjab_chiniot"),
    ("069", "THATTA DISTRICT"): ("sindh_thatta", "sindh_sujawal"),
    ("086", "KALAT DISTRICT"): ("balochistan_kalat", "balochistan_surab"),
    ("087", "KHARAN DISTRICT"): ("balochistan_kharan", "balochistan_washuk"),
    ("107", "SIBI DISTRICT"): ("balochistan_sibi", "balochistan_harnai"),
    ("111", "LORALAI DISTRICT"): ("balochistan_loralai", "balochistan_duki"),
    ("114", "ZHOB DISTRICT"): ("balochistan_zhob", "balochistan_sherani"),
    # The dashboard's one four-way parent, and its name carries the source's own trailing
    # lower-case t. The canonical frame holds the legacy unit AND the three carved
    # districts; the pool is the three real children (the legacy row is the same
    # geography's bookkeeping name, not a fourth place).
    ("992", "KOHISTAN DISTRICt"): ("kp_upper_kohistan", "kp_lower_kohistan",
                                   "kp_kolai_palas"),
}
SPECIAL = {
    # source typo for Chitral, which split in 2018: the pool is the two carved children,
    # like Kohistan's (the legacy unit is the same geography's bookkeeping name)
    ("991", "CHIRTAL DISTRICT"): ("kp_upper_chitral", "kp_lower_chitral"),
}
# KARACHI DIVISION: the dashboard's one division-grain row; pooled over the REAL Karachi
# districts of the canonical frame - the collision group sharing the Karachi shape, minus
# the legacy bookkeeping aggregate (the same rule Kohistan and Chitral follow). The rc46
# derivation matched the SUBSTRING "karachi", which admitted sindh_karachi_legacy as a
# fifth place and missed Malir, Korangi and Keamari, whose ids do not contain it.
KARACHI_KEY = ("990", "KARACHI DIVISION")
# Corrupt cells excluded by name: (period, crop, id, name) -> printed value it must carry.
# THE SUJAWAL RICE CELL IS CORRUPT IN SEVEN OF NINE YEARS, not the two a spot check first
# found: in every year it appears (2015-16..2021-22) its area equals the payload's ENTIRE
# excess over the Economic Survey national control, to 0.6 kt or better; the two clean
# years (2022-23, 2023-24) carry no Sujawal rice row at all. Each entry still pins the
# printed value, so a source-side revision fails the build instead of being silently
# excluded on stale grounds.
EXCLUDED = {
    ("2015-16", "rice", "152", "SUJAWAL DISTRICT"): 719.8,
    ("2016-17", "rice", "152", "SUJAWAL DISTRICT"): 750.5,
    ("2017-18", "rice", "152", "SUJAWAL DISTRICT"): 828.3,
    ("2018-19", "rice", "152", "SUJAWAL DISTRICT"): 690.2,
    ("2019-20", "rice", "152", "SUJAWAL DISTRICT"): 775.9,
    ("2020-21", "rice", "152", "SUJAWAL DISTRICT"): 709.0,
    ("2021-22", "rice", "152", "SUJAWAL DISTRICT"): 756.6,
}


def _norm(s):
    s = s.upper().replace(" DISTRICT", "").strip()
    return " ".join(re.sub(r"[^A-Z ]", "", s).split())


def _canonical():
    rows = [r for r in csv.DictReader(
        l for l in open(asset_path(DATA, "adm2_canonical.csv"), encoding="utf-8")
        if not l.startswith("#"))]
    by_norm = defaultdict(set)
    for r in rows:
        by_norm[_norm(r["canonical_name"])].add(r["adm2_id"])
        if r.get("shape_name"):
            by_norm[_norm(r["shape_name"])].add(r["adm2_id"])
    karachi_shape = next(r["shape_id"] for r in rows
                         if r["adm2_id"] == "sindh_karachi_legacy")
    karachi = tuple(sorted(
        r["adm2_id"] for r in rows
        if r["shape_id"] == karachi_shape
        and r["geometry_relation"] != "legacy_aggregate"))
    assert len(karachi) == 7, karachi
    return by_norm, karachi


def _pool_split(pool):
    """UNIFORM within-pool split, declared as such (rc47 Wave 1).

    The rc46 version claimed to read the reference year's own within-pool split from
    the audited district product and never did: it keyed the product by display name
    against a pool of adm2_ids, so the lookup always missed and every shipped split
    was silently the 1/n fallback - 727 rows asserting a provenance that never
    executed. And the claimed method was undefinable anyway: the product's frame is
    SHAPE-based, a collision group's children share one polygon, and no evidence the
    repository holds can see inside a shared shape. So the split is uniform, said
    plainly - and it is ALLOCATION-INERT by construction, because the cube re-sums
    pool children onto their shared shape before any mass is placed
    (grid_cube.agriculture_panels names units canonically; core.gis.cube
    district_factors sums same-shape units)."""
    return {d: 1.0 / len(pool) for d in pool}


def build():
    by_norm, karachi = _canonical()
    out = []
    for cid, crop in sorted(CROPS.items()):
        for period in PERIODS:
            path = asset_path(RAW, "crop%d_%s.json" % (cid, period))
            payload = json.load(open(path))["data"]
            merged = {}
            for r in payload:
                key = (str(r["id"]), r["name"].strip())
                if key in merged:
                    prev = merged[key]
                    merged[key] = {"area": (prev["area"] or 0) + (r["area"] or 0),
                                   "production": (prev["production"] or 0) + (r["production"] or 0),
                                   "dup": True}
                else:
                    merged[key] = {"area": r["area"] or 0.0,
                                   "production": r["production"] or 0.0, "dup": False}
            for (i, name), v in sorted(merged.items()):
                exc = EXCLUDED.get((period, crop, i, name))
                if exc is not None:
                    if abs(v["area"] - exc) > 0.2:
                        raise SystemExit(
                            "excluded cell (%s %s %s) no longer carries the corrupt value "
                            "this rule was written for (%.1f vs %.1f) - re-examine, do not "
                            "auto-exclude" % (period, crop, name, v["area"], exc))
                    out.append({"period_id": "FY" + period, "crop": crop, "adm2_id": "",
                                "area_kha": "%.3f" % v["area"],
                                "production_kt": "%.3f" % v["production"],
                                "qa_flag": "excluded_corrupt", "split_rule": "",
                                "source_row": "%s|%s" % (i, name)})
                    continue
                key = (i, name)
                if key == KARACHI_KEY:
                    pool = karachi
                elif key in POOLED:
                    pool = POOLED[key]
                elif key in SPECIAL:
                    pool = SPECIAL[key]
                else:
                    tgt = by_norm.get(_norm(name), set())
                    if len(tgt) == 1:
                        pool = (next(iter(tgt)),)
                    elif len(tgt) > 1:
                        raise SystemExit("ambiguous name %r not in POOLED - freeze it" % name)
                    else:
                        raise SystemExit("unmatched district %r (id %s) - extend the "
                                         "concordance, never guess" % (name, i))
                qa = "summed_duplicate" if v["dup"] else ""
                if len(pool) == 1:
                    out.append({"period_id": "FY" + period, "crop": crop,
                                "adm2_id": pool[0], "area_kha": "%.3f" % v["area"],
                                "production_kt": "%.3f" % v["production"],
                                "qa_flag": qa, "split_rule": "",
                                "source_row": "%s|%s" % (i, name)})
                else:
                    split = _pool_split(pool)
                    for d in pool:
                        out.append({"period_id": "FY" + period, "crop": crop,
                                    "adm2_id": d,
                                    "area_kha": "%.3f" % (v["area"] * split[d]),
                                    "production_kt": "%.3f" % (v["production"] * split[d]),
                                    "qa_flag": (qa + "|" if qa else "") + "pooled_parent",
                                    "split_rule": "uniform within-pool split %.4f (declared; allocation-inert, see _pool_split)" % split[d],
                                    "source_row": "%s|%s" % (i, name)})
    return out


def main(check=False):
    rows = build()
    # THE EXCLUSION MUST HAVE FIRED. A wrong id in EXCLUDED would not error - the corrupt
    # row would simply take the ordinary path and the rule would never run. Guessing wrong
    # silently is the one failure mode this rule must not have.
    fired = {(r["period_id"], r["crop"]) for r in rows if r["qa_flag"] == "excluded_corrupt"}
    for period, crop, _i, _n in EXCLUDED:
        if ("FY" + period, crop) not in fired:
            raise SystemExit("EXCLUDED rule for (%s, %s) never fired - the corrupt row "
                             "entered the panel by another key" % (period, crop))
    n_periods = len({r["period_id"] for r in rows})
    banner = [
        "DISTRICT CROP PANEL, NINE YEARS, FIVE CROPS (rc46 Wave 3), from the PBS National",
        "Accounts dashboard JSONs held under data/raw/pbs/crops_district/. Units: 000 ha,",
        "000 t, as served. The concordance, pooling and exclusion rules are in",
        "scripts/build_crop_district_panel.py - keyed (id, name), never id alone; the",
        "SEVEN corrupt Sujawal rice cells are excluded by a rule that FAILS if a value moves.",
        "%d rows over %d periods." % (len(rows), n_periods),
    ]
    return write_or_check(OUT, list(FIELDS), rows, check=check, banner=banner,
                          lineterminator="\n")


if __name__ == "__main__":
    raise SystemExit(main(check="--check" in sys.argv))
