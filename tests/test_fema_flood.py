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
    pts = {t: F._flood_risk_to_points(t, 30.0) for t in ("floodway", "sfha", "x_500yr", "d", "minimal")}
    assert pts == {"floodway": 0.0, "sfha": 4.5, "x_500yr": 16.5, "d": 13.5, "minimal": 30.0}


def test_worst_zone_wins_when_several_overlap():
    r = F.flood_zone_from_features([_z("X", "AREA OF MINIMAL FLOOD HAZARD"), _z("AE", None, "T")])
    assert r["risk_tier"] == "sfha" and r["flood_zone_pts"] == 4.5 and r["fld_zone"] == "AE"


def test_no_polygon_is_full_points_and_a_failed_request_is_none():
    assert F.flood_zone_from_features([])["flood_zone_pts"] == 30.0
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


def test_offline_recompute_uses_neutral_points_for_a_failed_lookup():
    p = _place()
    _mod.recompute_place(p, None)
    cr = p["livability_pillars"]["climate_risk"]
    assert cr["breakdown"]["flood_zone_pts"] == 15.0 and cr["summary"]["flood_risk_tier"] is None


def test_offline_recompute_skips_places_without_stored_points():
    p = _place()
    del p["livability_pillars"]["climate_risk"]["breakdown"]["heat_exposure_pts"]
    assert _mod.recompute_place(p, []) is None
