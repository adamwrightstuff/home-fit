#!/usr/bin/env python3
"""
Monitor calibration results and update code when ready.
This script checks if calibration is complete and updates the calibration parameters.
"""

import sys
import json
import time
from pathlib import Path

project_root = Path(__file__).parent.parent
calibration_file = project_root / "analysis" / "active_outdoors_calibration_round11.json"
active_outdoors_file = project_root / "pillars" / "active_outdoors.py"


def check_and_update():
    """Check if calibration is complete and update code."""
    if not calibration_file.exists():
        print("⏳ Calibration file not found yet. Still processing...")
        return False
    
    print(f"✅ Calibration file found! Reading results...")
    
    # Read calibration results
    with open(calibration_file, "r") as f:
        data = json.load(f)
    
    cal_data = data["calibration"]
    CAL_A = cal_data["CAL_A"]
    CAL_B = cal_data["CAL_B"]
    stats = cal_data["stats"]
    
    print(f"\n📊 Calibration Results:")
    print(f"   CAL_A: {CAL_A:.6f}")
    print(f"   CAL_B: {CAL_B:.6f}")
    print(f"   Mean Absolute Error: {stats['mean_abs_error']:.2f}")
    print(f"   Max Absolute Error: {stats['max_abs_error']:.2f}")
    print(f"   R²: {stats['r_squared']:.4f}")
    print(f"   Samples: {stats['n_samples']}")
    
    # Read current code
    with open(active_outdoors_file, "r") as f:
        code = f.read()
    
    # Update calibration parameters
    # Find the CAL_A and CAL_B assignment lines
    old_pattern_a = "CAL_A = 1.768"
    old_pattern_b = "CAL_B = 36.202"
    
    new_line_a = f"    CAL_A = {CAL_A:.6f}"
    new_line_b = f"    CAL_B = {CAL_B:.6f}"
    
    # Update the code
    updated = False
    lines = code.split("\n")
    new_lines = []
    
    for i, line in enumerate(lines):
        if "CAL_A = " in line and "CAL_A = 1.768" not in line and "#" not in line:
            # Skip if it's already been updated
            new_lines.append(line)
        elif "CAL_A = 1.768" in line:
            new_lines.append(new_line_a)
            updated = True
        elif "CAL_B = 36.202" in line and "CAL_A" not in line:
            new_lines.append(new_line_b)
            updated = True
        else:
            new_lines.append(line)
    
    if updated:
        # Write updated code
        with open(active_outdoors_file, "w") as f:
            f.write("\n".join(new_lines))
        
        print(f"\n✅ Updated calibration parameters in {active_outdoors_file}")
        print(f"   CAL_A: {old_pattern_a} → {new_line_a.strip()}")
        print(f"   CAL_B: {old_pattern_b} → {new_line_b.strip()}")
        return True
    else:
        print("\n⚠️  Could not find calibration parameter lines to update")
        return False


def main():
    """Main monitoring loop."""
    print("🔍 Checking for calibration results...")
    print(f"   Looking for: {calibration_file}")
    print()
    
    if check_and_update():
        print("\n✅ Calibration update complete!")
        sys.exit(0)
    else:
        print("\n⏳ Calibration not complete yet.")
        sys.exit(1)


if __name__ == "__main__":
    main()

