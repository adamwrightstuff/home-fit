"""
Healthcare Access Pillar
Scores access to hospitals, clinics, pharmacies, and emergency services

This pillar measures physical infrastructure availability (counts, distances, proximity)
based on objective, measurable data from OpenStreetMap and fallback databases.

What it measures:
- Hospital count and distance to nearest hospital
- Primary care facilities (clinics, doctors) within radius
- Pharmacy availability within radius
- Emergency services (hospitals with ER capability)
- Specialized care (unique specialties available)

What it does NOT measure:
- Insurance coverage rates or uninsured populations
- Cost barriers or affordability
- Demographic disparities in access
- Quality of care or hospital ratings
- Real-world accessibility barriers (transportation, trust, etc.)

These factors may affect actual healthcare access but are not included to maintain
objective, scalable, and reproducible scoring aligned with design principles.
"""

import json
import math
import os
from functools import lru_cache
from typing import Dict, Tuple, List, Optional
from data_sources import osm_api, data_quality
from data_sources.regional_baselines import get_contextual_expectations, get_area_classification
from data_sources.radius_profiles import get_radius_profile
from data_sources.places_healthcare_client import maybe_augment_healthcare_with_places
from data_sources.npi_specialty_client import get_specialty_count as _npi_specialty_count, state_from_latlon as _state_from_latlon
from logging_config import get_logger

logger = get_logger(__name__)

# Data-backed scoring curve parameters (not calibrated from target scores)
# Based on objective healthcare access quality thresholds:
# - 1.0× expected = meets basic needs (50% of max)
# - 1.5× expected = good access (85% of max)
# - 2.5× expected = excellent access (85% of max, plateaus)
# - 3.0× expected = exceptional access (95% of max)
RATIO_SCORING_PARAMS = {
    'at_expected': 50.0,      # Score at 1.0× expected (meets basic needs)
    'at_good': 85.0,          # Score at 1.5× expected (good access)
    'at_excellent': 85.0,     # Score at 2.5× expected (excellent access)
    'at_exceptional': 95.0,   # Score at 3.0× expected (exceptional access)
    'ratio_expected': 1.0,
    'ratio_good': 1.5,
    'ratio_excellent': 2.5,
    'ratio_exceptional': 3.0,
}


def _ratio_score(ratio: float, max_score: float) -> float:
    """
    Data-backed piecewise linear scoring curve based on objective healthcare access quality.
    
    Uses objective thresholds: 1×=basic, 1.5×=good, 2.5×=excellent, 3×=exceptional.
    
    Args:
        ratio: Count ratio (actual / expected)
        max_score: Maximum score for this component (e.g., 35 for hospitals, 15 for pharmacies)
    
    Returns:
        Score from 0 to max_score
    """
    # Minimum threshold: Lowered from 0.05 to 0.01 to give credit for minimal facilities
    # Even with very high expectations, 1 facility should get some credit
    # Also ensure minimum score floor for any positive ratio
    if ratio <= 0.0:
        return 0.0
    
    # Scale data-backed breakpoints to component's max_score
    # Curve goes 0→50→85→85→95 at ratios 0→1.0→1.5→2.5→3.0
    # Scale to max_score: multiply by (max_score / 95.0)
    scale = max_score / 95.0
    
    at_expected = RATIO_SCORING_PARAMS['at_expected'] * scale
    at_good = RATIO_SCORING_PARAMS['at_good'] * scale
    at_excellent = RATIO_SCORING_PARAMS['at_excellent'] * scale
    at_exceptional = RATIO_SCORING_PARAMS['at_exceptional'] * scale
    
    ratio_expected = RATIO_SCORING_PARAMS['ratio_expected']
    ratio_good = RATIO_SCORING_PARAMS['ratio_good']
    ratio_excellent = RATIO_SCORING_PARAMS['ratio_excellent']
    ratio_exceptional = RATIO_SCORING_PARAMS['ratio_exceptional']
    
    # Minimum score floor: Ensure any positive ratio gets at least 2-5% of max_score
    # This prevents locations with 1 facility from scoring 0 when expectations are very high
    min_score_floor = max_score * 0.02  # 2% minimum (e.g., 0.3 points for pharmacies, 0.5 for primary care)
    
    if ratio < ratio_expected:
        # Linear from 0 to at_expected
        if ratio <= 0.01:
            # Extremely small ratios: apply minimum floor
            return min_score_floor
        elif ratio <= 0.1:
            # Very small ratios: give minimal score (scaled down for very low ratios)
            # This ensures places with 1 pharmacy don't get 0.0 when expectations are high
            calculated_score = (at_expected / ratio_expected) * ratio * 0.8
            return max(min_score_floor, calculated_score)  # Ensure minimum floor
        else:
            return (at_expected / ratio_expected) * ratio
    elif ratio < ratio_good:
        # Linear from at_expected to at_good
        return at_expected + (ratio - ratio_expected) * (at_good - at_expected) / (ratio_good - ratio_expected)
    elif ratio < ratio_excellent:
        # Linear from at_good to at_excellent
        return at_good + (ratio - ratio_good) * (at_excellent - at_good) / (ratio_excellent - ratio_good)
    elif ratio < ratio_exceptional:
        # Linear from at_excellent to at_exceptional
        return at_excellent + (ratio - ratio_excellent) * (at_exceptional - at_excellent) / (ratio_exceptional - ratio_excellent)
    else:
        # At or above exceptional - cap at max_score
        return min(max_score, at_exceptional)


