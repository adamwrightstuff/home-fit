from pathlib import Path

from scripts.metro_agent import diagnose as dg
from scripts.metro_agent import preflight as pf


def _row(pillars, name="Testville", success=True):
    return {"catalog": {"name": name}, "success": success, "score": {"livability_pillars": pillars}}


def _causes(row):
    return {(f.pillar, f.cause, f.material) for f in dg.classify_place(row)}


def test_overpass_parks_failure_is_material_upstream_error():
    row = _row({"active_outdoors": {"score": 0.0, "summary": {"overpass": {"local": "overpass_error", "trail": "overpass_ok", "regional": "overpass_ok"}}}})
    assert ("active_outdoors", dg.UPSTREAM_ERROR, True) in _causes(row)


def test_trail_only_failure_is_minor():
    row = _row({"active_outdoors": {"score": 50, "summary": {"overpass": {"local": "overpass_ok", "trail": "overpass_error", "regional": "overpass_ok"}}}})
    assert ("active_outdoors", dg.UPSTREAM_ERROR, False) in _causes(row)


def test_clean_active_outdoors_has_no_finding():
    row = _row({"active_outdoors": {"score": 70, "summary": {"overpass": {"local": "overpass_ok", "trail": "overpass_ok", "regional": "overpass_ok"}}}})
    assert dg.classify_place(row) == []


def test_state_level_crime_aggregate_is_no_data_source():
    row = _row({"community_safety": {"score": None, "breakdown": {"source": "fbi_cde_state", "agency_name": "Georgetown Police Department"}}})
    f = dg.classify_place(row)[0]
    assert (f.cause, f.remedy, f.material) == (dg.NO_DATA_SOURCE, dg.SOURCE, True)


def test_amenities_failure_reason_decides_the_cause():
    base = {"score": None, "status": "no_data", "breakdown": {"business_list": [], "diagnostics": {}}}
    assert dg.classify_place(_row({"neighborhood_amenities": {**base, "failure_reason": "osm_unavailable (suburban area)"}}))[0].cause == dg.UPSTREAM_ERROR
    assert dg.classify_place(_row({"neighborhood_amenities": {**base, "failure_reason": "osm_data_gap (suburban area)"}}))[0].cause == dg.SUSPECTED_UPSTREAM
    assert dg.classify_place(_row({"neighborhood_amenities": {**base, "failure_reason": "no_businesses_found"}}))[0].cause == dg.NO_DATA_SOURCE
    assert dg.classify_place(_row({"neighborhood_amenities": base}))[0].cause == dg.SUSPECTED_UPSTREAM  # old files


def test_transit_fallback_needs_verification_not_blind_retry():
    row = _row({"public_transit_access": {"score": 17, "summary": {"fallback_applied": True, "fallback_reason": "Transitland API unavailable for exurban area"}}})
    assert dg.classify_place(row)[0].remedy == dg.VERIFY


def test_school_scoring_off_is_informational():
    row = _row({"quality_education": {"score": 0.0, "status": "fallback", "data_quality": {"reason": "School scoring disabled"}}})
    f = dg.classify_place(row)[0]
    assert (f.cause, f.material) == (dg.DISABLED, False)


def test_healthcare_api_error_flagged():
    row = _row({"healthcare_access": {"score": 76, "data_quality": {"data_warnings": ["api_error"], "completeness": 0.0}}})
    assert ("healthcare_access", dg.UPSTREAM_ERROR, True) in _causes(row)


def test_failed_place_is_material():
    assert dg.classify_place(_row({}, success=False))[0].material


def test_systemic_cause_is_called_out():
    bad = {"active_outdoors": {"score": 0, "summary": {"overpass": {"local": "overpass_error"}}}}
    rows = [_row(bad, name=f"p{i}") for i in range(8)] + [_row({}, name="ok1"), _row({}, name="ok2")]
    out = dg.diagnose(rows)
    assert out["systemic"] and out["systemic"][0]["pillar"] == "active_outdoors"
    assert "SYSTEMIC" in dg.format_report(out)


def test_python_314_blocks_the_run():
    assert pf.check_python((3, 14, 0)).status == pf.FAIL
    assert pf.check_python((3, 12, 5)).status == pf.PASS


def test_overpass_probe_picks_a_healthy_mirror(monkeypatch):
    monkeypatch.delenv("OVERPASS_URL", raising=False)
    def probe(url, lat, lon):
        ok = "openstreetmap.fr" not in url and "z.overpass" in url
        return {"url": url, "ok": ok, "seconds": 1.2 if ok else None, "error": "" if ok else "HTTP 500"}
    checks = pf.check_overpass(30.3, -97.7, probe=probe)
    assert checks[0].status == pf.FAIL and "z.overpass-api.de" in checks[0].fix


def test_overpass_all_down_blocks(monkeypatch):
    monkeypatch.delenv("OVERPASS_URL", raising=False)
    probe = lambda url, lat, lon: {"url": url, "ok": False, "seconds": None, "error": "refused"}
    assert pf.check_overpass(30.3, -97.7, probe=probe)[0].status == pf.FAIL


def test_csv_checks():
    good = [{"name": "A", "county_borough": "X", "state_abbr": "TX", "search_query": "A, TX", "lat": "30.1", "lon": "-97.1"}]
    assert pf.check_csv(good)[0].status == pf.PASS
    assert pf.check_csv(good + good)[0].status == pf.FAIL
    assert pf.check_csv([{**good[0], "lat": "x"}])[0].status == pf.FAIL


def test_registration_and_baseline_for_registered_and_unknown_metro():
    assert all(c.status == pf.PASS for c in pf.check_registration("austin"))
    assert any(c.status == pf.FAIL for c in pf.check_registration("denver"))
    assert pf.check_baseline("denver").status == pf.FAIL
