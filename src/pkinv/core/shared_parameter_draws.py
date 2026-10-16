"""Deterministic parameter draws shared by material-flow and pollutant engines.

The identity names the physical input, not an output row. Reordering or splitting
an output therefore does not add information or change a realisation. Parameter
distributions are conditional modelling assumptions, not probabilities assigned
to structural cases. Physical fractions use a bounded, mean-preserving beta.
"""
import hashlib
import math
import numpy as np

SEED = 20261014


def rng_for(identity, seed=SEED):
    digest = hashlib.sha256((str(seed) + "|" + identity).encode("utf-8")).digest()
    return np.random.default_rng(int.from_bytes(digest[:16], "big"))


def positive_multiplier(identity, uncertainty_pct, size, seed=SEED):
    """Mean-preserving lognormal using a declared local 95% relative half-width."""
    sigma = math.sqrt(math.log1p((float(uncertainty_pct or 0) / 196.0) ** 2))
    return np.exp(rng_for(identity, seed).standard_normal(size) * sigma - sigma * sigma / 2)


def physical_fraction(identity, mean, uncertainty_pct, size, seed=SEED):
    """Beta on [0,1], matching the local mean/variance where mathematically valid.

    Degenerate endpoints stay endpoints. An impossible mean/variance pair raises
    rather than silently clipping, narrowing an uncertainty, or repairing draws.
    """
    mean = float(mean)
    if not 0 <= mean <= 1:
        raise ValueError("%s fraction mean outside [0,1]" % identity)
    variance = (mean * float(uncertainty_pct or 0) / 196.0) ** 2
    if variance == 0 or mean in (0, 1):
        return np.full(size, mean)
    if variance >= mean * (1 - mean):
        raise ValueError("%s conditional variance is impossible for a physical fraction" % identity)
    concentration = mean * (1 - mean) / variance - 1
    return rng_for(identity, seed).beta(mean * concentration, (1 - mean) * concentration, size)


def parameter_identity(name):
    """Legacy graph names and air records identify the same physical input."""
    if name.startswith("livestock:") or name.startswith("crop:"):
        return "activity:" + name
    if name == "fertiliser:nitrogen_N_offtake":
        return "activity:agriculture:nitrogen_offtake"
    return name


def parameter_kind(name):
    return "activity" if parameter_identity(name).startswith("activity:") else "factor"


class Draws:
    """Common, extendable parameter streams for native GHG and air calculations."""
    def __init__(self, n=10000, dependence="persistent_parameters", seed=SEED):
        if dependence not in ("persistent_parameters", "annual_activity_errors"):
            raise ValueError("unknown conditional dependence case %r" % dependence)
        self.n, self.dependence, self.seed = n, dependence, seed
        self.cache, self.registry = {}, {}

    def identity(self, name, kind, year):
        name = parameter_identity(name)
        return name + (":FY%d" % year if kind == "activity" and self.dependence == "annual_activity_errors" else "")

    def normal(self, name, year):
        identity = self.identity(name, parameter_kind(name), year)
        return rng_for(identity, self.seed).standard_normal(self.n)

    def multiplier(self, entry, year):
        identity = self.identity(entry["id"], entry["kind"], year)
        if entry.get("distribution") == "bounded_beta":
            mean = float(entry["mean"])
            values = self.fraction(identity, mean, entry["uncert_pct"])
            if entry.get("complement"):
                if mean == 1:
                    raise ValueError("zero surviving central fraction for %s" % identity)
                return (1 - values) / (1 - mean)
            if mean == 0:
                raise ValueError("zero central fraction for %s" % identity)
            return values / mean
        key = (identity, float(entry["uncert_pct"]))
        if key not in self.cache:
            self.cache[key] = positive_multiplier(identity, entry["uncert_pct"], self.n, self.seed)
        self.registry[identity] = dict(entry, id=identity, distribution="mean_preserving_lognormal")
        return self.cache[key]

    def fraction(self, name, mean, uncertainty):
        key = (name, float(mean), float(uncertainty))
        if key not in self.cache:
            self.cache[key] = physical_fraction(name, mean, uncertainty, self.n, self.seed)
        self.registry[name] = {"id": name, "kind": "factor", "uncert_pct": uncertainty,
                               "mean": mean, "distribution": "bounded_beta", "evidence": "conditional mean and variance from declared parameter width; not a structural-case probability"}
        return self.cache[key]


