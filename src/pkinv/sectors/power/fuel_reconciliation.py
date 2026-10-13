"""The coal account over nine fiscal years, at the grain an outsider can re-derive it.

WHY THIS PRODUCT EXISTS. The 23rd review's second item: the abstract says coal energy comes
from the stations' own metered coal at rank-default calorific values, which is a real change,
and the detailed methods still described the account it replaced. A reviewer could not
reconstruct the revised nine-year series - above all for the years before the plant ledger
begins. The campaign had built most of it (research_campaign/energy/plant_fuel_year.csv, five
years, 39 rows) and nothing shipped read it, which is the same gap the 22nd review named.

WHAT A ROW CARRIES, and every column answers something the review asked for:

  the source          edition and table, per row, so a number can be looked up rather than
                      taken. Two editions supply the panel: NEPRA SoIR 2024 Table 21 for the
                      ledger years and SoIR 2018/2023 for the back years.
  the mass            with its RANK and the evidence for that rank, and - the distinction
                      the review asked be made explicit - `quantity_class`, which separates
                      a METERED quantity from a DERIVED one. A derived mass is generation
                      times a printed intensity; it is not a measurement and is not labelled
                      as one.
  the calorific value with its basis. `ncv_basis` is `rank_default` where the booked account
                      uses the IPCC default for the rank, and `generation_implied` where a
                      value is back-derived from generation. Both are given per row so the
                      reader can see which the account rests on.
  the energy          at both bases, in separate columns, never one blended number.
  the generation      with its declared basis and its own pointer.
  the coverage        `plant_coverage_class` says whether the row is a station the panel
                      enumerates or a residual, and `ke_treatment` records why K-Electric is
                      outside: its stations are in Tables 26-28 and none of them burns coal.

WHY THE REFERENCE IS PREFERRED, which the review said "reference" versus "plant-based" does
not establish now that both use plant coal. The two differ only in the calorific value:
the reference takes the IPCC default for the rank the station burns; the alternative takes
the value the station's own generation implies. The second is generation divided by
(mass x implied NCV), where the implied NCV was itself derived from generation and a printed
heat rate - so it reproduces the regulator's heat rates by construction and cannot test them.
That circularity is the reason, and `energy_TJ_generation_implied_basis` is published beside
`energy_TJ_booked_basis` so a reader can see the alternative rather than take the claim.

THE TWO RECONSTRUCTED YEARS are marked as such. FY2016-17 and FY2017-18 are in no per-station
coal table any held edition prints, so their rows carry `quantity_class = derived` with the
rule in `reconstruction_rule`, and the year's booked-total row carries the interval the
booking records. Nothing here hides a reconstruction inside a measured series.

THE COMMISSIONING LANE, AND HOW IT WENT MISSING. Four years carry CPPA-G coal generation
that no per-station coal table places: FY2016-17 873.17 and FY2017-18 11,783.11 GWh from
Sahiwal and Port Qasim while they were commissioning, FY2018-19 538.24 GWh and FY2021-22
77.56 GWh from stations the held editions enumerate only in adjacent years.
`coal_plant_fuel_back_years.csv` names the first two in its own header and says this file
reconstructs them - and an earlier version of this file did, with an interval. A rewrite of
the schema dropped the lane and updated neither consumer, and NOTHING NOTICED for a release:
the test could not read its own subject (it keyed on columns the producer never wrote, so it
errored in setUp and ran none of its cases) and pkinv.sectors.power.coal_configurations, the
only other reader, runs in the full build alone. The full build found it by raising
KeyError('row_kind'). The lane is restored as `plant_coverage_class = reconstructed lane`,
`quantity_class = reconstructed`.

NO POINT MASS IS INVENTED for it. The row carries `mass_lo_kt` and `mass_hi_kt` - the
generation divided by the intensity band the imported-coal stations themselves run at over
the ledger years, COMPUTED from the panel above rather than asserted, with the one cell the
back-years transcription flags as a real inter-edition revision excluded by name. Leaving
the generation out entirely is not the conservative choice it looks like: the fleet's
generation is the denominator of every efficiency the configurations product computes, and
without this lane FY2016-17 reads as 2.8 per cent efficient instead of 22.3.

Usage:  python3 -m pkinv.sectors.power.fuel_reconciliation [--check]
Writes: outputs/pakemis_power_fuel_reconciliation.csv
"""
import argparse
import collections
import csv
import io
import os
import sys

