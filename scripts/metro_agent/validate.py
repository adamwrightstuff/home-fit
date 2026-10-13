"""Validate results against INDEPENDENT ground truth, not against whether an API errored.

An empty or zero result can be wrong without any service reporting a failure.  These checks compare
what we stored with sources that do not depend on the lookup that produced it:

  amenities  Census County Business Patterns: establishments in the place's ZIP (retail + food + arts)
  transit    ACS: share of commuters in the ZIP who ride public transit
  peers      offline: a score collapsed to ~0/null while its 5 nearest scored neighbours are healthy

Verdicts
  CONTRADICTED   the independent source says our value cannot be right (a real data problem or bug)
  CONSISTENT     the independent source agrees the absence is genuine; recorded as an accepted gap
  SUSPICIOUS     weaker (peer-only) evidence that a value collapsed
  INCONCLUSIVE   not enough evidence either way

Thresholds are deliberately conservative impossibility tests (zero where the source shows plenty, or
zero where the source shows almost none). They are not scoring targets and never change a score.
"""
from __future__ import annotations

import json
import math
import os
import statistics
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

CONTRADICTED, CONSISTENT, SUSPICIOUS, INCONCLUSIVE = "CONTRADICTED", "CONSISTENT", "SUSPICIOUS", "INCONCLUSIVE"

# amenities: zero kept businesses while the ZIP has at least this many retail/food/arts establishments
AMEN_IMPOSSIBLE_MIN_ESTAB = 25
# ...and absence is plausible when the ZIP has fewer than this many
AMEN_GENUINE_MAX_ESTAB = 10
# transit: share of commuters riding transit above which "zero routes" is implausible / below which it is genuine
TRANSIT_IMPLAUSIBLE_SHARE = 0.02
TRANSIT_GENUINE_SHARE = 0.01
# above this share, zero routes is more likely a failed lookup than commuters reaching distant service
TRANSIT_FAILURE_SHARE = 0.05
# peers: a collapsed score vs healthy neighbours
PEER_K, PEER_MIN, PEER_COLLAPSED_AT_MOST, PEER_HEALTHY_MEDIAN_AT_LEAST = 5, 4, 5.0, 50.0

CBP_YEARS = (2022, 2021)
CBP_SECTORS = ("44-45", "72", "71")  # retail, accommodation & food, arts/entertainment

_cache: Dict[Any, Any] = {}


@dataclass
class Verdict:
    place: str
    pillar: str
    kind: str
    evidence: str


def _census_get(url: str, params: Dict[str, Any], get: Optional[Callable] = None) -> Optional[List[List[str]]]:
    import requests
    get = get or requests.get
    params = {**params, "key": os.getenv("CENSUS_API_KEY", "")}
    try:
        r = get(url, params=params, timeout=30)
        return r.json() if r.status_code == 200 else None
    except Exception:  # noqa: BLE001
        return None


def establishments(zip_code: str, get: Optional[Callable] = None) -> Optional[int]:
    """Retail + food + arts establishments in a ZIP (CBP), or None if unavailable."""
    key = ("cbp", zip_code)
    if key in _cache and get is None:
        return _cache[key]
    total, got = 0, False
    for sector in CBP_SECTORS:
        for year in CBP_YEARS:
            data = _census_get(f"https://api.census.gov/data/{year}/cbp",
                               {"get": "ESTAB", "for": f"zipcode:{zip_code}", "NAICS2017": sector}, get)
            if data and len(data) > 1:
                total += int(data[1][0]); got = True
                break
    out = total if got else None
    if get is None:
        _cache[key] = out
    return out


def healthcare_establishments(zip_code: str, get: Optional[Callable] = None) -> Optional[int]:
    """Ambulatory care (NAICS 621) + pharmacies (44611) establishments in a ZIP (CBP), or None."""
    key = ("cbp_health", zip_code)
    if key in _cache and get is None:
        return _cache[key]
    total, got = 0, False
    for naics in ("621", "44611"):
        for year in CBP_YEARS:
            data = _census_get(f"https://api.census.gov/data/{year}/cbp",
                               {"get": "ESTAB", "for": f"zipcode:{zip_code}", "NAICS2017": naics}, get)
            if data and len(data) > 1:
                total += int(data[1][0]); got = True
                break
    out = total if got else None
    if get is None:
        _cache[key] = out
    return out


