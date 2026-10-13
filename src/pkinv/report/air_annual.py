"""The nine-fiscal-year air-pollutant panel: atoms, rollup, coverage (air program Wave 3).

One covered-sources panel, FY2015-16..FY2023-24, built the way the greenhouse-gas
national series is built: each sector's own air engine called for each year under the
sector's own fiscal convention (power and aviation are fiscal-START keyed; everything
else fiscal-END), never a national total distributed downward. Three products:

  pakemis_air_atomic_annual.csv     one row per period x sector x category x process x
                                    subitem x pollutant, Gg (1 kt == 1 Gg), each atom
                                    carrying its activity basis, its factor source and
                                    its own stream anchor (air_join.stream_for,
                                    fail-closed - a row that cannot name its stream
                                    does not enter the panel)
  pakemis_air_annual_fy2015_16_fy2023_24.csv
                                    the rollup (period x sector x category x
                                    pollutant), coverage_scope=covered_sources_only in
                                    every row - this is NOT a complete national
                                    seven-species inventory and does not claim to be
  pakemis_air_coverage_matrix.csv   630 rows = 9 periods x 10 modules x 7 core
                                    species, closed E/NE/IE/NO/NA vocabulary
                                    (pkinv.core.notation): a missing estimate is
                                    written as its key, never as a zero

POWER IS NOT IN THE PANEL. Its air layer is an uncontrolled screening scenario by its
own declaration, so it ships beside the panel as
power_air_screening_fy2015_16_fy2023_24.csv and the coverage matrix writes power NE
with the scenario named in the basis - publishing a bound under a coverage flag would
launder it into an estimate. Since rc58 that screening is GRID-ONLY: captive
self-generation is IPCC 1.A.2 and is priced once, in the industrial layer, inside the
panel.

INDUSTRY IS IN THE PANEL (rc58). pkinv.sectors.industry.air_pollutants executes the
source-class register (data/air_source_classes.csv) - the same
terajoules, tonnes and clinker the greenhouse-gas streams book, on factors transcribed
with page and digest, SO2 from a sulfur balance on dated evidence, source-class-typical
controls, every class a stream anchor - and its estimate rows are atoms here; its typed
absences (NH3 everywhere, other-industry coal, captive solids, bagasse) stay in its own
detail file and in the coverage matrix's absence register.

THE ABSENCES ARE DATA. Every (module, species) cell the panel does not fill is typed by
data/air_coverage_absences.csv (or by the two code branches power and aviation keep);
a cell nobody types fails the build.

SUPPLEMENTAL SPECIES STAY OUT OF THE PANEL'S CORE. The seven are BC, CO, NH3, NMVOC,
NOx (as NO2), PM2.5, SO2 (dim_pollutant core7). Aviation's HC is not NMVOC, power's
VOC is not NMVOC, wear TSP/PM10 are strata of the particulate containment chain -
atoms for supplemental species ARE written (they are real emissions of real processes)
with core7=no, and the rollup and coverage matrix count only the core.

Period honesty: agriculture is REBUILT per year from its own fiscal activity
(fa.data_for_fiscal_year - Economic Survey crops and nitrogen), NOT the calendar
FAOSTAT series the 1990-2024 product uses; its livestock-driven atoms ride the
inter-census calendar projection and say so (activity_basis=calendar_projection).
Residential scales each stream's reference rows by the stream's own fuel ratio
(timeseries.fuel_TJ_series), with the five held fuels labelled held. Waste moves on
its population panel alone (parameters declared held). Railways and transport burn
their year's own fuel under the year's own declared sulfur regime. Aviation flies its
year's own movements on its era's own fleet mix.
"""

from pkinv.assets import asset_path
import csv
import io
import os
from collections import defaultdict

from pkinv.core import configurations as conf
from pkinv.paths import OUTPUTS
from pkinv.report import air_join

YEARS = tuple(range(2016, 2025))            # fiscal-END keys, FY2015-16..FY2023-24
CORE7 = ("BC", "CO", "NH3", "NMVOC", "NOx", "PM2.5", "SO2")
MODULES = ("agriculture", "aviation", "fugitives", "industry", "ippu", "power",
           "railways", "residential", "transport", "waste")
SCOPE = "covered_sources_only"

