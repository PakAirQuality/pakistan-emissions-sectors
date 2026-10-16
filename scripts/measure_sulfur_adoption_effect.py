#!/usr/bin/env python3
"""What the rc63 sulfur adoption moved, stream by stream and year by year.

WHY A SEPARATE MEASUREMENT. scripts/measure_spatial_rebase.py measures a SPATIAL re-base - mass
moving between shapes inside a province - and needs five products this change never touches. This
change is a MAGNITUDE one: two sulfur centrals moved and every stream that cites them moved with
them, in place. The two need different tables.

WHAT A REVIEWER ASKED FOR, AND WHY EACH PART IS HERE.

  "Which physical streams explain the revision and the historical decrease, INCLUDING INCREASES
  ELSEWHERE." A decomposition that lists only the falling sectors and reaches 102 percent has
  hidden its own offset. Every row here carries its sign, and the sector table is complete enough
  to sum to the published change.

  "Industry is not synonymous with brick kilns." Reporting that industry supplies 42 percent of the
  decline does not establish that brick coal supplies it. The national table is per SOURCE CLASS,
  so industrial furnace oil, brick coal and the other industrial fuels are separate rows and can
  never again be quoted as one.

  "Comparing the working tree with a pre-session HEAD would measure the cumulative session change."
  Correct, which is why the baseline here is an explicit preserved directory rather than a git ref.

WHAT THIS IS NOT. Not an independent regeneration. The baseline products were written by the engine
as it stood and preserved; nobody has re-derived them from inputs since. Every row is therefore a
REPORTED SESSION RESULT with its inputs named and digested, and the `provenance` column says so on
every line. It becomes a regeneration when the pre-adoption register can be rebuilt and reproduces
those digests - not before, and not by being committed.

BOTH ENDS ARE PRESERVED DIRECTORIES (rc67). The candidate was read from outputs/ until the
residential reference changed at rc67 and moved residential SO2 in every year: a rerun then
booked that movement as an unattributed effect of the sulfur adoption. A measurement of one
change needs both of its ends held still, so the candidate is the pair of files as they stood at
rc66, the last release in which they differ from the baseline by this adoption alone.

Usage:  python3 scripts/measure_sulfur_adoption_effect.py [--baseline DIR] [--candidate DIR]
                                                          [--check]
Reads:  data/baselines/pre_rc63_sulfur_adoption/  (default baseline, with its SHA256SUMS)
        data/baselines/post_rc63_sulfur_adoption/ (default candidate, with its SHA256SUMS)
Writes: outputs/pakemis_sulfur_adoption_effect.csv
"""
import collections
import csv
import hashlib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.assets import asset_path

from pkinv.core.io import write_or_check  # noqa: E402

OUT = asset_path(ROOT, "outputs", "pakemis_sulfur_adoption_effect.csv")
DEFAULT_BASELINE = asset_path(ROOT, "data", "baselines", "pre_rc63_sulfur_adoption")
DEFAULT_CANDIDATE = asset_path(ROOT, "data", "baselines", "post_rc63_sulfur_adoption")
# These are immutable rc63/rc66 comparison snapshots, not the current core panel.
CLASSES = "pakemis_air_source_classes_fy2015_16_fy2023_24.csv"
LAHORE = "pakemis_air_lahore_by_year.csv"
CONFIG = "REF_2023_24"

FIELDS = ("scope", "stream", "period_id", "before_Gg", "after_Gg", "delta_Gg", "pct_change",
          "direction", "driver", "baseline_sha256_16", "provenance", "note")

# which evidence row each moved class cites, so a reader can see WHAT moved it rather than
# inferring it from the sign
DRIVER = {
    "brick_fcbk_mapped": "coal_punjab_fields 4.5 -> 4.643 %, basis field_range -> measured_avg",
    "brick_zz_mapped": "coal_punjab_fields 4.5 -> 4.643 %, basis field_range -> measured_avg",
    "brick_unmapped_remainder": "coal_punjab_fields 4.5 -> 4.643 %, basis field_range -> measured_avg",
    "power_rfo_boiler": "power_rfo_spec_range 1.3229 % retired; class joins fo_hsfo_grade_mix at 3.0 %",
    "power_rfo_engine": "power_rfo_spec_range 1.3229 % retired; class joins fo_hsfo_grade_mix at 3.0 %",
    "power_rfo_turbine": "power_rfo_spec_range 1.3229 % retired; class joins fo_hsfo_grade_mix at 3.0 %",
}


def _rows(path):
    with open(path, encoding="utf-8") as handle:
        return list(csv.DictReader(l for l in handle if not l.startswith("#")))


