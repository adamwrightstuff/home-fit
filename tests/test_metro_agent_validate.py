import json

from scripts.metro_agent import diagnose as dg
from scripts.metro_agent import validate as vd


def test_amenities_zero_with_many_census_establishments_is_contradicted():
    assert vd.judge_amenities(171, 0)[0] == vd.CONTRADICTED
    assert vd.judge_amenities(4, 0)[0] == vd.CONSISTENT
    assert vd.judge_amenities(15, 0)[0] == vd.INCONCLUSIVE
    assert vd.judge_amenities(171, 12)[0] == vd.INCONCLUSIVE
    assert vd.judge_amenities(None, 0)[0] == vd.INCONCLUSIVE


def test_transit_zero_routes_judged_against_commuter_share():
    assert vd.judge_transit(0.09, 0)[0] == vd.CONTRADICTED
    assert vd.judge_transit(0.004, 0)[0] == vd.CONSISTENT
    assert vd.judge_transit(0.015, 0)[0] == vd.INCONCLUSIVE
    assert vd.judge_transit(0.09, 5)[0] == vd.INCONCLUSIVE


def _row(name, lat, lon, **pillars):
    return {"catalog": {"name": name, "lat": str(lat), "lon": str(lon)}, "success": True,
            "score": {"livability_pillars": {k: {"score": v} for k, v in pillars.items()}, "location_info": {"zip": "78734"}}}


def test_peer_collapse_flags_a_zero_among_healthy_neighbours_only():
    rows = [_row(f"p{i}", 30 + i * 0.01, -97, active_outdoors=60 + i) for i in range(6)]
    rows.append(_row("collapsed", 30.03, -97, active_outdoors=0.0))
    flagged = {(v.place, v.pillar) for v in vd.peer_collapses(rows)}
    assert ("collapsed", "active_outdoors") in flagged
    assert not any(p.startswith("p") for p, _ in flagged)


def test_peer_collapse_ignores_isolated_places_without_enough_peers():
    rows = [_row("a", 30, -97, active_outdoors=0.0), _row("b", 31, -97, active_outdoors=70)]
    assert vd.peer_collapses(rows) == []


def test_accepted_gaps_stop_blocking_but_contradicted_ones_never_do(tmp_path):
    scores = tmp_path / "s.jsonl"
    bd = {"business_list": [], "diagnostics": {}}
    row = {"catalog": {"name": "A"}, "success": True, "score": {"livability_pillars": {
        "neighborhood_amenities": {"score": None, "status": "no_data", "breakdown": bd, "failure_reason": "osm_data_gap (x)"}}}}
    scores.write_text(json.dumps(row) + "\n")
    assert dg.diagnose([row])["material_places"] == ["A"]
    vd.write_accepted(scores, [vd.Verdict("A", "neighborhood_amenities", vd.CONSISTENT, "ZIP 1: only 3 establishments")])
    accepted = dg.load_accepted(scores)
    assert dg.diagnose([row], accepted=accepted)["material_places"] == []
    vd.write_accepted(scores, [vd.Verdict("A", "neighborhood_amenities", vd.CONTRADICTED, "ZIP 1: 171 establishments")])
    assert dg.diagnose([row], accepted=dg.load_accepted(scores))["material_places"] == ["A"]


def test_validate_end_to_end_with_fake_sources():
    bd = {"business_list": [], "diagnostics": {}}
    row = _row("Lakeway", 30.36, -97.98)
    row["score"]["livability_pillars"] = {
        "neighborhood_amenities": {"score": None, "status": "no_data", "breakdown": bd, "failure_reason": "osm_data_gap (x)"},
        "public_transit_access": {"score": 17, "summary": {"fallback_applied": True, "fallback_reason": "Transitland API unavailable", "total_routes": 0}},
    }
    v = vd.validate([row], estab_fn=lambda z: 171, share_fn=lambda z: 0.003, log=lambda s: None)
    by = {x.pillar: x.kind for x in v}
    assert by["neighborhood_amenities"] == vd.CONTRADICTED and by["public_transit_access"] == vd.CONSISTENT
