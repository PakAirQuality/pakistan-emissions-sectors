"""NEPRA's SIR Detail-of-Generation listings, read into the plant-month panel.

WHAT THIS UNLOCKS. The PBS plant-month record ends at FY2020-21, so the three most recent
years - including the reference year every headline figure is quoted for - carried grid coal
and gas flat. rc20 enumerated NEPRA's per-plant daily-report archive (4,644 documents) as the
parse backlog; this pass found that the archive's own LISTING sheets already carry the whole
plant-month table. Each fiscal year's "Detail of Generation" index is an Excel-HTML sheet
whose rows are one plant each: company, technology, fuel, capacity, then twelve
(utilization %, GWh) pairs July to June, then a Sum pair. Three sheets, held since rc20 at
data/raw/nepra/sir_detail/, are the source; the 4,644 daily PDFs become the verification
sample rather than the parse target.

THE ROW PROVES ITSELF. Every plant row prints its own annual Sum, and the twelve months must
meet it. In FY2022-23 and FY2023-24 every row closes exactly. In FY2021-22 eight rows do not
- NEPRA's own arithmetic is wrong on its face by 49 GWh of 135,445, one of them a suspicious
February that repeats January to the last digit - and those eight go into a typed discrepancy
ledger rather than being silently kept or silently dropped. The months are what the monthly
layer consumes, so the months are kept and the printed Sum is recorded as disagreeing;
per-plant daily reports arbitrate where the archive serves them.

A MIXED LABEL IS NOT GUESSED - BUT SOMETIMES IT IS BOUNDED. The sheets label some plants with
two or three fuels at once (RLNG/HSD, GAS/HSD, Natural Gas/ Furnace Oil). No split is ever
invented. But the annual control (generation_by_fuel.csv, NEPRA's own Table 17) can FORCE a
label: if attributing the ENTIRE annual control of every other candidate fuel to a mixed
group still leaves at least DOMINANT (95 percent) of the group's generation on one fuel, the
group is that fuel to within the same tolerance the NEPRA plant-year panel already uses. At
FY2023-24 the whole country burned 126.6 GWh of HSD in grid plants while the RLNG/HSD
combined-cycle group generated 22,944 GWh - at least 99.4 percent of it is gas by arithmetic,
not by judgement. A group the bound cannot force stays unassigned, and any subitem whose
observed mass includes bound-assigned generation is capped at TE3: the fuel was inferred,
however tightly, and TE2 is reserved for plant-fuel-month cells the source states directly.

WHAT THIS SHAPES, AND WHAT IT DELIBERATELY DOES NOT. Coverage rows are written for Coal and
Gas only. Furnace Oil and Diesel Oil already ride the OCAC Total-Power panel in these years
with T1/T2 months; a TE3 generation shape would DISPLACE that under the monthly layer's
precedence and downgrade the evidence. The SIR furnace-oil series is published as a
crosscheck against the OCAC profile instead - two instruments, never blended.

Usage:  python3 scripts/ingest_sir_generation.py [--dry-run]
Writes: data/activity/power/generation_monthly.csv        (SIR years; PBS rows preserved)
        data/activity/power/generation_monthly_coverage.csv (SIR years; PBS rows preserved)
        data/activity/power/sir_row_discrepancies.csv
"""
import argparse
import csv
import collections
import hashlib
import html
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pkinv.assets import asset_path
import ingest_pbs_generation as pbs  # noqa: E402
from pkinv.core.io import write_or_check  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LISTING_DIR = asset_path(ROOT, "data", "raw", "nepra", "sir_detail")
LISTINGS = {
    2021: asset_path(LISTING_DIR, "sir_companies_2021_22.htm"),
    2022: asset_path(LISTING_DIR, "sir_companies_2022_23.htm"),
    2023: asset_path(LISTING_DIR, "sir_companies_2023_24.htm"),
}
# The four earlier listing years (Pass 2, Wave 2). These do NOT enter the panel: the PBS
# lane already carries FY2017-18..FY2020-21, and two vintages of one mass must compare,
# never sum. They serve two other jobs: the PBS-overlap shape validation
# (outputs/power_sir_pbs_overlap.csv), and the SAME-YEAR fuel crosswalk - the sheets
# label stations PBS's own fuel column leaves blank, which ingest_pbs_generation
# consumes through data/activity/power/pbs_sir_aliases.csv under a magnitude gate.
VALIDATION_LISTINGS = {
    2017: asset_path(LISTING_DIR, "sir_companies_2017_18.htm"),
    2018: asset_path(LISTING_DIR, "sir_companies_2018_19.htm"),
    2019: asset_path(LISTING_DIR, "sir_companies_2019_20.htm"),
    2020: asset_path(LISTING_DIR, "sir_companies_2020_21.htm"),
}
OUT = pbs.OUT
COVERAGE = pbs.COVERAGE
DISCREPANCIES = asset_path(ROOT, "data", "activity", "power",
                             "sir_row_discrepancies.csv")
