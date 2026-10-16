"""Agricultural AIR-POLLUTANT co-emissions (mass, kt) -- a parallel bottom-up layer.

Not greenhouse gases: reported in mass (kt), never converted to CO2e and never part of the GHG
control-total reconciliation. The GHG engine is untouched; this module reuses the activity it already
computes:
  * NH3  = volatilised NH3-N x 17/14, per source stream (synthetic fertiliser, organic manure
           applied, pasture deposition, manure management), plus small residue and burning terms.
           The NH3-N pool is requested explicitly from soils.volatilised_n(basis="NH3"): synthetic
           fertiliser uses EMEP/EEA product factors that are ALREADY NH3-N, while the IPCC organic
           and pasture fractions cover NH3+NOx and must have the NH3 share taken. Confusing those
           two bases understates ammonia and unbalances the indirect-N2O pool.
  * NOx  = soil NOx from APPLIED N x NOx_frac_of_applied x 46/14 (Stehfest & Bouwman; a distinct
           process from the NH3 pool, excluding grazing deposition) + burning NOx.
  * PM2.5, CO, NMVOC, BC, SO2 = mass_burnt x Cf x Gef(g/kg)/1e6  (crop-residue field burning).

Every factor traces to data/emission_factors.csv with a source string and an uncertainty; component
uncertainties are propagated with the IPCC Approach-1 product rule (uncertainty.product), as in the
GHG modules. Province allocation delegates to downscale.proxy_for on each row's `ghg_subitem`, so a
given nitrogen pool is allocated to the same provinces here as in the GHG layer.

Units: N pools in kg N -> pollutant kg via molar ratio -> /1e6 = Gg = kt.

Usage:  python3 -m pkinv.sectors.agriculture.air_pollutants
Writes: outputs/air_pollutants_2024.csv, outputs/air_pollutants_provincial_2024.csv
"""

from pkinv.assets import asset_path
import collections
import csv
import os
import sys


from pkinv.sectors.agriculture.ef_library import InventoryData, _read, DATA_DIR  # noqa: E402
from pkinv.sectors.agriculture import manure, soils, residue_burning  # noqa: E402
from pkinv.core.uncertainty import product  # noqa: E402

from pkinv.paths import ROOT

OUT_DIR = asset_path(ROOT, "outputs")
NH3_PER_N = 17.0 / 14.0      # kg NH3 per kg NH3-N
NO2_PER_N = 46.0 / 14.0      # kg NO2 per kg NOx-N
BURN_POLL = [("PM2.5", "Gef_PM25"), ("CO", "Gef_CO"), ("NOx", "Gef_NOx"),
             ("NMVOC", "Gef_NMVOC"), ("BC", "Gef_BC"), ("SO2", "Gef_SO2"), ("NH3", "Gef_NH3")]


