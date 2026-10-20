"""
Per-state prerequisites for a new metro, checked and (with --yes) fetched. Nothing is downloaded or paid for without --yes,
and the plan states what, from where, and how much first.

  PYTHONPATH=. python -m scripts.metro_agent prereqs --state AZ --state NV            # check only
  PYTHONPATH=. python -m scripts.metro_agent prereqs --state AZ --fetch               # print the plan
  PYTHONPATH=. python -m scripts.metro_agent prereqs --state AZ --fetch --yes         # do it

What a state needs (METRO_EXPANSION_PLAYBOOK.md Phase A2/A3)
  election   data/election/<st>_precincts.json     Harvard Dataverse (VEST 2020 precinct maps + 2024 results), free
  tiger      data_cache/tiger_{sd,place}_2024/     census.gov TIGER/Line school districts + places, free, about 5 MB
  snapshot   data/school_snapshot/<ST>.json.gz     SchoolDigger, about 0.5 calls per 250 schools, $0.008 each (overage)
  bundle     data/school_geo/                      rebuilt from the TIGER and zone files; only byte-different files kept
  overpass   the private server's extract          NOT automated: provisioning is a decision (scripts/overpass_server/add_states.sh)
"""
from __future__ import annotations

import gzip
import json
import math
import re
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import requests

from . import registry

REPO = registry.REPO
UA = {"User-Agent": "HomeFit/1.0 (metro prerequisites)"}
DATAVERSE = "https://dataverse.harvard.edu/api/datasets/:persistentId/versions/:latest-published/files"
DOI_2020, DOI_2024 = "doi:10.7910/DVN/K7760H", "doi:10.7910/DVN/NYTPDU"
DELINEATION_URL = ("https://www2.census.gov/programs-surveys/metro-micro/geographies/reference-files/2023/"
                   "delineation-files/list1_2023.xlsx")
DELINEATION_JSON = REPO / "data_cache" / "cbsa_delineation_2023.json"
IDS_FILE = REPO / "data" / "election" / "dataverse_ids.json"
OVERPASS_STATES = REPO / "data" / "overpass_states.json"
SD_PER_SCHOOL_CALL = 500 / 1.35    # a snapshot holds about 1.35x the NCES school count; 500 schools per call


def _fips(state: str) -> str:
    from data_sources.school_districts import _STATE_FIPS

    return _STATE_FIPS[state]


# ----------------------------------------------------------------------------------------------
# status
# ----------------------------------------------------------------------------------------------
def overpass_states() -> List[str]:
    try:
        return json.loads(OVERPASS_STATES.read_text())["states"]
    except (OSError, ValueError, KeyError):
        return []


def report(state: str) -> Dict[str, Any]:
    fips = _fips(state)
    sd = REPO / "data_cache" / "tiger_sd_2024"
    pl = REPO / "data_cache" / "tiger_place_2024"
    return {
        "state": state,
        "election": (REPO / "data" / "election" / f"{state.lower()}_precincts.json").is_file(),
        "tiger": (sd / f"tl_2024_{fips}_unsd").is_dir() and (pl / f"tl_2024_{fips}_place").is_dir(),
        "snapshot": (REPO / "data" / "school_snapshot" / f"{state}.json.gz").is_file(),
        "bundle": (REPO / "data" / "school_geo" / f"place_{fips}.geojson.gz").is_file(),
        "overpass": state in overpass_states(),
    }


def format_report(reps: List[Dict[str, Any]]) -> str:
    lines = [f"{'state':6} {'election':9} {'tiger':6} {'snapshot':9} {'bundle':7} {'overpass':9}"]
    for r in reps:
        mark = lambda b: "ok" if b else "MISSING"  # noqa: E731
        lines.append(f"{r['state']:6} {mark(r['election']):9} {mark(r['tiger']):6} {mark(r['snapshot']):9} {mark(r['bundle']):7} {mark(r['overpass']):9}")
    miss = [r["state"] for r in reps if not r["overpass"]]
    if miss:
        lines.append(f"\nOverpass does not cover {', '.join(miss)}: add them to the private server "
                     "(scripts/overpass_server/add_states.sh, a rebuild of a few hours) and list them in data/overpass_states.json.")
    return "\n".join(lines)