ATOM_FIELDS = ("period_id", "configuration_id", "sector_id", "category", "process",
               "fuel_or_material", "subitem", "pollutant", "core7",
               "pollutant_mass_basis", "estimate_status", "activity_basis",
               "emission_factor_source", "emissions_Gg", "support_anchor_id",
               "coverage_scope")
ROLLUP_FIELDS = ("period_id", "fiscal_end_year", "configuration_id", "sector_id",
                 "category", "pollutant", "emissions_Gg", "coverage_scope")
COVERAGE_FIELDS = ("period_id", "fiscal_end_year", "sector_id", "pollutant", "state",
                   "state_basis", "activity_basis", "gap_id", "note")
POWER_FIELDS = ("period_id", "fiscal_end_year", "category", "fuel", "fuel_detail",
                "pollutant", "emissions_kt", "uncert_pct", "ap42_table", "scenario",
                "basis")

ATOMS_OUT = asset_path(OUTPUTS, "pakemis_air_atomic_annual.csv")
ROLLUP_OUT = asset_path(OUTPUTS, "pakemis_air_annual_fy2015_16_fy2023_24.csv")
COVERAGE_OUT = asset_path(OUTPUTS, "pakemis_air_coverage_matrix.csv")
POWER_OUT = asset_path(OUTPUTS, "power_air_screening_fy2015_16_fy2023_24.csv")


def period_id(fy_end):
    return "FY%d-%s" % (fy_end - 1, str(fy_end)[2:])


def _basis_note(pollutant):
    if pollutant == "NOx":
        return "NO2-equivalent"
    if pollutant in ("BC", "OC"):
        return "component of PM2.5"
    if pollutant in ("PM", "PM10", "TSP"):
        return "particulate stratum (contains PM2.5)"
    return "native mass"


def _atom(fy_end, sector, row, kt, activity_basis, factor_source, process="",
          fuel=""):
    sid = air_join.stream_for(sector, row, _atom.index)
    return {
        "period_id": period_id(fy_end), "configuration_id": conf.REFERENCE,
        "sector_id": sector,
        "category": row.get("category", ""), "process": process,
        "fuel_or_material": fuel or row.get("fuel", ""),
        "subitem": row.get("subitem", "") or row.get("fuel", ""),
        "pollutant": row["pollutant"],
        "core7": "yes" if row["pollutant"] in CORE7 else "no",
        "pollutant_mass_basis": _basis_note(row["pollutant"]),
        "estimate_status": "E",
        "activity_basis": activity_basis,
        "emission_factor_source": factor_source,
        "emissions_Gg": kt,                     # 1 kt == 1 Gg, the panel's one unit
        "support_anchor_id": sid,
        "coverage_scope": SCOPE,
    }


# --- the seven covered sectors ---------------------------------------------------

def agriculture_atoms(fy_end):
    from pkinv.sectors.agriculture import air_pollutants as ap
    from pkinv.sectors.agriculture import fiscal_activity as fa
    data = fa.data_for_fiscal_year(fy_end)
    out = []
    for r in ap.compute(data):
        sub = r["subitem"].lower()
        livestock = any(w in sub for w in ("cattle", "buffalo", "pasture", "manure",
                                           "housing", "storage", "application"))
        basis = "calendar_projection" if livestock else "observed_fiscal"
        out.append(_atom(fy_end, "agriculture", r, r["emissions_kt"], basis,
                         "agriculture EF registry (EMEP/IPCC per stream)"))
    return out


