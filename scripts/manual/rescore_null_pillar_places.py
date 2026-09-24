#!/usr/bin/env python3
"""
Rescore specific pillars for catalog places that have score=None.
Targets only the exact (search_query, pillar) pairs listed in TARGETS.

Usage:
  cd /path/to/home-fit
  export $(grep HOMEFIT_PROXY_SECRET .env)
  PYTHONPATH=. python3 scripts/manual/rescore_null_pillar_places.py
"""
from __future__ import annotations
import json, os, sys, time, copy
from pathlib import Path
import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
BASE_URL = os.environ.get("HOMEFIT_API_URL", "https://home-fit-production.up.railway.app")
SECRET = os.environ.get("HOMEFIT_PROXY_SECRET", "")
HEADERS = {"X-HomeFit-Proxy-Secret": SECRET} if SECRET else {}

# (jsonl_file, search_query, pillar_to_rescore)
TARGETS = [
    # NYC
    ("data/nyc_metro_place_catalog_scores_merged.composites_recomputed.jsonl",
     "Glendale, Queens, New York", "neighborhood_amenities"),
    ("data/nyc_metro_place_catalog_scores_merged.composites_recomputed.jsonl",
     "Hempstead, NY", "community_safety"),
    ("data/nyc_metro_place_catalog_scores_merged.composites_recomputed.jsonl",
     "Pelham Bay, Bronx, New York", "neighborhood_amenities"),
    ("data/nyc_metro_place_catalog_scores_merged.composites_recomputed.jsonl",
     "Sleepy Hollow, NY", "community_safety"),
    ("data/nyc_metro_place_catalog_scores_merged.composites_recomputed.jsonl",
     "Summit, NJ", "community_safety"),
    # LA
    ("data/la_metro_place_catalog_scores_merged.composites_recomputed.jsonl",
     "East Los Angeles, California", "community_safety"),
    ("data/la_metro_place_catalog_scores_merged.composites_recomputed.jsonl",
     "Lakewood, California", "community_safety"),
    ("data/la_metro_place_catalog_scores_merged.composites_recomputed.jsonl",
     "Palos Verdes Estates, California", "community_safety"),
    ("data/la_metro_place_catalog_scores_merged.composites_recomputed.jsonl",
     "Rancho Palos Verdes, California", "neighborhood_amenities"),
    # SF
    ("data/sf_metro_place_catalog_scores_merged.composites_recomputed.jsonl",
     "Los Altos Hills, California", "neighborhood_amenities"),
]

DELAY = 3  # seconds between API calls


def fetch_pillar(location: str, pillar: str) -> dict:
    url = f"{BASE_URL}/score"
    params = {"location": location, "only": pillar, "enable_schools": "false"}
    r = requests.get(url, params=params, headers=HEADERS, timeout=300)
    r.raise_for_status()
    return r.json()


def merge_pillar(stored_score: dict, new_score: dict, pillar: str) -> None:
    new_lp = (new_score.get("livability_pillars") or {}).get(pillar)
    if new_lp is None:
        raise ValueError(f"New score missing pillar {pillar}")
    stored_lp = stored_score.setdefault("livability_pillars", {})
    # Preserve the stored weight — only update score, confidence, data_quality, details.
    stored_w = (stored_lp.get(pillar) or {}).get("weight")
    stored_lp[pillar] = new_lp
    if isinstance(stored_w, (int, float)) and not isinstance(new_lp.get("weight"), (int, float)):
        stored_lp[pillar]["weight"] = stored_w


def process_file(path: Path, updates: list[tuple[str, str]]) -> int:
    records = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    sq_pillar = {sq: pillar for sq, pillar in updates}
    updated = 0
    for rec in records:
        sq = (rec.get("catalog") or {}).get("search_query", "")
        if sq not in sq_pillar:
            continue
        pillar = sq_pillar[sq]
        name = (rec.get("catalog") or {}).get("name", sq)
        existing_score = ((rec.get("score") or {}).get("livability_pillars") or {}).get(pillar, {})
        if isinstance(existing_score.get("score"), (int, float)):
            print(f"  SKIP {name} — {pillar} already has score={existing_score['score']}")
            continue
        print(f"  Rescoring {name} → {pillar} ...", flush=True)
        try:
            new_score = fetch_pillar(sq, pillar)
            lp = new_score.get("livability_pillars") or {}
            pdata = lp.get(pillar) or {}
            pillar_score = pdata.get("score")
            if not isinstance(pillar_score, (int, float)):
                reason = (pdata.get("data_quality") or {}).get("reason") or pdata.get("error") or "no_data"
                print(f"  SKIP {name}: {pillar} still no score — {reason}")
                continue
            merge_pillar(rec["score"], new_score, pillar)
            pdata = (rec["score"].get("livability_pillars") or {}).get(pillar) or {}
            print(f"  DONE {name}: {pillar} score={pdata.get('score')}")
            updated += 1
        except Exception as e:
            print(f"  FAIL {name}: {e}")
        time.sleep(DELAY)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n")
    if updated:
        import subprocess
        print(f"  Recomputing composites for {path.name} ...")
        subprocess.run(
            ["python3", "scripts/catalog/recompute_catalog_composites.py",
             "--input", str(path), "--in-place", "--no-census", "--no-backup"],
            check=True, env={**os.environ, "PYTHONPATH": "."},
        )
    return updated


def main() -> None:
    by_file: dict[str, list[tuple[str, str]]] = {}
    for jsonl, sq, pillar in TARGETS:
        by_file.setdefault(jsonl, []).append((sq, pillar))

    total = 0
    for jsonl, updates in by_file.items():
        path = REPO_ROOT / jsonl
        print(f"\n=== {path.name} ({len(updates)} targets) ===")
        total += process_file(path, updates)
    print(f"\nDone — {total} pillars updated")


if __name__ == "__main__":
    main()
