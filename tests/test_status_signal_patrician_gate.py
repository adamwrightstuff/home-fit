"""Patrician post-gate, allow_patrician re-run, and demotion breakdown."""

import unittest

from pillars import status_signal


def _pg(edu, occ, w, lux, rule="patrician_grad_white_collar"):
    return status_signal._patrician_post_gate_passes(edu, occ, w, lux, rule)


class TestPatricianPostGate(unittest.TestCase):
    def test_gate_passes_when_all_meet_floor(self):
        ok, failures = _pg(70.0, 40.0, 95.0, 10.0)
        self.assertTrue(ok)
        self.assertEqual(failures, [])

    def test_gate_fails_on_null_education(self):
        ok, failures = _pg(None, 40.0, 95.0, 10.0)
        self.assertFalse(ok)
        self.assertIn("patrician_gate_education_null", failures)

    def test_gate_fails_on_low_education(self):
        ok, failures = _pg(50.0, 40.0, 95.0, 10.0)
        self.assertFalse(ok)
        self.assertIn("patrician_gate_education_low", failures)

    def test_gate_fails_on_low_occupation(self):
        ok, failures = _pg(70.0, 30.0, 95.0, 10.0)
        self.assertFalse(ok)
        self.assertIn("patrician_gate_occupation_low", failures)

    def test_gate_fails_on_low_wealth(self):
        ok, failures = _pg(70.0, 40.0, 50.0, 10.0)
        self.assertFalse(ok)
        self.assertIn("patrician_gate_wealth_low", failures)

    def test_gate_fails_on_high_luxury(self):
        ok, failures = _pg(70.0, 40.0, 95.0, 60.0)
        self.assertFalse(ok)
        self.assertIn("patrician_gate_luxury_high", failures)

    def test_old_money_allows_lower_education_floor(self):
        ok, failures = _pg(59.0, 40.0, 95.0, 10.0, "patrician_old_money_suburb")
        self.assertTrue(ok)
        self.assertEqual(failures, [])

    def test_non_old_money_still_requires_65_education(self):
        ok, failures = _pg(59.0, 40.0, 95.0, 10.0, "patrician_grad_white_collar")
        self.assertFalse(ok)
        self.assertIn("patrician_gate_education_low", failures)


class TestClassifyArchetypeAllowPatrician(unittest.TestCase):
    def test_allow_false_never_returns_patrician_for_grad_white_collar_inputs(self):
        at, rule = status_signal._classify_archetype(
            area_type="suburban",
            education=80.0,
            wealth=95.0,
            home_cost=50.0,
            luxury_pass1=10.0,
            luxury_detail={},
            median_income=200_000.0,
            wealth_gap=0.05,
            grad_pct_raw=85.0,
            white_collar_mgmt=75.0,
            self_employed_pct_raw=5.0,
            occupation_neutral=70.0,
            provisional=60.0,
            cbsa_median=85_000.0,
            allow_patrician=False,
        )
        self.assertNotEqual(at, "Patrician")
        self.assertEqual(rule, "typical_default")

    def test_allow_true_returns_patrician_for_same_inputs(self):
        at, rule = status_signal._classify_archetype(
            area_type="suburban",
            education=80.0,
            wealth=95.0,
            home_cost=50.0,
            luxury_pass1=10.0,
            luxury_detail={},
            median_income=200_000.0,
            wealth_gap=0.05,
            grad_pct_raw=85.0,
            white_collar_mgmt=75.0,
            self_employed_pct_raw=5.0,
            occupation_neutral=70.0,
            provisional=60.0,
            cbsa_median=85_000.0,
            allow_patrician=True,
        )
        self.assertEqual(at, "Patrician")
        self.assertEqual(rule, "patrician_grad_white_collar")


class TestPatricianDemotionIntegration(unittest.TestCase):
    """Patrician via income shortcut, gate fails on missing education -> demoted."""

    def test_demotion_produces_non_patrician_and_breakdown(self):
        # Patrician via 200k+ uniform shortcut; no education in social -> gate fails (education null).
        housing = {
            "summary": {
                "median_household_income": 201000,
                "mean_household_income": 210000,
                "median_home_value": 500000,
            }
        }
        social_fabric: dict = {}
        economic = {"breakdown": {"white_collar_pct": 45.0}}
        tract = {"cbsa_code": "35620"}

        score, bd = status_signal.compute_status_signal_with_breakdown(
            housing,
            social_fabric,
            economic,
            [],
            tract,
            "NY",
            city="IntegrationTest",
            lat=None,
            lon=None,
        )
        self.assertIsNotNone(score)
        self.assertNotEqual(bd.get("archetype"), "Patrician")
        dr = bd.get("downgrade_reason")
        self.assertIsNotNone(dr)
        self.assertIn("patrician_gate_education_null", dr)
        self.assertEqual(bd.get("original_archetype"), "Patrician")
        self.assertEqual(bd.get("original_archetype_rule"), "shortcut_200k_uniform")
        self.assertIsInstance(bd.get("rerun_inputs"), dict)
        self.assertIn("wealth", bd.get("rerun_inputs") or {})
        self.assertIn("wealth", bd.get("classifier_inputs") or {})


if __name__ == "__main__":
    unittest.main()