from pkinv.assets import asset_path
from pkinv.core.io import read_rows, table_text, write_table
from pkinv.paths import DATA, OUTPUTS, ROOT

OUT = asset_path(OUTPUTS, "pakemis_power_fuel_reconciliation.csv")

CAMPAIGN = os.path.join(ROOT, "research_campaign", "energy", "plant_fuel_year.csv")

TOE_PER_TJ = 1.0 / 0.041868          # 1 TJ = 23.8846 toe; the sector's own conversion

# Below this, a difference between the control and the station rows is a rounding artefact
# of the editions' own printed precision, not a station missing from the panel.
GENERATION_TOLERANCE_GWh = 1.0

FIELDS = (
    "period_id", "plant", "system", "fuel", "fuel_rank", "rank_evidence",
    "mass_kt", "mass_lo_kt", "mass_hi_kt",
    "quantity_class", "mass_semantics", "mass_source_edition",
    "mass_source_table",
    "ncv_TJ_per_Gg", "ncv_basis",
    "energy_TJ_booked_basis", "energy_TJ_generation_implied_basis",
    "net_generation_GWh", "generation_basis", "generation_source",
    "plant_coverage_class", "ke_treatment",
    "reconstruction_rule", "note",
    # v3 (the 23rd review's B1): the bases a reader needs to compare this account with
    # another, stated per row rather than left in the module docstring.
    "cv_gross_or_net", "moisture_basis", "generation_gross_or_net",
    "rank_share_weighting", "original_reporting_period", "station_status",
)

BANNER = """\
# THE COAL ACCOUNT, NINE FISCAL YEARS, ONE ROW PER STATION-YEAR
#
# Built so an outside reader can re-derive the booked coal energy for every year of the
# panel, including the years before the per-station ledger begins. See the module docstring
# in src/pkinv/sectors/power/fuel_reconciliation.py for what each column answers.
#
# THE THREE COLUMNS TO READ FIRST.
#   quantity_class   metered | derived | reconstructed.  A METERED mass is printed as a
#                    quantity by the edition named beside it. A DERIVED mass is generation
#                    times a PRINTED intensity - arithmetic on two published figures, not a
#                    measurement. A RECONSTRUCTED mass is not stated at all: the row carries
#                    mass_lo_kt and mass_hi_kt and the rule that produced them, because no
#                    held edition prints a quantity for that lane.
#   plant_coverage_class
#                    enumerated station | reconstructed lane | booked total.  The station
#                    rows and the reconstructed lane together close on the CPPA-G coal
#                    generation control for every year of the panel; the booked total is
#                    what the engine actually books, printed beside them to be checked.
#   ncv_basis        rank_default | generation_implied.  The booked account uses the IPCC
#                    default for the station's coal rank. The alternative uses the value the
#                    station's own generation implies, which restates the regulator's heat
#                    rates and so cannot test them - that circularity, and not a preference
#                    between sources, is why the reference is selected.
#
# Energy is given at BOTH bases in separate columns and never blended. Nothing in this file
# is booked: the engine reads data/sectors/power/activity/coal_energy_booking.csv, and this
# product exists so the booking can be checked against its sources.
"""


# WHAT "OUTSIDE" MEANS FOR K-ELECTRIC, stated precisely because the flat version
# ("no K-Electric station burns coal") is contradicted on its face by the repo's own
# generation table. Two different quantities are involved and only one of them is zero:
#   KE's own plant tables (NEPRA SoIR 26-28, and outputs/power_boundary_audit_fy2023_24.csv)
#     print gas and furnace oil and carry NO coal column - so there is no KE coal FUEL
#     quantity to bring into this account.
#   generation_by_fuel.csv does attribute coal-based ENERGY to the K-Electric system, 62 to
#     453 GWh a year from FY2016-17 on. This panel places no station against it.
# The distinction is why the panel's generation control is CPPA-G only, and the unresolved
# part of it is registered as data/shared/requests/data_gaps.csv#ke-boundary rather than
# settled here.
KE_TREATMENT = ("outside the CPPA-G panel: K-Electric's own plant tables (NEPRA SoIR 26-28) "
                "print gas and furnace oil and no coal quantity. The system-level generation "
                "table does attribute 62-453 GWh/yr of coal-based energy to K-Electric from "
                "FY2016-17; this panel places no station against it, and the scope question "
                "stays open as data_gaps.csv#ke-boundary")

