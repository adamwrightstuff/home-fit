from scripts.catalog.rerun_failed_catalog_pillars import recompute_totals
from scripts.metro_agent import reweight as rw


def _score():
    return {"livability_pillars": {k: {"score": 70.0, "status": "success", "weight": 9.09} for k in rw.BASE}}


def test_recompute_totals_sums_to_100():
    s = _score()
    recompute_totals(s)
    assert abs(sum(p["weight"] for p in s["livability_pillars"].values()) - 100) < 0.01
    assert abs(s["total_score"] - 70.0) < 0.05


def test_plan_detects_bad_sum():
    assert rw.plan([{"success": True, "score": _score()}]) == [0]
