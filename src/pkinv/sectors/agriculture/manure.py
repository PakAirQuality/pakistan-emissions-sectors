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
from collections import defaultdict

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

# Species-specific EMEP/EEA ammonia factors act on surviving total ammoniacal
# nitrogen (TAN). These are process stages, not additional manure destinations.
SYSTEM_STAGES = {
    "solid_storage": ("housing", "storage", "application"),
    "daily_spread": ("housing", "application"),
    "drylot": ("yard", "application"),
    "poultry_litter": ("housing", "storage", "application"),
    "liquid_slurry": ("housing", "storage", "application"),
}
NITROGEN_METHODS = ("tan", "ipcc")


def nitrogen_method(data, method=None):
    """The complete nitrogen formulation; a structural choice, never sampled."""
    chosen = method or getattr(data, "nitrogen_method", "tan")
    if chosen not in NITROGEN_METHODS:
        raise ValueError("nitrogen method must be 'tan' or 'ipcc', got %r" % chosen)
    return chosen


def _fraction(value, label):
    if not 0.0 <= value <= 1.0:
        raise ValueError("%s is %.8g, outside [0,1]" % (label, value))
    return value


def _nitrogen_close(initial, parts, label):
    residual = initial - sum(parts)
    # Inputs are float64 model quantities, not rounded source controls.
    if abs(residual) > max(1e-7, abs(initial) * 1e-12):
        raise ValueError("nitrogen ledger %s does not close: %.8g kg N" % (label, residual))
    return residual


def _cattle_split(data):
    cattle = data.livestock["cattle"]
    share = data.p("dairy_cattle_share")
    return {"dairy_cattle": cattle["head"] * share,
            "other_cattle": cattle["head"] * (1 - share)}


def _temp_blend(data, base):
    warm, cool = data.p("warm_zone_share"), data.p("cool_zone_share")
    return (warm * data.efv("manure_ch4", base + "_warm")
            + cool * data.efv("manure_ch4", base + "_cool"))


