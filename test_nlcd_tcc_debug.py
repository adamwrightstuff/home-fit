#!/usr/bin/env python3
"""Debug NLCD TCC to see why it's returning None."""

import ee
from data_sources.gee_api import GEE_AVAILABLE, _initialize_gee

if not GEE_AVAILABLE:
    _initialize_gee()

if GEE_AVAILABLE:
    lat, lon = 47.6101, -122.2015
    point = ee.Geometry.Point([lon, lat])
    buffer = point.buffer(1000)
    
    print("Testing NLCD TCC for Bellevue, WA...")
    print(f"Coordinates: {lat}, {lon}")
    print()
    
    # Try different years
    for year in [2023, 2022, 2021]:
        try:
            print(f"Testing year {year}...")
            nlcd_collection = ee.ImageCollection('USGS/NLCD_RELEASES/2023_REL/TCC/v2023-5')
            filtered = nlcd_collection.filter(ee.Filter.eq('year', year))
            count = filtered.size().getInfo()
            print(f"  Collection size for {year}: {count}")
            
            if count > 0:
                nlcd_tcc = filtered.first()
                print(f"  First image: {nlcd_tcc.getInfo()}")
                nlcd_tcc = nlcd_tcc.select('NLCD_Percent_Tree_Canopy_Cover')
                
                tcc_stats = nlcd_tcc.reduceRegion(
                    reducer=ee.Reducer.mean(),
                    geometry=buffer,
                    scale=30,
                    maxPixels=1e9
                )
                result = tcc_stats.getInfo()
                print(f"  Result: {result}")
                tcc_pct = result.get('NLCD_Percent_Tree_Canopy_Cover')
                if tcc_pct is not None:
                    print(f"  ✅ Canopy: {tcc_pct:.1f}%")
                    break
                else:
                    print(f"  ⚠️  Result is None")
            else:
                print(f"  ⚠️  No images for year {year}")
        except Exception as e:
            print(f"  ❌ Error: {e}")
        print()
