from scripts.metro_agent import health as hl


def _row(name, lat=1.0, lon=2.0, success=True):
    return {"success": success, "catalog": {"name": name, "county_borough": "C", "state_abbr": "TX", "lat": lat, "lon": lon},
            "score": {"livability_pillars": {}}}


def _csv(name, lat=1.0, lon=2.0):
    return {"name": name, "county_borough": "C", "state_abbr": "TX", "lat": str(lat), "lon": str(lon)}


def test_coverage_finds_missing_failed_moved_and_extra():
    c = hl.coverage([_csv("A"), _csv("B"), _csv("C"), _csv("D", 5, 5)],
                    [_row("A"), _row("C", success=False), _row("D", 9, 9), _row("Z")])
    assert c == {"missing": ["B"], "extra": ["Z"], "failed": ["C"], "pin_changed": ["D"]}


def test_report_lists_unhealthy_and_counts_publishable():
    reps = [{"metro": "a", "verdict": hl.HEALTHY, "places": 3, "problems": [], "notes": [], "retryable": False},
            {"metro": "b", "verdict": hl.UNHEALTHY, "places": 4, "problems": ["x"], "notes": [], "retryable": True}]
    out = hl.format_report(reps)
    assert "1 of 2 metros publishable" in out and "blocked: b" in out and "--fix" in out


def test_fix_only_touches_retryable_metros():
    calls = []
    reps = [{"metro": "a", "verdict": hl.UNHEALTHY, "retryable": True, "coverage": {"failed": []}},
            {"metro": "b", "verdict": hl.UNHEALTHY, "retryable": False, "coverage": {"failed": []}},
            {"metro": "c", "verdict": hl.HEALTHY, "retryable": True, "coverage": {"failed": []}}]
    done = hl.fix(reps, "http://x", log=lambda s: None, resolve_fn=lambda p, b, max_rounds=3: calls.append(p.name))
    assert done == ["a"] and len(calls) == 1


def test_quality_drift_reports_shape_on_empty_input():
    q = hl.quality_drift([])
    assert q == {"old_version": {}, "composite_drift": [], "other_flags": 0}
