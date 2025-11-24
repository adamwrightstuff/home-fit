"""
Healthcare Access Pillar
Scores access to hospitals, clinics, pharmacies, and emergency services
"""

import math
from typing import Dict, Tuple, List, Optional
from data_sources import osm_api, data_quality
from data_sources.regional_baselines import get_contextual_expectations
from data_sources.radius_profiles import get_radius_profile
from logging_config import get_logger

logger = get_logger(__name__)

# Comprehensive US hospitals database - major medical centers and regional hospitals
# Covers all major metropolitan areas and many mid-size cities
MAJOR_HOSPITALS = [
    # Northeast
    ("Massachusetts General Hospital", 42.3631, -71.0686, "large"),
    ("NewYork-Presbyterian Hospital", 40.7769, -73.9540, "large"),
    ("NYU Langone Medical Center", 40.7424, -73.9759, "large"),
    ("Mount Sinai Hospital", 40.7903, -73.9529, "large"),
    ("Johns Hopkins Hospital", 39.2971, -76.5929, "large"),
    ("Hospital of the University of Pennsylvania", 39.9496, -75.1955, "large"),
    ("Boston Medical Center", 42.3364, -71.0732, "large"),
    ("Yale-New Haven Hospital", 41.3045, -72.9362, "large"),
    ("Hartford Hospital", 41.7684, -72.6771, "medium"),
    ("Albany Medical Center", 42.6514, -73.7552, "medium"),
    ("Maine Medical Center", 43.6568, -70.2589, "medium"),
    ("Dartmouth-Hitchcock Medical Center", 43.7034, -72.2886, "medium"),
    
    # Southeast
    ("Emory University Hospital", 33.7974, -84.3239, "large"),
    ("Duke University Hospital", 36.0103, -78.9392, "large"),
    ("University of Miami Hospital", 25.7207, -80.2185, "large"),
    ("Shands Hospital at University of Florida", 29.6406, -82.3444, "large"),
    ("Vanderbilt University Medical Center", 36.1447, -86.8027, "large"),
    ("University of Virginia Medical Center", 38.0315, -78.5003, "large"),
    ("Wake Forest Baptist Medical Center", 36.0996, -80.2442, "large"),
    ("Medical University of South Carolina", 32.7846, -79.9498, "large"),
    ("University of Kentucky Hospital", 38.0315, -84.5003, "medium"),
    ("University of Tennessee Medical Center", 35.9442, -83.9401, "medium"),
    ("University of Alabama Hospital", 33.5023, -86.8027, "medium"),
    ("Ochsner Medical Center", 29.9511, -90.0715, "large"),
    
    # Midwest
    ("Northwestern Memorial Hospital", 41.8959, -87.6190, "large"),
    ("University of Chicago Medical Center", 41.7891, -87.6047, "large"),
    ("Cleveland Clinic", 41.5034, -81.6214, "large"),
    ("Mayo Clinic", 44.0225, -92.4660, "large"),
    ("University of Michigan Hospital", 42.2928, -83.7231, "large"),
    ("Ohio State University Hospital", 40.0000, -83.0114, "large"),
    ("Indiana University Health", 39.7684, -86.1581, "large"),
    ("University of Wisconsin Hospital", 43.0731, -89.4012, "large"),
    ("University of Minnesota Medical Center", 44.9778, -93.2650, "large"),
    ("University of Iowa Hospitals", 41.6611, -91.5302, "large"),
    ("University of Kansas Hospital", 39.0458, -94.5844, "medium"),
    ("University of Missouri Hospital", 38.9517, -92.3281, "medium"),
    ("University of Nebraska Medical Center", 41.2565, -95.9345, "medium"),
    ("University of Cincinnati Medical Center", 39.1329, -84.5150, "medium"),
    ("Detroit Medical Center", 42.3314, -83.0458, "large"),
    ("Henry Ford Hospital", 42.3314, -83.0458, "large"),
    
    # Southwest
    ("Methodist Hospital", 29.7098, -95.3984, "large"),
    ("UT Southwestern Medical Center", 32.8174, -96.8358, "large"),
    ("Baylor St. Luke's Medical Center", 29.7098, -95.3984, "large"),
    ("University of Texas Medical Branch", 29.3013, -94.7977, "medium"),
    ("University of New Mexico Hospital", 35.0844, -106.6504, "medium"),
    ("University of Arizona Medical Center", 32.2226, -110.9747, "large"),
    ("University of Oklahoma Medical Center", 35.2220, -97.4395, "medium"),
    ("University of Arkansas Medical Center", 34.7465, -92.2896, "medium"),
    ("University of Texas Health Science Center", 29.7098, -95.3984, "large"),
    
    # West - Major Centers
    ("UCLA Medical Center", 34.0652, -118.4450, "large"),
    ("Cedars-Sinai Medical Center", 34.0753, -118.3767, "large"),
    ("UCSF Medical Center", 37.7625, -122.4579, "large"),
    ("Stanford Hospital", 37.4442, -122.1718, "large"),
    ("University of Washington Medical Center", 47.6501, -122.3054, "large"),
    ("Oregon Health & Science University", 45.4995, -122.6862, "large"),
    
    # West - Colorado (Key Addition!)
    ("University of Colorado Hospital", 39.7439, -104.8303, "large"),
    ("Denver Health Medical Center", 39.7505, -105.0005, "large"),
    ("UCHealth Boulder Community Hospital", 40.0153, -105.2703, "medium"),
    ("Children's Hospital Colorado", 39.7439, -104.8303, "large"),
    ("UCHealth Memorial Hospital", 38.8339, -104.8214, "medium"),
    ("Poudre Valley Hospital", 40.5853, -105.0844, "medium"),
    
    # West - Other Major Centers
    ("University of Utah Hospital", 40.7608, -111.8910, "large"),
    ("University of Nevada Medical Center", 36.1147, -115.1728, "medium"),
    ("University of California Davis Medical Center", 38.5449, -121.7405, "large"),
    ("University of California San Diego Medical Center", 32.7157, -117.1611, "large"),
    ("University of California Irvine Medical Center", 33.6846, -117.8265, "large"),
    ("Harbor-UCLA Medical Center", 33.7890, -118.2944, "large"),
    ("University of California Los Angeles Medical Center", 34.0689, -118.4452, "large"),
    ("University of Washington Harborview Medical Center", 47.6062, -122.3321, "large"),
    ("Swedish Medical Center", 47.6062, -122.3321, "large"),
    ("Virginia Mason Medical Center", 47.6062, -122.3321, "large"),
    ("Providence St. Vincent Medical Center", 45.5152, -122.6784, "large"),
    ("Legacy Emanuel Medical Center", 45.5152, -122.6784, "medium"),
    ("Kaiser Permanente Medical Center", 37.7749, -122.4194, "large"),
    ("Sutter Health California Pacific Medical Center", 37.7749, -122.4194, "large"),
    
    # Major Children's Hospitals
    ("Children's Hospital Los Angeles", 34.0522, -118.2437, "large"),
    ("Children's Hospital of Orange County", 33.6846, -117.8265, "large"),
    ("Rady Children's Hospital", 32.7157, -117.1611, "large"),
    ("Seattle Children's Hospital", 47.6062, -122.3321, "large"),
    ("Doernbecher Children's Hospital", 45.4995, -122.6862, "large"),
    ("Primary Children's Hospital", 40.7608, -111.8910, "large"),
    ("Phoenix Children's Hospital", 33.4484, -112.0740, "large"),
    ("Children's Medical Center Dallas", 32.7767, -96.7970, "large"),
    ("Texas Children's Hospital", 29.7098, -95.3984, "large"),
    ("Children's Healthcare of Atlanta", 33.7490, -84.3880, "large"),
    ("Children's Hospital of Philadelphia", 39.9526, -75.1652, "large"),
    ("Boston Children's Hospital", 42.3601, -71.0589, "large"),
    ("Children's National Medical Center", 38.9072, -77.0369, "large"),
    ("Cincinnati Children's Hospital", 39.1329, -84.5150, "large"),
    ("Nationwide Children's Hospital", 39.9612, -82.9988, "large"),
    ("Children's Hospital of Wisconsin", 43.0389, -87.9065, "large"),
    ("Children's Hospital of Michigan", 42.3314, -83.0458, "large"),
    ("Children's Hospital of Minnesota", 44.9778, -93.2650, "large"),
    ("Children's Mercy Hospital", 39.0458, -94.5844, "large"),
]

