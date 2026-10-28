"""Unit tests for diversity_preference parsing and scoring mode."""

import pytest

from pillars.diversity import get_diversity_score, parse_diversity_preference


def test_parse_diversity_preference_empty():
    assert parse_diversity_preference(None) is None
    assert parse_diversity_preference("") is None
    assert parse_diversity_preference("[]") is None
    assert parse_diversity_preference("not json") is None


def test_parse_diversity_preference_valid_and_filters():
    assert parse_diversity_preference('["children", "older"]') == ["children", "older"]
    assert parse_diversity_preference(["children", "working_age", "children"]) == ["children", "working_age"]
    assert parse_diversity_preference('["invalid", "older"]') == ["older"]
    assert parse_diversity_preference('["race", "income"]') is None  # retired dimensions


def test_get_diversity_score_accepts_preference_without_crash():
    """Smoke: ensure get_diversity_score runs; values depend on Census availability."""
    lat, lon = 40.6782, -73.9442
    try:
        score, details = get_diversity_score(lat, lon, diversity_preference=["children", "older"])
    except RuntimeError as exc:
        pytest.skip(f"Census diversity data unavailable: {exc}")
    assert isinstance(score, float) or score is None
    assert "summary" in details
    assert details["summary"].get("diversity_preference") == ["children", "older"]
