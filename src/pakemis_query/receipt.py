"""Receipts: a query is reproducible or it is not an answer.

receipt = sha256("pakemis.receipt/v1" + canonical_request + release_id + result_sha256)[:32]
result_sha256 = sha256 of the canonical JSON of the values and the DIGESTED context. A receipt
is REPLAYED (the request is stored, never the result), so a receipt that stops reproducing is a
finding about the release, not a cached number.

WHY THE CONTEXT IS DIGESTED AND NOT TAKEN WHOLE. The context reports two different kinds of
thing. Most of its fields DETERMINE the answer - the basis, the periods, the configuration, the
GWP set, the geography, the spatial view, the LULUCF switch - and a receipt that did not move
when one of them moved would be worthless. One field does not: `commit`, the git hash of the
tree that built the release, which pakemis_query.release reads from release_manifest.json.

That hash changes on EVERY commit, including commits that touch no data at all - a paragraph
of a paper, a test added, a comment fixed. With it inside the digest, every frozen receipt in
tests/semantic/golden/ went stale on every commit, and the only way to make the suite green was
to re-freeze them immediately before checking them - which verifies nothing, because the
expectation is then re-derived from the code it is meant to hold to account. A guard that is
re-stamped whenever it fails is not a guard.

So `commit` stays in the reported context, where it is exactly the provenance a reader wants,
and stays OUT of the digest. Nothing is weakened by this: the values themselves are digested,
so any commit that actually changes a number still moves the receipt, and the release is still
identified by release_id and version, both of which are digested. What stops moving is the
receipt of an answer that did not change."""
import hashlib
import json

SCHEME = "pakemis.receipt/v1"

# Reported in the envelope, excluded from the digest: provenance about the TREE, not about the
# answer. Adding a field here weakens the receipt and needs the same argument as the one above.
DIGEST_EXCLUDED = ("commit",)


def digest_context(context):
    """The part of a context that determines the answer."""
    return {k: v for k, v in context.items() if k not in DIGEST_EXCLUDED}


def result_digest(values, context):
    payload = json.dumps({"values": values, "context": context}, sort_keys=True,
                         separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def receipt_id(canonical_request, release_id, result_sha256):
    payload = SCHEME + canonical_request + release_id + result_sha256
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]