def _distance_to_hospital_score(distance_km: float, max_score: float = 35.0) -> float:
    """
    Score hospital access based on distance to nearest hospital.
    
    Uses smooth exponential decay curve for distance-based scoring.
    This complements the count-based scoring for hospital access.
    
    Args:
        distance_km: Distance to nearest hospital in kilometers
        max_score: Maximum score (default 35 for hospital component)
    
    Returns:
        Score from 0 to max_score
    """
    if distance_km <= 0:
        return max_score
    
    # Smooth exponential decay: score = max_score * e^(-distance / decay_factor)
    # Data-backed breakpoints:
    # - 5km = 35pts (100%)
    # - 10km = 30pts (86%)
    # - 15km = 25pts (71%)
    # - 25km = 20pts (57%)
    # - 40km = 15pts (43%)
    # - 60km = 10pts (29%)
    # - >60km = 5pts (14%)
    
    # Use exponential decay with decay_factor ≈ 15km
    # This gives: score(5km) ≈ 0.95×max, score(10km) ≈ 0.86×max, score(15km) ≈ 0.71×max
    decay_factor = 15.0
    base_score = max_score * math.exp(-distance_km / decay_factor)
    
    # Ensure minimum score for very far hospitals (better than nothing)
    min_score = max_score * 0.14  # 5pts out of 35pts
    return max(min_score, base_score)

# Component budgets (points). The pillar score is points earned over the budgets of the components that could be
# read, scaled to 100, plus the hospital bonus. All five present: sum of points, as before.
HEALTHCARE_BUDGETS = {
    "hospital_access": 35.0,
    "primary_care": 25.0,
    "specialized_care": 15.0,
    "emergency_services": 10.0,
    "pharmacies": 15.0,
}

_MILE_KM = 1.609344


def _pharmacy_distance_fraction(distance_km: float) -> float:
    """
    Share of the pharmacy points earned at a given distance to the nearest pharmacy (one scale for every place).

    Sourced anchors, from published pharmacy-desert definitions (2024 national tract study, https://pmc.ncbi.nlm.nih.gov/articles/PMC11034534/):
    0.5 mile is the threshold for tracts where few residents own a car, 1 mile is the urban desert line, 10 miles is the
    rural desert line. Full credit inside 0.5 mile; half credit at 1 mile; 5 percent at 10 miles. The shape between the
    anchors is a design judgment (straight line from full to half, then exponential decay), not a published curve.
    The studies measure road distance or drive time; this uses straight-line distance. TODO: source a road-distance factor.
    """
    mi = max(0.0, float(distance_km)) / _MILE_KM
    if mi <= 0.5:
        return 1.0
    if mi <= 1.0:
        return 1.0 - (mi - 0.5)
    return 0.5 * math.exp(-math.log(10.0) * (mi - 1.0) / 9.0)


def healthcare_total(parts: Dict[str, Optional[float]], hospital_bonus: float = 0.0,
                     budgets: Optional[Dict[str, float]] = None) -> float:
    """Pillar score from the component points (None = could not be read), scaled over the components present, plus the bonus."""
    present = {k: v for k, v in parts.items() if v is not None}
    if not present:
        return 0.0
    budgets = budgets or HEALTHCARE_BUDGETS
    base = sum(present.values()) / sum(budgets[k] for k in present) * 100.0
    return max(0.0, min(100.0, base + hospital_bonus))


# One search radius for every place: the OpenStreetMap read is 10 km (see _get_osm_healthcare), and the capacity parts
# compare facilities in that disk to the people living in it.
HEALTHCARE_RADIUS_M = 10000


@lru_cache(maxsize=1)
def _load_supply_scale() -> Optional[Dict]:
    """data/healthcare_supply_scale.json (catalog medians of facilities per resident); None when the file is missing."""
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "healthcare_supply_scale.json")
    try:
        with open(path) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def people_within(lat: float, lon: float, radius_m: int = HEALTHCARE_RADIUS_M) -> Optional[float]:
    """Residents within the radius (local tract tables). The place context carries this for live requests; catalog scripts call it."""
    from data_sources.surrounding_density import people_within as _people_within
    return _people_within(lat, lon, radius_m)