# ----------------------------------------------------------------------------------------------
# fetchers
# ----------------------------------------------------------------------------------------------
def _dataverse_files(doi: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    start = 0
    while True:
        r = requests.get(DATAVERSE, params={"persistentId": doi, "limit": 100, "offset": start}, headers=UA, timeout=60)
        r.raise_for_status()
        d = r.json()["data"]
        out += d
        if len(d) < 100:
            return out
        start += 100


def election_ids(state: str) -> Dict[str, Any]:
    """Dataverse file IDs and sizes for a state's 2020 precinct map and 2024 results."""
    st = state.lower()
    f20 = next((f for f in _dataverse_files(DOI_2020) if f["label"].lower() == f"{st}_2020.zip"), None)
    f24 = next((f for f in _dataverse_files(DOI_2024) if re.match(rf"2024-{st}-precinct-general\.", f["label"], re.I)), None)
    if not f20 or not f24:
        raise RuntimeError(f"{state}: no VEST 2020 map or no 2024 results file on Dataverse")
    return {"shp2020": f20["dataFile"]["id"], "csv2024": [f24["dataFile"]["id"], f24["label"]],
            "mb": round(((f20["dataFile"].get("filesize") or 0) + (f24["dataFile"].get("filesize") or 0)) / 1e6, 1)}


def plan(state: str) -> List[str]:
    r = report(state)
    out = []
    if not r["election"]:
        try:
            e = election_ids(state)
            out.append(f"election: download VEST 2020 map + 2024 results from Harvard Dataverse, {e['mb']} MB, free")
        except Exception as ex:  # noqa: BLE001
            out.append(f"election: cannot plan ({ex})")
    if not r["tiger"]:
        out.append("tiger: download TIGER/Line 2024 school districts and places from www2.census.gov, about 5 MB, free")
    if not r["snapshot"]:
        n = _nces_count(state)
        calls = math.ceil(n * 1.35 / 500) if n else "?"
        out.append(f"snapshot: SchoolDigger, about {calls} calls (~${calls * 0.008:.2f} at the overage rate)" if n else
                   "snapshot: SchoolDigger calls (NCES school count unavailable)")
    if not r["bundle"] or not r["tiger"]:
        out.append("bundle: rebuild data/school_geo from the downloaded files")
    return out


def _nces_count(state: str) -> int:
    p = REPO / "data_cache" / "nces_ccd_2324" / "ccd_sch_029_2324_w_1a_073124.csv"
    if not p.is_file():
        return 0
    import pandas as pd

    df = pd.read_csv(p, dtype=str, low_memory=False, usecols=["ST", "SY_STATUS", "LEVEL"])
    return int(((df.ST == state) & (df.SY_STATUS == "1") & df.LEVEL.isin(["Elementary", "Middle", "High", "Other"])).sum())


def fetch_election(state: str, log: Callable[[str], None]) -> None:
    e = election_ids(state)
    ids = json.loads(IDS_FILE.read_text()) if IDS_FILE.is_file() else {}
    ids[state] = {"shp2020": e["shp2020"], "csv2024": e["csv2024"]}
    IDS_FILE.write_text(json.dumps(ids, indent=2) + "\n")
    import tempfile

    d = tempfile.mkdtemp(prefix="vest_")          # a fresh empty directory; downloaded files are data, never code
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "collectors" / "download_vest_shapefiles.py"), "--states", state,
                        "--download-dir", d, "--build"], cwd=str(REPO), env={"PYTHONPATH": str(REPO), "PATH": "/usr/bin:/bin"},
                       capture_output=True, text=True)
    log(f"  election {state}: " + ("built" if (REPO / "data" / "election" / f"{state.lower()}_precincts.json").is_file() else "FAILED\n" + r.stdout[-400:] + r.stderr[-400:]))


def fetch_tiger(state: str, log: Callable[[str], None]) -> None:
    fips = _fips(state)
    import tempfile

    tmp = Path(tempfile.mkdtemp(prefix="tiger_"))
    for kind, folder, sub in (("UNSD", "tiger_sd_2024", "unsd"), ("ELSD", "tiger_sd_2024", "elsd"), ("SCSD", "tiger_sd_2024", "scsd"),
                              ("PLACE", "tiger_place_2024", "place")):
        r = requests.get(f"https://www2.census.gov/geo/tiger/TIGER2024/{kind}/tl_2024_{fips}_{sub}.zip", headers=UA, timeout=300)
        if r.status_code != 200:
            log(f"  tiger {state} {kind}: none published (HTTP {r.status_code}); fine for ELSD/SCSD")
            continue
        z = tmp / f"tl_2024_{fips}_{sub}.zip"
        z.write_bytes(r.content)
        dest = REPO / "data_cache" / folder / f"tl_2024_{fips}_{sub}"
        dest.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(z) as zf:
            zf.extractall(dest)
        log(f"  tiger {state} {kind}: {len(r.content) // 1024} KB")


def fetch_snapshot(state: str, log: Callable[[str], None]) -> None:
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "catalog" / "fetch_school_snapshot.py"), "--states", state],
                       cwd=str(REPO), env={**__import__("os").environ, "PYTHONPATH": str(REPO)}, capture_output=True, text=True)
    tail = [ln for ln in r.stdout.splitlines() if "calls" in ln or "schools" in ln][-2:]
    log(f"  snapshot {state}: " + (" | ".join(tail) or "FAILED " + r.stderr[-300:]))