def residential_atoms(fy_end):
    """Residential atoms under BOTH configurations (air spatial Wave A; roles swapped
    at rc67).

    REF_2023_24: every stream's reference rows scaled by its own fuel-series ratio.
    Dung rides the two-anchor HIES per-household series, every year labelled by
    timeseries.dung_survey_basis - a survey-anchored reconstruction that never claims
    nine observed years. L_HERD1624 differs in the DUNG rows alone: the ledger engine
    rows (ap.compute(dung_basis="ledger")) scaled by the herd, all the dung agriculture
    diverts in that year burned in households. Non-residential sectors are
    configuration-invariant by construction, so the atoms table carries them once
    under the reference id and the rollup materialises both configurations in full
    (the greenhouse-gas annual product's own convention for its L rows)."""
    from pkinv.sectors.residential.data import ResidentialData
    from pkinv.sectors.residential import air_pollutants as ap
    from pkinv.sectors.residential import combustion, timeseries as ts
    data = residential_atoms._data
    if data is None:
        data = residential_atoms._data = ResidentialData()
        residential_atoms._series = ts.fuel_TJ_series(data)
        residential_atoms._ref = combustion.fuel_TJ(data)
        residential_atoms._rows = ap.compute(data)
        residential_atoms._ledger_rows = ap.compute(
            data, dung_basis=conf.ALTERNATIVE_DUNG_BASIS)
    series = residential_atoms._series[fy_end]
    basis_of = series["_basis"]
    ref = residential_atoms._ref

    def word(stream):
        b = basis_of[stream]
        return ("observed" if b == "OGRA series" else
                "held" if b.startswith("HELD") else "reconstructed")

    out = []
    for r in residential_atoms._rows:
        stream = ts.WORD_OF[r["subitem"].split()[0]]
        kt = r["emissions_kt"] * series[stream] / ref[stream]
        basis = (ts.dung_survey_basis(fy_end) if stream == "Dung cake"
                 else word(stream))
        out.append(_atom(fy_end, "residential", r, kt, basis,
                         "Andreae 2019 biofuel / EMEP 1.A.4 fossil", fuel=stream))
    # configuration L: dung rows on the herd-scaled nitrogen ledger, every other
    # stream identical to the reference (the ledger engine rows differ only there)
    herd = 1.0 if fy_end == data.year else ts.herd_scale(fy_end)
    for r in residential_atoms._ledger_rows:
        stream = ts.WORD_OF[r["subitem"].split()[0]]
        if stream == "Dung cake":
            kt, basis = r["emissions_kt"] * herd, "reconstructed"
        else:
            kt, basis = r["emissions_kt"] * series[stream] / ref[stream], word(stream)
        a = _atom(fy_end, "residential", r, kt, basis,
                  "Andreae 2019 biofuel / EMEP 1.A.4 fossil", fuel=stream)
        a["configuration_id"] = conf.LEDGER_SERIES
        out.append(a)
    return out


residential_atoms._data = None


def waste_atoms(fy_end):
    from pkinv.sectors.waste.data import WasteData
    from pkinv.sectors.waste import air_pollutants as ap
    data = waste_atoms._data or WasteData()
    waste_atoms._data = data
    return [_atom(fy_end, "waste", r, r["emissions_kt"],
                  "observed_population_held_parameters",
                  "Andreae 2019 garbage burning",
                  fuel="mixed municipal waste")
            for r in ap.compute(data, fy_end)]


waste_atoms._data = None


def railways_atoms(fy_end):
    from pkinv.sectors.railways.data import RailwaysData
    from pkinv.sectors.railways import air_pollutants as ap
    data = railways_atoms._data or RailwaysData()
    railways_atoms._data = data
    return [_atom(fy_end, "railways", r, r["emissions_kt"], "observed",
                  r.get("source", "EMEP 1.A.3.c Table 3-1"))
            for r in ap.compute(data, fy_end)]


railways_atoms._data = None


def transport_atoms(fy_end):
    from pkinv.sectors.transport.data import TransportData
    from pkinv.sectors.transport import air_pollutants as ap
    data = transport_atoms._data or TransportData()
    transport_atoms._data = data
    return [_atom(fy_end, "transport", r, r["emissions_kt"], "observed",
                  r.get("factor_basis", "EMEP Tier 1 road"),
                  process=r["process"], fuel=r["fuel"])
            for r in ap.compute(data, fy_end)]


transport_atoms._data = None


def aviation_atoms(fy_end):
    from pkinv.sectors.aviation.data import AviationData
    from pkinv.sectors.aviation import air_pollutants as ap
    data = aviation_atoms._data or AviationData()
    aviation_atoms._data = data
    return [_atom(fy_end, "aviation", r, r["emissions_kt"], "observed",
                  r.get("method", "EEDB / fuel-based"), fuel="Jet A-1")
            for r in ap.compute(data, fy_end - 1)]        # fiscal-START keyed


aviation_atoms._data = None

