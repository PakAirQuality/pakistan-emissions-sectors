#!/usr/bin/env python3
"""The claim matrix, resolved: every headline claim of the national manuscript held to the
release it describes (the v1.0.0 program's ESSD re-targeting, docs/essd_outline.md).

Reads   data/claim_matrix.csv - the registry: one row per headline claim, with the sentence
        as the prose prints it today, the quantity references into the existing claims
        machinery (claim: DOC_CLAIMS name / fact: product fact / registry: claims_registry
        row / table: label), the source pointer, the stored query and its parameters, the
        configuration, unit, rounding, evidence class, limitation label, technical notes
        and the artefact that shows it.
Writes  outputs/pakemis_claim_matrix.csv   the registry columns plus resolved_value,
                                            printed_value, tolerance, agrees, query_hash,
                                            receipt, semantic_release_id
        outputs/pakemis_claim_matrix.md    the same, readable, grouped by ESSD section
        paper_national/versions/<v>/generated/claim_matrix.tex   Supplement S5

HOW A ROW RESOLVES, in order: through pakemis_query when query_function is set (the
envelope's display is the resolved value, the receipt is recorded); else through the pointer
resolver (pkinv.report.claims - the claims-registry grammar); else through the DOC_CLAIMS
getter of the row's first claim: reference. The printed value is cut from the row's OWN
section file: by printed_pattern when the row carries one, otherwise by the DOC_CLAIMS
pattern of its first claim: reference. Agreement is the DOC_CLAIMS rule - half an ulp at the
printed precision plus the registered absolute tolerance of the claim (zero when the row has
no claim: reference); a strict half-ulp verdict is also recorded (agrees_strict).

THIS SCRIPT REPAIRS NOTHING. A disagreement is recorded as agrees=no and the script exits 0;
tests/paper_numbers/test_claim_matrix.py is what fails. --check renders into a temporary
directory and exits 1 if any of the three outputs differs from the tree's.

Usage:  python3 scripts/make_claim_matrix.py [--check] [--root DIR] [--out DIR]
"""

from pkinv.assets import asset_path
from pkinv.paths import PAPER_NATIONAL_MAIN_REL, PAPER_NATIONAL_SECTIONS  # noqa: E402
import argparse
import hashlib
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROOT = os.path.dirname(HERE)

REGISTRY = asset_path("data", "claim_matrix.csv")
OUT_CSV = asset_path("outputs", "pakemis_claim_matrix.csv")
OUT_MD = asset_path("outputs", "pakemis_claim_matrix.md")
# RELATIVE, like OUT_CSV and OUT_MD beside it: write_all() joins these onto an out_dir,
# and tests/paper_numbers/test_claim_matrix.py renders into a temp directory and compares.
# An ABSOLUTE path here silently defeats both - os.path.join(tmp, abs) returns abs - so the
# "fresh render" wrote over the real fragment mid-suite and the shipped-PDF staleness check
# failed two tests later, inside a full serial run only. SECTIONS_DIR is read, not written,
# so it stays absolute.
OUT_TEX = asset_path(PAPER_NATIONAL_MAIN_REL, "generated", "claim_matrix.tex")
SECTIONS_DIR = PAPER_NATIONAL_SECTIONS

REGISTRY_FIELDS = ("claim_id", "essd_section", "section_file", "claim_text", "printed_pattern",
                   "quantity_refs", "source_product_id", "source_pointer", "query_function",
                   "query_params", "configuration", "unit", "rounding", "evidence_class",
                   "limitation_ref", "tn_refs", "artefact_ref")
RESULT_FIELDS = REGISTRY_FIELDS + ("resolved_value", "printed_value", "tolerance", "agrees",
                                   "agrees_strict", "resolved_via", "query_hash", "receipt",
                                   "semantic_release_id")
ESSD_ORDER = ("abstract", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "conclusions")
ESSD_TITLES = {"abstract": "Abstract", "1": "1 Introduction", "2": "2 Dataset scope and architecture",
               "3": "3 Source data and processing", "4": "4 Dataset generation", "5": "5 Data records",
               "6": "6 Technical validation", "7": "7 Usage notes and limitations",
               "8": "8 Data availability", "9": "9 Code availability", "10": "10 Conclusions",
               "conclusions": "10 Conclusions"}
