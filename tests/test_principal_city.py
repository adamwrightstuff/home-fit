"""Principal-city membership and the two urban cutoffs (inside a principal city 15, elsewhere 35, unknown 25)."""

import pytest

from data_sources import data_quality
from data_sources import principal_city as pcmod
from data_sources import surrounding_density as sd


@pytest.fixture
def synthetic_layer(monkeypatch):
    from shapely.geometry import box
    from shapely.strtree import STRtree
    geoms = [box(-122.0, 37.0, -121.0, 38.0)]  # one "principal city" in California (state 06)
    monkeypatch.setattr(pcmod, "_loaded", True)
    monkeypatch.setattr(pcmod, "_geoms", geoms)
    monkeypatch.setattr(pcmod, "_names", [("Testville", "Test Metro")])
    monkeypatch.setattr(pcmod, "_tree", STRtree(geoms))
    monkeypatch.setattr(pcmod, "_covered", frozenset({"06"}))


def test_inside_an_outline_is_true(synthetic_layer):
    assert pcmod.principal_city_at(37.5, -121.5) is True


def test_outside_in_a_covered_state_is_false(synthetic_layer):
    assert pcmod.principal_city_at(36.0, -121.5, state_fips="06") is False


def test_outside_in_an_uncovered_state_is_unknown_not_false(synthetic_layer):
    assert pcmod.principal_city_at(30.0, -97.0, state_fips="48") is None


def test_outside_without_a_state_is_unknown(synthetic_layer):
    assert pcmod.principal_city_at(36.0, -121.5) is None


def test_missing_layer_is_unknown(monkeypatch):
    monkeypatch.setattr(pcmod, "_loaded", True)
    monkeypatch.setattr(pcmod, "_tree", None)
    assert pcmod.principal_city_at(37.5, -121.5, state_fips="06") is None


def test_real_layer_knows_chicago_but_not_oak_park():
    assert pcmod.principal_city_at(41.8781, -87.6298, state_fips="17") is True        # the Loop
    assert pcmod.principal_city_at(41.8850, -87.7845, state_fips="17") is False       # Oak Park: a separate town
    assert pcmod.principal_city_at(45.52, -122.68, state_fips="41") is None            # Oregon: not covered yet


def _stats(people, activity):
    return sd.SurroundingStats(people, 3, "disk", 0.0, activity)


def test_the_same_activity_is_urban_inside_a_principal_city_and_suburban_outside():
    s = _stats(9000, 20.0)
    assert sd.classify_surrounding(s, True) == "urban_residential"
    assert sd.classify_surrounding(s, False) == "suburban"
    assert sd.classify_surrounding(s, None) == "suburban"  # unknown membership uses 25


@pytest.mark.parametrize("member,activity,expected", [
    (True, 14.9, "suburban"), (True, 15.0, "urban_residential"),
    (False, 34.9, "suburban"), (False, 35.0, "urban_residential"),
    (None, 24.9, "suburban"), (None, 25.0, "urban_residential"),
])
def test_urban_steps(member, activity, expected):
    assert sd.classify_surrounding(_stats(9000, activity), member) == expected


def test_a_low_density_place_inside_a_principal_city_is_not_urban():
    # Lake Nona, Orlando: inside the city limits, 580 people and 1.1 activity units per acre
    assert sd.classify_surrounding(_stats(580, 1.1), True) == "rural"


def test_detect_area_type_passes_the_pin_state_to_the_membership_lookup(monkeypatch):
    seen = {}

    def fake(lat, lon, state_fips=None):
        seen["state"] = state_fips
        return True

    monkeypatch.setattr(pcmod, "principal_city_at", fake)
    monkeypatch.setattr(sd, "surrounding_stats", lambda lat, lon, radius_m=1000, tract_geoid=None: _stats(9000, 20.0))
    tract = {"state_fips": "17", "county_fips": "031", "tract_fips": "010100"}
    assert data_quality.detect_area_type(41.9, -87.7, census_tract=tract) == "urban_residential"
    assert seen["state"] == "17"


def test_only_principal_cities_named_in_their_metro_title_count():
    assert pcmod.principal_city_at(32.7767, -96.7970, state_fips="48") is True    # Dallas (Dallas-Fort Worth-Arlington)
    assert pcmod.principal_city_at(33.0198, -96.6989, state_fips="48") is False   # Plano: OMB principal city, not in the title
    assert pcmod.principal_city_at(37.3382, -121.8863, state_fips="06") is True   # San Jose
    assert pcmod.principal_city_at(37.3861, -122.0839, state_fips="06") is False  # Mountain View: not a principal city
