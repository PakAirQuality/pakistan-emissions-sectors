"""Air-pollutant SOURCE CLASSES, the COVERED estimate (rc58 W2, cross-module since rc59) - a register executed.

WHAT CHANGED FROM THE SCREENING. Through rc57 industry carried an uncontrolled screening scenario
that shipped beside the air panel and never inside it: three fuels, the power module's factor
rows, the power module's Thar-lignite sulfur, no controlled end. The user's admission rule for
the covered panel is: a defensible activity basis, an applicable factor for the ACTUAL source
class, an explicit process boundary and documented assumptions, with uncertainty - not a stack
measurement at every plant. This module meets that rule source class by source class and the
result ENTERS the panel as a provisional estimate; what cannot meet it is written as a typed
absence with the activity beside it, never a zero and never a borrowed number.

THE REGISTER IS THE METHOD. data/air_source_classes.csv names every (physical source x fuel x
equipment x control) class, the ENGINE quantity it burns or handles (the same terajoules,
tonnes, clinker, ammonia, steel, gas volumes and flared gas the greenhouse-gas streams book -
industry.combustion, industry.solid_fuels, power.captive, ippu.cement, ippu.ammonia,
ippu.steel, fugitives.data, the OCAC petrol total), the share of that activity it takes, the
factor rows it cites in data/air_emission_factors.csv (transcribed with page and digest), the
dated sulfur evidence its SO2 balance uses, and where it is reported. This module resolves each
row against a fiscal year and fails closed: an unknown factor id, a share set that does not sum
to one, an SO2 class with no evidence valid for the year, a physical source that does not own
the class - each raises, or writes a typed absence, by name.

THE CONTROL POSTURE IS SOURCE-CLASS TYPICAL (the user's choice for rc58): cement kilns carry
the particulate collection inherent to clinker production (the dust is product; EMEP 2.A.1
Tier 1 typical abatement), gas and oil boilers, engines and brick kilns carry uncontrolled
factors, and every row's control_state says what the factor already contains, so nothing is
credited twice.

DOUBLE COUNTING IS REFUSED BY CONSTRUCTION. Cement gas and the HDIP cement-coal column are IE
into the clinker-based integrated kiln class (a kiln is never also a boiler); captive oil
engines are IE into the OCAC industrial liquids that already contain their fuel; captive gas is
priced ONCE, here, under industry (IPCC 1.A.2, data/stream_reporting_sector.csv) and leaves the
power screening; the three brick classes partition HDIP's brick coal exactly. Since rc59 the
register spans three computing modules (industry, ippu, fugitives - reporting_sector names
where each class is reported): process pollutants of ammonia, urea, electric-route steel and
soda ash (2.B/2.C), and the fugitive NMVOC of every oil and gas segment the fugitives module
holds activity for, petrol distribution and refuelling, and satellite-observed flaring
(1.B.2). Nothing here moves a greenhouse-gas number.

Usage:  python3 -m pkinv.sectors.industry.air_pollutants
Reads:  data/air_source_classes.csv, data/air_emission_factors.csv,
        data/activity/industry/fuel_sulfur_evidence.csv, data/physical_sources.csv,
        outputs/pakemis_kiln_allocation_adm2.csv, data/gis/kilns/pak_brick_kiln_assets.csv,
        outputs/pakemis_cement_kiln_coal_reconstruction.csv (+ the sector data libraries)
Writes: outputs/pakemis_air_source_classes_fy2015_16_fy2024_25.csv (every class x year x species,
        estimates, typed absences and IE pointers alike, with the reporting sector)
        outputs/pakemis_air_source_class_uncertainty_by_year.csv (per sector x period x species)
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import csv
import os
from collections import defaultdict

from pkinv.core import air_factors, sulfur
from pkinv.activity.store import read_rows
from pkinv.core.uncertainty import combine_sum, product
from pkinv.paths import DATA, OUTPUTS
from pkinv.core.reporting_window import CORE_FY_ENDS, CORE_SUFFIX
from pkinv.sectors.industry import combustion, solid_fuels
from pkinv.sectors.industry.data import IndustryData

REGISTER = asset_path(DATA, "air_source_classes.csv")
PHYSICAL = asset_path(DATA, "physical_sources.csv")
KILN_ALLOCATION = asset_path(OUTPUTS, "pakemis_kiln_allocation_adm2.csv")
KILN_ASSETS = asset_path(DATA, "gis", "kilns", "pak_brick_kiln_assets.csv")
KILN_COAL_BAND = asset_path(OUTPUTS, "pakemis_cement_kiln_coal_reconstruction.csv")
OCAC_SECTORAL = asset_path(DATA, "activity", "transport", "ocac_sectoral_annual.csv")
FLARE_GAS_DENSITY_KG_M3 = 0.85          # EMEP/EEA 2023 1.B.2.c Table 3-1 note (flare gas)
FLARE_DENSITY_UNCERT_PCT = 15.0         # declared: associated-gas composition varies by field
FLARE_BLEND_UNCERT_PCT = 10.0           # declared: calendar-to-fiscal half-year blend
OUT = asset_path(OUTPUTS, "pakemis_air_source_classes_%s.csv" % CORE_SUFFIX)
UNCERT_OUT = asset_path(OUTPUTS, "pakemis_air_source_class_uncertainty_by_year.csv")
# reporting_sector vocabulary of the register. `power` joined at rc60 with the oil and diesel
# grid classes: SO2 only, on a reviewed plant-fuel-year register, with coal and gas still in the
# screening. Before that every power class reported under industry (the captive four), so this
# tuple and COMPUTING_MODULES differed by exactly that - and a reporting sector the tuple does
# not name is silently dropped rather than reported anywhere, which is why it is the gate.
MODULES = ("industry", "ippu", "fugitives", "power")
COMPUTING_MODULES = tuple(dict.fromkeys(MODULES + ("power",)))

YEARS = CORE_FY_ENDS
STATUSES = ("estimate", "typed_absent", "IE")
CAPTIVE_CATEGORY = "Captive gas self-generation (1A2)"
# the power module's own name for main-activity generation, so the admitted grid rows
# carry the same category as the screening and the greenhouse-gas streams they anchor
GRID_CATEGORY = "Electricity and heat production"
CEMENT_CATEGORY = "Cement kilns, integrated (1A2f gases, 2A1 particulate)"
CLINKER_UNCERT = {"reference": 5.0, "reference_model_census_anchored": 10.0}
QIM_ACTIVITY_UNCERT_PCT = 10.0          # PBS QIM large-scale manufacturing panel (declared)
OIL_DENSITY_T_M3 = 0.85                 # crude / refinery feed, t per m3 (EMEP 1.B.2.a.iv basis)
OIL_DENSITY_UNCERT_PCT = 5.0
FLARE_VOLUME_UNCERT_PCT = 30.0          # VIIRS-derived flared volume (fugitives module basis)

FIELDS = ("period_id", "fiscal_end_year", "sector_id", "source_class_id", "physical_source_id", "category",
          "fuel", "equipment_type", "control_state", "pollutant", "activity_value",
          "activity_unit", "ef_ids", "emissions_kt", "uncert_pct", "status",
          "ghg_anchor_module", "ghg_subitem", "basis")
UNCERT_FIELDS = ("period_id", "fiscal_end_year", "sector_id", "pollutant", "emissions_kt", "uncert_pct",
                 "classes", "basis")


ADMISSION = asset_path(DATA, "activity", "power", "power_so2_admission.csv")
_admission_cache = {}


def admitted_fuel_kt(fy_end, fuel, equipment_class):
    """(kt, uncert_pct) of admitted grid fuel for one fiscal-END year, fuel and equipment class.

    None where the register admits nothing - a station that did not run, a year before a fuel
    appears, or a population held back as `scenario_only`. An absence, never a zero.

    THE REGISTER IS THE BOUNDARY. Only `provisional_estimate` rows are read here; everything the
    review left open stays with the screening, and `tests/test_air_power_admission.py` asserts
    the two populations are disjoint by station, fuel and year rather than inferring it.
    """
    if not _admission_cache:
        for row in read_rows(ADMISSION):
            if row["disposition"] != "provisional_estimate":
                continue
            key = (int(row["fiscal_start_year"]) + 1, row["fuel"], row["equipment_class"])
            kt, u = _admission_cache.get(key, (0.0, 0.0))
            _admission_cache[key] = (kt + float(row["fuel_mass_kt"]),
                                     max(u, float(row["so2_uncert_pct"] or 0)))
        _admission_cache.setdefault("loaded", (0.0, 0.0))
    kt, _u = _admission_cache.get((fy_end, fuel, equipment_class), (None, None))
    if not kt:
        return None, None
    # The activity's own uncertainty, not the balance's: the sulfur term is applied by the
    # factor and would be counted twice if it were carried here as well. The ledger years are a
    # metered quantity and the backcast years a reconstruction that reproduces that quantity to
    # about one percent on sixty overlapping plant-years, so the declared activity uncertainty
    # is the power module's own furnace-oil figure.
    return kt, ADMITTED_ACTIVITY_UNCERT_PCT


ADMITTED_ACTIVITY_UNCERT_PCT = 12.0   # data/power_params.csv activity_uncert_fo, same evidence


def period_id(fy_end):
    return "FY%d-%02d" % (fy_end - 1, fy_end % 100)


# --- registers -----------------------------------------------------------------------------

def classes(module=None):
    """The source-class register, validated: closed status and module vocabularies, shares of
    one activity summing to exactly one (computed shares are validated at run time), IE
    targets that exist, factor ids that resolve, and a physical source that lists the class.
    `module` filters on computing_module (industry | ippu | fugitives) after validation."""
    rows = read_rows(REGISTER)
    by_id = {r["source_class_id"]: r for r in rows}
    if len(by_id) != len(rows):
        raise ValueError("duplicate source_class_id in %s" % os.path.relpath(REGISTER))
    physical = {r["physical_source_id"]: r for r in read_rows(PHYSICAL)}
    declared = defaultdict(float)
    whole = defaultdict(list)
    for r in rows:
        if r["status"] not in STATUSES:
            raise ValueError("%s: status %r" % (r["source_class_id"], r["status"]))
        if r["computing_module"] not in COMPUTING_MODULES or r["reporting_sector"] not in MODULES:
            raise ValueError("%s: module %r / reporting sector %r outside %s"
                             % (r["source_class_id"], r["computing_module"], r["reporting_sector"], MODULES))
        ps = physical.get(r["physical_source_id"])
        if ps is None or r["source_class_id"] not in ps["air_source_classes"].split(";"):
            raise ValueError("%s: physical source %r does not list it" % (r["source_class_id"], r["physical_source_id"]))
        if r["status"] == "IE" and r["ie_target_class"] not in by_id:
            raise ValueError("%s: IE target %r is not a class" % (r["source_class_id"], r["ie_target_class"]))
        if r["status"] == "typed_absent" and not r["gap_id"]:
            raise ValueError("%s: a typed absence needs a gap_id" % r["source_class_id"])
        if r["status"] == "estimate":
            if not r["ef_ids"]:
                raise ValueError("%s: an estimate class cites no factors" % r["source_class_id"])
            for ef_id in r["ef_ids"].split(";"):
                air_factors.factor(ef_id)          # raises UnknownFactor
            if r["activity_share"] != "computed":
                declared[r["activity_function"]] += float(r["activity_share"])
                whole[r["activity_function"]].append(r["share_basis"] == "whole")
    for fn, total in declared.items():
        if any(whole[fn]) and not all(whole[fn]):
            raise ValueError("%s mixes whole-activity classes with a declared partition" % fn)
        if all(whole[fn]):
            continue                    # distinct processes on the same whole activity (rc59: refinery
                                        # process species and refinery flaring both ride the feed)
        if abs(total - 1.0) > 1e-9:
            raise ValueError("shares of %s sum to %.6f, not 1" % (fn, total))
    if module is not None:
        rows = [r for r in rows if r["computing_module"] == module]
    return rows


def covered_core_species(module="industry"):
    """The core species at least one estimate class of `module` prices with a held factor row -
    the set the coverage matrix must show E for that module (industry's NH3 is typed absent
    everywhere; fugitives price NMVOC everywhere and the flare species besides)."""
    out = set()
    for r in classes():
        if r["status"] != "estimate" or r["reporting_sector"] != module:
            continue
        for ef_id in r["ef_ids"].split(";"):
            f = air_factors.factor(ef_id)
            if f["status"] != "absent":
                out.add(f["pollutant"])
    return out


# --- activity ------------------------------------------------------------------------------

class Context:
    """Lazily built sector data libraries and the kiln-frame shares, shared across years."""

    def __init__(self, data=None):
        self.data = data or IndustryData()
        self._power = None
        self._ippu = None
        self._kiln = None
        self._kiln_coal = None
        self._fugitives = None
        self._petrol = None
        self._flares = None
        self._qim = None
        self.sulfur = sulfur.load()

    @property
    def power(self):
        if self._power is None:
            from pkinv.sectors.power.data import PowerData
            self._power = PowerData()
        return self._power

    @property
    def ippu(self):
        if self._ippu is None:
            from pkinv.sectors.ippu.data import IppuData
            self._ippu = IppuData()
        return self._ippu

    @property
    def fugitives(self):
        if self._fugitives is None:
            from pkinv.sectors.fugitives.data import FugitivesData
            self._fugitives = FugitivesData(year=2024)
        return self._fugitives

    def flare_bcm_calendar(self):
        """{calendar year: bcm flared} - the satellite-observed series the fugitives module reads."""
        if self._flares is None:
            from pkinv.sectors.fugitives import observations
            self._flares = {r["year"]: r["flare_volume_bcm"] for r in observations.flare_timeseries()}
        return self._flares

    def petrol_tonnes(self, fy_end):
        """OCAC's TOTAL_INTERNAL motor-spirit tonnes for the fiscal year ending fy_end."""
        if self._petrol is None:
            self._petrol = {int(r["inventory_year"]): float(r["tonnes"])
                            for r in read_rows(OCAC_SECTORAL)
                            if r["sector_row"] == "TOTAL_INTERNAL" and r["product"] == "MS"}
        return self._petrol[fy_end]

    def qim_tonnes(self, item, fy_end):
        """A PBS QIM quantity item summed over the fiscal year ending fy_end, in tonnes; None
        when the panel does not cover the year (an absent row, not a zero)."""
        from pkinv.core import monthly as core_monthly
        from pkinv.core import pbs_qim
        if self._qim is None:
            self._qim = pbs_qim._panel()
        # the item is read by its PRINTED name (uncanonicalised items carry no canonical_item),
        # under the same two refusals as pbs_qim.series: index rows and partial years
        matched = [r for r in self._qim
                   if (r["canonical_item"] == item or (not r["canonical_item"] and r["item"] == item))
                   and int(r["fiscal_year_start"]) == fy_end - 1]
        if not matched:
            return None
        if {r["row_kind"] for r in matched} != {"quantity"} or {r["unit"] for r in matched} != {"MT"}:
            raise ValueError("QIM item %r FY ending %d is not a tonnage quantity row" % (item, fy_end))
        months = {r["month"]: float(r["quantity"]) for r in matched}
        missing = set(core_monthly.months_for(fy_end - 1)) - set(months)
        if missing:
            raise KeyError("QIM item %r FY ending %d is missing months %s" % (item, fy_end, sorted(missing)))
        return sum(months.values())

    def kiln_shares(self):
        """{'fcbk': share, 'zz': share, 'unmapped': share} of HDIP's brick coal: the surveyed
        frame's weight from the shipped kiln allocation (observed vs predicted), split within
        the frame by kiln count x measured coal per kiln-day (FCBTK 4.6 t, zig-zag 3.25 t)."""
        if self._kiln is None:
            mapped = sum(float(r["weight_national"]) for r in read_rows(KILN_ALLOCATION)
                         if r["frame"] == "surveyed_points")
            counts = defaultdict(int)
            for r in _activity_rows(KILN_ASSETS, comments=False):
                counts[r["kiln_type"]] += 1
            unknown = set(counts) - {"FCBK", "ZZ"}
            if unknown:
                raise ValueError("kiln types outside the two classes: %s" % sorted(unknown))
            w_f = counts["FCBK"] * self.data.p("brick_fcbtk_coal_t_per_kiln_day")
            w_z = counts["ZZ"] * self.data.p("brick_zigzag_coal_t_per_kiln_day")
            self._kiln = {"fcbk": mapped * w_f / (w_f + w_z), "zz": mapped * w_z / (w_f + w_z),
                          "unmapped": 1.0 - mapped}
        return self._kiln

    def kiln_coal_central_kt(self, fy_end):
        if self._kiln_coal is None:
            self._kiln_coal = {r["fiscal_year"]: float(r["coal_kt_central"])
                               for r in read_rows(KILN_COAL_BAND)}
        return self._kiln_coal[solid_fuels._fiscal_label(fy_end)]


