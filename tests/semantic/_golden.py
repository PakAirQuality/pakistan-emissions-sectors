"""The golden runner: a golden file is a request, the cells it must return, the tolerance rule
and (once frozen) the receipt. Expectations may carry a `claims_pointer` in the claims-registry
grammar (file.csv#k=v#column) so a golden is tied to the shipped cell the paper cites, not to a
literal alone."""
import glob
import json
import os
from decimal import Decimal

from pkinv.paths import OUTPUTS, ROOT
from pkinv.report import claims
from pkinv.semantic import OUT_DIR
from pakemis_query import Engine, Release
from pakemis_query import functions as F
from pakemis_query.models import (CompareRequest, CompletenessRequest, EvidenceRequest, QueryEmissions,
                                  SpatialLineageRequest, TimeseriesRequest, TransferRequest,
                                  UncertaintyRequest)

GOLDEN_DIR = os.path.join(os.path.dirname(__file__), "golden")


def load_goldens():
    out = []
    for path in sorted(glob.glob(os.path.join(GOLDEN_DIR, "*.json"))):
        with open(path, encoding="utf-8") as handle:
            out.append((os.path.basename(path), json.load(handle)))
    return out


def open_engine():
    release = Release.open(OUT_DIR, verify=True, manifest_path=os.path.join(OUTPUTS, "release_manifest.json"))
    return Engine(release)


def _q(d):
    d = dict(d)
    for k in ("periods", "gases", "sectors", "ipcc_codes", "categories", "streams", "geography_ids", "months", "group_by"):
        if k in d:
            d[k] = tuple(d[k])
    return QueryEmissions(**d)


def run(engine, golden):
    fn, req = golden["function"], golden["request"]
    if fn == "query_emissions":
        return engine.query_emissions(_q(req))
    if fn == "compare_emissions":
        return F.compare_emissions(engine, CompareRequest(left=_q(req["left"]), right=_q(req["right"]), mode=req.get("mode", "absolute")))
    if fn == "get_timeseries":
        return F.get_timeseries(engine, TimeseriesRequest(query=_q(req["query"]), step=req.get("step", "annual")))
    if fn == "get_uncertainty":
        return F.get_uncertainty(engine, UncertaintyRequest(**req))
    if fn == "get_completeness":
        d = dict(req); d["notation_keys"] = tuple(d.get("notation_keys", ())); d["ipcc_codes"] = tuple(d.get("ipcc_codes", ()))
        return F.get_completeness(engine, CompletenessRequest(**d))
    if fn == "get_evidence":
        return F.get_evidence(engine, EvidenceRequest(**req))
    if fn == "get_spatial_lineage":
        return F.get_spatial_lineage(engine, SpatialLineageRequest(**req))
    if fn == "get_cross_sector_transfer":
        return F.get_cross_sector_transfer(engine, TransferRequest(**req))
    if fn == "query_air":
        from pakemis_query.models import QueryAir
        d = {k: (tuple(v) if isinstance(v, list) else v) for k, v in req.items()}
        return engine.query_air(QueryAir(**d))
    raise KeyError(fn)


def resolve_pointer(pointer):
    """file.csv#k1=v1,k2=v2#column -> the cell's string (the claims-registry grammar).

    The body moved to pkinv.report.claims - the one resolver the golden runner and the claim
    matrix (scripts/make_claim_matrix.py) share - and this is the same call against this
    repository's outputs/: exactly one row may match, and the cell comes back as its string."""
    return claims.resolve_pointer(ROOT, pointer)


def check(golden, env):
    """The problems a golden finds in an envelope (empty when it passes)."""
    problems = []
    values = env["values"]
    for i, exp in enumerate(golden["expect"]):
        idx = exp.get("cell", i)
        if idx >= len(values):
            problems.append("cell %d absent (%d cells)" % (idx, len(values)))
            continue
        got = values[idx]
        if "group" in exp and got.get("group") != exp["group"]:
            problems.append("cell %d group %r != %r" % (idx, got.get("group"), exp["group"]))
        if "exact" in exp:
            tol = Decimal(str(exp.get("tolerance", "0")))
            if abs(Decimal(got["exact"]) - Decimal(exp["exact"])) > tol:
                problems.append("cell %d exact %s != %s (tol %s)" % (idx, got["exact"], exp["exact"], tol))
        if "display" in exp and got["display"] != exp["display"]:
            problems.append("cell %d display %r != %r" % (idx, got["display"], exp["display"]))
        if "claims_pointer" in exp:
            cell = resolve_pointer(exp["claims_pointer"])
            tol = Decimal(str(exp.get("tolerance", "0")))
            if abs(Decimal(got["exact"]) - Decimal(cell)) > tol:
                problems.append("cell %d exact %s != the cited cell %s (%s)" % (idx, got["exact"], cell, exp["claims_pointer"]))
    for k, v in golden.get("expect_context", {}).items():
        if env["context"].get(k) != v:
            problems.append("context %s %r != %r" % (k, env["context"].get(k), v))
    if golden.get("expect_receipt") and env["receipt"] != golden["expect_receipt"]:
        problems.append("receipt %s != frozen %s" % (env["receipt"], golden["expect_receipt"]))
    return problems
