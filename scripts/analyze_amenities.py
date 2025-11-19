#!/usr/bin/env python3
"""
Amenities Analysis Script

Analyzes neighborhood amenities test cases to identify patterns, issues, and calibration needs.
Focuses on walkability, business density, variety, and location quality.

Usage:
    python scripts/analyze_amenities.py [--input CSV_FILE] [--output OUTPUT_DIR]
"""

import json
import sys
import csv
import os
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
from collections import defaultdict

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from pillars.neighborhood_amenities import get_neighborhood_amenities_score
    from data_sources import geocoding
except ImportError:
    print("⚠️  Cannot import amenities module. Run from project root.")
    sys.exit(1)


@dataclass
class AmenitiesTestCase:
    """Test case with location and metrics."""
    name: str
    lat: Optional[float] = None
    lon: Optional[float] = None
    city: Optional[str] = None
    state: Optional[str] = None
    area_type: Optional[str] = None
    expected_score_range: Optional[str] = None
    notes: Optional[str] = None
    calculated_score: Optional[float] = None
    home_walkability: Optional[float] = None
    location_quality: Optional[float] = None
    total_businesses: Optional[int] = None
    businesses_within_1km: Optional[int] = None
    tier1_count: Optional[int] = None
    tier2_count: Optional[int] = None
    tier3_count: Optional[int] = None
    tier4_count: Optional[int] = None


def parse_test_data_from_csv(csv_file: str) -> List[AmenitiesTestCase]:
    """Parse test data from CSV file."""
    test_cases = []
    
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Extract location name
            name = row.get('Location', '').strip()
            if not name:
                continue
            
            # Try to geocode if lat/lon not provided
            lat = None
            lon = None
            city = row.get('City', '').strip()
            state = row.get('State', '').strip()
            
            if 'lat' in row and row.get('lat'):
                try:
                    lat = float(row['lat'])
                    lon = float(row['lon'])
                except (ValueError, KeyError):
                    pass
            
            if lat is None:
                # Geocode the location
                try:
                    location_str = f"{name}"
                    if city and state:
                        location_str = f"{city}, {state}"
                    elif city:
                        location_str = f"{name}, {city}"
                    
                    result = geocoding.geocode(location_str)
                    if result:
                        # geocode returns (lat, lon, zip_code, state, city)
                        lat, lon, zip_code, geocoded_state, geocoded_city = result
                        if not city:
                            city = geocoded_city
                        if not state:
                            state = geocoded_state
                except Exception as e:
                    print(f"⚠️  Could not geocode {name}: {e}")
                    continue
            
            test_case = AmenitiesTestCase(
                name=name,
                lat=lat,
                lon=lon,
                city=city,
                state=state,
                area_type=row.get('Area Type', '').strip() or None,
                expected_score_range=row.get('Expected Amenities Score', '').strip() or None,
                notes=row.get('Notes', '').strip() or None
            )
            
            test_cases.append(test_case)
    
    return test_cases


