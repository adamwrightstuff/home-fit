"""Ensure NA tries Google Places before imputed fallback when OSM has no POIs."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch


class TestPlacesOnEmpty(unittest.TestCase):
    @patch("pillars.neighborhood_amenities.maybe_augment_business_data_with_places")
    @patch("data_sources.data_quality.detect_area_type", return_value="suburban")
    @patch("data_sources.census_api.get_population_density", return_value=3000.0)
    @patch("pillars.neighborhood_amenities.osm_api.query_local_businesses")
    def test_places_runs_when_osm_returns_empty_tiers(
        self, mock_osm, _dens, _at, mock_places
    ):
        from pillars import neighborhood_amenities as na_mod

        mock_osm.return_value = {
            "tier1_daily": [],
            "tier2_social": [],
            "tier3_culture": [],
            "tier4_services": [],
        }

        def _places_side_effect(bd, lat, lon, radius_m, include_chains, oc, **kw):
            self.assertEqual(oc, 0.0)
            bd2 = {k: list(v) for k, v in bd.items()}
            bd2["tier1_daily"].append(
                {
                    "name": "Test Cafe",
                    "lat": lat,
                    "lon": lon,
                    "distance_m": 50.0,
                    "type": "cafe",
                    "source": "google_places",
                }
            )
            return bd2, {"used": True, "mapped_added": 1, "reason": "merged"}

        mock_places.side_effect = _places_side_effect

        score, details = na_mod.get_neighborhood_amenities_score(
            34.05,
            -118.25,
            include_chains=True,
            area_type="suburban",
            density=3000.0,
        )
        mock_places.assert_called()
        self.assertGreater(score, 0.0)
        self.assertEqual(details.get("places_fallback", {}).get("used"), True)
        self.assertGreater(len(details.get("business_list") or []), 0)


if __name__ == "__main__":
    unittest.main()
