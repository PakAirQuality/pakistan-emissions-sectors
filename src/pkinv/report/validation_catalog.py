"""The unified validation catalog: existence, FRESHNESS, and one verdict language.

WHAT THIS REPLACES-AND-EXTENDS. validation_registry.build() gates existence and
row count and nothing else - it cannot see a verdict, and it cannot see that a
cited product is three weeks stale (nine registry-cited outputs are produced by
hand-run scripts, the exact stale-product class tests/test_sector_qa_checks.py
documents for the sector QA tables). This builder consumes the rc33 catalog
(data/validation_catalog.csv - the registry joined to the benchmark tasks, with
grain / producer / wired / verdict_adapter first-class) and adds the two gates
the old lane lacked, then writes the scorecard that makes validation a
step-by-step program:

  1. EXISTENCE (kept): every non-absent result_output must exist with rows.
  2. FRESHNESS (new): a result_output wired as a run_all phase must be at
     least as new as the build's first key output (the sentinel below) - a
     validation product older than the build did not participate in it and is
     reported stale, loudly. hand_run and makefile_target rows (the named
     standalone studies) are exempt; their age is PRINTED at build time, never
     written into the product, because an mtime-derived column would make the
     bytes differ between builds and the regeneration guards depend on
     determinism.
  3. VERDICTS (new): each product's legacy verdict column is found by probing a
     known column set and projected through pkinv.validation.verdicts.LEGACY_MAP
     - one language over six vocabularies, applied at read time, no legacy file
     rewritten.

Outputs:
  outputs/pakemis_validation_catalog.csv    per-catalog-row status - THE
                                            validation register since rc35 (the
                                            old validation_registry lane is
                                            retired; this file is its superset)
  outputs/pakemis_validation_scorecard.csv  the (property x grain) matrix -
                                            every cell either carries verdict
                                            tallies + the best independence
                                            achieved, or is a declared_absent
                                            ROADMAP row. Advancing validation
                                            step by step = turning one row.

Usage:  python3 -m pkinv.report.validation_catalog
"""

from pkinv.assets import asset_path
import json
import os
import hashlib

from pkinv.activity.store import read_rows
from pkinv.core.io import write_table
from pkinv.paths import DATA, OUTPUTS
from pkinv.validation import verdicts

CATALOG = asset_path(DATA, "validation_catalog.csv")
# The FIRST phase's key output: everything a build writes lands at or after
# it. Two hours of slack covers the longest build; a product older than that
# belongs to a previous build.
SENTINEL = asset_path(OUTPUTS, "national_totals_2024.csv")
SLACK_S = 2 * 3600.0
OUT = asset_path(OUTPUTS, "pakemis_validation_catalog.csv")
SCORECARD = asset_path(OUTPUTS, "pakemis_validation_scorecard.csv")

# The verdict-bearing columns the prober recognises, in probe order. A file
# carrying none of them is metric_only - its numbers are the product and the
# projection reports that honestly rather than inventing a pass.
VERDICT_COLUMNS = ("verdict", "within_0.5_2.0x", "closes", "passed", "agrees",
                   "status", "flag", "band", "validation_status")

GRAINS = ("national", "sector", "category", "province", "district", "cell",
          "month", "month_district", "facility", "point", "worksheet_cell",
          "sample")
PROPERTIES = ("magnitude", "timing", "geography")


def _verified_outputs():
    """Ephemeral evidence from producers verified in this developer invocation."""
    path = os.environ.get("PKINV_BUILD_VERIFIED_OUTPUTS")
    if not path:
        return _seeded_outputs()
    try:
        with open(path, encoding="utf-8") as handle:
            proof = json.load(handle)
        root = os.path.realpath(os.path.dirname(OUTPUTS))
        if (proof.get("schema") == "pkinv.verified_outputs/v1" and proof.get("root") == root
                and isinstance(proof.get("outputs"), dict)):
            return proof["outputs"]
    except (OSError, ValueError, AttributeError):
        pass
    return {}


