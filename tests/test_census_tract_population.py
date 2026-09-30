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
