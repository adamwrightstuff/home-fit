"""
Tests for scripts/catalog/apply_preference_filters.py

Run:
  pytest tests/test_preference_filters.py -v

Integration tests require the NYC catalog JSONL at the default path.
Skip them with: pytest tests/test_preference_filters.py -v -m "not integration"
"""
import json
import math
import pytest
from pathlib import Path

from scripts.catalog.apply_preference_filters import (
    apply_nb_preferences_v9,
    apply_ao_preferences,
    apply_waterfront_sub_preference,
    weighted_score,
    passes_hard_filters,
    passes_housing_filter,
    passes_political_filter,
    lean_label_for,
    housing_type_for,
    process_catalog,
    score_row,
    resolve_weights,
    ALL_PILLARS,
    PRIORITY_TO_NUMERIC,
)

NYC_CATALOG = Path("data/nyc_metro_place_catalog_scores_merged.jsonl")


# ---------------------------------------------------------------------------
# NB OWA preference re-weighting
# ---------------------------------------------------------------------------

V9_OCEAN = {
    "gvi_score": 40.0,
    "water_score": 80.0,
    "canopy_score": 20.0,
    "topo_score": 10.0,
    "landcover_score": 30.0,
    "bio_score": 5.0,
    "inputs": {"water_type": "ocean"},
}

V9_RIVER = {
    "gvi_score": 60.0,
    "water_score": 50.0,
    "canopy_score": 55.0,
    "topo_score": 15.0,
    "landcover_score": 40.0,
    "bio_score": 10.0,
    "inputs": {"water_type": "river"},
}


def test_nb_ocean_pref_boosts_water_score():
    base = apply_nb_preferences_v9(V9_OCEAN, [])
    ocean = apply_nb_preferences_v9(V9_OCEAN, ["ocean"])
    assert ocean is not None
    assert ocean > (base or 0), "Ocean preference should boost a place with high water_score"


def test_nb_ocean_pref_penalizes_river_place():
    ocean_on_ocean = apply_nb_preferences_v9(V9_OCEAN, ["ocean"])
    ocean_on_river = apply_nb_preferences_v9(V9_RIVER, ["ocean"])
    assert ocean_on_ocean is not None
    assert ocean_on_river is not None
    assert ocean_on_ocean > ocean_on_river, "Ocean pref should score coastal place higher than river place"


def test_nb_canopy_pref_boosts_gvi():
    high_canopy = {**V9_RIVER, "gvi_score": 90.0, "inputs": {"water_type": "river"}}
    low_canopy = {**V9_RIVER, "gvi_score": 10.0, "inputs": {"water_type": "river"}}
    high = apply_nb_preferences_v9(high_canopy, ["canopy"])
    low = apply_nb_preferences_v9(low_canopy, ["canopy"])
    assert high is not None and low is not None
    assert high > low


def test_nb_multi_pref_ocean_and_canopy():
    result = apply_nb_preferences_v9(V9_OCEAN, ["ocean", "canopy"])
    assert result is not None
    assert 0 <= result <= 100


def test_nb_empty_prefs_returns_none():
    assert apply_nb_preferences_v9(V9_OCEAN, []) is None


def test_nb_empty_v9_returns_none():
    assert apply_nb_preferences_v9({}, ["ocean"]) is None


# ---------------------------------------------------------------------------
# AO OWA preference re-weighting
# ---------------------------------------------------------------------------

AO_PARKS_HEAVY = {"daily_urban_outdoors": 30.0, "wild_adventure": 5.0, "waterfront_lifestyle": 2.0}
AO_WATERFRONT_HEAVY = {"daily_urban_outdoors": 5.0, "wild_adventure": 5.0, "waterfront_lifestyle": 20.0}


def test_ao_local_parks_pref_boosts_parks_heavy_place():
    parks = apply_ao_preferences(AO_PARKS_HEAVY, ["local_parks"])
    wf = apply_ao_preferences(AO_WATERFRONT_HEAVY, ["local_parks"])
    assert parks is not None and wf is not None
    assert parks > wf


def test_ao_waterfront_pref_boosts_waterfront_heavy_place():
    wf = apply_ao_preferences(AO_WATERFRONT_HEAVY, ["waterfront"])
    parks = apply_ao_preferences(AO_PARKS_HEAVY, ["waterfront"])
    assert wf is not None and parks is not None
    assert wf > parks


def test_ao_normalizes_to_0_100():
    result = apply_ao_preferences(AO_PARKS_HEAVY, ["local_parks", "waterfront"])
    assert result is not None
    assert 0 <= result <= 100