def transit_commute_share(zip_code: str, get: Optional[Callable] = None) -> Optional[float]:
    key = ("acs", zip_code)
    if key in _cache and get is None:
        return _cache[key]
    data = _census_get("https://api.census.gov/data/2022/acs/acs5",
                       {"get": "B08301_001E,B08301_010E", "for": f"zip code tabulation area:{zip_code}"}, get)
    out = None
    if data and len(data) > 1:
        try:
            total, transit = float(data[1][0]), float(data[1][1])
            out = transit / total if total > 0 else None
        except (TypeError, ValueError):
            out = None
    if get is None:
        _cache[key] = out
    return out


def _zip(row: Dict[str, Any]) -> Optional[str]:
    z = ((row.get("score") or {}).get("location_info") or {}).get("zip") or (row.get("catalog") or {}).get("zip_code")
    return str(z).split("-")[0].zfill(5) if z else None


def judge_amenities(estab: Optional[int], kept: int) -> tuple:
    if estab is None:
        return INCONCLUSIVE, "Census business counts unavailable"
    if kept > 0:
        return INCONCLUSIVE, f"{kept} businesses kept; nothing to contradict"
    if estab >= AMEN_IMPOSSIBLE_MIN_ESTAB:
        return CONTRADICTED, (f"Census counts {estab} retail/food/arts establishments in this ZIP (wider than the pillar's radius) "
                              "but none are within it: confirm the pin sits where people live and shop")
    if estab < AMEN_GENUINE_MAX_ESTAB:
        return CONSISTENT, f"Census counts only {estab} retail/food/arts establishments in this ZIP; an empty result is plausible"
    return INCONCLUSIVE, f"Census counts {estab} establishments; neither clearly impossible nor clearly genuine"


HEALTH_IMPOSSIBLE_MIN_ESTAB = 10


def judge_healthcare(estab: Optional[int], local_facilities: int) -> tuple:
    """Zero clinics, pharmacies and urgent care found while the ZIP has many healthcare establishments."""
    if estab is None:
        return INCONCLUSIVE, "Census healthcare counts unavailable"
    if local_facilities > 0:
        return INCONCLUSIVE, f"{local_facilities} facilities found; nothing to contradict"
    if estab >= HEALTH_IMPOSSIBLE_MIN_ESTAB:
        return CONTRADICTED, (f"Census counts {estab} doctor/clinic/pharmacy establishments in this ZIP (wider than the "
                              "pillar's radius) but we found none: the lookup likely returned empty, not the place")
    return INCONCLUSIVE, f"Census counts {estab} healthcare establishments; absence not clearly impossible"


def judge_transit(share: Optional[float], routes: int) -> tuple:
    if share is None:
        return INCONCLUSIVE, "ACS commute data unavailable"
    if routes > 0:
        return INCONCLUSIVE, f"{routes} routes found; nothing to contradict"
    pct = f"{share * 100:.1f}%"
    if share >= TRANSIT_FAILURE_SHARE:
        return CONTRADICTED, f"{pct} of commuters in this ZIP ride transit but we found 0 routes"
    if share >= TRANSIT_IMPLAUSIBLE_SHARE:
        return CONSISTENT, (f"{pct} of commuters in this ZIP ride transit, but they reach service outside the pillar's walking "
                            "radius (commuter rail or a distant stop); 0 routes within it scores low by design")
    if share < TRANSIT_GENUINE_SHARE:
        return CONSISTENT, f"only {pct} of commuters in this ZIP ride transit; no routes is plausible"
    return INCONCLUSIVE, f"{pct} of commuters ride transit; inconclusive"



def _haversine_km(a, b) -> float:
    (la1, lo1), (la2, lo2) = a, b
    p = math.pi / 180
    h = 0.5 - math.cos((la2 - la1) * p) / 2 + math.cos(la1 * p) * math.cos(la2 * p) * (1 - math.cos((lo2 - lo1) * p)) / 2
    return 12742 * math.asin(math.sqrt(h))


