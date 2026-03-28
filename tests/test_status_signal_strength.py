"""Status Signal signal_strength bands (match frontend statusSignalStrength)."""

import unittest

from pillars import status_signal


class TestSignalStrengthBand(unittest.TestCase):
    def test_bands(self):
        self.assertEqual(status_signal._signal_strength_band(0), ("faint", "Faint signal"))
        self.assertEqual(status_signal._signal_strength_band(24.9), ("faint", "Faint signal"))
        self.assertEqual(status_signal._signal_strength_band(25), ("moderate", "Moderate signal"))
        self.assertEqual(status_signal._signal_strength_band(49.9), ("moderate", "Moderate signal"))
        self.assertEqual(status_signal._signal_strength_band(50), ("strong", "Strong signal"))
        self.assertEqual(status_signal._signal_strength_band(74.9), ("strong", "Strong signal"))
        self.assertEqual(status_signal._signal_strength_band(75), ("dominant", "Dominant signal"))
        self.assertEqual(status_signal._signal_strength_band(100), ("dominant", "Dominant signal"))


if __name__ == "__main__":
    unittest.main()
