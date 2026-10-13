"""The air spatial support ledger and the uncertainty split, per period.

TWO PRODUCTS, ONE JOIN. The by-year air spatial tables carry no evidence columns,
deliberately (the badge belongs to the weight registry, derived from what the build
DID - see spatial_by_year.py). This script publishes the join:

  pakemis_air_spatial_support_by_year.csv - every (period, configuration, anchor,
    pollutant) mass beside its registry row: the activity year, the weight period, the
    proxy operator, the pattern hash and the evidence grade PRESERVED AS SEPARATE
    COLUMNS, never collapsed into a composite score.

  pakemis_air_uncertainty_split_by_year.csv - per (period, configuration, pollutant),
    the two halves of the uncertainty REPORTED SEPARATELY, never combined: the
    activity/factor half (the reference-year sector layers' mass-weighted uncert_pct -
    the percent structure is the reference year's, and the basis column says so) and
    the spatial half measured for THAT year from the registry (what share of the mass
    rode the year's own pattern, a borrowed pattern, a substituted surface, or was
    never placed below ADM1).

Runs AFTER the weight registry phase (its input is the registry the build's own record
generates) and after the air panel.

Usage:  python3 -m scripts.build_air_spatial_support
"""
import collections
import csv
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from pkinv.assets import asset_path

from pkinv.core.io import read_rows                                # noqa: E402
from pkinv.paths import OUTPUTS                                    # noqa: E402
from pkinv.report.air_spatial_by_year import load_atoms            # noqa: E402

REGISTRY = asset_path(OUTPUTS, "pakemis_spatial_weights_by_year.csv")
SUPPORT_OUT = asset_path(OUTPUTS, "pakemis_air_spatial_support_by_year.csv")
SPLIT_OUT = asset_path(OUTPUTS, "pakemis_air_uncertainty_split_by_year.csv")

# the reference-year sector air layers: the activity/factor uncert basis
LAYER_FILES = ("air_pollutants_2024.csv", "residential_air_pollutants_2024.csv",
               "transport_air_pollutants_2024.csv", "waste_air_pollutants_2024.csv",
               "aviation_air_pollutants_fy2023_24.csv",
               "railways_air_pollutants_2024.csv")

SUPPORT_FIELDS = ("period_id", "configuration_id", "sector_id", "source_stream_id",
                  # rc59: "" | kiln_frame:FCBK | kiln_frame:ZZ | adm1_only
                  # rc60: national_only - the admitted power SO2, which has no defensible
                  # province either and so is placed at no sub-national grain at all
                  "spatial_frame",
                  "pollutant", "emissions_Gg", "spatial_time_basis", "weight_period",
                  "temporal_operator", "pattern_hash", "evidence_grade",
                  "substituted_share", "geometry_id", "surface")
SPLIT_FIELDS = ("period_id", "configuration_id", "pollutant",
                "activity_factor_uncert_pct", "activity_factor_basis",
                "own_pattern_mass_share", "borrowed_pattern_mass_share",
                "substituted_mass_share", "unallocated_mass_share")

OWN_BASES = ("annual_observed_activity", "static_structural")
# the token every row carries; the sentence it stands for lives in the product
# schema: the percent structure is FY2023-24's sector layers, mass-weighted -
# historical magnitudes are observed per year but their factor families are the
# same, so the number transfers while its composition does not. Reported beside
# the spatial half, never combined with it.
AF_BASIS = "reference_year_layers_mass_weighted"


def _af_uncert():
    """{pollutant: mass-weighted uncert_pct} over the reference-year layers."""
    mass = collections.defaultdict(float)
    weighted = collections.defaultdict(float)
    for name in LAYER_FILES:
        for r in read_rows(asset_path(OUTPUTS, name)):
            kt = abs(float(r["emissions_kt"] or 0.0))
            if kt == 0.0 or not r.get("uncert_pct"):
                continue
            mass[r["pollutant"]] += kt
            weighted[r["pollutant"]] += kt * float(r["uncert_pct"])
    return {p: weighted[p] / mass[p] for p in mass}


def _kiln_frames():
    """{kiln_type: pattern_hash} of the typed brick frames, built as the sink builds them."""
    from pkinv.core.gis.grid import build_grid
    from pkinv.report import kiln_frame_vectors
    return {t: f.pattern_hash for t, f in kiln_frame_vectors.build(build_grid()).items()}


def _power_frames():
    """{(frame_id, period_id): Frame} of the admitted power classes, as the sink builds them."""
    from pkinv.core.gis.grid import build_grid
    from pkinv.report import power_admission_vectors as pav
    return {(pav.frame_id(class_id), period_id): f
            for (class_id, period_id), f in pav.build(build_grid()).items()}


