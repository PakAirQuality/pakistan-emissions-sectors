"""Manure management - CH4 (Eq 10.22) and N2O direct (Eq 10.25) + indirect
(Eq 10.26) - IPCC Tier 1.

Also returns the manure-derived nitrogen pools needed by the managed-soils module:
  FON_N  = managed manure N available for application to soils (Eq 10.34)
  FPRP_N = N excreted on pasture/range/paddock (handled as soils FPRP)
so that pasture and applied-manure N2O are counted in soils, not double-counted here.

NITROGEN BOUNDARY (corrected; see Eq 10.34/10.34a/10.34b of the 2019 Refinement).
Two fractions govern different stages and must not be interchanged:

  FracGasMS  - NH3/NOx volatilised INSIDE the manure management system (housing and
               storage), i.e. BEFORE manure reaches the field. Table 10.22, per animal
               class and system. This is what reduces the manure available for
               application, together with leaching, N2 and the N2O-N already emitted:

                   FracLossMS = FracGasMS + FracLeachMS + FracN2MS + EF3   (Eq 10.34a)
                   FracN2MS   = RN2_N2O x EF3                              (Eq 10.34b)
                   FON        = SUM  N_managed(sp,sys) x (1 - FracLossMS)  (Eq 10.34)

  FracGASM   - NH3/NOx volatilised AFTER organic N is applied to soil or deposited at
               grazing. Table 11.3. It is applied ONCE, in soils.py, to drive indirect
               N2O; under Tier 1 it does NOT reduce FON before direct soil N2O.

An earlier implementation used FracGASM at the pre-field boundary AND again on the
survivor in soils.py, so one post-application fraction stood in for a pre-field loss
and was counted twice on the same nitrogen. Both are corrected here.
"""
from pkinv.core.uncertainty import product, combine_sum

N2O_N_TO_N2O = 44.0 / 28.0
MANAGED_SYSTEMS = ("daily_spread", "solid_storage", "drylot", "liquid_slurry",
                   "poultry_litter")
# Systems whose nitrogen leaves the agriculture sector rather than reaching soils.
# Dung cake is burnt as household fuel; its N is reported under Energy/Waste (IE).
DIVERTED_SYSTEMS = ("burned_fuel",)

# Table 10.22 is tabulated by animal column, not by our herd species. Buffalo take the
# Dairy Cow column: Ch10 categorises dairy buffalo as dairy cows, IPCC's "Other animals"
# column is the sheep-type group (cf. X=SO "Sheep and Other animals" in Ch11), and
# Pakistan's buffalo herd is predominantly dairy. The Other Cattle alternative is
# carried as a structural sensitivity in src/pkinv/eval/n_ledger_runs.py.
FRACGASMS_CLASS = {"dairy_cattle": "dairy_cattle", "other_cattle": "other_cattle",
                   "buffalo": "buffalo", "sheep": "other_animals",
                   "goats": "other_animals", "camels": "other_animals",
                   "poultry": "poultry"}
# mms_shares.csv is keyed by herd species; dairy and other cattle share the cattle row.
MMS_KEY = {"dairy_cattle": "cattle", "other_cattle": "cattle"}
# EF3PRP buckets: cattle/buffalo/poultry -> "cattle-type"; sheep/goats/camels -> "other".
# Module scope because the air-pollutant layer needs the same split for grazing NH3, and
# previously kept its own copy of this tuple with no import between them.
PRP_CATTLE_TYPE = ("dairy_cattle", "other_cattle", "buffalo", "poultry")


def _cattle_split(data):
    cattle = data.livestock["cattle"]
    share = data.p("dairy_cattle_share")
    return {"dairy_cattle": cattle["head"] * share,
            "other_cattle": cattle["head"] * (1 - share)}


def _temp_blend(data, base):
    warm, cool = data.p("warm_zone_share"), data.p("cool_zone_share")
    return (warm * data.efv("manure_ch4", base + "_warm")
            + cool * data.efv("manure_ch4", base + "_cool"))


