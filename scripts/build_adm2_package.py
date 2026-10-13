"""Build the canonical ADM2 package: one district system, and every observed spelling mapped.

WHY THIS EXISTS. Four district name systems are live in this repository and none of them
agree: the geoBoundaries 2019 geometry (126 shapes; the grid and the agriculture/railways
products), the PBS Census-2023 panel (134 districts, "X District" spellings; waste and
residential), the PBS 7th Agricultural Census (137, adds Cholistan Area), and the provincial
Bureau-of-Statistics registration tables (122, abbreviations like D.G.Khan). Until now the
only bridges were a 20-row alias file scoped to one sector and a normaliser copy-pasted into
three modules. A national spatial product cannot stand on that.

THE CANONICAL CHOICE, AND WHY. Canonical units = the PBS Census-2023 districts. They name the
real administrative universe; every new statistical panel arrives in their vocabulary; and the
census is the reviewer's named target ("one harmonised Census-2023 ADM2 system"). The
geometry, by contrast, is merely what can be rasterised today - a 2019-vintage boundary file
in which several 2023 districts have no polygon of their own. So the mapping runs
canonical -> geometry, many-to-one where the census subdivides a shape, and is DECLARED where
the geometry is simply absent. Folding the census into the geometry instead (Chiniot into
Jhang, seven Karachi districts into one) would be irreversible at ingest; this direction is
lossless.

WHAT THE GEOMETRY FILE TURNS OUT TO BE MISSING - found while building this, and the reason
geometry_relation exists as a column rather than as an assumption:
  - LARKANA HAS NO POLYGON. Not a vintage problem: Qambar Shahdadkot, which was carved OUT OF
    Larkana in 2004, is present. A distributor defect in geoBoundaries gbOpen PAK ADM2. Every
    district product built on this file to date has silently carried Larkana's cells as
    "outside any district" (grid fill -1).
  - Sixteen post-2005 districts have no own shape (Chiniot, Duki, Harnai, Chaman, Sohbatpur,
    Sujawal, Surab, Sherani, Washuk, Torghar, Nankana Sahib, Upper/Lower Chitral,
    Upper/Lower Kohistan, Kolai Palas) and are declared part_of or carved_from their parents.
  - The seven Karachi census districts share the single Karachi shape.

Deterministic: running twice produces byte-identical files. --check re-derives and diffs, the
same discipline as make_readme_tables.py. The hand-resolved knowledge below IS the content;
this script is where it is reviewed.

Usage:  python3 scripts/build_adm2_package.py [--check]
Writes: data/adm2_canonical.csv
        data/adm2_crosswalk.csv
"""
import csv
import io
import json
import os
import re
import sys
from pkinv.assets import resolve

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEOJSON = os.path.join(ROOT, "data", "gis", "PAK_ADM2.geojson")
POPULATION = os.path.join(ROOT, "data", "activity", "waste", "population_district.csv")
LIVESTOCK = os.path.join(ROOT, "data", "activity", "livestock_district_2024.csv")
VEHICLES = os.path.join(ROOT, "data", "activity", "transport", "vehicles_district.csv")
CANONICAL_OUT = os.path.join(ROOT, "data", "adm2_canonical.csv")
CROSSWALK_OUT = os.path.join(ROOT, "data", "adm2_crosswalk.csv")
GEOJSON, POPULATION, LIVESTOCK, VEHICLES, CANONICAL_OUT, CROSSWALK_OUT = (
    resolve(path, root=ROOT) for path in
    (GEOJSON, POPULATION, LIVESTOCK, VEHICLES, CANONICAL_OUT, CROSSWALK_OUT))

GEOMETRY_VERSION = "geoBoundaries-gbOpen-PAK-ADM2-2019"


def normalise(name):
    """One normaliser for every district string in the repository.

    Byte-compatible with the three `_norm` copies it replaces (lowercase, strip a trailing
    'district', hyphens and dots to spaces), so swapping it in changes no behaviour.
    """
    s = name.strip().lower()
    s = re.sub(r"\s+district$", "", s)
    s = s.replace("-", " ").replace(".", " ").replace("'", "")
    return re.sub(r"\s+", " ", s).strip()


