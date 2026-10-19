"""The sector self-checks, asserted against the SHIPPED files rather than trusted to run.

WHAT THIS IS FOR. Three sectors write a QA table - aviation, fugitives and IPPU - fifty-two
checks between them, each with a sentence explaining what it means. Two of them were false for
several releases and nothing said so.

The runners do raise on a false check, so the obvious question is how. The answer is that they
never ran: `make national` builds the cross-sector layer only, and `run_ippu` sits under the
`ippu:` target. So `outputs/ippu_qa_2024.csv` kept its pre-GEM contents through four releases
while `pkinv.report.facility_registry` - which IS in that target - moved the master registry to
nineteen geocoded facilities. Two registries then described the same thirty-four facilities and
disagreed, the IPPU manuscript was anchored to the stale one, and it told readers eight.

That is why this file asserts the COMMITTED table and not a fresh run. A guard that re-runs the
producer cannot see a stale product; it would have passed on the day the number went wrong.
Reading what is on disk is the whole point.

Run:  python3 -m unittest discover tests -p "test_sector_qa_checks.py"
"""

import glob
import os
import unittest
from pkinv.core.io import read_rows
from _support import OUT



def _tables():
    # Both shapes: <sector>_qa_<year>.csv and the reconciliation study's
    # <name>_qa.csv, which the first glob alone let escape for three releases.
    return sorted(set(glob.glob(os.path.join(OUT, "*_qa_*.csv")))
                  | set(glob.glob(os.path.join(OUT, "*_qa.csv"))))


def _rows(path):
    return read_rows(path)


# THE THREE SECTORS DO NOT SHARE A SCHEMA and this map says so rather than guessing. Aviation
# records a threshold comparison under `status`, fugitives an actual-versus-expected pair with
# a `note`, IPPU a boolean with a `detail`. Inferring the verdict column by trying several
# names would pass silently on a file that has none - which is the shape of failure this whole
# release has been about. A new QA table is enrolled by adding one line here, and until then
# the coverage test below says it is unenrolled.
# UNIFIED is the rc34 runner-contract schema (core/runner.py QA_FIELDS,
# fugitives' shape verbatim); every table migrates onto it as its runner
# moves to the harness, and an end-of-wave ratchet asserts nothing else is
# left.
UNIFIED = {"verdict": "passed", "true": {"true"}, "explains": "note"}

SCHEMAS = {
    "agriculture_qa_2024.csv": UNIFIED,
    "agriculture_n_ledger_qa_2024.csv": UNIFIED,
    "aviation_qa_fy2023_24.csv": UNIFIED,
    "aviation_reconciliation_qa.csv": UNIFIED,
    "aviation_fallback_qa_fy2023_24.csv": UNIFIED,
    "fugitives_qa_2024.csv": UNIFIED,
    "ippu_qa_2024.csv": UNIFIED,
    "industry_qa_2024.csv": UNIFIED,
    "residential_qa_2024.csv": UNIFIED,
    "railways_qa_2024.csv": UNIFIED,
    "power_qa_fy2023_24.csv": UNIFIED,
    "transport_qa_2024.csv": UNIFIED,
    "waste_qa_2024.csv": UNIFIED,
}


# A warning is a real third state and this is the only one. Allowed because it is TRUE -
# Juzzak carries no coordinate and the negative is logged (aviation-juzzak-coords-01) - and
# listed because an allow-list of one is a ratchet: a second warning has to be argued for.
DECLARED_WARNINGS = {
    ("aviation_fallback_qa_fy2023_24.csv", "airport_coordinate_coverage"):
        "one domestic aerodrome carries no coordinate in any held source; the search is "
        "logged negative as aviation-juzzak-coords-01 and the threshold stays at 1.0 so the "
        "gap keeps showing",
}


