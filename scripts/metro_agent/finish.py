"""
Finish a scored metro: everything that follows `run` and needs no judgment call, with each automatic decision
made by a documented, data-driven rule (never a place name). What it cannot decide it leaves flagged.

  PYTHONPATH=. python -m scripts.metro_agent finish --metro san_antonio --dry-run   # show decisions, change nothing
  PYTHONPATH=. python -m scripts.metro_agent finish --metro san_antonio

Steps
  1  education   re-score offline from the local school snapshot, apply the education weight (this metro only), composites
  2  crime       probe the FBI agency list for places with no crime data and apply RULE C
  3  retry       retry what can be retried (resolver, through a local API on its own port)
  4  accept      record the remaining gaps that meet RULES T, H, P, E (evidence is written into the reason)
  5  status      apply the status-signal class and trajectory blend (scripts/catalog/recompute_status_class.py). It must run
                 AFTER the last composites recompute, which otherwise overwrites status_signal and it_score
  6  report      health verdict and what is still open

Rules (DESIGN_PRINCIPLES.md: objective, reproducible, same for every place)
  C1 own agency     a police agency named for the place that returns agency-level data  -> map the place to it
  C2 neighborhood   a neighborhood of city X when a police agency whose name contains X (so "Charlotte-Mecklenburg Police
                    Department" counts for Charlotte) returns data and sits within 15 miles -> map city X to it
  C3 unincorporated a Census-designated place (CDP) with no agency of its own and a county sheriff with data, or (when
                    there is no sheriff) a consolidated "Metropolitan" or "County" police department within 15 miles
                    -> map to it as a county proxy (lower confidence, labelled by the scorer)
  C4 otherwise      record the gap with the probe's evidence; never borrow a neighbouring town's numbers
  C6 unincorporated a Census-designated place scored with an agency that is neither its own nor a sheriff (a neighbouring
     scored city's police) while its county sheriff returns data -> map to the sheriff (county proxy)
  C5 mismatch       a scored suburb whose matched agency is not named for it, while a police agency named for it (within 15
                    miles) returns data -> map it to that agency (the automatic match picked a lookalike or a neighbour)
  T  transit        Transitland found no routes AND a retry agrees -> accept; reason states the OpenStreetMap bus stops
                    within 1.9 miles (so a reader can see whether service exists beyond the search radius)
  H  healthcare     no clinics/pharmacies/hospitals found AND OpenStreetMap shows no hospital, clinic, doctor or pharmacy within 3 miles (the kinds the pillar counts) -> accept
  P  political lean no precinct polygon within range of the pin -> accept (opt-in filter)
  E  education      no K-12 district covers the pin (Census 'School District Not Defined') -> reviewed exception
  E2 education      a district covers the pin and public schools are within 3 miles, but none has a SchoolDigger rating
                    (very small schools are unrated) -> reviewed exception; the reason states the counts
"""
from __future__ import annotations

import csv
import json
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from . import diagnose as dg
from . import preflight as pf
from . import validate as vd

REPO = pf.REPO
PY = sys.executable
SPECIAL_AGENCY = re.compile(r"university|college|school|hospital|state park|park rangers?|constable|district attorney|"
                            r"prosecutor|attorney general|\bfire\b|transit|airport|port authority|forest|tribal|campus|"
                            r"investigat|detective|state police|marshal", re.I)
OWN_MAX_KM = 25.0   # an agency "named for the place" must also sit near it (a substring match can hit a same-named town far away)
CDP_LSAD = "57"


# ----------------------------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------------------------
def scores_path(metro: str) -> Path:
    return REPO / "data" / f"{metro}_metro_place_catalog_scores_merged.composites_recomputed.jsonl"


def _sh(args: List[str], env: Optional[Dict[str, str]] = None, quiet: bool = True) -> str:
    r = subprocess.run(args, cwd=str(REPO), capture_output=True, text=True, env={**os.environ, "PYTHONPATH": str(REPO), **(env or {})})
    return r.stdout + ("" if quiet else r.stderr)


