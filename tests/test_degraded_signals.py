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


if __name__ == "__main__":
    unittest.main()