def share_of(cls, ctx):
    """(share, share_uncert_pct) for a class - declared, whole, or computed from the frame."""
    if cls["activity_share"] == "":
        return 1.0, 0.0                     # typed-absent and IE rows carry no share
    if cls["activity_share"] != "computed":
        return float(cls["activity_share"]), float(cls["share_uncert_pct"] or 0)
    key = cls["share_basis"].split(":", 1)[1]
    shares = ctx.kiln_shares()
    lookup = {"kiln_frame_fcbk": "fcbk", "kiln_frame_zz": "zz", "kiln_frame_unmapped": "unmapped"}
    return shares[lookup[key]], float(cls["share_uncert_pct"] or 0)


def activity(cls, fy_end, ctx):
    """The class's activity for one fiscal-END year as every measure a factor might want -
    {'TJ_ncv', 'TJ_hhv', 't_fuel', 't_brick', 't_clinker', 't_product', 'e3m3_gas', 'm3_oil',
    'value', 'unit', 'uncert_pct', 'basis'} - or None when the class has no activity that year (a product OCAC prints no
    tonnes for; not a zero, an absence of the row). Shares are applied here."""
    fn = cls["activity_function"]
    if fn == "none":
        return None
    d = ctx.data
    share, share_u = share_of(cls, ctx)
    m = {"basis": "observed_fiscal"}
    if fn.startswith("industry.gas_TJ:"):
        stream = fn.split(":", 1)[1]
        if stream not in d.streams(fy_end):
            return None
        from pkinv.sectors.fugitives import post_meter
        tj = combustion.gas_TJ(d, stream, fy_end) * share * post_meter.combusted_fraction()
        if tj == 0.0:
            return None
        m.update(TJ_ncv=tj, TJ_hhv=tj / d.p("industry_gross_to_net"), value=tj, unit="TJ",
                 uncert_pct=product(d.p("industry_activity_uncert"), d.pu("industry_hhv_btu_per_scf"),
                                    d.pu("industry_gross_to_net"), share_u))
    elif fn.startswith("industry.liquid_TJ:"):
        code = fn.split(":", 1)[1]
        if code not in d.liquid_products(fy_end):
            return None
        tonnes = d.liquid_tonnes(code, fy_end) * share
        tj = combustion.liquid_TJ(d, code, fy_end) * share
        _f, ncv_item = d.LIQUID_ITEMS[code]
        m.update(TJ_ncv=tj, TJ_hhv=tj / d.p("industry_liquid_ncv_over_gcv"), t_fuel=tonnes,
                 value=tj, unit="TJ",
                 uncert_pct=product(d.p("industry_liquid_activity_uncert"), d.efu("industry_ncv", ncv_item),
                                    d.pu("industry_liquid_ncv_over_gcv"), share_u))
    elif fn.startswith("industry.coal_kt:"):
        consumer = fn.split(":", 1)[1]
        kt = solid_fuels.coal_kt(solid_fuels._fiscal_label(fy_end), consumer) * share
        m.update(t_fuel=kt * 1000.0, value=kt, unit="kt",
                 uncert_pct=product(d.p("industry_coal_activity_uncert"), share_u))
        if cls["product_per_activity"]:
            m["t_brick"] = kt * 1000.0 * float(cls["product_per_activity"])
    elif fn.startswith("power.admitted_fuel_kt:"):
        # The reviewed admission register, summed to (fuel x equipment class) for the year.
        # It is a MASS from the start - NEPRA prints tonnes of furnace oil and litres of diesel -
        # so the balance needs no calorific value and none is invented here. Rows the register
        # typed `scenario_only` are excluded: they are the population the screening keeps.
        _fuel, _equip = fn.split(":", 2)[1:]
        kt, u = admitted_fuel_kt(fy_end, _fuel, _equip)
        if kt is None:
            return None
        m.update(t_fuel=kt * 1000.0, value=kt, unit="kt",
                 uncert_pct=product(u, share_u),
                 basis="observed_fiscal")
    elif fn == "power.captive_gas_TJ":
        from pkinv.sectors.power import captive
        p = ctx.power
        from pkinv.sectors.fugitives import post_meter
        # AP combustion factors describe burned gas, matching the GHG boundary;
        # delivered gas remains the separate activity control.
        tj = captive.gas_TJ(p, year=fy_end) * share * post_meter.combusted_fraction()
        m.update(TJ_ncv=tj, TJ_hhv=tj / p.p("captive_gross_to_net"), value=tj, unit="TJ",
                 uncert_pct=product(p.p("captive_activity_uncert"), p.pu("captive_hhv_btu_per_scf"),
                                    p.pu("captive_gross_to_net"), share_u))
    elif fn == "ippu.clinker_kt":
        from pkinv.sectors.ippu import cement
        ip = ctx.ippu
        _comps, memo = cement.compute(ip, fy_end, activity_source=ip.cement_activity_source(fy_end))
        kt = memo[0]["clinker_production_kt"] * share
        status = memo[0].get("configuration_status", "reference")
        m.update(t_clinker=kt * 1000.0, value=kt, unit="kt clinker",
                 uncert_pct=product(CLINKER_UNCERT[status], share_u),
                 basis="observed_fiscal" if status == "reference" else "reconstructed")
    elif fn == "derived:cement_column_minus_kiln_coal":
        column = solid_fuels.coal_kt(solid_fuels._fiscal_label(fy_end), "cement")
        kt = max(0.0, column - ctx.kiln_coal_central_kt(fy_end))
        m.update(t_fuel=kt * 1000.0, value=kt, unit="kt", uncert_pct=None, basis="reconstructed")
    elif fn in ("ippu.nh3_kt", "ippu.urea_kt"):
        from pkinv.sectors.ippu import ammonia
        ip = ctx.ippu
        label = ammonia.fiscal_label(fy_end)
        kt = (ammonia.nh3_kt(ip, label) if fn == "ippu.nh3_kt"
              else ammonia.production_kt(ip, label, "Urea")) * share
        if kt == 0.0:
            return None
        # the ammonia module's own activity uncertainty (NFDC production, both products)
        m.update(t_product=kt * 1000.0, value=kt, unit="kt",
                 uncert_pct=product(ammonia.ACTIVITY_UNCERT_PCT, share_u))
    elif fn == "ippu.billets_kt":
        from pkinv.sectors.ippu import steel
        kt = steel.billets_kt(ctx.ippu, fy_end) * share
        m.update(t_product=kt * 1000.0, value=kt, unit="kt",
                 uncert_pct=product(steel.ACTIVITY_UNCERT_PCT, share_u))
    elif fn.startswith("ippu.qim_tonnes:"):
        item = fn.split(":", 1)[1]
        t = ctx.qim_tonnes(item, fy_end)
        if t is None:
            return None
        t *= share
        m.update(t_product=t, value=t / 1000.0, unit="kt",
                 uncert_pct=product(QIM_ACTIVITY_UNCERT_PCT, share_u), basis="observed_fiscal")
    elif fn.startswith("fugitives.activity:"):
        aid = fn.split(":", 1)[1]
        a = ctx.fugitives.activity(aid, fy_end)               # fiscal-END keyed anchors
        v = float(a["value"]) * share
        u = product(max(float(a["uncertainty_low_pct"]), float(a["uncertainty_high_pct"])), share_u)
        if a["unit"] == "million_m3":
            m.update(e3m3_gas=v * 1000.0, value=v, unit="million m3", uncert_pct=u)
        elif a["unit"] == "thousand_m3":
            m.update(m3_oil=v * 1000.0, t_product=v * 1000.0 * OIL_DENSITY_T_M3, value=v,
                     unit="thousand m3", uncert_pct=product(u, OIL_DENSITY_UNCERT_PCT))
        else:
            raise ValueError("%s: fugitives activity %s carries unit %r" % (cls["source_class_id"], aid, a["unit"]))
        m["basis"] = "observed_fiscal" if a.get("status", "") in ("observed", "estimated", "") else a["status"]
    elif fn == "fugitives.flare_bcm":
        cal = ctx.flare_bcm_calendar()
        bcm = 0.5 * cal[fy_end - 1] + 0.5 * cal[fy_end]        # Jul-Jun straddles two calendar years
        bcm *= share
        m.update(e3m3_gas=bcm * 1e6, t_product=bcm * 1e9 * FLARE_GAS_DENSITY_KG_M3 / 1000.0,
                 value=bcm, unit="bcm flared",
                 uncert_pct=product(FLARE_VOLUME_UNCERT_PCT, FLARE_BLEND_UNCERT_PCT, share_u),
                 basis="calendar_blend")
    elif fn == "transport.ocac_tonnes:MS:TOTAL_INTERNAL":
        t = ctx.petrol_tonnes(fy_end) * share
        m.update(t_product=t, value=t / 1000.0, unit="kt",
                 uncert_pct=product(ctx.data.p("industry_liquid_activity_uncert"), share_u))
    else:
        raise ValueError("%s: unknown activity_function %r" % (cls["source_class_id"], fn))
    return m