def overpass_url() -> str:
    return (os.environ.get("OVERPASS_URL") or "").strip()


def osm_count(ql: str, url: Optional[str] = None) -> Optional[int]:
    """Count result of an Overpass `out count;` query; None when the server cannot answer."""
    import requests

    url = url or overpass_url()
    if not url:
        return None
    try:
        r = requests.post(url, data={"data": f"[out:json][timeout:90];{ql}out count;"}, timeout=150)
        return int(r.json()["elements"][0]["tags"]["total"])
    except Exception:  # noqa: BLE001
        return None


def census_lsad() -> Dict[Tuple[str, str], str]:
    """{(state, base name): LSAD code} from the Census gazetteer in data_cache (57 = census-designated place)."""
    z = REPO / "data_cache" / "gazetteer_places_2023.zip"
    out: Dict[Tuple[str, str], str] = {}
    if not z.is_file():
        return out
    with zipfile.ZipFile(z) as zf:
        name = next(n for n in zf.namelist() if n.endswith(".txt"))
        lines = zf.read(name).decode("latin-1").splitlines()
    hdr = [h.strip() for h in lines[0].split("\t")]
    i_st, i_nm, i_ls = hdr.index("USPS"), hdr.index("NAME"), hdr.index("LSAD")
    for ln in lines[1:]:
        p = ln.split("\t")
        if len(p) <= i_ls:
            continue
        base = re.sub(r"\s+(city|town|village|CDP|borough|municipality|city and borough)$", "", p[i_nm].strip())
        out.setdefault((p[i_st].strip(), base), p[i_ls].strip())
    return out


def _catalog_rows(metro: str) -> Dict[str, Dict[str, str]]:
    p = REPO / "data" / f"{metro}_metro_place_catalog.csv"
    return {r["name"]: r for r in csv.DictReader(open(p))}


def _city_of(query: str) -> str:
    parts = [x.strip() for x in (query or "").split(",")]
    return parts[1] if len(parts) >= 3 else ""


def scorer_data(ori: str, name: str, rate_fn: Callable, last_year: int, years_back: int = 4) -> Optional[Dict[str, Any]]:
    """The scorer's own test for usable agency data (data_sources.crime_api._agency_year): the agency returns agency-tier
    violent AND property rates for a year and they are not both zero. The probe's lenient test ("violent rate at agency tier")
    let a county sheriff through that the scorer then rejected, so the rules use this one."""
    for yr in range(last_year, last_year - years_back, -1):
        v, p = rate_fn(ori, "violent-crime", yr, name), rate_fn(ori, "property-crime", yr, name)
        if (isinstance(v, (list, tuple)) and len(v) >= 2 and isinstance(p, (list, tuple)) and len(p) >= 2
                and v[1] == "agency" and p[1] == "agency" and (v[0] or 0) + (p[0] or 0) > 0):
            return {"year": yr, "violent_per_100k": v[0], "population": v[2] if len(v) > 2 else None}
    return None


def city_police(state: str, city: str, lat: float, lon: float, agencies_for: Callable[[str], List[Dict[str, Any]]],
                rate_fn: Callable, last_year: int) -> Optional[Dict[str, Any]]:
    """The nearest police agency of the state whose name contains the city's name (whole word) and that returns agency data."""
    from . import fbi_probe as fp

    word = re.compile(rf"\b{re.escape(city)}\b", re.I)
    best = None
    for ag in agencies_for(state):
        name = fp._name(ag)
        if not word.search(name) or not re.search(r"police", name, re.I) or SPECIAL_AGENCY.search(name):
            continue
        try:
            d = fp._km((lat, lon), (float(fp._get(ag, "latitude", "lat")), float(fp._get(ag, "longitude", "lng", "lon"))))
        except (TypeError, ValueError):
            continue
        if d > OWN_MAX_KM:
            continue
        data = scorer_data(fp._ori(ag), name, rate_fn, last_year)
        if data and (best is None or d < best["km"]):
            best = {"name": name, "km": d, "data": data}
    return best


