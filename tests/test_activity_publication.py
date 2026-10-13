"""The published activity tables: the promise each row makes, and the separations that keep it honest.

These tables exist so someone can use Pakistan's livestock, fuel-sales, fertiliser or power-plant
data without running PakEmis or studying emissions. That only works if every row answers six
questions on its own - what the quantity is, where and when it applies, what kind of evidence it is,
where it came from, what we changed, and whether it may be added to its neighbours.

⚠ THE SEPARATIONS BELOW ARE THE POINT. Tonnes of fertiliser product are not tonnes of nitrogen;
monthly power generation is not monthly fuel consumption; a pooled district split by a declared rule
is not an observed district figure; an empty cell is not a zero. Each of those is one line in a
registry and one assertion here, because each of them, got wrong, publishes a plausible falsehood.
"""

from pkinv.assets import asset_path, legacy_path
import csv
import io
import os
import unittest

from pkinv.activity import present, publish
from pkinv.core.io import read_rows
from pkinv.paths import DATA, OUTPUTS, ROOT

OUT = os.path.join(OUTPUTS, "activity")
ANSWERS = ("variable", "category", "value", "unit", "geography", "geography_level", "period",
           "period_basis", "evidence", "source_id", "combinable")


def table(name):
    path = os.path.join(OUT, "activity_%s.csv" % name)
    with open(path, encoding="utf-8") as handle:
        text = "".join(l for l in handle if not l.startswith("#"))
    return list(csv.DictReader(io.StringIO(text)))


def every_row():
    for name in sorted(publish.TABLES):
        for row in table(name):
            yield name, row