def analyze_amenities_score(test_case: AmenitiesTestCase) -> Dict:
    """Analyze amenities score for a test case."""
    if test_case.lat is None or test_case.lon is None:
        return {"error": "Missing coordinates"}
    
    try:
        score, breakdown = get_neighborhood_amenities_score(
            lat=test_case.lat,
            lon=test_case.lon,
            include_chains=False,
            area_type=test_case.area_type
        )
        
        # Extract component breakdown
        home_walkability = breakdown.get("breakdown", {}).get("home_walkability", {})
        location_quality = breakdown.get("breakdown", {}).get("location_quality", 0)
        
        home_score = home_walkability.get("score", 0) if isinstance(home_walkability, dict) else 0
        home_breakdown = home_walkability.get("breakdown", {}) if isinstance(home_walkability, dict) else {}
        
        # Extract summary metrics
        summary = breakdown.get("summary", {})
        total_businesses = summary.get("total_businesses", 0)
        businesses_within_1km = home_walkability.get("businesses_within_1km", 0) if isinstance(home_walkability, dict) else 0
        
        by_tier = summary.get("by_tier", {})
        tier1_count = by_tier.get("daily_essentials", {}).get("count", 0)
        tier2_count = by_tier.get("social_dining", {}).get("count", 0)
        tier3_count = by_tier.get("culture_leisure", {}).get("count", 0)
        tier4_count = by_tier.get("services_retail", {}).get("count", 0)
        
        # Parse expected score range
        expected_min = None
        expected_max = None
        if test_case.expected_score_range:
            try:
                parts = test_case.expected_score_range.split('-')
                if len(parts) == 2:
                    expected_min = float(parts[0])
                    expected_max = float(parts[1])
            except (ValueError, IndexError):
                pass
        
        score_gap = None
        if expected_min is not None and expected_max is not None:
            if score < expected_min:
                score_gap = score - expected_min  # Negative = under-scoring
            elif score > expected_max:
                score_gap = score - expected_max  # Positive = over-scoring
            else:
                score_gap = 0  # Within range
        
        return {
            "location": test_case.name,
            "city": test_case.city,
            "state": test_case.state,
            "calculated_score": round(score, 2),
            "expected_min": expected_min,
            "expected_max": expected_max,
            "score_gap": round(score_gap, 2) if score_gap is not None else None,
            "within_range": expected_min <= score <= expected_max if (expected_min is not None and expected_max is not None) else None,
            "home_walkability": {
                "score": round(home_score, 2),
                "density": round(home_breakdown.get("density", 0), 2),
                "variety": round(home_breakdown.get("variety", 0), 2),
                "proximity": round(home_breakdown.get("proximity", 0), 2),
                "businesses_within_1km": businesses_within_1km
            },
            "location_quality": round(location_quality, 2),
            "business_metrics": {
                "total_businesses": total_businesses,
                "businesses_within_1km": businesses_within_1km,
                "tier1_daily_essentials": tier1_count,
                "tier2_social_dining": tier2_count,
                "tier3_culture_leisure": tier3_count,
                "tier4_services_retail": tier4_count
            },
            "summary": summary,
            "data_quality": breakdown.get("data_quality", {}),
            "notes": test_case.notes
        }
    except Exception as e:
        import traceback
        return {
            "location": test_case.name,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


def analyze_patterns(analyses: List[Dict]) -> Dict:
    """Analyze patterns across all test cases."""
    patterns = {
        "by_area_type": defaultdict(list),
        "under_scoring": [],
        "over_scoring": [],
        "within_range": [],
        "business_density_patterns": [],
        "walkability_patterns": [],
        "location_quality_patterns": [],
        "tier_distribution": defaultdict(list)
    }
    
    for analysis in analyses:
        if "error" in analysis:
            continue
        
        area_type = analysis.get("area_type", "unknown")
        patterns["by_area_type"][area_type].append(analysis)
        
        # Check for scoring gaps
        score_gap = analysis.get("score_gap")
        within_range = analysis.get("within_range")
        
        if within_range is True:
            patterns["within_range"].append(analysis)
        elif score_gap is not None:
            if score_gap < -10:  # Under-scoring by 10+ points
                patterns["under_scoring"].append(analysis)
            elif score_gap > 10:  # Over-scoring by 10+ points
                patterns["over_scoring"].append(analysis)
        
        # Business density patterns
        business_metrics = analysis.get("business_metrics", {})
        total_businesses = business_metrics.get("total_businesses", 0)
        businesses_1km = business_metrics.get("businesses_within_1km", 0)
        score = analysis.get("calculated_score", 0)
        
        patterns["business_density_patterns"].append({
            "location": analysis["location"],
            "total_businesses": total_businesses,
            "businesses_1km": businesses_1km,
            "score": score,
            "area_type": area_type
        })
        
        # Walkability patterns
        home_walk = analysis.get("home_walkability", {})
        patterns["walkability_patterns"].append({
            "location": analysis["location"],
            "home_score": home_walk.get("score", 0),
            "density": home_walk.get("density", 0),
            "variety": home_walk.get("variety", 0),
            "proximity": home_walk.get("proximity", 0),
            "businesses_1km": home_walk.get("businesses_within_1km", 0),
            "score": score,
            "area_type": area_type
        })
        
        # Location quality patterns
        location_quality = analysis.get("location_quality", 0)
        patterns["location_quality_patterns"].append({
            "location": analysis["location"],
            "location_quality": location_quality,
            "score": score,
            "area_type": area_type
        })
        
        # Tier distribution
        patterns["tier_distribution"][area_type].append({
            "tier1": business_metrics.get("tier1_daily_essentials", 0),
            "tier2": business_metrics.get("tier2_social_dining", 0),
            "tier3": business_metrics.get("tier3_culture_leisure", 0),
            "tier4": business_metrics.get("tier4_services_retail", 0),
            "score": score
        })
    
    return patterns


def generate_report(analyses: List[Dict], patterns: Dict, output_dir: str):
    """Generate analysis report."""
    os.makedirs(output_dir, exist_ok=True)
    
    # Full analysis JSON
    with open(f"{output_dir}/amenities_analysis.json", 'w') as f:
        json.dump({
            "analyses": analyses,
            "patterns": patterns
        }, f, indent=2)
    
    # Summary report
    with open(f"{output_dir}/amenities_summary.txt", 'w') as f:
        f.write("=" * 80 + "\n")
        f.write("Neighborhood Amenities Analysis Summary\n")
        f.write("=" * 80 + "\n\n")
        
        f.write(f"Total Locations Analyzed: {len(analyses)}\n\n")
        
        # Within range
        f.write(f"Within Expected Range: {len(patterns['within_range'])}\n")
        f.write(f"Under-Scoring (10+ points below): {len(patterns['under_scoring'])}\n")
        f.write(f"Over-Scoring (10+ points above): {len(patterns['over_scoring'])}\n\n")
        
        # Under-scoring
        if patterns["under_scoring"]:
            f.write("Under-Scoring Locations (10+ points below expected min):\n")
            f.write("-" * 80 + "\n")
            for loc in sorted(patterns["under_scoring"], key=lambda x: x.get("score_gap", 0)):
                f.write(f"  {loc['location']}: {loc['calculated_score']} (expected: {loc['expected_min']}-{loc['expected_max']}, "
                       f"gap: {loc['score_gap']})\n")
            f.write("\n")
        
        # Over-scoring
        if patterns["over_scoring"]:
            f.write("Over-Scoring Locations (10+ points above expected max):\n")
            f.write("-" * 80 + "\n")
            for loc in sorted(patterns["over_scoring"], key=lambda x: x.get("score_gap", 0), reverse=True):
                f.write(f"  {loc['location']}: {loc['calculated_score']} (expected: {loc['expected_min']}-{loc['expected_max']}, "
                       f"gap: {loc['score_gap']})\n")
            f.write("\n")
        
        # By area type
        f.write("Score Distribution by Area Type:\n")
        f.write("-" * 80 + "\n")
        for area_type, locs in patterns["by_area_type"].items():
            scores = [l["calculated_score"] for l in locs if "calculated_score" in l]
            if scores:
                avg = sum(scores) / len(scores)
                f.write(f"  {area_type}: {len(locs)} locations, avg score: {avg:.1f}\n")
        f.write("\n")
        
        # Business density analysis
        f.write("Business Density Patterns:\n")
        f.write("-" * 80 + "\n")
        density_patterns = patterns["business_density_patterns"]
        high_density = [p for p in density_patterns if p["total_businesses"] >= 50]
        low_density = [p for p in density_patterns if p["total_businesses"] < 20]
        f.write(f"  High density (50+ businesses): {len(high_density)} locations\n")
        f.write(f"  Low density (<20 businesses): {len(low_density)} locations\n")
        f.write("\n")
        
        # Walkability analysis
        f.write("Walkability Patterns:\n")
        f.write("-" * 80 + "\n")
        walk_patterns = patterns["walkability_patterns"]
        high_walkability = [p for p in walk_patterns if p["home_score"] >= 50]
        low_walkability = [p for p in walk_patterns if p["home_score"] < 30]
        f.write(f"  High walkability (50+ home score): {len(high_walkability)} locations\n")
        f.write(f"  Low walkability (<30 home score): {len(low_walkability)} locations\n")
        f.write("\n")
    
    # CSV export for further analysis
    with open(f"{output_dir}/amenities_analysis.csv", 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            "Location", "City", "State", "Area Type", "Calculated Score", 
            "Expected Min", "Expected Max", "Score Gap", "Within Range",
            "Home Walkability", "Location Quality", "Total Businesses",
            "Businesses 1km", "Tier1 Daily", "Tier2 Social", "Tier3 Culture", "Tier4 Services",
            "Density Score", "Variety Score", "Proximity Score"
        ])
        
        for analysis in analyses:
            if "error" in analysis:
                continue
            
            home_walk = analysis.get("home_walkability", {})
            business_metrics = analysis.get("business_metrics", {})
            
            writer.writerow([
                analysis["location"],
                analysis.get("city", ""),
                analysis.get("state", ""),
                analysis.get("area_type", ""),
                analysis["calculated_score"],
                analysis.get("expected_min", ""),
                analysis.get("expected_max", ""),
                analysis.get("score_gap", ""),
                analysis.get("within_range", ""),
                home_walk.get("score", ""),
                analysis.get("location_quality", ""),
                business_metrics.get("total_businesses", ""),
                business_metrics.get("businesses_within_1km", ""),
                business_metrics.get("tier1_daily_essentials", ""),
                business_metrics.get("tier2_social_dining", ""),
                business_metrics.get("tier3_culture_leisure", ""),
                business_metrics.get("tier4_services_retail", ""),
                home_walk.get("density", ""),
                home_walk.get("variety", ""),
                home_walk.get("proximity", "")
            ])
    
    print(f"\n✅ Analysis complete! Results saved to {output_dir}/")
    print(f"   - amenities_analysis.json (full data)")
    print(f"   - amenities_summary.txt (summary report)")
    print(f"   - amenities_analysis.csv (spreadsheet format)")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Analyze Neighborhood Amenities Test Cases")
    parser.add_argument("--input", type=str, default="test_data/amenities_test_cases.csv",
                       help="Input CSV file with test cases")
    parser.add_argument("--output", type=str, default="analysis",
                       help="Output directory for analysis results")
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("Neighborhood Amenities Analysis Script")
    print("=" * 80)
    print(f"\nReading test cases from: {args.input}")
    
    # Parse test data
    test_cases = parse_test_data_from_csv(args.input)
    print(f"Found {len(test_cases)} test cases\n")
    
    # Analyze each location
    analyses = []
    for i, test_case in enumerate(test_cases, 1):
        print(f"[{i}/{len(test_cases)}] Analyzing: {test_case.name}")
        analysis = analyze_amenities_score(test_case)
        analyses.append(analysis)
        
        if "error" in analysis:
            print(f"  ❌ Error: {analysis['error']}")
        else:
            score = analysis['calculated_score']
            home = analysis['home_walkability']['score']
            location = analysis['location_quality']
            businesses = analysis['business_metrics']['businesses_within_1km']
            print(f"  ✅ Score: {score} (Home: {home}, Location: {location}, Businesses 1km: {businesses})")
    
    # Analyze patterns
    print("\n" + "=" * 80)
    print("Analyzing Patterns...")
    print("=" * 80)
    patterns = analyze_patterns(analyses)
    
    # Generate report
    generate_report(analyses, patterns, args.output)


if __name__ == "__main__":
    main()

