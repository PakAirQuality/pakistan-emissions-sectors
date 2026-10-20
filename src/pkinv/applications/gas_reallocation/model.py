"""One case of the gas reallocation, computed on paired parameter draws.

THE SUBSYSTEM. Only the processes the reallocation touches are computed: the two urea plants, the
stations that receive the gas, the generation it displaces, the post-meter leak base, the imported
urea and the upstream chains of the fuels that change. Everything else in the inventory is the
same in both states and cancels from the difference exactly. A state is the subsystem at a
reallocated fraction s' of the plants' gas, with BOTH services held at the case's level:
  urea:        domestic urea x (1 - s') + imported urea x s'            (same tonnage applied)
  electricity: receiving-station GWh(s') + displaced-station GWh(s_case) - GWh(s')  (same GWh)
The baseline is s' = 0 and the transition is s' = s_case. The change is transition minus baseline,
taken draw by draw from one set of draws, so a parameter both states use (the heating value of the
gas, the CO2 factor of gas, a station efficiency) cancels where the physics says it should.

UNITS. Every mass is in Gg (kt). CO2e is Gg CO2e on AR5 GWP100, fossil methane (the inventory's
primary basis); AR6 is computed beside it. Air pollutants keep the inventory's conventions: NOx as
NO2, BC inside PM2.5 (never added to it). A pollutant a process emits but no held factor prices is
None (NE). A pollutant a process does not emit is absent from that process (NA). Neither is ever 0.
"""
import math

import numpy as np

from pkinv.core import gwp
from pkinv.core.shared_parameter_draws import SEED, positive_multiplier, rng_for
from pkinv.core.units import TJ_PER_MMBTU
from pkinv.sectors.fugitives import post_meter
from pkinv.sectors.ippu.ammonia_reconciliation import UREA_CO2_RECOVERY as UREA_CO2   # 44/60, Eq 3.10

from . import inputs

POLLUTANTS = ("CO2", "CH4", "N2O", "NOx", "SO2", "PM2.5", "BC", "CO", "NMVOC", "NH3")
GHGS = ("CO2", "CH4", "N2O")
SCF_PER_T_PER_MMCF_PER_KT = 1000.0  # 1 MMCF per kt = 1,000 scf per t

# Sector keys of the decomposition: (key, label, boundary, inventory status of the process).
SECTORS = (
    ("2B1", "2.B.1 Ammonia production: CO2 net of urea recovery; process NOx, CO, NH3",
     "territorial", "inventory"),
    ("2B1_fuel", "2.B.1 process-fuel combustion: CH4, N2O and air pollutants",
     "territorial", "application addition (not estimated in the inventory)"),
    ("2B_finish", "2.B urea finishing (prilling): PM2.5 and NH3",
     "territorial", "application addition (not estimated in the inventory)"),
    ("1B2b", "1.B.2.b post-meter gas leakage", "territorial", "inventory convention"),
    ("1A1a_recv", "1.A.1.a receiving gas stations", "territorial", "inventory method"),
    ("1A1a_disp", "1.A.1.a displaced generation", "territorial", "inventory method"),
    ("3C_urea", "3.C urea application and soils (same urea, same fields)", "territorial",
     "inventory; unchanged by construction"),
    ("X_urea", "External: imported urea production (exporter 2.B.1 net of urea-bound CO2, "
               "plus feedstock upstream)", "external", "application (literature factors)"),
    ("X_fuel", "External: upstream of the displaced furnace oil, coal or LNG", "external",
     "application (literature proxy factors)"),
)
# Which way the activity of each process moves when gas leaves the plants (s' rises). It types
# the direction of a NOT-ESTIMATED component so a classification can say whether the missing part
# could only enlarge the estimated change or could reverse it.
DIRECTION = {"2B1": -1, "2B1_fuel": -1, "2B_finish": -1, "1A1a_recv": +1, "1A1a_disp": -1,
             "X_urea": +1, "X_fuel": -1}


