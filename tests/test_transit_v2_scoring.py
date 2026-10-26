"""Public transit: no legacy suburban layer, no commuter floor, commute informational only (design principles v2, P4, P5)."""
import math

import pytest

import pillars.public_transit_access as pt
from data_sources import census_api, data_quality


def _routes(n_sub=0, n_com=0, n_light=0, n_bus=0):
    out = []
    for t, n in ((1, n_sub), (2, n_com), (0, n_light), (3, n_bus)):
        for i in range(n):
            out.append({"route_type": t, "name": f"{t}-{i}", "route_id": f"r{t}{i}", "onestop_id": f"r{t}{i}",
                        "agency": "A", "distance_km": None})
    return out


def _supply(w):
    return 0.0 if w <= 0 else 100.0 * min(1.0, math.log(1.0 + w) / math.log(121.0))


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    monkeypatch.setattr(pt, "get_nearby_transit_stops", lambda *a, **k: None)
    monkeypatch.setattr(pt, "_nearest_heavy_rail_km", lambda *a, **k: float("inf"))
    monkeypatch.setattr(data_quality, "detect_area_type", lambda *a, **k: "exurban")
    monkeypatch.setattr(data_quality, "assess_pillar_data_quality",
                        lambda *a, **k: {"confidence": 70, "quality_tier": "good", "completeness": 0.7})
    monkeypatch.setattr(census_api, "get_commute_time", lambda *a, **k: 39.0)
    monkeypatch.setattr(census_api, "get_commute_time_stable", lambda *a, **k: 39.0)


def _score(routes, area_type="exurban"):
    import unittest.mock as m
    with m.patch.object(pt, "_get_nearby_routes", lambda *a, **k: routes):
        return pt.get_public_transit_score(41.0, -73.7, area_type=area_type, density=1200.0)


def test_bus_only_exurb_is_the_documented_supply_formula_not_a_legacy_lift():
    score, bd = _score(_routes(n_bus=5))
    assert score == pytest.approx(_supply(pt.W_BUS * 5), abs=0.1)  # about 31 on the supply formula, no legacy lift


def test_commuter_rail_town_has_no_floor():
    score, bd = _score(_routes(n_com=2, n_bus=2))
    assert score == pytest.approx(_supply(2 * pt.W_COMMUTER_RAIL + 2 * pt.W_BUS), abs=0.1)


def test_commute_minutes_do_not_change_the_score(monkeypatch):
    base, _ = _score(_routes(n_com=1, n_bus=3))
    monkeypatch.setattr(census_api, "get_commute_time", lambda *a, **k: 18.0)
    monkeypatch.setattr(census_api, "get_commute_time_stable", lambda *a, **k: 18.0)
    fast, bd = _score(_routes(n_com=1, n_bus=3))
    assert fast == base
    assert bd["details"]["commute_time"]["weight"] == 0.0
    assert "commute_bonus" not in bd["breakdown"]


def test_commute_is_still_reported_for_the_frontend_fallback():
    _, bd = _score(_routes(n_bus=2))
    assert bd["breakdown"]["commute_time"] > 0
    assert bd["summary"]["mean_commute_minutes"] == 39.0


def test_area_type_is_echoed():
    _, bd = _score(_routes(n_bus=1), area_type="rural")
    assert bd["area_classification"]["area_type"] == "rural"


def test_subway_outranks_the_same_number_of_buses():
    sub, _ = _score(_routes(n_sub=3))
    bus, _ = _score(_routes(n_bus=3))
    assert sub > bus


def test_documented_mode_weights():
    assert (pt.W_BUS, pt.W_LIGHT_RAIL, pt.W_COMMUTER_RAIL, pt.W_SUBWAY) == (0.7, 2.0, 3.0, 3.0)


def test_commuter_rail_town_scores_well_above_bus_only_town_with_same_route_count():
    town, _ = _score(_routes(n_com=2, n_bus=2))
    bus_only, _ = _score(_routes(n_bus=4))
    assert town > bus_only + 15