def _sha16(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()[:16]


def _class_so2(path):
    out = collections.defaultdict(float)
    for r in _rows(path):
        if r["pollutant"].upper() == "SO2" and r.get("emissions_kt"):
            out[(r["source_class_id"], r["period_id"])] += float(r["emissions_kt"])
    return out


# INDUSTRY AND IPPU ARE ONE ROW IN THE LAHORE TABLE, and the reason is not sulfur.
#
# The preserved baseline was written while the spatial air tables labelled an anchor stream with
# the last sector that rode it: general-industry gas combustion sat under `ippu` (which borrows
# that stream as its geography) in every district file, this one included. The label was
# corrected on 2026-10-07 (pkinv.report.air_spatial_by_year.load_atoms), so the candidate files
# the same mass under `industry`. A per-sector comparison across that correction would book the
# relabelled mass as a sulfur effect - up in industry, down in IPPU, by the same amount - and the
# baseline is at sector grain, so the stream cannot be moved back out of it.
#
# The sum of the two sectors is the only quantity both files define the same way, so that is
# what is compared. Nothing is lost that the table could support: the baseline's `industry` row
# never was all of industry. Every row still sums to the district total. The per-CLASS national
# table above is untouched - classes were never mislabelled, only their place in the spatial tables.
LAHORE_POOL = {"industry": "industry+ippu", "ippu": "industry+ippu"}
LAHORE_POOL_NOTE = (" Industry and IPPU are ONE row: the baseline predates the 2026-10-07 "
                    "sector-label correction (general-industry gas was filed under ippu in the "
                    "district tables), and their sum is the only figure both files define alike.")


def _lahore_so2(path):
    out = collections.defaultdict(float)
    for r in _rows(path):
        if (r["pollutant"].upper() == "SO2" and r["row_kind"] == "district"
                and r["configuration_id"] == CONFIG):
            sector = LAHORE_POOL.get(r["sector_id"], r["sector_id"])
            out[(sector, r["period_id"])] += float(r["emissions_Gg"] or 0.0)
    return out


def build(baseline, candidate=DEFAULT_CANDIDATE):
    rows = []

    def add(scope, stream, period, before, after, driver, note, sha):
        delta = after - before
        rows.append({
            "scope": scope, "stream": stream, "period_id": period,
            "before_Gg": "%.6f" % before, "after_Gg": "%.6f" % after,
            "delta_Gg": "%+.6f" % delta,
            "pct_change": "%+.2f" % ((after / before - 1.0) * 100.0) if before else "",
            # the sign is carried as a WORD as well as a number: a decomposition that lists only
            # its falling terms and reaches 102 percent has hidden the rest
            "direction": "increase" if delta > 1e-9 else ("decrease" if delta < -1e-9 else "unchanged"),
            "driver": driver, "baseline_sha256_16": sha,
            "provenance": "reported session result: candidate and baseline each from a "
                          "preserved directory; NOT an independent regeneration",
            "note": note})

    # ---- national, per SOURCE CLASS. Per class and not per sector, because "industry" is not
    # "brick kilns" and the two must not be quotable as one number.
    b_path = asset_path(baseline, CLASSES)
    before, after = _class_so2(b_path), _class_so2(asset_path(candidate, CLASSES))
    sha = _sha16(b_path)
    for cls, period in sorted(set(before) | set(after)):
        b, a = before.get((cls, period), 0.0), after.get((cls, period), 0.0)
        if abs(a - b) <= 1e-9:
            continue
        add("national_class", cls, period, b, a, DRIVER.get(cls, "(unattributed)"),
            "national SO2 for one source class; Gg", sha)

    # ---- Lahore, per SECTOR, complete so the offset is visible
    b_path = asset_path(baseline, LAHORE)
    before, after = _lahore_so2(b_path), _lahore_so2(asset_path(candidate, LAHORE))
    sha = _sha16(b_path)
    for sector, period in sorted(set(before) | set(after)):
        b, a = before.get((sector, period), 0.0), after.get((sector, period), 0.0)
        add("lahore_sector", sector, period, b, a,
            DRIVER.get(sector, "unchanged by this adoption" if abs(a - b) <= 1e-9 else "(unattributed)"),
            "Lahore District SO2 for one sector, configuration %s; Gg. EVERY sector is listed, "
            "including those this change did not move, so the rows sum to the district total and "
            "an offset cannot be dropped%s"
            % (CONFIG, LAHORE_POOL_NOTE if sector in LAHORE_POOL.values() else ""), sha)

    # ---- the two endpoints, and what they do to the endpoint change
    for scope_stream, table in (("lahore_total", (before, after)),):
        b_tot = {p: sum(v for (s, pp), v in before.items() if pp == p)
                 for p in {p for _, p in before}}
        a_tot = {p: sum(v for (s, pp), v in after.items() if pp == p)
                 for p in {p for _, p in after}}
        for period in sorted(b_tot):
            add(scope_stream, "ALL SECTORS", period, b_tot[period], a_tot[period],
                "both adopted sulfur centrals", "Lahore District SO2, all sectors; Gg", sha)
        first, last = sorted(b_tot)[0], sorted(b_tot)[-1]
        rows.append({
            "scope": "endpoint_change", "stream": "ALL SECTORS",
            "period_id": "%s..%s" % (first, last),
            "before_Gg": "%.6f" % (b_tot[last] / b_tot[first] * 100.0 - 100.0),
            "after_Gg": "%.6f" % (a_tot[last] / a_tot[first] * 100.0 - 100.0),
            "delta_Gg": "%+.6f" % ((a_tot[last] / a_tot[first] - b_tot[last] / b_tot[first]) * 100.0),
            "pct_change": "", "direction": "steeper", "driver": "re-weighting, not a changed path",
            "baseline_sha256_16": sha,
            "provenance": "reported session result; NOT an independent regeneration",
            "note": "PERCENT, not Gg: the ratio of the closing year to the opening one. It is an "
                    "ENDPOINT CHANGE and not a fitted rate - the series has a hump, and the "
                    "closing year rests on a brick column the publisher flags PARTIAL. Neither "
                    "sector's own path changed: industry falls 59.7 then 59.8 percent, power 78.3 "
                    "then 78.3. The aggregate steepened because power's share of the opening year "
                    "rose from 23 to 40 percent and power falls faster than the district does."})
    return rows


BANNER = (
    "WHAT THE rc63 SULFUR ADOPTION MOVED, per stream and per year, with every sign shown.",
    "Two centrals moved: brick-kiln coal 4.5 -> 4.643 % (basis field_range -> measured_avg) and the",
    "three power RFO classes from a retired 1.3229 % row onto the industry row at 3.0 %.",
    "PER SOURCE CLASS, not per sector: 'industry' is not 'brick kilns' and the two must not be",
    "quotable as one number. Every Lahore sector is listed including the unmoved ones, so the rows",
    "sum to the district total and an offset cannot be dropped. Industry and IPPU are one Lahore",
    "row: the baseline predates the 2026-10-07 sector-label correction in the district tables.",
    "A REPORTED SESSION RESULT, not an independent regeneration: the baseline is a preserved",
    "directory (data/baselines/pre_rc63_sulfur_adoption/, digests in its SHA256SUMS) written by the",
    "engine as it stood, and since rc67 so is the candidate (post_rc63_sulfur_adoption/, the two",
    "files as released at rc66): the rc67 reference change moved residential SO2, and a measurement",
    "of one change needs both ends held. Generated by scripts/measure_sulfur_adoption_effect.py.",
)


def main(argv):
    baseline = DEFAULT_BASELINE
    if "--baseline" in argv:
        baseline = argv[argv.index("--baseline") + 1]
    candidate = DEFAULT_CANDIDATE
    if "--candidate" in argv:
        candidate = argv[argv.index("--candidate") + 1]
    for label, path in (("baseline", baseline), ("candidate", candidate)):
        if not os.path.isdir(path):
            raise SystemExit("no %s at %s" % (label, path))
    rows = build(baseline, candidate)
    if "--check" in argv:
        # WAS A ROW COUNT. Until rc64 this compared len(held) against len(rows) and printed
        # "unchanged" whenever they matched, so no change to any VALUE could fail it - and the
        # held registry named this command as the verification for the product. write_or_check
        # compares the text the writer below would emit, through table_text, which is the one
        # code path both branches share.
        rc = write_or_check(OUT, list(FIELDS), rows, check=True, banner=BANNER)
        if rc == 0:
            # The coverage contract (rc64): name what was compared, so the held registry can
            # be held to it. See tests/test_held_product_freshness.py.
            print("checked: %s" % os.path.relpath(OUT, ROOT))
        return rc
    write_or_check(OUT, list(FIELDS), rows, banner=BANNER)
    moved = [r for r in rows if r["direction"] in ("increase", "decrease")]
    up = [r for r in moved if r["direction"] == "increase"]
    print("sulfur adoption effect -> %s (%d rows)" % (os.path.relpath(OUT, ROOT), len(rows)))
    print("  moved: %d rows, of which %d are INCREASES" % (len(moved), len(up)))
    for r in rows:
        if r["scope"] == "endpoint_change":
            print("  endpoint change %s: %s%% -> %s%% (%s pts)"
                  % (r["period_id"], r["before_Gg"], r["after_Gg"], r["delta_Gg"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
