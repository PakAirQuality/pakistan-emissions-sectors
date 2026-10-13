"""Build pakemis_verification_external/ - one zip per sector, sources AND results.

WHY. The bundle handed an outside reviewer the held DOCUMENTS a sector rests on and nothing
else: ten zips, 8.5 GB, every one of them input-side only. A reviewer could re-read the OGRA
table the transport engine consumes and could not see one number the engine produced from it.
The results were in the repository the whole time; the bundle simply never carried them, and
because the bundle had no builder - it was assembled by hand and gitignored - nothing could
say so.

WHAT A BUNDLE NOW CONTAINS.

  manifest.csv            the source-side manifest (unchanged schema: path, bytes, sha256 and
                          the two registry notes) - what the sector rests on
  sources/, data/         those documents themselves
  outputs/                every shipped file this sector's own code writes, verbatim, with
  outputs/manifest.csv    the role each one declares (data/artifact_roles.csv) beside it
  results/                READABLE views: the sector's totals, its streams, its nine-year
                          series, its provinces and districts, its months, its interval, its
                          air species, and its activity data at the grain a reader asks about
                          ("the ten highest-fleet districts of Punjab, by vehicle class")
  README.md               what to open first and what each file may be used to claim

WHERE EACH SIDE COMES FROM, and why neither is hand-listed here.

  SOURCES   data/verification_bundle_sources.csv - the hand selection, frozen out of the
            rc47 bundle and collapsed to 109 tree/directory/file rules. The builder reports
            drift against files_at_freeze rather than silently shipping more or less.

  OUTPUTS   DERIVED, not declared: a file belongs to a sector when the sector's own package
            under src/pkinv/sectors/<sector>/ is the only place in src/ or scripts/ that
            names it - the same static test scripts/audit_outputs.py uses to prove every
            output has a writer, run the other way round to ask WHOSE. A name two sectors
            write, or none, is national and is reported, never guessed at.

  RESULTS   Computed through the published query core (src/pakemis_query) against the
            semantic release, so a view in the bundle and the same figure in the manuscript
            are the same arithmetic, carrying the same receipt. The activity views are
            declared in data/verification_activity_views.csv.

Usage:  python3 scripts/build_verification_bundle.py [--sectors transport,power] [--out DIR]
        python3 scripts/build_verification_bundle.py --results-only   # keep the source side
        python3 scripts/build_verification_bundle.py --dry-run        # list, build nothing
Exit:   1 if any declared rule resolves to nothing, or a sector ends with no results
"""
import argparse
import collections
import csv
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.assets import asset_path

from pkinv.core.filenames import name_patterns          # noqa: E402
from pkinv.core.io import read_rows, table_text         # noqa: E402

OUTPUTS = asset_path(ROOT, "outputs")
SEMANTIC = asset_path(OUTPUTS, "semantic")
BUNDLE = asset_path(ROOT, "pakemis_verification_external")
SOURCE_RULES = asset_path(ROOT, "data", "verification_bundle_sources.csv")
ACTIVITY_VIEWS = asset_path(ROOT, "data", "verification_activity_views.csv")
INVENTORY = asset_path(OUTPUTS, "pakemis_artifact_inventory.csv")
# NOT pakemis_*: release_manifest.PRODUCT_PATTERNS sweeps outputs/pakemis_*.csv, and
# this is a RECORD of a gitignored 8.5 GB bundle, not a product the release is for.
# Hashed in as a product it would churn the manifest every time the bundle rebuilt.
RECORD = asset_path(OUTPUTS, "verification_bundle_contents.csv")

SECTORS = ("agriculture", "aviation", "fugitives", "industry", "ippu",
           "power", "railways", "residential", "transport", "waste")

# The parquet twin of a semantic CSV and the PNG of a figure add bytes and no evidence: the
# CSV beside them IS the identity (data/artifact_roles.csv says so in as many words).
SKIP_ROLES = ("format_variant", "figure")

# A zip entry's date is (1980,1,1) and its mode fixed, so two builds of an unchanged tree
# produce identical archives. Without this the bundle's digest changes on every run and the
# release manifest cannot say anything about it.
EPOCH = (1980, 1, 1, 0, 0, 0)


# --------------------------------------------------------------------------- sources

def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def source_rules():
    """{sector: [(rule, kind, files_at_freeze)]} from the frozen registry."""
    out = collections.defaultdict(list)
    for row in read_rows(SOURCE_RULES):
        out[row["sector"]].append((row["rule"], row["kind"], int(row["files_at_freeze"])))
    return out


def expand(rule, kind):
    """The repo-relative files a rule names, in sorted order."""
    if kind == "file":
        path = asset_path(ROOT, rule)
        return [rule] if os.path.isfile(path) else []
    directory = rule[:-3] if kind == "tree" else rule[:-2]
    base = asset_path(ROOT, directory)
    if not os.path.isdir(base):
        return []
    found = []
    if kind == "tree":
        for dirpath, _dirnames, filenames in os.walk(base):
            for name in filenames:
                found.append(os.path.relpath(asset_path(dirpath, name), ROOT))
    else:
        for name in os.listdir(base):
            if os.path.isfile(asset_path(base, name)):
                found.append(asset_path(directory, name))
    return sorted(found)


def source_members(sector, rules):
    """([relative paths], [drift notes]) - the sector's declared source documents."""
    members, drift = [], []
    for rule, kind, frozen in rules[sector]:
        found = expand(rule, kind)
        if not found:
            drift.append("%s: %s resolves to NOTHING (froze at %d)" % (sector, rule, frozen))
        elif len(found) != frozen:
            drift.append("%s: %s now covers %d files, froze at %d"
                         % (sector, rule, len(found), frozen))
        members.extend(found)
    return sorted(set(members)), drift


def _notes():
    """(raw-manifest note by path, [(archived_path, 'primary :: note')]) for the manifest join."""
    raw = {r["path"]: r.get("note", "") for r in read_rows(asset_path(ROOT, "data", "raw_manifest.csv"))}
    docs = []
    for r in read_rows(asset_path(ROOT, "data", "source_documents.csv")):
        archived = (r.get("archived_path") or "").strip()
        if archived:
            docs.append((archived, "%s :: %s" % (r["primary_source"], r.get("note", ""))))
    return raw, docs


