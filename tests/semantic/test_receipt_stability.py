"""A receipt moves when the answer moves, and not when the tree does.

THE DEFECT THIS HOLDS SHUT. `result_sha256` used to digest the whole reported context, which
carries `commit` - the git hash of the tree that built the release, re-read from
release_manifest.json on every regeneration. Every commit therefore invalidated every frozen
receipt in tests/semantic/golden/, including commits that changed no data at all, and the only
way to get a green suite was to re-freeze the goldens immediately before checking them. An
expectation re-derived from the code it is meant to hold to account is not an expectation, so
the treadmill was silently costing the release its strongest reproducibility guard.

These tests hold both halves of the property, because fixing the first without the second would
buy stability by making the receipt mean less.
"""
import unittest

from pakemis_query.receipt import DIGEST_EXCLUDED, digest_context, receipt_id, result_digest


def context(**overrides):
    base = {"release": "1.0.0rc42", "version": "1.0.0rc42",
            "commit": "631b95f0c04111e2f95e947e5fd6edb38e78f91b",
            "reporting_period": "FY2023-24", "basis": "fiscal", "periods": ["FY2023-24"],
            "configuration_id": "REF_2023_24", "gwp_basis": "AR5",
            "gwp_factors": {"CH4_fossil": 30.0}, "geography_level": "national",
            "geography_ids": ["PK"], "spatial_view": "all", "lulucf": "excluded",
            "defaults_applied": []}
    base.update(overrides)
    return base


VALUES = [{"result_row_id": "national_total", "co2e_Mt_AR5": "452.34662"}]


class TestTheTreeHashDoesNotMoveTheReceipt(unittest.TestCase):

    def test_a_different_commit_gives_the_same_digest(self):
        here = result_digest(VALUES, digest_context(context()))
        there = result_digest(VALUES, digest_context(context(commit="0" * 40)))
        self.assertEqual(here, there,
                         "the git hash of the build tree must not enter the result digest")

    def test_a_different_commit_gives_the_same_receipt(self):
        def receipt(ctx):
            return receipt_id('{"q":"national_total"}', ctx["release"],
                              result_digest(VALUES, digest_context(ctx)))
        self.assertEqual(receipt(context()), receipt(context(commit="0" * 40)))

    def test_commit_is_the_only_thing_excused(self):
        """A field is excused from the digest only with an argument in receipt.py's docstring.
        If this list grows, that argument has to grow with it."""
        self.assertEqual(DIGEST_EXCLUDED, ("commit",))

    def test_the_excluded_field_is_still_reported(self):
        """It leaves the digest, not the envelope: provenance a reader wants is still there."""
        ctx = context()
        self.assertIn("commit", ctx)
        self.assertNotIn("commit", digest_context(ctx))


class TestEverythingElseStillMovesIt(unittest.TestCase):
    """The other half: stability bought by making the receipt insensitive would be worse than
    the treadmill it replaced."""

    def test_every_answer_determining_field_moves_the_digest(self):
        base = result_digest(VALUES, digest_context(context()))
        for field, other in (("release", "1.0.0rc43"), ("version", "1.0.0rc43"),
                             ("basis", "calendar"), ("periods", ["FY2022-23"]),
                             ("configuration_id", "L_2023_24"), ("gwp_basis", "AR6"),
                             ("gwp_factors", {"CH4_fossil": 29.8}),
                             ("geography_level", "adm1"), ("geography_ids", ["PK-PB"]),
                             ("spatial_view", "physical"), ("lulucf", "included"),
                             ("reporting_period", "FY2022-23"),
                             ("defaults_applied", ["basis"])):
            moved = result_digest(VALUES, digest_context(context(**{field: other})))
            self.assertNotEqual(base, moved, "%s must move the receipt" % field)

    def test_a_changed_value_moves_the_digest(self):
        base = result_digest(VALUES, digest_context(context()))
        other = [{"result_row_id": "national_total", "co2e_Mt_AR5": "452.34663"}]
        self.assertNotEqual(base, result_digest(other, digest_context(context())))


if __name__ == "__main__":
    unittest.main()


class EveryEnvelopeReplaysFromItsOwnRequest(unittest.TestCase):
    """A receipt is minted over a canonical request. If an envelope then stores a DIFFERENT request,
    the receipt it carries can never be reproduced from the request it carries, and the replay path
    rejects it - which is precisely what happened to get_timeseries. It called query_emissions,
    which minted over the expanded QueryEmissions, and then overwrote `request` with the
    TimeseriesRequest. Every other request type replayed, so nothing looked wrong.

    This asserts the property for each function that mints an envelope, rather than for the one
    that was broken, because the next one to break will be a different one.
    """

    @classmethod
    def setUpClass(cls):
        from semantic._golden import open_engine
        cls.engine = open_engine()
        cls.release_id = cls.engine.release.release_id

    def check(self, env):
        from pakemis_query.receipt import receipt_id
        minted = receipt_id(env["request"], self.release_id, env["result_sha256"])
        self.assertEqual(env["receipt"], minted,
                         "%s: the stored request does not reproduce the stored receipt" % env["request_type"])
        self.assertIn(env["receipt"], env["citation"], "the citation carries a different receipt")

    def test_query_emissions(self):
        from pakemis_query.models import QueryEmissions
        self.check(self.engine.query_emissions(QueryEmissions(periods=("FY2023-24",))))

    def test_get_timeseries(self):
        from pakemis_query import functions as F
        from pakemis_query.models import QueryEmissions, TimeseriesRequest
        self.check(F.get_timeseries(self.engine, TimeseriesRequest(query=QueryEmissions(), step="annual")))

    def test_compare_emissions(self):
        from pakemis_query import functions as F
        from pakemis_query.models import CompareRequest, QueryEmissions
        self.check(F.compare_emissions(self.engine, CompareRequest(
            left=QueryEmissions(periods=("FY2022-23",)), right=QueryEmissions(periods=("FY2023-24",)), mode="absolute")))

    def test_get_uncertainty_and_completeness(self):
        from pakemis_query import functions as F
        from pakemis_query.models import CompletenessRequest, UncertaintyRequest
        self.check(F.get_uncertainty(self.engine, UncertaintyRequest(scope="national")))
        self.check(F.get_completeness(self.engine, CompletenessRequest(notation_keys=("NE",))))