def compute(data=None):
    """Return rows {category, subitem, ghg_subitem, pollutant, emissions_kt, uncert_pct}.

    `ghg_subitem` is the corresponding managed-soils/manure/burning subitem in the GHG engine; it is
    used only to look up that stream's province proxy via downscale, so the same nitrogen pool is
    allocated to the same provinces in both layers.
    """
    if data is None:
        data = InventoryData()
    _, npools = manure.compute(data)
    # NH3-N basis: the product factors are already NH3-N, so no NH3-share conversion is applied to
    # them here. See soils.volatilised_n for why the two bases must be requested explicitly.
    sv = soils.volatilised_n(data, npools, basis="NH3")
    mv = npools["volat_managed_N"]               # manure-management volatilised N (kg N)
    from pkinv.sectors.agriculture import fertiliser_mix
    gasf_u = fertiliser_mix.fracgasf_uncert(data)   # product-weighted EEA, not the superseded IPCC row
    fsn_u = data.fertilizer["nitrogen_N_offtake"]["uncert_pct"]
    rows = []

    def add(cat, sub, ghg_sub, poll, kt, u):
        rows.append({"category": cat, "subitem": sub, "ghg_subitem": ghg_sub,
                     "pollutant": poll, "emissions_kt": kt, "uncert_pct": u})

    # --- NH3 from synthetic fertiliser, PER PRODUCT (air spatial Wave A): the weighted
    #     EEA factor is a flattening of a per-product detail fertiliser_mix already
    #     computes - urea and DAP are different chemistry with different volatilisation,
    #     and the product distinction must survive into the atoms even while every
    #     product shares the one cropland surface today. The per-product masses are the
    #     exact partition of the weighted total (asserted by tests). ---
    weighted_gasf, gasf_detail, _total_n = fertiliser_mix.weighted_fracgasf(data)
    for d in gasf_detail:
        if d["contribution"] <= 0.0:
            continue
        add("Managed soils", "NH3 - synthetic fertiliser (%s)" % d["product"],
            "Direct N2O - synthetic fertiliser (upland)", "NH3",
            sv["synthetic"] * (d["contribution"] / weighted_gasf) * NH3_PER_N / 1e6,
            product(fsn_u, gasf_u))

    # --- NH3 from livestock: EMEP/EEA TAN mass flow, resolved per SPECIES and STAGE.
    #     The atoms carry the resolution the flow always computed (air spatial Wave A):
    #     housing/yard and storage volatilise at the ANIMAL HOUSES (the volatilisation
    #     stream's livestock surface), application at the RECEIVING CROPLAND (the
    #     organic-manure stream's manure_applied surface), grazing on the pasture
    #     streams - three different release locations the old four-row collapse partly
    #     misplaced. ---
    flows = livestock_nh3_flows(data, npools)
    STAGE_ROW = {
        "housing": ("Manure management", "NH3 - housing", "Indirect N2O (volatilisation)"),
        "yard": ("Manure management", "NH3 - yard", "Indirect N2O (volatilisation)"),
        "storage": ("Manure management", "NH3 - storage", "Indirect N2O (volatilisation)"),
        "application": ("Managed soils", "NH3 - manure applied to soils",
                        "Direct N2O - organic manure"),
        "grazing_cattle_type": ("Managed soils", "NH3 - pasture deposition (cattle-type)",
                                "Direct N2O - pasture deposition (cattle-type)"),
        "grazing_other": ("Managed soils", "NH3 - pasture deposition (sheep/goat/other)",
                          "Direct N2O - pasture deposition (sheep/goat/other)"),
    }
    for (sp, stage), kg_n in sorted(flows["by_species_stage"].items()):
        if kg_n <= 0.0:
            continue
        cat, sub, ghg_sub = STAGE_ROW[stage]
        u = livestock_stage_uncertainty(data, npools, sp, stage)
        add(cat, "%s (%s)" % (sub, sp.replace("_", " ")), ghg_sub, "NH3",
            kg_n * NH3_PER_N / 1e6, u)

    # --- Soil NOx by NITROGEN SOURCE (air spatial Wave A): ~0.7% of APPLIED N as NO-N
    #     (Stehfest & Bouwman; excludes pasture-deposited N and the NH3 volatilisation
    #     pool). The three pools were summed one line before use, which put manure-N
    #     and residue-N on the FERTILISER surface; each now rides its own anchor -
    #     synthetic on cropland-by-fertiliser, manure on the applied-manure surface,
    #     residues on the crop surface. The fraction is linear, so the split is an
    #     exact regrouping of the old single row. ---
    FSN = data.fertilizer["nitrogen_N_offtake"]["value_t"] * 1000.0
    nox_frac = data.efv("soils", "NOx_frac_of_applied")
    nox_efu = data.efu("soils", "NOx_frac_of_applied")
    for sub, ghg_sub, pool_n, act_u in (
            ("Soil NOx - synthetic fertiliser",
             "Direct N2O - synthetic fertiliser (upland)", FSN, fsn_u),
            ("Soil NOx - organic manure",
             "Direct N2O - organic manure", npools["FON_N"], 20),
            ("Soil NOx - crop residues",
             "Direct N2O - crop residues", soils.residue_N(data), 20)):
        nox_n = (npools["field_volat_NOx_N"]["organic"]
                 if "field_volat_NOx_N" in npools and "organic manure" in sub
                 else pool_n * nox_frac)
        add("Managed soils", sub, ghg_sub, "NOx",
            nox_n * NO2_PER_N / 1e6, product(act_u, nox_efu))
    # The common ledger's mixed NH3/NOx management and grazing loss must not
    # disappear from the air panel while remaining in indirect N2O activity.
    if "managed_NOx_N" in npools:
        add("Manure management", "NOx - manure management",
            "Indirect N2O (volatilisation)", "NOx",
            npools["managed_NOx_N"] * NO2_PER_N / 1e6,
            product(20, nox_efu))
        for pool, anchor in (("pasture_cattle", "Direct N2O - pasture deposition (cattle-type)"),
                             ("pasture_other", "Direct N2O - pasture deposition (sheep/goat/other)")):
            add("Managed soils", "NOx - " + pool, anchor, "NOx",
                npools["field_volat_NOx_N"][pool] * NO2_PER_N / 1e6,
                product(20, nox_efu))

    # --- NH3 from crop residues LEFT to decompose in the field (CRR) ---
    crr, _ = crop_residue_nh3(data)
    add("Managed soils", "NH3 - crop residues left in field",
        "Direct N2O - crop residues", "NH3", crr,
        product(20, data.efu("crop_residue_nh3", "slope")))

    # --- Crop-residue field burning PER CROP (mass x Cf x Gef[g/kg] / 1e6 = kt):
    #     the per-crop loop always ran inside mass_burnt and was discarded (air spatial
    #     Wave A); crop identity is what a crop-specific burned-area support keys on,
    #     and the per-crop masses sum to the old whole-sector row exactly. ---
    by_crop = residue_burning.mass_burnt_by_crop(data)
    cf = data.efv("burning", "combustion_factor")
    cf_u = data.efu("burning", "combustion_factor")
    for crop, mb in sorted(by_crop.items()):
        for poll, key in BURN_POLL:
            gef = data.efv("burning", key)
            u = product(20, cf_u, data.efu("burning", key))
            add("Field burning of residues",
                "Residue burning %s (%s)" % (poll, crop), "Residue burning CH4",
                poll, mb * cf * gef / 1e6, u)
    for row in rows:
        row["nitrogen_method"] = npools.get("nitrogen_method", "ipcc")
    return rows