def residue_burning_realisations(year, draws):
    """Native burned residue from summed crop flows, shared with air estimates.

    Residue ratios and burned shares stay conditional. Crop production, bounded
    combustion and gas factors use the existing physical-input identities; a sum
    of crop flows is never multiplied by every crop's activity multiplier.
    """
    from pkinv.sectors.agriculture.fiscal_activity import data_for_fiscal_year
    from pkinv.sectors.agriculture import residue_burning
    data = data_for_fiscal_year(year)
    mass = np.zeros(draws.n)
    for crop, tonnes in residue_burning.mass_burnt_by_crop(data).items():
        mass += tonnes * draws.multiplier({"id": "activity:crop:" + crop,
            "kind": "activity", "uncert_pct": data.crops[crop]["uncert_pct"]}, year)
    combustion = draws.fraction("factor:burning:combustion_factor",
        data.efv("burning", "combustion_factor"), data.efu("burning", "combustion_factor"))
    values = {"burned_dry_t": mass, "combusted_dry_t": mass * combustion}
    for gas in ("CH4", "N2O"):
        item = "Gef_" + gas
        factor = data.efv("burning", item) * draws.multiplier({
            "id": "factor:burning:" + item, "kind": "factor",
            "uncert_pct": data.efu("burning", item)}, year)
        values[gas] = values["combusted_dry_t"] * factor / 1e6
    return values


def nitrogen_realisations(year, draws, method="tan"):
    """Conserved native N releases, replayed once for both product families.

    NH3 keys contain Gg NH3, NOx keys Gg NO2-equivalent, and ``ghg:`` keys
    Gg N2O. The same head-count, nitrogen-input and factor realisation reaches
    every output. Management shares and nitrogen excretion rates remain fixed.
    """
    from pkinv.sectors.agriculture import manure
    from pkinv.sectors.agriculture.fiscal_activity import data_for_fiscal_year
    data = data_for_fiscal_year(year)
    data.nitrogen_method = method
    from pkinv.sectors.agriculture import fertiliser_mix
    product_shares, _ = fertiliser_mix.national_shares(data)
    data.nitrogen_product_shares = product_shares
    def activity(identity, uncertainty):
        return draws.multiplier({"id": identity, "kind": "activity", "uncert_pct": uncertainty}, year)
    head = {species: activity("activity:livestock:" + species, value["uncert_pct"])
            for species, value in data.livestock.items()}
    inputs = {"fertiliser": activity("activity:agriculture:nitrogen_offtake",
                                      data.fertilizer["nitrogen_N_offtake"]["uncert_pct"])}
    inputs.update({"crop:" + crop: activity("activity:crop:" + crop, value["uncert_pct"])
                   for crop, value in data.crops.items()})
    parameters = {}
    for (category, item), record in data.ef.items():
        # Only actual N-fate factors, with fixed climate/technology formulation.
        used = (category.startswith("nh3_emep_") if method == "tan" else category == "manure_fracgasms")
        used |= category in ("manure_n2o_ef3", "manure_fracleachms")
        used |= category == "soils" and item in ("EF1_dry", "EF1FR_rice", "EF3PRP_cattle",
                   "EF3PRP_sheepgoat", "EF4_dry", "EF5", "FracGASM", "FracLEACH", "NOx_frac_of_applied")
        if used:
            parameters[(category, item)] = draws.fraction("factor:%s:%s" % (category, item),
                                                          record["value"], record["uncert_pct"])
    for item in product_shares:
        record = data.ef[("fert_nh3_highpH", item)]
        common = draws.multiplier({"id": "factor:fert_nh3_highpH:shared_table", "kind": "factor",
                                    "uncert_pct": record["uncert_pct"]}, year)
        parameters[("fert_nh3_highpH", item)] = record["value"] * common
        if np.any(parameters[("fert_nh3_highpH", item)] > 1):
            raise ValueError("fertiliser factor draw exceeds physical fraction for %s" % item)
    slope = data.ef[("crop_residue_nh3", "slope")]
    parameters[("crop_residue_nh3", "slope")] = slope["value"] * draws.multiplier(
        {"id": "factor:crop_residue_nh3:slope", "kind": "factor", "uncert_pct": slope["uncert_pct"]}, year)
    results, max_closure = {}, 0.0
    for index in range(draws.n):
        ghg, pools = manure.rerun_nitrogen(
            data, {species: values[index] for species, values in head.items()},
            {parameter: values[index] for parameter, values in parameters.items()}, method,
            {key: values[index] for key, values in inputs.items()})
        values = {key: value * 17 / 14 / 1e6 for key, value in pools["stage_nh3_N"].items()}
        values.update({"field_volat_NOx_N:" + key: value * 46 / 14 / 1e6
                       for key, value in pools["field_volat_NOx_N"].items()})
        values["managed_NOx_N"] = pools["managed_NOx_N"] * 46 / 14 / 1e6
        nox = parameters[("soils", "NOx_frac_of_applied")][index]
        values["soil_NOx:synthetic"] = pools["FSN_N"] * nox * 46 / 14 / 1e6
        values["soil_NOx:crop_residues"] = pools["FCR_N"] * nox * 46 / 14 / 1e6
        values["crop_residue_NH3"] = pools["crop_residue_NH3_Gg"]
        applied_n = data.fertilizer["nitrogen_N_offtake"]["value_t"] * 1000 * inputs["fertiliser"][index]
        for item, share in product_shares.items():
            values["synthetic_NH3:" + item] = (applied_n * share * parameters[("fert_nh3_highpH", item)][index]
                                                       * 17 / 14 / 1e6)
        for row in ghg:
            if row["gas"] == "N2O":
                values["ghg:%s|%s|N2O" % (row["category"], row["subitem"])] = row["emissions_Gg"]
        for key, value in values.items():
            results.setdefault(key, np.zeros(draws.n))[index] = value
        residual = abs(pools["managed_N"] - sum(pools[name] for name in
                    ("FON_N", "volat_managed_N", "leach_managed_N", "n2_managed_N", "n2o_managed_N")))
        max_closure = max(max_closure, residual)
    return results, max_closure


