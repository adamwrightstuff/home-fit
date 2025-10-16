import requests

def get_coordinates(location):
    """
    Takes an address or ZIP, geocodes it using Nominatim,
    and returns latitude, longitude, ZIP, state (abbrev), and city.
    """

    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": location, "format": "json", "addressdetails": 1}

    try:
        response = requests.get(
    url,
    params=params,
    headers={"User-Agent": "HomeFit/1.0 (contact: contact@homefit.local)"},
    timeout=10
)
        response.raise_for_status()
        if not response.text.strip():
            print(f"❌ Empty response from Nominatim for '{location}'")
            return None, None, None, None, None
        data = response.json()
    except Exception as e:
        print(f"❌ Nominatim API error for '{location}': {e}")
        return None, None, None, None, None

    if not data:
        print(f"❌ No results from Nominatim for '{location}'")
        return None, None, None, None, None

    result = data[0]
    lat = float(result["lat"])
    lon = float(result["lon"])
    address = result.get("address", {})

    zip_code = address.get("postcode", "")
    state_full = address.get("state")
    city = (
        address.get("city")
        or address.get("town")
        or address.get("village")
        or address.get("county")
    )

    # --- Normalize state names to 2-letter abbreviations ---
    STATE_ABBREVIATIONS = {
        "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
        "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
        "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID",
        "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
        "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
        "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN",
        "Mississippi": "MS", "Missouri": "MO", "Montana": "MT", "Nebraska": "NE",
        "Nevada": "NV", "New Hampshire": "NH", "New Jersey": "NJ",
        "New Mexico": "NM", "New York": "NY", "North Carolina": "NC",
        "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR",
        "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
        "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT",
        "Vermont": "VT", "Virginia": "VA", "Washington": "WA",
        "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
        "District of Columbia": "DC"
    }

    state = STATE_ABBREVIATIONS.get(state_full, state_full)

    # Clean up “City of ...”
    if city and city.lower().startswith("city of "):
        city = city[8:].strip()

    print(f"📍 Geocoded '{location}' → ({lat}, {lon}) ZIP={zip_code} STATE={state} CITY={city}")

    return lat, lon, zip_code, state, city
