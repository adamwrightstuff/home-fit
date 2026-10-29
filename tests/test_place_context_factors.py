"""The place context carries the continuous factors the area type is derived from."""

import pathlib

import pytest

from data_sources import data_quality
from data_sources import place_context as pc
from data_sources import principal_city as pcmod
from data_sources import surrounding_density as sd

TRACT = {"state_fips": "17", "county_fips": "031", "tract_fips": "010100"}


def _stats(people, activity, jobs=500.0, method="disk"):
    return sd.SurroundingStats(people, 3, method, jobs, activity)


def test_factors_come_from_the_same_measurement_as_the_area_type(monkeypatch):
    seen = {}

    def fake_stats(lat, lon, radius_m=1000, tract_geoid=None):
        if radius_m == 1000:  # the 1 km factors; the 10 km population read passes no tract
            seen["geoid"] = tract_geoid
        return _stats(9000.0, 20.0)

    monkeypatch.setattr(sd, "surrounding_stats", fake_stats)
    monkeypatch.setattr(pcmod, "principal_city_at", lambda lat, lon, state_fips=None: True)
    f = pc.surrounding_factors(41.9, -87.7, TRACT)
    people_10km = f.pop("people_10km")  # the same fake density over the 10 km disk: density x pi r^2 in square miles
    assert abs(people_10km - 9000.0 * 3.141592653589793 * (10000 / 1609.344) ** 2) < 1.0
    assert f == {"people_density_1km": 9000.0, "activity_per_acre": 20.0, "jobs_1km": 500.0,
                 "density_method": "disk", "in_principal_city": True}
    assert seen["geoid"] == "17031010100"
    # the context's factors reproduce the category the classifier assigns from the same inputs
    ctx = pc.PlaceContext(lat=41.9, lon=-87.7, city=None, area_type="x", density=None, **f)
    stats = _stats(ctx.people_density_1km, ctx.activity_per_acre)
    assert sd.classify_surrounding(stats, ctx.in_principal_city) == data_quality.detect_area_type(41.9, -87.7, census_tract=TRACT)


def test_unmeasurable_place_gives_no_factors_but_still_reports_membership(monkeypatch):
    monkeypatch.setattr(sd, "surrounding_stats", lambda *a, **k: None)
    monkeypatch.setattr(pcmod, "principal_city_at", lambda lat, lon, state_fips=None: None)
    assert pc.surrounding_factors(0.0, 0.0, None) == {"in_principal_city": None, "people_10km": None}


def test_context_without_factors_still_builds_with_empty_defaults():
    ctx = pc.PlaceContext(lat=1.0, lon=2.0, city=None, area_type="suburban", density=1000.0)
    assert ctx.people_density_1km is None and ctx.activity_per_acre is None and ctx.in_principal_city is None


def test_main_builds_the_factors_at_both_context_sites_and_the_cache_was_invalidated():
    src = (pathlib.Path(__file__).resolve().parents[1] / "main.py").read_text()
    assert src.count("**surrounding_factors(lat, lon, census_tract)") >= 2
    assert "SHARED_PREPILLAR_CACHE_SCHEMA = 3" in src
