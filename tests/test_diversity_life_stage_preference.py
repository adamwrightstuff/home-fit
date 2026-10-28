import pytest
from pillars import diversity
from data_sources import census_api


def _fake(monkeypatch, youth, prime, seniors):
    monkeypatch.setattr(census_api, "get_census_tract", lambda lat, lon: {"tract_fips": "1", "state_fips": "1", "county_fips": "1"})
    monkeypatch.setattr(census_api, "get_diversity_data", lambda *a, **k: {
        "age_counts": {"youth": youth, "prime": prime, "seniors": seniors}, "income_counts": {"B19001_002E": 1},
        "ethnicity_counts": {"B03002_003E": 1}, "geo_level": "tract", "total_population": 100})


def test_no_preference_gives_no_score(monkeypatch):
    _fake(monkeypatch, 22, 62, 16)
    score, d = diversity.get_diversity_score(40.0, -75.0, area_type="suburban", density=3000.0)
    assert score is None and d["breakdown"]["age_shares"]["children"] == 22.0


def test_children_preference_scores_by_percentile(monkeypatch):
    _fake(monkeypatch, 35, 55, 10)
    hi, _ = diversity.get_diversity_score(40.0, -75.0, area_type="suburban", density=3000.0, diversity_preference=["children"])
    _fake(monkeypatch, 10, 70, 20)
    lo, _ = diversity.get_diversity_score(40.0, -75.0, area_type="suburban", density=3000.0, diversity_preference=["children"])
    assert hi > 90 and lo < 10


def test_old_dimension_names_are_ignored():
    assert diversity.parse_diversity_preference(["race", "income"]) is None
    assert diversity.parse_diversity_preference(["children", "older"]) == ["children", "older"]
