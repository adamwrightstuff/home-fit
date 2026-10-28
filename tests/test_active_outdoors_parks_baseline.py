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
        assert radius == 2000.0


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


def test_weighted_count_has_no_hard_edge():
    just_in = ao.weighted_park_count([{"distance_m": 998.0}], 2000.0)
    just_out = ao.weighted_park_count([{"distance_m": 1002.0}], 2000.0)
    assert just_in == pytest.approx(just_out, rel=0.01)


def test_weighted_count_decays_with_distance_and_stops_at_radius():
    near = ao.weighted_park_count([{"distance_m": 300.0}], 2000.0)
    far = ao.weighted_park_count([{"distance_m": 1600.0}], 2000.0)
    assert near == pytest.approx(math.exp(-0.0012 * 300.0))
    assert far < near / 3
    assert ao.weighted_park_count([{"distance_m": 2100.0}], 2000.0) == 0.0


def _term(parks, area_type, expectations, act):
    return ao._score_daily_urban_outdoors_v2(parks, [], [], area_type, expectations, activity_per_acre=act)


def test_term_ignores_area_type_when_factor_given():
    parks = _parks(10)
    a = _term(parks, "exurban", {"expected_parks_within_1km": 1}, 25)
    b = _term(parks, "urban_residential", {"expected_parks_within_1km": 90}, 25)
    assert a == pytest.approx(b)


def test_parks_for_count_supplies_the_wider_list():
    local_only = _parks(3)
    wide = local_only + _parks(0, n_beyond=20)
    narrow = ao._score_daily_urban_outdoors_v2(local_only, [], [], "suburban", {}, activity_per_acre=25)
    wider = ao._score_daily_urban_outdoors_v2(local_only, [], [], "suburban", {}, activity_per_acre=25, parks_for_count=wide)
    assert wider > narrow


def test_falls_back_to_table_without_factor():
    parks = _parks(10)
    exp = {"expected_parks_within_1km": 64}
    table = ao._score_daily_urban_outdoors_v2(parks, [], [], "suburban", exp)
    assert table == pytest.approx(ao._score_daily_urban_outdoors_v2(parks, [], [], "suburban", exp, activity_per_acre=None))
    assert _term(parks, "suburban", exp, 25) > table


def test_playground_baseline_loaded_monotone_and_floored():
    doc = ao._load_parks_baseline()
    assert len(doc["expected_playgrounds"]) == len(doc["knots"])
    vals = [ao.expected_playgrounds_for_activity(x)[0] for x in (1, 5, 10, 25, 100, 300)]
    assert vals == sorted(vals)
    assert min(vals) >= 1.0
    assert ao.expected_playgrounds_for_activity(None) is None


def _play_term(local, wide, act):
    # one park at 300 m keeps the count term equal across calls; compare through the playground difference only
    return ao._score_daily_urban_outdoors_v2(
        _parks(1), local, [], "suburban", {"expected_playgrounds_within_1km": 4},
        activity_per_acre=act, playgrounds_for_count=wide,
    )


def test_playground_term_decays_and_uses_wider_list():
    near = [{"distance_m": 300.0}] * 3
    far = [{"distance_m": 1700.0}] * 3
    assert _play_term(near, near, 25) > _play_term(far, far, 25)
    assert _play_term([], near + far, 25) > _play_term([], near, 25) - 1e-9


def test_playground_term_ignores_area_type_when_factor_given():
    pl = [{"distance_m": 400.0}] * 2
    a = ao._score_daily_urban_outdoors_v2(_parks(1), pl, [], "exurban", {"expected_playgrounds_within_1km": 0}, activity_per_acre=25)
    b = ao._score_daily_urban_outdoors_v2(_parks(1), pl, [], "urban_residential", {"expected_playgrounds_within_1km": 10}, activity_per_acre=25)
    assert a == pytest.approx(b)
