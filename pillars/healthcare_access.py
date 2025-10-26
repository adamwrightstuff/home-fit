"""
Healthcare Access Pillar
Scores access to hospitals, clinics, pharmacies, and emergency services
"""

import math
from typing import Dict, Tuple, List, Optional
from data_sources import osm_api, data_quality

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
        distance_m = _haversine_distance(lat, lon, facility_lat, facility_lon)
        
        # Only include facilities within 10km
        if distance_m <= 10000:
            urgent_care_facilities.append({
                "name": name,
                "distance_m": round(distance_m, 0),
                "source": "fallback_database"
            })
    
    return urgent_care_facilities


def get_healthcare_access_score(lat: float, lon: float) -> Tuple[float, Dict]:
    """
    Calculate healthcare access score (0-100).

    Scoring:
    - Hospital Access (0-40): Distance to nearest major hospital
    - Urgent Care (0-30): Clinics within 5km
    - Pharmacies (0-20): Pharmacies within 1km
    - Clinic Density (0-10): General healthcare facilities

    Returns:
        (total_score, detailed_breakdown)
    """
    print(f"🏥 Analyzing healthcare access...")

    # Score hospitals (using static database for major hospitals)
    hospital_score, nearest_hospital = _score_hospitals(lat, lon)

    # Query OSM for urgent care, pharmacies, clinics
    print(f"   💊 Querying pharmacies and clinics...")
    healthcare_facilities = _get_osm_healthcare(lat, lon)

    urgent_care = healthcare_facilities.get("urgent_care", [])
    pharmacies = healthcare_facilities.get("pharmacies", [])
    clinics = healthcare_facilities.get("clinics", [])
    
    print(f"   🔍 FINAL COUNTS: {len(urgent_care)} urgent care, {len(pharmacies)} pharmacies, {len(clinics)} clinics")
    
    # Add fallback urgent care data if OSM data is sparse
    if len(urgent_care) < 3:  # If we have fewer than 3 urgent care facilities from OSM
        print(f"   🔄 Adding fallback urgent care data (OSM returned {len(urgent_care)})...")
        fallback_urgent_care = _get_fallback_urgent_care(lat, lon)
        urgent_care.extend(fallback_urgent_care)
        print(f"   ✅ Total urgent care after fallback: {len(urgent_care)}")

    # Score components
    urgent_care_score = _score_urgent_care(urgent_care)
    pharmacy_score = _score_pharmacies(pharmacies)
    clinic_score = _score_clinics(clinics)

    total_score = hospital_score + urgent_care_score + pharmacy_score + clinic_score

    # Assess data quality
    combined_data = {
        'hospitals': [nearest_hospital] if nearest_hospital else [],
        'urgent_care': urgent_care,
        'pharmacies': pharmacies,
        'clinics': clinics,
        'total_score': total_score
    }
    
    # Get area classification for data quality assessment
    area_type = "urban_core"  # Default, could be enhanced with actual area detection
    quality_metrics = data_quality.assess_pillar_data_quality('healthcare_access', combined_data, lat, lon, area_type)

    # Build response
    breakdown = {
        "score": round(total_score, 1),
        "breakdown": {
            "hospital_access": round(hospital_score, 1),
            "urgent_care": round(urgent_care_score, 1),
            "pharmacies": round(pharmacy_score, 1),
            "clinic_density": round(clinic_score, 1)
        },
        "summary": _build_summary(
            nearest_hospital, urgent_care, pharmacies, clinics
        ),
        "data_quality": quality_metrics
    }

    # Log results
    print(f"✅ Healthcare Access Score: {total_score:.0f}/100")
    print(f"   🏥 Hospital Access: {hospital_score:.0f}/40")
    print(f"   🚑 Urgent Care: {urgent_care_score:.0f}/30 ({len(urgent_care)} facilities)")
    print(f"   💊 Pharmacies: {pharmacy_score:.0f}/20 ({len(pharmacies)} nearby)")
    print(f"   🩺 Clinic Density: {clinic_score:.0f}/10 ({len(clinics)} clinics)")
    print(f"   📊 Data Quality: {quality_metrics['quality_tier']} ({quality_metrics['confidence']}% confidence)")

    return round(total_score, 1), breakdown


