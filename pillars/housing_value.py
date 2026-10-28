"""
Housing Value Pillar
Scores housing value based on local affordability, space, and cost efficiency
"""

from typing import Dict, Tuple, Optional
from data_sources import census_api, data_quality
from data_sources.zillow_home_values import get_home_value, CENSUS_CAP


def get_housing_value_score(lat: float, lon: float,
                           census_tract: Optional[Dict] = None,
                           density: Optional[float] = None,
                           city: Optional[str] = None,
                           zip_code: Optional[str] = None,
                           use_national_income_for_affordability: bool = False,
                           user_household_income: Optional[int] = None) -> Tuple[float, Dict]:
    """
    Calculate housing value score (0-100) based on affordability and space.

    Scoring:
    - Local Affordability (0-50): Home price ÷ income denominator
    - Space/Size (0-30): Median rooms per unit
    - Value Efficiency (0-20): Usable space per dollar (rooms per $100k)

    Income denominator priority: user_household_income > us_median (when use_national_income_for_affordability) > local median.

    Args:
        census_tract: Pre-computed census tract data (optional, will fetch if None)
        density: Pre-computed population density (optional, will fetch if None)
        city: City name for data quality assessment (optional)
        use_national_income_for_affordability: If True, use US median household income for affordability
            (for remote/flexible workers; same home price vs national income).
        user_household_income: If set, use this as the income denominator for affordability
            (personalizes the score to the user's actual income).

    Returns:
        (total_score, detailed_breakdown)
    """
    print(f"🏠 Analyzing housing value...")

    if density is None:
        density = census_api.get_population_density(lat, lon) or 0.0
    area_type = data_quality.detect_area_type(lat, lon, density, city=city)

    # Get housing data from Census (pass pre-computed tract if available)
    # HOMEFIT_HOUSING_POOLED (default off): pool the tracts within 0.43 mile of the pin instead of the pin's single
    # tract (audit D14). Passed as an argument so cached single-tract results are never served for it.
    import os
    pooled = os.getenv("HOMEFIT_HOUSING_POOLED", "").strip().lower() in ("1", "true", "yes")
    housing_data = census_api.get_housing_data(lat, lon, tract=census_tract, area_type=area_type, pooled=pooled)

    if housing_data is None:
        # No median household income for the pin's tract (suppressed by the ACS) and the place-level data
        # is not usable. That is no data: the pillar fails and drops out of the total. It used to return a
        # hard-coded score by area type (45 to 65), which was invented and biased upward in dense cities.
        raise RuntimeError(
            f"No Census housing data for ({lat}, {lon}): median household income unavailable at the tract"
        )

    median_value = housing_data["median_home_value"]
    median_value, _zillow_used = get_home_value(median_value, zip_code)
    if _zillow_used:
        print(f"   📊 Zillow ZHVI override: Census capped at ${CENSUS_CAP:,} → Zillow ${median_value:,} (ZIP {zip_code})")
    median_income = housing_data["median_household_income"]
    median_rooms = housing_data["median_rooms"]
    median_gross_rent = housing_data.get("median_gross_rent")
    renter_pct = housing_data.get("renter_pct")
    housing_geo_level = housing_data.get("geo_level")

    # Income denominator priority: user_household_income > us_median > local_median
    affordability_denominator = "local_median"
    if user_household_income is not None and user_household_income > 0:
        median_income_for_affordability = float(user_household_income)
        affordability_denominator = "user_income"
    elif use_national_income_for_affordability:
        from data_sources.normalization import load_economic_baselines
        baselines = load_economic_baselines()
        national_income = baselines.get("us_median_household_income")
        if isinstance(national_income, (int, float)) and national_income > 0:
            median_income_for_affordability = float(national_income)
        else:
            median_income_for_affordability = 91016.0  # ACS 2022 1-year US median fallback
        affordability_denominator = "us_median"
    else:
        median_income_for_affordability = median_income

    # Detect metro area for contextual adjustments
    metro_name = None
    if city:
        try:
            from data_sources.regional_baselines import regional_baseline_manager
            metro_name = regional_baseline_manager._detect_metro_area(city, lat, lon)
        except Exception:
            pass

    # Affordability blend: weight owner and renter components by the neighborhood's actual
    # tenure mix. Suburban users are mostly buyers (low renter_pct → owner-dominated score);
    # urban users are mostly renters (high renter_pct → rent-dominated score). No threshold
    # judgment needed — the neighborhood's own B25003 tenure split determines the weight.
    # Value efficiency is an ownership concept only, so it scales by owner share.
    # Fallback to pure owner or pure rent path when one data source is missing.
    owner_pct = (1.0 - renter_pct) if renter_pct is not None else None
    has_rent = median_gross_rent is not None and median_gross_rent > 0
    has_value = median_value is not None

    if has_value and has_rent and owner_pct is not None:
        # Blended path
        owner_afford = _score_local_affordability(median_value, median_income_for_affordability)
        rent_afford = _score_rent_affordability(median_gross_rent, median_income_for_affordability)
        affordability_score = (
            owner_pct * owner_afford + renter_pct * rent_afford
            if owner_afford is not None and rent_afford is not None else None
        )
        space_score = _score_space(median_rooms)
        _eff = _score_value_efficiency(median_value, median_rooms, metro_name)
        efficiency_score = _eff * owner_pct if _eff is not None else None
        print(f"   ℹ️  Blended affordability ({owner_pct:.0%} owner / {renter_pct:.0%} renter)")
    elif not has_value and has_rent:
        # No owner value — rent-only (classic renter-dominant tract). Value efficiency is an ownership measure,
        # so with no owner-occupied value it is 0 by the formula (a design choice, see tracker D11), but it
        # still needs a room count to be defined.
        affordability_score = _score_rent_affordability(median_gross_rent, median_income_for_affordability)
        space_score = _score_space(median_rooms)
        efficiency_score = 0.0 if space_score is not None else None
        print(f"   ℹ️  Rent-only affordability (no owner value reported, rent=${int(median_gross_rent):,}/mo)")
    else:
        # Owner value only — pure owner path
        affordability_score = _score_local_affordability(median_value, median_income_for_affordability)
        space_score = _score_space(median_rooms)
        efficiency_score = _score_value_efficiency(median_value, median_rooms, metro_name)

    # Fail loudly: a component that cannot be computed is left out and the rest are scaled to 100 (identical to
    # the plain sum when all three are present). Affordability is required and at least one more component is
    # needed, otherwise there is no score. Nothing is scored as zero because it is missing.
    _components = {
        "local_affordability": (affordability_score, 50.0),
        "space": (space_score, 30.0),
        "value_efficiency": (efficiency_score, 20.0),
    }
    _present = {k: v for k, v in _components.items() if v[0] is not None}
    _missing = [k for k in _components if k not in _present]
    if "local_affordability" not in _present or len(_present) < 2:
        raise RuntimeError(
            f"Housing value: not enough data to score for ({lat}, {lon}) (missing: {', '.join(_missing)})"
        )
    total_score = sum(v[0] for v in _present.values()) * (100.0 / sum(v[1] for v in _present.values()))

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
    if _missing:
        quality_metrics["degraded"] = True
        quality_metrics["degraded_reasons"] = list(quality_metrics.get("degraded_reasons") or []) + [
            f"housing_value_components_missing: {', '.join(_missing)}"
        ]

    # Build response (summary uses income denominator that was used for affordability)
    summary_income = median_income_for_affordability if affordability_denominator == "us_median" else median_income
    breakdown = {
        "score": round(total_score, 1),
        "breakdown": {
            "local_affordability": round(affordability_score, 1) if affordability_score is not None else None,
            "space": round(space_score, 1) if space_score is not None else None,
            "value_efficiency": round(efficiency_score, 1) if efficiency_score is not None else None
        },
        "summary": _build_summary(median_value, summary_income, median_rooms,
                                   affordability_denominator=affordability_denominator,
                                   median_gross_rent=median_gross_rent if has_rent else None,
                                   renter_pct=renter_pct),
        "data_quality": quality_metrics,
        "area_classification": {}
    }
    if housing_data.get("mean_household_income") is not None:
        breakdown["summary"] = {**(breakdown["summary"] or {}), "mean_household_income": housing_data["mean_household_income"]}
    if housing_geo_level:
        breakdown["summary"]["geo_level"] = housing_geo_level

    # Log results
    print(f"✅ Housing Value Score: {total_score:.0f}/100")
    print(f"   💰 Local Affordability: {_fmt0(affordability_score)}/50")
    print(f"   🏡 Space: {_fmt0(space_score)}/30")
    print(f"   📊 Value Efficiency: {_fmt0(efficiency_score)}/20")
    print(f"   📊 Data Quality: {quality_metrics['quality_tier']} ({quality_metrics['confidence']}% confidence)")

    return round(total_score, 1), breakdown


