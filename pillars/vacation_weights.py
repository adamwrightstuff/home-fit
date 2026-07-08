"""
Vacation mode: pillar set and weight presets by trip type.
Used by main.py when mode=vacation is passed to /score.
"""

from typing import Dict, List, Optional

VACATION_PILLAR_SET = frozenset({
    "natural_beauty",
    "active_outdoors",
    "neighborhood_amenities",
    "air_travel_access",
    "climate_risk",
    "built_environment",  # stored as "built_environment" in response; fetch is triggered by alias in _include_pillar
    "healthcare_access",
})

# Weights must sum to 100 for each preset.
VACATION_WEIGHT_PRESETS: Dict[str, Dict[str, float]] = {
    "beach": {
        "natural_beauty": 28.0,       # ocean/water signal dominant
        "active_outdoors": 22.0,      # beach/water recreation
        "neighborhood_amenities": 20.0,  # food, nightlife
        "air_travel_access": 15.0,    # getting there
        "climate_risk": 10.0,         # hurricanes/heat matter
        "built_environment": 3.0,
        "healthcare_access": 2.0,
    },
    "mountain": {
        "natural_beauty": 32.0,       # scenery is the point
        "active_outdoors": 30.0,      # trails, skiing, climbing
        "air_travel_access": 12.0,
        "neighborhood_amenities": 10.0,
        "climate_risk": 8.0,
        "built_environment": 5.0,
        "healthcare_access": 3.0,
    },
    "city": {
        "neighborhood_amenities": 35.0,  # food/culture/nightlife is the point
        "built_environment": 20.0,     # architecture, streetscape
        "air_travel_access": 15.0,
        "natural_beauty": 12.0,
        "active_outdoors": 8.0,
        "climate_risk": 7.0,
        "healthcare_access": 3.0,
    },
    "road_trip": {
        "active_outdoors": 25.0,      # parks, scenery stops
        "natural_beauty": 25.0,
        "neighborhood_amenities": 20.0,  # food, charm towns
        "climate_risk": 12.0,
        "built_environment": 8.0,
        "healthcare_access": 5.0,
        "air_travel_access": 5.0,    # less relevant for road trips
    },
}

VALID_TRIP_TYPES = set(VACATION_WEIGHT_PRESETS.keys())

# Auto-injected natural_beauty_preference by trip type.
# Reweights internal natural_beauty sub-components (ocean/mountains/lakes_rivers/canopy)
# without changing the pillar's overall token weight.
VACATION_NATURAL_BEAUTY_PREFERENCE: Dict[str, Optional[List[str]]] = {
    "beach": ["ocean"],
    "mountain": ["mountains"],
    "road_trip": ["lakes_rivers"],
    "city": None,  # no scenery bias — canopy/streetscape matters more
}


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
