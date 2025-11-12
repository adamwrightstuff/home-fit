from data_sources.radius_profiles import get_radius_profile


def test_active_outdoors_urban():
    rp = get_radius_profile('active_outdoors', 'urban_core', 'city')
    assert rp['local_radius_m'] == 1500
    assert rp['regional_radius_m'] == 15000


def test_active_outdoors_rural():
    rp = get_radius_profile('active_outdoors', 'rural', 'city')
    assert rp['local_radius_m'] == 2000
    assert rp['regional_radius_m'] == 50000


def test_amenities_neighborhood():
    rp = get_radius_profile('neighborhood_amenities', 'urban_core', 'neighborhood')
    assert rp['query_radius_m'] == 1000
    assert rp['walkable_distance_m'] == 800


def test_transit_default():
    rp = get_radius_profile('public_transit_access', 'urban_core', 'city')
    assert rp['routes_radius_m'] == 1500


def test_healthcare_suburban():
    rp = get_radius_profile('healthcare_access', 'suburban', 'city')
    assert rp['fac_radius_m'] == 10000
    assert rp['pharm_radius_m'] == 3000


def test_built_beauty_neighborhood_scope():
    rp = get_radius_profile('built_beauty', 'urban_core', 'neighborhood')
    assert rp['tree_canopy_radius_m'] == 1000


def test_natural_beauty_neighborhood_scope():
    rp = get_radius_profile('natural_beauty', 'historic_urban', 'neighborhood')
    assert rp['tree_canopy_radius_m'] == 800


def test_air_travel_default():
    rp = get_radius_profile('air_travel_access', 'urban_core', 'city')
    assert rp['search_radius_km'] == 100