def crime_decisions(results: List[Dict[str, Any]], metro: str, lsad: Dict[Tuple[str, str], str],
                    agencies_for: Optional[Callable[[str], List[Dict[str, Any]]]] = None, rate_fn: Optional[Callable] = None,
                    last_year: int = 0, verify: Optional[Callable[[Dict[str, Any]], bool]] = None) -> List[Dict[str, Any]]:
    """Apply rules C1-C4 to FBI probe results. Pure given its inputs: returns decisions, writes nothing.
    `verify(candidate)` re-checks a candidate with the scorer's own data test before any rule may use it."""
    cat = _catalog_rows(metro)
    out = []
    for r in results:
        place, st = r["place"], r["state"]
        row = cat.get(place, {})
        is_neigh = row.get("type") == "neighborhood"
        city = _city_of(row.get("search_query", "")) if is_neigh else ""
        usable = [c for c in r["candidates"] if c.get("data") and not SPECIAL_AGENCY.search(c["name"]) and (verify is None or verify(c))]
        police = [c for c in usable if re.search(r"police", c["name"], re.I)]
        dec: Dict[str, Any] = {"place": place, "state": st, "action": "gap", "reason": r["note"]}
        named = [c for c in police if "named for the place" in c["why"]]
        own = [c for c in named if c.get("km") is not None and c["km"] <= OWN_MAX_KM]
        if not own and len(named) == 1 and named[0].get("coord_shared"):   # county-level point in the FBI file: distance is meaningless
            own = named                                                      # the only police agency in the state named for the place
        city_pd = [c for c in police if city and c["name"].lower() == f"{city.lower()} police department"]
        if is_neigh and city and not city_pd and agencies_for is not None:
            cp = city_police(st, city, float(row.get("lat", 0) or 0), float(row.get("lon", 0) or 0), agencies_for, rate_fn, last_year)
            if cp:
                city_pd = [{"name": cp["name"], "data": cp["data"]}]
        sheriff = [c for c in usable if "sheriff" in c["name"].lower() and "county agency" in c["why"]]
        consolidated = [c for c in police if re.search(r"metropolitan|county police", c["name"], re.I)
                        and c.get("km") is not None and c["km"] <= OWN_MAX_KM]
        if not is_neigh and own:
            c = own[0]
            dec.update(action="map", kind="own", agency=c["name"], keys=_keys(place),
                       reason=f"C1: {c['name']} is named for the place and returns {c['data']['year']} agency data")
        elif is_neigh and city_pd:
            c = city_pd[0]
            dec.update(action="map", kind="own", agency=c["name"], keys=_keys(city),
                       reason=f"C2: neighborhood of {city}; {c['name']} returns {c['data']['year']} agency data")
        elif not is_neigh and lsad.get((st, place)) == CDP_LSAD and not own and (sheriff or consolidated):
            c = (sheriff or consolidated)[0]
            dec.update(action="map", kind="county", agency=c["name"], keys=_keys(place),
                       reason=f"C3: census-designated (unincorporated) place with no agency of its own; {c['name']} "
                              f"returns {c['data']['year']} data (county proxy)")
        else:
            near = ", ".join(c["name"] for c in police[:3]) or "none"
            dec["reason"] = (f"C4: no police agency named for the place within {OWN_MAX_KM / 1.609:.0f} miles reports data, and it is neither a "
                             f"neighborhood of a city whose police department reports nor an unincorporated census-designated place "
                             f"with a reporting county sheriff. Nearby reporting agencies: {near}; they police other places, so their "
                             f"numbers are not borrowed.")
        out.append(dec)
    return out


