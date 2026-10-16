"""Cross-sector national rollup.

Sums every registered sector into outputs/national_all_sectors.csv - one row per sector
plus a TOTAL. Until this existed the all-sector total lived only in commit messages.

Two conventions, both deliberate:

MIXED VINTAGES. Each sector is reported for the latest year its sources support, so the
TOTAL row is a sum across reference years, not a single-year national total. The note
column says so on every run rather than leaving the caveat in a doc nobody reads.

MEMO ITEMS ARE NOT HERE AT ALL. International aviation bunkers and biogenic CO2 are
excluded from sector totals by construction and are reported in each sector's own outputs.
Writing them here with a blank column would invite someone to fill it in; leaving them out
and saying where they live does not. Off-road machinery diesel used to be on that list and
is not any more - it is a reported 1A4c category now, not a memo.

Usage:  python3 -m pkinv.report.national_rollup
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import csv
import os

from pkinv.core import period, registry
from pkinv.core.uncertainty import combine_sum
from pkinv.paths import DATA, OUTPUTS

MEMO = ("Memo items (international bunkers, off-road machinery diesel, biogenic CO2) are "
        "excluded by construction and live in each sector's own outputs.")

# What the TOTAL row's note says about vintage is DERIVED from the rows, not asserted. It
# asserted for one round too long: after the harmonisation round put every sector on
# FY2023-24 the note still opened "Sum across reference years, not a single-year total",
# in the same file, on the same row, as a period_label reading FY2023-24. A caveat that
# outlives the thing it warns about teaches a reader to discount the ones that are true.
MIXED_CAVEAT = ("Sum across reference years, not a single-year total: each sector reports "
                "the latest year its sources support. ") + MEMO
COMMON_CAVEAT = ("Every sector on one reporting period, so this is a single-period national "
                 "total. What a common period cost is declared per sector: some activity is "
                 "an enumeration rather than a flow over it, and some shape is borrowed from "
                 "a neighbouring period. ") + MEMO

# The one structural configuration that changes the national total. Residential dung is
# either read from the household survey's reported cake (demand, "survey" = S) or taken
# as everything agriculture's nitrogen ledger diverts (supply, "ledger" = L); the two
# are about a factor of five apart.
#
# THE BASELINE IS S SINCE rc67. Through rc66 it was L, "because it closes with
# agriculture's included-elsewhere booking". That closure is about the SUPPLY: it says
# the diverted mass exists, not that households burn it. The residential row is meant to
# measure household combustion, the survey observes household combustion, and nothing
# held supports a fivefold survey under-count. L is published beside it as a second
# national result: a destination assumption for the whole diverted supply.
#
# Until this constant existed the choice was a defaulted keyword argument three call
# levels down, and no national output recorded which one it had used - so a headline
# could be, and was, quoted without its configuration.
from pkinv.core import configurations as _conf
from pkinv.activity.store import read_rows
BASELINE = _conf.REFERENCE_DUNG_BASIS
ALTERNATIVE = _conf.ALTERNATIVE_DUNG_BASIS
SCENARIO_ID = _conf.REFERENCE
CONFIGURATIONS = {"ledger": "L", "survey": "S"}
CONFIG_NOTE = {
    "ledger": "configuration L (ledger): ALL the dung agriculture's nitrogen ledger "
              "diverts burned in households (supply basis) - a destination assumption, "
              "the baseline of every release through rc66",
    "survey": "configuration S (household demand), the baseline since rc67: residential "
              "dung read from the HIES rounds' reported cake; the rest of the diverted "
              "supply has no observed destination and is outside the total "
              "- see outputs/residential_dung_ledger_2024.csv for the fate account and "
              "outputs/national_dung_variants.csv for what each destination is worth",
}


def _build(sector, dung_basis):
    """Components for one sector under a named configuration.

    Only residential responds to the configuration; every other module takes no such
    argument, so this passes it exactly where it is accepted rather than widening every
    sector's signature for one sector's fork.
    """
    data = sector.load_data()
    if sector.NAME == "residential":
        return sector.build_components(data, dung_basis=dung_basis)
    return sector.build_components(data)


def rollup(dung_basis=BASELINE):
    """One dict per registered sector, in registry order, plus a TOTAL row.

    uncert_pct is IPCC Approach 1 (error propagation) over the sector's own components,
    computed from the rows already in hand. The fuller Approach-2 treatment, including
    what happens when the shared IPCC fuel-carbon factors are allowed to correlate across
    sectors, is pkinv.report.uncertainty_all.

    Every row records the configuration it was built under. A national number that does
    not say which configuration produced it is not a result, it is an ambiguity.
    """
    rows, all_terms = [], []
    config = CONFIGURATIONS[dung_basis]
    for s in registry.all_sectors():
        comps = _build(s, dung_basis)
        terms = [(c["co2e_Mt_AR5"], c["uncert_pct"], c.get("corr_group")) for c in comps]
        all_terms.extend(terms)
        _value, uncert = combine_sum(terms)
        # The integer year means DIFFERENT THINGS in different rows - power and aviation
        # number a fiscal year by the calendar year it opens in, everyone else by the year
        # it closes in - which is why the manuscript's table dropped the column entirely.
        # The released CSV keeps it, because filenames and sector code are built on it, and
        # carries the convention beside it so the integer can be decoded instead of guessed.
        rows.append({"sector": s.NAME, "year": s.YEAR,
                     "year_convention": s.YEAR_CONVENTION, "configuration": config,
                     "period_start": s.PERIOD_START.isoformat(),
                     "period_end": s.PERIOD_END.isoformat(),
                     "period_label": period.label(s.PERIOD_START, s.PERIOD_END),
                     "co2e_Mt_AR5": sum(c["co2e_Mt_AR5"] for c in comps),
                     "co2e_Mt_AR6": sum(c["co2e_Mt_AR6"] for c in comps),
                     "uncert_pct": uncert,
                     "note": CONFIG_NOTE[dung_basis] if s.NAME == "residential" else ""})
    total5 = sum(r["co2e_Mt_AR5"] for r in rows)
    total6 = sum(r["co2e_Mt_AR6"] for r in rows)
    for r in rows:
        r["share_pct"] = 100.0 * r["co2e_Mt_AR5"] / total5
    _v, total_uncert = combine_sum(all_terms)
    # The TOTAL row's period is the SPAN THE SECTORS ACTUALLY COVER, earliest start to
    # latest end, so a reader can see at a glance how far from a single-year total this is.
    # It is deliberately not the reference period: writing FY2023-24 here while three sectors
    # sit outside it would be the same false precision the integer year was hiding.
    starts = [s.PERIOD_START for s in registry.all_sectors()]
    ends = [s.PERIOD_END for s in registry.all_sectors()]
    common = {(r["period_start"], r["period_end"]) for r in rows}
    rows.append({"sector": "TOTAL",
                 # "mixed" was true of the year INTEGER and false of the period. It stayed
                 # after the harmonisation round put every sector on one span, so the row
                 # said "mixed" and "FY2023-24" side by side.
                 "year": (rows[0]["period_label"] if len(common) == 1 else "mixed"),
                 "year_convention": ("one period, see period_label" if len(common) == 1
                                     else "mixed"),
                 "configuration": config,
                 "period_start": min(starts).isoformat(), "period_end": max(ends).isoformat(),
                 "period_label": (period.label(min(starts), max(ends)) if len(common) == 1
                                  else "spans %s to %s" % (period.label(*period.from_year(
                                      min(starts).year, "fiscal-start")),
                                      period.label(*period.from_year(
                                          max(ends).year - 1, "fiscal-start")))),
                 "co2e_Mt_AR5": total5, "co2e_Mt_AR6": total6,
                 "uncert_pct": total_uncert, "share_pct": 100.0,
                 "note": (COMMON_CAVEAT if len(common) == 1 else MIXED_CAVEAT)
                          + " " + CONFIG_NOTE[dung_basis]})
    return rows


def benchmark_comparison(prebuilt=None):
    """Resolve data/benchmarks.csv against every registered sector, not just agriculture.

    sectors/agriculture/run_inventory.py writes outputs/benchmark_comparison.csv, but it
    only knows agriculture's six categories - so an EDGAR row for power or waste came out
    "n/a" there, and a row whose engine_category read TOTAL was divided into the
    AGRICULTURE total and printed a ratio of 12.61. This resolves by category first, then
    by sector name, then TOTAL, so every benchmark lands against the thing it measures.

    Rows whose engine_category is "(not estimated)" remain explicitly unresolved.
    Estimated industrial combustion is compared at its admitted source boundary;
    the comparator difference is not a missing-emissions quantity.

    THE ENGINE SIDE IS RESOLVED IN THE ROW'S OWN GWP. Until rc10 this emitted the AR5
    engine value unconditionally, so the seven Climate TRACE rows - published under AR6 -
    were compared cross-GWP without a flag: enteric CH4 differs by 9 percent between the
    two bases, which is real disagreement invented by the comparison itself. A row whose
    gwp is "native CO2" gets no engine value at all: the engine carries CO2e, and dividing
    a pure-CO2 comparator into it would manufacture the same artefact the other way.
    """
    components, categories, sector_of = prebuilt or registry.build_all()
    engine = {}
    for basis in ("AR5", "AR6"):
        col = "co2e_Mt_%s" % basis
        e = {}
        for category in categories:
            e[category] = sum(c[col] for c in components if c["category"] == category)
        for sector in registry.all_sectors():
            e[sector.NAME] = sum(c[col] for c in components
                                 if c["_sector"] == sector.NAME)
        # "TOTAL" means AGRICULTURE's total, not the national one. That convention
        # predates the national layer - every TOTAL row in benchmarks.csv is a FAOSTAT,
        # EDGAR or Climate TRACE figure for the agriculture sector - and reading it as
        # the national total silently compared 233.3 Mt of agriculture against 422.25 Mt
        # of everything and called the 1.81x ratio acceptable.
        e["TOTAL"] = e["agriculture"]
        e["NATIONAL"] = sum(c[col] for c in components)
        # EDGAR publishes 1A2 as one number; this inventory splits the same category
        # across two sectors - captive self-generation lives in power, process heat and
        # boilers in industry - so a benchmark pointed at either one alone understates
        # the compared activity boundary. The resulting difference can reflect
        # activity, factors, coverage and fiscal/calendar period choices.
        e["1A2 (all estimated)"] = sum(
            v for k, v in e.items() if k.endswith("(1A2)"))
        engine[basis] = e

    out = []
    for b in _activity_rows(asset_path(DATA, "benchmarks.csv"), comments=False):
        value = b["value_Mt_co2e"].strip()
        gwp = (b.get("gwp") or "AR5").strip()
        ev = engine.get(gwp, {}).get(b["engine_category"])
        permitted = (b.get("ratio_permitted", "yes") or "yes").strip().lower() == "yes"
        protocol = [b.get("benchmark_period", ""), b.get("engine_boundary", ""),
                    b.get("benchmark_boundary", ""), b.get("boundary_match", ""),
                    b.get("gas_scope", ""), b.get("bunker_treatment", ""),
                    b.get("biogenic_treatment", ""), b.get("comparison_role", "")]
        head = [b["source"], b["engine_category"], b["scope_detail"], b["year"],
                gwp, b.get("engine_period", "")]
        if ev is None or not value:
            # An unresolved row - a category the engine does not compute, like the
            # red-flagged CRT ammonia row, or a native-CO2 comparator no CO2e value
            # may face - still carries the register's flag exactly as below.
            out.append(head + protocol
                       + [value or "n/a", "n/a",
                          "n/a" if permitted else "",
                          "n/a" if permitted else "not comparable", b["note"]])
            continue
        bench = float(value)
        ratio = ev / bench if bench else 0.0
        # A RATIO IS NOT ALWAYS ADMISSIBLE. Two rows can be arithmetically divisible and
        # still mean different things: the engine's transport figure is the MODULE while
        # EDGAR's is a different set of modes on a different year, and cement calcination
        # against the whole of IPPU is a coverage statement rather than agreement. Where
        # the register says the boundaries do not support a ratio, the column is blank and
        # the row is read under its declared role instead.
        out.append(head + protocol
                   + [round(bench, 2), round(ev, 2),
                      round(ratio, 2) if permitted else "",
                      ("YES" if 0.5 <= ratio <= 2.0 else "REVIEW") if permitted
                      else "not comparable",
                      b["note"]])
    return out


# EDGAR's own decomposition of the 514.33 Mt national comparator. The magnitudes are EDGAR's,
# read off the same booklet row the NATIONAL benchmark is built from. WHAT IS ESTIMATED
# AGAINST EACH DOMAIN IS NO LONGER DECLARED HERE - see benchmark_scope_coverage().
#
# WHY THIS IS A SEPARATE METRIC FROM THE MAGNITUDE RATIO. "87% coverage" is a magnitude ratio,
# and a magnitude ratio conflates two different things: source domains this inventory does not
# estimate at all, and domains it does estimate where the two disagree in either direction -
# waste sits at 143% of EDGAR and agriculture at 86%. Netting those against each other produces
# a single number that reads as completeness and is not. A domain estimated and disagreeing is
# a validation question; a domain not estimated is a scope question; different work answers
# them.
EDGAR_DOMAINS = [
    ("Agriculture", 261.24),
    ("Power industry", 56.80),
    ("Transport", 48.76),
    ("Industrial combustion (1A2)", 43.98),
    ("Buildings", 31.42),
    ("Processes (IPPU)", 27.38),
    ("Waste", 27.21),
    ("Fuel exploitation (1B)", 17.54),
]

EDGAR_NATIONAL = 514.33


def _edgar_domain_codes():
    """{EDGAR domain: [IPCC codes]}, from data/edgar_domain_map.csv."""
    out = {}
    path = asset_path(DATA, "edgar_domain_map.csv")
    for row in _activity_rows(path, comments=True):
        out.setdefault(row["edgar_domain"], []).append(row["ipcc_code"])
    return out


def _completeness_keys():
    """{IPCC code: set of notation keys}, from the generated completeness matrix."""
    out = {}
    path = asset_path(OUTPUTS, "completeness.csv")
    if not os.path.exists(path):
        raise IOError("outputs/completeness.csv is missing: run "
                      "python3 -m pkinv.report.completeness first")
    for row in _activity_rows(path, comments=False):
        out.setdefault((row.get("code") or "").strip(), set()).add(row["notation_key"])
    return out


def benchmark_scope_coverage(prebuilt=None):
    """Three separate numbers where the manuscript had one ratio, the third one DERIVED.

    Returns (rows, summary).

      magnitude_ratio        - the familiar one: this inventory's total over EDGAR's. It says
                               how big, not how complete, and it nets overshoot in one domain
                               against absence in another.
      fully_represented      - the share of EDGAR's source domain, by EDGAR's magnitude, in
                               which EVERY IPCC category mapped to it is estimated (E),
                               included elsewhere (IE) or does not occur (NO).
      partially_represented  - the share in which at least one mapped category is NE, with
                               those categories named per domain.
      absent                 - the share with no estimate at all.

    THE WORD "WHOLE" IS RETIRED, AND SO IS THE DECLARED CLASSIFICATION IT CAME FROM. The first
    version of this function declared five domains estimated whole and three partial. That was
    a completeness claim written from memory, and the completeness matrix in the same
    repository contradicted it: transport carries domestic navigation and mobile
    air-conditioning as NE, fugitives carries transmission, distribution and solid fuels,
    waste carries industrial wastewater, incineration and biological treatment. The metric
    existed to stop a magnitude ratio from reading as completeness and was itself an
    unchecked completeness claim.

    The classification is now computed from the notation keys, through
    data/edgar_domain_map.csv. It is deliberately strict: ONE unestimated category makes a
    domain partial, however small, which is why the per-domain NE list is reported beside the
    band. A reader who wants to weigh a domain does it from the named categories, not from a
    band that quietly absorbed them.
    """
    components, _categories, _sector_of = prebuilt or registry.build_all()
    engine_total = sum(c["co2e_Mt_AR5"] for c in components)
    declared = sum(mt for _d, mt in EDGAR_DOMAINS)
    if abs(declared - EDGAR_NATIONAL) > 0.05:
        raise ValueError("the EDGAR domain decomposition sums to %.2f, not the %.2f "
                         "national comparator it is meant to decompose"
                         % (declared, EDGAR_NATIONAL))
    mapped = _edgar_domain_codes()
    keys = _completeness_keys()
    unmapped = sorted(set(mapped) - {d for d, _mt in EDGAR_DOMAINS})
    if unmapped:
        raise ValueError("data/edgar_domain_map.csv names domains that are not in the "
                         "national comparator: %s" % ", ".join(unmapped))

    bands = {"represented": 0.0, "partial": 0.0, "absent": 0.0}
    rows = []
    for domain, mt in EDGAR_DOMAINS:
        codes = mapped.get(domain)
        if not codes:
            raise ValueError("no IPCC codes mapped to EDGAR domain %r; the scope metric "
                             "would silently score it as complete" % domain)
        missing_from_matrix = [c for c in codes if c not in keys]
        if missing_from_matrix:
            raise ValueError("these codes are mapped to %s but absent from the completeness "
                             "matrix, so their status is unknown rather than complete: %s"
                             % (domain, ", ".join(missing_from_matrix)))
        # A code can carry both E and NE rows - 1.A.2 is estimated for gas and liquids and
        # not for solid fuels - so "estimated" and "has an NE" are not complements. Counting
        # them as complements made industrial combustion read "0 of 1 estimated", which is
        # the opposite of true.
        estimated = [c for c in codes if "E" in keys[c]]
        not_estimated = sorted(c for c in codes if "NE" in keys[c])
        partly = sorted(set(estimated) & set(not_estimated))
        # A code carrying NEITHER is not a silent gap - it is typed NA or NO, an absence
        # this inventory has RESOLVED rather than one it owes. Soda ash is the case that
        # exposed it: 2.B.7 is NA because IPCC Vol.3 s3.8.3.1 allocates Solvay-process
        # carbon to Energy, so it cannot be an IPPU shortfall. Left uncounted, the row read
        # "4 of 6 codes estimated" beside a single named NE and a reader subtracted two.
        resolved = sorted(c for c in codes
                          if c not in estimated and c not in not_estimated)
        klass = ("absent" if not estimated
                 else "partial" if not_estimated
                 else "represented")
        bands[klass] += mt
        rows.append([domain, round(mt, 2), round(mt / EDGAR_NATIONAL * 100.0, 1), klass,
                     "%d of %d codes estimated%s%s"
                     % (len(estimated), len(set(codes)),
                        ", %d only in part" % len(partly) if partly else "",
                        ", %d not applicable (%s)" % (len(resolved), "; ".join(resolved))
                        if resolved else ""),
                     "; ".join(not_estimated)])
    summary = {
        "engine_Mt": engine_total,
        "edgar_Mt": EDGAR_NATIONAL,
        "magnitude_ratio_pct": engine_total / EDGAR_NATIONAL * 100.0,
        "fully_represented_pct": bands["represented"] / EDGAR_NATIONAL * 100.0,
        "partially_represented_pct": bands["partial"] / EDGAR_NATIONAL * 100.0,
        "absent_pct": bands["absent"] / EDGAR_NATIONAL * 100.0,
    }
    return rows, summary


# ONE axis->family mapping for every national product that carries families (the
# bridge writer, the axis register, and - keyed by configuration - the
# configurations file's FAMILIES roles). Two dicts drifted for three rounds; the
# ninth review's axis-register demand is what finally merged them.
AXIS_FAMILIES = {
    "power coal energy basis": "power_grid_control",
    "power energy convention": "power_grid_control",
    "power scope": "power_grid_control",
    "fugitive practice": "fugitives_structural_envelope",
    "post-meter feedstock scope": "fugitives_structural_envelope",
}


def scenario_registry():
    """REF_2023_24, axis by axis, from data/scenarios.csv.

    The release used to record its structural configuration as the letter L. L names ONE axis
    - which reading of the dung evidence the residential sector takes - and the national total
    embeds nine. A reader given "configuration L" could not reconstruct the baseline, and a
    reader given the +/-11 percent interval could not tell that the interval excludes every one
    of these. The letter survives as the dung axis's setting; the registry is the scenario.
    """
    path = asset_path(DATA, "scenarios.csv")
    return read_rows(path)


def structural_bridge(prebuilt=None):
    """The deterministic effect of each named structural alternative on the national total.

    Each row is `national total under REF_2023_24` minus `national total with one axis moved`,
    read from the sector output the registry points at. It is NOT a probability distribution
    and the alternatives are not independent draws: two of the power axes describe the same
    coal energy in different ways and cannot both be taken at once. It is a bridge, and its
    purpose is to show what the conditional parametric interval leaves out.
    """
    components, _categories, _sector_of = prebuilt or registry.build_all()
    baseline = sum(c["co2e_Mt_AR5"] for c in components)
    module_totals = {}
    for c in components:
        module_totals[c["_sector"]] = module_totals.get(c["_sector"], 0.0) + c["co2e_Mt_AR5"]

    rows = []
    for entry in scenario_registry():
        out_name, row_key = entry["alternative_output"], entry["alternative_row"]
        if not out_name or not row_key:
            rows.append({"axis": entry["axis"], "module": entry["module"],
                         "setting": entry["setting"], "alternative": entry["alternative"],
                         "alternative_Mt": None, "national_delta_Mt": None,
                         "note": entry["note"] + "; no published alternative row"})
            continue
        value = _scenario_value(out_name, row_key)
        # The baseline this alternative replaces is the SAME TABLE'S reference row where it has
        # one, and the affected category's total otherwise. Using the module total instead
        # priced the power coal fork at 25 Mt rather than 19.4, because the power scenario
        # table is scoped to grid generation and the module also carries captive gas - the
        # alternative was being differenced against a magnitude it does not cover.
        reference = _scenario_reference(out_name)
        base = (reference if reference is not None
                else _category_total(components, out_name, row_key))
        delta = value - base
        rows.append({"axis": entry["axis"], "module": entry["module"],
                     "setting": entry["setting"], "alternative": entry["alternative"],
                     "alternative_Mt": value,
                     "national_delta_Mt": delta,
                     "note": entry["note"]})
    return baseline, rows


def _scenario_value(out_name, row_key):
    """The deterministic Mt of one alternative, from whichever column its output uses."""
    path = asset_path(OUTPUTS, out_name)
    for row in _activity_rows(path, comments=True):
        key = (row.get("category") or row.get("scenario")
               or row.get("structural_scenario") or row.get("configuration")
               or row.get("method") or "")
        if key.strip() == row_key:
            for col in ("co2e_Mt_AR5", "mt_co2e_ar5", "deterministic_Mt",
                        "deterministic_mt_co2", "deterministic_Mt_co2e",
                        "process_co2_mt", "deterministic"):
                if row.get(col):
                    return float(row[col])
    raise KeyError((out_name, row_key))


def _scenario_reference(out_name):
    """The reference row of a scenario table, if it has one. That is the magnitude the
    alternatives in the same table are alternatives TO, whatever scope the table covers."""
    path = asset_path(OUTPUTS, out_name)
    for row in _activity_rows(path, comments=True):
        key = (row.get("scenario") or row.get("structural_scenario")
               or row.get("configuration") or "").strip()
        if key == "reference":
            for col in ("mt_co2e_ar5", "deterministic_Mt", "co2e_Mt_AR5",
                        "deterministic"):
                if row.get(col):
                    return float(row[col])
    return None


def _category_total(components, out_name, row_key):
    """The baseline magnitude the alternative replaces, for a category-scoped alternative."""
    which = {
        "Sensitivity: dung configuration L (all diverted dung)": "Residential fuel combustion",
        "Sensitivity: wastewater on the river-discharge MCF (category total)":
            "Domestic wastewater",
        "Sensitivity: gas at 900 Btu/scf": "Industrial fuel combustion (1A2)",
        "diagnostic model f=0.95 (all-Portland)": "Cement production",
        "Diagnostic model f=0.75": "Cement production",
        "Sensitivity: including military and general aviation scope": "Domestic aviation",
        "Sensitivity: including military/government scope": "Domestic aviation",
        "Sensitivity: including general aviation 100LL": "Domestic aviation",
        "Sensitivity: including unresolved government JP-1": "Domestic aviation",
        # rc47 Wave 0: brick and captive retired (double counts of the activated
        # reference mass); cement re-priced net of the measured series.
        "Sensitivity: cement kiln fuel at the transferred-intensity model "
        "(excess over measured)":
            "Industrial fuel combustion (1A2)",
        "Sensitivity: including process bagasse (all-cane ceiling)":
            "Industrial fuel combustion (1A2)",
        "Sensitivity: route-resolved ledger reading": "Domestic aviation",
    }[row_key]
    return sum(c["co2e_Mt_AR5"] for c in components if c["category"] == which)


def _write_rollup(path, rows):
    """Every row carries the whole scenario AND the one axis the letter names.

    `configuration` used to travel alone, and readers -- including this project's own
    manuscript -- took the letter for the thing that produced the number. L names one axis of
    the ten in data/scenarios.csv. A row that carries only the letter cannot be traced back to
    the run that made it, so both are written: the scenario, and which reading of the dung
    evidence this rollup took.
    """
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        # row_kind is FIRST and typed, because the alternative was worse: this table holds
        # a TOTAL row in the same `sector` column as its ten parts, so summing the column
        # double-counts, and the only thing preventing that was every reader remembering
        # to filter a magic string out of free text. About a hundred and sixty call sites
        # do exactly that by hand. The row stays where a hundred and sixty readers expect
        # it - moving it moves no number and breaks all of them - but a reader can now ask
        # what a row IS instead of pattern-matching its name. The parts alone, keyed on
        # all five axes, are outputs/pakemis_atomic_annual.csv.
        w.writerow(["row_kind", "sector", "year", "year_convention", "period_start",
                    "period_end", "period_label", "scenario_id", "residential_dung_axis",
                    "co2e_Mt_AR5", "co2e_Mt_AR6",
                    "uncert_pct_95", "share_pct", "note"])
        for r in rows:
            w.writerow(["national_total" if r["sector"] == "TOTAL" else "sector",
                        r["sector"], r["year"], r["year_convention"],
                        r["period_start"], r["period_end"],
                        r["period_label"], SCENARIO_ID, r["configuration"],
                        round(r["co2e_Mt_AR5"], 5), round(r["co2e_Mt_AR6"], 5),
                        round(r["uncert_pct"], 1), round(r["share_pct"], 2), r["note"]])


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    rows = rollup()
    path = asset_path(OUTPUTS, "national_all_sectors.csv")
    _write_rollup(path, rows)

    # The second national result, computed rather than inferred by subtraction:
    # configuration L gets its own rollup through the same code path - including its own
    # Approach-1 propagation, which a subtraction could not have given.
    alt = rollup(ALTERNATIVE)
    _write_rollup(asset_path(OUTPUTS, "national_all_sectors_ledger.csv"), alt)

    baseline, bridge = structural_bridge()
    with open(asset_path(OUTPUTS, "national_structural_bridge.csv"), "w",
              newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        # Three of the power axes are one FAMILY - competing definitions of the same
        # grid control (rc11; the seventh review's demand that national products carry
        # the family as a family): the coal-energy and TOE-convention axes describe
        # the same coal energy two ways, and the scope axis moves the boundary. They
        # cannot be combined, and the family_id column says so machine-readably where
        # the figure caption used to say it in prose alone.
        bridge_families = AXIS_FAMILIES
        w.writerow(["axis", "module", "baseline_setting", "alternative",
                    "alternative_Mt_co2e", "national_delta_Mt_co2e", "national_total_Mt_co2e",
                    "family_id", "note"])
        for r in bridge:
            w.writerow([r["axis"], r["module"], r["setting"], r["alternative"],
                        "" if r["alternative_Mt"] is None else round(r["alternative_Mt"], 3),
                        "" if r["national_delta_Mt"] is None
                        else round(r["national_delta_Mt"], 3),
                        "" if r["national_delta_Mt"] is None
                        else round(baseline + r["national_delta_Mt"], 3),
                        bridge_families.get(r["axis"], ""),
                        r["note"]])

    scope_rows, scope = benchmark_scope_coverage()
    with open(asset_path(OUTPUTS, "national_benchmark_scope_coverage.csv"), "w",
              newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["edgar_domain", "edgar_Mt_co2e", "share_of_edgar_pct",
                    "coverage_class", "categories_estimated", "not_estimated_here"])
        w.writerows(scope_rows)
        w.writerow(["SUMMARY: magnitude ratio", round(scope["engine_Mt"], 2),
                    round(scope["magnitude_ratio_pct"], 1), "magnitude", "",
                    "this inventory over EDGAR's total; not a completeness measure"])
        w.writerow(["SUMMARY: scope fully represented", "",
                    round(scope["fully_represented_pct"], 1), "scope", "",
                    "share of EDGAR's magnitude in domains where every mapped IPCC "
                    "category is E, IE or NO"])
        w.writerow(["SUMMARY: scope partially represented", "",
                    round(scope["partially_represented_pct"], 1), "scope", "",
                    "share in domains carrying at least one NE category, named per row"])
        w.writerow(["SUMMARY: scope absent", "", round(scope["absent_pct"], 1),
                    "scope", "", "share with no estimate at all"])

    bench = benchmark_comparison()
    with open(asset_path(OUTPUTS, "national_benchmark_comparison.csv"), "w",
              newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["source", "engine_category", "scope_detail", "year",
                    "gwp", "engine_period",
                    "benchmark_period", "engine_boundary", "benchmark_boundary",
                    "boundary_match", "gas_scope", "bunker_treatment",
                    "biogenic_treatment", "comparison_role",
                    "benchmark_Mt_co2e", "engine_Mt_co2e", "ratio_engine_over_benchmark",
                    "within_0.5_2.0x", "note"])
        w.writerows(bench)

    total, alt_total = rows[-1], alt[-1]
    print("National all-sector total: %.2f Mt CO2e (AR5) +/- %.0f%%, %.2f Mt (AR6)"
          "   [baseline configuration %s]"
          % (total["co2e_Mt_AR5"], total["uncert_pct"], total["co2e_Mt_AR6"],
             CONFIGURATIONS[BASELINE]))
    print("  second configuration %s: %.2f Mt CO2e (AR5), %.2f Mt (AR6)  "
          "-> national_all_sectors_ledger.csv"
          % (CONFIGURATIONS[ALTERNATIVE], alt_total["co2e_Mt_AR5"],
             alt_total["co2e_Mt_AR6"]))
    for r in rows[:-1]:
        print("  %-14s %-6s %8.2f Mt  +/- %5.1f%%  %5.1f%%"
              % (r["sector"], r["year"], r["co2e_Mt_AR5"], r["uncert_pct"], r["share_pct"]))
    print("  uncertainty is IPCC Approach 1; Approach 2 and the correlated-factor case are")
    print("  in outputs/national_uncertainty_montecarlo.csv")
    # positional indices into benchmark_comparison() rows: 14 benchmark_Mt, 15 engine_Mt,
    # 16 ratio, 17 within-flag. The previous pair (r[5], r[7]) dated from before the
    # boundary columns and had counted every row resolved and none REVIEW since they landed.
    resolved = [r for r in bench if r[15] != "n/a"]
    review = [r for r in resolved if r[17] == "REVIEW"]
    print("  benchmarks: %d of %d rows resolve against an engine category; %d flagged REVIEW"
          % (len(resolved), len(bench), len(review)))
    for r in review:
        print("    %-34s engine %7.2f vs %-7s %.2f  (%.2fx)"
              % (r[1][:34], r[15], r[0], r[14], r[16]))
    print("  (%s)" % (COMMON_CAVEAT if len({(r["period_start"], r["period_end"])
                                           for r in rows if r["sector"] != "TOTAL"}) == 1
                       else MIXED_CAVEAT))


if __name__ == "__main__":
    main()