def source_manifest(members, notes):
    """The manifest.csv rows - the schema the rc47 bundle shipped, reproduced exactly."""
    raw, docs = notes
    rows = []
    for path in members:
        doc = ""
        for archived, note in docs:
            if path == archived or path.startswith(archived.rstrip("/") + "/"):
                doc = note
                break
        rows.append({"relative_path": path,
                     "bytes": str(os.path.getsize(asset_path(ROOT, path))),
                     "sha256": _sha256(asset_path(ROOT, path)),
                     "raw_manifest_note": raw.get(path, ""),
                     "source_document_note": doc})
    return rows


# --------------------------------------------------------------------------- outputs

def roles_by_artifact():
    """{artifact: (role, owner, description)} from the shipped inventory."""
    out = {}
    for row in read_rows(INVENTORY):
        out[row["artifact"]] = (row["role"], row["owner"], row["description"])
    return out


def _searched_source():
    texts = {}
    for base in ("src", "scripts"):
        for dirpath, dirnames, filenames in os.walk(asset_path(ROOT, base)):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            for name in filenames:
                if name.endswith((".py", ".sh")):
                    path = asset_path(dirpath, name)
                    with open(path, encoding="utf-8", errors="ignore") as handle:
                        texts[os.path.relpath(path, ROOT)] = handle.read()
    return texts


def output_owners():
    """({sector: [artifact]}, [artifact no single sector writes]).

    The audit_outputs test, asked whose rather than whether: an output belongs to the sector
    whose package is the ONLY one in src/ or scripts/ that names it, literally or with its
    digit runs generalised (names are built as "%s_totals_%d.csv" % (name, year)).
    """
    texts = _searched_source()
    sector_of = {p: p.split(os.sep)[3] for p in texts
                 if p.startswith(asset_path("src", "pkinv", "sectors") + os.sep)}
    owned, national = collections.defaultdict(list), []
    for name in sorted(os.listdir(OUTPUTS)):
        path = asset_path(OUTPUTS, name)
        if not os.path.isfile(path) or name.startswith("."):
            continue
        patterns = [re.compile(p) for p in name_patterns(name)]
        writers = {sector_of[p] for p, text in texts.items()
                   if p in sector_of and any(r.search(text) for r in patterns)}
        if len(writers) == 1:
            owned[writers.pop()].append(name)
        else:
            national.append(name)
    return owned, national


def output_members(sector, owned, roles):
    """[(artifact, role, owner, description)] - what this sector's own code writes."""
    rows = []
    for name in owned.get(sector, ()):
        role, owner, description = roles.get(name, ("unclassified", "", ""))
        if role in SKIP_ROLES:
            continue
        rows.append((name, role, owner, description))
    return rows


# --------------------------------------------------------------------------- results

VIEWS = (
    # (file, title, kind, request kwargs)
    ("01_totals_by_category.csv", "the sector's reference-year total, by IPCC category",
     "emissions", {"group_by": ("category",), "order_by": "value desc"}),
    ("02_by_stream.csv", "every source stream the sector prices, by category, subitem and gas",
     "emissions", {"group_by": ("category", "subitem", "gas"), "order_by": "value desc"}),
    ("03_annual_series.csv", "the nine published fiscal years",
     "emissions", {"periods": "ALL_FISCAL", "group_by": ("period_id", "category"), "order_by": ""}),
    ("04_provincial.csv", "the reference year split across provinces (ADM1)",
     "emissions", {"geography_level": "adm1", "group_by": ("province",), "order_by": "value desc"}),
    ("05_district_top20.csv", "the twenty highest-emitting districts (ADM2)",
     "emissions", {"geography_level": "adm2", "group_by": ("shape_id", "province"),
                   "order_by": "value desc", "limit": 20}),
    ("06_monthly.csv", "the twelve months of the reference year",
     "emissions", {"group_by": ("month",), "months": "ALL_MONTHS", "order_by": ""}),
    ("08_air_pollutants.csv", "the seven air species, in kilotonnes - never CO2e, never summed",
     "air", {"group_by": ("pollutant", "category"), "order_by": "value desc"}),
)


class Results:
    """The query core, opened once, asked the same seven questions per sector."""

    def __init__(self):
        from pakemis_query.engine import Engine
        from pakemis_query.release import Release
        self.release = Release.open(SEMANTIC, verify=True)
        self.engine = Engine(self.release)
        self.periods = tuple(p["period_id"] for p in self.release.dim("dim_period")
                             if p["basis"] == "fiscal")
        self.months = tuple(m["month"] for m in self.release.dim("dim_month"))
        # THE SPATIAL TABLES KEY ON shape_id, WHICH IS A geoBoundaries HASH. A district table
        # whose rows read "60131773B82635502895377" is not a result anybody can check, so the
        # name comes back from dim_geography and the id stays beside it for the join.
        self.shape_names = {g["shape_id"]: g["shape_name"]
                            for g in self.release.dim("dim_geography") if g["shape_id"]}

    def _flatten(self, envelope, keys):
        """Envelope values as CSV rows: the group keys, then the exact sum and its display.

        result_row_ids stay OUT of the table - a 7,000-id cell is not a result - and go to the
        receipt sidecar beside it, which is what a reader would re-run anyway.
        """
        rows = []
        for value in envelope["values"]:
            row = collections.OrderedDict()
            for key in keys:
                group = value.get("group", {}).get(key, "")
                if key == "shape_id":
                    row["district"] = self.shape_names.get(group, "(unnamed shape)")
                row[key] = group
            row["exact"] = value["exact"]
            row["display"] = value["display"]
            row["unit"] = value["unit"]
            row["rows_summed"] = value.get("n_rows", "")
            rows.append(row)
        return rows

    def view(self, sector, kind, kwargs):
        from pakemis_query.models import QueryAir, QueryEmissions
        kwargs = dict(kwargs)
        if kwargs.get("periods") == "ALL_FISCAL":
            kwargs["periods"] = self.periods
        if kwargs.get("months") == "ALL_MONTHS":
            kwargs["months"] = self.months
        keys = kwargs.get("group_by", ())
        if kind == "air":
            envelope = self.engine.query_air(QueryAir(sectors=(sector,), **kwargs))
        else:
            envelope = self.engine.query_emissions(QueryEmissions(sectors=(sector,), **kwargs))
        fields = []
        for key in keys:
            if key == "shape_id":
                fields.append("district")
            fields.append(key)
        fields += ["exact", "display", "unit", "rows_summed"]
        return self._flatten(envelope, keys), fields, envelope


