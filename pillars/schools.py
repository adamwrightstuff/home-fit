"""
Schools Pillar
Scores school quality and variety
Includes K-12 core scoring with small bonuses for early education and nearby colleges
"""

from typing import Any, Dict, Tuple, Optional, List
from data_sources import schools_api


import math as _math

MIN_RATED_FOR_SPLIT = 3  # a public-only or charter-only view with fewer rated schools is flagged thin


def score_from_ratings(ratings: List[float], early_ed_bonus: float = 0.0) -> Dict[str, float]:
    """
    The education formula on a list of school ratings (0-100): mean of the lower two thirds, plus
    an access bonus (+2 per rating >= 85 in the upper third, capped at +5), plus the early-ed bonus.
    Used by the live scorer and by the public/charter split so both always agree.
    """
    sorted_ratings = sorted(ratings)
    n_base = max(1, _math.ceil(len(sorted_ratings) * 2 / 3))
    base_ratings = sorted_ratings[:n_base]
    top_ratings = sorted_ratings[n_base:]
    base_avg = sum(base_ratings) / len(base_ratings)
    elite_count = sum(1 for r in top_ratings if r >= 85)
    access_bonus = min(5.0, elite_count * 2.0)
    return {
        "base_avg_rating": base_avg,
        "access_bonus": access_bonus,
        "elite_count": elite_count,
        "n_base": n_base,
        "score": min(100.0, base_avg + access_bonus + early_ed_bonus),
    }


def split_scores(rated_schools: List[Dict], early_ed_bonus: float = 0.0) -> Dict[str, Dict]:
    """
    Public-only and charter-only scores from the stored rated schools (same formula as the total).
    'public' = schools without the charter flag; independent charters are public schools in law
    but are separated here because they admit by lottery rather than by address.
    confidence: 'ok' (>= 3 rated), 'thin' (1-2), 'none' (0, score is None).
    """
    out: Dict[str, Dict] = {}
    for key, want_charter in (("public", False), ("charter", True)):
        ratings = [float(s["rating"]) for s in rated_schools
                   if bool(s.get("is_charter_school")) == want_charter and s.get("rating") is not None]
        if not ratings:
            out[key] = {"score": None, "n_rated": 0, "confidence": "none"}
            continue
        r = score_from_ratings(ratings, early_ed_bonus)
        out[key] = {
            "score": round(r["score"], 2),
            "n_rated": len(ratings),
            "confidence": "ok" if len(ratings) >= MIN_RATED_FOR_SPLIT else "thin",
        }
    return out


def _early_ed_bonus(lat: Optional[float], lon: Optional[float]) -> float:
    """Early-education bonus (0-3): preschools/kindergartens within 2 km (OSM), x0.7 if the nearest is over 1 km."""
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
    return early_ed_bonus


def _get_school_data_legacy(
    zip_code: Optional[str] = None,
    state: Optional[str] = None,
    city: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    area_type: Optional[str] = None,
    place_name: Optional[str] = None
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
    schools = schools_api.get_schools(zip_code, state, city, lat, lon, area_type, place_name)

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
    rated_schools = []  # every school that feeds the score (by_level keeps only the top 3 per level)

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
            "rank_movement": rank_movement,
            "is_charter_school": school.get("isCharterSchool") == "Yes",
        }

        # Categorize by level
        if "elementary" in school_level or "primary" in school_level:
            _lvl = "elementary"
        elif "middle" in school_level:
            _lvl = "middle"
        else:
            _lvl = "high" if "high" in school_level else "elementary"
        rated_schools.append({
            "name": name,
            "level": _lvl,
            "rating": round(rating, 2),
            "is_charter_school": school_info["is_charter_school"],
        })
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
    # Access bonus (0-5 pts): rewards districts with elite selective options available,
    # even though those schools aren't included in the base score
    _r = score_from_ratings(all_ratings)
    base_avg_rating = _r["base_avg_rating"]
    avg_rating = base_avg_rating
    elite_count = _r["elite_count"]
    access_bonus = _r["access_bonus"]
    base_ratings = all_ratings[:_r["n_base"]]  # count only, used in the log line below

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
    
    early_ed_bonus = _early_ed_bonus(lat, lon)

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
        "elite_schools_count": elite_count,
        "rated_schools": rated_schools,
        "split": split_scores(rated_schools, early_ed_bonus),
    }

    return round(total_score, 2), schools_by_level, breakdown


