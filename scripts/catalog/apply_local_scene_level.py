#!/usr/bin/env python3
"""
Offline: write the Local Scene ladder level from each place's stored score.local_scene_v2 facts. No API calls.

  score.local_scene_level   the ladder level the Explorer shows (quiet / low_key / lively / buzzing, None = no data)
and removes the retired fields: local_scene_score, local_scene_breakdown, local_scene_bucket, local_scene_bucket_v1 and the
v2 lively flag and bucket. Places with no venue data get level None (never Quiet).

  python3 scripts/catalog/apply_local_scene_level.py            # dry run
  python3 scripts/catalog/apply_local_scene_level.py --write
"""
import argparse, glob, json, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from pillars import local_scene_v2 as ls  # noqa: E402

_peers = None


def _load_peers():
    """Pin-circle places with a mix reading, for ranking a fallback place against its density band."""
    global _peers
    if _peers is not None:
        return _peers
    out = []
    for path in glob.glob(str(REPO / "data" / "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl")):
        for line in open(path, encoding="utf-8"):
            if not line.strip():
                continue
            d = json.loads(line)
            v = (d.get("score") or {}).get("local_scene_v2") if d.get("success") else None
            if isinstance(v, dict) and v.get("geography") == "pin_circle" and not v.get("measured_by_fallback") and v.get("combined") is not None and v.get("density_band") and v.get("activity_per_acre") is not None and v.get("culture_share") is not None:
                out.append((v["density_band"], v["activity_per_acre"], v["culture_share"], v["hangout_share"]))
    _peers = out
    return out


def _band_for(activity, peers):
    edges = {}
    for b, a, _, _ in peers:
        edges[b] = max(edges.get(b, a), a)
    for b in sorted(edges):
        if activity <= edges[b]:
            return b
    return max(edges) if edges else None


def fallback_pin_circle(s):
    """A town whose boundary held no named venue but whose pin circle did: measure the pin circle from the stored business list.
    The list has no brand tags, so culture venues are not filtered to independent ones (an approximation; a full rebuild from the
    brand reads replaces it). Ranked against the pin-circle places of the same density band without changing any of them."""
    v2 = s.get("local_scene_v2")
    if not isinstance(v2, dict) or v2.get("geography") != "town_boundary" or v2.get("venues_total") != 0 or not (v2.get("independent_venues_1200m") or 0) > 0:
        return False
    bl = ((((s.get("livability_pillars") or {}).get("neighborhood_amenities") or {}).get("breakdown")) or {}).get("business_list") or []
    mx = max((b["distance_m"] for b in bl if b.get("distance_m") is not None), default=None)
    radius = 1200 if (mx is not None and mx <= 1210) else 1500
    pin = ls.place_facts(bl, radius)
    if pin["venues_total"] == 0:
        return False
    v2.update({k: pin[k] for k in ("venues_total", "culture_venues", "culture_share", "hangout_share", "hangouts_5min", "radius_m", "few_venues")})
    v2["geography"] = "pin_circle"
    v2.pop("cafes_bars_in_town", None)
    v2["measured_by_fallback"] = True
    v2["combined"], v2["density_band"] = None, None
    apa = v2.get("activity_per_acre")
    peers = _load_peers()
    if apa is not None and peers and pin["culture_share"] is not None:
        band = _band_for(apa, peers)
        same = [p for p in peers if p[0] == band]
        cs = ls.percentile_ranks([p[2] for p in same] + [pin["culture_share"]])[-1]
        hs = ls.percentile_ranks([p[3] for p in same] + [pin["hangout_share"]])[-1]
        v2["combined"], v2["density_band"] = round((cs + hs) / 2, 1), band
    return True


def process(path, write=True):
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    changed = 0
    fallbacks = []
    for r in rows:
        s = r.get("score") if r.get("success") else None
        if not isinstance(s, dict):
            continue
        if fallback_pin_circle(s):
            fallbacks.append(r["catalog"]["name"])
        v2 = s.get("local_scene_v2")
        s["local_scene_level"] = ls.scene_level(v2) if isinstance(v2, dict) else None
        s.pop("local_scene_bucket", None)
        s.pop("local_scene_score", None)
        if isinstance(v2, dict):
            v2.pop("lively", None)
            v2.pop("bucket", None)
        s.pop("local_scene_breakdown", None)
        s.pop("local_scene_bucket_v1", None)
        changed += 1
    if write:
        Path(path).write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    print(f"{Path(path).name}: {changed} places updated" + (f"; pin-circle fallback for {fallbacks}" if fallbacks else ""))
    return changed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    for path in sorted(glob.glob(str(REPO / "data" / "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))):
        process(path, write=a.write)
    if not a.write:
        print("dry run: pass --write to save")


if __name__ == "__main__":
    main()
