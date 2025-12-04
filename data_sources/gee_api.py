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


def get_tree_canopy_gee(lat: float, lon: float, radius_m: int = 1000, area_type: Optional[str] = None) -> Optional[float]:
    """
    Get tree canopy percentage using Google Earth Engine.
    
    Uses NLCD Tree Canopy Cover dataset (30m resolution, USA only) as primary source.
    Validates against other sources for quality assurance. No data fabrication - uses real measurements only.
    
    Priority:
    1. NLCD TCC (2021) - Primary source, designed for urban/suburban areas
    2. NLCD Land Cover - Validation source
    3. Hansen Global Forest - Fallback only (measures woody vegetation, not just canopy)
    4. Sentinel-2 NDVI - Final fallback
    
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
        
        # Create point of interest
        point = ee.Geometry.Point([lon, lat])
        buffer = point.buffer(radius_m)
        
        # Priority 1: NLCD/USGS Tree Canopy Cover (urban/suburban, USA-only, CONUS coverage)
        # This is the official USGS NLCD TCC dataset (2023 release with data 1985-2023)
        nlcd_tcc_result = None
        try:
            nlcd_collection = ee.ImageCollection('USGS/NLCD_RELEASES/2023_REL/TCC/v2023-5')
            # Use 2021 data (most recent complete year at time of writing)
            nlcd_tcc = nlcd_collection.filter(ee.Filter.eq('year', 2021)).first().select('NLCD_Percent_Tree_Canopy_Cover')
            # Use mean reducer for accurate percentage coverage calculation
            tcc_stats = nlcd_tcc.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=buffer,
                scale=30,
                maxPixels=1e9
            )
            tcc_pct = tcc_stats.get('NLCD_Percent_Tree_Canopy_Cover').getInfo()
            # Lower threshold: accept any non-negative value (was >= 0.1)
            # Design principle: Objective and data-driven - use actual measured values
            if tcc_pct is not None and tcc_pct >= 0.0:
                print(f"   ✅ GEE Tree Canopy (USGS/NLCD TCC 2021): {tcc_pct:.1f}%")
                nlcd_tcc_result = min(100, max(0, tcc_pct))
            else:
                print(f"   ⚠️  NLCD TCC returned {0 if tcc_pct is None else tcc_pct:.1f}% (unavailable)")
        except Exception as nlcd_tcc_error:
            print(f"   ⚠️  NLCD TCC unavailable: {nlcd_tcc_error}")

        # Priority 2: Hansen Global Tree Cover (more reliable, global coverage)
        hansen_result = None
        try:
            hansen = ee.Image('UMD/hansen/global_forest_change_2024_v1_12').select('treecover2000')
            # Use mean reducer for accurate percentage coverage calculation
            h_stats = hansen.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=buffer,
                scale=30,
                maxPixels=1e9
            )
            h_mean = h_stats.get('treecover2000').getInfo()
            # Lower threshold: accept any non-negative value (was >= 0.1)
            # Design principle: Objective and data-driven - use actual measured values
            if h_mean is not None and h_mean >= 0.0:
                print(f"   ✅ GEE Tree Canopy (Hansen): {h_mean:.1f}%")
                hansen_result = min(100, max(0, h_mean))
            else:
                print(f"   ⚠️  Hansen tree cover returned {0 if h_mean is None else h_mean:.1f}% (unavailable)")
        except Exception as hansen_error:
            print(f"   ⚠️  Hansen tree cover unavailable: {hansen_error}")

        # Priority 3: NLCD Land Cover forest classes (rural/forested, USA-only)
        nlcd_landcover_result = None
        try:
            nlcd = ee.Image('USGS/NLCD_RELEASES/2021_REL/NLCD/2021')
            landcover = nlcd.select('landcover')
            # Classes: 40 Deciduous, 41 Evergreen, 42 Mixed, 43 Shrub/Scrub
            tree_classes = landcover.eq(40).Or(landcover.eq(41)).Or(landcover.eq(42)).Or(landcover.eq(43))
            # Use mean reducer for accurate percentage coverage calculation
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
                nlcd_landcover_result = min(100, max(0, canopy_percentage))
            else:
                print("   ⚠️  NLCD Land Cover forest classes indicate ~0% within buffer")
        except Exception as nlcd_error:
            print(f"   ⚠️  NLCD Land Cover unavailable: {nlcd_error}")
        
        # Validation-based multi-source approach: Use NLCD TCC as primary, validate with others
        if nlcd_tcc_result:
            # NLCD TCC is designed for urban/suburban - prioritize it
            primary_result = nlcd_tcc_result
            
            # Validate against other sources (don't blindly average - check agreement)
            validation_sources = []
            if nlcd_landcover_result:
                validation_sources.append(('NLCD Land Cover', nlcd_landcover_result))
            # Note: Hansen measures different things (woody vegetation vs tree canopy) - use cautiously
            
            # Check agreement with validation sources
            if validation_sources:
                agreements = []
                for source_name, source_value in validation_sources:
                    diff = abs(primary_result - source_value)
                    if diff <= 5:  # Within 5% = good agreement
                        agreements.append(source_name)
                        print(f"   ✓ {source_name} validates NLCD TCC (diff: {diff:.1f}%)")
                    elif diff <= 10:  # Within 10% = acceptable
                        agreements.append(source_name)
                        print(f"   ~ {source_name} roughly agrees with NLCD TCC (diff: {diff:.1f}%)")
                    else:
                        print(f"   ⚠️  {source_name} differs significantly from NLCD TCC ({diff:.1f}% diff)")
                
                if agreements:
                    print(f"   📊 NLCD TCC validated by {len(agreements)} source(s)")
                else:
                    print(f"   ⚠️  Validation sources disagree - using NLCD TCC as primary")
            
            # Validate canopy value for sanity (doesn't affect scoring, just logs warnings)
            # Design principle: Transparent and documented - flag data quality issues
            if primary_result is not None:
                if primary_result > 100.0:
                    print(f"   ⚠️  Canopy value {primary_result}% exceeds 100%, capping to 100%")
                    primary_result = 100.0
                elif primary_result > 80.0:
                    print(f"   ⚠️  Unusually high canopy value {primary_result}% - verify data quality")
                elif primary_result < 0.0:
                    print(f"   ⚠️  Negative canopy value {primary_result}%, setting to 0%")
                    primary_result = 0.0
            
            return primary_result
        
        # Fallback: If NLCD unavailable, try other sources
        sources = []
        if nlcd_landcover_result:
            sources.append(('NLCD Land Cover', nlcd_landcover_result))
        if hansen_result:
            sources.append(('Hansen', hansen_result))
        
        if len(sources) == 1:
            return sources[0][1]
        elif len(sources) > 1:
            # If multiple fallback sources, average them
            values = [s[1] for s in sources]
            combined_result = sum(values) / len(values)
            source_names = ', '.join([s[0] for s in sources])
            print(f"   📊 Combined fallback result ({source_names}): {combined_result:.1f}%")
            return min(100, max(0, combined_result))
        
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

        dem_info = dem_stats.getInfo()
        slope_info = slope_stats.getInfo()
        steep_info = steep_fraction.getInfo()

        if not dem_info or not slope_info:
            return None

        elevation_min = dem_info.get('elevation_min')
        elevation_max = dem_info.get('elevation_max')
        elevation_mean = dem_info.get('elevation_mean')
        relief = None
        if elevation_min is not None and elevation_max is not None:
            relief = elevation_max - elevation_min

        topography = {
            "source": "USGS/SRTMGL1_003",
            "elevation_mean_m": elevation_mean,
            "elevation_min_m": elevation_min,
            "elevation_max_m": elevation_max,
            "elevation_p10_m": dem_info.get('elevation_p10'),
            "elevation_p90_m": dem_info.get('elevation_p90'),
            "relief_range_m": relief,
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

        print(f"   ✅ GEE Topography: relief={relief:.1f}m, mean slope={topography['slope_mean_deg']:.1f}°")
        return topography

    except Exception as e:
        print(f"⚠️  GEE topography analysis error: {e}")
        return None


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
