from scripts.catalog.check_education import evaluate
from pillars.schools import score_from_ratings, split_scores


def _row(name, ratings, charters=(), weight=7.69, with_split=True, early=0.0, score=None):
    rs = [{"name": f"S{i}", "level": "elementary", "rating": r, "is_charter_school": i in charters}
          for i, r in enumerate(ratings)]
    total = round(score_from_ratings([float(r) for r in ratings], early)["score"], 2) if score is None else score
    b = {"early_ed_bonus": early, "rated_schools": rs}
    if with_split:
        b["split"] = split_scores(rs, early)
    return {"success": True, "catalog": {"name": name, "lat": "40.0", "lon": "-73.0"},
            "score": {"location_info": {"state": "New York"},
                      "livability_pillars": {
                          "quality_education": {"score": total, "confidence": 85, "weight": weight, "breakdown": b},
                          "housing_value": {"score": 50, "weight": 7.69}}}}


def _kinds(rep, key="failures"):
    return {f["check"] for f in rep[key]}


def test_clean_place_passes():
    rep = evaluate([_row("A", [80, 60, 100, 80])], "x", exceptions={}, use_district_checks=False)
    assert rep["verdict"] == "PASS" and not rep["failures"]


def test_zero_weight_split_missing_and_mismatch_fail():
    assert "weight_zero" in _kinds(evaluate([_row("A", [80, 60, 100], weight=0)], "x", {}, False))
    assert "no_split" in _kinds(evaluate([_row("A", [80, 60, 100], with_split=False)], "x", {}, False))
    assert "formula_mismatch" in _kinds(evaluate([_row("A", [80, 60, 100], score=10.0)], "x", {}, False))


def test_exception_is_not_a_failure():
    row = _row("A", [80, 60, 100])
    row["score"]["livability_pillars"]["quality_education"]["score"] = None
    rep = evaluate([row], "x", exceptions={"x:A": "accepted gap"}, use_district_checks=False)
    assert rep["verdict"] == "PASS" and rep["exceptions"][0]["reason"] == "accepted gap"


def test_thin_without_district_files_is_only_a_warning():
    rep = evaluate([_row("A", [80, 60])], "x", exceptions={}, use_district_checks=False)
    assert rep["verdict"] == "PASS" and "thin_unverified" in _kinds(rep, "warnings")
