"""Evaluate every registered manuscript claim and write the claim registry and its report.

Usage: PKINV_ROOT=<tree> PYTHONPATH=<tree>/src:<tree>/tests:<tree>/tests/paper_numbers \
       python3 tests/validation/claim_registry.py <tree> <registry csv> <report csv>

The registry is tests/paper_numbers/doc_claims.py (DOC_CLAIMS: label, document, section,
regex with one capture group, getter, extra tolerance) plus data/claims_registry.csv. For each
claim the getter is evaluated against the shipped products, the section is searched with the
regex, and the printed value is compared at the printed number of decimals with the same rule
tests/paper_numbers/test_claims.py uses. For printed quantities, test_status is agrees,
disagrees, unmatched (the regex finds nothing), or error (the getter raised). Semantic
registry rows also retain their claim_status and reason, so product-only diagnostics
cannot be read as manuscript claims. This is a record of one evaluation, written so a
reviewer can see every claim and its evidence without running the suite.
"""

from pkinv.assets import asset_path
import csv
import os
import re
import sys
import traceback


def main(root, registry_out, report_out):
    sys.path.insert(0, os.path.join(root, "tests"))
    sys.path.insert(0, os.path.join(root, "tests", "paper_numbers"))
    import doc_claims
    import _common

    rows, tally = [], {}
    for i, claim in enumerate(doc_claims.DOC_CLAIMS):
        label, doc, section, pattern, getter, tol = claim
        record = {"claim_id": "doc_claim_%04d" % i, "document": doc, "page_or_section": section,
                  "claim_type": "registered_quantity", "displayed_text_or_value": "", "canonical_product_id": "",
                  "canonical_key": label, "rounding_rule": "printed decimals; |printed - value| <= tol + half-ulp",
                  "expected_value": "", "tolerance": repr(tol), "test_status": "",
                  "claim_status": "current_manuscript", "status_reason": "Registered printed quantity."}
        try:
            value = getter()
            record["expected_value"] = repr(value)
        except Exception as exc:              # noqa: BLE001 - recorded, not hidden
            record["test_status"] = "error: %s" % exc.__class__.__name__
            rows.append(record)
            continue
        try:
            path = os.path.join(_common.DOCS[doc], section)
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
        except (KeyError, OSError):
            record["test_status"] = "unmatched: section not found"
            rows.append(record)
            continue
        m = re.search(pattern, text, re.S)
        if not m:
            record["test_status"] = "unmatched"
            rows.append(record)
            continue
        printed = m.group(1)
        record["displayed_text_or_value"] = printed
        try:
            p = float(printed.replace(",", "").replace("\\,", ""))
            decimals = len(printed.split(".")[1]) if "." in printed else 0
            ok = abs(p - float(value)) <= float(tol) + 0.5 * 10 ** (-decimals) + 1e-9
            record["test_status"] = "agrees" if ok else "disagrees"
        except (TypeError, ValueError):
            record["test_status"] = "agrees" if str(value) == printed else "disagrees"
        rows.append(record)
    # the semantic claims registry
    with open(asset_path(root, "data", "claims_registry.csv"), encoding="utf-8") as handle:
        for r in csv.DictReader(line for line in handle if not line.startswith("#")):
            rows.append({"claim_id": r["claim_id"], "document": r["allowed_documents"], "page_or_section": "",
                         "claim_type": "semantic_claim", "displayed_text_or_value": "",
                         "canonical_product_id": r["authoritative_output"], "canonical_key": r["numerator"],
                         "rounding_rule": r["rounding"], "expected_value": "", "tolerance": "",
                         "test_status": "asserted by tests/test_claims_registry.py",
                         "claim_status": r["claim_status"], "status_reason": r["status_reason"]})
    for r in rows:
        key = (r["document"].split(";")[0], r["test_status"].split(":")[0])
        tally[key] = tally.get(key, 0) + 1
    with open(registry_out, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    with open(report_out, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["document", "test_status", "claims"])
        for (doc, status), n in sorted(tally.items()):
            writer.writerow([doc, status, n])
    bad = sum(n for (d, s), n in tally.items() if s in ("disagrees", "error", "unmatched"))
    print("claims: %d evaluated, %d not agreeing" % (len(rows), bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:4]))