class Draws:
    """Named parameter draws. The same name returns the same array however often it is asked for.

    `tag` separates two otherwise identical sets of streams. It exists for one purpose: the test that
    shows what an UNPAIRED calculation (independent draws per state) would do to the interval.
    """

    def __init__(self, params, factors, n, seed=SEED, tag=""):
        self.params, self.factors, self.n, self.seed, self.tag = params, factors, n, seed, tag
        self._cache = {}

    def _rng(self, identity):
        return rng_for("gas_reallocation|%s%s" % (identity, self.tag), self.seed)

    def get(self, pid, use=""):
        """The draws of parameter `pid`. `use` separates two physical things one table row describes
        (the IPCC gas factor at the exporter and in baseline FA3 are different plants)."""
        key = (pid, use)
        if key in self._cache:
            return self._cache[key]
        p = self.params[pid]
        identity = pid + ("|" + use if use else "")
        dist = p["distribution"]
        if dist == "fixed":
            out = np.full(self.n, p["value"])
        elif dist == "lognormal_pct":
            out = p["value"] * positive_multiplier(
                "gas_reallocation|%s%s" % (identity, self.tag), p["uncert_pct"] or 0, self.n, self.seed)
        elif dist == "triangular":
            mode = p["value"] if p["value"] is not None else self.mode(pid)
            out = self._rng(identity).triangular(p["low"], mode, p["high"], self.n)
        elif dist == "uniform":
            out = self._rng(identity).uniform(p["low"], p["high"], self.n)
        elif dist == "loguniform":
            out = np.exp(self._rng(identity).uniform(math.log(p["low"]), math.log(p["high"]), self.n))
        else:
            raise ValueError("%s: unknown distribution %r" % (pid, dist))
        self._cache[key] = out
        return out

    def mode(self, pid):
        if pid == "hhv_network_btu_scf":
            return hhv_mode(self.params)
        raise ValueError("%s has no value and no derivation" % pid)

    def air(self, factor_set, pollutant):
        """g/GJ (or BC % of PM2.5 as a fraction) draws, or None where the source prints no factor."""
        entry = self.factors[factor_set].get(pollutant)
        if entry is None or "value" not in entry:
            return None
        key = ("air", factor_set, pollutant)
        if key not in self._cache:
            draw = self._rng("air|%s|%s" % (factor_set, pollutant)).triangular(
                entry["low"], entry["value"], entry["high"], self.n)
            self._cache[key] = draw / 100.0 if entry["unit"].startswith("%") else draw
        return self._cache[key]

    def register(self, ef_id):
        """A factor of the inventory's air register, on its declared uncertainty."""
        key = ("register", ef_id)
        if key not in self._cache:
            value, pct = inputs.air_register(ef_id)
            self._cache[key] = value * positive_multiplier(
                "gas_reallocation|register|%s%s" % (ef_id, self.tag), pct, self.n, self.seed)
        return self._cache[key]

    def position(self, identity):
        """A uniform [0, 1) stream: which station of a pathway the gas meets, shared across readings."""
        key = ("position", identity)
        if key not in self._cache:
            self._cache[key] = self._rng("position|" + identity).uniform(0.0, 1.0, self.n)
        return self._cache[key]


def hhv_mode(params, year=inputs.REFERENCE_YEAR):
    """The heating value one plant's own records imply: energy index / gas per tonne (Btu per scf).

    Fatimafert's calendar-year energy indices (company annual reports) averaged over the two calendar
    years FY2023-24 spans, divided by its NFDC-metered FY2023-24 gas per tonne of NFDC urea.
    """
    gas = inputs.plant_gas(year)["Fatimafert"]
    urea = inputs.plant_urea(year)["Fatimafert"]
    index = 0.5 * (params["fatimafert_energy_index_cy2023"]["value"]
                   + params["fatimafert_energy_index_cy2024"]["value"])
    scf_per_t = (gas["feed"] + gas["fuel"]) / urea * SCF_PER_T_PER_MMCF_PER_KT
    return index * 1e6 / scf_per_t


def _triangular_at(u, values, weights=None):
    """Inverse-CDF triangular on (min, weighted mean, max) of station values, at uniform positions u."""
    values = [float(v) for v in values]
    lo, hi = min(values), max(values)
    if weights is None:
        weights = [1.0] * len(values)
    mode = sum(v * w for v, w in zip(values, weights)) / sum(weights)
    if hi - lo < 1e-12:
        return np.full(len(u), lo)
    c = (mode - lo) / (hi - lo)
    return np.where(u < c, lo + np.sqrt(u * (hi - lo) * (mode - lo)),
                    hi - np.sqrt((1 - u) * (hi - lo) * (hi - mode)))