def compute(data, method=None):
    """GHG components and conserved N/TAN pools for the selected formulation.

    ``tan`` uses species-specific EMEP ammonia losses and retains IPCC management
    leaching, N2 and direct N2O losses. ``ipcc`` is the complete original IPCC
    volatilisation formulation. FON is nitrogen delivered to fields before
    application losses; direct soil factors must continue to multiply that gross
    input. Diverted dung is an unresolved destination, not observed combustion.
    """
    method = nitrogen_method(data, method)
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
    stage_nh3 = defaultdict(float)
    field_nh3 = defaultdict(float)
    field_nox = defaultdict(float)
    managed_nh3 = managed_nox = 0.0
    nh3_share = _fraction(data.efv("soils", "NH3_frac_of_volat"), "NH3 share of volatilised N")
    if nh3_share <= 0:
        raise ValueError("NH3 share must be positive to resolve the NOx-N loss")
    nox_per_nh3 = (1.0 - nh3_share) / nh3_share
    for sp, nx in nex_total.items():
        shares = data.mms[MMS_KEY.get(sp, sp)]
        cls = FRACGASMS_CLASS[sp]
        prp = shares.get("pasture_range_paddock", 0.0)
        if sp in PRP_CATTLE_TYPE:
            FPRP_cattle_N += nx * prp
            field_key, stage_key = "pasture_cattle", "grazing_cattle_type"
        else:
            FPRP_other_N += nx * prp
            field_key, stage_key = "pasture_other", "grazing_other"
        prp_n = nx * prp
        if method == "tan":
            tan_fraction = _fraction(data.efv("nh3_emep_tan", sp), "TAN fraction for %s" % sp)
            grazed_nh3 = prp_n * tan_fraction * _fraction(
                data.efv("nh3_emep_grazing", sp), "grazing NH3 fraction for %s" % sp)
            grazed_nox = grazed_nh3 * nox_per_nh3
        else:
            total = prp_n * data.efv("soils", "FracGASM")
            grazed_nh3, grazed_nox = total * nh3_share, total * (1.0 - nh3_share)
        if grazed_nh3 + grazed_nox > prp_n + 1e-7:
            raise ValueError("grazing volatilisation exceeds deposited N for %s" % sp)
        field_nh3[field_key] += grazed_nh3
        field_nox[field_key] += grazed_nox
        stage_nh3[(sp, stage_key)] += grazed_nh3
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
            other_losses = n_sys * (leachms + n2ms + ef3)
            details = []
            initial_tan = n_sys * _fraction(data.efv("nh3_emep_tan", sp), "TAN fraction for %s" % sp)
            tan = initial_tan
            nh3_n = nox_n = 0.0
            if method == "tan":
                for stage in SYSTEM_STAGES[system]:
                    if stage == "application":
                        continue
                    ef = _fraction(data.efv("nh3_emep_" + stage, sp), "%s NH3 fraction for %s" % (stage, sp))
                    incoming = tan
                    loss_nh3 = incoming * ef
                    loss_nox = loss_nh3 * nox_per_nh3
                    if loss_nh3 + loss_nox > incoming + 1e-7:
                        raise ValueError("%s volatilisation exceeds TAN for %s" % (stage, sp))
                    tan -= loss_nh3 + loss_nox
                    nh3_n += loss_nh3
                    nox_n += loss_nox
                    stage_nh3[(sp, stage)] += loss_nh3
                    details.append({"stage": stage, "input_TAN_N": incoming,
                                    "NH3_N": loss_nh3, "NOx_N": loss_nox,
                                    "remaining_TAN_N": tan})
                gasms = (nh3_n + nox_n) / n_sys if n_sys else 0.0
            else:
                nh3_n = n_sys * gasms * nh3_share
                nox_n = n_sys * gasms * (1.0 - nh3_share)
                # IPCC has a system-total fraction, no stage-resolved observation.
                stage = "yard" if system == "drylot" else "housing"
                stage_nh3[(sp, stage)] += nh3_n
            frac_loss = gasms + leachms + n2ms + ef3                # Eq 10.34a
            if not 0.0 <= frac_loss < 1.0:
                raise ValueError("FracLossMS for %s/%s is %.3f, outside [0,1)"
                                 % (sp, system, frac_loss))
            managed_N_total += n_sys
            volat_managed_N += n_sys * gasms
            managed_nh3 += nh3_n
            managed_nox += nox_n
            leach_managed_N += n_sys * leachms
            n2_managed_N += n_sys * n2ms
            applied_n = n_sys * (1 - frac_loss)
            FON_N += applied_n                                     # Eq 10.34
            _nitrogen_close(n_sys, (nh3_n, nox_n, other_losses, applied_n), "%s/%s management" % (sp, system))
            if method == "tan":
                # Other management losses remove TAN and organic N in proportion
                # to the surviving pools; no evidence selects a different split.
                after_volat_n = n_sys - nh3_n - nox_n
                tan *= applied_n / after_volat_n if after_volat_n else 0.0
                application_nh3 = tan * _fraction(data.efv("nh3_emep_application", sp), "application NH3 fraction for %s" % sp)
                application_nox = applied_n * data.efv("soils", "NOx_frac_of_applied")
            else:
                total = applied_n * data.efv("soils", "FracGASM")
                application_nh3, application_nox = total * nh3_share, total * (1.0 - nh3_share)
            if application_nh3 + application_nox > applied_n + 1e-7:
                raise ValueError("application volatilisation exceeds FON for %s/%s" % (sp, system))
            field_nh3["organic"] += application_nh3
            field_nox["organic"] += application_nox
            stage_nh3[(sp, "application")] += application_nh3
            if method == "tan":
                # Conditional factor width on the species-specific TAN sequence;
                # a complete parameter rerun is available below for constrained draws.
                stage_u = max(data.efu("nh3_emep_" + stage, sp)
                              for stage in SYSTEM_STAGES[system] if stage != "application")
                loss_u = product(data.efu("nh3_emep_tan", sp), stage_u)
            else:
                loss_u = data.efu("manure_fracgasms", cls + "_" + system)
            volat_terms.append((n_sys * gasms, loss_u))
            by_system.append({"species": sp, "system": system, "class": cls,
                              "excreted_N": n_sys, "FracGasMS": gasms,
                              "FracLeachMS": leachms, "FracN2MS": n2ms, "EF3": ef3,
                              "FracLossMS": frac_loss,
                              "volat_N": n_sys * gasms, "leach_N": n_sys * leachms,
                              "n2_N": n_sys * n2ms, "n2o_N": n_sys * ef3,
                              "applied_N": applied_n,
                              "NH3_N": nh3_n, "NOx_N": nox_n,
                              "TAN_initial_N": initial_tan,
                              "TAN_after_management_N": tan if method == "tan" else None,
                              "application_NH3_N": application_nh3,
                              "application_NOx_N": application_nox,
                              "stage_detail": details,
                              "nitrogen_method": method})

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
              "by_system": by_system, "nitrogen_method": method,
              "stage_nh3_N": dict(stage_nh3),
              "field_volat_NH3_N": dict(field_nh3),
              "field_volat_NOx_N": dict(field_nox),
              "managed_NH3_N": managed_nh3, "managed_NOx_N": managed_nox}
    _nitrogen_close(npools["excreted_N"],
                    (managed_N_total, FPRP_cattle_N, FPRP_other_N, diverted_N_total), "excretion destinations")
    _nitrogen_close(managed_N_total,
                    (FON_N, volat_managed_N, leach_managed_N, n2_managed_N, n2o_direct_N), "managed fate")
    return components, npools


