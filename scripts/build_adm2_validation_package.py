#!/usr/bin/env python3
"""Build the ADM2 maps validation package: the nine-year district products, and a
self-contained checker for them.

    python3 scripts/build_adm2_validation_package.py [--out DIR]

WHY THIS EXISTS, AND WHAT IT IS NOT. The full validation package
(scripts/build_validation_package.py) ships the whole release - every product, every source
document, the container, the manuscripts - and comes to about 410 MB. Someone who wants to
check ONE thing, the nine-year ADM2 maps this release adds, should not have to take all of it.
This package carries those maps, the provenance registry that grades them, the national control
they must close against, the district geometry so they can be drawn, and a checker that runs on
a stock Python with no installation and no dependencies.

It is a ONE-OFF, deliberately: it is not declared in data/product_schemas.csv, not written by
any run_all phase, and not regenerated at release. Re-run this script when it is wanted again.
That is a decision, not an oversight - the full package is the release artefact, and a second
registered one would have to be kept true at every release for a convenience that is occasional.

THE CHECKER IS AN INDEPENDENT RE-DERIVATION, not a copy of the repository's tests. It reads the
shipped CSVs and re-computes the identities from them; it does not import pkinv, and it does
not read the repository. If it disagrees with tests/test_spatial_by_year.py, that disagreement
is a finding rather than a formatting difference.
"""
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
import pkinv  # noqa: E402
from pkinv.assets import resolve

NAME = "pakemis_%s_adm2_maps" % pkinv.__version__

# (destination, source). The maps, what grades them, what they must close against, and what
# draws them - nothing else.
PAYLOAD = [
    ("maps/pakemis_adm1_by_year.csv", "outputs/pakemis_adm1_by_year.csv"),
    ("maps/pakemis_adm2_by_year.csv", "outputs/pakemis_adm2_by_year.csv"),
    ("maps/pakemis_adm2_monthly_by_year.csv", "outputs/pakemis_adm2_monthly_by_year.csv"),
    ("maps/pakemis_adm2_sector_by_year.csv", "outputs/pakemis_adm2_sector_by_year.csv"),
    ("provenance/pakemis_spatial_weights_by_year.csv",
     "outputs/pakemis_spatial_weights_by_year.csv"),
    ("provenance/pakemis_grid_fallbacks_by_year.csv",
     "outputs/pakemis_grid_fallbacks_by_year.csv"),
    ("control/pakemis_annual_fy2015_16_fy2024_25.csv",
     "outputs/pakemis_annual_fy2015_16_fy2024_25.csv"),
    ("control/national_all_sectors.csv", "outputs/national_all_sectors.csv"),
    ("geometry/PAK_ADM2.geojson", "data/gis/PAK_ADM2.geojson"),
    ("geometry/adm2_canonical.csv", "data/adm2_canonical.csv"),
    ("geometry/adm2_crosswalk.csv", "data/adm2_crosswalk.csv"),
    ("geometry/periods.csv", "data/periods.csv"),
    # The repository's own assertions, shipped to READ rather than to run: they need the full
    # tree. The checker beside them is independent on purpose.
    ("reference/test_spatial_by_year.py", "tests/test_spatial_by_year.py"),
    ("reference/test_spatial_weights.py", "tests/test_spatial_weights.py"),
    ("reference/spatial_products_contract.md", "docs/spatial_products_contract.md"),
    ("LICENSE-data", "LICENSE-data"),
]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git(*args):
    try:
        return subprocess.check_output(["git", "-C", ROOT] + list(args),
                                       text=True).strip()
    except Exception:                                    # noqa: BLE001
        return ""


