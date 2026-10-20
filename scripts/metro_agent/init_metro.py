"""
Set up a new metro from a spec: prerequisites, place list, registry entry, baselines. Everything the old playbook
had as hand edits (CBSA dict, frontend lists, education script lists, pin exceptions) is now generated from data.

  PYTHONPATH=. python -m scripts.metro_agent init --metro tucson                    # spec at data/metro_specs/tucson.json
  PYTHONPATH=. python -m scripts.metro_agent init --metro tucson --fetch --yes      # also fetch missing state data

After init:   run --metro X   ->   finish --metro X   ->   ship --metro X
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from . import place_list as pl
from . import prereqs
from . import preflight as pf
from . import registry

REPO = registry.REPO
PALETTE = ["#E0A100", "#8E44AD", "#1B9AAA", "#E4572E", "#2E7D32", "#6D4C41", "#C62828", "#283593", "#00897B", "#AD1457",
           "#558B2F", "#D1495B", "#0E7C86", "#B5651D", "#6B5CE7", "#2A9D8F"]


def load_spec(metro: str, path: Optional[Path] = None) -> Dict[str, Any]:
    p = path or REPO / "data" / "metro_specs" / f"{metro}.json"
    spec = json.loads(p.read_text())
    missing = [k for k in ("label", "long_label", "cbsa", "states") if k not in spec]
    if missing:
        raise ValueError(f"spec {p} lacks {', '.join(missing)}")
    if not (spec.get("neighborhoods") or spec.get("suburbs")):
        raise ValueError(f"spec {p} lists no neighborhoods or suburbs")
    spec["slug"] = metro
    return spec


def _upsert_registry(spec: Dict[str, Any], csv_path: Path, log: Callable[[str], None]) -> None:
    metros = registry.load()
    slug = spec["slug"]
    old = metros.get(slug, {})
    cbsa = None
    if prereqs.DELINEATION_JSON.is_file():
        d = json.loads(prereqs.DELINEATION_JSON.read_text()).get(spec["cbsa"])
        cbsa = {spec["cbsa"]: d["counties"]} if d else None
    entry = {
        "label": spec["label"], "long_label": spec["long_label"],
        "color": spec.get("color") or old.get("color") or PALETTE[len(metros) % len(PALETTE)],
        "bounds": registry.bounds_from_places(csv_path),
        "status": old.get("status", "building"),
        "states": spec["states"],
    }
    if cbsa:
        entry["cbsa"] = cbsa
    # tag rule for untagged places: state alone when this metro is the only one in the state, else by county
    counties = registry.counties_from_places(csv_path)
    shares = [s for s, m in metros.items() if s != slug and set(m.get("states", [])) & set(spec["states"])]
    st = spec["states"][0]
    if shares:
        entry["inference"] = {"state": st, "counties": counties.get(st, [])}
        for s in shares:                                  # a neighbour that used a state-only rule now needs counties too
            inf = metros[s].get("inference")
            other_csv = REPO / "data" / f"{s}_metro_place_catalog.csv"
            if inf and not inf.get("counties") and other_csv.is_file():
                inf["counties"] = registry.counties_from_places(other_csv).get(inf["state"], [])
                log(f"  {s}: inference rule now by county (it shares {st} with {slug})")
    else:
        entry["inference"] = {"state": st}
    metros[slug] = entry
    registry.save(metros)
    log(f"  registry: {slug} ({entry['status']})")


def init(metro: str, *, spec_path: Optional[Path] = None, fetch: bool = False, yes: bool = False,
         log: Callable[[str], None] = print) -> int:
    pf._load_env()
    spec = load_spec(metro, spec_path)
    log(f"== init {metro}: {spec['long_label']} (CBSA {spec['cbsa']}, states {', '.join(spec['states'])})")

    if not prereqs.DELINEATION_JSON.is_file():
        if fetch and yes:
            prereqs.fetch_delineation(log)
        else:
            log("The Census CBSA definition is not cached. Re-run with --fetch --yes (downloads one 140 KB file from census.gov).")
            return 2

    log("\n== prerequisites")
    reps = [prereqs.report(s) for s in spec["states"]]
    log(prereqs.format_report(reps))
    if fetch:
        prereqs.fetch(spec["states"], yes=yes, log=log)
        reps = [prereqs.report(s) for s in spec["states"]]
    blocking = [r["state"] for r in reps if not (r["election"] and r["snapshot"] and r["tiger"] and r["bundle"])]
    if blocking and not fetch:
        log(f"\nMissing data for {', '.join(blocking)}. Run with --fetch (plan) or --fetch --yes (do it).")
    if any(not r["overpass"] for r in reps):
        log("\nStopping: the private Overpass server does not cover every state of this metro yet.")
        return 2

    url = os.environ.get("OVERPASS_URL", "").strip()
    if not url:
        log("OVERPASS_URL is not set (open the tunnel to the private server first)")
        return 2

    log("\n== place list")
    rows, notes, problems = pl.build(spec, url, log)
    csv_path = REPO / "data" / f"{metro}_metro_place_catalog.csv"
    pl.write_csv(rows, csv_path)
    n_neigh = sum(1 for r in rows if r["type"] == "neighborhood")
    log(f"  wrote {csv_path.relative_to(REPO)}: {len(rows)} places ({n_neigh} neighborhoods)")
    for n in notes:
        log("  note: " + n)
    for p in problems:
        log("  PROBLEM: " + p)
    if problems:
        log("\nFix the problems above (edit the spec) and re-run init. The registry was not updated.")
        return 1
    added = pl.record_pin_exceptions(rows, pl.load_gazetteer())
    log(f"  pin exceptions recorded: {added}")

    log("\n== registry and baselines")
    _upsert_registry(spec, csv_path, log)
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "baselines" / "build_metro_baselines_from_cbsa.py"), "--only", f"{metro}_metro"],
                       cwd=str(REPO), env={**os.environ, "PYTHONPATH": str(REPO)}, capture_output=True, text=True)
    ok = f"Updated {metro}_metro in baselines" in r.stdout
    log("  baselines: " + ("built" if ok else "FAILED: " + (r.stdout + r.stderr)[-300:]))
    if not ok:
        return 1
    log(f"\nNext: PYTHONPATH=. python -m scripts.metro_agent preflight --metro {metro}   then   run --metro {metro}")
    return 0