def register_atoms(module):
    """rc58/rc59: the source-class register's estimate for one REPORTING sector - every
    class reported there that prices this year, one atom per (class, species). The class's
    own activity basis (observed_fiscal for OGRA/OCAC/HDIP/NFDC/QIM/fugitives-anchor
    quantities, reconstructed for the census-anchored clinker balance, calendar_blend for
    the satellite flare volumes) and its factor rows travel on the atom; the anchor is the
    class's declared greenhouse-gas stream, looked up in the module that computes it
    (captive classes anchor the power module's captive stream and report under industry;
    soda ash and petrol distribution name DECLARED proxies)."""
    def atoms(fy_end):
        from pkinv.sectors.industry import air_pollutants as ap
        ctx = register_atoms._ctx or ap.Context()
        register_atoms._ctx = ctx
        return [_atom(fy_end, module, r, r["emissions_kt"], r["activity_basis"],
                      r["factor_basis"], process=r["process"], fuel=r["fuel"])
                for r in ap.atoms(fy_end, ctx, module=module)]
    atoms.__name__ = "%s_atoms" % module
    return atoms


register_atoms._ctx = None
industry_atoms = register_atoms("industry")
ippu_atoms = register_atoms("ippu")
fugitives_atoms = register_atoms("fugitives")
# rc60: the oil and diesel grid classes report under POWER, not under industry as the captive
# four do, so the register's generic reader serves them unchanged. This tuple is the gate: a
# sector absent from it contributes no atoms and therefore no panel row, however complete its
# register entries are. SO2 only - the classes cite no other species, so every other pollutant
# on these stations stays typed absent exactly as before.
power_atoms = register_atoms("power")

SECTOR_ATOMS = (
    ("agriculture", agriculture_atoms),
    ("aviation", aviation_atoms),
    ("fugitives", fugitives_atoms),
    ("industry", industry_atoms),
    ("ippu", ippu_atoms),
    ("power", power_atoms),
    ("railways", railways_atoms),
    ("residential", residential_atoms),
    ("transport", transport_atoms),
    ("waste", waste_atoms),
)


def admitted_remainder_fraction(fy_end, screening_fuel):
    """(fraction still unestimated, why) for one fiscal-END year - a thin alias.

    THE NARROWING ITSELF LIVES IN power.air_pollutants, so that every consumer of the
    screening gets the same answer; this wrapper exists because the bridge and the guards
    speak in fiscal-END years while the power module is fiscal-START keyed, and one place
    should own that conversion.
    """
    from pkinv.sectors.power.data import PowerData
    from pkinv.sectors.power import air_pollutants as ap
    data = power_screening_rows._data or PowerData()
    power_screening_rows._data = data
    return ap.admitted_remainder_fraction(data, fy_end - 1, screening_fuel)


def power_screening_rows(fy_end):
    """BOTH scenario ends since the absence-screening round: the uncontrolled
    default and the controlled case (every unit credited with the named held-table
    control). The pair brackets what the fleet emits GIVEN the control inventory is
    unknown; neither is an estimate (see power.air_pollutants.CONTROLLED_BASIS).
    GRID ONLY since rc58: captive gas is priced once, in the industry atoms.

    NARROWED AT rc60. Oil and diesel SO2 is now estimated per station, so those two cells no
    longer screen the whole fleet - they screen what is left of it. Every other cell is
    untouched, and the narrowing is applied to SO2 alone: NOx, PM and the rest on these same
    stations remain entirely screened, because admitting one pollutant establishes nothing
    about the others.
    """
    from pkinv.sectors.power.data import PowerData
    from pkinv.sectors.power import air_pollutants as ap
    data = power_screening_rows._data or PowerData()
    power_screening_rows._data = data
    out = []
    for scenario in ("uncontrolled", "controlled_case"):
        for r in ap.compute(data, fy_end - 1, scenario=scenario):  # fiscal-START keyed
            # NOT narrowed here: power.air_pollutants.compute does it, so that the nine-year
            # panel and outputs/power_air_pollutants_fy2023_24.csv - the file the spatial layer
            # places power from - cannot disagree. Doing it in this function alone was the
            # first attempt and would have shipped two power geographies.
            kt, basis = r["emissions_kt"], r.get("basis", "")
            out.append({"period_id": period_id(fy_end), "fiscal_end_year": fy_end,
                        "category": r["category"], "fuel": r["fuel"],
                        "fuel_detail": r["fuel_detail"], "pollutant": r["pollutant"],
                        "emissions_kt": kt,
                        "uncert_pct": r["uncert_pct"], "ap42_table": r["ap42_table"],
                        "scenario": scenario,
                        "basis": basis})
    return out