# Imported, not redeclared: the grazing NH3 split must use the same buckets as the
# greenhouse-gas EF3PRP split, and this was previously a second copy of that tuple.
from pkinv.sectors.agriculture.manure import PRP_CATTLE_TYPE  # noqa: E402,F401

# How each manure-management system maps onto the EMEP stage sequence. EMEP is organised by
# livestock and manure type rather than by the IPCC system names, so the correspondence is stated
# here rather than left implicit: a dry lot is an uncovered yard, and daily spread reaches the field
# without a storage stage.
_LEGACY_SYSTEM_STAGES = {
    "solid_storage": ("housing", "storage", "application"),
    "daily_spread": ("housing", "application"),
    "drylot": ("yard", "application"),
    "poultry_litter": ("housing", "storage", "application"),
    "liquid_slurry": ("housing", "storage", "application"),
}

# Kept as a public re-export while the shared material-flow engine owns the stages.
SYSTEM_STAGES = getattr(manure, "SYSTEM_STAGES", _LEGACY_SYSTEM_STAGES)


def livestock_stage_uncertainty(data, npools, species, stage):
    """First-order uncertainty of a stage loss, using that species' factors.

    Stage losses act on surviving TAN. Earlier emission fractions therefore enter
    through their survival terms, whose relative sensitivity is f/(1-f), rather
    than being substituted by the housing uncertainty. The conditional ensemble
    propagates the complete ledger; this value is its auditable local linear
    approximation. Management-system shares remain a separate structural choice.
    """
    herd = manure.MMS_KEY.get(species, species)
    activity_u = data.livestock[herd]["uncert_pct"]
    tan_u = data.efu("nh3_emep_tan", species)
    if stage.startswith("grazing"):
        return product(activity_u, tan_u, data.efu("nh3_emep_grazing", species))
    terms = []
    for row in npools["by_system"]:
        if row["species"] != species:
            continue
        stages = SYSTEM_STAGES.get(row["system"], ())
        if stage not in stages:
            continue
        surviving = float(row["excreted_N"]) * data.efv("nh3_emep_tan", species)
        survival_u = []
        for previous in stages:
            fraction = data.efv("nh3_emep_" + previous, species)
            if previous == stage:
                loss = surviving * fraction
                terms.append((loss, product(activity_u, tan_u,
                                            data.efu("nh3_emep_" + stage, species),
                                            *survival_u), species))
                break
            surviving *= 1.0 - fraction
            if fraction < 1.0:
                survival_u.append(fraction / (1.0 - fraction)
                                  * data.efu("nh3_emep_" + previous, species))
    if not terms:
        # The IPCC alternative has a typed management loss without an EMEP
        # stage fraction. Its own shared ledger carries the matching uncertainty.
        return float(npools.get("managed_volat_uncert_pct", activity_u))
    from pkinv.core.uncertainty import combine_sum
    return combine_sum(terms)[1]