# --- HAND-RESOLVED KNOWLEDGE ------------------------------------------------------------
# Every entry below was resolved by reading the four vocabularies side by side. A wrong row
# here misallocates a district, so each carries its reason.

# geoBoundaries shapeName -> PBS census name, where the two spell one district differently
# (or the district was renamed). Everything not listed matches by normalise().
GEO_VARIANTS = {
    "Battagram": "Batagram District",
    "Jafarabad": "Jaffarabad District",
    "Naushehro Feroze": "Naushahro Feroze District",
    "Nawabshah": "Shaheed Benazirabad District",       # renamed 2008
    "Qambar Shahdadkot": "Kambar Shahdad Kot District",
    "Qilla Abdullah": "Killa Abdullah District",
    "Qilla Saifullah": "Killa Saifullah District",
    "Sheikhpura": "Sheikhupura District",
    "Vihari": "Vehari District",
    "Umerkot": "Umer Kot District",
    "Mirpurkhas": "Mirpur Khas District",
    "Kachhi": "Kachhi District",                        # PBS uses Kachhi; Bolan is the OLD name
    "Islamabad Capital Territory": "Islamabad District",
    "Malakand": "Malakand Protected Area",              # the census's formal name, no suffix
}

# PBS census districts with no polygon of their own: (canonical name -> (relation, parent
# geoBoundaries shapeName)). part_of = the census subdivided the shape; carved_from = the
# district was created out of the parent after the geometry vintage. Larkana is the
# distributor defect: the shape is absent although the district predates every other one.
NO_OWN_SHAPE = {
    "Karachi Central District": ("part_of", "Karachi"),
    "Karachi East District": ("part_of", "Karachi"),
    "Karachi South District": ("part_of", "Karachi"),
    "Karachi West District": ("part_of", "Karachi"),
    "Korangi District": ("part_of", "Karachi"),
    "Keamari District": ("part_of", "Karachi"),
    "Malir District": ("part_of", "Karachi"),
    "Lower Chitral District": ("part_of", "Chitral"),
    "Upper Chitral District": ("part_of", "Chitral"),
    "Lower Kohistan District": ("part_of", "Kohistan"),
    "Upper Kohistan District": ("part_of", "Kohistan"),
    "Chiniot District": ("carved_from", "Jhang"),
    "Nankana Sahib District": ("carved_from", "Sheikhpura"),
    "Duki District": ("carved_from", "Loralai"),
    "Harnai District": ("carved_from", "Sibi"),
    "Chaman District": ("carved_from", "Qilla Abdullah"),
    "Sohbatpur District": ("carved_from", "Jafarabad"),
    "Sujawal District": ("carved_from", "Thatta"),
    "Surab District": ("carved_from", "Kalat"),
    "Sherani District": ("carved_from", "Zhob"),
    "Washuk District": ("carved_from", "Kharan"),
    "Larkana District": ("shape_missing", ""),
}

# Canonical units present in some vocabularies but absent from the population panel.
# (name, province, unit_kind, geometry_relation, parent_shape, note)
EXTRA_CANONICAL = [
    ("Cholistan Area", "Punjab", "statistical_area", "no_geometry", "",
     "PBS 7th Agricultural Census reporting unit inside Bahawalpur/Bahawalnagar/R.Y.Khan; "
     "no census district and no geometry of its own"),
    ("Kolai Palas District", "Khyber Pakhtunkhwa", "census_district", "part_of", "Kohistan",
     "a real 2017-created district the Agricultural Census reports separately; the "
     "population panel folds it into Upper/Lower Kohistan"),
    ("Torghar District", "Khyber Pakhtunkhwa", "census_district", "carved_from", "Mansehra",
     "created 2011 out of Mansehra; reported by the Agricultural Census, absent from the "
     "population panel's district set"),
]

# Pre-subdivision districts that live data still names: BoS registration rows from the
# 2000s say "Karachi", "Chitral", "Kohistan" - the districts as they then were, each now
# subdivided. They are canonical rows of their own (unit_kind legacy_aggregate) because a
# historical record naming them is not misspelling anything; mapping them onto any single
# successor would misallocate the others' share.
LEGACY_AGGREGATES = {
    "Karachi": ("Sindh", "Karachi"),
    "Chitral": ("Khyber Pakhtunkhwa", "Chitral"),
    "Kohistan": ("Khyber Pakhtunkhwa", "Kohistan"),
}

