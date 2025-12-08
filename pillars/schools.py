"""
Schools Pillar
Scores school quality and variety
Includes K-12 core scoring with small bonuses for early education and nearby colleges
"""

from typing import Dict, Tuple, Optional, List
from data_sources import schools_api


def get_school_data(
    zip_code: Optional[str] = None,
    state: Optional[str] = None,
    city: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None
) -> Tuple[float, Dict[str, List[Dict]], Dict]:
    """
    Calculate school score (0-100) and return schools by level.
    
    Core K-12 scoring (0-100) with small bonuses:
    - Early education access: +5 points (max)
    - Nearby college/university: +5 points (max)
    - Total capped at 100 after bonuses

    Args:
        zip_code, state, city: For SchoolDigger API
        lat, lon: For OSM queries for early education and colleges

    Returns:
        (average_rating_with_bonuses, schools_by_level, breakdown)
        breakdown contains: base_avg_rating, quality_boost, early_ed_bonus, college_bonus
    """
    print(f"📚 Fetching school data...")

    # Get schools from API
    schools = schools_api.get_schools(zip_code, state, city)

    if not schools:
        print("⚠️  No schools found")
        return 0.0, {"elementary": [], "middle": [], "high": []}, {
            "base_avg_rating": 0.0,
            "quality_boost": 0.0,
            "early_ed_bonus": 0.0,
            "college_bonus": 0.0
        }

    print(f"📦 {len(schools)} schools found")
    
    # Check if any schools have rating data
    schools_with_ratings = 0
    for school in schools:
        rank_history = school.get("rankHistory", [])
        if rank_history and len(rank_history) > 0:
            rank_stars = rank_history[0].get("rankStars")
            if rank_stars is not None and rank_stars > 0:
                schools_with_ratings += 1
    
    if schools_with_ratings == 0:
        print(f"⚠️  Found {len(schools)} schools but none have rating data")
        print("   Sample school data:", school.get("schoolName", "Unknown") if schools else "No schools")
        return 0.0, {"elementary": [], "middle": [], "high": []}, {
            "base_avg_rating": 0.0,
            "quality_boost": 0.0,
            "early_ed_bonus": 0.0,
            "college_bonus": 0.0
        }

    # Process and score schools
    schools_by_level = {
        "elementary": [],
        "middle": [],
        "high": []
    }
    all_ratings = []

    for school in schools:
        # Get school info - SchoolDigger API sometimes returns generic "School #ID" in schoolName field
        # Try to construct a more readable name using available data
        name = school.get("schoolName") or school.get("name")
        
        # Check if schoolName is a generic ID format (School #number)
        if name and isinstance(name, str) and name.startswith("School #"):
            # Try to use district + level for better identification
            district = school.get("district", {})
            district_name = district.get("districtName", "") if isinstance(district, dict) else ""
            school_level = school.get("schoolLevel", "")
            
            # If district name exists and isn't also generic, use it
            if district_name and not district_name.startswith("School District #"):
                # Format: "District Name - Level School"
                name = f"{district_name.split(' School')[0]} - {school_level} School" if school_level else district_name.split(' School')[0]
            else:
                # Keep the generic ID format if no better option
                pass
        
        # Final fallback to generic ID if name is still missing
        if not name or (isinstance(name, str) and name.strip() == ""):
            school_id = school.get("schoolid") or school.get("schoolId") or school.get("id")
            if school_id:
                name = f"School #{school_id}"
            else:
                name = "Unknown School"

        school_level = school.get("schoolLevel", "").lower()

        # Get rating from rankHistory
        rating = None
        state_percentile = None
        rank_history = school.get("rankHistory", [])

        if rank_history and len(rank_history) > 0:
            latest_rank = rank_history[0]
            rank_stars = latest_rank.get("rankStars")
            state_percentile = latest_rank.get("rankStatewidePercentage")

            # Use rankStars as primary (most reliable - derived from test scores and comprehensive data)
            # rankStars is SchoolDigger's composite rating (0-5 stars)
            if rank_stars is not None:
                rating = float(rank_stars) * 20  # Convert 0-5 stars to 0-100
            elif state_percentile is not None:
                # Fallback: use state_percentile directly if stars unavailable
                # Higher percentile = better performance
                rating = float(state_percentile)  # Use percentile as score directly

        # Exclude schools without valid ratings (includes private schools without rankHistory)
        # Private schools CAN have ratings in SchoolDigger, but if they don't, exclude them
        is_private = school.get("isPrivate", False)
        if rating is None or rating == 0:
            if is_private:
                print(f"   ⚠️  Excluding {name} - private school with no quality data")
            else:
                print(f"   ⚠️  Excluding {name} - no rating data available")
            continue
            
        # Filter out schools with suspiciously low ratings (likely outside the area or data errors)
        # Only exclude very low ratings (1 star = 20) if we have other schools with better ratings
        # This prevents including schools from neighboring areas that don't represent the district
        # Check if there are other schools in the list with ratings > 20
        has_better_schools = any(
            s.get("rankHistory") and 
            len(s.get("rankHistory", [])) > 0 and
            s["rankHistory"][0].get("rankStars", 0) > 1
            for s in schools if s != school
        )
        
        if rating <= 20 and has_better_schools:
            print(f"   ⚠️  Excluding {name} - rating {rating:.0f}/100 (likely outside query area or data quality issue)")
            continue

        # Get additional details
        rank_movement = school.get("rankMovement")
        trend = "stable"
        if rank_movement is not None:
            if rank_movement > 0:
                trend = "improving"
            elif rank_movement < 0:
                trend = "declining"

        yearly_details = school.get("schoolYearlyDetails", [])
        student_teacher_ratio = None
        enrollment = None

        if yearly_details:
            student_teacher_ratio = yearly_details[0].get("pupilTeacherRatio")
            enrollment = yearly_details[0].get("numberOfStudents")

        school_info = {
            "name": name,
            "rating": round(rating, 2),
            "state_percentile": round(state_percentile, 1) if state_percentile else None,
            "student_teacher_ratio": round(student_teacher_ratio, 1) if student_teacher_ratio else None,
            "trend": trend,
            "enrollment": enrollment,
            "rank_movement": rank_movement
        }

        # Categorize by level
        if "elementary" in school_level or "primary" in school_level:
            schools_by_level["elementary"].append(school_info)
        elif "middle" in school_level:
            schools_by_level["middle"].append(school_info)
        elif "high" in school_level:
            schools_by_level["high"].append(school_info)
        else:
            schools_by_level["elementary"].append(school_info)

        all_ratings.append(rating)

    if not all_ratings:
        print("⚠️  Schools found but no ratings available")
        return 0.0, {"elementary": [], "middle": [], "high": []}, {
            "base_avg_rating": 0.0,
            "quality_boost": 0.0,
            "early_ed_bonus": 0.0,
            "college_bonus": 0.0
        }

    # Sort and keep top 3 per level
    for level in schools_by_level:
        schools_by_level[level].sort(key=lambda x: x["rating"], reverse=True)
        schools_by_level[level] = schools_by_level[level][:3]

    # Calculate average with quality boost for high-performing districts
    # Protect against empty list
    if len(all_ratings) > 0:
        base_avg_rating = sum(all_ratings) / len(all_ratings)
    else:
        base_avg_rating = 0.0
    
    # Count excellent schools (80+) and apply district quality boost
    excellent_schools = sum(1 for r in all_ratings if r >= 80)
    majority_excellent = excellent_schools >= len(all_ratings) * 0.6  # 60%+
    
    # Track quality boost amount
    quality_boost = 0.0
    avg_rating = base_avg_rating
    
    # Boost for districts with multiple highly-rated schools
    # This handles cases where one outlier drags down average
    if base_avg_rating >= 80 and len(all_ratings) >= 3:
        # Excellent district with multiple top schools
        quality_boost = min(10, 100 - base_avg_rating)
        avg_rating = min(100, base_avg_rating + quality_boost)
    elif base_avg_rating >= 70 and excellent_schools >= 3:
        # Very good district: 70+ average with 3+ excellent schools
        # One outlier shouldn't penalize top-tier districts
        quality_boost = min(8, 95 - base_avg_rating)
        avg_rating = min(95, base_avg_rating + quality_boost)
    elif base_avg_rating >= 65 and majority_excellent and len(all_ratings) >= 3:
        # Good district: 65+ average with majority excellent
        quality_boost = min(5, 90 - base_avg_rating)
        avg_rating = min(90, base_avg_rating + quality_boost)
    elif base_avg_rating >= 70 and len(all_ratings) >= 4:
        # Very good district
        quality_boost = min(5, 95 - base_avg_rating)
        avg_rating = min(95, base_avg_rating + quality_boost)

    # Log results
    print(f"\n📚 Schools by Level:")
    for level, schools_list in schools_by_level.items():
        if schools_list:
            print(f"\n  {level.upper()}:")
            for school in schools_list:
                trend_emoji = "📈" if school["trend"] == "improving" else "📉" if school["trend"] == "declining" else "➡️"
                ratio_str = f"({school['student_teacher_ratio']}:1)" if school['student_teacher_ratio'] else ""
                percentile_str = f"[Top {100-school['state_percentile']:.0f}%]" if school['state_percentile'] else ""
                print(
                    f"    {trend_emoji} {school['name']} → {school['rating']:.0f}/100 {ratio_str} {percentile_str}")

    print(
        f"\n✅ Overall avg rating: {avg_rating:.2f} (from {len(all_ratings)} schools)")
    
    # Add bonuses for early education and nearby colleges (if coordinates provided)
    early_ed_bonus = 0.0
    college_bonus = 0.0
    
    if lat is not None and lon is not None:
        try:
            from data_sources import osm_api
            import math
            
            # Query for early education (kindergarten, preschool) within 2km
            early_ed_query = f"""
            [out:json][timeout:20];
            (
              node["amenity"~"kindergarten|preschool|nursery"](around:2000,{lat},{lon});
              way["amenity"~"kindergarten|preschool|nursery"](around:2000,{lat},{lon});
              relation["amenity"~"kindergarten|preschool|nursery"](around:2000,{lat},{lon});
            );
            out body;
            >;
            out skel qt;
            """
            
            try:
                from data_sources.osm_api import get_overpass_url, requests, _retry_overpass
                def _do_request():
                    return requests.post(get_overpass_url(), data={"data": early_ed_query}, timeout=25, headers={"User-Agent":"HomeFit/1.0"})
                # Schools are standard (important but not critical) - use STANDARD profile
                resp = _retry_overpass(_do_request, query_type="schools")
                
                if resp and resp.status_code == 200:
                    data = resp.json()
                    elements = data.get("elements", [])
                    early_ed_count = len([e for e in elements if e.get("type") in ("node", "way", "relation")])
                    
                    if early_ed_count > 0:
                        # Score based on count and proximity
                        closest_distance = float('inf')
                        for elem in elements:
                            if elem.get("type") == "node":
                                elem_lat = elem.get("lat")
                                elem_lon = elem.get("lon")
                                if elem_lat and elem_lon:
                                    dist = math.sqrt((elem_lat - lat)**2 + (elem_lon - lon)**2) * 111000  # rough meters
                                    closest_distance = min(closest_distance, dist)
                        
                        # Bonus: 0-5 points based on count and distance
                        if early_ed_count >= 3:
                            early_ed_bonus = 5.0
                        elif early_ed_count >= 2:
                            early_ed_bonus = 3.0
                        elif early_ed_count >= 1:
                            early_ed_bonus = 2.0
                        
                        # Reduce bonus if far away
                        if closest_distance < float('inf') and closest_distance > 1000:
                            early_ed_bonus *= 0.7  # 30% reduction if >1km away
                        
                        print(f"   🎓 Early education bonus: +{early_ed_bonus:.1f} ({early_ed_count} facilities)")
            except Exception as e:
                print(f"   ⚠️  Early education query failed: {e}")
            
            # Query for colleges/universities within 10km
            college_query = f"""
            [out:json][timeout:20];
            (
              node["amenity"~"university|college"](around:10000,{lat},{lon});
              way["amenity"~"university|college"](around:10000,{lat},{lon});
              relation["amenity"~"university|college"](around:10000,{lat},{lon});
            );
            out body;
            >;
            out skel qt;
            """
            
            try:
                def _do_request():
                    return requests.post(get_overpass_url(), data={"data": college_query}, timeout=25, headers={"User-Agent":"HomeFit/1.0"})
                # Schools are standard (important but not critical) - use STANDARD profile
                resp = _retry_overpass(_do_request, query_type="schools")
                
                if resp and resp.status_code == 200:
                    data = resp.json()
                    elements = data.get("elements", [])
                    college_count = len([e for e in elements if e.get("type") in ("node", "way", "relation")])
                    
                    if college_count > 0:
                        # Score based on count and proximity
                        closest_distance = float('inf')
                        for elem in elements:
                            if elem.get("type") == "node":
                                elem_lat = elem.get("lat")
                                elem_lon = elem.get("lon")
                                if elem_lat and elem_lon:
                                    dist = math.sqrt((elem_lat - lat)**2 + (elem_lon - lon)**2) * 111000  # rough meters
                                    closest_distance = min(closest_distance, dist)
                        
                        # Bonus: 0-5 points based on count and distance
                        if college_count >= 2:
                            college_bonus = 5.0
                        elif college_count >= 1:
                            # Distance-based scoring
                            if closest_distance < float('inf'):
                                if closest_distance <= 2000:
                                    college_bonus = 5.0
                                elif closest_distance <= 5000:
                                    college_bonus = 3.0
                                elif closest_distance <= 10000:
                                    college_bonus = 2.0
                            else:
                                college_bonus = 3.0
                        
                        print(f"   🎓 College/university bonus: +{college_bonus:.1f} ({college_count} institutions)")
            except Exception as e:
                print(f"   ⚠️  College query failed: {e}")
        except Exception as e:
            print(f"   ⚠️  Bonus calculation failed: {e}")
    
    # Apply bonuses (capped at 100)
    total_score = avg_rating + early_ed_bonus + college_bonus
    total_score = min(100.0, total_score)
    
    if early_ed_bonus > 0 or college_bonus > 0:
        print(f"   📈 Score with bonuses: {total_score:.2f} (base: {avg_rating:.2f}, bonuses: +{early_ed_bonus + college_bonus:.1f})")

    # Build breakdown dictionary
    breakdown = {
        "base_avg_rating": round(base_avg_rating, 2),
        "quality_boost": round(quality_boost, 2),
        "early_ed_bonus": round(early_ed_bonus, 2),
        "college_bonus": round(college_bonus, 2),
        "total_schools_rated": len(all_ratings),
        "excellent_schools_count": excellent_schools
    }

    return round(total_score, 2), schools_by_level, breakdown
