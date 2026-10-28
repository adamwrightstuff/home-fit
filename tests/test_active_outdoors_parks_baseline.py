import math

import pytest

from pillars import active_outdoors as ao


def _parks(n_within, n_beyond=0):
    return [{"distance_m": 400.0} for _ in range(n_within)] + [{"distance_m": 1800.0} for _ in range(n_beyond)]


def test_baseline_reproduces_knots():
    doc = ao._load_parks_baseline()
    assert doc is not None
    for k, v in zip(doc["knots"], doc["expected_parks"]):
        exp, radius = ao.expected_parks_for_activity(k)
        assert exp == pytest.approx(max(1.0, v), rel=1e-6)
        assert radius == 1000.0


def test_baseline_monotone_and_held_at_ends():
    doc = ao._load_parks_baseline()
    xs = [0.5, 2, 3, 7, 12, 20, 35, 70, 150, 400]
    vals = [ao.expected_parks_for_activity(x)[0] for x in xs]
    assert vals == sorted(vals)
    assert vals[0] == pytest.approx(max(1.0, doc["expected_parks"][0]))
    assert vals[-1] == pytest.approx(doc["expected_parks"][-1])


def test_unavailable_when_factor_missing():
    assert ao.expected_parks_for_activity(None) is None
    assert ao.expected_parks_for_activity(-1) is None


def test_median_place_scores_one_minus_inverse_e():
    exp, _ = ao.expected_parks_for_activity(25)
    n = round(exp)
    score = ao._sat_ratio_v2(n, exp, 22.0)
    assert score == pytest.approx(22.0 * (1 - math.exp(-n / exp)))
    assert score == pytest.approx(13.9, abs=1.5)


def _count_term(parks, area_type, expectations, act):
    # nearest/playground/facility terms are zero with no area, playgrounds or facilities
    return ao._score_daily_urban_outdoors_v2(parks, [], [], area_type, expectations, activity_per_acre=act)


def test_term_ignores_area_type_when_factor_given():
    parks = _parks(10)
    a = _count_term(parks, "exurban", {"expected_parks_within_1km": 1}, 25)
    b = _count_term(parks, "urban_residential", {"expected_parks_within_1km": 90}, 25)
    assert a == pytest.approx(b)


def test_only_parks_inside_baseline_radius_count():
    near = _count_term(_parks(8), "suburban", {}, 25)
    padded = _count_term(_parks(8, n_beyond=30), "suburban", {}, 25)
    assert near == pytest.approx(padded)


def test_falls_back_to_table_without_factor():
    parks = _parks(10)
    table = ao._score_daily_urban_outdoors_v2(parks, [], [], "suburban", {"expected_parks_within_1km": 64})
    assert table == pytest.approx(ao._score_daily_urban_outdoors_v2(
        parks, [], [], "suburban", {"expected_parks_within_1km": 64}, activity_per_acre=None))
    with_factor = _count_term(parks, "suburban", {"expected_parks_within_1km": 64}, 25)
    assert with_factor > table