def test_ao_empty_prefs_returns_none():
    assert apply_ao_preferences(AO_PARKS_HEAVY, []) is None


# ---------------------------------------------------------------------------
# Waterfront sub-preference
# ---------------------------------------------------------------------------

AO_WITH_WF_BD = {
    "waterfront_breakdown": {"ocean_beach": 80.0, "lake_river": 10.0, "bay_harbor": 0.0}
}


def test_waterfront_sub_ocean_beach():
    result = apply_waterfront_sub_preference(AO_WITH_WF_BD, "ocean_beach")
    assert result is not None
    assert result > 50


def test_waterfront_sub_bay_harbor_zero_returns_zero():
    result = apply_waterfront_sub_preference(AO_WITH_WF_BD, "bay_harbor")
    assert result == 0.0


def test_waterfront_sub_missing_breakdown_returns_none():
    assert apply_waterfront_sub_preference({}, "ocean_beach") is None


# ---------------------------------------------------------------------------
# Weighted score
# ---------------------------------------------------------------------------

def test_weighted_score_single_pillar():
    lp = {"community_safety": {"score": 80.0}}
    w = {"community_safety": 100}
    assert weighted_score(lp, w) == 80.0


def test_weighted_score_uses_nb_adjusted():
    lp = {"natural_beauty": {"score": 50.0}}
    w = {"natural_beauty": 100}
    result = weighted_score(lp, w, nb_adjusted=90.0)
    assert result == 90.0


def test_weighted_score_uses_ao_adjusted():
    lp = {"active_outdoors": {"score": 40.0}}
    w = {"active_outdoors": 100}
    result = weighted_score(lp, w, ao_adjusted=75.0)
    assert result == 75.0


def test_weighted_score_zero_weights_returns_zero():
    lp = {"community_safety": {"score": 99.0}}
    w = {k: 0 for k in ALL_PILLARS}
    assert weighted_score(lp, w) == 0.0


# ---------------------------------------------------------------------------
# Housing filter
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("pct, expected", [
    (0.80, "sf_townhouse"),
    (0.30, "sf_townhouse"),
    (0.20, "small_multifamily"),
    (0.05, "apartment"),
])
def test_housing_type_for(pct, expected):
    assert housing_type_for(pct) == expected


def test_passes_housing_no_filter():
    assert passes_housing_filter(0.10, []) is True


def test_passes_housing_sf_townhouse():
    assert passes_housing_filter(0.30, ["sf_townhouse"]) is True
    assert passes_housing_filter(0.10, ["sf_townhouse"]) is False


def test_passes_housing_apartment():
    assert passes_housing_filter(0.05, ["apartment"]) is True
    assert passes_housing_filter(0.50, ["apartment"]) is False


# ---------------------------------------------------------------------------
# Political lean filter
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lean, label", [
    (0.75,  "strong_d"),
    (0.30,  "lean_d"),
    (0.00,  "moderate"),
    (-0.30, "lean_r"),
    (-0.75, "strong_r"),
])
def test_lean_label_for(lean, label):
    assert lean_label_for(lean) == label


def test_passes_political_no_filter():
    assert passes_political_filter(0.5, []) is True


def test_passes_political_lean_d_and_moderate():
    assert passes_political_filter(0.30, ["lean_d", "moderate"]) is True
    assert passes_political_filter(0.00, ["lean_d", "moderate"]) is True
    assert passes_political_filter(-0.30, ["lean_d", "moderate"]) is False


def test_passes_political_strong_r_excluded():
    assert passes_political_filter(-0.80, ["strong_d", "lean_d", "moderate", "lean_r"]) is False
    assert passes_political_filter(-0.80, ["strong_r"]) is True


# ---------------------------------------------------------------------------
# Hard filter
# ---------------------------------------------------------------------------

def _make_row(archetype="Affluent", trajectory="Arrived", local_scene="High",
               built_form="Historic urban fabric", lean_2024=0.3, pct_low=0.50) -> dict:
    return {
        "success": True,
        "score": {
            "status_signal_breakdown": {"archetype": archetype, "trajectory": trajectory},
            "local_scene_bucket": local_scene,
            "housing_stock": {"pct_low_density": pct_low},
            "livability_pillars": {
                "built_environment": {"summary": {"built_form_label": built_form}},
                "political_lean": {"breakdown": {"lean_2024": lean_2024, "label": "lean_d"}},
            },
        },
    }


