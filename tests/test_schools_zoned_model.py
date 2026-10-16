from pillars.schools import build_levels, headline_from_levels, school_rating
from scripts.catalog.check_education import evaluate


def _s(name, level, pct, dist, charter="No", stars=3):
    return {"schoolName": name, "schoolLevel": level, "distance": dist, "isCharterSchool": charter,
            "rankHistory": [{"rankStars": stars, "rankStatewidePercentage": pct}]}


POOL = [_s("Cameron Elementary School", "Elementary", 15.0, 0.3), _s("Dodge Elementary", "Elementary", 80.0, 0.6),
        _s("Lamar Middle", "Middle", 90.0, 1.0), _s("Webb Middle", "Middle", 2.0, 1.2), _s("Burnet Middle", "Middle", 4.0, 1.4),
        _s("Orr High School", "High", 1.0, 0.7), _s("KIPP Charter High", "High", 60.0, 0.5, charter="Yes")]


def test_rating_uses_percentile_not_stars():
    assert school_rating(_s("A", "Middle", 2.0, 1, stars=0)) == 2.0
    assert school_rating({"rankHistory": [{"rankStars": 4}]}) == 80.0


def test_zoned_school_beats_nearest_and_charters_stay_out_of_levels():
    zoned = [{"level": "elementary", "also_serves": ["middle"], "name": "CAMERON", "names": ["CAMERON"],
              "vintage": "2025-26", "caveat": ""}]
    lv = build_levels(POOL, zoned, 2.0)
    assert lv["elementary"]["source"] == "zone" and lv["elementary"]["score"] == 15.0
    # the K-8 zone has no middle school of its own, so Cameron stays unrated as a middle: falls to nearest
    assert lv["middle"]["source"] in ("zone", "nearest")
    assert all(not e["is_charter_school"] for v in lv.values() for e in v["schools"])


def test_no_zone_takes_nearest_per_level_and_headline_is_level_mean():
    lv = build_levels(POOL, [], 2.0)
    assert lv["elementary"]["source"] == "nearest"
    assert round(lv["middle"]["score"], 2) == round((90 + 2 + 4) / 3, 2)
    h = headline_from_levels(lv, 1.0)
    assert abs(h - (sum(v["score"] for v in lv.values() if v["score"] is not None) / 3 + 1.0)) < 1e-6


def test_check_validates_zoned_model_formula():
    lv = build_levels(POOL, [], 2.0)
    total = round(headline_from_levels(lv, 0.0), 2)
    row = {"success": True, "catalog": {"name": "X", "lat": "40", "lon": "-73"},
           "score": {"location_info": {"state": "Illinois"}, "livability_pillars": {
               "quality_education": {"score": total, "confidence": 85, "weight": 7.7, "breakdown": {
                   "model": "zoned_v1", "early_ed_bonus": 0.0, "levels": lv,
                   "rated_schools": [e for v in lv.values() for e in v["schools"]],
                   "split": {"public": {"score": total}, "charter": {"score": None}}}},
               "housing_value": {"score": 50, "weight": 7.7}}}}
    assert evaluate([row], "x", {}, False)["verdict"] == "PASS"
    row["score"]["livability_pillars"]["quality_education"]["score"] = 5.0
    assert "formula_mismatch" in {f["check"] for f in evaluate([row], "x", {}, False)["failures"]}


def test_state_names_normalize_to_abbreviations():
    from data_sources.schools_api import normalize_state
    assert normalize_state("New York") == "NY" and normalize_state(" ny ") == "NY" and normalize_state("Illinois") == "IL"


def test_choice_level_is_not_scored_where_the_district_publishes_zones():
    zoned = [{"level": "elementary", "also_serves": [], "name": "CAMERON", "names": ["CAMERON"],
              "vintage": "2025-26", "caveat": ""}]
    lv = build_levels(POOL, zoned, 2.0)
    assert lv["elementary"]["source"] == "zone"
    assert lv["middle"]["source"] == "choice" and lv["middle"]["score"] is None and lv["middle"]["schools"] == []
    assert lv["high"]["source"] == "choice" and lv["high"]["reference"]    # nearest kept only as a reference
    assert headline_from_levels(lv, 0.0) == lv["elementary"]["score"]       # headline is the zoned level alone


def test_resident_campus_with_several_schools_is_averaged():
    from shapely.geometry import box
    pool = [_s("Alpha High", "High", 80.0, 0.5), _s("Beta High", "High", 40.0, 0.5), _s("Far High", "High", 99.0, 5.0)]
    for i, sc in enumerate(pool):
        sc["address"] = {"latLong": {"latitude": 0.5 if i < 2 else 5.0, "longitude": 0.5 if i < 2 else 5.0}}
    zoned = [{"level": "high", "also_serves": [], "name": "", "names": [], "vintage": "2018", "caveat": "",
              "_geom": box(0, 0, 1, 1)}]
    lv = build_levels(pool, zoned, 2.0)
    assert lv["high"]["source"] == "zone" and lv["high"]["score"] == 60.0 and len(lv["high"]["schools"]) == 2


def test_nyc_zone_listing_two_schools_returns_both():
    from data_sources.school_zones import match_zoned_schools
    pool = [_s("Ps 18 Alpha", "Elementary", 50.0, 0.4), _s("Ps 98 Beta", "Elementary", 70.0, 0.5)]
    z = {"level": "elementary", "also_serves": [], "name": "06M018", "names": ["06M018", "06M098"],
         "alts": [["06M018"], ["06M098"]], "_geom": None}
    assert {s["schoolName"] for s in match_zoned_schools(z, pool)} == {"Ps 18 Alpha", "Ps 98 Beta"}
