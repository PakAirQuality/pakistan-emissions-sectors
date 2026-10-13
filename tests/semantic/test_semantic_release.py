"""The semantic release describes the release, and the release hashes it (v1.0.0 program).

outputs/semantic/ is the one numerical truth layer the paper, the Explorer and the downloads
consume by release id and hash. These tests hold it to the products it derives from: every
table's identity is its canonical CSV text, that digest is what the release manifest records,
the source products it names are the ones the manifest hashed, its columns are the registered
ones, its defaults are members of its dimensions, and a rebuild is byte-identical.
"""

from pkinv.assets import asset_path
import hashlib
import json
import os
import unittest

import pkinv
from pkinv.core.io import read_rows
from pkinv.core.manifest import sha256_file
from pkinv.paths import DATA, OUTPUTS, ROOT
from pkinv.semantic import OUT_DIR, SCHEMA
from pkinv.semantic.canonical import canonical_csv_text, sha256_text

RELEASE = os.path.join(OUT_DIR, "semantic_release.json")
SCHEMA_FILE = asset_path(DATA, "schemas", "semantic_release.schema.json")


def _load():
    with open(RELEASE, encoding="utf-8") as handle:
        return json.load(handle)


def _subset_validate(schema, obj, path="$"):
    """Enough of JSON Schema to hold the contract without the jsonschema package: type,
    required, properties, enum, items; the full validator runs when it is installed."""
    problems = []
    kind = schema.get("type")
    kinds = {"object": dict, "array": list, "string": str, "number": (int, float), "integer": int,
             "boolean": bool}
    if kind and kind in kinds and not isinstance(obj, kinds[kind]):
        problems.append("%s: expected %s" % (path, kind))
        return problems
    for key in schema.get("required", []):
        if key not in obj:
            problems.append("%s: missing %s" % (path, key))
    for key, sub in schema.get("properties", {}).items():
        if key in obj:
            problems += _subset_validate(sub, obj[key], "%s.%s" % (path, key))
    if "enum" in schema and obj not in schema["enum"]:
        problems.append("%s: %r not in %s" % (path, obj, schema["enum"]))
    if "items" in schema and isinstance(obj, list):
        for i, item in enumerate(obj):
            problems += _subset_validate(schema["items"], item, "%s[%d]" % (path, i))
    return problems


