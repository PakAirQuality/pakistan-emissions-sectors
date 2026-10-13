"""Waste release geography, published as its own objects (rc13).

THE THREE OBJECTS the eighth review asked to see separated, and where each lives:
  ORIGIN     outputs/waste_district_2024.csv (existing) - where the generating
             people live; census population, exact provincial closure.
  FATE       outputs/waste_ledger_2024.csv (existing) - what happens to the mass:
             collected/disposed, burned, and the 6.27 Mt UNRESOLVED row.
  RELEASE    this module - where the DISPOSED mass could physically emit, as far
             as the held evidence can say, with the unassignable share carried as
             EXPLICIT UNASSIGNED MASS rather than forced onto the nearest site.

WHAT THE EVIDENCE PERMITS. The only release geometry held is the OSM landfill
seed: 56 polygons (13 named) over 22 of 147 ADM2 units, with the coverage mask's
own sentence - "unmapped means nobody drew one, not that no disposal happens
here". So the assignment is deliberately weak: a district's disposal-site
emissions are assigned to its OWN mapped candidates (equal split, capacity
unknown and declared) only where candidates exist; everywhere else the mass is
UNASSIGNED with a reason. Nothing crosses a district boundary - forcing mass to
the nearest mapped site would launder OSM mapping effort into transport claims
nobody made. Scope is the DISPOSAL stream only: open burning is dispersed by
construction, and wastewater release (drains, works, outfalls) has no held
geometry at all - both stated, not implied.

ALLOCATION DISCIPLINE. These are observation-grade objects: the geometry set
obs:waste_release_candidates is kind=observation ("observation evidence, never
an allocation basis"), no stream registry row points here, and the sector's
cube allocation remains origin-based and says so. The prospective landfill
facility set is untouched.

Usage:  python3 -m pkinv.sectors.waste.gis.release_candidates
Writes: outputs/waste_release_candidates_2024.csv
        outputs/waste_release_assignment_2024.csv
"""
from pkinv.activity.store import input_exists as _input_exists
from pkinv.activity.store import read_rows as _activity_rows
import csv
import os

from pkinv.core import adm2
from pkinv.paths import DATA, OUTPUTS
from pkinv.core.io import write_table

ASSETS = os.path.join(DATA, "gis", "landfills", "pak_landfill_assets.csv")
COVERAGE = os.path.join(DATA, "gis", "landfills", "pak_landfill_coverage.csv")
ORIGIN = os.path.join(OUTPUTS, "waste_district_2024.csv")

DISPOSAL_STREAM = "Solid waste disposal"
TOL = 1e-9


HYDROWASTE = os.path.join(DATA, "activity", "waste", "hydrowaste_pak.csv")
CLIMATETRACE = os.path.join(os.path.dirname(DATA), "sources", "ClimateTRACE",
                            "climatetrace_waste_PAK_sources.json")
# rc41: the engine reads the consumed derivative of that JSON (scripts/
# ingest_climatetrace_waste.py proves it against the document wherever it is held); the
# package registers the document without shipping it.
CLIMATETRACE_TABLE = os.path.join(DATA, "activity", "waste", "climatetrace_waste_sites_pak.csv")


def candidates():
    rows = []
    for r in _activity_rows(ASSETS, comments=False):
        rows.append({
            "candidate_id": r["landfill_id"],
            "candidate_kind": "disposal_site",
            "name": r["name"] or "",
            "quality": r["quality"],
            "latitude": r["latitude"], "longitude": r["longitude"],
            "area_m2": r["area_m2"],
            "adm2_ids": r["adm2_ids"], "adm2_status": r["adm2_status"],
            "dataset": r["dataset"], "licence": r["licence"],
            "release_confidence": ("named_site" if r["name"]
                                   else r["quality"]),
            "note": "release CANDIDATE, never an allocation basis: the "
                    "assignment product carries what mass could plausibly "
                    "reach it and what mass stays unassigned"})
    # HydroWASTE WWTPs (rc13 fetch): the wastewater side's first candidates.
    if _input_exists(HYDROWASTE):
        for r in _activity_rows(HYDROWASTE, comments=False):
            rows.append({
                "candidate_id": "wwtp_hydrowaste_%s" % r["WASTE_ID"],
                "candidate_kind": "wastewater_treatment_plant",
                "name": r["WWTP_NAME"] or "",
                "quality": "hydrowaste_qual_loc_%s" % (r["QUAL_LOC"] or "na"),
                "latitude": r["LAT_WWTP"], "longitude": r["LON_WWTP"],
                "area_m2": "",
                "adm2_ids": "", "adm2_status": "not_joined",
                "dataset": "HydroWASTE v1.0 (Ehalt Macedo et al. 2022)",
                "licence": "CC-BY-4.0",
                "release_confidence": "global_register_location",
                "note": "wastewater release CANDIDATE from a global register "
                        "- a location, never evidence that treatment happens "
                        "at more than the modelled 1 percent share; outfall "
                        "coordinates and population served in "
                        "data/activity/waste/hydrowaste_pak.csv"})
    # Climate TRACE waste sources (rc13 fetch): comparator/candidate rows only.
    if _input_exists(CLIMATETRACE_TABLE):
        from pkinv.activity.store import read_rows
        for s in read_rows(CLIMATETRACE_TABLE):
            kind = ("disposal_site_modelled"
                    if s["subsector"] == "solid-waste-disposal"
                    else "wastewater_modelled")
            rows.append({
                "candidate_id": "climatetrace_%s" % s["source_id"],
                "candidate_kind": kind,
                "name": s["name"].replace("Unknown name", ""),
                "quality": s["quality"],
                "latitude": s["latitude"],
                "longitude": s["longitude"],
                "area_m2": "",
                "adm2_ids": "", "adm2_status": "not_joined",
                "dataset": "Climate TRACE v7 waste sources (API pull, "
                           "sources/ClimateTRACE)",
                "licence": "CC-BY-4.0",
                "release_confidence": "modelled_source_location",
                "note": "COMPARATOR/CANDIDATE per the eighth review's own "
                        "caveat: Climate TRACE's waste sources are modelled, "
                        "never ground truth; kept beside the OSM and "
                        "HydroWASTE candidates for cross-reference"})
    return rows


