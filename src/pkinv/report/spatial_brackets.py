"""Spatial-allocation brackets: what an admissible alternative would move, per stream.

WHY. The parametric interval prices factor and activity uncertainty; the structural
bridge prices magnitude forks; NOTHING priced the spatial allocation - how different
the map would look under the other defensible proxy. The fifth review asked for
spatial-allocation uncertainty per stream, and this module is the seed: every row of
data/stream_spatial_alternatives.csv resolves either to a priced province-level bracket
(computed from published share vectors, no grid re-runs), to a declared within-province
deferral (the cube's weights are share-constrained per province, so a raster swap
cannot move a province marginal - the honest bracket there is a grid-level product,
named and deferred), or to the S4 no-alternative admission.

NO PROBABILITIES, and no error bars: a bracket is the spread between two defensible
readings, not a distribution around a truth. The transport registration bracket in
particular is allocation disagreement, not error against an observation - no
independent provincial fuel record exists (validation registry, geo-transport-proxy).

Usage:  python3 -m pkinv.report.spatial_brackets
Writes: outputs/pakemis_spatial_brackets.csv
"""

from pkinv.assets import asset_path
import csv
import os

from pkinv.paths import DATA, OUTPUTS

REFERENCE = "FY2023-24"
from pkinv.activity.store import read_rows
from pkinv.core.io import write_table

FIELDS = ("alternative_id", "module", "stream_match", "level", "province",
          "reference_share", "alternative_share", "spread_pp", "status",
          "source", "note")


def _rows(path):
    return read_rows(path)


def registry():
    return _rows(asset_path(DATA, "stream_spatial_alternatives.csv"))


def _streams():
    return _rows(asset_path(OUTPUTS, "pakemis_source_streams.csv"))


def _matched_streams(entry, streams):
    match = entry["stream_match"]
    if match.startswith("module="):
        module = match.split("=", 1)[1]
        return [s for s in streams if s["module"] == module]
    if match.startswith("geometry="):
        # rc47 Wave 3: the aviation cruise streams share their profile id with the
        # LTO streams (both ride the movements proxy at province level), so a
        # profile match cannot separate them - but their GEOMETRY is exactly what
        # the admission is about, so the matcher says so directly.
        geometry = match.split("=", 1)[1]
        return [s for s in streams if s["geometry_id"] == geometry
                and s["module"] == entry["module"]]
    profiles = set(match.split(";"))
    return [s for s in streams if s["spatial_profile_id"] in profiles
            and s["module"] == entry["module"]]


def _registration_bracket(entry, fuel_col):
    """Fuel-sales vs registration provincial shares, from the published comparison."""
    rows = []
    worst = 0.0
    for r in _rows(asset_path(OUTPUTS,
                                "transport_provincial_proxy_comparison_2024.csv")):
        ref = float(r[fuel_col])
        alt = float(r["share_registration"])
        spread = (ref - alt) * 100.0
        worst = max(worst, abs(spread))
        rows.append({"province": r["province"], "reference_share": round(ref, 6),
                     "alternative_share": round(alt, 6),
                     "spread_pp": round(spread, 3)})
    return rows, worst


def _shape_year_bracket():
    """The FY2024-25 vs FY2021-22 borrowed-shape bracket, re-published per province
    with the fuel dimension collapsed to the worst case per province."""
    per_province = {}
    for r in _rows(asset_path(OUTPUTS, "transport_provincial_shape_brackets.csv")):
        spread = float(r["spread_pp"])
        province = r["province"]
        held = per_province.get(province)
        if held is None or abs(spread) > abs(held[2]):
            per_province[province] = (float(r["share_reference_shape"]),
                                      float(r["share_bracket_shape"]), spread)
    rows = []
    worst = 0.0
    for province, (ref, alt, spread) in sorted(per_province.items()):
        worst = max(worst, abs(spread))
        rows.append({"province": province, "reference_share": round(ref, 6),
                     "alternative_share": round(alt, 6),
                     "spread_pp": round(spread, 3)})
    return rows, worst


