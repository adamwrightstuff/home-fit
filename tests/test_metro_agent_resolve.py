import json

from scripts.metro_agent import diagnose as dg
from scripts.metro_agent import resolve as rs

BAD_AO = {"score": 0.0, "summary": {"overpass": {"local": "overpass_error", "trail": "overpass_ok", "regional": "overpass_ok"}}}
GOOD_AO = {"score": 60.0, "summary": {"overpass": {"local": "overpass_ok", "trail": "overpass_ok", "regional": "overpass_ok"}}}
BAD_TRANSIT = {"score": 17, "summary": {"fallback_applied": True, "fallback_reason": "Transitland API unavailable"}}
NO_CRIME = {"score": None, "breakdown": {"source": "fbi_cde_state", "agency_name": "Other PD"}}


def _row(name, **pillars):
    return {"catalog": {"name": name, "search_query": f"{name}, TX", "lat": "30.0", "lon": "-97.0"},
            "success": True, "score": {"livability_pillars": pillars}}


def _write(tmp_path, rows):
    p = tmp_path / "scores.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return p


def _merge(existing, new_score, pillars):
    out = json.loads(json.dumps(existing))
    for k in pillars:
        out["score"]["livability_pillars"][k] = new_score["livability_pillars"][k]
    return out


def _run(path, scorer, **kw):
    calls = []
    def wrapped(session, base, loc, pillars, lat, lon, timeout):
        calls.append((loc, tuple(pillars)))
        return scorer(loc, pillars)
    kw.setdefault("recompute", None)
    kw.setdefault("lean_refresh", None)
    kw.setdefault("delay", 0)
    kw.setdefault("dependency_check", lambda rows: None)
    kw.setdefault("log", lambda s: None)
    out = rs.resolve(path, "http://x", session=object(), scorer=wrapped, merge=_merge, **kw)
    return out, calls


def test_retry_fixes_upstream_failure_and_recomputes_once(tmp_path):
    p = _write(tmp_path, [_row("A", active_outdoors=BAD_AO), _row("B", active_outdoors=GOOD_AO)])
    recomputed = []
    out, calls = _run(p, lambda loc, ps: {"livability_pillars": {"active_outdoors": GOOD_AO}},
                      recompute=lambda path: recomputed.append(path))
    assert calls == [("A, TX", ("active_outdoors",))]  # only the affected place, only that pillar
    assert out["material_places_left"] == 0 and out["stopped"] == "nothing_actionable"
    assert len(recomputed) == 1
    assert dg.diagnose(dg.load_rows(p))["material_places"] == []


def test_verify_findings_are_retried_exactly_once(tmp_path):
    p = _write(tmp_path, [_row("A", public_transit_access=BAD_TRANSIT)])
    out, calls = _run(p, lambda loc, ps: {"livability_pillars": {"public_transit_access": BAD_TRANSIT}}, max_rounds=4)
    assert len(calls) == 1
    assert out["needs_human_check"][0]["place"] == "A"


def test_missing_crime_source_is_retried_once_because_the_agency_map_is_data(tmp_path):
    p = _write(tmp_path, [_row("A", community_safety=NO_CRIME)])
    out, calls = _run(p, lambda loc, ps: {"livability_pillars": {}})
    assert len(calls) == 1
    assert out["needs_data_source"][0]["pillar"] == "community_safety"
    assert out["material_places_left"] == 1


def test_worse_result_never_replaces_a_better_one(tmp_path):
    ok_but_partial = {"score": 40.0, "summary": {"overpass": {"local": "overpass_ok", "trail": "overpass_ok", "regional": "overpass_error"}}}
    p = _write(tmp_path, [_row("A", active_outdoors=ok_but_partial)])
    worse = {"score": 0.0, "summary": {"overpass": {"local": "overpass_error", "trail": "overpass_error", "regional": "overpass_error"}}}
    before = p.read_text()
    out, _ = _run(p, lambda loc, ps: {"livability_pillars": {"active_outdoors": worse}}, max_rounds=1)
    assert p.read_text() == before


def test_systemic_failure_with_unhealthy_dependency_aborts_before_any_call(tmp_path):
    rows = [_row(f"p{i}", active_outdoors=BAD_AO) for i in range(5)]
    p = _write(tmp_path, rows)
    out, calls = _run(p, lambda loc, ps: {"livability_pillars": {"active_outdoors": GOOD_AO}},
                      dependency_check=lambda r: "Overpass down")
    assert calls == [] and out["stopped"] == "dependency_down"


def test_stops_when_a_round_makes_no_progress(tmp_path):
    p = _write(tmp_path, [_row("A", active_outdoors=BAD_AO)])
    out, calls = _run(p, lambda loc, ps: {"livability_pillars": {"active_outdoors": BAD_AO}}, max_rounds=5)
    assert out["stopped"] == "no_progress" and len(calls) == 1
    assert out["still_failing_after_retries"][0]["place"] == "A"


def test_dry_run_makes_no_calls_and_writes_nothing(tmp_path):
    p = _write(tmp_path, [_row("A", active_outdoors=BAD_AO)])
    before = p.read_text()
    out, calls = _run(p, lambda loc, ps: {"livability_pillars": {}}, dry_run=True)
    assert calls == [] and p.read_text() == before and out["stopped"] == "dry_run"


def test_publish_gate_text():
    blocked = rs.format_summary({"stopped": "x", "rounds": 1, "api_calls": 0, "material_places_left": 2,
                                 "needs_data_source": [], "needs_human_check": [], "still_failing_after_retries": []})
    assert "BLOCKED" in blocked
    ok = rs.format_summary({"stopped": "x", "rounds": 1, "api_calls": 0, "material_places_left": 0,
                            "needs_data_source": [], "needs_human_check": [], "still_failing_after_retries": []})
    assert "PUBLISH: OK" in ok


def test_political_lean_findings_trigger_one_offline_refresh(tmp_path):
    no_lean = {"score": None, "breakdown": {"lean_2024": None}}
    p = _write(tmp_path, [_row("A", political_lean=no_lean)])
    seen = []
    _run(p, lambda loc, ps: {"livability_pillars": {}}, lean_refresh=lambda path: seen.append(path))
    assert len(seen) == 1