def uncertainty_view(sector):
    """The sector's rows of the joint (category x resolution) uncertainty table, as shipped."""
    rows = [r for r in read_rows(asset_path(SEMANTIC, "fact_uncertainty.csv"))
            if r.get("module") == sector]
    if not rows:
        return None, None
    fields = [f for f in rows[0] if f != "result_row_id"]
    return [{f: r[f] for f in fields} for r in rows], fields


def activity_views():
    out = collections.defaultdict(list)
    for row in read_rows(ACTIVITY_VIEWS):
        out[row["sector"]].append(row)
    return out


def _numeric(text):
    try:
        return float(str(text).replace(",", ""))
    except (TypeError, ValueError):
        return None


def build_activity(spec):
    """One declared activity view: the whole table, or the top N groups per partition.

    top_n_pivot turns a long class column into columns ("2W", "3W", ...) so the answer to
    "the ten highest-fleet districts of Punjab, by vehicle class" is ten rows, not seventy.
    """
    path = asset_path(ROOT, spec["source_path"])
    if not os.path.isfile(path):
        return None, None, "%s does not exist" % spec["source_path"]
    rows = read_rows(path)
    partition = spec.get("partition_by") or ""
    column = spec.get("filter_column") or ""

    if column:
        value = spec["filter_value"]
        if value != "MAX":
            rows = [r for r in rows if r[column] == value]
        else:
            # MAX rather than a named year, so the view follows the panel instead of going
            # stale the first time a year is added and nobody edits the registry.
            #
            # AND MAX IS TAKEN WITHIN THE PARTITION, not across the file. The provincial
            # vehicle panels do not end together - Khyber Pakhtunkhwa runs to 2024, Punjab to
            # 2023, Sindh to 2022 - so one global max silently emptied three provinces out of
            # four and the first build of this view answered "the ten highest-fleet districts
            # of Punjab" with no Punjab in it. Each partition now gets its own latest year and
            # says which one on every row.
            rows = [r for r in rows if r[column] != ""]
            latest = {}
            for r in rows:
                key = r.get(partition, "") if partition else ""
                seen = _numeric(r[column])
                if seen is not None and (key not in latest or seen > latest[key][0]):
                    latest[key] = (seen, r[column])
            rows = [r for r in rows
                    if r[column] == latest.get(r.get(partition, "") if partition else "",
                                               (None, None))[1]]
    if spec["recipe"] == "table":
        fields = list(rows[0]) if rows else []
        return rows, fields, None

    group = spec["group_by"]
    top_n = int(spec["top_n"])
    if spec["recipe"] == "top_n_pivot":
        cls, val = spec["class_column"], spec["value_columns"]
        classes = sorted({r[cls] for r in rows})
        cells, stamp = collections.defaultdict(dict), {}
        for r in rows:
            key = (r.get(partition, ""), r[group])
            cells[key][r[cls]] = (cells[key].get(r[cls]) or 0) + (_numeric(r[val]) or 0)
            if column:
                stamp[key] = r[column]
        wide = []
        for (part, name), by_class in cells.items():
            row = collections.OrderedDict()
            if partition:
                row[partition] = part
            if column:
                row[column] = stamp[(part, name)]
            row[group] = name
            for c in classes:
                row[c] = by_class.get(c, "")
            row["total"] = sum(v for v in by_class.values())
            wide.append(row)
        value_fields, rows = classes, wide
    else:                                            # top_n_wide
        # A GROUP IS NOT A ROW. The captive register carries up to 266 connection records for
        # one district, and ranking its rows individually answered "the ten largest districts"
        # with ten records of the same size from the same district. Aggregate to the group
        # first, exactly as the pivot does, then rank.
        value_fields = [c.strip() for c in spec["value_columns"].split(";")]
        cells, stamp = collections.defaultdict(lambda: collections.defaultdict(float)), {}
        for r in rows:
            key = (r.get(partition, ""), r[group])
            for c in value_fields:
                cells[key][c] += _numeric(r.get(c)) or 0
            if column:
                stamp[key] = r[column]
        wide = []
        for (part, name), sums in cells.items():
            row = collections.OrderedDict()
            if partition:
                row[partition] = part
            if column:
                row[column] = stamp[(part, name)]
            row[group] = name
            for c in value_fields:
                row[c] = sums[c]
            wide.append(row)
        rows = wide

    # RANKING IS DECLARED, NOT ASSUMED. Summing the value columns is right for counts of one
    # kind (head by species, movements by class) and wrong twice over otherwise: gas_mmcfd +
    # capacity_mw adds MMCFD to megawatts, and pop_total + pop_rural + pop_urban counts every
    # person twice, because pop_total IS rural plus urban. Both shipped in the first build of
    # these views. rank_by names the column, or "sum" says the columns are commensurate.
    rank_by = spec.get("rank_by") or "sum"
    if rank_by == "sum":
        for row in rows:
            row["total"] = sum(_numeric(row.get(c)) or 0 for c in value_fields)
        rank_column, extra = "total", ["total"]
    else:
        rank_column, extra = rank_by, []

    # A BLANK KEY IS A ROW, NOT A GAP TO DROP: 37 of the register's 1,105 connections carry no
    # district, and they are labelled rather than filtered so the reader can see them.
    unlabelled = "(not recorded)"
    for row in rows:
        if partition and not row.get(partition):
            row[partition] = unlabelled
        if not row.get(group):
            row[group] = unlabelled

    by_part = collections.defaultdict(list)
    for row in rows:
        by_part[row.get(partition, "")].append(row)
    kept = []
    for part in sorted(by_part):
        ranked = sorted(by_part[part],
                        key=lambda r: -(_numeric(r.get(rank_column)) or 0))[:top_n]
        for rank, row in enumerate(ranked, 1):
            row["rank_in_" + (partition or "table")] = rank
            kept.append(row)
    fields = ([partition] if partition else []) + ([column] if column else []) + [group] + \
             list(value_fields) + extra + ["rank_in_" + (partition or "table")]
    return kept, fields, None


