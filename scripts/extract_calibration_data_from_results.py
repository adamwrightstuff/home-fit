#!/usr/bin/env python3
"""
Extract calibration data from existing API results.

This script:
1. Reads data/results.csv (177 locations with API responses)
2. Parses JSON responses to extract:
   - Current scores for each pillar
   - Raw component scores (for pillars that have them)
   - Area types
3. Saves to JSON file ready for target score addition
"""

import json
import csv
import os
import sys
from typing import Dict, List, Optional
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def extract_pillar_data(response_json: Dict, pillar_name: str) -> Optional[Dict]:
    """Extract data for a specific pillar from API response."""
    try:
        pillars = response_json.get('livability_pillars', {})
        pillar_data = pillars.get(pillar_name)
        
        if not pillar_data:
            return None
        
        # Extract score
        score = pillar_data.get('score')
        
        # Extract breakdown for component scores
        breakdown = pillar_data.get('breakdown', {})
        
        # Extract area type
        area_classification = pillar_data.get('area_classification', {})
        area_type = area_classification.get('area_type')
        
        # Extract raw component scores based on pillar
        components = {}
        
        if pillar_name == 'active_outdoors':
            # Extract component scores (breakdown is direct, not nested)
            components = {
                'daily_urban_outdoors': breakdown.get('daily_urban_outdoors'),
                'wild_adventure': breakdown.get('wild_adventure'),
                'waterfront_lifestyle': breakdown.get('waterfront_lifestyle'),
            }
            # Calculate raw_total from components (before calibration)
            daily = components.get('daily_urban_outdoors', 0) or 0
            wild = components.get('wild_adventure', 0) or 0
            water = components.get('waterfront_lifestyle', 0) or 0
            raw_total = 0.30 * daily + 0.50 * wild + 0.20 * water
        
        elif pillar_name == 'natural_beauty':
            # Extract component scores
            # API uses tree_score_0_50 and enhancer_bonus_scaled (or enhancer_bonus_raw)
            tree_score = breakdown.get('tree_score_0_50', 0) or 0
            # Try to get scaled bonus first, fallback to raw
            enhancer_bonus_scaled = breakdown.get('enhancer_bonus_scaled', 0) or 0
            if not enhancer_bonus_scaled:
                enhancer_bonus_raw = breakdown.get('enhancer_bonus_raw', 0) or 0
                enhancer_bonus_scaled = min(18.0, enhancer_bonus_raw)
            
            # Also check details for enhancer_bonus_scaled
            details = pillar_data.get('details', {})
            if not enhancer_bonus_scaled and details:
                enhancer_bonus_scaled = details.get('enhancer_bonus_scaled', 0) or 0
                if not enhancer_bonus_scaled:
                    enhancer_bonus_raw = details.get('enhancer_bonus_raw', 0) or 0
                    enhancer_bonus_scaled = min(18.0, enhancer_bonus_raw)
            
            components = {
                'tree_score': tree_score,
                'natural_bonus_scaled': enhancer_bonus_scaled,
            }
            # Calculate raw_total using NEW formula (adjusted component weights)
            # Formula: (tree_score * 0.4) + (natural_bonus_scaled * 1.67), then scale to 0-100
            tree_weighted = tree_score * 0.4  # Max 20 points
            scenic_weighted = min(30.0, enhancer_bonus_scaled * 1.67)  # Max 30 points
            natural_native = max(0.0, tree_weighted + scenic_weighted)
            raw_total = min(100.0, natural_native * 2.0)  # Scale 0-50 to 0-100
        
        else:
            # For other pillars, just get score
            raw_total = score  # May not be accurate, but placeholder
        
        return {
            'current_score': score,
            'raw_total': raw_total,
            'components': components,
            'area_type': area_type,
            'breakdown': breakdown  # Keep full breakdown for reference
        }
    
    except Exception as e:
        print(f"  Warning: Error extracting {pillar_name}: {e}")
        return None


def extract_calibration_data(results_file: str, output_file: str, pillars: List[str]) -> None:
    """Extract calibration data from results.csv."""
    print("=" * 80)
    print("Extracting Calibration Data from API Results")
    print("=" * 80)
    print(f"Input: {results_file}")
    print(f"Output: {output_file}")
    print(f"Pillars: {', '.join(pillars)}")
    print()
    
    calibration_data = {
        "source": "data/results.csv",
        "extraction_date": datetime.now().isoformat(),
        "pillars": pillars,
        "locations": []
    }
    
    # Read results.csv
    locations_processed = 0
    locations_with_data = 0
    
    with open(results_file, 'r') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            location = row.get('location', '').strip()
            raw_json_str = row.get('raw_json', '')
            
            if not location or not raw_json_str:
                continue
            
            locations_processed += 1
            
            try:
                response_json = json.loads(raw_json_str)
            except json.JSONDecodeError as e:
                print(f"  Warning: Failed to parse JSON for {location}: {e}")
                continue
            
            # Extract location data
            location_data = {
                "name": location,
                "lat": None,  # Could extract from response if available
                "lon": None,  # Could extract from response if available
                "area_type": None,  # Will get from first pillar
                "pillars": {},
                "target_scores": {}  # User will fill these in
            }
            
            # Extract data for each pillar
            has_data = False
            for pillar_name in pillars:
                pillar_data = extract_pillar_data(response_json, pillar_name)
                
                if pillar_data:
                    location_data["pillars"][pillar_name] = pillar_data
                    # Set area_type from first pillar that has it
                    if location_data["area_type"] is None:
                        location_data["area_type"] = pillar_data.get('area_type')
                    has_data = True
                    # Initialize target score placeholder
                    location_data["target_scores"][pillar_name] = None
            
            if has_data:
                calibration_data["locations"].append(location_data)
                locations_with_data += 1
            
            if locations_processed % 20 == 0:
                print(f"  Processed {locations_processed} locations...")
    
    print()
    print(f"✅ Processed {locations_processed} locations")
    print(f"✅ Extracted data for {locations_with_data} locations")
    print()
    
    # Save to JSON
    print(f"Saving to {output_file}...")
    with open(output_file, 'w') as f:
        json.dump(calibration_data, f, indent=2)
    
    print(f"✅ Saved calibration data to {output_file}")
    print()
    print("Next Steps:")
    print("1. Review extracted data")
    print("2. Add target scores (via LLM evaluation or manual)")
    print("3. Calculate calibration parameters")
    print("4. Apply calibration to pillars")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Extract calibration data from API results')
    parser.add_argument('--input', type=str, default='data/results.csv',
                       help='Input CSV file with API results')
    parser.add_argument('--output', type=str, default='analysis/calibration_data_177_locations.json',
                       help='Output JSON file')
    parser.add_argument('--pillars', type=str, nargs='+',
                       default=['active_outdoors', 'natural_beauty'],
                       help='Pillars to extract data for')
    
    args = parser.parse_args()
    
    extract_calibration_data(args.input, args.output, args.pillars)
