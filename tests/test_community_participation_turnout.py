"""Community participation turnout blend (no external APIs)."""

import unittest
from unittest.mock import patch

from data_sources import community_participation


class TestTurnoutStateExcludedFromBlend(unittest.TestCase):
    @patch.object(community_participation.irs_bmf, "get_civic_orgs_per_1k")
    @patch.object(community_participation, "get_volunteering_score")
    @patch.object(community_participation, "get_precinct_or_voter_turnout")
    def test_state_turnout_rate_only_not_in_blend(
        self, mock_turnout, mock_vol, mock_bmf
    ):
        mock_bmf.side_effect = [
            (2.0, {"mean": 1.0, "std": 1.0}),
            (2.0, {"mean": 1.0, "std": 1.0}),
        ]
        mock_vol.return_value = (50.0, "sca_zip")
        mock_turnout.return_value = ((60.0, {"mean": 0.5, "std": 0.1}, 0.55), "state_turnout")

        tract = {"geoid": "36001000100", "state_fips": "36"}
        score, diag = community_participation.compute_participation_score(
            40.0, -74.0, tract, "suburban", "NE", zip_code="10708"
        )
        self.assertIsNone(diag.get("turnout_z"))
        self.assertEqual(diag.get("turnout_rate"), 0.55)
        self.assertEqual(diag.get("turnout_source"), "state_turnout")
        self.assertFalse(diag.get("turnout_in_engagement_blend"))
        self.assertEqual(diag.get("mix"), "no_turn_60_40_bmf_vol")
        self.assertIsNotNone(score)

    @patch.object(community_participation.irs_bmf, "get_civic_orgs_per_1k")
    @patch.object(community_participation, "get_volunteering_score")
    @patch.object(community_participation, "get_precinct_or_voter_turnout")
    def test_tract_turnout_in_blend(self, mock_turnout, mock_vol, mock_bmf):
        mock_bmf.side_effect = [
            (2.0, {"mean": 1.0, "std": 1.0}),
            (2.0, {"mean": 1.0, "std": 1.0}),
        ]
        mock_vol.return_value = (50.0, "sca_zip")
        mock_turnout.return_value = ((60.0, {"mean": 0.5, "std": 0.1}, 0.55), "tract_turnout")

        tract = {"geoid": "36001000100", "state_fips": "36"}
        score, diag = community_participation.compute_participation_score(
            40.0, -74.0, tract, "suburban", "NE", zip_code="10708"
        )
        self.assertIsNotNone(diag.get("turnout_z"))
        self.assertTrue(diag.get("turnout_in_engagement_blend"))
        self.assertEqual(diag.get("mix"), "full")
        self.assertIsNotNone(score)


if __name__ == "__main__":
    unittest.main()
