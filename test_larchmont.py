#!/usr/bin/env python3
"""
Test Larchmont, NY with custom token allocation.
Uses cached school data when available.
"""

import sys
import json
from main import get_livability_score

# Custom token allocation
token_allocation = {
    "housing_value": 4,
    "quality_education": 4,
    "neighborhood_beauty": 4,
    "active_outdoors": 2,
    "neighborhood_amenities": 2,
    "public_transit_access": 2,
    "healthcare_access": 1,
    "air_travel_access": 1
}

# Convert to tokens string format
tokens_parts = [f"{k}:{v}" for k, v in token_allocation.items()]
tokens_str = ",".join(tokens_parts)

print("=" * 70)
print("Testing Larchmont, NY with Custom Token Allocation")
print("=" * 70)
print(f"\nToken Allocation:")
for pillar, tokens in token_allocation.items():
    print(f"  {pillar}: {tokens}")
print(f"\nTotal: {sum(token_allocation.values())} tokens")
print("\n" + "=" * 70 + "\n")

# Call the scoring function
try:
    result = get_livability_score(
        location="Larchmont, NY",
        tokens=tokens_str,
        include_chains=False,
        beauty_weights=None  # Default 50/50
    )
    
    # Print summary
    print("\n" + "=" * 70)
    print("SCORING RESULTS")
    print("=" * 70)
    
    print(f"\n📍 Location: {result['location_info']['city']}, {result['location_info']['state']}")
    print(f"   Coordinates: {result['coordinates']['lat']:.6f}, {result['coordinates']['lon']:.6f}")
    print(f"   ZIP: {result['location_info']['zip']}")
    
    print(f"\n🏆 Total Score: {result['total_score']:.1f}/100")
    
    print(f"\n📊 Pillar Breakdown:")
    pillars = result['livability_pillars']
    
    for pillar_name, pillar_data in pillars.items():
        score = pillar_data['score']
        weight = pillar_data.get('weight', 0)
        contribution = pillar_data.get('contribution', 0)
        print(f"\n  {pillar_name.replace('_', ' ').title()}:")
        print(f"    Score: {score:.1f}/100")
        print(f"    Weight: {weight:.2f}")
        print(f"    Contribution: {contribution:.2f}")
    
    # Save full result
    output_file = "larchmont_score.json"
    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2)
    print(f"\n✅ Full results saved to {output_file}")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