def _frame_row(reg, frame, hashes, period_id="", power=None):
    """The registry row as the frame rewrites it (rc59): a typed kiln frame keeps the brick
    stream's basis, operator and grade and carries ITS OWN pattern hash and surface; the
    ADM1-only remainder is the cruise row's shape - unallocated, not placed, no hash."""
    if frame == "":
        return reg
    r = dict(reg)
    if frame.startswith("kiln_frame:"):
        kiln_type = frame.split(":", 1)[1]
        r["pattern_hash"] = hashes[kiln_type]
        r["surface"] = "brick_kiln_points_%s" % kiln_type
        r["substituted_share"] = "0.000000"
        return r
    if frame.startswith("power_admission:"):
        # rc61: a frame with a real, PER-PERIOD vector of its own, built from the reviewed
        # admission register rather than borrowed from the anchor stream. It is year-keyed in
        # the strongest sense the vocabulary has - the pattern is the year's own admitted
        # stations weighted by the year's own SO2 - so it carries `annual_observed_activity`
        # and its own period, not the anchor's. `substituted_share` is the part of the mass
        # placed no finer than a district (one station, Halmore Power, which holds no
        # coordinate); everything else sits on a station's own point.
        f = power[(frame, period_id)]
        r.update(spatial_time_basis="annual_observed_activity",
                 temporal_operator="own_period_pattern",
                 pattern_hash=f.pattern_hash, surface="power_admission_points",
                 weight_period=period_id,
                 substituted_share="%.6f" % f.district_grade_share())
        return r
    if frame == "adm1_only":
        # placed at ADM1 and no finer: unallocated as far as this ledger is concerned, because
        # it measures the evidence behind a PATTERN and this rides none. The level it stops at
        # is recorded by outputs/pakemis_air_unallocated_by_year.csv rather than repeated here.
        r.update(spatial_time_basis="unallocated", temporal_operator="not_placed",
                 pattern_hash="", evidence_grade="NA", substituted_share="0.000000",
                 surface="none", weight_period="")
        return r
    raise SystemExit("unknown spatial frame %r" % frame)


def main():
    atoms = load_atoms()
    registry = {(r["period_id"], r["source_stream_id"]): r
                for r in read_rows(REGISTRY)}
    hashes = None
    power = None
    support = []
    shares = collections.defaultdict(lambda: collections.defaultdict(float))
    for period_id in sorted(atoms):
        # the sector is in the atom key (two sectors may ride one anchor stream): see load_atoms
        for (cfg, sid, frame, sector), by_pol in sorted(atoms[period_id].items()):
            reg = registry.get((period_id, sid))
            if reg is None:
                raise SystemExit("air anchor %s has no %s registry row - the "
                                 "support join is fail-closed" % (sid, period_id))
            if frame.startswith("kiln_frame:") and hashes is None:
                hashes = _kiln_frames()
            if frame.startswith("power_admission:") and power is None:
                power = _power_frames()
            reg = _frame_row(reg, frame, hashes, period_id, power)
            for pol, mass in sorted(by_pol.items()):
                support.append({
                    "period_id": period_id, "configuration_id": cfg,
                    "sector_id": sector, "source_stream_id": sid,
                    "spatial_frame": frame,
                    "pollutant": pol, "emissions_Gg": "%.12g" % mass,
                    "spatial_time_basis": reg["spatial_time_basis"],
                    "weight_period": reg["weight_period"],
                    "temporal_operator": reg["temporal_operator"],
                    "pattern_hash": reg["pattern_hash"],
                    "evidence_grade": reg["evidence_grade"],
                    "substituted_share": reg["substituted_share"],
                    "geometry_id": reg["geometry_id"],
                    "surface": reg["surface"]})
                cell = shares[(period_id, cfg, pol)]
                cell["total"] += mass
                basis = reg["spatial_time_basis"]
                if basis in OWN_BASES:
                    cell["own"] += mass
                elif basis == "reference_shape_backcast":
                    cell["borrowed"] += mass
                elif basis == "unallocated":
                    cell["unallocated"] += mass
                else:
                    raise SystemExit("unrecognised spatial_time_basis %r for %s %s"
                                     % (basis, period_id, sid))
                cell["substituted"] += mass * float(reg["substituted_share"] or 0.0)
    af = _af_uncert()
    split = []
    for (period_id, cfg, pol), cell in sorted(shares.items()):
        total = cell["total"]
        split.append({
            "period_id": period_id, "configuration_id": cfg, "pollutant": pol,
            "activity_factor_uncert_pct": "%.1f" % af[pol],
            "activity_factor_basis": AF_BASIS,
            "own_pattern_mass_share": "%.6f" % (cell["own"] / total),
            "borrowed_pattern_mass_share": "%.6f" % (cell["borrowed"] / total),
            "substituted_mass_share": "%.6f" % (cell["substituted"] / total),
            "unallocated_mass_share": "%.6f" % (cell["unallocated"] / total)})
    for path, fields, rows in ((SUPPORT_OUT, SUPPORT_FIELDS, support),
                               (SPLIT_OUT, SPLIT_FIELDS, split)):
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(fields),
                                    lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
    print("air spatial support ledger: %d rows; uncertainty split: %d rows"
          % (len(support), len(split)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
