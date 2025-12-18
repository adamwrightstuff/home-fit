#!/usr/bin/env python3
"""
Pillar Regression Analysis

Analyzes collected HomeFit API results to perform regression analysis for each pillar.
Extracts pillar scores from results.csv and generates statistical insights.

Usage:
    python scripts/analyze_pillar_regression.py [--output-dir analysis/]
"""

import csv
import json
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict
import numpy as np

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Pillar names (from main.py)
PILLAR_NAMES = [
    "active_outdoors",
    "built_beauty",
    "natural_beauty",
    "neighborhood_amenities",
    "air_travel_access",
    "public_transit_access",
    "healthcare_access",
    "quality_education",
    "housing_value"
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
    
    print(f"Loaded {len(results)} results from {results_csv}")
    return results


def extract_pillar_scores(results: List[Dict]) -> Dict[str, List[float]]:
    """Extract pillar scores from all results."""
    pillar_scores = {pillar: [] for pillar in PILLAR_NAMES}
    location_data = []
    
    for result in results:
        pillars = result['data'].get('livability_pillars', {})
        location_info = {
            'location': result['location'],
            'total_score': result['data'].get('total_score', 0),
            'coordinates': result['data'].get('coordinates', {}),
            'location_info': result['data'].get('location_info', {})
        }
        
        for pillar_name in PILLAR_NAMES:
            if pillar_name in pillars:
                score = pillars[pillar_name].get('score', 0)
                pillar_scores[pillar_name].append(score)
                location_info[f'{pillar_name}_score'] = score
            else:
                pillar_scores[pillar_name].append(None)
                location_info[f'{pillar_name}_score'] = None
        
        location_data.append(location_info)
    
    return pillar_scores, location_data


def calculate_statistics(scores: List[float]) -> Dict:
    """Calculate basic statistics for a list of scores."""
    # Filter out None values
    valid_scores = [s for s in scores if s is not None]
    
    if not valid_scores:
        return {
            'count': 0,
            'mean': None,
            'std': None,
            'min': None,
            'max': None,
            'median': None,
            'q25': None,
            'q75': None
        }
    
    arr = np.array(valid_scores)
    
    return {
        'count': len(valid_scores),
        'mean': float(np.mean(arr)),
        'std': float(np.std(arr)),
        'min': float(np.min(arr)),
        'max': float(np.max(arr)),
        'median': float(np.median(arr)),
        'q25': float(np.percentile(arr, 25)),
        'q75': float(np.percentile(arr, 75))
    }


def calculate_correlations(location_data: List[Dict]) -> Dict[str, Dict[str, float]]:
    """Calculate correlations between pillars."""
    correlations = {}
    
    # Build arrays for each pillar
    pillar_arrays = {}
    for pillar in PILLAR_NAMES:
        scores = [loc.get(f'{pillar}_score') for loc in location_data]
        valid_scores = [s for s in scores if s is not None]
        if len(valid_scores) > 1:
            pillar_arrays[pillar] = np.array(valid_scores)
    
    # Calculate pairwise correlations
    for pillar1 in PILLAR_NAMES:
        if pillar1 not in pillar_arrays:
            continue
        correlations[pillar1] = {}
        for pillar2 in PILLAR_NAMES:
            if pillar2 not in pillar_arrays:
                correlations[pillar1][pillar2] = None
                continue
            
            # Align arrays (only locations with both scores)
            aligned_scores1 = []
            aligned_scores2 = []
            for loc in location_data:
                s1 = loc.get(f'{pillar1}_score')
                s2 = loc.get(f'{pillar2}_score')
                if s1 is not None and s2 is not None:
                    aligned_scores1.append(s1)
                    aligned_scores2.append(s2)
            
            if len(aligned_scores1) > 1:
                corr = np.corrcoef(aligned_scores1, aligned_scores2)[0, 1]
                correlations[pillar1][pillar2] = float(corr) if not np.isnan(corr) else None
            else:
                correlations[pillar1][pillar2] = None
    
    return correlations


def identify_outliers(scores: List[float], pillar_name: str, threshold: float = 2.0) -> List[tuple]:
    """Identify outliers using z-score method."""
    valid_scores = [(i, s) for i, s in enumerate(scores) if s is not None]
    
    if len(valid_scores) < 3:
        return []
    
    score_values = [s for _, s in valid_scores]
    mean = np.mean(score_values)
    std = np.std(score_values)
    
    if std == 0:
        return []
    
    outliers = []
    for idx, score in valid_scores:
        z_score = abs((score - mean) / std)
        if z_score > threshold:
            outliers.append((idx, score, z_score))
    
    return outliers


def generate_report(pillar_scores: Dict[str, List[float]], 
                   location_data: List[Dict],
                   output_dir: Path):
    """Generate comprehensive regression analysis report."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Statistics for each pillar
    pillar_stats = {}
    for pillar in PILLAR_NAMES:
        stats = calculate_statistics(pillar_scores[pillar])
        pillar_stats[pillar] = stats
    
    # Correlations
    correlations = calculate_correlations(location_data)
    
    # Generate summary report
    report_lines = [
        "# Pillar Regression Analysis Report",
        f"Generated from {len(location_data)} locations\n",
        "## Summary Statistics by Pillar\n"
    ]
    
    for pillar in PILLAR_NAMES:
        stats = pillar_stats[pillar]
        report_lines.append(f"### {pillar.replace('_', ' ').title()}")
        report_lines.append(f"- Count: {stats['count']}")
        if stats['mean'] is not None:
            report_lines.append(f"- Mean: {stats['mean']:.2f}")
            report_lines.append(f"- Std Dev: {stats['std']:.2f}")
            report_lines.append(f"- Min: {stats['min']:.2f}")
            report_lines.append(f"- Max: {stats['max']:.2f}")
            report_lines.append(f"- Median: {stats['median']:.2f}")
            report_lines.append(f"- Q25: {stats['q25']:.2f}")
            report_lines.append(f"- Q75: {stats['q75']:.2f}")
        report_lines.append("")
    
    # Correlation matrix
    report_lines.append("## Pillar Correlations\n")
    report_lines.append("| Pillar | " + " | ".join([p.replace('_', ' ').title()[:15] for p in PILLAR_NAMES]) + " |")
    report_lines.append("|" + "|".join(["---"] * (len(PILLAR_NAMES) + 1)) + "|")
    
    for pillar1 in PILLAR_NAMES:
        row = [pillar1.replace('_', ' ').title()[:15]]
        for pillar2 in PILLAR_NAMES:
            corr = correlations.get(pillar1, {}).get(pillar2)
            if corr is None:
                row.append("—")
            else:
                row.append(f"{corr:.2f}")
        report_lines.append("| " + " | ".join(row) + " |")
    
    # Outliers
    report_lines.append("\n## Outliers (Z-score > 2.0)\n")
    for pillar in PILLAR_NAMES:
        outliers = identify_outliers(pillar_scores[pillar], pillar)
        if outliers:
            report_lines.append(f"### {pillar.replace('_', ' ').title()}")
            for idx, score, z_score in outliers[:10]:  # Limit to top 10
                location = location_data[idx]['location']
                report_lines.append(f"- {location}: {score:.2f} (z={z_score:.2f})")
            report_lines.append("")
    
    # Write report
    report_path = output_dir / "pillar_regression_analysis.md"
    with open(report_path, 'w') as f:
        f.write("\n".join(report_lines))
    
    print(f"Report written to {report_path}")
    
    # Write JSON data for further analysis
    json_data = {
        'statistics': pillar_stats,
        'correlations': correlations,
        'location_count': len(location_data)
    }
    
    json_path = output_dir / "pillar_regression_data.json"
    with open(json_path, 'w') as f:
        json.dump(json_data, f, indent=2)
    
    print(f"Data written to {json_path}")


def main():
    parser = argparse.ArgumentParser(description='Analyze pillar regression from collected results')
    parser.add_argument('--results-csv', type=Path, default=Path('data/results.csv'),
                       help='Path to results.csv file')
    parser.add_argument('--output-dir', type=Path, default=Path('analysis'),
                       help='Output directory for reports')
    
    args = parser.parse_args()
    
    # Load results
    results = load_results(args.results_csv)
    
    if not results:
        print("No results found. Run the collector first.")
        sys.exit(1)
    
    # Extract pillar scores
    pillar_scores, location_data = extract_pillar_scores(results)
    
    # Generate report
    generate_report(pillar_scores, location_data, args.output_dir)
    
    print("\n✅ Regression analysis complete!")


if __name__ == "__main__":
    main()