class TestTheContractIsWellFormed(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.exists(RELEASE):
            raise unittest.SkipTest("semantic release not built")
        cls.release = _load()

    def test_schema_and_identity(self):
        self.assertEqual(self.release["schema"], SCHEMA)
        self.assertEqual(self.release["release"]["version"], pkinv.__version__)
        self.assertEqual(self.release["release"]["release_id"], "PakEmis %s" % pkinv.__version__)
        self.assertEqual(self.release["release"]["lulucf"]["status"], "excluded")

    def test_validates_against_its_json_schema(self):
        with open(SCHEMA_FILE, encoding="utf-8") as handle:
            schema = json.load(handle)
        problems = _subset_validate(schema, self.release)
        self.assertEqual(problems, [])
        try:
            import jsonschema
        except ImportError:
            return
        jsonschema.Draft202012Validator(schema).validate(self.release)

    def test_defaults_are_members_of_their_dimensions(self):
        d = self.release["defaults"]
        periods = {r["period_id"] for r in read_rows(os.path.join(OUT_DIR, "dim_period.csv"))}
        configurations = {r["configuration_id"]: r for r in read_rows(os.path.join(OUT_DIR, "dim_configuration.csv"))}
        geographies = {r["geography_id"] for r in read_rows(os.path.join(OUT_DIR, "dim_geography.csv"))}
        self.assertIn(d["period_id"], periods)
        self.assertEqual(configurations[d["configuration_id"]]["queryable"], "yes")
        self.assertIn(d["geography_id"], geographies)
        self.assertIn(d["gwp_basis"], {r["gwp_basis"] for r in read_rows(os.path.join(OUT_DIR, "dim_gwp.csv"))})
        self.assertEqual(d["spatial_view"], "all")
        self.assertEqual(d["basis"], "fiscal")

    def test_every_completeness_gap_is_a_known_limitation(self):
        gaps = {r["gap_id"] for r in read_rows(os.path.join(OUTPUTS, "completeness.csv"))
                if r["notation_key"] in ("NE", "NO") and r["gap_id"]}
        listed = {l["id"].split(":", 1)[1] for l in self.release["known_limitations"]
                  if l["id"].startswith("completeness:")}
        self.assertEqual(gaps, listed)


class TestEveryTableIsWhatTheContractSays(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.exists(RELEASE):
            raise unittest.SkipTest("semantic release not built")
        cls.release = _load()
        cls.tables = dict(cls.release["dimensions"], **cls.release["facts"])

    def test_the_csv_is_the_identity(self):
        for name, t in self.tables.items():
            path = asset_path(ROOT, t["path"])
            self.assertTrue(os.path.exists(path), name)
            self.assertEqual(sha256_file(path), t["sha256_csv"], name)
            rows = read_rows(path, comments=False)
            self.assertEqual(len(rows), t["rows"], name)
            self.assertEqual(list(rows[0].keys()), t["columns"], name)
            # sorted by key, header first, LF: re-serialising reproduces the digest
            text = canonical_csv_text(t["columns"], rows, tuple(t["primary_key"]))
            self.assertEqual(sha256_text(text), t["sha256_csv"], "%s is not in canonical form" % name)

    def test_the_parquet_twin_reserialises_to_the_csv(self):
        try:
            import pyarrow.parquet as pq
        except ImportError:
            self.skipTest("pyarrow not installed")
        for name, t in self.tables.items():
            path = asset_path(ROOT, t["parquet"]["path"])
            if not os.path.exists(path):
                continue
            table = pq.read_table(path).to_pylist()
            text = canonical_csv_text(t["columns"], table, tuple(t["primary_key"]))
            self.assertEqual(sha256_text(text), t["sha256_csv"], name)

    def test_primary_keys_are_unique_and_row_ids_stable(self):
        from pkinv.semantic.canonical import row_id
        for name, t in self.tables.items():
            rows = read_rows(asset_path(ROOT, t["path"]), comments=False)
            keys = [tuple(r[k] for k in t["primary_key"]) for r in rows]
            self.assertEqual(len(keys), len(set(keys)), "%s: duplicate primary key" % name)
            id_column = t.get("aggregation", {}).get("id_column")
            if id_column:
                # rc59: the readable activity tables carry ONE id, their declared column
                self.assertNotIn("result_row_id", t["columns"], name)
                self.assertEqual(t["primary_key"], [id_column], name)
                continue
            for r in rows[:50]:
                self.assertEqual(r["result_row_id"], row_id(name, [r[k] for k in t["primary_key"]]), name)

    def test_the_manifest_hashes_every_table_and_every_source(self):
        # against a FRESH manifest build, as test_the_release_manifest_regenerates_identically
        # does: the committed manifest is the last release's until the fixpoint re-cuts it
        from pkinv.report import release_manifest as rm
        manifest = {p["path"]: p["sha256"] for p in rm.build()["products"]}
        for name, t in self.tables.items():
            self.assertEqual(manifest.get(t["path"]), t["sha256_csv"],
                             "%s is not hashed by the release manifest as the contract says" % name)
        for p in self.release["products"]:
            # a source the manifest hashes must agree with it; one it does not (a data
            # registry, a report the manifest's patterns skip) is held to the file itself
            expected = manifest.get(p["path"]) or sha256_file(asset_path(ROOT, p["path"]))
            self.assertEqual(expected, p["sha256"],
                             "%s: the contract's source digest differs from the release's" % p["path"])
        self.assertIn("outputs/semantic/semantic_release.json", manifest)

    def test_columns_are_registered(self):
        registered = {}
        for r in read_rows(asset_path(DATA, "product_columns.csv")):
            registered.setdefault(r["product_id"], []).append(r["column"])
        for name, t in self.tables.items():
            self.assertEqual(registered.get("semantic." + name), t["columns"], name)

    def test_the_build_is_byte_stable(self):
        from pkinv.semantic import build
        self.assertEqual(build.main(["--check"]), 0)


class TestTheClosuresTheContractStates(unittest.TestCase):
    """The two computed tables against the closures the release already publishes."""

    @classmethod
    def setUpClass(cls):
        if not os.path.exists(RELEASE):
            raise unittest.SkipTest("semantic release not built")

    def test_adm1_sums_back_to_the_stream_month(self):
        from decimal import Decimal
        monthly = {(r["component_id"], r["month"]): Decimal(r["native_mass"])
                   for r in read_rows(os.path.join(OUT_DIR, "fact_monthly.csv"), comments=False)
                   if r["period_id"] == "FY2023-24" and r["configuration_id"] == "REF_2023_24"}
        sums = {}
        for r in read_rows(os.path.join(OUT_DIR, "fact_adm1_month.csv"), comments=False):
            if r["configuration_id"] != "REF_2023_24":
                continue
            k = (r["source_stream_id"], r["month"])
            sums[k] = sums.get(k, Decimal(0)) + Decimal(r["emissions_Gg"])
        # the declared shares carry five decimals, so a stream's provinces sum back to its
        # month to the precision of those shares: relative, not absolute
        worst = max((abs(sums[k] - monthly[k]) / monthly[k]) if monthly[k] else Decimal(0) for k in sums)
        self.assertLess(worst, Decimal("1e-4"), "ADM1 does not sum back to the stream month (worst rel %s)" % worst)
        self.assertEqual(set(sums), set(monthly), "a reference stream-month has no ADM1 rows")

    def test_configuration_l_composes_to_the_published_ledger_total(self):
        """REF - residential(REF) + residential(L) is the configuration-L national total.

        rc67: the roles swapped. The reference carries the household survey's dung and
        the period-named second configuration is L_2023_24, all the diverted dung burned
        in households, so the composition lands on national_all_sectors_ledger.csv and
        the reference on national_all_sectors.csv. The pinned form of this test, below,
        keeps the rc66 totals until the national total settles; this one joins the same
        closure to the published files and pins only the residential pair, which does not
        depend on any other sector (24.22042 under the reference, was 29.46668; 29.46668
        under L, where S_2023_24 was 24.33389)."""
        from decimal import Decimal

        def published(name):
            return next(Decimal(r["co2e_Mt_AR5"])
                        for r in read_rows(os.path.join(OUTPUTS, name))
                        if r["row_kind"] == "national_total")

        rows = read_rows(os.path.join(OUT_DIR, "fact_annual.csv"), comments=False)
        self.assertFalse({r["configuration_id"] for r in rows} & {"S_2023_24", "S_HIES1925"})
        ref = sum(Decimal(r["co2e_Mt_AR5"]) for r in rows if r["period_id"] == "FY2023-24"
                  and r["configuration_id"] == "REF_2023_24")
        ref_res = sum(Decimal(r["co2e_Mt_AR5"]) for r in rows if r["period_id"] == "FY2023-24"
                      and r["configuration_id"] == "REF_2023_24" and r["sector_id"] == "residential")
        l_rows = [r for r in rows if r["configuration_id"] == "L_2023_24"]
        self.assertEqual({r["period_id"] for r in l_rows}, {"FY2023-24"})
        self.assertEqual({r["sector_id"] for r in l_rows}, {"residential"})
        l_res = sum(Decimal(r["co2e_Mt_AR5"]) for r in l_rows)
        self.assertAlmostEqual(float(ref_res), 24.22042, places=4)
        self.assertAlmostEqual(float(l_res), 29.46668, places=4)
        self.assertAlmostEqual(float(ref), float(published("national_all_sectors.csv")),
                               places=4)
        self.assertAlmostEqual(float(ref - ref_res + l_res),
                               float(published("national_all_sectors_ledger.csv")), places=4)

    def test_the_configuration_dimension_names_the_ledger(self):
        """dim_configuration after rc67: REF_2023_24 is the reference and says its dung is
        the survey's; L_2023_24 (queryable, FY2023-24) and L_HERD1624 (the air panel's
        nine-year series) are of kind "ledger"; the retired survey ids are gone, and the
        ledger's national delta is positive."""
        dim = {r["configuration_id"]: r
               for r in read_rows(os.path.join(OUT_DIR, "dim_configuration.csv"))}
        self.assertNotIn("S_2023_24", dim)
        self.assertNotIn("S_HIES1925", dim)
        self.assertEqual(dim["REF_2023_24"]["kind"], "reference")
        self.assertIn("survey", dim["REF_2023_24"]["note"])
        for cid in ("L_2023_24", "L_HERD1624"):
            self.assertEqual(dim[cid]["kind"], "ledger", cid)
            self.assertEqual(dim[cid]["substitutes_module"], "residential", cid)
        self.assertNotIn("survey", {r["kind"] for r in dim.values()})
        self.assertEqual(dim["L_2023_24"]["queryable"], "yes")
        self.assertEqual(dim["L_2023_24"]["available_periods"], "FY2023-24")
        self.assertEqual(dim["L_2023_24"]["display_name"], "all_diverted_dung_household_fuel")
        self.assertEqual(dim["L_HERD1624"]["available_periods"], "FY2015-16..FY2023-24")
        self.assertAlmostEqual(float(dim["L_2023_24"]["national_delta_Mt"]), 5.24626, places=5)
        self.assertEqual(float(dim["REF_2023_24"]["national_delta_Mt"]), 0.0)
        limitations = {l["id"] for l in _load()["known_limitations"]}
        self.assertIn("config_L_residential_only", limitations)
        self.assertNotIn("config_S_residential_only", limitations)
        self.assertEqual(_load()["release"]["ledger_configuration"], "L_2023_24")
        self.assertNotIn("survey_configuration", _load()["release"])

    def test_configuration_s_composes_to_the_survey_pin(self):
        from decimal import Decimal
        rows = read_rows(os.path.join(OUT_DIR, "fact_annual.csv"), comments=False)
        ref = sum(Decimal(r["co2e_Mt_AR5"]) for r in rows if r["period_id"] == "FY2023-24"
                  and r["configuration_id"] == "REF_2023_24")
        ref_res = sum(Decimal(r["co2e_Mt_AR5"]) for r in rows if r["period_id"] == "FY2023-24"
                      and r["configuration_id"] == "REF_2023_24" and r["sector_id"] == "residential")
        s_res = sum(Decimal(r["co2e_Mt_AR5"]) for r in rows if r["configuration_id"] == "L_2023_24")
        # rc46 Wave 2 pins (previous: 452.34662 / 447.21383)
        # rc67 reference re-base: the reference (survey dung) and configuration L
        self.assertAlmostEqual(float(ref), 444.95542, places=4)   # was 451.85782 at rc66
        self.assertAlmostEqual(float(ref - ref_res + s_res), 450.20168, places=4)   # was 446.72502 (then S)


if __name__ == "__main__":
    unittest.main()