# Geometry-side units outside the census panel: the territories. AJK is ONE polygon in this
# file; GB has ten district polygons. They are canonical rows (the grid needs them named)
# with status=territory, and the national statistical panels do not report them.
TERRITORY_SHAPES = {
    "Azad Kashmir": "Azad Jammu and Kashmir",
    "Astore": "Gilgit-Baltistan", "Diamer": "Gilgit-Baltistan", "Ghanche": "Gilgit-Baltistan",
    "Ghizer": "Gilgit-Baltistan", "Gilgit": "Gilgit-Baltistan", "Hunza": "Gilgit-Baltistan",
    "Kharmang": "Gilgit-Baltistan", "Nagar": "Gilgit-Baltistan", "Shigar": "Gilgit-Baltistan",
    "Skardu": "Gilgit-Baltistan",
}

# Raw census-ingest spellings preserved in the waste alias file (the PBS publication's own
# abbreviations, normalised away before the panel was written).
PBS_RAW_VARIANTS = {
    "Karachi Keamari": "Keamari District",
    "Karachi Korangi": "Korangi District",
    "Karachi Malir": "Malir District",
    "S. Benazirabad": "Shaheed Benazirabad District",
    "Tando M. Khan": "Tando Muhammad Khan District",
}

# BoS registration-table spellings -> canonical name, where normalise() cannot bridge.
BOS_VARIANTS = {
    "Barkan": "Barkhan District",
    "Bolan": "Kachhi District",                         # old name
    "Turbat": "Kech District",                          # old name
    "Lora Lai": "Loralai District",
    "Dukki": "Duki District",
    "Lakki": "Lakki Marwat District",
    "M.B.Din": "Mandi Bahauddin District",
    "D.G.Khan": "Dera Ghazi Khan District",
    "D.I.Khan": "Dera Ismail Khan District",
    "R.Y.Khan": "Rahim Yar Khan District",
    "T.T.Singh": "Toba Tek Singh District",
    "N.Waziristan": "North Waziristan District",
    "Tor Ghar": "Torghar District",
    "Tando Mohammad Khan": "Tando Muhammad Khan District",
    "Chaghi": "Chagai District",
    "Chitral Lower": "Lower Chitral District",
    "Chitral Upper": "Upper Chitral District",
    "Dir Lower": "Lower Dir District",
    "Dir Upper": "Upper Dir District",
    "Kohistan Lower": "Lower Kohistan District",
    "Kohistan Upper": "Upper Kohistan District",
    "Kohistan Kolai Palas": "Kolai Palas District",
    "Jaffarabad": "Jaffarabad District",
    "Kamber Shahdadkot": "Kambar Shahdad Kot District",
    "Naushero Feroze": "Naushahro Feroze District",
    "Shaheed Benazirabad": "Shaheed Benazirabad District",
    "Larkana": "Larkana District",
    "Nankana Sahib": "Nankana Sahib District",
    "Sheikhupura": "Sheikhupura District",
    "Vehari": "Vehari District",
    "Chiniot": "Chiniot District",
    "Killa Abdullah": "Killa Abdullah District",
}

# Ag-census spellings needing more than normalise() (mostly shared with PBS).
AGCENSUS_VARIANTS = {
    "Kolai Palas Kohistan District": "Kolai Palas District",
    "Torghar District": "Torghar District",
    "Cholistan Area": "Cholistan Area",
}

# The agriculture/railways engine outputs use geoBoundaries spellings plus one residual row.
ENGINE_RESIDUAL = "Other (GB/AJK/ICT residual)"


def slug(name, province):
    base = normalise(name).replace(" ", "_")
    prov = {"Punjab": "punjab", "Sindh": "sindh", "Khyber Pakhtunkhwa": "kp",
            "Balochistan": "balochistan", "Other": "ict",
            "Azad Jammu and Kashmir": "ajk", "Gilgit-Baltistan": "gb"}[province]
    return "%s_%s" % (prov, base)


