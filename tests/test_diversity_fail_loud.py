import pytest
from data_sources import census_api


def test_failed_place_lookup_is_no_data(monkeypatch):
    monkeypatch.setattr(census_api, "_make_request_with_retry", lambda *a, **k: None)
    with pytest.raises(RuntimeError):
        census_api._place_fips_lookup(40.0, -75.0, strict=True)
    assert census_api._place_fips_lookup(40.0, -75.0) is None


def test_failed_place_acs_fetch_does_not_fall_back_to_tract(monkeypatch):
    tract = {"tract_fips": "000100", "state_fips": "42", "county_fips": "101"}
    monkeypatch.setattr(census_api, "_place_fips_lookup",
                        lambda lat, lon, strict=False: {"state_fips": "42", "place_fips": "60000", "geo_type": "incorporated_place"})
    monkeypatch.setattr(census_api, "_fetch_diversity_acs", lambda f, i: None)
    with pytest.raises(RuntimeError):
        census_api.get_diversity_data(40.0, -75.0, tract=tract, area_type="suburban")