def _seeded_outputs():
    """A clean reproduction's seeded products, each verified against its release digest
    before the build began (logs/seeded_products.json, written by the seeder). A seeded
    product keeps the mtime of the release it came from, so the age gate alone would call a
    source-phase product such as the HTAP comparison stale in every clean rebuild; its
    digest is the proof it is the released bytes. Absent outside a reproduction tree."""
    receipt = os.path.join(os.path.dirname(OUTPUTS), "logs", "seeded_products.json")
    try:
        with open(receipt, encoding="utf-8") as handle:
            return {row["path"]: row["sha256"] for row in json.load(handle)
                    if row.get("path") and row.get("sha256")}
    except (OSError, ValueError, TypeError, KeyError):
        return {}


def _content_verified(path, proof):
    rel = os.path.relpath(path, os.path.dirname(OUTPUTS))
    expected = proof.get(rel)
    if not expected:
        return False
    try:
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
        return digest.hexdigest() == expected
    except OSError:
        return False


def _project(value):
    return verdicts.LEGACY_MAP.get(str(value).strip(), None)


def _verdicts_of(path, row):
    """(verdict tally dict, mode) for one product, via adapter or probing."""
    adapter = row["verdict_adapter"]
    if adapter in ("spearman_json",):
        blob = json.load(open(path, encoding="utf-8"))
        rho = blob.get("spearman_rho") or blob.get("spearman_vs_cattle")
        if rho is None:
            return {}, "metric_only"
        return {verdicts.PASS if float(rho) >= 0.5 else verdicts.REVIEW: 1}, "adapter"
    if adapter == "spearman_csv_banner":
        # the rho lives in the banner comment; the rows are the per-district detail
        with open(path, encoding="utf-8") as handle:
            banner = [l for l in handle if l.startswith("#")]
        text = " ".join(banner)
        import re
        m = re.search(r"rho\s+(-?[\d.]+)", text)
        if not m:
            return {}, "metric_only"
        return {verdicts.PASS if float(m.group(1)) >= 0.5
                else verdicts.REVIEW: 1}, "adapter"
    rows = read_rows(path)
    if not rows:
        return {}, "empty"
    col = next((c for c in VERDICT_COLUMNS if c in rows[0]), None)
    if col is None:
        return {}, "metric_only"
    tally = {}
    for r in rows:
        v = _project(r[col])
        if v is None:
            continue
        tally[v] = tally.get(v, 0) + 1
    return tally, ("column:%s" % col if tally else "metric_only")


def build():
    """(catalog rows, age notes). The rows are the PRODUCT and must be
    deterministic - an mtime-derived age in the CSV would make every build's
    bytes differ and light up the regeneration guards - so ages go only into
    the notes, which main() prints and nothing hashes."""
    catalog = read_rows(CATALOG)
    verified = _verified_outputs()
    sentinel_mtime = (os.path.getmtime(SENTINEL)
                      if os.path.exists(SENTINEL) else None)
    out, problems, notes = [], [], []
    for row in catalog:
        result = dict(row)
        fname = row["result_output"]
        if row["wired"] == "declared_absence" or fname in ("none", ""):
            result.update({"exists": "declared_absent", "rows_live": 0,
                           "fresh": "", "verdict_tally": "", "verdict_mode": ""})
            out.append(result)
            continue
        path = asset_path(OUTPUTS, fname)
        if not os.path.exists(path):
            problems.append("%s: %s missing" % (row["validation_id"], fname))
            continue
        rows_live = (len(read_rows(path)) if path.endswith(".csv")
                     else 1 if os.path.getsize(path) else 0)
        if rows_live == 0:
            problems.append("%s: %s is empty" % (row["validation_id"], fname))
            continue
        mtime = os.path.getmtime(path)
        age_days = ""
        if sentinel_mtime is not None:
            fresh = mtime >= sentinel_mtime - SLACK_S
            age_days = "%.1f" % ((sentinel_mtime - mtime) / 86400.0)
        else:
            fresh = True
        # Only run_all phases are regenerated by every build; a makefile_target
        # here is a named standalone study (aviation-study, road graph), which
        # gets the hand_run treatment: exempt from the gate, age printed.
        if row["wired"] == "run_all_phase":
            if not fresh and _content_verified(path, verified):
                fresh = True
            if not fresh:
                problems.append(
                    "%s: %s is STALE (%s days older than the build sentinel) - "
                    "a wired validation must be regenerated by the build that "
                    "cites it" % (row["validation_id"], fname, age_days))
                continue
            fresh_out = "yes"
        else:
            fresh_out = "exempt"
            if not fresh:
                notes.append("%s: %s last regenerated %s days before this "
                             "build (hand-run lane)"
                             % (row["validation_id"], fname, age_days))
        tally, mode = ({}, "json") if path.endswith(".json") and \
            not row["verdict_adapter"] else _verdicts_of(path, row)
        result.update({
            "exists": "yes", "rows_live": rows_live, "fresh": fresh_out,
            "verdict_tally": ";".join("%s=%d" % kv for kv in sorted(tally.items())),
            "verdict_mode": mode,
        })
        out.append(result)
    if problems:
        raise SystemExit("validation catalog gate:\n  " + "\n  ".join(problems))
    return out, notes