def assignment():
    cands = candidates()
    by_adm2 = {}
    for c in cands:
        for a in c["adm2_ids"].split(";"):
            if a:
                by_adm2.setdefault(a, []).append(c["candidate_id"])
    cov = {}
    for r in _activity_rows(COVERAGE, comments=False):
        cov[r["adm2_id"]] = r["coverage"]

    out = []
    total = assigned_total = 0.0
    for r in _activity_rows(ORIGIN, comments=False):
        if r["stream"] != DISPOSAL_STREAM:
            continue
        mass = float(r["co2e_Mt_AR5"])
        total += mass
        try:
            ids = [adm2.resolve(r["district"])]
        except KeyError:
            ids = []
        hit = [c for a in ids for c in by_adm2.get(a, [])]
        coverage = (cov.get(ids[0], "unknown") if ids else "unknown")
        if hit:
            assigned_total += mass
            out.append({
                "district": r["district"], "province": r["province"],
                "adm2_id": ids[0], "origin_co2e_Mt": round(mass, 7),
                "assignment_status": "assigned_candidates_within_district",
                "candidate_ids": ";".join(sorted(hit)),
                "candidate_count": len(hit),
                "assigned_co2e_Mt": round(mass, 7),
                "unassigned_co2e_Mt": 0.0,
                "release_coverage": coverage,
                "basis": "equal split across the district's own mapped "
                         "candidates - capacity unknown, DECLARED; nothing "
                         "crosses a district boundary",
                "note": ""})
        else:
            reason = ("no_mapped_site_in_district"
                      if coverage == "not_mapped_in_osm"
                      else "no_candidate_resolves")
            out.append({
                "district": r["district"], "province": r["province"],
                "adm2_id": ids[0] if ids else "", "origin_co2e_Mt": round(mass, 7),
                "assignment_status": "UNASSIGNED",
                "candidate_ids": "", "candidate_count": 0,
                "assigned_co2e_Mt": 0.0,
                "unassigned_co2e_Mt": round(mass, 7),
                "release_coverage": coverage,
                "basis": reason,
                "note": "unmapped means nobody drew a polygon, not that no "
                        "disposal happens here - the mass stays with its "
                        "origin district, explicitly unassigned, never "
                        "forced to the nearest mapped site"})
    # closure: assigned + unassigned must partition the origin disposal mass
    check = sum(r["assigned_co2e_Mt"] + r["unassigned_co2e_Mt"] for r in out)
    if abs(check - total) > TOL * max(1.0, total):
        raise SystemExit("release assignment does not partition the origin "
                         "disposal mass: %r vs %r" % (check, total))
    return out, total, assigned_total


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    cands = candidates()
    write_table(os.path.join(OUTPUTS, "waste_release_candidates_2024.csv"), list(cands[0].keys()), cands)
    rows, total, assigned = assignment()
    write_table(os.path.join(OUTPUTS, "waste_release_assignment_2024.csv"), list(rows[0].keys()), rows)
    n_un = sum(1 for r in rows if r["assignment_status"] == "UNASSIGNED")
    print("waste release objects -> waste_release_candidates_2024.csv (%d "
          "candidates) + waste_release_assignment_2024.csv" % len(cands))
    print("  disposal origin %.4f Mt: %.4f assigned to within-district "
          "candidates, %.4f Mt EXPLICITLY UNASSIGNED across %d districts "
          "(%.0f%% of the category - the honest measure of how far the release "
          "map is from existing)"
          % (total, assigned, total - assigned, n_un,
             100 * (total - assigned) / total))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
