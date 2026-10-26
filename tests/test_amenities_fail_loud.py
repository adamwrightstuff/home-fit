import random
from unittest import mock

from data_sources import osm_api
from pillars import neighborhood_amenities as na

EMPTY_ELEMENTS = {"elements": []}


def _resp(payload, status=200):
    r = mock.Mock()
    r.status_code = status
    r.text = "{}"
    r.json.return_value = payload
    r.headers = {}
    return r


def _count(total):
    return {"elements": [{"type": "count", "id": 0, "tags": {"total": str(total)}}]}


def _query(first_payload, control_response, lat):
    # query_local_businesses is cached (memory and disk); a fresh coordinate per call keeps tests independent
    lat = lat + random.random() / 100
    with mock.patch.object(osm_api, "get_overpass_url", return_value="https://a.example/api"), \
         mock.patch.object(osm_api, "_retry_overpass", return_value=_resp(first_payload)), \
         mock.patch.object(osm_api, "_overpass_remark_error", return_value=None), \
         mock.patch.object(osm_api.requests, "post", return_value=control_response) as post:
        return osm_api.query_local_businesses(lat, -97.0, radius_m=1000), post


def test_empty_read_with_map_data_in_the_circle_is_a_genuine_empty():
    result, post = _query(EMPTY_ELEMENTS, _resp(_count(1200)), 31.1)
    assert result is not None and not any(result[k] for k in ("tier1_daily", "tier2_social", "tier3_culture", "tier4_services"))
    assert "out count" in post.call_args[1]["data"]["data"]


def test_empty_read_with_no_map_data_is_a_failed_read():
    result, _ = _query(EMPTY_ELEMENTS, _resp(_count(0)), 32.2)
    assert result is None


def test_empty_read_with_failed_control_query_is_a_failed_read():
    result, _ = _query(EMPTY_ELEMENTS, _resp({}, status=504), 34.4)
    assert result is None


def test_failed_places_fallback_marks_pillar_degraded():
    biz = {"tier1_daily": [{"type": "cafe", "distance_m": 100, "lat": 30.0, "lon": -97.0, "name": "c"}],
           "tier2_social": [], "tier3_culture": [], "tier4_services": []}
    meta = {"used": False, "triggered": True, "error": "places_request_failed", "mapped_added": 0}
    with mock.patch.object(na.osm_api, "query_local_businesses", return_value=biz), \
         mock.patch.object(na, "maybe_augment_business_data_with_places", side_effect=lambda bd, *a, **k: (bd, meta)), \
         mock.patch("data_sources.census_api.get_population_density", return_value=900.0):
        _, details = na.get_neighborhood_amenities_score(30.0, -97.0, area_type="suburban", density=900.0)
    assert details["data_quality"]["degraded"] is True
    assert any("places_fallback_failed" in r for r in details["data_quality"]["degraded_reasons"])
    assert details["breakdown"]["home_walkability"]["businesses_within_walk"] == 1
