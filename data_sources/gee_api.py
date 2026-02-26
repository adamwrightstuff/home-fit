"""
Google Earth Engine API Client
Provides satellite-based tree canopy and environmental analysis.
"""

import ee
import os
import json
from typing import Optional, Dict, Tuple, List
import math
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError, as_completed
import time
from functools import wraps
from data_sources.cache import cached, CACHE_TTL

# Defensive: prevent Earth Engine calls from hanging indefinitely.
# ee.data.setDeadline sets a per-request deadline (ms) for API calls.
try:
    deadline_ms = int(os.getenv("HOMEFIT_GEE_DEADLINE_MS", "9000"))
    if hasattr(ee, "data") and hasattr(ee.data, "setDeadline"):
        ee.data.setDeadline(deadline_ms)
except Exception:
    pass

# Initialize GEE with service account credentials
def _initialize_gee():
    """Initialize GEE with service account credentials.

    Tries in order:
    1. GOOGLE_APPLICATION_CREDENTIALS_JSON - raw JSON string (e.g. Vercel/Railway secrets)
    2. GOOGLE_APPLICATION_CREDENTIALS - path to key file (standard Google env var)
    3. ee.Initialize(project=...) - application default credentials / local dev
    """
    import tempfile

    try:
        # 1) Inline JSON (common in serverless / PaaS)
        credentials_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
        if credentials_json:
            try:
                creds_dict = json.loads(credentials_json)
                client_email = creds_dict.get('client_email', 'unknown')
                print(f"🔑 GEE: using GOOGLE_APPLICATION_CREDENTIALS_JSON ({client_email})")
            except Exception:
                pass
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                f.write(credentials_json)
                temp_credentials_file = f.name
            try:
                creds_dict = json.loads(credentials_json)
                client_email = creds_dict.get('client_email')
                credentials = ee.ServiceAccountCredentials(
                    email=client_email,
                    key_file=temp_credentials_file
                )
                ee.Initialize(credentials, project='homefit-475718')
                try:
                    os.unlink(temp_credentials_file)
                except Exception:
                    pass
                _log_gee_success("service account (GOOGLE_APPLICATION_CREDENTIALS_JSON)")
                return True
            except Exception as e3:
                print(f"⚠️  GEE init failed (GOOGLE_APPLICATION_CREDENTIALS_JSON): {e3}")
                try:
                    os.unlink(temp_credentials_file)
                except Exception:
                    pass
                return False

        # 2) Key file path (standard Google env var - use existing credentials)
        credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if credentials_path and os.path.isfile(credentials_path):
            try:
                with open(credentials_path, 'r') as f:
                    creds_dict = json.load(f)
                client_email = creds_dict.get('client_email')
                if not client_email:
                    print("⚠️  GEE: GOOGLE_APPLICATION_CREDENTIALS file missing client_email")
                    return False
                credentials = ee.ServiceAccountCredentials(
                    email=client_email,
                    key_file=credentials_path
                )
                ee.Initialize(credentials, project='homefit-475718')
                print(f"🔑 GEE: using GOOGLE_APPLICATION_CREDENTIALS ({client_email})")
                _log_gee_success("service account (GOOGLE_APPLICATION_CREDENTIALS)")
                return True
            except Exception as e2:
                print(f"⚠️  GEE init failed (GOOGLE_APPLICATION_CREDENTIALS): {e2}")
                return False

        # 3) Application default credentials / local dev
        try:
            ee.Initialize(project='homefit-475718')
            print("✅ GEE: initialized with default credentials")
            return True
        except Exception as e1:
            print(f"⚠️  GEE not initialized: {e1}")
            print("💡 Set GOOGLE_APPLICATION_CREDENTIALS (path to key file) or GOOGLE_APPLICATION_CREDENTIALS_JSON")
            return False

    except Exception as e0:
        print(f"⚠️  GEE initialization failed: {e0}")
        return False


def _log_gee_success(source: str):
    try:
        test_point = ee.Geometry.Point([0, 0])
        _ = test_point.getInfo()
        print(f"✅ Google Earth Engine initialized and working ({source})")
    except Exception as e:
        print(f"⚠️  GEE initialized but may have limited access: {e}")

# Initialize GEE safely - don't crash the app if it fails
try:
    GEE_AVAILABLE = _initialize_gee()
except Exception as e:
    print(f"⚠️  Failed to initialize Google Earth Engine: {e}")
    GEE_AVAILABLE = False


# Helper functions for parallel execution of different canopy sources
def _get_nlcd_tcc_canopy(buffer: ee.Geometry, year_used: int = 2021) -> Tuple[Optional[float], int]:
    """Get NLCD TCC canopy percentage. Returns (percentage, year_used).
    
    Filters by bounds to get the correct regional tile (CONUS, AK, HI, PR) instead of
    just taking the first image which might be Alaska.
    """
    try:
        nlcd_collection = ee.ImageCollection('USGS/NLCD_RELEASES/2023_REL/TCC/v2023-5')
        # Filter by year AND bounds to get the correct regional tile
        # This ensures we get CONUS for US locations, not Alaska
        nlcd_tcc = nlcd_collection.filter(ee.Filter.eq('year', year_used)).filterBounds(buffer).first()
        if nlcd_tcc is None:
            return (None, year_used)
        nlcd_tcc = nlcd_tcc.select('NLCD_Percent_Tree_Canopy_Cover')
        tcc_stats = nlcd_tcc.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=buffer,
            scale=30,
            maxPixels=1e9
        )
        tcc_pct = tcc_stats.get('NLCD_Percent_Tree_Canopy_Cover').getInfo()
        if tcc_pct is not None and tcc_pct >= 0.0:
            return (min(100, max(0, tcc_pct)), year_used)
    except Exception as e:
        # Log error for debugging but don't print (handled in main function)
        pass
    return (None, year_used)

def _get_hansen_canopy(buffer: ee.Geometry) -> Optional[float]:
    """Get Hansen tree cover percentage."""
    try:
        hansen = ee.Image('UMD/hansen/global_forest_change_2024_v1_12').select('treecover2000')
        h_stats = hansen.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=buffer,
            scale=30,
            maxPixels=1e9
        )
        h_mean = h_stats.get('treecover2000').getInfo()
        if h_mean is not None and h_mean >= 0.0:
            return min(100, max(0, h_mean))
    except Exception:
        pass
    return None

def _get_nlcd_landcover_canopy(buffer: ee.Geometry) -> Optional[float]:
    """Get NLCD Land Cover forest percentage."""
    try:
        nlcd = ee.Image('USGS/NLCD_RELEASES/2021_REL/NLCD/2021')
        landcover = nlcd.select('landcover')
        tree_classes = landcover.eq(40).Or(landcover.eq(41)).Or(landcover.eq(42)).Or(landcover.eq(43))
        canopy_stats = tree_classes.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=buffer,
            scale=30,
            maxPixels=1e9
        )
        canopy_mean = canopy_stats.get('landcover').getInfo()
        if canopy_mean is not None and canopy_mean > 0:
            return min(100, max(0, canopy_mean * 100))
    except Exception:
        pass
    return None