def capacity_score(count: int, residents: Optional[float], expected_per_unit: float, unit: float, max_score: float) -> Optional[float]:
    """Facilities per `unit` residents against the catalog-median supply, on the pillar's ratio curve. None when residents are unknown."""
    if not residents or residents <= 0 or expected_per_unit <= 0:
        return None
    per_unit = count / residents * unit
    return _ratio_score(per_unit / expected_per_unit, max_score) if count > 0 else 0.0


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
    ("Swedish Medical Center First Hill", 47.6085, -122.3336, "large"),
    ("Swedish Medical Center Cherry Hill", 47.6085, -122.3336, "large"),
    ("Virginia Mason Medical Center", 47.6062, -122.3321, "large"),
    ("Providence St. Vincent Medical Center", 45.5152, -122.6784, "large"),
    ("Legacy Emanuel Medical Center", 45.5152, -122.6784, "medium"),
    ("Kaiser Permanente Medical Center", 37.7749, -122.4194, "large"),
    ("Sutter Health California Pacific Medical Center", 37.7749, -122.4194, "large"),
    
    # Major Children's Hospitals
    ("Children's Hospital Los Angeles", 34.0522, -118.2437, "large"),
    ("Children's Hospital of Orange County", 33.6846, -117.8265, "large"),
    ("Rady Children's Hospital", 32.7157, -117.1611, "large"),
    ("Seattle Children's Hospital", 47.6626, -122.3135, "large"),
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

    # NYC Metro — borough community hospitals (not in the academic-center list above)
    ("Maimonides Medical Center", 40.6335, -74.0120, "large"),             # Borough Park / Boro Park, Brooklyn
    ("NYU Langone Health Brooklyn", 40.6379, -74.0179, "medium"),          # Sunset Park, Brooklyn (former Lutheran)
    ("NewYork-Presbyterian Brooklyn Methodist", 40.6617, -73.9890, "large"), # Park Slope, Brooklyn
    ("Kings County Hospital Center", 40.6566, -73.9435, "large"),          # Flatbush, Brooklyn
    ("SUNY Downstate Medical Center", 40.6552, -73.9415, "large"),         # Flatbush, Brooklyn
    ("Interfaith Medical Center", 40.6724, -73.9431, "medium"),            # Crown Heights, Brooklyn
    ("Wyckoff Heights Medical Center", 40.7029, -73.9205, "medium"),       # Bushwick, Brooklyn
    ("Woodhull Medical Center", 40.7031, -73.9384, "medium"),              # Williamsburg, Brooklyn
    ("Coney Island Hospital", 40.5768, -73.9958, "medium"),                # Coney Island, Brooklyn
    ("Forest Hills Hospital", 40.7197, -73.8476, "medium"),               # Forest Hills, Queens
    ("Elmhurst Hospital Center", 40.7446, -73.8820, "large"),              # Elmhurst, Queens
    ("NewYork-Presbyterian Queens", 40.7370, -73.8281, "large"),           # Flushing, Queens
    ("Flushing Hospital Medical Center", 40.7440, -73.8155, "medium"),     # Flushing, Queens
    ("Queens Hospital Center", 40.7008, -73.8050, "medium"),               # Jamaica, Queens
    ("Jamaica Hospital Medical Center", 40.6987, -73.8003, "medium"),      # Jamaica / Ozone Park, Queens
    ("Jacobi Medical Center", 40.8553, -73.8475, "large"),                 # Pelham Pkwy, Bronx
    ("Lincoln Medical Center", 40.8191, -73.9259, "large"),                # Mott Haven, Bronx
    ("North Central Bronx Hospital", 40.8866, -73.8776, "medium"),         # Norwood, Bronx
    ("Montefiore Medical Center Bronx", 40.8802, -73.8791, "large"),       # Norwood / Wakefield, Bronx
    ("BronxCare Health System", 40.8415, -73.9245, "large"),               # Grand Concourse, Bronx
    ("Richmond University Medical Center", 40.6380, -74.1155, "medium"),   # West Brighton, Staten Island
    ("Staten Island University Hospital North", 40.6095, -74.0838, "large"), # Seaview, Staten Island
    ("Staten Island University Hospital South", 40.5520, -74.1690, "medium"), # Prince's Bay, Staten Island

    # NYC Metro — Westchester / Hudson Valley
    ("Westchester Medical Center", 41.0750, -73.7993, "large"),            # Valhalla, NY (Level I trauma)
    ("White Plains Hospital", 41.0340, -73.7629, "medium"),                # White Plains, NY
    ("Phelps Hospital Northwell", 41.0895, -73.8629, "medium"),            # Sleepy Hollow, NY
    ("Northern Westchester Hospital", 41.2102, -73.7281, "medium"),        # Mount Kisco, NY
    ("Hudson Valley Hospital Center", 41.2743, -73.8851, "medium"),        # Cortlandt Manor, NY (near Peekskill)
    ("Montefiore New Rochelle Hospital", 40.9141, -73.7854, "medium"),     # New Rochelle, NY (near Mount Vernon)

    # NYC Metro — New Jersey
    ("Morristown Medical Center", 40.7967, -74.4760, "large"),             # Morristown, NJ (Atlantic Health)
    ("Overlook Medical Center", 40.7174, -74.3631, "large"),               # Summit, NJ (Atlantic Health)
    ("Saint Barnabas Medical Center", 40.7891, -74.3182, "large"),         # Livingston, NJ (RWJBarnabas)
    ("Newark Beth Israel Medical Center", 40.7282, -74.1738, "large"),     # Newark, NJ
    ("University Hospital Newark", 40.7443, -74.1855, "large"),            # Newark, NJ
    ("Hackensack University Medical Center", 40.8862, -74.0441, "large"),  # Hackensack, NJ
    ("Holy Name Medical Center", 40.8801, -74.0143, "medium"),             # Teaneck, NJ
    ("Englewood Health", 40.8921, -73.9727, "medium"),                     # Englewood, NJ
    ("Valley Hospital", 40.9794, -74.1164, "large"),                       # Ridgewood, NJ
    ("Mountainside Medical Center", 40.8221, -74.2135, "medium"),          # Montclair, NJ
    ("St. Joseph's University Medical Center", 40.9176, -74.1652, "large"), # Paterson, NJ
    ("Chilton Medical Center", 41.0050, -74.3118, "medium"),               # Pompton Plains, NJ

    # NYC Metro — Connecticut (Fairfield County)
    ("Stamford Hospital", 41.0547, -73.5346, "large"),                     # Stamford, CT
    ("Greenwich Hospital", 41.0259, -73.6323, "medium"),                   # Greenwich, CT
    ("Bridgeport Hospital", 41.1840, -73.2001, "large"),                   # Bridgeport, CT
    ("Norwalk Hospital", 41.1196, -73.4166, "medium"),                     # Norwalk, CT
    ("St. Vincent's Medical Center Bridgeport", 41.1673, -73.2012, "medium"), # Bridgeport, CT

    # NYC Metro — Long Island
    ("South Nassau Communities Hospital", 40.6381, -73.6370, "medium"),    # Oceanside, NY
    ("Nassau University Medical Center", 40.7329, -73.5457, "large"),      # East Meadow, NY
    ("North Shore University Hospital", 40.7756, -73.6924, "large"),       # Manhasset, NY
    ("NYU Langone Long Island", 40.7231, -73.5917, "large"),               # Mineola, NY
    ("Long Island Jewish Medical Center", 40.7547, -73.7065, "large"),     # New Hyde Park, NY

    # Community / regional hospitals for resort/rural destinations
    # (academic-center fallback misses these, causing wildly wrong distances)
    ("St. John's Medical Center", 43.4824, -110.7634, "medium"),           # Jackson, WY
    ("Vail Health Hospital", 39.6430, -106.3754, "medium"),                # Vail, CO
    ("Yampa Valley Medical Center", 40.4845, -106.8318, "medium"),         # Steamboat Springs, CO
    ("Moab Regional Hospital", 38.5745, -109.5486, "small"),               # Moab, UT
    ("The Outer Banks Hospital", 35.9520, -75.6167, "medium"),             # Kill Devil Hills / Nags Head, NC
    ("Sentara Virginia Beach General Hospital", 36.7872, -76.0339, "large"), # Virginia Beach, VA
    ("Sacred Heart Hospital on the Emerald Coast", 30.3699, -86.5100, "medium"), # Destin, FL
    ("Fort Walton Beach Medical Center", 30.4040, -86.5773, "medium"),     # Fort Walton Beach, FL
    ("Mount Desert Island Hospital", 44.3728, -68.2028, "small"),          # Bar Harbor, ME
    ("Mission Hospital Asheville", 35.5751, -82.5423, "large"),            # Asheville, NC
    ("Newport Hospital", 41.4944, -71.3175, "medium"),                     # Newport, RI
    ("Barton Memorial Hospital", 38.9406, -119.9626, "medium"),            # South Lake Tahoe, CA
    ("Coastal Carolina Hospital", 32.2283, -80.8519, "medium"),            # Hilton Head, SC
    ("Community Hospital of the Monterey Peninsula", 36.5935, -121.9018, "medium"), # Monterey, CA
    ("CHRISTUS St. Vincent Regional Medical Center", 35.6909, -106.0153, "large"), # Santa Fe, NM
    ("Summit Health Medical Center", 39.5741, -106.0980, "medium"),        # Breckenridge / Frisco, CO
    ("Montrose Memorial Hospital", 38.4784, -107.8779, "medium"),          # Telluride area, CO
    ("LeConte Medical Center", 35.8717, -83.5657, "medium"),               # Gatlinburg / Sevierville, TN
    ("Copley Hospital", 44.5598, -72.6232, "small"),                       # Stowe / Morrisville, VT
    ("University of Utah Health Park City", 40.6441, -111.4980, "medium"), # Park City, UT
    ("Cape Cod Hospital", 41.6429, -70.2778, "medium"),                    # Provincetown area, MA
    ("Falmouth Hospital", 41.5523, -70.6076, "small"),                     # Cape Cod, MA
    ("Queen of the Valley Medical Center", 38.3019, -122.3059, "large"),   # Napa, CA
    ("St. David's Medical Center", 30.2930, -97.7285, "large"),            # Austin, TX
    ("Seton Medical Center Austin", 30.3001, -97.7426, "large"),           # Austin, TX
    ("St. David's South Austin Medical Center", 30.2245, -97.7794, "large"), # Austin, TX
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
                "distance_km": round(distance_km / 1000.0, 1),  # Convert to km
                "source": "fallback_database"
            })
    
    return urgent_care_facilities