def main(argv):
    out_dir = os.path.join(ROOT, "dist")
    if "--out" in argv:
        out_dir = os.path.abspath(argv[argv.index("--out") + 1])
    top = os.path.join(out_dir, NAME)
    if os.path.exists(top):
        shutil.rmtree(top)

    copied = []
    for dst, src in PAYLOAD:
        full = resolve(os.path.join(ROOT, src), root=ROOT)
        if not os.path.exists(full):
            raise SystemExit("missing payload file: %s" % src)
        target = os.path.join(top, dst)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copy2(full, target)
        copied.append({"path": dst, "from": src, "bytes": os.path.getsize(target),
                       "sha256": sha256(target)})

    with open(os.path.join(top, "validate.py"), "w", encoding="utf-8") as handle:
        handle.write(VALIDATE)
    with open(os.path.join(top, "README.md"), "w", encoding="utf-8") as handle:
        handle.write(README % {"version": pkinv.__version__})

    manifest = {
        "package": NAME,
        "release": pkinv.__version__,
        "built_from_commit": git("rev-parse", "HEAD"),
        "tree_clean": git("status", "--porcelain") == "",
        "what_this_is": "the nine-year ADM2 maps of PakEmis %s, with an independent "
                        "checker; a convenience subset of the full validation package, not a "
                        "registered release product" % pkinv.__version__,
        "files": copied,
    }
    with open(os.path.join(top, "MANIFEST.json"), "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=1, sort_keys=True)
        handle.write("\n")

    lines = []
    for folder, _dirs, names in os.walk(top):
        for name in sorted(names):
            full = os.path.join(folder, name)
            rel = os.path.relpath(full, top)
            if rel != "SHA256SUMS":
                lines.append("%s  %s" % (sha256(full), rel))
    with open(os.path.join(top, "SHA256SUMS"), "w", encoding="utf-8") as handle:
        handle.write("\n".join(sorted(lines)) + "\n")

    zip_path = os.path.join(out_dir, NAME + ".zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for folder, dirs, names in os.walk(top):
            dirs.sort()
            for name in sorted(names):
                full = os.path.join(folder, name)
                zf.write(full, os.path.join(NAME, os.path.relpath(full, top)))

    total = sum(f["bytes"] for f in copied)
    print("%s" % top)
    print("  %d files, %.1f MB unpacked" % (len(copied) + 4, total / 1e6))
    print("  zip -> %s (%.1f MB)" % (zip_path, os.path.getsize(zip_path) / 1e6))
    print("  check it with:  cd %s && python3 validate.py" % NAME)
    return 0


VALIDATE = r'''#!/usr/bin/env python3
"""Check the nine-year ADM2 maps. Stock Python 3, no installation, no dependencies.

    python3 validate.py            # exits 0 if every check passes, 1 otherwise

WHAT THIS CHECKS, AND WHAT IT CANNOT. Every check below is an identity re-derived from the
files in this package - conservation, agreement between two views of the same mass, and the
internal consistency of the provenance registry. Conservation is a strong property and a
narrow one: it shows that each year's mass arrives somewhere and is counted once. It says
NOTHING about whether a district's share is right. For 1,102 of the 1,672 live stream-years
the within-province pattern is the reference year's, rescaled to that year's own control -
provenance/pakemis_spatial_weights_by_year.csv says which, per stream-year, and no arithmetic
here can detect a borrowed pattern. Read that file beside these results.
"""
import collections
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FAILURES = []
RESULTS = []


def rows(rel):
    with open(os.path.join(HERE, rel), newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(l for l in handle if not l.startswith("#")))


def check(name, ok, detail):
    RESULTS.append((name, bool(ok), detail))
    if not ok:
        FAILURES.append(name)


def relative(a, b):
    return abs(a - b) / b if b else (0.0 if a == b else 1.0)


# THE PUBLISHED FILES CARRY EIGHT DECIMAL PLACES, ABSOLUTELY, and an annual figure is the sum
# of twelve of them. Two views of the same mass are each rounded on the way out, so an annual
# cell can differ between them by up to twelve quanta per view - and comparing them RELATIVELY
# says nothing at all on a small cell: the shipped reference-year pair
# (pakemis_adm2_monthly.csv against ..._sector.csv) differs by at most 2.0e-08 Gg, which on a
# cell of 6.3e-05 Gg is a relative 1.6e-04. So agreement is judged ABSOLUTELY, at a bound
# DERIVED from the published precision rather than fitted to the observed error:
#
#     2 views x 12 months x 1e-8 Gq = 2.4e-07 Gg
#
# Measured against that bound: the shipped reference-year annual pair differs by at most
# 9.0e-08, and these nine-year products by at most 1.4e-07. Both sit under it, and a real
# arithmetic defect would not.
WRITE_QUANTUM = 1e-8
MONTHS_IN_PERIOD = 12
VIEW_TOLERANCE = 2 * MONTHS_IN_PERIOD * WRITE_QUANTUM


def agree(a, b):
    """True where two views differ by no more than the published write precision."""
    return abs(a - b) <= max(VIEW_TOLERANCE, 1e-9 * abs(b))


def main():
    adm1 = rows("maps/pakemis_adm1_by_year.csv")
    adm2 = rows("maps/pakemis_adm2_by_year.csv")
    monthly = rows("maps/pakemis_adm2_monthly_by_year.csv")
    sector = rows("maps/pakemis_adm2_sector_by_year.csv")
    weights = rows("provenance/pakemis_spatial_weights_by_year.csv")
    fallbacks = rows("provenance/pakemis_grid_fallbacks_by_year.csv")
    control = rows("control/pakemis_annual_fy2015_16_fy2024_25.csv")
    periods = [r["period_id"] for r in rows("geometry/periods.csv")]

    # ---- 1. every product covers every registered period -----------------------------
    for label, table in (("adm1", adm1), ("adm2", adm2), ("monthly", monthly),
                         ("sector", sector), ("weights", weights)):
        got = {r["period_id"] for r in table}
        check("periods present in %s" % label, got == set(periods),
              "%d of %d" % (len(got), len(periods)))

    # ---- 2. national == ADM1, per period ---------------------------------------------
    # The control is the release's own published annual panel, which is not derived from any
    # spatial product: the maps must reproduce it, not restate it.
    national = collections.defaultdict(float)
    for r in control:
        if r["configuration_id"] == "S_TAN" and r["grain"] == "category_gas":
            national[r["period_label"]] += float(r["co2e_Mt_AR5"])
    adm1_total = collections.defaultdict(float)
    for r in adm1:
        adm1_total[r["period_id"]] += float(r["co2e_Mt_AR5"])
    worst, where = 0.0, ""
    for period in periods:
        d = relative(adm1_total[period], national[period])
        if d > worst:
            worst, where = d, period
    check("national == ADM1 (nine periods)", worst < 1e-6,
          "worst %.2e at %s" % (worst, where))

    # ---- 3. ADM1 == ADM2 + the mass explicitly unallocated below ADM1 -----------------
    # The unallocated streams are named by the registry, not guessed: a stream-year typed
    # `unallocated` is one the cube declined to place below the province in that year.
    basis = {(r["source_stream_id"], r["period_id"]): r["spatial_time_basis"]
             for r in weights}
    adm1_gg = collections.defaultdict(float)
    unallocated = collections.defaultdict(float)
    for r in adm1:
        key = r["period_id"]
        value = float(r["emissions_Gg"])
        adm1_gg[key] += value
        if basis.get((r["source_stream_id"], key)) == "unallocated":
            unallocated[key] += value
    adm2_gg = collections.defaultdict(float)
    for r in adm2:
        if r["emissions_Gg"]:
            adm2_gg[r["period_id"]] += float(r["emissions_Gg"])
    worst, where = 0.0, ""
    for period in periods:
        d = relative(adm2_gg[period] + unallocated[period], adm1_gg[period])
        if d > worst:
            worst, where = d, period
    check("ADM1 == ADM2 + unallocated (nine periods)", worst < 1e-6,
          "worst %.2e at %s" % (worst, where))

    # ---- 4. the annual view is the monthly view summed --------------------------------
    key = lambda r: (r["period_id"], r["shape_id"], r["adm2_ids"], r["province"],
                     r["gas"], r["spatial_view"])
    summed = collections.defaultdict(float)
    for r in monthly:
        if r["emissions_Gg"]:
            summed[key(r)] += float(r["emissions_Gg"])
    worst, where, compared, bad = 0.0, "", 0, 0
    for r in adm2:
        if not r["emissions_Gg"]:
            continue
        want = summed.get(key(r), 0.0)
        got = float(r["emissions_Gg"])
        compared += 1
        if not agree(got, want):
            bad += 1
        if abs(got - want) > worst:
            worst, where = abs(got - want), key(r)[:2]
    check("annual ADM2 == monthly ADM2 summed", bad == 0 and compared > 10000,
          "%d cells, worst %.1e Gg at %s" % (compared, worst, where))

    # ---- 5. the module axis partitions the aggregate view -----------------------------
    agg = collections.defaultdict(float)
    for r in sector:
        if r["emissions_Gg"]:
            agg[(r["period_id"], r["shape_id"], r["gas"], r["spatial_view"])] += \
                float(r["emissions_Gg"])
    whole = collections.defaultdict(float)
    for r in adm2:
        if r["emissions_Gg"]:
            whole[(r["period_id"], r["shape_id"], r["gas"], r["spatial_view"])] += \
                float(r["emissions_Gg"])
    worst, where, bad = 0.0, "", 0
    for k, v in whole.items():
        got = agg.get(k, 0.0)
        if not agree(got, v):
            bad += 1
        if abs(got - v) > worst:
            worst, where = abs(got - v), k[:2]
    check("sector ADM2 partitions the aggregate view", bad == 0,
          "%d cells, worst %.1e Gg at %s" % (len(whole), worst, where))

    # ---- 6. the provenance registry is complete and closed ----------------------------
    seen = collections.Counter((r["source_stream_id"], r["period_id"]) for r in weights)
    streams = {r["source_stream_id"] for r in weights}
    check("one registry row per stream-period",
          seen and max(seen.values()) == 1 and len(weights) == len(streams) * len(periods),
          "%d rows = %d streams x %d periods" % (len(weights), len(streams), len(periods)))
    vocabulary = {"direct_activity", "administrative_activity", "dynamic_proxy",
                  "reference_shape_backcast", "substituted_surface", "unallocated",
                  "not_present"}
    outside = {r["spatial_time_basis"] for r in weights} - vocabulary
    check("the basis vocabulary is closed", not outside, "outside: %s" % sorted(outside))
    borrowed_wrong = [r for r in weights
                      if (r["spatial_time_basis"] == "reference_shape_backcast")
                      != bool(r["borrowed_from_period"])]
    check("only a backcast names the period it borrowed from", not borrowed_wrong,
          "%d rows disagree" % len(borrowed_wrong))

    # ---- 7. the substituted share is the emitted record, not a claim ------------------
    emitted = collections.defaultdict(float)
    for r in fallbacks:
        emitted[(r["source_stream_id"], r["period_id"])] += float(r["weight_share"])
    worst, where = 0.0, ""
    for r in weights:
        want = min(1.0, emitted.get((r["source_stream_id"], r["period_id"]), 0.0))
        d = abs(float(r["substituted_share"]) - want)
        if d > worst:
            worst, where = d, r["source_stream_id"]
    check("substituted_share matches the fallback record", worst < 1e-6,
          "worst %.2e at %s" % (worst, where))

    # ---- 8. every drawn shape exists in the geometry ----------------------------------
    with open(os.path.join(HERE, "geometry", "PAK_ADM2.geojson"), encoding="utf-8") as h:
        shapes = {f["properties"]["shapeID"] for f in json.load(h)["features"]}
    drawn = {r["shape_id"] for r in adm2 if r["shape_id"]}
    check("every drawn shape is in the geometry", drawn <= shapes,
          "%d drawn, %d absent" % (len(drawn), len(drawn - shapes)))

    # ---- 9. a declared absence carries no number -------------------------------------
    numeric_absences = [r for r in adm2 if r["absence_reason"] and r["emissions_Gg"]]
    check("a declared absence carries no number", not numeric_absences,
          "%d absence rows carry a value" % len(numeric_absences))

    # ---- 10. the reference year still states the release's own national total ---------
    published = None
    for r in rows("control/national_all_sectors.csv"):
        if r.get("row_kind") == "national_total":
            published = float(r["co2e_Mt_AR5"])
    check("reference year reproduces the published national total",
          published is not None
          and relative(adm1_total["FY2023-24"], published) < 1e-6,
          "ADM1 %.5f against %s" % (adm1_total["FY2023-24"], published))

    width = max(len(n) for n, _ok, _d in RESULTS)
    print("PakEmis ADM2 maps - independent checks\n")
    for name, ok, detail in RESULTS:
        print("  %-*s  %s  %s" % (width, name, "PASS" if ok else "FAIL", detail))
    print()
    if FAILURES:
        print("FAILED: %d of %d checks" % (len(FAILURES), len(RESULTS)))
        return 1
    print("All %d checks passed. Conservation holds; it does not establish that any "
          "district's share is correct - see provenance/." % len(RESULTS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


README = """# PakEmis %(version)s - the nine-year ADM2 maps

This is a **subset** of the PakEmis validation package: the district maps this release adds,
the registry that grades them, the national control they must close against, the boundary file
that draws them, and a checker with no dependencies. The full package
(`pakemis_%(version)s_full_validation.zip`, ~410 MB) carries the whole release; this one
carries one thing.

## Check it

    python3 validate.py

Stock Python 3, no installation. Ten identities, re-derived from the files here - it does not
import the inventory's code, so a disagreement with the repository's own tests
(`reference/`) would be a finding rather than a formatting difference.

## What is here

    maps/pakemis_adm1_by_year.csv           stream x province x period
    maps/pakemis_adm2_by_year.csv           shape x gas x view x period, annual
    maps/pakemis_adm2_monthly_by_year.csv   the same, all 108 months
    maps/pakemis_adm2_sector_by_year.csv    with the module axis, annual
    provenance/...weights_by_year.csv       how each stream-year's geography was arrived at
    provenance/...fallbacks_by_year.csv     what was substituted, per period, priced
    control/                                the release's published national totals
    geometry/                               the 152-unit canonical frame and its polygons
    reference/                              the repository's own assertions, to read

## What these maps claim, and what they do not

Each year's **national mass is evidenced for that year**. The **within-province pattern is
usually not**: of 1,701 stream-periods, 29 carry no mass and of the remaining 1,672 only
**299 (17.9%%) were measured in their own year**; **1,102 (65.9%%)** carry the reference
year's pattern rescaled to that year's own control, 58 ride a substitute surface and 213 are
unallocated below ADM1 in every year. `provenance/pakemis_spatial_weights_by_year.csv` says
which is which, per stream-year, and `validate.py` cannot detect a borrowed pattern - no
arithmetic can. **These are a reconstruction of where past emissions most likely sat, not nine
years of observed district data.**

The sharpest single case: grid power's plant-fuel ledger begins in FY2019-20, so the four
years before it place **42.6 to 53.3 Mt CO2e a year** on a built-up substitute, against 0.34 Mt
in the reference year. `provenance/pakemis_grid_fallbacks_by_year.csv` prices every such
substitution per stream and province.

**One frame carries all nine periods** - the canonical 152-unit set on
geoBoundaries-gbOpen-PAK-ADM2-2019. Eleven of those units were carved out of larger districts
during the window, so an earlier year's row for such a district is the mass that would fall
inside *today's* boundary, not a figure any administration reported at the time. The
contemporaneous geography is not held.

## Units

`emissions_Gg` is native gas mass (CO2, CH4, N2O as themselves), not CO2e. `co2e_Mt_AR5`
appears only in the ADM1 product, where a stream carries one gas and the conversion is exact.
The ADM2 tables deliberately carry no CO2e: two modules mix fossil and biogenic CH4 at the
published grain, so a single per-cell CO2e would be invented precision.

Data CC BY 4.0 (`LICENSE-data`); the boundary file is geoBoundaries (CC BY 4.0).
"""


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