def livestock_nh3_flows(data=None, npools=None):
    """Livestock NH3-N (kg N) by stage, resolved per species and manure system.

    The earlier implementation ran ONE solid-manure chain -- TAN 0.60, housing 0.08, storage 0.32,
    application 0.72, grazing 0.06 of excreted N -- over every species and system, while the
    greenhouse-gas side already resolved per system through IPCC Table 10.22. That was inconsistent
    with this work's own finding that the management split dominates the ammonia uncertainty, and it
    was wrong in specifics: EMEP/EEA Table 3-9 gives buffalo a TAN fraction of 0.50 rather than 0.60
    and a storage factor of 0.17 rather than 0.32, and its grazing factors are proportions of TAN
    (0.14 for cattle and buffalo, 0.09 for small ruminants) rather than of total excreted nitrogen.

    Every factor is now species-specific, taken verbatim from Table 3-9. Camels are not tabulated by
    EMEP; the small-ruminant values are used as the nearest published analogue and carry a wider
    uncertainty to say so.
    """
    if data is None:
        data = InventoryData()
    if npools is None:
        _, npools = manure.compute(data)

    if "stage_nh3_N" in npools:
        # One material account serves NH3 and indirect N2O. Do not start a second
        # TAN chain from pre-management excretion after the shared engine has
        # already debited housing, storage and field losses.
        detail = dict(npools["stage_nh3_N"])
        out = collections.defaultdict(float)
        for (_species, stage), value in detail.items():
            out[stage] += value
        out["grazing"] = out["grazing_cattle_type"] + out["grazing_other"]
        result = dict(out)
        result["by_species_stage"] = detail
        return result

    out = collections.defaultdict(float)
    detail = collections.defaultdict(float)   # (species, stage) -> NH3-N kg
    for row in npools["by_system"]:
        sp, system, n = row["species"], row["system"], row["excreted_N"]
        stages = SYSTEM_STAGES.get(system)
        if not stages:
            continue
        tan = n * data.efv("nh3_emep_tan", sp)
        for stage in stages:
            ef = data.efv("nh3_emep_" + stage, sp)
            lost = tan * ef
            out[stage] += lost
            detail[(sp, stage)] += lost
            tan -= lost                     # each stage acts on the TAN surviving the previous one

    # grazing: EMEP factors are proportions of TAN, so the excreted pool is converted first
    for sp, nex in npools["nex_by_species"].items():
        shares = data.mms[manure.MMS_KEY.get(sp, sp)]
        prp = nex * shares.get("pasture_range_paddock", 0.0)
        lost = prp * data.efv("nh3_emep_tan", sp) * data.efv("nh3_emep_grazing", sp)
        bucket = "grazing_cattle_type" if sp in PRP_CATTLE_TYPE else "grazing_other"
        out[bucket] += lost
        detail[(sp, bucket)] += lost
    out["grazing"] = out["grazing_cattle_type"] + out["grazing_other"]
    result = dict(out)
    # the per-(species, stage) resolution the loop always computed and used to discard
    # (air spatial Wave A): the atoms carry it; the stage totals above remain the
    # backwards-compatible interface every existing consumer reads
    result["by_species_stage"] = dict(detail)
    return result