# --------------------------------------------------------------------------- assembly

def _csv_bytes(fields, rows, banner=None):
    return table_text(fields, rows, banner=banner, extrasaction="ignore").encode("utf-8")


def readme(sector, sources, outputs, results, drift):
    lines = [
        "# PakEmis external verification bundle - %s" % sector,
        "",
        "Everything an outside reader needs to check the %s sector: the documents it rests" % sector,
        "on, the files its code writes, and readable views of what it concluded.",
        "",
        "## Read in this order",
        "",
        "1. `results/00_derivation_chain.csv` - THE WALK. The numbers as the publisher printed",
        "   them, what was taken off them and why, what the engine finally used, and what came",
        "   out. Every row names the file it was read from; nothing in it is recomputed.",
        "2. `results/00_activity_factor_ledger.csv` - per stream, the activity quantities, the",
        "   conversions, the emission factors and the published emission, on one row.",
        "3. `results/01_totals_by_category.csv` onward - the answers at each grain.",
        "4. `outputs/manifest.csv` - the shipped files, each with the ROLE it declares.",
        "5. `manifest.csv` - the source documents, with a SHA-256 for every one.",
        "",
        "## What is here",
        "",
        "| part | files | what it is |",
        "| --- | --- | --- |",
        "| `manifest.csv` + `sources/` + `data/` | %d | the held documents, hashed |" % len(sources),
        "| `outputs/` | %d | what this sector's own code writes, verbatim |" % len(outputs),
        "| `results/` | %d | views computed through the published query core |" % len(results),
        "",
        "## What a view may be used to claim",
        "",
        "The `results/` tables are not a second inventory. Each is a query against the same",
        "semantic release the manuscripts cite, and each carries its receipt in the `.receipt.json`",
        "beside it: the release id, the exact request, and the SHA-256 of the result. A number",
        "here and the same number in the paper are the same arithmetic or one of them is a bug.",
        "",
        "Sums are exact decimal sums; `exact` is the full-precision value and `display` is the",
        "release's own rounding. Air species are kilotonnes of that species - never CO2e, and",
        "never added across species. District (ADM2) cells outside the reference year are annual.",
        "",
        "**A `results/` view carries only what is IN the national total.** Memo items, excluded",
        "streams and sensitivity configurations are real and are published - aviation's",
        "international LTO and military rows, fugitives' legacy production-only benchmark - but",
        "they sit outside the total by decision, so they do not appear here. They are in",
        "`outputs/<sector>_totals_*.csv`, each with the note saying why it is out. A view that",
        "looks short against the shipped table is showing you that boundary, not losing rows.",
        "",
        "A refusal is an answer. Where a grain does not exist for this sector the bundle carries",
        "`<view>.refused.txt` with the reason the release gives, rather than an empty file or a",
        "number computed to fill the gap.",
        "",
        "## Roles in `outputs/manifest.csv`",
        "",
        "`sector_headline` is a result the manuscripts quote; `canonical` is a published product;",
        "`diagnostic` is a check the build runs on itself; `intermediate` is a working file that",
        "no reader-facing claim rests on. The vocabulary is `data/artifact_roles.csv`.",
    ]
    if drift:
        lines += ["", "## Drift against the frozen source selection", ""] + \
                 ["- %s" % d for d in drift]
    return ("\n".join(lines) + "\n").encode("utf-8")


# --------------------------------------------------------------------------- the common part

COMMON = "_common"

# WHAT _common.zip CARRIES, and why it carries the WHOLE of outputs/ rather than the remainder.
#
# The first design shipped only the files no sector owns and asserted that those plus the
# sector zips partitioned outputs/. A partition is a property that can quietly stop holding -
# a writer moves, a new subdirectory appears - and the failure mode is a shipped product in no
# zip, which is the exact defect this round exists to fix. 380 files, 222 MB, were in that
# state: 86 CANONICAL products including the nine-year national panel, all four grid cubes,
# every Monte Carlo draw file, the validation catalog, and the claim matrix - the table saying
# which number backs each claim in the papers.
#
# Shipping every output once makes the guarantee structural instead of arithmetic: "every file
# in outputs/ is in _common.zip" cannot be true-except-for-one. The sector zips keep their own
# subset so a reviewer handed one sector need not open two archives to see its products; that
# duplication is about 10 MB of small CSVs and is worth it.
#
# THE RUNNABLE TREE COMES FROM THE DEPOSIT'S OWN RULE, not a second opinion about licensing.
# scripts/build_validation_package.py already decides what this project may ship, and
# data/raw/ and data/cache/ - 11 GB of held documents and the ODbL flight archive - are
# hash-only there. They stay hash-only here: the sector manifests carry their SHA-256.
HASH_ONLY = ("sources/", "data/cache/", "data/raw/")
CODE_TREES = ("src", "scripts", "tests")
ROOT_FILES = ("Makefile", "pyproject.toml", "run_all.py", "README.md", "CHANGELOG.md",
              "CITATION.cff", "requirements.txt", "requirements.lock", "LICENSE", "LICENSE-data")

# The process folder EVERY SECTOR ZIP carries, so one zip is a complete story: the code that
# built it, the registries that drove it, and the tests that hold both to their promises.
PROCESS_FILES = ("scripts/build_verification_bundle.py",
                 "src/pkinv/report/derivation_chain.py",
                 "data/verification_bundle_sources.csv",
                 "data/verification_activity_views.csv",
                 "data/verification_chain.csv",
                 "tests/test_verification_bundle.py",
                 "tests/test_derivation_chain.py")