def scorecard(rows):
    """The (property x grain) matrix, empty cells as declared_absent roadmap rows."""
    cells = {}
    for r in rows:
        key = (r["property_tested"], r["grain"])
        cells.setdefault(key, []).append(r)
    rank = {"large": 3, "partial": 2, "none": 1, "not-applicable": 0}
    out = []
    for prop in PROPERTIES:
        for grain in GRAINS:
            members = cells.get((prop, grain), [])
            live = [m for m in members if m.get("exists") == "yes"]
            absent = [m for m in members if m.get("exists") == "declared_absent"]
            if not members:
                out.append({"property_tested": prop, "grain": grain,
                            "validations": 0, "verdict_tally": "",
                            "best_independence": "",
                            "status": verdicts.DECLARED_ABSENT,
                            "note": "no validation exists for this cell; the "
                                    "absence is the registered fact and this row "
                                    "is the roadmap entry"})
                continue
            tally = {}
            for m in live:
                for pair in (m["verdict_tally"] or "").split(";"):
                    if "=" in pair:
                        k, v = pair.split("=")
                        tally[k] = tally.get(k, 0) + int(v)
            best = max((m["independence_class"] for m in live),
                       key=lambda c: rank.get(c, -1), default="")
            out.append({
                "property_tested": prop, "grain": grain,
                "validations": len(live),
                "verdict_tally": ";".join("%s=%d" % kv for kv in sorted(tally.items())),
                "best_independence": best,
                "status": ("covered" if live else verdicts.DECLARED_ABSENT),
                "note": ("%d declared-absent rows alongside" % len(absent)
                         if absent and live else
                         "declared absent by catalog row(s): %s"
                         % ",".join(m["validation_id"] for m in absent)
                         if absent else ""),
            })
    return out


MODULES = ("agriculture", "power", "transport", "waste", "residential", "fugitives",
           "ippu", "industry", "railways", "aviation")

# (calibration_or_validation, independence_class) -> what a row may claim, higher is more.
_CLAIM_RANK = {
    ("validation", "large"): 5, ("validation", "partial"): 4, ("validation", "none"): 3,
    ("corroboration", "large"): 3, ("corroboration", "partial"): 3,
    ("corroboration", "none"): 2,
    ("calibration", "large"): 2, ("calibration", "partial"): 2, ("calibration", "none"): 1,
}
_CLAIM_LABEL = {5: "validation/large", 4: "validation/partial", 3: "corroboration",
                2: "calibration-or-shared", 1: "calibration/none", 0: "declared-absence",
                -1: "none"}
