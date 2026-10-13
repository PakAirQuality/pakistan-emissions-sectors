"""Managed-soils N2O - IPCC Tier 1, direct (Eq 11.1) and indirect
(Eq 11.9 volatilisation, Eq 11.10 leaching), with 2019 Refinement EFs.

Nitrogen input streams (kg N/yr):
  FSN  synthetic fertiliser N      (NFDC offtake)
  FON  organic/manure N applied    (from manure module, after storage volatilisation)
  FCR  crop-residue N returned     (Eq 11.6, residue_params.csv)
  FSOM N mineralised from SOC loss (set 0 at Tier 1)
  FPRP N excreted on pasture       (from manure module; split by EF3PRP class)
"""
from pkinv.core.uncertainty import product

N2O_N_TO_N2O = 44.0 / 28.0


def residue_N(data):
    """FCR: crop residue N returned to soil (kg N), Eq 11.6 simplified."""
    total = 0.0
    for crop, rp in data.residue.items():
        prod = data.crops.get(crop, {}).get("production_t")
        if not prod:
            continue
        ag_dry = prod * rp["residue_ratio_ag"]            # tonnes dry above-ground
        bg_dry = ag_dry * rp["below_above_ratio"]         # tonnes dry below-ground
        n_t = (ag_dry * rp["frac_returned"] * rp["n_ag_frac"]
               + bg_dry * rp["n_bg_frac"])                # tonnes N
        total += n_t * 1000.0                              # -> kg N
    return total


def compute(data, npools, ef1_override=None):
    """Managed-soils N2O. ef1_override (kg N2O-N/kg N) forces the upland EF1 for the
    sensitivity pass (e.g. 0.010 Pakistan-official); None uses the Tier 2 dry default."""
    components = []
    FSN = data.fertilizer["nitrogen_N_offtake"]["value_t"] * 1000.0   # kg N
    FSN_u = data.fertilizer["nitrogen_N_offtake"]["uncert_pct"]
    FON = npools["FON_N"]
    FCR = residue_N(data)
    FPRP_cattle = npools["FPRP_cattle_N"]
    FPRP_other = npools["FPRP_other_N"]

    # Tier 2: irrigated arid cropland -> dry EF1 (best-supported); rice N -> EF1FR
    ef1 = data.efv("soils", "EF1_dry") if ef1_override is None else ef1_override
    ef1fr = data.efv("soils", "EF1FR_rice")
    ef1_u = data.efu("soils", "EF1_dry")
    rice_frac = data.p("rice_N_fraction")          # share of synthetic N applied to rice
    FSN_rice = FSN * rice_frac
    FSN_upland = FSN - FSN_rice

    # ---- Direct N2O (Eq 11.1) ----
    def direct(label, n_kg, ef, ad_u, ef_u):
        gg = n_kg * ef * N2O_N_TO_N2O / 1e6
        components.append({"category": "Managed soils", "subitem": label, "gas": "N2O",
                           "emissions_Gg": gg, "uncert_pct": product(ad_u, ef_u)})

    direct("Direct N2O - synthetic fertiliser (upland)", FSN_upland, ef1, FSN_u, ef1_u)
    direct("Direct N2O - synthetic fertiliser (rice EF1FR)", FSN_rice, ef1fr, FSN_u,
           data.efu("soils", "EF1FR_rice"))
    direct("Direct N2O - organic manure", FON, ef1, 30, ef1_u)
    direct("Direct N2O - crop residues", FCR, ef1, 30, ef1_u)
    direct("Direct N2O - pasture deposition (cattle-type)", FPRP_cattle,
           data.efv("soils", "EF3PRP_cattle"), 20, data.efu("soils", "EF3PRP_cattle"))
    direct("Direct N2O - pasture deposition (sheep/goat/other)", FPRP_other,
           data.efv("soils", "EF3PRP_sheepgoat"), 20, data.efu("soils", "EF3PRP_sheepgoat"))

    # ---- Indirect N2O - volatilisation (Eq 11.9) -- explicit dry EF4 ----
    # Reported per SOURCE STREAM rather than as one lumped row. The magnitudes are identical either
    # way, but a lumped row can only carry one spatial proxy, and most of this nitrogen is
    # livestock-derived: routing the whole row on fertiliser offtake put ~70% of it on the wrong
    # geography. Each stream now follows the proxy of the nitrogen that produced it (downscale.PROXY_MAP).
    ef4 = data.efv("soils", "EF4_dry")
    ef4_u = product(20, data.efu("soils", "EF4_dry"))
    sv = volatilised_n(data, npools)
    for label, key in (("synthetic fertiliser", "synthetic"), ("organic manure", "organic"),
                       ("pasture, cattle-type", "pasture_cattle"),
                       ("pasture, sheep/goat/other", "pasture_other")):
        components.append({"category": "Managed soils",
                           "subitem": "Indirect N2O - volatilisation (%s)" % label, "gas": "N2O",
                           "emissions_Gg": sv[key] * ef4 * N2O_N_TO_N2O / 1e6,
                           "uncert_pct": ef4_u, "corr_group": "soils_volat"})

    # ---- Indirect N2O - leaching/runoff (Eq 11.10) ----
    ef5 = data.efv("soils", "EF5")
    ef5_u = product(20, data.efu("soils", "EF5"))
    fracleach = data.efv("soils", "FracLEACH") * data.p("leach_applicable_fraction")
    for label, n_kg in (("synthetic fertiliser", FSN), ("organic manure", FON),
                        ("crop residues", FCR), ("pasture, cattle-type", FPRP_cattle),
                        ("pasture, sheep/goat/other", FPRP_other)):
        components.append({"category": "Managed soils",
                           "subitem": "Indirect N2O - leaching/runoff (%s)" % label, "gas": "N2O",
                           "emissions_Gg": n_kg * fracleach * ef5 * N2O_N_TO_N2O / 1e6,
                           "uncert_pct": ef5_u, "corr_group": "soils_leach"})

    return components


