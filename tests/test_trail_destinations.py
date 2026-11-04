from data_sources.osm_api import build_trail_destinations

LAT, LON = 40.0, -74.0


def _el(i, tags, ha=0.0, dlat=0.0):
    """Element with a square bounding box of about `ha` hectares centred `dlat` degrees north of the pin."""
    side_deg = (ha * 0.01) ** 0.5 / 111.32 if ha else 0.0
    c = LAT + dlat
    return {"type": "way", "id": i, "tags": tags,
            "bounds": {"minlat": c - side_deg / 2, "maxlat": c + side_deg / 2,
                       "minlon": LON - side_deg / 2, "maxlon": LON + side_deg / 2}}


def test_hiking_routes_count_and_cycle_routes_do_not():
    els = [
        _el(1, {"route": "hiking", "name": "Blue Trail"}),
        _el(2, {"route": "hiking", "name": "Bike", "bicycle": "designated"}),
        _el(3, {"route": "hiking", "name": "NCN", "network": "ncn"}),
    ]
    out = build_trail_destinations(els, LAT, LON)
    assert [d["name"] for d in out] == ["Blue Trail"] and out[0]["type"] == "hiking_route"


def test_large_named_parks_count_once_small_ones_do_not():
    els = [
        _el(1, {"leisure": "park", "name": "Big Woods"}, ha=300),
        _el(2, {"leisure": "park", "name": "Big Woods"}, ha=300),
        _el(3, {"leisure": "park", "name": "Pocket Park"}, ha=5),
    ]
    out = build_trail_destinations(els, LAT, LON)
    assert [d["name"] for d in out] == ["Big Woods"]


def test_street_golf_and_historic_features_are_dropped():
    els = [
        _el(1, {"leisure": "park", "name": "Hudson River Greenway"}, ha=300),
        _el(2, {"leisure": "park", "name": "Marine Park Golf Course"}, ha=300),
        _el(3, {"boundary": "protected_area", "name": "Boerum Hill Historic District"}, ha=300),
        _el(4, {"boundary": "protected_area", "name": "Old Town", "historic": "yes"}, ha=300),
        _el(5, {"leisure": "nature_reserve", "name": "Marsh Reserve"}, ha=300),
    ]
    out = build_trail_destinations(els, LAT, LON)
    assert [d["name"] for d in out] == ["Marsh Reserve"]


def test_unnamed_large_areas_are_counted_by_id_and_distance_is_from_the_box_centre():
    els = [_el(1, {"boundary": "national_park"}, ha=500, dlat=0.02), _el(2, {"boundary": "national_park"}, ha=500, dlat=0.2)]
    out = build_trail_destinations(els, LAT, LON)
    assert len(out) == 2
    assert 2000 < out[0]["distance_m"] < 2400 and out[1]["distance_m"] > 20000
