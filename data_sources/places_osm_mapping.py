"""
Map Google Places (New) primary types to OSM-style neighborhood_amenities business records.

Only types we can place in a tier with confidence are included; unknown types are skipped.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

# (tier_key, business_type) — matches keys used by osm_api._process_business_features
GOOGLE_TYPE_TO_TIER: Dict[str, Tuple[str, str]] = {
    # tier1_daily
    "cafe": ("tier1_daily", "cafe"),
    "bakery": ("tier1_daily", "bakery"),
    "supermarket": ("tier1_daily", "grocery"),
    "grocery_store": ("tier1_daily", "grocery"),
    # tier2_social
    "restaurant": ("tier2_social", "restaurant"),
    "meal_takeaway": ("tier2_social", "restaurant"),
    "bar": ("tier2_social", "bar"),
    "night_club": ("tier2_social", "bar"),
    "liquor_store": ("tier2_social", "bar"),
    # tier3_culture
    "book_store": ("tier3_culture", "bookstore"),
    "museum": ("tier3_culture", "museum"),
    "art_gallery": ("tier3_culture", "gallery"),
    "movie_theater": ("tier3_culture", "theater"),
    "library": ("tier3_culture", "bookstore"),
    # tier4_services
    "gym": ("tier4_services", "fitness"),
    "clothing_store": ("tier4_services", "boutique"),
    "hair_care": ("tier4_services", "salon"),
    "florist": ("tier4_services", "garden"),
    "spa": ("tier4_services", "salon"),
}

# When multiple Google types apply, prefer more specific amenity types first.
_TYPE_MATCH_ORDER: List[str] = [
    "supermarket",
    "grocery_store",
    "cafe",
    "bakery",
    "restaurant",
    "meal_takeaway",
    "bar",
    "night_club",
    "liquor_store",
    "book_store",
    "museum",
    "art_gallery",
    "movie_theater",
    "library",
    "gym",
    "clothing_store",
    "hair_care",
    "florist",
    "spa",
]


def resolve_tier_and_type_from_google_types(types: Optional[List[str]]) -> Optional[Tuple[str, str]]:
    """
    Given Places `types` array, return (tier_key, business_type) or None if unmappable.
    """
    if not types:
        return None
    tset = set(types)
    for gt in _TYPE_MATCH_ORDER:
        if gt in tset:
            return GOOGLE_TYPE_TO_TIER[gt]
    return None


def included_types_for_nearby_search() -> List[str]:
    """All mapped Google types (union of `included_type_batches_for_nearby_search()`)."""
    return list(dict.fromkeys(GOOGLE_TYPE_TO_TIER.keys()))


def included_type_batches_for_nearby_search() -> List[List[str]]:
    """
    Disjoint type groups for multiple searchNearby calls (default five).

    Each batch uses OR semantics within the request; Google caps maxResultCount at 20 per request.
    All keys in GOOGLE_TYPE_TO_TIER appear exactly once across batches.
    """
    return [
        ["supermarket", "grocery_store", "cafe", "bakery"],
        ["restaurant", "meal_takeaway", "bar", "night_club", "liquor_store"],
        ["book_store", "museum", "art_gallery", "movie_theater", "library"],
        ["gym", "clothing_store", "hair_care", "florist"],
        ["spa"],
    ]