# IPCC 2006 Vol.2 Ch.1 Table 1.2 net calorific values, keyed on the rank the editions print.
# IMPORTED, not restated: pkinv.sectors.power.reference_audit owns these two numbers and
# uses them for the supply bound, and a second copy here could drift from the bound it is
# meant to be comparable with.
from pkinv.sectors.power.reference_audit import NCV_BIT, NCV_LIG   # noqa: E402

RANK_DEFAULT_NCV = {"imported": NCV_BIT, "Thar lignite": NCV_LIG}


def _campaign_rows():
    if not os.path.exists(CAMPAIGN):
        return []
    with open(CAMPAIGN, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(line for line in handle
                                   if not line.startswith("#")))


def _num(value):
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _period(fiscal_start_year):
    """"2016" -> "FY2016-17". Both tables key on the fiscal START year.

    THE FIRST VERSION OF THIS READ THE KEY AS THE END YEAR and shifted every booked row and
    every back year by one, which put the two reconstructed years on the wrong periods. Two
    independent checks settle it. The engine's own error message formats the key as
    "FY%d-%02d" % (year, year + 1) (sectors/power/data.py), so it books a start year. And
    the back-years masses match the campaign table - which carries an explicit period_id -
    exactly under the start reading and are shifted under the end reading: China Power Hub's
    key 2019 is 2252.72 kt, which the campaign prints against FY2019-20.

    This is the third off-by-one of its kind in this repository, after the agriculture seam
    and the plant ledger, so the convention is checked against a table that spells the period
    out rather than inferred from the column's name.
    """
    start = int(fiscal_start_year)
    return "FY%d-%02d" % (start, (start + 1) % 100)


def _coal_generation_control():
    """{fiscal start year: CPPA-G coal GWh}, the control the station rows must explain.

    CPPA-G ONLY, which is the panel's declared boundary. generation_by_fuel.csv also prints a
    K-Electric coal row (62-453 GWh from FY2016-17 on); that is system-level energy, not fuel
    burnt at a K-Electric station - KE's own plant tables (NEPRA SoIR Tables 26-28, and
    outputs/power_boundary_audit_fy2023_24.csv) carry gas and furnace oil and no coal column at
    all. Summing it into this control would make every year fail to close against stations that
    are correctly outside the panel.
    """
    out = {}
    path = asset_path(DATA, "activity", "power", "generation_by_fuel.csv")
    for r in read_rows(path):
        if r.get("system") != "CPPA-G" or "oal" not in (r.get("fuel") or ""):
            continue
        gwh = _num(r.get("gwh_net"))
        if gwh is not None:
            out[int(float(r["fiscal_year"]))] = gwh
    return out


