"""
Golden-set tests for the neighborhood_beauty blend formula.

Tests _combined_weight() and blend_scores() directly using stored catalog values
(built_score, natural_score, density, effective_area_type, BCR) — no live API calls.
Validates that the BCR ceiling produces correct directional behavior and keeps
scores within research-backed ranges for representative NYC-metro places.

Golden set covers five scenarios:
  - True suburbs (should rise vs. old formula)
  - Floor-protected historic suburb (stable)
  - Best-in-class historic urban (modest drop, stays excellent)
  - Dense historic urban (modest drop)
  - Dense place mislabeled suburban (slight drop, correct)
"""

import json
import os
import pytest
from pillars.neighborhood_beauty import _combined_weight, blend_scores

CATALOG_PATH = os.path.join(os.path.dirname(__file__), "..", "data",
                             "nyc_metro_place_catalog_scores_merged.jsonl")


def _load_place(name: str) -> dict:
    with open(CATALOG_PATH) as f:
        for line in f:
            d = json.loads(line)
            if d.get("catalog", {}).get("name") == name and d.get("success"):
                return d
    raise KeyError(f"Place not found in catalog: {name}")


def _extract(name: str):
    """Return (built_score, natural_score, density, effective_area_type, bcr)."""
    d = _load_place(name)
    nb = d["score"]["livability_pillars"]["neighborhood_beauty"]
    bk = nb["breakdown"]
    aa = (nb.get("details", {})
            .get("built_beauty", {})
            .get("architectural_analysis", {}) or {})
    return (
        bk["built_beauty_score"],
        bk["natural_beauty_score"],
        bk["density"],
        bk["effective_area_type"],
        aa.get("metrics", {}).get("built_coverage_ratio"),
    )


# ---------------------------------------------------------------------------
# True suburbs — score should rise under new formula (BCR ceiling lowers
# built_weight, shifting blend toward stronger natural scores).
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name,lo,hi", [
    ("Ardsley",   73, 79),
    ("Pelham",    65, 72),
    ("Great Neck", 76, 81),
    ("Montclair", 79, 83),
    ("Larchmont", 82, 86),
])
def test_suburb_score_rises(name, lo, hi):
    built, nat, density, eff, bcr = _extract(name)
    result = blend_scores(built, nat, density, eff, bcr)
    score = result["score"]
    assert lo <= score <= hi, (
        f"{name}: expected {lo}–{hi}, got {score:.1f} "
        f"(built={built:.1f}, nat={nat:.1f}, w={result['built_weight']:.3f}, bcr={bcr})"
    )


# ---------------------------------------------------------------------------
# Floor-protected historic suburb — floor=0.65 keeps weight stable; score
# should be roughly unchanged vs. old formula.
# ---------------------------------------------------------------------------

def test_bronxville_stable():
    built, nat, density, eff, bcr = _extract("Bronxville")
    result = blend_scores(built, nat, density, eff, bcr)
    assert 75 <= result["score"] <= 79, (
        f"Bronxville: expected 75–79, got {result['score']:.1f}"
    )
    # Floor must be the binding constraint, not the ceiling.
    assert result["built_weight"] >= 0.65, (
        f"Bronxville: floor should hold built_weight ≥ 0.65, got {result['built_weight']:.3f}"
    )


# ---------------------------------------------------------------------------
# Best-in-class historic urban — modest drop acceptable, must stay excellent.
# Over-correction guard: score must not fall below 91.
# ---------------------------------------------------------------------------

def test_west_village_stays_excellent():
    built, nat, density, eff, bcr = _extract("West Village")
    result = blend_scores(built, nat, density, eff, bcr)
    assert 91 <= result["score"] <= 96, (
        f"West Village: expected 91–96, got {result['score']:.1f}"
    )


def test_brooklyn_heights_stays_excellent():
    built, nat, density, eff, bcr = _extract("Brooklyn Heights")
    result = blend_scores(built, nat, density, eff, bcr)
    assert 88 <= result["score"] <= 93, (
        f"Brooklyn Heights: expected 88–93, got {result['score']:.1f}"
    )


# ---------------------------------------------------------------------------
# Dense place mislabeled suburban (high BCR) — ceiling still applies via BCR,
# modest drop is correct; should not swing more than 5 points.
# ---------------------------------------------------------------------------

def test_hoboken_slight_drop():
    built, nat, density, eff, bcr = _extract("Hoboken")
    result = blend_scores(built, nat, density, eff, bcr)
    assert 69 <= result["score"] <= 74, (
        f"Hoboken: expected 69–74, got {result['score']:.1f}"
    )


# ---------------------------------------------------------------------------
# Directional invariants — suburbs must rank higher than current after change.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["Ardsley", "Pelham", "Great Neck", "Larchmont", "Montclair"])
def test_suburb_scores_higher_than_old_formula(name):
    """New formula must improve every true suburb vs. density-only formula."""
    built, nat, density, eff, bcr = _extract(name)
    old = blend_scores(built, nat, density, eff, None)   # no BCR = old behaviour
    new = blend_scores(built, nat, density, eff, bcr)
    assert new["score"] > old["score"], (
        f"{name}: new score {new['score']:.1f} should exceed old {old['score']:.1f}"
    )


# ---------------------------------------------------------------------------
# Weight mechanics
# ---------------------------------------------------------------------------

def test_bcr_ceiling_caps_density():
    """A high-density place with low BCR must not exceed the BCR-derived ceiling."""
    # Simulate a place with very high density (would push w near 0.95) but low BCR.
    w = _combined_weight(density=100_000, effective_area_type="suburban",
                         built_coverage_ratio=0.10)
    expected_ceiling = 0.25 + 0.70 * (0.10 / 0.50)
    assert abs(w - expected_ceiling) < 0.001, (
        f"BCR ceiling not applied: w={w:.3f}, expected ≤{expected_ceiling:.3f}"
    )


def test_floor_overrides_ceiling():
    """urban_core/historic_urban floor must win even when BCR ceiling is lower."""
    w = _combined_weight(density=500, effective_area_type="urban_core",
                         built_coverage_ratio=0.05)
    assert w >= 0.65, f"Floor not applied: w={w:.3f}"


def test_no_bcr_falls_back_to_density_only():
    """When BCR is None, behaviour is identical to the old density-only formula."""
    w_new = _combined_weight(density=10_000, effective_area_type="suburban",
                             built_coverage_ratio=None)
    w_old = _combined_weight(density=10_000, effective_area_type="suburban")
    assert w_new == w_old, f"BCR=None should match old formula: {w_new} vs {w_old}"
