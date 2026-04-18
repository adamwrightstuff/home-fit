"""Unit tests for Social Fabric Places civic fallback (no live API calls)."""

import os
import unittest
from unittest.mock import patch

from data_sources.data_quality import data_quality_manager
from data_sources.places_social_fabric_client import (
    _classify_civic_node_type,
    maybe_augment_civic_nodes_with_places,
    places_social_fabric_fallback_enabled,
)


class TestSfPlacesClassification(unittest.TestCase):
    def test_library(self):
        self.assertEqual(_classify_civic_node_type(["library", "point_of_interest"]), "library")

    def test_worship(self):
        self.assertEqual(_classify_civic_node_type(["church", "place_of_worship"]), "place_of_worship")

    def test_townhall(self):
        self.assertEqual(_classify_civic_node_type(["city_hall", "establishment"]), "townhall")

    def test_community_center(self):
        self.assertEqual(_classify_civic_node_type(["community_center"]), "community_centre")

    def test_skip_unmapped(self):
        self.assertIsNone(_classify_civic_node_type(["restaurant"]))


class TestSfPlacesAugment(unittest.TestCase):
    @patch.dict(os.environ, {"HOMEFIT_PLACES_SF_FALLBACK_ENABLED": "1", "GOOGLE_PLACES_API_KEY": "x"})
    def test_enabled_with_key(self):
        self.assertTrue(places_social_fabric_fallback_enabled())

    def test_disabled_without_flag(self):
        with patch.dict(
            os.environ,
            {"GOOGLE_PLACES_API_KEY": "x", "HOMEFIT_PLACES_SF_FALLBACK_ENABLED": ""},
            clear=True,
        ):
            self.assertFalse(places_social_fabric_fallback_enabled())

    def test_skips_when_osm_ok(self):
        civic = {"nodes": [{"type": "library"}], "source_status": "ok"}
        out, meta = maybe_augment_civic_nodes_with_places(civic, 40.0, -74.0, 800)
        self.assertEqual(meta["reason"], "osm_not_error")
        self.assertIs(out, civic)

    @patch("data_sources.places_social_fabric_client._search_nearby_civic")
    @patch.dict(os.environ, {"HOMEFIT_PLACES_SF_FALLBACK_ENABLED": "1", "GOOGLE_PLACES_API_KEY": "k"})
    def test_fills_on_osm_error(self, mock_search):
        mock_search.return_value = [
            {
                "id": "pl1",
                "displayName": {"text": "Branch Library"},
                "location": {"latitude": 40.001, "longitude": -74.001},
                "types": ["library"],
            }
        ]
        civic = {
            "nodes": [],
            "source_status": "error",
            "error": {"source": "overpass", "code": "timeout", "message": "x"},
        }
        out, meta = maybe_augment_civic_nodes_with_places(civic, 40.0, -74.0, 800)
        self.assertTrue(meta.get("http_ok"))
        self.assertEqual(out["source_status"], "ok")
        self.assertEqual(len(out["nodes"]), 1)
        self.assertEqual(out["nodes"][0]["type"], "library")
        self.assertEqual(out["nodes"][0]["source"], "google_places")
        self.assertEqual(out["osm_source_status"], "error")


class TestSfCompletenessWithPlaces(unittest.TestCase):
    def test_civic_complete_when_places_ok_after_osm_error(self):
        data = {
            "mobility": {"x": 1},
            "engagement_score": 50.0,
            "source_status": {
                "stability_mobility_acs": "ok",
                "civic_osm": "error",
                "civic_places": "ok",
                "engagement_bmf": "ok",
                "engagement_turnout": "ok",
            },
        }
        c, tier = data_quality_manager._assess_social_fabric_completeness(data, {})
        self.assertGreaterEqual(c, 0.99)