def _intensity_band(rows_so_far):
    """The GWh/kt band the imported-coal stations run at, from the panel's own metered cells.

    COMPUTED, not asserted. The one excluded cell is the Sahiwal FY2021-22 reading that
    coal_plant_fuel_back_years.csv already records as a REAL inter-edition revision (SoIR
    2023 prints 1025.24 kt against SoIR 2024's 1180.0); at 4.77 GWh/kt against the fleet's
    1.8-2.8 it is the anomaly that file flags, and a bound set by it would be a bound set by
    a number the repository already doubts.
    """
    # THE TWO STATIONS THAT ARE THE LANE, not every imported-coal station. Sahiwal and Port
    # Qasim are the plants commissioning in the uncovered years, and the back-years header
    # names them; bounding their own commissioning coal by a band that includes a third
    # station's best year (China Power Hub reaches 3.62 GWh/kt in FY2023-24, against the next
    # highest 2.80) widened the interval until two years' implied efficiency straddled the
    # plausible band instead of sitting inside it - a weaker statement produced by a worse
    # estimator, not by better evidence.
    LANE = ("Huaneng Shandong Ruyi (Sahiwal Imported Coal)", "Port Qasim Electric Power")
    EXCLUDE = {("FY2021-22", "Huaneng Shandong Ruyi (Sahiwal Imported Coal)")}
    vals = []
    for r in rows_so_far:
        if (r["plant_coverage_class"] != "enumerated station"
                or r["plant"] not in LANE):
            continue
        if (r["period_id"], r["plant"]) in EXCLUDE:
            continue
        mass, gwh = _num(r.get("mass_kt")), _num(r.get("net_generation_GWh"))
        if mass and gwh and mass > 0 and gwh > 0:
            vals.append(gwh / mass)
    if len(vals) < 5:
        raise AssertionError(
            "only %d station-years of the commissioning lane's own two plants carry both a "
            "mass and a generation; the band would rest on too little to bound anything"
            % len(vals))
    return min(vals), max(vals)


def rows():
    """The account with its basis columns: what the product publishes."""
    out = account_rows(announce=True)
    for r in out:
        r.update(_basis_columns(r))
    return out


