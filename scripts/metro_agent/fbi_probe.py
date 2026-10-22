"""FBI agency probe: for places whose community safety has no usable data, find out WHY and who could serve them.

`community_safety` falls back to a state-wide aggregate (which it refuses to score) when the FBI lookup
cannot match the place's own police agency.  This probe lists, for each such place, the agencies that
could plausibly police it (named for the place, or the closest agencies, or the county sheriff) and asks
the FBI whether each one actually has data for the most recent years.  It only reports: it never changes a
mapping or a score.  `--suggest` writes the findings to a reviewable file.

  USABLE        an agency has its own (agency-tier) data: a mapping place -> agency would fix this place
  NO_AGENCY_DATA  agencies exist but none report: needs another source (state or city portal)
  NO_AGENCY      no agency of that name or nearby in the FBI list: the place may be policed by a county
                 sheriff or a neighbour; check jurisdiction before mapping
"""
from __future__ import annotations

import datetime
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from . import diagnose as dg

REPO = Path(__file__).resolve().parents[2]
NEAR_KM = 15.0
MAX_CANDIDATES = 8
YEARS_BACK = 4


def _get(ag: Dict[str, Any], *keys) -> Any:
    for k in keys:
        if ag.get(k) not in (None, ""):
            return ag[k]
    return None


def _name(ag): return str(_get(ag, "agency_name", "agencyName") or "")
def _ori(ag): return str(_get(ag, "ori", "ORI") or "")


def _km(a, b) -> float:
    import math
    p = math.pi / 180
    h = 0.5 - math.cos((b[0] - a[0]) * p) / 2 + math.cos(a[0] * p) * math.cos(b[0] * p) * (1 - math.cos((b[1] - a[1]) * p)) / 2
    return 12742 * math.asin(math.sqrt(h))


def candidates(agencies: List[Dict[str, Any]], place: str, county: str, lat: float, lon: float) -> List[Dict[str, Any]]:
    """Agencies worth checking: named for the place, the county sheriff, and the nearest others."""
    place_l, county_l = place.lower(), (county or "").lower()
    out: Dict[str, Dict[str, Any]] = {}
    # The FBI file gives some agencies a county-level point instead of their own location: several agencies share
    # one coordinate pair (Englewood and Greenwood Village police are both at the Arapahoe County point). Distance
    # to such an agency says nothing, so the candidate is marked and the distance rules do not apply to it.
    pts: Dict[Any, int] = {}
    for ag in agencies:
        k = (_get(ag, "latitude", "lat"), _get(ag, "longitude", "lng", "lon"))
        pts[k] = pts.get(k, 0) + 1

    def add(ag, why):
        ori = _ori(ag)
        if not ori:
            return
        try:
            d = _km((lat, lon), (float(_get(ag, "latitude", "lat")), float(_get(ag, "longitude", "lng", "lon"))))
        except (TypeError, ValueError):
            d = None
        row = out.setdefault(ori, {"ori": ori, "name": _name(ag), "type": _get(ag, "agencyType", "agency_type"),
                                   "is_nibrs": bool(_get(ag, "is_nibrs")), "km": None if d is None else round(d, 1), "why": [],
                                   "coord_shared": pts.get((_get(ag, "latitude", "lat"), _get(ag, "longitude", "lng", "lon")), 0) > 1})
        if why not in row["why"]:
            row["why"].append(why)

    for ag in agencies:
        n = _name(ag).lower()
        if place_l and place_l in n:
            add(ag, "named for the place")
        elif county_l and county_l in n and ("sheriff" in n or "county" in n):
            add(ag, "county agency")
    with_d = []
    for ag in agencies:
        try:
            d = _km((lat, lon), (float(_get(ag, "latitude", "lat")), float(_get(ag, "longitude", "lng", "lon"))))
        except (TypeError, ValueError):
            continue
        if d <= NEAR_KM:
            with_d.append((d, ag))
    for _, ag in sorted(with_d, key=lambda t: t[0])[:MAX_CANDIDATES]:
        add(ag, f"within {NEAR_KM:.0f} km")
    return sorted(out.values(), key=lambda r: (("named for the place" not in r["why"]), r["km"] if r["km"] is not None else 999))


