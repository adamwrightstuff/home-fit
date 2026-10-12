from scripts.metro_agent import probe as pr


def test_amenities_verdicts():
    assert pr.amenities_verdict(None, None).startswith("UPSTREAM")
    assert pr.amenities_verdict(0, 0).startswith("OSM HAS NO BUSINESSES")
    assert pr.amenities_verdict(120, 0).startswith("CODE")
    assert pr.amenities_verdict(120, 40).startswith("FIXED")


def test_transit_verdicts():
    ok = lambda a, b, c: {2000: {"routes": a}, 5000: {"routes": b}, 10000: {"routes": c}}
    assert pr.transit_verdict(ok(3, 5, 9)).startswith("FIXED")
    assert pr.transit_verdict(ok(0, 4, 9)).startswith("COVERAGE")
    assert pr.transit_verdict(ok(0, 0, 0)).startswith("NO SERVICE")
    assert pr.transit_verdict({2000: {"error": "HTTP 500"}, 5000: {"routes": 0}, 10000: {"routes": 0}}).startswith("UPSTREAM")


def test_transit_counts_with_fake_http():
    class R:
        status_code = 200
        def json(self): return {"routes": [{"agency": {"agency_name": "CapMetro"}}] * 2}
    out = pr.transit_counts(30.0, -97.0, get=lambda *a, **k: R())
    assert out[2000]["routes"] == 2 and out[2000]["agencies"] == ["CapMetro"]


def test_raw_business_count_parses_overpass_count_and_rejects_errors():
    class Ok:
        status_code = 200
        def json(self): return {"elements": [{"type": "count", "tags": {"total": "37"}}]}
    class Bad:
        status_code = 200
        def json(self): return {"remark": "runtime error: Query timed out", "elements": []}
    assert pr.raw_business_count(1, 1, 500, post=lambda *a, **k: Ok()) == 37
    assert pr.raw_business_count(1, 1, 500, post=lambda *a, **k: Bad()) is None
