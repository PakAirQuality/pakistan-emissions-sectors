"""Provenance and parameter identities for the existing air calculation engines.

No activity is estimated here. These adapters read the quantities and factor rows
the engines already use. Structural technology or sulfur endpoints are recorded
beside the conditional parameter model, never converted into confidence limits.
"""
import json
import math
import re
from functools import lru_cache


def driver(identity, uncertainty, kind="factor", evidence="declared conditional 95% half-width"):
    return {"id": identity, "uncert_pct": float(uncertainty or 0.0),
            "kind": kind, "evidence": evidence}


def fraction_driver(identity, mean, uncertainty, complement=False, evidence="declared conditional fraction uncertainty"):
    result = driver(identity, uncertainty, evidence=evidence)
    result.update(distribution="bounded_beta", mean=float(mean), complement=bool(complement))
    return result


@lru_cache(None)
def _data(sector):
    if sector == "residential":
        from pkinv.sectors.residential.data import ResidentialData
        return ResidentialData()
    if sector == "transport":
        from pkinv.sectors.transport.data import TransportData
        return TransportData()
    if sector == "railways":
        from pkinv.sectors.railways.data import RailwaysData
        return RailwaysData()
    if sector == "aviation":
        from pkinv.sectors.aviation.data import AviationData
        return AviationData()
    if sector == "waste":
        from pkinv.sectors.waste.data import WasteData
        return WasteData()
    if sector == "classes":
        from pkinv.sectors.industry.air_pollutants import Context
        return Context()
    raise KeyError(sector)


@lru_cache(None)
def _agriculture(year, method="tan"):
    from pkinv.sectors.agriculture.fiscal_activity import data_for_fiscal_year
    data = data_for_fiscal_year(year)
    data.nitrogen_method = method
    return data


def _ef(d, category, item):
    if item in ("BC_of_PM2.5", "BC_fraction", "combustion_factor") or category.endswith("_frac"):
        return fraction_driver("factor:%s:%s" % (category, item), d.efv(category, item), d.efu(category, item))
    return driver("factor:%s:%s" % (category, item), d.efu(category, item))


@lru_cache(None)
def _classes():
    from pkinv.sectors.industry.air_pollutants import classes
    return {r["source_class_id"]: r for r in classes()}


@lru_cache(None)
def _transport_inputs(year):
    from pkinv.sectors.transport import air_pollutants as ap, road
    data = _data("transport")
    return ap.fuel_kt_by_class(data, year), ap.active_counts(data, year), road.effective_vkt(data, year)[0]


def so2_sulfur_boundary(cls, year, factors):
    """Which sulfur an SO2 atom carries, and what removes it - stated on the record (rc68 air
    review, criterion 6). Fuel sulfur, raw-material sulfur and retention or removal are three
    different terms; a sulfur balance on fuel says nothing about the clay or kiln feed, and a
    declared retention fraction is an assumption, not an observed control."""
    from pkinv.core import sulfur
    if any(f["activity_basis"] == "sulfur_balance" for f in factors):
        s = sulfur.evidence(cls["sulfur_evidence_id"], year, cls["source_class_id"])
        r = float(cls["sulfur_retention_frac"] or 0)
        ru = float(cls["sulfur_retention_uncert_pct"] or 0)
        text = ("SO2 boundary: FUEL sulfur only (evidence %s, basis %s, central %s pct, band %s-%s; "
                "a transferred value, not an own-year national assay)" %
                (cls["sulfur_evidence_id"], s["basis"], s["s_pct_central"], s["s_pct_lo"], s["s_pct_hi"]))
        if cls["sulfur_evidence_id"] == "coal_punjab_fields":
            text += ("; three as-fired batches (2012 ICT, 2022 Punjab) are not a national sampling "
                     "design")
        if cls["activity_function"] == "industry.coal_kt:brick_kilns":
            text += "; raw-material (clay) sulfur NOT estimated"
        else:
            text += "; non-fuel (feed/raw-material) sulfur not estimated"
        if r:
            text += ("; retention %.2f (+/-%g pct) in ash/product is an ASSUMED fraction, not "
                     "measured removal; no control device credited" % (r, ru))
        else:
            text += "; no retention, removal or control device credited"
        return text
    if cls["source_class_id"].startswith("cement_kiln"):
        return ("SO2 boundary: AP-42 kiln factor per tonne clinker; fuel and raw-meal sulfur and "
                "in-kiln alkali retention are combined in the factor and are not separable here")
    return "SO2 boundary: factor-based; fuel sulfur implicit in the cited factor"