# --- factors -------------------------------------------------------------------------------

def _measure(m, unit_key, cls, ef_id):
    key = {"TJ_ncv": "TJ_ncv", "TJ_hhv": "TJ_hhv", "t_fuel": "t_fuel", "t_brick": "t_brick",
           "t_clinker": "t_clinker", "t_product": "t_product", "e3m3_gas": "e3m3_gas",
           "m3_oil": "m3_oil"}[unit_key]
    if key not in m:
        raise ValueError("%s cites %s, which wants %s, but the class's activity carries no %s"
                         % (cls["source_class_id"], ef_id, unit_key, key))
    return m[key]


def price(cls, fy_end, ctx, m):
    """{pollutant: (kt, uncert_pct, ef_ids_used)} for one class-year, plus
    {pollutant: reason} for the species the class types absent."""
    totals = defaultdict(list)          # pollutant -> [(kt, u, ef_id)]
    absent = {}
    shares = []                         # deferred BC rows
    sulfur_row = None
    if cls["sulfur_evidence_id"]:
        try:
            sulfur_row = sulfur.evidence(cls["sulfur_evidence_id"], fy_end, cls["source_class_id"], ctx.sulfur)
        except sulfur.NoSulfurEvidence as exc:
            absent["SO2"] = str(exc)
    for ef_id in cls["ef_ids"].split(";"):
        f = air_factors.factor(ef_id)
        pol = f["pollutant"]
        if f["status"] == "absent":
            absent.setdefault(pol, "%s: %s" % (f["gap_id"], f["note"]))
            continue
        if f["activity_basis"] == "pm25_share":
            shares.append(f)
            continue
        if f["activity_basis"] == "sulfur_balance":
            if sulfur_row is None:
                if "SO2" not in absent:
                    absent["SO2"] = ("%s cites the sulfur balance but names no sulfur evidence"
                                     % cls["source_class_id"])
                continue
            fuel_kt = m["t_fuel"] / 1000.0
            r = float(cls["sulfur_retention_frac"] or 0)
            kt = sulfur.so2_kt(fuel_kt, float(sulfur_row["s_pct_central"]),
                               float(cls["sulfur_oxidised_frac"] or 1.0), r)
            u = product(m["uncert_pct"],
                        sulfur.so2_uncert_pct(sulfur_row, r, float(cls["sulfur_retention_uncert_pct"] or 0)))
            totals["SO2"].append((kt, u, ef_id))
            continue
        k, unit_key = air_factors.kg_per_unit(f)
        q = _measure(m, unit_key, cls, ef_id)
        u_terms = [m["uncert_pct"], air_factors.uncert_pct(f)]
        if unit_key == "t_brick":
            u_terms.append(float(cls["product_ratio_uncert_pct"] or 0))
        scaled = air_factors.scaled_per_pct(f)
        if scaled == "S":
            if sulfur_row is None:
                absent.setdefault(pol, "%s scales with fuel sulfur and the class has no sulfur evidence for FY ending %d"
                                  % (ef_id, fy_end))
                continue
            k *= float(sulfur_row["s_pct_central"])
            u_terms.append(float(sulfur_row["uncert_pct"]))
        elif scaled == "A":
            raise ValueError("%s: ash-scaled factor %s cited and no ash evidence register exists"
                             % (cls["source_class_id"], ef_id))
        totals[pol].append((q * k / 1e6, product(*u_terms), ef_id))
    out = {}
    for pol, terms in totals.items():
        kt, u = combine_sum([(t[0], t[1]) for t in terms])
        out[pol] = (kt, u, ";".join(t[2] for t in terms))
    for f in shares:
        base = out.get("PM2.5")
        if base is None:
            absent.setdefault(f["pollutant"], "%s is a share of PM2.5 and the class prices no PM2.5" % f["ef_id"])
            continue
        frac, _unit = air_factors.kg_per_unit(f)
        out[f["pollutant"]] = (base[0] * frac, product(base[1], air_factors.uncert_pct(f)),
                               base[2] + ";" + f["ef_id"])
    for pol in list(absent):
        if pol in out:
            del absent[pol]
    return out, absent


