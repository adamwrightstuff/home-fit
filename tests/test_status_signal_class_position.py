"""Status signal class-position score (DPv2 option C): the number follows the class label."""

import unittest

from pillars import status_signal as ss

BASE = {
    "class_national": {"median_household_income": 75149.0, "poverty_guideline_3p": 23030,
                       "affluent_household_share_150k_cut": 37.55},
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


class TestHouseholdRouteToAffluent(unittest.TestCase):
    """Round 2 (docs/STATUS_SIGNAL_STEP2_TEST.md): a Middle Class place with many households at $150,000 or more is Affluent."""

    @staticmethod
    def cls(income, share=None, home=500000, monthly=2000):
        s = {"median_household_income": income, "median_home_value": home, "median_monthly_housing_cost": monthly}
        if share is not None:
            s["share_households_150k_plus"] = share
        return ss._classify_class(s, KEYS, BASE)

    def test_share_at_or_above_cut_promotes_middle_to_affluent(self):
        self.assertEqual(self.cls(100000, 40.0), ("Affluent", "class_affluent_households"))
        self.assertEqual(self.cls(100000, 37.55), ("Affluent", "class_affluent_households"))

    def test_share_below_cut_stays_middle(self):
        self.assertEqual(self.cls(100000, 30.0), ("Middle Class", "class_middle"))

    def test_missing_share_changes_nothing(self):
        self.assertEqual(self.cls(100000), ("Middle Class", "class_middle"))

    def test_burden_demoted_place_is_never_lifted(self):
        # income 60,000 with 70% housing share is demoted below Middle Class; a high share cannot lift it back
        self.assertEqual(self.cls(60000, 50.0, monthly=3500)[0], "Struggling")
        self.assertEqual(self.cls(60000, 50.0, monthly=1600)[0], "Working Class")

    def test_income_route_and_elite_are_unchanged(self):
        self.assertEqual(self.cls(130000, 10.0), ("Affluent", "class_affluent"))
        self.assertEqual(self.cls(200000, 10.0, home=900000), ("Elite", "class_elite"))

    def test_household_route_places_sit_at_the_affluent_band_floor(self):
        # Known limit: income is under the p80 line, so the position inside the Affluent band clips to 0 and they tie at 60.
        self.assertEqual(ss.class_position_score("Affluent", {"median_household_income": 100000}, KEYS, BASE), 60.0)
        self.assertEqual(ss.class_position_score("Affluent", {"median_household_income": 95000}, KEYS, BASE), 60.0)

    def test_insight_text_does_not_claim_the_top_fifth(self):
        t = ss._get_status_insight("Affluent", "class_affluent_households")
        self.assertIn("$150,000", t)
        self.assertNotEqual(t, ss._get_status_insight("Affluent", "class_affluent"))


if __name__ == "__main__":
    unittest.main()
