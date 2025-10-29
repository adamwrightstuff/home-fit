"""
Schools Pillar
Scores school quality and variety
"""

from typing import Dict, Tuple, Optional, List
from data_sources import schools_api


def get_school_data(
    zip_code: Optional[str] = None,
    state: Optional[str] = None,
    city: Optional[str] = None
) -> Tuple[float, Dict[str, List[Dict]]]:
    """
    Calculate school score (0-100) and return schools by level.

    Returns:
        (average_rating, schools_by_level)
    """
    print(f"📚 Fetching school data...")

    # Get schools from API
    schools = schools_api.get_schools(zip_code, state, city)

    if not schools:
        print("⚠️  No schools found")
        return 0.0, {"elementary": [], "middle": [], "high": []}

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
        return 0.0, {"elementary": [], "middle": [], "high": []}

    # Process and score schools
    schools_by_level = {
        "elementary": [],
        "middle": [],
        "high": []
    }
    all_ratings = []

    for school in schools:
        # Exclude private schools - SchoolDigger doesn't have quality/rating data for private schools
        is_private = school.get("isPrivate", False)
        if is_private:
            print(f"   ⚠️  Excluding {school.get('schoolName', 'Unknown')} - private school (no quality data available)")
            continue
        
        # Get school info - prioritize schoolName, fallback to name, avoid using IDs
        name = school.get("schoolName")
        if not name:
            name = school.get("name")
        if not name:
            # Only use ID as last resort with "School #" prefix
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

            if rank_stars is not None:
                rating = float(rank_stars) * 20  # Convert 0-5 stars to 0-100

        if rating is None or rating == 0:
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
        return 0.0, {"elementary": [], "middle": [], "high": []}

    # Sort and keep top 3 per level
    for level in schools_by_level:
        schools_by_level[level].sort(key=lambda x: x["rating"], reverse=True)
        schools_by_level[level] = schools_by_level[level][:3]

    # Calculate average with quality boost for high-performing districts
    avg_rating = sum(all_ratings) / len(all_ratings)
    
    # Count excellent schools (80+) and apply district quality boost
    excellent_schools = sum(1 for r in all_ratings if r >= 80)
    majority_excellent = excellent_schools >= len(all_ratings) * 0.6  # 60%+
    
    # Boost for districts with multiple highly-rated schools
    # This handles cases where one outlier drags down average
    if avg_rating >= 80 and len(all_ratings) >= 3:
        # Excellent district with multiple top schools
        avg_rating = min(100, avg_rating + 10)
    elif avg_rating >= 70 and excellent_schools >= 3:
        # Very good district: 70+ average with 3+ excellent schools
        # One outlier shouldn't penalize top-tier districts
        avg_rating = min(95, avg_rating + 8)
    elif avg_rating >= 65 and majority_excellent and len(all_ratings) >= 3:
        # Good district: 65+ average with majority excellent
        avg_rating = min(90, avg_rating + 5)
    elif avg_rating >= 70 and len(all_ratings) >= 4:
        # Very good district
        avg_rating = min(95, avg_rating + 5)

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

    return round(avg_rating, 2), schools_by_level
