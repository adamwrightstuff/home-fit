"""
Offline tests for filling 2010-vintage tract codes (returned by TIGERweb) with
2020-tract ACS populations when the Census split the tract.
"""

from __future__ import annotations

from unittest import mock

from data_sources import census_api


def _fake_county(state, county, year):
    if year == 2022:
        return {"012801": 2742, "012802": 1901, "013200": 3931, "014100": 500}
    return {"012800": 4556, "013200": 4292, "014000": 3800}


def test_split_tract_sums_its_2020_pieces():
    with mock.patch.object(census_api, "_acs_county_tract_populations", side_effect=_fake_county):
        pop, how = census_api._population_for_old_tract("06", "075", "012800")
    assert (pop, how) == (4643, "split_pieces_2022")


def test_renumbered_tract_falls_back_to_2019_same_code():
    with mock.patch.object(census_api, "_acs_county_tract_populations", side_effect=_fake_county):
        pop, how = census_api._population_for_old_tract("06", "075", "014000")
    assert (pop, how) == (3800, "acs_2019_same_code")


def test_suffixed_old_tract_does_not_borrow_sibling_populations():
    # 0128.01 is not a parent of 0128.02; only "00" tracts are split into suffixed pieces
    with mock.patch.object(census_api, "_acs_county_tract_populations", side_effect=_fake_county):
        pop, how = census_api._population_for_old_tract("06", "075", "012803")
    assert (pop, how) == (None, "missing")


def test_tract_lookups_use_the_2020_census_tract_layer():
    # ACS 2022 is tabulated on 2020 tracts; the tigerWMS_ACS2022 layer serves 2010 codes
    assert "tigerWMS_Census2020" in census_api.TIGERWEB_TRACT_LAYER_URL


def test_land_area_queries_the_2020_layer_by_tract_code():
    calls = []

    class _R:
        def json(self):
            return {"features": [{"attributes": {"AREALAND": 348_810, "AREAWATER": 0, "NAME": "Census Tract 2718.04", "GEOID": "06037271804"}}]}

    def fake_request(url, params, timeout=None):
        calls.append((url, params["where"]))
        return _R()

    tract = {"state_fips": "06", "county_fips": "037", "tract_fips": "271804"}
    with mock.patch.object(census_api, "_make_request_with_retry", side_effect=fake_request):
        area = census_api.get_land_area(tract)
    assert area is not None and abs(area - 348_810 / 2_589_988.11) < 1e-3
    url, where = calls[0]
    assert "tigerWMS_Census2020" in url and "TRACT='271804'" in where


def test_disk_tract_cache_key_includes_layer_vintage():
    import inspect
    sig = inspect.signature(census_api._tigerweb_tracts_intersecting_disk.__wrapped__)
    assert sig.parameters["vintage"].default == census_api.TIGERWEB_TRACT_VINTAGE
