"""Status class label reads the 350 m pool (docs/STATUS_SIGNAL_GEOGRAPHY_TEST.md)."""

import unittest
from unittest import mock

import main
from data_sources import census_api


def housing(geo="tract"):
    return {"summary": {"geo_level": geo, "median_household_income": 178041, "median_home_value": 2034859,
                        "median_monthly_housing_cost": 3500.0, "renter_pct": 0.61}, "breakdown": {}}


POOL = {"median_household_income": 141308.0, "median_home_value": 1815385.0, "median_monthly_housing_cost": 3300.0,
        "mean_household_income": 233745.0, "share_households_150k_plus": 55.7, "pooled_tracts": 9}
TRACT = {"state_fips": "36", "county_fips": "047", "tract_fips": "007700"}


class TestStatusPool(unittest.TestCase):
    def test_ring_is_350_m(self):
        self.assertEqual(census_api.STATUS_POOL_RING_M, 350)

    def test_tract_level_read_is_replaced_by_the_pool(self):
        with mock.patch.object(census_api, "get_status_pool_summary", return_value=POOL):
            out = main._housing_at_status_pool(housing(), 40.68, -73.99, TRACT)
        s = out["summary"]
        self.assertEqual(s["median_household_income"], 141308.0)
        self.assertEqual(s["share_households_150k_plus"], 55.7)
        self.assertEqual(s["status_pool"], {"ring_m": 350, "tracts": 9})
        self.assertEqual(s["renter_pct"], 0.61)  # fields the pool does not carry stay

    def test_place_level_read_is_left_alone(self):
        with mock.patch.object(census_api, "get_status_pool_summary", return_value=POOL) as m:
            h = housing("incorporated_place")
            self.assertIs(main._housing_at_status_pool(h, 40.68, -73.99, TRACT), h)
            m.assert_not_called()

    def test_failed_pool_falls_back_to_the_housing_summary(self):
        with mock.patch.object(census_api, "get_status_pool_summary", return_value=None):
            h = housing()
            self.assertIs(main._housing_at_status_pool(h, 40.68, -73.99, TRACT), h)
        with mock.patch.object(census_api, "get_status_pool_summary", side_effect=RuntimeError("boom")):
            h = housing()
            self.assertIs(main._housing_at_status_pool(h, 40.68, -73.99, TRACT), h)

    def test_no_coordinates_or_tract_is_left_alone(self):
        h = housing()
        self.assertIs(main._housing_at_status_pool(h, None, None, TRACT), h)
        self.assertIs(main._housing_at_status_pool(h, 40.68, -73.99, None), h)


if __name__ == "__main__":
    unittest.main()