class Records:
    """Everything the model reads, loaded once."""

    def __init__(self, year=inputs.REFERENCE_YEAR):
        self.year = year
        self.params = inputs.parameters()
        self.factors = inputs.air_factors()
        self.gas = inputs.plant_gas(year)
        self.urea = inputs.plant_urea(year)
        self.stations = {p: inputs.station_records(p, year)
                         for p in ("R1", "R2", "R3", "D1", "D2", "D3")}
        self.leak_share = post_meter.whole_gas_leak_share()
        self.gas_density = post_meter.param_value("gas_density_kg_per_m3")
        self.ch4_fraction = post_meter.param_value("gas_ch4_fraction")
        self.grid_average = inputs.fossil_grid_average(year)[0]

    @property
    def feed(self):
        return sum(g["feed"] for g in self.gas.values())

    @property
    def fuel(self):
        return sum(g["fuel"] for g in self.gas.values())

    @property
    def urea_kt(self):
        return sum(self.urea.values())

    def gwh_capacity(self, pathway):
        """Annual GWh the pathway's stations generated in the year: the most a displaced pathway can
        give up. Receiving pathways: nameplate hours minus that year's generation (an upper bound)."""
        printed = sum(leg["gwh"] for s in self.stations[pathway] for leg in s["legs"])
        if pathway.startswith("D"):
            return printed
        mw = inputs.station_capacity_mw(pathway)
        return mw * 8760.0 / 1e3 - printed


def receiving_gwh(d, rec, pathway, reading, mmbtu, mmcf, hhv, g2n):
    """GWh the receiving pathway generates from `mmbtu` (gross) of the plants' gas.

    PA1 (ledger): the stations' printed GWh per printed MMBTU, the MMBTU read as gross; a station whose
    fuel is printed in MMCFT converts by volume (GWh per MMCF), so no heating value enters it.
    PA2 (printed heat rate): gas energy on NCV times the SoIR net efficiency.
    The same position draw picks the station in both readings, so PA1 and PA2 are paired.
    """
    u = d.position(pathway)
    stations = rec.stations[pathway]
    if reading == "PA1":
        per_mmbtu, weights = [], []
        for s in stations:
            for leg in s["legs"]:
                if leg["unit"] == "MMBTU":
                    per_mmbtu.append(("mmbtu", leg["gwh"] / leg["quantity"]))
                elif leg["unit"] == "MMCFT":
                    per_mmbtu.append(("mmcf", leg["gwh"] / leg["quantity"]))
                else:
                    continue
                weights.append(leg["gwh"])
        if not per_mmbtu:
            raise ValueError("%s: no ledger fuel to convert with" % pathway)
        if all(kind == "mmcf" for kind, _v in per_mmbtu):
            return mmcf * _triangular_at(u, [v for _k, v in per_mmbtu], weights)
        if any(kind == "mmcf" for kind, _v in per_mmbtu):
            raise ValueError("%s mixes MMBTU and MMCFT stations" % pathway)
        return mmbtu * _triangular_at(u, [v for _k, v in per_mmbtu], weights)
    if reading == "PA2":
        effs = [e for s in stations for e in s["eff_net"]]
        if not effs:
            raise ValueError("%s: no printed heat rate" % pathway)
        eta = _triangular_at(u, effs)
        return mmbtu * g2n * TJ_PER_MMBTU * eta / 3.6
    raise ValueError("unknown power reading %r" % reading)


def displaced_fuel(d, rec, pathway, reading, gwh):
    """(TJ NCV, fuel mass Gg or None) the displaced pathway burns to make `gwh`.

    Furnace oil, PA1: the stations' printed fuel mass per printed GWh (measured specific consumption);
    energy is that mass at the inventory NCV. PA2: the printed net efficiency, mass back from the NCV.
    Imported coal: the station coal heating value is unresolved in the inventory, so both readings use
    the printed efficiency and no mass is formed.
    """
    u = d.position(pathway)
    stations = rec.stations[pathway]
    if pathway in ("D1", "D2"):
        ncv = d.get("ncv_rfo")
        if reading == "PA1":
            spec = [leg["quantity"] / leg["gwh"] for s in stations for leg in s["legs"] if leg["gwh"] > 0]
            weights = [leg["gwh"] for s in stations for leg in s["legs"] if leg["gwh"] > 0]
            mass = gwh * _triangular_at(u, spec, weights)
            return mass * ncv, mass
        effs = [e for s in stations for e in s["eff_net"]]
        tj = gwh * 3.6 / _triangular_at(u, effs)
        return tj, tj / ncv
    if pathway == "D3":
        effs = [e for s in stations for e in s["eff_net"]]
        return gwh * 3.6 / _triangular_at(u, effs), None
    raise ValueError(pathway)


