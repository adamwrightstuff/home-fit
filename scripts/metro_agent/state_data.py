"""Per-state data readiness: election (precinct) data and crime-source coverage, with one command to build what's missing.

    PYTHONPATH=. python -m scripts.metro_agent state --metro denver        # states found in the place list
    PYTHONPATH=. python -m scripts.metro_agent state --state CO --build    # download + build the precinct file

What it checks for a state:
  * a precinct file exists (data/election/<st>_precincts.json)
  * how much of it carries 2024 results (some states redrew precincts after 2020 and cannot be joined: the lookup then
    shows the 2020 lean, labelled as such)
  * the Harvard Dataverse source files are registered for the state (otherwise the downloader cannot fetch it)
  * how many places in data/crime_agency_map.json are mapped for the state
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

REPO = Path(__file__).resolve().parents[2]
MIN_2024_SHARE = 0.5


def registered_sources(state: str) -> Dict[str, bool]:
    sys.path.insert(0, str(REPO / "scripts" / "collectors"))
    try:
        import download_vest_shapefiles as dv  # type: ignore
        return {"shapefile_2020": state in dv._SHPZIP_2020, "results_2024": state in dv._CSV_2024}
    except Exception:  # noqa: BLE001
        return {"shapefile_2020": False, "results_2024": False}


def election_status(state: str) -> Dict[str, Any]:
    p = REPO / "data" / "election" / f"{state.lower()}_precincts.json"
    if not p.is_file():
        return {"file": False}
    arr = json.loads(p.read_text())
    n = len(arr)
    n24 = sum(1 for r in arr if (r.get("dem_2024", 0) + r.get("rep_2024", 0)) > 0)
    return {"file": True, "precincts": n, "with_2024": n24, "share_2024": round(n24 / n, 2) if n else 0.0}


def crime_map_entries(state: str) -> int:
    try:
        return len((json.loads((REPO / "data" / "crime_agency_map.json").read_text()).get(state.upper()) or {}))
    except (OSError, ValueError):
        return 0


def report(state: str) -> Dict[str, Any]:
    state = state.upper()
    el, src = election_status(state), registered_sources(state)
    issues: List[str] = []
    if not el["file"]:
        if not (src["shapefile_2020"] and src["results_2024"]):
            issues.append("no precinct file, and the Dataverse source IDs for this state are not registered in "
                          "scripts/collectors/download_vest_shapefiles.py (add _SHPZIP_2020 and _CSV_2024 entries, "
                          "IDs from doi:10.7910/DVN/K7760H and doi:10.7910/DVN/NYTPDU)")
        else:
            issues.append(f"no precinct file: run  state --state {state} --build")
    elif el["share_2024"] < MIN_2024_SHARE:
        issues.append(f"only {int(el['share_2024'] * 100)}% of precincts have 2024 results; political lean will show "
                      "2020 data (labelled). Precincts were probably redrawn; a coarser join is needed for 2024")
    return {"state": state, "election": el, "sources": src, "crime_map_entries": crime_map_entries(state),
            "issues": issues}


def build(state: str, runner: Optional[Callable] = None, log: Callable[[str], None] = print) -> int:
    runner = runner or subprocess.call
    log(f"downloading and building precinct data for {state} …")
    return runner([sys.executable, str(REPO / "scripts" / "collectors" / "download_vest_shapefiles.py"),
                   "--states", state.upper(), "--build"], cwd=str(REPO), env=None)


def format_report(reports: List[Dict[str, Any]]) -> str:
    lines = ["STATE DATA READINESS", "=" * 70]
    for r in reports:
        el = r["election"]
        e = (f"precincts {el['precincts']}, 2024 results on {int(el['share_2024'] * 100)}%" if el["file"] else "no precinct file")
        lines.append(f"{r['state']}: {e}; crime agency map entries: {r['crime_map_entries']}")
        lines += [f"    ! {i}" for i in r["issues"]]
    lines += ["", "Crime: city incident sources are per city (data_sources/crime_api.py). For suburbs, after scoring, run "
              "`fbi --input <scores> --suggest` and add confirmed agencies to data/crime_agency_map.json."]
    return "\n".join(lines)