def mismatch_decisions(rows: List[Dict[str, Any]], metro: str, agencies_for: Callable[[str], List[Dict[str, Any]]],
                       rate_fn: Callable, last_year: int, lsad: Optional[Dict[Tuple[str, str], str]] = None) -> List[Dict[str, Any]]:
    """Rules C5 and C6. Pure given its inputs: for scored suburbs, compare the matched agency with agencies named for the
    place (C5) and, for unincorporated census-designated places, with the county sheriff (C6)."""
    from . import fbi_probe as fp

    cat = _catalog_rows(metro)
    out = []
    for r in rows:
        c = r["catalog"]
        if not r.get("success") or c.get("type") != "suburb" or cat.get(c["name"], {}).get("type") != "suburb":
            continue
        cs = r["score"]["livability_pillars"].get("community_safety", {})
        matched = ((cs.get("breakdown") or {}).get("agency_name") or "")
        base = c["name"].lower()
        if not matched or base in matched.lower():
            continue
        best = None
        for ag in agencies_for(c["state_abbr"]):
            name = fp._name(ag)
            if base not in name.lower() or not re.search(r"police", name, re.I) or SPECIAL_AGENCY.search(name):
                continue
            try:
                d = fp._km((float(c["lat"]), float(c["lon"])), (float(fp._get(ag, "latitude", "lat")), float(fp._get(ag, "longitude", "lng", "lon"))))
            except (TypeError, ValueError):
                continue
            if d > OWN_MAX_KM:
                continue
            data = scorer_data(fp._ori(ag), name, rate_fn, last_year)
            if data and (best is None or d < best[0]):
                best = (d, name, data)
        if best:
            out.append({"place": c["name"], "state": c["state_abbr"], "action": "map", "kind": "own", "agency": best[1], "keys": _keys(c["name"]),
                        "reason": f"C5: scored with '{matched}', but {best[1]} is named for the place, {best[0] / 1.609:.0f} miles away, "
                                  f"and returns {best[2]['year']} agency data"})
            continue
        county = (cat.get(c["name"], {}).get("county_borough") or c.get("county_borough") or "").strip()
        if lsad and county and lsad.get((c["state_abbr"], c["name"])) == CDP_LSAD and "sheriff" not in matched.lower():
            for ag in agencies_for(c["state_abbr"]):
                name = fp._name(ag)
                if county.lower() not in name.lower() or "sheriff" not in name.lower() or SPECIAL_AGENCY.search(name):
                    continue
                data = scorer_data(fp._ori(ag), name, rate_fn, last_year)
                if data:
                    out.append({"place": c["name"], "state": c["state_abbr"], "action": "map", "kind": "county", "agency": name,
                                "keys": _keys(c["name"]),
                                "reason": f"C6: census-designated (unincorporated) place scored with '{matched}', which polices another "
                                          f"place; {name} returns {data['year']} data (county proxy)"})
                    break
    return out


def _keys(name: str) -> List[str]:
    """Lookup keys for a place in data/crime_agency_map.json. The scorer keys on the city its geocoder returns, which may be
    spelled differently ("Saint Petersburg" for "St. Petersburg"), so every spelling variant is registered."""
    base = name.lower().strip()
    variants = [base, f"{base} township"]
    for pat, rep in ((r"\bst\.? ", "saint "), (r"\bsaint ", "st. "), (r"\bft\.? ", "fort "), (r"\bmt\.? ", "mount ")):
        v = re.sub(pat, rep, base)
        if v != base and v not in variants:
            variants += [v, f"{v} township"]
    return variants


def add_geocoded_city_keys(decisions: List[Dict[str, Any]], rows: List[Dict[str, Any]]) -> None:
    """Also register the city name the scorer actually saw for a mapped place (a CDP can geocode to a neighbouring town)."""
    seen = {r["catalog"]["name"]: ((r.get("score") or {}).get("location_info") or {}).get("city", "") for r in rows}
    for d in decisions:
        city = (seen.get(d["place"]) or "").lower().strip()
        if d["action"] == "map" and city and city not in d["keys"]:
            d["keys"].append(city)
            d["reason"] += f" (the scorer's geocoder names the city '{seen[d['place']]}', so that key is registered too)"