# Major urgent care chains database (fallback for OSM gaps)
MAJOR_URGENT_CARE_CHAINS = [
    # AFC Urgent Care locations (sample - would need comprehensive database)
    ("AFC Urgent Care Boulder", 40.0153, -105.2703, "urgent_care"),
    ("AFC Urgent Care Denver", 39.7392, -104.9903, "urgent_care"),
    ("AFC Urgent Care Colorado Springs", 38.8339, -104.8214, "urgent_care"),
    
    # Concentra locations (sample)
    ("Concentra Urgent Care Boulder", 40.0153, -105.2703, "urgent_care"),
    ("Concentra Urgent Care Denver", 39.7392, -104.9903, "urgent_care"),
    
    # CityMD locations (primarily East Coast)
    ("CityMD Brooklyn", 40.6782, -73.9442, "urgent_care"),
    ("CityMD Manhattan", 40.7589, -73.9851, "urgent_care"),
    
    # GoHealth locations (sample)
    ("GoHealth Urgent Care Boulder", 40.0153, -105.2703, "urgent_care"),
    
    # MedExpress locations (sample)
    ("MedExpress Boulder", 40.0153, -105.2703, "urgent_care"),
]


def _get_fallback_urgent_care(lat: float, lon: float) -> List[Dict]:
    """
    Get urgent care facilities from fallback database for areas with poor OSM coverage.
    """
    urgent_care_facilities = []
    
    for name, facility_lat, facility_lon, facility_type in MAJOR_URGENT_CARE_CHAINS:
        distance_km = _haversine_distance(lat, lon, facility_lat, facility_lon)
        
        # Only include facilities within 10km
        if distance_km <= 10000:
            urgent_care_facilities.append({
                "name": name,
                "distance_km": round(distance_km, 0),
                "source": "fallback_database"
            })
    
    return urgent_care_facilities


