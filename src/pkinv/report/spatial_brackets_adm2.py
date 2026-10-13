"""ADM2-level spatial brackets: what the other defensible map says, district by district.

The rc7 seed priced province-level spreads; this module takes the registered
alternatives to the district level - reusing the cube's own weight machinery
(diffuse_weight, district_factors, shape_marginals, and the captive_weight function
lifted out of build() for exactly this purpose), never a second full build.

THREE ALTERNATIVES, THREE HONEST SHAPES:

  transport (registration shares)  PRICED, but derived: transport has no district
      panel, so its ADM2 marginal is share(province) x proxy(shape)/proxy(province) -
      the province bracket pushed through a fixed within-province split. Real per-shape
      numbers, no information the province rows don't already imply; the note says so.

  power captive (points vs builtup fallback)  PRICED, and genuinely new: geocoded
      plants concentrate mass in the handful of shapes containing them, the fallback
      surface spreads it over every built shape. This spread is not derivable from any
      province number.

  residential (builtup vs population)  STRUCTURALLY INVARIANT at ADM2: the district
      panels fix each shape's mass and the raster only redistributes within shapes, so
      an ADM2 bracket would print a column of zeros and invite the wrong conclusion.
      One proof row per stream, with the max per-cell |difference| attached as the
      grid-level magnitude the deferral carries.

Shares are fractions of the stream's NATIONAL mass per shape (summing to 1 with the
declared OUTSIDE row for cells outside every polygon), spread_pp = (ref - alt) x 100.
No probabilities.

Usage:  python3 -m pkinv.report.spatial_brackets_adm2
Writes: outputs/pakemis_spatial_brackets_adm2.csv
"""

from pkinv.assets import asset_path
import csv
import json
import os

from pkinv.paths import DATA, OUTPUTS
from pkinv.activity.store import read_rows
from pkinv.core.io import write_table

FIELDS = ("alternative_id", "module", "stream_match", "level", "shape_id", "adm2_ids",
          "allocation_status", "province", "reference_share", "alternative_share",
          "spread_pp", "absence_reason", "status", "source", "note")


def _rows(path):
    return read_rows(path)


def _registration_shares():
    return {r["province"]: float(r["share_registration"])
            for r in _rows(asset_path(
                OUTPUTS, "transport_provincial_proxy_comparison_2024.csv"))}