CORRECTIONS = asset_path(ROOT, "data", "activity", "power",
                           "sir_month_corrections.csv")

DISCREPANCY_FIELDS = ("fiscal_year", "plant", "fuel_label", "months_sum_gwh",
                      "printed_sum_gwh", "delta_gwh", "resolution")

# The sheet's fuel vocabulary, closed. A label outside it is an error, never a skip: a new
# NEPRA spelling must be read and placed here deliberately. Values are the panel's fuel words
# (ingest_pbs_generation.FUEL_TOKENS vocabulary) so the coverage grouping and the consumer
# see one vocabulary across both sources.
SINGLE_FUEL = {
    "gas": "Gas", "natural gas": "Gas", "rlng": "RLNG", "rfo": "RFO",
    "coal": "Coal", "lignite coal": "Coal", "hsd": "HSD",
    "hydel": "Hydel", "nuclear": "Nuclear", "wind": "Wind", "solar": "Solar",
    "bagasse": "Bagasse",
}
# label -> candidate panel fuel words, in the sheet's own order. No candidate is preferred;
# only the annual-control bound can pick one.
MIXED_FUEL = {
    "rlng/hsd": ("RLNG", "HSD"),
    "gas/hsd": ("Gas", "HSD"),
    "rfo/rlng/hsd": ("RFO", "RLNG", "HSD"),
    "natural gas/ furnace oil": ("Gas", "RFO"),
    "natural gas/furnace oil": ("Gas", "RFO"),
    "bagasse/coal": ("Bagasse", "Coal"),
}

# The two subitems this source is allowed to shape (see module docstring).
SHAPED_SUBITEMS = ("Coal", "Gas")

UNIT_BASIS = "GWh as printed"
# Sum-vs-months tolerance: the cells carry two decimals, so twelve roundings and the Sum's
# own can disagree by up to 0.065 GWh legitimately; beyond that the row's arithmetic is wrong.
CLOSURE_SLACK = 0.07

TR = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
TD = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
TAG = re.compile(r"<[^>]+>")


def _cells(row_html):
    out = []
    for cell in TD.findall(row_html):
        text = html.unescape(TAG.sub("", cell))
        out.append(" ".join(text.replace("\xa0", " ").split()))
    return out


def _number(text):
    if not text:
        return None
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return None


