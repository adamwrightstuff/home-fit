"""
Healthcare Access Pillar
Scores access to hospitals, clinics, pharmacies, and emergency services
"""

import math
from typing import Dict, Tuple, List, Optional
from data_sources import osm_api

# Major US hospitals database (simplified - top trauma centers and teaching hospitals)
# Data would ideally come from CMS Hospital Compare API
# For now, using a representative sample
MAJOR_HOSPITALS = [
    # Northeast
    ("Massachusetts General Hospital", 42.3631, -71.0686, "large"),
    ("NewYork-Presbyterian Hospital", 40.7769, -73.9540, "large"),
    ("NYU Langone Medical Center", 40.7424, -73.9759, "large"),
    ("Mount Sinai Hospital", 40.7903, -73.9529, "large"),
    ("Johns Hopkins Hospital", 39.2971, -76.5929, "large"),
    ("Hospital of the University of Pennsylvania", 39.9496, -75.1955, "large"),
    
    # Southeast
    ("Emory University Hospital", 33.7974, -84.3239, "large"),
    ("Duke University Hospital", 36.0103, -78.9392, "large"),
    ("University of Miami Hospital", 25.7207, -80.2185, "large"),
    ("Shands Hospital at University of Florida", 29.6406, -82.3444, "large"),
    
    # Midwest
    ("Northwestern Memorial Hospital", 41.8959, -87.6190, "large"),
    ("University of Chicago Medical Center", 41.7891, -87.6047, "large"),
    ("Cleveland Clinic", 41.5034, -81.6214, "large"),
    ("Mayo Clinic", 44.0225, -92.4660, "large"),
    ("University of Michigan Hospital", 42.2928, -83.7231, "large"),
    
    # Southwest
    ("Methodist Hospital", 29.7098, -95.3984, "large"),
    ("UT Southwestern Medical Center", 32.8174, -96.8358, "large"),
    
    # West
    ("UCLA Medical Center", 34.0652, -118.4450, "large"),
    ("Cedars-Sinai Medical Center", 34.0753, -118.3767, "large"),
    ("UCSF Medical Center", 37.7625, -122.4579, "large"),
    ("Stanford Hospital", 37.4442, -122.1718, "large"),
    ("University of Washington Medical Center", 47.6501, -122.3054, "large"),
]


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

    # Score components
    urgent_care_score = _score_urgent_care(urgent_care)
    pharmacy_score = _score_pharmacies(pharmacies)
    clinic_score = _score_clinics(clinics)

    total_score = hospital_score + urgent_care_score + pharmacy_score + clinic_score

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
        )
    }

    # Log results
    print(f"✅ Healthcare Access Score: {total_score:.0f}/100")
    print(f"   🏥 Hospital Access: {hospital_score:.0f}/40")
    print(f"   🚑 Urgent Care: {urgent_care_score:.0f}/30 ({len(urgent_care)} facilities)")
    print(f"   💊 Pharmacies: {pharmacy_score:.0f}/20 ({len(pharmacies)} nearby)")
    print(f"   🩺 Clinic Density: {clinic_score:.0f}/10 ({len(clinics)} clinics)")

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
    Query OSM for healthcare facilities.
    """
    try:
        # Custom Overpass query for healthcare
        query = f"""
        [out:json][timeout:25];
        (
          // Urgent care / Emergency
          node["amenity"="clinic"]["emergency"="yes"](around:5000,{lat},{lon});
          node["amenity"="clinic"]["healthcare"="urgent_care"](around:5000,{lat},{lon});
          
          // Pharmacies
          node["amenity"="pharmacy"](around:1000,{lat},{lon});
          way["amenity"="pharmacy"](around:1000,{lat},{lon});
          
          // General clinics
          node["amenity"="clinic"](around:5000,{lat},{lon});
          node["amenity"="doctors"](around:5000,{lat},{lon});
          way["amenity"="clinic"](around:5000,{lat},{lon});
          way["amenity"="doctors"](around:5000,{lat},{lon});
        );
        out body;
        >;
        out skel qt;
        """

        import requests
        resp = requests.post(
            "https://overpass-api.de/api/interpreter",
            data={"data": query},
            timeout=30,
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

            # Categorize
            if emergency == "yes" or healthcare == "urgent_care":
                urgent_care.append(facility)
            elif amenity == "pharmacy":
                pharmacies.append(facility)
            elif amenity in ["clinic", "doctors"]:
                clinics.append(facility)

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
    """Score pharmacy access (0-20 points)."""
    if not pharmacies:
        return 0.0

    closest = min(pharmacies, key=lambda x: x["distance_m"])
    dist = closest["distance_m"]
    count = len(pharmacies)

    # Distance score (0-12)
    if dist <= 500:
        dist_score = 12.0
    elif dist <= 800:
        dist_score = 10.0
    elif dist <= 1000:
        dist_score = 8.0
    else:
        dist_score = 5.0

    # Count score (0-8)
    if count >= 5:
        count_score = 8.0
    elif count >= 3:
        count_score = 6.0
    elif count >= 2:
        count_score = 4.0
    else:
        count_score = 2.0

    return min(20, dist_score + count_score)


def _score_clinics(clinics: List[Dict]) -> float:
    """Score general clinic density (0-10 points)."""
    count = len(clinics)

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