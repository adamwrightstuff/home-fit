#!/usr/bin/env python3
"""
Offline: add `local_scene_v2` to each catalog place (score.local_scene_v2) from the brand-tag venue re-read
(scripts/catalog/reread_brand_tags.py output). No API calls. Also writes score.local_scene_score (0-100 from the independent
venue count) and removes the retired name-guessing fields (local_scene_breakdown, local_scene_bucket_v1). The Aura flag is untouched. Radius per place is the one its stored business list used (1,200 m when the farthest stored listing is
within 1,210 m, else 1,500 m).

  python3 scripts/catalog/add_local_scene_v2_offline.py --reads <local_scene_brand_reads.jsonl>
"""
import argparse, glob, json, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from pillars import local_scene_v2 as ls  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reads", required=True)
    ap.add_argument("--boundary-reads", default=None, help="local_scene_boundary_reads.jsonl: towns use venues inside their boundary")
    a = ap.parse_args()
    reads = {}
    for line in open(a.reads, encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            reads[r["key"]] = r
    STATE_FIPS = {"AZ": "04", "CA": "06", "CO": "08", "CT": "09", "DE": "10", "FL": "12", "GA": "13", "IL": "17", "IN": "18", "MA": "25",
                  "MD": "24", "NC": "37", "NJ": "34", "NV": "32", "NY": "36", "PA": "42", "TX": "48", "WA": "53"}
    boundary = {}
    if a.boundary_reads:
        for line in open(a.boundary_reads, encoding="utf-8"):
            if line.strip():
                r = json.loads(line)
                boundary[r["key"]] = r
    files = {}
    refs = []  # (path, row index, facts)
    for path in sorted(glob.glob(str(REPO / "data" / "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))):
        rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
        files[path] = rows
        for i, r in enumerate(rows):
            s = r.get("score") if r.get("success") else None
            if not isinstance(s, dict):
                continue
            c = r["catalog"]
            key = f"{float(c['lat']):.5f},{float(c['lon']):.5f}"
            bl = ((((s.get("livability_pillars") or {}).get("neighborhood_amenities") or {}).get("breakdown")) or {}).get("business_list") or []
            mx = max((b["distance_m"] for b in bl if b.get("distance_m") is not None), default=None)
            radius = 1200 if (mx is not None and mx <= 1210) else 1500
            read = reads.get(key)
            metro = Path(path).name.split("_metro_")[0]
            bkey = f"{metro}|{c['name']}|{STATE_FIPS.get(c.get('state_abbr'))}"
            if bkey in boundary:
                facts = ls.boundary_facts(boundary[bkey]["venues"], boundary[bkey]["area_km2"])
            else:
                facts = ls.place_facts(read["venues"] if read else [], radius)
            facts["independent_venues_1200m"] = ls.independent_venue_count(read["venues"]) if read else None
            facts["bucket"] = ls.activity_bucket(facts["independent_venues_1200m"])
            apa = (((s.get("livability_pillars") or {}).get("active_outdoors") or {}).get("dpv2_recompute") or {}).get("activity_per_acre")
            facts["activity_per_acre"] = round(apa, 2) if isinstance(apa, (int, float)) else None
            refs.append((path, i, facts, read is not None))
    ls.apply_reading([f for _, _, f, _ in refs], [f["activity_per_acre"] for _, _, f, _ in refs])  # mix facts: combined, density band, lively
    n = lively = nodata = 0
    for path, i, facts, had_read in refs:
        sc = files[path][i]["score"]
        sc["local_scene_v2"] = facts
        # the Explorer chip, filter and place card read local_scene_bucket: it now carries the v2 tier (None = too few venues or no density)
        sc["local_scene_bucket"] = facts["bucket"]
        sc["local_scene_score"] = ls.scene_score(facts["independent_venues_1200m"])
        sc.pop("local_scene_breakdown", None)
        sc.pop("local_scene_bucket_v1", None)
        n += 1
        lively += facts["lively"]
        nodata += (facts["venues_total"] == 0)
    for path, rows in files.items():
        Path(path).write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    print(f"local_scene_v2 added for {n} places: lively {lively}, no venue data {nodata}")


if __name__ == "__main__":
    main()
