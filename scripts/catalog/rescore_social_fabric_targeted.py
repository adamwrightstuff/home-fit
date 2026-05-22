"""
Targeted social_fabric rescore for catalog entries with known data issues:
  - old_engagement: participation_mix still on no_turn_60_40_bmf_vol (pre-50/50 change)
  - civic_zero_non_rural: civic_node_count=0 for non-rural locations (OSM failure)

Usage:
    python scripts/catalog/rescore_social_fabric_targeted.py [--dry-run]
    python scripts/catalog/rescore_social_fabric_targeted.py --metro nyc
    python scripts/catalog/rescore_social_fabric_targeted.py --metro la
"""

import argparse
import json
import os
import sys
import time
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from pillars.social_fabric import get_social_fabric_score

CATALOGS = {
    "nyc": "data/nyc_metro_place_catalog_scores_merged.jsonl",
    "la":  "data/la_metro_place_catalog_scores_merged.jsonl",
}


def needs_rescore(sf: dict) -> tuple[bool, list[str]]:
    sm = sf.get("summary", {})
    ac = sf.get("area_classification", {})
    mix = sm.get("participation_mix", "")
    civic_n = sm.get("civic_node_count", 0)
    area_type = ac.get("area_type", "")
    flags = []
    if mix == "no_turn_60_40_bmf_vol":
        flags.append("old_engagement")
    if civic_n == 0 and area_type not in ("rural", "exurban"):
        flags.append("civic_zero_non_rural")
    return bool(flags), flags


def process_catalog(path: str, dry_run: bool) -> list:
    entries = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))

    ok = skip = err = 0

    for i, entry in enumerate(entries):
        name = entry.get("catalog", {}).get("name", f"entry_{i}")
        s = entry.get("score", {})
        coords = s.get("coordinates", {})
        lat = coords.get("lat")
        lon = coords.get("lon")
        sf = s.get("livability_pillars", {}).get("social_fabric")

        if not sf or not lat or not lon:
            skip += 1
            continue

        flagged, flags = needs_rescore(sf)
        if not flagged:
            skip += 1
            continue

        loc_info = s.get("location_info", {})
        city = loc_info.get("city")
        zip_code = loc_info.get("zip")
        area_type = sf.get("area_classification", {}).get("area_type")
        density = sf.get("summary", {}).get("tract_population_density_sqmi")

        old_score = sf.get("score")
        old_stability = sf.get("breakdown", {}).get("stability")
        old_civic = sf.get("breakdown", {}).get("civic_gathering")
        old_engagement = sf.get("breakdown", {}).get("engagement")

        print(f"  [{name}] flags={flags}  old={old_score}")

        if dry_run:
            ok += 1
            continue

        try:
            new_score, new_details = get_social_fabric_score(
                lat, lon,
                area_type=area_type,
                density=density,
                city=city,
                zip_code=zip_code,
            )
        except Exception as e:
            print(f"    ERROR: {e}")
            err += 1
            continue

        new_bk = new_details.get("breakdown", {})
        print(
            f"    → score {old_score}→{new_score}  "
            f"stability {old_stability:.1f}→{new_bk.get('stability', 0):.1f}  "
            f"civic {old_civic:.1f}→{new_bk.get('civic_gathering', 0):.1f}  "
            f"engagement {old_engagement:.1f}→{new_bk.get('engagement', 0):.1f}"
        )

        # Merge new social_fabric result back into entry
        entry["score"]["livability_pillars"]["social_fabric"] = {
            "score": new_score,
            "weight": sf.get("weight"),
            "importance_level": sf.get("importance_level"),
            "contribution": round(new_score * (sf.get("weight") or 0) / 100, 2),
            "breakdown": new_details.get("breakdown", {}),
            "summary": new_details.get("summary", {}),
            "confidence": new_details.get("data_quality", {}).get("confidence"),
            "data_quality": new_details.get("data_quality", {}),
            "area_classification": new_details.get("area_classification", {}),
            "source_status": new_details.get("source_status", {}),
            "source_errors": new_details.get("source_errors", []),
            "status": "success",
        }
        ok += 1
        time.sleep(0.2)

    print(f"\n  rescored={ok}  skipped={skip}  errors={err}")
    return entries


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--metro", choices=["nyc", "la"], default=None)
    args = parser.parse_args()

    metros = [args.metro] if args.metro else list(CATALOGS.keys())

    for metro in metros:
        path = CATALOGS[metro]
        print(f"\n=== {metro.upper()} ({path}) ===")
        entries = process_catalog(path, args.dry_run)

        if not args.dry_run:
            ts = time.strftime("%Y%m%d-%H%M%S")
            shutil.copy(path, f"{path}.bak.{ts}")
            with open(path, "w") as f:
                for entry in entries:
                    f.write(json.dumps(entry, separators=(",", ":")) + "\n")
            print(f"  Wrote {len(entries)} lines to {path}")


if __name__ == "__main__":
    main()
