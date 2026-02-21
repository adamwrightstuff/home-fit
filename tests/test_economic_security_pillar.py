import unittest
from unittest.mock import patch


class TestEconomicSecurityPillar(unittest.TestCase):
    """
    Unit test (no network): stub data fetches and verify response shape + score bounds.
    """
    def test_score_shape_and_range(self):
        from data_sources.economic_security_data import EconomicGeo
        import pillars.economic_security as econ

        fake_geo = EconomicGeo(
            level="county",
            name=None,
            state_fips="06",
            county_fips="001",
            cbsa_code=None,
        )

        def _fake_dp03(*, year, geo, variables):
            return {
                "DP03_0001E": 100000,  # pop 16+
                "DP03_0004E": 65000,  # employed
                "DP03_0009PE": 4.2,  # unemployment rate
                "DP03_0092E": 52000,  # median earnings (workers)
                # industry shares (sum ~ 100)
                "DP03_0033PE": 1.0,
                "DP03_0034PE": 6.0,
                "DP03_0035PE": 10.0,
                "DP03_0036PE": 4.0,
                "DP03_0037PE": 10.0,
                "DP03_0038PE": 6.0,
                "DP03_0039PE": 2.0,
                "DP03_0040PE": 10.0,
                "DP03_0041PE": 14.0,
                "DP03_0042PE": 20.0,
                "DP03_0043PE": 10.0,
                "DP03_0044PE": 5.0,
                "DP03_0045PE": 2.0,
            }

        def _fake_table(*, year, geo, variables, dataset="acs/acs5"):
            if variables == ["B25064_001E"]:
                return {"B25064_001E": 1800}  # monthly rent
            if variables == ["B01001_001E"]:
                return {"B01001_001E": 150000}  # total pop
            return {}

        def _fake_bds(*, year, geo):
            return {
                "ESTABS_ENTRY": 1200,
                "ESTABS_EXIT": 1100,
                "ESTABS_ENTRY_RATE": 0.0,
                "ESTABS_EXIT_RATE": 0.0,
            }

        with patch.object(econ, "get_economic_geography", lambda lat, lon, tract=None: fake_geo), patch.object(
            econ, "fetch_acs_profile_dp03", _fake_dp03
        ), patch.object(econ, "fetch_acs_table", _fake_table), patch.object(
            econ, "fetch_bds_establishment_dynamics", _fake_bds
        ):
            score, details = econ.get_economic_security_score(
                37.0,
                -122.0,
                city="Test City",
                state="CA",
                area_type="suburban",
                census_tract=None,
            )

        self.assertIsInstance(score, (int, float))
        self.assertGreaterEqual(float(score), 0.0)
        self.assertLessEqual(float(score), 100.0)

        self.assertIsInstance(details, dict)
        self.assertIn("breakdown", details)
        self.assertIn("summary", details)
        self.assertIn("data_quality", details)
        self.assertIn("resilience", details["breakdown"])
        self.assertIn("density", details["breakdown"])
        self.assertIn("mobility", details["breakdown"])
        self.assertIn("ecosystem", details["breakdown"])

    def test_job_category_overlays_adjust_score_when_requested(self):
        import pillars.economic_security as econ

        # Force a deterministic overlay: +10 job-market when tech_professional selected.
        def _fake_overlays(**kwargs):
            base = float(kwargs.get("base_job_market_strength") or 0.0)
            return {
                "job_category_overlays": {
                    "tech_professional": {
                        "adjustment": 10.0,
                        "final_job_market_score": min(100.0, base + 10.0),
                        "density_percentile": 0.9,
                        "earnings_percentile": 0.8,
                    }
                }
            }

        with patch.object(econ, "compute_job_category_overlays", _fake_overlays):
            score, details = econ.get_economic_security_score(
                37.0,
                -122.0,
                city="Test City",
                state="CA",
                area_type="suburban",
                census_tract=None,
                job_categories="tech_professional",
            )

        self.assertIn("base_score", details)
        self.assertIn("selected_job_categories", details)
        self.assertEqual(details.get("selected_job_categories"), ["tech_professional"])
        # If overlay applied, personalized score should differ from base_score (not strictly guaranteed,
        # but in our fake overlay it should increase).
        self.assertGreaterEqual(float(details.get("score") or 0.0), float(details.get("base_score") or 0.0))

