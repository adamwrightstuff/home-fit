"""Climate risk under DPv2: unmapped flood and zone D are no data, and PM2.5 takes the tract from the place context."""
import pytest

import pillars.climate_risk as cr
from data_sources.place_context import PlaceContext

HEAT = {"local_lst_c": 36.0, "land_pixel_fraction": 1.0}
AIR = {"pm25_ugm3": 8.0, "years": [2021, 2022], "source": "cdc_tracking_epa_downscaler"}
FLOOD = {"flood_zone_pts": 30.0, "risk_tier": "minimal", "fld_zone": "X", "label": "AREA OF MINIMAL FLOOD HAZARD"}
TREND = {"trend_c_per_decade": 0.25}


def _patch(monkeypatch, flood=FLOOD, air_fn=None):
    monkeypatch.setattr(cr, "get_heat_exposure_lst", lambda *a, **k: HEAT)
    monkeypatch.setattr(cr, "get_air_quality_pm25", air_fn or (lambda *a, **k: AIR))
    monkeypatch.setattr(cr, "get_fema_flood_zone", lambda *a, **k: flood)
    monkeypatch.setattr(cr, "get_climate_trend_terraclimate", lambda *a, **k: TREND)


@pytest.mark.parametrize("tier,reason", [("unmapped", "flood_no_mapped_polygon"), ("d", "flood_zone_d_undetermined")])
def test_unmapped_point_and_zone_d_are_no_flood_data_not_minimal(monkeypatch, tier, reason):
    _patch(monkeypatch, flood={"flood_zone_pts": None, "risk_tier": tier, "fld_zone": "D" if tier == "d" else None, "label": None})
    score, d = cr.get_climate_risk_score(40.0, -74.0, area_type="suburban", density=3000.0)
    b = d["breakdown"]
    assert b["flood_zone_pts"] is None and d["summary"]["components_missing"] == ["flood"]
    assert d["data_quality"]["degraded"] is True and reason in d["data_quality"]["degraded_reasons"]
    assert score == round((b["heat_exposure_pts"] + b["air_quality_pts"] + b["climate_trend_pts"]) / 70.0 * 100.0, 1)


def test_pm25_reads_the_tract_from_the_place_context(monkeypatch):
    seen = {}

    def air(lat, lon, census_tract=None):
        seen["tract"] = census_tract
        return AIR

    _patch(monkeypatch, air_fn=air)
    tract = {"geoid": "36119000100", "state_fips": "36", "county_fips": "119", "tract_fips": "000100"}
    ctx = PlaceContext(lat=40.0, lon=-74.0, city=None, area_type="suburban", density=3000.0, census_tract=tract)
    cr.get_climate_risk_score(40.0, -74.0, place_context=ctx)
    assert seen["tract"] == tract


def test_get_pm25_uses_the_supplied_tract_without_a_census_call(monkeypatch):
    import data_sources.air_quality_pm25 as aq
    import data_sources.census_api as ca

    monkeypatch.setattr(ca, "get_census_tract", lambda *a, **k: pytest.fail("geocoder called although a tract was supplied"))
    monkeypatch.setattr(aq, "load_table", lambda: {"tracts": {"36119000100": 8.2}, "_meta": {"years": [2021, 2022]}})
    got = aq.get_pm25(40.0, -74.0, census_tract={"geoid": "36119000100"})
    assert got["pm25_ugm3"] == 8.2 and got["match"] == "exact"


def test_get_pm25_looks_the_tract_up_when_none_is_supplied(monkeypatch):
    import data_sources.air_quality_pm25 as aq
    import data_sources.census_api as ca

    monkeypatch.setattr(ca, "get_census_tract", lambda *a, **k: {"geoid": "36119000100"})
    monkeypatch.setattr(aq, "load_table", lambda: {"tracts": {"36119000100": 8.2}, "_meta": {"years": [2021, 2022]}})
    assert aq.get_pm25(40.0, -74.0)["pm25_ugm3"] == 8.2