def waste_realisations(year, draws):
    """Native waste-fate rerun shared with the air burning activity.

    The established bounded/positive parameter distributions are retained.
    Fixed generation/management parameters persist across years in both
    dependence cases: these are not annually observed management statistics.
    """
    from pkinv.sectors.waste.data import WasteData
    from pkinv.sectors.waste.uncertainty import parameter_rerun_mc
    _rows, _categories, _totals, native = parameter_rerun_mc(
        WasteData(year=year), n_iter=draws.n, seed=draws.seed, return_native=True)
    for name, values in native.items():
        if not name.startswith("parameter:"):
            continue
        identity = "parameter:waste:" + name.split(":", 1)[1]
        draws.cache[(identity, 0.)] = np.asarray(values)
        draws.registry[identity] = dict(id=identity, kind="factor", uncert_pct=0.,
            distribution="native_waste_parameter", evidence="existing bounded/positive waste parameter rerun; raw parameter draws")
    return {key: np.asarray(values) for key, values in native.items()}


def fugitives_realisations(year, draws):
    """Native bounded fugitive draws paired by physical parameter across years."""
    from pkinv.sectors.fugitives.data import FugitivesData
    from pkinv.sectors.fugitives.uncertainty import refinement_analysis, _multiplier_from_u
    _stats, _totals, _sens, native, inputs = refinement_analysis(
        FugitivesData(), n_iter=draws.n, seed=draws.seed, year=year,
        return_native=True, parameter_draws=draws)
    result = {key: np.asarray(values) for key, values in native.items()}
    # The reference GHG transmission factor uses pipeline length. Air transfer
    # classes can instead use reported throughput; it is a separate control,
    # never an alias for that length. Expose admitted activity controls even when
    # a reference GHG factor does not currently consume them.
    data = FugitivesData()
    for (anchor_year, activity_id), row in data.anchors.items():
        if anchor_year != year or "activity:" + activity_id in result:
            continue
        group = data.activity_corr_group(activity_id)
        identity = draws.identity("activity:fugitives:" + group, "activity", year)
        uniform = rng_for(identity, draws.seed).random(draws.n)
        low, high = float(row["uncertainty_low_pct"]), float(row["uncertainty_high_pct"])
        result["activity:" + activity_id] = np.asarray([
            _multiplier_from_u(u, low, high, "bounded_split_triangular") for u in uniform])
        draws.cache[(identity, low, high)] = result["activity:" + activity_id]
        draws.registry[identity] = dict(id=identity, kind="activity", uncert_pct="",
            uncertainty_low_pct=low, uncertainty_high_pct=high,
            distribution="bounded_split_triangular", evidence=row.get("source_reference", row.get("source", "")))
    result["post_meter_factor_multiplier"] = np.asarray([
        _multiplier_from_u(u, 60, 60, "bounded_split_triangular")
        for u in inputs["factor:post_meter_industrial"]])
    for name, values in inputs.items():
        if len(values) != draws.n:
            continue
        identity = "native:fugitives:" + name
        draws.cache[(identity, 0.)] = np.asarray(values)
        draws.registry[identity] = dict(id=identity, kind="factor", uncert_pct=0.,
            distribution="native_fugitives_parameter", evidence="source/group bounded parameter rerun; raw underlying draw")
    return result


