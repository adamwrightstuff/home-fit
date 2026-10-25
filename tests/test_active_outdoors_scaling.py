"""Active outdoors: budgets scaled to 100, and a failed Overpass read is no data, not zero."""
import pytest

import pillars.active_outdoors as ao


def test_all_three_components_scale_by_100_over_110():
    score, missing = ao.scale_active_outdoors({"daily_urban_outdoors": 35.0, "wild_adventure": 50.0, "waterfront_lifestyle": 25.0})
    assert missing == [] and score == pytest.approx(100.0)  # only a perfect place reaches 100
    score, _ = ao.scale_active_outdoors({"daily_urban_outdoors": 30.0, "wild_adventure": 50.0, "waterfront_lifestyle": 22.0})
    assert score == pytest.approx(102.0 * 100 / 110)  # the old cap would have shown 100


def test_missing_component_rescales_from_those_that_read():
    score, missing = ao.scale_active_outdoors({"daily_urban_outdoors": 30.0, "wild_adventure": None, "waterfront_lifestyle": 15.0})
    assert missing == ["wild_adventure"] and score == pytest.approx(45.0 / 60.0 * 100.0)


def test_fewer_than_two_components_is_no_score():
    with pytest.raises(RuntimeError):
        ao.scale_active_outdoors({"daily_urban_outdoors": 30.0, "wild_adventure": None, "waterfront_lifestyle": None})


@pytest.mark.parametrize("outcome,area,empty_flag,expected", [
    ("overpass_error", "suburban", False, True), ("overpass_timeout", "rural", False, True),
    ("overpass_ok", "suburban", True, False), ("overpass_empty", "suburban", False, False),
    ("overpass_empty", "suburban", True, True), ("overpass_empty", "rural", True, False), (None, "suburban", True, False),
])
def test_overpass_read_failure_rules(outcome, area, empty_flag, expected):
    assert ao.overpass_read_failed(outcome, area, empty_is_failure=empty_flag) is expected


def _run(monkeypatch, trail_outcome):
    ok = {"_overpass_outcome": "overpass_ok"}
    parks = {**ok, "parks": [{"name": f"p{i}", "lat": 40.0, "lon": -74.0, "distance_m": 300 + i * 50, "area_sqm": 20000} for i in range(10)],
             "playgrounds": [], "recreational_facilities": []}
    trails = {"_overpass_outcome": trail_outcome, "hiking": [] if trail_outcome != "overpass_ok" else
              [{"name": f"t{i}", "distance_m": 2000 + i * 100, "length_km": 3.0} for i in range(40)]}
    regional = {**ok, "swimming": [{"name": "lake", "distance_m": 4000, "type": "lake"}], "camping": []}
    monkeypatch.setattr(ao.osm_api, "query_green_spaces", lambda *a, **k: parks)
    calls = {"n": 0}

    def nature(*a, **k):
        calls["n"] += 1
        return trails if calls["n"] == 1 else regional
    monkeypatch.setattr(ao.osm_api, "query_nature_features", nature)
    monkeypatch.setattr(ao, "get_tree_canopy_gee", lambda *a, **k: 20.0)
    monkeypatch.setattr(ao, "_OVERPASS_STAGGER_S", 0.0)
    return ao.get_active_outdoors_score_v2(40.0, -74.0, city="X", area_type="suburban", precomputed_tree_canopy_5km=20.0)


def test_failed_trail_read_leaves_wild_adventure_out_and_flags_degraded(monkeypatch):
    score, d = _run(monkeypatch, "overpass_error")
    assert d["breakdown"]["wild_adventure"] is None and d["summary"]["components_missing"] == ["wild_adventure"]
    assert d["data_quality"]["degraded"] is True
    b = d["breakdown"]
    assert score == pytest.approx(round((b["daily_urban_outdoors"] + b["waterfront_lifestyle"]) / 60.0 * 100.0, 1), abs=0.11)


def test_good_reads_score_the_scaled_total(monkeypatch):
    score, d = _run(monkeypatch, "overpass_ok")
    b = d["breakdown"]
    assert d["summary"]["components_missing"] == []
    assert score == pytest.approx((b["daily_urban_outdoors"] + b["wild_adventure"] + b["waterfront_lifestyle"]) * 100 / 110, abs=0.2)