def peer_collapses(rows: List[Dict[str, Any]], pillars: Optional[List[str]] = None) -> List[Verdict]:
    ok = [r for r in rows if r.get("success") and (r.get("catalog") or {}).get("lat")]
    pts = [(float(r["catalog"]["lat"]), float(r["catalog"]["lon"])) for r in ok]
    names = sorted({k for r in ok for k in ((r["score"].get("livability_pillars")) or {})})
    skip = {"quality_education", "political_lean", "air_travel_access"}
    pillars = pillars or [p for p in names if p not in skip]
    out: List[Verdict] = []
    for i, r in enumerate(ok):
        order = sorted((j for j in range(len(ok)) if j != i), key=lambda j: _haversine_km(pts[i], pts[j]))
        for p in pillars:
            mine = ((r["score"]["livability_pillars"].get(p) or {}).get("score"))
            if mine is not None and mine > PEER_COLLAPSED_AT_MOST:
                continue
            peer_scores = []
            for j in order:
                s = (ok[j]["score"]["livability_pillars"].get(p) or {}).get("score")
                if isinstance(s, (int, float)):
                    peer_scores.append(s)
                if len(peer_scores) == PEER_K:
                    break
            if len(peer_scores) >= PEER_MIN and statistics.median(peer_scores) >= PEER_HEALTHY_MEDIAN_AT_LEAST:
                out.append(Verdict(r["catalog"]["name"], p, SUSPICIOUS,
                                   f"score {mine} while the {len(peer_scores)} nearest scored places have median "
                                   f"{statistics.median(peer_scores):.0f}"))
    return out


def validate(rows: List[Dict[str, Any]], log: Callable[[str], None] = print,
             estab_fn: Callable = establishments, share_fn: Callable = transit_commute_share,
             health_fn: Callable = healthcare_establishments) -> List[Verdict]:
    from . import diagnose as dg
    verdicts: List[Verdict] = []
    for r in rows:
        if not r.get("success"):
            continue
        name, z = r["catalog"]["name"], _zip(r)
        for f in dg.classify_place(r):
            if f.remedy not in (dg.VERIFY, dg.SOURCE) or not z:
                continue
            lp = r["score"]["livability_pillars"]
            if f.pillar == "neighborhood_amenities":
                kept = len((lp["neighborhood_amenities"].get("breakdown") or {}).get("business_list") or [])
                kind, ev = judge_amenities(estab_fn(z), kept)
            elif f.pillar == "public_transit_access":
                routes = int(((lp["public_transit_access"].get("summary") or {}).get("total_routes")) or 0)
                kind, ev = judge_transit(share_fn(z), routes)
            else:
                continue
            verdicts.append(Verdict(name, f.pillar, kind, f"ZIP {z}: {ev}"))
        # Healthcare: the resolver clears the api_error flag when a retry returns cleanly but empty, so check
        # every place, not just flagged ones.
        hc = (r["score"]["livability_pillars"] or {}).get("healthcare_access") or {}
        sm = hc.get("summary") or {}
        local = sum(int(sm.get(k) or 0) for k in ("urgent_care_count", "pharmacy_count", "clinic_count", "hospital_count"))
        if z and hc and local == 0:
            kind, ev = judge_healthcare(health_fn(z), local)
            if kind == CONTRADICTED:
                verdicts.append(Verdict(name, "healthcare_access", kind, f"ZIP {z}: {ev}"))
    verdicts += peer_collapses(rows)
    return verdicts


def format_report(verdicts: List[Verdict]) -> str:
    lines = ["VALIDATION AGAINST INDEPENDENT SOURCES", "=" * 70]
    for kind, note in ((CONTRADICTED, "the independent source says our value is wrong: fix the lookup or filter, do not accept"),
                       (SUSPICIOUS, "collapsed relative to neighbours: look at these"),
                       (CONSISTENT, "absence confirmed as genuine: recorded as accepted gaps"),
                       (INCONCLUSIVE, "not enough evidence either way")):
        vs = [v for v in verdicts if v.kind == kind]
        if vs:
            lines += ["", f"{kind} ({len(vs)}): {note}"]
            lines += [f"  {v.place} / {v.pillar}: {v.evidence}" for v in vs]
    if len(lines) == 2:
        lines.append("nothing to validate")
    return "\n".join(lines)


def accepted_path(scores_path: Path) -> Path:
    return scores_path.with_suffix(".accepted.json")


def write_accepted(scores_path: Path, verdicts: List[Verdict]) -> int:
    p = accepted_path(scores_path)
    existing = {(a["place"], a["pillar"]): a for a in json.loads(p.read_text())} if p.is_file() else {}
    for v in verdicts:
        if v.kind == CONSISTENT:
            existing[(v.place, v.pillar)] = {"place": v.place, "pillar": v.pillar, "reason": v.evidence}
        elif v.kind == CONTRADICTED:
            existing.pop((v.place, v.pillar), None)  # new evidence overrides an earlier acceptance
    p.write_text(json.dumps(sorted(existing.values(), key=lambda a: (a["place"], a["pillar"])), indent=2))
    return len(existing)
