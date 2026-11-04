"""Heat plausibility screen: a surface reading far below the normal summer air temperature is no data. No Earth Engine reads."""
import pytest

import pillars.climate_risk as cr
from data_sources.heat_screen import HEAT_MAX_BELOW_AIR_C, lst_implausible_vs_air

AIR = {"pm25_ugm3": 8.0, "years": [2021, 2022], "source": "cdc_tracking_epa_downscaler"}
FLOOD = {"flood_zone_pts": 30.0, "risk_tier": "minimal", "fld_zone": "X", "label": "AREA OF MINIMAL FLOOD HAZARD"}
TREND = {"trend_c_per_decade": 0.25}


def _run(monkeypatch, lst, air_ref):
    monkeypatch.setattr(cr, "get_heat_exposure_lst", lambda *a, **k: {"local_lst_c": lst, "land_pixel_fraction": 1.0})
    monkeypatch.setattr(cr, "get_air_quality_pm25", lambda *a, **k: AIR)
    monkeypatch.setattr(cr, "get_fema_flood_zone", lambda *a, **k: FLOOD)
    monkeypatch.setattr(cr, "get_climate_trend_terraclimate", lambda *a, **k: TREND)
    monkeypatch.setattr(cr, "get_jja_tmax_normal_terraclimate", lambda *a, **k: None if air_ref is None else {"jja_tmax_c": air_ref})
    return cr.get_climate_risk_score(29.5, -98.5, area_type="suburban", density=3000.0)


def test_helper_margin_and_unknowns():
    assert lst_implausible_vs_air(20.7, 34.7) is True       # Alamo Heights TX: 14 C below the air normal
    assert lst_implausible_vs_air(24.8, 34.7) is False      # 9.9 C below: passes
    assert lst_implausible_vs_air(24.6, 34.7) is True
    assert lst_implausible_vs_air(None, 34.7) is False and lst_implausible_vs_air(20.0, None) is False
    assert HEAT_MAX_BELOW_AIR_C == 10.0


def test_implausible_reading_drops_heat_and_rescales_over_the_rest(monkeypatch):
    score, d = _run(monkeypatch, lst=20.7, air_ref=34.7)
    b, s = d["breakdown"], d["summary"]
    assert b["heat_exposure_pts"] is None and s["components_missing"] == ["heat"]
    assert s["heat_status"] == "implausible_vs_air_temperature" and s["local_lst_rejected_c"] == 20.7
    assert s["air_tmax_jja_normal_c"] == 34.7
    assert d["data_quality"]["degraded"] is True
    assert "heat_reading_implausible_vs_air_temperature" in d["data_quality"]["degraded_reasons"]
    assert score == round((b["air_quality_pts"] + b["flood_zone_pts"] + b["climate_trend_pts"]) / 75.0 * 100.0, 1)


def test_plausible_reading_keeps_heat(monkeypatch):
    score, d = _run(monkeypatch, lst=40.0, air_ref=34.7)
    assert d["breakdown"]["heat_exposure_pts"] is not None and d["summary"]["heat_status"] == "ok"


def test_no_reference_means_no_screen_and_heat_stays(monkeypatch):
    score, d = _run(monkeypatch, lst=20.7, air_ref=None)
    assert d["breakdown"]["heat_exposure_pts"] == pytest.approx(25.0) and d["summary"]["heat_status"] == "ok"