def build():
    import numpy as np

    from pkinv.core import adm2 as adm2_core
    from pkinv.core.gis import cube as cube_core
    from pkinv.core.gis.grid import ADM2_PATH, build_grid
    from pkinv.report import grid_cube

    grid = build_grid()
    ctx = cube_core.Context(grid)
    streams = {s["source_stream_id"]: s for s in grid_cube.load_streams()}

    shape_members = adm2_core.shape_to_adm2()
    canonical = adm2_core.load_canonical()
    name_to_idx = {name: i for i, name in enumerate(grid.districts)}
    idx_to_shape = {}
    with open(ADM2_PATH, encoding="utf-8") as handle:
        for feature in json.load(handle)["features"]:
            p = feature["properties"]
            if p["shapeName"] in name_to_idx:
                idx_to_shape[name_to_idx[p["shapeName"]]] = p["shapeID"]

    def shape_vector(weight):
        sums = cube_core.shape_marginals(grid, weight,
                                         cube_core.canonical_shape_province(grid))
        return sums

    out = []

    def emit_pair(alternative_id, module, stream_match, ref_w, alt_w, source, note):
        ref = shape_vector(ref_w)
        alt = shape_vector(alt_w)
        worst = 0.0
        for idx in sorted(idx_to_shape):
            sid = idx_to_shape[idx]
            members = shape_members.get(sid, [])
            provinces = {canonical[m]["province_id"] for m in members}
            status = "one_to_one" if len(members) == 1 else "shared_shape"
            # + 0.0 on every rounded cell below: a sub-half-ulp negative rounds to
            # -0.0, and the SIGN of that nothing flips with the float path run to
            # run - the rc47 Wave 2 noise-gate catch. Adding zero canonicalises it.
            spread = (ref[idx] - alt[idx]) * 100.0
            worst = max(worst, abs(spread))
            out.append({"alternative_id": alternative_id, "module": module,
                        "stream_match": stream_match, "level": "adm2",
                        "shape_id": sid, "adm2_ids": ";".join(members),
                        "allocation_status": status,
                        "province": ";".join(sorted(provinces)),
                        "reference_share": round(ref[idx], 6) + 0.0,
                        "alternative_share": round(alt[idx], 6) + 0.0,
                        "spread_pp": round(spread, 4) + 0.0,
                        "status": "priced", "source": source, "note": note})
        out.append({"alternative_id": alternative_id, "module": module,
                    "stream_match": stream_match, "level": "adm2",
                    "shape_id": "", "adm2_ids": "", "allocation_status": "",
                    "province": "OUTSIDE",
                    "reference_share": round(ref[-1], 6) + 0.0,
                    "alternative_share": round(alt[-1], 6) + 0.0,
                    "spread_pp": round((ref[-1] - alt[-1]) * 100.0, 4) + 0.0,
                    "status": "priced", "source": source,
                    "note": "cells outside every district polygon (the ADM2 view's "
                            "declared slack); kept so the shares sum to 1"})
        for adm2_id, row in sorted(canonical.items()):
            if row["geometry_relation"] in ("shape_missing", "no_geometry") \
                    and row["status"] == "active":
                out.append({"alternative_id": alternative_id, "module": module,
                            "stream_match": stream_match, "level": "adm2",
                            "shape_id": "", "adm2_ids": adm2_id,
                            "allocation_status": row["geometry_relation"],
                            "province": row["province_id"],
                            "reference_share": "", "alternative_share": "",
                            "spread_pp": "", "absence_reason": "unresolved-in-grid",
                            "status": "priced",
                            "source": source,
                            "note": "no polygon; silence must not read as zero "
                                    "disagreement"})
        out.append({"alternative_id": alternative_id, "module": module,
                    "stream_match": stream_match, "level": "adm2",
                    "shape_id": "", "adm2_ids": "", "allocation_status": "",
                    "province": "MAX_ABS", "reference_share": "",
                    "alternative_share": "", "spread_pp": round(worst, 4) + 0.0,
                    "status": "priced", "source": source,
                    "note": "largest absolute per-shape disagreement between the "
                            "two bases; allocation spread, not error against an "
                            "observation"})

    # --- transport: registration shares (derived) ----------------------------------------
    reg_shares = _registration_shares()
    for profile in ("transport_fuel_petrol", "transport_fuel_diesel"):
        # Any stream with the profile works: the weight depends only on
        # (module, spatial_profile_id, raster), never on the gas row.
        stream = next(s for s in streams.values()
                      if s["spatial_profile_id"] == profile)
        ref_shares = ctx.sector_shares("transport")[profile]
        ref_w = cube_core.diffuse_weight(ctx, stream, ref_shares, None)
        alt_w = cube_core.diffuse_weight(ctx, stream, reg_shares, None)
        emit_pair("transport_%s_registration_adm2"
                  % ("petrol" if "petrol" in profile else "diesel"),
                  "transport", profile, ref_w, alt_w,
                  "outputs/transport_provincial_proxy_comparison_2024.csv",
                  "DERIVED: transport has no district panel, so this is the province "
                  "bracket pushed through a fixed within-province proxy split - real "
                  "per-shape numbers, no information beyond the province rows")

    # --- transport: the calibrated road network (rc13 - genuinely new information) -------
    # The first transport ADM2 bracket that is NOT derivable from province rows: the
    # calibrated link weights (outputs/pakemis_road_weights_adm2.csv, declared
    # constants over the routable OSM graph) re-split each province's fuel across
    # districts, against the builtup reference's implied split. Province marginals
    # are share-constrained on both sides - conservation by construction - and the
    # reference allocation is UNCHANGED: this prices the alternative the road
    # products fence was built to keep out of the stream registries.
    road_shares = {}
    for r in _rows(asset_path(OUTPUTS, "pakemis_road_weights_adm2.csv")):
        road_shares[r["district"]] = float(r["share_calibrated"])
    for profile in ("transport_fuel_petrol", "transport_fuel_diesel"):
        stream = next(s for s in streams.values()
                      if s["spatial_profile_id"] == profile)
        ref_shares = ctx.sector_shares("transport")[profile]
        ref_w = cube_core.diffuse_weight(ctx, stream, ref_shares, None)
        alt_w = np.zeros((grid.height, grid.width), dtype=np.float64)
        for province, share in ref_shares.items():
            if share <= 0:
                continue
            members = [(idx, road_shares.get(name, 0.0))
                       for idx, name in enumerate(grid.districts)
                       if grid.district_province[idx] == province]
            total_cal = sum(w for _idx, w in members)
            if total_cal <= 0:
                mask = grid.province_mask(province)
                block = mask * ctx.cell_area
                alt_w += block * (share / float(block.sum()))
                continue
            for idx, w_cal in members:
                if w_cal <= 0:
                    continue
                dmask = grid.district_id == idx
                block = ctx.proxies["builtup"] * dmask
                btotal = float(block.sum())
                if btotal <= 0:
                    block = dmask * ctx.cell_area
                    btotal = float(block.sum())
                alt_w += block * (share * w_cal / total_cal / btotal)
        alt_w = alt_w / float(alt_w.sum())
        emit_pair("transport_road_network_%s_adm2"
                  % ("petrol" if "petrol" in profile else "diesel"),
                  "transport", profile, ref_w, alt_w,
                  "outputs/pakemis_road_weights_adm2.csv",
                  "GENUINELY NEW: the calibrated road-graph district split against "
                  "the builtup reference's implied split, province marginals "
                  "conserved on both sides. The calibration constants are declared "
                  "and unfitted (ROAD_SOURCES.json); the benchmark task that would "
                  "score them, spatial_road_transport, is pending_record")

    # --- power captive: points vs builtup fallback (the new information) -----------------
    captive_stream = next(s for s in streams.values()
                          if s["spatial_profile_id"] == "captive_gas")
    shares = ctx.sector_shares("power")["captive_gas"]
    ref_w = grid_cube.captive_weight(ctx, grid, captive_stream, shares)
    alt_w = np.zeros((grid.height, grid.width), dtype=np.float64)
    for province, share in shares.items():
        if share <= 0:
            continue
        mask = grid.province_mask(province)
        block = ctx.proxies["builtup"] * mask
        total = float(block.sum())
        if total <= 0:
            block = mask * ctx.cell_area
            total = float(block.sum())
        alt_w += block * (share / total)
    alt_w = alt_w / float(alt_w.sum())
    emit_pair("power_captive_points_builtup_adm2", "power", "captive_gas",
              ref_w, alt_w, "outputs/pakemis_grid_fallbacks.csv",
              "geocoded plant points against the builtup fallback surface - the "
              "spread is NOT derivable from any province number; the fallback is "
              "what the cube already declares for provinces with no geocoded plant")

    # --- agriculture rice: SPAM vs the own-year GCD-Rice 2023 (Wave 5) -------------------
    _rice_gcd_bracket(ctx, grid, streams, emit_pair)

    # --- power grid: its own points vs the declared builtup fallback (Wave 6) ------------
    # The captive bracket was reaching the grid category through the module-wide
    # placement join; scoping that join (joint_uncertainty.STREAM_MATCH_CATEGORY)
    # would have left a 57.8 Mt category declared-unpriced while its alternative -
    # the surface it rode until Wave 5 - is trivially priceable. Same pair shape
    # as the captive bracket, on the grid's own weight.
    grid_stream = next(s for s in streams.values()
                       if s["spatial_profile_id"] == "power_coal")
    grid_shares = ctx.sector_shares("power")["power_coal"]
    ref_w = grid_cube.grid_weight(ctx, grid, grid_stream, grid_shares)
    alt_w = np.zeros((grid.height, grid.width), dtype=np.float64)
    for province, share in grid_shares.items():
        if share <= 0:
            continue
        mask = grid.province_mask(province)
        block = ctx.proxies["builtup"] * mask
        total = float(block.sum())
        if total <= 0:
            block = mask * ctx.cell_area
            total = float(block.sum())
        alt_w += block * (share / total)
    alt_w = alt_w / float(alt_w.sum())
    emit_pair("power_grid_points_builtup_adm2", "power", "power_coal",
              ref_w, alt_w, "outputs/pakemis_grid_fallbacks.csv",
              "the grid fleet's corroborated station points (each at its own "
              "plant-ledger fuel, the Wave-5 allocation) against the builtup "
              "surface the fleet rode until then - the fallback the cube still "
              "declares for provinces with no located-and-fuelled station. "
              "Priced on the coal stream's shares; the other grid fuels ride "
              "the same mechanism at their own shares")

    # --- residential: structurally invariant at ADM2, with the grid magnitude ------------
    for profile, panel_word in (("residential_gas_conn", "Natural"),):
        stream = next(s for s in streams.values()
                      if s["spatial_profile_id"] == profile)
        shares = ctx.sector_shares("residential")[profile]
        panel = grid_cube.residential_panels()[panel_word]
        factors = cube_core.district_factors(ctx, panel, stream["source_stream_id"])
        ref_w = cube_core.diffuse_weight(ctx, stream, shares, factors)
        alt_w = _population_variant(ctx, grid, cube_core, stream, shares, factors)
        max_cell = float(abs(ref_w - alt_w).max())
        out.append({"alternative_id": "residential_builtup_population_adm2",
                    "module": "residential", "stream_match": profile,
                    "level": "within_shape", "shape_id": "", "adm2_ids": "",
                    "allocation_status": "", "province": "all",
                    "reference_share": "", "alternative_share": "",
                    "spread_pp": 0.0, "status": "structurally_invariant",
                    "source": "data/stream_grid_proxy.csv",
                    "note": "PROOF, not a price: the district panel fixes each "
                            "shape's mass and the raster only redistributes within "
                            "shapes, so the ADM2 spread is exactly zero by "
                            "construction (up to the declared Larkana remainder). "
                            "The choice matters at the cell: max per-cell weight "
                            "difference %.6f - a grid-level bracket, deferred and "
                            "declared" % max_cell})
        # rc13: the built-form bracket's THIRD member - the hybrid built x
        # population reading, same structural invariance at ADM2, its own
        # cell-level magnitude. The FOURTH member's surfaces landed at rc31
        # (GHS-BUILT-S total and NRES, 1 km, data/gis/manual/ghsl_built_1km/)
        # and are held-not-yet-wired: pricing waits for the rc32 fractional
        # intersection table, and the note below says so.
        hyb_w = _hybrid_variant(ctx, grid, cube_core, stream, shares, factors)
        max_cell_h = float(abs(ref_w - hyb_w).max())
        out.append({"alternative_id": "residential_builtup_hybrid_adm2",
                    "module": "residential", "stream_match": profile,
                    "level": "within_shape", "shape_id": "", "adm2_ids": "",
                    "allocation_status": "", "province": "all",
                    "reference_share": "", "alternative_share": "",
                    "spread_pp": 0.0, "status": "structurally_invariant",
                    "source": "data/stream_grid_proxy.csv",
                    "note": "PROOF row for the built x population HYBRID member "
                            "of the rc13 built-form bracket: ADM2-invariant like "
                            "its siblings (the district panel fixes shape mass); "
                            "max per-cell weight difference vs the builtup "
                            "reference %.6f. The residential-built fourth member's "
                            "surfaces are HELD since rc31 (GHS-BUILT-S total and "
                            "NRES 1 km, hashes in GHSL_SOURCES.json) and not yet "
                            "wired - pricing waits for the rc32 fractional "
                            "intersection table, declared rather than rushed"
                            % max_cell_h})
    return out