def volatilised_n(data, npools, basis="NH3+NOx"):
    """Volatilised soil-N pool (kg N) per source stream.

    TWO CHEMICAL BASES, and they must not be confused -- the streams do not share one:

      basis="NH3+NOx"  total volatilised N, which is what Eq 11.9 needs to drive indirect N2O
      basis="NH3"      the ammonia-nitrogen part only, which is what the air-pollutant layer reports

    The synthetic and organic streams reach those bases from opposite directions. The IPCC
    FracGASM (Table 11.3) is defined on NH3 *and* NOx together, so the NH3 part is obtained by
    taking the NH3 share of it. The EMEP/EEA product factors are published as NH3-N directly, so
    for synthetic fertiliser the NH3 part is the primary quantity and the NOx-N term is added to
    reach the total:

        synthetic:        NH3-N = FSN x f_NH3        NOx-N = FSN x f_NO
        organic/pasture:  total = N x FracGASM       NH3-N = total x NH3_frac_of_volat

    Applying the NH3 share to the already-NH3-N product factor -- as an earlier version did -- both
    understates ammonia and leaves the indirect-N2O pool missing its NOx-N term, so the split stops
    conserving nitrogen. tests/test_fertiliser_mix.py pins the conservation.

    Keys mirror the managed-soils subitems in soils.compute(), because each stream follows a
    different province proxy (fertiliser vs livestock vs small-ruminant). This is the ONLY place the
    synthetic fraction is resolved, so the air layer's NH3 and the greenhouse-gas layer's synthetic
    indirect N2O necessarily use the same number.
    """
    from pkinv.sectors.agriculture import fertiliser_mix
    if basis not in ("NH3+NOx", "NH3"):
        raise ValueError("basis must be 'NH3+NOx' or 'NH3', not %r" % basis)
    FSN = data.fertilizer["nitrogen_N_offtake"]["value_t"] * 1000.0
    f_nh3_sf, _ = fertiliser_mix.fracgasf(data)             # kg NH3-N per kg synthetic N
    f_no_sf = data.efv("soils", "NOx_frac_of_applied")      # kg NO-N per kg N applied
    fracgasm = data.efv("soils", "FracGASM")                # NH3 + NOx, IPCC Table 11.3
    nh3_share = data.efv("soils", "NH3_frac_of_volat")

    synthetic = FSN * (f_nh3_sf if basis == "NH3" else f_nh3_sf + f_no_sf)
    organic_f = fracgasm * (nh3_share if basis == "NH3" else 1.0)
    out = {
        "synthetic": synthetic,
        "organic": npools["FON_N"] * organic_f,
        "pasture_cattle": npools["FPRP_cattle_N"] * organic_f,
        "pasture_other": npools["FPRP_other_N"] * organic_f,
    }
    out["total"] = sum(out.values())
    return out
