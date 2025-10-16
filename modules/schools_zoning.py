import requests

def get_zoned_school_score(state, lat, lon):
    """
    Looks up NYC DOE school zoning (elementary, middle, high) using ArcGIS.
    Returns a dict of zoned schools or None if outside NYC / no match.
    """

    # --- Only run for New York State ---
    if state != "NY":
        return None

    url = "https://services5.arcgis.com/GfwWNkhOj9bNBqoJ/ArcGIS/rest/services/School_Zones/FeatureServer/0/query"

    params = {
        "where": "1=1",
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "distance": 30,               # 🔧 small buffer to catch near-boundary addresses
        "units": "esriSRUnit_Meter",  # use meters for the buffer
        "outFields": "*",
        "returnGeometry": "false",
        "f": "json"
    }

    print(f"🗺️ Querying NYC DOE Zoning at {url}")

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        features = data.get("features", [])
        if not features:
            print(f"⚠️ No zoning feature found for NY coordinate ({lat}, {lon})")
            return None

        attrs = features[0].get("attributes", {})
        schools = {
            "elementary": attrs.get("ES", None),
            "middle": attrs.get("MS", None),
            "high": attrs.get("HS", None)
        }

        print(f"🏫 NYC DOE assigned schools → {schools}")
        return schools

    except Exception as e:
        print(f"❌ Error calling NYC DOE ArcGIS: {e}")
        return None
