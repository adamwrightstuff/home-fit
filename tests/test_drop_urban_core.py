"""Urban core is no longer a class: the classifier never returns it and Census geography ignores it."""

import itertools

import pytest

from data_sources import census_api
from data_sources.data_quality import classify_morphology


def test_classifier_never_returns_urban_core():
    densities = [None, 0, 10, 500, 800, 1500, 2500, 3000, 4579, 8000, 12000, 25000, 60000, 90000]
    counts = [None, 0, 10, 80, 100, 150, 400, 1228, 3000]
    got = {classify_morphology(d, None, c, None) for d, c in itertools.product(densities, counts)}
    assert "urban_core" not in got
    assert got <= {"urban_residential", "suburban", "exurban", "rural", "unknown"}


def test_a_commercial_center_with_a_low_tract_density_is_urban_residential():
    # Midtown, New York: pin tract density 4,579 per sq mi, 1,228 businesses within 1 km
    assert classify_morphology(4579, None, 1228, None) == "urban_residential"


def test_existing_classes_are_unchanged_below_the_old_core_rule():
    assert classify_morphology(26000, None, 20, None) == "urban_residential"
    assert classify_morphology(12500, None, 100, None) == "urban_residential"
    assert classify_morphology(3500, None, 40, None) == "suburban"
    assert classify_morphology(1000, None, 10, None) == "exurban"
    assert classify_morphology(300, None, 5, None) == "rural"
    assert classify_morphology(1500, None, 90, None) == "unknown"  # dead-tract guard


TRACT = {"state_fips": "36", "county_fips": "061", "tract_fips": "011900"}
_next = itertools.count()


def _fresh_pin():
    # The Census lookups are cached by arguments, so each case gets its own coordinates.
    n = next(_next)
    return 40.0 + n * 0.0001, -73.0 - n * 0.0001


@pytest.mark.parametrize("area_type", [None, "urban_core", "urban_residential", "suburban"])
@pytest.mark.parametrize("units,expected", [(150_000, "incorporated_place"), (200_000, "incorporated_place"), (200_001, "tract")])
def test_housing_geography_depends_on_place_size_not_on_area_type(monkeypatch, area_type, units, expected):
    monkeypatch.setattr(census_api, "get_population", lambda t: 5000)
    monkeypatch.setattr(census_api, "get_place_fips_for_coordinates",
                        lambda lat, lon: {"geo_type": "incorporated_place", "place_fips": "51000", "state_fips": "36"})
    monkeypatch.setattr(census_api, "_fetch_housing_acs",
                        lambda geo_for, geo_in: {"total_occupied": units, "median_home_value": 1.0, "geo_for": geo_for})
    lat, lon = _fresh_pin()
    got = census_api.get_housing_data(lat, lon, tract=TRACT, area_type=area_type)
    assert got["geo_level"] == expected


@pytest.mark.parametrize("area_type", [None, "urban_core", "suburban"])
@pytest.mark.parametrize("adults,expected", [(150_000, "place"), (200_000, "place"), (200_001, "tract")])
def test_diversity_geography_depends_on_place_size_not_on_area_type(monkeypatch, area_type, adults, expected):
    monkeypatch.setattr(census_api, "get_place_fips_for_coordinates",
                        lambda lat, lon: {"geo_type": "incorporated_place", "place_fips": "51000", "state_fips": "36"})

    def fake(geo_for, geo_in):
        pop = adults if geo_for.startswith("place") else 4000
        return {"education_attainment": {"population_25_plus": pop}}

    monkeypatch.setattr(census_api, "_fetch_diversity_acs", fake)
    lat, lon = _fresh_pin()
    got = census_api.get_diversity_data(lat, lon, tract=TRACT, area_type=area_type)
    assert got["geo_level"] == expected