IPPU_CATEGORY = "Industrial process emissions (2B, 2C)"
FUGITIVES_CATEGORY = "Fugitive emissions from oil and gas (1B2)"


def category_of(cls):
    if cls["computing_module"] == "ippu":
        return IPPU_CATEGORY
    if cls["computing_module"] == "fugitives":
        return FUGITIVES_CATEGORY
    # rc60: DISCRIMINATE ON THE PHYSICAL SOURCE, not on the anchor module. This used to read
    # `if ghg_anchor_module == "power": return CAPTIVE_CATEGORY`, which was correct for exactly
    # as long as the captive four were the only classes anchoring a power stream. The admitted
    # grid classes anchor one too, and they labelled themselves "Captive gas self-generation
    # (1A2)" - main-activity furnace oil reported under a captive category, which broke the
    # air join outright and would otherwise have moved the captive boundary silently.
    if cls["physical_source_id"] == "ps_captive_generation":
        return CAPTIVE_CATEGORY
    if cls["physical_source_id"] == "ps_grid_generation":
        return GRID_CATEGORY
    if cls["source_class_id"] == "cement_kiln_integrated":
        return CEMENT_CATEGORY
    return combustion.CATEGORY


# --- the year --------------------------------------------------------------------------------

def compute(fy_end, ctx=None, register=None):
    """Every register row resolved for one fiscal-END year: a list of detail rows (FIELDS)."""
    ctx = ctx or Context()
    rows = []
    for cls in register or classes():
        m = activity(cls, fy_end, ctx)
        base = {"period_id": period_id(fy_end), "fiscal_end_year": fy_end,
                "sector_id": cls["reporting_sector"],
                "source_class_id": cls["source_class_id"],
                "physical_source_id": cls["physical_source_id"], "category": category_of(cls),
                "fuel": cls["fuel"], "equipment_type": cls["equipment_type"],
                "control_state": cls["control_state"],
                "activity_value": "" if m is None else m["value"],
                "activity_unit": cls["activity_unit"] if m is None else m["unit"],
                "ghg_anchor_module": cls["ghg_anchor_module"], "ghg_subitem": cls["ghg_anchor_subitem"]}
        if cls["status"] == "IE":
            rows.append(dict(base, pollutant="", ef_ids="", emissions_kt="", uncert_pct="",
                             status="IE", basis="included in %s: %s" % (cls["ie_target_class"], cls["note"])))
            continue
        if cls["status"] == "typed_absent":
            rows.append(dict(base, pollutant="", ef_ids="", emissions_kt="", uncert_pct="",
                             status="typed_absent", basis="%s: %s" % (cls["gap_id"], cls["note"])))
            continue
        if m is None:
            rows.append(dict(base, pollutant="", ef_ids="", emissions_kt="", uncert_pct="",
                             status="no_activity", basis="the activity source prints no quantity "
                             "for this class this year (absent row, not zero)"))
            continue
        priced, absent = price(cls, fy_end, ctx, m)
        for pol, (kt, u, ef_ids) in sorted(priced.items()):
            rows.append(dict(base, pollutant=pol, ef_ids=ef_ids, emissions_kt=kt, uncert_pct=u,
                             status="estimate", basis=cls["control_basis"]))
        for pol, reason in sorted(absent.items()):
            rows.append(dict(base, pollutant=pol, ef_ids="", emissions_kt="", uncert_pct="",
                             status="typed_absent", basis=reason))
        base["basis"] = m["basis"]
    return rows


