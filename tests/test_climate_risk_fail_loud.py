"""Climate risk fails loudly: missing components are no data, never a neutral or invented value."""
import pytest

import pillars.climate_risk as cr

HEAT = {"local_lst_c": 36.0, "land_pixel_fraction": 1.0}
AIR = {"pm25_proxy_ugm3": 0.0, "aer_ai_mean": -0.3}
FLOOD = {"flood_zone_pts": 30.0, "risk_tier": "minimal", "fld_zone": "X", "label": "AREA OF MINIMAL FLOOD HAZARD"}
TREND = {"trend_c_per_decade": 0.25}


def _run(monkeypatch, heat=HEAT, air=AIR, flood=FLOOD, trend=TREND):
    monkeypatch.setattr(cr, "get_heat_exposure_lst", lambda *a, **k: heat)
    monkeypatch.setattr(cr, "get_air_quality_aer_ai", lambda *a, **k: air)
    monkeypatch.setattr(cr, "get_fema_flood_zone", lambda *a, **k: flood)
    monkeypatch.setattr(cr, "get_climate_trend_terraclimate", lambda *a, **k: trend)
    monkeypatch.setattr(cr, "detect_area_type", lambda *a, **k: "suburban")
    return cr.get_climate_risk_score(40.0, -74.0, area_type="suburban", density=3000.0)


def test_all_components_present_matches_the_plain_sum(monkeypatch):
    score, d = _run(monkeypatch)
    b = d["breakdown"]
    assert score == round(b["heat_exposure_pts"] + b["air_quality_pts"] + b["flood_zone_pts"] + b["climate_trend_pts"], 1)
    assert d["summary"]["components_missing"] == []


def test_failed_flood_lookup_is_no_data_not_neutral(monkeypatch):
    score, d = _run(monkeypatch, flood=None)
    assert d["breakdown"]["flood_zone_pts"] is None
    assert d["summary"]["components_missing"] == ["flood"]
    assert d["data_quality"]["degraded"] is True
    b = d["breakdown"]
    assert score == round((b["heat_exposure_pts"] + b["air_quality_pts"] + b["climate_trend_pts"]) / 70.0 * 100.0, 1)


def test_mostly_water_buffer_is_no_heat_data(monkeypatch):
    score, d = _run(monkeypatch, heat={"local_lst_c": 31.0, "land_pixel_fraction": 0.1})
    assert d["breakdown"]["heat_exposure_pts"] is None


def test_missing_air_key_is_no_data_not_worst_case(monkeypatch):
    score, d = _run(monkeypatch, air={"aer_ai_mean": 0.1})
    assert d["breakdown"]["air_quality_pts"] is None


def test_fewer_than_three_components_raises(monkeypatch):
    with pytest.raises(RuntimeError):
        _run(monkeypatch, flood=None, trend=None)
    with pytest.raises(RuntimeError):
        _run(monkeypatch, heat=None, air=None, flood=None, trend=None)
