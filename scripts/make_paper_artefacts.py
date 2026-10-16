#!/usr/bin/env python3
"""The national manuscript's tables and figures as STORED QUERIES against the semantic release.

v1.0.0 Wave 4 (part B). paper_national/queries/paper_artefacts.csv registers every table and
figure of the national paper; this script opens the semantic release (verified against its
contract), runs each registered row's query through pakemis_query, and writes:

  paper_national/sections/gen_<id>.tex          a table body (or value macros) the section
                                                inputs - every number a `display` string of
                                                an envelope, first line a provenance comment
  outputs/paper_figure_data/<id>.csv            the cells a figure draws, canonical CSV
  outputs/paper_figures/<image>.png + .pdf      the figure, deterministic bytes
  paper_national/figures/<image>.png            the same PNG (what sync_figures would copy)
  outputs/pakemis_paper_artefact_hashes.csv     the sidecar: per artefact the params and
                                                result digests, receipt and output hashes

Registered outputs this script writes (tests/paper_numbers/quantity_policy.py exempts them
from the every-digit rule by reading the registry; test_every_generated_section_has_a_live_
generator asks the generator to NAME them): gen_tab_categorygas.tex, gen_tab_completeness.tex.

Rows of kind=static are the tables and figures pakemis_query cannot answer yet; the registry
says what blocks each, the sidecar records a hash of the inline source (the table block or
the image file), and --check fails if that source moved without the registry noticing.
Nothing numerical is computed here: the renderers (pkinv.report.paper_tables,
pkinv.report.paper_figures) print and draw what the envelopes carry.

Usage:  python3 scripts/make_paper_artefacts.py [--check] [--root DIR] [--out DIR]
  --root DIR   the repository (default: this script's parent)
  --out DIR    write under DIR instead of the repository (the same relative layout)
  --check      regenerate into a temporary directory and exit 1 on any byte difference
"""
import argparse
import csv
import filecmp
import hashlib
import io
import json
import os
from pkinv.paths import PAPER_NATIONAL_QUERIES  # noqa: E402
from pkinv.paths import PAPER_NATIONAL_REPORT_REL, PAPER_NATIONAL_REL  # noqa: E402
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(DEFAULT_ROOT, "src"))

from pkinv.assets import asset_path

from pakemis_query import Engine, Release  # noqa: E402
from pakemis_query import functions as F  # noqa: E402
from pakemis_query.models import (CompletenessRequest, EvidenceRequest, QueryEmissions,  # noqa: E402
                                  SpatialLineageRequest, TimeseriesRequest, TransferRequest,
                                  UncertaintyRequest)

REGISTRY = asset_path(PAPER_NATIONAL_QUERIES, "paper_artefacts.csv")
SEMANTIC = asset_path("outputs", "semantic")
SIDECAR = asset_path("outputs", "pakemis_paper_artefact_hashes.csv")
FIGURE_DATA = asset_path("outputs", "paper_figure_data")
FIGURES = asset_path("outputs", "paper_figures")
# TWO ROOTS, because the registry's paths carry their own subdirectory: a row writing
# sections/gen_tab_x.tex belongs to the SHIPPED VERSION, while one writing
# figures/fig_x.png belongs to the shared figures directory every version draws from.
# One string served both while the article sat at paper_national/; it cannot now.
PAPER = PAPER_NATIONAL_REPORT_REL
PAPER_SHARED = PAPER_NATIONAL_REL


def _paper_root(relative):
    """Which of the two roots a registry path belongs under."""
    return PAPER_SHARED if relative.startswith(("figures/", "versions/")) else PAPER
SIDECAR_FIELDS = ("artefact_id", "kind", "query_function", "params_sha256", "result_sha256",
                  "receipt", "output_file", "output_sha256", "image_sha256")
DATA_FIELDS = ("artefact_id", "query_index", "cell_index", "group_json", "exact", "display",
               "unit", "extra_json")
KINDS = ("table", "figure", "static")
STANDARD_CELL_KEYS = ("exact", "value", "display", "unit", "result_row_ids", "formula", "group")
TUPLE_FIELDS = ("periods", "gases", "sectors", "ipcc_codes", "categories", "streams",
                "geography_ids", "months", "group_by", "notation_keys")


# --- registry ------------------------------------------------------------------------------

