#!/usr/bin/env python3
"""Get Redondo Beach, CA scores with user priorities"""

import json
import requests

url = 'https://home-fit-production.up.railway.app/score'

priorities = {
    'housing_value': 'High',
    'built_beauty': 'High',
    'neighborhood_amenities': 'High',
    'quality_education': 'High',
    'public_transit_access': 'Medium',
    'natural_beauty': 'Medium',
    'healthcare_access': 'Low',
    'air_travel_access': 'Low',
    'active_outdoors': 'Low'
}

# Calculate token allocation manually
priority_weights = {'none': 0, 'low': 1, 'medium': 2, 'high': 3}
primary_pillars = [
    'housing_value', 'built_beauty', 'neighborhood_amenities', 'quality_education',
    'public_transit_access', 'natural_beauty', 'healthcare_access',
    'air_travel_access', 'active_outdoors'
]

weight_dict = {}
total_weight = 0.0
for pillar in primary_pillars:
    priority_str = priorities.get(pillar, "none").lower().strip()
    weight = priority_weights.get(priority_str, 0)
    weight_dict[pillar] = weight
    total_weight += weight

token_dict = {}
fractional_parts = []
for pillar in primary_pillars:
    weight = weight_dict[pillar]
    if weight > 0:
        proportional = (weight / total_weight) * 100.0
        token_dict[pillar] = proportional
        fractional_parts.append((pillar, proportional - int(proportional)))
    else:
        token_dict[pillar] = 0.0

rounded_tokens = {pillar: int(tokens) for pillar, tokens in token_dict.items()}
total_rounded = sum(rounded_tokens.values())
remainder = 100 - total_rounded

if remainder > 0:
    fractional_parts.sort(key=lambda x: x[1], reverse=True)
    for i in range(remainder):
        pillar = fractional_parts[i][0]
        rounded_tokens[pillar] += 1

token_allocation = {pillar: float(rounded_tokens.get(pillar, 0)) for pillar in primary_pillars}

params = {
    'location': 'Redondo Beach, CA',
    'priorities': json.dumps(priorities)
}

print("Fetching Redondo Beach, CA scores with your priorities...")
print("=" * 80)

response = requests.get(url, params=params, timeout=300)
data = response.json()

pillars = data.get('livability_pillars', {})
overall_confidence = data.get('overall_confidence', {})

# Calculate weighted score
total_weighted = 0
print(f"\n{'Pillar':<35} {'Score':<12} {'Tokens':<10} {'Weighted':<12}")
print("-" * 80)

for pillar_name in primary_pillars:
    pillar_data = pillars.get(pillar_name, {})
    score = pillar_data.get('score', 0)
    tokens = token_allocation.get(pillar_name, 0)
    weighted = score * (tokens / 100.0)
    total_weighted += weighted
    
    priority = priorities.get(pillar_name, 'None')
    pillar_display = f"{pillar_name.replace('_', ' ').title()} ({priority})"
    
    print(f"{pillar_display:<35} {score:>6.1f}/100    {tokens:>6.1f}     {weighted:>6.1f}")

print("-" * 80)
print(f"{'TOTAL':<35} {'':<12} {'100.0':<10} {total_weighted:>6.1f}")
print("=" * 80)

print(f"\n🎯 OVERALL WEIGHTED SCORE: {total_weighted:.1f}/100")
print(f"\nData Quality:")
print(f"  Average Confidence: {overall_confidence.get('average_confidence', 0):.1f}%")
print(f"  Fallback Usage: {overall_confidence.get('fallback_percentage', 0):.1f}%")
print(f"  Quality Tiers: {overall_confidence.get('quality_tier_distribution', {})}")
