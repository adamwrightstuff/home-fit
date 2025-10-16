import os
import requests
from typing import Optional, Tuple, List, Dict

SCHOOLDIGGER_BASE = "https://api.schooldigger.com/v2.0"

def get_school_data(
    zip_code: Optional[str] = None,
    state: Optional[str] = None,
    city: Optional[str] = None
) -> Tuple[float, Dict[str, List[Dict]]]:
    """
    Query SchoolDigger API and return average rating + schools by level.
    
    Returns:
        (average_rating, schools_by_level)
        where schools_by_level is {
            "elementary": [{name, rating, ...}, ...],
            "middle": [{name, rating, ...}, ...],
            "high": [{name, rating, ...}, ...]
        }
    """
    app_id = os.getenv("SCHOOLDIGGER_APPID")
    app_key = os.getenv("SCHOOLDIGGER_APPKEY")
    
    if not app_id or not app_key:
        print("⚠️  SchoolDigger credentials missing")
        return 0.0, {"elementary": [], "middle": [], "high": []}
    
    # Normalize inputs
    if zip_code:
        zip_code = zip_code.split("-")[0].strip()  # Handle ZIP+4
    if state:
        state = state.strip().upper()
    if city:
        city = city.strip()
    
    # Build query params
    params = {
        "appID": app_id,
        "appKey": app_key,
        "perPage": 50  # Get more schools for better averaging
    }
    
    # Try different query strategies
    schools = []
    
    # Strategy 1: ZIP + State (most reliable)
    if zip_code and state:
        print(f"📡 Fetching SchoolDigger data for {zip_code}, {state}...")
        params_zip = {**params, "zip": zip_code, "st": state}
        schools = _fetch_schools(params_zip)
        if schools:
            print(f"📦 {len(schools)} schools found (ZIP+State)")
    
    # Strategy 2: City + State (fallback)
    if not schools and city and state:
        print(f"📡 Trying SchoolDigger with city: {city}, {state}...")
        params_city = {**params, "city": city, "st": state}
        schools = _fetch_schools(params_city)
        if schools:
            print(f"📦 {len(schools)} schools found (City+State)")
    
    # Strategy 3: Just ZIP (last resort)
    if not schools and zip_code:
        print(f"📡 Trying SchoolDigger with ZIP only: {zip_code}...")
        params_zip_only = {**params, "zip": zip_code}
        schools = _fetch_schools(params_zip_only)
        if schools:
            print(f"📦 {len(schools)} schools found (ZIP only)")
    
    if not schools:
        print("⚠️  No schools found for this location")
        return 0.0, {"elementary": [], "middle": [], "high": []}
    
    # Process schools and organize by level
    schools_by_level = {
        "elementary": [],
        "middle": [],
        "high": []
    }
    all_ratings = []
    
    for school in schools:
        # Try multiple possible name fields
        name = (
            school.get("schoolName") or 
            school.get("name") or 
            school.get("schoolname") or
            "Unknown School"
        )
        
        # Get school level
        school_level = school.get("schoolLevel", "").lower()
        
        # Try to get rating from rankHistory (most recent year)
        rating = None
        state_percentile = None
        rank_history = school.get("rankHistory", [])
        
        if rank_history and len(rank_history) > 0:
            latest_rank = rank_history[0]
            rank_stars = latest_rank.get("rankStars")
            state_percentile = latest_rank.get("rankStatewidePercentage")
            
            if rank_stars is not None:
                # Convert 0-5 stars to 0-100 scale
                rating = float(rank_stars) * 20
        
        # Get rank movement (trend)
        rank_movement = school.get("rankMovement")
        trend = "stable"
        if rank_movement is not None:
            if rank_movement > 0:
                trend = "improving"
            elif rank_movement < 0:
                trend = "declining"
        
        # Get student/teacher ratio from most recent year
        student_teacher_ratio = None
        yearly_details = school.get("schoolYearlyDetails", [])
        if yearly_details and len(yearly_details) > 0:
            student_teacher_ratio = yearly_details[0].get("pupilTeacherRatio")
        
        # Get enrollment
        enrollment = None
        if yearly_details and len(yearly_details) > 0:
            enrollment = yearly_details[0].get("numberOfStudents")
        
        # Only include schools with valid ratings
        if rating is not None and rating > 0:
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
                # If level unclear, add to elementary as default
                schools_by_level["elementary"].append(school_info)
            
            all_ratings.append(rating)
    
    if not all_ratings:
        print("⚠️  Schools found but no ratings available")
        return 0.0, {"elementary": [], "middle": [], "high": []}
    
    # Sort each level by rating (descending) and keep top 3
    for level in schools_by_level:
        schools_by_level[level].sort(key=lambda x: x["rating"], reverse=True)
        schools_by_level[level] = schools_by_level[level][:3]  # Top 3 per level
    
    # Calculate average across all schools
    avg_rating = sum(all_ratings) / len(all_ratings)
    
    # Log results by level
    print(f"\n📚 Schools by Level:")
    for level, schools_list in schools_by_level.items():
        if schools_list:
            print(f"\n  {level.upper()}:")
            for school in schools_list:
                trend_emoji = "📈" if school["trend"] == "improving" else "📉" if school["trend"] == "declining" else "➡️"
                ratio_str = f"({school['student_teacher_ratio']}:1)" if school['student_teacher_ratio'] else ""
                percentile_str = f"[Top {100-school['state_percentile']:.0f}%]" if school['state_percentile'] else ""
                print(f"    {trend_emoji} {school['name']} → {school['rating']:.0f}/100 {ratio_str} {percentile_str}")
    
    print(f"\n✅ Overall avg rating: {avg_rating:.2f} (from {len(all_ratings)} schools)")
    
    return round(avg_rating, 2), schools_by_level


def _fetch_schools(params: Dict) -> List[Dict]:
    """Helper to fetch schools with error handling."""
    try:
        url = f"{SCHOOLDIGGER_BASE}/schools"
        resp = requests.get(url, params=params, timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            return data.get("schoolList", [])
        else:
            print(f"⚠️  SchoolDigger API error: {resp.status_code}")
            return []
    except Exception as e:
        print(f"⚠️  SchoolDigger request failed: {e}")
        return []