def canonical(params):
    return json.dumps(params, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_registry(root):
    path = asset_path(root, REGISTRY)
    with open(path, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        params = json.loads(row["query_params"])
        if canonical(params) != row["query_params"]:
            raise ValueError("%s: query_params is not canonical JSON (sorted keys, compact)"
                             % row["artefact_id"])
        if row["kind"] not in KINDS:
            raise ValueError("%s: kind %r" % (row["artefact_id"], row["kind"]))
        if not 1 <= int(row["essd_section"]) <= 10:
            raise ValueError("%s: essd_section %r" % (row["artefact_id"], row["essd_section"]))
        row["_params"] = params
    return rows


# --- queries -------------------------------------------------------------------------------

def _q(d):
    d = dict(d)
    for k in TUPLE_FIELDS:
        if k in d:
            d[k] = tuple(d[k])
    return QueryEmissions(**d)


def run_query(engine, fn, params):
    """One params object -> one envelope, through the public functions of the contract."""
    if fn == "query_emissions":
        return engine.query_emissions(_q(params))
    if fn == "get_timeseries":
        return F.get_timeseries(engine, TimeseriesRequest(query=_q(params.get("query", {})),
                                                          step=params.get("step", "annual")))
    if fn == "get_uncertainty":
        return F.get_uncertainty(engine, UncertaintyRequest(**params))
    if fn == "get_completeness":
        d = dict(params)
        d["notation_keys"] = tuple(d.get("notation_keys", ()))
        d["ipcc_codes"] = tuple(d.get("ipcc_codes", ()))
        return F.get_completeness(engine, CompletenessRequest(**d))
    if fn == "get_evidence":
        return F.get_evidence(engine, EvidenceRequest(**params))
    if fn == "get_spatial_lineage":
        return F.get_spatial_lineage(engine, SpatialLineageRequest(**params))
    if fn == "get_cross_sector_transfer":
        return F.get_cross_sector_transfer(engine, TransferRequest(**params))
    raise KeyError("%s is not a function this script can store" % fn)


def run_row(engine, row):
    """The envelopes of one registry row: query_params is one object or a list of them."""
    params = row["_params"]
    objects = params if isinstance(params, list) else [params]
    return [run_query(engine, row["query_function"], p) for p in objects]


def result_digest(envelopes):
    return sha256_text("".join(e["result_sha256"] for e in envelopes))


def receipts(envelopes):
    return ";".join(e["receipt"] for e in envelopes)


# --- writers -------------------------------------------------------------------------------

def header_line(row, envelopes, release):
    return ("%% GENERATED by scripts/make_paper_artefacts.py from paper_artefacts.csv: "
            "query=%s params_sha256=%s result_sha256=%s release=%s receipt=%s -- do not edit"
            % (row["query_function"], sha256_text(row["query_params"]),
               result_digest(envelopes), release.release_id, receipts(envelopes)))


def figure_data_text(row, envelopes):
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=DATA_FIELDS, lineterminator="\n")
    writer.writeheader()
    for qi, env in enumerate(envelopes):
        for ci, cell in enumerate(env["values"]):
            extra = {k: v for k, v in cell.items() if k not in STANDARD_CELL_KEYS}
            writer.writerow({"artefact_id": row["artefact_id"], "query_index": qi,
                             "cell_index": ci,
                             "group_json": canonical(cell.get("group", {})),
                             "exact": cell["exact"], "display": cell["display"],
                             "unit": cell["unit"], "extra_json": canonical(extra)})
    return buf.getvalue()


def _write_text(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        handle.write(text)


def _table_block(text, label):
    for m in re.finditer(r"\\begin\{table\*?\}.*?\\end\{table\*?\}", text, re.S):
        if "\\label{%s}" % label in m.group(0):
            return m.group(0)
    raise KeyError("no table labelled %s" % label)


def static_hash(root, row):
    """The hash the sidecar records for a static row: a table block's text, or an image
    file's bytes. Empty for a row whose source is pending."""
    params = row["_params"]
    source = params.get("source", "")
    if not source:
        return ""
    path = asset_path(root, _paper_root(source), source)
    if "label" in params and source.endswith(".tex"):
        text = open(path, encoding="utf-8").read()
        return sha256_text(_table_block(text, params["label"]))
    return sha256_file(path)


def build(root, out, engine, release, rows):
    """Write every artefact under `out`; return the sidecar rows."""
    from pkinv.report import paper_figures, paper_tables
    sidecar = []
    for row in rows:
        entry = {"artefact_id": row["artefact_id"], "kind": row["kind"],
                 "query_function": row["query_function"],
                 "params_sha256": sha256_text(row["query_params"]), "result_sha256": "",
                 "receipt": "", "output_file": row["output_file"], "output_sha256": "",
                 "image_sha256": ""}
        if row["kind"] == "static":
            entry["result_sha256"] = static_hash(root, row)
            entry["output_sha256"] = entry["result_sha256"]
            if row["image_file"]:
                entry["image_sha256"] = entry["result_sha256"]
            sidecar.append(entry)
            continue
        envelopes = run_row(engine, row)
        entry["result_sha256"] = result_digest(envelopes)
        entry["receipt"] = receipts(envelopes)
        if row["kind"] == "table":
            lines = paper_tables.RENDERERS[row["renderer"]](envelopes, release)
            text = header_line(row, envelopes, release) + "\n" + "\n".join(lines) + "\n"
            path = asset_path(out, _paper_root(row["output_file"]),
                              row["output_file"])
            _write_text(path, text)
            entry["output_sha256"] = sha256_text(text)
        else:
            data = figure_data_text(row, envelopes)
            data_path = asset_path(out, FIGURE_DATA, row["artefact_id"] + ".csv")
            _write_text(data_path, data)
            entry["output_sha256"] = sha256_text(data)
            png = asset_path(out, FIGURES, row["image_file"])
            pdf = os.path.splitext(png)[0] + ".pdf"
            paper_figures.DRAWERS[row["renderer"]](envelopes, png, pdf)
            entry["image_sha256"] = sha256_file(png)
            paper_png = asset_path(out, _paper_root(row["output_file"]),
                                   row["output_file"])
            os.makedirs(os.path.dirname(paper_png), exist_ok=True)
            shutil.copyfile(png, paper_png)
        sidecar.append(entry)
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=SIDECAR_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(sidecar)
    _write_text(asset_path(out, SIDECAR), buf.getvalue())
    return sidecar


def written_files(out):
    found = []
    for folder, _dirs, names in os.walk(out):
        for name in names:
            found.append(os.path.relpath(asset_path(folder, name), out))
    return sorted(found)


def check(root, out_tmp):
    """Every file the fresh build wrote must exist byte-identical under root."""
    problems = []
    for rel in written_files(out_tmp):
        held = asset_path(root, rel)
        if not os.path.exists(held):
            problems.append("%s: missing" % rel)
        elif not filecmp.cmp(asset_path(out_tmp, rel), held, shallow=False):
            problems.append("%s: differs" % rel)
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--root", default=DEFAULT_ROOT)
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)
    root = os.path.abspath(args.root)
    rows = read_registry(root)
    # Opened WITHOUT the release manifest on purpose: the manifest's commit would enter every
    # envelope's context and so every receipt, and the manifest hashes the sidecar that records
    # those receipts - a circle with no fixpoint (the same one that keeps the papers out of the
    # manifest). The release id and the table digests identify the release; the commit is the
    # manifest's to state.
    release = Release.open(asset_path(root, SEMANTIC), verify=True)
    engine = Engine(release)
    if args.check:
        tmp = tempfile.mkdtemp(prefix="paper_artefacts_")
        try:
            build(root, tmp, engine, release, rows)
            problems = check(root, tmp)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        if problems:
            print("paper artefacts do not reproduce from the registry:\n  " + "\n  ".join(problems))
            return 1
        print("paper artefacts reproduce (%d registry rows)" % len(rows))
        return 0
    out = os.path.abspath(args.out) if args.out else root
    sidecar = build(root, out, engine, release, rows)
    kinds = {}
    for entry in sidecar:
        kinds[entry["kind"]] = kinds.get(entry["kind"], 0) + 1
    print("Paper artefacts -> %s (%s; release %s)"
          % (os.path.relpath(asset_path(out, SIDECAR), os.getcwd()),
             ", ".join("%d %s" % (n, k) for k, n in sorted(kinds.items())), release.release_id))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