def _karachi_within_province_bracket():
    """(rows, worst) for the one within-province figure OCAC publishes.

    rc62. Every diffuse industry stream splits its provincial mass by ESA built-up area, and
    that surface has never been testable - no held source states industrial fuel below the
    province. Except once: OCAC prints KARACHI as a named sub-area of SINDH, so for that one
    district-group the publication says what share of Sindh's industrial furnace oil it takes.
    Built-up says 47.9 percent of Sindh; OCAC says 82.0 to 90.9 percent across the four
    complete panel years. This prices that gap, per year, as what it is - a measured
    disagreement between the executed surface and an observation, not an alternative
    allocation, because there is no second allocation to run.
    """
    from pkinv.activity.store import read_rows as _read
    from pkinv.sectors.industry import province_shape as ips
    from pkinv.core.gis.grid import build_grid
    from pkinv.report.air_spatial_by_year import shape_frame

    grid = build_grid()
    karachi_shape = None
    for idx, shape_id, adm2_ids, _status, province in shape_frame(grid):
        if "sindh_karachi" in adm2_ids:
            karachi_shape = (shape_id, adm2_ids)
            break
    # what built-up gives that shape inside Sindh, from the shipped reference vector
    ref_national = sindh_national = 0.0
    for r in _read(asset_path(OUTPUTS, "pakemis_adm2_stream_by_year.csv")):
        if ("industrial-furnace-oil-co2" not in r.get("source_stream_id", "")
                or r["period_id"] != REFERENCE):
            continue
        value = float(r.get("emissions_Gg") or 0)
        if r.get("province") == "Sindh":
            sindh_national += value
            if karachi_shape and r["adm2_ids"] == karachi_shape[1]:
                ref_national += value
    reference = (ref_national / sindh_national) if sindh_national else 0.0

    rows, worst = [], 0.0
    for fiscal_year in ips.complete_years("furnace_oil"):
        observed = ips.karachi_share_of_sindh("furnace_oil", fiscal_year)
        if observed is None:
            continue
        spread = 100.0 * (observed - reference)
        worst = max(worst, abs(spread))
        rows.append({"province": "Sindh/FY%d-%02d" % (fiscal_year - 1, fiscal_year % 100),
                     "reference_share": round(reference, 6),
                     "alternative_share": round(observed, 6),
                     "spread_pp": round(spread, 3)})
    return rows, worst


def _coal_basis_bracket(entry):
    """Grid coal's provincial split on its two energy weights, reference year.

    reference    the committed row: station tonnage at the rank-default calorific value,
                 which is how the national coal account is booked (rc66)
    alternative  the row every release through rc65 applied: the same tonnage at per-plant
                 implied calorific values, read from the pinned rc65 baseline and not
                 recomputed, so the bracket is against what was actually shipped
    """
    committed = {r["proxy"]: r for r in _rows(asset_path(DATA, "province_shares.csv"))}
    from pkinv.paths import ROOT
    with open(os.path.join(ROOT, entry["alternative_source"]), encoding="utf-8",
              newline="") as handle:
        former = {r["proxy"]: r for r in csv.DictReader(handle)}
    rows, worst = [], 0.0
    for province in ("Punjab", "Sindh", "Khyber Pakhtunkhwa", "Balochistan", "Other"):
        ref = float(committed["power_coal"][province])
        alt = float(former["power_coal"][province])
        if ref == 0.0 and alt == 0.0:
            continue
        spread = 100.0 * (alt - ref)
        worst = max(worst, abs(spread))
        rows.append({"province": province, "reference_share": round(ref, 6),
                     "alternative_share": round(alt, 6), "spread_pp": round(spread, 3)})
    return rows, worst


