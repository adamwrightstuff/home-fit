"""Verify stage: look at the raw upstream data for places `resolve` could not fix.

`resolve` retries a lookup; when it still comes back empty, the question is whether the data really
is not there or our code is losing it.  `probe` asks the upstream services directly, at the same
location, and reports raw counts so the verdict is evidence, not a guess.

  amenities  raw OSM businesses within the pillar's radius vs what survives our filtering
  transit    Transitland routes at 2 / 5 / 10 km (the pillar only looks at 2 km)
"""
from __future__ import annotations

import os
import sys
from typing import Any, Callable, Dict, List, Optional

from . import diagnose as dg

REPO = __import__("pathlib").Path(__file__).resolve().parents[2]
TRANSIT_RADII = (2000, 5000, 10000)


def _overpass_url() -> str:
    return (os.getenv("OVERPASS_URL") or "https://overpass.openstreetmap.fr/api/interpreter").strip()


def raw_business_count(lat: float, lon: float, radius_m: int, post: Optional[Callable] = None) -> Optional[int]:
    """Count any shop/amenity-type features Overpass knows about within radius (no name filtering)."""
    import requests
    post = post or requests.post
    q = (f"[out:json][timeout:30];(node[\"shop\"](around:{radius_m},{lat},{lon});"
         f"way[\"shop\"](around:{radius_m},{lat},{lon});"
         f"node[\"amenity\"~\"restaurant|cafe|bar|pub|fast_food|bank|pharmacy|library\"](around:{radius_m},{lat},{lon});"
         f"way[\"amenity\"~\"restaurant|cafe|bar|pub|fast_food|bank|pharmacy|library\"](around:{radius_m},{lat},{lon}););out count;")
    try:
        r = post(_overpass_url(), data={"data": q}, timeout=45, headers={"User-Agent": "HomeFit/1.0"})
        if r.status_code != 200:
            return None
        j = r.json()
        if "remark" in j and "error" in str(j["remark"]).lower():
            return None
        return int(j["elements"][0]["tags"]["total"])
    except Exception:  # noqa: BLE001
        return None


def processed_business_count(lat: float, lon: float, radius_m: int) -> Optional[int]:
    sys.path.insert(0, str(REPO))
    from data_sources import osm_api
    d = osm_api.query_local_businesses(lat, lon, radius_m=radius_m)
    if d is None:
        return None
    return sum(len(d.get(k) or []) for k in ("tier1_daily", "tier2_social", "tier3_culture", "tier4_services"))


def amenities_verdict(raw: Optional[int], kept: Optional[int]) -> str:
    if raw is None and kept is None:
        return "UPSTREAM: Overpass is not answering these queries; retry later or fix the server"
    if kept:
        return "FIXED UPSTREAM: businesses now come back; re-run resolve"
    if raw == 0:
        return "OSM HAS NO BUSINESSES HERE: a genuine data gap in OpenStreetMap (needs another source)"
    return "CODE: Overpass has businesses but none survive our name/brand filtering; look at the filter"


def transit_counts(lat: float, lon: float, get: Optional[Callable] = None) -> Dict[int, Dict[str, Any]]:
    import requests
    get = get or requests.get
    out: Dict[int, Dict[str, Any]] = {}
    for r in TRANSIT_RADII:
        try:
            resp = get("https://transit.land/api/v2/rest/routes",
                       params={"lat": lat, "lon": lon, "radius": r, "limit": 50, "apikey": os.getenv("TRANSITLAND_API_KEY", "")},
                       timeout=30)
            if resp.status_code != 200:
                out[r] = {"error": f"HTTP {resp.status_code}"}
                continue
            routes = resp.json().get("routes") or []
            agencies = sorted({((x.get("agency") or {}).get("agency_name") or "?") for x in routes})
            out[r] = {"routes": len(routes), "agencies": agencies[:3]}
        except Exception as e:  # noqa: BLE001
            out[r] = {"error": f"{type(e).__name__}"}
    return out


def transit_verdict(c: Dict[int, Dict[str, Any]]) -> str:
    if any("error" in v for v in c.values()):
        return "UPSTREAM: Transitland did not answer cleanly; retry"
    near, mid, far = (c[r]["routes"] for r in TRANSIT_RADII)
    if near:
        return "FIXED UPSTREAM: routes now come back within 2 km; re-run resolve"
    if mid or far:
        return (f"COVERAGE: no routes within 2 km but {mid} within 5 km and {far} within 10 km "
                "(service exists nearby, outside the pillar's radius; decide if that counts)")
    return "NO SERVICE IN TRANSITLAND within 10 km (genuinely none, or the agency's feed is not in Transitland)"


def probe(rows: List[Dict[str, Any]], log: Callable[[str], None] = print) -> List[Dict[str, Any]]:
    sys.path.insert(0, str(REPO))
    from data_sources.radius_profiles import get_radius_profile
    results = []
    targets = []
    for r in rows:
        for f in dg.classify_place(r):
            if f.remedy == dg.VERIFY and f.pillar in ("neighborhood_amenities", "public_transit_access"):
                targets.append((r, f))
    log(f"probing {len(targets)} flagged lookups…")
    for r, f in targets:
        cat = r["catalog"]
        lat, lon = float(cat["lat"]), float(cat["lon"])
        if f.pillar == "neighborhood_amenities":
            at = ((r["score"]["livability_pillars"].get("neighborhood_amenities") or {}).get("area_classification") or {}).get("area_type")
            radius = int(get_radius_profile("neighborhood_amenities", at, None).get("query_radius_m", 1500))
            raw, kept = raw_business_count(lat, lon, radius), processed_business_count(lat, lon, radius)
            verdict = amenities_verdict(raw, kept)
            detail = f"radius {radius} m: raw OSM businesses={raw}, kept after filtering={kept}"
        else:
            c = transit_counts(lat, lon)
            verdict = transit_verdict(c)
            detail = "; ".join(f"{k // 1000} km: {v.get('routes', v.get('error'))} routes {v.get('agencies', '')}" for k, v in c.items())
        results.append({"place": cat["name"], "pillar": f.pillar, "detail": detail, "verdict": verdict})
        log(f"\n{cat['name']} / {f.pillar}\n  {detail}\n  -> {verdict}")
    return results
