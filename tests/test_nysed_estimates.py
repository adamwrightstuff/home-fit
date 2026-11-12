"""NY schools SchoolDigger leaves unrated get an estimate from NYSED Regents results (Babylon Junior-Senior High)."""
from data_sources import school_snapshot as ss
from data_sources.school_zones import match_zoned_to_schools
from pillars.schools import _entry, _nearest_in_district, school_rating


def _ny():
    ss._mem.clear()
    return ss.load_state("NY")


def test_unrated_junior_senior_high_gets_a_flagged_estimate_for_middle_and_high():
    s = next(x for x in _ny()["schools"] if x["schoolName"] == "Babylon Junior-Senior High School")
    assert s["rankHistory"][0]["_estimated"] == "nysed_regents"
    assert 80 <= school_rating(s) <= 92
    assert s["_serves"] == ["middle", "high"]
    assert _entry(s, "zoned")["estimated"] == "nysed_regents"


def test_rated_schools_are_never_touched():
    for s in _ny()["schools"]:
        if s["schoolName"] == "Babylon Memorial Grade School":
            assert "_estimated" not in s["rankHistory"][0] and "_serves" not in s


def test_zone_and_nearest_find_the_estimated_school_despite_its_alternative_label():
    snap = _ny()
    pool = [dict(s, distance=1.0) for s in snap["by_district"]["3603720"]]
    zone = {"name": "BABYLON JUNIOR-SENIOR HIGH SCHOOL", "level": "high"}
    assert match_zoned_to_schools(zone, pool)["schoolName"] == "Babylon Junior-Senior High School"
    for level in ("middle", "high"):
        _, picked = _nearest_in_district(pool, level, 2.0)
        assert [p["schoolName"] for p in picked] == ["Babylon Junior-Senior High School"]
    assert _nearest_in_district(pool, "elementary", 2.0)[1][0]["schoolName"] == "Babylon Memorial Grade School"


def test_estimates_stay_out_of_choice_pool_averages():
    from pillars.schools import choice_pool_average
    snap = _ny()
    real = [{"schoolName": f"R{i}", "schoolLevel": "High", "rankHistory": [{"rankStatewidePercentage": 40.0}],
             "isCharterSchool": "No"} for i in range(3)]
    est = next(x for x in snap["schools"] if x["schoolName"] == "Babylon Junior-Senior High School")
    assert choice_pool_average(real + [est], "high") == choice_pool_average(real, "high")


def test_details_say_which_ratings_are_estimated():
    from pillars.schools import summary_extras
    bd = {"model": "zoned_v1", "levels": {
        "elementary": {"source": "zone", "score": 64.0, "schools": [{"name": "Memorial", "rating": 64.0}]},
        "high": {"source": "zone", "score": 86.74, "zone": None,
                 "schools": [{"name": "Babylon Junior-Senior High School", "rating": 86.74, "estimated": "nysed_regents"}]}}}
    assert summary_extras(bd)["estimated_ratings"] == \
        "Babylon Junior-Senior High School (87): estimated from NYSED Regents results, not a SchoolDigger rating"
    bd["levels"]["high"]["schools"][0].pop("estimated")
    assert "estimated_ratings" not in summary_extras(bd)
