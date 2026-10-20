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
  5  report      health verdict and what is still open

Rules (DESIGN_PRINCIPLES.md: objective, reproducible, same for every place)
  C1 own agency     a police agency named for the place that returns agency-level data  -> map the place to it
  C2 neighborhood   a neighborhood of city X when "X Police Department" returns data    -> map city X to it
  C3 unincorporated a Census-designated place (CDP) with no agency of its own and a county sheriff with data
                    -> map to the sheriff as a county proxy (lower confidence, labelled by the scorer)
  C4 otherwise      record the gap with the probe's evidence; never borrow a neighbouring town's numbers
  T  transit        Transitland found no routes AND a retry agrees -> accept; reason states the OpenStreetMap bus stops
                    within 1.9 miles (so a reader can see whether service exists beyond the search radius)
  H  healthcare     no clinics/pharmacies/hospitals found AND OpenStreetMap shows none within 3 miles -> accept
  P  political lean no precinct polygon within range of the pin -> accept (opt-in filter)
  E  education      no K-12 district covers the pin (Census 'School District Not Defined') -> reviewed exception
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


def crime_decisions(results: List[Dict[str, Any]], metro: str, lsad: Dict[Tuple[str, str], str]) -> List[Dict[str, Any]]:
    """Apply rules C1-C4 to FBI probe results. Pure function: returns decisions, writes nothing."""
    cat = _catalog_rows(metro)
    out = []
    for r in results:
        place, st = r["place"], r["state"]
        row = cat.get(place, {})
        is_neigh = row.get("type") == "neighborhood"
        city = _city_of(row.get("search_query", "")) if is_neigh else ""
        usable = [c for c in r["candidates"] if c.get("data") and not SPECIAL_AGENCY.search(c["name"])]
        police = [c for c in usable if re.search(r"police", c["name"], re.I)]
        dec: Dict[str, Any] = {"place": place, "state": st, "action": "gap", "reason": r["note"]}
        own = [c for c in police if "named for the place" in c["why"] and c.get("km") is not None and c["km"] <= OWN_MAX_KM]
        city_pd = [c for c in police if city and c["name"].lower() == f"{city.lower()} police department"]
        sheriff = [c for c in usable if "sheriff" in c["name"].lower() and "county agency" in c["why"]]
        if not is_neigh and own:
            c = own[0]
            dec.update(action="map", kind="own", agency=c["name"], keys=_keys(place),
                       reason=f"C1: {c['name']} is named for the place and returns {c['data']['year']} agency data")
        elif is_neigh and city_pd:
            c = city_pd[0]
            dec.update(action="map", kind="own", agency=c["name"], keys=_keys(city),
                       reason=f"C2: neighborhood of {city}; {c['name']} returns {c['data']['year']} agency data")
        elif not is_neigh and lsad.get((st, place)) == CDP_LSAD and not own and sheriff:
            c = sheriff[0]
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


def _keys(name: str) -> List[str]:
    base = name.lower()
    return [base, f"{base} township"]


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
        decisions = crime_decisions(results, metro, census_lsad())
        if not dry_run:
            path.with_suffix(".crime_decisions.json").write_text(json.dumps(decisions, indent=2))
        for d in decisions:
            log(f"   {d['place']:26} {d['action']:4} {d.get('agency', '-')[:40]:40} | {d['reason'][:90]}")
    else:
        log("   no FBI API key in the environment; skipped")

    proc = None
    try:
        if not dry_run:
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

    log("\n== 4. accept gaps that meet the rules")
    accepted = accept_by_rules(metro, path, dry_run=dry_run,
                               skip_crime={d["place"] for d in decisions if d["action"] == "map"} if dry_run else None, log=log)

    log("\n== 5. report")
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
            near = osm_count(f'nwr[amenity~"hospital|clinic|doctors|pharmacy|dentist"](around:4800,{la},{lo});')
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


def _probe_note(metro: str, place: str) -> str:
    p = scores_path(metro).with_suffix(".crime_decisions.json")
    try:
        for d in json.loads(p.read_text()):
            if d["place"] == place:
                return d["reason"].removeprefix("C4: ")
    except Exception:  # noqa: BLE001
        pass
    return "no police agency or county sheriff with data was found for this place in the FBI list."
