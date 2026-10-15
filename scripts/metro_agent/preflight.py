"""Preflight for a metro run: verify every dependency BEFORE scoring anything.

Each check returns PASS / WARN / FAIL with a one-line fix.  FAIL means do not start scoring.
Network checks use the same query shapes as the app so a pass means the real queries work.
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

REPO = Path(__file__).resolve().parents[2]
PASS, WARN, FAIL = "PASS", "WARN", "FAIL"

OVERPASS_CANDIDATES = [
    "https://overpass.openstreetmap.fr/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://z.overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass.nchc.org.tw/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
OVERPASS_SLOW_S = 8.0


@dataclass
class Check:
    name: str
    status: str
    detail: str
    fix: str = ""


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv(REPO / ".env")
    except Exception:
        pass


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ── environment ─────────────────────────────────────────────────────────────

def check_python(version=None) -> Check:
    v = version or sys.version_info[:3]
    s = ".".join(map(str, v))
    if v >= (3, 14):
        return Check("python", FAIL, f"Python {s}: pinned pydantic-core 2.14.1 cannot build",
                     "use Python 3.12 (brew install python@3.12; python3.12 -m venv .venv)")
    if v < (3, 11):
        return Check("python", WARN, f"Python {s} is older than tested versions", "use 3.12")
    return Check("python", PASS, f"Python {s}")


def check_env(api_base: Optional[str]) -> List[Check]:
    out = []
    if not os.getenv("CENSUS_API_KEY"):
        out.append(Check("env:CENSUS_API_KEY", FAIL, "not set (baselines, housing stock)", "add it to .env"))
    else:
        out.append(Check("env:CENSUS_API_KEY", PASS, "set"))
    remote = bool(api_base) and "127.0.0.1" not in api_base and "localhost" not in api_base
    if remote and not os.getenv("HOMEFIT_PROXY_SECRET"):
        out.append(Check("env:HOMEFIT_PROXY_SECRET", FAIL, "remote API needs the proxy secret", "export HOMEFIT_PROXY_SECRET"))
    for key, why in (("FBI_CRIME_API_KEY", "crime data"), ("TRANSITLAND_API_KEY", "transit"),
                     ("SCHOOLDIGGER_APPID", "schools (off by default)")):
        alt = os.getenv("FBI_API_KEY") if key == "FBI_CRIME_API_KEY" else None
        if not (os.getenv(key) or alt):
            out.append(Check(f"env:{key}", WARN if "schools" in why else FAIL, f"not set ({why})", "add it to .env"))
    return out


# ── network ─────────────────────────────────────────────────────────────────

# Health is judged at fixed, known-dense US reference points (Times Square, Central Park), NOT at a
# metro's first pin: a pin in a quiet spot returns nothing and would look like a dead server.
REF_DENSE = (40.7580, -73.9855)
REF_PARKS = (40.7829, -73.9654)


def _probe_overpass(url: str, lat: float, lon: float, timeout: float = 30.0) -> Dict[str, object]:
    import requests
    tiny = f"[out:json][timeout:25];node(around:500,{REF_DENSE[0]},{REF_DENSE[1]})[amenity];out 3;"
    # Same shape as the app's heaviest local query: a parks count within the daily-use radius.
    heavy = (f"[out:json][timeout:30];(way[\"leisure\"~\"^(park|garden)$\"](around:1500,{REF_PARKS[0]},{REF_PARKS[1]});"
             f"relation[\"leisure\"~\"^(park|garden)$\"](around:1500,{REF_PARKS[0]},{REF_PARKS[1]}););out count;")
    res: Dict[str, object] = {"url": url, "ok": False, "seconds": None, "error": ""}
    t0 = time.time()
    try:
        r = requests.post(url, data={"data": tiny}, timeout=timeout, headers={"User-Agent": "HomeFit/1.0"})
        if r.status_code != 200:
            res["error"] = f"HTTP {r.status_code}"
            return res
        if not r.json().get("elements"):
            res["error"] = "200 but no data (regional server?)"
            return res
        r2 = requests.post(url, data={"data": heavy}, timeout=timeout, headers={"User-Agent": "HomeFit/1.0"})
        if r2.status_code != 200:
            res["error"] = f"light query ok, parks query HTTP {r2.status_code}"
            return res
        res["ok"] = True
    except Exception as e:  # noqa: BLE001
        res["error"] = f"{type(e).__name__}: {str(e)[:80]}"
    res["seconds"] = round(time.time() - t0, 1)
    return res


def check_overpass(lat: float, lon: float, probe: Callable = _probe_overpass) -> List[Check]:
    configured = (os.getenv("OVERPASS_URL") or "").strip()
    urls = ([configured] if configured else []) + [u for u in OVERPASS_CANDIDATES if u != configured]
    results = [probe(u, lat, lon) for u in urls]
    healthy = sorted([r for r in results if r["ok"] and (r["seconds"] or 99) <= OVERPASS_SLOW_S],
                     key=lambda r: r["seconds"])
    detail = "; ".join(f"{r['url'].split('/')[2]}: " + (f"ok {r['seconds']}s" if r["ok"] else r["error"]) for r in results)
    if not healthy:
        slow = [r for r in results if r["ok"]]
        if slow:
            return [Check("overpass", WARN, f"only slow servers answer. {detail}", "expect timeouts; consider a private Overpass")]
        return [Check("overpass", FAIL, f"no Overpass server answers. {detail}", "wait, or run a private Overpass instance")]
    best = healthy[0]["url"]
    first = results[0]
    if first["ok"] and (first["seconds"] or 99) <= OVERPASS_SLOW_S:
        return [Check("overpass", PASS, detail)]
    return [Check("overpass", FAIL, f"the server the app tries first is down. {detail}",
                  f"set OVERPASS_URL={best} in .env and restart the API")]


def check_http(name: str, fn: Callable[[], str], fix: str) -> Check:
    try:
        return Check(name, PASS, fn())
    except Exception as e:  # noqa: BLE001
        return Check(name, FAIL, f"{type(e).__name__}: {str(e)[:100]}", fix)


def check_api(api_base: str) -> Check:
    import requests
    def go():
        r = requests.get(f"{api_base}/health", timeout=30,
                         headers={"X-HomeFit-Proxy-Secret": os.getenv("HOMEFIT_PROXY_SECRET", "")})
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}")
        return f"{api_base} healthy"
    return check_http("api", go, "start the API (uvicorn main:app) or fix HOMEFIT_API_BASE / the proxy secret")


def check_census() -> Check:
    import requests
    def go():
        r = requests.get("https://api.census.gov/data/2022/acs/acs5",
                         params={"get": "NAME", "for": "state:48", "key": os.getenv("CENSUS_API_KEY", "")}, timeout=30)
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}")
        return "Census API answers with the key"
    return check_http("census", go, "check CENSUS_API_KEY")


def check_transitland(lat: float, lon: float) -> Check:
    import requests
    def go():
        r = requests.get("https://transit.land/api/v2/rest/routes",
                         params={"lat": lat, "lon": lon, "radius": 2000, "limit": 1,
                                 "apikey": os.getenv("TRANSITLAND_API_KEY", "")}, timeout=30)
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}")
        return "Transitland answers with the key"
    return check_http("transitland", go, "check TRANSITLAND_API_KEY / quota")


# ── metro prerequisites (offline) ───────────────────────────────────────────

def check_csv(rows: List[Dict[str, str]]) -> List[Check]:
    need = {"name", "county_borough", "state_abbr", "search_query", "lat", "lon"}
    if not rows:
        return [Check("csv", FAIL, "empty or unreadable", "create the place list")]
    missing = need - set(rows[0])
    if missing:
        return [Check("csv", FAIL, f"missing columns {sorted(missing)}", "add them")]
    bad, seen, dup = [], set(), []
    for r in rows:
        try:
            float(r["lat"]); float(r["lon"])
        except ValueError:
            bad.append(r["name"])
        k = (r["name"], r["county_borough"], r["state_abbr"])
        if k in seen:
            dup.append(r["name"])
        seen.add(k)
    if bad or dup:
        return [Check("csv", FAIL, f"bad coordinates: {bad[:5]}; duplicates: {dup[:5]}", "fix the place list")]
    states = sorted({r["state_abbr"] for r in rows})
    return [Check("csv", PASS, f"{len(rows)} places in {', '.join(states)}")]


GAZETTEER_URL = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2023_Gazetteer/2023_Gaz_place_national.zip"
PIN_WARN_KM = 5.0


def _load_gazetteer() -> Dict[tuple, List[tuple]]:
    """Census place internal points: {(state, lowercased name): [(lat, lon), ...]}, cached under data_cache/."""
    import re
    import urllib.request
    import zipfile
    cache = REPO / "data_cache" / "gazetteer_places_2023.zip"
    if not cache.is_file():
        cache.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(GAZETTEER_URL, cache)
    z = zipfile.ZipFile(cache)
    lines = z.read(z.namelist()[0]).decode("latin1").splitlines()
    head = [x.strip() for x in lines[0].split("\t")]
    out: Dict[tuple, List[tuple]] = {}
    for line in lines[1:]:
        r = dict(zip(head, [x.strip() for x in line.split("\t")]))
        nm = re.sub(r"\s+(city|town|village|borough|CDP|township|municipality)$", "", r["NAME"], flags=re.I).lower()
        out.setdefault((r["USPS"], nm), []).append((float(r["INTPTLAT"]), float(r["INTPTLONG"])))
    return out


def _km(a, b) -> float:
    import math
    p = math.pi / 180
    h = 0.5 - math.cos((b[0] - a[0]) * p) / 2 + math.cos(a[0] * p) * math.cos(b[0] * p) * (1 - math.cos((b[1] - a[1]) * p)) / 2
    return 12742 * math.asin(math.sqrt(h))


PIN_EXCEPTIONS = REPO / "data" / "pin_exceptions.json"


def _pin_exceptions() -> Dict[str, str]:
    try:
        return {k: v for k, v in json.loads(PIN_EXCEPTIONS.read_text()).items() if not k.startswith("_")}
    except (OSError, ValueError):
        return {}


def check_pins(rows: List[Dict[str, str]], gazetteer: Optional[Dict[tuple, List[tuple]]] = None,
               exceptions: Optional[Dict[str, str]] = None) -> Check:
    """Mandatory check of the place list: a suburb whose pin is far from the Census center of the place of that
    name is probably geocoded to the wrong town and would be scored as a different place. A far pin must either be
    fixed or listed with a reason in data/pin_exceptions.json (keys "Name|ST")."""
    exceptions = _pin_exceptions() if exceptions is None else exceptions
    try:
        gaz = gazetteer if gazetteer is not None else _load_gazetteer()
    except Exception as e:  # noqa: BLE001
        return Check("pins", WARN, f"could not load the Census gazetteer ({type(e).__name__}); pins unchecked")
    far = []
    reviewed = 0
    for r in rows:
        if r.get("type") != "suburb":
            continue
        cands = gaz.get((r["state_abbr"], r["name"].lower()))
        if not cands:
            continue
        d = min(_km((float(r["lat"]), float(r["lon"])), c) for c in cands)
        if d > PIN_WARN_KM:
            if f"{r['name']}|{r['state_abbr']}" in exceptions:
                reviewed += 1
            else:
                far.append((round(d, 1), r["name"], r["state_abbr"]))
    if far:
        far.sort(reverse=True)
        return Check("pins", FAIL, "pins far from the Census center of the town of that name (km, town): "
                     + "; ".join(f"{d} {n}, {s}" for d, n, s in far[:12]),
                     "open each in a map and fix the pin, or if it is right add \"Name|ST\": \"reason\" to "
                     "data/pin_exceptions.json")
    note = f" ({reviewed} far pins covered by reviewed exceptions)" if reviewed else ""
    return Check("pins", PASS, "every suburb pin is near its Census town center" + note)


def check_baseline(metro: str) -> Check:
    sys.path.insert(0, str(REPO))
    from scripts.baselines.build_metro_baselines_from_cbsa import CBSA_TO_KEY
    key = f"{metro}_metro"
    if key not in set(CBSA_TO_KEY.values()):
        return Check("baseline:cbsa", FAIL, f"{key} not registered in the baseline builder",
                     "add the CBSA to CBSA_COUNTIES / CBSA_TO_KEY (playbook Phase A)")
    data = json.loads((REPO / "data" / "status_signal_baselines.json").read_text())
    if key not in data:
        return Check("baseline:cbsa", FAIL, f"{key} registered but not built",
                     f"PYTHONPATH=. python scripts/baselines/build_metro_baselines_from_cbsa.py --only {key}")
    return Check("baseline:cbsa", PASS, f"{key} registered and built")


def check_precincts(rows: List[Dict[str, str]]) -> List[Check]:
    out = []
    for st in sorted({r["state_abbr"] for r in rows}):
        p = REPO / "data" / "election" / f"{st.lower()}_precincts.json"
        n = sum(1 for r in rows if r["state_abbr"] == st)
        if p.is_file():
            out.append(Check(f"politics:{st}", PASS, f"precinct file present ({n} places)"))
        else:
            out.append(Check(f"politics:{st}", FAIL, f"no precinct file; political lean empty for {n} places",
                             f"download_vest_shapefiles.py --states {st} --build"))
    return out


def check_crime_source(metro: str) -> Check:
    sys.path.insert(0, str(REPO))
    from data_sources import crime_api
    if metro in crime_api._OPEN_DATA_CITY_GEOID:
        return Check("crime:city", PASS, f"incident-level source registered for {metro}")
    return Check("crime:city", WARN, f"no incident-level crime source for {metro}: neighborhoods in the core "
                 "city share one city-wide rate", "add a fetcher in data_sources/crime_api.py (playbook Phase A2)")


def check_registration(metro: str, csv_path: Optional[Path] = None) -> List[Check]:
    out = []
    meta = (REPO / "frontend" / "lib" / "catalogMetros.ts").read_text()
    out.append(Check("frontend:registry", PASS if f"'{metro}'" in meta else FAIL,
                     "in catalogMetros.ts" if f"'{metro}'" in meta else "missing from catalogMetros.ts",
                     "" if f"'{metro}'" in meta else "add to CATALOG_METROS and CATALOG_METRO_META"))
    fname = f"{metro}_metro_place_catalog_scores_merged.composites_recomputed.jsonl"
    cfg = (REPO / "frontend" / "next.config.js").read_text()
    out.append(Check("frontend:bundle", PASS if fname in cfg else FAIL,
                     "in next.config.js" if fname in cfg else "missing from next.config.js",
                     "" if fname in cfg else "add to outputFileTracingIncludes"))
    return out


def check_existing_output(path: Path) -> Check:
    if not path.is_file():
        return Check("output", PASS, "no previous output; fresh run")
    from .diagnose import diagnose, load_rows
    rows = load_rows(path)
    d = diagnose(rows)
    if d["material_places"]:
        return Check("output", WARN, f"{path.name} exists with {len(d['material_places'])} places that have material gaps; "
                     "a resume will keep those rows", "run `diagnose`, or move the file aside for a clean run")
    return Check("output", PASS, f"{path.name} exists and has no material gaps")


# ── runner ──────────────────────────────────────────────────────────────────

def run(metro: str, csv_path: Path, api_base: Optional[str], out_path: Optional[Path] = None,
        network: bool = True) -> List[Check]:
    _load_env()
    checks: List[Check] = [check_python()]
    checks += check_env(api_base)
    rows = read_csv(csv_path) if csv_path.is_file() else []
    checks += check_csv(rows)
    if rows and checks[-1].status != FAIL:
        checks.append(check_pins(rows))
    if rows:
        lat, lon = float(rows[0]["lat"]), float(rows[0]["lon"])
        checks += [check_baseline(metro), *check_precincts(rows), check_crime_source(metro), *check_registration(metro)]
        if network:
            checks += check_overpass(lat, lon)
            checks += [check_census(), check_transitland(lat, lon)]
            if api_base:
                checks.append(check_api(api_base))
    if out_path:
        checks.append(check_existing_output(out_path))
    return checks


def format_report(checks: List[Check]) -> str:
    icon = {PASS: "PASS", WARN: "WARN", FAIL: "FAIL"}
    lines = ["METRO PREFLIGHT", "=" * 70]
    for c in checks:
        lines.append(f"[{icon[c.status]}] {c.name}: {c.detail}")
        if c.status != PASS and c.fix:
            lines.append(f"        fix: {c.fix}")
    fails = sum(c.status == FAIL for c in checks)
    warns = sum(c.status == WARN for c in checks)
    lines += ["", f"{fails} blocking, {warns} warnings. " + ("DO NOT START SCORING." if fails else "Clear to start.")]
    return "\n".join(lines)