def power_coal_realisations(year, draws):
    """Rank heat and carbon content share their actual physical realisation."""
    from pkinv.sectors.power.data import PowerData
    data = PowerData()
    start = year - 1
    mass = draws.multiplier({"id": "activity:coal:power_station_mass", "kind": "activity",
                              "uncert_pct": data.p("activity_uncert_coal")}, year)
    heat = np.zeros(draws.n)
    co2 = np.zeros(draws.n)
    for row in data.coal_rank_account[start]:
        rank = row["fuel_rank"]
        multiplier = draws.multiplier({"id": "factor:ncv:" + rank, "kind": "factor",
                                       "uncert_pct": float(row["ncv_uncert_pct_95"])}, year)
        energy = float(row["energy_TJ"]) * mass * multiplier
        heat += energy
        factor = draws.multiplier({"id": "factor:co2:" + rank, "kind": "factor",
                                    "uncert_pct": data.efu("power_combustion_co2", rank)}, year)
        co2 += energy * data.efv("power_combustion_co2", rank) * factor / 1e6
    result = {"CO2": co2}
    for gas in ("CH4", "N2O"):
        category = "power_combustion_" + gas.lower()
        factor = draws.multiplier({"id": "factor:%s:Other Bituminous Coal" % gas.lower(),
                                    "kind": "factor", "uncert_pct": data.efu(category, "Coal")}, year)
        result[gas] = heat * data.efv(category, "Coal") * factor / 1e6
    return result


def dung_mass_multiplier(year, draws):
    """Ledger-L dung follows the same sampled herd, with VS/fate shares fixed."""
    from pkinv.sectors.agriculture.fiscal_activity import data_for_fiscal_year
    from pkinv.sectors.agriculture.manure import MMS_KEY
    from pkinv.sectors.residential.data import ResidentialData
    from pkinv.sectors.residential.combustion import diverted_n_by_species
    agri, residential = data_for_fiscal_year(year), ResidentialData()
    total, values = 0.0, np.zeros(draws.n)
    for species, nitrogen in diverted_n_by_species(agri).items():
        herd = MMS_KEY.get(species, species)
        ratio = residential.p("vs_rate_" + species) / agri.p("nex_rate_" + species)
        central = nitrogen * ratio
        multiplier = draws.multiplier({"id": "activity:livestock:" + herd, "kind": "activity",
                                       "uncert_pct": agri.livestock[herd]["uncert_pct"]}, year)
        values += central * multiplier
        total += central
    if total <= 0:
        raise ValueError("no diverted dung material for ledger configuration")
    return values / total