power_screening_rows._data = None


# --- coverage --------------------------------------------------------------------

ABSENCES = asset_path(os.path.dirname(OUTPUTS), "data", "air_coverage_absences.csv")
ABSENCE_STATES = ("NE", "IE", "NO", "NA")


def typed_absences():
    """{(module, pollutant|'ALL'): row} from data/air_coverage_absences.csv - the register
    that types every cell the panel does not fill. Validated: closed state vocabulary,
    every gap_id in data/data_gaps.csv, every module one of MODULES."""
    gaps = {r["gap_id"] for r in csv.DictReader(
        # Resolved by its OWN identity, not by ABSENCES' directory: the sector layout
        # sent these two siblings to different purpose folders (metadata and requests),
        # so dirname(ABSENCES) + "data_gaps.csv" names a file that does not exist.
        l for l in io.open(asset_path(os.path.dirname(OUTPUTS), "data", "data_gaps.csv"),
                           encoding="utf-8") if not l.startswith("#"))}
    out = {}
    with io.open(ABSENCES, encoding="utf-8") as f:
        for r in csv.DictReader(l for l in f if not l.startswith("#")):
            if r["sector_id"] not in MODULES:
                raise ValueError("air_coverage_absences: %r is not a module" % r["sector_id"])
            if r["state"] not in ABSENCE_STATES:
                raise ValueError("air_coverage_absences: state %r" % r["state"])
            if r["gap_id"] and r["gap_id"] not in gaps:
                raise ValueError("air_coverage_absences: gap %r is not in data_gaps.csv" % r["gap_id"])
            if not r["note"]:
                raise ValueError("air_coverage_absences: an absence with no reason (%s %s)"
                                 % (r["sector_id"], r["pollutant"]))
            key = (r["sector_id"], r["pollutant"])
            if key in out:
                raise ValueError("air_coverage_absences: duplicate %r" % (key,))
            out[key] = r
    return out


def coverage_rows(atoms):
    """The 630-row matrix: every (period, module, core species) cell typed.

    CONFIGURATION-FREE by declaration: E/NE membership is configuration-invariant
    (the ledger configuration moves residential magnitudes, never which cells are
    estimated), so the matrix reads the reference atoms and applies to both."""
    estimated = {(a["period_id"], a["sector_id"], a["pollutant"])
                 for a in atoms
                 if a["core7"] == "yes" and a["configuration_id"] == conf.REFERENCE}
    absences = typed_absences()
    rows = []
    for fy in YEARS:
        pid = period_id(fy)
        for module in MODULES:
            for pol in CORE7:
                cell = {"period_id": pid, "fiscal_end_year": fy,
                        "sector_id": module, "pollutant": pol,
                        "activity_basis": "", "gap_id": "", "note": ""}
                if (pid, module, pol) in estimated:
                    cell.update(state="E", state_basis="panel-atom",
                                activity_basis=";".join(sorted(
                                    {a["activity_basis"] for a in atoms
                                     if a["configuration_id"] == conf.REFERENCE
                                     and (a["period_id"], a["sector_id"],
                                          a["pollutant"]) == (pid, module, pol)})))
                elif module == "power":
                    screened = pol in ("NOx", "SO2", "CO", "PM2.5")
                    cell.update(
                        state="NE", state_basis="uncontrolled-screening-only",
                        gap_id="air-power-controlled",
                        note=("the screening PAIR (uncontrolled and controlled-case "
                              "scenario ends) prices this species in power_air_"
                              "screening_fy2015_16_fy2023_24.csv, joined per period in "
                              "pakemis_air_absence_screening_by_year.csv; the control "
                              "inventory exists at NEPRA unpublished, so no estimate "
                              "enters the covered panel" if screened else
                              "not in the AP-42 screening set (power VOC is not NMVOC; "
                              "no BC or NH3 factor screened)"))
                elif module == "aviation" and pol == "NMVOC":
                    cell.update(state="NE", state_basis="unharmonised-source-species",
                                gap_id="air-aviation-nmvoc",
                                note="EEDB publishes HC (unspeciated); HC is not "
                                     "renamed NMVOC (dim_pollutant rule) and the "
                                     "methane basis is undocumented")
                elif module == "aviation" and pol == "NH3":
                    cell.update(state="NE", state_basis="no-published-factor",
                                note="no NH3 factor in the aviation chain; absent, "
                                     "not zero")
                elif (module, pol) in absences or (module, "ALL") in absences:
                    a = absences.get((module, pol)) or absences[(module, "ALL")]
                    cell.update(state=a["state"], state_basis=a["state_basis"],
                                gap_id=a["gap_id"], note=a["note"])
                else:
                    raise AssertionError(
                        "uncovered cell %r: no panel atom and no row in %s"
                        % ((pid, module, pol), os.path.relpath(ABSENCES)))
                rows.append(cell)
    return rows


