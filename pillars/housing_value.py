"""
Housing Value Pillar
Scores housing value based on local affordability, space, and cost efficiency
"""

from typing import Dict, Tuple, Optional
from data_sources import census_api


def get_housing_value_score(lat: float, lon: float) -> Tuple[float, Dict]:
    """
    Calculate housing value score (0-100) based on affordability and space.

    Scoring:
    - Local Affordability (0-50): Home price ÷ local income
    - Space/Size (0-30): Median rooms per unit
    - Value Efficiency (0-20): Cost per room

    Returns:
        (total_score, detailed_breakdown)
    """
    print(f"🏠 Analyzing housing value...")

    # Get housing data from Census
    housing_data = census_api.get_housing_data(lat, lon)

    if housing_data is None:
        print("⚠️  Housing data unavailable")
        return 0, _empty_breakdown()

    median_value = housing_data["median_home_value"]
    median_income = housing_data["median_household_income"]
    median_rooms = housing_data["median_rooms"]

    # Score components
    affordability_score = _score_local_affordability(
        median_value, median_income)
    space_score = _score_space(median_rooms)
    efficiency_score = _score_value_efficiency(median_value, median_rooms)

    total_score = affordability_score + space_score + efficiency_score

    # Build response
    breakdown = {
        "score": round(total_score, 1),
        "breakdown": {
            "local_affordability": round(affordability_score, 1),
            "space": round(space_score, 1),
            "value_efficiency": round(efficiency_score, 1)
        },
        "summary": _build_summary(median_value, median_income, median_rooms)
    }

    # Log results
    print(f"✅ Housing Value Score: {total_score:.0f}/100")
    print(f"   💰 Local Affordability: {affordability_score:.0f}/50")
    print(f"   🏡 Space: {space_score:.0f}/30")
    print(f"   📊 Value Efficiency: {efficiency_score:.0f}/20")

    return round(total_score, 1), breakdown


def _score_local_affordability(home_value: float, income: float) -> float:
    """
    Score local affordability (0-50 points).
    Based on price-to-income ratio.

    Standard: Housing should be ≤3x annual income
    """
    if income == 0:
        return 0.0

    ratio = home_value / income

    if ratio <= 2.0:
        return 50.0  # Very affordable
    elif ratio <= 2.5:
        return 45.0
    elif ratio <= 3.0:
        return 40.0  # Affordable (standard threshold)
    elif ratio <= 3.5:
        return 35.0
    elif ratio <= 4.0:
        return 30.0  # Moderate
    elif ratio <= 4.5:
        return 25.0
    elif ratio <= 5.0:
        return 20.0  # Expensive
    elif ratio <= 6.0:
        return 15.0
    elif ratio <= 7.0:
        return 10.0  # Very expensive
    else:
        return 5.0   # Extremely expensive


def _score_space(median_rooms: float) -> float:
    """
    Score housing space (0-30 points).
    Based on median rooms per unit.

    Census rooms = all rooms except bathrooms, halls, closets
    """
    if median_rooms >= 8:
        return 30.0  # Large single-family
    elif median_rooms >= 6.5:
        return 25.0  # Typical single-family
    elif median_rooms >= 5.5:
        return 20.0  # Small house or large apartment
    elif median_rooms >= 4.5:
        return 15.0  # 2-bed apartment
    elif median_rooms >= 3.5:
        return 10.0  # 1-bed apartment
    else:
        return 5.0   # Studio/tiny


def _score_value_efficiency(home_value: float, median_rooms: float) -> float:
    """
    Score value efficiency (0-20 points).
    Based on cost per room.

    Lower cost per room = better value
    """
    if median_rooms == 0:
        return 0.0

    cost_per_room = home_value / median_rooms

    # Scoring thresholds (cost per room)
    if cost_per_room <= 40000:
        return 20.0  # Excellent value
    elif cost_per_room <= 60000:
        return 18.0
    elif cost_per_room <= 80000:
        return 16.0
    elif cost_per_room <= 100000:
        return 14.0  # Good value
    elif cost_per_room <= 125000:
        return 12.0
    elif cost_per_room <= 150000:
        return 10.0  # Moderate
    elif cost_per_room <= 200000:
        return 8.0
    elif cost_per_room <= 250000:
        return 6.0   # Expensive
    elif cost_per_room <= 300000:
        return 4.0
    else:
        return 2.0   # Very expensive


def _build_summary(home_value: float, income: float, rooms: float) -> Dict:
    """Build summary of housing value characteristics."""
    ratio = home_value / income if income > 0 else 0
    cost_per_room = home_value / rooms if rooms > 0 else 0

    # Determine housing type based on rooms
    if rooms >= 7:
        housing_type = "Large single-family home"
    elif rooms >= 6:
        housing_type = "Typical single-family home"
    elif rooms >= 5:
        housing_type = "Small house or large apartment"
    elif rooms >= 4:
        housing_type = "2-bedroom apartment"
    elif rooms >= 3:
        housing_type = "1-bedroom apartment"
    else:
        housing_type = "Studio or tiny apartment"

    # Determine affordability description
    if ratio <= 3:
        affordability = "Affordable"
    elif ratio <= 5:
        affordability = "Moderate"
    else:
        affordability = "Expensive"

    return {
        "median_home_value": int(home_value),
        "median_household_income": int(income),
        "median_rooms": round(rooms, 1),
        "price_to_income_ratio": round(ratio, 2),
        "cost_per_room": int(cost_per_room),
        "housing_type": housing_type,
        "affordability_rating": affordability
    }


def _empty_breakdown() -> Dict:
    """Return empty breakdown when no data."""
    return {
        "score": 0,
        "breakdown": {
            "local_affordability": 0,
            "space": 0,
            "value_efficiency": 0
        },
        "summary": {
            "median_home_value": 0,
            "median_household_income": 0,
            "median_rooms": 0,
            "price_to_income_ratio": 0,
            "cost_per_room": 0,
            "housing_type": "Unknown",
            "affordability_rating": "Unknown"
        }
    }
