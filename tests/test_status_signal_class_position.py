"""Status signal class-position score (DPv2 option C): the number follows the class label."""

import unittest

from pillars import status_signal as ss

BASE = {
    "class_national": {"median_household_income": 75149.0, "poverty_guideline_3p": 23030},
    "class_cuts": {"m": {"income_p80": 120000.0, "income_p90": 150000.0, "home_value_p90": 800000.0}},
}
KEYS = ["m"]


def score(archetype, income, **extra):
    return ss.class_position_score(archetype, {"median_household_income": income, **extra}, KEYS, BASE)


class TestClassPosition(unittest.TestCase):
    def test_band_edges(self):
        self.assertEqual(score("Struggling", 0.01), 0.0)
        self.assertEqual(score("Working Class", 23030), 20.0)
        self.assertEqual(score("Middle Class", 75149 * 2 / 3), 40.0)
        self.assertEqual(score("Affluent", 120000), 60.0)
        self.assertEqual(score("Elite", 150000), 80.0)
        self.assertEqual(score("Elite", 10_000_000), 100.0)  # clipped at the topcode

    def test_affluent_over_p90_ties_at_band_top(self):
        self.assertEqual(score("Affluent", 150000), 80.0)
        self.assertEqual(score("Affluent", 400000), 80.0)

    def test_elite_ceiling_is_the_acs_topcode(self):
        self.assertEqual(score("Elite", 250001), 100.0)
        self.assertLess(score("Elite", 200000), 100.0)

    def test_no_income_gives_no_class_and_no_score(self):
        sc, bd = ss.compute_status_signal_with_breakdown(
            {"summary": {"median_household_income": None, "median_home_value": 500000, "median_monthly_housing_cost": 2000}},
            None, {}, [], None, None)
        self.assertIsNone(sc)
        self.assertIsNone(bd["archetype"])
        self.assertIsNone(bd["status_label"])

    def test_higher_class_never_scores_lower(self):
        self.assertLessEqual(score("Working Class", 10**9), score("Middle Class", 1))
        self.assertLessEqual(score("Middle Class", 10**9), score("Affluent", 1))
        self.assertLessEqual(score("Affluent", 10**9), score("Elite", 1))

    def test_burden_demoted_place_sits_at_top_of_lower_class(self):
        self.assertEqual(score("Struggling", 60000), 20.0)
        self.assertEqual(score("Working Class", 74000), round(20 + 20 * (74000 - 23030) / (75149 - 23030), 1))

    def test_missing_inputs_give_none_not_neutral(self):
        self.assertIsNone(score("Middle Class", None))
        self.assertIsNone(score(None, 90000))
        self.assertIsNone(ss.class_position_score("Middle Class", {"median_household_income": 90000}, ["zz"], BASE))

    def test_no_education_or_occupation_input(self):
        a = score("Affluent", 130000)
        b = score("Affluent", 130000, education_attainment={"grad_pct": 99}, white_collar_pct=99)
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