def enrich(sector, year, row, process="", fuel=""):
    """Canonical attributes of an engine row, including a replayable driver list."""
    pol = row["pollutant"]
    sub = row.get("subitem", "")
    out = {"source_id": "%s:%s" % (sector, sub or fuel),
           "calculation_module": "pkinv.sectors.%s.air_pollutants" % sector,
           "maturity": "estimated", "activity_value": "", "activity_unit": "",
           "activity_provenance": "", "factor_ids": "", "factor_unit": "",
           "control_state": "factor_includes_source_typical_operation",
           "control_evidence": "no additional removal credited",
           "pm_definition": "not_applicable" if pol not in ("BC", "OC", "PM2.5", "PM10", "TSP", "PM") else "source_definition_not_harmonised",
           "release_boundary": "emitted_native_mass", "structural_sensitivity": "",
           "uncertainty_model": "conditional_parameters", "parameter_drivers": "[]"}
    ds = []
    if sector in ("industry", "ippu", "fugitives", "power"):
        from pkinv.sectors.industry import air_pollutants as ap
        from pkinv.core import air_factors, sulfur
        cls = _classes()[sub]
        m = ap.activity(cls, year, _data("classes"))
        fs = [air_factors.factor(e) for e in row["factor_basis"].split(": ", 1)[1].split(";")]
        share_u = float(cls["share_uncert_pct"] or 0)
        base_u = math.sqrt(max(0.0, m["uncert_pct"] ** 2 - share_u ** 2))
        identity = ("activity:coal:" + cls["activity_function"].split(":", 1)[1]
                    if cls["activity_function"].startswith("industry.coal_kt:")
                    else "activity:" + cls["activity_function"])
        ds.append(driver(identity, base_u, "activity"))
        for f in fs:
            if f["activity_basis"] == "sulfur_balance":
                s = sulfur.evidence(cls["sulfur_evidence_id"], year, sub)
                # A specification/regime range is a structural sensitivity. The
                # conditional calculation holds it fixed rather than laundering
                # its endpoints into a probabilistic 95% distribution.
                if s["basis"] == "measured_avg":
                    ds.append(driver("sulfur:" + s["fuel_pool"], s["uncert_pct"],
                                     evidence="declared transfer uncertainty; three batches, not a national sampling distribution"))
                else:
                    out["structural_sensitivity"] = "sulfur:%s:[%s,%s] pct; conditional sulfur held at %s" % (s["fuel_pool"], s["s_pct_lo"], s["s_pct_hi"], s["s_pct_central"])
                r = float(cls["sulfur_retention_frac"] or 0)
                ru = float(cls["sulfur_retention_uncert_pct"] or 0)
                if r and ru:
                    ds.append(fraction_driver("retention:" + sub, r, ru, complement=True,
                                              evidence="bounded retention assumption; control operation not measured"))
                continue
            if f["activity_basis"] == "pm25_share":
                ds.append(fraction_driver("factor:" + f["ef_id"], float(f["value"]) / 100,
                                          air_factors.uncert_pct(f), evidence=f["uncert_basis"]))
            else:
                ds.append(driver("factor:" + f["ef_id"], air_factors.uncert_pct(f),
                                 evidence=f["uncert_basis"] or "AP-42 rating mapped to declared conditional half-width"))
        out.update(source_id=cls["physical_source_id"], source_class_id=sub,
                   calculation_module="pkinv.sectors.industry.air_pollutants",
                   maturity="provisional_estimate", activity_value=m["value"], activity_unit=m["unit"],
                   activity_provenance=cls["activity_function"],
                   factor_ids=";".join(f["ef_id"] for f in fs),
                   factor_unit=";".join(sorted({f["unit_original"] for f in fs})),
                   control_state=cls["control_state"], control_evidence=cls["control_basis"],
                   pm_definition=";".join(sorted({f["pm_basis"] for f in fs if f["pm_basis"] != "na"})) or out["pm_definition"])
        if share_u:
            out["structural_sensitivity"] += "; equipment/fleet partition held conditional; alternative shares are structural and must sum to one"
        if cls["activity_function"].startswith("fugitives.activity:"):
            ds = [entry for entry in ds if entry["kind"] != "activity"]
            if any(air_factors.kg_per_unit(f)[1] == "t_product" for f in fs):
                ds.append(driver("conversion:fugitives:oil_density", ap.OIL_DENSITY_UNCERT_PCT, "conversion"))
            out["uncertainty_model"] = "shared_fugitive_activity"
        if (cls["activity_function"].startswith("industry.gas_TJ:")
                or cls["activity_function"] == "power.captive_gas_TJ"):
            out["uncertainty_model"] = "shared_net_gas_combustion"
            out["release_boundary"] = "gas_combustion_net_of_shared_post_meter_leakage"
        if cls["activity_function"] == "industry.coal_kt:brick_kilns":
            out["structural_sensitivity"] += "; official residual coal allocation versus dated fleet operating cases"
        if cls["product_ratio_uncert_pct"]:
            ds.append(driver("conversion:" + sub + ":product_per_activity", cls["product_ratio_uncert_pct"], "conversion"))
        if pol == "SO2":
            out["structural_sensitivity"] += "; " + so2_sulfur_boundary(cls, year, fs)
        out["structural_sensitivity"] = out["structural_sensitivity"].lstrip("; ")
    elif sector == "agriculture":
        from pkinv.sectors.agriculture import air_pollutants as ap, fertiliser_mix, manure, residue_burning, soils
        d = _agriculture(year, row.get("nitrogen_method", "tan"))
        _, pools = manure.compute(d)
        suffix = re.search(r"\(([^()]*)\)$", sub)
        item = suffix.group(1) if suffix else ""
        if sub.startswith("Residue burning"):
            q = residue_burning.mass_burnt_by_crop(d)[item]
            ef_item = dict(ap.BURN_POLL)[pol]
            ds = [driver("activity:crop:" + item, d.crops[item]["uncert_pct"], "activity"),
                  _ef(d, "burning", "combustion_factor"), _ef(d, "burning", ef_item)]
            out.update(activity_value=q, activity_unit="t_dry_residue", activity_provenance="crop production x residue ratio x burned fraction",
                       factor_ids="burning:combustion_factor;burning:" + ef_item, factor_unit="g/kg_dry_matter", pm_definition="compilation biomass-burning particulate; no condensable harmonisation")
            out["structural_sensitivity"] = "residue ratios and burned shares held; no annual observed burn-fraction series"
            out["source_id"] = out["source_class_id"] = "agriculture:field_burning:" + item
        elif sub.startswith("NH3 - synthetic"):
            shares, _ = fertiliser_mix.national_shares(d)
            q = d.fertilizer["nitrogen_N_offtake"]["value_t"] * shares[item]
            ds = [driver("activity:agriculture:nitrogen_offtake", d.fertilizer["nitrogen_N_offtake"]["uncert_pct"], "activity"),
                  driver("factor:fert_nh3_highpH:shared_table", d.efu("fert_nh3_highpH", item))]
            out.update(activity_value=q, activity_unit="t_N_offtake", activity_provenance="fiscal N offtake x NFDC product share; offtake is not application",
                       factor_ids="fert_nh3_highpH:" + item, factor_unit="kg_NH3-N/kg_N; 17/14 conversion")
            out["source_id"] = out["source_class_id"] = "agriculture:fertiliser:" + item
            out["nitrogen_recipe"] = json.dumps({"pool": "synthetic_NH3:" + item}, sort_keys=True)
            out["uncertainty_model"] = "shared_nitrogen_ledger"
        elif pol == "NH3" and item:
            sp = item.replace(" ", "_")
            stage = ("application" if "applied to soils" in sub else "grazing_cattle_type" if "cattle-type" in sub else "grazing_other" if "pasture" in sub else
                     "housing" if "housing" in sub else "storage" if "storage" in sub else "yard")
            q = pools["nex_by_species"][sp]
            herd = manure.MMS_KEY.get(sp, sp)
            ds = [driver("activity:livestock:" + herd, d.livestock[herd]["uncert_pct"], "activity")]
            stages = {"tan", "grazing"} if stage.startswith("grazing") else {"tan", "housing", "yard", "storage", "application"}
            ds.extend(_ef(d, "nh3_emep_" + name, sp) for name in sorted(stages))
            out.update(activity_value=q, activity_unit="kg_excreted_N", activity_provenance="shared manure nitrogen ledger: " + getattr(d, "nitrogen_method", "tan"),
                       factor_ids="nh3_emep_tan:%s;nh3_emep_%s:%s" % (sp, "grazing" if stage.startswith("grazing") else stage, sp),
                       factor_unit="kg_NH3-N/kg_surviving_TAN; 17/14 conversion",
                       uncertainty_model="shared_nitrogen_ledger")
            out["nitrogen_recipe"] = json.dumps({"species": sp, "stage": stage}, sort_keys=True)
            out["source_id"] = out["source_class_id"] = "agriculture:livestock:%s:%s" % (sp, stage)
        else:
            # Soil NOx: shared applied pools and one factor; zero residual NH3
            # remains an explicitly calculated zero, not a missing category.
            q = (d.fertilizer["nitrogen_N_offtake"]["value_t"] * 1000 if "synthetic" in sub else
                 soils.residue_N(d) if "crop residues" in sub else pools["FON_N"])
            ds = [driver("activity:agriculture:" + ("nitrogen_offtake" if "synthetic" in sub else "manure_applied" if "organic" in sub else "crop_residue_N"), 20, "activity")]
            if pol == "NOx":
                ds.append(_ef(d, "soils", "NOx_frac_of_applied"))
            out.update(activity_value=q, activity_unit="kg_N", activity_provenance="shared nitrogen ledger", factor_ids="soils:NOx_frac_of_applied" if pol == "NOx" else "crop_residue_nh3:slope",
                       factor_unit="kg_NOx-N/kg_N; 46/14 conversion" if pol == "NOx" else "g_NH3/kg_dry_residue")
            if pol == "NOx" and ("organic manure" in sub or sub.startswith("NOx -")):
                pool = ("field_volat_NOx_N:organic" if "organic manure" in sub else
                        "managed_NOx_N" if "management" in sub else
                        "field_volat_NOx_N:" + sub.split("NOx - ", 1)[1])
                out["nitrogen_recipe"] = json.dumps({"pool": pool}, sort_keys=True)
                out["uncertainty_model"] = "shared_nitrogen_ledger"
            elif pol == "NOx" and "synthetic fertiliser" in sub:
                ds = [driver("activity:agriculture:nitrogen_offtake", d.fertilizer["nitrogen_N_offtake"]["uncert_pct"], "activity"),
                      fraction_driver("factor:soils:NOx_frac_of_applied", d.efv("soils", "NOx_frac_of_applied"), d.efu("soils", "NOx_frac_of_applied"))]
                out["nitrogen_recipe"] = json.dumps({"pool": "soil_NOx:synthetic"}, sort_keys=True)
                out["uncertainty_model"] = "shared_nitrogen_ledger"
            elif pol == "NOx" and "crop residues" in sub:
                ds = [driver("activity:crop:" + crop, value["uncert_pct"], "activity") for crop, value in sorted(d.crops.items())]
                ds.append(fraction_driver("factor:soils:NOx_frac_of_applied", d.efv("soils", "NOx_frac_of_applied"), d.efu("soils", "NOx_frac_of_applied")))
                out["nitrogen_recipe"] = json.dumps({"pool": "soil_NOx:crop_residues"}, sort_keys=True)
                out["uncertainty_model"] = "shared_nitrogen_ledger"
            elif pol == "NH3" and "crop residues left in field" in sub:
                _central, detail = ap.crop_residue_nh3(d)
                out.update(activity_value=sum(r["residue_left_t_DM"] for r in detail),
                           activity_unit="t_dry_above_ground_residue_left_in_field",
                           activity_provenance="crop-specific production x residue ratio x returned fraction; threshold equation",
                           factor_ids="crop_residue_nh3:slope;crop_residue_nh3:intercept;crop_residue_nh3:N_threshold",
                           factor_unit="source threshold equation producing g_NH3/kg_dry_residue",
                           structural_sensitivity="crop residue N contents, threshold, intercept and return fractions held")
                ds = [driver("activity:crop:" + crop, value["uncert_pct"], "activity") for crop, value in sorted(d.crops.items())]
                ds.append(_ef(d, "crop_residue_nh3", "slope"))
                out["nitrogen_recipe"] = json.dumps({"pool": "crop_residue_NH3"}, sort_keys=True)
                out["uncertainty_model"] = "shared_nitrogen_ledger"
    elif sector == "residential":
        from pkinv.sectors.residential import air_pollutants as ap, combustion
        d = _data(sector)
        stream = fuel
        bio = next((s for s in ap.STREAMS if s[0] == stream), None)
        if bio:
            _stream, suffix, mass, ad, _anchor, _polls = bio
            p = "PM25" if pol == "PM2.5" else pol
            item = "Gef_%s_%s" % (p, suffix)
            q = mass(d, None, None, row.get("dung_basis"))
            ds = [driver("activity:residential:" + stream, d.p("activity_uncert_" + ad), "activity"), _ef(d, "residential_biofuel", item)]
            out.update(activity_value=q, activity_unit="kg_dry_fuel_including_ash", factor_ids="residential_biofuel:" + item, factor_unit="g/kg_dry_fuel_including_ash")
        else:
            s = next(s for s in ap.FOSSIL_STREAMS if s[0] == stream)
            _stream, suffix, ad, _anchor, bc, _polls = s
            p = "PM25" if pol in ("PM2.5", "BC") else pol
            item = "Gef_%s_%s" % (p, suffix)
            ds = [driver("activity:residential:" + stream, d.p("activity_uncert_" + ad), "activity"), _ef(d, "residential_air_fossil", item)]
            if pol == "BC":
                ds.append(_ef(d, "residential_air_fossil_frac", bc))
            out.update(activity_value=combustion.fuel_TJ(d)[stream], activity_unit="TJ_ncv", factor_ids="residential_air_fossil:" + item, factor_unit="g/GJ_ncv")
        out.update(activity_provenance="household fuel reconstruction; scale by own-year fuel ratio", release_boundary="gross_appliance_emission; outdoor_escape_fraction_not_estimated", pm_definition="Andreae dry-fuel particulate" if bio else "EMEP filterable/condensable definition unresolved")
        if stream == "Dung cake" and row.get("dung_basis") == "ledger":
            ds = [entry for entry in ds if entry["kind"] != "activity"]
            out["uncertainty_model"] = "shared_diverted_dung_flow"
        out["source_id"] = out["source_class_id"] = "residential:" + stream
    elif sector == "transport":
        from pkinv.sectors.transport import air_pollutants as ap, road
        d = _data(sector)
        cls = row["ei_class"]
        cat, efuel, proxy = ap.class_map()[(cls, fuel)]
        fuels, counts, distance = _transport_inputs(year)
        if process == "exhaust":
            q = fuels[(cls, fuel)]
            unit = "kt_fuel"
            identity = "activity:transport:" + fuel
            ef_id = "EMEP_road:%s:%s:%s" % (cat, efuel, pol)
        elif process == "evaporative":
            q = counts[(cls, fuel)]
            unit, identity = "active_vehicles", "activity:transport:fleet:" + cls
            ef_id = "EMEP_evaporation:" + cat
        else:
            q = distance[(cls, fuel)]
            unit, identity = "vehicle_km", "activity:transport:vkt:" + cls
            ef_id = "EMEP_wear:%s:%s:%s" % (process, cat, pol)
        ds = [driver(identity, road.activity_uncert(d), "activity")]
        out.update(activity_value=q, activity_unit=unit, activity_provenance="OCAC fuel control with reconstructed class composition" if process == "exhaust" else "survival-weighted registration fleet, own or earlier supported year",
                   factor_ids=ef_id, factor_unit="g/kg_fuel" if process == "exhaust" else "g/vehicle/day" if process == "evaporative" else "g/vehicle_km",
                   structural_sensitivity="EMEP technology endpoints and class/fuel proxies; held fixed in conditional interval" + ("; " + proxy if proxy else ""),
                   pm_definition="exhaust PM=PM2.5" if process == "exhaust" else "wear particulate; resuspended dust excluded")
        if pol == "SO2":
            out["factor_ids"] = "sulfur:pk_road_" + fuel.lower() + "_pool"
            out["factor_unit"] = "kg_SO2/kg_S"
            c, lo, hi = ap.sulfur_ppm(year)[fuel]
            out["structural_sensitivity"] = (
                "fuel specification cases, not measured compliance or 95%% limits; central %g ppm "
                "S is a DECLARED fuel-regime case keyed to policy/specification dates, not a pump "
                "or refinery assay; regime band %g-%g ppm" % (c, lo, hi))
        out["source_id"] = out["source_class_id"] = "transport:%s:%s:%s" % (cls, fuel, process)
    elif sector == "waste":
        from pkinv.sectors.waste import air_pollutants as ap, open_burning
        d = _data(sector)
        ef_item = dict(ap.POLLUTANTS)[pol]
        # Shared bounded waste-fate replay supplies burned dry tonnes. Sampling
        # activity multipliers again here would count the same uncertainty twice.
        ds = [_ef(d, "waste_burning", ef_item)]
        out.update(activity_value=open_burning.waste_burnt(d, year) * d.p("dry_matter"), activity_unit="t_dry_waste", activity_provenance="population x generation x uncollected x burned fraction x dry matter", factor_ids="waste_burning:" + ef_item, factor_unit="g/kg_dry_waste", release_boundary="open_burning; geography_at_origin_not_observed_fire_locations")
        out["source_id"] = out["source_class_id"] = "waste:open_burning"
        out["uncertainty_model"] = "shared_waste_flow"
    elif sector == "railways":
        from pkinv.sectors.railways import air_pollutants as ap, traction
        d = _data(sector)
        fraction = traction.locomotive_fraction(d, fuel, year)
        if row["category"] != ap.CATEGORY:
            fraction = 1.0 - fraction
        q = ap.fuel_tonnes(d, year)[fuel] * fraction
        activity_u = next(u for stream, _item, _density, u in traction.FUELS if stream == fuel)
        ds = [driver("activity:railways:" + fuel, d.p("activity_uncert_" + activity_u), "activity")]
        ef_item = "PM2.5" if pol == "BC" else pol
        if pol != "SO2":
            ds.append(_ef(d, "railway_air", ef_item))
            if pol == "BC":
                ds.append(_ef(d, "railway_air_frac", "BC_of_PM2.5"))
        else:
            out["structural_sensitivity"] = "operator sulfur unmeasured; explicit sulfur specification cases"
        out.update(activity_value=q, activity_unit="t_fuel", activity_provenance="operator fuel: traction/non-traction partition", factor_ids="railway_air:" + ef_item, factor_unit="kg/t_fuel")
        out["source_id"] = out["source_class_id"] = "railways:%s:%s" % (row["category"], fuel)
    elif sector == "aviation":
        from pkinv.sectors.aviation import lto
        d = _data(sector)
        ds = [driver("activity:aviation:domestic", lto.activity_uncert(d), "activity")]
        if pol in ("NOx", "CO", "HC"):
            q, unit = lto.lto_cycles(d, year - 1)["domestic"], "LTO_cycles"
            ds.append(driver("factor:aviation:representative_engine:" + pol, 60 if pol == "HC" else 40))
        else:
            q, unit = lto.fuel_tonnes(d, year - 1)["domestic"], "t_fuel"
            ds.append(_ef(d, "aviation_fuel_ef", "PM2.5" if pol == "BC" else pol))
            if pol == "BC":
                ds.append(_ef(d, "aviation_fuel_ef", "BC_fraction"))
        out.update(activity_value=q, activity_unit=unit, activity_provenance="domestic movements/fuel; representative engines and LTO-cruise split", factor_ids=row.get("method", ""), factor_unit="kg/LTO" if unit == "LTO_cycles" else "kg/t_fuel", maturity="provisional_estimate")
        out["source_id"] = out["source_class_id"] = "aviation:" + row["ghg_subitem"]
    else:
        raise KeyError(sector)
    out["source_class_id"] = out.get("source_class_id", "%s:%s" % (sector, sub or fuel))
    out["parameter_drivers"] = json.dumps(ds, sort_keys=True, separators=(",", ":"))
    return out