def parse_sheet(path):
    """([{plant, fuel_label, months[12], printed_sum}], [(plant, reason) excluded]).

    A plant row has a numeric serial in cell 0. Cells: serial, company, technology, fuel,
    installed MW, dependable MW, then (utilization %, GWh) pairs for Jul..Jun and a Sum
    pair - GWh at cells 7+2i, the annual Sum GWh at cell 31. Rows without month cells
    (a second, capacity-only table of delicensed units) and rows whose month cells hold
    words (DELICENSED) carry no generation and are typed out, never guessed at.
    """
    with open(path, encoding="windows-1252", errors="replace") as handle:
        sheet = handle.read()
    plants, excluded = [], []
    for row_html in TR.findall(sheet):
        cells = _cells(row_html)
        if not cells or not cells[0].isdigit():
            continue
        name = cells[1] if len(cells) > 1 else ""
        if len(cells) < 32:
            excluded.append((name, "no month cells printed (capacity-only listing row)"))
            continue
        months = [_number(cells[7 + 2 * i]) for i in range(12)]
        printed = _number(cells[31])
        numeric = [m for m in months if m is not None]
        if not numeric:
            reason = ("months printed as %r; no generation stated"
                      % (cells[6] or "(blank)"))
            excluded.append((name, reason))
            continue
        if len(numeric) != 12 or printed is None:
            raise SystemExit("%s: row %r states %d of 12 months numerically - a partial "
                             "row cannot be read without guessing" %
                             (os.path.basename(path), name, len(numeric)))
        plants.append({"plant": name, "fuel_label": " ".join(cells[3].split()),
                       "months": months, "printed_sum": printed})
    if not plants:
        raise SystemExit("%s: no plant rows parsed" % os.path.basename(path))
    return plants, excluded


def member_bound(fuel_label, member_total, controls):
    """The per-member annual-control bound: the single fuel a mixed label is FORCED to,
    or None.

    Stricter than the group bound the panel years use: it asks whether even attributing
    every OTHER candidate fuel's entire national control to THIS ONE member still leaves
    DOMINANT of the member's own generation on one fuel. Used by the same-year crosswalk,
    where a label lands on an individual PBS station rather than on a sheet group.
    """
    key = fuel_label.lower()
    if key in SINGLE_FUEL:
        return SINGLE_FUEL[key], "stated"
    candidates = MIXED_FUEL.get(key)
    if not candidates or member_total <= 0:
        return None, None
    for fuel in candidates:
        others = [f for f in candidates if f != fuel]
        if any(f not in controls for f in others):
            continue
        ceiling = sum(controls.get(f, 0.0) for f in others)
        if (member_total - ceiling) / member_total >= pbs.DOMINANT:
            return fuel, "bound"
    return None, None


def assign_fuels(plants, controls, label):
    """Label every plant row: the sheet's own single-fuel word, or the annual-control bound.

    Returns (rows-with-fuel/fuel_source/note, [(group_label, verdict) for mixed groups]).
    """
    groups = collections.defaultdict(list)
    for plant in plants:
        key = plant["fuel_label"].lower()
        if key in SINGLE_FUEL:
            plant["fuel"] = SINGLE_FUEL[key]
            plant["fuel_source"] = "sir_fuel_column"
            plant["note"] = ""
        elif key in MIXED_FUEL:
            groups[key].append(plant)
        else:
            raise SystemExit("%s: fuel label %r is outside the closed vocabulary"
                             % (label, plant["fuel_label"]))

    verdicts = []
    for key, members in sorted(groups.items()):
        candidates = MIXED_FUEL[key]
        total = sum(sum(p["months"]) for p in members)
        chosen, floor = None, None
        if total > 0:
            for fuel in candidates:
                others = [f for f in candidates if f != fuel]
                # A candidate with no annual control (bagasse) has no ceiling, so nothing
                # can be forced past it.
                if any(f not in controls for f in others):
                    continue
                ceiling = sum(controls.get(f, 0.0) for f in others)
                share = (total - ceiling) / total
                if share >= pbs.DOMINANT:
                    chosen, floor = fuel, share
                    break
        if chosen:
            source = "sir_annual_control_bound_%d%%" % int(100 * floor)
            note = ("mixed fuel label %r assigned to %s: the other candidate fuels' "
                    "entire annual control (%.0f GWh) is at most %.1f%% of this group's "
                    "%.0f GWh" % (members[0]["fuel_label"], chosen,
                                  sum(controls.get(f, 0.0) for f in candidates
                                      if f != chosen),
                                  100 * (1 - floor), total))
            for plant in members:
                plant["fuel"], plant["fuel_source"], plant["note"] = chosen, source, note
            verdicts.append((members[0]["fuel_label"],
                             "assigned %s at >=%.1f%% by annual-control bound"
                             % (chosen, 100 * floor)))
        else:
            note = ("mixed fuel label %r; the annual control cannot force a single fuel; "
                    "excluded from the fuel-specific monthly profiles"
                    % members[0]["fuel_label"])
            for plant in members:
                plant["fuel"], plant["fuel_source"], plant["note"] = "", "unassigned", note
            verdicts.append((members[0]["fuel_label"],
                             "unassigned (%.0f GWh; no candidate reaches the %.0f%% bound)"
                             % (total, 100 * pbs.DOMINANT)))
    return plants, verdicts