def account_rows(announce=False):
    """The coal account from data/ inputs alone: station rows, the booked total and the
    commissioning lane, WITHOUT the basis columns.

    Split from rows() because the basis columns read outputs/pakemis_power_station_status.csv,
    and pkinv.sectors.power.province_panel needs the station energies during the spatial
    phase, which runs before that product is written. The per-year provincial split of coal
    is these rows' booked energy by province; it must not depend on a product of its own
    consumers."""
    out = []

    # ---- the five ledger years, from the campaign's own reconciliation -------------
    for r in _campaign_rows():
        mass = _num(r.get("mass_kt"))
        ncv = _num(r.get("ipcc_default_ncv_TJ_per_Gg"))
        booked = mass * ncv * 1e-3 * 1e3 if (mass and ncv) else None
        out.append({
            "period_id": r["period_id"], "plant": r["plant"],
            "system": r.get("system", ""), "fuel": r.get("fuel", "Coal"),
            "fuel_rank": r.get("fuel_origin", ""),
            "rank_evidence": r.get("origin_evidence", ""),
            "mass_kt": r.get("mass_kt", ""), "mass_lo_kt": "", "mass_hi_kt": "",
            # The campaign's mass_quantity_class is already metered/consumed language; a
            # ledger year's mass is printed as a quantity, so it is metered.
            "quantity_class": "metered",
            "mass_semantics": r.get("mass_semantics", ""),
            "mass_source_edition": (r.get("mass_source_pointer") or "").split(" Table")[0],
            "mass_source_table": r.get("mass_source_pointer", ""),
            "ncv_TJ_per_Gg": r.get("ipcc_default_ncv_TJ_per_Gg", ""),
            "ncv_basis": "rank_default",
            "energy_TJ_booked_basis": "" if booked is None else "%.1f" % booked,
            "energy_TJ_generation_implied_basis":
                r.get("energy_TJ_at_net_export_hr", ""),
            "net_generation_GWh": r.get("net_generation_GWh", ""),
            "generation_basis": r.get("generation_basis", ""),
            "generation_source": r.get("generation_source_pointer", ""),
            "plant_coverage_class": "enumerated station",
            "ke_treatment": r.get("ke_treatment", ""),
            "reconstruction_rule": "",
            "note": r.get("flags", ""),
        })

    ledger_periods = {r["period_id"] for r in out}

    # ---- the back years, from the editions that print them -------------------------
    back = asset_path(DATA, "activity", "power", "coal_plant_fuel_back_years.csv")
    for r in read_rows(back):
        period = _period(r["fiscal_year"])
        if period in ledger_periods:
            continue                      # the ledger year is the better record
        mass = _num(r.get("quantity_kt"))
        intensity = _num(r.get("intensity_kg_per_kWh_printed"))
        generation = _num(r.get("net_generation_GWh"))
        derived = mass is None and intensity is not None and generation is not None
        if derived:
            mass = intensity * generation * 1e-3      # kg/kWh x GWh -> kt
        ncv = RANK_DEFAULT_NCV.get((r.get("fuel_origin") or "").strip())
        out.append({
            "period_id": period, "plant": r["plant"],
            "system": r.get("system", ""), "fuel": r.get("fuel", "Coal"),
            "fuel_rank": r.get("fuel_origin", ""),
            "rank_evidence": r.get("note", ""),
            "mass_kt": "" if mass is None else "%.2f" % mass,
            "mass_lo_kt": "", "mass_hi_kt": "",
            "quantity_class": "derived" if derived else "metered",
            "mass_semantics": "coal consumed by the station over the fiscal year",
            "mass_source_edition": "NEPRA SoIR %s" % r.get("edition", ""),
            "mass_source_table": r.get("source_table", ""),
            # THE RANK DEFAULT, RESTORED. These rows declared ncv_basis = rank_default and
            # then left the value empty, which is a basis without a quantity: the back years
            # carried a mass and a rank but no calorific value, so nothing downstream could
            # turn them into energy. pkinv.sectors.power.coal_configurations could not read
            # them at all, and the full build is where that surfaced - the only place it
            # could, because that module runs nowhere else.
            "ncv_TJ_per_Gg": "" if ncv is None else "%.1f" % ncv,
            "ncv_basis": "rank_default",
            "energy_TJ_booked_basis": ("" if (ncv is None or mass is None)
                                       else "%.1f" % (mass * ncv)),
            "energy_TJ_generation_implied_basis": "",
            "net_generation_GWh": r.get("net_generation_GWh", ""),
            "generation_basis": "net generation as printed by the edition",
            "generation_source": r.get("source_table", ""),
            "plant_coverage_class": "enumerated station",
            "ke_treatment": KE_TREATMENT,
            "reconstruction_rule":
                "mass = printed intensity (kg/kWh) x printed net generation (GWh)"
                if derived else "",
            "note": r.get("note", ""),
        })

    # ---- the booked account per year, as the control the rows must explain ---------
    booking = read_rows(asset_path(DATA, "activity", "power",
                                   "coal_energy_booking.csv"), comments=True)
    for r in booking:
        period = _period(r["fiscal_year"])
        toe = _num(r.get("booked_toe"))
        lo, hi = _num(r.get("booked_lo_toe")), _num(r.get("booked_hi_toe"))
        reconstructed = lo is not None and hi is not None and lo != hi
        out.append({
            "period_id": period, "plant": "ALL STATIONS (the booked account)",
            "system": "", "fuel": r.get("fuel", "Coal"),
            "fuel_rank": "", "rank_evidence": "",
            "mass_kt": "", "mass_lo_kt": "", "mass_hi_kt": "",
            "quantity_class": "derived" if reconstructed else "metered",
            "mass_semantics": r.get("mass_account", ""),
            "mass_source_edition": "data/sectors/power/activity/coal_energy_booking.csv",
            "mass_source_table": r.get("basis", ""),
            "ncv_TJ_per_Gg": "", "ncv_basis": "rank_default",
            "energy_TJ_booked_basis": "" if toe is None else "%.1f" % (toe / TOE_PER_TJ),
            "energy_TJ_generation_implied_basis": "",
            "net_generation_GWh": "", "generation_basis": "", "generation_source": "",
            "plant_coverage_class": "booked total",
            "ke_treatment": "",
            "reconstruction_rule":
                ("the booking takes the interval midpoint; booked_lo_toe %.1f and "
                 "booked_hi_toe %.1f bound it" % (lo, hi)) if reconstructed else "",
            "note": r.get("note", ""),
        })

    # ---- the commissioning lane: BOUNDED, not invented, not left silent ----------------
    # Four years carry CPPA-G coal generation that no held per-station coal table places:
    # Sahiwal and Port Qasim while they were commissioning, and two smaller pre-COD
    # residuals. coal_plant_fuel_back_years.csv names the first two in its own header and
    # says this file reconstructs them, and it must, because the fleet's generation is the
    # denominator of every efficiency the configurations product computes - leaving the
    # generation out makes FY2016-17 read as 2.8 per cent efficient instead of 22.3.
    #
    # NO POINT MASS IS INVENTED. The row carries an INTERVAL and the rule that produced it:
    # the generation divided by the intensity band the imported-coal stations themselves run
    # at over the ledger years. The band is COMPUTED from the panel above, not asserted, and
    # the one cell the back-years transcription flags as anomalous is excluded by name - its
    # 4.77 GWh/kt against the fleet's 1.8-2.8 is the inter-edition revision that file records,
    # and letting it set the bound would make the interval meaninglessly wide at the low end.
    control = _coal_generation_control()
    placed = {}
    for r in out:
        if r["plant_coverage_class"] != "enumerated station":
            continue
        gwh = _num(r.get("net_generation_GWh"))
        if gwh is not None:
            year = int(r["period_id"][2:6])
            placed[year] = placed.get(year, 0.0) + gwh
    lo_i, hi_i = _intensity_band(out)
    for year in sorted(control):
        gap = control[year] - placed.get(year, 0.0)
        if abs(gap) <= GENERATION_TOLERANCE_GWh:
            continue
        out.append({
            "period_id": _period(year),
            "plant": "Commissioning lane (no held edition prints a mass)",
            "system": "CPPA-G", "fuel": "Coal",
            "fuel_rank": "imported",
            "rank_evidence": "the stations commissioning in these years burn imported coal",
            "mass_kt": "",
            "mass_lo_kt": "%.2f" % (gap / hi_i),
            "mass_hi_kt": "%.2f" % (gap / lo_i),
            "quantity_class": "reconstructed",
            "mass_semantics": "an interval on the coal this generation implies; no point mass",
            "mass_source_edition": "", "mass_source_table": "",
            "ncv_TJ_per_Gg": "%.1f" % RANK_DEFAULT_NCV["imported"],
            "ncv_basis": "rank_default",
            "energy_TJ_booked_basis": "", "energy_TJ_generation_implied_basis": "",
            "net_generation_GWh": "%.2f" % gap,
            "generation_basis": "CPPA-G coal generation less the sum of the station rows "
                                "for this period",
            "generation_source": "data/sectors/power/activity/generation_by_fuel.csv "
                                 "(system CPPA-G, fuel Coal)",
            "plant_coverage_class": "reconstructed lane",
            "ke_treatment": "",
            "reconstruction_rule":
                "mass interval = %.2f GWh / the %.3f-%.3f GWh/kt band Sahiwal and Port "
                "Qasim - the plants commissioning in these years - run at over the ledger "
                "years, the Sahiwal FY2021-22 cell excluded because "
                "coal_plant_fuel_back_years.csv records it as a real inter-edition revision. "
                "NO POINT MASS: no held edition prints one for this lane"
                % (gap, lo_i, hi_i),
            "note": "%.2f GWh of CPPA-G coal generation that no per-station coal table "
                    "places. The generation is printed; the mass is BOUNDED, never stated as "
                    "a point, and never distributed over the enumerated stations." % gap,
        })

    # THE NINE PANEL PERIODS ONLY. The booking table reaches back to FY2012-13 because the
    # engine books those years for the historical series, but the reported panel is nine
    # years and a reconciliation that silently included three more would not reconcile
    # against anything the manuscript states.
    panel = {r["period_id"] for r in read_rows(asset_path(DATA, "periods.csv"))}
    dropped = sorted({r["period_id"] for r in out} - panel)
    out = [r for r in out if r["period_id"] in panel]
    assert len(panel) == 9, "the period registry holds %d periods, not nine" % len(panel)
    if dropped and announce:
        print("  outside the reported panel, not included: %s" % ", ".join(dropped))
    out.sort(key=lambda r: (r["period_id"], r["plant_coverage_class"] == "booked total",
                            r["plant"]))
    return out