def get_healthcare_access_score(lat: float, lon: float,
                                area_type: Optional[str] = None,
                                location_scope: Optional[str] = None) -> Tuple[float, Dict]:
    """
    Calculate healthcare access score (0-100).

    Scoring:
    - Hospital Access (0-35): Distance to nearest major hospital
    - Primary Care (0-25): Clinics and doctors within radius
    - Specialized Care (0-15): Specialty services available
    - Emergency Services (0-10): Emergency room capability
    - Pharmacies (0-15): Pharmacies within radius
    - Bonuses shown separately (cap at 100)

    Returns:
        (total_score, detailed_breakdown)
    """
    print(f"🏥 Analyzing healthcare access...")

    # Use provided area_type if available (already computed in main.py)
    # Only detect if not provided to avoid redundant API calls
    if area_type is None:
        from data_sources import census_api
        pop_density = census_api.get_population_density(lat, lon) or 0.0
        from data_sources import data_quality as dq
        detected_area_type = dq.detect_area_type(lat, lon, pop_density)
        area_type = detected_area_type

    # Contextual expectations (research-backed where available)
    expectations = get_contextual_expectations(area_type, 'healthcare_access') or {}
    exp_hosp = float(expectations.get('expected_hospitals_within_10km', 1) or 1)
    exp_urgent = float(expectations.get('expected_urgent_care_within_5km', 1) or 1)
    exp_pharm = float(expectations.get('expected_pharmacies_within_2km', 1) or 1)

    # Radius profiles (meters) via centralized helper
    rp = get_radius_profile('healthcare_access', area_type, location_scope)
    fac_radius_m = int(rp.get('fac_radius_m', 10000))
    pharm_radius_m = int(rp.get('pharm_radius_m', 3000))
    print(f"   🔧 Radius profile (healthcare): area_type={area_type}, scope={location_scope}, facilities={fac_radius_m}m, pharmacies={pharm_radius_m}m")

    # Query OSM for healthcare facilities (hospitals, clinics, doctors, pharmacies, urgent/emergency)
    print(f"   💊 Querying pharmacies and clinics...")
    healthcare_facilities = _get_osm_healthcare(lat, lon)
    
    hospitals = healthcare_facilities.get("hospitals", [])
    urgent_care = healthcare_facilities.get("urgent_care", [])
    pharmacies = healthcare_facilities.get("pharmacies", [])
    clinics = healthcare_facilities.get("clinics", [])
    doctors = healthcare_facilities.get("doctors", [])
    
    # Log warning if no data found (could indicate OSM failure)
    if not hospitals and not urgent_care and not pharmacies and not clinics and not doctors:
        print(f"   ⚠️  WARNING: No healthcare facilities found. This may indicate:")
        print(f"      - OSM query failed (rate limit, timeout, or network error)")
        print(f"      - No healthcare facilities in OSM for this location")
        print(f"      - Query radius too small or location data incomplete")
    
    print(f"   🔍 FINAL COUNTS (raw): {len(hospitals)} hospitals, {len(urgent_care)} urgent care, {len(pharmacies)} pharmacies, {len(clinics)} clinics, {len(doctors)} doctors")

    def _filter_by_radius(features: List[Dict], radius_m: int, category: str) -> List[Dict]:
        kept = []
        dropped = []
        radius_m = float(radius_m or 0)
        for feature in features:
            dist_km = feature.get("distance_km")
            name = feature.get("name")
            if dist_km is None:
                logger.warning(
                    "Healthcare feature missing distance; keeping in results",
                    extra={"category": category, "name": name, "facility_id": feature.get("osm_id")}
                )
                kept.append(feature)
                continue
            try:
                dist_m = float(dist_km) * 1000.0
            except (TypeError, ValueError):
                logger.warning(
                    "Healthcare feature distance could not be parsed; keeping in results",
                    extra={"category": category, "name": name, "distance_value": dist_km}
                )
                kept.append(feature)
                continue
            if dist_m <= radius_m:
                kept.append(feature)
            else:
                dropped.append(feature)
        if dropped and not kept:
            logger.warning(
                "All healthcare features filtered out by radius",
                extra={"category": category, "radius_m": radius_m, "dropped_count": len(dropped)}
            )
        return kept
    
    hospitals = _filter_by_radius(hospitals, fac_radius_m, "hospitals")
    urgent_care = _filter_by_radius(urgent_care, fac_radius_m, "urgent_care")
    clinics = _filter_by_radius(clinics, fac_radius_m, "clinics")
    doctors = _filter_by_radius(doctors, fac_radius_m, "doctors")
    pharmacies = _filter_by_radius(pharmacies, pharm_radius_m, "pharmacies")

    print(f"   🔍 FINAL COUNTS (filtered): {len(hospitals)} hospitals, {len(urgent_care)} urgent care, {len(pharmacies)} pharmacies, {len(clinics)} clinics, {len(doctors)} doctors | area={area_type}")

    # Population density (proxy) for normalization (per 10k)
    # pop_density already computed
    denom = max(1.0, (pop_density / 10000.0))

    # 1) Hospital presence (35 points base)
    has_hospital = len(hospitals) > 0
    hospital_base = 35.0 if has_hospital else 0.0
    # Bonus for additional hospitals (shown separately)
    hospital_bonus = 0.0
    if len(hospitals) > 1:
        hospital_bonus = min(10.0, float(len(hospitals) - 1) * 2.0)
    hospital_score = min(35.0, hospital_base)  # Base score capped at 35

    # 2) Primary care access (25 points) – expectations-aware
    has_clinic = len(clinics) > 0
    has_doctors = len(doctors) > 0
    primary_base = (10.0 if has_clinic else 0.0) + (10.0 if has_doctors else 0.0)
    primary_count = len(clinics) + len(doctors)
    # Use expected urgent care count as a proxy “good-enough” benchmark for primary care access.
    target_primary = max(1.0, exp_urgent)
    if primary_count <= 0:
        primary_density = 0.0
    else:
        primary_ratio = primary_count / target_primary
        # Ratio 1.0 → full 5pt density bonus; cap at 1.5x to avoid over-rewarding outliers.
        primary_density = max(0.0, min(5.0, 5.0 * min(primary_ratio, 1.5)))
    primary_score = primary_base + primary_density
    primary_score = min(25.0, primary_score)  # Cap at 25

    # 3) Specialized care (15 points)
    import re
    specialties = set()
    for f in (hospitals + clinics + doctors):
        spec = (f.get('tags', {}).get('healthcare:speciality') or '')
        for part in re.split(r"[;,|]", spec):
            s = part.strip().lower()
            if s:
                specialties.add(s)
    specialty_score = max(0.0, min(15.0, float(len(specialties))))

    # 4) Emergency services (10 points)
    # Use emergency=yes on hospitals as the signal for ER capability
    has_emergency_hospital = any(
        (f.get('tags', {}).get('emergency') == 'yes') or (f.get('emergency') == 'yes')
        for f in hospitals
    )
    emergency_score = 10.0 if has_emergency_hospital else 0.0

    # 5) Pharmacy access (15 points) – expectations-aware
    pharm_count = len(pharmacies)
    target_pharm = max(1.0, exp_pharm)
    if pharm_count <= 0:
        pharmacy_score = 0.0
    else:
        pharm_ratio = pharm_count / target_pharm
        pharmacy_score = max(0.0, min(15.0, 15.0 * min(pharm_ratio, 1.5)))

    # Base total (without bonuses)
    base_total = hospital_score + primary_score + specialty_score + emergency_score + pharmacy_score
    
    # Total with bonuses (cap at 100)
    total_score = base_total + hospital_bonus
    total_score = max(0.0, min(100.0, total_score))

    # Check if query failed
    query_failed = healthcare_facilities.get("_query_failed", False)
    
    # Assess data quality
    combined_data = {
        'hospitals': hospitals,
        'urgent_care': urgent_care,
        'pharmacies': pharmacies,
        'clinics': clinics,
        'doctors': doctors,
        'total_score': total_score
    }
    
    # Detect actual area type for data quality assessment
    area_type_dq = data_quality.detect_area_type(lat, lon, pop_density)
    quality_metrics = data_quality.assess_pillar_data_quality('healthcare_access', combined_data, lat, lon, area_type_dq)
    
    # If query failed, adjust confidence to indicate API failure (not data absence)
    if query_failed:
        # Set confidence to a low but non-zero value to indicate API failure
        # This distinguishes from "no data found" (which would be 0)
        quality_metrics['confidence'] = max(10, quality_metrics.get('confidence', 0))
        quality_metrics['quality_tier'] = 'very_poor'
        quality_metrics['completeness'] = 0.0
        quality_metrics['data_warning'] = 'api_error'
        print(f"   ⚠️  Healthcare query failed - confidence adjusted to {quality_metrics['confidence']}%")

    # Build response
    # Identify nearest hospital for summary (by reported distance_km)
    nearest_hospital = None
    numeric_hospitals = _with_numeric_distance(hospitals)
    if numeric_hospitals:
        nearest = min(numeric_hospitals, key=lambda x: x["distance_km"])
        nearest_hospital = {
            "name": nearest.get('name', 'Unknown Hospital'),
            "distance_km": nearest.get('distance_km')
        }

    breakdown = {
        "score": round(total_score, 1),
        "breakdown": {
            "hospital_access": round(hospital_score, 1),
            "primary_care": round(primary_score, 1),
            "specialized_care": round(specialty_score, 1),
            "emergency_services": round(emergency_score, 1),
            "pharmacies": round(pharmacy_score, 1)
        },
        "bonuses": {
            "hospital_bonus": round(hospital_bonus, 1)  # Additional hospitals beyond first
        },
        "summary": _build_summary(
            nearest_hospital, urgent_care, pharmacies, clinics
        ),
        "data_quality": quality_metrics
    }

    # Enrich summary with counts
    try:
        breakdown["summary"]["hospital_count"] = len(hospitals)
    except Exception:
        pass

    # Log results
    print(f"✅ Healthcare Access Score: {total_score:.0f}/100")
    print(f"   🏥 Hospital Access: {hospital_score:.0f}/35 ({len(hospitals)} hospitals)")
    if hospital_bonus > 0:
        print(f"      + Hospital Bonus: {hospital_bonus:.0f} (additional hospitals)")
    print(f"   🩺 Primary Care: {primary_score:.0f}/25 (clinics={len(clinics)}, doctors={len(doctors)})")
    print(f"   🧠 Specialized Care: {specialty_score:.0f}/15 (specialties={len(specialties)})")
    print(f"   🚨 Emergency Services: {emergency_score:.0f}/10 (hospital_emergency_tag={has_emergency_hospital})")
    print(f"   💊 Pharmacies: {pharmacy_score:.0f}/15 ({len(pharmacies)} nearby)")
    print(f"   📊 Data Quality: {quality_metrics['quality_tier']} ({quality_metrics['confidence']}% confidence)")

    return round(total_score, 1), breakdown