def _fmt0(v):
    return f"{v:.0f}" if v is not None else "n/a"


def _score_rent_affordability(monthly_rent: float, annual_income: float) -> Optional[float]:
    """
    Score affordability (0-50 points) for renter-dominant tracts using rent-to-income ratio.
    Standard: 30% of income on housing is the threshold for cost-burden.
    """
    if not annual_income or annual_income <= 0 or not monthly_rent or monthly_rent <= 0:
        return None
    ratio = (monthly_rent * 12) / annual_income
    if ratio <= 0.20:
        return 50.0   # <20%: very affordable
    elif ratio <= 0.25:
        return 43.0   # 20-25%: comfortable
    elif ratio <= 0.30:
        return 35.0   # 25-30%: standard threshold
    elif ratio <= 0.35:
        return 25.0   # 30-35%: slightly burdened
    elif ratio <= 0.40:
        return 15.0   # 35-40%: cost-burdened
    elif ratio <= 0.50:
        return 7.0    # 40-50%: severely burdened
    else:
        return 0.0    # >50%: extreme burden


def _score_local_affordability(home_value: Optional[float], income: float) -> Optional[float]:
    """
    Score local affordability (0-50 points).
    Based on price-to-income ratio.

    Standard: Housing should be ≤3x annual income
    """
    if home_value is None or not income or income <= 0:
        return None

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