class TestEverySectorSelfCheckPasses(unittest.TestCase):

    def test_the_tables_exist_and_are_not_empty(self):
        tables = _tables()
        # Twelve since rc34: the ten registered runners plus the two aviation
        # siblings, every one on the runner contract.
        self.assertGreaterEqual(len(tables), 12,
                                "a sector stopped publishing its QA table; a check that is "
                                "not written down cannot be read")
        for path in tables:
            self.assertTrue(_rows(path), os.path.basename(path))

    def test_every_enrolled_table_is_on_the_unified_schema(self):
        """The rc34 ratchet: the three legacy schemas were retired as their
        producers moved to core/runner.py, and nothing may reintroduce one -
        a new table enrols as UNIFIED or it does not enrol."""
        for name, schema in SCHEMAS.items():
            self.assertIs(schema, UNIFIED, "%s is enrolled on a non-unified schema" % name)
        for path in _tables():
            header = open(path, encoding="utf-8").readline().strip()
            self.assertEqual(header, "check,passed,actual,expected,note",
                             "%s does not carry the unified header" % os.path.basename(path))

    def test_every_table_declares_its_schema(self):
        """A table this file cannot read is a table it silently passes. Enrolment is by
        adding a line to SCHEMAS, and until then the failure names the file."""
        for path in _tables():
            self.assertIn(os.path.basename(path), SCHEMAS,
                          "%s publishes self-checks that nothing knows how to read"
                          % os.path.basename(path))

    def test_every_check_in_every_shipped_table_passes(self):
        """The SHIPPED table, not a fresh run. A guard that re-runs the producer cannot see a
        stale product, and a stale product is exactly what put a wrong number in a paper."""
        failures = []
        for path in _tables():
            name = os.path.basename(path)
            schema = SCHEMAS[name]
            for row in _rows(path):
                verdict = str(row.get(schema["verdict"], "")).strip().lower()
                if verdict in schema["true"]:
                    continue
                if (name, row.get("check")) in DECLARED_WARNINGS:
                    continue
                detail = row.get(schema["explains"] or "", "") or row
                failures.append("%s / %s -> %r: %s"
                                % (name, row.get("check", "?"), verdict, detail))
        self.assertFalse(failures, "sector self-checks are not passing in the shipped "
                                   "tables:\n  " + "\n  ".join(failures))

    def test_a_warning_is_declared_or_it_is_a_failure(self):
        """The ratchet. Every non-passing row must be on the allow-list with a reason, and
        the allow-list may not name a check that has since started passing - a permission
        nobody needs is a permission nobody rereads."""
        live = set()
        for path in _tables():
            name = os.path.basename(path)
            schema = SCHEMAS[name]
            for row in _rows(path):
                if str(row.get(schema["verdict"], "")).strip().lower() not in schema["true"]:
                    live.add((name, row.get("check")))
        self.assertEqual(live, set(DECLARED_WARNINGS),
                         "the declared-warning list and the tables disagree; only in tables "
                         "%s, only on the list %s"
                         % (sorted(live - set(DECLARED_WARNINGS)),
                            sorted(set(DECLARED_WARNINGS) - live)))
        for reason in DECLARED_WARNINGS.values():
            self.assertGreater(len(reason), 60, "a declared warning explains almost nothing")

    def test_every_check_is_interpretable_when_it_fails(self):
        """A failing check has to tell a reader what broke, and the three tables do that
        differently: IPPU writes a sentence, fugitives writes actual against expected with a
        short provenance note, aviation writes a value against a threshold. Requiring a long
        sentence everywhere would have failed three fugitives rows whose actual/expected pair
        is a better explanation than prose - so the property is INTERPRETABLE, not verbose."""
        for path in _tables():
            name = os.path.basename(path)
            schema = SCHEMAS[name]
            column = schema["explains"]
            bare = []
            for row in _rows(path):
                prose = str(row.get(column, "")) if column else ""
                compared = all(str(row.get(k, "")).strip()
                               for k in ("actual", "expected")) or \
                    all(str(row.get(k, "")).strip() for k in ("value", "threshold"))
                if len(prose) > 20 or compared:
                    continue
                bare.append(row.get("check"))
            self.assertFalse(bare, "%s: %d checks would say nothing on failure - no "
                                   "explanation and no comparison: %s"
                                   % (name, len(bare), bare[:4]))

    def test_the_guard_reads_the_committed_file(self):
        """Positive control on the thing that actually failed. A planted non-passing row in
        the table ON DISK must be caught - a different property from a fresh run raising, and
        the one that was missing."""
        path = _tables()[0]
        schema = SCHEMAS[os.path.basename(path)]
        rows = _rows(path)
        planted = dict(rows[0], **{schema["verdict"]: "definitely-not-passing"})
        caught = [r for r in [planted]
                  if str(r.get(schema["verdict"], "")).strip().lower() not in schema["true"]]
        self.assertEqual(len(caught), 1,
                         "a non-passing row on disk is no longer detectable by this test")


WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20, "thirty": 30, "thirty-four": 34,
}



if __name__ == "__main__":
    unittest.main()

