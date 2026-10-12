from unittest import mock

from pillars import neighborhood_amenities as na


EMPTY = {"tier1_daily": [], "tier2_social": [], "tier3_culture": [], "tier4_services": []}


def _score(business_data, area_type="suburban"):
    meta = {"used": False, "mapped_added": 0}
    with mock.patch.object(na.osm_api, "query_local_businesses", return_value=business_data), \
         mock.patch.object(na, "maybe_augment_business_data_with_places", side_effect=lambda bd, *a, **k: (bd, meta)), \
         mock.patch("data_sources.census_api.get_population_density", return_value=900.0):
        return na.get_neighborhood_amenities_score(30.36, -97.98, area_type=area_type, density=900.0)


def test_empty_walkable_area_gets_a_low_score_not_none():
    score, details = _score(EMPTY)
    assert score is not None and score <= 5
    assert details["empty_walkable_area"] is True
    assert "no_businesses_within_radius" in details["data_quality"]["data_warnings"]
    assert details["data_quality"]["confidence"] <= 40


def test_failed_lookup_is_still_none_with_the_reason():
    score, details = _score(None)
    assert score is None
    assert details["failure_reason"].startswith("osm_unavailable")


def test_rural_failed_lookup_is_labeled_unavailable_not_no_businesses():
    score, details = _score(None, area_type="rural")
    assert score is None and "osm_unavailable" in details["failure_reason"]