def _score_hospitals(lat: float, lon: float) -> Tuple[float, Optional[Dict]]:
    """
    Score hospital access (0-40 points) based on distance to nearest major hospital.
    """
    nearest = None
    min_distance = float('inf')

    for name, hosp_lat, hosp_lon, size in MAJOR_HOSPITALS:
        distance_km = _haversine_distance(lat, lon, hosp_lat, hosp_lon)
        if distance_km < min_distance:
            min_distance = distance_km
            nearest = {
                "name": name,
                "distance_km": round(distance_km / 1000, 1),
                "size": size
            }

    if not nearest:
        return 0.0, None

    dist_km = nearest["distance_km"]

    # Scoring based on distance
    if dist_km <= 5:
        score = 40.0
    elif dist_km <= 10:
        score = 35.0
    elif dist_km <= 15:
        score = 30.0
    elif dist_km <= 25:
        score = 25.0
    elif dist_km <= 40:
        score = 20.0
    elif dist_km <= 60:
        score = 15.0
    else:
        score = 10.0

    return score, nearest


def _get_osm_healthcare(lat: float, lon: float) -> Dict:
    """
    Query OSM for healthcare facilities with comprehensive coverage.
    """
    try:
        # Use the new comprehensive healthcare query
        healthcare_data = osm_api.query_healthcare_facilities(lat, lon, radius_m=10000)
        
        if healthcare_data:
            # Check if query failed (indicated by _query_failed flag)
            query_failed = healthcare_data.get("_query_failed", False)
            result = {
                "hospitals": healthcare_data.get("hospitals", []),
                "urgent_care": healthcare_data.get("urgent_care", []),
                "pharmacies": healthcare_data.get("pharmacies", []),
                "clinics": healthcare_data.get("clinics", []),
                "doctors": healthcare_data.get("doctors", [])
            }
            if query_failed:
                result["_query_failed"] = True
            return result
        else:
            print(f"   ⚠️  No healthcare data returned from OSM (query returned None)")
            print(f"   ⚠️  This may indicate: OSM rate limit, timeout, or query failure")
            return {
                "hospitals": [],
                "urgent_care": [],
                "pharmacies": [],
                "clinics": [],
                "doctors": [],
                "_query_failed": True
            }
    except Exception as e:
        print(f"   ⚠️  Healthcare query error: {e}")
        import traceback
        print(f"   ⚠️  Traceback: {traceback.format_exc()}")
        return {
            "hospitals": [],
            "urgent_care": [],
            "pharmacies": [],
            "clinics": [],
            "doctors": [],
            "_query_failed": True
        }