def coverage_rows(plants, controls, label):
    """Coal and Gas verdicts only, on the same ladder the PBS ingest uses - with one cap.

    A subitem whose observed mass includes bound-assigned generation is capped at TE3:
    the fuel was inferred from the control, however tightly, and TE2 is reserved for cells
    the source states plant-by-plant.
    """
    observed = collections.defaultdict(float)
    inferred = collections.defaultdict(float)
    for plant in plants:
        if not plant["fuel"]:
            continue
        gwh = sum(plant["months"])
        observed[plant["fuel"]] += gwh
        if plant["fuel_source"].startswith("sir_annual_control_bound"):
            inferred[plant["fuel"]] += gwh
    out = []
    for subitem, fuels in pbs.FUEL_GROUPS:
        if subitem not in SHAPED_SUBITEMS:
            continue
        control = sum(controls.get(f, 0.0) for f in fuels)
        if not control:
            continue
        share = sum(observed.get(f, 0.0) for f in fuels) / control
        bound_mass = sum(inferred.get(f, 0.0) for f in fuels)
        if share > pbs.COVERAGE_IMPOSSIBLE:
            grade, decision = "TE4", ("labelled generation exceeds the annual control; "
                                      "the fuel labels do not hold in this year")
        elif share >= pbs.COVERAGE_STRONG:
            grade, decision = "TE2", "fuel-specific monthly shape"
        elif share >= pbs.COVERAGE_WEAK:
            grade, decision = "TE3", "fuel-specific monthly shape, partial sample"
        else:
            grade, decision = "TE4", "no shape; the fuel keeps its flat profile"
        if grade == "TE2" and bound_mass > 0:
            grade = "TE3"
            decision = ("fuel-specific monthly shape; %.0f GWh of the observed mass is "
                        "assigned by annual-control bound rather than stated per plant, "
                        "so the grade is capped at TE3" % bound_mass)
        elif grade == "TE3" and bound_mass > 0:
            decision += ("; %.0f GWh of the observed mass is assigned by "
                         "annual-control bound" % bound_mass)
        out.append({"fiscal_year": label, "subitem": subitem,
                    "fuel_words": "+".join(fuels), "control_gwh": round(control, 2),
                    "observed_gwh": round(sum(observed.get(f, 0.0) for f in fuels), 2),
                    "coverage": round(share, 4), "temporal_class": grade,
                    "decision": decision})
    return out


