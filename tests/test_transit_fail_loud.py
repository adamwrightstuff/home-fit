"""Public transit: a failed Transitland read is no data, and no invented fallback score is applied (design principles v2, P9)."""
import pytest
import requests

import pillars.public_transit_access as pt
from data_sources import osm_api


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    monkeypatch.setattr(pt, "get_nearby_transit_stops", lambda *a, **k: None)
    monkeypatch.setattr(pt, "TRANSITLAND_API_KEY", "test-key")


class _Resp:
    def __init__(self, status, payload=None):
        self.status_code = status
        self._payload = payload or {}

    def json(self):
        return self._payload


def _score():
    return pt.get_public_transit_score(40.9, -73.8, area_type="suburban", density=3000.0)


def test_missing_api_key_raises(monkeypatch):
    monkeypatch.setattr(pt, "TRANSITLAND_API_KEY", None)
    with pytest.raises(pt.TransitReadError):
        pt._get_nearby_routes(40.9, -73.8, 2000)


def test_http_error_raises(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *a, **k: _Resp(503))
    with pytest.raises(pt.TransitReadError):
        pt._get_nearby_routes(40.9, -73.8, 2000)


def test_exception_raises(monkeypatch):
    def boom(*a, **k):
        raise requests.exceptions.ConnectionError("down")
    monkeypatch.setattr(requests, "get", boom)
    with pytest.raises(pt.TransitReadError):
        pt._get_nearby_routes(40.9, -73.8, 2000)


def test_genuine_empty_answer_is_an_empty_list(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *a, **k: _Resp(200, {"routes": []}))
    assert pt._get_nearby_routes(40.9, -73.8, 2000) == []


def test_failed_read_makes_the_pillar_raise_not_score_zero(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *a, **k: _Resp(500))
    with pytest.raises(pt.TransitReadError):
        _score()


def test_empty_answer_with_no_osm_station_is_a_marked_zero_without_invented_points(monkeypatch):
    monkeypatch.setattr(pt, "_get_nearby_routes", lambda *a, **k: [])
    monkeypatch.setattr(osm_api, "query_railway_stations", lambda *a, **k: [])
    score, bd = _score()
    assert score == 0
    assert bd["summary"].get("no_service_found") is True
    assert "fallback_applied" not in bd["summary"]
    assert "no_transit_routes_found" in bd["data_quality"]["data_warnings"]


def test_osm_station_read_failure_after_empty_routes_raises(monkeypatch):
    monkeypatch.setattr(pt, "_get_nearby_routes", lambda *a, **k: [])
    monkeypatch.setattr(osm_api, "query_railway_stations", lambda *a, **k: None)
    with pytest.raises(pt.TransitReadError):
        _score()
