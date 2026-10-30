"""Natural beauty fails loudly (design principles v2, P9): missing water, canopy, green view or terrain is
reported as degraded or no data, never scored as a neutral or zero value."""

import pytest

from pillars import natural_beauty as NB


def tree(**over):
    t = {
        "green_view_index": 30.0,
        "green_view_details": {"method": "semantic_gvi"},
        "weighted_canopy_pct": 20.0,
        "water_read_status": "measured",
        "natural_context": {
            "component_scores": {"topography_raw": 5.0},
            "debug_breakdown": {"water_proximity_type": "lake", "water_proximity_nearest_km": 2.0},
        },
    }
    t.update(over)
    return t


def run(t):
    return NB._apply_v9_formula({}, t, lat=40.0, lon=-75.0)


def test_complete_data_is_not_degraded():
    score, b = run(tree())
    assert b["degraded_reasons"] is None and b["low_confidence"] is None
    assert b["water_score"] is not None and b["topo_score"] is not None


def test_failed_water_read_is_not_scored_and_scenery_uses_terrain_alone():
    t = tree(water_read_status="unavailable")
    t["natural_context"]["debug_breakdown"] = {}
    score, b = run(t)
    assert b["water_score"] is None and b["water_status"] == "unavailable"
    assert b["scenery_score"] == pytest.approx(b["topo_score"], abs=0.01)
    assert any(r.startswith("water_read_unavailable") for r in b["degraded_reasons"])


def test_water_score_function_has_no_neutral_default():
    assert NB._v9_score_water(None, None, "unavailable") is None
    assert NB._v9_score_water(None, "lake", "measured") is None
    assert NB._v9_score_water(1.0, None, "measured") is None


def test_empty_water_read_takes_the_curve_floor_and_is_not_degraded():
    t = tree(water_read_status="none_within_15km")
    t["natural_context"]["debug_breakdown"] = {}
    score, b = run(t)
    assert b["water_score"] == 3.0 and b["water_status"] == "none_within_15km"
    assert b["degraded_reasons"] is None


def test_missing_water_status_is_treated_as_a_failed_read():
    t = tree()
    del t["water_read_status"]
    t["natural_context"]["debug_breakdown"] = {}
    assert run(t)[1]["water_score"] is None


def test_low_measured_green_view_is_used_as_measured_not_replaced_by_canopy():
    score, b = run(tree(green_view_index=1.2, weighted_canopy_pct=35.0))
    assert b["inputs"]["gvi_pct"] == pytest.approx(1.2)
    assert b["inputs"]["gvi_source"] == "measured"


def test_missing_canopy_is_none_not_zero_and_flagged():
    score, b = run(tree(weighted_canopy_pct=None))
    assert b["canopy_score"] is None and b["inputs"]["canopy_pct"] is None
    assert any(r.startswith("canopy_unavailable") for r in b["degraded_reasons"])
    assert b["streets_score"] == pytest.approx(b["gvi_score"], abs=0.01)


def test_composite_green_view_is_labeled_and_flagged():
    score, b = run(tree(green_view_details={"method": "composite"}))
    assert b["inputs"]["gvi_source"].startswith("composite_fallback")
    assert any(r.startswith("green_view_fallback") for r in b["degraded_reasons"])


def test_no_streets_measurement_is_no_data():
    t = tree(weighted_canopy_pct=None, green_view_index=None)
    with pytest.raises(NB.NaturalBeautyNoData, match="streets"):
        run(t)
    t = tree(weighted_canopy_pct=None, green_view_details={"method": "composite"})
    with pytest.raises(NB.NaturalBeautyNoData, match="streets"):
        run(t)


def test_no_scenery_measurement_is_no_data():
    t = tree(water_read_status="unavailable")
    t["natural_context"] = {"component_scores": {}, "debug_breakdown": {}}
    with pytest.raises(NB.NaturalBeautyNoData, match="scenery"):
        run(t)


