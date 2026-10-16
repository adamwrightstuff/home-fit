import os

import pytest

from data_sources.school_zones import ZONE_LAYERS, match_zoned_to_schools, zoned_schools, _root


def _s(name, level, dist=0.5, private=False):
    return {"schoolName": name, "schoolLevel": level, "distance": dist, "isPrivate": private}


def test_match_uses_name_tokens_level_and_skips_private():
    pool = [_s("Cameron Elementary School", "Elementary"), _s("Cameron Middle", "Middle"),
            _s("Cameron Academy", "Elementary", private=True)]
    z = {"level": "elementary", "also_serves": [], "name": "CAMERON", "names": ["CAMERON"]}
    assert match_zoned_to_schools(z, pool)["schoolName"] == "Cameron Elementary School"


def test_match_sf_alias_and_nyc_dbn_and_no_guess():
    pool = [_s("Carver (George Washington) Elementary", "Elementary"), _s("Ps 234", "Elementary")]
    sf = {"level": "elementary", "also_serves": [], "name": "Dr. George Washington Carver Elementary",
          "names": ["Dr. George Washington Carver Elementary", "CARVER"]}
    assert match_zoned_to_schools(sf, pool)["schoolName"].startswith("Carver")
    nyc = {"level": "elementary", "also_serves": [], "name": "30Q234", "names": ["30Q234"]}
    assert match_zoned_to_schools(nyc, pool)["schoolName"] == "Ps 234"
    none = {"level": "middle", "also_serves": [], "name": "30Q126", "names": ["30Q126"]}
    assert match_zoned_to_schools(none, pool) is None


def test_every_layer_has_levels_and_caveats():
    assert {l.level for l in ZONE_LAYERS} <= {"elementary", "middle", "high"}
    assert all(l.caveat and l.vintage for l in ZONE_LAYERS)


@pytest.mark.skipif(not os.path.isdir(os.path.join(_root(), "chicago_elementary_2526")),
                    reason="zone map files not downloaded")
def test_chicago_point_lookup():
    got = {z["level"]: z["name"] for z in zoned_schools(41.9024, -87.7230)}
    assert got.get("elementary") == "CAMERON" and got.get("high") == "ORR HS"


def test_match_by_location_inside_zone_and_prefers_regular_school():
    from shapely.geometry import Point, box
    from data_sources.school_zones import match_zone_by_location

    def sc(name, lon, lat, **kw):
        return {"schoolName": name, "schoolLevel": "Elementary", "isPrivate": False,
                "rankHistory": [{"rankStars": 3}], "address": {"latLong": {"latitude": lat, "longitude": lon}}, **kw}

    zone = {"level": "elementary", "also_serves": [], "names": [], "_geom": box(0, 0, 1, 1)}
    pool = [sc("Inside Elementary", 0.5, 0.5), sc("Outside Elementary", 5, 5),
            sc("Magnet Inside", 0.4, 0.4, isMagnetSchool="Yes")]
    assert match_zone_by_location(zone, pool)["schoolName"] == "Inside Elementary"
    assert match_zone_by_location({**zone, "_geom": box(9, 9, 10, 10)}, pool) is None
