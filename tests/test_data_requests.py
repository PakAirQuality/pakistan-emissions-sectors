"""The normalized request model preserves every sector assignment and old view row."""
import unittest

from pkinv.activity.store import read_rows
from pkinv.data_requests import COMPONENTS, REGISTER, VIEW, VIEW_FIELDS, rows, run
from pkinv.assets import resolve


class MonthlyRequestModelTests(unittest.TestCase):
    def test_register_and_relations_round_trip_legacy_rows(self):
        register = read_rows(REGISTER)
        components = read_rows(COMPONENTS)
        legacy = read_rows("data/monthly_data_requests.csv")
        self.assertEqual(len(register), 16)
        self.assertEqual(len(components), 31)
        self.assertEqual(rows(), legacy)
        self.assertEqual(list(legacy[0]), list(VIEW_FIELDS))
        self.assertEqual(len({row["request_id"] for row in register}), len(register))
        self.assertEqual(len({(row["request_id"], row["sector_id"], row["component"])
                              for row in components}), len(components))
        self.assertTrue(all(row["date_sent"] == "" for row in legacy))
        self.assertTrue(all(row["response_status"] == "not_sent" for row in legacy))

    def test_old_identity_resolves_to_generated_view(self):
        self.assertTrue(resolve("data/monthly_data_requests.csv").endswith(
            "data/shared/requests/views/monthly_data_requests.csv"))

    def test_view_is_current(self):
        self.assertEqual(run(check=True), 0)


if __name__ == "__main__":
    unittest.main()
