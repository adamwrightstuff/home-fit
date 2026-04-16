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
    "convenience_store": ("tier1_daily", "grocery"),
    # tier2_social
    "restaurant": ("tier2_social", "restaurant"),
    "meal_takeaway": ("tier2_social", "restaurant"),
    "food": ("tier2_social", "restaurant"),
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
    "beauty_salon": ("tier4_services", "salon"),
    "florist": ("tier4_services", "garden"),
    "spa": ("tier4_services", "salon"),
    "hardware_store": ("tier4_services", "boutique"),
}

# When multiple Google types apply, prefer more specific amenity types first.
_TYPE_MATCH_ORDER: List[str] = [
    "supermarket",
    "grocery_store",
    "convenience_store",
    "cafe",
    "bakery",
    "restaurant",
    "meal_takeaway",
    "food",
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
    "hardware_store",
    "hair_care",
    "beauty_salon",
    "florist",
    "spa",
]

# Per-tier filters for Places policy (urban stop-early; suburban tier3+4 follow-up).
# Use only types that exist in GOOGLE_TYPE_TO_TIER so responses map into scoring tiers.
TIER_PLACE_TYPES: Dict[str, List[str]] = {
    "tier1": ["cafe", "bakery", "grocery_store", "supermarket", "convenience_store"],
    "tier2": ["restaurant", "bar", "food", "meal_takeaway", "night_club", "liquor_store"],
    "tier3": ["book_store", "museum", "art_gallery", "movie_theater", "library"],
    "tier4": ["gym", "hair_care", "beauty_salon", "clothing_store", "florist", "spa", "hardware_store"],
}


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
    Disjoint type groups (legacy batch layout tests). All mapped types once across five batches.

    Each batch uses OR semantics within the request; Google caps maxResultCount at 20 per request.
    """
    return [
        ["supermarket", "grocery_store", "cafe", "bakery", "convenience_store"],
        ["restaurant", "meal_takeaway", "food", "bar", "night_club", "liquor_store"],
        ["book_store", "museum", "art_gallery", "movie_theater", "library"],
        ["gym", "clothing_store", "hair_care", "beauty_salon", "florist", "hardware_store"],
        ["spa"],
    ]


def tier3_and_tier4_place_types() -> List[str]:
    """Types for suburban second call (tier3 ∪ tier4), stable order, deduped."""
    seen: set = set()
    out: List[str] = []
    for t in TIER_PLACE_TYPES["tier3"] + TIER_PLACE_TYPES["tier4"]:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out