EVIDENCE_CLASSES = ("closure-exact", "estimated-TE1", "estimated-TE2", "estimated-TE3", "estimated-TE4",
                    "spatial-S1", "spatial-S2", "spatial-S3", "spatial-S4", "parametric", "structural",
                    "external-comparison", "coverage-count", "provenance-count")
QUERY_FUNCTIONS = ("query_emissions", "compare_emissions", "get_timeseries", "get_uncertainty",
                   "get_completeness", "get_evidence", "get_spatial_lineage", "get_cross_sector_transfer")


def _setup_paths(root):
    for sub in ("src", "tests"):
        path = asset_path(root, sub)
        if path not in sys.path:
            sys.path.insert(0, path)


def normalise(text):
    return " ".join(text.split())


def canonical_params(params_json):
    """The canonical JSON the query hash is taken over (sorted keys, compact)."""
    if not params_json:
        return ""
    return json.dumps(json.loads(params_json), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def query_hash(params_json):
    return hashlib.sha256(canonical_params(params_json).encode("utf-8")).hexdigest() if params_json else ""


# --- the printed value ----------------------------------------------------------------------

class Sections:
    def __init__(self, root):
        self.root = root
        self.raw = {}

    def text(self, name):
        if name not in self.raw:
            with open(asset_path(self.root, SECTIONS_DIR, name), encoding="utf-8") as handle:
                self.raw[name] = handle.read()
        return self.raw[name]

    def contains(self, name, sentence):
        return normalise(sentence) in normalise(self.text(name))


def doc_claim(label, doc_claims):
    for entry in doc_claims:
        if entry[0] == label and entry[1] == "national":
            return entry
    raise KeyError("DOC_CLAIMS has no national entry %r" % label)


def first_claim_ref(row):
    for ref in row["quantity_refs"].split(";"):
        if ref.startswith("claim:"):
            return ref[len("claim:"):]
    return ""


def printed_value(row, sections, doc_claims):
    """The value the row's own section prints, as the string in the prose."""
    if row["printed_pattern"]:
        pattern = row["printed_pattern"]
        # the live section first (a repaired number must be read from the prose, not from the
        # registry's quotation of it), then the quoted sentence
        for text in (sections.text(row["section_file"]), normalise(sections.text(row["section_file"])),
                     normalise(row["claim_text"])):
            m = re.search(pattern, text)
            if m:
                return m.group(1)
        raise LookupError("%s: printed_pattern matches nothing in %s" % (row["claim_id"], row["section_file"]))
    label = first_claim_ref(row)
    if not label:
        raise LookupError("%s: no printed_pattern and no claim: reference" % row["claim_id"])
    _label, _doc, section, pattern, _getter, _tol = doc_claim(label, doc_claims)
    m = re.search(pattern, sections.text(row["section_file"]))
    if not m:
        raise LookupError("%s: the DOC_CLAIMS pattern of %r (anchored in %s) matches nothing in %s"
                          % (row["claim_id"], label, section, row["section_file"]))
    return m.group(1)


# --- the resolved value ---------------------------------------------------------------------

def _query(d):
    from pakemis_query.models import QueryEmissions
    d = dict(d)
    for k in ("periods", "gases", "sectors", "ipcc_codes", "categories", "streams", "geography_ids", "months", "group_by"):
        if k in d:
            d[k] = tuple(d[k])
    return QueryEmissions(**d)


def run_query(engine, fn, params):
    from pakemis_query import functions as F
    from pakemis_query.models import (CompareRequest, CompletenessRequest, EvidenceRequest,
                                      SpatialLineageRequest, TimeseriesRequest, TransferRequest,
                                      UncertaintyRequest)
    req = {k: v for k, v in params.items() if not k.startswith("_")}
    if fn == "query_emissions":
        return engine.query_emissions(_query(req))
    if fn == "compare_emissions":
        return F.compare_emissions(engine, CompareRequest(left=_query(req["left"]), right=_query(req["right"]),
                                                          mode=req.get("mode", "absolute")))
    if fn == "get_timeseries":
        return F.get_timeseries(engine, TimeseriesRequest(query=_query(req.get("query", {})), step=req.get("step", "annual")))
    if fn == "get_uncertainty":
        return F.get_uncertainty(engine, UncertaintyRequest(**req))
    if fn == "get_completeness":
        d = dict(req)
        d["notation_keys"] = tuple(d.get("notation_keys", ()))
        d["ipcc_codes"] = tuple(d.get("ipcc_codes", ()))
        return F.get_completeness(engine, CompletenessRequest(**d))
    if fn == "get_evidence":
        return F.get_evidence(engine, EvidenceRequest(**req))
    if fn == "get_spatial_lineage":
        return F.get_spatial_lineage(engine, SpatialLineageRequest(**req))
    if fn == "get_cross_sector_transfer":
        return F.get_cross_sector_transfer(engine, TransferRequest(**req))
    raise KeyError(fn)


def select_cell(envelope, params):
    """The one value a row is about: `_cell` is "count" (how many values), a group dict, or
    absent (the first value)."""
    values = envelope["values"]
    cell = params.get("_cell")
    if cell == "count":
        return {"exact": str(len(values)), "display": str(len(values))}
    if isinstance(cell, dict):
        for v in values:
            if all(v.get("group", {}).get(k) == val for k, val in cell.items()):
                return v
        raise LookupError("no cell with group %r among %d values" % (cell, len(values)))
    if not values:
        raise LookupError("the envelope carries no values")
    return values[0]


def resolve(row, root, engine, doc_claims):
    """(resolved value as a string, via, receipt)."""
    from pkinv.report import claims
    if row["query_function"]:
        if engine is None:
            raise RuntimeError("pakemis_query is unavailable (duckdb?) and %s names a query" % row["claim_id"])
        params = json.loads(row["query_params"]) if row["query_params"] else {}
        env = run_query(engine, row["query_function"], params)
        cell = select_cell(env, params)
        exact = cell.get("exact", cell.get("display", ""))
        if params.get("_abs") and exact not in ("", None):
            from decimal import Decimal
            exact = str(abs(Decimal(exact)))
        return exact, "query", env["receipt"]
    if row["source_pointer"]:
        expr = row["source_pointer"]
        simple = expr.count("#") == 2 and not re.match(r"[a-z_]+:", expr)
        if simple:
            cell = claims.resolve_pointer(root, expr)
            try:
                float(cell)
            except ValueError:
                return cell, "pointer", ""
            return cell, "pointer", ""
        return repr(claims.resolve_expression(root, expr)), "pointer", ""
    label = first_claim_ref(row)
    if not label:
        raise LookupError("%s: nothing to resolve through" % row["claim_id"])
    getter = doc_claim(label, doc_claims)[4]
    value = getter()
    return repr(float(value)), "getter", ""


def claim_tolerance(row, doc_claims):
    label = first_claim_ref(row)
    return float(doc_claim(label, doc_claims)[5]) if label else 0.0


def _as_number(text):
    if text is None:
        return None
    t = text.strip().replace("{,}", "").replace(",", "")
    if t.lower() in ("no", "none", "zero"):
        return 0.0
    try:
        return float(t)
    except ValueError:
        return None


def compare(printed, resolved, dp, tol):
    """(agrees, agrees_strict) - the DOC_CLAIMS rule and the bare half-ulp rule."""
    p, r = _as_number(printed), _as_number(resolved)
    if p is None or r is None:
        same = normalise(printed).replace("--", "-") == normalise(resolved).replace("--", "-")
        return same, same
    half_ulp = 0.5 * 10 ** (-dp) + 1e-9
    return abs(p - r) <= half_ulp + tol, abs(p - r) <= half_ulp


# --- the build ------------------------------------------------------------------------------

def open_engine(root):
    try:
        import duckdb  # noqa: F401
    except ImportError:
        return None
    from pakemis_query import Engine, Release
    release = Release.open(asset_path(root, "outputs", "semantic"), verify=True,
                           manifest_path=asset_path(root, "outputs", "release_manifest.json"))
    return Engine(release)


def load_registry(root):
    from pkinv.core.io import read_rows
    rows = read_rows(asset_path(root, REGISTRY))
    if rows and tuple(rows[0].keys()) != REGISTRY_FIELDS:
        raise SystemExit("data/claim_matrix.csv columns are %r, expected %r" % (tuple(rows[0].keys()), REGISTRY_FIELDS))
    return rows


def build(root):
    """The resolved rows, in registry order."""
    _setup_paths(root)
    from paper_numbers.doc_claims import DOC_CLAIMS
    with open(asset_path(root, "outputs", "semantic", "semantic_release.json"), encoding="utf-8") as handle:
        release_id = json.load(handle)["release"]["release_id"]
    sections = Sections(root)
    engine = open_engine(root)
    out = []
    for row in load_registry(root):
        result = dict(row)
        printed = printed_value(row, sections, DOC_CLAIMS)
        resolved, via, receipt = resolve(row, root, engine, DOC_CLAIMS)
        tol = claim_tolerance(row, DOC_CLAIMS)
        agrees, strict = compare(printed, resolved, int(row["rounding"] or 0), tol)
        result.update(resolved_value=resolved, printed_value=printed, tolerance=repr(tol),
                      agrees="yes" if agrees else "no", agrees_strict="yes" if strict else "no",
                      resolved_via=via, query_hash=query_hash(row["query_params"]), receipt=receipt,
                      semantic_release_id=release_id)
        out.append(result)
    return out


# --- the three renderings -------------------------------------------------------------------

def _grouped(rows):
    for section in ESSD_ORDER:
        block = [r for r in rows if r["essd_section"] == section]
        if block:
            yield section, block


def render_md(rows):
    lines = ["# The claim matrix, resolved", "",
             "One row per headline claim of the national manuscript (data/claim_matrix.csv), held to the "
             "release: `printed` is what the section prints today, `resolved` is what the release answers "
             "(through pakemis_query where a stored query exists, else through the pointer, else through the "
             "DOC_CLAIMS getter). `agrees` applies the DOC_CLAIMS rule (half an ulp at the printed precision "
             "plus the claim's registered tolerance); `strict` is half an ulp alone. Nothing here is repaired: "
             "a `no` is a finding for tests/paper_numbers/test_claim_matrix.py.", ""]
    total = len(rows)
    lines.append("Rows: %d; agree: %d; disagree: %d; via query: %d, pointer: %d, getter: %d."
                 % (total, sum(r["agrees"] == "yes" for r in rows), sum(r["agrees"] == "no" for r in rows),
                    sum(r["resolved_via"] == "query" for r in rows), sum(r["resolved_via"] == "pointer" for r in rows),
                    sum(r["resolved_via"] == "getter" for r in rows)))
    lines.append("")
    for section, block in _grouped(rows):
        lines += ["## %s" % ESSD_TITLES[section], "",
                  "| claim_id | printed | resolved | unit | agrees | strict | evidence | via | limitation | artefact | refs |",
                  "|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in block:
            lines.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |"
                         % (r["claim_id"], r["printed_value"], r["resolved_value"], r["unit"], r["agrees"],
                            r["agrees_strict"], r["evidence_class"], r["resolved_via"], r["limitation_ref"],
                            r["artefact_ref"], r["quantity_refs"].replace("|", "\\|")))
        lines.append("")
    return "\n".join(lines) + "\n"


def tex_escape(text):
    out = []
    for ch in text:
        out.append({"_": r"\_", "&": r"\&", "%": r"\%", "#": r"\#", "$": r"\$", "{": r"\{", "}": r"\}",
                    "~": r"\textasciitilde{}", "^": r"\textasciicircum{}", "\\": r"\textbackslash{}"}.get(ch, ch))
    return "".join(out)


def render_tex(rows):
    lines = [
        "% GENERATED by scripts/make_claim_matrix.py from data/claim_matrix.csv - do not edit.",
        "\\subsection*{S5 The claim matrix}",
        "\\label{sec:claim-matrix}",
        "",
        "Every headline claim of the national paper is a row of \\texttt{data/claim\\_matrix.csv}: the "
        "sentence as printed, its quantity references into the claims machinery, the source pointer, the "
        "stored query, the configuration, unit and rounding, the evidence class, the limitation paragraph it "
        "is bounded by, the technical notes it rests on and the artefact that shows it. "
        "\\texttt{scripts/make\\_claim\\_matrix.py} resolves each row against the release and writes "
        "\\texttt{outputs/pakemis\\_claim\\_matrix.csv}; the tables below print the identifier, the printed "
        "and resolved values, the evidence class and the limitation label. The sentence itself, the pointer "
        "and the query parameters are in the CSV. A row whose printed value disagrees with the release fails "
        "\\texttt{tests/paper\\_numbers/test\\_claim\\_matrix.py}; nothing is repaired in place.",
        "",
    ]
    chunk = 32
    for section, block in _grouped(rows):
        for start in range(0, len(block), chunk):
            part = block[start:start + chunk]
            title = ESSD_TITLES[section] + (" (continued)" if start else "")
            lines += ["\\begin{table}[htbp]", "\\centering", "\\footnotesize", "\\setlength{\\tabcolsep}{4pt}",
                      "\\caption{Claim matrix: %s.}" % tex_escape(title),
                      "\\begin{tabular}{@{}p{3.6cm}lrrp{2.6cm}p{2.4cm}@{}}", "\\toprule",
                      "\\textbf{claim} & \\textbf{via} & \\textbf{printed} & \\textbf{resolved} & \\textbf{evidence} & \\textbf{limitation} \\\\",
                      "\\midrule"]
            for r in part:
                resolved = r["resolved_value"]
                if _as_number(resolved) is not None and _as_number(r["printed_value"]) is not None:
                    resolved = ("%%.%df" % int(r["rounding"])) % float(resolved)
                lines.append("%s & %s & %s & %s%s & %s & %s \\\\" % (
                    tex_escape(r["claim_id"]).replace("\\_", "\\_\\allowbreak{}"), r["resolved_via"], tex_escape(r["printed_value"]),
                    tex_escape(resolved), "" if r["agrees"] == "yes" else "$^{\\dagger}$",
                    tex_escape(r["evidence_class"]), tex_escape(r["limitation_ref"].replace("lim:", ""))))
            lines += ["\\bottomrule", "\\end{tabular}", "\\end{table}", ""]
    lines.append("$^{\\dagger}$ printed value outside the DOC\\_CLAIMS agreement rule at the time of rendering.")
    lines.append("")
    return "\n".join(lines)


def write_all(rows, out_dir):
    from pkinv.core.io import write_table
    write_table(asset_path(out_dir, OUT_CSV), RESULT_FIELDS, rows)
    for rel, text in ((OUT_MD, render_md(rows)), (OUT_TEX, render_tex(rows))):
        path = asset_path(out_dir, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="render to a temporary directory and exit 1 on any difference")
    parser.add_argument("--root", default=DEFAULT_ROOT, help="the release tree (default: this repository)")
    parser.add_argument("--out", default=None, help="write under this directory instead of the root")
    args = parser.parse_args(argv)
    root = os.path.abspath(args.root)
    rows = build(root)
    if args.check:
        with tempfile.TemporaryDirectory() as tmp:
            write_all(rows, tmp)
            stale = []
            for rel in (OUT_CSV, OUT_MD, OUT_TEX):
                held = asset_path(root, rel)
                fresh = open(asset_path(tmp, rel), "rb").read()
                if not os.path.exists(held) or open(held, "rb").read() != fresh:
                    stale.append(rel)
        if stale:
            print("claim matrix outputs differ from a fresh render: %s" % ", ".join(stale))
            return 1
        print("claim matrix outputs are current (%d rows)" % len(rows))
        return 0
    out_dir = os.path.abspath(args.out) if args.out else root
    write_all(rows, out_dir)
    disagree = [r for r in rows if r["agrees"] == "no"]
    print("Claim matrix -> %s (%d rows; %d disagree; via query %d / pointer %d / getter %d)"
          % (asset_path(out_dir, OUT_CSV), len(rows), len(disagree),
             sum(r["resolved_via"] == "query" for r in rows), sum(r["resolved_via"] == "pointer" for r in rows),
             sum(r["resolved_via"] == "getter" for r in rows)))
    for r in disagree:
        print("  DISAGREES %s: printed %s, resolved %s" % (r["claim_id"], r["printed_value"], r["resolved_value"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
