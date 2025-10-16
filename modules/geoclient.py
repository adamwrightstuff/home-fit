import requests
from typing import Optional, Tuple

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

def geocode(address: str) -> Optional[Tuple[float, float, str, str, str]]:
    """
    Geocode an address using Nominatim.
    
    Returns:
        (lat, lon, zip_code, state, city) or None if failed
    """
    print(f"📍 Using Nominatim for '{address}'")
    
    try:
        params = {
            "q": address,
            "format": "json",
            "addressdetails": 1,
            "limit": 1,
            "countrycodes": "us"  # Restrict to US
        }
        
        headers = {
            "User-Agent": "HomeFit/1.0 (livability scoring tool)"
        }
        
        resp = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=10)
        
        if resp.status_code != 200:
            print(f"❌ Nominatim error: HTTP {resp.status_code}")
            return None
        
        results = resp.json()
        
        if not results:
            print("❌ Nominatim returned no results")
            return None
        
        result = results[0]
        
        # Extract coordinates
        lat = float(result.get("lat"))
        lon = float(result.get("lon"))
        
        # Extract address details
        addr = result.get("address", {})
        
        # Handle ZIP code (remove +4 if present)
        zip_code = addr.get("postcode", "")
        if zip_code:
            zip_code = zip_code.split("-")[0].strip()
        
        # Handle state (convert to abbreviation if needed)
        state = addr.get("state", "")
        if state:
            state = _normalize_state(state)
        
        # Handle city - try multiple fields
        city = (
            addr.get("city") or 
            addr.get("town") or 
            addr.get("village") or
            addr.get("municipality") or
            addr.get("county", "").replace(" County", "")
        )
        
        # For NYC boroughs, Nominatim sometimes returns "New York"
        # Try to get the borough from the neighborhood/suburb field
        if city == "New York":
            borough = addr.get("suburb") or addr.get("neighbourhood")
            if borough:
                # Map common borough names
                borough_map = {
                    "Brooklyn": "Brooklyn",
                    "Queens": "Queens",
                    "Manhattan": "Manhattan",
                    "Bronx": "Bronx",
                    "Staten Island": "Staten Island"
                }
                for key, value in borough_map.items():
                    if key.lower() in borough.lower():
                        city = value
                        break
        
        print(f"✅ Nominatim success → {lat}, {lon}")
        print(f"   City: {city}, State: {state}, ZIP: {zip_code}")
        
        return lat, lon, zip_code, state, city
        
    except Exception as e:
        print(f"❌ Nominatim failed: {e}")
        return None


def _normalize_state(state: str) -> str:
    """Convert state name to abbreviation."""
    state_map = {
        "alabama": "AL",
        "alaska": "AK",
        "arizona": "AZ",
        "arkansas": "AR",
        "california": "CA",
        "colorado": "CO",
        "connecticut": "CT",
        "delaware": "DE",
        "florida": "FL",
        "georgia": "GA",
        "hawaii": "HI",
        "idaho": "ID",
        "illinois": "IL",
        "indiana": "IN",
        "iowa": "IA",
        "kansas": "KS",
        "kentucky": "KY",
        "louisiana": "LA",
        "maine": "ME",
        "maryland": "MD",
        "massachusetts": "MA",
        "michigan": "MI",
        "minnesota": "MN",
        "mississippi": "MS",
        "missouri": "MO",
        "montana": "MT",
        "nebraska": "NE",
        "nevada": "NV",
        "new hampshire": "NH",
        "new jersey": "NJ",
        "new mexico": "NM",
        "new york": "NY",
        "north carolina": "NC",
        "north dakota": "ND",
        "ohio": "OH",
        "oklahoma": "OK",
        "oregon": "OR",
        "pennsylvania": "PA",
        "rhode island": "RI",
        "south carolina": "SC",
        "south dakota": "SD",
        "tennessee": "TN",
        "texas": "TX",
        "utah": "UT",
        "vermont": "VT",
        "virginia": "VA",
        "washington": "WA",
        "west virginia": "WV",
        "wisconsin": "WI",
        "wyoming": "WY",
        "district of columbia": "DC",
        "washington dc": "DC",
        "washington, d.c.": "DC"
    }
    
    state_lower = state.lower().strip()
    
    # If already abbreviated, return uppercase
    if len(state) == 2:
        return state.upper()
    
    # Look up in map
    return state_map.get(state_lower, state.upper()[:2])