def _get_fallback_hospitals(lat: float, lon: float, max_distance_km: float = 60.0) -> List[Dict]:
    """
    Get hospitals from MAJOR_HOSPITALS database as fallback when OSM data is unavailable.
    
    This provides a scalable fallback mechanism for major medical centers across the US.
    The database covers major metropolitan areas and regional hospitals.
    
    Args:
        lat, lon: Location coordinates
        max_distance_km: Maximum distance to include hospitals (default 60km)
    
    Returns:
        List of hospital dicts with name, distance_km, size, and source
    """
    hospitals = []
    
    for name, hosp_lat, hosp_lon, size in MAJOR_HOSPITALS:
        distance_m = _haversine_distance(lat, lon, hosp_lat, hosp_lon)
        distance_km = distance_m / 1000.0
        
        # Only include hospitals within max_distance_km
        if distance_km <= max_distance_km:
            hospitals.append({
                "name": name,
                "distance_km": round(distance_km, 1),
                "size": size,
                "source": "major_hospitals_database",
                "tags": {
                    "emergency": "yes",  # Major hospitals typically have ER
                    "healthcare": "hospital"
                }
            })
    
    return hospitals


def _get_vacation_healthcare_score(lat: float, lon: float) -> Tuple[float, Dict]:
    """
    Vacation-mode HC: distance to nearest hospital only.
    Measures emergency access, not residential healthcare adequacy.
    Curve: ≤5km→90, ≤15km→75, ≤30km→60, ≤60km→45, ≤90km→30, >90km→20
    """
    healthcare_data = _get_osm_healthcare(lat, lon)
    hospitals = healthcare_data.get('hospitals', [])

    nearest_km: Optional[float] = None
    nearest_name: Optional[str] = None

    with_dist = _with_numeric_distance(hospitals)
    if with_dist:
        nearest = min(with_dist, key=lambda x: x['distance_km'])
        nearest_km = nearest['distance_km']
        nearest_name = nearest.get('name')

    if nearest_km is None:
        _, nearest_db = _score_hospitals(lat, lon)
        if nearest_db:
            nearest_km = nearest_db['distance_km']
            nearest_name = nearest_db.get('name')

    if nearest_km is None:
        score = 20.0
    elif nearest_km <= 5:
        score = 90.0
    elif nearest_km <= 15:
        score = 75.0
    elif nearest_km <= 30:
        score = 60.0
    elif nearest_km <= 60:
        score = 45.0
    elif nearest_km <= 90:
        score = 30.0
    else:
        score = 20.0

    confidence = 80 if nearest_km is not None and nearest_km < 100 else 30
    print(f"✅ Vacation Healthcare Score: {score:.0f}/100 (nearest hospital: {nearest_name}, {nearest_km}km)")
    return round(score, 1), {
        'score': score,
        'breakdown': {'hospital_distance': score},
        'summary': {
            'nearest_hospital_km': nearest_km,
            'nearest_hospital_name': nearest_name,
            'scoring_mode': 'vacation_distance_only',
        },
        'data_quality': {'confidence': confidence, 'quality_tier': 'good'},
    }


