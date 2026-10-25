"""Launch check: gates, contrasts, degenerate metros. Runs on synthetic catalog files; no network."""
import ast
import importlib.util
import json
import random
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("launch_check", ROOT / "scripts" / "qa" / "launch_check.py")
lc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lc)


def _row(name, healthcare, area="suburban", leaf=None):
    pillars = {"healthcare_access": {"score": healthcare, "status": "success", "data_quality": {}, "area_classification": {"area_type": area},
                                     "breakdown": {"x": leaf if leaf is not None else healthcare}, "summary": {}}}
    return {"catalog": {"name": name, "state_abbr": "NY"}, "score": {"livability_pillars": pillars}}


def _write(tmp_path, metro, rows):
    f = tmp_path / f"{metro}_metro_place_catalog_scores_merged.composites_recomputed.jsonl"
    f.write_text("\n".join(json.dumps(r) for r in rows))
    return str(tmp_path / "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl")


def test_no_network_imports():
    tree = ast.parse((ROOT / "scripts" / "qa" / "launch_check.py").read_text())
    mods = {n.names[0].name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import)} | \
           {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert not mods & {"requests", "urllib", "http", "socket"}


def test_extreme_share_fails_and_modal_share_warns(tmp_path):
    rng = random.Random(1)
    clumped = [_row(f"p{i}", 100.0 if i < 30 else rng.uniform(20, 99)) for i in range(100)]   # 30% at max
    g = _write(tmp_path, "a", clumped)
    places = lc.load_places([str(next(tmp_path.glob("*.jsonl")))])
    gates = lc.gate_stats(lc.pillar_stats(places, "healthcare_access"))
    assert ("FAIL", ) == tuple({l for l, _ in gates if l == "FAIL"})
    mild = [_row(f"p{i}", 50.0 if i < 20 else rng.uniform(10, 95)) for i in range(100)]          # 20% in one value, 20% at no extreme
    for f in tmp_path.glob("*.jsonl"):
        f.unlink()
    _write(tmp_path, "a", mild)
    gates = lc.gate_stats(lc.pillar_stats(lc.load_places([str(next(tmp_path.glob("*.jsonl")))]), "healthcare_access"))
    assert [l for l, _ in gates] == ["WARN"]


def test_low_spread_warns(tmp_path):
    rows = [_row(f"p{i}", 60.0 + (i % 3)) for i in range(60)]
    _write(tmp_path, "a", rows)
    gates = lc.gate_stats(lc.pillar_stats(lc.load_places([str(next(tmp_path.glob("*.jsonl")))]), "healthcare_access"))
    assert any("below" in m for _, m in gates)


def test_contrast_pass_warn_fail_and_too_few(tmp_path):
    rng = random.Random(2)
    rows = [_row(f"u{i}", 90 + rng.uniform(-3, 3), "urban_core") for i in range(15)] + [_row(f"r{i}", 50 + rng.uniform(-3, 3), "rural") for i in range(15)]
    _write(tmp_path, "a", rows)
    places = lc.load_places([str(next(tmp_path.glob("*.jsonl")))])
    base = {"pillar": "healthcare_access", "group_a": {"area_type": "urban_core"}, "group_b": {"area_type": "rural"}, "reason": "r"}
    res = lc.evaluate_contrasts(places, [
        {**base, "expected": "a_higher", "min_gap": 10},
        {**base, "expected": "a_higher", "min_gap": 60},
        {**base, "expected": "b_higher", "min_gap": 10},
        {**base, "group_a": {"places": ["a|u1"]}, "expected": "a_higher", "min_gap": 10},
    ])
    assert [r["level"] for r in res] == ["PASS", "WARN", "FAIL", "WARN"]


def test_degenerate_metro_is_flagged_only_when_the_rest_of_the_catalog_varies(tmp_path):
    rng = random.Random(3)
    # metro a: sub-metric always 0; metro b: varies; leaf comes from breakdown.x
    _write(tmp_path, "a", [_row(f"a{i}", rng.uniform(10, 90), leaf=0.0) for i in range(20)])
    _write(tmp_path, "b", [_row(f"b{i}", rng.uniform(10, 90), leaf=rng.uniform(1, 9)) for i in range(20)])
    places = lc.load_places(sorted(str(f) for f in tmp_path.glob("*.jsonl")))
    found = lc.degenerate_metros(places)
    assert any(d["metro"] == "a" and d["path"] == "breakdown.x" for d in found)
    assert not any(d["metro"] == "b" for d in found)
    allowed = [{"pillar": "healthcare_access", "path_prefix": "breakdown.", "reason": "by design"}]
    assert all(lc.is_expected_uniform(d, allowed) for d in found)


def test_degenerate_not_flagged_when_every_metro_is_constant(tmp_path):
    _write(tmp_path, "a", [_row(f"a{i}", 50.0 + i, leaf=1.0) for i in range(20)])
    _write(tmp_path, "b", [_row(f"b{i}", 50.0 + i, leaf=1.0) for i in range(20)])
    places = lc.load_places(sorted(str(f) for f in tmp_path.glob("*.jsonl")))
    assert lc.degenerate_metros(places) == []


def test_run_returns_report_and_exit_counts(tmp_path):
    rng = random.Random(4)
    g = _write(tmp_path, "a", [_row(f"p{i}", 100.0 if i < 40 else rng.uniform(20, 99)) for i in range(100)])
    report, fails, warns = lc.run(g, tmp_path / "none.json")
    assert fails >= 1 and "healthcare_access" in report and "None defined" in report
