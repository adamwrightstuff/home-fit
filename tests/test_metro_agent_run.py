from pathlib import Path

from scripts.metro_agent import preflight as pf
from scripts.metro_agent import run as rn

OUT = Path(rn.REPO / "data" / "x_out.jsonl")


class Recorder:
    def __init__(self, preflight_status=pf.PASS, failed_seq=(0,), material=0):
        self.calls = []
        self.preflight_status = preflight_status
        self.failed_seq = list(failed_seq)
        self.material = material

    def server(self, base, log):
        self.calls.append("server"); return None

    def preflight(self, metro, csv, base, out):
        self.calls.append("preflight"); return [pf.Check("x", self.preflight_status, "d")]

    def score(self, metro, csv, out, base):
        self.calls.append("score"); return 0

    def failed(self, path):
        return self.failed_seq.pop(0) if len(self.failed_seq) > 1 else self.failed_seq[0]

    def resolve(self, path, base, max_rounds=3):
        self.calls.append("resolve")
        return {"stopped": "nothing_actionable", "rounds": 0, "api_calls": 0, "material_places_left": self.material,
                "needs_data_source": [], "needs_human_check": [], "still_failing_after_retries": []}

    def publish(self, metro, out):
        self.calls.append("publish")


def _go(rec, tmp_path, monkeypatch, **kw):
    import json
    out = tmp_path / "scores.jsonl"
    out.write_text(json.dumps({"catalog": {"name": "A"}, "success": True, "score": {"livability_pillars": {}}}) + "\n")
    monkeypatch.setattr(rn.rs, "format_summary", lambda s: "")
    return rn.run_pipeline("x", api_base="http://127.0.0.1:8000", csv_path=tmp_path / "x.csv", out_path=out,
                           log=lambda s: None, server_fn=rec.server, preflight_fn=rec.preflight, score_fn=rec.score,
                           resolve_fn=rec.resolve, publish_fn=rec.publish, failed_fn=rec.failed, **kw), out


def test_preflight_failure_stops_before_any_scoring(tmp_path, monkeypatch):
    rec = Recorder(preflight_status=pf.FAIL)
    rc, _ = _go(rec, tmp_path, monkeypatch)
    assert rc == 2 and rec.calls == ["server", "preflight"]


def test_clean_run_goes_through_every_stage_in_order(tmp_path, monkeypatch):
    rec = Recorder()
    rc, _ = _go(rec, tmp_path, monkeypatch, push=True)
    assert rc == 0 and rec.calls == ["server", "preflight", "score", "resolve", "publish"]


def test_blocked_gate_never_publishes(tmp_path, monkeypatch):
    import scripts.metro_agent.run as r
    monkeypatch.setattr(r.dg, "diagnose", lambda rows, **kw: {"material_places": ["A"], "findings": [], "systemic": [], "places": 1, "clean": 0, "counts": {}})
    monkeypatch.setattr(r.dg, "format_report", lambda *a, **k: "")
    rec = Recorder(material=1)
    rc, _ = _go(rec, tmp_path, monkeypatch, push=True)
    assert rc == 1 and "publish" not in rec.calls


def test_failed_places_trigger_one_extra_scoring_pass(tmp_path, monkeypatch):
    rec = Recorder(failed_seq=[3, 0])
    rc, _ = _go(rec, tmp_path, monkeypatch)
    assert rec.calls.count("score") == 2 and rc == 0


def test_places_that_never_score_stop_the_run(tmp_path, monkeypatch):
    rec = Recorder(failed_seq=[3])
    rc, _ = _go(rec, tmp_path, monkeypatch)
    assert rc == 3 and "resolve" not in rec.calls


def test_changed_pin_drops_the_scored_row_so_it_is_rescored(tmp_path):
    import json
    csv_path = tmp_path / "x.csv"
    csv_path.write_text("name,county_borough,state_abbr,search_query,lat,lon\nA,K,TX,A,30.1111,-97.3182\nB,K,TX,B,30.0,-97.0\n")
    out = tmp_path / "o.jsonl"
    def row(n, la, lo):
        return json.dumps({"catalog": {"name": n, "county_borough": "K", "state_abbr": "TX", "lat": str(la), "lon": str(lo)}, "success": True}) + "\n"
    out.write_text(row("A", 30.0541, -97.3888) + row("B", 30.0, -97.0))
    assert rn.drop_stale_pins(csv_path, out, log=lambda s: None) == 1
    assert [json.loads(l)["catalog"]["name"] for l in out.read_text().splitlines()] == ["B"]