def _station_status():
    """{(period, plant): GEM window verdict} from the commissioning check, where it has run.

    Read, not recomputed: pkinv.report.power_station_status joins the GEM tracker once.
    Absent (a fresh tree), the column says so rather than guessing."""
    path = asset_path(OUTPUTS, "pakemis_power_station_status.csv")
    if not os.path.exists(path):
        return {}
    from pkinv.sectors.power.plant_names import plant_key
    out = {}
    for r in read_rows(path):
        label = r["window_check"]
        if r["gem_start_year"]:
            label += " (GEM %s, start %s%s)" % (r["gem_status"], r["gem_start_year"],
                                                 (", retired %s" % r["gem_retired_year"])
                                                 if r["gem_retired_year"] else "")
        out[(r["period_id"], plant_key(r["station"]))] = label
    return out


_STATUS = None


def _basis_columns(r):
    """The six basis columns, derived from what the row already states."""
    global _STATUS
    if _STATUS is None:
        _STATUS = _station_status()
    if r["plant_coverage_class"] == "reconstructed lane":
        status = "commissioning lane: no station named"
    elif r["plant"].startswith("ALL STATIONS") or r["plant"].startswith("(no coal"):
        status = "not a station row"
    else:
        from pkinv.sectors.power.plant_names import plant_key
        status = _STATUS.get((r["period_id"], plant_key(r["plant"])),
                             "not checked (run pkinv.report.power_station_status)")
    cv = ("net calorific value: IPCC 2006 Vol.2 Table 1.2 default for the rank, as "
          "consumed" if r["ncv_basis"] == "rank_default" else r["ncv_basis"])
    if r["energy_TJ_generation_implied_basis"]:
        cv += "; the generation-implied column uses the net-export heat rate"
    gen = r["generation_basis"] or ("" if not r["net_generation_GWh"] else "as printed")
    return {
        "cv_gross_or_net": cv,
        "moisture_basis": ("not stated by the source edition: tonnes as printed, no "
                           "as-received or dry basis given" if r["mass_kt"] not in ("", "NE")
                           else "no mass"),
        "generation_gross_or_net": gen,
        "rank_share_weighting": ("one rank per station-year (fuel_rank); the C1 account "
                                 "mass-weights stations, never a rank share within one"
                                 if r["fuel_rank"] else "no rank: no station mass"),
        "original_reporting_period": ("%s, fiscal July-June, as printed by %s"
                                      % (r["period_id"], r["mass_source_edition"])
                                      if r["mass_source_edition"] else r["period_id"]),
        "station_status": status,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--check", action="store_true",
                        help="compare the shipped file with a fresh build; write nothing")
    args = parser.parse_args(argv)
    data = rows()
    if args.check:
        # TWO DEFECTS, both of which made this check unable to pass in any tree. It rebuilt
        # the expected text by hand (DictWriter plus the banner joined with "\n") instead of
        # calling table_text, which IS what write_table puts in the file. And it read the
        # held file in TEXT mode, where Python's universal newlines silently collapse every
        # CRLF to LF - so a CRLF product came back 59 characters shorter than it is on disk
        # and compared unequal to itself. newline="" is what stops the translation.
        held = ""
        if os.path.exists(OUT):
            with open(OUT, encoding="utf-8", newline="") as handle:
                held = handle.read()
        fresh = table_text(list(FIELDS), data, banner=BANNER.splitlines())
        print("power fuel reconciliation: %s"
              % ("byte-identical" if held == fresh else "DIFFERS"))
        return 0 if held == fresh else 1
    write_table(OUT, list(FIELDS), data, banner=BANNER.splitlines())
    periods = sorted({r["period_id"] for r in data})
    # COUNTED PER CLASS, not as "derived and the rest". The first version printed
    # "%d derived, %d metered" with the second term as a subtraction, so when the
    # not_estimated lane was added its four rows were reported as metered - a summary line
    # claiming measurement for the one class that explicitly has none.
    classes = collections.Counter(r["quantity_class"] for r in data)
    unplaced = sum(1 for r in data
                   if r["plant_coverage_class"] == "reconstructed lane")
    print("power fuel reconciliation -> %s" % OUT)
    print("  %d rows over %d periods (%s..%s); %s"
          % (len(data), len(periods), periods[0], periods[-1],
             ", ".join("%d %s" % (n, k) for k, n in sorted(classes.items()))))
    if unplaced:
        print("  %d year(s) carry a reconstructed commissioning lane: generation printed, "
              "mass bounded, no point mass stated" % unplaced)
    return 0


if __name__ == "__main__":
    sys.exit(main())
