"""Luxury OSM tag classification for Status Signal."""

import unittest

from data_sources.status_signal_luxury_osm import classify_luxury_osm_tags


class TestClassifyLuxuryOsmTags(unittest.TestCase):
    def test_wealth_lawyer_not_estate_agent(self):
        self.assertIn("wealth_offices", classify_luxury_osm_tags({"office": "lawyer"}))
        self.assertNotIn("wealth_offices", classify_luxury_osm_tags({"office": "estate_agent"}))

    def test_private_recreation_requires_restricted_access(self):
        self.assertIn(
            "private_recreation",
            classify_luxury_osm_tags({"leisure": "swimming_pool", "access": "private"}),
        )
        self.assertNotIn(
            "private_recreation",
            classify_luxury_osm_tags({"leisure": "swimming_pool", "access": "yes"}),
        )
        self.assertNotIn(
            "private_recreation",
            classify_luxury_osm_tags({"leisure": "swimming_pool"}),
        )
        self.assertIn(
            "private_recreation",
            classify_luxury_osm_tags({"sport": "tennis", "access": "members"}),
        )


if __name__ == "__main__":
    unittest.main()