def _tracked():
    """Every tracked file. RAISES rather than returning empty outside a git checkout.

    `git ls-files` exits 128 with an empty stdout when there is no repository, and the first
    version of this function passed that straight through: common_members() would then have
    built a _common.zip containing outputs/ and NOTHING ELSE - no code, no data, no docs, no
    papers - and said nothing. A package that silently omits the half a reviewer needs is worse
    than a build that stops, and the validation package tree is exactly a place this runs
    outside a checkout.
    """
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True)
    tracked = [p for p in out.stdout.split("\n") if p]
    if out.returncode != 0 or not tracked:
        raise RuntimeError(
            "git ls-files returned nothing in %s (exit %d): the common archive is assembled "
            "from the tracked tree, so this would have shipped outputs/ alone. Run the builder "
            "from a git checkout." % (ROOT, out.returncode))
    return tracked


def outputs_tree():
    """Every file under outputs/, recursively, repo-relative."""
    found = []
    for dirpath, _dirnames, filenames in os.walk(OUTPUTS):
        for name in filenames:
            if name.startswith("."):
                continue
            found.append(os.path.relpath(asset_path(dirpath, name), ROOT))
    return sorted(found)


def _rights_answer():
    """(data_family, {data_file}) - THE licence authority, borrowed, never re-decided here.

    pkinv.report.deposit_manifest already answers "may this project republish this file", from
    data/source_documents.csv first and its own declared families second, and it raises rather
    than defaulting. This package asks the same question of the same module. The first build of
    the common archive did not ask at all, and would have shipped 165 MB of third-party rasters
    and publications - three SPAM rice grids, the GHSL built-up tiles, WorldPop, and the MNFSR
    and NFDC PDFs - none of which this project may redistribute.
    """
    from pkinv.report import deposit_manifest as deposit
    registered = {r["data_file"] for r in read_rows(asset_path(ROOT, "data", "source_documents.csv"))}
    return deposit, registered


def may_ship(rel, deposit, registered):
    """(True, reason) if this data file may be redistributed; (False, reason) if it may not."""
    if rel in registered:
        return True, "registered in data/source_documents.csv"
    try:
        _licence, reason = deposit.data_family(rel)
        return True, reason
    except KeyError:
        return False, ("no redistribution answer: matches no source_documents row and no "
                       "deposit_manifest family")


def common_members():
    """([(arcname, path)], [(path, reason)]) - what ships, and what is withheld and why."""
    deposit, registered = _rights_answer()
    withheld = []
    members = [("outputs/" + rel[len("outputs/"):], rel) for rel in outputs_tree()]
    tracked = _tracked()
    for rel in tracked:
        if any(rel.startswith(h) for h in HASH_ONLY):
            continue
        top = rel.split("/")[0]
        if top in CODE_TREES:
            members.append(("code/" + rel, rel))
        elif rel in ROOT_FILES:
            members.append(("code/" + rel, rel))
        elif top == "data":
            allowed, reason = may_ship(rel, deposit, registered)
            if allowed:
                members.append(("data/" + rel[len("data/"):], rel))
            else:
                withheld.append((rel, reason))
        elif top == "docs":
            members.append((rel, rel))
        elif top == "validation_package":
            members.append(("validation/" + rel[len("validation_package/"):], rel))
        elif rel.startswith("papers/pdf/") or (rel.startswith("paper_national/")
                                               and rel.endswith(".pdf")):
            members.append(("papers/" + os.path.basename(rel), rel))
    seen, out = set(), []
    for arc, rel in sorted(members):
        if arc not in seen and os.path.isfile(asset_path(ROOT, rel)):
            seen.add(arc)
            out.append((arc, rel))
    return out, sorted(set(withheld))


def common_readme(members, roles):
    counts = collections.Counter(arc.split("/")[0] for arc, _rel in members)
    lines = [
        "# PakEmis external verification package - the common part",
        "",
        "The ten sector archives beside this one carry the documents each sector rests on and",
        "the results it reached. This one carries everything they share: every file the release",
        "writes, the code that wrote it, the data it reads, the method notes and the papers.",
        "",
        "| part | files | what it is |",
        "| --- | --- | --- |",
    ]
    for prefix, description in (
            ("outputs", "EVERY file this release writes - the national roll-ups, the semantic "
                        "layer, the four grid cubes, the Monte Carlo draws, the validation "
                        "catalog and the claim matrix included"),
            ("code", "src/, scripts/ and tests/ as committed, with the Makefile and run_all.py"),
            ("data", "the activity tables, parameters and registries the engines read"),
            ("docs", "the method note, the QA/QC note, completeness, and the contracts"),
            ("papers", "the built manuscripts and supplements"),
            ("validation", "reproduce.sh, validate.sh and the Dockerfile")):
        lines.append("| `%s/` | %d | %s |" % (prefix, counts.get(prefix, 0), description))
    lines += [
        "",
        "## What is NOT here, and where it is",
        "",
        "`data/raw/` and `data/cache/` - 11 GB of held documents and the ODbL flight archive -",
        "are not copied. The documents each sector rests on are in that sector's archive, with a",
        "SHA-256 for every one in its `manifest.csv`, so you can prove you hold the same file.",
        "",
        "## Reproducing",
        "",
        "`validation/reproduce.sh` rebuilds the products from the code and data here and diffs",
        "the result against `outputs/`. `validation/validate.sh` runs the test suite in `code/`.",
        "Neither needs this repository, and neither needs the network.",
    ]
    return ("\n".join(lines) + "\n").encode("utf-8")


def process_entries(roles):
    """{arcname: bytes} - the process folder, identical in every sector zip."""
    entries = {}
    rows = []
    for rel in PROCESS_FILES:
        path = asset_path(ROOT, rel)
        if not os.path.isfile(path):
            continue
        with open(path, "rb") as handle:
            entries["process/" + os.path.basename(rel)] = handle.read()
        rows.append({"file": os.path.basename(rel), "repo_path": rel,
                     "bytes": str(os.path.getsize(path)), "sha256": _sha256(path)})
    entries["process/manifest.csv"] = _csv_bytes(
        ["file", "repo_path", "bytes", "sha256"], rows,
        banner=("# The code and registries that built this archive, byte-identical to the repo.",))
    entries["process/METHOD.md"] = METHOD.encode("utf-8")
    return entries