def _rice_gcd_bracket(ctx, grid, streams, emit_pair):
    """The Wave-5 rice bracket: the declared MapSPAM surface against the OWN-YEAR
    GCD-Rice 2023 30 m paddy extent, both as pure surface-driven within-province
    splits (factors=None). The shipped allocation additionally consults the
    district panel - which itself follows the declared surface - so this pair
    prices the SURFACE substitution cleanly; the crosscheck file publishes the
    same quantity per unit with its verdicts."""
    from pkinv.report import rice_geography_crosscheck as rgc
    stream = next(s for s in streams.values()
                  if s["spatial_profile_id"] == "rice_area")
    shares = ctx.sector_shares("agriculture")["rice_area"]
    spam = ctx.proxies.get("spam_rice")
    if spam is None:
        raise SystemExit("spam_rice absent from the context - the rice bracket "
                         "cannot price; the fallback allow-list no longer "
                         "permits building without it")
    gcd = rgc.gcd_fraction(grid)
    ref_w = _raster_variant(ctx, grid, stream, shares, None, spam)
    alt_w = _raster_variant(ctx, grid, stream, shares, None, gcd)
    emit_pair("agriculture_rice_gcd2023_adm2", "agriculture", "rice_area",
              ref_w, alt_w,
              "outputs/pakemis_rice_geography_crosscheck.csv",
              "GENUINELY NEW AND OWN-YEAR: the declared MapSPAM 2020 surface "
              "against GCD-Rice 2023 (30 m classified paddy, "
              "doi:10.57760/sciencedb.21665, ~88.9% accuracy), both as pure "
              "surface-driven splits with province marginals conserved. The "
              "reference allocation stays SPAM; this bracket is the measured "
              "price of the vintage-and-resolution disagreement, geography "
              "only, never magnitude")