def _combustion(d, tj, fuel, factor_set, combusted=1.0, mass=None):
    """GHG and air pollutants (Gg) of `tj` (NCV) of one fuel at one equipment class."""
    burnt = tj * combusted
    ef = {"gas_power": ("ef_co2_gas", "ef_ch4_gas_power", "ef_n2o_gas_power"),
          "gas_industry": ("ef_co2_gas", "ef_ch4_gas_industry", "ef_n2o_gas_industry"),
          "rfo": ("ef_co2_rfo", "ef_ch4_oil", "ef_n2o_oil"),
          "coal": ("ef_co2_coal", "ef_ch4_coal", "ef_n2o_coal")}[fuel]
    out = {"CO2": burnt * d.get(ef[0]) / 1e6, "CH4": burnt * d.get(ef[1]) / 1e6,
           "N2O": burnt * d.get(ef[2]) / 1e6}
    for pol in ("NOx", "CO", "NMVOC", "PM2.5", "NH3"):
        f = d.air(factor_set, pol)
        out[pol] = None if f is None else burnt * f * 1e-6
    so2 = d.factors[factor_set].get("SO2") or {}
    method = so2.get("so2_method")
    if method == "sulfur_balance":
        out["SO2"] = mass * d.get("rfo_sulfur_pct") / 100.0 * 2.0       # 64/32: S to SO2
    elif method == "factor_times_fgd":
        out["SO2"] = burnt * d.air(factor_set, "SO2") * 1e-6 * (1.0 - d.get("coal_fgd_removal"))
    else:
        f = d.air(factor_set, "SO2")
        out["SO2"] = None if f is None else burnt * f * 1e-6
    bc = d.air(factor_set, "BC")
    out["BC"] = None if (bc is None or out["PM2.5"] is None) else out["PM2.5"] * bc
    return out


def import_factor(d, route):
    """t CO2e per t of imported urea at the exporter (2.B.1 net of urea-bound CO2, plus upstream)."""
    nh3 = d.get("nh3_per_urea")
    if route == "F1":
        process = nh3 * d.get("ammonia_ef_ipcc_gas", use="exporter")
        upstream = nh3 * d.get("ammonia_fuel_req_gas", use="exporter") * d.get("wtt_natural_gas") / 1e3
    elif route == "F2":
        coal_gj = d.get("h2_per_nh3") * d.get("h2_frf_coal")
        process = nh3 * coal_gj * d.get("h2_ccf_coal") * 44.0 / 12.0
        upstream = nh3 * coal_gj * d.get("wtt_coal") / 1e3
    else:
        raise ValueError(route)
    return process - UREA_CO2 + upstream


