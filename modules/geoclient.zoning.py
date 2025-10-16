
import os, requests

def get_nyc_zoned_schools(lat, lon):
    """
    Calls NYC GeoClient API to get DOE zoned schools (elementary, middle, high)
    for a given coordinate pair.
    """
    app_id = os.getenv("GEOCITY_APPID")
    app_key = os.getenv("GEOCITY_APPKEY")

    url = "https://api.nyc.gov/geo/geoclient/v1/latlong.json"
    params = {
        "latitude": lat,
        "longitude": lon,
        "app_id": app_id,
        "app_key": app_key
    }

    print(f"🗺️ Querying NYC GeoClient for DOE zoning → {url}")
    try:
        res = requests.get(url, params=params, timeout=10)
        data = res.json()

        if "latLong" not in data:
            print(f"⚠️ No latLong object returned: {data}")
            return None

        info = data["latLong"]["address"]
        zoned = {
            "elementary": info.get("schoolNumberElementary"),
            "middle": info.get("schoolNumberMiddle"),
            "high": info.get("schoolNumberHigh")
        }

        if any(zoned.values()):
            print(f"🏫 NYC DOE assigned schools → {zoned}")
            return zoned
        else:
            print("⚠️ No DOE school assignments found for this coordinate.")
            return None

    except Exception as e:
        print(f"❌ GeoClient error: {e}")
        return None
