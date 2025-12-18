#!/usr/bin/env python3
"""
Pillar Tuning from Collected Results

Analyzes collected HomeFit API results to tune pillars with sufficient variance.
Focuses on pillars that have meaningful variation across locations.

Usage:
    python scripts/tune_pillars_from_results.py [--pillar PILLAR_NAME] [--output-dir analysis/]
"""

import csv
import json
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import numpy as np

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Pillars with sufficient variance for tuning (std > 1.0)
TUNEABLE_PILLARS = [
    "air_travel_access",        # std: 44.27
    "neighborhood_amenities",   # std: 23.79
    "healthcare_access",         # std: 24.30
    "public_transit_access",     # std: 28.41
    "built_beauty",              # std: 20.22
    "housing_value"              # std: 16.41
]


def load_results(results_csv: Path) -> List[Dict]:
    """Load all results from results.csv."""
    results = []
    
    if not results_csv.exists():
        print(f"Error: {results_csv} not found")
        return results
    
    with open(results_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                data = json.loads(row['raw_json'])
                results.append({
                    'location': row['location'],
                    'timestamp': row['timestamp'],
                    'data': data
                })
            except json.JSONDecodeError as e:
                print(f"Warning: Failed to parse JSON for {row['location']}: {e}")
                continue
    
    return results


def extract_pillar_data(results: List[Dict], pillar_name: str) -> List[Dict]:
    """Extract detailed data for a specific pillar."""
    pillar_data = []
    
    for result in results:
        pillars = result['data'].get('livability_pillars', {})
        if pillar_name not in pillars:
            continue
        
        pillar_info = pillars[pillar_name]
        location_info = result['data'].get('location_info', {})
        coordinates = result['data'].get('coordinates', {})
        
        entry = {
            'location': result['location'],
            'score': pillar_info.get('score', 0),
            'weight': pillar_info.get('weight', 0),
            'contribution': pillar_info.get('contribution', 0),
            'breakdown': pillar_info.get('breakdown', {}),
            'summary': pillar_info.get('summary', {}),
            'lat': coordinates.get('lat'),
            'lon': coordinates.get('lon'),
            'city': location_info.get('city'),
            'state': location_info.get('state'),
            'area_type': location_info.get('area_type'),
            'location_scope': location_info.get('location_scope'),
            'total_score': result['data'].get('total_score', 0)
        }
        
        pillar_data.append(entry)
    
    return pillar_data


def calculate_distribution_stats(scores: List[float]) -> Dict:
    """Calculate detailed distribution statistics."""
    scores_array = np.array(scores)
    
    return {
        'count': len(scores),
        'mean': float(np.mean(scores_array)),
        'median': float(np.median(scores_array)),
        'std': float(np.std(scores_array)),
        'min': float(np.min(scores_array)),
        'max': float(np.max(scores_array)),
        'q25': float(np.percentile(scores_array, 25)),
        'q75': float(np.percentile(scores_array, 75)),
        'q10': float(np.percentile(scores_array, 10)),
        'q90': float(np.percentile(scores_array, 90)),
        'skewness': float(((scores_array - np.mean(scores_array)) ** 3).mean() / (np.std(scores_array) ** 3)) if np.std(scores_array) > 0 else 0,
        'kurtosis': float(((scores_array - np.mean(scores_array)) ** 4).mean() / (np.std(scores_array) ** 4)) if np.std(scores_array) > 0 else 0
    }


def identify_outliers(pillar_data: List[Dict], z_threshold: float = 2.0) -> Tuple[List[Dict], List[Dict]]:
    """Identify high and low outliers."""
    scores = [d['score'] for d in pillar_data]
    mean = np.mean(scores)
    std = np.std(scores)
    
    if std == 0:
        return [], []
    
    high_outliers = []
    low_outliers = []
    
    for entry in pillar_data:
        z_score = (entry['score'] - mean) / std
        if z_score > z_threshold:
            entry['z_score'] = z_score
            high_outliers.append(entry)
        elif z_score < -z_threshold:
            entry['z_score'] = z_score
            low_outliers.append(entry)
    
    # Sort by absolute z-score
    high_outliers.sort(key=lambda x: abs(x['z_score']), reverse=True)
    low_outliers.sort(key=lambda x: abs(x['z_score']), reverse=True)
    
    return high_outliers, low_outliers


def analyze_by_category(pillar_data: List[Dict]) -> Dict:
    """Analyze scores by location categories."""
    by_area_type = defaultdict(list)
    by_state = defaultdict(list)
    
    for entry in pillar_data:
        if entry.get('area_type'):
            by_area_type[entry['area_type']].append(entry['score'])
        if entry.get('state'):
            by_state[entry['state']].append(entry['score'])
    
    category_stats = {
        'by_area_type': {},
        'by_state': {}
    }
    
    for area_type, scores in by_area_type.items():
        if len(scores) > 1:
            category_stats['by_area_type'][area_type] = {
                'count': len(scores),
                'mean': float(np.mean(scores)),
                'std': float(np.std(scores))
            }
    
    for state, scores in by_state.items():
        if len(scores) > 1:
            category_stats['by_state'][state] = {
                'count': len(scores),
                'mean': float(np.mean(scores)),
                'std': float(np.std(scores))
            }
    
    return category_stats


def generate_tuning_report(pillar_name: str, pillar_data: List[Dict], output_dir: Path):
    """Generate comprehensive tuning report for a pillar."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if not pillar_data:
        print(f"No data found for {pillar_name}")
        return
    
    scores = [d['score'] for d in pillar_data]
    stats = calculate_distribution_stats(scores)
    high_outliers, low_outliers = identify_outliers(pillar_data)
    category_stats = analyze_by_category(pillar_data)
    
    # Generate markdown report
    report_lines = [
        f"# {pillar_name.replace('_', ' ').title()} Tuning Analysis",
        f"\nGenerated from {len(pillar_data)} locations\n",
        "## Distribution Statistics\n",
        f"- **Count**: {stats['count']}",
        f"- **Mean**: {stats['mean']:.2f}",
        f"- **Median**: {stats['median']:.2f}",
        f"- **Std Dev**: {stats['std']:.2f}",
        f"- **Min**: {stats['min']:.2f}",
        f"- **Max**: {stats['max']:.2f}",
        f"- **Q25**: {stats['q25']:.2f}",
        f"- **Q75**: {stats['q75']:.2f}",
        f"- **Q10**: {stats['q10']:.2f}",
        f"- **Q90**: {stats['q90']:.2f}",
        f"- **Skewness**: {stats['skewness']:.2f}",
        f"- **Kurtosis**: {stats['kurtosis']:.2f}",
    ]
    
    # Outliers
    if high_outliers or low_outliers:
        report_lines.append("\n## Outliers\n")
        
        if high_outliers:
            report_lines.append("### High Outliers (Z-score > 2.0)\n")
            for outlier in high_outliers[:10]:
                report_lines.append(f"- **{outlier['location']}**: {outlier['score']:.2f} (z={outlier['z_score']:.2f})")
            report_lines.append("")
        
        if low_outliers:
            report_lines.append("### Low Outliers (Z-score < -2.0)\n")
            for outlier in low_outliers[:10]:
                report_lines.append(f"- **{outlier['location']}**: {outlier['score']:.2f} (z={outlier['z_score']:.2f})")
            report_lines.append("")
    
    # Category analysis
    if category_stats['by_area_type']:
        report_lines.append("## Scores by Area Type\n")
        report_lines.append("| Area Type | Count | Mean | Std Dev |")
        report_lines.append("|-----------|-------|------|---------|")
        for area_type, stat in sorted(category_stats['by_area_type'].items()):
            report_lines.append(f"| {area_type} | {stat['count']} | {stat['mean']:.2f} | {stat['std']:.2f} |")
        report_lines.append("")
    
    # Write report
    report_path = output_dir / f"{pillar_name}_tuning_analysis.md"
    with open(report_path, 'w') as f:
        f.write("\n".join(report_lines))
    
    print(f"Report written to {report_path}")
    
    # Write JSON data
    json_data = {
        'pillar': pillar_name,
        'statistics': stats,
        'high_outliers': [{k: v for k, v in o.items() if k != 'breakdown' and k != 'summary'} for o in high_outliers[:20]],
        'low_outliers': [{k: v for k, v in o.items() if k != 'breakdown' and k != 'summary'} for o in low_outliers[:20]],
        'category_stats': category_stats,
        'location_count': len(pillar_data)
    }
    
    json_path = output_dir / f"{pillar_name}_tuning_data.json"
    with open(json_path, 'w') as f:
        json.dump(json_data, f, indent=2)
    
    print(f"Data written to {json_path}")


def main():
    parser = argparse.ArgumentParser(description='Tune pillars from collected results')
    parser.add_argument('--results-csv', type=Path, default=Path('data/results.csv'),
                       help='Path to results.csv file')
    parser.add_argument('--pillar', type=str, choices=TUNEABLE_PILLARS + ['all'],
                       default='all', help='Pillar to analyze (default: all)')
    parser.add_argument('--output-dir', type=Path, default=Path('analysis'),
                       help='Output directory for reports')
    
    args = parser.parse_args()
    
    # Load results
    results = load_results(args.results_csv)
    
    if not results:
        print("No results found. Run the collector first.")
        sys.exit(1)
    
    print(f"Loaded {len(results)} results")
    
    # Determine which pillars to analyze
    pillars_to_analyze = TUNEABLE_PILLARS if args.pillar == 'all' else [args.pillar]
    
    # Analyze each pillar
    for pillar_name in pillars_to_analyze:
        print(f"\nAnalyzing {pillar_name}...")
        pillar_data = extract_pillar_data(results, pillar_name)
        
        if not pillar_data:
            print(f"  No data found for {pillar_name}")
            continue
        
        generate_tuning_report(pillar_name, pillar_data, args.output_dir)
    
    print("\n✅ Tuning analysis complete!")


if __name__ == "__main__":
    main()
