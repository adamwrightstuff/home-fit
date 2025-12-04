"""
Investigate housing data issues:
1. Ann Arbor income data error
2. Brickell data quality tier bug
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_sources import census_api
from pillars import housing_value

def test_ann_arbor():
    """Test Ann Arbor income data"""
    print("=" * 60)
    print("TESTING: Ann Arbor MI")
    print("=" * 60)
    lat, lon = 42.2813722, -83.7484616
    
    # Get census tract
    tract = census_api.get_census_tract(lat, lon)
    if tract:
        print(f"\n📍 Census Tract: {tract.get('name', 'Unknown')}")
        print(f"   State FIPS: {tract.get('state_fips')}")
        print(f"   County FIPS: {tract.get('county_fips')}")
        print(f"   Tract FIPS: {tract.get('tract_fips')}")
    
    # Get housing data
    print("\n📊 Fetching housing data...")
    housing_data = census_api.get_housing_data(lat, lon, tract=tract)
    
    if housing_data:
        print(f"\n✅ Housing Data Retrieved:")
        print(f"   Median home value: ${housing_data['median_home_value']:,.0f}")
        print(f"   Median household income: ${housing_data['median_household_income']:,.0f}")
        print(f"   Median rooms: {housing_data['median_rooms']:.1f}")
        
        # Check for suspicious values
        income = housing_data['median_household_income']
        if income < 30000:
            print(f"\n⚠️  WARNING: Income seems suspiciously low: ${income:,.0f}")
            print(f"   Expected range for Ann Arbor: $60,000-$70,000+")
    else:
        print("\n❌ Failed to retrieve housing data")
    
    # Get housing score
    print("\n🏠 Calculating housing score...")
    score, breakdown = housing_value.get_housing_value_score(lat, lon, census_tract=tract, city="Ann Arbor")
    
    print(f"\n📈 Housing Score: {score}/100")
    print(f"   Breakdown: {breakdown.get('breakdown', {})}")
    print(f"   Data Quality: {breakdown.get('data_quality', {})}")
    
    # Check data quality tier
    quality_tier = breakdown.get('data_quality', {}).get('quality_tier')
    print(f"\n🔍 Data Quality Tier Type: {type(quality_tier)}")
    print(f"   Value: {repr(quality_tier)}")
    if not isinstance(quality_tier, str):
        print(f"   ⚠️  WARNING: Quality tier is not a string!")


def test_brickell():
    """Test Brickell data quality tier"""
    print("\n" + "=" * 60)
    print("TESTING: Brickell Miami FL")
    print("=" * 60)
    lat, lon = 25.7625951, -80.1952987
    
    # Get census tract
    tract = census_api.get_census_tract(lat, lon)
    if tract:
        print(f"\n📍 Census Tract: {tract.get('name', 'Unknown')}")
    
    # Get housing score
    print("\n🏠 Calculating housing score...")
    score, breakdown = housing_value.get_housing_value_score(lat, lon, census_tract=tract, city="Miami")
    
    print(f"\n📈 Housing Score: {score}/100")
    print(f"   Breakdown: {breakdown.get('breakdown', {})}")
    
    # Check data quality
    data_quality = breakdown.get('data_quality', {})
    print(f"\n📊 Data Quality Metrics:")
    for key, value in data_quality.items():
        print(f"   {key}: {repr(value)} (type: {type(value).__name__})")
    
    quality_tier = data_quality.get('quality_tier')
    print(f"\n🔍 Data Quality Tier:")
    print(f"   Type: {type(quality_tier)}")
    print(f"   Value: {repr(quality_tier)}")
    
    if not isinstance(quality_tier, str):
        print(f"   ⚠️  ERROR: Quality tier is not a string!")
        print(f"   Expected one of: 'excellent', 'good', 'fair', 'poor', 'very_poor'")
    elif quality_tier not in ['excellent', 'good', 'fair', 'poor', 'very_poor']:
        print(f"   ⚠️  WARNING: Quality tier '{quality_tier}' is not a recognized value")


def check_census_api_response():
    """Check raw Census API response for Ann Arbor"""
    print("\n" + "=" * 60)
    print("TESTING: Raw Census API Response for Ann Arbor")
    print("=" * 60)
    lat, lon = 42.2813722, -83.7484616
    
    tract = census_api.get_census_tract(lat, lon)
    if not tract:
        print("❌ Failed to get census tract")
        return
    
    print(f"\n📍 Tract Info: {tract.get('name')}")
    
    # Make direct API call to see raw response
    import requests
    from dotenv import load_dotenv
    load_dotenv()
    import os
    
    CENSUS_API_KEY = os.getenv("CENSUS_API_KEY")
    CENSUS_BASE_URL = "https://api.census.gov/data"
    
    url = f"{CENSUS_BASE_URL}/2022/acs/acs5"
    params = {
        "get": "B25077_001E,B19013_001E,B25018_001E,NAME",
        "for": f"tract:{tract['tract_fips']}",
        "in": f"state:{tract['state_fips']} county:{tract['county_fips']}",
        "key": CENSUS_API_KEY,
    }
    
    print(f"\n🔗 API URL: {url}")
    print(f"   Parameters: {params}")
    
    try:
        response = requests.get(url, params=params, timeout=10)
        print(f"\n📡 Response Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n📦 Raw Response:")
            print(f"   Headers: {data[0] if data else 'No headers'}")
            if len(data) > 1:
                print(f"   Data Row: {data[1]}")
                print(f"\n   Parsed Values:")
                print(f"      Home Value (B25077_001E): {data[1][0]}")
                print(f"      Income (B19013_001E): {data[1][1]}")
                print(f"      Rooms (B25018_001E): {data[1][2]}")
                
                # Check for special codes
                income_raw = data[1][1]
                if income_raw == "-666666666":
                    print(f"      ⚠️  Income is Census null code (-666666666)")
                elif income_raw and isinstance(income_raw, str) and income_raw.startswith("-"):
                    print(f"      ⚠️  Income has negative code: {income_raw}")
        else:
            print(f"   Response text: {response.text[:500]}")
    except Exception as e:
        print(f"   ❌ Error: {e}")


if __name__ == "__main__":
    test_ann_arbor()
    test_brickell()
    check_census_api_response()

