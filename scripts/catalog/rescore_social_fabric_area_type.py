#!/usr/bin/env python3
"""
Rescore social_fabric for all catalog places using the corrected effective_area_type
from neighborhood_beauty breakdown (already patched to use classify_morphology).

Usage:
    PYTHONPATH=. python3 scripts/catalog/rescore_social_fabric_area_type.py
"""
import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pillars.social_fabric import get_social_fabric_score

CATALOGS = [
    Path("data/nyc_metro_place_catalog_scores_merged.jsonl"),
    Path("data/la_metro_place_catalog_scores_merged.jsonl"),
]


def process(path: Path):
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    updated = errors = skipped = 0

    for i, row in enumerate(rows, 1):
        score = row.get("score", {})
        coords = score.get("coordinates", {})
        lat, lon = coords.get("lat"), coords.get("lon")
        if not lat or not lon:
            skipped += 1
            continue

        loc_info = score.get("location_info", {})
        nb = score.get("livability_pillars", {}).get("neighborhood_beauty", {})
        area_type = nb.get("breakdown", {}).get("effective_area_type")
        density = nb.get("breakdown", {}).get("density")
        zip_code = loc_info.get("zip")
        name = row.get("catalog", {}).get("name", "?")

        try:
            new_score, new_details = get_social_fabric_score(
                lat, lon,
                area_type=area_type,
                density=density,
                zip_code=zip_code,
            )
            if new_score is not None:
                row["score"]["livability_pillars"]["social_fabric"] = {
                    **new_details,
                    "score": round(float(new_score), 2),
                    "status": "success",
                }
                updated += 1
            else:
                skipped += 1
        except Exception as e:
            print(f"  ERROR {name}: {e}")
            errors += 1

        if i % 20 == 0:
            print(f"  [{i}/{len(rows)}] {name} — score={new_score}")

    bak = path.with_suffix(path.suffix + f".bak.sf.{int(time.time())}")
    shutil.copy2(path, bak)
    path.write_text("\n".join(json.dumps(r, separators=(',', ':')) for r in rows) + "\n")
    print(f"{path.name}: updated={updated} skipped={skipped} errors={errors}")


for catalog in CATALOGS:
    print(f"\n=== {catalog.name} ===")
    process(catalog)