# ---------------------------------------------------------------------------------------------
# Zoned model (zoned_v1)
#   Headline = mean over levels (elementary, middle, high) of that level's score.
#   A level's score = the zoned school's statewide percentile when a zone map assigns one and it is
#   rated; otherwise the mean of the nearest 3 rated non-charter schools of that level in the home
#   district, widening the radius to a 3 mile cap. Charters are choice options: listed and scored
#   separately (split.charter), not in the headline. Early-education bonus still applies.
# ---------------------------------------------------------------------------------------------
LEVELS = ("elementary", "middle", "high")
NEAREST_PER_LEVEL = 3
WIDEN_CAP_MILES = 3.0
CHOICE_LIST_MAX = 6
MODEL = "zoned_v1"


def school_rating(school: Dict) -> Optional[float]:
    """Statewide percentile (0-100); stars x 20 only when a school has no percentile."""
    rh = (school.get("rankHistory") or [{}])[0] if school.get("rankHistory") else {}
    pct, stars = rh.get("rankStatewidePercentage"), rh.get("rankStars")
    if pct is not None:
        return round(float(pct), 2)
    if stars is not None:
        return float(stars) * 20.0
    return None


def _level_of(school: Dict) -> Optional[str]:
    t = (school.get("schoolLevel") or "").lower()
    if "elementary" in t or "primary" in t:
        return "elementary"
    if "middle" in t:
        return "middle"
    if "high" in t:
        return "high"
    return None


def _entry(school: Dict, role: str) -> Dict:
    rh = (school.get("rankHistory") or [{}])[0] if school.get("rankHistory") else {}
    return {
        "name": school.get("schoolName") or "Unknown School",
        "level": _level_of(school),
        "rating": school_rating(school),
        "stars": rh.get("rankStars"),
        "is_charter_school": school.get("isCharterSchool") == "Yes",
        "distance_mi": round(float(school["distance"]), 2) if school.get("distance") is not None else None,
        "role": role,
    }


def headline_from_levels(levels: Dict[str, Dict], early_ed_bonus: float = 0.0) -> Optional[float]:
    scores = [v["score"] for v in levels.values() if v.get("score") is not None]
    if not scores:
        return None
    return min(100.0, sum(scores) / len(scores) + early_ed_bonus)


def build_levels(pool: List[Dict], zoned: List[Dict], base_radius_miles: float) -> Dict[str, Dict]:
    """Per-level result: zoned school when available and rated, else nearest 3 in the home district."""
    from data_sources.school_zones import match_zoned_to_schools
    from data_sources.schools_api import _is_rated_school

    elem_factor = 2.1 / 3.2   # NHTS 2017 median trip: elementary 2.1 mi vs middle 3.2 mi
    out: Dict[str, Dict] = {}
    for level in LEVELS:
        z = next((x for x in zoned if x["level"] == level), None) or \
            next((x for x in zoned if level in x.get("also_serves", [])), None)
        res: Dict[str, Any] = {"source": None, "score": None, "schools": [], "zone": None}
        if z:
            res["zone"] = {"name": z["name"], "vintage": z["vintage"], "caveat": z["caveat"], "matched": False}
            m = match_zoned_to_schools(z, pool)
            if m is not None and _is_rated_school(m) and school_rating(m) is not None:
                res.update(source="zone", schools=[_entry(m, "zoned")])
                res["zone"]["matched"] = True
        if not res["schools"]:
            cand = sorted(
                (sc for sc in pool if _level_of(sc) == level and _is_rated_school(sc)
                 and sc.get("isCharterSchool") != "Yes" and sc.get("distance") is not None),
                key=lambda sc: float(sc["distance"]))
            base = base_radius_miles * (elem_factor if level == "elementary" else 1.0)
            picked: List[Dict] = []
            for r in sorted({base, base * 1.5, base * 2.0, WIDEN_CAP_MILES}):
                if r < base or r > max(WIDEN_CAP_MILES, base):
                    continue
                picked = [sc for sc in cand if float(sc["distance"]) <= r][:NEAREST_PER_LEVEL]
                if len(picked) >= NEAREST_PER_LEVEL:
                    break
            if picked:
                res.update(source="nearest", schools=[_entry(sc, "nearest") for sc in picked])
        ratings = [e["rating"] for e in res["schools"] if e["rating"] is not None]
        res["score"] = round(sum(ratings) / len(ratings), 2) if ratings else None
        out[level] = res
    return out


