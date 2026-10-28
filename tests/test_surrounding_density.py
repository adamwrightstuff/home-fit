"""Area type from the surrounding 1 km circle: people per sq mi and people plus jobs per acre."""

import math

import numpy as np
import pytest

from data_sources import data_quality
from data_sources import surrounding_density as sd

h3 = pytest.importorskip("h3")
PIN = (41.9217, -87.6806)


def _m_to_deg(north_m=0.0, east_m=0.0, lat=PIN[0]):
    return north_m / 110_540.0, east_m / (111_320.0 * math.cos(math.radians(lat)))


@pytest.fixture
def tables(monkeypatch):
    """Three tracts near the pin: two centers inside 1 km, one 3 km away."""
    def at(n, e):
        dlat, dlon = _m_to_deg(n, e)
        return PIN[0] + dlat, PIN[1] + dlon

    pts = [at(200, 100), at(-400, 300), at(3000, 0)]
    lat = np.array([p[0] for p in pts]); lon = np.array([p[1] for p in pts])
    pop = np.array([4000.0, 6000.0, 100.0]); land = np.array([0.5, 0.5, 1.0])
    monkeypatch.setattr(sd, "_tract", (lat, lon, pop, land))
    monkeypatch.setattr(sd, "_geoid_index", {"17031010100": 0, "17031010200": 1, "17031999900": 2})
    sd._stats_cached.cache_clear()
    yield
    sd._stats_cached.cache_clear()


def _jobs_patch(monkeypatch, per_cell):
    center = h3.latlng_to_cell(*PIN, 8)
    cells = sorted(h3.str_to_int(c) for c in h3.grid_disk(center, 12))
    monkeypatch.setattr(sd, "_jobs", (np.array(cells, dtype="uint64"), np.full(len(cells), float(per_cell))))
    sd._stats_cached.cache_clear()


def test_people_density_is_total_people_over_total_land_of_tracts_in_the_circle(tables):
    density, n, method = sd.people_density_in_disk(*PIN)
    assert (n, method) == (2, "disk")
    assert density == pytest.approx((4000 + 6000) / (0.5 + 0.5))  # the tract 3 km away is not counted


def test_a_circle_with_no_tract_center_uses_the_pin_tract_when_known(tables):
    far = (PIN[0] + 0.3, PIN[1])  # about 33 km from every center
    assert sd.people_density_in_disk(*far, tract_geoid="17031999900") == (100.0, 0, "pin_tract")


def test_without_the_pin_tract_the_nearest_center_stands_in_and_says_so(tables):
    d, n, method = sd.people_density_in_disk(PIN[0] + 0.05, PIN[1])  # about 5.5 km out, nearest center 2.5 km away
    assert (n, method) == (0, "nearest_tract")


def test_nothing_within_range_is_unavailable_not_zero(tables):
    assert sd.people_density_in_disk(PIN[0] + 5.0, PIN[1]) is None


def test_jobs_add_to_activity_per_acre(tables, monkeypatch):
    _jobs_patch(monkeypatch, per_cell=1000.0)
    stats = sd.surrounding_stats(*PIN)
    assert stats.jobs_known and stats.jobs > 0
    people_per_acre = stats.people_density / 640.0
    assert stats.activity_per_acre > people_per_acre


def test_jobs_grid_not_covering_the_place_is_unknown_and_activity_is_people_only(tables, monkeypatch):
    monkeypatch.setattr(sd, "_jobs", (np.array([], dtype="uint64"), np.array([], dtype="float64")))
    sd._stats_cached.cache_clear()
    stats = sd.surrounding_stats(*PIN)
    assert stats.jobs is None and not stats.jobs_known
    assert stats.activity_per_acre == pytest.approx(stats.people_density / 640.0)


def _stats(people, activity):
    return sd.SurroundingStats(people, 3, "disk", 0.0, activity)


@pytest.mark.parametrize("people,activity,expected", [
    (4579, 914.0, "urban_residential"),   # Midtown: sparse tract, jobs make it urban
    (30000, 24.9, "suburban"),            # just under the activity step: density alone decides
    (30000, 25.0, "urban_residential"),
    (18000, 41.0, "urban_residential"),   # a dense inner neighborhood (West Hollywood) is urban
    (3000, 10.0, "suburban"),
    (2999, 10.0, "exurban"),
    (800, 3.0, "exurban"),
    (799, 3.0, "rural"),
])
def test_cutoffs(people, activity, expected):
    assert sd.classify_surrounding(_stats(people, activity)) == expected


def test_no_measurement_is_unknown():
    assert sd.classify_surrounding(None) == "unknown"


def test_classifier_never_returns_urban_core():
    for people in (0, 500, 3000, 90000):
        for activity in (0, 20, 45, 900):
            assert sd.classify_surrounding(_stats(people, activity)) != "urban_core"


def test_detect_area_type_uses_the_surrounding_circle_and_ignores_the_pin_tract_and_business_count(monkeypatch):
    monkeypatch.setattr(sd, "surrounding_stats", lambda lat, lon, radius_m=1000, tract_geoid=None: _stats(18000, 60.0))
    # a sparse pin tract (17 per sq mi) and zero businesses would have read rural before
    assert data_quality.detect_area_type(1.0, 2.0, density=17.0, business_count=0) == "urban_residential"


def test_detect_area_type_passes_the_pin_tract_geoid(monkeypatch):
    seen = {}

    def fake(lat, lon, radius_m=1000, tract_geoid=None):
        seen["geoid"] = tract_geoid
        return _stats(1000, 5.0)

    monkeypatch.setattr(sd, "surrounding_stats", fake)
    data_quality.detect_area_type(1.0, 2.0, census_tract={"state_fips": "48", "county_fips": "243", "tract_fips": "950100"})
    assert seen["geoid"] == "48243950100"