METHOD = """# How this archive was built, and what each part may be used to claim

## The four stages of `results/00_derivation_chain.csv`

    1_source      the numbers as the publisher printed them, before any inventory decision
    3_correction  what was taken off, partitioned, re-anchored or selected, and why
    2_used        what the engine finally integrated
    4_final       the emissions

They are numbered 1, 3, 2, 4 because corrections happen TO the source and PRODUCE the used
value. The file is sorted by `step`, so reading it top to bottom reads correctly.

**Nothing in the chain is recomputed.** Every row is read from the file named in its
`evidence_file` column, so a chain row and its source agree by construction rather than by
luck. `tests/test_derivation_chain.py` asserts exactly that: every value must be findable as a
cell of the file its row names.

**A blank value is an absence the source published**, not a column the builder failed to read.
Transport's ledger names three claimants sitting inside the on-road residual - stationary
agricultural plant, captive generation, other retail non-road - with no quantity against any of
them. They are carried as rows so the absence is visible.

**A stage with no artifact is declared, never skipped.** Agriculture integrates head counts,
crop areas, residue mass, nitrogen and burned area in five unlike units and publishes no single
"what the engine used" table; its `2_used` stage is one row saying so.

## `results/00_activity_factor_ledger.csv`

Per source stream: the activity quantities, the conversions, the emission factors and the
published emission, on one row. Outside the fugitives segment ledger, nothing in this release
put those numbers beside each other before.

`reproduces` is `yes` ONLY where one distinct activity value times one distinct factor value
lands on the published mass within tolerance. Across 198 streams, 8 reproduce - all agriculture,
where head count times an IPCC factor is the whole method - 21 do not, and 169 are not
attempted because more than one product is definable. Searching candidate products for whichever
landed nearest would manufacture agreement rather than test it, so it is not done.

## Roles in `outputs/manifest.csv`

`sector_headline` is a result the manuscripts quote; `canonical` is a published product;
`derivation` is the audit chain; `diagnostic` is a check the build runs on itself;
`intermediate` is a working file no reader-facing claim rests on. The vocabulary is
`data/artifact_roles.csv`, shipped in `_common.zip`.

## Rebuilding this archive

    python3 scripts/build_verification_bundle.py           # all ten sectors and the common part
    python3 -m pkinv.report.derivation_chain               # the chains and ledgers
    python3 -m unittest discover tests -p "test_verification_bundle.py"
    python3 -m unittest discover tests -p "test_derivation_chain.py"

Zip entry timestamps are pinned, so an unchanged tree rebuilds to byte-identical archives.
"""


def _write_zip(target, copies, entries, held=None, keep=None):
    """One deterministic archive. Fixed dates and modes, so an unchanged tree rebuilds identically."""
    tmp = target + ".building"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for info in held or ():
            new = zipfile.ZipInfo(info.filename, date_time=EPOCH)
            new.compress_type = zipfile.ZIP_DEFLATED
            new.external_attr = 0o644 << 16
            zf.writestr(new, keep.read(info.filename))
        for arcname, path in sorted(copies):
            info = zipfile.ZipInfo(arcname, date_time=EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            with open(path, "rb") as handle:
                zf.writestr(info, handle.read())
        for arcname in sorted(entries):
            info = zipfile.ZipInfo(arcname, date_time=EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, entries[arcname])
    os.replace(tmp, target)


def build_common(out_dir, roles, dry_run=False):
    """_common.zip - everything the ten sector archives share, carried once."""
    members, withheld = common_members()
    copies = [(arc, asset_path(ROOT, rel)) for arc, rel in members]
    rows = [{"member": arc, "repo_path": rel,
             "role": roles.get(os.path.basename(rel), ("", "", ""))[0] if arc.startswith("outputs/") else "",
             "bytes": str(os.path.getsize(asset_path(ROOT, rel))),
             "sha256": _sha256(asset_path(ROOT, rel))} for arc, rel in members]
    entries = {
        "MANIFEST.csv": _csv_bytes(
            ["member", "repo_path", "role", "bytes", "sha256"], rows,
            banner=("# Every member of the common archive, with the role an output declares.",
                    "# Roles: data/artifact_roles.csv, shipped here under data/.",)),
        "README.md": common_readme(members, roles),
        # WITHHELD, NOT MISSING. A file this project may not redistribute is registered here
        # with its size, its digest and the reason - so a reviewer can prove they hold the
        # same file after fetching it from the publisher, which is the whole point of a
        # register and the reason withholding costs the package nothing.
        "WITHHELD.csv": _csv_bytes(
            ["repo_path", "bytes", "sha256", "reason"],
            [{"repo_path": rel, "bytes": str(os.path.getsize(asset_path(ROOT, rel))),
              "sha256": _sha256(asset_path(ROOT, rel)), "reason": reason}
             for rel, reason in withheld if os.path.isfile(asset_path(ROOT, rel))],
            banner=("# Files this project holds but may not republish: third-party rasters and",
                    "# publications with no stated redistribution terms. Each is named with its",
                    "# SHA-256 so you can verify you hold the same file after fetching it.",)),
    }
    entries.update(process_entries(roles))
    if not dry_run:
        _write_zip(asset_path(out_dir, COMMON + ".zip"), copies, entries)
    return members, withheld


def git_commit():
    out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                         capture_output=True, text=True)
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                           capture_output=True, text=True).stdout.strip()
    return (out.stdout.strip() or "unknown") + ("+dirty" if dirty else "")


