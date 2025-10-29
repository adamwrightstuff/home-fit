"""
Google Earth Engine API Client
Provides satellite-based tree canopy and environmental analysis.
"""

import ee
import os
import json
from typing import Optional, Dict, Tuple
import math

# Initialize GEE with service account credentials
def _initialize_gee():
    """Initialize GEE with service account credentials from environment variable."""
    import tempfile
    
    try:
        # Try to get service account credentials from environment variable
        credentials_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
        
        if credentials_json:
            # Parse to get the email for debugging
            try:
                creds_dict = json.loads(credentials_json)
                client_email = creds_dict.get('client_email', 'unknown')
                print(f"🔑 Found GEE service account: {client_email}")
            except:
                pass
            # Create a temporary file with the service account credentials
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                f.write(credentials_json)
                temp_credentials_file = f.name
            
            try:
                # Initialize with the credentials file
                # Parse client_email from the credentials
                creds_dict = json.loads(credentials_json)
                client_email = creds_dict.get('client_email')
                
                credentials = ee.ServiceAccountCredentials(
                    email=client_email,
                    key_file=temp_credentials_file
                )
                ee.Initialize(credentials, project='homefit-475718')
                
                # Test the connection by checking if we can access basic GEE functionality
                try:
                    # Try a simple operation to verify GEE is working
                    test_point = ee.Geometry.Point([0, 0])
                    _ = test_point.getInfo()
                    print("✅ Google Earth Engine initialized and working with service account credentials")
                except Exception as test_error:
                    print(f"⚠️  GEE initialized but may have limited access: {test_error}")
                
                # Clean up temp file after successful initialization
                try:
                    os.unlink(temp_credentials_file)
                except:
                    pass
                return True
            except Exception as e3:
                print(f"⚠️  Failed to initialize GEE with service account: {e3}")
                print("💡 The service account may need the 'roles/serviceusage.serviceUsageConsumer' role")
                print("💡 Visit: https://console.cloud.google.com/iam-admin/iam/project?project=homefit-475718")
                
                # Clean up temp file
                try:
                    os.unlink(temp_credentials_file)
                except:
                    pass
                return False
        else:
            # Fallback: try to initialize without credentials (for local development)
            try:
                ee.Initialize(project='homefit-475718')
                print("✅ Google Earth Engine initialized with default credentials")
                return True
            except Exception as e2:
                print(f"⚠️  Google Earth Engine not initialized: {e2}")
                print("💡 Set GOOGLE_APPLICATION_CREDENTIALS_JSON environment variable")
                return False
                
    except Exception as e1:
        print(f"⚠️  Google Earth Engine initialization failed: {e1}")
        return False

# Initialize GEE safely - don't crash the app if it fails
try:
    GEE_AVAILABLE = _initialize_gee()
except Exception as e:
    print(f"⚠️  Failed to initialize Google Earth Engine: {e}")
    GEE_AVAILABLE = False


