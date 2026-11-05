"""Live fetch: the share of households at $150,000 or more comes from B19001 bins 016 and 017."""

import unittest
from unittest import mock

from data_sources import census_api


class _Resp:
    def __init__(self, rows):
        self._rows = rows

    def json(self):
        return self._rows


def _row(b016, b017, total="1000"):
    # B25077, B19013, B25018, B19025, B19001_001, B25064, B25003_001, B25003_003, B25105, B19001_016, B19001_017, NAME
    return [["h"], ["500000", "100000", "5.5", "150000000", total, "2000", "1000", "400", "2500", b016, b017, "Tract 1"]]


class TestHouseholdShare(unittest.TestCase):
    def fetch(self, rows):
        with mock.patch.object(census_api, "_make_request_with_retry", return_value=_Resp(rows)):
            return census_api._fetch_housing_acs("tract:000100", "state:06 county:037")

    def test_share_is_percent_of_households(self):
        r = self.fetch(_row("150", "250"))
        self.assertAlmostEqual(r["share_households_150k_plus"], 40.0)
        self.assertEqual(r["median_household_income"], 100000.0)
        self.assertAlmostEqual(r["mean_household_income"], 150000.0)

    def test_suppressed_bin_gives_no_share_not_zero(self):
        r = self.fetch(_row("-666666666", "250"))
        self.assertNotIn("share_households_150k_plus", r)

    def test_existing_fields_still_read_from_the_same_columns(self):
        r = self.fetch(_row("0", "0"))
        self.assertEqual(r["median_home_value"], 500000.0)
        self.assertEqual(r["median_gross_rent"], 2000.0)
        self.assertEqual(r["median_monthly_housing_cost"], 2500.0)
        self.assertAlmostEqual(r["renter_pct"], 0.4)
        self.assertEqual(r["share_households_150k_plus"], 0.0)


if __name__ == "__main__":
    unittest.main()
