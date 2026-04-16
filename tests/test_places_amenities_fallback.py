"""Unit tests for Google Places fallback mapping and merge (no live API calls)."""

import os
import unittest
from unittest.mock import patch

from data_sources.places_osm_mapping import (
    included_type_batches_for_nearby_search,
    resolve_tier_and_type_from_google_types,
)
from data_sources.places_fallback_client import maybe_augment_business_data_with_places, place_json_to_business


class TestPlacesOsmMapping(unittest.TestCase):
    def test_five_disjoint_batches_cover_all_types(self):
        batches = included_type_batches_for_nearby_search()
        self.assertEqual(len(batches), 5)
        all_types = []
        for b in batches:
            all_types.extend(b)
        self.assertEqual(len(all_types), len(set(all_types)))

    def test_resolves_cafe(self):
        self.assertEqual(
            resolve_tier_and_type_from_google_types(["restaurant", "cafe", "food"]),
            ("tier1_daily", "cafe"),
        )

    def test_priority_prefers_grocery_over_restaurant(self):
        self.assertEqual(
            resolve_tier_and_type_from_google_types(["restaurant", "supermarket"]),
            ("tier1_daily", "grocery"),
        )


MOCK_CAFE = {
    "id": "abc123",
    "name": "places/abc123",
    "displayName": {"text": "Joe's Indie Cafe", "languageCode": "en"},
    "location": {"latitude": 40.7001, "longitude": -74.0001},
    "types": ["cafe", "establishment"],
}


class TestPlacesMerge(unittest.TestCase):
    def test_skips_when_completeness_high(self):
        osm = {
            "tier1_daily": [],
            "tier2_social": [],
            "tier3_culture": [],
            "tier4_services": [],
        }
        merged, meta = maybe_augment_business_data_with_places(osm, 40.7, -74.0, 1500.0, True, 0.95)
        self.assertEqual(merged, osm)
        self.assertEqual(meta["reason"], "completeness_above_threshold")
        self.assertFalse(meta["triggered"])

    @patch.dict(os.environ, {"HOMEFIT_PLACES_FALLBACK_ENABLED": "1", "GOOGLE_PLACES_API_KEY": "test"}, clear=False)
    @patch("data_sources.places_fallback_client._single_search_nearby")
    def test_merges_when_low_completeness_rural_one_call(self, mock_nearby):
        mock_nearby.return_value = [MOCK_CAFE]
        osm = {
            "tier1_daily": [],
            "tier2_social": [],
            "tier3_culture": [],
            "tier4_services": [],
        }
        merged, meta = maybe_augment_business_data_with_places(
            osm, 40.7, -74.0, 1500.0, True, 0.2, area_type="rural", density=500.0
        )
        self.assertTrue(meta["triggered"])
        self.assertTrue(meta["used"])
        self.assertEqual(meta["places_calls_made"], 1)
        self.assertEqual(meta["places_stop_reason"], "cap_reached")
        self.assertEqual(len(merged["tier1_daily"]), 1)
        self.assertEqual(merged["tier1_daily"][0]["type"], "cafe")
        self.assertEqual(merged["tier1_daily"][0]["source"], "google_places")
        mock_nearby.assert_called_once()

    @patch.dict(os.environ, {"HOMEFIT_PLACES_FALLBACK_ENABLED": "1", "GOOGLE_PLACES_API_KEY": "test"}, clear=False)
    @patch("data_sources.places_fallback_client._single_search_nearby")
    def test_suburban_second_call_when_still_below_threshold(self, mock_nearby):
        """After broad call, completeness still low → tier3+4 second call."""
        mock_nearby.side_effect = [
            [MOCK_CAFE],
            [
                {
                    "id": "m1",
                    "displayName": {"text": "Tiny Museum", "languageCode": "en"},
                    "location": {"latitude": 40.7002, "longitude": -74.0002},
                    "types": ["museum"],
                }
            ],
        ]
        osm = {
            "tier1_daily": [],
            "tier2_social": [],
            "tier3_culture": [],
            "tier4_services": [],
        }
        merged, meta = maybe_augment_business_data_with_places(
            osm, 40.7, -74.0, 1500.0, True, 0.15, area_type="suburban", density=3000.0
        )
        self.assertEqual(mock_nearby.call_count, 2)
        self.assertTrue(meta["places_suburban_second_call"])

    @patch.dict(os.environ, {"HOMEFIT_PLACES_FALLBACK_ENABLED": "1", "GOOGLE_PLACES_API_KEY": "test"}, clear=False)
    @patch("data_sources.places_fallback_client._single_search_nearby")
    def test_urban_core_runs_four_tier_calls_when_below_threshold(self, mock_nearby):
        p1 = dict(MOCK_CAFE)
        p2 = {
            "id": "r1",
            "displayName": {"text": "Rest", "languageCode": "en"},
            "location": {"latitude": 40.71, "longitude": -74.01},
            "types": ["restaurant"],
        }
        p3 = {
            "id": "m1",
            "displayName": {"text": "Mus", "languageCode": "en"},
            "location": {"latitude": 40.72, "longitude": -74.02},
            "types": ["museum"],
        }
        p4 = {
            "id": "g1",
            "displayName": {"text": "Gym", "languageCode": "en"},
            "location": {"latitude": 40.73, "longitude": -74.03},
            "types": ["gym"],
        }
        mock_nearby.side_effect = [[p1], [p2], [p3], [p4]]
        osm = {
            "tier1_daily": [],
            "tier2_social": [],
            "tier3_culture": [],
            "tier4_services": [],
        }
        merged, meta = maybe_augment_business_data_with_places(
            osm, 40.7, -74.0, 1500.0, True, 0.15, area_type="urban_core", density=12000.0
        )
        self.assertEqual(mock_nearby.call_count, 4)
        self.assertEqual(meta["places_calls_made"], 4)
        self.assertEqual(meta["places_stop_reason"], "cap_reached")
        self.assertTrue(meta["used"])

    def test_place_json_skips_chain_when_requested(self):
        place = {
            "displayName": {"text": "Starbucks"},
            "location": {"latitude": 40.7, "longitude": -74.0},
            "types": ["cafe"],
        }
        self.assertIsNone(place_json_to_business(place, 40.7, -74.0, include_chains=False))


if __name__ == "__main__":
    unittest.main()
