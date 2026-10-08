#!/usr/bin/env python3
"""
Recompute ONLY the happiness index (and its breakdown and version stamp) from stored pillar scores.

Offline: no API, Census or Overpass calls. Touches nothing else in a row (no total score, longevity or
status signal), unlike recompute_catalog_composites.py, which also applies stored-data corrections.
Preserves each file's existing JSON formatting (compact or default).

  PYTHONPATH=. python3 scripts/catalog/recompute_happiness_only.py data/nyc_metro_place_catalog_scores_merged.jsonl ...
  Add --dry-run to report changes without writing.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import List

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_happiness():
    spec = importlib.util.spec_from_file_location("happiness_index_offline", REPO_ROOT / "pillars" / "happiness_index.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _version() -> str:
    for line in (REPO_ROOT / "pillars" / "composite_indices.py").read_text().splitlines():
        if line.startswith("INDEX_VERSION_HAPPINESS"):
            return line.split("=")[1].strip().strip('"')
    raise RuntimeError("INDEX_VERSION_HAPPINESS not found")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    hi = _load_happiness()
    version = _version()

    for path in args.files:
        raw_lines = path.read_text(encoding="utf-8").split("\n")
        compact = False
        for ln in raw_lines:
            if ln.strip():
                compact = json.dumps(json.loads(ln), separators=(",", ":")) == ln
                break
        dump = (lambda o: json.dumps(o, separators=(",", ":"))) if compact else json.dumps
        out: List[str] = []
        n = changed = 0
        deltas: List[float] = []
        for ln in raw_lines:
            if not ln.strip():
                out.append(ln)
                continue
            row = json.loads(ln)
            sc = row.get("score") if row.get("success") else None
            if isinstance(sc, dict):
                p = sc.get("livability_pillars") or {}
                state = (sc.get("location_info") or {}).get("state")
                new, bd = hi.compute_happiness_index_with_breakdown(
                    p.get("housing_value"), p.get("public_transit_access"), p.get("economic_opportunity"),
                    p.get("natural_beauty"), state,
                    social_fabric_details=p.get("social_fabric"),
                    community_safety_details=p.get("community_safety"),
                    neighborhood_amenities_details=p.get("neighborhood_amenities"),
                    education_details=p.get("quality_education"),
                    climate_risk_details=p.get("climate_risk"),
                    active_outdoors_details=p.get("active_outdoors"),
                )
                old = sc.get("happiness_index")
                n += 1
                if new is not None:
                    if isinstance(old, (int, float)):
                        deltas.append(new - old)
                    changed += 1
                    sc["happiness_index"] = new
                    sc["happiness_index_breakdown"] = bd
                    iv = (sc.setdefault("metadata", {})).setdefault("indices_version", {})
                    iv["happiness"] = version
            out.append(dump(row))
        mean = sum(deltas) / len(deltas) if deltas else 0.0
        print(f"{path.name}: {n} scored rows, {changed} recomputed, mean change {mean:+.2f}, "
              f"min {min(deltas, default=0):+.1f}, max {max(deltas, default=0):+.1f}")
        if not args.dry_run:
            path.write_text("\n".join(out), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
