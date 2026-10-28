import math

import pytest

from pillars import active_outdoors as ao


def _trails(total, near):
    return [{"distance_m": 3000.0}] * near + [{"distance_m": 9000.0}] * (total - near)


def test_scale_file_loads_with_catalog_medians():
    scale = ao._load_trails_scale()
    assert scale is not None
    assert scale["expected_trails_15km"] > 0 and scale["expected_trails_5km"] > 0
    assert scale["budget_trails_15km"] + scale["budget_trails_5km"] + scale["budget_camping"] == 50.0


def test_same_inputs_score_the_same_for_every_type_and_flag():
    t, c = _trails(30, 6), [{"distance_m": 8000.0}]
    scores = {
        ao._score_wild_adventure_v2(t, c, a, is_mountain_town=m)
        for a in ("urban_residential", "suburban", "exurban", "rural") for m in (False, True)
    }
    assert len(scores) == 1


def test_median_place_scores_the_budgets_times_one_minus_inverse_e():
    scale = ao._load_trails_scale()
    t = _trails(int(scale["expected_trails_15km"]), int(scale["expected_trails_5km"]))
    got = ao._score_wild_adventure_v2(t, [], "suburban")
    want = 25.0 * (1 - math.exp(-int(scale["expected_trails_15km"]) / scale["expected_trails_15km"])) + \
        15.0 * (1 - math.exp(-int(scale["expected_trails_5km"]) / scale["expected_trails_5km"]))
    assert got == pytest.approx(want, abs=0.5)


def test_monotone_in_trails_and_no_cliff_at_five_km():
    base = ao._score_wild_adventure_v2(_trails(20, 2), [], "suburban")
    more = ao._score_wild_adventure_v2(_trails(40, 2), [], "suburban")
    assert more > base
    just_in = ao._score_wild_adventure_v2([{"distance_m": 4990.0}] * 10, [], "suburban")
    just_out = ao._score_wild_adventure_v2([{"distance_m": 5010.0}] * 10, [], "suburban")
    assert just_in > just_out  # known hard edge at 5 km, bounded to the 15-point near term


def test_camping_full_inside_limit_then_decays():
    scale = ao._load_trails_scale()
    inside = ao._score_wild_adventure_v2([], [{"distance_m": scale["camping_full_within_m"] - 1}], "rural")
    outside = ao._score_wild_adventure_v2([], [{"distance_m": scale["camping_full_within_m"] + 20000}], "rural")
    assert inside == pytest.approx(scale["budget_camping"])
    assert 0 < outside < inside


def test_bounded_zero_to_fifty():
    assert ao._score_wild_adventure_v2([], [], "rural") == 0.0
    assert ao._score_wild_adventure_v2(_trails(2000, 500), [{"distance_m": 100.0}], "rural") <= 50.0
