from scripts.metro_agent import changes as ch


def _row(name, hc, ss):
    return {"catalog": {"name": name, "county_borough": "C", "state_abbr": "NY"},
            "score": {"status_signal": ss, "livability_pillars": {"healthcare_access": {"score": hc}}}}


def test_compare_reports_pillar_changes_and_big_composite_moves():
    old = {("A", "C", "NY"): _row("A", 50.0, 60.0), ("B", "C", "NY"): _row("B", 70.0, 60.0)}
    new = {("A", "C", "NY"): _row("A", 55.0, 72.0), ("B", "C", "NY"): _row("B", 70.0, 60.5)}
    r = ch.compare(old, new)
    assert r["places_changed"] == 1 and r["pillar_changes"] == {"healthcare_access": 1}
    assert r["big_moves"][0][1:3] == ("A", "status_signal")