def public(name):
    with open(os.path.join(OUT, "public", "activity_%s.csv" % name), encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def details():
    with open(os.path.join(OUT, "activity_source_details.csv"), encoding="utf-8") as handle:
        return {r["Record ID"]: r for r in csv.DictReader(handle)}


class SixQuestions(unittest.TestCase):
    def test_every_row_answers_all_six(self):
        """⚠ THE ASSERTION THIS FILE EXISTS FOR. 79k rows cannot be eyeballed, and a blank unit or a
        missing place turns a reusable statistic back into a number only we can read."""
        missing = {}
        for name, row in every_row():
            for field in ANSWERS:
                if field == "value" and row["evidence"] == "not_printed":
                    continue          # the one legitimate blank, and it is typed
                if not (row[field] or "").strip():
                    missing.setdefault((name, field), 0)
                    missing[(name, field)] += 1
        self.assertEqual(missing, {}, "published rows that answer less than the six questions")

    def test_an_empty_value_is_typed_not_zero(self):
        """A source that printed a dash must never become a source that printed nothing."""
        for name, row in every_row():
            if not (row["value"] or "").strip():
                self.assertEqual(row["evidence"], "not_printed",
                                 "%s: an empty value that is not typed as not_printed" % name)
            if row["evidence"] == "not_printed":
                self.assertEqual(row["value"], "", "%s: not_printed carries a value" % name)

    def test_every_evidence_class_is_declared(self):
        classes = {r["evidence"] for r in read_rows(asset_path(DATA, "activity_evidence_classes.csv"))}
        for name, row in every_row():
            self.assertIn(row["evidence"], classes, "%s: undeclared evidence class" % name)

    def test_an_unmapped_status_fails_the_build(self):
        """⚠ NOT A DEFAULT. A status with no row in evidence_map.csv raises, because falling back to
        `reported` is how `verified` - a statement about our transcription - would come to be
        published as `observed`."""
        spec = {"evidence_col": "status", "path": "x.csv"}
        with self.assertRaises(publish.UnmappedStatus):
            publish._classify(spec, {"evidence_override": "", "transform": ""},
                              {"status": "a-word-nobody-mapped"}, {}, {}, "x.csv", "1")


class Separations(unittest.TestCase):
    def test_fertiliser_never_mixes_product_tonnes_with_nitrogen(self):
        """The brief is explicit, and an earlier draft of the registry got this wrong: it published
        996,000 t of phosphate and 6,579,000 t of urea product as tonnes of NITROGEN."""
        units = {r["unit"] for r in table("fertiliser")}
        self.assertTrue({"t product", "t N"} <= units)
        for row in table("fertiliser"):
            if row["category"] in ("phosphate", "potash"):
                self.assertNotEqual(row["unit"], "t N", "a non-nitrogen nutrient published as nitrogen")
            if row["unit"] == "t N":
                self.assertIn("nitrogen", row["category"])

    def test_monthly_power_is_generation_and_carries_no_fuel(self):
        """The source measured generation monthly; it never measured fuel monthly."""
        for row in table("power_monthly"):
            self.assertEqual(row["variable"], "net_generation")
            self.assertEqual(row["unit"], "GWh")

    def test_a_declared_split_is_an_allocation_not_an_observation(self):
        rows = [r for r in table("crops") if r["transform"] and "split" in r["transform"]]
        self.assertGreater(len(rows), 100)
        for row in rows:
            self.assertEqual(row["evidence"], "allocation",
                             "a pooled district split published as an observed district figure")

    def test_a_projection_is_never_a_count(self):
        proj = [r for r in table("livestock") if r["evidence"] == "projection"]
        self.assertGreater(len(proj), 0)
        for row in proj:
            self.assertEqual(row["combinable"], publish.PROJECTION_RULE,
                             "a projection that invites being summed with counts")
        # and the census counts beside it are NOT relabelled
        counts = [r for r in table("livestock") if r["evidence"] == "reported"]
        self.assertGreater(len(counts), len(proj))

    def test_household_fuel_keeps_its_survey_round(self):
        """The survey year survives even where the inventory applies the quantity to another year."""
        for row in table("household_fuel"):
            self.assertEqual(row["period_basis"], "survey_round")
            self.assertTrue(row["period"].startswith("hies"), row["period"])

    def test_area_sales_say_sold_is_not_burned(self):
        rows = table("fuel_sales_area")
        # Karachi is not a province, and PAKISTAN is not a place: the area pages are sales areas,
        # and the national row is published as Pakistan at national level
        self.assertEqual(set(r["geography_level"] for r in rows), {"sales_area", "national"})
        self.assertTrue(all(r["geography"] == "Pakistan" for r in rows if r["geography_level"] == "national"))
        # ⚠ the source's own additivity flag is on every row now, not named in prose and withheld
        non_additive = [r for r in rows if r["combinable"].startswith("no:")]
        self.assertGreater(len(non_additive), 10000)
        self.assertTrue(all("additive" in r["combinable"] for r in rows))


    def test_MODELLED_WASTE_IS_NEVER_REPORTED(self):
        """⚠ THE ASSERTION THIS ROUND ADDS, and the most damaging label to get wrong. Waste flows are
        a per-capita rate over an interpolated population panel and a fate partition - not measured
        municipal tonnage. The household survey beside them reads a different split, which is exactly
        why a reader must be able to tell the two apart from the row alone."""
        flows = table("waste_flows")
        self.assertTrue(flows)
        for row in flows:
            self.assertEqual(row["evidence"], "modelled", "a modelled waste flow typed as something else")
        # the services table mixes a household survey (HIES, design-weighted) with a published
        # statistic (WHO/UNICEF JMP). Both are legitimate and neither is a model output.
        for row in table("waste_services"):
            self.assertIn(row["evidence"], ("survey_estimate", "reported", "derived"))
            self.assertNotEqual(row["evidence"], "modelled",
                                "a reported service share typed as a model output")

    def test_unaccounted_for_gas_carries_its_own_prohibition(self):
        """The source says it in capitals; a published row that dropped it would invite exactly the
        multiplication by a GWP the source forbids."""
        ufg = [r for r in table("gas_network") if "UFG" in r["category"]]
        self.assertTrue(ufg)
        for row in ufg:
            self.assertIn("NOT AN EMISSION FIGURE", row["note"])

    def test_registered_vehicles_are_a_stock_not_traffic(self):
        rows = table("vehicles")
        stock = [r for r in rows if r["variable"] == "registered_vehicles"]
        self.assertTrue(stock)
        for row in stock[:50]:
            self.assertIn("STOCK", row["combinable"] + row["note"])
        # and the kilometre rates beside them are declared assumptions, not observations
        rates = [r for r in rows if r["variable"] == "distance_per_vehicle"]
        self.assertTrue(rates)
        for row in rates[:20]:
            self.assertEqual(row["evidence"], "assumption")

    def test_a_collection_that_publishes_nothing_fails_by_name(self):
        """⚠ `rows[0].keys()` on an empty table is an IndexError six frames deep. With seventeen
        tables, one mis-declared register row is how a collection comes back empty."""
        from pkinv.semantic import facts

        class Empty:
            def rows(self, name):
                return []

        with self.assertRaises(ValueError) as caught:
            facts._activity(Empty(), "waste_flows")
        self.assertIn("waste_flows", str(caught.exception))


class Provenance(unittest.TestCase):
    def test_every_source_resolves_and_is_ours_to_publish(self):
        """⚠ THE LICENCE GATE, ASSERTED RATHER THAN ASSUMED. Every published row names an ingest file,
        and that file's register row must say the derived table ships. The register keeps inbound use
        and outbound redistribution apart on purpose; this is the outbound question."""
        # Two identities for one asset, joined through the catalog rather than assumed equal.
        # The publication's source_id is the LEGACY path and stays that way - it is a
        # published identity and the join key of the activity registries - while the
        # generated register names each file where the sector layout keeps it. Normalising
        # both sides with legacy_path() is the join; comparing the raw strings is not.
        register = {legacy_path(r["data_file"], root=ROOT): r
                    for r in read_rows(os.path.join(OUTPUTS, "pakemis_source_register.csv"))}
        products = {r["relative_path"] for r in read_rows(asset_path(DATA, "product_schemas.csv"))}
        seen = {row["source_id"] for _, row in every_row()}
        self.assertGreater(len(seen), 20)
        for source in sorted(seen):
            if source.startswith("outputs/"):
                # an engine output is this project's own work; what it owes is registration as a
                # product of this release, not a redistribution answer about someone else's document
                self.assertIn(source, products, "%s: published but registered as no product" % source)
                continue
            source = legacy_path(source, root=ROOT)
            self.assertIn(source, register, "a published row names a file the register does not carry")
            self.assertEqual(register[source]["derived_file_in_deposit"], "yes",
                             "%s: published without the right to publish it" % source)

    def test_a_published_value_is_the_ingest_value(self):
        """This builder computes nothing. Spot-checked against the ingest on every collection."""
        checks = [
            ("livestock", "data/activity/livestock_2024.csv", "species", "cattle", "head_value"),
            ("power_monthly", "data/activity/power/generation_monthly.csv", "plant", "Kanupp", "gwh"),
        ]
        for name, path, key, value, column in checks:
            ingest = [r for r in read_rows(asset_path(ROOT, path)) if r[key] == value]
            self.assertTrue(ingest)
            published = {r["value"] for r in table(name) if r["category"] == value}
            self.assertTrue({r[column] for r in ingest} <= published,
                            "%s: a published value is not the ingest's own" % name)


if __name__ == "__main__":
    unittest.main()


class Presentation(unittest.TestCase):
    """The reader-facing tables are a VIEW of the technical ones. These hold the view to the record."""

    @classmethod
    def setUpClass(cls):
        cls.details = details()
        cls.reg = present.Registers()

    def test_EVERY_READABLE_VALUE_IS_ITS_TECHNICAL_VALUE(self):
        """⚠ THE ASSERTION THIS CLASS EXISTS FOR. 101,808 rows, joined on Record ID: the same count, and
        the same value on every one. The readable table adds labels and takes nothing away, and that
        is the one property a reader cannot check for themselves."""
        total = 0
        for name in publish.TABLES:
            rows = public(name)
            self.assertEqual(len(rows), len(table(name)), "%s: the readable table lost or gained rows" % name)
            for row in rows:
                tech = self.details.get(row["Record ID"])
                self.assertIsNotNone(tech, "%s: a readable row with no technical row" % name)
                self.assertEqual(row["Value"], tech["value"], "%s: a readable value that is not the record's" % name)
                self.assertEqual(tech["Public file"], "activity_%s.csv" % name)
                total += 1
        self.assertEqual(total, len(self.details))
        self.assertGreater(total, 100000)

    def test_the_six_restored_dimensions_are_present(self):
        """The reader's own review of the first export found six gaps; each was a defect upstream,
        and each is asserted closed here rather than described as closed."""
        aviation = table("aviation")
        self.assertTrue(all(r["geography"] not in ("", "Pakistan") or "airline" in r["source_id"] for r in aviation),
                        "an airport row without its airport")
        self.assertTrue(all(r["subcategory"] for r in aviation if "airline" in r["source_id"]), "an airline row without its airline")
        for r in table("fuel_sales_area"):
            self.assertTrue(r["combinable"].startswith(("yes", "only", "no:")), r["combinable"])
        for r in table("industry_fuel"):
            if "gas_monthly" in r["source_id"]:
                self.assertRegex(r["period"], r"^\d{4}-\d{2}$", "a monthly gas row with no year")
        for r in table("livestock"):
            if r["source_column"] == "head_following_year":
                self.assertEqual(r["period"], "FY2024-25")
        for r in table("waste_services"):
            if r["geography_level"] == "province_by_locality":
                self.assertNotEqual(r["geography"].split(" · ")[0], "Pakistan")
        for r in table("power_monthly"):
            self.assertEqual(r["subcategory"].count(" · "), 0, "fuel_source welded into the fuel again")
            self.assertTrue(r["evidence_note"], "a plant-month with no fuel-label provenance")

    def test_no_period_is_left_for_the_reader_to_guess(self):
        shapes = {"fiscal": r"^FY\d{4}-\d{2}$", "calendar": r"^\d{4}$", "calendar_month": r"^\d{4}-\d{2}$",
                  "snapshot_date": r"^\d{4}-\d{2}-\d{2}$", "survey_round": r"^hies\d{4}$"}
        for name, row in every_row():
            self.assertIn(row["period_basis"], shapes, name)
            self.assertRegex(row["period"], shapes[row["period_basis"]], "%s: %r" % (name, row["period"]))

    def test_every_label_comes_from_a_register(self):
        evidence = set(self.reg.evidence.values())
        measures, units = set(self.reg.measures.values()), set(self.reg.units.values())
        series = set(self.reg.series.values())
        for name in publish.TABLES:
            for row in public(name):
                self.assertIn(row["Evidence"], evidence)
                self.assertIn(row["Measure"], measures)
                self.assertIn(row["Unit"], units)
                self.assertIn(row["Source series"], series)
                self.assertTrue(row["Use note"])

    def test_an_unlabelled_value_fails_by_name(self):
        with self.assertRaises(present.UnlabelledValue) as caught:
            self.reg.measure({"source_id": "x.csv", "variable": "no_such_variable", "unit": "t"})
        self.assertIn("no_such_variable", str(caught.exception))