# --- build + closures ------------------------------------------------------------

GHG_ATOMIC = asset_path(OUTPUTS, "pakemis_atomic_annual.csv")


def _guard_supports_active(atoms):
    """Every (period, anchor) must be a stream-period the greenhouse-gas panel gives
    mass - the support-active guard (air spatial Wave A).

    The register-level join (air_join.stream_for) proves a stream EXISTS; it cannot
    prove the stream is ALIVE in the atom's own period, and the difference is exactly
    how 54 furnace-oil atoms sat for a release on a rail-network stream whose
    locomotive fuel was NIL in their six years. An anchor with no mass that period has
    no geography that period, and inheriting the reference shape silently is the
    defect class this module refuses. Raises with the full violation list; there are
    no declared exceptions, and a new one must argue its way in here by name."""
    present = set()
    with io.open(GHG_ATOMIC, encoding="utf-8") as f:
        for r in csv.DictReader(l for l in f if not l.startswith("#")):
            if float(r["emission_native_mass"] or 0.0) != 0.0:
                present.add((r["period_id"], r["source_stream_id"]))
    bad = sorted({(a["period_id"], a["support_anchor_id"]) for a in atoms}
                 - present)
    assert not bad, (
        "air atoms anchoring stream-periods the greenhouse-gas panel gives no mass "
        "(dead geography, the rail furnace-oil class):\n  "
        + "\n  ".join("%s %s" % b for b in bad[:12])
        + ("\n  ... and %d more" % (len(bad) - 12) if len(bad) > 12 else ""))


def build():
    atoms = []
    for _sector, fn in SECTOR_ATOMS:
        for fy in YEARS:
            atoms.extend(fn(fy))
    _guard_supports_active(atoms)
    # the rollup materialises BOTH configurations in full: the atoms table carries the
    # configuration-invariant sectors once under the reference id (the greenhouse-gas
    # annual product's own S convention), and each configuration's rollup takes the
    # reference atoms for every sector except where that configuration carries its own
    own_sectors = defaultdict(set)          # configuration -> sectors it re-runs
    for a in atoms:
        own_sectors[a["configuration_id"]].add(a["sector_id"])
    rollup = defaultdict(float)
    for cfg in conf.AIR_ALL:
        for a in atoms:
            if a["core7"] != "yes":
                continue
            use = (a["configuration_id"] == cfg
                   or (a["configuration_id"] == conf.REFERENCE
                       and a["sector_id"] not in own_sectors[cfg]))
            if not use:
                continue
            rollup[(a["period_id"], cfg, a["sector_id"], a["category"],
                    a["pollutant"])] += a["emissions_Gg"]
    rollup_rows = [{"period_id": k[0], "fiscal_end_year": 2000 + int(k[0][-2:]),
                    "configuration_id": k[1], "sector_id": k[2], "category": k[3],
                    "pollutant": k[4], "emissions_Gg": v, "coverage_scope": SCOPE}
                   for k, v in sorted(rollup.items())]
    power = []
    for fy in YEARS:
        power.extend(power_screening_rows(fy))
    return atoms, rollup_rows, coverage_rows(atoms), power