def crop_residue_nh3(data=None):
    """NH3 (kt) from crop residues left in the field to decompose, and the per-crop working.

    Residues left on the soil can either emit ammonia or immobilise nitrogen, depending on how much
    nitrogen they contain: below a threshold the decomposing microbial biomass consumes more N than
    the residue releases, so there is no net NH3 emission. de Ruijter and Huijsmans (2019), adopted in
    the EMEP/EEA 2023 Guidebook, express this as

        EF = 0                          if N_AG <= 0.0132
        EF = (410 * N_AG - 5.42) / 100  otherwise      [g NH3 per kg dry matter]

    Every crop in Pakistan's inventory sits below the threshold -- cotton is closest at 0.0120 -- so
    the national total is zero. That is now COMPUTED rather than assumed: the term was previously
    declared not-estimated, which left a reader unable to tell a genuine zero from an omission.
    """
    if data is None:
        data = InventoryData()
    slope = data.efv("crop_residue_nh3", "slope")
    intercept = data.efv("crop_residue_nh3", "intercept")
    threshold = data.efv("crop_residue_nh3", "N_threshold")
    total_kt, detail = 0.0, []
    for crop, rp in sorted(data.residue.items()):
        prod = data.crops.get(crop, {}).get("production_t")
        n_ag = rp["n_ag_frac"]
        ef = 0.0 if n_ag <= threshold else (slope * n_ag - intercept) / 100.0
        # dry above-ground residue actually left in the field, i.e. neither removed nor burnt
        left_frac = rp["frac_returned"]
        dm_t = (prod or 0.0) * rp["residue_ratio_ag"] * left_frac
        kt = dm_t * 1000.0 * ef / 1e6 / 1000.0        # t DM -> kg DM -> g NH3 -> kt
        total_kt += kt
        detail.append({"crop": crop, "n_ag_frac": n_ag, "above_threshold": n_ag > threshold,
                       "EF_g_per_kg_DM": ef, "residue_left_t_DM": dm_t, "NH3_kt": kt})
    return total_kt, detail


def crop_residue_nh3_sensitivity(data=None, spread=0.5):
    """How robust is the CRR zero? Vary each crop's residue nitrogen content and see.

    Cotton sits at 0.0120 against a threshold of 0.0132 -- within 10% of it. Reporting an exact zero
    without testing that margin would make a threshold artefact look like a finding, so the residue
    nitrogen contents are perturbed by +/-`spread` and the term recomputed.
    """
    import copy
    if data is None:
        data = InventoryData()
    out = []
    for factor in (1.0 - spread, 1.0, 1.0 + spread):
        d = copy.deepcopy(data)
        d.residue = {c: dict(v) for c, v in d.residue.items()}
        for c in d.residue:
            d.residue[c]["n_ag_frac"] = d.residue[c]["n_ag_frac"] * factor
        total, detail = crop_residue_nh3(d)
        out.append({"n_content_factor": factor, "NH3_kt": total,
                    "crops_above_threshold": [x["crop"] for x in detail if x["above_threshold"]]})
    return out