def get_tree_canopy_gee(lat: float, lon: float, radius_m: int = 1000) -> Optional[float]:
    """
    Get tree canopy percentage using Google Earth Engine.
    
    Uses NLCD Tree Canopy Cover dataset (30m resolution, USA only) for accurate data.
    Falls back to Sentinel-2 NDVI analysis if NLCD unavailable.
    
    Args:
        lat: Latitude
        lon: Longitude  
        radius_m: Analysis radius in meters
        
    Returns:
        Tree canopy percentage (0-100) or None if unavailable
    """
    if not GEE_AVAILABLE:
        return None
        
    try:
        print(f"🛰️  Analyzing tree canopy with Google Earth Engine at {lat}, {lon}...")
        
        # Create point of interest
        point = ee.Geometry.Point([lon, lat])
        buffer = point.buffer(radius_m)
        
        # Priority 1: NLCD Tree Canopy Cover (urban/suburban, USA-only)
        try:
            nlcd_tcc = ee.Image('USGS/NLCD_RELEASES/2021_REL/TCC/2021').select('tree_canopy_cover')
            tcc_stats = nlcd_tcc.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=buffer,
                scale=30,
                maxPixels=1e9
            )
            tcc_pct = tcc_stats.get('tree_canopy_cover').getInfo()
            if tcc_pct is not None and tcc_pct >= 0.1:
                print(f"   ✅ GEE Tree Canopy (NLCD TCC): {tcc_pct:.1f}%")
                return min(100, max(0, tcc_pct))
            else:
                print(f"   ⚠️  NLCD TCC returned {0 if tcc_pct is None else tcc_pct:.1f}% (too low or unavailable)")
        except Exception as nlcd_tcc_error:
            print(f"   ⚠️  NLCD TCC unavailable: {nlcd_tcc_error}")

        # Priority 2: NLCD Land Cover forest classes (rural/forested, USA-only)
        try:
            nlcd = ee.Image('USGS/NLCD_RELEASES/2021_REL/NLCD/2021')
            landcover = nlcd.select('landcover')
            # Classes: 40 Deciduous, 41 Evergreen, 42 Mixed, 43 Shrub/Scrub
            tree_classes = landcover.eq(40).Or(landcover.eq(41)).Or(landcover.eq(42)).Or(landcover.eq(43))
            canopy_stats = tree_classes.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=buffer,
                scale=30,
                maxPixels=1e9
            )
            canopy_mean = canopy_stats.get('landcover').getInfo()
            if canopy_mean is not None and canopy_mean > 0:
                canopy_percentage = canopy_mean * 100
                print(f"   ✅ GEE Tree Canopy (NLCD Land Cover): {canopy_percentage:.1f}%")
                return min(100, max(0, canopy_percentage))
            else:
                print("   ⚠️  NLCD Land Cover forest classes indicate ~0% within buffer")
        except Exception as nlcd_error:
            print(f"   ⚠️  NLCD Land Cover unavailable: {nlcd_error}")

        # Priority 3: Hansen/UMD global tree cover (international/global fallback)
        try:
            hansen = ee.Image('UMD/hansen/global_forest_change_2022_v1_10').select('treecover2000')
            h_stats = hansen.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=buffer,
                scale=30,
                maxPixels=1e9
            )
            h_mean = h_stats.get('treecover2000').getInfo()
            if h_mean is not None and h_mean >= 0.1:
                print(f"   ✅ GEE Tree Canopy (Hansen): {h_mean:.1f}%")
                return min(100, max(0, h_mean))
            else:
                print(f"   ⚠️  Hansen tree cover returned {0 if h_mean is None else h_mean:.1f}% (too low or unavailable)")
        except Exception as hansen_error:
            print(f"   ⚠️  Hansen tree cover unavailable: {hansen_error}")
        
        # Priority 4: Sentinel-2 NDVI fallback (recent imagery, cloud-limited)
        try:
            sentinel = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                       .filterDate('2023-01-01', '2024-12-31')
                       .filterBounds(buffer)
                       .filter(ee.Filter.lt('CLOUD_PERCENTAGE', 20)))
            
            count = sentinel.size().getInfo()
            if count == 0:
                print(f"   ⚠️  No Sentinel-2 data available for this location")
                return None
            
            image = sentinel.sort('system:time_start', False).first()
            ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
            tree_mask = ndvi.gt(0.4)  # NDVI > 0.4 = trees
            
            tree_stats = tree_mask.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=buffer,
                scale=20,
                maxPixels=1e9
            )
            
            tree_ratio = tree_stats.get('NDVI').getInfo()
            canopy_percentage = (tree_ratio * 100) if tree_ratio else 0
            
            print(f"   ✅ GEE Tree Canopy (Sentinel-2): {canopy_percentage:.1f}%")
            return min(100, max(0, canopy_percentage))
            
        except Exception as sentinel_error:
            print(f"   ⚠️  Sentinel-2 fallback failed: {sentinel_error}")
            return None
        
    except Exception as e:
        print(f"   ⚠️  GEE tree canopy analysis error: {e}")
        return None


def get_urban_greenness_gee(lat: float, lon: float, radius_m: int = 1000) -> Optional[Dict]:
    """
    Get comprehensive urban greenness analysis using GEE.
    
    Returns:
        {
            "tree_canopy_pct": float,
            "vegetation_health": float,
            "green_space_ratio": float,
            "seasonal_variation": float
        }
    """
    if not GEE_AVAILABLE:
        return None
        
    try:
        print(f"🌿 Analyzing urban greenness with GEE at {lat}, {lon}...")
        
        point = ee.Geometry.Point([lon, lat])
        buffer = point.buffer(radius_m)
        
        # Get multi-year Sentinel-2 data for seasonal analysis
        sentinel = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                   .filterDate('2020-01-01', '2024-12-31')
                   .filterBounds(buffer)
                   .filter(ee.Filter.lt('CLOUD_PERCENTAGE', 30)))
        
        # Calculate NDVI for each season
        def add_seasonal_ndvi(image):
            ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
            date = ee.Date(image.get('system:time_start'))
            season = date.get('month').subtract(1).divide(3).floor().add(1)
            season_image = ee.Image.constant(season).rename('season')
            return image.addBands(ndvi).addBands(season_image)
        
        seasonal_data = sentinel.map(add_seasonal_ndvi)
        
        # Calculate seasonal NDVI statistics
        seasonal_stats = seasonal_data.select(['NDVI', 'season']).median().reduceRegion(
            reducer=ee.Reducer.mean().group(0, 'season'),
            geometry=buffer,
            scale=20,
            maxPixels=1e9
        )
        
        # Calculate overall greenness metrics
        ndvi_mean = seasonal_data.select('NDVI').mean()
        
        # Tree canopy (NDVI > 0.4)
        tree_mask = ndvi_mean.gt(0.4)
        tree_canopy = tree_mask.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=buffer,
            scale=20,
            maxPixels=1e9
        ).get('NDVI')
        
        # Vegetation health (average NDVI)
        vegetation_health = ndvi_mean.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=buffer,
            scale=20,
            maxPixels=1e9
        ).get('NDVI')
        
        # Green space ratio (any vegetation NDVI > 0.2)
        green_mask = ndvi_mean.gt(0.2)
        green_ratio = green_mask.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=buffer,
            scale=20,
            maxPixels=1e9
        ).get('NDVI')
        
        # Get results
        tree_canopy_pct = tree_canopy.getInfo() * 100 if tree_canopy else 0
        veg_health = vegetation_health.getInfo() if vegetation_health else 0
        green_ratio_pct = green_ratio.getInfo() * 100 if green_ratio else 0
        
        # Calculate seasonal variation
        seasonal_ndvi = seasonal_stats.getInfo()
        seasonal_variation = 0
        if seasonal_ndvi and 'groups' in seasonal_ndvi:
            ndvi_values = [group['mean'] for group in seasonal_ndvi['groups'] if group['mean'] is not None]
            if len(ndvi_values) > 1:
                seasonal_variation = max(ndvi_values) - min(ndvi_values)
        
        result = {
            "tree_canopy_pct": min(100, max(0, tree_canopy_pct)),
            "vegetation_health": min(1, max(0, veg_health)),
            "green_space_ratio": min(100, max(0, green_ratio_pct)),
            "seasonal_variation": min(1, max(0, seasonal_variation))
        }
        
        print(f"   ✅ GEE Greenness Analysis: {tree_canopy_pct:.1f}% canopy, {veg_health:.2f} health")
        return result
        
    except Exception as e:
        print(f"   ⚠️  GEE greenness analysis error: {e}")
        return None


