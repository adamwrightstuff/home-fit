"""Healthcare: a failed clinics/pharmacies query must be flagged and must never be served from cache."""
from unittest.mock import patch

from data_sources import osm_api


def test_partial_category_failure_is_flagged_not_silent():
    calls = {"n": 0}

    def fake_fetch(cat, q):  # inside the function we cannot patch _fetch_category; patch the transport instead
        raise AssertionError

    class R:
        status_code = 200
        def __init__(self, ok): self.ok = ok
        def json(self): return {"elements": []}
        text = '{"elements": []}'

    def post(url, data=None, **kw):
        calls["n"] += 1
        if "shop\"=\"pharmacy" in data["data"]:
            raise RuntimeError("boom")
        return R(True)

    with patch.object(osm_api.requests, "post", post), patch.object(osm_api, "_retry_overpass", lambda f, **k: f()):
        out = osm_api.query_healthcare_facilities.__wrapped__.__wrapped__.__wrapped__(30.0, -97.0, 5000)
    assert out["_query_failed"] is True and "pharmacies" in out["_failed_categories"]
    assert out["_cache_skip"] is True


def test_cached_failure_is_not_served(monkeypatch):
    from data_sources import cache
    calls = []

    @cache.cached(ttl_seconds=60)
    def f(x):
        calls.append(x)
        return {"_query_failed": True} if len(calls) == 1 else {"ok": 1}

    assert f("k")["_query_failed"]
    assert f("k") == {"ok": 1}