def _score_urgent_care(urgent_care: List[Dict]) -> float:
    """Score urgent care access (0-30 points)."""
    valid = _with_numeric_distance(urgent_care)
    if not valid:
        logger.warning("No urgent care facilities with numeric distance; score defaults to 0")
        return 0.0

    closest = min(valid, key=lambda x: x["distance_km"])
    dist = closest["distance_km"]
    count = len(valid)

    # Distance score (0-20)
    if dist <= 2000:
        dist_score = 20.0
    elif dist <= 3000:
        dist_score = 16.0
    elif dist <= 5000:
        dist_score = 12.0
    else:
        dist_score = 8.0

    # Count score (0-10)
    if count >= 5:
        count_score = 10.0
    elif count >= 3:
        count_score = 7.0
    elif count >= 2:
        count_score = 5.0
    else:
        count_score = 3.0

    return min(30, dist_score + count_score)


def _score_pharmacies(pharmacies: List[Dict]) -> float:
    """Score pharmacy access (0-20 points) - improved scoring."""
    valid = _with_numeric_distance(pharmacies)
    if not valid:
        logger.warning("No pharmacies with numeric distance; score defaults to 0")
        return 0.0

    closest = min(valid, key=lambda x: x["distance_km"])
    dist = closest["distance_km"]
    count = len(pharmacies)

    # More generous distance scoring
    if dist <= 500:
        dist_score = 12.0
    elif dist <= 1000:
        dist_score = 10.0
    elif dist <= 1500:
        dist_score = 8.0
    elif dist <= 2000:
        dist_score = 6.0
    else:
        dist_score = 4.0

    # More generous count scoring
    if count >= 5:
        count_score = 8.0
    elif count >= 3:
        count_score = 6.0
    elif count >= 2:
        count_score = 4.0
    elif count >= 1:
        count_score = 2.0
    else:
        count_score = 0.0

    return min(20, dist_score + count_score)