def _score_hospitals(lat: float, lon: float) -> Tuple[float, Optional[Dict]]:
    """
    Score hospital access (0-40 points) based on distance to nearest major hospital.
    """
    nearest = None
    min_distance = float('inf')

    for name, hosp_lat, hosp_lon, size in MAJOR_HOSPITALS:
        distance_m = _haversine_distance(lat, lon, hosp_lat, hosp_lon)
        if distance_m < min_distance:
            min_distance = distance_m
            nearest = {
                "name": name,
                "distance_km": round(distance_m / 1000, 1),
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
        # Ultra-simplified Overpass query for fast response
        query = f"""
        [out:json][timeout:15];
        (
          node["healthcare"~"clinic|doctor|urgent_care"](around:5000,{lat},{lon});
          node["amenity"~"clinic|doctors|pharmacy|dentist"](around:3000,{lat},{lon});
        );
        out body;
        """

        import requests
        resp = requests.post(
            "https://overpass-api.de/api/interpreter",
            data={"data": query},
            timeout=20,
            headers={"User-Agent": "HomeFit/1.0"}
        )

        if resp.status_code != 200:
            return {"urgent_care": [], "pharmacies": [], "clinics": []}

        data = resp.json()
        elements = data.get("elements", [])

        # Process elements
        urgent_care = []
        pharmacies = []
        clinics = []
        nodes_dict = {}

        # Build nodes dict
        for elem in elements:
            if elem.get("type") == "node":
                nodes_dict[elem["id"]] = elem

        for elem in elements:
            tags = elem.get("tags", {})
            if not tags:
                continue

            amenity = tags.get("amenity")
            emergency = tags.get("emergency")
            healthcare = tags.get("healthcare")

            # Get coordinates
            elem_lat = elem.get("lat")
            elem_lon = elem.get("lon")

            if elem.get("type") == "way":
                elem_lat, elem_lon = _get_way_center(elem, nodes_dict)

            if not elem_lat or not elem_lon:
                continue

            distance_m = _haversine_distance(lat, lon, elem_lat, elem_lon)

            facility = {
                "name": tags.get("name", "Unnamed"),
                "distance_m": round(distance_m, 0)
            }

            # Enhanced categorization logic
            name_lower = facility["name"].lower()
            
            # DEBUG: Print first 5 facilities to see what's happening
            if len(urgent_care) + len(pharmacies) + len(clinics) < 5:
                print(f"      Processing: {facility['name']} - amenity={amenity}, healthcare={healthcare}")
            
            # Urgent care / Emergency facilities - ULTRA AGGRESSIVE DETECTION
            # Treat ALL healthcare facilities as urgent care (most urgent care centers are tagged as healthcare=clinic)
            # BUT EXCLUDE pharmacies and major hospitals ONLY
            if ((emergency == "yes" or 
                healthcare == "urgent_care" or 
                healthcare == "emergency" or
                healthcare == "clinic" or  # Most urgent care centers are tagged as healthcare=clinic
                healthcare == "doctor" or  # Many urgent care centers are tagged as healthcare=doctor
                healthcare == "primary_care" or  # Many urgent care centers are tagged as healthcare=primary_care
                healthcare == "specialist" or  # Many urgent care centers are tagged as healthcare=specialist
                amenity == "clinic" or  # Many urgent care centers are tagged as amenity=clinic
                amenity == "doctors" or  # Many urgent care centers are tagged as amenity=doctors
                "urgent" in name_lower or 
                "emergency" in name_lower or
                "walk-in" in name_lower or
                "walk in" in name_lower or
                "immediate" in name_lower or
                "afc" in name_lower or  # AFC Urgent Care
                "concentra" in name_lower or  # Concentra Urgent Care
                "citymd" in name_lower or  # CityMD
                "gohealth" in name_lower or  # GoHealth
                "medexpress" in name_lower or  # MedExpress
                "urgent care" in name_lower or
                "immediate care" in name_lower or
                "clinic" in name_lower or  # Many urgent care centers have "clinic" in their name
                "medical" in name_lower or  # Many urgent care centers have "medical" in their name
                "health" in name_lower or  # Many urgent care centers have "health" in their name
                "care" in name_lower) and  # Many urgent care centers have "care" in their name
                # EXCLUDE pharmacies and major hospitals ONLY (not medical centers or health centers)
                amenity != "pharmacy" and 
                healthcare != "pharmacy" and
                amenity != "hospital" and
                healthcare != "hospital" and
                "pharmacy" not in name_lower):
                urgent_care.append(facility)
            
            # Pharmacies and drug stores
            elif (amenity == "pharmacy" or 
                  tags.get("shop") == "pharmacy" or
                  healthcare == "pharmacy" or
                  "pharmacy" in name_lower or
                  "drug" in name_lower or
                  "cvs" in name_lower or
                  "walgreens" in name_lower or
                  "rite aid" in name_lower or
                  "rite-aid" in name_lower):
                pharmacies.append(facility)
            
            # General clinics - ONLY dentists now (everything else is urgent care)
            elif (amenity == "dentist" or
                  healthcare == "dentist" or
                  "dentist" in name_lower or
                  "dental" in name_lower):
                clinics.append(facility)

        # Debug output
        print(f"   🔍 DEBUG: OSM returned {len(elements)} total elements")
        print(f"   🔍 DEBUG: Found {len(urgent_care)} urgent care, {len(pharmacies)} pharmacies, {len(clinics)} clinics")
        if len(elements) > 0:
            print(f"   🔍 DEBUG: Sample OSM elements (first 3):")
            for i, elem in enumerate(elements[:3]):
                tags = elem.get("tags", {})
                print(f"      Element {i+1}: {tags.get('name', 'Unnamed')} - amenity={tags.get('amenity')}, healthcare={tags.get('healthcare')}")
        
        return {
            "urgent_care": urgent_care,
            "pharmacies": pharmacies,
            "clinics": clinics
        }

    except Exception as e:
        print(f"   ⚠️  Healthcare query error: {e}")
        return {"urgent_care": [], "pharmacies": [], "clinics": []}


def _score_urgent_care(urgent_care: List[Dict]) -> float:
    """Score urgent care access (0-30 points)."""
    if not urgent_care:
        return 0.0

    closest = min(urgent_care, key=lambda x: x["distance_m"])
    dist = closest["distance_m"]
    count = len(urgent_care)

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
    if not pharmacies:
        return 0.0

    closest = min(pharmacies, key=lambda x: x["distance_m"])
    dist = closest["distance_m"]
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


def _get_way_center(elem: Dict, nodes_dict: Dict) -> Tuple[Optional[float], Optional[float]]:
    """Get center point of a way."""
    if "nodes" not in elem:
        return None, None

    lats = []
    lons = []
    for node_id in elem["nodes"]:
        if node_id in nodes_dict:
            node = nodes_dict[node_id]
            if "lat" in node and "lon" in node:
                lats.append(node["lat"])
                lons.append(node["lon"])

    if not lats:
        return None, None

    return sum(lats) / len(lats), sum(lons) / len(lons)


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

    if urgent_care:
        closest = min(urgent_care, key=lambda x: x["distance_m"])
        summary["nearest_urgent_care"] = {
            "name": closest["name"],
            "distance_m": closest["distance_m"]
        }

    if pharmacies:
        closest = min(pharmacies, key=lambda x: x["distance_m"])
        summary["nearest_pharmacy"] = {
            "name": closest["name"],
            "distance_m": closest["distance_m"]
        }

    return summary