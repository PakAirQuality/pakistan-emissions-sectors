"""VALIDATION_MANIFEST.json validates against the schema it ships with (rc42, R6).

The rc41 manifest carried ten known exceptions whose lifetime read "permanent for this
release" against a schema enum of temporary | permanent, and nothing in the package or the
packager validated the manifest against its own schema. The packager validates both the
pre-validation and the final manifest now; this test does it again inside the package, with
jsonschema where it is installed and a standard-library subset (required keys, enums,
consts, patterns) where it is not. Package-only.
"""
import json
import os
import re
import unittest

from _support import ROOT
from validation._package import IN_PACKAGE, MANIFEST

SCHEMA = os.path.join(ROOT, "VALIDATION_MANIFEST.schema.json")


def _subset_validate(schema, value, path="$"):
    """The subset of JSON Schema this manifest's schema uses: type, required, properties,
    items, enum, const, pattern, additionalProperties (typed)."""
    problems = []
    kind = schema.get("type")
    if isinstance(kind, str):
        kind = [kind]
    if kind:
        ok = {"object": dict, "array": list, "string": str, "boolean": bool,
              "integer": int, "number": (int, float), "null": type(None)}
        if not any(isinstance(value, ok[k]) and not (k == "integer" and isinstance(value, bool)) for k in kind):
            problems.append("%s: type %s expected" % (path, "/".join(kind)))
            return problems
    if "const" in schema and value != schema["const"]:
        problems.append("%s: %r is not the constant %r" % (path, value, schema["const"]))
    if "enum" in schema and value not in schema["enum"]:
        problems.append("%s: %r is not one of %r" % (path, value, schema["enum"]))
    if "pattern" in schema and isinstance(value, str) and not re.search(schema["pattern"], value):
        problems.append("%s: %r does not match %r" % (path, value, schema["pattern"]))
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                problems.append("%s: required key %r absent" % (path, key))
        for key, sub in schema.get("properties", {}).items():
            if key in value:
                problems += _subset_validate(sub, value[key], "%s.%s" % (path, key))
        extra = schema.get("additionalProperties")
        if isinstance(extra, dict):
            for key, item in value.items():
                if key not in schema.get("properties", {}):
                    problems += _subset_validate(extra, item, "%s.%s" % (path, key))
    if isinstance(value, list) and "items" in schema:
        for index, item in enumerate(value):
            problems += _subset_validate(schema["items"], item, "%s[%d]" % (path, index))
    return problems


class TestTheManifestValidatesAgainstItsSchema(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not IN_PACKAGE or not os.path.exists(SCHEMA):
            raise unittest.SkipTest("only inside a built validation package")
        with open(SCHEMA, encoding="utf-8") as handle:
            cls.schema = json.load(handle)
        with open(MANIFEST, encoding="utf-8") as handle:
            cls.manifest = json.load(handle)

    def test_the_subset_validator_passes(self):
        problems = _subset_validate(self.schema, self.manifest)
        self.assertEqual(problems, [], "\n".join(problems))

    def test_jsonschema_passes_where_installed(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema not installed; the stdlib subset check stands in")
        jsonschema.Draft202012Validator(self.schema).validate(self.manifest)

    def test_the_subset_validator_catches_the_rc41_defect(self):
        bad = json.loads(json.dumps(self.manifest))
        bad["known_exceptions"][0]["temporary_or_permanent"] = "permanent for this release"
        problems = _subset_validate(self.schema, bad)
        self.assertTrue(any("temporary_or_permanent" in p for p in problems), problems)

    def test_every_exception_lifetime_is_the_enum(self):
        for exc in self.manifest["known_exceptions"]:
            self.assertIn(exc["temporary_or_permanent"], ("temporary", "permanent"), exc["exception_id"])

    def test_the_final_stage_is_the_shipped_one(self):
        """The manifest a reviewer holds says `final`. The packager runs the suites BEFORE it
        writes the final records (so the reproduction ledger they read is real), and marks
        those runs PKINV_PACKAGER_STAGE=pre; the records gate over the finished tree, and
        every later run, sees `final`."""
        if os.environ.get("PKINV_PACKAGER_STAGE") == "pre":
            self.skipTest("packager pre-stage run: the final records are written after the suites")
        self.assertEqual(self.manifest["release"].get("stage"), "final")


if __name__ == "__main__":
    unittest.main()