def apply_map(decisions: List[Dict[str, Any]]) -> int:
    p = REPO / "data" / "crime_agency_map.json"
    m = json.loads(p.read_text())
    n = 0
    for d in decisions:
        if d["action"] != "map":
            continue
        for k in d["keys"]:
            m.setdefault(d["state"], {})[k] = {"agency": d["agency"], "kind": d["kind"]}
        n += 1
    p.write_text(json.dumps(m, indent=2) + "\n")
    return n


# ----------------------------------------------------------------------------------------------
# the pipeline
# ----------------------------------------------------------------------------------------------
def finish(metro: str, *, dry_run: bool = False, api_base: str = "http://127.0.0.1:8010",
           log: Callable[[str], None] = print) -> int:
    from . import health as hl
    from . import resolve as rs
    from . import run as runner

    pf._load_env()
    path = scores_path(metro)
    if not path.is_file():
        log(f"no scores file for {metro}: run `metro_agent run --metro {metro}` first")
        return 2
    if not overpass_url():
        log("OVERPASS_URL is not set; the early-education bonus and the OpenStreetMap evidence need it")
        return 2

    log(f"\n== 1. education ({metro})")
    if dry_run:
        log("   (dry run) would re-score education offline, apply the weight to this metro only, recompute composites")
    else:
        out = _sh([PY, "scripts/catalog/rescore_education_offline.py", "--metro", metro])
        log("   " + next((l for l in out.splitlines() if "rescored" in l), "education re-scored"))
        sys.path.insert(0, str(REPO))
        from scripts.catalog import enable_education_weight as ew
        log(f"   weight applied to {ew.reweight_file(str(path), backup=False)} places")
        _sh([PY, "scripts/catalog/recompute_catalog_composites.py", "--no-census", "--input", str(path), "--output", str(path)])

    rows = dg.load_rows(path)
    log("\n== 2. crime agencies (rules C1-C4)")
    decisions: List[Dict[str, Any]] = []
    if os.getenv("FBI_CRIME_API_KEY") or os.getenv("FBI_API_KEY"):
        from . import fbi_probe as fp
        results = fp.run(rows, log=lambda s: None)
        import datetime

        from data_sources import crime_api
        cache: Dict[str, List[Dict[str, Any]]] = {}

        def agencies_for(st: str) -> List[Dict[str, Any]]:
            if st not in cache:
                cache[st] = crime_api._fetch_fbi_agencies(st) or []
            return cache[st]

        last_year = datetime.date.today().year - 1
        verify = lambda c: scorer_data(c["ori"], c["name"], crime_api._fetch_fbi_agency_rate, last_year) is not None  # noqa: E731
        decisions = crime_decisions(results, metro, census_lsad(), agencies_for, crime_api._fetch_fbi_agency_rate, last_year, verify)
        if not dry_run:
            path.with_suffix(".crime_decisions.json").write_text(json.dumps(decisions, indent=2))
        for d in decisions:
            log(f"   {d['place']:26} {d['action']:4} {d.get('agency', '-')[:40]:40} | {d['reason'][:90]}")
        extra = mismatch_decisions(rows, metro, agencies_for, crime_api._fetch_fbi_agency_rate, last_year, census_lsad())
        for d in extra:
            log(f"   {d['place']:26} map  {d['agency'][:40]:40} | {d['reason'][:100]}")
        decisions += extra
    else:
        log("   no FBI API key in the environment; skipped")

    proc = None
    try:
        if not dry_run:
            add_geocoded_city_keys(decisions, rows)
            n = apply_map(decisions)
            log(f"   mapped {n} places in data/crime_agency_map.json")
            proc = runner.start_server(api_base, log) if runner.is_local(api_base) else None
            mapped = [d["place"] for d in decisions if d["action"] == "map"]
            if mapped:
                _sh([PY, "scripts/catalog/rescore_catalog_pillar.py", "--input", str(path), "--in-place", "--pillars",
                     "community_safety", "--names", ",".join(mapped), "--use-catalog-coordinates", "--base-url", api_base,
                     "--delay", "1", "--no-backup"])
            log("\n== 3. retry what can be retried")
            summary = rs.resolve(path, api_base, max_rounds=2, log=lambda s: None)
            log(f"   resolver: {summary.get('stop')}, material places left: {summary.get('material_places_left')}")
            _sh([PY, "scripts/catalog/recompute_catalog_composites.py", "--no-census", "--input", str(path), "--output", str(path)])
    finally:
        if proc is not None:
            proc.terminate()

    mapped_places = {d["place"] for d in decisions if d["action"] == "map"}
    still_empty: List[str] = []
    if not dry_run and mapped_places:
        for r in dg.load_rows(path):
            cs = (r.get("score") or {}).get("livability_pillars", {}).get("community_safety", {})
            if r["catalog"]["name"] in mapped_places and cs.get("score") is None:
                still_empty.append(r["catalog"]["name"])
    log("\n== 4. accept gaps that meet the rules")
    if still_empty:
        log(f"   MAPPED BUT STILL NO CRIME DATA (left flagged, not accepted; the scorer rejected the agency): {', '.join(still_empty)}")
    accepted = accept_by_rules(metro, path, dry_run=dry_run, skip_crime=(mapped_places if dry_run else set(still_empty)), log=log)

    log("\n== 5. status class and it_score blend (after the last composites recompute)")
    if dry_run:
        log("   (dry run) would run recompute_status_class.py --write")
    else:
        out = _sh([PY, "scripts/catalog/recompute_status_class.py", "--metro", metro, "--write"])
        for ln in out.splitlines():
            if "trajectory" in ln or "labels changed" in ln or "wrote" in ln:
                log("   " + ln.strip()[:150])

    log("\n== 6. report")
    rep = hl.audit_all([metro], offline=True)[0]
    log(f"   verdict: {rep['verdict']}; accepted by rule this run: {accepted}")
    for pr in rep.get("problems", []):
        log("   OPEN  " + pr)
    return 0 if rep["verdict"] in ("HEALTHY", "ATTENTION") else 1


