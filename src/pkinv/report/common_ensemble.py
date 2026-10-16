"""The common draw ensemble: one draw_id across annual, monthly and spatial outputs.

WHY THIS EXISTS (the twelfth review). Every uncertainty product so far answered its
own question in its own file: the annual Monte Carlo published percentiles, the
monthly layer carried deterministic brackets, the spatial products carried none by
declared design - and nothing shared a draw. draw_index existed only inside two
sector draw files. A reader could not ask "in the realisations where the national
total is high, which months and which provinces are high?", and the two closure
identities the deterministic products enforce at 1e-9 - twelve months sum to the
year, allocated plus unallocated sums to the nation - were not even expressible per
draw. This module makes them expressible, and then asserts them, inside every one
of 10,000 draws.

THE PREFIX PROPERTY IS THE DESIGN. Every stream in the national pool is
identity-seeded (core.montecarlo stream_seed / group_stream_key on _mc_key), and
the injected sector engines' persisted files are strictly prefix-extendable, so
draw d of this ensemble IS draw d of the published 100,000-draw annual run -
bit-identical, not statistically similar. The ensemble is the published run's
first 10,000 realisations given a name (draw_id) and carried down to months and
provinces. A test asserts the prefix against the published quantile surface.

WHAT IS DRAWN AND WHAT IS DEGENERATE, per the no-invented-distribution rule:
  annual mass       drawn - the national pool's parameter model, unchanged.
  monthly profile   drawn ONLY where a MEASURED dispersion exists: the hindcast
                    WAPE streams (Road transport, Railways - the joint product's
                    timing rows whose source is the hindcast). Their monthly
                    shares take multiplicative lognormal noise sized so the mean
                    absolute share error equals the measured WAPE, renormalised
                    to sum to one INSIDE EVERY DRAW. Every other category's
                    weights are fixed at the reference profile and the summary
                    says so per row (profile_uncertainty_status) - a column, not
                    a caveat. The power fuel-mix variant remains a CONDITIONAL
                    configuration and is never mixed in.
  spatial shares    fixed - allocation is declared, not sampled, and the
                    structural alternatives carry no probability by schema-tested
                    contract. The spatial layer's per-draw variation is the
                    parametric mass reaching each province, which is new and
                    real; the alternatives ship as conditional quantile blocks
                    beside it (pakemis_ensemble_spatial_conditionals.csv).

WHY THE GRID IS NOT IN THE ENSEMBLE. A month x cell ensemble is ~118 GB
(10,000 x 108 x 90,780 x 3 gases); the ensemble is MARGINAL by design - category
grain for months, province grain plus the retained-at-ADM1 column for space - and
the deterministic weights whose sums-to-one the cube gates already enforce carry
each draw the rest of the way.

Usage:  python3 -m pkinv.report.common_ensemble
Writes: outputs/mc_draws/pakemis_ensemble_annual.parquet   (+ .meta.json)
        outputs/mc_draws/pakemis_ensemble_monthly.parquet  (+ .meta.json)
        outputs/mc_draws/pakemis_ensemble_spatial.parquet  (+ .meta.json)
        outputs/pakemis_ensemble_summary.csv
        outputs/pakemis_ensemble_spatial_conditionals.csv
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import csv
import hashlib
import json
import math
import os
import random

from pkinv.core import montecarlo as mc_core
from pkinv.paths import OUTPUTS
from pkinv.report import uncertainty_all
from pkinv.activity.store import read_rows
from pkinv.core.io import write_table

ENSEMBLE_N = 10000
SEED = uncertainty_all.NATIONAL_SEED
SCENARIO = "within_sector"               # the published headline's scenario
DRAW_DIR = asset_path(OUTPUTS, "mc_draws")

ANNUAL_OUT = asset_path(DRAW_DIR, "pakemis_ensemble_annual.parquet")
MONTHLY_OUT = asset_path(DRAW_DIR, "pakemis_ensemble_monthly.parquet")
SPATIAL_OUT = asset_path(DRAW_DIR, "pakemis_ensemble_spatial.parquet")
SUMMARY_OUT = asset_path(OUTPUTS, "pakemis_ensemble_summary.csv")
CONDITIONALS_OUT = asset_path(OUTPUTS,
                                "pakemis_ensemble_spatial_conditionals.csv")

# The placement axis: every stream has a PROVINCE (the S4 identity holds ADM1
# marginals for everything), and the split the reviewer's identity needs is
# whether the mass continues to the grid or is retained at ADM1.
PLACEMENT_GRIDDED = "gridded"
PLACEMENT_RETAINED = "retained_at_adm1"

# The lognormal sigma whose mean absolute multiplicative error equals a measured
# WAPE w (small-sigma matching: E|exp(sz-s^2/2)-1| ~ s*sqrt(2/pi)).
WAPE_TO_SIGMA = math.sqrt(math.pi / 2.0)


def _rows(path):
    return read_rows(path)


def annual_draws(prebuilt=None, n_iter=ENSEMBLE_N):
    """(categories, {category: [draws]}, [national draws], deterministic totals).

    The same machinery as uncertainty_all.run's category pass - same pooled
    components, same _mc_key pinning, same injected prefixes - run once with
    return_samples so the draws themselves come back. Kept deliberately parallel
    to uncertainty_all.run rather than refactored into it: the prefix test below
    is what holds the two together, and a shared helper would let them drift as
    one instead of failing loudly as two."""
    components, categories, sector_of = prebuilt or uncertainty_all.pooled(False)
    for c in components:
        c["_mc_key"] = "%s|%s|%s" % (c["category"], c["subitem"], c["gas"])
    cat_all, _sector_all, _metas, coupling = uncertainty_all._load_injected(
        components)
    injected = {k: v[:n_iter] for k, v in cat_all.items()}
    short = [k for k, v in injected.items() if len(v) < n_iter]
    if short:
        raise SystemExit("draw files carry fewer than %d draws for %s"
                         % (n_iter, short))
    # Wave 6: the per-draw gas identity rides the same truncated prefix of the
    # fugitives parameter channel, so draw d here is still bit-identically draw
    # d of the published 100k run.
    scalers = uncertainty_all.gas_coupling_scalers(components, coupling, n_iter)
    native, shared = uncertainty_all.native_components(components, n_iter, SEED)
    _stats, total_samples, cat_samples = mc_core.run(
        components, categories, n_iter=n_iter, seed=SEED, has_sinks=False,
        stream=uncertainty_all.NATIONAL_STREAM, return_samples=True,
        cross_sector=False, injected=injected, component_scalers=scalers,
        component_values=native, parameter_draws=shared)
    deterministic = {}
    for c in components:
        deterministic[c["category"]] = (deterministic.get(c["category"], 0.0)
                                        + c["co2e_Mt_AR5"])
    order = [c for c in categories if c in cat_samples]
    return order, cat_samples, total_samples, deterministic, sector_of


def reference_profiles():
    """{category: {month: share}} from the deterministic monthly national layer."""
    mass = {}
    for r in _rows(asset_path(OUTPUTS, "national_monthly_2024.csv")):
        key = (r["category"], r["month"])
        mass[key] = mass.get(key, 0.0) + float(r["co2e_Mt_AR5"])
    out = {}
    for (category, month), mt in mass.items():
        out.setdefault(category, {})[month] = mt
    for category, months in out.items():
        total = sum(months.values())
        if len(months) != 12 or total <= 0:
            raise SystemExit("category %r has %d months in the monthly layer"
                             % (category, len(months)))
        out[category] = {m: v / total for m, v in months.items()}
    return out


# The bases a drawn profile may rest on - an explicit vocabulary since Wave 3,
# replacing a substring test on the source text. Both are MEASURED mean absolute
# share errors (the same L1 quantity), earned two different ways: a hindcast scores
# candidates against held truth; a crosscheck publishes the disagreement between two
# instruments neither of which is truth. A structural variant is deliberately NOT
# here: it is a conditional configuration with nothing to draw.
DRAWN_TIMING_BASES = ("measured_hindcast_dispersion",
                      "measured_crosscheck_disagreement")


def measured_profile_sigmas():
    """{category: sigma} for exactly the categories whose timing bracket is a
    MEASURED dispersion (hindcast or two-instrument crosscheck) - read from the
    joint product so each error figure has one home. Everything else is
    degenerate and says so."""
    out = {}
    for r in _rows(asset_path(OUTPUTS, "pakemis_joint_uncertainty.csv")):
        if r["resolution"] != "monthly_national":
            continue
        if (r.get("timing_basis") or "") not in DRAWN_TIMING_BASES:
            continue
        if not r["timing_pct"]:
            continue
        out[r["category"]] = float(r["timing_pct"]) / 100.0 * WAPE_TO_SIGMA
    return out


def measured_profile_bases():
    """{category: timing_basis} for the drawn categories - the status column names
    which kind of measurement licensed each draw."""
    out = {}
    for r in _rows(asset_path(OUTPUTS, "pakemis_joint_uncertainty.csv")):
        if r["resolution"] != "monthly_national":
            continue
        basis = r.get("timing_basis") or ""
        if basis in DRAWN_TIMING_BASES and r["timing_pct"]:
            out[r["category"]] = basis
    return out


def _profile_stream(category, month):
    """A dedicated, reproducible RNG for one category-month share: sequential
    over draws, keyed away from every existing stream so the ensemble can never
    perturb the annual draws it consumes."""
    key = hashlib.blake2b(("profile|%d|%s|%s" % (SEED, category, month)).encode(),
                          digest_size=8).digest()
    return random.Random(int.from_bytes(key, "big"))


def drawn_profiles(profiles, sigmas, n_iter=ENSEMBLE_N):
    """{category: [ {month: share} per draw ]} for the measured categories only.

    Multiplicative lognormal noise per month, mean-preserving before the
    renormalisation that makes every draw's twelve shares sum to exactly one."""
    out = {}
    for category, sigma in sigmas.items():
        months = sorted(profiles[category])
        streams = {m: _profile_stream(category, m) for m in months}
        draws = []
        for _d in range(n_iter):
            weights = {m: profiles[category][m]
                       * math.exp(sigma * streams[m].gauss(0.0, 1.0)
                                  - 0.5 * sigma * sigma)
                       for m in months}
            total = sum(weights.values())
            draws.append({m: w / total for m, w in weights.items()})
        out[category] = draws
    return out