def state(d, rec, case, s_case, s):
    """The subsystem's emissions at reallocated fraction `s` of a case whose services are fixed at
    `s_case`. Returns {sector: {pollutant: Gg array or None}} plus a `flows` entry."""
    fa, pa, receiving, displaced, route = case
    if not 0.0 <= s <= s_case <= 1.0:
        raise ValueError("reallocated fraction %r of %r is outside the plants' gas (0 <= s <= s_case <= 1)"
                         % (s, s_case))
    h, g2n, ls = d.get("hhv_network_btu_scf"), d.get("gross_to_net"), rec.leak_share
    out = {k: {} for k, *_ in SECTORS}
    total_mmcf = rec.feed + rec.fuel

    # The plants at (1 - s): urea, its ammonia and the gas behind it.
    urea_dom = rec.urea_kt * (1 - s)
    nh3 = urea_dom * d.get("nh3_per_urea")
    feed_tj = rec.feed * (1 - s) * h * TJ_PER_MMBTU * g2n
    fuel_tj = rec.fuel * (1 - s) * h * TJ_PER_MMBTU * g2n
    if fa == "FA1":
        co2 = nh3 * d.get("ammonia_ef_calibrated") - urea_dom * UREA_CO2
    elif fa == "FA2":
        co2 = (feed_tj + fuel_tj * (1 - ls)) * d.get("ef_co2_gas") / 1e6 - urea_dom * UREA_CO2
    elif fa == "FA3":
        co2 = nh3 * d.get("ammonia_ef_ipcc_gas", use="baseline") - urea_dom * UREA_CO2
    elif fa == "FD1":
        co2 = None
    else:
        raise ValueError(fa)
    out["2B1"] = {"CO2": co2, "NOx": nh3 * d.register("emep_2b1_t1_nox") / 1e3,
                  "CO": nh3 * d.register("emep_2b1_t1_co") / 1e3,
                  "NH3": nh3 * d.register("emep_2b1_t1_nh3") / 1e3,
                  "SO2": None, "PM2.5": None, "NMVOC": None}
    fuel = _combustion(d, fuel_tj, "gas_industry", "process_gas", combusted=1 - ls)
    fuel.pop("CO2")          # the process fuel's CO2 is inside 2.B.1 under every reading
    out["2B1_fuel"] = fuel
    out["2B_finish"] = {
        "PM2.5": urea_dom * d.get("urea_prill_pm_kg_t") * d.get("urea_prill_pm25_fraction") / 1e3,
        "BC": None,
        "NH3": urea_dom * (d.get("urea_solution_nh3_kg_t") + d.get("urea_prill_nh3_kg_t")) / 1e3}

    # Gas to power and the GWh it makes (none under D4: the gas replaces RLNG, it adds no generation).
    moved = total_mmcf * s
    if receiving == "none":
        gwh_recv = 0.0 * h
        recv_mmbtu_full = 0.0 * h
        out["1A1a_recv"] = {p: 0.0 * h for p in GHGS}
    else:
        gwh_recv = receiving_gwh(d, rec, receiving, pa, moved * h, moved, h, g2n)
        recv_tj = moved * h * TJ_PER_MMBTU * g2n
        out["1A1a_recv"] = _combustion(d, recv_tj, "gas_power", "gas_turbine", combusted=1 - ls)
        recv_mmbtu_full = total_mmcf * s_case * h
    gwh_service = (0.0 * h if receiving == "none" else
                   receiving_gwh(d, rec, receiving, pa, recv_mmbtu_full, total_mmcf * s_case, h, g2n))

    # The displaced generation still running in this state: the case's GWh minus what gas now makes.
    gwh_disp = gwh_service - gwh_recv
    if displaced in ("D1", "D2", "D3"):
        tj, mass = displaced_fuel(d, rec, displaced, pa, gwh_disp)
        kind, fset = ("coal", "coal_boiler") if displaced == "D3" else (
            "rfo", "oil_engine" if displaced == "D1" else "oil_boiler")
        out["1A1a_disp"] = _combustion(d, tj, kind, fset, mass=mass)
        wtt = d.get("wtt_coal") if displaced == "D3" else d.get("wtt_fuel_oil")
        out["X_fuel"] = {"CO2e": tj * wtt / 1e3}
    elif displaced == "D5":
        out["1A1a_disp"] = {"CO2e": gwh_disp * rec.grid_average}
        out["X_fuel"] = {"CO2e": None}
    elif displaced == "D4":
        out["1A1a_disp"] = {p: 0.0 * h for p in GHGS}
        lng_tj = total_mmcf * (s_case - s) * h * TJ_PER_MMBTU * g2n
        out["X_fuel"] = {"CO2e": lng_tj * d.get("wtt_lng") / 1e3}
    else:
        raise ValueError(displaced)

    # The post-meter leak base (inventory convention: feedstock outside it, process fuel and power inside).
    base_mmcf = rec.fuel * (1 - s) + (moved if receiving != "none" else 0.0)
    out["1B2b"] = {"CH4": base_mmcf * inputs.MMCF_TO_M3 * rec.gas_density / 1e6 * ls
                   * rec.ch4_fraction}
    out["3C_urea"] = {"CO2": 0.0 * h, "N2O": 0.0 * h, "NH3": 0.0 * h}
    out["X_urea"] = {"CO2e": rec.urea_kt * s * import_factor(d, route)}
    out["flows"] = {"urea_domestic_kt": urea_dom, "urea_imported_kt": rec.urea_kt * s + 0 * h,
                    "gas_moved_mmcf": moved + 0 * h, "gas_moved_pj_hhv": moved * h * TJ_PER_MMBTU / 1e3,
                    "gwh_receiving": gwh_recv, "gwh_displaced_running": gwh_disp,
                    "gwh_service": gwh_service}
    return out


NA = "NA"     # a process that emits no greenhouse gas: excluded from CO2e, not 'not estimated'


def co2e(component, ar="AR5"):
    """Gg CO2e of one component's GHGs (fossil CH4); None if a GHG it emits is NE; NA if it emits none."""
    if "CO2e" in component:
        return component["CO2e"]
    if not any(gas in component for gas in GHGS):
        return NA
    total = None
    for gas in GHGS:
        if gas not in component:
            continue
        value = component[gas]
        if value is None:
            return None
        part = gwp.to_co2e(gas, value, ar=ar, fossil=True)
        total = part if total is None else total + part
    return total


def run(rec, case, s_case=1.0, n=10000, seed=SEED, paired=True):
    """Baseline and transition states of one case. paired=False draws the two states independently,
    which is WRONG for a difference and exists only so a test can show by how much."""
    d_base = Draws(rec.params, rec.factors, n, seed)
    d_tran = d_base if paired else Draws(rec.params, rec.factors, n, seed, tag="|transition")
    return state(d_base, rec, case, s_case, 0.0), state(d_tran, rec, case, s_case, s_case), d_base