def accept_by_rules(metro: str, path: Path, *, dry_run: bool = False, skip_crime: Optional[set] = None,
                    log: Callable[[str], None] = print) -> int:
    rows = dg.load_rows(path)
    labels = dg.place_labels(rows)
    cat = _catalog_rows(metro)
    result = dg.diagnose(rows, accepted=dg.load_accepted(path))
    verdicts: List[vd.Verdict] = []
    edu_exceptions: Dict[str, str] = {}

    def lat_lon(place: str) -> Tuple[float, float]:
        r = rows[labels.index(place)]["catalog"]
        return float(r["lat"]), float(r["lon"])

    for f in result["findings"]:
        if f["pillar"] == "(place)" or not f["material"] and not f["evidence"].startswith("withheld"):
            if f["pillar"] != "political_lean":
                continue
        place, pillar, ev = f["place"], f["pillar"], str(f["evidence"])
        try:
            la, lo = lat_lon(place)
        except ValueError:
            continue
        reason = None
        if pillar == "public_transit_access" and "no routes" in ev:
            stops = osm_count(f'node[highway=bus_stop](around:3000,{la},{lo});')
            if stops is not None:
                reason = (f"Rule T: Transitland returned no routes (confirmed on retry); OpenStreetMap shows {stops} bus stops "
                          f"within 1.9 miles; scores on the commute-time floor only.")
        elif pillar == "healthcare_access" and "no clinics" in ev:
            near = osm_count(f'nwr[amenity~"hospital|clinic|doctors|pharmacy"](around:4800,{la},{lo});')
            far = osm_count(f'nwr[amenity~"hospital|clinic|doctors|pharmacy"](around:12000,{la},{lo});')
            if near == 0:
                reason = f"Rule H: no clinics, pharmacies or hospitals within 3 miles in OpenStreetMap ({far} within 7.5 miles)."
        elif pillar == "political_lean" and "no precinct data" in ev:
            reason = "Rule P: no precinct polygon within range of the pin in the state's precinct file; political lean is an opt-in filter."
        elif pillar == "community_safety" and not ev.startswith("withheld") and place not in (skip_crime or set()):
            reason = "Rule C4: " + _probe_note(metro, place)
        if reason:
            verdicts.append(vd.Verdict(place, pillar, vd.CONSISTENT, f"accepted by rule: {reason}"))

    # E: places with no education score because no district covers them
    from data_sources import school_districts as sd
    for r in rows:
        c = r["catalog"]
        q = (r.get("score") or {}).get("livability_pillars", {}).get("quality_education", {})
        if r.get("success") and not q.get("score"):
            ds = sd.districts_for_point(float(c["lat"]), float(c["lon"]), c["state_abbr"])
            if not ds or all("not defined" in d["name"].lower() for d in ds):
                edu_exceptions[f"{metro}:{c['name']}"] = (
                    "Rule E: Census lists the pin as 'School District Not Defined' (no K-12 district covers it), so there is "
                    "no zoned or home-district school.")
            else:
                near, rated = nearby_schools(c["state_abbr"], float(c["lat"]), float(c["lon"]))
                if near and not rated:
                    edu_exceptions[f"{metro}:{c['name']}"] = (
                        f"Rule E2: {ds[0]['name']} covers the pin and {near} public schools are within 3 miles, but none has a "
                        f"SchoolDigger rating (very small schools are unrated), so there is nothing to score.")
    log(f"   {len(verdicts)} gaps accepted by rules T/H/P/C4, {len(edu_exceptions)} education exceptions (rule E)")
    for v in verdicts[:40]:
        log(f"     {v.place:24} {v.pillar:22} {v.evidence[19:110]}")
    if dry_run:
        return len(verdicts) + len(edu_exceptions)
    if verdicts:
        vd.write_accepted(path, verdicts)
    if edu_exceptions:
        p = REPO / "data" / "education_check_exceptions.json"
        d = json.loads(p.read_text())
        d.update(edu_exceptions)
        p.write_text(json.dumps(d, indent=2) + "\n")
    return len(verdicts) + len(edu_exceptions)