_STATUS = {5: "validated", 4: "validated", 3: "corroborated", 2: "calibrated_only",
           1: "calibrated_only", 0: verdicts.DECLARED_ABSENT, -1: "unregistered_absence"}


def _claim_rank(row):
    if row.get("calibration_or_validation") == "declared-absence":
        return 0
    return _CLAIM_RANK.get((row.get("calibration_or_validation", ""),
                            row.get("independence_class", "")), 1)


def sector_scorecard(rows):
    """The (module x property) projection: 30 cells, each carrying its BEST row.

    rc37. The (property x grain) scorecard pools every engine, so it cannot say whether
    agriculture is validated; the sector axis exists only in the catalog's `module`
    column. Here a cell is as good as the best row that tests that property for that
    module, ranked by what the row is allowed to claim: an independent record scored
    the property (validation/large) > scored against shared inputs (validation/partial) >
    two readings of shared data agree (corroboration) > the comparison tuned the product
    (calibration) > a registered absence naming its candidate > no row at all - the
    silence this projection exists to expose as `unregistered_absence`.
    """
    by = {}
    for r in rows:
        by.setdefault((r["module"], r["property_tested"]), []).append(r)
    out = []
    for module in MODULES:
        for prop in PROPERTIES:
            members = by.get((module, prop), [])
            live = [m for m in members if m.get("exists") in ("yes", "exempt")]
            absent = [m for m in members if m.get("exists") == "declared_absent"]
            best = max(live, key=_claim_rank, default=None)
            rank = _claim_rank(best) if best else (0 if absent else -1)
            limit = (best or (absent[0] if absent else {})).get("interpretation_limit", "")
            out.append({
                "module": module,
                "property_tested": prop,
                "rows": len(members),
                "best_row": (best["validation_id"] if best else
                             ",".join(m["validation_id"] for m in absent)),
                "best_class": _CLAIM_LABEL[rank],
                "best_independence": best.get("independence_class", "") if best else "",
                "status": _STATUS[rank],
                "limit": limit[:200] if limit else
                         "no catalog row tests this property for this module - not even an "
                         "absence; the projection exists to make this silence a row",
            })
    return out


SECTOR_SCORECARD = asset_path(OUTPUTS, "pakemis_validation_sector_scorecard.csv")


def main():
    rows, notes = build()
    for note in notes:
        print("  age: %s" % note)
    write_table(OUT, list(rows[0].keys()), rows, banner=(
        "Per-catalog-row validation status: existence, freshness against the",
        "build sentinel, and every legacy verdict projected through",
        "pkinv.validation.verdicts. Built from data/validation_catalog.csv.",
    ))
    card = scorecard(rows)
    write_table(SCORECARD, list(card[0].keys()), card, banner=(
        "THE VALIDATION SCORECARD (rc33): the (property x grain) space, one row",
        "per cell. A covered cell carries its verdict tally and the best",
        "independence class achieved; an empty cell is a declared_absent",
        "ROADMAP row. Advancing validation step by step = turning one row.",
    ))
    covered = sum(1 for c in card if c["status"] == "covered")
    sectors = sector_scorecard(rows)
    write_table(SECTOR_SCORECARD, list(sectors[0].keys()), sectors, banner=(
        "THE SECTOR SCORECARD (rc37): the (module x property) projection of the",
        "catalog, one row per cell carrying its BEST row and what that row may",
        "claim - validated (an independent or partially independent record scored",
        "the property), corroborated, calibrated_only, declared_absent, or",
        "unregistered_absence (no row at all). The sector passes turn these rows.",
    ))
    validated = sum(1 for c in sectors if c["status"] == "validated")
    large = sum(1 for c in sectors if c["best_class"] == "validation/large")
    print("validation catalog -> %s (%d assets) | scorecard -> %s "
          "(%d/%d cells covered) | sector scorecard -> %s (%d/%d validated, %d large)"
          % (OUT, len(rows), SCORECARD, covered, len(card),
             SECTOR_SCORECARD, validated, len(sectors), large))


if __name__ == "__main__":
    main()
