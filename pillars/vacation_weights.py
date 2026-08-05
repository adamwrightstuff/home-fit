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

# Traveler profile weight overrides.  AT fixed at 15% across all profiles.
# Remaining 85% redistributed per profile × trip type.
# beach/mountain: 6 pillars (no built_environment).  city: 7 pillars.
TRAVELER_PROFILE_WEIGHTS: Dict[str, Dict[str, Dict[str, float]]] = {
    "adventurer": {
        "beach":    {"active_outdoors": 36.0, "natural_beauty": 26.0, "neighborhood_amenities": 8.0,  "air_travel_access": 15.0, "healthcare_access": 7.0,  "climate_risk": 8.0},
        "mountain": {"active_outdoors": 44.0, "natural_beauty": 28.0, "neighborhood_amenities": 4.0,  "air_travel_access": 15.0, "healthcare_access": 5.0,  "climate_risk": 4.0},
        "city":     {"active_outdoors": 24.0, "built_environment": 8.0, "natural_beauty": 12.0, "neighborhood_amenities": 20.0, "air_travel_access": 15.0, "healthcare_access": 8.0, "climate_risk": 13.0},
    },
    "relaxer": {
        "beach":    {"active_outdoors": 10.0, "natural_beauty": 44.0, "neighborhood_amenities": 18.0, "air_travel_access": 15.0, "healthcare_access": 3.0,  "climate_risk": 10.0},
        "mountain": {"active_outdoors": 15.0, "natural_beauty": 50.0, "neighborhood_amenities": 8.0,  "air_travel_access": 15.0, "healthcare_access": 3.0,  "climate_risk": 9.0},
        "city":     {"active_outdoors": 8.0,  "built_environment": 14.0, "natural_beauty": 22.0, "neighborhood_amenities": 28.0, "air_travel_access": 15.0, "healthcare_access": 5.0, "climate_risk": 8.0},
    },
    "culture": {
        "beach":    {"active_outdoors": 10.0, "natural_beauty": 18.0, "neighborhood_amenities": 48.0, "air_travel_access": 15.0, "healthcare_access": 3.0,  "climate_risk": 6.0},
        "mountain": {"active_outdoors": 12.0, "natural_beauty": 22.0, "neighborhood_amenities": 38.0, "air_travel_access": 15.0, "healthcare_access": 3.0,  "climate_risk": 10.0},
        "city":     {"active_outdoors": 4.0,  "built_environment": 22.0, "natural_beauty": 6.0,  "neighborhood_amenities": 50.0, "air_travel_access": 15.0, "healthcare_access": 3.0, "climate_risk": 0.0},
    },
    "family": {
        "beach":    {"active_outdoors": 18.0, "natural_beauty": 24.0, "neighborhood_amenities": 28.0, "air_travel_access": 15.0, "healthcare_access": 10.0, "climate_risk": 5.0},
        "mountain": {"active_outdoors": 22.0, "natural_beauty": 26.0, "neighborhood_amenities": 18.0, "air_travel_access": 15.0, "healthcare_access": 10.0, "climate_risk": 9.0},
        "city":     {"active_outdoors": 8.0,  "built_environment": 10.0, "natural_beauty": 10.0, "neighborhood_amenities": 30.0, "air_travel_access": 15.0, "healthcare_access": 16.0, "climate_risk": 11.0},
    },
    "remote_worker": {
        "beach":    {"active_outdoors": 12.0, "natural_beauty": 22.0, "neighborhood_amenities": 35.0, "air_travel_access": 15.0, "healthcare_access": 4.0,  "climate_risk": 12.0},
        "mountain": {"active_outdoors": 16.0, "natural_beauty": 24.0, "neighborhood_amenities": 32.0, "air_travel_access": 15.0, "healthcare_access": 4.0,  "climate_risk": 9.0},
        "city":     {"active_outdoors": 5.0,  "built_environment": 18.0, "natural_beauty": 8.0,  "neighborhood_amenities": 40.0, "air_travel_access": 15.0, "healthcare_access": 3.0, "climate_risk": 11.0},
    },
}

VALID_TRAVELER_PROFILES = set(TRAVELER_PROFILE_WEIGHTS.keys())

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


def get_vacation_token_allocation(
    trip_type: Optional[str],
    traveler_profile: Optional[str] = None,
) -> Dict[str, float]:
    """Return token allocation for the given trip type, optionally adjusted by traveler profile."""
    key = (trip_type or "city").lower().strip()
    if key not in VACATION_WEIGHT_PRESETS:
        key = "city"
    if traveler_profile:
        profile_key = traveler_profile.lower().strip()
        profile_trips = TRAVELER_PROFILE_WEIGHTS.get(profile_key, {})
        if key in profile_trips:
            return dict(profile_trips[key])
    return dict(VACATION_WEIGHT_PRESETS[key])


def get_vacation_natural_beauty_preference(trip_type: Optional[str]) -> Optional[List[str]]:
    """Return natural_beauty_preference list for the given trip type, or None."""
    key = (trip_type or "city").lower().strip()
    return VACATION_NATURAL_BEAUTY_PREFERENCE.get(key)
