"""Unit tests for diversity_preference parsing and scoring mode."""

from pillars.diversity import get_diversity_score, parse_diversity_preference


def test_parse_diversity_preference_empty():
    assert parse_diversity_preference(None) is None
    assert parse_diversity_preference("") is None
    assert parse_diversity_preference("[]") is None
    assert parse_diversity_preference("not json") is None


def test_parse_diversity_preference_valid_and_filters():
    assert parse_diversity_preference('["race", "income"]') == ["race", "income"]
    assert parse_diversity_preference(["race", "age", "race"]) == ["race", "age"]
    assert parse_diversity_preference('["invalid", "race"]') == ["race"]


def test_get_diversity_score_accepts_preference_without_crash():
    """Smoke: ensure get_diversity_score runs; values depend on Census availability."""
    lat, lon = 40.6782, -73.9442
    score, details = get_diversity_score(lat, lon, diversity_preference=["race", "income"])
    assert isinstance(score, float)
    assert "summary" in details
    assert details["summary"].get("diversity_preference") == ["race", "income"]