def write_index(out_dir, built_from):
    """INDEX.csv and README.md at the top of the package - what a recipient meets first."""
    rows = []
    for name in sorted(os.listdir(out_dir)):
        if not name.endswith(".zip"):
            continue
        path = asset_path(out_dir, name)
        with zipfile.ZipFile(path) as zf:
            members = len(zf.namelist())
        rows.append({"archive": name, "part": "common" if name.startswith(COMMON) else "sector",
                     "members": str(members), "bytes": str(os.path.getsize(path)),
                     "sha256": _sha256(path), "built_from_commit": built_from})
    with open(asset_path(out_dir, "INDEX.csv"), "w", newline="", encoding="utf-8") as handle:
        handle.write(table_text(
            ["archive", "part", "members", "bytes", "sha256", "built_from_commit"], rows,
            banner=(
                "# Every archive in this package, with the commit it was built from.",
                "# Verify with: shasum -a 256 <archive> and compare.",
                "#",
                "# built_from_commit NAMES THE TREE THE ARCHIVES DESCRIBE, which is the tree as it",
                "# stood before this run wrote outputs/verification_bundle_contents.csv - the record",
                "# OF the bundle, not an input TO it. Committing that record moves HEAD one further,",
                "# so this column is deliberately one commit behind it rather than wrong. A '+dirty'",
                "# suffix means the tree carried uncommitted changes and the archives cannot be tied",
                "# to any commit at all; a package meant for a reviewer should not ship with it.",)))
    with open(asset_path(out_dir, "README.md"), "w", encoding="utf-8") as handle:
        handle.write(PACKAGE_README % {"commit": built_from, "archives": len(rows)})
    return rows


PACKAGE_README = """# PakEmis external verification package

Eleven archives: one per sector, plus `_common.zip` with everything they share.
Built from commit `%(commit)s`. `INDEX.csv` lists every archive with its SHA-256.

## Who this is for, and what it is not

This package is for a NAMED VERIFIER. It ships the held source documents themselves - 8.5 GB
of OGRA, NEPRA, PBS, NFDC and PCAA publications - so that a reviewer can re-read the table an
engine consumed rather than take its transcription on trust.

**It is therefore not the public deposit and must not be redistributed as one.** Most of those
documents carry no stated redistribution terms; `outputs/pakemis_deposit_manifest.csv` types
them `not-established`, and the Zenodo deposit built by `scripts/build_deposit_zip.py`
deliberately carries only a register row and a SHA-256 for each. That difference is the whole
distinction between the two packages, and it is a decision about redistribution, not about
evidence: the register lets anyone prove they hold the same document.

## Reading order

1. `<sector>.zip` -> `results/00_derivation_chain.csv` - the walk from the number the publisher
   printed, through every correction and why, to the number this inventory reports.
2. `results/00_activity_factor_ledger.csv` - per stream, the activity, the factor and the
   emission on one row.
3. `results/01_totals_by_category.csv` onward - the answers at each grain.
4. `<sector>.zip` -> `process/METHOD.md` - what each of those may be used to claim.
5. `<sector>.zip` -> `manifest.csv` and `sources/` - the documents, each with a SHA-256.
6. `_common.zip` -> `outputs/` - every product the release writes, the sector files included.
7. `_common.zip` -> `code/`, `docs/`, `papers/`, `validation/` - the software, the method
   notes, the manuscripts, and the scripts that re-run both.

## Checking it

    shasum -a 256 -c <(awk -F, 'NR>1 {print $5"  "$1}' INDEX.csv)   # every archive
    unzip -p transport.zip results/00_derivation_chain.csv | column -s, -t
    unzip _common.zip -d common && cd common && bash validation/validate.sh

Every archive is byte-reproducible: zip entry timestamps are pinned, so rebuilding from an
unchanged tree gives identical files and identical hashes.
"""