def build():
    streams = _streams()
    out = []

    def emit(entry, province, ref, alt, spread, status, note):
        out.append({"alternative_id": entry["alternative_id"],
                    "module": entry["module"],
                    "stream_match": entry["stream_match"],
                    "level": entry["level"], "province": province,
                    "reference_share": ref, "alternative_share": alt,
                    "spread_pp": spread, "status": status,
                    "source": entry["alternative_source"], "note": note})

    for entry in registry():
        matched = _matched_streams(entry, streams)
        if not matched:
            raise SystemExit("%s matches no stream" % entry["alternative_id"])
        if entry["status"] == "priced":
            if entry["alternative_id"] == "transport_petrol_registration":
                rows, worst = _registration_bracket(entry, "petrol_share_fuel")
            elif entry["alternative_id"] == "transport_diesel_registration":
                rows, worst = _registration_bracket(entry, "diesel_share_fuel")
            elif entry["alternative_id"] == "transport_shape_year":
                rows, worst = _shape_year_bracket()
            elif entry["alternative_id"] == "power_coal_provincial_basis":
                rows, worst = _coal_basis_bracket(entry)
            else:
                raise SystemExit("no pricer for %s" % entry["alternative_id"])
            for r in rows:
                emit(entry, r["province"], r["reference_share"],
                     r["alternative_share"], r["spread_pp"], "priced",
                     entry["why_admissible"])
            emit(entry, "MAX_ABS", "", "", round(worst, 3), "priced",
                 "largest absolute provincial disagreement between the two bases; "
                 "allocation spread, not error against an observation")
        elif entry["status"] == "priced_adm2":
            emit(entry, "all", "", "", "", "priced_adm2",
                 "priced at ADM2 level in outputs/pakemis_spatial_brackets_adm2.csv "
                 "(province marginals are share-constrained, so the province-level "
                 "spread is zero by construction) - %s" % entry["why_admissible"])
        elif entry["status"] == "structurally_invariant_at_adm2":
            emit(entry, "all", "", "", 0.0, "structurally_invariant_at_adm2",
                 "the district panel fixes each shape's mass and the raster moves "
                 "cells within shapes only: ADM2 spread exactly zero by "
                 "construction, proof and per-cell magnitude in "
                 "outputs/pakemis_spatial_brackets_adm2.csv - %s"
                 % entry["why_admissible"])
        elif entry["status"] == "declared_deferred":
            emit(entry, "all", "", "", "", "declared_deferred",
                 "province marginals are share-constrained, so this alternative "
                 "moves mass within provinces only; its bracket is a grid-level "
                 "product, deferred and declared - %s" % entry["why_admissible"])
        elif entry["status"] == "no_alternative":
            for s in matched:
                emit(entry, "all", "", "", "", "no_alternative_declared",
                     "%s; stream %s" % (entry["why_admissible"],
                                        s["source_stream_id"]))
        elif entry["status"] == "measured_disagreement":
            # rc62: not an alternative allocation - an OBSERVATION that contradicts the
            # executed surface inside a province. There is no second allocation to run, so
            # what is priced is the gap itself, per year, and the note says so rather than
            # letting a reader mistake it for a bracket between two candidate maps.
            rows, worst = _karachi_within_province_bracket()
            for r in rows:
                emit(entry, r["province"], r["reference_share"],
                     r["alternative_share"], r["spread_pp"], "measured_disagreement",
                     entry["why_admissible"])
            emit(entry, "MAX_ABS", "", "", round(worst, 3), "measured_disagreement",
                 "the largest gap between the executed within-province surface and the one "
                 "within-province figure the source publishes; a measured error, NOT an "
                 "allocation spread")
        else:
            raise SystemExit("unknown status %r" % entry["status"])
    return out


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    rows = build()
    path = asset_path(OUTPUTS, "pakemis_spatial_brackets.csv")
    write_table(path, list(FIELDS), rows)
    priced = [r for r in rows if r["province"] == "MAX_ABS"]
    print("spatial brackets -> %s (%d rows)" % (os.path.basename(path), len(rows)))
    for r in priced:
        print("  %-34s max |spread| %6.2f pp" % (r["alternative_id"],
                                                 float(r["spread_pp"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