def agency_data(ori: str, name: str, rate_fn: Callable, last_year: int, years_back: int = YEARS_BACK) -> Optional[Dict[str, Any]]:
    """Most recent year in which the FBI returns an agency-tier violent rate for this agency, else None."""
    for yr in range(last_year, last_year - years_back, -1):
        res = rate_fn(ori, "violent-crime", yr, name)
        if isinstance(res, (tuple, list)) and len(res) >= 2 and res[1] == "agency":   # a list when read back from the disk cache
            return {"year": yr, "violent_per_100k": res[0], "population": res[2] if len(res) > 2 else None}
    return None


def probe_place(place: str, county: str, lat: float, lon: float, agencies: List[Dict[str, Any]],
                rate_fn: Callable, last_year: int) -> Dict[str, Any]:
    cands = candidates(agencies, place, county, lat, lon)
    for c in cands:
        c["data"] = agency_data(c["ori"], c["name"], rate_fn, last_year)
    usable = [c for c in cands if c["data"]]
    own = [c for c in usable if "named for the place" in c["why"]]
    county_ok = [c for c in usable if "county agency" in c["why"]]
    if own:
        best, verdict = own[0], "USABLE"
        note = f"{best['name']} has its own data ({best['data']['year']}): map {place} to it"
    elif county_ok:
        best, verdict = county_ok[0], "USABLE"
        note = f"no agency named for {place}; {best['name']} has data ({best['data']['year']}). Confirm it polices {place} before mapping"
    elif not cands:
        best, verdict, note = None, "NO_AGENCY", f"no agency named for {place}, no county agency and nothing within {NEAR_KM:.0f} km in the FBI list"
    elif usable:
        best, verdict = None, "NO_AGENCY_DATA"
        note = ("only neighbouring agencies report: " + ", ".join(c["name"] for c in usable[:3]) +
                f". They do not police {place}; do not borrow their numbers")
    else:
        best, verdict, note = None, "NO_AGENCY_DATA", "agencies exist but none returns its own data; needs another source"
    return {"place": place, "verdict": verdict, "note": note, "best": best, "candidates": cands}


def format_result(r: Dict[str, Any]) -> str:
    lines = [f"\n{r['place']}: {r['verdict']}", f"  {r['note']}"]
    for c in r["candidates"]:
        d = c["data"]
        got = f"data {d['year']} (violent {d['violent_per_100k']}/100k, pop {d['population']})" if d else "NO agency-level data"
        lines.append(f"    - {c['name']} [{c['ori']}] {c['km']} km, {'NIBRS' if c['is_nibrs'] else 'UCR'}; {', '.join(c['why'])}; {got}")
    return "\n".join(lines)


def run(rows: List[Dict[str, Any]], only: Optional[List[str]] = None, suggest_path: Optional[Path] = None,
        agencies_fn: Optional[Callable] = None, rate_fn: Optional[Callable] = None,
        log: Callable[[str], None] = print) -> List[Dict[str, Any]]:
    sys.path.insert(0, str(REPO))
    from data_sources import crime_api
    if not (os.getenv("FBI_CRIME_API_KEY") or os.getenv("FBI_API_KEY")) and agencies_fn is None:
        raise RuntimeError("no FBI API key in the environment (FBI_CRIME_API_KEY)")
    agencies_fn = agencies_fn or crime_api._fetch_fbi_agencies
    rate_fn = rate_fn or crime_api._fetch_fbi_agency_rate
    last_year = datetime.date.today().year - 1  # same starting year as the scoring pipeline; it walks back from here
    targets = []
    for r in rows:
        for f in dg.classify_place(r):
            if f.pillar == "community_safety" and f.cause == dg.NO_DATA_SOURCE and (not only or f.place in only):
                targets.append(r)
    log(f"probing {len(targets)} places…")
    results, cache = [], {}
    for r in targets:
        c = r["catalog"]
        st = c["state_abbr"]
        if st not in cache:
            cache[st] = agencies_fn(st) or []
        res = probe_place(c["name"], c.get("county_borough") or "", float(c["lat"]), float(c["lon"]), cache[st], rate_fn, last_year)
        res["state"] = st
        results.append(res)
        log(format_result(res))
    if suggest_path:
        suggest_path.write_text(json.dumps(
            [{"place": x["place"], "state": x["state"], "verdict": x["verdict"], "note": x["note"],
              "agency": (x["best"] or {}).get("name"), "ori": (x["best"] or {}).get("ori")} for x in results], indent=2))
        log(f"\nsuggestions written to {suggest_path} (nothing applied)")
    return results
