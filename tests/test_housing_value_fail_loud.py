"""Housing value fails loudly: no invented fallback scores, no silent zeros."""
import pytest

import pillars.housing_value as hv
from data_sources import census_api, data_quality


def _patch(monkeypatch, housing):
    monkeypatch.setattr(census_api, "get_population_density", lambda *a, **k: 3000.0)
    monkeypatch.setattr(data_quality, "detect_area_type", lambda *a, **k: "urban_core")
    monkeypatch.setattr(census_api, "get_housing_data", lambda *a, **k: housing)
    monkeypatch.setattr(hv, "get_home_value", lambda value, zip_code: (value, False))


FULL = {"median_home_value": 400000.0, "median_household_income": 100000.0, "median_rooms": 5.0,
        "median_gross_rent": 2000.0, "renter_pct": 0.5}


def test_no_housing_data_raises_instead_of_a_fallback_score(monkeypatch):
    _patch(monkeypatch, None)
    with pytest.raises(RuntimeError):
        hv.get_housing_value_score(40.75, -73.98, city="New York", zip_code="10110")


def test_missing_room_count_is_no_data_not_a_zero(monkeypatch):
    _patch(monkeypatch, {**FULL, "median_rooms": None})
    with pytest.raises(RuntimeError):  # space and efficiency both need rooms, leaving affordability alone
        hv.get_housing_value_score(40.75, -73.98, city="New York", zip_code="10110")


def test_complete_data_scores_exactly_as_before(monkeypatch):
    _patch(monkeypatch, FULL)
    score, d = hv.get_housing_value_score(40.75, -73.98, city="New York", zip_code="10110")
    b = d["breakdown"]
    assert score == round(b["local_affordability"] + b["space"] + b["value_efficiency"], 1)
    assert not d["data_quality"].get("degraded")


def test_helpers_return_none_for_missing_inputs():
    assert hv._score_space(None) is None and hv._score_space(0) is None
    assert hv._score_local_affordability(None, 100000.0) is None and hv._score_local_affordability(300000.0, 0) is None
    assert hv._score_rent_affordability(2000.0, 0) is None
    assert hv._score_value_efficiency(300000.0, None) is None
