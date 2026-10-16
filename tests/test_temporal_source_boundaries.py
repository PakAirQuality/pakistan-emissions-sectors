"""Source observations do not imply a matching emission-process boundary."""
import collections
import unittest

from pkinv.core import monthly
from pkinv.core.io import read_rows
from pkinv.paths import OUTPUTS
from pkinv.report import air_monthly, temporal_profiles
from pkinv.sectors.aviation import monthly_layer
from pkinv.sectors.aviation.data import AviationData


class DomesticFlightTiming(unittest.TestCase):
    def test_actual_purchaser_sales_keep_weights_but_are_a_flight_proxy(self):
        year = 2024  # July2024--June2025, the new core year
        source = collections.defaultdict(float)
        for row in read_rows(OUTPUTS + "/aviation_ocac_monthly.csv"):
            if int(row["fiscal_year"]) == year and row["customer_category"].startswith("Domestic Avi"):
                source[row["period_end"].replace("-", "")] += float(row["monthly_t"])
        self.assertEqual(set(source), set(monthly.months_for(year)))
        denominator = sum(source.values())
        self.assertGreater(denominator, 0)
        components, records = monthly_layer.rows(AviationData(), year)
        self.assertTrue(records)
        for row in records:
            self.assertEqual(row["temporal_method"], "T3")
            self.assertAlmostEqual(row["share"], source[row["month"]] / denominator, places=12)
            self.assertIn("customer and flight-geography boundaries differ", row["basis"])
        # The GHG registry must not promote those same proxy weights back to TE1.
        example = dict(components[0], sector_id="aviation")
        spec = temporal_profiles.resolve(example, year)
        self.assertEqual(set(spec.classes.values()), {"TE3"})
        self.assertEqual(spec.observed_month_count, 0)
        self.assertEqual(spec.timing_target, "proxy_only")
        self.assertIn("aviation_ocac_monthly.csv", spec.source_id)
        self.assertAlmostEqual(sum(spec.weights.values()), 1)


class AirSourceBoundary(unittest.TestCase):
    def test_distinct_flight_and_national_distribution_boundaries_are_downgraded(self):
        months = monthly.months_for(2024)
        profile = {month: dict(share=1. if index == 0 else 0.,
                               temporal_evidence_class="TE1" if index % 2 else "TE2",
                               profile_id="observed_customer_sales", timing_target="fuel_sale",
                               source_id="OCAC") for index, month in enumerate(months)}
        for sector, source in (("aviation", "aviation:Domestic aviation LTO CO2"),
                               ("fugitives", "fug_petrol_distribution_refuelling")):
            atom = dict(period_id="FY2024-25", sector_id=sector, source_class_id=source,
                        support_anchor_id="customer-fuel", process="", subitem="fuel")
            result = air_monthly.profile_for(atom, {("FY2024-25", "customer-fuel"): profile})
            self.assertEqual({row[1] for row in result.values()}, {"TE3"})
            self.assertTrue(all("proxy" in row[3] for row in result.values()))
            for month, row in result.items():
                self.assertEqual(row[0], profile[month]["share"])
        # Direct road-fuel exhaust retains its matching activity support.
        road = dict(atom, sector_id="transport", source_class_id="road:car", process="exhaust")
        result = air_monthly.profile_for(road, {("FY2024-25", "customer-fuel"): profile})
        self.assertEqual({row[1] for row in result.values()}, {"TE1", "TE2"})


if __name__ == "__main__":
    unittest.main()