def build():
    shapes = {}
    for feature in json.load(open(GEOJSON))["features"]:
        p = feature["properties"]
        shapes[p["shapeName"]] = p["shapeID"]

    pbs = {}
    for row in csv.DictReader(open(POPULATION)):
        if row.get("district"):
            pbs[row["district"]] = row["province"]

    geo_to_pbs = {}
    for shape_name in shapes:
        target = GEO_VARIANTS.get(shape_name)
        if target is None:
            for census_name in pbs:
                if normalise(census_name) == normalise(shape_name):
                    target = census_name
                    break
        if target is not None:
            geo_to_pbs[shape_name] = target

    canonical = []
    crosswalk = []

    def add_cross(observed, system, adm2_id, match_kind, note=""):
        crosswalk.append({"observed_name": observed, "system": system, "adm2_id": adm2_id,
                          "match_kind": match_kind, "note": note})

    pbs_to_shape = {census: shape for shape, census in geo_to_pbs.items()}
    for census_name in sorted(pbs):
        province = pbs[census_name]
        adm2_id = slug(census_name, province)
        shape_name = pbs_to_shape.get(census_name, "")
        if shape_name:
            relation, shape_id = "one_to_one", shapes[shape_name]
        else:
            relation, parent = NO_OWN_SHAPE[census_name]
            shape_name = parent
            shape_id = shapes[parent] if parent else ""
        canonical.append({
            "adm2_id": adm2_id, "canonical_name": census_name, "province_id": province,
            "adm1_name": "Islamabad Capital Territory" if province == "Other" else province,
            "unit_kind": "census_district",
            "geometry_version": GEOMETRY_VERSION, "shape_id": shape_id,
            "shape_name": shape_name, "geometry_relation": relation,
            "effective_date": "census_2023", "status": "active",
            "note": ("no polygon in the boundary file although the district predates the "
                     "vintage - a distributor defect; its cells rasterise as outside any "
                     "district today" if relation == "shape_missing" else ""),
        })
        add_cross(census_name, "pbs_census_2023", adm2_id, "canonical")
        if shape_name and relation == "one_to_one" and normalise(shape_name) != normalise(census_name):
            add_cross(shape_name, "geoboundaries_2019", adm2_id, "spelling_variant",
                      "geometry file spelling")
        elif shape_name and relation == "one_to_one":
            add_cross(shape_name, "geoboundaries_2019", adm2_id, "exact")

    for name, province, kind, relation, parent, note in EXTRA_CANONICAL:
        adm2_id = slug(name, province)
        canonical.append({
            "adm2_id": adm2_id, "canonical_name": name, "province_id": province,
            "adm1_name": province, "unit_kind": kind,
            "geometry_version": GEOMETRY_VERSION,
            "shape_id": shapes[parent] if parent else "", "shape_name": parent,
            "geometry_relation": relation, "effective_date": "ag_census_2024",
            "status": "statistical_area" if kind == "statistical_area" else "active",
            "note": note})
        add_cross(name, "pbs_ag_census_2024", adm2_id, "canonical")

    for shape_name, territory in sorted(TERRITORY_SHAPES.items()):
        adm2_id = slug(shape_name, territory)
        canonical.append({
            "adm2_id": adm2_id, "canonical_name": shape_name, "province_id": "Other",
            "adm1_name": territory, "unit_kind": "territory_unit",
            "geometry_version": GEOMETRY_VERSION, "shape_id": shapes[shape_name],
            "shape_name": shape_name, "geometry_relation": "one_to_one",
            "effective_date": "boundary_2019", "status": "territory",
            "note": "outside the national statistical panels; carried for the grid and the "
                    "provincial Other residual"})
        add_cross(shape_name, "geoboundaries_2019", adm2_id, "exact")

    for name, (province, shape_name) in sorted(LEGACY_AGGREGATES.items()):
        adm2_id = slug(name + " legacy", province)
        canonical.append({
            "adm2_id": adm2_id, "canonical_name": name, "province_id": province,
            "adm1_name": province, "unit_kind": "legacy_aggregate",
            "geometry_version": GEOMETRY_VERSION, "shape_id": shapes[shape_name],
            "shape_name": shape_name, "geometry_relation": "legacy_aggregate",
            "effective_date": "pre_subdivision", "status": "superseded",
            "note": "the district before its subdivision; live historical panels still "
                    "report under this name and it maps one-to-one onto the shape"})
        add_cross(name, "provincial_bos", adm2_id, "legacy_aggregate")
        add_cross(name, "geoboundaries_2019", adm2_id, "legacy_aggregate")

    canonical.append({
        "adm2_id": "other_residual", "canonical_name": ENGINE_RESIDUAL,
        "province_id": "Other", "adm1_name": "GB/AJK/ICT",
        "unit_kind": "residual", "geometry_version": GEOMETRY_VERSION,
        "shape_id": "", "shape_name": "", "geometry_relation": "no_geometry",
        "effective_date": "n/a", "status": "residual",
        "note": "the engine outputs' catch-all row for emissions allocated outside the four "
                "provinces"})
    add_cross(ENGINE_RESIDUAL, "engine_output", "other_residual", "canonical")

    by_canonical = {r["canonical_name"]: r["adm2_id"] for r in canonical}
    for observed, target in sorted(BOS_VARIANTS.items()):
        add_cross(observed, "provincial_bos", by_canonical[target],
                  "old_name" if observed in ("Bolan", "Turbat") else "spelling_variant")
    for observed, target in sorted(PBS_RAW_VARIANTS.items()):
        add_cross(observed, "pbs_census_2023", by_canonical[target], "raw_publication_spelling")
    for observed, target in sorted(AGCENSUS_VARIANTS.items()):
        if observed != target:
            add_cross(observed, "pbs_ag_census_2024", by_canonical[target],
                      "spelling_variant")

    canonical.sort(key=lambda r: r["adm2_id"])
    crosswalk.sort(key=lambda r: (r["system"], r["observed_name"]))
    return canonical, crosswalk


