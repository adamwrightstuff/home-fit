import json

from data_sources import osm_api


class Resp:
    def __init__(self, body, status=200):
        self.status_code = status
        self.text = json.dumps(body)
        self.headers = {}

    def json(self):
        return json.loads(self.text)


TIMEOUT = Resp({"version": 0.6, "remark": 'runtime error: Query timed out in "query" at line 3 after 61 seconds.', "elements": []})
EMPTY_OK = Resp({"version": 0.6, "elements": []})
GOOD = Resp({"version": 0.6, "elements": [{"type": "node", "id": 1}]})


def test_remark_error_detected_only_when_it_is_a_runtime_error():
    assert "timed out" in osm_api._overpass_remark_error(TIMEOUT)
    assert osm_api._overpass_remark_error(EMPTY_OK) is None
    assert osm_api._overpass_remark_error(GOOD) is None
    assert osm_api._overpass_remark_error(Resp({"remark": "just a note", "elements": []})) is None
    assert osm_api._overpass_remark_error(Resp({}, status=504)) is None
    assert osm_api._overpass_remark_error(None) is None


def _retry(monkeypatch, responses):
    monkeypatch.setattr(osm_api.time, "sleep", lambda s: None)
    seq = list(responses)
    calls = []
    def fn():
        calls.append(1)
        return seq.pop(0)
    return osm_api._retry_overpass(fn, attempts=3, base_wait=0), calls


def test_server_side_timeout_is_retried_not_treated_as_empty(monkeypatch):
    resp, calls = _retry(monkeypatch, [TIMEOUT, TIMEOUT, GOOD])
    assert resp is GOOD and len(calls) == 3


def test_persistent_server_side_timeout_returns_none(monkeypatch):
    resp, calls = _retry(monkeypatch, [TIMEOUT, TIMEOUT, TIMEOUT])
    assert resp is None and len(calls) == 3


def test_a_genuine_empty_result_is_returned_without_retry(monkeypatch):
    resp, calls = _retry(monkeypatch, [EMPTY_OK, GOOD, GOOD])
    assert resp is EMPTY_OK and len(calls) == 1