def compute(data):
    components = []
    split = _cattle_split(data)

    # ---- CH4 (Eq 10.22) ----
    ch4_ef = {
        "dairy_cattle": _temp_blend(data, "dairy_cattle"),
        "other_cattle": _temp_blend(data, "other_cattle"),
        "buffalo": _temp_blend(data, "buffalo"),
        "sheep": data.efv("manure_ch4", "sheep"),
        "goats": data.efv("manure_ch4", "goats"),
        "camels": data.efv("manure_ch4", "camels"),
        "poultry": data.efv("manure_ch4", "poultry"),
    }
    heads = {
        "dairy_cattle": (split["dairy_cattle"], data.livestock["cattle"]["uncert_pct"]),
        "other_cattle": (split["other_cattle"], data.livestock["cattle"]["uncert_pct"]),
        "buffalo": (data.livestock["buffalo"]["head"], data.livestock["buffalo"]["uncert_pct"]),
        "sheep": (data.livestock["sheep"]["head"], data.livestock["sheep"]["uncert_pct"]),
        "goats": (data.livestock["goats"]["head"], data.livestock["goats"]["uncert_pct"]),
        "camels": (data.livestock["camels"]["head"], data.livestock["camels"]["uncert_pct"]),
        "poultry": (data.livestock["poultry"]["head"], data.livestock["poultry"]["uncert_pct"]),
    }
    for sp, (head, adu) in heads.items():
        emis_gg = head * ch4_ef[sp] / 1e6
        u = product(adu, data.efu("manure_ch4", "sheep"))  # all manure CH4 EFs ~30%
        components.append({"category": "Manure management", "subitem": sp + " (CH4)",
                           "gas": "CH4", "emissions_Gg": emis_gg, "uncert_pct": u})

    # ---- Nitrogen pools per species: Nex_total, managed N, PRP N ----
    # Cattle are kept split into dairy/other here (not pooled as in the CH4 step) because
    # Table 10.22 gives them different volatilisation fractions.
    nex_total = {}      # engine species -> kg N/yr
    nex_total["dairy_cattle"] = split["dairy_cattle"] * data.nex_per_head("dairy_cattle")
    nex_total["other_cattle"] = split["other_cattle"] * data.nex_per_head("other_cattle")
    for sp in ("buffalo", "sheep", "goats", "camels", "poultry"):
        nex_total[sp] = data.livestock[sp]["head"] * data.nex_per_head(sp)

    rn2 = data.efv("manure_n2", "RN2_N2O")
    FON_N = 0.0          # managed manure N available for application to soils (Eq 10.34)
    FPRP_cattle_N = 0.0  # pasture N from cattle-type animals (EF3PRP 0.002)
    FPRP_other_N = 0.0   # pasture N from sheep/goats/camels (EF3PRP 0.003)
    n2o_direct_N = 0.0
    volat_managed_N = 0.0    # NH3-N + NOx-N lost in housing and storage (FracGasMS)
    leach_managed_N = 0.0    # N lost by leaching/runoff in the MMS (FracLeachMS)
    n2_managed_N = 0.0       # N lost as N2 in the MMS (Eq 10.34b)
    managed_N_total = 0.0
    diverted_N_total = 0.0   # dung cake etc.: excreted but never enters the MMS balance
    volat_terms = []         # (kg N, uncert %) for the weighted FracGasMS uncertainty
    by_system = []           # per species x system detail for the nitrogen ledger
    for sp, nx in nex_total.items():
        shares = data.mms[MMS_KEY.get(sp, sp)]
        cls = FRACGASMS_CLASS[sp]
        prp = shares.get("pasture_range_paddock", 0.0)
        if sp in PRP_CATTLE_TYPE:
            FPRP_cattle_N += nx * prp
        else:
            FPRP_other_N += nx * prp
        for system, share in shares.items():
            n_sys = nx * share
            ef3 = data.efv("manure_n2o_ef3", system)
            # direct N2O during management applies to every system (Eq 10.25)
            n2o_direct_N += n_sys * ef3
            if system in DIVERTED_SYSTEMS:
                diverted_N_total += n_sys
                continue
            if system not in MANAGED_SYSTEMS:
                continue                      # pasture/range/paddock -> soils FPRP
            gasms = data.efv("manure_fracgasms", cls + "_" + system)
            leachms = data.efv("manure_fracleachms", system)
            n2ms = rn2 * ef3                                        # Eq 10.34b
            frac_loss = gasms + leachms + n2ms + ef3                # Eq 10.34a
            if not 0.0 <= frac_loss < 1.0:
                raise ValueError("FracLossMS for %s/%s is %.3f, outside [0,1)"
                                 % (sp, system, frac_loss))
            managed_N_total += n_sys
            volat_managed_N += n_sys * gasms
            leach_managed_N += n_sys * leachms
            n2_managed_N += n_sys * n2ms
            FON_N += n_sys * (1 - frac_loss)                        # Eq 10.34
            volat_terms.append((n_sys * gasms,
                                data.efu("manure_fracgasms", cls + "_" + system)))
            by_system.append({"species": sp, "system": system, "class": cls,
                              "excreted_N": n_sys, "FracGasMS": gasms,
                              "FracLeachMS": leachms, "FracN2MS": n2ms, "EF3": ef3,
                              "FracLossMS": frac_loss,
                              "volat_N": n_sys * gasms, "leach_N": n_sys * leachms,
                              "n2_N": n_sys * n2ms, "n2o_N": n_sys * ef3,
                              "applied_N": n_sys * (1 - frac_loss)})

    # ---- N2O direct (Eq 10.25) ----
    direct_gg = n2o_direct_N * N2O_N_TO_N2O / 1e6
    components.append({"category": "Manure management", "subitem": "Direct N2O",
                       "gas": "N2O", "emissions_Gg": direct_gg,
                       "uncert_pct": product(15, data.efu("manure_n2o_ef3", "solid_storage"))})

    # ---- N2O indirect: volatilisation during management (Eq 10.26) ----
    # Explicit dry EF4 (Pakistan predominantly arid), harmonised with the managed-soils
    # indirect-volatilisation treatment in soils.py so the same flux family uses one EF.
    ef4 = data.efv("soils", "EF4_dry")
    indirect_gg = volat_managed_N * ef4 * N2O_N_TO_N2O / 1e6
    # The volatilised pool is a sum over species x system, each carrying its own Table 10.22
    # uncertainty; combine them by magnitude (Eq 3.2) before the product rule (Eq 3.1).
    _, volat_u = combine_sum(volat_terms)
    components.append({"category": "Manure management", "subitem": "Indirect N2O (volatilisation)",
                       "gas": "N2O", "emissions_Gg": indirect_gg,
                       "uncert_pct": product(20, volat_u, data.efu("soils", "EF4_dry"))})

    npools = {"FON_N": FON_N, "FPRP_cattle_N": FPRP_cattle_N,
              "FPRP_other_N": FPRP_other_N, "volat_managed_N": volat_managed_N,
              # N excreted into managed (non-pasture, non-fuel) systems, before any loss;
              # the air-pollutant layer runs its own EMEP TAN mass flow over this pool.
              "managed_N": managed_N_total,
              # remaining Eq 10.34a loss terms, kept for the nitrogen ledger
              "leach_managed_N": leach_managed_N, "n2_managed_N": n2_managed_N,
              "n2o_managed_N": n2o_direct_N, "diverted_N": diverted_N_total,
              "excreted_N": sum(nex_total.values()), "nex_by_species": nex_total,
              "by_system": by_system}
    return components, npools