def get_healthcare_access_score(lat: float, lon: float,
                                area_type: Optional[str] = None,
                                location_scope: Optional[str] = None,
                                city: Optional[str] = None,
                                density: Optional[float] = None,
                                vacation_mode: bool = False,
                                place_context=None) -> Tuple[float, Dict]:
    """
    Calculate healthcare access score (0-100).

    Scoring (design principles v2): one radius (10 km) and one scale for every place, no area type or density table.
    - Hospital Access (15 points): distance to the nearest hospital (falls back to MAJOR_HOSPITALS up to 60 km). The
      hospital count is not scored (a count is not capacity); the score is scaled over the components that are scored.
    - Primary Care (0-25): clinics plus doctors per resident within the radius against the catalog-median supply
    - Specialized Care (0-15): distinct specialty tags available (measures OpenStreetMap tagging; kept as is)
    - Emergency Services (0-10): distance to the nearest hospital with an emergency room
    - Pharmacies (0-15): distance to the nearest pharmacy (full credit within half a mile, half at one mile)
    - A component that cannot be read (no pharmacy mapped near mapped clinics, residents unknown) is left out and the
      score is scaled over the rest. Bonus for extra hospitals shown separately (cap at 100)

    Failure handling (design principles v2, P9):
    - A failed OSM read raises (the pillar shows no data and is retried); it is never scored as zero facilities and
      no invented component scores are applied. If Google Places recovered facilities, the result is flagged degraded.
    - If OSM succeeds but lists no hospital, MAJOR_HOSPITALS supplies the distance to the nearest real hospital.

    Returns:
        (total_score, detailed_breakdown)
    """
    if vacation_mode:
        return _get_vacation_healthcare_score(lat, lon)

    print(f"🏥 Analyzing healthcare access...")

    # Use provided area_type if available (already computed in main.py)
    # Only detect if not provided to avoid redundant API calls
    from data_sources.place_context import resolve_place_context
    ctx = resolve_place_context(lat, lon, place_context=place_context, area_type=area_type, density=density, city=city, need_density=True)
    area_type, pop_density = ctx.area_type, ctx.density

    # One radius and one scale for every place: no area type or density table. Capacity parts compare the facilities
    # within the radius to the residents within it (catalog-median supply per resident, data/healthcare_supply_scale.json).
    fac_radius_m = pharm_radius_m = HEALTHCARE_RADIUS_M
    residents = ctx.people_10km if getattr(ctx, "people_10km", None) is not None else people_within(lat, lon, HEALTHCARE_RADIUS_M)
    supply_scale = _load_supply_scale() or {}
    exp_prim_per_1000 = float(supply_scale.get("expected_clinics_doctors_per_1000") or 0.0)
    print(f"   🔧 Healthcare: radius={HEALTHCARE_RADIUS_M}m, residents within radius={'unknown' if residents is None else round(residents)}")

    # Query OSM for healthcare facilities (hospitals, clinics, doctors, pharmacies, urgent/emergency)
    print(f"   💊 Querying pharmacies and clinics...")
    healthcare_facilities = _get_osm_healthcare(lat, lon)
    
    hospitals = healthcare_facilities.get("hospitals", [])
    urgent_care = healthcare_facilities.get("urgent_care", [])
    pharmacies = healthcare_facilities.get("pharmacies", [])
    clinics = healthcare_facilities.get("clinics", [])
    doctors = healthcare_facilities.get("doctors", [])
    query_failed = healthcare_facilities.get("_query_failed", False)
    
    # FALLBACK: Use MAJOR_HOSPITALS database if OSM query failed or returned no hospitals
    # This ensures we have hospital data even when OSM is unavailable (rate limits, timeouts, etc.)
    # This follows design principles: scalable fallback, not location-specific exceptions
    if query_failed or len(hospitals) == 0:
        print(f"   🔄 Using MAJOR_HOSPITALS database as fallback...")
        fallback_hospitals = _get_fallback_hospitals(lat, lon, max_distance_km=60.0)
        if fallback_hospitals:
            # Merge with OSM hospitals (if any), avoiding duplicates by name
            existing_names = {h.get("name", "").lower() for h in hospitals}
            for fb_hosp in fallback_hospitals:
                if fb_hosp.get("name", "").lower() not in existing_names:
                    hospitals.append(fb_hosp)
            print(f"   ✅ Added {len(fallback_hospitals)} hospitals from fallback database")
    
    # Google Places augmentation: supplements thin or failed OSM data
    places_meta = maybe_augment_healthcare_with_places(
        lat, lon,
        radius_m=fac_radius_m,
        hospitals=hospitals,
        urgent_care=urgent_care,
        pharmacies=pharmacies,
        clinics=clinics,
        doctors=doctors,
        query_failed=query_failed,
    )
    if places_meta.get("triggered"):
        print(f"   🔍 Places HC: {places_meta['reason']} — added {places_meta['hospitals_added']} hospitals, {places_meta['pharmacies_added']} pharmacies, {places_meta['doctors_added']} doctors (calls={places_meta['http_calls']})")

    # A failed OSM read is no data, not zero facilities (design principles v2, P9). Retry later; the pillar drops out of the
    # headline meanwhile. If Google Places (when enabled) added facilities after the failure, the data is real and the
    # result is flagged degraded instead.
    places_recovered = bool(places_meta.get("triggered")) and (
        (places_meta.get("hospitals_added") or 0) + (places_meta.get("pharmacies_added") or 0)
        + (places_meta.get("doctors_added") or 0)
    ) > 0
    if query_failed and not places_recovered:
        raise RuntimeError("healthcare facility read failed (Overpass); no data until it is retried")

    # Log warning if no data found (could indicate OSM failure)
    if not hospitals and not urgent_care and not pharmacies and not clinics and not doctors:
        print(f"   ⚠️  WARNING: No healthcare facilities found. This may indicate:")
        print(f"      - OSM query failed (rate limit, timeout, or network error)")
        print(f"      - No healthcare facilities in OSM for this location")
        print(f"      - Query radius too small or location data incomplete")
        print(f"      - Location outside coverage of MAJOR_HOSPITALS database")
    
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
    denom = max(1.0, ((pop_density or 0.0) / 10000.0))

    # 1) Hospital access (0-35 points) - DATA-BACKED RATIO-BASED + DISTANCE-BASED SCORING
    # Combine count-based (ratio to expected) and distance-based (proximity) scoring
    # This provides comprehensive scoring that follows design principles
    
    # (the 20-point count part is left out, see below)
    hospital_count = len(hospitals)
    # Hospital count is not scored: a count says nothing about capacity (a city medical centre and a small hospital count
    # the same), and hospitals per resident falls in the densest places where the hospitals are largest. Hospital access
    # is the distance to the nearest hospital, and the score is scaled over the components that are scored.
    hospital_count_score = None
    
    # Distance-based score (0-15 points): Proximity to nearest hospital
    # IMPORTANT: Use fallback hospitals for distance scoring even if they're beyond filter radius
    # This provides partial credit for hospitals within reasonable distance (up to 60km)
    nearest_dist_km = float('inf')
    
    if len(hospitals) > 0:
        # Use nearest hospital from OSM results (already filtered by radius)
        numeric_hospitals = _with_numeric_distance(hospitals)
        if numeric_hospitals:
            nearest_osm = min(numeric_hospitals, key=lambda x: x["distance_km"])
            nearest_dist_km = nearest_osm["distance_km"]
    
    # FALLBACK: If no OSM hospitals within radius, or if OSM query failed,
    # use MAJOR_HOSPITALS database for distance scoring (up to 60km)
    # This ensures we get distance-based credit even when OSM data is unavailable
    if nearest_dist_km == float('inf') or query_failed:
        _, nearest_db = _score_hospitals(lat, lon)
        if nearest_db:
            nearest_dist_km = nearest_db["distance_km"]
            # Log that we're using fallback for distance scoring
            if query_failed:
                logger.debug(f"Using fallback hospital database for distance scoring: {nearest_db.get('name')} at {nearest_dist_km}km")
    
    # Distance-based scoring using smooth exponential decay
    hospital_distance_score = _distance_to_hospital_score(nearest_dist_km, max_score=15.0)
    
    # Total hospital score: count (0-20) + distance (0-15) = 0-35 points
    hospital_score = (hospital_count_score or 0.0) + hospital_distance_score
    hospital_score = min(35.0, hospital_score)
    
    # Bonus for additional hospitals beyond first (shown separately)
    hospital_bonus = 0.0
    if len(hospitals) > 1:
        # Small bonus for multiple hospitals (indicates choice and redundancy)
        hospital_bonus = min(5.0, float(len(hospitals) - 1) * 0.5)

    # 2) Primary care access (25 points) – DATA-BACKED RATIO-BASED SCORING
    # Use data-backed curve based on ratio of clinics+doctors to expected urgent care
    primary_count = len(clinics) + len(doctors)
    primary_score = capacity_score(primary_count, residents, exp_prim_per_1000, 1000.0, 25.0)
    if primary_score is not None:
        primary_score = min(25.0, primary_score)

    # 3) Specialized care (15 points) – DATA-BACKED COUNT-BASED SCORING
    # Count unique specialties and score using data-backed curve
    # Expected: ~5-10 specialties for good access (conservative estimate)
    import re
    specialties = set()
    for f in (hospitals + clinics + doctors):
        spec = (f.get('tags', {}).get('healthcare:speciality') or '')
        for part in re.split(r"[;,|]", spec):
            s = part.strip().lower()
            if s:
                specialties.add(s)
    
    specialty_count = len(specialties)
    # Expected: ~8 specialties for good access (conservative estimate based on typical hospital)
    expected_specialties = 8.0
    
    if specialty_count <= 0:
        # Try NPI federal registry whenever specialty tags are absent — fires whether the
        # gap comes from Overpass failure or (more commonly) missing OSM specialty tagging.
        state = _state_from_latlon(lat, lon)
        npi_count = _npi_specialty_count(city or "", state, lat=lat, lon=lon)
        if npi_count > 0:
            specialty_count = npi_count
            print(f"   🏥 NPI specialty count: {npi_count} (state={state})")

        if specialty_count > 0:
            specialty_ratio = specialty_count / expected_specialties
            specialty_score = _ratio_score(specialty_ratio, max_score=15.0)
        else:
            specialty_score = 0.0
    else:
        specialty_ratio = specialty_count / expected_specialties
        # Use data-backed curve for smooth scoring
        specialty_score = _ratio_score(specialty_ratio, max_score=15.0)
    
    specialty_score = min(15.0, specialty_score)

    # 4) Emergency services (10 points): distance to the nearest hospital with an emergency room
    emergency_hospitals = [
        f for f in hospitals
        if (f.get('tags', {}).get('emergency') == 'yes') or (f.get('emergency') == 'yes')
    ]
    emergency_count = len(emergency_hospitals)
    # Distance to the nearest emergency-room hospital on the hospital distance curve (one scale for every place).
    # With none inside the radius, the nearest major hospital in the fallback database (up to 60 km) stands in.
    er_distances = [f["distance_km"] for f in _with_numeric_distance(emergency_hospitals)]
    if er_distances:
        nearest_er_km = min(er_distances)
    else:
        _, nearest_db_er = _score_hospitals(lat, lon)
        nearest_er_km = nearest_db_er["distance_km"] if nearest_db_er else float("inf")
    emergency_score = min(10.0, _distance_to_hospital_score(nearest_er_km, max_score=10.0))

    # 5) Pharmacy access (15 points): distance to the nearest pharmacy on one scale for every place.
    # No pharmacy inside the search radius where hospitals, clinics or doctors are mapped is treated as unknown
    # (OpenStreetMap often lacks pharmacy tags there), so the component is left out and the score is scaled over the
    # rest. When nothing at all is mapped in a successful read, the empty result stays a real zero.
    numeric_pharmacies = _with_numeric_distance(pharmacies)
    if numeric_pharmacies:
        nearest_pharm_km = min(f["distance_km"] for f in numeric_pharmacies)
        pharmacy_score: Optional[float] = 15.0 * _pharmacy_distance_fraction(nearest_pharm_km)
    elif hospitals or urgent_care or clinics or doctors:
        pharmacy_score = None
    else:
        pharmacy_score = 0.0

    parts = {
        "hospital_access": hospital_score,
        "primary_care": primary_score,
        "specialized_care": specialty_score,
        "emergency_services": emergency_score,
        "pharmacies": pharmacy_score,
    }
    budgets = dict(HEALTHCARE_BUDGETS)
    if hospital_count_score is None:
        budgets["hospital_access"] = 15.0  # only the distance part is scored
    total_score = healthcare_total(parts, hospital_bonus, budgets)

    # Assess data quality
    combined_data = {
        'hospitals': hospitals,
        'urgent_care': urgent_care,
        'pharmacies': pharmacies,
        'clinics': clinics,
        'doctors': doctors,
        'total_score': total_score
    }
    
    quality_metrics = data_quality.assess_pillar_data_quality('healthcare_access', combined_data, lat, lon, area_type, density=pop_density)
    
    # OSM failed but Google Places supplied facilities: the data is real but thinner, so flag it.
    if query_failed:
        quality_metrics['degraded'] = True
        quality_metrics['degraded_reasons'] = list(dict.fromkeys(
            list(quality_metrics.get('degraded_reasons') or []) + ["osm_query_failed_recovered_from_google_places"]))
        print("   ⚠️  OSM query failed; facilities recovered from Google Places (flagged degraded)")

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
    else:
        # Fallback to MAJOR_HOSPITALS database if no OSM hospitals with distances
        _, nearest_db = _score_hospitals(lat, lon)
        if nearest_db:
            nearest_hospital = {
                "name": nearest_db.get('name', 'Unknown Hospital'),
                "distance_km": nearest_db.get('distance_km')
            }

    # Get area classification for metadata (use provided area_type if available)
    try:
        if area_type:
            # Use provided area_type, but still need metro_name for metadata
            from data_sources.regional_baselines import regional_baseline_manager
            metro_name = regional_baseline_manager._detect_metro_area(city, lat, lon)
            area_metadata = {
                'density': pop_density,
                'metro_name': metro_name,
                'area_type': area_type,
                'classification_confidence': regional_baseline_manager._get_classification_confidence(pop_density, metro_name)
            }
        else:
            # Fallback: compute area type if not provided (use same method as main.py)
            # Use module-level data_quality import (already imported at top of file)
            area_type = data_quality.detect_area_type(lat, lon, density=pop_density, city=city)
            # Get metadata separately
            from data_sources.regional_baselines import regional_baseline_manager
            metro_name = regional_baseline_manager._detect_metro_area(city, lat, lon)
            area_metadata = {
                'density': pop_density,
                'metro_name': metro_name,
                'area_type': area_type,
                'classification_confidence': regional_baseline_manager._get_classification_confidence(pop_density, metro_name)
            }
    except Exception as e:
        # Fallback if area classification fails
        logger.warning(f"Area classification failed: {e}")
        area_metadata = {
            'density': pop_density,
            'metro_name': None,
            'area_type': area_type or 'unknown',
            'classification_confidence': 0.0
        }
    
    breakdown = {
        "score": round(total_score, 1),
        "breakdown": {
            "hospital_access": round(hospital_score, 1),
            "primary_care": None if primary_score is None else round(primary_score, 1),
            "specialized_care": round(specialty_score, 1),
            "emergency_services": round(emergency_score, 1),
            "pharmacies": None if pharmacy_score is None else round(pharmacy_score, 1)
        },
        "bonuses": {
            "hospital_bonus": round(hospital_bonus, 1)  # Additional hospitals beyond first
        },
        "summary": _build_summary(
            nearest_hospital, urgent_care, pharmacies, clinics
        ),
        "data_quality": quality_metrics,
        "area_classification": area_metadata,
        "places_augmentation": places_meta if places_meta.get("triggered") else None,
    }

    # Enrich summary with counts
    try:
        breakdown["summary"]["hospital_count"] = len(hospitals)
    except Exception:
        pass
    if pharmacy_score is None:
        breakdown["summary"]["pharmacies_unknown"] = True
    breakdown["summary"]["facility_radius_m"] = HEALTHCARE_RADIUS_M
    breakdown["summary"]["residents_within_radius"] = None if residents is None else round(residents)

    # Log results
    print(f"✅ Healthcare Access Score: {total_score:.0f}/100")
    print(f"   🏥 Hospital Access: {hospital_score:.0f}/35 ({len(hospitals)} hospitals)")
    if hospital_bonus > 0:
        print(f"      + Hospital Bonus: {hospital_bonus:.0f} (additional hospitals)")
    print(f"   🩺 Primary Care: {'unknown' if primary_score is None else f'{primary_score:.0f}'}/25 (clinics={len(clinics)}, doctors={len(doctors)})")
    print(f"   🧠 Specialized Care: {specialty_score:.0f}/15 (specialties={len(specialties)})")
    print(f"   🚨 Emergency Services: {emergency_score:.0f}/10 (emergency_hospitals={len(emergency_hospitals)})")
    print(f"   💊 Pharmacies: {'unknown (none in radius)' if pharmacy_score is None else f'{pharmacy_score:.0f}/15'} ({len(pharmacies)} nearby)")
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

    # Flat fields for UI (avoid nested objects in detail rows)
    if nearest_hospital and isinstance(nearest_hospital, dict):
        nk = nearest_hospital.get("distance_km")
        if nk is not None:
            try:
                summary["nearest_hospital_km"] = round(float(nk), 2)
            except (TypeError, ValueError):
                pass
        nm = nearest_hospital.get("name")
        if nm:
            summary["nearest_hospital_name"] = str(nm)
    if summary.get("nearest_pharmacy") and isinstance(summary["nearest_pharmacy"], dict):
        pk = summary["nearest_pharmacy"].get("distance_km")
        if pk is not None:
            try:
                summary["nearest_pharmacy_km"] = round(float(pk), 2)
            except (TypeError, ValueError):
                pass

    return summary