def _score_clinics(clinics: List[Dict]) -> float:
    """Score general clinic density (0-10 points) - improved scoring."""
    count = len(clinics)

    # More generous clinic scoring
    if count >= 10:
        return 10.0
    elif count >= 7:
        return 8.0
    elif count >= 5:
        return 6.0
    elif count >= 3:
        return 4.0
    elif count >= 1:
        return 2.0
    else:
        return 0.0


def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in meters."""
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi/2)**2 + math.cos(phi1) * \
        math.cos(phi2) * math.sin(delta_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    return R * c


def _with_numeric_distance(features: List[Dict]) -> List[Dict]:
    """Return only features that have a numeric distance_km value."""
    return [f for f in features if isinstance(f.get("distance_km"), (int, float))]


def _build_summary(nearest_hospital: Optional[Dict], urgent_care: List,
                   pharmacies: List, clinics: List) -> Dict:
    """Build summary of healthcare access."""
    summary = {
        "nearest_hospital": nearest_hospital,
        "urgent_care_count": len(urgent_care),
        "pharmacy_count": len(pharmacies),
        "clinic_count": len(clinics),
        "nearest_urgent_care": None,
        "nearest_pharmacy": None
    }

    def _nearest_with_distance(features: List[Dict]) -> Optional[Dict]:
        numeric = [f for f in features if isinstance(f.get("distance_km"), (int, float))]
        if not numeric:
            return None
        return min(numeric, key=lambda x: x["distance_km"])

    closest = _nearest_with_distance(urgent_care)
    if closest:
        summary["nearest_urgent_care"] = {
            "name": closest["name"],
            "distance_km": closest["distance_km"]
        }

    closest = _nearest_with_distance(pharmacies)
    if closest:
        summary["nearest_pharmacy"] = {
            "name": closest["name"],
            "distance_km": closest["distance_km"]
        }

    return summary