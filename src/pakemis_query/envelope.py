"""The result envelope: every answer carries its values, its context, its provenance, its
calculation, the uncertainty and evidence in scope, the unallocated mass, the limitations hit,
and a receipt. A value is a dict {exact, value, display, unit, result_row_ids, formula}; the
exact string is the decimal the engine summed, the display is the contract's rounding of it."""
from decimal import Decimal, ROUND_HALF_EVEN

from pakemis_query.receipt import digest_context, receipt_id, result_digest


def display(exact, decimals):
    if exact in ("", None):
        return ""
    q = Decimal(1).scaleb(-decimals)
    return str(Decimal(exact).quantize(q, rounding=ROUND_HALF_EVEN))


def value(exact, unit, decimals, row_ids=(), formula="", **extra):
    v = {"exact": exact, "value": float(exact) if exact not in ("", None) else None,
         "display": display(exact, decimals), "unit": unit,
         "result_row_ids": list(row_ids), "formula": formula}
    v.update(extra)
    return v


def envelope(release, request_type, canonical_request, request_fields, values, calculation,
             provenance, uncertainty=None, evidence=None, unallocated=None, completeness=None,
             limitations_hit=(), defaults_applied=()):
    context = release.context(request_fields)
    context["defaults_applied"] = list(defaults_applied)
    digest = result_digest(values, digest_context(context))
    body = {
        "request_type": request_type,
        "request": canonical_request,
        "context": context,
        "values": values,
        "calculation": calculation,
        "provenance": provenance,
        "uncertainty": uncertainty or {},
        "evidence": evidence or {},
        "unallocated": unallocated or {},
        "completeness": completeness or [],
        "limitations_hit": [release.limitations.get(l, {"id": l}) for l in limitations_hit],
        "citation": "Ahmad, R. (2026). %s. PakEmis (data set); query receipt %s"
                    % (release.release_id, ""),
        "result_sha256": digest,
    }
    body["receipt"] = receipt_id(canonical_request, release.release_id, digest)
    body["citation"] = body["citation"].rstrip() + body["receipt"]
    return body