def test_missing_terrain_alone_is_degraded_and_scores_from_water():
    t = tree()
    t["natural_context"]["component_scores"] = {}
    score, b = run(t)
    assert b["topo_score"] is None and b["scenery_score"] == pytest.approx(b["water_score"], abs=0.01)
    assert any(r.startswith("topography_unavailable") for r in b["degraded_reasons"])


def test_a_real_zero_green_view_is_still_scored():
    score, b = run(tree(green_view_index=0.0, weighted_canopy_pct=0.0))
    assert b["gvi_score"] == 0.0 and b["canopy_score"] == 0.0 and b["streets_score"] == 0.0


def test_main_does_not_fall_back_to_v7_when_there_is_no_data():
    import main
    t = tree(weighted_canopy_pct=None, green_view_index=None)
    with pytest.raises(NB.NaturalBeautyNoData):
        main._apply_v9_to_natural({"details": t}, 55.0, {}, 40.0, -75.0)


def test_main_records_degraded_reasons_in_data_quality():
    import main
    t = tree(water_read_status="unavailable")
    t["natural_context"]["debug_breakdown"] = {}
    score, details = main._apply_v9_to_natural({"details": t}, 55.0, {}, 40.0, -75.0)
    dq = details["data_quality"]
    assert dq["degraded"] is True and any("water_read_unavailable" in r for r in dq["degraded_reasons"])


def test_degraded_reason_survives_the_response_data_quality_summary():
    import main
    t = tree(water_read_status="unavailable")
    t["natural_context"]["debug_breakdown"] = {}
    score, details = main._apply_v9_to_natural({"details": t}, 55.0, {}, 40.0, -75.0)
    pillars = {"natural_beauty": {"score": score, "details": details, "data_quality": details["data_quality"]}}
    summary = main._calculate_data_quality_summary(pillars, "suburban")
    dq = pillars["natural_beauty"]["data_quality"]
    assert dq["degraded"] is True and any("water_read_unavailable" in r for r in dq["degraded_reasons"])
    assert summary["degraded"] is True and "natural_beauty" in summary["per_pillar_degraded"]


def test_complete_data_is_still_not_degraded_after_the_summary():
    import main
    score, details = main._apply_v9_to_natural({"details": tree()}, 55.0, {}, 40.0, -75.0)
    pillars = {"natural_beauty": {"score": score, "details": details, "data_quality": details.get("data_quality") or {}}}
    main._calculate_data_quality_summary(pillars, "suburban")
    assert pillars["natural_beauty"]["data_quality"]["degraded"] is False


def _feats(*items):
    return {"water_features": [{"type": t, "distance_km": d, "area_km2": a} for t, d, a in items]}


def test_water_by_type_takes_the_nearest_of_each_type_and_skips_ponds_and_far_streams():
    by = NB._water_by_type(_feats(("river", 0.4, 0.0), ("bay", 1.0, 5.0), ("lake", 3.0, 0.001), ("stream", 2.0, 0.0), ("lake", 5.0, 1.0)))
    assert by == {"river": 0.4, "ocean": 1.0, "lake": 5.0}


def test_best_type_water_lets_a_bay_beat_a_nearer_river():
    s, t, d = NB._v9_score_water_best_type({"river": 0.41, "ocean": 1.0})
    assert t == "ocean" and s == pytest.approx(100 * 2.718281828 ** -0.2, abs=0.1) and d == 1.0
    assert NB._v9_score_water_best_type(None) is None


def test_best_type_is_reported_but_not_used_while_the_flag_is_off():
    t = tree()
    t["natural_context"]["debug_breakdown"] = {"water_proximity_type": "river", "water_proximity_nearest_km": 0.41,
                                               "water_by_type": {"river": 0.41, "ocean": 1.0}}
    score, b = run(t)
    assert b["water_score_best_type"] > b["water_score"] and b["inputs"]["water_type"] == "river"


def test_data_limits_are_returned_in_data_quality():
    import main
    score, details = main._apply_v9_to_natural({"details": tree()}, 55.0, {}, 40.0, -75.0)
    lim = details["data_quality"]["data_limits"]
    assert len(lim) == 4 and any("regional medians" in x for x in lim) and any("degraded_reasons" in x for x in lim)