def check(atoms, rollup_rows, coverage, power):
    # 1. each configuration's rollup is exactly its own core atoms plus the
    #    configuration-invariant reference atoms, per (period, sector, pollutant)
    own_sectors = defaultdict(set)
    for a in atoms:
        own_sectors[a["configuration_id"]].add(a["sector_id"])
    want = defaultdict(float)
    for cfg in conf.AIR_ALL:
        for a in atoms:
            if a["core7"] != "yes":
                continue
            if (a["configuration_id"] == cfg
                    or (a["configuration_id"] == conf.REFERENCE
                        and a["sector_id"] not in own_sectors[cfg])):
                want[(a["period_id"], cfg, a["sector_id"],
                      a["pollutant"])] += a["emissions_Gg"]
    got = defaultdict(float)
    for r in rollup_rows:
        got[(r["period_id"], r["configuration_id"], r["sector_id"],
             r["pollutant"])] += r["emissions_Gg"]
    assert set(want) == set(got)
    for k, v in want.items():
        assert abs(got[k] - v) < 1e-9, k
    # 1b. the two configurations differ in residential alone, and only through dung:
    #     every non-residential (period, sector, pollutant) total is identical
    for (pid, cfg, sec, pol), v in want.items():
        if cfg == conf.LEDGER_SERIES and sec != "residential":
            assert abs(v - want[(pid, conf.REFERENCE, sec, pol)]) < 1e-12, (pid, sec, pol)
    # 2. the coverage matrix is exactly 630 typed cells and every E has mass rows
    assert len(coverage) == 9 * len(MODULES) * len(CORE7), len(coverage)
    for c in coverage:
        assert c["state"] in ("E", "NE", "IE", "NO", "NA"), c
        key = (c["period_id"], conf.REFERENCE, c["sector_id"], c["pollutant"])
        if c["state"] == "E":
            assert key in want, key
        else:
            assert key not in want, ("a %s cell has panel mass" % c["state"], key)
    # 3. the reference-year slice of the panel equals the shipped single-year layers
    #    (asserted in tests/test_air_annual.py against the CSVs, half-ulp absolute)
    # 4. every atom named a real stream (stream_for already raised otherwise) and
    #    every supplemental species is declared in dim_pollutant (the build fails
    #    closed there too)
    assert power, "the screening scenario is empty"
    assert not [r for r in power if r["category"].startswith("Captive")], \
        "captive rows in the power screening: captive is priced once, in the industry atoms"
    # 5. each register module (industry, ippu, fugitives) is E for exactly the core species
    #    its classes price, every period
    from pkinv.sectors.industry import air_pollutants as ind
    for module in ind.MODULES:
        covered = ind.covered_core_species(module) & set(CORE7)
        for c in coverage:
            if c["sector_id"] == module:
                assert (c["state"] == "E") == (c["pollutant"] in covered), c


def _write(path, fields, rows, fmt):
    with io.open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fields, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow(fmt(r))


def main():
    _atom.index = air_join.stream_index()
    atoms, rollup_rows, coverage, power = build()
    check(atoms, rollup_rows, coverage, power)
    _write(ATOMS_OUT, ATOM_FIELDS, atoms,
           lambda r: dict(r, emissions_Gg="%.6f" % r["emissions_Gg"]))
    _write(ROLLUP_OUT, ROLLUP_FIELDS, rollup_rows,
           lambda r: dict(r, emissions_Gg="%.6f" % r["emissions_Gg"]))
    _write(COVERAGE_OUT, COVERAGE_FIELDS, coverage, lambda r: r)
    _write(POWER_OUT, POWER_FIELDS, power,
           lambda r: dict(r, emissions_kt="%.6f" % r["emissions_kt"],
                          uncert_pct="%.1f" % r["uncert_pct"]))
    n_e = sum(1 for c in coverage if c["state"] == "E")
    print("air panel: %d atoms, %d rollup rows over %d periods; coverage %d cells "
          "(%d E, %d NE); screening %d rows"
          % (len(atoms), len(rollup_rows), len(YEARS), len(coverage), n_e,
             sum(1 for c in coverage if c["state"] == "NE"), len(power)))


_atom.index = None

if __name__ == "__main__":
    main()