def _score_space(median_rooms: Optional[float]) -> Optional[float]:
    """
    Score housing space (0-30 points).
    Based on median rooms per unit.

    Census rooms = all rooms except bathrooms, halls, closets. None when the room count is unavailable.
    """
    if median_rooms is None or median_rooms <= 0:
        return None
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


def _score_value_efficiency(home_value: Optional[float], median_rooms: Optional[float], metro_name: Optional[str] = None) -> Optional[float]:
    """
    Score value efficiency (0-20 points).
    Reframed as "usable space per dollar" rather than cheapness.
    Uses smooth scoring to avoid double-penalizing high-cost metros.

    Higher rooms per $100k = better value (more usable space per dollar)
    """
    if home_value is None or not median_rooms or median_rooms <= 0 or home_value <= 0:
        return None

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


def _build_summary(home_value: Optional[float], income: float, rooms: float, *, affordability_denominator: str = "local_median", median_gross_rent: Optional[float] = None, renter_pct: Optional[float] = None) -> Dict:
    """Build summary of housing value characteristics."""
    ratio = (home_value / income) if (home_value is not None and income > 0) else 0
    cost_per_room = (home_value / rooms) if (home_value is not None and rooms and rooms > 0) else 0
    rooms_per_100k = ((rooms / home_value) * 100000) if (home_value is not None and home_value > 0 and rooms) else 0

    # Determine housing type based on rooms
    if not rooms:
        housing_type = "Unknown"
    elif rooms >= 7:
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
    if home_value is None:
        affordability = "Unknown"
    elif ratio <= 3:
        affordability = "Affordable"
    elif ratio <= 5:
        affordability = "Moderate"
    else:
        affordability = "Expensive"

    out: Dict = {
        "median_home_value": int(home_value) if home_value is not None else None,
        "median_household_income": int(income),
        "median_rooms": round(rooms, 1) if rooms else None,
        "price_to_income_ratio": round(ratio, 2),
        "cost_per_room": int(cost_per_room),
        "rooms_per_100k": round(rooms_per_100k, 3),
        "housing_type": housing_type,
        "affordability_rating": affordability
    }
    if affordability_denominator == "us_median":
        out["affordability_denominator"] = "us_median"
    if renter_pct is not None:
        out["renter_pct"] = round(renter_pct, 3)
    if median_gross_rent is not None:
        out["median_gross_rent"] = int(median_gross_rent)
        out["affordability_basis"] = "rent"
    return out


def _add_geo_level_to_summary(breakdown: Dict, geo_level: Optional[str]) -> None:
    if geo_level and "summary" in breakdown:
        breakdown["summary"]["geo_level"] = geo_level


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
        },
        "data_quality": {},
        "area_classification": {}
    }
