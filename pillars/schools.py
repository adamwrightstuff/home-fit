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
    lon: Optional[float] = None,
    area_type: Optional[str] = None
) -> Tuple[float, Dict[str, List[Dict]], Dict]:
    """
    Calculate school score (0-100) and return schools by level.
    
    Core K-12 scoring (0-100) with small bonuses:
    - Early education access: +5 points (max)
    - Nearby college/university: +5 points (max)
    - Total capped at 100 after bonuses

    Args:
        zip_code, state, city: For SchoolDigger API
        lat, lon: For coordinate-based queries and OSM queries for early education and colleges
        area_type: For determining conservative search radius (urban_core, suburban, etc.)

    Returns:
        (average_rating_with_bonuses, schools_by_level, breakdown)
        breakdown contains: base_avg_rating, access_bonus, early_ed_bonus
    """
    print(f"📚 Fetching school data...")

    # Get schools from API using bulletproof approach
    schools = schools_api.get_schools(zip_code, state, city, lat, lon, area_type)

    if not schools:
        print("⚠️  No schools found")
        return 0.0, {"elementary": [], "middle": [], "high": []}, {
            "base_avg_rating": 0.0,
            "access_bonus": 0.0,
            "early_ed_bonus": 0.0,
        }

    print(f"📦 {len(schools)} schools found")
    
    # Check if any schools have rating data (0-star schools count if they have a state percentile)
    schools_with_ratings = 0
    for school in schools:
        rank_history = school.get("rankHistory", [])
        if rank_history and len(rank_history) > 0:
            rank_stars = rank_history[0].get("rankStars")
            state_pct = rank_history[0].get("rankStatewidePercentage")
            if rank_stars is not None and (rank_stars > 0 or state_pct is not None):
                schools_with_ratings += 1

    if schools_with_ratings == 0:
        print(f"⚠️  Found {len(schools)} schools but none have rating data")
        print("   Sample school data:", school.get("schoolName", "Unknown") if schools else "No schools")
        return 0.0, {"elementary": [], "middle": [], "high": []}, {
            "base_avg_rating": 0.0,
            "access_bonus": 0.0,
            "early_ed_bonus": 0.0,
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

            # Use rankStars as primary (0-5 stars → 0-100)
            if rank_stars is not None:
                rating = float(rank_stars) * 20
                # 0-star school: fall back to state percentile so genuinely bad districts
                # score low rather than being excluded entirely (e.g. Lawrence, NY at 8th pct)
                if rating == 0 and state_percentile is not None:
                    rating = float(state_percentile)
            elif state_percentile is not None:
                rating = float(state_percentile)

        # Exclude schools with no rating data at all
        is_private = school.get("isPrivate", False)
        if rating is None:
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
            "access_bonus": 0.0,
            "early_ed_bonus": 0.0,
        }

    # Sort and keep top 3 per level
    for level in schools_by_level:
        schools_by_level[level].sort(key=lambda x: x["rating"], reverse=True)
        schools_by_level[level] = schools_by_level[level][:3]

    # Lower-two-thirds average: removes selective/screened outliers from the base score
    # so families see realistic typical school quality, not inflated by a few elite schools
    import math as _math
    sorted_ratings = sorted(all_ratings)
    n_base = max(1, _math.ceil(len(sorted_ratings) * 2 / 3))
    base_ratings = sorted_ratings[:n_base]
    top_ratings = sorted_ratings[n_base:]
    base_avg_rating = sum(base_ratings) / len(base_ratings)
    avg_rating = base_avg_rating

    # Access bonus (0-5 pts): rewards districts with elite selective options available,
    # even though those schools aren't included in the base score
    elite_count = sum(1 for r in top_ratings if r >= 85)
    access_bonus = min(5.0, elite_count * 2.0)

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
        f"\n✅ Lower-2/3 avg: {base_avg_rating:.2f} (base from {len(base_ratings)}/{len(all_ratings)} schools, access_bonus=+{access_bonus:.1f})")
    
    # Early education bonus: preschool/kindergarten proximity matters for families with young kids
    early_ed_bonus = 0.0

    if lat is not None and lon is not None:
        try:
            import math
            from data_sources.osm_api import get_overpass_url, requests, _retry_overpass

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

            def _do_request():
                return requests.post(get_overpass_url(), data={"data": early_ed_query}, timeout=25, headers={"User-Agent": "HomeFit/1.0"})

            resp = _retry_overpass(_do_request, query_type="schools")
            if resp and resp.status_code == 200:
                elements = resp.json().get("elements", [])
                early_ed_count = len([e for e in elements if e.get("type") in ("node", "way", "relation")])
                if early_ed_count > 0:
                    closest_distance = float('inf')
                    for elem in elements:
                        if elem.get("type") == "node" and elem.get("lat") and elem.get("lon"):
                            dist = math.sqrt((elem["lat"] - lat)**2 + (elem["lon"] - lon)**2) * 111000
                            closest_distance = min(closest_distance, dist)
                    if early_ed_count >= 3:
                        early_ed_bonus = 3.0
                    elif early_ed_count >= 2:
                        early_ed_bonus = 2.0
                    elif early_ed_count >= 1:
                        early_ed_bonus = 1.0
                    if closest_distance > 1000:
                        early_ed_bonus *= 0.7
                    print(f"   🎓 Early education bonus: +{early_ed_bonus:.1f} ({early_ed_count} facilities)")
        except Exception as e:
            print(f"   ⚠️  Early education query failed: {e}")

    # Apply bonuses (capped at 100)
    total_score = min(100.0, avg_rating + access_bonus + early_ed_bonus)

    if access_bonus > 0 or early_ed_bonus > 0:
        print(f"   📈 Score with bonuses: {total_score:.2f} (base: {avg_rating:.2f}, access: +{access_bonus:.1f}, early_ed: +{early_ed_bonus:.1f})")

    # Build breakdown dictionary
    breakdown = {
        "base_avg_rating": round(base_avg_rating, 2),
        "access_bonus": round(access_bonus, 2),
        "early_ed_bonus": round(early_ed_bonus, 2),
        "total_schools_rated": len(all_ratings),
        "elite_schools_count": elite_count
    }

    return round(total_score, 2), schools_by_level, breakdown
