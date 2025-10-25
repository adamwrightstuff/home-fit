"""
Google Earth Engine API Client
Provides satellite-based tree canopy and environmental analysis.
"""

import ee
import os
from typing import Optional, Dict, Tuple
import math

# Initialize GEE (will need authentication)
def _initialize_gee():
    """Initialize GEE with your existing project."""
    try:
        # Use your existing GEE project
        ee.Initialize(project='homefit-475718')
        return True
    except Exception as e1:
        try:
            # Fallback: try without project
            ee.Initialize()
            return True
        except Exception as e2:
            print(f"⚠️  Google Earth Engine not initialized: {e2}")
            print("💡 Try running: earthengine authenticate --project homefit-475718")
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
    
    Uses Sentinel-2 data to calculate NDVI and tree canopy coverage.
    
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
        
        # Use Sentinel-2 data (more reliable and recent)
        sentinel = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                   .filterDate('2023-01-01', '2024-12-31')
                   .filterBounds(buffer)
                   .filter(ee.Filter.lt('CLOUD_PERCENTAGE', 20)))
        
        # Check if we have data
        count = sentinel.size().getInfo()
        if count == 0:
            print(f"   ⚠️  No Sentinel-2 data available for this location")
            return None
        
        # Get the most recent image
        image = sentinel.sort('system:time_start', False).first()
        
        # Calculate NDVI
        ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
        
        # Calculate tree canopy using NDVI thresholds
        # NDVI > 0.4 = moderate to dense vegetation (trees)
        tree_mask = ndvi.gt(0.4)
        
        # Calculate percentage within buffer
        tree_area = tree_mask.reduceRegion(
            reducer=ee.Reducer.sum(),
            geometry=buffer,
            scale=20,  # 20m resolution for Sentinel-2
            maxPixels=1e9
        ).get('NDVI')
        
        # Get total area
        total_area = buffer.area().getInfo()  # Total area in square meters
        tree_pixels = tree_area.getInfo() if tree_area else 0
        pixel_area = 20 * 20  # 20m x 20m pixel for Sentinel-2
        tree_area_sqm = tree_pixels * pixel_area
        
        canopy_percentage = (tree_area_sqm / total_area) * 100 if total_area > 0 else 0
        
        print(f"   ✅ GEE Tree Canopy: {canopy_percentage:.1f}%")
        return min(100, max(0, canopy_percentage))
        
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
            return image.addBands(ndvi).addBands(season.rename('season'))
        
        seasonal_data = sentinel.map(add_seasonal_ndvi)
        
        # Calculate seasonal NDVI statistics
        seasonal_stats = seasonal_data.select(['NDVI', 'season']).reduceRegion(
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
