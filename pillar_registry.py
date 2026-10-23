"""Single source of truth for which keys are pillars and which are filters.

Kept at the repo root with no imports so scripts and the API can use it without
loading the pillars package. frontend/lib/pillars.ts PILLAR_ORDER mirrors
SCORED_PILLARS and must be updated by hand when this changes.
"""

from __future__ import annotations

from typing import Tuple

# The 13 scored pillars, in frontend display order.
SCORED_PILLARS: Tuple[str, ...] = (
    "quality_education",
    "neighborhood_amenities",
    "economic_opportunity",
    "climate_risk",
    "active_outdoors",
    "natural_beauty",
    "diversity",
    "social_fabric",
    "healthcare_access",
    "public_transit_access",
    "air_travel_access",
    "housing_value",
    "community_safety",
)

# Opt-in filters. They take a priority like a pillar but are not scored pillars.
FILTER_PILLARS: Tuple[str, ...] = (
    "built_environment",
    "political_lean",
)

# Every key the agent accepts a priority for.
PRIORITY_KEYS: Tuple[str, ...] = SCORED_PILLARS + FILTER_PILLARS
