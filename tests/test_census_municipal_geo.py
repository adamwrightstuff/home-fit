from data_sources import census_api as c


def test_new_england_town_uses_county_subdivision_not_place():
    geo = {"geo_type": "county_subdivision", "cousub_fips": "33620", "county_fips": "190"}
    assert c._municipal_geo_params("09", None, geo) == ("county subdivision:33620", "state:09 county:190")


def test_regular_place_uses_place_clause():
    assert c._municipal_geo_params("36", "51000", None) == ("place:51000", "state:36")