def _engine_category_codes():
    """engine category -> {ipcc codes}, from the completeness rows - the
    repository's single statement of which engine category sits under which
    code (the same source fuel_combustion_sectors() reads)."""
    from pkinv.report import completeness
    codes = {}
    for row in completeness.ROWS:
        if len(row) >= 5 and row[4]:
            codes.setdefault(row[4], set()).add(row[0])
    return codes


def spatial_shares(categories, sector_of):
    """{engine category: ({province: share}, unallocated_share)} from the
    shipped spatial products: the provincial check's declared shares weighted
    by each stream's registered mass, and the S4 ledger's retained-at-ADM1
    mass.

    EVERY stream has provincial shares - the S4 identity holds ADM1 marginals
    for the whole inventory - and the placement split is whether the mass
    continues to the grid or is RETAINED at ADM1 (the streams of the S4
    ledger). The stream registry speaks IPCC names and the ensemble speaks
    engine categories, so streams are matched on (module, ipcc_code) through
    the completeness rows; a stream matched nowhere fails the build."""
    streams = [r for r in _rows(asset_path(OUTPUTS,
                                             "pakemis_source_streams.csv"))
               if r["notation_key"] == "E"]
    shares = {}
    for r in _rows(asset_path(OUTPUTS, "pakemis_grid_provincial_check.csv")):
        shares.setdefault(r["source_stream_id"], {})[r["province"]] = \
            float(r["declared_share"])
    unallocated_mt = {}
    for r in _rows(asset_path(OUTPUTS, "pakemis_spatial_unallocated.csv")):
        unallocated_mt[r["source_stream_id"]] = (
            unallocated_mt.get(r["source_stream_id"], 0.0)
            + float(r["co2e_Mt_AR5"]))

    codes = _engine_category_codes()
    owner_by_key = {}
    for category in categories:
        module = sector_of.get(category)
        for code in codes.get(category, ()):
            key = (module, code)
            if key in owner_by_key:
                raise SystemExit("(module, code) %r claimed by both %r and %r"
                                 % (key, owner_by_key[key], category))
            owner_by_key[key] = category

    by_category = {}
    unmatched = []
    for row in streams:
        category = owner_by_key.get((row["module"], row["ipcc_code"]))
        if category is None:
            unmatched.append(row["source_stream_id"])
            continue
        mt = float(row["emissions_ar5"])          # the registry publishes Mt AR5
        stream_id = row["source_stream_id"]
        if stream_id not in shares:
            raise SystemExit(
                "stream %r has no provincial shares - the S4 identity says "
                "every stream has an ADM1 marginal, so this is a build error, "
                "not a placement choice" % stream_id)
        placement = (PLACEMENT_RETAINED if stream_id in unallocated_mt
                     else PLACEMENT_GRIDDED)
        entry = by_category.setdefault(category, {"cells": {}, "mass": 0.0})
        entry["mass"] += mt
        for province, share in shares[stream_id].items():
            key = (province, placement)
            entry["cells"][key] = entry["cells"].get(key, 0.0) + mt * share
    if unmatched:
        raise SystemExit("streams matching no engine category: %s"
                         % sorted(unmatched))
    out = {}
    for category, entry in by_category.items():
        placed = sum(entry["cells"].values())
        if entry["mass"] and abs(placed - entry["mass"]) > 1e-6 * entry["mass"]:
            raise SystemExit("category %r: placed %.6f vs registered %.6f Mt"
                             % (category, placed, entry["mass"]))
        if not entry["mass"]:
            continue
        # Normalise over the PLACED mass, not the registered one: the registry
        # rounds each stream to three decimals, and dividing by the registered
        # sum would leave that rounding as a ~1e-8 residual inside every draw's
        # closure identity. The shares must sum to exactly one.
        out[category] = {k: v / placed for k, v in entry["cells"].items()}

    detail = {}
    for row in streams:
        stream_id = row["source_stream_id"]
        category = owner_by_key.get((row["module"], row["ipcc_code"]))
        detail[stream_id] = {"category": category,
                             "mt": float(row["emissions_ar5"]),
                             "shares": shares.get(stream_id, {})}
    return out, detail