def build_sector(sector, rules, notes, owned, roles, results, activity, out_dir,
                 results_only=False, dry_run=False):
    members, drift = source_members(sector, rules)
    outs = output_members(sector, owned, roles)

    entries = {}                                     # arcname -> bytes  (generated files)
    copies = []                                      # (arcname, absolute path)

    # ---- results
    made = []
    for name, title, kind, kwargs in VIEWS:
        try:
            rows, fields, envelope = results.view(sector, kind, kwargs)
        except Exception as exc:                     # a typed refusal is an ANSWER, so record it
            entries["results/" + name.replace(".csv", ".refused.txt")] = (
                "%s\n\n%s: %s\n" % (title, type(exc).__name__, exc)).encode("utf-8")
            continue
        if not rows:
            continue
        entries["results/" + name] = _csv_bytes(
            fields, rows, banner=("# %s - %s" % (sector, title),
                                  "# computed through src/pakemis_query against %s; the receipt "
                                  "beside this file carries the exact request"
                                  % results.release.release_id,))
        entries["results/" + name.replace(".csv", ".receipt.json")] = (
            json.dumps({"request": json.loads(envelope["request"]),
                        "context": envelope["context"],
                        "citation": envelope["citation"],
                        "result_sha256": envelope["result_sha256"],
                        "limitations_hit": envelope.get("limitations_hit", [])},
                       indent=1, sort_keys=True, default=str) + "\n").encode("utf-8")
        made.append(name)

    # THE WALK GOES FIRST, at 00. It is copied rather than rebuilt, and it needs copying
    # explicitly: pkinv.report.derivation_chain writes it, and the ownership rule that fills
    # outputs/ only recognises a writer under src/pkinv/sectors/, so a report-layer product
    # named for a sector belongs to no sector and would reach no zip.
    for name, arc in (("%s_derivation_chain.csv" % sector, "results/00_derivation_chain.csv"),
                      ("%s_activity_factor_ledger.csv" % sector,
                       "results/00_activity_factor_ledger.csv")):
        path = asset_path(OUTPUTS, name)
        if os.path.isfile(path):
            with open(path, "rb") as handle:
                entries[arc] = handle.read()
            made.append(os.path.basename(arc))

    rows, fields = uncertainty_view(sector)
    if rows:
        entries["results/07_uncertainty.csv"] = _csv_bytes(
            fields, rows, banner=("# %s - the interval, by category and resolution" % sector,
                                  "# an ENVELOPE, not a sigma: read aggregation_rule before adding anything",))
        made.append("07_uncertainty.csv")

    for index, spec in enumerate(activity.get(sector, ()), 9):
        rows, fields, problem = build_activity(spec)
        name = "%02d_%s.csv" % (index, spec["view_id"])
        if problem:
            entries["results/" + name.replace(".csv", ".refused.txt")] = (
                "%s\n\n%s\n" % (spec["title"], problem)).encode("utf-8")
            continue
        entries["results/" + name] = _csv_bytes(
            fields, rows, banner=("# %s - %s" % (sector, spec["title"]),
                                  "# activity data, read from %s" % spec["source_path"],
                                  "# %s" % spec["note"] if spec.get("note") else "# ",))
        made.append(name)

    # ---- outputs
    manifest_rows = []
    for name, role, owner, description in outs:
        path = asset_path(OUTPUTS, name)
        copies.append(("outputs/" + name, path))
        manifest_rows.append({"artifact": name, "role": role, "owner": owner,
                              "bytes": str(os.path.getsize(path)), "sha256": _sha256(path),
                              "description": description})
    entries["outputs/manifest.csv"] = _csv_bytes(
        ["artifact", "role", "owner", "bytes", "sha256", "description"], manifest_rows,
        banner=("# The files %s's own code writes, with the role each declares." % sector,
                "# Roles and their promises: data/artifact_roles.csv.",))

    entries.update(process_entries(roles))
    entries["README.md"] = readme(sector, members, outs, made, drift)

    # ---- sources
    if not results_only:
        entries["manifest.csv"] = _csv_bytes(
            ["relative_path", "bytes", "sha256", "raw_manifest_note", "source_document_note"],
            source_manifest(members, notes))
        copies.extend((path, asset_path(ROOT, path)) for path in members)

    if dry_run:
        return members, outs, made, drift, entries

    target = asset_path(out_dir, sector + ".zip")
    if results_only and os.path.exists(target):
        keep = zipfile.ZipFile(target)
        # EVERY PART THIS RUN REBUILDS MUST BE EXCLUDED FROM THE CARRY-OVER, or the archive
        # gets two entries under one name - the stale one first, which is what most readers
        # would extract. process/ was missing from this list and is rebuilt on every run.
        held = [i for i in keep.infolist()
                if not i.filename.startswith(("results/", "outputs/", "process/"))
                and i.filename != "README.md"]
    else:
        keep, held = None, []
    _write_zip(target, copies, entries, held=held, keep=keep)
    if keep is not None:
        keep.close()
    return members, outs, made, drift, entries


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--sectors", default="", help="comma-separated subset")
    parser.add_argument("--out", default=BUNDLE)
    parser.add_argument("--results-only", action="store_true",
                        help="rebuild results/ and outputs/, carrying the source side over "
                             "from the existing zip - it skips re-hashing 5,720 documents, "
                             "but the archive is still rewritten, so it is not free")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    sectors = tuple(s.strip() for s in args.sectors.split(",") if s.strip()) or SECTORS
    unknown = [s for s in sectors if s not in SECTORS]
    if unknown:
        print("not sectors of this inventory: %s" % ", ".join(unknown))
        return 1
    os.makedirs(args.out, exist_ok=True)

    rules, notes = source_rules(), _notes()
    roles = roles_by_artifact()
    owned, national = output_owners()
    activity = activity_views()
    results = Results()

    record, drifted, empty = [], [], []
    for sector in sectors:
        members, outs, made, drift, entries = build_sector(
            sector, rules, notes, owned, roles, results, activity, args.out,
            results_only=args.results_only, dry_run=args.dry_run)
        drifted.extend(drift)
        if not made:
            empty.append(sector)
        print("%-12s sources %5d   outputs %3d   results %2d%s"
              % (sector, len(members), len(outs), len(made), "   DRIFT" if drift else ""))
        for name in made:
            record.append({"sector": sector, "part": "results", "member": "results/" + name})
        for name, role, _owner, _d in outs:
            record.append({"sector": sector, "part": "outputs", "member": "outputs/" + name,
                           "role": role})
        record.append({"sector": sector, "part": "sources", "member": "manifest.csv",
                       "role": "%d documents" % len(members)})

    if set(sectors) == set(SECTORS):
        common, withheld = build_common(args.out, roles, dry_run=args.dry_run)
        print("%-12s %5d members  (every output once, plus code, data, docs and papers)"
              % (COMMON, len(common)))
        if withheld:
            print("%-12s %5d withheld and registered in WITHHELD.csv (no redistribution answer)"
                  % ("", len(withheld)))
        for arc, rel in common:
            record.append({"sector": COMMON, "part": arc.split("/")[0], "member": arc,
                           "role": roles.get(os.path.basename(rel), ("", "", ""))[0]})
        if not args.dry_run:
            built_from = git_commit()
            index = write_index(args.out, built_from)
            print("wrote README.md and INDEX.csv (%d archives, commit %s)"
                  % (len(index), built_from))

    if not args.dry_run and set(sectors) == set(SECTORS) and not args.results_only:
        with open(RECORD, "w", newline="", encoding="utf-8") as handle:
            handle.write(table_text(
                ["sector", "part", "member", "role"], record, extrasaction="ignore",
                banner=("# What each pakemis_verification_external/<sector>.zip contains.",
                        "# Written by scripts/build_verification_bundle.py; the bundle itself is",
                        "# gitignored (8.5 GB of held documents), so this is the tracked record of it.",)))
        print("wrote %s (%d rows)" % (os.path.relpath(RECORD, ROOT), len(record)))

    print("\n%d outputs belong to no single sector (national or cross-cutting); they ship in "
          "%s.zip, which carries every output once" % (len(national), COMMON))
    if drifted:
        print("\nDRIFT against data/verification_bundle_sources.csv:")
        for line in drifted:
            print("  " + line)
    if empty:
        print("\nNO RESULTS BUILT for: %s" % ", ".join(empty))
    return 1 if empty or any("NOTHING" in d for d in drifted) else 0


if __name__ == "__main__":
    sys.exit(main())
