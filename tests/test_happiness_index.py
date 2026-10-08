"""Offline tests for the v5 happiness index weights (no network, no pillar imports)."""

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "happiness_index_under_test", Path(__file__).resolve().parents[1] / "pillars" / "happiness_index.py"
)
hi = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hi)


def _pillar(score):
    return {"score": score}


def _all(score=50.0):
    return dict(
        housing_details=_pillar(score),
        public_transit_details={"breakdown": {"commute_time": score}},
        economic_opportunity_details=_pillar(score),
        natural_beauty_details=_pillar(score),
        state_abbrev="NY",
        social_fabric_details=_pillar(score),
        community_safety_details={"status": "success", "score": score},
        neighborhood_amenities_details=_pillar(score),
        education_details=_pillar(score),
        climate_risk_details=_pillar(score),
        active_outdoors_details=_pillar(score),
    )


def test_weights_sum_to_one():
    total = (hi.W_SOCIAL + hi.W_SAFETY + hi.W_HOME + hi.W_GREEN + hi.W_ECONOMIC + hi.W_ACTIVE
             + hi.W_CLIMATE + hi.W_COMMUTE + hi.W_NEIGHBORHOOD + hi.W_EDUCATION)
    assert abs(total - 1.0) < 1e-9


def test_uniform_scores_give_same_index_and_education_has_no_weight():
    score, bd = hi.compute_happiness_index_with_breakdown(**_all(70.0))
    assert score == 70.0
    assert "education" not in bd["component_weights"]
    assert bd["education"] == 70.0  # still reported for display
    assert abs(sum(bd["component_weights"].values()) - 1.0) < 0.01


def test_education_does_not_move_the_score():
    a, _ = hi.compute_happiness_index_with_breakdown(**{**_all(60.0), "education_details": _pillar(0.0)})
    b, _ = hi.compute_happiness_index_with_breakdown(**{**_all(60.0), "education_details": _pillar(100.0)})
    assert a == b


def test_economic_is_a_component_not_a_social_modifier():
    lo, bd_lo = hi.compute_happiness_index_with_breakdown(**{**_all(60.0), "economic_opportunity_details": _pillar(0.0)})
    hi_, bd_hi = hi.compute_happiness_index_with_breakdown(**{**_all(60.0), "economic_opportunity_details": _pillar(100.0)})
    assert bd_lo["social"] == bd_hi["social"] == 60.0
    assert abs((hi_ - lo) - 100.0 * hi.W_ECONOMIC) < 0.2


def test_missing_components_renormalize():
    kwargs = _all(80.0)
    kwargs["community_safety_details"] = {"status": "degraded", "score": 0}
    kwargs["climate_risk_details"] = None
    score, bd = hi.compute_happiness_index_with_breakdown(**kwargs)
    assert score == 80.0
    assert "safety" not in bd["component_weights"] and "climate" not in bd["component_weights"]
    assert abs(sum(bd["component_weights"].values()) - 1.0) < 0.01


def test_no_components_returns_none():
    score, bd = hi.compute_happiness_index_with_breakdown(None, None, None, None, None)
    assert score is None and bd["component_weights"] == {}


def test_failed_pillar_stored_as_zero_is_missing_data_not_a_zero():
    kwargs = _all(80.0)
    kwargs["natural_beauty_details"] = {"score": 0.0, "confidence": 0, "status": "failed"}
    kwargs["social_fabric_details"] = {"score": 0.0, "confidence": 0, "status": "failed"}
    score, bd = hi.compute_happiness_index_with_breakdown(**kwargs)
    assert score == 80.0
    assert bd["green"] is None and bd["social"] is None
    assert "green" not in bd["component_weights"] and "social" not in bd["component_weights"]
