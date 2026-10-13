"""query_activity: rows of one activity table as the source printed them, with their definitions.

Built for the question an assistant could not answer: "how many cars are in Lahore". The record
exists (fact_activity_vehicles, Lahore, 30 June 2023, Provincial Bureaux of Statistics); what was
missing was a typed function that returns it with the use note that says it is a registered
stock and not traffic."""
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SEMANTIC = os.path.join(ROOT, "outputs", "semantic")


class TestQueryActivity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.exists(os.path.join(SEMANTIC, "semantic_release.json")):
            raise unittest.SkipTest("semantic release not built")
        from pakemis_query.engine import Engine
        from pakemis_query.release import Release
        cls.engine = Engine(Release.open(SEMANTIC, verify=False,
                                         manifest_path=os.path.join(ROOT, "outputs", "release_manifest.json")))

    def _ask(self, **kw):
        from pakemis_query import functions as F
        from pakemis_query.models import QueryActivity
        return F.query_activity(self.engine, QueryActivity(**kw))

    def test_the_function_is_in_the_contract(self):
        self.assertIn("query_activity", self.engine.release.contract["query_contract"]["functions"])

    def test_lahore_cars_come_back_as_a_dated_registered_stock_with_the_use_note(self):
        env = self._ask(table="fact_activity_vehicles", locations=("Lahore",), categories=("Small cars (4W1)",))
        self.assertEqual(len(env["values"]), 1)
        v = env["values"][0]
        self.assertEqual(v["location"], "Lahore")
        self.assertEqual(v["category"], "Small cars (4W1)")
        self.assertEqual(v["period_type"], "Snapshot date")
        self.assertRegex(v["period_label"], r"^\d{1,2} \w+ \d{4}$")
        self.assertEqual(v["unit"], "vehicles")
        self.assertIn("not traffic", v["use_note"])
        self.assertTrue(v["source_series"] and v["source_reference"] and v["record_id"])
        self.assertIn("periods", env["context"]["defaults_applied"])
        self.assertEqual(env["calculation"]["kind"], "records")
        self.assertIn("Vehicle class", env["calculation"]["class_columns"])
        self.assertIn("Measure", env["calculation"]["definitions"])

    def test_latest_period_is_per_place_and_class_never_a_sum(self):
        env = self._ask(table="fact_activity_vehicles", locations=("Lahore",), measure="Registered vehicles")
        periods = {v["period"] for v in env["values"]}
        self.assertEqual(len(periods), 1, "one newest date for every class")
        classes = [v["category"] for v in env["values"]]
        self.assertEqual(len(classes), len(set(classes)))
        for v in env["values"]:
            self.assertEqual(v["formula"], "as printed by the source; no arithmetic")

    def test_an_explicit_period_is_honoured_and_the_count_reads_grouped_and_in_millions(self):
        env = self._ask(table="fact_activity_vehicles", locations=("Lahore",), periods=("2016-06-30",),
                        categories=("Small cars (4W1)",))
        self.assertEqual(env["context"]["periods"], ["2016-06-30"] if isinstance(env["context"]["periods"], list) else ("2016-06-30",))
        self.assertNotIn("periods", env["context"]["defaults_applied"])
        v = env["values"][0]
        self.assertTrue(v["display_words"].endswith(" million"))
        # the figure as the source printed it, grouped and unrounded
        self.assertEqual(v["display"].replace(",", ""), str(int(float(v["exact"]))))
        self.assertIn(",", v["display"])
        self.assertNotIn("display_short", v, "the API's name for its own two-decimal rendering")

    def test_a_year_finds_the_register_dated_inside_it(self):
        year = self._ask(table="fact_activity_vehicles", locations=("Lahore",), periods=("2023",),
                         categories=("Small cars (4W1)",))
        date = self._ask(table="fact_activity_vehicles", locations=("Lahore",), periods=("2023-06-30",),
                         categories=("Small cars (4W1)",))
        self.assertEqual([v["record_id"] for v in year["values"]], [v["record_id"] for v in date["values"]])
        self.assertEqual(len(year["values"]), 1)

    def test_a_period_the_release_does_not_hold_is_refused_with_the_span_it_does_hold(self):
        """"What is the 2026 count?" must not come back empty, which reads as zero."""
        from pakemis_query import errors as E
        with self.assertRaises(E.UnknownDimensionValue) as cm:
            self._ask(table="fact_activity_vehicles", locations=("Lahore",), measure="Registered vehicles",
                      periods=("2026",))
        self.assertIn("nothing later", cm.exception.message)
        self.assertNotIn("fact_activity", cm.exception.message, "a reader is shown this sentence")
        self.assertRegex(cm.exception.message, r"\d{1,2} \w+ \d{4} to \d{1,2} \w+ \d{4}")
        self.assertEqual(cm.exception.detail["dimension"], "periods")
        newest = self._ask(table="fact_activity_vehicles", locations=("Lahore",), categories=("Small cars (4W1)",))
        self.assertEqual(cm.exception.detail["last_period"], newest["values"][0]["period"])

    def test_a_place_the_table_does_not_name_is_refused_with_the_near_names(self):
        from pakemis_query import errors as E
        with self.assertRaises(E.UnknownDimensionValue) as cm:
            self._ask(table="fact_activity_vehicles", locations=("Lahor",))
        self.assertIn("Lahore", cm.exception.message)

    def test_every_row_carries_where_it_sits_in_the_deposit_and_whether_it_combines(self):
        env = self._ask(table="fact_activity_vehicles", locations=("Lahore",), measure="Registered vehicles")
        for v in env["values"]:
            self.assertTrue(v["source_table"].endswith(".csv") and v["source_row"].isdigit(), v)
            self.assertTrue(v["combinable"].lower().startswith("yes"), v)

    def test_the_total_is_one_more_value_marked_as_computed_and_equal_to_its_rows(self):
        from decimal import Decimal
        rows = self._ask(table="fact_activity_vehicles", locations=("Lahore",), measure="Registered vehicles")
        env = self._ask(table="fact_activity_vehicles", locations=("Lahore",), measure="Registered vehicles", total=True)
        self.assertEqual(len(env["values"]), len(rows["values"]) + 1)
        total = env["values"][-1]
        self.assertEqual(Decimal(total["exact"]), sum(Decimal(v["exact"]) for v in rows["values"]))
        self.assertEqual(total["derived"], "sum")
        self.assertIn("not a figure the source printed", total["interpretation"])
        self.assertEqual(total["result_row_ids"], [v["record_id"] for v in rows["values"]])
        self.assertEqual(total["classes_summed"].split("; "), [v["category"] for v in rows["values"]])
        self.assertEqual((total["period"], total["location"], total["unit"]),
                         (rows["values"][0]["period"], "Lahore", "vehicles"))
        self.assertIn("not traffic", total["use_note"])
        for v in env["values"][:-1]:
            self.assertNotIn("derived", v)
        self.assertTrue(env["calculation"]["total"])
        self.assertFalse(rows["calculation"]["total"])

    def test_a_total_wider_than_one_place_period_and_measure_is_refused(self):
        """A register summed across years counts each vehicle once per year."""
        from pakemis_query import errors as E
        cases = (dict(locations=("Lahore",), measure="Registered vehicles", periods=("2022", "2023")),
                 dict(locations=("Lahore", "Karachi"), measure="Registered vehicles"),
                 dict(locations=("Pakistan",)))                       # several measures, some not combinable
        for kw in cases:
            with self.assertRaises(E.GrainUnavailable, msg=kw):
                self._ask(table="fact_activity_vehicles", total=True, **kw)

    def test_rows_the_release_bars_from_combining_are_never_summed(self):
        """Livestock mixes census counts with forward estimates; the combinable column says so."""
        from pakemis_query import errors as E
        with self.assertRaises(E.GrainUnavailable) as cm:
            self._ask(table="fact_activity_livestock", locations=("Pakistan",), total=True)
        self.assertIn("not to be combined", cm.exception.message)

    def test_a_missing_or_unknown_table_is_a_typed_refusal_that_lists_the_tables(self):
        from pakemis_query import errors as E
        with self.assertRaises(E.UnknownDimensionValue) as cm:
            self._ask()
        self.assertIn("fact_activity_vehicles", str(cm.exception))
        with self.assertRaises(E.UnknownDimensionValue):
            self._ask(table="fact_annual")
        with self.assertRaises(E.UnknownDimensionValue):
            self._ask(table="fact_activity_source_details")

    def test_a_location_level_is_matched_without_case_and_a_wrong_one_lists_the_levels(self):
        """The first caller typed "district"; the table prints "District" and refused it."""
        from pakemis_query import errors as E
        typed = self._ask(table="fact_activity_vehicles", locations=("Lahore",), location_level="district")
        printed = self._ask(table="fact_activity_vehicles", locations=("Lahore",), location_level="District")
        self.assertTrue(typed["values"])
        self.assertEqual([v["record_id"] for v in typed["values"]], [v["record_id"] for v in printed["values"]])
        self.assertEqual({v["location_level"] for v in typed["values"]}, {"District"})
        with self.assertRaises(E.UnknownDimensionValue) as cm:
            self._ask(table="fact_activity_vehicles", location_level="city")
        self.assertIn("District", str(cm.exception))

    def test_every_activity_table_answers_with_its_own_class_columns(self):
        from pakemis_query.functions import activity_tables
        tables = activity_tables(self.engine.release)
        self.assertGreaterEqual(len(tables), 15)
        for table in tables:
            env = self._ask(table=table, limit=5)
            self.assertTrue(env["values"], table)
            for v in env["values"]:
                self.assertTrue(v["measure"] and v["unit"] is not None and v["record_id"], table)
                self.assertEqual(set(v["classes"]), set(env["calculation"]["class_columns"]), table)

    def test_the_receipt_replays(self):
        env = self._ask(table="fact_activity_livestock", limit=3)
        self.assertTrue(env.get("receipt"))
        again = self._ask(table="fact_activity_livestock", limit=3)
        self.assertEqual(env["receipt"], again["receipt"])


if __name__ == "__main__":
    unittest.main()