def rerun_nitrogen(data, livestock_scales=None, factor_values=None, method=None,
                   activity_scales=None):
    """Rerun the conserved fate ledger and soils on one shared parameter realisation.

    Sampling is the caller's responsibility: ``livestock_scales`` is keyed by
    inventory species and ``factor_values`` by (factor_category, factor_item).
    Fractional factors must be supplied within their physical domain; this helper
    never repairs an invalid draw by clipping an emission or a nitrogen residual.
    It supports native GHG/AP paired draws instead of independent emission-row
    multipliers, which cannot conserve a shared material ledger.
    """
    from copy import copy
    from pkinv.sectors.agriculture import soils

    # The factor library and management tables are immutable inputs. Copy only
    # the state that changes in a realisation, keeping large native ensembles
    # practical without changing the equations or parameter draws.
    draw = copy(data)
    draw.livestock = {key: dict(value) for key, value in data.livestock.items()}
    draw.crops = {key: dict(value) for key, value in data.crops.items()}
    draw.fertilizer = {key: dict(value) for key, value in data.fertilizer.items()}
    for species, scale in (livestock_scales or {}).items():
        if scale < 0:
            raise ValueError("negative livestock scale for %s" % species)
        draw.livestock[species]["head"] *= scale
    for key, scale in (activity_scales or {}).items():
        if scale < 0:
            raise ValueError("negative nitrogen input scale for %s" % key)
        if key == "fertiliser":
            draw.fertilizer["nitrogen_N_offtake"]["value_t"] *= scale
        elif key.startswith("crop:"):
            draw.crops[key.split(":", 1)[1]]["production_t"] *= scale
        else:
            raise KeyError("unknown nitrogen input scale %r" % key)
    original = draw.efv
    values = factor_values or {}
    draw.efv = lambda category, item: values.get((category, item), original(category, item))
    # Avoid caching by object id during an ensemble: short-lived draw objects
    # can reuse ids. The weighted synthetic NH3 fraction uses this draw's actual
    # product factors, not a value retained from a previous realisation.
    from pkinv.sectors.agriculture import fertiliser_mix
    shares = getattr(data, "nitrogen_product_shares", None)
    if shares is None:
        shares, _ = fertiliser_mix.national_shares(data)
    draw.nitrogen_fracgasf = sum(share * draw.efv("fert_nh3_highpH", item)
                               for item, share in shares.items())
    components, pools = compute(draw, method=method)
    components += soils.compute(draw, pools)
    # Expose these exact replayed inputs to the air consumer rather than sampling
    # a second aggregate nitrogen quantity with a different uncertainty width.
    from pkinv.sectors.agriculture.air_pollutants import crop_residue_nh3
    pools["FSN_N"] = draw.fertilizer["nitrogen_N_offtake"]["value_t"] * 1000.0
    pools["FCR_N"] = soils.residue_N(draw)
    pools["crop_residue_NH3_Gg"] = crop_residue_nh3(draw)[0]
    return components, pools