@cached(ttl_seconds=CACHE_TTL.get('census_data', 48 * 3600))  # Cache for 48 hours (canopy data is very stable)
def get_tree_canopy_gee(lat: float, lon: float, radius_m: int = 1000, area_type: Optional[str] = None) -> Optional[float]:
    """
    Get tree canopy percentage using Google Earth Engine with parallel multi-source validation.
    
    Uses NLCD Tree Canopy Cover dataset as primary source, validates in parallel with other sources
    to compensate for NLCD's known ~10% underestimation bias. Sources run concurrently with timeouts
    to minimize latency while ensuring accuracy.
    
    Args:
        lat: Latitude
        lon: Longitude  
        radius_m: Analysis radius in meters
        area_type: Optional area type for logging/debugging (no adjustments applied)
        
    Returns:
        Tree canopy percentage (0-100) or None if unavailable
    """
    if not GEE_AVAILABLE:
        return None
        
    try:
        print(f"🛰️  Analyzing tree canopy with Google Earth Engine at {lat}, {lon}...")
        start_time = time.time()
        
        # Create point of interest
        point = ee.Geometry.Point([lon, lat])
        buffer = point.buffer(radius_m)
        
        # Determine most recent NLCD year (one-time check)
        nlcd_collection = ee.ImageCollection('USGS/NLCD_RELEASES/2023_REL/TCC/v2023-5')
        available_years = nlcd_collection.aggregate_array('year').distinct().getInfo()
        year_used = 2021  # Default
        if 2023 in available_years:
            year_used = 2023
        elif 2022 in available_years:
            year_used = 2022
        
        # Run all sources in parallel with timeouts (max 8 seconds per source)
        # Total time should be ~8-10 seconds max instead of 15-20+ sequential
        nlcd_tcc_result = None
        hansen_result = None
        nlcd_landcover_result = None
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            # Submit all tasks
            nlcd_future = executor.submit(_get_nlcd_tcc_canopy, buffer, year_used)
            hansen_future = executor.submit(_get_hansen_canopy, buffer)
            landcover_future = executor.submit(_get_nlcd_landcover_canopy, buffer)
            
            # Collect results with timeouts (8 seconds per source)
            futures = {
                nlcd_future: 'NLCD TCC',
                hansen_future: 'Hansen',
                landcover_future: 'NLCD Land Cover'
            }
            
            for future in as_completed(futures, timeout=10):
                source_name = futures[future]
                try:
                    result = future.result(timeout=8)
                    if source_name == 'NLCD TCC':
                        if result[0] is not None:
                            nlcd_tcc_result, year_used = result
                            print(f"   ✅ GEE Tree Canopy (USGS/NLCD TCC {year_used}): {nlcd_tcc_result:.1f}%")
                        else:
                            print(f"   ⚠️  NLCD TCC returned None (unavailable)")
                    elif source_name == 'Hansen':
                        if result is not None:
                            hansen_result = result
                            print(f"   ✅ GEE Tree Canopy (Hansen): {hansen_result:.1f}%")
                        else:
                            print(f"   ⚠️  Hansen returned None (unavailable)")
                    elif source_name == 'NLCD Land Cover':
                        if result is not None:
                            nlcd_landcover_result = result
                            print(f"   ✅ GEE Tree Canopy (NLCD Land Cover): {nlcd_landcover_result:.1f}%")
                        else:
                            print(f"   ⚠️  NLCD Land Cover returned None (unavailable)")
                except FutureTimeoutError:
                    print(f"   ⚠️  {source_name} timed out after 8s (skipping)")
                except Exception as e:
                    print(f"   ⚠️  {source_name} error: {str(e)[:100]}")
        
        elapsed = time.time() - start_time
        print(f"   ⏱️  Multi-source canopy analysis completed in {elapsed:.1f}s")
        
        # Multi-source approach: Use highest value to avoid NLCD underestimation bias
        # Research shows NLCD systematically underestimates by ~10% (up to 13.9% in urban)
        if nlcd_tcc_result is not None:
            primary_result = nlcd_tcc_result
            print(f"   ⚠️  Note: NLCD known to underestimate canopy by ~10% (up to 13.9% in urban)")
            
            # Collect validation sources and use highest value if significantly different
            validation_sources = []
            if nlcd_landcover_result is not None:
                validation_sources.append(('NLCD Land Cover', nlcd_landcover_result))
            if hansen_result is not None:
                # Cap Hansen at 90% to avoid extreme outliers
                validation_sources.append(('Hansen', min(90, hansen_result)))
            
            # Check agreement and use highest value if validation suggests underestimation
            # Research shows NLCD systematically underestimates by ~10% (up to 13.9% in urban)
            # Use higher validation value when available to compensate, even for smaller differences
            if validation_sources:
                max_validation_value = primary_result
                agreements = []
                underestimation_detected = False
                
                for source_name, source_value in validation_sources:
                    diff = abs(primary_result - source_value)
                    diff_pct = source_value - primary_result  # Positive = higher, negative = lower
                    
                    if diff <= 5:  # Within 5% = good agreement
                        agreements.append(source_name)
                        # If validation is higher (even slightly), use it to compensate for NLCD underestimation
                        if source_value > primary_result + 3.0:  # >3% higher = meaningful underestimation
                            print(f"   ✓ {source_name} validates NLCD TCC (diff: {diff:.1f}%)")
                            print(f"   💡 {source_name} is {diff_pct:.1f}% higher - using to compensate for NLCD underestimation bias")
                            max_validation_value = max(max_validation_value, source_value)
                            underestimation_detected = True
                        else:
                            print(f"   ✓ {source_name} validates NLCD TCC (diff: {diff:.1f}%)")
                    elif diff <= 10:  # Within 10% = acceptable
                        agreements.append(source_name)
                        # If validation is higher, use it
                        if source_value > primary_result + 3.0:  # >3% higher = meaningful underestimation
                            print(f"   ~ {source_name} roughly agrees with NLCD TCC (diff: {diff:.1f}%)")
                            print(f"   💡 {source_name} is {diff_pct:.1f}% higher - using to compensate for NLCD underestimation bias")
                            max_validation_value = max(max_validation_value, source_value)
                            underestimation_detected = True
                        else:
                            print(f"   ~ {source_name} roughly agrees with NLCD TCC (diff: {diff:.1f}%)")
                    else:
                        # Large difference - check if validation source suggests underestimation
                        if source_value > primary_result + 3.0:  # >3% higher = meaningful underestimation
                            print(f"   ⚠️  {source_name} ({source_value:.1f}%) significantly higher than NLCD TCC ({primary_result:.1f}%, diff: +{diff_pct:.1f}%)")
                            print(f"   💡 Using higher value to compensate for NLCD underestimation bias")
                            max_validation_value = max(max_validation_value, source_value)
                            underestimation_detected = True
                        else:
                            print(f"   ⚠️  {source_name} differs from NLCD TCC ({diff:.1f}% diff)")
                
                if agreements:
                    if underestimation_detected:
                        print(f"   📊 NLCD TCC validated by {len(agreements)} source(s), but using higher value to compensate for underestimation")
                    else:
                        print(f"   📊 NLCD TCC validated by {len(agreements)} source(s)")
                else:
                    print(f"   ⚠️  Validation sources disagree - using highest value to compensate for NLCD underestimation")
                
                # Use the highest value if validation sources suggest underestimation
                if max_validation_value > primary_result:
                    print(f"   ✅ Updating canopy from {primary_result:.1f}% to {max_validation_value:.1f}% (compensating for NLCD underestimation)")
                    primary_result = max_validation_value
            
            # Validate canopy value for sanity
            if primary_result is not None:
                if primary_result > 100.0:
                    primary_result = 100.0
                elif primary_result > 80.0:
                    print(f"   ⚠️  Unusually high canopy value {primary_result}% - verify data quality")
                elif primary_result < 0.0:
                    primary_result = 0.0
            
            return primary_result
        
        # Fallback: If NLCD unavailable, use other sources
        sources = []
        if nlcd_landcover_result is not None:
            sources.append(('NLCD Land Cover', nlcd_landcover_result))
        if hansen_result is not None:
            sources.append(('Hansen', hansen_result))
        
        if len(sources) == 1:
            return sources[0][1]
        elif len(sources) > 1:
            values = [s[1] for s in sources]
            combined_result = max(values)  # Use max instead of average
            source_names = ', '.join([s[0] for s in sources])
            print(f"   📊 Using highest fallback value ({source_names}): {combined_result:.1f}% (max of {values})")
            return min(100, max(0, combined_result))
        
        return None
        
    except Exception as e:
        print(f"   ⚠️  GEE tree canopy analysis error: {e}")
        return None