def get_school_data(
    zip_code: Optional[str] = None,
    state: Optional[str] = None,
    city: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    area_type: Optional[str] = None,
    place_name: Optional[str] = None,
) -> Tuple[float, Dict[str, List[Dict]], Dict]:
    """
    Education score (0-100), schools by level, breakdown. Uses the zoned model when the point has
    Census district data; otherwise the legacy radius model (places outside the boundary files).
    """
    print("📚 Fetching school data (zoned model)...")
    cands = schools_api.get_zone_candidates(lat, lon, state, area_type) if (lat is not None and state) else None
    if not cands:
        print("   no district boundary data for this point; using the legacy lookup")
        return _get_school_data_legacy(zip_code, state, city, lat, lon, area_type, place_name)

    from data_sources.school_zones import zoned_schools
    zoned = zoned_schools(lat, lon)
    levels = build_levels(cands["pool"], zoned, cands["radius_miles"])
    early = _early_ed_bonus(lat, lon)
    total = headline_from_levels(levels, early)
    if total is None:
        print("⚠️  No rated schools for any level")
        return 0.0, {"elementary": [], "middle": [], "high": []}, {
            "model": MODEL, "base_avg_rating": 0.0, "access_bonus": 0.0, "early_ed_bonus": 0.0,
            "levels": levels, "districts": cands["districts"],
        }

    used = {lv: [e for e in v["schools"]] for lv, v in levels.items()}
    used_names = {e["name"] for es in used.values() for e in es}
    choice = []
    for sc in sorted(cands["charters"], key=lambda x: float(x.get("distance") or 99)):
        if _level_of(sc) and school_rating(sc) is not None:
            e = _entry(sc, "choice")
            if e["name"] not in used_names and len(choice) < CHOICE_LIST_MAX:
                choice.append(e)
    n_levels = sum(1 for v in levels.values() if v["score"] is not None)
    charter_ratings = [e["rating"] for e in choice]
    split = {
        "public": {"score": round(total, 2), "n_rated": sum(len(v["schools"]) for v in levels.values()),
                   "confidence": "ok" if n_levels >= 2 else "thin"},
        "charter": ({"score": round(sum(charter_ratings) / len(charter_ratings), 2), "n_rated": len(choice),
                     "confidence": "ok" if len(choice) >= MIN_RATED_FOR_SPLIT else "thin"}
                    if choice else {"score": None, "n_rated": 0, "confidence": "none"}),
    }
    rated_schools = [e for es in used.values() for e in es] + choice
    base_avg = sum(v["score"] for v in levels.values() if v["score"] is not None) / n_levels
    breakdown = {
        "model": MODEL,
        "base_avg_rating": round(base_avg, 2),
        "access_bonus": 0.0,
        "early_ed_bonus": round(early, 2),
        "total_schools_rated": len(rated_schools),
        "elite_schools_count": sum(1 for e in rated_schools if (e["rating"] or 0) >= 85),
        "levels": levels,
        "choice": choice,
        "rated_schools": rated_schools,
        "split": split,
        "districts": cands["districts"],
    }
    by_level = {lv: sorted(used[lv], key=lambda e: -(e["rating"] or 0)) for lv in LEVELS}
    return round(total, 2), by_level, breakdown
