"""
Built Beauty golden set regression tests.

These tests are *live* integration checks: they call the real scoring pipeline,
which may hit external data sources (OSM Overpass, Census, etc.).

To run locally:
  RUN_LIVE_GOLDEN_BUILT_BEAUTY=1 python3 -m pytest -q tests/test_built_beauty_golden_set.py
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import pytest

from pillars.built_beauty import calculate_built_beauty


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_GOLDEN_BUILT_BEAUTY") != "1",
    reason="Live Built Beauty golden set disabled. Set RUN_LIVE_GOLDEN_BUILT_BEAUTY=1 to run.",
)


@dataclass(frozen=True)
class GoldenLocation:
    name: str
    lat: float
    lon: float
    expected_range: Tuple[float, float]
    current_note: Optional[str] = None


GOLDEN_LOCATIONS = [
    # HIGH SCORERS (65-85)
    GoldenLocation("Beacon Hill, Boston", 42.3588, -71.0707, (68, 75), current_note="Current ~69"),
    GoldenLocation("French Quarter, NOLA", 29.9584, -90.0644, (70, 80)),
    GoldenLocation("Georgetown, DC", 38.9072, -77.0659, (65, 75)),
    GoldenLocation("National Mall, DC", 38.8893, -77.0502, (75, 85)),
    GoldenLocation("Charleston Historic District", 32.7765, -79.9311, (70, 80)),
    # MEDIUM SCORERS (45-65)
    GoldenLocation("Palm Springs modernist area", 33.8303, -116.5453, (55, 65)),
    GoldenLocation("Greenwich Village, NYC", 40.7336, -74.0027, (60, 70)),
    GoldenLocation("Savannah Historic", 32.0809, -81.0912, (65, 75)),
    # LOW-MEDIUM (35-50)
    GoldenLocation("Laurel Canyon, LA", 34.1192, -118.3774, (35, 50), current_note="Current ~36"),
    GoldenLocation("Levittown, NY", 40.7259, -73.5143, (35, 45), current_note="Current ~40"),
    # LOW SCORERS (<40)
    GoldenLocation("Generic strip mall", 33.9137, -118.4064, (20, 35)),
    GoldenLocation("New suburban development (Irvine, CA)", 33.6846, -117.8265, (30, 40)),
]


def _compact_debug(result: Dict) -> Dict:
    details = result.get("details") or {}
    arch = details.get("architectural_analysis") or {}
    return {
        "score": result.get("score"),
        "score_before_normalization": result.get("score_before_normalization"),
        "component_score_0_50": result.get("component_score_0_50"),
        "built_bonus_scaled": result.get("built_bonus_scaled"),
        "effective_area_type": result.get("effective_area_type"),
        "arch_score_0_50": arch.get("score"),
        "arch_confidence_0_1": arch.get("confidence_0_1"),
        "metrics": arch.get("metrics"),
        "historic_context": arch.get("historic_context"),
        "bonus_breakdown": arch.get("bonus_breakdown"),
        "data_quality": result.get("data_quality"),
    }


@pytest.mark.parametrize("loc", GOLDEN_LOCATIONS, ids=lambda x: x.name)
def test_built_beauty_golden_location_in_expected_range(loc: GoldenLocation) -> None:
    result = calculate_built_beauty(loc.lat, loc.lon, location_name=loc.name)
    score = float(result.get("score") or 0.0)
    lo, hi = loc.expected_range

    assert lo <= score <= hi, (
        f"{loc.name} score {score:.1f} outside expected range [{lo}, {hi}].\n"
        f"Debug: {_compact_debug(result)}"
    )

