"""Two-part natural beauty (streets + scenery): formula, rescale, preference tilt, catalog script."""

import pytest

from pillars import natural_beauty as NB
from scripts.catalog import recompute_natural_beauty_two_part_offline as OFF
from scripts.catalog.apply_preference_filters import apply_nb_preferences_v9

COMP = {"gvi_score": 40.0, "canopy_score": 50.0, "topo_score": 80.0, "water_score": 20.0,
        "landcover_score": 90.0, "bio_score": 90.0}


def test_each_part_leans_on_its_stronger_component():
    r = NB.nb_two_part(COMP)
    assert r["streets"] == pytest.approx(0.7 * 50 + 0.3 * 40)
    assert r["scenery"] == pytest.approx(0.7 * 80 + 0.3 * 20)
    assert r["blend"] == pytest.approx(0.5 * r["streets"] + 0.5 * r["scenery"], abs=0.01)


def test_landcover_and_biodiversity_are_not_scored():
    low = NB.nb_two_part({**COMP, "landcover_score": 0.0, "bio_score": 0.0})
    assert low["score"] == NB.nb_two_part(COMP)["score"]


def test_scale_table_is_monotone_and_matches_the_old_score_range():
    t = NB._v9_scale()
    assert all(b2 > b1 for b1, b2 in zip(t["blend"], t["blend"][1:]))
    assert all(s2 >= s1 for s1, s2 in zip(t["score"], t["score"][1:]))
    assert 0 <= t["score"][0] < t["score"][-1] <= 100 and t["n_places"] >= 1400
    assert NB._blend_to_score(-5) == t["score"][0] and NB._blend_to_score(500) == t["score"][-1]


def test_score_rises_with_the_blend_and_never_leaves_0_to_100():
    levels = [NB.nb_two_part({k: v for k in ("gvi_score", "canopy_score", "topo_score", "water_score")})["score"]
              for v in (0.0, 25.0, 50.0, 75.0, 100.0)]
    assert levels == sorted(levels) and 0 <= levels[0] and levels[-1] <= 100


def test_catalog_scores_keep_the_old_mean_and_spread_without_a_pile_up_at_100():
    import glob, json, statistics as S
    sc = []
    for f in glob.glob("data/*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"):
        for line in open(f):
            nb = ((json.loads(line).get("score") or {}).get("livability_pillars") or {}).get("natural_beauty") or {}
            if (nb.get("details") or {}).get("score_before_two_part") is not None:
                sc.append(nb["score"])
    if len(sc) < 1400:
        pytest.skip("catalog files not present")
    assert abs(S.mean(sc) - 64.6) < 1.5 and abs(S.pstdev(sc) - 18.9) < 1.5
    assert sum(1 for x in sc if x >= 99.5) < 0.005 * len(sc)


def test_missing_greenery_is_not_scored_as_zero_and_is_flagged():
    comp = {"gvi_score": 0.0, "canopy_score": 0.0, "topo_score": 40.0, "water_score": 20.0}
    assert NB.streets_inputs_missing(0.0, 0.0) and not NB.streets_inputs_missing(0.03, 0.1)
    assert NB.streets_inputs_missing(None, None, measured=False) and not NB.streets_inputs_missing(0, 0, measured=True)
    missing = NB.nb_two_part(comp, streets_missing=True)
    assert missing["streets"] is None and missing["blend"] == pytest.approx(missing["scenery"], abs=0.01)
    assert missing["score"] > NB.nb_two_part(comp)["score"]  # a real zero would have dragged it down


def test_scenery_preference_favors_the_scenic_part_and_canopy_the_street_part():
    neutral = NB.v9_score_from_components(COMP)
    assert NB.v9_score_from_components(COMP, ["mountains"]) > neutral  # topo 80 beats streets 47
    assert NB.v9_score_from_components(COMP, ["canopy"]) < neutral
    assert NB.v9_score_from_components(COMP, ["mountains", "canopy"]) == pytest.approx(neutral, abs=0.01)


def test_water_type_mismatch_cuts_the_water_score_for_a_water_preference():
    c = {**COMP, "water_score": 60.0}
    on_ocean = NB.v9_score_from_components(c, ["ocean"], "ocean")
    on_river = NB.v9_score_from_components(c, ["ocean"], "river")
    assert on_ocean > on_river
    assert NB.v9_score_from_components(c, None, "river") == NB.v9_score_from_components(c, None, "ocean")


def test_a_missing_part_falls_back_to_the_other_and_nothing_gives_none():
    only_streets = NB.nb_two_part({"gvi_score": 50.0})
    assert only_streets["scenery"] is None and only_streets["blend"] == pytest.approx(50.0)
    assert NB.nb_two_part({}) is None and NB.v9_score_from_components({}) is None


def test_catalog_script_formula_and_frontend_mirror_agree_with_the_pillar():
    v9 = {**COMP, "inputs": {"water_type": "ocean", "gvi_pct": 12.0, "canopy_pct": 9.0}}
    for prefs in (["mountains"], ["canopy"], ["ocean"], ["lakes_rivers"], ["ocean", "canopy"]):
        assert apply_nb_preferences_v9(v9, prefs) == pytest.approx(
            NB.v9_score_from_components(v9, prefs, "ocean"), abs=0.01), prefs


def test_offline_recompute_is_idempotent_and_keeps_the_original_score():
    score = {"livability_pillars": {"natural_beauty": {"score": 70.0, "weight": 0.1,
             "details": {"v9_breakdown": {**COMP, "owa_score": 70.0, "weights": [1], "owa_components": [1]}}}}}
    first = OFF.recompute_place(score)
    nb = score["livability_pillars"]["natural_beauty"]
    assert first["before"] == 70.0 and nb["score"] == first["after"]
    assert nb["details"]["score_before_two_part"] == 70.0
    assert "owa_score" not in nb["details"]["v9_breakdown"]
    again = OFF.recompute_place(score)
    assert again["after"] == first["after"] and nb["details"]["score_before_two_part"] == 70.0