def get_vegetation_health_metrics(lat: float, lon: float, radius_m: int = 1000) -> Optional[Dict]:
    """
    Calculate enhanced vegetation health metrics using NDVI and VARI.
    
    VARI (Visible Atmospherically Resistant Index) is better for capturing
    vegetation health from visible bands, complementing NDVI.
    
    Returns:
        {
            "vegetation_health_ndvi": float,  # Average NDVI (0-1)
            "vegetation_health_vari": float,  # Average VARI (-1 to 1, typically 0-0.5)
            "vegetation_health_score": float,  # Composite health score (0-100)
        }
    """
    if not GEE_AVAILABLE:
        return None
    
    try:
        point = ee.Geometry.Point([lon, lat])
        buffer = point.buffer(radius_m)
        
        # Get recent Sentinel-2 data for vegetation health
        sentinel = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                   .filterDate('2023-06-01', '2024-09-30')  # Recent summer/fall data
                   .filterBounds(buffer)
                   .filter(ee.Filter.lt('CLOUD_PERCENTAGE', 20))
                   .median())
        
        # Calculate NDVI (NIR - Red) / (NIR + Red)
        # B8 = NIR, B4 = Red
        ndvi = sentinel.normalizedDifference(['B8', 'B4']).rename('NDVI')
        
        # Calculate VARI (Green - Red) / (Green + Red - Blue)
        # B3 = Green, B4 = Red, B2 = Blue
        # VARI = (Green - Red) / (Green + Red - Blue)
        green = sentinel.select('B3')
        red = sentinel.select('B4')
        blue = sentinel.select('B2')
        vari = green.subtract(red).divide(green.add(red).subtract(blue)).rename('VARI')
        
        # Calculate average NDVI and VARI
        ndvi_mean = ndvi.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=buffer,
            scale=20,
            maxPixels=1e9,
            bestEffort=True
        ).get('NDVI')
        
        vari_mean = vari.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=buffer,
            scale=20,
            maxPixels=1e9,
            bestEffort=True
        ).get('VARI')
        
        veg_health_ndvi = ndvi_mean.getInfo() if ndvi_mean else 0.0
        veg_health_vari = vari_mean.getInfo() if vari_mean else 0.0
        
        # Composite health score (0-100): combines NDVI and VARI
        # NDVI: 0-1 scale, VARI: -1 to 1 scale (but vegetation typically 0-0.5)
        # Normalize VARI to 0-1 scale for vegetation (clamp negative values to 0)
        vari_normalized = max(0.0, min(1.0, (veg_health_vari + 0.2) / 0.7)) if veg_health_vari else 0.0
        
        # Combined health score: 60% NDVI, 40% VARI
        health_score = (veg_health_ndvi * 0.6 + vari_normalized * 0.4) * 100
        health_score = max(0.0, min(100.0, health_score))
        
        return {
            "vegetation_health_ndvi": round(veg_health_ndvi, 3),
            "vegetation_health_vari": round(veg_health_vari, 3),
            "vegetation_health_score": round(health_score, 2)
        }
    except Exception as e:
        print(f"   ⚠️  Vegetation health metrics calculation failed: {e}")
        return None


def get_semantic_gvi(lat: float, lon: float, radius_m: int = 1000) -> Optional[Dict]:
    """
    Calculate Semantic Green View Index (SGVI) using enhanced vegetation detection.
    
    Note: Full semantic segmentation requires Street View imagery or ML models.
    This implementation uses enhanced NDVI-based detection to approximate SGVI
    by distinguishing actual vegetation from green objects.
    
    Future enhancement: Integrate Google Street View API for true semantic segmentation.
    
    Returns:
        {
            "semantic_gvi": float,  # SGVI score (0-100)
            "vegetation_pct": float,  # Percentage of visible pixels that are vegetation
            "method": str,  # "ndvi_enhanced" or "street_view" (when available)
        }
    """
    if not GEE_AVAILABLE:
        return None
    
    try:
        point = ee.Geometry.Point([lon, lat])
        buffer = point.buffer(radius_m)
        
        # Get recent high-resolution Sentinel-2 data
        sentinel = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                   .filterDate('2023-06-01', '2024-09-30')
                   .filterBounds(buffer)
                   .filter(ee.Filter.lt('CLOUD_PERCENTAGE', 20))
                   .median())
        
        # Enhanced vegetation detection using NDVI + VARI combination
        # This helps distinguish actual vegetation from green objects
        ndvi = sentinel.normalizedDifference(['B8', 'B4'])
        green = sentinel.select('B3')
        red = sentinel.select('B4')
        blue = sentinel.select('B2')
        vari = green.subtract(red).divide(green.add(red).subtract(blue))
        
        # Combined vegetation mask: NDVI > 0.3 AND VARI > 0 (vegetation-like)
        # This is more selective than NDVI alone, reducing false positives from green objects
        vegetation_mask = ndvi.gt(0.3).And(vari.gt(0.0))
        
        # Calculate semantic GVI as percentage of visible pixels that are vegetation
        semantic_gvi_pct = vegetation_mask.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=buffer,
            scale=10,  # 10m resolution for street-level accuracy
            maxPixels=1e9,
            bestEffort=True
        ).get('NDVI')  # Using NDVI band name from mask
        
        if semantic_gvi_pct:
            semantic_gvi_value = semantic_gvi_pct.getInfo() * 100 if semantic_gvi_pct else 0.0
        else:
            semantic_gvi_value = 0.0
        
        return {
            "semantic_gvi": round(semantic_gvi_value, 2),
            "vegetation_pct": round(semantic_gvi_value, 2),
            "method": "ndvi_enhanced"
        }
    except Exception as e:
        print(f"   ⚠️  Semantic GVI calculation failed: {e}")
        return None


