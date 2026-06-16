#!/usr/bin/env python3
"""Backfill political_lean for LA catalog (was entirely absent — no ca_precincts.json existed
until now). Mirrors the NYC structure: score=None, weight 0 (it's a filter), breakdown carries
lean_2024/lean_2020/trend for the Explorer's progressive/conservative filter."""
import json, os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pillars.political_lean import get_political_lean_score

fn = "data/la_metro_place_catalog_scores_merged.jsonl"
shutil.copyfile(fn, fn + ".bakPol")
tmp = fn + ".new"
added = skipped = 0
with open(fn) as src, open(tmp, "w") as out:
    for line in src:
        r = json.loads(line)
        lp = r["score"]["livability_pillars"]
        if lp.get("political_lean") is None:
            cat = r["catalog"]
            score, det = get_political_lean_score(float(cat["lat"]), float(cat["lon"]), "CA")
            bd = det.get("breakdown")
            if bd:
                lp["political_lean"] = {
                    "score": None, "weight": 0.0, "contribution": 0.0,
                    "breakdown": bd, "data_quality": det.get("data_quality", {"confidence": 1.0}),
                    "_rescore_version": "la_political_backfill",
                }
                added += 1
            else:
                skipped += 1
                print(f"   skip {cat.get('name')}: {det.get('error')}", flush=True)
        out.write(json.dumps(r) + "\n")
os.replace(tmp, fn)
print(f"added political_lean to {added} LA places ({skipped} skipped). backup: {fn}.bakPol")
