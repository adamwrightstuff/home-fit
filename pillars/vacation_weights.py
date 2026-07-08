"""
Vacation mode: pillar sets and weight presets by trip type.
Used by main.py when mode=vacation is passed to /score.
"""

from typing import Dict, FrozenSet, List, Optional

# Per-trip-type pillar sets. built_environment is only meaningful for city/road_trip
# (streetscape, architecture); it carries no useful signal for beach or mountain trips.
VACATION_PILLAR_SETS: Dict[str, FrozenSet[str]] = {
    "beach": frozenset({
        "natural_beauty",
        "active_outdoors",
        "neighborhood_amenities",
        "air_travel_access",
        "climate_risk",
        "healthcare_access",
    }),
    "mountain": frozenset({
        "natural_beauty",
        "active_outdoors",
        "neighborhood_amenities",
        "air_travel_access",
        "climate_risk",
        "healthcare_access",
    }),
    "city": frozenset({
        "natural_beauty",
        "active_outdoors",
        "neighborhood_amenities",
        "air_travel_access",
        "climate_risk",
        "built_environment",
        "healthcare_access",
    }),
    "road_trip": frozenset({
        "natural_beauty",
        "active_outdoors",
        "neighborhood_amenities",
        "air_travel_access",
        "climate_risk",
        "built_environment",
        "healthcare_access",
    }),
}

# Weights must sum to 100 for each preset.
# beach/mountain have 6 pillars; city/road_trip have 7.
VACATION_WEIGHT_PRESETS: Dict[str, Dict[str, float]] = {
    "beach": {
        "natural_beauty": 30.0,       # ocean/water signal dominant; freed 3pts from built_env
        "active_outdoors": 24.0,      # beach/water recreation; freed 2pts
        "neighborhood_amenities": 21.0,
        "air_travel_access": 15.0,
        "climate_risk": 8.0,
        "healthcare_access": 2.0,
    },
    "mountain": {
        "natural_beauty": 35.0,       # scenery is the point; freed 5pts from built_env
        "active_outdoors": 32.0,      # trails, skiing, climbing; freed 1pt
        "air_travel_access": 12.0,
        "neighborhood_amenities": 10.0,
        "climate_risk": 8.0,
        "healthcare_access": 3.0,
    },
    "city": {
        "neighborhood_amenities": 35.0,  # food/culture/nightlife is the point
        "built_environment": 20.0,       # architecture, streetscape — meaningful here
        "air_travel_access": 15.0,
        "natural_beauty": 12.0,
        "active_outdoors": 8.0,
        "climate_risk": 7.0,
        "healthcare_access": 3.0,
    },
    "road_trip": {
        "active_outdoors": 25.0,         # parks, scenery stops
        "natural_beauty": 25.0,
        "neighborhood_amenities": 20.0,  # food, charm towns
        "climate_risk": 12.0,
        "built_environment": 8.0,        # small town character matters
        "healthcare_access": 5.0,
        "air_travel_access": 5.0,
    },
}

VALID_TRIP_TYPES = set(VACATION_WEIGHT_PRESETS.keys())

# Auto-injected natural_beauty_preference by trip type.
VACATION_NATURAL_BEAUTY_PREFERENCE: Dict[str, Optional[List[str]]] = {
    "beach": ["ocean"],
    "mountain": ["mountains"],
    "road_trip": ["lakes_rivers"],
    "city": None,
}


def get_vacation_pillar_set(trip_type: Optional[str]) -> FrozenSet[str]:
    """Return the pillar set for the given trip type, defaulting to city."""
    key = (trip_type or "city").lower().strip()
    return VACATION_PILLAR_SETS.get(key, VACATION_PILLAR_SETS["city"])


def get_vacation_token_allocation(trip_type: Optional[str]) -> Dict[str, float]:
    """Return token allocation dict for the given trip type, defaulting to city."""
    key = (trip_type or "city").lower().strip()
    if key not in VACATION_WEIGHT_PRESETS:
        key = "city"
    return dict(VACATION_WEIGHT_PRESETS[key])


def get_vacation_natural_beauty_preference(trip_type: Optional[str]) -> Optional[List[str]]:
    """Return natural_beauty_preference list for the given trip type, or None."""
    key = (trip_type or "city").lower().strip()
    return VACATION_NATURAL_BEAUTY_PREFERENCE.get(key)