def nearby_schools(state: str, lat: float, lon: float, radius_mi: float = 3.0) -> Tuple[int, int]:
    """(public schools within the radius, how many of them have a SchoolDigger rating) from the local snapshot."""
    import math

    from data_sources import school_snapshot as ss

    snap = ss.load_state(state)
    near = rated = 0
    for sc in (snap or {}).get("schools", []):
        ll = (sc.get("address") or {}).get("latLong") or {}
        if sc.get("isPrivate") or ll.get("latitude") is None:
            continue
        p = math.pi / 180
        h = 0.5 - math.cos((ll["latitude"] - lat) * p) / 2 + math.cos(lat * p) * math.cos(ll["latitude"] * p) * (1 - math.cos((ll["longitude"] - lon) * p)) / 2
        if 7917.5 * math.asin(math.sqrt(h)) <= radius_mi:
            near += 1
            rated += 1 if sc.get("rankHistory") else 0
    return near, rated


def _probe_note(metro: str, place: str) -> str:
    p = scores_path(metro).with_suffix(".crime_decisions.json")
    try:
        for d in json.loads(p.read_text()):
            if d["place"] == place:
                return d["reason"].removeprefix("C4: ")
    except Exception:  # noqa: BLE001
        pass
    return "no police agency or county sheriff with data was found for this place in the FBI list."