def render(rows, fields):
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def main(check=False):
    canonical, crosswalk = build()
    canon_text = render(canonical, list(canonical[0]))
    cross_text = render(crosswalk, list(crosswalk[0]))
    if check:
        for path, text in ((CANONICAL_OUT, canon_text), (CROSSWALK_OUT, cross_text)):
            if not os.path.exists(path) or open(path, encoding="utf-8").read() != text:
                print("%s is stale; run python3 scripts/build_adm2_package.py"
                      % os.path.relpath(path, ROOT))
                return 1
        print("ADM2 package is current.")
        return 0
    open(CANONICAL_OUT, "w", encoding="utf-8").write(canon_text)
    open(CROSSWALK_OUT, "w", encoding="utf-8").write(cross_text)
    # The release-stamped crosswalk ARTIFACT (rc14, the ninth review's item 6):
    # the crosswalk lived only as data/ inputs, so a downstream joiner had no
    # published product to cite. One denormalised row per canonical unit, under
    # outputs/ where the manifest hashes it.
    publish = os.path.join(ROOT, "outputs", "pakemis_adm2_crosswalk.csv")
    alias_count = {}
    for r in crosswalk:
        alias_count[r["adm2_id"]] = alias_count.get(r["adm2_id"], 0) + 1
    with open(publish, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "adm2_id", "canonical_name", "province_id", "unit_kind",
            "geometry_version", "shape_id", "shape_name", "geometry_relation",
            "status", "observed_aliases", "note"])
        w.writeheader()
        for u in canonical:
            w.writerow({
                "adm2_id": u["adm2_id"], "canonical_name": u["canonical_name"],
                "province_id": u["province_id"], "unit_kind": u["unit_kind"],
                "geometry_version": u["geometry_version"],
                "shape_id": u["shape_id"], "shape_name": u["shape_name"],
                "geometry_relation": u["geometry_relation"],
                "status": u["status"],
                "observed_aliases": alias_count.get(u["adm2_id"], 0),
                "note": u["note"]})
    print("wrote %s (%d units), %s (%d rows) and %s"
          % (os.path.relpath(CANONICAL_OUT, ROOT), len(canonical),
             os.path.relpath(CROSSWALK_OUT, ROOT), len(crosswalk),
             os.path.relpath(publish, ROOT)))
    return 0


if __name__ == "__main__":
    from pkinv.activity.store import staging_inputs
    with staging_inputs():
        raise SystemExit(main(check="--check" in sys.argv))