def _by_pollutant(rows):
    tot = {}
    for r in rows:
        tot[r["pollutant"]] = tot.get(r["pollutant"], 0.0) + r["emissions_kt"]
    return tot


def _provincial(rows):
    """Split each row by the SAME province proxy the GHG layer uses for that nitrogen/biomass stream.

    Proxy resolution is delegated to downscale.proxy_for on the row's `ghg_subitem`, so the air layer
    cannot drift from the GHG allocation (e.g. organic/pasture N follows livestock, not fertiliser)."""
    from pkinv.sectors.agriculture import downscale
    shares = downscale.load_shares()
    for proxy, sh in shares.items():                      # same guard as downscale.allocate_rows
        s = sum(sh.values())
        if abs(s - 1.0) > 1e-6:
            raise ValueError("province shares for '%s' sum to %.6f, not 1.0" % (proxy, s))
    out = []
    for r in rows:
        proxy = downscale.proxy_for({"category": r["category"], "subitem": r["ghg_subitem"]})
        for prov, frac in shares[proxy].items():
            out.append({"province": prov, "category": r["category"], "subitem": r["subitem"],
                        "proxy": proxy, "pollutant": r["pollutant"],
                        "emissions_kt": r["emissions_kt"] * frac})
    return out


ANCHOR_YEAR = 2024


def scopes(rows):
    """Map engine rows to the NH3 scopes the external benchmarks report.

    Prefix sums since the Wave A disaggregation: the synthetic pool is per product and
    the burning pool per crop, and a benchmark scope is a property of the pool."""
    nh3 = [r for r in rows if r["pollutant"] == "NH3"]
    total = sum(r["emissions_kt"] for r in nh3)
    synthetic = sum(r["emissions_kt"] for r in nh3
                    if r["subitem"].startswith("NH3 - synthetic fertiliser"))
    burning = sum(r["emissions_kt"] for r in nh3
                  if r["subitem"].startswith("Residue burning NH3"))
    return {"TOTAL": total, "Managed soils - synthetic": synthetic,
            "Livestock (grazing+manure+management)": total - synthetic - burning,
            "Field burning of residues": burning}


_YEAR_CACHE = {}


def engine_rows_for_year(year):
    """Engine rows on `year`'s activity, or None if that year has no historical activity data.

    The benchmarks report 2015 while our anchor is 2024, and Pakistani agricultural activity grew
    substantially over that interval -- so comparing our anchor against their 2015 conflates activity
    growth with genuine methodological divergence. This rebuilds the engine on the benchmark's own
    year so the two can be separated. Emission factors are held constant, exactly as in the time
    series; only activity varies.
    """
    if year in _YEAR_CACHE:
        return _YEAR_CACHE[year]
    if year == ANCHOR_YEAR:
        _YEAR_CACHE[year] = compute(InventoryData())
        return _YEAR_CACHE[year]
    from pkinv.sectors.agriculture import timeseries as ts  # deferred: avoids a module-level cycle
    try:
        live, crops, nitro = ts._load_history()
    except (OSError, KeyError):                   # history not fetched
        _YEAR_CACHE[year] = None
        return None
    if not (year in live and year in crops and year in nitro):
        _YEAR_CACHE[year] = None
        return None
    data = InventoryData()
    ts._apply_year(data, live[year], crops[year], nitro[year])
    _YEAR_CACHE[year] = compute(data)
    return _YEAR_CACHE[year]