def atoms(fy_end, ctx=None, module="industry"):
    """The rows the air panel consumes for one REPORTING sector: estimate rows only, with the
    anchor and basis the panel's _atom() wants. emissions_kt is a float; nothing is rounded."""
    out = []
    ctx = ctx or Context()
    reg = [r for r in classes() if r["reporting_sector"] == module]
    basis_of = {}
    for cls in reg:
        if cls["status"] == "estimate":
            m = activity(cls, fy_end, ctx)
            if m is not None:
                basis_of[cls["source_class_id"]] = m["basis"]
    for r in compute(fy_end, ctx, reg):
        if r["status"] != "estimate":
            continue
        out.append({"sector_id": r["sector_id"], "category": r["category"], "subitem": r["source_class_id"],
                    "fuel": r["fuel"], "process": r["equipment_type"],
                    "pollutant": r["pollutant"], "emissions_kt": r["emissions_kt"],
                    "uncert_pct": r["uncert_pct"], "ghg_subitem": r["ghg_subitem"],
                    "ghg_anchor_module": r["ghg_anchor_module"],
                    "activity_basis": basis_of[r["source_class_id"]],
                    "factor_basis": "air_emission_factors.csv: " + r["ef_ids"]})
    return out


def uncertainty_rows(detail):
    """Per (period, species): the covered total and its combined uncertainty, classes sharing
    a factor row treated as correlated (combine_sum corr_group = the row's ef_ids)."""
    by = defaultdict(list)
    for r in detail:
        if r["status"] == "estimate":
            by[(r["period_id"], r["fiscal_end_year"], r["sector_id"], r["pollutant"])].append(
                (r["emissions_kt"], r["uncert_pct"], r["ef_ids"], r["source_class_id"]))
    out = []
    for (pid, fy, sec, pol), terms in sorted(by.items()):
        total, u = combine_sum([(t[0], t[1], t[2]) for t in terms])
        out.append({"period_id": pid, "fiscal_end_year": fy, "sector_id": sec, "pollutant": pol,
                    "emissions_kt": total, "uncert_pct": u,
                    "classes": ";".join(t[3] for t in terms),
                    "basis": "IPCC Approach 1: activity x share x factor x sulfur terms in quadrature per class; "
                             "classes citing the same factor rows combined as correlated"})
    return out


