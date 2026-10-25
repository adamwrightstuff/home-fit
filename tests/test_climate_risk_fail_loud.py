"""Climate risk fails loudly: missing components are no data, never a neutral or invented value."""
import pytest

import pillars.climate_risk as cr

HEAT = {"local_lst_c": 36.0, "land_pixel_fraction": 1.0}
AIR = {"pm25_ugm3": 8.0, "years": [2021, 2022], "source": "cdc_tracking_epa_downscaler"}
FLOOD = {"flood_zone_pts": 30.0, "risk_tier": "minimal", "fld_zone": "X", "label": "AREA OF MINIMAL FLOOD HAZARD"}
TREND = {"trend_c_per_decade": 0.25}


def _run(monkeypatch, heat=HEAT, air=AIR, flood=FLOOD, trend=TREND):
    monkeypatch.setattr(cr, "get_heat_exposure_lst", lambda *a, **k: heat)
    monkeypatch.setattr(cr, "get_air_quality_pm25", lambda *a, **k: air)
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


def test_missing_air_value_is_no_data_not_worst_case(monkeypatch):
    score, d = _run(monkeypatch, air={"years": [2022]})
    assert d["breakdown"]["air_quality_pts"] is None
    score, d = _run(monkeypatch, air=None)  # tract with no PM2.5 value
    assert d["breakdown"]["air_quality_pts"] is None and d["data_quality"]["degraded"] is True


@pytest.mark.parametrize("pm,expected", [(5.0, 20.0), (4.0, 20.0), (20.0, 10.0), (35.0, 0.0), (50.0, 0.0)])
def test_air_points_are_linear_from_the_who_guideline_to_the_zero_point(monkeypatch, pm, expected):
    score, d = _run(monkeypatch, air={"pm25_ugm3": pm, "years": [2022], "source": "x"})
    assert d["breakdown"]["air_quality_pts"] == pytest.approx(expected)
    assert d["summary"]["pm25_ugm3"] == pytest.approx(pm)


def test_fewer_than_three_components_raises(monkeypatch):
    with pytest.raises(RuntimeError):
        _run(monkeypatch, flood=None, trend=None)
    with pytest.raises(RuntimeError):
        _run(monkeypatch, heat=None, air=None, flood=None, trend=None)


@pytest.mark.parametrize("lst", [-21.5, 7.7, 14.0, 80.0])
def test_implausible_surface_temperature_is_no_data_not_full_heat_points(monkeypatch, lst):
    score, d = _run(monkeypatch, heat={"local_lst_c": lst, "land_pixel_fraction": 1.0})
    assert d["breakdown"]["heat_exposure_pts"] is None
    assert d["summary"]["heat_status"] == "implausible_lst" and d["summary"]["local_lst_rejected_c"] == lst
    assert d["data_quality"]["degraded"] is True


def test_coastal_fog_temperature_is_still_scored(monkeypatch):
    score, d = _run(monkeypatch, heat={"local_lst_c": 19.0, "land_pixel_fraction": 1.0})
    assert d["breakdown"]["heat_exposure_pts"] == pytest.approx(25.0)
    assert d["summary"]["heat_status"] == "ok"
