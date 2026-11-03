"""FEMA flood tiers and the offline climate_risk flood recompute."""

import importlib.util
import os

import pytest

from data_sources import fema_flood as F

_spec = importlib.util.spec_from_file_location(
    "recompute_flood", os.path.join(os.path.dirname(__file__), "..", "scripts", "catalog", "recompute_flood_offline.py")
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)


def _z(zone, sub=None, sfha="F"):
    return {"FLD_ZONE": zone, "ZONE_SUBTY": sub, "SFHA_TF": sfha}


def test_unshaded_x_is_minimal_not_moderate():
    assert F._classify_zone("X", "F", "AREA OF MINIMAL FLOOD HAZARD") == "minimal"
    assert F._classify_zone("X", "F", None) == "minimal"


def test_shaded_and_levee_x_are_moderate():
    assert F._classify_zone("X", "F", "0.2 PCT ANNUAL CHANCE FLOOD HAZARD") == "x_500yr"
    assert F._classify_zone("X", "F", "AREA WITH REDUCED FLOOD RISK DUE TO LEVEE") == "x_500yr"


def test_special_flood_hazard_floodway_and_undetermined():
    assert F._classify_zone("AE", "T", None) == "sfha"
    assert F._classify_zone("VE", "T", "COASTAL FLOODPLAIN") == "sfha"
    assert F._classify_zone("AE", "T", "FLOODWAY") == "floodway"
    assert F._classify_zone("D", None, None) == "d"


def test_points_follow_the_tiers():
    pts = {t: F._flood_risk_to_points(t, 30.0) for t in ("floodway", "sfha", "x_500yr", "d", "unmapped", "minimal")}
    assert pts == {"floodway": 0.0, "sfha": 4.5, "x_500yr": pytest.approx(24.9), "d": None, "unmapped": None, "minimal": 30.0}


def test_shaded_x_loss_is_the_annual_chance_ratio_of_the_sfha_loss():
    lost_sfha = 30.0 - F._flood_risk_to_points("sfha", 30.0)
    lost_x500 = 30.0 - F._flood_risk_to_points("x_500yr", 30.0)
    assert lost_x500 == pytest.approx(lost_sfha * 0.2)


def test_worst_zone_wins_when_several_overlap():
    r = F.flood_zone_from_features([_z("X", "AREA OF MINIMAL FLOOD HAZARD"), _z("AE", None, "T")])
    assert r["risk_tier"] == "sfha" and r["flood_zone_pts"] == 4.5 and r["fld_zone"] == "AE"


def test_no_polygon_and_zone_d_are_no_data_and_a_failed_request_is_none():
    r = F.flood_zone_from_features([])
    assert r["flood_zone_pts"] is None and r["risk_tier"] == "unmapped"
    d = F.flood_zone_from_features([_z("D")])
    assert d["flood_zone_pts"] is None and d["risk_tier"] == "d"
    assert F.flood_zone_from_features(None) is None


def _place(score=70.3):
    return {"livability_pillars": {"climate_risk": {
        "score": score, "weight": 7.6923076923, "contribution": 0,
        "breakdown": {"heat_exposure_pts": 9.92, "air_quality_pts": 20.0, "flood_zone_pts": 30.0, "climate_trend_pts": 10.35,
                      "flood_zone_score_0_100": 100.0},
        "summary": {"flood_risk_tier": "minimal"}}}}


def test_offline_recompute_replaces_only_the_flood_points():
    p = _place()
    info = _mod.recompute_place(p, [_z("AE", "COASTAL FLOODPLAIN", "T")])
    cr = p["livability_pillars"]["climate_risk"]
    assert cr["breakdown"]["flood_zone_pts"] == 4.5 and cr["breakdown"]["flood_zone_score_0_100"] == 15.0
    assert cr["score"] == round(9.92 + 20.0 + 4.5 + 10.35, 1) == info["after"]
    assert cr["contribution"] == pytest.approx(7.6923076923 * cr["score"] / 100, abs=1e-4)
    assert cr["summary"]["flood_risk_tier"] == "sfha" and cr["summary"]["fld_zone"] == "AE"


def test_offline_recompute_failed_request_is_no_data_not_stored_neutral():
    p = _place()
    p["livability_pillars"]["climate_risk"]["breakdown"]["flood_zone_pts"] = 15.0
    info = _mod.recompute_place(p, None, request_failed=True)
    cr = p["livability_pillars"]["climate_risk"]
    assert cr["breakdown"]["flood_zone_pts"] is None and cr["summary"]["components_missing"] == ["flood"]
    assert cr["score"] == round((9.92 + 20.0 + 10.35) / 70.0 * 100.0, 1) == info["after"]
    assert cr["data_quality"]["degraded"] is True
    assert "flood_lookup_failed" in cr["data_quality"]["degraded_reasons"]


def test_offline_recompute_zone_d_and_unmapped_scale_over_the_rest():
    for feats, reason in (([_z("D")], "flood_zone_d_undetermined"), ([], "flood_no_mapped_polygon")):
        p = _place()
        _mod.recompute_place(p, feats)
        cr = p["livability_pillars"]["climate_risk"]
        assert cr["breakdown"]["flood_zone_pts"] is None
        assert reason in cr["data_quality"]["degraded_reasons"]
        assert cr["score"] == round((9.92 + 20.0 + 10.35) / 70.0 * 100.0, 1)


def test_offline_recompute_shaded_x_keeps_83_percent():
    p = _place()
    _mod.recompute_place(p, [_z("X", "0.2 PCT ANNUAL CHANCE FLOOD HAZARD")])
    assert p["livability_pillars"]["climate_risk"]["breakdown"]["flood_zone_pts"] == 24.9


def test_offline_recompute_skips_places_without_stored_points():
    p = _place()
    bd = p["livability_pillars"]["climate_risk"]["breakdown"]
    del bd["heat_exposure_pts"]
    del bd["air_quality_pts"]
    assert _mod.recompute_place(p, [_z("AE", None, "T")]) is None  # two of four components absent: fewer than three
