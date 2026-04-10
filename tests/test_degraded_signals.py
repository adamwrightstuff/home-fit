"""Tests for main._collect_degraded_signals (Social Fabric civic OSM error, etc.)."""

import unittest

import main


class TestCollectDegradedSignals(unittest.TestCase):
    def test_civic_osm_error_is_degraded(self):
        sig = main._collect_degraded_signals({"source_status": {"civic_osm": "error"}})
        self.assertTrue(sig["degraded"])
        self.assertIn("civic_osm_unavailable", sig["warnings"])

    def test_civic_osm_ok_not_degraded(self):
        sig = main._collect_degraded_signals({"source_status": {"civic_osm": "ok"}})
        self.assertFalse(sig["degraded"])

    def test_civic_osm_empty_not_degraded(self):
        sig = main._collect_degraded_signals({"source_status": {"civic_osm": "empty"}})
        self.assertFalse(sig["degraded"])

    def test_stability_mobility_acs_error_is_degraded(self):
        sig = main._collect_degraded_signals({"source_status": {"stability_mobility_acs": "error"}})
        self.assertTrue(sig["degraded"])
        self.assertIn("stability_acs_unavailable", sig["warnings"])

    def test_stability_mobility_acs_ok_not_degraded(self):
        sig = main._collect_degraded_signals({"source_status": {"stability_mobility_acs": "ok"}})
        self.assertFalse(sig["degraded"])

    def test_built_beauty_informational_height_diversity_not_degraded(self):
        sig = main._collect_degraded_signals(
            {"details": {"architectural_analysis": {"data_warning": "suspiciously_low_height_diversity"}}}
        )
        self.assertFalse(sig["degraded"])
        self.assertIn("suspiciously_low_height_diversity", sig["warnings"])

    def test_built_beauty_informational_low_coverage_not_degraded(self):
        sig = main._collect_degraded_signals(
            {"details": {"architectural_analysis": {"data_warning": "low_building_coverage"}}}
        )
        self.assertFalse(sig["degraded"])
        self.assertIn("low_building_coverage", sig["warnings"])

    def test_built_beauty_api_error_is_degraded(self):
        sig = main._collect_degraded_signals(
            {"details": {"architectural_analysis": {"data_warning": "api_error"}}}
        )
        self.assertTrue(sig["degraded"])
        self.assertIn("api_error", sig["warnings"])

    def test_built_beauty_informational_plus_api_error_still_degraded(self):
        sig = main._collect_degraded_signals(
            {
                "details": {
                    "architectural_analysis": {
                        "data_warning": "suspiciously_low_height_diversity",
                        "nested": {"data_warning": "api_error"},
                    }
                }
            }
        )
        self.assertTrue(sig["degraded"])


if __name__ == "__main__":
    unittest.main()
