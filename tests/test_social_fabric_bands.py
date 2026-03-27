"""Unit tests for Social Fabric national/regional band calibration (no network)."""

import json
import os
import unittest

from data_sources import social_fabric_bands as sfb


class TestSocialFabricBands(unittest.TestCase):
    def test_interpolate_at_median_maps_to_mid_anchor(self):
        bands = {
            "score_anchors": {"at_knot": [12, 30, 50, 70, 85]},
            "national": {
                "rooted_pct": {"p10": 60, "p25": 72, "p50": 84, "p75": 92, "p90": 97}
            },
        }
        q = bands["national"]["rooted_pct"]
        anchors = tuple(bands["score_anchors"]["at_knot"])
        s = sfb.interpolate_from_quantile_bands(84.0, q, anchors)
        self.assertAlmostEqual(s, 50.0, places=1)

    def test_regional_adjustment_nudges_toward_national_median(self):
        path = os.path.join(os.path.dirname(__file__), "..", "data", "social_fabric_bands.json")
        path = os.path.normpath(path)
        with open(path, "r", encoding="utf-8") as f:
            bands = json.load(f)
        raw = 80.0
        adj = sfb.adjust_rooted_pct_for_regional_bands(raw, "middle_atlantic", bands)
        # Middle Atlantic division median in file is below national median → expect upward nudge.
        self.assertGreater(adj, raw)

    def test_civic_zero_is_low_in_suburban_bands(self):
        path = os.path.join(os.path.dirname(__file__), "..", "data", "social_fabric_bands.json")
        path = os.path.normpath(path)
        with open(path, "r", encoding="utf-8") as f:
            bands = json.load(f)
        s = sfb.score_civic_gathering_from_bands(0, "suburban", bands, proximity=False)
        self.assertLess(s, 25.0)


if __name__ == "__main__":
    unittest.main()