def _meta(path, note, extra=None):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    meta = {
        "file": os.path.relpath(path, OUTPUTS),
        "sha256": digest.hexdigest(),
        "seed": SEED,
        "n_iter": ENSEMBLE_N,
        "scenario": SCENARIO,
        "engine": "pkinv.report.common_ensemble",
        "rng": ("prefix of the published national pool (identity-seeded "
                "parameter streams + injected sector draw files); profile noise "
                "on dedicated blake2b-keyed streams"),
        "note": note,
    }
    meta.update(extra or {})
    with open(path.rsplit(".", 1)[0] + ".meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, sort_keys=True)
        f.write("\n")
    return meta


def build():
    import pandas as pd

    order, cat_samples, total_samples, deterministic, sector_of = annual_draws()
    profiles = reference_profiles()
    sigmas = measured_profile_sigmas()
    drawn = drawn_profiles(profiles, sigmas)
    spatial, stream_detail = spatial_shares(order, sector_of)

    categories = [c for c in order]
    missing_profiles = [c for c in categories if c not in profiles]
    if missing_profiles:
        raise SystemExit("categories with draws but no monthly profile: %s"
                         % missing_profiles)
    missing_spatial = [c for c in categories if c not in spatial]
    if missing_spatial:
        raise SystemExit("categories with draws but no spatial shares: %s"
                         % missing_spatial)

    os.makedirs(DRAW_DIR, exist_ok=True)

    # --- annual: draw_id x category (wide), plus the national total ------------
    annual = pd.DataFrame({"draw_id": range(ENSEMBLE_N)})
    for c in categories:
        annual[c] = pd.Series(cat_samples[c], dtype="float64")
    annual["NATIONAL_TOTAL"] = pd.Series(total_samples, dtype="float64")
    annual.to_parquet(ANNUAL_OUT, index=False)

    # --- monthly: draw_id x category x month (long) ----------------------------
    months = sorted(next(iter(profiles.values())))
    frames = []
    for c in categories:
        cat_draws = pd.Series(cat_samples[c], dtype="float64")
        if c in drawn:
            weights = pd.DataFrame(drawn[c])[months]
        else:
            weights = pd.DataFrame([profiles[c]] * ENSEMBLE_N)[months]
        block = weights.multiply(cat_draws, axis=0)
        block.insert(0, "draw_id", range(ENSEMBLE_N))
        long = block.melt(id_vars="draw_id", var_name="month",
                          value_name="co2e_Mt_AR5")
        long.insert(1, "category", c)
        frames.append(long)
    monthly = pd.concat(frames, ignore_index=True)
    monthly["month"] = monthly["month"].astype("int32")
    monthly["draw_id"] = monthly["draw_id"].astype("int32")
    monthly["category"] = monthly["category"].astype("category")
    monthly.to_parquet(MONTHLY_OUT, index=False)

    # --- spatial: draw_id x category x province x placement --------------------
    frames = []
    for c in categories:
        cat_draws = pd.Series(cat_samples[c], dtype="float64")
        block = pd.DataFrame({"%s|%s" % key: cat_draws * s
                              for key, s in spatial[c].items()})
        block.insert(0, "draw_id", range(ENSEMBLE_N))
        long = block.melt(id_vars="draw_id", var_name="cell",
                          value_name="co2e_Mt_AR5")
        split = long["cell"].str.split("|", n=1, expand=True)
        long["province"] = split[0]
        long["placement"] = split[1]
        long = long.drop(columns="cell")
        long.insert(1, "category", c)
        frames.append(long)
    spatial_df = pd.concat(frames, ignore_index=True)
    spatial_df["draw_id"] = spatial_df["draw_id"].astype("int32")
    for col in ("category", "province", "placement"):
        spatial_df[col] = spatial_df[col].astype("category")
    spatial_df = spatial_df[["draw_id", "category", "province", "placement",
                             "co2e_Mt_AR5"]]
    spatial_df.to_parquet(SPATIAL_OUT, index=False)

    return {"annual": annual, "monthly": monthly, "spatial": spatial_df,
            "categories": categories, "profiles": profiles, "sigmas": sigmas,
            "deterministic": deterministic, "spatial_shares": spatial,
            "stream_detail": stream_detail,
            "total_samples": total_samples, "cat_samples": cat_samples}


def _published_national():
    for r in _rows(asset_path(OUTPUTS, "national_uncertainty_montecarlo.csv")):
        if (r["scenario"] == SCENARIO and r["aggregation_level"] == "national"):
            return r
    raise SystemExit("no published national row to converge against")


def write_summary(built):
    """Per-category quantiles with SEs, the drawn/degenerate status, and the
    agreement against the published 100,000-draw surface - the convergence
    statement for the 10,000-draw prefix."""
    published = _published_national()
    bases = measured_profile_bases()
    rows = []
    for c in built["categories"] + ["NATIONAL_TOTAL"]:
        samples = (built["total_samples"] if c == "NATIONAL_TOTAL"
                   else built["cat_samples"][c])
        ordered = sorted(samples)
        qse = mc_core.batch_quantile_se(samples) or {}
        det = (sum(built["deterministic"].values()) if c == "NATIONAL_TOTAL"
               else built["deterministic"].get(c, 0.0))
        status = ("drawn_" + bases.get(c, "measured_hindcast_dispersion")
                  if c in built["sigmas"]
                  else "not_applicable" if c == "NATIONAL_TOTAL"
                  else "degenerate_no_measured_dispersion")
        rows.append({
            "name": c,
            "deterministic_Mt": round(det, 5),
            "mean_Mt": round(sum(samples) / len(samples), 4),
            "P2.5_Mt": round(mc_core.percentile(ordered, 0.025), 4),
            "P50_Mt": round(mc_core.percentile(ordered, 0.50), 4),
            "P97.5_Mt": round(mc_core.percentile(ordered, 0.975), 4),
            "p025_se_Mt": round(qse.get("p025_se", 0.0), 4),
            "p975_se_Mt": round(qse.get("p975_se", 0.0), 4),
            "profile_uncertainty_status": status,
            "profile_sigma": (round(built["sigmas"][c], 5)
                              if c in built["sigmas"] else ""),
            "n_iter": ENSEMBLE_N,
            "note": "",
        })
        if c == "NATIONAL_TOTAL":
            rows[-1]["note"] = (
                "prefix of the published run: 100k within_sector national "
                "P2.5/P50/P97.5 = %s/%s/%s; the differences are the 10k "
                "quantile noise the SE columns size. The ensemble mean sits "
                "above the deterministic total by the injected engines' "
                "mode-anchored asymmetry, exactly as the annual MC states"
                % (published["P2.5_Mt"], published["P50_Mt"],
                   published["P97.5_Mt"]))
    write_table(SUMMARY_OUT, list(rows[0].keys()), rows, banner=("# The common ensemble's summary surface: one row per category plus the national total, draw grain 10,000 (draw_id 0..9999, a bit-identical prefix of the published 100,000-draw run).", "# profile_uncertainty_status says which categories' monthly weights are DRAWN (measured hindcast dispersion) and which are degenerate; the power fuel-mix variant is a conditional configuration and is never mixed in.",))
    return rows


def write_spatial_conditionals(built):
    """The alternatives beside the ensemble: for every priced province-level
    spatial alternative, the province quantiles the SAME annual draws imply
    under the alternative shares - conditional blocks, never mixed.

    The brackets name a PROXY (transport_fuel_petrol), not a stream, and carry
    no mass. The affected streams are recovered through the proxy's own
    declared shares (data/province_shares.csv): a stream whose declared
    provincial shares equal the proxy's rides that proxy, so the union over the
    bracket's stream_match proxies is the affected set. An alternative
    matching no stream is a build failure, not a silent skip."""
    from pkinv.paths import DATA
    proxy_shares = {}
    for r in _activity_rows(asset_path(DATA, "province_shares.csv"), comments=False):
        proxy_shares[r["proxy"]] = {
            p: float(r[p]) for p in
            ("Punjab", "Sindh", "Khyber Pakhtunkhwa", "Balochistan",
             "Other")}

    alt_rows = [r for r in _rows(asset_path(OUTPUTS,
                                              "pakemis_spatial_brackets.csv"))
                if r["status"] == "priced" and r["reference_share"]]
    by_alt = {}
    for r in alt_rows:
        by_alt.setdefault(r["alternative_id"], []).append(r)

    out = []
    for alt_id, rows in sorted(by_alt.items()):
        proxies = rows[0]["stream_match"].split(";")
        fingerprints = [proxy_shares[p] for p in proxies]
        matched = [
            (stream_id, d) for stream_id, d in built["stream_detail"].items()
            if d["shares"] and any(
                all(abs(d["shares"].get(p, 0.0) - s) < 1e-4
                    for p, s in fp.items())
                for fp in fingerprints)]
        if not matched:
            raise SystemExit("spatial alternative %r matches no stream "
                             "through its proxies %s - its conditional block "
                             "cannot be built" % (alt_id, proxies))
        by_category = {}
        for _stream_id, d in matched:
            by_category[d["category"]] = by_category.get(d["category"], 0.0) \
                + d["mt"]
        for category, affected_mt in sorted(by_category.items()):
            cat_mass = built["deterministic"].get(category)
            samples = built["cat_samples"][category]
            fraction = affected_mt / cat_mass
            for r in sorted(rows, key=lambda x: x["province"]):
                ref = sorted(s * fraction * float(r["reference_share"])
                             for s in samples)
                alt = sorted(s * fraction * float(r["alternative_share"])
                             for s in samples)
                out.append({
                    "alternative_id": alt_id,
                    "category": category,
                    "affected_Mt": round(affected_mt, 5),
                    "province": r["province"],
                    "reference_share": r["reference_share"],
                    "alternative_share": r["alternative_share"],
                    "reference_P2.5_Mt": round(mc_core.percentile(ref, 0.025), 4),
                    "reference_P50_Mt": round(mc_core.percentile(ref, 0.50), 4),
                    "reference_P97.5_Mt": round(mc_core.percentile(ref, 0.975), 4),
                    "alternative_P2.5_Mt": round(mc_core.percentile(alt, 0.025), 4),
                    "alternative_P50_Mt": round(mc_core.percentile(alt, 0.50), 4),
                    "alternative_P97.5_Mt": round(mc_core.percentile(alt, 0.975), 4),
                    "note": "conditional block over the AFFECTED %.2f Mt (the "
                            "streams whose declared shares fingerprint-match "
                            "the bracket): the same draw_ids under the "
                            "alternative allocation; no probability attaches "
                            "to the choice between blocks" % affected_mt,
                })
    # THE ADM2 BRACKETS (Wave 6). Until this block the conditionals file carried
    # only the ADM1 transport alternatives - the Wave-5 ADM2 program (the rice GCD
    # surface, the captive and grid points-vs-builtup pairs, the road-graph split)
    # shipped `priced_adm2` rows the filter above never read, so "the alternatives
    # beside the ensemble" silently excluded every district-grain alternative.
    # Each ADM2 alternative's stream names its category directly (these brackets
    # are whole-category streams, no fingerprint recovery needed), and rows are
    # emitted for shapes above a declared spread floor so the file stays readable
    # - the floor is stated in the note, never silent.
    ADM2_SPREAD_FLOOR_PP = 0.5
    ADM2_STREAM_CATEGORY = {
        "rice_area": "Rice cultivation",
        "power_coal": "Electricity and heat production",
        "captive_gas": "Captive gas self-generation (1A2)",
        "transport_fuel_petrol": "Road transport",
        "transport_fuel_diesel": "Road transport",
    }
    adm2_rows = [r for r in _rows(asset_path(
        OUTPUTS, "pakemis_spatial_brackets_adm2.csv"))
        if r["status"].startswith("priced") and r["shape_id"]
        and r["reference_share"] and r["alternative_share"]]
    by_alt2 = {}
    for r in adm2_rows:
        by_alt2.setdefault(r["alternative_id"], []).append(r)
    for alt_id, rows in sorted(by_alt2.items()):
        category = ADM2_STREAM_CATEGORY.get(rows[0]["stream_match"])
        if category is None:
            raise SystemExit("ADM2 spatial alternative %r names stream %r with "
                             "no category mapping - its conditional block "
                             "cannot be built and silence is not an option"
                             % (alt_id, rows[0]["stream_match"]))
        cat_mass = built["deterministic"].get(category)
        if cat_mass is None:
            continue
        samples = built["cat_samples"][category]
        kept = [r for r in rows
                if abs(float(r["spread_pp"] or 0.0)) >= ADM2_SPREAD_FLOOR_PP]
        for r in sorted(kept, key=lambda x: -abs(float(x["spread_pp"]))):
            ref = sorted(s * float(r["reference_share"]) for s in samples)
            alt = sorted(s * float(r["alternative_share"]) for s in samples)
            out.append({
                "alternative_id": alt_id,
                "category": category,
                "affected_Mt": round(cat_mass, 5),
                "province": "shape:%s" % r["shape_id"],
                "reference_share": r["reference_share"],
                "alternative_share": r["alternative_share"],
                "reference_P2.5_Mt": round(mc_core.percentile(ref, 0.025), 4),
                "reference_P50_Mt": round(mc_core.percentile(ref, 0.50), 4),
                "reference_P97.5_Mt": round(mc_core.percentile(ref, 0.975), 4),
                "alternative_P2.5_Mt": round(mc_core.percentile(alt, 0.025), 4),
                "alternative_P50_Mt": round(mc_core.percentile(alt, 0.50), 4),
                "alternative_P97.5_Mt": round(mc_core.percentile(alt, 0.975), 4),
                "note": "ADM2 conditional block (Wave 6): the same draw_ids "
                        "under the alternative allocation, shapes above the "
                        "%.1f pp spread floor only (%d of %d shapes shown); "
                        "no probability attaches to the choice between blocks"
                        % (ADM2_SPREAD_FLOOR_PP, len(kept), len(rows)),
            })
    with open(CONDITIONALS_OUT, "w", newline="", encoding="utf-8") as f:
        f.write("# Spatial alternatives as CONDITIONAL ensemble blocks: same "
                "draw_ids, alternative shares, affected mass only. The choice "
                "between blocks is structural and carries no probability - the "
                "anti-probability schema contract of the configurations file, "
                "kept. ADM2 alternatives (Wave 6) appear as shape:<id> rows "
                "above a declared spread floor.\n")
        if out:
            w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
            w.writeheader()
            w.writerows(out)
    return out


def write_ledger_summary(built):
    """Configuration L on shared parameter identities, with actual ledger components.

    Other sources retain their reference realisations. Dung follows the same
    sampled livestock as the nitrogen ledger; VS, excretion and fate assumptions
    are held conditional. The printed deterministic dung ratio is not used as a
    replacement for L's activity uncertainty.
    """
    from pkinv.core import configurations as conf
    from pkinv.core import montecarlo as mc_core
    components, categories, _sector_of = uncertainty_all.pooled(False)
    for c in components:
        c["_mc_key"] = "%s|%s|%s" % (c["category"], c["subitem"], c["gas"])
    cat_all, _s, _m, coupling = uncertainty_all._load_injected(components)
    injected = {k: v[:ENSEMBLE_N] for k, v in cat_all.items()}
    scalers = uncertainty_all.gas_coupling_scalers(components, coupling, ENSEMBLE_N)
    register = {r["configuration"]: float(r["co2e_Mt_AR5"]) for r in _rows(
        asset_path(OUTPUTS, "residential_configurations_2024.csv"))}
    # the dung ratio in CO2e is the register pair's own quotient restricted to
    # the dung components; every dung component scales alike (one basis switch)
    from pkinv.sectors.residential import engine as res_engine
    data = res_engine.load_data()
    ref_comps = res_engine.build_components(data)
    alt_comps = res_engine.build_components(
        data, dung_basis=conf.ALTERNATIVE_DUNG_BASIS)
    dung_ref = sum(c["co2e_Mt_AR5"] for c in ref_comps if "dung" in c["subitem"].lower())
    dung_alt = sum(c["co2e_Mt_AR5"] for c in alt_comps if "dung" in c["subitem"].lower())
    k = dung_alt / dung_ref  # deterministic level ratio only; not an uncertainty multiplier
    n_scaled = 0
    alternatives = {(row["subitem"], row["gas"]): row for row in alt_comps}
    for c in components:
        if c["category"] == "Residential fuel combustion" and "dung" in c["subitem"].lower():
            alternate = alternatives[(c["subitem"], c["gas"])]
            c.update(alternate)
            n_scaled += 1
    if not n_scaled:
        raise SystemExit("ledger ensemble: no dung component found to scale - "
                         "the configuration would silently equal the reference")
    native, shared = uncertainty_all.native_components(components, ENSEMBLE_N, SEED, dung_basis="ledger")
    _stats, total_samples, _cats = mc_core.run(
        components, categories, n_iter=ENSEMBLE_N, seed=SEED, has_sinks=False,
        stream=uncertainty_all.NATIONAL_STREAM, return_samples=True,
        cross_sector=False, injected=injected, component_scalers=scalers,
        component_values=native, parameter_draws=shared)
    ordered = sorted(total_samples)
    det = sum(c["co2e_Mt_AR5"] for c in components)
    out = asset_path(OUTPUTS, "pakemis_ensemble_ledger_summary.csv")
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["configuration_id", "deterministic_Mt", "mean_Mt", "P2.5_Mt",
                    "P50_Mt", "P97.5_Mt", "n_draws", "dung_scale",
                    "draw_identity"])
        w.writerow([conf.LEDGER, round(det, 5),
                    round(sum(ordered) / len(ordered), 4),
                    round(mc_core.percentile(ordered, 0.025), 4),
                    round(mc_core.percentile(ordered, 0.5), 4),
                    round(mc_core.percentile(ordered, 0.975), 4),
                    len(ordered), round(k, 6),
                    "same shared parameter identities; ledger dung follows sampled herd; "
                    "fate/excretion fixed; dung_scale is deterministic level ratio only"])
    print("ledger ensemble -> %s (L deterministic %.5f, dung scale %.4f, "
          "%d scaled components)" % (out, det, k, n_scaled))
    return out


