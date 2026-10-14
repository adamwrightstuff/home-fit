import json

from scripts.metro_agent import diagnose as dg
from scripts.metro_agent import withhold as wh


def _row(name, hc):
    return {"success": True, "catalog": {"name": name, "state_abbr": "CA", "lat": 1, "lon": 2},
            "score": {"livability_pillars": {"healthcare_access": hc}}}


BAD = {"score": 33.2, "weight": 9.0, "data_quality": {"data_warning": "api_error", "completeness": 0.0},
       "summary": {"nearest_hospital_km": 20}}
GOOD = {"score": 80.0, "data_quality": {"completeness": 1.0}, "summary": {"hospital_count": 2, "clinic_count": 5}}


def test_withhold_blanks_only_failed_pillars_and_keeps_them_on_the_retry_list(tmp_path):
    p = tmp_path / "m.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in (_row("A", BAD), _row("B", GOOD))))
    n = wh.withhold(p, log=lambda s: None, recompute=lambda path: None)
    rows = dg.load_rows(p)
    assert n == 1
    assert rows[0]["score"]["livability_pillars"]["healthcare_access"]["score"] is None
    assert rows[1]["score"]["livability_pillars"]["healthcare_access"]["score"] == 80.0
    res = dg.diagnose(rows)
    assert res["material_places"] == []  # no longer a publish blocker
    f = [x for x in res["findings"] if x["place"] == "A"][0]
    assert f["remedy"] == dg.RETRY and f["evidence"].startswith("withheld")


def test_dry_run_changes_nothing(tmp_path):
    p = tmp_path / "m.jsonl"
    body = json.dumps(_row("A", BAD)) + "\n"
    p.write_text(body)
    assert wh.withhold(p, dry_run=True, log=lambda s: None) == 1
    assert p.read_text() == body
