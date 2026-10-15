import json

import pytest
import requests

from data_sources import overpass_cache as oc
from pillars import strict_lookups as sl

URL = "https://overpass-api.de/api/interpreter"
GOOD = json.dumps({"elements": [{"type": "node", "id": 1}]}).encode()


def _resp(status, body):
    r = requests.Response()
    r.status_code = status
    r._content = body
    return r


def test_only_verified_good_answers_are_kept():
    assert oc.is_verified_good(200, GOOD)
    assert not oc.is_verified_good(200, json.dumps({"elements": []}).encode())                      # silent empty
    assert not oc.is_verified_good(200, json.dumps({"elements": [{"id": 1}], "remark": "runtime error: timeout"}).encode())
    assert not oc.is_verified_good(504, GOOD)
    assert not oc.is_verified_good(200, b"<html>busy</html>")


def test_good_answers_replay_and_bad_ones_are_asked_again(tmp_path, monkeypatch):
    monkeypatch.setenv("HOMEFIT_OSM_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("HOMEFIT_OSM_CACHE_MODE", "readwrite")
    answers = [_resp(504, b"busy"), _resp(200, GOOD)]
    calls = []
    monkeypatch.setattr(oc, "_real_post", lambda url, *a, **k: calls.append(1) or answers[len(calls) - 1])
    q = {"data": "[out:json];node(1);out;"}
    assert oc.cached_post(URL, data=q).status_code == 504       # not saved
    assert oc.cached_post(URL, data=q).status_code == 200       # asked again, saved
    assert oc.cached_post(URL, data=q).json()["elements"]       # replayed: no third call
    assert len(calls) == 2


def test_replay_mode_never_touches_the_network(tmp_path, monkeypatch):
    monkeypatch.setenv("HOMEFIT_OSM_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("HOMEFIT_OSM_CACHE_MODE", "replay")
    monkeypatch.setattr(oc, "_real_post", lambda *a, **k: pytest.fail("network used"))
    with pytest.raises(requests.ConnectionError):
        oc.cached_post(URL, data={"data": "[out:json];node(2);out;"})


def test_non_overpass_urls_pass_through(tmp_path, monkeypatch):
    monkeypatch.setenv("HOMEFIT_OSM_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(oc, "_real_post", lambda url, *a, **k: _resp(200, b"ok"))
    assert oc.cached_post("https://example.com/x", data={"data": "q"}).content == b"ok"


def test_strict_mode_blanks_failed_lookups_only(monkeypatch):
    pillars = {
        "healthcare_access": {"score": 40.0, "data_quality": {"data_warning": "api_error"}, "contribution": 3.6},
        "active_outdoors": {"score": 50.0, "summary": {"overpass": {"local": "overpass_ok", "regional": "overpass_error"}}},
        "social_fabric": {"score": 60.0},
    }
    monkeypatch.delenv("HOMEFIT_STRICT_LOOKUPS", raising=False)
    import copy
    off = copy.deepcopy(pillars); sl.apply_strict_lookup_failures(off)
    assert off == pillars                                        # live behaviour unchanged
    monkeypatch.setenv("HOMEFIT_STRICT_LOOKUPS", "true")
    sl.apply_strict_lookup_failures(pillars)
    assert pillars["healthcare_access"]["score"] is None and pillars["active_outdoors"]["score"] is None
    assert pillars["social_fabric"]["score"] == 60.0
    assert pillars["healthcare_access"]["data_quality"]["lookup_failed"]