def main():
    built = build()
    summary = write_summary(built)
    write_ledger_summary(built)
    conditionals = write_spatial_conditionals(built)

    _meta(ANNUAL_OUT,
          "draw_id x category annual draws; bit-identical prefix of the "
          "published 100k within_sector national run")
    _meta(MONTHLY_OUT,
          "draw_id x category x month; every draw's twelve months sum exactly "
          "to its annual draw; weights drawn only where a measured hindcast "
          "dispersion exists (%s)" % ", ".join(sorted(built["sigmas"])) if
          built["sigmas"] else "no measured dispersions found",
          extra={"drawn_profile_categories": sorted(built["sigmas"])})
    _meta(SPATIAL_OUT,
          "draw_id x category x province x placement (gridded | %s); every "
          "draw's cells sum exactly to its annual draw, and the reviewer's "
          "identity national = gridded + unallocated holds per draw as the "
          "placement split" % PLACEMENT_RETAINED)

    national = next(r for r in summary if r["name"] == "NATIONAL_TOTAL")
    print("common ensemble -> outputs/mc_draws/pakemis_ensemble_{annual,monthly,"
          "spatial}.parquet (%d draws)" % ENSEMBLE_N)
    print("  national: det %.2f, mean %s, [%s, %s] Mt; %d categories"
          % (sum(built["deterministic"].values()), national["mean_Mt"],
             national["P2.5_Mt"], national["P97.5_Mt"],
             len(built["categories"])))
    print("  monthly rows %d, spatial rows %d; drawn profiles: %s; "
          "%d spatial conditional blocks"
          % (len(built["monthly"]), len(built["spatial"]),
             ", ".join(sorted(built["sigmas"])) or "none", len(conditionals)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