def corrections():
    """{(fiscal_year, plant): [rows]} from the arbitration file, comments stripped."""
    out = collections.defaultdict(list)
    if not os.path.exists(CORRECTIONS):
        return out
    with open(CORRECTIONS, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(line for line in handle
                                  if not line.startswith("#")):
            out[(row["fiscal_year"], row["plant"])].append(row)
    return out


def build():
    controls_all = pbs.control_by_fuel()
    arbitrated = corrections()
    rows, coverage, ledger, report = [], [], [], []
    for fy_start in sorted(LISTINGS):
        path = LISTINGS[fy_start]
        label = "FY%d-%02d" % (fy_start, (fy_start + 1) % 100)
        digest = pbs._sha256(path)
        plants, excluded = parse_sheet(path)
        controls = controls_all.get(fy_start, {})
        if not controls:
            raise SystemExit("%s: no annual control; the bound and the coverage both "
                             "need generation_by_fuel.csv" % label)

        misclosed = []
        for plant in plants:
            delta = sum(plant["months"]) - plant["printed_sum"]
            if abs(delta) > max(CLOSURE_SLACK, 0.001 * abs(plant["printed_sum"])):
                misclosed.append((plant, sum(plant["months"]), delta))
        misclosed_names = {plant["plant"] for plant, _raw, _delta in misclosed}

        # Arbitration: a correction may only touch a row the closure identity already
        # flagged, must quote the sheet cell it replaces exactly, and the corrected row
        # must then close on the printed Sum - or, for a confirmed Sum typo, every month
        # was independently corroborated and nothing moves.
        keys = pbs.months_for(fy_start)
        for (fix_label, name), fixes in arbitrated.items():
            if fix_label != label:
                continue
            if name not in misclosed_names:
                raise SystemExit("%s: a correction names %r, which the closure identity "
                                 "does not flag - the arbitration file has drifted from "
                                 "the sheet" % (label, name))
            plant = next(p for p, _raw, _d in misclosed if p["plant"] == name)
            for fix in fixes:
                if fix["kind"] == "sum_typo_confirmed":
                    continue
                if fix["kind"] != "month_cell":
                    raise SystemExit("%s %r: unknown correction kind %r"
                                     % (label, name, fix["kind"]))
                index = keys.index(fix["month"])
                if abs(plant["months"][index] - float(fix["sheet_gwh"])) > 0.005:
                    raise SystemExit("%s %r %s: the sheet reads %.2f, not the %.2f the "
                                     "correction quotes" % (label, name, fix["month"],
                                                            plant["months"][index],
                                                            float(fix["sheet_gwh"])))
                plant["months"][index] = float(fix["corrected_gwh"])
            kinds = {fix["kind"] for fix in fixes}
            if "month_cell" in kinds:
                delta = sum(plant["months"]) - plant["printed_sum"]
                if abs(delta) > max(CLOSURE_SLACK, 0.001 * abs(plant["printed_sum"])):
                    raise SystemExit("%s %r: still misses the printed Sum by %+.2f GWh "
                                     "after correction" % (label, name, delta))

        for plant, raw_sum, delta in misclosed:
            fixes = arbitrated.get((label, plant["plant"]), [])
            if any(f["kind"] == "month_cell" for f in fixes):
                resolution = ("; ".join(f["reason"] for f in fixes)
                              + " (arbitrated by %s)"
                              % ", ".join(f["basis_document"] for f in fixes))
            elif any(f["kind"] == "sum_typo_confirmed" for f in fixes):
                resolution = ("%s (arbitrated by the plant's daily reports, e.g. %s)"
                              % (fixes[0]["reason"], fixes[0]["basis_document"]))
            else:
                resolution = ("months kept; the printed annual Sum disagrees with the "
                              "twelve months in the source's own arithmetic; per-plant "
                              "daily reports arbitrate where the archive serves them")
            ledger.append({
                "fiscal_year": label, "plant": plant["plant"],
                "fuel_label": plant["fuel_label"],
                "months_sum_gwh": round(raw_sum, 2),
                "printed_sum_gwh": round(plant["printed_sum"], 2),
                "delta_gwh": round(delta, 2),
                "resolution": resolution,
            })

        plants, verdicts = assign_fuels(plants, controls, label)

        # Sanity bracket, the PBS unit test transplanted: total generation against the
        # fossil control. GWh are stated, so the scale must be 1 - anything else means the
        # sheet is not what this parser thinks it is.
        fossil_control = sum(controls.get(f, 0.0) for f in pbs.FOSSIL)
        total = sum(sum(p["months"]) for p in plants)
        if not 1.0 <= total / fossil_control <= 3.0:
            raise SystemExit("%s: total generation %.0f GWh against a fossil control of "
                             "%.0f GWh is outside the 1-3x bracket; the sheet is not "
                             "plant-month GWh" % (label, total, fossil_control))

        year_coverage = coverage_rows(plants, controls, label)
        coverage.extend(year_coverage)
        shaped = [c["subitem"] for c in year_coverage if c["temporal_class"] != "TE4"]
        report.append((label, "OK",
                       "%d plants (%d rows excluded, %d misclosed), %.0f GWh total; "
                       "shaped fuels: %s"
                       % (len(plants), len(excluded), len(misclosed), total,
                          ", ".join(shaped) if shaped else "none")))
        for group_label, verdict in verdicts:
            report.append((label, "MIXED", "%s: %s" % (group_label, verdict)))
        for name, reason in excluded:
            report.append((label, "EXCLUDED", "%s: %s" % (name, reason)))

        keys = pbs.months_for(fy_start)
        for plant in plants:
            for index, month in enumerate(keys):
                rows.append({
                    "fiscal_year": label, "month": month, "plant": plant["plant"],
                    "fuel": plant["fuel"], "fuel_source": plant["fuel_source"],
                    "gwh": round(plant["months"][index], 4),
                    "unit_basis": UNIT_BASIS,
                    "source_file": os.path.relpath(path, ROOT),
                    "source_sha256": digest,
                    "note": plant["note"],
                })
    return rows, coverage, ledger, report


def _merge(path, fields, own_rows, own_years, check=False):
    """The lane-preserving write: this source's years replaced, every other row kept.

    WHY A WHOLE-FILE CHECK IS SOUND HERE even though two scripts write this file. The two
    lanes write in OPPOSITE orders - ingest_pbs_generation puts its own rows first, this
    one puts its own last - and PBS holds the earlier fiscal years, so both run orders
    converge on the same layout ([PBS years, then SIR years]) whichever lane ran last.
    That property was confirmed by running both lanes, not deduced. A difference under
    --check therefore means this lane no longer reproduces its own rows, not that the
    other lane happened to write more recently.
    """
    preserved = []
    if os.path.exists(path):
        with open(path, newline="", encoding="utf-8") as handle:
            preserved = [r for r in csv.DictReader(handle)
                         if r["fiscal_year"] not in own_years]
    return write_or_check(path, fields, list(preserved) + list(own_rows), check)


OVERLAP_OUT = asset_path(ROOT, "outputs", "power_sir_pbs_overlap.csv")
OVERLAP_FIELDS = ("fiscal_year", "subitem", "month", "sir_share", "pbs_share",
                  "delta_pp", "sir_gwh", "pbs_gwh")


def overlap_rows():
    """The PBS-overlap validation: two independent vintages of one fleet's months.

    For FY2017-18..FY2020-21 both records exist - PBS's plant-month tables and NEPRA's
    listing sheets - and the sixteenth review's rule is compare, never sum. Each
    subitem-year where both sides carry twelve labelled months gets its two normalised
    shapes side by side; the DELTA is the honest width of the plant-month timing claim,
    the same instrument-vs-instrument statement the furnace-oil crosscheck makes
    against OCAC. Neither side is corrected toward the other.
    """
    controls_all = pbs.control_by_fuel()
    out = []
    for fy_start, path in sorted(VALIDATION_LISTINGS.items()):
        if not os.path.exists(path):
            continue
        label = "FY%d-%02d" % (fy_start, (fy_start + 1) % 100)
        plants, _excluded = parse_sheet(path)
        plants, _verdicts = assign_fuels(plants, controls_all.get(fy_start, {}), label)
        keys = pbs.months_for(fy_start)
        sir_months = collections.defaultdict(lambda: [0.0] * 12)
        for plant in plants:
            if plant["fuel"]:
                for index in range(12):
                    sir_months[plant["fuel"]][index] += plant["months"][index]
        pbs_months = collections.defaultdict(lambda: [0.0] * 12)
        with open(OUT, newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                if row["fiscal_year"] == label and row["fuel"]:
                    pbs_months[row["fuel"]][keys.index(row["month"])] += \
                        float(row["gwh"])
        for subitem, fuels in pbs.FUEL_GROUPS:
            sir = [sum(sir_months[f][i] for f in fuels) for i in range(12)]
            ours = [sum(pbs_months[f][i] for f in fuels) for i in range(12)]
            if sum(sir) <= 0 or sum(ours) <= 0:
                continue
            for index in range(12):
                sir_share = sir[index] / sum(sir)
                pbs_share = ours[index] / sum(ours)
                out.append({
                    "fiscal_year": label, "subitem": subitem, "month": keys[index],
                    "sir_share": round(sir_share, 6), "pbs_share": round(pbs_share, 6),
                    "delta_pp": round(100 * (sir_share - pbs_share), 3),
                    "sir_gwh": round(sir[index], 2), "pbs_gwh": round(ours[index], 2),
                })
    return out


def write_overlap():
    rows = overlap_rows()
    os.makedirs(os.path.dirname(OVERLAP_OUT), exist_ok=True)
    with open(OVERLAP_OUT, "w", newline="", encoding="utf-8") as handle:
        handle.write("# The PBS-overlap validation for FY2017-18..FY2020-21: NEPRA's "
                     "listing-sheet months beside PBS's plant-month record, per fuel "
                     "subitem, normalised. Two vintages of one mass: compared, never "
                     "summed, and neither corrected toward the other.\n")
        writer = csv.DictWriter(handle, fieldnames=OVERLAP_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    worst = max((abs(float(r["delta_pp"])), r["fiscal_year"], r["subitem"])
                for r in rows)
    print("PBS-overlap validation -> %s (%d subitem-months; worst share gap "
          "%.1f pp, %s %s)" % (os.path.relpath(OVERLAP_OUT, ROOT), len(rows),
                               worst[0], worst[1], worst[2]))
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Ingest NEPRA SIR Detail-of-Generation listings.")
    parser.add_argument("--check", action="store_true",
                        help="re-derive and report whether the committed panel still "
                             "follows from the held listings; writes nothing")
    parser.add_argument("--dry-run", action="store_true", help="report and write nothing")
    args = parser.parse_args(argv)

    rows, coverage, ledger, report = build()
    print("NEPRA SIR Detail-of-Generation listings -> monthly plant generation")
    for label, status, detail in report:
        print("  %-10s %-9s %s" % (label, status, detail))
    print("  %d rows over %d fiscal years" % (len(rows),
                                              len({r["fiscal_year"] for r in rows})))
    if coverage:
        print("\n  coverage against the annual control, by the subitem a profile applies to")
        for row in coverage:
            print("    %-10s %-12s %7.1f%% of %8.0f GWh  %s  %s"
                  % (row["fiscal_year"], row["subitem"], 100 * row["coverage"],
                     row["control_gwh"], row["temporal_class"], row["decision"]))
    if ledger:
        print("\n  %d rows whose printed Sum disagrees with their own twelve months"
              % len(ledger))
        for row in ledger:
            print("    %-10s %-45s %9.2f vs printed %9.2f (%+.2f)"
                  % (row["fiscal_year"], row["plant"][:45], row["months_sum_gwh"],
                     row["printed_sum_gwh"], row["delta_gwh"]))
    if args.dry_run:
        print("\n--dry-run: nothing written.")
        return 0

    own_years = {r["fiscal_year"] for r in rows}
    if _merge(OUT, pbs.FIELDS, rows, own_years, args.check):
        return 1
    if _merge(COVERAGE, pbs.COVERAGE_FIELDS, coverage, own_years, args.check):
        return 1
    if args.check:
        print("the SIR lane's years reproduce from the held listings.")
        return 0
    with open(DISCREPANCIES, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=DISCREPANCY_FIELDS)
        writer.writeheader()
        writer.writerows(ledger)
    print("\nwrote %s\n      %s\n      %s"
          % (os.path.relpath(OUT, ROOT), os.path.relpath(COVERAGE, ROOT),
             os.path.relpath(DISCREPANCIES, ROOT)))
    if all(os.path.exists(p) for p in VALIDATION_LISTINGS.values()):
        write_overlap()
    return 0


if __name__ == "__main__":
    sys.exit(main())
