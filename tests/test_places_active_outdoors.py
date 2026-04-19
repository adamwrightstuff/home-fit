"""Unit tests for Active Outdoors Places augmentation (no live API calls)."""

import os
import unittest
from unittest.mock import patch

from data_sources.places_active_outdoors_client import (
    _classify_local,
    _classify_regional,
    _merge_local_places,
    _merge_regional_places,
    maybe_augment_active_outdoors_with_places,
    places_ao_fallback_enabled,
)


class TestAoPlacesClassification(unittest.TestCase):
    def test_local_prefers_playground_when_both_present(self):
        self.assertEqual(
            _classify_local(["park", "playground", "point_of_interest"]),
            "playground",
        )

    def test_local_marina_skipped(self):
        self.assertIsNone(_classify_local(["marina", "park"]))

    def test_regional_beach_before_camp(self):
        self.assertEqual(_classify_regional(["beach", "campground"]), ("swim", "beach"))

    def test_regional_rv_park(self):
        self.assertEqual(_classify_regional(["rv_park", "lodging"]), ("camp", "rv_park"))


class TestAoPlacesMerge(unittest.TestCase):
    def test_merge_local_skips_near_osm_park(self):
        parks = [{"name": "OSM", "lat": 40.0, "lon": -74.0, "distance_m": 100, "area_sqm": 1000}]
        playgrounds: list = []
        seen = set()
        places = [
            {
                "id": "p1",
                "displayName": {"text": "Tiny Park"},
                "location": {"latitude": 40.00005, "longitude": -74.00005},
                "types": ["park"],
            }
        ]
        # ~7m from OSM point — within default 85m dedupe
        added = _merge_local_places(places, 40.0, -74.0, parks, playgrounds, 85.0, seen)
        self.assertEqual(added, 0)
        self.assertEqual(len(parks), 1)

    def test_merge_regional_adds_beach(self):
        swimming: list = []
        camping: list = []
        seen = set()
        places = [
            {
                "id": "b1",
                "displayName": {"text": "Sandy Beach"},
                "location": {"latitude": 40.5, "longitude": -73.5},
                "types": ["beach", "establishment"],
            }
        ]
        sa, ca = _merge_regional_places(places, 40.0, -74.0, swimming, camping, seen)
        self.assertEqual(sa, 1)
        self.assertEqual(ca, 0)
        self.assertEqual(swimming[0]["type"], "beach")
        self.assertEqual(swimming[0]["source"], "google_places")


class TestAoPlacesGate(unittest.TestCase):
    @patch.dict(os.environ, {"HOMEFIT_PLACES_AO_FALLBACK_ENABLED": "1", "GOOGLE_PLACES_API_KEY": "x"})
    def test_enabled_with_key(self):
        self.assertTrue(places_ao_fallback_enabled())

    @patch.dict(
        os.environ,
        {
            "HOMEFIT_PLACES_FALLBACK_ENABLED": "1",
            "HOMEFIT_PLACES_AO_FALLBACK_ENABLED": "",
            "GOOGLE_PLACES_API_KEY": "x",
        },
    )
    def test_enabled_with_master_flag_only(self):
        self.assertTrue(places_ao_fallback_enabled())

    def test_disabled_without_flag(self):
        with patch.dict(os.environ, {"GOOGLE_PLACES_API_KEY": "x"}, clear=False):
            if "HOMEFIT_PLACES_AO_FALLBACK_ENABLED" in os.environ:
                del os.environ["HOMEFIT_PLACES_AO_FALLBACK_ENABLED"]
        # May still be set from other tests — patch fully
        with patch.dict(
            os.environ,
            {
                "GOOGLE_PLACES_API_KEY": "x",
                "HOMEFIT_PLACES_AO_FALLBACK_ENABLED": "",
                "HOMEFIT_PLACES_FALLBACK_ENABLED": "",
            },
            clear=True,
        ):
            self.assertFalse(places_ao_fallback_enabled())

    @patch.dict(os.environ, {"HOMEFIT_PLACES_AO_FALLBACK_ENABLED": "1", "GOOGLE_PLACES_API_KEY": "x"})
    def test_skips_when_osm_counts_high(self):
        parks = [{"lat": 40.0, "lon": -74.0}] * 3
        playgrounds = []
        swimming = [
            {"type": "lake", "distance_m": 1000},
            {"type": "coastline", "distance_m": 2000},
        ]
        camping = [{"type": "campsite", "distance_m": 5000}]
        meta = maybe_augment_active_outdoors_with_places(
            40.0,
            -74.0,
            local_radius_m=800,
            regional_radius_m=15000,
            parks=parks,
            playgrounds=playgrounds,
            swimming=swimming,
            camping=camping,
        )
        self.assertEqual(meta["reason"], "osm_counts_sufficient")
        self.assertFalse(meta["triggered"])