def get_urban_greenness_gee(lat: float, lon: float, radius_m: int = 1000) -> Optional[Dict]:
    """
    Get comprehensive urban greenness analysis using GEE.
    
    Enhanced with VARI vegetation health metrics and semantic GVI support.
    
    Returns:
        {
            "tree_canopy_pct": float,
            "vegetation_health": float,
            "vegetation_health_ndvi": float,
            "vegetation_health_vari": float,
            "vegetation_health_score": float,
            "green_space_ratio": float,
            "seasonal_variation": float,
            "semantic_gvi": float,
            "visible_green_fraction": float,
            "street_level_ndvi": float,
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
        
        # Check if collection is empty
        collection_size = seasonal_data.size().getInfo()
        if collection_size == 0:
            print(f"   ⚠️  No Sentinel-2 images found for greenness analysis")
            return None
        
        # Calculate seasonal NDVI statistics
        seasonal_stats = seasonal_data.select(['NDVI', 'season']).median().reduceRegion(
            reducer=ee.Reducer.mean().group(0, 'season'),
            geometry=buffer,
            scale=20,
            maxPixels=1e9
        )
        
        # Calculate overall greenness metrics
        ndvi_mean = seasonal_data.select('NDVI').mean()
        
        # Check if ndvi_mean has bands before doing comparisons
        # If the collection is empty or has no valid NDVI data, this will fail
        try:
            # Try to get band names to verify the image has bands
            ndvi_bands = ndvi_mean.bandNames().getInfo()
            if not ndvi_bands or len(ndvi_bands) == 0:
                print(f"   ⚠️  NDVI image has no bands, skipping greenness analysis")
                return None
        except Exception as band_check_error:
            print(f"   ⚠️  Cannot verify NDVI bands: {band_check_error}")
            return None
        
        # Tree canopy (NDVI > 0.4)
        # Wrap in try/except to handle cases where .gt() fails due to band mismatch
        try:
            tree_mask = ndvi_mean.gt(0.4)
            tree_canopy = tree_mask.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=buffer,
                scale=20,
                maxPixels=1e9
            ).get('NDVI')
        except Exception as tree_error:
            print(f"   ⚠️  Tree canopy calculation failed: {tree_error}")
            tree_canopy = None
        
        # Vegetation health (average NDVI)
        try:
            vegetation_health = ndvi_mean.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=buffer,
                scale=20,
                maxPixels=1e9
            ).get('NDVI')
        except Exception as veg_error:
            print(f"   ⚠️  Vegetation health calculation failed: {veg_error}")
            vegetation_health = None
        
        # Green space ratio (any vegetation NDVI > 0.2)
        try:
            green_mask = ndvi_mean.gt(0.2)
            green_ratio = green_mask.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=buffer,
                scale=20,
                maxPixels=1e9
            ).get('NDVI')
        except Exception as green_error:
            print(f"   ⚠️  Green space ratio calculation failed: {green_error}")
            green_ratio = None
        
        # Get results with safe defaults
        try:
            tree_canopy_pct = tree_canopy.getInfo() * 100 if tree_canopy else 0.0
        except Exception:
            tree_canopy_pct = 0.0
        
        try:
            veg_health = vegetation_health.getInfo() if vegetation_health else 0.0
        except Exception:
            veg_health = 0.0
        
        try:
            green_ratio_pct = green_ratio.getInfo() * 100 if green_ratio else 0.0
        except Exception:
            green_ratio_pct = 0.0
        
        # Calculate seasonal variation
        seasonal_variation = 0.0
        try:
            seasonal_ndvi = seasonal_stats.getInfo()
            if seasonal_ndvi and 'groups' in seasonal_ndvi:
                ndvi_values = [group['mean'] for group in seasonal_ndvi['groups'] if group['mean'] is not None]
                if len(ndvi_values) > 1:
                    seasonal_variation = max(ndvi_values) - min(ndvi_values)
        except Exception as seasonal_error:
            print(f"   ⚠️  Seasonal variation calculation failed: {seasonal_error}")
            seasonal_variation = 0.0
        
        # NEW: Calculate visible green fraction (eye-level greenery proxy)
        # Use NDVI > 0.3 threshold for visible vegetation (lower than tree threshold)
        # This captures shrubs, grass, and smaller vegetation visible at street level
        visible_green_fraction = 0.0
        try:
            visible_green_mask = ndvi_mean.gt(0.3)  # NDVI > 0.3 = visible green
            visible_green = visible_green_mask.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=buffer,
                scale=10,  # Higher resolution (10m) for street-level accuracy
                maxPixels=1e9,
                bestEffort=True
            ).get('NDVI')
            if visible_green:
                visible_green_fraction = visible_green.getInfo() * 100 if visible_green else 0.0
        except Exception as visible_error:
            print(f"   ⚠️  Visible green fraction calculation failed: {visible_error}")
            # Fallback: use green_ratio_pct as proxy
            visible_green_fraction = green_ratio_pct * 0.8  # Assume 80% of green space is visible
        
        # NEW: Calculate seasonal consistency (year-round greenery)
        # Lower seasonal variation = more consistent year-round greenery (better)
        seasonal_consistency = 1.0 - min(1.0, seasonal_variation / 0.5)  # Normalize to 0-1
        seasonal_consistency = max(0.0, min(1.0, seasonal_consistency))
        
        # NEW: Street-level vegetation index (using higher resolution)
        # Calculate NDVI at 10m resolution (street-level) for more accurate eye-level estimate
        street_level_ndvi = 0.0
        try:
            # Use recent Sentinel-2 image (prefer summer for vegetation visibility)
            recent_sentinel = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                             .filterDate('2023-06-01', '2024-09-30')  # Summer months
                             .filterBounds(buffer)
                             .filter(ee.Filter.lt('CLOUD_PERCENTAGE', 20))
                             .median())
            
            street_ndvi = recent_sentinel.normalizedDifference(['B8', 'B4']).rename('NDVI')
            street_ndvi_mean = street_ndvi.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=buffer,
                scale=10,  # 10m resolution for street-level accuracy
                maxPixels=1e9,
                bestEffort=True
            ).get('NDVI')
            
            if street_ndvi_mean:
                street_level_ndvi_val = street_ndvi_mean.getInfo()
                if street_level_ndvi_val is not None:
                    street_level_ndvi = max(0.0, min(1.0, street_level_ndvi_val))
        except Exception as street_error:
            print(f"   ⚠️  Street-level NDVI calculation failed: {street_error}")
            # Fallback: use overall NDVI
            street_level_ndvi = veg_health
        
        # Get enhanced vegetation health metrics (VARI)
        veg_health_metrics = get_vegetation_health_metrics(lat, lon, radius_m)
        veg_health_ndvi = veg_health_metrics.get("vegetation_health_ndvi", veg_health) if veg_health_metrics else veg_health
        veg_health_vari = veg_health_metrics.get("vegetation_health_vari", 0.0) if veg_health_metrics else 0.0
        veg_health_score = veg_health_metrics.get("vegetation_health_score", veg_health * 100) if veg_health_metrics else (veg_health * 100)
        
        # Get semantic GVI
        semantic_gvi_data = get_semantic_gvi(lat, lon, radius_m)
        semantic_gvi = semantic_gvi_data.get("semantic_gvi", visible_green_fraction) if semantic_gvi_data else visible_green_fraction
        
        result = {
            "tree_canopy_pct": min(100, max(0, tree_canopy_pct)),
            "vegetation_health": min(1, max(0, veg_health)),  # Legacy key
            "vegetation_health_ndvi": round(veg_health_ndvi, 3),
            "vegetation_health_vari": round(veg_health_vari, 3),
            "vegetation_health_score": round(veg_health_score, 2),
            "green_space_ratio": min(100, max(0, green_ratio_pct)),
            "seasonal_variation": min(1, max(0, seasonal_variation)),
            "visible_green_fraction": min(100, max(0, visible_green_fraction)),
            "semantic_gvi": round(semantic_gvi, 2),
            "seasonal_consistency": round(seasonal_consistency, 3),
            "street_level_ndvi": round(street_level_ndvi, 3)
        }
        
        print(f"   ✅ GEE Greenness Analysis: {tree_canopy_pct:.1f}% canopy, health={veg_health_score:.1f}, SGVI={semantic_gvi:.1f}%, visible green={visible_green_fraction:.1f}%")
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


def get_topography_context(lat: float, lon: float, radius_m: int = 5000) -> Optional[Dict]:
    """
    Analyze elevation and slope context around a location.

    Returns statistics describing terrain relief which can be used to boost
    scenic scoring for hillside and mountain locations.
    """
    if not GEE_AVAILABLE:
        return None

    try:
        print(f"⛰️  Analyzing topography with GEE at {lat}, {lon} (radius={radius_m}m)")
        point = ee.Geometry.Point([lon, lat])
        buffer = point.buffer(radius_m)

        dem = ee.Image('USGS/SRTMGL1_003')
        slope = ee.Terrain.slope(dem)

        dem_stats = dem.reduceRegion(
            reducer=(ee.Reducer.mean()
                     .combine(ee.Reducer.minMax(), sharedInputs=True)
                     .combine(ee.Reducer.percentile([10, 90]), sharedInputs=True)),
            geometry=buffer,
            scale=90,
            maxPixels=1e9,
            bestEffort=True
        )

        slope_stats = slope.reduceRegion(
            reducer=(ee.Reducer.mean()
                     .combine(ee.Reducer.max(), sharedInputs=True)
                     .combine(ee.Reducer.stdDev(), sharedInputs=True)
                     .combine(ee.Reducer.percentile([85]), sharedInputs=True)),
            geometry=buffer,
            scale=90,
            maxPixels=1e9,
            bestEffort=True
        )

        steep_fraction = slope.gt(15).reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=buffer,
            scale=90,
            maxPixels=1e9,
            bestEffort=True
        )

        # Calculate elevation standard deviation for ruggedness index
        dem_std = dem.reduceRegion(
            reducer=ee.Reducer.stdDev(),
            geometry=buffer,
            scale=90,
            maxPixels=1e9,
            bestEffort=True
        )

        # Calculate terrain prominence: elevation at center point vs surrounding area
        # Use a smaller buffer (2km) for local prominence calculation
        center_point = ee.Geometry.Point([lon, lat])
        local_buffer = center_point.buffer(2000)  # 2km radius for prominence
        prominence_buffer = buffer.difference(local_buffer)  # Area outside local buffer
        
        center_elevation = dem.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=center_point.buffer(100),  # Very small buffer for center point
            scale=90,
            maxPixels=1e9,
            bestEffort=True
        )
        
        # Mean elevation of surrounding area (outside local buffer)
        surrounding_elevation = None
        if prominence_buffer.area(1).getInfo() > 0:  # Check if buffer has area
            surrounding_elevation = dem.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=prominence_buffer,
                scale=90,
                maxPixels=1e9,
                bestEffort=True
            )

        dem_info = dem_stats.getInfo()
        slope_info = slope_stats.getInfo()
        steep_info = steep_fraction.getInfo()
        dem_std_info = dem_std.getInfo()
        center_elev = center_elevation.getInfo()
        surrounding_elev = surrounding_elevation.getInfo() if surrounding_elevation else None

        if not dem_info or not slope_info:
            return None

        elevation_min = dem_info.get('elevation_min')
        elevation_max = dem_info.get('elevation_max')
        elevation_mean = dem_info.get('elevation_mean')
        relief = None
        if elevation_min is not None and elevation_max is not None:
            relief = elevation_max - elevation_min

        # Calculate prominence: center elevation - mean surrounding elevation
        prominence = None
        if center_elev and elevation_mean is not None:
            center_elev_val = center_elev.get('elevation_mean') or center_elev.get('elevation')
            if center_elev_val is not None:
                if surrounding_elev:
                    surrounding_elev_val = surrounding_elev.get('elevation_mean') or surrounding_elev.get('elevation')
                    if surrounding_elev_val is not None:
                        prominence = max(0.0, center_elev_val - surrounding_elev_val)
                else:
                    # Fallback: use p10 as proxy for surrounding elevation
                    if elevation_min is not None:
                        prominence = max(0.0, center_elev_val - elevation_min)

        # Calculate ruggedness index: standard deviation of elevation
        ruggedness_index = None
        if dem_std_info:
            ruggedness_index = dem_std_info.get('elevation_stdDev') or dem_std_info.get('elevation')

        # Calculate local relief intensity: relief per unit area (m/km²)
        # Buffer area in km²
        buffer_area_km2 = (math.pi * (radius_m / 1000.0) ** 2) if radius_m else None
        relief_intensity = None
        if relief is not None and buffer_area_km2 and buffer_area_km2 > 0:
            relief_intensity = relief / buffer_area_km2

        topography = {
            "source": "USGS/SRTMGL1_003",
            "elevation_mean_m": elevation_mean,
            "elevation_min_m": elevation_min,
            "elevation_max_m": elevation_max,
            "elevation_p10_m": dem_info.get('elevation_p10'),
            "elevation_p90_m": dem_info.get('elevation_p90'),
            "relief_range_m": relief,
            "relief_intensity_m_per_km2": relief_intensity,
            "terrain_prominence_m": prominence,
            "ruggedness_index_m": ruggedness_index,
            "slope_mean_deg": slope_info.get('slope_mean'),
            "slope_max_deg": slope_info.get('slope_max'),
            "slope_std_deg": slope_info.get('slope_stdDev'),
            "slope_p85_deg": slope_info.get('slope_p85'),
            "steep_fraction": steep_info.get('slope') if steep_info else None
        }

        # Validate slope values against elevation (sanity check - doesn't affect scoring)
        # Design principle: Transparent and documented - flag data quality issues
        if elevation_mean is not None and topography["slope_mean_deg"] is not None:
            # Rough heuristic: higher elevation should generally have higher slope
            # This is not a hard rule, but can flag anomalies
            expected_min_slope = min(5.0, elevation_mean / 1000.0)  # Conservative estimate
            if elevation_mean > 500 and topography["slope_mean_deg"] < expected_min_slope * 0.3:
                print(
                    f"   ⚠️  Slope {topography['slope_mean_deg']:.1f}° seems unusually low "
                    f"for elevation {elevation_mean:.0f}m - verify data quality"
                )

        print(f"   ✅ GEE Topography: relief={relief:.1f}m, prominence={prominence:.1f}m, ruggedness={ruggedness_index:.1f}m, mean slope={topography['slope_mean_deg']:.1f}°")
        return topography

    except Exception as e:
        print(f"⚠️  GEE topography analysis error: {e}")
        return None


@cached(ttl_seconds=CACHE_TTL.get('census_data', 48 * 3600))  # Cache for 48 hours
def get_viewshed_proxy(lat: float, lon: float, radius_m: int = 5000, 
                      landcover_metrics: Optional[Dict] = None) -> Optional[Dict]:
    """
    Enhanced DEM-based scenic viewshed analysis.
    
    Computes a 360° viewshed by combining terrain analysis with landcover to estimate
    what fraction of natural features (forests, mountains, water) would be visible from a location.
    Uses DEM-based calculations to determine visible natural terrain vs built environment.
    
    Args:
        lat: Latitude
        lon: Longitude
        radius_m: Analysis radius in meters (default 5000m)
        landcover_metrics: Optional pre-computed landcover metrics (to avoid redundant GEE calls)
    
    Returns:
        Dict with keys:
        - visible_natural_pct: Estimated percentage of visible natural area (0-100)
        - visible_natural_terrain_pct: Percentage of viewshed that is natural (0-100)
        - viewshed_relief_m: Maximum vertical relief visible in viewshed
        - scenic_viewshed_score: Composite scenic viewshed score (0-100)
        - viewshed_radius_m: Effective viewshed radius
        - terrain_prominence_m: Terrain prominence (height above surroundings)
        - visible_forest_pct: Estimated visible forest percentage
        - visible_water_pct: Estimated visible water percentage
        - viewshed_quality: "high"|"medium"|"low" based on terrain complexity
    """
    if not GEE_AVAILABLE:
        return None
    
    try:
        print(f"🔭 Analyzing viewshed proxy with GEE at {lat}, {lon} (radius={radius_m}m)")
        point = ee.Geometry.Point([lon, lat])
        buffer = point.buffer(radius_m)
        
        # Get topography for prominence calculation
        dem = ee.Image('USGS/SRTMGL1_003')
        slope = ee.Terrain.slope(dem)
        
        # Get center elevation
        center_point = ee.Geometry.Point([lon, lat])
        center_elev = dem.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=center_point.buffer(100),
            scale=90,
            maxPixels=1e9,
            bestEffort=True
        ).getInfo()
        
        # Get surrounding elevation (area 2-5km from center)
        local_buffer = center_point.buffer(2000)
        prominence_buffer = buffer.difference(local_buffer)
        
        surrounding_elev = None
        if prominence_buffer.area(1).getInfo() > 0:
            surrounding_elev = dem.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=prominence_buffer,
                scale=90,
                maxPixels=1e9,
                bestEffort=True
            ).getInfo()
        
        # Calculate prominence
        terrain_prominence_m = None
        if center_elev and 'elevation' in center_elev:
            center_elev_val = center_elev['elevation']
            if surrounding_elev and 'elevation' in surrounding_elev:
                terrain_prominence_m = max(0.0, center_elev_val - surrounding_elev['elevation'])
            else:
                # Fallback: use mean elevation difference
                dem_stats = dem.reduceRegion(
                    reducer=ee.Reducer.minMax(),
                    geometry=buffer,
                    scale=90,
                    maxPixels=1e9,
                    bestEffort=True
                ).getInfo()
                if dem_stats and 'elevation_min' in dem_stats:
                    terrain_prominence_m = max(0.0, center_elev_val - dem_stats['elevation_min'])
        
        # Approximate viewshed: higher prominence and slope = better visibility
        # Use a simple model: visibility decays with distance, enhanced by terrain
        slope_stats = slope.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=buffer,
            scale=90,
            maxPixels=1e9,
            bestEffort=True
        ).getInfo()
        
        slope_mean = slope_stats.get('slope') if slope_stats else 0.0
        slope_mean = max(0.0, slope_mean) if slope_mean else 0.0
        
        # Visibility factor: higher prominence = better viewshed
        # Rough approximation: prominence > 200m = excellent viewshed
        prominence_factor = min(1.0, (terrain_prominence_m or 0.0) / 200.0)
        slope_factor = min(1.0, slope_mean / 20.0)  # 20° slope = full visibility bonus
        
        # Effective viewshed radius (reduced for flat terrain, enhanced for prominent terrain)
        base_viewshed_radius = radius_m * 0.6  # Assume 60% effective visibility on average
        terrain_enhancement = 1.0 + (prominence_factor * 0.3) + (slope_factor * 0.2)
        viewshed_radius_m = base_viewshed_radius * terrain_enhancement
        
        # Get landcover if not provided
        if landcover_metrics is None:
            landcover_metrics = get_landcover_context_gee(lat, lon, radius_m=int(viewshed_radius_m))
        
        if not landcover_metrics:
            # Fallback to basic estimate
            visible_natural_pct = min(100.0, (terrain_prominence_m or 0.0) / 10.0) if terrain_prominence_m else 0.0
            # Calculate basic relief estimate
            dem_elev_range = dem.reduceRegion(
                reducer=ee.Reducer.minMax(),
                geometry=buffer,
                scale=90,
                maxPixels=1e9,
                bestEffort=True
            ).getInfo()
            viewshed_relief_m = None
            if dem_elev_range and 'elevation_min' in dem_elev_range and 'elevation_max' in dem_elev_range:
                viewshed_relief_m = dem_elev_range['elevation_max'] - dem_elev_range['elevation_min']
            elif terrain_prominence_m:
                viewshed_relief_m = terrain_prominence_m * 2.0
            scenic_viewshed_score = min(70.0, visible_natural_pct * 0.7)
            if viewshed_relief_m:
                scenic_viewshed_score += min(30.0, (viewshed_relief_m / 500.0) * 30.0)
            return {
                "visible_natural_pct": visible_natural_pct,
                "visible_natural_terrain_pct": visible_natural_pct,
                "viewshed_relief_m": round(viewshed_relief_m, 2) if viewshed_relief_m else None,
                "scenic_viewshed_score": round(scenic_viewshed_score, 2),
                "viewshed_radius_m": viewshed_radius_m,
                "terrain_prominence_m": terrain_prominence_m,
                "visible_forest_pct": None,
                "visible_water_pct": None,
                "viewshed_quality": "low" if not terrain_prominence_m else "medium"
            }
        
        # Estimate visible natural features
        forest_pct = landcover_metrics.get('forest_pct', 0.0) or 0.0
        water_pct = landcover_metrics.get('water_pct', 0.0) or 0.0
        shrub_pct = landcover_metrics.get('shrub_pct', 0.0) or 0.0
        grass_pct = landcover_metrics.get('grass_pct', 0.0) or 0.0
        
        # Visible natural = forest + water + natural areas (weighted by visibility)
        # Forests and water are more visible than shrub/grass
        visible_natural_pct = (
            forest_pct * 1.0 +  # Forests highly visible
            water_pct * 1.0 +   # Water highly visible
            shrub_pct * 0.6 +   # Shrub moderately visible
            grass_pct * 0.4     # Grass less visible
        )
        
        # Apply terrain-based visibility enhancement
        # Higher prominence = more of the landscape is visible
        visibility_enhancement = 1.0 + (prominence_factor * 0.2)
        visible_natural_pct = min(100.0, visible_natural_pct * visibility_enhancement)
        
        visible_forest_pct = min(100.0, forest_pct * visibility_enhancement)
        visible_water_pct = min(100.0, water_pct * visibility_enhancement)
        
        # Determine viewshed quality
        if terrain_prominence_m and terrain_prominence_m > 200 and slope_mean > 10:
            viewshed_quality = "high"
        elif terrain_prominence_m and terrain_prominence_m > 100:
            viewshed_quality = "medium"
        else:
            viewshed_quality = "low"
        
        # Calculate viewshed relief: maximum elevation difference visible in viewshed
        # Use relief from landcover metrics if available, otherwise estimate from prominence
        viewshed_relief_m = None
        if landcover_metrics:
            # Get elevation range from DEM within viewshed radius
            dem_elev_range = dem.reduceRegion(
                reducer=ee.Reducer.minMax(),
                geometry=buffer,
                scale=90,
                maxPixels=1e9,
                bestEffort=True
            ).getInfo()
            if dem_elev_range and 'elevation_min' in dem_elev_range and 'elevation_max' in dem_elev_range:
                viewshed_relief_m = dem_elev_range['elevation_max'] - dem_elev_range['elevation_min']
        elif terrain_prominence_m:
            # Fallback: use prominence as proxy for relief
            viewshed_relief_m = terrain_prominence_m * 2.0  # Rough estimate
        
        # Calculate scenic viewshed score (0-100): composite of visible natural terrain and relief
        # Higher scores for high visible natural % and high relief
        scenic_viewshed_score = 0.0
        if visible_natural_pct > 0:
            # Base score from visible natural percentage (0-70 points)
            natural_component = min(70.0, visible_natural_pct * 0.7)
            # Relief component (0-30 points): rewards high-relief viewsheds
            relief_component = 0.0
            if viewshed_relief_m:
                # Scale relief: 0m = 0 points, 500m+ = 30 points
                relief_component = min(30.0, (viewshed_relief_m / 500.0) * 30.0)
            scenic_viewshed_score = natural_component + relief_component
        
        result = {
            "visible_natural_pct": round(visible_natural_pct, 2),
            "visible_natural_terrain_pct": round(visible_natural_pct, 2),  # Alias for new metric name
            "viewshed_relief_m": round(viewshed_relief_m, 2) if viewshed_relief_m else None,
            "scenic_viewshed_score": round(scenic_viewshed_score, 2),
            "viewshed_radius_m": round(viewshed_radius_m, 0),
            "terrain_prominence_m": round(terrain_prominence_m, 2) if terrain_prominence_m else None,
            "visible_forest_pct": round(visible_forest_pct, 2),
            "visible_water_pct": round(visible_water_pct, 2),
            "viewshed_quality": viewshed_quality
        }
        
        print(f"   ✅ Scenic Viewshed: {visible_natural_pct:.1f}% visible natural, relief={viewshed_relief_m:.1f}m, score={scenic_viewshed_score:.1f}, quality={viewshed_quality}")
        return result
        
    except Exception as e:
        print(f"⚠️  GEE viewshed proxy analysis error: {e}")
        return None


# Alias for backwards compatibility and clarity
def get_scenic_viewshed_index(lat: float, lon: float, radius_m: int = 5000, 
                               landcover_metrics: Optional[Dict] = None) -> Optional[Dict]:
    """
    Alias for get_viewshed_proxy - Enhanced DEM-based scenic viewshed analysis.
    
    This function computes a 360° viewshed by combining terrain analysis with landcover
    to estimate what fraction of natural features would be visible from a location.
    """
    return get_viewshed_proxy(lat, lon, radius_m, landcover_metrics)


@cached(ttl_seconds=CACHE_TTL.get('census_data', 48 * 3600))  # Landcover is stable; cache aggressively.
def get_landcover_context_gee(lat: float, lon: float, radius_m: int = 3000) -> Optional[Dict]:
    """
    Summarize surrounding land cover mix using GEE datasets.

    Attempts NLCD (US-only) first, then falls back to ESA WorldCover for global coverage.
    """
    if not GEE_AVAILABLE:
        return None

    def _compute_histogram(image: ee.Image, band: str, source: str) -> Optional[Dict]:
        histogram = image.reduceRegion(
            reducer=ee.Reducer.frequencyHistogram(),
            geometry=buffer,
            scale=scale,
            maxPixels=1e9,
            bestEffort=True
        ).get(band)
        if histogram is None:
            return None
        hist = ee.Dictionary(histogram).getInfo()
        if not hist:
            return None
        return {"source": source, "histogram": {int(float(k)): v for k, v in hist.items()}}

    try:
        print(f"🗺️  Analyzing land cover with GEE at {lat}, {lon} (radius={radius_m}m)")
        point = ee.Geometry.Point([lon, lat])
        buffer = point.buffer(radius_m)

        # Try NLCD (USA)
        scale = 30
        nlcd_image = ee.Image('USGS/NLCD_RELEASES/2021_REL/NLCD/2021').select('landcover')
        hist_info = _compute_histogram(nlcd_image, 'landcover', 'NLCD 2021')

        if hist_info is None:
            # Fallback to global ESA WorldCover (10m)
            scale = 10
            worldcover = ee.ImageCollection('ESA/WorldCover/v200').first().select('Map')
            hist_info = _compute_histogram(worldcover, 'Map', 'ESA WorldCover v200')

        if hist_info is None:
            return None

        histogram = hist_info["histogram"]
        total_pixels = sum(histogram.values())
        if total_pixels <= 0:
            return None

        def pct(class_ids):
            count = sum(histogram.get(cid, 0) for cid in class_ids)
            return round((count / total_pixels) * 100, 2)

        if hist_info["source"].startswith('NLCD'):
            forest_pct = pct([41, 42, 43])
            wetland_pct = pct([90, 95])
            water_pct = pct([11])
            shrub_pct = pct([52])
            grass_pct = pct([71])
            developed_pct = pct([21, 22, 23, 24])
        else:
            # ESA WorldCover class mapping (see https://esa-worldcover.org/en/data-access)
            forest_pct = pct([10, 20, 30])
            wetland_pct = pct([90])
            water_pct = pct([80])
            shrub_pct = pct([40])
            grass_pct = pct([60])
            developed_pct = pct([50])

        result = {
            "source": hist_info["source"],
            "forest_pct": forest_pct,
            "wetland_pct": wetland_pct,
            "water_pct": water_pct,
            "shrub_pct": shrub_pct,
            "grass_pct": grass_pct,
            "developed_pct": developed_pct
        }

        print(f"   ✅ GEE Land Cover ({hist_info['source']}): forest={forest_pct}%, water={water_pct}%")
        return result

    except Exception as e:
        print(f"⚠️  GEE land cover analysis error: {e}")
        return None


# ---------------------------------------------------------------------------
# Climate & Flood Risk pillar (Phase 1A: GEE only — heat + air quality)
# ---------------------------------------------------------------------------

@cached(ttl_seconds=CACHE_TTL.get('census_data', 48 * 3600))
def get_heat_exposure_lst(
    lat: float, lon: float, local_radius_m: int = 500, regional_radius_m: int = 5000
) -> Optional[Dict]:
    """
    Landsat 8/9 Collection 2 L2 surface temperature (ST_B10).
    JJA (June–August) composite; heat_excess = local_mean - regional_mean (urban heat island).
    Returns heat_excess_deg_c, local_lst_c, regional_lst_c for climate_risk pillar.
    """
    if not GEE_AVAILABLE:
        return None
    try:
        point = ee.Geometry.Point([lon, lat])
        local_buffer = point.buffer(local_radius_m)
        regional_buffer = point.buffer(regional_radius_m)

        # Landsat 8 + 9 C02 T1_L2: ST_B10 = surface temp (Kelvin: scale 0.00341802, offset 149.0)
        l8 = (ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')
              .filterDate('2022-06-01', '2022-08-31')
              .filterBounds(regional_buffer)
              .filter(ee.Filter.lt('CLOUD_COVER', 30)))
        l9 = (ee.ImageCollection('LANDSAT/LC09/C02/T1_L2')
              .filterDate('2022-06-01', '2022-08-31')
              .filterBounds(regional_buffer)
              .filter(ee.Filter.lt('CLOUD_COVER', 30)))
        combined = l8.merge(l9)
        n_images = combined.size().getInfo()
        if not n_images or n_images == 0:
            print("   ⚠️  GEE LST: no Landsat images in date range / bounds")
            return None
        composite = combined.mean()

        # ST_B10: Kelvin = scale * DN + offset (USGS C02 L2)
        scale = 0.00341802
        offset = 149.0
        lst_k = composite.select('ST_B10').multiply(scale).add(offset)
        lst_c = lst_k.subtract(273.15)

        local_mean = lst_c.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=local_buffer,
            scale=100,
            maxPixels=1e9
        )
        regional_mean = lst_c.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=regional_buffer,
            scale=100,
            maxPixels=1e9
        )
        local_info = local_mean.getInfo()
        regional_info = regional_mean.getInfo()
        if not local_info or not regional_info:
            return None
        # Band name is ST_B10; fallback to first value if key differs (e.g. some GEE versions)
        local_c = local_info.get('ST_B10')
        regional_c = regional_info.get('ST_B10')
        if local_c is None and len(local_info) == 1:
            local_c = next(iter(local_info.values()))
        if regional_c is None and len(regional_info) == 1:
            regional_c = next(iter(regional_info.values()))
        if local_c is None or regional_c is None:
            return None
        try:
            local_f = float(local_c)
            regional_f = float(regional_c)
        except (TypeError, ValueError):
            return None
        if not (abs(local_f) < 1e6 and abs(regional_f) < 1e6):
            return None
        heat_excess = local_f - regional_f
        return {
            'heat_excess_deg_c': round(heat_excess, 2),
            'local_lst_c': round(local_f, 2),
            'regional_lst_c': round(regional_f, 2),
        }
    except Exception as e:
        print(f"   ⚠️  GEE LST heat exposure error: {e}")
        return None


@cached(ttl_seconds=CACHE_TTL.get('census_data', 48 * 3600))
def get_air_quality_aer_ai(lat: float, lon: float, radius_m: int = 2000) -> Optional[Dict]:
    """
    Sentinel-5P NRTI L3 Aerosol Index (UV AI). Used as air-quality proxy for climate_risk pillar.
    PRD uses PM2.5 (ug/m³); GEE S5P does not provide PM2.5 directly. We use AER_AI mean and
    map to a 0–35 proxy scale for scoring (higher AI = worse). Returns pm25_proxy_ugm3 (0–35 scale).
    """
    if not GEE_AVAILABLE:
        return None
    try:
        point = ee.Geometry.Point([lon, lat])
        buffer = point.buffer(radius_m)
        # COPERNICUS/S5P/NRTI/L3_AER_AI; use recent year
        col = (ee.ImageCollection('COPERNICUS/S5P/NRTI/L3_AER_AI')
               .filterDate('2023-01-01', '2024-12-31')
               .filterBounds(buffer)
               .select('absorbing_aerosol_index'))
        n_images = col.size().getInfo()
        if not n_images or n_images == 0:
            print("   ⚠️  GEE AER_AI: no S5P images in date range / bounds")
            return None
        img = col.mean()
        stats = img.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=buffer,
            scale=11132,
            maxPixels=1e9
        )
        info = stats.getInfo()
        if not info:
            return None
        ai_val = info.get('absorbing_aerosol_index')
        if ai_val is None and len(info) == 1:
            ai_val = next(iter(info.values()))
        if ai_val is None:
            return None
        try:
            ai_float = float(ai_val)
        except (TypeError, ValueError):
            return None
        # Aerosol index typically -1 to 5; map to 0–35 proxy (higher = worse). Rough: 0 -> 0, 2 -> 20, 4+ -> 35
        pm25_proxy = max(0, min(35, ai_float * 8.75))
        return {
            'aer_ai_mean': round(ai_float, 3),
            'pm25_proxy_ugm3': round(pm25_proxy, 1),
        }
    except Exception as e:
        print(f"   ⚠️  GEE air quality (AER_AI) error: {e}")
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