def test_passes_all_filters():
    row = _make_row()
    cfg = {
        "archetypes": ["Affluent", "Elite"],
        "trajectories": ["Arrived"],
        "local_scene": "High",
        "built_forms": ["Historic urban fabric", "Suburban"],
        "political_lean": ["lean_d", "moderate"],
        "housing": ["sf_townhouse"],
    }
    ok, reason = passes_hard_filters(row, cfg)
    assert ok, reason


def test_fails_archetype():
    row = _make_row(archetype="Middle Class")
    ok, reason = passes_hard_filters(row, {"archetypes": ["Affluent", "Elite"]})
    assert not ok
    assert "archetype" in reason


def test_fails_trajectory():
    row = _make_row(trajectory="Declining")
    ok, reason = passes_hard_filters(row, {"trajectories": ["Arrived"]})
    assert not ok
    assert "trajectory" in reason


def test_fails_local_scene():
    row = _make_row(local_scene="Low")
    ok, reason = passes_hard_filters(row, {"local_scene": "High"})
    assert not ok


def test_fails_political_lean():
    row = _make_row(lean_2024=-0.80)
    ok, reason = passes_hard_filters(row, {"political_lean": ["lean_d", "moderate"]})
    assert not ok


def test_fails_housing():
    row = _make_row(pct_low=0.05)
    ok, reason = passes_hard_filters(row, {"housing": ["sf_townhouse"]})
    assert not ok


def test_empty_filters_pass_everything():
    row = _make_row(archetype="Struggling", trajectory="Declining", local_scene="Low",
                    lean_2024=-0.95, pct_low=0.01)
    ok, _ = passes_hard_filters(row, {})
    assert ok


# ---------------------------------------------------------------------------
# Integration: real NYC catalog
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.skipif(not NYC_CATALOG.exists(), reason="NYC catalog not found")
def test_integration_filter_count():
    cfg = {
        "archetypes": ["Elite", "Affluent"],
        "trajectories": ["Arrived"],
        "local_scene": "High",
        "built_forms": ["Historic urban fabric", "Urban residential", "Suburban"],
        "political_lean": ["lean_d", "moderate"],
        "housing": ["sf_townhouse"],
        "nb_prefs": ["ocean", "canopy"],
        "ao_prefs": ["local_parks", "waterfront"],
        "waterfront_sub": None,
    }
    weights = resolve_weights({
        "community_safety": "High", "quality_education": "High", "social_fabric": "High",
        "neighborhood_amenities": "Medium", "natural_beauty": "Medium", "diversity": "Medium",
        "healthcare_access": "Low", "active_outdoors": "Low",
        "housing_value": "Low", "public_transit_access": "Low",
    })
    results: list = []
    process_catalog(NYC_CATALOG, cfg, weights, results)
    assert len(results) > 0, "Should have at least one result"
    assert len(results) < 50, "Should filter most places out"


@pytest.mark.integration
@pytest.mark.skipif(not NYC_CATALOG.exists(), reason="NYC catalog not found")
def test_integration_scores_in_range():
    cfg = {"archetypes": ["Affluent", "Elite"], "trajectories": ["Arrived"],
           "local_scene": "High", "nb_prefs": ["ocean", "canopy"],
           "ao_prefs": ["local_parks", "waterfront"]}
    weights = resolve_weights({"community_safety": "High", "social_fabric": "High",
                               "natural_beauty": "Medium", "active_outdoors": "Low"})
    results: list = []
    process_catalog(NYC_CATALOG, cfg, weights, results)
    for r in results:
        assert 0 <= r["final_score"] <= 100, f"{r['name']} score out of range: {r['final_score']}"


@pytest.mark.integration
@pytest.mark.skipif(not NYC_CATALOG.exists(), reason="NYC catalog not found")
def test_integration_ranking_stable():
    cfg = {"archetypes": ["Affluent", "Elite"], "trajectories": ["Arrived"],
           "local_scene": "High", "nb_prefs": ["ocean", "canopy"],
           "ao_prefs": ["local_parks", "waterfront"]}
    weights = resolve_weights({"community_safety": "High", "quality_education": "High",
                               "social_fabric": "High", "neighborhood_amenities": "Medium",
                               "natural_beauty": "Medium", "active_outdoors": "Low"})
    results: list = []
    process_catalog(NYC_CATALOG, cfg, weights, results)
    results.sort(key=lambda x: x["final_score"], reverse=True)
    scores = [r["final_score"] for r in results]
    assert scores == sorted(scores, reverse=True)
    # Carroll Gardens should appear in top results with these filters
    names = [r["name"] for r in results[:10]]
    assert any("Carroll" in n for n in names), f"Carroll Gardens missing from top 10: {names}"