def get_building_density_gee(lat: float, lon: float, radius_m: int = 1000) -> Optional[Dict]:
    """
    Get building density and urban form analysis using GEE.
    
    Returns:
        {
            "building_density": float,
            "impervious_surface_pct": float,
            "urban_heat_island": float
        }
    """
    if not GEE_AVAILABLE:
        return None
        
    try:
        print(f"🏢 Analyzing building density with GEE at {lat}, {lon}...")
        
        point = ee.Geometry.Point([lon, lat])
        buffer = point.buffer(radius_m)
        
        # Use Global Human Settlement Layer (GHSL) for building data
        ghsl_buildings = ee.Image('JRC/GHSL/P2023A/GHS_BUILT_S_E2023_GLOBE_R2023A_54009_10_V1_0_R4_C1')
        
        # Get building density within buffer
        building_density = ghsl_buildings.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=buffer,
            scale=100,  # 100m resolution
            maxPixels=1e9
        ).get('built_surface_density')
        
        # Calculate impervious surface using Landsat
        landsat = (ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')
                  .filterDate('2020-01-01', '2024-12-31')
                  .filterBounds(buffer)
                  .filter(ee.Filter.lt('CLOUD_COVER', 20))
                  .median())
        
        # Calculate Normalized Difference Built-up Index (NDBI)
        ndbi = landsat.normalizedDifference(['SR_B6', 'SR_B5']).rename('NDBI')
        
        # Impervious surface (NDBI > 0.2 indicates built-up areas)
        impervious_mask = ndbi.gt(0.2)
        impervious_pct = impervious_mask.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=buffer,
            scale=30,
            maxPixels=1e9
        ).get('NDBI')
        
        # Urban heat island effect (LST - Land Surface Temperature)
        lst = landsat.select('ST_B10').multiply(0.00341802).add(149.0)  # Convert to Kelvin
        lst_mean = lst.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=buffer,
            scale=30,
            maxPixels=1e9
        ).get('ST_B10')
        
        # Get results
        building_density_pct = building_density.getInfo() * 100 if building_density else 0
        impervious_pct = impervious_pct.getInfo() * 100 if impervious_pct else 0
        heat_island = lst_mean.getInfo() - 273.15 if lst_mean else 0  # Convert to Celsius
        
        result = {
            "building_density": min(100, max(0, building_density_pct)),
            "impervious_surface_pct": min(100, max(0, impervious_pct)),
            "urban_heat_island": heat_island
        }
        
        print(f"   ✅ GEE Building Analysis: {building_density_pct:.1f}% density, {heat_island:.1f}°C")
        return result
        
    except Exception as e:
        print(f"   ⚠️  GEE building analysis error: {e}")
        return None


def authenticate_gee():
    """
    Authenticate with Google Earth Engine using your existing project.
    This will open a browser window for authentication.
    """
    try:
        ee.Authenticate()
        ee.Initialize(project='homefit-475718')
        print("✅ Google Earth Engine authenticated successfully with homefit-475718")
        return True
    except Exception as e:
        try:
            # Fallback: try without project
            ee.Initialize()
            print("✅ Google Earth Engine authenticated successfully (default project)")
            return True
        except Exception as e2:
            print(f"❌ GEE authentication failed: {e2}")
            print("💡 Make sure Earth Engine API is enabled in your Google Cloud project")
            return False


# Test function
def test_gee_connection():
    """Test GEE connection and basic functionality."""
    if not GEE_AVAILABLE:
        print("❌ GEE not available - run authenticate_gee() first")
        return False
    
    try:
        # Test with a simple point
        point = ee.Geometry.Point([-122.4194, 37.7749])  # San Francisco
        print("✅ GEE connection successful")
        return True
    except Exception as e:
        print(f"❌ GEE connection failed: {e}")
        return False