def benchmark(rows):
    """Compare NH3 against independent inventories (data/benchmarks_air.csv).

    Compared AT THE BENCHMARK'S OWN YEAR wherever the historical activity supports it, because the
    benchmarks report 2015 and our anchor is 2024. Both ratios are reported: the matched-year one is
    the meaningful comparison and carries the 0.5-2.0x screen; the anchor-year one is retained but
    labelled, since it also contains nine years of activity growth. Divergences are flagged, never
    tuned away.
    """
    path = asset_path(DATA_DIR, "benchmarks_air.csv")
    if not os.path.exists(path):
        return []
    anchor = scopes(rows)
    out = []
    for b in _read(path):
        av = anchor.get(b["engine_scope"])
        if av is None:
            continue
        bench = float(b["value_kt"])
        byear = int(b["year"])
        brows = engine_rows_for_year(byear)
        matched = brows is not None
        ev = scopes(brows)[b["engine_scope"]] if matched else av
        ratio = ev / bench if bench else None
        out.append({"source": b["source"], "pollutant": b["pollutant"],
                    "scope": b["engine_scope"], "benchmark_kt": bench,
                    "benchmark_year": byear,
                    "engine_kt": ev, "engine_year": byear if matched else ANCHOR_YEAR,
                    "ratio": ratio,
                    "within_0.5_2.0x": "YES" if 0.5 <= ratio <= 2.0 else "REVIEW",
                    "year_matched": "YES" if matched else "NO",
                    "engine_kt_anchor": av,
                    "ratio_anchor": av / bench if bench else None,
                    "activity_growth": av / ev if ev else None,
                    "derived": b["derived"], "note": b["note"]})
    return out


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    rows = compute()
    with open(asset_path(OUT_DIR, "air_pollutants_2024.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["category", "subitem", "pollutant", "emissions_kt", "uncert_pct"])
        for r in rows:
            w.writerow([r["category"], r["subitem"], r["pollutant"], round(r["emissions_kt"], 3),
                        round(r["uncert_pct"], 1)])

    prov = _provincial(rows)
    with open(asset_path(OUT_DIR, "air_pollutants_provincial_2024.csv"), "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["province", "category", "subitem", "proxy", "pollutant", "emissions_kt"])
        for r in prov:
            w.writerow([r["province"], r["category"], r["subitem"], r["proxy"], r["pollutant"],
                        round(r["emissions_kt"], 3)])

    bench = benchmark(rows)
    if bench:
        fields = ["source", "pollutant", "scope", "benchmark_year", "benchmark_kt",
                  "engine_year", "engine_kt", "ratio", "within_0.5_2.0x", "year_matched",
                  "engine_kt_anchor", "ratio_anchor", "activity_growth", "derived", "note"]
        with open(asset_path(OUT_DIR, "benchmark_air_comparison.csv"), "w", newline="",
                  encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for r in bench:
                r = dict(r)
                for k, nd in (("benchmark_kt", 1), ("engine_kt", 1), ("engine_kt_anchor", 1),
                              ("ratio", 2), ("ratio_anchor", 2), ("activity_growth", 2)):
                    if r.get(k) is not None:
                        r[k] = round(r[k], nd)
                w.writerow(r)

    tot = _by_pollutant(rows)
    print("Pakistan agricultural air-pollutant co-emissions (2024, kt; mass, not CO2e):")
    for poll in ("NH3", "CO", "NMVOC", "PM2.5", "NOx", "BC", "SO2"):
        if poll in tot:
            print("  %-7s %9.1f kt" % (poll, tot[poll]))
    if bench:
        print("  NH3 vs independent inventories, compared at the benchmark's own year")
        print("  (0.5-2.0x screen on the matched-year ratio; anchor-year ratio shown for contrast):")
        for r in bench:
            print("    %-18s %-36s %d bench %7.1f  engine %7.1f  x%.2f %-6s | %d x%.2f (growth x%.2f)"
                  % (r["source"], r["scope"][:36], r["benchmark_year"], r["benchmark_kt"],
                     r["engine_kt"], r["ratio"], r["within_0.5_2.0x"],
                     ANCHOR_YEAR, r["ratio_anchor"], r["activity_growth"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
