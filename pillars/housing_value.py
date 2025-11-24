"""
Housing Value Pillar
Scores housing value based on local affordability, space, and cost efficiency
"""

from typing import Dict, Tuple, Optional
from data_sources import census_api, data_quality


def get_housing_value_score(lat: float, lon: float, 
                           census_tract: Optional[Dict] = None,
                           density: Optional[float] = None,
                           city: Optional[str] = None) -> Tuple[float, Dict]:
    """
    Calculate housing value score (0-100) based on affordability and space.

    Scoring:
    - Local Affordability (0-50): Home price ÷ local income
    - Space/Size (0-30): Median rooms per unit
    - Value Efficiency (0-20): Usable space per dollar (rooms per $100k)

    Args:
        census_tract: Pre-computed census tract data (optional, will fetch if None)
        density: Pre-computed population density (optional, will fetch if None)
        city: City name for data quality assessment (optional)

    Returns:
        (total_score, detailed_breakdown)
    """
    print(f"🏠 Analyzing housing value...")

    # Get housing data from Census (pass pre-computed tract if available)
    housing_data = census_api.get_housing_data(lat, lon, tract=census_tract)

    if housing_data is None:
        print("⚠️  Housing data unavailable")
        return 0, _empty_breakdown()

    median_value = housing_data["median_home_value"]
    median_income = housing_data["median_household_income"]
    median_rooms = housing_data["median_rooms"]

    # Detect metro area for contextual adjustments
    metro_name = None
    if city:
        try:
            from data_sources.regional_baselines import regional_baseline_manager
            metro_name = regional_baseline_manager._detect_metro_area(city, lat, lon)
        except Exception:
            pass

    # Score components
    affordability_score = _score_local_affordability(
        median_value, median_income)
    space_score = _score_space(median_rooms)
    efficiency_score = _score_value_efficiency(median_value, median_rooms, metro_name)

    total_score = affordability_score + space_score + efficiency_score

    # Assess data quality
    combined_data = {
        'housing_data': housing_data,
        'total_score': total_score
    }
    
    # Use pre-computed density if provided, otherwise fetch
    if density is None:
        density = census_api.get_population_density(lat, lon) or 0.0
    
    # Detect actual area type for data quality assessment
    # Use provided city if available for better classification
    area_type = data_quality.detect_area_type(lat, lon, density, city=city)
    quality_metrics = data_quality.assess_pillar_data_quality('housing_value', combined_data, lat, lon, area_type)

    # Build response
    breakdown = {
        "score": round(total_score, 1),
        "breakdown": {
            "local_affordability": round(affordability_score, 1),
            "space": round(space_score, 1),
            "value_efficiency": round(efficiency_score, 1)
        },
        "summary": _build_summary(median_value, median_income, median_rooms),
        "data_quality": quality_metrics
    }

    # Log results
    print(f"✅ Housing Value Score: {total_score:.0f}/100")
    print(f"   💰 Local Affordability: {affordability_score:.0f}/50")
    print(f"   🏡 Space: {space_score:.0f}/30")
    print(f"   📊 Value Efficiency: {efficiency_score:.0f}/20")
    print(f"   📊 Data Quality: {quality_metrics['quality_tier']} ({quality_metrics['confidence']}% confidence)")

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