def main():
    ctx = Context()
    detail = []
    for fy in YEARS:
        detail.extend(compute(fy, ctx))
    with open(OUT, "w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=list(FIELDS), lineterminator="\n")
        w.writeheader()
        for r in detail:
            w.writerow(dict(r, emissions_kt="" if r["emissions_kt"] == "" else "%.6f" % r["emissions_kt"],
                            uncert_pct="" if r["uncert_pct"] == "" else "%.1f" % r["uncert_pct"],
                            activity_value="" if r["activity_value"] == "" else "%.4f" % r["activity_value"]))
    with open(asset_path(OUTPUTS, "pakemis_air_source_classes_fy2015_16_fy2023_24.csv"),
              "w", newline="", encoding="utf-8") as h:
        writer = csv.DictWriter(h, fieldnames=list(FIELDS), lineterminator="\n")
        writer.writeheader()
        for r in detail:
            if r["fiscal_end_year"] <= 2024:
                writer.writerow(dict(r, emissions_kt="" if r["emissions_kt"] == "" else "%.6f" % r["emissions_kt"],
                                     uncert_pct="" if r["uncert_pct"] == "" else "%.1f" % r["uncert_pct"],
                                     activity_value="" if r["activity_value"] == "" else "%.4f" % r["activity_value"]))
    unc = uncertainty_rows(detail)
    with open(UNCERT_OUT, "w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=list(UNCERT_FIELDS), lineterminator="\n")
        w.writeheader()
        for r in unc:
            w.writerow(dict(r, emissions_kt="%.6f" % r["emissions_kt"], uncert_pct="%.1f" % r["uncert_pct"]))
    n_e = sum(1 for r in detail if r["status"] == "estimate")
    n_a = sum(1 for r in detail if r["status"] == "typed_absent")
    print("air source classes -> %s (%d estimate rows, %d typed absences, %d IE pointers)"
          % (os.path.relpath(OUT), n_e, n_a, sum(1 for r in detail if r["status"] == "IE")))
    for r in unc:
        if r["fiscal_end_year"] == 2024:
            print("  FY2023-24 %-10s %-6s %10.3f kt  +/-%5.1f%%" % (r["sector_id"], r["pollutant"], r["emissions_kt"], r["uncert_pct"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