def _hybrid_variant(ctx, grid, cube_core, stream, shares, factors):
    """The built x population HYBRID member of the rc13 built-form bracket: the
    within-shape raster is the normalised product of the two admissible readings
    (gas reaches the built grid AND people are the demand). A local array, never
    entering the closed raster vocabulary."""
    import numpy as np
    hybrid = ctx.proxies["builtup"] * ctx.proxies["population"]
    return _raster_variant(ctx, grid, stream, shares, factors, hybrid)


def _population_variant(ctx, grid, cube_core, stream, shares, factors):
    """The same nested weight with the population raster forced in place of the
    stream's declared raster - a local override, never touching the shared cache."""
    return _raster_variant(ctx, grid, stream, shares, factors,
                           ctx.proxies["population"])


def _raster_variant(ctx, grid, stream, shares, factors, population):
    import numpy as np
    # Re-run the diffuse formula manually with the swapped raster: share x d_share x
    # proxy/proxy(shape), mirroring cube_core.diffuse_weight's structure.
    weight = np.zeros((grid.height, grid.width), dtype=np.float64)
    for province, share in shares.items():
        if share <= 0:
            continue
        d_shares = (factors or {}).get(province, {})
        if d_shares:
            for shape_id, d_share in d_shares.items():
                mask = ctx.shape_mask(shape_id)
                if mask is None:
                    continue
                block = population * mask
                total = float(block.sum())
                if total <= 0:
                    block = mask * ctx.cell_area
                    total = float(block.sum())
                weight += block * (share * d_share / total)
        else:
            mask = grid.province_mask(province)
            block = population * mask
            total = float(block.sum())
            weight += block * (share / total)
    return weight / float(weight.sum())


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    rows = build()
    path = asset_path(OUTPUTS, "pakemis_spatial_brackets_adm2.csv")
    write_table(path, list(FIELDS), rows)
    for r in rows:
        if r["province"] == "MAX_ABS":
            print("  %-40s max |spread| %7.3f pp"
                  % (r["alternative_id"], float(r["spread_pp"])))
        if r["status"] == "structurally_invariant":
            print("  %-40s ADM2-invariant (proof row)" % r["alternative_id"])
    print("spatial brackets (ADM2) -> %s (%d rows)"
          % (os.path.basename(path), len(rows)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