def rebuild_bundle(log: Callable[[str], None]) -> None:
    """Rebuild data/school_geo, then restore files whose gzip bytes changed but whose content did not (header timestamps)."""
    subprocess.run([sys.executable, str(REPO / "scripts" / "catalog" / "build_school_data_bundle.py")], cwd=str(REPO),
                   env={**__import__("os").environ, "PYTHONPATH": str(REPO)}, capture_output=True, text=True)
    status = subprocess.run(["git", "status", "--short", "data/school_geo"], cwd=str(REPO), capture_output=True, text=True).stdout
    same = []
    for ln in status.splitlines():
        if ln[:2].strip() == "M":
            p = ln[3:]
            old = subprocess.run(["git", "show", "HEAD:" + p], cwd=str(REPO), capture_output=True).stdout
            if gzip.decompress(old) == gzip.open(REPO / p).read():
                same.append(p)
    if same:
        subprocess.run(["git", "checkout", "--"] + same, cwd=str(REPO), check=True)
    log(f"  bundle rebuilt; {len(same)} byte-different but identical files restored")


def fetch(states: List[str], *, yes: bool, log: Callable[[str], None] = print) -> int:
    any_plan = False
    for st in states:
        steps = plan(st)
        if steps:
            any_plan = True
            log(f"{st}:")
            for s in steps:
                log("  - " + s)
    if not any_plan:
        log("nothing to fetch")
        return 0
    if not yes:
        log("\nNothing was downloaded or paid for. Re-run with --yes to do the above.")
        return 0
    for st in states:
        r = report(st)
        if not r["election"]:
            fetch_election(st, log)
        if not r["tiger"]:
            fetch_tiger(st, log)
        if not r["snapshot"]:
            fetch_snapshot(st, log)
    rebuild_bundle(log)
    return 0


# ----------------------------------------------------------------------------------------------
# Census CBSA delineation -> data_cache/cbsa_delineation_2023.json
# ----------------------------------------------------------------------------------------------
def parse_delineation_xlsx(xlsx: Path) -> Dict[str, Any]:
    """Census CBSA delineation workbook (an xlsx is zipped XML, read without extra packages) -> {cbsa: {...}}."""
    import xml.etree.ElementTree as ET

    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    z = zipfile.ZipFile(xlsx)
    ss = ["".join(t.text or "" for t in si.iter(ns + "t")) for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall(ns + "si")]
    rows = []
    for rw in ET.fromstring(z.read("xl/worksheets/sheet1.xml")).iter(ns + "row"):
        cells = {}
        for c in rw.findall(ns + "c"):
            v = c.find(ns + "v")
            if v is None:
                continue
            col = 0
            for ch in re.match(r"[A-Z]+", c.get("r")).group(0):
                col = col * 26 + ord(ch) - 64
            cells[col - 1] = ss[int(v.text)] if c.get("t") == "s" else v.text
        rows.append(cells)
    hdr = next(i for i, r_ in enumerate(rows) if "CBSA Code" in r_.values())
    nm = {v: k for k, v in rows[hdr].items()}
    out: Dict[str, Any] = {}
    for r_ in rows[hdr + 1:]:
        code = r_.get(nm["CBSA Code"])
        if not code:
            continue
        o = out.setdefault(code, {"title": r_.get(nm["CBSA Title"]), "counties": {}, "county_names": []})
        o["counties"].setdefault(r_.get(nm["FIPS State Code"]), []).append(r_.get(nm["FIPS County Code"]))
        o["county_names"].append(re.sub(r"\s+(County|Parish)$", "", r_.get(nm["County/County Equivalent"], "")))
    for o in out.values():
        for k in o["counties"]:
            o["counties"][k] = sorted(o["counties"][k])
    return out


def fetch_delineation(log: Callable[[str], None] = print, xlsx: Optional[Path] = None) -> Path:
    """Cache the Census CBSA definition. Downloads one small public file unless `xlsx` (already on disk) is given."""
    import tempfile

    if xlsx is None:
        r = requests.get(DELINEATION_URL, headers=UA, timeout=120)
        r.raise_for_status()
        xlsx = Path(tempfile.mkdtemp(prefix="delineation_")) / "list1.xlsx"   # fresh empty directory
        xlsx.write_bytes(r.content)
        log(f"downloaded {len(r.content) // 1024} KB from census.gov")
    out = parse_delineation_xlsx(xlsx)
    DELINEATION_JSON.parent.mkdir(parents=True, exist_ok=True)
    DELINEATION_JSON.write_text(json.dumps(out))
    log(f"delineation cached for {len(out)} CBSAs -> {DELINEATION_JSON.relative_to(REPO)}")
    return DELINEATION_JSON