def _score_value_efficiency(home_value: float, median_rooms: float, metro_name: Optional[str] = None) -> float:
    """
    Score value efficiency (0-20 points).
    Reframed as "usable space per dollar" rather than cheapness.
    Uses smooth scoring to avoid double-penalizing high-cost metros.

    Higher rooms per $100k = better value (more usable space per dollar)
    """
    if median_rooms == 0 or home_value == 0:
        return 0.0

    # Calculate rooms per $100k (positive metric: higher = better)
    rooms_per_100k = (median_rooms / home_value) * 100000

    # Metro-specific adjustments: high-cost metros get more forgiving thresholds
    # This prevents double-penalization (affordability already penalizes them)
    # 
    # RATIONALE: This adjustment is based on the observation that larger metros (>2M population)
    # tend to have higher home values, which is already reflected in the affordability component.
    # Without this adjustment, high-cost metros would be penalized twice:
    # 1. In affordability (lower score for high home values)
    # 2. In value efficiency (lower score for fewer rooms per $100k)
    # 
    # This is a context-aware adjustment, not location-specific tuning, as it applies to all
    # locations within metros of a given size category.
    # 
    # TODO: Consider replacing with research-backed metro-specific expected values
    metro_adjustment = 1.0
    if metro_name:
        try:
            from data_sources.regional_baselines import regional_baseline_manager
            metro_data = regional_baseline_manager.major_metros.get(metro_name, {})
            if metro_data:
                # High-cost metros (NYC, SF, Boston, etc.) get adjusted thresholds
                # Adjust based on typical home values in major metros
                population = metro_data.get('population', 0)
                if population > 5000000:  # Very large metros tend to be expensive
                    metro_adjustment = 1.5  # More forgiving scoring
                elif population > 2000000:  # Large metros
                    metro_adjustment = 1.3
        except Exception:
            pass

    # Smooth scoring curve using adjusted thresholds
    # Base thresholds (rooms per $100k): 0.5 = excellent, 0.2 = good, 0.1 = moderate
    adjusted_threshold_excellent = 0.5 * metro_adjustment
    adjusted_threshold_good = 0.2 * metro_adjustment
    adjusted_threshold_moderate = 0.1 * metro_adjustment

    # Smooth scoring curve
    if rooms_per_100k >= adjusted_threshold_excellent:
        # Excellent: 0.5+ rooms per $100k (e.g., $200k for 1 room, $400k for 2 rooms)
        # Scale from threshold to 1.0+ rooms per $100k → 18 to 20 points
        if rooms_per_100k >= 1.0:
            return 20.0
        else:
            # Linear interpolation between threshold and 1.0
            range_size = 1.0 - adjusted_threshold_excellent
            if range_size > 0:
                ratio = (rooms_per_100k - adjusted_threshold_excellent) / range_size
                return 18.0 + (2.0 * min(1.0, ratio))
            else:
                return 18.0
    elif rooms_per_100k >= adjusted_threshold_good:
        # Good: 0.2-0.5 rooms per $100k
        # Scale from good to excellent → 14 to 18 points
        range_size = adjusted_threshold_excellent - adjusted_threshold_good
        if range_size > 0:
            ratio = (rooms_per_100k - adjusted_threshold_good) / range_size
            return 14.0 + (4.0 * ratio)
        else:
            return 14.0
    elif rooms_per_100k >= adjusted_threshold_moderate:
        # Moderate: 0.1-0.2 rooms per $100k
        # Scale from moderate to good → 10 to 14 points
        range_size = adjusted_threshold_good - adjusted_threshold_moderate
        if range_size > 0:
            ratio = (rooms_per_100k - adjusted_threshold_moderate) / range_size
            return 10.0 + (4.0 * ratio)
        else:
            return 10.0
    else:
        # Lower: 0.0-0.1 rooms per $100k
        # Scale from 0.0 to moderate → 0 to 10 points
        if rooms_per_100k <= 0:
            return 0.0
        if adjusted_threshold_moderate > 0:
            ratio = rooms_per_100k / adjusted_threshold_moderate
            return 10.0 * min(1.0, ratio)
        else:
            return 0.0


def _build_summary(home_value: float, income: float, rooms: float) -> Dict:
    """Build summary of housing value characteristics."""
    ratio = home_value / income if income > 0 else 0
    cost_per_room = home_value / rooms if rooms > 0 else 0
    rooms_per_100k = (rooms / home_value) * 100000 if home_value > 0 else 0

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
        "rooms_per_100k": round(rooms_per_100k, 3),  # New metric: usable space per dollar
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
